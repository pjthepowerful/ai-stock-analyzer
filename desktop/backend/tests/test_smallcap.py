"""Tests for smallcap_pullback.py — the small-cap gainer pullback autopilot modes.

These cover the parts of the system where a silent bug costs real money: the
sizing caps, the ladder's total-risk identity, the retest grader's real-vs-fake
discrimination, and the rails that are supposed to be un-overridable.

No network. Everything that would touch Alpaca/Polygon/EDGAR is stubbed.

Run directly:  python3 desktop/backend/tests/test_smallcap.py
"""
import os
import pathlib
import re
import sys
import types
from datetime import datetime, timedelta

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

# Stub trading.py before importing — smallcap_pullback resolves it lazily via
# _t(), so a module-level stub is enough and keeps the suite offline.
_fake = types.ModuleType("trading")
_fake.ALPACA_BASE = "https://stub.invalid"
_fake._alpaca_headers = lambda: {}
_fake._market_is_open = lambda: (True, "open")
_fake._polygon_key = lambda: None
_fake.alpaca_account = lambda: {"equity": 50_000, "buying_power": 50_000, "daily_pnl": 0}
_fake.alpaca_positions = lambda: []
_fake.alpaca_close_all = lambda: {"ok": True}
_fake.alpaca_cancel_all_orders = lambda: {"ok": True}
_fake.alpaca_sell = lambda **k: {"ok": True}
_fake.polygon_gainers = lambda limit=20: []
_fake.polygon_all_snapshots = lambda: []
_fake._news_sentiment = lambda t: {}
_fake._update_stop_order = lambda *a, **k: {"ok": True}
sys.modules.setdefault("trading", _fake)

import smallcap_pullback as scp  # noqa: E402

ET = scp.ET
STRICT = scp.get_mode("strict")
INTENSE = scp.get_mode("intense")
AGGRO = INTENSE   # legacy alias: "aggro" now resolves to "intense"


def _bar(minute, o, h, l, c, v, hour=10):
    return (datetime(2026, 8, 12, hour, minute, tzinfo=ET), o, h, l, c, v)


# ── Mode registry ──────────────────────────────────────────────────────────

def test_both_modes_define_every_parameter_the_runner_reads():
    """A missing key doesn't fail loudly — it KeyErrors mid-cycle with an open
    position. Both modes must define the same surface."""
    required = set(STRICT) - {"key", "label", "tagline"}
    for k in required:
        assert k in AGGRO, f"aggro is missing {k!r}"
    for k in ("R_PCT", "MAX_POSITIONS", "DAILY_LOSS_LIMIT", "FLATTEN_AT",
              "MAX_STOP_PCT", "CATASTROPHE_CAP_PCT", "ENTRY_WINDOWS", "SETUPS"):
        assert k in STRICT and k in AGGRO


def test_intense_concentrates_rather_than_diversifies():
    """10-20% of capital in one name is the design. Guard the ceiling so a later
    edit can't turn a concentrated mode into a leveraged one."""
    assert INTENSE["CATASTROPHE_CAP_PCT"] <= 0.20
    assert INTENSE["LADDER_TARGET_EQUITY_PCT"] <= INTENSE["CATASTROPHE_CAP_PCT"]
    assert INTENSE["MAX_POSITIONS"] * INTENSE["CATASTROPHE_CAP_PCT"] <= 0.40


def test_ladder_full_extension_respects_the_equity_target():
    """The adds must carry the position TO the target, not start there."""
    # Levels close together => tiny risk-per-share => the fixed-fractional size
    # alone would be enormous. The equity target has to be what clamps it.
    lad = scp.plan_ladder(5.00, 4.96, {"vwap": 4.98, "pdh": 4.965}, 50_000, INTENSE,
                          adv=900e6, med1=90e6)
    assert lad is not None
    unclamped = (50_000 * INTENSE["R_PCT"]) / (lad["avg_price_if_full"] - lad["final_stop"])
    assert unclamped > lad["total_qty"] * 1.2, "fixture must actually exercise the clamp"
    full_notional = lad["total_qty"] * lad["avg_price_if_full"]
    assert full_notional <= 50_000 * INTENSE["LADDER_TARGET_EQUITY_PCT"] * 1.05
    first = lad["tranches"][0]
    assert first["qty"] * first["price"] < full_notional * 0.5, "first tranche is a starter"


def test_volatility_gate_rejects_a_name_that_gapped_then_died():
    """Big day range from the morning gap, but flat ever since. This must be
    caught by the ATR check specifically — the range check would pass it."""
    bars = [(datetime(2026, 8, 17, 9, 31, tzinfo=ET), 5.0, 5.60, 4.98, 5.55, 800_000)]
    bars += [(datetime(2026, 8, 17, 10, i, tzinfo=ET), 5.55, 5.557, 5.545, 5.55, 3_000)
             for i in range(40)]
    ctx = {"bars1": bars, "bars5": bars, "price": 5.55, "atr5": 0.006}
    prof = scp.volatility_profile(ctx, INTENSE)
    assert prof["range_pct"] > INTENSE["MIN_DAY_RANGE_PCT"], "range alone would pass it"
    assert prof["ok"] is False
    assert "ATR" in prof["reason"]


def test_volatility_gate_rejects_a_name_too_wide_to_scalp():
    # Must clear ATR and day-range first, so the spread check is what rejects it:
    # a thin book where even quiet minutes print a wide bar.
    bars = [(datetime(2026, 8, 17, 9, 31, tzinfo=ET), 5.0, 5.90, 4.90, 5.60, 300_000)]
    bars += [(datetime(2026, 8, 17, 10, i, tzinfo=ET), 5.5, 5.62, 5.38, 5.5, 4_000)
             for i in range(20)]
    ctx = {"bars1": bars, "bars5": bars, "price": 5.5, "atr5": 0.12}
    prof = scp.volatility_profile(ctx, INTENSE)
    assert prof["atr_pct"] >= INTENSE["MIN_ATR_PCT"], "ATR alone would pass it"
    assert prof["range_pct"] >= INTENSE["MIN_DAY_RANGE_PCT"], "range alone would pass it"
    assert prof["ok"] is False and "spread" in prof["reason"]


def test_volatility_gate_passes_a_name_that_is_actually_moving():
    # Real tape mixes travelling minutes with quiet ones; a fixture where every
    # bar has an identical range makes every percentile the same and tells you
    # nothing about whether spread and movement are being separated.
    live = []
    for i in range(40):
        base = 5.0 + (i % 7) * 0.12
        wide = i % 3 == 0                      # a third of minutes are active
        hi = base + (0.09 if wide else 0.012)
        lo = base - (0.08 if wide else 0.010)
        live.append((datetime(2026, 8, 17, 10, i, tzinfo=ET), base, hi, lo,
                     base + 0.02, 140_000 if wide else 40_000))
    ctx = {"bars1": live, "bars5": live, "price": 5.4, "atr5": 0.11}
    assert scp.volatility_profile(ctx, INTENSE)["ok"] is True


def test_volatility_gate_rejects_a_name_with_no_day_range():
    """Ticks along with respectable per-bar ATR but has gone nowhere all day —
    caught by the range check specifically, not by ATR or spread."""
    bars = []
    for i in range(30):
        wide = i % 4 == 0                      # occasional active minute
        bars.append((datetime(2026, 8, 17, 10, i, tzinfo=ET), 5.0,
                     5.0 + (0.055 if wide else 0.008),
                     5.0 - (0.050 if wide else 0.007), 5.0,
                     120_000 if wide else 30_000))
    ctx = {"bars1": bars, "bars5": bars, "price": 5.0, "atr5": 0.09}
    prof = scp.volatility_profile(ctx, INTENSE)
    assert prof["atr_pct"] >= INTENSE["MIN_ATR_PCT"], "ATR alone would pass it"
    assert prof["spread_pct"] <= INTENSE["MAX_SPREAD_PCT"], "spread alone would pass it"
    assert prof["ok"] is False and "range" in prof["reason"]


def test_market_cap_is_a_prior_not_a_gate():
    """A volatile name outside the sweet spot trades smaller, not never."""
    ok_ideal, mult_ideal, _ = scp.cap_fit(100e6, INTENSE)
    ok_off, mult_off, note = scp.cap_fit(300e6, INTENSE)
    ok_out, _, _ = scp.cap_fit(2e9, INTENSE)
    assert ok_ideal and mult_ideal == 1.0
    assert ok_off and 0 < mult_off < 1.0 and "sweet spot" in note
    assert not ok_out


def test_unknown_cap_is_not_disqualifying():
    ok, mult, _ = scp.cap_fit(None, INTENSE)
    assert ok and mult == 1.0


def test_stall_fires_when_highs_stop_coming_on_fading_volume():
    bars = [(datetime(2026, 8, 17, 10, i * 5, tzinfo=ET), 5, 5.2 + i * 0.05,
             4.9, 5.1 + i * 0.05, 200_000) for i in range(4)]
    bars += [(datetime(2026, 8, 17, 10, 20 + i * 5, tzinfo=ET), 5.3, 5.32, 5.2, 5.25, 90_000)
             for i in range(3)]
    assert scp.momentum_stalled(bars, 3) is True


def test_stall_does_not_fire_while_new_highs_keep_printing():
    bars = [(datetime(2026, 8, 17, 10, i * 5, tzinfo=ET), 5, 5.2 + i * 0.08,
             4.9, 5.15 + i * 0.08, 200_000) for i in range(8)]
    assert scp.momentum_stalled(bars, 3) is False


def test_atr_stop_widens_for_a_wild_name_and_respects_structure():
    wild = scp.atr_stop(10.0, {"atr5": 0.30}, INTENSE, structural_stop=9.90)
    calm = scp.atr_stop(10.0, {"atr5": 0.03}, INTENSE, structural_stop=9.90)
    assert wild < calm, "a more volatile name needs a wider stop"
    assert wild >= 10.0 * (1 - INTENSE["MAX_STOP_PCT"]), "never past the max-stop rail"


def test_legacy_aggro_config_still_resolves():
    """An existing autopilot_config.json saying 'aggro' must not fall back to a
    different strategy than the one that was running."""
    assert scp.get_mode("aggro")["key"] == "intense"


def test_only_two_modes_are_offered():
    assert {m["key"] for m in scp.mode_summary()} == {"strict", "intense"}


def test_original_intense_risk_ordering():
    assert AGGRO["R_PCT"] > STRICT["R_PCT"]
    # Intense does NOT hold more names — it holds fewer, larger ones. Risk shows
    # up as concentration and per-trade R, not as position count.
    assert AGGRO["MAX_POSITIONS"] <= STRICT["MAX_POSITIONS"]
    assert AGGRO["DAILY_LOSS_LIMIT"] > STRICT["DAILY_LOSS_LIMIT"]
    assert AGGRO["RVOL_MIN"] < STRICT["RVOL_MIN"]
    assert AGGRO["CATASTROPHE_CAP_PCT"] > STRICT["CATASTROPHE_CAP_PCT"]
    assert AGGRO["FLOAT_MIN"] < STRICT["FLOAT_MIN"]
    assert AGGRO["SCALE_IN"] and not STRICT["SCALE_IN"]


def test_unknown_mode_falls_back_to_strict_not_aggro():
    """Fail safe, not fail loose."""
    assert scp.get_mode("nonsense")["key"] == "strict"
    assert scp.get_mode("")["key"] == "strict"
    assert scp.get_mode(None)["key"] == "strict"


def test_rails_are_not_per_mode():
    """Attempts cap, no-overnight, and the hard flatten are module constants —
    if these ever become mode keys, a mode could disable them."""
    assert scp.MAX_ATTEMPTS_PER_TICKER == 2
    assert scp.NEVER_HOLD_OVERNIGHT is True
    assert "MAX_ATTEMPTS_PER_TICKER" not in STRICT and "MAX_ATTEMPTS_PER_TICKER" not in AGGRO
    for m in (STRICT, AGGRO):
        h, _ = scp._hm(m["FLATTEN_AT"])
        assert h < 16, "a mode must flatten before the close"
        assert m["FLATTEN_AT"] <= scp.HARD_FLATTEN_LATEST


def test_mode_summary_shape_for_the_ui():
    rows = scp.mode_summary()
    assert {r["key"] for r in rows} == {"strict", "intense"}
    for r in rows:
        assert r["label"] and r["tagline"]
        assert len(r["price_band"]) == 2 and len(r["float_band"]) == 2


# ── Indicator math ─────────────────────────────────────────────────────────

def test_vwap_is_volume_weighted_not_a_plain_average():
    bars = [_bar(0, 10, 10, 10, 10, 100), _bar(1, 20, 20, 20, 20, 900)]
    vwap = scp._vwap(bars)
    assert abs(vwap - 19.0) < 1e-9, vwap  # heavy bar dominates


def test_vwap_of_empty_or_zero_volume_is_none_not_a_crash():
    assert scp._vwap([]) is None
    assert scp._vwap([_bar(0, 5, 5, 5, 5, 0)]) is None


def test_ema_needs_a_full_period():
    assert scp._ema([1, 2, 3], 9) is None
    assert scp._ema(list(range(1, 13)), 9) is not None


def test_ema_series_aligns_with_input_length():
    vals = list(range(1, 21))
    s = scp._ema_series(vals, 9)
    assert len(s) == len(vals)
    assert s[7] is None and s[8] is not None


def test_atr_on_flat_bars_is_the_bar_range():
    bars = [_bar(i, 10, 10.5, 9.5, 10.0, 1000) for i in range(20)]
    assert abs(scp._atr(bars, 14) - 1.0) < 1e-9


def test_atr_returns_none_when_too_few_bars():
    assert scp._atr([_bar(i, 10, 11, 9, 10, 100) for i in range(5)], 14) is None


# ── Confluence + retest quality ────────────────────────────────────────────

def test_confluent_level_needs_two_references():
    ctx = {"vwap": 5.01, "pdh": 4.99, "pmh": 7.20}
    hits = scp._confluence_levels(5.00, ctx)
    assert "vwap" in hits and "pdh" in hits and "pmh" not in hits
    assert len(hits) >= 2


def test_isolated_level_is_not_confluent():
    hits = scp._confluence_levels(6.37, {"vwap": 5.00, "pdh": 4.20, "pmh": 7.90})
    assert len(hits) < 2, hits


def test_round_number_counts_as_a_reference():
    assert "round" in scp._confluence_levels(5.00, {})


def _impulse_then_quiet_pullback():
    """Pole on heavy volume, then a shallow drift on a fraction of it."""
    bars = [_bar(i * 5, 4.0 + i * 0.1, 4.1 + i * 0.1, 3.95 + i * 0.1, 4.08 + i * 0.1, 200_000)
            for i in range(8)]                       # impulse to ~4.78
    bars += [_bar(40 + i * 5, 4.78 - i * 0.02, 4.80 - i * 0.02, 4.72 - i * 0.02,
                  4.75 - i * 0.02, 60_000) for i in range(3)]
    return bars


def _impulse_then_distribution():
    """Same pole, but the pullback prints MORE volume than the leg."""
    bars = [_bar(i * 5, 4.0 + i * 0.1, 4.1 + i * 0.1, 3.95 + i * 0.1, 4.08 + i * 0.1, 200_000)
            for i in range(8)]
    bars += [_bar(40 + i * 5, 4.78 - i * 0.08, 4.80 - i * 0.08, 4.60 - i * 0.08,
                  4.65 - i * 0.08, 520_000) for i in range(3)]
    return bars


def test_quiet_pullback_grades_higher_than_distribution():
    """The volume signature is the single best real-vs-fake tell, so the grader
    must separate these two by a wide margin."""
    ctx = {"vwap": 4.50, "pdh": 4.70}
    good = scp._retest_quality(_impulse_then_quiet_pullback(), 4.70, ctx, STRICT)
    bad = scp._retest_quality(_impulse_then_distribution(), 4.70, ctx, STRICT)
    assert good["vol_ratio"] < 0.5, good
    assert bad["vol_ratio"] > 1.0, bad
    assert good["grade"] > bad["grade"] + 20, (good["grade"], bad["grade"])


def test_distribution_pullback_fails_the_strict_grade_bar():
    ctx = {"vwap": 4.50, "pdh": 4.70}
    bad = scp._retest_quality(_impulse_then_distribution(), 4.70, ctx, STRICT)
    assert bad["grade"] < STRICT["MIN_SETUP_GRADE"]
    assert any("distribution" in n.lower() for n in bad["notes"]), bad["notes"]


def test_retest_quality_degrades_gracefully_on_short_history():
    g = scp._retest_quality([_bar(0, 1, 1, 1, 1, 10)], 1.0, {}, STRICT)
    assert g["grade"] == 0


def test_failed_test_fires_on_expanding_volume_and_lower_highs():
    """The level breaking on rising volume with lower highs stacking beneath it
    is the exact bar an averaging-down rule would buy. It must be detectable."""
    bars = [_bar(i * 5, 5.0, 5.05, 4.95, 5.0, 100_000) for i in range(4)]
    bars += [_bar(20 + i * 5, 4.9 - i * 0.05, 4.95 - i * 0.06, 4.70 - i * 0.05,
                  4.75 - i * 0.05, 400_000) for i in range(4)]
    assert scp._failed_test(bars, 5.00) is True


def test_failed_test_does_not_fire_on_a_healthy_hold():
    bars = _impulse_then_quiet_pullback()
    assert scp._failed_test(bars, 4.70) is False


# ── Sizing (Section 3) ─────────────────────────────────────────────────────

def test_base_size_is_fixed_fractional():
    r = scp.size_position(50_000, 5.00, 4.75, STRICT, "T", adv=50e6, med1=5e6)
    # 0.5% of 50k = $250 risk / $0.25 per share = 1000 shares
    assert r["caps"]["base"] == 1000
    assert r["qty"] == 1000 and r["binding_cap"] == "base"


def test_wide_stop_is_passed_on_not_widened():
    r = scp.size_position(50_000, 5.00, 4.00, STRICT, "T")
    assert r["qty"] == 0
    assert "wider than" in r["reason"]


def test_catastrophe_cap_binds_independently_of_stop_math():
    """A very tight stop implies a huge share count. Notional must still be
    capped, because stops are a fiction through halts and gaps."""
    r = scp.size_position(50_000, 5.00, 4.99, STRICT, "T", adv=500e6, med1=50e6)
    assert r["binding_cap"] == "catastrophe"
    assert r["qty"] * 5.00 <= 50_000 * STRICT["CATASTROPHE_CAP_PCT"] + 5


def test_liquidity_caps_bind_in_a_thin_name():
    r = scp.size_position(50_000, 5.00, 4.75, STRICT, "T", adv=1e6, med1=10_000)
    assert r["binding_cap"] in ("adv", "min1")
    assert r["qty"] < 1000


def test_aggro_sizes_larger_than_strict_on_identical_input():
    a = scp.size_position(50_000, 5.00, 4.75, AGGRO, "T", adv=50e6, med1=5e6)
    s = scp.size_position(50_000, 5.00, 4.75, STRICT, "T", adv=50e6, med1=5e6)
    assert a["qty"] > s["qty"]


def test_size_multiplier_scales_risk_down():
    full = scp.size_position(50_000, 5.00, 4.75, STRICT, "T", adv=50e6, med1=5e6)
    half = scp.size_position(50_000, 5.00, 4.75, STRICT, "T", adv=50e6, med1=5e6,
                             size_mult=0.5)
    assert half["qty"] == full["qty"] // 2


def test_inverted_stop_is_rejected():
    assert scp.size_position(50_000, 5.00, 5.50, STRICT, "T")["qty"] == 0


# ── The ladder (Section 4.4) ───────────────────────────────────────────────

def test_strict_mode_refuses_to_build_a_ladder():
    assert scp.plan_ladder(5.00, 4.75, {"vwap": 4.80, "pdh": 4.60}, 50_000, STRICT) is None


def test_ladder_total_risk_equals_one_R():
    """The identity that makes this a scale-in rather than a martingale: full
    size at the average price down to the final stop is the same 1R any single
    trade gets."""
    lad = scp.plan_ladder(5.00, 4.75, {"vwap": 4.80, "pdh": 4.60}, 50_000, AGGRO,
                          adv=100e6, med1=5e6)
    assert lad is not None
    risk = (lad["avg_price_if_full"] - lad["final_stop"]) * lad["total_qty"]
    one_r = 50_000 * AGGRO["R_PCT"]
    assert abs(risk - one_r) / one_r < 0.05, (risk, one_r)


def test_ladder_levels_are_pre_existing_chart_levels():
    lad = scp.plan_ladder(5.00, 4.75, {"vwap": 4.80, "pdh": 4.60}, 50_000, AGGRO,
                          adv=100e6, med1=5e6)
    names = [t["level_name"] for t in lad["tranches"]]
    assert set(names) <= set(AGGRO["LADDER_LEVELS"])
    prices = [t["price"] for t in lad["tranches"]]
    assert prices == sorted(prices, reverse=True), "tranches must descend"


def test_ladder_final_stop_sits_below_every_tranche():
    lad = scp.plan_ladder(5.00, 4.75, {"vwap": 4.80, "pdh": 4.60}, 50_000, AGGRO,
                          adv=100e6, med1=5e6)
    assert lad["final_stop"] < min(t["price"] for t in lad["tranches"])


def test_ladder_shrinks_under_a_liquidity_cap_rather_than_moving_the_stop():
    """When the caps bite, tranche sizes fall. The stop does not move."""
    wide = scp.plan_ladder(5.00, 4.75, {"vwap": 4.80, "pdh": 4.60}, 50_000, AGGRO,
                           adv=100e6, med1=5e6)
    thin = scp.plan_ladder(5.00, 4.75, {"vwap": 4.80, "pdh": 4.60}, 50_000, AGGRO,
                           adv=3e6, med1=40_000)
    assert thin is None or thin["total_qty"] < wide["total_qty"]
    if thin:
        assert abs(thin["final_stop"] - wide["final_stop"]) < 1e-9


def test_ladder_needs_at_least_two_real_levels():
    """No VWAP and no PDH means there is nothing to ladder into — inventing
    levels mid-trade is the failure mode this whole section exists to prevent."""
    assert scp.plan_ladder(5.00, 4.75, {}, 50_000, AGGRO, adv=100e6, med1=5e6) is None


def test_ladder_rejects_levels_above_the_entry():
    """A 'support' level above where you bought is not support."""
    lad = scp.plan_ladder(5.00, 4.75, {"vwap": 5.40, "pdh": 5.60}, 50_000, AGGRO,
                          adv=100e6, med1=5e6)
    assert lad is None


def test_ladder_carries_its_time_stop():
    lad = scp.plan_ladder(5.00, 4.75, {"vwap": 4.80, "pdh": 4.60}, 50_000, AGGRO,
                          adv=100e6, med1=5e6)
    assert 30 <= lad["time_stop_min"] <= 90


# ── Time-of-day gating ─────────────────────────────────────────────────────

def test_strict_avoids_the_open_and_midday():
    w = STRICT["ENTRY_WINDOWS"]
    assert not scp._in_window(datetime(2026, 8, 12, 9, 35, tzinfo=ET), w)
    assert scp._in_window(datetime(2026, 8, 12, 10, 15, tzinfo=ET), w)
    assert not scp._in_window(datetime(2026, 8, 12, 12, 15, tzinfo=ET), w)
    assert scp._in_window(datetime(2026, 8, 12, 14, 0, tzinfo=ET), w)


def test_aggro_trades_midday_strict_does_not():
    noon = datetime(2026, 8, 12, 12, 15, tzinfo=ET)
    assert scp._in_window(noon, AGGRO["ENTRY_WINDOWS"])
    assert not scp._in_window(noon, STRICT["ENTRY_WINDOWS"])


def test_no_mode_opens_new_trades_into_the_close():
    late = datetime(2026, 8, 12, 15, 40, tzinfo=ET)
    for m in (STRICT, AGGRO):
        assert not scp._in_window(late, m["ENTRY_WINDOWS"])


# ── Daily state ────────────────────────────────────────────────────────────

def test_state_resets_on_a_new_day():
    scp.STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    stale = {"date": (datetime.now(ET) - timedelta(days=1)).strftime("%Y-%m-%d"),
             "attempts": {"AAAA": 2}, "positions": {}, "stopped_out": [],
             "rescued": [], "halted_for_day": True}
    import json
    scp.STATE_FILE.write_text(json.dumps(stale))
    st = scp._load_state()
    assert st["attempts"] == {}
    assert st["halted_for_day"] is False
    scp.STATE_FILE.unlink(missing_ok=True)


def test_corrupt_state_file_does_not_crash_the_cycle():
    scp.STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    scp.STATE_FILE.write_text("{ not json")
    st = scp._load_state()
    assert st["attempts"] == {} and "date" in st
    scp.STATE_FILE.unlink(missing_ok=True)


# ── Runner gating (offline, stubbed account) ───────────────────────────────

def _run_with_pnl(mode_key, daily_pnl, equity=250_000):
    """Default equity is deliberately large so the PDT floor stays out of the
    way of tests that aren't about it."""
    scp.STATE_FILE.unlink(missing_ok=True)
    prev = _fake.alpaca_account
    _fake.alpaca_account = lambda: {"equity": equity, "buying_power": equity,
                                    "daily_pnl": daily_pnl}
    try:
        return scp.run(mode_key, skip_market_check=True)
    finally:
        # Restore, or the next test inherits this equity — a $26k leak makes an
        # unrelated test return early at the PDT floor and fail for the wrong reason.
        _fake.alpaca_account = prev
        scp.STATE_FILE.unlink(missing_ok=True)


def test_daily_loss_limit_halts_the_day():
    out = _run_with_pnl("strict", -1200, equity=50_000)   # -2.4% vs a 2% limit
    assert out.get("halted") is True
    assert any("Daily loss limit" in l for l in out["log"])


def test_intense_tolerates_a_loss_that_stops_strict():
    """Same drawdown, different modes — this is the difference showing up."""
    strict_out = _run_with_pnl("strict", -1200, equity=50_000)
    aggro_out = _run_with_pnl("intense", -1200, equity=50_000)   # -2.4% vs a 3% limit
    assert strict_out.get("halted") is True
    assert aggro_out.get("halted") is not True


def test_runner_always_reports_its_mode():
    for k in ("strict", "intense"):
        out = _run_with_pnl(k, 0)
        assert out["mode"] == k
        assert out["log"] and "Mode:" in out["log"][0]


def test_runner_survives_a_dead_account_connection():
    scp.STATE_FILE.unlink(missing_ok=True)
    _fake.alpaca_account = lambda: None
    out = scp.run("strict", skip_market_check=True)
    assert out["ok"] is False
    _fake.alpaca_account = lambda: {"equity": 50_000, "buying_power": 50_000, "daily_pnl": 0}


# ── Cross-strategy safety ──────────────────────────────────────────────────

def _flatten_time_run(state_positions):
    """Drive manage_positions at flatten time and record what got sold."""
    sold = []
    _fake.alpaca_positions = lambda: [
        {"ticker": "AAPL", "qty": 10, "current_price": 220.0, "avg_entry": 210.0,
         "unrealized_pnl_pct": 4.8},
        {"ticker": "ABCD", "qty": 100, "current_price": 5.10, "avg_entry": 5.00,
         "unrealized_pnl_pct": 2.0},
    ]
    _fake.alpaca_sell = lambda **k: (sold.append(k.get("ticker")), {"ok": True})[1]
    state = {"date": "x", "attempts": {}, "positions": dict(state_positions),
             "stopped_out": [], "rescued": [], "halted_for_day": False}
    log = []
    real_now = scp._now_et
    scp._now_et = lambda: datetime(2026, 8, 14, 15, 50, tzinfo=ET)  # past FLATTEN_AT
    try:
        scp.manage_positions(STRICT, state, log)
    finally:
        scp._now_et = real_now
        _fake.alpaca_positions = lambda: []
        _fake.alpaca_sell = lambda **k: {"ok": True}
    return sold, log


def test_flatten_does_not_liquidate_another_strategys_positions():
    """Switching to a small-cap mode while Core holds swing positions must not
    dump Core's book at 15:45. This is the trap: the rail is absolute for
    positions this engine opened, and silent overreach for ones it didn't."""
    sold, log = _flatten_time_run({
        "ABCD": {"entry": 5.00, "initial_stop": 4.75, "qty": 100,
                 "opened_at": datetime(2026, 8, 14, 10, 0, tzinfo=ET).isoformat(),
                 "mode": "strict", "scaled1": False, "scaled2": False, "ladder": None},
    })
    assert "ABCD" in sold, "its own position must still be flattened"
    assert "AAPL" not in sold, "another strategy's position must be left alone"


def test_foreign_position_is_flagged_rather_than_ignored_silently():
    _, log = _flatten_time_run({})
    joined = " ".join(log)
    assert "AAPL" in joined and "another strategy" in joined


def test_flatten_rail_still_applies_to_every_position_it_opened():
    sold, _ = _flatten_time_run({
        "ABCD": {"entry": 5.00, "initial_stop": 4.75, "qty": 100,
                 "opened_at": datetime(2026, 8, 14, 10, 0, tzinfo=ET).isoformat(),
                 "mode": "strict", "scaled1": False, "scaled2": False, "ladder": None},
        "AAPL": {"entry": 210.0, "initial_stop": 205.0, "qty": 10,
                 "opened_at": datetime(2026, 8, 14, 10, 0, tzinfo=ET).isoformat(),
                 "mode": "strict", "scaled1": False, "scaled2": False, "ladder": None},
    })
    assert set(sold) == {"ABCD", "AAPL"}


def _run_with_positions(mode_key, tickers, state_positions):
    scp.STATE_FILE.unlink(missing_ok=True)
    import json
    if state_positions:
        st = {"date": datetime(2026, 8, 17, 11, 0, tzinfo=ET).strftime("%Y-%m-%d"), "attempts": {},
              "positions": state_positions, "stopped_out": [], "rescued": [],
              "halted_for_day": False}
        scp.STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        scp.STATE_FILE.write_text(json.dumps(st))
    _fake.alpaca_positions = lambda: [
        {"ticker": t, "qty": 5, "current_price": 100.0, "avg_entry": 100.0,
         "unrealized_pnl_pct": 0.0} for t in tickers]
    real_now = scp._now_et
    scp._now_et = lambda: datetime(2026, 8, 17, 11, 0, tzinfo=ET)
    try:
        return scp.run(mode_key, skip_market_check=True)
    finally:
        scp._now_et = real_now
        _fake.alpaca_positions = lambda: []
        scp.STATE_FILE.unlink(missing_ok=True)


def test_another_strategys_positions_do_not_consume_this_modes_slots():
    """The bug: a Core book of 4 swing names against aggro's 3-position cap left
    the small-cap engine permanently at capacity, so it never scanned all day."""
    out = _run_with_positions("intense", ["AAPL", "LLY", "MNST", "WSO"], {})
    joined = " ".join(out["log"])
    assert "Max positions" not in joined, joined[-300:]
    assert "another strategy" in joined


def test_this_modes_own_positions_still_consume_slots():
    own = {t: {"entry": 5.0, "initial_stop": 4.8, "qty": 10, "mode": "intense",
               "opened_at": datetime(2026, 8, 17, 10, 30, tzinfo=ET).isoformat(),
               "scaled1": False, "scaled2": False, "ladder": None}
           for t in ("AAA", "BBB", "CCC")}
    out = _run_with_positions("intense", ["AAA", "BBB", "CCC"], own)
    assert "Max positions" in " ".join(out["log"])


def test_a_mixed_book_counts_only_its_own():
    own = {"AAA": {"entry": 5.0, "initial_stop": 4.8, "qty": 10, "mode": "intense",
                   "opened_at": datetime(2026, 8, 17, 10, 30, tzinfo=ET).isoformat(),
                   "scaled1": False, "scaled2": False, "ladder": None}}
    out = _run_with_positions("intense", ["AAA", "AAPL", "LLY", "WSO"], own)
    assert "Max positions" not in " ".join(out["log"])


def test_intense_has_no_daily_entry_cap():
    """High-intensity means trade count is not the limiter."""
    assert INTENSE.get("MAX_DAILY_ENTRIES") is None


def test_disciplined_keeps_its_entry_cap():
    """The two modes are meant to be opposites; removing this from both would
    collapse the distinction."""
    assert isinstance(STRICT.get("MAX_DAILY_ENTRIES"), int)


def test_removing_the_count_cap_leaves_the_loss_limit_intact():
    """The daily stop is what actually protects the account, so it has to still
    halt the day with the count cap gone."""
    assert INTENSE["DAILY_LOSS_LIMIT"] > 0
    out = _run_with_pnl("intense", -0.031 * 50_000, equity=50_000)
    assert out.get("halted") is True


def test_uncapped_mode_does_not_trip_the_cap_gate_after_many_entries():
    import json
    scp.STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    scp.STATE_FILE.write_text(json.dumps({
        "date": datetime(2026, 8, 17, 11, 0, tzinfo=ET).strftime("%Y-%m-%d"),
        "attempts": {f"T{i}": 1 for i in range(40)},
        "positions": {}, "stopped_out": [], "rescued": [], "halted_for_day": False}))
    # Must be inside the entry window, or run() returns at the time gate before
    # the entry-count gate is ever evaluated and the test proves nothing.
    real_now = scp._now_et
    scp._now_et = lambda: datetime(2026, 8, 17, 11, 0, tzinfo=ET)
    try:
        out = scp.run("intense", skip_market_check=True)
        joined = " ".join(out["log"]).lower()
        assert "outside" not in joined, "fixture fell out at the time gate"
        assert "entry cap" not in joined
    finally:
        scp._now_et = real_now
        scp.STATE_FILE.unlink(missing_ok=True)


# ── PDT floor ──────────────────────────────────────────────────────────────

def test_pdt_headroom_math():
    h = scp.pdt_headroom(26_000)
    assert h["floor"] == scp.PDT_MIN_EQUITY + scp.PDT_BUFFER
    assert h["room"] == 26_000 - h["floor"]
    assert not h["blocked"]
    assert abs(h["max_loss_pct"] - h["room"] / 26_000) < 1e-9


def test_daily_stop_tightens_when_close_to_the_pdt_floor():
    """At $26k the cushion is smaller than a 3% mode stop, so the floor wins."""
    out = _run_with_pnl("intense", 0, equity=26_000)
    joined = " ".join(out["log"])
    assert "tightened" in joined, joined[:400]
    h = scp.pdt_headroom(26_000)
    assert h["max_loss_pct"] < INTENSE["DAILY_LOSS_LIMIT"]


def test_no_new_entries_once_the_account_is_at_the_floor():
    out = _run_with_pnl("intense", 0, equity=25_200)
    assert out.get("pdt_blocked") is True
    assert out["buys"] == 0
    assert "PDT floor" in " ".join(out["log"])


def test_a_loss_that_would_breach_the_floor_halts_the_day_early():
    """-2% is well inside the mode's 3% limit but past the ~1.5% of headroom the
    account actually has above the PDT floor."""
    out = _run_with_pnl("intense", -0.02 * 26_000, equity=26_000)
    assert out.get("halted") is True


def test_large_accounts_are_unaffected_by_the_pdt_logic():
    out = _run_with_pnl("intense", 0, equity=250_000)
    joined = " ".join(out["log"])
    assert "tightened" not in joined and "PDT" not in joined
    assert scp.pdt_headroom(250_000)["applies"] is False


def test_pdt_floor_applies_to_both_modes():
    for k in ("strict", "intense"):
        out = _run_with_pnl(k, 0, equity=25_100)
        assert out.get("pdt_blocked") is True, k


# ── Feed diagnostics ───────────────────────────────────────────────────────

class _Resp:
    def __init__(self, status, tickers=0, text=""):
        self.status_code = status
        self._t = tickers
        self.text = text
    def json(self):
        return {"tickers": [{"ticker": f"T{i}"} for i in range(self._t)]}


def _with_feed(status, tickers=0, text="", key="k"):
    import types
    real_get, real_key = scp.requests.get, scp._pkey
    scp.requests = types.SimpleNamespace(get=lambda *a, **k: _Resp(status, tickers, text))
    scp._pkey = lambda: key
    try:
        return scp.feed_diagnostics()
    finally:
        scp.requests = __import__("requests")
        scp._pkey = real_key


def test_missing_api_key_is_named_explicitly():
    d = _with_feed(200, key=None)
    assert d["key_present"] is False
    assert "POLYGON_API_KEY" in d["verdict"]


def test_plan_rejection_is_distinguished_from_a_quiet_market():
    """403 and 'no movers today' both surfaced as '0 ranked'. They must not."""
    denied = _with_feed(403, text="not entitled")
    quiet = _with_feed(200, tickers=0)
    assert "plan" in denied["verdict"] or "rejected" in denied["verdict"]
    assert denied["verdict"] != quiet["verdict"]
    assert "closed" in quiet["verdict"] or "empty" in quiet["verdict"]


def test_rate_limit_is_called_out():
    assert "429" in _with_feed(429)["verdict"]


def test_healthy_feed_says_an_empty_pool_is_a_filter_result():
    d = _with_feed(200, tickers=40)
    assert "Feed OK" in d["verdict"] and "filter result" in d["verdict"]


# ── Reporting: a cycle must never be silent ────────────────────────────────

def test_a_cycle_that_buys_nothing_still_explains_itself():
    """Weeks of 'no trades' were undiagnosable because a quiet cycle logged
    nothing about why it was quiet."""
    out = _run_with_pnl("intense", 0, equity=50_000)
    joined = " ".join(out["log"]).lower()
    assert any(k in joined for k in ("no entry", "no candidates", "outside", "max positions",
                                     "pdt", "cap reached", "before")), joined[-300:]


def test_run_reports_structured_entries_not_just_a_count():
    """The phone notification names tickers, which needs structure, not a tally."""
    out = _run_with_pnl("intense", 0, equity=50_000)
    assert "entries" in out or out.get("buys", 0) == 0
    if out.get("entries"):
        e = out["entries"][0]
        for k in ("ticker", "qty", "entry", "stop", "setup"):
            assert k in e


def test_funnel_is_returned_for_diagnosis():
    out = _run_with_pnl("intense", 0, equity=50_000)
    assert isinstance(out.get("funnel", {}), dict)


def test_notification_text_names_tickers():
    """Mirrors the server's builder: '2 bought' is not actionable from a phone."""
    entries = [{"ticker": "ABCD", "qty": 300, "entry": 5.00, "stop": 4.75},
               {"ticker": "WXYZ", "qty": 120, "entry": 12.40, "stop": 11.90}]
    text = " · ".join(f"{e['ticker']} {e['qty']}@${e['entry']:.2f} stop ${e['stop']:.2f}"
                      for e in entries[:4])
    assert "ABCD" in text and "$5.00" in text and "$4.75" in text
    title = "Bought " + ", ".join(e["ticker"] for e in entries[:3])
    assert title == "Bought ABCD, WXYZ"


# ── End-to-end: a synthetic market that actually reaches the order path ────
# Every earlier test stopped at an empty feed, so nothing covered scanning,
# grading, sizing or ordering. Three mutations to the execution block passed
# unnoticed because of it. This drives the full pipeline.

import contextlib


@contextlib.contextmanager
def fake_market(tickers=("ABCD", "WXYZ"), setup_grade=80, buy_ok=True):
    orders = []
    stops = []
    saved = {}

    def _stub(name, fn):
        saved[name] = getattr(scp, name)
        setattr(scp, name, fn)

    _fake.polygon_gainers = lambda limit=20: [
        {"Ticker": t, "Price": 5.00, "Chg%": 24.0, "Volume": 9_000_000} for t in tickers]
    _fake.polygon_all_snapshots = lambda: []
    _fake.alpaca_positions = lambda: []

    # A real gapper: opens near 4.55, works up past 5.10 (>12% day range), with a
    # mix of active and quiet minutes so the spread proxy has something to read.
    bars = []
    for i in range(40):
        base = 4.55 + i * 0.015
        active = i % 3 == 0
        bars.append((datetime(2026, 8, 18, 10, i, tzinfo=ET), base,
                     base + (0.07 if active else 0.012),
                     base - (0.06 if active else 0.010),
                     base + 0.02, 120_000 if active else 40_000))
    ctx = {"ticker": "X", "price": 5.00, "bars1": bars, "bars5": bars, "vwap": 4.90,
           "ema9": 4.95, "ema20": 4.92, "ema9_series": [4.9] * 40, "ema20_series": [4.9] * 40,
           "atr5": 0.09, "pdh": 4.85, "pdl": 4.2, "prev_close": 4.03, "pmh": 4.95,
           "orh": 4.98, "orl": 4.6, "hod": 5.10, "hvn": 4.97, "now": None}

    _stub("time_adjusted_rvol", lambda t, now=None: 6.5)
    _stub("float_and_cap", lambda t: (30e6, 100e6))
    _stub("dollar_volume_today", lambda t, now=None: (20e6, 60e6))
    _stub("median_1min_dollar_volume", lambda t, minutes=30: 400_000)
    _stub("halt_count_recent", lambda t, minutes=20: 0)
    _stub("_avg_dollar_volume_20d", lambda t: 80e6)
    _stub("build_context", lambda t, now=None: dict(ctx, ticker=t))
    _stub("filings_hazard", lambda t: {"ok": True, "flags": [], "days_since_424b5": None,
                                       "s3_shelf": False, "serial_splitter": False,
                                       "reverse_split_months": None})
    _stub("catalyst_grade", lambda t: {"grade": "real", "reason": "contract award", "headline": ""})
    _stub("detect_setups", lambda c, m: [{
        "setup": "VWAP reclaim", "level": 4.90, "entry": 5.00, "stop": 4.78,
        "grade": setup_grade, "quality": {}, "why": "held the retest",
        "notes": ["volume dried up", "structure above VWAP"]}])
    _stub("buy_marketable_limit", lambda t, q, px, slip=0.004:
          (orders.append((t, q, px)),
           {"ok": True, "id": f"ord-{t}"} if buy_ok else {"ok": False, "error": "rejected"})[1])
    # Default: the order fills in full. Individual tests override for the
    # unfilled / partial cases.
    _stub("_order_fill", lambda oid, wait_s=3.0:
          (next((q for (tk, q, _) in orders if f"ord-{tk}" == oid), 0), 5.00))
    _stub("cancel_order", lambda oid: True)
    _stub("place_stop", lambda t, q, stop: (stops.append((t, q, stop)), {"ok": True})[1])
    _stub("sell_marketable_limit", lambda t, q, px, slip=0.006: {"ok": True})
    _stub("_now_et", lambda: datetime(2026, 8, 18, 11, 0, tzinfo=ET))
    scp.STATE_FILE.unlink(missing_ok=True)
    try:
        yield orders, stops
    finally:
        for k, v in saved.items():
            setattr(scp, k, v)
        _fake.polygon_gainers = lambda limit=20: []
        _fake.polygon_all_snapshots = lambda: []
        _fake.alpaca_positions = lambda: []
        scp.STATE_FILE.unlink(missing_ok=True)


def test_end_to_end_scan_places_orders_and_names_them():
    with fake_market() as (orders, stops):
        out = scp.run("intense", skip_market_check=True)
    assert out["scanned"] >= 2, out["log"]
    assert out["buys"] >= 1, out["log"]
    assert orders, "no order was ever sent"
    assert out["entries"], "entries must be reported so the alert can name them"
    e = out["entries"][0]
    assert e["ticker"] in ("ABCD", "WXYZ")
    assert e["entry"] == 5.00 and e["stop"] < e["entry"] and e["qty"] > 0
    joined = " ".join(out["log"])
    assert e["ticker"] in joined, "the log must name what it bought"
    assert "VWAP reclaim" in joined


def test_end_to_end_places_a_protective_stop_with_every_entry():
    with fake_market() as (orders, stops):
        scp.run("intense", skip_market_check=True)
    assert len(stops) == len(orders), "every filled entry needs a working stop"
    for _, _, stop in stops:
        assert stop < 5.00


def test_end_to_end_respects_the_concentration_ceiling():
    with fake_market() as (orders, _):
        out = scp.run("intense", skip_market_check=True)
    # fake_market leaves the module-default $50k account in place.
    equity = _fake.alpaca_account()["equity"]
    for e in out["entries"]:
        assert e["notional"] <= equity * INTENSE["CATASTROPHE_CAP_PCT"] + 1


def test_end_to_end_low_grade_setups_are_rejected():
    with fake_market(setup_grade=20) as (orders, _):
        out = scp.run("intense", skip_market_check=True)
    assert out["buys"] == 0
    assert not orders
    joined = " ".join(out["log"]).lower()
    assert "below this mode" in joined and "no entry" in joined


def test_end_to_end_a_rejected_order_is_reported_not_silent():
    with fake_market(buy_ok=False) as (orders, _):
        out = scp.run("intense", skip_market_check=True)
    assert out["buys"] == 0
    joined = " ".join(out["log"]).lower()
    assert "rejected" in joined


def test_end_to_end_funnel_counts_the_pool():
    with fake_market() as _:
        out = scp.run("intense", skip_market_check=True)
    assert out["funnel"].get("pool", 0) >= 2


def test_end_to_end_disciplined_is_stricter_on_the_same_tape():
    """Same synthetic market, both modes — Disciplined must not take more."""
    with fake_market() as (o1, _):
        intense = scp.run("intense", skip_market_check=True)
    with fake_market() as (o2, _):
        strict = scp.run("strict", skip_market_check=True)
    assert strict["buys"] <= intense["buys"]


def test_a_scan_that_grades_candidates_but_buys_none_still_says_why():
    """The final no-buy branch: candidates existed, sizing or ordering stopped
    them. Without this the cycle logs the candidates and then goes quiet."""
    with fake_market(buy_ok=False) as (orders, _):
        out = scp.run("intense", skip_market_check=True)
    assert out["buys"] == 0 and out["opportunities"] > 0
    joined = " ".join(out["log"]).lower()
    assert "no entry" in joined, joined[-300:]


# ── Data-source fallback ───────────────────────────────────────────────────

def test_alpaca_movers_shape_matches_polygon_gainers():
    """The fallback has to be a drop-in or the scanner reads the wrong keys."""
    import types
    real = scp.requests
    class _R:
        status_code = 200
        def json(self):
            return {"gainers": [{"symbol": "ABCD", "percent_change": 23.4, "price": 5.12},
                                {"symbol": "WXYZ", "percent_change": 11.0, "price": 2.30}]}
    scp.requests = types.SimpleNamespace(get=lambda *a, **k: _R())
    os.environ["ALPACA_KEY_ID"] = "x"
    try:
        rows = scp.alpaca_movers(20)
    finally:
        scp.requests = real
    assert rows and set(rows[0]) >= {"Ticker", "Price", "Chg%"}
    assert rows[0]["Ticker"] == "ABCD" and rows[0]["Chg%"] == 23.4


def test_scan_falls_back_to_alpaca_when_polygon_returns_nothing():
    _fake.polygon_gainers = lambda limit=20: None
    _fake.polygon_all_snapshots = lambda: None
    real = scp.alpaca_movers
    real_now = scp._now_et
    scp.alpaca_movers = lambda top=50: [
        {"Ticker": "ABCD", "Price": 5.0, "Chg%": 22.0, "Volume": 0}]
    scp._now_et = lambda: datetime(2026, 8, 18, 11, 0, tzinfo=ET)  # inside the window
    try:
        out = scp.run("intense", skip_market_check=True)
    finally:
        scp.alpaca_movers = real
        scp._now_et = real_now
        _fake.polygon_gainers = lambda limit=20: []
        _fake.polygon_all_snapshots = lambda: []
        scp._ACTIVE_FEED.update(source=None, note="")
        scp.STATE_FILE.unlink(missing_ok=True)
    joined = " ".join(out["log"])
    assert "feed: alpaca" in joined, joined[:300]
    assert "IEX" in joined, "the volume caveat must be stated, not hidden"


def test_iex_volume_factor_relaxes_the_dollar_volume_bar():
    """IEX is a small slice of consolidated volume; applying the SIP threshold
    to it would reject every name for the wrong reason."""
    assert 0 < scp.VOLUME_FEED_FACTOR < 1
    assert INTENSE["DOLLAR_VOL_MIN"] * scp.VOLUME_FEED_FACTOR < INTENSE["DOLLAR_VOL_MIN"]


def test_aggs_falls_through_to_alpaca_on_a_plan_rejection():
    import types
    calls = {"alpaca": 0}
    real_req, real_alp = scp.requests, scp._aggs_alpaca
    class _R:
        status_code = 403
        text = "NOT_AUTHORIZED"
        def json(self): return {}
    scp.requests = types.SimpleNamespace(get=lambda *a, **k: _R())
    scp._aggs_alpaca = lambda *a, **k: (calls.__setitem__("alpaca", calls["alpaca"] + 1), [{"t": 1}])[1]
    scp._ACTIVE_FEED.update(source=None)
    real_key = scp._pkey
    scp._pkey = lambda: "k"
    try:
        got = scp._aggs("ABCD", 1, "minute", "2026-08-01", "2026-08-18")
    finally:
        scp.requests, scp._aggs_alpaca, scp._pkey = real_req, real_alp, real_key
    assert calls["alpaca"] == 1 and got == [{"t": 1}]


def test_alpaca_bars_paginates_instead_of_truncating():
    """A 20-session minute lookback needs ~11k bars; Alpaca caps a page at 10k.
    Unpaginated with sort=asc, the OLDEST bars are kept and the recent sessions
    the RVOL baseline depends on are silently dropped."""
    import types
    pages = [
        {"bars": [{"t": "2026-08-01T13:31:00Z", "o": 1, "h": 1, "l": 1, "c": 1, "v": 10}],
         "next_page_token": "tok1"},
        {"bars": [{"t": "2026-08-02T13:31:00Z", "o": 2, "h": 2, "l": 2, "c": 2, "v": 20}],
         "next_page_token": None},
    ]
    seen = []

    class _R:
        status_code = 200
        def __init__(self, i): self._i = i
        def json(self): return pages[self._i]

    def _get(url, headers=None, params=None, timeout=None):
        seen.append(params.get("page_token"))
        return _R(min(len(seen) - 1, len(pages) - 1))

    real = scp.requests
    scp.requests = types.SimpleNamespace(get=_get)
    os.environ["ALPACA_KEY_ID"] = "x"
    try:
        bars = scp.alpaca_bars("ABCD", "1Min", start="2026-08-01T00:00:00Z")
    finally:
        scp.requests = real
    assert len(bars) == 2, f"pagination did not follow the token: {bars}"
    assert seen == [None, "tok1"], seen


def test_alpaca_bars_stops_paginating_on_an_error_page():
    """A mid-pagination failure must return what it has, not loop or crash."""
    import types
    calls = {"n": 0}

    class _Ok:
        status_code = 200
        def json(self):
            return {"bars": [{"t": "2026-08-01T13:31:00Z", "o": 1, "h": 1, "l": 1,
                              "c": 1, "v": 10}], "next_page_token": "tok"}

    class _Bad:
        status_code = 500
        def json(self): return {}

    def _get(url, headers=None, params=None, timeout=None):
        calls["n"] += 1
        return _Ok() if calls["n"] == 1 else _Bad()

    real = scp.requests
    scp.requests = types.SimpleNamespace(get=_get)
    os.environ["ALPACA_KEY_ID"] = "x"
    try:
        bars = scp.alpaca_bars("ABCD", "1Min")
    finally:
        scp.requests = real
    assert bars and len(bars) == 1, "must return the page it did get"
    # And must stop: without the early return it keeps requesting the bad page
    # until the loop bound, wasting the rate limit on every scan.
    assert calls["n"] == 2, f"kept requesting after an error: {calls['n']} calls"


def test_pagination_is_bounded():
    """A server that always returns a token must not hang the scan."""
    import types
    calls = {"n": 0}

    class _R:
        status_code = 200
        def json(self):
            return {"bars": [{"t": "2026-08-01T13:31:00Z", "o": 1, "h": 1, "l": 1,
                              "c": 1, "v": 1}], "next_page_token": "always"}

    def _get(url, headers=None, params=None, timeout=None):
        calls["n"] += 1
        return _R()

    real = scp.requests
    scp.requests = types.SimpleNamespace(get=_get)
    os.environ["ALPACA_KEY_ID"] = "x"
    try:
        scp.alpaca_bars("ABCD", "1Min")
    finally:
        scp.requests = real
    assert calls["n"] <= 6, f"unbounded pagination: {calls['n']} requests"


def test_snapshots_are_fetched_in_bulk_not_per_ticker():
    """Per-ticker quotes would burn the rate limit; one call covers 100 symbols."""
    import types
    calls = {"n": 0}

    class _R:
        status_code = 200
        def json(self):
            return {"snapshots": {
                "ABCD": {"latestTrade": {"p": 5.0}, "dailyBar": {"c": 5.0, "v": 900000},
                         "prevDailyBar": {"c": 4.0}},
                "WXYZ": {"latestTrade": {"p": 12.0}, "dailyBar": {"c": 12.0, "v": 500000},
                         "prevDailyBar": {"c": 11.0}}}}

    def _get(url, headers=None, params=None, timeout=None):
        calls["n"] += 1
        assert "," in params["symbols"], "symbols must be batched"
        return _R()

    real = scp.requests
    scp.requests = types.SimpleNamespace(get=_get)
    os.environ["ALPACA_KEY_ID"] = "x"
    try:
        got = scp.alpaca_snapshots(["ABCD", "WXYZ"])
    finally:
        scp.requests = real
    assert calls["n"] == 1
    assert got["ABCD"]["Chg%"] == 25.0, got["ABCD"]
    assert got["WXYZ"]["Price"] == 12.0


def test_snapshot_without_a_previous_close_is_skipped():
    """No prior close means no computable % change — better dropped than zero."""
    import types

    class _R:
        status_code = 200
        def json(self):
            return {"snapshots": {"NEWL": {"latestTrade": {"p": 8.0},
                                           "dailyBar": {"c": 8.0}, "prevDailyBar": {}}}}
    real = scp.requests
    scp.requests = types.SimpleNamespace(get=lambda *a, **k: _R())
    os.environ["ALPACA_KEY_ID"] = "x"
    try:
        assert scp.alpaca_snapshots(["NEWL"]) == {}
    finally:
        scp.requests = real


# ── Tunability ─────────────────────────────────────────────────────────────

def test_intense_gates_are_env_tunable():
    """A bad threshold should cost a Railway variable change, not a deploy."""
    import importlib
    os.environ["INTENSE_RVOL_MIN"] = "0.9"
    os.environ["INTENSE_PRICE_MAX"] = "12"
    try:
        importlib.reload(scp)
        m = scp.get_mode("intense")
        assert m["RVOL_MIN"] == 0.9
        assert m["PRICE_MAX"] == 12.0
    finally:
        os.environ.pop("INTENSE_RVOL_MIN", None)
        os.environ.pop("INTENSE_PRICE_MAX", None)
        importlib.reload(scp)
    assert scp.get_mode("intense")["RVOL_MIN"] == 1.8


def test_a_malformed_override_falls_back_to_the_default():
    import importlib
    os.environ["INTENSE_RVOL_MIN"] = "not-a-number"
    try:
        importlib.reload(scp)
        assert scp.get_mode("intense")["RVOL_MIN"] == 1.8
    finally:
        os.environ.pop("INTENSE_RVOL_MIN", None)
        importlib.reload(scp)


def test_intense_is_looser_than_disciplined_on_every_universe_gate():
    I, S = scp.get_mode("intense"), scp.get_mode("strict")
    assert I["RVOL_MIN"] < S["RVOL_MIN"]
    assert I["PRICE_MAX"] > S["PRICE_MAX"]
    assert I["FLOAT_MAX"] > S["FLOAT_MAX"]
    assert I["MIN_DAY_CHANGE"] < S["MIN_DAY_CHANGE"]
    assert I["MIN_SETUP_GRADE"] < S["MIN_SETUP_GRADE"]


def test_loosening_did_not_touch_the_risk_rails():
    """Frequency was the goal; per-trade risk and the safety limits were not."""
    I = scp.get_mode("intense")
    assert I["CATASTROPHE_CAP_PCT"] <= 0.20
    assert I["LADDER_TARGET_EQUITY_PCT"] <= 0.18
    assert I["DAILY_LOSS_LIMIT"] <= 0.03
    assert I["MAX_POSITIONS"] <= 2
    assert I["R_PCT"] <= 0.01
    assert scp.MAX_ATTEMPTS_PER_TICKER == 2


def test_near_misses_are_reported_when_nothing_clears():
    """The point of near-miss reporting is to name the ONE threshold to move.
    Without it, an empty scan invites loosening everything at once."""
    _fake.polygon_gainers = lambda limit=20: [
        {"Ticker": "TOOBIG", "Price": 75.0, "Chg%": 30.0, "Volume": 5_000_000}]
    _fake.polygon_all_snapshots = lambda: []
    real_now, real_alp = scp._now_et, scp.alpaca_movers
    scp._now_et = lambda: datetime(2026, 8, 18, 11, 0, tzinfo=ET)
    scp.alpaca_movers = lambda top=50: None
    try:
        out = scp.run("intense", skip_market_check=True)
    finally:
        scp._now_et, scp.alpaca_movers = real_now, real_alp
        _fake.polygon_gainers = lambda limit=20: []
        scp.STATE_FILE.unlink(missing_ok=True)
    joined = " ".join(out["log"])
    assert "closest misses" in joined, joined[:400]
    assert "TOOBIG" in joined
    assert "near_miss" in out.get("funnel", {})


# ── Sizing on an IEX-measured book ─────────────────────────────────────────

def test_liquidity_scale_only_applies_on_the_alpaca_feed():
    scp._ACTIVE_FEED.update(source="polygon")
    assert scp.liquidity_scale() == 1.0
    scp._ACTIVE_FEED.update(source="alpaca")
    try:
        assert scp.liquidity_scale() > 1.0
        assert scp.liquidity_scale() <= 40.0, "scaling must stay bounded"
    finally:
        scp._ACTIVE_FEED.update(source=None)


def test_iex_liquidity_caps_no_longer_dominate_the_size():
    """The live failure: DPRO sized 40 shares where 1% risk called for 324,
    because the 1-minute cap was measured on IEX volume."""
    entry, stop = 5.25, 4.85          # 7.6% stop, inside MAX_STOP_PCT
    iex_med1, iex_adv = 1_400, 4_000_000        # what IEX actually showed
    unscaled = scp.size_position(25_926, entry, stop, INTENSE, "DPRO",
                                 adv=iex_adv, med1=iex_med1)
    scp._ACTIVE_FEED.update(source="alpaca")
    try:
        k = scp.liquidity_scale()
        scaled = scp.size_position(25_926, entry, stop, INTENSE, "DPRO",
                                   adv=iex_adv * k, med1=iex_med1 * k)
    finally:
        scp._ACTIVE_FEED.update(source=None)
    assert unscaled["binding_cap"] == "min1"
    assert scaled["qty"] > unscaled["qty"] * 5
    # ...but never past the risk-based size, which is the real limit.
    assert scaled["qty"] <= scaled["caps"]["base"]


def test_scaling_never_breaches_the_concentration_ceiling():
    scp._ACTIVE_FEED.update(source="alpaca")
    try:
        r = scp.size_position(25_926, 5.25, 5.20, INTENSE, "X",
                              adv=9e9, med1=9e8)
    finally:
        scp._ACTIVE_FEED.update(source=None)
    assert r["qty"] * 5.25 <= 25_926 * INTENSE["CATASTROPHE_CAP_PCT"] + 6


# ── Fill verification ──────────────────────────────────────────────────────

def _fill_stub(status, filled_qty, avg=5.0):
    import types
    class _R:
        status_code = 200
        def json(self):
            return {"status": status, "filled_qty": str(filled_qty),
                    "filled_avg_price": str(avg)}
    return types.SimpleNamespace(get=lambda *a, **k: _R(),
                                 delete=lambda *a, **k: types.SimpleNamespace(status_code=204))


def test_unfilled_entry_places_no_stop_and_is_cancelled():
    """NEOV left a live stop for 32 shares whose buy was cancelled unfilled."""
    with fake_market() as (orders, stops):
        scp._order_fill = lambda oid, wait_s=3.0: (0, 0.0)
        out = scp.run("intense", skip_market_check=True)
    assert not stops, "a stop must never exist without a filled position"
    assert out["buys"] == 0
    assert "didn't fill" in " ".join(out["log"])


def test_partial_fill_sizes_the_stop_to_what_actually_filled():
    with fake_market() as (orders, stops):
        scp._order_fill = lambda oid, wait_s=3.0: (7, 5.01)
        out = scp.run("intense", skip_market_check=True)
    assert stops, "a partial fill still needs a stop"
    for _, q, _ in stops:
        assert q == 7, f"stop sized to {q}, should match the 7 filled"
    assert out["entries"][0]["qty"] == 7


def test_scan_applies_the_liquidity_scale_to_real_sizing():
    """Exercises the scan's own use of the scale, not a pre-scaled call. This is
    the path that produced 40 shares instead of 324."""
    def _run(feed):
        with fake_market() as (orders, _):
            scp._avg_dollar_volume_20d = lambda t: 4_000_000
            scp.median_1min_dollar_volume = lambda t, minutes=30: 1_400
            scp._ACTIVE_FEED.update(source=feed)
            try:
                out = scp.run("intense", skip_market_check=True)
            finally:
                scp._ACTIVE_FEED.update(source=None)
        return out["entries"][0]["qty"] if out.get("entries") else 0

    thin_iex = _run("alpaca")
    as_measured = _run("polygon")
    assert as_measured > 0 and thin_iex > 0
    assert thin_iex > as_measured * 3, (
        f"IEX-measured book still dominates sizing: {thin_iex} vs {as_measured}")


def test_liquidity_scale_stays_bounded_for_a_tiny_factor():
    """A near-zero factor would otherwise imply a near-infinite book."""
    import importlib
    os.environ["IEX_VOLUME_FACTOR"] = "0.0001"
    try:
        importlib.reload(scp)
        scp._ACTIVE_FEED.update(source="alpaca")
        assert scp.liquidity_scale() <= 40.0
    finally:
        scp._ACTIVE_FEED.update(source=None)
        os.environ.pop("IEX_VOLUME_FACTOR", None)
        importlib.reload(scp)


# ── Config plumbing ────────────────────────────────────────────────────────
# These need the REAL trading module, but this file stubs `trading` in
# sys.modules so the strategy tests stay offline. Run them in a subprocess.

def _in_subprocess(body: str, env_extra=None):
    import subprocess, os
    env = dict(os.environ)
    env["PYTHONPATH"] = _ROOT
    env.update(env_extra or {})
    r = subprocess.run([sys.executable, "-c", body], capture_output=True,
                       text=True, timeout=300, env=env,
                       cwd=os.path.join(_ROOT, "desktop", "backend"))
    assert r.returncode == 0, (r.stdout + r.stderr)[-600:]
    return r.stdout.strip().splitlines()[-1].strip()


def test_mode_write_is_read_back_by_the_engine():
    """The bug this guards: server.py resolved autopilot_config.json relative to
    itself while trading.py resolved it relative to the repo root, so every mode
    switch was written to a file the autopilot never read."""
    out = _in_subprocess("""
import engine as trading
before = trading.load_autopilot_config().get("STRATEGY_MODE")
try:
    trading.save_autopilot_config({"STRATEGY_MODE": "aggro"})
    assert trading.load_autopilot_config().get("STRATEGY_MODE") == "aggro"
    trading.save_autopilot_config({"STRATEGY_MODE": "strict"})
    assert trading.load_autopilot_config().get("STRATEGY_MODE") == "strict"
    print("ROUNDTRIP_OK")
finally:
    trading.save_autopilot_config({"STRATEGY_MODE": before or "core"})
""")
    assert "ROUNDTRIP_OK" in out


def test_no_server_site_bypasses_the_shared_config_path():
    src = (pathlib.Path(_ROOT) / "desktop" / "backend" / "server.py").read_text()
    stray = re.findall(r'pathlib\.Path\(__file__\)\.parent / "autopilot_config\.json"', src)
    assert not stray, f"{len(stray)} server.py site(s) still bypass engine.autopilot_cfg_path()"


def test_config_follows_the_persistent_volume_when_one_is_mounted():
    """On Railway the container filesystem is wiped every deploy — a mode saved
    outside DB_DIR silently reverts to the git contents on the next push."""
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        out = _in_subprocess(
            "import engine; print(engine.autopilot_cfg_path())",
            {"DB_DIR": d})
        assert out.startswith(d), out
    out = _in_subprocess("import engine; print(engine.autopilot_cfg_path())",
                         {"DB_DIR": ""})
    assert out.endswith("autopilot_config.json") and "/tmp/" not in out


def test_every_run_result_reports_a_scanned_count():
    """0 must be reported as 0. The UI renders `data.scanned || '?'`, so a
    missing key and a genuine zero both surfaced as '? stocks scanned'."""
    for key in ("strict", "intense"):
        out = _run_with_pnl(key, 0)
        assert "scanned" in out, f"{key} run returned no scanned count"
        assert isinstance(out["scanned"], int)


# ── Runner ─────────────────────────────────────────────────────────────────

def main():
    tests = [(n, o) for n, o in sorted(globals().items())
             if n.startswith("test_") and callable(o)]
    print("small-cap pullback tests")
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"  PASS  {name}")
        except AssertionError as e:
            failed += 1
            print(f"  FAIL  {name}: {e}")
        except Exception as e:
            failed += 1
            print(f"  ERROR {name}: {type(e).__name__}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
