"""
Placing orders from chat. A buy/sell/short/cover message never trades by
itself: chat answers with a confirm card, and only the Confirm button calls
POST /api/trade/execute — so a single (possibly misread) message can't place
an order. Ported from the original backend's /api/trade/execute with one
tightening: an account without its own broker keys would fall back to the
shared account, so only the allowlisted owners may trade without keys.
"""
import asyncio
from typing import Literal, Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from ..bridge import engine
from ..deps import current_user_required, has_broker, in_request_context
from ..services.trade_log import log_trade
from ..ws import manager

router = APIRouter(prefix="/api/trade", tags=["trade"])


class TradeRequest(BaseModel):
    action: Literal["buy", "sell", "short", "cover", "cancel_orders", "close_all"]
    ticker: str = ""
    qty: Optional[float] = Field(default=None, gt=0)
    notional: Optional[float] = Field(default=None, gt=0)
    smart: bool = False
    sell_all: bool = False
    cover_all: bool = False


def _clean_error(msg: str) -> str:
    lc = (msg or "").lower()
    if any(s in lc for s in ("no day trades permitted", "previous day account equity", "pattern day trader")):
        return "Order rejected"
    return (msg or "Order failed")[:160]


def _place(req: TradeRequest) -> dict:
    t = req.ticker
    if req.action == "cancel_orders":
        r = engine.alpaca_cancel_all_orders()
        if r.get("ok"):
            n = r.get("count")
            return {"ok": True, "message": f"Cancelled {n if n is not None else 'all'} open order{'' if n == 1 else 's'}. Your positions are untouched."}
        return r
    if req.action == "close_all":
        r = engine.alpaca_close_all()
        return {**r, "message": "Closed all positions — your portfolio is flat."} if r.get("ok") else r
    if req.action == "buy":
        if req.smart:
            data = engine.fetch_full(t)
            if data:
                r = engine.alpaca_smart_buy(ticker=t, trade_signal=engine.generate_trade_signal(data))
                if r.get("ok"):
                    return {**r, "message": f"Bought {r.get('qty_calculated', req.qty)} shares of {t} (risk-sized) · {r.get('status', 'submitted')}"}
                return r
        r = engine.alpaca_buy(ticker=t, qty=req.qty, notional=req.notional)
        if r.get("ok"):
            what = f"{r.get('qty', req.qty)} shares" if (r.get("qty") or req.qty) else f"${req.notional}"
            return {**r, "message": f"Bought {what} of {t} · {r.get('status', 'submitted')}"}
        return r
    if req.action == "sell":
        r = engine.alpaca_sell(ticker=t, qty=req.qty, sell_all=req.sell_all)
        if r.get("ok"):
            act = "Closed your position in" if req.sell_all else f"Sold {req.qty or r.get('qty', '')} shares of"
            return {**r, "message": f"{act} {t} · {r.get('status', 'submitted')}"}
        return r
    if req.action == "short":
        r = engine.alpaca_short(ticker=t, qty=req.qty or 1)
        if r.get("ok"):
            return {**r, "message": f"Shorted {req.qty or 1} shares of {t} · {r.get('status', 'submitted')}"}
        return r
    r = engine.alpaca_cover(ticker=t, qty=req.qty, cover_all=req.cover_all)
    if r.get("ok"):
        act = "Covered all of" if req.cover_all else f"Covered {req.qty or r.get('qty', '')} shares of"
        return {**r, "message": f"{act} {t} (short closed) · {r.get('status', 'submitted')}"}
    return r


@router.post("/execute")
async def execute(req: TradeRequest, authorization: str = Header(None)):
    user = current_user_required(authorization)   # also applies the user's own broker keys
    if not has_broker(user):
        raise HTTPException(403, "Connect your Alpaca account in Settings to place orders.")

    req.ticker = req.ticker.strip().upper()
    if req.action not in ("cancel_orders", "close_all") and not (req.ticker and req.ticker.replace(".", "").replace("-", "").isalnum() and len(req.ticker) <= 10):
        raise HTTPException(400, "Invalid ticker")

    loop = asyncio.get_running_loop()
    try:
        result = await loop.run_in_executor(None, in_request_context(_place, req)) or {}
    except Exception as e:
        return {"ok": False, "error": _clean_error(str(e))}
    if not result.get("ok"):
        return {"ok": False, "error": _clean_error(result.get("error", ""))}

    log_trade(req.action, req.ticker or "ALL", qty=req.qty or result.get("qty") or 0,
              price=result.get("avg_price") or result.get("price") or 0, extra={"source": "chat", "user_id": user["id"]})
    try:
        await manager.broadcast("trade", {"action": req.action})
    except Exception:
        pass
    return {"ok": True, "message": result.get("message", "Order submitted")}
