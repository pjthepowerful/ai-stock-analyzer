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


@router.get("/orders")
def get_orders(status: str = "open", limit: int = 10, authorization: str = Header(None)):
    current_user_optional(authorization)
    return {"ok": True, "data": engine.alpaca_orders(status=status, limit=limit)}


@router.get("/analyze/{ticker}")
def analyze_ticker(ticker: str):
    data = engine.fetch_full(ticker.upper())
    if not data:
        raise HTTPException(404, f"No data for {ticker.upper()}")
    signal = engine.generate_trade_signal(data)
    return {"ok": True, "data": {**data, "signal": signal}}


@router.get("/portfolio/benchmark")
def portfolio_benchmark(period: str = "1M", authorization: str = Header(None)):
    current_user_optional(authorization)
    hist = engine.alpaca_portfolio_history(period=period)
    if not hist or not hist.get("equity"):
        raise HTTPException(404, "No portfolio history yet. Place some trades first.")

    ts = hist["timestamps"]
    eq = list(hist["equity"])
    base = next((e for e in eq if e), None)
    if not base:
        raise HTTPException(404, "Portfolio has no value yet.")
    port_pct = [round((e / base - 1) * 100, 2) if e else 0 for e in eq]

    import datetime as dt
    spy_pct: list[float] = []
    spy_ret = None
    try:
        start = dt.datetime.fromtimestamp(ts[0])
        end = dt.datetime.fromtimestamp(ts[-1])
        days = max((end - start).days + 2, 3)
        spy = engine._polygon_daily_hist("SPY", days=days + 5)
        if spy is not None and len(spy) >= 2:
            closes = spy["Close"].tolist()
            sbase = closes[0]
            spy_ret = round((closes[-1] / sbase - 1) * 100, 2)
            spy_pct = [round((c / sbase - 1) * 100, 2) for c in closes]
    except Exception:
        pass

    port_ret = port_pct[-1] if port_pct else 0
    return {
        "ok": True,
        "period": period,
        "portfolio_return_pct": port_ret,
        "spy_return_pct": spy_ret,
        "alpha_pct": round(port_ret - spy_ret, 2) if spy_ret is not None else None,
        "beating_market": (spy_ret is not None and port_ret > spy_ret),
        "portfolio_series": port_pct,
        "spy_series": spy_pct,
        "timestamps": ts,
    }
