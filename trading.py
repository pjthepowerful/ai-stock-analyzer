import streamlit as st
import yfinance as yf
import pandas as pd
import json
from datetime import datetime

# Page configuration
st.set_page_config(page_title="AI Stock Analyzer", page_icon="🚀", layout="wide")

# Initialize session state for portfolio settings
if 'portfolio_size' not in st.session_state:
    st.session_state.portfolio_size = 0.00
if 'risk_percent' not in st.session_state:
    st.session_state.risk_percent = 2
if 'analyzed_stocks' not in st.session_state:
    st.session_state.analyzed_stocks = []

# Title
st.title("🚀 AI-Enhanced Stock Analyzer")
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

        return {
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
            "error": False
        }

    except Exception as e:
        return {"ticker": ticker, "verdict": "ERROR", "score": 0, "error": True, "error_msg": str(e)}

# Main content tabs
tab1, tab2, tab3 = st.tabs(["📊 Single Stock Analysis", "📈 Multiple Stocks", "💎 Buy Signals Summary"])

with tab1:
    st.header("Analyze a Single Stock")
    
    col1, col2 = st.columns([3, 1])
    with col1:
        ticker_input = st.text_input("Enter Stock Ticker (e.g., AAPL, TSLA, NVDA)", "").upper()
    with col2:
        analyze_btn = st.button("🔍 Analyze", type="primary", use_container_width=True)
    
    if analyze_btn and ticker_input:
        with st.spinner(f"📊 Fetching data for {ticker_input}..."):
            result = analyze_stock(ticker_input, st.session_state.portfolio_size, st.session_state.risk_percent)
            
            if result["error"]:
                st.error(f"❌ Error analyzing {ticker_input}: {result.get('error_msg', 'No data available')}")
            else:
                # Add to analyzed stocks
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
                
                # Technical Indicators
                st.markdown("### 📈 Technical Indicators")
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"**RSI:** {result['rsi']}")
                    st.write(f"**50-day SMA:** ${result['sma50']}")
                    st.write(f"**200-day SMA:** ${result['sma200']}")
                with col2:
                    st.write(f"**ATR:** ${result['atr']}")
                    st.write(f"**Volume Ratio:** {result['volume_ratio']}x")
                    st.write(f"**Volatility:** {result['volatility']}%")
                
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
                st.markdown("### 🔍 Analysis Factors")
                for factor in result['factors']:
                    st.write(factor)

with tab2:
    st.header("Analyze Multiple Stocks")
    
    input_method = st.radio("Choose input method:", ["Enter Tickers Manually", "Upload File"])
    
    tickers = []
    
    if input_method == "Enter Tickers Manually":
        ticker_text = st.text_area("Enter tickers (one per line)", "AAPL\nTSLA\nGOOGL\nMSFT\nAMZN", height=150)
        tickers = [t.strip().upper() for t in ticker_text.split("\n") if t.strip()]
    else:
        uploaded_file = st.file_uploader("Upload tickers.txt", type=['txt'])
        if uploaded_file:
            content = uploaded_file.read().decode('utf-8')
            tickers = [t.strip().upper() for t in content.split("\n") if t.strip()]
    
    if st.button("🚀 Analyze All Stocks", type="primary") and tickers:
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        results = []
        for i, ticker in enumerate(tickers):
            status_text.text(f"Analyzing {ticker}... ({i+1}/{len(tickers)})")
            result = analyze_stock(ticker, st.session_state.portfolio_size, st.session_state.risk_percent)
            results.append(result)
            st.session_state.analyzed_stocks.append(result)
            progress_bar.progress((i + 1) / len(tickers))
        
        status_text.text("✅ Analysis complete!")
        progress_bar.empty()
        
        # Filter and display results
        buy_stocks = [s for s in results if "BUY" in s["verdict"] and not s["error"]]
        hold_stocks = [s for s in results if "HOLD" in s["verdict"] and not s["error"]]
        sell_stocks = [s for s in results if "SELL" in s["verdict"] and not s["error"]]
        
        buy_stocks_sorted = sorted(buy_stocks, key=lambda x: x["score"], reverse=True)
        
        # Summary
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Analyzed", len(results))
        with col2:
            st.metric("Buy Signals", len(buy_stocks))
        with col3:
            st.metric("Hold Signals", len(hold_stocks))
        with col4:
            st.metric("Sell Signals", len(sell_stocks))
        
        # Display buy signals
        if buy_stocks_sorted:
            st.success(f"### 📈 BUY SIGNALS ({len(buy_stocks_sorted)})")
            for stock in buy_stocks_sorted:
                with st.expander(f"{stock['ticker']} - {stock['company']} | Score: {stock['score']} | {stock['verdict']}"):
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.write(f"**Price:** ${stock['price']}")
                        st.write(f"**Daily Change:** {stock['daily_change']}%")
                    with col2:
                        st.write(f"**TP1:** ${stock['tp1']} | **TP2:** ${stock['tp2']}")
                        st.write(f"**SL1:** ${stock['sl1']} | **SL2:** ${stock['sl2']}")
                    with col3:
                        st.write(f"**Shares:** {stock['shares']}")
                        st.write(f"**Risk:** ${stock['risk_amount']}")

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
            
            # Detailed view
            for stock in buy_signals_sorted:
                with st.expander(f"📊 {stock['ticker']} - {stock['company']}"):
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Price", f"${stock['price']}")
                        st.metric("Score", stock['score'])
                    with col2:
                        st.write(f"**TP1:** ${stock['tp1']}")
                        st.write(f"**TP2:** ${stock['tp2']}")
                        st.write(f"**SL1:** ${stock['sl1']}")
                        st.write(f"**SL2:** ${stock['sl2']}")
                    with col3:
                        st.write(f"**Shares:** {stock['shares']}")
                        st.write(f"**Position:** ${stock['position_value']}")
                        st.write(f"**Risk:** ${stock['risk_amount']}")
        else:
            st.info("No buy signals found yet. Analyze some stocks first!")
        
        if st.button("🗑️ Clear All Signals"):
            st.session_state.analyzed_stocks = []
            st.rerun()
    else:
        st.info("No stocks analyzed yet. Go to the analysis tabs to get started!")

# Footer
st.sidebar.markdown("---")
st.sidebar.markdown("### 📊 Scoring System")
st.sidebar.markdown("""
**Score ≥ 5:** 🚀 STRONG BUY
**Score 3-4:** ✅ BUY  
**Score 1-2:** ⏸️ HOLD  
**Score ≤ 0:** ❌ SELL
""")