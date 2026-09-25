"""
Owner-customizable autopilot settings, per strategy mode.

The strategies ship with tuned defaults (smallcap_pullback's mode dicts, and
trading.load_autopilot_config for core). This module lets the owner change a
curated set of those values from the app, within ranges that keep the engine
safe to run. It is the only place that knows which knobs exist, their limits,
and how each one maps onto the engine's own parameter names.

Choices are stored in their own file (strategy_custom.json, next to the
autopilot config) so nothing that rewrites autopilot_config.json can clobber
them. An empty file means every mode runs exactly its shipped defaults.

Engine hooks:
  smallcap_pullback.get_active_mode()  -> apply_smallcap()
  trading.load_autopilot_config()      -> apply_core()
"""
import json
import os
import pathlib
import re
import threading

_HERE = pathlib.Path(__file__).parent
_lock = threading.Lock()

SMALLCAP_SETUPS = {
    "vwap_reclaim": "VWAP reclaim",
    "ema_pullback": "EMA pullback",
    "pdh_retest": "Prior-day-high retest",
    "orb_retest": "Opening-range retest",
    "hod_break": "High-of-day break",
    "flag": "Bull flag",
}

# type: pct  -> stored as a fraction, shown as a percent (x100)
#       pts  -> already in percent units (e.g. 2.5 means 2.5%)
#       num / int / bool / time / setups
# zero: label shown when 0 is chosen and 0 means something special.
_SMALLCAP_KNOBS = [
    # Risk & sizing
    {"key": "R_PCT", "group": "Risk & sizing", "label": "Risk per trade", "type": "pct",
     "min": 0.001, "max": 0.02, "step": 0.0005,
     "help": "How much of your account a trade loses if it hits its stop."},
    {"key": "MAX_POSITIONS", "group": "Risk & sizing", "label": "Open positions at once", "type": "int",
     "min": 1, "max": 5, "step": 1},
    {"key": "DAILY_LOSS_LIMIT", "group": "Risk & sizing", "label": "Daily loss limit", "type": "pct",
     "min": 0.005, "max": 0.06, "step": 0.0025,
     "help": "Stops trading for the day once the account is down this much."},
    {"key": "MAX_DAILY_ENTRIES", "group": "Risk & sizing", "label": "New trades per day", "type": "int",
     "min": 0, "max": 20, "step": 1, "zero": "No limit"},
    {"key": "CATASTROPHE_CAP_PCT", "group": "Risk & sizing", "label": "Largest single position", "type": "pct",
     "min": 0.05, "max": 0.30, "step": 0.01,
     "help": "Hard ceiling on one name's size as a share of the account, adds included."},
    {"key": "MAX_STOP_PCT", "group": "Risk & sizing", "label": "Widest allowed stop", "type": "pct",
     "min": 0.02, "max": 0.15, "step": 0.005,
     "help": "Skips a setup when its stop would sit further than this below entry."},
    # What it buys
    {"key": "PRICE_MIN", "group": "What it buys", "label": "Lowest share price", "type": "num",
     "min": 0.5, "max": 50, "step": 0.25, "unit": "$"},
    {"key": "PRICE_MAX", "group": "What it buys", "label": "Highest share price", "type": "num",
     "min": 2, "max": 200, "step": 1, "unit": "$"},
    {"key": "MIN_DAY_CHANGE", "group": "What it buys", "label": "Minimum gain on the day", "type": "pts",
     "min": 2, "max": 50, "step": 0.5},
    {"key": "RVOL_MIN", "group": "What it buys", "label": "Minimum relative volume", "type": "num",
     "min": 1, "max": 10, "step": 0.1, "unit": "x",
     "help": "Today's volume versus normal for this time of day."},
    {"key": "MIN_SETUP_GRADE", "group": "What it buys", "label": "Minimum setup grade", "type": "int",
     "min": 30, "max": 95, "step": 1,
     "help": "0–100 quality score for the pullback. Higher means fewer, cleaner trades."},
    {"key": "REQUIRE_CATALYST", "group": "What it buys", "label": "Require a news catalyst", "type": "bool"},
    {"key": "SETUPS", "group": "What it buys", "label": "Setups it may trade", "type": "setups",
     "options": SMALLCAP_SETUPS},
    # Timing
    {"key": "ENTRY_START", "group": "Timing", "label": "First entry", "type": "time",
     "min": "09:30", "max": "15:30"},
    {"key": "ENTRY_END", "group": "Timing", "label": "Last entry", "type": "time",
     "min": "09:35", "max": "15:45"},
    {"key": "FLATTEN_AT", "group": "Timing", "label": "Close everything at", "type": "time",
     "min": "12:00", "max": "15:55",
     "help": "Never later than 3:55 PM — nothing is held overnight."},
    # Exits
    {"key": "SCALE1_R", "group": "Exits", "label": "First profit take at", "type": "num",
     "min": 0.25, "max": 3, "step": 0.05, "unit": "R",
     "help": "In multiples of the risk taken. 1R = the amount you'd lose at the stop."},
    {"key": "SCALE1_FRAC", "group": "Exits", "label": "Sell at first take", "type": "pct",
     "min": 0.10, "max": 0.60, "step": 0.01},
    {"key": "TIME_STOP_MIN", "group": "Exits", "label": "Cut a flat trade after", "type": "int",
     "min": 10, "max": 180, "step": 5, "unit": "min"},
    {"key": "SCALE_IN", "group": "Exits", "label": "Add to winners on dips", "type": "bool",
     "modes": ["intense"]},
]

_CORE_KNOBS = [
    {"key": "RISK_PER_TRADE", "group": "Risk & sizing", "label": "Risk per trade", "type": "pct",
     "min": 0, "max": 0.02, "step": 0.0005, "zero": "Auto (by market)",
     "help": "Auto sizes risk from the market regime: 1% in a healthy trend, less when it isn't."},
    {"key": "MAX_POSITIONS", "group": "Risk & sizing", "label": "Open positions at once", "type": "int",
     "min": 1, "max": 6, "step": 1},
    {"key": "MAX_DAILY_ENTRIES", "group": "Risk & sizing", "label": "New trades per day", "type": "int",
     "min": 1, "max": 10, "step": 1},
    {"key": "DAILY_LOSS_LIMIT", "group": "Risk & sizing", "label": "Daily loss limit", "type": "pct",
     "min": 0.005, "max": 0.06, "step": 0.0025},
    {"key": "MAX_POS_PCT", "group": "Risk & sizing", "label": "Largest single position", "type": "pct",
     "min": 0.02, "max": 0.30, "step": 0.01},
    {"key": "MIN_SCORE", "group": "Entry quality", "label": "Minimum signal score", "type": "int",
     "min": 60, "max": 95, "step": 1},
    {"key": "MIN_CONFLUENCE", "group": "Entry quality", "label": "Factors that must agree", "type": "int",
     "min": 2, "max": 8, "step": 1},
    {"key": "MIN_RR", "group": "Entry quality", "label": "Minimum reward-to-risk", "type": "num",
     "min": 1, "max": 5, "step": 0.1, "unit": "x"},
    {"key": "SELL_BELOW", "group": "Exits", "label": "Sell when score drops below", "type": "int",
     "min": 10, "max": 60, "step": 1},
    {"key": "PARTIAL_PROFIT_PCT", "group": "Exits", "label": "Take half off at", "type": "pct",
     "min": 0.005, "max": 0.10, "step": 0.0025},
    {"key": "TAKE_PROFIT_PCT", "group": "Exits", "label": "Full exit at", "type": "pct",
     "min": 0.01, "max": 0.25, "step": 0.005},
    {"key": "TRAIL_ACTIVATE_PCT", "group": "Exits", "label": "Start trailing at", "type": "pts",
     "min": 0.5, "max": 10, "step": 0.1},
    {"key": "TRAIL_DISTANCE_PCT", "group": "Exits", "label": "Trail distance", "type": "pts",
     "min": 0.5, "max": 10, "step": 0.1},
    {"key": "TRADING_HOURS_START", "group": "Timing", "label": "First entry", "type": "time",
     "min": "09:30", "max": "15:30"},
    {"key": "TRADING_HOURS_END", "group": "Timing", "label": "Last entry", "type": "time",
     "min": "09:35", "max": "15:55"},
    {"key": "AVOID_MIDDAY", "group": "Timing", "label": "Skip the midday lull", "type": "bool"},
    {"key": "AUTO_TUNE", "group": "Timing", "label": "Auto-tune daily", "type": "bool",
     "help": "Tightens or relaxes entry quality each morning based on yesterday. Your own "
             "values above still win."},
]

MODES = ("strict", "intense", "core")


def knobs(mode: str) -> list[dict]:
    base = _CORE_KNOBS if mode == "core" else _SMALLCAP_KNOBS
    return [k for k in base if mode in k.get("modes", MODES)]


# ── Storage ──────────────────────────────────────────────────────────────

def _path() -> pathlib.Path:
    base = os.environ.get("DB_DIR")
    return (pathlib.Path(base) if base else _HERE) / "strategy_custom.json"


def load_all() -> dict:
    try:
        data = json.loads(_path().read_text())
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def load(mode: str) -> dict:
    """Validated overrides for one mode. Anything stale or out of range in the
    file is dropped here, so a hand-edited file can't push the engine outside
    the limits."""
    raw = load_all().get(mode) or {}
    specs = {k["key"]: k for k in knobs(mode)}
    out = {}
    for key, val in raw.items():
        if key in specs:
            try:
                out[key] = _coerce(specs[key], val)
            except ValueError:
                pass
    return out


def save(mode: str, updates: dict) -> dict:
    """Merge validated `updates` into this mode's overrides. A None value
    resets that knob to the default. Raises ValueError with a readable message."""
    if mode not in MODES:
        raise ValueError(f"Unknown mode {mode!r}")
    specs = {k["key"]: k for k in knobs(mode)}
    with _lock:
        all_modes = load_all()
        current = dict(load(mode))
        for key, val in (updates or {}).items():
            if key not in specs:
                raise ValueError(f"{key} can't be customized for this strategy")
            if val is None:
                current.pop(key, None)
            else:
                current[key] = _coerce(specs[key], val)
        _check_combined(mode, current)
        all_modes[mode] = current
        p = _path()
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(all_modes, indent=2))
        tmp.replace(p)   # atomic: a reader never sees half a file
    return current


# ── Validation ───────────────────────────────────────────────────────────

_TIME = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def _coerce(spec: dict, val):
    t = spec["type"]
    label = spec["label"]
    if t == "bool":
        if not isinstance(val, bool):
            raise ValueError(f"{label} must be on or off")
        return val
    if t == "time":
        if not isinstance(val, str) or not _TIME.match(val):
            raise ValueError(f"{label} must be a time like 09:45")
        if not (spec["min"] <= val <= spec["max"]):
            raise ValueError(f"{label} must be between {spec['min']} and {spec['max']} ET")
        return val
    if t == "setups":
        if not isinstance(val, list) or not val:
            raise ValueError("Pick at least one setup")
        bad = [v for v in val if v not in spec["options"]]
        if bad:
            raise ValueError(f"Unknown setup: {bad[0]}")
        return [s for s in spec["options"] if s in val]   # canonical order, no dupes
    if isinstance(val, bool) or not isinstance(val, (int, float)):
        raise ValueError(f"{label} must be a number")
    n = int(round(val)) if t == "int" else float(val)
    if not (spec["min"] <= n <= spec["max"]):
        raise ValueError(f"{label} is out of range")
    return n


def _check_combined(mode: str, v: dict) -> None:
    """Rules that involve two knobs. Uses the mode's defaults for whichever
    side isn't customized."""
    d = defaults(mode)
    g = lambda k: v.get(k, d.get(k))  # noqa: E731
    if mode == "core":
        if g("TRADING_HOURS_START") >= g("TRADING_HOURS_END"):
            raise ValueError("First entry has to be before the last entry")
        if g("PARTIAL_PROFIT_PCT") >= g("TAKE_PROFIT_PCT"):
            raise ValueError("Take half off before the full exit")
        return
    if g("PRICE_MIN") >= g("PRICE_MAX"):
        raise ValueError("Lowest share price has to be below the highest")
    if g("ENTRY_START") >= g("ENTRY_END"):
        raise ValueError("First entry has to be before the last entry")
    if g("ENTRY_END") > g("FLATTEN_AT"):
        raise ValueError("Last entry can't be after the time everything closes")
    # The second scale-out sells a share of what's left; the two can't add up
    # to the whole position (the engine divides by what remains).
    if g("SCALE1_FRAC") + (d.get("SCALE2_FRAC") or 0) >= 0.95:
        raise ValueError("Sell at first take is too large — something has to be left to trail")


# ── Defaults (what each knob is when not customized) ─────────────────────

def defaults(mode: str) -> dict:
    if mode == "core":
        import trading
        base = trading.load_autopilot_config(apply_custom=False)
        out = {k["key"]: base.get(k["key"]) for k in _CORE_KNOBS}
        if base.get("RISK_AUTO"):
            out["RISK_PER_TRADE"] = 0   # "Auto"
        out["AUTO_TUNE"] = True
        return out
    import smallcap_pullback as scp
    m = scp.get_mode(mode)
    out = {k["key"]: m.get(k["key"]) for k in _SMALLCAP_KNOBS if k["key"] in m}
    out["MAX_DAILY_ENTRIES"] = m.get("MAX_DAILY_ENTRIES") or 0
    wins = m.get("ENTRY_WINDOWS") or [("09:45", "15:00")]
    out["ENTRY_START"] = max(wins[0][0], m.get("OPEN_BLACKOUT_UNTIL", "09:30"))
    out["ENTRY_END"] = wins[-1][1]
    return out


# ── Engine hooks ─────────────────────────────────────────────────────────

def apply_smallcap(mode: dict, key: str) -> dict:
    """The mode dict with this owner's overrides applied (a copy)."""
    o = load(key)
    if not o:
        return mode
    m = dict(mode)
    for k, v in o.items():
        if k in ("ENTRY_START", "ENTRY_END"):
            continue
        m[k] = v
    if "MAX_DAILY_ENTRIES" in o:
        m["MAX_DAILY_ENTRIES"] = o["MAX_DAILY_ENTRIES"] or None
    if "ENTRY_START" in o or "ENTRY_END" in o:
        start = o.get("ENTRY_START")
        end = o.get("ENTRY_END")
        wins = []
        for a, b in m.get("ENTRY_WINDOWS") or []:
            a2, b2 = max(a, start) if start else a, min(b, end) if end else b
            if a2 < b2:
                wins.append((a2, b2))
        if not wins:
            # The chosen hours fall outside every default window (e.g. only
            # midday): trade exactly the hours asked for.
            d = defaults(key)
            wins = [(start or d["ENTRY_START"], end or d["ENTRY_END"])]
        # Earlier hours need the open blackout moved too, or it still blocks them.
        if start:
            m["OPEN_BLACKOUT_UNTIL"] = start
        m["ENTRY_WINDOWS"] = wins
    return m


def apply_core(params: dict) -> dict:
    """Core params with overrides applied (a copy)."""
    o = load("core")
    if not o:
        return params
    p = dict(params)
    for k, v in o.items():
        if k == "RISK_PER_TRADE":
            if v:   # 0 keeps the automatic, regime-based risk
                p["RISK_PER_TRADE"] = v
                p["RISK_AUTO"] = False
            continue
        p[k] = v
    return p
