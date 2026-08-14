"""Tests for bell_alerts.py — the class-schedule notification scheduler.

The bug class these exist for: the schedule is written in school-local time and
the market runs on ET. An hour's drift would fire every alert into the wrong
part of the session, and nothing about the notification would look wrong.
"""
import os
import sys
from datetime import datetime, timedelta

_BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, _BACKEND)

import bell_alerts as b  # noqa: E402

ET = b.ET
FRI = datetime(2026, 8, 14, 8, 0, tzinfo=ET)


def _cfg(**over):
    c = dict(b.DEFAULTS)
    c["periods"] = b.DEFAULT_PERIODS
    c.update(over)
    return c


def test_central_school_time_converts_to_eastern_market_time():
    """1st period ends 8:35 school time; with a 2-min lead that is 09:33 ET,
    three minutes after the opening bell — not 08:33 ET, which is premarket."""
    a = b.schedule_for_day(_cfg(), FRI)[0]
    assert a["period"] == "1st"
    assert a["fire_et"].strftime("%H:%M") == "09:33"
    assert a["fire_local"] == "08:33"


def test_alerts_land_before_the_period_ends_not_after():
    for a in b.schedule_for_day(_cfg(lead_minutes=2), FRI):
        end_h, end_m = (int(x) for x in a["ends_local"].split(":"))
        fire_h, fire_m = (int(x) for x in a["fire_local"].split(":"))
        assert fire_h * 60 + fire_m == end_h * 60 + end_m - 2


def test_lead_time_is_configurable_and_clamped():
    assert b.load_config()["lead_minutes"] >= 1
    a = b.schedule_for_day(_cfg(lead_minutes=5), FRI)[0]
    assert a["fire_local"] == "08:30"


def test_last_period_is_reported_as_never_firing():
    """7th ends 15:15 CT = 16:15 ET, after the close. It must be surfaced as
    dead rather than silently never arriving."""
    live, dead = b.usable_periods(_cfg(), FRI)
    assert [a["period"] for a in dead] == ["7th"]
    assert len(live) == 7


def test_next_alert_skips_closed_market_slots():
    after_6th = datetime(2026, 8, 14, 15, 30, tzinfo=ET)
    nxt = b.next_alert(_cfg(), after_6th)
    assert nxt["period"] == "1st"          # rolls to the next day, not 7th
    assert nxt["fire_et"].date() > after_6th.date()


def test_friday_evening_rolls_to_monday():
    fri_night = datetime(2026, 8, 14, 20, 0, tzinfo=ET)
    nxt = b.next_alert(_cfg(), fri_night)
    assert nxt["fire_et"].weekday() == 0, nxt["fire_et"]


def test_no_alert_is_scheduled_on_a_weekend():
    sat = datetime(2026, 8, 15, 8, 0, tzinfo=ET)
    nxt = b.next_alert(_cfg(), sat)
    assert nxt["fire_et"].weekday() < 5


def test_next_alert_is_strictly_in_the_future():
    exact = None
    for a in b.schedule_for_day(_cfg(), FRI):
        if b._market_open_at(a["fire_et"]):
            exact = a["fire_et"]
            break
    nxt = b.next_alert(_cfg(), exact)
    assert nxt["fire_et"] > exact, "an alert at exactly now must not re-fire"


def test_dst_transition_keeps_the_alert_in_school_time():
    """In November the US shifts; school time and ET shift together, so the
    local fire time must not move even though the UTC offset does."""
    nov = datetime(2026, 11, 5, 8, 0, tzinfo=ET)
    assert b.schedule_for_day(_cfg(), nov)[0]["fire_local"] == "08:33"


def test_a_non_central_school_still_maps_correctly():
    a = b.schedule_for_day(_cfg(timezone="America/New_York"), FRI)[0]
    assert a["fire_et"].strftime("%H:%M") == "08:33"   # same zone, no shift
    assert not b._market_open_at(a["fire_et"])          # and thus premarket


def test_bad_timezone_falls_back_instead_of_crashing():
    a = b.schedule_for_day(_cfg(timezone="Not/AZone"), FRI)[0]
    assert a["fire_et"].strftime("%H:%M") == "09:33"


def test_malformed_period_is_skipped_not_fatal():
    cfg = _cfg(periods=[{"name": "bad", "end": "nope"}, {"name": "ok", "end": "10:00"}])
    got = b.schedule_for_day(cfg, FRI)
    assert [a["period"] for a in got] == ["ok"]


def test_smallcap_message_reports_an_empty_scan_honestly():
    title, body = b.format_smallcap("3rd", {"candidates": [], "scanned": 41, "mode": "strict"}, 3)
    assert "nothing qualifying" in title
    assert "41" in body


def test_smallcap_message_carries_entry_stop_and_hazard():
    res = {"mode": "aggro", "scanned": 30, "candidates": [{
        "ticker": "ABCD", "price": 5.0, "chg": 22.0, "rvol": 7.1, "float": 2e7,
        "setup": "VWAP reclaim", "grade": 88, "entry": 5.00, "stop": 4.75,
        "notes": [], "catalyst": "real", "hazards": ["effective S-3 shelf"],
        "size_mult": 0.5}]}
    title, body = b.format_smallcap("2nd", res, 3)
    assert "ABCD" in body and "$5.00" in body and "$4.75" in body
    assert "-5.0%" in body                      # risk shown as a percentage
    assert "S-3" in body and "x0.5" in body


def test_core_message_ignores_non_buy_picks():
    picks = [{"ticker": "AAA", "action": "SELL", "price": 10, "score": 90},
             {"ticker": "BBB", "action": "BUY", "price": 20, "score": 88,
              "trade": {"entry": 20, "stop": 19, "risk_reward": 2.5}, "signals": ["above VWAP"]}]
    title, body = b.format_core("1st", picks, 3)
    assert "BBB" in body and "AAA" not in body
    assert "2.5R" in body


def test_max_picks_is_respected():
    res = {"mode": "strict", "scanned": 10, "candidates": [
        {"ticker": f"T{i}", "price": 5, "chg": 10, "rvol": 6, "float": 2e7,
         "setup": "flag", "grade": 80, "entry": 5, "stop": 4.8, "notes": [],
         "catalyst": "real", "hazards": [], "size_mult": 1} for i in range(6)]}
    _, body = b.format_smallcap("4th", res, 2)
    assert body.count("grade 80") == 2


def main():
    tests = [(n, o) for n, o in sorted(globals().items())
             if n.startswith("test_") and callable(o)]
    print("bell-alert tests")
    failed = 0
    for name, fn in tests:
        try:
            fn(); print(f"  PASS  {name}")
        except AssertionError as e:
            failed += 1; print(f"  FAIL  {name}: {e}")
        except Exception as e:
            failed += 1; print(f"  ERROR {name}: {type(e).__name__}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
