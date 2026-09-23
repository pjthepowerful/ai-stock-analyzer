"""
Auth router — thin, typed wrapper around the EXISTING auth.py (password
hashing, JWT issuance, the SQLite user table). We do not touch that logic;
real user credentials are not the place to introduce new code paths.
"""
import re

from fastapi import APIRouter, Header, HTTPException

import os

from ..bridge import auth
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
    return {"ok": True, **auth.get_settings(user["id"])}


@router.post("/settings")
def save_settings(req: SettingsRequest, authorization: str = Header(None)):
    user = current_user_required(authorization)
    is_plus = auth.is_plus(user["id"]) or is_admin(user)
    payload = req.dict()
    if not is_plus:
        # Connections (broker/data API keys) are Plus-only. The UI hides
        # them, but the endpoint enforces it too so a direct POST can't
        # bypass the paywall.
        for k in ("alpaca_key", "alpaca_secret", "groq_key", "polygon_key"):
            payload.pop(k, None)
        return auth.save_settings(user["id"], payload)

    result = auth.save_settings(user["id"], payload)
    if req.alpaca_key:
        os.environ["ALPACA_KEY_ID"] = req.alpaca_key
    if req.alpaca_secret:
        os.environ["ALPACA_SECRET"] = req.alpaca_secret
    return result
