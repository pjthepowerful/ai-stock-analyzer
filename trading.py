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
    page_title="AI Stock Analyzer",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Clean modern CSS
st.markdown("""
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
        transform: translateY(-1px) !important;
        box-shadow: 0 4px 12px rgba(37, 99, 235, 0.4) !important;
    }
    
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background: transparent;
    }
    
    .stTabs [data-baseweb="tab"] {
        background: rgba(255, 255, 255, 0.05);
        border-radius: 8px;
        color: #9ca3af;
        padding: 8px 16px;
    }
    
    .stTabs [aria-selected="true"] {
        background: rgba(37, 99, 235, 0.3) !important;
        color: #ffffff !important;
    }
    
    hr {
        border-color: rgba(255, 255, 255, 0.1) !important;
        margin: 1.5rem 0 !important;
    }
    
    .main-header {
        text-align: center;
        padding: 1.5rem 0 1rem 0;
    }
    
    .main-header h1 {
        font-size: 2.5rem !important;
        margin-bottom: 0.5rem !important;
        background: linear-gradient(135deg, #60a5fa 0%, #a78bfa 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
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
    
    .metric-card {
        background: rgba(255, 255, 255, 0.03);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 12px;
        padding: 1rem;
        text-align: center;
    }
    
    .metric-value {
        font-size: 1.5rem;
        font-weight: 700;
        color: #ffffff;
    }
    
    .metric-label {
        font-size: 0.8rem;
        color: #9ca3af;
        margin-top: 4px;
    }
    
    .positive { color: #10b981 !important; }
    .negative { color: #ef4444 !important; }
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
    'ZOMATO.NS', 'IRCTC.NS', 'HAL.NS', 'BEL.NS', 'TATAPOWER.NS'
]

# Session state
if 'chat_messages' not in st.session_state:
    st.session_state.chat_messages = []
if 'market' not in st.session_state:
    st.session_state.market = 'US'
if 'current_chart_data' not in st.session_state:
    st.session_state.current_chart_data = None

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

# ==================== CHART FUNCTIONS ====================

def create_price_chart(ticker, period="6mo"):
    """Create an interactive price chart with volume"""
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period=period)
        
        if hist.empty:
            return None
        
        # Create figure with secondary y-axis
        fig = make_subplots(
            rows=2, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.03,
            row_heights=[0.7, 0.3]
        )
        
        # Candlestick chart
        fig.add_trace(
            go.Candlestick(
                x=hist.index,
                open=hist['Open'],
                high=hist['High'],
                low=hist['Low'],
                close=hist['Close'],
                name='Price',
                increasing_line_color='#10b981',
                decreasing_line_color='#ef4444'
            ),
            row=1, col=1
        )
        
        # Add moving averages
        if len(hist) >= 20:
            hist['MA20'] = hist['Close'].rolling(window=20).mean()
            fig.add_trace(
                go.Scatter(
                    x=hist.index,
                    y=hist['MA20'],
                    name='20 MA',
                    line=dict(color='#f59e0b', width=1)
                ),
                row=1, col=1
            )
        
        if len(hist) >= 50:
            hist['MA50'] = hist['Close'].rolling(window=50).mean()
            fig.add_trace(
                go.Scatter(
                    x=hist.index,
                    y=hist['MA50'],
                    name='50 MA',
                    line=dict(color='#8b5cf6', width=1)
                ),
                row=1, col=1
            )
        
        # Volume bars
        colors = ['#10b981' if hist['Close'].iloc[i] >= hist['Open'].iloc[i] 
                  else '#ef4444' for i in range(len(hist))]
        
        fig.add_trace(
            go.Bar(
                x=hist.index,
                y=hist['Volume'],
                name='Volume',
                marker_color=colors,
                opacity=0.7
            ),
            row=2, col=1
        )
        
        # Update layout
        fig.update_layout(
            title=f"{get_display_ticker(ticker)} - Price Chart",
            template='plotly_dark',
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            xaxis_rangeslider_visible=False,
            height=500,
            margin=dict(l=50, r=50, t=50, b=50),
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            ),
            font=dict(color='#9ca3af')
        )
        
        fig.update_xaxes(
            gridcolor='rgba(255,255,255,0.05)',
            showgrid=True
        )
        fig.update_yaxes(
            gridcolor='rgba(255,255,255,0.05)',
            showgrid=True
        )
        
        return fig
    except Exception as e:
        return None


def create_comparison_chart(tickers):
    """Create a comparison chart for multiple stocks"""
    try:
        fig = go.Figure()
        
        for ticker in tickers:
            stock = yf.Ticker(ticker)
            hist = stock.history(period="6mo")
            
            if not hist.empty:
                # Normalize to percentage change from first day
                normalized = (hist['Close'] / hist['Close'].iloc[0] - 1) * 100
                
                fig.add_trace(
                    go.Scatter(
                        x=hist.index,
                        y=normalized,
                        name=get_display_ticker(ticker),
                        mode='lines',
                        line=dict(width=2)
                    )
                )
        
        fig.update_layout(
            title="6-Month Performance Comparison (%)",
            template='plotly_dark',
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            height=400,
            margin=dict(l=50, r=50, t=50, b=50),
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            ),
            font=dict(color='#9ca3af'),
            yaxis_title="% Change",
            hovermode='x unified'
        )
        
        fig.update_xaxes(gridcolor='rgba(255,255,255,0.05)')
        fig.update_yaxes(gridcolor='rgba(255,255,255,0.05)')
        
        # Add zero line
        fig.add_hline(y=0, line_dash="dash", line_color="rgba(255,255,255,0.3)")
        
        return fig
    except Exception as e:
        return None


def create_metrics_chart(data):
    """Create a radar chart for stock metrics"""
    try:
        categories = ['Valuation', 'Profitability', 'Health', 'Growth', 'Dividend']
        
        # Calculate scores (0-100 scale)
        val_score = 50
        if data.get('pe_ratio') and data['pe_ratio'] > 0:
            val_score = max(0, min(100, 100 - (data['pe_ratio'] * 2)))
        
        prof_score = 50
        if data.get('roe') and data['roe'] > 0:
            prof_score = min(100, data['roe'] * 100 * 3)
        
        health_score = 50
        if data.get('current_ratio'):
            health_score = min(100, data['current_ratio'] * 40)
        
        growth_score = 50
        if data.get('profit_margin') and data['profit_margin'] > 0:
            growth_score = min(100, data['profit_margin'] * 100 * 3)
        
        div_score = 30
        if data.get('dividend_yield') and data['dividend_yield'] > 0:
            div_score = min(100, data['dividend_yield'] * 100 * 15)
        
        values = [val_score, prof_score, health_score, growth_score, div_score]
        
        fig = go.Figure()
        
        fig.add_trace(go.Scatterpolar(
            r=values + [values[0]],  # Close the polygon
            theta=categories + [categories[0]],
            fill='toself',
            fillcolor='rgba(59, 130, 246, 0.3)',
            line=dict(color='#3b82f6', width=2),
            name='Score'
        ))
        
        fig.update_layout(
            polar=dict(
                radialaxis=dict(
                    visible=True,
                    range=[0, 100],
                    gridcolor='rgba(255,255,255,0.1)',
                    linecolor='rgba(255,255,255,0.1)'
                ),
                angularaxis=dict(
                    gridcolor='rgba(255,255,255,0.1)',
                    linecolor='rgba(255,255,255,0.1)'
                ),
                bgcolor='rgba(0,0,0,0)'
            ),
            template='plotly_dark',
            paper_bgcolor='rgba(0,0,0,0)',
            height=350,
            margin=dict(l=80, r=80, t=30, b=30),
            font=dict(color='#9ca3af'),
            showlegend=False
        )
        
        return fig
    except Exception as e:
        return None


def create_sector_pie_chart(stocks_data):
    """Create a pie chart showing sector distribution"""
    try:
        sectors = {}
        for stock in stocks_data:
            sector = stock.get('sector', 'Other')
            sectors[sector] = sectors.get(sector, 0) + 1
        
        fig = go.Figure(data=[go.Pie(
            labels=list(sectors.keys()),
            values=list(sectors.values()),
            hole=.4,
            marker_colors=['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', 
                          '#06b6d4', '#ec4899', '#84cc16', '#f97316', '#6366f1']
        )])
        
        fig.update_layout(
            title="Sector Distribution",
            template='plotly_dark',
            paper_bgcolor='rgba(0,0,0,0)',
            height=350,
            margin=dict(l=30, r=30, t=50, b=30),
            font=dict(color='#9ca3af'),
            showlegend=True,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=-0.2,
                xanchor="center",
                x=0.5
            )
        )
        
        return fig
    except Exception as e:
        return None

# ==================== LIVE DATA ====================

@st.cache_data(ttl=120)
def get_live_stock_data(ticker):
    """Get LIVE stock data from Yahoo Finance"""
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

# ==================== ANALYSIS WITH CHARTS ====================

def analyze_stock_with_chart(ticker):
    """Analyze stock and prepare chart data"""
    original = ticker.upper().strip().replace('.NS', '').replace('.BO', '')
    market = st.session_state.market
    
    full_ticker = f"{original}.NS" if market == 'India' else original
    data = get_live_stock_data(full_ticker)
    
    if not data:
        alt_ticker = original if market == 'India' else f"{original}.NS"
        data = get_live_stock_data(alt_ticker)
        full_ticker = alt_ticker
    
    if not data:
        return {"success": False, "error": f"Could not fetch data for {original}"}
    
    # Store chart data in session state
    st.session_state.current_chart_data = {
        "type": "single",
        "ticker": full_ticker,
        "data": data
    }
    
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
        "show_chart": True,
        "source": "Yahoo Finance (Live)",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "company": {
            "ticker": data['display_ticker'],
            "name": data['name'],
            "sector": data['sector'],
            "industry": data['industry']
        },
        "price": {
            "current": f"{currency}{data['price']:,.2f}",
            "change": f"{data['change']:+.2f}",
            "change_pct": f"{data['change_pct']:+.2f}%",
            "market_cap": data['market_cap_fmt'],
            "52w_high": f"{currency}{data['52_week_high']:,.2f}" if data['52_week_high'] else "N/A",
            "52w_low": f"{currency}{data['52_week_low']:,.2f}" if data['52_week_low'] else "N/A"
        },
        "metrics": {
            "pe": round(data['pe_ratio'], 2) if data['pe_ratio'] else "N/A",
            "peg": round(data['peg_ratio'], 2) if data['peg_ratio'] else "N/A",
            "roe": f"{data['roe']*100:.1f}%" if data['roe'] else "N/A",
            "margin": f"{data['profit_margin']*100:.1f}%" if data['profit_margin'] else "N/A",
            "debt_equity": round(data['debt_to_equity'], 1) if data['debt_to_equity'] else "N/A",
            "div_yield": f"{data['dividend_yield']*100:.2f}%" if data['dividend_yield'] else "N/A"
        },
        "rating": {
            "score": f"{total}/12",
            "pct": round(pct, 1),
            "verdict": rating,
            "emoji": emoji
        }
    }


def compare_stocks_with_chart(tickers_str):
    """Compare stocks with chart"""
    tickers = [t.strip().upper().replace('.NS', '').replace('.BO', '') for t in re.split(r'[,\s]+', tickers_str) if t.strip()]
    
    results = []
    full_tickers = []
    market = st.session_state.market
    
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
            results.append({
                "ticker": data['display_ticker'],
                "name": data['name'][:25] + "..." if len(data['name']) > 25 else data['name'],
                "price": f"{currency}{data['price']:,.2f}",
                "change": f"{data['change_pct']:+.2f}%",
                "market_cap": data['market_cap_fmt'],
                "pe": round(data['pe_ratio'], 1) if data['pe_ratio'] else "N/A",
                "roe": f"{data['roe']*100:.0f}%" if data['roe'] else "N/A",
                "sector": data['sector']
            })
    
    # Store chart data
    st.session_state.current_chart_data = {
        "type": "comparison",
        "tickers": full_tickers
    }
    
    return {
        "success": True,
        "show_chart": True,
        "source": "Yahoo Finance (Live)",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "count": len(results),
        "stocks": results
    }


def screen_stocks_with_chart(screen_type):
    """Screen stocks with chart"""
    results = []
    stocks = get_stock_list()
    market = st.session_state.market
    
    progress = st.progress(0)
    status = st.empty()
    
    stocks_data = []
    
    for i, ticker in enumerate(stocks):
        progress.progress((i + 1) / len(stocks))
        status.text(f"Scanning {get_display_ticker(ticker)}...")
        
        data = get_live_stock_data(ticker)
        if not data:
            continue
        
        currency = '₹' if data['market'] == 'India' else '$'
        
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
                    stocks_data.append(data)
        
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
                    stocks_data.append(data)
        
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
                stocks_data.append(data)
    
    progress.empty()
    status.empty()
    
    # Store chart data for sector pie
    if stocks_data:
        st.session_state.current_chart_data = {
            "type": "screener",
            "stocks": stocks_data
        }
    
    criteria_map = {
        "undervalued": "PE < 20, ROE > 12%",
        "growth": "ROE > 15%, Margin > 10%",
        "dividend": "Yield > 2%"
    }
    
    if results:
        return {
            "success": True,
            "show_chart": True,
            "source": "Yahoo Finance (Live)",
            "market": market,
            "screen": screen_type,
            "criteria": criteria_map.get(screen_type, ""),
            "found": len(results),
            "stocks": results[:15]
        }
    return {"success": False, "message": f"No {screen_type} stocks found"}


# ==================== DISPLAY CHARTS ====================

def display_charts():
    """Display charts based on current data"""
    chart_data = st.session_state.current_chart_data
    
    if not chart_data:
        return
    
    st.markdown("---")
    
    if chart_data["type"] == "single":
        ticker = chart_data["ticker"]
        data = chart_data["data"]
        
        # Create tabs for different charts
        tab1, tab2 = st.tabs(["📈 Price Chart", "📊 Metrics"])
        
        with tab1:
            # Time period selector
            col1, col2 = st.columns([3, 1])
            with col2:
                period = st.selectbox(
                    "Period",
                    ["1mo", "3mo", "6mo", "1y", "2y"],
                    index=2,
                    key="period_select"
                )
            
            price_chart = create_price_chart(ticker, period)
            if price_chart:
                st.plotly_chart(price_chart, use_container_width=True)
        
        with tab2:
            metrics_chart = create_metrics_chart(data)
            if metrics_chart:
                st.plotly_chart(metrics_chart, use_container_width=True)
    
    elif chart_data["type"] == "comparison":
        tickers = chart_data["tickers"]
        
        comparison_chart = create_comparison_chart(tickers)
        if comparison_chart:
            st.plotly_chart(comparison_chart, use_container_width=True)
    
    elif chart_data["type"] == "screener":
        stocks = chart_data["stocks"]
        
        sector_chart = create_sector_pie_chart(stocks)
        if sector_chart:
            st.plotly_chart(sector_chart, use_container_width=True)


# ==================== AI CHAT ====================

def detect_and_execute(message):
    """Detect intent and get live data"""
    msg = message.lower()
    
    if any(w in msg for w in ['undervalued', 'value', 'cheap', 'low pe', 'bargain']):
        return screen_stocks_with_chart("undervalued")
    
    if any(w in msg for w in ['growth', 'growing', 'high growth', 'fast growing']):
        return screen_stocks_with_chart("growth")
    
    if any(w in msg for w in ['dividend', 'yield', 'income', 'passive']):
        return screen_stocks_with_chart("dividend")
    
    if any(w in msg for w in ['compare', 'vs', 'versus', 'comparison']):
        tickers = re.findall(r'\b([A-Z]{2,6})\b', message.upper())
        exclude = ['PE', 'ROE', 'VS', 'AND', 'THE', 'FOR', 'ROA', 'EPS']
        tickers = [t for t in tickers if t not in exclude]
        if len(tickers) >= 2:
            return compare_stocks_with_chart(','.join(tickers))
    
    # Single stock
    tickers = re.findall(r'\b([A-Z]{2,6})\b', message.upper())
    exclude = ['PE', 'ROE', 'VS', 'AND', 'THE', 'FOR', 'ROA', 'EPS', 'AI', 'OK', 'HI', 'CEO', 'CFO', 'IPO', 'IT', 'IS', 'BE', 'TO', 'IN', 'OF']
    
    for t in tickers:
        if t in US_STOCKS and t not in exclude:
            return analyze_stock_with_chart(t)
    
    indian_names = [s.replace('.NS', '') for s in INDIAN_STOCKS]
    for t in tickers:
        if t in indian_names and t not in exclude:
            return analyze_stock_with_chart(t)
    
    if any(w in msg for w in ['analyze', 'analysis', 'check', 'tell me', 'how is', 'price', 'stock', 'chart', 'show']):
        for t in tickers:
            if t not in exclude and len(t) >= 2:
                return analyze_stock_with_chart(t)
    
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
    
    system = f"""You are a professional stock analyst with LIVE market data.

RULES:
1. ONLY use data provided - it's LIVE from Yahoo Finance
2. NEVER use training data for prices
3. Note that charts are displayed separately below your response
4. Be concise and data-focused

Market: {market} | Currency: {currency}
Time: {datetime.now().strftime("%Y-%m-%d %H:%M")}

End with: "⚠️ Educational only, not financial advice" """

    messages = [{"role": "system", "content": system}]
    
    for m in history[-4:]:
        messages.append({"role": m["role"], "content": m["content"]})
    
    if data:
        prompt = f"""Question: {user_message}

LIVE DATA:
{json.dumps(data, indent=2, default=str)}

Note: Interactive charts are displayed below. Analyze the data concisely."""
    else:
        prompt = f"""Question: {user_message}

No live data fetched. Ask user to specify a ticker (AAPL, NVDA, TCS, RELIANCE, etc.)
DO NOT provide stock prices from training data."""
    
    messages.append({"role": "user", "content": prompt})
    
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            max_tokens=1500,
            temperature=0.5
        )
        return response.choices[0].message.content
    except Exception as e:
        if "rate_limit" in str(e).lower():
            return "⚠️ Rate limit reached. Please wait."
        return f"Error: {e}"


# ==================== UI ====================

# Header
st.markdown("""
<div class="main-header">
    <h1>📈 AI Stock Analyzer</h1>
    <p>Real-time analysis with interactive charts</p>
</div>
""", unsafe_allow_html=True)

# Controls
col1, col2, col3 = st.columns([2, 1, 1])

with col1:
    market_emoji = "🇺🇸" if st.session_state.market == 'US' else "🇮🇳"
    st.markdown(f"""
    <div class="market-badge">
        {market_emoji} <strong>{st.session_state.market} Market</strong> • Live data
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
        st.session_state.current_chart_data = None
        st.cache_data.clear()
        st.rerun()

with col3:
    c1, c2 = st.columns(2)
    with c1:
        if st.button("🔄", use_container_width=True, help="Refresh data"):
            st.cache_data.clear()
            st.rerun()
    with c2:
        if st.button("🗑️", use_container_width=True, help="Clear chat"):
            st.session_state.chat_messages = []
            st.session_state.current_chart_data = None
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
    st.error("⚠️ Add GROQ_API_KEY to Streamlit Secrets")
    st.code('GROQ_API_KEY = "gsk_your_key_here"')
    st.stop()

# Chat messages
for m in st.session_state.chat_messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

# Display charts if available
if st.session_state.current_chart_data:
    display_charts()

# Welcome
if not st.session_state.chat_messages:
    st.markdown("### 👋 Welcome! Ask me about any stock.")
    st.markdown("**Examples:**")
    
    if st.session_state.market == 'India':
        examples = ["Analyze TCS", "Compare RELIANCE INFY TCS", "Find undervalued stocks", "Show dividend stocks"]
    else:
        examples = ["Analyze AAPL", "Compare AAPL MSFT GOOGL", "Find growth stocks", "Show dividend stocks"]
    
    cols = st.columns(len(examples))
    for i, ex in enumerate(examples):
        with cols[i]:
            if st.button(ex, key=f"ex_{i}", use_container_width=True):
                st.session_state.chat_messages.append({"role": "user", "content": ex})
                st.rerun()

# Chat input
if prompt := st.chat_input("Ask about stocks... (e.g., 'Analyze NVDA' or 'Compare TCS INFY')"):
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
    📈 AI Stock Analyzer • Live data from Yahoo Finance • Powered by Groq AI<br>
    ⚠️ For educational purposes only. Not financial advice.
</div>
""", unsafe_allow_html=True)
