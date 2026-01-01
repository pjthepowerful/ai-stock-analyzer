import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import warnings
import json
import os
from dotenv import load_dotenv
import re
from groq import Groq

warnings.filterwarnings('ignore')
load_dotenv()

st.set_page_config(
    page_title="AI Stock Analyzer",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Clean modern CSS
st.markdown("""
<style>
    /* Main background */
    .stApp {
        background: linear-gradient(180deg, #0a0f1a 0%, #111827 100%);
    }
    
    /* Hide default streamlit elements */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* Typography */
    h1, h2, h3 {
        color: #ffffff !important;
        font-weight: 700 !important;
    }
    
    p, span, div, label {
        color: #d1d5db !important;
    }
    
    /* Chat container */
    .stChatMessage {
        background: rgba(255, 255, 255, 0.03) !important;
        border: 1px solid rgba(255, 255, 255, 0.08) !important;
        border-radius: 16px !important;
        padding: 1.25rem !important;
        margin: 0.75rem 0 !important;
    }
    
    /* Chat input */
    .stChatInput > div {
        background: rgba(255, 255, 255, 0.05) !important;
        border: 1px solid rgba(255, 255, 255, 0.1) !important;
        border-radius: 12px !important;
    }
    
    .stChatInput input {
        color: #ffffff !important;
    }
    
    /* Selectbox */
    .stSelectbox > div > div {
        background: rgba(255, 255, 255, 0.08) !important;
        border: 1px solid rgba(255, 255, 255, 0.15) !important;
        border-radius: 10px !important;
        color: #ffffff !important;
    }
    
    /* Buttons */
    .stButton > button {
        background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%) !important;
        color: white !important;
        border: none !important;
        border-radius: 10px !important;
        font-weight: 600 !important;
        padding: 0.5rem 1.5rem !important;
        transition: all 0.2s ease !important;
    }
    
    .stButton > button:hover {
        background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%) !important;
        transform: translateY(-1px) !important;
        box-shadow: 0 4px 12px rgba(37, 99, 235, 0.4) !important;
    }
    
    /* Info box */
    .stAlert {
        background: rgba(37, 99, 235, 0.1) !important;
        border: 1px solid rgba(37, 99, 235, 0.3) !important;
        border-radius: 12px !important;
    }
    
    /* Divider */
    hr {
        border-color: rgba(255, 255, 255, 0.1) !important;
        margin: 1.5rem 0 !important;
    }
    
    /* Code blocks in chat */
    code {
        background: rgba(255, 255, 255, 0.1) !important;
        color: #60a5fa !important;
        padding: 0.2rem 0.5rem !important;
        border-radius: 6px !important;
    }
    
    /* Links */
    a {
        color: #60a5fa !important;
    }
    
    /* Market badge */
    .market-badge {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        background: rgba(255, 255, 255, 0.05);
        padding: 8px 16px;
        border-radius: 20px;
        font-size: 14px;
        color: #9ca3af;
    }
    
    /* Header styling */
    .main-header {
        text-align: center;
        padding: 2rem 0 1rem 0;
    }
    
    .main-header h1 {
        font-size: 2.5rem !important;
        margin-bottom: 0.5rem !important;
        background: linear-gradient(135deg, #60a5fa 0%, #a78bfa 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
    }
    
    .main-header p {
        color: #6b7280 !important;
        font-size: 1rem;
    }
    
    /* Example chips */
    .example-chip {
        display: inline-block;
        background: rgba(255, 255, 255, 0.05);
        border: 1px solid rgba(255, 255, 255, 0.1);
        padding: 8px 16px;
        border-radius: 20px;
        margin: 4px;
        font-size: 13px;
        color: #9ca3af;
        cursor: pointer;
        transition: all 0.2s;
    }
    
    .example-chip:hover {
        background: rgba(255, 255, 255, 0.1);
        color: #ffffff;
    }
</style>
""", unsafe_allow_html=True)

# ==================== STOCK DATA ====================

US_STOCKS = [
    'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META', 'TSLA', 'BRK-B', 'V', 'UNH',
    'JNJ', 'WMT', 'JPM', 'MA', 'PG', 'XOM', 'HD', 'CVX', 'MRK', 'ABBV',
    'PEP', 'KO', 'AVGO', 'COST', 'LLY', 'TMO', 'ACN', 'MCD', 'CSCO', 'ABT',
    'DHR', 'CRM', 'VZ', 'ADBE', 'NKE', 'NEE', 'WFC', 'TXN', 'PM', 'UPS',
    'RTX', 'HON', 'ORCL', 'BMY', 'QCOM', 'UNP', 'INTU', 'LOW', 'AMD', 'COP'
]

INDIAN_STOCKS = [
    'RELIANCE.NS', 'TCS.NS', 'HDFCBANK.NS', 'INFY.NS', 'ICICIBANK.NS',
    'HINDUNILVR.NS', 'ITC.NS', 'SBIN.NS', 'BHARTIARTL.NS', 'KOTAKBANK.NS',
    'LT.NS', 'HCLTECH.NS', 'AXISBANK.NS', 'ASIANPAINT.NS', 'MARUTI.NS',
    'SUNPHARMA.NS', 'TITAN.NS', 'BAJFINANCE.NS', 'DMART.NS', 'WIPRO.NS',
    'ULTRACEMCO.NS', 'ONGC.NS', 'NTPC.NS', 'POWERGRID.NS', 'M&M.NS',
    'TATAMOTORS.NS', 'TATASTEEL.NS', 'JSWSTEEL.NS', 'ADANIENT.NS', 'ADANIPORTS.NS',
    'COALINDIA.NS', 'BAJAJFINSV.NS', 'TECHM.NS', 'HDFCLIFE.NS', 'SBILIFE.NS',
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

# ==================== LIVE DATA ====================

@st.cache_data(ttl=120)
def get_live_stock_data(ticker):
    """Get LIVE stock data from Yahoo Finance"""
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        
        if not info:
            return None
        
        # Get current price
        current_price = info.get('regularMarketPrice') or info.get('currentPrice') or info.get('previousClose')
        
        if current_price is None:
            hist = stock.history(period='5d')
            if not hist.empty:
                current_price = hist['Close'].iloc[-1]
            else:
                return None
        
        market = 'India' if '.NS' in ticker or '.BO' in ticker else 'US'
        prev_close = info.get('previousClose') or info.get('regularMarketPreviousClose') or current_price
        change = current_price - prev_close if prev_close else 0
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

# ==================== ANALYSIS TOOLS ====================

def analyze_stock(ticker):
    """Analyze a single stock"""
    original = ticker.upper().strip().replace('.NS', '').replace('.BO', '')
    market = st.session_state.market
    
    full_ticker = f"{original}.NS" if market == 'India' else original
    data = get_live_stock_data(full_ticker)
    
    if not data:
        alt_ticker = original if market == 'India' else f"{original}.NS"
        data = get_live_stock_data(alt_ticker)
    
    if not data:
        return {"success": False, "error": f"Could not fetch data for {original}"}
    
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
    pct = (total / 12) * 100
    
    if pct >= 70: rating, emoji = "Strong Buy", "🟢"
    elif pct >= 55: rating, emoji = "Buy", "🟡"
    elif pct >= 40: rating, emoji = "Hold", "🟠"
    else: rating, emoji = "Caution", "🔴"
    
    currency = '₹' if data['market'] == 'India' else '$'
    
    return {
        "success": True,
        "source": "Yahoo Finance (Live)",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "company": {
            "ticker": data['display_ticker'],
            "name": data['name'],
            "sector": data['sector'],
            "industry": data['industry'],
            "market": data['market']
        },
        "price": {
            "current": f"{currency}{data['price']:,.2f}",
            "change": f"{data['change']:+.2f}",
            "change_pct": f"{data['change_pct']:+.2f}%",
            "market_cap": data['market_cap_fmt'],
            "52w_high": f"{currency}{data['52_week_high']:,.2f}" if data['52_week_high'] else "N/A",
            "52w_low": f"{currency}{data['52_week_low']:,.2f}" if data['52_week_low'] else "N/A"
        },
        "valuation": {
            "pe": round(data['pe_ratio'], 2) if data['pe_ratio'] else "N/A",
            "forward_pe": round(data['forward_pe'], 2) if data['forward_pe'] else "N/A",
            "peg": round(data['peg_ratio'], 2) if data['peg_ratio'] else "N/A",
            "pb": round(data['price_to_book'], 2) if data['price_to_book'] else "N/A"
        },
        "profitability": {
            "roe": f"{data['roe']*100:.1f}%" if data['roe'] else "N/A",
            "profit_margin": f"{data['profit_margin']*100:.1f}%" if data['profit_margin'] else "N/A",
            "operating_margin": f"{data['operating_margin']*100:.1f}%" if data['operating_margin'] else "N/A"
        },
        "health": {
            "debt_equity": round(data['debt_to_equity'], 1) if data['debt_to_equity'] else "N/A",
            "current_ratio": round(data['current_ratio'], 2) if data['current_ratio'] else "N/A"
        },
        "dividend": {
            "yield": f"{data['dividend_yield']*100:.2f}%" if data['dividend_yield'] else "N/A",
            "payout": f"{data['payout_ratio']*100:.1f}%" if data['payout_ratio'] else "N/A"
        },
        "rating": {
            "score": f"{total}/12",
            "pct": round(pct, 1),
            "verdict": rating,
            "emoji": emoji
        },
        "about": data['business_summary'][:350] + "..." if len(str(data['business_summary'])) > 350 else data['business_summary']
    }


def compare_stocks(tickers_str):
    """Compare multiple stocks"""
    tickers = [t.strip().upper().replace('.NS', '').replace('.BO', '') for t in re.split(r'[,\s]+', tickers_str) if t.strip()]
    
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
                "name": data['name'][:25] + "..." if len(data['name']) > 25 else data['name'],
                "price": f"{currency}{data['price']:,.2f}",
                "change": f"{data['change_pct']:+.2f}%",
                "market_cap": data['market_cap_fmt'],
                "pe": round(data['pe_ratio'], 1) if data['pe_ratio'] else "N/A",
                "roe": f"{data['roe']*100:.0f}%" if data['roe'] else "N/A",
                "div_yield": f"{data['dividend_yield']*100:.1f}%" if data['dividend_yield'] else "-",
                "sector": data['sector']
            })
        else:
            results.append({"ticker": ticker, "error": "No data"})
    
    return {
        "success": True,
        "source": "Yahoo Finance (Live)",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "count": len(results),
        "stocks": results
    }


def screen_stocks(screen_type):
    """Screen stocks by criteria"""
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
        
        currency = '₹' if data['market'] == 'India' else '$'
        
        # Apply filter based on screen type
        if screen_type == "undervalued":
            if data['pe_ratio'] and 0 < data['pe_ratio'] < 20:
                if data['roe'] and data['roe'] > 0.12:
                    results.append({
                        "ticker": data['display_ticker'],
                        "name": data['name'][:20],
                        "price": f"{currency}{data['price']:,.2f}",
                        "pe": round(data['pe_ratio'], 1),
                        "roe": f"{data['roe']*100:.0f}%",
                        "sector": data['sector']
                    })
        
        elif screen_type == "growth":
            if data['roe'] and data['roe'] > 0.15:
                if data['profit_margin'] and data['profit_margin'] > 0.10:
                    results.append({
                        "ticker": data['display_ticker'],
                        "name": data['name'][:20],
                        "price": f"{currency}{data['price']:,.2f}",
                        "roe": f"{data['roe']*100:.0f}%",
                        "margin": f"{data['profit_margin']*100:.0f}%",
                        "sector": data['sector']
                    })
        
        elif screen_type == "dividend":
            if data['dividend_yield'] and data['dividend_yield'] > 0.02:
                results.append({
                    "ticker": data['display_ticker'],
                    "name": data['name'][:20],
                    "price": f"{currency}{data['price']:,.2f}",
                    "yield": f"{data['dividend_yield']*100:.2f}%",
                    "pe": round(data['pe_ratio'], 1) if data['pe_ratio'] else "N/A",
                    "sector": data['sector']
                })
    
    progress.empty()
    status.empty()
    
    criteria_map = {
        "undervalued": "PE < 20, ROE > 12%",
        "growth": "ROE > 15%, Margin > 10%",
        "dividend": "Yield > 2%"
    }
    
    if results:
        return {
            "success": True,
            "source": "Yahoo Finance (Live)",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "market": market,
            "screen": screen_type,
            "criteria": criteria_map.get(screen_type, ""),
            "found": len(results),
            "stocks": results[:15]
        }
    return {"success": False, "message": f"No {screen_type} stocks found"}


# ==================== AI CHAT ====================

def detect_and_execute(message):
    """Detect intent and get live data"""
    msg = message.lower()
    
    if any(w in msg for w in ['undervalued', 'value', 'cheap', 'low pe', 'bargain']):
        return screen_stocks("undervalued")
    
    if any(w in msg for w in ['growth', 'growing', 'high growth', 'fast growing']):
        return screen_stocks("growth")
    
    if any(w in msg for w in ['dividend', 'yield', 'income', 'passive']):
        return screen_stocks("dividend")
    
    if any(w in msg for w in ['compare', 'vs', 'versus', 'comparison']):
        tickers = re.findall(r'\b([A-Z]{2,6})\b', message.upper())
        exclude = ['PE', 'ROE', 'VS', 'AND', 'THE', 'FOR', 'ROA', 'EPS']
        tickers = [t for t in tickers if t not in exclude]
        if len(tickers) >= 2:
            return compare_stocks(','.join(tickers))
    
    # Single stock
    tickers = re.findall(r'\b([A-Z]{2,6})\b', message.upper())
    exclude = ['PE', 'ROE', 'VS', 'AND', 'THE', 'FOR', 'ROA', 'EPS', 'AI', 'OK', 'HI', 'CEO', 'CFO', 'IPO', 'IT', 'IS', 'BE', 'TO', 'IN', 'OF']
    
    for t in tickers:
        if t in US_STOCKS and t not in exclude:
            return analyze_stock(t)
    
    indian_names = [s.replace('.NS', '') for s in INDIAN_STOCKS]
    for t in tickers:
        if t in indian_names and t not in exclude:
            return analyze_stock(t)
    
    if any(w in msg for w in ['analyze', 'analysis', 'check', 'tell me', 'how is', 'price', 'stock']):
        for t in tickers:
            if t not in exclude and len(t) >= 2:
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
        return "⚠️ Please add GROQ_API_KEY to Streamlit Secrets"
    
    data = detect_and_execute(user_message)
    
    client = Groq(api_key=api_key)
    market = st.session_state.market
    currency = '₹' if market == 'India' else '$'
    
    system = f"""You are a professional stock analyst with LIVE market data access.

CRITICAL RULES:
1. ONLY use data provided in this prompt - it's LIVE from Yahoo Finance
2. NEVER use training data for prices - it's outdated
3. Always note data is from Yahoo Finance
4. Format responses cleanly with markdown

Market: {market} | Currency: {currency}
Time: {datetime.now().strftime("%Y-%m-%d %H:%M")}

Style: Professional, concise, data-driven
Always add: "⚠️ Educational only, not financial advice" at the end"""

    messages = [{"role": "system", "content": system}]
    
    for m in history[-4:]:
        messages.append({"role": m["role"], "content": m["content"]})
    
    if data:
        prompt = f"""Question: {user_message}

LIVE DATA (use ONLY this):
{json.dumps(data, indent=2, default=str)}

Provide analysis based on this live data."""
    else:
        prompt = f"""Question: {user_message}

No live data was fetched. Either:
1. Help with general stock questions
2. Ask user to specify a ticker (like AAPL, NVDA, TCS, RELIANCE)
3. DO NOT provide any stock prices - they would be outdated"""
    
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
            return "⚠️ Rate limit reached. Please wait a moment."
        return f"Error: {e}"


# ==================== UI ====================

# Header
st.markdown("""
<div class="main-header">
    <h1>📈 AI Stock Analyzer</h1>
    <p>Real-time analysis for US & Indian markets</p>
</div>
""", unsafe_allow_html=True)

# Controls row
col1, col2, col3 = st.columns([2, 1, 1])

with col1:
    market_emoji = "🇺🇸" if st.session_state.market == 'US' else "🇮🇳"
    st.markdown(f"""
    <div class="market-badge">
        {market_emoji} <strong>{st.session_state.market} Market</strong> • Live data from Yahoo Finance
    </div>
    """, unsafe_allow_html=True)

with col2:
    market = st.selectbox(
        "Market",
        ['US', 'India'],
        index=0 if st.session_state.market == 'US' else 1,
        label_visibility="collapsed"
    )
    if market != st.session_state.market:
        st.session_state.market = market
        st.session_state.chat_messages = []
        st.cache_data.clear()
        st.rerun()

with col3:
    col3a, col3b = st.columns(2)
    with col3a:
        if st.button("🔄 Refresh", use_container_width=True):
            st.cache_data.clear()
            st.rerun()
    with col3b:
        if st.button("🗑️ Clear", use_container_width=True):
            st.session_state.chat_messages = []
            st.rerun()

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
    st.error("⚠️ **Setup Required**")
    st.markdown("""
    1. Get free API key: [console.groq.com/keys](https://console.groq.com/keys)
    2. Add to Streamlit Secrets:
    ```
    GROQ_API_KEY = "gsk_your_key_here"
    ```
    """)
    st.stop()

# Chat messages
for m in st.session_state.chat_messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

# Welcome message when empty
if not st.session_state.chat_messages:
    st.markdown("### 👋 Welcome! What would you like to know?")
    
    st.markdown("**Try asking:**")
    
    if st.session_state.market == 'India':
        examples = [
            "Analyze TCS",
            "Compare RELIANCE, INFY, TCS", 
            "Find undervalued stocks",
            "Show dividend stocks",
            "How is HDFC Bank doing?"
        ]
    else:
        examples = [
            "Analyze AAPL",
            "Compare AAPL, MSFT, GOOGL",
            "Find undervalued stocks", 
            "Show growth stocks",
            "Tell me about NVDA"
        ]
    
    cols = st.columns(len(examples))
    for i, ex in enumerate(examples):
        with cols[i]:
            if st.button(ex, key=f"ex_{i}", use_container_width=True):
                st.session_state.chat_messages.append({"role": "user", "content": ex})
                st.rerun()

# Chat input
if prompt := st.chat_input("Ask about any stock... (e.g., 'Analyze AAPL' or 'Compare TCS, INFY')"):
    st.session_state.chat_messages.append({"role": "user", "content": prompt})
    
    with st.chat_message("user"):
        st.markdown(prompt)
    
    with st.chat_message("assistant"):
        with st.spinner("📡 Fetching live data..."):
            response = process_message(prompt, st.session_state.chat_messages[:-1])
        st.markdown(response)
    
    st.session_state.chat_messages.append({"role": "assistant", "content": response})
    st.rerun()

# Footer
st.markdown("---")
st.markdown("""
<div style="text-align: center; color: #6b7280; font-size: 12px;">
    <p>📈 AI Stock Analyzer • Live data from Yahoo Finance • Powered by Groq AI</p>
    <p>⚠️ For educational purposes only. Not financial advice.</p>
</div>
""", unsafe_allow_html=True)
