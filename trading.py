import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from supabase import create_client, Client

st.set_page_config(page_title="WealthStockify", page_icon="📈", layout="wide")

# Initialize Supabase
@st.cache_resource
def init_supabase():
    try:
        return create_client(st.secrets["supabase"]["url"], st.secrets["supabase"]["key"])
    except:
        return None

supabase = init_supabase()

# CSS
st.markdown("""
<style>
    .stApp {background: #0a0e17;}
    h1, h2, h3 {color: #fff !important;}
    .stButton>button {
        background: #1e293b;
        color: #fff;
        border: 1px solid #334155;
        border-radius: 6px;
        padding: 0.5rem 1rem;
        font-weight: 500;
        transition: 0.2s;
    }
    .stButton>button:hover {background: #334155;}
    .metric-container {
        background: #1e293b;
        padding: 1rem;
        border-radius: 8px;
        border: 1px solid #334155;
    }
</style>
""", unsafe_allow_html=True)

# Session State Init
for key in ['auth', 'user', 'profile', 'page']:
    if key not in st.session_state:
        st.session_state[key] = None if key != 'page' else 'analysis'

# Auth Functions
class Auth:
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
        except Exception as e:
            return False, None, str(e)
    
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

# Database Functions
class DB:
    @staticmethod
    def upgrade_premium(user_id):
        try:
            supabase.table('user_profiles').upsert({
                'id': user_id,
                'is_premium': True,
                'subscription_end_date': (datetime.now() + timedelta(days=30)).isoformat()
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
    def get_profile(user_id):
        try:
            res = supabase.table('user_profiles').select('*').eq('id', user_id).single().execute()
            return res.data if res.data else {'is_premium': False}
        except:
            return {'is_premium': False}
    
    @staticmethod
    def get_watchlist(user_id):
        try:
            res = supabase.table('watchlists').select('ticker').eq('user_id', user_id).execute()
            return [item['ticker'] for item in res.data]
        except:
            return []
    
    @staticmethod
    def add_watchlist(user_id, ticker):
        try:
            supabase.table('watchlists').insert({'user_id': user_id, 'ticker': ticker}).execute()
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

# Analysis Functions
class Analysis:
    @staticmethod
    def add_indicators(df):
        delta = df['Close'].diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = -delta.where(delta < 0, 0).rolling(14).mean()
        df['RSI'] = 100 - (100 / (1 + gain / loss))
        
        ema12 = df['Close'].ewm(span=12).mean()
        ema26 = df['Close'].ewm(span=26).mean()
        df['MACD'] = ema12 - ema26
        df['Signal'] = df['MACD'].ewm(span=9).mean()
        
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
        
        return df
    
    @staticmethod
    def calculate_score(df, info):
        score = 50
        try:
            price = df['Close'].iloc[-1]
            rsi = df['RSI'].iloc[-1]
            macd = df['MACD'].iloc[-1]
            signal = df['Signal'].iloc[-1]
            sma50 = df['SMA50'].iloc[-1]
            sma200 = df['SMA200'].iloc[-1]
            
            if 40 <= rsi <= 60: score += 10
            elif 30 <= rsi <= 70: score += 5
            if macd > signal: score += 10
            if price > sma50 > sma200: score += 15
            elif price > sma50: score += 8
            
            pe = info.get('trailingPE', 0)
            if 10 <= pe <= 25: score += 15
            if info.get('profitMargins', 0) > 0.15: score += 10
            if info.get('returnOnEquity', 0) > 0.15: score += 10
        except:
            pass
        return max(0, min(100, score))
    
    @staticmethod
    def predict_price(df, days=30):
        try:
            recent = df.tail(90).copy()
            recent['idx'] = range(len(recent))
            X, y = recent['idx'].values, recent['Close'].values
            slope = ((X - X.mean()) * (y - y.mean())).sum() / ((X - X.mean()) ** 2).sum()
            intercept = y.mean() - slope * X.mean()
            momentum = (df['Close'].iloc[-1] - df['Close'].iloc[-30]) / df['Close'].iloc[-30]
            return max(0, (slope * (1 + momentum * 0.5)) * (len(recent) + days) + intercept)
        except:
            return None
    
    @staticmethod
    def run_backtest(ticker, start, end, capital=10000):
        try:
            df = yf.Ticker(ticker).history(start=start, end=end)
            if df.empty: return None
            
            df = Analysis.add_indicators(df)
            df['Signal'] = 0
            
            for i in range(1, len(df)):
                if pd.notna(df['MACD'].iloc[i]) and pd.notna(df['RSI'].iloc[i]):
                    if df['MACD'].iloc[i] > df['Signal'].iloc[i] and df['RSI'].iloc[i] < 70:
                        df.loc[df.index[i], 'Signal'] = 1
                    elif df['MACD'].iloc[i] < df['Signal'].iloc[i]:
                        df.loc[df.index[i], 'Signal'] = -1
            
            df['Position'] = df['Signal'].replace(0, np.nan).ffill().fillna(0)
            df['Returns'] = df['Close'].pct_change()
            df['Strategy'] = df['Position'].shift(1) * df['Returns']
            df['Cumulative'] = (1 + df['Returns']).cumprod()
            df['CumulativeStrategy'] = (1 + df['Strategy']).cumprod()
            
            total_return = (df['CumulativeStrategy'].iloc[-1] - 1) * 100
            buy_hold = (df['Cumulative'].iloc[-1] - 1) * 100
            trades = len(df[df['Signal'] != 0])
            sharpe = np.sqrt(252) * df['Strategy'].mean() / df['Strategy'].std() if df['Strategy'].std() > 0 else 0
            
            cumulative = df['CumulativeStrategy']
            drawdown = ((cumulative - cumulative.expanding().max()) / cumulative.expanding().max()).min() * 100
            
            return {
                'df': df,
                'total_return': total_return,
                'buy_hold': buy_hold,
                'trades': trades,
                'sharpe': sharpe,
                'drawdown': drawdown
            }
        except:
            return None

# Auth Screen
if not st.session_state.auth:
    st.title("WealthStockify")
    st.markdown("Premium Stock Analysis Platform")
    
    tab1, tab2, tab3 = st.tabs(["Login", "Sign Up", "Reset Password"])
    
    with tab1:
        with st.form("login"):
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            submit = st.form_submit_button("Login", use_container_width=True)
            
            if submit and email and password:
                success, user, profile = Auth.signin(email, password)
                if success:
                    st.session_state.auth = True
                    st.session_state.user = user
                    st.session_state.profile = profile
                    st.rerun()
                else:
                    st.error("Invalid credentials")
    
    with tab2:
        with st.form("signup"):
            email = st.text_input("Email", key="signup_email")
            password = st.text_input("Password (6+ chars)", type="password", key="signup_password")
            confirm = st.text_input("Confirm Password", type="password")
            submit = st.form_submit_button("Sign Up", use_container_width=True)
            
            if submit:
                if password != confirm:
                    st.error("Passwords don't match")
                elif len(password) < 6:
                    st.error("Password too short")
                else:
                    success, msg = Auth.signup(email, password)
                    if success:
                        st.success("Account created! Please login.")
                    else:
                        st.error(msg)
    
    with tab3:
        with st.form("reset"):
            email = st.text_input("Email", key="reset_email")
            submit = st.form_submit_button("Send Reset Link", use_container_width=True)
            
            if submit and email:
                success, msg = Auth.reset_password(email)
                st.success(msg) if success else st.error(msg)
    
    st.stop()

# Main App
is_premium = st.session_state.profile.get('is_premium', False)

# Sidebar
with st.sidebar:
    st.title("WealthStockify")
    st.caption(st.session_state.user.email)
    
    st.markdown("---")
    
    if is_premium:
        st.success("Premium Active")
        if st.button("Downgrade", use_container_width=True):
            if DB.downgrade_premium(st.session_state.user.id):
                st.session_state.profile = DB.get_profile(st.session_state.user.id)
                st.rerun()
    else:
        st.info("Free Tier")
        if st.button("Upgrade - $9.99/mo", use_container_width=True, type="primary"):
            if DB.upgrade_premium(st.session_state.user.id):
                st.session_state.profile = DB.get_profile(st.session_state.user.id)
                st.balloons()
                st.rerun()
    
    st.markdown("---")
    
    if st.button("Logout", use_container_width=True):
        Auth.signout()
        st.rerun()
    
    st.markdown("---")
    
    st.caption("Premium Features")
    features = ["AI Scoring", "Advanced Charts", "Stock Screener", "Backtesting", "Predictions", "Watchlist"]
    for f in features:
        st.caption(f"{'✓' if is_premium else '✗'} {f}")

# Navigation
cols = st.columns(5)
pages = ["Analysis", "Screener", "Backtest", "Watchlist", "Calculator"]
for i, (col, page) in enumerate(zip(cols, pages)):
    with col:
        if st.button(page, use_container_width=True, key=f"nav_{page}"):
            st.session_state.page = page.lower()

st.markdown("---")

# Stock Analysis
if st.session_state.page == 'analysis':
    st.header("Stock Analysis")
    
    col1, col2 = st.columns([3, 1])
    with col1:
        ticker = st.text_input("Ticker", "AAPL").upper()
    with col2:
        period = st.selectbox("Period", ["1mo", "3mo", "6mo", "1y", "2y", "5y"], index=2)
    
    if ticker:
        try:
            stock = yf.Ticker(ticker)
            df = stock.history(period=period)
            info = stock.info
            
            if not df.empty:
                df = Analysis.add_indicators(df)
                price = df['Close'].iloc[-1]
                prev = df['Close'].iloc[-2]
                change = ((price - prev) / prev) * 100
                
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Price", f"${price:.2f}", f"{change:+.2f}%")
                col2.metric("AI Score", f"{Analysis.calculate_score(df, info):.0f}/100" if is_premium else "Premium")
                col3.metric("Volume", f"{info.get('volume', 0)/1e6:.1f}M")
                col4.metric("Market Cap", f"${info.get('marketCap', 0)/1e9:.1f}B")
                
                st.markdown("---")
                
                fig = make_subplots(rows=3 if is_premium else 1, cols=1, shared_xaxes=True,
                                   vertical_spacing=0.05, row_heights=[0.6, 0.2, 0.2] if is_premium else [1])
                
                fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'],
                                            low=df['Low'], close=df['Close'], name='Price'), row=1, col=1)
                
                if is_premium:
                    fig.add_trace(go.Scatter(x=df.index, y=df['SMA50'], name='SMA50', line=dict(color='orange')), row=1, col=1)
                    fig.add_trace(go.Scatter(x=df.index, y=df['SMA200'], name='SMA200', line=dict(color='red')), row=1, col=1)
                    fig.add_trace(go.Scatter(x=df.index, y=df['MACD'], name='MACD', line=dict(color='blue')), row=2, col=1)
                    fig.add_trace(go.Scatter(x=df.index, y=df['Signal'], name='Signal', line=dict(color='red')), row=2, col=1)
                    fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], name='RSI', line=dict(color='purple')), row=3, col=1)
                
                fig.update_layout(height=700, template='plotly_dark', xaxis_rangeslider_visible=False, showlegend=True)
                st.plotly_chart(fig, use_container_width=True)
                
                if is_premium:
                    col1, col2 = st.columns(2)
                    with col1:
                        st.subheader("Fundamentals")
                        st.write(f"P/E: {info.get('trailingPE', 'N/A')}")
                        st.write(f"Dividend: {info.get('dividendYield', 0)*100:.2f}%")
                    with col2:
                        st.subheader("Prediction")
                        pred = Analysis.predict_price(df, 30)
                        if pred:
                            pred_change = ((pred - price) / price) * 100
                            st.metric("30-Day Forecast", f"${pred:.2f}", f"{pred_change:+.2f}%")
        except Exception as e:
            st.error(f"Error: {e}")

elif st.session_state.page == 'watchlist':
    st.header("Watchlist")
    
    if is_premium:
        col1, col2 = st.columns([3, 1])
        with col1:
            new_ticker = st.text_input("Add ticker").upper()
        with col2:
            st.write("")
            st.write("")
            if st.button("Add"):
                if new_ticker and DB.add_watchlist(st.session_state.user.id, new_ticker):
                    st.rerun()
        
        watchlist = DB.get_watchlist(st.session_state.user.id)
        if watchlist:
            for ticker in watchlist:
                col1, col2 = st.columns([4, 1])
                with col1:
                    st.write(ticker)
                with col2:
                    if st.button("X", key=f"del_{ticker}"):
                        DB.remove_watchlist(st.session_state.user.id, ticker)
                        st.rerun()
        else:
            st.info("Empty watchlist")
    else:
        st.warning("Premium feature")

elif st.session_state.page == 'backtest':
    st.header("Backtesting")
    
    if is_premium:
        col1, col2, col3 = st.columns(3)
        with col1:
            ticker = st.text_input("Ticker", "AAPL").upper()
        with col2:
            start = st.date_input("Start", datetime.now() - timedelta(days=365))
        with col3:
            end = st.date_input("End", datetime.now())
        
        if st.button("Run Backtest"):
            with st.spinner("Running..."):
                result = Analysis.run_backtest(ticker, start, end)
                
                if result:
                    col1, col2, col3, col4 = st.columns(4)
                    col1.metric("Return", f"{result['total_return']:.2f}%")
                    col2.metric("Buy & Hold", f"{result['buy_hold']:.2f}%")
                    col3.metric("Trades", result['trades'])
                    col4.metric("Sharpe", f"{result['sharpe']:.2f}")
                    
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(x=result['df'].index, y=result['df']['CumulativeStrategy']*10000, name='Strategy'))
                    fig.add_trace(go.Scatter(x=result['df'].index, y=result['df']['Cumulative']*10000, name='Buy & Hold'))
                    fig.update_layout(height=400, template='plotly_dark')
                    st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("Premium feature")

else:
    st.info(f"{st.session_state.page.title()} - Coming soon")

st.markdown("---")
st.caption("WealthStockify © 2025")
