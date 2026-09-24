"""
The autonomous trading loop for v2 — ported from server.py's
_autopilot_loop/_spawn_autopilot/_autopilot_watchdog. The strategy itself is
still engine.run_autopilot(), untouched; this module only owns scheduling,
restart-on-crash, persistence across restarts, and reporting.

Differences from the original, all on purpose:
- State lives in autopilot_state_v2.json (next to the database, so it survives
  redeploys), not the original's file, so restarting one app never
  auto-resumes the other's loop.
- start() refuses while the ORIGINAL app's state file says its autopilot is
  on: two loops trading the same Alpaca account would double every order.
- Moving production over: set AUTOPILOT_ADOPT_ORIGINAL=1 and, if the original
  app's autopilot was on, v2 takes it over at startup (same owner) and marks
  the original's state off so the old app can never resume it as well.
- WebSocket events carry only the event kind; the details (tickers, logs)
  come from the signed-in /api/autopilot/status, not every open socket.
- The last few cycles are kept in memory so the UI can show recent activity
  instead of only whatever arrived over the websocket while it was open.
- Dropped: the pre-market scan (depends on the Streamlit session shim) and the
  hourly/milestone phone pings. Trade, error and start/stop pings are kept.
"""
import asyncio
import json
import os
import time
from collections import deque
from datetime import date, datetime
from typing import Optional
from zoneinfo import ZoneInfo

from ..bridge import auth, engine
from ..ws import manager
from .trade_log import log_trade

_DATA_DIR = os.environ.get("DB_DIR", os.path.dirname(os.path.abspath(auth.__file__)))
_STATE_FILE = os.path.join(_DATA_DIR, "autopilot_state_v2.json")
_ORIGINAL_STATE_FILE = os.path.join(_DATA_DIR, "autopilot_state.json")

CYCLE_SECONDS = 5 * 60
CLOSED_POLL_SECONDS = 60
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "paula-trades")

_task: Optional[asyncio.Task] = None
_owner_id: Optional[int] = None
_started_at: Optional[float] = None
_recent: deque = deque(maxlen=20)       # newest last; one entry per cycle/event
_alerted_today: dict[str, str] = {}


# ── State ────────────────────────────────────────────────────────────────

def _save_state(on: bool, owner_id: Optional[int]) -> None:
    try:
        with open(_STATE_FILE, "w") as f:
            json.dump({"on": on, "owner_id": owner_id}, f)
    except Exception as e:
        print(f"[autopilot] could not save state: {e}", flush=True)


def _load_state() -> dict:
    try:
        with open(_STATE_FILE) as f:
            return json.load(f)
    except Exception:
        return {"on": False, "owner_id": None}


def original_app_running_autopilot() -> bool:
    try:
        with open(_ORIGINAL_STATE_FILE) as f:
            return bool(json.load(f).get("on"))
    except Exception:
        return False


def is_running() -> bool:
    return _task is not None and not _task.done()


def status() -> dict:
    return {
        "running": is_running(),
        "owner_id": _owner_id if is_running() else None,
        "started_at": _started_at if is_running() else None,
        "recent": list(_recent)[::-1],   # newest first for the UI
    }


def _record(kind: str, **data) -> dict:
    entry = {"at": datetime.now(ZoneInfo("US/Eastern")).isoformat(), "kind": kind, **data}
    _recent.append(entry)
    return entry


async def _emit(kind: str, **data) -> None:
    entry = _record(kind, **data)
    try:
        await manager.broadcast("autopilot", {"kind": kind, "at": entry["at"], "running": is_running()})
    except Exception:
        pass


async def _notify(title: str, message: str, priority: str = "default") -> None:
    def _post():
        import requests
        requests.post(
            f"https://ntfy.sh/{NTFY_TOPIC}",
            data=message.encode(),
            headers={"Title": title, "Priority": priority},
            timeout=5,
        )
    try:
        await asyncio.get_running_loop().run_in_executor(None, _post)
    except Exception:
        pass  # a failed phone ping must never affect trading


# ── Loop ─────────────────────────────────────────────────────────────────

async def _loop() -> None:
    while True:
        try:
            is_open, status_msg = engine._market_is_open()
            if not is_open:
                # Only log the transition, not a "paused" row every minute.
                if not _recent or _recent[-1].get("kind") != "paused":
                    await _emit("paused", reason=status_msg)
                await asyncio.sleep(CLOSED_POLL_SECONDS)
                continue

            creds = None
            try:
                if _owner_id:
                    creds = auth.get_user_alpaca_creds(_owner_id)
            except Exception:
                creds = None

            def _run():
                # Executor threads don't inherit per-request creds, so apply
                # the OWNER's keys here — autopilot trades their account.
                if creds:
                    engine.set_alpaca_creds(creds.get("key_id"), creds.get("secret"))
                return engine.run_autopilot()

            result = await asyncio.get_running_loop().run_in_executor(None, _run) or {}
            buys, sells, shorts = (result.get(k, 0) or 0 for k in ("buys", "sells", "shorts"))
            await _emit(
                "cycle",
                ok=bool(result.get("ok", True)),
                mode=result.get("mode"),
                scanned=result.get("scanned", 0),
                opportunities=result.get("opportunities", 0),
                buys=buys,
                sells=sells,
                shorts=shorts,
                log=(result.get("log") or [])[-30:],
                error=result.get("error"),
            )

            # High-conviction alerts, once per ticker per day.
            today = date.today().isoformat()
            for k in [k for k, v in _alerted_today.items() if v != today]:
                _alerted_today.pop(k, None)
            for a in result.get("alerts") or []:
                t = a.get("ticker")
                if t and _alerted_today.get(t) != today:
                    _alerted_today[t] = today
                    await manager.broadcast("alert", {"ticker": t, "score": a.get("score"), "rr": a.get("rr")})

            if buys or sells or shorts:
                entries = result.get("entries") or []
                for e in entries:
                    log_trade("buy", e.get("ticker", "?"), qty=e.get("qty", 0), price=e.get("entry", 0),
                              extra={"source": "autopilot", "stop": e.get("stop")})
                if not entries:
                    log_trade("autopilot", "-", extra={"source": "autopilot", "buys": buys,
                                                       "sells": sells, "shorts": shorts})
                if entries:
                    detail = " · ".join(
                        f"{e['ticker']} {e.get('qty', '')}@${e.get('entry', 0):.2f} stop ${e.get('stop', 0):.2f}"
                        for e in entries[:4]
                    )
                    title = "Bought " + ", ".join(e["ticker"] for e in entries[:3])
                else:
                    detail = ", ".join(
                        s for s in (f"{buys} bought" if buys else "", f"{shorts} shorted" if shorts else "",
                                    f"{sells} closed" if sells else "") if s
                    )
                    title = "Paula trade"
                await _notify(title, detail)

        except asyncio.CancelledError:
            raise
        except Exception as e:
            err = str(e)[:200]
            print(f"[autopilot] cycle error: {err}", flush=True)
            await _emit("error", error=err)
            await _notify("Paula autopilot error", err[:80], priority="high")

        await asyncio.sleep(CYCLE_SECONDS)


def _watchdog(task: asyncio.Task) -> None:
    """Restart the loop if it ever exits without a deliberate stop."""
    if task is not _task or task.cancelled():
        return
    try:
        exc = task.exception()
    except asyncio.CancelledError:
        return
    reason = repr(exc) if exc else "loop returned unexpectedly"
    print(f"[autopilot] loop died ({reason}) — restarting in 10s", flush=True)

    async def _restart():
        global _task
        await asyncio.sleep(10)
        if _owner_id is not None and _task is task:
            _task = _spawn()
            await _emit("restarted", reason=reason[:160])

    asyncio.get_running_loop().create_task(_restart())


def _spawn() -> asyncio.Task:
    t = asyncio.get_running_loop().create_task(_loop())
    t.add_done_callback(_watchdog)
    return t


# ── Public API ───────────────────────────────────────────────────────────

class AutopilotConflict(Exception):
    pass


async def start(owner: dict) -> bool:
    """Returns False if it was already running."""
    global _task, _owner_id, _started_at
    if is_running():
        return False
    if original_app_running_autopilot():
        raise AutopilotConflict(
            "The original Paula app has autopilot on. Stop it there first — "
            "two loops on one account would double every order."
        )
    _owner_id = owner["id"]
    _started_at = time.time()
    _task = _spawn()
    _save_state(True, _owner_id)
    await _emit("started", by=owner.get("email"))
    await _notify("Autopilot started", "Paula is scanning for trades every 5 minutes")
    return True


async def stop() -> None:
    global _task, _owner_id, _started_at
    task, _task = _task, None
    _owner_id = None
    _started_at = None
    if task and not task.done():
        task.cancel()
    _save_state(False, None)
    await _emit("stopped")
    await _notify("Autopilot stopped", "Paula is no longer trading")


def _adopt_original() -> Optional[dict]:
    """Production switch-over: take over the original app's running autopilot."""
    if os.environ.get("AUTOPILOT_ADOPT_ORIGINAL") != "1":
        return None
    try:
        with open(_ORIGINAL_STATE_FILE) as f:
            orig = json.load(f)
    except Exception:
        return None
    if not orig.get("on") or not orig.get("owner_id"):
        return None
    try:
        with open(_ORIGINAL_STATE_FILE, "w") as f:
            json.dump({"on": False, "owner_id": None, "adopted_by": "v2"}, f)
    except Exception as e:
        print(f"[autopilot] could not take over from the original app: {e}", flush=True)
        return None
    _save_state(True, orig["owner_id"])
    print(f"[autopilot] took over the original app's autopilot (owner {orig['owner_id']})", flush=True)
    return {"on": True, "owner_id": orig["owner_id"]}


async def resume_if_needed() -> None:
    """Called at startup: bring the loop back if it was on before a restart."""
    global _task, _owner_id, _started_at
    st = _load_state()
    if not st.get("on"):
        st = _adopt_original() or st
    if not st.get("on") or is_running():
        return
    if original_app_running_autopilot():
        print("[autopilot] not resuming: the original app's autopilot is on", flush=True)
        _save_state(False, None)
        return
    _owner_id = st.get("owner_id")
    _started_at = time.time()
    _task = _spawn()
    await _emit("resumed")
    print(f"[autopilot] resumed after restart (owner {_owner_id})", flush=True)


async def shutdown() -> None:
    """Process exit: cancel the task but keep the saved state, so it resumes."""
    if _task and not _task.done():
        _task.cancel()
