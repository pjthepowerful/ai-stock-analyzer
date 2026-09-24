"""
Appends every order Paula places to the original backend's trade_log.json, so
the history stays in one place whichever app placed the trade.
"""
import json
import os
import pathlib
import threading
from datetime import datetime

from ..bridge import auth

# Same file the original backend writes (it lives beside server.py there).
TRADE_LOG_PATH = pathlib.Path(os.path.dirname(os.path.abspath(auth.__file__))) / "trade_log.json"
_lock = threading.Lock()


def log_trade(action: str, ticker: str, qty=0, price=0.0, pnl=0.0, extra: dict | None = None) -> None:
    try:
        with _lock:
            trades = json.loads(TRADE_LOG_PATH.read_text()) if TRADE_LOG_PATH.exists() else []
            trades.append({
                "time": datetime.now().isoformat(),
                "action": action,
                "ticker": ticker,
                "qty": qty,
                "price": price,
                "pnl": pnl,
                **(extra or {}),
            })
            TRADE_LOG_PATH.write_text(json.dumps(trades[-500:], indent=2))
    except Exception as e:  # logging must never break trading
        print(f"[trade_log] write failed: {e!r}", flush=True)
