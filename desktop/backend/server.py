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
import engine

# ── State ──
autopilot_task: Optional[asyncio.Task] = None
connected_clients: list[WebSocket] = []
chat_history: list[dict] = []


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown."""
    print("🟢 Paula backend starting...")
    # Start the EOD guardian — runs independently of autopilot
    eod_task = asyncio.create_task(_eod_guardian())
    yield
    print("🔴 Paula backend stopping...")
    eod_task.cancel()
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


def _sanitize_trade_error(result: dict) -> dict:
    """Strip broker day-trade restriction text from user-facing errors."""
    error = result.get("error")
    if not error:
        return result
    error_lc = error.lower()
    if (
        "no day trades permitted" in error_lc
        or "previous day account equity" in error_lc
        or "pattern day trader" in error_lc
    ):
        result = dict(result)
        result["error"] = "Order rejected"
    return result



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


@app.post("/api/chat/clear")
async def clear_chat():
    """Clear chat history."""
    chat_history.clear()
    return {"ok": True}


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
    result = _sanitize_trade_error(result)
    if result.get("ok"):
        await broadcast("trade", {"action": "buy", "ticker": req.ticker, **result})
    return result


@app.post("/api/sell")
async def sell_stock(req: TradeRequest):
    """Sell a stock."""
    result = engine.alpaca_sell(ticker=req.ticker, qty=req.qty, sell_all=req.qty is None)
    result = _sanitize_trade_error(result)
    if result.get("ok"):
        await broadcast("trade", {"action": "sell", "ticker": req.ticker, **result})
    return result


@app.post("/api/short")
async def short_stock(req: ShortRequest):
    """Short a stock."""
    result = engine.alpaca_short(ticker=req.ticker, qty=req.qty)
    result = _sanitize_trade_error(result)
    if result.get("ok"):
        await broadcast("trade", {"action": "short", "ticker": req.ticker, **result})
    return result


@app.post("/api/cover")
async def cover_stock(req: CoverRequest):
    """Cover a short position."""
    result = engine.alpaca_cover(ticker=req.ticker, qty=req.qty, cover_all=req.cover_all)
    result = _sanitize_trade_error(result)
    if result.get("ok"):
        await broadcast("trade", {"action": "cover", "ticker": req.ticker, **result})
    return result


@app.post("/api/close-all")
async def close_all():
    """Close all positions."""
    result = engine.alpaca_close_all()
    result = _sanitize_trade_error(result)
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
async def chart_data(ticker: str, period: str = "1y"):
    """Get chart OHLCV data."""
    try:
        import yfinance as yf
        hist = yf.Ticker(ticker).history(period=period)
        if hist is None or hist.empty:
            return {"ok": False, "error": "No data"}
        # Format dates as YYYY-MM-DD, deduplicate
        raw_dates = [str(d)[:10] for d in hist.index]
        seen = set()
        indices = []
        clean_dates = []
        for i, d in enumerate(raw_dates):
            if d not in seen:
                seen.add(d)
                indices.append(i)
                clean_dates.append(d)
        data = {
            "dates": clean_dates,
            "open": [round(float(hist["Open"].iloc[i]), 2) for i in indices],
            "high": [round(float(hist["High"].iloc[i]), 2) for i in indices],
            "low": [round(float(hist["Low"].iloc[i]), 2) for i in indices],
            "close": [round(float(hist["Close"].iloc[i]), 2) for i in indices],
            "volume": [int(hist["Volume"].iloc[i]) for i in indices],
        }
        return {"ok": True, "data": data}
    except Exception as e:
        return {"ok": False, "error": str(e)[:100]}


# ── Chat (AI response via Groq) ──

@app.post("/api/chat")
async def chat(msg: ChatMessage):
    """Process a chat message through Paula's brain."""
    global autopilot_task
    user_msg = msg.message.strip()
    if not user_msg:
        return {"ok": False, "error": "Empty message"}

    chat_history.append({"role": "user", "content": user_msg})

    # Route the message
    intent = engine.route(user_msg)

    # If chat triggers autopilot, start/stop the real background task
    if intent.get("type") == "autopilot":
        if not autopilot_task or autopilot_task.done():
            autopilot_task = asyncio.create_task(_autopilot_loop())

    if intent.get("type") == "stop_autopilot":
        if autopilot_task and not autopilot_task.done():
            autopilot_task.cancel()
            autopilot_task = None

    # Run in thread pool since engine functions are blocking
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, engine.execute, intent)

    if result and result.get("ok"):
        resp = result.get("msg", "")
        rtype = result.get("type", "")

        if rtype == "analysis":
            if not resp:
                resp = await loop.run_in_executor(None, engine.ai_response, user_msg, result.get("data"), chat_history, "US")
        elif rtype == "list":
            # Send list data to AI for real analysis instead of just showing a table
            list_data = result.get("data", [])
            resp = await loop.run_in_executor(None, engine.ai_response, user_msg, {"list_title": result.get("title", ""), "stocks": list_data}, chat_history, "US")
        elif not resp:
            resp = await loop.run_in_executor(None, engine.ai_response, user_msg, None, chat_history, "US")
    elif result and result.get("error"):
        resp = f"⚠️ {result['error']}"
    else:
        resp = await loop.run_in_executor(None, engine.ai_response, user_msg, None, chat_history, "US")

    chat_history.append({"role": "assistant", "content": resp})

    response = {
        "ok": True,
        "message": resp,
        "type": result.get("type") if result else "chat",
        "ticker": result.get("ticker") if result else None,
        "trade_signal": result.get("trade_signal") if result else None,
        "table": result.get("data") if result and result.get("type") == "list" else None,
        "autopilot": autopilot_task is not None and not autopilot_task.done(),
    }

    return response


# ── Autopilot ──

async def _eod_guardian():
    """
    DEDICATED EOD CLOSER — runs independently of autopilot.
    Every 30 seconds from 2:00-3:00 PM CT, checks for open positions
    and force-closes them. Multiple safety layers:
    1. Cancel ALL orders first
    2. DELETE /positions with cancel_orders=true
    3. Verify positions are closed
    4. If any remain, retry individually
    """
    import requests as req
    while True:
        try:
            et = ZoneInfo("US/Eastern")
            ct = ZoneInfo("US/Central")
            now_et = datetime.now(et)
            now_ct = datetime.now(ct)

            # Only run on weekdays during EOD window (3:00-4:00 PM ET = 2:00-3:00 PM CT)
            if now_et.weekday() < 5:
                eod_start = now_et.replace(hour=15, minute=0, second=0, microsecond=0)
                eod_end = now_et.replace(hour=16, minute=0, second=0, microsecond=0)

                if eod_start <= now_et <= eod_end:
                    positions = engine.alpaca_positions()
                    if positions:
                        time_str = now_ct.strftime('%I:%M %p CT')
                        await broadcast("autopilot", {"status": "scanned", "log": [
                            f"🔔 **EOD GUARDIAN** — {len(positions)} positions open at {time_str}",
                        ]})

                        # Step 1: Cancel ALL pending orders
                        try:
                            req.delete(f"{engine.ALPACA_BASE}/v2/orders",
                                      headers=engine._alpaca_headers(), timeout=10)
                        except Exception:
                            pass

                        # Step 2: Wait for cancellations to process
                        await asyncio.sleep(2)

                        # Step 3: Close all positions
                        try:
                            req.delete(f"{engine.ALPACA_BASE}/v2/positions",
                                      headers=engine._alpaca_headers(),
                                      params={"cancel_orders": "true"}, timeout=10)
                        except Exception:
                            pass

                        # Step 4: Wait and verify
                        await asyncio.sleep(5)
                        remaining = engine.alpaca_positions()

                        if not remaining:
                            await broadcast("autopilot", {"status": "scanned", "log": [
                                f"✅ All positions closed — flat for the night"
                            ]})
                            await broadcast("trade", {"action": "close_all"})
                        else:
                            # Step 5: Retry individually
                            await broadcast("autopilot", {"status": "scanned", "log": [
                                f"⚠️ {len(remaining)} positions survived — retrying individually"
                            ]})
                            for pos in remaining:
                                try:
                                    # Cancel orders for this ticker
                                    req.delete(f"{engine.ALPACA_BASE}/v2/orders",
                                              headers=engine._alpaca_headers(), timeout=10)
                                    await asyncio.sleep(1)
                                    # Close position
                                    req.delete(
                                        f"{engine.ALPACA_BASE}/v2/positions/{pos['ticker']}",
                                        headers=engine._alpaca_headers(),
                                        params={"cancel_orders": "true"}, timeout=10)
                                except Exception:
                                    pass

                            await asyncio.sleep(3)
                            final = engine.alpaca_positions()
                            if not final:
                                await broadcast("autopilot", {"status": "scanned", "log": [
                                    "✅ All positions finally closed"
                                ]})
                            else:
                                await broadcast("autopilot", {"status": "scanned", "log": [
                                    f"🔴 **{len(final)} POSITIONS STILL OPEN** — will retry in 30s"
                                ]})
                            await broadcast("trade", {"action": "close_all"})

                    # During EOD window, check every 30 seconds
                    await asyncio.sleep(30)
                    continue

        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"EOD Guardian error: {e}")

        # Outside EOD window, sleep 60 seconds
        await asyncio.sleep(60)


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
