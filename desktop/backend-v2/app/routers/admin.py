"""
Owner-only admin panel: users, Plus grants, bug reports, maintenance mode.
Ported from the original server.py, reading and writing the SAME database and
the SAME bug_reports.json / maintenance.json files, so both apps agree.

Deliberately NOT ported: /api/admin/clear-all (delete every user but the
admin in one click). That's too destructive to sit behind a button in a
preview build; do it from a shell if it's ever really needed.

Also public here (no auth): POST /api/report-bug and GET /api/maintenance,
since they live next to the admin views that consume them.
"""
import asyncio
import json
import os
import uuid
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from ..bridge import auth
from ..deps import admin_required, current_user_optional, is_admin
from ..ws import manager

router = APIRouter(tags=["admin"])

# Same files the original backend uses (resolved relative to desktop/backend,
# honouring DB_DIR the same way server.py does).
_OLD_BACKEND = os.path.dirname(os.path.abspath(auth.__file__))
_DATA_DIR = os.environ.get("DB_DIR", _OLD_BACKEND)
_BUG_REPORTS_FILE = os.path.join(_DATA_DIR, "bug_reports.json")
_MAINT_FILE = os.path.join(_DATA_DIR, "maintenance.json")

_MAX_REPORTS = 500


def _load_reports() -> list:
    try:
        with open(_BUG_REPORTS_FILE) as f:
            return json.load(f)
    except Exception:
        return []


def _save_reports(reports: list) -> None:
    with open(_BUG_REPORTS_FILE, "w") as f:
        json.dump(reports, f, indent=2, default=str)


def _maint_state() -> dict:
    try:
        with open(_MAINT_FILE) as f:
            return json.load(f)
    except Exception:
        return {"on": False, "message": ""}


# What still answers during maintenance: the status itself, and what the
# owner needs to sign in and turn it back off. Everything else is refused
# server-side, so skipping the screen in the browser gets you nothing.
_OPEN_IN_MAINTENANCE = (
    "/api/maintenance",
    "/api/health",
    "/api/launch",
    "/api/auth/login",
    "/api/auth/verify-code",
    "/api/auth/resend-code",
    "/api/auth/me",
)
_maint_cache: tuple[float, dict] = (0.0, {})


def maintenance_blocked(request) -> bool:
    """True when this request should get the 'down for maintenance' answer."""
    global _maint_cache
    if request.method == "OPTIONS":
        return False
    path = request.url.path
    if not path.startswith("/api/") or path.startswith(_OPEN_IN_MAINTENANCE):
        return False
    import time as _time

    # Read the file at most once a second, not on every request.
    at, state = _maint_cache
    if _time.time() - at > 1:
        state = _maint_state()
        _maint_cache = (_time.time(), state)
    if not state.get("on"):
        return False
    return not is_admin(current_user_optional(request.headers.get("authorization")))


# ── Public ──────────────────────────────────────────────────────────────────

class BugReportRequest(BaseModel):
    note: str = ""
    chat_title: str = ""
    messages: list = []
    version: str = ""
    user_agent: str = ""
    url: str = ""


@router.post("/api/report-bug")
def report_bug(req: BugReportRequest, authorization: Optional[str] = Header(None)):
    user = current_user_optional(authorization)
    if not req.note.strip() and not req.messages:
        raise HTTPException(422, "Describe the problem or attach a chat")
    report = {
        "id": uuid.uuid4().hex[:12],
        "at": datetime.now(ZoneInfo("US/Eastern")).isoformat(),
        "user_email": (user.get("email") if user else None) or "anonymous",
        "user_id": user.get("id") if user else None,
        "note": req.note[:2000],
        "chat_title": req.chat_title[:200],
        "messages": req.messages[-200:],
        "app_version": req.version[:40],
        "user_agent": req.user_agent[:400],
        "url": req.url[:400],
    }
    reports = _load_reports()
    reports.append(report)
    _save_reports(reports[-_MAX_REPORTS:])
    return {"ok": True, "id": report["id"]}


@router.get("/api/maintenance")
def maintenance_status():
    return {"ok": True, **_maint_state()}


# ── Admin ───────────────────────────────────────────────────────────────────

@router.get("/api/admin/stats")
def stats(authorization: Optional[str] = Header(None)):
    admin_required(authorization)
    db = auth._get_db()
    try:
        total_users = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        plus_users = db.execute("SELECT COUNT(*) FROM users WHERE plus = 1").fetchone()[0]
        total_messages = db.execute("SELECT COUNT(*) FROM chat_history").fetchone()[0]
        active_7d = db.execute(
            "SELECT COUNT(*) FROM users WHERE last_login >= datetime('now', '-7 days')"
        ).fetchone()[0]
    finally:
        db.close()
    return {
        "ok": True,
        "total_users": total_users,
        "plus_users": plus_users,
        "active_7d": active_7d,
        "total_messages": total_messages,
        "open_reports": len(_load_reports()),
        "maintenance": _maint_state(),
    }


@router.get("/api/admin/users")
def list_users(authorization: Optional[str] = Header(None)):
    admin_required(authorization)
    db = auth._get_db()
    try:
        rows = db.execute(
            """SELECT u.id, u.username, u.email, u.created_at, u.last_login, u.plus,
                      (SELECT COUNT(*) FROM chat_history h WHERE h.user_id = u.id) AS messages
               FROM users u ORDER BY u.id DESC"""
        ).fetchall()
    finally:
        db.close()
    users = [
        {
            "id": r["id"],
            "username": r["username"],
            "email": r["email"],
            "created_at": r["created_at"],
            "last_login": r["last_login"],
            "plus": bool(r["plus"]),
            "messages": r["messages"],
        }
        for r in rows
    ]
    return {"ok": True, "users": users, "total": len(users)}


class SetPlusRequest(BaseModel):
    user_id: int
    on: bool = True
    message: str = ""


@router.post("/api/admin/set-plus")
async def set_plus(req: SetPlusRequest, authorization: Optional[str] = Header(None)):
    admin_required(authorization)
    db = auth._get_db()
    try:
        exists = db.execute("SELECT 1 FROM users WHERE id = ?", (req.user_id,)).fetchone()
    finally:
        db.close()
    if not exists:
        raise HTTPException(404, "No such user")
    auth.set_plus(req.user_id, req.on, gift_msg=req.message.strip()[:300] if req.on else "")
    # Only the id goes over the shared socket; that person's app refetches
    # its own account (and the gift note) through the signed-in /me.
    try:
        await manager.broadcast("plus_changed", {"user_id": req.user_id})
    except Exception:
        pass
    return {"ok": True, "user_id": req.user_id, "plus": req.on}


@router.delete("/api/admin/users/{user_id}")
def delete_user(user_id: int, authorization: Optional[str] = Header(None)):
    admin = admin_required(authorization)
    if user_id == admin["id"]:
        raise HTTPException(400, "You can't delete your own account from here")
    db = auth._get_db()
    try:
        if not db.execute("SELECT 1 FROM users WHERE id = ?", (user_id,)).fetchone():
            raise HTTPException(404, "No such user")
        db.execute("DELETE FROM chat_history WHERE user_id = ?", (user_id,))
        db.execute("DELETE FROM user_settings WHERE user_id = ?", (user_id,))
        # The original leaves synced chats behind; don't keep a deleted
        # person's conversations.
        db.execute("DELETE FROM synced_chats WHERE user_id = ?", (user_id,))
        db.execute("DELETE FROM users WHERE id = ?", (user_id,))
        db.commit()
    finally:
        db.close()
    return {"ok": True}


@router.get("/api/admin/bug-reports")
def list_reports(authorization: Optional[str] = Header(None)):
    admin_required(authorization)
    reports = list(reversed(_load_reports()))
    summaries = [
        {
            "id": r.get("id"),
            "at": r.get("at"),
            "user_email": r.get("user_email"),
            "note": r.get("note", ""),
            "chat_title": r.get("chat_title", ""),
            "app_version": r.get("app_version", ""),
            "msg_count": len(r.get("messages") or []),
        }
        for r in reports
    ]
    return {"ok": True, "count": len(summaries), "reports": summaries}


@router.get("/api/admin/bug-reports/{report_id}")
def get_report(report_id: str, authorization: Optional[str] = Header(None)):
    admin_required(authorization)
    for r in _load_reports():
        if r.get("id") == report_id:
            return {"ok": True, "report": r}
    raise HTTPException(404, "Report not found")


@router.delete("/api/admin/bug-reports/{report_id}")
def delete_report(report_id: str, authorization: Optional[str] = Header(None)):
    admin_required(authorization)
    reports = _load_reports()
    remaining = [r for r in reports if r.get("id") != report_id]
    if len(remaining) == len(reports):
        raise HTTPException(404, "Report not found")
    _save_reports(remaining)
    return {"ok": True, "remaining": len(remaining)}


class MaintenanceRequest(BaseModel):
    on: bool
    message: str = ""
    eta_minutes: Optional[int] = None  # shown as a countdown on the maintenance screen


@router.post("/api/admin/maintenance")
async def set_maintenance(req: MaintenanceRequest, authorization: Optional[str] = Header(None)):
    admin_required(authorization)
    global _maint_cache
    eta = None
    if req.on and req.eta_minutes and 0 < req.eta_minutes <= 7 * 24 * 60:
        import time as _time

        eta = _time.time() + req.eta_minutes * 60
    state = {"on": req.on, "message": req.message.strip()[:300], "eta": eta}
    _maint_cache = (0.0, {})

    def _write():
        with open(_MAINT_FILE, "w") as f:
            json.dump(state, f)

    await asyncio.to_thread(_write)
    # Flip every open client immediately instead of waiting for a poll.
    await manager.broadcast("maintenance", state)
    return {"ok": True, **state}
