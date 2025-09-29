import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import json

# Page configuration
st.set_page_config(
    page_title="AI Stock Analyzer Pro", 
    page_icon="🚀", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for dark mode toggle
if 'dark_mode' not in st.session_state:
    st.session_state.dark_mode = False

# Apply theme
if st.session_state.dark_mode:
    st.markdown("""
        <style>
        .stApp {
            background-color: #0e1117;
            color: #fafafa;
        }
        </style>
    """, unsafe_allow_html=True)

# Initialize session state
if 'portfolio_size' not in st.session_state:
    st.session_state.portfolio_size = 0.00
if 'risk_percent' not in st.session_state:
    st.session_state.risk_percent = 2
if 'analyzed_stocks' not in st.session_state:
    st.session_state.analyzed_stocks = []
if 'favorites' not in st.session_state:
    st.session_state.favorites = []
if 'buy_signals_history' not in st.session_state:
    st.session_state.buy_signals_history = []

# Title with dark mode toggle
col1, col2 = st.columns([6, 1])
with col1:
    st.title("🚀 AI Stock Analyzer Pro")
with col2:
    if st.button("🌙" if not st.session_state.dark_mode else "☀️"):
        st.session_state.dark_mode = not st.session_state.dark_mode
        st.rerun()

st.markdown("---")

# Sidebar - Portfolio Settings
st.sidebar.header("💼 Portfolio Settings")
st.session_state.portfolio_size = st.sidebar.number_input(
    "Portfolio Size ($)", 
    value=st.session_state.portfolio_size, 
    min_value=0.0, 
    step=10.0
)
st.session_state.risk_percent = st.sidebar.slider(
    "Risk per Trade (%)", 
    min_value=1, 
    max_value=10, 
    value=st.session_state.risk_percent
)

st.sidebar.markdown(f"**Current Portfolio:** ${st.session_state.portfolio_size:.2f}")
st.sidebar.markdown(f"**Risk per Trade:** {st.session_state.risk_percent}%")
st.sidebar.markdown(f"**Max Risk:** ${st.session_state.portfolio_size * (st.session_state.risk_percent / 100):.2f}")

st.sidebar.markdown("---")

# Favorites section
st.sidebar.header("⭐ Favorite Tickers")
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
else:
    st.sidebar.info("No favorites yet. Add some!")

def create_candlestick_chart(ticker, hist):
    """Create interactive candlestick chart with indicators"""
    fig = make_subplots(
        rows=3, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.05,
        subplot_titles=(f'{ticker} Price', 'Volume', 'RSI'),
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
    
    # Add SMAs
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
        template='plotly_dark' if st.session_state.dark_mode else 'plotly_white'
    )
    
    return fig

def analyze_stock(ticker, portfolio_size, risk_percent):
    """Enhanced stock analysis with AI scoring"""
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="6mo")
        info = stock.info

        if hist.empty or len(hist) < 50:
            return {"ticker": ticker, "verdict": "NO DATA", "score": 0, "error": True}

        close = hist["Close"].iloc[-1]
        prev_close = hist["Close"].iloc[-2] if len(hist) > 1 else close

        # Calculate technical indicators
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

        # Bollinger Bands
        sma20 = hist["Close"].rolling(20).mean().iloc[-1]
        std20 = hist["Close"].rolling(20).std().iloc[-1]
        upper_band = sma20 + (std20 * 2)
        lower_band = sma20 - (std20 * 2)

        # Volume analysis
        avg_volume = hist["Volume"].mean()
        current_volume = hist["Volume"].iloc[-1]
        volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1

        # Volatility
        returns = hist["Close"].pct_change()
        volatility = returns.std() * (252 ** 0.5) * 100

        # Enhanced scoring system
        score = 0
        factors = []

        # Price vs SMAs
        if close > sma50:
            score += 2
            factors.append(f"✅ Price above 50-day SMA (${sma50:.2f}) [+2]")
        else:
            factors.append(f"❌ Price below 50-day SMA (${sma50:.2f}) [-2]")
            score -= 2

        if close > sma200:
            score += 1
            factors.append(f"✅ Price above 200-day SMA (${sma200:.2f}) [+1]")
        else:
            factors.append(f"❌ Price below 200-day SMA (${sma200:.2f}) [-1]")
            score -= 1

        # RSI analysis
        if rsi < 30:
            score += 2
            factors.append(f"✅ RSI oversold ({rsi:.1f}) [+2]")
        elif 30 <= rsi <= 70:
            score += 1
            factors.append(f"✅ RSI neutral range ({rsi:.1f}) [+1]")
        else:
            score -= 1
            factors.append(f"❌ RSI overbought ({rsi:.1f}) [-1]")

        # Volume analysis
        if volume_ratio > 1.5:
            score += 1
            factors.append(f"✅ High volume ({volume_ratio:.2f}x avg) [+1]")
        elif volume_ratio < 0.5:
            score -= 1
            factors.append(f"❌ Low volume ({volume_ratio:.2f}x avg) [-1]")
        else:
            factors.append(f"➖ Normal volume ({volume_ratio:.2f}x avg) [0]")

        # Volatility check
        if volatility < 20:
            factors.append(f"➖ Low volatility ({volatility:.1f}%) [0]")
        elif volatility > 40:
            score -= 1
            factors.append(f"❌ High volatility ({volatility:.1f}%) [-1]")
        else:
            factors.append(f"➖ Moderate volatility ({volatility:.1f}%) [0]")

        # MACD
        if macd_current > signal_current:
            score += 1
            factors.append(f"✅ MACD bullish crossover [+1]")
        else:
            factors.append(f"❌ MACD bearish [0]")

        # Bollinger Bands
        if close < lower_band:
            score += 1
            factors.append(f"✅ Price near lower Bollinger Band [+1]")
        elif close > upper_band:
            score -= 1
            factors.append(f"❌ Price near upper Bollinger Band [-1]")

        # Momentum
        daily_change = ((close - prev_close) / prev_close) * 100
        if daily_change > 2:
            score += 1
            factors.append(f"✅ Strong momentum (+{daily_change:.2f}%) [+1]")
        elif daily_change < -2:
            score -= 1
            factors.append(f"❌ Weak momentum ({daily_change:.2f}%) [-1]")
        else:
            factors.append(f"➖ Moderate momentum ({daily_change:.2f}%) [0]")

        # Verdict based on enhanced scoring
        if score >= 5:
            verdict = "🚀 STRONG BUY"
        elif score >= 3:
            verdict = "✅ BUY"
        elif score >= 1:
            verdict = "⏸️ HOLD"
        else:
            verdict = "❌ SELL"

        # ATR-based TP/SL
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
            "upper_band": round(upper_band, 2),
            "lower_band": round(lower_band, 2),
            "tp1": tp1,
            "tp2": tp2,
            "sl1": sl1,
            "sl2": sl2,
            "shares": shares,
            "position_value": round(shares * close, 2),
            "risk_amount": round(max_risk, 2),
            "factors": factors,
            "hist": hist,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "error": False
        }

        # Add to history if it's a buy signal
        if "BUY" in verdict:
            st.session_state.buy_signals_history.append(result.copy())

        return result

    except Exception as e:
        return {"ticker": ticker, "verdict": "ERROR", "score": 0, "error": True, "error_msg": str(e)}

# Main content tabs
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📊 Single Stock", 
    "📈 Multi-Stock Compare", 
    "💎 Buy Signals", 
    "📜 History",
    "📊 Charts"
])

with tab1:
    st.header("Analyze a Single Stock")
    
    col1, col2, col3 = st.columns([3, 1, 1])
    with col1:
        ticker_input = st.text_input("Enter Stock Ticker (e.g., AAPL, TSLA, NVDA)", 
                                     value=st.session_state.get('quick_analyze', '')).upper()
    with col2:
        analyze_btn = st.button("🔍 Analyze", type="primary", use_container_width=True)
    with col3:
        if ticker_input and ticker_input not in st.session_state.favorites:
            if st.button("⭐ Add to Favorites", use_container_width=True):
                st.session_state.favorites.append(ticker_input)
                st.success(f"Added {ticker_input} to favorites!")
                st.rerun()
    
    if analyze_btn and ticker_input:
        with st.spinner(f"📊 Fetching data for {ticker_input}..."):
            result = analyze_stock(ticker_input, st.session_state.portfolio_size, st.session_state.risk_percent)
            
            if result["error"]:
                st.error(f"❌ Error analyzing {ticker_input}: {result.get('error_msg', 'No data available')}")
            else:
                st.session_state.analyzed_stocks.append(result)
                
                st.markdown("---")
                st.subheader(f"🚀 {result['ticker']} - {result['company']}")
                st.caption(f"{result['sector']} | Market Cap: ${result['market_cap']:,}")
                
                # Key metrics
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Current Price", f"${result['price']}")
                with col2:
                    st.metric("Daily Change", f"{result['daily_change']}%", delta=f"{result['daily_change']}%")
                with col3:
                    st.metric("Analysis Score", result['score'])
                with col4:
                    verdict_color = "🟢" if "BUY" in result['verdict'] else "🟡" if "HOLD" in result['verdict'] else "🔴"
                    st.metric("Verdict", f"{verdict_color} {result['verdict']}")
                
                # Charts
                st.plotly_chart(create_candlestick_chart(ticker_input, result['hist']), use_container_width=True)
                
                # Technical Indicators
                st.markdown("### 📈 Technical Indicators")
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.write(f"**RSI:** {result['rsi']}")
                    st.write(f"**50-day SMA:** ${result['sma50']}")
                    st.write(f"**200-day SMA:** ${result['sma200']}")
                with col2:
                    st.write(f"**ATR:** ${result['atr']}")
                    st.write(f"**Volume Ratio:** {result['volume_ratio']}x")
                    st.write(f"**Volatility:** {result['volatility']}%")
                with col3:
                    st.write(f"**Upper BB:** ${result['upper_band']}")
                    st.write(f"**Lower BB:** ${result['lower_band']}")
                
                # Trading Levels
                st.markdown("### 🎯 Trading Levels")
                col1, col2 = st.columns(2)
                with col1:
                    st.success(f"**Take Profit 1:** ${result['tp1']}")
                    st.success(f"**Take Profit 2:** ${result['tp2']}")
                with col2:
                    st.error(f"**Stop Loss 1:** ${result['sl1']}")
                    st.error(f"**Stop Loss 2:** ${result['sl2']}")
                
                # Position Sizing
                st.markdown("### 💼 Position Sizing")
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.info(f"**Recommended Shares:** {result['shares']}")
                with col2:
                    st.info(f"**Position Value:** ${result['position_value']}")
                with col3:
                    st.info(f"**Risk Amount:** ${result['risk_amount']}")
                
                # Analysis Factors
                with st.expander("🔍 Detailed Analysis Factors"):
                    for factor in result['factors']:
                        st.write(factor)

with tab2:
    st.header("Compare Multiple Stocks")
    
    col1, col2 = st.columns([3, 1])
    with col1:
        compare_tickers = st.text_input("Enter tickers separated by commas (e.g., AAPL,TSLA,GOOGL)", "")
    with col2:
        compare_btn = st.button("📊 Compare", type="primary", use_container_width=True)
    
    if compare_btn and compare_tickers:
        tickers_list = [t.strip().upper() for t in compare_tickers.split(",") if t.strip()]
        
        if len(tickers_list) < 2:
            st.warning("Please enter at least 2 tickers to compare")
        else:
            progress_bar = st.progress(0)
            results = []
            
            for i, ticker in enumerate(tickers_list):
                result = analyze_stock(ticker, st.session_state.portfolio_size, st.session_state.risk_percent)
                if not result["error"]:
                    results.append(result)
                progress_bar.progress((i + 1) / len(tickers_list))
            
            progress_bar.empty()
            
            if results:
                # Comparison table
                df = pd.DataFrame(results)
                df = df[["ticker", "company", "price", "score", "verdict", "rsi", "daily_change", "volatility"]]
                df.columns = ["Ticker", "Company", "Price", "Score", "Verdict", "RSI", "Change %", "Volatility %"]
                df = df.sort_values("Score", ascending=False)
                
                st.dataframe(df, use_container_width=True, hide_index=True)
                
                # Side by side comparison
                st.markdown("### 📊 Detailed Comparison")
                cols = st.columns(len(results))
                for i, result in enumerate(sorted(results, key=lambda x: x['score'], reverse=True)):
                    with cols[i]:
                        st.subheader(result['ticker'])
                        st.metric("Score", result['score'])
                        st.metric("Price", f"${result['price']}")
                        st.write(f"**Verdict:** {result['verdict']}")
                        st.write(f"**RSI:** {result['rsi']}")
                        st.write(f"**TP1:** ${result['tp1']}")
                        st.write(f"**SL1:** ${result['sl1']}")

with tab3:
    st.header("💎 Buy Signals Summary")
    
    if st.session_state.analyzed_stocks:
        buy_signals = [s for s in st.session_state.analyzed_stocks if "BUY" in s.get("verdict", "") and not s.get("error", False)]
        buy_signals_sorted = sorted(buy_signals, key=lambda x: x["score"], reverse=True)
        
        if buy_signals_sorted:
            st.success(f"Found {len(buy_signals_sorted)} buy signals")
            
            # Create DataFrame
            df = pd.DataFrame(buy_signals_sorted)
            df = df[["ticker", "company", "price", "score", "verdict", "tp1", "tp2", "sl1", "sl2", "shares", "risk_amount"]]
            df.columns = ["Ticker", "Company", "Price", "Score", "Verdict", "TP1", "TP2", "SL1", "SL2", "Shares", "Risk $"]
            
            st.dataframe(df, use_container_width=True, hide_index=True)
            
            # Download button
            csv = df.to_csv(index=False)
            st.download_button(
                label="📥 Download Buy Signals as CSV",
                data=csv,
                file_name=f"buy_signals_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )
        else:
            st.info("No buy signals found yet. Analyze some stocks first!")
        
        if st.button("🗑️ Clear All Signals"):
            st.session_state.analyzed_stocks = []
            st.rerun()
    else:
        st.info("No stocks analyzed yet. Go to the analysis tabs to get started!")

with tab4:
    st.header("📜 Buy Signals History")
    
    if st.session_state.buy_signals_history:
        st.info(f"Total historical buy signals: {len(st.session_state.buy_signals_history)}")
        
        # Filter by date
        col1, col2 = st.columns([2, 1])
        with col1:
            filter_ticker = st.text_input("Filter by ticker (optional)", "")
        with col2:
            if st.button("🗑️ Clear History"):
                st.session_state.buy_signals_history = []
                st.rerun()
        
        filtered = st.session_state.buy_signals_history
        if filter_ticker:
            filtered = [s for s in filtered if s['ticker'].upper() == filter_ticker.upper()]
        
        if filtered:
            for signal in reversed(filtered[-20:]):  # Show last 20
                with st.expander(f"{signal['ticker']} - {signal['verdict']} (Score: {signal['score']}) - {signal['timestamp']}"):
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.write(f"**Price:** ${signal['price']}")
                        st.write(f"**Score:** {signal['score']}")
                    with col2:
                        st.write(f"**TP1:** ${signal['tp1']}")
                        st.write(f"**SL1:** ${signal['sl1']}")
                    with col3:
                        st.write(f"**Shares:** {signal['shares']}")
                        st.write(f"**Risk:** ${signal['risk_amount']}")
        else:
            st.info("No signals match your filter")
    else:
        st.info("No historical buy signals yet. Start analyzing stocks!")

with tab5:
    st.header("📊 Advanced Charts")
    
    chart_ticker = st.text_input("Enter ticker for detailed charts", "AAPL").upper()
    period_select = st.selectbox("Time Period", ["1mo", "3mo", "6mo", "1y", "2y"], index=2)
    
    if st.button("📈 Generate Charts", type="primary"):
        with st.spinner(f"Loading charts for {chart_ticker}..."):
            try:
                stock = yf.Ticker(chart_ticker)
                hist = stock.history(period=period_select)
                
                if not hist.empty:
                    st.plotly_chart(create_candlestick_chart(chart_ticker, hist), use_container_width=True)
                else:
                    st.error("No data available for this ticker")
            except Exception as e:
                st.error(f"Error loading charts: {e}")

# Footer
st.sidebar.markdown("---")
st.sidebar.markdown("### 📊 Scoring System")
st.sidebar.markdown("""
**Score ≥ 5:** 🚀 STRONG BUY
**Score 3-4:** ✅ BUY  
**Score 1-2:** ⏸️ HOLD  
**Score ≤ 0:** ❌ SELL
""")
