"""
Crypto day trading for Paula's autopilot: the index-momentum rules from
intraday_modes.py ("noise area" breakout + VWAP trail) applied to BTC and ETH.

It runs alongside whichever stock mode is selected, around the clock, because
crypto never closes. Differences from the QQQ mode, all forced by the market:

  • the "day" is the UTC day: its 00:00 bar is the open, and positions are
    flattened at FLATTEN_AT UTC so nothing carries into the next day's band
  • long only, no leverage (Alpaca crypto can't be shorted or bought on margin)
  • at most ALLOCATION of the account in crypto, split evenly across symbols,
    sized down on volatile days (TARGET_VOL / recent daily volatility)
  • its own daily loss limit, counted on crypto P&L only
  • the disaster stop is a stop-limit (Alpaca crypto has no plain stop orders)

NOT backtested: the owner asked for it live on the paper account before a
backtest. Treat its results as the experiment.

State lives in intraday_crypto_state.json next to the database.
"""
from __future__ import annotations

import json
import os
import pathlib
import statistics
import time
from datetime import datetime, timedelta, timezone

import requests

UTC = timezone.utc
_HERE = pathlib.Path(__file__).parent
_STATE_DIR = pathlib.Path(os.environ.get("DB_DIR", str(_HERE / "desktop" / "backend")))
STATE_FILE = _STATE_DIR / "intraday_crypto_state.json"
_BARS_URL = "https://data.alpaca.markets/v1beta3/crypto/us/bars"

MODE = {
    "key": "crypto",
    "label": "Crypto momentum",
    "tagline": "Buys BTC/ETH when they break above their normal daily range; trails VWAP; flat by 23:50 UTC.",
    "SYMBOLS": ["BTC/USD", "ETH/USD"],
    "LOOKBACK": 14,
    "BAND_MULT": 1.0,
    "TARGET_VOL": 0.03,          # crypto's calm-day daily vol; busier days size down
    "ALLOCATION": 0.25,          # most of the account in crypto at once
    "CHECK_EVERY": 30,
    "FLATTEN_AT": "23:50",       # UTC
    "DAILY_LOSS_LIMIT": 0.01,    # of account equity, crypto P&L only
    "STOP_LIMIT_SLIP": 0.01,     # stop-limit's limit sits this far past the stop
    "EVIDENCE": None,
}


def _t():
    import trading
    return trading


def enabled() -> bool:
    try:
        return bool(_t().load_autopilot_config(apply_custom=False).get("CRYPTO_ENABLED", True))
    except Exception:
        return True


def _pos_symbol(sym: str) -> str:
    return sym.replace("/", "")


# ── State ────────────────────────────────────────────────────────────────

def _load_state() -> dict:
    today = datetime.now(UTC).date().isoformat()
    try:
        st = json.loads(STATE_FILE.read_text())
    except Exception:
        st = {}
    if st.get("day") != today:
        st = {"day": today, "slots": [], "positions": {}, "realized": 0.0, "halted": False}
    return st


def _save_state(st: dict) -> None:
    if st.get("_dry"):
        return
    try:
        STATE_FILE.write_text(json.dumps(st, default=str))
    except Exception as e:
        print(f"[crypto] could not save state: {e}", flush=True)


# ── Market data ──────────────────────────────────────────────────────────

_hist_cache: dict = {}


def _bars(sym: str, start: datetime, end: datetime | None = None) -> list:
    h = _t()._alpaca_headers()
    h.pop("Content-Type", None)
    params = {"symbols": sym, "timeframe": "1Min", "start": start.isoformat().replace("+00:00", "Z"),
              "limit": 10000, "sort": "asc"}
    if end:
        params["end"] = end.isoformat().replace("+00:00", "Z")
    out, token = [], None
    for _ in range(10):
        if token:
            params["page_token"] = token
        r = requests.get(_BARS_URL, headers=h, params=params, timeout=20)
        r.raise_for_status()
        j = r.json()
        for b in (j.get("bars") or {}).get(sym) or []:
            out.append([int(datetime.fromisoformat(b["t"].replace("Z", "+00:00")).timestamp()),
                        b["o"], b["h"], b["l"], b["c"], b["v"], b.get("vw", b["c"])])
        token = j.get("next_page_token")
        if not token:
            break
    return out


def _minute(ts: int) -> int:
    d = datetime.fromtimestamp(ts, UTC)
    return d.hour * 60 + d.minute


def _history(sym: str, lookback: int) -> tuple[list[dict], list[float]]:
    """Per-minute |move from the UTC open| for the last `lookback` UTC days,
    and those days' closes. Cached for the day."""
    today = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    key = (sym, today.date().isoformat(), lookback)
    if key in _hist_cache:
        return _hist_cache[key]
    bars = _bars(sym, today - timedelta(days=lookback + 1), today)
    days: dict[str, list] = {}
    for b in bars:
        days.setdefault(datetime.fromtimestamp(b[0], UTC).date().isoformat(), []).append(b)
    full = [d for d in sorted(days) if len(days[d]) >= 1000][-(lookback + 1):]
    moves = []
    for d in full[-lookback:]:
        o = days[d][0][1]
        mv, last = {}, 0.0
        by_min = {_minute(b[0]): abs(b[4] / o - 1) for b in days[d]}
        for m in range(1440):          # carry the last move over minutes with no trade
            last = by_min.get(m, last)
            mv[m] = last
        moves.append(mv)
    closes = [days[d][-1][4] for d in full]
    _hist_cache.clear()
    _hist_cache[key] = (moves, closes)
    return moves, closes


def noise_levels(mode: dict, today_open: float, minute_index: int,
                 moves: list[dict], closes: list[float]) -> dict:
    sig = [m[minute_index] for m in moves if minute_index in m]
    sigma = (sum(sig) / len(sig)) * mode["BAND_MULT"] if sig else None
    rets = [closes[i] / closes[i - 1] - 1 for i in range(1, len(closes))]
    dvol = statistics.pstdev(rets) if len(rets) > 2 else 0.04
    scale = min(1.0, mode["TARGET_VOL"] / dvol) if dvol else 1.0
    if sigma is None:
        return {"sigma": None, "scale": scale}
    prev_close = closes[-1] if closes else today_open
    return {
        "sigma": sigma,
        "upper": max(today_open, prev_close) * (1 + sigma),
        "lower": min(today_open, prev_close) * (1 - sigma),
        "scale": scale,
        "dvol": dvol,
    }


# ── Orders ───────────────────────────────────────────────────────────────

def _order(payload: dict) -> dict:
    t = _t()
    try:
        r = requests.post(f"{t.ALPACA_BASE}/v2/orders", headers=t._alpaca_headers(), json=payload, timeout=10)
        data = r.json()
        if r.status_code in (200, 201):
            return {"ok": True, "id": data.get("id")}
        return {"ok": False, "error": str(data.get("message", "rejected"))[:160]}
    except Exception as e:
        return {"ok": False, "error": str(e)[:160]}


def _positions() -> dict:
    """Crypto positions by pair ('BTC/USD') straight from Alpaca."""
    t = _t()
    r = requests.get(f"{t.ALPACA_BASE}/v2/positions", headers=t._alpaca_headers(), timeout=10)
    r.raise_for_status()
    out = {}
    for p in r.json():
        if p.get("asset_class") == "crypto":
            sym = p["symbol"] if "/" in p["symbol"] else p["symbol"][:-3] + "/USD"
            out[sym] = p
    return out


def _cancel_orders(sym: str) -> None:
    t = _t()
    try:
        r = requests.get(f"{t.ALPACA_BASE}/v2/orders", headers=t._alpaca_headers(),
                         params={"status": "open", "limit": 200}, timeout=10)
        for o in (r.json() if r.ok else []):
            if o.get("symbol") in (sym, _pos_symbol(sym)):
                requests.delete(f"{t.ALPACA_BASE}/v2/orders/{o['id']}", headers=t._alpaca_headers(), timeout=10)
    except Exception:
        pass


def _close(sym: str) -> dict:
    t = _t()
    _cancel_orders(sym)
    time.sleep(0.5)
    try:
        r = requests.delete(f"{t.ALPACA_BASE}/v2/positions/{_pos_symbol(sym)}",
                            headers=t._alpaca_headers(), timeout=10)
        return {"ok": r.status_code in (200, 204, 207), "error": None if r.ok else r.text[:160]}
    except Exception as e:
        return {"ok": False, "error": str(e)[:160]}


def _open(mode: dict, sym: str, notional: float, disaster_stop: float) -> dict:
    """Market buy by dollar amount, then a GTC stop-limit on what actually
    filled (Alpaca takes its fee in the coin, so the fill is a bit under)."""
    res = _order({"symbol": sym, "notional": f"{notional:.2f}", "side": "buy",
                  "type": "market", "time_in_force": "gtc"})
    if not res["ok"]:
        return res
    qty = None
    for _ in range(6):
        time.sleep(1)
        try:
            p = _positions().get(sym)
            if p:
                qty = p.get("qty_available") or p.get("qty")
                break
        except Exception:
            pass
    res["stop_ok"] = False
    if qty:
        stop = _order({"symbol": sym, "qty": str(qty), "side": "sell", "type": "stop_limit",
                       "stop_price": f"{disaster_stop:.2f}",
                       "limit_price": f"{disaster_stop * (1 - mode['STOP_LIMIT_SLIP']):.2f}",
                       "time_in_force": "gtc"})
        res["stop_ok"] = stop["ok"]
        res["stop_error"] = stop.get("error")
    return res


# ── The cycle ────────────────────────────────────────────────────────────

def _slot(mode: dict, now: datetime) -> int:
    mins = now.hour * 60 + now.minute
    return mins - mins % mode["CHECK_EVERY"]


def due(now: datetime | None = None) -> bool:
    """Cheap check (no API calls): is a half-hour decision or the flatten due?"""
    mode = MODE
    now = now or datetime.now(UTC)
    st = _load_state()
    fh, fm = map(int, mode["FLATTEN_AT"].split(":"))
    if (now.hour, now.minute) >= (fh, fm):
        return bool(st.get("positions"))
    s = _slot(mode, now)
    return s >= 30 and s not in st["slots"]


def run(dry_run: bool = False) -> dict:
    t = _t()
    mode = MODE
    log = [f"**{mode['label']}** — {mode['tagline']}"]
    out = {"ok": True, "log": log, "buys": 0, "sells": 0, "shorts": 0, "mode": "crypto",
           "scanned": len(mode["SYMBOLS"]), "entries": []}
    now = datetime.now(UTC)
    st = _load_state()
    if dry_run:
        st["_dry"] = True

    account = t.alpaca_account()
    if not account:
        return {**out, "ok": False, "log": log + ["Alpaca account unavailable."]}
    equity = float(account["equity"])
    try:
        held = _positions()
    except Exception as e:
        return {**out, "ok": False, "log": log + [f"Positions unavailable: {str(e)[:120]}"]}

    mine = st.setdefault("positions", {})
    for sym in list(mine):
        if sym not in held:
            log.append(f"{sym} position is gone (stop filled or closed by hand).")
            mine.pop(sym)

    def close(sym: str, why: str) -> None:
        p = held.get(sym) or {}
        if not dry_run:
            res = _close(sym)
            if not res["ok"]:
                log.append(f"⚠️ Could not close {sym}: {res['error']}")
                return
        st["realized"] = st.get("realized", 0.0) + float(p.get("unrealized_pl", 0) or 0)
        mine.pop(sym, None)
        out["sells"] += 1
        log.append(f"📤 **Sold {sym}** — {why}")

    # ── Flat by the end of the UTC day ───────────────────────────────────
    fh, fm = map(int, mode["FLATTEN_AT"].split(":"))
    if (now.hour, now.minute) >= (fh, fm):
        for sym in list(mine):
            close(sym, f"{mode['FLATTEN_AT']} UTC rail; never holds into the next day.")
        if not mine:
            log.append("Flat for the day.")
        _save_state(st)
        return out

    # ── Crypto-only daily loss limit ─────────────────────────────────────
    open_pl = sum(float(held[s].get("unrealized_pl", 0) or 0) for s in mine if s in held)
    day_pl = st.get("realized", 0.0) + open_pl
    if equity and day_pl / equity <= -mode["DAILY_LOSS_LIMIT"] and not st.get("halted"):
        st["halted"] = True
        for sym in list(mine):
            close(sym, "crypto daily loss limit hit.")
        log.append(f"🛑 **Crypto loss limit hit** (${day_pl:,.0f}). Done until 00:00 UTC.")

    slot = _slot(mode, now)
    if slot < 30 or (slot in st["slots"] and not dry_run):
        _save_state(st)
        return out
    st["slots"].append(slot)
    out["decided"] = True

    per_symbol = equity * mode["ALLOCATION"] / len(mode["SYMBOLS"])
    today0 = now.replace(hour=0, minute=0, second=0, microsecond=0)
    for sym in mode["SYMBOLS"]:
        try:
            bars = _bars(sym, today0)
            moves, closes = _history(sym, mode["LOOKBACK"])
        except Exception as e:
            log.append(f"{sym}: market data unavailable ({str(e)[:100]})")
            continue
        decision = [b for b in bars if _minute(b[0]) < slot]
        if len(decision) < 20 or len(moves) < mode["LOOKBACK"] // 2:
            log.append(f"{sym}: not enough bars yet to judge today's range.")
            continue
        today_open = bars[0][1]
        px = decision[-1][4]
        lv = noise_levels(mode, today_open, slot - 1, moves, closes)
        if lv["sigma"] is None:
            continue
        pv = sum(b[6] * b[5] for b in decision)
        vv = sum(b[5] for b in decision)
        vwap = pv / vv if vv else px
        log.append(f"{sym} ${px:,.2f} · range ${lv['lower']:,.2f}–${lv['upper']:,.2f} · VWAP ${vwap:,.2f}")

        if sym in mine and px < max(lv["upper"], vwap):
            close(sym, "back inside its range / below VWAP.")
        elif sym not in mine and sym in held:
            log.append(f"ℹ️ {sym} is held but wasn't bought by this mode — leaving it alone.")
        elif sym not in mine and not st.get("halted") and px > lv["upper"]:
            cash = float(account.get("non_marginable_buying_power", equity) or 0)
            notional = min(per_symbol * lv["scale"], cash * 0.95)
            if notional < 10:
                log.append(f"{sym}: broke out but only ${cash:,.0f} cash free — skipped.")
                continue
            res = {"ok": True, "stop_ok": True} if dry_run else _open(mode, sym, notional, lv["lower"])
            if res["ok"]:
                mine[sym] = {"notional": round(notional, 2), "entry": px, "at": now.isoformat()}
                out["buys"] += 1
                out["entries"].append({"ticker": sym, "qty": round(notional / px, 6), "entry": px,
                                       "stop": lv["lower"]})
                log.append(f"📥 **Bought ${notional:,.0f} of {sym}** @ ~${px:,.2f} ({lv['scale']:.2f}x size) — "
                           f"broke above its normal range. Disaster stop ${lv['lower']:,.2f}."
                           + ("" if res.get("stop_ok") else f" ⚠️ Stop not placed: {res.get('stop_error')}"))
            else:
                log.append(f"⚠️ {sym} order rejected: {res.get('error')}")
        elif sym not in mine:
            log.append(f"{sym}: inside its normal range — no trade.")
    _save_state(st)
    return out
