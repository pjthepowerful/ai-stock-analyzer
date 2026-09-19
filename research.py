"""
Longer-term research for Paula.
===============================

WHY THIS EXISTS, AND WHY IT IS A SEPARATE BOOK
-----------------------------------------------
The rest of this app trades an intraday small-cap momentum strategy that
flattens every afternoon. That strategy refuses to hold through an earnings
print, and correctly so: at 10-20% of capital in one volatile small cap, a 30%
overnight gap is an account-ender and a stop does not execute through it.

That rule is about CONCENTRATION AND UNIVERSE, not about the calendar. A
diversified book at small position sizes holding through announcements is
ordinary practice. So this module is a second book with its own rules, not a
setting on the first one.

The effect it looks for is post-earnings announcement drift over WEEKS rather
than minutes. The multi-week form of the drift is one of the most replicated
anomalies in the literature — better documented than the intraday version the
autopilot trades — which is why it is worth a separate implementation rather
than a longer holding period bolted onto the existing engine.

WHAT IT WILL NOT DO
-------------------
It does not place orders. It ranks candidates and shows the numbers behind
each; a human clicks buy. Auto-execution on a multi-week clock is the one place
a bug compounds instead of closing itself out at 15:45, and nothing here has
been watched long enough to earn that.

THE CONSTRAINT THAT ACTUALLY BINDS
----------------------------------
Not gap risk — the Pattern Day Trader floor. Below $25,000 in equity, day
trading is unavailable until the account is back above it. Overnight positions
do not reduce equity directly, but they add overnight variance to it, so a
correlated gap across several held names can push equity under the floor and
switch off the intraday system this capital was raised for.

The user chose per-position sizing with no sleeve total. That is their call, so
this module does not enforce a total — but `pdt_exposure()` exists so the total
is never invisible, and reports the gap percentage that would breach the floor.

DATA SOURCES
------------
* SEC EDGAR (`data.sec.gov`) — free, no key, requires a contact User-Agent.
  Real filing figures: revenue, net income, debt, shares outstanding.
* Alpaca's news endpoint — free with the keys already configured, and a better
  feed than the Polygon free tier used for intraday catalyst grading.
* `earnings.py` — surprise history, already built and tested.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import requests

ET_UTC_OFFSET = None  # unused; timestamps from these APIs are already tz-aware

SEC_BASE = "https://data.sec.gov"
SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
# The SEC requires a contact address in the User-Agent and throttles or blocks
# requests without one. This is a real fair-use condition, not a formality, so
# it is configurable and the default says plainly that it should be replaced.
SEC_USER_AGENT = os.environ.get(
    "SEC_USER_AGENT", "Paula Research (set SEC_USER_AGENT to your email)")
SEC_TIMEOUT = float(os.environ.get("SEC_TIMEOUT", 15))

ALPACA_DATA_BASE = "https://data.alpaca.markets"

# Drift window. The literature puts the bulk of post-earnings drift inside the
# first 60 days; past that the surprise is priced and the name trades on
# something else.
DRIFT_MAX_DAYS = int(os.environ.get("RESEARCH_DRIFT_MAX_DAYS", 60))
DRIFT_MIN_SURPRISE = float(os.environ.get("RESEARCH_MIN_SURPRISE_PCT", 5.0))

# Suggested size for a single idea, as a fraction of equity. Per-position only:
# no sleeve total is enforced, by explicit choice.
POSITION_PCT = float(os.environ.get("RESEARCH_POSITION_PCT", 0.04))
POSITION_MAX_USD = float(os.environ.get("RESEARCH_POSITION_MAX_USD", 2000))

PDT_FLOOR = float(os.environ.get("PDT_FLOOR", 25000))


# ═══════════════════════════════════════════════════════════════════════════
#  SEC EDGAR
# ═══════════════════════════════════════════════════════════════════════════

_CIK_CACHE: dict = {}


def _sec_headers() -> dict:
    return {"User-Agent": SEC_USER_AGENT,
            "Accept-Encoding": "gzip, deflate",
            "Host": "data.sec.gov"}


def cik_for(ticker: str) -> str | None:
    """Map a ticker to its zero-padded CIK.

    The whole map is one small file, so it is fetched once and kept. A miss is
    None rather than a raise: plenty of tradable tickers (ADRs, some funds)
    simply are not SEC filers, and that is a fact about the name, not a fault.
    """
    global _CIK_CACHE
    t = str(ticker or "").upper().strip()
    if not t:
        return None
    if not _CIK_CACHE:
        try:
            r = requests.get(SEC_TICKERS_URL,
                             headers={"User-Agent": SEC_USER_AGENT},
                             timeout=SEC_TIMEOUT)
            r.raise_for_status()
            rows = r.json() or {}
            _CIK_CACHE = {
                str(v.get("ticker", "")).upper(): f"{int(v.get('cik_str', 0)):010d}"
                for v in rows.values() if v.get("ticker")
            }
        except Exception:
            _CIK_CACHE = {}
            return None
    return _CIK_CACHE.get(t)


def _series(facts: dict, keys: list[str], unit: str = "USD") -> list[dict]:
    """Pull the first populated concept from a list of synonyms.

    US-GAAP has several tags for the same line depending on filer and year —
    revenue alone is tagged at least four ways — so every accessor tries a list
    and takes the first that has data, rather than assuming one shape.
    """
    us = (facts.get("facts") or {}).get("us-gaap") or {}
    dei = (facts.get("facts") or {}).get("dei") or {}
    for k in keys:
        node = us.get(k) or dei.get(k)
        if not node:
            continue
        units = node.get("units") or {}
        rows = units.get(unit) or units.get("shares") or units.get("USD/shares")
        if not rows:
            continue
        # Annual figures only: 10-K rows, deduplicated by fiscal year, latest
        # filing wins. Mixing 10-Q into a growth rate compares a quarter to a
        # year and invents a collapse that never happened.
        annual = {}
        for row in rows:
            if row.get("form") not in ("10-K", "20-F", "40-F"):
                continue
            fy = row.get("fy")
            if fy is None or row.get("val") is None:
                continue
            prev = annual.get(fy)
            if prev is None or str(row.get("filed", "")) > str(prev.get("filed", "")):
                annual[fy] = row
        if annual:
            return [annual[k2] for k2 in sorted(annual)]
    return []


_REVENUE_TAGS = ["Revenues",
                 "RevenueFromContractWithCustomerExcludingAssessedTax",
                 "RevenueFromContractWithCustomerIncludingAssessedTax",
                 "SalesRevenueNet"]
_INCOME_TAGS = ["NetIncomeLoss", "ProfitLoss"]
_DEBT_TAGS = ["Liabilities", "LiabilitiesAndStockholdersEquity"]
_SHARE_TAGS = ["CommonStockSharesOutstanding",
               "EntityCommonStockSharesOutstanding",
               "WeightedAverageNumberOfSharesOutstandingBasic"]


def _pct_change(series: list[dict]) -> float | None:
    if len(series) < 2:
        return None
    prev, last = series[-2].get("val"), series[-1].get("val")
    try:
        if not prev:
            return None
        return (last - prev) / abs(prev) * 100.0
    except Exception:
        return None


def fundamentals(ticker: str) -> dict:
    """Multi-year figures straight from the company's own filings.

    Never raises. A name with no usable filings comes back with `available`
    False and a reason, because "we could not check" and "we checked and it
    looks bad" must not render the same way.
    """
    out = {"ticker": str(ticker).upper(), "available": False, "reason": "",
           "revenue_growth_pct": None, "net_income_growth_pct": None,
           "profitable": None, "dilution_pct": None,
           "latest_revenue": None, "fiscal_years": 0}
    cik = cik_for(ticker)
    if not cik:
        out["reason"] = "not an SEC filer (or ticker not in the EDGAR map)"
        return out
    try:
        r = requests.get(f"{SEC_BASE}/api/xbrl/companyfacts/CIK{cik}.json",
                         headers=_sec_headers(), timeout=SEC_TIMEOUT)
        r.raise_for_status()
        facts = r.json() or {}
    except Exception as e:
        out["reason"] = f"EDGAR unreachable ({type(e).__name__})"
        return out

    rev = _series(facts, _REVENUE_TAGS)
    inc = _series(facts, _INCOME_TAGS)
    sh = _series(facts, _SHARE_TAGS, unit="shares")

    if not rev and not inc:
        out["reason"] = "no annual revenue or income tagged in EDGAR"
        return out

    out["available"] = True
    out["fiscal_years"] = len(rev) or len(inc)
    out["revenue_growth_pct"] = _pct_change(rev)
    out["net_income_growth_pct"] = _pct_change(inc)
    out["latest_revenue"] = rev[-1].get("val") if rev else None
    if inc:
        out["profitable"] = (inc[-1].get("val") or 0) > 0
    # Share count rising is dilution — for a small cap financing itself by
    # issuance this is often the single most important number on the page,
    # and it is the one a headline never mentions.
    out["dilution_pct"] = _pct_change(sh)
    return out


# ═══════════════════════════════════════════════════════════════════════════
#  News
# ═══════════════════════════════════════════════════════════════════════════

def news(ticker: str, limit: int = 6, days: int = 30) -> list[dict]:
    """Recent headlines from Alpaca's news feed. [] rather than a raise."""
    if not os.environ.get("ALPACA_KEY_ID"):
        return []
    try:
        start = (datetime.now(timezone.utc) - timedelta(days=days)).strftime(
            "%Y-%m-%dT%H:%M:%SZ")
        r = requests.get(
            f"{ALPACA_DATA_BASE}/v1beta1/news",
            headers={"APCA-API-KEY-ID": os.environ.get("ALPACA_KEY_ID", ""),
                     "APCA-API-SECRET-KEY": os.environ.get("ALPACA_SECRET", "")},
            params={"symbols": str(ticker).upper(), "limit": max(1, min(limit, 50)),
                    "start": start, "sort": "desc"},
            timeout=15)
        r.raise_for_status()
        items = (r.json() or {}).get("news") or []
    except Exception:
        return []
    out = []
    for it in items[:limit]:
        out.append({
            "headline": (it.get("headline") or "").strip(),
            "source": it.get("source"),
            "url": it.get("url"),
            "at": it.get("created_at"),
        })
    return out


# ═══════════════════════════════════════════════════════════════════════════
#  Scoring
# ═══════════════════════════════════════════════════════════════════════════

def drift_leg(ticker: str) -> dict:
    """Is this name inside a post-earnings drift window, and how strong?

    Deliberately looks BACKWARDS only. A company that has not reported yet has
    no drift to trade, and pretending otherwise is how a research screen turns
    into holding through a print.
    """
    leg = {"in_window": False, "days_since": None, "surprise_pct": None,
           "score": 0.0, "note": ""}
    try:
        import earnings as _earn
        last = _earn.last_report(ticker)
        if not last or not last.get("date"):
            leg["note"] = "no reported quarter on file"
            return leg
        when = last["date"]
        days = (datetime.now(when.tzinfo) - when).days
        leg["days_since"] = days
        sur = last.get("surprise_pct")
        leg["surprise_pct"] = sur
        if days < 0:
            leg["note"] = "has not reported yet — nothing to drift on"
            return leg
        if days > DRIFT_MAX_DAYS:
            leg["note"] = f"reported {days}d ago — outside the {DRIFT_MAX_DAYS}d drift window"
            return leg
        if sur is None:
            leg["note"] = "reported, but no surprise figure published"
            return leg
        if sur < DRIFT_MIN_SURPRISE:
            leg["note"] = (f"{sur:+.0f}% surprise is inside the noise band "
                           f"(needs +{DRIFT_MIN_SURPRISE:.0f}%)")
            return leg
        leg["in_window"] = True
        # Decay across the window: a beat 5 days ago has more drift left than
        # the same beat 55 days ago.
        freshness = max(0.0, 1.0 - days / float(DRIFT_MAX_DAYS))
        leg["score"] = min(sur / 25.0, 1.0) * (0.4 + 0.6 * freshness)
        leg["note"] = f"beat by {sur:.0f}%, {days}d into the drift window"
    except Exception as e:
        leg["note"] = f"drift check failed ({type(e).__name__})"
    return leg


def fundamentals_leg(f: dict) -> dict:
    """Turn filing figures into a score and a sentence a human can argue with."""
    leg = {"score": 0.0, "notes": []}
    if not f.get("available"):
        leg["notes"].append(f.get("reason") or "no filings")
        return leg
    s = 0.0
    rg = f.get("revenue_growth_pct")
    if rg is not None:
        if rg > 20:
            s += 0.4; leg["notes"].append(f"revenue +{rg:.0f}% y/y")
        elif rg > 0:
            s += 0.2; leg["notes"].append(f"revenue +{rg:.0f}% y/y")
        else:
            s -= 0.2; leg["notes"].append(f"revenue {rg:.0f}% y/y")
    if f.get("profitable") is True:
        s += 0.3; leg["notes"].append("profitable last fiscal year")
    elif f.get("profitable") is False:
        leg["notes"].append("loss-making last fiscal year")
    d = f.get("dilution_pct")
    if d is not None:
        if d > 20:
            s -= 0.4; leg["notes"].append(f"share count +{d:.0f}% — heavy dilution")
        elif d > 5:
            s -= 0.2; leg["notes"].append(f"share count +{d:.0f}%")
        elif d < -1:
            s += 0.2; leg["notes"].append(f"share count {d:.0f}% — buying back")
    leg["score"] = max(-1.0, min(1.0, s))
    return leg


def suggest_size(price: float | None, equity: float | None) -> dict:
    """Suggested dollar size for one idea.

    Per-position only. No sleeve total is enforced — that was an explicit
    choice — so `pdt_exposure()` carries the job of keeping the accumulated
    total visible.
    """
    out = {"shares": 0, "dollars": 0.0, "note": ""}
    if not price or price <= 0 or not equity or equity <= 0:
        out["note"] = "need a live price and account equity to size"
        return out
    dollars = min(equity * POSITION_PCT, POSITION_MAX_USD)
    shares = int(dollars // price)
    if shares < 1:
        out["note"] = f"${dollars:,.0f} does not buy one share at ${price:,.2f}"
        return out
    out["shares"] = shares
    out["dollars"] = round(shares * price, 2)
    out["note"] = f"{POSITION_PCT*100:.0f}% of equity, capped at ${POSITION_MAX_USD:,.0f}"
    return out


def pdt_exposure(equity: float | None, positions: list[dict] | None) -> dict:
    """How close the held book is to switching off day trading.

    The user chose not to cap the sleeve, so this is the safeguard that
    replaces the cap: it makes the accumulated total visible and states the
    single number that matters — the across-the-board gap percentage that puts
    equity under the PDT floor.
    """
    out = {"equity": equity, "floor": PDT_FLOOR, "headroom": None,
           "exposure": 0.0, "breach_gap_pct": None, "positions": 0, "note": ""}
    if equity is None:
        out["note"] = "account equity unavailable"
        return out
    out["headroom"] = round(equity - PDT_FLOOR, 2)

    total = 0.0
    n = 0
    for p in positions or []:
        try:
            mv = p.get("market_value")
            if mv is None:
                qty, px = p.get("qty"), p.get("price") or p.get("current_price")
                mv = float(qty) * float(px) if qty and px else None
            if mv is not None:
                total += abs(float(mv))
                n += 1
        except Exception:
            continue
    out["exposure"] = round(total, 2)
    out["positions"] = n

    if equity <= PDT_FLOOR:
        out["note"] = "already below the PDT floor — day trading is unavailable"
        return out
    if total <= 0:
        out["note"] = "nothing held overnight"
        return out
    # What uniform decline across the held book erases the headroom?
    gap = (equity - PDT_FLOOR) / total * 100.0
    out["breach_gap_pct"] = round(gap, 1)
    if gap < 10:
        out["note"] = (f"a {gap:.0f}% drop across these positions puts you under "
                       f"${PDT_FLOOR:,.0f} and stops day trading")
    else:
        out["note"] = f"a {gap:.0f}% drop across these positions would reach the floor"
    return out


def evaluate(ticker: str, price: float | None = None,
             equity: float | None = None) -> dict:
    """Everything known about one name, as one row for the UI."""
    f = fundamentals(ticker)
    d = drift_leg(ticker)
    fl = fundamentals_leg(f)
    heads = news(ticker, limit=4)

    score = round(d["score"] * 0.6 + fl["score"] * 0.4, 3)
    return {
        "ticker": str(ticker).upper(),
        "score": score,
        "drift": d,
        "fundamentals": f,
        "fundamental_notes": fl["notes"],
        "news": heads,
        "size": suggest_size(price, equity),
        "buyable": bool(d["in_window"] and fl["score"] >= 0),
    }


def rank(tickers: list[str], equity: float | None = None,
         prices: dict | None = None, limit: int = 12, progress=None) -> list[dict]:
    """Score a list of names, best first. Failures drop out rather than raise.

    `progress(done, total, label)` is called as it goes. Each name costs an
    EDGAR call and a news call, so a 60-name scan is minutes, not seconds —
    long enough that silence reads as a hang.
    """
    prices = prices or {}
    rows = []
    names = list(tickers or [])
    for i, t in enumerate(names):
        try:
            rows.append(evaluate(t, price=prices.get(str(t).upper()), equity=equity))
        except Exception:
            pass
        if progress:
            try:
                progress(i + 1, len(names), str(t).upper())
            except Exception:
                pass
    rows.sort(key=lambda r: r["score"], reverse=True)
    return rows[:limit]
