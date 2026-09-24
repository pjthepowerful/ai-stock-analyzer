"""
What people are actually looking up. Every successful Analyze lookup (and
every stock analysis asked for in chat) is recorded; "popular" is the tickers
the most distinct people looked at over the last 7 days, so one person
refreshing a ticker can't push it up the list.

Stored in the shared SQLite database (its own table), keyed by a salted hash
of the user id / IP — never the raw identity.
"""
import hashlib
import os
import threading
import time

from ..bridge import auth

WINDOW_DAYS = 7
DEFAULTS = ["AAPL", "NVDA", "MSFT", "TSLA", "AMZN", "META", "SPY"]
_SALT = os.environ.get("JWT_SECRET", "paula")
_init_lock = threading.Lock()
_ready = False
_cache: dict = {"at": 0.0, "data": None}
CACHE_TTL = 60


def _ensure_table() -> None:
    global _ready
    if _ready:
        return
    with _init_lock:
        if _ready:
            return
        db = auth._get_db()
        try:
            db.execute(
                """CREATE TABLE IF NOT EXISTS ticker_lookups (
                       ticker TEXT NOT NULL,
                       who    TEXT NOT NULL,
                       day    TEXT NOT NULL,
                       at     REAL NOT NULL,
                       PRIMARY KEY (ticker, who, day)
                   )"""
            )
            db.execute("CREATE INDEX IF NOT EXISTS idx_ticker_lookups_at ON ticker_lookups(at)")
            db.commit()
        finally:
            db.close()
        _ready = True


def _who(user_id, ip: str | None) -> str:
    raw = f"u:{user_id}" if user_id else f"ip:{ip or 'unknown'}"
    return hashlib.sha256(f"{_SALT}|{raw}".encode()).hexdigest()[:16]


def record(ticker: str, user_id=None, ip: str | None = None) -> None:
    """Count one person looking at one ticker (at most once per day each)."""
    t = (ticker or "").strip().upper()
    if not t or len(t) > 10:
        return
    try:
        _ensure_table()
        db = auth._get_db()
        try:
            db.execute(
                "INSERT OR IGNORE INTO ticker_lookups (ticker, who, day, at) VALUES (?, ?, date('now'), ?)",
                (t, _who(user_id, ip), time.time()),
            )
            db.commit()
        finally:
            db.close()
    except Exception as e:  # never let analytics break a lookup
        print(f"[popularity] record failed: {e!r}", flush=True)


def popular(limit: int = 7) -> list[dict]:
    """Trending tickers, most distinct lookers first, padded with defaults."""
    now = time.time()
    if _cache["data"] is not None and now - _cache["at"] < CACHE_TTL:
        rows = _cache["data"]
    else:
        rows = []
        try:
            _ensure_table()
            db = auth._get_db()
            try:
                rows = [
                    {"ticker": r[0], "people": r[1]}
                    for r in db.execute(
                        """SELECT ticker, COUNT(DISTINCT who) AS people
                           FROM ticker_lookups WHERE at >= ?
                           GROUP BY ticker ORDER BY people DESC, MAX(at) DESC LIMIT 20""",
                        (now - WINDOW_DAYS * 86400,),
                    ).fetchall()
                ]
            finally:
                db.close()
        except Exception as e:
            print(f"[popularity] query failed: {e!r}", flush=True)
        _cache.update(at=now, data=rows)

    out = [dict(r, trending=True) for r in rows[:limit]]
    for t in DEFAULTS:
        if len(out) >= limit:
            break
        if all(o["ticker"] != t for o in out):
            out.append({"ticker": t, "people": 0, "trending": False})
    return out
