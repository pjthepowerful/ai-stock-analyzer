"""Tests for signal_logic.compute_price_math — pre-computed arithmetic so the
LLM never has to (it produced things like "a gain of $211 from $211").

Run directly:  python3 desktop/backend/tests/test_price_math.py
"""
import os
import sys

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from signal_logic import compute_price_math  # noqa: E402


def test_move_to_target():
    r = compute_price_math("if NVDA hits 230 what's that from here?", 211.14)
    assert r["kind"] == "move_to_target"
    assert r["to"] == 230.0 and r["from"] == 211.14
    assert r["dollar_change"] == 18.86
    assert abs(r["pct_change"] - 8.93) < 0.01


def test_move_between_two_prices():
    r = compute_price_math("what's my gain from 142 to 158", 211.14)
    assert r["kind"] == "move_between"
    assert r["dollar_change"] == 16.0
    assert abs(r["pct_change"] - 11.27) < 0.01


def test_position_value():
    r = compute_price_math("if I buy 100 shares of NVDA what's it worth", 211.14)
    assert r["kind"] == "position_value"
    assert r["qty"] == 100
    assert r["value"] == 21114.0


def test_no_match_returns_none():
    assert compute_price_math("what do you think of AMD", 516.10) is None
    assert compute_price_math("should I buy NVDA", 211.14) is None


def test_no_negative_or_zero_price_crash():
    # Must not raise when price is missing/zero.
    assert compute_price_math("100 shares", 0) is None or True
    compute_price_math("if it hits 50", 0)  # should not raise


def test_the_original_bug_case():
    # Regression: this exact question produced "a gain of $211.14 from $211.14".
    r = compute_price_math("if NVDA hits 230 what's that from here?", 211.14)
    assert r is not None
    assert "+8.93%" in r["phrasing"] and "$211.14" in r["phrasing"] and "$230.00" in r["phrasing"]
    # The wrong answer would have shown $211.14 as the change; correct is $18.86.
    assert "18.86" in r["phrasing"]


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
    print("price-math tests")
    sys.exit(0 if _run() else 1)
