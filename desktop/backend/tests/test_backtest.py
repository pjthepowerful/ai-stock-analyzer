"""Regression tests for run_backtest accuracy fixes.

Covers the two bugs that corrupted reported numbers:
  - chronological compounding (results must be order-independent)
  - profit-factor definition (gross win / gross loss)

These test the *logic* in isolation rather than calling run_backtest (which
needs network data), mirroring the production formulas exactly.

Run directly:  python3 desktop/backend/tests/test_backtest.py
"""
import os
import random
import sys

sys.path.insert(0, os.path.dirname(__file__))


def _compound(pending, start=25_000, risk=0.02):
    """Mirror of run_backtest's chronological compounding pass."""
    pending = sorted(pending, key=lambda t: t["entry_date"])
    cap = start
    for pt in pending:
        if cap < 500:
            break
        max_risk = cap * risk * pt["score_mult"]
        rps = pt["risk_per_share"]
        if rps <= 0:
            continue
        qty = max(1, int(max_risk / rps))
        cost = qty * pt["entry"]
        if cost > cap * 0.25:
            qty = max(1, int(cap * 0.25 / pt["entry"]))
            cost = qty * pt["entry"]
        if cost > cap:
            continue
        cap += pt["ret_frac"] * cost
    return round(cap, 2)


def _sample_trades(n=50):
    return [{"entry_date": i, "entry": 50 + (i % 30),
             "ret_frac": (0.05 if i % 3 else -0.03),
             "risk_per_share": 1.5, "score_mult": 1.0} for i in range(n)]


def test_compounding_is_order_independent():
    base = _sample_trades()
    expected = _compound(base)
    for _ in range(10):
        shuffled = base[:]
        random.shuffle(shuffled)
        assert _compound(shuffled) == expected, "final capital must not depend on collection order"


def test_compounding_grows_with_winning_trades():
    winners = [{"entry_date": i, "entry": 100, "ret_frac": 0.04,
                "risk_per_share": 2.0, "score_mult": 1.0} for i in range(10)]
    assert _compound(winners) > 25_000


def test_compounding_shrinks_with_losing_trades():
    losers = [{"entry_date": i, "entry": 100, "ret_frac": -0.04,
               "risk_per_share": 2.0, "score_mult": 1.0} for i in range(10)]
    assert _compound(losers) < 25_000


def _profit_factor(trades):
    """Mirror of run_backtest's PF computation."""
    gross_win = sum(t for t in trades if t > 0)
    gross_loss = abs(sum(t for t in trades if t < 0))
    if gross_loss > 0:
        return gross_win / gross_loss
    return float("inf") if gross_win > 0 else 0


def test_profit_factor_definition():
    # 3 wins of +100 (=300), 2 losses of -100 (=200) -> PF 1.5
    assert _profit_factor([100, 100, 100, -100, -100]) == 1.5


def test_profit_factor_all_wins_is_inf():
    assert _profit_factor([10, 20, 30]) == float("inf")


def test_profit_factor_no_trades_is_zero():
    assert _profit_factor([]) == 0


def test_slippage_makes_breakeven_trade_a_loss():
    # A trade that exits exactly at entry should net negative after round-trip slippage.
    SLIPPAGE = 0.0005
    entry = 100.0
    exit_ = 100.0
    entry_fill = entry * (1 + SLIPPAGE)
    exit_fill = exit_ * (1 - SLIPPAGE)
    ret_frac = (exit_fill - entry_fill) / entry
    assert ret_frac < 0, "round-trip slippage must turn a flat trade into a small loss"


def test_stop_distance_is_capped():
    # Regression: AMD at $516 with high ATR produced a 15% stop and $750 target.
    # The stop must be clamped to [1.5%, 4%] of entry.
    MAX_STOP_PCT = 0.04
    MIN_STOP_PCT = 0.015
    entry = 516.10
    atr = 26.0  # high ATR -> 3xATR = $78 stop (15%) before clamping
    stop_atr = round(entry - 3.0 * atr, 2)
    stop_loss = stop_atr
    min_stop = round(entry * (1 - MIN_STOP_PCT), 2)
    max_stop = round(entry * (1 - MAX_STOP_PCT), 2)
    if stop_loss > min_stop:
        stop_loss = min_stop
    if stop_loss < max_stop:
        stop_loss = max_stop
    risk_pct = (entry - stop_loss) / entry * 100
    assert 1.4 <= risk_pct <= 4.1, f"stop should be clamped to ~4%, got {risk_pct:.1f}%"
    # And the 3:1 target should now be realistic, not $750.
    risk = entry - stop_loss
    target = entry + 3 * risk
    assert target < entry * 1.13, f"target should be realistic, got {target:.0f}"


def _run():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = 0
    for t in tests:
        try:
            t()
            print(f"  PASS  {t.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"  FAIL  {t.__name__}: {e}")
        except Exception as e:
            print(f"  ERROR {t.__name__}: {type(e).__name__}: {e}")
    print(f"\n{passed}/{len(tests)} passed")
    return passed == len(tests)


if __name__ == "__main__":
    print("backtest accuracy tests")
    sys.exit(0 if _run() else 1)
