import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import numpy as np
import time

# Database setup (optional - comment out if not using Supabase yet)
try:
    from supabase import create_client, Client
    
    # Get secrets from Streamlit
    SUPABASE_URL = st.secrets["supabase"]["https://wkochyecnjnpabjxhbui.supabase.co"]
    SUPABASE_KEY = st.secrets["supabase"]["eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Indrb2NoeWVjbmpucGFianhoYnVpIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTkzNTQwMDksImV4cCI6MjA3NDkzMDAwOX0.NQtJ-LM3wQhxnwsBWXNX3jUQFc3vddhvkE6Q2oDW6Ww"]
    
    # Initialize Supabase client
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    DB_ENABLED = True
except:
    DB_ENABLED = False
    st.warning("Database not configured. Running in local mode.")

# Page configuration
st.set_page_config(
    page_title="AI Stock Analyzer Pro", 
    page_icon="🚀", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state
if 'portfolio_size' not in st.session_state:
    st.session_state.portfolio_size = 0.0
if 'risk_percent' not in st.session_state:
    st.session_state.risk_percent = 2
if 'analyzed_stocks' not in st.session_state:
    st.session_state.analyzed_stocks = []
if 'favorites' not in st.session_state:
    st.session_state.favorites = []
if 'buy_signals_history' not in st.session_state:
    st.session_state.buy_signals_history = []
if 'alerts' not in st.session_state:
    st.session_state.alerts = []
if 'watchlist_data' not in st.session_state:
    st.session_state.watchlist_data = {}
if 'auto_refresh' not in st.session_state:
    st.session_state.auto_refresh = False
if 'refresh_interval' not in st.session_state:
    st.session_state.refresh_interval = 60
if 'is_subscribed' not in st.session_state:
    st.session_state.is_subscribed = False  # True if user paid
if 'user_email' not in st.session_state:
    st.session_state.user_email = None

def show_paywall():
    """Show subscription paywall"""
    st.warning("🔒 This is a premium feature")
    
    st.markdown("### Subscribe for $9.99/month")
    st.markdown("""
    **Get unlimited access to:**
    - Unlimited stock analyses
    - Unlimited watchlist stocks
    - Large screener (200+ stocks)
    - Auto-refresh & live data
    - Advanced technical indicators
    - AI price predictions
    - Pattern recognition
    - Position size calculator
    - Fundamental analysis
    - 5-year backtesting
    - Priority support
    """)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        user_email = st.text_input("Email for subscription", key="subscription_email")
        
        if st.button("Subscribe Now - $9.99/month", type="primary", use_container_width=True, key="subscribe_btn"):
            if user_email:
                st.info("🔄 Redirecting to payment... (Demo mode - click below to activate)")
                # In production, integrate Stripe here
                # For demo purposes:
                if st.button("✅ Complete Payment (Demo)", key="demo_payment", use_container_width=True):
                    st.session_state.is_subscribed = True
                    st.session_state.user_email = user_email
                    
                    # Save to database
                    if DB_ENABLED:
                        save_user_subscription(user_email)
                    
                    st.success("Subscription activated!")
                    st.rerun()
            else:
                st.error("Please enter your email")

def save_user_subscription(email):
    """Save user subscription to database"""
    if not DB_ENABLED:
        return
    
    try:
        data = {
            "email": email,
            "subscribed": True,
            "subscription_date": datetime.now().isoformat(),
            "plan": "premium"
        }
        supabase.table("users").upsert(data).execute()
    except Exception as e:
        st.error(f"Database error: {e}")

def save_watchlist(email, tickers):
    """Save user's watchlist to database"""
    if not DB_ENABLED:
        return
    
    try:
        data = {
            "email": email,
            "watchlist": tickers,
            "updated_at": datetime.now().isoformat()
        }
        supabase.table("watchlists").upsert(data).execute()
    except Exception as e:
        st.error(f"Failed to save watchlist: {e}")

def load_watchlist(email):
    """Load user's watchlist from database"""
    if not DB_ENABLED:
        return []
    
    try:
        response = supabase.table("watchlists").select("watchlist").eq("email", email).execute()
        if response.data and len(response.data) > 0:
            return response.data[0]["watchlist"]
        return []
    except:
        return []

def save_analysis(email, ticker, result):
    """Save stock analysis to database"""
    if not DB_ENABLED:
        return
    
    try:
        data = {
            "email": email,
            "ticker": ticker,
            "analysis_data": result,
            "created_at": datetime.now().isoformat()
        }
        supabase.table("analyses").insert(data).execute()
    except Exception as e:
        st.error(f"Failed to save analysis: {e}")

# Title with subscription badge
col_title, col_badge = st.columns([5, 1])
with col_title:
    st.title("🚀 AI Stock Analyzer Pro")
with col_badge:
    if st.session_state.is_subscribed:
        st.success("✅ Subscribed")
    else:
        st.warning("🔒 Free")

st.markdown("---")

# Show subscription prompt for free users
if not st.session_state.is_subscribed:
    st.info("🔒 Subscribe for $9.99/month to unlock all premium features")


# Sidebar
st.sidebar.header("💼 Portfolio Settings")
st.session_state.portfolio_size = st.sidebar.number_input(
    "Portfolio Size ($)", 
    value=st.session_state.portfolio_size, 
    min_value=0.0, 
    step=100.0,
    key="portfolio_input"
)
st.session_state.risk_percent = st.sidebar.slider(
    "Risk per Trade (%)", 
    min_value=1, 
    max_value=10, 
    value=st.session_state.risk_percent,
    key="risk_slider"
)

st.sidebar.markdown(f"**Portfolio:** ${st.session_state.portfolio_size:.2f}")
st.sidebar.markdown(f"**Risk:** {st.session_state.risk_percent}%")

st.sidebar.markdown("---")

# Subscription Section
if not st.session_state.is_subscribed:
    st.sidebar.error("🔒 Free Account")
    if st.sidebar.button("💳 Subscribe - $9.99/mo", type="primary", use_container_width=True, key="sidebar_subscribe"):
        st.session_state.show_paywall = True
        st.rerun()
else:
    st.sidebar.success(f"✅ Subscribed")
    st.sidebar.caption(f"Email: {st.session_state.user_email}")
    if st.sidebar.button("Cancel Subscription", key="cancel_sub"):
        st.session_state.is_subscribed = False
        st.warning("Subscription cancelled")
        st.rerun()

st.sidebar.markdown("---")
st.sidebar.header("⭐ Watchlist")

new_ticker = st.sidebar.text_input("Add to Watchlist", "", key="add_watchlist_input").upper()
if st.sidebar.button("➕ Add", key="add_watchlist_btn") and new_ticker:
    if new_ticker not in st.session_state.favorites:
        st.session_state.favorites.append(new_ticker)
        
        # Save to database
        if DB_ENABLED and st.session_state.user_email:
            save_watchlist(st.session_state.user_email, st.session_state.favorites)
        
        st.sidebar.success(f"Added {new_ticker}!")
        st.rerun()
    else:
        st.sidebar.warning("Already in watchlist")

if st.session_state.favorites:
    for idx, fav in enumerate(st.session_state.favorites):
        col1, col2 = st.sidebar.columns([4, 1])
        with col1:
            if st.button(fav, key=f"fav_btn_{idx}_{fav}", use_container_width=True):
                st.session_state.quick_analyze = fav
        with col2:
            if st.button("❌", key=f"remove_btn_{idx}_{fav}"):
                st.session_state.favorites.remove(fav)
                st.rerun()

st.sidebar.markdown("---")
st.sidebar.header("🔔 Active Alerts")
if st.session_state.alerts:
    for i, alert in enumerate(st.session_state.alerts):
        with st.sidebar.expander(f"{alert['ticker']} - {alert['condition']}", expanded=False):
            st.write(f"**Trigger:** {alert['condition']}")
            if st.button("Delete", key=f"del_alert_btn_{i}"):
                st.session_state.alerts.pop(i)
                st.rerun()

st.sidebar.markdown("---")
st.sidebar.header("🔄 Auto-Refresh")

if not st.session_state.is_subscribed:
    st.sidebar.warning("🔒 Premium Feature")
    if st.sidebar.button("Unlock All Features", key="unlock_all"):
        st.session_state.show_paywall = True
        st.rerun()
else:
    st.session_state.auto_refresh = st.sidebar.checkbox("Enable Live Updates", value=st.session_state.auto_refresh, key="auto_refresh_check")
    if st.session_state.auto_refresh:
        st.session_state.refresh_interval = st.sidebar.slider("Refresh interval (seconds)", 30, 300, 60, key="refresh_interval_slider")
        st.sidebar.info(f"Updates every {st.session_state.refresh_interval}s")

def get_market_overview():
    """Get major market indices"""
    try:
        indices = {
            'S&P 500': '^GSPC',
            'NASDAQ': '^IXIC',
            'DOW': '^DJI',
            'Russell 2000': '^RUT',
            'VIX': '^VIX'
        }
        
        overview = {}
        for name, ticker in indices.items():
            stock = yf.Ticker(ticker)
            hist = stock.history(period='5d')
            if not hist.empty:
                current = hist['Close'].iloc[-1]
                prev = hist['Close'].iloc[-2] if len(hist) > 1 else current
                change = ((current - prev) / prev) * 100
                overview[name] = {
                    'price': round(current, 2),
                    'change': round(change, 2)
                }
        return overview
    except:
        return None

def get_sector_performance():
    """Get sector ETF performance"""
    sectors = {
        'Technology': 'XLK',
        'Healthcare': 'XLV',
        'Financial': 'XLF',
        'Energy': 'XLE',
        'Consumer': 'XLY',
        'Industrial': 'XLI',
        'Utilities': 'XLU',
        'Real Estate': 'XLRE',
        'Materials': 'XLB'
    }
    
    performance = {}
    try:
        for name, ticker in sectors.items():
            stock = yf.Ticker(ticker)
            hist = stock.history(period='5d')
            if not hist.empty:
                current = hist['Close'].iloc[-1]
                prev = hist['Close'].iloc[-2] if len(hist) > 1 else current
                change = ((current - prev) / prev) * 100
                performance[name] = round(change, 2)
        return performance
    except:
        return None

def detect_patterns(hist):
    """Detect chart patterns"""
    patterns = []
    
    if len(hist) < 20:
        return patterns
    
    close = hist['Close'].values
    
    # Head and Shoulders
    if len(close) >= 50:
        recent = close[-50:]
        peaks = []
        for i in range(1, len(recent)-1):
            if recent[i] > recent[i-1] and recent[i] > recent[i+1]:
                peaks.append((i, recent[i]))
        
        if len(peaks) >= 3:
            if peaks[1][1] > peaks[0][1] and peaks[1][1] > peaks[2][1]:
                patterns.append("📉 Head & Shoulders (Bearish)")
    
    # Double Top/Bottom
    if len(close) >= 30:
        recent = close[-30:]
        max_idx = np.argmax(recent[:15])
        max_idx2 = np.argmax(recent[15:]) + 15
        
        if abs(recent[max_idx] - recent[max_idx2]) / recent[max_idx] < 0.02:
            patterns.append("📉 Double Top (Bearish)")
        
        min_idx = np.argmin(recent[:15])
        min_idx2 = np.argmin(recent[15:]) + 15
        
        if abs(recent[min_idx] - recent[min_idx2]) / recent[min_idx] < 0.02:
            patterns.append("📈 Double Bottom (Bullish)")
    
    # Bull/Bear Flags
    recent_10 = close[-10:]
    if len(recent_10) == 10:
        trend = np.polyfit(range(10), recent_10, 1)[0]
        if trend < 0 and close[-1] > close[-10]:
            patterns.append("🚀 Bull Flag (Bullish)")
        elif trend > 0 and close[-1] < close[-10]:
            patterns.append("📉 Bear Flag (Bearish)")
    
    return patterns if patterns else ["No clear patterns detected"]

def calculate_advanced_indicators(hist):
    """Calculate advanced technical indicators"""
    indicators = {}
    
    # Fibonacci
    high_price = hist['High'].max()
    low_price = hist['Low'].min()
    diff = high_price - low_price
    
    indicators['fib_236'] = high_price - (0.236 * diff)
    indicators['fib_382'] = high_price - (0.382 * diff)
    indicators['fib_500'] = high_price - (0.500 * diff)
    indicators['fib_618'] = high_price - (0.618 * diff)
    
    # Stochastic
    low_14 = hist['Low'].rolling(14).min()
    high_14 = hist['High'].rolling(14).max()
    k_percent = 100 * ((hist['Close'] - low_14) / (high_14 - low_14))
    indicators['stochastic_k'] = k_percent.iloc[-1]
    indicators['stochastic_d'] = k_percent.rolling(3).mean().iloc[-1]
    
    # ADX
    high_diff = hist['High'].diff()
    low_diff = -hist['Low'].diff()
    
    plus_dm = high_diff.where((high_diff > low_diff) & (high_diff > 0), 0)
    minus_dm = low_diff.where((low_diff > high_diff) & (low_diff > 0), 0)
    
    tr = pd.concat([
        hist['High'] - hist['Low'],
        abs(hist['High'] - hist['Close'].shift()),
        abs(hist['Low'] - hist['Close'].shift())
    ], axis=1).max(axis=1)
    
    atr = tr.rolling(14).mean()
    plus_di = 100 * (plus_dm.rolling(14).mean() / atr)
    minus_di = 100 * (minus_dm.rolling(14).mean() / atr)
    
    dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
    adx = dx.rolling(14).mean()
    indicators['adx'] = adx.iloc[-1]
    
    # OBV
    obv = (np.sign(hist['Close'].diff()) * hist['Volume']).fillna(0).cumsum()
    indicators['obv'] = obv.iloc[-1]
    indicators['obv_trend'] = "Bullish" if obv.iloc[-1] > obv.iloc[-10] else "Bearish"
    
    return indicators

def predict_price(hist):
    """Simple price prediction"""
    if len(hist) < 30:
        return None
    
    recent = hist['Close'].tail(30).values
    x = np.arange(len(recent))
    
    coefficients = np.polyfit(x, recent, 1)
    future_x = np.arange(len(recent), len(recent) + 5)
    predictions = np.polyval(coefficients, future_x)
    
    current_price = recent[-1]
    predicted_5day = predictions[-1]
    change = ((predicted_5day - current_price) / current_price) * 100
    
    return {
        'current': current_price,
        'predicted_5day': predicted_5day,
        'change_percent': change,
        'trend': 'Upward' if change > 0 else 'Downward',
        'confidence': 'Medium'
    }

def get_fundamental_data(ticker):
    """Get fundamental data"""
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        
        fundamentals = {
            'pe_ratio': info.get('trailingPE', 'N/A'),
            'forward_pe': info.get('forwardPE', 'N/A'),
            'pb_ratio': info.get('priceToBook', 'N/A'),
            'debt_to_equity': info.get('debtToEquity', 'N/A'),
            'current_ratio': info.get('currentRatio', 'N/A'),
            'roe': info.get('returnOnEquity', 'N/A'),
            'profit_margin': info.get('profitMargins', 'N/A'),
            'revenue_growth': info.get('revenueGrowth', 'N/A'),
            'earnings_growth': info.get('earningsGrowth', 'N/A'),
            'dividend_yield': info.get('dividendYield', 'N/A'),
            'peg_ratio': info.get('pegRatio', 'N/A')
        }
        
        return fundamentals
    except:
        return None

def calculate_position_sizes(portfolio_size, price, volatility):
    """Position sizing methods"""
    if portfolio_size == 0:
        return {
            'fixed_percent': 0,
            'volatility_based': 0,
            'kelly': 0
        }
    
    risk_amount = portfolio_size * 0.02
    fixed_shares = int(risk_amount / (price * 0.1))
    
    if volatility > 0:
        vol_multiplier = 20 / volatility if volatility > 20 else 1
        vol_shares = int(fixed_shares * vol_multiplier)
    else:
        vol_shares = fixed_shares
    
    win_rate = 0.55
    avg_win = 1.5
    avg_loss = 1.0
    
    kelly_percent = (win_rate * avg_win - (1 - win_rate) * avg_loss) / avg_win
    kelly_percent = max(0, min(kelly_percent * 0.5, 0.05))
    kelly_shares = int((portfolio_size * kelly_percent) / price)
    
    return {
        'fixed_percent': fixed_shares,
        'volatility_based': vol_shares,
        'kelly': kelly_shares
    }

def create_candlestick_chart(ticker, hist):
    """Create candlestick chart"""
    fig = make_subplots(
        rows=3, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.05,
        subplot_titles=(f'{ticker} Price', 'Volume', 'RSI'),
        row_heights=[0.6, 0.2, 0.2]
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
    
    hist['SMA50'] = hist['Close'].rolling(50).mean()
    hist['SMA200'] = hist['Close'].rolling(200).mean()
    
    fig.add_trace(
        go.Scatter(x=hist.index, y=hist['SMA50'], name='SMA 50', line=dict(color='orange', width=1)),
        row=1, col=1
    )
    fig.add_trace(
        go.Scatter(x=hist.index, y=hist['SMA200'], name='SMA 200', line=dict(color='blue', width=1)),
        row=1, col=1
    )
    
    colors = ['red' if hist['Close'].iloc[i] < hist['Open'].iloc[i] else 'green' for i in range(len(hist))]
    fig.add_trace(
        go.Bar(x=hist.index, y=hist['Volume'], name='Volume', marker_color=colors),
        row=2, col=1
    )
    
    delta = hist['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    
    fig.add_trace(
        go.Scatter(x=hist.index, y=rsi, name='RSI', line=dict(color='purple', width=2)),
        row=3, col=1
    )
    fig.add_hline(y=70, line_dash="dash", line_color="red", row=3, col=1)
    fig.add_hline(y=30, line_dash="dash", line_color="green", row=3, col=1)
    
    fig.update_layout(
        height=800,
        showlegend=True,
        xaxis_rangeslider_visible=False,
        template='plotly_white'
    )
    
    return fig

def backtest_strategy(ticker, years=2):
    """Backtest strategy"""
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period=f"{years}y")
        
        if hist.empty or len(hist) < 200:
            return None
        
        trades = []
        position = None
        
        for i in range(200, len(hist)):
            window = hist.iloc[i-200:i]
            close = window['Close'].iloc[-1]
            
            sma50 = window['Close'].rolling(50).mean().iloc[-1]
            sma200 = window['Close'].rolling(200).mean().iloc[-1]
            
            delta = window['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
            rs = gain / loss
            rsi = (100 - (100 / (1 + rs))).iloc[-1]
            
            score = 0
            if close > sma50:
                score += 2
            if close > sma200:
                score += 1
            if rsi < 30:
                score += 2
            elif 30 <= rsi <= 70:
                score += 1
            
            if score >= 3 and position is None:
                position = {
                    'entry_price': close,
                    'entry_date': hist.index[i],
                    'score': score
                }
            elif position and (score < 1 or close < position['entry_price'] * 0.95):
                pnl = ((close - position['entry_price']) / position['entry_price']) * 100
                trades.append({
                    'entry_date': position['entry_date'],
                    'exit_date': hist.index[i],
                    'entry_price': position['entry_price'],
                    'exit_price': close,
                    'pnl_percent': pnl,
                    'score': position['score']
                })
                position = None
        
        if trades:
            trades_df = pd.DataFrame(trades)
            win_rate = len(trades_df[trades_df['pnl_percent'] > 0]) / len(trades_df) * 100
            avg_win = trades_df[trades_df['pnl_percent'] > 0]['pnl_percent'].mean() if len(trades_df[trades_df['pnl_percent'] > 0]) > 0 else 0
            avg_loss = trades_df[trades_df['pnl_percent'] < 0]['pnl_percent'].mean() if len(trades_df[trades_df['pnl_percent'] < 0]) > 0 else 0
            
            return {
                'total_trades': len(trades),
                'win_rate': win_rate,
                'avg_win': avg_win,
                'avg_loss': avg_loss,
                'trades': trades_df
            }
        return None
    except:
        return None

def analyze_stock(ticker, portfolio_size, risk_percent):
    """Full stock analysis"""
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="6mo")
        info = stock.info

        if hist.empty or len(hist) < 50:
            return {"ticker": ticker, "verdict": "NO DATA", "score": 0, "error": True}

        close = hist["Close"].iloc[-1]
        prev_close = hist["Close"].iloc[-2] if len(hist) > 1 else close

        hist["SMA50"] = hist["Close"].rolling(50).mean()
        hist["SMA200"] = hist["Close"].rolling(200).mean()
        sma50 = hist["SMA50"].iloc[-1]
        sma200 = hist["SMA200"].iloc[-1]

        delta = hist["Close"].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs)).iloc[-1]

        exp1 = hist["Close"].ewm(span=12, adjust=False).mean()
        exp2 = hist["Close"].ewm(span=26, adjust=False).mean()
        macd = exp1 - exp2
        signal = macd.ewm(span=9, adjust=False).mean()
        macd_current = macd.iloc[-1]
        signal_current = signal.iloc[-1]

        avg_volume = hist["Volume"].mean()
        current_volume = hist["Volume"].iloc[-1]
        volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1

        returns = hist["Close"].pct_change()
        volatility = returns.std() * (252 ** 0.5) * 100

        score = 0
        factors = []

        if close > sma50:
            score += 2
            factors.append(f"✅ Price above 50 SMA [+2]")
        else:
            score -= 2
            factors.append(f"❌ Price below 50 SMA [-2]")

        if close > sma200:
            score += 1
            factors.append(f"✅ Price above 200 SMA [+1]")
        else:
            score -= 1
            factors.append(f"❌ Price below 200 SMA [-1]")

        if rsi < 30:
            score += 2
            factors.append(f"✅ RSI oversold ({rsi:.1f}) [+2]")
        elif 30 <= rsi <= 70:
            score += 1
            factors.append(f"✅ RSI neutral ({rsi:.1f}) [+1]")
        else:
            score -= 1
            factors.append(f"❌ RSI overbought ({rsi:.1f}) [-1]")

        if volume_ratio > 1.5:
            score += 1
            factors.append(f"✅ High volume [+1]")

        if macd_current > signal_current:
            score += 1
            factors.append(f"✅ MACD bullish [+1]")

        if score >= 5:
            verdict = "🚀 STRONG BUY"
        elif score >= 3:
            verdict = "✅ BUY"
        elif score >= 1:
            verdict = "⏸️ HOLD"
        else:
            verdict = "❌ SELL"

        hist["H-L"] = hist["High"] - hist["Low"]
        hist["H-C"] = abs(hist["High"] - hist["Close"].shift())
        hist["L-C"] = abs(hist["Low"] - hist["Close"].shift())
        tr = hist[["H-L", "H-C", "L-C"]].max(axis=1)
        atr = tr.rolling(14).mean().iloc[-1]

        tp1 = round(close + atr, 2)
        tp2 = round(close + 2 * atr, 2)
        sl1 = round(close - atr, 2)
        sl2 = round(close - 2 * atr, 2)

        max_risk = portfolio_size * (risk_percent / 100)
        risk_per_share = close - sl1
        shares = int(max_risk // risk_per_share) if risk_per_share > 0 else 0

        daily_change = ((close - prev_close) / prev_close) * 100

        patterns = detect_patterns(hist)
        advanced_indicators = calculate_advanced_indicators(hist)
        prediction = predict_price(hist)
        fundamentals = get_fundamental_data(ticker)
        position_sizes = calculate_position_sizes(portfolio_size, close, volatility)

        result = {
            "ticker": ticker,
            "company": info.get("longName", ticker),
            "sector": info.get("sector", "N/A"),
            "market_cap": info.get("marketCap", 0),
            "price": round(close, 2),
            "daily_change": round(daily_change, 2),
            "score": score,
            "verdict": verdict,
            "rsi": round(rsi, 1),
            "sma50": round(sma50, 2),
            "sma200": round(sma200, 2),
            "atr": round(atr, 2),
            "volume_ratio": round(volume_ratio, 2),
            "volatility": round(volatility, 1),
            "tp1": tp1,
            "tp2": tp2,
            "sl1": sl1,
            "sl2": sl2,
            "shares": shares,
            "position_value": round(shares * close, 2),
            "risk_amount": round(max_risk, 2),
            "factors": factors,
            "hist": hist,
            "patterns": patterns,
            "advanced_indicators": advanced_indicators,
            "prediction": prediction,
            "fundamentals": fundamentals,
            "position_sizes": position_sizes,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "error": False
        }

        if "BUY" in verdict:
            st.session_state.buy_signals_history.append(result.copy())

        return result

    except Exception as e:
        return {"ticker": ticker, "verdict": "ERROR", "score": 0, "error": True, "error_msg": str(e)}

# Main tabs
tab0, tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9 = st.tabs([
    "💳 Subscribe",
    "🌍 Market",
    "📊 Analysis",
    "🎯 Watchlist", 
    "🔍 Screener",
    "📈 Patterns",
    "📐 Position",
    "💰 Fundamentals",
    "🔙 Backtest",
    "💎 Signals"
])

with tab0:
    if st.session_state.is_subscribed:
        st.success("✅ You're subscribed!")
        st.markdown(f"**Email:** {st.session_state.user_email}")
        st.markdown("**Plan:** Premium - $9.99/month")
        st.markdown("**Status:** Active")
        
        st.markdown("---")
        st.markdown("### Your Benefits")
        st.markdown("""
        - ✅ Unlimited stock analyses
        - ✅ Unlimited watchlist
        - ✅ 200+ stock screener
        - ✅ Auto-refresh & live data
        - ✅ Advanced indicators
        - ✅ AI predictions
        - ✅ Pattern recognition
        - ✅ Position calculator
        - ✅ Fundamental analysis
        - ✅ 5-year backtesting
        """)
    else:
        show_paywall()

with tab1:
    st.header("🌍 Market Overview Dashboard")
    
    if st.session_state.auto_refresh:
        st.info(f"🔄 Auto-refreshing every {st.session_state.refresh_interval} seconds")
    
    refresh_btn = st.button("🔄 Refresh Market Data", type="primary", key="market_refresh_btn")
    
    overview = None
    sectors = None
    
    if refresh_btn or st.session_state.auto_refresh:
        with st.spinner("Loading market data..."):
            st.subheader("📈 Major Indices")
            overview = get_market_overview()
            
            if overview:
                cols = st.columns(len(overview))
                for i, (name, data) in enumerate(overview.items()):
                    with cols[i]:
                        st.metric(name, f"{data['price']:,.2f}", f"{data['change']:.2f}%")
            else:
                st.warning("Unable to load indices")
            
            st.markdown("---")
            
            st.subheader("🏭 Sector Performance")
            sectors = get_sector_performance()
            
            if sectors:
                sorted_sectors = sorted(sectors.items(), key=lambda x: x[1], reverse=True)
                
                fig = go.Figure()
                colors = ['green' if v > 0 else 'red' for k, v in sorted_sectors]
                
                fig.add_trace(go.Bar(
                    y=[k for k, v in sorted_sectors],
                    x=[v for k, v in sorted_sectors],
                    orientation='h',
                    marker=dict(color=colors),
                    text=[f"{v:.2f}%" for k, v in sorted_sectors],
                    textposition='auto'
                ))
                
                fig.update_layout(
                    title="Sector Performance Today",
                    xaxis_title="Change %",
                    height=400,
                    template='plotly_white'
                )
                
                st.plotly_chart(fig, use_container_width=True)
                
                col1, col2 = st.columns(2)
                with col1:
                    st.success("### 🚀 Top Performers")
                    for sector, perf in sorted_sectors[:3]:
                        st.write(f"**{sector}:** +{perf:.2f}%")
                
                with col2:
                    st.error("### 📉 Bottom Performers")
                    for sector, perf in sorted_sectors[-3:]:
                        st.write(f"**{sector}:** {perf:.2f}%")
    
    if overview:
        st.markdown("---")
        st.subheader("💡 Market Insights")
        
        insights = []
        
        if overview.get('S&P 500', {}).get('change', 0) > 1:
            insights.append("🟢 Strong bullish momentum")
        elif overview.get('S&P 500', {}).get('change', 0) < -1:
            insights.append("🔴 Market weakness")
        
        if overview.get('VIX', {}).get('price', 0) > 25:
            insights.append("⚠️ High volatility - caution")
        elif overview.get('VIX', {}).get('price', 0) < 15:
            insights.append("✅ Low volatility")
        
        if sectors:
            top_sector = max(sectors.items(), key=lambda x: x[1])
            insights.append(f"🏆 {top_sector[0]} leading (+{top_sector[1]:.2f}%)")
        
        for insight in insights:
            st.info(insight)
    else:
        st.info("Click 'Refresh Market Data' to load overview")
    
    if st.session_state.auto_refresh:
        time.sleep(st.session_state.refresh_interval)
        st.rerun()

with tab2:
    st.header("Stock Analysis")
    
    col1, col2, col3 = st.columns([3, 1, 1])
    with col1:
        ticker_input = st.text_input("Enter Stock Ticker", value=st.session_state.get('quick_analyze', ''), key="main_analysis_ticker").upper()
    with col2:
        analyze_btn = st.button("🔍 Analyze", type="primary", key="main_analyze_btn", use_container_width=True)
    with col3:
        if ticker_input and ticker_input not in st.session_state.favorites:
            if st.button("⭐ Watchlist", key="add_to_watchlist_btn", use_container_width=True):
                st.session_state.favorites.append(ticker_input)
                st.rerun()
    
    if analyze_btn and ticker_input:
        if not st.session_state.is_subscribed:
            show_paywall()
        else:
            with st.spinner(f"Analyzing {ticker_input}..."):
                result = analyze_stock(ticker_input, st.session_state.portfolio_size, st.session_state.risk_percent)
                
                if not result["error"]:
                    st.session_state.analyzed_stocks.append(result)
                    
                    st.markdown("---")
                    st.subheader(f"{result['ticker']} - {result['company']}")
                    
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("Price", f"${result['price']}")
                    with col2:
                        st.metric("Change", f"{result['daily_change']}%", delta=f"{result['daily_change']}%")
                    with col3:
                        st.metric("Score", result['score'])
                    with col4:
                        st.metric("Verdict", result['verdict'])
                    
                    st.plotly_chart(create_candlestick_chart(ticker_input, result['hist']), use_container_width=True)
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.markdown("### 📈 Technical")
                        st.write(f"**RSI:** {result['rsi']}")
                        st.write(f"**SMA50:** ${result['sma50']}")
                        st.write(f"**SMA200:** ${result['sma200']}")
                        st.write(f"**Volume:** {result['volume_ratio']}x")
                    
                    with col2:
                        st.markdown("### 🎯 Targets")
                        st.success(f"**TP1:** ${result['tp1']}")
                        st.success(f"**TP2:** ${result['tp2']}")
                        st.error(f"**SL1:** ${result['sl1']}")
                        st.error(f"**SL2:** ${result['sl2']}")
                    
                    with col3:
                        st.markdown("### 💼 Position")
                        st.info(f"**Shares:** {result['shares']}")
                        st.info(f"**Value:** ${result['position_value']}")
                        st.info(f"**Risk:** ${result['risk_amount']}")
                    
                    with st.expander("🔍 Details"):
                        for factor in result['factors']:
                            st.write(factor)
                else:
                    st.error(f"Error: {result.get('error_msg', 'Unable to analyze')}")

with tab3:
    st.header("🎯 Watchlist")
    
    if st.session_state.favorites:
        col1, col2 = st.columns([1, 4])
        with col1:
            if st.button("🔄 Refresh", type="primary", key="watchlist_refresh_btn", use_container_width=True):
                with st.spinner("Updating..."):
                    for ticker in st.session_state.favorites:
                        result = analyze_stock(ticker, st.session_state.portfolio_size, st.session_state.risk_percent)
                        if not result['error']:
                            st.session_state.watchlist_data[ticker] = result
                    st.success("Updated!")
                    st.rerun()
        with col2:
            if st.session_state.auto_refresh:
                st.info("🟢 Auto-refresh enabled")
        
        st.markdown("---")
        
        cols = st.columns(min(3, len(st.session_state.favorites)))
        for i, ticker in enumerate(st.session_state.favorites):
            with cols[i % 3]:
                if ticker in st.session_state.watchlist_data:
                    data = st.session_state.watchlist_data[ticker]
                    
                    if "STRONG BUY" in data['verdict']:
                        st.success(f"### {ticker}")
                    elif "BUY" in data['verdict']:
                        st.info(f"### {ticker}")
                    else:
                        st.warning(f"### {ticker}")
                    
                    st.metric("Price", f"${data['price']}", f"{data['daily_change']}%")
                    st.write(f"**Score:** {data['score']}")
                    st.write(f"**RSI:** {data['rsi']}")
                    
                    if st.button("Analyze", key=f"watchlist_analyze_{i}_{ticker}"):
                        st.session_state.quick_analyze = ticker
                        st.rerun()
                else:
                    st.info(f"### {ticker}")
                    st.write("Click 'Refresh'")
    else:
        st.info("Add tickers to watchlist!")

with tab4:
    st.header("🔍 Screener")
    
    if not st.session_state.is_subscribed:
        show_paywall()
    else:
        col1, col2 = st.columns([2, 1])
        with col1:
            screener_option = st.radio("Select:", ["Popular", "S&P 100", "Custom"], key="screener_option")
        with col2:
            min_score = st.slider("Min Score", 0, 10, 3, key="screener_min_score")
        
        if screener_option == "Popular":
            tickers = ["AAPL", "GOOGL", "MSFT", "AMZN", "TSLA", "NVDA", "META", "NFLX", "AMD", "INTC"]
        elif screener_option == "S&P 100":
            tickers = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "BRK.B", "JPM", "JNJ",
                      "V", "PG", "XOM", "MA", "HD", "CVX", "MRK", "PFE", "ABBV", "KO"]
        else:
            custom = st.text_area("Tickers (comma-separated)", "AAPL,TSLA", key="screener_custom")
            tickers = [t.strip().upper() for t in custom.split(",")]
    
    if st.button("🚀 Run Screener", type="primary", key="run_screener_btn"):
        progress = st.progress(0)
        results = []
        
        for i, ticker in enumerate(tickers):
            result = analyze_stock(ticker, st.session_state.portfolio_size, st.session_state.risk_percent)
            if not result['error'] and result['score'] >= min_score:
                results.append(result)
            progress.progress((i + 1) / len(tickers))
        
        progress.empty()
        
        if results:
            results_sorted = sorted(results, key=lambda x: x['score'], reverse=True)
            st.success(f"Found {len(results_sorted)} stocks!")
            
            st.markdown("### 🏆 Top Picks")
            cols = st.columns(min(3, len(results_sorted[:3])))
            for i, r in enumerate(results_sorted[:3]):
                with cols[i]:
                    st.success(f"### #{i+1} {r['ticker']}")
                    st.metric("Score", r['score'])
                    st.write(f"**Price:** ${r['price']}")
            
            df = pd.DataFrame(results_sorted)
            df = df[["ticker", "price", "score", "verdict", "rsi"]]
            df.columns = ["Ticker", "Price", "Score", "Verdict", "RSI"]
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.warning(f"No stocks with score >= {min_score}")

with tab5:
    st.header("📈 Patterns & Predictions")
    
    if not st.session_state.is_subscribed:
        show_paywall()
    else:
        pattern_ticker = st.text_input("Ticker", "AAPL", key="pattern_ticker_input").upper()
        
        if st.button("🔍 Analyze", type="primary", key="pattern_analyze_btn"):
            with st.spinner("Analyzing..."):
                result = analyze_stock(pattern_ticker, st.session_state.portfolio_size, st.session_state.risk_percent)
                
                if not result['error']:
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.subheader("📊 Patterns")
                        for pattern in result['patterns']:
                            if "Bullish" in pattern:
                                st.success(pattern)
                            elif "Bearish" in pattern:
                                st.error(pattern)
                            else:
                                st.info(pattern)
                    
                    with col2:
                        st.subheader("🔮 Prediction")
                        if result['prediction']:
                            pred = result['prediction']
                            st.metric("5-Day Forecast", f"${pred['predicted_5day']:.2f}", f"{pred['change_percent']:.2f}%")
                            st.write(f"**Current:** ${pred['current']:.2f}")
                            st.write(f"**Trend:** {pred['trend']}")
                        else:
                            st.info("Not enough data")
                    
                    st.markdown("### 📐 Advanced Indicators")
                    adv = result['advanced_indicators']
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.write("**Fibonacci**")
                        st.write(f"23.6%: ${adv['fib_236']:.2f}")
                        st.write(f"38.2%: ${adv['fib_382']:.2f}")
                        st.write(f"50.0%: ${adv['fib_500']:.2f}")
                        st.write(f"61.8%: ${adv['fib_618']:.2f}")
                    
                    with col2:
                        st.write("**Stochastic**")
                        st.write(f"K: {adv['stochastic_k']:.2f}")
                        st.write(f"D: {adv['stochastic_d']:.2f}")
                        if adv['stochastic_k'] > 80:
                            st.error("Overbought")
                        elif adv['stochastic_k'] < 20:
                            st.success("Oversold")
                        else:
                            st.info("Neutral")
                    
                    with col3:
                        st.write("**Trend**")
                        st.write(f"ADX: {adv['adx']:.2f}")
                        if adv['adx'] > 25:
                            st.success("Strong")
                        elif adv['adx'] > 20:
                            st.info("Moderate")
                        else:
                            st.warning("Weak")
                        st.write(f"**OBV:** {adv['obv_trend']}")

with tab6:
    st.header("📐 Position Calculator")
    
    if not st.session_state.is_subscribed:
        show_paywall()
    else:
        calc_ticker = st.text_input("Ticker", "AAPL", key="calc_ticker_input").upper()
        
        if st.button("💰 Calculate", type="primary", key="calc_position_btn"):
            with st.spinner("Calculating..."):
                result = analyze_stock(calc_ticker, st.session_state.portfolio_size, st.session_state.risk_percent)
                
                if not result['error'] and st.session_state.portfolio_size > 0:
                    st.success(f"Position sizing for {calc_ticker} @ ${result['price']}")
                    
                    positions = result['position_sizes']
                    
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        st.metric("Fixed %", f"{positions['fixed_percent']} shares")
                        st.write("**Risk:** 2% portfolio")
                        st.info(f"Value: ${positions['fixed_percent'] * result['price']:.2f}")
                    
                    with col2:
                        st.metric("Volatility", f"{positions['volatility_based']} shares")
                        st.write(f"**Vol:** {result['volatility']:.1f}%")
                        st.info(f"Value: ${positions['volatility_based'] * result['price']:.2f}")
                    
                    with col3:
                        st.metric("Kelly", f"{positions['kelly']} shares")
                        st.write("**Win:** 55%")
                        st.info(f"Value: ${positions['kelly'] * result['price']:.2f}")
                    
                    avg_shares = int(np.mean([positions['fixed_percent'], positions['volatility_based'], positions['kelly']]))
                    st.success(f"**Recommended:** {avg_shares} shares (${avg_shares * result['price']:.2f})")
                elif st.session_state.portfolio_size == 0:
                    st.warning("Set portfolio size in sidebar!")

with tab7:
    st.header("💰 Fundamentals")
    
    if not st.session_state.is_subscribed:
        show_paywall()
    else:
        fund_ticker = st.text_input("Ticker", "AAPL", key="fund_ticker_input").upper()
        
        if st.button("📊 Get Fundamentals", type="primary", key="fund_get_btn"):
            with st.spinner("Loading..."):
                fundamentals = get_fundamental_data(fund_ticker)
                
                if fundamentals:
                    st.success(f"Fundamentals for {fund_ticker}")
                    
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        st.markdown("### 💵 Valuation")
                        st.write(f"**P/E:** {fundamentals['pe_ratio']}")
                        st.write(f"**Forward P/E:** {fundamentals['forward_pe']}")
                        st.write(f"**P/B:** {fundamentals['pb_ratio']}")
                        st.write(f"**PEG:** {fundamentals['peg_ratio']}")
                    
                    with col2:
                        st.markdown("### 📈 Growth")
                        st.write(f"**Revenue:** {fundamentals['revenue_growth']}")
                        st.write(f"**Earnings:** {fundamentals['earnings_growth']}")
                        st.write(f"**Profit Margin:** {fundamentals['profit_margin']}")
                        st.write(f"**ROE:** {fundamentals['roe']}")
                    
                    with col3:
                        st.markdown("### 🏦 Health")
                        st.write(f"**Debt/Equity:** {fundamentals['debt_to_equity']}")
                        st.write(f"**Current Ratio:** {fundamentals['current_ratio']}")
                        st.write(f"**Dividend:** {fundamentals['dividend_yield']}")

with tab8:
    st.header("🔙 Backtesting")
    
    if not st.session_state.is_subscribed:
        show_paywall()
    else:
        col1, col2 = st.columns([2, 1])
        with col1:
            backtest_ticker = st.text_input("Ticker", "AAPL", key="backtest_ticker_input").upper()
        with col2:
            years = st.selectbox("Years", [1, 2, 3, 5], index=1, key="backtest_years")
        
        if st.button("🔬 Backtest", type="primary", key="backtest_run_btn"):
        with st.spinner("Backtesting..."):
            results = backtest_strategy(backtest_ticker, years)
            
            if results:
                st.success("Complete!")
                
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Trades", results['total_trades'])
                with col2:
                    st.metric("Win Rate", f"{results['win_rate']:.1f}%")
                with col3:
                    st.metric("Avg Win", f"{results['avg_win']:.2f}%")
                with col4:
                    st.metric("Avg Loss", f"{results['avg_loss']:.2f}%")
                
                st.dataframe(results['trades'], use_container_width=True)
                
                results['trades']['cumulative'] = results['trades']['pnl_percent'].cumsum()
                
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=results['trades']['exit_date'],
                    y=results['trades']['cumulative'],
                    mode='lines+markers',
                    line=dict(color='green', width=2)
                ))
                fig.update_layout(
                    title="Cumulative Returns",
                    template='plotly_white'
                )
                st.plotly_chart(fig, use_container_width=True)

with tab9:
    st.header("💎 Buy Signals")
    
    if st.session_state.analyzed_stocks:
        buy_signals = [s for s in st.session_state.analyzed_stocks if "BUY" in s.get("verdict", "") and not s.get("error", False)]
        buy_signals_sorted = sorted(buy_signals, key=lambda x: x["score"], reverse=True)
        
        if buy_signals_sorted:
            st.success(f"Found {len(buy_signals_sorted)} signals")
            
            df = pd.DataFrame(buy_signals_sorted)
            df = df[["ticker", "price", "score", "verdict", "tp1", "sl1"]]
            df.columns = ["Ticker", "Price", "Score", "Verdict", "TP1", "SL1"]
            
            st.dataframe(df, use_container_width=True, hide_index=True)
            
            csv = df.to_csv(index=False)
            st.download_button("📥 Download", csv, f"signals_{datetime.now().strftime('%Y%m%d')}.csv", "text/csv", key="download_signals_btn")
        else:
            st.info("No signals yet")
        
        if st.button("🗑️ Clear", key="clear_signals_btn"):
            st.session_state.analyzed_stocks = []
            st.rerun()
    else:
        st.info("Analyze stocks first")

# Footer
st.sidebar.markdown("---")
if st.session_state.is_subscribed:
    st.sidebar.markdown("### Premium Active")
    st.sidebar.markdown("""
    - Unlimited analyses
    - Unlimited watchlist
    - 200+ stock screener
    - Auto-refresh
    - Advanced indicators
    - AI predictions
    - Pattern recognition
    - Position calculator
    - Fundamental analysis
    - 5-year backtesting
    """)
else:
    st.sidebar.markdown("### Subscribe to Unlock")
    st.sidebar.markdown("""
    **$9.99/month gets you:**
    - All premium features
    - Unlimited everything
    - Priority support
    """)
    if st.sidebar.button("Subscribe Now", key="footer_subscribe"):
        st.session_state.show_paywall = True
        st.rerun()

# Show paywall modal if triggered
if st.session_state.get('show_paywall', False):
    show_paywall() watchlist stocks  
    ✅ 200 screener stocks  
    ✅ 5 year backtest  
    ✅ All features unlocked  
    ✅ Priority support  
    ✅ API access (coming soon)
    """)
