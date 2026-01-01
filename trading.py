import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import warnings
import time
import json
import os
from dotenv import load_dotenv
import re
from groq import Groq

warnings.filterwarnings('ignore')
load_dotenv()

st.set_page_config(
    page_title="AI Stock Analyzer",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
    .stApp {
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%) !important;
        color: #ffffff !important;
    }
    h1, h2, h3, h4, h5, h6 {
        color: #ffffff !important;
        font-family: 'Inter', 'Segoe UI', sans-serif !important;
        font-weight: 600 !important;
    }
    p, span, div, label, .stMarkdown { color: #e5e7eb !important; }
    .stChatMessage {
        background: rgba(255, 255, 255, 0.05) !important;
        border-radius: 12px !important;
        padding: 1rem !important;
        margin: 0.5rem 0 !important;
    }
    input, textarea {
        background: rgba(255, 255, 255, 0.1) !important;
        color: #ffffff !important;
        border: 1px solid rgba(255, 255, 255, 0.2) !important;
    }
    .stButton > button {
        background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%) !important;
        color: white !important;
        border: none !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
    }
    .stButton > button:hover {
        background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%) !important;
    }
    a { color: #60a5fa !important; }
</style>
""", unsafe_allow_html=True)

# ==================== STOCK UNIVERSES ====================

US_STOCKS = [
    'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META', 'TSLA', 'BRK-B', 'V', 'UNH',
    'JNJ', 'WMT', 'JPM', 'MA', 'PG', 'XOM', 'HD', 'CVX', 'MRK', 'ABBV',
    'PEP', 'KO', 'AVGO', 'COST', 'LLY', 'TMO', 'ACN', 'MCD', 'CSCO', 'ABT',
    'DHR', 'CRM', 'VZ', 'ADBE', 'NKE', 'NEE', 'WFC', 'TXN', 'PM', 'UPS',
    'RTX', 'HON', 'ORCL', 'BMY', 'QCOM', 'UNP', 'INTU', 'LOW', 'AMD', 'COP',
    'BA', 'AMGN', 'SPGI', 'GE', 'CAT', 'PLD', 'SBUX', 'GILD', 'DE', 'MMC'
]

INDIAN_STOCKS = [
    'RELIANCE.NS', 'TCS.NS', 'HDFCBANK.NS', 'INFY.NS', 'ICICIBANK.NS',
    'HINDUNILVR.NS', 'ITC.NS', 'SBIN.NS', 'BHARTIARTL.NS', 'KOTAKBANK.NS',
    'LT.NS', 'HCLTECH.NS', 'AXISBANK.NS', 'ASIANPAINT.NS', 'MARUTI.NS',
    'SUNPHARMA.NS', 'TITAN.NS', 'BAJFINANCE.NS', 'DMART.NS', 'WIPRO.NS',
    'ULTRACEMCO.NS', 'ONGC.NS', 'NTPC.NS', 'POWERGRID.NS', 'M&M.NS',
    'TATAMOTORS.NS', 'TATASTEEL.NS', 'JSWSTEEL.NS', 'ADANIENT.NS', 'ADANIPORTS.NS',
    'COALINDIA.NS', 'BAJAJFINSV.NS', 'TECHM.NS', 'HDFCLIFE.NS', 'SBILIFE.NS',
    'GRASIM.NS', 'DIVISLAB.NS', 'DRREDDY.NS', 'CIPLA.NS', 'APOLLOHOSP.NS',
    'ZOMATO.NS', 'IRCTC.NS', 'HAL.NS', 'BEL.NS', 'TATAPOWER.NS'
]

# Session state
if 'chat_messages' not in st.session_state:
    st.session_state.chat_messages = []
if 'market' not in st.session_state:
    st.session_state.market = 'US'

# ==================== HELPER FUNCTIONS ====================

def get_stock_list():
    return INDIAN_STOCKS if st.session_state.market == 'India' else US_STOCKS

def get_display_ticker(ticker):
    return ticker.replace('.NS', '').replace('.BO', '')

def format_market_cap(value, market='US'):
    if value is None:
        return "N/A"
    symbol = '₹' if market == 'India' else '$'
    if value >= 1e12:
        return f"{symbol}{value/1e12:.2f}T"
    elif value >= 1e9:
        return f"{symbol}{value/1e9:.2f}B"
    elif value >= 1e6:
        return f"{symbol}{value/1e6:.2f}M"
    return f"{symbol}{value:,.0f}"

def format_price(value, market='US'):
    if value is None:
        return "N/A"
    symbol = '₹' if market == 'India' else '$'
    return f"{symbol}{value:,.2f}"

# ==================== LIVE DATA FUNCTIONS ====================

@st.cache_data(ttl=120)  # Cache for 2 minutes only
def get_live_stock_data(ticker):
    """Get LIVE stock data from Yahoo Finance - this is the PRIMARY data source"""
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        
        if not info or 'regularMarketPrice' not in info and 'currentPrice' not in info:
            # Try to get from history
            hist = stock.history(period='5d')
            if hist.empty:
                return None
            current_price = hist['Close'].iloc[-1]
        else:
            current_price = info.get('regularMarketPrice') or info.get('currentPrice') or info.get('previousClose')
        
        if current_price is None:
            hist = stock.history(period='5d')
            if not hist.empty:
                current_price = hist['Close'].iloc[-1]
            else:
                return None
        
        # Determine market
        market = 'India' if '.NS' in ticker or '.BO' in ticker else 'US'
        
        # Get previous close for change calculation
        prev_close = info.get('previousClose') or info.get('regularMarketPreviousClose') or current_price
        change = current_price - prev_close
        change_pct = (change / prev_close * 100) if prev_close else 0
        
        return {
            "ticker": ticker,
            "display_ticker": get_display_ticker(ticker),
            "name": info.get('longName') or info.get('shortName') or get_display_ticker(ticker),
            "price": round(current_price, 2),
            "price_fmt": format_price(current_price, market),
            "change": round(change, 2),
            "change_pct": round(change_pct, 2),
            "prev_close": round(prev_close, 2) if prev_close else None,
            "market_cap": info.get('marketCap'),
            "market_cap_fmt": format_market_cap(info.get('marketCap'), market),
            "pe_ratio": info.get('trailingPE'),
            "forward_pe": info.get('forwardPE'),
            "peg_ratio": info.get('pegRatio'),
            "price_to_book": info.get('priceToBook'),
            "roe": info.get('returnOnEquity'),
            "profit_margin": info.get('profitMargins'),
            "operating_margin": info.get('operatingMargins'),
            "debt_to_equity": info.get('debtToEquity'),
            "current_ratio": info.get('currentRatio'),
            "dividend_yield": info.get('dividendYield'),
            "payout_ratio": info.get('payoutRatio'),
            "beta": info.get('beta'),
            "52_week_high": info.get('fiftyTwoWeekHigh'),
            "52_week_low": info.get('fiftyTwoWeekLow'),
            "avg_volume": info.get('averageVolume'),
            "sector": info.get('sector', 'N/A'),
            "industry": info.get('industry', 'N/A'),
            "market": market,
            "business_summary": info.get('longBusinessSummary', 'No description available.')
        }
    except Exception as e:
        return None

# ==================== STOCK ANALYSIS TOOLS ====================

def analyze_stock(ticker):
    """Analyze a single stock with LIVE data"""
    # Normalize ticker
    original = ticker.upper().strip().replace('.NS', '').replace('.BO', '')
    market = st.session_state.market
    
    # Try current market first
    if market == 'India':
        full_ticker = f"{original}.NS"
    else:
        full_ticker = original
    
    data = get_live_stock_data(full_ticker)
    
    # If not found, try other market
    if not data:
        alt_ticker = original if market == 'India' else f"{original}.NS"
        data = get_live_stock_data(alt_ticker)
    
    if not data:
        return {"success": False, "error": f"Could not fetch live data for {original}. Please check the ticker symbol."}
    
    # Calculate scores
    val_score = 0
    if data['pe_ratio'] and data['pe_ratio'] > 0:
        if data['pe_ratio'] < 15: val_score += 2
        elif data['pe_ratio'] < 25: val_score += 1
    if data['peg_ratio'] and data['peg_ratio'] < 2:
        val_score += 2 if data['peg_ratio'] < 1 else 1
    
    prof_score = 0
    if data['roe'] and data['roe'] > 0.12:
        prof_score += 2 if data['roe'] > 0.20 else 1
    if data['profit_margin'] and data['profit_margin'] > 0.10:
        prof_score += 2 if data['profit_margin'] > 0.20 else 1
    
    health_score = 0
    if data['current_ratio'] and data['current_ratio'] > 1.2:
        health_score += 2 if data['current_ratio'] > 2 else 1
    if data['debt_to_equity'] and data['debt_to_equity'] < 100:
        health_score += 2 if data['debt_to_equity'] < 50 else 1
    
    total = val_score + prof_score + health_score
    max_score = 12
    pct = (total / max_score) * 100
    
    if pct >= 70: rating, emoji = "Strong Buy", "🟢"
    elif pct >= 55: rating, emoji = "Buy", "🟡"
    elif pct >= 40: rating, emoji = "Hold", "🟠"
    else: rating, emoji = "Caution", "🔴"
    
    currency = '₹' if data['market'] == 'India' else '$'
    
    return {
        "success": True,
        "data_source": "Yahoo Finance (Live)",
        "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "company": {
            "ticker": data['display_ticker'],
            "name": data['name'],
            "sector": data['sector'],
            "industry": data['industry'],
            "market": data['market']
        },
        "price_data": {
            "current_price": f"{currency}{data['price']:,.2f}",
            "change": f"{data['change']:+.2f}",
            "change_percent": f"{data['change_pct']:+.2f}%",
            "previous_close": f"{currency}{data['prev_close']:,.2f}" if data['prev_close'] else "N/A",
            "market_cap": data['market_cap_fmt'],
            "52_week_high": f"{currency}{data['52_week_high']:,.2f}" if data['52_week_high'] else "N/A",
            "52_week_low": f"{currency}{data['52_week_low']:,.2f}" if data['52_week_low'] else "N/A"
        },
        "valuation": {
            "pe_ratio": round(data['pe_ratio'], 2) if data['pe_ratio'] else "N/A",
            "forward_pe": round(data['forward_pe'], 2) if data['forward_pe'] else "N/A",
            "peg_ratio": round(data['peg_ratio'], 2) if data['peg_ratio'] else "N/A",
            "price_to_book": round(data['price_to_book'], 2) if data['price_to_book'] else "N/A",
            "score": f"{val_score}/4"
        },
        "profitability": {
            "roe": f"{data['roe']*100:.2f}%" if data['roe'] else "N/A",
            "profit_margin": f"{data['profit_margin']*100:.2f}%" if data['profit_margin'] else "N/A",
            "operating_margin": f"{data['operating_margin']*100:.2f}%" if data['operating_margin'] else "N/A",
            "score": f"{prof_score}/4"
        },
        "financial_health": {
            "debt_to_equity": round(data['debt_to_equity'], 2) if data['debt_to_equity'] else "N/A",
            "current_ratio": round(data['current_ratio'], 2) if data['current_ratio'] else "N/A",
            "score": f"{health_score}/4"
        },
        "dividends": {
            "dividend_yield": f"{data['dividend_yield']*100:.2f}%" if data['dividend_yield'] else "N/A",
            "payout_ratio": f"{data['payout_ratio']*100:.1f}%" if data['payout_ratio'] else "N/A"
        },
        "rating": {
            "score": f"{total}/{max_score}",
            "percentage": round(pct, 1),
            "recommendation": rating,
            "emoji": emoji
        },
        "summary": data['business_summary'][:400] + "..." if len(str(data['business_summary'])) > 400 else data['business_summary']
    }


def compare_stocks(tickers_str):
    """Compare multiple stocks with LIVE data"""
    tickers = [t.strip().upper() for t in re.split(r'[,\s]+', tickers_str) if t.strip()]
    tickers = [t.replace('.NS', '').replace('.BO', '') for t in tickers]
    
    results = []
    market = st.session_state.market
    
    for ticker in tickers[:5]:
        full_ticker = f"{ticker}.NS" if market == 'India' else ticker
        data = get_live_stock_data(full_ticker)
        
        if not data:
            alt = ticker if market == 'India' else f"{ticker}.NS"
            data = get_live_stock_data(alt)
        
        if data:
            currency = '₹' if data['market'] == 'India' else '$'
            results.append({
                "ticker": data['display_ticker'],
                "name": data['name'],
                "price": f"{currency}{data['price']:,.2f}",
                "change": f"{data['change_pct']:+.2f}%",
                "market_cap": data['market_cap_fmt'],
                "pe_ratio": round(data['pe_ratio'], 2) if data['pe_ratio'] else "N/A",
                "roe": f"{data['roe']*100:.1f}%" if data['roe'] else "N/A",
                "profit_margin": f"{data['profit_margin']*100:.1f}%" if data['profit_margin'] else "N/A",
                "dividend_yield": f"{data['dividend_yield']*100:.2f}%" if data['dividend_yield'] else "N/A",
                "sector": data['sector']
            })
        else:
            results.append({"ticker": ticker, "error": "Data not available"})
    
    return {
        "success": True,
        "data_source": "Yahoo Finance (Live)",
        "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "count": len(results),
        "comparisons": results
    }


def find_undervalued_stocks():
    """Find undervalued stocks with LIVE data"""
    results = []
    stocks = get_stock_list()
    market = st.session_state.market
    
    progress = st.progress(0)
    status = st.empty()
    
    for i, ticker in enumerate(stocks):
        progress.progress((i + 1) / len(stocks))
        status.text(f"Scanning {get_display_ticker(ticker)}...")
        
        data = get_live_stock_data(ticker)
        if not data:
            continue
        
        pe = data['pe_ratio']
        roe = data['roe']
        
        if pe and pe > 0 and pe < 20:
            if roe and roe > 0.12:
                currency = '₹' if data['market'] == 'India' else '$'
                results.append({
                    "ticker": data['display_ticker'],
                    "name": data['name'],
                    "price": f"{currency}{data['price']:,.2f}",
                    "pe_ratio": round(pe, 2),
                    "roe": f"{roe*100:.1f}%",
                    "sector": data['sector']
                })
    
    progress.empty()
    status.empty()
    
    if results:
        results = sorted(results, key=lambda x: x['pe_ratio'])
        return {
            "success": True,
            "data_source": "Yahoo Finance (Live)",
            "market": market,
            "criteria": "PE < 20, ROE > 12%",
            "total_found": len(results),
            "stocks": results[:15]
        }
    return {"success": False, "message": "No undervalued stocks found"}


def find_growth_stocks():
    """Find high growth stocks"""
    results = []
    stocks = get_stock_list()
    market = st.session_state.market
    
    progress = st.progress(0)
    status = st.empty()
    
    for i, ticker in enumerate(stocks):
        progress.progress((i + 1) / len(stocks))
        status.text(f"Scanning {get_display_ticker(ticker)}...")
        
        data = get_live_stock_data(ticker)
        if not data:
            continue
        
        roe = data['roe']
        margin = data['profit_margin']
        
        if roe and roe > 0.15 and margin and margin > 0.10:
            currency = '₹' if data['market'] == 'India' else '$'
            results.append({
                "ticker": data['display_ticker'],
                "name": data['name'],
                "price": f"{currency}{data['price']:,.2f}",
                "roe": f"{roe*100:.1f}%",
                "profit_margin": f"{margin*100:.1f}%",
                "sector": data['sector']
            })
    
    progress.empty()
    status.empty()
    
    if results:
        results = sorted(results, key=lambda x: float(x['roe'].replace('%', '')), reverse=True)
        return {
            "success": True,
            "data_source": "Yahoo Finance (Live)",
            "market": market,
            "criteria": "ROE > 15%, Profit Margin > 10%",
            "total_found": len(results),
            "stocks": results[:15]
        }
    return {"success": False, "message": "No growth stocks found"}


def find_dividend_stocks():
    """Find dividend stocks"""
    results = []
    stocks = get_stock_list()
    market = st.session_state.market
    
    progress = st.progress(0)
    status = st.empty()
    
    for i, ticker in enumerate(stocks):
        progress.progress((i + 1) / len(stocks))
        status.text(f"Scanning {get_display_ticker(ticker)}...")
        
        data = get_live_stock_data(ticker)
        if not data:
            continue
        
        div_yield = data['dividend_yield']
        
        if div_yield and div_yield > 0.02:
            currency = '₹' if data['market'] == 'India' else '$'
            results.append({
                "ticker": data['display_ticker'],
                "name": data['name'],
                "price": f"{currency}{data['price']:,.2f}",
                "dividend_yield": f"{div_yield*100:.2f}%",
                "pe_ratio": round(data['pe_ratio'], 2) if data['pe_ratio'] else "N/A",
                "sector": data['sector']
            })
    
    progress.empty()
    status.empty()
    
    if results:
        results = sorted(results, key=lambda x: float(x['dividend_yield'].replace('%', '')), reverse=True)
        return {
            "success": True,
            "data_source": "Yahoo Finance (Live)",
            "market": market,
            "criteria": "Dividend Yield > 2%",
            "total_found": len(results),
            "stocks": results[:15]
        }
    return {"success": False, "message": "No dividend stocks found"}


# ==================== AI CHATBOT ====================

def detect_and_execute(message):
    """Detect intent and fetch LIVE data"""
    msg = message.lower()
    
    # Undervalued stocks
    if any(w in msg for w in ['undervalued', 'value stock', 'cheap', 'low pe']):
        return find_undervalued_stocks()
    
    # Growth stocks
    if any(w in msg for w in ['growth', 'growing', 'high growth']):
        return find_growth_stocks()
    
    # Dividend stocks
    if any(w in msg for w in ['dividend', 'yield', 'income']):
        return find_dividend_stocks()
    
    # Compare stocks
    if any(w in msg for w in ['compare', 'vs', 'versus', 'comparison']):
        tickers = re.findall(r'\b([A-Z]{2,6})\b', message.upper())
        exclude = ['PE', 'ROE', 'VS', 'AND', 'THE', 'FOR', 'ROA', 'EPS']
        tickers = [t for t in tickers if t not in exclude]
        if len(tickers) >= 2:
            return compare_stocks(','.join(tickers))
    
    # Single stock analysis - check for any ticker
    tickers = re.findall(r'\b([A-Z]{2,6})\b', message.upper())
    exclude = ['PE', 'ROE', 'VS', 'AND', 'THE', 'FOR', 'ROA', 'EPS', 'AI', 'OK', 'HI', 'CEO', 'CFO', 'IPO']
    
    # Check US stocks
    for t in tickers:
        if t in US_STOCKS and t not in exclude:
            return analyze_stock(t)
    
    # Check Indian stocks
    indian_names = [s.replace('.NS', '') for s in INDIAN_STOCKS]
    for t in tickers:
        if t in indian_names and t not in exclude:
            return analyze_stock(t)
    
    # Generic analysis request
    if any(w in msg for w in ['analyze', 'analysis', 'check', 'tell me', 'how is', 'price of', 'stock price']):
        for t in tickers:
            if t not in exclude:
                return analyze_stock(t)
    
    return None


def process_message(user_message, history):
    """Process with Groq AI"""
    api_key = None
    try:
        if hasattr(st, 'secrets') and "GROQ_API_KEY" in st.secrets:
            api_key = st.secrets["GROQ_API_KEY"]
    except:
        pass
    
    if not api_key:
        api_key = os.environ.get("GROQ_API_KEY")
    
    if not api_key:
        return "⚠️ Please set GROQ_API_KEY in Streamlit Secrets."
    
    # Get live data first
    data = detect_and_execute(user_message)
    
    client = Groq(api_key=api_key)
    market = st.session_state.market
    currency = '₹' if market == 'India' else '$'
    
    system = f"""You are a stock analyst with access to LIVE market data.

IMPORTANT RULES:
1. ONLY use the data provided in this prompt - it is LIVE from Yahoo Finance
2. NEVER use your training data for stock prices - they are outdated
3. Always mention the data is live from Yahoo Finance
4. If no data is provided, tell the user you couldn't fetch live data

Current market: {market}
Currency: {currency}
Timestamp: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

Format responses with:
- Clear headers
- Tables for comparisons
- Key insights highlighted
- Note: "Data is live from Yahoo Finance"
- Disclaimer: Educational only, not financial advice"""

    messages = [{"role": "system", "content": system}]
    
    for m in history[-4:]:
        messages.append({"role": m["role"], "content": m["content"]})
    
    if data:
        prompt = f"""User question: {user_message}

LIVE DATA FROM YAHOO FINANCE (use ONLY this data):
{json.dumps(data, indent=2, default=str)}

Analyze this LIVE data and respond. NEVER mention old prices from your training."""
    else:
        prompt = f"""User question: {user_message}

I could not fetch live data for this query. Please:
1. Ask the user to specify a valid stock ticker
2. Suggest example tickers ({', '.join(US_STOCKS[:5])} for US or {', '.join([s.replace('.NS','') for s in INDIAN_STOCKS[:5]])} for India)
3. Do NOT provide any stock prices from your training data - they are outdated"""
    
    messages.append({"role": "user", "content": prompt})
    
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            max_tokens=2048,
            temperature=0.5
        )
        return response.choices[0].message.content
    except Exception as e:
        if "rate_limit" in str(e).lower():
            return "⚠️ Rate limit. Please wait and try again."
        return f"❌ Error: {e}"


# ==================== UI ====================

col1, col2, col3 = st.columns([3, 1, 1])
with col1:
    st.title("📊 AI Stock Analyzer")
    st.caption("Live data from Yahoo Finance | US & Indian Markets")
with col2:
    market = st.selectbox("🌍 Market", ['US', 'India'], 
                          index=0 if st.session_state.market == 'US' else 1,
                          key="mkt")
    if market != st.session_state.market:
        st.session_state.market = market
        st.session_state.chat_messages = []
        st.cache_data.clear()
        st.rerun()
with col3:
    if st.button("🔄 Refresh"):
        st.cache_data.clear()
        st.rerun()

# Market indicator
emoji = "🇺🇸" if st.session_state.market == 'US' else "🇮🇳"
st.info(f"{emoji} **{st.session_state.market}** Market | Data updates every 2 minutes")

st.markdown("---")

# API check
api_key = None
try:
    if hasattr(st, 'secrets') and "GROQ_API_KEY" in st.secrets:
        api_key = st.secrets["GROQ_API_KEY"]
except:
    pass
if not api_key:
    api_key = os.environ.get("GROQ_API_KEY")
if not api_key:
    st.error("⚠️ Add GROQ_API_KEY to Streamlit Secrets")
    st.code('GROQ_API_KEY = "gsk_your_key"')
    st.stop()

# Quick actions
st.markdown("### ⚡ Quick Actions")
c1, c2, c3, c4, c5 = st.columns(5)

if st.session_state.market == 'India':
    with c1:
        if st.button("🔍 Undervalued", key="u"):
            st.session_state.chat_messages.append({"role": "user", "content": "Find undervalued Indian stocks"})
            st.rerun()
    with c2:
        if st.button("📈 Growth", key="g"):
            st.session_state.chat_messages.append({"role": "user", "content": "Find growth stocks"})
            st.rerun()
    with c3:
        if st.button("💰 Dividends", key="d"):
            st.session_state.chat_messages.append({"role": "user", "content": "Find dividend stocks"})
            st.rerun()
    with c4:
        if st.button("🏢 TCS", key="t"):
            st.session_state.chat_messages.append({"role": "user", "content": "Analyze TCS"})
            st.rerun()
    with c5:
        if st.button("🧹 Clear", key="c"):
            st.session_state.chat_messages = []
            st.rerun()
else:
    with c1:
        if st.button("🔍 Undervalued", key="u"):
            st.session_state.chat_messages.append({"role": "user", "content": "Find undervalued stocks"})
            st.rerun()
    with c2:
        if st.button("📈 Growth", key="g"):
            st.session_state.chat_messages.append({"role": "user", "content": "Find growth stocks"})
            st.rerun()
    with c3:
        if st.button("💰 Dividends", key="d"):
            st.session_state.chat_messages.append({"role": "user", "content": "Find dividend stocks"})
            st.rerun()
    with c4:
        if st.button("🏢 AAPL", key="a"):
            st.session_state.chat_messages.append({"role": "user", "content": "Analyze AAPL"})
            st.rerun()
    with c5:
        if st.button("🧹 Clear", key="c"):
            st.session_state.chat_messages = []
            st.rerun()

st.markdown("---")

# Chat
for m in st.session_state.chat_messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

if prompt := st.chat_input("Ask about stocks (e.g., 'Analyze AAPL', 'Compare TCS INFY')"):
    st.session_state.chat_messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    with st.chat_message("assistant"):
        with st.spinner("📡 Fetching live data..."):
            response = process_message(prompt, st.session_state.chat_messages[:-1])
        st.markdown(response)
    st.session_state.chat_messages.append({"role": "assistant", "content": response})
    st.rerun()

# Help
if not st.session_state.chat_messages:
    st.markdown("### 💡 Try:")
    if st.session_state.market == 'India':
        st.markdown("- `Analyze TCS` or `Analyze RELIANCE`")
        st.markdown("- `Compare TCS INFY WIPRO`")
        st.markdown("- `Find undervalued stocks`")
    else:
        st.markdown("- `Analyze AAPL` or `Analyze NVDA`")
        st.markdown("- `Compare AAPL MSFT GOOGL`")
        st.markdown("- `Find dividend stocks`")

st.markdown("---")
st.caption(f"📊 AI Stock Analyzer | {emoji} {st.session_state.market} | Live data from Yahoo Finance | ⚠️ Educational only")
