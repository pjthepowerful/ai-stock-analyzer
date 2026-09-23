"""
Per-ticker research for the Analyze screen: the earnings forecast, earnings
snapshot, and the research row (news, post-earnings drift, SEC fundamentals).
Thin wrappers over the repo-root forecast.py / earnings.py / research.py,
which are unchanged. Sign-in required, as in the original — these fan out to
several paid/rate-limited data sources per call.
"""
import asyncio
from datetime import datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Header, HTTPException

from ..bridge import engine
from ..deps import current_user_required, in_request_context
from .earnings import _progress_emitter

router = APIRouter(prefix="/api", tags=["research"])


def _clean(ticker: str) -> str:
    t = ticker.strip().upper()
    if not t or len(t) > 10 or not t.replace(".", "").replace("-", "").isalnum():
        raise HTTPException(422, "Not a valid ticker")
    return t


_SEC_BLOCKED = "SEC lookup blocked — set SEC_USER_AGENT in the backend .env to include a contact email"


def _fix_sec_note(row: dict) -> dict:
    """research.cik_for() says "not an SEC filer" whenever its ticker map is
    empty — including when the SEC refused the download (403 without a
    contact in SEC_USER_AGENT). Say which one it actually is."""
    import research as res

    fund = row.get("fundamentals") or {}
    if not fund.get("available") and not getattr(res, "_CIK_CACHE", None):
        fund["reason"] = _SEC_BLOCKED
        row["fundamental_notes"] = [_SEC_BLOCKED]
    return row


# Ranking 40–60 names takes about a minute, so results are kept for 15
# minutes and concurrent requests for the same ranking share one run.
_RANK_TTL = 15 * 60
_rank_cache: dict[tuple, tuple[float, dict]] = {}
_rank_locks: dict[tuple, asyncio.Lock] = {}


async def _cached(key: tuple, build):
    import time

    hit = _rank_cache.get(key)
    if hit and time.time() - hit[0] < _RANK_TTL:
        return {**hit[1], "cached_at": hit[0]}
    lock = _rank_locks.setdefault(key, asyncio.Lock())
    async with lock:
        hit = _rank_cache.get(key)
        if hit and time.time() - hit[0] < _RANK_TTL:
            return {**hit[1], "cached_at": hit[0]}
        data = await build()
        now = time.time()
        _rank_cache[key] = (now, data)
        return {**data, "cached_at": now}


def _calendar_names(start, end) -> list[str]:
    """Tickers the earnings-calendar cache has reporting in [start, end]."""
    import earnings as earn

    names: list[str] = []
    for dstr, rows in (earn._load_cache().get("dates") or {}).items():
        try:
            d = datetime.strptime(dstr, "%Y-%m-%d").date()
        except ValueError:
            continue
        if start <= d <= end:
            names += [r["ticker"] for r in rows if r.get("ticker")]
    return list(dict.fromkeys(names))


# Fixed paths first: /forecast/{ticker} and /research/{ticker} would
# otherwise capture "upcoming" and "candidates" as tickers.

@router.get("/forecast/upcoming")
async def forecast_upcoming(days: int = 21, limit: int = 12, fresh: bool = False,
                            authorization: Optional[str] = Header(None)):
    """Companies reporting soon, ranked by how likely they look to beat.
    Forward-looking and advisory only — nothing here places an order."""
    current_user_required(authorization)
    days, limit = max(1, min(days, 90)), max(1, min(limit, 30))
    if fresh:
        _rank_cache.pop(("upcoming", days, limit), None)
    return await _cached(("upcoming", days, limit), lambda: _build_upcoming(days, limit))


async def _build_upcoming(days: int, limit: int) -> dict:
    import forecast as fc

    today = datetime.now(ZoneInfo("US/Eastern")).date()
    names = _calendar_names(today, today + timedelta(days=days))
    if not names:
        return {"ok": True, "rows": [], "scanned": 0,
                "note": f"Nothing in the calendar reports in the next {days} days — rebuild the calendar."}
    loop = asyncio.get_running_loop()
    emit = _progress_emitter("forecast", loop)
    rows = await loop.run_in_executor(None, in_request_context(fc.rank, names[:40], limit=limit, progress=emit))
    return {"ok": True, "rows": rows, "scanned": min(len(names), 40)}


@router.get("/research/candidates")
async def research_candidates(limit: int = 12, fresh: bool = False, authorization: Optional[str] = Header(None)):
    """Names inside a post-earnings drift window (already reported), ranked.
    Nothing forward-looking is a candidate: there's no drift before a print."""
    current_user_required(authorization)
    limit = max(1, min(limit, 30))
    if fresh:
        _rank_cache.pop(("candidates", limit), None)
    return await _cached(("candidates", limit), lambda: _build_candidates(limit))


async def _build_candidates(limit: int) -> dict:
    import research as res

    today = datetime.now(ZoneInfo("US/Eastern")).date()
    names = _calendar_names(today - timedelta(days=res.DRIFT_MAX_DAYS), today)
    held = {p["ticker"]: p for p in (engine.alpaca_positions() or []) if p.get("ticker")}
    names = list(dict.fromkeys(names + list(held)))
    if not names:
        return {"ok": True, "candidates": [], "scanned": 0,
                "note": "No company in the calendar has reported inside the drift window — rebuild the calendar."}
    acct = engine.alpaca_account() or {}
    prices = {t: p.get("current_price") for t, p in held.items()}
    loop = asyncio.get_running_loop()
    emit = _progress_emitter("research", loop)
    rows = await loop.run_in_executor(
        None,
        in_request_context(res.rank, names[:60], equity=acct.get("equity"), prices=prices, limit=limit, progress=emit),
    )
    return {"ok": True, "candidates": [_fix_sec_note(r) for r in rows], "scanned": min(len(names), 60), "equity": acct.get("equity")}


@router.get("/research/exposure")
def research_exposure(authorization: Optional[str] = Header(None)):
    """How close the held book is to the pattern-day-trader line. Visible,
    not enforced — by the owner's choice."""
    current_user_required(authorization)
    import research as res

    acct = engine.alpaca_account() or {}
    return {"ok": True, **res.pdt_exposure(acct.get("equity"), engine.alpaca_positions() or [])}


@router.get("/forecast/{ticker}")
def forecast(ticker: str, authorization: Optional[str] = Header(None)):
    current_user_required(authorization)
    import forecast as fc
    return {"ok": True, **fc.forecast(_clean(ticker))}


@router.get("/earnings/{ticker}")
def earnings(ticker: str, authorization: Optional[str] = Header(None)):
    current_user_required(authorization)
    import earnings as earn
    return {"ok": True, **earn.snapshot(_clean(ticker))}


@router.get("/research/{ticker}")
def research(ticker: str, authorization: Optional[str] = Header(None)):
    current_user_required(authorization)
    import research as res

    t = _clean(ticker)
    acct = engine.alpaca_account() or {}
    held = {p["ticker"]: p for p in (engine.alpaca_positions() or []) if p.get("ticker")}
    row = res.evaluate(t, price=(held.get(t) or {}).get("current_price"), equity=acct.get("equity"))

    return {"ok": True, **_fix_sec_note(row)}
