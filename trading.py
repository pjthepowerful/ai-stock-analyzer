"""
Paula — Stock Analysis & Trade Signal Engine
Built for future automation. Every analysis outputs a machine-readable
trade_signal dict alongside the human-readable response.
"""

import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from groq import Groq
from dotenv import load_dotenv
import os
import json
import re
import random
import time
import requests
import warnings

warnings.filterwarnings("ignore")
load_dotenv()

# ── Stock universe ───────────────────────────────────────────────────────────

NASDAQ_100 = [
    "AAPL","MSFT","AMZN","NVDA","GOOGL","META","TSLA","AVGO","COST","NFLX",
    "AMD","ADBE","PEP","CSCO","TMUS","INTC","CMCSA","INTU","QCOM","TXN",
    "AMGN","HON","AMAT","ISRG","BKNG","SBUX","VRTX","LRCX","MU","ADI",
    "MDLZ","REGN","ADP","PANW","KLAC","SNPS","CDNS","MELI","CRWD","ASML",
    "PYPL","MAR","ORLY","CTAS","MRVL","ABNB","NXPI","PCAR","WDAY","CPRT",
]
SP500_TOP = [
    "AAPL","MSFT","AMZN","NVDA","GOOGL","META","BRK-B","LLY","TSLA","UNH",
    "JPM","XOM","V","JNJ","PG","MA","AVGO","HD","MRK","CVX",
    "COST","ABBV","PEP","KO","WMT","ADBE","MCD","CSCO","CRM","BAC",
]

# ── Mid-cap & small-cap growth ──
MIDCAP_GROWTH = [
    "AXON","DUOL","CELH","TMDX","RELY","HIMS","CAVA","ONON","BIRK","ELF",
    "WFRD","FTNT","ZS","MNDY","CFLT","GLBE","TOST","BROS","DT","ESTC",
    "FRSH","PYCR","INTA","VERX","ALKT","PAYC","LMND","ROOT","OSCR","GDRX",
]
# ── Small-cap high-potential ──
SMALLCAP = [
    "UPST","AFRM","JOBY","LUNR","ASTS","RKLB","ACHR","VERI","BBAI","SOUN",
    "BIGC","DM","OUST","IREN","CLSK","MARA","RIOT","HUT","BTBT","BITF",
    "MVST","QS","PTRA","GOEV","PSNY","BLNK","CHPT","EVGO","SPWR","ARRY",
    "DNA","RXRX","BEAM","CRSP","NTLA","EDIT","VERA","SDGR","TWST","TGTX",
]
# ── Value / Dividend ──
VALUE_DIVIDEND = [
    "O","SCHD","VZ","T","MO","PM","BTI","AGNC","NLY","STAG",
    "EPD","ET","MPLX","OKE","WMB","KMI","EMR","ITW","GPC","SWK",
    "DOW","LYB","NUE","CLF","AA","FCX","VALE","RIO","BHP",
]
# ── Sector-specific (energy, biotech, fintech, defense, space) ──
SECTOR_PICKS = [
    "FSLR","ENPH","SEDG","NEE","CEG","VST","SMR","NNE","OKLO","LEU",
    "LMT","RTX","NOC","GD","HII","KTOS","LDOS","BWXT","RCAT","PLTR",
    "MRNA","BNTX","REGN","VRTX","ARGX","ALNY","BMRN","IONS","SGEN","RARE",
]

NIFTY_50 = [
    "RELIANCE.NS","TCS.NS","HDFCBANK.NS","INFY.NS","ICICIBANK.NS",
    "HINDUNILVR.NS","BHARTIARTL.NS","SBIN.NS","BAJFINANCE.NS","ITC.NS",
    "KOTAKBANK.NS","LT.NS","HCLTECH.NS","AXISBANK.NS","ASIANPAINT.NS",
    "MARUTI.NS","SUNPHARMA.NS","TITAN.NS","WIPRO.NS","NTPC.NS",
    "TATAMOTORS.NS","TATASTEEL.NS","ADANIENT.NS",
]
TRENDING = [
    "PLTR","SMCI","ARM","IONQ","RGTI","MSTR","COIN","HOOD","SOFI","RKLB",
    "RIVN","LCID","NIO","GME","AMC","DKNG","SNOW","NET","OKTA",
    "HIMS","CAVA","DUOL","CELH","LUNR","ASTS","SOUN","JOBY","UPST","AFRM",
]

# All US tickers for recognition
ALL_US_TICKERS = set(NASDAQ_100 + SP500_TOP + MIDCAP_GROWTH + SMALLCAP + VALUE_DIVIDEND + SECTOR_PICKS + TRENDING)

COMPANIES: dict[str, str] = {
    # Mega-cap
    "apple":"AAPL","microsoft":"MSFT","amazon":"AMZN","google":"GOOGL",
    "meta":"META","facebook":"META","tesla":"TSLA","nvidia":"NVDA",
    "netflix":"NFLX","amd":"AMD","intel":"INTC","adobe":"ADBE",
    "salesforce":"CRM","oracle":"ORCL","paypal":"PYPL","shopify":"SHOP",
    "spotify":"SPOT","uber":"UBER","airbnb":"ABNB","disney":"DIS",
    "nike":"NKE","starbucks":"SBUX","mcdonalds":"MCD","walmart":"WMT",
    "costco":"COST","boeing":"BA","coca cola":"KO","pepsi":"PEP",
    "pfizer":"PFE","moderna":"MRNA","palantir":"PLTR","crowdstrike":"CRWD",
    "snowflake":"SNOW","coinbase":"COIN","robinhood":"HOOD","sofi":"SOFI",
    "gamestop":"GME",
    # Mid / small cap
    "duolingo":"DUOL","celsius":"CELH","cava":"CAVA","on running":"ONON",
    "hims":"HIMS","elf beauty":"ELF","toast":"TOST","dutch bros":"BROS",
    "datadog":"DDOG","axon":"AXON","upstart":"UPST","affirm":"AFRM",
    "joby":"JOBY","rocket lab":"RKLB","archer":"ACHR","intuitive machines":"LUNR",
    "ast spacemobile":"ASTS","soundhound":"SOUN","marathon digital":"MARA",
    "riot":"RIOT","crispr":"CRSP","beam":"BEAM","fuelcell":"FCEL",
    "chargepoint":"CHPT","quantumscape":"QS","lucid":"LCID","rivian":"RIVN",
    # Indian
    "reliance":"RELIANCE","tcs":"TCS","infosys":"INFY",
    "hdfc":"HDFCBANK","wipro":"WIPRO","tata motors":"TATAMOTORS",
    "sbi":"SBIN","itc":"ITC","icici":"ICICIBANK","kotak":"KOTAKBANK",
    "airtel":"BHARTIARTL","bharti":"BHARTIARTL",
}

_INDIA_TICKERS = {s.replace(".NS", "") for s in NIFTY_50}
_INDIA_KW = frozenset([
    "nifty","sensex","bse","nse","india","indian","rupee",
    "reliance","tcs","infosys","hdfc","icici","sbi","wipro","tata",
    "airtel","bharti","kotak","axis","maruti","titan","itc","adani","bajaj",
])
_US_KW = frozenset([
    "nasdaq","s&p","sp500","dow","nyse","dollar",
    "apple","microsoft","google","amazon","meta","tesla","nvidia","amd",
    "netflix","disney","nike","starbucks","walmart","costco","boeing",
])
_NOISE_WORDS = frozenset([
    "THE","AND","FOR","ARE","BUT","NOT","YOU","ALL","CAN","BUY","SELL",
    "WHAT","WHICH","STOCK","PRICE","MARKET","TODAY","SHOULD","WOULD","COULD",
    "ABOUT","THEIR","WILL","WITH","THIS","THAT","FROM","HAVE","BEEN","MORE",
    "ANALYZE","TELL","SHOW","GIVE","FIND","BEST","GOOD","HIGH","LOW","MONEY",
    "WHEN","WHERE","SOME","INTO","TIME","VERY","JUST","KNOW","TAKE","COME",
    "MAKE","LIKE","BACK","ONLY","OVER","SUCH","MOST","NEED","HELP","THANK",
    "HOW","MUCH","DOES","THINK","LOOK","WANT","PLEASE","COULD","REALLY",
    # Common words that look like tickers
    "NAME","LIST","PICK","THEM","ALSO","BEEN","EACH","EVEN","NEXT","THEN",
    "THAN","YEAR","LONG","DOWN","MANY","WELL","WORK","CALL","KEEP","LAST",
    "SAME","SELF","SEEM","TURN","PART","PLAN","FREE","FULL","LIVE","OPEN",
    "PLAY","SAFE","STAY","WEEK","RISK","GAIN","LOSS","HOLD","RATE","GROW",
    "MOVE","DROP","JUMP","RISE","FAST","HARD","EASY","SURE","TALK","TEXT",
    "SEND","SAVE","IDEA","HOPE","FEEL","REAL","ZERO","HALF","HUGE","TINY",
    "WIDE","DEEP","PURE","BOLD","WARM","COOL","DARK","FAIR","RARE","WILD",
    "MAIN","NICE","ABLE","AWAY","HERE","ONCE","EVER","ELSE","DONE","GONE",
    "WORD","SAID","SORT","TYPE","MODE","HOME","BOTH","NEAR","LOTS","MUST",
    "STOP","TECH","EDIT","CHAT","YOUR","THEY","WERE","YEAH","OKAY","YALL",
    "MINE","HERS","OURS","WHOM","WENT","GAVE","TOLD","LEFT","CAME","FELT",
    "KEPT","PAID","SENT","LOST","GREW","DREW","FELL","HELD","READ","LEAD",
    "MEAN","CASE","FACT","VIEW","NOTE","SIGN","FORM","LINE","SIDE","HAND",
    "HEAD","FACE","BODY","FOOD","LAND","CITY","LIFE","MIND","LOVE","HATE",
    "FEAR","CARE","PICK","TOPS","ONES","PUTS","GETS","HITS","RUNS","OWNS",
    "SAYS","GOES","PAYS","WINS","ADDS","ASKS","LETS","USES","SEES","PUTS",
    "SEEM","TEND","TEND","VARY","GIVE","GAVE","THESE","THOSE","EVERY",
    "OTHER","AFTER","FIRST","STILL","MIGHT","RIGHT","GREAT","NEVER",
    "THREE","WORLD","WHILE","BEING","GOING","USING","DOING","UNDER",
    "MAJOR","SMALL","LARGE","YOUNG","EARLY","ABOVE","BELOW","LOWER",
    "UPPER","INNER","OUTER","WHOLE","TOTAL","CLEAR","BRIEF","QUICK",
    "SEVEN","EIGHT","MAYBE","SINCE","AMONG","ALONG","OFTEN","LATER",
    "UNTIL","SHALL","GONNA","ABOUT","AGAIN",
])


# ── Helpers ──────────────────────────────────────────────────────────────────

def _detect_market(text: str) -> str:
    low = text.lower()
    india = sum(1 for k in _INDIA_KW if k in low)
    us = sum(1 for k in _US_KW if k in low)
    return "India" if india > us else "US"


def _find_ticker(text: str) -> tuple[str | None, str]:
    low = text.lower()
    # 1) Known company names
    for name, tick in COMPANIES.items():
        if name in low:
            return tick, "India" if tick in _INDIA_TICKERS else "US"
    # 2) Known tickers in our universe
    us_set = ALL_US_TICKERS
    for word in text.upper().split():
        clean = re.sub(r"[^A-Z]", "", word)
        if clean and 2 <= len(clean) <= 5 and clean not in _NOISE_WORDS:
            if clean in _INDIA_TICKERS:
                return clean, "India"
            if clean in us_set:
                return clean, "US"
    # 3) Polygon search — only if the message looks like a specific stock query
    stock_intent = any(w in low for w in [
        "analyze", "analysis", "price", "buy", "sell", "chart", "quote",
        "stock", "ticker", "how is", "how's", "what about", "look at",
        "check out", "thoughts on", "opinion on", "review",
    ])
    if stock_intent:
        words = [w for w in text.split() if len(w) > 3 and w.upper() not in _NOISE_WORDS]
        if words:
            query = " ".join(words[:3])
            found = polygon_search_ticker(query)
            if found:
                return found, "US"
    return None, _detect_market(text)


def _ensure_suffix(ticker: str, market: str) -> str:
    if market == "India" and "." not in ticker:
        return f"{ticker}.NS"
    return ticker


def _safe(val, fallback=None):
    """Return val if it's a real number, else fallback."""
    if val is None:
        return fallback
    try:
        v = float(val)
        return fallback if np.isnan(v) or np.isinf(v) else v
    except (TypeError, ValueError):
        return fallback


# ═══════════════════════════════════════════════════════════════════════════════
#  POLYGON.IO API — scans the ENTIRE market, not just a hardcoded list
# ═══════════════════════════════════════════════════════════════════════════════

def _polygon_key() -> str | None:
    """Get Polygon API key from secrets or env."""
    try:
        return st.secrets.get("POLYGON_API_KEY") or os.environ.get("POLYGON_API_KEY") or "wzJ5v31KgEA_rwFQxViseXokW5TLoSrG"
    except Exception:
        return os.environ.get("POLYGON_API_KEY") or "wzJ5v31KgEA_rwFQxViseXokW5TLoSrG"

POLYGON_BASE = "https://api.polygon.io"


@st.cache_data(ttl=180)
def polygon_gainers(limit: int = 20) -> list[dict] | None:
    """Top gainers across ALL US stocks — one API call."""
    key = _polygon_key()
    if not key:
        return None
    try:
        r = requests.get(
            f"{POLYGON_BASE}/v2/snapshot/locale/us/markets/stocks/gainers",
            params={"apiKey": key, "include_otc": "false"},
            timeout=10,
        )
        if r.status_code != 200:
            return None
        data = r.json()
        results = []
        for t in data.get("tickers", [])[:limit]:
            ticker = t.get("ticker", "")
            day = t.get("day", {})
            prev = t.get("prevDay", {})
            snap = t.get("todaysChangePerc", 0)
            price = day.get("c") or t.get("lastTrade", {}).get("p", 0)
            if price and price > 1 and snap > 0:  # Filter pennystocks
                results.append({
                    "Ticker": ticker,
                    "Price": round(price, 2),
                    "Chg%": round(snap, 2),
                    "Volume": day.get("v", 0),
                })
        return results if results else None
    except Exception:
        return None


@st.cache_data(ttl=180)
def polygon_losers(limit: int = 20) -> list[dict] | None:
    """Top losers across ALL US stocks — one API call."""
    key = _polygon_key()
    if not key:
        return None
    try:
        r = requests.get(
            f"{POLYGON_BASE}/v2/snapshot/locale/us/markets/stocks/losers",
            params={"apiKey": key, "include_otc": "false"},
            timeout=10,
        )
        if r.status_code != 200:
            return None
        data = r.json()
        results = []
        for t in data.get("tickers", [])[:limit]:
            ticker = t.get("ticker", "")
            day = t.get("day", {})
            snap = t.get("todaysChangePerc", 0)
            price = day.get("c") or t.get("lastTrade", {}).get("p", 0)
            if price and price > 1 and snap < 0:
                results.append({
                    "Ticker": ticker,
                    "Price": round(price, 2),
                    "Chg%": round(snap, 2),
                    "Volume": day.get("v", 0),
                })
        return results if results else None
    except Exception:
        return None


@st.cache_data(ttl=180)
def polygon_all_snapshots() -> list[dict] | None:
    """
    Get snapshot of ALL tickers — finds the real movers, not just a curated list.
    Falls back to grouped daily bars if snapshots aren't available on plan.
    """
    key = _polygon_key()
    if not key:
        return None
    try:
        r = requests.get(
            f"{POLYGON_BASE}/v2/snapshot/locale/us/markets/stocks/tickers",
            params={"apiKey": key, "include_otc": "false"},
            timeout=15,
        )
        if r.status_code != 200:
            return None
        data = r.json()
        results = []
        for t in data.get("tickers", []):
            ticker = t.get("ticker", "")
            day = t.get("day", {})
            prev = t.get("prevDay", {})
            chg_pct = t.get("todaysChangePerc", 0)
            price = day.get("c") or t.get("lastTrade", {}).get("p", 0)
            vol = day.get("v", 0)
            # Filter: real stocks only (price > $1, has volume)
            if price and price > 1 and vol and vol > 50000:
                results.append({
                    "Ticker": ticker,
                    "Price": round(price, 2),
                    "Chg%": round(chg_pct, 2),
                    "Volume": vol,
                })
        return results if results else None
    except Exception:
        return None


@st.cache_data(ttl=300)
def polygon_search_ticker(query: str) -> str | None:
    """Search for a ticker by company name — finds ANY stock, not just our list."""
    key = _polygon_key()
    if not key:
        return None
    try:
        r = requests.get(
            f"{POLYGON_BASE}/v3/reference/tickers",
            params={
                "search": query, "active": "true", "market": "stocks",
                "limit": 5, "apiKey": key,
            },
            timeout=8,
        )
        if r.status_code != 200:
            return None
        data = r.json()
        results = data.get("results", [])
        if results:
            # Prefer exact match, then first result
            for res in results:
                if res.get("ticker", "").upper() == query.upper():
                    return res["ticker"]
            return results[0].get("ticker")
        return None
    except Exception:
        return None



# ═══════════════════════════════════════════════════════════════════════════════
#  ALPACA PAPER TRADING ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

ALPACA_BASE = "https://paper-api.alpaca.markets"

def _alpaca_headers() -> dict:
    key_id = st.secrets.get("ALPACA_KEY_ID") or os.environ.get("ALPACA_KEY_ID") or "PKZ433ZF6BTR5OXHRNDJ2HVTAI"
    secret = st.secrets.get("ALPACA_SECRET") or os.environ.get("ALPACA_SECRET") or "5kV7Q11v3ksPmMmhdxLTgEYQgAWMiuKfVqSCaFvQwfsv"
    return {
        "APCA-API-KEY-ID": key_id,
        "APCA-API-SECRET-KEY": secret,
        "Content-Type": "application/json",
    }


def alpaca_account() -> dict | None:
    """Get account info: buying power, equity, P&L."""
    try:
        r = requests.get(f"{ALPACA_BASE}/v2/account", headers=_alpaca_headers(), timeout=10)
        if r.status_code != 200:
            return None
        a = r.json()
        equity = float(a.get("equity", 0))
        cash = float(a.get("cash", 0))
        buying_power = float(a.get("buying_power", 0))
        last_equity = float(a.get("last_equity", equity))
        pnl = equity - last_equity
        pnl_pct = (pnl / last_equity * 100) if last_equity > 0 else 0
        return {
            "equity": round(equity, 2),
            "cash": round(cash, 2),
            "buying_power": round(buying_power, 2),
            "daily_pnl": round(pnl, 2),
            "daily_pnl_pct": round(pnl_pct, 2),
            "portfolio_value": round(float(a.get("portfolio_value", equity)), 2),
            "long_market_value": round(float(a.get("long_market_value", 0)), 2),
            "short_market_value": round(float(a.get("short_market_value", 0)), 2),
            "status": a.get("status", "UNKNOWN"),
        }
    except Exception:
        return None


def alpaca_positions() -> list[dict]:
    """Get all open positions."""
    try:
        r = requests.get(f"{ALPACA_BASE}/v2/positions", headers=_alpaca_headers(), timeout=10)
        if r.status_code != 200:
            return []
        positions = []
        for p in r.json():
            positions.append({
                "ticker": p.get("symbol", ""),
                "qty": float(p.get("qty", 0)),
                "side": p.get("side", "long"),
                "avg_entry": round(float(p.get("avg_entry_price", 0)), 2),
                "current_price": round(float(p.get("current_price", 0)), 2),
                "market_value": round(float(p.get("market_value", 0)), 2),
                "unrealized_pnl": round(float(p.get("unrealized_pl", 0)), 2),
                "unrealized_pnl_pct": round(float(p.get("unrealized_plpc", 0)) * 100, 2),
                "today_pnl": round(float(p.get("unrealized_intraday_pl", 0)), 2),
            })
        return positions
    except Exception:
        return []


def alpaca_buy(ticker: str, qty: int = None, notional: float = None,
               stop_loss: float = None, take_profit: float = None,
               limit_price: float = None) -> dict:
    """
    Place a buy order. Supports:
    - Market order (qty or notional)
    - Limit order (limit_price)
    - Bracket order (stop_loss and/or take_profit)
    """
    # Validate inputs
    if qty is not None and qty <= 0:
        return {"ok": False, "error": f"Can't buy {qty} shares — need at least 1"}
    if notional is not None and notional <= 0:
        return {"ok": False, "error": f"Can't buy ${notional} — need a positive amount"}

    order = {
        "symbol": ticker.upper(),
        "side": "buy",
        "time_in_force": "day",
    }

    if notional and not qty:
        order["notional"] = round(notional, 2)
    else:
        order["qty"] = str(qty or 1)

    # Bracket order: entry + stop-loss + take-profit
    if stop_loss and take_profit:
        order["type"] = "limit" if limit_price else "market"
        order["order_class"] = "bracket"
        order["stop_loss"] = {"stop_price": str(round(stop_loss, 2))}
        order["take_profit"] = {"limit_price": str(round(take_profit, 2))}
        if limit_price:
            order["limit_price"] = str(round(limit_price, 2))
    elif stop_loss:
        order["type"] = "limit" if limit_price else "market"
        order["order_class"] = "oto"
        order["stop_loss"] = {"stop_price": str(round(stop_loss, 2))}
        if limit_price:
            order["limit_price"] = str(round(limit_price, 2))
    elif limit_price:
        order["type"] = "limit"
        order["limit_price"] = str(round(limit_price, 2))
    else:
        order["type"] = "market"

    try:
        r = requests.post(f"{ALPACA_BASE}/v2/orders", headers=_alpaca_headers(),
                          json=order, timeout=10)
        data = r.json()
        if r.status_code in (200, 201):
            return {
                "ok": True,
                "order_id": data.get("id"),
                "symbol": data.get("symbol"),
                "qty": data.get("qty") or data.get("notional"),
                "side": "buy",
                "type": data.get("type"),
                "status": data.get("status"),
                "order_class": data.get("order_class", "simple"),
            }
        else:
            return {"ok": False, "error": data.get("message", "Order rejected")}
    except Exception as e:
        return {"ok": False, "error": str(e)[:100]}


def alpaca_sell(ticker: str, qty: int = None, sell_all: bool = False) -> dict:
    """Sell shares or close entire position."""
    if qty is not None and qty <= 0 and not sell_all:
        return {"ok": False, "error": f"Can't sell {qty} shares — need at least 1"}
    if sell_all:
        try:
            r = requests.delete(f"{ALPACA_BASE}/v2/positions/{ticker.upper()}",
                                headers=_alpaca_headers(), timeout=10)
            data = r.json()
            if r.status_code in (200, 201, 207):
                return {"ok": True, "symbol": ticker.upper(), "action": "closed_position",
                        "qty": data.get("qty", "all"), "status": data.get("status")}
            else:
                return {"ok": False, "error": data.get("message", "Failed to close")}
        except Exception as e:
            return {"ok": False, "error": str(e)[:100]}

    order = {
        "symbol": ticker.upper(),
        "qty": str(qty or 1),
        "side": "sell",
        "type": "market",
        "time_in_force": "day",
    }
    try:
        r = requests.post(f"{ALPACA_BASE}/v2/orders", headers=_alpaca_headers(),
                          json=order, timeout=10)
        data = r.json()
        if r.status_code in (200, 201):
            return {"ok": True, "order_id": data.get("id"), "symbol": data.get("symbol"),
                    "qty": data.get("qty"), "side": "sell", "status": data.get("status")}
        else:
            return {"ok": False, "error": data.get("message", "Order rejected")}
    except Exception as e:
        return {"ok": False, "error": str(e)[:100]}


def alpaca_close_all() -> dict:
    """Close ALL positions — panic button."""
    try:
        r = requests.delete(f"{ALPACA_BASE}/v2/positions",
                            headers=_alpaca_headers(), timeout=10)
        if r.status_code in (200, 207):
            return {"ok": True, "message": "All positions closed"}
        return {"ok": False, "error": "Failed to close all positions"}
    except Exception as e:
        return {"ok": False, "error": str(e)[:100]}


def alpaca_orders(status: str = "open", limit: int = 10) -> list[dict]:
    """Get recent orders."""
    try:
        r = requests.get(f"{ALPACA_BASE}/v2/orders",
                         headers=_alpaca_headers(),
                         params={"status": status, "limit": limit, "direction": "desc"},
                         timeout=10)
        if r.status_code != 200:
            return []
        orders = []
        for o in r.json():
            orders.append({
                "id": o.get("id", "")[:8],
                "symbol": o.get("symbol", ""),
                "side": o.get("side", ""),
                "qty": o.get("qty") or o.get("notional", ""),
                "type": o.get("type", ""),
                "status": o.get("status", ""),
                "filled_avg": o.get("filled_avg_price", "—"),
                "submitted": o.get("submitted_at", "")[:16],
            })
        return orders
    except Exception:
        return []


def alpaca_portfolio_history(period: str = "1M") -> dict | None:
    """Fetch portfolio equity history from Alpaca."""
    try:
        params = {"period": period, "timeframe": "1D"}
        r = requests.get(f"{ALPACA_BASE}/v2/account/portfolio/history",
                         headers=_alpaca_headers(), params=params, timeout=10)
        if r.status_code != 200:
            return None
        data = r.json()
        timestamps = data.get("timestamp", [])
        equity = data.get("equity", [])
        profit_loss = data.get("profit_loss", [])
        profit_loss_pct = data.get("profit_loss_pct", [])
        if not timestamps or not equity:
            return None
        return {
            "timestamps": timestamps,
            "equity": equity,
            "profit_loss": profit_loss or [0] * len(timestamps),
            "profit_loss_pct": profit_loss_pct or [0] * len(timestamps),
        }
    except Exception:
        return None


def build_portfolio_chart(history: dict) -> go.Figure | None:
    """Build a portfolio equity chart."""
    if not history or not history.get("timestamps"):
        return None
    try:
        dates = pd.to_datetime(history["timestamps"], unit="s")
        equity = history["equity"]
        pnl = history["profit_loss"]

        fig = go.Figure()

        # Equity line
        fig.add_trace(go.Scatter(
            x=dates, y=equity, mode="lines",
            name="Equity",
            line=dict(color="#00d4aa", width=2.5),
            fill="tozeroy",
            fillcolor="rgba(0, 212, 170, 0.1)",
        ))

        # Color the P&L bars green/red
        colors = ["#00d4aa" if p >= 0 else "#ff4444" for p in pnl]
        fig.add_trace(go.Bar(
            x=dates, y=pnl, name="Daily P&L",
            marker_color=colors, opacity=0.4,
            yaxis="y2",
        ))

        # Starting equity reference line
        if equity:
            start_eq = equity[0]
            fig.add_hline(y=start_eq, line_dash="dash", line_color="gray",
                          opacity=0.5, annotation_text=f"Start ${start_eq:,.0f}")

        fig.update_layout(
            template="plotly_dark",
            paper_bgcolor="#0e1117",
            plot_bgcolor="#0e1117",
            title=dict(text="Portfolio Performance", font=dict(size=16, color="#fafafa")),
            xaxis=dict(showgrid=False),
            yaxis=dict(title="Equity ($)", showgrid=True, gridcolor="#1e2530", side="left"),
            yaxis2=dict(title="Daily P&L ($)", overlaying="y", side="right", showgrid=False),
            legend=dict(orientation="h", y=1.12, x=0.5, xanchor="center"),
            height=400,
            margin=dict(l=10, r=10, t=50, b=10),
            showlegend=True,
        )
        return fig
    except Exception:
        return None


def alpaca_smart_buy(ticker: str, trade_signal: dict, risk_pct: float = 0.02) -> dict:
    """
    Smart buy using Paula's trade signal. Automatically calculates:
    - Position size based on risk % of portfolio
    - Sets bracket order with stop-loss and take-profit from signal
    """
    account = alpaca_account()
    if not account:
        return {"ok": False, "error": "Could not fetch account info"}

    trade = trade_signal.get("trade", {})
    entry = trade.get("entry", 0)
    stop = trade.get("stop_loss", 0)
    target = trade.get("target_1", 0)

    if not entry or not stop or entry <= stop:
        return {"ok": False, "error": "Invalid trade signal — no entry/stop calculated"}

    # Position sizing: risk X% of equity per trade
    equity = account["equity"]
    risk_per_share = entry - stop
    max_risk_dollars = equity * risk_pct
    qty = max(1, int(max_risk_dollars / risk_per_share))

    # Don't exceed 20% of buying power on one trade
    max_qty_by_bp = int(account["buying_power"] * 0.20 / entry)
    qty = min(qty, max_qty_by_bp)

    if qty < 1:
        return {"ok": False, "error": f"Position too small — need at least ${ entry:.2f} buying power"}

    cost = qty * entry
    result = alpaca_buy(
        ticker=ticker,
        qty=qty,
        stop_loss=stop,
        take_profit=target,
    )

    if result["ok"]:
        result["qty_calculated"] = qty
        result["cost_estimate"] = round(cost, 2)
        result["risk_per_share"] = round(risk_per_share, 2)
        result["total_risk"] = round(qty * risk_per_share, 2)
        result["stop_loss"] = stop
        result["take_profit"] = target

    return result


# ═══════════════════════════════════════════════════════════════════════════════
#  TECHNICAL ANALYSIS ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

def _compute_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def _compute_stoch_rsi(rsi: pd.Series, period: int = 14, smooth_k: int = 3, smooth_d: int = 3):
    rsi_min = rsi.rolling(period).min()
    rsi_max = rsi.rolling(period).max()
    stoch = (rsi - rsi_min) / (rsi_max - rsi_min) * 100
    k = stoch.rolling(smooth_k).mean()
    d = k.rolling(smooth_d).mean()
    return k, d


def _compute_adx(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    plus_dm = high.diff()
    minus_dm = -low.diff()
    plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0.0)
    minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0.0)
    tr = pd.concat([high - low, (high - close.shift(1)).abs(), (low - close.shift(1)).abs()], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1 / period, min_periods=period).mean()
    plus_di = 100 * (plus_dm.ewm(alpha=1 / period, min_periods=period).mean() / atr)
    minus_di = 100 * (minus_dm.ewm(alpha=1 / period, min_periods=period).mean() / atr)
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di)
    return dx.ewm(alpha=1 / period, min_periods=period).mean()


def _compute_atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    tr = pd.concat([high - low, (high - close.shift(1)).abs(), (low - close.shift(1)).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / period, min_periods=period).mean()


def _find_support_resistance(close: pd.Series, window: int = 20, num_levels: int = 3) -> dict:
    if len(close) < window * 2:
        return {"support": [], "resistance": []}
    highs, lows = [], []
    arr = close.values
    for i in range(window, len(arr) - window):
        if arr[i] == max(arr[i - window : i + window + 1]):
            highs.append(float(arr[i]))
        if arr[i] == min(arr[i - window : i + window + 1]):
            lows.append(float(arr[i]))
    price = float(close.iloc[-1])

    def cluster(levels):
        if not levels:
            return []
        levels = sorted(levels)
        clusters, current = [], [levels[0]]
        for lv in levels[1:]:
            if (lv - current[0]) / current[0] < 0.015:
                current.append(lv)
            else:
                clusters.append(round(np.mean(current), 2))
                current = [lv]
        clusters.append(round(np.mean(current), 2))
        return clusters

    all_levels = cluster(highs + lows)
    support = sorted([l for l in all_levels if l < price], reverse=True)[:num_levels]
    resistance = sorted([l for l in all_levels if l > price])[:num_levels]
    return {"support": support, "resistance": resistance}


def _detect_trend_regime(close: pd.Series, adx: pd.Series) -> dict:
    adx_val = _safe(adx.iloc[-1], 0)
    sma50 = close.rolling(50).mean().iloc[-1] if len(close) >= 50 else None
    sma200 = close.rolling(200).mean().iloc[-1] if len(close) >= 200 else None
    sma20 = close.rolling(20).mean()
    slope = (sma20.iloc[-1] - sma20.iloc[-5]) / sma20.iloc[-5] * 100 if len(sma20.dropna()) >= 5 else 0

    if adx_val >= 25:
        regime = "strong_uptrend" if slope > 0.5 else ("strong_downtrend" if slope < -0.5 else "trending")
    elif adx_val >= 15:
        regime = "weak_trend"
    else:
        regime = "ranging"

    cross = None
    if sma50 is not None and sma200 is not None:
        cross = "golden_cross" if sma50 > sma200 else "death_cross"

    return {"regime": regime, "adx": round(adx_val, 1), "slope_20d": round(slope, 2), "ma_cross": cross}


def compute_technicals(hist: pd.DataFrame) -> dict:
    if hist is None or hist.empty or len(hist) < 20:
        return {}
    c, h, l, v = hist["Close"], hist["High"], hist["Low"], hist["Volume"]
    price = float(c.iloc[-1])
    tech: dict = {"price": price}

    # Moving Averages
    for p in [9, 20, 50, 200]:
        if len(c) >= p:
            tech[f"sma_{p}"] = round(float(c.rolling(p).mean().iloc[-1]), 2)
    for p in [9, 21]:
        if len(c) >= p:
            tech[f"ema_{p}"] = round(float(c.ewm(span=p, adjust=False).mean().iloc[-1]), 2)

    # RSI + Stochastic RSI
    rsi = _compute_rsi(c, 14)
    tech["rsi"] = _safe(round(float(rsi.iloc[-1]), 1))
    if len(rsi.dropna()) >= 14:
        k, d = _compute_stoch_rsi(rsi)
        tech["stoch_rsi_k"] = _safe(round(float(k.iloc[-1]), 1))
        tech["stoch_rsi_d"] = _safe(round(float(d.iloc[-1]), 1))

    # MACD
    ema12 = c.ewm(span=12, adjust=False).mean()
    ema26 = c.ewm(span=26, adjust=False).mean()
    macd_line = ema12 - ema26
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    macd_hist = macd_line - signal_line
    tech["macd"] = _safe(round(float(macd_line.iloc[-1]), 4))
    tech["macd_signal"] = _safe(round(float(signal_line.iloc[-1]), 4))
    tech["macd_hist"] = _safe(round(float(macd_hist.iloc[-1]), 4))
    if len(macd_hist.dropna()) >= 3:
        tech["macd_accel"] = "expanding" if abs(macd_hist.iloc[-1]) > abs(macd_hist.iloc[-2]) else "contracting"

    # Bollinger Bands
    sma20 = c.rolling(20).mean()
    std20 = c.rolling(20).std()
    bb_upper = sma20 + 2 * std20
    bb_lower = sma20 - 2 * std20
    tech["bb_upper"] = round(float(bb_upper.iloc[-1]), 2)
    tech["bb_lower"] = round(float(bb_lower.iloc[-1]), 2)
    bb_width = (bb_upper - bb_lower) / sma20
    tech["bb_width"] = _safe(round(float(bb_width.iloc[-1]), 4))
    pct_b = (c - bb_lower) / (bb_upper - bb_lower)
    tech["bb_pct_b"] = _safe(round(float(pct_b.iloc[-1]), 3))

    # ATR
    atr = _compute_atr(h, l, c, 14)
    tech["atr"] = _safe(round(float(atr.iloc[-1]), 2))
    tech["atr_pct"] = _safe(round(float(atr.iloc[-1]) / price * 100, 2))

    # ADX
    adx = _compute_adx(h, l, c, 14)
    tech["adx"] = _safe(round(float(adx.iloc[-1]), 1))

    # Volume
    if v is not None and len(v) >= 20:
        avg_vol = v.rolling(20).mean().iloc[-1]
        tech["vol_ratio"] = _safe(round(float(v.iloc[-1] / avg_vol), 2)) if avg_vol > 0 else 1.0
        tech["avg_volume"] = int(avg_vol) if not np.isnan(avg_vol) else None
        obv = (np.sign(c.diff()) * v).cumsum()
        if len(obv) >= 10:
            tech["obv_trend"] = "rising" if obv.iloc[-1] - obv.iloc[-10] > 0 else "falling"

    # Momentum
    for days, label in [(5, "5d"), (20, "20d"), (60, "60d")]:
        if len(c) >= days:
            tech[f"mom_{label}"] = round((price / float(c.iloc[-days]) - 1) * 100, 2)

    # Support / Resistance
    sr = _find_support_resistance(c, window=15, num_levels=3)
    tech["support_levels"] = sr["support"]
    tech["resistance_levels"] = sr["resistance"]

    # Trend regime
    regime = _detect_trend_regime(c, adx)
    tech["trend_regime"] = regime["regime"]
    tech["trend_slope"] = regime["slope_20d"]
    tech["ma_cross"] = regime["ma_cross"]

    return tech


# ═══════════════════════════════════════════════════════════════════════════════
#  TRADE SIGNAL GENERATOR — the core profit engine
#
#  Confluence categories (each votes bullish/bearish with a cap):
#    1. Trend       (regime + MAs)              max ±30
#    2. Momentum    (RSI, StochRSI, MACD)       max ±30
#    3. Mean-revert (Bollinger, S/R proximity)  max ±15
#    4. Volume      (ratio, OBV)                max ±10
#    5. Fundamentals (valuation, analysts)      max ±15
#    6. News        (headline sentiment)        max ±10
#
#  Action fires only when enough categories agree (confluence).
#  Risk management: ATR-based entry / stop / targets with R:R.
# ═══════════════════════════════════════════════════════════════════════════════

def generate_trade_signal(data: dict) -> dict:
    """
    Strategy: Buy pullbacks in confirmed uptrends.
    
    This is ONE proven strategy instead of mixing 5 conflicting ones.
    
    Entry rules (ALL must be true for BUY):
    1. Price above 200 SMA (long-term uptrend)
    2. Price above 50 SMA (medium-term uptrend)
    3. Price pulled back toward 20 SMA (the dip to buy)
    4. RSI 30-60 (pulled back but not collapsing)
    5. ADX > 18 (market is trending, not choppy)
    
    Score = quality of the setup (how many bonus factors align)
    """
    tech = data.get("technicals", {})
    price = data.get("price", 0)
    if not price or not tech:
        return {"action": "NO_DATA", "confidence": 0, "score": 0,
                "confluence": {"bullish": 0, "bearish": 0},
                "category_scores": {}, "signals": [], "warnings": [],
                "trade": {"entry": 0, "stop_loss": 0, "target_1": 0,
                          "target_2": 0, "risk_reward": 0, "risk_pct": 0, "atr": 0}}

    signals = []
    warnings = []
    score = 50  # Start neutral

    # ── Core indicators ──
    sma20 = _safe(tech.get("sma_20"))
    sma50 = _safe(tech.get("sma_50"))
    sma200 = _safe(tech.get("sma_200"))
    rsi = _safe(tech.get("rsi"), 50)
    adx = _safe(tech.get("adx"), 15)
    atr = _safe(tech.get("atr"), price * 0.02)
    macd_h = _safe(tech.get("macd_hist"), 0)
    macd_accel = tech.get("macd_accel", "")
    vol_ratio = _safe(tech.get("vol_ratio"), 1.0)
    obv_trend = tech.get("obv_trend", "flat")
    bb_pct_b = _safe(tech.get("bb_pct_b"), 0.5)
    regime = tech.get("trend_regime", "ranging")
    slope = _safe(tech.get("trend_slope"), 0)
    supports = tech.get("support_levels", [])
    resistances = tech.get("resistance_levels", [])
    stoch_k = _safe(tech.get("stoch_rsi_k"), 50)
    stoch_d = _safe(tech.get("stoch_rsi_d"), 50)

    # ═══ STEP 1: TREND FILTER (pass/fail gates) ═══
    above_200 = sma200 is not None and price > sma200
    above_50 = sma50 is not None and price > sma50
    above_20 = sma20 is not None and price > sma20
    
    # MA stacking: 20 > 50 > 200 is ideal
    mas_stacked = (sma20 is not None and sma50 is not None and sma200 is not None 
                   and sma20 > sma50 > sma200)
    
    trending = adx > 18
    
    # ═══ STEP 2: PULLBACK DETECTION ═══
    # How far has price pulled back from 20 SMA? 
    pullback_to_20 = False
    pullback_quality = 0
    if sma20:
        dist_from_20 = (price - sma20) / sma20 * 100
        # Ideal: price is within -3% to +1% of 20 SMA (just touching it or slightly below)
        if -4 <= dist_from_20 <= 1.5:
            pullback_to_20 = True
            pullback_quality = 10 - abs(dist_from_20) * 2  # closer to 20 SMA = better
    
    # Also check if near 50 SMA (deeper pullback in strong trend)
    pullback_to_50 = False
    if sma50 and sma200 and price > sma200:
        dist_from_50 = (price - sma50) / sma50 * 100
        if -3 <= dist_from_50 <= 1:
            pullback_to_50 = True
    
    # ═══ STEP 3: SCORING ═══
    
    # -- Trend health (0-25 points) --
    if above_200:
        score += 8
        signals.append("Above 200 SMA — long-term uptrend ✓")
    else:
        score -= 15
        warnings.append("Below 200 SMA — no uptrend")
    
    if above_50:
        score += 6
        signals.append("Above 50 SMA — medium-term uptrend ✓")
    else:
        score -= 10
        warnings.append("Below 50 SMA")
    
    if mas_stacked:
        score += 6
        signals.append("MAs stacked bullish (20 > 50 > 200)")
    
    if regime == "strong_uptrend":
        score += 5
        signals.append(f"Strong uptrend (ADX {adx:.0f})")
    elif regime == "strong_downtrend":
        score -= 12
        warnings.append(f"Strong downtrend (ADX {adx:.0f})")
    
    if tech.get("ma_cross") == "golden_cross":
        score += 3
        signals.append("Golden cross")
    elif tech.get("ma_cross") == "death_cross":
        score -= 5
        warnings.append("Death cross")
    
    # -- Pullback quality (0-15 points) --
    if pullback_to_20 and above_50:
        score += int(max(0, pullback_quality))
        signals.append(f"Pulled back to 20 SMA — buy-the-dip setup")
    if pullback_to_50 and above_200:
        score += 6
        signals.append(f"Deeper pullback to 50 SMA in uptrend — high value entry")
    
    # -- RSI sweet spot (0-10 points) --
    if 35 <= rsi <= 50:
        score += 8
        signals.append(f"RSI in ideal pullback zone ({rsi:.0f})")
    elif 30 <= rsi <= 35:
        score += 5
        signals.append(f"RSI oversold bounce zone ({rsi:.0f})")
    elif 50 < rsi <= 60:
        score += 3  # okay, not ideal
    elif rsi > 75:
        score -= 8
        warnings.append(f"RSI overbought ({rsi:.0f}) — don't chase")
    elif rsi < 25:
        score -= 5
        warnings.append(f"RSI crashing ({rsi:.0f}) — could keep falling")
    
    # -- Momentum confirmation (0-10 points) --
    if macd_h > 0 and macd_accel == "expanding":
        score += 7
        signals.append("MACD bullish & accelerating")
    elif macd_h > 0:
        score += 4
        signals.append("MACD bullish")
    elif macd_h < 0 and macd_accel == "expanding":
        score -= 5
        warnings.append("MACD bearish & accelerating")
    elif macd_h < 0:
        # If MACD is negative but about to cross (histogram getting less negative), that's ok for a pullback
        score -= 1
    
    if stoch_k < 25 and stoch_k > stoch_d:
        score += 5
        signals.append(f"StochRSI bullish cross from oversold")
    elif stoch_k > 80 and stoch_k < stoch_d:
        score -= 4
        warnings.append(f"StochRSI bearish")
    
    # -- Volume (0-6 points) --
    # On a pullback, LOWER volume is good (no panic selling)
    if pullback_to_20 or pullback_to_50:
        if vol_ratio < 0.8:
            score += 4
            signals.append(f"Low volume on pullback ({vol_ratio:.1f}x) — healthy dip")
        elif vol_ratio > 2.0:
            score -= 3
            warnings.append(f"High volume on pullback ({vol_ratio:.1f}x) — possible distribution")
    else:
        if vol_ratio > 1.5:
            score += 3
            signals.append(f"Above-average volume ({vol_ratio:.1f}x)")
        elif vol_ratio < 0.4:
            score -= 2
            warnings.append(f"Very thin volume")
    
    if obv_trend == "rising":
        score += 3
        signals.append("OBV rising — accumulation")
    elif obv_trend == "falling":
        score -= 3
        warnings.append("OBV falling — distribution")
    
    # -- Bollinger Band context (0-5 points) --
    if bb_pct_b is not None:
        if bb_pct_b <= 0.15 and above_50:
            score += 5
            signals.append(f"At lower Bollinger in uptrend — bounce likely")
        elif bb_pct_b >= 0.95:
            score -= 4
            warnings.append(f"At upper Bollinger — extended")
    
    # -- Support proximity (0-4 points) --
    if supports:
        dist = (price - supports[0]) / price * 100
        if dist < 2 and above_50:
            score += 4
            signals.append(f"Near support ${supports[0]:.2f}")
    
    # -- Fundamentals (light touch, only if available) --
    pe = _safe(data.get("pe_ratio"))
    fwd_pe = _safe(data.get("forward_pe"))
    if pe and fwd_pe and fwd_pe < pe * 0.82:
        score += 3
        signals.append(f"Earnings growth (Fwd P/E {fwd_pe:.1f} vs {pe:.1f})")
    
    rec = data.get("recommendation")
    if rec in ("strongBuy", "strong_buy"):
        score += 3
    elif rec in ("sell", "strongSell", "strong_sell"):
        score -= 3
    
    target_price = _safe(data.get("target_price"))
    if target_price and price:
        upside = (target_price - price) / price * 100
        if upside > 20:
            score += 2
        elif upside < -10:
            score -= 2
    
    # -- Relative strength vs SPY (0-10 points) --
    rs = data.get("relative_strength", {})
    rs_score_val = rs.get("rs_score", 0)
    if rs_score_val > 5:
        score += 8
        signals.append(f"Strong relative strength vs SPY (+{rs_score_val:.1f}%)")
    elif rs_score_val > 2:
        score += 5
        signals.append(f"Outperforming SPY (+{rs_score_val:.1f}%)")
    elif rs_score_val > 0:
        score += 2
    elif rs_score_val < -5:
        score -= 6
        warnings.append(f"Lagging SPY badly ({rs_score_val:.1f}%)")
    elif rs_score_val < -2:
        score -= 3
        warnings.append(f"Underperforming SPY ({rs_score_val:.1f}%)")
    
    # -- Sector strength (0-8 points) --
    sector_etf = data.get("sector_etf")
    in_strong_sector = False
    if sector_etf:
        sectors = _get_sector_strength()
        sec_data = sectors.get(sector_etf)
        if sec_data:
            if sec_data.get("rank", 99) <= 3:
                score += 8
                in_strong_sector = True
                signals.append(f"Top 3 sector: {sec_data['name']} (#{sec_data['rank']})")
            elif sec_data.get("top_half"):
                score += 4
                in_strong_sector = True
                signals.append(f"Strong sector: {sec_data['name']} (#{sec_data['rank']})")
            elif sec_data.get("rank", 99) >= 9:
                score -= 5
                warnings.append(f"Weak sector: {sec_data['name']} (#{sec_data['rank']})")
            elif not sec_data.get("top_half"):
                score -= 2
    
    # -- News sentiment (±10 points) --
    news_sent = data.get("news_sentiment", {})
    news_score = news_sent.get("score", 0)
    news_label = news_sent.get("sentiment", "neutral")
    if news_score >= 4:
        score += 8
        signals.append(f"Very bullish news sentiment ({news_sent.get('bullish_count', 0)} positive headlines)")
    elif news_score >= 2:
        score += 5
        signals.append(f"Bullish news sentiment")
    elif news_score >= 1:
        score += 2
    elif news_score <= -4:
        score -= 8
        warnings.append(f"Very bearish news sentiment ({news_sent.get('bearish_count', 0)} negative headlines)")
    elif news_score <= -2:
        score -= 5
        warnings.append(f"Bearish news sentiment")
    elif news_score <= -1:
        score -= 2
    
    # ═══ STEP 4: DETERMINE ACTION ═══
    score = max(0, min(100, score))
    
    bullish_count = sum(1 for s in signals if "✓" in s or "bullish" in s.lower() or "uptrend" in s.lower() or "rising" in s.lower() or "buy" in s.lower() or "outperform" in s.lower() or "sector" in s.lower())
    bearish_count = sum(1 for w in warnings)
    
    # BUY requires: uptrend confirmed + quality score
    # STRONG_BUY requires: pullback + strong sector + relative strength
    is_uptrend = above_200 and above_50
    has_pullback = pullback_to_20 or pullback_to_50
    outperforming = rs.get("outperforming", False)
    
    if score >= 75 and is_uptrend and trending and (in_strong_sector or outperforming):
        action = "STRONG_BUY"
        confidence = min(95, score)
    elif score >= 62 and is_uptrend:
        action = "BUY"
        confidence = min(85, score)
    elif score <= 30:
        action = "STRONG_SELL"
        confidence = min(90, 100 - score)
    elif score <= 40:
        action = "SELL"
        confidence = min(80, 100 - score)
    else:
        action = "HOLD"
        confidence = max(40, 100 - abs(score - 50) * 2)
    
    # ═══ STEP 5: RISK MANAGEMENT (Day Trading) ═══
    if action in ("BUY", "STRONG_BUY"):
        entry = price
        # Stop loss: 1.5x ATR below entry, or below nearest support — whichever is tighter
        stop_atr = round(entry - 1.5 * atr, 2)
        stop_support = round(supports[0] - 0.2 * atr, 2) if supports and (price - supports[0]) / price < 0.03 else stop_atr
        stop_loss = max(stop_atr, stop_support)
        # Minimum 1% stop distance
        min_stop = round(entry * 0.99, 2)
        if stop_loss > min_stop:
            stop_loss = min_stop
        
        risk = max(entry - stop_loss, 0.01)
        # Target at 2:1 and 3:1 R:R (day trading targets)
        target_1 = round(entry + 2.0 * risk, 2)
        target_2 = round(entry + 3.0 * risk, 2)
        risk_pct = round(risk / entry * 100, 2)
    elif action in ("SELL", "STRONG_SELL"):
        entry = price
        stop_loss = round(price + 1.5 * atr, 2)
        risk = max(stop_loss - entry, 0.01)
        target_1 = round(entry - 2.0 * risk, 2)
        target_2 = round(entry - 3.0 * risk, 2)
        risk_pct = round(risk / entry * 100, 2)
    else:
        entry = price
        stop_loss = round(price - 1.5 * atr, 2)
        risk = 1.5 * atr
        target_1 = round(price + 1.5 * atr, 2)
        target_2 = round(price + 3.0 * atr, 2)
        risk_pct = round(risk / price * 100, 2)
    
    rr = round((target_1 - entry) / risk, 2) if risk > 0 and target_1 > entry else (
         round((entry - target_1) / risk, 2) if risk > 0 and entry > target_1 else 0)
    
    return {
        "action": action,
        "score": score,
        "confidence": confidence,
        "confluence": {"bullish": bullish_count, "bearish": bearish_count},
        "category_scores": {
            "trend": 1 if is_uptrend else -1,
            "pullback": 1 if has_pullback else 0,
            "momentum": 1 if macd_h > 0 else -1,
            "volume": 1 if obv_trend == "rising" else (-1 if obv_trend == "falling" else 0),
            "rsi": 1 if 30 <= rsi <= 55 else (-1 if rsi > 75 else 0),
            "news": 1 if news_score >= 2 else (-1 if news_score <= -2 else 0),
        },
        "signals": signals,
        "warnings": warnings,
        "trade": {
            "entry": round(entry, 2),
            "stop_loss": round(stop_loss, 2),
            "target_1": target_1,
            "target_2": target_2,
            "risk_reward": rr,
            "risk_pct": risk_pct,
            "atr": round(atr, 2),
        },
    }

# ── Data fetching ────────────────────────────────────────────────────────────

@st.cache_data(ttl=120)
def fetch_price(ticker: str) -> dict | None:
    try:
        stk = yf.Ticker(ticker)
        info = stk.info or {}
        price = info.get("currentPrice") or info.get("regularMarketPrice")
        prev = info.get("previousClose") or info.get("regularMarketPreviousClose")
        if not price or price <= 0:
            hist = stk.history(period="5d")
            if hist is None or hist.empty:
                return None
            price = float(hist["Close"].iloc[-1])
            prev = float(hist["Close"].iloc[-2]) if len(hist) >= 2 else price
        prev = prev or price
        return {
            "price": round(price, 2), "prev_close": round(prev, 2),
            "change": round(price - prev, 2),
            "change_pct": round((price - prev) / prev * 100, 2) if prev else 0,
            "name": info.get("shortName") or ticker,
            "market_cap": info.get("marketCap"),
            "pe_ratio": info.get("trailingPE"), "forward_pe": info.get("forwardPE"),
            "52w_high": info.get("fiftyTwoWeekHigh"), "52w_low": info.get("fiftyTwoWeekLow"),
            "sector": info.get("sector"),
            "target_price": info.get("targetMeanPrice"),
            "recommendation": info.get("recommendationKey"),
        }
    except Exception:
        return None



# ── Sector rotation + relative strength ──────────────────────────────────────

SECTOR_ETFS = {
    "XLK": "Technology", "XLV": "Healthcare", "XLF": "Financials",
    "XLY": "Consumer Discretionary", "XLP": "Consumer Staples",
    "XLE": "Energy", "XLI": "Industrials", "XLB": "Materials",
    "XLU": "Utilities", "XLRE": "Real Estate", "XLC": "Communication",
}

TICKER_SECTOR = {
    **{t: "XLK" for t in ["AAPL","MSFT","NVDA","AMD","AVGO","TXN","QCOM","AMAT","LRCX","KLAC",
        "SNPS","CDNS","MRVL","ADI","NXPI","MCHP","SWKS","MPWR","ENTG","TER","ON","ARM","SMCI",
        "MU","INTC","ASML","TSM","CRM","INTU","ADBE","NOW","ORCL","WDAY","VEEV","HUBS",
        "CYBR","PANW","CRWD","PATH","DOCN","FROG","MANH","PTC","PAYC","SHOP","TTD",
        "PLTR","IBM","CSCO","HPQ","FICO","APP","S","QLYS"]},
    **{t: "XLV" for t in ["UNH","LLY","ABBV","MRK","JNJ","PFE","TMO","ABT","SYK","BSX",
        "ISRG","DHR","VRTX","REGN","AMGN","GILD","ALNY","ARGX","BMRN","TGTX","RXRX",
        "CRSP","NBIX","MOH","HUM","CNC","ELV","MCK","DXCM","PODD","ALGN","TMDX",
        "MRNA","BNTX","HIMS","DOCS","RMD","ZBH","HOLX","EW"]},
    **{t: "XLF" for t in ["JPM","V","MA","GS","MS","BAC","WFC","BX","SCHW","COF","AXP",
        "HOOD","COIN","MSTR","PYPL","C","PNC","USB","TFC","MTB","CFG","HBAN","RF","KEY",
        "ALL","PRU","AIG","HIG","ACGL","WRB","BRO","RJF","LPLA","BK","MMC","AON","CINF",
        "UPST","LMND","ROOT"]},
    **{t: "XLY" for t in ["AMZN","TSLA","HD","COST","TJX","ROST","ORLY","AZO","CMG","DPZ",
        "MCD","SBUX","NKE","LULU","BKNG","MAR","HLT","RCL","UBER","ABNB","CVNA","DASH",
        "CHWY","ETSY","W","EBAY","DECK","GM","F","RIVN","NIO","LEN","PHM","TOL","DHI",
        "ONON","ELF","CAVA","BROS","TOST","DUOL","CELH"]},
    **{t: "XLP" for t in ["PG","KO","PEP","WMT","PM","MO","CL","KMB","STZ","KHC",
        "HSY","MNST","MDLZ"]},
    **{t: "XLE" for t in ["XOM","CVX","COP","EOG","DVN","OXY","SLB","HAL","BKR","MPC",
        "VLO","PSX","FANG","TRGP","OKE","WMB","ET","EPD","MRO","APA","EQT","CTRA",
        "MARA","RIOT","CLSK"]},
    **{t: "XLI" for t in ["CAT","DE","HON","GE","BA","UPS","FDX","RTX","LMT","NOC",
        "GD","LHX","KTOS","AXON","TDG","CARR","IR","EMR","ROK","PH","URI","WAB",
        "PWR","PCAR","GWW","FAST","CPRT","WM","ITW","RKLB","SOUN","ASTS","LUNR","JOBY",
        "OTIS","STE","HUBB","FTV"]},
    **{t: "XLB" for t in ["NUE","CLF","STLD","FCX","NEM","VMC","MLM","APD","ECL","SHW",
        "PPG","DD","DOW","LIN","RS","VALE","CF","MOS","NTR"]},
    **{t: "XLU" for t in ["NEE","DUK","SO","D","AEP","EXC","SRE","WEC","XEL","ED","PCG",
        "FSLR","ENPH","CEG","VST","SMR","OKLO"]},
    **{t: "XLRE" for t in ["PLD","EQIX","SPG","O","DLR","CCI","EQR","AVB","WELL","STAG","NNN"]},
    **{t: "XLC" for t in ["GOOGL","GOOG","META","DIS","CMCSA","NFLX","T","VZ","TMUS",
        "WBD","SPOT","ROKU","SNAP","PINS","MTCH","DKNG","EA","TTWO"]},
}


@st.cache_data(ttl=600)
def _get_spy_performance() -> dict:
    """Get SPY performance over multiple timeframes for relative strength."""
    try:
        spy = yf.Ticker("SPY")
        hist = spy.history(period="6mo")
        if hist is None or hist.empty or len(hist) < 60:
            return {}
        close = hist["Close"]
        current = float(close.iloc[-1])
        perf = {}
        for days, label in [(5, "1w"), (21, "1m"), (63, "3m")]:
            if len(close) > days:
                past = float(close.iloc[-days - 1])
                perf[label] = (current - past) / past * 100
        return perf
    except Exception:
        return {}


@st.cache_data(ttl=600)
def _get_sector_strength() -> dict:
    """Rank sector ETFs by recent performance."""
    results = {}
    for etf, name in SECTOR_ETFS.items():
        try:
            hist = yf.Ticker(etf).history(period="3mo")
            if hist is None or hist.empty or len(hist) < 20:
                continue
            close = hist["Close"]
            current = float(close.iloc[-1])
            past_1m = float(close.iloc[-22]) if len(close) > 22 else current
            past_1w = float(close.iloc[-6]) if len(close) > 6 else current
            perf_1m = (current - past_1m) / past_1m * 100
            perf_1w = (current - past_1w) / past_1w * 100
            composite = perf_1w * 0.6 + perf_1m * 0.4
            results[etf] = {"name": name, "1w": round(perf_1w, 2), "1m": round(perf_1m, 2),
                            "composite": round(composite, 2)}
        except Exception:
            continue
    ranked = sorted(results.items(), key=lambda x: x[1]["composite"], reverse=True)
    for rank, (etf, data) in enumerate(ranked):
        results[etf]["rank"] = rank + 1
        results[etf]["top_half"] = rank < len(ranked) / 2
    return results


def _calc_relative_strength(hist: pd.DataFrame) -> dict:
    """Calculate stock's performance vs SPY over multiple timeframes."""
    try:
        close = hist["Close"]
        current = float(close.iloc[-1])
        spy_perf = _get_spy_performance()
        if not spy_perf:
            return {"rs_score": 0, "outperforming": False}
        stock_perf = {}
        for days, label in [(5, "1w"), (21, "1m"), (63, "3m")]:
            if len(close) > days:
                past = float(close.iloc[-days - 1])
                stock_perf[label] = (current - past) / past * 100
        rs_values = []
        for label in ["1w", "1m", "3m"]:
            if label in stock_perf and label in spy_perf:
                rs_values.append(stock_perf[label] - spy_perf[label])
        if not rs_values:
            return {"rs_score": 0, "outperforming": False}
        weights = [0.5, 0.3, 0.2][:len(rs_values)]
        rs_score = sum(r * w for r, w in zip(rs_values, weights)) / sum(weights)
        return {"rs_score": round(rs_score, 2), "outperforming": rs_score > 0, "stock_perf": stock_perf}
    except Exception:
        return {"rs_score": 0, "outperforming": False}


# ── News Sentiment ───────────────────────────────────────────────────────────

_BULLISH_KW = [
    "upgrade", "upgrades", "upgraded", "beat", "beats", "beating", "surpass",
    "record", "soars", "soar", "surge", "surges", "rally", "rallies", "jumps",
    "breakout", "outperform", "buy", "bullish", "raises", "raise", "boost",
    "boosts", "growth", "grows", "profit", "profits", "strong", "positive",
    "optimistic", "launch", "launches", "deal", "partnership", "expand",
    "expansion", "approval", "approved", "fda approved", "dividend", "buyback",
    "repurchase", "innovation", "ai", "breakthrough", "wins", "contract",
    "higher", "accelerat", "momentum", "upbeat", "top", "tops", "exceeded",
    "exceeds", "impressive", "robust", "blowout", "crushes", "crush",
]
_BEARISH_KW = [
    "downgrade", "downgrades", "downgraded", "miss", "misses", "missed",
    "cut", "cuts", "slash", "slashes", "plunge", "plunges", "crash",
    "crashes", "tumble", "tumbles", "drops", "drop", "falls", "fall",
    "sell", "bearish", "weak", "warns", "warning", "layoff", "layoffs",
    "lawsuit", "sued", "fraud", "investigation", "probe", "recall",
    "recalls", "bankruptcy", "debt", "loss", "losses", "negative",
    "decline", "declining", "risk", "fear", "concerns", "worried",
    "disappointing", "disappoints", "underperform", "lower", "lowers",
    "worst", "slump", "trouble", "struggles", "struggling", "delay",
    "delayed", "reject", "rejected", "overvalued", "bubble", "short",
]


@st.cache_data(ttl=600)
def _news_sentiment(ticker: str) -> dict:
    """Fast keyword-based news sentiment from yfinance headlines. Returns score and headlines."""
    try:
        stk = yf.Ticker(ticker)
        raw = stk.news or []
        headlines = []
        for n in raw[:8]:
            title = n.get("title", "")
            if not title:
                continue
            headlines.append({"title": title, "publisher": n.get("publisher", "")})

        if not headlines:
            return {"score": 0, "sentiment": "neutral", "headlines": [], "count": 0}

        bull = 0
        bear = 0
        for h in headlines:
            t = h["title"].lower()
            for kw in _BULLISH_KW:
                if kw in t:
                    bull += 1
                    break
            for kw in _BEARISH_KW:
                if kw in t:
                    bear += 1
                    break

        total = len(headlines)
        # Net sentiment: -10 to +10
        if total > 0:
            net = (bull - bear) / total
            score = round(net * 10)
        else:
            score = 0

        if score >= 4:
            sentiment = "very_bullish"
        elif score >= 2:
            sentiment = "bullish"
        elif score <= -4:
            sentiment = "very_bearish"
        elif score <= -2:
            sentiment = "bearish"
        else:
            sentiment = "neutral"

        return {
            "score": max(-10, min(10, score)),
            "sentiment": sentiment,
            "headlines": headlines,
            "count": total,
            "bullish_count": bull,
            "bearish_count": bear,
        }
    except Exception:
        return {"score": 0, "sentiment": "neutral", "headlines": [], "count": 0}


def fetch_scan(ticker: str) -> dict | None:
    """Lightweight fetch for scanning — skips slow .info calls, just gets history + technicals."""
    try:
        stk = yf.Ticker(ticker)
        hist = stk.history(period="1y")
        if hist is None or hist.empty or len(hist) < 50:
            return None
        price = float(hist["Close"].iloc[-1])
        prev = float(hist["Close"].iloc[-2]) if len(hist) >= 2 else price
        if not price or price < 1:
            return None
        tech = compute_technicals(hist)
        rs = _calc_relative_strength(hist)
        sector_etf = TICKER_SECTOR.get(ticker)
        news = _news_sentiment(ticker)
        return {
            "price": round(price, 2),
            "prev_close": round(prev, 2),
            "change_pct": round((price - prev) / prev * 100, 2) if prev else 0,
            "name": ticker,
            "ticker": ticker,
            "full_ticker": ticker,
            "technicals": tech,
            "relative_strength": rs,
            "sector_etf": sector_etf,
            "news_sentiment": news,
        }
    except Exception:
        return None


@st.cache_data(ttl=120)
def fetch_full(ticker: str) -> dict | None:
    basic = fetch_price(ticker)
    if not basic:
        return None
    try:
        stk = yf.Ticker(ticker)
        info = stk.info or {}
        hist = stk.history(period="1y")
        tech = compute_technicals(hist)
        news = []
        try:
            for n in (stk.news or [])[:5]:
                news.append({"title": n.get("title", ""), "publisher": n.get("publisher", "")})
        except Exception:
            pass
        return {
            **basic, "ticker": ticker.replace(".NS", ""), "full_ticker": ticker,
            "peg_ratio": info.get("pegRatio"), "roe": info.get("returnOnEquity"),
            "profit_margin": info.get("profitMargins"),
            "revenue_growth": info.get("revenueGrowth"),
            "earnings_growth": info.get("earningsGrowth"),
            "debt_to_equity": info.get("debtToEquity"),
            "dividend_yield": info.get("dividendYield"), "beta": info.get("beta"),
            "target_high": info.get("targetHighPrice"),
            "target_low": info.get("targetLowPrice"),
            "num_analysts": info.get("numberOfAnalystOpinions"),
            "industry": info.get("industry", "N/A"),
            "technicals": tech, "news": news,
            "news_sentiment": _news_sentiment(ticker),
        }
    except Exception:
        return basic


# ── Chart ────────────────────────────────────────────────────────────────────

def build_chart(ticker: str, period: str = "6mo", trade_signal: dict | None = None) -> go.Figure | None:
    try:
        hist = yf.Ticker(ticker).history(period=period)
        if hist is None or hist.empty or len(hist) < 5:
            hist = yf.Ticker(ticker).history(period="1mo")
            if hist is None or hist.empty:
                return None

        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.02, row_heights=[0.75, 0.25])

        fig.add_trace(go.Candlestick(
            x=hist.index, open=hist["Open"], high=hist["High"],
            low=hist["Low"], close=hist["Close"], name="Price",
            increasing_line_color="#34d399", decreasing_line_color="#f87171",
            increasing_fillcolor="#34d399", decreasing_fillcolor="#f87171",
        ), row=1, col=1)

        if len(hist) >= 20:
            fig.add_trace(go.Scatter(x=hist.index, y=hist["Close"].rolling(20).mean(), name="20d", line=dict(color="#60a5fa", width=1)), row=1, col=1)
        if len(hist) >= 50:
            fig.add_trace(go.Scatter(x=hist.index, y=hist["Close"].rolling(50).mean(), name="50d", line=dict(color="#fbbf24", width=1)), row=1, col=1)

        # Trade signal lines on chart
        if trade_signal and trade_signal.get("trade"):
            tr = trade_signal["trade"]
            act = trade_signal.get("action", "")
            if act in ("BUY", "STRONG_BUY", "SELL", "STRONG_SELL"):
                fig.add_hline(y=tr["entry"], line_dash="dash", line_color="#60a5fa", annotation_text=f"Entry {tr['entry']:.2f}", row=1, col=1)
                fig.add_hline(y=tr["stop_loss"], line_dash="dash", line_color="#f87171", annotation_text=f"Stop {tr['stop_loss']:.2f}", row=1, col=1)
                fig.add_hline(y=tr["target_1"], line_dash="dash", line_color="#34d399", annotation_text=f"T1 {tr['target_1']:.2f}", row=1, col=1)
                fig.add_hline(y=tr["target_2"], line_dash="dot", line_color="#34d399", annotation_text=f"T2 {tr['target_2']:.2f}", row=1, col=1)

        colors = ["#34d399" if c >= o else "#f87171" for c, o in zip(hist["Close"], hist["Open"])]
        fig.add_trace(go.Bar(x=hist.index, y=hist["Volume"], marker_color=colors, opacity=0.4, name="Vol"), row=2, col=1)

        fig.update_layout(
            template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#94a3b8", size=11, family="JetBrains Mono, monospace"),
            showlegend=True, legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(size=10)),
            height=420, margin=dict(l=0, r=0, t=30, b=0), xaxis_rangeslider_visible=False,
        )
        fig.update_xaxes(showgrid=False, zeroline=False)
        fig.update_yaxes(showgrid=True, gridcolor="rgba(148,163,184,0.08)", zeroline=False)
        return fig
    except Exception:
        return None


# ── Intent routing ───────────────────────────────────────────────────────────

def route(msg: str) -> dict:
    m = msg.lower().strip()
    if m in ("hi", "hello", "hey", "thanks", "thank you", "help", "bye"):
        return {"type": "chat"}
    ticker, market = _find_ticker(msg)

    # ── Trading commands ──
    if any(w in m for w in ["activate autopilot", "activate alpaca", "autopilot", "auto trade",
                            "start trading", "go autopilot", "run autopilot", "auto pilot",
                            "scan and trade", "find and buy", "find trades"]):
        return {"type": "autopilot"}
    if any(w in m for w in ["force scan", "scan now", "scan anyway", "scan market", "run scan"]):
        return {"type": "force_scan"}
    if any(w in m for w in ["stop autopilot", "deactivate", "stop trading", "pause", "stop auto",
                            "turn off autopilot", "kill autopilot", "stop"]):
        return {"type": "stop_autopilot"}
    if any(w in m for w in ["backtest", "back test", "test strategy", "prove it", "historical test",
                            "how would it have done", "test the strategy"]):
        return {"type": "backtest"}
    if any(w in m for w in ["market health", "market regime", "is market safe", "spy check", "market status"]):
        return {"type": "market_regime"}
    if any(w in m for w in ["sector strength", "sector rotation", "sectors", "hot sectors", "strong sectors"]):
        return {"type": "sector_strength"}
    if any(w in m for w in ["portfolio", "my account", "buying power", "my equity", "account info", "how much do i have"]):
        return {"type": "portfolio"}
    if any(w in m for w in ["my positions", "what do i own", "what am i holding", "open positions", "show positions"]):
        return {"type": "positions"}
    if any(w in m for w in ["my orders", "open orders", "order history", "recent orders", "pending orders"]):
        return {"type": "orders"}
    if any(w in m for w in ["close all", "sell everything", "liquidate", "panic sell", "close everything"]):
        return {"type": "close_all"}

    # "buy NVDA", "buy 10 AAPL", "buy $500 of TSLA"
    buy_match = re.search(r'\bbuy\b', m)
    if buy_match and ticker:
        qty = None
        notional = None
        qty_match = re.search(r'buy\s+(\d+)\s+', m)
        dollar_match = re.search(r'buy\s+\$?([\d,]+(?:\.\d+)?)\s+(?:of|worth)', m)
        if qty_match:
            qty = int(qty_match.group(1))
        elif dollar_match:
            notional = float(dollar_match.group(1).replace(",", ""))
        return {"type": "buy", "ticker": ticker, "market": market, "qty": qty, "notional": notional}

    # "sell NVDA", "sell 5 AAPL", "close TSLA", "sell all NVDA"
    sell_match = re.search(r'\b(sell|close)\b', m)
    if sell_match and ticker:
        sell_all = "all" in m or "close" in m
        qty = None
        qty_match = re.search(r'sell\s+(\d+)\s+', m)
        if qty_match:
            qty = int(qty_match.group(1))
        return {"type": "sell", "ticker": ticker, "market": market, "qty": qty, "sell_all": sell_all}

    # "execute trade on NVDA", "trade AAPL", "smart buy TSLA"
    if any(w in m for w in ["execute trade", "smart buy", "auto buy", "trade signal buy"]):
        if ticker:
            return {"type": "smart_buy", "ticker": ticker, "market": market}

    # ── Market scanning ──
    if any(w in m for w in ["gainer", "gaining", "top performer", "winners", "best stock"]):
        return {"type": "gainers", "market": market}
    if any(w in m for w in ["loser", "losing", "worst", "dropping", "falling"]):
        return {"type": "losers", "market": market}
    if any(w in m for w in ["trending", "hot", "movers", "moving"]):
        return {"type": "hot", "market": market}
    if any(w in m for w in ["price of", "price for", "what's the price", "how much is", "current price", "quote"]):
        if ticker:
            return {"type": "price", "ticker": ticker, "market": market}
    if ticker:
        return {"type": "analyze", "ticker": ticker, "market": market}
    return {"type": "chat", "market": market}


def _market_is_open() -> tuple[bool, str]:
    """Check if US stock market is currently open."""
    et = ZoneInfo("US/Eastern")
    now = datetime.now(et)
    weekday = now.weekday()  # 0=Mon, 6=Sun

    if weekday >= 5:
        next_open = "Monday 9:30 AM ET"
        return False, f"Weekend — market reopens {next_open}"

    market_open = now.replace(hour=9, minute=30, second=0, microsecond=0)
    market_close = now.replace(hour=16, minute=0, second=0, microsecond=0)

    if now < market_open:
        return False, f"Pre-market — opens at 9:30 AM ET ({market_open - now} from now)"
    if now >= market_close:
        return False, "Market closed for today — reopens tomorrow 9:30 AM ET"

    return True, "Market is open"


# ── Market regime filter ─────────────────────────────────────────────────────

def check_market_regime() -> dict:
    """
    Check overall market health using SPY.
    Returns regime + whether it's safe to buy.
    """
    try:
        spy = yf.Ticker("SPY")
        hist = spy.history(period="1y")
        if hist is None or hist.empty or len(hist) < 200:
            return {"regime": "unknown", "safe_to_buy": True, "reason": "Not enough SPY data"}

        close = hist["Close"]
        price = float(close.iloc[-1])

        # Key moving averages
        sma_50 = float(close.rolling(50).mean().iloc[-1])
        sma_200 = float(close.rolling(200).mean().iloc[-1])
        sma_20 = float(close.rolling(20).mean().iloc[-1])

        # RSI
        delta = close.diff()
        gain = delta.where(delta > 0, 0.0).ewm(alpha=1/14, min_periods=14).mean()
        loss = (-delta.where(delta < 0, 0.0)).ewm(alpha=1/14, min_periods=14).mean()
        rs = gain / loss.replace(0, 1e-10)
        rsi = float(100 - (100 / (1 + rs)).iloc[-1])

        # Percentage from 200 SMA
        dist_from_200 = (price - sma_200) / sma_200 * 100

        # Determine regime
        if price > sma_200 and sma_50 > sma_200:
            if dist_from_200 > 10:
                regime = "strong_bull"
            else:
                regime = "bull"
        elif price > sma_200 and sma_50 < sma_200:
            regime = "recovery"
        elif price < sma_200 and sma_50 > sma_200:
            regime = "weakening"
        elif price < sma_200 and sma_50 < sma_200:
            if dist_from_200 < -10:
                regime = "strong_bear"
            else:
                regime = "bear"
        else:
            regime = "neutral"

        # Safe to buy?
        safe = True
        reason = ""

        if regime in ("strong_bear", "bear"):
            safe = False
            reason = f"SPY below 200 SMA — bear market (SPY ${price:.2f}, 200 SMA ${sma_200:.2f})"
        elif regime == "weakening":
            safe = True  # can still buy but with caution
            reason = f"Market weakening — SPY slipping below 50 SMA (RSI {rsi:.0f})"
        elif rsi > 80:
            safe = False
            reason = f"SPY overbought (RSI {rsi:.0f}) — wait for pullback"
        elif rsi < 25:
            safe = False
            reason = f"SPY extremely oversold (RSI {rsi:.0f}) — possible crash, stay out"
        else:
            reason = f"SPY ${price:.2f} — {regime} regime, RSI {rsi:.0f}"

        return {
            "regime": regime,
            "safe_to_buy": safe,
            "reason": reason,
            "spy_price": round(price, 2),
            "sma_50": round(sma_50, 2),
            "sma_200": round(sma_200, 2),
            "rsi": round(rsi, 1),
        }
    except Exception as e:
        return {"regime": "unknown", "safe_to_buy": True, "reason": f"Could not check: {str(e)[:60]}"}


# ── Earnings avoidance ───────────────────────────────────────────────────────

def _has_upcoming_earnings(ticker: str, days: int = 7) -> tuple[bool, str | None]:
    """Check if a stock has earnings within the next N days."""
    try:
        stk = yf.Ticker(ticker)
        cal = stk.calendar
        if cal is None or (isinstance(cal, pd.DataFrame) and cal.empty):
            return False, None
        # yfinance returns earnings date in different formats
        if isinstance(cal, dict):
            earn_date = cal.get("Earnings Date")
            if isinstance(earn_date, list) and earn_date:
                earn_date = earn_date[0]
        elif isinstance(cal, pd.DataFrame):
            if "Earnings Date" in cal.columns:
                earn_date = cal["Earnings Date"].iloc[0]
            elif "Earnings Date" in cal.index:
                earn_date = cal.loc["Earnings Date"].iloc[0]
            else:
                return False, None
        else:
            return False, None

        if earn_date is None:
            return False, None

        if isinstance(earn_date, str):
            earn_date = pd.to_datetime(earn_date)
        elif hasattr(earn_date, 'to_pydatetime'):
            earn_date = earn_date.to_pydatetime()

        if hasattr(earn_date, 'tzinfo') and earn_date.tzinfo:
            now = datetime.now(earn_date.tzinfo)
        else:
            now = datetime.now()

        delta = (earn_date - now).days
        if 0 <= delta <= days:
            return True, earn_date.strftime("%Y-%m-%d")
        return False, None
    except Exception:
        return False, None


# ── Trailing stops ───────────────────────────────────────────────────────────

def update_trailing_stops(positions: list[dict], log: list) -> list[str]:
    """
    For each open position, check if price has moved up enough to trail the stop.
    Uses 1.5x ATR trailing stop from the highest price since entry (day trading).
    """
    actions = []
    for pos in positions:
        try:
            ticker = pos["ticker"]
            entry = pos["avg_entry"]
            current = pos["current_price"]
            pnl_pct = pos["unrealized_pnl_pct"]

            # Only trail stops on positions that are profitable
            if pnl_pct <= 0:
                continue

            # Get ATR for trailing distance
            hist = yf.Ticker(ticker).history(period="1mo")
            if hist is None or hist.empty or len(hist) < 14:
                continue

            # Calculate ATR
            high = hist["High"]
            low = hist["Low"]
            close = hist["Close"]
            tr = pd.concat([
                high - low,
                (high - close.shift(1)).abs(),
                (low - close.shift(1)).abs(),
            ], axis=1).max(axis=1)
            atr = float(tr.rolling(14).mean().iloc[-1])

            # Highest close in recent days
            recent_high = float(close.tail(5).max())

            # New trailing stop: highest recent price minus 1.5x ATR (day trading)
            new_stop = round(recent_high - (1.5 * atr), 2)

            # Only move stop UP, never down. And only if it's above entry (lock in profit)
            if new_stop > entry and new_stop > entry * 1.01:
                # Cancel existing orders and place new stop
                # First check for existing stop orders
                orders = alpaca_orders(status="open", limit=20)
                for o in orders:
                    if o["symbol"] == ticker and o["type"] in ("stop", "stop_limit"):
                        # Cancel old stop
                        try:
                            requests.delete(f"{ALPACA_BASE}/v2/orders/{o['id']}",
                                            headers=_alpaca_headers(), timeout=5)
                        except Exception:
                            pass

                # Place new trailing stop as a stop market order
                stop_order = {
                    "symbol": ticker,
                    "qty": str(int(pos["qty"])),
                    "side": "sell",
                    "type": "stop",
                    "stop_price": str(new_stop),
                    "time_in_force": "day",  # day trading — expires at close
                }
                try:
                    r = requests.post(f"{ALPACA_BASE}/v2/orders", headers=_alpaca_headers(),
                                      json=stop_order, timeout=10)
                    if r.status_code in (200, 201):
                        actions.append(f"📈 Trailed stop on {ticker}: ${entry:.2f} → ${new_stop:.2f} (locking in ${new_stop - entry:.2f}/share profit)")
                    else:
                        actions.append(f"⚠️ Failed to trail {ticker}: {r.json().get('message', '')[:60]}")
                except Exception:
                    pass
        except Exception:
            continue

    return actions


# ── Backtester ───────────────────────────────────────────────────────────────

def run_backtest(years: int = 2) -> dict:
    """
    Backtest the signal engine against historical data.
    Simulates autopilot with trailing stops over the last N years.
    """
    STARTING_CAPITAL = 25_000
    RISK_PER_TRADE = 0.01
    MIN_SCORE = 65
    MIN_RR = 1.5

    # 100 stocks
    TEST_UNIVERSE = [
        # ── Tech / Semis ──
        "AAPL","MSFT","AMZN","NVDA","GOOGL","META","TSLA","AMD","NFLX","ADBE",
        "CRM","INTU","QCOM","AMAT","ISRG","MU","PANW","CRWD","AVGO","TXN",
        "ASML","KLAC","SNPS","CDNS","MRVL","LRCX","ADI","NXPI","MCHP","SWKS",
        "MPWR","ENTG","TER","ON","ARM","SMCI",
        # ── Software / Cloud ──
        "NOW","ORCL","WDAY","VEEV","HUBS","DDOG","MNDY","CFLT","ESTC","GTLB",
        "PATH","DOCN","FROG","MANH","PTC","PAYC","SHOP","TTD",
        # ── Mid-cap growth ──
        "AXON","HIMS","CAVA","DUOL","CELH","ELF","ONON","TOST","BROS",
        "IOT","DOCS","APP","RAMP","DECK","TMDX","PODD","ALGN","DXCM",
        "FICO","LPLA","MPWR","HUBB","FTV",
        # ── Fintech / Finance ──
        "JPM","V","MA","GS","MS","BAC","WFC","BX","SCHW","COF",
        # ── Healthcare / Biotech ──
        "UNH","LLY","ABBV","MRK","JNJ","PFE","TMO","ABT","SYK","BSX",
        "ISRG","DHR","VRTX","REGN","AMGN","GILD","ALNY","ARGX","BMRN",
        "TGTX","RXRX","CRSP","NBIX","MOH","HUM","CNC","ELV","MCK",
        # ── Consumer ──
        "HD","COST","WMT","PG","KO","PEP","MCD","SBUX","NKE","LULU",
        "TJX","ROST","ORLY","AZO","CMG","DPZ","CHWY","ETSY","DASH","BKNG",
        "MAR","HLT","RCL","UBER","ABNB","CVNA",
        # ── Industrial / Defense ──
        "CAT","DE","HON","GE","BA","UPS","FDX","RTX","LMT","NOC",
        "GD","LHX","KTOS","AXON","TDG","CARR","IR","EMR","ROK","PH",
        "URI","WAB","PWR","PCAR","GWW","FAST",
        # ── Energy ──
        "XOM","CVX","COP","EOG","DVN","OXY","SLB","HAL","BKR","MPC",
        "VLO","PSX","FANG","TRGP","OKE","WMB","ET","EPD",
        # ── Clean Energy / Nuclear ──
        "FSLR","ENPH","CEG","VST","SMR","OKLO","NEE",
        # ── Materials / Mining ──
        "NUE","CLF","STLD","FCX","NEM","VMC","MLM","APD","ECL","SHW","PPG",
        # ── Real Estate / REITs ──
        "PLD","EQIX","SPG","O","DLR","CCI","EQR","AVB","WELL","STAG","NNN","MAA",
        # ── Telecom / Media ──
        "TMUS","VZ","T","DIS","CMCSA","WBD","SPOT","ROKU","DKNG","EA","TTWO",
        # ── Utilities ──
        "DUK","SO","D","AEP","EXC","SRE","WEC","XEL","ED","PCG",
        # ── Consumer Staples ──
        "PM","MO","CL","KMB","STZ","KHC","HSY","MNST","MDLZ",
        # ── Small-cap / Speculative ──
        "PLTR","UPST","RKLB","SOUN","ASTS","LUNR","JOBY","BBAI",
        "MARA","RIOT","CLSK","IONQ","RGTI","RIVN","NIO",
        # ── More mid-cap ──
        "LULU","CPRT","WM","SNAP","PINS","MTCH","RBLX","ABNB","DASH",
        "ANET","ZBRA","POOL","HOLX","GNRC","TYL","TTWO","NTRA","PCVX",
        "ALNY","MOH","TMDX","WST","ROKU","CHWY","ETSY","CVNA",
        # ── International ADRs ──
        "TSM","BABA","MELI","NU","SE","GRAB","CPNG","NVO","AZN","SAP",
        "SONY","TM","JD","PDD","BIDU","ASML","DEO","GSK","SNY",
    ]

    capital = STARTING_CAPITAL
    trades = []
    wins = 0
    losses = 0
    peak = capital
    min_capital = capital

    log = [f"**Backtesting {len(TEST_UNIVERSE)} stocks over {years} years...**",
           f"Starting capital: ${STARTING_CAPITAL:,}",
           f"Rules: score≥{MIN_SCORE}, BUY/STRONG_BUY only, R:R≥{MIN_RR}, 1.5x ATR trailing stops, pullback-in-uptrend"]

    step = 20

    for ticker in TEST_UNIVERSE:
        try:
            stk = yf.Ticker(ticker)
            hist = stk.history(period=f"{years}y")
            if hist is None or hist.empty or len(hist) < 252:
                continue

            window_size = 200

            for i in range(window_size, len(hist) - 40, step):
                if capital < 500:
                    break

                window = hist.iloc[i - window_size:i]
                future = hist.iloc[i:i + 60]

                if len(window) < window_size or len(future) < 10:
                    continue

                tech = compute_technicals(window)
                if not tech:
                    continue

                entry_price = float(window["Close"].iloc[-1])
                if entry_price < 5:
                    continue

                # Trend alignment: price must be above 50 SMA
                sma50 = tech.get("sma_50")
                if sma50 and entry_price < sma50:
                    continue

                data = {"price": entry_price, "technicals": tech, "ticker": ticker}
                sig = generate_trade_signal(data)

                # Strict: only BUY/STRONG_BUY, no HOLD
                if sig["action"] not in ("BUY", "STRONG_BUY"):
                    continue
                if sig["score"] < MIN_SCORE:
                    continue
                if sig["trade"]["risk_reward"] < MIN_RR:
                    continue

                stop = sig["trade"]["stop_loss"]
                target = sig["trade"]["target_1"]
                if entry_price <= stop or stop <= 0:
                    continue

                # Position sizing
                risk_per_share = entry_price - stop
                max_risk = capital * RISK_PER_TRADE
                qty = max(1, int(max_risk / risk_per_share))
                cost = qty * entry_price
                if cost > capital * 0.15:
                    qty = max(1, int(capital * 0.15 / entry_price))
                    cost = qty * entry_price
                if cost > capital:
                    continue

                # Simulate with trailing stop + partial profits
                highest = entry_price
                current_stop = stop
                exit_price = float(future["Close"].iloc[-1])
                exit_reason = "TIMEOUT"
                atr = _safe(tech.get("atr"), entry_price * 0.02)
                partial_taken = False
                partial_pnl = 0
                remaining_qty = qty
                partial_threshold = entry_price * 1.04  # +4%

                for _, day in future.iterrows():
                    day_low = float(day["Low"])
                    day_high = float(day["High"])
                    day_close = float(day["Close"])

                    # Partial profit: sell half at +4%
                    if not partial_taken and day_high >= partial_threshold and remaining_qty > 1:
                        half = remaining_qty // 2
                        partial_pnl = (partial_threshold - entry_price) * half
                        remaining_qty -= half
                        partial_taken = True
                        # Move stop to breakeven after taking partials
                        current_stop = max(current_stop, entry_price)

                    if day_low <= current_stop:
                        exit_price = current_stop
                        exit_reason = "STOPPED" if not partial_taken else "TRAILED"
                        break
                    if day_high >= target:
                        exit_price = target
                        exit_reason = "TARGET"
                        break
                    if day_close > highest:
                        highest = day_close
                        new_stop = round(highest - 1.5 * atr, 2)
                        if new_stop > current_stop:
                            current_stop = new_stop

                # Total P&L = partial profit + remaining shares profit
                remaining_pnl = (exit_price - entry_price) * remaining_qty
                pnl = partial_pnl + remaining_pnl
                pnl_pct = pnl / (entry_price * qty) * 100
                capital += pnl

                if pnl > 0:
                    wins += 1
                else:
                    losses += 1

                peak = max(peak, capital)
                min_capital = min(min_capital, capital)

                trades.append({
                    "ticker": ticker, "entry": round(entry_price, 2),
                    "exit": round(exit_price, 2), "qty": qty,
                    "pnl": round(pnl, 2), "pnl_pct": round(pnl_pct, 2),
                    "result": exit_reason, "score": sig["score"],
                })
        except Exception:
            continue

    total_trades = wins + losses
    win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
    avg_win = np.mean([t["pnl"] for t in trades if t["pnl"] > 0]) if wins > 0 else 0
    avg_loss = np.mean([t["pnl"] for t in trades if t["pnl"] < 0]) if losses > 0 else 0
    profit_factor = abs(avg_win * wins / (avg_loss * losses)) if losses > 0 and avg_loss != 0 else float("inf")
    max_drawdown = ((peak - min_capital) / peak * 100) if peak > 0 else 0
    total_return = ((capital - STARTING_CAPITAL) / STARTING_CAPITAL * 100)

    if trades:
        returns = [t["pnl_pct"] for t in trades]
        avg_ret = np.mean(returns)
        std_ret = np.std(returns) if len(returns) > 1 else 1
        sharpe = (avg_ret / std_ret * np.sqrt(252 / step)) if std_ret > 0 else 0
    else:
        sharpe = 0

    log.append("")
    log.append("**Results:**")
    log.append(f"Total trades: {total_trades} ({wins}W / {losses}L)")
    log.append(f"Win rate: {win_rate:.1f}%")
    log.append(f"Avg win: ${avg_win:+,.2f} · Avg loss: ${avg_loss:+,.2f}")
    log.append(f"Profit factor: {profit_factor:.2f}")
    log.append(f"Sharpe ratio: {sharpe:.2f}")
    log.append("")
    log.append("**Capital:**")
    log.append(f"Starting: ${STARTING_CAPITAL:,} → Final: ${capital:,.2f}")
    log.append(f"Total return: {total_return:+.1f}%")
    log.append(f"Max drawdown: {max_drawdown:.1f}%")
    log.append(f"Peak: ${peak:,.2f} · Trough: ${min_capital:,.2f}")

    if trades:
        log.append("")
        log.append("**Top 5 winners:**")
        best = sorted(trades, key=lambda x: x["pnl"], reverse=True)[:5]
        for t in best:
            log.append(f"🟢 {t['ticker']}: ${t['entry']} → ${t['exit']} ({t['pnl_pct']:+.1f}%) = ${t['pnl']:+,.2f} [{t['result']}]")
        log.append("")
        log.append("**Top 5 losers:**")
        worst = sorted(trades, key=lambda x: x["pnl"])[:5]
        for t in worst:
            log.append(f"🔴 {t['ticker']}: ${t['entry']} → ${t['exit']} ({t['pnl_pct']:+.1f}%) = ${t['pnl']:+,.2f} [{t['result']}]")

        targets_hit = sum(1 for t in trades if t["result"] == "TARGET")
        stops_hit = sum(1 for t in trades if t["result"] == "STOPPED")
        timeouts = sum(1 for t in trades if t["result"] == "TIMEOUT")
        timeout_wins = sum(1 for t in trades if t["result"] == "TIMEOUT" and t["pnl"] > 0)
        log.append("")
        log.append(f"**Exit breakdown:** {targets_hit} targets hit · {stops_hit} stopped out · {timeouts} timed out ({timeout_wins} profitable)")

    return {
        "ok": True, "log": log,
        "total_trades": total_trades, "win_rate": round(win_rate, 1),
        "total_return": round(total_return, 1), "sharpe": round(sharpe, 2),
        "final_capital": round(capital, 2),
    }

def run_autopilot(skip_market_check: bool = False, dry_run: bool = False) -> dict:
    """
    Full autopilot cycle:
    1. Check account & existing positions
    2. Sell any positions where signal has turned bad
    3. Scan universe for high-conviction setups
    4. Execute bracket orders on the best ones
    Returns a report of everything it did.
    """
    log = []

    # ── Market hours check ──
    is_open, status_msg = _market_is_open()
    if not is_open and not skip_market_check:
        log.append(f"⏸️ {status_msg}")
        log.append("Autopilot is paused — will resume when market opens.")
        return {"ok": True, "log": log, "buys": 0, "sells": 0, "scanned": 0, "opportunities": 0, "market_closed": True}
    if not is_open and skip_market_check:
        log.append(f"⚠️ {status_msg} — scanning anyway (forced)")

    # Track what we've already bought this session to prevent duplicates
    if "autopilot_bought" not in st.session_state:
        st.session_state["autopilot_bought"] = set()
    # Reset bought tracker each new day
    et = ZoneInfo("US/Eastern")
    today = datetime.now(et).strftime("%Y-%m-%d")
    if st.session_state.get("autopilot_date") != today:
        st.session_state["autopilot_bought"] = set()
        st.session_state["autopilot_date"] = today

    # ── 1. Account check ──
    account = alpaca_account()
    if not account:
        return {"ok": False, "error": "Can't connect to Alpaca."}
    log.append(f"Portfolio: ${account['equity']:,.2f} · Cash: ${account['cash']:,.2f} · Buying power: ${account['buying_power']:,.2f}")

    positions = alpaca_positions()
    held_tickers = {p["ticker"] for p in positions} | st.session_state.get("autopilot_bought", set())

    # Scale positions with equity: 1 per $5k, min 4, max 20
    MAX_POSITIONS = max(4, min(20, int(account["equity"] / 5000)))
    RISK_PER_TRADE = 0.01         # 1% risk per trade (tighter for day trading)
    MAX_POS_PCT = 0.10
    MIN_SCORE = 65                # slightly lower bar — more opportunities intraday
    MIN_CONFLUENCE = 3
    MIN_RR = 1.5                  # 1.5:1 R:R (day trades have tighter targets)
    SELL_BELOW = 40               # quicker exits

    log.append(f"Open positions: {len(positions)} · Max: {MAX_POSITIONS}")
    DAILY_LOSS_LIMIT = 0.02       # 2% max daily loss — tighter for day trading
    PARTIAL_PROFIT_PCT = 0.02     # take half off at 2% profit (faster partials)
    PARTIAL_PROFIT_SOLD_KEY = "autopilot_partial_sold"

    # ── 1b. Daily loss limit ──
    daily_pnl_pct = account.get("daily_pnl_pct", 0)
    if daily_pnl_pct <= -DAILY_LOSS_LIMIT * 100 and not dry_run:
        log.append(f"🛑 **DAILY LOSS LIMIT HIT** — down {daily_pnl_pct:.2f}% today")
        log.append("Closing all positions and shutting down autopilot.")
        result = alpaca_close_all()
        if result.get("ok"):
            log.append("All positions closed.")
        else:
            log.append(f"⚠️ Failed to close: {result.get('error', '')}")
        st.session_state["autopilot_active"] = False
        return {"ok": True, "log": log, "buys": 0, "sells": len(positions), "scanned": 0, "opportunities": 0}
    elif daily_pnl_pct <= -DAILY_LOSS_LIMIT * 100 and dry_run:
        log.append(f"🛑 Daily loss limit would trigger — down {daily_pnl_pct:.2f}% today")
    elif daily_pnl_pct < 0:
        log.append(f"Daily P&L: {daily_pnl_pct:+.2f}% (limit: -{DAILY_LOSS_LIMIT*100:.0f}%)")
    else:
        log.append(f"Daily P&L: {daily_pnl_pct:+.2f}%")

    # ── 1b. EOD Liquidation — close all positions 15min before close ──
    now_et = datetime.now(et)
    market_close = now_et.replace(hour=15, minute=45, second=0, microsecond=0)
    if now_et >= market_close and positions and not dry_run:
        log.append("🔔 **EOD LIQUIDATION** — closing all positions before market close")
        result = alpaca_close_all()
        if result.get("ok"):
            log.append(f"Closed {len(positions)} positions — flat for the day")
        else:
            log.append(f"⚠️ EOD close failed: {result.get('error', '')}")
        return {"ok": True, "log": log, "buys": 0, "sells": len(positions), "scanned": 0, "opportunities": 0}
    elif now_et >= market_close and positions and dry_run:
        log.append(f"🔔 EOD: Would close {len(positions)} positions (dry run)")

    # No new buys in last 30min of trading
    last_buy_cutoff = now_et.replace(hour=15, minute=30, second=0, microsecond=0)
    no_new_buys_eod = now_et >= last_buy_cutoff

    # ── 1c. Market regime check ──
    regime = check_market_regime()
    log.append(f"Market: {regime['reason']}")

    if not regime["safe_to_buy"]:
        log.append("⛔ Market regime unsafe — skipping new buys, only managing existing positions")

    # ── 1c. Sector strength report ──
    sectors = _get_sector_strength()
    if sectors:
        ranked = sorted(sectors.items(), key=lambda x: x[1].get("rank", 99))
        top3 = [f"{d['name']}" for _, d in ranked[:3]]
        bot3 = [f"{d['name']}" for _, d in ranked[-3:]]
        log.append(f"Hot sectors: {', '.join(top3)} · Cold: {', '.join(bot3)}")

    # ── 2. Trail stops on profitable positions ──
    if positions:
        trail_actions = update_trailing_stops(positions, log)
        for a in trail_actions:
            log.append(a)
        if not trail_actions:
            log.append("No stops to trail — positions not yet profitable enough")

    # ── 2b. Partial profit-taking — sell half at +4% to lock in gains ──
    if PARTIAL_PROFIT_SOLD_KEY not in st.session_state:
        st.session_state[PARTIAL_PROFIT_SOLD_KEY] = set()
    # Reset daily
    if st.session_state.get("autopilot_date") != today:
        st.session_state[PARTIAL_PROFIT_SOLD_KEY] = set()

    partials = []
    for pos in positions:
        ticker = pos["ticker"]
        pnl_pct = pos.get("unrealized_pnl_pct", 0)
        qty = int(pos.get("qty", 0))

        # Only take partials if: profitable enough, haven't already taken partials, and have >1 share
        if (pnl_pct >= PARTIAL_PROFIT_PCT * 100
                and ticker not in st.session_state[PARTIAL_PROFIT_SOLD_KEY]
                and qty > 1):
            half = max(1, qty // 2)
            if dry_run:
                partials.append(f"💰 Would sell {half}/{qty} shares of {ticker} at +{pnl_pct:.1f}% (locking in partial profit)")
            else:
                result = alpaca_sell(ticker=ticker, qty=half)
                if result.get("ok"):
                    partials.append(f"💰 Sold {half}/{qty} {ticker} at +{pnl_pct:.1f}% — half off, letting rest ride")
                    st.session_state[PARTIAL_PROFIT_SOLD_KEY].add(ticker)
                else:
                    partials.append(f"⚠️ Partial sell failed for {ticker}: {result.get('error', '')}")

    for p in partials:
        log.append(p)
    if not partials:
        log.append("No positions hit +4% for partial profit yet")

    # ── 3. Check existing positions — sell if signal turned bad ──
    sells = []
    for pos in positions:
        try:
            data = fetch_scan(pos["ticker"])
            if not data:
                continue
            sig = generate_trade_signal(data)
            if sig["score"] <= SELL_BELOW or sig["action"] in ("SELL", "STRONG_SELL"):
                if dry_run:
                    sells.append(f"🔴 Would sell {pos['ticker']} — score {sig['score']}, signal: {sig['action']}")
                else:
                    result = alpaca_sell(ticker=pos["ticker"], sell_all=True)
                    if result.get("ok"):
                        sells.append(f"🔴 Sold {pos['ticker']} — score dropped to {sig['score']}, signal: {sig['action']}")
                    else:
                        sells.append(f"⚠️ Tried to sell {pos['ticker']} but failed: {result.get('error','')}")
        except Exception:
            continue

    for s in sells:
        log.append(s)
    if not sells:
        log.append("All positions still healthy — no sells needed")

    # ── 4. Scan for new opportunities ──
    open_slots = MAX_POSITIONS - (len(positions) - len(sells))
    if open_slots <= 0 and not dry_run:
        log.append(f"Max positions ({MAX_POSITIONS}) reached — skipping scan")
        return {"ok": True, "log": log, "buys": 0, "sells": len(sells)}
    if open_slots <= 0 and dry_run:
        open_slots = MAX_POSITIONS  # show what we'd buy if we had room
        log.append(f"Max positions reached — but scanning anyway (dry run)")

    if account["buying_power"] < 100 and not dry_run:
        log.append("Not enough buying power — skipping scan")
        return {"ok": True, "log": log, "buys": 0, "sells": len(sells)}

    if no_new_buys_eod and not dry_run:
        log.append("⏰ Last 30min of trading — no new buys, managing existing only")
        return {"ok": True, "log": log, "buys": 0, "sells": len(sells), "scanned": 0, "opportunities": 0}

    # Gate: don't buy in bear markets
    if not regime["safe_to_buy"]:
        log.append("Skipped scan — waiting for better market conditions")
        return {"ok": True, "log": log, "buys": 0, "sells": len(sells), "scanned": 0, "opportunities": 0}

    # ── 4. Scan for new opportunities ──
    # Step A: Use Polygon to pre-screen the ENTIRE market in one API call
    # Then only deep-analyze the top candidates (saves 30+ min vs scanning all 500)
    log.append("Pre-screening entire US market via Polygon...")

    candidates = []

    # Get top gainers — stocks with momentum today
    gainers = polygon_gainers(limit=20) or []
    # Get all snapshots for broader view
    all_snaps = polygon_all_snapshots() or []

    if all_snaps:
        # Filter to real stocks: price > $5, volume > 200k
        viable = [s for s in all_snaps if s.get("Price", 0) > 5 and s.get("Volume", 0) > 200_000]
        # Sort by absolute daily change — we want movers
        movers = sorted(viable, key=lambda x: abs(x.get("Chg%", 0)), reverse=True)[:80]
        # Also get positive movers separately
        positive = sorted([s for s in viable if s.get("Chg%", 0) > 0.5], key=lambda x: x["Chg%"], reverse=True)[:40]

        seen = set()
        for s in positive + movers:
            t = s["Ticker"]
            if t not in seen and t not in held_tickers:
                seen.add(t)
                candidates.append(t)

        log.append(f"Polygon found {len(viable)} viable stocks → narrowed to {len(candidates)} candidates")

    # Fallback: full S&P 500 + Russell growth + popular mid/small caps
    if len(candidates) < 30:
        FULL_UNIVERSE = [
            # ── S&P 500 (all sectors) ──
            "AAPL","MSFT","AMZN","NVDA","GOOGL","GOOG","META","BRK-B","LLY","AVGO",
            "TSLA","JPM","UNH","V","XOM","MA","JNJ","PG","HD","COST",
            "ABBV","MRK","CVX","CRM","NFLX","AMD","PEP","KO","ADBE","WMT",
            "TMO","BAC","LIN","CSCO","MCD","ACN","ABT","DHR","WFC","ORCL",
            "PM","TXN","GE","CMCSA","INTU","DIS","ISRG","VZ","AMGN","IBM",
            "NOW","PFE","QCOM","UBER","CAT","AMAT","GS","BKNG","BLK","AXP",
            "T","MS","LOW","SPGI","RTX","MDLZ","ELV","BA","HON","SYK",
            "LRCX","PLD","NEE","TJX","VRTX","DE","C","BSX","SCHW","ADI",
            "SNPS","CDNS","INTC","CME","SO","CB","ICE","CL","SHW","DUK",
            "ABNB","PYPL","MO","PNC","EQIX","CTAS","TT","HUM","MCK","AON",
            "MAR","USB","APD","ECL","WM","ORLY","PSX","CMG","ITW","GD",
            "COF","MELI","EMR","CCI","MSI","SLB","NXPI","PH","VLO","CRWD",
            "GM","RCL","AIG","EW","CARR","AEP","MPC","NUE","PCAR","FTNT",
            "FDX","MNST","WELL","AZO","D","AFL","KMB","HLT","F","TFC",
            "O","ROST","PRU","SRE","DLR","BK","STZ","PAYX","CNC","IQV",
            "ALL","FAST","CPRT","TEL","KHC","OXY","SPG","MSCI","MCHP","AME",
            "OTIS","A","GWW","PCG","DHI","KR","LHX","CTVA","HSY","YUM",
            "EA","FANG","EXC","DD","ED","AVB","VRSK","XEL","PPG","WBD",
            "AMP","MLM","MTB","WEC","CBRE","IDXX","RMD","EFX","DOW","GEHC",
            "ACGL","TSCO","IR","HIG","CDW","WAB","KEYS","BRO","RJF","IFF",
            "TDG","WST","TRGP","STE","ROK","DECK","CAH","EQR","VLTO","EBAY",
            "NDAQ","ZBRA","POOL","HOLX","MPWR","ENTG","TER","SWKS","ALGN","GNRC",
            "WRB","TYL","MOH","TTWO","PODD","FICO","LPLA","HUBB","FTV","PTC",
            "NTAP","SMCI","TRMB","DPZ","BALL","CFG","HBAN","RF","KEY","CINF",
            "LUV","DAL","UAL","AAL","ALK","JBLU",
            "EQT","RRC","AR","SWN","CTRA",
            # ── Mid-cap growth ──
            "AXON","HIMS","CAVA","DUOL","CELH","ELF","ONON","TOST","BROS","DDOG",
            "DAVA","HUBS","ESTC","FROG","MANH","ROKU","TTD","SNAP","PINS","MTCH",
            "CHWY","ETSY","W","OPEN","ZG","CVNA","DASH","GRAB","SE",
            # ── Small-cap / speculative ──
            "UPST","AFRM","RKLB","SOUN","ASTS","LUNR","JOBY","BBAI","AEHR",
            "MARA","RIOT","CLSK","IREN","BTBT","CIFR","HUT","CORZ",
            "QS","MVST","BLDP","PLUG","FCEL","BE","CHPT","EVGO","BLNK",
            "IONQ","RGTI","QUBT","ARQQ",
            "SOFI","HOOD","LMND","ROOT","OSCR","RELY",
            "PLTR","SMCI","ARM",
            # ── Sector plays ──
            "FSLR","ENPH","CEG","VST","SMR","OKLO","NNE","LEU",
            "LMT","RTX","KTOS","RCAT","AVAV","BWXT","HII","NOC","GD","LHX",
            "COIN","MSTR","MARA","RIOT","CLSK",
            "NET","ZS","CRWD","PANW","FTNT","CYBR","QLYS","TENB","RPD","S",
            "ARGX","MRNA","BNTX","REGN","VRTX","ALNY","BMRN","RARE","NBIX","PCVX",
            # ── Dividend / value ──
            "O","STAG","NNN","AGNC","NLY","ARCC","MAIN","TPVG",
            "EPD","ET","WES","MPLX","PAA","OKE","KMI","WMB",
            "VALE","FCX","NUE","CLF","STLD","RS","ATI",
            "MOS","NTR","CF","FMC","IPI",
            # ── International ADRs ──
            "BABA","JD","PDD","BIDU","NIO","XPEV","LI","TME","BILI","IQ",
            "TSM","ASML","SAP","TM","SONY","NVO","AZN","SNY","GSK","DEO",
            "MELI","NU","GLOB","DLO","STNE",
            "SE","GRAB","CPNG","BEKE",
        ]
        fallback = [t for t in FULL_UNIVERSE if t not in held_tickers and t not in set(candidates)]
        random.shuffle(fallback)
        candidates.extend(fallback[:200])
        log.append(f"Added full universe fallback → total {len(candidates)} candidates")

    scan_list = candidates
    log.append(f"Deep-analyzing {len(scan_list)} stocks...")

    opportunities = []
    all_scores = []
    analyzed = 0
    errors = 0
    MAX_ANALYZE = 200
    for ticker in scan_list[:MAX_ANALYZE]:
        try:
            data = fetch_scan(ticker)
            if not data:
                errors += 1
                continue
            price = data.get("price", 0)
            if not price or price < 2:
                continue
            analyzed += 1
            sig = generate_trade_signal(data)
            all_scores.append((ticker, sig["score"], sig["action"], sig["confluence"]["bullish"], sig["trade"]["risk_reward"]))

            if (sig["score"] >= MIN_SCORE
                    and sig["confluence"]["bullish"] >= MIN_CONFLUENCE
                    and sig["trade"]["risk_reward"] >= MIN_RR
                    and sig["action"] in ("BUY", "STRONG_BUY")):
                opportunities.append({
                    "ticker": ticker,
                    "score": sig["score"],
                    "action": sig["action"],
                    "confluence": sig["confluence"]["bullish"],
                    "rr": sig["trade"]["risk_reward"],
                    "signal": sig,
                    "data": data,
                })
                if len(opportunities) >= open_slots + 5:
                    log.append(f"Found {len(opportunities)} opportunities — stopping early")
                    break
        except Exception:
            errors += 1
            continue

    log.append(f"Analyzed {analyzed} stocks ({errors} failed to fetch)")

    # Show top 10 scores regardless of whether they qualified
    all_scores.sort(key=lambda x: x[1], reverse=True)
    top_10 = all_scores[:10]
    log.append("**Top 10 scores found:**")
    for t, s, a, c, rr in top_10:
        passed = "✓" if s >= MIN_SCORE and c >= MIN_CONFLUENCE and rr >= MIN_RR else "✗"
        log.append(f"{passed} {t}: score {s}, {a}, {c} bullish, R:R {rr:.1f}")

    # Sort: STRONG_BUY first, then BUY, then HOLD — within each group by score
    action_priority = {"STRONG_BUY": 0, "BUY": 1, "HOLD": 2}
    opportunities.sort(key=lambda x: (action_priority.get(x["action"], 3), -x["score"]))

    if not opportunities:
        log.append("No stocks passed the criteria (score≥68, BUY/STRONG_BUY, confluence≥3, R:R≥2.0)")
        return {"ok": True, "log": log, "buys": 0, "sells": len(sells), "scanned": analyzed}

    log.append(f"Found {len(opportunities)} opportunities — executing top {min(open_slots, len(opportunities))}")

    # ── 5. Execute trades on best opportunities ──
    buys = []
    for opp in opportunities[:open_slots]:
        ticker = opp["ticker"]
        sig = opp["signal"]
        trade = sig["trade"]

        # Earnings check — skip stocks reporting within 7 days
        has_earnings, earn_date = _has_upcoming_earnings(ticker, days=7)
        if has_earnings:
            log.append(f"⏭️ Skipped {ticker} — earnings on {earn_date}")
            continue

        # News check — skip if headlines are very bearish
        opp_news = opp["data"].get("news_sentiment", {})
        if opp_news.get("sentiment") == "very_bearish":
            log.append(f"⏭️ Skipped {ticker} — very bearish news ({opp_news.get('bearish_count', 0)} negative headlines)")
            continue

        entry = trade["entry"]
        stop = trade["stop_loss"]
        target = trade["target_1"]

        if entry <= stop:
            continue

        # Position sizing: risk X% of equity
        risk_per_share = entry - stop
        max_risk_dollars = account["equity"] * RISK_PER_TRADE
        qty = max(1, int(max_risk_dollars / risk_per_share))

        # Cap at MAX_POS_PCT of equity
        max_qty = int(account["equity"] * MAX_POS_PCT / entry)
        qty = min(qty, max_qty)

        # Cap at buying power
        max_qty_bp = int(account["buying_power"] * 0.90 / entry)
        qty = min(qty, max_qty_bp)

        if qty < 1:
            continue

        cost = qty * entry
        if dry_run:
            buys.append(f"🟢 Would buy {qty} {ticker} @ ~${entry:.2f} · Stop ${stop:.2f} · Target ${target:.2f} · Score {opp['score']} · R:R {opp['rr']:.1f}:1")
            account["buying_power"] -= cost
        else:
            result = alpaca_buy(ticker=ticker, qty=qty, stop_loss=stop, take_profit=target)

            if result.get("ok"):
                buys.append(f"🟢 Bought {qty} {ticker} @ ~${entry:.2f} · Stop ${stop:.2f} · Target ${target:.2f} · Score {opp['score']} · R:R {opp['rr']:.1f}:1")
                st.session_state.setdefault("autopilot_bought", set()).add(ticker)
                account["buying_power"] -= cost
            else:
                buys.append(f"⚠️ Failed to buy {ticker}: {result.get('error','')}")

    for b in buys:
        log.append(b)

    return {
        "ok": True,
        "log": log,
        "buys": sum(1 for b in buys if b.startswith("🟢")),
        "sells": len(sells),
        "scanned": analyzed,
        "opportunities": len(opportunities),
    }


def execute(intent: dict) -> dict:
    t = intent["type"]
    market = intent.get("market", "US")

    if t == "force_scan":
        result = run_autopilot(skip_market_check=True, dry_run=True)
        if not result.get("ok"):
            return {"ok": False, "error": result.get("error", "Scan failed")}
        report_lines = result["log"]
        summary = (
            f"**🔍 Market Scan (dry run — no trades placed)**\n\n"
            f"Scanned: {result.get('scanned', '?')} stocks · "
            f"Found: {result.get('opportunities', 0)} opportunities\n\n"
            f"---\n\n" +
            "\n\n".join(report_lines)
        )
        return {"ok": True, "type": "trade", "msg": summary}

    # ── Autopilot ──
    if t == "autopilot":
        st.session_state["autopilot_active"] = True
        result = run_autopilot()
        if not result.get("ok"):
            return {"ok": False, "error": result.get("error", "Autopilot failed")}
        report_lines = result["log"]
        summary = (
            f"**🟢 Autopilot Active — Running Continuously**\n\n"
            f"Scanned: {result.get('scanned', '?')} stocks · "
            f"Found: {result.get('opportunities', 0)} opportunities · "
            f"Bought: {result.get('buys', 0)} · Sold: {result.get('sells', 0)}\n\n"
            f"*Next scan in 10 minutes. Say \"stop\" to deactivate.*\n\n"
            f"---\n\n" +
            "\n\n".join(report_lines)
        )
        return {"ok": True, "type": "trade", "msg": summary}

    if t == "stop_autopilot":
        st.session_state["autopilot_active"] = False
        return {"ok": True, "type": "trade", "msg": "🔴 **Autopilot deactivated.** No more automatic scans. Your positions remain open."}

    if t == "backtest":
        result = run_backtest(years=2)
        if not result.get("ok"):
            return {"ok": False, "error": "Backtest failed"}
        summary = "\n\n".join(result["log"])
        return {"ok": True, "type": "trade", "msg": summary}

    if t == "market_regime":
        regime = check_market_regime()
        safe = "✅ Safe to buy" if regime["safe_to_buy"] else "⛔ Not safe to buy"
        msg = (
            f"**Market Regime Check**\n\n"
            f"Regime: **{regime['regime']}** · {safe}\n\n"
            f"{regime['reason']}\n\n"
            f"SPY: ${regime.get('spy_price', '?')} · 50 SMA: ${regime.get('sma_50', '?')} · 200 SMA: ${regime.get('sma_200', '?')} · RSI: {regime.get('rsi', '?')}"
        )
        return {"ok": True, "type": "trade", "msg": msg}

    if t == "sector_strength":
        sectors = _get_sector_strength()
        if not sectors:
            return {"ok": False, "error": "Could not fetch sector data"}
        ranked = sorted(sectors.items(), key=lambda x: x[1].get("rank", 99))
        lines = ["**Sector Rotation Rankings**\n"]
        for etf, data in ranked:
            rank = data["rank"]
            emoji = "🟢" if rank <= 3 else ("🟡" if rank <= 6 else "🔴")
            lines.append(f"{emoji} #{rank} **{data['name']}** ({etf}) — 1w: {data['1w']:+.1f}% · 1m: {data['1m']:+.1f}%")
        lines.append(f"\nAutopilot prioritizes stocks in top 3 sectors and avoids bottom 3.")
        return {"ok": True, "type": "trade", "msg": "\n\n".join(lines)}

    # ── Trading commands ──
    if t == "portfolio":
        acc = alpaca_account()
        if not acc:
            return {"ok": False, "error": "Could not connect to Alpaca. Check API keys."}
        arrow = "▲" if acc["daily_pnl"] >= 0 else "▼"
        msg = (
            f"**Portfolio**\n\n"
            f"Equity: `${acc['equity']:,.2f}`\n\n"
            f"Cash: `${acc['cash']:,.2f}` · Buying Power: `${acc['buying_power']:,.2f}`\n\n"
            f"Today: `{arrow} ${acc['daily_pnl']:+,.2f}` ({acc['daily_pnl_pct']:+.2f}%)\n\n"
            f"Long: `${acc['long_market_value']:,.2f}` · Status: {acc['status']}"
        )
        return {"ok": True, "type": "portfolio", "msg": msg, "data": acc, "show_portfolio_chart": True}

    if t == "positions":
        positions = alpaca_positions()
        if not positions:
            return {"ok": True, "type": "positions", "msg": "No open positions.", "data": []}
        table = []
        total_pnl = 0
        for p in positions:
            arrow = "▲" if p["unrealized_pnl"] >= 0 else "▼"
            table.append({
                "Ticker": p["ticker"],
                "Qty": int(p["qty"]),
                "Entry": f"${p['avg_entry']:.2f}",
                "Now": f"${p['current_price']:.2f}",
                "P&L": f"{arrow} ${p['unrealized_pnl']:+,.2f}",
                "P&L%": f"{p['unrealized_pnl_pct']:+.1f}%",
            })
            total_pnl += p["unrealized_pnl"]
        arrow = "▲" if total_pnl >= 0 else "▼"
        msg = f"**Open Positions** ({len(positions)}) · Total P&L: `{arrow} ${total_pnl:+,.2f}`"
        return {"ok": True, "type": "list", "title": "Positions", "msg": msg, "data": table}

    if t == "orders":
        orders = alpaca_orders(status="all", limit=15)
        if not orders:
            return {"ok": True, "type": "orders", "msg": "No recent orders."}
        table = []
        for o in orders:
            table.append({
                "Symbol": o["symbol"],
                "Side": o["side"].upper(),
                "Qty": o["qty"],
                "Type": o["type"],
                "Status": o["status"],
                "Filled@": o["filled_avg"],
                "Time": o["submitted"],
            })
        return {"ok": True, "type": "list", "title": "Recent Orders", "msg": "**Recent Orders**", "data": table}

    if t == "close_all":
        result = alpaca_close_all()
        if result["ok"]:
            return {"ok": True, "type": "trade", "msg": "🔴 **All positions closed.** Portfolio is flat."}
        return {"ok": False, "error": result.get("error", "Failed to close all")}

    if t == "buy":
        ticker = intent["ticker"]
        qty = intent.get("qty")
        notional = intent.get("notional")
        result = alpaca_buy(ticker=ticker, qty=qty, notional=notional)
        if result["ok"]:
            qty_str = f"{result['qty']} shares" if result.get("qty") else f"${notional}"
            return {"ok": True, "type": "trade",
                    "msg": f"🟢 **Bought {qty_str} of {ticker.upper()}** · Status: {result['status']}"}
        return {"ok": False, "error": f"Buy failed: {result.get('error', 'Unknown')}"}

    if t == "sell":
        ticker = intent["ticker"]
        sell_all = intent.get("sell_all", False)
        qty = intent.get("qty")
        result = alpaca_sell(ticker=ticker, qty=qty, sell_all=sell_all)
        if result["ok"]:
            action = "Closed position in" if sell_all else f"Sold {qty or result.get('qty', '')} shares of"
            return {"ok": True, "type": "trade",
                    "msg": f"🔴 **{action} {ticker.upper()}** · Status: {result.get('status', 'submitted')}"}
        return {"ok": False, "error": f"Sell failed: {result.get('error', 'Unknown')}"}

    if t == "smart_buy":
        ticker = intent["ticker"]
        # First analyze the stock
        data = fetch_full(ticker)
        if not data:
            return {"ok": False, "error": f"No data for {ticker}."}
        signal = generate_trade_signal(data)
        if signal["action"] not in ("BUY", "STRONG_BUY"):
            return {"ok": True, "type": "analysis", "ticker": ticker, "market": market,
                    "data": {**data, **signal}, "trade_signal": signal,
                    "msg": f"⚠️ Signal is **{signal['action']}** (score: {signal['score']}). Not executing — doesn't meet buy criteria."}
        # Execute the smart buy
        result = alpaca_smart_buy(ticker=ticker, trade_signal=signal)
        if result["ok"]:
            msg = (
                f"🟢 **Smart buy executed: {result.get('qty_calculated', '?')} shares of {ticker.upper()}**\n\n"
                f"Cost: ~`${result.get('cost_estimate', 0):,.2f}` · "
                f"Stop: `${result.get('stop_loss', 0):.2f}` · "
                f"Target: `${result.get('take_profit', 0):.2f}`\n\n"
                f"Risk: `${result.get('total_risk', 0):,.2f}` ({signal['trade']['risk_pct']:.1f}% per share) · "
                f"R:R `{signal['trade']['risk_reward']:.1f}:1`"
            )
            return {"ok": True, "type": "trade", "ticker": ticker, "msg": msg, "trade_signal": signal}
        return {"ok": False, "error": f"Smart buy failed: {result.get('error', 'Unknown')}"}

    # ── Standard commands ──
    if t == "price":
        tick = _ensure_suffix(intent["ticker"], market)
        data = fetch_price(tick)
        if not data:
            return {"ok": False, "error": f"No data for {intent['ticker']}."}
        sym = "$" if market == "US" else "₹"
        arrow = "▲" if data["change_pct"] >= 0 else "▼"
        return {"ok": True, "type": "price", "market": market, "ticker": tick, "data": data,
                "msg": f"**{data['name']}** ({intent['ticker']})\n\n`{sym}{data['price']:,.2f}` {arrow} {data['change_pct']:+.2f}%"}

    if t == "analyze":
        tick = _ensure_suffix(intent["ticker"], market)
        data = fetch_full(tick)
        if not data:
            return {"ok": False, "error": f"No data for {intent['ticker']}."}
        signal = generate_trade_signal(data)
        return {"ok": True, "type": "analysis", "ticker": tick, "market": market, "data": {**data, **signal}, "trade_signal": signal}

    if t in ("gainers", "losers", "hot"):
        results = None

        # ── Try Polygon first: scans the ENTIRE market in one API call ──
        if market != "India":
            if t == "gainers":
                results = polygon_gainers(limit=20)
                title = "Top Gainers"
            elif t == "losers":
                results = polygon_losers(limit=20)
                title = "Top Losers"
            else:
                # Hot/movers: get all snapshots and sort by absolute change
                all_snaps = polygon_all_snapshots()
                if all_snaps:
                    results = sorted(all_snaps, key=lambda x: abs(x["Chg%"]), reverse=True)[:20]
                title = "Biggest Movers"

            # Filter: only stocks with real volume and price > $1
            if results:
                results = [r for r in results if r.get("Price", 0) > 1][:15]

        # ── Fallback to yfinance scanning if Polygon fails ──
        if not results:
            if market == "India":
                pool = NIFTY_50
            else:
                mega = random.sample(NASDAQ_100, min(15, len(NASDAQ_100)))
                mid = random.sample(MIDCAP_GROWTH, min(12, len(MIDCAP_GROWTH)))
                small = random.sample(SMALLCAP, min(10, len(SMALLCAP)))
                trending = TRENDING[:15] if t == "hot" else []
                val = random.sample(VALUE_DIVIDEND, min(5, len(VALUE_DIVIDEND))) if t != "hot" else []
                sect = random.sample(SECTOR_PICKS, min(8, len(SECTOR_PICKS)))
                seen = set()
                pool = []
                for s in trending + mega + mid + small + val + sect:
                    if s not in seen:
                        seen.add(s)
                        pool.append(s)
            results = []
            for s in pool[:50]:
                d = fetch_price(s)
                if d:
                    results.append({"Ticker": s.replace(".NS", ""), "Price": d["price"], "Chg%": d["change_pct"]})
            if t == "gainers":
                results = sorted([r for r in results if r["Chg%"] > 0], key=lambda x: x["Chg%"], reverse=True)[:10]
                title = "Top Gainers"
            elif t == "losers":
                results = sorted([r for r in results if r["Chg%"] < 0], key=lambda x: x["Chg%"])[:10]
                title = "Top Losers"
            else:
                results = sorted(results, key=lambda x: abs(x["Chg%"]), reverse=True)[:12]
                title = "Biggest Movers"

        return {"ok": True, "type": "list", "title": title, "data": results or [], "market": market}

    return {"ok": False, "type": "chat"}


# ── AI response ──────────────────────────────────────────────────────────────

def ai_response(user_msg: str, stock_data: dict | None, history: list, market: str) -> str:
    key = st.secrets.get("GROQ_API_KEY") or os.environ.get("GROQ_API_KEY")
    if not key:
        return "⚠️ Set `GROQ_API_KEY` in Streamlit secrets or environment."

    system = f"""You're Paula — think of yourself as that one friend who's weirdly obsessed with the stock market and actually knows what she's talking about. You talk like a real person, not a Bloomberg terminal. Today is {datetime.now().strftime("%Y-%m-%d")}. Market: {market}.

You get live stock data attached to each message. This includes a full trade signal with confluence scoring across 6 categories (trend, momentum, mean-reversion, volume, fundamentals, news sentiment), trend regime detection, support/resistance levels, and ATR-based entry/stop/target with risk-reward ratios. USE all of it — that's what makes you useful — but weave the numbers into natural conversation.

IMPORTANT: This is a DAY TRADING setup. Positions are opened and closed within the same trading day. Stops are tight (1.5x ATR), targets are close (2:1 R:R), and everything gets liquidated 15 minutes before market close. Keep this context when discussing trades — don't talk about "holding for weeks" or "long-term potential".

CRITICAL — Stock recommendations:
When asked to suggest, name, or recommend stocks, NEVER just list the same boring mega-caps everyone already knows (AAPL, MSFT, GOOGL, AMZN, TSLA, etc.). Anyone can name those. Instead:
- Mix market caps: include mid-caps ($2B-$20B) and small-caps (<$2B) alongside any large-caps
- Think across sectors: biotech, space, fintech, clean energy, cybersecurity, defense, materials, not just Big Tech
- Include high-growth disruptors: companies like HIMS, CAVA, DUOL, CELH, AXON, UPST, LUNR, RKLB, TOST, ONON
- Include value/dividend plays when relevant: O, EPD, STAG, NUE, FCX
- Include sector specialists: FSLR (solar), SMR (nuclear), KTOS (defense drones), RXRX (AI drug discovery)
- If someone asks for "10 stocks" give them a MIX — maybe 2 large-cap, 4 mid-cap, 3 small-cap, 1 speculative
- Explain WHY each pick is interesting — don't just list tickers
- The goal is to surface opportunities people haven't already heard of a thousand times

How you talk:
- Like you're texting a friend who asked "hey should I buy this?" — direct, opinionated, casual
- Lead with your gut take, THEN back it up with data. "Honestly this looks pretty solid right now" before diving into numbers
- Use the score naturally: "I'd give this a 72 — solidly in buy territory" not "Score: 72/100 — BUY"
- Mix short punchy sentences with longer explanations. Vary your rhythm
- Say "look" or "here's the thing" or "what I like about this" — real human transitions
- It's okay to be excited about a good setup or blunt about a bad one
- ALWAYS include the concrete trade plan — entry, stop-loss, targets, risk-reward — but frame it naturally: "If I were getting in, I'd look around $X with a stop at $Y, first target $Z — that's a 2:1 risk-reward which I like"
- Mention the trend regime and what it means: "we're in a strong uptrend with ADX at 32, so buying dips makes sense here"
- Call out confluence: "4 out of 6 categories are bullish which is rare — this has conviction"
- Mention news sentiment when it's strong: "headlines are running hot right now — 5 bullish articles in the last few days" or "news flow is ugly, lot of negative press"
- Mention key S/R levels traders need: "watching support at $X and resistance at $Y"
- If signals conflict, be honest: "momentum looks great but volume isn't confirming, which bugs me"

What to avoid:
- NEVER default to just listing AAPL, MSFT, GOOGL, AMZN, META, TSLA when recommending stocks
- Never start with "Based on the data" or "Let me analyze" — just jump in
- No robotic headers like "VERDICT:" or "RISK ASSESSMENT:"
- Don't disclaim you're an AI or say "not financial advice" — the app has that
- Never say you don't have data. You do
- Don't pad with filler or repeat points in different words

For simple price checks: 1–2 sentences max.
For general chat: be friendly, no need to force stock talk.
For full analysis: go deep but stay conversational. 2–3 natural paragraphs. Always close with the trade plan numbers."""

    messages = [{"role": "system", "content": system}]
    for h in history[-8:]:
        messages.append({"role": h["role"], "content": h["content"]})
    content = user_msg
    if stock_data:
        content += f"\n\n---DATA---\n{json.dumps(stock_data, indent=2, default=str)}"
    messages.append({"role": "user", "content": content})

    try:
        client = Groq(api_key=key)
        resp = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=messages, max_tokens=1800, temperature=0.72)
        return resp.choices[0].message.content
    except Exception as e:
        return f"⚠️ AI error: {str(e)[:120]}"


# ── UI ───────────────────────────────────────────────────────────────────────

def main():
    st.set_page_config(page_title="Paula", page_icon="◉", layout="wide", initial_sidebar_state="collapsed")

    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@300;400;500;600&display=swap');

    :root {
        --bg:       #0a0a0b;
        --surface:  #111113;
        --surface2: #19191d;
        --border:   #222228;
        --muted:    #555566;
        --text:     #b0b0be;
        --bright:   #e8e8f0;
        --green:    #00d4aa;
        --red:      #ff4d6a;
        --amber:    #f0b232;
        --blue:     #4d94ff;
    }

    .stApp { background: var(--bg) !important; }
    header, footer, #MainMenu, .stDeployButton { visibility: hidden !important; display: none !important; }

    .block-container {
        max-width: 780px !important;
        padding: 1.5rem 1.2rem 5rem 1.2rem !important;
    }

    /* ── Typography ── */
    h1,h2,h3 {
        font-family: 'IBM Plex Sans', sans-serif !important;
        color: var(--bright) !important;
        font-weight: 600 !important;
        letter-spacing: -0.03em !important;
    }
    p, span, div, label, li {
        font-family: 'IBM Plex Sans', sans-serif !important;
        color: var(--text) !important;
        line-height: 1.6 !important;
    }
    code, pre {
        font-family: 'IBM Plex Mono', monospace !important;
        background: var(--surface2) !important;
        color: var(--green) !important;
        border: none !important;
    }

    /* ── Kill the chatbot bubble look ── */
    .stChatMessage {
        background: transparent !important;
        border: none !important;
        border-radius: 0 !important;
        padding: 0.6rem 0 !important;
        border-bottom: 1px solid var(--border) !important;
        gap: 0.8rem !important;
    }
    /* Hide the avatar icons entirely */
    .stChatMessage [data-testid="chatAvatarIcon-user"],
    .stChatMessage [data-testid="chatAvatarIcon-assistant"] {
        background: var(--surface2) !important;
        border: 1px solid var(--border) !important;
        border-radius: 4px !important;
    }
    /* Tighten up message container */
    [data-testid="stChatMessageContent"] {
        padding: 0 !important;
    }

    .stChatMessage p, .stChatMessage span, .stChatMessage li {
        color: var(--text) !important;
        font-size: 0.92rem !important;
    }
    .stChatMessage strong, .stChatMessage b {
        color: var(--bright) !important;
        font-weight: 600 !important;
    }

    /* User messages — styled like terminal input */
    [data-testid="stChatMessage-user"] {
        border-bottom: none !important;
        padding: 0.4rem 0 0.2rem 0 !important;
    }
    [data-testid="stChatMessage-user"] p {
        color: var(--muted) !important;
        font-family: 'IBM Plex Mono', monospace !important;
        font-size: 0.85rem !important;
    }

    /* ── Input bar — command prompt style ── */
    .stChatInput > div > div > textarea,
    .stTextInput > div > div > input {
        background: var(--surface) !important;
        border: 1px solid var(--border) !important;
        border-radius: 6px !important;
        color: var(--bright) !important;
        font-family: 'IBM Plex Mono', monospace !important;
        font-size: 0.88rem !important;
        padding: 0.8rem 1rem !important;
    }
    .stChatInput > div > div > textarea:focus {
        border-color: var(--green) !important;
        box-shadow: 0 0 0 1px rgba(0,212,170,0.2) !important;
    }
    .stChatInput > div > div > textarea::placeholder {
        color: var(--muted) !important;
        font-family: 'IBM Plex Mono', monospace !important;
    }

    /* ── Send button ── */
    .stChatInput button {
        background: var(--green) !important;
        border: none !important;
        border-radius: 6px !important;
    }
    .stChatInput button svg { color: var(--bg) !important; }

    /* ── Data tables — terminal grid look ── */
    .stDataFrame { border-radius: 4px !important; overflow: hidden !important; }
    .stDataFrame td, .stDataFrame th {
        background: var(--surface) !important;
        color: var(--text) !important;
        border-color: var(--border) !important;
        font-family: 'IBM Plex Mono', monospace !important;
        font-size: 0.8rem !important;
        padding: 0.4rem 0.8rem !important;
    }
    .stDataFrame th {
        color: var(--muted) !important;
        font-weight: 500 !important;
        text-transform: uppercase !important;
        font-size: 0.7rem !important;
        letter-spacing: 0.05em !important;
    }

    /* ── Dividers ── */
    hr { border-color: var(--border) !important; margin: 0.6rem 0 !important; }

    /* ── Caption ── */
    .stCaption p {
        color: var(--muted) !important;
        font-size: 0.72rem !important;
        font-family: 'IBM Plex Mono', monospace !important;
        letter-spacing: 0.02em !important;
    }

    /* ── Plotly ── */
    .js-plotly-plot .plotly .modebar { display: none !important; }

    /* ── Spinner ── */
    .stSpinner > div { border-top-color: var(--green) !important; }

    /* ── Scrollbar ── */
    ::-webkit-scrollbar { width: 5px; }
    ::-webkit-scrollbar-track { background: transparent; }
    ::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }
    ::-webkit-scrollbar-thumb:hover { background: var(--muted); }

    /* ── Lists in messages — cleaner ── */
    .stChatMessage ol, .stChatMessage ul {
        padding-left: 1.2rem !important;
        margin: 0.4rem 0 !important;
    }
    .stChatMessage li {
        margin-bottom: 0.3rem !important;
        padding-left: 0.2rem !important;
    }
    .stChatMessage li::marker {
        color: var(--muted) !important;
    }
    </style>
    """, unsafe_allow_html=True)

    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Header — minimal, not chatbot-y
    st.markdown("## Paula")
    st.caption(f"analysis + paper trading · {datetime.now().strftime('%b %d, %Y')}")
    st.markdown("---")

    for mi, m in enumerate(st.session_state.messages):
        av = "🟢" if m["role"] == "assistant" else "⬛"
        with st.chat_message(m["role"], avatar=av):
            st.markdown(m["content"])
            if m["role"] == "assistant" and m.get("chart"):
                fig = build_chart(m["chart"], trade_signal=m.get("trade_signal"))
                if fig:
                    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False}, key=f"chart_hist_{mi}")
            if m["role"] == "assistant" and m.get("table"):
                st.dataframe(pd.DataFrame(m["table"]), width="stretch", hide_index=True, key=f"table_hist_{mi}")
            if m["role"] == "assistant" and m.get("portfolio_chart"):
                hist = alpaca_portfolio_history(period="1M")
                pfig = build_portfolio_chart(hist)
                if pfig:
                    st.plotly_chart(pfig, width="stretch", config={"displayModeBar": False}, key=f"pchart_hist_{mi}")

    prompt = st.chat_input("NVDA… buy 10 AAPL… portfolio… top gainers…",
                           disabled=st.session_state.get("processing", False))
    if not prompt:
        _run_autopilot_loop()
        return

    st.session_state["processing"] = True
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="⬛"):
        st.markdown(prompt)

    with st.chat_message("assistant", avatar="🟢"):
        with st.spinner(""):
            intent = route(prompt)
            result = execute(intent)
            chart_ticker, table_data, trade_signal = None, None, None
            portfolio_chart = False
            market = result.get("market", intent.get("market", "US"))

            if result.get("ok"):
                if result["type"] == "price":
                    chart_ticker = result["ticker"]
                    resp = result["msg"]
                elif result["type"] == "analysis":
                    chart_ticker = result.get("ticker")
                    trade_signal = result.get("trade_signal")
                    if result.get("msg"):
                        resp = result["msg"]
                    else:
                        resp = ai_response(prompt, result["data"], st.session_state.messages, market)
                elif result["type"] == "list":
                    table_data = result["data"]
                    resp = result.get("msg", f"**{result.get('title', '')}** — {market} market")
                elif result["type"] in ("portfolio", "trade", "positions", "orders"):
                    resp = result.get("msg", "Done.")
                    chart_ticker = result.get("ticker")
                    trade_signal = result.get("trade_signal")
                    portfolio_chart = result.get("show_portfolio_chart", False)
                else:
                    resp = ai_response(prompt, None, st.session_state.messages, market)
            elif result.get("error"):
                resp = f"⚠️ {result['error']}"
            else:
                resp = ai_response(prompt, None, st.session_state.messages, market)

            st.markdown(resp)

            if chart_ticker:
                fig = build_chart(chart_ticker, trade_signal=trade_signal)
                if fig:
                    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False}, key="chart_new")

            if portfolio_chart:
                hist = alpaca_portfolio_history(period="1M")
                pfig = build_portfolio_chart(hist)
                if pfig:
                    st.plotly_chart(pfig, width="stretch", config={"displayModeBar": False}, key="portfolio_chart_new")

            if table_data:
                df = pd.DataFrame(table_data)
                # Format market data columns if they exist
                sym = "₹" if market == "India" else "$"
                if "Price" in df.columns:
                    df["Price"] = df["Price"].apply(lambda x: f"{sym}{x:,.2f}" if isinstance(x, (int, float)) else x)
                if "Chg%" in df.columns:
                    df["Chg%"] = df["Chg%"].apply(lambda x: f"{'▲' if x>=0 else '▼'} {x:+.2f}%" if isinstance(x, (int, float)) else x)
                if "Volume" in df.columns:
                    df["Volume"] = df["Volume"].apply(lambda x: f"{x/1e6:.1f}M" if isinstance(x, (int, float)) and x >= 1e6 else (f"{x/1e3:.0f}K" if isinstance(x, (int, float)) and x >= 1e3 else str(x)))
                st.dataframe(df, width="stretch", hide_index=True, key="table_new")

    st.session_state.messages.append({"role": "assistant", "content": resp, "chart": chart_ticker, "table": table_data, "trade_signal": trade_signal, "portfolio_chart": portfolio_chart})
    st.session_state["processing"] = False

    # ── Autopilot continuous loop ──
    _run_autopilot_loop()


def _run_autopilot_loop():
    """If autopilot is active, wait then scan again automatically."""
    if not st.session_state.get("autopilot_active", False):
        return

    # Check market hours first
    is_open, status_msg = _market_is_open()

    if not is_open:
        st.markdown(f"---\n\n⏸️ **Autopilot paused** · {status_msg}\n\nWill auto-resume when market opens. You can close this tab — positions are safe on Alpaca.")
        time.sleep(300)  # Check every 5 min if market has opened
        st.rerun()
        return

    INTERVAL = 10 * 60  # 10 minutes — day trading pace

    last_scan = st.session_state.get("autopilot_last_scan", 0)
    now = time.time()
    elapsed = now - last_scan

    if elapsed < INTERVAL and last_scan > 0:
        remaining = int(INTERVAL - elapsed)
        mins, secs = divmod(remaining, 60)
        st.markdown(f"---\n\n🟢 **Autopilot active** · Next scan in {mins}m {secs}s · Say \"stop\" to deactivate")
        time.sleep(min(60, remaining))
        st.rerun()
    else:
        st.session_state["autopilot_last_scan"] = now
        with st.chat_message("assistant", avatar="🟢"):
            with st.spinner("Autopilot scanning..."):
                result = run_autopilot()
                if result.get("market_closed"):
                    summary = "\n\n".join(result["log"])
                elif result.get("ok"):
                    report = result["log"]
                    summary = (
                        f"**🟢 Autopilot Scan Complete**\n\n"
                        f"Scanned: {result.get('scanned', '?')} · "
                        f"Found: {result.get('opportunities', 0)} · "
                        f"Bought: {result.get('buys', 0)} · Sold: {result.get('sells', 0)}\n\n"
                        f"*Next scan in 10 minutes.*\n\n---\n\n" +
                        "\n\n".join(report)
                    )
                else:
                    summary = f"⚠️ Autopilot error: {result.get('error', 'Unknown')}"
                st.markdown(summary)
                st.session_state.messages.append({"role": "assistant", "content": summary})
        time.sleep(60)
        st.rerun()


if __name__ == "__main__":
    main()
