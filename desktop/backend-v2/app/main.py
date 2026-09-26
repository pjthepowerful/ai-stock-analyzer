"""
Paula v2 backend — FastAPI, typed routers, real HTTP status codes.
Reuses the existing engine/auth/trading modules unchanged (see bridge.py).
Runs on :4141 so it never collides with the original backend on :3141.
"""
import asyncio
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from .json_safe import SafeJSONResponse
from .routers import admin as admin_router
from .routers import auth as auth_router
from .routers import autopilot as autopilot_router
from .routers import chart as chart_router
from .routers import chat as chat_router
from .routers import chats as chats_router
from .routers import earnings as earnings_router
from .routers import lab as lab_router
from .routers import launch as launch_router
from .routers import market as market_router
from .routers import overview as overview_router
from .routers import plus as plus_router
from .routers import research as research_router
from .routers import strategy as strategy_router
from .routers import trade as trade_router
from .services import autopilot_runner
from .ws import manager



@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Keep the market strip's cache warm so no page load waits on it.
    warm = asyncio.create_task(overview_router.keep_warm())
    # Autopilot runs unattended: bring it back if it was on before a restart.
    try:
        await autopilot_runner.resume_if_needed()
    except Exception as e:
        print(f"[autopilot] could not resume: {e!r}", flush=True)
    yield
    warm.cancel()
    await autopilot_runner.shutdown()


app = FastAPI(title="Paula v2", default_response_class=SafeJSONResponse, lifespan=lifespan)


# Before the launch time, only the coming-soon page and the owner get through.
# Registered before CORS so CORS (added last = outermost) still decorates it.
@app.middleware("http")
async def prelaunch_gate(request: Request, call_next):
    if launch_router.prelaunch_blocked(request):
        return JSONResponse({"detail": "Paula 5 isn't live yet.", "prelaunch": True}, status_code=503)
    return await call_next(request)


@app.middleware("http")
async def maintenance_gate(request: Request, call_next):
    if admin_router.maintenance_blocked(request):
        return JSONResponse({"detail": "Paula is down for maintenance.", "maintenance": True}, status_code=503)
    return await call_next(request)

# Local dev: any localhost port. Hosted: the same Vercel deployments the
# original backend allows (override with FRONTEND_ORIGIN_REGEX), plus any exact
# URLs in ALLOWED_ORIGINS, comma-separated.
_extra_origins = [o.strip() for o in os.environ.get("ALLOWED_ORIGINS", "").split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_extra_origins,
    allow_origin_regex=os.environ.get(
        "FRONTEND_ORIGIN_REGEX",
        r"https://ai-stock-analyzer[a-z0-9-]*\.vercel\.app"
        r"|https://([a-z0-9-]+-)?pjthepowerful[a-z0-9-]*\.vercel\.app",
    )
    + r"|https?://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router.router)
app.include_router(chat_router.router)
app.include_router(chats_router.router)
app.include_router(market_router.router)
app.include_router(overview_router.router)
app.include_router(chart_router.router)
app.include_router(autopilot_router.router)
app.include_router(trade_router.router)
app.include_router(earnings_router.router)
app.include_router(plus_router.router)
app.include_router(research_router.router)
app.include_router(admin_router.router)
app.include_router(strategy_router.router)
app.include_router(launch_router.router)
app.include_router(lab_router.router)


@app.get("/api/health")
def health():
    return {"ok": True, "service": "paula-backend-v2"}


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await manager.connect(ws)
    try:
        while True:
            try:
                msg = await ws.receive_json()
            except ValueError:
                continue  # a malformed frame shouldn't drop the connection
            if isinstance(msg, dict) and msg.get("type") == "ping":
                await ws.send_json({"event": "pong"})
    except WebSocketDisconnect:
        pass
    finally:
        # Any other failure too — a dead socket left in the list would be
        # retried on every broadcast.
        manager.disconnect(ws)
