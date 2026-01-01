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
from supabase import create_client, Client
import extra_streamlit_components as stx
from streamlit_mic_recorder import speech_to_text

warnings.filterwarnings('ignore')
load_dotenv()

st.set_page_config(
    page_title="Paula - AI Stock Analyst",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ==================== SUPABASE AUTH ====================

def init_supabase():
    """Initialize Supabase client"""
    url = st.secrets.get("SUPABASE_URL") or os.environ.get("SUPABASE_URL")
    key = st.secrets.get("SUPABASE_KEY") or os.environ.get("SUPABASE_KEY")
    
    if not url or not key:
        return None
    
    return create_client(url, key)

def get_cookie_manager():
    """Get cookie manager for persistent login"""
    return stx.CookieManager()

def check_auth_state():
    """Check if user is authenticated via session or cookie"""
    # Check session state first
    if st.session_state.get('authenticated') and st.session_state.get('user'):
        return True
    
    # Check for stored session in cookies
    cookie_manager = get_cookie_manager()
    stored_token = cookie_manager.get("paula_auth_token")
    stored_email = cookie_manager.get("paula_user_email")
    stored_name = cookie_manager.get("paula_user_name")
    
    if stored_token and stored_email:
        # Verify token with Supabase
        supabase = init_supabase()
        if supabase:
            try:
                # Try to get user with stored token
                supabase.auth.set_session(stored_token, stored_token)
                user = supabase.auth.get_user(stored_token)
                if user:
                    st.session_state['authenticated'] = True
                    st.session_state['user'] = {
                        'email': stored_email,
                        'name': stored_name or '',
                        'access_token': stored_token
                    }
                    return True
            except Exception as e:
                # Token expired or invalid, clear cookies
                cookie_manager.delete("paula_auth_token")
                cookie_manager.delete("paula_user_email")
                cookie_manager.delete("paula_user_name")
    
    return False

def login_user(email, password):
    """Login user with Supabase"""
    supabase = init_supabase()
    if not supabase:
        return False, "Supabase not configured"
    
    try:
        response = supabase.auth.sign_in_with_password({
            "email": email,
            "password": password
        })
        
        if response.user:
            # Get name from user metadata
            user_name = ""
            if response.user.user_metadata:
                user_name = response.user.user_metadata.get('name', '')
            
            st.session_state['authenticated'] = True
            st.session_state['user'] = {
                'email': response.user.email,
                'id': response.user.id,
                'name': user_name,
                'access_token': response.session.access_token
            }
            
            # Store in cookies for persistent login
            cookie_manager = get_cookie_manager()
            cookie_manager.set("paula_auth_token", response.session.access_token, 
                             expires_at=datetime.now() + timedelta(days=30))
            cookie_manager.set("paula_user_email", response.user.email,
                             expires_at=datetime.now() + timedelta(days=30))
            cookie_manager.set("paula_user_name", user_name,
                             expires_at=datetime.now() + timedelta(days=30))
            
            return True, "Login successful!"
        else:
            return False, "Invalid credentials"
            
    except Exception as e:
        error_msg = str(e)
        if "Invalid login credentials" in error_msg:
            return False, "Invalid email or password"
        return False, f"Login failed: {error_msg}"

def signup_user(email, password, name=""):
    """Sign up new user with Supabase"""
    supabase = init_supabase()
    if not supabase:
        return False, "Supabase not configured"
    
    try:
        response = supabase.auth.sign_up({
            "email": email,
            "password": password,
            "options": {
                "data": {
                    "name": name
                }
            }
        })
        
        if response.user:
            return True, "Account created! Please check your email to verify your account."
        else:
            return False, "Sign up failed"
            
    except Exception as e:
        error_msg = str(e)
        if "already registered" in error_msg.lower():
            return False, "This email is already registered"
        return False, f"Sign up failed: {error_msg}"

def logout_user():
    """Logout user"""
    supabase = init_supabase()
    if supabase:
        try:
            supabase.auth.sign_out()
        except:
            pass
    
    # Clear session state
    st.session_state['authenticated'] = False
    st.session_state['user'] = None
    
    # Clear cookies
    cookie_manager = get_cookie_manager()
    cookie_manager.delete("paula_auth_token")
    cookie_manager.delete("paula_user_email")
    cookie_manager.delete("paula_user_name")

def reset_password(email):
    """Send password reset email"""
    supabase = init_supabase()
    if not supabase:
        return False, "Supabase not configured"
    
    try:
        supabase.auth.reset_password_email(email)
        return True, "Password reset email sent! Check your inbox."
    except Exception as e:
        return False, f"Failed to send reset email: {str(e)}"

# ==================== LOGIN PAGE ====================

def show_login_page():
    """Display the login/signup page"""
    
    # CSS for login page
    st.markdown("""
    <style>
        .stApp {
            background: linear-gradient(180deg, #0a0f1a 0%, #111827 100%);
        }
        
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}
        
        .login-container {
            max-width: 400px;
            margin: 0 auto;
            padding: 2rem;
        }
        
        .login-header {
            text-align: center;
            margin-bottom: 2rem;
        }
        
        .login-header h1 {
            font-size: 3rem;
            margin-bottom: 0.5rem;
            background: linear-gradient(135deg, #60a5fa 0%, #a78bfa 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        
        .login-header p {
            color: #9ca3af;
            font-size: 1.1rem;
        }
        
        h1, h2, h3 {
            color: #ffffff !important;
        }
        
        p, span, div, label {
            color: #d1d5db !important;
        }
        
        .stTextInput > div > div {
            background: rgba(255, 255, 255, 0.05) !important;
            border: 1px solid rgba(255, 255, 255, 0.1) !important;
            border-radius: 10px !important;
        }
        
        .stTextInput input {
            color: #ffffff !important;
        }
        
        .stButton > button {
            background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%) !important;
            color: white !important;
            border: none !important;
            border-radius: 10px !important;
            font-weight: 600 !important;
            padding: 0.75rem 1.5rem !important;
            width: 100%;
        }
        
        .stButton > button:hover {
            background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%) !important;
        }
        
        .stTabs [data-baseweb="tab-list"] {
            gap: 0;
            background: rgba(255, 255, 255, 0.05);
            border-radius: 10px;
            padding: 4px;
        }
        
        .stTabs [data-baseweb="tab"] {
            background: transparent;
            border-radius: 8px;
            color: #9ca3af;
            padding: 10px 20px;
        }
        
        .stTabs [aria-selected="true"] {
            background: rgba(37, 99, 235, 0.5) !important;
            color: #ffffff !important;
        }
        
        .success-msg {
            background: rgba(16, 185, 129, 0.1);
            border: 1px solid rgba(16, 185, 129, 0.3);
            border-radius: 8px;
            padding: 12px;
            color: #10b981;
            text-align: center;
        }
        
        .error-msg {
            background: rgba(239, 68, 68, 0.1);
            border: 1px solid rgba(239, 68, 68, 0.3);
            border-radius: 8px;
            padding: 12px;
            color: #ef4444;
            text-align: center;
        }
    </style>
    """, unsafe_allow_html=True)
    
    # Center the login form
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        # Header
        st.markdown("""
        <div class="login-header">
            <h1>👩‍💼 Paula</h1>
            <p>Your AI Stock Analyst</p>
        </div>
        """, unsafe_allow_html=True)
        
        # Check if Supabase is configured
        supabase = init_supabase()
        if not supabase:
            st.error("⚠️ Supabase not configured!")
            st.markdown("""
            **Add these to your Streamlit Secrets:**
            ```
            SUPABASE_URL = "https://your-project.supabase.co"
            SUPABASE_KEY = "your-anon-key"
            ```
            
            **Get these from:** [Supabase Dashboard](https://supabase.com) → Your Project → Settings → API
            """)
            return
        
        # Tabs for Login / Sign Up
        tab1, tab2, tab3 = st.tabs(["🔐 Login", "✨ Sign Up", "🔑 Reset Password"])
        
        with tab1:
            st.markdown("#### Welcome back!")
            
            with st.form("login_form"):
                email = st.text_input("Email", placeholder="your@email.com")
                password = st.text_input("Password", type="password", placeholder="••••••••")
                
                submit = st.form_submit_button("Login", use_container_width=True)
                
                if submit:
                    if not email or not password:
                        st.error("Please fill in all fields")
                    else:
                        with st.spinner("Logging in..."):
                            success, message = login_user(email, password)
                        
                        if success:
                            st.success(message)
                            st.rerun()
                        else:
                            st.error(message)
        
        with tab2:
            st.markdown("#### Create your account")
            
            with st.form("signup_form"):
                name = st.text_input("Name", placeholder="Your name")
                email = st.text_input("Email", placeholder="your@email.com", key="signup_email")
                password = st.text_input("Password", type="password", placeholder="Min 6 characters", key="signup_password")
                confirm = st.text_input("Confirm Password", type="password", placeholder="••••••••")
                
                submit = st.form_submit_button("Create Account", use_container_width=True)
                
                if submit:
                    if not email or not password:
                        st.error("Please fill in all required fields")
                    elif password != confirm:
                        st.error("Passwords don't match")
                    elif len(password) < 6:
                        st.error("Password must be at least 6 characters")
                    else:
                        with st.spinner("Creating account..."):
                            success, message = signup_user(email, password, name)
                        
                        if success:
                            st.success(message)
                        else:
                            st.error(message)
        
        with tab3:
            st.markdown("#### Forgot your password?")
            st.markdown("Enter your email and we'll send you a reset link.")
            
            with st.form("reset_form"):
                email = st.text_input("Email", placeholder="your@email.com", key="reset_email")
                
                submit = st.form_submit_button("Send Reset Link", use_container_width=True)
                
                if submit:
                    if not email:
                        st.error("Please enter your email")
                    else:
                        with st.spinner("Sending..."):
                            success, message = reset_password(email)
                        
                        if success:
                            st.success(message)
                        else:
                            st.error(message)
        
        # Footer
        st.markdown("---")
        st.markdown("""
        <div style="text-align: center; color: #6b7280; font-size: 12px;">
            <p>By signing up, you agree to our Terms of Service</p>
            <p>📈 Paula - AI Stock Analyst</p>
        </div>
        """, unsafe_allow_html=True)


# ==================== MAIN APP (After Login) ====================

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
    
    .user-badge {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        background: rgba(16, 185, 129, 0.1);
        border: 1px solid rgba(16, 185, 129, 0.3);
        padding: 6px 12px;
        border-radius: 20px;
        font-size: 13px;
        color: #10b981;
    }
    
    /* Voice button styling */
    .stAudioInput > div, [data-testid="stAudioInput"] {
        background: transparent !important;
    }
    
    .voice-container button {
        background: linear-gradient(135deg, #10b981 0%, #059669 100%) !important;
        border-radius: 50% !important;
        width: 45px !important;
        height: 45px !important;
        padding: 0 !important;
        border: none !important;
        color: white !important;
        font-size: 1.2rem !important;
    }
    
    .voice-container button:hover {
        background: linear-gradient(135deg, #34d399 0%, #10b981 100%) !important;
        transform: scale(1.05) !important;
    }
    
    /* Recording state */
    .voice-container button[kind="secondary"] {
        background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%) !important;
        animation: pulse 1s infinite !important;
    }
    
    @keyframes pulse {
        0%, 100% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.4); }
        50% { box-shadow: 0 0 0 10px rgba(239, 68, 68, 0); }
    }
</style>
"""

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
    
    user_email = st.session_state.get('user', {}).get('email', 'User')
    
    system = f"""You are Paula, a friendly and professional stock analyst.
User: {user_email}

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

def show_main_app():
    """Display the main Paula app (after login)"""
    st.markdown(MAIN_APP_CSS, unsafe_allow_html=True)
    
    # Initialize session state
    if 'chat_messages' not in st.session_state:
        st.session_state.chat_messages = []
    if 'market' not in st.session_state:
        st.session_state.market = 'US'
    if 'charts_to_display' not in st.session_state:
        st.session_state.charts_to_display = []
    if 'voice_prompt' not in st.session_state:
        st.session_state.voice_prompt = None
    
    # Header
    st.markdown("""
    <div class="main-header">
        <h1>👩‍💼 Paula</h1>
        <p style="color: #9ca3af;">Your AI Stock Analyst</p>
    </div>
    """, unsafe_allow_html=True)
    
    # User info and controls
    col1, col2, col3, col4 = st.columns([2, 1, 0.5, 0.5])
    
    with col1:
        market_emoji = "🇺🇸" if st.session_state.market == 'US' else "🇮🇳"
        user_display = st.session_state.get('user', {}).get('name', '')
        if not user_display:
            user_display = st.session_state.get('user', {}).get('email', 'User')
        st.markdown(f"""
        <div class="market-badge">{market_emoji} <strong>{st.session_state.market} Market</strong></div>
        <div class="user-badge">👤 {user_display}</div>
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
    
    with col4:
        if st.button("🚪", use_container_width=True, help="Logout"):
            logout_user()
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
        user_name = st.session_state.get('user', {}).get('name', '')
        if not user_name:
            user_name = st.session_state.get('user', {}).get('email', 'there').split('@')[0]
        st.markdown(f"### 👋 Hi {user_name}! I'm Paula. Ask me about any stock.")
        st.markdown("**Examples:**")
        
        examples = ["Analyze TCS", "Compare RELIANCE INFY", "Find undervalued", "Show dividends"] if st.session_state.market == 'India' else ["Analyze AAPL", "Compare AAPL MSFT", "Find growth stocks", "Show dividends"]
        
        cols = st.columns(len(examples))
        for i, ex in enumerate(examples):
            with cols[i]:
                if st.button(ex, key=f"ex_{i}", use_container_width=True):
                    st.session_state.chat_messages.append({"role": "user", "content": ex})
                    st.rerun()
    
    # Voice and Chat input
    col_voice, col_chat = st.columns([1, 11])
    
    with col_voice:
        voice_text = speech_to_text(
            language='en',
            start_prompt="🎤",
            stop_prompt="⏹️",
            just_once=True,
            key='voice_input',
            use_container_width=True
        )
    
    # Handle voice input
    if voice_text:
        st.session_state.voice_prompt = voice_text
        st.rerun()
    
    # Check for voice prompt from previous run
    prompt = None
    if st.session_state.get('voice_prompt'):
        prompt = st.session_state.voice_prompt
        st.session_state.voice_prompt = None  # Clear it
    
    # Regular chat input
    with col_chat:
        typed_prompt = st.chat_input("Ask Paula about stocks... or click 🎤 to speak")
    
    if typed_prompt:
        prompt = typed_prompt
    
    if prompt:
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
        👩‍💼 Paula • Live data from Yahoo Finance • ⚠️ Educational only
    </div>
    """, unsafe_allow_html=True)


# ==================== MAIN ====================

def main():
    # Initialize session state
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'user' not in st.session_state:
        st.session_state.user = None
    
    # Check if already authenticated
    if not st.session_state.authenticated:
        check_auth_state()
    
    # Show login or main app
    if st.session_state.authenticated and st.session_state.user:
        show_main_app()
    else:
        show_login_page()

if __name__ == "__main__":
    main()
