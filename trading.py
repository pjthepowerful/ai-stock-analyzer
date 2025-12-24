import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

# Page configuration
st.set_page_config(
    page_title="StockMaster Pro - AI Stock Analysis",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for beautiful UI
st.markdown("""
<style>
    .stApp {
        background: linear-gradient(135deg, #0a0e27 0%, #1a1f3a 100%);
    }
    h1, h2, h3 {
        color: #ffffff !important;
        font-family: 'Segoe UI', sans-serif;
        font-weight: 600;
    }
    .stButton > button {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        border-radius: 10px;
        padding: 0.6rem 1.5rem;
        font-weight: 600;
        transition: all 0.3s;
        box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);
    }
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(102, 126, 234, 0.6);
    }
    .metric-card {
        background: rgba(255, 255, 255, 0.05);
        padding: 1.5rem;
        border-radius: 12px;
        border: 1px solid rgba(255, 255, 255, 0.1);
        backdrop-filter: blur(10px);
    }
    .score-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 2rem;
        border-radius: 15px;
        color: white;
        text-align: center;
        box-shadow: 0 8px 32px rgba(102, 126, 234, 0.3);
    }
    .stMetric {
        background: rgba(255, 255, 255, 0.05);
        padding: 1rem;
        border-radius: 10px;
        border: 1px solid rgba(255, 255, 255, 0.1);
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        background: rgba(255, 255, 255, 0.05);
        border-radius: 8px;
        padding: 0.5rem 1rem;
    }
    .recommendation-box {
        padding: 1.5rem;
        border-radius: 12px;
        margin: 1rem 0;
        border-left: 4px solid;
    }
    .buy-signal {
        background: rgba(34, 197, 94, 0.1);
        border-color: #22c55e;
    }
    .sell-signal {
        background: rgba(239, 68, 68, 0.1);
        border-color: #ef4444;
    }
    .hold-signal {
        background: rgba(234, 179, 8, 0.1);
        border-color: #eab308;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'watchlist' not in st.session_state:
    st.session_state.watchlist = ['AAPL', 'MSFT', 'GOOGL']
if 'page' not in st.session_state:
    st.session_state.page = "Stock Analysis"
if 'last_request_time' not in st.session_state:
    st.session_state.last_request_time = 0

# Helper Functions
@st.cache_data(ttl=600)  # Cache for 10 minutes
def get_stock_data(ticker, period='6mo'):
    """Fetch stock data with caching and retry logic"""
    import time
    max_retries = 3
    retry_delay = 2
    
    for attempt in range(max_retries):
        try:
            # Add small delay between requests to avoid rate limiting
            if attempt > 0:
                time.sleep(retry_delay * attempt)
            
            stock = yf.Ticker(ticker)
            
            # Fetch data with timeout
            hist = stock.history(period=period)
            
            # Only fetch info if we successfully got history
            if not hist.empty:
                try:
                    info = stock.info
                except:
                    # If info fails, use basic data from history
                    info = {
                        'symbol': ticker,
                        'volume': int(hist['Volume'].iloc[-1]) if len(hist) > 0 else 0,
                        'marketCap': 0
                    }
                return hist, info
            
        except Exception as e:
            error_msg = str(e).lower()
            if 'rate limit' in error_msg or '429' in error_msg or 'too many requests' in error_msg:
                if attempt < max_retries - 1:
                    st.warning(f"⏳ Rate limited. Waiting {retry_delay * (attempt + 1)} seconds before retry {attempt + 2}/{max_retries}...")
                    time.sleep(retry_delay * (attempt + 1))
                    continue
                else:
                    st.error(f"❌ Rate limit exceeded. Please wait a few minutes and try again.")
                    return pd.DataFrame(), {}
            else:
                if attempt < max_retries - 1:
                    continue
                else:
                    st.error(f"❌ Error fetching data: {str(e)}")
                    return pd.DataFrame(), {}
    
    return pd.DataFrame(), {}

def calculate_technical_indicators(df):
    """Calculate comprehensive technical indicators"""
    if df.empty or len(df) < 2:
        return df
    
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
    df['Signal_Line'] = df['MACD'].ewm(span=9, adjust=False).mean()
    df['MACD_Histogram'] = df['MACD'] - df['Signal_Line']
    
    # Bollinger Bands
    df['BB_Middle'] = df['Close'].rolling(window=20).mean()
    bb_std = df['Close'].rolling(window=20).std()
    df['BB_Upper'] = df['BB_Middle'] + (bb_std * 2)
    df['BB_Lower'] = df['BB_Middle'] - (bb_std * 2)
    df['BB_Width'] = (df['BB_Upper'] - df['BB_Lower']) / df['BB_Middle']
    
    # Moving Averages
    df['SMA_20'] = df['Close'].rolling(window=20).mean()
    df['SMA_50'] = df['Close'].rolling(window=50).mean()
    df['SMA_200'] = df['Close'].rolling(window=200).mean()
    df['EMA_12'] = df['Close'].ewm(span=12, adjust=False).mean()
    df['EMA_26'] = df['Close'].ewm(span=26, adjust=False).mean()
    
    # ATR (Average True Range)
    high_low = df['High'] - df['Low']
    high_close = np.abs(df['High'] - df['Close'].shift())
    low_close = np.abs(df['Low'] - df['Close'].shift())
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = np.max(ranges, axis=1)
    df['ATR'] = true_range.rolling(14).mean()
    
    # Stochastic Oscillator
    low_14 = df['Low'].rolling(window=14).min()
    high_14 = df['High'].rolling(window=14).max()
    df['Stochastic_K'] = 100 * ((df['Close'] - low_14) / (high_14 - low_14))
    df['Stochastic_D'] = df['Stochastic_K'].rolling(window=3).mean()
    
    # Volume indicators
    df['Volume_SMA'] = df['Volume'].rolling(window=20).mean()
    df['Volume_Ratio'] = df['Volume'] / df['Volume_SMA']
    
    # Price momentum
    df['ROC'] = ((df['Close'] - df['Close'].shift(10)) / df['Close'].shift(10)) * 100
    df['Momentum'] = df['Close'] - df['Close'].shift(10)
    
    return df

def calculate_advanced_score(df, info):
    """Advanced AI scoring system (0-100)"""
    if df.empty or len(df) < 50:
        return 50, {"error": "Insufficient data"}
    
    score = 0
    breakdown = {}
    current_price = df['Close'].iloc[-1]
    
    # 1. Trend Analysis (25 points)
    trend_score = 0
    sma50 = df['SMA_50'].iloc[-1] if pd.notna(df['SMA_50'].iloc[-1]) else None
    sma200 = df['SMA_200'].iloc[-1] if pd.notna(df['SMA_200'].iloc[-1]) else None
    
    if sma50 and sma200:
        if current_price > sma50 > sma200:
            trend_score = 25  # Strong uptrend
        elif current_price > sma50:
            trend_score = 18  # Moderate uptrend
        elif current_price > sma200:
            trend_score = 12  # Weak uptrend
        elif sma50 > current_price > sma200:
            trend_score = 8  # Consolidation
        else:
            trend_score = 3  # Downtrend
    breakdown['Trend Analysis'] = trend_score
    score += trend_score
    
    # 2. Momentum Indicators (20 points)
    momentum_score = 0
    rsi = df['RSI'].iloc[-1] if pd.notna(df['RSI'].iloc[-1]) else 50
    
    if 45 <= rsi <= 55:
        momentum_score += 10  # Neutral, balanced
    elif 40 <= rsi < 45 or 55 < rsi <= 60:
        momentum_score += 8  # Slight bias
    elif 35 <= rsi < 40 or 60 < rsi <= 65:
        momentum_score += 6  # Moderate bias
    elif 30 <= rsi < 35:
        momentum_score += 9  # Oversold - potential reversal
    elif 65 < rsi <= 70:
        momentum_score += 7  # Overbought but strong
    else:
        momentum_score += 3  # Extreme levels
    
    # MACD contribution
    if pd.notna(df['MACD'].iloc[-1]) and pd.notna(df['Signal_Line'].iloc[-1]):
        macd_hist = df['MACD_Histogram'].iloc[-1]
        if macd_hist > 0 and df['MACD'].iloc[-1] > df['Signal_Line'].iloc[-1]:
            momentum_score += 10  # Bullish momentum
        elif macd_hist > 0:
            momentum_score += 6
        elif macd_hist < 0:
            momentum_score += 2
    
    breakdown['Momentum'] = momentum_score
    score += momentum_score
    
    # 3. Volatility & Risk (15 points)
    volatility_score = 0
    bb_width = df['BB_Width'].iloc[-1] if pd.notna(df['BB_Width'].iloc[-1]) else 0.1
    
    if 0.02 <= bb_width <= 0.08:
        volatility_score = 15  # Healthy volatility
    elif 0.01 <= bb_width < 0.02 or 0.08 < bb_width <= 0.12:
        volatility_score = 11  # Acceptable
    else:
        volatility_score = 6  # Too tight or too wide
    
    breakdown['Volatility'] = volatility_score
    score += volatility_score
    
    # 4. Volume Analysis (10 points)
    volume_score = 0
    volume_ratio = df['Volume_Ratio'].iloc[-1] if pd.notna(df['Volume_Ratio'].iloc[-1]) else 1
    
    if 1.2 <= volume_ratio <= 2.0:
        volume_score = 10  # Strong volume
    elif 0.8 <= volume_ratio < 1.2:
        volume_score = 7  # Average volume
    elif volume_ratio > 2.0:
        volume_score = 6  # Spike (could be news)
    else:
        volume_score = 3  # Low volume
    
    breakdown['Volume'] = volume_score
    score += volume_score
    
    # 5. Fundamental Analysis (20 points)
    fundamental_score = 0
    
    try:
        # P/E Ratio
        pe = info.get('trailingPE') or info.get('forwardPE')
        if pe and 5 <= pe <= 30:
            fundamental_score += 8
        elif pe and 30 < pe <= 50:
            fundamental_score += 5
        elif pe:
            fundamental_score += 2
        
        # Profit Margin
        profit_margin = info.get('profitMargins')
        if profit_margin and profit_margin > 0.20:
            fundamental_score += 6
        elif profit_margin and profit_margin > 0.10:
            fundamental_score += 4
        elif profit_margin and profit_margin > 0:
            fundamental_score += 2
        
        # ROE
        roe = info.get('returnOnEquity')
        if roe and roe > 0.20:
            fundamental_score += 6
        elif roe and roe > 0.10:
            fundamental_score += 4
        elif roe and roe > 0:
            fundamental_score += 2
        
        # If we got no fundamental data, give neutral score
        if fundamental_score == 0:
            fundamental_score = 10
            
    except:
        fundamental_score = 10  # Neutral if data unavailable
    
    breakdown['Fundamentals'] = fundamental_score
    score += fundamental_score
    
    # 6. Recent Performance (10 points)
    performance_score = 0
    recent_return = ((current_price - df['Close'].iloc[-20]) / df['Close'].iloc[-20]) * 100
    
    if 2 <= recent_return <= 8:
        performance_score = 10  # Steady growth
    elif 0 <= recent_return < 2:
        performance_score = 7  # Slight growth
    elif 8 < recent_return <= 15:
        performance_score = 8  # Strong growth
    elif recent_return > 15:
        performance_score = 5  # Parabolic (risky)
    elif -5 <= recent_return < 0:
        performance_score = 6  # Slight decline
    else:
        performance_score = 3  # Significant decline
    
    breakdown['Recent Performance'] = performance_score
    score += performance_score
    
    return min(max(score, 0), 100), breakdown

def get_recommendation(score, df):
    """Get trading recommendation based on score"""
    current_price = df['Close'].iloc[-1]
    rsi = df['RSI'].iloc[-1] if pd.notna(df['RSI'].iloc[-1]) else 50
    
    if score >= 75:
        signal = "STRONG BUY"
        color = "buy-signal"
        emoji = "🚀"
    elif score >= 60:
        signal = "BUY"
        color = "buy-signal"
        emoji = "📈"
    elif score >= 45:
        signal = "HOLD"
        color = "hold-signal"
        emoji = "⏸️"
    elif score >= 30:
        signal = "SELL"
        color = "sell-signal"
        emoji = "📉"
    else:
        signal = "STRONG SELL"
        color = "sell-signal"
        emoji = "⚠️"
    
    return signal, color, emoji

def predict_price_ml(df, days=30):
    """Advanced price prediction using multiple methods"""
    if len(df) < 90:
        return None, None, None
    
    recent = df.tail(90).copy()
    
    # Linear regression with momentum
    recent['Days'] = range(len(recent))
    X = recent['Days'].values
    y = recent['Close'].values
    
    x_mean, y_mean = X.mean(), y.mean()
    numerator = ((X - x_mean) * (y - y_mean)).sum()
    denominator = ((X - x_mean) ** 2).sum()
    
    if denominator == 0:
        return None, None, None
    
    slope = numerator / denominator
    intercept = y_mean - slope * x_mean
    
    # Calculate momentum factor
    momentum = (df['Close'].iloc[-1] - df['Close'].iloc[-30]) / df['Close'].iloc[-30]
    volatility = df['Close'].pct_change().std()
    
    # Adjusted prediction
    future_day = len(recent) + days
    base_pred = slope * future_day + intercept
    
    # Apply momentum and volatility adjustments
    adjusted_slope = slope * (1 + momentum * 0.3)
    prediction = max(adjusted_slope * future_day + intercept, 0)
    
    # Calculate confidence based on R-squared
    y_pred = slope * X + intercept
    ss_res = ((y - y_pred) ** 2).sum()
    ss_tot = ((y - y_mean) ** 2).sum()
    r_squared = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0
    confidence = max(min(r_squared * 100, 95), 30)
    
    # Conservative and optimistic scenarios
    conservative = prediction * 0.92
    optimistic = prediction * 1.08
    
    return prediction, confidence, (conservative, optimistic)

def calculate_support_resistance(df):
    """Calculate support and resistance levels"""
    if len(df) < 50:
        return [], []
    
    # Find local maxima and minima
    window = 10
    highs = df['High'].rolling(window=window, center=True).max()
    lows = df['Low'].rolling(window=window, center=True).min()
    
    resistance_levels = []
    support_levels = []
    
    for i in range(window, len(df) - window):
        if df['High'].iloc[i] == highs.iloc[i]:
            resistance_levels.append(df['High'].iloc[i])
        if df['Low'].iloc[i] == lows.iloc[i]:
            support_levels.append(df['Low'].iloc[i])
    
    # Cluster nearby levels
    resistance = sorted(set([r for r in resistance_levels if r > df['Close'].iloc[-1]]))[-3:] if resistance_levels else []
    support = sorted(set([s for s in support_levels if s < df['Close'].iloc[-1]]), reverse=True)[:3] if support_levels else []
    
    return support, resistance

def run_backtest_strategy(ticker, start_date, end_date, initial_capital=10000):
    """Run backtesting with enhanced strategy"""
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(start=start_date, end=end_date)
        
        if df.empty or len(df) < 50:
            return None
        
        df = calculate_technical_indicators(df)
        
        # Trading signals based on multiple indicators
        df['Signal'] = 0
        position = 0
        
        for i in range(50, len(df)):
            if pd.notna(df['RSI'].iloc[i]) and pd.notna(df['MACD'].iloc[i]):
                # Buy signals
                if (df['MACD'].iloc[i] > df['Signal_Line'].iloc[i] and 
                    df['MACD'].iloc[i-1] <= df['Signal_Line'].iloc[i-1] and 
                    df['RSI'].iloc[i] < 65 and
                    df['Close'].iloc[i] > df['SMA_50'].iloc[i] and
                    position == 0):
                    df.loc[df.index[i], 'Signal'] = 1
                    position = 1
                
                # Sell signals
                elif ((df['MACD'].iloc[i] < df['Signal_Line'].iloc[i] and 
                       df['MACD'].iloc[i-1] >= df['Signal_Line'].iloc[i-1]) or
                      df['RSI'].iloc[i] > 75) and position == 1:
                    df.loc[df.index[i], 'Signal'] = -1
                    position = 0
        
        # Calculate returns
        df['Position'] = df['Signal'].replace(0, np.nan).ffill().fillna(0)
        df['Returns'] = df['Close'].pct_change()
        df['Strategy_Returns'] = df['Position'].shift(1) * df['Returns']
        
        df['Cumulative_Market'] = (1 + df['Returns']).cumprod()
        df['Cumulative_Strategy'] = (1 + df['Strategy_Returns']).cumprod()
        
        # Metrics
        total_return = (df['Cumulative_Strategy'].iloc[-1] - 1) * 100
        market_return = (df['Cumulative_Market'].iloc[-1] - 1) * 100
        
        num_trades = len(df[df['Signal'] != 0])
        winning_trades = len(df[(df['Signal'] == -1) & (df['Strategy_Returns'] > 0)])
        win_rate = (winning_trades / (num_trades / 2) * 100) if num_trades > 0 else 0
        
        sharpe = np.sqrt(252) * df['Strategy_Returns'].mean() / df['Strategy_Returns'].std() if df['Strategy_Returns'].std() != 0 else 0
        
        cumulative = df['Cumulative_Strategy']
        running_max = cumulative.expanding().max()
        drawdown = (cumulative - running_max) / running_max
        max_drawdown = drawdown.min() * 100
        
        return {
            'df': df,
            'total_return': total_return,
            'market_return': market_return,
            'num_trades': num_trades,
            'win_rate': win_rate,
            'sharpe_ratio': sharpe,
            'max_drawdown': max_drawdown,
            'final_value': initial_capital * df['Cumulative_Strategy'].iloc[-1]
        }
    except Exception as e:
        st.error(f"Backtest error: {str(e)}")
        return None

def screen_stocks_advanced():
    """Screen top stocks with AI scoring"""
    tickers = [
        'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META', 'TSLA', 'BRK-B',
        'JPM', 'JNJ', 'V', 'PG', 'MA', 'HD', 'CVX', 'MRK', 'ABBV', 'KO',
        'PEP', 'COST', 'AVGO', 'TMO', 'WMT', 'DIS', 'CSCO', 'ACN', 'NFLX',
        'AMD', 'INTC', 'QCOM', 'TXN', 'ORCL', 'IBM', 'CRM', 'ADBE', 'PYPL'
    ]
    
    results = []
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    import time
    
    for idx, ticker in enumerate(tickers):
        try:
            status_text.text(f"Analyzing {ticker}... ({idx + 1}/{len(tickers)})")
            
            # Add delay between requests to avoid rate limiting
            if idx > 0:
                time.sleep(0.5)  # 500ms delay between stocks
            
            hist, info = get_stock_data(ticker, '6mo')
            
            if not hist.empty and len(hist) > 50:
                hist = calculate_technical_indicators(hist)
                score, _ = calculate_advanced_score(hist, info)
                
                current_price = hist['Close'].iloc[-1]
                change_1m = ((current_price - hist['Close'].iloc[-20]) / hist['Close'].iloc[-20]) * 100
                
                signal, _, _ = get_recommendation(score, hist)
                
                results.append({
                    'Ticker': ticker,
                    'Price': f"${current_price:.2f}",
                    'Change_1M': f"{change_1m:+.2f}%",
                    'AI_Score': score,
                    'Signal': signal,
                    'RSI': f"{hist['RSI'].iloc[-1]:.0f}" if pd.notna(hist['RSI'].iloc[-1]) else "N/A",
                    'Volume': f"{info.get('volume', 0)/1e6:.1f}M"
                })
            
            progress_bar.progress((idx + 1) / len(tickers))
            
        except Exception as e:
            # If we hit rate limit, wait longer
            if 'rate limit' in str(e).lower() or '429' in str(e):
                status_text.warning(f"⏳ Rate limited. Taking a 5-second break...")
                time.sleep(5)
            continue
    
    progress_bar.empty()
    status_text.empty()
    
    if results:
        return pd.DataFrame(results).sort_values('AI_Score', ascending=False).reset_index(drop=True)
    return pd.DataFrame()

# Sidebar
with st.sidebar:
    st.markdown("# 📈 StockMaster Pro")
    st.markdown("### AI-Powered Analysis")
    st.markdown("---")
    
    st.markdown("#### Quick Navigation")
    pages = {
        "📊 Stock Analysis": "Stock Analysis",
        "🔍 Stock Screener": "Stock Screener",
        "⚡ Backtesting": "Backtesting",
        "⭐ Watchlist": "Watchlist",
        "💰 Position Sizer": "Position Sizer"
    }
    
    for icon_name, page_name in pages.items():
        if st.button(icon_name, use_container_width=True, key=f"nav_{page_name}"):
            st.session_state.page = page_name
            st.rerun()
    
    st.markdown("---")
    
    st.markdown("#### Features")
    features = [
        "✅ Real-time Data",
        "✅ AI Scoring (0-100)",
        "✅ Technical Indicators",
        "✅ Price Predictions",
        "✅ Backtesting Engine",
        "✅ Stock Screener",
        "✅ Support/Resistance",
        "✅ Risk Management"
    ]
    for feature in features:
        st.markdown(feature)
    
    st.markdown("---")
    st.caption("Data powered by Yahoo Finance")
    st.caption("For educational purposes only")

# Main App
page = st.session_state.page

# Rate limit info
if 'show_rate_limit_info' not in st.session_state:
    st.session_state.show_rate_limit_info = True

if st.session_state.show_rate_limit_info:
    info_container = st.container()
    with info_container:
        col1, col2 = st.columns([6, 1])
        with col1:
            st.info("💡 **Tip:** Yahoo Finance has rate limits. If you see errors, wait 1-2 minutes between analyses or use different tickers. Data is cached for 10 minutes to help with this.")
        with col2:
            if st.button("✕", key="close_info"):
                st.session_state.show_rate_limit_info = False
                st.rerun()

# ==================== STOCK ANALYSIS PAGE ====================
if page == "Stock Analysis":
    st.title("📊 Advanced Stock Analysis")
    
    col1, col2, col3 = st.columns([3, 2, 1])
    with col1:
        ticker = st.text_input("Enter Stock Ticker", value="AAPL", placeholder="e.g., AAPL, MSFT, GOOGL").upper()
    with col2:
        period = st.selectbox("Time Period", ["1mo", "3mo", "6mo", "1y", "2y", "5y"], index=2)
    with col3:
        st.write("")
        st.write("")
        analyze_btn = st.button("🔍 Analyze", type="primary", use_container_width=True)
    
    if ticker:
        try:
            with st.spinner(f"Analyzing {ticker}..."):
                hist, info = get_stock_data(ticker, period)
            
            if hist.empty:
                st.error("❌ Invalid ticker or no data available")
            else:
                hist = calculate_technical_indicators(hist)
                current_price = hist['Close'].iloc[-1]
                prev_close = hist['Close'].iloc[-2] if len(hist) > 1 else current_price
                change = current_price - prev_close
                change_pct = (change / prev_close) * 100
                
                # Calculate AI Score
                ai_score, breakdown = calculate_advanced_score(hist, info)
                signal, signal_color, emoji = get_recommendation(ai_score, hist)
                
                # Top Metrics Row
                st.markdown("### Key Metrics")
                col1, col2, col3, col4, col5 = st.columns(5)
                
                with col1:
                    st.metric("Current Price", f"${current_price:.2f}", f"{change_pct:+.2f}%")
                with col2:
                    color = "🟢" if ai_score >= 60 else "🟡" if ai_score >= 40 else "🔴"
                    st.metric("AI Score", f"{color} {ai_score}/100")
                with col3:
                    day_change = ((hist['Close'].iloc[-1] - hist['Open'].iloc[-1]) / hist['Open'].iloc[-1]) * 100
                    st.metric("Day Change", f"{day_change:+.2f}%")
                with col4:
                    volume = info.get('volume', hist['Volume'].iloc[-1])
                    st.metric("Volume", f"{volume/1e6:.1f}M")
                with col5:
                    market_cap = info.get('marketCap', 0)
                    st.metric("Market Cap", f"${market_cap/1e9:.1f}B" if market_cap > 0 else "N/A")
                
                # Signal Box
                st.markdown(f"""
                <div class="recommendation-box {signal_color}">
                    <h2 style="margin:0;">{emoji} {signal}</h2>
                    <p style="margin:0.5rem 0 0 0;">AI Confidence Score: {ai_score}/100</p>
                </div>
                """, unsafe_allow_html=True)
                
                # Score Breakdown
                with st.expander("📊 Score Breakdown", expanded=True):
                    cols = st.columns(3)
                    for idx, (category, score) in enumerate(breakdown.items()):
                        with cols[idx % 3]:
                            max_score = 25 if category == "Trend Analysis" else 20 if category in ["Momentum", "Fundamentals"] else 15 if category == "Volatility" else 10
                            percentage = (score / max_score) * 100
                            st.metric(category, f"{score}/{max_score}", f"{percentage:.0f}%")
                
                st.markdown("---")
                
                # Price Chart with Indicators
                st.subheader("📈 Price Chart & Technical Analysis")
                
                fig = make_subplots(
                    rows=4, cols=1,
                    shared_xaxes=True,
                    vertical_spacing=0.05,
                    row_heights=[0.5, 0.15, 0.15, 0.2],
                    subplot_titles=('Price & Moving Averages', 'MACD', 'RSI', 'Volume')
                )
                
                # Candlestick
                fig.add_trace(go.Candlestick(
                    x=hist.index,
                    open=hist['Open'],
                    high=hist['High'],
                    low=hist['Low'],
                    close=hist['Close'],
                    name='Price',
                    increasing_line_color='#26a69a',
                    decreasing_line_color='#ef5350'
                ), row=1, col=1)
                
                # Moving Averages
                fig.add_trace(go.Scatter(x=hist.index, y=hist['SMA_20'], name='SMA 20', line=dict(color='orange', width=1)), row=1, col=1)
                fig.add_trace(go.Scatter(x=hist.index, y=hist['SMA_50'], name='SMA 50', line=dict(color='blue', width=1)), row=1, col=1)
                fig.add_trace(go.Scatter(x=hist.index, y=hist['SMA_200'], name='SMA 200', line=dict(color='red', width=1)), row=1, col=1)
                
                # Bollinger Bands
                fig.add_trace(go.Scatter(x=hist.index, y=hist['BB_Upper'], name='BB Upper', line=dict(color='gray', width=1, dash='dash'), opacity=0.3), row=1, col=1)
                fig.add_trace(go.Scatter(x=hist.index, y=hist['BB_Lower'], name='BB Lower', line=dict(color='gray', width=1, dash='dash'), opacity=0.3, fill='tonexty'), row=1, col=1)
                
                # MACD
                fig.add_trace(go.Scatter(x=hist.index, y=hist['MACD'], name='MACD', line=dict(color='blue', width=2)), row=2, col=1)
                fig.add_trace(go.Scatter(x=hist.index, y=hist['Signal_Line'], name='Signal', line=dict(color='red', width=2)), row=2, col=1)
                colors = ['green' if val >= 0 else 'red' for val in hist['MACD_Histogram']]
                fig.add_trace(go.Bar(x=hist.index, y=hist['MACD_Histogram'], name='Histogram', marker_color=colors), row=2, col=1)
                
                # RSI
                fig.add_trace(go.Scatter(x=hist.index, y=hist['RSI'], name='RSI', line=dict(color='purple', width=2)), row=3, col=1)
                fig.add_hline(y=70, line_dash="dash", line_color="red", opacity=0.5, row=3, col=1)
                fig.add_hline(y=30, line_dash="dash", line_color="green", opacity=0.5, row=3, col=1)
                fig.add_hrect(y0=30, y1=70, fillcolor="gray", opacity=0.1, row=3, col=1)
                
                # Volume
                colors = ['green' if hist['Close'].iloc[i] > hist['Open'].iloc[i] else 'red' for i in range(len(hist))]
                fig.add_trace(go.Bar(x=hist.index, y=hist['Volume'], name='Volume', marker_color=colors), row=4, col=1)
                fig.add_trace(go.Scatter(x=hist.index, y=hist['Volume_SMA'], name='Vol SMA', line=dict(color='orange', width=1)), row=4, col=1)
                
                fig.update_layout(
                    height=1000,
                    template='plotly_dark',
                    showlegend=True,
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                    hovermode='x unified',
                    xaxis_rangeslider_visible=False
                )
                
                fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='rgba(128,128,128,0.2)')
                fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='rgba(128,128,128,0.2)')
                
                st.plotly_chart(fig, use_container_width=True)
                
                # Additional Analysis
                col1, col2 = st.columns(2)
                
                with col1:
                    st.subheader("📋 Company Information")
                    company_data = {
                        "Company Name": info.get('longName', 'N/A'),
                        "Sector": info.get('sector', 'N/A'),
                        "Industry": info.get('industry', 'N/A'),
                        "Country": info.get('country', 'N/A'),
                        "Website": info.get('website', 'N/A')
                    }
                    for key, value in company_data.items():
                        st.text(f"{key}: {value}")
                    
                    st.markdown("---")
                    st.subheader("💰 Fundamentals")
                    fundamentals = {
                        "P/E Ratio": f"{info.get('trailingPE', 'N/A'):.2f}" if isinstance(info.get('trailingPE'), (int, float)) else "N/A",
                        "EPS": f"${info.get('trailingEps', 0):.2f}",
                        "Dividend Yield": f"{info.get('dividendYield', 0)*100:.2f}%" if info.get('dividendYield') else "N/A",
                        "Profit Margin": f"{info.get('profitMargins', 0)*100:.2f}%" if info.get('profitMargins') else "N/A",
                        "ROE": f"{info.get('returnOnEquity', 0)*100:.2f}%" if info.get('returnOnEquity') else "N/A",
                        "Debt/Equity": f"{info.get('debtToEquity', 0):.2f}" if info.get('debtToEquity') else "N/A"
                    }
                    
                    fund_df = pd.DataFrame(list(fundamentals.items()), columns=['Metric', 'Value'])
                    st.dataframe(fund_df, hide_index=True, use_container_width=True)
                
                with col2:
                    st.subheader("🎯 Support & Resistance Levels")
                    support, resistance = calculate_support_resistance(hist)
                    
                    st.markdown("**Resistance Levels** (🔴 Sell zones)")
                    if resistance:
                        for i, level in enumerate(resistance[:3], 1):
                            distance = ((level - current_price) / current_price) * 100
                            st.text(f"R{i}: ${level:.2f} (+{distance:.2f}%)")
                    else:
                        st.text("No clear resistance identified")
                    
                    st.markdown("**Current Price**")
                    st.text(f"💰 ${current_price:.2f}")
                    
                    st.markdown("**Support Levels** (🟢 Buy zones)")
                    if support:
                        for i, level in enumerate(support[:3], 1):
                            distance = ((current_price - level) / current_price) * 100
                            st.text(f"S{i}: ${level:.2f} (-{distance:.2f}%)")
                    else:
                        st.text("No clear support identified")
                    
                    st.markdown("---")
                    st.subheader("🔮 AI Price Prediction")
                    prediction, confidence, range_pred = predict_price_ml(hist, 30)
                    
                    if prediction:
                        pred_change = ((prediction - current_price) / current_price) * 100
                        st.metric("30-Day Forecast", f"${prediction:.2f}", f"{pred_change:+.2f}%")
                        st.progress(confidence / 100)
                        st.caption(f"Confidence: {confidence:.0f}%")
                        
                        if range_pred:
                            st.text(f"Range: ${range_pred[0]:.2f} - ${range_pred[1]:.2f}")
                        
                        st.warning("⚠️ Predictions are estimates only. Not financial advice.")
                    else:
                        st.info("Insufficient data for prediction")
                
                # Technical Indicators Summary
                st.markdown("---")
                st.subheader("📊 Current Technical Indicators")
                
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    rsi = hist['RSI'].iloc[-1]
                    rsi_signal = "Overbought" if rsi > 70 else "Oversold" if rsi < 30 else "Neutral"
                    st.metric("RSI (14)", f"{rsi:.1f}", rsi_signal)
                
                with col2:
                    macd_signal = "Bullish" if hist['MACD'].iloc[-1] > hist['Signal_Line'].iloc[-1] else "Bearish"
                    st.metric("MACD Signal", macd_signal, f"{hist['MACD_Histogram'].iloc[-1]:.2f}")
                
                with col3:
                    stoch = hist['Stochastic_K'].iloc[-1] if pd.notna(hist['Stochastic_K'].iloc[-1]) else 0
                    stoch_signal = "Overbought" if stoch > 80 else "Oversold" if stoch < 20 else "Neutral"
                    st.metric("Stochastic", f"{stoch:.1f}", stoch_signal)
                
                with col4:
                    atr = hist['ATR'].iloc[-1] if pd.notna(hist['ATR'].iloc[-1]) else 0
                    st.metric("ATR (14)", f"${atr:.2f}", "Volatility")
                
        except Exception as e:
            st.error(f"❌ Error analyzing stock: {str(e)}")

# ==================== STOCK SCREENER PAGE ====================
elif page == "Stock Screener":
    st.title("🔍 AI Stock Screener")
    st.markdown("Scan 35+ top stocks with AI-powered analysis")
    
    col1, col2 = st.columns([3, 1])
    with col1:
        st.info("🤖 Our AI analyzes multiple factors: trends, momentum, volatility, volume, fundamentals, and recent performance")
    with col2:
        if st.button("🚀 Start Screening", type="primary", use_container_width=True):
            with st.spinner("Analyzing stocks... This may take a minute"):
                results_df = screen_stocks_advanced()
            
            if not results_df.empty:
                st.success(f"✅ Analyzed {len(results_df)} stocks successfully!")
                
                # Filters
                st.markdown("### Filter Results")
                col1, col2, col3 = st.columns(3)
                with col1:
                    min_score = st.slider("Minimum AI Score", 0, 100, 50)
                with col2:
                    signal_filter = st.multiselect("Signal Type", ["STRONG BUY", "BUY", "HOLD", "SELL", "STRONG SELL"], default=["STRONG BUY", "BUY", "HOLD"])
                with col3:
                    sort_by = st.selectbox("Sort By", ["AI_Score", "Change_1M", "Price"])
                
                # Apply filters
                filtered_df = results_df[
                    (results_df['AI_Score'] >= min_score) &
                    (results_df['Signal'].isin(signal_filter))
                ].sort_values(by=sort_by, ascending=False)
                
                # Display results
                st.markdown(f"### 📊 Top Stocks ({len(filtered_df)} results)")
                
                # Style the dataframe
                def color_score(val):
                    if isinstance(val, (int, float)):
                        if val >= 75:
                            return 'background-color: #22c55e; color: white; font-weight: bold'
                        elif val >= 60:
                            return 'background-color: #84cc16; color: white'
                        elif val >= 40:
                            return 'background-color: #eab308; color: black'
                        else:
                            return 'background-color: #ef4444; color: white'
                    return ''
                
                styled_df = filtered_df.style.applymap(color_score, subset=['AI_Score'])
                st.dataframe(styled_df, use_container_width=True, height=600)
                
                # Top 5 recommendations
                st.markdown("### 🏆 Top 5 Recommendations")
                top_5 = filtered_df.head(5)
                
                cols = st.columns(5)
                for idx, (_, row) in enumerate(top_5.iterrows()):
                    with cols[idx]:
                        st.markdown(f"""
                        <div class="metric-card">
                            <h3>{row['Ticker']}</h3>
                            <p style="font-size: 1.5rem; margin: 0.5rem 0;">{row['Price']}</p>
                            <p style="color: #22c55e; margin: 0;">{row['Change_1M']}</p>
                            <p style="font-weight: bold; font-size: 1.2rem; margin: 0.5rem 0;">Score: {row['AI_Score']}/100</p>
                            <p style="margin: 0;">{row['Signal']}</p>
                        </div>
                        """, unsafe_allow_html=True)
                
                # Download button
                csv = filtered_df.to_csv(index=False)
                st.download_button(
                    label="📥 Download Results as CSV",
                    data=csv,
                    file_name=f"stock_screening_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            else:
                st.warning("No results found. Please try again.")

# ==================== BACKTESTING PAGE ====================
elif page == "Backtesting":
    st.title("⚡ Strategy Backtesting")
    st.markdown("Test trading strategies on historical data")
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        bt_ticker = st.text_input("Ticker", value="AAPL").upper()
    with col2:
        start_date = st.date_input("Start Date", datetime.now() - timedelta(days=365))
    with col3:
        end_date = st.date_input("End Date", datetime.now())
    with col4:
        initial_capital = st.number_input("Initial Capital ($)", value=10000, step=1000)
    
    if st.button("🚀 Run Backtest", type="primary", use_container_width=True):
        with st.spinner("Running backtest..."):
            results = run_backtest_strategy(bt_ticker, start_date, end_date, initial_capital)
        
        if results:
            st.success("✅ Backtest completed!")
            
            # Performance metrics
            col1, col2, col3, col4, col5 = st.columns(5)
            with col1:
                st.metric("Total Return", f"{results['total_return']:.2f}%")
            with col2:
                st.metric("Buy & Hold", f"{results['market_return']:.2f}%")
            with col3:
                st.metric("Sharpe Ratio", f"{results['sharpe_ratio']:.2f}")
            with col4:
                st.metric("Max Drawdown", f"{results['max_drawdown']:.2f}%")
            with col5:
                st.metric("Total Trades", results['num_trades'])
            
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Win Rate", f"{results['win_rate']:.1f}%")
            with col2:
                st.metric("Final Value", f"${results['final_value']:.2f}")
            
            # Performance chart
            st.markdown("### 📈 Performance Comparison")
            
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=results['df'].index,
                y=results['df']['Cumulative_Strategy'] * initial_capital,
                name='Strategy',
                line=dict(color='#22c55e', width=2)
            ))
            fig.add_trace(go.Scatter(
                x=results['df'].index,
                y=results['df']['Cumulative_Market'] * initial_capital,
                name='Buy & Hold',
                line=dict(color='#3b82f6', width=2)
            ))
            
            fig.update_layout(
                template='plotly_dark',
                height=500,
                hovermode='x unified',
                yaxis_title='Portfolio Value ($)',
                xaxis_title='Date'
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            # Trade signals
            st.markdown("### 📊 Trade Signals")
            trades = results['df'][results['df']['Signal'] != 0][['Close', 'Signal', 'RSI', 'MACD']]
            trades['Action'] = trades['Signal'].apply(lambda x: 'BUY' if x == 1 else 'SELL')
            st.dataframe(trades.tail(20), use_container_width=True)
            
        else:
            st.error("❌ Backtest failed. Please check your inputs.")

# ==================== WATCHLIST PAGE ====================
elif page == "Watchlist":
    st.title("⭐ My Watchlist")
    
    col1, col2 = st.columns([3, 1])
    with col1:
        new_ticker = st.text_input("Add Stock to Watchlist", placeholder="e.g., TSLA").upper()
    with col2:
        st.write("")
        st.write("")
        if st.button("➕ Add", type="primary", use_container_width=True):
            if new_ticker and new_ticker not in st.session_state.watchlist:
                st.session_state.watchlist.append(new_ticker)
                st.success(f"✅ Added {new_ticker} to watchlist")
                st.rerun()
            elif new_ticker in st.session_state.watchlist:
                st.warning("Already in watchlist")
    
    if st.session_state.watchlist:
        st.markdown(f"### 📋 Your Stocks ({len(st.session_state.watchlist)})")
        
        # Fetch data for all watchlist stocks
        watchlist_data = []
        for ticker in st.session_state.watchlist:
            try:
                hist, info = get_stock_data(ticker, '1mo')
                if not hist.empty:
                    hist = calculate_technical_indicators(hist)
                    score, _ = calculate_advanced_score(hist, info)
                    
                    current_price = hist['Close'].iloc[-1]
                    change = ((current_price - hist['Close'].iloc[0]) / hist['Close'].iloc[0]) * 100
                    
                    signal, _, emoji = get_recommendation(score, hist)
                    
                    watchlist_data.append({
                        'Ticker': ticker,
                        'Price': current_price,
                        'Change': change,
                        'Score': score,
                        'Signal': signal,
                        'Emoji': emoji
                    })
            except:
                continue
        
        # Display watchlist items
        for item in watchlist_data:
            col1, col2, col3, col4, col5, col6 = st.columns([2, 2, 2, 2, 2, 1])
            
            with col1:
                st.markdown(f"### {item['Ticker']}")
            with col2:
                st.metric("Price", f"${item['Price']:.2f}")
            with col3:
                st.metric("Change", f"{item['Change']:+.2f}%")
            with col4:
                color = "🟢" if item['Score'] >= 60 else "🟡" if item['Score'] >= 40 else "🔴"
                st.metric("AI Score", f"{color} {item['Score']}/100")
            with col5:
                st.markdown(f"**{item['Emoji']} {item['Signal']}**")
            with col6:
                if st.button("🗑️", key=f"remove_{item['Ticker']}", help="Remove from watchlist"):
                    st.session_state.watchlist.remove(item['Ticker'])
                    st.rerun()
            
            st.markdown("---")
        
    else:
        st.info("👋 Your watchlist is empty. Add some stocks to get started!")

# ==================== POSITION SIZER PAGE ====================
elif page == "Position Sizer":
    st.title("💰 Position Size Calculator")
    st.markdown("Calculate optimal position sizes based on risk management")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Account Settings")
        account_size = st.number_input("Account Size ($)", value=10000, step=1000)
        risk_percent = st.slider("Risk Per Trade (%)", 0.5, 5.0, 2.0, 0.5)
        
        st.subheader("Stock Details")
        ps_ticker = st.text_input("Ticker", value="AAPL").upper()
        entry_price = st.number_input("Entry Price ($)", value=150.0, step=1.0)
        stop_loss = st.number_input("Stop Loss ($)", value=145.0, step=1.0)
    
    with col2:
        st.subheader("Risk Management Method")
        method = st.radio("Select Method", ["Fixed Percentage", "Kelly Criterion", "Volatility Based"])
        
        if method == "Kelly Criterion":
            win_rate = st.slider("Win Rate (%)", 30, 70, 55) / 100
            avg_win = st.number_input("Average Win (R)", value=1.5, step=0.1)
            avg_loss = st.number_input("Average Loss (R)", value=1.0, step=0.1)
    
    if st.button("💡 Calculate Position Size", type="primary", use_container_width=True):
        try:
            # Fetch stock data
            hist, info = get_stock_data(ps_ticker, '1mo')
            
            if not hist.empty:
                hist = calculate_technical_indicators(hist)
                current_price = hist['Close'].iloc[-1]
                volatility = hist['ATR'].iloc[-1] if pd.notna(hist['ATR'].iloc[-1]) else None
                
                # Calculate position size
                risk_amount = account_size * (risk_percent / 100)
                risk_per_share = entry_price - stop_loss
                
                if risk_per_share <= 0:
                    st.error("❌ Stop loss must be below entry price")
                else:
                    # Basic calculation
                    shares_basic = int(risk_amount / risk_per_share)
                    position_value = shares_basic * entry_price
                    
                    st.success("✅ Position Size Calculated")
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Shares to Buy", f"{shares_basic:,}")
                    with col2:
                        st.metric("Position Value", f"${position_value:,.2f}")
                    with col3:
                        portfolio_pct = (position_value / account_size) * 100
                        st.metric("Portfolio %", f"{portfolio_pct:.1f}%")
                    
                    st.markdown("---")
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Risk Amount", f"${risk_amount:.2f}")
                    with col2:
                        st.metric("Risk Per Share", f"${risk_per_share:.2f}")
                    with col3:
                        potential_loss = shares_basic * risk_per_share
                        st.metric("Max Loss", f"${potential_loss:.2f}")
                    
                    # Advanced calculations
                    if method == "Kelly Criterion":
                        q = 1 - win_rate
                        b = avg_win / avg_loss
                        kelly_fraction = max(0, min((win_rate * b - q) / b * 0.5, 0.25))
                        kelly_shares = int(account_size * kelly_fraction / entry_price)
                        
                        st.markdown("### Kelly Criterion Analysis")
                        st.metric("Kelly Fraction", f"{kelly_fraction*100:.1f}%")
                        st.metric("Kelly Position", f"{kelly_shares:,} shares")
                        st.info("Kelly Criterion uses win rate and win/loss ratio to optimize position size")
                    
                    elif method == "Volatility Based" and volatility:
                        vol_shares = int(risk_amount / volatility)
                        st.markdown("### Volatility-Based Sizing")
                        st.metric("ATR", f"${volatility:.2f}")
                        st.metric("Vol-Adjusted Shares", f"{vol_shares:,}")
                        st.info("Position sized based on recent price volatility (ATR)")
                    
                    # Risk scenarios
                    st.markdown("---")
                    st.markdown("### 📊 Risk Scenarios")
                    
                    scenarios = pd.DataFrame({
                        'Scenario': ['Stop Loss Hit', 'Target (2R)', 'Target (3R)', 'Current Price'],
                        'Price': [
                            stop_loss,
                            entry_price + (2 * risk_per_share),
                            entry_price + (3 * risk_per_share),
                            current_price
                        ]
                    })
                    
                    scenarios['P&L'] = (scenarios['Price'] - entry_price) * shares_basic
                    scenarios['Return %'] = ((scenarios['Price'] - entry_price) / entry_price) * 100
                    scenarios['Account Impact %'] = (scenarios['P&L'] / account_size) * 100
                    
                    st.dataframe(scenarios.style.format({
                        'Price': '${:.2f}',
                        'P&L': '${:,.2f}',
                        'Return %': '{:+.2f}%',
                        'Account Impact %': '{:+.2f}%'
                    }), hide_index=True, use_container_width=True)
                    
                    st.warning("⚠️ This is for educational purposes only. Always do your own research and consider consulting a financial advisor.")
            else:
                st.error("❌ Could not fetch stock data")
                
        except Exception as e:
            st.error(f"❌ Error: {str(e)}")

# Footer
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #888; padding: 2rem;'>
    <p><strong>StockMaster Pro</strong> © 2025 | Powered by AI & Yahoo Finance</p>
    <p style='font-size: 0.9rem;'>⚠️ For educational purposes only. Not financial advice. Always do your own research.</p>
</div>
""", unsafe_allow_html=True)
