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

# DB location: use DB_DIR (a Railway persistent volume) if set, so the database
# survives redeploys. Falls back to the code directory for local dev.
_DB_DIR = os.environ.get("DB_DIR", os.path.dirname(os.path.abspath(__file__)))
try:
    os.makedirs(_DB_DIR, exist_ok=True)
except Exception:
    _DB_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(_DB_DIR, "paula.db")

# JWT secret MUST be stable across restarts, or every redeploy invalidates all
# existing login tokens (everyone gets logged out / "invalid account"). Set
# JWT_SECRET in the host env. The random fallback is dev-only.
JWT_SECRET = os.environ.get("JWT_SECRET")
if not JWT_SECRET:
    import warnings as _w
    _w.warn("JWT_SECRET not set — using a random secret; logins won't survive restarts. Set JWT_SECRET in env for hosting.")
    JWT_SECRET = secrets.token_hex(32)
TOKEN_EXPIRY_DAYS = 30

# ── Encryption for stored API secrets (Alpaca keys) ──
# Derive a Fernet key from JWT_SECRET so secrets aren't stored in plaintext.
# Tied to JWT_SECRET (already required to be stable in hosting), so no new env
# var. If decryption ever fails (e.g. secret rotated), we treat the key as unset.
def _fernet():
    from cryptography.fernet import Fernet
    digest = hashlib.sha256(("paula-keys::" + JWT_SECRET).encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))

def encrypt_secret(plain: str) -> str:
    if not plain:
        return ""
    try:
        return _fernet().encrypt(plain.encode()).decode()
    except Exception:
        return ""

def decrypt_secret(token: str) -> str:
    if not token:
        return ""
    try:
        return _fernet().decrypt(token.encode()).decode()
    except Exception:
        return ""  # not decryptable (plaintext legacy or rotated secret)


def is_plus(user_id: int) -> bool:
    """Whether the user has Paula Plus."""
    db = _get_db()
    try:
        row = db.execute("SELECT plus FROM users WHERE id = ?", (user_id,)).fetchone()
        return bool(row and row["plus"])
    finally:
        db.close()


def set_plus(user_id: int, on: bool = True, gift_msg: str = None) -> bool:
    db = _get_db()
    try:
        if on:
            db.execute("UPDATE users SET plus = 1, plus_gift_msg = ? WHERE id = ?",
                       ((gift_msg or "")[:300], user_id))
        else:
            db.execute("UPDATE users SET plus = 0, plus_gift_msg = '' WHERE id = ?", (user_id,))
        db.commit()
        return True
    finally:
        db.close()


def get_gift_msg(user_id: int) -> str:
    db = _get_db()
    try:
        row = db.execute("SELECT plus_gift_msg FROM users WHERE id = ?", (user_id,)).fetchone()
        return (row["plus_gift_msg"] if row and "plus_gift_msg" in row.keys() else "") or ""
    finally:
        db.close()


def messages_today(user_id: int) -> int:
    """Count this user's messages sent today (for the free-tier daily limit)."""
    db = _get_db()
    try:
        row = db.execute(
            "SELECT COUNT(*) AS c FROM chat_history WHERE user_id = ? AND role = 'user' "
            "AND date(created_at) = date('now')",
            (user_id,),
        ).fetchone()
        return int(row["c"]) if row else 0
    finally:
        db.close()


def get_user_alpaca_creds(user_id: int) -> dict:
    """Return a user's decrypted Alpaca creds, or empty strings if unset."""
    db = _get_db()
    try:
        row = db.execute("SELECT alpaca_key, alpaca_secret FROM user_settings WHERE user_id = ?", (user_id,)).fetchone()
        if not row:
            return {"key_id": "", "secret": ""}
        return {"key_id": decrypt_secret(row["alpaca_key"] or ""),
                "secret": decrypt_secret(row["alpaca_secret"] or "")}
    finally:
        db.close()


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
        CREATE TABLE IF NOT EXISTS email_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL,
            code_hash TEXT NOT NULL,
            purpose TEXT NOT NULL,
            expires_at INTEGER NOT NULL,
            used INTEGER DEFAULT 0,
            attempts INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
    """)
    db.commit()

    # Migration: add email_verified + twofa_enabled columns if missing
    try:
        cols = [r["name"] for r in db.execute("PRAGMA table_info(users)").fetchall()]
        if "email_verified" not in cols:
            db.execute("ALTER TABLE users ADD COLUMN email_verified INTEGER DEFAULT 0")
        if "twofa_enabled" not in cols:
            db.execute("ALTER TABLE users ADD COLUMN twofa_enabled INTEGER DEFAULT 1")
        if "plus" not in cols:
            db.execute("ALTER TABLE users ADD COLUMN plus INTEGER DEFAULT 0")
        if "plus_gift_msg" not in cols:
            db.execute("ALTER TABLE users ADD COLUMN plus_gift_msg TEXT DEFAULT ''")
        db.commit()
    except Exception:
        pass

    # Migration: drop UNIQUE constraint on username (allow duplicate names; only email unique)
    try:
        ddl_row = db.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='users'"
        ).fetchone()
        ddl = (ddl_row[0] if ddl_row else "") or ""
        if "username TEXT UNIQUE" in ddl:
            db.executescript("""
                PRAGMA foreign_keys=off;
                BEGIN TRANSACTION;
                CREATE TABLE users_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL COLLATE NOCASE,
                    email TEXT UNIQUE,
                    password_hash TEXT NOT NULL,
                    salt TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    last_login TEXT
                );
                INSERT INTO users_new (id, username, email, password_hash, salt, created_at, last_login)
                    SELECT id, username, email, password_hash, salt, created_at, last_login FROM users;
                DROP TABLE users;
                ALTER TABLE users_new RENAME TO users;
                COMMIT;
                PRAGMA foreign_keys=on;
            """)
            db.commit()
    except Exception:
        pass

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
    """Create a new user. Email is required and must be unique; usernames may repeat."""
    if not username or len(username) < 2:
        return {"ok": False, "error": "Name must be at least 2 characters"}
    if not password or len(password) < 4:
        return {"ok": False, "error": "Password must be at least 4 characters"}
    email = email.strip().lower() if email else None
    if not email:
        return {"ok": False, "error": "Email is required"}
    import re as _re
    if not _re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", email):
        return {"ok": False, "error": "Enter a valid email address"}

    pw_hash, salt = _hash_password(password)
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
        return {"ok": False, "error": "Could not create account"}
    finally:
        db.close()


def login(username: str, password: str) -> dict:
    """Authenticate a user by email + password. Email is case-insensitive."""
    db = _get_db()
    try:
        ident = (username or "").strip().lower()
        if not ident:
            return {"ok": False, "error": "Enter your email"}
        import re as _re
        if not _re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", ident):
            return {"ok": False, "error": "Enter a valid email address"}
        row = db.execute("SELECT * FROM users WHERE email = ?", (ident,)).fetchone()
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
            # Never expose stored secrets back to the client — just signal whether
            # each is configured so the UI can show "saved".
            "alpaca_key_set": bool(row["alpaca_key"]),
            "alpaca_secret_set": bool(row["alpaca_secret"]),
            "groq_key": row["groq_key"] or "",
            "polygon_key": row["polygon_key"] or "",
            "display_name": row["display_name"] or "",
            "settings": json.loads(row["settings_json"] or "{}"),
        }
    finally:
        db.close()


def save_settings(user_id: int, settings: dict) -> dict:
    """Save user settings. Empty key fields are treated as 'keep existing' so
    the UI never has to pre-load (and expose) saved secrets just to re-save."""
    db = _get_db()
    try:
        # For secret fields, NULLIF('', ...) + COALESCE keeps the old value when
        # the incoming field is blank.
        db.execute("""
            UPDATE user_settings SET
                alpaca_key    = COALESCE(NULLIF(?, ''), alpaca_key),
                alpaca_secret = COALESCE(NULLIF(?, ''), alpaca_secret),
                groq_key      = COALESCE(NULLIF(?, ''), groq_key),
                polygon_key   = COALESCE(NULLIF(?, ''), polygon_key),
                display_name  = ?,
                settings_json = ?
            WHERE user_id = ?
        """, (
            encrypt_secret(settings.get("alpaca_key", "")) if settings.get("alpaca_key", "") else "",
            encrypt_secret(settings.get("alpaca_secret", "")) if settings.get("alpaca_secret", "") else "",
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


CODE_TTL_SECONDS = 600  # 6-digit codes valid 10 minutes

def _hash_code(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()


def create_email_code(email: str, purpose: str) -> str | None:
    """Generate a 6-digit code for 'verify' (signup) or '2fa' (login). Stores the
    hash; returns the raw code for the caller to email. Invalidates prior codes."""
    if not email:
        return None
    email = email.strip().lower()
    code = f"{secrets.randbelow(1000000):06d}"
    db = _get_db()
    try:
        db.execute("UPDATE email_codes SET used = 1 WHERE email = ? AND purpose = ? AND used = 0",
                   (email, purpose))
        db.execute(
            "INSERT INTO email_codes (email, code_hash, purpose, expires_at) VALUES (?, ?, ?, ?)",
            (email, _hash_code(code), purpose, int(time.time()) + CODE_TTL_SECONDS),
        )
        db.commit()
        return code
    finally:
        db.close()


def verify_email_code(email: str, code: str, purpose: str) -> dict:
    """Check a 6-digit code. On success for 'verify', marks the user verified."""
    if not email or not code:
        return {"ok": False, "error": "Enter the 6-digit code"}
    email = email.strip().lower()
    code = code.strip()
    db = _get_db()
    try:
        row = db.execute(
            "SELECT id, code_hash, expires_at, used, attempts FROM email_codes "
            "WHERE email = ? AND purpose = ? AND used = 0 ORDER BY id DESC LIMIT 1",
            (email, purpose),
        ).fetchone()
        if not row:
            return {"ok": False, "error": "No active code — request a new one"}
        if row["attempts"] >= 5:
            db.execute("UPDATE email_codes SET used = 1 WHERE id = ?", (row["id"],))
            db.commit()
            return {"ok": False, "error": "Too many attempts — request a new code"}
        if row["expires_at"] < int(time.time()):
            return {"ok": False, "error": "Code expired — request a new one"}
        if _hash_code(code) != row["code_hash"]:
            db.execute("UPDATE email_codes SET attempts = attempts + 1 WHERE id = ?", (row["id"],))
            db.commit()
            return {"ok": False, "error": "Incorrect code"}
        db.execute("UPDATE email_codes SET used = 1 WHERE id = ?", (row["id"],))
        if purpose == "verify":
            db.execute("UPDATE users SET email_verified = 1 WHERE email = ?", (email,))
        db.commit()
        return {"ok": True}
    finally:
        db.close()


def issue_token_for_email(email: str) -> dict:
    """Issue a session token for an already-authenticated email (used after a
    2FA code is verified — the password was already checked in login())."""
    if not email:
        return {"ok": False, "error": "Missing email"}
    db = _get_db()
    try:
        row = db.execute("SELECT * FROM users WHERE email = ?", (email.strip().lower(),)).fetchone()
        if not row:
            return {"ok": False, "error": "Account not found"}
        db.execute("UPDATE users SET last_login = ? WHERE id = ?",
                   (datetime.utcnow().isoformat(), row["id"]))
        db.commit()
        token = _make_jwt({"user_id": row["id"], "username": row["username"], "email": row["email"] or ""})
        return {"ok": True, "token": token,
                "user": {"id": row["id"], "username": row["username"], "email": row["email"] or ""}}
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
