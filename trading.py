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
from groq import Groq
from dotenv import load_dotenv
import os
import json
import re
import random
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
    "IOT","DOCS","PCOR","BRZE","SMAR","GTLB","DDOG","BILL","DOCN","ASAN",
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
    "DOW","LYB","NUE","CLF","X","AA","FCX","VALE","RIO","BHP",
]
# ── Sector-specific (energy, biotech, fintech, defense, space) ──
SECTOR_PICKS = [
    "FSLR","ENPH","SEDG","NEE","CEG","VST","SMR","NNE","OKLO","LEU",
    "LMT","RTX","NOC","GD","HII","KTOS","LDOS","BWXT","RCAT","PLTR",
    "SQ","AFRM","NU","STNE","PAGS","FOUR","RPAY","PSFE","NUVEI","ADYEY",
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
    "block":"SQ","square":"SQ","nu bank":"NU","realty income":"O",
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
#
#  Action fires only when enough categories agree (confluence).
#  Risk management: ATR-based entry / stop / targets with R:R.
# ═══════════════════════════════════════════════════════════════════════════════

def generate_trade_signal(data: dict) -> dict:
    tech = data.get("technicals", {})
    price = data.get("price", 0)
    if not price or not tech:
        return {"action": "NO_DATA", "confidence": 0}

    votes: dict[str, float] = {}
    signals: list[str] = []
    warnings: list[str] = []

    # ── 1. TREND (±30) ──
    regime = tech.get("trend_regime", "ranging")
    adx = _safe(tech.get("adx"), 0)
    slope = _safe(tech.get("trend_slope"), 0)
    trend_score = 0

    if regime == "strong_uptrend":
        trend_score += 20
        signals.append(f"Strong uptrend (ADX {adx}, slope +{slope:.1f}%)")
    elif regime == "strong_downtrend":
        trend_score -= 20
        warnings.append(f"Strong downtrend (ADX {adx}, slope {slope:.1f}%)")
    elif regime == "weak_trend":
        trend_score += 5 if slope > 0 else -5

    sma20, sma50, sma200 = _safe(tech.get("sma_20")), _safe(tech.get("sma_50")), _safe(tech.get("sma_200"))
    ma_above = sum(1 for ma in [sma20, sma50, sma200] if ma and price > ma)
    ma_total = sum(1 for ma in [sma20, sma50, sma200] if ma)
    ma_below = ma_total - ma_above

    if ma_above == 3:
        trend_score += 10
        signals.append("Price above all key MAs (20/50/200)")
    elif ma_above == 0 and ma_total >= 2:
        trend_score -= 10
        warnings.append("Price below all key MAs")
    else:
        trend_score += (ma_above - ma_below) * 3

    if tech.get("ma_cross") == "golden_cross":
        trend_score += 5
        signals.append("Golden cross (50 > 200 SMA)")
    elif tech.get("ma_cross") == "death_cross":
        trend_score -= 5
        warnings.append("Death cross (50 < 200 SMA)")

    votes["trend"] = max(-30, min(30, trend_score))

    # ── 2. MOMENTUM (±30) ──
    mom_score = 0
    rsi = _safe(tech.get("rsi"))
    if rsi is not None:
        if rsi < 25:
            mom_score += 12; signals.append(f"RSI deeply oversold ({rsi:.0f})")
        elif rsi < 35:
            mom_score += 6; signals.append(f"RSI in buy zone ({rsi:.0f})")
        elif rsi > 80:
            mom_score -= 12; warnings.append(f"RSI extremely overbought ({rsi:.0f})")
        elif rsi > 68:
            mom_score -= 5; warnings.append(f"RSI elevated ({rsi:.0f})")

    stoch_k, stoch_d = _safe(tech.get("stoch_rsi_k")), _safe(tech.get("stoch_rsi_d"))
    if stoch_k is not None and stoch_d is not None:
        if stoch_k < 20 and stoch_k > stoch_d:
            mom_score += 6; signals.append(f"StochRSI bullish cross in oversold ({stoch_k:.0f})")
        elif stoch_k > 80 and stoch_k < stoch_d:
            mom_score -= 6; warnings.append(f"StochRSI bearish cross in overbought ({stoch_k:.0f})")

    macd_h = _safe(tech.get("macd_hist"))
    if macd_h is not None:
        accel = tech.get("macd_accel", "")
        if macd_h > 0 and accel == "expanding":
            mom_score += 8; signals.append("MACD bullish & accelerating")
        elif macd_h > 0:
            mom_score += 4; signals.append("MACD bullish")
        elif macd_h < 0 and accel == "expanding":
            mom_score -= 8; warnings.append("MACD bearish & accelerating")
        elif macd_h < 0:
            mom_score -= 4; warnings.append("MACD bearish")

    mom5 = _safe(tech.get("mom_5d"))
    if mom5 is not None:
        if mom5 > 5: mom_score += 4
        elif mom5 < -5: mom_score -= 4

    votes["momentum"] = max(-30, min(30, mom_score))

    # ── 3. MEAN REVERSION (±15) ──
    mr_score = 0
    bb_pct_b = _safe(tech.get("bb_pct_b"))
    if bb_pct_b is not None:
        if bb_pct_b <= 0.05:
            mr_score += 10; signals.append(f"At lower Bollinger Band (%B: {bb_pct_b:.2f})")
        elif bb_pct_b <= 0.2:
            mr_score += 5; signals.append(f"Near lower Bollinger (%B: {bb_pct_b:.2f})")
        elif bb_pct_b >= 0.95:
            mr_score -= 8; warnings.append(f"At upper Bollinger Band (%B: {bb_pct_b:.2f})")
        elif bb_pct_b >= 0.8:
            mr_score -= 3

    bb_width = _safe(tech.get("bb_width"))
    if bb_width is not None and bb_width < 0.04:
        signals.append(f"Bollinger squeeze (width: {bb_width:.3f}) — breakout imminent")

    supports = tech.get("support_levels", [])
    resistances = tech.get("resistance_levels", [])
    if supports:
        dist = (price - supports[0]) / price * 100
        if dist < 2:
            mr_score += 5; signals.append(f"Near support {supports[0]:.2f} ({dist:.1f}% away)")
    if resistances:
        dist = (resistances[0] - price) / price * 100
        if dist < 1.5:
            mr_score -= 3; warnings.append(f"Resistance at {resistances[0]:.2f} ({dist:.1f}% away)")

    votes["mean_reversion"] = max(-15, min(15, mr_score))

    # ── 4. VOLUME (±10) ──
    vol_score = 0
    vol_ratio = _safe(tech.get("vol_ratio"))
    if vol_ratio is not None:
        if vol_ratio > 2.0:
            vol_score += 5; signals.append(f"Volume surge ({vol_ratio:.1f}× avg)")
        elif vol_ratio > 1.3:
            vol_score += 2
        elif vol_ratio < 0.4:
            vol_score -= 3; warnings.append(f"Thin volume ({vol_ratio:.1f}× avg)")

    obv_trend = tech.get("obv_trend")
    if obv_trend == "rising":
        vol_score += 3; signals.append("Accumulation (OBV rising)")
    elif obv_trend == "falling":
        vol_score -= 3; warnings.append("Distribution (OBV falling)")

    votes["volume"] = max(-10, min(10, vol_score))

    # ── 5. FUNDAMENTALS (±15) ──
    fund_score = 0
    pe, fwd_pe = _safe(data.get("pe_ratio")), _safe(data.get("forward_pe"))
    if pe and fwd_pe:
        if fwd_pe < pe * 0.82:
            fund_score += 5; signals.append(f"Earnings growth (Fwd P/E {fwd_pe:.1f} vs {pe:.1f})")
        elif fwd_pe > pe * 1.1:
            fund_score -= 3; warnings.append(f"Earnings decel (Fwd P/E {fwd_pe:.1f} > {pe:.1f})")

    roe = _safe(data.get("roe"))
    if roe is not None:
        if roe > 0.25: fund_score += 3; signals.append(f"Strong ROE ({roe*100:.0f}%)")
        elif roe < 0.05: fund_score -= 2

    rev_g = _safe(data.get("revenue_growth"))
    if rev_g is not None and rev_g > 0.15:
        fund_score += 2; signals.append(f"Revenue +{rev_g*100:.0f}% YoY")
    earn_g = _safe(data.get("earnings_growth"))
    if earn_g is not None and earn_g > 0.20:
        fund_score += 2

    de = _safe(data.get("debt_to_equity"))
    if de is not None and de > 200:
        fund_score -= 4; warnings.append(f"High leverage (D/E: {de:.0f})")

    rec = data.get("recommendation")
    if rec in ("strongBuy", "strong_buy"):
        fund_score += 4; signals.append("Analysts: Strong Buy")
    elif rec == "buy":
        fund_score += 2
    elif rec in ("sell", "strongSell", "strong_sell"):
        fund_score -= 4; warnings.append(f"Analysts: {rec.replace('_',' ').title()}")

    target = _safe(data.get("target_price"))
    if target and price:
        upside = (target - price) / price * 100
        if upside > 20:
            fund_score += 3; signals.append(f"Target {target:.2f} → {upside:.0f}% upside")
        elif upside < -10:
            fund_score -= 3; warnings.append(f"Trading {abs(upside):.0f}% above target")

    votes["fundamentals"] = max(-15, min(15, fund_score))

    # ═══ AGGREGATE ═══
    raw_score = sum(votes.values())
    score = max(0, min(100, int(50 + raw_score / 2)))
    bullish_cats = sum(1 for v in votes.values() if v > 2)
    bearish_cats = sum(1 for v in votes.values() if v < -2)

    if score >= 72 and bullish_cats >= 3:
        action, confidence = "STRONG_BUY", min(95, score)
    elif score >= 60 and bullish_cats >= 2:
        action, confidence = "BUY", min(85, score)
    elif score <= 28 and bearish_cats >= 3:
        action, confidence = "STRONG_SELL", min(95, 100 - score)
    elif score <= 40 and bearish_cats >= 2:
        action, confidence = "SELL", min(85, 100 - score)
    else:
        action, confidence = "HOLD", max(40, 100 - abs(score - 50) * 2)

    # ═══ ATR-BASED RISK MANAGEMENT ═══
    atr = _safe(tech.get("atr"), price * 0.02)

    if action in ("BUY", "STRONG_BUY"):
        entry = supports[0] if (supports and (price - supports[0]) / price < 0.03) else price
        stop_atr = round(entry - 2 * atr, 2)
        stop_sr = round(supports[0] - 0.5 * atr, 2) if supports else stop_atr
        stop_loss = max(stop_atr, stop_sr)
        risk = max(entry - stop_loss, 0.01)
        target_1 = round(entry + 2 * risk, 2)
        target_2 = round(entry + 3 * risk, 2)
        if resistances:
            target_1 = min(target_1, resistances[0])
        risk_pct = round(risk / entry * 100, 2)
    elif action in ("SELL", "STRONG_SELL"):
        entry = price
        stop_loss = round(price + 2 * atr, 2)
        if resistances:
            stop_loss = min(stop_loss, round(resistances[0] + 0.5 * atr, 2))
        risk = max(stop_loss - entry, 0.01)
        target_1 = round(entry - 2 * risk, 2)
        target_2 = round(entry - 3 * risk, 2)
        risk_pct = round(risk / entry * 100, 2)
    else:
        entry = price
        stop_loss = round(price - 2 * atr, 2)
        risk = 2 * atr
        target_1 = round(price + 2 * atr, 2)
        target_2 = round(price + 3 * atr, 2)
        risk_pct = round(risk / price * 100, 2)

    if action in ("BUY", "STRONG_BUY"):
        rr = round((target_1 - entry) / risk, 2) if risk > 0 else 0
    elif action in ("SELL", "STRONG_SELL"):
        rr = round((entry - target_1) / risk, 2) if risk > 0 else 0
    else:
        rr = 0

    return {
        "action": action,
        "score": score,
        "confidence": confidence,
        "confluence": {"bullish": bullish_cats, "bearish": bearish_cats},
        "category_scores": {k: round(v, 1) for k, v in votes.items()},
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


def execute(intent: dict) -> dict:
    t = intent["type"]
    market = intent.get("market", "US")

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

You get live stock data attached to each message. This includes a full trade signal with confluence scoring across 5 categories (trend, momentum, mean-reversion, volume, fundamentals), trend regime detection, support/resistance levels, and ATR-based entry/stop/target with risk-reward ratios. USE all of it — that's what makes you useful — but weave the numbers into natural conversation.

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
- Call out confluence: "4 out of 5 categories are bullish which is rare — this has conviction"
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
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&family=Outfit:wght@300;400;500;600;700&display=swap');
    :root { --bg:#0c0c0f; --surface:#141418; --border:#1e1e24; --muted:#63637a; --text:#cdcdd6; --bright:#ededf0; --accent:#34d399; --red:#f87171; }
    .stApp { background: var(--bg) !important; }
    header, footer, #MainMenu { visibility: hidden !important; }
    .block-container { max-width: 820px !important; padding: 2rem 1.5rem 5rem 1.5rem !important; }
    h1,h2,h3 { font-family:'Outfit',sans-serif !important; color:var(--bright) !important; font-weight:600 !important; letter-spacing:-0.02em !important; }
    p,span,div,label,li { font-family:'Outfit',sans-serif !important; color:var(--text) !important; }
    code,pre { font-family:'JetBrains Mono',monospace !important; }
    .stChatMessage { background:var(--surface) !important; border:1px solid var(--border) !important; border-radius:10px !important; padding:1rem 1.2rem !important; }
    .stChatMessage p,.stChatMessage span,.stChatMessage li,.stChatMessage code { color:var(--text) !important; }
    .stChatMessage strong { color:var(--bright) !important; }
    .stChatInput>div>div>textarea,.stTextInput>div>div>input { background:var(--surface) !important; border:1px solid var(--border) !important; border-radius:10px !important; color:var(--bright) !important; font-family:'Outfit',sans-serif !important; font-size:0.95rem !important; }
    .stChatInput>div>div>textarea:focus { border-color:var(--accent) !important; box-shadow:0 0 0 1px var(--accent) !important; }
    .stDataFrame { border-radius:8px !important; overflow:hidden; }
    .stDataFrame td,.stDataFrame th { background:var(--surface) !important; color:var(--text) !important; border-color:var(--border) !important; font-family:'JetBrains Mono',monospace !important; font-size:0.82rem !important; }
    .stDataFrame th { color:var(--muted) !important; font-weight:500 !important; }
    hr { border-color:var(--border) !important; margin:0.8rem 0 !important; }
    .stCaption p { color:var(--muted) !important; font-size:0.78rem !important; }
    .js-plotly-plot .plotly .modebar { display:none !important; }
    ::-webkit-scrollbar { width:6px; }
    ::-webkit-scrollbar-track { background:var(--bg); }
    ::-webkit-scrollbar-thumb { background:var(--border); border-radius:3px; }
    </style>
    """, unsafe_allow_html=True)

    if "messages" not in st.session_state:
        st.session_state.messages = []

    st.markdown("## ◉ Paula")
    st.caption("Stock analysis terminal — type a ticker or ask anything")
    st.markdown("---")

    for m in st.session_state.messages:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])
            if m["role"] == "assistant" and m.get("chart"):
                fig = build_chart(m["chart"], trade_signal=m.get("trade_signal"))
                if fig:
                    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
            if m["role"] == "assistant" and m.get("table"):
                st.dataframe(pd.DataFrame(m["table"]), use_container_width=True, hide_index=True)

    prompt = st.chat_input("Analyze NVDA… Top gainers… Price of AAPL…")
    if not prompt:
        return

    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner(""):
            intent = route(prompt)
            result = execute(intent)
            chart_ticker, table_data, trade_signal = None, None, None
            market = result.get("market", intent.get("market", "US"))

            if result.get("ok"):
                if result["type"] == "price":
                    chart_ticker = result["ticker"]
                    resp = result["msg"]
                elif result["type"] == "analysis":
                    chart_ticker = result["ticker"]
                    trade_signal = result.get("trade_signal")
                    resp = ai_response(prompt, result["data"], st.session_state.messages, market)
                elif result["type"] == "list":
                    table_data = result["data"]
                    resp = f"**{result['title']}** — {market} market"
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
                    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

            if table_data:
                df = pd.DataFrame(table_data)
                sym = "₹" if market == "India" else "$"
                df["Price"] = df["Price"].apply(lambda x: f"{sym}{x:,.2f}")
                df["Chg%"] = df["Chg%"].apply(lambda x: f"{'▲' if x>=0 else '▼'} {x:+.2f}%")
                if "Volume" in df.columns:
                    df["Volume"] = df["Volume"].apply(lambda x: f"{x/1e6:.1f}M" if x >= 1e6 else (f"{x/1e3:.0f}K" if x >= 1e3 else str(x)))
                st.dataframe(df, use_container_width=True, hide_index=True)

    st.session_state.messages.append({"role": "assistant", "content": resp, "chart": chart_ticker, "table": table_data, "trade_signal": trade_signal})


if __name__ == "__main__":
    main()
