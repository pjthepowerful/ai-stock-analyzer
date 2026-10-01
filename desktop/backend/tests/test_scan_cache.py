"""Scan pre-screen data: a throttled (empty) Yahoo download must not drop a
ticker that had good data recently, and filtered names are remembered."""
import os
import sys

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.join(_ROOT, "desktop", "backend"))

import engine as _engine  # noqa: F401,E402  installs the streamlit shim for trading.py
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import trading  # noqa: E402


def _frame(tickers, price=50.0):
    idx = pd.date_range(end=pd.Timestamp.now().normalize(), periods=260, freq="B")
    cols = {}
    for t in tickers:
        close = np.linspace(price * 0.8, price, len(idx))
        for f, v in (("Open", close), ("High", close * 1.01), ("Low", close * 0.99),
                     ("Close", close), ("Volume", np.full(len(idx), 2_000_000.0))):
            cols[(t, f)] = v
    return pd.DataFrame(cols, index=idx)


def test_throttled_ticker_falls_back_to_last_good(monkeypatch):
    for c in (trading._SCAN_DATA_CACHE, trading._SCAN_LAST_GOOD, trading._SCAN_DEMAND):
        c.clear()
    monkeypatch.setattr(trading, "_calc_relative_strength", lambda h: {"rs_score": 0})
    monkeypatch.setattr(trading, "_clear_yf_session", lambda: None)
    monkeypatch.setattr(trading.time if hasattr(trading, "time") else __import__("time"), "sleep", lambda s: None)
    monkeypatch.setattr(trading.yf, "download", lambda chunk, **k: _frame(chunk))
    first = trading.batch_fetch_scan(["AAA", "BBB"])
    assert set(first) == {"AAA", "BBB"}

    trading._SCAN_DATA_CACHE.clear()                              # past the TTL
    monkeypatch.setattr(trading.yf, "download", lambda chunk, **k: pd.DataFrame())  # throttled
    second = trading.batch_fetch_scan(["AAA", "BBB"])
    assert set(second) == {"AAA", "BBB"}, "throttled tickers were dropped"
    assert second["AAA"]["price"] == first["AAA"]["price"]


def test_illiquid_name_is_remembered_not_redownloaded(monkeypatch):
    for c in (trading._SCAN_DATA_CACHE, trading._SCAN_LAST_GOOD):
        c.clear()
    calls = []

    def dl(chunk, **k):
        calls.append(list(chunk))
        f = _frame(chunk, price=2.0)
        for t in chunk:
            f[(t, "Volume")] = 100.0                              # ~$200/day: filtered out
        return f
    monkeypatch.setattr(trading.yf, "download", dl)
    monkeypatch.setattr(trading, "_calc_relative_strength", lambda h: {"rs_score": 0})
    assert trading.batch_fetch_scan(["TINY"]) == {}
    assert trading.batch_fetch_scan(["TINY"]) == {}
    assert len(calls) == 1, "a filtered ticker was downloaded again inside the TTL"
