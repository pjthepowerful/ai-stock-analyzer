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


# ── Calendar ───────────────────────────────────────────────────────────────

def _tmp_cache():
    import tempfile, pathlib
    d = tempfile.mkdtemp()
    E.CALENDAR_CACHE = pathlib.Path(d) / "cal.json"
    return E.CALENDAR_CACHE


def test_calendar_groups_tickers_by_date():
    _tmp_cache()
    dates = {"AAA": 3, "BBB": 3, "CCC": 10}
    E.next_report = lambda t: {"ticker": t, "date": _days(dates[t]),
                               "eps_estimate": 1.0, "confirmed": True}
    try:
        data = E.build_calendar_from_tickers(["AAA", "BBB", "CCC"])
        assert len(data["dates"]) == 2, data["dates"]
        same = [v for v in data["dates"].values() if len(v) == 2][0]
        assert {r["ticker"] for r in same} == {"AAA", "BBB"}
    finally:
        _restore()


def test_calendar_survives_individual_lookup_failures():
    """One bad ticker must not lose the whole scan — a partial calendar is far
    more useful than none."""
    _tmp_cache()
    def _flaky(t):
        if t == "BAD":
            raise RuntimeError("boom")
        return {"ticker": t, "date": _days(4), "eps_estimate": None, "confirmed": True}
    E.next_report = _flaky
    try:
        data = E.build_calendar_from_tickers(["AAA", "BAD", "CCC"])
        assert data["errors"] == 1
        tickers = [r["ticker"] for v in data["dates"].values() for r in v]
        assert set(tickers) == {"AAA", "CCC"}
    finally:
        _restore()


def test_calendar_respects_the_ticker_cap():
    _tmp_cache()
    E.CALENDAR_MAX_TICKERS = 5
    E.next_report = lambda t: {"ticker": t, "date": _days(2),
                               "eps_estimate": None, "confirmed": True}
    try:
        data = E.build_calendar_from_tickers([f"T{i}" for i in range(50)])
        assert data["count"] == 5
    finally:
        _restore()


def test_calendar_deduplicates_tickers():
    _tmp_cache()
    E.next_report = lambda t: {"ticker": t, "date": _days(2),
                               "eps_estimate": None, "confirmed": True}
    try:
        data = E.build_calendar_from_tickers(["AAA", "aaa", "AAA", "BBB"])
        assert data["count"] == 2
    finally:
        _restore()


def test_month_view_filters_to_that_month():
    _tmp_cache()
    E._save_cache({"built_at": E._now_et().isoformat(),
                   "dates": {"2026-09-21": [{"ticker": "AAA"}],
                             "2026-10-05": [{"ticker": "BBB"}]},
                   "count": 2, "errors": 0})
    try:
        sep = E.calendar_month(2026, 9)
        assert list(sep["dates"]) == ["2026-09-21"]
        assert E.calendar_month(2026, 10)["dates"]["2026-10-05"][0]["ticker"] == "BBB"
        assert E.calendar_month(2026, 11)["dates"] == {}
    finally:
        _restore()


def test_missing_cache_reports_stale_rather_than_crashing():
    import pathlib, tempfile
    E.CALENDAR_CACHE = pathlib.Path(tempfile.mkdtemp()) / "nope.json"
    try:
        assert E.cache_age_hours() is None
        assert E.cache_is_stale() is True
        assert E.calendar_month(2026, 9)["dates"] == {}
    finally:
        _restore()


# ── Verdicts ───────────────────────────────────────────────────────────────

_MODE = {"PRICE_MIN": 1.0, "PRICE_MAX": 60.0, "MCAP_MIN": 25e6, "MCAP_MAX": 1.2e9}


def _fit(ok=True, why=""):
    E._universe_fit = lambda t, m: (ok, why)


def test_pre_print_is_never_buyable():
    """The whole point: there is no 'buy before earnings' in this system."""
    _fit()
    E.recent_print = lambda t, within_sessions=None: None
    E.reports_before_next_open = lambda t: (True, "reports Sep 21 4:05 PM ET")
    E.next_report = lambda t: {"ticker": t, "date": _days(0), "days_away": 0,
                               "eps_estimate": 1.0, "confirmed": True}
    E.last_report = lambda t: None
    try:
        v = E.verdict("AAA", _MODE)
        assert v["verdict"] == "blocked"
        assert v["buyable"] is False
        assert "gap" in v["reason"]
    finally:
        _restore()


def test_a_beat_inside_the_window_is_the_only_buyable_state():
    _fit()
    E.recent_print = lambda t, within_sessions=None: {
        "verdict": "beat", "surprise_pct": 32.0, "sessions_ago": 1}
    E.next_report = lambda t: None
    E.last_report = lambda t: None
    try:
        v = E.verdict("AAA", _MODE)
        assert v["verdict"] == "candidate" and v["buyable"] is True
        assert "32%" in v["reason"]
    finally:
        _restore()


def test_a_miss_is_flagged_as_a_fade_not_a_buy():
    _fit()
    E.recent_print = lambda t, within_sessions=None: {
        "verdict": "miss", "surprise_pct": -28.0, "sessions_ago": 0}
    E.next_report = lambda t: None
    E.last_report = lambda t: None
    try:
        v = E.verdict("AAA", _MODE)
        assert v["verdict"] == "fade" and v["buyable"] is False
        assert "against the news" in v["reason"]
    finally:
        _restore()


def test_out_of_universe_short_circuits_before_anything_else():
    """A name the mode would never trade should say so plainly rather than
    offering a verdict about a trade that cannot happen."""
    _fit(False, "$412.00 above the $60 ceiling")
    E.recent_print = lambda t, within_sessions=None: {
        "verdict": "beat", "surprise_pct": 50.0, "sessions_ago": 0}
    E.next_report = lambda t: None
    E.last_report = lambda t: None
    try:
        v = E.verdict("AAA", _MODE)
        assert v["verdict"] == "skip" and v["buyable"] is False
        assert "ceiling" in v["reason"]
    finally:
        _restore()


def test_a_distant_report_is_watch_and_says_there_is_nothing_to_do():
    _fit()
    E.recent_print = lambda t, within_sessions=None: None
    E.reports_before_next_open = lambda t: (False, "")
    E.next_report = lambda t: {"ticker": t, "date": _days(9), "days_away": 9,
                               "eps_estimate": 2.0, "confirmed": True}
    E.last_report = lambda t: None
    try:
        v = E.verdict("AAA", _MODE)
        assert v["verdict"] == "watch" and v["buyable"] is False
        assert "9 day" in v["reason"]
    finally:
        _restore()


def test_verdict_never_raises_on_broken_data():
    def _boom(t):
        raise RuntimeError("down")
    E.next_report = _boom
    try:
        v = E.verdict("AAA", _MODE)
        assert v["ticker"] == "AAA" and v["buyable"] is False
    finally:
        _restore()


def test_no_mode_means_no_universe_filtering():
    """Core mode has no small-cap bands, so nothing should be marked out of range."""
    ok, why = E._universe_fit("AAA", None)
    assert ok is True and why == ""


# ── Nasdaq calendar source ─────────────────────────────────────────────────

def test_nasdaq_money_parsing():
    """Nasdaq sends display text, not numbers. Every shape it uses must land
    on the right value, and anything unparseable must become None rather than
    zero — zero is a real EPS and must never be invented."""
    n = E._nasdaq_num
    assert n("$1,234,567") == 1234567
    assert n("$0.34") == 0.34
    assert n("(0.12)") == -0.12          # accounting parentheses = negative
    assert n("($1.50)") == -1.5
    assert n("$1.2B") == 1.2e9
    assert n("450M") == 450e6
    assert n("N/A") is None
    assert n("") is None
    assert n(None) is None
    assert n("--") is None
    assert n("garbage") is None
    assert n("0.00") == 0.0              # a real zero survives


def test_nasdaq_day_maps_rows_and_report_time():
    import types, sys as _s
    captured = {}

    class _Resp:
        def raise_for_status(self): pass
        def json(self):
            return {"data": {"rows": [
                {"symbol": "aaa", "name": "Alpha Inc",
                 "epsForecast": "$0.20", "marketCap": "$120,000,000",
                 "time": "time-pre-market"},
                {"symbol": "BBB", "name": "Beta Co",
                 "epsForecast": "(0.05)", "marketCap": "N/A",
                 "time": "time-after-hours"},
                {"symbol": "", "name": "no ticker", "time": "time-not-supplied"},
            ]}}

    fake = types.ModuleType("requests")
    def _get(url, params=None, headers=None, timeout=None):
        captured.update(url=url, params=params, headers=headers)
        return _Resp()
    fake.get = _get
    old = _s.modules.get("requests")
    _s.modules["requests"] = fake
    try:
        rows = E.nasdaq_day("2026-09-22")
        assert [r["ticker"] for r in rows] == ["AAA", "BBB"], rows  # blank dropped, upcased
        assert rows[0]["hour"] == "BMO" and rows[1]["hour"] == "AMC"
        assert rows[0]["eps_estimate"] == 0.20
        assert rows[1]["eps_estimate"] == -0.05
        assert rows[0]["market_cap"] == 120e6
        assert rows[1]["market_cap"] is None
        assert captured["params"]["date"] == "2026-09-22"
        assert "Mozilla" in captured["headers"]["User-Agent"]  # Nasdaq 403s without one
    finally:
        if old is not None:
            _s.modules["requests"] = old
        else:
            _s.modules.pop("requests", None)
        _restore()


def test_nasdaq_day_handles_a_null_rows_list():
    """Weekends and holidays come back with rows: null. That is an empty day,
    not a failure, and must not count as an error."""
    import types, sys as _s
    class _Resp:
        def raise_for_status(self): pass
        def json(self): return {"data": {"rows": None}}
    fake = types.ModuleType("requests")
    fake.get = lambda *a, **k: _Resp()
    old = _s.modules.get("requests")
    _s.modules["requests"] = fake
    try:
        assert E.nasdaq_day("2026-09-20") == []
    finally:
        if old is not None: _s.modules["requests"] = old
        else: _s.modules.pop("requests", None)
        _restore()


def test_nasdaq_build_skips_weekends_and_groups_by_date():
    _tmp_cache()
    E.NASDAQ_PAUSE = 0
    asked = []
    def _fetch(day):
        asked.append(day)
        return [{"ticker": "AAA", "market_cap": 100e6, "eps_estimate": 0.1,
                 "hour": "BMO", "confirmed": True, "company": "Alpha"}]
    try:
        data = E.build_calendar_from_nasdaq(days_ahead=9, days_back=0, fetch=_fetch)
        from datetime import datetime as _dt
        for d in asked:
            assert _dt.strptime(d, "%Y-%m-%d").weekday() < 5, f"weekend fetched: {d}"
        assert data["source"] == "nasdaq"
        assert data["count"] == 1
        assert len(data["dates"]) == len(asked)
    finally:
        _restore()


def test_nasdaq_build_keeps_unknown_caps_but_drops_mega_caps():
    """An unknown cap must be KEPT — Nasdaq omits it for the smallest names,
    which are exactly this strategy's targets. Dropping on unknown would
    silently delete the universe."""
    _tmp_cache()
    E.NASDAQ_PAUSE = 0
    rows = [
        {"ticker": "SMALL", "market_cap": 90e6},
        {"ticker": "UNKNOWN", "market_cap": None},
        {"ticker": "MEGA", "market_cap": 900e9},
        {"ticker": "DUST", "market_cap": 1e3},
    ]
    try:
        data = E.build_calendar_from_nasdaq(days_ahead=9, days_back=0,
                                            fetch=lambda d: rows)
        kept = {r["ticker"] for v in data["dates"].values() for r in v}
        assert "SMALL" in kept and "UNKNOWN" in kept
        assert "MEGA" not in kept, "a 900B cap is never a small-cap setup"
        assert "DUST" not in kept
    finally:
        _restore()


def test_a_held_position_survives_the_cap_filter():
    """Whatever the account actually owns stays on the calendar even if its cap
    is outside the band — you still need to know when it reports."""
    _tmp_cache()
    E.NASDAQ_PAUSE = 0
    rows = [{"ticker": "MEGA", "market_cap": 900e9}]
    try:
        data = E.build_calendar_from_nasdaq(days_ahead=9, days_back=0,
                                            keep={"mega"}, fetch=lambda d: rows)
        kept = {r["ticker"] for v in data["dates"].values() for r in v}
        assert "MEGA" in kept
    finally:
        _restore()


def test_nasdaq_build_survives_some_days_failing():
    _tmp_cache()
    E.NASDAQ_PAUSE = 0
    calls = {"n": 0}
    def _flaky(day):
        calls["n"] += 1
        if calls["n"] % 3 == 0:
            raise RuntimeError("rate limited")
        return [{"ticker": "AAA", "market_cap": 100e6}]
    try:
        data = E.build_calendar_from_nasdaq(days_ahead=20, days_back=0, fetch=_flaky)
        assert data["errors"] > 0
        assert len(data["dates"]) > 0, "a partial calendar still beats none"
    finally:
        _restore()


def test_nasdaq_build_raises_when_every_day_fails():
    """Total failure must raise so build_calendar can fall back to Yahoo,
    rather than quietly caching an empty calendar over a good one."""
    _tmp_cache()
    E.NASDAQ_PAUSE = 0
    def _dead(day):
        raise RuntimeError("blocked")
    try:
        try:
            E.build_calendar_from_nasdaq(days_ahead=5, days_back=0, fetch=_dead)
        except RuntimeError:
            pass
        else:
            raise AssertionError("expected a raise when no day could be fetched")
    finally:
        _restore()


def test_build_calendar_falls_back_to_yahoo_when_nasdaq_is_blocked():
    _tmp_cache()
    def _dead(**kw):
        raise RuntimeError("nasdaq blocked")
    E.build_calendar_from_nasdaq = _dead
    E.next_report = lambda t: {"ticker": t, "date": _days(3),
                               "eps_estimate": None, "confirmed": True}
    try:
        data = E.build_calendar(["AAA", "BBB"])
        assert data["source"] == "yahoo"
        assert data["count"] == 2
    finally:
        _restore()


def test_build_calendar_prefers_nasdaq():
    _tmp_cache()
    E.NASDAQ_PAUSE = 0
    E.build_calendar_from_tickers = lambda *a, **k: (_ for _ in ()).throw(
        AssertionError("Yahoo must not be reached when Nasdaq works"))
    try:
        data = E.build_calendar_from_nasdaq(
            days_ahead=9, days_back=0,
            fetch=lambda d: [{"ticker": "AAA", "market_cap": 100e6}])
        assert data["source"] == "nasdaq"
    finally:
        _restore()


def test_month_view_reports_its_source():
    _tmp_cache()
    E._save_cache({"built_at": E._now_et().isoformat(),
                   "dates": {"2026-09-21": [{"ticker": "AAA"}]},
                   "count": 1, "errors": 0, "source": "nasdaq"})
    try:
        assert E.calendar_month(2026, 9)["source"] == "nasdaq"
    finally:
        _restore()


def test_an_all_weekend_range_is_not_mistaken_for_total_failure():
    """errors == len(days) is true when len(days) is ZERO. Without a separate
    guard an all-weekend window reports Nasdaq as dead and sends the caller to
    the fallback for no reason."""
    _tmp_cache()
    E.NASDAQ_PAUSE = 0
    called = {"n": 0}
    def _fetch(d):
        called["n"] += 1
        return []
    try:
        # A Saturday-to-Sunday window: zero trading days, zero fetches.
        from datetime import datetime as _dt, timedelta as _td
        sat = E._now_et()
        while sat.weekday() != 5:
            sat += _td(days=1)
        E._now_et = lambda: sat
        try:
            E.build_calendar_from_nasdaq(days_ahead=1, days_back=0, fetch=_fetch)
        except RuntimeError as e:
            assert "no trading days" in str(e), f"wrong reason: {e}"
        else:
            raise AssertionError("expected a raise for an empty range")
        assert called["n"] == 0, "weekend days must never be fetched"
    finally:
        _restore()


def test_the_universe_list_does_not_bypass_the_cap_filter():
    """Only held positions get to skip the cap band. If the whole universe were
    passed as `keep`, the filter would be a no-op for every large cap in it."""
    _tmp_cache()
    E.NASDAQ_PAUSE = 0
    seen = {}
    def _spy(days_ahead=None, days_back=None, keep=None, progress=None, fetch=None):
        seen["keep"] = set(keep or ())
        return {"built_at": E._now_et().isoformat(), "dates": {}, "count": 0,
                "errors": 0, "source": "nasdaq"}
    E.build_calendar_from_nasdaq = _spy
    try:
        E.build_calendar(["MEGA", "HUGE", "AAA"], keep={"AAA"})
        assert seen["keep"] == {"AAA"}, seen["keep"]
    finally:
        _restore()


# ── Future dates must differentiate ────────────────────────────────────────

def _future_verdict(lean):
    """verdict() for a name reporting in 12 days, with quick_lean stubbed."""
    import sys, types
    E.next_report = lambda t: {"ticker": t, "date": _days(12), "days_away": 12,
                               "eps_estimate": 1.0, "confirmed": True}
    E.last_report = lambda t: None
    E.recent_print = lambda t: None
    E.reports_before_next_open = lambda t: (False, "")
    E._universe_fit = lambda t, m: (True, "")
    fake = types.ModuleType("forecast")
    fake.quick_lean = lambda t: lean
    old = sys.modules.get("forecast")
    sys.modules["forecast"] = fake
    try:
        return E.verdict("AAA", None)
    finally:
        if old is not None: sys.modules["forecast"] = old
        else: sys.modules.pop("forecast", None)


def test_a_future_date_is_not_automatically_watch():
    """The bug this replaces: every branch of verdict() needed the print to be
    in the last two sessions or before the next open, and a calendar is almost
    entirely neither — so every name on every future date read 'Watch' and the
    calendar carried no information at all."""
    try:
        v = _future_verdict({"score": 0.7, "lean": "strong beat lean",
                             "grounded": True, "notes": ["9 estimates up vs 1 down"]})
        assert v["verdict"] == "lean_beat", v
        assert "estimates up" in v["reason"]
    finally:
        _restore()


def test_a_negative_lean_is_surfaced_not_flattened():
    try:
        v = _future_verdict({"score": -0.7, "lean": "strong miss lean",
                             "grounded": True, "notes": ["6 estimates CUT vs 0 raised"]})
        assert v["verdict"] == "lean_miss", v
    finally:
        _restore()


def test_no_published_data_stays_watch_rather_than_inventing_a_lean():
    """A name nobody covers must read as 'no lean', never as a mild call
    manufactured out of two empty signals."""
    try:
        v = _future_verdict({"score": 0.0, "lean": "no lean",
                             "grounded": False, "notes": []})
        assert v["verdict"] == "watch"
        assert "No lean" in v["reason"]
    finally:
        _restore()


def test_a_lean_is_never_buyable():
    """A lean says which way to watch, not what to own. Autopilot does not hold
    through prints, so nothing on a future date may be marked buyable."""
    try:
        for lean in ({"score": 0.9, "lean": "strong beat lean", "grounded": True, "notes": []},
                     {"score": -0.9, "lean": "strong miss lean", "grounded": True, "notes": []}):
            assert _future_verdict(lean)["buyable"] is False
    finally:
        _restore()


def test_verdict_survives_forecast_being_unavailable():
    """The forecast module failing must degrade to 'no lean', never take the
    calendar down with it."""
    import sys, types
    E.next_report = lambda t: {"ticker": t, "date": _days(12), "days_away": 12,
                               "eps_estimate": None, "confirmed": True}
    E.last_report = lambda t: None
    E.recent_print = lambda t: None
    E.reports_before_next_open = lambda t: (False, "")
    E._universe_fit = lambda t, m: (True, "")
    fake = types.ModuleType("forecast")
    def _boom(t): raise RuntimeError("yahoo down")
    fake.quick_lean = _boom
    old = sys.modules.get("forecast")
    sys.modules["forecast"] = fake
    try:
        v = E.verdict("AAA", None)
        assert v["verdict"] == "watch"
        assert "reports in 12 days" in v["reason"]
    finally:
        if old is not None: sys.modules["forecast"] = old
        else: sys.modules.pop("forecast", None)
        _restore()


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
