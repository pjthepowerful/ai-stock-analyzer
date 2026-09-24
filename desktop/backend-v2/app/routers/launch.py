"""
Launch countdown. Until `launch_at`, the site shows a coming-soon page and the
API refuses everything except what that page and the owner's sign-in need
(see `prelaunch_blocked`). At `launch_at` it opens by itself — nothing has to
be deployed at that moment.

Changing the time needs the owner's admin login AND the launch phrase. The
phrase lives only in the LAUNCH_PHRASE env var (never in this public repo);
if it isn't set, the time can't be changed from the site at all.
"""
import hmac
import json
import os
import threading
import time
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel

from ..bridge import auth
from ..deps import admin_required, current_user_optional, is_admin
from ..ws import manager

router = APIRouter(prefix="/api/launch", tags=["launch"])

_DATA_DIR = os.environ.get("DB_DIR", os.path.dirname(os.path.abspath(auth.__file__)))
_FILE = os.path.join(_DATA_DIR, "launch.json")
_lock = threading.Lock()


def _initial() -> float:
    """First boot: LAUNCH_AT (ISO 8601 with offset) or no gate at all."""
    raw = os.environ.get("LAUNCH_AT", "").strip()
    if not raw:
        return 0.0
    try:
        return datetime.fromisoformat(raw).timestamp()
    except ValueError:
        print(f"[launch] LAUNCH_AT not ISO 8601: {raw!r} — no countdown", flush=True)
        return 0.0


def launch_at() -> float:
    try:
        with open(_FILE) as f:
            return float(json.load(f).get("launch_at", 0))
    except FileNotFoundError:
        at = _initial()
        _save(at)
        return at
    except Exception:
        return 0.0


def _save(at: float) -> None:
    with _lock:
        with open(_FILE, "w") as f:
            json.dump({"launch_at": at, "updated": time.time()}, f)


def is_live() -> bool:
    at = launch_at()
    return not at or time.time() >= at


# What the coming-soon page and the owner's sign-in need before launch.
_OPEN_BEFORE_LAUNCH = (
    "/api/launch",
    "/api/health",
    "/api/auth/login",
    "/api/auth/verify-code",
    "/api/auth/resend-code",
    "/api/auth/me",
)


def prelaunch_blocked(request: Request) -> bool:
    """True when this request should get the 'not launched yet' answer."""
    if is_live() or request.method == "OPTIONS":
        return False
    path = request.url.path
    if not path.startswith("/api/") or path.startswith(_OPEN_BEFORE_LAUNCH):
        return False
    # The owner can use the whole app before launch (to check it).
    return not is_admin(current_user_optional(request.headers.get("authorization")))


@router.get("")
def status():
    at = launch_at()
    return {"ok": True, "launch_at": at or None, "now": time.time(), "live": is_live()}


# A few wrong phrases per IP, then a pause — the phrase is short.
_attempts: dict[str, list[float]] = {}


def _check_phrase(phrase: str, request: Request) -> None:
    secret = os.environ.get("LAUNCH_PHRASE", "")
    if not secret:
        raise HTTPException(503, "The launch phrase isn't set on the server.")
    ip = request.client.host if request.client else "?"
    recent = [t for t in _attempts.get(ip, []) if time.time() - t < 600]
    if len(recent) >= 8:
        raise HTTPException(429, "Too many tries — wait a few minutes.")
    if not hmac.compare_digest(phrase.strip().lower().encode(), secret.strip().lower().encode()):
        _attempts[ip] = recent + [time.time()]
        raise HTTPException(403, "That's not the phrase.")
    _attempts.pop(ip, None)


class UnlockRequest(BaseModel):
    phrase: str


@router.post("/unlock")
def unlock(req: UnlockRequest, request: Request, authorization: Optional[str] = Header(None)):
    admin_required(authorization)
    _check_phrase(req.phrase, request)
    return {"ok": True}


class SetRequest(BaseModel):
    phrase: str
    launch_at: float   # unix seconds; 0 or in the past = launch now


@router.post("/set")
async def set_time(req: SetRequest, request: Request, authorization: Optional[str] = Header(None)):
    admin_required(authorization)
    _check_phrase(req.phrase, request)
    at = max(0.0, req.launch_at)
    if at and at < time.time():
        at = time.time()
    _save(at)
    live = is_live()
    try:
        await manager.broadcast("launch", {"launch_at": at or None, "live": live})
    except Exception:
        pass
    print(f"[launch] launch time set to {at} (live={live})", flush=True)
    return {"ok": True, "launch_at": at or None, "live": live}
