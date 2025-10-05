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
        background: #0e1117;
    }
    
    /* Main Header */
    .main-header {
        font-size: 2rem;
        font-weight: 900;
        color: #ffffff;
        margin-bottom: 0.5rem;
        font-family: 'Inter', sans-serif;
        letter-spacing: -1px;
        text-align: left;
        padding: 1rem 0;
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
        background: #10b981;
        color: white;
        padding: 0.4rem 1rem;
        border-radius: 8px;
        font-weight: 600;
        font-size: 0.85rem;
        display: inline-block;
        margin: 0.5rem 0;
    }
    
    .free-badge {
        background: #6b7280;
        color: white;
        padding: 0.4rem 1rem;
        border-radius: 8px;
        font-weight: 600;
        font-size: 0.85rem;
        display: inline-block;
        margin: 0.5rem 0;
    }
    
    /* Navigation Items */
    .nav-item {
        padding: 0.75rem;
        margin: 0.5rem 0;
        border-radius: 8px;
        transition: all 0.2s ease;
    }
    
    .nav-item:hover {
        background: rgba(255, 255, 255, 0.05);
    }
    
    .nav-title {
        font-size: 1rem;
        font-weight: 600;
        color: #ffffff;
        margin-bottom: 0.25rem;
    }
    
    .nav-desc {
        font-size: 0.8rem;
        color: #9ca3af;
        line-height: 1.3;
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
    
    /* Buttons */
    .stButton > button {
        background: #1f2937;
        color: white;
        border: 1px solid #374151;
        border-radius: 8px;
        padding: 0.75rem 2rem;
        font-weight: 600;
        font-size: 1rem;
        transition: all 0.3s ease;
        width: 100%;
    }
    
    .stButton > button:hover {
        background: #374151;
        border-color: #4b5563;
    }
    
    /* Sidebar Styling */
    section[data-testid="stSidebar"] {
        background: #1a1d24;
        border-right: 1px solid #374151;
    }
    
    /* Input Fields */
    .stTextInput > div > div > input {
        background: #1f2937;
        border: 1px solid #374151;
        border-radius: 8px;
        color: white;
        font-size: 1rem;
        padding: 0.75rem;
    }
    
    .stSelectbox > div > div {
        background: #1f2937;
        border: 1px solid #374151;
        border-radius: 8px;
    }
    
    /* DataFrames */
    .stDataFrame {
        background: rgba(255, 255, 255, 0.03);
        border-radius: 10px;
        border: 1px solid #374151;
    }
    
    /* Section Headers */
    h1, h2, h3 {
        color: #ffffff !important;
        font-family: 'Inter', sans-serif;
        font-weight: 700;
    }
    
    h2 {
        border-bottom: 2px solid #374151;
        padding-bottom: 0.5rem;
        margin-top: 2rem;
    }
    
    /* Info boxes */
    .stAlert {
        border-radius: 8px;
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
    st.markdown("# WealthStockify")
    
    if st.session_state.is_premium:
        st.success("⭐ PREMIUM")
    else:
        st.info("🆓 FREE TIER")
        if st.button("Upgrade to Premium - $9.99/mo", use_container_width=True):
            st.session_state.is_premium = True
            st.rerun()
    
    st.markdown("---")
    st.subheader("Navigation")
    
    page = st.radio(
        "Choose a section:",
        ["Stock Analysis", "Stock Screener", "Backtesting", "Watchlist", "Position Sizer"],
        label_visibility="collapsed"
    )
    
    # Add descriptions below radio
    descriptions = {
        "Stock Analysis": "📊 Real-time stock data with AI scoring and technical analysis",
        "Stock Screener": "🔍 Find top opportunities across 30+ popular stocks",
        "Backtesting": "📈 Test trading strategies with historical data",
        "Watchlist": "👁️ Track your favorite stocks with smart alerts",
        "Position Sizer": "💰 Calculate optimal position sizes for risk management"
    }
    
    if page in descriptions:
        st.caption(descriptions[page])
    
    st.markdown("---")
    
    with st.expander("✨ Premium Features"):
        features = [
            "✅ Unlimited Stock Analysis",
            "✅ AI Scoring System",
            "✅ Advanced Technical Indicators",
            "✅ Stock Screener (30+ stocks)",
            "✅ AI Price Predictions",
            "✅ Position Size Calculator",
            "✅ 5-Year Backtesting",
            "✅ Watchlist with Alerts",
            "✅ Export to CSV"
        ]
        for feature in features:
            if st.session_state.is_premium:
                st.markdown(feature)
            else:
                st.markdown(feature.replace("✅", "🔒"))

# Main Content
if page == "Stock Analysis":
    st.title("📊 Stock Analysis Dashboard")
    
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
                            st.caption("⚠️ AI predictions for educational purposes only")
                        else:
                            st.warning("Insufficient data for predictions")
                    
                    # Technical Indicators Summary
                    st.subheader("📉 Technical Indicators Summary")
                    
                    col1, col2, col3, col4 = st.columns(4)
                    
                    with col1:
                        rsi = hist['RSI'].iloc[-1]
                        rsi_signal = "Oversold 🟢" if rsi < 30 else "Overbought 🔴" if rsi > 70 else "Neutral 🟡"
                        st.metric("RSI (14)", f"{rsi:.2f}", rsi_signal)
                    
                    with col2:
                        macd = hist['MACD'].iloc[-1]
                        signal = hist['Signal'].iloc[-1]
                        macd_signal = "Bullish 🟢" if macd > signal else "Bearish 🔴"
                        st.metric("MACD Signal", macd_signal)
                    
                    with col3:
                        sma50 = hist['SMA_50'].iloc[-1]
                        sma_signal = "Above 🟢" if current_price > sma50 else "Below 🔴"
                        st.metric("vs SMA 50", sma_signal)
                    
                    with col4:
                        atr = hist['ATR'].iloc[-1]
                        volatility = (atr / current_price) * 100
                        st.metric("Volatility", f"{volatility:.2f}%")
                    
                    # Export
                    st.markdown("---")
                    if st.button("📥 Export Full Analysis to CSV"):
                        csv = hist.to_csv()
                        st.download_button(
                            label="⬇️ Download CSV File",
                            data=csv,
                            file_name=f"{ticker}_analysis_{datetime.now().strftime('%Y%m%d')}.csv",
                            mime="text/csv"
                        )
                else:
                    st.info("🔒 Upgrade to Premium to unlock fundamental analysis, AI predictions, and advanced indicators!")
                
        except Exception as e:
            st.error(f"❌ Error fetching data: {str(e)}")

elif page == "Stock Screener":
    st.title("🔍 Stock Screener")
    
    if st.session_state.is_premium:
        st.info("🔍 Screening 30 popular stocks with AI analysis...")
        
        if st.button("🚀 Run Advanced Screener", type="primary"):
            with st.spinner("Analyzing markets..."):
                results_df = screen_stocks()
            
            if not results_df.empty:
                st.success(f"✅ Found {len(results_df)} stocks")
                
                # Filters
                col1, col2 = st.columns(2)
                with col1:
                    min_score = st.slider("🎯 Minimum AI Score", 0, 100, 50)
                with col2:
                    sort_by = st.selectbox("📊 Sort By", ["AI_Score", "Change_6M"])
                
                filtered_df = results_df[results_df['AI_Score'] >= min_score].sort_values(sort_by, ascending=False)
                
                st.dataframe(
                    filtered_df.style.background_gradient(subset=['AI_Score'], cmap='RdYlGn', vmin=0, vmax=100),
                    use_container_width=True,
                    hide_index=True,
                    height=600
                )
                
                # Export
                st.markdown("---")
                if st.button("📥 Export Screener Results"):
                    csv = filtered_df.to_csv(index=False)
                    st.download_button(
                        label="⬇️ Download CSV",
                        data=csv,
                        file_name=f"stock_screener_{datetime.now().strftime('%Y%m%d')}.csv",
                        mime="text/csv"
                    )
    else:
        st.warning("🔒 Stock Screener is a Premium Feature")
        st.info("✨ Upgrade to Premium to screen 30+ stocks with advanced AI filters!")
        
        # Preview
        st.subheader("Preview")
        preview_data = {
            'Ticker': ['AAPL', 'MSFT', 'GOOGL'],
            'Price': ['$258.02', '$423.15', '$142.58'],
            'AI_Score': ['🔒 Premium', '🔒 Premium', '🔒 Premium']
        }
        st.dataframe(pd.DataFrame(preview_data), hide_index=True)

elif page == "Backtesting":
    st.title("📈 Backtesting Engine")
    
    if st.session_state.is_premium:
        col1, col2, col3 = st.columns(3)
        
        with col1:
            bt_ticker = st.text_input("📊 Ticker Symbol", value="AAPL").upper()
        
        with col2:
            start_date = st.date_input("📅 Start Date", value=datetime.now() - timedelta(days=365*2))
        
        with col3:
            end_date = st.date_input("📅 End Date", value=datetime.now())
        
        initial_capital = st.number_input("💰 Initial Capital ($)", value=10000, min_value=1000, step=1000)
        
        if st.button("🚀 Run Backtest", type="primary"):
            with st.spinner("⏳ Running backtest simulation..."):
                results = run_backtest(bt_ticker, start_date, end_date, initial_capital)
            
            if results:
                st.success("✅ Backtest completed successfully!")
                
                # Performance Metrics
                st.subheader("📊 Performance Metrics")
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric("💹 Strategy Return", f"{results['total_return']:.2f}%")
                with col2:
                    st.metric("📈 Buy & Hold", f"{results['buy_hold_return']:.2f}%")
                with col3:
                    st.metric("🔄 Total Trades", results['num_trades'])
                with col4:
                    st.metric("⚡ Sharpe Ratio", f"{results['sharpe_ratio']:.2f}")
                
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("📉 Max Drawdown", f"{results['max_drawdown']:.2f}%")
                with col2:
                    alpha = results['total_return'] - results['buy_hold_return']
                    st.metric("🎯 Alpha", f"{alpha:.2f}%")
                
                # Equity Curve
                st.subheader("📈 Equity Curve")
                
                fig = go.Figure()
                
                fig.add_trace(go.Scatter(
                    x=results['df'].index,
                    y=results['df']['Cumulative_Strategy_Returns'] * initial_capital,
                    name='Strategy',
                    line=dict(color='#00D9FF', width=3),
                    fill='tozeroy',
                    fillcolor='rgba(0, 217, 255, 0.1)'
                ))
                
                fig.add_trace(go.Scatter(
                    x=results['df'].index,
                    y=results['df']['Cumulative_Returns'] * initial_capital,
                    name='Buy & Hold',
                    line=dict(color='#FF6B6B', width=2, dash='dash')
                ))
                
                fig.update_layout(
                    title=f"{bt_ticker} - Strategy Performance",
                    xaxis_title="Date",
                    yaxis_title="Portfolio Value ($)",
                    height=500,
                    template='plotly_dark',
                    hovermode='x unified',
                    showlegend=True
                )
                
                fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='rgba(128,128,128,0.2)')
                fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='rgba(128,128,128,0.2)')
                
                st.plotly_chart(fig, use_container_width=True)
                
                # Trade Signals
                st.subheader("📊 Trade History")
                
                trades_df = results['df'][results['df']['Signal'] != 0][['Close', 'Signal', 'RSI', 'MACD']].copy()
                if not trades_df.empty:
                    trades_df['Action'] = trades_df['Signal'].apply(lambda x: '🟢 BUY' if x == 1 else '🔴 SELL')
                    trades_df['Price'] = trades_df['Close'].apply(lambda x: f"${x:.2f}")
                    trades_df = trades_df[['Action', 'Price', 'RSI', 'MACD']]
                    
                    st.dataframe(trades_df, use_container_width=True, height=400)
                
                # Export
                st.markdown("---")
                if st.button("📥 Export Backtest Results"):
                    csv = results['df'].to_csv()
                    st.download_button(
                        label="⬇️ Download Full Results",
                        data=csv,
                        file_name=f"{bt_ticker}_backtest_{datetime.now().strftime('%Y%m%d')}.csv",
                        mime="text/csv"
                    )
            else:
                st.error("❌ Backtest failed. Please check the ticker and date range.")
    else:
        st.warning("🔒 Backtesting is a Premium Feature")
        st.info("✨ Upgrade to Premium to backtest strategies over 5+ years of data!")

elif page == "Watchlist":
    st.title("👁️ Watchlist & Alerts")
    
    if st.session_state.is_premium:
        col1, col2 = st.columns([3, 1])
        
        with col1:
            new_ticker = st.text_input("➕ Add Stock to Watchlist", placeholder="e.g., AAPL, TSLA").upper()
        
        with col2:
            st.write("")
            st.write("")
            if st.button("Add to List", type="primary"):
                if new_ticker and new_ticker not in st.session_state.watchlist:
                    st.session_state.watchlist.append(new_ticker)
                    st.success(f"✅ Added {new_ticker}")
                    st.rerun()
                elif new_ticker in st.session_state.watchlist:
                    st.warning("Already in watchlist!")
        
        if st.session_state.watchlist:
            st.subheader("📋 Your Stocks")
            
            watchlist_data = []
            
            for ticker in st.session_state.watchlist:
                try:
                    stock = yf.Ticker(ticker)
                    hist = stock.history(period='1mo')
                    info = stock.info
                    
                    if not hist.empty:
                        hist = calculate_technical_indicators(hist)
                        current_price = hist['Close'].iloc[-1]
                        prev_close = hist['Close'].iloc[-2] if len(hist) > 1 else current_price
                        change = ((current_price - prev_close) / prev_close) * 100
                        
                        ai_score = calculate_ai_score(hist, info)
                        rsi = hist['RSI'].iloc[-1] if 'RSI' in hist.columns else 0
                        
                        alert = ""
                        if rsi < 30:
                            alert = "🟢 Oversold"
                        elif rsi > 70:
                            alert = "🔴 Overbought"
                        elif ai_score >= 75:
                            alert = "⭐ High Score"
                        
                        watchlist_data.append({
                            'Ticker': ticker,
                            'Price': f"${current_price:.2f}",
                            'Change': f"{change:+.2f}%",
                            'AI Score': f"{ai_score:.0f}",
                            'RSI': f"{rsi:.1f}",
                            'Alert': alert
                        })
                except:
                    continue
            
            if watchlist_data:
                df = pd.DataFrame(watchlist_data)
                st.dataframe(
                    df.style.background_gradient(subset=['AI Score'], cmap='RdYlGn', vmin=0, vmax=100),
                    use_container_width=True,
                    hide_index=True,
                    height=400
                )
                
                # Remove
                st.subheader("🗑️ Manage")
                ticker_to_remove = st.selectbox("Remove ticker:", st.session_state.watchlist)
                if st.button("Remove Selected"):
                    st.session_state.watchlist.remove(ticker_to_remove)
                    st.success(f"Removed {ticker_to_remove}")
                    st.rerun()
                
                # Export
                st.markdown("---")
                if st.button("📥 Export Watchlist"):
                    csv = df.to_csv(index=False)
                    st.download_button(
                        label="⬇️ Download CSV",
                        data=csv,
                        file_name=f"watchlist_{datetime.now().strftime('%Y%m%d')}.csv",
                        mime="text/csv"
                    )
            else:
                st.info("No valid data for watchlist items")
        else:
            st.info("📝 Your watchlist is empty. Add some stocks to get started!")
    else:
        st.warning("🔒 Watchlist is a Premium Feature")
        st.info("✨ Upgrade to Premium to track unlimited stocks with real-time alerts!")

elif page == "Position Sizer":
    st.title("💰 Position Size Calculator")
    
    if st.session_state.is_premium:
        col1, col2 = st.columns(2)
        
        with col1:
            ps_ticker = st.text_input("📊 Stock Ticker", value="AAPL").upper()
            account_size = st.number_input("💰 Account Size ($)", value=100000, min_value=1000, step=1000)
            risk_percent = st.slider("⚠️ Risk Per Trade (%)", 0.5, 5.0, 2.0, 0.5)
        
        with col2:
            method = st.selectbox(
                "🎯 Calculation Method",
                ["Fixed Risk", "Kelly Criterion", "Volatility-Based"]
            )
        
        # Kelly parameters
        if method == "Kelly Criterion":
            col1, col2 = st.columns(2)
            with col1:
                win_rate = st.slider("📊 Win Rate (%)", 30, 80, 55) / 100
                avg_win = st.number_input("📈 Avg Win Multiple", value=1.5, min_value=1.0, step=0.1)
            with col2:
                avg_loss = st.number_input("📉 Avg Loss Multiple", value=1.0, min_value=0.5, step=0.1)
        
        if st.button("🧮 Calculate Position Size", type="primary"):
            try:
                with st.spinner("Calculating..."):
                    stock = yf.Ticker(ps_ticker)
                    hist = stock.history(period='3mo')
                
                if hist.empty:
                    st.error("❌ Invalid ticker symbol")
                else:
                    current_price = hist['Close'].iloc[-1]
                    hist = calculate_technical_indicators(hist)
                    
                    returns = hist['Close'].pct_change()
                    volatility = returns.std()
                    atr = hist['ATR'].iloc[-1] if 'ATR' in hist.columns else 0
                    
                    # Calculate
                    if method == "Kelly Criterion":
                        shares = calculate_position_size(
                            account_size, current_price, 'kelly', risk_percent,
                            volatility, win_rate, avg_win, avg_loss
                        )
                    elif method == "Volatility-Based":
                        shares = calculate_position_size(
                            account_size, current_price, 'volatility', risk_percent, volatility
                        )
                    else:
                        shares = calculate_position_size(
                            account_size, current_price, 'fixed', risk_percent
                        )
                    
                    position_value = shares * current_price
                    position_pct = (position_value / account_size) * 100
                    
                    st.success("✅ Position calculated!")
                    
                    # Results
                    st.subheader("📊 Position Details")
                    col1, col2, col3, col4 = st.columns(4)
                    
                    with col1:
                        st.metric("💵 Price", f"${current_price:.2f}")
                    with col2:
                        st.metric("📦 Shares", f"{shares:,}")
                    with col3:
                        st.metric("💰 Position Value", f"${position_value:,.2f}")
                    with col4:
                        st.metric("📊 % of Account", f"{position_pct:.2f}%")
                    
                    # Risk Analysis
                    st.subheader("⚠️ Risk Analysis")
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        risk_amount = account_size * (risk_percent / 100)
                        st.metric("💸 Risk Amount", f"${risk_amount:,.2f}")
                        st.metric("📊 Daily Volatility", f"{volatility*100:.2f}%")
                    
                    with col2:
                        if atr > 0:
                            st.metric("📉 ATR (14)", f"${atr:.2f}")
                            stop_loss = current_price - (2 * atr)
                            st.metric("🛑 Stop Loss (2x ATR)", f"${stop_loss:.2f}")
                    
                    # Summary
                    st.subheader("📝 Trade Summary")
                    
                    summary = f"""
                    **Position Setup for {ps_ticker}**
                    
                    - Entry Price: ${current_price:.2f}
                    - Shares to Buy: {shares:,}
                    - Total Investment: ${position_value:,.2f}
                    - Position Size: {position_pct:.2f}% of account
                    - Risk per Trade: ${risk_amount:,.2f} ({risk_percent}%)
                    - Method: {method}
                    
                    **Risk Management**
                    - Suggested Stop Loss: ${stop_loss:.2f} ({((stop_loss-current_price)/current_price*100):.2f}%)
                    - Risk per Share: ${abs(current_price - stop_loss):.2f}
                    """
                    
                    st.markdown(summary)
                    st.caption("⚠️ For educational purposes only. Not financial advice.")
                    
            except Exception as e:
                st.error(f"❌ Error: {str(e)}")
    else:
        st.warning("🔒 Position Calculator is a Premium Feature")
        st.info("✨ Upgrade to Premium for Kelly Criterion, volatility-based sizing, and more!")

# Footer
st.markdown("---")
st.markdown(
    """
    <div style='text-align: center; color: #666; padding: 2rem;'>
        <p style='font-size: 1.1rem; font-weight: 600;'>WealthStockify © 2025</p>
        <p style='font-size: 0.9rem; margin-top: 0.5rem;'>Professional Stock Analysis Platform</p>
        <p style='font-size: 0.85rem; color: #888; margin-top: 1rem;'>
            ⚠️ <strong>Disclaimer:</strong> This platform is for educational purposes only.<br>
            Not financial advice. Always conduct your own research before investing.
        </p>
    </div>
    """,
    unsafe_allow_html=True
)
