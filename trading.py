import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import MinMaxScaler
import plotly.graph_objects as go
from datetime import timedelta

st.set_page_config(page_title="Stock Predictor", page_icon="📈", layout="wide")

st.title("🤖 AI Stock Price Predictor")
st.markdown("### Simple & Fast Machine Learning Predictions")

# Sidebar
ticker = st.sidebar.text_input("Stock Ticker:", value="AAPL").upper()
period = st.sidebar.selectbox("Period:", ["1mo", "3mo", "6mo", "1y"], index=1)
predict_days = st.sidebar.slider("Predict Days:", 5, 20, 10)

if st.sidebar.button("🚀 Predict", type="primary"):
    with st.spinner(f"Analyzing {ticker}..."):
        try:
            # Download data
            stock = yf.Ticker(ticker)
            data = stock.history(period=period)
            
            if len(data) == 0:
                st.error("No data found!")
            else:
                # Display current info
                current_price = data['Close'].iloc[-1]
                st.success(f"✅ Downloaded {len(data)} days of data")
                
                col1, col2, col3 = st.columns(3)
                col1.metric("Current Price", f"${current_price:.2f}")
                col2.metric("High", f"${data['High'].max():.2f}")
                col3.metric("Low", f"${data['Low'].min():.2f}")
                
                # Prepare data for ML
                lookback = 30
                prices = data['Close'].values
                
                X, y = [], []
                for i in range(lookback, len(prices)):
                    X.append(prices[i-lookback:i])
                    y.append(prices[i])
                
                X = np.array(X)
                y = np.array(y)
                
                # Split data
                split = int(0.8 * len(X))
                X_train, X_test = X[:split], X[split:]
                y_train, y_test = y[:split], y[split:]
                
                # Train model
                with st.spinner("🤖 Training AI..."):
                    model = RandomForestRegressor(n_estimators=50, max_depth=10, random_state=42)
                    model.fit(X_train, y_train)
                
                st.success("✅ Training complete!")
                
                # Test predictions
                y_pred = model.predict(X_test)
                mae = np.mean(np.abs(y_test - y_pred))
                accuracy = 100 - (mae / np.mean(y_test) * 100)
                
                col1, col2 = st.columns(2)
                col1.metric("Prediction Accuracy", f"{accuracy:.1f}%")
                col2.metric("Avg Error", f"${mae:.2f}")
                
                # Plot test results
                st.subheader("📊 Test Predictions vs Actual")
                fig = go.Figure()
                fig.add_trace(go.Scatter(y=y_test, name="Actual", line=dict(color='green', width=2)))
                fig.add_trace(go.Scatter(y=y_pred, name="Predicted", line=dict(color='orange', width=2, dash='dash')))
                fig.update_layout(height=400, xaxis_title="Time", yaxis_title="Price ($)")
                st.plotly_chart(fig, use_container_width=True)
                
                # Future predictions
                st.subheader("🔮 Future Predictions")
                future_preds = []
                last_seq = prices[-lookback:].copy()
                
                for _ in range(predict_days):
                    pred = model.predict(last_seq.reshape(1, -1))[0]
                    future_preds.append(pred)
                    last_seq = np.append(last_seq[1:], pred)
                
                # Plot future
                fig2 = go.Figure()
                fig2.add_trace(go.Scatter(
                    x=data.index[-30:], 
                    y=data['Close'].iloc[-30:], 
                    name="Historical",
                    line=dict(color='blue', width=2)
                ))
                
                future_dates = pd.date_range(
                    start=data.index[-1] + timedelta(days=1), 
                    periods=predict_days, 
                    freq='D'
                )
                
                fig2.add_trace(go.Scatter(
                    x=future_dates, 
                    y=future_preds, 
                    name="Forecast",
                    line=dict(color='red', width=3, dash='dot'),
                    mode='lines+markers'
                ))
                
                fig2.update_layout(height=400, title="Price Forecast")
                st.plotly_chart(fig2, use_container_width=True)
                
                # Show predictions
                st.markdown("**Predicted Prices:**")
                for i, pred in enumerate(future_preds, 1):
                    change = ((pred - current_price) / current_price) * 100
                    st.write(f"Day {i}: ${pred:.2f} ({change:+.1f}%)")
                
                expected_return = ((future_preds[-1] - current_price) / current_price) * 100
                if expected_return > 0:
                    st.success(f"📈 Expected Return: +{expected_return:.2f}%")
                else:
                    st.error(f"📉 Expected Return: {expected_return:.2f}%")
                
        except Exception as e:
            st.error(f"Error: {str(e)}")

st.sidebar.markdown("---")
st.sidebar.info("⚡ Lightweight ML model using Random Forest")
st.sidebar.warning("⚠️ Educational purposes only!")
