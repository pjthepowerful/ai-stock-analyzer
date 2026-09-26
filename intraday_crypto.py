"""
Crypto trend trading for Paula's autopilot: a 24/7 breakout system across every
non-stablecoin token Alpaca lists, running alongside whichever stock mode is on.

    Entry  (checked on the hour):   last 5-min close > highest high of the prior 72 hours
    Exit   (checked every 15 min):  last 5-min close < lowest low of the prior 24 hours

Positions carry across days — crypto never closes, so there's no end-of-day
flatten. Long only, no leverage (Alpaca crypto can't be shorted or margined).
Each token gets an equal slice of ALLOCATION of the account.

Why these rules (scratch backtest, 5-min Alpaca bars, 32 tokens, Mar–Sep 2026,
0.25% fee + 0.05% slippage per side, rules picked on the first 90 days):
  • the earlier UTC-day "noise area" port lost 38–97% after fees; faster checks lost more
  • this system: first 90 days −4.1% (max drawdown −6.5%) while buy-and-hold lost 19.3%;
    last 90 days (untouched) +15.2% (max drawdown −6.5%) while buy-and-hold made 69.2%
  • checking entries every 5 min instead of hourly doubled the trades and the drawdown
So it's a trend filter: it sidesteps most of a falling market and lags a rising one.
Research: crypto time-series momentum is well documented; cross-sectional is weak.

A GTC stop-limit sits CATASTROPHE_STOP below each entry so an outage can't
leave a position unbounded; the 24h-low exit is the real one.

State (which coins this mode bought) lives in intraday_crypto_state.json.
"""
from __future__ import annotations

import json
import os
import pathlib
import time
from datetime import datetime, timedelta, timezone

import requests

UTC = timezone.utc
_HERE = pathlib.Path(__file__).parent
_STATE_DIR = pathlib.Path(os.environ.get("DB_DIR", str(_HERE / "desktop" / "backend")))
STATE_FILE = _STATE_DIR / "intraday_crypto_state.json"
_BARS_URL = "https://data.alpaca.markets/v1beta3/crypto/us/bars"

# Stablecoins and gold don't trend; they'd only pay fees.
_EXCLUDE = {"USDT/USD", "USDC/USD", "USDG/USD", "PAXG/USD", "DAI/USD"}

MODE = {
    "key": "crypto",
    "label": "Crypto trend",
    "tagline": "Buys any listed token that breaks its 72-hour high; sells when it breaks its 24-hour low. 24/7.",
    "ENTRY_HOURS": 72,
    "EXIT_HOURS": 24,
    "ENTRY_EVERY": 60,           # minutes
    "EXIT_EVERY": 15,            # minutes
    "ALLOCATION": 0.25,          # most of the account in crypto, split evenly per token
    "CATASTROPHE_STOP": 0.15,    # resting stop-limit this far under entry
    "STOP_LIMIT_SLIP": 0.02,
    "MIN_NOTIONAL": 10.0,
    "EVIDENCE": {"period": "Mar–Sep 2026", "first_half_pct": -4.1, "second_half_pct": 15.2,
                 "max_dd_pct": -6.5, "buy_hold_first_pct": -19.3, "buy_hold_second_pct": 69.2},
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
    try:
        st = json.loads(STATE_FILE.read_text())
    except Exception:
        st = {}
    st.setdefault("positions", {})
    st.setdefault("last_slot", None)
    return st


def _save_state(st: dict) -> None:
    if st.get("_dry"):
        return
    try:
        STATE_FILE.write_text(json.dumps({k: v for k, v in st.items() if not k.startswith("_")}, default=str))
    except Exception as e:
        print(f"[crypto] could not save state: {e}", flush=True)


def _slot(now: datetime) -> str:
    m = now.minute - now.minute % MODE["EXIT_EVERY"]
    return now.replace(minute=m, second=0, microsecond=0).isoformat()


def due(now: datetime | None = None) -> bool:
    """Cheap check (no API calls): has a new 15-minute slot started?"""
    return _load_state().get("last_slot") != _slot(now or datetime.now(UTC))


# ── Market data ──────────────────────────────────────────────────────────

_universe_cache: dict = {"at": 0.0, "symbols": []}


def universe() -> list[str]:
    """Every tradable USD crypto pair on Alpaca, minus stablecoins. Refreshed daily."""
    if time.time() - _universe_cache["at"] < 86400 and _universe_cache["symbols"]:
        return _universe_cache["symbols"]
    t = _t()
    r = requests.get(f"{t.ALPACA_BASE}/v2/assets", headers=t._alpaca_headers(),
                     params={"asset_class": "crypto", "status": "active"}, timeout=15)
    r.raise_for_status()
    syms = sorted(a["symbol"] for a in r.json()
                  if a.get("tradable") and a["symbol"].endswith("/USD") and a["symbol"] not in _EXCLUDE)
    _universe_cache.update(at=time.time(), symbols=syms)
    return syms


def _bars(symbols: list[str], start: datetime) -> dict[str, list]:
    """5-min bars for many symbols at once: {sym: [[ts, o, h, l, c, v], ...]}."""
    h = _t()._alpaca_headers()
    h.pop("Content-Type", None)
    params = {"symbols": ",".join(symbols), "timeframe": "5Min",
              "start": start.isoformat().replace("+00:00", "Z"), "limit": 10000, "sort": "asc"}
    out: dict[str, list] = {}
    for _ in range(20):
        r = requests.get(_BARS_URL, headers=h, params=params, timeout=30)
        r.raise_for_status()
        j = r.json()
        for sym, bs in (j.get("bars") or {}).items():
            out.setdefault(sym, []).extend(
                [int(datetime.fromisoformat(b["t"].replace("Z", "+00:00")).timestamp()),
                 b["o"], b["h"], b["l"], b["c"], b["v"]] for b in bs)
        if not j.get("next_page_token"):
            break
        params["page_token"] = j["next_page_token"]
    return out


def levels(bars: list, now_ts: int) -> dict | None:
    """Breakout levels from CLOSED 5-min bars: the last close, the prior-72h
    high and prior-24h low (both excluding that last bar)."""
    closed = [b for b in bars if b[0] + 300 <= now_ts]
    if len(closed) < 2:
        return None
    last = closed[-1]
    prior = closed[:-1]
    hi_from = last[0] - MODE["ENTRY_HOURS"] * 3600
    lo_from = last[0] - MODE["EXIT_HOURS"] * 3600
    hi_bars = [b for b in prior if b[0] >= hi_from]
    lo_bars = [b for b in prior if b[0] >= lo_from]
    # Need most of the window, or a thin/new listing looks like a breakout.
    if len(hi_bars) < MODE["ENTRY_HOURS"] * 12 * 0.6 or not lo_bars:
        return None
    return {"px": last[4], "high": max(b[2] for b in hi_bars), "low": min(b[3] for b in lo_bars)}


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
                         params={"status": "open", "limit": 500}, timeout=10)
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


def _open(sym: str, notional: float, px: float) -> dict:
    """Market buy by dollar amount, then a GTC catastrophe stop-limit on what
    actually filled (Alpaca takes its fee in the coin, so the fill is a bit under)."""
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
    stop = px * (1 - MODE["CATASTROPHE_STOP"])
    res["stop"] = stop
    res["stop_ok"] = False
    if qty:
        s = _order({"symbol": sym, "qty": str(qty), "side": "sell", "type": "stop_limit",
                    "stop_price": _fmt_price(stop), "limit_price": _fmt_price(stop * (1 - MODE["STOP_LIMIT_SLIP"])),
                    "time_in_force": "gtc"})
        res["stop_ok"] = s["ok"]
        res["stop_error"] = s.get("error")
    return res


def _fmt_price(p: float) -> str:
    # Sub-cent tokens (PEPE, SHIB, BONK) need more than 2 decimals.
    return f"{p:.2f}" if p >= 1 else f"{p:.8f}".rstrip("0")


def _fmt_px(p: float) -> str:
    return f"${p:,.2f}" if p >= 1 else f"${p:.8f}".rstrip("0")


# ── The cycle ────────────────────────────────────────────────────────────

def run(dry_run: bool = False) -> dict:
    t = _t()
    now = datetime.now(UTC)
    st = _load_state()
    if dry_run:
        st["_dry"] = True
    entries_due = now.minute < MODE["EXIT_EVERY"]     # the slot that starts on the hour
    log = [f"**{MODE['label']}** — {'entries + exits' if entries_due else 'exit check'}"]
    out = {"ok": True, "log": log, "buys": 0, "sells": 0, "shorts": 0, "mode": "crypto", "entries": []}

    account = t.alpaca_account()
    if not account:
        return {**out, "ok": False, "log": log + ["Alpaca account unavailable."]}
    equity = float(account["equity"])
    try:
        held = _positions()
        syms = universe()
    except Exception as e:
        return {**out, "ok": False, "log": log + [f"Alpaca unavailable: {str(e)[:120]}"]}

    mine = st["positions"]
    for sym in list(mine):
        if sym not in held:
            log.append(f"{sym} position is gone (catastrophe stop filled or closed by hand).")
            mine.pop(sym)

    check = sorted(set(mine) | (set(syms) if entries_due else set()))
    out["scanned"] = len(check)
    if not check:
        st["last_slot"] = _slot(now)
        _save_state(st)
        log.append("Nothing held; next entry check on the hour.")
        return out
    try:
        bars = _bars(check, now - timedelta(hours=MODE["ENTRY_HOURS"] + 1))
    except Exception as e:
        return {**out, "ok": False, "log": log + [f"Market data unavailable: {str(e)[:120]}"]}
    st["last_slot"] = _slot(now)

    # Exits first.
    for sym in list(mine):
        lv = levels(bars.get(sym) or [], int(now.timestamp()))
        if not lv or lv["px"] >= lv["low"]:
            continue
        pl = float(held[sym].get("unrealized_pl", 0) or 0)
        if not dry_run:
            res = _close(sym)
            if not res["ok"]:
                log.append(f"⚠️ Could not sell {sym}: {res['error']}")
                continue
        mine.pop(sym)
        out["sells"] += 1
        log.append(f"📤 **Sold {sym}** @ ~{_fmt_px(lv['px'])} — broke its 24-hour low {_fmt_px(lv['low'])} "
                   f"({'+' if pl >= 0 else '−'}${abs(pl):,.2f}).")

    if entries_due:
        slice_ = equity * MODE["ALLOCATION"] / max(1, len(syms))
        cash = float(account.get("non_marginable_buying_power", 0) or 0)
        breakouts = []
        for sym in syms:
            if sym in mine or sym in held:
                continue
            lv = levels(bars.get(sym) or [], int(now.timestamp()))
            if lv and lv["px"] > lv["high"]:
                breakouts.append((lv["px"] / lv["high"] - 1, sym, lv))
        for _, sym, lv in sorted(breakouts, reverse=True):
            notional = min(slice_, cash * 0.95)
            if notional < MODE["MIN_NOTIONAL"]:
                log.append(f"{sym}: broke out but only ${cash:,.0f} cash free — skipped.")
                continue
            res = {"ok": True, "stop_ok": True, "stop": lv["px"] * (1 - MODE["CATASTROPHE_STOP"])} \
                if dry_run else _open(sym, notional, lv["px"])
            if res["ok"]:
                cash -= notional
                mine[sym] = {"notional": round(notional, 2), "entry": lv["px"], "at": now.isoformat()}
                out["buys"] += 1
                out["entries"].append({"ticker": sym, "qty": notional / lv["px"], "entry": lv["px"],
                                       "stop": res["stop"]})
                log.append(f"📥 **Bought ${notional:,.0f} of {sym}** @ ~{_fmt_px(lv['px'])} — above its "
                           f"72-hour high {_fmt_px(lv['high'])}."
                           + ("" if res.get("stop_ok") else f" ⚠️ Safety stop not placed: {res.get('stop_error')}"))
            else:
                log.append(f"⚠️ {sym} order rejected: {res.get('error')}")
        if not breakouts:
            log.append(f"No breakouts across {len(syms)} tokens.")

    if mine:
        log.append("Holding " + ", ".join(sorted(mine)) + ".")
    _save_state(st)
    return out
