"""Tests for the longer-term research book.

The module places no orders, so the risk here is not a bad fill — it is a
convincing-looking number that is wrong. Three things get the most attention:

  * EDGAR parsing, because US-GAAP tags the same line several ways and mixing
    a 10-Q into an annual growth rate invents a collapse that never happened;
  * the drift window, because a screen that lets a not-yet-reported company
    through has quietly become "hold through the print";
  * pdt_exposure, because the user declined a sleeve cap and this figure is
    what replaced it.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))))))

import research as R  # noqa: E402


def _restore():
    import importlib
    importlib.reload(R)


def _facts(concept, rows, space="us-gaap", unit="USD"):
    return {"facts": {space: {concept: {"units": {unit: rows}}}}}


def _row(fy, val, form="10-K", filed="2026-01-01"):
    return {"fy": fy, "val": val, "form": form, "filed": filed, "end": f"{fy}-12-31"}


# ── EDGAR parsing ──────────────────────────────────────────────────────────

def test_series_ignores_quarterly_filings():
    """A 10-Q value next to a 10-K would be read as a year-over-year collapse.
    Only annual forms may enter a growth series."""
    f = _facts("Revenues", [
        _row(2024, 1000, filed="2025-02-01"),
        _row(2025, 1200, filed="2026-02-01"),
        # Filed LATER than the 10-K, so if the form filter were missing this
        # row would win the same-fiscal-year dedup and a $1,200 year would be
        # read as a $300 year — an invented 75% collapse.
        _row(2025, 300, form="10-Q", filed="2026-05-01"),
    ])
    s = R._series(f, ["Revenues"])
    assert [r["val"] for r in s] == [1000, 1200], s
    assert R._pct_change(s) == 20.0, "growth must come from annual figures only"


def test_series_prefers_the_latest_filing_for_a_restated_year():
    f = _facts("Revenues", [
        _row(2025, 900, filed="2025-03-01"),
        _row(2025, 950, filed="2026-02-01"),   # restatement
    ])
    s = R._series(f, ["Revenues"])
    assert [r["val"] for r in s] == [950]


def test_series_falls_through_tag_synonyms():
    """Revenue is tagged at least four ways across filers and years."""
    f = _facts("RevenueFromContractWithCustomerExcludingAssessedTax",
               [_row(2024, 10), _row(2025, 20)])
    s = R._series(f, R._REVENUE_TAGS)
    assert [r["val"] for r in s] == [10, 20]


def test_series_is_empty_rather_than_raising_on_junk():
    for junk in ({}, {"facts": {}}, {"facts": {"us-gaap": {"Revenues": {}}}},
                 {"facts": {"us-gaap": {"Revenues": {"units": {}}}}}):
        assert R._series(junk, ["Revenues"]) == []


def test_pct_change_handles_zero_and_negative_bases():
    assert R._pct_change([_row(2024, 100), _row(2025, 150)]) == 50.0
    assert R._pct_change([_row(2024, 0), _row(2025, 150)]) is None   # no /0
    # A loss narrowing from -100 to -50 is a 50% improvement, not -50%.
    assert R._pct_change([_row(2024, -100), _row(2025, -50)]) == 50.0
    assert R._pct_change([_row(2025, 10)]) is None


def test_unavailable_fundamentals_are_not_reported_as_bad_ones():
    """'We could not check' and 'we checked and it is bad' must not render the
    same way, or an unreadable filer looks like a failing company."""
    R.cik_for = lambda t: None
    try:
        f = R.fundamentals("NOPE")
        assert f["available"] is False
        assert f["reason"]
        assert f["revenue_growth_pct"] is None
        leg = R.fundamentals_leg(f)
        assert leg["score"] == 0.0, "an unknown must score neutral, not negative"
    finally:
        _restore()


# ── Fundamental scoring ────────────────────────────────────────────────────

def test_heavy_dilution_is_penalised():
    """For a small cap financing itself by issuance this is often the most
    important number on the page, and no headline mentions it."""
    good = {"available": True, "revenue_growth_pct": 30, "profitable": True,
            "dilution_pct": 0}
    diluting = dict(good, dilution_pct=45)
    assert R.fundamentals_leg(diluting)["score"] < R.fundamentals_leg(good)["score"]
    assert any("dilution" in n for n in R.fundamentals_leg(diluting)["notes"])


def test_buybacks_score_above_flat_share_count():
    flat = {"available": True, "revenue_growth_pct": 10, "profitable": True,
            "dilution_pct": 0}
    buyback = dict(flat, dilution_pct=-5)
    assert R.fundamentals_leg(buyback)["score"] > R.fundamentals_leg(flat)["score"]


def test_fundamental_score_is_bounded():
    extreme = {"available": True, "revenue_growth_pct": 9999, "profitable": True,
               "dilution_pct": -99}
    awful = {"available": True, "revenue_growth_pct": -99, "profitable": False,
             "dilution_pct": 500}
    assert -1.0 <= R.fundamentals_leg(extreme)["score"] <= 1.0
    assert -1.0 <= R.fundamentals_leg(awful)["score"] <= 1.0


# ── Drift window ───────────────────────────────────────────────────────────

class _FakeEarnings:
    def __init__(self, days_ago=None, surprise=None, missing=False):
        self.days_ago, self.surprise, self.missing = days_ago, surprise, missing

    def last_report(self, ticker):
        if self.missing:
            return None
        from datetime import datetime, timedelta, timezone
        when = datetime.now(timezone.utc) - timedelta(days=self.days_ago)
        return {"ticker": ticker, "date": when, "surprise_pct": self.surprise}


def _with_earnings(fake):
    sys.modules["earnings"] = fake


def test_a_company_that_has_not_reported_is_never_in_the_window():
    """The whole point of the separate book is that it trades the reaction.
    A negative days-since means the print is still ahead — letting that through
    turns the screen into holding into an announcement."""
    real = sys.modules.get("earnings")
    _with_earnings(_FakeEarnings(days_ago=-5, surprise=40))
    try:
        leg = R.drift_leg("AAA")
        assert leg["in_window"] is False
        assert leg["score"] == 0.0
        assert "not reported" in leg["note"]
    finally:
        if real is not None: sys.modules["earnings"] = real
        else: sys.modules.pop("earnings", None)
        _restore()


def test_a_stale_beat_is_outside_the_window():
    real = sys.modules.get("earnings")
    _with_earnings(_FakeEarnings(days_ago=R.DRIFT_MAX_DAYS + 10, surprise=40))
    try:
        leg = R.drift_leg("AAA")
        assert leg["in_window"] is False
        assert "outside" in leg["note"]
    finally:
        if real is not None: sys.modules["earnings"] = real
        else: sys.modules.pop("earnings", None)
        _restore()


def test_a_small_surprise_does_not_qualify():
    real = sys.modules.get("earnings")
    _with_earnings(_FakeEarnings(days_ago=3, surprise=1.0))
    try:
        leg = R.drift_leg("AAA")
        assert leg["in_window"] is False
        assert "noise" in leg["note"]
    finally:
        if real is not None: sys.modules["earnings"] = real
        else: sys.modules.pop("earnings", None)
        _restore()


def test_a_miss_never_qualifies_as_drift():
    real = sys.modules.get("earnings")
    _with_earnings(_FakeEarnings(days_ago=3, surprise=-40))
    try:
        assert R.drift_leg("AAA")["in_window"] is False
    finally:
        if real is not None: sys.modules["earnings"] = real
        else: sys.modules.pop("earnings", None)
        _restore()


def test_drift_score_decays_across_the_window():
    """A beat five days old has more drift left than the same beat at day 55."""
    real = sys.modules.get("earnings")
    try:
        _with_earnings(_FakeEarnings(days_ago=5, surprise=30))
        fresh = R.drift_leg("AAA")["score"]
        _with_earnings(_FakeEarnings(days_ago=R.DRIFT_MAX_DAYS - 5, surprise=30))
        old = R.drift_leg("AAA")["score"]
        assert fresh > old > 0, (fresh, old)
    finally:
        if real is not None: sys.modules["earnings"] = real
        else: sys.modules.pop("earnings", None)
        _restore()


def test_missing_surprise_figure_does_not_qualify():
    real = sys.modules.get("earnings")
    _with_earnings(_FakeEarnings(days_ago=3, surprise=None))
    try:
        leg = R.drift_leg("AAA")
        assert leg["in_window"] is False
        assert "no surprise" in leg["note"]
    finally:
        if real is not None: sys.modules["earnings"] = real
        else: sys.modules.pop("earnings", None)
        _restore()


# ── Sizing ─────────────────────────────────────────────────────────────────

def test_size_respects_the_dollar_cap():
    R.POSITION_PCT = 0.04
    R.POSITION_MAX_USD = 2000
    try:
        s = R.suggest_size(price=10.0, equity=1_000_000)
        assert s["dollars"] <= 2000, s     # 4% of 1M is 40k; the cap must bind
        assert s["shares"] == 200
    finally:
        _restore()


def test_size_refuses_rather_than_rounding_up_to_one_share():
    s = R.suggest_size(price=5000.0, equity=26000)
    assert s["shares"] == 0
    assert "does not buy one share" in s["note"]


def test_size_needs_both_price_and_equity():
    for args in ((None, 26000), (10.0, None), (0, 26000), (10.0, 0)):
        s = R.suggest_size(*args)
        assert s["shares"] == 0 and s["note"]


# ── PDT exposure: the safeguard that replaced the sleeve cap ───────────────

def test_breach_gap_is_the_drop_that_reaches_the_floor():
    """$25,926 equity, $10,000 held: headroom is $926, so a 9.3% fall across
    the book erases it. This is the number the user waved off, so it has to be
    right."""
    R.PDT_FLOOR = 25000
    try:
        e = R.pdt_exposure(25926, [{"ticker": "A", "market_value": 10000}])
        assert e["headroom"] == 926
        assert e["exposure"] == 10000
        assert e["breach_gap_pct"] == 9.3, e["breach_gap_pct"]
        assert "stops day trading" in e["note"]
    finally:
        _restore()


def test_more_positions_shrink_the_breach_gap():
    """The pile is the risk, not any single position. Five $2,000 positions
    must read as more dangerous than one."""
    R.PDT_FLOOR = 25000
    try:
        one = R.pdt_exposure(25926, [{"market_value": 2000}])
        five = R.pdt_exposure(25926, [{"market_value": 2000}] * 5)
        assert five["breach_gap_pct"] < one["breach_gap_pct"]
        assert five["positions"] == 5
    finally:
        _restore()


def test_exposure_falls_back_to_qty_times_price():
    e = R.pdt_exposure(30000, [{"qty": 100, "current_price": 12.5}])
    assert e["exposure"] == 1250


def test_short_positions_count_toward_exposure():
    """A short's market value is negative; its risk is not."""
    e = R.pdt_exposure(30000, [{"market_value": -4000}])
    assert e["exposure"] == 4000


def test_already_below_the_floor_is_stated_plainly():
    R.PDT_FLOOR = 25000
    try:
        e = R.pdt_exposure(24000, [{"market_value": 5000}])
        assert "below the PDT floor" in e["note"]
        assert e["breach_gap_pct"] is None
    finally:
        _restore()


def test_no_positions_means_no_breach_gap():
    e = R.pdt_exposure(26000, [])
    assert e["breach_gap_pct"] is None
    assert "nothing held" in e["note"]


def test_exposure_survives_malformed_positions():
    e = R.pdt_exposure(26000, [{"market_value": "junk"}, {}, None,
                               {"market_value": 1000}])
    assert e["exposure"] == 1000


def test_missing_equity_does_not_crash_the_meter():
    e = R.pdt_exposure(None, [{"market_value": 5000}])
    assert e["headroom"] is None and e["note"]


# ── Ranking ────────────────────────────────────────────────────────────────

def test_rank_orders_by_score_and_drops_failures():
    def _eval(t, price=None, equity=None):
        if t == "BOOM":
            raise RuntimeError("bad name")
        return {"ticker": t, "score": {"AAA": 0.1, "BBB": 0.9}[t]}
    R.evaluate = _eval
    try:
        rows = R.rank(["AAA", "BOOM", "BBB"])
        assert [r["ticker"] for r in rows] == ["BBB", "AAA"]
    finally:
        _restore()


def test_rank_honours_the_limit():
    R.evaluate = lambda t, price=None, equity=None: {"ticker": t, "score": 0.5}
    try:
        assert len(R.rank([f"T{i}" for i in range(30)], limit=5)) == 5
    finally:
        _restore()


def test_news_returns_empty_without_credentials():
    old = os.environ.pop("ALPACA_KEY_ID", None)
    try:
        assert R.news("AAA") == []
    finally:
        if old is not None:
            os.environ["ALPACA_KEY_ID"] = old


def main():
    tests = [(n, o) for n, o in sorted(globals().items())
             if n.startswith("test_") and callable(o)]
    print("research tests")
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
