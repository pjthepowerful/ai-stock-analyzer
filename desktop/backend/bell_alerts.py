"""
Bell-schedule alerts — push a watchlist to the phone shortly before each period ends.

The schedule is in SCHOOL time (default America/Chicago); the market runs on ET.
Everything here converts explicitly rather than assuming they're the same, because
the two differ by an hour and a silent off-by-one would fire every alert into the
wrong part of the session.

These are ADVISORY only. They never place, size, or cancel an order — the scan
runs through smallcap_pullback.run(candidates_only=True) or the core scan and the
result is formatted into a push notification. Trading remains autopilot's job.
"""

from __future__ import annotations

import json
import os
import pathlib
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

ET = ZoneInfo("US/Eastern")

_DIR = pathlib.Path(os.environ.get("DB_DIR", os.path.dirname(os.path.abspath(__file__))))
CFG_PATH = _DIR / "bell_alerts.json"

# Times are school-local, 24h. end is what the alert is anchored to.
DEFAULT_PERIODS = [
    {"name": "1st", "start": "07:45", "end": "08:35"},
    {"name": "2nd", "start": "08:41", "end": "09:31"},
    {"name": "3rd", "start": "09:37", "end": "10:29"},
    {"name": "4th", "start": "10:35", "end": "11:27"},
    {"name": "5A",  "start": "11:33", "end": "12:25"},
    {"name": "5B",  "start": "12:31", "end": "13:23"},
    {"name": "6th", "start": "13:29", "end": "14:19"},
    {"name": "7th", "start": "14:25", "end": "15:15"},
]

DEFAULTS = {
    "enabled": False,
    "timezone": "America/Chicago",
    "lead_minutes": 2,
    "max_picks": 3,
    "periods": DEFAULT_PERIODS,
    "weekdays_only": True,
    "skip_when_market_closed": True,
}


def load_config() -> dict:
    cfg = dict(DEFAULTS)
    try:
        if CFG_PATH.exists():
            cfg.update(json.loads(CFG_PATH.read_text()) or {})
    except Exception:
        pass
    cfg["periods"] = cfg.get("periods") or DEFAULT_PERIODS
    try:
        cfg["lead_minutes"] = max(1, min(15, int(cfg.get("lead_minutes", 2))))
    except Exception:
        cfg["lead_minutes"] = 2
    return cfg


def save_config(updates: dict) -> dict:
    cfg = load_config()
    cfg.update(updates or {})
    CFG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CFG_PATH.write_text(json.dumps(cfg, indent=2))
    return cfg


def _school_tz(cfg: dict):
    try:
        return ZoneInfo(cfg.get("timezone") or "America/Chicago")
    except Exception:
        return ZoneInfo("America/Chicago")


def schedule_for_day(cfg: dict, day_et: datetime) -> list[dict]:
    """Every alert for `day_et`, as ET datetimes.

    Anchored to each period's END minus lead_minutes, so the push lands while
    you're still in the room rather than in the hallway.
    """
    tz = _school_tz(cfg)
    lead = timedelta(minutes=cfg["lead_minutes"])
    local_day = day_et.astimezone(tz).date()
    out = []
    for p in cfg["periods"]:
        try:
            h, m = (int(x) for x in p["end"].split(":"))
        except Exception:
            continue
        end_local = datetime(local_day.year, local_day.month, local_day.day, h, m, tzinfo=tz)
        fire = (end_local - lead).astimezone(ET)
        out.append({
            "period": p.get("name", "?"),
            "ends_local": p["end"],
            "fire_et": fire,
            "fire_local": (end_local - lead).strftime("%H:%M"),
        })
    out.sort(key=lambda x: x["fire_et"])
    return out


def _market_open_at(dt_et: datetime) -> bool:
    """Regular session only. Half-days and holidays are handled by the live
    market check at fire time; this is the coarse filter for scheduling."""
    if dt_et.weekday() >= 5:
        return False
    hm = (dt_et.hour, dt_et.minute)
    return (9, 30) <= hm < (16, 0)


def next_alert(cfg: dict, now_et: datetime) -> dict | None:
    """The next alert strictly after `now_et`, skipping ones outside market hours."""
    for offset in range(0, 5):           # today, then look ahead over a weekend
        day = now_et + timedelta(days=offset)
        if cfg.get("weekdays_only", True) and day.weekday() >= 5:
            continue
        for a in schedule_for_day(cfg, day):
            if a["fire_et"] <= now_et:
                continue
            if cfg.get("skip_when_market_closed", True) and not _market_open_at(a["fire_et"]):
                continue
            return a
    return None


def usable_periods(cfg: dict, day_et: datetime) -> tuple[list, list]:
    """(alerts that land during market hours, alerts that don't) — for the UI,
    so it's obvious up front which bells can never fire."""
    live, dead = [], []
    for a in schedule_for_day(cfg, day_et):
        (live if _market_open_at(a["fire_et"]) else dead).append(a)
    return live, dead


# ── Message formatting ─────────────────────────────────────────────────────

def format_smallcap(period: str, res: dict, max_picks: int) -> tuple[str, str]:
    cands = (res.get("candidates") or [])[:max_picks]
    mode = res.get("mode", "?")
    if not cands:
        return (f"{period} — nothing qualifying",
                f"Scanned {res.get('scanned', 0)} gainers, no setup cleared the "
                f"{mode} filters. Sitting out is the trade.")
    lines = []
    for c in cands:
        risk = (c["entry"] - c["stop"]) / c["entry"] * 100 if c["entry"] else 0
        line = (f"{c['ticker']} ${c['entry']:.2f} · {c['setup']} · grade {c['grade']}\n"
                f"  stop ${c['stop']:.2f} (-{risk:.1f}%) · RVOL {c['rvol']} · {c['chg']:+.0f}%")
        if c.get("hazards"):
            line += f"\n  ⚠ {c['hazards'][0]}"
        if c.get("size_mult", 1) < 1:
            line += f"\n  size x{c['size_mult']}"
        lines.append(line)
    return (f"{period} — {len(cands)} setup{'s' if len(cands) > 1 else ''} ({mode})",
            "\n".join(lines))


def format_core(period: str, picks: list, max_picks: int) -> tuple[str, str]:
    picks = [p for p in (picks or []) if str(p.get("action", "")).upper().startswith("BUY")][:max_picks]
    if not picks:
        return (f"{period} — no buys", "Scan finished with nothing above threshold.")
    lines = []
    for p in picks:
        tr = p.get("trade") or {}
        bit = f"{p['ticker']} ${p.get('price', 0):.2f} · score {p.get('score', 0)}"
        if tr.get("entry") and tr.get("stop"):
            bit += f"\n  entry ${tr['entry']:.2f} · stop ${tr['stop']:.2f}"
            if tr.get("risk_reward"):
                bit += f" · {tr['risk_reward']:.1f}R"
        if p.get("signals"):
            bit += f"\n  {p['signals'][0]}"
        lines.append(bit)
    return (f"{period} — {len(picks)} pick{'s' if len(picks) > 1 else ''}", "\n".join(lines))
