"""Tests for signal_logic.classify_analysis_side — the EXIT-vs-SHORT fix.

Run directly:  python3 desktop/backend/tests/test_signal_logic.py
Or via pytest: pytest desktop/backend/tests/test_signal_logic.py
"""
import os
import sys

# Make the repo-root importable (signal_logic.py lives there).
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from signal_logic import classify_analysis_side  # noqa: E402


def test_bullish_is_long():
    assert classify_analysis_side("BUY", "what about NVDA", False) == "LONG"
    assert classify_analysis_side("STRONG_BUY", "thoughts on AAPL", False) == "LONG"


def test_hold_is_neutral():
    assert classify_analysis_side("HOLD", "how's TSLA looking", False) == "NEUTRAL"
    assert classify_analysis_side("NO_DATA", "??", False) == "NEUTRAL"


def test_bearish_not_held_is_avoid():
    # Bearish, no holding, no exit phrasing -> stay flat, never a SHORT card.
    assert classify_analysis_side("SELL", "what do you think of F", False) == "AVOID"
    assert classify_analysis_side("STRONG_SELL", "analyze NIO", False) == "AVOID"


def test_bearish_when_held_is_exit():
    # The core bug: holding a long + bearish signal must be EXIT, never SHORT.
    assert classify_analysis_side("SELL", "analyze NVDA", True) == "EXIT"
    assert classify_analysis_side("STRONG_SELL", "thoughts?", True) == "EXIT"


def test_exit_phrasing_triggers_exit_even_without_position_data():
    # If they ask to sell, treat as EXIT even if the position lookup failed.
    assert classify_analysis_side("SELL", "should I sell my AAPL?", False) == "EXIT"
    assert classify_analysis_side("STRONG_SELL", "thinking of dumping my TSLA", False) == "EXIT"
    assert classify_analysis_side("SELL", "time to take profit on NVDA", False) == "EXIT"


def test_exit_phrasing_does_not_override_bullish():
    # "sell" appearing in a bullish-scored question shouldn't force EXIT.
    assert classify_analysis_side("BUY", "should I sell and rebuy NVDA", False) == "LONG"


def test_case_insensitive():
    assert classify_analysis_side("STRONG_SELL", "SHOULD I SELL MY AAPL", False) == "EXIT"


def test_empty_message_safe():
    assert classify_analysis_side("SELL", "", False) == "AVOID"
    assert classify_analysis_side("SELL", None, False) == "AVOID"


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
    print("signal_logic tests")
    sys.exit(0 if _run() else 1)
