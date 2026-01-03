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
import plotly.graph_objects as go
from plotly.subplots import make_subplots

warnings.filterwarnings('ignore')
load_dotenv()

st.set_page_config(
    page_title="Paula - AI Stock Analyst",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Force dark theme via config
if 'theme' not in st.session_state:
    st.session_state.theme = 'dark'

# CSS - Force Dark Mode
st.markdown("""
<style>
    /* Force dark mode */
    :root { color-scheme: dark !important; }
    
    .stApp { background: linear-gradient(180deg, #0a0f1a 0%, #111827 100%) !important; }
    #MainMenu, footer, header {visibility: hidden;}
    
    h1, h2, h3 {color: #ffffff !important; font-weight: 700 !important;}
    p, span, div, label {color: #d1d5db !important;}
    
    .stChatMessage {
        background: rgba(255, 255, 255, 0.03) !important;
        border: 1px solid rgba(255, 255, 255, 0.08) !important;
        border-radius: 16px !important;
    }
    
    .stChatMessage p, .stChatMessage span, .stChatMessage div {
        color: #e5e7eb !important;
    }
    
    .stSelectbox > div > div {
        background: rgba(255, 255, 255, 0.08) !important;
        border: 1px solid rgba(255, 255, 255, 0.15) !important;
        border-radius: 10px !important;
        color: #ffffff !important;
    }
    
    .stButton > button {
        background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%) !important;
        color: white !important; 
        border: none !important; 
        border-radius: 10px !important;
    }
    
    .stButton > button:hover {
        background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%) !important;
    }
    
    hr {border-color: rgba(255, 255, 255, 0.1) !important;}
    
    .main-header {text-align: center; padding: 1rem 0;}
    .main-header h1 {
        font-size: 2.5rem !important;
        background: linear-gradient(135deg, #60a5fa 0%, #a78bfa 100%);
        -webkit-background-clip: text; 
        -webkit-text-fill-color: transparent;
        background-clip: text;
    }
    
    .market-badge {
        display: inline-flex; align-items: center; gap: 8px;
        background: rgba(255, 255, 255, 0.05);
        padding: 8px 16px; border-radius: 20px; font-size: 14px; color: #9ca3af !important;
    }
    
    /* Unified input styling - ALWAYS DARK */
    .stTextInput > div > div > input {
        background: #1a1a2e !important;
        border: 1px solid rgba(255, 255, 255, 0.2) !important;
        border-radius: 12px !important;
        padding: 14px 18px !important;
        color: #ffffff !important;
        font-size: 16px !important;
    }
    
    .stTextInput > div > div > input::placeholder {
        color: #6b7280 !important;
    }
    
    .stTextInput > div > div > input:focus {
        border-color: #8b5cf6 !important;
        box-shadow: 0 0 0 3px rgba(139, 92, 246, 0.25) !important;
        background: #1a1a2e !important;
    }
    
    /* Force form container dark */
    [data-testid="stForm"] {
        background: #0d1117 !important;
        border: 1px solid rgba(255, 255, 255, 0.1) !important;
        border-radius: 16px !important;
        padding: 12px !important;
    }
    
    /* Force submit button dark */
    .stFormSubmitButton > button {
        background: #1a1a2e !important;
        color: #ffffff !important;
        border: 1px solid rgba(255, 255, 255, 0.2) !important;
        border-radius: 12px !important;
    }
    
    .stFormSubmitButton > button:hover {
        background: #2d2d44 !important;
        border-color: #8b5cf6 !important;
    }
    
    /* Force mic button area dark */
    [data-testid="stForm"] [data-testid="column"] {
        background: transparent !important;
    }
    
    /* Dataframe styling */
    .stDataFrame { background: rgba(255, 255, 255, 0.03) !important; border-radius: 10px !important; }
    
    /* Progress bar */
    .stProgress > div > div { background: linear-gradient(90deg, #8b5cf6, #6d28d9) !important; }
    
    /* Scrollbar */
    ::-webkit-scrollbar { width: 8px; height: 8px; }
    ::-webkit-scrollbar-track { background: #1f2937; }
    ::-webkit-scrollbar-thumb { background: #4b5563; border-radius: 4px; }
</style>
""", unsafe_allow_html=True)

# ==================== STOCK DATA ====================
US_STOCKS = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META', 'TSLA', 'BRK-B', 'V', 'UNH',
    'JNJ', 'WMT', 'JPM', 'MA', 'PG', 'XOM', 'HD', 'CVX', 'MRK', 'ABBV',
    'PEP', 'KO', 'AVGO', 'COST', 'LLY', 'TMO', 'ACN', 'MCD', 'CSCO', 'ABT',
    'DHR', 'CRM', 'VZ', 'ADBE', 'NKE', 'NEE', 'WFC', 'TXN', 'PM', 'UPS',
    'RTX', 'HON', 'ORCL', 'BMY', 'QCOM', 'UNP', 'INTU', 'LOW', 'AMD', 'COP']

INDIAN_STOCKS = ['RELIANCE.NS', 'TCS.NS', 'HDFCBANK.NS', 'INFY.NS', 'ICICIBANK.NS',
    'HINDUNILVR.NS', 'ITC.NS', 'SBIN.NS', 'BHARTIARTL.NS', 'KOTAKBANK.NS',
    'LT.NS', 'HCLTECH.NS', 'AXISBANK.NS', 'ASIANPAINT.NS', 'MARUTI.NS',
    'SUNPHARMA.NS', 'TITAN.NS', 'BAJFINANCE.NS', 'DMART.NS', 'WIPRO.NS']

# Company name to ticker mapping (case-insensitive)
COMPANY_TO_TICKER = {
    # US Companies
    'apple': 'AAPL', 'microsoft': 'MSFT', 'google': 'GOOGL', 'alphabet': 'GOOGL',
    'amazon': 'AMZN', 'nvidia': 'NVDA', 'meta': 'META', 'facebook': 'META',
    'tesla': 'TSLA', 'berkshire': 'BRK-B', 'visa': 'V', 'unitedhealth': 'UNH',
    'johnson': 'JNJ', 'walmart': 'WMT', 'jpmorgan': 'JPM', 'chase': 'JPM',
    'mastercard': 'MA', 'procter': 'PG', 'exxon': 'XOM', 'home depot': 'HD',
    'chevron': 'CVX', 'merck': 'MRK', 'abbvie': 'ABBV', 'pepsi': 'PEP',
    'pepsico': 'PEP', 'coca cola': 'KO', 'coke': 'KO', 'broadcom': 'AVGO',
    'costco': 'COST', 'eli lilly': 'LLY', 'lilly': 'LLY', 'thermo fisher': 'TMO',
    'accenture': 'ACN', 'mcdonalds': 'MCD', "mcdonald's": 'MCD', 'cisco': 'CSCO',
    'abbott': 'ABT', 'danaher': 'DHR', 'salesforce': 'CRM', 'verizon': 'VZ',
    'adobe': 'ADBE', 'nike': 'NKE', 'nextera': 'NEE', 'wells fargo': 'WFC',
    'texas instruments': 'TXN', 'philip morris': 'PM', 'ups': 'UPS',
    'raytheon': 'RTX', 'honeywell': 'HON', 'oracle': 'ORCL', 'bristol': 'BMY',
    'qualcomm': 'QCOM', 'union pacific': 'UNP', 'intuit': 'INTU', 'lowes': 'LOW',
    "lowe's": 'LOW', 'amd': 'AMD', 'conocophillips': 'COP', 'netflix': 'NFLX',
    'disney': 'DIS', 'paypal': 'PYPL', 'intel': 'INTC', 'ibm': 'IBM',
    'boeing': 'BA', 'caterpillar': 'CAT', 'goldman': 'GS', 'morgan stanley': 'MS',
    'spotify': 'SPOT', 'uber': 'UBER', 'airbnb': 'ABNB', 'zoom': 'ZM',
    'snowflake': 'SNOW', 'palantir': 'PLTR', 'coinbase': 'COIN', 'robinhood': 'HOOD',
    
    # Indian Companies
    'reliance': 'RELIANCE', 'tcs': 'TCS', 'tata consultancy': 'TCS',
    'hdfc': 'HDFCBANK', 'hdfc bank': 'HDFCBANK', 'infosys': 'INFY',
    'icici': 'ICICIBANK', 'icici bank': 'ICICIBANK', 'hindustan unilever': 'HINDUNILVR',
    'hul': 'HINDUNILVR', 'itc': 'ITC', 'sbi': 'SBIN', 'state bank': 'SBIN',
    'bharti airtel': 'BHARTIARTL', 'airtel': 'BHARTIARTL', 'kotak': 'KOTAKBANK',
    'larsen': 'LT', 'l&t': 'LT', 'hcl': 'HCLTECH', 'axis': 'AXISBANK',
    'axis bank': 'AXISBANK', 'asian paints': 'ASIANPAINT', 'maruti': 'MARUTI',
    'maruti suzuki': 'MARUTI', 'sun pharma': 'SUNPHARMA', 'titan': 'TITAN',
    'bajaj finance': 'BAJFINANCE', 'bajaj': 'BAJFINANCE', 'dmart': 'DMART',
    'avenue supermarts': 'DMART', 'wipro': 'WIPRO'
}

def get_ticker_from_name(query):
    """Convert company name to ticker symbol"""
    query_lower = query.lower().strip()
    
    # Direct match
    if query_lower in COMPANY_TO_TICKER:
        return COMPANY_TO_TICKER[query_lower]
    
    # Partial match (e.g., "apple inc" should match "apple")
    for name, ticker in COMPANY_TO_TICKER.items():
        if name in query_lower or query_lower in name:
            return ticker
    
    return None

def get_stock_list():
    return INDIAN_STOCKS if st.session_state.get('market') == 'India' else US_STOCKS

def get_display_ticker(ticker):
    return ticker.replace('.NS', '').replace('.BO', '')

def format_market_cap(value, market='US'):
    if value is None: return "N/A"
    symbol = '₹' if market == 'India' else '$'
    if value >= 1e12: return f"{symbol}{value/1e12:.2f}T"
    elif value >= 1e9: return f"{symbol}{value/1e9:.2f}B"
    elif value >= 1e6: return f"{symbol}{value/1e6:.2f}M"
    return f"{symbol}{value:,.0f}"

# ==================== TECHNICAL ====================
def calculate_rsi(data, period=14):
    delta = data['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def calculate_macd(data):
    exp1 = data['Close'].ewm(span=12, adjust=False).mean()
    exp2 = data['Close'].ewm(span=26, adjust=False).mean()
    macd = exp1 - exp2
    signal = macd.ewm(span=9, adjust=False).mean()
    return macd, signal, macd - signal

def create_technical_chart(ticker, period="6mo"):
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period=period)
        if hist.empty or len(hist) < 30: return None
        
        display_name = get_display_ticker(ticker)
        hist['RSI'] = calculate_rsi(hist)
        hist['MACD'], hist['Signal'], hist['MACD_Hist'] = calculate_macd(hist)
        hist['MA20'] = hist['Close'].rolling(window=20).mean()
        hist['MA50'] = hist['Close'].rolling(window=50).mean()
        
        fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.05,
            row_heights=[0.5, 0.25, 0.25], subplot_titles=(f'{display_name} Price', 'RSI', 'MACD'))
        
        fig.add_trace(go.Candlestick(x=hist.index, open=hist['Open'], high=hist['High'],
            low=hist['Low'], close=hist['Close'], name='Price',
            increasing_line_color='#10b981', decreasing_line_color='#ef4444'), row=1, col=1)
        fig.add_trace(go.Scatter(x=hist.index, y=hist['MA20'], name='MA20', line=dict(color='#f59e0b', width=1)), row=1, col=1)
        fig.add_trace(go.Scatter(x=hist.index, y=hist['MA50'], name='MA50', line=dict(color='#8b5cf6', width=1)), row=1, col=1)
        fig.add_trace(go.Scatter(x=hist.index, y=hist['RSI'], name='RSI', line=dict(color='#06b6d4')), row=2, col=1)
        fig.add_hline(y=70, line_dash="dash", line_color="red", row=2, col=1)
        fig.add_hline(y=30, line_dash="dash", line_color="green", row=2, col=1)
        fig.add_trace(go.Scatter(x=hist.index, y=hist['MACD'], name='MACD', line=dict(color='#3b82f6')), row=3, col=1)
        fig.add_trace(go.Scatter(x=hist.index, y=hist['Signal'], name='Signal', line=dict(color='#f59e0b')), row=3, col=1)
        
        fig.update_layout(template='plotly_dark', paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
            height=600, margin=dict(l=50, r=30, t=40, b=30), showlegend=True, xaxis_rangeslider_visible=False)
        return fig
    except: return None

# ==================== DATA ====================
@st.cache_data(ttl=120)
def get_live_stock_data(ticker):
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        
        if not info or len(info) < 5:
            return None
        
        current_price = info.get('regularMarketPrice') or info.get('currentPrice') or info.get('previousClose')
        if current_price is None:
            hist = stock.history(period='5d')
            if not hist.empty: 
                current_price = hist['Close'].iloc[-1]
            else: 
                return None
        
        market = 'India' if '.NS' in ticker or '.BO' in ticker else 'US'
        prev_close = info.get('previousClose') or current_price
        change = current_price - prev_close if prev_close else 0
        change_pct = (change / prev_close * 100) if prev_close else 0
        
        return {
            "ticker": ticker, "display_ticker": get_display_ticker(ticker),
            "name": info.get('longName') or info.get('shortName') or get_display_ticker(ticker),
            "price": round(current_price, 2), "change": round(change, 2), "change_pct": round(change_pct, 2),
            "market_cap": info.get('marketCap'), "market_cap_fmt": format_market_cap(info.get('marketCap'), market),
            "pe_ratio": info.get('trailingPE'), "roe": info.get('returnOnEquity'),
            "profit_margin": info.get('profitMargins'), "debt_to_equity": info.get('debtToEquity'),
            "current_ratio": info.get('currentRatio'), "dividend_yield": info.get('dividendYield'),
            "sector": info.get('sector', 'N/A'), "industry": info.get('industry', 'N/A'), "market": market,
        }
    except:
        return None

# ==================== ANALYSIS ====================
def analyze_stock(ticker):
    original = ticker.upper().strip().replace('.NS', '').replace('.BO', '')
    market = st.session_state.get('market', 'US')
    full_ticker = f"{original}.NS" if market == 'India' else original
    data = get_live_stock_data(full_ticker)
    
    if not data:
        alt_ticker = original if market == 'India' else f"{original}.NS"
        data = get_live_stock_data(alt_ticker)
        full_ticker = alt_ticker
    
    if not data: 
        # Don't set charts if data fetch failed
        return {"success": False, "error": f"Could not fetch detailed data for {original}", "ticker": original}
    
    # Only show chart if we got valid data
    st.session_state.charts_to_display = [full_ticker]
    
    score = 0
    if data['pe_ratio'] and 0 < data['pe_ratio'] < 25: score += 2
    if data['roe'] and data['roe'] > 0.12: score += 2
    if data['profit_margin'] and data['profit_margin'] > 0.10: score += 2
    if data['current_ratio'] and data['current_ratio'] > 1.2: score += 1
    if data['debt_to_equity'] and data['debt_to_equity'] < 100: score += 1
    
    pct = (score / 8) * 100
    if pct >= 70: rating, emoji = "Strong Buy", "🟢"
    elif pct >= 50: rating, emoji = "Buy", "🟡"
    elif pct >= 35: rating, emoji = "Hold", "🟠"
    else: rating, emoji = "Caution", "🔴"
    
    currency = '₹' if data['market'] == 'India' else '$'
    return {
        "success": True, "ticker": data['display_ticker'], "name": data['name'],
        "sector": data['sector'], "price": f"{currency}{data['price']:,.2f}",
        "change": f"{data['change']:+.2f} ({data['change_pct']:+.2f}%)",
        "market_cap": data['market_cap_fmt'],
        "pe_ratio": round(data['pe_ratio'], 2) if data['pe_ratio'] else "N/A",
        "roe": f"{data['roe']*100:.1f}%" if data['roe'] else "N/A",
        "rating": f"{emoji} {rating} ({score}/8)"
    }

def compare_stocks(tickers_str):
    tickers = [t.strip().upper().replace('.NS', '') for t in re.split(r'[,\s]+', tickers_str) if t.strip()]
    results, full_tickers = [], []
    market = st.session_state.get('market', 'US')
    
    for ticker in tickers[:5]:
        full_ticker = f"{ticker}.NS" if market == 'India' else ticker
        data = get_live_stock_data(full_ticker)
        if not data:
            data = get_live_stock_data(ticker if market == 'India' else f"{ticker}.NS")
            full_ticker = ticker if market == 'India' else f"{ticker}.NS"
        if data:
            full_tickers.append(full_ticker)
            currency = '₹' if data['market'] == 'India' else '$'
            results.append({
                "Ticker": data['display_ticker'], "Price": f"{currency}{data['price']:,.2f}",
                "Change": f"{'🟢' if data['change_pct'] >= 0 else '🔴'} {data['change_pct']:+.2f}%",
                "P/E": round(data['pe_ratio'], 1) if data['pe_ratio'] else "N/A",
                "Sector": data['sector'][:15] if data['sector'] else "N/A"
            })
    
    st.session_state.charts_to_display = full_tickers
    return {"success": True, "count": len(results), "table": results}

def screen_stocks(screen_type):
    results, found_tickers = [], []
    stocks = get_stock_list()
    market = st.session_state.get('market', 'US')
    
    progress = st.progress(0)
    for i, ticker in enumerate(stocks):
        progress.progress((i + 1) / len(stocks))
        data = get_live_stock_data(ticker)
        if not data: continue
        
        currency = '₹' if data['market'] == 'India' else '$'
        
        if screen_type == "undervalued" and data['pe_ratio'] and 0 < data['pe_ratio'] < 20 and data['roe'] and data['roe'] > 0.12:
            found_tickers.append(ticker)
            results.append({"Ticker": data['display_ticker'], "Price": f"{currency}{data['price']:,.2f}",
                          "P/E": round(data['pe_ratio'], 1), "ROE": f"{data['roe']*100:.0f}%"})
        elif screen_type == "growth" and data['roe'] and data['roe'] > 0.15 and data['profit_margin'] and data['profit_margin'] > 0.10:
            found_tickers.append(ticker)
            results.append({"Ticker": data['display_ticker'], "Price": f"{currency}{data['price']:,.2f}",
                          "ROE": f"{data['roe']*100:.0f}%", "Margin": f"{data['profit_margin']*100:.0f}%"})
        elif screen_type == "dividend" and data['dividend_yield'] and data['dividend_yield'] > 0.02:
            found_tickers.append(ticker)
            results.append({"Ticker": data['display_ticker'], "Price": f"{currency}{data['price']:,.2f}",
                          "Yield": f"{data['dividend_yield']*100:.2f}%"})
    
    progress.empty()
    st.session_state.charts_to_display = found_tickers[:3]
    
    if results: return {"success": True, "screen_type": screen_type.title(), "found": len(results), "table": results[:15]}
    return {"success": False, "message": f"No {screen_type} stocks found"}

# ==================== AI ====================
def detect_and_execute(message):
    msg = message.lower()
    
    # Clear charts for non-stock queries
    st.session_state.charts_to_display = []
    
    # Check for screening keywords first
    if any(w in msg for w in ['undervalued', 'value stocks', 'cheap stocks']): return screen_stocks("undervalued")
    if any(w in msg for w in ['growth stocks', 'growing companies']): return screen_stocks("growth")
    if any(w in msg for w in ['dividend', 'yield', 'income stocks']): return screen_stocks("dividend")
    
    # Check for stock-related intent (must have these words to trigger stock analysis)
    stock_intent_words = ['stock', 'price', 'analyze', 'analysis', 'ticker', 'share', 'shares', 
                          'buy', 'sell', 'invest', 'trading', 'market cap', 'pe ratio', 'compare']
    has_stock_intent = any(w in msg for w in stock_intent_words)
    
    # Handle comparisons - check for company names AND tickers
    if any(w in msg for w in ['compare', 'vs', 'versus']):
        found_tickers = []
        
        # First, find company names in message
        for company_name, ticker in COMPANY_TO_TICKER.items():
            if company_name in msg:
                if ticker not in found_tickers:
                    found_tickers.append(ticker)
        
        # Also find ticker symbols
        ticker_matches = re.findall(r'\b([A-Z]{2,6})\b', message.upper())
        exclude = ['PE', 'ROE', 'VS', 'AND', 'THE', 'FOR', 'OR', 'COMPARE', 'WITH']
        for t in ticker_matches:
            if t not in exclude and t not in found_tickers:
                found_tickers.append(t)
        
        if len(found_tickers) >= 2:
            return compare_stocks(','.join(found_tickers))
    
    # First, try to find company name in message
    ticker_from_name = get_ticker_from_name(msg)
    if ticker_from_name:
        return analyze_stock(ticker_from_name)
    
    # Also check for multi-word company names
    for company_name in COMPANY_TO_TICKER.keys():
        if company_name in msg:
            return analyze_stock(COMPANY_TO_TICKER[company_name])
    
    # Only look for ticker symbols if there's stock intent
    if has_stock_intent:
        tickers = re.findall(r'\b([A-Z]{2,6})\b', message.upper())
        exclude = ['PE', 'ROE', 'VS', 'AND', 'THE', 'FOR', 'AI', 'OK', 'HI', 'RSI', 'MACD', 
                   'ANALYZE', 'ANALYSIS', 'TELL', 'ME', 'ABOUT', 'SHOW', 'GET', 'FIND', 
                   'STOCK', 'PRICE', 'BUY', 'SELL', 'WHAT', 'HOW', 'WHY', 'CAN', 'YOU']
        
        for t in tickers:
            if t in US_STOCKS and t not in exclude: return analyze_stock(t)
        
        indian_names = [s.replace('.NS', '') for s in INDIAN_STOCKS]
        for t in tickers:
            if t in indian_names and t not in exclude: return analyze_stock(t)
        
        # Only try unknown tickers if there's clear stock intent
        for t in tickers:
            if t not in exclude and len(t) >= 3: return analyze_stock(t)
    
    # No stock query detected - return None for general conversation
    return None

def process_message(user_message, history):
    api_key = st.secrets.get("GROQ_API_KEY") or os.environ.get("GROQ_API_KEY")
    if not api_key: return "⚠️ Please add GROQ_API_KEY to Streamlit Secrets", None
    
    data = detect_and_execute(user_message)
    client = Groq(api_key=api_key)
    market = st.session_state.get('market', 'US')
    
    system = f"""You are Paula, a friendly AI assistant who specializes in stock analysis but can chat about anything.
Market: {market} | Time: {datetime.now().strftime("%Y-%m-%d %H:%M")}

If stock data is provided, analyze it. If not, just have a helpful conversation.
For stock-related responses, end with: "⚠️ Educational only, not financial advice" """

    messages = [{"role": "system", "content": system}]
    for m in history[-4:]: messages.append({"role": m["role"], "content": m["content"]})
    
    if data and data.get("success"):
        data_for_ai = {k: v for k, v in data.items() if k != 'table'}
        if 'table' in data: data_for_ai['top_stocks'] = [row.get('Ticker', '') for row in data['table'][:5]]
        prompt = f"Question: {user_message}\n\nLIVE DATA:\n{json.dumps(data_for_ai, indent=2, default=str)}"
    else:
        # No stock data - just have a normal conversation
        prompt = user_message
    
    messages.append({"role": "user", "content": prompt})
    
    try:
        response = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=messages, max_tokens=1500, temperature=0.7)
        return response.choices[0].message.content, data
    except Exception as e:
        return f"Error: {e}", None

# ==================== DISPLAY ====================
def display_table(data):
    if "table" in data and data["table"]:
        st.dataframe(pd.DataFrame(data["table"]), use_container_width=True, hide_index=True)

def display_charts():
    charts = st.session_state.get('charts_to_display', [])
    if not charts: return
    
    st.markdown("### 📈 Charts")
    period = st.selectbox("Period", ["1mo", "3mo", "6mo", "1y"], index=2, key="chart_period")
    
    charts_loaded = False
    for ticker in charts[:3]:
        fig = create_technical_chart(ticker, period)
        if fig: 
            st.plotly_chart(fig, use_container_width=True)
            charts_loaded = True
    
    if not charts_loaded:
        st.warning("📊 Unable to load charts right now. Yahoo Finance may be temporarily unavailable.")

def process_and_display(prompt):
    st.session_state.chat_messages.append({"role": "user", "content": prompt})
    with st.spinner("📡 Fetching data..."):
        response, data = process_message(prompt, st.session_state.chat_messages[:-1])
    msg_data = {"role": "assistant", "content": response}
    if data and "table" in data: msg_data["table_data"] = data
    st.session_state.chat_messages.append(msg_data)

# ==================== MAIN ====================
def main():
    # Init state
    if 'chat_messages' not in st.session_state: st.session_state.chat_messages = []
    if 'market' not in st.session_state: st.session_state.market = 'US'
    if 'charts_to_display' not in st.session_state: st.session_state.charts_to_display = []
    
    # Header
    st.markdown('<div class="main-header"><h1>👩‍💼 Paula</h1><p style="color: #9ca3af;">Your AI Stock Analyst</p></div>', unsafe_allow_html=True)
    
    # Controls
    col1, col2, col3 = st.columns([2, 1, 0.5])
    with col1:
        st.markdown(f'<div class="market-badge">{"🇺🇸" if st.session_state.market == "US" else "🇮🇳"} <strong>{st.session_state.market} Market</strong></div>', unsafe_allow_html=True)
    with col2:
        market = st.selectbox("Market", ['US', 'India'], index=0 if st.session_state.market == 'US' else 1, label_visibility="collapsed")
        if market != st.session_state.market:
            st.session_state.market = market
            st.session_state.chat_messages = []
            st.session_state.charts_to_display = []
            st.rerun()
    with col3:
        if st.button("🔄", help="Refresh"): 
            st.cache_data.clear()
            st.rerun()
    
    st.markdown("---")
    
    # API check
    if not (st.secrets.get("GROQ_API_KEY") or os.environ.get("GROQ_API_KEY")):
        st.error("⚠️ Add GROQ_API_KEY to secrets")
        return
    
    # Chat history
    for m in st.session_state.chat_messages:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])
            if m.get("table_data"): display_table(m["table_data"])
    
    # Charts
    if st.session_state.charts_to_display: display_charts()
    
    # Welcome
    if not st.session_state.chat_messages:
        st.markdown("### 👋 Hi! I'm Paula. Ask me about any stock.")
        examples = ["Analyze TCS", "Compare RELIANCE INFY", "Find undervalued"] if st.session_state.market == 'India' else ["Analyze Apple", "Compare Tesla and Microsoft", "Find growth stocks"]
        cols = st.columns(len(examples))
        for i, ex in enumerate(examples):
            if cols[i].button(ex, key=f"ex_{i}", use_container_width=True):
                process_and_display(ex)
                st.rerun()
    
    st.markdown("---")
    
    # ==================== UNIFIED INPUT (Voice + Text) ====================
    
    # Check for voice input first (auto-sends)
    try:
        from streamlit_mic_recorder import speech_to_text
        has_voice = True
    except ImportError:
        has_voice = False
        voice_text = None
    
    # Layout: [Text Input] [Mic] [Send]
    col1, col2, col3 = st.columns([5, 0.7, 0.7])
    
    with col1:
        with st.form(key="chat_form", clear_on_submit=True):
            form_col1, form_col2 = st.columns([5, 1])
            with form_col1:
                text_input = st.text_input(
                    "Message Paula",
                    placeholder="Ask about any stock or click 🎤 to speak...",
                    key="unified_input",
                    label_visibility="collapsed"
                )
            with form_col2:
                submitted = st.form_submit_button("➤", use_container_width=True)
    
    with col2:
        if has_voice:
            voice_text = speech_to_text(
                language='en',
                start_prompt="🎤",
                stop_prompt="⏹️",
                just_once=True,
                use_container_width=True,
                key='voice_input'
            )
        else:
            st.button("🎤", disabled=True, help="pip install streamlit-mic-recorder", use_container_width=True)
    
    # Process text input
    if submitted and text_input:
        process_and_display(text_input)
        st.rerun()
    
    # Auto-send voice input immediately
    if has_voice and voice_text:
        process_and_display(voice_text)
        st.rerun()
    
    st.markdown('<div style="text-align:center;color:#6b7280;font-size:12px;margin-top:20px;">👩‍💼 Paula • Yahoo Finance • ⚠️ Educational only</div>', unsafe_allow_html=True)

if __name__ == "__main__":
    main()
