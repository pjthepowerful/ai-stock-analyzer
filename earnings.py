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


# ═══════════════════════════════════════════════════════════════════════════
#  CALENDAR  —  who reports when, and whether the system would touch them
# ═══════════════════════════════════════════════════════════════════════════
# yfinance has no "who reports on date X" query; it is one call per ticker. A
# few hundred of those is minutes, not milliseconds, so the calendar is built in
# the background and cached, and the per-stock verdicts are computed on demand
# for just the handful of names on the clicked date.

import json
import pathlib as _pl

_CACHE_DIR = _pl.Path(os.environ.get("DB_DIR", os.path.dirname(os.path.abspath(__file__))))
CALENDAR_CACHE = _CACHE_DIR / "earnings_calendar.json"
CALENDAR_TTL_HOURS = float(os.environ.get("EARNINGS_CALENDAR_TTL_HOURS", 12))
CALENDAR_MAX_TICKERS = int(os.environ.get("EARNINGS_CALENDAR_MAX", 250))


def _load_cache() -> dict:
    try:
        if CALENDAR_CACHE.exists():
            return json.loads(CALENDAR_CACHE.read_text())
    except Exception:
        pass
    return {"built_at": None, "dates": {}, "count": 0, "errors": 0}


def _save_cache(data: dict):
    try:
        CALENDAR_CACHE.parent.mkdir(parents=True, exist_ok=True)
        CALENDAR_CACHE.write_text(json.dumps(data))
    except Exception:
        pass


def cache_age_hours() -> float | None:
    c = _load_cache()
    if not c.get("built_at"):
        return None
    try:
        built = datetime.fromisoformat(c["built_at"])
        return (_now_et() - built).total_seconds() / 3600.0
    except Exception:
        return None


def cache_is_stale() -> bool:
    age = cache_age_hours()
    return age is None or age > CALENDAR_TTL_HOURS


# ── Source A: Nasdaq's earnings calendar (date-first) ──────────────────────
# Yahoo can only answer "when does TICKER report", so a calendar built from it
# is only ever as complete as the ticker list fed in — a company outside the
# universe file is invisible no matter how well it fits the strategy. Nasdaq
# answers the question the calendar actually asks ("who reports on DATE"), in
# one request per day, and hands back market cap for free, which is exactly the
# filter a small-cap strategy needs.
#
# This is Nasdaq's undocumented public JSON endpoint. It is not a contract:
# it requires a browser User-Agent, it rate-limits, and it can change shape
# without notice. So it is a preferred source, not a required one — every
# failure path falls back to the Yahoo ticker scan below.

NASDAQ_CALENDAR_URL = "https://api.nasdaq.com/api/calendar/earnings"
NASDAQ_TIMEOUT = float(os.environ.get("EARNINGS_NASDAQ_TIMEOUT", 12))
NASDAQ_PAUSE = float(os.environ.get("EARNINGS_NASDAQ_PAUSE", 0.25))
CALENDAR_DAYS_AHEAD = int(os.environ.get("EARNINGS_CALENDAR_DAYS_AHEAD", 45))
CALENDAR_DAYS_BACK = int(os.environ.get("EARNINGS_CALENDAR_DAYS_BACK", 7))
# Cap band kept in the calendar. Wider than any trading mode's band on purpose:
# the calendar is for looking at, and the per-date verdict applies the mode's
# real limits. This only throws out the mega caps that could never be setups.
CALENDAR_CAP_MAX = float(os.environ.get("EARNINGS_CALENDAR_CAP_MAX", 5e9))
CALENDAR_CAP_MIN = float(os.environ.get("EARNINGS_CALENDAR_CAP_MIN", 5e6))

_NASDAQ_HOUR = {"time-pre-market": "BMO", "time-after-hours": "AMC"}


def _nasdaq_num(val):
    """Parse Nasdaq's money strings.

    They arrive as display text, not numbers: '$1,234,567', '(0.12)' for a
    negative EPS in accounting parentheses, '$1.2B', 'N/A'. Anything that
    doesn't parse becomes None rather than raising or guessing zero — zero is
    a real EPS value and must not be invented.
    """
    if val is None:
        return None
    s = str(val).strip()
    if not s or s.upper() in ("N/A", "NA", "--", "-", "$", "NONE"):
        return None
    neg = s.startswith("(") and s.endswith(")")
    s = s.strip("()").replace("$", "").replace(",", "").strip()
    mult = 1.0
    if s and s[-1].upper() in ("K", "M", "B", "T"):
        mult = {"K": 1e3, "M": 1e6, "B": 1e9, "T": 1e12}[s[-1].upper()]
        s = s[:-1].strip()
    try:
        n = float(s) * mult
    except ValueError:
        return None
    return -n if neg else n


def nasdaq_day(date_str: str) -> list[dict]:
    """Every company Nasdaq lists as reporting on one date.

    Returns [] for a day with no reports (weekends, holidays) — Nasdaq sends
    a null rows list for those, which is data, not an error.
    """
    import requests
    hdrs = {
        "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/125.0.0.0 Safari/537.36"),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
    }
    r = requests.get(NASDAQ_CALENDAR_URL, params={"date": date_str},
                     headers=hdrs, timeout=NASDAQ_TIMEOUT)
    r.raise_for_status()
    rows = (((r.json() or {}).get("data") or {}).get("rows")) or []
    out = []
    for row in rows:
        sym = str(row.get("symbol") or "").upper().strip()
        if not sym:
            continue
        out.append({
            "ticker": sym,
            "company": (str(row.get("name") or "").strip() or None),
            "eps_estimate": _nasdaq_num(row.get("epsForecast")),
            "market_cap": _nasdaq_num(row.get("marketCap")),
            "hour": _NASDAQ_HOUR.get(str(row.get("time") or "").strip()),
            "confirmed": True,
        })
    return out


def _in_calendar_band(cap) -> bool:
    """Keep a name in the calendar on market cap.

    An unknown cap is KEPT. Nasdaq routinely omits cap for the smallest names,
    and those are the ones this strategy trades — dropping on unknown would
    systematically delete the targets.
    """
    if cap is None:
        return True
    return CALENDAR_CAP_MIN <= cap <= CALENDAR_CAP_MAX


def build_calendar_from_nasdaq(days_ahead: int | None = None,
                               days_back: int | None = None,
                               keep: set | None = None,
                               progress=None,
                               fetch=None) -> dict:
    """Walk a date range against Nasdaq and cache date -> [companies].

    Raises if Nasdaq is unreachable on EVERY day tried, so the caller can fall
    back. A partial result — most days fetched, a few failed — is kept, since
    a calendar missing three days beats no calendar.
    """
    import time
    ahead = CALENDAR_DAYS_AHEAD if days_ahead is None else days_ahead
    back = CALENDAR_DAYS_BACK if days_back is None else days_back
    getter = fetch or nasdaq_day
    keep = {str(k).upper() for k in (keep or set())}

    today = _now_et().date()
    days = [today + timedelta(days=d) for d in range(-back, ahead + 1)]
    days = [d for d in days if d.weekday() < 5]   # Nasdaq is empty on weekends

    dates: dict = {}
    errors = 0
    tickers_seen: set = set()
    for i, d in enumerate(days):
        key = d.strftime("%Y-%m-%d")
        try:
            rows = getter(key)
        except Exception:
            errors += 1
            continue
        kept = [r for r in rows
                if r.get("ticker") in keep or _in_calendar_band(r.get("market_cap"))]
        if kept:
            kept.sort(key=lambda r: r["ticker"])
            dates[key] = kept
            tickers_seen.update(r["ticker"] for r in kept)
        if progress:
            try:
                progress(i + 1, len(days), key)
            except Exception:
                pass
        if NASDAQ_PAUSE:
            time.sleep(NASDAQ_PAUSE)

    # Distinguish "nothing was asked" from "everything failed". Without the
    # first guard an all-weekend range reports total failure and sends the
    # caller to the fallback for no reason.
    if not days:
        raise RuntimeError("no trading days in the requested range")
    if errors and errors == len(days):
        raise RuntimeError(f"Nasdaq unreachable on all {errors} days tried")

    data = {"built_at": _now_et().isoformat(), "dates": dates,
            "count": len(tickers_seen), "errors": errors, "source": "nasdaq"}
    _save_cache(data)
    return data


# ── Source B: Yahoo, one call per ticker (fallback) ────────────────────────

def build_calendar_from_tickers(tickers: list[str], progress=None) -> dict:
    """Scan tickers for their next report date and cache date -> [tickers].

    Slow and rate-limit sensitive, so it is capped and meant to run off the
    request path. Partial results are still cached: a calendar covering 200 of
    250 names is far more useful than none.

    Only as complete as the list handed in — which is why Nasdaq is tried
    first. This exists so the calendar still works when Nasdaq does not.
    """
    seen, ordered = set(), []
    for t in tickers or []:
        u = str(t).upper().strip()
        if u and u not in seen:
            seen.add(u)
            ordered.append(u)
    ordered = ordered[:CALENDAR_MAX_TICKERS]

    dates: dict = {}
    errors = 0
    for i, t in enumerate(ordered):
        try:
            nxt = next_report(t)
            if nxt and nxt.get("date"):
                key = nxt["date"].strftime("%Y-%m-%d")
                dates.setdefault(key, []).append({
                    "ticker": t,
                    "eps_estimate": nxt.get("eps_estimate"),
                    "confirmed": nxt.get("confirmed", False),
                    "hour": nxt["date"].strftime("%H:%M"),
                })
        except Exception:
            errors += 1
        if progress:
            try:
                progress(i + 1, len(ordered), t)
            except Exception:
                pass

    for k in dates:
        dates[k].sort(key=lambda r: r["ticker"])
    data = {"built_at": _now_et().isoformat(), "dates": dates,
            "count": len(ordered), "errors": errors, "source": "yahoo"}
    _save_cache(data)
    return data


def build_calendar(tickers: list[str] | None = None, keep: set | None = None,
                   progress=None) -> dict:
    """Build the calendar from the best source available.

    Nasdaq first — it is date-first, so it sees every reporting company rather
    than only the ones on our list. Yahoo second, scanning `tickers`, for when
    Nasdaq is blocked or has changed shape.

    `keep` is the short list that bypasses the cap filter — held positions,
    which you need reporting dates for whatever their size. It deliberately
    defaults to nothing rather than to `tickers`: the universe list is mostly
    names the filter is there to remove.
    """
    try:
        return build_calendar_from_nasdaq(keep=set(keep or ()), progress=progress)
    except Exception as e:
        print(f"[earnings] Nasdaq calendar unavailable ({e!r}); "
              f"falling back to per-ticker scan", flush=True)
    return build_calendar_from_tickers(tickers or [], progress=progress)


def calendar_month(year: int, month: int) -> dict:
    """date -> [tickers] for one month, straight from cache."""
    c = _load_cache()
    prefix = f"{year:04d}-{month:02d}-"
    out = {k: v for k, v in (c.get("dates") or {}).items() if k.startswith(prefix)}
    return {"dates": out, "built_at": c.get("built_at"),
            "count": c.get("count", 0), "errors": c.get("errors", 0),
            "source": c.get("source"), "stale": cache_is_stale()}


# ── Per-stock verdict ──────────────────────────────────────────────────────

def _universe_fit(ticker: str, mode: dict | None) -> tuple[bool, str]:
    """Does this name fall inside the trading mode's universe at all?

    Price and market cap only — the volatility and setup checks need intraday
    bars that do not exist for a future date, so they are deliberately not
    pretended at here.
    """
    if not mode:
        return True, ""
    try:
        import yfinance as yf
        info = yf.Ticker(ticker).get_info() or {}
        price = info.get("currentPrice") or info.get("regularMarketPrice")
        cap = info.get("marketCap")
    except Exception:
        return True, "couldn't load price/cap"

    if price is not None:
        lo, hi = mode.get("PRICE_MIN"), mode.get("PRICE_MAX")
        if lo and price < lo:
            return False, f"${price:.2f} below the ${lo:.0f} floor"
        if hi and price > hi:
            return False, f"${price:.2f} above the ${hi:.0f} ceiling"
    if cap is not None:
        lo, hi = mode.get("MCAP_MIN"), mode.get("MCAP_MAX")
        if lo and cap < lo:
            return False, f"${cap/1e6:.0f}M cap below the floor"
        if hi and cap > hi:
            return False, f"${cap/1e9:.1f}B cap above the ceiling"
    return True, ""


def verdict(ticker: str, mode: dict | None = None) -> dict:
    """Would the system buy this around its earnings, and why not.

    The honest answer before a print is always no. The strategy flattens daily
    and never holds into an announcement, because a stop does not execute
    through a gap. So the useful signal is not "buy before" — it is whether the
    name is worth watching for the reaction afterwards, and whether the reaction
    that already happened is still tradable.

    Verdicts:
      blocked   — reports before the next open; autopilot will not enter
      watch     — reports later, fits the universe, worth watching after it prints
      skip      — outside the tradable universe entirely
      candidate — already reported and beat, still inside the drift window
      fade      — already reported and MISSED; a rally on that is a fade setup
      stale     — reported too long ago to be today's catalyst
    """
    out = {"ticker": ticker.upper(), "verdict": "watch", "reason": "",
           "buyable": False, "next": None, "last": None}
    try:
        nxt = next_report(ticker)
        last = last_report(ticker)
        out["next"] = _serialise(nxt)
        out["last"] = _serialise(last)

        fits, why_not = _universe_fit(ticker, mode)
        if not fits:
            out["verdict"] = "skip"
            out["reason"] = f"outside this mode's universe — {why_not}"
            return out

        rec = recent_print(ticker)
        if rec:
            if rec["verdict"] == "beat":
                out["verdict"] = "candidate"
                out["buyable"] = True
                out["reason"] = (f"beat by {rec['surprise_pct']:.0f}% "
                                 f"{'today' if rec['sessions_ago'] == 0 else 'recently'} — "
                                 f"the reaction is tradable while it still has volume")
            elif rec["verdict"] == "miss":
                out["verdict"] = "fade"
                out["reason"] = (f"missed by {abs(rec['surprise_pct']):.0f}% — "
                                 f"any rally here is against the news, not because of it")
            else:
                out["verdict"] = "watch"
                out["reason"] = "reported in line; no edge either way"
            return out

        blocked, why = reports_before_next_open(ticker)
        if blocked:
            out["verdict"] = "blocked"
            out["reason"] = (f"{why} — autopilot will not open a position that "
                             f"would be held through it; a stop does not execute "
                             f"through an earnings gap")
            return out

        if nxt and nxt.get("days_away") is not None:
            d = nxt["days_away"]
            out["verdict"] = "watch"
            out["reason"] = (f"reports in {d} day{'s' if d != 1 else ''}. Nothing to do "
                             f"before then — the system trades the reaction, not the print")
        else:
            out["verdict"] = "watch"
            out["reason"] = "no confirmed date"
    except Exception as e:
        out["reason"] = f"lookup failed: {str(e)[:80]}"
    return out
