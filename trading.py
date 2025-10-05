import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from supabase import create_client, Client

# Page configuration
st.set_page_config(
    page_title="WealthStockify - Premium Stock Analysis",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize Supabase
@st.cache_resource
def init_supabase() -> Client:
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["key"]
    return create_client(url, key)

supabase = init_supabase()

# Custom CSS (same as before, truncated for brevity)
st.markdown("""
<style>
    .stApp { background: #0e1117; }
    h1, h2, h3 { color: #ffffff !important; }
    .stButton > button {
        background: #1f2937;
        color: white;
        border: 1px solid #374151;
        border-radius: 8px;
        padding: 0.75rem 2rem;
        font-weight: 600;
    }
    .stButton > button:hover {
        background: #374151;
    }
</style>
""", unsafe_allow_html=True)

# Authentication Functions
def sign_up(email: str, password: str):
    try:
        response = supabase.auth.sign_up({
            "email": email,
            "password": password
        })
        if response.user:
            # Create user profile
            supabase.table('user_profiles').insert({
                'id': response.user.id,
                'email': email,
                'is_premium': False
            }).execute()
            return True, "Account created successfully! Please check your email to verify."
        return False, "Failed to create account"
    except Exception as e:
        return False, str(e)

def sign_in(email: str, password: str):
    try:
        response = supabase.auth.sign_in_with_password({
            "email": email,
            "password": password
        })
        if response.user:
            # Get user profile
            profile = supabase.table('user_profiles').select('*').eq('id', response.user.id).execute()
            return True, response.user, profile.data[0] if profile.data else None
        return False, None, None
    except Exception as e:
        return False, None, str(e)

def sign_out():
    supabase.auth.sign_out()
    st.session_state.clear()

def get_user_watchlist(user_id: str):
    try:
        response = supabase.table('watchlists').select('ticker').eq('user_id', user_id).execute()
        return [item['ticker'] for item in response.data]
    except:
        return []

def add_to_watchlist(user_id: str, ticker: str):
    try:
        supabase.table('watchlists').insert({
            'user_id': user_id,
            'ticker': ticker
        }).execute()
        return True
    except:
        return False

def remove_from_watchlist(user_id: str, ticker: str):
    try:
        supabase.table('watchlists').delete().eq('user_id', user_id).eq('ticker', ticker).execute()
        return True
    except:
        return False

# Initialize session state
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'user' not in st.session_state:
    st.session_state.user = None
if 'user_profile' not in st.session_state:
    st.session_state.user_profile = None

# Helper Functions (same as before)
def calculate_technical_indicators(df):
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    
    exp1 = df['Close'].ewm(span=12, adjust=False).mean()
    exp2 = df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = exp1 - exp2
    df['Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    
    df['BB_Middle'] = df['Close'].rolling(window=20).mean()
    bb_std = df['Close'].rolling(window=20).std()
    df['BB_Upper'] = df['BB_Middle'] + (bb_std * 2)
    df['BB_Lower'] = df['BB_Middle'] - (bb_std * 2)
    
    df['SMA_50'] = df['Close'].rolling(window=50).mean()
    df['SMA_200'] = df['Close'].rolling(window=200).mean()
    df['EMA_20'] = df['Close'].ewm(span=20, adjust=False).mean()
    
    high_low = df['High'] - df['Low']
    high_close = np.abs(df['High'] - df['Close'].shift())
    low_close = np.abs(df['Low'] - df['Close'].shift())
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = np.max(ranges, axis=1)
    df['ATR'] = true_range.rolling(14).mean()
    
    return df

def calculate_ai_score(df, info):
    score = 50
    if len(df) > 0:
        current_price = df['Close'].iloc[-1]
        if 'RSI' in df.columns and pd.notna(df['RSI'].iloc[-1]):
            rsi = df['RSI'].iloc[-1]
            if 40 <= rsi <= 60:
                score += 10
            elif 30 <= rsi < 40 or 60 < rsi <= 70:
                score += 5
        if 'MACD' in df.columns and 'Signal' in df.columns:
            if pd.notna(df['MACD'].iloc[-1]) and pd.notna(df['Signal'].iloc[-1]):
                if df['MACD'].iloc[-1] > df['Signal'].iloc[-1]:
                    score += 10
        if 'SMA_50' in df.columns and 'SMA_200' in df.columns:
            sma50 = df['SMA_50'].iloc[-1]
            sma200 = df['SMA_200'].iloc[-1]
            if pd.notna(sma50) and pd.notna(sma200):
                if current_price > sma50 > sma200:
                    score += 15
                elif current_price > sma50:
                    score += 8
    try:
        if 'trailingPE' in info and info['trailingPE']:
            pe = info['trailingPE']
            if 10 <= pe <= 25:
                score += 15
        if 'profitMargins' in info and info['profitMargins']:
            if info['profitMargins'] > 0.15:
                score += 10
        if 'returnOnEquity' in info and info['returnOnEquity']:
            if info['returnOnEquity'] > 0.15:
                score += 10
    except:
        pass
    return min(max(score, 0), 100)

# Authentication UI
if not st.session_state.authenticated:
    st.markdown("# WealthStockify")
    st.markdown("### Professional Stock Analysis Platform")
    
    tab1, tab2 = st.tabs(["Login", "Sign Up"])
    
    with tab1:
        st.subheader("Login to Your Account")
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Password", type="password", key="login_password")
        
        if st.button("Login", use_container_width=True):
            if email and password:
                success, user, profile = sign_in(email, password)
                if success:
                    st.session_state.authenticated = True
                    st.session_state.user = user
                    st.session_state.user_profile = profile
                    st.success("Logged in successfully!")
                    st.rerun()
                else:
                    st.error("Invalid credentials")
            else:
                st.warning("Please enter email and password")
    
    with tab2:
        st.subheader("Create New Account")
        new_email = st.text_input("Email", key="signup_email")
        new_password = st.text_input("Password (min 6 characters)", type="password", key="signup_password")
        confirm_password = st.text_input("Confirm Password", type="password", key="confirm_password")
        
        if st.button("Sign Up", use_container_width=True):
            if new_email and new_password and confirm_password:
                if new_password != confirm_password:
                    st.error("Passwords do not match")
                elif len(new_password) < 6:
                    st.error("Password must be at least 6 characters")
                else:
                    success, message = sign_up(new_email, new_password)
                    if success:
                        st.success(message)
                    else:
                        st.error(f"Error: {message}")
            else:
                st.warning("Please fill all fields")
    
    st.stop()

# Main App (for authenticated users)
# Sidebar
with st.sidebar:
    st.markdown(f"# WealthStockify")
    st.markdown(f"**{st.session_state.user.email}**")
    
    is_premium = st.session_state.user_profile.get('is_premium', False) if st.session_state.user_profile else False
    
    if is_premium:
        st.success("⭐ PREMIUM")
        sub_end = st.session_state.user_profile.get('subscription_end_date')
        if sub_end:
            st.caption(f"Valid until: {sub_end}")
    else:
        st.info("🆓 FREE TIER")
        if st.button("Upgrade to Premium - $9.99/mo", use_container_width=True):
            st.info("Payment integration coming soon! Contact support to upgrade.")
    
    if st.button("Logout", use_container_width=True):
        sign_out()
        st.rerun()
    
    st.markdown("---")
    
    with st.expander("✨ Premium Features"):
        features = [
            "Unlimited Stock Analysis",
            "AI Scoring System",
            "Advanced Technical Indicators",
            "Stock Screener (30+ stocks)",
            "AI Price Predictions",
            "Position Size Calculator",
            "5-Year Backtesting",
            "Watchlist with Alerts",
            "Export to CSV"
        ]
        for feature in features:
            icon = "✅" if is_premium else "🔒"
            st.markdown(f"{icon} {feature}")

# Top Navigation
st.markdown("### Navigation")
nav_cols = st.columns(5)

with nav_cols[0]:
    if st.button("📊 Stock Analysis", use_container_width=True):
        st.session_state.page = "Stock Analysis"

with nav_cols[1]:
    if st.button("🔍 Stock Screener", use_container_width=True):
        st.session_state.page = "Stock Screener"

with nav_cols[2]:
    if st.button("📈 Backtesting", use_container_width=True):
        st.session_state.page = "Backtesting"

with nav_cols[3]:
    if st.button("👁️ Watchlist", use_container_width=True):
        st.session_state.page = "Watchlist"

with nav_cols[4]:
    if st.button("💰 Position Sizer", use_container_width=True):
        st.session_state.page = "Position Sizer"

if 'page' not in st.session_state:
    st.session_state.page = "Stock Analysis"

page = st.session_state.page
st.markdown("---")

# Stock Analysis Page
if page == "Stock Analysis":
    st.title("📊 Stock Analysis Dashboard")
    
    col1, col2, col3 = st.columns([3, 2, 1])
    
    with col1:
        ticker = st.text_input("Enter Stock Ticker", value="AAPL").upper()
    
    with col2:
        period = st.selectbox("Time Period", ["1mo", "3mo", "6mo", "1y", "2y", "5y"], index=2)
    
    with col3:
        st.write("")
        st.write("")
        analyze_btn = st.button("Analyze", type="primary")
    
    if ticker:
        try:
            with st.spinner("Fetching data..."):
                stock = yf.Ticker(ticker)
                hist = stock.history(period=period)
                info = stock.info
            
            if hist.empty:
                st.error("Invalid ticker or no data available.")
            else:
                hist = calculate_technical_indicators(hist)
                
                current_price = hist['Close'].iloc[-1]
                prev_close = hist['Close'].iloc[-2] if len(hist) > 1 else current_price
                change = current_price - prev_close
                change_pct = (change / prev_close) * 100
                
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric("Current Price", f"${current_price:.2f}", f"{change_pct:+.2f}%")
                
                with col2:
                    if is_premium:
                        ai_score = calculate_ai_score(hist, info)
                        color = "🟢" if ai_score >= 70 else "🟡" if ai_score >= 50 else "🔴"
                        st.metric("AI Score", f"{ai_score:.0f}/100", color)
                    else:
                        st.metric("AI Score", "🔒 Premium")
                
                with col3:
                    volume = info.get('volume', 0)
                    st.metric("Volume", f"{volume/1e6:.1f}M")
                
                with col4:
                    market_cap = info.get('marketCap', 0)
                    if market_cap > 0:
                        st.metric("Market Cap", f"${market_cap/1e9:.2f}B")
                
                st.markdown("---")
                
                # Chart
                st.subheader("📈 Price Chart")
                
                fig = make_subplots(
                    rows=3 if is_premium else 1,
                    cols=1,
                    shared_xaxes=True,
                    vertical_spacing=0.08,
                    row_heights=[0.6, 0.2, 0.2] if is_premium else [1]
                )
                
                fig.add_trace(
                    go.Candlestick(
                        x=hist.index,
                        open=hist['Open'],
                        high=hist['High'],
                        low=hist['Low'],
                        close=hist['Close'],
                        name='Price'
                    ),
                    row=1, col=1
                )
                
                if is_premium:
                    fig.add_trace(go.Scatter(x=hist.index, y=hist['SMA_50'], name='SMA 50', line=dict(color='orange')), row=1, col=1)
                    fig.add_trace(go.Scatter(x=hist.index, y=hist['SMA_200'], name='SMA 200', line=dict(color='red')), row=1, col=1)
                    fig.add_trace(go.Scatter(x=hist.index, y=hist['MACD'], name='MACD', line=dict(color='blue')), row=2, col=1)
                    fig.add_trace(go.Scatter(x=hist.index, y=hist['Signal'], name='Signal', line=dict(color='red')), row=2, col=1)
                    fig.add_trace(go.Scatter(x=hist.index, y=hist['RSI'], name='RSI', line=dict(color='purple')), row=3, col=1)
                    fig.add_hline(y=70, line_dash="dash", line_color="red", row=3, col=1)
                    fig.add_hline(y=30, line_dash="dash", line_color="green", row=3, col=1)
                
                fig.update_layout(height=800 if is_premium else 500, template='plotly_dark', xaxis_rangeslider_visible=False)
                st.plotly_chart(fig, use_container_width=True)
                
        except Exception as e:
            st.error(f"Error: {str(e)}")

elif page == "Watchlist":
    st.title("👁️ Watchlist")
    
    if is_premium:
        col1, col2 = st.columns([3, 1])
        
        with col1:
            new_ticker = st.text_input("Add Stock", placeholder="e.g., AAPL").upper()
        
        with col2:
            st.write("")
            st.write("")
            if st.button("Add", type="primary"):
                if new_ticker:
                    if add_to_watchlist(st.session_state.user.id, new_ticker):
                        st.success(f"Added {new_ticker}")
                        st.rerun()
                    else:
                        st.error("Failed to add")
        
        watchlist = get_user_watchlist(st.session_state.user.id)
        
        if watchlist:
            st.subheader("Your Stocks")
            for ticker in watchlist:
                col1, col2 = st.columns([4, 1])
                with col1:
                    st.write(f"📊 {ticker}")
                with col2:
                    if st.button("Remove", key=f"remove_{ticker}"):
                        remove_from_watchlist(st.session_state.user.id, ticker)
                        st.rerun()
        else:
            st.info("Your watchlist is empty")
    else:
        st.warning("🔒 Watchlist is a Premium Feature")

else:
    st.info(f"'{page}' page coming soon!")

# Footer
st.markdown("---")
st.markdown("WealthStockify © 2025 | For educational purposes only")
