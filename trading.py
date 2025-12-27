import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import warnings
import time
warnings.filterwarnings('ignore')

# Page configuration
st.set_page_config(
    page_title="Professional Swing Trading System",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Enhanced Custom CSS
st.markdown("""
<style>
    .stApp {
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
    }
    h1, h2, h3 {
        color: #ffffff !important;
        font-family: 'Inter', 'Segoe UI', sans-serif;
        font-weight: 600;
    }
    .stButton > button {
        background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
        color: white;
        border: none;
        border-radius: 8px;
        padding: 0.6rem 1.5rem;
        font-weight: 600;
        transition: all 0.3s;
        box-shadow: 0 4px 15px rgba(59, 130, 246, 0.4);
    }
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(59, 130, 246, 0.6);
    }
    .setup-card {
        background: rgba(255, 255, 255, 0.05);
        padding: 1.5rem;
        border-radius: 12px;
        border-left: 4px solid;
        margin: 1rem 0;
        backdrop-filter: blur(10px);
    }
    .strong-buy {
        border-color: #22c55e;
        background: rgba(34, 197, 94, 0.1);
    }
    .buy {
        border-color: #3b82f6;
        background: rgba(59, 130, 246, 0.1);
    }
    .caution {
        border-color: #eab308;
        background: rgba(234, 179, 8, 0.1);
    }
    .metric-box {
        background: rgba(255, 255, 255, 0.05);
        padding: 1rem;
        border-radius: 10px;
        border: 1px solid rgba(255, 255, 255, 0.1);
        text-align: center;
    }
    .strategy-tag {
        display: inline-block;
        padding: 0.25rem 0.75rem;
        border-radius: 20px;
        font-size: 0.85rem;
        font-weight: 600;
        margin: 0.25rem;
    }
    .tag-trend {
        background: rgba(59, 130, 246, 0.2);
        color: #60a5fa;
        border: 1px solid #3b82f6;
    }
    .tag-pullback {
        background: rgba(34, 197, 94, 0.2);
        color: #4ade80;
        border: 1px solid #22c55e;
    }
    .tag-breakout {
        background: rgba(168, 85, 247, 0.2);
        color: #c084fc;
        border: 1px solid #a855f7;
    }
    .tag-reversal {
        background: rgba(234, 179, 8, 0.2);
        color: #fde047;
        border: 1px solid #eab308;
    }
</style>
""", unsafe_allow_html=True)

# Nasdaq 100 Components (Top liquid stocks)
NASDAQ_100 = [
    'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META', 'TSLA', 'AVGO', 'COST', 'ASML',
    'NFLX', 'AMD', 'PEP', 'ADBE', 'CSCO', 'TMUS', 'CMCSA', 'INTC', 'TXN', 'QCOM',
    'INTU', 'AMGN', 'AMAT', 'HON', 'SBUX', 'ISRG', 'BKNG', 'VRTX', 'ADI', 'GILD',
    'PANW', 'ADP', 'LRCX', 'MU', 'REGN', 'MDLZ', 'MELI', 'PYPL', 'SNPS', 'KLAC',
    'CDNS', 'MAR', 'CSX', 'CRWD', 'MRVL', 'ORLY', 'FTNT', 'ADSK', 'ABNB', 'DASH',
    'NXPI', 'WDAY', 'MNST', 'CHTR', 'CPRT', 'AEP', 'PAYX', 'ROST', 'ODFL', 'FAST',
    'PCAR', 'KDP', 'EA', 'KHC', 'VRSK', 'CTSH', 'GEHC', 'DXCM', 'LULU', 'EXC',
    'CEG', 'IDXX', 'XEL', 'CCEP', 'TTWO', 'ANSS', 'ON', 'ZS', 'FANG', 'CTAS',
    'CDW', 'BIIB', 'WBD', 'GFS', 'ILMN', 'MDB', 'MRNA', 'DLTR', 'ARM', 'SMCI'
]

# Session state initialization
if 'scan_results' not in st.session_state:
    st.session_state.scan_results = None
if 'account_size' not in st.session_state:
    st.session_state.account_size = 100000
if 'risk_per_trade' not in st.session_state:
    st.session_state.risk_per_trade = 1.0
if 'last_scan_time' not in st.session_state:
    st.session_state.last_scan_time = None
if 'page' not in st.session_state:
    st.session_state.page = 'Scanner'

# ===================== CORE FUNCTIONS =====================

@st.cache_data(ttl=300)
def get_stock_data_optimized(ticker, period='3mo', interval='1d'):
    """Optimized data fetching with retry logic"""
    max_retries = 2
    for attempt in range(max_retries):
        try:
            if attempt > 0:
                time.sleep(1)
            
            stock = yf.Ticker(ticker)
            hist = stock.history(period=period, interval=interval)
            
            if not hist.empty:
                try:
                    info = stock.info
                except:
                    info = {'symbol': ticker, 'volume': int(hist['Volume'].iloc[-1]) if len(hist) > 0 else 0}
                return hist, info
        except Exception as e:
            if attempt < max_retries - 1:
                continue
            return pd.DataFrame(), {}
    return pd.DataFrame(), {}

@st.cache_data(ttl=300)
def get_market_regime():
    """Determine overall market trend using QQQ"""
    try:
        qqq = yf.Ticker('QQQ')
        hist = qqq.history(period='1y')
        
        if len(hist) < 200:
            return 'NEUTRAL', 0
        
        current_price = hist['Close'].iloc[-1]
        sma_200 = hist['Close'].rolling(window=200).mean().iloc[-1]
        sma_50 = hist['Close'].rolling(window=50).mean().iloc[-1]
        
        # Calculate strength
        above_200 = (current_price - sma_200) / sma_200 * 100
        
        if current_price > sma_50 > sma_200:
            regime = 'BULLISH'
        elif current_price > sma_200:
            regime = 'NEUTRAL_BULLISH'
        elif current_price < sma_200:
            regime = 'BEARISH'
        else:
            regime = 'NEUTRAL'
        
        return regime, above_200
    except:
        return 'NEUTRAL', 0

def calculate_swing_indicators(df):
    """Calculate technical indicators optimized for swing trading"""
    if df.empty or len(df) < 2:
        return df
    
    # Essential moving averages
    df['EMA_9'] = df['Close'].ewm(span=9, adjust=False).mean()
    df['EMA_20'] = df['Close'].ewm(span=20, adjust=False).mean()
    df['SMA_50'] = df['Close'].rolling(window=50).mean()
    df['SMA_200'] = df['Close'].rolling(window=200).mean()
    
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
    df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    df['MACD_Histogram'] = df['MACD'] - df['MACD_Signal']
    
    # ATR for volatility
    high_low = df['High'] - df['Low']
    high_close = np.abs(df['High'] - df['Close'].shift())
    low_close = np.abs(df['Low'] - df['Close'].shift())
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = np.max(ranges, axis=1)
    df['ATR'] = true_range.rolling(14).mean()
    
    # Volume analysis
    df['Volume_SMA_20'] = df['Volume'].rolling(window=20).mean()
    df['Volume_Ratio'] = df['Volume'] / df['Volume_SMA_20']
    
    # Relative strength (vs QQQ)
    try:
        qqq = yf.Ticker('QQQ').history(period='3mo')
        if len(qqq) >= len(df):
            qqq_return = (qqq['Close'].iloc[-1] - qqq['Close'].iloc[-20]) / qqq['Close'].iloc[-20]
            stock_return = (df['Close'].iloc[-1] - df['Close'].iloc[-20]) / df['Close'].iloc[-20]
            df['Relative_Strength'] = stock_return - qqq_return
        else:
            df['Relative_Strength'] = 0
    except:
        df['Relative_Strength'] = 0
    
    # Price distance from EMAs
    df['Distance_EMA20'] = ((df['Close'] - df['EMA_20']) / df['EMA_20']) * 100
    df['Distance_SMA50'] = ((df['Close'] - df['SMA_50']) / df['SMA_50']) * 100
    
    return df

def identify_setup_type(df, info):
    """
    Identify the specific swing trading setup
    Returns: (setup_type, quality_score, entry_price, stop_loss, target, reasoning)
    """
    if len(df) < 60:
        return None, 0, 0, 0, 0, "Insufficient data"
    
    current_price = df['Close'].iloc[-1]
    prev_close = df['Close'].iloc[-2]
    ema_20 = df['EMA_20'].iloc[-1]
    ema_9 = df['EMA_9'].iloc[-1]
    sma_50 = df['SMA_50'].iloc[-1]
    sma_200 = df['SMA_200'].iloc[-1]
    rsi = df['RSI'].iloc[-1]
    atr = df['ATR'].iloc[-1]
    volume_ratio = df['Volume_Ratio'].iloc[-1]
    macd_hist = df['MACD_Histogram'].iloc[-1]
    
    setups = []
    
    # Prerequisite: Strong trend structure
    uptrend = current_price > sma_50 > sma_200 if pd.notna(sma_200) else current_price > sma_50
    
    if not uptrend:
        return None, 0, 0, 0, 0, "Not in uptrend structure"
    
    # 1. INSTITUTIONAL PULLBACK TO 20 EMA (High probability)
    if pd.notna(ema_20):
        distance_to_ema20 = abs(current_price - ema_20) / ema_20 * 100
        
        if (distance_to_ema20 < 2.5 and  # Near EMA
            current_price > ema_20 and  # Above support
            rsi > 40 and rsi < 60 and  # Not oversold or overbought
            macd_hist > 0):  # Bullish momentum
            
            quality = 85
            if volume_ratio > 1.2:
                quality += 5
            if df['Close'].iloc[-3:].min() <= ema_20 <= df['High'].iloc[-3:].max():
                quality += 5  # Perfect touch
            
            entry = current_price
            stop = ema_20 - (atr * 0.5)
            risk = entry - stop
            target = entry + (risk * 3)  # 3R
            
            setups.append({
                'type': 'EMA_20_PULLBACK',
                'quality': quality,
                'entry': entry,
                'stop': stop,
                'target': target,
                'reason': f'Pullback to 20 EMA in uptrend. RSI: {rsi:.0f}, Vol: {volume_ratio:.1f}x'
            })
    
    # 2. INSTITUTIONAL PULLBACK TO 50 SMA (Medium-High probability)
    if pd.notna(sma_50):
        distance_to_sma50 = abs(current_price - sma_50) / sma_50 * 100
        
        if (distance_to_sma50 < 3.0 and
            current_price > sma_50 and
            rsi > 35 and rsi < 55 and
            sma_50 > sma_200):
            
            quality = 75
            if volume_ratio > 1.0:
                quality += 5
            if df['Close'].iloc[-5:].min() <= sma_50:
                quality += 5
            
            entry = current_price
            stop = sma_50 - (atr * 0.75)
            risk = entry - stop
            target = entry + (risk * 2.5)
            
            setups.append({
                'type': 'SMA_50_PULLBACK',
                'quality': quality,
                'entry': entry,
                'stop': stop,
                'target': target,
                'reason': f'Pullback to 50 SMA support. RSI: {rsi:.0f}'
            })
    
    # 3. TIGHT CONSOLIDATION BREAKOUT (High probability)
    recent_high = df['High'].iloc[-20:].max()
    distance_from_high = (recent_high - current_price) / current_price * 100
    
    if distance_from_high < 3:  # Within 3% of recent high
        # Check for tight consolidation
        last_10_range = (df['High'].iloc[-10:].max() - df['Low'].iloc[-10:].min()) / current_price * 100
        
        if (last_10_range < 8 and  # Tight range
            current_price > ema_20 and
            volume_ratio > 1.3 and  # Volume expansion
            rsi > 50 and rsi < 70):
            
            quality = 80
            if current_price > recent_high:
                quality += 10  # Breakout confirmed
            
            entry = current_price
            stop = df['Low'].iloc[-10:].min() - (atr * 0.3)
            risk = entry - stop
            target = entry + (risk * 3.5)
            
            setups.append({
                'type': 'CONSOLIDATION_BREAKOUT',
                'quality': quality,
                'entry': entry,
                'stop': stop,
                'target': target,
                'reason': f'Tight consolidation near highs. Range: {last_10_range:.1f}%, Vol: {volume_ratio:.1f}x'
            })
    
    # 4. SUPPORT BOUNCE IN STRONG STOCK (Medium probability)
    # Find recent swing low
    recent_low = df['Low'].iloc[-20:].min()
    distance_from_low = (current_price - recent_low) / recent_low * 100
    
    if (distance_from_low < 5 and  # Near recent low
        current_price > ema_9 and  # Bouncing back
        rsi > 30 and rsi < 50 and  # Recovering from oversold
        df['Relative_Strength'].iloc[-1] > 0):  # Outperforming market
        
        quality = 70
        if volume_ratio > 1.5:
            quality += 5
        if current_price > prev_close:
            quality += 5
        
        entry = current_price
        stop = recent_low - (atr * 0.5)
        risk = entry - stop
        target = entry + (risk * 2.5)
        
        setups.append({
            'type': 'SUPPORT_BOUNCE',
            'quality': quality,
            'entry': entry,
            'stop': stop,
            'target': target,
            'reason': f'Bounce from support. RS > Market, RSI: {rsi:.0f}'
        })
    
    # 5. MEAN REVERSION BOUNCE (Lower probability, only in very strong trends)
    if (current_price > sma_50 and sma_50 > sma_200 and
        rsi < 35 and rsi > 25 and  # Oversold but not extreme
        macd_hist < 0 and df['MACD_Histogram'].iloc[-2] < df['MACD_Histogram'].iloc[-1]):  # MACD turning up
        
        quality = 65
        if df['Relative_Strength'].iloc[-1] > 0:
            quality += 5
        
        entry = current_price
        stop = current_price - (atr * 1.5)
        risk = entry - stop
        target = ema_20  # Conservative target
        
        setups.append({
            'type': 'MEAN_REVERSION',
            'quality': quality,
            'entry': entry,
            'stop': stop,
            'target': target,
            'reason': f'Oversold bounce in uptrend. RSI: {rsi:.0f}, MACD turning'
        })
    
    # Return best setup
    if not setups:
        return None, 0, 0, 0, 0, "No valid setup identified"
    
    best_setup = max(setups, key=lambda x: x['quality'])
    
    return (
        best_setup['type'],
        best_setup['quality'],
        best_setup['entry'],
        best_setup['stop'],
        best_setup['target'],
        best_setup['reason']
    )

def calculate_position_size(account_size, risk_percent, entry, stop):
    """Calculate position size based on fixed risk"""
    if entry <= stop or stop <= 0:
        return 0, 0
    
    risk_amount = account_size * (risk_percent / 100)
    risk_per_share = entry - stop
    shares = int(risk_amount / risk_per_share)
    position_value = shares * entry
    
    return shares, position_value

def scan_nasdaq_for_setups(timeframe='1d', top_n=20, min_quality=65):
    """
    Scan Nasdaq 100 for high-quality swing trading setups
    """
    market_regime, market_strength = get_market_regime()
    
    # Only trade in bullish markets
    if market_regime not in ['BULLISH', 'NEUTRAL_BULLISH']:
        return pd.DataFrame(), market_regime, market_strength
    
    results = []
    total_stocks = len(NASDAQ_100)
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for idx, ticker in enumerate(NASDAQ_100):
        try:
            status_text.text(f"Scanning {ticker}... ({idx + 1}/{total_stocks})")
            
            # Rate limiting
            if idx > 0 and idx % 10 == 0:
                time.sleep(1)
            
            period = '3mo' if timeframe == '1d' else '1mo'
            hist, info = get_stock_data_optimized(ticker, period=period, interval=timeframe)
            
            if hist.empty or len(hist) < 60:
                continue
            
            # Skip low liquidity stocks
            avg_volume = info.get('averageVolume', 0)
            if avg_volume < 500000:  # Minimum 500K average volume
                continue
            
            # Calculate indicators
            hist = calculate_swing_indicators(hist)
            
            # Identify setup
            setup_type, quality, entry, stop, target, reason = identify_setup_type(hist, info)
            
            if setup_type and quality >= min_quality:
                # Calculate metrics
                risk_per_share = entry - stop
                reward = target - entry
                reward_risk = reward / risk_per_share if risk_per_share > 0 else 0
                
                # Position sizing
                shares, position_value = calculate_position_size(
                    st.session_state.account_size,
                    st.session_state.risk_per_trade,
                    entry,
                    stop
                )
                
                results.append({
                    'Ticker': ticker,
                    'Setup': setup_type.replace('_', ' ').title(),
                    'Quality': quality,
                    'Entry': entry,
                    'Stop': stop,
                    'Target': target,
                    'Risk_$': risk_per_share,
                    'Reward_$': reward,
                    'R_R_Ratio': reward_risk,
                    'Shares': shares,
                    'Position_$': position_value,
                    'RSI': hist['RSI'].iloc[-1],
                    'Volume_Ratio': hist['Volume_Ratio'].iloc[-1],
                    'Reason': reason,
                    'Price': hist['Close'].iloc[-1],
                    'EMA_20': hist['EMA_20'].iloc[-1],
                    'SMA_50': hist['SMA_50'].iloc[-1],
                })
            
            progress_bar.progress((idx + 1) / total_stocks)
            
        except Exception as e:
            continue
    
    progress_bar.empty()
    status_text.empty()
    
    if results:
        df = pd.DataFrame(results)
        # Sort by quality score first, then R:R ratio
        df = df.sort_values(by=['Quality', 'R_R_Ratio'], ascending=[False, False]).reset_index(drop=True)
        return df.head(top_n), market_regime, market_strength
    
    return pd.DataFrame(), market_regime, market_strength

def create_setup_chart(ticker, timeframe='1d'):
    """Create detailed chart for a specific setup"""
    period = '6mo' if timeframe == '1d' else '2mo'
    hist, info = get_stock_data_optimized(ticker, period=period, interval=timeframe)
    
    if hist.empty:
        return None
    
    hist = calculate_swing_indicators(hist)
    setup_type, quality, entry, stop, target, reason = identify_setup_type(hist, info)
    
    fig = make_subplots(
        rows=3, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.6, 0.2, 0.2],
        subplot_titles=(f'{ticker} - {setup_type.replace("_", " ").title() if setup_type else "Analysis"}', 'RSI', 'Volume')
    )
    
    # Candlestick
    fig.add_trace(go.Candlestick(
        x=hist.index,
        open=hist['Open'],
        high=hist['High'],
        low=hist['Low'],
        close=hist['Close'],
        name='Price',
        increasing_line_color='#22c55e',
        decreasing_line_color='#ef4444'
    ), row=1, col=1)
    
    # EMAs and SMAs
    fig.add_trace(go.Scatter(x=hist.index, y=hist['EMA_9'], name='EMA 9', 
                            line=dict(color='#fbbf24', width=1)), row=1, col=1)
    fig.add_trace(go.Scatter(x=hist.index, y=hist['EMA_20'], name='EMA 20', 
                            line=dict(color='#3b82f6', width=2)), row=1, col=1)
    fig.add_trace(go.Scatter(x=hist.index, y=hist['SMA_50'], name='SMA 50', 
                            line=dict(color='#8b5cf6', width=2)), row=1, col=1)
    if pd.notna(hist['SMA_200'].iloc[-1]):
        fig.add_trace(go.Scatter(x=hist.index, y=hist['SMA_200'], name='SMA 200', 
                                line=dict(color='#ef4444', width=2)), row=1, col=1)
    
    # Entry, Stop, Target lines
    if entry > 0:
        fig.add_hline(y=entry, line_dash="dash", line_color="#3b82f6", 
                     annotation_text=f"Entry: ${entry:.2f}", row=1, col=1)
        fig.add_hline(y=stop, line_dash="dash", line_color="#ef4444", 
                     annotation_text=f"Stop: ${stop:.2f}", row=1, col=1)
        fig.add_hline(y=target, line_dash="dash", line_color="#22c55e", 
                     annotation_text=f"Target: ${target:.2f}", row=1, col=1)
    
    # RSI
    fig.add_trace(go.Scatter(x=hist.index, y=hist['RSI'], name='RSI', 
                            line=dict(color='#a855f7', width=2)), row=2, col=1)
    fig.add_hline(y=70, line_dash="dot", line_color="red", opacity=0.5, row=2, col=1)
    fig.add_hline(y=30, line_dash="dot", line_color="green", opacity=0.5, row=2, col=1)
    
    # Volume
    colors = ['#22c55e' if hist['Close'].iloc[i] > hist['Open'].iloc[i] else '#ef4444' 
              for i in range(len(hist))]
    fig.add_trace(go.Bar(x=hist.index, y=hist['Volume'], name='Volume', 
                        marker_color=colors), row=3, col=1)
    
    fig.update_layout(
        height=800,
        template='plotly_dark',
        showlegend=True,
        hovermode='x unified',
        xaxis_rangeslider_visible=False
    )
    
    return fig

# ===================== SIDEBAR =====================

with st.sidebar:
    st.markdown("# 📊 Pro Swing Trader")
    st.markdown("### Institutional Grade System")
    st.markdown("---")
    
    # Navigation
    st.markdown("#### Navigation")
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("🔍 Scanner", use_container_width=True):
            st.session_state.page = 'Scanner'
            st.rerun()
    with col2:
        if st.button("📊 Analyze", use_container_width=True):
            st.session_state.page = 'Individual'
            st.rerun()
    with col3:
        if st.button("💰 Sizer", use_container_width=True):
            st.session_state.page = 'Position Sizer'
            st.rerun()
    
    st.markdown("---")
    
    st.markdown("#### Account Settings")
    st.session_state.account_size = st.number_input(
        "Account Size ($)", 
        min_value=10000, 
        value=st.session_state.account_size, 
        step=10000
    )
    
    st.session_state.risk_per_trade = st.slider(
        "Risk Per Trade (%)", 
        min_value=0.5, 
        max_value=2.0, 
        value=st.session_state.risk_per_trade, 
        step=0.1
    )
    
    st.markdown("---")
    
    # Scanner settings - initialize with defaults
    scan_timeframe = '1d'
    min_quality_score = 70
    max_results = 20
    
    # Show scanner settings only on scanner page
    if st.session_state.page == 'Scanner':
        st.markdown("#### Scanner Settings")
        scan_timeframe = st.selectbox("Timeframe", ["1d", "1h"], index=0)
        min_quality_score = st.slider("Min Quality Score", 60, 90, 70, 5)
        max_results = st.slider("Max Results", 10, 30, 20, 5)
        
        st.markdown("---")
    
    st.markdown("#### Strategy Types")
    strategies = [
        ("✅ EMA 20 Pullback", "Institutional support"),
        ("✅ SMA 50 Pullback", "Major support level"),
        ("✅ Consolidation Breakout", "High momentum"),
        ("✅ Support Bounce", "Strong stocks only"),
        ("✅ Mean Reversion", "Oversold recovery")
    ]
    for name, desc in strategies:
        st.markdown(f"**{name}**")
        st.caption(desc)
    
    st.markdown("---")
    st.caption("Built for consistent profits")
    st.caption("Not financial advice")

# ===================== MAIN APP =====================

page = st.session_state.page

# ==================== SCANNER PAGE ====================
if page == 'Scanner':
    st.title("📊 Professional Swing Trading Scanner")

    # Market Status
    market_regime, market_strength = get_market_regime()
    col1, col2, col3 = st.columns(3)

    with col1:
        regime_color = {
            'BULLISH': '🟢',
            'NEUTRAL_BULLISH': '🟡',
            'BEARISH': '🔴',
            'NEUTRAL': '⚪'
        }
        st.metric("Market Regime", f"{regime_color.get(market_regime, '⚪')} {market_regime}")

    with col2:
        st.metric("QQQ vs 200 SMA", f"{market_strength:+.2f}%")

    with col3:
        risk_amount = st.session_state.account_size * (st.session_state.risk_per_trade / 100)
        st.metric("Risk Per Trade", f"${risk_amount:,.0f}")

    if market_regime in ['BEARISH']:
        st.warning("⚠️ Market in bearish regime. Scanner disabled. Cash is a position.")
        st.stop()

    st.markdown("---")

    # Scan Button
    col1, col2, col3 = st.columns([2, 2, 2])

    with col2:
        if st.button("🚀 SCAN NASDAQ 100", type="primary", use_container_width=True):
            with st.spinner("Scanning Nasdaq 100 for high-quality setups..."):
                results_df, regime, strength = scan_nasdaq_for_setups(
                    timeframe=scan_timeframe,
                    top_n=max_results,
                    min_quality=min_quality_score
                )
                st.session_state.scan_results = results_df
                st.session_state.last_scan_time = datetime.now()
            
            if not results_df.empty:
                st.success(f"✅ Found {len(results_df)} high-quality setups!")
            else:
                st.info("No setups meeting criteria. Market may be extended or choppy.")

    # Display scan results
    if st.session_state.scan_results is not None and not st.session_state.scan_results.empty:
        df = st.session_state.scan_results
        
        if st.session_state.last_scan_time:
            st.caption(f"Last scan: {st.session_state.last_scan_time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        st.markdown("### 🎯 Top Trading Setups")
        
        # Display each setup
        for idx, row in df.iterrows():
            # Determine card style
            if row['Quality'] >= 80:
                card_class = "strong-buy"
                badge = "🔥 STRONG"
            elif row['Quality'] >= 70:
                card_class = "buy"
                badge = "✅ GOOD"
            else:
                card_class = "caution"
                badge = "⚠️ MONITOR"
            
            # Setup tags
            setup_tags = {
                'Ema 20 Pullback': 'tag-pullback',
                'Sma 50 Pullback': 'tag-pullback',
                'Consolidation Breakout': 'tag-breakout',
                'Support Bounce': 'tag-trend',
                'Mean Reversion': 'tag-reversal'
            }
            tag_class = setup_tags.get(row['Setup'], 'tag-trend')
            
            st.markdown(f"""
            <div class="setup-card {card_class}">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <div>
                        <h2 style="margin: 0;">{row['Ticker']} - {badge}</h2>
                        <span class="strategy-tag {tag_class}">{row['Setup']}</span>
                    </div>
                    <div style="text-align: right;">
                        <div style="font-size: 2rem; font-weight: bold;">{row['Quality']}/100</div>
                        <div style="color: #888;">Quality Score</div>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            # Metrics row
            col1, col2, col3, col4, col5, col6 = st.columns(6)
            
            with col1:
                st.metric("Entry", f"${row['Entry']:.2f}")
            with col2:
                st.metric("Stop Loss", f"${row['Stop']:.2f}")
            with col3:
                st.metric("Target", f"${row['Target']:.2f}")
            with col4:
                st.metric("R:R Ratio", f"{row['R_R_Ratio']:.1f}R")
            with col5:
                st.metric("Position Size", f"{row['Shares']:,} shares")
            with col6:
                st.metric("Capital", f"${row['Position_$']:,.0f}")
            
            # Additional info
            col1, col2 = st.columns([2, 1])
            
            with col1:
                st.caption(f"**Analysis:** {row['Reason']}")
                risk_pct = (row['Risk_$'] / row['Entry']) * 100
                reward_pct = (row['Reward_$'] / row['Entry']) * 100
                st.caption(f"Risk: ${row['Risk_$']:.2f} ({risk_pct:.1f}%) | Reward: ${row['Reward_$']:.2f} ({reward_pct:.1f}%)")
            
            with col2:
                if st.button(f"📊 View Chart", key=f"chart_{row['Ticker']}", use_container_width=True):
                    chart_fig = create_setup_chart(row['Ticker'], scan_timeframe)
                    if chart_fig:
                        st.plotly_chart(chart_fig, use_container_width=True)
            
            st.markdown("---")
        
        # Summary table
        with st.expander("📋 Full Results Table", expanded=False):
            display_df = df[[
                'Ticker', 'Setup', 'Quality', 'Entry', 'Stop', 'Target', 
                'R_R_Ratio', 'Shares', 'Position_$', 'RSI', 'Volume_Ratio'
            ]].copy()
            
            st.dataframe(
                display_df.style.format({
                    'Entry': '${:.2f}',
                    'Stop': '${:.2f}',
                    'Target': '${:.2f}',
                    'R_R_Ratio': '{:.1f}R',
                    'Position_$': '${:,.0f}',
                    'RSI': '{:.0f}',
                    'Volume_Ratio': '{:.1f}x'
                }),
                use_container_width=True,
                height=400
            )
        
        # Download results
        csv = df.to_csv(index=False)
        st.download_button(
            label="📥 Download Results (CSV)",
            data=csv,
            file_name=f"swing_setups_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
            mime="text/csv",
            use_container_width=True
        )

    else:
        st.info("👆 Click 'SCAN NASDAQ 100' to find high-quality swing trading setups")
        
        st.markdown("### 📚 How This System Works")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("""
            **Strategy Philosophy:**
            - Only trade in bullish market environments
            - Focus on institutional-grade setups
            - Strict risk management: 0.5-1% per trade
            - Predefined entry, stop, and target for every trade
            - No subjective decisions
            
            **Setup Types (Prioritized):**
            1. **EMA 20 Pullback** - Highest probability
            2. **SMA 50 Pullback** - Major support
            3. **Consolidation Breakout** - Momentum plays
            4. **Support Bounce** - Strong stocks only
            5. **Mean Reversion** - Oversold recovery
            """)
        
        with col2:
            st.markdown("""
            **Quality Scoring:**
            - 85-100: Exceptional setups (rare)
            - 75-84: Strong probability plays
            - 65-74: Good setups with confirmation
            - Below 65: Filtered out
            
            **Risk Management:**
            - Fixed % risk per trade
            - Position size auto-calculated
            - Stop loss based on structure
            - Targets based on R:R ratio
            - Never risk more than defined amount
            
            **What Makes This Different:**
            - No curve-fitting or optimization
            - Proven institutional patterns
            - Filters for quality over quantity
            - Designed for consistency
            """)

# ==================== INDIVIDUAL STOCK ANALYSIS PAGE ====================
elif page == 'Individual':
    st.title("📊 Individual Stock Analysis")
    st.markdown("Deep dive analysis of any stock for swing trading setups")
    
    col1, col2, col3 = st.columns([3, 2, 1])
    with col1:
        ticker_input = st.text_input("Enter Stock Ticker", value="AAPL", placeholder="e.g., AAPL, TSLA, NVDA").upper()
    with col2:
        analysis_timeframe = st.selectbox("Timeframe", ["1d", "1h"], index=0, key="individual_tf")
    with col3:
        st.write("")
        st.write("")
        analyze_btn = st.button("🔍 Analyze", type="primary", use_container_width=True)
    
    if ticker_input:
        with st.spinner(f"Analyzing {ticker_input}..."):
            period = '6mo' if analysis_timeframe == '1d' else '2mo'
            hist, info = get_stock_data_optimized(ticker_input, period=period, interval=analysis_timeframe)
            
            if hist.empty or len(hist) < 60:
                st.error(f"❌ Unable to fetch sufficient data for {ticker_input}")
            else:
                # Calculate indicators
                hist = calculate_swing_indicators(hist)
                
                # Get setup analysis
                setup_type, quality, entry, stop, target, reason = identify_setup_type(hist, info)
                
                # Current metrics
                current_price = hist['Close'].iloc[-1]
                rsi = hist['RSI'].iloc[-1]
                volume_ratio = hist['Volume_Ratio'].iloc[-1]
                
                # Market regime
                market_regime, market_strength = get_market_regime()
                
                # Header metrics
                col1, col2, col3, col4, col5 = st.columns(5)
                
                with col1:
                    prev_close = hist['Close'].iloc[-2]
                    change_pct = ((current_price - prev_close) / prev_close) * 100
                    st.metric("Current Price", f"${current_price:.2f}", f"{change_pct:+.2f}%")
                
                with col2:
                    regime_color = {
                        'BULLISH': '🟢', 'NEUTRAL_BULLISH': '🟡',
                        'BEARISH': '🔴', 'NEUTRAL': '⚪'
                    }
                    st.metric("Market Regime", f"{regime_color.get(market_regime, '⚪')} {market_regime}")
                
                with col3:
                    st.metric("RSI", f"{rsi:.0f}")
                
                with col4:
                    st.metric("Volume", f"{volume_ratio:.1f}x avg")
                
                with col5:
                    avg_vol = info.get('averageVolume', 0)
                    st.metric("Avg Volume", f"{avg_vol/1e6:.1f}M" if avg_vol > 0 else "N/A")
                
                st.markdown("---")
                
                # Setup Analysis
                if setup_type and quality >= 60:
                    # Quality badge
                    if quality >= 80:
                        card_class = "strong-buy"
                        badge = "🔥 STRONG SETUP"
                    elif quality >= 70:
                        card_class = "buy"
                        badge = "✅ GOOD SETUP"
                    else:
                        card_class = "caution"
                        badge = "⚠️ FAIR SETUP"
                    
                    st.markdown(f"""
                    <div class="setup-card {card_class}">
                        <h2>{badge}</h2>
                        <h3>{setup_type.replace('_', ' ').title()}</h3>
                        <p><strong>Quality Score: {quality}/100</strong></p>
                        <p>{reason}</p>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # Trade Plan
                    st.markdown("### 📋 Trade Plan")
                    
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        st.markdown("**🟢 Entry Zone**")
                        st.metric("Entry Price", f"${entry:.2f}")
                        st.caption("Execute at or below this price")
                    
                    with col2:
                        st.markdown("**🔴 Stop Loss**")
                        st.metric("Stop Price", f"${stop:.2f}")
                        risk_pct = ((entry - stop) / entry) * 100
                        st.caption(f"Risk: {risk_pct:.1f}% from entry")
                    
                    with col3:
                        st.markdown("**🎯 Target**")
                        st.metric("Target Price", f"${target:.2f}")
                        reward_pct = ((target - entry) / entry) * 100
                        st.caption(f"Reward: {reward_pct:.1f}% from entry")
                    
                    # Position Sizing
                    st.markdown("---")
                    st.markdown("### 💰 Position Sizing")
                    
                    shares, position_value = calculate_position_size(
                        st.session_state.account_size,
                        st.session_state.risk_per_trade,
                        entry,
                        stop
                    )
                    
                    risk_amount = st.session_state.account_size * (st.session_state.risk_per_trade / 100)
                    potential_profit = shares * (target - entry)
                    reward_risk_ratio = (target - entry) / (entry - stop)
                    
                    col1, col2, col3, col4 = st.columns(4)
                    
                    with col1:
                        st.metric("Shares to Buy", f"{shares:,}")
                    with col2:
                        st.metric("Position Value", f"${position_value:,.0f}")
                    with col3:
                        st.metric("Risk Amount", f"${risk_amount:,.0f}")
                    with col4:
                        st.metric("R:R Ratio", f"{reward_risk_ratio:.1f}:1")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        st.metric("Potential Profit", f"${potential_profit:,.0f}")
                    with col2:
                        portfolio_pct = (position_value / st.session_state.account_size) * 100
                        st.metric("Portfolio %", f"{portfolio_pct:.1f}%")
                    
                else:
                    st.warning(f"⚠️ No high-quality setup identified for {ticker_input}")
                    st.info(f"**Reason:** {reason}")
                    st.markdown("**Suggestions:**")
                    st.markdown("- Wait for a pullback to EMA 20 or SMA 50")
                    st.markdown("- Look for consolidation near recent highs")
                    st.markdown("- Check if stock is in a confirmed uptrend")
                
                # Chart
                st.markdown("---")
                st.markdown("### 📈 Technical Chart")
                
                chart_fig = create_setup_chart(ticker_input, analysis_timeframe)
                if chart_fig:
                    st.plotly_chart(chart_fig, use_container_width=True)
                
                # Technical Details
                st.markdown("---")
                st.markdown("### 📊 Technical Details")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown("**Moving Averages**")
                    ema_20 = hist['EMA_20'].iloc[-1]
                    sma_50 = hist['SMA_50'].iloc[-1]
                    sma_200 = hist['SMA_200'].iloc[-1]
                    
                    st.text(f"EMA 20: ${ema_20:.2f} ({((current_price/ema_20-1)*100):+.1f}%)")
                    st.text(f"SMA 50: ${sma_50:.2f} ({((current_price/sma_50-1)*100):+.1f}%)")
                    if pd.notna(sma_200):
                        st.text(f"SMA 200: ${sma_200:.2f} ({((current_price/sma_200-1)*100):+.1f}%)")
                    
                    st.markdown("**Trend Structure**")
                    if current_price > sma_50 > sma_200:
                        st.success("✅ Strong uptrend (Price > 50 > 200)")
                    elif current_price > sma_50:
                        st.info("📊 Uptrend (Price > 50 SMA)")
                    else:
                        st.warning("⚠️ Not in uptrend")
                
                with col2:
                    st.markdown("**Momentum Indicators**")
                    macd = hist['MACD'].iloc[-1]
                    macd_signal = hist['MACD_Signal'].iloc[-1]
                    
                    st.text(f"RSI: {rsi:.1f}")
                    if rsi > 70:
                        st.caption("🔴 Overbought")
                    elif rsi < 30:
                        st.caption("🟢 Oversold")
                    else:
                        st.caption("🟡 Neutral")
                    
                    st.text(f"MACD: {macd:.2f}")
                    if macd > macd_signal:
                        st.caption("🟢 Bullish")
                    else:
                        st.caption("🔴 Bearish")
                    
                    st.markdown("**Volume Analysis**")
                    st.text(f"Vol Ratio: {volume_ratio:.1f}x")
                    if volume_ratio > 1.5:
                        st.caption("🔥 High volume")
                    elif volume_ratio > 1.0:
                        st.caption("✅ Above average")
                    else:
                        st.caption("⚪ Below average")

# ==================== POSITION SIZER PAGE ====================
elif page == 'Position Sizer':
    st.title("💰 Professional Position Sizer")
    st.markdown("Calculate optimal position size with institutional risk management")
    
    # Quick preset buttons
    st.markdown("### ⚡ Quick Presets")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if st.button("📊 Conservative (0.5%)", use_container_width=True):
            st.session_state.risk_per_trade = 0.5
            st.rerun()
    with col2:
        if st.button("📈 Standard (1.0%)", use_container_width=True):
            st.session_state.risk_per_trade = 1.0
            st.rerun()
    with col3:
        if st.button("🚀 Aggressive (1.5%)", use_container_width=True):
            st.session_state.risk_per_trade = 1.5
            st.rerun()
    with col4:
        st.metric("Current Risk", f"{st.session_state.risk_per_trade}%")
    
    st.markdown("---")
    
    # Input section
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 📝 Trade Details")
        
        ticker_ps = st.text_input("Ticker (Optional)", value="", placeholder="e.g., AAPL").upper()
        entry_price = st.number_input("Entry Price ($)", min_value=0.01, value=150.00, step=0.01)
        stop_loss_price = st.number_input("Stop Loss ($)", min_value=0.01, value=145.00, step=0.01)
        target_price = st.number_input("Target Price ($)", min_value=0.01, value=165.00, step=0.01)
        
        # Fetch live price if ticker provided
        if ticker_ps and st.button("Get Current Price"):
            with st.spinner(f"Fetching {ticker_ps}..."):
                hist, info = get_stock_data_optimized(ticker_ps, period='5d', interval='1d')
                if not hist.empty:
                    live_price = hist['Close'].iloc[-1]
                    st.info(f"💡 Current {ticker_ps} price: ${live_price:.2f}")
    
    with col2:
        st.markdown("### ⚙️ Advanced Options")
        
        custom_account = st.number_input(
            "Account Size (Override)",
            min_value=1000,
            value=st.session_state.account_size,
            step=10000,
            help="Override sidebar account size"
        )
        
        custom_risk = st.number_input(
            "Risk % (Override)",
            min_value=0.1,
            max_value=5.0,
            value=st.session_state.risk_per_trade,
            step=0.1,
            help="Override sidebar risk %"
        )
        
        max_position_pct = st.slider(
            "Max Position Size (% of Account)",
            min_value=5,
            max_value=50,
            value=25,
            step=5
        )
        
        commission = st.number_input(
            "Commission Per Trade ($)",
            min_value=0.0,
            value=0.0,
            step=0.1
        )
    
    st.markdown("---")
    
    # Calculate button
    if st.button("🧮 Calculate Position Size", type="primary", use_container_width=True):
        # Validation
        if entry_price <= 0 or stop_loss_price <= 0 or target_price <= 0:
            st.error("❌ All prices must be greater than 0")
        elif stop_loss_price >= entry_price:
            st.error("❌ Stop loss must be below entry price")
        elif target_price <= entry_price:
            st.error("❌ Target must be above entry price")
        else:
            # Calculations
            risk_per_share = entry_price - stop_loss_price
            reward_per_share = target_price - entry_price
            reward_risk_ratio = reward_per_share / risk_per_share
            
            risk_amount = custom_account * (custom_risk / 100)
            shares = int(risk_amount / risk_per_share)
            position_value = shares * entry_price
            
            # Check position size limits
            max_position_value = custom_account * (max_position_pct / 100)
            
            if position_value > max_position_value:
                st.warning(f"⚠️ Position size exceeds max. Adjusting...")
                shares = int(max_position_value / entry_price)
                position_value = shares * entry_price
            
            # Display results
            st.success("✅ Position Size Calculated")
            
            st.markdown("### 📊 Position Details")
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Shares to Buy", f"{shares:,}")
            with col2:
                st.metric("Position Value", f"${position_value:,.0f}")
            with col3:
                portfolio_allocation = (position_value / custom_account) * 100
                st.metric("Portfolio %", f"{portfolio_allocation:.1f}%")
            with col4:
                st.metric("R:R Ratio", f"{reward_risk_ratio:.2f}:1")
            
            st.markdown("---")
            
            # Risk Analysis
            st.markdown("### 🎯 Risk & Reward Analysis")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.markdown("**📉 Risk Metrics**")
                st.metric("Risk Per Share", f"${risk_per_share:.2f}")
                st.metric("Total Risk", f"${risk_amount:,.0f}")
                risk_pct_of_account = (risk_amount / custom_account) * 100
                st.metric("Risk % of Account", f"{risk_pct_of_account:.2f}%")
            
            with col2:
                st.markdown("**📈 Reward Metrics**")
                st.metric("Reward Per Share", f"${reward_per_share:.2f}")
                potential_profit = shares * reward_per_share
                st.metric("Potential Profit", f"${potential_profit:,.0f}")
                reward_pct_of_account = (potential_profit / custom_account) * 100
                st.metric("Reward % of Account", f"{reward_pct_of_account:.2f}%")
            
            with col3:
                st.markdown("**💼 Trade Cost**")
                total_cost = position_value + (commission * 2)
                st.metric("Entry Cost", f"${position_value:,.0f}")
                if commission > 0:
                    st.metric("Total Commission", f"${commission * 2:.2f}")
                st.metric("Total Capital Needed", f"${total_cost:,.0f}")
            
            st.markdown("---")
            
            # Scenario Analysis
            st.markdown("### 📊 Scenario Analysis")
            
            scenarios = pd.DataFrame({
                'Scenario': [
                    '🔴 Stop Loss Hit',
                    '🟡 Breakeven',
                    '🟢 Target Hit (1R)',
                    '🟢 Target Hit (2R)',
                    '🚀 Full Target'
                ],
                'Exit Price': [
                    stop_loss_price,
                    entry_price,
                    entry_price + (risk_per_share * 1),
                    entry_price + (risk_per_share * 2),
                    target_price
                ]
            })
            
            scenarios['P&L'] = (scenarios['Exit Price'] - entry_price) * shares
            scenarios['Account Impact'] = (scenarios['P&L'] / custom_account) * 100
            scenarios['New Account Value'] = custom_account + scenarios['P&L']
            
            st.dataframe(
                scenarios.style.format({
                    'Exit Price': '${:.2f}',
                    'P&L': '${:,.2f}',
                    'Account Impact': '{:+.2f}%',
                    'New Account Value': '${:,.2f}'
                }),
                use_container_width=True,
                hide_index=True
            )
            
            # Order Summary
            st.markdown("---")
            st.markdown("### 📋 Order Summary")
            
            order_summary = f"""
**Stock:** {ticker_ps if ticker_ps else 'N/A'}
**Action:** BUY {shares:,} shares
**Entry Price:** ${entry_price:.2f}
**Stop Loss:** ${stop_loss_price:.2f}
**Target:** ${target_price:.2f}
**Position Size:** ${position_value:,.0f} ({portfolio_allocation:.1f}% of account)
**Risk:** ${risk_amount:,.0f} ({risk_pct_of_account:.2f}% of account)
**Potential Profit:** ${potential_profit:,.0f} ({reward_pct_of_account:.2f}% of account)
**R:R Ratio:** {reward_risk_ratio:.2f}:1
            """
            
            st.code(order_summary, language=None)

st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #888; padding: 1rem;'>
    <p><strong>Professional Swing Trading System</strong> | Built for Consistency</p>
    <p style='font-size: 0.85rem;'>⚠️ Trading involves risk. This is for educational purposes. Not financial advice.</p>
</div>
""", unsafe_allow_html=True)
