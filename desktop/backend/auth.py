"""
Paula Auth System — SQLite + JWT + PBKDF2 hashing
No bcrypt dependency — works on Python 3.14
"""
import sqlite3
import hashlib
import secrets
import json
import time
import hmac
import base64
import os
from pathlib import Path
from datetime import datetime, timedelta

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "paula.db")
JWT_SECRET = os.environ.get("JWT_SECRET", secrets.token_hex(32))
TOKEN_EXPIRY_DAYS = 30


def _get_db():
    db = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=10)
    db.row_factory = sqlite3.Row
    return db


def init_db():
    """Create tables if they don't exist."""
    db = _get_db()
    db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL COLLATE NOCASE,
            email TEXT UNIQUE,
            password_hash TEXT NOT NULL,
            salt TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            last_login TEXT
        );
        CREATE TABLE IF NOT EXISTS user_settings (
            user_id INTEGER PRIMARY KEY,
            alpaca_key TEXT DEFAULT '',
            alpaca_secret TEXT DEFAULT '',
            groq_key TEXT DEFAULT '',
            polygon_key TEXT DEFAULT '',
            display_name TEXT DEFAULT '',
            settings_json TEXT DEFAULT '{}',
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            msg_type TEXT DEFAULT 'chat',
            ticker TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS password_resets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            token_hash TEXT NOT NULL,
            expires_at INTEGER NOT NULL,
            used INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
    """)
    db.commit()
    db.close()


def _hash_password(password: str, salt: str = None) -> tuple:
    """Hash password with PBKDF2-SHA256. Returns (hash, salt)."""
    if not salt:
        salt = secrets.token_hex(16)
    pw_hash = hashlib.pbkdf2_hmac(
        'sha256', password.encode(), salt.encode(), 100_000
    ).hex()
    return pw_hash, salt


def _make_jwt(payload: dict) -> str:
    """Create a simple JWT token."""
    header = base64.urlsafe_b64encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode()).decode().rstrip("=")
    payload["exp"] = int(time.time()) + TOKEN_EXPIRY_DAYS * 86400
    body = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    sig = hmac.new(JWT_SECRET.encode(), f"{header}.{body}".encode(), hashlib.sha256).hexdigest()
    return f"{header}.{body}.{sig}"


def _verify_jwt(token: str) -> dict | None:
    """Verify and decode a JWT token."""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        header, body, sig = parts
        expected_sig = hmac.new(JWT_SECRET.encode(), f"{header}.{body}".encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected_sig):
            return None
        # Pad base64
        body += "=" * (4 - len(body) % 4)
        payload = json.loads(base64.urlsafe_b64decode(body))
        if payload.get("exp", 0) < time.time():
            return None
        return payload
    except Exception:
        return None


def signup(username: str, password: str, email: str = None) -> dict:
    """Create a new user."""
    if not username or len(username) < 2:
        return {"ok": False, "error": "Username must be at least 2 characters"}
    if not password or len(password) < 4:
        return {"ok": False, "error": "Password must be at least 4 characters"}

    pw_hash, salt = _hash_password(password)
    email = email.strip().lower() if email else None
    db = _get_db()
    try:
        db.execute("INSERT INTO users (username, email, password_hash, salt) VALUES (?, ?, ?, ?)",
                   (username, email, pw_hash, salt))
        user_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        db.execute("INSERT INTO user_settings (user_id, display_name) VALUES (?, ?)",
                   (user_id, username))
        db.commit()
        token = _make_jwt({"user_id": user_id, "username": username, "email": email or ""})
        return {"ok": True, "token": token, "user": {"id": user_id, "username": username, "email": email or ""}}
    except sqlite3.IntegrityError as e:
        if "email" in str(e).lower():
            return {"ok": False, "error": "An account with this email already exists"}
        return {"ok": False, "error": "An account with this name already exists"}
    finally:
        db.close()


def login(username: str, password: str) -> dict:
    """Authenticate a user. Accepts username or email (email is case-insensitive)."""
    db = _get_db()
    try:
        ident = (username or "").strip()
        row = db.execute(
            "SELECT * FROM users WHERE username = ? OR email = ?",
            (ident, ident.lower())
        ).fetchone()
        if not row:
            return {"ok": False, "error": "No account found with this email"}
        pw_hash, _ = _hash_password(password, row["salt"])
        if pw_hash != row["password_hash"]:
            return {"ok": False, "error": "Incorrect password"}
        db.execute("UPDATE users SET last_login = ? WHERE id = ?",
                   (datetime.utcnow().isoformat(), row["id"]))
        db.commit()
        token = _make_jwt({"user_id": row["id"], "username": row["username"], "email": row["email"] or ""})
        return {"ok": True, "token": token, "user": {"id": row["id"], "username": row["username"], "email": row["email"] or ""}}
    finally:
        db.close()


def get_user(token: str) -> dict | None:
    """Get user from JWT token."""
    payload = _verify_jwt(token)
    if not payload:
        return None
    return {"id": payload["user_id"], "username": payload["username"], "email": payload.get("email", "")}


def get_settings(user_id: int) -> dict:
    """Get user settings."""
    db = _get_db()
    try:
        row = db.execute("SELECT * FROM user_settings WHERE user_id = ?", (user_id,)).fetchone()
        if not row:
            return {}
        return {
            "alpaca_key": row["alpaca_key"] or "",
            "alpaca_secret": row["alpaca_secret"] or "",
            "groq_key": row["groq_key"] or "",
            "polygon_key": row["polygon_key"] or "",
            "display_name": row["display_name"] or "",
            "settings": json.loads(row["settings_json"] or "{}"),
        }
    finally:
        db.close()


def save_settings(user_id: int, settings: dict) -> dict:
    """Save user settings."""
    db = _get_db()
    try:
        db.execute("""
            UPDATE user_settings SET
                alpaca_key = ?, alpaca_secret = ?, groq_key = ?, polygon_key = ?,
                display_name = ?, settings_json = ?
            WHERE user_id = ?
        """, (
            settings.get("alpaca_key", ""),
            settings.get("alpaca_secret", ""),
            settings.get("groq_key", ""),
            settings.get("polygon_key", ""),
            settings.get("display_name", ""),
            json.dumps(settings.get("settings", {})),
            user_id,
        ))
        db.commit()
        return {"ok": True}
    finally:
        db.close()


def save_chat(user_id: int, role: str, content: str, msg_type: str = "chat", ticker: str = None):
    """Save a chat message. Never raises — DB errors are silently ignored."""
    try:
        db = _get_db()
        db.execute("INSERT INTO chat_history (user_id, role, content, msg_type, ticker) VALUES (?, ?, ?, ?, ?)",
                   (user_id, role, content, msg_type, ticker))
        db.commit()
        db.close()
    except Exception:
        pass


def get_chat_history(user_id: int, limit: int = 50) -> list:
    """Get recent chat history."""
    db = _get_db()
    try:
        rows = db.execute(
            "SELECT role, content, msg_type, ticker, created_at FROM chat_history WHERE user_id = ? ORDER BY id DESC LIMIT ?",
            (user_id, limit)
        ).fetchall()
        return [{"role": r["role"], "content": r["content"], "type": r["msg_type"],
                 "ticker": r["ticker"], "time": r["created_at"]} for r in reversed(rows)]
    finally:
        db.close()


def clear_chat(user_id: int):
    """Clear chat history for a user."""
    db = _get_db()
    try:
        db.execute("DELETE FROM chat_history WHERE user_id = ?", (user_id,))
        db.commit()
    finally:
        db.close()


# ── Password reset ──────────────────────────────────────────────────────────
RESET_TOKEN_TTL_SECONDS = 3600  # 1 hour


def _hash_token(token: str) -> str:
    """Hash a reset token before storing it (never store the raw token)."""
    return hashlib.sha256(token.encode()).hexdigest()


def create_reset_token(email: str) -> dict | None:
    """Create a one-time reset token for the account with this email.

    Returns {"token": ..., "email": ..., "username": ...} for the caller to
    email, or None if no such account exists. The caller must NOT reveal to the
    client whether an account was found (anti-enumeration).
    """
    if not email:
        return None
    db = _get_db()
    try:
        row = db.execute("SELECT id, username, email FROM users WHERE email = ?",
                         (email.strip().lower(),)).fetchone()
        if not row:
            return None
        token = secrets.token_urlsafe(32)
        expires_at = int(time.time()) + RESET_TOKEN_TTL_SECONDS
        # Invalidate any prior outstanding tokens for this user
        db.execute("UPDATE password_resets SET used = 1 WHERE user_id = ? AND used = 0", (row["id"],))
        db.execute("INSERT INTO password_resets (user_id, token_hash, expires_at) VALUES (?, ?, ?)",
                   (row["id"], _hash_token(token), expires_at))
        db.commit()
        return {"token": token, "email": row["email"], "username": row["username"]}
    finally:
        db.close()


def reset_password(token: str, new_password: str) -> dict:
    """Consume a reset token and set a new password."""
    if not token:
        return {"ok": False, "error": "Invalid or expired reset link"}
    if not new_password or len(new_password) < 6:
        return {"ok": False, "error": "Password must be at least 6 characters"}
    db = _get_db()
    try:
        row = db.execute(
            "SELECT id, user_id, expires_at, used FROM password_resets WHERE token_hash = ?",
            (_hash_token(token),)
        ).fetchone()
        if not row or row["used"]:
            return {"ok": False, "error": "Invalid or expired reset link"}
        if row["expires_at"] < int(time.time()):
            return {"ok": False, "error": "This reset link has expired"}
        pw_hash, salt = _hash_password(new_password)
        db.execute("UPDATE users SET password_hash = ?, salt = ? WHERE id = ?",
                   (pw_hash, salt, row["user_id"]))
        db.execute("UPDATE password_resets SET used = 1 WHERE id = ?", (row["id"],))
        db.commit()
        return {"ok": True}
    finally:
        db.close()


# Initialize on import
init_db()
