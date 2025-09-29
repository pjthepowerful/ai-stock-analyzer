import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import numpy as np
import time

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
st.sidebar.markdown(f"**Max Risk:** ${st.session_state.portfolio_size * (st.session_state.risk_percent / 100):.2f}")

st.sidebar.markdown("---")
st.sidebar.header("⭐ Watchlist")

new_ticker = st.sidebar.text_input("Add to Watchlist", "", key="add_watchlist_input").upper()
if st.sidebar.button("➕ Add", key="add_watchlist_btn") and new_ticker:
    if new_ticker not in st.session_state.favorites:
        st.session_state.favorites.append(new_ticker)
        st.sidebar.success(f"Added {new_ticker}!")
        st.rerun()

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
tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9 = st.tabs([
    "🌍 Market Overview",
    "📊 Analysis",
    "🎯 Watchlist", 
    "🔍 Screener",
    "📈 Patterns",
    "📐 Position Calc",
    "💰 Fundamentals",
    "🔙 Backtest",
    "💎 Buy Signals"
])

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
            insights.append("✅ Low volat
