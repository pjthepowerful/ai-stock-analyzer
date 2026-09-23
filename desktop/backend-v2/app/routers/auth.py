"""
Auth router — thin, typed wrapper around the EXISTING auth.py (password
hashing, JWT issuance, the SQLite user table). We do not touch that logic;
real user credentials are not the place to introduce new code paths.
"""
import re

from fastapi import APIRouter, Header, HTTPException

import os

from ..bridge import auth, engine
from ..deps import current_user_required, is_admin
from ..models.auth import (
    LoginRequest,
    ResendCodeRequest,
    SignupRequest,
    VerifyCodeRequest,
)
from ..models.settings import SettingsRequest

router = APIRouter(prefix="/api/auth", tags=["auth"])


EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def _send_code_email(email: str, code: str, purpose: str) -> bool:
    # Same no-op-if-unconfigured behavior as the original backend: log to
    # console when RESEND_API_KEY isn't set, rather than failing signup/login.
    import os
    if not os.environ.get("RESEND_API_KEY"):
        print(f"[auth] (no RESEND_API_KEY) {purpose} code for {email}: {code}", flush=True)
        return False
    try:
        import requests
        requests.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {os.environ['RESEND_API_KEY']}"},
            json={
                "from": os.environ.get("RESET_FROM_EMAIL", "Paula <onboarding@resend.dev>"),
                "to": [email],
                "subject": "Your Paula verification code",
                "text": f"Your code is {code}",
            },
            timeout=8,
        )
        return True
    except Exception as e:
        print(f"[auth] code email failed: {e}", flush=True)
        return False


EMAIL_AUTH_ENABLED = False  # flip on once RESEND_API_KEY + a verified domain exist


@router.post("/signup")
def signup(req: SignupRequest):
    if not EMAIL_RE.match(req.email):
        raise HTTPException(422, "Invalid email format")
    if len(req.username.strip()) < 2:
        raise HTTPException(422, "Name must be at least 2 characters")
    if len(req.password) < 6:
        raise HTTPException(422, "Password must be at least 6 characters")

    result = auth.signup(req.username.strip(), req.password, req.email.strip().lower())
    if not result.get("ok"):
        raise HTTPException(409, result.get("error", "Could not create account"))

    if EMAIL_AUTH_ENABLED:
        code = auth.create_email_code(req.email.strip().lower(), "verify")
        if code:
            _send_code_email(req.email.strip().lower(), code, "verify")
        result["needs_verification"] = True
    return result


@router.post("/login")
def login(req: LoginRequest):
    result = auth.login(req.email.strip(), req.password)
    if not result.get("ok"):
        raise HTTPException(401, result.get("error", "Invalid credentials"))

    if EMAIL_AUTH_ENABLED:
        email = (result.get("user") or {}).get("email", "").strip().lower()
        code = auth.create_email_code(email, "2fa")
        sent = _send_code_email(email, code, "2fa") if code else False
        if sent:
            return {"ok": True, "needs_2fa": True, "email": email}
        # Password was already verified — don't lock the user out just
        # because the code email failed to send.
        direct = auth.issue_token_for_email(email)
        direct["twofa_skipped"] = True
        return direct
    return result


@router.post("/verify-code")
def verify_code(req: VerifyCodeRequest):
    vr = auth.verify_email_code(req.email.strip().lower(), req.code.strip(), req.purpose)
    if not vr.get("ok"):
        raise HTTPException(400, vr.get("error", "Invalid or expired code"))
    if req.purpose == "2fa":
        return auth.issue_token_for_email(req.email.strip().lower())
    return {"ok": True, "verified": True}


@router.post("/resend-code")
def resend_code(req: ResendCodeRequest):
    code = auth.create_email_code(req.email.strip().lower(), req.purpose)
    if not code:
        raise HTTPException(429, "Please wait before requesting another code")
    _send_code_email(req.email.strip().lower(), code, req.purpose)
    return {"ok": True}


@router.get("/me")
def me(authorization: str = Header(None)):
    user = current_user_required(authorization)
    is_plus = auth.is_plus(user["id"])
    return {
        "ok": True,
        "user": {**user, "plus": is_plus, "is_admin": is_admin(user)},
        "gift_msg": auth.get_gift_msg(user["id"]) if is_plus else "",
        "messages_today": auth.messages_today(user["id"]),
    }


@router.get("/settings")
def get_settings(authorization: str = Header(None)):
    user = current_user_required(authorization)
    raw = auth.get_settings(user["id"])
    # auth.get_settings() returns the Groq/Polygon keys in plain text. Never
    # send a stored secret back to the browser — only whether one is set.
    return {
        "ok": True,
        "display_name": raw.get("display_name", ""),
        "settings": raw.get("settings", {}),
        "alpaca_connected": bool(raw.get("alpaca_key_set") and raw.get("alpaca_secret_set")),
        "groq_key_set": bool(raw.get("groq_key")),
        "polygon_key_set": bool(raw.get("polygon_key")),
    }


def _alpaca_check(key_id: str, secret: str) -> dict:
    """Read-only probe of a key pair against Alpaca's account endpoint."""
    import requests

    try:
        r = requests.get(
            f"{engine.ALPACA_BASE}/v2/account",
            headers={"APCA-API-KEY-ID": key_id, "APCA-API-SECRET-KEY": secret},
            timeout=8,
        )
    except Exception:
        return {"ok": False, "error": "Couldn't reach Alpaca — try again in a moment."}
    if r.status_code in (401, 403):
        return {"ok": False, "error": "Alpaca rejected those keys. Paula uses paper trading — use your paper account's keys."}
    if r.status_code != 200:
        return {"ok": False, "error": f"Alpaca returned {r.status_code}."}
    acct = r.json()
    return {"ok": True, "equity": float(acct.get("equity") or 0), "account_number": acct.get("account_number")}


@router.post("/settings")
def save_settings(req: SettingsRequest, authorization: str = Header(None)):
    user = current_user_required(authorization)
    current = auth.get_settings(user["id"])

    # auth.save_settings() overwrites display_name and settings_json every
    # time, so fill in anything the client didn't send from what's stored —
    # otherwise saving a key would blank your name, and saving your name
    # would wipe your preferences.
    payload = {
        "display_name": req.display_name if req.display_name is not None else current.get("display_name", ""),
        "settings": {**current.get("settings", {}), **(req.settings or {})},
        "alpaca_key": "",
        "alpaca_secret": "",
        "groq_key": "",
        "polygon_key": "",
    }

    wants_keys = any((req.alpaca_key, req.alpaca_secret, req.groq_key, req.polygon_key))
    if wants_keys and not (auth.is_plus(user["id"]) or is_admin(user)):
        raise HTTPException(403, "Connecting your own accounts is part of Paula Plus.")

    result: dict = {"ok": True}
    if req.alpaca_key or req.alpaca_secret:
        if not (req.alpaca_key and req.alpaca_secret):
            raise HTTPException(422, "Enter both the Alpaca key ID and secret.")
        check = _alpaca_check(req.alpaca_key.strip(), req.alpaca_secret.strip())
        if not check["ok"]:
            raise HTTPException(422, check["error"])
        payload["alpaca_key"] = req.alpaca_key.strip()
        payload["alpaca_secret"] = req.alpaca_secret.strip()
        result["alpaca"] = {"equity": check["equity"]}
    if req.groq_key:
        payload["groq_key"] = req.groq_key.strip()
    if req.polygon_key:
        payload["polygon_key"] = req.polygon_key.strip()

    # Note: the original also copied the keys into os.environ, which made one
    # user's broker account the fallback for every other user and guest.
    # Per-request creds (deps._resolve_user) already cover the owner.
    auth.save_settings(user["id"], payload)
    return result


@router.delete("/connections/alpaca")
def disconnect_alpaca(authorization: str = Header(None)):
    user = current_user_required(authorization)
    db = auth._get_db()
    try:
        db.execute("UPDATE user_settings SET alpaca_key = NULL, alpaca_secret = NULL WHERE user_id = ?", (user["id"],))
        db.commit()
    finally:
        db.close()
    return {"ok": True}
