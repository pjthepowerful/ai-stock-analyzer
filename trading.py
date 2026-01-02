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
import streamlit.components.v1 as components

warnings.filterwarnings('ignore')
load_dotenv()

st.set_page_config(
    page_title="Paula - AI Stock Analyst",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# CSS
st.markdown("""
<style>
    .stApp { background: linear-gradient(180deg, #0a0f1a 0%, #111827 100%); }
    #MainMenu, footer, header {visibility: hidden;}
    h1, h2, h3 {color: #ffffff !important; font-weight: 700 !important;}
    p, span, div, label {color: #d1d5db !important;}
    .stChatMessage {
        background: rgba(255, 255, 255, 0.03) !important;
        border: 1px solid rgba(255, 255, 255, 0.08) !important;
        border-radius: 16px !important;
    }
    .stSelectbox > div > div {
        background: rgba(255, 255, 255, 0.08) !important;
        border: 1px solid rgba(255, 255, 255, 0.15) !important;
        border-radius: 10px !important;
    }
    .stButton > button {
        background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%) !important;
        color: white !important; border: none !important; border-radius: 10px !important;
    }
    hr {border-color: rgba(255, 255, 255, 0.1) !important;}
    .main-header {text-align: center; padding: 1rem 0;}
    .main-header h1 {
        font-size: 2.5rem !important;
        background: linear-gradient(135deg, #60a5fa 0%, #a78bfa 100%);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    }
    .market-badge {
        display: inline-flex; align-items: center; gap: 8px;
        background: rgba(255, 255, 255, 0.05);
        padding: 8px 16px; border-radius: 20px; font-size: 14px; color: #9ca3af;
    }
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
        if not info: return None
        
        current_price = info.get('regularMarketPrice') or info.get('currentPrice') or info.get('previousClose')
        if current_price is None:
            hist = stock.history(period='5d')
            if not hist.empty: current_price = hist['Close'].iloc[-1]
            else: return None
        
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
    except: return None

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
    
    if not data: return {"success": False, "error": f"Could not fetch data for {original}"}
    
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
    
    if any(w in msg for w in ['undervalued', 'value', 'cheap']): return screen_stocks("undervalued")
    if any(w in msg for w in ['growth', 'growing']): return screen_stocks("growth")
    if any(w in msg for w in ['dividend', 'yield', 'income']): return screen_stocks("dividend")
    if any(w in msg for w in ['compare', 'vs', 'versus']):
        tickers = re.findall(r'\b([A-Z]{2,6})\b', message.upper())
        tickers = [t for t in tickers if t not in ['PE', 'ROE', 'VS', 'AND', 'THE', 'FOR']]
        if len(tickers) >= 2: return compare_stocks(','.join(tickers))
    
    tickers = re.findall(r'\b([A-Z]{2,6})\b', message.upper())
    exclude = ['PE', 'ROE', 'VS', 'AND', 'THE', 'FOR', 'AI', 'OK', 'HI', 'RSI', 'MACD']
    
    for t in tickers:
        if t in US_STOCKS and t not in exclude: return analyze_stock(t)
    
    indian_names = [s.replace('.NS', '') for s in INDIAN_STOCKS]
    for t in tickers:
        if t in indian_names and t not in exclude: return analyze_stock(t)
    
    for t in tickers:
        if t not in exclude and len(t) >= 2: return analyze_stock(t)
    
    return None

def process_message(user_message, history):
    api_key = st.secrets.get("GROQ_API_KEY") or os.environ.get("GROQ_API_KEY")
    if not api_key: return "⚠️ Please add GROQ_API_KEY to Streamlit Secrets", None
    
    data = detect_and_execute(user_message)
    client = Groq(api_key=api_key)
    market = st.session_state.get('market', 'US')
    
    system = f"""You are Paula, a friendly stock analyst. Use ONLY the live data provided. 
Market: {market} | Time: {datetime.now().strftime("%Y-%m-%d %H:%M")}
End responses with: "⚠️ Educational only, not financial advice" """

    messages = [{"role": "system", "content": system}]
    for m in history[-4:]: messages.append({"role": m["role"], "content": m["content"]})
    
    if data:
        data_for_ai = {k: v for k, v in data.items() if k != 'table'}
        if 'table' in data: data_for_ai['top_stocks'] = [row.get('Ticker', '') for row in data['table'][:5]]
        prompt = f"Question: {user_message}\n\nLIVE DATA:\n{json.dumps(data_for_ai, indent=2, default=str)}"
    else:
        prompt = f"Question: {user_message}\n\nNo stock data found. Help user with a valid ticker."
    
    messages.append({"role": "user", "content": prompt})
    
    try:
        response = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=messages, max_tokens=1500, temperature=0.5)
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
    for ticker in charts[:3]:
        fig = create_technical_chart(ticker, period)
        if fig: st.plotly_chart(fig, use_container_width=True)

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
        examples = ["Analyze TCS", "Compare RELIANCE INFY", "Find undervalued"] if st.session_state.market == 'India' else ["Analyze AAPL", "Compare AAPL MSFT", "Find growth stocks"]
        cols = st.columns(len(examples))
        for i, ex in enumerate(examples):
            if cols[i].button(ex, key=f"ex_{i}", use_container_width=True):
                process_and_display(ex)
                st.rerun()
    
    st.markdown("---")
    
    # Voice input section (optional - for voice users)
    with st.expander("🎤 Voice Input (Chrome/Edge)", expanded=False):
        st.markdown("Click the button, speak, then copy the text to the chat input below.")
        components.html("""
            <div style="display: flex; align-items: center; gap: 10px;">
                <button id="mic" onclick="toggleMic()" style="
                    background: linear-gradient(135deg, #8b5cf6, #6366f1);
                    color: white; border: none; padding: 10px 20px;
                    border-radius: 20px; cursor: pointer; font-size: 14px;
                ">🎤 Click to Speak</button>
                <span id="status" style="color: #9ca3af;"></span>
            </div>
            <div id="result" style="margin-top: 10px; padding: 10px; background: rgba(139,92,246,0.1);
                border-radius: 8px; display: none;">
                <div style="color: #a78bfa; font-size: 11px;">HEARD (copy this):</div>
                <div id="text" style="color: white; font-size: 14px; user-select: all;"></div>
            </div>
            <script>
                const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
                let rec, on = false;
                if (SR) {
                    rec = new SR();
                    rec.continuous = true;
                    rec.interimResults = true;
                    rec.lang = 'en-US';
                    rec.onstart = () => {
                        on = true;
                        document.getElementById('mic').innerText = '🔴 Stop';
                        document.getElementById('mic').style.background = '#ef4444';
                        document.getElementById('status').innerText = 'Listening...';
                    };
                    rec.onend = () => {
                        on = false;
                        document.getElementById('mic').innerText = '🎤 Click to Speak';
                        document.getElementById('mic').style.background = 'linear-gradient(135deg, #8b5cf6, #6366f1)';
                        document.getElementById('status').innerText = '';
                    };
                    rec.onresult = (e) => {
                        let t = '';
                        for (let i = 0; i < e.results.length; i++) t += e.results[i][0].transcript;
                        document.getElementById('result').style.display = 'block';
                        document.getElementById('text').innerText = t;
                    };
                    rec.onerror = () => {
                        on = false;
                        document.getElementById('mic').innerText = '🎤 Click to Speak';
                        document.getElementById('mic').style.background = 'linear-gradient(135deg, #8b5cf6, #6366f1)';
                    };
                }
                function toggleMic() {
                    if (!rec) { alert('Use Chrome or Edge'); return; }
                    if (on) rec.stop(); else rec.start();
                }
            </script>
        """, height=120)
    
    # Main chat input - THIS WORKS RELIABLY
    if prompt := st.chat_input("Ask Paula anything..."):
        process_and_display(prompt)
        st.rerun()
    
    st.markdown('<div style="text-align:center;color:#6b7280;font-size:12px;margin-top:20px;">👩‍💼 Paula • Yahoo Finance • ⚠️ Educational only</div>', unsafe_allow_html=True)

if __name__ == "__main__":
    main()
