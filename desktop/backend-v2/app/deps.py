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


# Accounts that may use the shared (env) Alpaca account: autopilot, orders
# without their own keys. Everyone else only ever sees their own broker.
AUTOPILOT_EMAILS = {"parjan.d@icloud.com", "pinakin.d@moftmail.com"}

# engine falls back to the shared env account whenever no per-request creds
# are set. Anyone not allowed that account gets these placeholder creds
# instead, so every account/position/order call fails like "not connected"
# rather than quietly showing (or trading) the owner's account. Market data
# never goes through these headers, so it's unaffected.
_NO_BROKER = "not-connected"


def can_autopilot(user: Optional[dict]) -> bool:
    return bool(user) and (user.get("email") or "").lower() in AUTOPILOT_EMAILS


def _own_creds(user_id: int) -> dict:
    try:
        c = auth.get_user_alpaca_creds(user_id) or {}
    except Exception:
        return {}
    return c if c.get("key_id") and c.get("secret") else {}


def has_broker(user: Optional[dict]) -> bool:
    """Signed in with their own Alpaca keys, or allowed the shared account."""
    return bool(user) and (can_autopilot(user) or bool(_own_creds(user["id"])))


def _resolve_user(authorization: Optional[str]) -> Optional[dict]:
    engine.set_alpaca_creds(_NO_BROKER, _NO_BROKER)
    if not authorization:
        return None
    token = authorization.replace("Bearer ", "").strip()
    if not token:
        return None
    user = auth.get_user(token)
    if not user:
        return None
    # Fetch a fresh email (older JWTs may lack it) and apply this user's own
    # Alpaca creds for the request.
    try:
        db = auth._get_db()
        try:
            row = db.execute("SELECT email FROM users WHERE id = ?", (user["id"],)).fetchone()
        finally:
            db.close()
        if row and row["email"]:
            user["email"] = row["email"]
    except Exception:
        pass
    creds = _own_creds(user["id"])
    if creds:
        engine.set_alpaca_creds(creds["key_id"], creds["secret"])
    elif can_autopilot(user):
        engine.set_alpaca_creds(None, None)   # the shared account is theirs
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


def broker_user_required(authorization: Optional[str] = Header(None)) -> dict:
    user = current_user_required(authorization)
    if not has_broker(user):
        raise HTTPException(status_code=403, detail="Connect your Alpaca account in Settings to see your portfolio.")
    return user


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
