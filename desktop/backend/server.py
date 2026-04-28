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

# ── Phone notifications via ntfy.sh ──
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "paula-trades")  # Change this to your own topic

async def send_phone_notification(title: str, message: str, priority: str = "default"):
    """Send push notification to phone via ntfy.sh (free, no signup)."""
    try:
        import requests as req
        req.post(
            f"https://ntfy.sh/{NTFY_TOPIC}",
            data=message.encode(),
            headers={
                "Title": title,
                "Priority": priority,
                "Tags": "chart_with_upwards_trend" if "Buy" in title or "+" in message else "chart_with_downwards_trend",
            },
            timeout=5,
        )
    except Exception:
        pass  # Don't break trading if notification fails

# ── Trade Logger — saves every trade to JSON for performance tracking ──
import pathlib
TRADE_LOG_PATH = pathlib.Path(__file__).parent / "trade_log.json"

def log_trade(action: str, ticker: str, qty: float = 0, price: float = 0, pnl: float = 0, extra: dict = None):
    """Append a trade to the log file."""
    try:
        trades = []
        if TRADE_LOG_PATH.exists():
            trades = json.loads(TRADE_LOG_PATH.read_text())
        trades.append({
            "time": datetime.now().isoformat(),
            "action": action,
            "ticker": ticker,
            "qty": qty,
            "price": price,
            "pnl": pnl,
            **(extra or {}),
        })
        # Keep last 500 trades
        trades = trades[-500:]
        TRADE_LOG_PATH.write_text(json.dumps(trades, indent=2))
    except Exception:
        pass


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

    # ── Push notification via ntfy.sh ──
    if event == "trade" and data.get("action"):
        try:
            import requests as req
            action = data.get("action", "")
            ticker = data.get("ticker", data.get("symbol", ""))
            ntfy_topic = os.environ.get("NTFY_TOPIC", "paula-trades")
            emoji = {"buy": "📈", "sell": "📉", "short": "📉", "cover": "📈", "close_all": "🔴"}.get(action, "📊")
            title = f"{emoji} Paula: {action.upper()} {ticker}"
            if action == "close_all":
                title = "🔴 Paula: All positions closed"
            req.post(f"https://ntfy.sh/{ntfy_topic}",
                     data=title.encode(), headers={"Title": "Paula Trade"}, timeout=3)
        except Exception:
            pass  # Don't let notification failure block anything

    # ── Trade logging to JSON ──
    if event == "trade" and data.get("action"):
        try:
            import pathlib
            log_path = pathlib.Path(__file__).parent / "trade_log.json"
            existing = []
            if log_path.exists():
                existing = json.loads(log_path.read_text())
            existing.append({
                "time": datetime.now(ZoneInfo("US/Central")).isoformat(),
                "action": data.get("action"),
                "ticker": data.get("ticker", data.get("symbol", "")),
                "qty": data.get("qty"),
                "price": data.get("price"),
                "pnl": data.get("pnl"),
            })
            # Keep last 500 trades
            existing = existing[-500:]
            log_path.write_text(json.dumps(existing, indent=2))
        except Exception:
            pass


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


@app.get("/api/performance")
async def performance():
    """Performance dashboard data — trade history, daily P&L, win rate."""
    import pathlib
    log_path = pathlib.Path(__file__).parent / "trade_log.json"
    config_path = pathlib.Path(__file__).parent / "autopilot_config.json"

    trades = []
    if log_path.exists():
        try:
            trades = json.loads(log_path.read_text())
        except Exception:
            pass

    config = {}
    if config_path.exists():
        try:
            config = json.loads(config_path.read_text())
        except Exception:
            pass

    # Calculate stats
    buys = [t for t in trades if t.get("action") == "buy"]
    sells = [t for t in trades if t.get("action") in ("sell", "cover")]

    # Group by date
    daily = {}
    for t in trades:
        date = t.get("time", "")[:10]
        if date not in daily:
            daily[date] = {"trades": 0, "buys": 0, "sells": 0}
        daily[date]["trades"] += 1
        if t.get("action") == "buy":
            daily[date]["buys"] += 1
        elif t.get("action") in ("sell", "cover"):
            daily[date]["sells"] += 1

    # Get Alpaca portfolio history for P&L chart
    pnl_history = []
    try:
        hist = engine.alpaca_portfolio_history()
        if hist:
            pnl_history = hist
    except Exception:
        pass

    return {
        "ok": True,
        "total_trades": len(trades),
        "recent_trades": trades[-20:],
        "daily_summary": daily,
        "tune_history": config.get("tune_history", []),
        "current_params": {k: v for k, v in config.items() if k not in ("tune_history", "last_tuned")},
        "pnl_history": pnl_history,
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
        log_trade("buy", req.ticker, qty=req.qty or 0, price=result.get("avg_price", 0))
        await send_phone_notification(f"Bought {req.ticker}", f"Qty: {req.qty or 'notional'}")
    return result


@app.post("/api/sell")
async def sell_stock(req: TradeRequest):
    """Sell a stock."""
    result = engine.alpaca_sell(ticker=req.ticker, qty=req.qty, sell_all=req.qty is None)
    result = _sanitize_trade_error(result)
    if result.get("ok"):
        await broadcast("trade", {"action": "sell", "ticker": req.ticker, **result})
        log_trade("sell", req.ticker, qty=req.qty or 0)
        await send_phone_notification(f"Sold {req.ticker}", f"Position closed")
    return result


@app.post("/api/short")
async def short_stock(req: ShortRequest):
    """Short a stock."""
    result = engine.alpaca_short(ticker=req.ticker, qty=req.qty)
    result = _sanitize_trade_error(result)
    if result.get("ok"):
        await broadcast("trade", {"action": "short", "ticker": req.ticker, **result})
        log_trade("short", req.ticker, qty=req.qty or 0)
        await send_phone_notification(f"Shorted {req.ticker}", f"Qty: {req.qty}")
    return result


@app.post("/api/cover")
async def cover_stock(req: CoverRequest):
    """Cover a short position."""
    result = engine.alpaca_cover(ticker=req.ticker, qty=req.qty, cover_all=req.cover_all)
    result = _sanitize_trade_error(result)
    if result.get("ok"):
        await broadcast("trade", {"action": "cover", "ticker": req.ticker, **result})
        log_trade("cover", req.ticker, qty=req.qty or 0)
        await send_phone_notification(f"Covered {req.ticker}", f"Short closed")
    return result


@app.post("/api/close-all")
async def close_all():
    """Close all positions."""
    result = engine.alpaca_close_all()
    result = _sanitize_trade_error(result)
    if result.get("ok"):
        await broadcast("trade", {"action": "close_all"})
        log_trade("close_all", "ALL")
        await send_phone_notification("All Positions Closed", "Portfolio is flat", priority="high")
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


@app.get("/api/performance")
async def get_performance():
    """Get trading performance data for dashboard."""
    try:
        trades = []
        if TRADE_LOG_PATH.exists():
            trades = json.loads(TRADE_LOG_PATH.read_text())

        # Also pull from Alpaca for real P&L data
        import requests as req
        headers = engine._alpaca_headers()
        base = engine.ALPACA_BASE

        # Get portfolio history (last 30 days)
        hist_r = req.get(f"{base}/v2/account/portfolio/history",
                        headers=headers,
                        params={"period": "1M", "timeframe": "1D"},
                        timeout=10)
        portfolio_history = []
        if hist_r.status_code == 200:
            h = hist_r.json()
            timestamps = h.get("timestamp", [])
            equity = h.get("equity", [])
            pnl = h.get("profit_loss", [])
            pnl_pct = h.get("profit_loss_pct", [])
            for i, ts in enumerate(timestamps):
                portfolio_history.append({
                    "date": datetime.fromtimestamp(ts).strftime("%Y-%m-%d"),
                    "equity": equity[i] if i < len(equity) else 0,
                    "pnl": pnl[i] if i < len(pnl) else 0,
                    "pnl_pct": round((pnl_pct[i] or 0) * 100, 2) if i < len(pnl_pct) else 0,
                })

        # Get closed orders for win/loss stats (last 7 days)
        et = ZoneInfo("US/Eastern")
        from datetime import timedelta
        orders_r = req.get(f"{base}/v2/orders",
                          headers=headers,
                          params={"status": "closed", "limit": 200,
                                  "after": (datetime.now(et) - timedelta(days=7)).isoformat()},
                          timeout=15)
        recent_orders = orders_r.json() if orders_r.status_code == 200 else []
        filled_orders = [o for o in recent_orders if o.get("filled_qty") and float(o["filled_qty"]) > 0]

        # Auto-tune config
        config_path = pathlib.Path(__file__).parent / "autopilot_config.json"
        config = {}
        if config_path.exists():
            config = json.loads(config_path.read_text())

        return {
            "ok": True,
            "data": {
                "trade_log": trades[-50:],
                "portfolio_history": portfolio_history,
                "recent_orders": len(filled_orders),
                "config": {k: v for k, v in config.items() if k != "tune_history"},
                "tune_history": config.get("tune_history", [])[-10:],
            }
        }
    except Exception as e:
        return {"ok": False, "error": str(e)[:100]}


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
                eod_start = now_et.replace(hour=15, minute=30, second=0, microsecond=0)  # 2:30 PM CT
                eod_end = now_et.replace(hour=16, minute=0, second=0, microsecond=0)    # 3:00 PM CT

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

            buys = result.get("buys", 0)
            sells = result.get("sells", 0)
            shorts = result.get("shorts", 0)

            await broadcast("autopilot", {
                "status": "scanned",
                "log": result.get("log", []),
                "buys": buys,
                "shorts": shorts,
                "sells": sells,
                "scanned": result.get("scanned", 0),
            })

            # Send phone notification if trades were made
            if buys > 0 or sells > 0 or shorts > 0:
                parts = []
                if buys: parts.append(f"{buys} bought")
                if shorts: parts.append(f"{shorts} shorted")
                if sells: parts.append(f"{sells} sold")
                await send_phone_notification(
                    "Paula Autopilot",
                    " · ".join(parts),
                    priority="default"
                )

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
