"""
Small-Cap Gainer Pullback System — Paula autopilot strategy modes.
=================================================================

Implements the formalized "scan gainers → buy the test → sell the strength"
system (see docs/small-cap-gainer-pullback-system.md) as two selectable
autopilot strategy modes, alongside Paula's existing large-cap engine:

    core    → legacy run_autopilot() in trading.py (unchanged)
    strict  → this file, Sections 1–3 + 6 as written. Hard stops only.
    aggro   → this file, loosened universe/windows, bigger R, and the
              Section 4.4 pre-planned scale-in ladder behind hard caps.

Everything here is long-only, intraday-only, and paper-account oriented.

DESIGN NOTES
------------
Three things are *rails*, not parameters — they are identical in both modes and
deliberately not exposed to the config, because the source doc identifies them
as the account-enders:

  1. Flat by the close, every day, no exceptions (financing window risk).
  2. A real mechanical stop always exists; size is never added to a position
     that has no pre-planned ladder and no fixed final stop.
  3. Max 2 attempts per ticker per day; never re-ladder after a stop-out.

Everything else is per-mode. Every entry is journaled to smallcap_ab_log.json
with its mode and whether a ladder was used, so the strict-vs-aggro A/B the
doc asks for can be settled with data instead of vibes.

This module never imports trading.py at module scope (trading.py dispatches
into it), so all engine access goes through _t().
"""

from __future__ import annotations

import json
import math
import os
import pathlib
import time
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import requests

ET = ZoneInfo("US/Eastern")

_HERE = pathlib.Path(__file__).parent
_STATE_DIR = pathlib.Path(os.environ.get("DB_DIR", str(_HERE / "desktop" / "backend")))
STATE_FILE = _STATE_DIR / "smallcap_state.json"
AB_LOG_FILE = _STATE_DIR / "smallcap_ab_log.json"

SEC_UA = os.environ.get("SEC_USER_AGENT", "Paula Trading Research paula@example.com")


# ═══════════════════════════════════════════════════════════════════════════
#  MODE DEFINITIONS
# ═══════════════════════════════════════════════════════════════════════════

_STRICT = {
    "key": "strict",
    "label": "Disciplined",
    "tagline": "The spec as written. A-grade retests only, 0.5R, hard stops.",

    # ── Section 1: universe ────────────────────────────────────────────────
    "MIN_DAY_CHANGE": 10.0,          # % vs prior close
    "PRICE_MIN": 1.50,
    "PRICE_MAX": 20.00,
    "MCAP_MIN": 50e6,
    "MCAP_MAX": 500e6,
    "FLOAT_MIN": 15e6,               # skip the 5–15M halt-chain lottery entirely
    "FLOAT_MAX": 75e6,
    "RVOL_MIN": 5.0,                 # time-adjusted
    "RVOL_MIN_AFTERNOON": 3.0,
    "DOLLAR_VOL_MIN": 10e6,          # traded before first entry
    "PROJ_DOLLAR_VOL_MIN": 30e6,     # projected full day
    "TOP_N_GAINERS": 20,

    # ── Section 2: setups ──────────────────────────────────────────────────
    "SETUPS": ["vwap_reclaim", "ema_pullback", "pdh_retest", "orb_retest",
               "hod_break", "flag"],
    "REQUIRE_RETEST": True,          # never buy the break itself
    "MIN_CONFLUENCE_LEVELS": 2,      # a level needs 2+ of VWAP/PDH/PMH/ORH/round/HVN
    "MAX_RETEST_DEPTH": 0.50,        # pullback retraces <50% of impulse
    "MAX_PULLBACK_VOL_RATIO": 0.50,  # pullback vol ≤ half the impulse leg's
    "MAX_RECLAIM_BARS": 3,
    "REQUIRE_ABOVE_VWAP": True,
    "MIN_SETUP_GRADE": 75,           # 0–100 retest-quality score

    # ── Section 2.7: time-of-day ───────────────────────────────────────────
    "ENTRY_WINDOWS": [("09:45", "11:30"), ("13:30", "15:00")],
    "OPEN_BLACKOUT_UNTIL": "09:45",
    "ALLOW_MIDDAY": False,
    "MIDDAY": ("11:30", "13:30"),

    # ── Section 3: sizing & risk ───────────────────────────────────────────
    "R_PCT": 0.005,                  # 0.5% of equity per trade while unproven
    "MAX_POSITIONS": 2,
    "LIQ_CAP_ADV_PCT": 0.01,         # ≤1% of 20d avg dollar volume
    "LIQ_CAP_MIN1_PCT": 0.10,        # ≤10% of median 1-min $ vol, last 30min
    "CATASTROPHE_CAP_PCT": 0.15,     # notional ≤15% of equity
    "MAX_STOP_PCT": 0.08,            # structurally correct stop must be ≤8% away
    "DAILY_LOSS_LIMIT": 0.02,
    "WEEKLY_CIRCUIT": 0.05,
    "MAX_DAILY_ENTRIES": 4,

    # ── Section 4: scale-in ────────────────────────────────────────────────
    "SCALE_IN": False,

    # ── Section 5: hazards ─────────────────────────────────────────────────
    "REQUIRE_CATALYST": True,        # "none" grade is skipped outright
    "FLUFF_SIZE_MULT": 0.5,
    "HAZARD_BLOCK_424B5_DAYS": 5,    # fresh takedown → skip
    "HAZARD_ATM_SIZE_MULT": 0.5,
    "BLOCK_REVERSE_SPLIT_MONTHS": 6,
    "BLOCK_SERIAL_SPLITTER": True,
    "MAX_HALTS_20MIN": 1,            # 2 halts in 20min → no entry

    # ── Section 6: exits ───────────────────────────────────────────────────
    "SCALE1_R": 1.0, "SCALE1_FRAC": 0.34,
    "SCALE2_R": 2.0, "SCALE2_FRAC": 0.33,
    "BREAKEVEN_AFTER_SCALE1": True,
    "CLIMAX_ATR_MULT": 2.0,          # bar >2×ATR above 9EMA on an RVOL spike
    "TRAIL_ON": "ema9_close",        # runner trails 9EMA closes / 5m higher lows
    "HARD_TRAIL_FLOOR": "vwap",
    "TIME_STOP_MIN": 45,             # flat & heavy → cut
    "TIME_STOP_MAX_R": 0.3,          # "flat" means |open R| < this
    "MIDDAY_CUT_TIME": "11:30",      # cut to runner if still flat here
    "FLATTEN_AT": "15:45",

    # attempts rail (see module docstring) is not overridable
}

_INTENSE = {
    "key": "intense",
    "label": "Intense",
    "tagline": "Volatility-first. Buys the dips in a holding range, sells the stall for cents.",

    # ── Universe: volatility IS the filter ─────────────────────────────────
    # Market cap is a PROXY for how much a name moves, not a target in itself.
    # ~$100M is the sweet spot, so it's scored rather than gated: closer to
    # $100M scores higher, but a genuinely volatile $300M name still qualifies.
    "MCAP_IDEAL": 100e6,
    "MCAP_MIN": 25e6,
    "MCAP_MAX": 600e6,
    "MCAP_SOFT_LO": 75e6,
    "MCAP_SOFT_HI": 125e6,
    "OFF_IDEAL_SIZE_MULT": 0.75,     # outside the sweet spot, smaller — not banned

    # The volatility gates the old modes were missing entirely.
    "MIN_ATR_PCT": 0.012,            # 5-min ATR ≥1.2% of price
    "MIN_DAY_RANGE_PCT": 0.08,       # high-to-low ≥8% today
    "MAX_SPREAD_PCT": 0.015,         # wider than this and cents-scalping is a fee
    "MIN_DAY_CHANGE": 7.0,
    "PRICE_MIN": 1.00,
    "PRICE_MAX": 30.00,
    "FLOAT_MIN": 5e6,
    "FLOAT_MAX": 150e6,
    "RVOL_MIN": 3.0,
    "RVOL_MIN_AFTERNOON": 2.5,
    "DOLLAR_VOL_MIN": 5e6,
    "PROJ_DOLLAR_VOL_MIN": 15e6,
    "TOP_N_GAINERS": 30,

    # ── Setups: dips inside a range that is still holding ──────────────────
    "SETUPS": ["vwap_reclaim", "ema_pullback", "pdh_retest", "orb_retest",
               "hod_break", "flag"],
    "REQUIRE_RETEST": False,
    "MIN_CONFLUENCE_LEVELS": 1,
    "MAX_RETEST_DEPTH": 0.66,
    "MAX_PULLBACK_VOL_RATIO": 0.80,
    "MAX_RECLAIM_BARS": 5,
    "REQUIRE_ABOVE_VWAP": False,
    "MIN_SETUP_GRADE": 50,

    "ENTRY_WINDOWS": [("09:35", "15:20")],
    "OPEN_BLACKOUT_UNTIL": "09:35",
    "OPEN_SIZE_MULT": 0.4,
    "ALLOW_MIDDAY": True,
    "MIDDAY": ("11:30", "13:30"),
    "MIDDAY_SIZE_MULT": 0.7,

    # ── Sizing: 10–20% of capital is the FULL extended position ────────────
    # Reached by the adds, not by the first entry. Starting at 15% and adding
    # twice lands at ~38% of the account in one sub-$150M name; a single
    # halt-reopen at -35% takes ~13% off the account to chase a 2% gain.
    "R_PCT": 0.01,
    "MAX_POSITIONS": 2,              # fewer names, because each one is large
    "LIQ_CAP_ADV_PCT": 0.02,
    "LIQ_CAP_MIN1_PCT": 0.15,
    "CATASTROPHE_CAP_PCT": 0.20,     # hard ceiling on ONE name, adds included
    "MAX_STOP_PCT": 0.10,
    "DAILY_LOSS_LIMIT": 0.03,
    # No cap on entries. The -3% daily loss limit is the real backstop: it stops
    # the day on losses rather than on trade count, which is the number that
    # actually matters. A count cap would also halt a session that is going well.
    "MAX_DAILY_ENTRIES": None,
    "WEEKLY_CIRCUIT": 0.06,
    "ATR_STOP_MULT": 1.8,            # stop = 1.8x this name's own 5-min ATR

    # ── Adding to the position on dips ─────────────────────────────────────
    "SCALE_IN": True,
    "LADDER_TRANCHES": [0.38, 0.32, 0.30],
    "LADDER_LEVELS": ["trigger", "vwap", "pdh"],
    "LADDER_TARGET_EQUITY_PCT": 0.18,   # full extension ≈18% of equity
    "LADDER_MAX_TOTAL_R": 1.0,
    "LADDER_TIME_STOP_MIN": 45,
    "LADDER_ONE_RESCUE_PER_TICKER": False,   # this mode's whole point is the adds
    "LADDER_MAX_ADDS_PER_TICKER": 2,

    "REQUIRE_CATALYST": False,
    "FLUFF_SIZE_MULT": 0.85,
    "HAZARD_BLOCK_424B5_DAYS": 2,
    "HAZARD_ATM_SIZE_MULT": 0.75,
    "BLOCK_REVERSE_SPLIT_MONTHS": 3,
    "BLOCK_SERIAL_SPLITTER": True,
    "MAX_HALTS_20MIN": 2,

    # ── Exits: cents, taken quickly ────────────────────────────────────────
    # You cannot sell the peak, only the moment momentum stops confirming. The
    # stall detector is that moment: a bar that fails to make a new high while
    # volume is already falling away.
    "SCALE1_R": 0.5, "SCALE1_FRAC": 0.50,
    "SCALE2_R": 1.2, "SCALE2_FRAC": 0.25,
    "BREAKEVEN_AFTER_SCALE1": True,
    "STALL_EXIT": True,
    "STALL_LOOKBACK": 3,
    "CLIMAX_ATR_MULT": 2.0,
    "TRAIL_ON": "ema9_close",
    "HARD_TRAIL_FLOOR": "vwap",
    "TIME_STOP_MIN": 30,
    "TIME_STOP_MAX_R": 0.20,
    "MIDDAY_CUT_TIME": "14:00",
    "FLATTEN_AT": "15:50",
}

MODES = {"strict": _STRICT, "intense": _INTENSE}
# "aggro" was folded into "intense"; "core" remains a valid config value
# for the legacy engine but is no longer offered as a strategy choice.
LEGACY_MODE_ALIASES = {"aggro": "intense"}

# Rails — identical in every mode, deliberately not configurable.
MAX_ATTEMPTS_PER_TICKER = 2

# Pattern Day Trader floor. Below $25,000 equity a margin account is blocked
# from day trading entirely, which is worse than any single losing day: the
# strategy stops existing until the account is funded back up. This is broker
# rule, not strategy preference, so it applies to every mode.
PDT_MIN_EQUITY = float(os.environ.get("PDT_MIN_EQUITY", 25_000))
PDT_BUFFER = float(os.environ.get("PDT_BUFFER", 600))


def pdt_headroom(equity: float) -> dict:
    """How much the account can lose today before day trading is switched off.

    Returns the effective daily loss limit, which is the tighter of the mode's
    own limit and the distance to the PDT floor. An account at $26,000 has a
    $1,000 cushion; a 3% mode stop is $780, so two ordinary bad days would end
    the strategy. The floor takes precedence.
    """
    floor = PDT_MIN_EQUITY + PDT_BUFFER
    room = equity - floor
    return {
        "floor": floor,
        "room": room,
        "blocked": room <= 0,
        "max_loss_pct": max(room / equity, 0.0) if equity else 0.0,
        "applies": equity < PDT_MIN_EQUITY * 4,   # irrelevant on a large account
    }
NEVER_HOLD_OVERNIGHT = True
HARD_FLATTEN_LATEST = "15:55"


def get_mode(key: str) -> dict:
    """Resolve a mode key to its parameter dict. Unknown keys fall back to strict."""
    k = (key or "strict").lower()
    k = LEGACY_MODE_ALIASES.get(k, k)
    return MODES.get(k, _STRICT)


def mode_summary() -> list[dict]:
    """Compact descriptor list for the UI's mode picker."""
    out = []
    for k, m in MODES.items():
        out.append({
            "key": k,
            "label": m["label"],
            "tagline": m["tagline"],
            "risk_per_trade": m["R_PCT"],
            "max_positions": m["MAX_POSITIONS"],
            "daily_loss_limit": m["DAILY_LOSS_LIMIT"],
            "price_band": [m["PRICE_MIN"], m["PRICE_MAX"]],
            "float_band": [m["FLOAT_MIN"], m["FLOAT_MAX"]],
            "rvol_min": m["RVOL_MIN"],
            "scale_in": m["SCALE_IN"],
            "max_daily_entries": m.get("MAX_DAILY_ENTRIES"),
            "concentration": m.get("LADDER_TARGET_EQUITY_PCT") or m["CATASTROPHE_CAP_PCT"],
        })
    return out


# ═══════════════════════════════════════════════════════════════════════════
#  ENGINE ACCESS + SMALL UTILITIES
# ═══════════════════════════════════════════════════════════════════════════

def _t():
    """Lazy handle on trading.py (avoids a circular import at module load)."""
    import trading
    return trading


def _now_et() -> datetime:
    return datetime.now(ET)


def _hm(s: str) -> tuple[int, int]:
    h, m = s.split(":")
    return int(h), int(m)


def _at(now: datetime, s: str) -> datetime:
    h, m = _hm(s)
    return now.replace(hour=h, minute=m, second=0, microsecond=0)


def _in_window(now: datetime, windows) -> bool:
    for start, end in windows:
        if _at(now, start) <= now <= _at(now, end):
            return True
    return False


def _load_state() -> dict:
    try:
        if STATE_FILE.exists():
            st = json.loads(STATE_FILE.read_text())
            if st.get("date") == _now_et().strftime("%Y-%m-%d"):
                return st
    except Exception:
        pass
    return {"date": _now_et().strftime("%Y-%m-%d"), "attempts": {},
            "positions": {}, "stopped_out": [], "rescued": [], "halted_for_day": False}


def _save_state(st: dict):
    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps(st, indent=2))
    except Exception:
        pass


def _journal(entry: dict):
    """Append to the A/B log. Every entry, both modes, ladder flag included —
    this is the file Section 7.3's comparison eventually gets run against."""
    try:
        AB_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        rows = []
        if AB_LOG_FILE.exists():
            try:
                rows = json.loads(AB_LOG_FILE.read_text())
            except Exception:
                rows = []
        entry["ts"] = _now_et().isoformat()
        rows.append(entry)
        AB_LOG_FILE.write_text(json.dumps(rows[-2000:], indent=2))
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════════════════
#  MARKET DATA — Polygon aggregates
# ═══════════════════════════════════════════════════════════════════════════

def _pkey():
    return _t()._polygon_key()


def _aggs(ticker: str, mult: int, span: str, frm: str, to: str, limit: int = 50000):
    """Raw Polygon aggregate bars. Returns list of dicts with t/o/h/l/c/v."""
    key = _pkey()
    if not key:
        return None
    try:
        r = requests.get(
            f"https://api.polygon.io/v2/aggs/ticker/{ticker.upper()}/range/{mult}/{span}/{frm}/{to}",
            params={"apiKey": key, "adjusted": "true", "sort": "asc", "limit": limit},
            timeout=15,
        )
        if r.status_code != 200:
            return None
        return r.json().get("results") or None
    except Exception:
        return None



def feed_diagnostics() -> dict:
    """Probe the two market-wide endpoints and report what actually came back.

    polygon_gainers() and polygon_all_snapshots() both swallow every failure and
    return None, so an expired key, a plan that doesn't include snapshots, and a
    genuinely quiet market are indistinguishable — all three surface as
    "0 ranked". This says which one it was.
    """
    out = {"key_present": False, "gainers": {}, "snapshots": {}, "verdict": ""}
    key = _pkey()
    out["key_present"] = bool(key)
    if not key:
        out["verdict"] = "No Polygon API key on the backend — POLYGON_API_KEY is unset."
        return out

    base = "https://api.polygon.io/v2/snapshot/locale/us/markets/stocks"
    for name, url in (("gainers", f"{base}/gainers"), ("snapshots", f"{base}/tickers")):
        info = {"status": None, "count": 0, "error": ""}
        try:
            r = requests.get(url, params={"apiKey": key, "include_otc": "false"}, timeout=15)
            info["status"] = r.status_code
            if r.status_code == 200:
                info["count"] = len(r.json().get("tickers", []))
            else:
                body = (r.text or "")[:160]
                info["error"] = body
        except Exception as e:
            info["error"] = str(e)[:160]
        out[name] = info

    g, sn = out["gainers"], out["snapshots"]
    if g.get("status") in (401, 403) or sn.get("status") in (401, 403):
        out["verdict"] = ("Polygon rejected the request (401/403). The snapshot endpoints "
                          "aren't on the current plan, or the key is invalid. This scan "
                          "cannot see the market until that's resolved.")
    elif g.get("status") == 429 or sn.get("status") == 429:
        out["verdict"] = "Polygon rate-limited the request (429) — too many calls per minute."
    elif (g.get("count") or 0) == 0 and (sn.get("count") or 0) == 0:
        out["verdict"] = "Endpoints answered 200 but returned no tickers — market closed or feed empty."
    else:
        out["verdict"] = (f"Feed OK — gainers {g.get('count')}, snapshots {sn.get('count')}. "
                          f"An empty pool after this is a filter result, not a data failure.")
    return out


def _bars_today(ticker: str, mult: int = 1, span: str = "minute", back_days: int = 0):
    """Today's bars (including premarket), oldest first, as (dt_et, o,h,l,c,v)."""
    now = _now_et()
    start = (now - timedelta(days=back_days)).strftime("%Y-%m-%d")
    raw = _aggs(ticker, mult, span, start, now.strftime("%Y-%m-%d"))
    if not raw:
        return []
    out = []
    for b in raw:
        dt = datetime.fromtimestamp(b["t"] / 1000, tz=timezone.utc).astimezone(ET)
        out.append((dt, b.get("o", 0), b.get("h", 0), b.get("l", 0), b.get("c", 0), b.get("v", 0)))
    return out


def _session_only(bars, day: datetime | None = None):
    """Regular-hours bars (09:30–16:00 ET) for a given day."""
    day = day or _now_et()
    d = day.date()
    return [b for b in bars
            if b[0].date() == d and (b[0].hour, b[0].minute) >= (9, 30) and b[0].hour < 16]


def _premarket_high(bars, day: datetime | None = None):
    day = day or _now_et()
    d = day.date()
    pm = [b for b in bars if b[0].date() == d and (b[0].hour, b[0].minute) < (9, 30)]
    return max((b[2] for b in pm), default=None)


def _vwap(bars):
    """Session VWAP from regular-hours bars."""
    pv = v = 0.0
    for b in bars:
        typical = (b[2] + b[3] + b[4]) / 3.0
        pv += typical * b[5]
        v += b[5]
    return (pv / v) if v else None


def _ema(vals, period):
    if not vals or len(vals) < period:
        return None
    k = 2.0 / (period + 1)
    e = sum(vals[:period]) / period
    for x in vals[period:]:
        e = x * k + e * (1 - k)
    return e


def _ema_series(vals, period):
    if not vals or len(vals) < period:
        return []
    k = 2.0 / (period + 1)
    e = sum(vals[:period]) / period
    out = [None] * (period - 1) + [e]
    for x in vals[period:]:
        e = x * k + e * (1 - k)
        out.append(e)
    return out


def _atr(bars, period=14):
    if len(bars) < period + 1:
        return None
    trs = []
    for i in range(1, len(bars)):
        h, l, pc = bars[i][2], bars[i][3], bars[i - 1][4]
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    if len(trs) < period:
        return None
    return sum(trs[-period:]) / period


def _prev_day(ticker: str):
    """Prior session OHLCV — for PDH/PDL and the gap reference."""
    key = _pkey()
    if not key:
        return None
    try:
        r = requests.get(f"https://api.polygon.io/v2/aggs/ticker/{ticker.upper()}/prev",
                         params={"apiKey": key, "adjusted": "true"}, timeout=10)
        if r.status_code != 200:
            return None
        res = (r.json().get("results") or [None])[0]
        return res
    except Exception:
        return None


def _avg_dollar_volume_20d(ticker: str):
    to = _now_et().strftime("%Y-%m-%d")
    frm = (_now_et() - timedelta(days=40)).strftime("%Y-%m-%d")
    raw = _aggs(ticker, 1, "day", frm, to, limit=60)
    if not raw or len(raw) < 5:
        return None
    rows = raw[-21:-1] if len(raw) > 21 else raw[:-1]
    if not rows:
        return None
    return sum((b.get("vw") or b.get("c", 0)) * b.get("v", 0) for b in rows) / len(rows)


# ═══════════════════════════════════════════════════════════════════════════
#  SECTION 1 FILTERS — RVOL, float, dollar volume, hazards
# ═══════════════════════════════════════════════════════════════════════════

def time_adjusted_rvol(ticker: str, now: datetime | None = None) -> float | None:
    """Today's cumulative session volume ÷ the 20-day average cumulative volume
    *at the same clock time*.

    Naive RVOL (today ÷ full-day average) reads ~0.3 at 09:45 on a name doing
    five times its normal business, which is exactly backwards. This walks each
    of the last 20 sessions' minute bars up to the current time of day and
    averages those partial sums instead.
    """
    now = now or _now_et()
    cutoff = (now.hour, now.minute)
    bars = _bars_today(ticker, 1, "minute", back_days=0)
    today = [b for b in _session_only(bars, now) if (b[0].hour, b[0].minute) <= cutoff]
    if not today:
        return None
    today_vol = sum(b[5] for b in today)

    frm = (now - timedelta(days=40)).strftime("%Y-%m-%d")
    to = (now - timedelta(days=1)).strftime("%Y-%m-%d")
    raw = _aggs(ticker, 1, "minute", frm, to)
    if not raw:
        return None

    by_day: dict = {}
    for b in raw:
        dt = datetime.fromtimestamp(b["t"] / 1000, tz=timezone.utc).astimezone(ET)
        if (dt.hour, dt.minute) < (9, 30) or dt.hour >= 16:
            continue
        if (dt.hour, dt.minute) > cutoff:
            continue
        by_day[dt.date()] = by_day.get(dt.date(), 0) + b.get("v", 0)

    days = sorted(by_day.values(), reverse=False)[-20:]
    if not days:
        return None
    avg = sum(days) / len(days)
    return round(today_vol / avg, 2) if avg else None


def dollar_volume_today(ticker: str, now: datetime | None = None):
    """(traded so far, projected full day) in dollars."""
    now = now or _now_et()
    bars = _session_only(_bars_today(ticker, 1, "minute"), now)
    if not bars:
        return (None, None)
    traded = sum(((b[2] + b[3] + b[4]) / 3.0) * b[5] for b in bars)
    open_dt = _at(now, "09:30")
    elapsed = max((now - open_dt).total_seconds() / 60.0, 1.0)
    total_min = 390.0
    # Volume is front-loaded; a linear projection overstates the afternoon.
    # Damp it: assume the remaining session trades at ~55% of the morning rate.
    remaining = max(total_min - elapsed, 0)
    projected = traded + (traded / elapsed) * remaining * 0.55
    return (traded, projected)


def median_1min_dollar_volume(ticker: str, minutes: int = 30):
    bars = _session_only(_bars_today(ticker, 1, "minute"))[-minutes:]
    if not bars:
        return None
    vals = sorted(((b[2] + b[3] + b[4]) / 3.0) * b[5] for b in bars)
    n = len(vals)
    return vals[n // 2] if n % 2 else (vals[n // 2 - 1] + vals[n // 2]) / 2


def float_and_cap(ticker: str):
    """(float_shares, market_cap). yfinance first, Polygon reference as backup.

    Note: this is *today's* float. The doc is right that point-in-time float is
    what a backtest needs — for live trading today's number is the correct one,
    but any backtest built on this function is lying to you.
    """
    flt = cap = None
    try:
        import yfinance as yf
        info = yf.Ticker(ticker).get_info()
        flt = info.get("floatShares")
        cap = info.get("marketCap")
    except Exception:
        pass
    if flt and cap:
        return (float(flt), float(cap))
    key = _pkey()
    if key:
        try:
            r = requests.get(f"https://api.polygon.io/v3/reference/tickers/{ticker.upper()}",
                             params={"apiKey": key}, timeout=10)
            if r.status_code == 200:
                res = r.json().get("results", {})
                cap = cap or res.get("market_cap")
                flt = flt or res.get("weighted_shares_outstanding") or res.get("share_class_shares_outstanding")
        except Exception:
            pass
    return (float(flt) if flt else None, float(cap) if cap else None)


_CIK_CACHE: dict = {}


def _cik_for(ticker: str):
    global _CIK_CACHE
    if not _CIK_CACHE:
        try:
            r = requests.get("https://www.sec.gov/files/company_tickers.json",
                             headers={"User-Agent": SEC_UA}, timeout=15)
            if r.status_code == 200:
                for row in r.json().values():
                    _CIK_CACHE[row["ticker"].upper()] = str(row["cik_str"]).zfill(10)
        except Exception:
            return None
    return _CIK_CACHE.get(ticker.upper())


def filings_hazard(ticker: str) -> dict:
    """Section 5.1/5.2 hazard grade from SEC EDGAR.

    Returns dilution/split flags with day counts. This is a *grade*, not an
    automatic exclusion — the caller decides whether to skip or halve size.
    A spike in a name with an active ATM is, from the CFO's chair, a financing
    window, and that is the single most common way these trades die.
    """
    out = {"ok": True, "days_since_424b5": None, "s3_shelf": False, "atm": False,
           "recent_s1": False, "reverse_split_months": None, "serial_splitter": False,
           "flags": []}
    cik = _cik_for(ticker)
    if not cik:
        out["ok"] = False
        return out
    try:
        r = requests.get(f"https://data.sec.gov/submissions/CIK{cik}.json",
                         headers={"User-Agent": SEC_UA}, timeout=15)
        if r.status_code != 200:
            out["ok"] = False
            return out
        recent = r.json().get("filings", {}).get("recent", {})
        forms = recent.get("form", [])
        dates = recent.get("filingDate", [])
        today = _now_et().date()
        for form, d in zip(forms, dates):
            try:
                fd = datetime.strptime(d, "%Y-%m-%d").date()
            except Exception:
                continue
            age = (today - fd).days
            if age > 400:
                break
            f = (form or "").upper()
            if f.startswith("424B5") and (out["days_since_424b5"] is None or age < out["days_since_424b5"]):
                out["days_since_424b5"] = age
            if f.startswith("S-3") and age <= 400:
                out["s3_shelf"] = True
            if f.startswith("S-1") and age <= 120:
                out["recent_s1"] = True
            if f in ("8-K", "10-Q") and age <= 120:
                pass  # ATM disclosure lives in the body; see below
        if out["days_since_424b5"] is not None and out["days_since_424b5"] <= 30:
            out["flags"].append(f"424B5 takedown {out['days_since_424b5']}d ago")
        if out["s3_shelf"]:
            out["flags"].append("effective S-3 shelf")
        if out["recent_s1"]:
            out["flags"].append("fresh S-1")
    except Exception:
        out["ok"] = False

    # Reverse splits — Polygon carries the corporate action feed.
    key = _pkey()
    if key:
        try:
            r = requests.get("https://api.polygon.io/v3/reference/splits",
                             params={"ticker": ticker.upper(), "apiKey": key, "limit": 10},
                             timeout=10)
            if r.status_code == 200:
                splits = r.json().get("results", [])
                rev = []
                for s in splits:
                    # reverse split: split_from > split_to (e.g. 10 → 1)
                    if s.get("split_from", 1) > s.get("split_to", 1):
                        rev.append(s.get("execution_date"))
                if rev:
                    try:
                        newest = max(datetime.strptime(d, "%Y-%m-%d").date() for d in rev if d)
                        out["reverse_split_months"] = (_now_et().date() - newest).days / 30.0
                        if out["reverse_split_months"] <= 12:
                            out["flags"].append(f"reverse split {out['reverse_split_months']:.0f}mo ago")
                    except Exception:
                        pass
                    if len(rev) >= 2:
                        out["serial_splitter"] = True
                        out["flags"].append(f"serial reverse-splitter ({len(rev)}x)")
        except Exception:
            pass
    return out


def catalyst_grade(ticker: str) -> dict:
    """Section 1 catalyst triage: real / fluff / none, via Groq over the PR text.

    'Real' means a verifiable economic event — an earnings beat, an FDA action,
    a contract with a dollar figure, a named strategic investor. 'Fluff' is an
    LOI, 'exploring strategic alternatives', or a buzzword pivot. 'None' means
    you can't identify the catalyst, which per Section 5.4 means you *are* it.
    """
    out = {"grade": "none", "reason": "", "headline": ""}
    try:
        news = _t()._news_sentiment(ticker) or {}
        heads = news.get("headlines", [])[:8]
        if not heads:
            return out
        out["headline"] = heads[0].get("title", "")[:140]
        key = os.environ.get("GROQ_API_KEY", "")
        if not key:
            return {**out, "grade": "unknown"}
        from groq import Groq
        client = Groq(api_key=key)
        text = "\n".join(f"- {h.get('title','')} ({h.get('publisher','')})" for h in heads)
        resp = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            max_tokens=120,
            temperature=0,
            messages=[{"role": "user", "content": f"""Classify today's catalyst for the small-cap stock {ticker}. Answer in EXACTLY this format:

GRADE: [REAL or FLUFF or NONE]
REASON: [one short sentence]

REAL = earnings beat, FDA/regulatory action, contract or order with a stated dollar figure, named strategic investor, completed acquisition, major partnership with terms.
FLUFF = letter of intent, MOU, "exploring strategic alternatives", buzzword pivot (AI/quantum/crypto) with no economics, conference presentation, patent filing, name change.
NONE = no company-specific news; sympathy move, promotion, or unexplained.

Headlines:
{text}"""}],
        )
        body = resp.choices[0].message.content.strip()
        for line in body.split("\n"):
            ls = line.strip()
            if ls.upper().startswith("GRADE:"):
                g = ls.split(":", 1)[1].strip().upper()
                out["grade"] = {"REAL": "real", "FLUFF": "fluff", "NONE": "none"}.get(g, "none")
            elif ls.upper().startswith("REASON:"):
                out["reason"] = ls.split(":", 1)[1].strip()[:160]
    except Exception:
        out["grade"] = "unknown"
    return out


def halt_count_recent(ticker: str, minutes: int = 20) -> int:
    """Approximate recent LULD halts by looking for minute-bar gaps in an
    otherwise active tape. Polygon doesn't hand us a halt feed on most plans,
    and a name that has already halted twice in twenty minutes is a coin flip
    between a fill and a lockup — worth approximating rather than ignoring."""
    bars = _session_only(_bars_today(ticker, 1, "minute"))
    if len(bars) < 5:
        return 0
    recent = bars[-(minutes + 6):]
    holes = 0
    for i in range(1, len(recent)):
        gap = (recent[i][0] - recent[i - 1][0]).total_seconds() / 60.0
        if gap >= 4:  # LULD pauses are 5 minutes
            holes += 1
    return holes



# ═══════════════════════════════════════════════════════════════════════════
#  VOLATILITY PROFILE  —  the thing the system implicitly assumed but never checked
# ═══════════════════════════════════════════════════════════════════════════

def volatility_profile(ctx: dict, mode: dict) -> dict:
    """Is this name moving enough to be worth trading today?

    Every setup here is a bet on continued movement. A name that gapped and then
    went quiet produces textbook-looking retests that go nowhere, and no price
    filter catches it — the chart looks identical to a live one until you're in.
    """
    out = {"ok": True, "atr_pct": None, "range_pct": None, "spread_pct": None,
           "notes": [], "reason": ""}
    b1, b5, px = ctx.get("bars1") or [], ctx.get("bars5") or [], ctx.get("price") or 0
    if not b1 or not px:
        out["ok"] = False
        out["reason"] = "no intraday data"
        return out

    atr = ctx.get("atr5")
    if atr:
        out["atr_pct"] = round(atr / px, 4)
    hi = max(b[2] for b in b1)
    lo = min(b[3] for b in b1)
    out["range_pct"] = round((hi - lo) / px, 4) if px else None

    # Spread proxy: the QUIET minutes, not the median one. A real quote spread
    # isn't on most plans. Using the median bar range conflates spread with
    # movement — a fast name prints wide bars because it's travelling, which is
    # the reason to trade it, not a reason to skip it. The low percentile of the
    # last 20 bars isolates the minutes where little happened, and in those the
    # bar range is mostly the spread.
    recent = b1[-20:]
    if recent:
        ranges = sorted((b[2] - b[3]) / px for b in recent if px)
        out["spread_pct"] = round(ranges[max(0, int(len(ranges) * 0.25) - 1)], 4)

    if mode.get("MIN_ATR_PCT") and (out["atr_pct"] or 0) < mode["MIN_ATR_PCT"]:
        out["ok"] = False
        out["reason"] = (f"ATR {(out['atr_pct'] or 0):.1%} of price — under "
                         f"{mode['MIN_ATR_PCT']:.1%}, not moving enough to pay for the risk")
        return out
    if mode.get("MIN_DAY_RANGE_PCT") and (out["range_pct"] or 0) < mode["MIN_DAY_RANGE_PCT"]:
        out["ok"] = False
        out["reason"] = f"day range {(out['range_pct'] or 0):.1%} — gapped then went quiet"
        return out
    if mode.get("MAX_SPREAD_PCT") and (out["spread_pct"] or 0) > mode["MAX_SPREAD_PCT"]:
        out["ok"] = False
        out["reason"] = (f"~{(out['spread_pct'] or 0):.1%} spread — a few cents of edge "
                         f"is smaller than the round trip")
        return out

    out["notes"].append(f"ATR {(out['atr_pct'] or 0):.1%}/bar, {(out['range_pct'] or 0):.0%} day range")
    return out


def cap_fit(cap, mode: dict) -> tuple[bool, float, str]:
    """Market cap as a volatility PRIOR, not a hard target.

    ~$100M is where the movement tends to live, so names in the sweet spot trade
    at full size and names outside it trade smaller rather than not at all. A
    genuinely volatile $300M name is a better trade than a dead $100M one.
    """
    lo, hi = mode.get("MCAP_MIN"), mode.get("MCAP_MAX")
    if not cap:
        return True, 1.0, ""                    # unknown cap isn't disqualifying
    if lo and cap < lo:
        return False, 0.0, f"cap ${cap/1e6:.0f}M below ${lo/1e6:.0f}M floor"
    if hi and cap > hi:
        return False, 0.0, f"cap ${cap/1e6:.0f}M above ${hi/1e6:.0f}M ceiling"
    slo, shi = mode.get("MCAP_SOFT_LO"), mode.get("MCAP_SOFT_HI")
    if slo and shi and not (slo <= cap <= shi):
        return True, mode.get("OFF_IDEAL_SIZE_MULT", 0.75), \
            f"cap ${cap/1e6:.0f}M outside the ${slo/1e6:.0f}–{shi/1e6:.0f}M sweet spot"
    return True, 1.0, ""


def momentum_stalled(bars5, lookback: int = 3) -> bool:
    """The sell signal for a cents-scalp.

    You can't sell the peak — the peak is only identifiable afterwards. What is
    identifiable live is the moment momentum stops confirming: consecutive bars
    that fail to take out the prior high while volume is already receding. That
    is the exit, and taking it means routinely selling before the actual top.
    """
    if len(bars5) < lookback + 3:
        return False
    recent = bars5[-lookback:]
    prior_high = max(b[2] for b in bars5[-(lookback + 3):-lookback])
    no_new_high = all(b[2] <= prior_high for b in recent)
    prior_vol = sum(b[5] for b in bars5[-(lookback + 3):-lookback]) / 3
    recent_vol = sum(b[5] for b in recent) / len(recent)
    fading = recent_vol < prior_vol * 0.85 if prior_vol else False
    return bool(no_new_high and fading)


def atr_stop(entry: float, ctx: dict, mode: dict, structural_stop: float) -> float:
    """Stop distance scaled to THIS name's volatility, floored by structure.

    A flat percentage judges a 12%-ATR name and a 3%-ATR name identically, so the
    quiet one gets stopped by noise and the wild one gets a stop that means
    nothing. Structure still wins when it's tighter than the ATR band.
    """
    mult = mode.get("ATR_STOP_MULT")
    atr = ctx.get("atr5")
    if not mult or not atr:
        return structural_stop
    return max(min(structural_stop, entry - mult * atr), entry * (1 - mode["MAX_STOP_PCT"]))


# ═══════════════════════════════════════════════════════════════════════════
#  SECTION 2 — SETUP DETECTION
# ═══════════════════════════════════════════════════════════════════════════

def _confluence_levels(price, ctx, tol=0.008):
    """Which reference levels sit within tolerance of `price`. A level is only
    tradable when at least two of these agree (Section 2)."""
    hits = []
    for name, lvl in (("vwap", ctx.get("vwap")), ("pdh", ctx.get("pdh")),
                      ("pmh", ctx.get("pmh")), ("orh", ctx.get("orh")),
                      ("hvn", ctx.get("hvn"))):
        if lvl and abs(price - lvl) / price <= tol:
            hits.append(name)
    # whole / half dollar
    frac = price - math.floor(price)
    if min(frac, abs(frac - 0.5), 1 - frac) <= max(price * tol, 0.02):
        hits.append("round")
    return hits


def _retest_quality(bars5, level, ctx, mode) -> dict:
    """Grade a retest 0–100 on the doc's five checks: depth, volume signature,
    speed, location, and (proxied) tape. Volume signature carries the most
    weight because it is the single best real-vs-fake tell."""
    g = {"grade": 0, "notes": [], "depth": None, "vol_ratio": None, "bars_to_reclaim": None}
    if len(bars5) < 8:
        return g

    # Impulse leg = run from the recent swing low to the recent high before the pullback
    highs = [b[2] for b in bars5]
    lows = [b[3] for b in bars5]
    closes = [b[4] for b in bars5]
    vols = [b[5] for b in bars5]

    hi_i = max(range(len(highs) - 1), key=lambda i: highs[i]) if len(highs) > 2 else 0
    lookback = bars5[max(0, hi_i - 8):hi_i + 1]
    if len(lookback) < 3:
        return g
    leg_low = min(b[3] for b in lookback)
    leg_high = highs[hi_i]
    impulse = leg_high - leg_low
    if impulse <= 0:
        return g

    pull = bars5[hi_i + 1:]
    if not pull:
        return g
    pull_low = min(b[3] for b in pull)
    depth = (leg_high - pull_low) / impulse
    g["depth"] = round(depth, 2)

    imp_vol = sum(b[5] for b in lookback) / max(len(lookback), 1)
    pull_vol = sum(b[5] for b in pull) / max(len(pull), 1)
    vr = (pull_vol / imp_vol) if imp_vol else 1.0
    g["vol_ratio"] = round(vr, 2)

    bars_since = len(pull)
    g["bars_to_reclaim"] = bars_since

    score = 0
    # depth (25)
    if depth <= 0.33:
        score += 25; g["notes"].append(f"shallow pullback ({depth:.0%} of leg)")
    elif depth <= mode["MAX_RETEST_DEPTH"]:
        score += 15; g["notes"].append(f"pullback {depth:.0%} of leg")
    else:
        g["notes"].append(f"deep pullback ({depth:.0%}) — weak")

    # volume signature (35) — the money check
    if vr <= 0.35:
        score += 35; g["notes"].append(f"volume dried up ({vr:.2f}x impulse)")
    elif vr <= mode["MAX_PULLBACK_VOL_RATIO"]:
        score += 22; g["notes"].append(f"volume contracting ({vr:.2f}x)")
    elif vr <= 1.0:
        score += 8; g["notes"].append(f"volume flat into pullback ({vr:.2f}x)")
    else:
        g["notes"].append(f"pullback volume EXCEEDS impulse ({vr:.2f}x) — distribution")

    # speed (15)
    if bars_since <= mode["MAX_RECLAIM_BARS"]:
        score += 15; g["notes"].append(f"reclaim in {bars_since} bars")
    else:
        g["notes"].append(f"grinding at level ({bars_since} bars)")

    # location (15)
    vwap = ctx.get("vwap")
    if vwap and closes[-1] > vwap:
        score += 15; g["notes"].append("structure above VWAP")
    elif mode["REQUIRE_ABOVE_VWAP"]:
        g["notes"].append("below VWAP — invalid for longs")

    # confluence at the level (10)
    conf = _confluence_levels(level, ctx)
    if len(conf) >= 2:
        score += 10; g["notes"].append("confluent level: " + "+".join(conf))
    elif conf:
        score += 4; g["notes"].append("single level: " + conf[0])

    g["grade"] = min(score, 100)
    g["confluence"] = conf
    return g


def _failed_test(bars5, level) -> bool:
    """The universal failed-test tell: the level breaks on EXPANDING volume,
    bounces can't reclaim within 2–3 bars, and lower highs stack beneath it.
    This is the exact condition under which averaging down buys more."""
    if len(bars5) < 6:
        return False
    recent = bars5[-4:]
    below = [b for b in recent if b[4] < level]
    if len(below) < 3:
        return False
    prior_vol = sum(b[5] for b in bars5[-8:-4]) / 4 if len(bars5) >= 8 else 0
    break_vol = sum(b[5] for b in recent) / len(recent)
    expanding = break_vol > prior_vol * 1.1 if prior_vol else False
    lower_highs = recent[-1][2] < recent[-2][2] < recent[-3][2]
    return bool(expanding and (lower_highs or len(below) == 4))


def build_context(ticker: str, now: datetime | None = None) -> dict | None:
    """Everything the setup detectors need: bars, VWAP, EMAs, ATR, key levels."""
    now = now or _now_et()
    b1 = _bars_today(ticker, 1, "minute")
    if not b1:
        return None
    sess1 = _session_only(b1, now)
    if len(sess1) < 10:
        return None
    b5 = _bars_today(ticker, 5, "minute")
    sess5 = _session_only(b5, now)
    if len(sess5) < 6:
        return None

    closes5 = [b[4] for b in sess5]
    ema9 = _ema_series(closes5, 9)
    ema20 = _ema_series(closes5, 20)
    prev = _prev_day(ticker) or {}
    or_bars = [b for b in sess1 if (b[0].hour, b[0].minute) < (9, 45)]

    # High-volume node: price of the highest-volume 5-min bar so far
    hvn = max(sess5, key=lambda b: b[5])[4] if sess5 else None

    return {
        "ticker": ticker,
        "price": sess1[-1][4],
        "bars1": sess1,
        "bars5": sess5,
        "vwap": _vwap(sess1),
        "ema9": ema9[-1] if ema9 else None,
        "ema20": ema20[-1] if ema20 else None,
        "ema9_series": ema9,
        "ema20_series": ema20,
        "atr5": _atr(sess5, 14),
        "pdh": prev.get("h"),
        "pdl": prev.get("l"),
        "prev_close": prev.get("c"),
        "pmh": _premarket_high(b1, now),
        "orh": max((b[2] for b in or_bars), default=None),
        "orl": min((b[3] for b in or_bars), default=None),
        "hod": max(b[2] for b in sess1),
        "hvn": hvn,
        "now": now,
    }


def detect_setups(ctx: dict, mode: dict) -> list[dict]:
    """Run all six Section 2 detectors. Returns candidate setups, best first.

    Every returned setup carries entry, stop, the grade breakdown, and a
    human-readable 'why' — no setup fires without a structural stop, because a
    setup without an invalidation level is not a setup.
    """
    out = []
    b5, b1 = ctx["bars5"], ctx["bars1"]
    price = ctx["price"]
    vwap, ema9, ema20, atr = ctx["vwap"], ctx["ema9"], ctx["ema20"], ctx["atr5"]
    closes5 = [b[4] for b in b5]

    def add(name, level, entry, stop, why):
        if not entry or not stop or stop >= entry:
            return
        q = _retest_quality(b5, level, ctx, mode)
        if _failed_test(b5, level):
            return  # the level is failing, not holding — this is a short setup, not a discount
        if mode["REQUIRE_ABOVE_VWAP"] and vwap and price < vwap:
            return
        if len(q.get("confluence", [])) < mode["MIN_CONFLUENCE_LEVELS"]:
            return
        if q["grade"] < mode["MIN_SETUP_GRADE"]:
            return
        out.append({
            "setup": name, "level": round(level, 2), "entry": round(entry, 2),
            "stop": round(stop, 2), "grade": q["grade"], "quality": q,
            "why": why, "notes": q["notes"],
        })

    # 2.1 VWAP reclaim — entered on the retest from above, not the first poke
    if "vwap_reclaim" in mode["SETUPS"] and vwap and atr:
        below = [c for c in closes5[-12:-1] if c < vwap]
        if len(below) >= 4 and closes5[-1] > vwap and price > vwap:
            swing_low = min(b[3] for b in b5[-4:])
            stop = max(swing_low, vwap - 1.5 * atr)
            add("VWAP reclaim", vwap, price, min(stop, price * 0.995),
                "lost VWAP, curled back, holding the retest from above")

    # 2.2 First pullback to a rising 9/20 EMA — the bread-and-butter setup
    if "ema_pullback" in mode["SETUPS"] and ema9 and ema20 and len(b5) >= 12:
        rising = ctx["ema9_series"][-1] and ctx["ema9_series"][-4] and ctx["ema9_series"][-1] > ctx["ema9_series"][-4]
        touched9 = any(b[3] <= ema9 * 1.004 for b in b5[-3:])
        touched20 = any(b[3] <= ema20 * 1.004 for b in b5[-3:])
        broke_prior_high = b5[-1][4] > b5[-2][2]
        if rising and (touched9 or touched20) and broke_prior_high:
            level = ema9 if touched9 else ema20
            stop = min(b[3] for b in b5[-3:]) * 0.998
            add("9/20 EMA pullback", level, price, stop,
                "first rest after the impulse leg, EMA holding, prior bar's high taken")

    # 2.3 Prior-day-high retest — the S/R flip is the whole thesis
    if "pdh_retest" in mode["SETUPS"] and ctx["pdh"]:
        pdh = ctx["pdh"]
        if price > pdh and (price - pdh) / pdh < 0.05:
            recent_low = min(b[3] for b in b5[-4:])
            if recent_low <= pdh * 1.008:
                add("PDH retest", pdh, price, pdh * 0.985,
                    "broke yesterday's high, came back and held the flip")

    # 2.4 Opening-range break + retest
    if "orb_retest" in mode["SETUPS"] and ctx["orh"] and ctx["orl"]:
        orh, orl = ctx["orh"], ctx["orl"]
        mid = (orh + orl) / 2
        if price > orh:
            pulled_back = min(b[3] for b in b5[-4:]) <= orh * 1.008
            if pulled_back or not mode["REQUIRE_RETEST"]:
                stop = mid if (price - mid) / price < 0.08 else orh * 0.985
                if (price - stop) / price <= mode["MAX_STOP_PCT"]:
                    add("OR break + retest", orh, price, stop,
                        "opening range taken out, holding above on the retest")

    # 2.5 High-of-day break — most likely to fill you seconds before a halt
    if "hod_break" in mode["SETUPS"] and ctx["hod"]:
        hod = ctx["hod"]
        base = b5[-4:-1]
        if len(base) == 3:
            base_high = max(b[2] for b in base)
            base_low = min(b[3] for b in base)
            tight = (base_high - base_low) / price < 0.04
            if tight and price >= base_high * 0.999:
                if mode["REQUIRE_RETEST"] and price > hod * 1.002:
                    pass  # chasing the break itself — skip in strict
                else:
                    add("HOD break", base_high, price, base_low * 0.997,
                        "ledge under the high held for 15+ minutes, breaking on expanding volume")

    # 2.6 Flag on declining volume — the volume taper IS the setup
    if "flag" in mode["SETUPS"] and len(b5) >= 10:
        flag = b5[-6:-1]
        vols = [b[5] for b in flag]
        tapering = all(vols[i] >= vols[i + 1] * 0.85 for i in range(len(vols) - 1))
        above = all(b[4] > (ema20 or 0) and b[4] > (vwap or 0) for b in flag)
        flag_high = max(b[2] for b in flag)
        flag_low = min(b[3] for b in flag)
        if tapering and above and price > flag_high:
            add("Flag breakout", flag_high, price, flag_low * 0.997,
                "pole then a drift on shrinking volume, holding above VWAP and the 20EMA")

    out.sort(key=lambda s: -s["grade"])
    return out


# ═══════════════════════════════════════════════════════════════════════════
#  SECTION 3 — POSITION SIZING
# ═══════════════════════════════════════════════════════════════════════════

def size_position(equity, entry, stop, mode, ticker, adv=None, med1=None,
                  size_mult=1.0) -> dict:
    """Fixed-fractional base size, then the minimum of three caps.

    The catastrophe cap is the one that matters: stops are a fiction through
    halts and gaps, so notional is capped independently of what the stop math
    allows. A −40% reopen on a capped position is survivable; on an uncapped
    one it isn't.
    """
    res = {"qty": 0, "reason": "", "caps": {}}
    risk_per_share = entry - stop
    if risk_per_share <= 0:
        res["reason"] = "non-positive risk per share"
        return res

    stop_pct = risk_per_share / entry
    if stop_pct > mode["MAX_STOP_PCT"]:
        res["reason"] = f"stop {stop_pct:.1%} away — wider than {mode['MAX_STOP_PCT']:.0%}, setup doesn't fit"
        return res

    r_dollars = equity * mode["R_PCT"] * size_mult
    base = math.floor(r_dollars / risk_per_share)
    res["caps"]["base"] = base

    caps = [base]
    if adv:
        c = math.floor((adv * mode["LIQ_CAP_ADV_PCT"]) / entry)
        res["caps"]["adv"] = c
        caps.append(c)
    if med1:
        c = math.floor((med1 * mode["LIQ_CAP_MIN1_PCT"]) / entry)
        res["caps"]["min1"] = c
        caps.append(c)
    c = math.floor((equity * mode["CATASTROPHE_CAP_PCT"]) / entry)
    res["caps"]["catastrophe"] = c
    caps.append(c)

    qty = max(0, min(caps))
    res["qty"] = qty
    res["risk_per_share"] = round(risk_per_share, 4)
    res["r_dollars"] = round(r_dollars, 2)
    res["stop_pct"] = round(stop_pct, 4)
    binding = min(res["caps"], key=lambda k: res["caps"][k])
    res["binding_cap"] = binding
    if qty < 1:
        res["reason"] = f"size rounds to zero under the {binding} cap"
    return res


def plan_ladder(entry, stop, ctx, equity, mode, adv=None, med1=None) -> dict | None:
    """Section 4.4 — the only sanctioned scale-in.

    The whole ladder is written before the first fill: three tranches at levels
    that already exist on the chart (trigger, VWAP, PDH), a final hard stop
    below the last structural level, and total risk on the FULL size at the
    AVERAGE price down to that final stop equal to one normal R. If the math
    demands more than 1R, the tranches shrink — the stop does not move.
    """
    if not mode.get("SCALE_IN"):
        return None
    levels = []
    for name in mode["LADDER_LEVELS"]:
        lvl = {"trigger": entry, "vwap": ctx.get("vwap"), "pdh": ctx.get("pdh")}.get(name)
        if lvl and lvl < entry * 1.001:
            levels.append((name, float(lvl)))
    # de-duplicate and order high → low; entry is always tranche 1
    seen, ordered = set(), []
    for name, lvl in sorted(levels, key=lambda x: -x[1]):
        k = round(lvl, 2)
        if k not in seen:
            seen.add(k)
            ordered.append((name, lvl))
    if len(ordered) < 2:
        return None
    ordered = ordered[:len(mode["LADDER_TRANCHES"])]

    final_stop = min(min(l for _, l in ordered), stop) * 0.985
    fracs = mode["LADDER_TRANCHES"][:len(ordered)]
    fsum = sum(fracs)
    fracs = [f / fsum for f in fracs]

    avg_price = sum(f * l for f, (_, l) in zip(fracs, ordered))
    risk_per_share_full = avg_price - final_stop
    if risk_per_share_full <= 0:
        return None
    if (avg_price - final_stop) / avg_price > mode["MAX_STOP_PCT"] * 1.5:
        return None

    r_dollars = equity * mode["R_PCT"]
    total_qty = math.floor(r_dollars / risk_per_share_full)

    # When the mode targets a concentration (10–20% of capital in one name), that
    # is the size at FULL EXTENSION — first tranche ~7%, adds carrying it to ~18%.
    # Starting at 15% and adding twice instead lands near 38% of the account in a
    # single sub-$150M name, which is a bet the exits cannot rescue.
    tgt = mode.get("LADDER_TARGET_EQUITY_PCT")
    if tgt:
        total_qty = min(total_qty, math.floor((equity * tgt) / avg_price))

    cap = math.floor((equity * mode["CATASTROPHE_CAP_PCT"]) / entry)
    if adv:
        cap = min(cap, math.floor((adv * mode["LIQ_CAP_ADV_PCT"]) / entry))
    if med1:
        cap = min(cap, math.floor((med1 * mode["LIQ_CAP_MIN1_PCT"]) / entry))
    total_qty = max(0, min(total_qty, cap))
    if total_qty < 3:
        return None

    tranches = []
    for (name, lvl), f in zip(ordered, fracs):
        q = max(1, math.floor(total_qty * f))
        tranches.append({"level_name": name, "price": round(lvl, 2), "qty": q, "filled": False})
    return {
        "tranches": tranches,
        "final_stop": round(final_stop, 2),
        "total_qty": sum(t["qty"] for t in tranches),
        "avg_price_if_full": round(avg_price, 2),
        "total_risk_R": 1.0,
        "time_stop_min": mode["LADDER_TIME_STOP_MIN"],
    }


# ═══════════════════════════════════════════════════════════════════════════
#  ORDERS — marketable limits, day TIF, real working stops
# ═══════════════════════════════════════════════════════════════════════════

def _order(payload: dict) -> dict:
    t = _t()
    try:
        r = requests.post(f"{t.ALPACA_BASE}/v2/orders", headers=t._alpaca_headers(),
                          json=payload, timeout=10)
        data = r.json()
        if r.status_code in (200, 201):
            return {"ok": True, "id": data.get("id"), "status": data.get("status")}
        return {"ok": False, "error": str(data.get("message", "rejected"))[:140]}
    except Exception as e:
        return {"ok": False, "error": str(e)[:140]}


def buy_marketable_limit(ticker: str, qty: int, ref_price: float, slip=0.004) -> dict:
    """Never send a market order into a thin book (Section 5.5). A marketable
    limit a few tenths above the ask fills like a market order when there's
    size there and simply doesn't fill when there isn't — which is the correct
    behaviour in a name whose book is 40 cents wide."""
    return _order({
        "symbol": ticker.upper(), "qty": str(int(qty)), "side": "buy",
        "type": "limit", "limit_price": str(round(ref_price * (1 + slip), 2)),
        "time_in_force": "day",
    })


def sell_marketable_limit(ticker: str, qty: int, ref_price: float, slip=0.006) -> dict:
    return _order({
        "symbol": ticker.upper(), "qty": str(int(qty)), "side": "sell",
        "type": "limit", "limit_price": str(round(ref_price * (1 - slip), 2)),
        "time_in_force": "day",
    })


def place_stop(ticker: str, qty: int, stop: float) -> dict:
    return _t()._update_stop_order(ticker, stop, int(qty))


# ═══════════════════════════════════════════════════════════════════════════
#  SECTION 6 — POSITION MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════

def manage_positions(mode: dict, state: dict, log: list) -> int:
    """The scale-out ladder, thesis-invalidation exits, time stops, and the
    non-negotiable flatten. Runs before any new entries are considered."""
    t = _t()
    now = _now_et()
    acted = 0
    positions = t.alpaca_positions() or []
    if not positions:
        return 0

    hard_flatten = now >= _at(now, HARD_FLATTEN_LATEST)
    mode_flatten = now >= _at(now, mode["FLATTEN_AT"])

    for p in positions:
        tkr = p["ticker"]
        meta = state["positions"].get(tkr)
        qty = int(p["qty"])
        if qty <= 0:
            continue
        px = p["current_price"]

        # ── Positions this engine didn't open are not its to close ─────────
        # The flatten rail below is absolute for small-cap trades, but applying
        # it to a book another strategy owns would silently liquidate Core's
        # swing positions the first afternoon after a mode switch. Warn instead.
        if not meta:
            if mode_flatten or hard_flatten:
                log.append(f"⚠️ **{tkr}** is held by another strategy (not opened in "
                           f"{mode['key']} mode) — left alone. Close it yourself if you "
                           f"don't want it overnight.")
            continue

        # ── Rail: flat by the close, every day, no exceptions ──────────────
        if mode_flatten or hard_flatten:
            t.alpaca_cancel_all_orders()
            r = t.alpaca_sell(ticker=tkr, sell_all=True)
            log.append(f"🔔 **{tkr} flattened** — {mode['FLATTEN_AT']} rail. "
                       f"Overnight in this universe is a financing window, not a hold.")
            if r.get("ok"):
                acted += 1
                _journal({"event": "flatten", "ticker": tkr, "mode": mode["key"],
                          "pnl_pct": p.get("unrealized_pnl_pct")})
            state["positions"].pop(tkr, None)
            continue

        entry = meta.get("entry", p["avg_entry"])
        stop0 = meta.get("initial_stop")
        if not stop0 or entry <= stop0:
            continue
        R = entry - stop0
        open_r = (px - entry) / R if R else 0

        ctx = build_context(tkr, now)

        # ── Thesis invalidation overrides price (4.4 constraint 4) ─────────
        if ctx:
            vwap = ctx.get("vwap")
            if vwap and px < vwap and _failed_test(ctx["bars5"], vwap):
                t.alpaca_cancel_all_orders()
                t.alpaca_sell(ticker=tkr, sell_all=True)
                log.append(f"❌ **{tkr} exited whole** — VWAP lost on expanding volume. "
                           f"Thesis invalidated; ladder state irrelevant.")
                _journal({"event": "invalidation_exit", "ticker": tkr, "mode": mode["key"],
                          "r": round(open_r, 2)})
                state["positions"].pop(tkr, None)
                acted += 1
                continue

        # ── Scale-out ladder ───────────────────────────────────────────────
        if not meta.get("scaled1") and open_r >= mode["SCALE1_R"]:
            q = max(1, int(qty * mode["SCALE1_FRAC"]))
            if sell_marketable_limit(tkr, q, px).get("ok"):
                meta["scaled1"] = True
                log.append(f"💰 **{tkr}** — scaled {q} at +{open_r:.1f}R into the bid.")
                acted += 1
                if mode["BREAKEVEN_AFTER_SCALE1"]:
                    place_stop(tkr, qty - q, entry)
                    meta["stop"] = entry
                    log.append(f"   Stop to breakeven (${entry:.2f}) on the remainder.")

        elif meta.get("scaled1") and not meta.get("scaled2"):
            climax = False
            if ctx and ctx.get("atr5") and ctx.get("ema9"):
                last = ctx["bars5"][-1]
                stretch = last[2] - ctx["ema9"]
                avg_vol = sum(b[5] for b in ctx["bars5"][-10:-1]) / 9 if len(ctx["bars5"]) > 10 else 0
                climax = (stretch > mode["CLIMAX_ATR_MULT"] * ctx["atr5"]
                          and avg_vol and last[5] > avg_vol * 2)
            if open_r >= mode["SCALE2_R"] or climax:
                q = max(1, int(qty * mode["SCALE2_FRAC"] / (1 - mode["SCALE1_FRAC"])))
                q = min(q, max(qty - 1, 1))
                if sell_marketable_limit(tkr, q, px).get("ok"):
                    meta["scaled2"] = True
                    why = "climax bar — the only moment the bid absorbs size" if climax else f"+{open_r:.1f}R"
                    log.append(f"💰 **{tkr}** — scaled {q} into strength ({why}).")
                    acted += 1

        # ── Stall exit: sell when momentum stops confirming ────────────────
        if (mode.get("STALL_EXIT") and ctx and meta.get("scaled1")
                and not meta.get("stalled") and open_r > 0):
            if momentum_stalled(ctx["bars5"],
                                mode.get("STALL_LOOKBACK", 3)):
                if sell_marketable_limit(tkr, qty, px).get("ok"):
                    meta["stalled"] = True
                    log.append(f"⚡ **{tkr} closed on the stall** — no new high in "
                               f"{mode.get('STALL_LOOKBACK', 3)} bars on fading volume, "
                               f"out at {open_r:+.2f}R. This sells before the top by design.")
                    _journal({"event": "stall_exit", "ticker": tkr, "mode": mode["key"],
                              "r": round(open_r, 2)})
                    state["positions"].pop(tkr, None)
                    acted += 1
                    continue

        # ── Runner trail: 9EMA closes, hard floor at VWAP ──────────────────
        if meta.get("scaled2") and ctx:
            ema9, vwap = ctx.get("ema9"), ctx.get("vwap")
            if ema9:
                new_stop = max(ema9 * 0.995, vwap or 0, meta.get("stop") or 0)
                if new_stop > (meta.get("stop") or 0) * 1.002 and new_stop < px:
                    if place_stop(tkr, qty, new_stop).get("ok"):
                        meta["stop"] = round(new_stop, 2)
                        log.append(f"🪜 **{tkr}** — runner stop trailed to ${new_stop:.2f}.")
                        acted += 1

        # ── Time stop: dead money decays in this universe ──────────────────
        opened = meta.get("opened_at")
        if opened and not meta.get("scaled1"):
            try:
                age = (now - datetime.fromisoformat(opened)).total_seconds() / 60
            except Exception:
                age = 0
            if age >= mode["TIME_STOP_MIN"] and abs(open_r) < mode["TIME_STOP_MAX_R"]:
                t.alpaca_cancel_all_orders()
                if t.alpaca_sell(ticker=tkr, sell_all=True).get("ok"):
                    log.append(f"⏱ **{tkr} cut** — {int(age)}min in, still flat "
                               f"({open_r:+.2f}R). The setup has lost its reason to exist.")
                    _journal({"event": "time_stop", "ticker": tkr, "mode": mode["key"],
                              "r": round(open_r, 2), "minutes": int(age)})
                    state["positions"].pop(tkr, None)
                    acted += 1
                    continue

        # ── Ladder management (aggro only) ─────────────────────────────────
        ladder = meta.get("ladder")
        if ladder and mode.get("SCALE_IN"):
            acted += _work_ladder(tkr, meta, ladder, px, mode, state, log, now)

        state["positions"][tkr] = meta

    return acted


def _work_ladder(tkr, meta, ladder, px, mode, state, log, now) -> int:
    """Fill pre-planned tranches when price reaches pre-planned levels.

    Three hard gates, all from 4.4: one rescue per ticker per day, never after
    a stop-out, and a time stop on the whole ladder. Nothing here is reactive —
    every level and every share count was fixed before the first fill.
    """
    t = _t()
    acted = 0
    if tkr in state.get("stopped_out", []):
        return 0
    if mode.get("LADDER_ONE_RESCUE_PER_TICKER") and tkr in state.get("rescued", []):
        return 0

    started = meta.get("opened_at")
    if started:
        try:
            age = (now - datetime.fromisoformat(started)).total_seconds() / 60
        except Exception:
            age = 0
        if age >= ladder.get("time_stop_min", 75) and not meta.get("scaled1"):
            t.alpaca_cancel_all_orders()
            t.alpaca_sell(ticker=tkr, sell_all=True)
            log.append(f"⏱ **{tkr} ladder timed out** — trigger not reclaimed in "
                       f"{int(age)}min. Out of the whole stack.")
            _journal({"event": "ladder_timeout", "ticker": tkr, "mode": mode["key"]})
            state["positions"].pop(tkr, None)
            return 1

    for tr in ladder["tranches"]:
        if tr["filled"]:
            continue
        if px <= tr["price"] * 1.002:
            r = buy_marketable_limit(tkr, tr["qty"], px)
            if r.get("ok"):
                tr["filled"] = True
                acted += 1
                state.setdefault("rescued", []).append(tkr)
                filled_qty = sum(x["qty"] for x in ladder["tranches"] if x["filled"])
                place_stop(tkr, filled_qty, ladder["final_stop"])
                log.append(f"🪜 **{tkr} tranche filled** — {tr['qty']} at the pre-planned "
                           f"{tr['level_name']} level (${tr['price']:.2f}). "
                           f"Final stop unchanged at ${ladder['final_stop']:.2f}; total risk still 1R.")
                _journal({"event": "ladder_fill", "ticker": tkr, "mode": mode["key"],
                          "level": tr["level_name"], "qty": tr["qty"],
                          "final_stop": ladder["final_stop"]})
            break  # one tranche per cycle
    return acted


# ═══════════════════════════════════════════════════════════════════════════
#  THE RUNNER
# ═══════════════════════════════════════════════════════════════════════════

def run(mode_key: str = "strict", dry_run: bool = False, skip_market_check: bool = False,
        candidates_only: bool = False) -> dict:
    """One full cycle of the small-cap gainer pullback autopilot.

    candidates_only=True makes this a read-only scan: no position management, no
    orders, no state writes, and the time-of-day and slot gates are skipped so a
    watchlist can still be produced. It returns the graded candidates instead of
    trading them. Alerts run through this path rather than a parallel scanner, so
    an alert can never describe a setup the autopilot wouldn't itself take."""
    t = _t()
    mode = get_mode(mode_key)
    log = [f"**Mode: {mode['label']}** — {mode['tagline']}"]
    now = _now_et()
    state = _load_state()

    is_open, status = t._market_is_open()
    if not is_open and not skip_market_check and not dry_run:
        return {"ok": True, "log": log + [status], "buys": 0, "sells": 0,
                "mode": mode_key, "scanned": 0}

    account = t.alpaca_account()
    if not account:
        return {"ok": False, "log": log + ["Alpaca account unavailable."], "mode": mode_key}
    equity = account["equity"]

    # ── Manage what's open first ───────────────────────────────────────────
    sells = 0 if candidates_only else manage_positions(mode, state, log)

    # ── PDT floor: the account must stay able to day trade at all ──────────
    pdt = pdt_headroom(equity)
    effective_limit = mode["DAILY_LOSS_LIMIT"]
    if pdt["applies"]:
        if pdt["blocked"]:
            state["halted_for_day"] = True
            _save_state(state)
            log.append(f"🛑 **Equity ${equity:,.0f} is at the PDT floor** "
                       f"(${pdt['floor']:,.0f} incl. buffer). No new entries — another "
                       f"day trade risks locking the account out entirely. Existing "
                       f"positions are still managed.")
            return {"ok": True, "log": log, "buys": 0, "sells": sells, "mode": mode_key,
                    "scanned": 0, "halted": True, "pdt_blocked": True}
        if pdt["max_loss_pct"] < effective_limit:
            effective_limit = pdt["max_loss_pct"]
            log.append(f"⚠️ Daily stop tightened to {effective_limit:.2%} "
                       f"(${pdt['room']:,.0f} of room above the PDT floor) — "
                       f"below the mode's {mode['DAILY_LOSS_LIMIT']:.0%}.")

    # ── Daily loss limit, enforced in software rather than willpower ───────
    day_pnl_pct = (account.get("daily_pnl", 0) or 0) / equity if equity else 0
    if day_pnl_pct <= -effective_limit:
        state["halted_for_day"] = True
        _save_state(state)
        t.alpaca_close_all()
        log.append(f"🛑 **Daily loss limit hit** ({day_pnl_pct:.2%} ≤ -{effective_limit:.2%}). "
                   f"Flat and done for the day.")
        return {"ok": True, "log": log, "buys": 0, "sells": sells, "mode": mode_key, "halted": True}
    if state.get("halted_for_day"):
        log.append("🛑 Daily loss limit already hit today — managing only, no new entries.")
        _save_state(state)
        return {"ok": True, "log": log, "buys": 0, "sells": sells, "mode": mode_key, "halted": True}

    # ── Entry gates ────────────────────────────────────────────────────────
    positions = t.alpaca_positions() or []
    held = {p["ticker"] for p in positions}

    # MAX_POSITIONS is a limit on THIS strategy's concurrent risk, so only count
    # positions this mode opened. Counting the whole account meant a Core book
    # left open (4 swing names vs a 3-position cap) put the small-cap engine
    # permanently at capacity, and it never scanned at all.
    mine = [p for p in positions if p["ticker"] in state.get("positions", {})]
    foreign = [p["ticker"] for p in positions if p["ticker"] not in state.get("positions", {})]
    open_slots = mode["MAX_POSITIONS"] - len(mine)
    if foreign:
        log.append(f"ℹ️ {len(foreign)} position(s) held by another strategy "
                   f"({', '.join(foreign[:4])}) — not counted against this mode's "
                   f"{mode['MAX_POSITIONS']} slots, and not managed here.")
    entries_today = len(state.get("attempts", {}))

    if now < _at(now, mode["OPEN_BLACKOUT_UNTIL"]) and not dry_run and not candidates_only:
        log.append(f"⏸ Before {mode['OPEN_BLACKOUT_UNTIL']} — widest spreads, most halts, most traps. Observing.")
        _save_state(state)
        return {"ok": True, "log": log, "buys": 0, "sells": sells, "mode": mode_key, "scanned": 0}

    if not _in_window(now, mode["ENTRY_WINDOWS"]) and not dry_run and not candidates_only:
        log.append("⏸ Outside this mode's entry windows — managing existing positions only.")
        _save_state(state)
        return {"ok": True, "log": log, "buys": 0, "sells": sells, "mode": mode_key, "scanned": 0}

    if open_slots <= 0 and not dry_run and not candidates_only:
        log.append(f"Max positions ({mode['MAX_POSITIONS']}) held — these names are one trade "
                   f"wearing different tickers. No scan.")
        _save_state(state)
        return {"ok": True, "log": log, "buys": 0, "sells": sells, "mode": mode_key, "scanned": 0}

    cap = mode.get("MAX_DAILY_ENTRIES")
    if cap and entries_today >= cap and not dry_run and not candidates_only:
        log.append(f"Daily entry cap reached ({entries_today}/{cap}).")
        _save_state(state)
        return {"ok": True, "log": log, "buys": 0, "sells": sells, "mode": mode_key, "scanned": 0}

    # ── Section 1: scan ────────────────────────────────────────────────────
    log.append("")
    log.append("**Scanning gainers**")
    raw_gainers = t.polygon_gainers(limit=mode["TOP_N_GAINERS"])
    raw_snaps = t.polygon_all_snapshots()
    gainers = raw_gainers or []
    snaps = raw_snaps or []
    log.append(f"feed: gainers {len(gainers) if raw_gainers is not None else 'NONE'} · "
               f"snapshots {len(snaps) if raw_snaps is not None else 'NONE'}")
    pool = {}
    for g in gainers:
        pool[g.get("Ticker")] = g
    for s in snaps:
        if s.get("Chg%", 0) >= mode["MIN_DAY_CHANGE"] and s.get("Ticker") not in pool:
            pool[s["Ticker"]] = s
    ranked = sorted(pool.values(), key=lambda x: -(x.get("Chg%") or 0))[:mode["TOP_N_GAINERS"] + 15]

    survivors, rejected = [], []
    for row in ranked:
        tkr = row.get("Ticker")
        if not tkr or tkr in held:
            continue
        if state.get("attempts", {}).get(tkr, 0) >= MAX_ATTEMPTS_PER_TICKER:
            rejected.append((tkr, "2 attempts already — a third is revenge, not analysis"))
            continue
        price, chg = row.get("Price", 0), row.get("Chg%", 0)
        if not (mode["PRICE_MIN"] <= price <= mode["PRICE_MAX"]):
            rejected.append((tkr, f"${price:.2f} outside price band"))
            continue
        if chg < mode["MIN_DAY_CHANGE"]:
            rejected.append((tkr, f"{chg:+.1f}% under threshold"))
            continue

        rvol = time_adjusted_rvol(tkr, now)
        rv_min = mode["RVOL_MIN"] if now.hour < 12 else mode["RVOL_MIN_AFTERNOON"]
        if rvol is None or rvol < rv_min:
            rejected.append((tkr, f"RVOL {rvol if rvol is not None else '?'} < {rv_min} — thin tape drifting"))
            continue

        flt, cap = float_and_cap(tkr)
        if flt and not (mode["FLOAT_MIN"] <= flt <= mode["FLOAT_MAX"]):
            rejected.append((tkr, f"float {flt/1e6:.0f}M outside band"))
            continue
        cap_ok, cap_mult, cap_note = cap_fit(cap, mode)
        if not cap_ok:
            rejected.append((tkr, cap_note))
            continue

        traded, projected = dollar_volume_today(tkr, now)
        if not traded or traded < mode["DOLLAR_VOL_MIN"]:
            rejected.append((tkr, f"${(traded or 0)/1e6:.1f}M traded — exit liquidity too thin"))
            continue
        if projected and projected < mode["PROJ_DOLLAR_VOL_MIN"]:
            rejected.append((tkr, f"projected ${projected/1e6:.0f}M full day — under bar"))
            continue

        halts = halt_count_recent(tkr, 20)
        if halts > mode["MAX_HALTS_20MIN"]:
            rejected.append((tkr, f"{halts} halts in 20min — entry is a coin flip between a fill and a lockup"))
            continue

        survivors.append({"ticker": tkr, "price": price, "chg": chg, "rvol": rvol,
                          "float": flt, "cap": cap, "traded": traded,
                          "projected": projected, "halts": halts,
                          "cap_mult": cap_mult, "cap_note": cap_note})

    if not ranked:
        # Empty pool is either a dead feed or a market with no movers. Say which,
        # rather than printing "0 ranked" and leaving it ambiguous for a week.
        diag = feed_diagnostics()
        log.append(f"⚠️ **No candidates in the pool.** {diag['verdict']}")
        if diag.get("gainers", {}).get("status") not in (200, None):
            log.append(f"   gainers endpoint → HTTP {diag['gainers']['status']} "
                       f"{diag['gainers'].get('error', '')[:120]}")
        if diag.get("snapshots", {}).get("status") not in (200, None):
            log.append(f"   snapshots endpoint → HTTP {diag['snapshots']['status']} "
                       f"{diag['snapshots'].get('error', '')[:120]}")
        _save_state(state)
        return {"ok": True, "log": log, "buys": 0, "sells": sells, "scanned": 0,
                "mode": mode_key, "candidates": [], "feed": diag}

    log.append(f"{len(ranked)} ranked → **{len(survivors)} cleared the universe filters**")
    for tkr, why in rejected[:8]:
        log.append(f"  ⏭ {tkr} — {why}")
    if not survivors:
        _save_state(state)
        return {"ok": True, "log": log, "buys": 0, "sells": sells, "scanned": len(ranked),
                "mode": mode_key, "candidates": []}

    # ── Section 2 + 5: setups and hazards on the survivors ─────────────────
    log.append("")
    log.append("**Grading setups**")
    candidates = []
    for s in survivors[:12]:
        tkr = s["ticker"]
        ctx = build_context(tkr, now)
        if not ctx:
            continue
        vol = volatility_profile(ctx, mode)
        if not vol["ok"]:
            log.append(f"  ⏭ {tkr} — {vol['reason']}")
            continue
        setups = detect_setups(ctx, mode)
        if not setups:
            log.append(f"  · {tkr} — no valid retest right now")
            continue
        best = setups[0]

        hz = filings_hazard(tkr)
        cat = catalyst_grade(tkr)
        size_mult = 1.0
        skip = None

        if hz.get("days_since_424b5") is not None and hz["days_since_424b5"] <= mode["HAZARD_BLOCK_424B5_DAYS"]:
            skip = f"424B5 priced {hz['days_since_424b5']}d ago — you're buying into the offering"
        elif hz.get("serial_splitter") and mode["BLOCK_SERIAL_SPLITTER"]:
            skip = "serial reverse-splitter — volatility is the product here"
        elif hz.get("reverse_split_months") is not None and hz["reverse_split_months"] <= mode["BLOCK_REVERSE_SPLIT_MONTHS"]:
            skip = f"reverse split {hz['reverse_split_months']:.0f}mo ago"
        elif cat["grade"] == "none" and mode["REQUIRE_CATALYST"]:
            skip = "no identifiable catalyst — if you can't name it, you are it"

        if skip:
            log.append(f"  ⏭ {tkr} — {skip}")
            continue

        if hz.get("s3_shelf"):
            size_mult *= mode["HAZARD_ATM_SIZE_MULT"]
        if cat["grade"] == "fluff":
            size_mult *= mode["FLUFF_SIZE_MULT"]
        if mode.get("LOW_FLOAT_CUTOFF") and s["float"] and s["float"] < mode["LOW_FLOAT_CUTOFF"]:
            size_mult *= mode["LOW_FLOAT_SIZE_MULT"]
        if mode.get("MIDDAY_SIZE_MULT") and _at(now, mode["MIDDAY"][0]) <= now <= _at(now, mode["MIDDAY"][1]):
            size_mult *= mode["MIDDAY_SIZE_MULT"]
        if mode.get("OPEN_SIZE_MULT") and now < _at(now, "09:45"):
            size_mult *= mode["OPEN_SIZE_MULT"]

        size_mult *= s.get("cap_mult", 1.0)
        best["stop"] = round(atr_stop(best["entry"], ctx, mode, best["stop"]), 2)
        candidates.append({**s, "ctx": ctx, "setup": best, "hazard": hz,
                           "catalyst": cat, "size_mult": size_mult, "vol": vol})
        log.append(f"  ✅ **{tkr}** {best['setup']} · grade {best['grade']} · RVOL {s['rvol']} · "
                   f"catalyst {cat['grade']} · {vol['notes'][0] if vol['notes'] else ''}" + (f" · ⚠ {', '.join(hz['flags'][:2])}" if hz.get("flags") else ""))

    if not candidates:
        _save_state(state)
        return {"ok": True, "log": log, "buys": 0, "sells": sells, "scanned": len(ranked),
                "mode": mode_key, "candidates": []}

    candidates.sort(key=lambda c: -c["setup"]["grade"])

    if candidates_only:
        return {"ok": True, "mode": mode_key, "scanned": len(ranked), "log": log,
                "candidates": [{
                    "ticker": c["ticker"], "price": c["price"], "chg": c["chg"],
                    "rvol": c["rvol"], "float": c["float"],
                    "setup": c["setup"]["setup"], "grade": c["setup"]["grade"],
                    "entry": c["setup"]["entry"], "stop": c["setup"]["stop"],
                    "notes": c["setup"]["notes"][:3],
                    "catalyst": c["catalyst"]["grade"],
                    "hazards": c["hazard"].get("flags", []),
                    "size_mult": round(c["size_mult"], 2),
                } for c in candidates]}

    # ── Section 3 + execution ──────────────────────────────────────────────
    log.append("")
    log.append("**Executing**")
    buys = 0
    for c in candidates[:max(open_slots, 1)]:
        tkr = c["ticker"]
        setup = c["setup"]
        entry, stop = setup["entry"], setup["stop"]
        adv = _avg_dollar_volume_20d(tkr)
        med1 = median_1min_dollar_volume(tkr, 30)

        ladder = None
        if mode.get("SCALE_IN"):
            ladder = plan_ladder(entry, stop, c["ctx"], equity, mode, adv, med1)

        if ladder:
            qty = ladder["tranches"][0]["qty"]
            final_stop = ladder["final_stop"]
            _qtys = "/".join(str(tr["qty"]) for tr in ladder["tranches"])
            _lvls = "/".join("${:.2f}".format(tr["price"]) for tr in ladder["tranches"])
            plan_txt = (f"ladder {_qtys} at {_lvls}, final stop ${final_stop:.2f} "
                        f"(total risk still 1R)")
        else:
            sz = size_position(equity, entry, stop, mode, tkr, adv, med1, c["size_mult"])
            qty = sz["qty"]
            final_stop = stop
            if qty < 1:
                log.append(f"  ⏭ {tkr} — {sz['reason']}")
                continue
            plan_txt = (f"{qty} sh, stop ${stop:.2f} ({sz['stop_pct']:.1%}), "
                        f"binding cap: {sz['binding_cap']}")

        notional = qty * entry
        line = (f"{'🟢' if not dry_run else '🔍'} **{tkr}** — {setup['setup']} @ ${entry:.2f} · "
                f"{plan_txt} · ${notional:,.0f} notional")

        if dry_run:
            log.append(line + "  _(dry run)_")
            for n in setup["notes"][:3]:
                log.append(f"     · {n}")
            continue

        r = buy_marketable_limit(tkr, qty, entry)
        if not r.get("ok"):
            log.append(f"  ❌ {tkr} — order rejected: {r.get('error')}")
            continue
        time.sleep(1.2)
        place_stop(tkr, qty, final_stop)

        state.setdefault("attempts", {})[tkr] = state.get("attempts", {}).get(tkr, 0) + 1
        state["positions"][tkr] = {
            "entry": entry, "initial_stop": final_stop, "stop": final_stop,
            "qty": qty, "opened_at": now.isoformat(), "setup": setup["setup"],
            "grade": setup["grade"], "mode": mode["key"], "ladder": ladder,
            "scaled1": False, "scaled2": False,
        }
        _journal({"event": "entry", "ticker": tkr, "mode": mode["key"],
                  "setup": setup["setup"], "grade": setup["grade"], "entry": entry,
                  "stop": final_stop, "qty": qty, "ladder": bool(ladder),
                  "rvol": c["rvol"], "float": c["float"], "catalyst": c["catalyst"]["grade"],
                  "hazard_flags": c["hazard"].get("flags", [])})
        log.append(line)
        for n in setup["notes"][:3]:
            log.append(f"     · {n}")
        buys += 1

    _save_state(state)
    return {"ok": True, "log": log, "buys": buys, "sells": sells,
            "scanned": len(ranked), "opportunities": len(candidates), "mode": mode_key}
