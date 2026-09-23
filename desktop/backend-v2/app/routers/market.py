"""
Market data router — quick lookups + account/positions. Calls the same
engine.* functions the original backend uses; only the HTTP layer is new.
"""
from fastapi import APIRouter, Header, HTTPException

from ..bridge import engine
from ..deps import current_user_optional

router = APIRouter(prefix="/api", tags=["market"])


@router.get("/quick/{ticker}")
def quick_lookup(ticker: str):
    data = engine.fetch_full(ticker.upper())
    if not data or not data.get("price"):
        raise HTTPException(404, f"No data for {ticker.upper()}")

    signal = engine.generate_trade_signal(data)
    price = data.get("price", 0)
    prev = data.get("prev_close", price)
    change = price - prev if prev else 0
    change_pct = (change / prev * 100) if prev else 0

    return {
        "ok": True,
        "ticker": ticker.upper(),
        "price": round(price, 2),
        "change": round(change, 2),
        "change_pct": round(change_pct, 2),
        "score": signal.get("score"),
        "signal": signal.get("action"),
    }


@router.get("/account")
def get_account(authorization: str = Header(None)):
    current_user_optional(authorization)  # applies per-user Alpaca creds
    acc = engine.alpaca_account()
    if not acc:
        raise HTTPException(502, "Couldn't reach your brokerage account. Check Alpaca keys in Settings.")
    return {"ok": True, "data": acc}


@router.get("/positions")
def get_positions(authorization: str = Header(None)):
    current_user_optional(authorization)
    return {"ok": True, "data": engine.alpaca_positions()}
