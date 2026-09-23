"""
Market overview for the strip above the chat: regime (SPY trend, VIX), the
day's top mover each way, and a small tape of daily % moves. Ported from the
original's /api/market-regime and /api/tape, merged into one call and cached
for 60s since every open client polls it.
"""
import threading
import time
import warnings

from fastapi import APIRouter

from ..bridge import engine

router = APIRouter(prefix="/api/market", tags=["market"])

TAPE_SYMBOLS = ["SPY", "QQQ", "IWM", "NVDA", "AAPL", "MSFT", "AMZN", "META", "TSLA", "GOOGL", "AMD", "AVGO"]
TTL = 60

_cache: dict = {"at": 0.0, "data": None}
_lock = threading.Lock()


def _movers() -> tuple[dict | None, dict | None]:
    def row(r):
        return {"ticker": r["Ticker"], "chg": r["Chg%"], "price": r["Price"]}

    gainer = loser = None
    try:
        g = engine.polygon_gainers(limit=1)
        gainer = row(g[0]) if g else None
    except Exception:
        pass
    try:
        l = engine.polygon_losers(limit=1)
        loser = row(l[0]) if l else None
    except Exception:
        pass
    if gainer is None and loser is None:
        # Polygon's snapshot endpoints need a paid plan; fall back to Yahoo.
        try:
            mv = engine.yahoo_top_movers()
            gainer = row(mv["gainer"]) if mv.get("gainer") else None
            loser = row(mv["loser"]) if mv.get("loser") else None
        except Exception:
            pass
    return gainer, loser


def _tape() -> list[dict]:
    import yfinance as yf

    out = []
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        data = yf.download(TAPE_SYMBOLS, period="5d", interval="1d", progress=False, group_by="ticker", threads=True)
    for s in TAPE_SYMBOLS:
        try:
            closes = data[s]["Close"].dropna()
            if len(closes) >= 2:
                last, prev = float(closes.iloc[-1]), float(closes.iloc[-2])
                out.append({"sym": s, "price": round(last, 2), "pct": round((last / prev - 1) * 100, 2)})
        except Exception:
            continue
    return out


def _build() -> dict:
    regime = {}
    try:
        regime = engine.check_market_regime() or {}
    except Exception:
        pass
    gainer, loser = _movers()
    try:
        tape = _tape()
    except Exception:
        tape = []
    return {
        "regime": regime.get("regime"),
        "safe_to_buy": regime.get("safe_to_buy"),
        "reason": regime.get("reason"),
        "spy": {"price": regime.get("spy_price"), "pct": regime.get("spy_change_pct")},
        "vix": regime.get("vix"),
        "rsi": regime.get("rsi"),
        "top_gainer": gainer,
        "top_loser": loser,
        "tape": tape,
    }


@router.get("/overview")
def overview():
    # Plain def → runs in the threadpool; the lock stops a burst of clients
    # from each kicking off the same slow yfinance/Polygon round.
    with _lock:
        if _cache["data"] and time.time() - _cache["at"] < TTL:
            return {"ok": True, "cached": True, **_cache["data"]}
        data = _build()
        # Don't cache an all-empty result; the next request should retry.
        if data["regime"] or data["tape"]:
            _cache.update(at=time.time(), data=data)
        return {"ok": True, "cached": False, **data}
