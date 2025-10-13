"""
AI STOCK GENIUS - REDESIGNED v4.0
Beginner-Friendly Stock Analysis Platform
"""

# IMPORTS
import json
import time
import warnings
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional

import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

try:
    from supabase import create_client
    SUPABASE_AVAILABLE = True
except:
    SUPABASE_AVAILABLE = False

warnings.filterwarnings('ignore')

# PAGE CONFIGURATION
st.set_page_config(
    page_title="AI Stock Genius",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CUSTOM CSS
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');
    
    * { font-family: 'Inter', sans-serif; }
    
    .stApp {
        background: linear-gradient(135deg, #0a0e1a 0%, #151b2e 100%);
    }
    
    .main .block-container {
        background: rgba(21, 27, 46, 0.6);
        backdrop-filter: blur(20px);
        border-radius: 20px;
        padding: 2.5rem;
    }
    
    h1, h2, h3 { color: #ffffff !important; font-weight: 700 !important; }
    p, div, span, label { color: #e0e6f0 !important; }
    
    .stButton > button {
        background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
        color: white;
        border: none;
        border-radius: 12px;
        padding: 0.875rem 1.75rem;
        font-weight: 600;
        width: 100%;
        min-height: 44px;
    }
    
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(59, 130, 246, 0.6);
    }
    
    .premium-badge {
        background: linear-gradient(135deg, #fbbf24 0%, #f59e0b 100%);
        color: #1e293b !important;
        padding: 0.75rem 1.5rem;
        border-radius: 12px;
        font-weight: 700;
        text-align: center;
    }
</style>
""", unsafe_allow_html=True)

# SESSION MANAGER
class SessionManager:
    @staticmethod
    def initialize():
        defaults = {
            'authenticated': False,
            'user': None,
            'profile': {'is_premium': False},
            'page': 'home',
            'beginner_mode': True,
            'demo_mode': True
        }
        for key, value in defaults.items():
            if key not in st.session_state:
                st.session_state[key] = value
    
    @staticmethod
    def get(key, default=None):
        return st.session_state.get(key, default)
    
    @staticmethod
    def set(key, value):
        st.session_state[key] = value

# Initialize session
SessionManager.initialize()

# DATABASE (Mock for demo)
class DatabaseService:
    @staticmethod
    def get_watchlist(user_id):
        return SessionManager.get('watchlist', [])
    
    @staticmethod
    def add_to_watchlist(user_id, ticker):
        watchlist = SessionManager.get('watchlist', [])
        if ticker not in [w.get('ticker') for w in watchlist]:
            watchlist.append({'ticker': ticker})
            SessionManager.set('watchlist', watchlist)
            return True
        return False
    
    @staticmethod
    def remove_from_watchlist(user_id, ticker):
        watchlist = SessionManager.get('watchlist', [])
        watchlist = [w for w in watchlist if w.get('ticker') != ticker]
        SessionManager.set('watchlist', watchlist)
        return True

# STOCK SEARCH
class StockSearchHelper:
    @staticmethod
    def search_stock(query):
        if not query or len(query) < 1:
            return []
        
        popular_stocks = {
            'AAPL': 'Apple Inc.',
            'MSFT': 'Microsoft Corporation',
            'GOOGL': 'Alphabet Inc.',
            'AMZN': 'Amazon.com Inc.',
            'META': 'Meta Platforms Inc.',
            'NVDA': 'NVIDIA Corporation',
            'TSLA': 'Tesla Inc.',
            'AMD': 'Advanced Micro Devices',
            'NFLX': 'Netflix Inc.',
        }
        
        results = []
        query_upper = query.upper()
        
        for ticker, name in popular_stocks.items():
            if query_upper in ticker or query_upper in name.upper():
                results.append((ticker, name))
        
        return results[:10]
    
    @staticmethod
    def format_option(ticker, name):
        if len(name) > 50:
            name = name[:47] + "..."
        return f"{ticker} - {name}"

# TECHNICAL ANALYSIS
class TechnicalAnalysisEngine:
    @staticmethod
    def calculate_all_indicators(df):
        try:
            # RSI
            delta = df['Close'].diff()
            gain = delta.where(delta > 0, 0).rolling(window=14).mean()
            loss = -delta.where(delta < 0, 0).rolling(window=14).mean()
            rs = gain / loss
            df['RSI'] = 100 - (100 / (1 + rs))
            
            # Moving averages
            df['SMA20'] = df['Close'].rolling(window=20).mean()
            df['SMA50'] = df['Close'].rolling(window=50).mean()
            
            return df
        except:
            return df

# AUTH PAGE
def render_auth_page():
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown("<h1 style='text-align: center;'>🤖 AI Stock Genius</h1>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; color: #94a3b8; font-size: 1.2rem;'>Beginner-Friendly Stock Analysis</p>", unsafe_allow_html=True)
        
        st.info("👋 **Demo Mode** - Click 'Try Demo' to explore without signing up!")
        
        if st.button("🚀 Try Demo", use_container_width=True, type="primary"):
            SessionManager.set('authenticated', True)
            SessionManager.set('demo_mode', True)
            st.rerun()
        
        st.markdown("<p style='text-align: center; margin-top: 2rem;'>or sign in with your account</p>", unsafe_allow_html=True)
        
        with st.form("signin_form"):
            email = st.text_input("Email", placeholder="your@email.com")
            password = st.text_input("Password", type="password")
            if st.form_submit_button("Sign In", use_container_width=True):
                st.info("Authentication coming soon! Use Demo Mode for now.")

# SIDEBAR
def render_sidebar(is_premium):
    with st.sidebar:
        st.markdown("### 🤖 AI Stock Genius")
        st.markdown("---")
        
        if SessionManager.get('demo_mode'):
            st.markdown('<div class="premium-badge">🎮 DEMO MODE</div>', unsafe_allow_html=True)
        
        st.markdown("---")
        st.markdown("#### Navigation")
        
        if st.button("🏠 Home", use_container_width=True):
            SessionManager.set('page', 'home')
            st.rerun()
        
        if st.button("📊 Analyze", use_container_width=True):
            SessionManager.set('page', 'analyze')
            st.rerun()
        
        if st.button("💼 My Stocks", use_container_width=True):
            SessionManager.set('page', 'mystocks')
            st.rerun()
        
        st.markdown("---")
        
        if st.button("🚪 Exit Demo" if SessionManager.get('demo_mode') else "🚪 Sign Out", use_container_width=True):
            SessionManager.set('authenticated', False)
            st.rerun()

# HOME PAGE
def render_home_page(is_premium):
    st.title("🏠 Home Dashboard")
    
    st.success("🎉 Welcome to AI Stock Genius! Start by analyzing a stock.")
    
    st.markdown("### 🚀 Quick Actions")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("📊 Analyze a Stock", use_container_width=True, type="primary"):
            SessionManager.set('page', 'analyze')
            st.rerun()
    
    with col2:
        if st.button("💼 View My Stocks", use_container_width=True):
            SessionManager.set('page', 'mystocks')
            st.rerun()
    
    with col3:
        st.metric("Watchlist", len(DatabaseService.get_watchlist('demo')))

# ANALYZE PAGE
def render_analyze_page(is_premium):
    st.title("📊 Stock Analysis")
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        search_query = st.text_input(
            "Search by company name or ticker",
            placeholder="e.g., Apple, Tesla, MSFT...",
            label_visibility="collapsed"
        )
    
    ticker = None
    
    if search_query:
        results = StockSearchHelper.search_stock(search_query)
        
        if results:
            options = [StockSearchHelper.format_option(t, n) for t, n in results]
            selected = st.selectbox("Select a stock:", options)
            
            if selected:
                ticker = selected.split(" - ")[0].strip()
        else:
            st.info(f"No results found for '{search_query}'")
    else:
        ticker = 'AAPL'
        st.info("💡 Try searching: Apple, Microsoft, Tesla, Amazon")
    
    if ticker:
        try:
            with st.spinner(f"🤖 Analyzing {ticker}..."):
                stock = yf.Ticker(ticker)
                df = stock.history(period='6mo')
                info = stock.info
                
                if df.empty:
                    st.error("Unable to fetch data")
                    return
                
                df = TechnicalAnalysisEngine.calculate_all_indicators(df)
                
                price = df['Close'].iloc[-1]
                prev = df['Close'].iloc[-2] if len(df) > 1 else price
                change_pct = ((price - prev) / prev) * 100
                
                company_name = info.get('longName', ticker)
                st.markdown(f"## {company_name} ({ticker})")
                
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Current Price", f"${price:.2f}", f"{change_pct:+.2f}%")
                col2.metric("Volume", f"{info.get('volume', 0)/1e6:.1f}M")
                col3.metric("Market Cap", f"${info.get('marketCap', 0)/1e9:.1f}B")
                col4.metric("P/E Ratio", f"{info.get('trailingPE', 0):.2f}")
                
                st.markdown("---")
                
                # Chart
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=df.index,
                    y=df['Close'],
                    name='Price',
                    line=dict(color='#3b82f6', width=3),
                    fill='tozeroy',
                    fillcolor='rgba(59, 130, 246, 0.1)'
                ))
                fig.update_layout(
                    height=500,
                    template='plotly_dark',
                    title="Price History (6 months)",
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0.3)'
                )
                st.plotly_chart(fig, use_container_width=True)
                
                # Action buttons
                col1, col2 = st.columns(2)
                with col1:
                    if st.button(f"⭐ Add {ticker} to Watchlist", use_container_width=True, type="primary"):
                        if DatabaseService.add_to_watchlist('demo', ticker):
                            st.success(f"✅ {ticker} added to watchlist!")
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.warning("Already in watchlist")
                
        except Exception as e:
            st.error(f"Error: {str(e)}")

# MY STOCKS PAGE
def render_mystocks_page(is_premium):
    st.title("💼 My Stocks")
    
    st.markdown("### 👁️ Your Watchlist")
    
    with st.expander("➕ Add Stock to Watchlist"):
        search = st.text_input("Search stock", placeholder="e.g., Apple, TSLA")
        
        if search:
            results = StockSearchHelper.search_stock(search)
            if results:
                options = [StockSearchHelper.format_option(t, n) for t, n in results]
                selected = st.selectbox("Select stock:", options)
                
                if st.button("Add to Watchlist", type="primary"):
                    ticker = selected.split(" - ")[0].strip()
                    if DatabaseService.add_to_watchlist('demo', ticker):
                        st.success(f"✅ {ticker} added!")
                        time.sleep(0.5)
                        st.rerun()
    
    st.markdown("---")
    
    watchlist = DatabaseService.get_watchlist('demo')
    
    if watchlist:
        st.markdown(f"**{len(watchlist)} stocks in your watchlist**")
        
        for i in range(0, len(watchlist), 3):
            cols = st.columns(3)
            for j, col in enumerate(cols):
                if i + j < len(watchlist):
                    item = watchlist[i + j]
                    ticker = item['ticker']
                    
                    try:
                        stock = yf.Ticker(ticker)
                        hist = stock.history(period='1d')
                        
                        if not hist.empty:
                            price = hist['Close'].iloc[-1]
                            
                            with col:
                                st.markdown(f"**{ticker}**")
                                st.metric("Price", f"${price:.2f}")
                                if st.button("Remove", key=f"rm_{ticker}_{i}_{j}"):
                                    DatabaseService.remove_from_watchlist('demo', ticker)
                                    st.rerun()
                    except:
                        with col:
                            st.markdown(f"**{ticker}**")
                            st.caption("Data unavailable")
    else:
        st.info("Your watchlist is empty. Add stocks to track them!")

# MAIN
def main():
    SessionManager.initialize()
    
    if not SessionManager.get('authenticated', False):
        render_auth_page()
        return
    
    profile = SessionManager.get('profile', {})
    is_premium = profile.get('is_premium', False)
    
    render_sidebar(is_premium)
    
    page = SessionManager.get('page', 'home')
    
    if page == 'home':
        render_home_page(is_premium)
    elif page == 'analyze':
        render_analyze_page(is_premium)
    elif page == 'mystocks':
        render_mystocks_page(is_premium)

# RUN
main()
