"""
Research-backed day-trading modes for Paula's autopilot.

Each mode here is the live twin of a strategy in intraday_backtest.py: the same
rules and parameters, so the backtest number on the mode card describes what the
autopilot actually does. A mode only ships if it passed the backtest out of
sample (see docs/day-trading-research.md).

    momentum   Index intraday momentum ("noise area" + VWAP trail) on QQQ —
               Zarattini, Aziz & Barbon (2024). One position at most, checked
               on the half hour, flat by the close.

Rails shared with the small-cap modes:
  • flat by the close, every day
  • the PDT floor tightens the daily loss limit (smallcap_pullback.pdt_headroom)
  • paper account unless ALPACA_BASE is changed deliberately in trading.py

State (the half-hour slots already decided, today's entry) lives in
intraday_state.json next to the database.
"""
from __future__ import annotations

import json
import os
import pathlib
import statistics
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import requests

ET = ZoneInfo("America/New_York")
_HERE = pathlib.Path(__file__).parent
_STATE_DIR = pathlib.Path(os.environ.get("DB_DIR", str(_HERE / "desktop" / "backend")))
STATE_FILE = _STATE_DIR / "intraday_state.json"

_MOMENTUM = {
    "key": "momentum",
    "label": "Index momentum",
    "tagline": "Rides QQQ when it breaks out of its normal daily range; trails VWAP; flat by the close.",
    "SYMBOL": "QQQ",
    "LOOKBACK": 14,
    "BAND_MULT": 1.0,
    "TARGET_VOL": 0.02,
    "MAX_LEVERAGE": 2.0,
    "SIDES": "both",              # "both" | "long"
    "CHECK_EVERY": 30,
    "FLATTEN_AT": "15:50",
    "DAILY_LOSS_LIMIT": 0.03,
    # Backtest evidence shown on the mode card (intraday_backtest.run("noise", ...)
    # 2016-03 → 2026-09, 1-min SIP bars, $0.0035/sh + $0.001/sh slippage).
    "EVIDENCE": {"period": "2016–2026", "sharpe": 1.53, "cagr_pct": 19.6, "max_dd_pct": -9.9,
                 "oos_sharpe": 1.31, "oos_from": "2024-05"},
}

MODES = {"momentum": _MOMENTUM}


def get_mode(key: str) -> dict:
    mode = dict(MODES.get((key or "").lower(), _MOMENTUM))
    try:
        import strategy_custom
        mode = strategy_custom.apply_intraday(mode, mode["key"])
    except Exception:
        pass
    return mode


def mode_summary() -> list[dict]:
    out = []
    for k in MODES:
        m = get_mode(k)
        out.append({
            "key": k, "label": m["label"], "tagline": m["tagline"],
            "risk_per_trade": None, "max_positions": 1,
            "daily_loss_limit": m["DAILY_LOSS_LIMIT"], "rvol_min": None,
            "stats": f"{m['SYMBOL']} · up to {m['MAX_LEVERAGE']:g}x · "
                     f"{'long & short' if m['SIDES'] == 'both' else 'long only'} · "
                     f"daily loss limit {m['DAILY_LOSS_LIMIT']:.0%}",
            "evidence": m.get("EVIDENCE"),
        })
    return out


def _t():
    import trading
    return trading


# ── State ────────────────────────────────────────────────────────────────

def _load_state() -> dict:
    today = datetime.now(ET).date().isoformat()
    try:
        st = json.loads(STATE_FILE.read_text())
    except Exception:
        st = {}
    if st.get("day") != today:
        st = {"day": today, "slots": [], "position": None, "halted": False}
    return st


def _save_state(st: dict) -> None:
    if st.get("_dry"):
        return
    try:
        STATE_FILE.write_text(json.dumps(st, default=str))
    except Exception as e:
        print(f"[intraday] could not save state: {e}", flush=True)


# ── Market data ──────────────────────────────────────────────────────────

def _data_headers() -> dict:
    h = _t()._alpaca_headers()
    h.pop("Content-Type", None)
    return h


def _today_bars(symbol: str) -> list:
    """Today's regular-session 1-min bars from the real-time IEX feed (the free
    plan's only live feed; for QQQ it tracks SIP closely)."""
    now = datetime.now(ET)
    start = now.replace(hour=9, minute=30, second=0, microsecond=0)
    r = requests.get(f"https://data.alpaca.markets/v2/stocks/{symbol}/bars",
                     headers=_data_headers(),
                     params={"timeframe": "1Min", "start": start.isoformat(), "feed": "iex",
                             "limit": 1000, "sort": "asc"}, timeout=15)
    r.raise_for_status()
    return [[int(datetime.fromisoformat(b["t"].replace("Z", "+00:00")).timestamp()),
             b["o"], b["h"], b["l"], b["c"], b["v"], b.get("vw", b["c"])]
            for b in (r.json().get("bars") or [])]


def _history(symbol: str, lookback: int) -> tuple[dict, list[float]]:
    """Per-minute |move from open| for the last `lookback` full sessions, and
    the daily closes behind the vol target. SIP history via intraday_data's cache."""
    import intraday_data
    today = datetime.now(ET).date()
    series = intraday_data.minute_range(symbol, today - timedelta(days=lookback * 2 + 10),
                                        today - timedelta(days=1))
    days = [d for d in sorted(series) if len(series[d]) >= 300][-(lookback + 1):]
    moves = []
    for d in days[-lookback:]:
        bars = series[d]
        o = bars[0][1]
        mv = {}
        for b in bars:
            t = datetime.fromtimestamp(b[0], ET)
            mv[(t.hour - 9) * 60 + t.minute - 30] = abs(b[4] / o - 1)
        moves.append(mv)
    closes = [series[d][-1][4] for d in days]
    return moves, closes


def noise_levels(mode: dict, today_open: float, minute_index: int,
                 moves: list[dict], closes: list[float]) -> dict:
    """The upper/lower noise boundaries for the bar ending at minute_index+1."""
    sig = [m.get(minute_index) for m in moves if m.get(minute_index) is not None]
    sigma = (sum(sig) / len(sig)) * mode["BAND_MULT"] if sig else None
    prev_close = closes[-1] if closes else today_open
    rets = [closes[i] / closes[i - 1] - 1 for i in range(1, len(closes))]
    dvol = statistics.pstdev(rets) if len(rets) > 2 else 0.01
    lev = min(mode["MAX_LEVERAGE"], mode["TARGET_VOL"] / dvol) if dvol else 1.0
    if sigma is None:
        return {"sigma": None, "leverage": lev}
    return {
        "sigma": sigma,
        "upper": max(today_open, prev_close) * (1 + sigma),
        "lower": min(today_open, prev_close) * (1 - sigma),
        "leverage": lev,
        "prev_close": prev_close,
    }


# ── Orders ───────────────────────────────────────────────────────────────

def _order(payload: dict) -> dict:
    t = _t()
    try:
        r = requests.post(f"{t.ALPACA_BASE}/v2/orders", headers=t._alpaca_headers(),
                          json=payload, timeout=10)
        data = r.json()
        if r.status_code in (200, 201):
            return {"ok": True, "id": data.get("id")}
        return {"ok": False, "error": str(data.get("message", "rejected"))[:160]}
    except Exception as e:
        return {"ok": False, "error": str(e)[:160]}


def _cancel_symbol_orders(symbol: str) -> None:
    t = _t()
    try:
        r = requests.get(f"{t.ALPACA_BASE}/v2/orders", headers=t._alpaca_headers(),
                         params={"status": "open", "symbols": symbol}, timeout=10)
        for o in (r.json() if r.ok else []):
            requests.delete(f"{t.ALPACA_BASE}/v2/orders/{o['id']}", headers=t._alpaca_headers(), timeout=10)
    except Exception:
        pass


def _close(symbol: str) -> dict:
    """Cancel the protective stop, then flatten at market."""
    t = _t()
    _cancel_symbol_orders(symbol)
    try:
        r = requests.delete(f"{t.ALPACA_BASE}/v2/positions/{symbol}", headers=t._alpaca_headers(), timeout=10)
        return {"ok": r.status_code in (200, 204, 207), "error": None if r.ok else r.text[:160]}
    except Exception as e:
        return {"ok": False, "error": str(e)[:160]}


def _open(symbol: str, side: int, qty: int, disaster_stop: float) -> dict:
    """Market entry, then a GTC-day protective stop at the far noise boundary.
    The strategy's real exits are the half-hour checks; the stop only exists
    so a crash between checks (or a Paula outage) can't run unbounded."""
    res = _order({"symbol": symbol, "qty": str(qty), "side": "buy" if side > 0 else "sell",
                  "type": "market", "time_in_force": "day"})
    if not res["ok"]:
        return res
    stop = _order({"symbol": symbol, "qty": str(qty), "side": "sell" if side > 0 else "buy",
                   "type": "stop", "stop_price": str(round(disaster_stop, 2)), "time_in_force": "day"})
    res["stop_ok"] = stop["ok"]
    return res


# ── The cycle ────────────────────────────────────────────────────────────

def run(mode_key: str = "momentum", dry_run: bool = False, skip_market_check: bool = False) -> dict:
    t = _t()
    mode = get_mode(mode_key)
    sym = mode["SYMBOL"]
    log = [f"**Mode: {mode['label']}** — {mode['tagline']}"]
    out = {"ok": True, "log": log, "buys": 0, "sells": 0, "shorts": 0, "mode": mode["key"], "scanned": 1}
    now = datetime.now(ET)

    is_open, status = t._market_is_open()
    if not is_open and not skip_market_check and not dry_run:
        log.append(status)
        return out

    st = _load_state()
    if dry_run:
        st["_dry"] = True      # a dry run must not consume today's half-hour slots
    account = t.alpaca_account()
    if not account:
        return {**out, "ok": False, "log": log + ["Alpaca account unavailable."]}
    equity = float(account["equity"])

    positions = {p["ticker"]: p for p in (t.alpaca_positions() or [])}
    held = positions.get(sym)
    pos_side = 0
    if held and st.get("position"):
        pos_side = 1 if held.get("side", "long") == "long" else -1
    elif held and not st.get("position"):
        log.append(f"ℹ️ {sym} is held but wasn't opened by this mode — leaving it alone.")
    elif st.get("position") and not held:
        log.append(f"{sym} position is gone (stop filled or closed by hand).")
        st["position"] = None

    # ── Flat by the close ────────────────────────────────────────────────
    flat_h, flat_m = map(int, mode["FLATTEN_AT"].split(":"))
    if (now.hour, now.minute) >= (flat_h, flat_m):
        if pos_side:
            if not dry_run:
                _close(sym)
            st["position"] = None
            out["sells"] += 1
            log.append(f"🔔 **{sym} flattened** — {mode['FLATTEN_AT']} rail. This mode never holds overnight.")
        else:
            log.append("Flat for the day.")
        _save_state(st)
        return out

    # ── Loss limit (PDT floor tightens it) ────────────────────────────────
    limit = mode["DAILY_LOSS_LIMIT"]
    try:
        import smallcap_pullback
        pdt = smallcap_pullback.pdt_headroom(equity)
        if pdt["applies"]:
            if pdt["blocked"]:
                log.append(f"🛑 Equity ${equity:,.0f} is at the PDT floor — no new day trades.")
                st["halted"] = True
            else:
                limit = min(limit, pdt["max_loss_pct"])
    except Exception:
        pass
    day_pnl = float(account.get("daily_pnl", 0) or 0)
    if equity and day_pnl / equity <= -limit and not st.get("halted"):
        st["halted"] = True
        if pos_side and not dry_run:
            _close(sym)
            st["position"] = None
            out["sells"] += 1
        log.append(f"🛑 **Daily loss limit hit** ({day_pnl / equity:.2%}). Flat and done for the day.")

    # ── Decide only on the half hour, once per slot ───────────────────────
    mins = (now.hour - 9) * 60 + now.minute - 30
    slot = mins - mins % mode["CHECK_EVERY"]
    if slot < 30 or (slot in st["slots"] and not dry_run):
        nxt = slot + mode["CHECK_EVERY"] if slot >= 30 else 30
        h, m = divmod(9 * 60 + 30 + nxt, 60)
        log.append(f"Next check at {h}:{m:02d} ET." + (f" Holding {sym} {'long' if pos_side > 0 else 'short'}." if pos_side else ""))
        _save_state(st)
        return out

    try:
        bars = _today_bars(sym)
        moves, closes = _history(sym, mode["LOOKBACK"])
    except Exception as e:
        return {**out, "ok": False, "log": log + [f"Market data unavailable: {str(e)[:120]}"]}
    # The decision bar is the last one that closed at or before the slot.
    decision = [b for b in bars if (datetime.fromtimestamp(b[0], ET).hour - 9) * 60
                + datetime.fromtimestamp(b[0], ET).minute - 30 < slot]
    if len(decision) < 20 or len(moves) < mode["LOOKBACK"] // 2:
        log.append("Not enough bars yet to judge today's range.")
        _save_state(st)
        return out
    today_open = bars[0][1]
    px = decision[-1][4]
    lv = noise_levels(mode, today_open, slot - 1, moves, closes)
    if lv["sigma"] is None:
        log.append("No noise band for this time of day yet.")
        _save_state(st)
        return out
    pv = sum(b[6] * b[5] for b in bars if b[0] <= decision[-1][0])
    vv = sum(b[5] for b in bars if b[0] <= decision[-1][0])
    vwap = pv / vv if vv else px
    st["slots"].append(slot)
    log.append(f"{sym} ${px:.2f} · range ${lv['lower']:.2f}–${lv['upper']:.2f} · VWAP ${vwap:.2f}")

    # exits first: trailing stop = tighter of the band and VWAP
    if pos_side > 0 and px < max(lv["upper"], vwap):
        if not dry_run:
            _close(sym)
        st["position"] = None
        pos_side = 0
        out["sells"] += 1
        log.append(f"📤 **Closed {sym} long** — back inside the range / below VWAP.")
    elif pos_side < 0 and px > min(lv["lower"], vwap):
        if not dry_run:
            _close(sym)
        st["position"] = None
        pos_side = 0
        out["sells"] += 1
        log.append(f"📤 **Covered {sym} short** — back inside the range / above VWAP.")

    if pos_side == 0 and not st.get("halted"):
        side = 1 if px > lv["upper"] else (-1 if px < lv["lower"] and mode["SIDES"] == "both" else 0)
        if side:
            buying_power = float(account.get("buying_power", equity) or equity)
            qty = int(min(equity * lv["leverage"], buying_power * 0.95) / px)
            if qty > 0:
                stop = lv["lower"] if side > 0 else lv["upper"]
                res = {"ok": True} if dry_run else _open(sym, side, qty, stop)
                if res["ok"]:
                    st["position"] = {"side": side, "qty": qty, "entry": px, "at": now.isoformat()}
                    if side > 0:
                        out["buys"] += 1
                    else:
                        out["shorts"] += 1
                    log.append(f"{'📥 **Bought' if side > 0 else '📉 **Shorted'} {qty} {sym}** @ ~${px:.2f} "
                               f"({lv['leverage']:.1f}x) — broke {'above' if side > 0 else 'below'} its normal range. "
                               f"Disaster stop ${stop:.2f}.")
                else:
                    log.append(f"⚠️ Order rejected: {res.get('error')}")
        else:
            log.append("Inside its normal range — no trade.")
    _save_state(st)
    return out
