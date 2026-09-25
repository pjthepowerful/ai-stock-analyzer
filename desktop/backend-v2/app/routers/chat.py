"""
Chat router — the core loop. Routes a message through the SAME engine.route()/
engine.execute() the original backend uses (unchanged signal/strategy logic),
then hands the result to chat_orchestrator.build_response() — a faithful port
of the original's per-intent-type reply construction (Plus-gating, live news,
web search, price-hallucination guard) — before returning a typed response.

Market scans ("what should I buy?") can take long enough to trip a gateway
timeout, so — exactly like the original — we kick them off in the background
and deliver the result over the WebSocket as a `scan_result` event, returning
an immediate `scan_started` ack from the HTTP call itself.
"""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from fastapi import APIRouter, Header, Request

from ..bridge import auth, engine
from ..deps import current_user_optional, in_request_context, is_admin
from ..models.chat import ChatRequest
from ..services import chat_orchestrator as orch
from ..services import popularity
from ..ws import manager

router = APIRouter(prefix="/api/chat", tags=["chat"])

_scan_executor = ThreadPoolExecutor(max_workers=2)
_light_executor = ThreadPoolExecutor(max_workers=4)
_active_scans: dict[int, asyncio.Task] = {}

def _is_plus_or_exempt(user: Optional[dict]) -> bool:
    if not user:
        return False
    return bool(auth.is_plus(user["id"]) or is_admin(user))


def _make_progress_cb(loop: asyncio.AbstractEventLoop, scan_id: str):
    def _cb(phase: str, pct: float, label: str = ""):
        asyncio.run_coroutine_threadsafe(
            manager.broadcast("scan_progress", {"scan_id": scan_id, "phase": phase, "pct": pct, "label": label}), loop,
        )
    return _cb


FREE_DAILY_MESSAGES = 3

# Guests have no account to count against, so count by client IP for the
# day. The original only counted guests in the browser (clear storage, get
# more); this is the server-side version of the same "3 a day" rule.
_guest_counts: dict[str, tuple[str, int]] = {}


def _client_ip(request: Request) -> str:
    # X-Forwarded-For is client-controlled unless a proxy we run sets it, so
    # only honour it when deployed behind one (TRUST_PROXY=1); otherwise a
    # guest could dodge the limit by sending a fake header.
    import os

    if os.environ.get("TRUST_PROXY") == "1":
        fwd = request.headers.get("x-forwarded-for")
        if fwd:
            return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _guest_over_limit(ip: str) -> bool:
    from datetime import date

    today = date.today().isoformat()
    day, n = _guest_counts.get(ip, (today, 0))
    if day != today:
        n = 0
    if n >= FREE_DAILY_MESSAGES:
        return True
    _guest_counts[ip] = (today, n + 1)
    return False


@router.post("")
async def chat(req: ChatRequest, request: Request, authorization: str = Header(None)):
    user_msg = req.message.strip()
    if not user_msg and req.image:
        user_msg = "What do you see in this image?"
    if not user_msg:
        return {"ok": False, "error": "Empty message"}

    user = current_user_optional(authorization)
    user_id = user["id"] if user else 0
    is_plus = _is_plus_or_exempt(user)

    if user and not is_plus and auth.messages_today(user["id"]) >= FREE_DAILY_MESSAGES:
        return {
            "ok": True, "type": "limit", "limit_reached": True,
            "message": "You've used your 3 free messages for today. Upgrade to Paula Plus for unlimited messages.",
        }
    if not user and _guest_over_limit(_client_ip(request)):
        return {
            "ok": True, "type": "limit", "limit_reached": True,
            "message": "That's the 3 free guest messages for today. Create a free account to keep going.",
        }

    # Contextvars reach the executor threads via in_request_context, so the
    # engine's LLM calls see the picked tier and report back what answered.
    engine.LLM_TIER.set("fast" if req.model == "fast" else "smart")
    used: dict = {}
    engine.LLM_USED.set(used)

    if user:
        auth.save_chat(user_id, "user", user_msg)

    if req.history is not None:
        chat_history = [{"role": m.role, "content": m.content} for m in req.history][-12:]
    elif user:
        chat_history = orch.get_user_history(user_id)
    else:
        # Never fall back to a server-side history for guests: they all share
        # user_id 0, so one guest's conversation would leak into another's.
        chat_history = []
    chat_history.append({"role": "user", "content": user_msg})

    if req.image:
        return await _image_reply(req.image, user_msg, chat_history, user_id, used)

    # route() can call the LLM to classify a message; keep that off the event
    # loop so one slow classification doesn't stall every other request.
    loop = asyncio.get_running_loop()
    intent = await loop.run_in_executor(
        _light_executor, in_request_context(engine.route, user_msg, history=chat_history[:-1])
    )
    used.clear()  # classifying isn't answering; only credit the model that writes the reply

    if intent.get("type") in ("autopilot", "stop_autopilot"):
        from ..services import autopilot_runner
        from .autopilot import can_autopilot

        if not can_autopilot(user):
            return {"ok": True, "type": "chat", "message": "Autopilot is limited to authorized accounts."}
        if intent["type"] == "autopilot":
            try:
                await autopilot_runner.start(user)
            except autopilot_runner.AutopilotConflict as e:
                return {"ok": True, "type": "chat", "message": str(e)}
            msg = "Autopilot is on — scanning every 5 minutes while the market is open."
        else:
            await autopilot_runner.stop()
            msg = "Autopilot stopped."
        auth.save_chat(user_id, "assistant", msg)
        return {"ok": True, "type": "chat", "message": msg, "autopilot": autopilot_runner.is_running()}

    # engine.execute() closes every position immediately for this intent; in
    # v2 it goes through the same confirm card as every other order.
    if intent.get("type") == "close_all":
        if not user:
            return {"ok": True, "type": "chat", "message": "Sign in and connect your Alpaca account to place orders."}
        return {"ok": True, "type": "confirm_trade", "message": "", "trade": {"action": "close_all"}}

    if intent.get("type") == "stock_ideas":
        return await _start_scan(intent, user_id, is_plus)

    result = await loop.run_in_executor(_light_executor, in_request_context(engine.execute, intent, is_plus=is_plus))
    if result and result.get("ok") and result.get("type") == "analysis" and result.get("ticker"):
        popularity.record(result["ticker"], user_id=user_id or None, ip=_client_ip(request))
    out = await orch.build_response(loop, user_msg, intent, result, chat_history, user, is_plus)
    if used and isinstance(out, dict):
        out["model"] = used.get("label")
    return out


_IMAGE_PREFIXES = ("data:image/png;base64,", "data:image/jpeg;base64,", "data:image/webp;base64,")
_MAX_IMAGE_CHARS = 4_000_000  # ~3 MB of image; the browser shrinks it well under this


async def _image_reply(image: str, user_msg: str, chat_history: list, user_id: int, used: dict):
    if not image.startswith(_IMAGE_PREFIXES) or len(image) > _MAX_IMAGE_CHARS:
        return {"ok": True, "type": "chat", "message": "That image didn't come through — try a PNG or JPEG screenshot under a few MB."}
    loop = asyncio.get_running_loop()
    reply = await loop.run_in_executor(
        _light_executor, in_request_context(engine.ai_image_response, user_msg, image, chat_history[:-1])
    )
    if user_id:
        auth.save_chat(user_id, "assistant", reply)
    out = {"ok": True, "type": "chat", "message": reply}
    if used:
        out["model"] = used.get("label")
    return out


@router.get("/models")
def models():
    """Tiers for the composer's model picker."""
    return {"ok": True, "configured": bool(engine._llm_key()), "tiers": engine.llm_tiers()}


# A market scan takes ~15s and reads the same universe for everyone, so an
# identical scan (same category/filters, same plan tier) inside a few minutes
# is answered from the last run instead of re-downloading everything.
_SCAN_TTL = 3 * 60
_scan_cache: dict[str, tuple[float, str]] = {}


def _scan_key(intent: dict, is_plus: bool) -> str:
    import json

    shape = {k: v for k, v in intent.items() if not k.startswith("_")}
    return json.dumps([shape, is_plus], sort_keys=True, default=str)


async def _start_scan(intent: dict, user_id: int, is_plus: bool):
    import time

    key = _scan_key(intent, is_plus)
    hit = _scan_cache.get(key)
    if hit and time.time() - hit[0] < _SCAN_TTL:
        if user_id:
            try:
                auth.save_chat(user_id, "assistant", hit[1])
            except Exception:
                pass
        return {"ok": True, "type": "chat", "message": hit[1], "cached_scan": True}

    # Scan events go out on the shared broadcast channel; the id lets each
    # client pick out its own scan instead of taking whichever finishes first.
    import uuid

    scan_id = uuid.uuid4().hex[:12]
    loop = asyncio.get_event_loop()
    prog = _make_progress_cb(loop, scan_id)

    prev = _active_scans.pop(user_id, None)
    if prev and not prev.done():
        prev.cancel()

    async def _run_scan():
        try:
            res = await asyncio.wait_for(
                loop.run_in_executor(_scan_executor, in_request_context(engine.execute, intent, progress_cb=prog, is_plus=is_plus)),
                timeout=240,
            )
            msg_out = res.get("msg", "") if res and res.get("ok") else orch.friendly_error((res or {}).get("error", ""))
            msg_out = orch.humanize_labels(msg_out)
            if res and res.get("ok") and msg_out:
                import time as _t

                _scan_cache[key] = (_t.time(), msg_out)
            tickers_out = (res or {}).get("tickers", []) if res and res.get("ok") else []
            if user_id:
                try:
                    auth.save_chat(user_id, "assistant", msg_out)
                except Exception:
                    pass
            await manager.broadcast("scan_result", {"scan_id": scan_id, "ok": bool(res and res.get("ok")), "message": msg_out, "tickers": tickers_out})
        except asyncio.CancelledError:
            raise
        except asyncio.TimeoutError:
            await manager.broadcast("scan_result", {"scan_id": scan_id, "ok": False, "message": "The scan is taking longer than usual — try again in a moment."})
        except Exception as e:
            await manager.broadcast("scan_result", {"scan_id": scan_id, "ok": False, "message": orch.friendly_error(str(e))})

    task = asyncio.ensure_future(_run_scan())
    if user_id:
        _active_scans[user_id] = task
    return {"ok": True, "type": "scan_started", "scan_id": scan_id, "message": "Scanning the market…"}


@router.post("/clear")
def clear_chat(authorization: str = Header(None)):
    user = current_user_optional(authorization)
    if user:
        try:
            auth.clear_chat(user["id"])
        except Exception:
            pass
    return {"ok": True}
