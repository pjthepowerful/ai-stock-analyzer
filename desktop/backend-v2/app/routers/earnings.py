"""
Earnings calendar — ported from server.py. Calendar build/verdicts are the
tuned part (which feed to trust, how a "candidate/watch/blocked/fade/skip"
verdict is derived); preserved as-is, only the HTTP layer is new.
"""
import asyncio
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Header, HTTPException

from ..bridge import engine, read_strategy_mode
from ..deps import current_user_required
from ..services.parallel import pmap
from ..ws import manager

router = APIRouter(prefix="/api/earnings", tags=["earnings"])

_cal_build_task: asyncio.Task | None = None

# Per-day verdicts need live quotes but don't move minute to minute.
_DAY_TTL = 5 * 60
_day_cache: dict[tuple, tuple[float, dict]] = {}


@router.get("/calendar/month")
def calendar_month(year: int = 0, month: int = 0, authorization: str = Header(None)):
    current_user_required(authorization)
    now = datetime.now(ZoneInfo("US/Eastern"))
    y = year or now.year
    m = month or now.month
    try:
        import earnings as earn

        data = earn.calendar_month(y, m)
        return {"ok": True, "year": y, "month": m, **data}
    except Exception as e:
        raise HTTPException(502, str(e)[:200])


@router.get("/calendar/day")
def calendar_day(date: str, authorization: str = Header(None)):
    """Stocks reporting on one date, each with a verdict — computed live
    since it needs current price/cap, not the cached build."""
    current_user_required(authorization)
    try:
        import earnings as earn
        import smallcap_pullback as scp

        mode_key = read_strategy_mode()
        mode = scp.get_mode(mode_key) if mode_key in ("strict", "intense") else None

        key = (date, mode_key)
        hit = _day_cache.get(key)
        if hit and time.time() - hit[0] < _DAY_TTL:
            return hit[1]

        cache = earn._load_cache()
        rows = (cache.get("dates") or {}).get(date, [])

        # One verdict per name, each a few network calls — run them
        # concurrently instead of one after another.
        verdicts = pmap(lambda r: {**r, **earn.verdict(r["ticker"], mode)}, rows[:40])
        out = list(verdicts)
        order = {"candidate": 0, "watch": 1, "blocked": 2, "fade": 3, "skip": 4, "stale": 5}
        out.sort(key=lambda x: (order.get(x.get("verdict"), 9), x["ticker"]))

        result = {"ok": True, "date": date, "mode": mode_key, "stocks": out}
        _day_cache[key] = (time.time(), result)
        return result
    except Exception as e:
        raise HTTPException(502, str(e)[:200])


def _progress_emitter(channel: str, loop: asyncio.AbstractEventLoop):
    """Bridge a sync progress callback in a worker thread to the WebSocket,
    throttled so a frame-per-ticker doesn't flood the socket."""
    import time

    last = {"at": 0.0}

    def _cb(done, total, label=""):
        now = time.time()
        if done < total and now - last["at"] < 0.4:
            return
        last["at"] = now
        try:
            asyncio.run_coroutine_threadsafe(
                manager.broadcast("work_progress", {"channel": channel, "done": done, "total": total, "label": label}),
                loop,
            )
        except Exception:
            pass

    return _cb


@router.post("/calendar/refresh")
async def refresh_calendar(authorization: str = Header(None)):
    global _cal_build_task
    current_user_required(authorization)
    if _cal_build_task and not _cal_build_task.done():
        return {"ok": True, "status": "already building"}

    loop = asyncio.get_event_loop()

    async def _build():
        try:
            import earnings as earn

            held = []
            try:
                held = [p["ticker"] for p in (engine.alpaca_positions() or []) if p.get("ticker")]
            except Exception:
                pass
            tickers = list(held)
            try:
                from universe import liquid_universe

                tickers += liquid_universe()
            except Exception:
                pass
            emit = _progress_emitter("calendar", loop)
            data = await loop.run_in_executor(None, lambda: earn.build_calendar(tickers, keep=set(held), progress=emit))
            _day_cache.clear()
            await manager.broadcast("earnings", {"status": "calendar_built", "dates": len(data["dates"])})
        except Exception as e:
            print(f"[earnings] calendar build failed: {e!r}", flush=True)

    _cal_build_task = asyncio.ensure_future(_build())
    return {"ok": True, "status": "building"}
