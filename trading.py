import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from supabase import create_client

# =============================================================================
# PAGE CONFIG
# =============================================================================
st.set_page_config(
    page_title="WealthStockify Professional",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =============================================================================
# INITIALIZE SUPABASE
# =============================================================================
@st.cache_resource
def init_supabase():
    try:
        return create_client(st.secrets["supabase"]["url"], st.secrets["supabase"]["key"])
    except:
        return None

supabase = init_supabase()

# =============================================================================
# CSS STYLING
# =============================================================================
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    * {font-family: 'Inter', sans-serif;}
    .stApp {background: linear-gradient(180deg, #0f172a 0%, #1e293b 100%);}
    h1, h2, h3 {color: #f1f5f9 !important; font-weight: 600 !important;}
    .stButton > button {
        background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
        color: white; border: none; border-radius: 8px;
        padding: 0.625rem 1.25rem; font-weight: 500;
        box-shadow: 0 4px 6px -1px rgba(59, 130, 246, 0.3);
    }
    .stButton > button:hover {
        background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%);
        transform: translateY(-1px);
    }
</style>
""", unsafe_allow_html=True)

# =============================================================================
# SESSION STATE
# =============================================================================
for key in ['authenticated', 'user', 'profile', 'page']:
    if key not in st.session_state:
        st.session_state[key] = None if key != 'page' else 'dashboard'

# =============================================================================
# AUTH SERVICE
# =============================================================================
class AuthService:
    @staticmethod
    def signup(email, password):
        try:
            res = supabase.auth.sign_up({"email": email, "password": password})
            return res.user is not None, "Success" if res.user else "Failed"
        except Exception as e:
            return False, str(e)
    
    @staticmethod
    def signin(email, password):
        try:
            res = supabase.auth.sign_in_with_password({"email": email, "password": password})
            if res.user:
                profile = supabase.table('user_profiles').select('*').eq('id', res.user.id).single().execute()
                return True, res.user, profile.data if profile.data else {'is_premium': False}
            return False, None, None
        except:
            return False, None, None
    
    @staticmethod
    def signout():
        try:
            supabase.auth.sign_out()
        except:
            pass
        for key in list(st.session_state.keys()):
            del st.session_state[key]
    
    @staticmethod
    def reset_password(email):
        try:
            supabase.auth.reset_password_for_email(email)
            return True, "Reset email sent"
        except Exception as e:
            return False, str(e)

# =============================================================================
# DATABASE SERVICE
# =============================================================================
class DatabaseService:
    @staticmethod
    def get_profile(user_id):
        try:
            res = supabase.table('user_profiles').select('*').eq('id', user_id).single().execute()
            return res.data if res.data else {'is_premium': False}
        except:
            return {'is_premium': False}
    
    @staticmethod
    def upgrade_premium(user_id):
        try:
            user_email = st.session_state.user.email
            end_date = (datetime.now() + timedelta(days=30)).isoformat()
            supabase.table('user_profiles').upsert({
                'id': user_id,
                'email': user_email,
                'is_premium': True,
                'subscription_end_date': end_date
            }).execute()
            return True
        except:
            return False
    
    @staticmethod
    def downgrade_premium(user_id):
        try:
            supabase.table('user_profiles').update({
                'is_premium': False,
                'subscription_end_date': None
            }).eq('id', user_id).execute()
            return True
        except:
            return False
    
    @staticmethod
    def get_watchlist(user_id):
        try:
            res = supabase.table('watchlists').select('*').eq('user_id', user_id).execute()
            return res.data if res.data else []
        except:
            return []
    
    @staticmethod
    def add_watchlist(user_id, ticker):
        try:
            existing = supabase.table('watchlists').select('ticker').eq('user_id', user_id).eq('ticker', ticker).execute()
            if existing.data:
                return False
            supabase.table('watchlists').insert({
                'user_id': user_id,
                'ticker': ticker,
                'created_at': datetime.now().isoformat()
            }).execute()
            return True
        except:
            return False
    
    @staticmethod
    def remove_watchlist(user_id, ticker):
        try:
            supabase.table('watchlists').delete().eq('user_id', user_id).eq('ticker', ticker).execute()
            return True
        except:
            return False
    
    @staticmethod
    def get_portfolio(user_id):
        try:
            res = supabase.table('portfolio').select('*').eq('user_id', user_id).execute()
            return res.data if res.data else []
        except:
            return []
    
    @staticmethod
    def add_portfolio(user_id, ticker, shares, avg_price, purchase_date):
        try:
            existing = supabase.table('portfolio').select('*').eq('user_id', user_id).eq('ticker', ticker).execute()
            if existing.data:
                old = existing.data[0]
                total_shares = old['shares'] + shares
                new_avg = ((old['shares'] * old['average_price']) + (shares * avg_price)) / total_shares
                supabase.table('portfolio').update({
                    'shares': total_shares,
                    'average_price': new_avg
                }).eq('user_id', user_id).eq('ticker', ticker).execute()
            else:
                supabase.table('portfolio').insert({
                    'user_id': user_id,
                    'ticker': ticker,
                    'shares': shares,
                    'average_price': avg_price,
                    'purchase_date': purchase_date
                }).execute()
            return True
        except:
            return False
    
    @staticmethod
    def remove_portfolio(user_id, ticker):
        try:
            supabase.table('portfolio').delete().eq('user_id', user_id).eq('ticker', ticker).execute()
            return True
        except:
            return False

# =============================================================================
# TECHNICAL ANALYSIS
# =============================================================================
class TechnicalAnalysis:
    @staticmethod
    def add_indicators(df):
        delta = df['Close'].diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = -delta.where(delta < 0, 0).rolling(14).mean()
        df['RSI'] = 100 - (100 / (1 + gain / loss))
        
        ema12 = df['Close'].ewm(span=12).mean()
        ema26 = df['Close'].ewm(span=26).mean()
        df['MACD'] = ema12 - ema26
        df['MACD_Signal'] = df['MACD'].ewm(span=9).mean()
        
        df['SMA20'] = df['Close'].rolling(20).mean()
        df['SMA50'] = df['Close'].rolling(50).mean()
        df['SMA200'] = df['Close'].rolling(200).mean()
        
        std = df['Close'].rolling(20).std()
        df['BB_Upper'] = df['SMA20'] + (std * 2)
        df['BB_Lower'] = df['SMA20'] - (std * 2)
        
        hl = df['High'] - df['Low']
        hc = abs(df['High'] - df['Close'].shift())
        lc = abs(df['Low'] - df['Close'].shift())
        df['ATR'] = pd.concat([hl, hc, lc], axis=1).max(axis=1).rolling(14).mean()
        
        df['Volume_SMA'] = df['Volume'].rolling(20).mean()
        df['Volume_Ratio'] = df['Volume'] / df['Volume_SMA']
        
        return df
    
    @staticmethod
    def calculate_score(df, info):
        score = 50
        try:
            price = df['Close'].iloc[-1]
            rsi = df['RSI'].iloc[-1]
            
            if 40 <= rsi <= 60:
                score += 10
            if df['MACD'].iloc[-1] > df['MACD_Signal'].iloc[-1]:
                score += 10
            if price > df['SMA50'].iloc[-1] > df['SMA200'].iloc[-1]:
                score += 15
            
            pe = info.get('trailingPE', 0)
            if 10 <= pe <= 25:
                score += 15
            if info.get('profitMargins', 0) > 0.15:
                score += 10
        except:
            pass
        return max(0, min(100, score))

# =============================================================================
# POSITION SIZING & RISK
# =============================================================================
class PositionManager:
    @staticmethod
    def calculate_size(account, price, volatility, method='kelly', risk_pct=0.02, win_rate=0.55, avg_win=2.0, avg_loss=1.0):
        results = {}
        
        if method in ['kelly', 'all']:
            q = 1 - win_rate
            b = avg_win / avg_loss
            kelly = (win_rate * b - q) / b
            kelly = max(0, min(kelly * 0.5, 0.25))
            shares = int((account * kelly) / price)
            results['kelly'] = {'shares': shares, 'value': shares * price, 'pct': kelly * 100}
        
        if method in ['fixed', 'all']:
            shares = int((account * risk_pct) / price)
            results['fixed'] = {'shares': shares, 'value': shares * price, 'pct': (shares * price / account) * 100}
        
        if method in ['volatility', 'all']:
            shares = int((account * risk_pct) / (volatility * price))
            results['volatility'] = {'shares': shares, 'value': shares * price, 'pct': (shares * price / account) * 100}
        
        return results
    
    @staticmethod
    def calculate_stops(entry, atr, rr=2.0):
        stop = entry - (2 * atr)
        risk = entry - stop
        target = entry + (risk * rr)
        return {
            'entry': entry,
            'stop': stop,
            'target': target,
            'risk': risk,
            'reward': target - entry,
            'rr': rr,
            'stop_pct': ((entry - stop) / entry) * 100,
            'target_pct': ((target - entry) / entry) * 100
        }

# =============================================================================
# AUTHENTICATION UI
# =============================================================================
if not st.session_state.authenticated:
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown("<h1 style='text-align: center;'>WealthStockify</h1>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; color: #94a3b8;'>Professional Stock Analysis Platform</p>", unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)
        
        tab1, tab2, tab3 = st.tabs(["Sign In", "Create Account", "Reset Password"])
        
        with tab1:
            with st.form("signin"):
                email = st.text_input("Email")
                password = st.text_input("Password", type="password")
                if st.form_submit_button("Sign In", use_container_width=True):
                    success, user, profile = AuthService.signin(email, password)
                    if success:
                        st.session_state.authenticated = True
                        st.session_state.user = user
                        st.session_state.profile = profile
                        st.rerun()
                    else:
                        st.error("Invalid credentials")
        
        with tab2:
            with st.form("signup"):
                email = st.text_input("Email", key="signup_email")
                password = st.text_input("Password (6+ chars)", type="password", key="signup_pass")
                confirm = st.text_input("Confirm Password", type="password")
                if st.form_submit_button("Create Account", use_container_width=True):
                    if password != confirm:
                        st.error("Passwords don't match")
                    elif len(password) < 6:
                        st.error("Password too short")
                    else:
                        success, msg = AuthService.signup(email, password)
                        st.success("Account created! Please sign in.") if success else st.error(msg)
        
        with tab3:
            with st.form("reset"):
                email = st.text_input("Email", key="reset_email")
                if st.form_submit_button("Send Reset Link", use_container_width=True):
                    success, msg = AuthService.reset_password(email)
                    st.success(msg) if success else st.error(msg)
    
    st.stop()

# =============================================================================
# MAIN APP
# =============================================================================
is_premium = st.session_state.profile.get('is_premium', False)

# Sidebar
with st.sidebar:
    st.title("WealthStockify")
    st.caption(st.session_state.user.email)
    st.markdown("---")
    
    if is_premium:
        st.success("Premium Active")
        if st.button("Downgrade", use_container_width=True):
            if DatabaseService.downgrade_premium(st.session_state.user.id):
                st.session_state.profile = DatabaseService.get_profile(st.session_state.user.id)
                st.rerun()
    else:
        st.info("Free Tier")
        if st.button("Upgrade - $9.99/mo", use_container_width=True, type="primary"):
            if DatabaseService.upgrade_premium(st.session_state.user.id):
                st.session_state.profile = DatabaseService.get_profile(st.session_state.user.id)
                st.balloons()
                st.rerun()
    
    st.markdown("---")
    
    if st.button("Sign Out", use_container_width=True):
        AuthService.signout()
        st.rerun()
    
    st.markdown("---")
    st.caption("Premium Features")
    for f in ["AI Scoring", "Advanced Charts", "Stock Screener", "Backtesting", "Position Sizer", "Watchlist", "Portfolio"]:
        st.caption(f"{'✓' if is_premium else '✗'} {f}")

# Navigation
pages = ["Dashboard", "Analysis", "Screener", "Backtest", "Position Sizer", "Watchlist", "Portfolio"]
cols = st.columns(len(pages))
for i, (col, page) in enumerate(zip(cols, pages)):
    with col:
        if st.button(page, use_container_width=True, key=f"nav_{page}"):
            st.session_state.page = page.lower().replace(' ', '_')

st.markdown("---")

# Pages
if st.session_state.page == 'dashboard':
    st.title("Dashboard")
    col1, col2, col3 = st.columns(3)
    col1.metric("Account", "Premium" if is_premium else "Free")
    col2.metric("Watchlist", len(DatabaseService.get_watchlist(st.session_state.user.id)))
    col3.metric("Portfolio", len(DatabaseService.get_portfolio(st.session_state.user.id)))

elif st.session_state.page == 'analysis':
    st.title("Stock Analysis")
    
    col1, col2 = st.columns([3, 1])
    with col1:
        ticker = st.text_input("Ticker", "AAPL").upper()
    with col2:
        period = st.selectbox("Period", ["1mo", "3mo", "6mo", "1y"])
    
    if ticker:
        try:
            stock = yf.Ticker(ticker)
            df = stock.history(period=period)
            info = stock.info
            
            if not df.empty:
                df = TechnicalAnalysis.add_indicators(df)
                price = df['Close'].iloc[-1]
                
                col1, col2, col3 = st.columns(3)
                col1.metric("Price", f"${price:.2f}")
                col2.metric("AI Score", f"{TechnicalAnalysis.calculate_score(df, info):.0f}/100" if is_premium else "Premium")
                col3.metric("Volume", f"{info.get('volume', 0)/1e6:.1f}M")
                
                fig = go.Figure()
                fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close']))
                if is_premium:
                    fig.add_trace(go.Scatter(x=df.index, y=df['SMA50'], name='SMA50', line=dict(color='orange')))
                fig.update_layout(height=600, template='plotly_dark', xaxis_rangeslider_visible=False)
                st.plotly_chart(fig, use_container_width=True)
        except Exception as e:
            st.error(f"Error: {e}")

elif st.session_state.page == 'position_sizer':
    st.title("Position Size Manager")
    
    if is_premium:
        col1, col2 = st.columns(2)
        with col1:
            ticker = st.text_input("Ticker", "AAPL").upper()
            account = st.number_input("Account Size", 100000, step=1000)
            risk_pct = st.slider("Risk %", 0.5, 5.0, 2.0) / 100
        with col2:
            method = st.selectbox("Method", ["Kelly Criterion", "Fixed Risk", "Volatility", "All"])
            rr = st.slider("Risk/Reward", 1.0, 5.0, 2.0)
        
        if st.button("Calculate", type="primary"):
            try:
                stock = yf.Ticker(ticker)
                hist = stock.history(period='3mo')
                df = TechnicalAnalysis.add_indicators(hist)
                
                price = df['Close'].iloc[-1]
                vol = df['Close'].pct_change().std()
                atr = df['ATR'].iloc[-1]
                
                method_map = {"Kelly Criterion": "kelly", "Fixed Risk": "fixed", "Volatility": "volatility", "All": "all"}
                sizes = PositionManager.calculate_size(account, price, vol, method_map[method], risk_pct)
                stops = PositionManager.calculate_stops(price, atr, rr)
                
                st.subheader("Results")
                if method == "All":
                    for m, data in sizes.items():
                        st.write(f"**{m.title()}:** {data['shares']} shares (${data['value']:,.0f})")
                else:
                    data = sizes[method_map[method]]
                    col1, col2, col3 = st.columns(3)
                    col1.metric("Shares", data['shares'])
                    col2.metric("Value", f"${data['value']:,.0f}")
                    col3.metric("% Account", f"{data['pct']:.1f}%")
                
                st.markdown("---")
                st.subheader("Risk Management")
                col1, col2, col3 = st.columns(3)
                col1.metric("Entry", f"${stops['entry']:.2f}")
                col2.metric("Stop Loss", f"${stops['stop']:.2f}", f"-{stops['stop_pct']:.1f}%")
                col3.metric("Target", f"${stops['target']:.2f}", f"+{stops['target_pct']:.1f}%")
            except Exception as e:
                st.error(f"Error: {e}")
    else:
        st.warning("Premium feature")

elif st.session_state.page == 'watchlist':
    st.title("Watchlist")
    
    if is_premium:
        col1, col2 = st.columns([3, 1])
        with col1:
            new = st.text_input("Add ticker").upper()
        with col2:
            st.write("")
            st.write("")
            if st.button("Add"):
                if DatabaseService.add_watchlist(st.session_state.user.id, new):
                    st.success("Added")
                    st.rerun()
                else:
                    st.warning("Already in watchlist")
        
        watchlist = DatabaseService.get_watchlist(st.session_state.user.id)
        for item in watchlist:
            col1, col2 = st.columns([4, 1])
            col1.write(item['ticker'])
            if col2.button("Remove", key=item['ticker']):
                DatabaseService.remove_watchlist(st.session_state.user.id, item['ticker'])
                st.rerun()
    else:
        st.warning("Premium feature")

elif st.session_state.page == 'portfolio':
    st.title("Portfolio")
    
    if is_premium:
        with st.expander("Add Position"):
            col1, col2, col3 = st.columns(3)
            ticker = col1.text_input("Ticker").upper()
            shares = col2.number_input("Shares", 0.0, step=0.1)
            price = col3.number_input("Avg Price", 0.0, step=0.01)
            
            if st.button("Add"):
                if DatabaseService.add_portfolio(st.session_state.user.id, ticker, shares, price, datetime.now().date().isoformat()):
                    st.success("Added")
                    st.rerun()
        
        portfolio = DatabaseService.get_portfolio(st.session_state.user.id)
        for pos in portfolio:
            col1, col2 = st.columns([4, 1])
            col1.write(f"{pos['ticker']}: {pos['shares']} @ ${pos['average_price']:.2f}")
            if col2.button("Remove", key=pos['ticker']):
                DatabaseService.remove_portfolio(st.session_state.user.id, pos['ticker'])
                st.rerun()
    else:
        st.warning("Premium feature")

else:
    st.info(f"{st.session_state.page} - Coming soon")

st.markdown("---")
st.caption("WealthStockify © 2025")
