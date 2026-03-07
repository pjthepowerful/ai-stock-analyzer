"""
Paula Engine — Streamlit-free trading engine wrapper.

This module strips all Streamlit dependencies from trading.py and
exposes the core functions for use by the FastAPI backend.
"""

import os
import sys

# ── Mock st.secrets and st.session_state so the engine doesn't crash ──

class _MockSecrets(dict):
    def get(self, key, default=None):
        return os.environ.get(key, default)

class _MockSessionState(dict):
    def get(self, key, default=None):
        return super().get(key, default)

class _MockStreamlit:
    """Minimal mock of streamlit module."""
    secrets = _MockSecrets()
    session_state = _MockSessionState()

    @staticmethod
    def cache_data(ttl=None, **kwargs):
        def decorator(func):
            return func
        return decorator

    @staticmethod
    def set_page_config(**kwargs): pass
    @staticmethod
    def markdown(*args, **kwargs): pass
    @staticmethod
    def caption(*args, **kwargs): pass
    @staticmethod
    def chat_input(*args, **kwargs): return None
    @staticmethod
    def chat_message(*args, **kwargs):
        class _ctx:
            def __enter__(self): return self
            def __exit__(self, *a): pass
        return _ctx()
    @staticmethod
    def spinner(*args, **kwargs):
        class _ctx:
            def __enter__(self): return self
            def __exit__(self, *a): pass
        return _ctx()
    @staticmethod
    def plotly_chart(*args, **kwargs): pass
    @staticmethod
    def dataframe(*args, **kwargs): pass
    @staticmethod
    def rerun(): pass
    @staticmethod
    def columns(*args, **kwargs): return [type('col', (), {'metric': lambda *a, **k: None})()]
    @staticmethod
    def metric(*args, **kwargs): pass

# Install the mock before importing trading
sys.modules['streamlit'] = _MockStreamlit()

# Now import the actual trading engine
# It will use our mock streamlit, so no crashes
from trading import (
    # Core data
    fetch_price,
    fetch_full,
    fetch_scan,
    fetch_scan_intraday,
    compute_technicals,
    compute_intraday_technicals,

    # Signal engines
    generate_trade_signal,
    generate_intraday_signal,

    # Alpaca trading
    alpaca_account,
    alpaca_positions,
    alpaca_orders,
    alpaca_buy,
    alpaca_sell,
    alpaca_short,
    alpaca_cover,
    alpaca_close_all,
    alpaca_portfolio_history,

    # Autopilot
    run_autopilot,

    # Market
    check_market_regime,
    _market_is_open,
    _get_spy_intraday_trend,
    _get_sector_strength,

    # News
    _news_sentiment,

    # Router & AI
    route,
    execute,
    ai_response,

    # Charts
    build_chart,
    build_portfolio_chart,
)

print("✅ Paula engine loaded (Streamlit-free)")
