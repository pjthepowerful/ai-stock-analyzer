"""
Paula v2 backend — FastAPI, typed routers, real HTTP status codes.
Reuses the existing engine/auth/trading modules unchanged (see bridge.py).
Runs on :4141 so it never collides with the original backend on :3141.
"""
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from .routers import auth as auth_router
from .routers import chat as chat_router
from .routers import market as market_router
from .ws import manager

app = FastAPI(title="Paula v2")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5180", "http://127.0.0.1:5180"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router.router)
app.include_router(chat_router.router)
app.include_router(market_router.router)


@app.get("/api/health")
def health():
    return {"ok": True, "service": "paula-backend-v2"}


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await manager.connect(ws)
    try:
        while True:
            msg = await ws.receive_json()
            if msg.get("type") == "ping":
                await ws.send_json({"event": "pong"})
    except WebSocketDisconnect:
        manager.disconnect(ws)
