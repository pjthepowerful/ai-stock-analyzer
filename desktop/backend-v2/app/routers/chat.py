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
from ..ws import manager

router = APIRouter(prefix="/api/chat", tags=["chat"])

_scan_executor = ThreadPoolExecutor(max_workers=2)
_light_executor = ThreadPoolExecutor(max_workers=4)
_active_scans: dict[int, asyncio.Task] = {}

def _is_plus_or_exempt(user: Optional[dict]) -> bool:
    if not user:
        return False
    return bool(auth.is_plus(user["id"]) or is_admin(user))


def _make_progress_cb(loop: asyncio.AbstractEventLoop):
    def _cb(phase: str, pct: float, label: str = ""):
        asyncio.run_coroutine_threadsafe(
            manager.broadcast("scan_progress", {"phase": phase, "pct": pct, "label": label}), loop,
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

    intent = engine.route(user_msg, history=chat_history[:-1])

    if intent.get("type") in ("autopilot", "stop_autopilot"):
        return {"ok": True, "type": "chat", "message": "Autopilot isn't wired up in this preview build yet."}

    if intent.get("type") == "stock_ideas":
        return await _start_scan(intent, user_id, is_plus)

    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(_light_executor, in_request_context(engine.execute, intent, is_plus=is_plus))
    return await orch.build_response(loop, user_msg, intent, result, chat_history, user, is_plus)


async def _start_scan(intent: dict, user_id: int, is_plus: bool):
    loop = asyncio.get_event_loop()
    prog = _make_progress_cb(loop)

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
            tickers_out = (res or {}).get("tickers", []) if res and res.get("ok") else []
            if user_id:
                try:
                    auth.save_chat(user_id, "assistant", msg_out)
                except Exception:
                    pass
            await manager.broadcast("scan_result", {"ok": bool(res and res.get("ok")), "message": msg_out, "tickers": tickers_out})
        except asyncio.CancelledError:
            raise
        except asyncio.TimeoutError:
            await manager.broadcast("scan_result", {"ok": False, "message": "The scan is taking longer than usual — try again in a moment."})
        except Exception as e:
            await manager.broadcast("scan_result", {"ok": False, "message": orch.friendly_error(str(e))})

    task = asyncio.ensure_future(_run_scan())
    if user_id:
        _active_scans[user_id] = task
    return {"ok": True, "type": "scan_started", "message": "Scanning the market…"}


@router.post("/clear")
def clear_chat(authorization: str = Header(None)):
    user = current_user_optional(authorization)
    if user:
        try:
            auth.clear_chat(user["id"])
        except Exception:
            pass
    return {"ok": True}
