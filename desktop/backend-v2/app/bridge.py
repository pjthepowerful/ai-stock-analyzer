"""
Bridge into the EXISTING backend package (desktop/backend) so v2 reuses the
real `engine`, `auth`, `trading` (via engine's own sys.path bootstrap) modules
byte-for-byte. We do not re-derive any trading/signal logic here — this file
only wires up imports and .env loading so the same code paths run under the
new API layer.
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))                      # backend-v2/app
_BACKEND_V2 = os.path.dirname(_HERE)                                     # backend-v2
_DESKTOP = os.path.dirname(_BACKEND_V2)                                  # desktop
_OLD_BACKEND = os.path.join(_DESKTOP, "backend")                         # desktop/backend

if _OLD_BACKEND not in sys.path:
    # engine.py / auth.py live here. engine.py itself extends sys.path to reach
    # the repo-root trading.py, and auth.py resolves paula.db relative to its
    # own __file__ — so importing it from here still shares the same database
    # and the same tuned strategy code, with zero duplication.
    sys.path.insert(0, _OLD_BACKEND)

# Load the same .env the old backend uses (real Alpaca/Groq/Polygon keys),
# checking backend-v2's own .env first in case someone wants to override.
try:
    from dotenv import load_dotenv
    for _env_path in (
        os.path.join(_BACKEND_V2, ".env"),
        os.path.join(_OLD_BACKEND, ".env"),
    ):
        if os.path.exists(_env_path):
            load_dotenv(_env_path)
            print(f"[bridge] loaded {_env_path}", flush=True)
            break
except Exception as e:
    print(f"[bridge] dotenv not loaded: {e}", flush=True)

import engine   # noqa: E402  (must come after sys.path/env setup above)
import auth     # noqa: E402

__all__ = ["engine", "auth"]


def read_strategy_mode() -> str:
    """The autopilot's STRATEGY_MODE, read without side effects.

    engine.load_autopilot_config() re-writes autopilot_config.json on every
    call. Both apps call it, so a read racing a write can see a truncated
    file, fall back to defaults and quietly report (or persist) 'core'. The
    GET endpoints here only need the mode, so they read the file directly.
    """
    import json

    try:
        with open(engine.autopilot_cfg_path()) as f:
            return (json.load(f).get("STRATEGY_MODE") or "core").lower()
    except Exception:
        return "core"
