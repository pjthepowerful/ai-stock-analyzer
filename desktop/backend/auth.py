"""
Paula Auth — User accounts, API key management, JWT tokens.
Uses SQLite for storage, bcrypt for passwords, Fernet for key encryption.
"""

import os
import sqlite3
import time
from datetime import datetime, timedelta
from pathlib import Path

from passlib.context import CryptContext
from jose import jwt, JWTError
from cryptography.fernet import Fernet

# ── Config ──
DB_PATH = Path(__file__).parent / "paula.db"
JWT_SECRET = os.environ.get("JWT_SECRET", "paula-secret-change-me-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = 72

# Encryption key for API keys — derived from JWT_SECRET
_key_seed = JWT_SECRET.encode().ljust(32, b'\0')[:32]
import base64
FERNET_KEY = base64.urlsafe_b64encode(_key_seed)
fernet = Fernet(FERNET_KEY)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    """Create tables if they don't exist."""
    conn = _get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            display_name TEXT DEFAULT '',
            created_at REAL DEFAULT (strftime('%s','now')),
            last_login REAL DEFAULT 0,
            is_admin INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS api_keys (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            provider TEXT NOT NULL DEFAULT 'alpaca_paper',
            key_id_encrypted TEXT NOT NULL,
            secret_encrypted TEXT NOT NULL,
            label TEXT DEFAULT '',
            is_active INTEGER DEFAULT 1,
            created_at REAL DEFAULT (strftime('%s','now')),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS watchlist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            ticker TEXT NOT NULL,
            added_at REAL DEFAULT (strftime('%s','now')),
            notes TEXT DEFAULT '',
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            UNIQUE(user_id, ticker)
        );
    """)
    conn.commit()
    conn.close()


# ── Password hashing ──

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(password: str, hashed: str) -> bool:
    return pwd_context.verify(password, hashed)


# ── JWT tokens ──

def create_token(user_id: int, username: str) -> str:
    expire = datetime.utcnow() + timedelta(hours=JWT_EXPIRE_HOURS)
    return jwt.encode(
        {"sub": str(user_id), "username": username, "exp": expire},
        JWT_SECRET, algorithm=JWT_ALGORITHM
    )

def decode_token(token: str) -> dict | None:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return {"user_id": int(payload["sub"]), "username": payload["username"]}
    except JWTError:
        return None


# ── Encrypt/decrypt API keys ──

def encrypt_key(plaintext: str) -> str:
    return fernet.encrypt(plaintext.encode()).decode()

def decrypt_key(encrypted: str) -> str:
    return fernet.decrypt(encrypted.encode()).decode()


# ── User CRUD ──

def create_user(username: str, email: str, password: str, display_name: str = "") -> dict:
    conn = _get_db()
    try:
        conn.execute(
            "INSERT INTO users (username, email, password_hash, display_name) VALUES (?, ?, ?, ?)",
            (username.lower().strip(), email.lower().strip(), hash_password(password), display_name or username)
        )
        conn.commit()
        user_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.close()
        return {"ok": True, "user_id": user_id}
    except sqlite3.IntegrityError as e:
        conn.close()
        if "username" in str(e):
            return {"ok": False, "error": "Username already taken"}
        if "email" in str(e):
            return {"ok": False, "error": "Email already registered"}
        return {"ok": False, "error": str(e)}


def login_user(username: str, password: str) -> dict:
    conn = _get_db()
    row = conn.execute(
        "SELECT id, username, email, password_hash, display_name, is_admin FROM users WHERE username = ?",
        (username.lower().strip(),)
    ).fetchone()
    if not row:
        conn.close()
        return {"ok": False, "error": "User not found"}
    if not verify_password(password, row["password_hash"]):
        conn.close()
        return {"ok": False, "error": "Wrong password"}
    conn.execute("UPDATE users SET last_login = ? WHERE id = ?", (time.time(), row["id"]))
    conn.commit()
    conn.close()
    token = create_token(row["id"], row["username"])
    return {
        "ok": True,
        "token": token,
        "user": {
            "id": row["id"],
            "username": row["username"],
            "email": row["email"],
            "display_name": row["display_name"],
            "is_admin": bool(row["is_admin"]),
        }
    }


def get_user(user_id: int) -> dict | None:
    conn = _get_db()
    row = conn.execute(
        "SELECT id, username, email, display_name, is_admin, created_at FROM users WHERE id = ?",
        (user_id,)
    ).fetchone()
    conn.close()
    if not row:
        return None
    return {
        "id": row["id"],
        "username": row["username"],
        "email": row["email"],
        "display_name": row["display_name"],
        "is_admin": bool(row["is_admin"]),
        "created_at": row["created_at"],
    }


# ── API Key management ──

def save_api_keys(user_id: int, provider: str, key_id: str, secret: str, label: str = "") -> dict:
    conn = _get_db()
    # Deactivate old keys for same provider
    conn.execute(
        "UPDATE api_keys SET is_active = 0 WHERE user_id = ? AND provider = ?",
        (user_id, provider)
    )
    conn.execute(
        "INSERT INTO api_keys (user_id, provider, key_id_encrypted, secret_encrypted, label) VALUES (?, ?, ?, ?, ?)",
        (user_id, provider, encrypt_key(key_id), encrypt_key(secret), label)
    )
    conn.commit()
    conn.close()
    return {"ok": True}


def get_api_keys(user_id: int, provider: str = "alpaca_paper") -> dict | None:
    conn = _get_db()
    row = conn.execute(
        "SELECT key_id_encrypted, secret_encrypted, label FROM api_keys WHERE user_id = ? AND provider = ? AND is_active = 1 ORDER BY id DESC LIMIT 1",
        (user_id, provider)
    ).fetchone()
    conn.close()
    if not row:
        return None
    return {
        "key_id": decrypt_key(row["key_id_encrypted"]),
        "secret": decrypt_key(row["secret_encrypted"]),
        "label": row["label"],
    }


def get_user_providers(user_id: int) -> list:
    conn = _get_db()
    rows = conn.execute(
        "SELECT DISTINCT provider, label, created_at FROM api_keys WHERE user_id = ? AND is_active = 1",
        (user_id,)
    ).fetchall()
    conn.close()
    return [{"provider": r["provider"], "label": r["label"], "connected_at": r["created_at"]} for r in rows]


def delete_api_keys(user_id: int, provider: str) -> dict:
    conn = _get_db()
    conn.execute(
        "UPDATE api_keys SET is_active = 0 WHERE user_id = ? AND provider = ?",
        (user_id, provider)
    )
    conn.commit()
    conn.close()
    return {"ok": True}


# ── Watchlist ──

def get_watchlist(user_id: int) -> list:
    conn = _get_db()
    rows = conn.execute(
        "SELECT ticker, notes, added_at FROM watchlist WHERE user_id = ? ORDER BY added_at DESC",
        (user_id,)
    ).fetchall()
    conn.close()
    return [{"ticker": r["ticker"], "notes": r["notes"], "added_at": r["added_at"]} for r in rows]


def add_to_watchlist(user_id: int, ticker: str, notes: str = "") -> dict:
    conn = _get_db()
    try:
        conn.execute(
            "INSERT INTO watchlist (user_id, ticker, notes) VALUES (?, ?, ?)",
            (user_id, ticker.upper().strip(), notes)
        )
        conn.commit()
        conn.close()
        return {"ok": True}
    except sqlite3.IntegrityError:
        conn.close()
        return {"ok": False, "error": f"{ticker} already in watchlist"}


def remove_from_watchlist(user_id: int, ticker: str) -> dict:
    conn = _get_db()
    conn.execute(
        "DELETE FROM watchlist WHERE user_id = ? AND ticker = ?",
        (user_id, ticker.upper().strip())
    )
    conn.commit()
    conn.close()
    return {"ok": True}


# ── Init on import ──
init_db()
print("✅ Auth database ready")
