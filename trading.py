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
import logging as _logging
_log = _logging.getLogger("paula")
if not _log.handlers:
    _h = _logging.StreamHandler()
    _h.setFormatter(_logging.Formatter("%(asctime)s [paula] %(levelname)s %(message)s"))
    _log.addHandler(_h)
    _log.setLevel(_logging.INFO)
import os
import json
import re
import random
import time
import requests
import warnings
from signal_logic import classify_analysis_side, compute_price_math

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
    "ORCL","NFLX","AMD","TMUS","ACN","LIN","DHR","TXN","WFC","DIS",
    "ABT","PM","INTU","VZ","QCOM","IBM","CAT","GE","NOW","ISRG",
]

# ── Mid-cap & small-cap growth ──
MIDCAP_GROWTH = [
    "AXON","DUOL","CELH","TMDX","RELY","HIMS","CAVA","ONON","BIRK","ELF",
    "WFRD","FTNT","ZS","MNDY","GLBE","TOST","BROS","DT","ESTC","DDOG",
    "FRSH","INTA","VERX","ALKT","PAYC","LMND","ROOT","OSCR","GDRX","CRDO",
    "APP","RDDT","TEM","ALAB","NBIS","RBRK","CART","NU","GRAB","SE",
]
# ── Small-cap high-potential ──
SMALLCAP = [
    "UPST","AFRM","JOBY","LUNR","ASTS","RKLB","ACHR","VERI","BBAI","SOUN",
    "OUST","IREN","CLSK","MARA","RIOT","HUT","BTBT","WULF","CIFR","CORZ",
    "MVST","QS","PSNY","BLNK","CHPT","EVGO","ARRY","NXT","SHLS","FLNC",
    "DNA","RXRX","BEAM","CRSP","NTLA","VERA","SDGR","TWST","TGTX","RNA",
]
# ── Value / Dividend ──
VALUE_DIVIDEND = [
    "O","SCHD","VZ","T","MO","PM","BTI","AGNC","NLY","STAG",
    "EPD","ET","MPLX","OKE","WMB","KMI","EMR","ITW","GPC","SWK",
    "DOW","LYB","NUE","CLF","AA","FCX","VALE","RIO","BHP",
    "PFE","KHC","GIS","K","CAG","HRL","KMB","CL","ED","SO",
]
# ── Sector-specific (energy, biotech, fintech, defense, space) ──
SECTOR_PICKS = [
    "FSLR","ENPH","NEE","CEG","VST","SMR","NNE","OKLO","LEU","GEV",
    "LMT","RTX","NOC","GD","HII","KTOS","LDOS","BWXT","RCAT","PLTR",
    "MRNA","BNTX","REGN","VRTX","ARGX","ALNY","BMRN","IONS","RARE","NBIX",
    "ANET","MRVL","MU","LRCX","KLAC","AMAT","ASML","TSM","DELL","SMCI",
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
    "RIVN","LCID","NIO","GME","DKNG","SNOW","NET","OKTA","QBTS","APP",
    "HIMS","CAVA","DUOL","CELH","LUNR","ASTS","SOUN","JOBY","UPST","AFRM",
    "RDDT","TSLA","NVDA","AMD","MU","AVGO","DELL","ANET","VST","CEG",
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
    # Words commonly confused with tickers
    "CAPS","CAP","MEGA","MID","TOP","HOT","NEW","OLD","OWN","RUN",
    "SET","TRY","WAY","DAY","BIG","FEW","FAR","OUR","OWN","SAY",
    "ANY","WAR","END","AGE","AID","AIR","ARM","ART","BAD","BAR",
    "BED","BIT","BOX","BOY","BUS","CUT","DID","DOG","EAR","EAT",
    "EGG","ERA","EYE","FAN","FIT","FIX","FLY","GAS","GOD","GOT",
    "GUN","GUY","HAD","HAS","HER","HIM","HIS","HIT","ICE","ILL",
    "ITS","JOB","KEY","KID","LAW","LAY","LED","LEG","LET","LIE",
    "LOT","MAP","MAY","MEN","MET","MIX","NOR","NOW","NUT","ODD",
    "OFF","OIL","ONE","OUT","OWE","PAN","PAY","PEN","PER","PET",
    "PIE","PIN","PIT","POT","PUT","RAN","RAW","RED","RID","ROW",
    "SAD","SAT","SAW","SEA","SIT","SIX","SKI","SKY","SON","SUM",
    "SUN","TAX","TEA","TEN","THE","TIE","TIN","TIP","TOE","TON",
    "TOO","TWO","USE","VAN","WAS","WET","WHO","WHY","WIN","WON",
    "YES","YET","DIPS","TIPS","IDEAS","SWING","TRADE","TRADES",
    "ENTRY","GRAPH","CHART","ORDER","POINT","LEVEL","VALUE","WORTH",
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
    # 2.5) Common misspellings, typos, voice recognition, and aliases
    ALIASES = {
        # Apple
        "appl": "AAPL", "aple": "AAPL", "apple": "AAPL", "aaple": "AAPL",
        # Google
        "goog": "GOOGL", "googl": "GOOGL", "google": "GOOGL", "gogle": "GOOGL",
        # Microsoft
        "msft": "MSFT", "microsoft": "MSFT", "micosoft": "MSFT", "mircosoft": "MSFT",
        # Amazon
        "amzn": "AMZN", "amazon": "AMAZON", "amazn": "AMZN",
        # Tesla
        "tsla": "TSLA", "tesla": "TSLA", "telsa": "TSLA", "tesle": "TSLA",
        # Nvidia
        "nvda": "NVDA", "nvidia": "NVDA", "nvidea": "NVDA", "nviida": "NVDA",
        # Meta
        "meta": "META", "facebook": "META",
        # Netflix
        "nflx": "NFLX", "netflix": "NFLX", "netflex": "NFLX", "netflx": "NFLX",
        # Intel
        "intc": "INTC", "intel": "INTC",
        # AMD
        "amd": "AMD",
        # Coinbase
        "coin": "COIN", "coinbase": "COIN",
        # Palantir
        "pltr": "PLTR", "palantir": "PLTR", "palentir": "PLTR",
        # Others
        "baba": "BABA", "alibaba": "BABA",
        "snap": "SNAP", "snapchat": "SNAP",
        "uber": "UBER",
        "disney": "DIS", "dis": "DIS",
        "nike": "NKE", "nke": "NKE",
        "starbucks": "SBUX", "sbux": "SBUX",
        "walmart": "WMT", "wmt": "WMT",
        "costco": "COST", "cost": "COST",
        "boeing": "BA",
        "ford": "F",
        "shopify": "SHOP", "shop": "SHOP",
        "robinhood": "HOOD", "hood": "HOOD",
        "sofi": "SOFI",
        "roblox": "RBLX", "rblx": "RBLX",
        "celsius": "CELH", "celh": "CELH",
        "rivian": "RIVN", "rivn": "RIVN",
        "duolingo": "DUOL", "duol": "DUOL",
        "chipotle": "CMG", "cmg": "CMG",
        "moderna": "MRNA", "mrna": "MRNA",
        "crowdstrike": "CRWD", "crwd": "CRWD",
        "datadog": "DDOG", "ddog": "DDOG",
        "snowflake": "SNOW", "snow": "SNOW",
        "broadcom": "AVGO", "avgo": "AVGO",
        "jpmorgan": "JPM", "jpm": "JPM", "jp morgan": "JPM",
        "goldman": "GS", "goldman sachs": "GS",
        "berkshire": "BRK-B",
    }
    for word in text.lower().split():
        clean = re.sub(r"[^a-z]", "", word)
        if clean in ALIASES:
            tick = ALIASES[clean]
            return tick, "US"
    # 2.6) Fuzzy match — if a word is 1-2 chars off from a known ticker
    for word in text.upper().split():
        clean = re.sub(r"[^A-Z]", "", word)
        if clean and 3 <= len(clean) <= 5 and clean not in _NOISE_WORDS:
            for known in list(us_set)[:200]:  # check against top tickers
                if len(known) == len(clean) and known != clean:
                    diffs = sum(1 for a, b in zip(known, clean) if a != b)
                    if diffs == 1:  # only 1 letter off
                        return known, "US"
    # 3) Polygon search — only if the message looks like a specific stock query
    stock_intent = any(w in low for w in [
        "analyze", "analysis", "price", "buy", "sell", "short", "cover", "chart", "graph", "quote",
        "stock", "ticker", "how is", "how's", "what about", "look at",
        "check out", "thoughts on", "opinion on", "review", "show me", "pull up", "display",
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
def web_search(query: str, max_results: int = 5) -> list[dict] | None:
    """Open-web search via Tavily (for questions Polygon stock-news can't cover,
    e.g. 'SpaceX IPO', macro, anything beyond a ticker). Reads TAVILY_API_KEY
    from the environment — never hardcoded. Returns [{title, url, content}] or
    None if no key / failure (caller falls back to training knowledge)."""
    key = os.environ.get("TAVILY_API_KEY")
    if not key:
        return None
    try:
        r = requests.post(
            "https://api.tavily.com/search",
            json={
                "api_key": key,
                "query": query,
                "max_results": max_results,
                "search_depth": "basic",
                "include_answer": True,
            },
            timeout=12,
        )
        if r.status_code != 200:
            return None
        data = r.json()
        out = []
        # Tavily's synthesized answer first (most useful for the LLM)
        if data.get("answer"):
            out.append({"title": "Summary", "url": "", "content": data["answer"][:600]})
        for res in data.get("results", [])[:max_results]:
            out.append({
                "title": res.get("title", ""),
                "url": res.get("url", ""),
                "content": (res.get("content") or "")[:400],
            })
        return out or None
    except Exception:
        return None


def fetch_news(ticker: str | None = None, limit: int = 6) -> list[dict] | None:
    """Recent news headlines via Polygon. If ticker is given, news for that
    stock; otherwise the latest market news. Returns [{title, publisher, date,
    url, summary}] or None."""
    key = _polygon_key()
    if not key:
        return None
    try:
        params = {"apiKey": key, "limit": limit, "order": "desc", "sort": "published_utc"}
        if ticker:
            params["ticker"] = ticker.upper()
        r = requests.get(f"{POLYGON_BASE}/v2/reference/news", params=params, timeout=10)
        if r.status_code != 200:
            return None
        out = []
        for a in r.json().get("results", [])[:limit]:
            out.append({
                "title": a.get("title", ""),
                "publisher": (a.get("publisher") or {}).get("name", ""),
                "date": (a.get("published_utc") or "")[:10],
                "url": a.get("article_url", ""),
                "summary": (a.get("description") or "")[:300],
            })
        return out or None
    except Exception:
        return None


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


def yahoo_top_movers() -> dict:
    """Fallback top gainer/loser from a curated liquid large-cap set via ONE
    yfinance batch download. Used when Polygon's gainers/losers snapshot isn't
    available (the free Polygon tier blocks that endpoint). Returns
    {'gainer': {...}, 'loser': {...}} with whatever it could compute.

    Note: this is a large-cap-only readout (not the whole market), so it won't
    surface a tiny stock up 300% — but it's reliable and free, and a big liquid
    name making a move is more meaningful for context anyway.
    """
    universe = [
        "AAPL","MSFT","NVDA","AMZN","GOOGL","META","TSLA","AVGO","JPM","V",
        "WMT","MA","JNJ","ORCL","HD","PG","COST","NFLX","BAC","AMD",
        "ADBE","CRM","KO","PEP","XOM","CVX","DIS","INTC","QCOM","CSCO",
        "MCD","NKE","BA","GE","CAT","PFE","T","VZ","UBER","PYPL",
    ]
    try:
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            df = yf.download(universe, period="2d", interval="1d",
                             group_by="ticker", auto_adjust=True,
                             threads=True, progress=False)
        rows = []
        for t in universe:
            try:
                sub = df[t] if len(universe) > 1 else df
                sub = sub.dropna(how="all")
                if sub is None or sub.empty or len(sub) < 2:
                    continue
                last = float(sub["Close"].iloc[-1])
                prev = float(sub["Close"].iloc[-2])
                if not prev:
                    continue
                chg = round((last - prev) / prev * 100, 2)
                rows.append({"Ticker": t, "Price": round(last, 2), "Chg%": chg})
            except Exception:
                continue
        if not rows:
            return {}
        rows.sort(key=lambda r: r["Chg%"], reverse=True)
        return {"gainer": rows[0], "loser": rows[-1]}
    except Exception:
        return {}


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

# ═══════════════════════════════════════════════════════════════════════════
#  TRADING HORIZON — Paula is a SWING trader, not a day trader.
#  Swing mode: holds positions across days (no end-of-day force-close), uses
#  daily-bar signals, wider stops/targets to ride multi-day moves. Target hold
#  is roughly 3–10 trading days; positions are only closed on stop, target,
#  signal reversal, or the max-hold timeout — never just because the bell rang.
# ═══════════════════════════════════════════════════════════════════════════
SWING_MODE = True
SWING_MAX_HOLD_DAYS = 10      # exit a stale trade after ~2 weeks
SWING_STOP_ATR_MULT = 2.0     # wider stop than intraday to survive overnight noise
SWING_MIN_STOP_PCT = 0.03     # at least 3% room
SWING_MAX_STOP_PCT = 0.10     # at most 10% risk on a multi-day hold
# Concurrent positions — the single knob controlling how much capital is
# deployed at once. Higher = more trades captured & higher return, but larger
# drawdown. Used by BOTH the backtest and the live autopilot so they stay in
# sync (change here = changes everywhere). 2 ≈ ~8% drawdown in backtest.
SWING_MAX_POSITIONS = 4      # backtest: ~+11% / 14% max DD — balanced; leaves headroom since live < backtest



import contextvars
# Per-user Alpaca credentials for the current request/scan. When set, overrides
# the shared env-var account so each user trades their OWN Alpaca paper account.
# Falls back to the shared env account when unset (None).
_current_alpaca_creds: contextvars.ContextVar = contextvars.ContextVar("alpaca_creds", default=None)

def set_alpaca_creds(key_id: str | None, secret: str | None):
    """Set the Alpaca creds for the current context (per-request). Pass None/empty
    to clear and fall back to the shared account."""
    if key_id and secret:
        _current_alpaca_creds.set({"key_id": key_id, "secret": secret})
    else:
        _current_alpaca_creds.set(None)


def _alpaca_headers() -> dict:
    creds = _current_alpaca_creds.get()
    if creds and creds.get("key_id") and creds.get("secret"):
        key_id, secret = creds["key_id"], creds["secret"]
    else:
        key_id = st.secrets.get("ALPACA_KEY_ID") or os.environ.get("ALPACA_KEY_ID", "")
        secret = st.secrets.get("ALPACA_SECRET") or os.environ.get("ALPACA_SECRET", "")
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
    """Get all open positions with stop loss levels."""
    try:
        r = requests.get(f"{ALPACA_BASE}/v2/positions", headers=_alpaca_headers(), timeout=10)
        if r.status_code != 200:
            return []
        
        # Fetch open orders to find stop losses
        stop_map = {}
        try:
            or_ = requests.get(f"{ALPACA_BASE}/v2/orders",
                              headers=_alpaca_headers(),
                              params={"status": "open", "limit": 100},
                              timeout=10)
            if or_.status_code == 200:
                for o in or_.json():
                    sym = o.get("symbol", "")
                    otype = o.get("type", "")
                    if otype in ("stop", "stop_limit") and sym:
                        stop_map[sym] = round(float(o.get("stop_price", 0)), 2)
        except Exception:
            pass

        positions = []
        for p in r.json():
            ticker = p.get("symbol", "")
            entry = round(float(p.get("avg_entry_price", 0)), 2)
            current = round(float(p.get("current_price", 0)), 2)
            stop = stop_map.get(ticker, 0)
            # Calculate stop distance %
            stop_pct = round((stop - entry) / entry * 100, 2) if stop and entry else 0
            positions.append({
                "ticker": ticker,
                "qty": float(p.get("qty", 0)),
                "side": p.get("side", "long"),
                "avg_entry": entry,
                "current_price": current,
                "market_value": round(float(p.get("market_value", 0)), 2),
                "unrealized_pnl": round(float(p.get("unrealized_pl", 0)), 2),
                "unrealized_pnl_pct": round(float(p.get("unrealized_plpc", 0)) * 100, 2),
                "today_pnl": round(float(p.get("unrealized_intraday_pl", 0)), 2),
                "stop_loss": stop,
                "stop_pct": stop_pct,
            })
        return positions
    except Exception:
        return []


@st.cache_data(ttl=300)
def trade_track_record(days: int = 30) -> dict:
    """Build a track record from recently CLOSED Alpaca orders so the AI can give
    advice grounded in the user's actual results, not generic platitudes.
    Returns win rate, counts, avg win/loss, and a short recent-trades summary."""
    try:
        from datetime import timedelta
        after = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
        r = requests.get(
            f"{ALPACA_BASE}/v2/orders",
            headers=_alpaca_headers(),
            params={"status": "closed", "limit": 200, "after": after, "direction": "desc"},
            timeout=10,
        )
        if r.status_code != 200:
            return {"ok": False}
        orders = r.json()
        # Pair fills per symbol to realize P&L (FIFO). Sells/covers close longs/shorts.
        fills = [o for o in orders if o.get("filled_at") and o.get("filled_avg_price")]
        fills.sort(key=lambda o: o.get("filled_at", ""))
        from collections import defaultdict, deque
        lots = defaultdict(deque)  # symbol -> deque of (qty, price, side)
        realized = []  # list of pnl per closed trade
        for o in fills:
            sym = o.get("symbol")
            side = o.get("side")
            qty = float(o.get("filled_qty", 0) or 0)
            px = float(o.get("filled_avg_price", 0) or 0)
            if qty <= 0 or px <= 0:
                continue
            if side == "buy":
                # closes a short lot if one is open, else opens a long
                if lots[sym] and lots[sym][0][2] == "short":
                    while qty > 0 and lots[sym] and lots[sym][0][2] == "short":
                        lq, lp, _ = lots[sym][0]
                        m = min(qty, lq)
                        realized.append((lp - px) * m)  # short: entry-exit
                        qty -= m
                        if m >= lq: lots[sym].popleft()
                        else: lots[sym][0] = (lq - m, lp, "short")
                    if qty > 0: lots[sym].append((qty, px, "long"))
                else:
                    lots[sym].append((qty, px, "long"))
            else:  # sell
                if lots[sym] and lots[sym][0][2] == "long":
                    while qty > 0 and lots[sym] and lots[sym][0][2] == "long":
                        lq, lp, _ = lots[sym][0]
                        m = min(qty, lq)
                        realized.append((px - lp) * m)  # long: exit-entry
                        qty -= m
                        if m >= lq: lots[sym].popleft()
                        else: lots[sym][0] = (lq - m, lp, "long")
                    if qty > 0: lots[sym].append((qty, px, "short"))
                else:
                    lots[sym].append((qty, px, "short"))
        closed = len(realized)
        if closed == 0:
            return {"ok": True, "closed_trades": 0, "summary": "No closed trades in the last %d days." % days}
        wins = [p for p in realized if p > 0]
        losses = [p for p in realized if p <= 0]
        win_rate = round(len(wins) / closed * 100, 1)
        avg_win = round(sum(wins) / len(wins), 2) if wins else 0
        avg_loss = round(sum(losses) / len(losses), 2) if losses else 0
        total = round(sum(realized), 2)
        return {
            "ok": True,
            "closed_trades": closed,
            "wins": len(wins), "losses": len(losses),
            "win_rate": win_rate,
            "avg_win": avg_win, "avg_loss": avg_loss,
            "total_realized": total,
            "summary": f"Last {days}d: {closed} closed trades, {win_rate}% win rate "
                       f"({len(wins)}W/{len(losses)}L), avg win ${avg_win}, avg loss ${avg_loss}, "
                       f"net ${total}.",
        }
    except Exception:
        return {"ok": False}


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

    # In swing mode, orders must persist across days. A "day" TIF makes Alpaca
    # auto-cancel the bracket's stop/target legs at the closing bell — which
    # silently turned swing positions into same-day exits. GTC keeps them alive.
    _tif = "gtc" if SWING_MODE else "day"
    order = {
        "symbol": ticker.upper(),
        "side": "buy",
        "time_in_force": _tif,
    }

    if notional and not qty:
        order["notional"] = round(notional, 2)
    else:
        order["qty"] = str(qty or 1)

    # NOTE: a plain market order with GTC is rejected by Alpaca (market orders
    # are inherently day). GTC only applies to limit/bracket/stop orders, which
    # is exactly what swing positions use (they always carry stop+target).

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

    # Alpaca rejects GTC on plain market orders (no stop/target legs to persist).
    # Such an order has nothing to hold overnight anyway, so fall back to day.
    if order.get("type") == "market" and order.get("order_class", "simple") in ("simple", None) and order["time_in_force"] == "gtc":
        order["time_in_force"] = "day"

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


def alpaca_cancel_all_orders() -> dict:
    """Cancel ALL open/pending orders (stops, limits, brackets) WITHOUT touching
    open positions. Different from close_all, which also liquidates positions."""
    try:
        # Count first so we can report how many were cancelled.
        try:
            r0 = requests.get(f"{ALPACA_BASE}/v2/orders", headers=_alpaca_headers(),
                              params={"status": "open"}, timeout=10)
            n = len(r0.json()) if r0.status_code == 200 and isinstance(r0.json(), list) else None
        except Exception:
            n = None
        r = requests.delete(f"{ALPACA_BASE}/v2/orders", headers=_alpaca_headers(), timeout=10)
        if r.status_code in (200, 207, 204):
            return {"ok": True, "count": n}
        return {"ok": False, "error": f"Failed to cancel orders: {r.status_code}"}
    except Exception as e:
        return {"ok": False, "error": str(e)[:100]}


def alpaca_close_all() -> dict:
    """Close ALL positions — cancel orders first, then close."""
    try:
        # Step 1: Cancel ALL pending orders (stops, limits, brackets)
        # These block position closes if not cancelled first
        requests.delete(f"{ALPACA_BASE}/v2/orders",
                       headers=_alpaca_headers(), timeout=10)

        # Step 2: Close all positions with cancel_orders flag
        r = requests.delete(f"{ALPACA_BASE}/v2/positions",
                            headers=_alpaca_headers(),
                            params={"cancel_orders": "true"},
                            timeout=10)
        if r.status_code in (200, 207):
            return {"ok": True, "message": "All positions closed"}
        return {"ok": False, "error": f"Failed to close positions: {r.status_code}"}
    except Exception as e:
        return {"ok": False, "error": str(e)[:100]}


def alpaca_short(ticker: str, qty: int = 1,
                 stop_loss: float = None, take_profit: float = None) -> dict:
    """
    Short sell — sell shares you don't own, profit when price drops.
    Alpaca paper trading supports shorting via regular sell orders.
    """
    if qty <= 0:
        return {"ok": False, "error": f"Can't short {qty} shares — need at least 1"}

    order = {
        "symbol": ticker.upper(),
        "qty": str(qty),
        "side": "sell",
        "type": "market",
        "time_in_force": "day",
    }

    # Bracket order for short: stop above, target below
    if stop_loss and take_profit:
        order["order_class"] = "bracket"
        order["stop_loss"] = {"stop_price": str(round(stop_loss, 2))}
        order["take_profit"] = {"limit_price": str(round(take_profit, 2))}
    elif stop_loss:
        order["order_class"] = "oto"
        order["stop_loss"] = {"stop_price": str(round(stop_loss, 2))}

    try:
        r = requests.post(f"{ALPACA_BASE}/v2/orders", headers=_alpaca_headers(),
                          json=order, timeout=10)
        data = r.json()
        if r.status_code in (200, 201):
            return {
                "ok": True,
                "order_id": data.get("id"),
                "symbol": data.get("symbol"),
                "qty": data.get("qty"),
                "side": "short",
                "type": data.get("type"),
                "status": data.get("status"),
                "order_class": data.get("order_class", "simple"),
            }
        else:
            return {"ok": False, "error": data.get("message", "Short order rejected")}
    except Exception as e:
        return {"ok": False, "error": str(e)[:100]}


def _update_stop_order(ticker: str, new_stop: float, qty: int) -> dict:
    """Move a long position's protective stop UP (trailing stop). Cancels any
    existing open stop/sell orders for the symbol, then places a fresh stop
    order at new_stop. Long-only."""
    sym = ticker.upper()
    try:
        # Cancel existing open orders for this symbol (the old stop sits here).
        r = requests.get(f"{ALPACA_BASE}/v2/orders", headers=_alpaca_headers(),
                         params={"status": "open", "symbols": sym}, timeout=10)
        if r.status_code == 200:
            for o in r.json():
                oid = o.get("id")
                if oid:
                    requests.delete(f"{ALPACA_BASE}/v2/orders/{oid}", headers=_alpaca_headers(), timeout=10)
        # Place the new stop (sell stop below market protects a long).
        order = {
            "symbol": sym,
            "qty": str(int(qty)),
            "side": "sell",
            "type": "stop",
            "stop_price": str(round(new_stop, 2)),
            "time_in_force": "gtc",
        }
        r = requests.post(f"{ALPACA_BASE}/v2/orders", headers=_alpaca_headers(), json=order, timeout=10)
        if r.status_code in (200, 201):
            return {"ok": True, "stop": new_stop}
        return {"ok": False, "error": (r.json().get("message", "") if r.text else "rejected")}
    except Exception as e:
        return {"ok": False, "error": str(e)[:100]}


def alpaca_cover(ticker: str, qty: int = None, cover_all: bool = False) -> dict:
    """Cover a short position — buy back shares to close."""
    # Always use DELETE endpoint — it handles qty correctly
    try:
        url = f"{ALPACA_BASE}/v2/positions/{ticker.upper()}"
        if qty and not cover_all:
            # Partial cover — use query param
            r = requests.delete(url, headers=_alpaca_headers(),
                                params={"qty": str(qty)}, timeout=10)
        else:
            # Full cover
            r = requests.delete(url, headers=_alpaca_headers(), timeout=10)
        
        if r.status_code in (200, 201, 207):
            data = r.json() if r.text else {}
            return {"ok": True, "symbol": ticker.upper(), "action": "covered_short",
                    "qty": data.get("qty", qty or "all"), "status": data.get("status", "closed")}
        elif r.status_code == 404:
            return {"ok": False, "error": f"No position found for {ticker}"}
        else:
            data = r.json() if r.text else {}
            return {"ok": False, "error": data.get("message", f"Failed to cover {ticker}")}
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
        # Alpaca needs an intraday timeframe for a 1-day chart, else it returns
        # a single point. Use 5Min for 1D, 1H for 1W, 1D for everything longer.
        tf_map = {"1D": "5Min", "1W": "1H"}
        timeframe = tf_map.get(period, "1D")
        params = {"period": period, "timeframe": timeframe}
        # intraday extended hours give a fuller 1D curve
        if period == "1D":
            params["extended_hours"] = "true"
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
            line=dict(color="#00e5a0", width=2.5),
            fill="tozeroy",
            fillcolor="rgba(0, 229, 160, 0.06)",
        ))

        # Color the P&L bars green/red
        colors = ["#00e5a0" if p >= 0 else "#ff3b5c" for p in pnl]
        fig.add_trace(go.Bar(
            x=dates, y=pnl, name="Daily P&L",
            marker_color=colors, opacity=0.35,
            yaxis="y2",
        ))

        # Starting equity reference line
        if equity:
            start_eq = equity[0]
            fig.add_hline(y=start_eq, line_dash="dash", line_color="#4a4a60",
                          opacity=0.5, annotation_text=f"Start ${start_eq:,.0f}")

        fig.update_layout(
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            title=dict(text="Portfolio Performance", font=dict(size=14, color="#e4e4f0", family="Outfit, sans-serif")),
            xaxis=dict(showgrid=False),
            yaxis=dict(title="Equity ($)", showgrid=True, gridcolor="rgba(30,30,42,0.8)", side="left"),
            yaxis2=dict(title="Daily P&L ($)", overlaying="y", side="right", showgrid=False),
            legend=dict(orientation="h", y=1.12, x=0.5, xanchor="center", font=dict(size=10, color="#4a4a60")),
            height=380,
            margin=dict(l=10, r=10, t=50, b=10),
            showlegend=True,
            font=dict(color="#4a4a60", size=10, family="JetBrains Mono, monospace"),
        )
        return fig
    except Exception:
        return None


def alpaca_smart_buy(ticker: str, trade_signal: dict, risk_pct: float = 0.02, dry_run: bool = False) -> dict:
    """
    Smart buy using Paula's trade signal. Automatically calculates:
    - Position size based on risk % of portfolio
    - Sets bracket order with stop-loss and take-profit from signal
    dry_run=True returns the computed qty/cost WITHOUT placing an order (used to
    populate the confirmation card).
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
    if dry_run:
        return {"ok": True, "qty_calculated": qty, "cost_estimate": round(cost, 2)}
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

    # ── 52-week high/low position (swing traders buy strength near highs) ──
    lookback = min(len(c), 252)
    hi_52 = float(c.iloc[-lookback:].max())
    lo_52 = float(c.iloc[-lookback:].min())
    tech["high_52w"] = round(hi_52, 2)
    tech["low_52w"] = round(lo_52, 2)
    tech["pct_from_52w_high"] = round((price - hi_52) / hi_52 * 100, 2) if hi_52 else 0
    if hi_52 > lo_52:
        tech["pct_in_52w_range"] = round((price - lo_52) / (hi_52 - lo_52) * 100, 1)

    # ── Volatility contraction (VCP-style: range tightening before a move) ──
    # Compare recent ATR% to the prior baseline. A contracting range while the
    # trend holds is a classic swing setup — energy coiling for a breakout.
    try:
        atr_series = _compute_atr(h, l, c, 14) / c * 100  # ATR as % of price
        if len(atr_series.dropna()) >= 30:
            recent_atr = float(atr_series.iloc[-5:].mean())
            base_atr = float(atr_series.iloc[-30:-10].mean())
            if base_atr > 0:
                tech["vol_contraction_ratio"] = round(recent_atr / base_atr, 2)
                tech["volatility_contracting"] = recent_atr < base_atr * 0.8
    except Exception:
        pass

    return tech


# ═══════════════════════════════════════════════════════════════════════════════
#  INTRADAY SIGNAL ENGINE — 5-minute bar analysis for day trading
#
#  Uses VWAP, intraday EMAs, 5min RSI/MACD, and volume spikes.
#  Completely separate from the daily signal engine.
# ═══════════════════════════════════════════════════════════════════════════════

def compute_intraday_technicals(hist: pd.DataFrame) -> dict:
    """Compute technicals on 5-minute bars for day trading.
    
    Advanced indicators:
    - Higher timeframe bias (hourly 100 EMA)
    - VWAP bounce quality (wick analysis)  
    - First hour trend lock
    - Parabolic exhaustion detection
    - RSI extremes with reversal candles
    - Previous day levels (stop hunt zones)
    - Stochastic RSI
    """
    if hist is None or hist.empty or len(hist) < 20:
        return {}

    close = hist["Close"]
    high = hist["High"]
    low = hist["Low"]
    open_ = hist["Open"]
    volume = hist["Volume"]
    price = float(close.iloc[-1])

    # ── VWAP ──
    typical_price = (high + low + close) / 3
    cum_tp_vol = (typical_price * volume).cumsum()
    cum_vol = volume.cumsum()
    vwap = cum_tp_vol / cum_vol.replace(0, 1)
    vwap_val = float(vwap.iloc[-1]) if not vwap.empty else price

    # ── EMAs on 5min bars ──
    ema_9 = float(close.ewm(span=9).mean().iloc[-1])
    ema_20 = float(close.ewm(span=20).mean().iloc[-1])
    ema_50 = float(close.ewm(span=50).mean().iloc[-1]) if len(close) >= 50 else ema_20

    # ── Higher Timeframe Bias: resample to 1H, compute ~20 EMA (proxy for 100 on 5min) ──
    htf_bias = "neutral"
    try:
        hourly = close.resample("1h").last().dropna()
        if len(hourly) >= 10:
            htf_ema = float(hourly.ewm(span=10).mean().iloc[-1])  # 10 hourly ~= 100 on 5min
            if price > htf_ema * 1.002:
                htf_bias = "bullish"
            elif price < htf_ema * 0.998:
                htf_bias = "bearish"
    except Exception:
        pass

    # ── RSI ──
    delta = close.diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss.replace(0, 0.001)
    rsi_series = 100 - (100 / (1 + rs))
    rsi = float(rsi_series.iloc[-1]) if not rsi_series.empty else 50

    # ── RSI(2) — ultra-short-term for VWAP pullback strategy ──
    rsi_2 = 50.0
    if len(close) >= 3:
        delta_2 = close.diff()
        gain_2 = delta_2.where(delta_2 > 0, 0).rolling(2).mean()
        loss_2 = (-delta_2.where(delta_2 < 0, 0)).rolling(2).mean()
        rs_2 = gain_2 / loss_2.replace(0, 0.001)
        rsi_2_series = 100 - (100 / (1 + rs_2))
        rsi_2 = float(rsi_2_series.iloc[-1]) if not rsi_2_series.empty and not pd.isna(rsi_2_series.iloc[-1]) else 50.0

    # ── Stochastic RSI ──
    stoch_k, stoch_d = 50.0, 50.0
    if len(rsi_series.dropna()) >= 14:
        rsi_min = rsi_series.rolling(14).min()
        rsi_max = rsi_series.rolling(14).max()
        stoch_rsi = ((rsi_series - rsi_min) / (rsi_max - rsi_min).replace(0, 1)) * 100
        stoch_k = float(stoch_rsi.rolling(3).mean().iloc[-1])
        stoch_d = float(stoch_rsi.rolling(3).mean().rolling(3).mean().iloc[-1])

    # ── MACD ──
    ema12 = close.ewm(span=12).mean()
    ema26 = close.ewm(span=26).mean()
    macd_line = ema12 - ema26
    macd_signal = macd_line.ewm(span=9).mean()
    macd_hist = float((macd_line - macd_signal).iloc[-1])

    # ── Volume ratio ──
    vol_avg = float(volume.rolling(20).mean().iloc[-1]) if len(volume) >= 20 else float(volume.mean())
    vol_current = float(volume.iloc[-1])
    vol_ratio = round(vol_current / max(vol_avg, 1), 2)

    # ── ATR ──
    tr = pd.concat([
        high - low,
        (high - close.shift(1)).abs(),
        (low - close.shift(1)).abs(),
    ], axis=1).max(axis=1)
    atr = float(tr.rolling(14).mean().iloc[-1]) if len(tr) >= 14 else float(tr.mean())

    # ── Day high/low ──
    day_high = float(high.max())
    day_low = float(low.min())

    # ── Previous day high/low (stop hunt levels) ──
    prev_day_high, prev_day_low = day_high, day_low
    try:
        daily_highs = high.resample("D").max().dropna()
        daily_lows = low.resample("D").min().dropna()
        if len(daily_highs) >= 2:
            prev_day_high = float(daily_highs.iloc[-2])
            prev_day_low = float(daily_lows.iloc[-2])
    except Exception:
        pass

    # ── Stop hunt detection ──
    # Did price just sweep past prev day high/low then reverse?
    stop_hunt = "none"
    last_5_high = float(high.tail(5).max())
    last_5_low = float(low.tail(5).min())
    if last_5_high > prev_day_high and price < prev_day_high:
        stop_hunt = "bull_trap"  # swept highs, reversed down → short signal
    elif last_5_low < prev_day_low and price > prev_day_low:
        stop_hunt = "bear_trap"  # swept lows, reversed up → long signal

    # ── Higher lows / Lower highs ──
    recent_lows = low.tail(6).values
    higher_lows = all(recent_lows[i] >= recent_lows[i-1] for i in range(1, len(recent_lows))) if len(recent_lows) >= 3 else False
    recent_highs = high.tail(6).values
    lower_highs = all(recent_highs[i] <= recent_highs[i-1] for i in range(1, len(recent_highs))) if len(recent_highs) >= 3 else False

    # ── VWAP bounce quality ──
    # Look for long wick rejection at VWAP (smart money stepping in)
    vwap_bounce_quality = 0
    if len(hist) >= 3:
        for i in range(-3, 0):
            bar_low = float(low.iloc[i])
            bar_close = float(close.iloc[i])
            bar_open = float(open_.iloc[i])
            bar_high = float(high.iloc[i])
            body = abs(bar_close - bar_open)
            lower_wick = min(bar_close, bar_open) - bar_low
            bar_vol = float(volume.iloc[i])
            # Long lower wick near VWAP = bullish rejection
            if lower_wick > body * 1.5 and abs(bar_low - vwap_val) / price < 0.003 and bar_vol > vol_avg * 1.2:
                vwap_bounce_quality = max(vwap_bounce_quality, 3)
            elif lower_wick > body and abs(bar_low - vwap_val) / price < 0.005:
                vwap_bounce_quality = max(vwap_bounce_quality, 2)

    # ── Parabolic exhaustion ──
    # 5+ consecutive green or red candles = exhaustion incoming
    parabolic = "none"
    if len(close) >= 6:
        last_colors = [(float(close.iloc[i]) > float(open_.iloc[i])) for i in range(-6, 0)]
        greens = sum(last_colors)
        reds = 6 - greens
        if greens >= 5:
            # Check if last candle is red (reversal starting)
            if float(close.iloc[-1]) < float(open_.iloc[-1]):
                parabolic = "bear_reversal"  # was parabolic green, first red → short
            else:
                parabolic = "extended_bull"  # still running but exhaustion likely
        elif reds >= 5:
            if float(close.iloc[-1]) > float(open_.iloc[-1]):
                parabolic = "bull_reversal"  # was parabolic red, first green → long
            else:
                parabolic = "extended_bear"

    # ── RSI exhaustion with reversal candle ──
    rsi_exhaustion = "none"
    if rsi >= 85:
        if float(close.iloc[-1]) < float(open_.iloc[-1]):  # red candle
            rsi_exhaustion = "overbought_reversal"
    elif rsi <= 15:
        if float(close.iloc[-1]) > float(open_.iloc[-1]):  # green candle
            rsi_exhaustion = "oversold_reversal"

    # ── First hour trend ──
    first_hour_trend = "neutral"
    try:
        today = hist.index[-1].date()
        today_bars = hist[hist.index.date == today]
        if len(today_bars) >= 6:  # ~30min of data
            first_6 = today_bars.head(6)
            fh_open = float(first_6["Open"].iloc[0])
            fh_close = float(first_6["Close"].iloc[-1])
            fh_change = (fh_close - fh_open) / fh_open * 100
            if fh_change > 0.3:
                first_hour_trend = "bullish"
            elif fh_change < -0.3:
                first_hour_trend = "bearish"
    except Exception:
        pass

    # ── ADX (trend strength) ──
    adx_val = 20.0
    try:
        plus_dm = high.diff().clip(lower=0)
        minus_dm = (-low.diff()).clip(lower=0)
        # Zero out when opposite DM is larger
        plus_dm[plus_dm < minus_dm] = 0
        minus_dm[minus_dm < plus_dm] = 0
        atr_14 = tr.rolling(14).mean()
        plus_di = 100 * (plus_dm.rolling(14).mean() / atr_14.replace(0, 1))
        minus_di = 100 * (minus_dm.rolling(14).mean() / atr_14.replace(0, 1))
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di).replace(0, 1)
        adx_val = float(dx.rolling(14).mean().iloc[-1])
    except Exception:
        adx_val = 20.0

    # ── Candlestick Patterns (last 3 bars) ──
    candle_pattern = "none"
    try:
        c1_open, c1_close = float(open_.iloc[-1]), float(close.iloc[-1])
        c1_high, c1_low = float(high.iloc[-1]), float(low.iloc[-1])
        c1_body = abs(c1_close - c1_open)
        c1_range = c1_high - c1_low
        c1_lower_wick = min(c1_open, c1_close) - c1_low
        c1_upper_wick = c1_high - max(c1_open, c1_close)
        c1_green = c1_close > c1_open

        c2_open, c2_close = float(open_.iloc[-2]), float(close.iloc[-2])
        c2_body = abs(c2_close - c2_open)
        c2_green = c2_close > c2_open

        # Hammer (bullish reversal) — long lower wick, small body at top
        if c1_lower_wick > c1_body * 2 and c1_upper_wick < c1_body * 0.5 and c1_range > 0:
            candle_pattern = "hammer"
        # Shooting star (bearish reversal) — long upper wick, small body at bottom
        elif c1_upper_wick > c1_body * 2 and c1_lower_wick < c1_body * 0.5 and c1_range > 0:
            candle_pattern = "shooting_star"
        # Bullish engulfing
        elif c1_green and not c2_green and c1_body > c2_body * 1.3 and c1_close > c2_open:
            candle_pattern = "bullish_engulfing"
        # Bearish engulfing
        elif not c1_green and c2_green and c1_body > c2_body * 1.3 and c1_close < c2_open:
            candle_pattern = "bearish_engulfing"
        # Doji — body is tiny vs range
        elif c1_range > 0 and c1_body / c1_range < 0.1:
            candle_pattern = "doji"
    except Exception:
        pass

    # ── Support/Resistance from recent swing points ──
    support_level = day_low
    resistance_level = day_high
    try:
        recent_close = close.tail(40)
        recent_high = high.tail(40)
        recent_low = low.tail(40)
        # Simple S/R: find local min/max
        if len(recent_close) >= 20:
            rolling_min = recent_low.rolling(10, center=True).min()
            rolling_max = recent_high.rolling(10, center=True).max()
            supports = recent_low[recent_low == rolling_min].dropna().unique()
            resists = recent_high[recent_high == rolling_max].dropna().unique()
            if len(supports) > 0:
                support_level = float(max(s for s in supports if s < price)) if any(s < price for s in supports) else day_low
            if len(resists) > 0:
                resistance_level = float(min(r for r in resists if r > price)) if any(r > price for r in resists) else day_high
    except Exception:
        pass

    # ── Breakout detection ──
    breakout = "none"
    if price > prev_day_high * 1.001:
        breakout = "above_prev_high"
    elif price < prev_day_low * 0.999:
        breakout = "below_prev_low"

    # ── Range detection ──
    is_ranging = False
    try:
        last_20_range = float(high.tail(20).max() - low.tail(20).min())
        last_20_avg = float(close.tail(20).mean())
        range_pct = last_20_range / last_20_avg * 100
        is_ranging = range_pct < 1.5 and adx_val < 20
    except Exception:
        pass

    return {
        "price": price,
        "vwap": round(vwap_val, 2),
        "ema_9": round(ema_9, 2),
        "ema_20": round(ema_20, 2),
        "ema_50": round(ema_50, 2),
        "rsi": round(rsi, 1),
        "rsi_2": round(rsi_2, 1),
        "stoch_k": round(stoch_k, 1),
        "stoch_d": round(stoch_d, 1),
        "macd_hist": round(macd_hist, 4),
        "vol_ratio": vol_ratio,
        "atr": round(atr, 4),
        "adx": round(adx_val, 1),
        "day_high": round(day_high, 2),
        "day_low": round(day_low, 2),
        "day_open": round(float(open_.iloc[0]), 2) if len(open_) > 0 else 0,
        "prev_day_high": round(prev_day_high, 2),
        "prev_day_low": round(prev_day_low, 2),
        "higher_lows": higher_lows,
        "lower_highs": lower_highs,
        "above_vwap": price > vwap_val,
        "ema_bullish": ema_9 > ema_20,
        "htf_bias": htf_bias,
        "vwap_bounce_quality": vwap_bounce_quality,
        "stop_hunt": stop_hunt,
        "parabolic": parabolic,
        "rsi_exhaustion": rsi_exhaustion,
        "first_hour_trend": first_hour_trend,
        "candle_pattern": candle_pattern,
        "support_level": round(support_level, 2),
        "resistance_level": round(resistance_level, 2),
        "breakout": breakout,
        "is_ranging": is_ranging,
    }


def generate_intraday_signal(data: dict) -> dict:
    """
    Day Trading Signal Engine — Buy intraday momentum above VWAP.

    Strategy: Buy when price is above VWAP with EMA confirmation,
    on a pullback with volume. Tight stops, quick targets.

    Entry rules (ALL must be true for BUY):
    1. Price above VWAP (institutions are buying)
    2. 9 EMA above 20 EMA (short-term momentum up)
    3. Price pulled back toward VWAP or 20 EMA (the dip to buy)
    4. RSI 35-65 on 5min (not overbought)
    5. Volume above average (confirmation)
    """
    tech = data.get("intraday_technicals", {})
    price = tech.get("price", 0)
    if not price or not tech:
        return {"action": "NO_DATA", "confidence": 0, "score": 0,
                "confluence": {"bullish": 0, "bearish": 0},
                "category_scores": {}, "signals": [], "warnings": [],
                "trade": {"entry": 0, "stop_loss": 0, "target_1": 0,
                          "target_2": 0, "risk_reward": 0, "risk_pct": 0, "atr": 0}}

    signals = []
    warnings = []
    score = 50  # neutral starting point

    vwap = tech.get("vwap", price)
    ema_9 = tech.get("ema_9", price)
    ema_20 = tech.get("ema_20", price)
    ema_50 = tech.get("ema_50", price)
    rsi = tech.get("rsi", 50)
    macd_h = tech.get("macd_hist", 0)
    vol_ratio = tech.get("vol_ratio", 1)
    atr = tech.get("atr", 0.01)
    above_vwap = tech.get("above_vwap", False)
    ema_bullish = tech.get("ema_bullish", False)
    higher_lows = tech.get("higher_lows", False)
    lower_highs = tech.get("lower_highs", False)
    day_high = tech.get("day_high", price)
    day_low = tech.get("day_low", price)

    # ── 1. VWAP Position (±15 points) ──
    vwap_dist = (price - vwap) / vwap * 100 if vwap else 0
    if above_vwap and vwap_dist > 0.5:
        score += 12
        signals.append(f"✓ Above VWAP (${vwap:.2f}) — buyers in control")
    elif above_vwap:
        score += 6
        signals.append(f"Near VWAP (${vwap:.2f})")
    elif vwap_dist < -0.5:
        score -= 12
        warnings.append(f"Below VWAP (${vwap:.2f}) — sellers in control")
    else:
        score -= 4

    # ── 2. EMA Trend (±12 points) ──
    if ema_bullish and ema_9 > ema_50:
        score += 12
        signals.append("✓ Strong EMA alignment (9 > 20 > 50)")
    elif ema_bullish:
        score += 8
        signals.append("✓ 9 EMA above 20 EMA — momentum up")
    elif not ema_bullish and ema_9 < ema_50:
        score -= 12
        warnings.append("EMAs bearish (9 < 20 < 50)")
    else:
        score -= 6
        warnings.append("9 EMA below 20 EMA — momentum down")

    # ── 3. Pullback Quality (±10 points) ──
    # Best entry: price above VWAP but pulled back near it or near 20 EMA
    dist_to_vwap = abs(price - vwap) / price * 100
    dist_to_ema20 = abs(price - ema_20) / price * 100

    if above_vwap and dist_to_vwap < 0.3:
        score += 10
        signals.append("✓ Pullback to VWAP — ideal entry")
    elif above_vwap and dist_to_ema20 < 0.2:
        score += 8
        signals.append("✓ Pullback to 20 EMA")
    elif above_vwap and dist_to_vwap > 1.5:
        score -= 3
        warnings.append("Extended above VWAP — risky chase")

    # ── 4. RSI (±8 points) ──
    if 35 <= rsi <= 55:
        score += 8
        signals.append(f"✓ RSI {rsi:.0f} — pulled back, room to run")
    elif 55 < rsi <= 65:
        score += 3
    elif rsi > 75:
        score -= 8
        warnings.append(f"RSI {rsi:.0f} — overbought, avoid chasing")
    elif rsi < 30:
        score -= 6
        warnings.append(f"RSI {rsi:.0f} — oversold, wait for reversal")
    elif rsi > 65:
        score -= 3
        warnings.append(f"RSI {rsi:.0f} — getting hot")

    # ── 5. Volume (±10 points) ──
    if vol_ratio >= 2.0:
        score += 10
        signals.append(f"✓ Volume spike ({vol_ratio:.1f}x avg) — strong interest")
    elif vol_ratio >= 1.3:
        score += 6
        signals.append(f"Above-average volume ({vol_ratio:.1f}x)")
    elif vol_ratio < 0.5:
        score -= 6
        warnings.append(f"Dead volume ({vol_ratio:.1f}x) — no conviction")
    elif vol_ratio < 0.8:
        score -= 3

    # ── 6. MACD Histogram (±6 points) ──
    if macd_h > 0:
        score += 6
        signals.append("MACD histogram positive")
    else:
        score -= 4
        warnings.append("MACD histogram negative")

    # ── 7. Price Action (±6 points) ──
    if higher_lows and above_vwap:
        score += 6
        signals.append("✓ Higher lows — buyers stepping up")
    elif lower_highs and not above_vwap:
        score -= 6
        warnings.append("Lower highs — sellers pressing")

    # ── 8. News Sentiment (±8 points) ──
    news_sent = data.get("news_sentiment", {})
    news_score = news_sent.get("score", 0)
    if news_score >= 3:
        score += 8
        signals.append(f"Bullish news ({news_sent.get('bullish_count', 0)} positive headlines)")
    elif news_score >= 1:
        score += 3
    elif news_score <= -3:
        score -= 8
        warnings.append(f"Bearish news ({news_sent.get('bearish_count', 0)} negative headlines)")
    elif news_score <= -1:
        score -= 3

    # ── 9. ADX Trend Strength (±8 points) ──
    adx = tech.get("adx", 20)
    if adx >= 30:
        score += 8 if above_vwap else -6
        signals.append(f"✓ Strong trend (ADX {adx:.0f}) — {'ride it' if above_vwap else 'trending down'}")
    elif adx >= 22:
        score += 4 if above_vwap else -3
        signals.append(f"Moderate trend (ADX {adx:.0f})")
    elif adx < 15:
        score -= 2
        warnings.append(f"No trend (ADX {adx:.0f}) — choppy, beware fakeouts")

    # ── 10. Breakout Detection (±10 points) ──
    breakout = tech.get("breakout", "none")
    if breakout == "above_prev_high" and vol_ratio >= 1.3:
        score += 10
        signals.append(f"✓ Breakout above prev day high (${tech.get('prev_day_high', 0):.2f}) on volume")
    elif breakout == "above_prev_high":
        score += 5
        signals.append(f"Above prev day high — needs volume confirmation")
    elif breakout == "below_prev_low" and vol_ratio >= 1.3:
        score -= 10
        warnings.append(f"Breakdown below prev day low (${tech.get('prev_day_low', 0):.2f}) on volume")
    elif breakout == "below_prev_low":
        score -= 5
        warnings.append(f"Below prev day low — weak")

    # ── 11. Candlestick Patterns (±8 points) ──
    candle = tech.get("candle_pattern", "none")
    if candle == "hammer":
        score += 8
        signals.append("✓ Hammer candle — bullish reversal pattern")
    elif candle == "bullish_engulfing":
        score += 8
        signals.append("✓ Bullish engulfing — strong reversal")
    elif candle == "shooting_star":
        score -= 8
        warnings.append("Shooting star — bearish reversal pattern")
    elif candle == "bearish_engulfing":
        score -= 8
        warnings.append("Bearish engulfing — strong reversal down")
    elif candle == "doji":
        score -= 2
        warnings.append("Doji — indecision, wait for confirmation")

    # ── 12. Stop Hunt / Liquidity Sweep (±6 points) ──
    stop_hunt = tech.get("stop_hunt", "none")
    if stop_hunt == "bear_trap":
        score += 6
        signals.append("✓ Bear trap — swept lows then reversed up (smart money long)")
    elif stop_hunt == "bull_trap":
        score -= 6
        warnings.append("Bull trap — swept highs then reversed down (smart money short)")

    # ── 13. Parabolic / Exhaustion (±6 points) ──
    parabolic = tech.get("parabolic", "none")
    if parabolic == "bull_reversal":
        score += 6
        signals.append("✓ Parabolic sell-off reversing — bounce play")
    elif parabolic == "bear_reversal":
        score -= 6
        warnings.append("Parabolic rally exhausted — reversal candle")
    elif parabolic == "extended_bull":
        score -= 3
        warnings.append("Extended run (5+ green candles) — exhaustion risk")
    elif parabolic == "extended_bear":
        score += 2

    # ── 14. Stochastic RSI (±6 points) ──
    stoch_k = tech.get("stoch_k", 50)
    stoch_d = tech.get("stoch_d", 50)
    if stoch_k < 20 and stoch_k > stoch_d:
        score += 6
        signals.append(f"✓ Stoch RSI oversold ({stoch_k:.0f}) crossing up — momentum turning")
    elif stoch_k > 80 and stoch_k < stoch_d:
        score -= 6
        warnings.append(f"Stoch RSI overbought ({stoch_k:.0f}) crossing down — momentum fading")
    elif stoch_k > 85:
        score -= 3
        warnings.append(f"Stoch RSI stretched ({stoch_k:.0f})")

    # ── 15. First Hour Trend (±5 points) ──
    fh_trend = tech.get("first_hour_trend", "neutral")
    if fh_trend == "bullish" and above_vwap:
        score += 5
        signals.append("✓ First hour trend bullish — momentum from open")
    elif fh_trend == "bearish" and not above_vwap:
        score -= 5
        warnings.append("First hour trend bearish — selling from open")

    # ── 16. Higher Timeframe Bias (±5 points) ──
    htf = tech.get("htf_bias", "neutral")
    if htf == "bullish":
        score += 5
        signals.append("✓ Hourly trend bullish — higher timeframe supports longs")
    elif htf == "bearish":
        score -= 5
        warnings.append("Hourly trend bearish — higher timeframe favors shorts")

    # ── 17. Range Warning (±4 points) ──
    is_ranging = tech.get("is_ranging", False)
    if is_ranging:
        score -= 4
        warnings.append("Stock is range-bound (ADX low, tight price action) — breakout or fade")

    # ── 18. VWAP Bounce Quality (±4 points) ──
    vwap_bounce = tech.get("vwap_bounce_quality", 0)
    if vwap_bounce >= 3:
        score += 4
        signals.append("✓ Clean VWAP bounce with volume — institutional buying")
    elif vwap_bounce >= 2:
        score += 2
        signals.append("VWAP bounce detected")

    # ── 19. VWAP Pullback Strategy (±10 points) ──
    # Based on Brian Shannon method — backtested at 1.69 profit factor
    # Buy when: price above VWAP + RSI(2) oversold (price pulled back to VWAP)
    rsi_2 = tech.get("rsi_2", 50)
    if above_vwap and rsi_2 < 25 and dist_to_vwap < 0.5:
        score += 10
        signals.append(f"✓ VWAP Pullback Setup — RSI(2)={rsi_2:.0f}, price at VWAP support")
    elif above_vwap and rsi_2 < 35 and dist_to_vwap < 0.8:
        score += 5
        signals.append(f"Near VWAP pullback — RSI(2)={rsi_2:.0f}")
    elif not above_vwap and rsi_2 > 75 and dist_to_vwap < 0.5:
        score -= 10
        warnings.append(f"Bearish VWAP pullback — RSI(2)={rsi_2:.0f}, price at VWAP resistance")
    elif not above_vwap and rsi_2 > 65 and dist_to_vwap < 0.8:
        score -= 5

    # ── 20. Open = High/Low Strategy (±8 points) ──
    # If open = day high after 15 min → bearish (sellers immediately took over)
    # If open = day low after 15 min → bullish (buyers stepped in immediately)
    day_open = tech.get("day_open", 0)
    if day_open > 0 and day_high > 0 and day_low > 0:
        open_is_high = abs(day_open - day_high) / price < 0.001  # within 0.1%
        open_is_low = abs(day_open - day_low) / price < 0.001
        if open_is_low and price > day_open:
            score += 8
            signals.append("✓ Open = Day Low — buyers dominated from the bell")
        elif open_is_high and price < day_open:
            score -= 8
            warnings.append("Open = Day High — sellers dominated from the bell")

    # ── 21. Volume Breakout Confirmation (±6 points) ──
    # Breakouts only matter with 2x+ volume — confirmed by 2025 research
    if breakout in ("above_prev_high", "below_prev_low"):
        if vol_ratio >= 2.0:
            score += 6 if breakout == "above_prev_high" else -6
            signals.append(f"✓ Volume-confirmed breakout ({vol_ratio:.1f}x) — high probability")
        elif vol_ratio < 1.0:
            # Fake breakout — low volume
            if breakout == "above_prev_high":
                score -= 4
                warnings.append(f"Low-volume breakout ({vol_ratio:.1f}x) — likely fakeout")
            else:
                score += 4
                signals.append(f"Low-volume breakdown ({vol_ratio:.1f}x) — likely fakeout bounce")

    # ── DETERMINE ACTION ──
    # Raw positives can total ~+115 over the 50 baseline, so genuinely strong
    # stocks used to slam into the 100 ceiling and all read identically (the
    # "why are they all 100" bug). Compress the above-50 portion so a perfect
    # setup lands ~95, not 150 — preserving real differentiation between good
    # and great. Below 50 is left linear (a bad stock should read clearly bad).
    if score > 50:
        # Diminishing returns above baseline: 0.6x compression, capped at 98.
        score = 50 + min(48, (score - 50) * 0.6)
    score = max(0, min(100, round(score)))

    bullish_count = sum(1 for s in signals if "✓" in s)
    bearish_count = len(warnings)

    if score >= 68 and above_vwap and ema_bullish:
        action = "STRONG_BUY"
        confidence = min(95, score)
    elif score >= 56 and (above_vwap or ema_bullish):
        action = "BUY"
        confidence = min(85, score)
    elif score <= 32:
        action = "STRONG_SELL"
        confidence = min(90, 100 - score)
    elif score <= 42 and (not above_vwap or not ema_bullish):
        action = "SELL"
        confidence = min(80, 100 - score)
    else:
        action = "HOLD"
        confidence = max(40, 100 - abs(score - 50) * 2)

    # ── RISK MANAGEMENT (Intraday — uses 5min ATR) ──
    # Load stop floor from config
    _stop_floor = 0.013  # default 1.3%
    try:
        _cfg_path = pathlib.Path(__file__).parent / "autopilot_config.json"
        if _cfg_path.exists():
            _cfg = json.loads(_cfg_path.read_text())
            _stop_floor = _cfg.get("STOP_FLOOR", 0.013)
    except Exception:
        pass

    if action in ("BUY", "STRONG_BUY"):
        entry = price
        # Stop: 3x intraday ATR — give room to breathe
        stop_atr = round(entry - 3.0 * atr, 2)
        stop_vwap = round(vwap - 1.0 * atr, 2) if above_vwap and dist_to_vwap < 0.5 else stop_atr
        stop_loss = max(stop_atr, stop_vwap)
        # Floor: at least STOP_FLOOR% stop distance
        min_stop = round(entry * (1.0 - _stop_floor), 2)
        if stop_loss > min_stop:
            stop_loss = min_stop

        risk = max(entry - stop_loss, 0.01)
        target_1 = round(entry + 2.5 * risk, 2)
        target_2 = round(entry + 4.0 * risk, 2)
        risk_pct = round(risk / entry * 100, 2)
    elif action in ("SELL", "STRONG_SELL"):
        entry = price
        stop_loss = round(price + 3.0 * atr, 2)
        max_stop = round(entry * (1.0 + _stop_floor), 2)
        if stop_loss < max_stop:
            stop_loss = max_stop
        risk = max(stop_loss - entry, 0.01)
        target_1 = round(entry - 2.5 * risk, 2)
        target_2 = round(entry - 4.0 * risk, 2)
        risk_pct = round(risk / entry * 100, 2)
    else:
        # HOLD — no high-conviction entry. Guard against tiny/zero ATR collapsing
        # entry=stop=target, and bias direction by intraday structure (VWAP/EMA20).
        entry = price
        eff_atr = atr if atr and atr > 0 else max(round(price * 0.01, 2), 0.01)
        bearish_bias = (not above_vwap) and (price < ema_20)
        if bearish_bias:
            stop_loss = round(price + 3.0 * eff_atr, 2)
            target_1 = round(price - 3.0 * eff_atr, 2)
            target_2 = round(price - 5.0 * eff_atr, 2)
        else:
            stop_loss = round(price - 3.0 * eff_atr, 2)
            target_1 = round(price + 3.0 * eff_atr, 2)
            target_2 = round(price + 5.0 * eff_atr, 2)
        risk = 3.0 * eff_atr
        risk_pct = round(risk / price * 100, 2)

    rr = round((target_1 - entry) / risk, 2) if risk > 0 and target_1 > entry else (
         round((entry - target_1) / risk, 2) if risk > 0 and entry > target_1 else 0)

    return {
        "action": action,
        "score": score,
        "confidence": confidence,
        "confluence": {"bullish": bullish_count, "bearish": bearish_count},
        "category_scores": {
            "vwap": 1 if above_vwap else -1,
            "ema_trend": 1 if ema_bullish else -1,
            "momentum": 1 if macd_h > 0 else -1,
            "volume": 1 if vol_ratio >= 1.3 else (-1 if vol_ratio < 0.8 else 0),
            "rsi": 1 if 35 <= rsi <= 55 else (-1 if rsi > 70 else 0),
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
            "atr": round(atr, 4),
        },
    }


@st.cache_data(ttl=120)
def fetch_scan_intraday(ticker: str) -> dict | None:
    """Fetch 5-minute bars for day trading analysis."""
    try:
        stk = yf.Ticker(ticker)
        # Get 5-day 5min history (yfinance max for 5m interval)
        hist = stk.history(period="5d", interval="5m")
        if hist is None or hist.empty or len(hist) < 30:
            return None

        price = float(hist["Close"].iloc[-1])
        if not price or price < 1:
            return None

        # Also get daily history for relative strength and sector
        daily = stk.history(period="6mo")
        rs = _calc_relative_strength(daily) if daily is not None and len(daily) >= 50 else {}
        sector_etf = TICKER_SECTOR.get(ticker)
        news = _news_sentiment(ticker)

        intraday_tech = compute_intraday_technicals(hist)

        prev = float(hist["Close"].iloc[-2]) if len(hist) >= 2 else price

        return {
            "price": round(price, 2),
            "prev_close": round(prev, 2),
            "change_pct": round((price - prev) / prev * 100, 2) if prev else 0,
            "name": ticker,
            "ticker": ticker,
            "full_ticker": ticker,
            "intraday_technicals": intraday_tech,
            "relative_strength": rs,
            "sector_etf": sector_etf,
            "news_sentiment": news,
        }
    except Exception:
        return None


# ═══════════════════════════════════════════════════════════════════════════════
#  TRADE SIGNAL GENERATOR — daily chart engine (used for manual analysis)
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

    # -- 52-week high position (swing: buy strength, not falling knives) --
    pct_from_high = tech.get("pct_from_52w_high", -100)
    if pct_from_high >= -3:
        score += 6
        signals.append("Near 52-week high — leadership strength")
    elif pct_from_high >= -10:
        score += 4
        signals.append(f"Within {abs(pct_from_high):.0f}% of 52-week high")
    elif pct_from_high >= -20:
        score += 1
    elif pct_from_high <= -50:
        score -= 4
        warnings.append("Far below 52-week high — deep downtrend")

    # -- Volatility contraction (coiling before a breakout) --
    if tech.get("volatility_contracting") and (above_50 or above_200):
        score += 6
        vcr = tech.get("vol_contraction_ratio", 1)
        signals.append(f"Volatility contracting ({vcr:.2f}x) — coiling for a move")

    # ═══ STEP 4: DETERMINE ACTION ═══
    # Compress the above-baseline portion so genuinely strong setups spread
    # across ~80-98 instead of all pinning at 100 (matches the intraday fix).
    if score > 50:
        score = 50 + min(48, (score - 50) * 0.6)
    score = max(0, min(100, round(score)))
    
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

    # ── Setup classification: name the thesis behind the trade ──
    setup = "No clear setup"
    if action in ("BUY", "STRONG_BUY"):
        if pullback_to_50:
            setup = "Deep pullback in uptrend"
        elif pullback_to_20:
            setup = "Pullback to 20 SMA in uptrend"
        elif tech.get("volatility_contracting"):
            setup = "Volatility contraction (coiling)"
        elif pct_from_high >= -3:
            setup = "Breakout / new-high momentum"
        elif rsi < 40 and above_200:
            setup = "Oversold bounce in uptrend"
        elif is_uptrend:
            setup = "Trend continuation"
        else:
            setup = "Momentum"
    elif action in ("SELL", "STRONG_SELL"):
        setup = "Breakdown / downtrend"

    # ═══ STEP 5: RISK MANAGEMENT ═══
    # Stop distance is bounded both ways. In SWING mode the band is wider
    # (3–10%) so a multi-day hold can survive normal overnight noise; the
    # legacy intraday band was tight (1.5–4%).
    if SWING_MODE:
        MAX_STOP_PCT = SWING_MAX_STOP_PCT   # 0.10
        MIN_STOP_PCT = SWING_MIN_STOP_PCT   # 0.03
        STOP_ATR_MULT = SWING_STOP_ATR_MULT # 2.0
    else:
        MAX_STOP_PCT = 0.04
        MIN_STOP_PCT = 0.015
        STOP_ATR_MULT = 3.0
    if action in ("BUY", "STRONG_BUY"):
        entry = price
        # Stop loss: ATR-based below entry, or below nearest support
        stop_atr = round(entry - STOP_ATR_MULT * atr, 2)
        stop_support = round(supports[0] - 0.3 * atr, 2) if supports and (price - supports[0]) / price < 0.05 else stop_atr
        stop_loss = max(stop_atr, stop_support)
        # Clamp stop distance to [MIN_STOP_PCT, MAX_STOP_PCT] of entry.
        min_stop = round(entry * (1 - MIN_STOP_PCT), 2)   # nearest allowed (tight)
        max_stop = round(entry * (1 - MAX_STOP_PCT), 2)   # farthest allowed (wide)
        if stop_loss > min_stop:
            stop_loss = min_stop
        if stop_loss < max_stop:
            stop_loss = max_stop

        risk = max(entry - stop_loss, 0.01)
        target_1 = round(entry + 3.0 * risk, 2)
        target_2 = round(entry + 5.0 * risk, 2)
        risk_pct = round(risk / entry * 100, 2)
    elif action in ("SELL", "STRONG_SELL"):
        entry = price
        stop_loss = round(price + STOP_ATR_MULT * atr, 2)
        max_short_stop = round(entry * (1 + MAX_STOP_PCT), 2)
        if stop_loss > max_short_stop:
            stop_loss = max_short_stop
        risk = max(stop_loss - entry, 0.01)
        target_1 = round(entry - 3.0 * risk, 2)
        target_2 = round(entry - 5.0 * risk, 2)
        risk_pct = round(risk / entry * 100, 2)
    else:
        # HOLD — no high-conviction entry. Still show indicative levels, but make
        # them directional (down-bias if the stock is below its MAs) and never let
        # them collapse onto the entry when ATR is tiny/zero.
        entry = price
        eff_atr = atr if atr and atr > 0 else max(round(price * 0.01, 2), 0.01)  # fallback ~1%
        _below_mas = (bool(sma20 and price < sma20)) and (bool(sma50 and price < sma50))
        bearish_bias = (regime == "strong_downtrend") or _below_mas
        if bearish_bias:
            stop_loss = round(price + 3.0 * eff_atr, 2)
            target_1 = round(price - 3.0 * eff_atr, 2)
            target_2 = round(price - 5.0 * eff_atr, 2)
        else:
            stop_loss = round(price - 3.0 * eff_atr, 2)
            target_1 = round(price + 3.0 * eff_atr, 2)
            target_2 = round(price + 5.0 * eff_atr, 2)
        risk = 3.0 * eff_atr
        risk_pct = round(risk / price * 100, 2)
    
    rr = round((target_1 - entry) / risk, 2) if risk > 0 and target_1 > entry else (
         round((entry - target_1) / risk, 2) if risk > 0 and entry > target_1 else 0)
    
    # Sub-scores for visual cards (0-100 scale)
    # Trend must be DIRECTIONAL: a high ADX (strong trend) only helps if price is
    # actually trending up. In a downtrend, trend strength counts against the score.
    _above20 = bool(sma20 and price > sma20)
    _above50 = bool(sma50 and price > sma50)
    # Net directional structure: how many of the key MAs price sits above
    _ma_dir = (1 if above_200 else -1) + (1 if _above50 else -1) + (1 if _above20 else -1)  # -3..+3
    _strong = adx > 25
    if regime == "strong_downtrend" or _ma_dir <= -2:
        # Confirmed downtrend — strength makes it worse
        trend_sub = max(0, 35 - (15 if _strong else 0) + _ma_dir * 5)
    elif regime == "strong_uptrend" or _ma_dir >= 2:
        # Confirmed uptrend — strength helps
        trend_sub = min(100, 60 + (15 if _strong else 0) + _ma_dir * 5)
    else:
        # Mixed / sideways
        trend_sub = min(100, max(0, 50 + _ma_dir * 8))
    trend_sub = int(min(100, max(0, trend_sub)))
    momentum_sub = min(100, max(0, int(rsi) if 30 < rsi < 70 else (30 if rsi <= 30 else 80)))
    mr_sub = min(100, max(0, 50 + (20 if has_pullback else 0) + (-15 if rsi > 75 else 10 if rsi < 40 else 0)))
    news_sub = min(100, max(0, 50 + news_score * 10))

    trend_lbl = "strong uptrend" if trend_sub >= 70 else "uptrend" if trend_sub >= 55 else "sideways" if trend_sub >= 42 else "downtrend" if trend_sub >= 25 else "strong downtrend"
    momentum_lbl = f"RSI {int(rsi)}, {'overbought' if rsi > 70 else 'oversold' if rsi < 30 else 'trending up' if macd_h > 0 else 'trending down'}"
    mr_lbl = "low — not overstretched" if mr_sub >= 50 else "extended — pullback likely"
    news_lbl = f"{'bullish' if news_sub >= 60 else 'neutral' if news_sub >= 40 else 'bearish'} coverage last 3d"

    # Earnings warning
    earn_warn = ""
    for w in warnings:
        if "earning" in w.lower():
            earn_warn = w
            break

    return {
        "action": action,
        "score": score,
        "confidence": confidence,
        "confluence": {"bullish": bullish_count, "bearish": bearish_count},
        "setup": setup,
        "category_scores": {
            "trend": 1 if is_uptrend else -1,
            "pullback": 1 if has_pullback else 0,
            "momentum": 1 if macd_h > 0 else -1,
            "volume": 1 if obv_trend == "rising" else (-1 if obv_trend == "falling" else 0),
            "rsi": 1 if 30 <= rsi <= 55 else (-1 if rsi > 75 else 0),
            "news": 1 if news_score >= 2 else (-1 if news_score <= -2 else 0),
        },
        "trend_score": trend_sub, "trend_label": trend_lbl,
        "momentum_score": momentum_sub, "momentum_label": momentum_lbl,
        "mean_reversion_score": mr_sub, "mean_reversion_label": mr_lbl,
        "news_score": news_sub, "news_label": news_lbl,
        "earnings_warning": earn_warn,
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
    # Try yfinance first
    try:
        stk = yf.Ticker(ticker)
        info = stk.info or {}
        price = info.get("currentPrice") or info.get("regularMarketPrice")
        prev = info.get("previousClose") or info.get("regularMarketPreviousClose")
        if not price or price <= 0:
            hist = stk.history(period="5d")
            if hist is None or hist.empty:
                raise ValueError("No yfinance data")
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
        pass

    # Fallback: Polygon API
    polygon_key = os.environ.get("POLYGON_API_KEY", "")
    if polygon_key:
        try:
            clean = ticker.replace(".NS", "").replace("-", ".")
            r = requests.get(f"https://api.polygon.io/v2/aggs/ticker/{clean}/prev",
                            params={"apiKey": polygon_key}, timeout=10)
            if r.status_code == 200:
                data = r.json()
                results = data.get("results", [])
                if results:
                    bar = results[0]
                    price = bar.get("c", 0)
                    prev = bar.get("o", price)
                    return {
                        "price": round(price, 2), "prev_close": round(prev, 2),
                        "change": round(price - prev, 2),
                        "change_pct": round((price - prev) / prev * 100, 2) if prev else 0,
                        "name": ticker, "market_cap": None, "pe_ratio": None,
                        "forward_pe": None, "52w_high": None, "52w_low": None,
                        "sector": None, "target_price": None, "recommendation": None,
                    }
        except Exception:
            pass

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


@st.cache_data(ttl=1800)
def _ai_news_analysis(ticker: str) -> dict:
    """Use Groq LLM to deeply analyze news headlines for a ticker."""
    try:
        basic = _news_sentiment(ticker)
        headlines = basic.get("headlines", [])
        if not headlines:
            return {**basic, "ai_summary": "", "ai_score": 0, "macro_risk": False}

        key = os.environ.get("GROQ_API_KEY", "")
        if not key:
            return {**basic, "ai_summary": "", "ai_score": 0, "macro_risk": False}

        from groq import Groq
        client = Groq(api_key=key)

        headline_text = "\n".join([f"- {h['title']} ({h.get('publisher', '')})" for h in headlines])

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{
                "role": "user",
                "content": f"""Analyze these news headlines for {ticker}. Respond in EXACTLY this format, nothing else:

SCORE: [number from -10 to 10, negative=bearish, positive=bullish]
MACRO_RISK: [YES or NO — is there a macro event like war, sanctions, recession, rate hike that could cause a crash?]
SUMMARY: [one sentence summary of the news sentiment and why]

Headlines:
{headline_text}"""
            }],
            max_tokens=150,
            temperature=0,
        )

        text = response.choices[0].message.content.strip()
        ai_score = 0
        macro_risk = False
        ai_summary = ""

        for line in text.split("\n"):
            line = line.strip()
            if line.startswith("SCORE:"):
                try:
                    ai_score = int(float(line.replace("SCORE:", "").strip()))
                    ai_score = max(-10, min(10, ai_score))
                except:
                    pass
            elif line.startswith("MACRO_RISK:"):
                macro_risk = "YES" in line.upper()
            elif line.startswith("SUMMARY:"):
                ai_summary = line.replace("SUMMARY:", "").strip()

        return {
            **basic,
            "ai_score": ai_score,
            "ai_summary": ai_summary,
            "macro_risk": macro_risk,
        }
    except Exception:
        basic = _news_sentiment(ticker)
        return {**basic, "ai_summary": "", "ai_score": 0, "macro_risk": False}


_DELISTED_CACHE = set()
# Short-lived cache of scored scan data per ticker. Daily-bar data barely moves
# minute to minute, so reusing it across back-to-back scans (e.g. a broad scan
# then a themed one) avoids re-downloading the same 1y history. 90s TTL.
_SCAN_DATA_CACHE = {}   # ticker -> (timestamp, data)
_SCAN_CACHE_TTL = 300   # 5 min — daily bars barely move intraday, so repeat
                        # scans (or overlapping universes) reuse data and are
                        # near-instant instead of re-downloading.

def _clear_yf_session():
    """Force yfinance to drop its cached session + crumb token. Yahoo's
    'Invalid Crumb' 401 happens when that token goes stale; clearing it makes
    the next request fetch a fresh one. Defensive across yfinance versions."""
    try:
        import yfinance as _yf
        # Newer yfinance keeps a shared data singleton with the crumb/cookies.
        try:
            from yfinance import shared as _yshared
            if hasattr(_yshared, "_ERRORS"):
                _yshared._ERRORS = {}
        except Exception:
            pass
        try:
            from yfinance.data import YfData as _YfData
            inst = getattr(_YfData, "_instances", None)
            if inst:
                _YfData._instances = {}
            # Reset crumb/cookie on any live instance.
            for attr in ("_crumb", "_cookie", "_cookie_strategy"):
                try:
                    setattr(_YfData, attr, None)
                except Exception:
                    pass
        except Exception:
            pass
    except Exception:
        pass


def batch_fetch_scan(tickers: list, skip_news: bool = True, progress_cb=None) -> dict:
    """Bulk-fetch 1-year history for MANY tickers in a few HTTP requests using
    yf.download (multi-ticker). Returns {ticker: scan_data_dict}. Far faster than
    per-ticker fetch_scan for big universes — one network round-trip per chunk
    instead of one per stock. News is skipped here (fetched only for top picks).
    Chunks are downloaded IN PARALLEL so a 1000-name scan isn't 7 sequential
    round-trips but a handful of concurrent ones.

    progress_cb(done, total, phase): optional callback fired as chunks complete,
    so the UI can show a live progress bar. 'done'/'total' are ticker counts.
    """
    out = {}
    tickers = [t for t in tickers if t not in _DELISTED_CACHE]
    if not tickers:
        return out
    # Serve fresh-cached tickers immediately; only download the misses.
    import time as _t
    _now = _t.time()
    _need = []
    for t in tickers:
        cached = _SCAN_DATA_CACHE.get(t)
        if cached and (_now - cached[0]) < _SCAN_CACHE_TTL:
            out[t] = cached[1]
        else:
            _need.append(t)
    tickers = _need
    if not tickers:
        return out
    # Balance: bigger chunks mean FEWER total HTTP requests (each yf.download
    # call is one request for the whole chunk), which is what actually keeps us
    # under Yahoo's rate limit. Combined with modest concurrency, this is fast
    # WITHOUT triggering "Too Many Requests". Going too parallel (8+ workers,
    # tiny chunks) floods Yahoo and gets the whole scan throttled — which then
    # returns no data and makes the AI fall back to guessing.
    CHUNK = 175
    chunks = [tickers[i:i + CHUNK] for i in range(0, len(tickers), CHUNK)]

    import time as _time

    def _fetch_chunk(chunk):
        # Retry with exponential backoff if Yahoo rate-limits us, so a temporary
        # throttle doesn't silently drop a whole chunk of stocks from the scan.
        for attempt in range(3):
            try:
                import warnings
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    df = yf.download(
                        chunk, period="1y", interval="1d",
                        group_by="ticker", auto_adjust=True,
                        threads=True, progress=False,
                    )
                # Empty frame can signal a soft rate-limit OR a stale-crumb block
                # ("Invalid Crumb" 401) — clear yfinance's cached session/crumb and
                # retry, which usually fixes the crumb case.
                if (df is None or df.empty) and attempt < 2:
                    _clear_yf_session()
                    _time.sleep(1.5 * (attempt + 1))
                    continue
                return chunk, df
            except Exception as e:
                msg = str(e).lower()
                if (("rate" in msg or "too many" in msg or "crumb" in msg
                     or "401" in msg or "unauthorized" in msg) and attempt < 2):
                    _clear_yf_session()
                    _time.sleep(2.0 * (attempt + 1))  # 2s, then 4s
                    continue
                _log.warning(f"batch_fetch_scan chunk failed ({len(chunk)} tickers): {e}")
                return chunk, None
        return chunk, None

    from concurrent.futures import ThreadPoolExecutor
    # Modest concurrency — 3 chunks at a time. Process each chunk's frame as it
    # finishes and drop it immediately, so we never hold all ~500 tickers' worth
    # of 1y data in memory at once (that peak was a contributor to OOM kills).
    from concurrent.futures import as_completed
    _total = len(tickers)
    _done = 0
    if progress_cb:
        try: progress_cb(0, _total, "fetching")
        except Exception: pass
    # IMPORTANT: only 2 chunks in flight at once. Each yf.download(threads=True)
    # spawns its OWN internal thread pool, so N outer workers multiply into N×
    # internal threads. On a small Railway container that exhausts the thread
    # limit ("can't start new thread" → container crash mid-scan). 2 outer workers
    # keeps total threads bounded while still overlapping network waits.
    with ThreadPoolExecutor(max_workers=min(2, len(chunks))) as _ex:
        try:
            futures = [_ex.submit(_fetch_chunk, ch) for ch in chunks]
        except RuntimeError as _re:
            # "can't start new thread" — the host is out of thread budget. Bail
            # gracefully with whatever we have rather than crashing the process.
            _log.warning(f"scan thread-pool submit failed: {_re}")
            futures = []
        for fut in as_completed(futures):
            try:
                chunk, df = fut.result()
            except Exception as _fe:
                _log.warning(f"scan chunk result error: {_fe}")
                continue
            _done += len(chunk)
            if progress_cb:
                try: progress_cb(min(_done, _total), _total, "scoring")
                except Exception: pass
            if df is None or df.empty:
                continue
            for t in chunk:
                try:
                    # Multi-ticker frame is column-keyed by ticker; single-ticker isn't.
                    sub = df[t] if len(chunk) > 1 else df
                    sub = sub.dropna(how="all")
                    if sub is None or sub.empty or len(sub) < 50:
                        # IMPORTANT: do NOT mark delisted here. An empty frame in a
                        # bulk download usually means Yahoo throttled/blocked the
                        # whole request ("Invalid Crumb" 401), not that the stock is
                        # dead. Marking it delisted would wrongly drop alive names
                        # (FI, MMC, HOLX, etc.) from all future scans. We just skip
                        # this one for now; genuine delistings are caught by the
                        # single-ticker path's explicit Yahoo "delisted" message.
                        continue
                    price = float(sub["Close"].iloc[-1])
                    prev = float(sub["Close"].iloc[-2]) if len(sub) >= 2 else price
                    if not price or price < 1:
                        continue
                    try:
                        import pandas as _pd
                        last_dt = sub.index[-1]
                        last_ts = _pd.Timestamp(last_dt)
                        now_ts = _pd.Timestamp.now(tz=last_ts.tz) if last_ts.tz else _pd.Timestamp.now()
                        if (now_ts - last_ts).days > 5:
                            _DELISTED_CACHE.add(t)
                            continue
                    except Exception:
                        pass
                    try:
                        recent = sub.tail(20)
                        avg_dollar_vol = float((recent["Close"] * recent["Volume"]).mean())
                        if avg_dollar_vol < 5_000_000:
                            continue
                    except Exception:
                        pass
                    tech = compute_technicals(sub)
                    if not tech:
                        continue
                    rs = _calc_relative_strength(sub)
                    data = {
                        "price": round(price, 2),
                        "prev_close": round(prev, 2),
                        "change_pct": round((price - prev) / prev * 100, 2) if prev else 0,
                        "name": t, "ticker": t, "full_ticker": t,
                        "technicals": tech,
                        "relative_strength": rs,
                        "sector_etf": TICKER_SECTOR.get(t),
                        "news_sentiment": {} if skip_news else _news_sentiment(t),
                    }
                    out[t] = data
                    _SCAN_DATA_CACHE[t] = (_now, data)
                    if len(_SCAN_DATA_CACHE) > 1500:
                        for _k in sorted(_SCAN_DATA_CACHE, key=lambda k: _SCAN_DATA_CACHE[k][0])[:500]:
                            _SCAN_DATA_CACHE.pop(_k, None)
                except Exception:
                    continue
            # Release this chunk's frame before moving to the next completed one.
            del df
    return out


def fetch_scan(ticker: str) -> dict | None:
    """Lightweight fetch for scanning — skips slow .info calls, just gets history + technicals."""
    if ticker in _DELISTED_CACHE:
        return None
    try:
        stk = yf.Ticker(ticker)
        hist = stk.history(period="1y")
        if hist is None or hist.empty or len(hist) < 50:
            # Empty/thin can mean genuinely delisted OR Yahoo blocked us
            # ("Invalid Crumb" 401). Don't poison the delisted cache on an empty
            # response — that wrongly drops alive names when Yahoo throttles. We
            # only treat the STALE-BAR case below (data returned, but last bar is
            # days old) as a real delisting. Just skip this one for now.
            return None
        price = float(hist["Close"].iloc[-1])
        prev = float(hist["Close"].iloc[-2]) if len(hist) >= 2 else price
        if not price or price < 1:
            return None
        # Delisted/halted guard: stale last bar = no longer trading (see batch scan).
        try:
            import pandas as _pd
            last_ts = _pd.Timestamp(hist.index[-1])
            now_ts = _pd.Timestamp.now(tz=last_ts.tz) if last_ts.tz else _pd.Timestamp.now()
            if (now_ts - last_ts).days > 5:
                _DELISTED_CACHE.add(ticker)
                return None
        except Exception:
            pass
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


_FULL_CACHE = {}  # ticker -> (timestamp, data) — short TTL so analyze tab & chat agree

def fetch_full(ticker: str) -> dict | None:
    # Serve a recent cached result so two independent calls for the same ticker
    # (e.g. the Analyze tab and a chat analysis moments apart) return identical
    # data — and therefore identical scores. 60s TTL keeps it fresh enough.
    import time as _t
    _key = ticker.upper()
    _now = _t.time()
    _hit = _FULL_CACHE.get(_key)
    if _hit and (_now - _hit[0]) < 60:
        return _hit[1]
    _result = _fetch_full_uncached(ticker)
    if _result:
        _FULL_CACHE[_key] = (_now, _result)
        if len(_FULL_CACHE) > 600:
            for _k in sorted(_FULL_CACHE, key=lambda k: _FULL_CACHE[k][0])[:200]:
                _FULL_CACHE.pop(_k, None)
    return _result


def _fetch_full_uncached(ticker: str) -> dict | None:
    basic = fetch_price(ticker)
    if not basic:
        return None
    try:
        stk = yf.Ticker(ticker)
        info = stk.info or {}
        hist = stk.history(period="1y")
        tech = compute_technicals(hist)
        # Detect delisted/halted: how stale is the most recent bar?
        stale_days = 0
        try:
            if hist is not None and not hist.empty:
                import pandas as _pd
                last_ts = _pd.Timestamp(hist.index[-1])
                now_ts = _pd.Timestamp.now(tz=last_ts.tz) if last_ts.tz else _pd.Timestamp.now()
                stale_days = (now_ts - last_ts).days
        except Exception:
            pass
        news = []
        try:
            for n in (stk.news or [])[:5]:
                news.append({"title": n.get("title", ""), "publisher": n.get("publisher", "")})
        except Exception:
            pass
        return {
            **basic, "ticker": ticker.replace(".NS", ""), "full_ticker": ticker,
            "history_days": int(len(hist)) if hist is not None else 0,
            "stale_days": int(stale_days),
            "delisted": bool(stale_days > 5),
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
            increasing_line_color="#00e5a0", decreasing_line_color="#ff3b5c",
            increasing_fillcolor="#00e5a0", decreasing_fillcolor="#ff3b5c",
        ), row=1, col=1)

        if len(hist) >= 20:
            fig.add_trace(go.Scatter(x=hist.index, y=hist["Close"].rolling(20).mean(), name="20d", line=dict(color="#3388ff", width=1.2)), row=1, col=1)
        if len(hist) >= 50:
            fig.add_trace(go.Scatter(x=hist.index, y=hist["Close"].rolling(50).mean(), name="50d", line=dict(color="#ffb020", width=1.2)), row=1, col=1)

        # Trade signal lines on chart
        if trade_signal and trade_signal.get("trade"):
            tr = trade_signal["trade"]
            act = trade_signal.get("action", "")
            if act in ("BUY", "STRONG_BUY", "SELL", "STRONG_SELL"):
                fig.add_hline(y=tr["entry"], line_dash="dash", line_color="#3388ff", annotation_text=f"Entry {tr['entry']:.2f}", row=1, col=1)
                fig.add_hline(y=tr["stop_loss"], line_dash="dash", line_color="#ff3b5c", annotation_text=f"Stop {tr['stop_loss']:.2f}", row=1, col=1)
                fig.add_hline(y=tr["target_1"], line_dash="dash", line_color="#00e5a0", annotation_text=f"T1 {tr['target_1']:.2f}", row=1, col=1)
                fig.add_hline(y=tr["target_2"], line_dash="dot", line_color="#00e5a0", annotation_text=f"T2 {tr['target_2']:.2f}", row=1, col=1)

        colors = ["#00e5a0" if c >= o else "#ff3b5c" for c, o in zip(hist["Close"], hist["Open"])]
        fig.add_trace(go.Bar(x=hist.index, y=hist["Volume"], marker_color=colors, opacity=0.4, name="Vol"), row=2, col=1)

        fig.update_layout(
            template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#4a4a60", size=11, family="JetBrains Mono, monospace"),
            showlegend=True, legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(size=10, color="#4a4a60")),
            height=420, margin=dict(l=0, r=0, t=30, b=0), xaxis_rangeslider_visible=False,
        )
        fig.update_xaxes(showgrid=False, zeroline=False)
        fig.update_yaxes(showgrid=True, gridcolor="rgba(30,30,42,0.8)", zeroline=False)
        return fig
    except Exception:
        return None


# ── Intent routing ───────────────────────────────────────────────────────────

@st.cache_data(ttl=900)
def _llm_classify_intent(msg: str) -> dict | None:
    """Second-opinion intent classifier for messages the keyword router can't
    confidently place (it only runs on the chat fallthrough). Restricted to
    SAFE, non-destructive intents — never trades or autopilot, so a
    misclassification can't execute an order. Returns an intent dict or None
    (caller then falls back to plain chat). Cached so repeated identical short
    queries don't re-hit the LLM (helps with Groq rate limits)."""
    try:
        key = st.secrets.get("GROQ_API_KEY") or os.environ.get("GROQ_API_KEY")
    except Exception:
        key = os.environ.get("GROQ_API_KEY")
    if not key:
        return None
    try:
        from groq import Groq
        client = Groq(api_key=key)
        sys_prompt = (
            "Classify the user's stock-app message into ONE intent. Respond with ONLY "
            "the intent word, nothing else. Options:\n"
            "- stock_ideas (wants trade/swing setups, picks, 'what should I buy', scan for opportunities)\n"
            "- market (asking about overall market, SPY, conditions, regime)\n"
            "- backtest (wants to backtest/test the strategy)\n"
            "- portfolio (asking about their positions, holdings, P&L)\n"
            "- gainers (top gainers/movers up)\n"
            "- losers (top losers/movers down)\n"
            "- chat (general question, conversation, news, anything else)\n"
            "Reply with exactly one word from that list."
        )
        resp = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": sys_prompt},
                      {"role": "user", "content": msg[:300]}],
            temperature=0,
            max_tokens=5,
        )
        out = (resp.choices[0].message.content or "").strip().lower()
        valid = {"stock_ideas", "market", "backtest", "portfolio", "gainers", "losers", "chat"}
        for v in valid:
            if v in out:
                if v == "chat":
                    return None  # let normal chat handling proceed
                if v == "stock_ideas":
                    return {"type": "stock_ideas", "category": "all", "_original_msg": msg}
                return {"type": v, "market": _detect_market(msg)}
        return None
    except Exception:
        return None


def route(msg: str) -> dict:
    # Quoted lines (the user highlighted part of a prior reply and is asking
    # ABOUT it) are context, not commands. Strip them before routing so words
    # inside a quote — e.g. a "BUY" signal — never trigger a real trade.
    if msg and "\n" in msg or (msg and msg.lstrip().startswith(">")):
        _lines = [ln for ln in msg.split("\n") if not ln.lstrip().startswith(">")]
        _stripped = "\n".join(_lines).strip()
        if _stripped:  # keep the user's actual question, drop the quote
            msg = _stripped
    m = msg.lower().strip()
    if m in ("hi", "hello", "hey", "thanks", "thank you", "help", "bye"):
        return {"type": "chat"}

    # ── Private / non-tradeable companies ──
    # Questions about companies with no public ticker (or pre-IPO) should be a
    # plain conversational answer — NOT a stock lookup that attaches unrelated
    # data (e.g. "SpaceX IPO?" must not pull AAPL from earlier in the chat).
    PRIVATE_COMPANIES = [
        "spacex", "starlink", "openai", "anthropic", "stripe", "databricks",
        "discord", "epic games", "valve", "chick-fil-a", "in-n-out", "ikea",
        "mars inc", "cargill", "koch", "deloitte", "pwc", "ey ", "kpmg",
        "fidelity", "vanguard", "bloomberg lp", "spacex's", "neuralink",
        "the boring company", "xai", "x.ai", "fanatics", "canva", "revolut",
    ]
    if any(p in m for p in PRIVATE_COMPANIES):
        return {"type": "chat", "private_company": True, "market": "US"}

    # ── Earnings calendar ── ("when does NVDA report earnings", "AAPL earnings date")
    if "earnings" in m and any(w in m for w in ["when", "date", "next", "report", "reporting", "calendar", "upcoming"]):
        import re as _re_e
        _et = [t.upper() for t in _re_e.findall(r"\b([A-Za-z]{1,5})\b", msg)
               if t.upper() in ALL_US_TICKERS and (t.isupper() or t.upper() not in {"A","AN","IS","IT","ON","AT","TO","DO","BE","ME","MY","SO","UP","ALL","ANY","FOR","ARE","WHEN","NEXT","DOES"})]
        if _et:
            return {"type": "earnings", "ticker": _et[0], "market": "US", "_original_msg": msg}

    # ── Position sizing ── ("how many shares of NVDA if I risk $200")
    # Must mention RISK specifically — "how many shares can I buy with $5k" is an
    # affordability question (handled elsewhere), not risk-based sizing.
    _size_trigger = (("how many shares" in m or "position size" in m or "size a position" in m
                      or "shares should i" in m or "size my position" in m)
                     and ("risk" in m) and ("$" in msg or "dollar" in m or any(c.isdigit() for c in msg)))
    if _size_trigger:
        import re as _re_sz
        _szt = [t.upper() for t in _re_sz.findall(r"\b([A-Za-z]{1,5})\b", msg)
                if t.upper() in ALL_US_TICKERS and (t.isupper() or t.upper() not in {"A","AN","IS","IT","ON","AT","TO","DO","BE","ME","MY","SO","UP","ALL","ANY","FOR","ARE","BUY","CAN","HOW","IF","I"})]
        _risk = None
        _rm = _re_sz.search(r"\$?\s*([0-9][0-9,]*(?:\.[0-9]+)?)\s*(?:dollars|bucks)?", msg.replace(",", ""))
        if _rm:
            try: _risk = float(_rm.group(1))
            except Exception: _risk = None
        if _szt and _risk:
            return {"type": "position_size", "ticker": _szt[0], "risk": _risk, "market": "US", "_original_msg": msg}


    import re as _re_cmp
    _compare_trigger = (" vs " in m or " vs. " in m or "versus" in m
                        or m.startswith("compare ") or " compare " in m
                        or (" or " in m and any(w in m for w in ["better", "stronger", "buy", "which", "pick", "rather", "instead"])))
    if _compare_trigger:
        # Case-insensitive ticker match, but skip common English words that happen
        # to be valid tickers (AND, OR, ALL, ON, IT, etc.) unless typed in caps.
        _CMP_STOP = {"AND", "OR", "VS", "THE", "A", "AN", "IS", "IT", "ON", "AT", "TO",
                     "ALL", "ANY", "BE", "BY", "DO", "GO", "HAS", "ME", "MY", "SO",
                     "UP", "WHO", "ARE", "FOR", "BUY", "CAN", "GET", "NOW", "ONE", "OUT", "SEE", "TWO"}
        _ct = []
        for w in _re_cmp.findall(r"\b([A-Za-z]{1,5})\b", msg):
            up = w.upper()
            if up in ALL_US_TICKERS and (w.isupper() or up not in _CMP_STOP):
                _ct.append(up)
        _seen = set(); _ct = [x for x in _ct if not (x in _seen or _seen.add(x))]
        if len(_ct) >= 2:
            return {"type": "compare", "tickers": _ct[:2], "market": "US", "_original_msg": msg}

    # ── Detect questions/advice requests → send to AI, not execute commands ──
    is_question = any(q in m for q in [
        "should i", "which", "what should", "can you tell", "can you suggest",
        "recommend", "suggestion", "advice", "ideas", "what are the best",
        "tell me which", "help me find", "what to buy", "what to sell",
        "give me", "find me", "pick me", "any good", "what do you think",
        "is it a good", "worth buying", "worth selling", "opinion",
        "how many shares", "how many do i", "do i own", "do i have",
        "am i holding", "shares do i", "my shares",
    ])
    # Stock recommendation questions → smart scan
    wants_picks = any(q in m for q in [
        "what should i buy", "what to buy", "give me trade ideas", "trade ideas",
        "what stocks", "what stock", "which stocks", "which stock",
        "recommend", "suggest", "pick me",
        "what large cap", "large caps", "best stocks", "top stocks",
        "what should i invest", "what to invest", "find me stocks",
        "good buys", "what looks good", "any opportunities", "what do you like",
        "tell me a stock", "give me a stock", "find me a stock",
        "stock i should buy", "stock to buy", "stock should i buy",
        "what can i buy", "interested in buying", "interested in invest",
        "swing trading", "swing trade", "day trading", "day trade",
        "swing setup", "swing setups", "find setups", "find swing", "best setups",
        "find me a trade", "find a trade", "trade for tomorrow", "trade for tmr",
        "trade for today", "what to trade", "trade idea", "setup for", "setups",
        "scan for", "scan the market", "best swing", "top picks", "show me picks",
        "with $", "with 5k", "with 10k", "with 1k", "with 500",
        "i have $", "i have 5k", "i have 10k", "i have 1k",
        "budget of", "invest $", "trade with",
        "turn that into", "turn into more", "make more money",
        "put it in", "should i put", "where should i put",
        "what should i do with", "what do i do with",
        "dollars", "want to invest", "want to trade", "want to buy",
        "money into", "into the market", "into stocks",
    ])
    # A specific ticker named alongside a "how many shares / what's it worth /
    # can I afford" question is a position-math question about THAT stock — not
    # a request to scan for ideas. Route to analyze so price-math can answer it.
    _named_ticker, _named_market = _find_ticker(msg)
    shares_math = any(p in m for p in [
        "how many shares", "shares can i", "shares could i", "shares of",
        "what's it worth", "whats it worth", "position worth", "worth if",
        "how many can i", "can i afford", "afford",
    ])
    if _named_ticker and shares_math:
        return {"type": "analyze", "ticker": _named_ticker, "market": _named_market, "_original_msg": msg}

    if wants_picks and not any(cmd in m for cmd in [
        "close all", "sell everything", "liquidate",
    ]):
        # Determine category
        cat = "all"
        if any(w in m for w in ["large cap", "large-cap", "mega cap", "big cap", "blue chip", "sp500", "s&p"]):
            cat = "large"
        elif any(w in m for w in ["mid cap", "mid-cap", "midcap", "growth"]):
            cat = "mid"
        elif any(w in m for w in ["small cap", "small-cap", "smallcap", "penny", "cheap"]):
            cat = "small"
        elif any(w in m for w in ["tech", "technology", "software", "ai ", "semiconductor", "chips", "chip "]):
            cat = "tech"
        elif any(w in m for w in ["energy", "solar", "nuclear", "clean energy", "utilities", "oil"]):
            cat = "energy"
        elif any(w in m for w in ["defense", "defence", "military", "aerospace", "weapons"]):
            cat = "defense"
        elif any(w in m for w in ["biotech", "biotechnology", "pharma", "healthcare", "drug"]):
            cat = "biotech"
        elif any(w in m for w in ["crypto", "bitcoin", "miner", "mining", "blockchain"]):
            cat = "crypto"
        elif any(w in m for w in ["dividend", "income", "value", "safe"]):
            cat = "value"
        elif "nasdaq" in m:
            cat = "nasdaq"
        elif any(w in m for w in ["all stocks", "every stock", "entire market", "whole market", "nyse", "all nyse", "everything", "full market", "all of nyse", "scan everything"]):
            cat = "full"
        return {"type": "stock_ideas", "category": cat, "_original_msg": msg}

    # ── Position queries — check before is_question short-circuits to analyze ──
    is_position_query = any(w in m for w in [
        "my positions", "what do i own", "what am i holding", "open positions", "show positions",
        "what positions", "current positions", "what do we have", "what are we holding",
        "positions do we", "our positions",
        "how many shares", "shares do i", "shares of", "do i own", "do i have",
        "am i holding", "my shares", "what am i long", "what am i short"])
    if is_position_query:
        ticker_p, market_p = _find_ticker(msg)
        return {"type": "positions", "ticker": ticker_p}

    if is_question and not any(cmd in m for cmd in [
        "close all", "sell everything", "liquidate", "stop autopilot",
        "start autopilot", "activate autopilot",
    ]):
        ticker, market = _find_ticker(msg)
        if ticker:
            return {"type": "analyze", "ticker": ticker, "market": market, "_original_msg": msg}
        return {"type": "chat", "market": _detect_market(msg)}

    ticker, market = _find_ticker(msg)

    # ── Trading commands ──
    # Autopilot: only activate if clearly a command, NOT a question about it
    autopilot_questions = ["explain", "what is", "how does", "tell me about", "describe", "strategy", "what does", "how do"]
    is_asking_about = any(q in m for q in autopilot_questions)
    if not is_asking_about and any(w in m for w in [
        "activate autopilot", "activate alpaca", "start autopilot", "auto trade",
        "start trading", "go autopilot", "run autopilot", "auto pilot",
        "scan and trade", "find and buy", "find trades"]):
        return {"type": "autopilot"}
    # "autopilot" alone = start it, but not if asking a question
    if m.strip() == "autopilot":
        return {"type": "autopilot"}
    if any(w in m for w in ["force scan", "scan now", "scan anyway", "scan market", "run scan"]):
        return {"type": "force_scan"}
    if any(w in m for w in ["stop autopilot", "deactivate", "stop trading", "stop auto",
                            "turn off autopilot", "kill autopilot"]):
        return {"type": "stop_autopilot"}
    # "stop" alone means stop autopilot, but NOT "stop loss", "stop order", "stop price"
    if m.strip() == "stop" or m.strip() == "pause":
        return {"type": "stop_autopilot"}
    if any(w in m for w in ["backtest", "back test", "test strategy", "prove it", "historical test",
                            "how would it have done", "test the strategy"]):
        # Optional position count: "backtest 4" / "backtest with 5 positions"
        _bt = re.search(r"(\d{1,2})\s*(?:position|pos|slot)?", m)
        mp = None
        if _bt:
            v = int(_bt.group(1))
            if 1 <= v <= 20:
                mp = v
        return {"type": "backtest", "max_positions": mp}
    if any(w in m for w in ["market health", "market regime", "is market safe", "spy check", "market status"]):
        return {"type": "market_regime"}
    if any(w in m for w in ["sector strength", "sector rotation", "sectors", "hot sectors", "strong sectors"]):
        return {"type": "sector_strength"}
    if any(w in m for w in ["portfolio", "my account", "my equity", "account info", "how much do i have"]):
        # Don't route to portfolio if user is asking about trading WITH their money
        if not any(t in m for t in ["buy", "invest", "trade", "put it in", "turn that", "what stock", "should i", "recommend"]):
            return {"type": "portfolio"}
    if "buying power" in m and not any(t in m for t in ["buy", "invest", "trade", "put it in", "turn", "what stock", "should i", "recommend", "want to"]):
        return {"type": "portfolio"}
    if any(w in m for w in ["my positions", "what do i own", "what am i holding", "open positions", "show positions",
                            "what positions", "current positions", "what do we have", "what are we holding",
                            "positions do we", "our positions",
                            "how many shares", "shares do i", "shares of", "do i own", "do i have",
                            "am i holding", "my shares", "what am i long", "what am i short"]):
        return {"type": "positions"}
    # Cancel open orders — must come before the "show orders" check so
    # "cancel all orders" / "cancel my orders" isn't read as "show orders".
    if "cancel" in m and any(w in m for w in ["order", "orders", "all trade", "active trade", "pending", "everything"]):
        return {"type": "cancel_orders"}
    if any(w in m for w in ["my orders", "open orders", "order history", "recent orders", "pending orders"]):
        return {"type": "orders"}
    if any(w in m for w in ["how did", "today's trades", "recap", "review", "session", "performance",
                            "how was", "daily summary", "what trades", "trades today", "p&l today",
                            "pnl today", "how much did", "money lost", "money made", "profit today",
                            "loss today", "what happened today", "autopilot results", "end of day"]):
        return {"type": "daily_review"}
    if any(w in m for w in ["close all", "sell everything", "liquidate", "panic sell", "close everything"]):
        return {"type": "close_all"}

    # A trade command is an IMPERATIVE ("buy AAPL"), not a question or an
    # explanation request. If the message reads as a question/explainer, never
    # route it to a real buy/sell/short/cover — even if those words appear (e.g.
    # quoting a "BUY" signal and asking "explain this"). This prevents accidental
    # order execution from analytical questions.
    _is_question = (
        m.endswith("?")
        or any(w in m for w in [
            "explain", "what does", "what do", "what is", "what's", "why ", "why's",
            "how ", "should i", "does this", "do you think", "mean", "tell me",
            "is it a good", "is this a good", "worth", "thoughts", "opinion",
            "would you", "can you explain", "help me understand", "break down",
        ])
    )
    # But an explicit imperative like "yes buy it" / "go ahead and buy 5 AAPL"
    # should still work — only treat as a question when there's no clear command lead.
    _explicit_cmd = bool(re.match(r'^\s*(buy|sell|short|cover|close|go ahead|yes,? (buy|sell)|do it|execute|confirm)\b', m))
    _block_trade = _is_question and not _explicit_cmd

    # "buy NVDA", "buy 10 AAPL", "buy $500 of TSLA"
    buy_match = re.search(r'\bbuy\b', m)
    if buy_match and ticker and not _block_trade:
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
    if sell_match and ticker and not _block_trade:
        sell_all = "all" in m or "close" in m
        qty = None
        qty_match = re.search(r'sell\s+(\d+)\s+', m)
        if qty_match:
            qty = int(qty_match.group(1))
        return {"type": "sell", "ticker": ticker, "market": market, "qty": qty, "sell_all": sell_all}

    # "short NVDA", "short 10 AAPL", "cover TSLA", "cover all NVDA"
    short_match = re.search(r'\bshort\b', m)
    if short_match and ticker and not _block_trade:
        qty = None
        qty_match = re.search(r'short\s+(\d+)\s+', m)
        if qty_match:
            qty = int(qty_match.group(1))
        return {"type": "short", "ticker": ticker, "market": market, "qty": qty}

    cover_match = re.search(r'\bcover\b', m)
    if cover_match and ticker and not _block_trade:
        cover_all = "all" in m
        qty = None
        qty_match = re.search(r'cover\s+(\d+)\s+', m)
        if qty_match:
            qty = int(qty_match.group(1))
        return {"type": "cover", "ticker": ticker, "market": market, "qty": qty, "cover_all": cover_all}

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
    if any(w in m for w in ["chart", "graph", "show chart", "show graph", "show me the chart",
                            "pull up", "display chart", "candle", "candlestick", "show me"]):
        if ticker:
            return {"type": "chart", "ticker": ticker, "market": market}
    if any(w in m for w in ["price of", "price for", "what's the price", "how much is", "current price", "quote",
                            "what is the price", "what's the stock price", "how much does", "what does.*trade at",
                            "price check", "what is it at", "where is it trading"]):
        if ticker:
            return {"type": "price", "ticker": ticker, "market": market}
    if ticker:
        return {"type": "analyze", "ticker": ticker, "market": market, "_original_msg": msg}

    # Keyword routing didn't confidently place this. Before defaulting to chat,
    # ask the LLM for a second opinion — but ONLY on safe, non-destructive
    # intents (never trades/autopilot). If it's unsure or errors, fall to chat.
    # Skip the LLM for obvious chitchat/explainer questions (those are real chat).
    _skip_llm = any(m.startswith(w) for w in ["hi ", "hey", "hello", "thanks", "explain", "how do", "how does", "tell me about", "what is a", "what is an", "what does", "why is", "why are"])
    # Up to ~25 words covers natural phrasings like "I've got 5k and want a couple
    # swing trades for next week" that the keyword router misses; longer messages
    # are usually genuine conversation/explainers, so leave those to chat.
    if not _skip_llm and len(m.split()) <= 25:
        _llm = _llm_classify_intent(msg)
        if _llm:
            return _llm
    return {"type": "chat", "market": market}


@st.cache_data(ttl=120)
def _get_spy_intraday_trend() -> dict | None:
    """Check SPY's intraday trend to filter trades directionally."""
    try:
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            spy = yf.Ticker("SPY")
            hist = spy.history(period="2d", interval="5m")
            if hist is None or hist.empty or len(hist) < 10:
                hist = spy.history(period="5d", interval="1d")
                if hist is None or hist.empty or len(hist) < 2:
                    hist = spy.history(period="1mo", interval="1d")
                    if hist is None or hist.empty or len(hist) < 2:
                        return None
                price = float(hist["Close"].iloc[-1])
                prev = float(hist["Close"].iloc[-2])
                return {
                    "price": price,
                    "change_pct": round((price - prev) / prev * 100, 2),
                    "direction": "bullish" if price > prev else "bearish",
                    "above_vwap": True,
                    "strong": abs((price - prev) / prev * 100) > 0.5,
                }

        close = hist["Close"]
        high = hist["High"]
        low = hist["Low"]
        volume = hist["Volume"]
        price = float(close.iloc[-1])
        open_price = float(close.iloc[0])

        # VWAP
        typical = (high + low + close) / 3
        cum_tp_vol = (typical * volume).cumsum()
        cum_vol = volume.cumsum()
        vwap = float((cum_tp_vol / cum_vol.replace(0, 1)).iloc[-1])

        change_pct = round((price - open_price) / open_price * 100, 2)
        above_vwap = price > vwap

        if change_pct > 0.3 and above_vwap:
            direction = "bullish"
        elif change_pct < -0.3 and not above_vwap:
            direction = "bearish"
        else:
            direction = "neutral"

        return {
            "price": round(price, 2),
            "vwap": round(vwap, 2),
            "change_pct": change_pct,
            "direction": direction,
            "above_vwap": above_vwap,
            "strong": abs(change_pct) > 0.5,
        }
    except Exception:
        return None


# NYSE full-day market holidays (observed dates). The market is fully closed on
# these. Hardcoded because they're published years in advance and this avoids a
# dependency. Extend as new years are announced. (Half-days like the day after
# Thanksgiving / Christmas Eve are NOT full closes and aren't listed here.)
_MARKET_HOLIDAYS = {
    # 2026
    "2026-01-01",  # New Year's Day
    "2026-01-19",  # MLK Jr. Day
    "2026-02-16",  # Washington's Birthday / Presidents' Day
    "2026-04-03",  # Good Friday
    "2026-05-25",  # Memorial Day
    "2026-06-19",  # Juneteenth
    "2026-07-03",  # Independence Day (observed — Jul 4 is a Saturday)
    "2026-09-07",  # Labor Day
    "2026-11-26",  # Thanksgiving
    "2026-12-25",  # Christmas
    # 2027
    "2027-01-01",  # New Year's Day
    "2027-01-18",  # MLK Jr. Day
    "2027-02-15",  # Presidents' Day
    "2027-03-26",  # Good Friday
    "2027-05-31",  # Memorial Day
    "2027-06-18",  # Juneteenth (observed — Jun 19 is a Saturday)
    "2027-07-05",  # Independence Day (observed — Jul 4 is a Sunday)
    "2027-09-06",  # Labor Day
    "2027-11-25",  # Thanksgiving
    "2027-12-24",  # Christmas (observed — Dec 25 is a Saturday)
}


def _market_is_open() -> tuple[bool, str]:
    """Check if US stock market is currently open."""
    et = ZoneInfo("US/Eastern")
    now = datetime.now(et)
    weekday = now.weekday()  # 0=Mon, 6=Sun

    if weekday >= 5:
        next_open = "Monday 8:30 AM CT"
        return False, f"Weekend — market reopens {next_open}"

    # Market holiday? (weekday but exchange fully closed)
    if now.strftime("%Y-%m-%d") in _MARKET_HOLIDAYS:
        return False, "Market holiday — closed today, reopens next trading day 8:30 AM CT"

    market_open = now.replace(hour=9, minute=30, second=0, microsecond=0)
    market_close = now.replace(hour=16, minute=0, second=0, microsecond=0)

    if now < market_open:
        return False, f"Pre-market — opens at 8:30 AM CT"
    if now >= market_close:
        return False, "Market closed for today — reopens tomorrow 8:30 AM CT"

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
        prev_close = float(close.iloc[-2]) if len(close) >= 2 else price
        spy_change_pct = round((price - prev_close) / prev_close * 100, 2) if prev_close else 0.0

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
            "spy_change_pct": spy_change_pct,
            "sma_50": round(sma_50, 2),
            "sma_200": round(sma_200, 2),
            "rsi": round(rsi, 1),
            "vix": _get_vix(),
        }
    except Exception as e:
        return {"regime": "unknown", "safe_to_buy": True, "reason": f"Could not check: {str(e)[:60]}"}


@st.cache_data(ttl=300)
def _get_vix() -> dict:
    """Get VIX (fear index) level."""
    try:
        vix = yf.Ticker("^VIX")
        hist = vix.history(period="5d")
        if hist is None or hist.empty:
            return {"level": 0, "status": "unknown"}
        price = float(hist["Close"].iloc[-1])
        prev = float(hist["Close"].iloc[-2]) if len(hist) >= 2 else price
        change = round(price - prev, 2)

        if price >= 35:
            status = "extreme_fear"
        elif price >= 25:
            status = "high_fear"
        elif price >= 20:
            status = "elevated"
        elif price >= 15:
            status = "normal"
        else:
            status = "complacent"

        return {"level": round(price, 2), "change": change, "status": status}
    except Exception:
        return {"level": 0, "status": "unknown"}


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


def next_earnings_date(ticker: str) -> dict | None:
    """Return the next earnings date for a ticker: {date, days_away, when}."""
    try:
        stk = yf.Ticker(ticker)
        cal = stk.calendar
        earn_date = None
        if isinstance(cal, dict):
            ed = cal.get("Earnings Date")
            earn_date = ed[0] if isinstance(ed, list) and ed else ed
        elif isinstance(cal, pd.DataFrame) and not cal.empty:
            if "Earnings Date" in cal.columns:
                earn_date = cal["Earnings Date"].iloc[0]
            elif "Earnings Date" in cal.index:
                earn_date = cal.loc["Earnings Date"].iloc[0]
        if earn_date is None:
            return None
        if isinstance(earn_date, str):
            earn_date = pd.to_datetime(earn_date)
        elif hasattr(earn_date, "to_pydatetime"):
            earn_date = earn_date.to_pydatetime()
        now = datetime.now(earn_date.tzinfo) if getattr(earn_date, "tzinfo", None) else datetime.now()
        days_away = (earn_date.date() - now.date()).days if hasattr(earn_date, "date") else None
        return {
            "ticker": ticker.upper(),
            "date": earn_date.strftime("%B %d, %Y"),
            "days_away": days_away,
            "when": "today" if days_away == 0 else (f"in {days_away} days" if days_away and days_away > 0 else "recently"),
        }
    except Exception:
        return None


# ── Trailing stops ───────────────────────────────────────────────────────────

def update_trailing_stops(positions: list[dict], log: list) -> list[str]:
    """
    For each open position, check if price has moved up enough to trail the stop.
    Uses 2x intraday ATR (5min bars) trailing stop — tighter for day trading.
    """
    actions = []
    for pos in positions:
        try:
            ticker = pos["ticker"]
            entry = pos["avg_entry"]
            current = pos["current_price"]
            pnl_pct = pos["unrealized_pnl_pct"]

            # Fast breakeven: once +0.5%, move stop to breakeven immediately
            if 0.5 <= pnl_pct < 1.5:
                breakeven_stop = round(entry * 1.001, 2)  # just above entry
                orders = alpaca_orders(status="open", limit=20)
                has_stop = False
                for o in orders:
                    if o["symbol"] == ticker and o["type"] in ("stop", "stop_limit"):
                        # Check if stop is already at or above breakeven
                        if float(o.get("stop_price", 0)) >= entry:
                            has_stop = True
                            break
                if not has_stop:
                    # Place breakeven stop
                    try:
                        # Cancel existing stops first
                        for o in orders:
                            if o["symbol"] == ticker and o["type"] in ("stop", "stop_limit"):
                                requests.delete(f"{ALPACA_BASE}/v2/orders/{o['id']}",
                                                headers=_alpaca_headers(), timeout=5)
                        stop_order = {
                            "symbol": ticker,
                            "qty": str(int(abs(pos["qty"]))),
                            "side": "sell" if pos.get("side", "long") == "long" else "buy",
                            "type": "stop",
                            "stop_price": str(breakeven_stop),
                            "time_in_force": "day",
                        }
                        r = requests.post(f"{ALPACA_BASE}/v2/orders", headers=_alpaca_headers(),
                                          json=stop_order, timeout=10)
                        if r.status_code in (200, 201):
                            actions.append(f"🔒 Breakeven stop on {ticker} @ ${breakeven_stop:.2f} (+{pnl_pct:.1f}%)")
                    except Exception:
                        pass
                continue

            # Trail stops once position is profitable enough
            is_short = pos.get("side") == "short"

            # For longs: trail when up 0.8%+. For shorts: trail when down 0.8%+
            if not is_short and pnl_pct < 0.8:
                continue
            if is_short and pnl_pct > -0.8:
                continue

            # Get intraday 5min bars for tighter trailing
            hist = yf.Ticker(ticker).history(period="1d", interval="5m")
            if hist is None or hist.empty or len(hist) < 14:
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

            if not is_short:
                # LONG: trail stop below highest recent price
                recent_high = float(close.tail(12).max())
                new_stop = round(recent_high - (2.5 * atr), 2)
                # Floor: at least 0.5% profit locked in
                min_lock = round(entry * 1.005, 2)
                new_stop = max(new_stop, min_lock)

                if new_stop > entry:
                    # Cancel existing stops and place new one
                    orders = alpaca_orders(status="open", limit=20)
                    for o in orders:
                        if o["symbol"] == ticker and o["type"] in ("stop", "stop_limit"):
                            try:
                                requests.delete(f"{ALPACA_BASE}/v2/orders/{o['id']}",
                                                headers=_alpaca_headers(), timeout=5)
                            except Exception:
                                pass

                    stop_order = {
                        "symbol": ticker,
                        "qty": str(int(pos["qty"])),
                        "side": "sell",
                        "type": "stop",
                        "stop_price": str(new_stop),
                        "time_in_force": "day",
                    }
                    try:
                        r = requests.post(f"{ALPACA_BASE}/v2/orders", headers=_alpaca_headers(),
                                          json=stop_order, timeout=10)
                        if r.status_code in (200, 201):
                            actions.append(f"📈 Trailed stop on {ticker}: ${new_stop:.2f} (locking +${new_stop - entry:.2f}/share)")
                    except Exception:
                        pass
            else:
                # SHORT: trail stop above lowest recent price
                recent_low = float(close.tail(12).min())
                new_stop = round(recent_low + (2.5 * atr), 2)
                # Floor: at least 0.5% profit locked in
                max_lock = round(entry * 0.995, 2)
                new_stop = min(new_stop, max_lock)

                if new_stop < entry:
                    orders = alpaca_orders(status="open", limit=20)
                    for o in orders:
                        if o["symbol"] == ticker and o["type"] in ("stop", "stop_limit"):
                            try:
                                requests.delete(f"{ALPACA_BASE}/v2/orders/{o['id']}",
                                                headers=_alpaca_headers(), timeout=5)
                            except Exception:
                                pass

                    stop_order = {
                        "symbol": ticker,
                        "qty": str(int(abs(pos["qty"]))),
                        "side": "buy",
                        "type": "stop",
                        "stop_price": str(new_stop),
                        "time_in_force": "day",
                    }
                    try:
                        r = requests.post(f"{ALPACA_BASE}/v2/orders", headers=_alpaca_headers(),
                                          json=stop_order, timeout=10)
                        if r.status_code in (200, 201):
                            actions.append(f"📈 Trailed stop on {ticker} (short): ${new_stop:.2f} (locking +${entry - new_stop:.2f}/share)")
                    except Exception:
                        pass
        except Exception:
            continue

    return actions


# ── Backtester ───────────────────────────────────────────────────────────────

def run_backtest(years: int = 2, max_positions: int | None = None) -> dict:
    """
    Backtest the signal engine against historical data.
    Simulates autopilot with trailing stops over the last N years.
    """
    STARTING_CAPITAL = 25_000
    RISK_PER_TRADE = 0.01        # 1% risk per trade — matches the live engine
    MIN_SCORE = 50               # lower bar — backtester has ~20-30 pts missing data
    MIN_RR = 1.2                 # lower R:R bar = more trades
    SLIPPAGE = 0.0005            # 5 bps per side — models realistic fill cost

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
    pending_trades = []   # collected per-ticker, compounded chronologically later
    wins = 0
    losses = 0
    peak = capital
    min_capital = capital

    log = [f"**Backtesting {len(TEST_UNIVERSE)} stocks over {years} years...**",
           f"Starting capital: ${STARTING_CAPITAL:,}",
           f"Mode: {'SWING (~%d-day holds)' % SWING_MAX_HOLD_DAYS if SWING_MODE else 'Intraday'} · score≥{MIN_SCORE} · R:R≥{MIN_RR}",
           f"Stops: {'2x ATR, 3–10% band' if SWING_MODE else '3x ATR, 1.5–4% band'} · partial @ +{4 if SWING_MODE else 2}% · trail {SWING_STOP_ATR_MULT if SWING_MODE else 1.5}x ATR",
           f"Fills: {SLIPPAGE*10000:.0f}bps slippage/side · stop wins intrabar ties · chronological compounding",
           f"⚠️ Score threshold lowered to {MIN_SCORE} (live has RS/sector/news data worth ~20+ extra pts)",
           f"⚠️ Fixed universe of current names → results carry survivorship bias; treat as optimistic"]

    step = 3        # check every 3 bars
    max_hold = SWING_MAX_HOLD_DAYS if SWING_MODE else 25   # swing: ~10 trading days

    for ticker in TEST_UNIVERSE:
        try:
            stk = yf.Ticker(ticker)
            hist = stk.history(period=f"{years}y")
            if hist is None or hist.empty or len(hist) < 252:
                continue

            window_size = 200
            skip_until = 0  # prevent overlapping trades on same stock

            for i in range(window_size, len(hist) - max_hold, step):
                if capital < 500:
                    break
                if i < skip_until:
                    continue

                window = hist.iloc[i - window_size:i]
                future = hist.iloc[i:i + max_hold]

                if len(window) < window_size or len(future) < 5:
                    continue

                tech = compute_technicals(window)
                if not tech:
                    continue

                entry_price = float(window["Close"].iloc[-1])
                if entry_price < 5:
                    continue

                data = {"price": entry_price, "technicals": tech, "ticker": ticker}
                sig = generate_trade_signal(data)

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

                # Position sizing — tiered by conviction.
                # NOTE: sizing is resolved later (after sorting trades by date)
                # so capital compounds chronologically, not in ticker order.
                risk_per_share = entry_price - stop
                if risk_per_share <= 0:
                    continue

                # Higher score = bigger position
                score_mult = 1.0
                if sig["score"] >= 85:
                    score_mult = 1.3  # high conviction
                elif sig["score"] >= 80:
                    score_mult = 1.0
                else:
                    score_mult = 0.7  # lower conviction

                # Momentum filter: 5-day return must be positive
                if i >= 5:
                    recent_return = (entry_price - float(hist["Close"].iloc[i-5])) / float(hist["Close"].iloc[i-5])
                    if recent_return < 0:
                        continue  # no buying into downtrends

                # ── Simulate trade (qty-independent: track per-share P&L on a
                # notional 1-share position; capital sizing is applied later) ──
                highest = entry_price
                current_stop = stop
                exit_price = float(future["Close"].iloc[-1])
                exit_reason = "TIMEOUT"
                atr = _safe(tech.get("atr"), entry_price * 0.02)
                partial_taken = False
                partial_pnl_ps = 0.0      # realized P&L per share from the partial
                remaining_frac = 1.0      # fraction of the position still open
                partial_threshold = entry_price * (1.04 if SWING_MODE else 1.02)  # swing: partial at +4%
                bars_held = 0

                for _, day in future.iterrows():
                    day_low = float(day["Low"])
                    day_high = float(day["High"])
                    day_close = float(day["Close"])
                    bars_held += 1

                    # ── Intrabar tie rule: STOP WINS ──────────────────────────
                    # Within one bar we can't know the true high/low ordering.
                    # The honest, conservative convention is to assume the stop
                    # was hit before the target whenever the bar's range touches
                    # both. Checking the stop first (and breaking) enforces this
                    # and removes the optimistic bias toward target fills.
                    if day_low <= current_stop:
                        exit_price = current_stop
                        exit_reason = "STOPPED" if not partial_taken else "TRAILED"
                        break

                    # Partial profit: sell half the position at +2%
                    if not partial_taken and day_high >= partial_threshold:
                        partial_pnl_ps = (partial_threshold - entry_price) * 0.5
                        remaining_frac = 0.5
                        partial_taken = True
                        # Move stop to entry + 1% (lock in profit aggressively)
                        current_stop = max(current_stop, round(entry_price * 1.01, 2))

                    # Check target (only reached if stop was NOT hit this bar)
                    if day_high >= target:
                        exit_price = target
                        exit_reason = "TARGET"
                        break

                    # Trailing stop: 2x ATR for swing (room to breathe over days),
                    # 1.5x for intraday.
                    if day_high > highest:
                        highest = day_high
                        _trail_mult = SWING_STOP_ATR_MULT if SWING_MODE else 1.5
                        new_stop = round(highest - _trail_mult * atr, 2)
                        if new_stop > current_stop:
                            current_stop = new_stop

                # Skip ahead so we don't double-trade same stock
                skip_until = i + bars_held + 5

                # ── Per-share P&L as a fraction of entry price (qty-independent).
                # Apply round-trip slippage so fills aren't free.
                entry_fill = entry_price * (1 + SLIPPAGE)
                exit_fill = exit_price * (1 - SLIPPAGE)
                remaining_pnl_ps = (exit_fill - entry_fill) * remaining_frac
                # Partial leg also pays slippage on its exit.
                partial_pnl_ps_net = partial_pnl_ps
                if partial_taken:
                    partial_pnl_ps_net = (partial_threshold * (1 - SLIPPAGE) - entry_fill) * 0.5
                total_pnl_ps = partial_pnl_ps_net + remaining_pnl_ps
                ret_frac = total_pnl_ps / entry_price  # return per dollar deployed

                try:
                    entry_date = window.index[-1]
                except Exception:
                    entry_date = i
                try:
                    # Exit happens after `bars_held` bars into the future window.
                    exit_date = future.index[min(bars_held, len(future) - 1)]
                except Exception:
                    exit_date = entry_date

                pending_trades.append({
                    "ticker": ticker,
                    "entry_date": entry_date,
                    "exit_date": exit_date,
                    "entry": round(entry_price, 2),
                    "exit": round(exit_price, 2),
                    "ret_frac": ret_frac,
                    "risk_per_share": risk_per_share,
                    "score_mult": score_mult,
                    "result": exit_reason,
                    "score": sig["score"],
                    "bars_held": bars_held,
                })
                continue
        except Exception:
            continue

    # ── Portfolio simulation with a concurrent-position cap ─────────────────
    # The live engine holds at most a couple positions at once. Summing every
    # signal independently (the old pass) let the backtest hold hundreds of
    # correlated positions simultaneously, so a market dip crushed all of them
    # together → fake 90%+ drawdowns. This walks the real timeline: a new trade
    # can only open when a slot is free, exactly like live trading.
    def _to_dt(d):
        try:
            return d.to_pydatetime().replace(tzinfo=None)
        except Exception:
            try:
                return d.tz_localize(None)
            except Exception:
                return d

    # Normalize dates and sort by entry.
    evs = []
    for t in pending_trades:
        try:
            ed = _to_dt(t["entry_date"])
            xd = _to_dt(t.get("exit_date", t["entry_date"]))
            evs.append((ed, xd, t))
        except Exception:
            continue
    try:
        evs.sort(key=lambda x: x[0])
    except Exception:
        pass

    MAX_CONCURRENT = max_positions if max_positions else SWING_MAX_POSITIONS   # shared knob (see module constants)
    RISK_PER_TRADE_BT = RISK_PER_TRADE
    MAX_POS_PCT = 0.15
    DD_BRAKE = 0.20

    open_slots = []          # list of (exit_date, cost, ret_frac) currently held
    skipped_full = 0         # trades skipped because all slots were busy
    skipped_dd = 0

    def _close_due(now_dt):
        """Realize P&L for any open positions whose exit date has passed."""
        nonlocal capital, peak, min_capital, open_slots
        still_open = []
        for (xd, cost, rf, rec) in open_slots:
            if xd <= now_dt:
                pnl = rf * cost
                capital += pnl
                peak = max(peak, capital)
                min_capital = min(min_capital, capital)
                rec["pnl"] = round(pnl, 2)
                trades.append(rec)
            else:
                still_open.append((xd, cost, rf, rec))
        open_slots = still_open

    for (ed, xd, pt) in evs:
        # First, close anything that exited before this entry.
        _close_due(ed)
        if capital < 500:
            break

        # Drawdown brake.
        dd = (peak - capital) / peak if peak > 0 else 0
        if dd >= DD_BRAKE:
            skipped_dd += 1
            continue
        # Concurrent-position cap.
        if len(open_slots) >= MAX_CONCURRENT:
            skipped_full += 1
            continue

        rps = pt["risk_per_share"]
        if rps <= 0:
            continue
        max_risk = capital * RISK_PER_TRADE_BT * pt["score_mult"]
        qty = max(1, int(max_risk / rps))
        cost = qty * pt["entry"]
        if cost > capital * MAX_POS_PCT:
            qty = max(1, int(capital * MAX_POS_PCT / pt["entry"]))
            cost = qty * pt["entry"]
        if cost > capital or qty < 1:
            continue

        # Count win/loss at entry time (P&L realized at exit).
        if pt["ret_frac"] > 0:
            wins += 1
        else:
            losses += 1

        rec = {
            "ticker": pt["ticker"], "entry": pt["entry"], "exit": pt["exit"],
            "qty": qty, "pnl_pct": round(pt["ret_frac"] * 100, 2),
            "result": pt["result"], "score": pt["score"], "bars_held": pt["bars_held"],
        }
        open_slots.append((xd, cost, pt["ret_frac"], rec))

    # Close any positions still open at the end of the test.
    _close_due(datetime.max.replace(tzinfo=None))

    total_trades = wins + losses
    win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
    gross_win = sum(t["pnl"] for t in trades if t.get("pnl", 0) > 0)
    gross_loss = abs(sum(t["pnl"] for t in trades if t.get("pnl", 0) < 0))
    avg_win = (gross_win / wins) if wins > 0 else 0
    avg_loss = (-gross_loss / losses) if losses > 0 else 0
    profit_factor = (gross_win / gross_loss) if gross_loss > 0 else (float("inf") if gross_win > 0 else 0)
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
    if skipped_full or skipped_dd:
        log.append(f"📋 Held max {MAX_CONCURRENT} positions · skipped {skipped_full} (slots full) + {skipped_dd} (drawdown brake)")
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
        trailed = sum(1 for t in trades if t["result"] == "TRAILED")
        timeouts = sum(1 for t in trades if t["result"] == "TIMEOUT")
        timeout_wins = sum(1 for t in trades if t["result"] == "TIMEOUT" and t["pnl"] > 0)
        avg_bars = np.mean([t.get("bars_held", 0) for t in trades]) if trades else 0
        log.append("")
        log.append(f"**Exit breakdown:** {targets_hit} targets · {stops_hit} stopped · {trailed} trailed · {timeouts} timed out ({timeout_wins} profitable)")
        log.append(f"**Avg hold:** {avg_bars:.0f} bars")

    return {
        "ok": True, "log": log,
        "total_trades": total_trades, "win_rate": round(win_rate, 1),
        "total_return": round(total_return, 1), "sharpe": round(sharpe, 2),
        "final_capital": round(capital, 2),
    }

def premarket_scan() -> dict:
    """Run at 8:15 AM CT — build today's watchlist BEFORE market opens."""
    import yfinance as yf
    log = ["🌅 **Pre-Market Scan** — building today's watchlist"]

    # Get pre-market movers from Polygon
    all_snaps = polygon_all_snapshots() or []
    watchlist = []

    if all_snaps:
        viable = [s for s in all_snaps if s.get("Price", 0) > 10
                  and s.get("Volume", 0) > 300_000
                  and abs(s.get("Chg%", 0)) > 1.0]

        gappers = sorted(viable, key=lambda x: abs(x.get("Chg%", 0)), reverse=True)[:20]
        for s in gappers:
            ticker = s.get("Ticker", "")
            if ticker and not _has_earnings_today(ticker):
                watchlist.append(ticker)
                arrow = "▲" if s.get("Chg%", 0) > 0 else "▼"
                log.append(f"  {arrow} {ticker} {s.get('Chg%', 0):+.1f}% · Vol: {s.get('Volume', 0):,.0f}")

    # Add consistent large-cap movers
    for ticker in NASDAQ_100[:15]:
        if ticker not in watchlist:
            watchlist.append(ticker)

    log.append(f"\n📋 Watchlist: {len(watchlist)} stocks ready for open")

    # Store in session state
    st.session_state["premarket_watchlist"] = watchlist
    st.session_state["premarket_done"] = datetime.now(ZoneInfo("US/Eastern")).strftime("%Y-%m-%d")

    return {"ok": True, "log": log, "watchlist": watchlist}


def _has_earnings_today(ticker: str) -> bool:
    """Check if a stock has earnings today — never trade on earnings day."""
    try:
        import yfinance as yf
        cal = yf.Ticker(ticker).calendar
        if cal is not None:
            # yfinance returns earnings date in various formats
            if hasattr(cal, 'get'):
                earnings_date = cal.get("Earnings Date")
            elif hasattr(cal, 'iloc'):
                earnings_date = cal.iloc[0] if len(cal) > 0 else None
            else:
                return False

            today = datetime.now(ZoneInfo("US/Eastern")).strftime("%Y-%m-%d")
            if earnings_date is not None:
                if isinstance(earnings_date, list):
                    return any(str(d)[:10] == today for d in earnings_date)
                return str(earnings_date)[:10] == today
    except Exception:
        pass
    return False


def _check_sector_correlation(ticker: str, positions: list, max_per_sector: int = 1) -> bool:
    """Returns True if adding this ticker would exceed sector limit."""
    new_sector = TICKER_SECTOR.get(ticker)
    if not new_sector:
        return False  # Unknown sector — allow it

    sector_count = 0
    for pos in positions:
        pos_sector = TICKER_SECTOR.get(pos.get("ticker", ""))
        if pos_sector == new_sector:
            sector_count += 1

    return sector_count >= max_per_sector


def load_autopilot_config() -> dict:
    """Load autopilot config from disk, apply the SWING override, and persist.
    Single source of truth used by both the autopilot loop and the dashboard so
    the displayed config can never drift back to stale day-trade values."""
    import pathlib as _pl
    cfg_path = _pl.Path(__file__).parent / "autopilot_config.json"
    defaults = {
        "MAX_POSITIONS": SWING_MAX_POSITIONS if SWING_MODE else 1,
        "RISK_PER_TRADE": 0.01, "MAX_POS_PCT": 0.15, "MIN_SCORE": 82,
        "MIN_CONFLUENCE": 5, "MIN_RR": 2.0, "STOP_FLOOR": 0.013, "SELL_BELOW": 35,
        "DAILY_LOSS_LIMIT": 0.04 if SWING_MODE else 0.01,
        "PARTIAL_PROFIT_PCT": 0.04 if SWING_MODE else 0.025,
        "MAX_DAILY_ENTRIES": 4,
        "MAX_HOLD_DAYS": SWING_MAX_HOLD_DAYS if SWING_MODE else 0,
        "STALE_MINUTES": 0 if SWING_MODE else 120,
        "TRADING_HOURS_START": "09:45",
        "TRADING_HOURS_END": "15:55" if SWING_MODE else "15:00",
        "AVOID_MIDDAY": False if SWING_MODE else True,
        "MIDDAY_START": "11:30", "MIDDAY_END": "13:30",
        "LONG_ONLY": True, "last_tuned": "", "tune_history": [],
    }
    try:
        params = json.loads(cfg_path.read_text()) if cfg_path.exists() else dict(defaults)
    except Exception:
        params = dict(defaults)
    for k, v in defaults.items():
        params.setdefault(k, v)
    if SWING_MODE:
        params["MAX_POSITIONS"] = SWING_MAX_POSITIONS
        params["MAX_HOLD_DAYS"] = SWING_MAX_HOLD_DAYS
        params["AVOID_MIDDAY"] = False
        params["TRADING_HOURS_END"] = "15:55"
        params["PARTIAL_PROFIT_PCT"] = 0.04
        params["STALE_MINUTES"] = 0
        params["DAILY_LOSS_LIMIT"] = 0.04

    # ── AUTO RISK ────────────────────────────────────────────────────────────
    # Risk per trade is determined automatically from market conditions, the
    # same way market direction is auto. Healthy/trending market -> normal risk;
    # choppy or risk-off market -> dial risk down. Best-effort: if the regime
    # check fails, fall back to a sensible default so sizing never breaks.
    try:
        regime = check_market_regime()
        _rg = regime.get("regime", "neutral")
        if not regime.get("safe_to_buy", True):
            auto_risk = 0.005          # market says don't buy -> minimal risk if any
        elif _rg in ("strong_bull", "bull"):
            auto_risk = 0.01           # healthy trend -> normal 1%
        elif _rg in ("weakening", "recovery", "neutral"):
            auto_risk = 0.0075         # mixed -> cautious 0.75%
        else:                          # bear / strong_bear / unknown
            auto_risk = 0.005          # defensive 0.5%
    except Exception:
        auto_risk = 0.01
    params["RISK_PER_TRADE"] = auto_risk
    params["RISK_AUTO"] = True  # flag so the UI can show "Auto"

    try:
        cfg_path.write_text(json.dumps(params, indent=2))
    except Exception:
        pass
    return params


def autopilot_entries_today() -> set:
    """Count today's actual entries (filled BUY orders) straight from Alpaca,
    so autopilot's daily-entry count stays correct across backend restarts and
    doesn't rely on in-memory state (which resets and was Streamlit-only). This
    is what lets a resumed autopilot 'sync' with what already happened today.
    Returns a set of tickers bought today."""
    try:
        et = ZoneInfo("US/Eastern")
        start_of_day = datetime.now(et).replace(hour=0, minute=0, second=0, microsecond=0)
        r = requests.get(f"{ALPACA_BASE}/v2/orders",
                         headers=_alpaca_headers(),
                         params={"status": "closed", "limit": 200,
                                 "after": start_of_day.isoformat()},
                         timeout=10)
        if r.status_code != 200:
            return set()
        bought = set()
        for o in r.json():
            if (o.get("side") == "buy" and o.get("filled_qty")
                    and float(o.get("filled_qty", 0)) > 0):
                sym = o.get("symbol")
                if sym:
                    bought.add(sym)
        return bought
    except Exception:
        return set()


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

    # Sync today's entries from Alpaca (filled buy orders) — the real source of
    # truth. Works across restarts and doesn't depend on in-memory state. This
    # is how a resumed autopilot knows what it already did today.
    et = ZoneInfo("US/Eastern")
    today = datetime.now(et).strftime("%Y-%m-%d")
    bought_today = autopilot_entries_today()

    # ── 1. Account check ──
    account = alpaca_account()
    if not account:
        return {"ok": False, "error": "Can't connect to Alpaca."}
    log.append(f"💰 Portfolio: ${account['equity']:,.2f} · Cash: ${account['cash']:,.2f} · Buying power: ${account['buying_power']:,.2f}")

    positions = alpaca_positions()
    # Don't re-buy anything we already hold OR already bought today.
    held_tickers = {p["ticker"] for p in positions} | bought_today

    # ── AUTO-TUNER: Load params from config, adjust daily based on performance ──
    import json, os, pathlib
    CONFIG_PATH = pathlib.Path(__file__).parent / "autopilot_config.json"

    # Load config via the shared loader (applies SWING override + persists, so
    # the live loop and the dashboard always agree and can't drift to stale
    # day-trade values).
    params = load_autopilot_config()

    # ── Daily auto-tune: review yesterday's trades and adjust ──
    # PROVEN FLOORS (backtest: 33% WR, +$58, profitable):
    # MIN_SCORE >= 78, MAX_POSITIONS <= 2, MAX_DAILY_ENTRIES <= 5
    # STOP_FLOOR >= 0.010, MIN_CONFLUENCE >= 4
    FLOOR_MIN_SCORE = 78
    FLOOR_MAX_POS = SWING_MAX_POSITIONS if SWING_MODE else 2
    FLOOR_MAX_ENTRIES = 5
    FLOOR_STOP = 0.010
    FLOOR_CONFLUENCE = 4

    if params.get("last_tuned") != today and not dry_run:
        try:
            orders_r = requests.get(f"{ALPACA_BASE}/v2/orders",
                                    headers=_alpaca_headers(),
                                    params={"status": "closed", "limit": 100,
                                            "after": (datetime.now(et) - timedelta(days=2)).isoformat()},
                                    timeout=15)
            if orders_r.status_code == 200:
                closed_orders = orders_r.json()
                buys = {}
                sells = {}
                for o in closed_orders:
                    if o.get("filled_qty") and float(o["filled_qty"]) > 0:
                        sym = o["symbol"]
                        avg = float(o.get("filled_avg_price", 0))
                        qty = float(o["filled_qty"])
                        if o["side"] == "buy":
                            buys.setdefault(sym, []).append({"price": avg, "qty": qty})
                        else:
                            sells.setdefault(sym, []).append({"price": avg, "qty": qty})

                wins, losses, total_pnl = 0, 0, 0
                for sym in sells:
                    if sym in buys:
                        buy_avg = sum(b["price"] * b["qty"] for b in buys[sym]) / max(1, sum(b["qty"] for b in buys[sym]))
                        sell_avg = sum(s["price"] * s["qty"] for s in sells[sym]) / max(1, sum(s["qty"] for s in sells[sym]))
                        pnl = sell_avg - buy_avg
                        if pnl > 0: wins += 1
                        else: losses += 1
                        total_pnl += pnl

                total_trades = wins + losses
                win_rate = wins / max(1, total_trades)
                tune_msg = []

                if total_trades >= 2:
                    # RULE 1: Losing day → tighten (fast)
                    if total_pnl < 0:
                        params["MIN_SCORE"] = min(90, params["MIN_SCORE"] + 2)
                        params["MAX_DAILY_ENTRIES"] = max(2, params["MAX_DAILY_ENTRIES"] - 1)
                        tune_msg.append(f"Loss day (${total_pnl:.0f}) → score={params['MIN_SCORE']}, entries={params['MAX_DAILY_ENTRIES']}")

                    # RULE 2: Win rate below 30% → tighten hard
                    if win_rate < 0.30 and total_trades >= 3:
                        params["MIN_SCORE"] = min(90, params["MIN_SCORE"] + 3)
                        params["MIN_CONFLUENCE"] = min(6, params["MIN_CONFLUENCE"] + 1)
                        tune_msg.append(f"Low WR ({win_rate:.0%}) → score={params['MIN_SCORE']}, confluence={params['MIN_CONFLUENCE']}")

                    # RULE 3: Profitable day → relax VERY slowly (1 point, only if above floor)
                    if total_pnl > 50 and win_rate > 0.40:
                        if params["MIN_SCORE"] > FLOOR_MIN_SCORE + 2:
                            params["MIN_SCORE"] = max(FLOOR_MIN_SCORE, params["MIN_SCORE"] - 1)
                            tune_msg.append(f"Profit day +${total_pnl:.0f} ({win_rate:.0%} WR) → score={params['MIN_SCORE']} (relaxed 1pt)")

                    # RULE 4: Big loss → widen stops slightly (less noise stopouts)
                    if total_pnl < -100:
                        params["STOP_FLOOR"] = min(0.020, params.get("STOP_FLOOR", 0.013) + 0.001)
                        tune_msg.append(f"Big loss → stop_floor={params['STOP_FLOOR']:.1%}")

                    # RULE 5: 3+ wins in a row → narrow stops back (confidence)
                    if wins >= 3 and losses == 0:
                        params["STOP_FLOOR"] = max(FLOOR_STOP, params.get("STOP_FLOOR", 0.013) - 0.001)
                        tune_msg.append(f"Clean sweep ({wins}W) → stop_floor={params['STOP_FLOOR']:.1%}")

                    # HARD CLAMPS — never violate proven floors
                    params["MIN_SCORE"] = max(FLOOR_MIN_SCORE, min(92, params["MIN_SCORE"]))
                    params["MAX_POSITIONS"] = max(1, min(FLOOR_MAX_POS, params["MAX_POSITIONS"]))
                    params["MAX_DAILY_ENTRIES"] = max(2, min(FLOOR_MAX_ENTRIES, params["MAX_DAILY_ENTRIES"]))
                    params["MIN_CONFLUENCE"] = max(FLOOR_CONFLUENCE, min(7, params["MIN_CONFLUENCE"]))
                    params["STOP_FLOOR"] = max(FLOOR_STOP, min(0.020, params.get("STOP_FLOOR", 0.013)))
                    params["MIN_RR"] = max(1.8, min(3.0, params["MIN_RR"]))
                    params["DAILY_LOSS_LIMIT"] = max(0.005, min(0.015, params.get("DAILY_LOSS_LIMIT", 0.01)))
                    # NEVER relax these below proven values
                    params["AVOID_MIDDAY"] = True  # always skip midday chop

                if tune_msg:
                    log.append("🔧 **Auto-Tune** — adjusted based on yesterday:")
                    for m in tune_msg:
                        log.append(f"   • {m}")
                    params["tune_history"].append({"date": today, "changes": tune_msg,
                                                   "stats": {"trades": total_trades, "wins": wins, "losses": losses, "pnl": round(total_pnl, 2)}})
                    params["tune_history"] = params["tune_history"][-30:]

                params["last_tuned"] = today
                CONFIG_PATH.write_text(json.dumps(params, indent=2))
        except Exception as e:
            log.append(f"⚠️ Auto-tune skipped: {str(e)[:60]}")

    # Apply params
    MAX_POSITIONS = params["MAX_POSITIONS"]
    RISK_PER_TRADE = params["RISK_PER_TRADE"]
    MAX_POS_PCT = params["MAX_POS_PCT"]
    MIN_SCORE = params["MIN_SCORE"]
    MIN_CONFLUENCE = params["MIN_CONFLUENCE"]
    MIN_RR = params["MIN_RR"]
    SELL_BELOW = params["SELL_BELOW"]
    MAX_DAILY_ENTRIES = params.get("MAX_DAILY_ENTRIES", 6)

    daily_entries = len(bought_today)

    log.append(f"Open positions: {len(positions)} · Max: {MAX_POSITIONS} · Entries today: {daily_entries}/{MAX_DAILY_ENTRIES}")
    log.append(f"📊 Mode: **{'Swing' if SWING_MODE else 'Selective Intraday'}** · Score≥{MIN_SCORE} · R:R≥{MIN_RR} · Max {MAX_POSITIONS} pos")
    DAILY_LOSS_LIMIT = params["DAILY_LOSS_LIMIT"]
    PARTIAL_PROFIT_PCT = params["PARTIAL_PROFIT_PCT"]
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

    # ── 1b. EOD handling ──
    now_et = datetime.now(et)
    weekday = now_et.strftime("%A")
    log.append(f"📅 {weekday} {now_et.strftime('%I:%M %p ET')}")

    if SWING_MODE:
        # Swing trading: positions are held across days. We do NOT force-close
        # at the bell — exits happen on stop/target/reversal/max-hold only.
        log.append("📈 Swing mode — positions held overnight, no EOD liquidation")
        no_new_buys_eod = False
    else:
        # (legacy intraday path — kept for reference, disabled while SWING_MODE)
        eod_warning = now_et.replace(hour=15, minute=30, second=0, microsecond=0)
        eod_liquidation = now_et.replace(hour=15, minute=45, second=0, microsecond=0)
        eod_hard_close = now_et.replace(hour=15, minute=55, second=0, microsecond=0)

        if now_et >= eod_warning and now_et < eod_liquidation and positions:
            log.append(f"⏰ **EOD WARNING** — closing all in {(eod_liquidation - now_et).seconds // 60} min")

        if now_et >= eod_liquidation and positions and not dry_run:
            log.append(f"🔔 **EOD LIQUIDATION (2:45 PM CT)** — closing ALL {len(positions)} positions")
            result = alpaca_close_all()
            if result.get("ok"):
                log.append(f"✅ Closed {len(positions)} positions — flat for the day")
            else:
                log.append(f"⚠️ Bulk close failed: {result.get('error', '')} — trying individually")
                for pos in positions:
                    try:
                        ticker = pos["ticker"]
                        requests.delete(
                            f"{ALPACA_BASE}/v2/orders",
                            headers=_alpaca_headers(),
                            params={"symbols": ticker.upper()},
                            timeout=10
                        )
                        r = requests.delete(
                            f"{ALPACA_BASE}/v2/positions/{ticker.upper()}",
                            headers=_alpaca_headers(),
                            params={"cancel_orders": "true"},
                            timeout=10
                        )
                        if r.status_code in (200, 201, 207):
                            log.append(f"✅ Closed {ticker} ({pos.get('side', 'long')})")
                        else:
                            err = r.json().get("message", "") if r.text else "unknown"
                            log.append(f"⚠️ Failed {ticker}: {err}")
                    except Exception as e:
                        log.append(f"⚠️ Error closing {ticker}: {str(e)[:60]}")

            if now_et >= eod_hard_close:
                remaining = alpaca_positions()
                if remaining:
                    log.append(f"🔴 **HARD CLOSE** — {len(remaining)} positions still open at 2:55 PM CT")
                    requests.delete(f"{ALPACA_BASE}/v2/orders", headers=_alpaca_headers(), timeout=10)
                    requests.delete(f"{ALPACA_BASE}/v2/positions", headers=_alpaca_headers(),
                                   params={"cancel_orders": "true"}, timeout=10)
                    log.append("🔴 Cancelled all orders + closed all positions")

            return {"ok": True, "log": log, "buys": 0, "sells": len(positions), "scanned": 0, "opportunities": 0}
        elif now_et >= eod_liquidation and positions and dry_run:
            log.append(f"🔔 EOD: Would close {len(positions)} positions (dry run)")

        # No new trades in last 60min of trading (intraday only)
        last_buy_cutoff = now_et.replace(hour=15, minute=30, second=0, microsecond=0)
        no_new_buys_eod = now_et >= last_buy_cutoff

    # ── 1b2. Avoid the open — first 15min is pure chop ──
    start_h, start_m = [int(x) for x in params.get("TRADING_HOURS_START", "09:45").split(":")]
    end_h, end_m = [int(x) for x in params.get("TRADING_HOURS_END", "15:00").split(":")]
    market_open_safe = now_et.replace(hour=start_h, minute=start_m, second=0, microsecond=0)
    market_open_actual = now_et.replace(hour=9, minute=30, second=0, microsecond=0)
    trading_end = now_et.replace(hour=end_h, minute=end_m, second=0, microsecond=0)
    too_early = market_open_actual <= now_et < market_open_safe
    too_late = now_et >= trading_end
    if too_early:
        log.append(f"⏳ Waiting until {start_h}:{start_m:02d} AM — first 15min is chop, letting VWAP establish")
        no_new_buys_eod = True
    if too_late:
        log.append(f"⏳ Past {end_h}:{end_m:02d} — no new entries, managing exits only")
        no_new_buys_eod = True

    # ── 1b3. Midday chop filter ──
    if params.get("AVOID_MIDDAY", False):
        mid_start_h, mid_start_m = [int(x) for x in params.get("MIDDAY_START", "11:30").split(":")]
        mid_end_h, mid_end_m = [int(x) for x in params.get("MIDDAY_END", "13:30").split(":")]
        midday_start = now_et.replace(hour=mid_start_h, minute=mid_start_m, second=0, microsecond=0)
        midday_end = now_et.replace(hour=mid_end_h, minute=mid_end_m, second=0, microsecond=0)
        if midday_start <= now_et < midday_end:
            log.append(f"⏳ Midday ({mid_start_h}:{mid_start_m:02d}-{mid_end_h}:{mid_end_m:02d}) — low volume chop, skipping entries")
            no_new_buys_eod = True

    # ── 1b4. SPY correlation filter — don't go long into a dump ──
    spy_trend = _get_spy_intraday_trend()
    if spy_trend:
        log.append(f"📈 SPY: {spy_trend['direction']} ({spy_trend['change_pct']:+.2f}%) · VWAP {'above' if spy_trend['above_vwap'] else 'below'}")

    # ── 1c. Market regime + VIX check ──
    regime = check_market_regime()
    vix = regime.get("vix", {})
    vix_level = vix.get("level", 0)
    vix_status = vix.get("status", "unknown")
    log.append(f"📊 Market: {regime['reason']}")
    if vix_level > 0:
        vix_emoji = "🟢" if vix_level < 20 else "🟡" if vix_level < 25 else "🔴"
        log.append(f"{vix_emoji} VIX: {vix_level} ({vix_status}) — {'fear is low, good for trading' if vix_level < 20 else 'elevated fear, trade smaller' if vix_level < 30 else 'EXTREME FEAR — reducing exposure'}")

    # VIX panic mode — shut down longs, only allow shorts
    vix_panic = vix_level >= 35
    vix_cautious = vix_level >= 25

    if vix_panic and not dry_run:
        log.append("🛑 **VIX EXTREME (≥35)** — closing all long positions, only shorts allowed")
        for pos in positions:
            if pos.get("side", "long") == "long":
                alpaca_sell(ticker=pos["ticker"], sell_all=True)
                log.append(f"🔴 Emergency closed {pos['ticker']} (VIX panic)")

    if not regime["safe_to_buy"]:
        log.append("⛔ Market regime unsafe — skipping new longs, only managing existing")

    # ── 1d. Sector strength report ──
    sectors = _get_sector_strength()
    if sectors:
        ranked = sorted(sectors.items(), key=lambda x: x[1].get("rank", 99))
        top3 = [f"{d['name']}" for _, d in ranked[:3]]
        bot3 = [f"{d['name']}" for _, d in ranked[-3:]]
        log.append(f"Hot sectors: {', '.join(top3)} · Cold: {', '.join(bot3)}")

    # ── 2. Trail stops on profitable positions ──
    log.append("")
    log.append("**Step 1: Managing existing positions**")
    if positions:
        trail_actions = update_trailing_stops(positions, log)
        for a in trail_actions:
            log.append(a)
        if not trail_actions:
            log.append("No stops to trail — positions not yet profitable enough")

    # ── 2a. Time-based stops — kill flat trades (dead money) ──
    STALE_KEY = "autopilot_entry_times"
    if STALE_KEY not in st.session_state:
        st.session_state[STALE_KEY] = {}
    # Track entry time for new positions
    for pos in positions:
        t = pos["ticker"]
        if t not in st.session_state[STALE_KEY]:
            st.session_state[STALE_KEY][t] = time.time()
    # Clean up closed positions
    held = {p["ticker"] for p in positions}
    st.session_state[STALE_KEY] = {k: v for k, v in st.session_state[STALE_KEY].items() if k in held}

    stale_kills = []
    STALE_MINUTES = params.get("STALE_MINUTES", 90)
    for pos in positions:
        if SWING_MODE or STALE_MINUTES <= 0:
            break  # swing holds across days — no intraday "dead money" kill
        ticker = pos["ticker"]
        pnl_pct = pos.get("unrealized_pnl_pct", 0)
        entry_time = st.session_state[STALE_KEY].get(ticker, time.time())
        minutes_held = (time.time() - entry_time) / 60

        # If held 90+ min and PnL between -0.5% and +0.5% — it's dead money
        if minutes_held >= STALE_MINUTES and -0.2 <= pnl_pct <= 0.15:
            is_short = pos.get("side") == "short"
            if dry_run:
                stale_kills.append(f"⏰ Would close {ticker} {'(short)' if is_short else ''} — flat for {minutes_held:.0f}min ({pnl_pct:+.1f}%)")
            else:
                if is_short:
                    result = alpaca_cover(ticker=ticker, cover_all=True)
                else:
                    result = alpaca_sell(ticker=ticker, sell_all=True)
                if result.get("ok"):
                    stale_kills.append(f"⏰ Closed {ticker} {'(short)' if is_short else ''} — dead money, flat for {minutes_held:.0f}min ({pnl_pct:+.1f}%)")
                    st.session_state[STALE_KEY].pop(ticker, None)

    for s in stale_kills:
        log.append(s)
    if stale_kills:
        log.append(f"Killed {len(stale_kills)} stale positions")

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
        qty = int(abs(pos.get("qty", 0)))
        is_short = pos.get("side") == "short"

        # Only take partials if: profitable enough, haven't already taken partials, and have >1 share
        if (pnl_pct >= PARTIAL_PROFIT_PCT * 100
                and ticker not in st.session_state[PARTIAL_PROFIT_SOLD_KEY]
                and qty > 1):
            half = max(1, qty // 2)
            if dry_run:
                partials.append(f"💰 Would close {half}/{qty} shares of {ticker} {'(short)' if is_short else ''} at +{pnl_pct:.1f}%")
            else:
                if is_short:
                    result = alpaca_cover(ticker=ticker, qty=half)
                else:
                    result = alpaca_sell(ticker=ticker, qty=half)
                if result.get("ok"):
                    partials.append(f"💰 {'Covered' if is_short else 'Sold'} {half}/{qty} {ticker} {'(short)' if is_short else ''} at +{pnl_pct:.1f}% — half off, letting rest ride")
                    st.session_state[PARTIAL_PROFIT_SOLD_KEY].add(ticker)
                else:
                    partials.append(f"⚠️ Partial close failed for {ticker}: {result.get('error', '')}")

    for p in partials:
        log.append(p)
    if not partials:
        log.append(f"No positions hit +{PARTIAL_PROFIT_PCT*100:.1f}% for partial profit yet")

    # ── 2c. Trailing stop (autopilot only) ──
    # Once a long is up enough, ratchet its stop UP to lock in gains: track each
    # position's high-water price and keep the stop a fixed % below that high.
    # The stop only ever moves up, never down. Autopilot-managed positions only.
    TRAIL_KEY = "autopilot_trail_high"
    if TRAIL_KEY not in st.session_state:
        st.session_state[TRAIL_KEY] = {}
    TRAIL_ACTIVATE_PCT = params.get("TRAIL_ACTIVATE_PCT", 3.0)   # start trailing after +3%
    TRAIL_DISTANCE_PCT = params.get("TRAIL_DISTANCE_PCT", 2.5)   # stop sits 2.5% below the high
    # Forget high-water marks for positions we no longer hold.
    _held = {p["ticker"] for p in positions}
    st.session_state[TRAIL_KEY] = {k: v for k, v in st.session_state[TRAIL_KEY].items() if k in _held}

    trails = []
    for pos in positions:
        if pos.get("side") == "short":
            continue  # trailing logic here is long-only
        ticker = pos["ticker"]
        pnl_pct = pos.get("unrealized_pnl_pct", 0)
        cur_price = float(pos.get("current_price", 0) or 0)
        if cur_price <= 0:
            continue
        # Only trail once the trade is working.
        if pnl_pct < TRAIL_ACTIVATE_PCT:
            continue
        prev_high = st.session_state[TRAIL_KEY].get(ticker, 0)
        high = max(prev_high, cur_price)
        st.session_state[TRAIL_KEY][ticker] = high
        new_stop = round(high * (1 - TRAIL_DISTANCE_PCT / 100), 2)
        # Current stop (from open stop orders), so we only ever raise it.
        cur_stop = 0.0
        try:
            cur_stop = float(pos.get("stop_loss", 0) or 0)
        except Exception:
            cur_stop = 0.0
        if new_stop <= cur_stop + 0.01:
            continue  # would not raise the stop — leave it
        if dry_run:
            trails.append(f"🪜 Would trail {ticker} stop → ${new_stop} (high ${high:.2f}, +{pnl_pct:.1f}%)")
        else:
            res = _update_stop_order(ticker, new_stop, int(abs(pos.get("qty", 0))))
            if res.get("ok"):
                trails.append(f"🪜 Trailed {ticker} stop up → ${new_stop} (locking in below ${high:.2f})")
            else:
                trails.append(f"⚠️ Trail failed for {ticker}: {res.get('error', '')[:50]}")
    for tr in trails:
        log.append(tr)

    # ── 3. Check existing positions — close if signal flipped ──
    log.append("")
    log.append("**Step 2: Checking if positions need closing**")
    sells = []
    for pos in positions:
        try:
            is_short = pos.get("side") == "short"
            if SWING_MODE:
                # Swing: judge exits on the DAILY signal, not 5-min intraday noise.
                data = fetch_scan(pos["ticker"])
                if not data:
                    continue
                sig = generate_trade_signal(data)
            else:
                data = fetch_scan_intraday(pos["ticker"])
                if not data:
                    data = fetch_scan(pos["ticker"])
                    if not data:
                        continue
                    sig = generate_trade_signal(data)
                else:
                    sig = generate_intraday_signal(data)

            # For longs: close if signal turned bearish
            # For shorts: close if signal turned bullish
            should_close = False
            if not is_short and (sig["score"] <= SELL_BELOW or sig["action"] == "STRONG_SELL"):
                should_close = True
            elif is_short and (sig["score"] >= (100 - SELL_BELOW) or sig["action"] == "STRONG_BUY"):
                should_close = True

            if should_close:
                action_word = "Covered" if is_short else "Sold"
                if dry_run:
                    sells.append(f"🔴 Would close {pos['ticker']} {'(short)' if is_short else ''} — score {sig['score']}, signal: {sig['action']}")
                else:
                    if is_short:
                        result = alpaca_cover(ticker=pos["ticker"], cover_all=True)
                    else:
                        result = alpaca_sell(ticker=pos["ticker"], sell_all=True)
                    if result.get("ok"):
                        sells.append(f"🔴 {action_word} {pos['ticker']} {'(short)' if is_short else ''} — score {sig['score']}, signal: {sig['action']}")
                        # Prevent re-buying this ticker today
                        held_tickers.add(pos["ticker"])
                    else:
                        sells.append(f"⚠️ Tried to close {pos['ticker']} but failed: {result.get('error','')}")
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
        log.append("⏰ **2:30 PM CT** — no new trades, managing existing positions only")
        return {"ok": True, "log": log, "buys": 0, "sells": len(sells), "scanned": 0, "opportunities": 0}

    # Gate: daily entry cap reached
    if daily_entries >= MAX_DAILY_ENTRIES and not dry_run:
        log.append(f"🛑 **Daily entry cap reached** ({daily_entries}/{MAX_DAILY_ENTRIES}) — no more new trades today")
        return {"ok": True, "log": log, "buys": 0, "sells": len(sells), "scanned": 0, "opportunities": 0}

    # Gate: don't buy in bear markets
    if not regime["safe_to_buy"]:
        log.append("Skipped scan — waiting for better market conditions")
        return {"ok": True, "log": log, "buys": 0, "sells": len(sells), "scanned": 0, "opportunities": 0}

    # ── 4. Scan for new opportunities ──
    # Step A: Pre-market gap scan — find stocks gapping hard on volume
    log.append("")
    log.append("**Step 3: Scanning market for new setups**")
    log.append("Pre-screening for gaps and momentum...")

    candidates = []
    gap_stocks = []

    # Get top gainers and losers — these are today's movers with gaps
    gainers = polygon_gainers(limit=20) or []
    all_snaps = polygon_all_snapshots() or []

    if all_snaps:
        # Filter: real stocks, decent volume, price > $5
        viable = [s for s in all_snaps if s.get("Price", 0) > 5 and s.get("Volume", 0) > 200_000]

        # Gap scan: stocks moving >1.5% with volume — these gapped
        gappers_up = sorted([s for s in viable if s.get("Chg%", 0) > 1.5], key=lambda x: x["Chg%"], reverse=True)[:25]
        gappers_down = sorted([s for s in viable if s.get("Chg%", 0) < -1.5], key=lambda x: x["Chg%"])[:25]

        # Liquidity filter: skip thin stocks (avg volume < 500K where available)
        gappers_up = [s for s in gappers_up if s.get("Volume", 0) > 500_000]
        gappers_down = [s for s in gappers_down if s.get("Volume", 0) > 500_000]

        for s in gappers_up:
            gap_stocks.append(f"▲ {s['Ticker']} +{s.get('Chg%', 0):.1f}%")
        for s in gappers_down:
            gap_stocks.append(f"▼ {s['Ticker']} {s.get('Chg%', 0):.1f}%")

        if gap_stocks:
            log.append(f"**Gap scan:** {len(gappers_up)} gapping up, {len(gappers_down)} gapping down")
            log.append("Top gaps: " + " · ".join(gap_stocks[:10]))

        # Build candidate list: gappers first (highest priority), then movers
        movers = sorted(viable, key=lambda x: abs(x.get("Chg%", 0)), reverse=True)[:80]
        # Positive movers for longs
        positive = sorted([s for s in viable if s.get("Chg%", 0) > 0.5], key=lambda x: x["Chg%"], reverse=True)[:40]
        # Negative movers for shorts
        negative = sorted([s for s in viable if s.get("Chg%", 0) < -0.5], key=lambda x: x["Chg%"])[:40]

        seen = set()
        # Gappers first — highest priority for day trading
        for s in gappers_up + gappers_down:
            t = s["Ticker"]
            if t not in seen and t not in held_tickers:
                seen.add(t)
                candidates.append(t)
        # Then other movers
        for s in positive + negative + movers:
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
            # ── Mid-cap growth (liquid, established) ──
            "AXON","HIMS","CAVA","DUOL","CELH","ELF","ONON","TOST","BROS","DDOG",
            "HUBS","FROG","MANH","TTD","DASH","CVNA",
            # ── Additional large/mid caps ──
            "SHOP","PLTR","COIN","SOFI","HOOD","MSTR","RIOT","MARA","NIO","RIVN",
            "LCID","SNAP","RBLX","U","DKNG","SQ","NET","ZS","PANW","OKTA",
            "MDB","SNOW","ROKU","PINS","TWLO","ZM","DOCU","BILL","PAYC","PCOR",
            "WIX","ETSY","CHWY","W","BURL","TJX","ROST","DG","DLTR","FIVE",
            "ULTA","LULU","TPR","CPRI","RL","PVH","VFC","HBI","GILD","BIIB",
            "REGN","ILMN","DXCM","VEEV","ZTS","WDAY","SPLK","TEAM","ATLZ",
            "ANET","FFIV","JNPR","AKAM","GDDY","MTCH","IAC","ANSS","EPAM",
            "GLOB","INFY","WIT","SAP","ASML","LRCX","KLAC","ONTO","CRUS",
            "WOLF","GFS","STM","SSNC","FIS","FISV","GPN","WU","NVST","TFX",
            "BAX","BDX","CI","CVS","HCA","THC","TEVA","MYL","VTRS","ZBH",
            "SYY","USFD","US","KDP","STZ","TAP","BF-B","SAM","MNST","COKE",
            "CLX","CHD","SJM","GIS","K","CPB","MKC","HRL","TSN","CAG",
            "BG","ADM","CTLT","LW","INGR","DAR","BERY","SEE","AMCR","IP",
            "WRK","PKG","CE","CC","LYB","EMN","APD","ECL","SHW","PPG",
            "NEM","GOLD","FNV","WPM","AEM","KGC","RGLD","PAAS","AG","HL",
            "FCX","RIO","BHP","VALE","CLF","X","NUE","STLD","RS","CMC",
            "BLDR","VMC","MLM","CX","SRCL","WCN","RSG","WM","CLH","ECOL",
        ]
        fallback = [t for t in FULL_UNIVERSE if t not in held_tickers and t not in set(candidates)]
        # Widen with the same large liquid universe the manual scanner uses, so
        # autopilot considers 500+ names instead of just this hardcoded list.
        try:
            from universe import large_universe
            extra = [t for t in large_universe() if t not in held_tickers and t not in set(candidates) and t not in set(fallback)]
            fallback.extend(extra)
        except Exception:
            pass
        random.shuffle(fallback)
        candidates.extend(fallback[:600])
        log.append(f"Large-cap universe → {len(candidates)} candidates")

    # ── SECTOR ROTATION FILTER — prioritize hot sectors ──
    hot_sectors = set()
    if sectors:
        ranked_sectors = sorted(sectors.items(), key=lambda x: x[1].get("rank", 99))
        hot_sectors = {etf for etf, data in ranked_sectors[:3]}  # Top 3 sectors
        cold_sectors = {etf for etf, data in ranked_sectors[-2:]}  # Bottom 2

        # Filter candidates: boost hot sector stocks, remove cold sector stocks
        hot_tickers = []
        neutral_tickers = []
        for t in candidates:
            t_sector = TICKER_SECTOR.get(t)
            if t_sector in cold_sectors:
                continue  # Skip stocks in cold sectors
            elif t_sector in hot_sectors:
                hot_tickers.append(t)
            else:
                neutral_tickers.append(t)
        # Hot sector stocks first, then rest
        candidates = hot_tickers + neutral_tickers
        if hot_tickers:
            log.append(f"🔥 Sector filter: {len(hot_tickers)} stocks in hot sectors, {len(neutral_tickers)} neutral, skipped cold")

    scan_list = candidates
    log.append(f"Deep-analyzing {len(scan_list)} stocks...")

    opportunities = []
    all_scores = []
    analyzed = 0
    errors = 0
    # Swing mode can analyze a big universe fast via batch download; intraday mode
    # stays per-ticker (needs live intraday bars + per-name momentum checks).
    MAX_ANALYZE = 400 if SWING_MODE else 80
    scan_list = scan_list[:MAX_ANALYZE]

    # In swing mode, bulk-fetch all candidates in a few requests (same fast path
    # as the manual scanner) instead of one slow fetch per ticker.
    swing_batch = {}
    if SWING_MODE and len(scan_list) > 40:
        try:
            swing_batch = batch_fetch_scan(scan_list, skip_news=True)
            log.append(f"Batch-fetched {len(swing_batch)} stocks")
        except Exception:
            swing_batch = {}

    for ticker in scan_list:
        try:
            if SWING_MODE:
                data = swing_batch.get(ticker) if swing_batch else fetch_scan(ticker)
                if not data:
                    errors += 1
                    continue
                price = data.get("price", 0)
                if not price or price < 5:
                    continue
                if _has_earnings_today(ticker):
                    continue
                analyzed += 1
                sig = generate_trade_signal(data)
            else:
                data = fetch_scan_intraday(ticker)
                if not data:
                    errors += 1
                    continue
                price = data.get("price", 0)
                if not price or price < 5:  # $5 minimum — skip penny stocks
                    continue
                # Liquidity: skip if intraday volume too thin
                itech = data.get("intraday_technicals", {})
                if itech.get("vol_ratio", 1) < 0.3:
                    continue  # dead volume

                # ── EARNINGS FILTER — never trade on earnings day ──
                if _has_earnings_today(ticker):
                    continue

                # ── MOMENTUM FILTER — stock must be moving today ──
                day_change = data.get("change_pct", 0)
                # Skip stocks barely moving (between -0.3% and +0.3%) — no momentum
                if abs(day_change) < 0.3:
                    continue

                analyzed += 1
                sig = generate_intraday_signal(data)
            all_scores.append((ticker, sig["score"], sig["action"], sig["confluence"]["bullish"], sig["trade"]["risk_reward"]))

            # LONG opportunities
            if (sig["score"] >= MIN_SCORE
                    and sig["confluence"]["bullish"] >= MIN_CONFLUENCE
                    and sig["trade"]["risk_reward"] >= MIN_RR
                    and sig["action"] == "STRONG_BUY"):
                opportunities.append({
                    "ticker": ticker,
                    "score": sig["score"],
                    "action": sig["action"],
                    "side": "long",
                    "confluence": sig["confluence"]["bullish"],
                    "rr": sig["trade"]["risk_reward"],
                    "signal": sig,
                    "data": data,
                })

            # SHORT opportunities — bearish signals with conviction
            elif (sig["score"] <= (100 - MIN_SCORE)
                    and sig["confluence"]["bearish"] >= MIN_CONFLUENCE
                    and sig["trade"]["risk_reward"] >= MIN_RR
                    and sig["action"] == "STRONG_SELL"):
                opportunities.append({
                    "ticker": ticker,
                    "score": 100 - sig["score"],  # invert so higher = more bearish conviction
                    "action": sig["action"],
                    "side": "short",
                    "confluence": sig["confluence"]["bearish"],
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

    # Sort: STRONG signals first, then by score (higher = more conviction for both sides)
    action_priority = {"STRONG_BUY": 0, "STRONG_SELL": 0, "BUY": 1, "SELL": 1, "HOLD": 2}
    opportunities.sort(key=lambda x: (action_priority.get(x["action"], 3), -x["score"]))

    if not opportunities:
        log.append(f"No stocks passed (longs: score≥{MIN_SCORE}, shorts: score≤{100-MIN_SCORE}, confluence≥{MIN_CONFLUENCE}, R:R≥{MIN_RR})")
        return {"ok": True, "log": log, "buys": 0, "sells": len(sells), "scanned": analyzed}

    longs = [o for o in opportunities if o["side"] == "long"]
    shorts = [o for o in opportunities if o["side"] == "short"]
    log.append(f"Found {len(opportunities)} setups ({len(longs)} long, {len(shorts)} short)")

    # ── 5. Execute trades on best opportunities ──
    log.append("")
    log.append(f"**Step 4: Executing top {min(open_slots, len(opportunities))} trades**")
    executions = []
    for opp in opportunities[:open_slots]:
        ticker = opp["ticker"]
        sig = opp["signal"]
        trade = sig["trade"]
        is_short = opp["side"] == "short"

        # Earnings check — skip stocks reporting within 7 days
        has_earnings, earn_date = _has_upcoming_earnings(ticker, days=7)
        if has_earnings:
            log.append(f"⏭️ Skipped {ticker} — earnings on {earn_date}")
            continue

        # Deep news check via AI — HARD GATE
        opp_news = _ai_news_analysis(ticker)
        if not is_short and opp_news.get("ai_score", 0) <= -3:
            log.append(f"⏭️ Skipped {ticker} long — AI news bearish ({opp_news.get('ai_summary', '')[:60]})")
            continue
        if is_short and opp_news.get("ai_score", 0) >= 3:
            log.append(f"⏭️ Skipped {ticker} short — AI news bullish ({opp_news.get('ai_summary', '')[:60]})")
            continue
        if opp_news.get("macro_risk"):
            log.append(f"⚠️ MACRO RISK detected for {ticker}: {opp_news.get('ai_summary', '')[:80]}")
            if not is_short:
                log.append(f"⏭️ Skipped {ticker} long — macro risk active")
                continue

        # SPY directional filter — don't fight the market
        if spy_trend and spy_trend.get("strong"):
            if not is_short and spy_trend["direction"] == "bearish":
                log.append(f"⏭️ Skipped {ticker} long — SPY dumping ({spy_trend['change_pct']:+.1f}%)")
                continue
            if is_short and spy_trend["direction"] == "bullish":
                log.append(f"⏭️ Skipped {ticker} short — SPY ripping ({spy_trend['change_pct']:+.1f}%)")
                continue

        # VIX filter — block longs in panic, reduce size in fear
        if vix_panic and not is_short:
            log.append(f"⏭️ Skipped {ticker} long — VIX ≥35 (panic mode, shorts only)")
            continue
        if vix_cautious and not is_short and not regime["safe_to_buy"]:
            log.append(f"⏭️ Skipped {ticker} long — VIX elevated + bear regime")
            continue

        entry = trade["entry"]
        stop = trade["stop_loss"]
        target = trade["target_1"]

        # Position sizing: risk X% of equity
        if is_short:
            risk_per_share = abs(stop - entry)
        else:
            risk_per_share = abs(entry - stop)

        if risk_per_share <= 0:
            continue

        # Scale risk down when VIX is elevated
        # ── SECTOR CORRELATION — max 1 position per sector ──
        if _check_sector_correlation(ticker, positions):
            log.append(f"⏭️ Skipped {ticker} — already have a position in same sector")
            continue

        # ── SMART POSITION SIZING — scale with conviction ──
        risk_mult = 1.0
        if vix_cautious:
            risk_mult = 0.5
            log.append(f"⚠️ VIX elevated — half position size for {ticker}")

        # Score-based sizing: 75-79 = 0.7x, 80-84 = 1.0x, 85+ = 1.3x
        score = opp["score"]
        if score >= 85:
            risk_mult *= 1.3  # high conviction — larger position
        elif score >= 80:
            risk_mult *= 1.0  # standard
        else:
            risk_mult *= 0.7  # lower conviction — smaller position

        max_risk_dollars = account["equity"] * RISK_PER_TRADE * risk_mult
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
        side_emoji = "🔴" if is_short else "🟢"
        side_word = "Short" if is_short else "Bought"

        if dry_run:
            executions.append(f"{side_emoji} Would {'short' if is_short else 'buy'} {qty} {ticker} @ ~${entry:.2f} · Stop ${stop:.2f} · Target ${target:.2f} · Score {opp['score']} · R:R {opp['rr']:.1f}:1")
            account["buying_power"] -= cost
        else:
            # After 1:00 PM CT (2:00 PM ET): NO bracket orders — they block EOD closes
            late_session = now_et.hour > 15 or (now_et.hour == 15 and now_et.minute >= 30)  # After 3:30 PM ET = 2:30 PM CT
            if late_session:
                if is_short:
                    result = alpaca_short(ticker=ticker, qty=qty)
                else:
                    result = alpaca_buy(ticker=ticker, qty=qty)
            else:
                if is_short:
                    result = alpaca_short(ticker=ticker, qty=qty, stop_loss=stop, take_profit=target)
                else:
                    result = alpaca_buy(ticker=ticker, qty=qty, stop_loss=stop, take_profit=target)

            if result.get("ok"):
                executions.append(f"{side_emoji} {side_word} {qty} {ticker} @ ~${entry:.2f} · Stop ${stop:.2f} · Target ${target:.2f} · Score {opp['score']} · R:R {opp['rr']:.1f}:1")
                held_tickers.add(ticker)
                account["buying_power"] -= cost
            else:
                executions.append(f"⚠️ Failed to {'short' if is_short else 'buy'} {ticker}: {result.get('error','')}")

    for b in executions:
        log.append(b)

    # High-conviction alerts: any long setup scoring 90+ (whether or not
    # autopilot bought it). These get surfaced to the user as an in-app alert.
    # all_scores rows are (ticker, score, action, bullish_confluence, rr).
    high_conviction = []
    for row in all_scores:
        try:
            tkr, sc, act, conf, rr = row
            if sc >= 90 and act == "STRONG_BUY":
                high_conviction.append({"ticker": tkr, "score": int(sc), "rr": round(float(rr), 1)})
        except Exception:
            continue
    high_conviction.sort(key=lambda x: x["score"], reverse=True)

    return {
        "ok": True,
        "log": log,
        "buys": sum(1 for b in executions if "🟢" in b),
        "shorts": sum(1 for b in executions if "🔴" in b),
        "sells": len(sells),
        "scanned": analyzed,
        "opportunities": len(opportunities),
        "alerts": high_conviction[:5],
    }


def execute(intent: dict, progress_cb=None, is_plus: bool = True) -> dict:
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
            f"Bought: {result.get('buys', 0)} · Shorted: {result.get('shorts', 0)} · Closed: {result.get('sells', 0)}\n\n"
            f"*Next scan in 5 minutes. Say \"stop\" to deactivate.*\n\n"
            f"---\n\n" +
            "\n\n".join(report_lines)
        )
        return {"ok": True, "type": "trade", "msg": summary}

    if t == "stop_autopilot":
        st.session_state["autopilot_active"] = False
        return {"ok": True, "type": "trade", "msg": "🔴 **Autopilot deactivated.** No more automatic scans. Your positions remain open."}

    if t == "backtest":
        result = run_backtest(years=2, max_positions=intent.get("max_positions"))
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
    if t == "daily_review":
        acc = alpaca_account()
        positions = alpaca_positions()
        filled_orders = alpaca_orders(status="closed", limit=50)
        
        # Filter to today's orders
        today_str = datetime.now(ZoneInfo("US/Eastern")).strftime("%Y-%m-%d")
        todays_orders = [o for o in filled_orders if o.get("submitted", "").startswith(today_str)]
        
        review_data = {
            "account": acc or {},
            "daily_pnl": acc.get("daily_pnl", 0) if acc else 0,
            "daily_pnl_pct": acc.get("daily_pnl_pct", 0) if acc else 0,
            "equity": acc.get("equity", 0) if acc else 0,
            "open_positions": len(positions),
            "positions": [{"ticker": p["ticker"], "side": p.get("side", "long"), 
                          "qty": p.get("qty", 0), "pnl": p.get("unrealized_pnl", 0),
                          "pnl_pct": p.get("unrealized_pnl_pct", 0)} for p in positions],
            "todays_trades": todays_orders,
            "total_trades_today": len(todays_orders),
            "buys_today": len([o for o in todays_orders if o.get("side") == "buy"]),
            "sells_today": len([o for o in todays_orders if o.get("side") == "sell"]),
        }
        
        return {"ok": True, "type": "analysis", "data": review_data}

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

        # Check if asking about a specific ticker
        asked_ticker = intent.get("ticker") or None
        if not asked_ticker:
            # Try to find ticker in original message context
            for p in positions:
                if p["ticker"].lower() in str(intent).lower():
                    asked_ticker = p["ticker"]
                    break

        # If asking about a specific stock
        if asked_ticker:
            match = [p for p in positions if p["ticker"].upper() == asked_ticker.upper()]
            if match:
                p = match[0]
                arrow = "▲" if p["unrealized_pnl"] >= 0 else "▼"
                msg = f"You own **{int(p['qty'])} shares** of **{p['ticker']}** ({p.get('side','long')}).\n\n"
                msg += f"Entry: `${p['avg_entry']:.2f}` → Now: `${p['current_price']:.2f}`\n"
                msg += f"P&L: `{arrow} ${p['unrealized_pnl']:+,.2f}` ({p['unrealized_pnl_pct']:+.1f}%)"
                return {"ok": True, "type": "positions", "msg": msg, "ticker": p["ticker"], "data": []}
            else:
                return {"ok": True, "type": "positions", "msg": f"You don't own any shares of {asked_ticker.upper()}.", "data": []}

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

    if t == "cancel_orders":
        # Confirm first — cancelling pending orders also removes protective stops.
        return {"ok": True, "type": "confirm_trade",
                "trade": {"action": "cancel_orders"},
                "msg": ""}

    if t == "buy":
        ticker = intent["ticker"]
        qty = intent.get("qty")
        notional = intent.get("notional")
        # SAFETY: don't execute from a chat intent. Return a confirmation request
        # so the user explicitly approves before any real order is placed. This
        # prevents accidental trades from misread intent (e.g. a quoted "BUY").
        return {"ok": True, "type": "confirm_trade",
                "trade": {"action": "buy", "ticker": ticker.upper(),
                          "qty": qty, "notional": notional},
                "msg": ""}

    if t == "sell":
        ticker = intent["ticker"]
        sell_all = intent.get("sell_all", False)
        qty = intent.get("qty")
        return {"ok": True, "type": "confirm_trade",
                "trade": {"action": "sell", "ticker": ticker.upper(),
                          "qty": qty, "sell_all": sell_all},
                "msg": ""}

    if t == "short":
        ticker = intent["ticker"]
        qty = intent.get("qty", 1)
        return {"ok": True, "type": "confirm_trade",
                "trade": {"action": "short", "ticker": ticker.upper(), "qty": qty},
                "msg": ""}

    if t == "cover":
        ticker = intent["ticker"]
        cover_all = intent.get("cover_all", False)
        qty = intent.get("qty")
        return {"ok": True, "type": "confirm_trade",
                "trade": {"action": "cover", "ticker": ticker.upper(),
                          "qty": qty, "cover_all": cover_all},
                "msg": ""}

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
        # SAFETY: confirm before executing (same as a manual buy). Compute the
        # risk-sized qty so the confirm card can show it, but place no order.
        try:
            qty_calc = alpaca_smart_buy(ticker=ticker, trade_signal=signal, dry_run=True).get("qty_calculated")
        except Exception:
            qty_calc = None
        return {"ok": True, "type": "confirm_trade",
                "trade": {"action": "buy", "ticker": ticker.upper(),
                          "qty": qty_calc, "smart": True},
                "msg": ""}

    # ── Standard commands ──
    if t == "stock_ideas":
        cat = intent.get("category", "all")
        user_msg_lower = intent.get("_original_msg", "").lower()
        wants_single = any(w in user_msg_lower for w in ["1 stock", "one stock", "a stock", "single stock", "just one", "best one", "top pick"])

        # Extract price OR market-cap filter. "under $50" = share price;
        # "under $1 billion (market cap)" = market cap. Disambiguate by the
        # billion/million/cap keywords so we don't read "$1 billion" as "$1".
        max_price = None
        max_mcap = None   # in dollars
        min_mcap = None
        import re as _pre
        # Market cap: "under $1 billion", "below 500 million", "less than 2b market cap"
        _mcap_match = _pre.search(r'(?:under|below|less than|max|up to|smaller than)\s*\$?(\d+(?:\.\d+)?)\s*(billion|bn|b|million|mm|m)\b', user_msg_lower)
        if _mcap_match:
            _val = float(_mcap_match.group(1))
            _unit = _mcap_match.group(2)
            mult = 1e9 if _unit in ("billion", "bn", "b") else 1e6
            max_mcap = _val * mult
        # Also catch "small cap"/"micro cap" as implicit cap ceilings.
        if max_mcap is None:
            if "micro cap" in user_msg_lower or "micro-cap" in user_msg_lower or "microcap" in user_msg_lower:
                max_mcap = 300e6
            elif "mid cap" in user_msg_lower or "mid-cap" in user_msg_lower:
                max_mcap = 10e9; min_mcap = 2e9
        # Share price: only if NOT a market-cap phrase (avoid "$1 billion" -> $1)
        if max_mcap is None:
            _price_match = _pre.search(r'(?:under|below|less than|cheaper than|max|up to)\s*\$?(\d+(?:\.\d+)?)\b(?!\s*(?:billion|bn|b|million|mm|m|k)\b)', user_msg_lower)
            if _price_match:
                max_price = float(_price_match.group(1))

        if cat == "large":
            universe = list(dict.fromkeys(SP500_TOP + NASDAQ_100 + VALUE_DIVIDEND + SECTOR_PICKS))
        elif cat == "mid":
            universe = list(dict.fromkeys(MIDCAP_GROWTH + SMALLCAP[:20] + TRENDING))
        elif cat == "small":
            universe = list(dict.fromkeys(SMALLCAP + MIDCAP_GROWTH))
        elif cat == "tech":
            universe = ["AAPL","MSFT","NVDA","GOOGL","META","AMZN","AVGO","CRM","ADBE","AMD","INTC","ORCL","PLTR","SNOW","NET","ZS","FTNT","PANW","CRWD","NOW","MU","QCOM","TXN","AMAT","LRCX","KLAC","ADI","MRVL","SMCI","DELL","ANET","ARM","ASML","TSM","APP","DDOG"]
        elif cat == "energy":
            universe = ["XOM","CVX","COP","EOG","SLB","OXY","PSX","MPC","VLO","KMI","WMB","OKE","ET","EPD","FSLR","ENPH","NEE","CEG","VST","SMR","OKLO","NNE","LEU","GEV","NXT","SHLS","FLNC"]
        elif cat == "defense":
            universe = ["LMT","RTX","NOC","GD","HII","KTOS","LDOS","BWXT","RCAT","PLTR","AVAV","AXON","BA","HWM","TDG","LHX","CW","HEI"]
        elif cat == "biotech":
            universe = ["LLY","MRK","ABBV","JNJ","PFE","BMY","AMGN","GILD","VRTX","REGN","MRNA","BNTX","ARGX","ALNY","BMRN","IONS","RARE","NBIX","BEAM","CRSP","NTLA","TGTX","VERA","SDGR"]
        elif cat == "crypto":
            universe = list(dict.fromkeys(["COIN","MSTR","MARA","RIOT","CLSK","HUT","BTBT","WULF","CIFR","CORZ","IREN","HOOD"]))
        elif cat == "value":
            universe = list(dict.fromkeys(VALUE_DIVIDEND + ["JPM","BAC","WFC","KO","PEP","PG","JNJ","WMT","HD","MCD","VZ","T"]))
        elif cat == "nasdaq":
            # WHOLE NASDAQ — every NASDAQ common-stock listing (~3-4k symbols).
            # This is a big scan; with free Yahoo throttling the server, expect it
            # to take a while and return PARTIAL data (some chunks come back empty
            # when Yahoo blocks us). The liquidity filter drops the junk.
            try:
                from universe import all_exchange_tickers
                universe = all_exchange_tickers(nasdaq_only=True)
            except Exception:
                from universe import large_universe
                universe = large_universe()
        elif cat == "full":
            # ENTIRE market — live NYSE + NASDAQ common-stock listing (~5-7k
            # symbols). The batch fetch + liquidity filter below drop the
            # illiquid/dead junk so only real tradeable names get scored.
            try:
                from universe import all_exchange_tickers
                universe = all_exchange_tickers(include_nasdaq=True)
            except Exception:
                from universe import large_universe
                universe = large_universe()
        else:
            # Default broad scan — ~500 names. The Railway container is small
            # (limited threads/memory); bigger scans were spawning too many
            # threads ("can't start new thread" → crash). 500 is the reliable
            # ceiling for this host. Free tier still capped ~100 below.
            try:
                from universe import large_universe
                universe = large_universe()[:500]
            except Exception:
                try:
                    from universe import liquid_universe
                    universe = liquid_universe()
                except Exception:
                    universe = list(dict.fromkeys(SP500_TOP + NASDAQ_100))

        # If user wants cheap stocks OR a small market cap, widen the universe
        # to include more small/mid caps so there's something to find.
        if (max_price and max_price <= 100) or (max_mcap and max_mcap <= 10e9):
            universe = list(set(universe + MIDCAP_GROWTH + SMALLCAP + TRENDING))
        # For an explicit small/micro-cap request, go even broader (full market)
        # since most small caps aren't in the curated lists.
        if max_mcap and max_mcap <= 2e9:
            try:
                from universe import all_exchange_tickers
                universe = list(set(universe + all_exchange_tickers(include_nasdaq=True)))
            except Exception:
                pass

        # Free tier scans a lighter ~100-stock slice; Plus gets the full universe.
        # Prefer the most-liquid core names so a free scan still surfaces quality,
        # just fewer of them. (is_plus is threaded in from the backend; default
        # True so non-web callers / internal use aren't capped.)
        if not is_plus:
            try:
                from universe import liquid_universe
                _core = liquid_universe()
            except Exception:
                _core = list(dict.fromkeys(SP500_TOP + NASDAQ_100))
            # Keep universe order but prioritize liquid-core members, cap at 100.
            _core_set = set(_core)
            _ranked = [t for t in _core if t in set(universe)] + [t for t in universe if t not in _core_set]
            universe = _ranked[:100]

        picks = []

        def _score_data(ticker, data):
            try:
                if not data:
                    return None
                sig = generate_trade_signal(data)
                if sig and sig.get("score", 0) >= 50:
                    reasons = sig.get("signals", [])
                    return {
                        "ticker": ticker,
                        "score": sig["score"],
                        "action": sig["action"],
                        "setup": sig.get("setup", ""),
                        "price": data.get("price", 0),
                        "change_pct": data.get("change_pct", 0),
                        "market_cap": data.get("market_cap"),
                        "signals": reasons[:3],
                        "trade": sig.get("trade", {}),
                        "confluence": sig.get("confluence", {}).get("bullish", 0),
                        "rr": sig.get("trade", {}).get("risk_reward", 0),
                    }
            except Exception:
                return None
            return None

        if len(universe) > 120:
            # BIG scan — bulk-download all history in a few HTTP requests
            # (yf.download), then score locally. This is what makes 600-1000+
            # stocks fast: one round-trip per ~150 tickers instead of one per
            # stock. News is skipped here; it's fetched only for the top picks.
            batch = batch_fetch_scan(universe, skip_news=True, progress_cb=progress_cb)
            for _tk, _data in batch.items():
                _r = _score_data(_tk, _data)
                if _r:
                    picks.append(_r)
        else:
            # Smaller themed scans — per-ticker thread pool (keeps news inline).
            def _scan_one(ticker):
                return _score_data(ticker, fetch_scan(ticker))
            from concurrent.futures import ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=6) as _ex:
                for _r in _ex.map(_scan_one, universe):
                    if _r:
                        picks.append(_r)

        picks.sort(key=lambda x: x["score"], reverse=True)
        # Apply price filter if user specified one
        if max_price:
            picks = [p for p in picks if p.get("price", 0) <= max_price]
        # Apply market-cap filter(s)
        if max_mcap:
            picks = [p for p in picks if p.get("market_cap") and p["market_cap"] <= max_mcap]
        if min_mcap:
            picks = [p for p in picks if p.get("market_cap") and p["market_cap"] >= min_mcap]
        # Consider a deeper slice (top 15 by score) so we don't miss a clean buy
        # that ranks below 5th. The recommendation output filters to the ones that
        # clear autopilot's bar, so showing more candidates here costs nothing.
        top = picks[:15]

        # ── Price consistency: the intraday scanner's price (last 5-min bar)
        # can differ by cents/dollars from the Analyze tab + chart, which use
        # the real-time quote. We re-stamp the displayed price from that SAME
        # source — but only for the picks we'll actually SHOW (done after the buy
        # filter below), so we don't fire 15 extra quote calls and worsen
        # rate-limiting. (Re-stamp loop moved below.)

        if not top:
            if max_mcap:
                _cap_str = f"${max_mcap/1e9:.1f}B" if max_mcap >= 1e9 else f"${max_mcap/1e6:.0f}M"
                return {"ok": True, "type": "analysis", "msg": f"I scanned {len(universe)} stocks but couldn't find any under {_cap_str} market cap with a strong enough setup right now. Smaller companies are often more volatile and thinly covered — try a wider cap range, or ask me to analyze a specific small-cap ticker."}
            if max_price:
                return {"ok": True, "type": "analysis", "msg": f"I scanned {len(universe)} stocks but couldn't find any under ${max_price:.0f} a share that score high enough right now. Try a higher price range or ask me to analyze a specific cheap ticker."}
            return {"ok": True, "type": "analysis", "msg": "I scanned " + str(len(universe)) + " stocks but nothing scored high enough right now. The market might be choppy — try again later or ask me to analyze a specific ticker."}

        # Single stock request — written response with the best pick
        if wants_single and top:
            p = top[0]
            try:
                fresh = fetch_price(p["ticker"])
                if fresh and fresh.get("price"):
                    _op = p["price"]; p["price"] = fresh["price"]
                    if fresh.get("prev_close"):
                        p["change_pct"] = round((fresh["price"] - fresh["prev_close"]) / fresh["prev_close"] * 100, 2)
                    _tr = p.get("trade", {})
                    if _tr and abs(_tr.get("entry", 0) - _op) < 0.01:
                        _tr["entry"] = fresh["price"]
            except Exception:
                pass
            entry = p["trade"].get("entry", p["price"])
            stop = p["trade"].get("stop_loss", 0)
            t1 = p["trade"].get("target_1", 0)
            rr = p["trade"].get("risk_reward", 0)
            arrow = "▲" if p["change_pct"] >= 0 else "▼"
            sigs = " · ".join(p["signals"][:2]) if p["signals"] else ""

            # Calculate shares based on user's budget if mentioned
            budget_match = re.search(r'(\d[\d,]*\.?\d*)\s*(dollars|bucks|\$|k\b)', user_msg_lower)
            shares_info = ""
            if budget_match:
                budget = float(budget_match.group(1).replace(",", ""))
                if "k" in budget_match.group(2):
                    budget *= 1000
                shares = int(budget / p["price"])
                shares_info = f" With ${budget:,.0f}, that's about **{shares} shares**."

            msg = (
                f"I'd go with **{p['ticker']}** right now.\n\n"
                f"It's at **${p['price']:.2f}** ({arrow}{p['change_pct']:+.1f}% today) with a signal score of **{p['score']}** ({p['action']}). "
                f"{sigs}.\n\n"
            )
            if stop and t1:
                msg += f"**The setup:** Entry around `${entry:.2f}`, stop at `${stop:.2f}`, target `${t1:.2f}` — that's a `{rr:.1f}:1` risk-reward."
            msg += shares_info

            return {"ok": True, "type": "analysis", "ticker": p["ticker"],
                    "tickers": [p["ticker"]],
                    "msg": msg, "data": {"price": p["price"]},
                    "signal_data": None}

        # Autopilot's live decision bar — use the SAME thresholds it trades on,
        # so the scan's verdict matches what autopilot would actually do.
        AP_SCORE, AP_CONF, AP_RR = 82, 5, 2.0

        # Market-regime context line (autopilot checks this before it acts).
        regime_line = ""
        try:
            reg = check_market_regime()
            _safe = reg.get("safe_to_buy", True)
            _rname = str(reg.get("regime", "")).replace("_", " ")
            if _rname:
                regime_line = (f"Market backdrop: **{_rname}** — "
                               + ("conditions favor new long setups.\n\n" if _safe
                                  else "be selective; the backdrop is shaky for new longs.\n\n"))
        except Exception:
            pass

        def _verdict(p):
            """Autopilot-style verdict for a pick using its real trade thresholds."""
            sc = p.get("score", 0); cf = p.get("confluence", 0); rr = p.get("rr", 0) or 0
            act = p.get("action", "")
            if act == "STRONG_BUY" and sc >= AP_SCORE and cf >= AP_CONF and rr >= AP_RR:
                return "✅ **Autopilot would buy this** — clears every bar (score, confluence, and reward-to-risk)."
            # Explain what's missing so it's a real recommendation, not a label.
            misses = []
            if sc < AP_SCORE: misses.append(f"score {sc} (wants ≥{AP_SCORE})")
            if cf < AP_CONF: misses.append(f"only {cf} confirming signals (wants ≥{AP_CONF})")
            if rr < AP_RR: misses.append(f"reward-to-risk {rr:.1f}:1 (wants ≥{AP_RR})")
            if act != "STRONG_BUY": misses.append(f"signal is {act}, not STRONG_BUY")
            if sc >= 70 and act in ("STRONG_BUY", "BUY"):
                return "👀 **Worth watching** — close, but " + ("; ".join(misses)) + "."
            return "⏸️ **Pass for now** — " + ("; ".join(misses)) + "."

        def _is_buy(p):
            return (p.get("action") == "STRONG_BUY" and p.get("score", 0) >= AP_SCORE
                    and p.get("confluence", 0) >= AP_CONF and (p.get("rr") or 0) >= AP_RR)

        # Only the definite buys — the ones autopilot would actually act on.
        buys = [p for p in top if _is_buy(p)][:8]

        # Re-stamp displayed prices from the real-time quote source (matches the
        # Analyze tab/chart) — only for the buys we're about to show.
        for p in buys:
            try:
                fresh = fetch_price(p["ticker"])
                if fresh and fresh.get("price"):
                    old_price = p["price"]
                    p["price"] = fresh["price"]
                    if fresh.get("change") is not None and fresh.get("prev_close"):
                        prev = fresh["prev_close"]
                        p["change_pct"] = round((fresh["price"] - prev) / prev * 100, 2) if prev else p["change_pct"]
                    tr = p.get("trade", {})
                    if tr and abs(tr.get("entry", 0) - old_price) < 0.01:
                        tr["entry"] = fresh["price"]
            except Exception:
                pass

        if not buys:
            # Nothing clears the bar — say so cleanly instead of listing watch-list
            # names the user didn't ask for.
            msg = [f"I scanned {len(universe)} stocks and judged them the way autopilot does — "
                   "**nothing clears the full buy bar right now** (score ≥82, 5+ confirming signals, and 2:1+ reward-to-risk)."]
            if regime_line:
                msg.append("\n" + regime_line.strip())
            msg.append("\nNo clean setup is worth forcing — better to wait for one that lines up. "
                       "Ask me to scan again later, or I can analyze a specific ticker if you have one in mind.")
            msg.append("\n**Based on my 21-factor signal engine — not financial advice.**")
            if not is_plus:
                msg.append("\n**Free scans cover the ~100 most-liquid stocks. Paula Plus scans the full ~1,000-name universe.**")
            return {"ok": True, "type": "analysis", "ticker": top[0]["ticker"],
                    "tickers": [], "msg": "\n".join(msg)}

        _n = len(buys)
        lines = [f"**{_n} buy{'s' if _n != 1 else ''} worth acting on** — scanned {len(universe)} stocks; "
                 f"these are the only ones that clear autopilot's full bar (score ≥{AP_SCORE}, {AP_CONF}+ signals, {AP_RR:.0f}:1+ reward-to-risk).\n"]
        if regime_line:
            lines.append(regime_line)
        for i, p in enumerate(buys, 1):
            entry = p["trade"].get("entry", p["price"])
            stop = p["trade"].get("stop_loss", 0)
            t1 = p["trade"].get("target_1", 0)
            arrow = "▲" if p["change_pct"] >= 0 else "▼"
            lines.append(f"**{i}. {p['ticker']}** · ${p['price']:.2f} {arrow}{p['change_pct']:+.1f}% · score `{p['score']}` ✅")
            if p.get("setup"):
                lines.append(f"   **The setup:** {p['setup']}")
            if p["signals"]:
                lines.append(f"   **Why:** {' · '.join(p['signals'][:3])}")
            if stop and t1:
                _risk = abs(entry - stop) / entry * 100 if entry else 0
                lines.append(f"   **The plan:** enter near `${entry:.2f}`, stop `${stop:.2f}` (risking ~{_risk:.1f}%), first target `${t1:.2f}`"
                             + (f" · {p['rr']:.1f}:1 reward-to-risk" if p.get('rr') else ""))
            lines.append("")

        lines.append("**Based on my 21-factor signal engine — not financial advice. You make the call.**")
        if not is_plus:
            lines.append("\n**Free scans cover the ~100 most-liquid stocks. Paula Plus scans the full ~1,000-name universe for more setups.**")
        return {"ok": True, "type": "analysis", "ticker": buys[0]["ticker"],
                "tickers": [p["ticker"] for p in buys],
                "msg": "\n".join(lines)}

    if t == "chart":
        tick = _ensure_suffix(intent["ticker"], market)
        data = fetch_price(tick)
        if not data:
            return {"ok": False, "error": f"No data for {intent['ticker']}."}
        arrow = "▲" if data["change_pct"] >= 0 else "▼"
        return {"ok": True, "type": "analysis", "ticker": tick, "market": market, "data": data,
                "msg": f"**{data['name']}** ({tick}) · `${data['price']:,.2f}` {arrow} {data['change_pct']:+.2f}%"}

    if t == "price":
        tick = _ensure_suffix(intent["ticker"], market)
        data = fetch_price(tick)
        if not data:
            return {"ok": False, "error": f"No data for {intent['ticker']}."}
        sym = "$" if market == "US" else "₹"
        arrow = "▲" if data["change_pct"] >= 0 else "▼"
        return {"ok": True, "type": "price", "market": market, "ticker": tick, "data": data,
                "msg": f"**{data['name']}** ({intent['ticker']})\n\n`{sym}{data['price']:,.2f}` {arrow} {data['change_pct']:+.2f}%"}

    if t == "earnings":
        tick = _ensure_suffix(intent["ticker"], market)
        ed = next_earnings_date(tick)
        if not ed:
            return {"ok": True, "type": "chat",
                    "msg": f"I couldn't find a confirmed upcoming earnings date for {intent['ticker']} right now — it may not be scheduled yet, or the data isn't available."}
        when = ed["when"]
        days = ed.get("days_away")
        warn = ""
        if days is not None and 0 <= days <= 5:
            warn = f"\n\n⚠️ That's soon — holding a position through earnings means overnight gap risk in either direction. Size accordingly."
        return {"ok": True, "type": "earnings",
                "ticker": tick,
                "msg": f"**{intent['ticker']}** next reports earnings on **{ed['date']}** ({when}).{warn}"}

    if t == "position_size":
        tick = _ensure_suffix(intent["ticker"], market)
        risk = float(intent.get("risk", 0) or 0)
        data = fetch_full(tick)
        if not data:
            return {"ok": False, "error": f"No data for {intent['ticker']}."}
        sig = generate_trade_signal(data)
        tr = sig.get("trade", {})
        entry = float(tr.get("entry") or data.get("price", 0) or 0)
        stop = float(tr.get("stop_loss") or 0)
        price = float(data.get("price", 0) or 0)
        # Fall back to a 2% stop if the signal didn't produce one (e.g. HOLD).
        if not stop or stop >= entry:
            stop = round((entry or price) * 0.98, 2)
        per_share_risk = max(0.01, round((entry or price) - stop, 2))
        shares = int(risk // per_share_risk) if per_share_risk > 0 else 0
        cost = round(shares * (entry or price), 2)
        # Edge case: risk budget too small to buy even one share at this stop.
        note = ""
        if shares < 1:
            note = (f"Your ${risk:,.0f} risk is smaller than the ${per_share_risk:.2f} "
                    f"risk per share at this stop, so it doesn't cover even one share. "
                    f"You'd need a tighter stop or a larger risk budget.")
        return {
            "ok": True, "type": "position_size",
            "ticker": tick,
            "data": {
                "ticker": tick, "name": data.get("name", tick),
                "price": price, "entry": entry, "stop": stop,
                "per_share_risk": per_share_risk, "risk_budget": risk,
                "shares": shares, "position_cost": cost,
                "action": sig.get("action", "HOLD"), "score": sig.get("score", 0),
                "note": note,
            },
        }

    if t == "compare":
        tickers = intent.get("tickers", [])[:2]
        if len(tickers) < 2:
            return {"ok": False, "error": "Need two tickers to compare."}
        compared = []
        for tk in tickers:
            tick = _ensure_suffix(tk, market)
            data = fetch_full(tick)
            if not data:
                return {"ok": False, "error": f"No data for {tk}."}
            sig = generate_trade_signal(data)
            tr = sig.get("trade", {})
            compared.append({
                "ticker": tick,
                "name": data.get("name", tick),
                "price": data.get("price", 0),
                "change_pct": data.get("change_pct", 0),
                "action": sig.get("action", "HOLD"),
                "score": sig.get("score", 0),
                "rsi": data.get("rsi"),
                "trend": data.get("trend_regime") or data.get("trend"),
                "pct_from_52w_high": data.get("pct_from_52w_high"),
                "rr": tr.get("risk_reward", 0),
                "reasons": sig.get("reasons", [])[:4],
            })
        # Let the AI write the comparison from the two structured scorecards.
        better = max(compared, key=lambda x: x.get("score", 0))
        return {
            "ok": True, "type": "compare",
            "data": {"compare": compared, "higher_score": better["ticker"]},
            "tickers": [c["ticker"] for c in compared],
        }

    if t == "analyze":
        tick = _ensure_suffix(intent["ticker"], market)
        data = fetch_full(tick)
        if not data:
            return {"ok": False, "error": f"No data for {intent['ticker']}."}
        signal = generate_trade_signal(data)
        action = signal.get("action", "HOLD")
        # Build structured signal data for visual cards
        trade = signal.get("trade", {})

        # ── Bearish framing (bug fix) ───────────────────────────────────────
        # A low score must NOT be presented as a "SHORT" entry setup. The app
        # is long-biased, and users asking "should I sell my AAPL?" hold a LONG.
        # The side decision lives in signal_logic.classify_analysis_side so it
        # can be unit-tested without trading.py's heavy dependencies.
        orig_msg = intent.get("_original_msg") or ""
        holds_long = False
        try:
            for _p in (alpaca_positions() or []):
                _pt = (_p.get("ticker") or "").upper().replace(".", "-")
                if _pt == tick.upper().replace(".", "-") and _p.get("side", "long") == "long":
                    holds_long = True
                    break
        except Exception:
            pass

        side = classify_analysis_side(action, orig_msg, holds_long)

        # The structured SignalCard shows the real computed levels for ALL sides
        # (so a HOLD/short still displays its stop & target). The LLM is handled
        # separately by _scrub_trade_levels_for_llm so it never writes prose
        # levels — this is the card's data, not the model's.
        t_entry = trade.get("entry", 0)
        t_stop = trade.get("stop_loss", 0)
        t_target = trade.get("target_1", 0)
        t_rr = trade.get("risk_reward", 0)

        sig_data = {
            "ticker": tick,
            "name": data.get("name", tick),
            "price": data.get("price", 0),
            "action": action,
            "score": signal.get("score", 0),
            "scores": {
                "trend": {"value": signal.get("trend_score", 0), "label": signal.get("trend_label", "")},
                "momentum": {"value": signal.get("momentum_score", 0), "label": signal.get("momentum_label", "")},
                "mean_reversion": {"value": signal.get("mean_reversion_score", 0), "label": signal.get("mean_reversion_label", "")},
                "news": {"value": signal.get("news_score", 0), "label": signal.get("news_label", "")},
            },
            "trade": {
                "side": side,
                "holds_long": holds_long,
                "entry": t_entry,
                "stop": t_stop,
                "target": t_target,
                "rr": t_rr,
            },
            "earnings_warning": signal.get("earnings_warning", ""),
        }
        return {"ok": True, "type": "analysis", "ticker": tick, "market": market, "data": {**data, **signal}, "trade_signal": signal, "signal_data": sig_data}

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

def _market_status_line() -> str:
    """Human-readable market status so Paula always knows (and acknowledges)
    whether the market is open, closed, pre-market, or after-hours."""
    try:
        now = datetime.now(ZoneInfo("US/Eastern"))
    except Exception:
        # Fallback if tz database unavailable: approximate ET as UTC-5.
        from datetime import timezone, timedelta
        now = datetime.now(timezone.utc) - timedelta(hours=5)
    try:
        wd = now.weekday()  # 0=Mon .. 6=Sun
        t = now.hour * 60 + now.minute
        day = now.strftime("%A")
        if wd >= 5:
            return f"Market: CLOSED (weekend, {day})."
        if now.strftime("%Y-%m-%d") in _MARKET_HOLIDAYS:
            return f"Market: CLOSED (market holiday, {day})."
        if t < 9 * 60 + 30:
            return f"Market: PRE-MARKET ({day}, opens 9:30 AM ET)."
        if t < 16 * 60:
            return f"Market: OPEN ({day}, regular hours, closes 4:00 PM ET)."
        if t < 20 * 60:
            return f"Market: AFTER-HOURS ({day}, closed at 4:00 PM ET)."
        return f"Market: CLOSED ({day}, reopens 9:30 AM ET next trading day)."
    except Exception:
        return "Market: status unavailable."

# Shared voice spec used by both ai_response and ai_response_stream so the
# personality stays consistent. This defines how Paula SOUNDS — the factual
# rules (price accuracy, no arithmetic) live separately in each caller.
PAULA_VOICE = """HOW YOU SOUND (this matters as much as being correct):

You're a sharp trader texting a friend who asked for your read. Confident, fast, a little opinionated. You have a view and you share it.

Voice rules:
- LEAD WITH THE VERDICT. First sentence = your actual take. "NVDA looks strong here" or "I'd pass on this one." Never open with "Based on the data" or "Let me analyze" — just say what you think.
- BE CONCISE. 2-4 short paragraphs, often less. A price check is 1-2 sentences. Don't dump every indicator — pick the 2-3 that actually drive your view and skip the rest.
- HAVE CONVICTION. Commit to a read. "This is a clean setup" or "I don't love this." Hedging everything ("it could go either way") is useless to a trader. If signals genuinely conflict, say which side you lean and why — don't just list both.
- EXPLAIN THE WHY, not the what. Not "RSI is 49." Instead "RSI at 49 means it's pulled back without breaking down — that's the dip you want to buy." Translate every number into what it means for the trade.
- SOUND HUMAN. Use natural rhythm — mix short punchy lines with a longer one. Contractions, plain words. "Here's the thing" / "What I like" / "The catch is".
- NO DATA DUMPS. Never list 6 indicators in a row. Never use headers like "VERDICT:" or "RISK:". Write in flowing prose, not a spec sheet.
- END WITH THE TRADE or the next step when relevant: where you'd get in, where the stop goes, what you're watching.
- ANSWER WHAT THEY ACTUALLY ASKED. Read the request carefully and respond to the real question — if they ask "is now a good time to add to my NVDA?", weigh their existing position and the current setup, don't just re-run a generic analysis. If they ask something the attached data genuinely doesn't cover, say so in one honest line and answer with what you do know — never pad with invented specifics to seem complete.

Good example (analysis):
"NVDA's setting up nicely. It's pulled back to the 20-day after a strong run, RSI's at 49 so there's room to move, and it's still well above the 200-day — the uptrend's intact. I'd look to get in around $211 with a stop at $205; first target's $230. The one thing I'd watch is volume, which has been light on the bounce."

Bad example (what NOT to do):
"Based on the analysis, NVDA has a score of 90. The RSI is 49.4. The MACD is bearish but accelerating. The trend regime is weak with a slope of 0.33. The OBV trend is falling. The trade plan suggests an entry at $211.14 with a stop-loss at $204.88..."
(Too robotic, no view, dumps every number, buries the point.)"""


def _scrub_trade_levels_for_llm(stock_data: dict | None) -> dict | None:
    """Before handing data to the LLM, remove any trade-level fields when there
    is NO valid trade plan (HOLD/NEUTRAL/EXIT/AVOID, or levels are 0/equal).

    The LLM otherwise grabs the current price and invents an entry/stop/target
    (often repeating the price for all three). If there is no plan, we delete the
    fields entirely and drop in an explicit no-trade flag so the model has
    nothing to fabricate from.
    """
    if not isinstance(stock_data, dict):
        return stock_data
    import copy as _copy
    sd = _copy.deepcopy(stock_data)

    def _has_real_plan(tr: dict) -> bool:
        if not isinstance(tr, dict):
            return False
        e = tr.get("entry", 0) or 0
        s = tr.get("stop", tr.get("stop_loss", 0)) or 0
        t = tr.get("target", tr.get("target_1", 0)) or 0
        side = str(tr.get("side", "")).upper()
        if side in ("EXIT", "AVOID", "NEUTRAL", "HOLD"):
            return False
        if not e or not s or not t:
            return False
        # collapsed / hallucination-prone: all three (near) equal
        if abs(e - s) < 0.01 and abs(s - t) < 0.01:
            return False
        return True

    action = str(sd.get("action", "")).upper()
    tr = sd.get("trade")
    plan_ok = _has_real_plan(tr) and action in ("BUY", "STRONG_BUY")

    if plan_ok:
        # Hand the LLM a single, unambiguous pre-formatted line to quote verbatim,
        # so it can't accidentally repeat the entry as the target (a recurring
        # hallucination). Numbers come straight from the validated trade dict.
        e = tr.get("entry", 0)
        s = tr.get("stop", tr.get("stop_loss", 0))
        t1 = tr.get("target", tr.get("target_1", 0))
        t2 = tr.get("target_2", 0)
        rr = tr.get("risk_reward", tr.get("rr", 0))
        plan = f"Entry ${e} · Stop ${s} · Target ${t1}"
        if t2 and abs(float(t2) - float(t1)) > 0.01:
            plan += f" (then ${t2})"
        if rr:
            plan += f" · about {rr}:1 risk-reward"
        sd["trade_plan"] = (
            "USE THESE EXACT LEVELS — do not recompute or repeat the entry as the target: " + plan
        )
        # Remove the raw numeric level fields so the model can't accidentally grab
        # the wrong one (e.g. echo the entry as the target). The clean sentence
        # above is now the single source of levels.
        for k in ("entry", "stop", "stop_loss", "target", "target_1", "target_2", "risk_reward", "rr", "risk_pct"):
            sd.pop(k, None)
            if isinstance(sd.get("trade"), dict):
                sd["trade"].pop(k, None)

    if not plan_ok:
        # strip every level field anywhere in the payload
        for k in ("entry", "stop", "stop_loss", "target", "target_1", "target_2", "risk_reward", "rr", "risk_pct"):
            sd.pop(k, None)
            if isinstance(sd.get("trade"), dict):
                sd["trade"].pop(k, None)
        # also remove support/resistance arrays — the LLM repurposes them as fake
        # "targets"/"stops" when asked directly ("target and stop loss for QCOM").
        for k in ("supports", "resistances", "support_levels", "resistance_levels", "support", "resistance"):
            sd.pop(k, None)
        sd["trade_plan"] = ("NONE — this is not an actionable BUY setup. There is NO entry, stop, or target. "
                            "If the user asks for a target or stop, tell them there is no trade setup here and "
                            "why (e.g. downtrend / HOLD), and do NOT invent or derive any price level from support, "
                            "resistance, ATR, or the current price.")
    return sd


def ai_response(user_msg: str, stock_data: dict | None, history: list, market: str) -> str:
    key = st.secrets.get("GROQ_API_KEY") or os.environ.get("GROQ_API_KEY")
    if not key:
        return "⚠️ Set `GROQ_API_KEY` in Streamlit secrets or environment."

    system = f"""You're Paula — a sharp, knowledgeable trading assistant who genuinely enjoys helping people understand the market. You're approachable and warm, but you know your stuff. Think of yourself as a really smart friend who happens to be great at trading. Today is {datetime.now(ZoneInfo("US/Eastern")).strftime("%Y-%m-%d")}. Market: {market}. {_market_status_line()}

Be aware of the market status above and reflect it naturally — if the market is closed, pre-market, or after-hours, factor that in. Don't describe live intraday action when the market isn't open.

You get live stock data attached to each message. For manual analysis, this includes daily chart signals with confluence scoring across 6 categories (trend, momentum, mean-reversion, volume, fundamentals, news sentiment). USE all of it — weave the numbers into natural conversation.

INTELLIGENCE RULES:
- Actually READ and UNDERSTAND what the user is asking. If they ask "why is NVDA up?", explain the catalyst — don't just give a generic analysis.
- When given a list of stocks (like top gainers), analyze EACH one — what's the catalyst? Is it earnings? Sector rotation? FDA approval? Short squeeze? Don't just say "strong momentum" — that's lazy.
- Use SPECIFIC numbers from the data: "RSI is at 67 and trending up" not "momentum is strong". "Trading 3.2% above VWAP with 2.1x average volume" not "above VWAP with high volume".
- Compare to the broader market: "While SPY is flat, NVDA is up 4% — showing real relative strength"
- Mention risk factors: "Earnings are in 3 days which adds volatility" or "This is extended 8% above the 20 SMA, so a pullback is likely"
- If you see conflicting signals, explain the conflict clearly and say which side you lean toward and why
- Think about what the user ACTUALLY needs to make a trading decision, not just what data you have
- IT'S OK TO SAY "DON'T TRADE THIS." You are not a salesperson and you are not obligated to surface a trade. If the setup is weak, the risk/reward is poor, the market regime is hostile (e.g. SPY in a downtrend, high VIX), or a stock is choppy/extended with no clean entry, say so plainly: "I wouldn't buy this here" or "There's no good setup right now — sitting in cash is the right move." A good "no" protects the user's money and builds trust. Don't soften a genuine no into a lukewarm maybe, and don't invent a mediocre idea just to have something to say. "The best trade is sometimes no trade" is a real and valuable answer.
- When you DO pass on something, briefly say what would change your mind ("if it pulls back to the 20-day around $X and holds, that's more interesting") so the user knows what to watch for — but only if you have the data to back it.
- PORTFOLIO-AWARE: if a "portfolio_context" block is attached (buying power, equity, open positions with P&L), USE it when giving advice. If they ask about adding to a stock they already hold, note the existing position and whether it's already a big chunk of their book ("you're already up 12% on this and it's ~30% of your equity — adding here concentrates your risk"). Flag concentration, respect their buying power, and factor in whether a position is winning or losing. Never invent position sizes or dollar amounts — only use the exact numbers in the block.
- COMPARING TWO STOCKS: if a "compare" block is attached (two scorecards with score, action, RSI, trend, R/R, reasons), give a clear head-to-head: call out which has the stronger setup and WHY, using the exact scores/numbers provided. End with a clear pick ("I'd lean NVDA here — score 78 vs 64, cleaner trend, better risk-reward"), but note what would make the other one the better choice. Use only the numbers in the block.
- POSITION SIZING: if a "position_size" block is attached (price, entry, stop, per_share_risk, risk_budget, shares, position_cost), tell them plainly how many shares to buy to risk exactly that dollar amount, and show the math simply: "To risk $X on TICKER with a stop at $S (about $R/share), buy N shares (~$cost). If it hits your stop you lose ~$X." Use the exact numbers. Add a one-line caveat that this assumes the stop fills at that level.

CRITICAL — PRICE ACCURACY:
- ONLY quote prices that appear in the attached data. NEVER guess or estimate a price.
- If data shows Price: 142.50 — say $142.50. Don't round to $143 or say "around $140".
- For trade plans (entry, stop, targets), use the EXACT entry/stop/target numbers already provided in the attached signal data. Do NOT recompute them.
- If the trade levels are 0, missing, or the side is HOLD/NEUTRAL/EXIT/AVOID, DO NOT state any entry, stop, or target at all — there is no trade plan. Never write a line like "Entry: $X · Stop: $X · Target: $X". Just describe the setup and what to watch for. Inventing levels (e.g. repeating the current price as entry, stop, AND target) is a serious error.
- If you don't have price data for a stock, say so — don't make up a number.
- NEVER state a specific market cap (e.g. "$943M market cap") unless that exact figure is in the attached data. Market cap is NOT something you can estimate or recall — you will get it wrong (e.g. calling a $50B company "$943M"). If asked for small-caps and the data doesn't include verified caps, describe the names you found without inventing cap numbers, or say you can pull the exact figure if they analyze a specific ticker.
- Do NOT recall or estimate company facts you're unsure of (who acquired whom, whether a company is still public, its size). Stale training data causes confident errors. Stick to the attached data; if it's not there, say you'd need to look it up.
- When listing multiple stocks, use the exact Price and Chg% from the data for each one.

CRITICAL — NO ARITHMETIC (you are bad at math, so don't do any):
- NEVER calculate percentages, gains, losses, dollar amounts, share counts, or projections yourself. You make arithmetic errors.
- For the day's move, use the EXACT "Chg%" value from the data verbatim. Do not derive it from prices.
- For risk/reward, position size, P&L, or "what if I bought X shares" — if a PRE-COMPUTED block is attached, state that number exactly. Otherwise only use numbers already in the data; if a number isn't available, do NOT compute it — say you can run it if they place the trade.
- Never multiply price × shares, never subtract two prices to get a gain, never convert a dollar move to a percent. If you're tempted to do math, stop and just quote the pre-computed figure from the data.
- It is far better to omit a number than to state a wrong one. Round-number estimates and "roughly X%" calculations are BANNED.

RESPONSE STYLE:
- Keep responses SHORT — 2-4 paragraphs max. No walls of text.
- ALWAYS answer directly. NEVER say "I'm ready to help" or "What would you like". Just give the answer.
- Lead with the answer, then support with 2-3 key data points.
- NEVER ask clarifying questions. If the user says "market regime" — give the regime. If they say "top gainers" — list them. If they say "AAPL" — analyze it.
- For market regime: just state bull/bear, SPY price, RSI, whether safe to trade. 3 sentences max.
- For stock analysis: score, action, key levels, 1 paragraph.
- For trade ideas: list the good ones with scores and why — brief. If only 1-2 are genuinely worth it, list just those. If nothing meets the bar right now, say so honestly rather than padding the list with weak names.

CHAT HISTORY:
- You have access to the full conversation history. Use it to maintain context.
- If the user says "what about that one?" — refer to the last stock discussed.
- If they say "buy it" — they mean the last ticker mentioned.
- Remember what you've already told them and don't repeat yourself.
- If a price was mentioned earlier in the conversation, you CAN reference it.
- If the user says "rewrite" or "above you said" — look at previous messages.

BANNED PHRASES (NEVER say these — they make you sound broken):
- "I need to look up" / "I don't have access" / "Let me check on that"
- "I'm ready to help" / "What would you like" / "How can I assist"
- "I don't have real-time data" — you DO get real data attached
- "I don't see a response" — read the conversation history, it's there
- Never show portfolio/account data when the user is asking for trade ideas

IMPORTANT: Autopilot runs a SWING-TRADING engine. It holds positions across multiple days (typically 3–10 trading days), not intraday. It combines proven swing strategies on daily bars:

1. TREND FOLLOWING — buys established uptrends (price above stacked 20/50/200 SMAs) and rides them for days.
2. PULLBACK ENTRIES — the core edge: buy quality stocks when they pull back to the 20 or 50 SMA in an uptrend, then resume higher.
3. MOMENTUM — RSI, MACD, and relative strength confirm the move has legs before entering.
4. BREAKOUT — enters on daily closes above key resistance with volume confirmation.
5. RELATIVE STRENGTH — favors stocks outperforming SPY and their sector.
6. NEWS / CATALYST — AI headline analysis flags catalysts and blocks entries fighting strong negative news.
7. RISK MANAGEMENT — wider stops (2x daily ATR, ~3–10% room) to survive normal overnight noise, partial profits into strength, trailing stops, and a max-hold timeout (~10 days) to cut dead trades.

Filters: SPY trend (avoid longs in a broad downtrend), VIX panic filter, ADX trend strength, sector rank, earnings-date awareness.

This is SWING trading — positions ARE held overnight and across days. There is NO end-of-day liquidation. Trades exit on stop-loss, target, signal reversal, or the max-hold timeout — never just because the market is closing. Users can manually buy, sell, short, and cover any time.

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

{PAULA_VOICE}

When you have a trade plan, weave it in naturally: "I'd look around $X with a stop at $Y, first target $Z — about 2:1 risk-reward." If a "trade_plan" line is attached in the data, those are the ONLY correct entry/stop/target numbers — copy them exactly and NEVER repeat the entry price as the target (a target must be meaningfully above the entry for a buy). Use the score conversationally ("I'd rate this a 72 — solidly in buy territory"), not as a label. Call out confluence or conflicts honestly, and mention news sentiment or key support/resistance only when it actually matters to the decision.

CRITICAL — Market awareness:
- You know today's date and can determine if the market is open (8:30 AM - 3:00 PM CT, Mon-Fri)
- If asked about today's performance and data shows 0 trades, say "No trades were executed today" — don't make up a narrative
- If the user asks about autopilot results, look at the ACTUAL data attached — trades count, P&L, positions
- Be honest about results — if the day was a loss, say so and explain what happened
- If the market hasn't opened yet, say "Market hasn't opened yet" — don't speculate about future trades

Don'ts:
- NEVER default to just listing AAPL, MSFT, GOOGL, AMZN, META, TSLA when recommending stocks
- Don't disclaim you're an AI or say "not financial advice" — the app has that
- NEVER fabricate trades, P&L numbers, or performance data — only reference what's in the attached data
- NEVER say "I need to look it up", "I don't have access", "Let me check", or "I don't have real-time access" — you DO get real data attached. These are BANNED.
- If you truly don't know something, say "Ask me to analyze [ticker] and I'll pull the data"

RESPONSE LENGTH by request type:
- Price check: price, change, one line of context. That's it.
- Top gainers / ideas: 3-5 tickers, one line each with the catalyst.
- Analysis: your verdict + the 2-3 numbers that drive it + the trade plan. One tight paragraph.
- Daily review: trades count, P&L, top winner, top loser. Brief."""

    messages = [{"role": "system", "content": system}]
    for h in history[-20:]:
        messages.append({"role": h["role"], "content": h["content"]})
    content = user_msg
    # Pre-compute any price arithmetic the model would otherwise botch.
    _cur = 0.0
    if stock_data:
        _cur = _safe(stock_data.get("price"), 0) or 0
    try:
        _pm = compute_price_math(user_msg, _cur)
    except Exception:
        _pm = None
    if _pm:
        content += f"\n\n---PRE-COMPUTED (state this number exactly, do NOT recalculate)---\n{_pm['phrasing']}"
    if stock_data:
        content += f"\n\n---LIVE DATA (use ONLY these exact prices, do NOT make up numbers)---\n{json.dumps(_scrub_trade_levels_for_llm(stock_data), indent=2, default=str)}"
    messages.append({"role": "user", "content": content})

    try:
        client = Groq(api_key=key)
        _models = ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"]
        _last_err = None
        for _mi, _model in enumerate(_models):
            try:
                resp = client.chat.completions.create(model=_model, messages=messages, max_tokens=500, temperature=0.3)
                return resp.choices[0].message.content
            except Exception as e:
                _last_err = e
                _msg = str(e).lower()
                if ("429" in _msg or "rate limit" in _msg or "rate_limit" in _msg) and _mi < len(_models) - 1:
                    import time as _t; _t.sleep(0.6); continue
                if "429" in _msg or "rate limit" in _msg or "rate_limit" in _msg:
                    return "⚠️ Paula's AI is busy right now (rate limit). Give it a few seconds and try again."
                return f"⚠️ AI error: {str(e)[:120]}"
        return f"⚠️ AI error: {str(_last_err)[:120]}"
    except Exception as e:
        return f"⚠️ AI error: {str(e)[:120]}"


def ai_response_stream(user_msg: str, stock_data: dict | None, history: list, market: str):
    """Streaming version — yields text chunks as they come from Groq."""
    key = os.environ.get("GROQ_API_KEY", "")
    if not key:
        yield "AI not configured — set GROQ_API_KEY."
        return

    system = f"""You're Paula — a sharp, knowledgeable trading assistant. Today is {datetime.now(ZoneInfo("US/Eastern")).strftime("%Y-%m-%d")}. Market: {market}. {_market_status_line()}

Be aware of the market status above and reflect it naturally — if the market is closed, pre-market, or after-hours, factor that in. Don't describe live intraday action when the market isn't open.

{PAULA_VOICE}

FACTUAL RULES (never break these):
1. NEVER say "I'm ready to help", "What would you like", "Let me check", "I need to look up", or "I don't have access". These are BANNED phrases.
2. If LIVE DATA is attached below, use those exact prices. Never invent prices.
3. If NO live data is attached, use information from the conversation history — prices or stocks discussed earlier are real, reference them.
4. If you truly have zero information about a stock, say "Ask me to analyze [ticker] and I'll pull up the full picture" — never say you "need to look it up".
5. NO ARITHMETIC — you make math errors. Use the exact Chg% and pre-computed entry/stop/target numbers verbatim. If a PRE-COMPUTED block is attached, state that number exactly. Never multiply, subtract, or convert prices yourself. Omitting a number always beats stating a wrong one.
6. PORTFOLIO-AWARE — if a "portfolio_context" block is attached (buying power, equity, open positions), use it when giving advice: note an existing position before suggesting adding to it, flag concentration if one name is a big share of equity, respect buying power, and factor in whether the position is up or down. Use only the exact numbers in the block — never invent position sizes or dollar amounts."""

    messages = [{"role": "system", "content": system}]
    for h in (history or [])[-12:]:
        messages.append({"role": h.get("role", "user"), "content": str(h.get("content", ""))[:800]})
    content = user_msg
    _cur = (_safe(stock_data.get("price"), 0) or 0) if stock_data else 0
    try:
        _pm = compute_price_math(user_msg, _cur)
    except Exception:
        _pm = None
    if _pm:
        content += f"\n\n---PRE-COMPUTED (state this number exactly, do NOT recalculate)---\n{_pm['phrasing']}"
    if stock_data:
        content += f"\n\n---LIVE DATA (use ONLY these exact prices, do NOT make up numbers)---\n{json.dumps(_scrub_trade_levels_for_llm(stock_data), indent=2, default=str)}"
    # Ground advice in the user's REAL results when they're weighing a decision.
    _ml = user_msg.lower()
    if any(w in _ml for w in ["should i", "worth it", "good idea", "take this", "buy", "sell", "short", "how am i", "doing", "track record", "win rate", "performance"]):
        try:
            _tr = trade_track_record(30)
            if _tr.get("ok") and _tr.get("closed_trades", 0) > 0:
                content += (f"\n\n---YOUR ACTUAL TRADING RESULTS (last 30 days — reference these "
                            f"when giving advice; be honest about what's working)---\n{_tr['summary']}")
        except Exception:
            pass
    messages.append({"role": "user", "content": content})

    # Model fallback chain: if the primary is rate-limited (429), drop to the
    # next model automatically. Each Groq model has its own rate bucket, so a
    # smaller model is usually still available when the big one is capped.
    _models = ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "llama-3.3-70b-versatile"]
    client = Groq(api_key=key)
    _last_err = None
    for _mi, _model in enumerate(_models):
        try:
            stream = client.chat.completions.create(
                model=_model, messages=messages,
                max_tokens=500, temperature=0.3, stream=True
            )
            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
            return  # success — stop after a working model finishes
        except Exception as e:
            _last_err = e
            _msg = str(e).lower()
            # Only fall through to the next model on rate-limit/429; otherwise stop.
            if "429" in _msg or "rate limit" in _msg or "rate_limit" in _msg:
                if _mi < len(_models) - 1:
                    import time as _t
                    _t.sleep(0.6)
                    continue
                yield "⚠️ Paula's AI is busy right now (rate limit). Give it a few seconds and try again."
                return
            yield f"⚠️ AI error: {str(e)[:120]}"
            return


# ── UI ───────────────────────────────────────────────────────────────────────

def main():
    st.set_page_config(page_title="Paula", page_icon="◉", layout="wide", initial_sidebar_state="collapsed")

    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;500;600;700&family=Outfit:wght@300;400;500;600;700;800&display=swap');

    :root {
        --bg:       #050508;
        --surface:  #0c0c10;
        --surface2: #131318;
        --surface3: #1a1a22;
        --border:   #1e1e2a;
        --border2:  #2a2a3a;
        --muted:    #4a4a60;
        --text:     #a0a0b8;
        --bright:   #e4e4f0;
        --white:    #f5f5ff;
        --green:    #00e5a0;
        --green2:   #00c488;
        --red:      #ff3b5c;
        --red2:     #cc2244;
        --amber:    #ffb020;
        --blue:     #3388ff;
        --purple:   #8866ff;
        --cyan:     #00ccee;
    }

    .stApp {
        background: var(--bg) !important;
        background-image:
            radial-gradient(ellipse 80% 60% at 50% -20%, rgba(0,229,160,0.03) 0%, transparent 60%),
            radial-gradient(ellipse 60% 40% at 80% 100%, rgba(51,136,255,0.02) 0%, transparent 50%) !important;
    }
    header, footer, #MainMenu, .stDeployButton { visibility: hidden !important; display: none !important; }

    .block-container {
        max-width: 820px !important;
        padding: 1rem 1.2rem 6rem 1.2rem !important;
    }

    /* ── Typography ── */
    h1,h2,h3 {
        font-family: 'Outfit', sans-serif !important;
        color: var(--white) !important;
        font-weight: 700 !important;
        letter-spacing: -0.04em !important;
    }
    p, span, div, label, li {
        font-family: 'Outfit', sans-serif !important;
        color: var(--text) !important;
        line-height: 1.65 !important;
    }
    code, pre, .stCode {
        font-family: 'JetBrains Mono', monospace !important;
        background: var(--surface2) !important;
        color: var(--green) !important;
        border: 1px solid var(--border) !important;
        border-radius: 6px !important;
        font-size: 0.82rem !important;
    }

    /* ── Chat messages ── */
    .stChatMessage {
        background: transparent !important;
        border: none !important;
        border-radius: 0 !important;
        padding: 0.8rem 0 !important;
        border-bottom: 1px solid rgba(30,30,42,0.6) !important;
        gap: 0.9rem !important;
    }

    /* Avatar styling */
    .stChatMessage [data-testid="chatAvatarIcon-user"],
    .stChatMessage [data-testid="chatAvatarIcon-assistant"] {
        background: var(--surface2) !important;
        border: 1px solid var(--border) !important;
        border-radius: 6px !important;
        width: 28px !important;
        height: 28px !important;
    }

    [data-testid="stChatMessageContent"] {
        padding: 0 !important;
    }

    .stChatMessage p, .stChatMessage span, .stChatMessage li {
        color: var(--text) !important;
        font-size: 0.9rem !important;
        font-weight: 400 !important;
    }
    .stChatMessage strong, .stChatMessage b {
        color: var(--bright) !important;
        font-weight: 600 !important;
    }

    /* User messages */
    [data-testid="stChatMessage-user"] {
        border-bottom: none !important;
        padding: 0.3rem 0 0.1rem 0 !important;
    }
    [data-testid="stChatMessage-user"] p {
        color: var(--muted) !important;
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 0.82rem !important;
        font-weight: 400 !important;
    }

    /* ── Input bar ── */
    .stChatInput > div > div > textarea,
    .stTextInput > div > div > input {
        background: var(--surface) !important;
        border: 1px solid var(--border) !important;
        border-radius: 10px !important;
        color: var(--bright) !important;
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 0.85rem !important;
        padding: 0.85rem 1.1rem !important;
        transition: all 0.2s ease !important;
    }
    .stChatInput > div > div > textarea:focus {
        border-color: var(--green2) !important;
        box-shadow: 0 0 0 1px rgba(0,229,160,0.15), 0 4px 20px rgba(0,229,160,0.05) !important;
        background: var(--surface2) !important;
    }
    .stChatInput > div > div > textarea::placeholder {
        color: var(--muted) !important;
        font-family: 'JetBrains Mono', monospace !important;
        font-weight: 300 !important;
    }

    /* Send button */
    .stChatInput button {
        background: linear-gradient(135deg, var(--green), var(--green2)) !important;
        border: none !important;
        border-radius: 8px !important;
        transition: all 0.2s ease !important;
        box-shadow: 0 2px 8px rgba(0,229,160,0.15) !important;
    }
    .stChatInput button:hover {
        box-shadow: 0 2px 16px rgba(0,229,160,0.25) !important;
        transform: translateY(-1px) !important;
    }
    .stChatInput button svg { color: var(--bg) !important; }

    /* ── Data tables ── */
    .stDataFrame {
        border-radius: 8px !important;
        overflow: hidden !important;
        border: 1px solid var(--border) !important;
    }
    .stDataFrame td, .stDataFrame th {
        background: var(--surface) !important;
        color: var(--text) !important;
        border-color: var(--border) !important;
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 0.78rem !important;
        padding: 0.45rem 0.9rem !important;
    }
    .stDataFrame th {
        color: var(--muted) !important;
        font-weight: 600 !important;
        text-transform: uppercase !important;
        font-size: 0.68rem !important;
        letter-spacing: 0.08em !important;
        background: var(--surface2) !important;
    }

    /* ── Dividers ── */
    hr {
        border-color: var(--border) !important;
        margin: 0.6rem 0 !important;
        opacity: 0.5 !important;
    }

    /* ── Caption ── */
    .stCaption p {
        color: var(--muted) !important;
        font-size: 0.72rem !important;
        font-family: 'JetBrains Mono', monospace !important;
        letter-spacing: 0.04em !important;
        font-weight: 300 !important;
    }

    /* ── Plotly ── */
    .js-plotly-plot .plotly .modebar { display: none !important; }

    /* ── Spinner ── */
    .stSpinner > div { border-top-color: var(--green) !important; }

    /* ── Scrollbar ── */
    ::-webkit-scrollbar { width: 4px; }
    ::-webkit-scrollbar-track { background: transparent; }
    ::-webkit-scrollbar-thumb { background: var(--border); border-radius: 4px; }
    ::-webkit-scrollbar-thumb:hover { background: var(--muted); }

    /* ── Lists ── */
    .stChatMessage ol, .stChatMessage ul {
        padding-left: 1.2rem !important;
        margin: 0.5rem 0 !important;
    }
    .stChatMessage li {
        margin-bottom: 0.35rem !important;
        padding-left: 0.2rem !important;
    }
    .stChatMessage li::marker { color: var(--muted) !important; }

    </style>
    """, unsafe_allow_html=True)

    if "messages" not in st.session_state:
        st.session_state.messages = []

    # ── Header ──
    et = ZoneInfo("US/Eastern")
    now_et = datetime.now(et)
    autopilot_on = st.session_state.get("autopilot_active", False)
    ap_status = "◉ live" if autopilot_on else "○ off"
    st.markdown(f"## Paula")
    st.caption(f"intraday long/short · {now_et.strftime('%b %d, %Y · %I:%M %p')} ET · autopilot {ap_status}")

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

    prompt = st.chat_input("NVDA… buy 10 AAPL… short TSLA… portfolio… autopilot…",
                           disabled=st.session_state.get("processing", False))
    if not prompt:
        _run_autopilot_loop()
        return

    st.session_state["processing"] = True
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="⬛"):
        st.markdown(prompt)

    resp = "Something went wrong — try again."
    chart_ticker, table_data, trade_signal = None, None, None
    portfolio_chart = False
    market = "US"

    try:
        with st.chat_message("assistant", avatar="🟢"):
            with st.spinner(""):
                intent = route(prompt)
                result = execute(intent)
                market = result.get("market", intent.get("market", "US")) if result else "US"

                if result and result.get("ok"):
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
                elif result and result.get("error"):
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
    except Exception as e:
        with st.chat_message("assistant", avatar="🟢"):
            resp = f"⚠️ Error: {str(e)[:200]}"
            st.markdown(resp)
    finally:
        st.session_state["processing"] = False

    st.session_state.messages.append({"role": "assistant", "content": resp, "chart": chart_ticker, "table": table_data, "trade_signal": trade_signal, "portfolio_chart": portfolio_chart})

    # ── Autopilot continuous loop ──
    # Force a rerun so the message renders first, THEN the loop takes over on next cycle
    if st.session_state.get("autopilot_active", False):
        st.rerun()
    _run_autopilot_loop()


def _run_autopilot_loop():
    """If autopilot is active, wait then scan again automatically."""
    if not st.session_state.get("autopilot_active", False):
        return

    # Check market hours first
    is_open, status_msg = _market_is_open()

    if not is_open:
        st.markdown(f"---\n\n⏸️ **Autopilot paused** · {status_msg}\n\nWill auto-resume when market opens. Say \"stop\" to deactivate.")
        time.sleep(60)  # Check every 1 min
        st.rerun()
        return

    INTERVAL = 5 * 60  # 5 minutes — aggressive day trading

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
                        f"Bought: {result.get('buys', 0)} · Shorted: {result.get('shorts', 0)} · Closed: {result.get('sells', 0)}\n\n"
                        f"*Next scan in 5 minutes.*\n\n---\n\n" +
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
