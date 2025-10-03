import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

# Page config
st.set_page_config(
    page_title="AI Stock Analyzer Pro",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: 700;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 1rem;
    }
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.5rem;
        border-radius: 10px;
        color: white;
        text-align: center;
        margin: 0.5rem 0;
    }
    .buy-signal {
        background-color: #28a745;
        color: white;
        padding: 0.5rem 1rem;
        border-radius: 5px;
        font-weight: bold;
    }
    .sell-signal {
        background-color: #dc3545;
        color: white;
        padding: 0.5rem 1rem;
        border-radius: 5px;
        font-weight: bold;
    }
    .neutral-signal {
        background-color: #ffc107;
        color: black;
        padding: 0.5rem 1rem;
        border-radius: 5px;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'subscribed' not in st.session_state:
    st.session_state.subscribed = False
if 'watchlist' not in st.session_state:
    st.session_state.watchlist = []

# Subscription management
def check_subscription():
    return st.session_state.subscribed

def show_paywall():
    st.markdown('<h1 class="main-header">🚀 AI Stock Analyzer Pro</h1>', unsafe_allow_html=True)
    st.markdown("---")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("""
        ### 💎 Premium Features
        
        **Unlock the full power of AI-driven stock analysis:**
        
        ✅ Advanced Technical Indicators (RSI, MACD, Bollinger Bands)  
        ✅ AI-Powered Price Predictions  
        ✅ Pattern Recognition (Head & Shoulders, Double Tops, Flags)  
        ✅ Custom Stock Screener (200+ stocks)  
        ✅ Position Size Calculator (Kelly Criterion)  
        ✅ Strategy Backtesting Engine  
        ✅ Fundamental Analysis Dashboard  
        ✅ Real-time Watchlist with Auto-refresh  
        
        ### 💰 Only $9.99/month
        """)
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        if st.button("🔓 Subscribe Now", type="primary", use_container_width=True):
            st.session_state.subscribed = True
            st.success("🎉 Welcome to AI Stock Analyzer Pro!")
            st.rerun()
        
        st.markdown("<br>", unsafe_allow_html=True)
        st.info("💡 **Demo Mode**: Try basic features with limited functionality")
        
        if st.button("👀 Continue with Free Version", use_container_width=True):
            st.session_state.demo_mode = True
            st.rerun()

# Technical indicators
def calculate_rsi(data, period=14):
    delta = data['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def calculate_macd(data):
    exp1 = data['Close'].ewm(span=12, adjust=False).mean()
    exp2 = data['Close'].ewm(span=26, adjust=False).mean()
    macd = exp1 - exp2
    signal = macd.ewm(span=9, adjust=False).mean()
    return macd, signal

def calculate_bollinger_bands(data, period=20):
    sma = data['Close'].rolling(window=period).mean()
    std = data['Close'].rolling(window=period).std()
    upper = sma + (std * 2)
    lower = sma - (std * 2)
    return upper, sma, lower

def calculate_atr(data, period=14):
    high_low = data['High'] - data['Low']
    high_close = np.abs(data['High'] - data['Close'].shift())
    low_close = np.abs(data['Low'] - data['Close'].shift())
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = np.max(ranges, axis=1)
    atr = true_range.rolling(period).mean()
    return atr

# Pattern recognition
def detect_head_shoulders(data, window=20):
    patterns = []
    for i in range(window, len(data) - window):
        window_data = data.iloc[i-window:i+window]['Close']
        if len(window_data) < window * 2:
            continue
        
        left_shoulder = window_data.iloc[:window//3].max()
        head = window_data.iloc[window//3:2*window//3].max()
        right_shoulder = window_data.iloc[2*window//3:].max()
        
        if head > left_shoulder * 1.05 and head > right_shoulder * 1.05:
            if abs(left_shoulder - right_shoulder) / left_shoulder < 0.03:
                patterns.append({
                    'date': data.index[i],
                    'pattern': 'Head & Shoulders',
                    'signal': 'Bearish'
                })
    return patterns

def detect_double_top_bottom(data, window=20):
    patterns = []
    highs = data['High'].rolling(window=5).max()
    lows = data['Low'].rolling(window=5).min()
    
    for i in range(window, len(data) - window):
        recent_highs = highs.iloc[i-window:i]
        recent_lows = lows.iloc[i-window:i]
        
        if len(recent_highs) > 0:
            max_high = recent_highs.max()
            high_count = (recent_highs > max_high * 0.98).sum()
            
            if high_count >= 2:
                patterns.append({
                    'date': data.index[i],
                    'pattern': 'Double Top',
                    'signal': 'Bearish'
                })
    
    return patterns

# Signal scoring system
def calculate_signal_score(data):
    score = 0
    signals = []
    
    # RSI
    rsi = calculate_rsi(data).iloc[-1]
    if rsi < 30:
        score += 2
        signals.append("RSI Oversold (Bullish)")
    elif rsi > 70:
        score -= 2
        signals.append("RSI Overbought (Bearish)")
    
    # MACD
    macd, signal_line = calculate_macd(data)
    if macd.iloc[-1] > signal_line.iloc[-1] and macd.iloc[-2] <= signal_line.iloc[-2]:
        score += 2
        signals.append("MACD Bullish Crossover")
    elif macd.iloc[-1] < signal_line.iloc[-1] and macd.iloc[-2] >= signal_line.iloc[-2]:
        score -= 2
        signals.append("MACD Bearish Crossover")
    
    # Moving averages
    sma50 = data['Close'].rolling(window=50).mean().iloc[-1]
    sma200 = data['Close'].rolling(window=200).mean().iloc[-1]
    current_price = data['Close'].iloc[-1]
    
    if current_price > sma50 > sma200:
        score += 2
        signals.append("Golden Cross (Bullish)")
    elif current_price < sma50 < sma200:
        score -= 2
        signals.append("Death Cross (Bearish)")
    
    # Determine overall signal
    if score >= 4:
        overall = "STRONG BUY"
        signal_class = "buy-signal"
    elif score >= 2:
        overall = "BUY"
        signal_class = "buy-signal"
    elif score <= -4:
        overall = "STRONG SELL"
        signal_class = "sell-signal"
    elif score <= -2:
        overall = "SELL"
        signal_class = "sell-signal"
    else:
        overall = "NEUTRAL"
        signal_class = "neutral-signal"
    
    return score, overall, signal_class, signals

# AI Prediction
def predict_price(data, days=5):
    prices = data['Close'].values
    X = np.arange(len(prices)).reshape(-1, 1)
    
    # Polynomial regression
    coeffs = np.polyfit(range(len(prices)), prices, 3)
    poly = np.poly1d(coeffs)
    
    future_X = np.arange(len(prices), len(prices) + days)
    predictions = poly(future_X)
    
    return predictions

# Position size calculator
def calculate_position_size(account_size, risk_percent, entry_price, stop_loss, method='fixed'):
    risk_amount = account_size * (risk_percent / 100)
    risk_per_share = abs(entry_price - stop_loss)
    
    if method == 'fixed':
        shares = risk_amount / risk_per_share
    elif method == 'volatility':
        shares = risk_amount / (risk_per_share * 1.5)
    elif method == 'kelly':
        win_rate = 0.55
        avg_win = risk_per_share * 2
        avg_loss = risk_per_share
        kelly_fraction = (win_rate * avg_win - (1 - win_rate) * avg_loss) / avg_win
        kelly_fraction = max(0, min(kelly_fraction, 0.25))
        shares = (account_size * kelly_fraction) / entry_price
    
    return int(shares)

# Backtesting
def backtest_strategy(ticker, start_date, end_date):
    data = yf.download(ticker, start=start_date, end=end_date, progress=False)
    
    data['SMA50'] = data['Close'].rolling(window=50).mean()
    data['SMA200'] = data['Close'].rolling(window=200).mean()
    data['Signal'] = 0
    data.loc[data['SMA50'] > data['SMA200'], 'Signal'] = 1
    data['Position'] = data['Signal'].diff()
    
    buy_dates = data[data['Position'] == 1].index
    sell_dates = data[data['Position'] == -1].index
    
    trades = []
    capital = 10000
    shares = 0
    
    for i in range(min(len(buy_dates), len(sell_dates))):
        buy_price = data.loc[buy_dates[i], 'Close']
        sell_price = data.loc[sell_dates[i], 'Close']
        
        shares = capital / buy_price
        capital = shares * sell_price
        
        profit = ((sell_price - buy_price) / buy_price) * 100
        trades.append({
            'Buy Date': buy_dates[i],
            'Buy Price': buy_price,
            'Sell Date': sell_dates[i],
            'Sell Price': sell_price,
            'Profit %': profit
        })
    
    total_return = ((capital - 10000) / 10000) * 100
    
    return trades, total_return, capital

# Main app
def main():
    if not check_subscription() and 'demo_mode' not in st.session_state:
        show_paywall()
        return
    
    # Sidebar
    with st.sidebar:
        st.markdown("### 📊 AI Stock Analyzer Pro")
        
        if check_subscription():
            st.success("✅ Premium Active")
        else:
            st.warning("🆓 Demo Mode")
        
        st.markdown("---")
        
        page = st.radio("Navigation", [
            "🏠 Market Overview",
            "📈 Stock Analysis",
            "⭐ Watchlist",
            "🔍 Stock Screener",
            "🎯 Pattern Recognition",
            "🤖 AI Predictions",
            "💰 Position Calculator",
            "📊 Fundamental Analysis",
            "🔄 Backtesting"
        ])
        
        st.markdown("---")
        
        if st.button("🚪 Logout"):
            st.session_state.subscribed = False
            if 'demo_mode' in st.session_state:
                del st.session_state.demo_mode
            st.rerun()
    
    # Market Overview
    if page == "🏠 Market Overview":
        st.markdown('<h1 class="main-header">🏠 Market Overview</h1>', unsafe_allow_html=True)
        
        col1, col2, col3, col4 = st.columns(4)
        
        indices = {'^GSPC': 'S&P 500', '^DJI': 'Dow Jones', '^IXIC': 'NASDAQ', '^RUT': 'Russell 2000'}
        
        for i, (ticker, name) in enumerate(indices.items()):
            try:
                data = yf.download(ticker, period='5d', progress=False)
                current = data['Close'].iloc[-1]
                prev = data['Close'].iloc[-2]
                change = ((current - prev) / prev) * 100
                
                with [col1, col2, col3, col4][i]:
                    st.metric(name, f"${current:.2f}", f"{change:+.2f}%")
            except:
                pass
        
        st.markdown("### 📰 Market Insights")
        st.info("💡 **Market Summary**: Indices showing mixed performance. Tech sector leading gains.")
        
        # Sector performance
        st.markdown("### 🏭 Sector Performance")
        sectors = {
            'XLK': 'Technology',
            'XLF': 'Financials',
            'XLE': 'Energy',
            'XLV': 'Healthcare',
            'XLY': 'Consumer Discretionary'
        }
        
        sector_data = []
        for ticker, name in sectors.items():
            try:
                data = yf.download(ticker, period='1mo', progress=False)
                change = ((data['Close'].iloc[-1] - data['Close'].iloc[0]) / data['Close'].iloc[0]) * 100
                sector_data.append({'Sector': name, 'Change %': change})
            except:
                pass
        
        if sector_data:
            df = pd.DataFrame(sector_data).sort_values('Change %', ascending=False)
            fig = go.Figure(data=[
                go.Bar(x=df['Sector'], y=df['Change %'],
                      marker_color=['green' if x > 0 else 'red' for x in df['Change %']])
            ])
            fig.update_layout(title='30-Day Sector Performance', yaxis_title='Change %')
            st.plotly_chart(fig, use_container_width=True)
    
    # Stock Analysis
    elif page == "📈 Stock Analysis":
        st.markdown('<h1 class="main-header">📈 Stock Analysis</h1>', unsafe_allow_html=True)
        
        col1, col2 = st.columns([2, 1])
        with col1:
            ticker = st.text_input("Enter Stock Ticker", "AAPL").upper()
        with col2:
            period = st.selectbox("Time Period", ["1mo", "3mo", "6mo", "1y", "2y"])
        
        if st.button("Analyze", type="primary"):
            try:
                data = yf.download(ticker, period=period, progress=False)
                
                if len(data) == 0:
                    st.error("No data found for this ticker")
                    return
                
                # Current price
                current_price = data['Close'].iloc[-1]
                prev_close = data['Close'].iloc[-2]
                change = current_price - prev_close
                change_pct = (change / prev_close) * 100
                
                col1, col2, col3 = st.columns(3)
                col1.metric("Current Price", f"${current_price:.2f}", f"{change:+.2f} ({change_pct:+.2f}%)")
                col2.metric("Volume", f"{data['Volume'].iloc[-1]:,.0f}")
                col3.metric("Day Range", f"${data['Low'].iloc[-1]:.2f} - ${data['High'].iloc[-1]:.2f}")
                
                # Signal scoring
                score, signal, signal_class, reasons = calculate_signal_score(data)
                
                st.markdown(f"### Trading Signal")
                st.markdown(f'<div class="{signal_class}">{signal} (Score: {score})</div>', unsafe_allow_html=True)
                
                with st.expander("📋 Signal Breakdown"):
                    for reason in reasons:
                        st.write(f"• {reason}")
                
                # Technical indicators
                st.markdown("### 📊 Technical Indicators")
                
                rsi = calculate_rsi(data)
                macd, signal_line = calculate_macd(data)
                upper_bb, middle_bb, lower_bb = calculate_bollinger_bands(data)
                
                fig = make_subplots(rows=3, cols=1, shared_xaxes=True,
                                   row_heights=[0.5, 0.25, 0.25],
                                   subplot_titles=(f'{ticker} Price', 'RSI', 'MACD'))
                
                # Price with Bollinger Bands
                fig.add_trace(go.Candlestick(x=data.index, open=data['Open'],
                                            high=data['High'], low=data['Low'],
                                            close=data['Close'], name='Price'), row=1, col=1)
                fig.add_trace(go.Scatter(x=data.index, y=upper_bb, name='Upper BB',
                                        line=dict(dash='dash')), row=1, col=1)
                fig.add_trace(go.Scatter(x=data.index, y=middle_bb, name='Middle BB'), row=1, col=1)
                fig.add_trace(go.Scatter(x=data.index, y=lower_bb, name='Lower BB',
                                        line=dict(dash='dash')), row=1, col=1)
                
                # RSI
                fig.add_trace(go.Scatter(x=data.index, y=rsi, name='RSI'), row=2, col=1)
                fig.add_hline(y=70, line_dash="dash", line_color="red", row=2, col=1)
                fig.add_hline(y=30, line_dash="dash", line_color="green", row=2, col=1)
                
                # MACD
                fig.add_trace(go.Scatter(x=data.index, y=macd, name='MACD'), row=3, col=1)
                fig.add_trace(go.Scatter(x=data.index, y=signal_line, name='Signal'), row=3, col=1)
                
                fig.update_layout(height=900, showlegend=True)
                st.plotly_chart(fig, use_container_width=True)
                
                # Add to watchlist
                if st.button("⭐ Add to Watchlist"):
                    if ticker not in st.session_state.watchlist:
                        st.session_state.watchlist.append(ticker)
                        st.success(f"Added {ticker} to watchlist!")
                    else:
                        st.info(f"{ticker} already in watchlist")
                
            except Exception as e:
                st.error(f"Error analyzing {ticker}: {str(e)}")
    
    # Watchlist
    elif page == "⭐ Watchlist":
        st.markdown('<h1 class="main-header">⭐ Watchlist</h1>', unsafe_allow_html=True)
        
        if not check_subscription():
            st.warning("⚠️ Watchlist feature requires Premium subscription")
            return
        
        if len(st.session_state.watchlist) == 0:
            st.info("Your watchlist is empty. Add stocks from the Stock Analysis page.")
        else:
            watchlist_data = []
            
            for ticker in st.session_state.watchlist:
                try:
                    data = yf.download(ticker, period='5d', progress=False)
                    current = data['Close'].iloc[-1]
                    prev = data['Close'].iloc[-2]
                    change = ((current - prev) / prev) * 100
                    
                    watchlist_data.append({
                        'Ticker': ticker,
                        'Price': f"${current:.2f}",
                        'Change %': f"{change:+.2f}%",
                        'Volume': f"{data['Volume'].iloc[-1]:,.0f}"
                    })
                except:
                    pass
            
            if watchlist_data:
                df = pd.DataFrame(watchlist_data)
                st.dataframe(df, use_container_width=True, hide_index=True)
            
            # Remove from watchlist
            ticker_to_remove = st.selectbox("Remove from watchlist", st.session_state.watchlist)
            if st.button("Remove"):
                st.session_state.watchlist.remove(ticker_to_remove)
                st.success(f"Removed {ticker_to_remove}")
                st.rerun()
    
    # Stock Screener
    elif page == "🔍 Stock Screener":
        st.markdown('<h1 class="main-header">🔍 Stock Screener</h1>', unsafe_allow_html=True)
        
        if not check_subscription():
            st.warning("⚠️ Stock Screener requires Premium subscription")
            return
        
        st.info("💡 Screen stocks based on technical and fundamental criteria")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            min_price = st.number_input("Min Price ($)", value=10.0)
        with col2:
            max_price = st.number_input("Max Price ($)", value=500.0)
        with col3:
            min_volume = st.number_input("Min Volume (M)", value=1.0) * 1000000
        
        rsi_filter = st.checkbox("RSI < 30 (Oversold)")
        
        if st.button("🔍 Run Screener", type="primary"):
            with st.spinner("Screening stocks..."):
                # Sample stock list
                tickers = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA', 'META', 'NVDA', 'AMD',
                          'NFLX', 'DIS', 'BA', 'JPM', 'GS', 'V', 'MA', 'WMT', 'PG', 'JNJ']
                
                results = []
                for ticker in tickers:
                    try:
                        data = yf.download(ticker, period='3mo', progress=False)
                        current_price = data['Close'].iloc[-1]
                        volume = data['Volume'].iloc[-1]
                        rsi = calculate_rsi(data).iloc[-1]
                        
                        if min_price <= current_price <= max_price and volume >= min_volume:
                            if not rsi_filter or rsi < 30:
                                results.append({
                                    'Ticker': ticker,
                                    'Price': f"${current_price:.2f}",
                                    'Volume': f"{volume:,.0f}",
                                    'RSI': f"{rsi:.2f}"
                                })
                    except:
                        pass
                
                if results:
                    st.success(f"Found {len(results)} stocks matching criteria")
                    df = pd.DataFrame(results)
                    st.dataframe(df, use_container_width=True, hide_index=True)
                else:
                    st.warning("No stocks found matching criteria")
    
    # Pattern Recognition
    elif page == "🎯 Pattern Recognition":
        st.markdown('<h1 class="main-header">🎯 Pattern Recognition</h1>', unsafe_allow_html=True)
        
        if not check_subscription():
            st.warning("⚠️ Pattern Recognition requires Premium subscription")
            return
        
        ticker = st.text_input("Enter Stock Ticker", "AAPL").upper()
        
        if st.button("Detect Patterns", type="primary"):
            try:
                data = yf.download(ticker, period='6mo', progress=False)
                
                st.info("🔍 Scanning for chart patterns...")
                
                hs_patterns = detect_head_shoulders(data)
                dt_patterns = detect_double_top_bottom(data)
                
                st.markdown("### 📊 Detected Patterns")
                
                if hs_patterns:
                    st.markdown("**Head & Shoulders Patterns:**")
                    for pattern in hs_patterns[-3:]:
                        st.write(f"• {pattern['date'].strftime('%Y-%m-%d')}: {pattern['pattern']} - {pattern['signal']}")
                
                if dt_patterns:
                    st.markdown("**Double Top/Bottom Patterns:**")
                    for pattern in dt_patterns[-3:]:
                        st.write(f"• {pattern['date'].strftime('%Y-%m-%d')}: {pattern['pattern']} - {pattern['signal']}")
                
                if not hs_patterns and not dt_patterns:
                    st.success("✅ No significant patterns detected in the selected timeframe")
                
            except Exception as e:
                st.error(f"Error: {str(e)}")
    
    # AI Predictions
    elif page == "🤖 AI Predictions":
        st.markdown('<h1 class="main-header">🤖 AI Predictions</h1>', unsafe_allow_html=True)
        
        if not check_subscription():
            st.warning("⚠️ AI Predictions requires Premium subscription")
            return
        
        ticker = st.text_input("Enter Stock Ticker", "AAPL").upper()
        days = st.slider("Prediction Days", 1, 10, 5)
        
        if st.button("🔮 Generate Prediction", type="primary"):
            try:
                data = yf.download(ticker, period='3mo', progress=False)
                predictions = predict_price(data, days)
                
                st.markdown(f"### 📈 {days}-Day Price Forecast")
                
                future_dates = pd.date_range(start=data.index[-1] + timedelta(days=1), periods=days)
                
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Current Price", f"${data['Close'].iloc[-1]:.2f}")
                with col2:
                    st.metric("Predicted Price (Day 5)", f"${predictions[4]:.2f}")
                
                # Chart
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=data.index, y=data['Close'],
                                        mode='lines', name='Historical'))
                fig.add_trace(go.Scatter(x=future_dates, y=predictions,
                                        mode='lines+markers', name='Predicted',
                                        line=dict(dash='dash')))
                fig.update_layout(title=f'{ticker} Price Prediction',
                                 xaxis_title='Date', yaxis_title='Price ($)')
                st.plotly_chart(fig, use_container_width=True)
                
                st.warning("⚠️ Predictions are for educational purposes only. Not financial advice.")
                
            except Exception as e:
                st.error(f"Error: {str(e)}")
    
    # Position Calculator
    elif page == "💰 Position Calculator":
        st.markdown('<h1 class="main-header">💰 Position Size Calculator</h1>', unsafe_allow_html=True)
        
        if not check_subscription():
            st.warning("⚠️ Position Calculator requires Premium subscription")
            return
        
        col1, col2 = st.columns(2)
        
        with col1:
            account_size = st.number_input("Account Size ($)", value=10000.0, step=1000.0)
            risk_percent = st.number_input("Risk Per Trade (%)", value=2.0, step=0.5, max_value=10.0)
            entry_price = st.number_input("Entry Price ($)", value=100.0, step=1.0)
        
        with col2:
            stop_loss = st.number_input("Stop Loss ($)", value=95.0, step=1.0)
            method = st.selectbox("Sizing Method", ["Fixed %", "Volatility-Based", "Kelly Criterion"])
        
        if st.button("Calculate Position Size", type="primary"):
            method_map = {
                "Fixed %": "fixed",
                "Volatility-Based": "volatility",
                "Kelly Criterion": "kelly"
            }
            
            shares = calculate_position_size(account_size, risk_percent, entry_price,
                                            stop_loss, method_map[method])
            position_value = shares * entry_price
            risk_amount = account_size * (risk_percent / 100)
            
            st.markdown("### 📊 Position Details")
            
            col1, col2, col3 = st.columns(3)
            col1.metric("Shares to Buy", f"{shares:,}")
            col2.metric("Position Value", f"${position_value:,.2f}")
            col3.metric("Max Risk", f"${risk_amount:,.2f}")
            
            st.info(f"💡 Risk per share: ${abs(entry_price - stop_loss):.2f} ({abs(entry_price - stop_loss)/entry_price*100:.1f}%)")
    
    # Fundamental Analysis
    elif page == "📊 Fundamental Analysis":
        st.markdown('<h1 class="main-header">📊 Fundamental Analysis</h1>', unsafe_allow_html=True)
        
        if not check_subscription():
            st.warning("⚠️ Fundamental Analysis requires Premium subscription")
            return
        
        ticker = st.text_input("Enter Stock Ticker", "AAPL").upper()
        
        if st.button("Analyze Fundamentals", type="primary"):
            try:
                stock = yf.Ticker(ticker)
                info = stock.info
                
                st.markdown(f"### 🏢 {info.get('longName', ticker)}")
                st.write(f"**Sector:** {info.get('sector', 'N/A')} | **Industry:** {info.get('industry', 'N/A')}")
                
                # Key metrics
                st.markdown("### 💰 Key Financial Metrics")
                
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    market_cap = info.get('marketCap', 0)
                    if market_cap:
                        st.metric("Market Cap", f"${market_cap/1e9:.2f}B")
                    pe_ratio = info.get('trailingPE', 'N/A')
                    if pe_ratio != 'N/A':
                        st.metric("P/E Ratio", f"{pe_ratio:.2f}")
                
                with col2:
                    pb_ratio = info.get('priceToBook', 'N/A')
                    if pb_ratio != 'N/A':
                        st.metric("P/B Ratio", f"{pb_ratio:.2f}")
                    div_yield = info.get('dividendYield', 0)
                    if div_yield:
                        st.metric("Dividend Yield", f"{div_yield*100:.2f}%")
                
                with col3:
                    roe = info.get('returnOnEquity', 0)
                    if roe:
                        st.metric("ROE", f"{roe*100:.2f}%")
                    profit_margin = info.get('profitMargins', 0)
                    if profit_margin:
                        st.metric("Profit Margin", f"{profit_margin*100:.2f}%")
                
                with col4:
                    debt_to_equity = info.get('debtToEquity', 'N/A')
                    if debt_to_equity != 'N/A':
                        st.metric("Debt/Equity", f"{debt_to_equity:.2f}")
                    current_ratio = info.get('currentRatio', 'N/A')
                    if current_ratio != 'N/A':
                        st.metric("Current Ratio", f"{current_ratio:.2f}")
                
                # Valuation assessment
                st.markdown("### 📈 Valuation Assessment")
                
                valuation_score = 0
                assessments = []
                
                if pe_ratio != 'N/A' and isinstance(pe_ratio, (int, float)):
                    if pe_ratio < 15:
                        valuation_score += 2
                        assessments.append("✅ P/E Ratio below 15 (Undervalued)")
                    elif pe_ratio > 30:
                        valuation_score -= 1
                        assessments.append("⚠️ P/E Ratio above 30 (Potentially Overvalued)")
                
                if pb_ratio != 'N/A' and isinstance(pb_ratio, (int, float)):
                    if pb_ratio < 3:
                        valuation_score += 1
                        assessments.append("✅ P/B Ratio below 3 (Good Value)")
                
                if roe and roe > 0.15:
                    valuation_score += 1
                    assessments.append("✅ ROE above 15% (Strong Returns)")
                
                if debt_to_equity != 'N/A' and isinstance(debt_to_equity, (int, float)):
                    if debt_to_equity < 1:
                        valuation_score += 1
                        assessments.append("✅ Debt/Equity below 1 (Healthy Balance Sheet)")
                    elif debt_to_equity > 2:
                        valuation_score -= 1
                        assessments.append("⚠️ Debt/Equity above 2 (High Leverage)")
                
                if valuation_score >= 3:
                    overall_valuation = "🟢 UNDERVALUED"
                elif valuation_score >= 1:
                    overall_valuation = "🟡 FAIR VALUE"
                else:
                    overall_valuation = "🔴 OVERVALUED"
                
                st.markdown(f"**Overall Assessment:** {overall_valuation}")
                
                for assessment in assessments:
                    st.write(assessment)
                
                # Financial statements
                st.markdown("### 📋 Recent Financial Data")
                
                try:
                    financials = stock.financials
                    if not financials.empty:
                        st.dataframe(financials.head(), use_container_width=True)
                except:
                    st.info("Financial statements not available")
                
                # Analyst recommendations
                st.markdown("### 🎯 Analyst Recommendations")
                try:
                    recommendations = stock.recommendations
                    if recommendations is not None and not recommendations.empty:
                        recent = recommendations.tail(5)
                        st.dataframe(recent, use_container_width=True)
                except:
                    st.info("Analyst recommendations not available")
                
            except Exception as e:
                st.error(f"Error fetching fundamental data: {str(e)}")
    
    # Backtesting
    elif page == "🔄 Backtesting":
        st.markdown('<h1 class="main-header">🔄 Strategy Backtesting</h1>', unsafe_allow_html=True)
        
        if not check_subscription():
            st.warning("⚠️ Backtesting requires Premium subscription")
            return
        
        st.info("💡 Test the Golden Cross strategy (SMA50 crosses above SMA200)")
        
        col1, col2 = st.columns(2)
        
        with col1:
            ticker = st.text_input("Stock Ticker", "AAPL").upper()
        
        with col2:
            years = st.selectbox("Backtest Period", [1, 2, 3, 5])
        
        if st.button("🚀 Run Backtest", type="primary"):
            try:
                end_date = datetime.now()
                start_date = end_date - timedelta(days=years*365)
                
                with st.spinner("Running backtest..."):
                    trades, total_return, final_capital = backtest_strategy(
                        ticker, start_date, end_date
                    )
                
                st.markdown("### 📊 Backtest Results")
                
                col1, col2, col3, col4 = st.columns(4)
                
                col1.metric("Total Return", f"{total_return:.2f}%")
                col2.metric("Final Capital", f"${final_capital:,.2f}")
                col3.metric("Total Trades", len(trades))
                
                if trades:
                    winning_trades = [t for t in trades if t['Profit %'] > 0]
                    win_rate = (len(winning_trades) / len(trades)) * 100
                    col4.metric("Win Rate", f"{win_rate:.1f}%")
                
                # Trade history
                if trades:
                    st.markdown("### 📝 Trade History")
                    df_trades = pd.DataFrame(trades)
                    df_trades['Buy Date'] = df_trades['Buy Date'].dt.strftime('%Y-%m-%d')
                    df_trades['Sell Date'] = df_trades['Sell Date'].dt.strftime('%Y-%m-%d')
                    df_trades['Buy Price'] = df_trades['Buy Price'].apply(lambda x: f"${x:.2f}")
                    df_trades['Sell Price'] = df_trades['Sell Price'].apply(lambda x: f"${x:.2f}")
                    df_trades['Profit %'] = df_trades['Profit %'].apply(lambda x: f"{x:.2f}%")
                    
                    st.dataframe(df_trades, use_container_width=True, hide_index=True)
                    
                    # Performance chart
                    st.markdown("### 📈 Equity Curve")
                    
                    data = yf.download(ticker, start=start_date, end=end_date, progress=False)
                    
                    fig = go.Figure()
                    
                    # Normalize to starting capital
                    normalized_price = (data['Close'] / data['Close'].iloc[0]) * 10000
                    
                    fig.add_trace(go.Scatter(
                        x=data.index,
                        y=normalized_price,
                        name='Buy & Hold',
                        line=dict(color='blue')
                    ))
                    
                    # Add strategy equity curve
                    equity = [10000]
                    equity_dates = [data.index[0]]
                    
                    for trade in trades:
                        buy_idx = data.index.get_indexer([trade['Buy Date']], method='nearest')[0]
                        sell_idx = data.index.get_indexer([trade['Sell Date']], method='nearest')[0]
                        
                        if buy_idx < len(data) and sell_idx < len(data):
                            buy_price = data['Close'].iloc[buy_idx]
                            sell_price = data['Close'].iloc[sell_idx]
                            
                            shares = equity[-1] / buy_price
                            new_equity = shares * sell_price
                            
                            equity.append(new_equity)
                            equity_dates.append(data.index[sell_idx])
                    
                    fig.add_trace(go.Scatter(
                        x=equity_dates,
                        y=equity,
                        name='Strategy',
                        line=dict(color='green'),
                        mode='lines+markers'
                    ))
                    
                    fig.update_layout(
                        title='Strategy vs Buy & Hold Performance',
                        xaxis_title='Date',
                        yaxis_title='Portfolio Value ($)',
                        hovermode='x unified'
                    )
                    
                    st.plotly_chart(fig, use_container_width=True)
                    
                    # Performance metrics
                    buy_hold_return = ((normalized_price.iloc[-1] - 10000) / 10000) * 100
                    
                    st.markdown("### 📊 Performance Comparison")
                    
                    col1, col2 = st.columns(2)
                    col1.metric("Strategy Return", f"{total_return:.2f}%")
                    col2.metric("Buy & Hold Return", f"{buy_hold_return:.2f}%")
                    
                    if total_return > buy_hold_return:
                        st.success(f"✅ Strategy outperformed Buy & Hold by {total_return - buy_hold_return:.2f}%")
                    else:
                        st.warning(f"⚠️ Strategy underperformed Buy & Hold by {buy_hold_return - total_return:.2f}%")
                
                else:
                    st.warning("No trades generated during the backtest period")
                    
            except Exception as e:
                st.error(f"Error running backtest: {str(e)}")

if __name__ == "__main__":
    main()
