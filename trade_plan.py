"""
Trade plan for an earnings idea — entry, stop loss, targets, size.

Every earnings screen answers "is this worth looking at"; this answers "and if
I take it, where am I wrong". Levels come from the stock's own daily range
(ATR) and its recent swing low, not a flat percentage, so a sleepy utility and
a biotech get stops that fit how they actually move.

The one thing a stop cannot do is protect through an earnings gap: the stock
opens past it and the order fills wherever the market is. So every plan also
carries the name's typical earnings-day move, and says so plainly when that
move is bigger than the stop.

Advisory only. Nothing here places an order.
"""
from __future__ import annotations

import math
import os
import threading
import time

ATR_DAYS = 14
ATR_STOP_MULT = float(os.environ.get("PLAN_ATR_STOP_MULT", 2.0))
SWING_DAYS = 10
# Account risk per idea: lose this fraction of equity if the stop fills.
RISK_PCT = float(os.environ.get("PLAN_RISK_PCT", 0.01))
TARGET_R = (2.0, 3.0)
GAP_WARN_DAYS = 30

_BARS_TTL = 15 * 60
_bars_cache: dict[str, tuple[float, object]] = {}
_bars_lock = threading.Lock()


def _bars(ticker: str):
    """Two years of daily bars — enough for ATR and ~8 past earnings moves."""
    t = ticker.upper()
    with _bars_lock:
        hit = _bars_cache.get(t)
        if hit and time.time() - hit[0] < _BARS_TTL:
            return hit[1]
    try:
        import yfinance as yf
        df = yf.Ticker(t).history(period="2y", interval="1d", auto_adjust=False)
        if df is None or len(df) < ATR_DAYS + 2:
            df = None
    except Exception:
        df = None
    with _bars_lock:
        _bars_cache[t] = (time.time(), df)
    return df


def _atr(df) -> float | None:
    high, low, close = df["High"], df["Low"], df["Close"]
    prev = close.shift(1)
    tr = (high - low).combine((high - prev).abs(), max).combine((low - prev).abs(), max)
    val = float(tr.tail(ATR_DAYS).mean())
    return val if math.isfinite(val) and val > 0 else None


def earnings_moves(ticker: str, df=None) -> list[float]:
    """Absolute % moves on past earnings reactions, newest first.

    Yahoo doesn't say whether a report came before the open or after the
    close, so the reaction is the bigger of the report day and the day after —
    one of the two is the gap, the other an ordinary session.
    """
    df = _bars(ticker) if df is None else df
    if df is None:
        return []
    try:
        import earnings as earn
        rows = earn._rows(earn._earnings_frame(ticker))
    except Exception:
        return []
    closes = df["Close"]
    days = [d.date() for d in df.index]
    moves = []
    for dt, _est, rep, _sur in rows:
        if rep is None:
            continue
        d = dt.date()
        # First session on or after the report date.
        i = next((k for k, day in enumerate(days) if day >= d), None)
        if i is None or i < 1 or i + 1 >= len(days) or (days[i] - d).days > 4:
            continue
        c0, c1, c2 = float(closes.iloc[i - 1]), float(closes.iloc[i]), float(closes.iloc[i + 1])
        if c0 <= 0 or c1 <= 0:
            continue
        moves.append(max(abs(c1 / c0 - 1), abs(c2 / c1 - 1)) * 100)
    return moves[:8]


def _money(x: float) -> str:
    return f"${x:,.2f}"


def plan(ticker: str, side: str = "long", equity: float | None = None,
         next_report: dict | None = None, max_dollars: float | None = None) -> dict:
    """Entry, stop, two targets and a risk-based size for one name.

    `next_report` is earnings.next_report()'s dict (or anything with
    days_away / date_str) — pass it when the caller already has it.
    Never raises; `available: False` with a `note` when there's no data.
    """
    side = "short" if side == "short" else "long"
    out = {"available": False, "side": side, "note": ""}
    df = _bars(ticker)
    if df is None:
        out["note"] = "no price history to set levels from"
        return out
    try:
        entry = float(df["Close"].iloc[-1])
        atr = _atr(df)
        if not atr or entry <= 0:
            out["note"] = "not enough price history to measure its range"
            return out
        sign = 1 if side == "long" else -1

        # Stop: under the recent swing low (over the swing high for a short)
        # when that's a sensible distance away, else 2× ATR. A swing point
        # closer than 1 ATR is inside normal noise and would get tagged by an
        # ordinary day; one further than the ATR stop risks too much.
        atr_stop = entry - sign * ATR_STOP_MULT * atr
        recent = df.tail(SWING_DAYS)
        swing = (float(recent["Low"].min()) - 0.25 * atr) if side == "long" \
            else (float(recent["High"].max()) + 0.25 * atr)
        dist_swing = sign * (entry - swing)
        if atr <= dist_swing <= ATR_STOP_MULT * atr:
            stop = swing
            basis = f"just {'under' if side == 'long' else 'over'} the {SWING_DAYS}-day swing {'low' if side == 'long' else 'high'}"
        else:
            stop = atr_stop
            basis = f"{ATR_STOP_MULT:g}× its average daily range ({_money(atr)})"
        risk = abs(entry - stop)
        targets = [entry + sign * r * risk for r in TARGET_R]
        if side == "short" and targets[-1] <= 0:
            targets = [max(t, 0.01) for t in targets]

        out.update({
            "available": True,
            "entry": round(entry, 2),
            "stop": round(stop, 2),
            "stop_pct": round(risk / entry * 100, 1),
            "targets": [round(t, 2) for t in targets],
            "target_r": list(TARGET_R),
            "risk_per_share": round(risk, 2),
            "atr": round(atr, 2),
            "atr_pct": round(atr / entry * 100, 1),
            "basis": basis,
        })

        # Nearest overhead resistance (support for a short) inside the first
        # target: the 60-day extreme is where the last buyers gave up.
        look = df.tail(60)
        wall = float(look["High"].max()) if side == "long" else float(look["Low"].min())
        if sign * (wall - entry) > 0.25 * atr and sign * (targets[0] - wall) > 0:
            out["resistance"] = round(wall, 2)

        # Size: lose RISK_PCT of equity if the stop fills, never more than
        # the per-idea dollar cap.
        if equity and equity > 0:
            shares = int(equity * RISK_PCT // risk)
            if max_dollars:
                shares = min(shares, int(max_dollars // entry))
            out["shares"] = max(shares, 0)
            out["risk_dollars"] = round(shares * risk, 2)
            out["size_note"] = (f"risks {RISK_PCT*100:g}% of equity at the stop"
                                + (f", capped at {_money(max_dollars)}" if max_dollars else ""))

        # Earnings gap risk.
        moves = earnings_moves(ticker, df)
        if moves:
            avg = sum(moves) / len(moves)
            out["earnings_move_pct"] = round(avg, 1)
            out["earnings_move_max_pct"] = round(max(moves), 1)
            out["earnings_quarters"] = len(moves)
        days_away = (next_report or {}).get("days_away")
        # Only a report inside a normal swing hold is worth warning about.
        if days_away is not None and 0 <= days_away <= GAP_WARN_DAYS:
            when = (next_report or {}).get("date_str") or f"in {days_away}d"
            gap = out.get("earnings_move_pct")
            if gap and gap > out["stop_pct"]:
                out["warning"] = (f"Reports {when}. Its typical earnings move (±{gap:.1f}%) is bigger than "
                                  f"this stop ({out['stop_pct']:.1f}%) — a stop won't fill through a gap. "
                                  f"Exit before the report or size for the gap.")
            else:
                out["warning"] = (f"Reports {when}. A stop doesn't protect through the report — "
                                  f"it can open past it.")
    except Exception as e:
        out = {"available": False, "side": side, "note": f"couldn't build levels ({type(e).__name__})"}
    return out


def side_for(verdict: str | None) -> str:
    """Calendar verdicts that lean bearish get a short-side plan."""
    return "short" if verdict in ("fade", "lean_miss") else "long"


def summary(p: dict) -> str:
    """One line for chat answers."""
    if not p.get("available"):
        return ""
    t = p["targets"]
    s = (f"{p['side']} plan: entry ~{_money(p['entry'])}, stop {_money(p['stop'])} ({p['stop_pct']}% away), "
         f"targets {_money(t[0])} / {_money(t[1])}")
    if p.get("earnings_move_pct"):
        s += f"; typical earnings move ±{p['earnings_move_pct']}%"
    return s
