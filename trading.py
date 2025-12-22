import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from supabase import create_client, Client
import hashlib

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

# Custom CSS
st.markdown("""
<style>
    .stApp { background: #0e1117; }
    h1, h2, h3 { color: #ffffff !important; font-family: 'Inter', sans-serif; }
    .stButton > button {
        background: #1f2937;
        color: white;
        border: 1px solid #374151;
        border-radius: 8px;
        padding: 0.75rem 2rem;
        font-weight: 600;
        transition: all 0.3s;
    }
    .stButton > button:hover { background: #374151; }
    .premium-card {
        background: linear-gradient(135deg, #1e3a8a 0%, #3b82f6 100%);
        padding: 2rem;
        border-radius: 12px;
        color: white;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)

# Authentication Functions
def sign_up(email: str, password: str):
    try:
        response = supabase.auth.sign_up({"email": email, "password": password})
        if response.user:
            return True, "Account created! You can now log in."
        return False, "Failed to create account"
    except Exception as e:
        return False, str(e)

def sign_in(email: str, password: str):
    try:
        response = supabase.auth.sign_in_with_password({"email": email, "password": password})
        if response.user:
            profile = supabase.table('user_profiles').select('*').eq('id', response.user.id).execute()
            return True, response.user, profile.data[0] if profile.data else None
        return False, None, None
    except Exception as e:
        return False, None, str(e)

def sign_out():
    supabase.auth.sign_out()
    st.session_state.clear()

def reset_password(email: str):
    try:
        supabase.auth.reset_password_for_email(email)
        return True, "Password reset email sent! Check your inbox."
    except Exception as e:
        return False, str(e)

def upgrade_to_premium(user_id: str):
    try:
        end_date = (datetime.now() + timedelta(days=30)).isoformat()
        supabase.table('user_profiles').update({
            'is_premium': True,
            'subscription_end_date': end_date
        }).eq('id', user_id).execute()
        return True
    except:
        return False

def cancel_premium(user_id: str):
    try:
        supabase.table('user_profiles').update({
            'is_premium': False,
            'subscription_end_date': None
        }).eq('id', user_id).execute()
        return True
    except:
        return False

def get_user_watchlist(user_id: str):
    try:
        response = supabase.table('watchlists').select('ticker').eq('user_id', user_id).execute()
        return [item['ticker'] for item in response.data]
    except:
        return []

def add_to_watchlist(user_id: str, ticker: str):
    try:
        supabase.table('watchlists').insert({'user_id': user_id, 'ticker': ticker}).execute()
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

# Helper Functions
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

def predict_price(df, days=30):
    if len(df) < 30:
        return None
    recent_df = df.tail(90).copy()
    recent_df['Days'] = range(len(recent_df))
    X = recent_df['Days'].values
    y = recent_df['Close'].values
    x_mean, y_mean = X.mean(), y.mean()
    numerator = ((X - x_mean) * (y - y_mean)).sum()
    denominator = ((X - x_mean) ** 2).sum()
    if denominator == 0:
        return None
    slope = numerator / denominator
    intercept = y_mean - slope * x_mean
    momentum = (df['Close'].iloc[-1] - df['Close'].iloc[-30]) / df['Close'].iloc[-30]
    adjusted_slope = slope * (1 + momentum * 0.5)
    future_day = len(recent_df) + days
    return max(adjusted_slope * future_day + intercept, 0)

def calculate_position_size(account_size, stock_price, method='fixed', risk_percent=2, volatility=None, win_rate=0.55, avg_win=1.5, avg_loss=1):
    if method == 'fixed':
        shares = int(account_size * (risk_percent / 100) / stock_price)
    elif method == 'kelly':
        q = 1 - win_rate
        b = avg_win / avg_loss
        kelly_fraction = max(0, min((win_rate * b - q) / b * 0.5, 0.25))
        shares = int(account_size * kelly_fraction / stock_price)
    elif method == 'volatility' and volatility:
        shares = int(account_size * (risk_percent / 100) / volatility / stock_price)
    else:
        shares = 0
    return max(shares, 0)

def run_backtest(ticker, start_date, end_date, initial_capital=10000):
    stock = yf.Ticker(ticker)
    df = stock.history(start=start_date, end=end_date)
    if df.empty:
        return None
    df = calculate_technical_indicators(df)
    df['Signal'] = 0
    for i in range(1, len(df)):
        if pd.notna(df['MACD'].iloc[i]) and pd.notna(df['Signal'].iloc[i]) and pd.notna(df['RSI'].iloc[i]):
            if df['MACD'].iloc[i] > df['Signal'].iloc[i] and df['MACD'].iloc[i-1] <= df['Signal'].iloc[i-1] and df['RSI'].iloc[i] < 70:
                df.loc[df.index[i], 'Signal'] = 1
            elif df['MACD'].iloc[i] < df['Signal'].iloc[i] and df['MACD'].iloc[i-1] >= df['Signal'].iloc[i-1]:
                df.loc[df.index[i], 'Signal'] = -1
    df['Position'] = df['Signal'].replace(0, np.nan).ffill().fillna(0)
    df['Returns'] = df['Close'].pct_change()
    df['Strategy_Returns'] = df['Position'].shift(1) * df['Returns']
    df['Cumulative_Returns'] = (1 + df['Returns']).cumprod()
    df['Cumulative_Strategy_Returns'] = (1 + df['Strategy_Returns']).cumprod()
    total_return = (df['Cumulative_Strategy_Returns'].iloc[-1] - 1) * 100
    buy_hold_return = (df['Cumulative_Returns'].iloc[-1] - 1) * 100
    num_trades = len(df[df['Signal'] != 0])
    sharpe_ratio = np.sqrt(252) * df['Strategy_Returns'].mean() / df['Strategy_Returns'].std() if df['Strategy_Returns'].std() != 0 else 0
    cumulative = df['Cumulative_Strategy_Returns']
    running_max = cumulative.expanding().max()
    drawdown = (cumulative - running_max) / running_max
    max_drawdown = drawdown.min() * 100
    return {
        'df': df,
        'total_return': total_return,
        'buy_hold_return': buy_hold_return,
        'num_trades': num_trades,
        'sharpe_ratio': sharpe_ratio,
        'max_drawdown': max_drawdown
    }

def screen_stocks():
    tickers = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA', 'META', 'NVDA', 'AMD', 'NFLX', 'DIS',
               'JPM', 'BAC', 'V', 'MA', 'JNJ', 'PFE', 'XOM', 'CVX', 'WMT', 'HD',
               'COST', 'NKE', 'PYPL', 'INTC', 'QCOM', 'CSCO', 'ORCL', 'IBM', 'ADBE', 'CRM']
    results = []
    progress_bar = st.progress(0)
    for idx, ticker in enumerate(tickers):
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            hist = stock.history(period='6mo')
            if not hist.empty:
                hist = calculate_technical_indicators(hist)
                score = calculate_ai_score(hist, info)
                current_price = hist['Close'].iloc[-1]
                change = ((current_price - hist['Close'].iloc[0]) / hist['Close'].iloc[0]) * 100
                results.append({
                    'Ticker': ticker,
                    'Price': f"${current_price:.2f}",
                    'Change_6M': f"{change:.2f}%",
                    'AI_Score': score,
                    'RSI': f"{hist['RSI'].iloc[-1]:.1f}" if 'RSI' in hist.columns else "N/A"
                })
            progress_bar.progress((idx + 1) / len(tickers))
        except:
            continue
    progress_bar.empty()
    return pd.DataFrame(results).sort_values('AI_Score', ascending=False)

# Authentication UI
if not st.session_state.authenticated:
    st.markdown("# WealthStockify")
    st.markdown("### Professional Stock Analysis Platform")
    
    tab1, tab2, tab3 = st.tabs(["Login", "Sign Up", "Reset Password"])
    
    with tab1:
        st.subheader("Login to Your Account")
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Password", type="password", key="login_password")
        
        if st.button("Login", use_container_width=True, type="primary"):
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
        
        if st.button("Sign Up", use_container_width=True, type="primary"):
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
    
    with tab3:
        st.subheader("Reset Your Password")
        reset_email = st.text_input("Enter your email address", key="reset_email")
        
        if st.button("Send Reset Link", use_container_width=True, type="primary"):
            if reset_email:
                success, message = reset_password(reset_email)
                if success:
                    st.success(message)
                else:
                    st.error(f"Error: {message}")
            else:
                st.warning("Please enter your email")
    
    st.stop()

# Main App
with st.sidebar:
    st.markdown(f"# WealthStockify")
    st.markdown(f"**{st.session_state.user.email}**")
    
    is_premium = st.session_state.user_profile.get('is_premium', False) if st.session_state.user_profile else False
    
    if is_premium:
        st.success("Premium Active")
        sub_end = st.session_state.user_profile.get('subscription_end_date')
        if sub_end:
            st.caption(f"Valid until: {sub_end[:10]}")
        if st.button("Cancel Subscription", use_container_width=True):
            if cancel_premium(st.session_state.user.id):
                profile = supabase.table('user_profiles').select('*').eq('id', st.session_state.user.id).execute()
                st.session_state.user_profile = profile.data[0]
                st.rerun()
    else:
        st.info("Free Tier")
        if st.button("Upgrade to Premium - $9.99/mo", use_container_width=True, type="primary"):
            if upgrade_to_premium(st.session_state.user.id):
                profile = supabase.table('user_profiles').select('*').eq('id', st.session_state.user.id).execute()
                st.session_state.user_profile = profile.data[0]
                st.balloons()
                st.rerun()
    
    if st.button("Logout", use_container_width=True):
        sign_out()
        st.rerun()
    
    st.markdown("---")
    
    with st.expander("Premium Features"):
        features = ["Unlimited Stock Analysis", "AI Scoring System", "Advanced Technical Indicators",
                   "Stock Screener (30+ stocks)", "AI Price Predictions", "Position Size Calculator",
                   "5-Year Backtesting", "Watchlist with Alerts", "Export to CSV"]
        for feature in features:
            icon = "✓" if is_premium else "✗"
            st.markdown(f"{icon} {feature}")

# Navigation
st.markdown("### Navigation")
nav_cols = st.columns(5)
pages = ["Stock Analysis", "Stock Screener", "Backtesting", "Watchlist", "Position Sizer"]
for i, (col, page_name) in enumerate(zip(nav_cols, pages)):
    with col:
        if st.button(page_name, use_container_width=True):
            st.session_state.page = page_name

if 'page' not in st.session_state:
    st.session_state.page = "Stock Analysis"
page = st.session_state.page
st.markdown("---")

# Stock Analysis Page
if page == "Stock Analysis":
    st.title("Stock Analysis Dashboard")
    
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
                st.error("Invalid ticker")
            else:
                hist = calculate_technical_indicators(hist)
                current_price = hist['Close'].iloc[-1]
                prev_close = hist['Close'].iloc[-2] if len(hist) > 1 else current_price
                change_pct = ((current_price - prev_close) / prev_close) * 100
                
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Current Price", f"${current_price:.2f}", f"{change_pct:+.2f}%")
                with col2:
                    if is_premium:
                        ai_score = calculate_ai_score(hist, info)
                        st.metric("AI Score", f"{ai_score:.0f}/100")
                    else:
                        st.metric("AI Score", "Premium Only")
                with col3:
                    st.metric("Volume", f"{info.get('volume', 0)/1e6:.1f}M")
                with col4:
                    market_cap = info.get('marketCap', 0)
                    st.metric("Market Cap", f"${market_cap/1e9:.2f}B" if market_cap > 0 else "N/A")
                
                st.markdown("---")
                st.subheader("Price Chart")
                
                fig = make_subplots(rows=3 if is_premium else 1, cols=1, shared_xaxes=True,
                                   vertical_spacing=0.08, row_heights=[0.6, 0.2, 0.2] if is_premium else [1])
                
                fig.add_trace(go.Candlestick(x=hist.index, open=hist['Open'], high=hist['High'],
                                            low=hist['Low'], close=hist['Close'], name='Price'), row=1, col=1)
                
                if is_premium:
                    fig.add_trace(go.Scatter(x=hist.index, y=hist['SMA_50'], name='SMA 50',
                                           line=dict(color='orange')), row=1, col=1)
                    fig.add_trace(go.Scatter(x=hist.index, y=hist['SMA_200'], name='SMA 200',
                                           line=dict(color='red')), row=1, col=1)
                    fig.add_trace(go.Scatter(x=hist.index, y=hist['MACD'], name='MACD',
                                           line=dict(color='blue')), row=2, col=1)
                    fig.add_trace(go.Scatter(x=hist.index, y=hist['Signal'], name='Signal',
                                           line=dict(color='red')), row=2, col=1)
                    fig.add_trace(go.Scatter(x=hist.index, y=hist['RSI'], name='RSI',
                                           line=dict(color='purple')), row=3, col=1)
                    fig.add_hline(y=70, line_dash="dash", line_color="red", row=3, col=1)
                    fig.add_hline(y=30, line_dash="dash", line_color="green", row=3, col=1)
                
                fig.update_layout(height=800 if is_premium else 500, template='plotly_dark',
                                xaxis_rangeslider_visible=False)
                st.plotly_chart(fig, use_container_width=True)
                
                if is_premium:
                    col1, col2 = st.columns(2)
                    with col1:
                        st.subheader("Fundamentals")
                        fund_data = {
                            "Metric": ["P/E Ratio", "Market Cap", "Dividend Yield"],
                            "Value": [
                                f"{info.get('trailingPE', 'N/A'):.2f}" if isinstance(info.get('trailingPE'), (int, float)) else "N/A",
                                f"${info.get('marketCap', 0)/1e9:.2f}B" if info.get('marketCap') else "N/A",
                                f"{info.get('dividendYield', 0)*100:.2f}%" if info.get('dividendYield') else "N/A"
                            ]
                        }
                        st.dataframe(pd.DataFrame(fund_data), hide_index=True)
                    with col2:
                        st.subheader("AI Predictions")
                        pred_30 = predict_price(hist, 30)
                        if pred_30:
                            pred_change = ((pred_30 - current_price) / current_price) * 100
                            st.metric("30-Day Forecast", f"${pred_30:.2f}", f"{pred_change:+.2f}%")
                            st.caption("For educational purposes only")
                
        except Exception as e:
            st.error(f"Error: {str(e)}")

elif page == "Watchlist":
    st.title("Watchlist")
    
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
        
        watchlist = get_user_watchlist(st.session_state.user.id)
        if watchlist:
            st.subheader("Your Stocks")
            for ticker in watchlist:
                col1, col2 = st.columns([4, 1])
                with col1:
                    st.write(f"{ticker}")
                with col2:
                    if st.button("Remove", key=f"remove_{ticker}"):
                        remove_from_watchlist(st.session_state.user.id, ticker)
                        st.rerun()
        else:
            st.info("Your watchlist is empty")
    else:
        st.warning("Watchlist is a Premium Feature")

else:
    st.info(f"'{page}' page - upgrade to premium for full access!")

st.markdown("---")
st.markdown("WealthStockify © 2025 | For educational purposes only")
