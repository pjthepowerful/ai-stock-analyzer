import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Page configuration
st.set_page_config(
    page_title="WealthStockify - Premium Stock Analysis",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 1rem;
    }
    .premium-badge {
        background: gold;
        color: black;
        padding: 0.3rem 0.8rem;
        border-radius: 20px;
        font-weight: bold;
        font-size: 0.8rem;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'is_premium' not in st.session_state:
    st.session_state.is_premium = False
if 'watchlist' not in st.session_state:
    st.session_state.watchlist = []

# Helper Functions
def calculate_technical_indicators(df):
    """Calculate various technical indicators"""
    # RSI
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    
    # MACD
    exp1 = df['Close'].ewm(span=12, adjust=False).mean()
    exp2 = df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = exp1 - exp2
    df['Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    
    # Bollinger Bands
    df['BB_Middle'] = df['Close'].rolling(window=20).mean()
    bb_std = df['Close'].rolling(window=20).std()
    df['BB_Upper'] = df['BB_Middle'] + (bb_std * 2)
    df['BB_Lower'] = df['BB_Middle'] - (bb_std * 2)
    
    # Moving Averages
    df['SMA_50'] = df['Close'].rolling(window=50).mean()
    df['SMA_200'] = df['Close'].rolling(window=200).mean()
    
    # ATR
    high_low = df['High'] - df['Low']
    high_close = np.abs(df['High'] - df['Close'].shift())
    low_close = np.abs(df['Low'] - df['Close'].shift())
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = np.max(ranges, axis=1)
    df['ATR'] = true_range.rolling(14).mean()
    
    return df

def calculate_ai_score(df, info):
    """Calculate AI-based stock score (0-100)"""
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
    """Simple price prediction"""
    if len(df) < 30:
        return None
    
    recent_df = df.tail(90).copy()
    recent_df['Days'] = range(len(recent_df))
    
    X = recent_df['Days'].values
    y = recent_df['Close'].values
    
    x_mean = X.mean()
    y_mean = y.mean()
    
    numerator = ((X - x_mean) * (y - y_mean)).sum()
    denominator = ((X - x_mean) ** 2).sum()
    
    if denominator == 0:
        return None
    
    slope = numerator / denominator
    intercept = y_mean - slope * x_mean
    
    momentum = (df['Close'].iloc[-1] - df['Close'].iloc[-30]) / df['Close'].iloc[-30]
    adjusted_slope = slope * (1 + momentum * 0.5)
    
    future_day = len(recent_df) + days
    predicted_price = adjusted_slope * future_day + intercept
    
    return max(predicted_price, 0)

def calculate_position_size(account_size, stock_price, method='fixed', risk_percent=2, volatility=None, win_rate=0.55, avg_win=1.5, avg_loss=1):
    """Calculate position size"""
    if method == 'fixed':
        risk_amount = account_size * (risk_percent / 100)
        shares = int(risk_amount / stock_price)
        
    elif method == 'kelly':
        q = 1 - win_rate
        b = avg_win / avg_loss
        kelly_fraction = (win_rate * b - q) / b
        kelly_fraction = max(0, min(kelly_fraction * 0.5, 0.25))
        position_value = account_size * kelly_fraction
        shares = int(position_value / stock_price)
        
    elif method == 'volatility' and volatility:
        target_risk = account_size * (risk_percent / 100)
        position_value = target_risk / volatility
        shares = int(position_value / stock_price)
    else:
        shares = 0
    
    return max(shares, 0)

def run_backtest(ticker, start_date, end_date, initial_capital=10000):
    """Run backtest"""
    stock = yf.Ticker(ticker)
    df = stock.history(start=start_date, end=end_date)
    
    if df.empty:
        return None
    
    df = calculate_technical_indicators(df)
    df['Signal'] = 0
    
    for i in range(1, len(df)):
        if pd.notna(df['MACD'].iloc[i]) and pd.notna(df['Signal'].iloc[i]) and pd.notna(df['RSI'].iloc[i]):
            if (df['MACD'].iloc[i] > df['Signal'].iloc[i] and 
                df['MACD'].iloc[i-1] <= df['Signal'].iloc[i-1] and 
                df['RSI'].iloc[i] < 70):
                df.loc[df.index[i], 'Signal'] = 1
            elif (df['MACD'].iloc[i] < df['Signal'].iloc[i] and 
                  df['MACD'].iloc[i-1] >= df['Signal'].iloc[i-1]):
                df.loc[df.index[i], 'Signal'] = -1
    
    df['Position'] = df['Signal'].replace(0, np.nan).ffill().fillna(0)
    df['Returns'] = df['Close'].pct_change()
    df['Strategy_Returns'] = df['Position'].shift(1) * df['Returns']
    df['Cumulative_Returns'] = (1 + df['Returns']).cumprod()
    df['Cumulative_Strategy_Returns'] = (1 + df['Strategy_Returns']).cumprod()
    
    total_return = (df['Cumulative_Strategy_Returns'].iloc[-1] - 1) * 100
    buy_hold_return = (df['Cumulative_Returns'].iloc[-1] - 1) * 100
    
    trades = df[df['Signal'] != 0]
    num_trades = len(trades)
    
    if df['Strategy_Returns'].std() != 0:
        sharpe_ratio = np.sqrt(252) * df['Strategy_Returns'].mean() / df['Strategy_Returns'].std()
    else:
        sharpe_ratio = 0
    
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
    """Screen stocks"""
    tickers = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA', 'META', 'NVDA', 'AMD', 'NFLX', 'DIS',
               'JPM', 'BAC', 'V', 'MA', 'JNJ', 'PFE', 'XOM', 'CVX', 'WMT', 'HD']
    
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
                    'RSI': hist['RSI'].iloc[-1] if 'RSI' in hist.columns else 0
                })
            
            progress_bar.progress((idx + 1) / len(tickers))
        except:
            continue
    
    progress_bar.empty()
    return pd.DataFrame(results).sort_values('AI_Score', ascending=False)

# Sidebar
with st.sidebar:
    st.markdown('<div class="main-header">WealthStockify</div>', unsafe_allow_html=True)
    
    if st.session_state.is_premium:
        st.markdown('<span class="premium-badge">⭐ PREMIUM</span>', unsafe_allow_html=True)
        st.success("All features unlocked!")
    else:
        st.warning("FREE TIER - Limited Access")
        if st.button("Upgrade to Premium"):
            st.session_state.is_premium = True
            st.rerun()
    
    st.markdown("---")
    
    page = st.radio(
        "Navigation",
        ["Stock Analysis", "Stock Screener", "Backtesting", "Watchlist", "Position Sizer"]
    )

# Main Content
if page == "Stock Analysis":
    st.title("📊 Stock Analysis Dashboard")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        ticker = st.text_input("Enter Stock Ticker", value="AAPL").upper()
    
    with col2:
        period = st.selectbox("Time Period", ["1mo", "3mo", "6mo", "1y", "2y"])
    
    if ticker:
        try:
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
                
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.metric("Current Price", f"${current_price:.2f}", f"{change_pct:.2f}%")
                
                with col2:
                    if st.session_state.is_premium:
                        ai_score = calculate_ai_score(hist, info)
                        color = "🟢" if ai_score >= 70 else "🟡" if ai_score >= 50 else "🔴"
                        st.metric("AI Score", f"{color} {ai_score:.0f}/100")
                    else:
                        st.metric("AI Score", "🔒 Premium")
                
                with col3:
                    volume = info.get('volume', 0)
                    st.metric("Volume", f"{volume:,}")
                
                st.subheader("Price Chart")
                
                fig = make_subplots(
                    rows=3, cols=1,
                    shared_xaxes=True,
                    vertical_spacing=0.05,
                    row_heights=[0.6, 0.2, 0.2],
                    subplot_titles=(f'{ticker} Price', 'MACD', 'RSI')
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
                
                if st.session_state.is_premium:
                    fig.add_trace(go.Scatter(x=hist.index, y=hist['SMA_50'], name='SMA 50', line=dict(color='orange')), row=1, col=1)
                    fig.add_trace(go.Scatter(x=hist.index, y=hist['SMA_200'], name='SMA 200', line=dict(color='red')), row=1, col=1)
                    fig.add_trace(go.Scatter(x=hist.index, y=hist['MACD'], name='MACD', line=dict(color='blue')), row=2, col=1)
                    fig.add_trace(go.Scatter(x=hist.index, y=hist['Signal'], name='Signal', line=dict(color='red')), row=2, col=1)
                    fig.add_trace(go.Scatter(x=hist.index, y=hist['RSI'], name='RSI', line=dict(color='purple')), row=3, col=1)
                    fig.add_hline(y=70, line_dash="dash", line_color="red", row=3, col=1)
                    fig.add_hline(y=30, line_dash="dash", line_color="green", row=3, col=1)
                
                fig.update_layout(height=800, showlegend=True, xaxis_rangeslider_visible=False)
                st.plotly_chart(fig, use_container_width=True)
                
                if st.session_state.is_premium:
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
                            st.metric("30-Day Prediction", f"${pred_30:.2f}", f"{pred_change:.2f}%")
                            st.caption("⚠️ For educational purposes only")
                
        except Exception as e:
            st.error(f"Error: {str(e)}")

elif page == "Stock Screener":
    st.title("🔍 Stock Screener")
    
    if st.session_state.is_premium:
        if st.button("Run Screener", type="primary"):
            results_df = screen_stocks()
            
            if not results_df.empty:
                st.success(f"Found {len(results_df)} stocks")
                st.dataframe(results_df, use_container_width=True, hide_index=True)
    else:
        st.warning("🔒 Premium Feature")

elif page == "Backtesting":
    st.title("📈 Backtesting Engine")
    
    if st.session_state.is_premium:
        col1, col2 = st.columns(2)
        
        with col1:
            bt_ticker = st.text_input("Ticker", value="AAPL").upper()
            start_date = st.date_input("Start", value=datetime.now() - timedelta(days=365))
        
        with col2:
            end_date = st.date_input("End", value=datetime.now())
            initial_capital = st.number_input("Capital", value=10000, step=1000)
        
        if st.button("Run Backtest", type="primary"):
            with st.spinner("Running..."):
                results = run_backtest(bt_ticker, start_date, end_date, initial_capital)
                
                if results:
                    st.success("Complete!")
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Strategy Return", f"{results['total_return']:.2f}%")
                    with col2:
                        st.metric("Buy & Hold", f"{results['buy_hold_return']:.2f}%")
                    with col3:
                        st.metric("Trades", results['num_trades'])
                    
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(
                        x=results['df'].index,
                        y=results['df']['Cumulative_Strategy_Returns'] * initial_capital,
                        name='Strategy'
                    ))
                    fig.add_trace(go.Scatter(
                        x=results['df'].index,
                        y=results['df']['Cumulative_Returns'] * initial_capital,
                        name='Buy & Hold'
                    ))
                    fig.update_layout(title="Equity Curve", height=400)
                    st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("🔒 Premium Feature")

elif page == "Watchlist":
    st.title("👁️ Watchlist")
    
    if st.session_state.is_premium:
        new_ticker = st.text_input("Add Stock").upper()
        
        if st.button("Add") and new_ticker:
            if new_ticker not in st.session_state.watchlist:
                st.session_state.watchlist.append(new_ticker)
                st.success(f"Added {new_ticker}")
                st.rerun()
        
        if st.session_state.watchlist:
            for ticker in st.session_state.watchlist:
                try:
                    stock = yf.Ticker(ticker)
                    price = stock.history(period='1d')['Close'].iloc[-1]
                    st.write(f"{ticker}: ${price:.2f}")
                except:
                    pass
    else:
        st.warning("🔒 Premium Feature")

elif page == "Position Sizer":
    st.title("💰 Position Calculator")
    
    if st.session_state.is_premium:
        ps_ticker = st.text_input("Ticker", value="AAPL").upper()
        account_size = st.number_input("Account Size", value=100000, step=1000)
        risk_percent = st.slider("Risk %", 0.5, 5.0, 2.0, 0.5)
        
        if st.button("Calculate"):
            try:
                stock = yf.Ticker(ps_ticker)
                hist = stock.history(period='3mo')
                current_price = hist['Close'].iloc[-1]
                
                shares = calculate_position_size(account_size, current_price, 'fixed', risk_percent)
                position_value = shares * current_price
                
                st.success("Calculated!")
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Shares", f"{shares:,}")
                with col2:
                    st.metric("Position Value", f"${position_value:,.2f}")
            except Exception as e:
                st.error(f"Error: {str(e)}")
    else:
        st.warning("🔒 Premium Feature")

st.markdown("---")
st.markdown("WealthStockify © 2025 | Educational purposes only")
