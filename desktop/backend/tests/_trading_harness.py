"""Import trading.py for testing without its heavy runtime dependencies.

trading.py imports streamlit / yfinance / plotly / groq / dotenv at module
load. None of those are needed to test the pure-Python router (`route`), so we
install lightweight stand-ins (mirroring what engine.py does for streamlit)
before importing. Import `trading` from this module in tests.
"""
import os
import sys
import types

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


def _install_mocks():
    class _CacheDecorator:
        """Mimics st.cache_data / st.cache_resource used as @decorator or @decorator(ttl=...)."""
        def __call__(self, *args, **kwargs):
            if args and callable(args[0]):
                return args[0]
            def deco(fn):
                return fn
            return deco

    for name in ("streamlit", "yfinance", "plotly", "plotly.graph_objects",
                 "plotly.subplots", "groq", "dotenv"):
        if name not in sys.modules:
            sys.modules[name] = types.ModuleType(name)

    sys.modules["dotenv"].load_dotenv = lambda *a, **k: None
    sys.modules["groq"].Groq = object

    st = sys.modules["streamlit"]
    st.cache_data = _CacheDecorator()
    st.cache_resource = _CacheDecorator()

    go = sys.modules["plotly.graph_objects"]
    for attr in ("Figure", "Candlestick", "Scatter", "Bar"):
        setattr(go, attr, object)
    sys.modules["plotly.subplots"].make_subplots = lambda *a, **k: None
    sys.modules["plotly"].graph_objects = go


_install_mocks()

import trading  # noqa: E402,F401  (re-exported for tests)
