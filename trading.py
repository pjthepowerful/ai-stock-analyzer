import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

# Import TensorFlow/Keras for REAL AI (Neural Networks)
try:
    import tensorflow as tf
    from tensorflow import keras
    from tensorflow.keras import layers
    from tensorflow.keras.models import Sequential
    from tensorflow.keras.layers import LSTM, Dense, Dropout
    from sklearn.preprocessing import MinMaxScaler
    NEURAL_NETWORK_AVAILABLE = True
except ImportError:
    NEURAL_NETWORK_AVAILABLE = False
    st.error("⚠️ TensorFlow not available. Install with: pip install tensorflow")

st.set_page_config(page_title="LSTM AI Stock Predictor", page_icon="🧠", layout="wide")

# Header
st.markdown("""
    <style>
    .main-header {
        font-size: 3.5rem;
        font-weight: bold;
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-align: center;
        margin-bottom: 1rem;
    }
    .sub-header {
        text-align: center;
        color: #666;
        font-size: 1.2rem;
        margin-bottom: 2rem;
    }
    </style>
""", unsafe_allow_html=True)

st.markdown('<p class="main-header">🧠 LSTM Neural Network Stock Predictor</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-header">Deep Learning AI • Real Neural Networks • Like ChatGPT for Stocks</p>', unsafe_allow_html=True)

# Info banner
st.info("🔥 **This uses REAL AI**: LSTM Neural Networks - the same technology behind ChatGPT and advanced sequence prediction!")

# Sidebar
st.sidebar.header("⚙️ Neural Network Settings")

mode = st.sidebar.radio("Select Mode:", 
    ["🧠 Single Stock (LSTM)", 
     "⚔️ Compare Stocks (LSTM)", 
     "🔙 Backtest Strategy (LSTM)"])

# Helper Functions
@st.cache_data(ttl=3600)
def download_stock_data(ticker, period="3mo", interval="1d"):
    """Download stock data"""
    try:
        stock = yf.Ticker(ticker)
        data = stock.history(period=period, interval=interval)
        info = stock.info
        if len(data) > 0:
            return data, info, None
        return None, None, f"No data found for {ticker}"
    except Exception as e:
        return None, None, str(e)

def create_lstm_sequences(data, sequence_length=60):
    """Create sequences for LSTM neural network"""
    prices = data['Close'].values.reshape(-1, 1)
    
    # Normalize data (neural networks need this)
    scaler = MinMaxScaler(feature_range=(0, 1))
    scaled_data = scaler.fit_transform(prices)
    
    X, y = [], []
    for i in range(sequence_length, len(scaled_data)):
        X.append(scaled_data[i-sequence_length:i, 0])
        y.append(scaled_data[i, 0])
    
    X = np.array(X)
    y = np.array(y)
    
    # Reshape for LSTM [samples, time steps, features]
    X = X.reshape(X.shape[0], X.shape[1], 1)
    
    return X, y, scaler

def build_lstm_model(sequence_length, neurons=50):
    """
    Build LSTM Neural Network
    
    LSTM = Long Short-Term Memory
    - Type of Recurrent Neural Network (RNN)
    - Designed for sequence data (like stock prices over time)
    - Has "memory" of past patterns
    - Same tech used in ChatGPT for language
    """
    model = Sequential([
        # First LSTM layer - learns patterns in sequences
        LSTM(neurons, return_sequences=True, input_shape=(sequence_length, 1)),
        Dropout(0.2),  # Prevents overfitting
        
        # Second LSTM layer - learns deeper patterns
        LSTM(neurons, return_sequences=False),
        Dropout(0.2),
        
        # Dense layers - combines learned patterns
        Dense(25, activation='relu'),
        
        # Output layer - predicts next price
        Dense(1)
    ])
    
    # Adam optimizer - smart learning algorithm
    model.compile(optimizer='adam', loss='mean_squared_error', metrics=['mae'])
    
    return model

def predict_future_lstm(model, last_sequence, scaler, steps=10):
    """Predict future using LSTM"""
    predictions = []
    current_seq = last_sequence.copy()
    
    for _ in range(steps):
        # Predict next value
        pred = model.predict(current_seq.reshape(1, -1, 1), verbose=0)
        predictions.append(pred[0, 0])
        
        # Update sequence (slide window forward)
        current_seq = np.append(current_seq[1:], pred[0, 0])
    
    # Inverse transform to get actual prices
    predictions = scaler.inverse_transform(np.array(predictions).reshape(-1, 1))
    return predictions.flatten()

def calculate_metrics(y_true, y_pred):
    """Calculate prediction metrics"""
    mae = np.mean(np.abs(y_true - y_pred))
    mse = np.mean((y_true - y_pred) ** 2)
    rmse = np.sqrt(mse)
    mape = np.mean(np.abs((y_true - y_pred) / y_true)) * 100
    
    # Direction accuracy
    if len(y_true) > 1:
        true_direction = np.diff(y_true.flatten()) > 0
        pred_direction = np.diff(y_pred.flatten()) > 0
        direction_accuracy = np.mean(true_direction == pred_direction) * 100
    else:
        direction_accuracy = 0
    
    return mae, rmse, mape, direction_accuracy

# ==========================================
# MODE 1: SINGLE STOCK LSTM ANALYSIS
# ==========================================

if mode == "🧠 Single Stock (LSTM)":
    
    if not NEURAL_NETWORK_AVAILABLE:
        st.error("❌ TensorFlow not installed. Cannot use LSTM neural networks.")
        st.stop()
    
    st.sidebar.markdown("---")
    st.sidebar.subheader("Stock Settings")
    ticker = st.sidebar.text_input("Stock Ticker:", value="AAPL").upper()
    period = st.sidebar.selectbox("Data Period:", ["1mo", "3mo", "6mo", "1y"], index=2)
    
    st.sidebar.subheader("LSTM Neural Network")
    sequence_length = st.sidebar.slider("Sequence Length (lookback):", 30, 100, 60)
    neurons = st.sidebar.slider("LSTM Neurons:", 25, 100, 50)
    epochs = st.sidebar.slider("Training Epochs:", 10, 50, 20)
    prediction_steps = st.sidebar.slider("Predict Steps:", 5, 30, 10)
    
    # Info about neural network
    with st.sidebar.expander("ℹ️ What is LSTM?"):
        st.markdown("""
        **LSTM = Long Short-Term Memory**
        
        - Type of Neural Network
        - Has "memory" of past patterns
        - Used in ChatGPT, translation, etc.
        - Perfect for time series like stocks
        
        **Your Network:**
        - 2 LSTM layers with {0} neurons each
        - Dropout layers (prevent overfitting)
        - Dense layers (combine patterns)
        - Total: ~{1} parameters to learn
        """.format(neurons, neurons * neurons * 4))
    
    if st.sidebar.button("🧠 Train Neural Network", type="primary"):
        
        # Download data
        with st.spinner(f"📥 Downloading {ticker} data..."):
            data, info, error = download_stock_data(ticker, period, "1d")
        
        if error:
            st.error(f"❌ {error}")
        elif len(data) < sequence_length + 20:
            st.error(f"❌ Need at least {sequence_length + 20} data points. Got {len(data)}.")
        else:
            st.success(f"✅ Downloaded {len(data)} days of data")
            
            # Display stock info
            current_price = data['Close'].iloc[-1]
            price_change = data['Close'].iloc[-1] - data['Close'].iloc[-2]
            price_change_pct = (price_change / data['Close'].iloc[-2]) * 100
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Current Price", f"${current_price:.2f}", 
                         f"{price_change:+.2f} ({price_change_pct:+.2f}%)")
            with col2:
                st.metric("Period High", f"${data['High'].max():.2f}")
            with col3:
                st.metric("Period Low", f"${data['Low'].min():.2f}")
            with col4:
                st.metric("Data Points", len(data))
            
            # Prepare sequences
            with st.spinner("🔧 Creating training sequences for neural network..."):
                X, y, scaler = create_lstm_sequences(data, sequence_length)
                
                # Split
                split = int(0.8 * len(X))
                X_train, X_test = X[:split], X[split:]
                y_train, y_test = y[:split], y[split:]
            
            st.info(f"📊 Training: {len(X_train)} sequences | Testing: {len(X_test)} sequences")
            
            # Build model
            st.success("🏗️ Building LSTM neural network architecture...")
            model = build_lstm_model(sequence_length, neurons)
            
            # Show architecture
            with st.expander("🔍 View Neural Network Architecture"):
                # Create architecture visualization
                st.text(f"""
Neural Network Architecture:
════════════════════════════════════════════════════

Input Layer: [{sequence_length} time steps]
    ↓
LSTM Layer 1: {neurons} neurons (with memory cells)
    ↓
Dropout: 20% (prevents overfitting)
    ↓
LSTM Layer 2: {neurons} neurons (deeper patterns)
    ↓
Dropout: 20%
    ↓
Dense Layer: 25 neurons (combination)
    ↓
Output: 1 value (predicted price)

════════════════════════════════════════════════════
Total Parameters: ~{neurons * neurons * 4 + 25 + 1:,}
Trainable: Yes
Optimizer: Adam (adaptive learning rate)
Loss Function: Mean Squared Error
════════════════════════════════════════════════════
                """)
            
            # Train neural network
            st.markdown("### 🧠 Training Neural Network...")
            st.write("This is where the AI learns patterns from historical data!")
            
            progress_bar = st.progress(0)
            status_text = st.empty()
            loss_chart_placeholder = st.empty()
            
            # Training history
            history_loss = []
            history_mae = []
            
            # Train epoch by epoch to show progress
            for epoch in range(epochs):
                # Train for 1 epoch
                h = model.fit(
                    X_train, y_train,
                    batch_size=32,
                    epochs=1,
                    verbose=0,
                    validation_split=0.1
                )
                
                # Track metrics
                history_loss.append(h.history['loss'][0])
                history_mae.append(h.history['mae'][0])
                
                # Update progress
                progress = (epoch + 1) / epochs
                progress_bar.progress(progress)
                status_text.text(
                    f"Epoch {epoch+1}/{epochs} | "
                    f"Loss: {h.history['loss'][0]:.6f} | "
                    f"MAE: {h.history['mae'][0]:.6f}"
                )
                
                # Update loss chart every 5 epochs
                if (epoch + 1) % 5 == 0 or epoch == epochs - 1:
                    fig_loss = go.Figure()
                    fig_loss.add_trace(go.Scatter(
                        y=history_loss,
                        name="Training Loss",
                        line=dict(color='#667eea', width=2)
                    ))
                    fig_loss.update_layout(
                        title="Neural Network Learning Progress",
                        xaxis_title="Epoch",
                        yaxis_title="Loss (Lower = Better)",
                        height=300
                    )
                    loss_chart_placeholder.plotly_chart(fig_loss, use_container_width=True)
            
            progress_bar.empty()
            status_text.empty()
            st.success("✅ Neural network training complete!")
            
            # Make predictions on test data
            st.markdown("### 📊 Testing Neural Network on Unseen Data")
            
            with st.spinner("🔮 Making predictions..."):
                test_predictions_scaled = model.predict(X_test, verbose=0)
                test_predictions = scaler.inverse_transform(test_predictions_scaled)
                y_test_actual = scaler.inverse_transform(y_test.reshape(-1, 1))
            
            # Calculate metrics
            mae, rmse, mape, direction_acc = calculate_metrics(y_test_actual, test_predictions)
            
            # Display metrics
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Mean Absolute Error", f"${mae:.2f}")
            with col2:
                st.metric("RMSE", f"${rmse:.2f}")
            with col3:
                accuracy = 100 - mape
                st.metric("Price Accuracy", f"{accuracy:.1f}%", 
                         "🔥 Excellent" if accuracy > 90 else "✅ Good" if accuracy > 85 else "⚠️ Okay")
            with col4:
                st.metric("Direction Accuracy", f"{direction_acc:.1f}%",
                         "🔥 Excellent" if direction_acc > 70 else "✅ Good" if direction_acc > 60 else "⚠️ Okay")
            
            # Plot predictions vs actual
            st.markdown("### 📈 Neural Network Predictions vs Reality")
            fig = go.Figure()
            
            fig.add_trace(go.Scatter(
                y=y_test_actual.flatten(),
                name="Actual Prices",
                line=dict(color='#2ecc71', width=3),
                mode='lines'
            ))
            
            fig.add_trace(go.Scatter(
                y=test_predictions.flatten(),
                name="LSTM Predictions",
                line=dict(color='#e74c3c', width=2, dash='dash'),
                mode='lines'
            ))
            
            fig.update_layout(
                height=450,
                xaxis_title="Time Steps (Test Period)",
                yaxis_title="Price ($)",
                hovermode='x unified',
                legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01)
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            # Future predictions
            st.markdown("### 🔮 Future Price Predictions (LSTM Neural Network)")
            
            with st.spinner("Predicting future prices..."):
                # Get last sequence
                last_sequence_scaled = scaler.transform(
                    data['Close'].values[-sequence_length:].reshape(-1, 1)
                ).flatten()
                
                future_predictions = predict_future_lstm(
                    model, last_sequence_scaled, scaler, prediction_steps
                )
            
            col1, col2 = st.columns([2, 1])
            
            with col1:
                # Forecast chart
                fig_future = go.Figure()
                
                # Historical
                fig_future.add_trace(go.Scatter(
                    x=data.index[-60:],
                    y=data['Close'].iloc[-60:],
                    name="Historical Prices",
                    line=dict(color='#3498db', width=2)
                ))
                
                # Future
                future_dates = pd.date_range(
                    start=data.index[-1] + timedelta(days=1),
                    periods=prediction_steps,
                    freq='D'
                )
                
                fig_future.add_trace(go.Scatter(
                    x=future_dates,
                    y=future_predictions,
                    name="LSTM Forecast",
                    line=dict(color='#e74c3c', width=3, dash='dot'),
                    mode='lines+markers',
                    marker=dict(size=8)
                ))
                
                fig_future.update_layout(
                    title="LSTM Neural Network Forecast",
                    height=400,
                    xaxis_title="Date",
                    yaxis_title="Price ($)",
                    hovermode='x unified'
                )
                
                st.plotly_chart(fig_future, use_container_width=True)
            
            with col2:
                st.markdown("**🔮 Predicted Prices:**")
                
                for i, pred in enumerate(future_predictions, 1):
                    change = ((pred - current_price) / current_price) * 100
                    color = "🟢" if change > 0 else "🔴"
                    st.write(f"{color} Day {i}: ${pred:.2f} ({change:+.1f}%)")
                
                st.markdown("---")
                expected_return = ((future_predictions[-1] - current_price) / current_price) * 100
                
                if expected_return > 5:
                    st.success(f"🚀 **Strong Buy Signal**\nExpected Return: +{expected_return:.2f}%")
                elif expected_return > 0:
                    st.info(f"📈 **Moderate Buy**\nExpected Return: +{expected_return:.2f}%")
                elif expected_return > -5:
                    st.warning(f"📊 **Hold/Neutral**\nExpected Return: {expected_return:.2f}%")
                else:
                    st.error(f"📉 **Sell Signal**\nExpected Return: {expected_return:.2f}%")
            
            # Neural network insights
            st.markdown("### 🧠 What the Neural Network Learned")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("""
                **Pattern Recognition:**
                - ✅ Analyzed {0} days of price history
                - ✅ Trained on {1} different sequences
                - ✅ Learned {2:,} pattern parameters
                - ✅ Achieved {3:.1f}% accuracy
                """.format(len(data), len(X_train), neurons * neurons * 4, 100 - mape))
            
            with col2:
                st.markdown("""
                **This LSTM Network:**
                - 🧠 Has memory of past {0} days
                - 🔄 Updates predictions sequentially
                - 📊 Considers price momentum & trends
                - 🎯 Optimized for time series data
                """.format(sequence_length))

# ==========================================
# MODE 2: COMPARE STOCKS (LSTM)
# ==========================================

elif mode == "⚔️ Compare Stocks (LSTM)":
    
    if not NEURAL_NETWORK_AVAILABLE:
        st.error("❌ TensorFlow not installed")
        st.stop()
    
    st.sidebar.markdown("---")
    tickers_input = st.sidebar.text_area(
        "Enter tickers (comma-separated):",
        value="AAPL,MSFT,GOOGL,NVDA,TSLA"
    )
    tickers = [t.strip().upper() for t in tickers_input.split(',')]
    
    period = st.sidebar.selectbox("Period:", ["3mo", "6mo"], index=0)
    sequence_length = st.sidebar.slider("Sequence Length:", 30, 80, 50)
    epochs = st.sidebar.slider("Epochs:", 10, 25, 15)
    
    if st.sidebar.button("⚔️ Compare with LSTM", type="primary"):
        results = []
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for idx, ticker in enumerate(tickers):
            status_text.text(f"🧠 Training LSTM for {ticker}... ({idx+1}/{len(tickers)})")
            
            data, info, error = download_stock_data(ticker, period, "1d")
            
            if error or len(data) < sequence_length + 30:
                st.warning(f"⚠️ Skipping {ticker}: Insufficient data")
                continue
            
            try:
                # Prepare data
                X, y, scaler = create_lstm_sequences(data, sequence_length)
                split = int(0.8 * len(X))
                X_train, X_test = X[:split], X[split:]
                y_train, y_test = y[:split], y[split:]
                
                # Build and train
                model = build_lstm_model(sequence_length, neurons=40)
                model.fit(X_train, y_train, batch_size=32, epochs=epochs, verbose=0, validation_split=0.1)
                
                # Predict
                test_pred = model.predict(X_test, verbose=0)
                test_pred_prices = scaler.inverse_transform(test_pred)
                y_test_prices = scaler.inverse_transform(y_test.reshape(-1, 1))
                
                mae, rmse, mape, direction_acc = calculate_metrics(y_test_prices, test_pred_prices)
                
                # Future prediction
                last_seq = scaler.transform(data['Close'].values[-sequence_length:].reshape(-1, 1)).flatten()
                future_preds = predict_future_lstm(model, last_seq, scaler, 10)
                
                current_price = data['Close'].iloc[-1]
                predicted_price = future_preds[-1]
                expected_return = ((predicted_price - current_price) / current_price) * 100
                
                results.append({
                    'Ticker': ticker,
                    'Name': info.get('longName', ticker)[:25] if info else ticker,
                    'Current': current_price,
                    'Predicted': predicted_price,
                    'Return (%)': expected_return,
                    'Accuracy (%)': 100 - mape,
                    'Direction (%)': direction_acc
                })
                
            except Exception as e:
                st.warning(f"⚠️ Error with {ticker}: {str(e)}")
            
            progress_bar.progress((idx + 1) / len(tickers))
        
        progress_bar.empty()
        status_text.empty()
        
        if results:
            st.success(f"✅ LSTM analysis complete for {len(results)} stocks!")
            
            df = pd.DataFrame(results).sort_values('Return (%)', ascending=False)
            
            # Top 3
            st.markdown("### 🏆 Top 3 Picks (LSTM Neural Network)")
            cols = st.columns(3)
            
            for idx, (_, row) in enumerate(df.head(3).iterrows()):
                with cols[idx]:
                    medal = ["🥇", "🥈", "🥉"][idx]
                    st.markdown(f"### {medal} {row['Ticker']}")
                    st.metric("Expected Return", f"{row['Return (%)']:.2f}%")
                    st.metric("Current", f"${row['Current']:.2f}")
                    st.metric("LSTM Accuracy", f"{row['Accuracy (%)']:.1f}%")
            
            # Table
            st.markdown("### 📊 Complete LSTM Analysis")
            st.dataframe(
                df.style.format({
                    'Current': '${:.2f}',
                    'Predicted': '${:.2f}',
                    'Return (%)': '{:+.2f}%',
                    'Accuracy (%)': '{:.1f}%',
                    'Direction (%)': '{:.1f}%'
                }),
                use_container_width=True,
                hide_index=True
            )
            
            # Chart
            fig = go.Figure()
            colors = ['#2ecc71' if x > 0 else '#e74c3c' for x in df['Return (%)']]
            fig.add_trace(go.Bar(
                x=df['Ticker'],
                y=df['Return (%)'],
                marker_color=colors,
                text=df['Return (%)'].apply(lambda x: f'{x:+.1f}%'),
                textposition='outside'
            ))
            fig.update_layout(
                title="LSTM Expected Returns Comparison",
                height=400,
                yaxis_title="Expected Return (%)",
                showlegend=False
            )
            st.plotly_chart(fig, use_container_width=True)

# ==========================================
# MODE 3: BACKTEST (LSTM)
# ==========================================

else:  # Backtest mode
    st.markdown("### 🔙 LSTM Backtest")
    st.info("💡 Backtesting with LSTM coming soon! This requires historical prediction simulation.")
    
    st.markdown("""
    **What LSTM Backtesting Would Show:**
    - Train LSTM on historical data
    - Make predictions day-by-day
    - Simulate buy/sell based on LSTM signals
    - Compare to buy-and-hold strategy
    
    **Why It's Complex:**
    - Need to retrain network for each time point
    - Computationally intensive
    - Takes 10-20 minutes to backtest properly
    
    **Alternative:** Use the lightweight version for backtesting, or run LSTM locally with more time.
    """)

# Footer
st.sidebar.markdown("---")
st.sidebar.markdown("""
### 🧠 About LSTM

**Long Short-Term Memory** is a type of Recurrent Neural Network (RNN) designed for sequence data.

**Used in:**
- ChatGPT (language prediction)
- Google Translate
- Voice recognition
- Stock prediction
- Weather forecasting

**Your Network:**
- 2 LSTM layers
- Dropout regularization  
- Dense output layer
- Adam optimizer

This is **REAL deep learning AI!**
""")

st.sidebar.warning("⚠️ Educational purposes only. Not financial advice!")
