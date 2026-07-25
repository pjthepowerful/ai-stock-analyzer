"""
Paula — Signal Study (decile analysis + factor correlation)
==========================================================

WHY THIS EXISTS
---------------
Backtesting completed TRADES gives you a dozen observations — far too few to say
anything statistically. This evaluates SIGNALS instead: it scores every stock on
every day over a multi-year window (no threshold, no position limits) and asks a
single question —

    Is the score monotonically related to forward return?

That turns 12 observations into tens of thousands. If mean forward return climbs
across score deciles, the score means something and the slope tells you where to
actually put MIN_SCORE. If the deciles are flat, the 21 factors are decoration
and no threshold will save the strategy.

A second analysis correlates the factor signals against each other to expose
collinearity — how few independent dimensions the 21 factors really span.

WHAT IT MEASURES (and does not)
-------------------------------
* It reproduces the SCAN score exactly: same compute_technicals + the same
  generate_trade_signal the live scan uses. No re-implementation, no drift.
* It is DAILY. The live scan score is daily too; the intraday VWAP/EMA overlay
  and news sentiment are applied elsewhere and are not reconstructable over two
  years, so they're out of scope here. This studies the daily signal engine,
  which is what MIN_SCORE gates.

HONEST CAVEATS — read these before trusting a green result
----------------------------------------------------------
1. SURVIVORSHIP BIAS. A fixed present-day universe omits delisted/bankrupt names,
   which biases forward returns UPWARD. Treat any positive edge as an optimistic
   ceiling. (Point-in-time universe membership would fix this; yfinance can't
   give it cheaply.)
2. OVERLAPPING WINDOWS. Consecutive days share most of their 5-day forward
   window, so observations are autocorrelated and naive significance is
   overstated. Use --sample 5 to make windows non-overlapping when you want
   honest error bars; the Information Coefficient (rank IC) is reported because
   it degrades gracefully under overlap.
3. NO COSTS. Forward returns here are gross. A real edge must survive the
   slippage/spread modeled in validation.py.

USAGE
-----
    python signal_study.py --years 2 --horizon 5 --sample 1
    python signal_study.py --universe my_tickers.txt --horizon 5 --sample 5

Outputs (written next to the script):
    signal_observations.csv   every (ticker, day, score, forward return, factors)
    signal_deciles.csv        the decile table
    factor_correlation.csv    the 21x21 factor correlation matrix
    *.png                     plots, if matplotlib is installed
"""

import argparse
import os
import sys
import warnings

import numpy as np
import pandas as pd

# engine.py installs the streamlit mock and puts the repo root on sys.path, so
# importing it first lets `import trading` succeed with the same setup the live
# backend uses.
import engine  # noqa: F401  (bootstraps trading's import environment)
import trading as T  # the live engine — compute_technicals + generate_trade_signal


# A liquid, sector-spread default universe. Deliberately fixed for reproducibility.
# NOTE: this is a survivorship-biased snapshot of today's names (see caveat #1).
DEFAULT_UNIVERSE = [
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "AVGO", "JPM", "V",
    "UNH", "MA", "HD", "PG", "COST", "LLY", "ABBV", "MRK", "PEP", "KO",
    "ADBE", "CRM", "NFLX", "AMD", "INTC", "QCOM", "TXN", "ORCL", "CSCO", "IBM",
    "BA", "CAT", "GE", "HON", "UPS", "DE", "LMT", "RTX", "MMM", "F",
    "XOM", "CVX", "COP", "SLB", "NEE", "DUK", "SO",
    "WMT", "TGT", "LOW", "NKE", "SBUX", "MCD", "DIS", "CMCSA",
    "PFE", "JNJ", "TMO", "ABT", "DHR", "BMY", "AMGN", "GILD",
    "BAC", "WFC", "GS", "MS", "C", "AXP", "BLK", "SCHW",
    "PLTR", "SNOW", "CRWD", "PANW", "NET", "DDOG", "SHOP", "UBER", "ABNB", "COIN",
    "MRNA", "RIVN", "LCID", "SOFI", "HOOD", "RBLX", "DKNG", "ROKU", "SQ", "PYPL",
    "MU", "LRCX", "AMAT", "KLAC", "ADI", "MRVL", "SMCI", "ARM", "ANET", "DELL",
]


# ── Factor extraction ────────────────────────────────────────────────────────
# The ~21 factor SIGNALS that feed generate_trade_signal, pulled straight from the
# technicals dict the engine computes. We correlate these to find collinearity.
# (We correlate the drivers, not the point weights — two factors whose drivers
# move together are redundant regardless of how many points each is worth.)
def extract_factors(tech: dict, price: float) -> dict:
    def sf(x, d=0.0):
        try:
            v = float(x)
            return v if np.isfinite(v) else d
        except Exception:
            return d

    sma20, sma50, sma200 = tech.get("sma_20"), tech.get("sma_50"), tech.get("sma_200")
    rsi = sf(tech.get("rsi"), 50)
    adx = sf(tech.get("adx"), 15)
    macd_h = sf(tech.get("macd_hist"), 0)
    vol_ratio = sf(tech.get("vol_ratio"), 1.0)
    bb_b = sf(tech.get("bb_pct_b"), 0.5)
    stoch_k = sf(tech.get("stoch_rsi_k"), 50)
    stoch_d = sf(tech.get("stoch_rsi_d"), 50)

    dist20 = ((price - sma20) / sma20 * 100) if sma20 else 0.0
    dist50 = ((price - sma50) / sma50 * 100) if sma50 else 0.0

    return {
        # Trend
        "f_above_200": 1.0 if (sma200 and price > sma200) else 0.0,
        "f_above_50": 1.0 if (sma50 and price > sma50) else 0.0,
        "f_above_20": 1.0 if (sma20 and price > sma20) else 0.0,
        "f_mas_stacked": 1.0 if (sma20 and sma50 and sma200 and sma20 > sma50 > sma200) else 0.0,
        "f_strong_uptrend": 1.0 if tech.get("trend_regime") == "strong_uptrend" else 0.0,
        "f_golden_cross": 1.0 if tech.get("ma_cross") == "golden_cross" else 0.0,
        "f_trend_slope": sf(tech.get("trend_slope"), 0),
        # Pullback / mean reversion
        "f_pullback_20": 1.0 if (-4 <= dist20 <= 1.5) else 0.0,
        "f_pullback_50": 1.0 if (sma50 and sma200 and price > sma200 and -3 <= dist50 <= 1) else 0.0,
        "f_dist_from_20": dist20,
        "f_bb_pct_b": bb_b,
        # Momentum
        "f_rsi": rsi,
        "f_rsi_sweet": 1.0 if (30 <= rsi <= 60) else 0.0,
        "f_macd_bull": 1.0 if macd_h > 0 else 0.0,
        "f_macd_accel": 1.0 if tech.get("macd_accel") == "expanding" else 0.0,
        "f_stoch_bull": 1.0 if stoch_k > stoch_d else 0.0,
        "f_mom_20d": sf(tech.get("mom_20d"), 0),
        # Trend strength / volume
        "f_adx": adx,
        "f_adx_trending": 1.0 if adx > 18 else 0.0,
        "f_vol_ratio": vol_ratio,
        "f_obv_rising": 1.0 if tech.get("obv_trend") == "rising" else 0.0,
        # Position
        "f_52w_range_pos": sf(tech.get("pct_in_52w_range"), 50),
        "f_vol_contracting": 1.0 if tech.get("volatility_contracting") else 0.0,
    }


FACTOR_COLS = None  # filled after first extraction


def _spearman(a: pd.Series, b: pd.Series) -> float:
    """Rank Information Coefficient without scipy: Spearman is just Pearson on the
    ranks, and pandas' Pearson path has no scipy dependency."""
    try:
        return float(a.rank().corr(b.rank(), method="pearson"))
    except Exception:
        return float("nan")


# ── Observation builder ──────────────────────────────────────────────────────
def build_observations(hist_by_ticker: dict, horizon: int = 5,
                       min_history: int = 260, sample_every: int = 1) -> pd.DataFrame:
    """Walk each ticker day by day. At day t: score using ONLY data up to t, then
    look forward `horizon` trading days for the realized return. No lookahead."""
    global FACTOR_COLS
    rows = []
    n_tickers = len(hist_by_ticker)
    for ti, (tk, hist) in enumerate(hist_by_ticker.items(), 1):
        if hist is None or len(hist) < min_history + horizon + 1:
            continue
        closes = hist["Close"].to_numpy(dtype=float)
        n = len(hist)
        for t in range(min_history, n - horizon, sample_every):
            # Bounded trailing window (>=252 covers SMA200 + 52w range) keeps each
            # call cheap and point-in-time — it ends AT day t, never after.
            window = hist.iloc[max(0, t - min_history + 1): t + 1]
            tech = T.compute_technicals(window)
            if not tech:
                continue
            price = closes[t]
            if price <= 0:
                continue
            sig = T.generate_trade_signal({"price": price, "technicals": tech})
            score = sig.get("score", 0)
            if not score:
                continue
            fwd = closes[t + horizon] / price - 1.0
            feats = extract_factors(tech, price)
            if FACTOR_COLS is None:
                FACTOR_COLS = list(feats.keys())
            rows.append({"ticker": tk, "t": int(t), "score": float(score),
                         "fwd_ret": float(fwd), **feats})
        print(f"  [{ti}/{n_tickers}] {tk}: {len([r for r in rows if r['ticker']==tk])} obs")
    return pd.DataFrame(rows)


# ── Decile study ─────────────────────────────────────────────────────────────
def decile_study(df: pd.DataFrame, horizon: int) -> pd.DataFrame:
    """Bucket observations into deciles by score and report mean forward return
    per decile, plus the rank Information Coefficient (the headline number)."""
    n = len(df)
    if n < 100:
        print(f"\n⚠️  Only {n} observations — too few to trust. Widen the window.")
    # Rank IC: Spearman correlation of score vs forward return. This is THE metric.
    ic = _spearman(df["score"], df["fwd_ret"])
    pearson = df["score"].corr(df["fwd_ret"], method="pearson")

    # Deciles by score (qcut handles ties/uneven distributions).
    try:
        df = df.copy()
        df["decile"] = pd.qcut(df["score"].rank(method="first"), 10, labels=False) + 1
    except Exception:
        df["decile"] = pd.cut(df["score"], 10, labels=False) + 1

    g = df.groupby("decile")
    table = pd.DataFrame({
        "n": g.size(),
        "score_min": g["score"].min(),
        "score_max": g["score"].max(),
        "mean_fwd_ret_pct": g["fwd_ret"].mean() * 100,
        "median_fwd_ret_pct": g["fwd_ret"].median() * 100,
        "hit_rate_pct": g["fwd_ret"].apply(lambda s: (s > 0).mean() * 100),
        "std_pct": g["fwd_ret"].std() * 100,
    }).reset_index()

    # Monotonicity: how consistently does mean forward return rise with decile?
    means = table["mean_fwd_ret_pct"].to_numpy()
    up_steps = int(np.sum(np.diff(means) > 0))
    mono = up_steps / (len(means) - 1) if len(means) > 1 else 0
    top_minus_bottom = means[-1] - means[0]

    print("\n" + "=" * 74)
    print(f"DECILE STUDY  —  {n:,} observations, {horizon}-day forward return")
    print("=" * 74)
    print(table.to_string(index=False, float_format=lambda x: f"{x:8.3f}"))
    print("-" * 74)
    print(f"Rank IC (Spearman score vs fwd):   {ic:+.4f}   "
          f"({'MEANINGFUL' if abs(ic) >= 0.03 else 'NEGLIGIBLE — score barely predicts'})")
    print(f"Pearson (score vs fwd):            {pearson:+.4f}")
    print(f"Top decile − bottom decile:        {top_minus_bottom:+.3f}%  per {horizon}d")
    print(f"Monotonic up-steps:                {up_steps}/9 "
          f"({mono*100:.0f}% of steps increase)")
    verdict = (
        "Score is well-ordered — set MIN_SCORE where the slope turns up." if (abs(ic) >= 0.03 and mono >= 0.6 and top_minus_bottom > 0)
        else "Weak/flat ordering — the score is near-random; a threshold won't rescue it." if abs(ic) < 0.03
        else "Mixed — some signal, but not cleanly monotonic. Treat MIN_SCORE tuning with suspicion."
    )
    print(f"\nVERDICT: {verdict}")
    print("Reminder: gross returns, survivorship-biased, overlapping windows. "
          "This is a ceiling, not a promise.")
    return table


# ── Factor correlation ───────────────────────────────────────────────────────
def factor_correlation(df: pd.DataFrame, threshold: float = 0.8) -> pd.DataFrame:
    """Correlation matrix over the factor signals. Pairs above `threshold` are
    redundant — they add points but not independent information."""
    cols = [c for c in df.columns if c.startswith("f_")]
    corr = df[cols].corr(method="pearson")

    print("\n" + "=" * 74)
    print(f"FACTOR COLLINEARITY  —  {len(cols)} factors")
    print("=" * 74)
    # Also show each factor's own IC vs forward return — a factor that's both
    # redundant AND uncorrelated with returns is pure dead weight.
    ics = {c: _spearman(df[c], df["fwd_ret"]) for c in cols}
    redundant = []
    for i in range(len(cols)):
        for j in range(i + 1, len(cols)):
            r = corr.iloc[i, j]
            if abs(r) >= threshold:
                redundant.append((cols[i], cols[j], r))
    if redundant:
        print(f"\nRedundant pairs (|r| ≥ {threshold}) — candidates to merge or drop:")
        for a, b, r in sorted(redundant, key=lambda x: -abs(x[2])):
            print(f"  {r:+.2f}   {a:22} ~ {b:22}"
                  f"  (IC {ics[a]:+.3f} / {ics[b]:+.3f})")
    else:
        print(f"\nNo pairs above |r| ≥ {threshold} — factors are reasonably independent.")

    print("\nPer-factor rank IC vs forward return (weakest predictors first):")
    for c, v in sorted(ics.items(), key=lambda x: abs(x[1])):
        flag = "  ← near-zero, consider dropping" if abs(v) < 0.01 else ""
        print(f"  {c:24} IC {v:+.4f}{flag}")
    return corr


# ── Plotting (optional) ──────────────────────────────────────────────────────
def maybe_plot(table: pd.DataFrame, corr: pd.DataFrame, outdir: str):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        print("\n(matplotlib not installed — skipping plots; CSVs still written)")
        return
    # Decile bar chart
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.bar(table["decile"], table["mean_fwd_ret_pct"], color="#16a34a")
    ax.axhline(0, color="#888", lw=0.8)
    ax.set_xlabel("Score decile (1 = lowest, 10 = highest)")
    ax.set_ylabel("Mean forward return (%)")
    ax.set_title("Forward return by score decile")
    fig.tight_layout()
    fig.savefig(os.path.join(outdir, "signal_deciles.png"), dpi=120)
    # Correlation heatmap
    fig2, ax2 = plt.subplots(figsize=(11, 9))
    im = ax2.imshow(corr.to_numpy(), cmap="RdBu_r", vmin=-1, vmax=1)
    ax2.set_xticks(range(len(corr))); ax2.set_xticklabels(corr.columns, rotation=90, fontsize=6)
    ax2.set_yticks(range(len(corr))); ax2.set_yticklabels(corr.columns, fontsize=6)
    fig2.colorbar(im, ax=ax2, shrink=0.7)
    ax2.set_title("Factor correlation matrix")
    fig2.tight_layout()
    fig2.savefig(os.path.join(outdir, "factor_correlation.png"), dpi=120)
    print(f"\nPlots written to {outdir}/signal_deciles.png and factor_correlation.png")


# ── Data download ────────────────────────────────────────────────────────────
def download(universe: list, years: float) -> dict:
    """Fetch daily history for the universe. Tries yfinance in bulk first; for any
    ticker it misses (Yahoo throttling, the fc.yahoo.com cookie failure, DNS
    blockers, etc.) it falls back to Polygon — the same key Paula's engine uses —
    so a flaky Yahoo can't stop the study."""
    from datetime import datetime, timedelta
    days = int(365 * years) + 320  # +warmup for SMA200 / 52w range
    out = {}

    # ── 1) yfinance bulk (fast when it works) ──
    try:
        import yfinance as yf
        end = datetime.now()
        start = end - timedelta(days=days)
        print(f"Downloading {len(universe)} tickers via yfinance, {years}y + warmup…")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            data = yf.download(universe, start=start.strftime("%Y-%m-%d"),
                               end=end.strftime("%Y-%m-%d"), group_by="ticker",
                               progress=False, threads=True, auto_adjust=True)
        for tk in universe:
            try:
                if tk in data.columns.get_level_values(0):
                    df = data[tk].dropna()
                    if len(df) > 260:
                        out[tk] = df
            except Exception:
                pass
        print(f"  yfinance: {len(out)}/{len(universe)} tickers")
    except Exception as e:
        print(f"  yfinance bulk failed ({str(e)[:80]}) — falling back to Polygon for all.")

    # ── 2) Polygon fallback for whatever's missing ──
    missing = [t for t in universe if t not in out]
    if missing:
        import time as _time
        print(f"  Polygon fallback for {len(missing)} ticker(s)…")
        print("  (Polygon free tier is 5 req/min — this throttles to stay under it;")
        print("   if you're on the free plan and this crawls, use a smaller --universe.)")
        got = 0
        for i, tk in enumerate(missing, 1):
            try:
                df = T._polygon_daily_hist(tk, days=days)
                if df is not None and len(df) > 260:
                    out[tk] = df
                    got += 1
            except Exception:
                pass
            if i % 5 == 0:
                print(f"    …{i}/{len(missing)} ({got} recovered)")
                _time.sleep(60)  # respect the 5-req/min free-tier limit
            else:
                _time.sleep(0.3)
        print(f"  Polygon recovered {got}/{len(missing)}")

    print(f"Usable history for {len(out)}/{len(universe)} tickers total")
    return out


def main():
    ap = argparse.ArgumentParser(description="Paula signal decile + factor study")
    ap.add_argument("--years", type=float, default=2.0)
    ap.add_argument("--horizon", type=int, default=5, help="forward return horizon in trading days")
    ap.add_argument("--sample", type=int, default=1, help="evaluate every Nth day (use 5 for non-overlapping 5d windows)")
    ap.add_argument("--universe", type=str, default=None, help="file with one ticker per line")
    ap.add_argument("--threshold", type=float, default=0.8, help="collinearity flag threshold")
    args = ap.parse_args()

    universe = DEFAULT_UNIVERSE
    if args.universe and os.path.exists(args.universe):
        universe = [ln.strip().upper() for ln in open(args.universe) if ln.strip()]

    hist = download(universe, args.years)
    if not hist:
        print("No data. Are you online / is Yahoo reachable?")
        return

    df = build_observations(hist, horizon=args.horizon, sample_every=args.sample)
    if df.empty:
        print("No observations produced.")
        return

    outdir = os.path.dirname(os.path.abspath(__file__))
    df.to_csv(os.path.join(outdir, "signal_observations.csv"), index=False)
    table = decile_study(df, args.horizon)
    table.to_csv(os.path.join(outdir, "signal_deciles.csv"), index=False)
    corr = factor_correlation(df, threshold=args.threshold)
    corr.to_csv(os.path.join(outdir, "factor_correlation.csv"))
    maybe_plot(table, corr, outdir)
    print(f"\nWrote signal_observations.csv ({len(df):,} rows), signal_deciles.csv, "
          f"factor_correlation.csv to {outdir}")


if __name__ == "__main__":
    main()
