"""Smoke tests for trading.route() — the chat -> intent classifier.

These lock in the routing-bug fixes from earlier sessions (e.g. "stop loss"
must not stop autopilot, questions must not execute trades) plus the core
buy/sell/short parsing.

Run directly:  python3 desktop/backend/tests/test_router.py
Or via pytest: pytest desktop/backend/tests/test_router.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from _trading_harness import trading  # noqa: E402

route = trading.route


# ── Greetings / chat ────────────────────────────────────────────────────────
def test_greetings_are_chat():
    for g in ("hi", "hello", "hey", "thanks", "help"):
        assert route(g)["type"] == "chat", g


# ── Buy parsing ───────────────────────────────────────────────────────────────
def test_buy_plain():
    r = route("buy NVDA")
    assert r["type"] == "buy" and r["ticker"] == "NVDA"
    assert r["qty"] is None and r["notional"] is None


def test_buy_with_quantity():
    r = route("buy 10 NVDA")
    assert r["type"] == "buy" and r["qty"] == 10


def test_buy_with_dollar_notional():
    r = route("buy $500 of TSLA")
    assert r["type"] == "buy" and r["notional"] == 500.0


# ── Sell / short / cover ──────────────────────────────────────────────────────
def test_sell_with_quantity():
    r = route("sell 5 AAPL")
    assert r["type"] == "sell" and r["qty"] == 5


def test_sell_all():
    r = route("sell all NVDA")
    assert r["type"] == "sell" and r["sell_all"] is True


def test_short_command():
    r = route("short 10 AAPL")
    assert r["type"] == "short" and r["qty"] == 10


def test_cover_all():
    r = route("cover all NVDA")
    assert r["type"] == "cover" and r["cover_all"] is True


# ── Autopilot routing (the bug-prone area) ────────────────────────────────────
def test_start_autopilot():
    assert route("start autopilot")["type"] == "autopilot"
    assert route("autopilot")["type"] == "autopilot"


def test_stop_autopilot():
    assert route("stop autopilot")["type"] == "stop_autopilot"
    assert route("stop")["type"] == "stop_autopilot"


def test_stop_loss_does_NOT_stop_autopilot():
    # Regression: "stop loss" contains "stop" but must never deactivate autopilot.
    r = route("set a stop loss on AAPL")
    assert r["type"] != "stop_autopilot", f"stop-loss wrongly routed to {r['type']}"


def test_autopilot_question_is_not_a_command():
    # "explain autopilot" should go to chat/AI, not start autopilot.
    r = route("explain how autopilot works")
    assert r["type"] != "autopilot"


# ── Questions must not execute trades ─────────────────────────────────────────
def test_question_does_not_buy():
    # "should I buy NVDA?" is advice, not a buy command.
    r = route("should i buy NVDA")
    assert r["type"] != "buy", f"question wrongly routed to {r['type']}"


def test_sell_question_routes_to_analyze_with_original_msg():
    # Feeds the EXIT/AVOID framing fix — analyze must carry the raw message.
    r = route("should i sell my TSLA")
    assert r["type"] == "analyze"
    assert r.get("_original_msg") == "should i sell my TSLA"


# ── Other intents ─────────────────────────────────────────────────────────────
def test_positions_query():
    assert route("what do i own")["type"] == "positions"


def test_close_all():
    assert route("close all positions")["type"] == "close_all"


def test_bare_ticker_is_analyze():
    r = route("NVDA")
    assert r["type"] == "analyze" and r["ticker"] == "NVDA"


def test_stock_ideas():
    r = route("what stocks should i buy")
    assert r["type"] == "stock_ideas"


def test_shares_math_with_ticker_is_analyze_not_scan():
    # "$5000, how many shares of TSLA" must analyze TSLA, not trigger the scanner.
    r = route("I have $5,000, how many shares of TSLA can I buy?")
    assert r["type"] == "analyze" and r["ticker"] == "TSLA", f"got {r}"


def test_position_worth_with_ticker_is_analyze():
    r = route("if I buy 100 shares of NVDA what's it worth")
    assert r["type"] == "analyze" and r["ticker"] == "NVDA", f"got {r}"


def test_generic_money_question_still_scans():
    # No specific ticker -> still routes to ideas scanner.
    r = route("what should i buy with $5000")
    assert r["type"] == "stock_ideas", f"got {r}"


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
    print("router smoke tests")
    sys.exit(0 if _run() else 1)
