import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import numpy as np

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

# Title with live indicator
col_title, col_live = st.columns([5, 1])
with col_title:
    st.title("🚀 AI Stock Analyzer Pro")
with col_live:
    if st.session_state.auto_refresh:
        st.success("🟢 LIVE")
    else:
        st.info("⚪ Paused")

st.markdown("---")

# Sidebar
st.sidebar.header("💼 Portfolio Settings")
st.session_state.portfolio_size = st.sidebar.number_input(
    "Portfolio Size ($)", 
    value=st.session_state.portfolio_size, 
    min_value=0.0, 
    step=100.0
)
st.session_state.risk_percent = st.sidebar.slider(
    "Risk per Trade (%)", 
    min_value=1, 
    max_value=10, 
    value=st.session_state.risk_percent
)

st.sidebar.markdown(f"**Portfolio:** ${st.session_state.portfolio_size:.2f}")
st.sidebar.markdown(f"**Risk:** {st.session_state.risk_percent}%")
st.sidebar.markdown(f"**Max Risk:** ${st.session_state.portfolio_size * (st.session_state.risk_percent / 100):.2f}")

st.sidebar.markdown("---")
st.sidebar.header("⭐ Watchlist")

new_ticker = st.sidebar.text_input("Add to Watchlist", "").upper()
if st.sidebar.button("➕ Add") and new_ticker:
    if new_ticker not in st.session_state.favorites:
        st.session_state.favorites.append(new_ticker)
        st.sidebar.success(f"Added {new_ticker}!")
        st.rerun()

if st.session_state.favorites:
    for fav in st.session_state.favorites:
        col1, col2 = st.sidebar.columns([4, 1])
        with col1:
            if st.button(fav, key=f"fav_{fav}", use_container_width=True):
                st.session_state.quick_analyze = fav
        with col2:
            if st.button("❌", key=f"remove_{fav}"):
                st.session_state.favorites.remove(fav)
                st.rerun()

st.sidebar.markdown("---")
st.sidebar.header("🔔 Active Alerts")
if st.session_state.alerts:
    for i, alert in enumerate(st.session_state.alerts):
        with st.sidebar.expander(f"{alert['ticker']} - {alert['condition']}"):
            st.write(f"**Trigger:** {alert['condition']}")
            if st.button("Delete", key=f"del_alert_{i}"):
                st.session_state.alerts.pop(i)
                st.rerun()

st.sidebar.markdown("---")
st.sidebar.header("🔄 Auto-Refresh")
st.session_state.auto_refresh = st.sidebar.checkbox("Enable Live Updates", value=st.session_state.auto_refresh)
if st.session_state.auto_refresh:
    st.session_state.refresh_interval = st.sidebar.slider("Refresh interval (seconds)", 30, 300, 60)
    st.sidebar.info(f"Updates every {st.session_state.refresh_interval}s")

def get_market_overview():
    """Get major market indices and overview"""
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
    high = hist['High'].values
    low = hist['Low'].values
    
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
    
    # Double Top
    if len(close) >= 30:
        recent = close[-30:]
        max_idx = np.argmax(recent[:15])
        max_idx2 = np.argmax(recent[15:]) + 15
        
        if abs(recent[max_idx] - recent[max_idx2]) / recent[max_idx] < 0.02:
            patterns.append("📉 Double Top (Bearish)")
    
    # Double Bottom
    if len(close) >= 30:
        recent = close[-30:]
        min_idx = np.argmin(recent[:15])
        min_idx2 = np.argmin(recent[15:]) + 15
        
        if abs(recent[min_idx] - recent[min_idx2]) / recent[min_idx] < 0.02:
            patterns.append("📈 Double Bottom (Bullish)")
    
    # Bull Flag
    recent_10 = close[-10:]
    if len(recent_10) == 10:
        trend = np.polyfit(range(10), recent_10, 1)[0]
        if trend < 0 and close[-1] > close[-10]:
            patterns.append("🚀 Bull Flag (Bullish)")
    
    # Bear Flag
    if len(recent_10) == 10:
        trend = np.polyfit(range(10), recent_10, 1)[0]
        if trend > 0 and close[-1] < close[-10]:
            patterns.append("📉 Bear Flag (Bearish)")
    
    return patterns if patterns else ["No clear patterns detected"]

def calculate_advanced_indicators(hist):
    """Calculate advanced technical indicators"""
    indicators = {}
    
    # Fibonacci Retracement
    high_price = hist['High'].max()
    low_price = hist['Low'].min()
    diff = high_price - low_price
    
    indicators['fib_236'] = high_price - (0.236 * diff)
    indicators['fib_382'] = high_price - (0.382 * diff)
    indicators['fib_500'] = high_price - (0.500 * diff)
    indicators['fib_618'] = high_price - (0.618 * diff)
    
    # Stochastic Oscillator
    low_14 = hist['Low'].rolling(14).min()
    high_14 = hist['High'].rolling(14).max()
    k_percent = 100 * ((hist['Close'] - low_14) / (high_14 - low_14))
    indicators['stochastic_k'] = k_percent.iloc[-1]
    indicators['stochastic_d'] = k_percent.rolling(3).mean().iloc[-1]
    
    # ADX (Average Directional Index)
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
    
    # OBV (On-Balance Volume)
    obv = (np.sign(hist['Close'].diff()) * hist['Volume']).fillna(0).cumsum()
    indicators['obv'] = obv.iloc[-1]
    indicators['obv_trend'] = "Bullish" if obv.iloc[-1] > obv.iloc[-10] else "Bearish"
    
    return indicators

def predict_price(hist):
    """Simple price prediction using linear regression"""
    if len(hist) < 30:
        return None
    
    # Use last 30 days
    recent = hist['Close'].tail(30).values
    x = np.arange(len(recent))
    
    # Linear regression
    coefficients = np.polyfit(x, recent, 1)
    
    # Predict next 5 days
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
    """Get fundamental analysis data"""
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
    """Advanced position sizing methods"""
    if portfolio_size == 0:
        return {
            'fixed_percent': 0,
            'volatility_based': 0,
            'kelly': 0
        }
    
    # Fixed Percentage (2% risk)
    risk_amount = portfolio_size * 0.02
    fixed_shares = int(risk_amount / (price * 0.1))  # Assuming 10% stop loss
    
    # Volatility-based
    if volatility > 0:
        vol_multiplier = 20 / volatility if volatility > 20 else 1
        vol_shares = int(fixed_shares * vol_multiplier)
    else:
        vol_shares = fixed_shares
    
    # Kelly Criterion (simplified)
    win_rate = 0.55  # Assumed 55% win rate
    avg_win = 1.5  # Assumed 1.5:1 reward/risk
    avg_loss = 1.0
    
    kelly_percent = (win_rate * avg_win - (1 - win_rate) * avg_loss) / avg_win
    kelly_percent = max(0, min(kelly_percent * 0.5, 0.05))  # Half Kelly, max 5%
    
    kelly_shares = int((portfolio_size * kelly_percent) / price)
    
    return {
        'fixed_percent': fixed_shares,
        'volatility_based': vol_shares,
        'kelly': kelly_shares
    }

def create_candlestick_chart(ticker, hist):
    """Create interactive candlestick chart"""
    fig = make_subplots(
        rows=3, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.05,
        subplot_titles=(f'{ticker} Price & Indicators', 'Volume', 'RSI'),
        row_heights=[0.6, 0.2, 0.2]
    )
    
    # Candlestick
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
    
    # SMAs
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
    
    # Bollinger Bands
    sma20 = hist['Close'].rolling(20).mean()
    std20 = hist['Close'].rolling(20).std()
    upper_band = sma20 + (std20 * 2)
    lower_band = sma20 - (std20 * 2)
    
    fig.add_trace(
        go.Scatter(x=hist.index, y=upper_band, name='Upper BB', 
                   line=dict(color='gray', width=1, dash='dash'), opacity=0.5),
        row=1, col=1
    )
    fig.add_trace(
        go.Scatter(x=hist.index, y=lower_band, name='Lower BB', 
                   line=dict(color='gray', width=1, dash='dash'), opacity=0.5),
        row=1, col=1
    )
    
    # Volume
    colors = ['red' if hist['Close'].iloc[i] < hist['Open'].iloc[i] else 'green' for i in range(len(hist))]
    fig.add_trace(
        go.Bar(x=hist.index, y=hist['Volume'], name='Volume', marker_color=colors),
        row=2, col=1
    )
    
    # RSI
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
    """Backtest the trading strategy"""
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
    """Enhanced stock analysis with all features"""
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="6mo")
        info = stock.info

        if hist.empty or len(hist) < 50:
            return {"ticker": ticker, "verdict": "NO DATA", "score": 0, "error": True}

        close = hist["Close"].iloc[-1]
        prev_close = hist["Close"].iloc[-2] if len(hist) > 1 else close

        # Technical indicators
        hist["SMA50"] = hist["Close"].rolling(50).mean()
        hist["SMA200"] = hist["Close"].rolling(200).mean()
        sma50 = hist["SMA50"].iloc[-1]
        sma200 = hist["SMA200"].iloc[-1]

        # RSI
        delta = hist["Close"].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs)).iloc[-1]

        # MACD
        exp1 = hist["Close"].ewm(span=12, adjust=False).mean()
        exp2 = hist["Close"].ewm(span=26, adjust=False).mean()
        macd = exp1 - exp2
        signal = macd.ewm(span=9, adjust=False).mean()
        macd_current = macd.iloc[-1]
        signal_current = signal.iloc[-1]

        # Volume
        avg_volume = hist["Volume"].mean()
        current_volume = hist["Volume"].iloc[-1]
        volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1

        # Volatility
        returns = hist["Close"].pct_change()
        volatility = returns.std() * (252 ** 0.5) * 100

        # Scoring
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

        # Verdict
        if score >= 5:
            verdict = "🚀 STRONG BUY"
        elif score >= 3:
            verdict = "✅ BUY"
        elif score >= 1:
            verdict = "⏸️ HOLD"
        else:
            verdict = "❌ SELL"

        # ATR
        hist["H-L"] = hist["High"] - hist["Low"]
        hist["H-C"] = abs(hist["High"] - hist["Close"].shift())
        hist["L-C"] = abs(hist["Low"] - hist["Close"].shift())
        tr = hist[["H-L", "H-C", "L-C"]].max(axis=1)
        atr = tr.rolling(14).mean().iloc[-1]

        tp1 = round(close + atr, 2)
        tp2 = round(close + 2 * atr, 2)
        sl1 = round(close - atr, 2)
        sl2 = round(close - 2 * atr, 2)

        # Position sizing
        max_risk = portfolio_size * (risk_percent / 100)
        risk_per_share = close - sl1
        shares = int(max_risk // risk_per_share) if risk_per_share > 0 else 0

        daily_change = ((close - prev_close) / prev_close) * 100

        # Get advanced features
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
tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9 = st.tabs([
    "🌍 Market Overview",
    "📊 Analysis",
    "🎯 Watchlist", 
    "🔍 Screener",
    "📈 Patterns & Predictions",
    "📐 Position Calculator",
    "💰 Fundamentals",
    "🔙 Backtesting",
    "💎 Buy Signals"
])

with tab1:
    st.header("🌍 Market Overview Dashboard")
    
    # Auto-refresh logic
    if st.session_state.auto_refresh:
        st.info(f"🔄 Auto-refreshing every {st.session_state.refresh_interval} seconds")
        time.sleep(0.1)  # Small delay to prevent too frequent updates
    
    refresh_btn = st.button("🔄 Refresh Market Data", type="primary")
    
    overview = None
    sectors = None
    
    if refresh_btn or st.session_state.auto_refresh:
        with st.spinner("Loading market data..."):
            # Major Indices
            st.subheader("📈 Major Indices")
            overview = get_market_overview()
            
            if overview:
                cols = st.columns(len(overview))
                for i, (name, data) in enumerate(overview.items()):
                    with cols[i]:
                        delta_color = "normal" if name == "VIX" else "normal"
                        st.metric(
                            name,
                            f"{data['price']:,.2f}",
                            f"{data['change']:.2f}%",
                            delta_color=delta_color
                        )
            else:
                st.warning("Unable to load market indices")
            
            st.markdown("---")
            
            # Sector Performance
            st.subheader("🏭 Sector Performance (Daily)")
            sectors = get_sector_performance()
            
            if sectors:
                # Sort sectors by performance
                sorted_sectors = sorted(sectors.items(), key=lambda x: x[1], reverse=True)
                
                # Create horizontal bar chart
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
                    yaxis_title="Sector",
                    height=400,
                    template='plotly_white'
                )
                
                st.plotly_chart(fig, use_container_width=True)
                
                # Top and Bottom Performers
                col1, col2 = st.columns(2)
                with col1:
                    st.success("### 🚀 Top Performers")
                    for sector, perf in sorted_sectors[:3]:
                        st.write(f"**{sector}:** +{perf:.2f}%")
                
                with col2:
                    st.error("### 📉 Bottom Performers")
                    for sector, perf in sorted_sectors[-3:]:
                        st.write(f"**{sector}:** {perf:.2f}%")
            else:
                st.warning("Unable to load sector data")
            
            st.markdown("---")
            
            # Market Breadth
            st.subheader("📊 Market Statistics")
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                if overview and 'S&P 500' in overview:
                    trend = "Bullish 📈" if overview['S&P 500']['change'] > 0 else "Bearish 📉"
                    st.metric("Market Trend", trend)
            
            with col2:
                if overview and 'VIX' in overview:
                    vix_level = overview['VIX']['price']
                    volatility = "Low" if vix_level < 15 else "Medium" if vix_level < 25 else "High"
                    st.metric("Volatility", volatility, f"VIX: {vix_level:.2f}")
            
            with col3:
                if sectors:
                    positive = sum(1 for v in sectors.values() if v > 0)
                    st.metric("Sectors Up", f"{positive}/9")
            
            with col4:
                current_time = datetime.now().strftime("%H:%M:%S")
                st.metric("Last Updated", current_time)
    
    # Market insights
    if overview:
        st.markdown("---")
        st.subheader("💡 Market Insights")
    
    if overview:
        insights = []
        
        if overview.get('S&P 500', {}).get('change', 0) > 1:
            insights.append("🟢 Strong bullish momentum in the broader market")
        elif overview.get('S&P 500', {}).get('change', 0) < -1:
            insights.append("🔴 Market showing weakness today")
        
        if overview.get('VIX', {}).get('price', 0) > 25:
            insights.append("⚠️ High volatility detected - exercise caution")
        elif overview.get('VIX', {}).get('price', 0) < 15:
            insights.append("✅ Low volatility - stable market conditions")
        
        if sectors:
            top_sector = max(sectors.items(), key=lambda x: x[1])
            insights.append(f"🏆 {top_sector[0]} is the strongest sector today (+{top_sector[1]:.2f}%)")
        
        for insight in insights:
            st.info(insight)
    else:
        st.info("Click 'Refresh Market Data' to load market overview")
    
    # Auto-refresh implementation
    if st.session_state.auto_refresh:
        st.rerun()

with tab9:
    st.header("Stock Analysis")
    
    col1, col2, col3 = st.columns([3, 1, 1])
    with col1:
        ticker_input = st.text_input("Enter Ticker", value=st.session_state.get('quick_analyze', '')).upper()
    with col2:
        analyze_btn = st.button("🔍 Analyze", type="primary", use_container_width=True)
    with col3:
        if ticker_input and ticker_input not in st.session_state.favorites:
            if st.button("⭐ Watchlist", use_container_width=True):
                st.session_state.favorites.append(ticker_input)
                st.rerun()
    
    if analyze_btn and ticker_input:
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
                    st.write(f"**Volatility:** {result['volatility']}%")
                
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
                
                with st.expander("🔍 Analysis Details"):
                    for factor in result['factors']:
                        st.write(factor)
            else:
                st.error(f"Error: {result.get('error_msg', 'Unable to analyze')}")

with tab2:
    st.header("🎯 Watchlist Dashboard")
    
    if st.session_state.favorites:
        col1, col2 = st.columns([1, 4])
        with col1:
            if st.button("🔄 Refresh All", type="primary", use_container_width=True):
                with st.spinner("Updating..."):
                    for ticker in st.session_state.favorites:
                        result = analyze_stock(ticker, st.session_state.portfolio_size, st.session_state.risk_percent)
                        if not result['error']:
                            st.session_state.watchlist_data[ticker] = result
                    st.success("Updated!")
                    st.rerun()
        with col2:
            if st.session_state.auto_refresh:
                st.info("🟢 Auto-refresh enabled - Watchlist updates automatically")
        
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
                    
                    if st.button("Analyze", key=f"analyze_{ticker}"):
                        st.session_state.quick_analyze = ticker
                        st.rerun()
                else:
                    st.info(f"### {ticker}")
                    st.write("Click 'Refresh All'")
    else:
        st.info("Add tickers to watchlist!")

with tab3:
    st.header("🔍 AI Stock Screener")
    
    col1, col2 = st.columns([2, 1])
    with col1:
        screener_option = st.radio("Select:", ["Popular", "S&P 100", "Custom"])
    with col2:
        min_score = st.slider("Min Score", 0, 10, 3)
    
    if screener_option == "Popular":
        tickers = ["AAPL", "GOOGL", "MSFT", "AMZN", "TSLA", "NVDA", "META", "NFLX", "AMD", "INTC"]
    elif screener_option == "S&P 100":
        tickers = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "BRK.B", "JPM", "JNJ", 
                   "V", "PG", "XOM", "MA", "HD", "CVX", "MRK", "PFE", "ABBV", "KO"]
    else:
        custom = st.text_area("Tickers (comma-separated)", "AAPL,TSLA")
        tickers = [t.strip().upper() for t in custom.split(",")]
    
    if st.button("🚀 Run Screener", type="primary"):
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

with tab4:
    st.header("📈 Pattern Recognition & Price Predictions")
    
    pattern_ticker = st.text_input("Ticker for pattern analysis", "AAPL").upper()
    
    if st.button("🔍 Analyze Patterns", type="primary"):
        with st.spinner("Analyzing..."):
            result = analyze_stock(pattern_ticker, st.session_state.portfolio_size, st.session_state.risk_percent)
            
            if not result['error']:
                col1, col2 = st.columns(2)
                
                with col1:
                    st.subheader("📊 Chart Patterns Detected")
                    for pattern in result['patterns']:
                        if "Bullish" in pattern:
                            st.success(pattern)
                        elif "Bearish" in pattern:
                            st.error(pattern)
                        else:
                            st.info(pattern)
                
                with col2:
                    st.subheader("🔮 Price Prediction")
                    if result['prediction']:
                        pred = result['prediction']
                        st.metric(
                            "5-Day Forecast",
                            f"${pred['predicted_5day']:.2f}",
                            f"{pred['change_percent']:.2f}%"
                        )
                        st.write(f"**Current:** ${pred['current']:.2f}")
                        st.write(f"**Trend:** {pred['trend']}")
                        st.write(f"**Confidence:** {pred['confidence']}")
                    else:
                        st.info("Not enough data for prediction")
                
                st.markdown("### 📐 Advanced Technical Indicators")
                adv = result['advanced_indicators']
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.write("**Fibonacci Levels**")
                    st.write(f"23.6%: ${adv['fib_236']:.2f}")
                    st.write(f"38.2%: ${adv['fib_382']:.2f}")
                    st.write(f"50.0%: ${adv['fib_500']:.2f}")
                    st.write(f"61.8%: ${adv['fib_618']:.2f}")
                
                with col2:
                    st.write("**Stochastic Oscillator**")
                    st.write(f"K: {adv['stochastic_k']:.2f}")
                    st.write(f"D: {adv['stochastic_d']:.2f}")
                    if adv['stochastic_k'] > 80:
                        st.error("Overbought")
                    elif adv['stochastic_k'] < 20:
                        st.success("Oversold")
                    else:
                        st.info("Neutral")
                
                with col3:
                    st.write("**Trend Strength**")
                    st.write(f"ADX: {adv['adx']:.2f}")
                    if adv['adx'] > 25:
                        st.success("Strong Trend")
                    elif adv['adx'] > 20:
                        st.info("Moderate Trend")
                    else:
                        st.warning("Weak Trend")
                    
                    st.write(f"**OBV:** {adv['obv_trend']}")

with tab5:
    st.header("📐 Advanced Position Size Calculator")
    
    st.write("Calculate optimal position size using different methods")
    
    calc_ticker = st.text_input("Ticker", "AAPL").upper()
    
    if st.button("💰 Calculate Position", type="primary"):
        with st.spinner("Calculating..."):
            result = analyze_stock(calc_ticker, st.session_state.portfolio_size, st.session_state.risk_percent)
            
            if not result['error'] and st.session_state.portfolio_size > 0:
                st.success(f"Position sizing for {calc_ticker} @ ${result['price']}")
                
                positions = result['position_sizes']
                
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.metric("Fixed % Method", f"{positions['fixed_percent']} shares")
                    st.write("**Risk:** 2% of portfolio")
                    st.write("**Stop Loss:** 10%")
                    st.info(f"Position Value: ${positions['fixed_percent'] * result['price']:.2f}")
                
                with col2:
                    st.metric("Volatility-Based", f"{positions['volatility_based']} shares")
                    st.write(f"**Volatility:** {result['volatility']:.1f}%")
                    st.write("Adjusts for stock volatility")
                    st.info(f"Position Value: ${positions['volatility_based'] * result['price']:.2f}")
                
                with col3:
                    st.metric("Kelly Criterion", f"{positions['kelly']} shares")
                    st.write("**Win Rate:** 55%")
                    st.write("**Risk/Reward:** 1.5:1")
                    st.info(f"Position Value: ${positions['kelly'] * result['price']:.2f}")
                
                st.markdown("---")
                st.markdown("### 📊 Recommendation")
                
                avg_shares = int(np.mean([positions['fixed_percent'], positions['volatility_based'], positions['kelly']]))
                st.success(f"**Recommended Position:** {avg_shares} shares (${avg_shares * result['price']:.2f})")
                
                st.write("**Risk Management:**")
                st.write(f"- Stop Loss: ${result['sl1']}")
                st.write(f"- Take Profit 1: ${result['tp1']}")
                st.write(f"- Max Loss: ${result['risk_amount']:.2f} ({st.session_state.risk_percent}% of portfolio)")
                
            elif st.session_state.portfolio_size == 0:
                st.warning("Please set your portfolio size in the sidebar first!")
            else:
                st.error("Unable to calculate positions")

with tab6:
    st.header("💰 Fundamental Analysis")
    
    fund_ticker = st.text_input("Ticker for fundamentals", "AAPL").upper()
    
    if st.button("📊 Get Fundamentals", type="primary"):
        with st.spinner("Loading fundamentals..."):
            fundamentals = get_fundamental_data(fund_ticker)
            
            if fundamentals:
                st.success(f"Fundamental data for {fund_ticker}")
                
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.markdown("### 💵 Valuation Metrics")
                    st.write(f"**P/E Ratio:** {fundamentals['pe_ratio']}")
                    st.write(f"**Forward P/E:** {fundamentals['forward_pe']}")
                    st.write(f"**P/B Ratio:** {fundamentals['pb_ratio']}")
                    st.write(f"**PEG Ratio:** {fundamentals['peg_ratio']}")
                
                with col2:
                    st.markdown("### 📈 Growth & Profitability")
                    st.write(f"**Revenue Growth:** {fundamentals['revenue_growth']}")
                    st.write(f"**Earnings Growth:** {fundamentals['earnings_growth']}")
                    st.write(f"**Profit Margin:** {fundamentals['profit_margin']}")
                    st.write(f"**ROE:** {fundamentals['roe']}")
                
                with col3:
                    st.markdown("### 🏦 Financial Health")
                    st.write(f"**Debt/Equity:** {fundamentals['debt_to_equity']}")
                    st.write(f"**Current Ratio:** {fundamentals['current_ratio']}")
                    st.write(f"**Dividend Yield:** {fundamentals['dividend_yield']}")
                
                st.markdown("---")
                st.markdown("### 📝 Analysis Summary")
                
                # Simple scoring
                fund_score = 0
                notes = []
                
                if isinstance(fundamentals['pe_ratio'], (int, float)) and fundamentals['pe_ratio'] < 25:
                    fund_score += 1
                    notes.append("✅ Reasonable P/E ratio")
                
                if isinstance(fundamentals['revenue_growth'], (int, float)) and fundamentals['revenue_growth'] > 0.1:
                    fund_score += 1
                    notes.append("✅ Strong revenue growth")
                
                if isinstance(fundamentals['debt_to_equity'], (int, float)) and fundamentals['debt_to_equity'] < 100:
                    fund_score += 1
                    notes.append("✅ Healthy debt levels")
                
                if isinstance(fundamentals['roe'], (int, float)) and fundamentals['roe'] > 0.15:
                    fund_score += 1
                    notes.append("✅ Strong return on equity")
                
                if fund_score >= 3:
                    st.success(f"**Fundamental Score:** {fund_score}/4 - Strong fundamentals")
                elif fund_score >= 2:
                    st.info(f"**Fundamental Score:** {fund_score}/4 - Moderate fundamentals")
                else:
                    st.warning(f"**Fundamental Score:** {fund_score}/4 - Weak fundamentals")
                
                for note in notes:
                    st.write(note)
            else:
                st.error("Unable to load fundamental data")

with tab7:
    st.header("🔙 Strategy Backtesting")
    
    col1, col2 = st.columns([2, 1])
    with col1:
        backtest_ticker = st.text_input("Ticker", "AAPL").upper()
    with col2:
        years = st.selectbox("Years", [1, 2, 3, 5], index=1)
    
    if st.button("🔬 Run Backtest", type="primary"):
        with st.spinner(f"Backtesting {backtest_ticker}..."):
            results = backtest_strategy(backtest_ticker, years)
            
            if results:
                st.success("Backtest Complete!")
                
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
                    name='Cumulative P&L',
                    line=dict(color='green', width=2)
                ))
                fig.update_layout(
                    title="Cumulative Returns",
                    xaxis_title="Date",
                    yaxis_title="Cumulative P&L %",
                    template='plotly_white'
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.error("Not enough data")

with tab8:
    st.header("💎 Buy Signals Summary")
    
    if st.session_state.analyzed_stocks:
        buy_signals = [s for s in st.session_state.analyzed_stocks if "BUY" in s.get("verdict", "") and not s.get("error", False)]
        buy_signals_sorted = sorted(buy_signals, key=lambda x: x["score"], reverse=True)
        
        if buy_signals_sorted:
            st.success(f"Found {len(buy_signals_sorted)} buy signals")
            
            df = pd.DataFrame(buy_signals_sorted)
            df = df[["ticker", "company", "price", "score", "verdict", "tp1", "sl1", "shares"]]
            df.columns = ["Ticker", "Company", "Price", "Score", "Verdict", "TP1", "SL1", "Shares"]
            
            st.dataframe(df, use_container_width=True, hide_index=True)
            
            csv = df.to_csv(index=False)
            st.download_button(
                "📥 Download CSV",
                csv,
                f"buy_signals_{datetime.now().strftime('%Y%m%d')}.csv",
                "text/csv"
            )
            
            for stock in buy_signals_sorted[:5]:
                with st.expander(f"{stock['ticker']} - {stock['verdict']} (Score: {stock['score']})"):
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Price", f"${stock['price']}")
                        st.write(f"**RSI:** {stock['rsi']}")
                    with col2:
                        st.write(f"**TP1:** ${stock['tp1']}")
                        st.write(f"**SL1:** ${stock['sl1']}")
                    with col3:
                        st.write(f"**Shares:** {stock['shares']}")
                        st.write(f"**Risk:** ${stock['risk_amount']}")
        else:
            st.info("No buy signals yet")
        
        if st.button("🗑️ Clear"):
            st.session_state.analyzed_stocks = []
            st.rerun()
    else:
        st.info("Analyze stocks to see signals")

# Footer
st.sidebar.markdown("---")
st.sidebar.markdown("### 📊 Pro Features")
st.sidebar.markdown("""
✅ Real-time Market Data  
✅ Pattern Recognition  
✅ Price Predictions  
✅ Advanced Indicators  
✅ Fundamental Analysis  
✅ Position Calculator  
✅ Strategy Backtesting  
✅ Auto-Refresh Mode
""")
