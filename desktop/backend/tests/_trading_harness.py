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

    class _AnyAttrModule(types.ModuleType):
        """Stub module that yields a harmless object for ANY attribute access.

        Needed because trading.py references e.g. `pd.Series` in type
        annotations at import time; a bare ModuleType would raise AttributeError.
        """
        def __getattr__(self, name):
            return object

    # Libraries trading.py imports at module load but that route() never uses.
    # If a real one is installed (e.g. inside the venv), keep it; only stub the
    # ones that are actually missing so the router stays testable anywhere.
    optional = ("streamlit", "yfinance", "pandas", "numpy", "plotly",
                "plotly.graph_objects", "plotly.subplots", "groq", "dotenv",
                "requests")
    for name in optional:
        if name in sys.modules:
            continue
        try:
            __import__(name)
        except Exception:
            sys.modules[name] = _AnyAttrModule(name)

    # Fill in the specific attributes trading.py references at import time.
    # Only patch modules WE stubbed (real installed libs already have these and
    # must not be clobbered). _AnyAttrModule answers hasattr() for everything,
    # so we detect our stubs by type rather than by hasattr().
    def _is_stub(mod):
        return isinstance(mod, _AnyAttrModule)

    dotenv = sys.modules["dotenv"]
    if _is_stub(dotenv):
        dotenv.load_dotenv = lambda *a, **k: None

    groq = sys.modules["groq"]
    if _is_stub(groq):
        groq.Groq = object

    st = sys.modules["streamlit"]
    if _is_stub(st):
        st.cache_data = _CacheDecorator()
        st.cache_resource = _CacheDecorator()

    go = sys.modules["plotly.graph_objects"]
    if _is_stub(go):
        for attr in ("Figure", "Candlestick", "Scatter", "Bar"):
            setattr(go, attr, object)
    subplots = sys.modules["plotly.subplots"]
    if _is_stub(subplots):
        subplots.make_subplots = lambda *a, **k: None
    plotly = sys.modules["plotly"]
    if _is_stub(plotly):
        plotly.graph_objects = go


_install_mocks()

import trading  # noqa: E402,F401  (re-exported for tests)
