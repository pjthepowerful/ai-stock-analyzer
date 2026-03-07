"""
Paula Desktop — FastAPI Backend
Wraps the trading engine as a local API server.
"""

import asyncio
import json
import time
import os
from datetime import datetime
from zoneinfo import ZoneInfo
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# ── Import the trading engine ──
# This imports everything from the existing trading.py
import engine

# ── State ──
autopilot_task: Optional[asyncio.Task] = None
connected_clients: list[WebSocket] = []
chat_history: list[dict] = []


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown."""
    print("🟢 Paula backend starting...")
    yield
    print("🔴 Paula backend stopping...")
    if autopilot_task and not autopilot_task.done():
        autopilot_task.cancel()


app = FastAPI(title="Paula", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Models ──

class ChatMessage(BaseModel):
    message: str

class TradeRequest(BaseModel):
    ticker: str
    qty: Optional[int] = None
    notional: Optional[float] = None

class ShortRequest(BaseModel):
    ticker: str
    qty: int = 1

class CoverRequest(BaseModel):
    ticker: str
    qty: Optional[int] = None
    cover_all: bool = False


# ── Broadcast to WebSocket clients ──

async def broadcast(event: str, data: dict):
    """Send event to all connected WebSocket clients."""
    msg = json.dumps({"event": event, "data": data})
    disconnected = []
    for ws in connected_clients:
        try:
            await ws.send_text(msg)
        except Exception:
            disconnected.append(ws)
    for ws in disconnected:
        connected_clients.remove(ws)


# ── WebSocket for real-time updates ──

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_clients.append(websocket)
    try:
        # Send current state on connect
        await websocket.send_text(json.dumps({
            "event": "connected",
            "data": {
                "autopilot": autopilot_task is not None and not autopilot_task.done(),
            }
        }))
        while True:
            data = await websocket.receive_text()
            # Client can send pings or commands via WS
            msg = json.loads(data)
            if msg.get("type") == "ping":
                await websocket.send_text(json.dumps({"event": "pong"}))
    except WebSocketDisconnect:
        if websocket in connected_clients:
            connected_clients.remove(websocket)


# ── REST Endpoints ──

@app.get("/api/health")
async def health():
    ct = ZoneInfo("US/Central")
    return {
        "status": "ok",
        "time_et": datetime.now(ct).strftime("%I:%M %p CT"),
        "autopilot": autopilot_task is not None and not autopilot_task.done(),
    }


@app.get("/api/account")
async def get_account():
    """Get Alpaca account info."""
    acc = engine.alpaca_account()
    if not acc:
        return {"ok": False, "error": "Can't connect to Alpaca"}
    return {"ok": True, "data": acc}


@app.get("/api/positions")
async def get_positions():
    """Get all open positions."""
    positions = engine.alpaca_positions()
    return {"ok": True, "data": positions}


@app.get("/api/orders")
async def get_orders(status: str = "open", limit: int = 10):
    """Get recent orders."""
    orders = engine.alpaca_orders(status=status, limit=limit)
    return {"ok": True, "data": orders}


@app.get("/api/price/{ticker}")
async def get_price(ticker: str):
    """Get current price for a ticker."""
    data = engine.fetch_price(ticker)
    if not data:
        return {"ok": False, "error": f"No data for {ticker}"}
    return {"ok": True, "data": data}


@app.get("/api/analyze/{ticker}")
async def analyze_ticker(ticker: str):
    """Full analysis of a ticker."""
    data = engine.fetch_full(ticker)
    if not data:
        return {"ok": False, "error": f"No data for {ticker}"}
    signal = engine.generate_trade_signal(data)
    return {"ok": True, "data": {**data, "signal": signal}}


@app.get("/api/analyze-intraday/{ticker}")
async def analyze_intraday(ticker: str):
    """Intraday analysis using 5min bars."""
    data = engine.fetch_scan_intraday(ticker)
    if not data:
        return {"ok": False, "error": f"No intraday data for {ticker}"}
    signal = engine.generate_intraday_signal(data)
    return {"ok": True, "data": {**data, "signal": signal}}


@app.post("/api/buy")
async def buy_stock(req: TradeRequest):
    """Buy a stock."""
    result = engine.alpaca_buy(ticker=req.ticker, qty=req.qty, notional=req.notional)
    if result.get("ok"):
        await broadcast("trade", {"action": "buy", "ticker": req.ticker, **result})
    return result


@app.post("/api/sell")
async def sell_stock(req: TradeRequest):
    """Sell a stock."""
    result = engine.alpaca_sell(ticker=req.ticker, qty=req.qty, sell_all=req.qty is None)
    if result.get("ok"):
        await broadcast("trade", {"action": "sell", "ticker": req.ticker, **result})
    return result


@app.post("/api/short")
async def short_stock(req: ShortRequest):
    """Short a stock."""
    result = engine.alpaca_short(ticker=req.ticker, qty=req.qty)
    if result.get("ok"):
        await broadcast("trade", {"action": "short", "ticker": req.ticker, **result})
    return result


@app.post("/api/cover")
async def cover_stock(req: CoverRequest):
    """Cover a short position."""
    result = engine.alpaca_cover(ticker=req.ticker, qty=req.qty, cover_all=req.cover_all)
    if result.get("ok"):
        await broadcast("trade", {"action": "cover", "ticker": req.ticker, **result})
    return result


@app.post("/api/close-all")
async def close_all():
    """Close all positions."""
    result = engine.alpaca_close_all()
    if result.get("ok"):
        await broadcast("trade", {"action": "close_all"})
    return result


@app.get("/api/market-regime")
async def market_regime():
    """Check market regime."""
    regime = engine.check_market_regime()
    return {"ok": True, "data": regime}


@app.get("/api/spy-trend")
async def spy_trend():
    """Get SPY intraday trend."""
    trend = engine._get_spy_intraday_trend()
    return {"ok": True, "data": trend}


@app.get("/api/chart/{ticker}")
async def chart_data(ticker: str, period: str = "6mo"):
    """Get chart OHLCV data."""
    try:
        import yfinance as yf
        hist = yf.Ticker(ticker).history(period=period)
        if hist is None or hist.empty:
            return {"ok": False, "error": "No data"}
        data = {
            "dates": hist.index.strftime("%Y-%m-%d %H:%M").tolist(),
            "open": hist["Open"].round(2).tolist(),
            "high": hist["High"].round(2).tolist(),
            "low": hist["Low"].round(2).tolist(),
            "close": hist["Close"].round(2).tolist(),
            "volume": hist["Volume"].tolist(),
        }
        return {"ok": True, "data": data}
    except Exception as e:
        return {"ok": False, "error": str(e)[:100]}


# ── Chat (AI response via Groq) ──

@app.post("/api/chat")
async def chat(msg: ChatMessage):
    """Process a chat message through Paula's brain."""
    user_msg = msg.message.strip()
    if not user_msg:
        return {"ok": False, "error": "Empty message"}

    chat_history.append({"role": "user", "content": user_msg})

    # Route the message
    intent = engine.route(user_msg)
    result = engine.execute(intent)

    if result and result.get("ok"):
        resp = result.get("msg", "")
        if not resp and result.get("type") == "analysis":
            resp = engine.ai_response(user_msg, result.get("data"), chat_history, "US")
        elif not resp:
            resp = engine.ai_response(user_msg, None, chat_history, "US")
    elif result and result.get("error"):
        resp = f"⚠️ {result['error']}"
    else:
        resp = engine.ai_response(user_msg, None, chat_history, "US")

    chat_history.append({"role": "assistant", "content": resp})

    response = {
        "ok": True,
        "message": resp,
        "type": result.get("type") if result else "chat",
        "ticker": result.get("ticker") if result else None,
        "trade_signal": result.get("trade_signal") if result else None,
        "table": result.get("data") if result and result.get("type") == "list" else None,
    }

    # Don't broadcast here — the REST response already delivers the message
    # WebSocket is only for autopilot updates and trade notifications
    return response


# ── Autopilot ──

async def _autopilot_loop():
    """Background autopilot loop — runs every 5 minutes."""
    while True:
        try:
            is_open, status_msg = engine._market_is_open()
            if not is_open:
                await broadcast("autopilot", {"status": "paused", "reason": status_msg})
                await asyncio.sleep(60)
                continue

            # Run the scan in a thread pool (yfinance is blocking)
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, engine.run_autopilot)

            await broadcast("autopilot", {
                "status": "scanned",
                "log": result.get("log", []),
                "buys": result.get("buys", 0),
                "shorts": result.get("shorts", 0),
                "sells": result.get("sells", 0),
                "scanned": result.get("scanned", 0),
            })

        except asyncio.CancelledError:
            break
        except Exception as e:
            await broadcast("autopilot", {"status": "error", "error": str(e)[:200]})

        await asyncio.sleep(5 * 60)  # 5 minutes


@app.post("/api/autopilot/start")
async def start_autopilot():
    """Start the autopilot background loop."""
    global autopilot_task
    if autopilot_task and not autopilot_task.done():
        return {"ok": True, "message": "Autopilot already running"}

    autopilot_task = asyncio.create_task(_autopilot_loop())
    await broadcast("autopilot", {"status": "started"})
    return {"ok": True, "message": "Autopilot started"}


@app.post("/api/autopilot/stop")
async def stop_autopilot():
    """Stop the autopilot."""
    global autopilot_task
    if autopilot_task and not autopilot_task.done():
        autopilot_task.cancel()
        autopilot_task = None
    await broadcast("autopilot", {"status": "stopped"})
    return {"ok": True, "message": "Autopilot stopped"}


@app.get("/api/autopilot/status")
async def autopilot_status():
    """Check if autopilot is running."""
    running = autopilot_task is not None and not autopilot_task.done()
    return {"ok": True, "running": running}


# ── Run ──

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=3141, log_level="info")
