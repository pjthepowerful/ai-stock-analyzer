import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import time

# Page configuration
st.set_page_config(
    page_title="AI Stock Analyzer Ultimate", 
    page_icon="🚀", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state
if 'portfolio_size' not in st.session_state:
    st.session_state.portfolio_size = 192.91
if 'risk_percent' not in st.session_state:
    st.session_state.risk_percent = 2
if 'analyzed_stocks' not in st.session_state:
    st.session_state.analyzed_stocks = []
if 'favorites' not in st.session_state:
    st.session_state.favorites = []
if 'buy_signals_history' not in st.session_state:
    st.session_state.buy_signals_history = []
if 'dark_mode' not in st.session_state:
    st.session_state.dark_mode = False
if 'alerts' not in st.session_state:
    st.session_state.alerts = []
if 'watchlist_data' not in st.session_state:
    st.session_state.watchlist_data = {}

# Apply dark mode
if st.session_state.dark_mode:
    st.markdown("""
        <style>
        .stApp {
            background-color: #0e1117;
            color: #fafafa;
        }
        </style>
    """, unsafe_allow_html=True)

# Title
col1, col2 = st.columns([6, 1])
with col1:
    st.title("🚀 AI Stock Analyzer Ultimate")
with col2:
    if st.button("🌙" if not st.session_state.dark_mode else "☀️"):
        st.session_state.dark_mode = not st.session_state.dark_mode
        st.rerun()

st.markdown("---")

# Sidebar
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

st.sidebar.markdown(f"**Portfolio:** ${st.session_state.portfolio_size:.2f}")
st.sidebar.markdown(f"**Risk:** {st.session_state.risk_percent}%")
st.sidebar.markdown(f"**Max Risk:** ${st.session_state.portfolio_size * (st.session_state.risk_percent / 100):.2f}")

st.sidebar.markdown("---")
st.sidebar.header("⭐ Watchlist")

# Add to watchlist
new_ticker = st.sidebar.text_input("Add to Watchlist", "").upper()
if st.sidebar.button("➕ Add") and new_ticker:
    if new_ticker not in st.session_state.favorites:
        st.session_state.favorites.append(new_ticker)
        st.sidebar.success(f"Added {new_ticker}!")
        st.rerun()
    else:
        st.sidebar.warning("Already in watchlist")

# Display watchlist
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
    st.sidebar.info("Add tickers to watchlist")

st.sidebar.markdown("---")
st.sidebar.header("🔔 Active Alerts")
if st.session_state.alerts:
    for i, alert in enumerate(st.session_state.alerts):
        with st.sidebar.expander(f"{alert['ticker']} - {alert['condition']}"):
            st.write(f"**Trigger:** {alert['condition']}")
            st.write(f"**Value:** {alert['value']}")
            if st.button("Delete", key=f"del_alert_{i}"):
                st.session_state.alerts.pop(i)
                st.rerun()
else:
    st.sidebar.info("No active alerts")

def get_stock_news(ticker):
    """Fetch recent news for a stock"""
    try:
        stock = yf.Ticker(ticker)
        news = stock.news[:5] if hasattr(stock, 'news') and stock.news else []
        return news
    except:
        return []

def create_candlestick_chart(ticker, hist):
    """Create interactive candlestick chart"""
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
            
            # Calculate indicators
            sma50 = window['Close'].rolling(50).mean().iloc[-1]
            sma200 = window['Close'].rolling(200).mean().iloc[-1]
            
            delta = window['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
            rs = gain / loss
            rsi = (100 - (100 / (1 + rs))).iloc[-1]
            
            # Calculate score
            score = 0
            if close > sma50:
                score += 2
            if close > sma200:
                score += 1
            if rsi < 30:
                score += 2
            elif 30 <= rsi <= 70:
                score += 1
            
            # Trading logic
            if score >= 3 and position is None:
                # Buy signal
                position = {
                    'entry_price': close,
                    'entry_date': hist.index[i],
                    'score': score
                }
            elif position and (score < 1 or close < position['entry_price'] * 0.95):
                # Sell signal or stop loss
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
    except Exception as e:
        return None

def analyze_stock(ticker, portfolio_size, risk_percent):
    """Enhanced stock analysis"""
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
            factors.append(f"✅ High volume ({volume_ratio:.2f}x) [+1]")
        elif volume_ratio < 0.5:
            score -= 1
            factors.append(f"❌ Low volume ({volume_ratio:.2f}x) [-1]")

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
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "error": False
        }

        # Check alerts
        for alert in st.session_state.alerts:
            if alert['ticker'] == ticker:
                if alert['condition'] == 'RSI < 30' and rsi < 30:
                    st.sidebar.success(f"🔔 Alert: {ticker} RSI = {rsi:.1f}")
                elif alert['condition'] == 'Strong Buy' and score >= 5:
                    st.sidebar.success(f"🔔 Alert: {ticker} is STRONG BUY!")
                elif alert['condition'] == 'Price Below' and close < alert['value']:
                    st.sidebar.success(f"🔔 Alert: {ticker} below ${alert['value']}")

        if "BUY" in verdict:
            st.session_state.buy_signals_history.append(result.copy())

        return result

    except Exception as e:
        return {"ticker": ticker, "verdict": "ERROR", "score": 0, "error": True, "error_msg": str(e)}

# Main tabs
tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
    "📊 Analysis",
    "🎯 Watchlist Dashboard", 
    "🔍 Stock Screener",
    "📰 News & Alerts",
    "📈 Backtesting",
    "💎 Buy Signals",
    "📜 History"
])

with tab1:
    st.header("Stock Analysis")
    
    col1, col2, col3 = st.columns([3, 1, 1])
    with col1:
        ticker_input = st.text_input("Enter Ticker", value=st.session_state.get('quick_analyze', '')).upper()
    with col2:
        analyze_btn = st.button("🔍 Analyze", type="primary", use_container_width=True)
    with col3:
        if ticker_input and ticker_input not in st.session_state.favorites:
            if st.button("⭐ Add to Watchlist", use_container_width=True):
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
                
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("### 📈 Indicators")
                    st.write(f"**RSI:** {result['rsi']}")
                    st.write(f"**SMA50:** ${result['sma50']}")
                    st.write(f"**SMA200:** ${result['sma200']}")
                    st.write(f"**Volume:** {result['volume_ratio']}x")
                
                with col2:
                    st.markdown("### 🎯 Targets")
                    st.success(f"**TP1:** ${result['tp1']}")
                    st.success(f"**TP2:** ${result['tp2']}")
                    st.error(f"**SL1:** ${result['sl1']}")
                    st.error(f"**SL2:** ${result['sl2']}")
                
                with st.expander("🔍 Analysis Details"):
                    for factor in result['factors']:
                        st.write(factor)

with tab2:
    st.header("🎯 Watchlist Dashboard")
    
    if st.session_state.favorites:
        if st.button("🔄 Refresh All", type="primary"):
            with st.spinner("Updating watchlist..."):
                for ticker in st.session_state.favorites:
                    result = analyze_stock(ticker, st.session_state.portfolio_size, st.session_state.risk_percent)
                    if not result['error']:
                        st.session_state.watchlist_data[ticker] = result
                st.success("Watchlist updated!")
        
        st.markdown("---")
        
        # Display watchlist
        cols = st.columns(min(3, len(st.session_state.favorites)))
        for i, ticker in enumerate(st.session_state.favorites):
            with cols[i % 3]:
                if ticker in st.session_state.watchlist_data:
                    data = st.session_state.watchlist_data[ticker]
                    
                    # Color based on verdict
                    if "STRONG BUY" in data['verdict']:
                        st.success(f"### {ticker}")
                    elif "BUY" in data['verdict']:
                        st.info(f"### {ticker}")
                    elif "HOLD" in data['verdict']:
                        st.warning(f"### {ticker}")
                    else:
                        st.error(f"### {ticker}")
                    
                    st.metric("Price", f"${data['price']}", f"{data['daily_change']}%")
                    st.write(f"**Score:** {data['score']}")
                    st.write(f"**Verdict:** {data['verdict']}")
                    st.write(f"**RSI:** {data['rsi']}")
                    
                    if st.button("Analyze", key=f"analyze_{ticker}"):
                        st.session_state.quick_analyze = ticker
                        st.switch_page
                else:
                    st.info(f"### {ticker}")
                    st.write("Click 'Refresh All' to load data")
    else:
        st.info("Add tickers to your watchlist to see them here!")

with tab3:
    st.header("🔍 AI Stock Screener")
    
    st.write("Scan multiple stocks to find the best opportunities")
    
    col1, col2 = st.columns([2, 1])
    with col1:
        screener_option = st.radio("Select stocks to screen:", 
            ["Popular Stocks", "S&P 100 Sample", "Custom List"])
    with col2:
        min_score = st.slider("Minimum Score", 0, 10, 3)
    
    if screener_option == "Popular Stocks":
        screen_tickers = ["AAPL", "GOOGL", "MSFT", "AMZN", "TSLA", "NVDA", "META", "NFLX", "AMD", "INTC"]
    elif screener_option == "S&P 100 Sample":
        screen_tickers = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "BRK.B", "JPM", "JNJ", 
                         "V", "PG", "XOM", "MA", "HD", "CVX", "MRK", "PFE", "ABBV", "KO"]
    else:
        custom_input = st.text_area("Enter tickers (comma-separated)", "AAPL,TSLA,GOOGL")
        screen_tickers = [t.strip().upper() for t in custom_input.split(",")]
    
    if st.button("🚀 Run Screener", type="primary"):
        st.info(f"Screening {len(screen_tickers)} stocks...")
        progress = st.progress(0)
        
        results = []
        for i, ticker in enumerate(screen_tickers):
            result = analyze_stock(ticker, st.session_state.portfolio_size, st.session_state.risk_percent)
            if not result['error'] and result['score'] >= min_score:
                results.append(result)
            progress.progress((i + 1) / len(screen_tickers))
        
        progress.empty()
        
        if results:
            results_sorted = sorted(results, key=lambda x: x['score'], reverse=True)
            
            st.success(f"Found {len(results_sorted)} stocks matching criteria!")
            
            # Top picks
            st.markdown("### 🏆 Top Picks")
            cols = st.columns(min(3, len(results_sorted[:3])))
            for i, result in enumerate(results_sorted[:3]):
                with cols[i]:
                    st.success(f"### #{i+1} {result['ticker']}")
                    st.metric("Score", result['score'])
                    st.write(f"**Price:** ${result['price']}")
                    st.write(f"**Verdict:** {result['verdict']}")
            
            # Full results table
            st.markdown("### 📊 All Results")
            df = pd.DataFrame(results_sorted)
            df = df[["ticker", "company", "price", "score", "verdict", "rsi", "daily_change"]]
            df.columns = ["Ticker", "Company", "Price", "Score", "Verdict", "RSI", "Change %"]
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.warning(f"No stocks found with score >= {min_score}")

with tab4:
    st.header("📰 News & Custom Alerts")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📰 Stock News")
        news_ticker = st.text_input("Get news for ticker", "AAPL").upper()
        
        if st.button("📰 Fetch News"):
            with st.spinner("Fetching news..."):
                news = get_stock_news(news_ticker)
                
                if news:
                    for article in news:
                        with st.expander(f"📰 {article.get('title', 'News Article')}"):
                            st.write(f"**Publisher:** {article.get('publisher', 'Unknown')}")
                            st.write(f"**Published:** {datetime.fromtimestamp(article.get('providerPublishTime', 0)).strftime('%Y-%m-%d %H:%M')}")
                            st.write(article.get('link', ''))
                else:
                    st.info("No recent news available")
    
    with col2:
        st.subheader("🔔 Create Custom Alert")
        
        alert_ticker = st.text_input("Ticker for alert", "").upper()
        alert_type = st.selectbox("Alert Type", [
            "RSI < 30",
            "Strong Buy Signal",
            "Price Below Target",
            "Score Above 5"
        ])
        
        alert_value = None
        if alert_type == "Price Below Target":
            alert_value = st.number_input("Target Price", min_value=0.0, step=1.0)
        
        if st.button("➕ Create Alert") and alert_ticker:
            new_alert = {
                'ticker': alert_ticker,
                'condition': alert_type,
                'value': alert_value,
                'created': datetime.now().strftime('%Y-%m-%d %H:%M')
            }
            st.session_state.alerts.append(new_alert)
            st.success(f"Alert created for {alert_ticker}!")
            st.rerun()

with tab5:
    st.header("📈 Strategy Backtesting")
    
    st.write("Test how the strategy would have performed historically")
    
    col1, col2 = st.columns([2, 1])
    with col1:
        backtest_ticker = st.text_input("Ticker to backtest", "AAPL").upper()
    with col2:
        backtest_years = st.selectbox("Years to test", [1, 2, 3, 5], index=1)
    
    if st.button("🔬 Run Backtest", type="primary"):
        with st.spinner(f"Backtesting {backtest_ticker} over {backtest_years} years..."):
            results = backtest_strategy(backtest_ticker, backtest_years)
            
            if results:
                st.success("Backtest Complete!")
                
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Total Trades", results['total_trades'])
                with col2:
                    st.metric("Win Rate", f"{results['win_rate']:.1f}%")
                with col3:
                    st.metric("Avg Win", f"{results['avg_win']:.2f}%")
                with col4:
                    st.metric("Avg Loss", f"{results['avg_loss']:.2f}%")
                
                st.markdown("### 📊 Trade History")
                st.dataframe(results['trades'], use_container_width=True)
                
                # Cumulative returns chart
                results['trades']['cumulative_pnl'] = results['trades']['pnl_percent'].cumsum()
                
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=results['trades']['exit_date'],
                    y=results['trades']['cumulative_pnl'],
                    mode='lines+markers',
                    name='Cumulative P&L %',
                    line=dict(color='green', width=2)
                ))
                fig.update_layout(
                    title="Cumulative Returns",
                    xaxis_title="Date",
                    yaxis_title="Cumulative P&L %",
                    template='plotly_dark' if st.session_state.dark_mode else 'plotly_white'
                )
                st.plotly_chart(fig, use_container_width=True)
                
            else:
                st.error("Unable to backtest. Not enough historical data.")

with tab6:
    st.header("💎 Buy Signals Summary")
    
    if st.session_state.analyzed_stocks:
        buy_signals = [s for s in st.session_state.analyzed_stocks if "BUY" in s.get("verdict", "") and not s.get("error", False)]
        buy_signals_sorted = sorted(buy_signals, key=lambda x: x["score"], reverse=True)
        
        if buy_signals_sorted:
            st.success(f"Found {len(buy_signals_sorted)} buy signals")
            
            df = pd.DataFrame(buy_signals_sorted)
            df = df[["ticker", "company", "price", "score", "verdict", "tp1", "tp2", "sl1", "sl2", "shares", "risk_amount"]]
            df.columns = ["Ticker", "Company", "Price", "Score", "Verdict", "TP1", "TP2", "SL1", "SL2", "Shares", "Risk $"]
            
            st.dataframe(df, use_container_width=True, hide_index=True)
            
            csv = df.to_csv(index=False)
            st.download_button(
                label="📥 Download Buy Signals CSV",
                data=csv,
                file_name=f"buy_signals_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )
            
            # Detailed cards
            st.markdown("### 📋 Detailed View")
            for stock in buy_signals_sorted:
                with st.expander(f"{stock['ticker']} - {stock['company']} (Score: {stock['score']})"):
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Price", f"${stock['price']}")
                        st.write(f"**RSI:** {stock['rsi']}")
                    with col2:
                        st.write(f"**TP1:** ${stock['tp1']}")
                        st.write(f"**TP2:** ${stock['tp2']}")
                        st.write(f"**SL1:** ${stock['sl1']}")
                    with col3:
                        st.write(f"**Shares:** {stock['shares']}")
                        st.write(f"**Position:** ${stock['position_value']}")
                        st.write(f"**Risk:** ${stock['risk_amount']}")
        else:
            st.info("No buy signals yet")
        
        if st.button("🗑️ Clear Signals"):
            st.session_state.analyzed_stocks = []
            st.rerun()
    else:
        st.info("Analyze stocks to see buy signals")

with tab7:
    st.header("📜 Historical Buy Signals")
    
    if st.session_state.buy_signals_history:
        st.info(f"Total historical signals: {len(st.session_state.buy_signals_history)}")
        
        col1, col2 = st.columns([2, 1])
        with col1:
            filter_ticker = st.text_input("Filter by ticker", "")
        with col2:
            if st.button("🗑️ Clear History"):
                st.session_state.buy_signals_history = []
                st.rerun()
        
        filtered = st.session_state.buy_signals_history
        if filter_ticker:
            filtered = [s for s in filtered if s['ticker'].upper() == filter_ticker.upper()]
        
        if filtered:
            for signal in reversed(filtered[-20:]):
                with st.expander(f"{signal['ticker']} - {signal['verdict']} (Score: {signal['score']}) - {signal['timestamp']}"):
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.write(f"**Price:** ${signal['price']}")
                        st.write(f"**Score:** {signal['score']}")
                        st.write(f"**RSI:** {signal['rsi']}")
                    with col2:
                        st.write(f"**TP1:** ${signal['tp1']}")
                        st.write(f"**TP2:** ${signal['tp2']}")
                        st.write(f"**SL1:** ${signal['sl1']}")
                    with col3:
                        st.write(f"**Shares:** {signal['shares']}")
                        st.write(f"**Risk:** ${signal['risk_amount']}")
        else:
            st.info("No matching signals")
    else:
        st.info("No historical signals yet")

# Footer
st.sidebar.markdown("---")
st.sidebar.markdown("### 📊 Scoring System")
st.sidebar.markdown("""
**Score ≥ 5:** 🚀 STRONG BUY  
**Score 3-4:** ✅ BUY  
**Score 1-2:** ⏸️ HOLD  
**Score ≤ 0:** ❌ SELL

**Features:**
- 🎯 Live Watchlist Dashboard
- 🔍 AI Stock Screener
- 📰 Real-time News
- 🔔 Custom Alerts
- 📈 Strategy Backtesting
""")
