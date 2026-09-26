"""
Intraday backtest lab — replays day-trading strategies on real 1-minute SIP bars.

Strategies come from published research with fixed, pre-registered rules so the
test is honest rather than curve-fit:

  orb      Opening Range Breakout on "Stocks in Play" — Zarattini, Barbon & Aziz
           (2024), "A Profitable Day Trading Strategy for the U.S. Equity Market",
           SSRN 4729284. Tested 2016–2023 in the paper.
  noise    Intraday momentum on SPY/QQQ with a "noise area" and VWAP trailing stop —
           Zarattini, Aziz & Barbon (2024), "Beat the Market", SSRN 4824172.
           Tested 2007–early 2024 in the paper.
  lasthalf Market intraday momentum — Gao, Han, Li & Zhou (2018, JFE): the first
           half-hour return predicts the last half-hour.

Everything after a paper's sample ends is genuinely out-of-sample, and every
report splits it out: that number, not the headline, is the one to trust.

Fill model (deliberately pessimistic):
  • stop-entries fill at the trigger or the bar's open if it gapped through
  • if a bar touches both the entry and the protective stop, it's a loss
  • stops fill at the stop or the bar's open if it gapped through
  • commission $0.0035/share + slippage per share on every fill
"""
from __future__ import annotations

import bisect
import math
import statistics
from dataclasses import dataclass, field, asdict
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import intraday_data as data

ET = ZoneInfo("America/New_York")

COMMISSION = 0.0035   # $/share, Interactive Brokers-style; Alpaca is $0 but slippage isn't


@dataclass
class Trade:
    day: str
    symbol: str
    side: str            # "long" | "short"
    entry: float
    exit: float
    qty: int
    entry_time: str
    exit_time: str
    reason: str
    pnl: float
    r: float             # P&L in units of initial risk (0 when there's no fixed stop)


@dataclass
class Result:
    strategy: str
    params: dict
    start: str
    end: str
    equity: list = field(default_factory=list)   # [(day, equity)]
    trades: list = field(default_factory=list)

    def summary(self, oos_from: str | None = None) -> dict:
        out = {"strategy": self.strategy, "params": self.params, "start": self.start,
               "end": self.end, **_stats(self.equity, self.trades)}
        years = {}
        for d, _ in self.equity:
            years.setdefault(d[:4], None)
        out["by_year"] = {y: _stats([e for e in self.equity if e[0][:4] == y],
                                    [t for t in self.trades if t.day[:4] == y], brief=True)
                          for y in years}
        if oos_from:
            out["out_of_sample"] = {"from": oos_from, **_stats(
                [e for e in self.equity if e[0] >= oos_from],
                [t for t in self.trades if t.day >= oos_from])}
        return out


def _stats(equity, trades, brief=False) -> dict:
    if len(equity) < 2:
        return {"days": len(equity), "trades": len(trades)}
    vals = [e for _, e in equity]
    rets = [vals[i] / vals[i - 1] - 1 for i in range(1, len(vals))]
    total = vals[-1] / vals[0] - 1
    yrs = len(rets) / 252
    cagr = (vals[-1] / vals[0]) ** (1 / yrs) - 1 if yrs > 0 and vals[-1] > 0 else -1
    sd = statistics.pstdev(rets) if len(rets) > 1 else 0
    sharpe = statistics.mean(rets) / sd * math.sqrt(252) if sd else 0
    peak, mdd = vals[0], 0.0
    for v in vals:
        peak = max(peak, v)
        mdd = min(mdd, v / peak - 1)
    wins = [t.pnl for t in trades if t.pnl > 0]
    losses = [t.pnl for t in trades if t.pnl <= 0]
    out = {
        "days": len(rets), "trades": len(trades),
        "total_return_pct": round(total * 100, 2),
        "cagr_pct": round(cagr * 100, 2),
        "sharpe": round(sharpe, 2),
        "max_drawdown_pct": round(mdd * 100, 2),
        "win_rate_pct": round(len(wins) / len(trades) * 100, 1) if trades else None,
    }
    if brief:
        return out
    gross_loss = -sum(losses)
    out.update({
        "profit_factor": round(sum(wins) / gross_loss, 2) if gross_loss else None,
        "avg_win": round(statistics.mean(wins), 2) if wins else 0,
        "avg_loss": round(statistics.mean(losses), 2) if losses else 0,
        "avg_r": round(statistics.mean(t.r for t in trades), 3) if trades else None,
        "pct_days_green": round(sum(r > 0 for r in rets) / len(rets) * 100, 1),
        "worst_day_pct": round(min(rets) * 100, 2),
        "best_day_pct": round(max(rets) * 100, 2),
    })
    return out


def _hm(ts: int) -> tuple[int, int]:
    t = datetime.fromtimestamp(ts, ET)
    return t.hour, t.minute


def _clock(ts: int) -> str:
    return datetime.fromtimestamp(ts, ET).strftime("%H:%M")


# ═══════════════════════════════════════════════════════════════════════════
#  Single-position replay with a stop-entry, protective stop and EOD exit
# ═══════════════════════════════════════════════════════════════════════════

def replay_breakout(bars, side: str, trigger: float, stop_dist: float, qty: int,
                    start_idx: int, slip: float, target_r: float | None = None,
                    exit_hm=(15, 59)):
    """Walk minute bars from start_idx: fill a stop-entry at `trigger`, then
    exit at the protective stop, an optional R-multiple target, or the close.
    Returns (entry, exit, entry_ts, exit_ts, reason) or None if never filled."""
    long = side == "long"
    entry = entry_ts = None
    stop = target = None
    for i in range(start_idx, len(bars)):
        ts, o, h, l, c = bars[i][:5]
        if _hm(ts) >= exit_hm:
            if entry is None:
                return None
            px = o - slip if long else o + slip
            return entry, px, entry_ts, ts, "close"
        if entry is None:
            hit = h >= trigger if long else l <= trigger
            if not hit:
                continue
            fill = max(trigger, o) if long else min(trigger, o)
            entry = fill + slip if long else fill - slip
            entry_ts = ts
            stop = fill - stop_dist if long else fill + stop_dist
            target = (fill + target_r * stop_dist if long else fill - target_r * stop_dist) if target_r else None
            # Same-bar stop touch: assume the worst.
            if (l <= stop) if long else (h >= stop):
                px = stop - slip if long else stop + slip
                return entry, px, entry_ts, ts, "stop"
            continue
        if (l <= stop) if long else (h >= stop):
            fill = min(stop, o) if long else max(stop, o)
            return entry, fill - slip if long else fill + slip, entry_ts, ts, "stop"
        if target is not None and ((h >= target) if long else (l <= target)):
            fill = max(target, o) if long else min(target, o)
            return entry, fill - slip if long else fill + slip, entry_ts, ts, "target"
    if entry is None:
        return None
    last = bars[-1]
    return entry, last[4] - slip if long else last[4] + slip, entry_ts, last[0], "close"


# ═══════════════════════════════════════════════════════════════════════════
#  Strategy 1 — Opening Range Breakout on Stocks in Play
# ═══════════════════════════════════════════════════════════════════════════

ORB_DEFAULTS = {
    "or_minutes": 5,          # opening range length
    "top_n": 20,              # stocks in play traded per day
    "min_rvol": 1.0,          # opening volume vs its 14-day average (paper: >100%)
    "min_price": 5.0,
    "min_avg_volume": 1_000_000,
    "min_atr": 0.50,          # dollars, 14-day
    "stop_atr_frac": 0.10,    # stop distance = 10% of ATR
    "risk_pct": 0.01,         # equity risked per trade
    "max_leverage": 4.0,
    "target_r": None,         # None = hold to the close, as in the paper
    "sides": "both",          # "both" | "long"
    "slippage": 0.01,         # $/share per fill
    "lookback": 14,
}


def _atr(rows, n=14):
    trs = []
    for i in range(1, len(rows)):
        h, l, pc = rows[i][2], rows[i][3], rows[i - 1][4]
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    return sum(trs[-n:]) / min(len(trs), n) if trs else None


def orb_candidates(day: date, daily: dict, p: dict) -> dict:
    """Symbols that pass the pre-open filters using only data before `day`."""
    cutoff = datetime.combine(day, datetime.min.time(), ET).timestamp()
    out = {}
    for sym, rows in daily.items():
        past = rows[max(0, bisect.bisect_left(rows, [cutoff]) - 40):bisect.bisect_left(rows, [cutoff])]
        if len(past) < p["lookback"] + 1:
            continue
        prev_close = past[-1][4]
        if prev_close < p["min_price"]:
            continue
        avg_vol = sum(r[5] for r in past[-p["lookback"]:]) / p["lookback"]
        if avg_vol < p["min_avg_volume"]:
            continue
        atr = _atr(past[-(p["lookback"] + 1):], p["lookback"])
        if not atr or atr < p["min_atr"]:
            continue
        out[sym] = {"atr": atr, "prev_close": prev_close}
    return out


def run_orb(start: date, end: date, params: dict | None = None, equity0: float = 25_000,
            progress=None) -> Result:
    p = {**ORB_DEFAULTS, **(params or {})}
    days = data.trading_days(start - timedelta(days=40), end)
    test_days = [d for d in days if d >= start]
    daily = data.daily_bars(start - timedelta(days=70), end)
    res = Result("orb", p, start.isoformat(), end.isoformat())
    equity = equity0
    res.equity.append(((test_days[0] - timedelta(days=1)).isoformat(), equity))
    for k, day in enumerate(test_days):
        cands = orb_candidates(day, daily, p)
        syms = sorted(cands)
        idx = days.index(day)
        today = data.opening_bars(day, syms, p["or_minutes"])
        hist = [data.opening_bars(d, syms, p["or_minutes"]) for d in days[max(0, idx - p["lookback"]):idx]]
        ranked = []
        for s, bar in today.items():
            vols = [h[s][5] for h in hist if h.get(s)]
            if len(vols) < p["lookback"] // 2:
                continue
            base = sum(vols) / len(vols)
            rvol = bar[5] / base if base else 0
            if rvol < p["min_rvol"]:
                continue
            o, c = bar[1], bar[4]
            if c == o or (p["sides"] == "long" and c < o):
                continue
            ranked.append((rvol, s, bar))
        ranked.sort(reverse=True)
        picks = ranked[:p["top_n"]]
        day_pnl = 0.0
        if picks:
            mins = data.minute_bars(day, [s for _, s, _ in picks])
            for rvol, s, bar in picks:
                bars = mins.get(s) or []
                side = "long" if bar[4] > bar[1] else "short"
                trigger = bar[2] if side == "long" else bar[3]
                stop_dist = max(p["stop_atr_frac"] * cands[s]["atr"], 0.01)
                qty = int(min(equity * p["risk_pct"] / stop_dist,
                              equity * p["max_leverage"] / p["top_n"] / trigger))
                if qty <= 0:
                    continue
                after_or = divmod(9 * 60 + 30 + p["or_minutes"], 60)
                first = next((i for i, b in enumerate(bars) if _hm(b[0]) >= after_or), None)
                if first is None:
                    continue
                r = replay_breakout(bars, side, trigger, stop_dist, qty, first,
                                    p["slippage"], p["target_r"])
                if not r:
                    continue
                en, ex, ets, xts, why = r
                gross = (ex - en) * qty if side == "long" else (en - ex) * qty
                pnl = gross - 2 * COMMISSION * qty
                day_pnl += pnl
                res.trades.append(Trade(day.isoformat(), s, side, round(en, 4), round(ex, 4), qty,
                                        _clock(ets), _clock(xts), why, round(pnl, 2),
                                        round(pnl / (stop_dist * qty), 3)))
        equity += day_pnl
        res.equity.append((day.isoformat(), round(equity, 2)))
        if progress and k % 5 == 0:
            progress(k + 1, len(test_days), day.isoformat(), equity)
        if equity <= 0:
            break
    return res


# ═══════════════════════════════════════════════════════════════════════════
#  Strategy 2 — Noise-area intraday momentum (SPY / QQQ)
# ═══════════════════════════════════════════════════════════════════════════

# Defaults are what the live "momentum" mode trades. The paper used SPY at up
# to 4x; on SPY that held up poorly after publication (Sharpe 0.47 since
# 2024-05) while QQQ at 2x held Sharpe 1.3 — see docs/day-trading-research.md.
NOISE_DEFAULTS = {
    "symbol": "QQQ",
    "lookback": 14,           # days for the noise band and the vol target
    "band_mult": 1.0,
    "target_vol": 0.02,       # daily vol target for sizing
    "max_leverage": 2.0,
    "check_every": 30,        # minutes; decisions only at HH:00 / HH:30
    "sides": "both",
    "slippage": 0.001,        # $/share, as in the paper
    "vwap_stop": True,
}


def run_noise(start: date, end: date, params: dict | None = None, equity0: float = 25_000,
              progress=None) -> Result:
    p = {**NOISE_DEFAULTS, **(params or {})}
    sym = p["symbol"]
    series = data.minute_range(sym, start - timedelta(days=40), end)
    days = sorted(series)
    res = Result("noise", p, start.isoformat(), end.isoformat())
    equity = equity0
    moves: list[dict] = []        # per day: {minute_index: |close/open - 1|}
    closes: list[float] = []
    started = False
    for di, day in enumerate(days):
        bars = series[day]
        if len(bars) < 300:       # half-days: skip, but keep the history going
            moves.append({})
            closes.append(bars[-1][4] if bars else (closes[-1] if closes else 0))
            continue
        o = bars[0][1]
        mv = {}
        for b in bars:
            h, m = _hm(b[0])
            mv[(h - 9) * 60 + m - 30] = abs(b[4] / o - 1)
        if day >= start and len(moves) >= p["lookback"] and closes:
            if not started:
                res.equity.append(((day - timedelta(days=1)).isoformat(), equity))
                started = True
            prev_close = closes[-1]
            hist = moves[-p["lookback"]:]
            dr = [closes[i] / closes[i - 1] - 1 for i in range(len(closes) - p["lookback"], len(closes)) if i > 0]
            dvol = statistics.pstdev(dr) if len(dr) > 2 else 0.01
            lev = min(p["max_leverage"], p["target_vol"] / dvol) if dvol else 1
            qty = int(equity * lev / o)
            upper_base, lower_base = max(o, prev_close), min(o, prev_close)
            pos = 0            # +1 long, -1 short
            entry = 0.0
            day_pnl = 0.0
            pv = vv = 0.0
            for b in bars:
                ts, bo, bh, bl, bc, bv = b[:6]
                pv += b[6] * bv
                vv += bv
                vwap = pv / vv if vv else bc
                h, m = _hm(ts)
                mi = (h - 9) * 60 + m - 30
                closing = (h, m) >= (15, 59)
                if closing:
                    if pos:
                        px = bo - pos * p["slippage"]
                        pnl = pos * (px - entry) * qty - COMMISSION * qty
                        day_pnl += pnl
                        res.trades[-1].exit, res.trades[-1].exit_time = round(px, 4), _clock(ts)
                        res.trades[-1].reason = "close"
                        res.trades[-1].pnl = round(res.trades[-1].pnl + pnl, 2)
                        pos = 0
                    break
                # decisions on the bar that CLOSES at HH:00/HH:30 (index mi is the bar start)
                if (mi + 1) % p["check_every"] != 0 or mi + 1 < 30:
                    continue
                sig = [d.get(mi) for d in hist if d.get(mi) is not None]
                if len(sig) < p["lookback"] // 2:
                    continue
                sigma = sum(sig) / len(sig) * p["band_mult"]
                ub, lb = upper_base * (1 + sigma), lower_base * (1 - sigma)
                # exits first (trailing stop = tighter of band and VWAP)
                if pos == 1:
                    stop = max(ub, vwap) if p["vwap_stop"] else ub
                    if bc < stop:
                        px = bc - p["slippage"]
                        pnl = (px - entry) * qty - COMMISSION * qty
                        day_pnl += pnl
                        t = res.trades[-1]
                        t.exit, t.exit_time, t.reason, t.pnl = round(px, 4), _clock(ts), "trail", round(t.pnl + pnl, 2)
                        pos = 0
                elif pos == -1:
                    stop = min(lb, vwap) if p["vwap_stop"] else lb
                    if bc > stop:
                        px = bc + p["slippage"]
                        pnl = (entry - px) * qty - COMMISSION * qty
                        day_pnl += pnl
                        t = res.trades[-1]
                        t.exit, t.exit_time, t.reason, t.pnl = round(px, 4), _clock(ts), "trail", round(t.pnl + pnl, 2)
                        pos = 0
                if pos == 0 and qty > 0:
                    if bc > ub:
                        pos, entry = 1, bc + p["slippage"]
                    elif bc < lb and p["sides"] == "both":
                        pos, entry = -1, bc - p["slippage"]
                    if pos:
                        res.trades.append(Trade(day.isoformat(), sym, "long" if pos == 1 else "short",
                                                round(entry, 4), 0.0, qty, _clock(ts + 60), "", "",
                                                round(-COMMISSION * qty, 2), 0.0))
            equity += day_pnl
            res.equity.append((day.isoformat(), round(equity, 2)))
            if progress and di % 50 == 0:
                progress(di, len(days), day.isoformat(), equity)
        moves.append(mv)
        closes.append(bars[-1][4])
    # Winners/losers need exits filled in; drop any orphan (shouldn't happen).
    res.trades = [t for t in res.trades if t.exit]
    return res


# ═══════════════════════════════════════════════════════════════════════════
#  Strategy 3 — Last-half-hour market momentum (Gao, Han, Li & Zhou)
# ═══════════════════════════════════════════════════════════════════════════

LASTHALF_DEFAULTS = {"symbol": "SPY", "leverage": 1.0, "slippage": 0.001, "sides": "both"}


def run_lasthalf(start: date, end: date, params: dict | None = None, equity0: float = 25_000,
                 progress=None) -> Result:
    p = {**LASTHALF_DEFAULTS, **(params or {})}
    series = data.minute_range(p["symbol"], start - timedelta(days=7), end)
    days = sorted(series)
    res = Result("lasthalf", p, start.isoformat(), end.isoformat())
    equity, prev_close = equity0, None
    for day in days:
        bars = series[day]
        if prev_close is None or day < start or len(bars) < 300:
            prev_close = bars[-1][4] if bars else prev_close
            continue
        if not res.equity:
            res.equity.append(((day - timedelta(days=1)).isoformat(), equity))
        by = {_hm(b[0]): b for b in bars}
        b10, b1530, b1559 = by.get((9, 59)), by.get((15, 29)), by.get((15, 59))
        if b10 and b1530 and b1559:
            first = b10[4] / prev_close - 1
            side = 1 if first > 0 else -1
            if side == 1 or p["sides"] == "both":
                qty = int(equity * p["leverage"] / b1530[4])
                en = b1530[4] + side * p["slippage"]
                ex = b1559[4] - side * p["slippage"]
                pnl = side * (ex - en) * qty - 2 * COMMISSION * qty
                equity += pnl
                res.trades.append(Trade(day.isoformat(), p["symbol"], "long" if side == 1 else "short",
                                        round(en, 4), round(ex, 4), qty, "15:30", "16:00", "close",
                                        round(pnl, 2), 0.0))
        res.equity.append((day.isoformat(), round(equity, 2)))
        prev_close = bars[-1][4]
    return res


# ═══════════════════════════════════════════════════════════════════════════
#  Strategy 4 — Paula's own small-cap pullback modes (strict / intense)
# ═══════════════════════════════════════════════════════════════════════════
#
# Replays smallcap_pullback.detect_setups() — the live code, not a copy — on
# historical minute bars every 5 minutes. What history can't supply is left out
# and said so in the report: float, market cap, catalyst grade, SEC-filing
# hazards, halts and premarket high. The intense mode's add-on ladder isn't
# modeled; its first tranche is sized as the full position.

SMALLCAP_DEFAULTS = {"mode": "strict", "max_candidates": 12, "slippage_pct": 0.0015,
                     "min_avg_volume": 300_000}


def _to_dt_bars(rows):
    return [(datetime.fromtimestamp(r[0], ET), r[1], r[2], r[3], r[4], r[5]) for r in rows]


def _five(rows):
    out = []
    for r in rows:
        t = r[0].replace(minute=r[0].minute - r[0].minute % 5, second=0)
        if out and out[-1][0] == t:
            o = out[-1]
            out[-1] = (t, o[1], max(o[2], r[2]), min(o[3], r[3]), r[4], o[5] + r[5])
        else:
            out.append((t, r[1], r[2], r[3], r[4], r[5]))
    return out


def smallcap_candidates(day, days, daily, mode, p):
    cutoff = datetime.combine(day, datetime.min.time(), ET).timestamp()
    pre = {}
    for sym, rows in daily.items():
        past = rows[max(0, bisect.bisect_left(rows, [cutoff]) - 21):bisect.bisect_left(rows, [cutoff])]
        if len(past) < 15:
            continue
        pc = past[-1][4]
        if not (mode["PRICE_MIN"] * 0.8 <= pc <= mode["PRICE_MAX"]):
            continue
        if sum(r[5] for r in past[-14:]) / 14 < p["min_avg_volume"]:
            continue
        pre[sym] = {"prev": past[-1]}
    syms = sorted(pre)
    idx = days.index(day)
    today = data.opening_bars(day, syms, 5)
    hist = [data.opening_bars(d, syms, 5) for d in days[max(0, idx - 14):idx]]
    ranked = []
    for s, bar in today.items():
        pc = pre[s]["prev"][4]
        chg = (bar[4] / pc - 1) * 100
        if chg < mode["MIN_DAY_CHANGE"] or not (mode["PRICE_MIN"] <= bar[4] <= mode["PRICE_MAX"]):
            continue
        vols = [h[s][5] for h in hist if h.get(s)]
        base = sum(vols) / len(vols) if vols else 0
        if not base or bar[5] / base < mode["RVOL_MIN"]:
            continue
        ranked.append((chg, s))
    ranked.sort(reverse=True)
    return [(s, pre[s]["prev"]) for _, s in ranked[:p["max_candidates"]]]


def run_smallcap(start: date, end: date, params: dict | None = None, equity0: float = 25_000,
                 progress=None) -> Result:
    import smallcap_pullback as sp
    p = {**SMALLCAP_DEFAULTS, **(params or {})}
    mode = dict(sp.get_mode(p["mode"]))
    mode.update({k: v for k, v in (params or {}).items() if k in mode})
    days = data.trading_days(start - timedelta(days=40), end)
    test_days = [d for d in days if d >= start]
    daily = data.daily_bars(start - timedelta(days=60), end)
    res = Result("smallcap", {**p, "mode_params": {k: v for k, v in mode.items() if isinstance(v, (int, float, str))}},
                 start.isoformat(), end.isoformat())
    equity = equity0
    res.equity.append(((test_days[0] - timedelta(days=1)).isoformat(), equity))
    windows = mode["ENTRY_WINDOWS"]
    flat_at = tuple(map(int, mode["FLATTEN_AT"].split(":")))
    for k, day in enumerate(test_days):
        cands = smallcap_candidates(day, days, daily, mode, p)
        mins = data.minute_bars(day, [s for s, _ in cands]) if cands else {}
        bars = {s: _to_dt_bars(mins.get(s) or []) for s, _ in cands}
        prev = dict(cands)
        open_pos: dict[str, dict] = {}
        attempts: dict[str, int] = {}
        day_pnl = 0.0
        stopped_day = False
        clock = datetime(day.year, day.month, day.day, 9, 35, tzinfo=ET)
        close_t = datetime(day.year, day.month, day.day, 16, 0, tzinfo=ET)
        while clock < close_t:
            hm = (clock.hour, clock.minute)
            # manage open positions minute by minute up to `clock`
            for s in list(open_pos):
                pos = open_pos[s]
                for b in bars[s]:
                    if b[0] < pos["cursor"] or b[0] >= clock:
                        continue
                    pos["cursor"] = b[0] + timedelta(minutes=1)
                    t, o, h, l, c, v = b
                    slip = c * p["slippage_pct"]
                    risk = pos["entry"] - pos["stop0"]

                    def _exit(px, qty, why):
                        nonlocal day_pnl
                        pnl = (px - pos["entry"]) * qty - COMMISSION * qty
                        pos["pnl"] += pnl
                        pos["qty"] -= qty
                        day_pnl += pnl
                        pos["reason"] = why
                        pos["exit_px"] = px
                        pos["exit_t"] = t
                    if l <= pos["stop"]:
                        _exit(min(pos["stop"], o) - slip, pos["qty"], "stop")
                    else:
                        if not pos["s1"] and h >= pos["entry"] + mode["SCALE1_R"] * risk:
                            q = int(pos["qty0"] * mode["SCALE1_FRAC"])
                            _exit(pos["entry"] + mode["SCALE1_R"] * risk - slip, q, "scale1")
                            pos["s1"] = True
                            if mode.get("BREAKEVEN_AFTER_SCALE1"):
                                pos["stop"] = max(pos["stop"], pos["entry"])
                        if pos["s1"] and not pos["s2"] and h >= pos["entry"] + mode["SCALE2_R"] * risk:
                            q = int(pos["qty0"] * mode["SCALE2_FRAC"])
                            _exit(pos["entry"] + mode["SCALE2_R"] * risk - slip, q, "scale2")
                            pos["s2"] = True
                        mins_in = (t - pos["t0"]).total_seconds() / 60
                        open_r = (c - pos["entry"]) / risk if risk else 0
                        if pos["qty"] > 0 and mins_in >= mode["TIME_STOP_MIN"] and not pos["s1"] \
                                and abs(open_r) < mode["TIME_STOP_MAX_R"]:
                            _exit(c - slip, pos["qty"], "time stop")
                        if pos["qty"] > 0 and (t.hour, t.minute) >= flat_at:
                            _exit(c - slip, pos["qty"], "flatten")
                    if pos["qty"] <= 0:
                        break
                # 5-minute trailing checks for the runner (9EMA close, VWAP floor)
                if pos["qty"] > 0 and pos["s1"]:
                    sess = [b for b in bars[s] if b[0] < clock]
                    b5 = _five(sess)
                    e9 = sp._ema([x[4] for x in b5], 9)
                    vw = sp._vwap(sess)
                    last = b5[-1][4] if b5 else None
                    if last and ((e9 and last < e9) or (vw and last < vw)):
                        pos["cursor"] = clock
                        t = clock
                        pnl = (last * (1 - p["slippage_pct"]) - pos["entry"]) * pos["qty"] - COMMISSION * pos["qty"]
                        pos["pnl"] += pnl
                        day_pnl += pnl
                        pos.update(qty=0, reason="trail", exit_px=last, exit_t=t)
                if pos["qty"] <= 0:
                    res.trades.append(Trade(day.isoformat(), s, "long", round(pos["entry"], 4),
                                            round(pos["exit_px"], 4), pos["qty0"], pos["t0"].strftime("%H:%M"),
                                            pos["exit_t"].strftime("%H:%M"), pos["reason"], round(pos["pnl"], 2),
                                            round(pos["pnl"] / (pos["risk0"] * pos["qty0"]), 3) if pos["risk0"] else 0))
                    del open_pos[s]
            if day_pnl <= -mode["DAILY_LOSS_LIMIT"] * equity:
                stopped_day = True
            in_window = any(tuple(map(int, a.split(":"))) <= hm < tuple(map(int, b.split(":"))) for a, b in windows)
            if in_window and not stopped_day and len(open_pos) < mode["MAX_POSITIONS"]:
                for s, pday in cands:
                    if s in open_pos or attempts.get(s, 0) >= sp.MAX_ATTEMPTS_PER_TICKER:
                        continue
                    sess = [b for b in bars[s] if b[0] < clock]
                    if len(sess) < 10:
                        continue
                    b5 = _five(sess)
                    if len(b5) < 6:
                        continue
                    closes5 = [b[4] for b in b5]
                    or_b = [b for b in sess if (b[0].hour, b[0].minute) < (9, 45)]
                    ctx = {"ticker": s, "price": sess[-1][4], "bars1": sess, "bars5": b5,
                           "vwap": sp._vwap(sess), "ema9": sp._ema(closes5, 9), "ema20": sp._ema(closes5, 20),
                           "ema9_series": sp._ema_series(closes5, 9), "ema20_series": sp._ema_series(closes5, 20),
                           "atr5": sp._atr(b5, 14), "pdh": pday[2], "pdl": pday[3], "prev_close": pday[4],
                           "pmh": None, "orh": max((b[2] for b in or_b), default=None),
                           "orl": min((b[3] for b in or_b), default=None),
                           "hod": max(b[2] for b in sess), "hvn": max(b5, key=lambda b: b[5])[4], "now": clock}
                    if ctx["ema9_series"] and len(ctx["ema9_series"]) < 4:
                        continue
                    try:
                        setups = sp.detect_setups(ctx, mode)
                    except Exception:
                        continue
                    if not setups:
                        continue
                    st = setups[0]
                    nxt = next((b for b in bars[s] if b[0] >= clock), None)
                    if not nxt:
                        continue
                    entry = nxt[1] * (1 + p["slippage_pct"])
                    stop = sp.atr_stop(entry, ctx, mode, st["stop"])
                    if stop >= entry or (entry - stop) / entry > mode["MAX_STOP_PCT"]:
                        continue
                    risk = entry - stop
                    qty = int(min(equity * mode["R_PCT"] / risk, equity * mode["CATASTROPHE_CAP_PCT"] / entry))
                    if qty <= 0:
                        continue
                    attempts[s] = attempts.get(s, 0) + 1
                    open_pos[s] = {"entry": entry, "stop": stop, "stop0": stop, "risk0": risk, "qty": qty,
                                   "qty0": qty, "t0": nxt[0], "cursor": nxt[0], "s1": False, "s2": False,
                                   "pnl": -COMMISSION * qty, "setup": st["setup"]}
                    day_pnl -= COMMISSION * qty
                    if len(open_pos) >= mode["MAX_POSITIONS"]:
                        break
            clock += timedelta(minutes=5)
        equity += day_pnl
        res.equity.append((day.isoformat(), round(equity, 2)))
        if progress and k % 5 == 0:
            progress(k + 1, len(test_days), day.isoformat(), equity)
    return res


# Where each paper's own sample ends: everything after is out-of-sample.
PUBLISHED_THROUGH = {"orb": "2024-01-01", "noise": "2024-05-01", "lasthalf": "2014-01-01", "smallcap": None}
RUNNERS = {"orb": run_orb, "noise": run_noise, "lasthalf": run_lasthalf, "smallcap": run_smallcap}
DEFAULTS = {"orb": ORB_DEFAULTS, "noise": NOISE_DEFAULTS, "lasthalf": LASTHALF_DEFAULTS,
            "smallcap": SMALLCAP_DEFAULTS}


# What the Backtest Lab shows and lets you change, per strategy.
CATALOG = {
    "noise": {
        "label": "Index momentum",
        "source": "Zarattini, Aziz & Barbon (2024) — Beat the Market, SSRN 4824172",
        "summary": "Buy SPY/QQQ when it breaks above its normal intraday range, short when it breaks below. "
                   "Checked every half hour; exits on VWAP or back inside the range; flat by the close.",
        "live_mode": "momentum",
        "params": [
            {"key": "symbol", "label": "Symbol", "type": "choice", "options": ["QQQ", "SPY"]},
            {"key": "sides", "label": "Direction", "type": "choice", "options": ["both", "long"]},
            {"key": "max_leverage", "label": "Max leverage", "type": "number", "min": 0.5, "max": 4, "step": 0.5},
            {"key": "target_vol", "label": "Daily vol target", "type": "percent", "min": 0.005, "max": 0.04, "step": 0.005},
            {"key": "band_mult", "label": "Range width ×", "type": "number", "min": 0.5, "max": 2, "step": 0.25},
            {"key": "lookback", "label": "Lookback days", "type": "int", "min": 5, "max": 30, "step": 1},
            {"key": "vwap_stop", "label": "VWAP trailing stop", "type": "bool"},
        ],
        "earliest": "2016-03-01",
    },
    "orb": {
        "label": "Opening range breakout",
        "source": "Zarattini, Barbon & Aziz (2024) — A Profitable Day Trading Strategy, SSRN 4729284",
        "summary": "Each morning, find the 20 stocks trading the most unusual volume in the first minutes. "
                   "Buy a break of the opening-range high (or short the low), stop at 10% of ATR, flat by the close.",
        "live_mode": None,
        "params": [
            {"key": "or_minutes", "label": "Opening range", "type": "choice", "options": [5, 15, 30], "unit": "min"},
            {"key": "top_n", "label": "Stocks per day", "type": "int", "min": 5, "max": 30, "step": 5},
            {"key": "sides", "label": "Direction", "type": "choice", "options": ["both", "long"]},
            {"key": "stop_atr_frac", "label": "Stop (× ATR)", "type": "number", "min": 0.05, "max": 0.5, "step": 0.05},
            {"key": "risk_pct", "label": "Risk per trade", "type": "percent", "min": 0.0025, "max": 0.02, "step": 0.0025},
            {"key": "target_r", "label": "Profit target (R)", "type": "number", "min": 0, "max": 10, "step": 1,
             "help": "0 holds to the close, as in the paper"},
        ],
        "earliest": "2022-01-03",
    },
    "smallcap": {
        "label": "Small-cap pullback (Paula)",
        "source": "Paula's own strict / intense modes — smallcap_pullback.py",
        "summary": "Replays the live small-cap setup detector on gappers. Float, catalysts, SEC filings, halts and the "
                   "intense mode's add-on ladder can't be replayed from history and are left out.",
        "live_mode": "strict",
        "params": [
            {"key": "mode", "label": "Mode", "type": "choice", "options": ["strict", "intense"]},
            {"key": "max_candidates", "label": "Gappers watched", "type": "int", "min": 4, "max": 20, "step": 2},
        ],
        "earliest": "2022-01-03",
    },
}


def benchmark(symbol: str, start: date, end: date, equity0: float = 25_000) -> dict:
    """Buy-and-hold over the same window, for the report."""
    rows = data.daily_bars(start, end, symbols=[symbol]).get(symbol) or []
    if len(rows) < 2:
        return {}
    eq = [(datetime.fromtimestamp(r[0], ET).date().isoformat(), equity0 * r[4] / rows[0][4]) for r in rows]
    return {"symbol": symbol, **_stats(eq, [], brief=True)}


def run(strategy: str, start: date, end: date, params: dict | None = None,
        equity0: float = 25_000, progress=None) -> dict:
    res = RUNNERS[strategy](start, end, params, equity0, progress)
    out = res.summary(PUBLISHED_THROUGH.get(strategy))
    out["benchmark"] = benchmark("SPY", start, end, equity0)
    out["equity_curve"] = res.equity
    out["trade_list"] = [asdict(t) for t in res.trades]
    return out
