"""
Historical intraday data for Paula's day-trading backtests.

Pulls consolidated (SIP) bars from Alpaca's market-data API and caches them on
disk so a backtest re-run costs nothing. Three kinds of pull, sized for the
"stocks in play" research design, where downloading every minute of every
stock would be ~100M bars:

    daily_bars()     every symbol, one row per day      → universe + ATR filters
    opening_bars()   every symbol, first N minutes only  → relative volume ranking
    minute_bars()    a handful of symbols, full session  → the actual trade replay

Survivorship caveat: the symbol list comes from Alpaca's *currently active*
assets, so names that were delisted inside the test window are missing. That
flatters long-side results a little; reports say so.
"""
from __future__ import annotations

import gzip
import json
import os
import pathlib
import time
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import requests

ET = ZoneInfo("America/New_York")
DATA_BASE = "https://data.alpaca.markets"
TRADE_BASE = os.environ.get("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")

_HERE = pathlib.Path(__file__).parent
CACHE = pathlib.Path(os.environ.get(
    "INTRADAY_CACHE", str(pathlib.Path(os.environ.get("DB_DIR", str(_HERE / "desktop" / "backend"))) / "intraday_cache")))

# URL length keeps a multi-symbol request to roughly this many tickers.
_SYMBOL_CHUNK = 400


def _headers() -> dict:
    return {
        "APCA-API-KEY-ID": os.environ.get("ALPACA_KEY_ID", ""),
        "APCA-API-SECRET-KEY": os.environ.get("ALPACA_SECRET", ""),
    }


def available() -> bool:
    return bool(os.environ.get("ALPACA_KEY_ID") and os.environ.get("ALPACA_SECRET"))


def _get(url: str, params: dict) -> dict:
    """GET with backoff on rate limits. The free data plan allows ~200 req/min."""
    for attempt in range(20):
        try:
            r = requests.get(url, headers=_headers(), params=params, timeout=30)
        except (requests.ConnectionError, requests.Timeout):
            # Dropped connections and TLS resets happen over an hour-long pull.
            time.sleep(min(2 ** attempt, 30))
            continue
        if r.status_code == 429:
            # Per-minute budget: waiting out the window always works eventually.
            time.sleep(min(2 ** attempt, 20))
            continue
        if r.status_code >= 500:
            time.sleep(2)
            continue
        r.raise_for_status()
        return r.json()
    raise RuntimeError(f"Alpaca kept rate-limiting {url}")


def _multi_bars(symbols: list[str], timeframe: str, start: str, end: str) -> dict[str, list]:
    """All pages of /v2/stocks/bars for up to _SYMBOL_CHUNK symbols."""
    out: dict[str, list] = {}
    token = None
    # The free plan serves SIP only up to 15 minutes ago; asking for later is a 403.
    latest = datetime.now(timezone.utc) - timedelta(minutes=16)
    if "T" not in end:
        end = f"{end}T23:59:59Z"
    if datetime.fromisoformat(end.replace("Z", "+00:00")) > latest:
        end = latest.strftime("%Y-%m-%dT%H:%M:%SZ")
    while True:
        params = {"symbols": ",".join(symbols), "timeframe": timeframe, "start": start,
                  "end": end, "limit": 10000, "feed": "sip", "adjustment": "split",
                  "sort": "asc"}
        if token:
            params["page_token"] = token
        body = _get(f"{DATA_BASE}/v2/stocks/bars", params)
        for sym, rows in (body.get("bars") or {}).items():
            out.setdefault(sym, []).extend(rows)
        token = body.get("next_page_token")
        if not token:
            return out


def _read(path: pathlib.Path):
    try:
        with gzip.open(path, "rt") as f:
            return json.load(f)
    except Exception:
        return None


def _write(path: pathlib.Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with gzip.open(tmp, "wt") as f:
        json.dump(obj, f, separators=(",", ":"))
    tmp.replace(path)


def _ts_et(t: str) -> datetime:
    return datetime.fromisoformat(t.replace("Z", "+00:00")).astimezone(ET)


def _compact(row: dict) -> list:
    """[epoch_s, o, h, l, c, v, vwap] — a fraction of the JSON size."""
    ts = int(datetime.fromisoformat(row["t"].replace("Z", "+00:00")).timestamp())
    return [ts, row["o"], row["h"], row["l"], row["c"], row["v"], row.get("vw", row["c"])]


# ── Universe ────────────────────────────────────────────────────────────────

def tradable_symbols(refresh: bool = False) -> list[str]:
    """Active, tradable US common-stock-looking symbols on the major venues."""
    path = CACHE / "assets.json.gz"
    if not refresh:
        cached = _read(path)
        if cached and time.time() - cached["at"] < 7 * 86400:
            return cached["symbols"]
    r = requests.get(f"{TRADE_BASE}/v2/assets", headers=_headers(),
                     params={"status": "active", "asset_class": "us_equity"}, timeout=60)
    r.raise_for_status()
    syms = sorted(
        a["symbol"] for a in r.json()
        if a.get("tradable") and a.get("exchange") in ("NYSE", "NASDAQ", "AMEX", "ARCA", "BATS")
        # Warrants, units, rights and preferreds carry suffixes; skip them.
        and a["symbol"].isalpha() and len(a["symbol"]) <= 5
    )
    _write(path, {"at": time.time(), "symbols": syms})
    return syms


def trading_days(start: date, end: date) -> list[date]:
    """Sessions per SPY's own daily bars (so holidays are exact)."""
    rows = daily_bars(start, end, symbols=["SPY"]).get("SPY", [])
    return [datetime.fromtimestamp(r[0], ET).date() for r in rows]


def daily_bars(start: date, end: date, symbols: list[str] | None = None,
               progress=None) -> dict[str, list]:
    """Daily bars keyed by symbol, cached per calendar year."""
    if symbols and len(symbols) <= 5:
        return {s: _daily_one(s, start, end) for s in symbols}
    symbols = symbols or tradable_symbols()
    out: dict[str, list] = {}
    for year in range(start.year, end.year + 1):
        path = CACHE / "daily" / f"{year}.json.gz"
        cached = _read(path) or {}
        have = cached.get("bars", {})
        # Symbols with no bars that year are stored as [], so "missing" only
        # means never asked — a cache built for SPY alone doesn't hide the rest.
        missing = [s for s in symbols if s not in have]
        year_end = min(date(year, 12, 31), date.today())
        if missing:
            for i in range(0, len(missing), _SYMBOL_CHUNK):
                chunk = missing[i:i + _SYMBOL_CHUNK]
                got = _multi_bars(chunk, "1Day", f"{year}-01-01", year_end.isoformat())
                for s in chunk:
                    have[s] = [_compact(r) for r in got.get(s, [])]
                if progress:
                    progress(f"daily {year}: {min(i + _SYMBOL_CHUNK, len(missing))}/{len(missing)}")
            _write(path, {"bars": have, "_complete": year_end < date.today() - timedelta(days=3),
                          "_through": year_end.isoformat()})
        elif year == date.today().year and cached.get("_through", "") < (date.today() - timedelta(days=1)).isoformat():
            # Current year: top up the tail for everyone.
            frm = cached.get("_through", f"{year}-01-01")
            for i in range(0, len(symbols), _SYMBOL_CHUNK):
                chunk = symbols[i:i + _SYMBOL_CHUNK]
                got = _multi_bars(chunk, "1Day", frm, date.today().isoformat())
                for s, rows in got.items():
                    old = have.setdefault(s, [])
                    last = old[-1][0] if old else 0
                    old.extend(r for r in map(_compact, rows) if r[0] > last)
            _write(path, {"bars": have, "_complete": False, "_through": date.today().isoformat()})
        lo = datetime.combine(start, datetime.min.time(), ET).timestamp()
        hi = datetime.combine(end, datetime.max.time(), ET).timestamp()
        for s in symbols:
            rows = [r for r in have.get(s, []) if lo <= r[0] <= hi]
            if rows:
                out.setdefault(s, []).extend(rows)
    return out


def _daily_one(symbol: str, start: date, end: date) -> list:
    """One symbol's daily bars from its own small cache (benchmarks, the
    trading calendar) — without loading the full-market yearly files."""
    path = CACHE / "daily_sym" / f"{symbol}.json.gz"
    cached = _read(path) or {"rows": [], "through": "2000-01-01", "from": "2100-01-01"}
    want_from = min(start, date(2016, 1, 1)).isoformat()
    fresh = cached["through"] >= (date.today() - timedelta(days=1)).isoformat()
    if cached["from"] > want_from or not fresh:
        got = _multi_bars([symbol], "1Day", want_from, date.today().isoformat())
        cached = {"rows": [_compact(r) for r in got.get(symbol, [])], "from": want_from,
                  "through": date.today().isoformat()}
        _write(path, cached)
    lo = datetime.combine(start, datetime.min.time(), ET).timestamp()
    hi = datetime.combine(end, datetime.max.time(), ET).timestamp()
    return [r for r in cached["rows"] if lo <= r[0] <= hi]


# ── Intraday ────────────────────────────────────────────────────────────────

def _session_utc(day: date, hhmm: str) -> str:
    h, m = map(int, hhmm.split(":"))
    return datetime(day.year, day.month, day.day, h, m, tzinfo=ET).astimezone(timezone.utc) \
        .strftime("%Y-%m-%dT%H:%M:%SZ")


def opening_bars(day: date, symbols: list[str], minutes: int = 5) -> dict[str, list]:
    """The first `minutes` of the regular session as ONE aggregated bar per symbol:
    [ts, open, high, low, close, volume, vwap]. Cached per day and window."""
    path = CACHE / f"open{minutes}" / f"{day.isoformat()}.json.gz"
    cached = _read(path) or {}
    missing = [s for s in symbols if s not in cached]
    if missing:
        start = _session_utc(day, "09:30")
        end_t = (datetime(day.year, day.month, day.day, 9, 30, tzinfo=ET) + timedelta(minutes=minutes - 1))
        end = end_t.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        for i in range(0, len(missing), _SYMBOL_CHUNK):
            chunk = missing[i:i + _SYMBOL_CHUNK]
            got = _multi_bars(chunk, "1Min", start, end)
            for s in chunk:
                rows = got.get(s) or []
                if not rows:
                    cached[s] = None
                    continue
                v = sum(r["v"] for r in rows)
                vw = sum(r.get("vw", r["c"]) * r["v"] for r in rows) / v if v else rows[-1]["c"]
                cached[s] = [_compact(rows[0])[0], rows[0]["o"], max(r["h"] for r in rows),
                             min(r["l"] for r in rows), rows[-1]["c"], v, vw]
        _write(path, cached)
    return {s: cached[s] for s in symbols if cached.get(s)}


def minute_bars(day: date, symbols: list[str]) -> dict[str, list]:
    """Full regular-session 1-minute bars for a few symbols on one day."""
    out = {}
    need = []
    for s in symbols:
        rows = _read(CACHE / "min" / day.isoformat() / f"{s}.json.gz")
        if rows is None:
            need.append(s)
        else:
            out[s] = rows
    for i in range(0, len(need), 20):   # 20 × 390 bars stays under one page
        chunk = need[i:i + 20]
        got = _multi_bars(chunk, "1Min", _session_utc(day, "09:30"), _session_utc(day, "15:59"))
        for s in chunk:
            rows = [_compact(r) for r in got.get(s, [])]
            _write(CACHE / "min" / day.isoformat() / f"{s}.json.gz", rows)
            out[s] = rows
    return out


def minute_range(symbol: str, start: date, end: date) -> dict[date, list]:
    """1-minute regular-session bars for ONE symbol over many days (e.g. SPY),
    cached per month. Returns {day: rows}."""
    out: dict[date, list] = {}
    d = date(start.year, start.month, 1)
    while d <= end:
        nxt = date(d.year + (d.month == 12), d.month % 12 + 1, 1)
        path = CACHE / "series" / symbol / f"{d:%Y-%m}.json.gz"
        cached = _read(path)
        month_done = nxt <= date.today() - timedelta(days=1)
        if cached is None or not cached.get("_complete"):
            got = _multi_bars([symbol], "1Min", f"{d.isoformat()}T13:00:00Z",
                              f"{min(nxt - timedelta(days=1), date.today()).isoformat()}T21:00:00Z")
            rows = [_compact(r) for r in got.get(symbol, [])]
            cached = {"rows": rows, "_complete": month_done}
            _write(path, cached)
        for r in cached["rows"]:
            t = datetime.fromtimestamp(r[0], ET)
            if not (start <= t.date() <= end):
                continue
            if (t.hour, t.minute) < (9, 30) or t.hour >= 16:
                continue
            out.setdefault(t.date(), []).append(r)
        d = nxt
    return out
