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

# Clean modern CSS for main app
MAIN_APP_CSS = """
<style>
    .stApp {
        background: linear-gradient(180deg, #0a0f1a 0%, #111827 100%);
    }
    
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    h1, h2, h3 {
        color: #ffffff !important;
        font-weight: 700 !important;
    }
    
    p, span, div, label {
        color: #d1d5db !important;
    }
    
    .stChatMessage {
        background: rgba(255, 255, 255, 0.03) !important;
        border: 1px solid rgba(255, 255, 255, 0.08) !important;
        border-radius: 16px !important;
        padding: 1.25rem !important;
        margin: 0.75rem 0 !important;
    }
    
    .stChatInput > div {
        background: rgba(255, 255, 255, 0.05) !important;
        border: 1px solid rgba(255, 255, 255, 0.1) !important;
        border-radius: 12px !important;
    }
    
    .stChatInput input {
        color: #ffffff !important;
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
        font-weight: 600 !important;
        padding: 0.5rem 1.5rem !important;
        transition: all 0.2s ease !important;
    }
    
    .stButton > button:hover {
        background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%) !important;
    }
    
    hr {
        border-color: rgba(255, 255, 255, 0.1) !important;
    }
    
    .main-header {
        text-align: center;
        padding: 1rem 0;
    }
    
    .main-header h1 {
        font-size: 2.5rem !important;
        background: linear-gradient(135deg, #60a5fa 0%, #a78bfa 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    
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
</style>
"""

# ==================== VOICE INPUT COMPONENT ====================

def create_voice_input_component():
    """Create the voice input HTML/JS component that types into Streamlit input"""
    voice_html = """
    <script>
    let recognition = null;
    let isListening = false;
    let finalTranscript = '';
    
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    
    if (SpeechRecognition) {
        recognition = new SpeechRecognition();
        recognition.continuous = true;
        recognition.interimResults = true;
        recognition.lang = 'en-US';
        
        recognition.onstart = function() {
            isListening = true;
            updateMicButton(true);
        };
        
        recognition.onend = function() {
            isListening = false;
            updateMicButton(false);
            
            if (finalTranscript.trim()) {
                fillChatInput(finalTranscript.trim());
            }
        };
        
        recognition.onresult = function(event) {
            let interimTranscript = '';
            
            for (let i = event.resultIndex; i < event.results.length; i++) {
                const transcript = event.results[i][0].transcript;
                if (event.results[i].isFinal) {
                    finalTranscript += transcript + ' ';
                } else {
                    interimTranscript += transcript;
                }
            }
            
            // Update input in real-time
            const display = finalTranscript + interimTranscript;
            if (display.trim()) {
                fillChatInput(display.trim());
            }
        };
        
        recognition.onerror = function(event) {
            console.error('Speech recognition error:', event.error);
            isListening = false;
            updateMicButton(false);
        };
    }
    
    function fillChatInput(text) {
        // Find the Streamlit chat input textarea
        const inputs = window.parent.document.querySelectorAll('textarea[data-testid="stChatInputTextArea"]');
        if (inputs.length > 0) {
            const input = inputs[0];
            const nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.parent.HTMLTextAreaElement.prototype, 'value').set;
            nativeInputValueSetter.call(input, text);
            const event = new Event('input', { bubbles: true });
            input.dispatchEvent(event);
            input.focus();
        }
    }
    
    function updateMicButton(listening) {
        const btn = window.parent.document.getElementById('voice-mic-btn');
        if (btn) {
            if (listening) {
                btn.style.background = '#ef4444';
                btn.innerHTML = '🔴';
            } else {
                btn.style.background = 'transparent';
                btn.innerHTML = '🎤';
            }
        }
    }
    
    window.toggleVoiceRecognition = function() {
        if (!recognition) {
            alert('Voice recognition not supported. Try Chrome or Edge.');
            return;
        }
        
        if (isListening) {
            recognition.stop();
        } else {
            finalTranscript = '';
            try {
                recognition.start();
            } catch (e) {
                console.error('Start error:', e);
            }
        }
    };
    </script>
    """
    return voice_html


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
    'ZOMATO.NS', 'IRCTC.NS', 'HAL.NS', 'BEL.NS', 'TATAPOWER.NS'
]

# ==================== HELPER FUNCTIONS ====================

def get_stock_list():
    return INDIAN_STOCKS if st.session_state.get('market') == 'India' else US_STOCKS

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

# ==================== TECHNICAL INDICATORS ====================

def calculate_rsi(data, period=14):
    delta = data['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def calculate_macd(data, fast=12, slow=26, signal=9):
    exp1 = data['Close'].ewm(span=fast, adjust=False).mean()
    exp2 = data['Close'].ewm(span=slow, adjust=False).mean()
    macd = exp1 - exp2
    signal_line = macd.ewm(span=signal, adjust=False).mean()
    histogram = macd - signal_line
    return macd, signal_line, histogram

def calculate_bollinger_bands(data, period=20, std_dev=2):
    sma = data['Close'].rolling(window=period).mean()
    std = data['Close'].rolling(window=period).std()
    upper_band = sma + (std * std_dev)
    lower_band = sma - (std * std_dev)
    return upper_band, sma, lower_band

# ==================== CHART FUNCTION ====================

def create_technical_chart(ticker, period="6mo"):
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period=period)
        
        if hist.empty or len(hist) < 30:
            return None
        
        display_name = get_display_ticker(ticker)
        
        hist['RSI'] = calculate_rsi(hist)
        hist['MACD'], hist['Signal'], hist['MACD_Hist'] = calculate_macd(hist)
        hist['BB_Upper'], hist['BB_Middle'], hist['BB_Lower'] = calculate_bollinger_bands(hist)
        hist['MA20'] = hist['Close'].rolling(window=20).mean()
        hist['MA50'] = hist['Close'].rolling(window=50).mean()
        
        fig = make_subplots(
            rows=4, cols=1, shared_xaxes=True, vertical_spacing=0.03,
            row_heights=[0.45, 0.18, 0.18, 0.19],
            subplot_titles=(f'{display_name} Price', 'Volume', 'RSI (14)', 'MACD')
        )
        
        # Bollinger Bands
        fig.add_trace(go.Scatter(x=hist.index, y=hist['BB_Upper'], name='BB Upper',
                                line=dict(color='rgba(128,128,128,0.3)', width=1), showlegend=False), row=1, col=1)
        fig.add_trace(go.Scatter(x=hist.index, y=hist['BB_Lower'], name='BB Lower',
                                line=dict(color='rgba(128,128,128,0.3)', width=1),
                                fill='tonexty', fillcolor='rgba(128,128,128,0.1)', showlegend=False), row=1, col=1)
        
        # Candlestick
        fig.add_trace(go.Candlestick(x=hist.index, open=hist['Open'], high=hist['High'],
                                     low=hist['Low'], close=hist['Close'], name='Price',
                                     increasing_line_color='#10b981', decreasing_line_color='#ef4444'), row=1, col=1)
        
        # MAs
        fig.add_trace(go.Scatter(x=hist.index, y=hist['MA20'], name='MA 20',
                                line=dict(color='#f59e0b', width=1.5)), row=1, col=1)
        fig.add_trace(go.Scatter(x=hist.index, y=hist['MA50'], name='MA 50',
                                line=dict(color='#8b5cf6', width=1.5)), row=1, col=1)
        
        # Volume
        colors = ['#10b981' if hist['Close'].iloc[i] >= hist['Open'].iloc[i] else '#ef4444' for i in range(len(hist))]
        fig.add_trace(go.Bar(x=hist.index, y=hist['Volume'], name='Volume',
                            marker_color=colors, opacity=0.7, showlegend=False), row=2, col=1)
        
        # RSI
        fig.add_trace(go.Scatter(x=hist.index, y=hist['RSI'], name='RSI',
                                line=dict(color='#06b6d4', width=1.5)), row=3, col=1)
        fig.add_hline(y=70, line_dash="dash", line_color="rgba(239,68,68,0.5)", row=3, col=1)
        fig.add_hline(y=30, line_dash="dash", line_color="rgba(16,185,129,0.5)", row=3, col=1)
        fig.add_hrect(y0=70, y1=100, fillcolor="rgba(239,68,68,0.1)", line_width=0, row=3, col=1)
        fig.add_hrect(y0=0, y1=30, fillcolor="rgba(16,185,129,0.1)", line_width=0, row=3, col=1)
        
        # MACD
        fig.add_trace(go.Scatter(x=hist.index, y=hist['MACD'], name='MACD',
                                line=dict(color='#3b82f6', width=1.5)), row=4, col=1)
        fig.add_trace(go.Scatter(x=hist.index, y=hist['Signal'], name='Signal',
                                line=dict(color='#f59e0b', width=1.5)), row=4, col=1)
        macd_colors = ['#10b981' if val >= 0 else '#ef4444' for val in hist['MACD_Hist']]
        fig.add_trace(go.Bar(x=hist.index, y=hist['MACD_Hist'], name='MACD Hist',
                            marker_color=macd_colors, opacity=0.6, showlegend=False), row=4, col=1)
        fig.add_hline(y=0, line_dash="solid", line_color="rgba(255,255,255,0.2)", row=4, col=1)
        
        fig.update_layout(
            template='plotly_dark', paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
            height=700, margin=dict(l=60, r=30, t=40, b=30),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(size=10)),
            font=dict(color='#9ca3af'), xaxis_rangeslider_visible=False
        )
        
        for i in range(1, 5):
            fig.update_xaxes(gridcolor='rgba(255,255,255,0.05)', showgrid=True, row=i, col=1)
            fig.update_yaxes(gridcolor='rgba(255,255,255,0.05)', showgrid=True, row=i, col=1)
        
        fig.update_yaxes(range=[0, 100], row=3, col=1)
        
        for annotation in fig['layout']['annotations']:
            annotation['font'] = dict(color='#9ca3af', size=12)
        
        return fig
    except Exception as e:
        return None

# ==================== LIVE DATA ====================

@st.cache_data(ttl=120)
def get_live_stock_data(ticker):
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        
        if not info:
            return None
        
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
            "ticker": ticker, "display_ticker": get_display_ticker(ticker),
            "name": info.get('longName') or info.get('shortName') or get_display_ticker(ticker),
            "price": round(current_price, 2), "price_fmt": format_price(current_price, market),
            "change": round(change, 2), "change_pct": round(change_pct, 2),
            "prev_close": round(prev_close, 2) if prev_close else None,
            "market_cap": info.get('marketCap'), "market_cap_fmt": format_market_cap(info.get('marketCap'), market),
            "pe_ratio": info.get('trailingPE'), "forward_pe": info.get('forwardPE'),
            "peg_ratio": info.get('pegRatio'), "price_to_book": info.get('priceToBook'),
            "roe": info.get('returnOnEquity'), "profit_margin": info.get('profitMargins'),
            "operating_margin": info.get('operatingMargins'), "debt_to_equity": info.get('debtToEquity'),
            "current_ratio": info.get('currentRatio'), "dividend_yield": info.get('dividendYield'),
            "52_week_high": info.get('fiftyTwoWeekHigh'), "52_week_low": info.get('fiftyTwoWeekLow'),
            "sector": info.get('sector', 'N/A'), "industry": info.get('industry', 'N/A'), "market": market,
        }
    except:
        return None

# ==================== ANALYSIS FUNCTIONS ====================

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
        return {"success": False, "error": f"Could not fetch data for {original}"}
    
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
        "success": True, "source": "Yahoo Finance (Live)",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "ticker": data['display_ticker'], "name": data['name'],
        "sector": data['sector'], "industry": data['industry'],
        "price": f"{currency}{data['price']:,.2f}",
        "change": f"{data['change']:+.2f} ({data['change_pct']:+.2f}%)",
        "market_cap": data['market_cap_fmt'],
        "pe_ratio": round(data['pe_ratio'], 2) if data['pe_ratio'] else "N/A",
        "roe": f"{data['roe']*100:.1f}%" if data['roe'] else "N/A",
        "profit_margin": f"{data['profit_margin']*100:.1f}%" if data['profit_margin'] else "N/A",
        "dividend_yield": f"{data['dividend_yield']*100:.2f}%" if data['dividend_yield'] else "N/A",
        "rating": f"{emoji} {rating} ({score}/8)"
    }

def compare_stocks(tickers_str):
    tickers = [t.strip().upper().replace('.NS', '').replace('.BO', '') for t in re.split(r'[,\s]+', tickers_str) if t.strip()]
    
    results = []
    full_tickers = []
    market = st.session_state.get('market', 'US')
    
    for ticker in tickers[:5]:
        full_ticker = f"{ticker}.NS" if market == 'India' else ticker
        data = get_live_stock_data(full_ticker)
        
        if not data:
            alt = ticker if market == 'India' else f"{ticker}.NS"
            data = get_live_stock_data(alt)
            full_ticker = alt
        
        if data:
            full_tickers.append(full_ticker)
            currency = '₹' if data['market'] == 'India' else '$'
            change_color = "🟢" if data['change_pct'] >= 0 else "🔴"
            
            results.append({
                "Ticker": data['display_ticker'],
                "Price": f"{currency}{data['price']:,.2f}",
                "Change": f"{change_color} {data['change_pct']:+.2f}%",
                "Market Cap": data['market_cap_fmt'],
                "P/E": round(data['pe_ratio'], 1) if data['pe_ratio'] else "N/A",
                "ROE": f"{data['roe']*100:.0f}%" if data['roe'] else "N/A",
                "Sector": data['sector'][:15] if data['sector'] else "N/A"
            })
    
    st.session_state.charts_to_display = full_tickers
    
    return {"success": True, "source": "Yahoo Finance (Live)",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "count": len(results), "table": results}

def screen_stocks(screen_type):
    results = []
    stocks = get_stock_list()
    market = st.session_state.get('market', 'US')
    
    progress = st.progress(0)
    status = st.empty()
    found_tickers = []
    
    for i, ticker in enumerate(stocks):
        progress.progress((i + 1) / len(stocks))
        status.text(f"Scanning {get_display_ticker(ticker)}...")
        
        data = get_live_stock_data(ticker)
        if not data:
            continue
        
        currency = '₹' if data['market'] == 'India' else '$'
        
        if screen_type == "undervalued":
            if data['pe_ratio'] and 0 < data['pe_ratio'] < 20 and data['roe'] and data['roe'] > 0.12:
                found_tickers.append(ticker)
                results.append({"Ticker": data['display_ticker'], "Name": data['name'][:20],
                              "Price": f"{currency}{data['price']:,.2f}", "P/E": round(data['pe_ratio'], 1),
                              "ROE": f"{data['roe']*100:.0f}%", "Sector": data['sector'][:12] if data['sector'] else "N/A"})
        
        elif screen_type == "growth":
            if data['roe'] and data['roe'] > 0.15 and data['profit_margin'] and data['profit_margin'] > 0.10:
                found_tickers.append(ticker)
                results.append({"Ticker": data['display_ticker'], "Name": data['name'][:20],
                              "Price": f"{currency}{data['price']:,.2f}", "ROE": f"{data['roe']*100:.0f}%",
                              "Margin": f"{data['profit_margin']*100:.0f}%", "Sector": data['sector'][:12] if data['sector'] else "N/A"})
        
        elif screen_type == "dividend":
            if data['dividend_yield'] and data['dividend_yield'] > 0.02:
                found_tickers.append(ticker)
                results.append({"Ticker": data['display_ticker'], "Name": data['name'][:20],
                              "Price": f"{currency}{data['price']:,.2f}", "Yield": f"{data['dividend_yield']*100:.2f}%",
                              "P/E": round(data['pe_ratio'], 1) if data['pe_ratio'] else "N/A",
                              "Sector": data['sector'][:12] if data['sector'] else "N/A"})
    
    progress.empty()
    status.empty()
    
    st.session_state.charts_to_display = found_tickers[:3]
    
    criteria = {"undervalued": "P/E < 20, ROE > 12%", "growth": "ROE > 15%, Margin > 10%", "dividend": "Yield > 2%"}
    
    if results:
        return {"success": True, "source": "Yahoo Finance (Live)", "market": market,
                "screen_type": screen_type.title(), "criteria": criteria.get(screen_type, ""),
                "found": len(results), "table": results[:15]}
    return {"success": False, "message": f"No {screen_type} stocks found"}

# ==================== DISPLAY FUNCTIONS ====================

def display_table(data):
    if "table" in data and data["table"]:
        df = pd.DataFrame(data["table"])
        st.dataframe(df, use_container_width=True, hide_index=True)

def display_charts():
    charts = st.session_state.get('charts_to_display', [])
    if not charts:
        return
    
    st.markdown("### 📈 Technical Analysis Charts")
    period = st.selectbox("Time Period", ["1mo", "3mo", "6mo", "1y", "2y"], index=2, key="chart_period")
    st.caption("📊 Showing: Price + Bollinger Bands, Volume, RSI, MACD")
    
    for ticker in charts[:3]:
        fig = create_technical_chart(ticker, period)
        if fig:
            st.plotly_chart(fig, use_container_width=True)
            st.markdown("---")

# ==================== AI CHAT ====================

def detect_and_execute(message):
    msg = message.lower()
    
    if any(w in msg for w in ['undervalued', 'value', 'cheap', 'low pe', 'bargain']):
        return screen_stocks("undervalued")
    if any(w in msg for w in ['growth', 'growing', 'high growth']):
        return screen_stocks("growth")
    if any(w in msg for w in ['dividend', 'yield', 'income']):
        return screen_stocks("dividend")
    if any(w in msg for w in ['compare', 'vs', 'versus']):
        tickers = re.findall(r'\b([A-Z]{2,6})\b', message.upper())
        exclude = ['PE', 'ROE', 'VS', 'AND', 'THE', 'FOR']
        tickers = [t for t in tickers if t not in exclude]
        if len(tickers) >= 2:
            return compare_stocks(','.join(tickers))
    
    tickers = re.findall(r'\b([A-Z]{2,6})\b', message.upper())
    exclude = ['PE', 'ROE', 'VS', 'AND', 'THE', 'FOR', 'AI', 'OK', 'HI', 'RSI', 'MACD']
    
    for t in tickers:
        if t in US_STOCKS and t not in exclude:
            return analyze_stock(t)
    
    indian_names = [s.replace('.NS', '') for s in INDIAN_STOCKS]
    for t in tickers:
        if t in indian_names and t not in exclude:
            return analyze_stock(t)
    
    if any(w in msg for w in ['analyze', 'check', 'tell me', 'price', 'chart', 'show']):
        for t in tickers:
            if t not in exclude and len(t) >= 2:
                return analyze_stock(t)
    
    return None

def process_message(user_message, history):
    api_key = st.secrets.get("GROQ_API_KEY") or os.environ.get("GROQ_API_KEY")
    if not api_key:
        return "⚠️ Please add GROQ_API_KEY to Streamlit Secrets", None
    
    data = detect_and_execute(user_message)
    client = Groq(api_key=api_key)
    market = st.session_state.get('market', 'US')
    currency = '₹' if market == 'India' else '$'
    
    system = f"""You are Paula, a friendly and professional stock analyst.

RULES:
1. ONLY use data provided - it's LIVE from Yahoo Finance
2. NEVER use training data for prices
3. Be friendly but professional
4. Technical charts are shown separately

Market: {market} | Currency: {currency}
Time: {datetime.now().strftime("%Y-%m-%d %H:%M")}

End with: "⚠️ Educational only, not financial advice" """

    messages = [{"role": "system", "content": system}]
    for m in history[-4:]:
        messages.append({"role": m["role"], "content": m["content"]})
    
    if data:
        data_for_ai = {k: v for k, v in data.items() if k != 'table'}
        if 'table' in data:
            data_for_ai['stocks_found'] = len(data['table'])
            data_for_ai['top_stocks'] = [row.get('Ticker', '') for row in data['table'][:5]]
        prompt = f"Question: {user_message}\n\nLIVE DATA:\n{json.dumps(data_for_ai, indent=2, default=str)}"
    else:
        prompt = f"Question: {user_message}\n\nNo data fetched. Ask for a valid ticker."
    
    messages.append({"role": "user", "content": prompt})
    
    try:
        response = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=messages, max_tokens=1500, temperature=0.5)
        return response.choices[0].message.content, data
    except Exception as e:
        return f"Error: {e}", None

# ==================== MAIN APP ====================

def main():
    """Display the main Paula app"""
    st.markdown(MAIN_APP_CSS, unsafe_allow_html=True)
    
    # Add custom CSS for mic button styling
    st.markdown("""
    <style>
        /* Style the mic button container */
        .mic-button-container {
            position: fixed;
            bottom: 24px;
            right: 100px;
            z-index: 1000;
        }
        
        .mic-btn {
            background: transparent;
            border: none;
            font-size: 20px;
            cursor: pointer;
            padding: 8px;
            border-radius: 50%;
            transition: all 0.2s ease;
        }
        
        .mic-btn:hover {
            background: rgba(255, 255, 255, 0.1);
        }
        
        .mic-btn.listening {
            background: rgba(239, 68, 68, 0.2);
            animation: pulse 1s infinite;
        }
        
        @keyframes pulse {
            0%, 100% { opacity: 1; transform: scale(1); }
            50% { opacity: 0.7; transform: scale(1.1); }
        }
    </style>
    """, unsafe_allow_html=True)
    
    # Initialize session state
    if 'chat_messages' not in st.session_state:
        st.session_state.chat_messages = []
    if 'market' not in st.session_state:
        st.session_state.market = 'US'
    if 'charts_to_display' not in st.session_state:
        st.session_state.charts_to_display = []
    
    # Header
    st.markdown("""
    <div class="main-header">
        <h1>👩‍💼 Paula</h1>
        <p style="color: #9ca3af;">Your AI Stock Analyst</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Controls
    col1, col2, col3 = st.columns([2, 1, 0.5])
    
    with col1:
        market_emoji = "🇺🇸" if st.session_state.market == 'US' else "🇮🇳"
        st.markdown(f"""
        <div class="market-badge">{market_emoji} <strong>{st.session_state.market} Market</strong></div>
        """, unsafe_allow_html=True)
    
    with col2:
        market = st.selectbox("Market", ['US', 'India'],
                             index=0 if st.session_state.market == 'US' else 1,
                             label_visibility="collapsed")
        if market != st.session_state.market:
            st.session_state.market = market
            st.session_state.chat_messages = []
            st.session_state.charts_to_display = []
            st.cache_data.clear()
            st.rerun()
    
    with col3:
        if st.button("🔄", use_container_width=True, help="Refresh"):
            st.cache_data.clear()
            st.rerun()
    
    st.markdown("---")
    
    # Check GROQ API key
    api_key = st.secrets.get("GROQ_API_KEY") or os.environ.get("GROQ_API_KEY")
    if not api_key:
        st.error("⚠️ Add GROQ_API_KEY to Streamlit Secrets")
        return
    
    # Chat messages
    for m in st.session_state.chat_messages:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])
            if m.get("table_data"):
                display_table(m["table_data"])
    
    # Charts
    if st.session_state.charts_to_display:
        display_charts()
    
    # Welcome
    if not st.session_state.chat_messages:
        st.markdown("### 👋 Hi! I'm Paula. Ask me about any stock.")
        st.markdown("**Try these examples:** *(or click 🎤 to speak)*")
        
        examples = ["Analyze TCS", "Compare RELIANCE INFY", "Find undervalued", "Show dividends"] if st.session_state.market == 'India' else ["Analyze AAPL", "Compare AAPL MSFT", "Find growth stocks", "Show dividends"]
        
        cols = st.columns(len(examples))
        for i, ex in enumerate(examples):
            with cols[i]:
                if st.button(ex, key=f"ex_{i}", use_container_width=True):
                    st.session_state.chat_messages.append({"role": "user", "content": ex})
                    st.rerun()
    
    # Inject voice recognition script (hidden)
    components.html(create_voice_input_component(), height=0)
    
    # Add mic button that floats near the chat input
    st.markdown("""
    <div class="mic-button-container">
        <button id="voice-mic-btn" class="mic-btn" onclick="window.parent.toggleVoiceRecognition ? window.parent.toggleVoiceRecognition() : (window.frames[0] && window.frames[0].toggleVoiceRecognition ? window.frames[0].toggleVoiceRecognition() : alert('Voice not ready'))" title="Click to speak">
            🎤
        </button>
    </div>
    
    <script>
    // Make toggleVoiceRecognition available globally
    document.addEventListener('DOMContentLoaded', function() {
        // Find the iframe with our voice script and expose the function
        const iframes = document.querySelectorAll('iframe');
        iframes.forEach(iframe => {
            try {
                if (iframe.contentWindow && iframe.contentWindow.toggleVoiceRecognition) {
                    window.toggleVoiceRecognition = iframe.contentWindow.toggleVoiceRecognition;
                }
            } catch(e) {}
        });
    });
    </script>
    """, unsafe_allow_html=True)
    
    # Chat input
    if prompt := st.chat_input("Ask Paula about stocks... (or click 🎤 to speak)"):
        st.session_state.chat_messages.append({"role": "user", "content": prompt})
        
        with st.chat_message("user"):
            st.markdown(prompt)
        
        with st.chat_message("assistant"):
            with st.spinner("📡 Fetching live data..."):
                response, data = process_message(prompt, st.session_state.chat_messages[:-1])
            st.markdown(response)
            if data and "table" in data:
                display_table(data)
        
        msg_data = {"role": "assistant", "content": response}
        if data and "table" in data:
            msg_data["table_data"] = data
        st.session_state.chat_messages.append(msg_data)
        st.rerun()
    
    # Footer
    st.markdown("---")
    st.markdown("""
    <div style="text-align: center; color: #6b7280; font-size: 12px;">
        👩‍💼 Paula • Live data from Yahoo Finance • 🎤 Voice input supported • ⚠️ Educational only
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
