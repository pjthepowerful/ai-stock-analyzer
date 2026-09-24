"""
Market data router — quick lookups + account/positions. Calls the same
engine.* functions the original backend uses; only the HTTP layer is new.
"""
from fastapi import APIRouter, Header, HTTPException, Request

from ..bridge import engine
from ..deps import current_user_optional, current_user_required
from ..services import popularity
from ..services.ttl import TTLCache

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


_analyze_cache = TTLCache(ttl=60)


class _NoData(Exception):
    pass


@router.get("/tickers/popular")
def popular_tickers(limit: int = 7):
    """What people are actually looking up this week (see services/popularity)."""
    return {"ok": True, "tickers": popularity.popular(max(1, min(limit, 20)))}


@router.get("/analyze/{ticker}")
def analyze_ticker(ticker: str, request: Request, authorization: str = Header(None)):
    t = ticker.strip().upper()
    if not t or len(t) > 10 or not t.replace(".", "").replace("-", "").isalnum():
        raise HTTPException(422, "Not a valid ticker")

    def build():
        data = engine.fetch_full(t)
        if not data:
            raise _NoData()
        return {**data, "signal": engine.generate_trade_signal(data)}

    try:
        # Quotes/signals barely move inside a minute; re-opening a ticker you
        # just viewed shouldn't redo every upstream call.
        data = _analyze_cache.get_or_set(t, build)
        user = current_user_optional(authorization)
        popularity.record(t, user_id=(user or {}).get("id"), ip=request.client.host if request.client else None)
        return {"ok": True, "data": data}
    except _NoData:
        raise HTTPException(404, f"No data for {t}") from None


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
        # _polygon_daily_hist returns None for < 50 bars (it's built for the
        # indicator pipeline), so always fetch a long window and slice it.
        spy = engine._polygon_daily_hist("SPY", days=max(days + 5, 120))
        if spy is not None:
            spy = spy[spy.index >= start.replace(hour=0, minute=0, second=0)]
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


_PERIOD_DAYS = {"1D": 1, "1W": 7, "1M": 30, "3M": 90, "6M": 180, "1A": 365}


@router.get("/portfolio/performance")
def portfolio_performance(period: str = "1M", authorization: str = Header(None)):
    """Equity curve + trade activity for the Portfolio screen. Port of the
    original /api/performance, minus the autopilot config dump, and behind
    sign-in (the original serves account data to anyone)."""
    from collections import defaultdict
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo

    import requests

    current_user_required(authorization)
    if period not in _PERIOD_DAYS:
        raise HTTPException(422, f"period must be one of {', '.join(_PERIOD_DAYS)}")

    et = ZoneInfo("US/Eastern")
    hist = engine.alpaca_portfolio_history(period=period) or {}
    curve = [
        {"ts": t, "equity": round(e, 2), "pnl": round(p or 0, 2)}
        for t, e, p in zip(hist.get("timestamps", []), hist.get("equity", []), hist.get("profit_loss", []))
        if e and e > 0
    ]

    # Filled orders in the window, bucketed by day / week / month.
    bucket = "day" if period in ("1D", "1W") else "week" if period == "1M" else "month"
    after = (datetime.now(et) - timedelta(days=_PERIOD_DAYS[period])).isoformat()
    orders = []
    try:
        r = requests.get(
            f"{engine.ALPACA_BASE}/v2/orders",
            headers=engine._alpaca_headers(),
            params={"status": "closed", "limit": 500, "after": after},
            timeout=15,
        )
        if r.status_code == 200:
            orders = [o for o in r.json() if float(o.get("filled_qty") or 0) > 0]
    except Exception:
        pass

    def key_for(day: str) -> str:
        if bucket == "day":
            return day
        d = datetime.strptime(day, "%Y-%m-%d")
        if bucket == "week":
            return (d - timedelta(days=d.weekday())).strftime("%Y-%m-%d")  # Monday
        return day[:7] + "-01"

    pnl_by_day = defaultdict(float)
    # profit_loss from Alpaca is per-bar; with daily bars that's the day's P&L.
    if period not in ("1D", "1W"):
        for p in curve:
            pnl_by_day[datetime.fromtimestamp(p["ts"], tz=et).strftime("%Y-%m-%d")] += p["pnl"]

    groups: dict = defaultdict(lambda: {"buys": 0, "sells": 0, "tickers": set(), "days": set()})
    for o in orders:
        day = (o.get("filled_at") or o.get("created_at") or "")[:10]
        if not day:
            continue
        g = groups[key_for(day)]
        g["buys" if o.get("side") == "buy" else "sells"] += 1
        g["tickers"].add(o.get("symbol"))
        g["days"].add(day)

    recaps = []
    for k in sorted(groups, reverse=True):
        g = groups[k]
        recaps.append({
            "start": k,
            "buys": g["buys"],
            "sells": g["sells"],
            "tickers": sorted(t for t in g["tickers"] if t)[:12],
            "pnl": round(sum(pnl_by_day.get(d, 0) for d in g["days"]), 2) if pnl_by_day else None,
        })

    return {"ok": True, "period": period, "bucket": bucket, "curve": curve, "recaps": recaps}
