"""Levels shown to a buyer must read stop < entry < target on every rating.

A SELL's `trade` is short-side (stop above, target below) because autopilot
shorts with it; `plan` is what Analyze, chat and position sizing show.
"""
import os
import sys

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.join(_ROOT, "desktop", "backend"))

import engine as _engine  # noqa: F401,E402  installs the streamlit shim for trading.py
import trading  # noqa: E402


def _data(price, sma20, sma50, sma200, rsi, supports=()):
    return {
        "price": price,
        "technicals": {
            "sma_20": sma20, "sma_50": sma50, "sma_200": sma200, "rsi": rsi,
            "adx": 30, "atr": price * 0.03, "macd_hist": -1 if price < sma50 else 1,
            "vol_ratio": 1.0, "obv_trend": "falling" if price < sma50 else "rising",
            "bb_pct_b": 0.5, "trend_regime": "strong_downtrend" if price < sma200 else "strong_uptrend",
            "support_levels": list(supports), "resistance_levels": [],
        },
        "news_sentiment": {"score": -5 if price < sma50 else 0},
        "relative_strength": {"rs_score": -8 if price < sma50 else 6, "outperforming": price > sma50},
    }


def _ordered(t):
    return t["stop_loss"] < t["entry"] < t["target_1"] < t["target_2"]


def test_downtrend_sell_plan_is_long_side_and_trade_is_short_side():
    s = trading.generate_trade_signal(_data(50, 60, 70, 80, 28))
    assert s["action"] in ("SELL", "STRONG_SELL")
    assert _ordered(s["plan"]), s["plan"]
    assert s["trade"]["stop_loss"] > s["trade"]["entry"] > s["trade"]["target_1"]


def test_buy_plan_equals_trade():
    s = trading.generate_trade_signal(_data(100, 99, 90, 80, 50, supports=(97,)))
    assert _ordered(s["plan"])
    if s["action"] in ("BUY", "STRONG_BUY"):
        for k in ("entry", "stop_loss", "target_1", "target_2"):
            assert s["plan"][k] == s["trade"][k]


def test_support_above_price_never_puts_the_stop_above_entry():
    s = trading.generate_trade_signal(_data(100, 99, 90, 80, 50, supports=(104,)))
    assert _ordered(s["plan"]), s["plan"]
