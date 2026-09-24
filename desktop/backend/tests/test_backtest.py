"""Tests for the earnings backtest.

A backtest is the one piece of code where being wrong is WORSE than being
absent: a broken one produces a confident, flattering number that justifies
risking money. Almost every way it can be broken is a leak of information from
after the event into the features before it, so that is what these push on.

The tests build synthetic price and earnings series where the correct answer
is known by construction, so a passing result means the arithmetic is right
rather than merely plausible.
"""

import os
import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))))))

import backtest_earnings as B  # noqa: E402

ET = ZoneInfo("US/Eastern")


def _restore():
    import importlib
    importlib.reload(B)


def _series(n_days=800, start=100.0):
    """A flat price series keyed by date, plus its sorted date list."""
    base = datetime(2022, 1, 3)
    closes, days = {}, []
    for i in range(n_days):
        d = (base + timedelta(days=i)).strftime("%Y-%m-%d")
        closes[d] = start
        days.append(d)
    return closes, days


def _quarters(closes, days, spec, first_idx=100, spacing=90):
    """Place earnings events into the series.

    spec is a list of (surprise, reaction_pct): the reaction is applied by
    lifting every close from the reaction day onward, so the move is real in
    the price series rather than asserted.
    """
    rows = []
    for k, (surprise, reaction) in enumerate(spec):
        i = first_idx + k * spacing
        d = days[i]
        when = datetime.strptime(d, "%Y-%m-%d").replace(tzinfo=ET)
        # Reaction lands on the session after the report date.
        i_react = i + 1
        factor = 1.0 + reaction / 100.0
        for j in range(i_react, len(days)):
            closes[days[j]] *= factor
        rows.append((when, 1.0, 1.0, surprise))
    return rows


# ── Point-in-time discipline ───────────────────────────────────────────────

def test_features_never_use_the_event_being_scored():
    """The cardinal sin. If the current event's own reaction leaks into
    prior_beat_up_rate, a backtest measures hindsight and reports it as skill.

    Construction: five prior beats that all FELL, then a sixth beat that
    rises hard. The sixth event's prior_beat_up_rate must be 0.0 — if the
    current pop were included it would be non-zero.
    """
    closes, days = _series()
    spec = [(20, -10)] * 5 + [(20, +40)]
    rows = _quarters(closes, days, spec)
    evs = B.events_for("AAA", closes, days, rows)
    assert evs, "no events produced"
    last = evs[-1]
    assert last["prior_beat_up_rate"] == 0.0, last
    assert last["reaction_pct"] > 30, "the event's own pop should still be recorded"


def test_history_accumulates_forward_not_backward():
    """Event k may see exactly k prior quarters — never the later ones."""
    closes, days = _series()
    rows = _quarters(closes, days, [(10, 1)] * 8)
    evs = B.events_for("AAA", closes, days, rows)
    counts = [e["prior_quarters"] for e in evs]
    assert counts == sorted(counts), counts
    assert counts[0] == B.MIN_PRIOR_QUARTERS, counts
    for a, b in zip(counts, counts[1:]):
        assert b == a + 1, counts
    # Off-by-one check that the reaction-day guard cannot mask: with 8 quarters
    # and a 4-quarter minimum, exactly 4 events are scorable. An inclusive
    # slice would score 5 and would also fold each event's OWN surprise into
    # its prior beat rate — a leak no other guard here catches.
    assert len(evs) == 8 - B.MIN_PRIOR_QUARTERS, (
        f"scored {len(evs)} events; an inclusive slice scores one too many")


def test_events_without_enough_history_are_dropped():
    """Scoring the first quarter of a company's life on a beat rate computed
    from nothing would be a division by zero dressed up as a signal."""
    closes, days = _series()
    rows = _quarters(closes, days, [(10, 2)] * 3)     # fewer than the minimum
    assert B.events_for("AAA", closes, days, rows) == []


def test_prior_beat_rate_counts_only_earlier_quarters():
    closes, days = _series()
    # Four misses, then four beats. The fifth event (first scored) sees only
    # the four misses, so its prior beat rate is 0.
    rows = _quarters(closes, days, [(-20, -5)] * 4 + [(30, 5)] * 4)
    evs = B.events_for("AAA", closes, days, rows)
    assert evs[0]["prior_beat_rate"] == 0.0, evs[0]
    assert evs[-1]["prior_beat_rate"] > 0, evs[-1]


def test_runup_is_measured_before_the_event_not_through_it():
    """A run-up that accidentally spans the reaction would make every big
    pop look like it was preceded by a big pop."""
    closes, days = _series()
    rows = _quarters(closes, days, [(10, 1)] * 4 + [(10, +50)])
    evs = B.events_for("AAA", closes, days, rows)
    last = evs[-1]
    assert last["runup_pct"] is not None
    assert last["runup_pct"] < 10, ("the +50% reaction must not appear in the "
                                    f"pre-event run-up: {last['runup_pct']}")


# ── Return measurement ─────────────────────────────────────────────────────

def test_forward_returns_start_at_the_reaction_close():
    """The drift trade is entered AFTER the gap. Measuring from before it
    would credit the strategy with a move it could never have captured."""
    closes, days = _series()
    rows = _quarters(closes, days, [(10, 1)] * 4 + [(30, +25)])
    evs = B.events_for("AAA", closes, days, rows)
    last = evs[-1]
    assert abs(last["reaction_pct"] - 25) < 0.5, last["reaction_pct"]
    # Flat afterwards, so every forward return is ~0 — the 25% is NOT in them.
    # The values must EXIST: an earlier version returned None for all of them
    # and this assertion passed vacuously while the backtest was measuring
    # nothing at all.
    assert last.get("fwd_5") is not None, "forward returns must be computed"
    for n in B.HOLD_DAYS:
        v = last.get(f"fwd_{n}")
        if v is not None:
            assert abs(v) < 0.5, f"fwd_{n} picked up the gap: {v}"


def test_forward_returns_capture_post_reaction_drift():
    closes, days = _series()
    rows = _quarters(closes, days, [(10, 0)] * 5)
    evs = B.events_for("AAA", closes, days, rows)
    # Lift prices after the final event's reaction to simulate drift.
    last_date = evs[-1]["date"]
    i = days.index(last_date)
    for j in range(i + 2, len(days)):
        closes[days[j]] *= 1.10
    evs2 = B.events_for("AAA", closes, days, rows)
    assert evs2[-1]["fwd_5"] > 9, evs2[-1]["fwd_5"]


# ── Statistics ─────────────────────────────────────────────────────────────

def test_cost_is_subtracted_from_every_return():
    s = B._stats([1.0, 1.0, 1.0], cost=0.5)
    assert s["mean"] == 0.5, s
    # A cost bigger than the gross turns winners into losers, as it should.
    assert B._stats([0.3, 0.3], cost=0.5)["hit_rate"] == 0.0


def test_edge_is_measured_against_the_baseline():
    """A strategy returning +3% where everything returned +3% has no edge.
    This is the number amateurs skip and it must not read as success."""
    base = B._stats([3.0] * 10)
    same = B._stats([3.0] * 10)
    better = B._stats([6.0] * 10)
    assert B._edge(same, base)["mean_edge"] == 0.0
    assert B._edge(better, base)["mean_edge"] == 3.0


def test_edge_is_none_rather_than_zero_when_there_is_no_sample():
    """An empty bucket must not report a 0.0 edge, which reads as 'tested and
    found neutral' rather than 'never tested'."""
    assert B._edge({"n": 0}, B._stats([1.0]))["mean_edge"] is None
    assert B._stats([])["n"] == 0


def test_stats_ignore_missing_forward_returns():
    """Recent events have no 60-day forward return yet. Treating those as
    zero would drag every long-hold average toward nothing."""
    s = B._stats([5.0, None, 5.0, None])
    assert s["n"] == 2 and s["mean"] == 5.0


# ── Reporting ──────────────────────────────────────────────────────────────

def test_the_report_always_names_what_it_could_not_test():
    """The revision legs carry 0.65 of the earnings lean and cannot be
    backtested at all. A summary that quietly omitted that would imply the
    whole forecast had been validated."""
    res = B.analyse([])
    assert res["cannot_test"], "the untestable legs must always be declared"
    joined = " ".join(res["cannot_test"]).lower()
    assert "revision" in joined and "0.45" in joined
    assert any("survivorship" in b for b in res["known_biases"])


def test_analyse_survives_an_empty_run():
    res = B.analyse([])
    assert res["events"] == 0
    assert res["holds"] == {}


def test_a_planted_edge_is_detected():
    """End to end: beats followed by drift must show a positive edge, and the
    baseline must not absorb it."""
    evs = []
    for i in range(40):
        beat = i % 2 == 0
        evs.append({
            "ticker": "T", "date": f"2024-01-{i%28+1:02d}",
            "surprise_pct": 20.0 if beat else -20.0,
            "reaction_pct": 5.0 if beat else -5.0,
            "prior_beat_rate": 80.0, "prior_beat_up_rate": 80.0,
            "prior_quarters": 8, "runup_pct": 2.0,
            "fwd_1": 0.0, "fwd_5": 8.0 if beat else -8.0,
            "fwd_20": 0.0, "fwd_60": 0.0,
        })
    res = B.analyse(evs, cost=0.0)
    d = res["holds"]["5d"]
    assert d["baseline_all_events"]["mean"] == 0.0, d["baseline_all_events"]
    assert d["after_a_beat"]["mean_edge"] == 8.0, d["after_a_beat"]
    assert d["after_a_miss"]["mean_edge"] == -8.0


def test_no_edge_is_reported_as_no_edge():
    """The failure mode that matters most: a strategy with nothing in it must
    come back flat, not faintly positive."""
    evs = []
    for i in range(40):
        evs.append({
            "ticker": "T", "date": f"2024-02-{i%28+1:02d}",
            "surprise_pct": 20.0 if i % 2 == 0 else -20.0,
            "reaction_pct": 1.0,
            "prior_beat_rate": 50.0, "prior_beat_up_rate": 50.0,
            "prior_quarters": 8, "runup_pct": 0.0,
            "fwd_1": 3.0, "fwd_5": 3.0, "fwd_20": 3.0, "fwd_60": 3.0,
        })
    res = B.analyse(evs, cost=0.0)
    assert res["holds"]["5d"]["after_a_beat"]["mean_edge"] == 0.0


def test_a_prior_reaction_landing_on_the_event_day_is_excluded():
    """Isolates the second look-ahead guard, which the test above cannot reach
    because the two guards mask each other.

    When two reports fall a day apart — a delayed filing, a restatement — the
    EARLIER event's reaction day can land on or after the LATER event's date.
    Counting it would let the later event see a price move that had not
    happened when it reported.

    Construction: four beats that fell, then beat A with a big pop, then beat B
    the very next day. A's reaction day IS B's date, so B's prior_beat_up_rate
    must be 0.0 (four fallers only). Without the guard it becomes 20.0.
    """
    closes, days = _series()
    rows = []
    # Four spaced beats that each fell 10%.
    for k in range(4):
        i = 100 + k * 90
        rows.append((datetime.strptime(days[i], "%Y-%m-%d").replace(tzinfo=ET),
                     1.0, 1.0, 20))
        for j in range(i + 1, len(days)):
            closes[days[j]] *= 0.90
    # Beat A, reacting +40% on the following session...
    ia = 100 + 4 * 90
    rows.append((datetime.strptime(days[ia], "%Y-%m-%d").replace(tzinfo=ET),
                 1.0, 1.0, 20))
    for j in range(ia + 1, len(days)):
        closes[days[j]] *= 1.40
    # ...and beat B on that very session.
    ib = ia + 1
    rows.append((datetime.strptime(days[ib], "%Y-%m-%d").replace(tzinfo=ET),
                 1.0, 1.0, 20))

    evs = B.events_for("AAA", closes, days, rows)
    b = [e for e in evs if e["date"] == days[ib]]
    assert b, f"event B was not scored: {[e['date'] for e in evs]}"
    assert b[0]["prior_beat_up_rate"] == 0.0, (
        "A's reaction landed on B's report date and must not count toward B's "
        f"history: {b[0]}")


def main():
    tests = [(n, o) for n, o in sorted(globals().items())
             if n.startswith("test_") and callable(o)]
    print("backtest tests")
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
