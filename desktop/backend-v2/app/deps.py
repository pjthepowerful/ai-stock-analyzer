"""
Auth dependency for routers. Unlike the original backend (which returns
{"ok": false} with HTTP 200 for auth failures), routes that require a user
raise a real 401 — the point of this rewrite's API layer is honest status
codes. `current_user_optional` is for routes (like chat) that behave
differently for guests vs. logged-in users but don't hard-require auth.
"""
from typing import Optional

from fastapi import Header, HTTPException

from .bridge import auth, engine


def _resolve_user(authorization: Optional[str]) -> Optional[dict]:
    if not authorization:
        return None
    token = authorization.replace("Bearer ", "").strip()
    if not token:
        return None
    user = auth.get_user(token)
    if not user:
        return None
    # Fetch a fresh email (older JWTs may lack it) and apply this user's own
    # Alpaca creds for the request, exactly like the original backend does.
    try:
        db = auth._get_db()
        row = db.execute("SELECT email FROM users WHERE id = ?", (user["id"],)).fetchone()
        if row and row["email"]:
            user["email"] = row["email"]
        db.close()
    except Exception:
        pass
    try:
        creds = auth.get_user_alpaca_creds(user["id"])
        engine.set_alpaca_creds(creds.get("key_id"), creds.get("secret"))
    except Exception:
        engine.set_alpaca_creds(None, None)
    return user


def current_user_optional(authorization: Optional[str] = Header(None)) -> Optional[dict]:
    return _resolve_user(authorization)


def current_user_required(authorization: Optional[str] = Header(None)) -> dict:
    user = _resolve_user(authorization)
    if not user:
        raise HTTPException(status_code=401, detail="Sign in required")
    return user


# Owner account — the only one that gets the admin panel. Same value the
# original backend hard-codes as ADMIN_EMAIL.
ADMIN_EMAIL = "parjan.d@icloud.com"


def is_admin(user: Optional[dict]) -> bool:
    return bool(user) and (user.get("email") or "").lower() == ADMIN_EMAIL


def admin_required(authorization: Optional[str] = Header(None)) -> dict:
    user = current_user_required(authorization)
    if not is_admin(user):
        raise HTTPException(status_code=403, detail="Admin only")
    return user


def in_request_context(fn, *args, **kwargs):
    """Bind fn to a copy of the current context for run_in_executor.

    Per-user Alpaca creds live in a contextvar (engine.set_alpaca_creds), and
    executor threads don't inherit contextvars — without this, account and
    position lookups made inside an executor silently hit the shared account
    instead of the signed-in user's own."""
    import contextvars
    import functools

    return functools.partial(contextvars.copy_context().run, fn, *args, **kwargs)
