"""Tests for pre-earnings forecasting.

This is the only forward-looking part of the app, so the failure that matters
is a confident-looking call with nothing behind it. The tests push hardest on:

  * missing data scoring NEUTRAL, never bullish — a name Yahoo publishes no
    revisions for must not inherit a beat lean by default;
  * the lean staying a direction rather than becoming a fake percentage;
  * typical_move, because it is the number that is supposed to stop a good
    forecast from being sized like a certainty.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))))))

import forecast as F  # noqa: E402


def _restore():
    import importlib
    importlib.reload(F)


class _FakeTicker:
    def __init__(self, revisions=None, trend=None):
        self.eps_revisions = revisions
        self.eps_trend = trend


def _yf(ticker_obj):
    import types
    m = types.ModuleType("yfinance")
    m.Ticker = lambda t: ticker_obj
    sys.modules["yfinance"] = m


def _unyf(real):
    if real is not None:
        sys.modules["yfinance"] = real
    else:
        sys.modules.pop("yfinance", None)


# ── Frame normalising ──────────────────────────────────────────────────────

def test_frame_rows_handles_every_shape_yfinance_returns():
    assert F._frame_rows(None) == []
    assert F._frame_rows({}) == []
    rows = F._frame_rows({"0q": {"upLast30days": 4}})
    assert rows and rows[0]["_key"] == "0q" and rows[0]["upLast30days"] == 4


def test_num_drops_nan():
    assert F._num(float("nan")) is None
    assert F._num("3.5") == 3.5
    assert F._num(None) is None
    assert F._num("abc") is None


# ── Revisions ──────────────────────────────────────────────────────────────

def test_upgrades_score_positive_and_cuts_score_negative():
    real = sys.modules.get("yfinance")
    try:
        _yf(_FakeTicker(revisions={"0q": {"upLast30days": 8, "downLast30days": 1}}))
        up = F.revision_signal("AAA")
        _yf(_FakeTicker(revisions={"0q": {"upLast30days": 1, "downLast30days": 8}}))
        down = F.revision_signal("AAA")
        assert up["score"] > 0.3 and down["score"] < -0.3
        assert "CUT" in down["note"]
    finally:
        _unyf(real); _restore()


def test_missing_revisions_score_neutral_not_bullish():
    """A name Yahoo publishes nothing for must not inherit a beat lean by
    default — absence of evidence is not evidence."""
    real = sys.modules.get("yfinance")
    try:
        _yf(_FakeTicker(revisions=None))
        r = F.revision_signal("AAA")
        assert r["available"] is False
        assert r["score"] == 0.0
    finally:
        _unyf(real); _restore()


def test_zero_revisions_either_way_is_not_a_signal():
    real = sys.modules.get("yfinance")
    try:
        _yf(_FakeTicker(revisions={"0q": {"upLast30days": 0, "downLast30days": 0}}))
        r = F.revision_signal("AAA")
        assert r["score"] == 0.0
        assert "no analyst moved" in r["note"]
    finally:
        _unyf(real); _restore()


def test_revision_signal_prefers_the_current_quarter_row():
    real = sys.modules.get("yfinance")
    try:
        _yf(_FakeTicker(revisions={
            "+1y": {"upLast30days": 0, "downLast30days": 9},
            "0q":  {"upLast30days": 9, "downLast30days": 0},
        }))
        assert F.revision_signal("AAA")["score"] > 0.5, "must read 0q, not +1y"
    finally:
        _unyf(real); _restore()


# ── Estimate drift ─────────────────────────────────────────────────────────

def test_estimate_drift_direction_and_zero_base():
    real = sys.modules.get("yfinance")
    try:
        _yf(_FakeTicker(trend={"0q": {"current": 1.15, "90daysAgo": 1.00}}))
        up = F.estimate_drift("AAA")
        assert up["change_pct"] == 15.0 and up["score"] > 0
        _yf(_FakeTicker(trend={"0q": {"current": 0.85, "90daysAgo": 1.00}}))
        assert F.estimate_drift("AAA")["score"] < 0
        # A zero base would divide by zero rather than mean "infinite growth".
        _yf(_FakeTicker(trend={"0q": {"current": 1.0, "90daysAgo": 0}}))
        z = F.estimate_drift("AAA")
        assert z["available"] is False and z["score"] == 0.0
    finally:
        _unyf(real); _restore()


def test_estimate_drift_falls_back_through_shorter_windows():
    real = sys.modules.get("yfinance")
    try:
        _yf(_FakeTicker(trend={"0q": {"current": 1.1, "30daysAgo": 1.0}}))
        assert F.estimate_drift("AAA")["available"] is True
    finally:
        _unyf(real); _restore()


# ── Beat history ───────────────────────────────────────────────────────────

class _FakeEarnings:
    ET = None

    def __init__(self, surprises):
        from zoneinfo import ZoneInfo
        _FakeEarnings.ET = ZoneInfo("US/Eastern")
        self.ET = _FakeEarnings.ET
        self.surprises = surprises

    def _earnings_frame(self, t):
        return "frame"

    def _rows(self, frame):
        from datetime import datetime, timedelta
        now = datetime.now(self.ET)
        return [(now - timedelta(days=90 * (i + 1)), 1.0, 1.0, s)
                for i, s in enumerate(self.surprises)]


def _earn(fake):
    sys.modules["earnings"] = fake


def test_a_serial_beater_scores_above_a_coin_flip():
    real = sys.modules.get("earnings")
    try:
        _earn(_FakeEarnings([20, 15, 12, 8, 10, 9, 14, 11]))
        serial = F.beat_history("AAA")
        _earn(_FakeEarnings([20, -15, 12, -8, 10, -9, 14, -11]))
        flip = F.beat_history("AAA")
        assert serial["beat_rate"] == 100 and serial["score"] > 0.9
        assert flip["beat_rate"] == 50
        assert abs(flip["score"]) < 0.01, "50% is no information, not a signal"
    finally:
        if real is not None: sys.modules["earnings"] = real
        else: sys.modules.pop("earnings", None)
        _restore()


def test_beat_history_is_capped_to_the_lookback():
    real = sys.modules.get("earnings")
    try:
        F.LOOKBACK_QUARTERS = 4
        _earn(_FakeEarnings([10] * 20))
        assert F.beat_history("AAA")["quarters"] == 4
    finally:
        if real is not None: sys.modules["earnings"] = real
        else: sys.modules.pop("earnings", None)
        _restore()


def test_no_history_scores_neutral():
    real = sys.modules.get("earnings")
    try:
        _earn(_FakeEarnings([]))
        h = F.beat_history("AAA")
        assert h["available"] is False and h["score"] == 0.0
    finally:
        if real is not None: sys.modules["earnings"] = real
        else: sys.modules.pop("earnings", None)
        _restore()


# ── Leans ──────────────────────────────────────────────────────────────────

def test_lean_is_a_direction_not_a_percentage():
    for score in (-1, -0.5, -0.2, 0, 0.2, 0.5, 1):
        lean = F._lean(score)
        assert isinstance(lean, str)
        assert "%" not in lean, "a lean must never render as a probability"


def test_lean_thresholds_are_ordered():
    assert F._lean(0.9) == "strong beat lean"
    assert F._lean(0.25) == "mild beat lean"
    assert F._lean(0.0) == "no lean"
    assert F._lean(-0.25) == "mild miss lean"
    assert F._lean(-0.9) == "strong miss lean"


def test_all_signals_missing_yields_no_lean():
    """Three blanks must not add up to a call."""
    real_y, real_e = sys.modules.get("yfinance"), sys.modules.get("earnings")
    try:
        _yf(_FakeTicker(revisions=None, trend=None))
        _earn(_FakeEarnings([]))
        F.typical_move = lambda t: {"available": False, "note": "n/a"}
        f = F.forecast("AAA")
        assert f["score"] == 0.0
        assert f["lean"] == "no lean"
    finally:
        _unyf(real_y)
        if real_e is not None: sys.modules["earnings"] = real_e
        else: sys.modules.pop("earnings", None)
        _restore()


def test_revisions_are_the_heaviest_single_leg():
    """Revisions are the best-documented of the three, so swinging that leg
    must move the score more than swinging either other leg. (It is the
    largest single weight, NOT a majority over the other two combined — an
    earlier version of this test asserted the stronger claim and was simply
    wrong about the design.)"""
    F.typical_move = lambda t: {"available": False, "note": ""}

    def _swing(leg):
        spread = []
        for v in (-1.0, 1.0):
            F.revision_signal = lambda t, v=v: {"score": v if leg == "rev" else 0.0, "note": ""}
            F.estimate_drift = lambda t, v=v: {"score": v if leg == "drift" else 0.0, "note": ""}
            F.beat_history = lambda t, v=v: {"score": v if leg == "hist" else 0.0, "note": ""}
            spread.append(F.forecast("AAA")["score"])
        return spread[1] - spread[0]

    try:
        rev, hist, drift = _swing("rev"), _swing("hist"), _swing("drift")
        assert rev > hist > drift, (rev, hist, drift)
    finally:
        _restore()


def test_zero_upgrades_is_a_count_not_a_missing_value():
    """`a or b` treats 0 as absent. With 0 raised and 3 cut in 30 days, falling
    through to the 7-day figure would mix two different windows into one
    number — and here would turn a clearly negative signal into a blank."""
    real = sys.modules.get("yfinance")
    try:
        _yf(_FakeTicker(revisions={"0q": {
            "upLast30days": 0, "downLast30days": 3,
            "upLast7days": 5, "downLast7days": 0,   # must be ignored
        }}))
        r = F.revision_signal("AAA")
        assert r["up"] == 0 and r["down"] == 3, r
        assert r["score"] < 0, "0 up vs 3 cut is a negative signal"
    finally:
        _unyf(real); _restore()


# ── Risk figure ────────────────────────────────────────────────────────────

def test_forecast_always_carries_a_risk_key():
    """The gap figure is what stops a confident lean being sized like a
    certainty, so it must be present on every row even when unmeasurable."""
    F.revision_signal = lambda t: {"score": 0.9, "note": "strong"}
    F.estimate_drift = lambda t: {"score": 0.9, "note": "up"}
    F.beat_history = lambda t: {"score": 0.9, "note": "beats"}
    F.typical_move = lambda t: {"available": False, "note": "could not measure"}
    try:
        f = F.forecast("AAA")
        assert "risk" in f and f["risk"] is not None
        assert f["lean"] == "strong beat lean"
        assert any("could not measure" in e for e in f["evidence"])
    finally:
        _restore()


def test_typical_move_never_raises_on_broken_data():
    real_y, real_e = sys.modules.get("yfinance"), sys.modules.get("earnings")
    try:
        _yf(_FakeTicker())
        _earn(_FakeEarnings([]))
        m = F.typical_move("AAA")
        assert m["available"] is False and m["note"]
    finally:
        _unyf(real_y)
        if real_e is not None: sys.modules["earnings"] = real_e
        else: sys.modules.pop("earnings", None)
        _restore()


# ── Ranking / progress ─────────────────────────────────────────────────────

def test_rank_sorts_by_score_and_reports_progress():
    seen = []
    F.forecast = lambda t: {"ticker": t, "score": {"A": 0.1, "B": 0.9, "C": 0.5}[t]}
    try:
        rows = F.rank(["A", "B", "C"], progress=lambda d, t, l: seen.append((d, t, l)))
        assert [r["ticker"] for r in rows] == ["B", "C", "A"]
        assert seen[-1][0] == seen[-1][1] == 3, "the final tick must reach 100%"
        assert seen[0][2] == "A"
    finally:
        _restore()


def test_rank_survives_a_failing_name_and_still_finishes_progress():
    def _f(t):
        if t == "BAD":
            raise RuntimeError("boom")
        return {"ticker": t, "score": 0.5}
    F.forecast = _f
    seen = []
    try:
        rows = F.rank(["A", "BAD", "C"], progress=lambda d, t, l: seen.append(d))
        assert {r["ticker"] for r in rows} == {"A", "C"}
        assert seen[-1] == 3, "progress must complete even when a name fails"
    finally:
        _restore()


# ── The stock lean: a beat is not the same as the stock going up ──────────

def _rx(pairs, runups=None):
    """Stub _reactions with (surprise, move) pairs."""
    runups = runups or [0] * len(pairs)
    F._reactions = lambda t: ([{"surprise": s, "move_pct": m, "runup_pct": r}
                               for (s, m), r in zip(pairs, runups)], "")


def test_a_company_that_beats_and_falls_is_flagged():
    """The case the whole thing exists for: reliably beats, stock drops anyway
    because the call keeps disappointing. This must NOT read as bullish."""
    try:
        _rx([(20, -8), (15, -12), (10, -5), (25, 3)])
        r = F.reaction_history("AAA")
        assert r["beats"] == 4 and r["beats_up"] == 1
        assert r["score"] < -0.4, r
        assert "FELL on 3" in r["note"], r["note"]
    finally:
        _restore()


def test_a_company_that_reliably_pops_on_beats_scores_positive():
    try:
        _rx([(20, 9), (15, 12), (10, 4), (25, 7)])
        r = F.reaction_history("AAA")
        assert r["beat_up_rate"] == 100 and r["score"] > 0.9
        assert "all 4" in r["note"]
    finally:
        _restore()


def test_misses_do_not_pollute_the_beat_reaction_stat():
    """Only beats answer 'does beating help'. A miss falling is not evidence
    that a beat would have."""
    try:
        _rx([(20, 5), (-30, -20), (-25, -18), (10, 4)])
        r = F.reaction_history("AAA")
        assert r["beats"] == 2 and r["beats_up"] == 2
        assert r["score"] > 0.9, "the two crashes on misses must not count"
    finally:
        _restore()


def test_no_beats_in_the_window_is_stated_not_scored():
    try:
        _rx([(-10, -4), (-20, -9)])
        r = F.reaction_history("AAA")
        assert r["available"] is False and r["score"] == 0.0
        assert "no beats" in r["note"]
    finally:
        _restore()


def test_typical_move_and_reaction_share_one_fetch():
    """Both derive from _reactions, so a name costs one price download, not
    two. Verified by counting calls."""
    calls = {"n": 0}
    def _counted(t):
        calls["n"] += 1
        return ([{"surprise": 10, "move_pct": -6, "runup_pct": 0}], "")
    F._reactions = _counted
    try:
        F.typical_move("AAA"); F.reaction_history("AAA")
        assert calls["n"] == 2, "one fetch each, not one per signal inside them"
        # And the risk figure is unsigned while the reaction figure is signed.
        F._reactions = _counted
        assert F.typical_move("AAA")["typical_move_pct"] == 6.0
    finally:
        _restore()


def test_a_big_runup_scores_negative_and_a_flat_stock_scores_zero():
    """Buy the rumour, sell the news — but only a LARGE run-up is informative.
    A flat stock into a print says nothing and must score neutral."""
    import types, sys as _s
    class _H:
        def __init__(self, closes): self._c = closes
        empty = False
        def iterrows(self):
            return [(i, {"Close": c}) for i, c in enumerate(self._c)]
    def _mk(closes):
        m = types.ModuleType("yfinance")
        m.Ticker = lambda t: type("T", (), {"history": lambda s, **k: _H(closes)})()
        _s.modules["yfinance"] = m
    old = _s.modules.get("yfinance")
    try:
        _mk([100.0] * 20 + [140.0])          # +40% into the print
        hot = F.runup("AAA")
        assert hot["runup_pct"] == 40.0 and hot["score"] < -0.5
        assert "priced in" in hot["note"]

        _mk([100.0] * 21)                     # flat
        flat = F.runup("AAA")
        assert flat["score"] == 0.0, "a flat stock is not a signal"
    finally:
        if old is not None: _s.modules["yfinance"] = old
        else: _s.modules.pop("yfinance", None)
        _restore()


def test_runup_needs_enough_sessions():
    import types, sys as _s
    class _H:
        empty = False
        def iterrows(self): return [(i, {"Close": 100.0}) for i in range(5)]
    m = types.ModuleType("yfinance")
    m.Ticker = lambda t: type("T", (), {"history": lambda s, **k: _H()})()
    old = _s.modules.get("yfinance")
    _s.modules["yfinance"] = m
    try:
        r = F.runup("AAA")
        assert r["available"] is False and "not enough sessions" in r["note"]
    finally:
        if old is not None: _s.modules["yfinance"] = old
        else: _s.modules.pop("yfinance", None)
        _restore()


def _stub_legs(earn_score, react_score, run_score, react_avail=True, run_avail=True):
    F.revision_signal = lambda t: {"score": earn_score, "note": ""}
    F.estimate_drift = lambda t: {"score": earn_score, "note": ""}
    F.beat_history = lambda t: {"score": earn_score, "note": ""}
    F.typical_move = lambda t: {"available": False, "note": ""}
    F.reaction_history = lambda t: {"score": react_score, "available": react_avail, "note": ""}
    F.runup = lambda t: {"score": run_score, "available": run_avail, "note": ""}


def test_the_stock_lean_is_never_blended_into_the_earnings_lean():
    """The point of two numbers. A company that reliably beats whose stock
    reliably sells off must show BOTH — averaging them into one mild positive
    hides the single most useful fact on the row."""
    try:
        _stub_legs(earn_score=0.9, react_score=-0.9, run_score=-0.5)
        f = F.forecast("AAA")
        assert f["lean"] == "strong beat lean", f["lean"]
        assert f["stock_lean"] == "often falls anyway", f["stock_lean"]
        assert f["score"] > 0.8, "the earnings lean must not be dragged down"
        assert f["stock_score"] < -0.5
    finally:
        _restore()


def test_the_stock_lean_is_not_asked_when_no_beat_is_expected():
    """'How does it react to beats' is only a question if a beat is coming."""
    try:
        _stub_legs(earn_score=-0.9, react_score=0.9, run_score=0.0)
        f = F.forecast("AAA")
        assert f["stock_lean"] == "n/a — no beat expected", f["stock_lean"]
    finally:
        _restore()


def test_the_stock_lean_is_unknown_when_nothing_was_measurable():
    try:
        _stub_legs(earn_score=0.9, react_score=0.0, run_score=0.0,
                   react_avail=False, run_avail=False)
        assert F.forecast("AAA")["stock_lean"] == "unknown"
    finally:
        _restore()


def test_reaction_weighs_more_than_runup():
    try:
        _stub_legs(earn_score=0.9, react_score=1.0, run_score=-1.0)
        assert F.forecast("AAA")["stock_score"] > 0, "history must outweigh run-up"
    finally:
        _restore()


def main():
    tests = [(n, o) for n, o in sorted(globals().items())
             if n.startswith("test_") and callable(o)]
    print("forecast tests")
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
