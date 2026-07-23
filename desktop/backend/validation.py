"""
Paula — Strategy Validation
===========================

A backtest tells you what happened. This module tells you whether to BELIEVE it.

Three things quietly turn a losing strategy into a winning-looking backtest:

  1. FREE TRADING. Backtests fill at the exact close price. Reality charges you
     spread and slippage on every entry AND exit. A strategy with a small edge
     and lots of trades dies entirely on friction.

  2. LUCK MISTAKEN FOR EDGE. A 60% win rate over 20 trades is what a coin flip
     does regularly. Without a null hypothesis you cannot tell skill from noise.

  3. NO BENCHMARK. +8% looks great until you learn SPY did +12% over the same
     window with none of the work or risk.

So this module: applies real costs, tests the result against a null distribution
of RANDOM entries, bootstraps a confidence interval on the average trade, checks
the drawdown against reshuffled orderings, compares to buy-and-hold, and then
hands down a verdict — including "INCONCLUSIVE", which is the honest answer far
more often than people like.

IMPORTANT — what each test actually proves:

  * Reshuffling TRADE ORDER does NOT test edge. Total P&L is invariant under
    permutation (addition is commutative). It only tells you whether your
    observed max drawdown was lucky sequencing. Useful, but it is not a test of
    whether the strategy works, and anyone selling it as one is confused.

  * The RANDOM-ENTRY test is the one that can genuinely fail you. It asks: if I
    had entered the same names for the same holding periods on random dates,
    how often would I have beaten what the signal engine produced? If the answer
    is "often", the signals aren't adding anything.
"""

import random
import statistics
from datetime import datetime


# ── Cost model ───────────────────────────────────────────────────────────────
# Defaults are deliberately realistic-to-pessimistic for liquid US large caps on
# a commission-free broker (Alpaca). Friction is charged on BOTH sides.
#   slippage_bps : how far past the quote you actually fill (market impact +
#                  latency). 5bps each way is normal for liquid names; illiquid
#                  small caps are far worse.
#   half_spread_bps : you buy at the ask and sell at the bid, not at the mid.
#   commission   : per-trade dollar fee (0 on Alpaca; set it if you move brokers).
DEFAULT_COSTS = {
    "slippage_bps": 5.0,
    "half_spread_bps": 2.0,
    "commission": 0.0,
}


def _round_trip_cost_pct(costs: dict) -> float:
    """Total friction as a fraction of position value, charged over a full
    round trip (entry + exit)."""
    per_side = (costs.get("slippage_bps", 0) + costs.get("half_spread_bps", 0)) / 10000.0
    return per_side * 2


def apply_costs(trades: list, costs: dict = None) -> list:
    """Return a copy of `trades` with realistic frictions applied.

    Each trade gains:
      gross_pct : return before costs
      net_pct   : return after slippage, spread and commission
    """
    costs = {**DEFAULT_COSTS, **(costs or {})}
    rt = _round_trip_cost_pct(costs)
    out = []
    for t in trades:
        entry = t.get("entry")
        exit_ = t.get("exit")
        if not entry or not exit_ or entry <= 0:
            continue
        gross = (exit_ - entry) / entry
        # Commission is a fixed dollar amount, so express it as a fraction of the
        # position. Without qty we can't, so fall back to ignoring it (0 anyway
        # on a commission-free broker).
        qty = t.get("qty") or 0
        comm_pct = 0.0
        if qty and costs.get("commission"):
            notional = entry * qty
            if notional > 0:
                comm_pct = (costs["commission"] * 2) / notional
        net = gross - rt - comm_pct
        c = dict(t)
        c["gross_pct"] = gross
        c["net_pct"] = net
        out.append(c)
    return out


# ── Test 1: bootstrap confidence interval on the average trade ───────────────

def bootstrap_mean(returns: list, n_sims: int = 2000, seed: int = 42) -> dict:
    """Resample the trades WITH replacement to get a confidence interval on the
    mean return per trade.

    This answers: 'given this sample of trades, how precisely do I actually know
    the average?' If the 95% interval includes zero, you have not demonstrated a
    profitable strategy — regardless of what the headline total says.
    """
    if len(returns) < 2:
        return {"ok": False, "reason": "need at least 2 trades"}
    rng = random.Random(seed)
    n = len(returns)
    means = []
    for _ in range(n_sims):
        means.append(sum(rng.choice(returns) for _ in range(n)) / n)
    means.sort()
    lo = means[int(0.025 * n_sims)]
    hi = means[int(0.975 * n_sims)]
    observed = sum(returns) / n
    return {
        "ok": True,
        "mean_pct": observed * 100,
        "ci_low_pct": lo * 100,
        "ci_high_pct": hi * 100,
        # The interval straddling zero is the thing that matters.
        "includes_zero": lo <= 0 <= hi,
        "prob_positive": sum(1 for m in means if m > 0) / n_sims,
    }


# ── Test 2: the real one — random-entry null hypothesis ──────────────────────

def random_entry_null(trades: list, ticker_data: dict, n_sims: int = 1000,
                      costs: dict = None, seed: int = 42) -> dict:
    """Compare the strategy against entering the SAME tickers for the SAME
    holding periods, but on RANDOM dates.

    This is the test that can actually fail a strategy. It isolates the only
    thing the signal engine claims to provide: better timing. If random entry
    dates match or beat it, the signals contribute nothing and you're just
    getting paid for market exposure.

    Returns a p-value: the fraction of random runs that beat the strategy. Below
    0.05 means the result would be unlikely to arise from chance timing alone.
    """
    costs = {**DEFAULT_COSTS, **(costs or {})}
    rt = _round_trip_cost_pct(costs)

    # Build (ticker, holding_days) pairs from the real trades.
    specs = []
    for t in trades:
        tk = t.get("ticker")
        if tk not in ticker_data:
            continue
        hold = _holding_days(t)
        if hold and hold > 0:
            specs.append((tk, hold))
    if len(specs) < 5:
        return {"ok": False, "reason": "need at least 5 dated trades to test"}

    # Precompute closing-price series per ticker.
    closes = {}
    for tk, df in ticker_data.items():
        try:
            closes[tk] = [float(x) for x in df["Close"].tolist()]
        except Exception:
            pass

    rng = random.Random(seed)
    sim_totals = []
    for _ in range(n_sims):
        total = 0.0
        for tk, hold in specs:
            series = closes.get(tk)
            if not series or len(series) <= hold + 1:
                continue
            i = rng.randrange(0, len(series) - hold - 1)
            entry = series[i]
            exit_ = series[i + hold]
            if entry <= 0:
                continue
            total += (exit_ - entry) / entry - rt
        sim_totals.append(total)

    if not sim_totals:
        return {"ok": False, "reason": "insufficient price history"}

    observed = sum(t.get("net_pct", 0) for t in trades)
    beaten_by = sum(1 for s in sim_totals if s >= observed)
    p = beaten_by / len(sim_totals)
    sim_totals_sorted = sorted(sim_totals)
    return {
        "ok": True,
        "observed_total_pct": observed * 100,
        "random_mean_pct": (sum(sim_totals) / len(sim_totals)) * 100,
        "random_p95_pct": sim_totals_sorted[int(0.95 * len(sim_totals_sorted))] * 100,
        "p_value": p,
        "significant": p < 0.05,
        "n_sims": len(sim_totals),
    }


def _holding_days(trade: dict):
    """Trading-day-ish holding period from a trade's entry/exit dates."""
    try:
        a = datetime.strptime(str(trade.get("entry_date"))[:10], "%Y-%m-%d")
        b = datetime.strptime(str(trade.get("exit_date"))[:10], "%Y-%m-%d")
        cal = (b - a).days
        if cal <= 0:
            return 1
        # Rough calendar->trading day conversion (5/7), floored at 1.
        return max(1, int(cal * 5 / 7))
    except Exception:
        return None


# ── Test 3: was the drawdown lucky? (order permutation) ──────────────────────

def drawdown_permutation(returns: list, n_sims: int = 1000, seed: int = 42) -> dict:
    """Reshuffle the ORDER of the same trades and re-measure max drawdown.

    NOTE: this does not test edge — total return is identical in every shuffle.
    It tests sequencing luck. If your observed drawdown sits at the good end of
    the distribution, the real-world experience of running this strategy is
    likely to be WORSE than the backtest felt, even if the returns hold up.
    """
    if len(returns) < 5:
        return {"ok": False, "reason": "need at least 5 trades"}
    rng = random.Random(seed)

    def max_dd(seq):
        equity = 1.0
        peak = 1.0
        worst = 0.0
        for r in seq:
            equity *= (1 + r)
            peak = max(peak, equity)
            worst = max(worst, (peak - equity) / peak)
        return worst

    observed = max_dd(returns)
    sims = []
    pool = list(returns)
    for _ in range(n_sims):
        rng.shuffle(pool)
        sims.append(max_dd(pool))
    sims.sort()
    worse = sum(1 for s in sims if s > observed)
    return {
        "ok": True,
        "observed_dd_pct": observed * 100,
        "median_dd_pct": sims[len(sims) // 2] * 100,
        "p95_dd_pct": sims[int(0.95 * len(sims))] * 100,
        # How often a different ordering would have hurt more.
        "pct_orderings_worse": worse / len(sims) * 100,
    }


# ── Test 4: benchmark ────────────────────────────────────────────────────────

def benchmark_return(ticker_data: dict, symbol: str = "SPY") -> dict:
    """Buy-and-hold return over the same window, for comparison."""
    df = ticker_data.get(symbol)
    if df is None:
        return {"ok": False, "reason": f"no {symbol} data"}
    try:
        closes = [float(x) for x in df["Close"].tolist()]
        if len(closes) < 2 or closes[0] <= 0:
            return {"ok": False, "reason": "insufficient data"}
        return {"ok": True, "symbol": symbol,
                "return_pct": (closes[-1] - closes[0]) / closes[0] * 100}
    except Exception as e:
        return {"ok": False, "reason": str(e)}


# ── Verdict ──────────────────────────────────────────────────────────────────

# Below this many trades, no statistical test is worth trusting. Stated loudly
# because Paula's live config (2 positions, score >= 75) produces FEW trades, and
# a 70% win rate over 12 trades means nothing at all.
MIN_TRADES_FOR_CONFIDENCE = 30


def validate(trades: list, ticker_data: dict = None, costs: dict = None,
             n_sims: int = 1000, benchmark: str = "SPY") -> dict:
    """Run the full validation suite over a backtest's completed trades.

    Returns every sub-test plus an overall PASS / FAIL / INCONCLUSIVE verdict
    and a plain-English explanation of what drove it.
    """
    ticker_data = ticker_data or {}
    priced = apply_costs(trades, costs)
    if not priced:
        return {"ok": False, "error": "No completed trades to validate."}

    net = [t["net_pct"] for t in priced]
    gross = [t["gross_pct"] for t in priced]
    n = len(net)

    total_net = sum(net) * 100
    total_gross = sum(gross) * 100
    wins = sum(1 for r in net if r > 0)

    boot = bootstrap_mean(net, n_sims=max(n_sims, 1000))
    null = random_entry_null(priced, ticker_data, n_sims=n_sims, costs=costs) if ticker_data else {"ok": False, "reason": "no price data supplied"}
    dd = drawdown_permutation(net, n_sims=n_sims)
    bench = benchmark_return(ticker_data, benchmark) if ticker_data else {"ok": False}

    # ── Decide ──
    reasons = []
    verdict = "PASS"

    if n < MIN_TRADES_FOR_CONFIDENCE:
        verdict = "INCONCLUSIVE"
        reasons.append(
            f"Only {n} completed trades — below the {MIN_TRADES_FOR_CONFIDENCE} needed "
            f"before any of these numbers mean much. Widen the window or loosen filters "
            f"to build a bigger sample."
        )

    if total_net <= 0:
        verdict = "FAIL"
        reasons.append(f"Loses money after costs ({total_net:+.2f}%).")
    elif total_gross > 0 and total_net <= 0:
        verdict = "FAIL"
        reasons.append("Profitable before costs, unprofitable after — the edge is smaller than the friction.")

    if boot.get("ok") and boot.get("includes_zero") and verdict != "FAIL":
        verdict = "FAIL" if n >= MIN_TRADES_FOR_CONFIDENCE else "INCONCLUSIVE"
        reasons.append(
            f"The 95% confidence interval on the average trade "
            f"({boot['ci_low_pct']:+.2f}% to {boot['ci_high_pct']:+.2f}%) includes zero — "
            f"no demonstrated edge."
        )

    if null.get("ok"):
        if not null.get("significant") and verdict != "FAIL":
            verdict = "FAIL" if n >= MIN_TRADES_FOR_CONFIDENCE else "INCONCLUSIVE"
            reasons.append(
                f"Random entry dates matched or beat this result {null['p_value']*100:.1f}% "
                f"of the time (p={null['p_value']:.3f}). The signal timing isn't adding value."
            )
        elif null.get("significant"):
            reasons.append(
                f"Beat random-entry timing (p={null['p_value']:.3f}) — the signals are "
                f"contributing something beyond market exposure."
            )

    if bench.get("ok"):
        if total_net < bench["return_pct"]:
            reasons.append(
                f"Underperformed buy-and-hold {bench['symbol']} "
                f"({total_net:+.2f}% vs {bench['return_pct']:+.2f}%) — same period, "
                f"far less risk and effort."
            )
            if verdict == "PASS":
                verdict = "INCONCLUSIVE"
        else:
            reasons.append(
                f"Beat buy-and-hold {bench['symbol']} "
                f"({total_net:+.2f}% vs {bench['return_pct']:+.2f}%)."
            )

    if dd.get("ok") and dd.get("pct_orderings_worse", 0) > 80:
        reasons.append(
            f"Drawdown was fortunate: {dd['pct_orderings_worse']:.0f}% of other trade "
            f"orderings would have drawn down harder (observed {dd['observed_dd_pct']:.1f}%, "
            f"95th pct {dd['p95_dd_pct']:.1f}%). Expect worse live."
        )

    return {
        "ok": True,
        "verdict": verdict,
        "reasons": reasons,
        "summary": {
            "trades": n,
            "win_rate": round(wins / n * 100, 1),
            "total_gross_pct": round(total_gross, 2),
            "total_net_pct": round(total_net, 2),
            "cost_drag_pct": round(total_gross - total_net, 2),
            "avg_trade_net_pct": round(sum(net) / n * 100, 3),
        },
        "bootstrap": boot,
        "random_entry_test": null,
        "drawdown_test": dd,
        "benchmark": bench,
        "costs_applied": {**DEFAULT_COSTS, **(costs or {})},
    }
