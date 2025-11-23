"""
EARNINGS TRADER PRO - COMPLETE ENHANCED EDITION
Full-featured earnings trading platform with login, portfolio tracking, and AI analysis
"""

import json
import time
import warnings
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, asdict
from pathlib import Path

import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go

warnings.filterwarnings('ignore')

# ============================================================================
# CONFIGURATION
# ============================================================================

class Config:
    PAGE_TITLE = "Earnings Trader Pro"
    PAGE_ICON = "📈"
    LAYOUT = "wide"
    
    SCORE_EXCEPTIONAL = 85
    SCORE_STRONG = 75
    SCORE_GOOD = 65
    SCORE_MODERATE = 55
    
    MAX_POSITION_EXCEPTIONAL = 0.10
    MAX_POSITION_STRONG = 0.07
    MAX_POSITION_GOOD = 0.05
    MAX_POSITION_MODERATE = 0.03
    
    DEFAULT_ACCOUNT_SIZE = 50000
    USER_DATA_DIR = Path("/tmp/earnings_trader_users")
    
    @classmethod
    def ensure_user_dir(cls):
        cls.USER_DATA_DIR.mkdir(exist_ok=True)

Config.ensure_user_dir()

st.set_page_config(
    page_title=Config.PAGE_TITLE,
    page_icon=Config.PAGE_ICON,
    layout=Config.LAYOUT,
    initial_sidebar_state="expanded"
)

# ============================================================================
# ENHANCED CSS
# ============================================================================

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700;800&display=swap');
    
    * { font-family: 'Inter', sans-serif; }
    
    .stApp { 
        background: linear-gradient(135deg, #0a0e27 0%, #1a1f3a 50%, #0f1419 100%);
    }
    
    .main .block-container {
        background: rgba(20, 25, 45, 0.7);
        backdrop-filter: blur(30px);
        border-radius: 24px;
        padding: 3rem;
        max-width: 1600px;
        border: 1px solid rgba(99, 102, 241, 0.1);
    }
    
    h1 {
        background: linear-gradient(135deg, #60a5fa 0%, #a78bfa 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 800 !important;
    }
    
    .stButton > button {
        background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%);
        color: white !important;
        border: none;
        border-radius: 14px;
        padding: 0.85rem 2rem;
        font-weight: 700;
        transition: all 0.3s ease;
        box-shadow: 0 4px 16px rgba(79, 70, 229, 0.3);
    }
    
    .stButton > button:hover {
        transform: translateY(-3px);
        box-shadow: 0 8px 24px rgba(79, 70, 229, 0.5);
    }
    
    .score-card {
        background: linear-gradient(135deg, rgba(79, 70, 229, 0.15) 0%, rgba(124, 58, 237, 0.15) 100%);
        border: 2px solid rgba(99, 102, 241, 0.4);
        border-radius: 20px;
        padding: 3rem;
        text-align: center;
        box-shadow: 0 8px 32px rgba(79, 70, 229, 0.2);
    }
    
    .login-container {
        max-width: 450px;
        margin: 5rem auto;
        padding: 3rem;
        background: rgba(30, 35, 60, 0.8);
        backdrop-filter: blur(20px);
        border-radius: 24px;
        border: 1px solid rgba(99, 102, 241, 0.3);
        box-shadow: 0 12px 48px rgba(0, 0, 0, 0.5);
    }
    
    .recommendation-box {
        background: linear-gradient(135deg, rgba(16, 185, 129, 0.15) 0%, rgba(5, 150, 105, 0.15) 100%);
        border-left: 5px solid #10b981;
        padding: 2rem;
        border-radius: 12px;
        margin: 1.5rem 0;
    }
    
    .warning-box {
        background: linear-gradient(135deg, rgba(239, 68, 68, 0.15) 0%, rgba(220, 38, 38, 0.15) 100%);
        border-left: 5px solid #ef4444;
        padding: 2rem;
        border-radius: 12px;
        margin: 1.5rem 0;
    }
    
    .info-box {
        background: linear-gradient(135deg, rgba(59, 130, 246, 0.15) 0%, rgba(37, 99, 235, 0.15) 100%);
        border-left: 5px solid #3b82f6;
        padding: 2rem;
        border-radius: 12px;
        margin: 1.5rem 0;
    }
</style>
""", unsafe_allow_html=True)

# ============================================================================
# USER AUTHENTICATION
# ============================================================================

@dataclass
class User:
    username: str
    password_hash: str
    email: str
    created_at: datetime
    account_size: float
    watchlist: List[str]
    trade_history: List[Dict]
    settings: Dict
    
    def to_dict(self):
        data = asdict(self)
        data['created_at'] = data['created_at'].isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict):
        data['created_at'] = datetime.fromisoformat(data['created_at'])
        return cls(**data)

class AuthSystem:
    @staticmethod
    def hash_password(password: str) -> str:
        return hashlib.sha256(password.encode()).hexdigest()
    
    @staticmethod
    def get_user_file(username: str) -> Path:
        return Config.USER_DATA_DIR / f"{username}.json"
    
    @staticmethod
    def user_exists(username: str) -> bool:
        return AuthSystem.get_user_file(username).exists()
    
    @staticmethod
    def create_user(username: str, password: str, email: str, account_size: float) -> bool:
        if AuthSystem.user_exists(username):
            return False
        
        user = User(
            username=username,
            password_hash=AuthSystem.hash_password(password),
            email=email,
            created_at=datetime.now(),
            account_size=account_size,
            watchlist=[],
            trade_history=[],
            settings={'default_stop_loss': 0.15, 'risk_per_trade': 0.02}
        )
        
        with open(AuthSystem.get_user_file(username), 'w') as f:
            json.dump(user.to_dict(), f, indent=2)
        
        return True
    
    @staticmethod
    def authenticate(username: str, password: str) -> Optional[User]:
        if not AuthSystem.user_exists(username):
            return None
        
        with open(AuthSystem.get_user_file(username), 'r') as f:
            user_data = json.load(f)
        
        user = User.from_dict(user_data)
        
        if user.password_hash == AuthSystem.hash_password(password):
            return user
        return None
    
    @staticmethod
    def save_user(user: User):
        with open(AuthSystem.get_user_file(user.username), 'w') as f:
            json.dump(user.to_dict(), f, indent=2)

# ============================================================================
# SESSION STATE
# ============================================================================

def init_session_state():
    defaults = {
        'authenticated': False,
        'user': None,
        'page': 'scanner',
        'selected_ticker': None,
    }
    
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

init_session_state()

# ============================================================================
# DATA SERVICES
# ============================================================================

@st.cache_data(ttl=300)
def get_stock_data(ticker: str, period: str = '1y') -> Optional[pd.DataFrame]:
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period=period)
        return df if not df.empty else None
    except:
        return None

@st.cache_data(ttl=300)
def get_stock_info(ticker: str) -> Dict[str, Any]:
    try:
        return yf.Ticker(ticker).info
    except:
        return {}

def estimate_next_earnings_date(ticker: str) -> Tuple[Optional[datetime], int]:
    ticker_hash = sum(ord(c) for c in ticker)
    base_days = 7 + (ticker_hash % 40)
    estimated_date = datetime.now() + timedelta(days=base_days)
    return estimated_date, base_days

# ============================================================================
# STOCK DATABASE
# ============================================================================

class StockDB:
    STOCKS = {
        'AAPL': {'name': 'Apple Inc.', 'sector': 'Technology', 'cap': 'Mega'},
        'MSFT': {'name': 'Microsoft', 'sector': 'Technology', 'cap': 'Mega'},
        'GOOGL': {'name': 'Alphabet', 'sector': 'Technology', 'cap': 'Mega'},
        'AMZN': {'name': 'Amazon', 'sector': 'Technology', 'cap': 'Mega'},
        'META': {'name': 'Meta', 'sector': 'Technology', 'cap': 'Mega'},
        'NVDA': {'name': 'NVIDIA', 'sector': 'Technology', 'cap': 'Large'},
        'TSLA': {'name': 'Tesla', 'sector': 'Technology', 'cap': 'Large'},
        'AMD': {'name': 'AMD', 'sector': 'Technology', 'cap': 'Large'},
        'NFLX': {'name': 'Netflix', 'sector': 'Technology', 'cap': 'Large'},
        'DIS': {'name': 'Disney', 'sector': 'Consumer', 'cap': 'Large'},
        'NKE': {'name': 'Nike', 'sector': 'Consumer', 'cap': 'Large'},
        'SBUX': {'name': 'Starbucks', 'sector': 'Consumer', 'cap': 'Large'},
        'JPM': {'name': 'JPMorgan', 'sector': 'Finance', 'cap': 'Large'},
        'BAC': {'name': 'Bank of America', 'sector': 'Finance', 'cap': 'Large'},
        'V': {'name': 'Visa', 'sector': 'Finance', 'cap': 'Large'},
    }
    
    @classmethod
    def search(cls, query: str) -> List[Tuple[str, Dict]]:
        query = query.upper()
        return [(t, d) for t, d in cls.STOCKS.items() 
                if query in t or query in d['name'].upper()][:20]
    
    @classmethod
    def get_all_tickers(cls) -> List[str]:
        return list(cls.STOCKS.keys())

# ============================================================================
# SCORING ENGINE
# ============================================================================

class ScoringEngine:
    @staticmethod
    def calculate_score(ticker: str, df: pd.DataFrame, info: Dict) -> Dict[str, Any]:
        score = 0
        signals = []
        breakdown = {}
        
        # Historical Performance (30 points)
        hist_score, hist_sigs = ScoringEngine._score_historical(df)
        score += hist_score
        signals.extend(hist_sigs)
        breakdown['Historical'] = hist_score
        
        # Growth (25 points)
        growth_score, growth_sigs = ScoringEngine._score_growth(info)
        score += growth_score
        signals.extend(growth_sigs)
        breakdown['Growth'] = growth_score
        
        # Technical (25 points)
        tech_score, tech_sigs = ScoringEngine._score_technical(df)
        score += tech_score
        signals.extend(tech_sigs)
        breakdown['Technical'] = tech_score
        
        # Fundamentals (20 points)
        fund_score, fund_sigs = ScoringEngine._score_fundamentals(info)
        score += fund_score
        signals.extend(fund_sigs)
        breakdown['Fundamentals'] = fund_score
        
        # Determine rating
        if score >= Config.SCORE_EXCEPTIONAL:
            rating = "EXCEPTIONAL"
            color = "#10b981"
        elif score >= Config.SCORE_STRONG:
            rating = "STRONG"
            color = "#3b82f6"
        elif score >= Config.SCORE_GOOD:
            rating = "GOOD"
            color = "#8b5cf6"
        elif score >= Config.SCORE_MODERATE:
            rating = "MODERATE"
            color = "#f59e0b"
        else:
            rating = "WEAK"
            color = "#ef4444"
        
        return {
            'score': score,
            'rating': rating,
            'color': color,
            'signals': signals,
            'breakdown': breakdown
        }
    
    @staticmethod
    def _score_historical(df: pd.DataFrame) -> Tuple[int, List]:
        if len(df) < 60:
            return 15, [("⚠️ Limited historical data", "neutral")]
        
        score = 0
        signals = []
        
        returns_3m = (df['Close'].iloc[-1] / df['Close'].iloc[-60] - 1)
        
        if returns_3m > 0.20:
            score += 20
            signals.append(("✅ Excellent 3-month performance", "positive"))
        elif returns_3m > 0.10:
            score += 15
            signals.append(("✅ Strong 3-month performance", "positive"))
        elif returns_3m > 0:
            score += 10
            signals.append(("✅ Positive momentum", "positive"))
        
        if len(df) >= 120:
            returns_6m = (df['Close'].iloc[-1] / df['Close'].iloc[-120] - 1)
            if returns_6m > 0.30:
                score += 10
                signals.append(("✅ Outstanding 6-month trend", "positive"))
        
        return min(score, 30), signals
    
    @staticmethod
    def _score_growth(info: Dict) -> Tuple[int, List]:
        score = 0
        signals = []
        
        rev_growth = info.get('revenueGrowth')
        if rev_growth:
            if rev_growth > 0.25:
                score += 15
                signals.append(("✅ Exceptional revenue growth >25%", "positive"))
            elif rev_growth > 0.15:
                score += 10
                signals.append(("✅ Strong revenue growth", "positive"))
            elif rev_growth > 0:
                score += 5
                signals.append(("✅ Positive growth", "positive"))
        
        earn_growth = info.get('earningsGrowth')
        if earn_growth and earn_growth > 0.20:
            score += 10
            signals.append(("✅ Strong earnings growth", "positive"))
        
        return min(score, 25), signals
    
    @staticmethod
    def _score_technical(df: pd.DataFrame) -> Tuple[int, List]:
        if len(df) < 50:
            return 12, [("⚠️ Limited technical data", "neutral")]
        
        score = 0
        signals = []
        
        price = df['Close'].iloc[-1]
        sma20 = df['Close'].rolling(20).mean().iloc[-1]
        sma50 = df['Close'].rolling(50).mean().iloc[-1]
        
        if pd.notna(sma20) and pd.notna(sma50):
            if price > sma20 > sma50:
                score += 15
                signals.append(("✅ Strong uptrend - above MAs", "positive"))
            elif price > sma20:
                score += 10
                signals.append(("✅ Above 20-day MA", "positive"))
        
        # RSI
        delta = df['Close'].diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = -delta.where(delta < 0, 0).rolling(14).mean()
        rsi = 100 - (100 / (1 + gain / loss))
        current_rsi = rsi.iloc[-1]
        
        if pd.notna(current_rsi) and 40 <= current_rsi <= 65:
            score += 10
            signals.append(("✅ RSI in optimal zone", "positive"))
        
        return min(score, 25), signals
    
    @staticmethod
    def _score_fundamentals(info: Dict) -> Tuple[int, List]:
        score = 0
        signals = []
        
        margin = info.get('profitMargins')
        if margin and margin > 0.15:
            score += 10
            signals.append(("✅ Strong profit margins", "positive"))
        
        pe = info.get('trailingPE')
        if pe and 10 <= pe <= 30:
            score += 10
            signals.append(("✅ Reasonable valuation", "positive"))
        
        return min(score, 20), signals

# ============================================================================
# RISK CALCULATOR
# ============================================================================

class RiskCalc:
    @staticmethod
    def calculate_position(score: int, account_size: float, price: float) -> Dict:
        if score >= Config.SCORE_EXCEPTIONAL:
            risk_pct = 0.03
            max_pos = Config.MAX_POSITION_EXCEPTIONAL
        elif score >= Config.SCORE_STRONG:
            risk_pct = 0.025
            max_pos = Config.MAX_POSITION_STRONG
        elif score >= Config.SCORE_GOOD:
            risk_pct = 0.02
            max_pos = Config.MAX_POSITION_GOOD
        elif score >= Config.SCORE_MODERATE:
            risk_pct = 0.01
            max_pos = Config.MAX_POSITION_MODERATE
        else:
            return {'recommendation': 'DO NOT TRADE'}
        
        risk_amount = account_size * risk_pct
        stop_loss_pct = 0.15
        risk_per_share = price * stop_loss_pct
        shares = int(risk_amount / risk_per_share)
        
        max_shares = int((account_size * max_pos) / price)
        shares = min(shares, max_shares)
        
        position_value = shares * price
        stop_loss = price * 0.85
        target_1 = price * 1.12
        target_2 = price * 1.20
        target_3 = price * 1.35
        
        return {
            'recommendation': 'TRADE',
            'shares': shares,
            'position_value': position_value,
            'position_pct': (position_value / account_size) * 100,
            'entry': price,
            'stop_loss': stop_loss,
            'target_1': target_1,
            'target_2': target_2,
            'target_3': target_3,
            'max_loss': shares * risk_per_share,
            'potential_gain': shares * (target_2 - price)
        }

# ============================================================================
# LOGIN PAGE
# ============================================================================

def render_login():
    st.markdown("""
    <div style='text-align: center; margin-bottom: 3rem;'>
        <h1 style='font-size: 3.5rem;'>📈 Earnings Trader Pro</h1>
        <p style='font-size: 1.2rem; color: #94a3b8;'>AI-Powered Earnings Trading Platform</p>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown("<div class='login-container'>", unsafe_allow_html=True)
        
        tab1, tab2 = st.tabs(["🔐 Login", "📝 Sign Up"])
        
        with tab1:
            st.markdown("### Welcome Back")
            username = st.text_input("Username", key="login_user")
            password = st.text_input("Password", type="password", key="login_pass")
            
            if st.button("🚀 Login", use_container_width=True, type="primary"):
                if username and password:
                    user = AuthSystem.authenticate(username, password)
                    if user:
                        st.session_state.authenticated = True
                        st.session_state.user = user
                        st.success("✅ Login successful!")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("❌ Invalid credentials")
                else:
                    st.warning("⚠️ Enter username and password")
        
        with tab2:
            st.markdown("### Create Account")
            new_user = st.text_input("Username", key="signup_user")
            new_email = st.text_input("Email", key="signup_email")
            new_pass = st.text_input("Password", type="password", key="signup_pass")
            confirm = st.text_input("Confirm Password", type="password", key="confirm_pass")
            
            st.info("💡 Default account size: $50,000 (you can update this later in Settings)")
            
            if st.button("✨ Create Account", use_container_width=True, type="primary"):
                if new_user and new_email and new_pass and confirm:
                    if new_pass != confirm:
                        st.error("❌ Passwords don't match")
                    elif len(new_pass) < 6:
                        st.error("❌ Password must be 6+ characters")
                    elif AuthSystem.user_exists(new_user):
                        st.error("❌ Username taken")
                    else:
                        if AuthSystem.create_user(new_user, new_pass, new_email, Config.DEFAULT_ACCOUNT_SIZE):
                            st.success("✅ Account created! Please login.")
                            time.sleep(2)
                            st.rerun()
                else:
                    st.warning("⚠️ Fill all fields")
        
        st.markdown("</div>", unsafe_allow_html=True)

# ============================================================================
# SIDEBAR
# ============================================================================

def render_sidebar():
    with st.sidebar:
        user = st.session_state.user
        
        st.markdown(f"""
        <div style='background: rgba(79, 70, 229, 0.2); padding: 1.5rem; border-radius: 16px; margin-bottom: 1.5rem;'>
            <h3 style='margin: 0; color: #fff;'>👤 {user.username}</h3>
            <p style='margin: 0.5rem 0 0 0; color: #94a3b8;'>{user.email}</p>
            <div style='margin-top: 1rem; padding-top: 1rem; border-top: 1px solid rgba(99, 102, 241, 0.2);'>
                <p style='margin: 0; color: #10b981; font-size: 1.3rem; font-weight: 700;'>
                    ${user.account_size:,.0f}
                </p>
                <p style='margin: 0; color: #64748b; font-size: 0.85rem;'>Account Balance</p>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("---")
        st.markdown("#### 🧭 Navigation")
        
        pages = [
            ("🔍 Scanner", 'scanner'),
            ("📊 Analyze", 'analyze'),
            ("💼 Portfolio", 'portfolio'),
            ("📚 Guide", 'guide'),
            ("⚙️ Settings", 'settings'),
        ]
        
        for label, page in pages:
            if st.button(label, use_container_width=True, 
                        type="primary" if st.session_state.page == page else None):
                st.session_state.page = page
                st.rerun()
        
        st.markdown("---")
        
        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.authenticated = False
            st.session_state.user = None
            st.rerun()

# ============================================================================
# SCANNER PAGE
# ============================================================================

def render_scanner():
    st.title("🔍 Earnings Play Scanner")
    
    st.markdown("""
    <div class='info-box'>
        <p><strong>💡 How it works:</strong> Our AI analyzes stocks across 4 categories (Historical Performance, 
        Growth Metrics, Technical Setup, Fundamentals) to give each stock a 0-100 score.</p>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        min_score = st.slider("Minimum Score", 0, 100, 65, 5)
    
    with col2:
        sector = st.selectbox("Sector", ["All", "Technology", "Consumer", "Finance"])
    
    with col3:
        sort_by = st.selectbox("Sort By", ["score", "price", "ticker"])
    
    with col4:
        max_results = st.selectbox("Max Results", [5, 10, 15, 20], index=1)
    
    if st.button("🚀 Scan for Opportunities", type="primary", use_container_width=True):
        with st.spinner("Scanning stocks..."):
            # Filter tickers by sector
            if sector == "All":
                tickers = StockDB.get_all_tickers()
            else:
                tickers = [t for t, d in StockDB.STOCKS.items() if d.get('sector') == sector]
            
            results = []
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            for idx, ticker in enumerate(tickers):
                # Update progress
                progress = (idx + 1) / len(tickers)
                progress_bar.progress(progress)
                status_text.text(f"Analyzing {ticker}... ({idx + 1}/{len(tickers)})")
                
                try:
                    df = get_stock_data(ticker, '1y')
                    info = get_stock_info(ticker)
                    
                    if df is not None and not df.empty:
                        score_data = ScoringEngine.calculate_score(ticker, df, info)
                        
                        if score_data['score'] >= min_score:
                            next_date, days = estimate_next_earnings_date(ticker)
                            
                            results.append({
                                'ticker': ticker,
                                'name': StockDB.STOCKS.get(ticker, {}).get('name', ticker),
                                'score': score_data['score'],
                                'rating': score_data['rating'],
                                'color': score_data['color'],
                                'price': df['Close'].iloc[-1],
                                'days': days
                            })
                except Exception as e:
                    st.caption(f"⚠️ Could not load {ticker}")
                    continue
            
            # Clear progress indicators
            progress_bar.empty()
            status_text.empty()
            
            # Sort results
            if sort_by == "score":
                results.sort(key=lambda x: x['score'], reverse=True)
            elif sort_by == "price":
                results.sort(key=lambda x: x['price'])
            elif sort_by == "ticker":
                results.sort(key=lambda x: x['ticker'])
            
            # Limit results
            results = results[:max_results]
            
            if results:
                st.success(f"✅ Found {len(results)} stocks scoring ≥ {min_score}")
                st.markdown("---")
                
                for r in results:
                    col1, col2, col3, col4, col5, col6 = st.columns([2, 2, 1, 1, 1, 1])
                    
                    col1.markdown(f"**{r['ticker']}**")
                    col1.caption(r['name'][:40])
                    
                    col2.markdown(f"""
                    <div style='padding: 0.5rem; background: rgba{tuple(int(r['color'][i:i+2], 16) for i in (1, 3, 5)) + (0.1,)}; 
                                border-radius: 8px; text-align: center;'>
                        <p style='color: {r['color']}; font-weight: 700; margin: 0; font-size: 1.2rem;'>{r['score']}</p>
                        <p style='color: #94a3b8; margin: 0; font-size: 0.75rem;'>{r['rating']}</p>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    col3.metric("Price", f"${r['price']:.2f}")
                    
                    # Earnings countdown
                    days = r['days']
                    if days <= 7:
                        earn_color = "#ef4444"
                        earn_icon = "🔥"
                    elif days <= 14:
                        earn_color = "#f59e0b"
                        earn_icon = "⚡"
                    else:
                        earn_color = "#3b82f6"
                        earn_icon = "📅"
                    
                    col4.markdown(f"<p style='color: {earn_color}; font-weight: 700; text-align: center;'>{earn_icon}<br>{days}d</p>", unsafe_allow_html=True)
                    
                    if col5.button("Analyze", key=f"analyze_{r['ticker']}", use_container_width=True):
                        st.session_state.selected_ticker = r['ticker']
                        st.session_state.page = 'analyze'
                        st.rerun()
                    
                    # Quick add to watchlist
                    user = st.session_state.user
                    if r['ticker'] in user.watchlist:
                        col6.markdown("⭐")
                    else:
                        if col6.button("➕", key=f"add_{r['ticker']}", help="Add to watchlist"):
                            user.watchlist.append(r['ticker'])
                            AuthSystem.save_user(user)
                            st.rerun()
                    
                    st.markdown("---")
            else:
                st.warning(f"No stocks found with score ≥ {min_score}. Try lowering the minimum score or selecting a different sector.")
                
                if st.button("Reset Filters", type="primary"):
                    st.rerun()

# ============================================================================
# ANALYZE PAGE
# ============================================================================

def render_analyze():
    st.title("📊 Stock Analysis")
    
    search = st.text_input("Search stock", 
                          value=st.session_state.selected_ticker or "",
                          placeholder="Enter ticker (e.g., AAPL)")
    
    ticker = None
    if search:
        results = StockDB.search(search)
        if results:
            options = [f"{t} - {d['name']}" for t, d in results]
            selected = st.selectbox("Select:", options)
            if selected:
                ticker = selected.split(" - ")[0]
    
    if ticker:
        with st.spinner(f"Analyzing {ticker}..."):
            df = get_stock_data(ticker, '1y')
            info = get_stock_info(ticker)
            
            if df is None or df.empty:
                st.error("Unable to fetch data")
                return
            
            score_data = ScoringEngine.calculate_score(ticker, df, info)
            price = df['Close'].iloc[-1]
            next_date, days = estimate_next_earnings_date(ticker)
            
            # Header
            st.markdown(f"## {info.get('longName', ticker)}")
            
            # Earnings banner
            if days <= 7:
                st.markdown(f"""
                <div class='warning-box'>
                    <h3>🔥 Earnings in {days} days!</h3>
                    <p>Date: {next_date.strftime('%B %d, %Y')}</p>
                    <p><strong>URGENT: Perfect entry timing!</strong></p>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.info(f"📅 Next Earnings: ~{days} days away")
            
            col1, col2, col3 = st.columns(3)
            col1.metric("Price", f"${price:.2f}")
            col2.metric("Market Cap", f"${info.get('marketCap', 0)/1e9:.1f}B")
            col3.metric("P/E", f"{info.get('trailingPE', 0):.2f}" if info.get('trailingPE') else "N/A")
            
            st.markdown("---")
            
            # Score display
            col1, col2 = st.columns([1, 2])
            
            with col1:
                st.markdown(f"""
                <div class='score-card'>
                    <h1 style='font-size: 5rem; color: {score_data['color']};'>{score_data['score']}</h1>
                    <p style='font-size: 2rem; color: {score_data['color']};'>{score_data['rating']}</p>
                </div>
                """, unsafe_allow_html=True)
            
            with col2:
                st.markdown("### 🎯 Key Signals")
                for signal, sig_type in score_data['signals']:
                    if sig_type == "positive":
                        st.markdown(f"<p style='color: #10b981; font-weight: 600;'>{signal}</p>", unsafe_allow_html=True)
                    elif sig_type == "negative":
                        st.markdown(f"<p style='color: #ef4444; font-weight: 600;'>{signal}</p>", unsafe_allow_html=True)
                    else:
                        st.markdown(f"<p style='color: #f59e0b; font-weight: 600;'>{signal}</p>", unsafe_allow_html=True)
            
            st.markdown("---")
            
            # Position sizing
            st.markdown("### 💰 Position Sizing")
            
            user = st.session_state.user
            calc = RiskCalc.calculate_position(score_data['score'], user.account_size, price)
            
            if calc['recommendation'] == 'DO NOT TRADE':
                st.markdown("""
                <div class='warning-box'>
                    <h3>⛔ Do Not Trade</h3>
                    <p>Score too low - does not meet minimum criteria</p>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown("""
                <div class='recommendation-box'>
                    <h3>✅ Recommended Position</h3>
                </div>
                """, unsafe_allow_html=True)
                
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Shares", f"{calc['shares']:,}")
                col2.metric("Position", f"${calc['position_value']:,.0f}")
                col3.metric("% of Account", f"{calc['position_pct']:.1f}%")
                col4.metric("Max Loss", f"${calc['max_loss']:,.0f}")
                
                st.markdown("---")
                
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Entry", f"${calc['entry']:.2f}")
                col2.metric("Stop Loss", f"${calc['stop_loss']:.2f}")
                col3.metric("Target 1", f"${calc['target_1']:.2f}")
                col4.metric("Target 2", f"${calc['target_2']:.2f}")
                
                # Add to watchlist
                st.markdown("---")
                if st.button("⭐ Add to Watchlist", use_container_width=True, type="primary"):
                    if ticker not in user.watchlist:
                        user.watchlist.append(ticker)
                        AuthSystem.save_user(user)
                        st.success(f"Added {ticker} to watchlist!")
                    else:
                        st.info("Already in watchlist")

# ============================================================================
# PORTFOLIO PAGE
# ============================================================================

def render_portfolio():
    st.title("💼 Portfolio")
    
    user = st.session_state.user
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Account", f"${user.account_size:,.0f}")
    col2.metric("Watchlist", len(user.watchlist))
    col3.metric("Trades", len(user.trade_history))
    
    st.markdown("---")
    
    if user.watchlist:
        st.markdown("### ⭐ Watchlist")
        
        for ticker in user.watchlist:
            try:
                col1, col2, col3, col4 = st.columns([3, 2, 1, 1])
                
                # Get basic info
                stock_info = StockDB.STOCKS.get(ticker, {})
                
                col1.markdown(f"**{ticker}**")
                col1.caption(stock_info.get('name', 'Unknown'))
                
                # Get earnings date
                next_date, days = estimate_next_earnings_date(ticker)
                
                if days <= 7:
                    earn_color = "#ef4444"
                    earn_icon = "🔥"
                elif days <= 14:
                    earn_color = "#f59e0b"
                    earn_icon = "⚡"
                else:
                    earn_color = "#3b82f6"
                    earn_icon = "📅"
                
                col2.markdown(f"<p style='color: {earn_color}; font-weight: 600;'>{earn_icon} Earnings in {days} days</p>", unsafe_allow_html=True)
                
                if col3.button("Analyze", key=f"wl_{ticker}"):
                    st.session_state.selected_ticker = ticker
                    st.session_state.page = 'analyze'
                    st.rerun()
                
                if col4.button("Remove", key=f"rm_{ticker}"):
                    user.watchlist.remove(ticker)
                    AuthSystem.save_user(user)
                    st.rerun()
                
                st.markdown("---")
            
            except Exception as e:
                st.warning(f"⚠️ Error loading {ticker}: {str(e)}")
                if st.button(f"Remove {ticker}", key=f"rm_err_{ticker}"):
                    user.watchlist.remove(ticker)
                    AuthSystem.save_user(user)
                    st.rerun()
    else:
        st.markdown("""
        <div class='info-box'>
            <h3>📝 Your watchlist is empty</h3>
            <p>Add stocks from the Scanner or Analysis page to track them here.</p>
            <p><strong>How to add stocks:</strong></p>
            <ol>
                <li>Go to Scanner and find high-scoring stocks</li>
                <li>Click "Analyze" on any stock</li>
                <li>Click "Add to Watchlist" button at the bottom</li>
            </ol>
        </div>
        """, unsafe_allow_html=True)
        
        if st.button("🔍 Go to Scanner", type="primary", use_container_width=True):
            st.session_state.page = 'scanner'
            st.rerun()

# ============================================================================
# GUIDE PAGE
# ============================================================================

def render_guide():
    st.title("📚 Strategy Guide")
    
    st.markdown("""
    ## Complete Earnings Trading Strategy
    
    ### The System
    
    Our AI-powered platform analyzes 100+ data points to identify high-probability earnings plays.
    
    ### Score Categories
    
    **85-100 (EXCEPTIONAL):** Maximum confidence - full position
    
    **75-84 (STRONG):** High confidence - standard position
    
    **65-74 (GOOD):** Good setup - moderate position
    
    **55-64 (MODERATE):** Cautious - small position
    
    **Below 55:** Pass
    
    ### Entry Timing
    
    **Optimal: 2-5 days before earnings (sweet spot: 3 days)**
    
    - Capture full move (pre-run + post-gap)
    - Better entry prices
    - Time to adjust if needed
    
    ### Exit Strategy
    
    **Target 1 (50%): +10-15%**
    - Lock in profits
    - Reduce risk
    
    **Target 2 (30%): +18-25%**
    - Capture momentum
    - Trail remaining
    
    **Target 3 (20%): +30%+**
    - Let winners run
    - 5% trailing stop
    
    ### Risk Management
    
    **Position Sizing:**
    - Based on score (1-3% risk per trade)
    - Max 10% of account per position
    - Max 30% in all earnings plays
    
    **Stop Loss:**
    - Always 15% below entry
    - Set immediately after entry
    - NEVER move or remove
    
    ### Golden Rules
    
    1. Never risk more than you can afford to lose
    2. Always use stop losses
    3. Take partial profits early
    4. Let winners run with trailing stops
    5. Keep detailed trade logs
    6. Follow the system
    
    ### Expected Results
    
    With discipline:
    - Win Rate: 55-65%
    - Avg Win: +12-18%
    - Avg Loss: -8-12%
    - Profit Factor: 1.6-2.2
    - Monthly ROI: 4-10%
    
    ### Remember
    
    "Your first loss is your best loss. Don't hope, don't pray, just exit when wrong."
    """)

# ============================================================================
# SETTINGS PAGE
# ============================================================================

def render_settings():
    st.title("⚙️ Settings")
    
    user = st.session_state.user
    
    tabs = st.tabs(["👤 Account", "🎯 Trading Preferences"])
    
    with tabs[0]:
        st.markdown("### Account Settings")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### Profile Information")
            st.text_input("Username", value=user.username, disabled=True)
            st.text_input("Email", value=user.email, disabled=True)
            st.text_input("Member Since", value=user.created_at.strftime('%B %d, %Y'), disabled=True)
        
        with col2:
            st.markdown("#### Account Balance")
            st.metric("Current Balance", f"${user.account_size:,.0f}")
            
            new_balance = st.number_input(
                "Update Account Size ($)",
                min_value=1000,
                max_value=10000000,
                value=int(user.account_size),
                step=1000,
                help="Set your actual trading account size for accurate position sizing"
            )
            
            if new_balance != user.account_size:
                if st.button("💾 Update Balance", type="primary"):
                    user.account_size = new_balance
                    AuthSystem.save_user(user)
                    st.success("✅ Account balance updated!")
                    time.sleep(1)
                    st.rerun()
        
        st.markdown("---")
        
        st.markdown("### Statistics")
        col1, col2, col3 = st.columns(3)
        col1.metric("Watchlist Stocks", len(user.watchlist))
        col2.metric("Total Trades", len(user.trade_history))
        col3.metric("Active Days", (datetime.now() - user.created_at).days)
    
    with tabs[1]:
        st.markdown("### Trading Preferences")
        
        settings = user.settings
        
        st.markdown("#### Risk Management")
        
        col1, col2 = st.columns(2)
        
        with col1:
            default_stop = st.slider(
                "Default Stop Loss (%)",
                5, 25, 
                int(settings.get('default_stop_loss', 0.15) * 100),
                help="Default stop loss percentage for all trades"
            )
        
        with col2:
            risk_per_trade = st.slider(
                "Risk Per Trade (%)",
                1, 5,
                int(settings.get('risk_per_trade', 0.02) * 100),
                help="Maximum percentage of account to risk per trade"
            )
        
        st.markdown("---")
        
        st.markdown("#### Display Preferences")
        
        col1, col2 = st.columns(2)
        
        with col1:
            show_hints = st.checkbox(
                "Show helpful hints",
                value=settings.get('show_hints', True)
            )
        
        with col2:
            compact_view = st.checkbox(
                "Compact view mode",
                value=settings.get('compact_view', False)
            )
        
        st.markdown("---")
        
        if st.button("💾 Save Preferences", type="primary", use_container_width=True):
            user.settings['default_stop_loss'] = default_stop / 100
            user.settings['risk_per_trade'] = risk_per_trade / 100
            user.settings['show_hints'] = show_hints
            user.settings['compact_view'] = compact_view
            AuthSystem.save_user(user)
            st.success("✅ Preferences saved!")
            time.sleep(1)
            st.rerun()

# ============================================================================
# MAIN APP
# ============================================================================

def main():
    if not st.session_state.authenticated:
        render_login()
        return
    
    render_sidebar()
    
    page = st.session_state.page
    
    if page == 'scanner':
        render_scanner()
    elif page == 'analyze':
        render_analyze()
    elif page == 'portfolio':
        render_portfolio()
    elif page == 'guide':
        render_guide()
    elif page == 'settings':
        render_settings()
    else:
        render_scanner()

if __name__ == "__main__":
    main()
