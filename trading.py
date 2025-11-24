import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timedelta
import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers
from sklearn.preprocessing import MinMaxScaler
import warnings
warnings.filterwarnings('ignore')

# Page configuration
st.set_page_config(
    page_title="AI Stock Predictor Pro",
    page_icon="📈",
    layout="wide"
)

# Custom CSS
st.markdown("""
    <style>
    .main-header {
        font-size: 3rem;
        font-weight: bold;
        background: linear-gradient(90deg, #1f77b4, #2ca02c);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-align: center;
        margin-bottom: 2rem;
    }
    .metric-positive {
        color: #2ca02c;
        font-weight: bold;
    }
    .metric-negative {
        color: #d62728;
        font-weight: bold;
    }
    .info-box {
        background-color: #e7f3ff;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #1f77b4;
        margin: 1rem 0;
    }
    </style>
""", unsafe_allow_html=True)

st.markdown('<p class="main-header">🤖 AI Stock Price Predictor Pro</p>', unsafe_allow_html=True)
st.markdown("### Neural Network Stock Prediction with Backtesting & Multi-Stock Analysis")

# Sidebar
st.sidebar.header("⚙️ Configuration")
mode = st.sidebar.radio("Select Mode:", 
    ["📊 Single Stock Analysis", 
     "⚔️ Compare Multiple Stocks", 
     "🔙 Backtest Strategy"])

# ==========================================
# HELPER FUNCTIONS
# ==========================================

@st.cache_data(ttl=3600)
def download_stock_data(ticker, period="3mo", interval="1d"):
    """Download stock data from Yahoo Finance"""
    try:
        stock = yf.Ticker(ticker)
        data = stock.history(period=period, interval=interval)
        info = stock.info
        if len(data) > 0:
            return data, info, None
        else:
            return None, None, f"No data found for {ticker}"
    except Exception as e:
        return None, None, str(e)

def prepare_data(data, sequence_length=50, test_size=0.2):
    """Prepare data for neural network training"""
    prices = data['Close'].values.reshape(-1, 1)
    
    # Normalize prices
    scaler = MinMaxScaler(feature_range=(0, 1))
    scaled_prices = scaler.fit_transform(prices)
    
    # Create sequences
    X, y = [], []
    for i in range(sequence_length, len(scaled_prices)):
        X.append(scaled_prices[i-sequence_length:i, 0])
        y.append(scaled_prices[i, 0])
    
    X = np.array(X)
    y = np.array(y)
    X = X.reshape(X.shape[0], X.shape[1], 1)
    
    # Split into train and test
    split = int((1 - test_size) * len(X))
    X_train, X_test = X[:split], X[split:]
    y_train, y_test = y[:split], y[split:]
    
    return X_train, X_test, y_train, y_test, scaler, prices

def build_model(sequence_length, neurons=50):
    """Build the neural network model"""
    model = keras.Sequential([
        layers.LSTM(neurons, return_sequences=True, input_shape=(sequence_length, 1)),
        layers.Dropout(0.2),
        layers.LSTM(neurons, return_sequences=False),
        layers.Dropout(0.2),
        layers.Dense(25, activation='relu'),
        layers.Dense(1)
    ])
    model.compile(optimizer='adam', loss='mean_squared_error', metrics=['mae'])
    return model

def train_model(model, X_train, y_train, epochs=20, batch_size=32):
    """Train the model"""
    history = model.fit(
        X_train, y_train,
        batch_size=batch_size,
        epochs=epochs,
        verbose=0,
        validation_split=0.1
    )
    return history

def predict_future(model, last_sequence, scaler, steps=10):
    """Predict future prices"""
    predictions = []
    current_sequence = last_sequence.copy()
    
    for _ in range(steps):
        pred = model.predict(current_sequence.reshape(1, -1, 1), verbose=0)
        predictions.append(pred[0, 0])
        current_sequence = np.append(current_sequence[1:], pred[0, 0])
    
    predictions = scaler.inverse_transform(np.array(predictions).reshape(-1, 1))
    return predictions.flatten()

def calculate_metrics(y_true, y_pred):
    """Calculate prediction accuracy metrics"""
    mae = np.mean(np.abs(y_true - y_pred))
    mse = np.mean((y_true - y_pred) ** 2)
    rmse = np.sqrt(mse)
    mape = np.mean(np.abs((y_true - y_pred) / y_true)) * 100
    direction_accuracy = np.mean((np.diff(y_true.flatten()) > 0) == (np.diff(y_pred.flatten()) > 0)) * 100
    return mae, rmse, mape, direction_accuracy

def backtest_strategy(data, model, scaler, sequence_length, initial_capital=10000):
    """
    Backtest a trading strategy using the AI predictions
    Strategy: Buy when AI predicts price will go up, Sell when it predicts down
    """
    prices = data['Close'].values
    scaled_prices = scaler.transform(prices.reshape(-1, 1))
    
    # Portfolio tracking
    capital = initial_capital
    shares = 0
    portfolio_value = []
    trades = []
    positions = []  # Track when we're in/out of market
    
    # Start after we have enough data for sequence
    for i in range(sequence_length, len(scaled_prices) - 1):
        current_price = prices[i]
        
        # Get sequence and predict next price
        sequence = scaled_prices[i-sequence_length:i]
        pred_scaled = model.predict(sequence.reshape(1, sequence_length, 1), verbose=0)
        pred_price = scaler.inverse_transform(pred_scaled)[0, 0]
        
        # Trading logic
        if pred_price > current_price * 1.002:  # Predict 0.2% increase
            # BUY signal
            if shares == 0 and capital > current_price:
                shares = capital / current_price
                capital = 0
                trades.append(('BUY', i, current_price, shares))
                positions.append(1)
        
        elif pred_price < current_price * 0.998:  # Predict 0.2% decrease
            # SELL signal
            if shares > 0:
                capital = shares * current_price
                trades.append(('SELL', i, current_price, shares))
                shares = 0
                positions.append(0)
        else:
            positions.append(1 if shares > 0 else 0)
        
        # Calculate portfolio value
        if shares > 0:
            portfolio_value.append(shares * current_price)
        else:
            portfolio_value.append(capital)
    
    # Close any open position at the end
    if shares > 0:
        final_price = prices[-1]
        capital = shares * final_price
        trades.append(('SELL', len(prices)-1, final_price, shares))
        shares = 0
    
    final_value = capital
    total_return = ((final_value - initial_capital) / initial_capital) * 100
    
    # Buy and hold comparison
    buy_hold_shares = initial_capital / prices[sequence_length]
    buy_hold_value = buy_hold_shares * prices[-1]
    buy_hold_return = ((buy_hold_value - initial_capital) / initial_capital) * 100
    
    return {
        'final_value': final_value,
        'total_return': total_return,
        'trades': trades,
        'portfolio_value': portfolio_value,
        'buy_hold_return': buy_hold_return,
        'buy_hold_value': buy_hold_value,
        'num_trades': len(trades),
        'positions': positions
    }

# ==========================================
# MODE 1: SINGLE STOCK ANALYSIS
# ==========================================

if mode == "📊 Single Stock Analysis":
    st.sidebar.markdown("---")
    st.sidebar.subheader("Stock Settings")
    ticker = st.sidebar.text_input("Enter Stock Ticker:", value="AAPL").upper()
    period = st.sidebar.selectbox("Historical Data Period:", ["1mo", "3mo", "6mo", "1y", "2y"], index=1)
    interval = st.sidebar.selectbox("Data Interval:", ["1d", "1h"], index=0)
    
    st.sidebar.subheader("AI Settings")
    sequence_length = st.sidebar.slider("Sequence Length (Lookback):", 20, 100, 50)
    prediction_steps = st.sidebar.slider("Predict Next N Steps:", 5, 30, 10)
    epochs = st.sidebar.slider("Training Epochs:", 10, 50, 20)
    neurons = st.sidebar.slider("Neural Network Size:", 25, 100, 50)
    
    if st.sidebar.button("🚀 Analyze Stock", type="primary"):
        with st.spinner(f"📥 Downloading {ticker} data..."):
            data, info, error = download_stock_data(ticker, period, interval)
        
        if error:
            st.error(f"❌ Error: {error}")
        else:
            st.success(f"✅ Downloaded {len(data)} data points for {ticker}")
            
            # Stock info
            if info:
                st.subheader(f"📌 {info.get('longName', ticker)}")
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    current_price = data['Close'].iloc[-1]
                    price_change = data['Close'].iloc[-1] - data['Close'].iloc[-2]
                    price_change_pct = (price_change / data['Close'].iloc[-2]) * 100
                    st.metric("Current Price", f"${current_price:.2f}", 
                             f"{price_change:+.2f} ({price_change_pct:+.2f}%)")
                with col2:
                    st.metric("Market Cap", f"${info.get('marketCap', 0)/1e9:.2f}B")
                with col3:
                    st.metric("52W High", f"${info.get('fiftyTwoWeekHigh', 0):.2f}")
                with col4:
                    st.metric("52W Low", f"${info.get('fiftyTwoWeekLow', 0):.2f}")
            
            # Prepare data
            with st.spinner("🔧 Preparing data..."):
                X_train, X_test, y_train, y_test, scaler, all_prices = prepare_data(
                    data, sequence_length, test_size=0.2
                )
            
            st.info(f"📊 Training: {len(X_train)} sequences | Testing: {len(X_test)} sequences")
            
            # Build and train model
            with st.spinner("🧠 Building and training neural network..."):
                model = build_model(sequence_length, neurons)
                
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                for epoch in range(epochs):
                    history = model.fit(
                        X_train, y_train,
                        batch_size=32,
                        epochs=1,
                        verbose=0,
                        validation_split=0.1
                    )
                    progress = (epoch + 1) / epochs
                    progress_bar.progress(progress)
                    status_text.text(f"Training... Epoch {epoch+1}/{epochs} - Loss: {history.history['loss'][0]:.6f}")
                
                progress_bar.empty()
                status_text.empty()
            
            st.success("✅ Training complete!")
            
            # Make predictions on test data
            test_predictions = model.predict(X_test, verbose=0)
            test_predictions_prices = scaler.inverse_transform(test_predictions)
            y_test_actual = scaler.inverse_transform(y_test.reshape(-1, 1))
            
            # Calculate accuracy
            mae, rmse, mape, direction_acc = calculate_metrics(y_test_actual, test_predictions_prices)
            
            st.subheader("📈 Model Performance Metrics")
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Mean Absolute Error", f"${mae:.2f}")
            with col2:
                st.metric("RMSE", f"${rmse:.2f}")
            with col3:
                st.metric("Price Accuracy", f"{100 - mape:.1f}%")
            with col4:
                st.metric("Direction Accuracy", f"{direction_acc:.1f}%")
            
            # Plot test predictions
            st.subheader("📊 AI Predictions vs Actual Prices (Test Data)")
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                y=y_test_actual.flatten(), 
                name="Actual Prices", 
                line=dict(color='#2ca02c', width=3)
            ))
            fig.add_trace(go.Scatter(
                y=test_predictions_prices.flatten(), 
                name="AI Predictions", 
                line=dict(color='#ff7f0e', width=2, dash='dash')
            ))
            fig.update_layout(
                height=450, 
                xaxis_title="Time Steps", 
                yaxis_title="Price ($)", 
                hovermode='x unified',
                legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01)
            )
            st.plotly_chart(fig, use_container_width=True)
            
            # Predict future
            st.subheader("🔮 Future Price Predictions")
            last_sequence = scaler.transform(all_prices[-sequence_length:].reshape(-1, 1)).flatten()
            future_predictions = predict_future(model, last_sequence, scaler, prediction_steps)
            
            # Create future dates
            last_date = data.index[-1]
            if interval == "1d":
                future_dates = pd.date_range(start=last_date + timedelta(days=1), periods=prediction_steps, freq='B')
            else:
                future_dates = pd.date_range(start=last_date + timedelta(hours=1), periods=prediction_steps, freq='H')
            
            # Display predictions
            col1, col2 = st.columns([2, 1])
            
            with col1:
                fig_future = go.Figure()
                
                # Historical prices
                fig_future.add_trace(go.Scatter(
                    x=data.index[-50:], 
                    y=data['Close'].iloc[-50:], 
                    name="Historical", 
                    line=dict(color='#1f77b4', width=2)
                ))
                
                # Future predictions
                fig_future.add_trace(go.Scatter(
                    x=future_dates, 
                    y=future_predictions, 
                    name="Predicted", 
                    line=dict(color='#d62728', width=3, dash='dot'),
                    mode='lines+markers'
                ))
                
                fig_future.update_layout(
                    height=400,
                    title="Price Forecast",
                    xaxis_title="Date",
                    yaxis_title="Price ($)",
                    hovermode='x unified'
                )
                st.plotly_chart(fig_future, use_container_width=True)
            
            with col2:
                st.markdown("**Predicted Prices:**")
                pred_df = pd.DataFrame({
                    'Step': range(1, prediction_steps + 1),
                    'Date': future_dates.strftime('%Y-%m-%d'),
                    'Price': [f"${p:.2f}" for p in future_predictions],
                    'Change': [f"{((future_predictions[i] - current_price) / current_price * 100):+.2f}%" 
                              for i in range(len(future_predictions))]
                })
                st.dataframe(pred_df, hide_index=True, use_container_width=True)
                
                expected_return = ((future_predictions[-1] - current_price) / current_price) * 100
                if expected_return > 0:
                    st.success(f"📈 Expected Return: +{expected_return:.2f}%")
                else:
                    st.error(f"📉 Expected Return: {expected_return:.2f}%")

# ==========================================
# MODE 2: COMPARE MULTIPLE STOCKS
# ==========================================

elif mode == "⚔️ Compare Multiple Stocks":
    st.sidebar.markdown("---")
    st.sidebar.subheader("Stock List")
    
    default_tickers = "AAPL,MSFT,GOOGL,TSLA,NVDA"
    tickers_input = st.sidebar.text_area(
        "Enter tickers (comma-separated):", 
        value=default_tickers
    )
    tickers = [t.strip().upper() for t in tickers_input.split(',')]
    
    period = st.sidebar.selectbox("Data Period:", ["1mo", "3mo", "6mo"], index=1)
    st.sidebar.subheader("AI Settings")
    sequence_length = st.sidebar.slider("Sequence Length:", 20, 80, 40)
    prediction_steps = st.sidebar.slider("Prediction Steps:", 5, 20, 10)
    epochs = st.sidebar.slider("Training Epochs:", 10, 30, 15)
    
    if st.sidebar.button("⚔️ Compare Stocks", type="primary"):
        results = []
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for idx, ticker in enumerate(tickers):
            status_text.text(f"Analyzing {ticker}... ({idx + 1}/{len(tickers)})")
            
            data, info, error = download_stock_data(ticker, period, "1d")
            
            if error or len(data) < sequence_length + 20:
                st.warning(f"⚠️ Skipping {ticker}: Insufficient data")
                continue
            
            try:
                # Prepare and train
                X_train, X_test, y_train, y_test, scaler, all_prices = prepare_data(
                    data, sequence_length, test_size=0.2
                )
                
                model = build_model(sequence_length, neurons=40)
                model.fit(X_train, y_train, batch_size=32, epochs=epochs, verbose=0, validation_split=0.1)
                
                # Evaluate
                test_predictions = model.predict(X_test, verbose=0)
                test_predictions_prices = scaler.inverse_transform(test_predictions)
                y_test_actual = scaler.inverse_transform(y_test.reshape(-1, 1))
                mae, rmse, mape, direction_acc = calculate_metrics(y_test_actual, test_predictions_prices)
                
                # Future predictions
                last_sequence = scaler.transform(all_prices[-sequence_length:].reshape(-1, 1)).flatten()
                future_preds = predict_future(model, last_sequence, scaler, prediction_steps)
                
                current_price = data['Close'].iloc[-1]
                predicted_price = future_preds[-1]
                expected_return = ((predicted_price - current_price) / current_price) * 100
                
                results.append({
                    'Ticker': ticker,
                    'Name': info.get('longName', ticker)[:30] if info else ticker,
                    'Current Price': current_price,
                    'Predicted Price': predicted_price,
                    'Expected Return (%)': expected_return,
                    'Accuracy (%)': 100 - mape,
                    'Direction Acc (%)': direction_acc,
                    'MAE': mae
                })
                
            except Exception as e:
                st.warning(f"⚠️ Error analyzing {ticker}: {str(e)}")
            
            progress_bar.progress((idx + 1) / len(tickers))
        
        progress_bar.empty()
        status_text.empty()
        
        if results:
            st.success(f"✅ Successfully analyzed {len(results)} stocks!")
            
            # Create results dataframe
            df_results = pd.DataFrame(results)
            df_results = df_results.sort_values('Expected Return (%)', ascending=False)
            
            # Display top picks
            st.subheader("🏆 Top Stock Picks (by Expected Return)")
            
            col1, col2, col3 = st.columns(3)
            
            for idx, row in df_results.head(3).iterrows():
                with [col1, col2, col3][df_results.head(3).index.get_loc(idx)]:
                    st.markdown(f"### #{df_results.index.get_loc(idx) + 1} {row['Ticker']}")
                    st.metric("Expected Return", f"{row['Expected Return (%)']:.2f}%")
                    st.metric("Current Price", f"${row['Current Price']:.2f}")
                    st.metric("Predicted Price", f"${row['Predicted Price']:.2f}")
                    st.metric("Accuracy", f"{row['Accuracy (%)']:.1f}%")
            
            # Full comparison table
            st.subheader("📊 Complete Comparison")
            
            # Style the dataframe
            def highlight_returns(val):
                if isinstance(val, (int, float)):
                    color = 'background-color: #d4edda' if val > 0 else 'background-color: #f8d7da'
                    return color
                return ''
            
            styled_df = df_results.style.format({
                'Current Price': '${:.2f}',
                'Predicted Price': '${:.2f}',
                'Expected Return (%)': '{:+.2f}%',
                'Accuracy (%)': '{:.1f}%',
                'Direction Acc (%)': '{:.1f}%',
                'MAE': '${:.2f}'
            }).applymap(highlight_returns, subset=['Expected Return (%)'])
            
            st.dataframe(styled_df, use_container_width=True, hide_index=True)
            
            # Visualization
            st.subheader("📈 Expected Returns Comparison")
            fig = go.Figure()
            
            colors = ['#2ca02c' if x > 0 else '#d62728' for x in df_results['Expected Return (%)']]
            
            fig.add_trace(go.Bar(
                x=df_results['Ticker'],
                y=df_results['Expected Return (%)'],
                marker_color=colors,
                text=df_results['Expected Return (%)'].apply(lambda x: f'{x:+.2f}%'),
                textposition='outside'
            ))
            
            fig.update_layout(
                height=400,
                xaxis_title="Stock",
                yaxis_title="Expected Return (%)",
                showlegend=False
            )
            st.plotly_chart(fig, use_container_width=True)
            
            # Investment recommendation
            best_stock = df_results.iloc[0]
            if best_stock['Expected Return (%)'] > 5:
                st.success(f"💡 **Top Recommendation**: {best_stock['Ticker']} shows the highest expected return of {best_stock['Expected Return (%)']:.2f}% with {best_stock['Accuracy (%)']:.1f}% prediction accuracy!")
            else:
                st.info("💡 **Note**: Current market conditions show modest expected returns across analyzed stocks.")

# ==========================================
# MODE 3: BACKTEST STRATEGY
# ==========================================

elif mode == "🔙 Backtest Strategy":
    st.sidebar.markdown("---")
    st.sidebar.subheader("Backtest Settings")
    ticker = st.sidebar.text_input("Enter Stock Ticker:", value="AAPL").upper()
    period = st.sidebar.selectbox("Backtest Period:", ["3mo", "6mo", "1y", "2y"], index=2)
    initial_capital = st.sidebar.number_input("Initial Capital ($):", min_value=1000, value=10000, step=1000)
    
    st.sidebar.subheader("AI Settings")
    sequence_length = st.sidebar.slider("Sequence Length:", 20, 80, 50)
    epochs = st.sidebar.slider("Training Epochs:", 10, 30, 20)
    
    st.markdown("""
    <div class="info-box">
    <strong>📖 How Backtesting Works:</strong><br>
    The AI predicts whether the price will go up or down. If it predicts up by >0.2%, we BUY. 
    If it predicts down by >0.2%, we SELL. We track the portfolio value over time and compare 
    it to a simple "buy and hold" strategy.
    </div>
    """, unsafe_allow_html=True)
    
    if st.sidebar.button("🔙 Run Backtest", type="primary"):
        with st.spinner(f"📥 Downloading {ticker} data..."):
            data, info, error = download_stock_data(ticker, period, "1d")
        
        if error:
            st.error(f"❌ Error: {error}")
        elif len(data) < sequence_length + 50:
            st.error(f"❌ Insufficient data. Need at least {sequence_length + 50} data points.")
        else:
            st.success(f"✅ Downloaded {len(data)} days of data for {ticker}")
            
            # Display stock info
            if info:
                st.subheader(f"📌 {info.get('longName', ticker)}")
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Current Price", f"${data['Close'].iloc[-1]:.2f}")
                with col2:
                    st.metric("Start Price", f"${data['Close'].iloc[0]:.2f}")
                with col3:
                    period_return = ((data['Close'].iloc[-1] - data['Close'].iloc[0]) / data['Close'].iloc[0]) * 100
                    st.metric("Period Return", f"{period_return:+.2f}%")
            
            # Prepare data and train model
            with st.spinner("🧠 Training AI model for backtesting..."):
                X_train, X_test, y_train, y_test, scaler, all_prices = prepare_data(
                    data, sequence_length, test_size=0.1
                )
                
                model = build_model(sequence_length, neurons=50)
                
                progress_bar = st.progress(0)
                for epoch in range(epochs):
                    model.fit(X_train, y_train, batch_size=32, epochs=1, verbose=0, validation_split=0.1)
                    progress_bar.progress((epoch + 1) / epochs)
                progress_bar.empty()
            
            st.success("✅ Model trained! Running backtest...")
            
            # Run backtest
            with st.spinner("📊 Simulating trades..."):
                backtest_results = backtest_strategy(data, model, scaler, sequence_length, initial_capital)
            
            # Display results
            st.subheader("💰 Backtest Results")
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Final Portfolio Value", 
                         f"${backtest_results['final_value']:.2f}",
                         f"{backtest_results['total_return']:+.2f}%")
            
            with col2:
                st.metric("Buy & Hold Value", 
                         f"${backtest_results['buy_hold_value']:.2f}",
                         f"{backtest_results['buy_hold_return']:+.2f}%")
            
            with col3:
                outperformance = backtest_results['total_return'] - backtest_results['buy_hold_return']
                st.metric("Outperformance", 
                         f"{outperformance:+.2f}%",
                         "vs Buy & Hold")
            
            with col4:
                st.metric("Number of Trades", backtest_results['num_trades'])
            
            # Performance comparison
            st.subheader("📈 Strategy Performance vs Buy & Hold")
            
            fig = go.Figure()
            
            # AI Strategy portfolio value
            fig.add_trace(go.Scatter(
                x=data.index[sequence_length:-1],
                y=backtest_results['portfolio_value'],
                name='AI Trading Strategy',
                line=dict(color='#ff7f0e', width=3),
                fill='tozeroy',
                fillcolor='rgba(255, 127, 14, 0.1)'
            ))
            
            # Buy and hold comparison
            buy_hold_values = []
            buy_hold_shares = initial_capital / data['Close'].iloc[sequence_length]
            for i in range(sequence_length, len(data) - 1):
                buy_hold_values.append(buy_hold_shares * data['Close'].iloc[i])
            
            fig.add_trace(go.Scatter(
                x=data.index[sequence_length:-1],
                y=buy_hold_values,
                name='Buy & Hold Strategy',
                line=dict(color='#1f77b4', width=2, dash='dash')
            ))
            
            fig.update_layout(
                height=450,
                xaxis_title="Date",
                yaxis_title="Portfolio Value ($)",
                hovermode='x unified',
                legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01)
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            # Trade history
            st.subheader("📋 Trade History")
            
            if backtest_results['trades']:
                trades_df = pd.DataFrame(backtest_results['trades'], 
                                        columns=['Action', 'Index', 'Price', 'Shares'])
                trades_df['Date'] = [data.index[int(idx)] for idx in trades_df['Index']]
                trades_df['Value'] = trades_df['Price'] * trades_df['Shares']
                trades_df = trades_df[['Date', 'Action', 'Price', 'Shares', 'Value']]
                
                trades_df['Price'] = trades_df['Price'].apply(lambda x: f"${x:.2f}")
                trades_df['Shares'] = trades_df['Shares'].apply(lambda x: f"{x:.4f}")
                trades_df['Value'] = trades_df['Value'].apply(lambda x: f"${x:.2f}")
                
                st.dataframe(trades_df, use_container_width=True, hide_index=True)
            else:
                st.info("No trades were executed during the backtest period.")
            
            # Performance summary
            st.subheader("📊 Performance Summary")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("**AI Trading Strategy:**")
                profit_loss = backtest_results['final_value'] - initial_capital
                st.write(f"- Initial Capital: ${initial_capital:,.2f}")
                st.write(f"- Final Value: ${backtest_results['final_value']:,.2f}")
                st.write(f"- Profit/Loss: ${profit_loss:+,.2f}")
                st.write(f"- Return: {backtest_results['total_return']:+.2f}%")
                st.write(f"- Total Trades: {backtest_results['num_trades']}")
            
            with col2:
                st.markdown("**Buy & Hold Strategy:**")
                bh_profit = backtest_results['buy_hold_value'] - initial_capital
                st.write(f"- Initial Capital: ${initial_capital:,.2f}")
                st.write(f"- Final Value: ${backtest_results['buy_hold_value']:,.2f}")
                st.write(f"- Profit/Loss: ${bh_profit:+,.2f}")
                st.write(f"- Return: {backtest_results['buy_hold_return']:+.2f}%")
                st.write(f"- Total Trades: 2 (Buy at start, Hold)")
            
            # Verdict
            if backtest_results['total_return'] > backtest_results['buy_hold_return']:
                st.success(f"🎉 **The AI strategy outperformed Buy & Hold by {outperformance:.2f}%!**")
            elif backtest_results['total_return'] > 0:
                st.info(f"📊 **The AI strategy was profitable but underperformed Buy & Hold by {abs(outperformance):.2f}%**")
            else:
                st.warning(f"⚠️ **The AI strategy resulted in a loss. Buy & Hold performed better by {abs(outperformance):.2f}%**")
            
            st.markdown("""
            ---
            **⚠️ Disclaimer:** Past performance does not guarantee future results. This backtest does not account for:
            - Transaction fees and commissions
            - Slippage (difference between expected and actual trade prices)
            - Market impact of large orders
            - Real-world execution delays
            
            Always do your own research and consult with financial advisors before making investment decisions.
            """)

# Footer
st.sidebar.markdown("---")
st.sidebar.markdown("""
### 📚 About This App
This AI-powered stock predictor uses:
- **LSTM Neural Networks** for time series prediction
- **Real market data** from Yahoo Finance
- **Backtesting** to validate strategies

**⚠️ Disclaimer:** This is for educational purposes only. 
Not financial advice!
""")

st.sidebar.markdown("---")
st.sidebar.info("💡 **Tip:** Try different sequence lengths and epochs to optimize predictions!")
