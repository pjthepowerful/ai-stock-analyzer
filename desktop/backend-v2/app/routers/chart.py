"""
Chart data — ported faithfully from server.py's /api/chart handler. This is
retry/fallback logic tuned for real-world reliability (Yahoo aggressively
rate-limits datacenter IPs, Polygon is the fallback), not boilerplate, so it's
preserved as-is rather than simplified.
"""
import os
import time
import warnings
from datetime import datetime, timedelta

from fastapi import APIRouter

router = APIRouter(prefix="/api/chart", tags=["chart"])

_CHART_CACHE: dict[tuple, tuple[float, dict]] = {}
_CHART_CACHE_TTL = 180


def _polygon_chart_bars(ticker: str, period: str, intraday: bool, interval: str | None = None):
    import requests

    key = os.environ.get("POLYGON_API_KEY", "")
    if not key:
        return None
    span = {
        "1d": (5, "minute", 1),
        "5d": (30, "minute", 5),
        "1mo": (1, "day", 31),
        "3mo": (1, "day", 93),
        "6mo": (1, "day", 186),
        "1y": (1, "day", 372),
        "5y": (1, "week", 1830),
    }.get(period, (1, "day", 372))
    mult, timespan, lookback = span
    end = datetime.utcnow().date()
    start = end - timedelta(days=lookback)
    try:
        url = f"https://api.polygon.io/v2/aggs/ticker/{ticker}/range/{mult}/{timespan}/{start.isoformat()}/{end.isoformat()}"
        r = requests.get(url, params={"apiKey": key, "adjusted": "true", "sort": "asc", "limit": 50000}, timeout=12)
        if r.status_code != 200:
            return None
        results = (r.json() or {}).get("results") or []
        if not results:
            return None
        dates, o, h, l, c, v = [], [], [], [], [], []
        for bar in results:
            ts = bar.get("t")
            if ts is None:
                continue
            d = datetime.utcfromtimestamp(ts / 1000)
            dates.append(d.strftime("%Y-%m-%d %H:%M" if intraday else "%Y-%m-%d"))
            o.append(round(float(bar.get("o", 0)), 2))
            h.append(round(float(bar.get("h", 0)), 2))
            l.append(round(float(bar.get("l", 0)), 2))
            c.append(round(float(bar.get("c", 0)), 2))
            v.append(int(bar.get("v", 0)))
        if not dates:
            return None
        return {"ok": True, "data": {"dates": dates, "open": o, "high": h, "low": l, "close": c, "volume": v}}
    except Exception:
        return None


@router.get("/{ticker}")
def chart_data(ticker: str, period: str = "1y"):
    import yfinance as yf

    ticker = ticker.upper()
    INTRADAY = {"1d": "5m", "5d": "30m"}
    interval = INTRADAY.get(period)
    intraday = interval is not None

    ttl = 60 if intraday else _CHART_CACHE_TTL
    ck = (ticker, period)
    cached = _CHART_CACHE.get(ck)
    if cached and (time.time() - cached[0]) < ttl:
        return cached[1]

    last_err = "No data"
    for attempt in range(3):
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                tk = yf.Ticker(ticker)
                hist = tk.history(period=period, interval=interval) if intraday else tk.history(period=period)
            if hist is None or hist.empty:
                last_err = "No data"
                if attempt < 2:
                    time.sleep(1.2 * (attempt + 1))
                    continue
                poly = _polygon_chart_bars(ticker, period, intraday, interval)
                if poly:
                    _CHART_CACHE[ck] = (time.time(), poly)
                    return poly
                if cached:
                    return cached[1]
                return {"ok": False, "error": "No data"}

            import math

            raw_keys = [str(d)[:16] if intraday else str(d)[:10] for d in hist.index]
            seen, indices, clean_dates = set(), [], []
            for i, d in enumerate(raw_keys):
                if d in seen:
                    continue
                # yfinance occasionally returns a NaN bar (data gaps, half
                # days) — drop just that bar rather than failing the whole
                # chart, which is what the pre-existing endpoint this was
                # ported from does (a single bad bar 500s/errors the request).
                row = (hist["Open"].iloc[i], hist["High"].iloc[i], hist["Low"].iloc[i], hist["Close"].iloc[i], hist["Volume"].iloc[i])
                if any(math.isnan(v) for v in row):
                    continue
                seen.add(d)
                indices.append(i)
                clean_dates.append(d)
            payload = {
                "ok": True,
                "data": {
                    "dates": clean_dates,
                    "open": [round(float(hist["Open"].iloc[i]), 2) for i in indices],
                    "high": [round(float(hist["High"].iloc[i]), 2) for i in indices],
                    "low": [round(float(hist["Low"].iloc[i]), 2) for i in indices],
                    "close": [round(float(hist["Close"].iloc[i]), 2) for i in indices],
                    "volume": [int(hist["Volume"].iloc[i]) for i in indices],
                },
            }
            _CHART_CACHE[ck] = (time.time(), payload)
            if len(_CHART_CACHE) > 400:
                for k in sorted(_CHART_CACHE, key=lambda k: _CHART_CACHE[k][0])[:150]:
                    _CHART_CACHE.pop(k, None)
            return payload
        except Exception as e:
            last_err = str(e)[:100]
            msg = last_err.lower()
            if ("rate" in msg or "too many" in msg) and attempt < 2:
                time.sleep(2.0 * (attempt + 1))
                continue
            break

    poly = _polygon_chart_bars(ticker, period, intraday, interval)
    if poly:
        _CHART_CACHE[ck] = (time.time(), poly)
        return poly
    if cached:
        return cached[1]
    return {"ok": False, "error": last_err}
