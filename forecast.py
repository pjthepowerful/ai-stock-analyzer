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

AND THE REACTION ITSELF IS PARTLY MEASURABLE
---------------------------------------------
Nothing free can read a conference call before it happens, so the guidance that
actually drives most reactions cannot be forecast directly. But a company whose
stock has fallen on most of its recent BEATS is one whose calls keep
disappointing, and that pattern is measurable. `reaction_history()` reports it,
and `runup()` reports how much of a beat is already in the price.

These are kept as a SEPARATE lean, never blended into the earnings one.
Averaging them would turn "reliably beats, reliably sells off" — the single
most useful thing to know here — into a mild positive.

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


def _reactions(ticker: str) -> tuple[list, str]:
    """Past earnings days paired with what the STOCK actually did.

    One fetch, three uses. Each entry is {surprise, move_pct, runup_pct} where
    move_pct is SIGNED — the direction is the whole point, since the question
    is not how far the stock moved but whether beating it helped.
    """
    import yfinance as yf
    import earnings as _earn
    rows = _earn._rows(_earn._earnings_frame(ticker))
    now = datetime.now(_earn.ET)
    past = [(r[0], r[3]) for r in rows if r[0] <= now]
    past.sort(key=lambda x: x[0], reverse=True)
    past = past[:MOVE_SAMPLE]
    if not past:
        return [], "no past report dates to measure"

    hist = yf.Ticker(ticker).history(period="2y", auto_adjust=False)
    if hist is None or getattr(hist, "empty", True):
        return [], "no price history to measure against"

    closes = {str(idx.date()): float(row["Close"])
              for idx, row in hist.iterrows() if _num(row.get("Close"))}
    days = sorted(closes)
    if not days:
        return [], "no usable closes in the price history"

    out = []
    for when, surprise in past:
        key = when.strftime("%Y-%m-%d")
        after = next((d for d in days if d >= key), None)
        before = None
        for d in reversed(days):
            if d < key:
                before = d
                break
        if not after or not before or after == before:
            continue
        i = days.index(after)
        # A report after the close moves the NEXT session, so take one further.
        nxt = days[i + 1] if i + 1 < len(days) else after
        move = (closes[nxt] - closes[before]) / closes[before] * 100.0

        # How far the stock had already run in the 20 sessions before the
        # print. A name up 30% into a beat has the beat in the price already.
        j = days.index(before)
        runup = None
        if j >= 20:
            base = closes[days[j - 20]]
            if base:
                runup = (closes[before] - base) / base * 100.0
        out.append({"surprise": surprise, "move_pct": move, "runup_pct": runup})

    if not out:
        return [], "could not line up reports with price history"
    return out, ""


def typical_move(ticker: str) -> dict:
    """How far this stock moves on earnings day, in either direction.

    The risk number. Measured, not assumed, and it is what should decide
    position size — a name that routinely gaps 25% is not made safe by a
    confident forecast, because no stop executes through a gap.
    """
    out = {"available": False, "samples": 0, "typical_move_pct": None,
           "worst_move_pct": None, "note": ""}
    try:
        rx, why = _reactions(ticker)
        if not rx:
            out["note"] = why
            return out
        moves = sorted(abs(r["move_pct"]) for r in rx)
        mid = moves[len(moves) // 2]
        out.update(available=True, samples=len(moves),
                   typical_move_pct=round(mid, 1),
                   worst_move_pct=round(max(moves), 1))
        out["note"] = (f"typically moves {mid:.0f}% on earnings day "
                       f"(worst of last {len(moves)}: {max(moves):.0f}%)")
    except Exception as e:
        out["note"] = f"could not measure ({type(e).__name__})"
    return out


def reaction_history(ticker: str) -> dict:
    """Does beating actually help THIS stock?

    The gap this closes: predicting the earnings and predicting the stock are
    different problems. A company can beat and fall because guidance on the
    call was soft, or because the beat was already priced. Nothing free can
    read a call before it happens — but a company whose stock has dropped on
    most of its recent beats is one whose calls keep disappointing, and that
    pattern IS measurable.

    So this reports, from the same history: when this name beat, which way did
    the stock go, and how far.
    """
    out = {"available": False, "beats": 0, "beats_up": 0, "beat_up_rate": None,
           "avg_move_on_beat": None, "samples": 0, "score": 0.0, "note": ""}
    try:
        rx, why = _reactions(ticker)
        if not rx:
            out["note"] = why
            return out
        out["samples"] = len(rx)
        beats = [r for r in rx if (r["surprise"] or 0) > 0]
        if not beats:
            out["note"] = "no beats in the measured window to judge by"
            return out
        up = [r for r in beats if r["move_pct"] > 0]
        avg = sum(r["move_pct"] for r in beats) / len(beats)
        out.update(available=True, beats=len(beats), beats_up=len(up),
                   beat_up_rate=round(len(up) / len(beats) * 100, 0),
                   avg_move_on_beat=round(avg, 1))
        # Centred on a coin flip: rising on 4 of 8 beats is no information.
        out["score"] = max(-1.0, min(1.0, (len(up) / len(beats) - 0.5) * 2))
        if len(up) == len(beats):
            out["note"] = f"rose on all {len(beats)} of its recent beats (avg {avg:+.0f}%)"
        elif len(up) * 2 < len(beats):
            out["note"] = (f"FELL on {len(beats) - len(up)} of its last {len(beats)} "
                           f"beats (avg {avg:+.0f}%) — beating has not been enough")
        else:
            out["note"] = (f"rose on {len(up)} of its last {len(beats)} beats "
                           f"(avg {avg:+.0f}%)")
    except Exception as e:
        out["note"] = f"could not measure ({type(e).__name__})"
    return out


def runup(ticker: str) -> dict:
    """How much the stock has already moved into this print.

    Buy the rumour, sell the news: a name up 30% in the month before a beat
    has the beat in the price, and the reaction to good news is often a
    selloff. Measured over the last 20 sessions.
    """
    out = {"available": False, "runup_pct": None, "score": 0.0, "note": ""}
    try:
        import yfinance as yf
        hist = yf.Ticker(ticker).history(period="3mo", auto_adjust=False)
        if hist is None or getattr(hist, "empty", True):
            out["note"] = "no recent price history"
            return out
        closes = [float(r["Close"]) for _, r in hist.iterrows() if _num(r.get("Close"))]
        if len(closes) < 21:
            out["note"] = "not enough sessions to measure the run-up"
            return out
        base, last = closes[-21], closes[-1]
        if not base:
            out["note"] = "no usable base price"
            return out
        pct = (last - base) / base * 100.0
        out.update(available=True, runup_pct=round(pct, 1))
        # Only a large run-up is informative, and only as a NEGATIVE: a flat
        # stock into a print says nothing either way.
        out["score"] = -min(1.0, max(0.0, (pct - 15.0) / 25.0))
        if pct > 25:
            out["note"] = f"already up {pct:.0f}% into the print — a beat may be priced in"
        elif pct > 10:
            out["note"] = f"up {pct:.0f}% into the print"
        elif pct < -15:
            out["note"] = f"down {abs(pct):.0f}% into the print — expectations are low"
        else:
            out["note"] = f"roughly flat into the print ({pct:+.0f}%)"
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
    react = reaction_history(ticker)
    run = runup(ticker)

    # Revisions carry the most weight: they are the best-documented of the
    # three and the only one that reflects information arriving right now.
    score = round(rev["score"] * 0.45 + hist["score"] * 0.35 + drift["score"] * 0.20, 3)

    # The STOCK lean is deliberately a separate number, not blended into the
    # one above. They answer different questions, and averaging them hides
    # exactly the case worth seeing: a company that reliably beats whose stock
    # reliably falls anyway, because the call keeps disappointing. Blending
    # would show that as a mild positive and tell you nothing.
    #
    # It is conditional on the earnings lean: how this stock reacts to beats
    # is only informative if a beat is what is coming.
    stock_score = round(react["score"] * 0.7 + run["score"] * 0.3, 3)
    if score <= 0:
        # No beat expected, so "how it reacts to beats" is not the question.
        stock_lean = "n/a — no beat expected"
    elif not react.get("available") and not run.get("available"):
        stock_lean = "unknown"
    elif stock_score >= 0.3:
        stock_lean = "usually rewards a beat"
    elif stock_score <= -0.3:
        stock_lean = "often falls anyway"
    else:
        stock_lean = "mixed reaction"

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
        "stock_score": stock_score,
        "stock_lean": stock_lean,
        "revisions": rev,
        "estimate_drift": drift,
        "history": hist,
        "risk": move,
        "reaction": react,
        "runup": run,
        "evidence": [x["note"] for x in (rev, drift, hist, react, run, move)
                     if x.get("note")],
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


def quick_lean(ticker: str) -> dict:
    """A lean from the two heaviest legs only — revisions and beat history.

    A full forecast() costs four or five network calls per name, which is fine
    for one row and far too slow for a list of forty. This drops the estimate
    drift leg (0.20 of the weight) and the price-history measurement, keeping
    the two that carry 0.80 between them, and renormalises so the thresholds
    still mean what they mean in forecast().
    """
    rev = revision_signal(ticker)
    hist = beat_history(ticker)
    score = round(rev["score"] * 0.5625 + hist["score"] * 0.4375, 3)
    return {
        "score": score,
        "lean": _lean(score),
        "grounded": bool(rev.get("available") or hist.get("available")),
        "notes": [x["note"] for x in (rev, hist) if x.get("note")],
    }
