"""
Paula — Stock Analysis Terminal
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
import os, json, re, warnings

warnings.filterwarnings("ignore")
load_dotenv()

# ─── Market Universes ────────────────────────────────────────────────────────

MARKETS = {
    "US": {
        "suffix": "",
        "currency": "$",
        "flag": "🇺🇸",
        "stocks": [
            "AAPL", "MSFT", "AMZN", "NVDA", "GOOGL", "META", "TSLA", "AVGO",
            "COST", "NFLX", "AMD", "ADBE", "PEP", "CSCO", "TMUS", "INTC",
            "CMCSA", "INTU", "QCOM", "TXN", "AMGN", "HON", "AMAT", "ISRG",
            "BKNG", "SBUX", "VRTX", "LRCX", "MU", "ADI", "REGN", "ADP",
            "PANW", "KLAC", "SNPS", "CDNS", "CRWD", "ASML", "PYPL", "MAR",
            "ORLY", "CTAS", "MRVL", "ABNB", "NXPI", "PCAR", "WDAY", "CPRT",
            "JPM", "V", "MA", "BAC", "WMT", "UNH", "JNJ", "PG", "HD", "MRK",
            "LLY", "ABBV", "CVX", "XOM", "CRM", "BRK-B", "KO", "MCD", "DIS",
            "BA", "NKE", "ORCL", "UBER", "SHOP", "SPOT",
            # Trending / meme
            "PLTR", "SMCI", "ARM", "IONQ", "RGTI", "MSTR", "COIN", "HOOD",
            "SOFI", "RKLB", "RIVN", "LCID", "NIO", "GME", "AMC", "DKNG",
            "SNOW", "NET", "OKTA",
        ],
    },
    "India": {
        "suffix": ".NS",
        "currency": "₹",
        "flag": "🇮🇳",
        "stocks": [
            "RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK", "HINDUNILVR",
            "BHARTIARTL", "SBIN", "BAJFINANCE", "ITC", "KOTAKBANK", "LT",
            "HCLTECH", "AXISBANK", "ASIANPAINT", "MARUTI", "SUNPHARMA",
            "TITAN", "WIPRO", "NTPC", "TATAMOTORS", "TATASTEEL", "ADANIENT",
            "BAJAJFINSV", "NESTLEIND", "ONGC", "POWERGRID", "M&M",
            "JSWSTEEL", "ULTRACEMCO",
        ],
    },
    "UK": {
        "suffix": ".L",
        "currency": "£",
        "flag": "🇬🇧",
        "stocks": [
            "SHEL", "AZN", "HSBA", "ULVR", "BP", "RIO", "GSK", "DGE",
            "BATS", "LSEG", "REL", "NG", "VOD", "BARC", "LLOY", "GLEN",
        ],
    },
    "Europe": {
        "suffix": "",  # mixed exchanges
        "currency": "€",
        "flag": "🇪🇺",
        "stocks": [
            "ASML", "MC.PA", "SAP.DE", "SIE.DE", "OR.PA", "TTE.PA",
            "ALV.DE", "AI.PA", "SAN.PA", "BNP.PA", "ENEL.MI", "IBE.MC",
        ],
    },
    "Japan": {
        "suffix": ".T",
        "currency": "¥",
        "flag": "🇯🇵",
        "stocks": [
            "7203", "6758", "9984", "8306", "6861", "6902", "7267",
            "9432", "4063", "6501",
        ],
    },
    "Crypto": {
        "suffix": "-USD",
        "currency": "$",
        "flag": "₿",
        "stocks": [
            "BTC", "ETH", "SOL", "BNB", "XRP", "ADA", "DOGE", "AVAX",
            "DOT", "MATIC", "LINK", "UNI",
        ],
    },
}

# ─── Company Name → Ticker Map ───────────────────────────────────────────────

COMPANY_NAMES = {
    # US
    "apple": ("AAPL", "US"), "microsoft": ("MSFT", "US"), "amazon": ("AMZN", "US"),
    "google": ("GOOGL", "US"), "alphabet": ("GOOGL", "US"), "meta": ("META", "US"),
    "facebook": ("META", "US"), "tesla": ("TSLA", "US"), "nvidia": ("NVDA", "US"),
    "netflix": ("NFLX", "US"), "amd": ("AMD", "US"), "intel": ("INTC", "US"),
    "adobe": ("ADBE", "US"), "salesforce": ("CRM", "US"), "oracle": ("ORCL", "US"),
    "paypal": ("PYPL", "US"), "shopify": ("SHOP", "US"), "spotify": ("SPOT", "US"),
    "uber": ("UBER", "US"), "airbnb": ("ABNB", "US"), "disney": ("DIS", "US"),
    "nike": ("NKE", "US"), "starbucks": ("SBUX", "US"), "mcdonalds": ("MCD", "US"),
    "walmart": ("WMT", "US"), "costco": ("COST", "US"), "boeing": ("BA", "US"),
    "coca cola": ("KO", "US"), "pepsi": ("PEP", "US"), "pfizer": ("PFE", "US"),
    "moderna": ("MRNA", "US"), "palantir": ("PLTR", "US"), "crowdstrike": ("CRWD", "US"),
    "snowflake": ("SNOW", "US"), "coinbase": ("COIN", "US"), "robinhood": ("HOOD", "US"),
    "sofi": ("SOFI", "US"), "gamestop": ("GME", "US"), "broadcom": ("AVGO", "US"),
    "eli lilly": ("LLY", "US"), "lilly": ("LLY", "US"), "jpmorgan": ("JPM", "US"),
    "jp morgan": ("JPM", "US"), "visa": ("V", "US"), "mastercard": ("MA", "US"),
    # India
    "reliance": ("RELIANCE", "India"), "tcs": ("TCS", "India"),
    "infosys": ("INFY", "India"), "hdfc": ("HDFCBANK", "India"),
    "icici": ("ICICIBANK", "India"), "sbi": ("SBIN", "India"),
    "wipro": ("WIPRO", "India"), "tata motors": ("TATAMOTORS", "India"),
    "itc": ("ITC", "India"), "kotak": ("KOTAKBANK", "India"),
    "airtel": ("BHARTIARTL", "India"), "bharti": ("BHARTIARTL", "India"),
    "titan": ("TITAN", "India"), "maruti": ("MARUTI", "India"),
    # UK
    "shell": ("SHEL", "UK"), "astrazeneca": ("AZN", "UK"), "hsbc": ("HSBA", "UK"),
    "unilever": ("ULVR", "UK"), "bp": ("BP", "UK"), "vodafone": ("VOD", "UK"),
    "barclays": ("BARC", "UK"), "lloyds": ("LLOY", "UK"),
    # Crypto
    "bitcoin": ("BTC", "Crypto"), "btc": ("BTC", "Crypto"),
    "ethereum": ("ETH", "Crypto"), "eth": ("ETH", "Crypto"),
    "solana": ("SOL", "Crypto"), "sol": ("SOL", "Crypto"),
    "dogecoin": ("DOGE", "Crypto"), "doge": ("DOGE", "Crypto"),
    "ripple": ("XRP", "Crypto"), "xrp": ("XRP", "Crypto"),
    "cardano": ("ADA", "Crypto"), "ada": ("ADA", "Crypto"),
}

# Keywords for market auto-detection
MARKET_KEYWORDS = {
    "India": ["nifty", "sensex", "bse", "nse", "₹", "rupee", "indian market"],
    "UK": ["ftse", "lse", "london stock", "£", "pence", "uk market"],
    "Europe": ["dax", "cac", "stoxx", "euronext", "€", "european market"],
    "Japan": ["nikkei", "topix", "tse", "tokyo stock", "yen", "¥", "japanese market"],
    "Crypto": ["crypto", "bitcoin", "blockchain", "defi", "web3", "altcoin", "token"],
    "US": ["nasdaq", "s&p", "sp500", "dow", "nyse", "$", "wall street", "us market"],
}

# Words that look like tickers but aren't
TICKER_BLACKLIST = {
    "THE", "AND", "FOR", "ARE", "BUT", "NOT", "YOU", "ALL", "CAN", "BUY",
    "SELL", "WHAT", "WHICH", "STOCK", "PRICE", "MARKET", "TODAY", "SHOULD",
    "WOULD", "COULD", "ABOUT", "THEIR", "WILL", "WITH", "THIS", "THAT",
    "FROM", "HAVE", "BEEN", "MORE", "ANALYZE", "TELL", "SHOW", "GIVE",
    "FIND", "BEST", "GOOD", "HIGH", "LOW", "MONEY", "WHEN", "WHERE",
    "SOME", "INTO", "TIME", "VERY", "JUST", "KNOW", "TAKE", "COME",
    "MAKE", "LIKE", "BACK", "ONLY", "OVER", "SUCH", "MOST", "NEED",
    "HELP", "THANK", "HOW", "WHY", "WHO", "HAS", "GET", "OUR", "NEW",
    "TOP", "HOT", "UP", "DO", "SO", "IF", "IT", "IS", "MY", "ME", "BE",
    "AT", "TO", "IN", "OF", "ON", "OR", "AN", "AS", "BY", "GO", "NO",
    "VS", "RUN", "SET", "TRY", "SAY", "SEE", "NOW", "WAY", "MAY", "DAY",
    "TOO", "ANY", "FEW", "GOT", "HER", "HIM", "HIS", "OLD", "PUT",
    "OWN", "SAY", "SHE", "USE", "HER", "BOT", "ASK", "API",
    # Common words that slip through
    "ABOVE", "BELOW", "AFTER", "BEFORE", "ALSO", "THAN", "THEN", "THEM",
    "THESE", "THOSE", "BEING", "DOES", "DONE", "DOWN", "EACH", "EVEN",
    "EVER", "EVERY", "FIRST", "GAVE", "GOES", "GONE", "GREAT", "HAD",
    "HERE", "HOLD", "KEEP", "LAST", "LEFT", "LONG", "LOOK", "MADE",
    "MANY", "MUCH", "MUST", "NAME", "NEAR", "NEXT", "ONCE", "OPEN",
    "PART", "PLAN", "PLAY", "REAL", "SAME", "SAID", "SHOW", "SIDE",
    "SURE", "TELL", "TEND", "TOLD", "TURN", "UPON", "USED", "WANT",
    "WELL", "WENT", "WERE", "WHAT", "WORK", "YEAR", "YOUR", "ZERO",
    "CALL", "CAME", "CASE", "CHAT", "DEAL", "DROP", "ELSE", "FALL",
    "FEEL", "FULL", "GAVE", "GROW", "HALF", "HAND", "HARD", "HEAD",
    "HEAR", "IDEA", "JUMP", "KIND", "LATE", "LEAD", "LESS", "LINE",
    "LIST", "LIVE", "LOSE", "LOST", "MAIN", "MEAN", "MIND", "MISS",
    "MOVE", "NOTE", "OKAY", "PASS", "PAST", "PICK", "PULL", "PUSH",
    "RATE", "READ", "REST", "RISE", "RISK", "ROLE", "RULE", "SAFE",
    "SAVE", "SEEM", "SELL", "SEND", "SHUT", "SIGN", "SORT", "STAR",
    "STAY", "STEP", "STOP", "TALK", "TEAM", "TEST", "THINK", "TRADE",
    "TRUE", "TYPE", "WAIT", "WALK", "WEAK", "WEEK", "WHAT", "WIDE",
    "WINS", "WISE", "WORD", "YEAH", "LOOKS", "THINK", "GOING", "STILL",
    "THING", "THERE", "WHERE", "WHILE", "MIGHT", "COULD", "NEVER",
    "MAYBE", "QUITE", "RIGHT", "SINCE", "SMALL", "START", "THREE",
    "WATCH", "WHOLE", "WORLD", "WORSE", "WORTH", "WRONG", "WROTE",
}


# ─── Data Layer ──────────────────────────────────────────────────────────────

def _resolve_ticker(raw_ticker: str, market: str) -> str:
    """Add the correct exchange suffix to a raw ticker."""
    if "." in raw_ticker or "-USD" in raw_ticker:
        return raw_ticker  # already qualified
    cfg = MARKETS.get(market, MARKETS["US"])
    suffix = cfg["suffix"]
    if suffix and not raw_ticker.endswith(suffix):
        return raw_ticker + suffix
    return raw_ticker


def fetch_price(ticker: str) -> dict | None:
    """Fetch current price data for a single ticker."""
    try:
        stock = yf.Ticker(ticker)

        # Try fast_info first (yfinance 0.2+)
        try:
            fi = stock.fast_info
            price = fi.get("lastPrice") or fi.get("last_price")
            prev = fi.get("previousClose") or fi.get("previous_close")
            if price and price > 0:
                prev = prev or price
                info = {}
                try:
                    info = stock.info or {}
                except Exception:
                    pass
                return _build_price_dict(price, prev, ticker, info)
        except Exception:
            pass

        # Fallback: info dict
        try:
            info = stock.info
            if info:
                price = info.get("currentPrice") or info.get("regularMarketPrice")
                prev = info.get("previousClose") or info.get("regularMarketPreviousClose")
                if price and price > 0:
                    prev = prev or price
                    return _build_price_dict(price, prev, ticker, info)
        except Exception:
            pass

        # Fallback: history
        try:
            hist = stock.history(period="5d")
            if hist is not None and not hist.empty:
                price = float(hist["Close"].iloc[-1])
                prev = float(hist["Close"].iloc[-2]) if len(hist) >= 2 else price
                if price > 0:
                    info = {}
                    try:
                        info = stock.info or {}
                    except Exception:
                        pass
                    return _build_price_dict(price, prev, ticker, info)
        except Exception:
            pass

        return None
    except Exception:
        return None


def _build_price_dict(price, prev, ticker, info):
    change = price - prev
    change_pct = (change / prev * 100) if prev > 0 else 0.0
    return {
        "price": round(price, 2),
        "prev_close": round(prev, 2),
        "change": round(change, 2),
        "change_pct": round(change_pct, 2),
        "name": info.get("shortName") or info.get("longName") or ticker.split(".")[0],
        "market_cap": info.get("marketCap"),
        "pe_ratio": info.get("trailingPE"),
        "forward_pe": info.get("forwardPE"),
        "52w_high": info.get("fiftyTwoWeekHigh"),
        "52w_low": info.get("fiftyTwoWeekLow"),
        "sector": info.get("sector"),
        "industry": info.get("industry"),
        "target_price": info.get("targetMeanPrice"),
        "target_high": info.get("targetHighPrice"),
        "target_low": info.get("targetLowPrice"),
        "recommendation": info.get("recommendationKey"),
        "num_analysts": info.get("numberOfAnalystOpinions"),
        "dividend_yield": info.get("dividendYield"),
        "beta": info.get("beta"),
        "peg_ratio": info.get("pegRatio"),
        "roe": info.get("returnOnEquity"),
        "profit_margin": info.get("profitMargins"),
        "revenue_growth": info.get("revenueGrowth"),
        "debt_to_equity": info.get("debtToEquity"),
    }


def fetch_full(ticker: str) -> dict | None:
    """Fetch comprehensive data: price + technicals + news."""
    basic = fetch_price(ticker)
    if not basic:
        return None

    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="6mo")

        tech = _compute_technicals(hist)
        news = _fetch_news(stock)

        return {
            **basic,
            "ticker": ticker.replace(".NS", "").replace(".L", "").replace(".T", "").replace("-USD", ""),
            "full_ticker": ticker,
            "technicals": tech,
            "news": news,
        }
    except Exception:
        basic["technicals"] = {}
        basic["news"] = []
        return basic


def _compute_technicals(hist) -> dict:
    if hist is None or hist.empty or len(hist) < 14:
        return {}

    c = hist["Close"]
    tech = {}

    # Moving averages
    if len(c) >= 20:
        tech["sma_20"] = round(float(c.rolling(20).mean().iloc[-1]), 2)
    if len(c) >= 50:
        tech["sma_50"] = round(float(c.rolling(50).mean().iloc[-1]), 2)
    if len(c) >= 100:
        tech["sma_100"] = round(float(c.rolling(100).mean().iloc[-1]), 2)

    # EMA 12, 26 for MACD
    if len(c) >= 26:
        ema12 = c.ewm(span=12, adjust=False).mean()
        ema26 = c.ewm(span=26, adjust=False).mean()
        macd_line = ema12 - ema26
        signal_line = macd_line.ewm(span=9, adjust=False).mean()
        tech["macd"] = round(float(macd_line.iloc[-1]), 4)
        tech["macd_signal"] = round(float(signal_line.iloc[-1]), 4)
        tech["macd_hist"] = round(float((macd_line - signal_line).iloc[-1]), 4)

    # RSI
    delta = c.diff()
    gain = delta.where(delta > 0, 0.0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0.0)).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi_series = 100 - (100 / (1 + rs))
    if not rsi_series.dropna().empty:
        tech["rsi"] = round(float(rsi_series.iloc[-1]), 1)

    # Bollinger Bands
    if len(c) >= 20:
        sma20 = c.rolling(20).mean()
        std20 = c.rolling(20).std()
        tech["bb_upper"] = round(float((sma20 + 2 * std20).iloc[-1]), 2)
        tech["bb_lower"] = round(float((sma20 - 2 * std20).iloc[-1]), 2)

    # ATR (14-day)
    if len(hist) >= 14 and all(col in hist.columns for col in ["High", "Low", "Close"]):
        h = hist["High"]
        l = hist["Low"]
        prev_c = c.shift(1)
        tr = pd.concat([h - l, (h - prev_c).abs(), (l - prev_c).abs()], axis=1).max(axis=1)
        tech["atr_14"] = round(float(tr.rolling(14).mean().iloc[-1]), 2)

    # Momentum
    if len(c) >= 5:
        tech["mom_5d"] = round(float((c.iloc[-1] / c.iloc[-5] - 1) * 100), 2)
    if len(c) >= 20:
        tech["mom_20d"] = round(float((c.iloc[-1] / c.iloc[-20] - 1) * 100), 2)
    if len(c) >= 60:
        tech["mom_60d"] = round(float((c.iloc[-1] / c.iloc[-60] - 1) * 100), 2)

    # Volume ratio
    if "Volume" in hist.columns and len(hist) >= 20:
        avg_vol = hist["Volume"].rolling(20).mean().iloc[-1]
        today_vol = hist["Volume"].iloc[-1]
        tech["vol_ratio"] = round(float(today_vol / avg_vol), 2) if avg_vol > 0 else 1.0

    # Volatility (20-day annualized)
    if len(c) >= 20:
        returns = c.pct_change().dropna()
        if len(returns) >= 20:
            tech["volatility_20d"] = round(float(returns.tail(20).std() * np.sqrt(252) * 100), 1)

    return tech


def _fetch_news(stock) -> list:
    news = []
    try:
        raw = stock.news or []
        for n in raw[:5]:
            title = n.get("title", "")
            publisher = n.get("publisher", "")
            if title:
                news.append({"title": title, "publisher": publisher})
    except Exception:
        pass
    return news


# ─── Scoring Engine ──────────────────────────────────────────────────────────

def compute_score(data: dict) -> dict:
    """
    Multi-factor scoring: technicals, fundamentals, sentiment.
    Returns score 0-100, rating, signals list, warnings list.
    """
    score = 50.0
    signals, warnings = [], []
    tech = data.get("technicals", {})
    price = data.get("price", 0)

    # ── Technical Factors ──

    rsi = tech.get("rsi")
    if rsi is not None:
        if rsi < 25:
            score += 12
            signals.append(f"RSI deeply oversold ({rsi:.0f}) — high probability bounce zone")
        elif rsi < 35:
            score += 7
            signals.append(f"RSI in buy zone ({rsi:.0f})")
        elif rsi > 75:
            score -= 12
            warnings.append(f"RSI overbought ({rsi:.0f}) — pullback risk elevated")
        elif rsi > 65:
            score -= 4
            warnings.append(f"RSI running warm ({rsi:.0f})")

    # Trend: price vs SMAs
    sma20 = tech.get("sma_20")
    sma50 = tech.get("sma_50")
    sma100 = tech.get("sma_100")

    above_count = 0
    if sma20 and price > sma20:
        above_count += 1
    if sma50 and price > sma50:
        above_count += 1
    if sma100 and price > sma100:
        above_count += 1

    if above_count == 3:
        score += 8
        signals.append("Price above all key SMAs — strong uptrend")
    elif above_count >= 2:
        score += 4
        signals.append("Price above major moving averages — uptrend intact")
    elif above_count == 0 and sma20:
        score -= 6
        warnings.append("Price below all key SMAs — downtrend")

    # Golden / death cross
    if sma20 and sma50:
        if sma20 > sma50:
            score += 3
            signals.append("20 SMA > 50 SMA — bullish alignment")
        elif sma20 < sma50 * 0.98:
            score -= 3
            warnings.append("20 SMA < 50 SMA — bearish alignment")

    # MACD
    macd_hist = tech.get("macd_hist")
    if macd_hist is not None:
        if macd_hist > 0:
            score += 3
            signals.append("MACD histogram positive — bullish momentum")
        else:
            score -= 2
            warnings.append("MACD histogram negative — momentum fading")

    # Momentum
    mom5 = tech.get("mom_5d")
    mom20 = tech.get("mom_20d")
    if mom5 is not None:
        if mom5 > 5:
            score += 6
            signals.append(f"5-day momentum +{mom5:.1f}%")
        elif mom5 < -5:
            score -= 6
            warnings.append(f"5-day momentum {mom5:.1f}%")

    if mom20 is not None:
        if mom20 > 10:
            score += 4
            signals.append(f"20-day momentum +{mom20:.1f}%")
        elif mom20 < -10:
            score -= 4
            warnings.append(f"20-day momentum {mom20:.1f}%")

    # Volume conviction
    vol = tech.get("vol_ratio")
    if vol is not None:
        if vol > 2.0:
            score += 5
            signals.append(f"Volume {vol:.1f}× average — high conviction")
        elif vol > 1.3:
            score += 2
        elif vol < 0.5:
            warnings.append("Volume well below average — low conviction")

    # Bollinger position
    bb_upper = tech.get("bb_upper")
    bb_lower = tech.get("bb_lower")
    if bb_upper and bb_lower and price:
        bb_range = bb_upper - bb_lower
        if bb_range > 0:
            bb_pos = (price - bb_lower) / bb_range
            if bb_pos < 0.1:
                score += 5
                signals.append("Near lower Bollinger Band — potential reversion")
            elif bb_pos > 0.95:
                score -= 3
                warnings.append("At upper Bollinger Band — extended")

    # ── Fundamental Factors ──

    pe = data.get("pe_ratio")
    fwd_pe = data.get("forward_pe")
    if pe and fwd_pe and pe > 0 and fwd_pe > 0:
        compression = (fwd_pe - pe) / pe * 100
        if compression < -15:
            score += 5
            signals.append(f"Forward P/E ({fwd_pe:.1f}) well below trailing ({pe:.1f}) — strong earnings growth expected")
        elif compression < -5:
            score += 2
            signals.append(f"Forward P/E ({fwd_pe:.1f}) < trailing ({pe:.1f}) — earnings improving")
        elif compression > 15:
            score -= 3
            warnings.append(f"Forward P/E ({fwd_pe:.1f}) > trailing ({pe:.1f}) — earnings expected to decline")

    peg = data.get("peg_ratio")
    if peg is not None and peg > 0:
        if peg < 1.0:
            score += 4
            signals.append(f"PEG ratio {peg:.2f} — undervalued relative to growth")
        elif peg > 2.5:
            score -= 2
            warnings.append(f"PEG ratio {peg:.2f} — expensive vs growth")

    roe = data.get("roe")
    if roe is not None:
        if roe > 0.25:
            score += 3
            signals.append(f"ROE {roe*100:.0f}% — excellent capital efficiency")
        elif roe < 0:
            score -= 3
            warnings.append("Negative ROE")

    rev_growth = data.get("revenue_growth")
    if rev_growth is not None:
        if rev_growth > 0.2:
            score += 4
            signals.append(f"Revenue growing {rev_growth*100:.0f}% YoY")
        elif rev_growth < -0.05:
            score -= 3
            warnings.append(f"Revenue declining {rev_growth*100:.0f}% YoY")

    dte = data.get("debt_to_equity")
    if dte is not None:
        if dte > 200:
            score -= 4
            warnings.append(f"High debt-to-equity ({dte:.0f})")
        elif dte < 30:
            score += 2
            signals.append("Low leverage — clean balance sheet")

    # ── Analyst Sentiment ──

    rec = data.get("recommendation")
    if rec:
        rec_lower = rec.lower().replace("_", "")
        if rec_lower in ("strongbuy",):
            score += 8
            signals.append("Analyst consensus: Strong Buy")
        elif rec_lower in ("buy",):
            score += 4
            signals.append("Analyst consensus: Buy")
        elif rec_lower in ("sell", "strongsell"):
            score -= 8
            warnings.append(f"Analyst consensus: {rec.replace('_', ' ').title()}")

    target = data.get("target_price")
    if target and price and price > 0:
        upside = (target - price) / price * 100
        if upside > 25:
            score += 7
            signals.append(f"Analyst target ${target:.2f} → {upside:.0f}% upside")
        elif upside > 10:
            score += 3
            signals.append(f"Analyst target ${target:.2f} → {upside:.0f}% upside")
        elif upside < -10:
            score -= 4
            warnings.append(f"Trading {abs(upside):.0f}% above analyst target")

    # 52-week range position
    high_52 = data.get("52w_high")
    low_52 = data.get("52w_low")
    if high_52 and low_52 and price and (high_52 - low_52) > 0:
        range_pct = (price - low_52) / (high_52 - low_52) * 100
        if range_pct < 15:
            score += 4
            signals.append("Near 52-week low — potential value entry")
        elif range_pct > 95:
            warnings.append("At 52-week high — may be extended")

    # Clamp
    score = max(0, min(100, score))

    # Rating
    if score >= 72:
        rating = "STRONG BUY"
    elif score >= 58:
        rating = "BUY"
    elif score >= 42:
        rating = "HOLD"
    elif score >= 28:
        rating = "WEAK"
    else:
        rating = "AVOID"

    return {
        "score": round(score),
        "rating": rating,
        "signals": signals,
        "warnings": warnings,
    }


# ─── Chart Builder ───────────────────────────────────────────────────────────

def build_chart(ticker: str, period: str = "3mo") -> go.Figure | None:
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period=period)

        if hist is None or hist.empty or len(hist) < 5:
            hist = stock.history(period="1mo")
            if hist is None or hist.empty:
                return None

        fig = make_subplots(
            rows=2, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.04,
            row_heights=[0.75, 0.25],
        )

        # Candlestick
        fig.add_trace(
            go.Candlestick(
                x=hist.index,
                open=hist["Open"], high=hist["High"],
                low=hist["Low"], close=hist["Close"],
                name="Price",
                increasing_line_color="#16a34a",
                decreasing_line_color="#dc2626",
                increasing_fillcolor="#16a34a",
                decreasing_fillcolor="#dc2626",
            ),
            row=1, col=1,
        )

        # SMAs
        if len(hist) >= 20:
            sma20 = hist["Close"].rolling(20).mean()
            fig.add_trace(
                go.Scatter(x=hist.index, y=sma20, name="SMA 20",
                           line=dict(color="#60a5fa", width=1.2, dash="dot")),
                row=1, col=1,
            )
        if len(hist) >= 50:
            sma50 = hist["Close"].rolling(50).mean()
            fig.add_trace(
                go.Scatter(x=hist.index, y=sma50, name="SMA 50",
                           line=dict(color="#fbbf24", width=1.2, dash="dot")),
                row=1, col=1,
            )

        # Volume
        colors = [
            "#16a34a" if c >= o else "#dc2626"
            for c, o in zip(hist["Close"], hist["Open"])
        ]
        fig.add_trace(
            go.Bar(x=hist.index, y=hist["Volume"], marker_color=colors,
                   opacity=0.4, name="Volume", showlegend=False),
            row=2, col=1,
        )

        fig.update_layout(
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(family="JetBrains Mono, monospace", color="#71717a", size=11),
            showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
                        font=dict(size=10)),
            height=400,
            margin=dict(l=0, r=0, t=20, b=0),
            xaxis_rangeslider_visible=False,
        )
        fig.update_xaxes(showgrid=False, zeroline=False)
        fig.update_yaxes(showgrid=True, gridcolor="rgba(63,63,70,0.3)", zeroline=False)

        return fig
    except Exception:
        return None


# ─── Intent Detection ────────────────────────────────────────────────────────

def detect_market(msg: str) -> str | None:
    """Return a market key if the message clearly references one, else None."""
    low = msg.lower()
    scores = {}
    for market, keywords in MARKET_KEYWORDS.items():
        scores[market] = sum(1 for k in keywords if k in low)
    best = max(scores, key=scores.get)
    if scores[best] > 0:
        return best
    return None


def find_ticker(msg: str, market: str = "US") -> tuple[str | None, str]:
    """Extract a ticker and its market from a user message."""
    low = msg.lower()

    # 1. Check company name map
    for name, (tick, mkt) in COMPANY_NAMES.items():
        if name in low:
            return tick, mkt

    # 2. Check all market stock lists for exact word matches
    all_market_tickers = {}
    for mkt, cfg in MARKETS.items():
        for s in cfg["stocks"]:
            raw = s.replace(cfg["suffix"], "") if cfg["suffix"] else s
            all_market_tickers[raw.upper()] = mkt

    for word in msg.upper().split():
        clean = re.sub(r"[^A-Z0-9&\-]", "", word)
        if clean and len(clean) >= 1 and clean not in TICKER_BLACKLIST:
            if clean in all_market_tickers:
                return clean, all_market_tickers[clean]

    # 3. Only treat it as a ticker if it's ALL CAPS in the original message
    #    (user intentionally typed "PLTR" not "pltr" in a sentence)
    for word in msg.split():
        clean = re.sub(r"[^A-Z0-9]", "", word)
        if (clean and 2 <= len(clean) <= 5
                and clean == word.strip("?.,!:;\"'()[]")
                and clean not in TICKER_BLACKLIST
                and clean.isupper()
                and not any(c.isdigit() for c in clean)):
            return clean, market

    return None, market


def classify_intent(msg: str, market: str = "US") -> dict:
    """Classify the user's message into an actionable intent."""
    low = msg.lower().strip()

    # Greetings / meta / conversational
    greetings = {"hi", "hello", "hey", "thanks", "thank you", "help", "bye",
                 "ok", "okay", "sure", "yes", "no", "yep", "nope", "cool",
                 "great", "awesome", "nice", "wow", "lol", "haha", "hmm",
                 "what can you do", "who are you", "what are you"}
    if low in greetings or low.rstrip("?!. ") in greetings:
        return {"type": "chat"}

    ticker, detected_market = find_ticker(msg, market)

    # Price query
    price_kw = ["price of", "what's the price", "what is the price", "how much is",
                 "current price", "quote for", "what is", "how is"]
    if any(k in low for k in price_kw) and ticker:
        return {"type": "price", "ticker": ticker, "market": detected_market}

    # Compare
    if any(k in low for k in ["compare", "vs", "versus", "against"]):
        # Try to find two tickers
        tickers_found = []
        for word in msg.upper().split():
            clean = re.sub(r"[^A-Z]", "", word)
            if clean and clean not in TICKER_BLACKLIST and len(clean) >= 2:
                tickers_found.append(clean)
        if len(tickers_found) >= 2:
            return {"type": "compare", "tickers": tickers_found[:2], "market": detected_market}

    # Analysis
    analysis_kw = ["analyze", "analysis", "should i buy", "should i sell", "verdict",
                   "recommendation", "what do you think", "outlook", "forecast",
                   "worth buying", "good buy", "deep dive", "bull case", "bear case"]
    if any(k in low for k in analysis_kw) and ticker:
        return {"type": "analyze", "ticker": ticker, "market": detected_market}

    # Screener: gainers / losers / movers
    if any(k in low for k in ["gainer", "gaining", "best stock", "top performer", "top stocks", "winners", "green"]):
        return {"type": "gainers"}
    if any(k in low for k in ["loser", "losing", "worst", "dropping", "falling", "down today", "red"]):
        return {"type": "losers"}
    if any(k in low for k in ["hot", "trending", "moving", "movers", "what's moving", "most active"]):
        return {"type": "hot"}

    # If a ticker was found AND the message is short / stock-focused, analyze
    if ticker:
        word_count = len(low.split())
        # Short messages with a ticker are almost certainly stock queries
        if word_count <= 6:
            return {"type": "analyze", "ticker": ticker, "market": detected_market}
        # Longer messages: only if they contain stock-related words
        stock_words = ["stock", "price", "buy", "sell", "hold", "trade", "invest",
                       "chart", "target", "earning", "valuation", "worth", "position"]
        if any(w in low for w in stock_words):
            return {"type": "analyze", "ticker": ticker, "market": detected_market}

    return {"type": "chat"}


# ─── Intent Execution ────────────────────────────────────────────────────────

def execute(intent: dict, market: str = "US") -> dict:
    """Execute an intent and return structured results."""
    itype = intent.get("type")
    market = intent.get("market", market)

    if itype == "price":
        ticker = _resolve_ticker(intent["ticker"], market)
        data = fetch_price(ticker)
        if data:
            cfg = MARKETS.get(market, MARKETS["US"])
            sym = cfg["currency"]
            arrow = "▲" if data["change_pct"] >= 0 else "▼"
            clr = "green" if data["change_pct"] >= 0 else "red"
            display = intent["ticker"]
            return {
                "ok": True, "type": "price", "market": market,
                "msg": f"**{display}** — {sym}{data['price']:,.2f}  {arrow} {data['change_pct']:+.2f}%",
                "data": data, "ticker": ticker,
            }
        return {"ok": False, "error": f"Couldn't fetch data for {intent['ticker']}"}

    if itype == "analyze":
        ticker = _resolve_ticker(intent["ticker"], market)
        data = fetch_full(ticker)
        if data:
            sc = compute_score(data)
            return {
                "ok": True, "type": "analysis", "market": market,
                "data": {**data, **sc}, "ticker": ticker,
            }
        return {"ok": False, "error": f"Couldn't fetch data for {intent['ticker']}"}

    if itype == "compare":
        results = {}
        for t in intent.get("tickers", []):
            ticker = _resolve_ticker(t, market)
            data = fetch_full(ticker)
            if data:
                sc = compute_score(data)
                results[t] = {**data, **sc}
        if results:
            return {"ok": True, "type": "compare", "market": market, "data": results}
        return {"ok": False, "error": "Couldn't fetch data for comparison"}

    if itype in ("gainers", "losers", "hot"):
        cfg = MARKETS.get(market, MARKETS["US"])
        stocks = cfg["stocks"]
        results = []
        for s in stocks[:30]:
            full = _resolve_ticker(s, market)
            d = fetch_price(full)
            if d:
                results.append({
                    "ticker": s.replace(".NS", "").replace(".L", "").replace(".T", "").replace("-USD", ""),
                    "price": d["price"],
                    "change_pct": d["change_pct"],
                })

        if itype == "gainers":
            results = sorted([r for r in results if r["change_pct"] > 0],
                             key=lambda x: x["change_pct"], reverse=True)[:10]
            title = "Top Gainers"
        elif itype == "losers":
            results = sorted([r for r in results if r["change_pct"] < 0],
                             key=lambda x: x["change_pct"])[:10]
            title = "Top Losers"
        else:
            results = sorted(results, key=lambda x: abs(x["change_pct"]), reverse=True)[:12]
            title = "Biggest Movers"

        return {"ok": True, "type": "list", "title": title, "data": results, "market": market}

    return {"ok": False, "type": "chat"}


# ─── AI Response ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are Paula, a sharp, experienced stock analyst. You speak like a real trader — direct, specific, no filler.

Today: {date} | Market focus: {market}

You always have real-time data injected into the conversation. USE IT — cite exact numbers.

When analyzing a stock:
1. Lead with the verdict (score + rating) and one-line thesis
2. Technical setup — RSI, MACD, SMA positioning, momentum, volume. Be specific.
3. Fundamentals — P/E, growth, margins, balance sheet. Only what matters.
4. Catalyst / risk — news, earnings, macro. What could move this?
5. Trade plan — entry zone, stop loss level, price targets (1-3 month). Be concrete.

Style rules:
- Numbers, not adjectives. "$142.50" not "the stock is doing well"
- Short paragraphs. No walls of text.
- Bold the rating and key numbers
- If the data shows mixed signals, say so — don't force a narrative
- Never claim you can't access data. You always have it.
- Don't hedge everything with disclaimers — you're an analyst, give a clear view
- For simple price queries, be brief: price + quick context
- For compare requests, structure side-by-side
"""


def get_ai_response(msg: str, data, history: list, market: str = "US") -> str:
    key = st.secrets.get("GROQ_API_KEY") or os.environ.get("GROQ_API_KEY")
    if not key:
        return "⚠️ Add `GROQ_API_KEY` to your Streamlit secrets or environment."

    try:
        client = Groq(api_key=key)

        system = SYSTEM_PROMPT.format(date=datetime.now().strftime("%Y-%m-%d"), market=market)
        messages = [{"role": "system", "content": system}]

        for h in history[-8:]:
            messages.append({"role": h["role"], "content": h["content"][:2000]})

        if data:
            content = f"{msg}\n\n---DATA---\n{json.dumps(data, indent=2, default=str)}"
        else:
            content = msg
        messages.append({"role": "user", "content": content})

        resp = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            max_tokens=1800,
            temperature=0.6,
        )
        return resp.choices[0].message.content
    except Exception as e:
        return f"Error: {str(e)[:120]}"


# ─── UI ──────────────────────────────────────────────────────────────────────

def inject_css():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&family=Instrument+Sans:wght@400;500;600;700&display=swap');

    :root {
        --bg: #0c0c0c;
        --surface: #141414;
        --border: #1e1e1e;
        --border-hover: #2a2a2a;
        --text-primary: #e8e8e8;
        --text-secondary: #737373;
        --text-muted: #525252;
        --accent: #22c55e;
        --accent-dim: #16a34a;
        --red: #ef4444;
        --mono: 'JetBrains Mono', monospace;
        --sans: 'Instrument Sans', -apple-system, sans-serif;
    }

    .stApp {
        background: var(--bg) !important;
    }

    header, footer, #MainMenu { visibility: hidden !important; }

    .block-container {
        max-width: 860px !important;
        padding: 2rem 1.5rem 5rem 1.5rem !important;
    }

    /* Typography — exclude material icon spans from font override */
    h1, h2, h3 {
        font-family: var(--sans) !important;
        color: var(--text-primary) !important;
        font-weight: 600 !important;
        letter-spacing: -0.02em !important;
    }
    p, label, li {
        font-family: var(--sans) !important;
        color: var(--text-secondary) !important;
    }
    div, span {
        color: var(--text-secondary) !important;
    }
    code, pre {
        font-family: var(--mono) !important;
    }
    strong, b, em, i {
        font-family: inherit !important;
    }

    /* Preserve Streamlit's icon font for avatars */
    [data-testid="stChatMessageAvatarCustom"],
    [data-testid="stChatMessageAvatarAssistant"],
    [data-testid="stChatMessageAvatarUser"],
    .stChatMessage [data-testid] > span {
        font-family: 'Material Symbols Rounded', 'Material Icons', sans-serif !important;
    }

    /* Chat messages */
    .stChatMessage {
        background: var(--surface) !important;
        border: 1px solid var(--border) !important;
        border-radius: 8px !important;
        padding: 1rem 1.2rem !important;
        margin-bottom: 0.5rem !important;
    }
    .stChatMessage p, .stChatMessage span, .stChatMessage li,
    .stChatMessage div, .stChatMessage strong, .stChatMessage b,
    .stChatMessage em, .stChatMessage i, .stChatMessage a,
    .stChatMessage code {
        color: var(--text-primary) !important;
        font-size: 0.92rem !important;
        line-height: 1.6 !important;
        font-family: var(--sans) !important;
    }
    .stChatMessage strong, .stChatMessage b {
        color: #fff !important;
        font-weight: 600 !important;
    }
    .stChatMessage em, .stChatMessage i {
        font-style: italic !important;
    }

    /* Input */
    .stChatInput > div > div > textarea,
    .stTextInput > div > div > input {
        background: var(--surface) !important;
        border: 1px solid var(--border) !important;
        border-radius: 8px !important;
        color: var(--text-primary) !important;
        font-family: var(--sans) !important;
        font-size: 0.92rem !important;
    }
    .stChatInput > div > div > textarea:focus,
    .stTextInput > div > div > input:focus {
        border-color: var(--border-hover) !important;
        box-shadow: none !important;
    }

    /* Buttons */
    .stButton > button {
        background: var(--surface) !important;
        color: var(--text-secondary) !important;
        border: 1px solid var(--border) !important;
        border-radius: 6px !important;
        font-family: var(--mono) !important;
        font-size: 0.78rem !important;
        letter-spacing: 0.03em !important;
        text-transform: uppercase !important;
        padding: 0.4rem 0.8rem !important;
        transition: all 0.15s ease !important;
    }
    .stButton > button:hover {
        background: var(--border) !important;
        color: var(--text-primary) !important;
        border-color: var(--border-hover) !important;
    }

    /* Dataframe */
    .stDataFrame {
        border-radius: 6px !important;
        overflow: hidden !important;
    }
    .stDataFrame td, .stDataFrame th {
        background: var(--surface) !important;
        color: var(--text-primary) !important;
        border-color: var(--border) !important;
        font-family: var(--mono) !important;
        font-size: 0.82rem !important;
    }

    /* Divider */
    hr {
        border-color: var(--border) !important;
        margin: 1.5rem 0 !important;
    }

    /* Caption */
    .stCaption, small {
        font-family: var(--mono) !important;
        font-size: 0.72rem !important;
        color: var(--text-muted) !important;
        letter-spacing: 0.02em !important;
    }

    /* Scrollbar */
    ::-webkit-scrollbar { width: 6px; }
    ::-webkit-scrollbar-track { background: var(--bg); }
    ::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }
    ::-webkit-scrollbar-thumb:hover { background: var(--border-hover); }

    /* Plotly */
    .js-plotly-plot { border-radius: 6px; overflow: hidden; }
    </style>
    """, unsafe_allow_html=True)


def main():
    st.set_page_config(
        page_title="Paula",
        page_icon="◆",
        layout="wide",
        initial_sidebar_state="collapsed",
    )

    inject_css()

    # State
    if "messages" not in st.session_state:
        st.session_state.messages = [
            {
                "role": "assistant",
                "content": "Hey — I'm Paula. Give me a ticker and I'll break it down for you. Technicals, fundamentals, trade plan, the works.\n\nTry something like **analyze NVDA**, **AAPL vs MSFT**, or **top gainers**.",
                "chart": None,
                "table": None,
            }
        ]
    if "market" not in st.session_state:
        st.session_state.market = "US"

    # Header
    st.markdown(f"### ◆ Paula")
    st.caption("ask about any stock, anywhere")

    st.markdown("---")

    # Render history
    for m in st.session_state.messages:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])
            if m["role"] == "assistant" and m.get("chart") :
                ch = build_chart(m["chart"])
                if ch:
                    st.plotly_chart(ch, use_container_width=True)
            if m["role"] == "assistant" and m.get("table"):
                st.dataframe(pd.DataFrame(m["table"]), use_container_width=True, hide_index=True)

    # Input
    prompt = st.chat_input("analyze NVDA · top gainers · AAPL vs MSFT ...")

    if prompt:
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner(""):
                # Auto-detect market
                detected = detect_market(prompt)
                if detected:
                    st.session_state.market = detected
                market = st.session_state.market

                # Process
                intent = classify_intent(prompt, market)
                res = execute(intent, market)

                if res.get("market"):
                    st.session_state.market = res["market"]
                    market = res["market"]

                chart_ticker = None
                table_data = None

                if res.get("ok"):
                    if res["type"] == "price":
                        chart_ticker = res["ticker"]
                        resp = get_ai_response(prompt, res["data"], st.session_state.messages, market)

                    elif res["type"] == "analysis":
                        chart_ticker = res["ticker"]
                        resp = get_ai_response(prompt, res["data"], st.session_state.messages, market)

                    elif res["type"] == "compare":
                        resp = get_ai_response(prompt, res["data"], st.session_state.messages, market)

                    elif res["type"] == "list":
                        cfg = MARKETS.get(market, MARKETS["US"])
                        sym = cfg["currency"]
                        table_data = []
                        for i in res["data"]:
                            arrow = "▲" if i["change_pct"] >= 0 else "▼"
                            table_data.append({
                                "Ticker": i["ticker"],
                                "Price": f"{sym}{i['price']:,.2f}",
                                "Change": f"{arrow} {i['change_pct']:+.2f}%",
                            })
                        resp = f"**{res['title']}** — {cfg['flag']} {market}"
                    else:
                        resp = get_ai_response(prompt, None, st.session_state.messages, market)

                elif res.get("error"):
                    resp = f"⚠️ {res['error']}"
                else:
                    resp = get_ai_response(prompt, None, st.session_state.messages, market)

                st.markdown(resp)

                if chart_ticker :
                    ch = build_chart(chart_ticker)
                    if ch:
                        st.plotly_chart(ch, use_container_width=True)

                if table_data:
                    st.dataframe(pd.DataFrame(table_data), use_container_width=True, hide_index=True)

        st.session_state.messages.append({
            "role": "assistant",
            "content": resp,
            "chart": chart_ticker,
            "table": table_data,
        })

    # Footer
    st.markdown("---")
    st.caption("not financial advice · always do your own research")


if __name__ == "__main__":
    main()
