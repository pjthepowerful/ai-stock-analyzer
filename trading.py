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

# Enhanced Custom CSS
st.markdown("""
<style>
    /* Import Google Fonts */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;900&display=swap');
    
    /* Global Styles */
    .stApp {
        background: linear-gradient(135deg, #0f0c29 0%, #302b63 50%, #24243e 100%);
    }
    
    /* Main Header */
    .main-header {
        font-size: 3.5rem;
        font-weight: 900;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 50%, #f093fb 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.5rem;
        font-family: 'Inter', sans-serif;
        letter-spacing: -2px;
        text-align: center;
        padding: 1rem 0;
        animation: glow 2s ease-in-out infinite alternate;
    }
    
    @keyframes glow {
        from {
            filter: drop-shadow(0 0 10px rgba(102, 126, 234, 0.5));
        }
        to {
            filter: drop-shadow(0 0 20px rgba(118, 75, 162, 0.8));
        }
    }
    
    /* Subtitle */
    .subtitle {
        text-align: center;
        color: #a0a0a0;
        font-size: 1.1rem;
        margin-bottom: 2rem;
        font-weight: 300;
    }
    
    /* Premium Badge Styles */
    .premium-badge {
        background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
        color: white;
        padding: 0.5rem 1.5rem;
        border-radius: 25px;
        font-weight: bold;
        font-size: 0.9rem;
        box-shadow: 0 4px 15px rgba(245, 87, 108, 0.4);
        display: inline-block;
        margin: 1rem 0;
        animation: pulse 2s infinite;
    }
    
    @keyframes pulse {
        0%, 100% { transform: scale(1); }
        50% { transform: scale(1.05); }
    }
    
    .free-badge {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 0.5rem 1.5rem;
        border-radius: 25px;
        font-weight: bold;
        font-size: 0.9rem;
        box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3);
        display: inline-block;
        margin: 1rem 0;
    }
    
    /* Metric Cards */
    div[data-testid="stMetricValue"] {
        font-size: 2rem;
        font-weight: 700;
        color: #ffffff;
    }
    
    div[data-testid="stMetricLabel"] {
        font-size: 0.9rem;
        color: #a0a0a0;
        font-weight: 600;
    }
    
    div[data-testid="stMetricDelta"] {
        font-size: 1rem;
    }
    
    /* Glassmorphism Cards */
    .glass-card {
        background: rgba(255, 255, 255, 0.05);
        backdrop-filter: blur(10px);
        border-radius: 20px;
        padding: 2rem;
        border: 1px solid rgba(255, 255, 255, 0.1);
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
        margin: 1rem 0;
    }
    
    /* Buttons */
    .stButton > button {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        border-radius: 12px;
        padding: 0.75rem 2rem;
        font-weight: 600;
        font-size: 1rem;
        box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);
        transition: all 0.3s ease;
        width: 100%;
    }
    
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(102, 126, 234, 0.6);
    }
    
    /* Sidebar Styling */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #1a1a2e 0%, #16213e 100%);
        border-right: 1px solid rgba(255, 255, 255, 0.1);
    }
    
    section[data-testid="stSidebar"] .stRadio > label {
        background: rgba(255, 255, 255, 0.05);
        padding: 0.75rem 1rem;
        border-radius: 10px;
        margin: 0.25rem 0;
        transition: all 0.3s ease;
        border: 1px solid transparent;
    }
    
    section[data-testid="stSidebar"] .stRadio > label:hover {
        background: rgba(102, 126, 234, 0.2);
        border: 1px solid rgba(102, 126, 234, 0.5);
        transform: translateX(5px);
    }
    
    /* Input Fields */
    .stTextInput > div > div > input {
        background: rgba(255, 255, 255, 0.05);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 10px;
        color: white;
        font-size: 1rem;
        padding: 0.75rem;
    }
    
    .stSelectbox > div > div {
        background: rgba(255, 255, 255, 0.05);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 10px;
    }
    
    /* DataFrames */
    .stDataFrame {
        background: rgba(255, 255, 255, 0.05);
        border-radius: 15px;
        border: 1px solid rgba(255, 255, 255, 0.1);
    }
    
    /* Progress bars */
    .stProgress > div > div {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
    }
    
    /* Section Headers */
    h1, h2, h3 {
        color: #ffffff !important;
        font-family: 'Inter', sans-serif;
        font-weight: 700;
    }
    
    h2 {
        border-bottom: 2px solid rgba(102, 126, 234, 0.3);
        padding-bottom: 0.5rem;
        margin-top: 2rem;
    }
    
    /* Info boxes */
    .stAlert {
        background: rgba(102, 126, 234, 0.1);
        border: 1px solid rgba(102, 126, 234, 0.3);
        border-radius: 10px;
    }
    
    /* Tooltips and captions */
    .caption {
        color: #888;
        font-size: 0.85rem;
        font-style: italic;
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
    """Calculate AI-based stock score"""
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
    num_trades = len(df[df['Signal'] != 0])
    
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
               'JPM', 'BAC', 'V', 'MA', 'JNJ', 'PFE', 'XOM', 'CVX', 'WMT', 'HD',
               'COST', 'NKE', 'PYPL', 'INTC', 'QCOM', 'CSCO', 'ORCL', 'IBM', 'ADBE', 'CRM']
    
    results = []
    progress_bar = st.progress(0)
    status = st.empty()
    
    for idx, ticker in enumerate(tickers):
        try:
            status.text(f"🔍 Screening {ticker}... ({idx+1}/{len(tickers)})")
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
    status.empty()
    return pd.DataFrame(results).sort_values('AI_Score', ascending=False)

# Sidebar
with st.sidebar:
    st.markdown('<div class="main-header" style="font-size: 2rem;">WealthStockify</div>', unsafe_allow_html=True)
    
    if st.session_state.is_premium:
        st.markdown('<div class="premium-badge">⭐ PREMIUM ACTIVE</div>', unsafe_allow_html=True)
        st.success("🎉 All features unlocked!")
    else:
        st.markdown('<div class="free-badge">🆓 FREE TIER</div>', unsafe_allow_html=True)
        st.warning("⚡ Limited access")
        if st.button("🚀 Upgrade to Premium - $9.99/mo"):
            st.session_state.is_premium = True
            st.rerun()
    
    st.markdown("---")
    
    page = st.radio(
        "🧭 Navigation",
        ["📊 Stock Analysis", "🔍 Stock Screener", "📈 Backtesting", "👁️ Watchlist", "💰 Position Sizer"]
    )
    
    st.markdown("---")
    
    st.subheader("✨ Premium Features")
    features = [
        "Unlimited Stock Analysis",
        "AI Scoring System",
        "Advanced Indicators",
        "Stock Screener (30+ stocks)",
        "AI Price Predictions",
        "Position Calculator",
        "5-Year Backtesting",
        "Watchlist & Alerts",
        "Export to CSV"
    ]
    for idx, feature in enumerate(features, 1):
        icon = "✅" if st.session_state.is_premium else "🔒"
        st.markdown(f"{icon} {feature}")

# Main Content
if page == "📊 Stock Analysis":
    st.markdown('<div class="main-header">WealthStockify</div>', unsafe_allow_html=True)
    st.markdown('<div class="subtitle">Professional-Grade Stock Analysis Platform</div>', unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([3, 2, 1])
    
    with col1:
        ticker = st.text_input("🔍 Enter Stock Ticker", value="AAPL", placeholder="e.g., AAPL, TSLA, GOOGL").upper()
    
    with col2:
        period = st.selectbox("📅 Time Period", ["1mo", "3mo", "6mo", "1y", "2y", "5y"], index=2)
    
    with col3:
        st.write("")
        st.write("")
        analyze_btn = st.button("🚀 Analyze", type="primary")
    
    if ticker:
        try:
            with st.spinner("🔄 Fetching real-time data..."):
                stock = yf.Ticker(ticker)
                hist = stock.history(period=period)
                info = stock.info
            
            if hist.empty:
                st.error("❌ Invalid ticker or no data available.")
            else:
                hist = calculate_technical_indicators(hist)
                
                current_price = hist['Close'].iloc[-1]
                prev_close = hist['Close'].iloc[-2] if len(hist) > 1 else current_price
                change = current_price - prev_close
                change_pct = (change / prev_close) * 100
                
                # Key Metrics Row
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric(
                        "💵 Current Price",
                        f"${current_price:.2f}",
                        f"{change_pct:+.2f}%",
                        delta_color="normal"
                    )
                
                with col2:
                    if st.session_state.is_premium:
                        ai_score = calculate_ai_score(hist, info)
                        color = "🟢" if ai_score >= 70 else "🟡" if ai_score >= 50 else "🔴"
                        st.metric("🤖 AI Score", f"{ai_score:.0f}/100", color)
                    else:
                        st.metric("🤖 AI Score", "🔒 Premium", "Unlock")
                
                with col3:
                    volume = info.get('volume', 0)
                    st.metric("📊 Volume", f"{volume/1e6:.1f}M")
                
                with col4:
                    market_cap = info.get('marketCap', 0)
                    if market_cap > 0:
                        st.metric("💎 Market Cap", f"${market_cap/1e9:.2f}B")
                    else:
                        st.metric("💎 Market Cap", "N/A")
                
                st.markdown("---")
                
                # Enhanced Chart
                st.subheader("📈 Interactive Price Chart")
                
                fig = make_subplots(
                    rows=3, cols=1,
                    shared_xaxes=True,
                    vertical_spacing=0.03,
                    row_heights=[0.6, 0.2, 0.2],
                    subplot_titles=(f'{ticker} - Price Action', 'MACD Indicator', 'RSI Oscillator')
                )
                
                # Candlestick
                fig.add_trace(
                    go.Candlestick(
                        x=hist.index,
                        open=hist['Open'],
                        high=hist['High'],
                        low=hist['Low'],
                        close=hist['Close'],
                        name='OHLC',
                        increasing_line_color='#00ff88',
                        decreasing_line_color='#ff4444'
                    ),
                    row=1, col=1
                )
                
                if st.session_state.is_premium:
                    # Moving Averages
                    fig.add_trace(go.Scatter(
                        x=hist.index, y=hist['SMA_50'],
                        name='SMA 50',
                        line=dict(color='#FFA500', width=2)
                    ), row=1, col=1)
                    
                    fig.add_trace(go.Scatter(
                        x=hist.index, y=hist['SMA_200'],
                        name='SMA 200',
                        line=dict(color='#FF69B4', width=2)
                    ), row=1, col=1)
                    
                    fig.add_trace(go.Scatter(
                        x=hist.index, y=hist['BB_Upper'],
                        name='BB Upper',
                        line=dict(color='rgba(150,150,150,0.3)', dash='dash', width=1)
                    ), row=1, col=1)
                    
                    fig.add_trace(go.Scatter(
                        x=hist.index, y=hist['BB_Lower'],
                        name='BB Lower',
                        line=dict(color='rgba(150,150,150,0.3)', dash='dash', width=1),
                        fill='tonexty',
                        fillcolor='rgba(150,150,150,0.1)'
                    ), row=1, col=1)
                    
                    # MACD
                    fig.add_trace(go.Scatter(
                        x=hist.index, y=hist['MACD'],
                        name='MACD',
                        line=dict(color='#00D9FF', width=2)
                    ), row=2, col=1)
                    
                    fig.add_trace(go.Scatter(
                        x=hist.index, y=hist['Signal'],
                        name='Signal',
                        line=dict(color='#FF6B6B', width=2)
                    ), row=2, col=1)
                    
                    # RSI
                    fig.add_trace(go.Scatter(
                        x=hist.index, y=hist['RSI'],
                        name='RSI',
                        line=dict(color='#A78BFA', width=2),
                        fill='tozeroy',
                        fillcolor='rgba(167, 139, 250, 0.2)'
                    ), row=3, col=1)
                    
                    fig.add_hline(y=70, line_dash="dash", line_color="red", opacity=0.5, row=3, col=1)
                    fig.add_hline(y=30, line_dash="dash", line_color="green", opacity=0.5, row=3, col=1)
                
                fig.update_layout(
                    height=900,
                    showlegend=True,
                    xaxis_rangeslider_visible=False,
                    template='plotly_dark',
                    hovermode='x unified',
                    legend=dict(
                        orientation="h",
                        yanchor="bottom",
                        y=1.02,
                        xanchor="right",
                        x=1
                    )
                )
                
                fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='rgba(128,128,128,0.2)')
                fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='rgba(128,128,128,0.2)')
                
                st.plotly_chart(fig, use_container_width=True)
                
                st.markdown("---")
                
                # Two Column Layout
                if st.session_state.is_premium:
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.subheader("📊 Fundamental Analysis")
                        fund_data = {
                            "Metric": ["P/E Ratio", "EPS", "Dividend Yield", "Profit Margin", "ROE", "Debt/Equity"],
                            "Value": [
                                f"{info.get('trailingPE', 'N/A'):.2f}" if isinstance(info.get('trailingPE'), (int, float)) else "N/A",
                                f"${info.get('trailingEps', 'N/A'):.2f}" if isinstance(info.get('trailingEps'), (int, float)) else "N/A",
                                f"{info.get('dividendYield', 0)*100:.2f}%" if info.get('dividendYield') else "N/A",
                                f"{info.get('profitMargins', 0)*100:.2f}%" if info.get('profitMargins') else "N/A",
                                f"{info.get('returnOnEquity', 0)*100:.2f}%" if info.get('returnOnEquity') else "N/A",
                                f"{info.get('debtToEquity', 'N/A'):.2f}" if isinstance(info.get('debtToEquity'), (int, float)) else "N/A"
                            ]
                        }
                        st.dataframe(pd.DataFrame(fund_data), use_container_width=True, hide_index=True)
                    
                    with col2:
                        st.subheader("🤖 AI Price Predictions")
                        pred_30 = predict_price(hist, 30)
                        pred_90 = predict_price(hist, 90)
                        
                        if pred_30 and pred_90:
                            pred_change_30 = ((pred_30 - current_price) / current_price) * 100
                            pred_change_90 = ((pred_90 - current_price) / current_price) * 100
                            
                            st.metric("30-Day Forecast", f"${pred_30:.2f}", f"{pred_change_30:+.2f}%")
                            st.metric("90-Day Forecast", f"${pred_90:.2f}", f"{pred_change_90:+.2f}%")
                            st.
