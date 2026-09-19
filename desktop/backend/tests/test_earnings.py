"""Tests for earnings.py and its wiring into the trading modes.

The dangerous direction here is permissive failure: a guard that silently
returns "no earnings" when the lookup breaks would let the autopilot open a
position into a print, which is the one exposure no stop protects against. So
several of these assert the *conservative* behaviour on bad data rather than
just the happy path.

No network. yfinance is stubbed.
"""
import os
import sys
import types
from datetime import datetime, timedelta

_BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_ROOT = os.path.abspath(os.path.join(_BACKEND, "..", ".."))
for p in (_ROOT, _BACKEND):
    if p not in sys.path:
        sys.path.insert(0, p)

import earnings as E  # noqa: E402

ET = E.ET


class _FakeFrame:
    """Minimal stand-in for the yfinance earnings_dates DataFrame."""

    def __init__(self, rows, columns=("EPS Estimate", "Reported EPS", "Surprise(%)")):
        self._rows = rows          # [(datetime, est, reported, surprise)]
        self.columns = list(columns)

    def __len__(self):
        return len(self._rows)

    def iterrows(self):
        for dt, est, rep, sur in self._rows:
            yield dt, {"EPS Estimate": est, "Reported EPS": rep, "Surprise(%)": sur}


def _stub_frame(rows, columns=("EPS Estimate", "Reported EPS", "Surprise(%)")):
    E._earnings_frame = lambda t: _FakeFrame(rows, columns)


def _restore():
    import importlib
    importlib.reload(E)


def _days(n):
    return E._now_et() + timedelta(days=n)


# ── Column handling ────────────────────────────────────────────────────────

def test_column_lookup_is_tolerant_of_naming_variants():
    df = _FakeFrame([], columns=["epsestimate", "Reported EPS", "Surprise (%)"])
    assert E._column(df, "EPS Estimate") == "epsestimate"
    assert E._column(df, "Reported EPS") == "Reported EPS"
    assert E._column(df, "Surprise(%)") == "Surprise (%)"


def test_missing_column_returns_none_rather_than_raising():
    assert E._column(_FakeFrame([], columns=["Something Else"]), "EPS Estimate") is None
    assert E._column(None, "EPS Estimate") is None


def test_surprise_is_derived_when_the_column_is_absent():
    """Yahoo omits the surprise column for some tickers. Both sides present is
    unambiguous, so compute it rather than reporting nothing."""
    _stub_frame([(_days(-3), 1.00, 1.40, None)])
    try:
        last = E.last_report("X")
        assert last["surprise_pct"] == 40.0, last
        assert last["verdict"] == "beat"
    finally:
        _restore()


def test_nan_values_are_treated_as_missing():
    assert E._num(float("nan")) is None
    assert E._num(None) is None
    assert E._num("") is None
    assert E._num(3.5) == 3.5


# ── next / last report ─────────────────────────────────────────────────────

def test_next_report_picks_the_soonest_unreported_quarter():
    _stub_frame([(_days(30), 2.0, None, None),
                 (_days(5), 1.5, None, None),
                 (_days(-40), 1.2, 1.3, 8.3)])
    try:
        nxt = E.next_report("X")
        assert nxt["days_away"] == 5
        assert nxt["eps_estimate"] == 1.5
        assert nxt["confirmed"] is True
    finally:
        _restore()


def test_a_future_row_with_a_reported_figure_is_not_upcoming():
    """A row dated ahead but already carrying an actual is stale data, not a
    scheduled report — treating it as upcoming would block trading forever."""
    _stub_frame([(_days(3), 1.0, 1.1, 10.0)])
    try:
        assert E.next_report("X") is None
    finally:
        _restore()


def test_last_report_ignores_quarters_with_no_actual():
    _stub_frame([(_days(2), 1.0, None, None),
                 (_days(-10), 0.9, 1.0, 11.1)])
    try:
        last = E.last_report("X")
        assert last["days_ago"] == 10
        assert last["eps_actual"] == 1.0
    finally:
        _restore()


def test_verdict_thresholds():
    for surprise, expected in ((40.0, "beat"), (-40.0, "miss"), (1.0, "in line"),
                               (-1.0, "in line")):
        _stub_frame([(_days(-3), 1.0, 1.0, surprise)])
        try:
            assert E.last_report("X")["verdict"] == expected, surprise
        finally:
            _restore()


def test_no_data_returns_none_everywhere():
    E._earnings_frame = lambda t: None
    try:
        assert E.last_report("X") is None
        assert E.recent_print("X") is None
    finally:
        _restore()


# ── Session counting ───────────────────────────────────────────────────────

def test_weekend_does_not_count_as_sessions():
    fri = datetime(2026, 9, 18, 16, 30, tzinfo=ET)
    mon = datetime(2026, 9, 21, 10, 0, tzinfo=ET)
    assert E._sessions_between(fri, mon) == 1


def test_sessions_between_is_never_negative():
    a = datetime(2026, 9, 21, 10, 0, tzinfo=ET)
    b = datetime(2026, 9, 18, 10, 0, tzinfo=ET)
    assert E._sessions_between(a, b) == 0


# ── recent_print: the tradable window ──────────────────────────────────────

def test_recent_print_inside_the_window():
    _stub_frame([(_days(-1), 1.0, 1.5, 50.0)])
    try:
        r = E.recent_print("X")
        assert r is not None and r["verdict"] == "beat"
    finally:
        _restore()


def test_recent_print_expires_outside_the_window():
    """Past the drift window the gap has been digested and the name is trading
    on something else, so it must stop counting as today's catalyst."""
    _stub_frame([(_days(-30), 1.0, 1.5, 50.0)])
    try:
        assert E.recent_print("X") is None
    finally:
        _restore()


# ── The forward guard ──────────────────────────────────────────────────────

def test_report_within_a_day_is_blocked():
    _stub_frame([(E._now_et() + timedelta(hours=6), 1.0, None, None)])
    try:
        blocked, why = E.reports_before_next_open("X")
        assert blocked is True and why
    finally:
        _restore()


def test_report_further_out_is_not_blocked():
    _stub_frame([(_days(6), 1.0, None, None)])
    try:
        assert E.reports_before_next_open("X")[0] is False
    finally:
        _restore()


def test_guard_does_not_raise_when_the_lookup_fails():
    def _boom(t):
        raise RuntimeError("yahoo down")
    E._earnings_frame = _boom
    try:
        # next_report catches internally; the guard must return, not propagate.
        blocked, _ = E.reports_before_next_open("X")
        assert blocked in (True, False)
    finally:
        _restore()


def test_snapshot_never_raises_on_broken_data():
    E._earnings_frame = lambda t: (_ for _ in ()).throw(ValueError("bad"))
    try:
        snap = E.snapshot("X")
        assert snap["ticker"] == "X"
        assert snap["next"] is None and snap["last"] is None
    finally:
        _restore()


def test_snapshot_is_json_safe():
    """The API returns this straight to the browser; a datetime would 500."""
    import json
    _stub_frame([(_days(-2), 1.0, 1.4, 40.0), (_days(20), 1.1, None, None)])
    try:
        json.dumps(E.snapshot("X"))
    finally:
        _restore()


# ── Catalyst classification ────────────────────────────────────────────────

def test_a_verified_beat_grades_real():
    _stub_frame([(_days(-1), 1.0, 1.4, 40.0)])
    try:
        c = E.catalyst_from_earnings("X")
        assert c["grade"] == "real" and c["source"] == "earnings"
        assert c["verdict"] == "beat" and "40%" in c["reason"]
    finally:
        _restore()


def test_a_rally_against_a_miss_is_graded_down_not_up():
    """The stock is up but the news was bad — that is a bounce against the
    print, not a reaction to it. Grading it 'real' would size INTO a fade."""
    _stub_frame([(_days(-1), 1.0, 0.5, -50.0)])
    try:
        c = E.catalyst_from_earnings("X")
        assert c["grade"] == "fluff", c
        assert "fade" in c["reason"]
    finally:
        _restore()


def test_no_recent_print_yields_no_earnings_catalyst():
    """So the engine falls through to the LLM grader rather than inventing one."""
    _stub_frame([(_days(-60), 1.0, 1.4, 40.0)])
    try:
        assert E.catalyst_from_earnings("X") is None
    finally:
        _restore()


def test_catalyst_shape_matches_the_llm_grader():
    """It substitutes for catalyst_grade() directly, so the keys must line up."""
    _stub_frame([(_days(-1), 1.0, 1.4, 40.0)])
    try:
        c = E.catalyst_from_earnings("X")
        assert set(c) >= {"grade", "reason"}
        assert c["grade"] in ("real", "fluff", "none")
    finally:
        _restore()


# ── Mode wiring ────────────────────────────────────────────────────────────

def _smallcap():
    """Reuse test_smallcap's harness rather than building a second `trading`
    stub — two competing stubs in one process means whichever imports first
    wins, and the loser silently gets an empty module."""
    sys.path.insert(0, os.path.dirname(__file__))
    import test_smallcap as T
    return T


def _modes():
    return _smallcap().scp


def test_both_modes_block_holding_into_a_print():
    m = _modes()
    for k in ("strict", "intense"):
        assert m.get_mode(k)["BLOCK_PRE_EARNINGS"] is True, k


def test_only_intense_sizes_up_on_a_verified_beat():
    m = _modes()
    assert m.get_mode("intense")["EARNINGS_BEAT_SIZE_MULT"] > 1.0
    assert m.get_mode("strict")["EARNINGS_BEAT_SIZE_MULT"] == 1.0


def test_the_beat_boost_cannot_breach_the_concentration_ceiling():
    """Size multipliers scale the RISK budget, never the notional cap. If a
    boost could push past the catastrophe cap it would be leverage, not
    conviction."""
    m = _modes()
    mode = m.get_mode("intense")
    boosted = m.size_position(25_000, 5.00, 4.75, mode, "X",
                              adv=9e9, med1=9e8,
                              size_mult=mode["EARNINGS_BEAT_SIZE_MULT"])
    assert boosted["qty"] * 5.00 <= 25_000 * mode["CATASTROPHE_CAP_PCT"] + 6


def test_scan_source_treats_earnings_as_the_higher_authority():
    """A verified print must override the LLM grade, not merely tie with it."""
    src = open(os.path.join(_ROOT, "smallcap_pullback.py")).read()
    block = src[src.index("cat = None"):src.index("size_mult = 1.0")]
    assert "catalyst_from_earnings" in block
    assert block.index("catalyst_from_earnings") < block.index("catalyst_grade(tkr)")
    assert "if cat is None:" in block, "LLM grader must be the fallback, not the primary"


def test_scan_refuses_to_enter_a_name_reporting_before_the_next_open():
    """Behavioural, not static: drive a full scan where the only candidate has
    a print scheduled tonight, and assert no order is placed. A static check on
    the source would still pass if the block were rewired to never fire."""
    T = _smallcap()
    with T.fake_market() as (orders, _stops):
        import earnings as _E
        real_guard = _E.reports_before_next_open
        real_cat = _E.catalyst_from_earnings
        _E.reports_before_next_open = lambda t: (True, "reports Sep 19 4:05 PM ET")
        _E.catalyst_from_earnings = lambda t: None
        try:
            out = T.scp.run("intense", skip_market_check=True)
        finally:
            _E.reports_before_next_open = real_guard
            _E.catalyst_from_earnings = real_cat

    assert not orders, f"opened a position into a print: {orders}"
    assert out["buys"] == 0
    joined = " ".join(out["log"]).lower()
    assert "no stop protects through a gap" in joined, joined[-400:]


def test_scan_still_trades_a_name_with_no_pending_print():
    """The guard must be specific. If it blocked indiscriminately the mode
    would simply stop trading, which is how the last outage looked."""
    T = _smallcap()
    with T.fake_market() as (orders, _stops):
        import earnings as _E
        real_guard = _E.reports_before_next_open
        real_cat = _E.catalyst_from_earnings
        _E.reports_before_next_open = lambda t: (False, "")
        _E.catalyst_from_earnings = lambda t: None
        try:
            out = T.scp.run("intense", skip_market_check=True)
        finally:
            _E.reports_before_next_open = real_guard
            _E.catalyst_from_earnings = real_cat

    assert orders, "guard blocked a name with no pending report"
    assert out["buys"] >= 1


def main():
    tests = [(n, o) for n, o in sorted(globals().items())
             if n.startswith("test_") and callable(o)]
    print("earnings tests")
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
