"""
Pre-earnings forecasting.
=========================

WHAT THIS ANSWERS
-----------------
"Which companies reporting soon are likely to beat, and what happens to the
stock if I'm wrong."

Both halves matter, and the second one is the half that gets skipped.

WHY THE SECOND NUMBER IS NOT OPTIONAL
--------------------------------------
Predicting the earnings RESULT and predicting the STOCK REACTION are different
problems with different hit rates. Companies beat and fall all the time —
guidance disappoints, or the beat was already in the price. The correlation
between surprise sign and next-day return is real but weak.

So a forecast that says "likely beat" and stops there is telling you the easier
half of the question and letting you assume the harder half. Every row here
carries `typical_move_pct`: what this specific name has actually done on its
last several earnings days, in either direction. For a small cap that is often
±20-30%, and no stop executes through it — the position gaps straight past.

That number, not the beat lean, is what should decide size.

WHAT THE SIGNALS ARE
--------------------
* **Estimate revisions** — analysts moving numbers UP in the weeks before a
  print is the best-documented free predictor of a beat. `eps_revisions`.
* **Estimate drift** — the consensus itself rising over 30/60/90 days.
  `eps_trend`.
* **Beat-rate history** — some companies beat almost every quarter because
  they guide conservatively. A real base rate, not a hunch.
* **Last quarter's surprise** — surprises autocorrelate.

WHAT THIS DELIBERATELY DOES NOT DO
-----------------------------------
It does not emit a calibrated probability. "73% chance of a beat" would be a
fabricated precision — nothing here has been backtested against outcomes, and
dressing a heuristic in a percentage invites it to be trusted like a model.
It gives the components, a directional lean, and the real historical base rate,
and lets a human weigh them.

It also places no orders, and nothing in the autopilot path consumes it. The
autopilot still refuses to hold through a print.
"""

from __future__ import annotations

import os
from datetime import datetime

LOOKBACK_QUARTERS = int(os.environ.get("FORECAST_LOOKBACK_QUARTERS", 8))
MOVE_SAMPLE = int(os.environ.get("FORECAST_MOVE_SAMPLE", 6))


def _safe(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


def _frame_rows(df) -> list[dict]:
    """yfinance returns a DataFrame, a dict, or an empty frame depending on
    version and ticker. Normalise to a list of plain dicts or []."""
    if df is None:
        return []
    try:
        if hasattr(df, "empty") and df.empty:
            return []
        if hasattr(df, "to_dict"):
            recs = df.to_dict("index")
            out = []
            for k, v in recs.items():
                row = dict(v)
                row["_key"] = str(k)
                out.append(row)
            return out
        if isinstance(df, dict):
            return [dict(v, _key=str(k)) for k, v in df.items()]
    except Exception:
        pass
    return []


def _num(v):
    try:
        if v is None:
            return None
        f = float(v)
        return None if f != f else f     # drop NaN
    except Exception:
        return None


# ── Signals ────────────────────────────────────────────────────────────────

def revision_signal(ticker: str) -> dict:
    """Are analysts moving their numbers up or down into this print?

    The single best-documented free predictor of a surprise. Rows are keyed by
    period ('0q' = current quarter).
    """
    out = {"available": False, "up": None, "down": None, "net": None,
           "score": 0.0, "note": ""}
    import yfinance as yf
    rows = _frame_rows(_safe(lambda: yf.Ticker(ticker).eps_revisions))
    if not rows:
        out["note"] = "no revision data published"
        return out
    row = None
    for r in rows:
        if str(r.get("_key", "")).lower().startswith("0q"):
            row = r
            break
    row = row or rows[0]

    # `a or b` treats a legitimate ZERO as missing. "0 analysts raised" is a
    # real and meaningful count, and falling through to the 7-day figure would
    # silently mix a 30-day window with a 7-day one — two different questions
    # reported as one number. Pick the window explicitly.
    def _window(thirty, seven):
        v = _num(row.get(thirty))
        return v if v is not None else _num(row.get(seven))

    up = _window("upLast30days", "upLast7days")
    down = _window("downLast30days", "downLast7days")
    if up is None and down is None:
        out["note"] = "no revision counts in the last 30 days"
        return out
    up = 0.0 if up is None else up
    down = 0.0 if down is None else down
    out.update(available=True, up=up, down=down, net=up - down)

    total = up + down
    if total <= 0:
        out["note"] = "no analyst moved a number in the last 30 days"
        return out
    ratio = (up - down) / total          # -1 .. +1
    out["score"] = ratio
    if ratio > 0.3:
        out["note"] = f"{up:.0f} estimates up vs {down:.0f} down in 30 days"
    elif ratio < -0.3:
        out["note"] = f"{down:.0f} estimates CUT vs {up:.0f} raised in 30 days"
    else:
        out["note"] = f"revisions mixed ({up:.0f} up, {down:.0f} down)"
    return out


def estimate_drift(ticker: str) -> dict:
    """Has consensus itself moved up over the last 90 days?"""
    out = {"available": False, "current": None, "ago_90d": None,
           "change_pct": None, "score": 0.0, "note": ""}
    import yfinance as yf
    rows = _frame_rows(_safe(lambda: yf.Ticker(ticker).eps_trend))
    if not rows:
        out["note"] = "no estimate trend published"
        return out
    row = None
    for r in rows:
        if str(r.get("_key", "")).lower().startswith("0q"):
            row = r
            break
    row = row or rows[0]

    cur = _num(row.get("current"))
    old = _num(row.get("90daysAgo")) or _num(row.get("60daysAgo")) or _num(row.get("30daysAgo"))
    if cur is None or old is None or old == 0:
        out["note"] = "estimate trend incomplete"
        return out
    ch = (cur - old) / abs(old) * 100.0
    out.update(available=True, current=cur, ago_90d=old, change_pct=round(ch, 1))
    out["score"] = max(-1.0, min(1.0, ch / 15.0))
    if ch > 2:
        out["note"] = f"consensus raised {ch:+.0f}% over 90 days"
    elif ch < -2:
        out["note"] = f"consensus cut {ch:.0f}% over 90 days"
    else:
        out["note"] = "consensus flat over 90 days"
    return out


def beat_history(ticker: str) -> dict:
    """How often this company actually beats, and by how much.

    A real base rate. Some names beat almost every quarter because they guide
    conservatively, and that is a more solid input than any of the momentum
    signals above.
    """
    out = {"available": False, "quarters": 0, "beats": 0, "beat_rate": None,
           "avg_surprise_pct": None, "last_surprise_pct": None,
           "score": 0.0, "note": ""}
    try:
        import earnings as _earn
        rows = _earn._rows(_earn._earnings_frame(ticker))
    except Exception:
        out["note"] = "no earnings history available"
        return out

    now = datetime.now(_earn.ET) if hasattr(_earn, "ET") else datetime.now()
    done = []
    for r in rows:
        try:
            dt, est, rep, sur = r
            if dt <= now and sur is not None:
                done.append((dt, sur))
        except Exception:
            continue
    done.sort(key=lambda x: x[0], reverse=True)
    done = done[:LOOKBACK_QUARTERS]
    if not done:
        out["note"] = "no completed quarters with a published surprise"
        return out

    sur = [s for _, s in done]
    beats = sum(1 for s in sur if s > 0)
    out.update(available=True, quarters=len(sur), beats=beats,
               beat_rate=round(beats / len(sur) * 100, 0),
               avg_surprise_pct=round(sum(sur) / len(sur), 1),
               last_surprise_pct=round(sur[0], 1))
    # Centre the base rate on 50%: beating 7 of 8 is information, 4 of 8 is not.
    out["score"] = max(-1.0, min(1.0, (beats / len(sur) - 0.5) * 2))
    out["note"] = (f"beat {beats} of the last {len(sur)} quarters, "
                   f"average surprise {out['avg_surprise_pct']:+.0f}%")
    return out


def typical_move(ticker: str) -> dict:
    """What this stock has actually DONE on its last several earnings days.

    The risk number. It is measured, not assumed, and it is the figure that
    should decide position size — a name that routinely gaps 25% is not made
    safe by a confident forecast, because no stop executes through a gap.
    """
    out = {"available": False, "samples": 0, "typical_move_pct": None,
           "worst_move_pct": None, "note": ""}
    try:
        import yfinance as yf
        import earnings as _earn
        t = yf.Ticker(ticker)
        rows = _earn._rows(_earn._earnings_frame(ticker))
        now = datetime.now(_earn.ET)
        past = sorted([r[0] for r in rows if r[0] <= now], reverse=True)[:MOVE_SAMPLE]
        if not past:
            out["note"] = "no past report dates to measure"
            return out
        hist = t.history(period="2y", auto_adjust=False)
        if hist is None or getattr(hist, "empty", True):
            out["note"] = "no price history to measure against"
            return out

        closes = {str(idx.date()): float(row["Close"])
                  for idx, row in hist.iterrows() if _num(row.get("Close"))}
        days = sorted(closes)
        moves = []
        for when in past:
            key = when.strftime("%Y-%m-%d")
            # First session at or after the report, versus the session before.
            after = next((d for d in days if d >= key), None)
            before = None
            for d in reversed(days):
                if d < key:
                    before = d
                    break
            if not after or not before or after == before:
                continue
            # If the report was after the close, the reaction is the NEXT day.
            idx = days.index(after)
            if after == before:
                continue
            nxt = days[idx + 1] if idx + 1 < len(days) else after
            move = (closes[nxt] - closes[before]) / closes[before] * 100.0
            moves.append(abs(move))
        if not moves:
            out["note"] = "could not line up reports with price history"
            return out
        moves.sort()
        mid = moves[len(moves) // 2]
        out.update(available=True, samples=len(moves),
                   typical_move_pct=round(mid, 1),
                   worst_move_pct=round(max(moves), 1))
        out["note"] = (f"typically moves {mid:.0f}% on earnings day "
                       f"(worst of last {len(moves)}: {max(moves):.0f}%)")
    except Exception as e:
        out["note"] = f"could not measure ({type(e).__name__})"
    return out


# ── Combination ────────────────────────────────────────────────────────────

_LEANS = [(0.45, "strong beat lean"), (0.15, "mild beat lean"),
          (-0.15, "no lean"), (-0.45, "mild miss lean")]


def _lean(score: float) -> str:
    for threshold, label in _LEANS:
        if score >= threshold:
            return label
    return "strong miss lean"


def forecast(ticker: str) -> dict:
    """Everything known before a print, as one row.

    `lean` is directional and deliberately not a percentage: none of this has
    been backtested against outcomes, and a number like "73%" would invite
    trust this has not earned.
    """
    rev = revision_signal(ticker)
    drift = estimate_drift(ticker)
    hist = beat_history(ticker)
    move = typical_move(ticker)

    # Revisions carry the most weight: they are the best-documented of the
    # three and the only one that reflects information arriving right now.
    score = round(rev["score"] * 0.45 + hist["score"] * 0.35 + drift["score"] * 0.20, 3)

    nxt = None
    try:
        import earnings as _earn
        n = _earn.next_report(ticker)
        if n and n.get("date"):
            nxt = {"date": n["date"].strftime("%Y-%m-%d"),
                   "date_str": n["date"].strftime("%B %d, %Y"),
                   "eps_estimate": n.get("eps_estimate"),
                   "days_away": (n["date"].date() - datetime.now(n["date"].tzinfo).date()).days}
    except Exception:
        pass

    return {
        "ticker": str(ticker).upper(),
        "next": nxt,
        "score": score,
        "lean": _lean(score),
        "revisions": rev,
        "estimate_drift": drift,
        "history": hist,
        "risk": move,
        "evidence": [x["note"] for x in (rev, drift, hist, move) if x.get("note")],
    }


def rank(tickers: list[str], limit: int = 12, progress=None) -> list[dict]:
    """Forecast a list of names, strongest beat lean first."""
    rows = []
    names = list(tickers or [])
    for i, t in enumerate(names):
        try:
            rows.append(forecast(t))
        except Exception:
            pass
        if progress:
            try:
                progress(i + 1, len(names), str(t).upper())
            except Exception:
                pass
    rows.sort(key=lambda r: r["score"], reverse=True)
    return rows[:limit]
