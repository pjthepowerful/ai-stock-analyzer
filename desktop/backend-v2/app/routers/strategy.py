"""
Owner-only strategy health checks: the signal-validation study (does a higher
score actually predict a higher forward return?) and the validated backtest
(does the strategy survive costs and beat random entries?).

Both take minutes, so they run as background jobs: POST starts one (a second
POST while it runs is a no-op), GET reports status plus the last result. The
last result of each is saved to disk so the panel loads instantly. The
signal-validation file is the same one the original admin panel reads.
Neither job places orders or changes any setting.
"""
import asyncio
import json
import os
import time
from typing import Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from ..bridge import auth, engine
from ..deps import admin_required

router = APIRouter(prefix="/api/admin/strategy", tags=["strategy"])

_DATA_DIR = os.environ.get("DB_DIR", os.path.dirname(os.path.abspath(auth.__file__)))
_FILES = {
    "signal": os.path.join(_DATA_DIR, "signal_validation.json"),
    "backtest": os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "backtest_validation.json"),
}
_jobs: dict[str, dict] = {k: {"status": "idle", "error": None, "started_at": None, "task": None} for k in _FILES}


def _load(kind: str):
    try:
        with open(_FILES[kind]) as f:
            return json.load(f)
    except Exception:
        return None


def _save(kind: str, result: dict) -> None:
    try:
        with open(_FILES[kind], "w") as f:
            json.dump(result, f, default=str)
    except Exception as e:
        print(f"[strategy] could not save {kind} result: {e}", flush=True)


def _run_signal(horizon: int) -> dict:
    import signal_study

    return signal_study.run_signal_validation(years=2.0, horizon=horizon)


def _run_backtest(days: int) -> dict:
    import backtest

    cfg = {}
    try:
        path = engine.autopilot_cfg_path()
        if path.exists():
            cfg = json.loads(path.read_text())
    except Exception:
        pass
    res = backtest.run_backtest(
        days=days,
        min_score=cfg.get("MIN_SCORE", 82),
        max_positions=cfg.get("MAX_POSITIONS", 1),
        stop_pct=cfg.get("STOP_FLOOR", 0.013),
        validate=True,
    )
    # The equity curve and per-trade list are large and the panel only needs
    # the summary; keep the file small.
    res.pop("equity_curve", None)
    res["trades"] = (res.get("trades") or [])[-20:]
    res["params"] = {"days": days, "min_score": cfg.get("MIN_SCORE", 82)}
    res["generated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    return res


def _relabel_signal(res: dict | None) -> dict | None:
    """signal_study's verdict only tests IC >= +0.03 and |IC| < 0.03, so a
    clearly NEGATIVE IC (higher scores -> worse returns) falls through to
    "MIXED". That's the most important thing the study can say, so say it."""
    if res and isinstance(res.get("rank_ic"), (int, float)) and res["rank_ic"] <= -0.03:
        res = {**res, "verdict": "INVERTED", "detail": (
            "Higher scores have been followed by WORSE forward returns — the score is "
            "ranking backwards. Raising MIN_SCORE would select for weaker trades, not "
            "stronger ones.")}
    return res


def _status(kind: str) -> dict:
    job = _jobs[kind]
    result = _load(kind)
    return {
        "status": job["status"],
        "error": job["error"],
        "started_at": job["started_at"],
        "result": _relabel_signal(result) if kind == "signal" else result,
    }


@router.get("")
def status(authorization: Optional[str] = Header(None)):
    admin_required(authorization)
    return {"ok": True, "signal": _status("signal"), "backtest": _status("backtest")}


class RunRequest(BaseModel):
    horizon: int = 5   # signal: forward-return horizon in trading days
    days: int = 365    # backtest: lookback window


@router.post("/{kind}")
async def run(kind: str, req: RunRequest, authorization: Optional[str] = Header(None)):
    admin_required(authorization)
    if kind not in _jobs:
        raise HTTPException(404, "Unknown job")
    job = _jobs[kind]
    if job["status"] == "running":
        return {"ok": True, **_status(kind)}

    if kind == "signal":
        horizon = max(1, min(req.horizon, 60))
        work = lambda: _run_signal(horizon)  # noqa: E731
    else:
        days = max(30, min(req.days, 730))
        work = lambda: _run_backtest(days)  # noqa: E731

    async def _bg():
        try:
            res = await asyncio.get_running_loop().run_in_executor(None, work)
            if res and res.get("ok"):
                _save(kind, res)
                job.update(status="done", error=None)
            else:
                job.update(status="error", error=(res or {}).get("error", "Run failed"))
        except Exception as e:
            job.update(status="error", error=str(e)[:200])

    job.update(status="running", error=None, started_at=time.time())
    job["task"] = asyncio.ensure_future(_bg())
    return {"ok": True, **_status(kind)}
