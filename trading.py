import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time

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
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.5rem;
        border-radius: 10px;
        color: white;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .premium-badge {
        background: gold;
        color: black;
        padding: 0.3rem 0.8rem;
        border-radius: 20px;
        font-weight: bold;
        font-size: 0.8rem;
    }
    .free-badge {
        background: #gray;
        color: white;
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
if 'auto_refresh' not in st.session_state:
    st.session_state.auto_refresh = False

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
    df['EMA_20'] = df['Close'].ewm(span=20, adjust=False).mean()
    
    # ATR (Average True Range)
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
    
    # Technical Analysis (40 points)
    if len(df) > 0:
        current_price = df['Close'].iloc[-1]
        
        # RSI scoring
        if 'RSI' in df.columns:
            rsi = df['RSI'].iloc[-1]
            if 40 <= rsi <= 60:
                score += 10
            elif 30 <= rsi < 40 or 60 < rsi <= 70:
                score += 5
        
        # MACD scoring
        if 'MACD' in df.columns and 'Signal' in df.columns:
            if df['MACD'].iloc[-1] > df['Signal'].iloc[-1]:
                score += 10
        
        # Moving Average scoring
        if 'SMA_50' in df.columns and 'SMA_200' in df.columns:
            sma50 = df['SMA_50'].iloc[-1]
            sma200 = df['SMA_200'].iloc[-1]
            if pd.notna(sma50) and pd.notna(sma200):
                if current_price > sma50 > sma200:
                    score += 15
                elif current_price > sma50:
                    score += 8
        
        # Bollinger Bands
        if 'BB_Lower' in df.columns and 'BB_Upper' in df.columns:
            bb_position = (current_price - df['BB_Lower'].iloc[-1]) / (df['BB_Upper'].iloc[-1] - df['BB_Lower'].iloc[-1])
            if 0.3 <= bb_position <= 0.7:
                score += 5
    
    # Fundamental Analysis (60 points)
    try:
        # P/E Ratio
        if 'trailingPE' in info and info['trailingPE']:
            pe = info['trailingPE']
            if 10 <= pe <= 25:
                score += 15
            elif 5 <= pe < 10 or 25 < pe <= 35:
                score += 8
        
        # Profit Margin
        if 'profitMargins' in info and info['profitMargins']:
            if info['profitMargins'] > 0.15:
                score += 10
            elif info['profitMargins'] > 0.05:
                score += 5
        
        # Revenue Growth
        if 'revenueGrowth' in info and info['revenueGrowth']:
            if info['revenueGrowth'] > 0.15:
                score += 10
            elif info['revenueGrowth'] > 0.05:
                score += 5
        
        # Debt to Equity
        if 'debtToEquity' in info and info['debtToEquity']:
            if info['debtToEquity'] < 50:
                score += 10
            elif info['debtToEquity'] < 100:
                score += 5
        
        # ROE
        if 'returnOnEquity' in info and info['returnOnEquity']:
            if info['returnOnEquity'] > 0.15:
                score += 15
            elif info['returnOnEquity'] > 0.08:
                score += 8
    except:
        pass
    
    return min(max(score, 0), 100)

def predict_price(df, days=30):
    """Simple AI-based price prediction using linear regression with momentum"""
    if len(df) < 30:
        return None
    
    # Use last 90 days for prediction
    recent_df = df.tail(90).copy()
    recent_df['Days'] = range(len(recent_df))
    
    X = recent_df['Days'].values
    y = recent_df['Close'].values
    
    # Simple linear regression
    n = len(X)
    x_mean = X.mean()
    y_mean = y.mean()
    
    numerator = ((X - x_mean) * (y - y_mean)).sum()
    denominator = ((X - x_mean) ** 2).sum()
    
    slope = numerator / denominator
    intercept = y_mean - slope * x_mean
    
    # Add momentum factor
    momentum = (df['Close'].iloc[-1] - df['Close'].iloc[-30]) / df['Close'].iloc[-30]
    adjusted_slope = slope * (1 + momentum * 0.5)
    
    future_day = len(recent_df) + days
    predicted_price = adjusted_slope * future_day + intercept
    
    return max(predicted_price, 0)

def calculate_position_size(account_size, stock_price, method='kelly', risk_percent=2, volatility=None, win_rate=0.55, avg_win=1.5, avg_loss=1):
    """Calculate position size using different methods"""
    if method == 'fixed':
        risk_amount = account_size * (risk_percent / 100)
        shares = int(risk_amount / stock_price)
        
    elif method == 'kelly':
        # Kelly Criterion: f = (p*b - q) / b
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
    """Run a simple backtest with buy/sell signals"""
    stock = yf.Ticker(ticker)
    df = stock.history(start=start_date, end=end_date)
    
    if df.empty:
        return None
    
    df = calculate_technical_indicators(df)
    
    # Simple strategy: MACD crossover + RSI
    df['Signal'] = 0
    df['Position'] = 0
    
    for i in range(1, len(df)):
        if pd.notna(df['MACD'].iloc[i]) and pd.notna(df['Signal'].iloc[i]) and pd.notna(df['RSI'].iloc[i]):
            # Buy signal
            if (df['MACD'].iloc[i] > df['Signal'].iloc[i] and 
                df['MACD'].iloc[i-1] <= df['Signal'].iloc[i-1] and 
                df['RSI'].iloc[i] < 70):
                df.loc[df.index[i], 'Signal'] = 1
            # Sell signal
            elif (df['MACD'].iloc[i] < df['Signal'].iloc[i] and 
                  df['MACD'].iloc[i-1] >= df['Signal'].iloc[i-1]):
                df.loc[df.index[i], 'Signal'] = -1
    
    # Calculate positions and returns
    df['Position'] = df['Signal'].replace(0, np.nan).ffill().fillna(0)
    df['Returns'] = df['Close'].pct_change()
    df['Strategy_Returns'] = df['Position'].shift(1) * df['Returns']
    df['Cumulative_Returns'] = (1 + df['Returns']).cumprod()
    df['Cumulative_Strategy_Returns'] = (1 + df['Strategy_Returns']).cumprod()
    
    # Calculate metrics
    total_return = (df['Cumulative_Strategy_Returns'].iloc[-1] - 1) * 100
    buy_hold_return = (df['Cumulative_Returns'].iloc[-1] - 1) * 100
    
    trades = df[df['Signal'] != 0]
    num_trades = len(trades)
    
    # Sharpe Ratio (annualized)
    if df['Strategy_Returns'].std() != 0:
        sharpe_ratio = np.sqrt(252) * df['Strategy_Returns'].mean() / df['Strategy_Returns'].std()
    else:
        sharpe_ratio = 0
    
    # Max Drawdown
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
    """Screen popular stocks based on criteria"""
    tickers = [
        'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA', 'META', 'NVDA', 'AMD', 'NFLX', 'DIS',
        'JPM', 'BAC', 'WFC', 'GS', 'MS', 'V', 'MA', 'PYPL', 'SQ', 'COIN',
        'JNJ', 'PFE', 'UNH', 'ABBV', 'TMO', 'XOM', 'CVX', 'COP', 'SLB', 'MPC',
        'WMT', 'HD', 'COST', 'TGT', 'LOW', 'NKE', 'SBUX', 'MCD', 'CMG', 'YUM',
        'BA', 'CAT', 'DE', 'GE', 'HON', 'INTC', 'QCOM', 'AVGO', 'TXN', 'AMAT'
    ]
    
    results = []
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for idx, ticker in enumerate(tickers):
        try:
            status_text.text(f"Screening {ticker}... ({idx+1}/{len(tickers)})")
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
                    'RSI': hist['RSI'].iloc[-1] if 'RSI' in hist.columns else 0,
                    'Volume': info.get('volume', 0),
                    'Market_Cap': info.get('marketCap', 0)
                })
            
            progress_bar.progress((idx + 1) / len(tickers))
        except:
            continue
    
    progress_bar.empty()
    status_text.empty()
    
    return pd.DataFrame(results).sort_values('AI_Score', ascending=False)

# Sidebar
with st.sidebar:
    st.markdown('<div class="main-header">WealthStockify</div>', unsafe_allow_html=True)
    
    # Subscription Status
    if st.session_state.is_premium:
        st.markdown('<span class="premium-badge">⭐ PREMIUM</span>', unsafe_allow_html=True)
        st.success("All features unlocked!")
    else:
        st.markdown('<span class="free-badge">FREE TIER</span>', unsafe_allow_html=True)
        st.warning("Limited access - Upgrade to Premium!")
        if st.button("🚀 Run Backtest", type="primary"):
            with st.spinner("Running backtest..."):
                results = run_backtest(bt_ticker, start_date, end_date, initial_capital)
                
                if results:
                    st.success("Backtest completed!")
                    
                    # Performance Metrics
                    col1, col2, col3, col4 = st.columns(4)
                    
                    with col1:
                        st.metric("Strategy Return", f"{results['total_return']:.2f}%")
                    with col2:
                        st.metric("Buy & Hold Return", f"{results['buy_hold_return']:.2f}%")
                    with col3:
                        st.metric("Number of Trades", results['num_trades'])
                    with col4:
                        st.metric("Sharpe Ratio", f"{results['sharpe_ratio']:.2f}")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        st.metric("Max Drawdown", f"{results['max_drawdown']:.2f}%")
                    with col2:
                        alpha = results['total_return'] - results['buy_hold_return']
                        st.metric("Alpha (vs Buy & Hold)", f"{alpha:.2f}%")
                    
                    # Equity Curve
                    st.subheader("📈 Equity Curve")
                    
                    fig = go.Figure()
                    
                    fig.add_trace(go.Scatter(
                        x=results['df'].index,
                        y=results['df']['Cumulative_Strategy_Returns'] * initial_capital,
                        name='Strategy',
                        line=dict(color='blue', width=2)
                    ))
                    
                    fig.add_trace(go.Scatter(
                        x=results['df'].index,
                        y=results['df']['Cumulative_Returns'] * initial_capital,
                        name='Buy & Hold',
                        line=dict(color='gray', width=2, dash='dash')
                    ))
                    
                    fig.update_layout(
                        title=f"{bt_ticker} Backtest Results",
                        xaxis_title="Date",
                        yaxis_title="Portfolio Value ($)",
                        height=500,
                        hovermode='x unified'
                    )
                    
                    st.plotly_chart(fig, use_container_width=True)
                    
                    # Trade Signals
                    st.subheader("📊 Trade Signals")
                    
                    trades_df = results['df'][results['df']['Signal'] != 0][['Close', 'Signal', 'RSI', 'MACD']].copy()
                    trades_df['Action'] = trades_df['Signal'].apply(lambda x: '🟢 BUY' if x == 1 else '🔴 SELL')
                    trades_df = trades_df.rename(columns={'Close': 'Price'})
                    trades_df['Price'] = trades_df['Price'].apply(lambda x: f"${x:.2f}")
                    
                    st.dataframe(trades_df[['Action', 'Price', 'RSI', 'MACD']], use_container_width=True)
                    
                    # Export
                    if st.button("📥 Export Backtest Results"):
                        csv = results['df'].to_csv()
                        st.download_button(
                            label="Download CSV",
                            data=csv,
                            file_name=f"{bt_ticker}_backtest_{datetime.now().strftime('%Y%m%d')}.csv",
                            mime="text/csv"
                        )
                else:
                    st.error("Backtest failed. Please check the ticker and date range.")
    else:
        st.warning("🔒 Backtesting is a Premium Feature")
        st.info("Upgrade to Premium to backtest strategies over 5+ years!")

elif page == "👁️ Watchlist":
    st.title("👁️ Watchlist & Alerts")
    
    if st.session_state.is_premium:
        col1, col2 = st.columns([3, 1])
        
        with col1:
            new_ticker = st.text_input("Add Stock to Watchlist", placeholder="Enter ticker (e.g., AAPL)").upper()
        
        with col2:
            st.write("")
            st.write("")
            if st.button("➕ Add", type="primary"):
                if new_ticker and new_ticker not in st.session_state.watchlist:
                    st.session_state.watchlist.append(new_ticker)
                    st.success(f"Added {new_ticker} to watchlist!")
                    st.rerun()
        
        if st.session_state.watchlist:
            st.subheader("Your Watchlist")
            
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
                        
                        # Alert conditions
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
                            'Change': f"{change:.2f}%",
                            'AI Score': ai_score,
                            'RSI': f"{rsi:.1f}",
                            'Alert': alert
                        })
                except:
                    continue
            
            if watchlist_data:
                df = pd.DataFrame(watchlist_data)
                st.dataframe(df, use_container_width=True, hide_index=True)
                
                # Remove from watchlist
                st.subheader("Manage Watchlist")
                ticker_to_remove = st.selectbox("Remove ticker", st.session_state.watchlist)
                if st.button("🗑️ Remove"):
                    st.session_state.watchlist.remove(ticker_to_remove)
                    st.rerun()
                
                # Export watchlist
                if st.button("📥 Export Watchlist"):
                    csv = df.to_csv(index=False)
                    st.download_button(
                        label="Download CSV",
                        data=csv,
                        file_name=f"watchlist_{datetime.now().strftime('%Y%m%d')}.csv",
                        mime="text/csv"
                    )
            else:
                st.info("No valid data for watchlist items")
        else:
            st.info("Your watchlist is empty. Add some stocks to get started!")
    else:
        st.warning("🔒 Watchlist is a Premium Feature")
        st.info("Upgrade to Premium to create watchlists with real-time alerts!")

elif page == "💰 Position Sizer":
    st.title("💰 Position Size Calculator")
    
    if st.session_state.is_premium:
        st.write("Calculate optimal position sizes using multiple risk management methods")
        
        col1, col2 = st.columns(2)
        
        with col1:
            ps_ticker = st.text_input("Stock Ticker", value="AAPL").upper()
            account_size = st.number_input("Account Size ($)", value=100000, min_value=1000, step=1000)
            risk_percent = st.slider("Risk Per Trade (%)", min_value=0.5, max_value=5.0, value=2.0, step=0.5)
        
        with col2:
            st.write("")
            st.write("")
            method = st.selectbox(
                "Position Sizing Method",
                ["Fixed Risk", "Kelly Criterion", "Volatility-Based"]
            )
        
        # Additional parameters for Kelly
        if method == "Kelly Criterion":
            col1, col2 = st.columns(2)
            with col1:
                win_rate = st.slider("Win Rate (%)", 30, 80, 55) / 100
                avg_win = st.number_input("Avg Win Multiplier", value=1.5, min_value=1.0, max_value=5.0, step=0.1)
            with col2:
                avg_loss = st.number_input("Avg Loss Multiplier", value=1.0, min_value=0.5, max_value=2.0, step=0.1)
        
        if st.button("🧮 Calculate Position Size", type="primary"):
            try:
                stock = yf.Ticker(ps_ticker)
                hist = stock.history(period='3mo')
                
                if hist.empty:
                    st.error("Invalid ticker symbol")
                else:
                    current_price = hist['Close'].iloc[-1]
                    hist = calculate_technical_indicators(hist)
                    
                    # Calculate volatility
                    returns = hist['Close'].pct_change()
                    volatility = returns.std()
                    atr = hist['ATR'].iloc[-1] if 'ATR' in hist.columns else 0
                    
                    # Calculate position size
                    method_map = {
                        "Fixed Risk": "fixed",
                        "Kelly Criterion": "kelly",
                        "Volatility-Based": "volatility"
                    }
                    
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
                    
                    # Display results
                    st.success("Position Size Calculated!")
                    
                    col1, col2, col3, col4 = st.columns(4)
                    
                    with col1:
                        st.metric("Current Price", f"${current_price:.2f}")
                    with col2:
                        st.metric("Shares to Buy", f"{shares:,}")
                    with col3:
                        st.metric("Position Value", f"${position_value:,.2f}")
                    with col4:
                        st.metric("% of Account", f"{position_pct:.2f}%")
                    
                    # Risk Analysis
                    st.subheader("📊 Risk Analysis")
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        risk_amount = account_size * (risk_percent / 100)
                        st.metric("Risk Amount", f"${risk_amount:,.2f}")
                        st.metric("Daily Volatility", f"{volatility*100:.2f}%")
                    
                    with col2:
                        if atr > 0:
                            st.metric("ATR (14)", f"${atr:.2f}")
                            stop_loss = current_price - (2 * atr)
                            st.metric("Suggested Stop Loss (2x ATR)", f"${stop_loss:.2f}")
                    
                    # Position summary
                    st.subheader("📝 Position Summary")
                    
                    summary = f"""
                    **Trade Setup for {ps_ticker}**
                    
                    - **Entry Price:** ${current_price:.2f}
                    - **Shares:** {shares:,}
                    - **Total Investment:** ${position_value:,.2f}
                    - **Position Size:** {position_pct:.2f}% of account
                    - **Risk per Trade:** ${risk_amount:,.2f} ({risk_percent}%)
                    - **Method:** {method}
                    
                    **Risk Management:**
                    - Stop Loss: ${stop_loss:.2f} ({((stop_loss-current_price)/current_price*100):.2f}%)
                    - Risk per Share: ${current_price - stop_loss:.2f}
                    """
                    
                    st.markdown(summary)
                    
                    st.caption("⚠️ This is for educational purposes only. Always do your own research before trading.")
                    
            except Exception as e:
                st.error(f"Error: {str(e)}")
    else:
        st.warning("🔒 Position Size Calculator is a Premium Feature")
        st.info("Upgrade to Premium to access advanced position sizing tools!")

# Footer
st.markdown("---")
st.markdown(
    """
    <div style='text-align: center; color: gray;'>
        <p>WealthStockify © 2025 | Premium Stock Analysis Platform</p>
        <p style='font-size: 0.8rem;'>⚠️ Disclaimer: This platform is for educational purposes only. 
        Not financial advice. Always conduct your own research before investing.</p>
    </div>
    """,
    unsafe_allow_html=True
)

# Auto-refresh logic
if st.session_state.is_premium and st.session_state.auto_refresh and page == "📊 Stock Analysis":
    time.sleep(60)
    st.rerun()🚀 Upgrade to Premium - $9.99/mo"):
            st.session_state.is_premium = True
            st.rerun()
    
    st.markdown("---")
    
    # Navigation
    page = st.radio(
        "Navigation",
        ["📊 Stock Analysis", "🔍 Stock Screener", "📈 Backtesting", "👁️ Watchlist", "💰 Position Sizer"]
    )
    
    st.markdown("---")
    
    # Premium Features List
    st.subheader("Premium Features")
    features = [
        "✅ Unlimited Stock Analysis",
        "✅ AI Scoring System",
        "✅ Advanced Technical Indicators",
        "✅ Stock Screener (200+ stocks)",
        "✅ Auto-Refresh Live Data",
        "✅ AI Price Predictions",
        "✅ Position Size Calculator",
        "✅ Fundamental Analysis",
        "✅ 5-Year Backtesting",
        "✅ Watchlist with Alerts",
        "✅ Export to CSV"
    ]
    for feature in features:
        if st.session_state.is_premium:
            st.markdown(feature)
        else:
            st.markdown(f"{feature} 🔒")

# Main Content
if page == "📊 Stock Analysis":
    st.title("📊 Stock Analysis Dashboard")
    
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        ticker = st.text_input("Enter Stock Ticker", value="AAPL", key="ticker_input").upper()
    
    with col2:
        period = st.selectbox("Time Period", ["1mo", "3mo", "6mo", "1y", "2y", "5y"])
    
    with col3:
        if st.session_state.is_premium:
            auto_refresh = st.checkbox("Auto-Refresh", value=st.session_state.auto_refresh)
            st.session_state.auto_refresh = auto_refresh
        else:
            st.info("🔒 Premium Feature")
    
    if ticker:
        try:
            # Fetch data
            stock = yf.Ticker(ticker)
            hist = stock.history(period=period)
            info = stock.info
            
            if hist.empty:
                st.error("Invalid ticker or no data available.")
            else:
                # Calculate indicators
                hist = calculate_technical_indicators(hist)
                
                # Key Metrics
                current_price = hist['Close'].iloc[-1]
                prev_close = hist['Close'].iloc[-2] if len(hist) > 1 else current_price
                change = current_price - prev_close
                change_pct = (change / prev_close) * 100
                
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric("Current Price", f"${current_price:.2f}", f"{change:.2f} ({change_pct:.2f}%)")
                
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
                
                with col4:
                    market_cap = info.get('marketCap', 0)
                    if market_cap > 0:
                        st.metric("Market Cap", f"${market_cap/1e9:.2f}B")
                    else:
                        st.metric("Market Cap", "N/A")
                
                # Price Chart with Indicators
                st.subheader("📈 Price Chart & Technical Indicators")
                
                fig = make_subplots(
                    rows=3, cols=1,
                    shared_xaxes=True,
                    vertical_spacing=0.05,
                    row_heights=[0.6, 0.2, 0.2],
                    subplot_titles=(f'{ticker} Price & Moving Averages', 'MACD', 'RSI')
                )
                
                # Candlestick chart
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
                    # Moving averages
                    fig.add_trace(go.Scatter(x=hist.index, y=hist['SMA_50'], name='SMA 50', line=dict(color='orange', width=1)), row=1, col=1)
                    fig.add_trace(go.Scatter(x=hist.index, y=hist['SMA_200'], name='SMA 200', line=dict(color='red', width=1)), row=1, col=1)
                    fig.add_trace(go.Scatter(x=hist.index, y=hist['BB_Upper'], name='BB Upper', line=dict(color='gray', width=1, dash='dash')), row=1, col=1)
                    fig.add_trace(go.Scatter(x=hist.index, y=hist['BB_Lower'], name='BB Lower', line=dict(color='gray', width=1, dash='dash')), row=1, col=1)
                    
                    # MACD
                    fig.add_trace(go.Scatter(x=hist.index, y=hist['MACD'], name='MACD', line=dict(color='blue')), row=2, col=1)
                    fig.add_trace(go.Scatter(x=hist.index, y=hist['Signal'], name='Signal', line=dict(color='red')), row=2, col=1)
                    
                    # RSI
                    fig.add_trace(go.Scatter(x=hist.index, y=hist['RSI'], name='RSI', line=dict(color='purple')), row=3, col=1)
                    fig.add_hline(y=70, line_dash="dash", line_color="red", row=3, col=1)
                    fig.add_hline(y=30, line_dash="dash", line_color="green", row=3, col=1)
                
                fig.update_layout(height=800, showlegend=True, xaxis_rangeslider_visible=False)
                st.plotly_chart(fig, use_container_width=True)
                
                # Two Column Layout
                col1, col2 = st.columns(2)
                
                with col1:
                    # Fundamental Analysis
                    st.subheader("📊 Fundamental Analysis")
                    
                    if st.session_state.is_premium:
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
                    else:
                        st.info("🔒 Premium Feature - Upgrade to view fundamental analysis")
                
                with col2:
                    # AI Price Prediction
                    st.subheader("🤖 AI Price Prediction")
                    
                    if st.session_state.is_premium:
                        pred_30 = predict_price(hist, 30)
                        pred_90 = predict_price(hist, 90)
                        
                        if pred_30 and pred_90:
                            pred_change_30 = ((pred_30 - current_price) / current_price) * 100
                            pred_change_90 = ((pred_90 - current_price) / current_price) * 100
                            
                            st.metric("30-Day Prediction", f"${pred_30:.2f}", f"{pred_change_30:.2f}%")
                            st.metric("90-Day Prediction", f"${pred_90:.2f}", f"{pred_change_90:.2f}%")
                            
                            st.caption("⚠️ Predictions are AI-generated estimates for educational purposes only")
                        else:
                            st.warning("Insufficient data for predictions")
                    else:
                        st.info("🔒 Premium Feature - Upgrade to view AI predictions")
                
                # Technical Indicators Summary
                if st.session_state.is_premium:
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
                        st.metric("MACD", f"{macd:.2f}", macd_signal)
                    
                    with col3:
                        sma50 = hist['SMA_50'].iloc[-1]
                        sma_signal = "Above 🟢" if current_price > sma50 else "Below 🔴"
                        st.metric("SMA 50", f"${sma50:.2f}", sma_signal)
                    
                    with col4:
                        atr = hist['ATR'].iloc[-1]
                        volatility = (atr / current_price) * 100
                        st.metric("ATR", f"{atr:.2f}", f"Vol: {volatility:.2f}%")
                
                # Export functionality
                if st.session_state.is_premium:
                    if st.button("📥 Export Analysis to CSV"):
                        csv = hist.to_csv()
                        st.download_button(
                            label="Download CSV",
                            data=csv,
                            file_name=f"{ticker}_analysis_{datetime.now().strftime('%Y%m%d')}.csv",
                            mime="text/csv"
                        )
                
        except Exception as e:
            st.error(f"Error fetching data: {str(e)}")

elif page == "🔍 Stock Screener":
    st.title("🔍 Stock Screener")
    
    if st.session_state.is_premium:
        st.info("Screening 50 popular stocks based on AI scoring and technical indicators...")
        
        if st.button("🔎 Run Stock Screener", type="primary"):
            results_df = screen_stocks()
            
            if not results_df.empty:
                st.success(f"Found {len(results_df)} stocks")
                
                # Filters
                col1, col2 = st.columns(2)
                with col1:
                    min_score = st.slider("Minimum AI Score", 0, 100, 50)
                with col2:
                    min_rsi = st.slider("Minimum RSI", 0, 100, 0)
                
                filtered_df = results_df[
                    (results_df['AI_Score'] >= min_score) & 
                    (results_df['RSI'] >= min_rsi)
                ]
                
                st.dataframe(
                    filtered_df.style.background_gradient(subset=['AI_Score'], cmap='RdYlGn'),
                    use_container_width=True,
                    hide_index=True
                )
                
                # Export
                if st.button("📥 Export Screener Results"):
                    csv = filtered_df.to_csv(index=False)
                    st.download_button(
                        label="Download CSV",
                        data=csv,
                        file_name=f"stock_screener_{datetime.now().strftime('%Y%m%d')}.csv",
                        mime="text/csv"
                    )
    else:
        st.warning("🔒 Stock Screener is a Premium Feature")
        st.info("Upgrade to Premium to screen 200+ stocks with advanced filters!")

elif page == "📈 Backtesting":
    st.title("📈 Backtesting Engine")
    
    if st.session_state.is_premium:
        col1, col2, col3 = st.columns(3)
        
        with col1:
            bt_ticker = st.text_input("Ticker Symbol", value="AAPL").upper()
        
        with col2:
            start_date = st.date_input("Start Date", value=datetime.now() - timedelta(days=365*5))
        
        with col3:
            end_date = st.date_input("End Date", value=datetime.now())
        
        initial_capital = st.number_input("Initial Capital ($)", value=10000, min_value=1000, step=1000)
        
        if st.button("
