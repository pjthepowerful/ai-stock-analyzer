"""
The engine occasionally produces NaN/Infinity floats (insufficient history for
an indicator, a division edge case) buried in nested dicts. Python's default
json encoder raises on those instead of emitting `null`, so any endpoint that
returns raw engine data can 500 on an otherwise-successful computation. This
sanitizes recursively before a response leaves the process — no new
dependency, no change to engine.py itself.
"""
import math
from typing import Any

from fastapi.responses import JSONResponse


def sanitize(obj: Any) -> Any:
    if isinstance(obj, float):
        return None if (math.isnan(obj) or math.isinf(obj)) else obj
    if isinstance(obj, dict):
        return {k: sanitize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [sanitize(v) for v in obj]
    return obj


class SafeJSONResponse(JSONResponse):
    """Drop-in JSONResponse that can't 500 on a stray NaN/Infinity anywhere
    in the payload. Set as the app's default_response_class so every route
    gets this for free, instead of relying on each handler to remember it."""

    def render(self, content: Any) -> bytes:
        return super().render(sanitize(content))
