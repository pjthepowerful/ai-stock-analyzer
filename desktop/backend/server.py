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

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# ── Import the trading engine ──
import engine
import auth

# Disable yfinance timezone cache (prevents SQLite lock errors)
try:
    import yfinance as yf
    import tempfile
    # Use unique temp dir to avoid lock conflicts with concurrent requests
    _yf_cache = os.path.join(tempfile.gettempdir(), f"yf_tz_{os.getpid()}")
    os.makedirs(_yf_cache, exist_ok=True)
    yf.set_tz_cache_location(_yf_cache)
except Exception:
    pass

# ── State ──
autopilot_task: Optional[asyncio.Task] = None
connected_clients: list[WebSocket] = []
# Per-user session isolation — NO global shared state
_user_sessions: dict[int, list[dict]] = {}  # {user_id: [chat messages]}
_session_lock = asyncio.Lock()
autopilot_owner_id: Optional[int] = None  # Only one user can own autopilot

def _get_user_history(user_id: int) -> list:
    """Get chat history for a specific user. Creates if needed."""
    if user_id not in _user_sessions:
        # Load from DB on first access
        db_history = auth.get_chat_history(user_id, limit=20)
        _user_sessions[user_id] = db_history or []
    return _user_sessions[user_id]

def _trim_history(user_id: int, max_len: int = 30):
    """Keep history bounded to prevent memory bloat."""
    if user_id in _user_sessions and len(_user_sessions[user_id]) > max_len:
        _user_sessions[user_id] = _user_sessions[user_id][-max_len:]

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

    # Load saved API keys from DB (first user's keys)
    try:
        db = auth._get_db()
        row = db.execute("SELECT * FROM user_settings LIMIT 1").fetchone()
        db.close()
        if row:
            if row["alpaca_key"] and not os.environ.get("ALPACA_KEY_ID"):
                os.environ["ALPACA_KEY_ID"] = row["alpaca_key"]
                print(f"  ✓ Loaded Alpaca key from DB")
            if row["alpaca_secret"] and not os.environ.get("ALPACA_SECRET"):
                os.environ["ALPACA_SECRET"] = row["alpaca_secret"]
                print(f"  ✓ Loaded Alpaca secret from DB")
            if row["groq_key"] and not os.environ.get("GROQ_API_KEY"):
                os.environ["GROQ_API_KEY"] = row["groq_key"]
                print(f"  ✓ Loaded Groq key from DB")
            if row["polygon_key"] and not os.environ.get("POLYGON_API_KEY"):
                os.environ["POLYGON_API_KEY"] = row["polygon_key"]
                print(f"  ✓ Loaded Polygon key from DB")
    except Exception as e:
        print(f"  ⚠️ Could not load keys from DB: {e}")

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
    expose_headers=["*"],
)

# Global exception handler — ensures CORS headers on 500 errors
from fastapi.responses import JSONResponse
from fastapi import Request

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    print(f"⚠️ Unhandled error on {request.url.path}: {exc}")
    return JSONResponse(
        status_code=200,
        content={"ok": False, "error": str(exc)[:200]},
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

# ── Auth endpoints ──

class AuthRequest(BaseModel):
    username: str = None
    password: str
    email: str = None

class SettingsRequest(BaseModel):
    alpaca_key: str = ""
    alpaca_secret: str = ""
    groq_key: str = ""
    polygon_key: str = ""
    display_name: str = ""
    settings: dict = {}

def _get_user(authorization: str = Header(None)):
    """Extract user from Authorization header. Always fetches email from DB."""
    if not authorization:
        return None
    token = authorization.replace("Bearer ", "")
    user = auth.get_user(token)
    if user:
        # Always fetch fresh email from DB (old JWTs may lack it)
        try:
            db = auth._get_db()
            row = db.execute("SELECT email FROM users WHERE id = ?", (user["id"],)).fetchone()
            if row and row["email"]:
                user["email"] = row["email"]
            db.close()
        except: pass
    return user

@app.post("/api/auth/signup")
async def signup(req: AuthRequest):
    # Validate email format
    if req.email:
        import re as _re
        if not _re.match(r'^[^\s@]+@[^\s@]+\.[^\s@]+$', req.email):
            return {"ok": False, "error": "Invalid email format"}
    else:
        return {"ok": False, "error": "Email is required"}
    if not req.username or len(req.username.strip()) < 2:
        return {"ok": False, "error": "Name must be at least 2 characters"}
    if not req.password or len(req.password) < 6:
        return {"ok": False, "error": "Password must be at least 6 characters"}
    result = auth.signup(req.username.strip(), req.password, req.email.strip().lower())
    return result

@app.post("/api/auth/login")
async def login(req: AuthRequest):
    # Login accepts email or username
    identifier = req.email or req.username
    if not identifier:
        return {"ok": False, "error": "Email is required"}
    result = auth.login(identifier.strip(), req.password)
    return result

@app.get("/api/auth/me")
async def me(authorization: str = Header(None)):
    user = _get_user(authorization)
    if not user:
        return {"ok": False, "error": "Not authenticated"}
    settings = auth.get_settings(user["id"])
    return {"ok": True, "user": user, "settings": settings}

@app.post("/api/auth/settings")
async def save_user_settings(req: SettingsRequest, authorization: str = Header(None)):
    user = _get_user(authorization)
    if not user:
        return {"ok": False, "error": "Not authenticated"}
    result = auth.save_settings(user["id"], req.dict())

    # Hot-reload API keys into environment (no restart needed)
    if req.alpaca_key:
        os.environ["ALPACA_KEY_ID"] = req.alpaca_key
    if req.alpaca_secret:
        os.environ["ALPACA_SECRET"] = req.alpaca_secret

    return result


@app.get("/api/auth/onboarding")
async def check_onboarding(authorization: str = Header(None)):
    """Check if user has completed onboarding (has Alpaca keys)."""
    user = _get_user(authorization)
    if not user:
        return {"ok": False, "error": "Not authenticated"}
    settings = auth.get_settings(user["id"])
    has_keys = bool(settings.get("alpaca_key")) and bool(settings.get("alpaca_secret"))
    return {"ok": True, "onboarded": has_keys, "user": user}

@app.get("/api/auth/chat-history")
async def get_chat_hist(authorization: str = Header(None)):
    user = _get_user(authorization)
    if not user:
        return {"ok": False, "error": "Not authenticated"}
    history = auth.get_chat_history(user["id"])
    return {"ok": True, "messages": history}

@app.post("/api/auth/save-chat")
async def save_chat_msg(authorization: str = Header(None)):
    """Chat saving is handled automatically by the chat endpoint."""
    return {"ok": True}


@app.get("/api/health")
async def health():
    ct = ZoneInfo("US/Central")
    return {
        "status": "ok",
        "time_et": datetime.now(ct).strftime("%I:%M %p CT"),
        "autopilot": autopilot_task is not None and not autopilot_task.done(),
    }


@app.get("/api/performance")
async def performance(period: str = "1M"):
    """Performance dashboard data with period-specific trade recaps."""
    import pathlib
    from datetime import timedelta
    import requests as req

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

    # Get Alpaca portfolio history for equity chart
    pnl_history = []
    try:
        period_map = {"1D": "1D", "1W": "1W", "1M": "1M", "3M": "3M", "6M": "6M", "1A": "1A", "all": "all"}
        api_period = period_map.get(period, "1M")
        hist = engine.alpaca_portfolio_history(period=api_period)
        if hist and hist.get("equity"):
            pnl_history = [{"equity": round(e, 2), "pnl": round(p, 2), "ts": t}
                          for t, e, p in zip(hist["timestamps"], hist["equity"], hist.get("profit_loss", [0]*len(hist["equity"])))
                          if e and e > 0]
    except Exception:
        pass

    # Account info
    acc = engine.alpaca_account() or {}

    # Pull closed orders from Alpaca for trade recaps
    daily_recaps = []
    recaps = []
    recap_type = "daily"  # daily, weekly, monthly
    try:
        et = ZoneInfo("US/Eastern")
        days_map = {"1D": 1, "1W": 7, "1M": 30, "3M": 90, "6M": 180, "1A": 365, "all": 730}
        lookback = days_map.get(period, 30)
        headers = engine._alpaca_headers()
        base = engine.ALPACA_BASE

        orders_r = req.get(f"{base}/v2/orders", headers=headers,
                          params={"status": "closed", "limit": 500,
                                  "after": (datetime.now(et) - timedelta(days=lookback)).isoformat()},
                          timeout=15)
        if orders_r.status_code == 200:
            closed = orders_r.json()
            filled = [o for o in closed if o.get("filled_qty") and float(o["filled_qty"]) > 0]

            # Group by date
            by_date = {}
            for o in filled:
                date = (o.get("filled_at") or o.get("created_at", ""))[:10]
                if not date:
                    continue
                if date not in by_date:
                    by_date[date] = {"buys": 0, "sells": 0, "tickers": set(), "total_orders": 0}
                by_date[date]["total_orders"] += 1
                if o["side"] == "buy":
                    by_date[date]["buys"] += 1
                else:
                    by_date[date]["sells"] += 1
                by_date[date]["tickers"].add(o["symbol"])

            # Match with P&L from portfolio history
            pnl_by_date = {}
            for p in pnl_history:
                if p.get("ts"):
                    d = datetime.fromtimestamp(p["ts"], tz=et).strftime("%Y-%m-%d")
                    pnl_by_date[d] = p.get("pnl", 0)

            # Build daily recaps
            for date in sorted(by_date.keys(), reverse=True):
                d = by_date[date]
                daily_recaps.append({
                    "date": date,
                    "trades": d["total_orders"],
                    "buys": d["buys"],
                    "sells": d["sells"],
                    "tickers": sorted(list(d["tickers"]))[:8],
                    "pnl": round(pnl_by_date.get(date, 0), 2),
                })

            # Aggregate based on period
            if period in ("1D", "1W"):
                # Day/Week: show daily recaps
                recaps = daily_recaps
                recap_type = "daily"
            elif period == "1M":
                # Month: group into ~4 weekly recaps
                recap_type = "weekly"
                from collections import defaultdict
                weeks = defaultdict(lambda: {"trades": 0, "buys": 0, "sells": 0, "tickers": set(), "pnl": 0, "days": 0, "start": "", "end": ""})
                for dr in daily_recaps:
                    dt = datetime.strptime(dr["date"], "%Y-%m-%d")
                    week_key = dt.strftime("%Y-W%U")
                    w = weeks[week_key]
                    w["trades"] += dr["trades"]
                    w["buys"] += dr["buys"]
                    w["sells"] += dr["sells"]
                    w["tickers"].update(dr["tickers"])
                    w["pnl"] += dr["pnl"]
                    w["days"] += 1
                    if not w["start"] or dr["date"] < w["start"]:
                        w["start"] = dr["date"]
                    if not w["end"] or dr["date"] > w["end"]:
                        w["end"] = dr["date"]
                for wk in sorted(weeks.keys(), reverse=True):
                    w = weeks[wk]
                    recaps.append({
                        "date": w["start"],
                        "end_date": w["end"],
                        "trades": w["trades"],
                        "buys": w["buys"],
                        "sells": w["sells"],
                        "tickers": sorted(list(w["tickers"]))[:10],
                        "pnl": round(w["pnl"], 2),
                        "days": w["days"],
                    })
            else:
                # 3M/6M/YTD/All: group into monthly recaps
                recap_type = "monthly"
                from collections import defaultdict
                months = defaultdict(lambda: {"trades": 0, "buys": 0, "sells": 0, "tickers": set(), "pnl": 0, "days": 0})
                for dr in daily_recaps:
                    month_key = dr["date"][:7]  # YYYY-MM
                    m = months[month_key]
                    m["trades"] += dr["trades"]
                    m["buys"] += dr["buys"]
                    m["sells"] += dr["sells"]
                    m["tickers"].update(dr["tickers"])
                    m["pnl"] += dr["pnl"]
                    m["days"] += 1
                for mk in sorted(months.keys(), reverse=True):
                    m = months[mk]
                    recaps.append({
                        "date": mk + "-01",
                        "trades": m["trades"],
                        "buys": m["buys"],
                        "sells": m["sells"],
                        "tickers": sorted(list(m["tickers"]))[:12],
                        "pnl": round(m["pnl"], 2),
                        "days": m["days"],
                    })
    except Exception:
        pass

    return {
        "ok": True,
        "total_trades": len(trades),
        "recent_trades": trades[-20:],
        "recaps": recaps,
        "recap_type": recap_type,
        "tune_history": config.get("tune_history", []),
        "current_params": {k: v for k, v in config.items() if k not in ("tune_history", "last_tuned")},
        "pnl_history": pnl_history,
        "equity": acc.get("equity", 0),
        "daily_pnl": acc.get("daily_pnl", 0),
        "daily_pnl_pct": acc.get("daily_pnl_pct", 0),
    }


class TitleRequest(BaseModel):
    message: str

@app.post("/api/chat/title")
async def generate_title(req: TitleRequest):
    """Generate a short chat title from the first message."""
    msg = req.message.strip()
    # Simple fallback: capitalize and shorten
    fallback = msg[:30].strip().title() if len(msg) <= 30 else msg[:28].strip() + '...'

    try:
        import requests as r
        key = os.environ.get("GROQ_API_KEY", "")
        if not key:
            return {"ok": True, "title": fallback}
        resp = r.post("https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={
                "model": "llama-3.3-70b-versatile",
                "messages": [
                    {"role": "system", "content": "You are a title generator. Output ONLY a 2-5 word title. Nothing else. No sentences. No punctuation. No quotes. No explanation. Just the title words.\n\nExamples:\nInput: 'market regime' → Market Regime Check\nInput: 'top gainers' → Top Gainers Today\nInput: 'analyze AAPL' → AAPL Analysis\nInput: 'What should I buy?' → Trade Ideas\nInput: 'How did we do today?' → Daily Recap\nInput: 'buy 10 NVDA' → Buy NVDA Order"},
                    {"role": "user", "content": msg[:100]}
                ],
                "max_tokens": 10, "temperature": 0.1
            }, timeout=4)
        if resp.status_code == 200:
            title = resp.json()["choices"][0]["message"]["content"].strip()
            # Clean up: remove quotes, periods, anything after a newline
            title = title.split('\n')[0].strip().strip('"').strip("'").rstrip('.')
            # If it looks conversational (>8 words), use fallback
            if len(title.split()) > 8 or len(title) > 40:
                return {"ok": True, "title": fallback}
            return {"ok": True, "title": title[:40]}
    except Exception:
        pass
    return {"ok": True, "title": fallback}


@app.post("/api/chat/clear")
async def clear_chat(authorization: str = Header(None)):
    """Clear chat history for current user."""
    user = _get_user(authorization)
    user_id = user["id"] if user else 0
    _user_sessions.pop(user_id, None)
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
        await send_phone_notification(f"📈 Bought {req.ticker}", f"Qty: {req.qty or 'notional'} | Entry: ${result.get('price', '?')}")
    return result


@app.post("/api/sell")
async def sell_stock(req: TradeRequest):
    """Sell a stock."""
    result = engine.alpaca_sell(ticker=req.ticker, qty=req.qty, sell_all=req.qty is None)
    result = _sanitize_trade_error(result)
    if result.get("ok"):
        await broadcast("trade", {"action": "sell", "ticker": req.ticker, **result})
        log_trade("sell", req.ticker, qty=req.qty or 0)
        await send_phone_notification(f"📉 Sold {req.ticker}", f"Position closed at ${result.get('price', '?')}")
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


@app.post("/api/backtest")
async def run_backtest_endpoint(authorization: str = Header(None)):
    """Run backtest with current strategy params."""
    import backtest
    try:
        # Load current auto-tuner params
        config = {}
        config_path = pathlib.Path(__file__).parent / "autopilot_config.json"
        if config_path.exists():
            config = json.loads(config_path.read_text())

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, lambda: backtest.run_backtest(
            days=90,
            min_score=config.get("MIN_SCORE", 82),
            max_positions=config.get("MAX_POSITIONS", 1),
            stop_pct=config.get("STOP_FLOOR", 0.013),
        ))
        return result
    except Exception as e:
        print(f"⚠️ Backtest error: {e}")
        return {"ok": False, "error": str(e)[:200]}


@app.post("/api/ml/train")
async def train_ml():
    """Train ML model on trade history."""
    try:
        log_path = pathlib.Path(__file__).parent / "trade_log.json"
        if not log_path.exists():
            return {"ok": False, "error": "No trade history yet"}

        trades = json.loads(log_path.read_text())
        if len(trades) < 3:
            return {"ok": False, "error": f"Need at least 3 trades to analyze. You have {len(trades)}."}

        # Build feature matrix from trade log
        features = []
        labels = []
        for t in trades:
            if t.get("pnl") is None:
                continue
            feat = {
                "score": t.get("score", 50),
                "rr_ratio": t.get("rr_ratio", 2.0),
                "confluence": t.get("confluence", 3),
                "hour": int(t.get("time", "12:00")[:2]) if t.get("time") else 12,
            }
            features.append(feat)
            labels.append(1 if t.get("pnl", 0) > 0 else 0)

        if len(features) < 3:
            return {"ok": False, "error": f"Need at least 3 completed trades with P&L data. Found {len(features)}."}

        # Simple logistic-style scoring (no sklearn needed)
        wins = [f for f, l in zip(features, labels) if l == 1]
        losses_f = [f for f, l in zip(features, labels) if l == 0]

        insights = {
            "total_trades": len(features),
            "wins": sum(labels),
            "losses": len(labels) - sum(labels),
            "win_rate": round(sum(labels) / len(labels) * 100, 1),
        }

        # Find patterns
        if wins and losses_f:
            avg_win_score = sum(w["score"] for w in wins) / len(wins)
            avg_loss_score = sum(w["score"] for w in losses_f) / len(losses_f)
            insights["avg_winning_score"] = round(avg_win_score, 1)
            insights["avg_losing_score"] = round(avg_loss_score, 1)
            insights["recommended_min_score"] = round((avg_win_score + avg_loss_score) / 2 + 5, 0)

            # Best/worst hours
            hour_wins = {}
            hour_total = {}
            for f, l in zip(features, labels):
                h = f["hour"]
                hour_total[h] = hour_total.get(h, 0) + 1
                if l: hour_wins[h] = hour_wins.get(h, 0) + 1
            best_hours = sorted(hour_total.keys(), key=lambda h: hour_wins.get(h, 0) / hour_total[h], reverse=True)
            insights["best_hours"] = best_hours[:3]
            insights["worst_hours"] = best_hours[-2:]

            # Recommendations
            recs = []
            if avg_win_score > avg_loss_score + 5:
                recs.append(f"Raise MIN_SCORE to {int(insights['recommended_min_score'])} — winning trades average {avg_win_score:.0f}")
            if insights["win_rate"] < 45:
                recs.append("Win rate below 45% — tighten entry criteria or widen stops")
            if insights["win_rate"] > 55:
                recs.append("Win rate above 55% — strategy is working, consider increasing position size")
            insights["recommendations"] = recs

        return {"ok": True, "insights": insights}
    except Exception as e:
        print(f"⚠️ ML error: {e}")
        return {"ok": False, "error": str(e)[:200]}


@app.get("/api/trades")
def get_trades():
    """Export trade log."""
    try:
        log_path = pathlib.Path(__file__).parent / "trade_log.json"
        if not log_path.exists():
            return {"ok": True, "data": []}
        trades = json.loads(log_path.read_text())
        return {"ok": True, "data": trades}
    except Exception as e:
        return {"ok": False, "error": str(e)[:100]}


@app.post("/api/profile")
async def save_profile(request: Request):
    """Save trader profile — updates autopilot config."""
    try:
        body = await request.json()
        config_path = pathlib.Path(__file__).parent / "autopilot_config.json"
        config = {}
        if config_path.exists():
            config = json.loads(config_path.read_text())

        # Map profile settings to engine params
        style = body.get("tradingStyle", "Day")
        bias = body.get("marketBias", "Bull")
        risk = body.get("riskPct", "1.0%")

        # Trading style affects hold time and stop discipline
        if style == "Swing":
            config["MAX_HOLD_DAYS"] = 5
            config["STOP_FLOOR"] = 0.015  # wider stops for swing
        else:
            config["MAX_HOLD_DAYS"] = 0  # intraday
            config["STOP_FLOOR"] = 0.01

        # Market bias affects LONG_ONLY mode
        if bias == "Bull":
            config["LONG_ONLY"] = True
        elif bias == "Bear":
            config["LONG_ONLY"] = False
        else:
            config["LONG_ONLY"] = True  # neutral defaults to long

        # Risk per trade
        risk_val = float(risk.replace("%", "")) / 100
        config["RISK_PER_TRADE"] = risk_val

        config_path.write_text(json.dumps(config, indent=2))
        return {"ok": True, "message": f"Profile saved: {style} · {bias} · {risk}"}
    except Exception as e:
        return {"ok": False, "error": str(e)[:100]}


@app.get("/api/profile")
def get_profile():
    """Get current trader profile from config."""
    try:
        config_path = pathlib.Path(__file__).parent / "autopilot_config.json"
        if not config_path.exists():
            return {"ok": True, "profile": {"tradingStyle": "Day", "marketBias": "Bull", "riskPct": "1.0%"}}
        config = json.loads(config_path.read_text())
        style = "Swing" if config.get("MAX_HOLD_DAYS", 0) > 0 else "Day"
        bias = "Bull" if config.get("LONG_ONLY", True) else "Bear"
        risk_val = config.get("RISK_PER_TRADE", 0.01) * 100
        risk = f"{risk_val:.1f}%"
        return {"ok": True, "profile": {"tradingStyle": style, "marketBias": bias, "riskPct": risk}}
    except Exception as e:
        return {"ok": False, "error": str(e)[:100]}


@app.get("/api/quick/{ticker}")
def quick_lookup(ticker: str):
    """Quick ticker lookup — uses the SAME signal engine as chat for consistent scores."""
    try:
        data = engine.fetch_full(ticker.upper())
        if not data or not data.get("price"):
            # Fallback to yfinance direct
            import yfinance as yf
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                t = yf.Ticker(ticker.upper())
                hist = t.history(period="5d")
            if hist is None or hist.empty:
                return {"ok": False, "error": "No data"}
            price = float(hist["Close"].iloc[-1])
            prev = float(hist["Close"].iloc[-2]) if len(hist) > 1 else price
            return {
                "ok": True, "ticker": ticker.upper(),
                "price": round(price, 2),
                "change": round(price - prev, 2),
                "change_pct": round((price - prev) / prev * 100 if prev else 0, 2),
                "score": 50, "signal": "HOLD",
            }

        signal = engine.generate_trade_signal(data)
        price = data.get("price", 0)
        prev = data.get("prev_close", price)
        change = price - prev if prev else 0
        change_pct = (change / prev * 100) if prev else 0

        score = signal.get("score", 50)
        action = signal.get("action", "HOLD")
        # Map action to simple signal
        if action in ("BUY", "STRONG_BUY"):
            sig = "BUY"
        elif action in ("SELL", "STRONG_SELL"):
            sig = "SELL"
        else:
            sig = "HOLD"

        return {
            "ok": True, "ticker": ticker.upper(),
            "price": round(price, 2),
            "change": round(change, 2),
            "change_pct": round(change_pct, 2),
            "score": score, "signal": sig,
        }
    except Exception as e:
        return {"ok": False, "error": str(e)[:100]}


@app.get("/api/spy-trend")
def spy_trend():
    """Get SPY intraday trend — sync, auto-threaded."""
    try:
        trend = engine._get_spy_intraday_trend()
        return {"ok": True, "data": trend}
    except Exception as e:
        return {"ok": False, "error": str(e)[:100]}


@app.get("/api/chart/{ticker}")
def chart_data(ticker: str, period: str = "1y"):
    """Get chart OHLCV data — sync endpoint, auto-threaded by FastAPI."""
    import yfinance as yf
    import warnings
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            hist = yf.Ticker(ticker.upper()).history(period=period)
        if hist is None or hist.empty:
            return {"ok": False, "error": "No data"}
        raw_dates = [str(d)[:10] for d in hist.index]
        seen = set()
        indices = []
        clean_dates = []
        for i, d in enumerate(raw_dates):
            if d not in seen:
                seen.add(d)
                indices.append(i)
                clean_dates.append(d)
        return {
            "ok": True, "data": {
                "dates": clean_dates,
                "open": [round(float(hist["Open"].iloc[i]), 2) for i in indices],
                "high": [round(float(hist["High"].iloc[i]), 2) for i in indices],
                "low": [round(float(hist["Low"].iloc[i]), 2) for i in indices],
                "close": [round(float(hist["Close"].iloc[i]), 2) for i in indices],
                "volume": [int(hist["Volume"].iloc[i]) for i in indices],
            }
        }
    except Exception as e:
        return {"ok": False, "error": str(e)[:100]}


# ── Chat (AI response via Groq) ──

@app.post("/api/chat/stream")
async def chat_stream(msg: ChatMessage, authorization: str = Header(None)):
    """Stream AI response token by token via SSE."""
    from starlette.responses import StreamingResponse
    global autopilot_task, autopilot_owner_id

    user_msg = msg.message.strip()
    if not user_msg:
        return {"ok": False, "error": "Empty message"}

    user = _get_user(authorization)
    user_id = user["id"] if user else 0
    if user:
        auth.save_chat(user["id"], "user", user_msg)

    # Per-user isolated chat history
    chat_history = _get_user_history(user_id)
    chat_history.append({"role": "user", "content": user_msg})

    # Route the message
    intent = engine.route(user_msg)
    itype = intent.get("type", "chat")

    # Autopilot start/stop — admin only
    if itype == "autopilot":
        if not user or user.get("email", "").lower() != ADMIN_EMAIL:
            return {"ok": True, "message": "Autopilot is restricted to admin accounts.", "stream": False, "type": "chat", "autopilot": False}
        if not autopilot_task or autopilot_task.done():
            autopilot_owner_id = user_id
            autopilot_task = asyncio.create_task(_autopilot_loop())
        resp = "Autopilot activated. Scanning every 5 minutes."
        chat_history.append({"role": "assistant", "content": resp})
        return {"ok": True, "message": resp, "stream": False, "type": "trade", "autopilot": True}

    if itype == "stop_autopilot":
        if not user or user.get("email", "").lower() != ADMIN_EMAIL:
            return {"ok": True, "message": "Autopilot is restricted to admin accounts.", "stream": False, "type": "chat", "autopilot": False}
        if autopilot_task and not autopilot_task.done():
            autopilot_task.cancel()
            autopilot_task = None
            autopilot_owner_id = None
        resp = "Autopilot stopped."
        chat_history.append({"role": "assistant", "content": resp})
        return {"ok": True, "message": resp, "stream": False, "type": "trade", "autopilot": False}

    # Execute intent (analysis, trade, list, etc)
    result = None
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, engine.execute, intent)
    except Exception as e:
        print(f"⚠️ Execute error: {e}")

    # Determine response strategy
    stock_data = None

    # If execute returned a ready message (trades, regime, etc) — return instantly
    if result and result.get("ok") and result.get("msg"):
        rtype = result.get("type", "")
        if rtype in ("analysis", "list"):
            # Has data — stream AI analysis
            stock_data = result.get("data") if rtype == "analysis" else {"stocks": result.get("data", [])}
        else:
            # Complete response — return now
            resp = result["msg"]
            chat_history.append({"role": "assistant", "content": resp})
            if user:
                auth.save_chat(user["id"], "assistant", resp, msg_type=rtype, ticker=result.get("ticker"))
            return {
                "ok": True, "message": resp, "stream": False,
                "type": rtype, "ticker": result.get("ticker"),
                "trade_signal": result.get("trade_signal"),
                "autopilot": autopilot_task is not None and not autopilot_task.done(),
            }
    elif result and result.get("ok") and result.get("type") == "analysis":
        stock_data = result.get("data")
    elif result and result.get("error"):
        resp = f"⚠️ {result['error']}"
        chat_history.append({"role": "assistant", "content": resp})
        return {"ok": True, "message": resp, "stream": False, "type": "chat"}

    # Stream AI response
    async def generate():
        import queue, threading
        full_response = ""
        q = queue.Queue()

        def _run_stream():
            try:
                for chunk in engine.ai_response_stream(user_msg, stock_data, chat_history, "US"):
                    q.put(chunk)
            except Exception as e:
                q.put(f"⚠️ {str(e)[:80]}")
            q.put(None)

        t = threading.Thread(target=_run_stream, daemon=True)
        t.start()

        while True:
            try:
                chunk = q.get(timeout=0.05)
            except queue.Empty:
                await asyncio.sleep(0.01)
                continue
            if chunk is None:
                break
            full_response += chunk
            yield f"data: {json.dumps({'chunk': chunk})}\n\n"

        t.join(timeout=5)

        chat_history.append({"role": "assistant", "content": full_response})
        if user:
            auth.save_chat(user["id"], "assistant", full_response,
                          msg_type=result.get("type", "chat") if result else "chat",
                          ticker=result.get("ticker") if result else None)

        yield f"data: {json.dumps({'done': True, 'type': result.get('type') if result else 'chat', 'ticker': result.get('ticker') if result else None, 'trade_signal': result.get('trade_signal') if result else None})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream",
                            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.post("/api/chat")
async def chat(msg: ChatMessage, authorization: str = Header(None)):
    """Process a chat message through Paula's brain."""
    global autopilot_task, autopilot_owner_id
    user_msg = msg.message.strip()
    if not user_msg:
        return {"ok": False, "error": "Empty message"}

    # Get user if authenticated
    user = _get_user(authorization)
    user_id = user["id"] if user else 0
    if user:
        auth.save_chat(user["id"], "user", user_msg)

    # Per-user isolated chat history
    chat_history = _get_user_history(user_id)
    chat_history.append({"role": "user", "content": user_msg})

    # Route the message
    intent = engine.route(user_msg)

    # Autopilot — admin only
    if intent.get("type") == "autopilot":
        if not user or user.get("email", "").lower() != ADMIN_EMAIL:
            return {"ok": True, "message": "Autopilot is restricted to admin accounts.", "type": "chat", "autopilot": False}
        if not autopilot_task or autopilot_task.done():
            autopilot_owner_id = user_id
            autopilot_task = asyncio.create_task(_autopilot_loop())
        return {"ok": True, "message": "Autopilot activated.", "type": "trade", "autopilot": True}

    if intent.get("type") == "stop_autopilot":
        if not user or user.get("email", "").lower() != ADMIN_EMAIL:
            return {"ok": True, "message": "Autopilot is restricted to admin accounts.", "type": "chat", "autopilot": False}
        if autopilot_task and not autopilot_task.done():
            autopilot_task.cancel()
            autopilot_task = None
            autopilot_owner_id = None
        return {"ok": True, "message": "Autopilot stopped.", "type": "trade", "autopilot": False}

    # Run in thread pool since engine functions are blocking
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, engine.execute, intent)

    if result and result.get("ok"):
        resp = result.get("msg", "")
        rtype = result.get("type", "")

        if rtype == "analysis":
            if not resp:
                # AI generates analysis — but we prepend real data header
                ai_text = await loop.run_in_executor(None, engine.ai_response, user_msg, result.get("data"), chat_history, "US")
                # Build factual header from data
                data = result.get("data", {})
                ticker = result.get("ticker", "")
                if data and ticker:
                    price = data.get("price", 0)
                    change_pct = data.get("change_pct", 0)
                    arrow = "▲" if change_pct >= 0 else "▼"
                    resp = ai_text
                    # Validate: if AI mentions a price that's >20% off real price, fix it
                    if price > 0:
                        import re
                        def fix_prices(text, real_price, ticker_name):
                            """Replace hallucinated prices with real ones."""
                            def replacer(match):
                                mentioned = float(match.group(1).replace(",", ""))
                                # If mentioned price is >20% off real price, it's hallucinated
                                if abs(mentioned - real_price) / real_price > 0.20:
                                    return f"${real_price:.2f}"
                                return match.group(0)
                            return re.sub(r'\$(\d{1,5}(?:,\d{3})*\.?\d{0,2})', replacer, text)
                        resp = fix_prices(resp, price, ticker)
                else:
                    resp = ai_text
        elif rtype == "list":
            # Send list data to AI for real analysis instead of just showing a table
            list_data = result.get("data", [])
            resp = await loop.run_in_executor(None, engine.ai_response, user_msg, {"list_title": result.get("title", ""), "stocks": list_data}, chat_history, "US")
        elif not resp:
            # Try to extract tickers from message AND history to provide context
            _chat_data = {}
            try:
                import re as _re
                # Scan current message + last 6 history items for tickers
                _all_text = user_msg + " " + " ".join(h.get("content", "") for h in chat_history[-6:])
                _found_tickers = list(set(_re.findall(r'\b([A-Z]{1,5})\b', _all_text)))
                # Filter to known tickers (avoid matching random words like "THE", "AND")
                _known = set(["AAPL","MSFT","NVDA","GOOGL","AMZN","META","TSLA","AMD","NFLX","SPY","QQQ","JPM","V","BA","HD","CRM","AVGO","LLY","COST","WMT","DIS","XOM","CVX","GS","BAC","INTC","PYPL","COIN","PLTR","UBER","SHOP","SOFI","MARA","CELH","NIO","RIVN","F","GM","KO","PEP","NKE","ADBE","CSCO","IBM","QCOM","TXN","MU","MA","SQ","HOOD","MS","C","WFC","UNH","JNJ","MRK","PFE","ABBV","TGT","SBUX","MCD","CMG","DASH","BKNG","ABNB","LULU","SLB","COP","CAT","GE","HON","DE","UPS","FDX","LMT","SNAP","RBLX","DKNG","MSTR","RIOT","NET","DDOG","SNOW","PANW","CRWD","TTD","SMCI","ARM","IONQ","TMDX","DUOL","FCEL","ONON","HIMS","CAVA","TOST","ELF","LCID","DELL","ROKU","NOW","INTU","PINS","CVNA","MRNA","BRK-B","RKLB","AXON"])
                _valid = [t for t in _found_tickers if t in _known][:5]  # max 5 lookups
                if _valid:
                    _multi = {}
                    for _vt in _valid:
                        try:
                            _vd = engine.fetch_full(_vt)
                            if _vd and _vd.get("price"):
                                _multi[_vt] = {"price": _vd["price"], "change_pct": _vd.get("change_pct", 0), "name": _vd.get("name", _vt)}
                        except: pass
                    if _multi:
                        _chat_data = {"stocks": _multi, "note": "Use ONLY these exact prices"}
                    elif len(_valid) == 1:
                        _chat_data = engine.fetch_full(_valid[0]) or {}
            except Exception:
                pass
            resp = await loop.run_in_executor(None, engine.ai_response, user_msg, _chat_data if _chat_data else None, chat_history, "US")
    elif result and result.get("error"):
        resp = f"⚠️ {result['error']}"
    else:
        # Final fallthrough — try to find context from history
        _fall_data = None
        try:
            for h in reversed(chat_history[-6:]):
                import re as _re
                _found = _re.findall(r'\b([A-Z]{1,5})\b', h.get("content", ""))
                for _ft in _found:
                    if _ft in ["AAPL","MSFT","NVDA","GOOGL","AMZN","META","TSLA","AMD","NFLX","SPY","QQQ","JPM","V","BA","HD","CRM","AVGO","LLY","COST","WMT","DIS","XOM","CVX","GS","BAC","INTC","PYPL","COIN","PLTR","UBER","SHOP","SOFI","MARA","CELH","NIO","RIVN","F","GM","KO","PEP","NKE","ADBE","CSCO","IBM","QCOM","TXN","MU","AMAT","LRCX","KLAC","MA","SQ","HOOD","AFRM","MS","C","WFC","SCHW","BLK","UNH","JNJ","MRK","PFE","ABBV","TMO","TGT","NKE","SBUX","MCD","CMG","DASH","BKNG","ABNB","LULU","ETSY","SLB","COP","CAT","GE","HON","DE","UPS","FDX","LMT","SNAP","RBLX","DKNG","MSTR","RIOT","NET","DDOG","SNOW","MDB","PANW","CRWD","ZS","TTD","HUBS","SMCI","ARM","IONQ","TMDX","DUOL","FCEL","ONON","HIMS","CAVA","TOST","BROS","ELF","LCID","LI","DELL","ROKU","ZM","DOCU","NOW","INTU","WDAY","PINS","MTCH","CVNA","AMT","PLD","O","T","VZ","TMUS","NEE","NEM","GOLD","FCX","NUE","MRNA","BIIB","BRK-B","RKLB","AXON","SOXX","DIA","ARKK","IWM","XLF","XLE"]:
                        _fall_data = engine.fetch_full(_ft)
                        break
                if _fall_data:
                    break
        except Exception:
            pass
        resp = await loop.run_in_executor(None, engine.ai_response, user_msg, _fall_data, chat_history, "US")

    # ── Price validation: fix any hallucinated prices in AI responses ──
    if resp and result:
        _real_price = 0
        _rd = result.get("data") or {}
        if isinstance(_rd, dict):
            _real_price = _rd.get("price", 0)
        if _real_price and _real_price > 0:
            import re as _pre
            def _fix_ai_prices(text, rp):
                def _repl(match):
                    try:
                        mentioned = float(match.group(1).replace(",", ""))
                        if mentioned > 1 and abs(mentioned - rp) / rp > 0.25:
                            return f"${rp:.2f}"
                    except: pass
                    return match.group(0)
                return _pre.sub(r'\$(\d{1,5}(?:,\d{3})*\.?\d{0,2})', _repl, text)
            resp = _fix_ai_prices(resp, _real_price)

    chat_history.append({"role": "assistant", "content": resp})
    _trim_history(user_id)

    # Save assistant response for logged-in users
    if user:
        auth.save_chat(user["id"], "assistant", resp,
                      msg_type=result.get("type", "chat") if result else "chat",
                      ticker=result.get("ticker") if result else None)

    response = {
        "ok": True,
        "message": resp,
        "type": result.get("type") if result else "chat",
        "ticker": result.get("ticker") if result else None,
        "tickers": [],
        "trade_signal": result.get("trade_signal") if result else None,
        "signal_data": result.get("signal_data") if result else None,
        "table": result.get("data") if result and result.get("type") == "list" else None,
        "autopilot": autopilot_task is not None and not autopilot_task.done(),
    }

    # Extract tickers for charts
    if result:
        rtype = result.get("type", "")
        if result.get("tickers"):
            # Direct tickers array from stock_ideas, etc
            response["tickers"] = result["tickers"][:6]
        elif rtype == "list" and result.get("data"):
            # Pull tickers from list results (top gainers, etc)
            response["tickers"] = [r.get("Ticker", r.get("ticker", "")) for r in result["data"] if r.get("Ticker") or r.get("ticker")][:6]
        elif result.get("ticker"):
            response["tickers"] = [result["ticker"]]

    # Also scan the AI response for mentioned tickers
    if resp and not response["tickers"]:
        import re
        # Find uppercase 1-5 letter words that look like tickers
        found = re.findall(r'\b([A-Z]{1,5})\b', resp)
        known = set()
        try:
            known = set(engine.FULL_UNIVERSE)
        except Exception:
            pass
        if known:
            response["tickers"] = [t for t in dict.fromkeys(found) if t in known][:6]

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
    last_hourly_update = -1  # track which hour we last sent status
    last_milestone_reset = ""

    while True:
        try:
            is_open, status_msg = engine._market_is_open()

            # ── Pre-market scan: run once between 8:15-8:30 AM CT ──
            et = ZoneInfo("US/Eastern")
            now_et = datetime.now(et)
            ct_hour = (now_et.hour - 1) % 24  # rough CT

            if now_et.weekday() < 5 and now_et.hour == 9 and 15 <= now_et.minute <= 29:
                today = now_et.strftime("%Y-%m-%d")
                if not hasattr(engine.st.session_state, "premarket_done") or engine.st.session_state.get("premarket_done") != today:
                    try:
                        loop = asyncio.get_event_loop()
                        pm_result = await loop.run_in_executor(None, engine.premarket_scan)
                        await broadcast("autopilot", {"status": "scanned", "log": pm_result.get("log", [])})
                        await send_phone_notification(
                            "🌅 Pre-Market Scan",
                            f"Watchlist ready: {len(pm_result.get('watchlist', []))} stocks",
                            priority="low"
                        )
                    except Exception:
                        pass

            # ── Reset daily flags ──
            today_str = now_et.strftime("%Y-%m-%d")
            if today_str != last_milestone_reset:
                last_milestone_reset = today_str
                for m in [100, 200, 500]:
                    setattr(engine, f"_notified_{m}", False)

            # ── Hourly status update (during market hours) ──
            if is_open and now_et.hour != last_hourly_update:
                last_hourly_update = now_et.hour
                try:
                    acc = engine.alpaca_account() or {}
                    positions = engine.alpaca_positions() or []
                    equity = acc.get("equity", 0)
                    daily_pnl = acc.get("daily_pnl", 0)
                    pnl_sign = "+" if daily_pnl >= 0 else ""
                    pos_count = len(positions)

                    # Build position summary
                    pos_summary = ""
                    if positions:
                        pos_names = [p.get("ticker", "?") for p in positions[:4]]
                        pos_summary = f" | Holding: {', '.join(pos_names)}"

                    ct_time = now_et.strftime("%-I:%M %p")
                    await send_phone_notification(
                        f"📊 Paula Status — {ct_time}",
                        f"Equity: ${equity:,.0f} | Today: {pnl_sign}${abs(daily_pnl):,.0f} ({pnl_sign}{acc.get('daily_pnl_pct', 0):.2f}%) | {pos_count} positions{pos_summary}",
                        priority="low"
                    )
                except Exception:
                    pass

            if not is_open:
                # ── EOD recap notification ──
                if now_et.hour == 16 and now_et.minute < 5 and last_hourly_update != 160:
                    last_hourly_update = 160
                    try:
                        acc = engine.alpaca_account() or {}
                        daily_pnl = acc.get("daily_pnl", 0)
                        pnl_sign = "+" if daily_pnl >= 0 else ""
                        emoji = "🟢" if daily_pnl >= 0 else "🔴"
                        await send_phone_notification(
                            f"{emoji} Market Closed — Daily Recap",
                            f"P&L: {pnl_sign}${abs(daily_pnl):,.0f} ({pnl_sign}{acc.get('daily_pnl_pct', 0):.2f}%) | Equity: ${acc.get('equity', 0):,.0f} | 0 positions",
                            priority="default"
                        )
                    except Exception:
                        pass

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

            # Send detailed phone notification if trades were made
            if buys > 0 or sells > 0 or shorts > 0:
                # Log trades from autopilot
                for line in result.get("log", []):
                    if "BOUGHT" in line or "SHORTED" in line or "SOLD" in line or "COVERED" in line:
                        parts_l = line.split()
                        ticker_l = parts_l[1] if len(parts_l) > 1 else "?"
                        action_l = "buy" if "BOUGHT" in line else "sell" if "SOLD" in line else "short" if "SHORTED" in line else "cover"
                        # Extract price if present
                        price_l = 0
                        for p in parts_l:
                            if p.startswith("$"):
                                try: price_l = float(p.replace("$","").replace(",",""))
                                except: pass
                        log_trade(action_l, ticker_l, price=price_l, extra={"source": "autopilot", "score": result.get("score", 0)})
                parts = []
                if buys: parts.append(f"📈 {buys} bought")
                if shorts: parts.append(f"📉 {shorts} shorted")
                if sells: parts.append(f"💰 {sells} closed")
                try:
                    acc = engine.alpaca_account() or {}
                    pnl = acc.get("daily_pnl", 0)
                    pnl_sign = "+" if pnl >= 0 else ""
                    pos_count = len(engine.alpaca_positions() or [])
                    detail = f"{' | '.join(parts)} | Day: {pnl_sign}${abs(pnl):,.0f} | {pos_count} open"
                except Exception:
                    detail = " | ".join(parts)

                await send_phone_notification("Paula Trade", detail, priority="default")

            # P&L milestone alerts
            try:
                acc = engine.alpaca_account() or {}
                daily_pnl = acc.get("daily_pnl", 0)
                # Check milestones: ±$100, ±$200, ±$500
                for milestone in [500, 200, 100]:
                    milestone_key = f"_notified_{milestone}"
                    if abs(daily_pnl) >= milestone and not getattr(engine, milestone_key, False):
                        setattr(engine, milestone_key, True)
                        emoji = "🎉" if daily_pnl > 0 else "⚠️"
                        await send_phone_notification(
                            f"{emoji} P&L Alert: {'+'if daily_pnl>0 else ''}{daily_pnl:.0f}",
                            f"{'Great day!' if daily_pnl > 0 else 'Consider stopping.'} Equity: ${acc.get('equity', 0):,.0f}",
                            priority="high" if milestone >= 200 else "default"
                        )
                        break
            except Exception:
                pass

            # Notify about interesting setups found (even if not traded)
            scanned = result.get("scanned", 0)
            opportunities = result.get("opportunities", 0)
            if opportunities > 0 and buys == 0 and sells == 0 and shorts == 0:
                await send_phone_notification(
                    f"👀 {opportunities} setups found",
                    f"Scanned {scanned} stocks. Setups didn't meet entry criteria yet.",
                    priority="low"
                )

        except asyncio.CancelledError:
            break
        except asyncio.CancelledError:
            raise  # Let cancellation work
        except Exception as e:
            await broadcast("autopilot", {"status": "error", "error": str(e)[:200]})
            await send_phone_notification("⚠️ Paula Error", str(e)[:80], priority="high")

        try:
            await asyncio.sleep(5 * 60)  # 5 minutes
        except asyncio.CancelledError:
            break  # Clean exit on stop


@app.post("/api/autopilot/start")
async def start_autopilot(authorization: str = Header(None)):
    """Start the autopilot background loop. Admin only."""
    global autopilot_task, autopilot_owner_id
    user = _get_user(authorization)
    if not user or user.get("email", "").lower() != ADMIN_EMAIL:
        return {"ok": False, "error": "Autopilot access restricted"}
    if autopilot_task and not autopilot_task.done():
        return {"ok": True, "message": "Autopilot already running"}

    autopilot_owner_id = user["id"]
    autopilot_task = asyncio.create_task(_autopilot_loop())
    await broadcast("autopilot", {"status": "started"})
    await send_phone_notification("🟢 Autopilot Started", "Paula is now scanning for trades every 5 minutes", priority="default")
    return {"ok": True, "message": "Autopilot started"}


@app.post("/api/autopilot/stop")
async def stop_autopilot(authorization: str = Header(None)):
    """Stop the autopilot. Admin only."""
    global autopilot_task, autopilot_owner_id
    user = _get_user(authorization)
    if not user or user.get("email", "").lower() != ADMIN_EMAIL:
        return {"ok": False, "error": "Autopilot access restricted"}
    if autopilot_task and not autopilot_task.done():
        autopilot_task.cancel()
        autopilot_task = None
        autopilot_owner_id = None
    await broadcast("autopilot", {"status": "stopped"})
    try:
        acc = engine.alpaca_account() or {}
        pnl = acc.get("daily_pnl", 0)
        pnl_sign = "+" if pnl >= 0 else ""
        await send_phone_notification("🔴 Autopilot Stopped", f"Day so far: {pnl_sign}${abs(pnl):,.0f} | Equity: ${acc.get('equity', 0):,.0f}", priority="default")
    except Exception:
        await send_phone_notification("🔴 Autopilot Stopped", "Paula is no longer trading", priority="default")
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


# ═══ Admin Panel ═══
ADMIN_EMAIL = "parjan.d@icloud.com"  # Only this email can access admin

@app.get("/api/admin/users")
async def admin_list_users(authorization: str = Header(None)):
    user = _get_user(authorization)
    if not user or user.get("email", "").lower() != ADMIN_EMAIL:
        return {"ok": False, "error": "Unauthorized"}
    db = auth._get_db()
    try:
        rows = db.execute("SELECT id, username, email, created_at, last_login FROM users ORDER BY id DESC").fetchall()
        users = [{"id": r["id"], "username": r["username"], "email": r["email"],
                  "created_at": r["created_at"], "last_login": r["last_login"]} for r in rows]
        # Get session counts
        for u in users:
            u["messages"] = db.execute("SELECT COUNT(*) FROM chat_history WHERE user_id = ?", (u["id"],)).fetchone()[0]
        return {"ok": True, "users": users, "total": len(users),
                "autopilot_owner": autopilot_owner_id}
    finally:
        db.close()


@app.delete("/api/admin/users/{user_id}")
async def admin_delete_user(user_id: int, authorization: str = Header(None)):
    user = _get_user(authorization)
    if not user or user.get("email", "").lower() != ADMIN_EMAIL:
        return {"ok": False, "error": "Unauthorized"}
    if user_id == user["id"]:
        return {"ok": False, "error": "Cannot delete yourself"}
    db = auth._get_db()
    try:
        db.execute("DELETE FROM chat_history WHERE user_id = ?", (user_id,))
        db.execute("DELETE FROM user_settings WHERE user_id = ?", (user_id,))
        db.execute("DELETE FROM users WHERE id = ?", (user_id,))
        db.commit()
        _user_sessions.pop(user_id, None)
        return {"ok": True}
    finally:
        db.close()


@app.post("/api/admin/clear-all")
async def admin_clear_all(authorization: str = Header(None)):
    """Clear ALL users except admin. Nuclear option."""
    user = _get_user(authorization)
    if not user or user.get("email", "").lower() != ADMIN_EMAIL:
        return {"ok": False, "error": "Unauthorized"}
    db = auth._get_db()
    try:
        db.execute("DELETE FROM chat_history WHERE user_id != ?", (user["id"],))
        db.execute("DELETE FROM user_settings WHERE user_id != ?", (user["id"],))
        db.execute("DELETE FROM users WHERE id != ?", (user["id"],))
        db.commit()
        # Clear all sessions except admin
        for uid in list(_user_sessions.keys()):
            if uid != user["id"]:
                _user_sessions.pop(uid, None)
        remaining = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        return {"ok": True, "remaining": remaining}
    finally:
        db.close()


@app.get("/api/admin/stats")
async def admin_stats(authorization: str = Header(None)):
    user = _get_user(authorization)
    if not user or user.get("email", "").lower() != ADMIN_EMAIL:
        return {"ok": False, "error": "Unauthorized"}
    db = auth._get_db()
    try:
        total_users = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        total_messages = db.execute("SELECT COUNT(*) FROM chat_history").fetchone()[0]
        active_sessions = len(_user_sessions)
        return {"ok": True, "total_users": total_users, "total_messages": total_messages,
                "active_sessions": active_sessions,
                "autopilot_active": autopilot_task is not None and not autopilot_task.done(),
                "autopilot_owner": autopilot_owner_id}
    finally:
        db.close()
