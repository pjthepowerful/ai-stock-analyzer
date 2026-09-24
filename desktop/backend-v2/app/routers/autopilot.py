"""
Autopilot: start/stop the autonomous trading loop (services/autopilot_runner),
switch strategy, and the "why no trades" diagnostic. Everything that changes
anything is limited to the same allowlisted accounts as the original backend.
"""
import os

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from ..bridge import engine, read_strategy_mode
from ..deps import current_user_optional, current_user_required
from ..services import autopilot_runner as runner
from ..ws import manager

router = APIRouter(prefix="/api/autopilot", tags=["autopilot"])

AUTOPILOT_EMAILS = {"parjan.d@icloud.com", "pinakin.d@moftmail.com"}


def can_autopilot(user: dict | None) -> bool:
    return bool(user) and user.get("email", "").lower() in AUTOPILOT_EMAILS


def _require_autopilot(authorization: str | None) -> dict:
    user = current_user_required(authorization)
    if not can_autopilot(user):
        raise HTTPException(403, "Autopilot is limited to authorized accounts")
    return user


def _mode() -> str:
    try:
        return read_strategy_mode()
    except Exception:
        return "core"


@router.get("/status")
def status(authorization: str = Header(None)):
    out = {"ok": True, "running": runner.is_running(), "mode": _mode()}
    # Tickers and cycle logs are the owner's trading activity — only the
    # accounts allowed to run autopilot see them.
    if can_autopilot(current_user_optional(authorization)):
        st = runner.status()
        out.update(started_at=st["started_at"], recent=st["recent"])
    return out


@router.post("/start")
async def start(authorization: str = Header(None)):
    user = _require_autopilot(authorization)
    try:
        started = await runner.start(user)
    except runner.AutopilotConflict as e:
        raise HTTPException(409, str(e))
    return {"ok": True, "running": True, "message": "Autopilot started" if started else "Autopilot already running"}


@router.post("/stop")
async def stop(authorization: str = Header(None)):
    _require_autopilot(authorization)
    await runner.stop()
    return {"ok": True, "running": False, "message": "Autopilot stopped"}


class ModeRequest(BaseModel):
    mode: str


@router.post("/mode")
async def set_mode(req: ModeRequest, authorization: str = Header(None)):
    """Refused while running: the modes manage positions differently, and
    handing an open book to the other mode's exit logic can leave a position
    with no owner and no stop. Stop, switch, restart."""
    _require_autopilot(authorization)
    mode = req.mode.lower().strip()
    valid = getattr(engine, "STRATEGY_MODES", ["core"])
    if mode not in valid:
        raise HTTPException(400, f"Unknown mode {mode!r}. Valid: {', '.join(valid)}")
    if runner.is_running():
        raise HTTPException(409, "Stop autopilot before switching strategy — open positions are managed by the mode that opened them.")
    try:
        engine.save_autopilot_config({"STRATEGY_MODE": mode})
    except Exception as e:
        raise HTTPException(500, f"Could not save mode: {str(e)[:120]}")
    if _mode() != mode:
        raise HTTPException(500, "Mode did not persist")
    await manager.broadcast("autopilot", {"kind": "mode_changed", "running": False})
    return {"ok": True, "mode": mode}


@router.get("/modes")
def modes():
    current = "core"
    try:
        current = read_strategy_mode()
    except Exception:
        pass
    mode_list = []
    try:
        mode_list = engine.smallcap_mode_summary()
    except Exception:
        pass
    return {"ok": True, "current": current, "modes": mode_list}


@router.get("/diagnostics")
def diagnostics(authorization: str = Header(None)):
    """Answer 'why did it place no trades?' — a read-only scan of the active
    mode, no orders, no state writes. Ported faithfully from server.py."""
    user = current_user_required(authorization)
    if not can_autopilot(user):
        raise HTTPException(403, "Restricted")

    mode = "core"
    try:
        mode = read_strategy_mode()
    except Exception:
        pass

    out = {
        "ok": True,
        "mode": mode,
        "keys": {
            "polygon": bool(os.environ.get("POLYGON_API_KEY")),
            "groq": bool(os.environ.get("GROQ_API_KEY")),
            "alpaca": bool(os.environ.get("ALPACA_KEY_ID")),
        },
    }

    if not out["keys"]["polygon"]:
        out["verdict"] = "POLYGON_API_KEY is not set on the backend. The scan cannot see the market at all — this alone explains zero trades."
        return out

    if mode == "core":
        out["verdict"] = "Core mode — this diagnostic covers the small-cap modes only."
        return out

    import smallcap_pullback

    # A plain `def` route — FastAPI runs it in its own worker thread
    # automatically, so this blocking call doesn't stall the event loop.
    res = smallcap_pullback.run(mode, candidates_only=True, skip_market_check=True) or {}
    out["feed"] = res.get("feed") or smallcap_pullback.feed_diagnostics()
    try:
        out["active_feed"] = smallcap_pullback.active_feed()
    except Exception:
        out["active_feed"] = {}
    out["funnel"] = res.get("funnel", {})
    out["candidates"] = len(res.get("candidates") or [])
    out["log"] = res.get("log", [])

    pool = out["funnel"].get("pool", 0)
    src = (out.get("active_feed") or {}).get("source")
    if pool == 0 and src == "alpaca":
        out["verdict"] = "Polygon's plan doesn't cover the snapshot endpoints, so the scan is on Alpaca's screener instead. Pool was still empty — check the log for the Alpaca response."
    elif pool == 0:
        out["verdict"] = out["feed"].get("verdict", "Empty pool — see feed status.")
    elif out["candidates"] == 0:
        biggest = max(
            ((k, v) for k, v in out["funnel"].items() if k not in ("pool", "cleared_universe")),
            key=lambda kv: kv[1],
            default=(None, 0),
        )
        out["verdict"] = f"Feed is fine ({pool} names in the pool). Nothing qualified — most dropped at: {biggest[0]} ({biggest[1]})."
    else:
        out["verdict"] = f"{out['candidates']} candidate(s) right now. Entries also require the time window, an open slot, and the daily/PDT limits to allow it."
    return out
