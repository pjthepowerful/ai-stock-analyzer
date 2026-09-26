"""
Backtest Lab: replay a day-trading strategy on historical 1-minute bars
(intraday_backtest.py) with your own settings, and keep the results.

Runs are background jobs — one at a time, because they share the Alpaca data
rate limit — and each finished run is saved under DB_DIR/lab_runs so the list
survives restarts. Limited to the accounts allowed to run autopilot: runs use
the owner's market-data keys, and nothing here places an order.
"""
import asyncio
import json
import os
import time
import uuid
from datetime import date
from typing import Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from ..bridge import auth
from ..deps import can_autopilot, current_user_required

router = APIRouter(prefix="/api/lab", tags=["lab"])

_DATA_DIR = os.environ.get("DB_DIR", os.path.dirname(os.path.abspath(auth.__file__)))
_RUNS_DIR = os.path.join(_DATA_DIR, "lab_runs")
_KEEP = 30
_MAX_CURVE_POINTS = 600
_MAX_TRADES = 400

_job: dict = {"id": None, "status": "idle", "progress": None, "error": None, "request": None, "started_at": None}


def _require(authorization: Optional[str]) -> dict:
    user = current_user_required(authorization)
    if not can_autopilot(user):
        raise HTTPException(403, "The backtest lab is limited to autopilot accounts")
    return user


def _bt():
    import intraday_backtest

    return intraday_backtest


@router.get("/strategies")
def strategies(authorization: Optional[str] = Header(None)):
    _require(authorization)
    bt = _bt()
    return {
        "ok": True,
        "strategies": [
            {"key": k, **v, "defaults": {p["key"]: bt.DEFAULTS[k].get(p["key"]) for p in v["params"]},
             "published_through": bt.PUBLISHED_THROUGH.get(k)}
            for k, v in bt.CATALOG.items()
        ],
    }


def _thin(curve: list) -> list:
    if len(curve) <= _MAX_CURVE_POINTS:
        return curve
    step = len(curve) / _MAX_CURVE_POINTS
    out = [curve[int(i * step)] for i in range(_MAX_CURVE_POINTS)]
    out[-1] = curve[-1]
    return out


def _summary_row(run: dict) -> dict:
    r = run.get("result") or {}
    return {
        "id": run["id"], "created_at": run["created_at"], "strategy": run["strategy"],
        "label": run.get("label"), "start": run["start"], "end": run["end"],
        "params": run.get("params"),
        "total_return_pct": r.get("total_return_pct"), "sharpe": r.get("sharpe"),
        "max_drawdown_pct": r.get("max_drawdown_pct"), "trades": r.get("trades"),
    }


def _saved() -> list[dict]:
    if not os.path.isdir(_RUNS_DIR):
        return []
    runs = []
    for name in os.listdir(_RUNS_DIR):
        if not name.endswith(".json"):
            continue
        try:
            with open(os.path.join(_RUNS_DIR, name)) as f:
                runs.append(json.load(f))
        except Exception:
            continue
    runs.sort(key=lambda r: r.get("created_at", 0), reverse=True)
    return runs


@router.get("/runs")
def runs(authorization: Optional[str] = Header(None)):
    _require(authorization)
    return {"ok": True, "job": {k: v for k, v in _job.items()}, "runs": [_summary_row(r) for r in _saved()]}


@router.get("/runs/{run_id}")
def run_detail(run_id: str, authorization: Optional[str] = Header(None)):
    _require(authorization)
    if not run_id.replace("-", "").isalnum():
        raise HTTPException(404, "No such run")
    path = os.path.join(_RUNS_DIR, f"{run_id}.json")
    if not os.path.exists(path):
        raise HTTPException(404, "No such run")
    with open(path) as f:
        return {"ok": True, "run": json.load(f)}


@router.delete("/runs/{run_id}")
def delete_run(run_id: str, authorization: Optional[str] = Header(None)):
    _require(authorization)
    path = os.path.join(_RUNS_DIR, f"{run_id}.json")
    if run_id.replace("-", "").isalnum() and os.path.exists(path):
        os.remove(path)
    return {"ok": True}


class RunRequest(BaseModel):
    strategy: str
    start: str
    end: str
    params: dict = {}
    equity: float = 25_000
    label: Optional[str] = None


def _clean_params(strategy: str, params: dict) -> dict:
    """Only the knobs the catalog exposes, clamped to their ranges."""
    spec = {p["key"]: p for p in _bt().CATALOG[strategy]["params"]}
    out = {}
    for k, v in (params or {}).items():
        p = spec.get(k)
        if p is None or v is None:
            continue
        if p["type"] == "choice":
            if v not in p["options"]:
                raise HTTPException(422, f"{p['label']}: pick one of {p['options']}")
            out[k] = v
        elif p["type"] == "bool":
            out[k] = bool(v)
        else:
            try:
                x = float(v)
            except (TypeError, ValueError):
                raise HTTPException(422, f"{p['label']} must be a number") from None
            x = min(max(x, p["min"]), p["max"])
            out[k] = int(x) if p["type"] == "int" else x
    if strategy == "orb" and out.get("target_r") == 0:
        out["target_r"] = None
    return out


@router.post("/run")
async def start_run(req: RunRequest, authorization: Optional[str] = Header(None)):
    _require(authorization)
    bt = _bt()
    if req.strategy not in bt.CATALOG:
        raise HTTPException(404, "Unknown strategy")
    if _job["status"] == "running":
        raise HTTPException(409, "A backtest is already running — wait for it to finish.")
    try:
        start, end = date.fromisoformat(req.start), date.fromisoformat(req.end)
    except ValueError:
        raise HTTPException(422, "Dates must be YYYY-MM-DD") from None
    earliest = date.fromisoformat(bt.CATALOG[req.strategy]["earliest"])
    start = max(start, earliest)
    end = min(end, date.today())
    if (end - start).days < 20:
        raise HTTPException(422, "Pick a window of at least a month.")
    params = _clean_params(req.strategy, req.params)
    equity = min(max(float(req.equity or 25_000), 1_000), 10_000_000)
    run_id = uuid.uuid4().hex[:12]
    _job.update(id=run_id, status="running", progress=None, error=None, started_at=time.time(),
                request={"strategy": req.strategy, "start": start.isoformat(), "end": end.isoformat(),
                         "params": params})

    def progress(i, n, day, eq):
        _job["progress"] = {"done": i, "total": n, "day": day, "equity": round(eq, 2)}

    def work():
        return bt.run(req.strategy, start, end, params, equity, progress)

    async def _bg():
        try:
            res = await asyncio.get_running_loop().run_in_executor(None, work)
            curve = _thin(res.pop("equity_curve", []))
            trades = res.pop("trade_list", [])
            run = {
                "id": run_id, "created_at": time.time(), "strategy": req.strategy,
                "label": (req.label or "").strip()[:80] or None,
                "start": start.isoformat(), "end": end.isoformat(), "params": params, "equity0": equity,
                "result": res, "equity_curve": curve, "trades": trades[-_MAX_TRADES:],
                "trades_total": len(trades),
            }
            os.makedirs(_RUNS_DIR, exist_ok=True)
            with open(os.path.join(_RUNS_DIR, f"{run_id}.json"), "w") as f:
                json.dump(run, f, default=str)
            for old in _saved()[_KEEP:]:
                try:
                    os.remove(os.path.join(_RUNS_DIR, f"{old['id']}.json"))
                except OSError:
                    pass
            _job.update(status="done")
        except Exception as e:
            print(f"[lab] run {run_id} failed: {e!r}", flush=True)
            _job.update(status="error", error=str(e)[:200])

    asyncio.create_task(_bg())
    return {"ok": True, "job": dict(_job)}
