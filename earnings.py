"""
Earnings intelligence for Paula.
================================

Two jobs:

1. **Answer questions** — when does a company report, what does the street
   expect, what did it actually do last time, and by how much did it miss or
   beat. Surfaced in the Co-Pilot tab and in chat.

2. **Feed the Intense trading mode** — turn "did this gap on earnings?" from an
   LLM guess at headlines into a verified fact with numbers behind it.

WHY THIS MATTERS TO THE TRADING SIDE
------------------------------------
The small-cap engine grades every gapper's catalyst as real / fluff / none by
asking an LLM to read the headlines. That is a reasonable fallback and a poor
primary source: "Q3 revenue up 40%" and "announces intent to explore Q3
opportunities" look similar to a language model scanning a feed, and only one of
them is a reason for a stock to be up 30%.

An earnings print is the one catalyst that can be *checked*. If a company
reported yesterday and beat by 40%, that is not a promotion — it is a number
that a filing confirms. So a verified recent print outranks the LLM grade.

THE RISK THIS MODULE DOES NOT REMOVE
------------------------------------
Trading earnings reactions is not the same as holding through a print, and this
module never enables the latter. Holding a position into an announcement is the
one thing the underlying strategy document calls an account-ender: stops do not
execute through a gap, and a 30% overnight move against a concentrated position
is not survivable on a small account.

What is tradable is the *reaction* — the session after the print, when the news
is public, the market is open and the book is liquid. That is post-earnings
announcement drift, and it is why `recent_print()` looks backwards and
`reports_before_next_open()` exists to block the forward-looking case.

DATA SOURCE
-----------
yfinance, which wraps Yahoo. It is free and already a dependency, but its return
shapes are inconsistent across versions and tickers — the same call yields a
dict, a DataFrame, or an empty frame depending on the name. Every accessor here
handles all three and degrades to None rather than raising, because an earnings
lookup failing must never take down a scan.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

ET = ZoneInfo("US/Eastern")

# A print is "recent" if it landed within this many sessions. The drift effect
# is strongest in the first day or two; past that the gap has been digested and
# the name is trading on something else.
RECENT_SESSIONS = int(os.environ.get("EARNINGS_RECENT_SESSIONS", 2))

# Surprise beyond this counts as a genuine beat/miss rather than an in-line
# print rounded off. A 1% beat is noise; the street models it that closely.
SURPRISE_THRESHOLD = float(os.environ.get("EARNINGS_SURPRISE_PCT", 5.0))


def _now_et() -> datetime:
    return datetime.now(ET)


def _as_datetime(val):
    """yfinance hands back str / Timestamp / datetime depending on the call."""
    if val is None:
        return None
    try:
        if isinstance(val, str):
            import pandas as pd
            return pd.to_datetime(val).to_pydatetime()
        if hasattr(val, "to_pydatetime"):
            return val.to_pydatetime()
        if isinstance(val, datetime):
            return val
    except Exception:
        return None
    return None


def _to_et(dt):
    """Normalise to Eastern so date comparisons against the session are valid."""
    if dt is None:
        return None
    try:
        if getattr(dt, "tzinfo", None) is None:
            return dt.replace(tzinfo=ET)
        return dt.astimezone(ET)
    except Exception:
        return None


def _num(val):
    """Coerce to float, treating NaN and blanks as missing."""
    if val is None:
        return None
    try:
        f = float(val)
        return None if f != f else f          # NaN != NaN
    except Exception:
        return None


# ═══════════════════════════════════════════════════════════════════════════
#  RAW FETCH
# ═══════════════════════════════════════════════════════════════════════════

def _earnings_frame(ticker: str):
    """The earnings-history table: one row per quarter, indexed by date.

    Columns vary by yfinance version; commonly 'EPS Estimate', 'Reported EPS'
    and 'Surprise(%)'. Returns None on any failure — callers must cope.
    """
    try:
        import yfinance as yf
        df = yf.Ticker(ticker).earnings_dates
        if df is None or len(df) == 0:
            return None
        return df
    except Exception:
        return None


def _column(df, *names):
    """First matching column name, case/spacing tolerant across versions."""
    if df is None:
        return None
    norm = {str(c).lower().replace(" ", "").replace("(", "").replace(")", "").replace("%", "pct"): c
            for c in df.columns}
    for n in names:
        key = n.lower().replace(" ", "").replace("(", "").replace(")", "").replace("%", "pct")
        if key in norm:
            return norm[key]
    return None


def _rows(df):
    """(datetime_et, estimate, reported, surprise_pct) per row, newest first."""
    if df is None:
        return []
    est_c = _column(df, "EPS Estimate", "epsestimate")
    rep_c = _column(df, "Reported EPS", "reportedeps")
    sur_c = _column(df, "Surprise(%)", "surprisepct", "Surprise")
    out = []
    try:
        for idx, row in df.iterrows():
            dt = _to_et(_as_datetime(idx))
            if dt is None:
                continue
            est = _num(row.get(est_c)) if est_c else None
            rep = _num(row.get(rep_c)) if rep_c else None
            sur = _num(row.get(sur_c)) if sur_c else None
            # Yahoo sometimes reports surprise as a fraction (0.42) and
            # sometimes as a percentage (42.0). Derive it ourselves when both
            # sides are present, which is unambiguous.
            if sur is None and est not in (None, 0) and rep is not None:
                sur = (rep - est) / abs(est) * 100.0
            out.append((dt, est, rep, sur))
    except Exception:
        return []
    out.sort(key=lambda r: r[0], reverse=True)
    return out


# ═══════════════════════════════════════════════════════════════════════════
#  PUBLIC API
# ═══════════════════════════════════════════════════════════════════════════

def next_report(ticker: str) -> dict | None:
    """The next scheduled report, or None if nothing is on the calendar.

    A row counts as upcoming when it has no reported EPS yet and sits in the
    future — Yahoo keeps future quarters in the same table as past ones.

    Never raises: a safety guard is built on this, and an exception escaping
    here would be caught upstream as "no earnings found", which is the
    permissive direction on exactly the wrong question.
    """
    try:
        rows = _rows(_earnings_frame(ticker))
    except Exception:
        rows = []
    now = _now_et()
    upcoming = [r for r in rows if r[0] > now and r[2] is None]
    if not upcoming:
        # Fall back to the calendar object, which sometimes has a date when the
        # history table does not.
        try:
            import yfinance as yf
            cal = yf.Ticker(ticker).calendar
            ed = None
            if isinstance(cal, dict):
                ed = cal.get("Earnings Date")
                if isinstance(ed, list) and ed:
                    ed = ed[0]
            elif cal is not None and hasattr(cal, "columns"):
                if "Earnings Date" in getattr(cal, "columns", []):
                    ed = cal["Earnings Date"].iloc[0]
                elif "Earnings Date" in getattr(cal, "index", []):
                    ed = cal.loc["Earnings Date"].iloc[0]
            dt = _to_et(_as_datetime(ed))
            if dt and dt > now:
                return {"ticker": ticker.upper(), "date": dt,
                        "date_str": dt.strftime("%B %d, %Y"),
                        "days_away": (dt.date() - now.date()).days,
                        "eps_estimate": None, "confirmed": False}
        except Exception:
            pass
        return None
    dt, est, _rep, _sur = min(upcoming, key=lambda r: r[0])
    return {"ticker": ticker.upper(), "date": dt,
            "date_str": dt.strftime("%B %d, %Y"),
            "days_away": (dt.date() - now.date()).days,
            "eps_estimate": est, "confirmed": True}


def last_report(ticker: str) -> dict | None:
    """The most recent completed report, with the surprise. Never raises."""
    try:
        rows = _rows(_earnings_frame(ticker))
    except Exception:
        return None
    now = _now_et()
    done = [r for r in rows if r[0] <= now and r[2] is not None]
    if not done:
        return None
    dt, est, rep, sur = max(done, key=lambda r: r[0])
    verdict = "in line"
    if sur is not None:
        if sur >= SURPRISE_THRESHOLD:
            verdict = "beat"
        elif sur <= -SURPRISE_THRESHOLD:
            verdict = "miss"
    return {"ticker": ticker.upper(), "date": dt,
            "date_str": dt.strftime("%B %d, %Y"),
            "days_ago": (now.date() - dt.date()).days,
            "eps_estimate": est, "eps_actual": rep,
            "surprise_pct": round(sur, 1) if sur is not None else None,
            "verdict": verdict}


def _sessions_between(then: datetime, now: datetime) -> int:
    """Trading sessions between two dates, weekends excluded.

    Holidays are not modelled, so this can overcount by a day around one. That
    only ever makes `recent_print` slightly stricter, which is the safe
    direction for a gate that permits trading.
    """
    if then is None or now is None or then > now:
        return 0
    days = 0
    cur = then.date()
    end = now.date()
    while cur < end:
        cur += timedelta(days=1)
        if cur.weekday() < 5:
            days += 1
    return days


def recent_print(ticker: str, within_sessions: int | None = None) -> dict | None:
    """Did this name report within the last N sessions? The tradable case.

    This is what makes an earnings gap a *verified* catalyst: the move has a
    filing behind it, not a press release about exploring opportunities.
    """
    within = RECENT_SESSIONS if within_sessions is None else within_sessions
    last = last_report(ticker)
    if not last:
        return None
    sessions = _sessions_between(last["date"], _now_et())
    if sessions > within:
        return None
    return {**last, "sessions_ago": sessions}


def reports_before_next_open(ticker: str) -> tuple[bool, str]:
    """Would a print land between now and the next session's open?

    The forward-looking guard. A position opened now and held into that print is
    exposed to a gap no stop can protect against. The Intense mode flattens
    before the close, so an after-close print is structurally survived — but
    this is belt-and-braces, and it also catches the genuinely dangerous case of
    a print scheduled during today's session.
    """
    nxt = next_report(ticker)
    if not nxt or not nxt.get("date"):
        return False, ""
    now = _now_et()
    dt = nxt["date"]
    horizon = now + timedelta(days=1)
    if now <= dt <= horizon:
        when = dt.strftime("%b %d %I:%M %p ET").replace(" 0", " ")
        return True, f"reports {when}"
    return False, ""


def snapshot(ticker: str) -> dict:
    """Everything known about one ticker's earnings. Never raises."""
    out = {"ticker": ticker.upper(), "next": None, "last": None,
           "recent": None, "blocked": False, "block_reason": ""}
    try:
        nxt = next_report(ticker)
        last = last_report(ticker)
        out["next"] = _serialise(nxt)
        out["last"] = _serialise(last)
        rec = recent_print(ticker)
        out["recent"] = _serialise(rec)
        blocked, why = reports_before_next_open(ticker)
        out["blocked"] = blocked
        out["block_reason"] = why
    except Exception:
        pass
    return out


def _serialise(d):
    """Drop the datetime so the dict is JSON-safe for the API and the UI."""
    if not d:
        return None
    return {k: v for k, v in d.items() if k != "date"}


def calendar(tickers: list[str], days: int = 7) -> list[dict]:
    """Upcoming reports among a set of tickers, soonest first."""
    out = []
    for t in tickers or []:
        try:
            nxt = next_report(t)
            if nxt and nxt.get("days_away") is not None and 0 <= nxt["days_away"] <= days:
                out.append(_serialise(nxt))
        except Exception:
            continue
    out.sort(key=lambda r: r.get("days_away", 999))
    return out


# ═══════════════════════════════════════════════════════════════════════════
#  TRADING-SIDE CLASSIFICATION
# ═══════════════════════════════════════════════════════════════════════════

def catalyst_from_earnings(ticker: str) -> dict | None:
    """Grade a gapper's catalyst from its earnings, when one explains the move.

    Returns the same shape the small-cap engine's LLM catalyst grader produces,
    so it can substitute directly:

        {"grade": "real"|"fluff"|"none", "reason": str, "source": "earnings"}

    A verified beat is the strongest catalyst this universe produces. A verified
    *miss* that has gapped the stock up is the opposite — the move is a bounce
    against the news rather than a reaction to it, which is a fade setup rather
    than a long one, so it is graded down instead of up.
    """
    rec = recent_print(ticker)
    if not rec:
        return None
    sur = rec.get("surprise_pct")
    verdict = rec.get("verdict")
    when = "today" if rec["sessions_ago"] == 0 else (
        "yesterday" if rec["sessions_ago"] == 1 else f"{rec['sessions_ago']} sessions ago")

    if verdict == "beat":
        return {"grade": "real", "source": "earnings",
                "reason": f"reported {when}, beat by {sur:.0f}%",
                "surprise_pct": sur, "verdict": verdict}
    if verdict == "miss":
        return {"grade": "fluff", "source": "earnings",
                "reason": f"reported {when}, MISSED by {abs(sur):.0f}% — "
                          f"a rally against a miss is a fade, not a catalyst",
                "surprise_pct": sur, "verdict": verdict}
    return {"grade": "real", "source": "earnings",
            "reason": f"reported {when}, in line",
            "surprise_pct": sur, "verdict": verdict}
