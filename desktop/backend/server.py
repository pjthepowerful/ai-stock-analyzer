"""
Paula Desktop — FastAPI Backend
Wraps the trading engine as a local API server.
"""

import asyncio
import functools
import json
import time
import os
from datetime import datetime
from zoneinfo import ZoneInfo
from contextlib import asynccontextmanager
from typing import Optional

# ── Load .env BEFORE importing the engine ──────────────────────────────────
# Keys live in a gitignored .env file so they never need to be exported by
# hand (and never end up in shell history). We look in the backend dir first,
# then the repo root, so it works regardless of where the server is launched.
try:
    from dotenv import load_dotenv
    _here = os.path.dirname(os.path.abspath(__file__))
    for _env_path in (os.path.join(_here, ".env"),
                      os.path.abspath(os.path.join(_here, "..", "..", ".env"))):
        if os.path.exists(_env_path):
            load_dotenv(_env_path)
            print(f"[env] loaded {_env_path}", flush=True)
            break
except Exception as _e:
    print(f"[env] dotenv not loaded: {_e}", flush=True)

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
ADMIN_EMAIL = "parjan.d@icloud.com"  # Only this email gets admin (admin panel, etc.)
AUTOPILOT_EMAILS = {"parjan.d@icloud.com", "pinakin.d@moftmail.com"}  # Emails allowed to run autopilot

# Email-dependent auth features (2FA + signup email verification). OFF until a
# domain is verified in Resend — the sandbox onboarding@resend.dev can only mail
# the Resend account owner, so codes never reach testers. Flip to "1" (env
# EMAIL_AUTH_ENABLED=1) once a real sending domain is set up. Password reset is
# also gated on this since it relies on the same email delivery.
EMAIL_AUTH_ENABLED = os.environ.get("EMAIL_AUTH_ENABLED", "0") == "1"

def _can_autopilot(user) -> bool:
    return bool(user) and user.get("email", "").lower() in AUTOPILOT_EMAILS


def _friendly_error(err: str) -> str:
    """Turn a raw/technical error into something a person can act on."""
    e = (err or "").lower()
    if "no data" in e or "delisted" in e or "symbol may be" in e:
        return ("I couldn't pull data for that ticker. It might be misspelled, "
                "newly listed, delisted, or not a US-listed stock. Double-check "
                "the symbol and try again.")
    if "rate" in e or "too many" in e:
        return ("The market data source is busy right now (rate-limited). Give it "
                "a few seconds and try again — it usually clears quickly.")
    if "alpaca" in e or "connect" in e or "credential" in e or "unauthorized" in e:
        return ("I couldn't reach your brokerage account. Check that your Alpaca "
                "API keys are set correctly in Settings → Connections.")
    if "buying power" in e or "insufficient" in e:
        return ("That order needs more buying power than the account has. Try a "
                "smaller share count.")
    if "timeout" in e or "timed out" in e:
        return ("That took too long and timed out. The data source may be slow "
                "right now — please try again.")
    # Fallback: show the original but cleaned up.
    return f"Something went wrong: {err}"


def _taste_analysis(result: dict) -> dict:
    """Free users get a *taste* of a deep stock analysis: the ticker, current
    price, the signal (BUY/SELL/etc) and the score — but NOT the full data dict,
    chart, entry/stop/target levels, or detailed breakdown (those stay Plus).
    Returns a trimmed chat response with a flag so the frontend shows a
    'see the full analysis with Plus' prompt under it."""
    data = result.get("data") or {}
    ticker = (result.get("ticker") or data.get("ticker") or "").upper()
    price = data.get("price")
    signal = data.get("action") or data.get("signal") or (data.get("trade") or {}).get("side")
    score = data.get("score")
    bits = []
    if price is not None:
        try:
            bits.append(f"**{ticker}** is at ${float(price):,.2f}")
        except Exception:
            bits.append(f"**{ticker}**")
    else:
        bits.append(f"**{ticker}**")
    if signal:
        bits.append(f"current signal: **{signal}**")
    if score is not None:
        bits.append(f"score **{score}/100**")
    teaser = " · ".join(bits)
    msg = (
        f"{teaser}\n\nThat's the quick read. The full breakdown — setup scores, "
        f"entry/stop/target levels, the chart, and Paula's reasoning — is part of "
        f"Paula Plus."
    )
    return {
        "ok": True, "stream": False, "type": "taste",
        "taste": True, "plus_upsell": True,
        "ticker": ticker, "message": msg,
    }

# Shared set of recognizable tickers (used for chat data + news lookups)
KNOWN_TICKERS = set(["AAPL","MSFT","NVDA","GOOGL","AMZN","META","TSLA","AMD","NFLX","SPY","QQQ","JPM","V","BA","HD","CRM","AVGO","LLY","COST","WMT","DIS","XOM","CVX","GS","BAC","INTC","PYPL","COIN","PLTR","UBER","SHOP","SOFI","MARA","CELH","NIO","RIVN","F","GM","KO","PEP","NKE","ADBE","CSCO","IBM","QCOM","TXN","MU","MA","SQ","HOOD","MS","C","WFC","UNH","JNJ","MRK","PFE","ABBV","TGT","SBUX","MCD","CMG","DASH","BKNG","ABNB","LULU","SLB","COP","CAT","GE","HON","DE","UPS","FDX","LMT","SNAP","RBLX","DKNG","MSTR","RIOT","NET","DDOG","SNOW","PANW","CRWD","TTD","SMCI","ARM","IONQ","TMDX","DUOL","FCEL","ONON","HIMS","CAVA","TOST","ELF","LCID","DELL","ROKU","NOW","INTU","PINS","CVNA","MRNA","BRK-B","RKLB","AXON"])
autopilot_task: Optional[asyncio.Task] = None
connected_clients: list[WebSocket] = []
# Per-user session isolation — NO global shared state
_user_sessions: dict[int, list[dict]] = {}  # {user_id: [chat messages]}
_session_lock = asyncio.Lock()
autopilot_owner_id: Optional[int] = None  # Only one user can own autopilot

# Per-user in-flight scan tasks, so a scan can be cancelled when the user
# navigates away / closes the tab (don't burn server resources for nobody).
_active_scans: dict = {}

# High-conviction alert dedup: ticker -> date last alerted. Prevents re-alerting
# the same 90+ stock every 5-min cycle; it can re-alert on a new day.
_alerted_today: dict = {}

# ── Autopilot persistence ──
# Autopilot runs as a server-side background task, so it keeps trading even when
# the user closes their laptop/browser. But an in-memory task is lost if the
# backend restarts (deploy, crash, host bounce). We persist the on/off state +
# owner to a small file and auto-resume on startup, so autopilot survives
# restarts and genuinely runs unattended.
_AP_STATE_FILE = os.path.join(os.environ.get("DB_DIR", os.path.dirname(os.path.abspath(__file__))), "autopilot_state.json")

def _save_autopilot_state(on: bool, owner_id: Optional[int]):
    try:
        with open(_AP_STATE_FILE, "w") as f:
            json.dump({"on": bool(on), "owner_id": owner_id}, f)
    except Exception as e:
        print(f"  ⚠️ Could not save autopilot state: {e}")

def _load_autopilot_state() -> dict:
    try:
        with open(_AP_STATE_FILE) as f:
            return json.load(f)
    except Exception:
        return {"on": False, "owner_id": None}

# ── Maintenance mode ── (admin-only toggle; blocks the app for everyone but admin)
_MAINT_FILE = os.path.join(os.environ.get("DB_DIR", os.path.dirname(os.path.abspath(__file__))), "maintenance.json")
def _maint_state() -> dict:
    try:
        with open(_MAINT_FILE) as f:
            return json.load(f)
    except Exception:
        return {"on": False, "message": ""}
def _set_maint(on: bool, message: str = ""):
    try:
        with open(_MAINT_FILE, "w") as f:
            json.dump({"on": bool(on), "message": message or ""}, f)
    except Exception:
        pass

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

    # Auto-resume autopilot if it was running before a restart (deploy/crash/host
    # bounce). This is what makes autopilot genuinely unattended — it survives the
    # backend going down and comes back trading on its own.
    global autopilot_task, autopilot_owner_id
    try:
        _ap = _load_autopilot_state()
        if _ap.get("on"):
            autopilot_owner_id = _ap.get("owner_id")
            autopilot_task = _spawn_autopilot()
            print(f"  ✓ Auto-resumed autopilot (owner {autopilot_owner_id}) after restart")
    except Exception as e:
        print(f"  ⚠️ Could not auto-resume autopilot: {e}")

    yield
    print("🔴 Paula backend stopping...")
    eod_task.cancel()
    if autopilot_task and not autopilot_task.done():
        autopilot_task.cancel()


app = FastAPI(title="Paula", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    # Can't use allow_origins=["*"] together with allow_credentials=True — the
    # browser requires a SPECIFIC origin to be echoed back when credentials are
    # allowed, so "*" results in no Access-Control-Allow-Origin header at all
    # (which is the CORS error). Use a regex that matches our real frontends:
    # any *.vercel.app deployment + localhost for dev.
    allow_origin_regex=r"https://([a-z0-9-]+\.)*vercel\.app|http://localhost(:\d+)?|https://localhost(:\d+)?",
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
    # Echo the request origin so a 500 surfaces as the real error, not a
    # misleading CORS failure (the CORS middleware doesn't always wrap responses
    # produced by a custom exception handler).
    origin = request.headers.get("origin", "")
    import re as _cors_re
    allowed = bool(_cors_re.fullmatch(
        r"https://([a-z0-9-]+\.)*vercel\.app|http://localhost(:\d+)?|https://localhost(:\d+)?",
        origin or "",
    ))
    headers = {}
    if allowed:
        headers = {
            "Access-Control-Allow-Origin": origin,
            "Access-Control-Allow-Credentials": "true",
        }
    return JSONResponse(
        status_code=200,
        content={"ok": False, "error": str(exc)[:200]},
        headers=headers,
    )


# ── Models ──

class ChatMessage(BaseModel):
    message: str
    history: Optional[list] = None  # per-chat history from the frontend (each chat independent)

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
    # Tag autopilot/trade events with the account that owns autopilot, so each
    # client can decide whether to play sounds (only the owning ACCOUNT should
    # hear them — works across all of that account's sessions/devices).
    if event in ("autopilot", "trade") and isinstance(data, dict) and "ap_owner_id" not in data:
        data = {**data, "ap_owner_id": autopilot_owner_id}
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


def _make_scan_progress_cb(loop):
    """Build a progress callback safe to call from the scan's worker thread.
    It schedules a websocket broadcast onto the main event loop. Throttled so a
    fast scan doesn't spam the socket. Returns None if there's no loop."""
    if loop is None:
        return None
    _last = {"pct": -1}
    def _cb(done, total, phase="scanning"):
        try:
            pct = int(done / total * 100) if total else 0
            # Only push when the percent actually advances (avoid socket spam).
            if pct <= _last["pct"]:
                return
            _last["pct"] = pct
            payload = {"done": int(done), "total": int(total), "pct": pct, "phase": phase}
            asyncio.run_coroutine_threadsafe(broadcast("scan_progress", payload), loop)
        except Exception:
            pass
    return _cb

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
            try:
                msg = json.loads(data)
            except Exception:
                continue
            if msg.get("type") == "ping":
                await websocket.send_text(json.dumps({"event": "pong"}))
    except Exception:
        # Any disconnect/error path — fall through to cleanup.
        pass
    finally:
        # ALWAYS remove the socket so connected_clients can't grow unbounded
        # (a leak here is a slow OOM as clients reconnect over and over).
        if websocket in connected_clients:
            try:
                connected_clients.remove(websocket)
            except ValueError:
                pass


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

class ForgotRequest(BaseModel):
    email: str

class ResetRequest(BaseModel):
    token: str
    password: str

def _get_user(authorization: str = Header(None)):
    """Extract user from Authorization header. Always fetches email from DB.
    Also applies the user's OWN Alpaca creds for this request (per-user trading);
    falls back to the shared account when the user hasn't set their own keys."""
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
        # Apply this user's Alpaca keys for the request (per-account trading).
        try:
            creds = auth.get_user_alpaca_creds(user["id"])
            engine.set_alpaca_creds(creds.get("key_id"), creds.get("secret"))
        except Exception:
            engine.set_alpaca_creds(None, None)
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
    if result.get("ok") and EMAIL_AUTH_ENABLED:
        # Send a 6-digit email verification code (only when email is configured).
        try:
            code = auth.create_email_code(req.email.strip().lower(), "verify")
            if code:
                _send_code_email(req.email.strip().lower(), code, "verify")
            result["needs_verification"] = True
            result["email"] = req.email.strip().lower()
        except Exception:
            pass
    return result

@app.post("/api/auth/login")
async def login(req: AuthRequest):
    # Login is email-only (validated in auth.login)
    identifier = req.email or req.username
    if not identifier:
        return {"ok": False, "error": "Email is required"}
    result = auth.login(identifier.strip(), req.password)
    if result.get("ok") and EMAIL_AUTH_ENABLED:
        # 2FA: password was correct — but require an emailed code before issuing
        # the real session token. Withhold the token; send a code instead.
        email = (result.get("user", {}) or {}).get("email", "").strip().lower()
        if email:
            try:
                code = auth.create_email_code(email, "2fa")
                sent = False
                if code:
                    sent = _send_code_email(email, code, "2fa")
                if sent:
                    return {"ok": True, "needs_2fa": True, "email": email}
                # SAFETY VALVE: if the code email could NOT be sent (e.g. Resend
                # misconfigured), do NOT lock the user out — the password was
                # already verified, so issue the session directly and flag it.
                print(f"[2fa] email NOT sent for {email} — falling back to direct login (password was valid)", flush=True)
                direct = auth.issue_token_for_email(email)
                direct["twofa_skipped"] = True
                return direct
            except Exception as e:
                print(f"[2fa] error, falling back to direct login: {e}", flush=True)
                return auth.issue_token_for_email(email)
    return result


@app.post("/api/auth/verify-code")
async def verify_code(req: AuthRequest):
    """Verify a 6-digit code for signup verification or 2FA login.
    Expects email, code (in password field), and purpose (in username field)."""
    email = (req.email or "").strip().lower()
    code = (req.password or "").strip()
    purpose = (req.username or "2fa").strip()
    if purpose not in ("verify", "2fa"):
        purpose = "2fa"
    vr = auth.verify_email_code(email, code, purpose)
    if not vr.get("ok"):
        return vr
    if purpose == "2fa":
        # Code good — now issue the real session token.
        return auth.issue_token_for_email(email)
    return {"ok": True, "verified": True}


@app.post("/api/auth/resend-code")
async def resend_code(req: AuthRequest):
    email = (req.email or "").strip().lower()
    purpose = (req.username or "2fa").strip()
    if purpose not in ("verify", "2fa"):
        purpose = "2fa"
    if not email:
        return {"ok": False, "error": "Email required"}
    try:
        code = auth.create_email_code(email, purpose)
        if code:
            _send_code_email(email, code, purpose)
    except Exception:
        pass
    return {"ok": True, "message": "A new code has been sent."}


# ── Password reset ───────────────────────────────────────────────────────────
# To enable real emails: set RESEND_API_KEY (https://resend.com) and FRONTEND_URL.
# Without a key, the reset link is printed to the server log (dev mode) so the
# flow is fully testable locally.
FRONTEND_URL = os.environ.get("FRONTEND_URL", "https://paula-seven.vercel.app").rstrip("/")


def _send_reset_email(to_email: str, token: str) -> bool:
    """Send a password-reset email. Falls back to logging in dev."""
    reset_link = f"{FRONTEND_URL}/?reset={token}"
    api_key = os.environ.get("RESEND_API_KEY", "")
    from_addr = os.environ.get("RESET_FROM_EMAIL", "Paula <onboarding@resend.dev>")
    if not api_key:
        # Dev mode — no email provider configured.
        print(f"[password-reset] (no RESEND_API_KEY set) reset link for {to_email}:\n  {reset_link}", flush=True)
        return False
    try:
        import requests as r
        resp = r.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "from": from_addr,
                "to": [to_email],
                "subject": "Reset your Paula password",
                "html": (
                    "<p>You requested a password reset for your Paula account.</p>"
                    f'<p><a href="{reset_link}">Click here to set a new password</a>. '
                    "This link expires in 1 hour.</p>"
                    "<p>If you didn't request this, you can ignore this email.</p>"
                ),
            },
            timeout=10,
        )
        return resp.status_code in (200, 201)
    except Exception as e:
        print(f"[password-reset] email send failed: {e}", flush=True)
        return False


def _send_code_email(to_email: str, code: str, purpose: str) -> bool:
    """Send a 6-digit verification or 2FA code. Falls back to logging in dev."""
    api_key = os.environ.get("RESEND_API_KEY", "")
    from_addr = os.environ.get("RESET_FROM_EMAIL", "Paula <onboarding@resend.dev>")
    label = "Verify your email" if purpose == "verify" else "Your Paula sign-in code"
    if not api_key:
        print(f"[{purpose}] (no RESEND_API_KEY) code for {to_email}: {code}", flush=True)
        return False
    try:
        import requests as r
        resp = r.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "from": from_addr,
                "to": [to_email],
                "subject": label,
                "html": (
                    f"<p>{label}.</p>"
                    f'<p style="font-size:28px;font-weight:700;letter-spacing:4px">{code}</p>'
                    "<p>This code expires in 10 minutes. If you didn't request it, ignore this email.</p>"
                ),
            },
            timeout=10,
        )
        ok = resp.status_code in (200, 201)
        if ok:
            print(f"[{purpose}] email sent to {to_email} (from={from_addr})", flush=True)
        else:
            # Surface the REAL reason Resend rejected it (unverified domain,
            # bad key, restricted from-address, etc.) so it's debuggable.
            print(f"[{purpose}] RESEND REJECTED ({resp.status_code}) from={from_addr} to={to_email}: {resp.text[:400]}", flush=True)
        return ok
    except Exception as e:
        print(f"[{purpose}] email send EXCEPTION: {e}", flush=True)
        return False


@app.post("/api/auth/forgot")
async def forgot_password(req: ForgotRequest):
    # Always return the same response regardless of whether the account exists,
    # to avoid leaking which emails are registered (account enumeration).
    generic = {"ok": True, "message": "If an account exists for that email, a reset link has been sent."}
    try:
        info = auth.create_reset_token((req.email or "").strip().lower())
        if info:
            await asyncio.get_event_loop().run_in_executor(
                None, _send_reset_email, info["email"], info["token"]
            )
    except Exception as e:
        print(f"[password-reset] forgot error: {e}", flush=True)
    return generic


@app.post("/api/auth/reset")
async def reset_password_endpoint(req: ResetRequest):
    return auth.reset_password(req.token.strip(), req.password)

@app.get("/api/auth/me")
async def me(authorization: str = Header(None)):
    user = _get_user(authorization)
    if not user:
        return {"ok": False, "error": "Not authenticated"}
    settings = auth.get_settings(user["id"])
    plus = auth.is_plus(user["id"])
    return {"ok": True, "user": user, "settings": settings,
            "plus": plus,
            "gift_msg": auth.get_gift_msg(user["id"]) if plus else "",
            "messages_today": auth.messages_today(user["id"]),
            "is_admin": (user.get("email", "").lower() == ADMIN_EMAIL)}


@app.post("/api/plus/purchase")
async def plus_purchase(req: dict = None, authorization: str = Header(None)):
    """Mock checkout — grants Paula Plus. (No real payment is processed.)"""
    user = _get_user(authorization)
    if not user:
        return {"ok": False, "error": "Not authenticated"}
    plan = (req or {}).get("plan", "monthly") if isinstance(req, dict) else "monthly"
    auth.set_plus(user["id"], True)
    return {"ok": True, "plus": True, "plan": plan}


@app.post("/api/trade/execute")
async def execute_confirmed_trade(req: dict, authorization: str = Header(None)):
    """Actually place a trade — ONLY called after the user explicitly confirms
    in the UI. Chat 'buy/sell/short/cover' intents return a confirm_trade card
    instead of executing, so an order can never be placed from a single
    (possibly misread) message. This endpoint is the only path to a live order
    from chat."""
    user = _get_user(authorization)
    if not user:
        return {"ok": False, "error": "Not authenticated"}
    action = (req or {}).get("action")
    ticker = (req or {}).get("ticker", "").upper()
    qty = req.get("qty")
    if action == "cancel_orders":
        try:
            result = engine.alpaca_cancel_all_orders()
            if result.get("ok"):
                n = result.get("count")
                return {"ok": True, "message": f"✅ Cancelled {n if n is not None else 'all'} open order{'' if n==1 else 's'}. Your positions are untouched."}
            return {"ok": False, "error": result.get("error", "Cancel failed")}
        except Exception as e:
            return {"ok": False, "error": str(e)[:160]}
    if not ticker or action not in ("buy", "sell", "short", "cover"):
        return {"ok": False, "error": "Invalid trade request"}
    try:
        if action == "buy":
            if req.get("smart"):
                # Re-derive the signal and place the risk-sized bracket order.
                data = engine.fetch_full(ticker)
                if data:
                    sig = engine.generate_trade_signal(data)
                    result = engine.alpaca_smart_buy(ticker=ticker, trade_signal=sig)
                else:
                    result = engine.alpaca_buy(ticker=ticker, qty=qty)
                if result.get("ok"):
                    return {"ok": True, "message": f"🟢 Bought {result.get('qty_calculated', qty)} shares of {ticker} (risk-sized) · {result.get('status','submitted')}"}
            else:
                result = engine.alpaca_buy(ticker=ticker, qty=qty, notional=req.get("notional"))
                if result.get("ok"):
                    qty_str = f"{result.get('qty', qty)} shares" if (result.get("qty") or qty) else f"${req.get('notional')}"
                    return {"ok": True, "message": f"🟢 Bought {qty_str} of {ticker} · {result.get('status','submitted')}"}
        elif action == "sell":
            result = engine.alpaca_sell(ticker=ticker, qty=qty, sell_all=req.get("sell_all", False))
            if result.get("ok"):
                act = "Closed position in" if req.get("sell_all") else f"Sold {qty or result.get('qty','')} shares of"
                return {"ok": True, "message": f"🔴 {act} {ticker} · {result.get('status','submitted')}"}
        elif action == "short":
            result = engine.alpaca_short(ticker=ticker, qty=qty or 1)
            if result.get("ok"):
                return {"ok": True, "message": f"🔴 Shorted {qty or 1} shares of {ticker} · {result.get('status','submitted')}"}
        elif action == "cover":
            result = engine.alpaca_cover(ticker=ticker, qty=qty, cover_all=req.get("cover_all", False))
            if result.get("ok"):
                act = "Covered all of" if req.get("cover_all") else f"Covered {qty or result.get('qty','')} shares of"
                return {"ok": True, "message": f"🟢 {act} {ticker} (short closed) · {result.get('status','submitted')}"}
        return {"ok": False, "error": result.get("error", "Order failed")}
    except Exception as e:
        return {"ok": False, "error": str(e)[:160]}

@app.post("/api/auth/settings")
async def save_user_settings(req: SettingsRequest, authorization: str = Header(None)):
    user = _get_user(authorization)
    if not user:
        return {"ok": False, "error": "Not authenticated"}

    # Connections (broker/data API keys) are a Plus feature. The UI hides them
    # behind a LockedCard, but the endpoint must enforce it too — otherwise a
    # free user could POST keys directly and bypass the paywall. Strip the
    # key fields for non-Plus users; their other settings (theme, font, etc.)
    # still save normally.
    _is_plus = auth.is_plus(user["id"]) or _can_autopilot(user) or (user.get("email", "").lower() == ADMIN_EMAIL)
    payload = req.dict()
    if not _is_plus:
        for _k in ("alpaca_key", "alpaca_secret", "groq_key", "polygon_key"):
            payload.pop(_k, None)
        result = auth.save_settings(user["id"], payload)
        return result

    result = auth.save_settings(user["id"], payload)

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


@app.post("/api/chat/import")
async def import_guest_chats(req: dict = None, authorization: str = Header(None)):
    """Migrate a guest's locally-saved messages into their new account."""
    user = _get_user(authorization)
    if not user:
        return {"ok": False, "error": "Not authenticated"}
    msgs = (req or {}).get("messages", []) if isinstance(req, dict) else []
    saved = 0
    for m in msgs[:100]:
        if isinstance(m, str) and m.strip():
            try:
                auth.save_chat(user["id"], "user", m.strip()[:2000], msg_type="imported")
                saved += 1
            except Exception:
                pass
    return {"ok": True, "imported": saved}


@app.get("/api/health")
async def health():
    ct = ZoneInfo("US/Central")
    return {
        "status": "ok",
        "build": "v3.39.0",  # bump marker — confirms running code
        "private_company_routing": bool(engine.route("what about the SpaceX IPO?").get("private_company")),
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
    try:
        config = engine.load_autopilot_config()
    except Exception:
        # Safety net: if the loader isn't available, read the file but STILL
        # force swing values so the panel can't show stale day-trade params.
        if config_path.exists():
            try:
                config = json.loads(config_path.read_text())
            except Exception:
                config = {}
        try:
            if getattr(engine, "SWING_MODE", True):
                config["MAX_POSITIONS"] = getattr(engine, "SWING_MAX_POSITIONS", 4)
                config["MAX_HOLD_DAYS"] = getattr(engine, "SWING_MAX_HOLD_DAYS", 10)
                config["AVOID_MIDDAY"] = False
                config["TRADING_HOURS_END"] = "15:55"
                config["PARTIAL_PROFIT_PCT"] = 0.04
                config["STALE_MINUTES"] = 0
                config["DAILY_LOSS_LIMIT"] = 0.04
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
    """Clear chat history for current user — both in-memory AND the DB, so a
    fresh chat doesn't reload prior context (which caused Paula to say things
    like 'I've mentioned this before' at the start of a new chat)."""
    user = _get_user(authorization)
    user_id = user["id"] if user else 0
    # Reset in-memory to empty (not pop — pop would trigger a DB reload).
    _user_sessions[user_id] = []
    try:
        auth.clear_chat(user_id)
    except Exception:
        pass
    return {"ok": True}


@app.get("/api/account")
async def get_account(authorization: str = Header(None)):
    """Get Alpaca account info (per-user account when keys are set)."""
    _get_user(authorization)  # sets this user's Alpaca creds for the request
    acc = engine.alpaca_account()
    if not acc:
        return {"ok": False, "error": "Couldn't reach your brokerage account. Check your Alpaca keys in Settings → Connections."}
    return {"ok": True, "data": acc}


@app.get("/api/positions")
async def get_positions(authorization: str = Header(None)):
    """Get all open positions (per-user account when keys are set)."""
    _get_user(authorization)
    positions = engine.alpaca_positions()
    return {"ok": True, "data": positions}


@app.get("/api/orders")
async def get_orders(status: str = "open", limit: int = 10, authorization: str = Header(None)):
    """Get recent orders (per-user account when keys are set)."""
    _get_user(authorization)
    orders = engine.alpaca_orders(status=status, limit=limit)
    return {"ok": True, "data": orders}


_TAPE_CACHE = {"at": 0, "data": []}

@app.get("/api/tape")
def market_tape():
    """Public (no-auth) endpoint: real daily % moves for the login ticker tape.
    Cached for 60s — the login screen can be hit a lot, and this data barely
    moves minute-to-minute, so we avoid a 15-ticker yfinance download per visit."""
    import time as _t
    if _TAPE_CACHE["data"] and (_t.time() - _TAPE_CACHE["at"] < 60):
        return {"ok": True, "tape": _TAPE_CACHE["data"], "cached": True}
    import yfinance as yf
    import warnings
    syms = ["NVDA","AAPL","MSFT","GOOGL","AMZN","META","TSLA","AVGO","AMD","XOM","JPM","NFLX","SPY","QQQ","COST"]
    out = []
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            data = yf.download(syms, period="2d", interval="1d", progress=False, group_by="ticker", threads=True)
        for s in syms:
            try:
                closes = data[s]["Close"].dropna()
                if len(closes) >= 2:
                    pct = (float(closes.iloc[-1]) - float(closes.iloc[-2])) / float(closes.iloc[-2]) * 100
                    out.append({"sym": s, "pct": round(pct, 1)})
            except Exception:
                continue
    except Exception:
        pass
    if out:
        _TAPE_CACHE["data"] = out
        _TAPE_CACHE["at"] = _t.time()
    return {"ok": True, "tape": out or _TAPE_CACHE["data"]}


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
    """Check market regime + the day's single top gainer and loser (best-effort)."""
    regime = engine.check_market_regime()
    # Top mover each way. Try Polygon's all-market snapshot first; if that's
    # unavailable (free tier blocks it), fall back to a Yahoo large-cap scan so
    # the card still shows movers instead of nothing.
    _g = _l = None
    try:
        g = engine.polygon_gainers(limit=1)
        if g:
            _g = {"ticker": g[0]["Ticker"], "chg": g[0]["Chg%"], "price": g[0]["Price"]}
    except Exception:
        pass
    try:
        l = engine.polygon_losers(limit=1)
        if l:
            _l = {"ticker": l[0]["Ticker"], "chg": l[0]["Chg%"], "price": l[0]["Price"]}
    except Exception:
        pass
    if _g is None and _l is None:
        # Polygon gave nothing — Yahoo large-cap fallback.
        try:
            mv = engine.yahoo_top_movers()
            if mv.get("gainer"):
                _g = {"ticker": mv["gainer"]["Ticker"], "chg": mv["gainer"]["Chg%"], "price": mv["gainer"]["Price"]}
            if mv.get("loser"):
                _l = {"ticker": mv["loser"]["Ticker"], "chg": mv["loser"]["Chg%"], "price": mv["loser"]["Price"]}
        except Exception:
            pass
    if _g:
        regime["top_gainer"] = _g
    if _l:
        regime["top_loser"] = _l
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


_COMPANY_CACHE = {}

def _company_info(ticker: str) -> dict:
    """Fetch company name, CEO, sector, and a short description (cached)."""
    t = ticker.upper()
    if t in _COMPANY_CACHE:
        return _COMPANY_CACHE[t]
    info_out = {"name": None, "ceo": None, "sector": None, "summary": None}
    try:
        import yfinance as yf
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            info = yf.Ticker(t).info or {}
        info_out["name"] = info.get("longName") or info.get("shortName")
        info_out["sector"] = info.get("sector")
        summary = info.get("longBusinessSummary")
        if summary:
            # keep it short — first 2 sentences
            parts = summary.split(". ")
            info_out["summary"] = ". ".join(parts[:2]).strip().rstrip(".") + "."
        officers = info.get("companyOfficers") or []
        for o in officers:
            title = (o.get("title") or "").lower()
            # Only accept a clear CEO title. We deliberately DON'T fall back to
            # "first officer in the list" — that surfaced wrong names (e.g. a CFO
            # or a stale/mismatched record) labeled as CEO. Better to show no CEO
            # than a wrong one.
            if ("chief executive" in title or title.strip() in ("ceo", "co-ceo")
                    or title.startswith("ceo")):
                name = o.get("name")
                # Yahoo sometimes returns a placeholder/empty or a name that
                # clearly isn't a person (all caps junk, single token). Basic sanity.
                if name and len(name.split()) >= 2:
                    info_out["ceo"] = name
                    break
        # No reliable-CEO fallback on purpose — leave it None if unclear.
    except Exception:
        pass
    _COMPANY_CACHE[t] = info_out
    if len(_COMPANY_CACHE) > 800:
        # Company info is plain dicts; just trim arbitrary entries when oversized.
        for _k in list(_COMPANY_CACHE)[:300]:
            _COMPANY_CACHE.pop(_k, None)
    return info_out


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

        # DELISTED / ACQUIRED / HALTED guard: stale last bar means the stock no
        # longer trades (e.g. MASI after the Danaher buyout). Don't score or let
        # anyone try to buy it.
        if data.get("delisted"):
            return {
                "ok": True, "ticker": ticker.upper(),
                "price": round(price, 2),
                "change": round(change, 2),
                "change_pct": round(change_pct, 2),
                "score": None, "signal": "DELISTED",
                "delisted": True,
                "stale_days": data.get("stale_days", 0),
                "company": _company_info(ticker),
                "reasons": [],
            }

        # IPO / brand-new-listing guard: the engine relies on history (20/50/200
        # SMAs, RSI, ADX, ATR, volume trend). Too few bars, or flat OHLC with zero
        # volume, means there's nothing real to score — don't fake a HOLD·0.
        tech = data.get("technicals", {}) or {}
        hist_days = data.get("history_days", 999)
        day_high = tech.get("day_high") or tech.get("high")
        day_low = tech.get("day_low") or tech.get("low")
        flat = (day_high is not None and day_low is not None and abs(float(day_high) - float(day_low)) < 1e-6)
        no_vol = (tech.get("volume", 0) or 0) == 0
        if hist_days < 50 or (flat and no_vol):
            return {
                "ok": True, "ticker": ticker.upper(),
                "price": round(price, 2),
                "change": round(change, 2),
                "change_pct": round(change_pct, 2),
                "score": None, "signal": "NEW",
                "too_new": True,
                "history_days": hist_days,
                "company": _company_info(ticker),
                "reasons": [],
            }

        score = signal.get("score", 50)
        action = signal.get("action", "HOLD")
        # Map action to simple signal
        if action in ("BUY", "STRONG_BUY"):
            sig = "BUY"
        elif action in ("SELL", "STRONG_SELL"):
            sig = "SELL"
        else:
            sig = "HOLD"

        reasons = signal.get("signals", []) or signal.get("reasons", [])
        return {
            "ok": True, "ticker": ticker.upper(),
            "price": round(price, 2),
            "change": round(change, 2),
            "change_pct": round(change_pct, 2),
            "score": score, "signal": sig,
            "company": _company_info(ticker),
            "reasons": reasons[:5],
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


_CHART_CACHE = {}        # (ticker, period) -> (timestamp, payload)
_CHART_CACHE_TTL = 180   # daily bars: 3 min; intraday refreshes a touch faster below

def _polygon_chart_bars(ticker: str, period: str, intraday: bool, interval: str = None):
    """Fallback chart source: Polygon aggregates. Yahoo aggressively rate-limits
    single-ticker history calls from datacenter IPs (like Railway's), which makes
    the chart fail constantly; Polygon is far more reliable from a server. Returns
    the same payload shape as the Yahoo path, or None on failure."""
    import requests as _rq, time as _t
    from datetime import datetime as _dt, timedelta as _td
    key = os.environ.get("POLYGON_API_KEY", "") or "wzJ5v31KgEA_rwFQxViseXokW5TLoSrG"
    if not key:
        return None
    # Map our periods to a Polygon (multiplier, timespan, lookback-days).
    span = {
        "1d":  (5, "minute", 1),
        "5d":  (30, "minute", 5),
        "1mo": (1, "day", 31),
        "3mo": (1, "day", 93),
        "6mo": (1, "day", 186),
        "1y":  (1, "day", 372),
        "5y":  (1, "week", 1830),
    }.get(period, (1, "day", 372))
    mult, timespan, lookback = span
    end = _dt.utcnow().date()
    start = end - _td(days=lookback)
    try:
        url = (f"https://api.polygon.io/v2/aggs/ticker/{ticker}/range/"
               f"{mult}/{timespan}/{start.isoformat()}/{end.isoformat()}")
        r = _rq.get(url, params={"apiKey": key, "adjusted": "true", "sort": "asc", "limit": 50000}, timeout=12)
        if r.status_code != 200:
            return None
        results = (r.json() or {}).get("results") or []
        if not results:
            return None
        dates, o, h, l, c, v = [], [], [], [], [], []
        for bar in results:
            ts = bar.get("t")
            if ts is None:
                continue
            d = _dt.utcfromtimestamp(ts / 1000)
            dates.append(d.strftime("%Y-%m-%d %H:%M" if intraday else "%Y-%m-%d"))
            o.append(round(float(bar.get("o", 0)), 2))
            h.append(round(float(bar.get("h", 0)), 2))
            l.append(round(float(bar.get("l", 0)), 2))
            c.append(round(float(bar.get("c", 0)), 2))
            v.append(int(bar.get("v", 0)))
        if not dates:
            return None
        return {"ok": True, "data": {"dates": dates, "open": o, "high": h, "low": l, "close": c, "volume": v}}
    except Exception:
        return None


@app.get("/api/chart/{ticker}")
def chart_data(ticker: str, period: str = "1y"):
    """Get chart OHLCV data — sync endpoint, auto-threaded by FastAPI.
    Cached + retries on rate-limit so chart views don't fail when Yahoo is busy
    (e.g. right after a scan)."""
    import yfinance as yf
    import warnings, time as _t
    ticker = ticker.upper()
    INTRADAY = {"1d": "5m", "5d": "30m"}
    interval = INTRADAY.get(period)
    intraday = interval is not None

    # Serve from cache when fresh (intraday gets a shorter TTL so it stays live).
    ttl = 60 if intraday else _CHART_CACHE_TTL
    ck = (ticker, period)
    cached = _CHART_CACHE.get(ck)
    if cached and (_t.time() - cached[0]) < ttl:
        return cached[1]

    last_err = "No data"
    for attempt in range(3):
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                tk = yf.Ticker(ticker)
                hist = tk.history(period=period, interval=interval) if intraday else tk.history(period=period)
            if hist is None or hist.empty:
                last_err = "No data"
                # Could be a soft rate-limit returning empty — brief retry.
                if attempt < 2:
                    _t.sleep(1.2 * (attempt + 1)); continue
                # Yahoo gave us nothing — try Polygon before giving up.
                _poly = _polygon_chart_bars(ticker, period, intraday, interval)
                if _poly:
                    _CHART_CACHE[ck] = (_t.time(), _poly)
                    return _poly
                # If we have a stale cached copy, better to show it than nothing.
                if cached:
                    return cached[1]
                return {"ok": False, "error": "No data"}
            raw_keys = [str(d)[:16] if intraday else str(d)[:10] for d in hist.index]
            seen = set(); indices = []; clean_dates = []
            for i, d in enumerate(raw_keys):
                if d not in seen:
                    seen.add(d); indices.append(i); clean_dates.append(d)
            payload = {
                "ok": True, "data": {
                    "dates": clean_dates,
                    "open": [round(float(hist["Open"].iloc[i]), 2) for i in indices],
                    "high": [round(float(hist["High"].iloc[i]), 2) for i in indices],
                    "low": [round(float(hist["Low"].iloc[i]), 2) for i in indices],
                    "close": [round(float(hist["Close"].iloc[i]), 2) for i in indices],
                    "volume": [int(hist["Volume"].iloc[i]) for i in indices],
                }
            }
            _CHART_CACHE[ck] = (_t.time(), payload)
            if len(_CHART_CACHE) > 400:
                for _k in sorted(_CHART_CACHE, key=lambda k: _CHART_CACHE[k][0])[:150]:
                    _CHART_CACHE.pop(_k, None)
            return payload
        except Exception as e:
            last_err = str(e)[:100]
            msg = last_err.lower()
            if ("rate" in msg or "too many" in msg) and attempt < 2:
                _t.sleep(2.0 * (attempt + 1))  # 2s, then 4s
                continue
            break
    # All Yahoo attempts failed — try Polygon, then stale cache, then the error.
    _poly = _polygon_chart_bars(ticker, period, intraday, interval)
    if _poly:
        _CHART_CACHE[ck] = (_t.time(), _poly)
        return _poly
    if cached:
        return cached[1]
    return {"ok": False, "error": last_err}


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
    # Free-tier daily message limit — MUST match /api/chat. Without this, the
    # stream endpoint was an open bypass: a free user hitting /api/chat/stream
    # directly skipped the cap entirely. Plus/admin/autopilot are exempt.
    if user:
        _exempt = auth.is_plus(user["id"]) or _can_autopilot(user) or (user.get("email", "").lower() == ADMIN_EMAIL)
        if not _exempt and auth.messages_today(user["id"]) >= 3:
            return {
                "ok": True, "stream": False, "type": "limit", "limit_reached": True,
                "message": "You've used your 3 free messages for today. Upgrade to Paula Plus for unlimited messages, new chats, and full access.",
            }
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
        if not _can_autopilot(user):
            return {"ok": True, "message": "Autopilot is restricted to authorized accounts.", "stream": False, "type": "chat", "autopilot": False}
        if not autopilot_task or autopilot_task.done():
            autopilot_owner_id = user_id
            autopilot_task = _spawn_autopilot()
            _save_autopilot_state(True, user_id)
        resp = "Autopilot activated. Scanning every 5 minutes."
        chat_history.append({"role": "assistant", "content": resp})
        return {"ok": True, "message": resp, "stream": False, "type": "trade", "autopilot": True}

    if itype == "stop_autopilot":
        if not _can_autopilot(user):
            return {"ok": True, "message": "Autopilot is restricted to authorized accounts.", "stream": False, "type": "chat", "autopilot": False}
        if autopilot_task and not autopilot_task.done():
            autopilot_task.cancel()
            autopilot_task = None
            autopilot_owner_id = None
        _save_autopilot_state(False, None)
        resp = "Autopilot stopped."
        chat_history.append({"role": "assistant", "content": resp})
        return {"ok": True, "message": resp, "stream": False, "type": "trade", "autopilot": False}

    # Execute intent (analysis, trade, list, etc)
    result = None
    try:
        loop = asyncio.get_event_loop()
        _prog = _make_scan_progress_cb(loop)
        _is_plus = bool(user) and (auth.is_plus(user["id"]) or _can_autopilot(user) or (user.get("email", "").lower() == ADMIN_EMAIL))
        result = await loop.run_in_executor(None, functools.partial(engine.execute, intent, progress_cb=_prog, is_plus=_is_plus))
    except Exception as e:
        print(f"⚠️ Execute error: {e}")

    # Determine response strategy
    stock_data = None

    # Trade confirmation — a buy/sell/short/cover intent returns a confirm card
    # (no order placed). The frontend shows Confirm/Cancel; only Confirm hits
    # /api/trade/execute. This guarantees no order from a single chat message.
    if result and result.get("ok") and result.get("type") == "confirm_trade":
        return {
            "ok": True, "stream": False, "type": "confirm_trade",
            "trade": result.get("trade"),
            "autopilot": autopilot_task is not None and not autopilot_task.done(),
        }

    # If execute returned a ready message (trades, regime, etc) — return instantly
    if result and result.get("ok") and result.get("msg"):
        rtype = result.get("type", "")
        # Deep single-stock analysis is Plus-only (see the non-stream path for
        # the full rationale) — close the chat bypass here as well.
        _is_deep = rtype == "analysis" and bool(result.get("ticker")) and isinstance(result.get("data"), dict)
        if _is_deep:
            _plus = bool(user) and (auth.is_plus(user["id"]) or _can_autopilot(user) or (user.get("email", "").lower() == ADMIN_EMAIL))
            if not _plus:
                return _taste_analysis(result)
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
        _is_deep2 = bool(result.get("ticker")) and isinstance(result.get("data"), dict)
        if _is_deep2:
            _plus2 = bool(user) and (auth.is_plus(user["id"]) or _can_autopilot(user) or (user.get("email", "").lower() == ADMIN_EMAIL))
            if not _plus2:
                return _taste_analysis(result)
        stock_data = result.get("data")
    elif result and result.get("error"):
        resp = f"⚠️ {_friendly_error(result.get('error', ''))}"
        chat_history.append({"role": "assistant", "content": resp})
        return {"ok": True, "message": resp, "stream": False, "type": "chat"}

    # ── Make the AI portfolio-aware for DECISION questions ──
    # If the user is weighing a move ("should I add to NVDA", "trim my winners",
    # "how's my risk"), attach a lightweight account + positions snapshot so the
    # AI can reason about buying power, concentration, and existing exposure —
    # not blind generic advice. Skip for pure idea-discovery ("find me setups"),
    # where mixing in the portfolio is explicitly unwanted.
    try:
        _ml = user_msg.lower()
        _wants_ideas = intent.get("type") in ("stock_ideas", "gainers", "losers")
        _decision = any(p in _ml for p in [
            "should i", "add to", "buy more", "trim", "sell some", "take profit",
            "my position", "my risk", "my portfolio", "my exposure", "concentrated",
            "too much", "rebalance", "cut", "hold or", "average down", "double down",
            "how am i", "am i too", "diversif",
        ])
        if _decision and not _wants_ideas:
            acct = engine.alpaca_account() or {}
            poss = engine.alpaca_positions() or []
            snapshot = {
                "buying_power": acct.get("buying_power"),
                "equity": acct.get("equity"),
                "cash": acct.get("cash"),
                "open_pl": acct.get("unrealized_pl") or acct.get("open_pl"),
                "positions": [
                    {"ticker": p.get("ticker") or p.get("symbol"),
                     "qty": p.get("qty"),
                     "market_value": p.get("market_value"),
                     "unrealized_pl": p.get("unrealized_pnl") or p.get("unrealized_pl"),
                     "unrealized_pl_pct": p.get("unrealized_pnl_pct") or p.get("unrealized_plpc"),
                     "side": p.get("side", "long")}
                    for p in poss
                ],
                "position_count": len(poss),
            }
            if stock_data is None:
                stock_data = {}
            if isinstance(stock_data, dict):
                stock_data = {**stock_data, "portfolio_context": snapshot}
    except Exception:
        pass

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


@app.post("/api/scan/cancel")
async def cancel_scan(authorization: str = Header(None), token: str = None):
    """Cancel the caller's in-flight market scan (e.g. they switched chats or
    closed the tab). Best-effort: cancelling the asyncio task stops the result
    from being processed/broadcast and frees the slot. (A scan already blocked
    inside a worker thread will let that thread finish its current chunk — Python
    can't force-kill a thread — but no further work is queued and nothing is
    sent back.)"""
    # Auth may come via header (switchChat fetch) or ?token= (sendBeacon on tab
    # close, which can't set headers).
    user = _get_user(authorization)
    if not user and token:
        user = _get_user("Bearer " + token)
    if not user:
        return {"ok": True, "cancelled": False}
    task = _active_scans.pop(user["id"], None)
    if task and not task.done():
        task.cancel()
        return {"ok": True, "cancelled": True}
    return {"ok": True, "cancelled": False}


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
    # Free-tier daily message limit (Paula Plus, admin, and authorized accounts
    # are exempt). 3 free messages per day; the 4th is blocked with the Plus prompt.
    if user:
        _exempt = auth.is_plus(user["id"]) or _can_autopilot(user) or (user.get("email", "").lower() == ADMIN_EMAIL)
        if not _exempt and auth.messages_today(user["id"]) >= 3:
            return {
                "ok": True, "stream": False, "type": "limit",
                "limit_reached": True,
                "message": "You've used your 3 free messages for today. Upgrade to Paula Plus for unlimited messages, new chats, and full access.",
            }
    if user:
        auth.save_chat(user["id"], "user", user_msg)

    # Per-chat history: if the frontend sends the current chat's messages, use
    # those (each sidebar chat stays independent). Fall back to the per-user
    # blob only when no history is supplied.
    if msg.history is not None:
        chat_history = [
            {"role": m.get("role"), "content": m.get("content", "")}
            for m in msg.history
            if m.get("role") in ("user", "assistant") and m.get("content")
        ][-12:]
    else:
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
            autopilot_task = _spawn_autopilot()
            _save_autopilot_state(True, user_id)
        return {"ok": True, "message": "Autopilot activated.", "type": "trade", "autopilot": True}

    if intent.get("type") == "stop_autopilot":
        if not user or user.get("email", "").lower() != ADMIN_EMAIL:
            return {"ok": True, "message": "Autopilot is restricted to admin accounts.", "type": "chat", "autopilot": False}
        if autopilot_task and not autopilot_task.done():
            autopilot_task.cancel()
            autopilot_task = None
            autopilot_owner_id = None
        _save_autopilot_state(False, None)
        return {"ok": True, "message": "Autopilot stopped.", "type": "trade", "autopilot": False}

    # Run in thread pool since engine functions are blocking
    loop = asyncio.get_event_loop()
    _prog = _make_scan_progress_cb(loop)
    _is_plus = bool(user) and (auth.is_plus(user["id"]) or _can_autopilot(user) or (user.get("email", "").lower() == ADMIN_EMAIL))

    # ── Async scan ──
    # A market scan (stock_ideas) can take long enough that the gateway drops the
    # HTTP request ("Connection lost"). So we DON'T run it inline: kick it off in
    # the background, return an immediate ack, and deliver the finished result
    # over the websocket (the same channel the progress bar already uses).
    if intent.get("type") == "stock_ideas":
        _uid = user["id"] if user else None
        _big = intent.get("category") in ("full", "nasdaq")
        _scan_timeout = 1500 if _big else 240  # 25 min vs 4 min
        # Cancel any previous scan still running for this user before starting a
        # new one (a user only needs their latest scan).
        _prev = _active_scans.pop(_uid, None) if _uid is not None else None
        if _prev and not _prev.done():
            _prev.cancel()
        async def _run_scan_bg():
            try:
                res = await asyncio.wait_for(
                    loop.run_in_executor(
                        None, functools.partial(engine.execute, intent, progress_cb=_prog, is_plus=_is_plus)),
                    timeout=_scan_timeout,
                )
                msg_out = res.get("msg", "") if res and res.get("ok") else _friendly_error((res or {}).get("error", "Scan failed"))
                tickers_out = (res or {}).get("tickers", []) if res and res.get("ok") else []
                if _uid:
                    try: auth.save_chat(_uid, "assistant", msg_out)
                    except Exception: pass
                await broadcast("scan_result", {
                    "ok": bool(res and res.get("ok")),
                    "message": msg_out,
                    "tickers": tickers_out,
                })
            except asyncio.CancelledError:
                # User navigated away / closed the tab — drop it silently, no
                # broadcast (nobody's waiting).
                raise
            except asyncio.TimeoutError:
                await broadcast("scan_result", {
                    "ok": False,
                    "message": "⚠️ The market's data source is slow right now and the scan couldn't finish. Please try again in a moment — or ask me to analyze a specific ticker.",
                })
            except Exception as _se:
                await broadcast("scan_result", {"ok": False, "message": _friendly_error(str(_se))})
            finally:
                if _uid is not None and _active_scans.get(_uid) is _scan_task:
                    _active_scans.pop(_uid, None)
        _scan_task = asyncio.create_task(_run_scan_bg())
        if _uid is not None:
            _active_scans[_uid] = _scan_task
        return {
            "ok": True, "type": "scan_started", "big": _big,
            "message": ("On it — scanning the entire " + ("NASDAQ" if intent.get("category") == "nasdaq" else "market") +
                        ". This is a big one and can take several minutes…") if _big
                       else "On it — scanning the market for the best setups. This takes a moment…",
        }

    result = await loop.run_in_executor(None, functools.partial(engine.execute, intent, progress_cb=_prog, is_plus=_is_plus))

    if result and result.get("ok"):
        resp = result.get("msg", "")
        rtype = result.get("type", "")

        # Trade confirmation — return the confirm card, place no order.
        if rtype == "confirm_trade":
            return {
                "ok": True, "type": "confirm_trade", "trade": result.get("trade"),
                "autopilot": autopilot_task is not None and not autopilot_task.done(),
            }

        if rtype == "analysis":
            # Deep single-stock analysis is a Plus feature. A result carrying a
            # specific ticker + full data dict is a deep-dive (not a scan/list or
            # a market overview), so gate it. This closes the bypass where free
            # users reach the Plus 'Analyze' experience via chat ("analyze AAPL")
            # or the in-chat Analyze chips, not just the gated Analyze tab.
            _is_deep = bool(result.get("ticker")) and isinstance(result.get("data"), dict)
            if _is_deep and user:
                _plus = auth.is_plus(user["id"]) or _can_autopilot(user) or (user.get("email", "").lower() == ADMIN_EMAIL)
                if not _plus:
                    return _taste_analysis(result)
            elif _is_deep and not user:
                # Guests/anonymous also get just the taste.
                return _taste_analysis(result)
            if not resp:
                # If the question is news-oriented, fetch recent headlines for
                # the analyzed ticker and feed them to the AI (same as chat path).
                _amsg = user_msg
                _aml = user_msg.lower()
                if any(w in _aml for w in ["news","latest","happening","headline","why is","why did","catalyst","recent","what's going on","whats going on","update"]):
                    try:
                        _atk = result.get("ticker", "")
                        _anews = engine.fetch_news(_atk, limit=5) if _atk else None
                        if _anews:
                            _al = "\n".join(f"- ({n['date']}) {n['title']} — {n['publisher']}: {n['summary']}" for n in _anews)
                            _amsg = user_msg + f"\n\n[LIVE NEWS (use these recent headlines, cite dates):\n{_al}\n]"
                    except Exception:
                        pass
                # AI generates analysis — but we prepend real data header
                ai_text = await loop.run_in_executor(None, engine.ai_response, _amsg, result.get("data"), chat_history, "US")
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
        elif rtype == "position_size":
            ps = result.get("data", {})
            resp = await loop.run_in_executor(None, engine.ai_response, user_msg, {"position_size": ps}, chat_history, "US")
        elif rtype == "compare":
            # Two structured scorecards → let the AI write a head-to-head verdict.
            cmp_data = result.get("data", {})
            resp = await loop.run_in_executor(None, engine.ai_response, user_msg, cmp_data, chat_history, "US")
        elif rtype == "list":
            # Send list data to AI for real analysis instead of just showing a table
            list_data = result.get("data", [])
            resp = await loop.run_in_executor(None, engine.ai_response, user_msg, {"list_title": result.get("title", ""), "stocks": list_data}, chat_history, "US")
        elif not resp:
            # Try to extract tickers from message AND history to provide context
            _chat_data = {}
            try:
                import re as _re
                # Only scan the CURRENT message for tickers — pulling them from
                # history attached unrelated data (e.g. AAPL from an earlier turn)
                # to questions about something else entirely (e.g. "SpaceX IPO?").
                if not (result and result.get("private_company")):
                    _found_tickers = list(set(_re.findall(r'\b([A-Z]{1,5})\b', user_msg)))
                    _known = KNOWN_TICKERS
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
            _umsg = user_msg
            if result and result.get("private_company"):
                _umsg = user_msg + "\n\n[Note: this is about a privately-held / pre-IPO company with no public ticker. Answer conversationally from what you know — explain its private status, any IPO/funding context, and how (or whether) someone could get exposure. Do NOT say you lack data or look for a stock price.]"
            # ── Live news: if the question is news-oriented, fetch recent
            # headlines (Polygon) and inject them so Paula answers with current
            # info instead of stale training knowledge.
            _ml = user_msg.lower()
            _wants_news = any(w in _ml for w in [
                "news", "latest", "happening", "headline", "earnings", "report",
                "announced", "update on", "what's going on", "whats going on",
                "why is", "why did", "catalyst", "recent", "today",
            ])
            if _wants_news and not (result and result.get("private_company")):
                try:
                    import re as _re2
                    _nt = None
                    for _w in _re2.findall(r'\b([A-Z]{1,5})\b', user_msg):
                        if _w in KNOWN_TICKERS:
                            _nt = _w; break
                    _news = engine.fetch_news(_nt, limit=5)
                    if _news:
                        _lines = "\n".join(f"- ({n['date']}) {n['title']} — {n['publisher']}: {n['summary']}" for n in _news)
                        _umsg = _umsg + f"\n\n[LIVE NEWS (use these recent headlines in your answer, cite the dates):\n{_lines}\n]"
                except Exception:
                    pass
            resp = await loop.run_in_executor(None, engine.ai_response, _umsg, _chat_data if _chat_data else None, chat_history, "US")
    elif result and result.get("error"):
        resp = f"⚠️ {_friendly_error(result.get('error', ''))}"
    else:
        # Final fallthrough — plain conversational answer.
        _fall_data = None
        _fmsg = user_msg
        _is_private = bool(result and result.get("private_company"))
        if _is_private:
            _fmsg = user_msg + "\n\n[Note: this is about a privately-held / pre-IPO company with no public ticker. Answer conversationally, and do NOT analyze any unrelated ticker.]"
            # Pull live open-web context (Tavily) so private-company answers are
            # current (e.g. recent SpaceX IPO reporting), not stale training data.
            try:
                _ws = engine.web_search(user_msg, max_results=5)
                if _ws:
                    _wl = "\n".join(f"- {w['title']}: {w['content']}" + (f" [source]({w['url']})" if w['url'] else "") for w in _ws)
                    _fmsg = _fmsg + f"\n\n[LIVE WEB SEARCH — use this current info. Cite sources as markdown links [publisher](url), never bare URLs:\n{_wl}\n]"
            except Exception:
                pass
        else:
            # Only attach a ticker the CURRENT message actually names — never
            # one pulled from earlier in the conversation (that caused unrelated
            # data, e.g. LLY/AAPL, to be stapled onto questions like "SpaceX IPO").
            try:
                import re as _re
                _cur = [t for t in _re.findall(r'\b([A-Z]{1,5})\b', user_msg) if t in KNOWN_TICKERS]
                if _cur:
                    _fall_data = engine.fetch_full(_cur[0])
                # News injection for news-oriented questions
                _fl = user_msg.lower()
                _is_news = any(w in _fl for w in ["news","latest","happening","headline","earnings","why is","why did","catalyst","recent","update"])
                # Explicit user request to look something up / search the web.
                _wants_search = any(p in _fl for p in [
                    "look it up", "look up", "search for", "search the web", "google",
                    "can you find", "find out", "look into", "check online", "search online",
                    "what's the latest on", "whats the latest on",
                ])
                if _is_news:
                    _ntk = _cur[0] if _cur else None
                    _fnews = engine.fetch_news(_ntk, limit=5)
                    if _fnews:
                        _fl2 = "\n".join(f"- ({n['date']}) {n['title']} — {n['publisher']}: {n['summary']}" for n in _fnews)
                        _fmsg = _fmsg + f"\n\n[LIVE NEWS (use these recent headlines, cite dates):\n{_fl2}\n]"
                # Fire a web search whenever the user explicitly asks to look it up,
                # OR for a current-info question with no ticker attached.
                if _wants_search or (not _cur and _is_news):
                    _ws = engine.web_search(user_msg, max_results=5)
                    if _ws:
                        _wl = "\n".join(f"- {w['title']}: {w['content']}" + (f" [source]({w['url']})" if w['url'] else "") for w in _ws)
                        _fmsg = _fmsg + f"\n\n[LIVE WEB SEARCH — use this current info. Cite sources as markdown links [publisher](url), never bare URLs:\n{_wl}\n]"
            except Exception:
                pass
        resp = await loop.run_in_executor(None, engine.ai_response, _fmsg, _fall_data, chat_history, "US")

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

    In SWING mode this is a no-op: swing positions are held overnight and must
    NOT be force-closed at the bell. The closer only runs if the engine is in
    legacy intraday mode.
    """
    if getattr(engine, "SWING_MODE", False):
        print("[eod-guardian] swing mode — EOD liquidation disabled", flush=True)
        return

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


def _autopilot_watchdog(task: asyncio.Task):
    """Restart autopilot if the loop ever dies for any reason other than a
    deliberate stop. Prevents the 'autopilot randomly stops' failure mode."""
    global autopilot_task
    # Ignore the callback if this isn't the live task anymore (e.g. it was
    # replaced by a stop+restart) or if it was cleanly cancelled.
    if task is not autopilot_task:
        return
    if task.cancelled():
        return
    exc = None
    try:
        exc = task.exception()
    except asyncio.CancelledError:
        return
    # Loop exited without being cancelled — that's never expected. Restart it.
    reason = repr(exc) if exc else "loop returned unexpectedly"
    print(f"[autopilot] loop died ({reason}) — restarting in 10s", flush=True)

    async def _restart():
        global autopilot_task
        await asyncio.sleep(10)  # avoid a tight crash-loop
        if autopilot_owner_id is not None:
            autopilot_task = _spawn_autopilot()
            try:
                await broadcast("autopilot", {"status": "restarted", "reason": reason[:160]})
            except Exception:
                pass

    asyncio.create_task(_restart())


def _spawn_autopilot() -> asyncio.Task:
    """Create the autopilot task and attach the restart watchdog."""
    t = asyncio.create_task(_autopilot_loop())
    t.add_done_callback(_autopilot_watchdog)
    return t


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

            # Run the scan in a thread pool (yfinance is blocking). Apply the
            # autopilot OWNER's Alpaca creds inside the thread (contextvars don't
            # propagate into executor threads), so autopilot trades the owner's
            # own account, not the shared one.
            loop = asyncio.get_event_loop()
            _owner_creds = None
            try:
                if autopilot_owner_id:
                    _owner_creds = auth.get_user_alpaca_creds(autopilot_owner_id)
            except Exception:
                _owner_creds = None

            def _run_with_creds():
                if _owner_creds:
                    engine.set_alpaca_creds(_owner_creds.get("key_id"), _owner_creds.get("secret"))
                return engine.run_autopilot()

            result = await loop.run_in_executor(None, _run_with_creds)

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

            # High-conviction alerts (90+) — fire an in-app alert per ticker, but
            # only once per day each (dedup) so it doesn't repeat every cycle.
            try:
                from datetime import date as _date
                _today_str = _date.today().isoformat()
                # Drop stale entries from previous days.
                for _k in [k for k, v in _alerted_today.items() if v != _today_str]:
                    _alerted_today.pop(_k, None)
                for a in (result.get("alerts") or []):
                    tkr = a.get("ticker")
                    if not tkr or _alerted_today.get(tkr) == _today_str:
                        continue
                    _alerted_today[tkr] = _today_str
                    await broadcast("alert", {
                        "ticker": tkr,
                        "score": a.get("score"),
                        "rr": a.get("rr"),
                    })
            except Exception as _ae:
                print(f"  ⚠️ alert broadcast error: {_ae}")

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
            break  # Clean exit on stop
        except Exception as e:
            # The error handler itself must never raise — a failed broadcast or
            # notification used to bubble out of the loop and silently kill autopilot.
            err = str(e)[:200]
            print(f"[autopilot] scan error: {err}", flush=True)
            try:
                await broadcast("autopilot", {"status": "error", "error": err})
            except Exception:
                pass
            try:
                await send_phone_notification("⚠️ Paula Error", err[:80], priority="high")
            except Exception:
                pass

        try:
            await asyncio.sleep(5 * 60)  # 5 minutes
        except asyncio.CancelledError:
            break  # Clean exit on stop


@app.post("/api/autopilot/start")
async def start_autopilot(authorization: str = Header(None)):
    """Start the autopilot background loop. Admin only."""
    global autopilot_task, autopilot_owner_id
    user = _get_user(authorization)
    if not user:
        print("[autopilot] start rejected: no authenticated user", flush=True)
        return {"ok": False, "error": "Not signed in"}
    if not _can_autopilot(user):
        print(f"[autopilot] start rejected: {user.get('email')!r} not in autopilot allowlist", flush=True)
        return {"ok": False, "error": "Autopilot access restricted"}
    if autopilot_task and not autopilot_task.done():
        print("[autopilot] already running", flush=True)
        return {"ok": True, "message": "Autopilot already running"}

    autopilot_owner_id = user["id"]
    autopilot_task = _spawn_autopilot()
    _save_autopilot_state(True, user["id"])
    print(f"[autopilot] started by {user.get('email')}", flush=True)
    await broadcast("autopilot", {"status": "started"})
    try:
        await send_phone_notification("🟢 Autopilot Started", "Paula is now scanning for trades every 5 minutes", priority="default")
    except Exception:
        pass
    return {"ok": True, "message": "Autopilot started"}


@app.post("/api/autopilot/stop")
async def stop_autopilot(authorization: str = Header(None)):
    """Stop the autopilot. Admin only."""
    global autopilot_task, autopilot_owner_id
    user = _get_user(authorization)
    if not _can_autopilot(user):
        return {"ok": False, "error": "Autopilot access restricted"}
    if autopilot_task and not autopilot_task.done():
        autopilot_task.cancel()
        autopilot_task = None
        autopilot_owner_id = None
    _save_autopilot_state(False, None)
    await broadcast("autopilot", {"status": "stopped"})
    try:
        acc = engine.alpaca_account() or {}
        pnl = acc.get("daily_pnl", 0)
        pnl_sign = "+" if pnl >= 0 else ""
        await send_phone_notification("🔴 Autopilot Stopped", f"Day so far: {pnl_sign}${abs(pnl):,.0f} | Equity: ${acc.get('equity', 0):,.0f}", priority="default")
    except Exception:
        try:
            await send_phone_notification("🔴 Autopilot Stopped", "Paula is no longer trading", priority="default")
        except Exception:
            pass
    print("[autopilot] stopped", flush=True)
    return {"ok": True, "message": "Autopilot stopped"}


@app.get("/api/autopilot/status")
async def autopilot_status():
    """Check if autopilot is running."""
    running = autopilot_task is not None and not autopilot_task.done()
    return {"ok": True, "running": running}


# ── Run ──

if __name__ == "__main__":
    import uvicorn
    # Cloud hosts (Railway, Render) inject a PORT env var and require binding to
    # 0.0.0.0. Locally, default to 127.0.0.1:3141 as before.
    _port = int(os.environ.get("PORT", "3141"))
    _host = "0.0.0.0" if os.environ.get("PORT") else "127.0.0.1"
    uvicorn.run(app, host=_host, port=_port, log_level="info")


# ═══ Admin Panel ═══

@app.get("/api/maintenance")
async def maintenance_status():
    """Public — frontend polls this to show the maintenance screen to everyone."""
    return {"ok": True, **_maint_state()}


@app.post("/api/admin/set-plus")
async def admin_set_plus(req: dict, authorization: str = Header(None)):
    """Admin-only: grant or revoke Paula Plus for a user."""
    user = _get_user(authorization)
    if not user or user.get("email", "").lower() != ADMIN_EMAIL:
        return {"ok": False, "error": "Unauthorized"}
    target_id = req.get("user_id")
    on = bool(req.get("on", True))
    gift_msg = req.get("message", "") if on else ""
    if not target_id:
        return {"ok": False, "error": "Missing user_id"}
    auth.set_plus(int(target_id), on, gift_msg=gift_msg)
    return {"ok": True, "user_id": target_id, "plus": on}


@app.post("/api/admin/maintenance")
async def admin_set_maintenance(req: dict, authorization: str = Header(None)):
    """Admin-only: turn maintenance mode on/off."""
    user = _get_user(authorization)
    if not user or user.get("email", "").lower() != ADMIN_EMAIL:
        return {"ok": False, "error": "Unauthorized"}
    _set_maint(bool(req.get("on")), req.get("message", ""))
    state = _maint_state()
    # Push to all connected clients so the maintenance screen flips on/off
    # instantly — no refresh and no waiting for the next poll.
    try:
        await broadcast("maintenance", state)
    except Exception:
        pass
    return {"ok": True, **state}


@app.get("/api/admin/users")
async def admin_list_users(authorization: str = Header(None)):
    user = _get_user(authorization)
    if not user or user.get("email", "").lower() != ADMIN_EMAIL:
        return {"ok": False, "error": "Unauthorized"}
    db = auth._get_db()
    try:
        rows = db.execute("SELECT id, username, email, created_at, last_login, plus FROM users ORDER BY id DESC").fetchall()
        users = [{"id": r["id"], "username": r["username"], "email": r["email"],
                  "created_at": r["created_at"], "last_login": r["last_login"],
                  "plus": bool(r["plus"]) if "plus" in r.keys() else False} for r in rows]
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
