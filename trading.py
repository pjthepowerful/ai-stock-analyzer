import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timedelta
import warnings
import random
import time
import json
import os
warnings.filterwarnings('ignore')

# Import TensorFlow/Keras
try:
    import tensorflow as tf
    from tensorflow import keras
    from tensorflow.keras import layers
    from sklearn.preprocessing import MinMaxScaler
    NEURAL_NETWORK_AVAILABLE = True
except ImportError:
    NEURAL_NETWORK_AVAILABLE = False

st.set_page_config(page_title="AI Stock Predictor", page_icon="🧠", layout="wide")

# Custom CSS
st.markdown("""
    <style>
    .main-header {
        font-size: 3.5rem;
        font-weight: bold;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-align: center;
        margin-bottom: 0.5rem;
    }
    .sub-header {
        text-align: center;
        color: #666;
        font-size: 1.2rem;
        margin-bottom: 2rem;
    }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# GLOBAL STATE - AUTO-TRAINS ON EACH RUN
# ==========================================

# ==========================================
# PERSISTENT STORAGE (CLOUD)
# ==========================================

STATE_FILE = '/tmp/evolution_state.json'

def save_evolution_state():
    """Save evolution progress to cloud storage"""
    state = {
        'evolved_config': st.session_state.evolved_config,
        'evolution_stats': st.session_state.evolution_stats,
        'saved_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    try:
        with open(STATE_FILE, 'w') as f:
            json.dump(state, f, indent=2)
        return True
    except Exception as e:
        print(f"Error saving state: {e}")
        return False

def load_evolution_state():
    """Load evolution progress from cloud storage"""
    try:
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, 'r') as f:
                state = json.load(f)
            return state
        return None
    except Exception as e:
        print(f"Error loading state: {e}")
        return None

# ==========================================
# GLOBAL STATE - AUTO-TRAINS ON EACH RUN
# ==========================================

# Try to load saved state first
if 'state_loaded' not in st.session_state:
    saved_state = load_evolution_state()
    if saved_state:
        st.session_state.evolved_config = saved_state.get('evolved_config', {
            'neurons_layer1': 50,
            'neurons_layer2': 50,
            'dropout': 0.2,
            'lookback': 50,
            'generation': 0,
            'fitness': 0,
            'training_stocks': 'Initializing...',
            'last_updated': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        st.session_state.evolution_stats = saved_state.get('evolution_stats', {
            'total_tested': 0,
            'best_fitness_history': [],
            'current_generation': 0,
            'last_train_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        st.session_state.state_loaded = True
        st.session_state.auto_train_done = True  # Don't auto-train if we loaded state
    else:
        # Initialize fresh
        st.session_state.evolved_config = {
            'neurons_layer1': 50,
            'neurons_layer2': 50,
            'dropout': 0.2,
            'lookback': 50,
            'generation': 0,
            'fitness': 0,
            'training_stocks': 'Initializing...',
            'last_updated': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        st.session_state.evolution_stats = {
            'total_tested': 0,
            'best_fitness_history': [],
            'current_generation': 0,
            'last_train_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        st.session_state.state_loaded = True
        st.session_state.auto_train_done = False

if 'auto_train_done' not in st.session_state:
    st.session_state.auto_train_done = False

# ==========================================
# HELPER FUNCTIONS
# ==========================================

@st.cache_data(ttl=3600)
def download_stock_data(ticker, period="3mo", interval="1d"):
    try:
        stock = yf.Ticker(ticker)
        data = stock.history(period=period, interval=interval)
        info = stock.info
        if len(data) > 0:
            return data, info, None
        return None, None, f"No data found for {ticker}"
    except Exception as e:
        return None, None, str(e)

def create_sequences(data, lookback=50):
    prices = data['Close'].values.reshape(-1, 1)
    scaler = MinMaxScaler(feature_range=(0, 1))
    scaled_data = scaler.fit_transform(prices)
    
    X, y = [], []
    for i in range(lookback, len(scaled_data)):
        X.append(scaled_data[i-lookback:i, 0])
        y.append(scaled_data[i, 0])
    
    X = np.array(X)
    y = np.array(y)
    X = X.reshape(X.shape[0], X.shape[1], 1)
    
    return X, y, scaler

def build_lstm_model(lookback, config):
    model = keras.Sequential([
        layers.LSTM(config['neurons_layer1'], return_sequences=True, input_shape=(lookback, 1)),
        layers.Dropout(config['dropout']),
        layers.LSTM(config['neurons_layer2'], return_sequences=False),
        layers.Dropout(config['dropout']),
        layers.Dense(25, activation='relu'),
        layers.Dense(1)
    ])
    
    model.compile(optimizer='adam', loss='mse', metrics=['mae'])
    return model

def predict_future(model, last_sequence, scaler, steps=10):
    predictions = []
    current_seq = last_sequence.copy()
    
    for _ in range(steps):
        pred = model.predict(current_seq.reshape(1, -1, 1), verbose=0)
        predictions.append(pred[0, 0])
        current_seq = np.append(current_seq[1:], pred[0, 0])
    
    predictions = scaler.inverse_transform(np.array(predictions).reshape(-1, 1))
    return predictions.flatten()

# ==========================================
# EVOLUTIONARY TRAINING
# ==========================================

class LSTMTrader:
    def __init__(self, config=None):
        if config is None:
            self.config = {
                'neurons_layer1': random.randint(30, 100),
                'neurons_layer2': random.randint(30, 100),
                'dropout': round(random.uniform(0.1, 0.4), 2),
                'lookback': random.randint(40, 80),
            }
        else:
            self.config = config
        
        self.model = None
        self.scaler = MinMaxScaler()
        self.fitness = 0
        
    def build_and_train(self, data, epochs=8):
        try:
            lookback = self.config['lookback']
            
            prices = data['Close'].values.reshape(-1, 1)
            scaled = self.scaler.fit_transform(prices)
            
            X, y = [], []
            for i in range(lookback, len(scaled)):
                X.append(scaled[i-lookback:i, 0])
                y.append(scaled[i, 0])
            
            X = np.array(X).reshape(-1, lookback, 1)
            y = np.array(y)
            
            split = int(0.8 * len(X))
            X_train, X_test = X[:split], X[split:]
            y_train, y_test = y[:split], y[split:]
            
            self.model = build_lstm_model(lookback, self.config)
            self.model.fit(X_train, y_train, batch_size=32, epochs=epochs, verbose=0, validation_split=0.1)
            
            test_pred = self.model.predict(X_test, verbose=0)
            mae = np.mean(np.abs(y_test - test_pred.flatten()))
            
            self.fitness = 1 / (mae + 0.0001)
            return self.fitness
        except:
            self.fitness = 0
            return 0

def crossover(parent1, parent2):
    child_config = {}
    for key in parent1.config.keys():
        child_config[key] = parent1.config[key] if random.random() < 0.5 else parent2.config[key]
    return LSTMTrader(child_config)

def mutate(trader, rate=0.25):
    config = trader.config.copy()
    if random.random() < rate:
        key = random.choice(list(config.keys()))
        if key == 'neurons_layer1':
            config['neurons_layer1'] = random.randint(30, 100)
        elif key == 'neurons_layer2':
            config['neurons_layer2'] = random.randint(30, 100)
        elif key == 'dropout':
            config['dropout'] = round(random.uniform(0.1, 0.4), 2)
        elif key == 'lookback':
            config['lookback'] = random.randint(40, 80)
    return LSTMTrader(config)

def run_single_generation(population_size=20):
    """Run one generation of evolution - called automatically"""
    
    # Stock pool
    STOCK_POOL = ['AAPL', 'MSFT', 'GOOGL', 'NVDA', 'TSLA', 'AMD', 'META', 'AMZN', 'JPM', 'V']
    
    # Pick 3 random stocks
    training_stocks = random.sample(STOCK_POOL, 3)
    
    # Download data
    stock_data = []
    for ticker in training_stocks:
        data, _, error = download_stock_data(ticker, "6mo", "1d")
        if not error and len(data) >= 100:
            stock_data.append(data)
    
    if len(stock_data) == 0:
        return None
    
    # Create or evolve population
    if st.session_state.evolution_stats['current_generation'] == 0:
        # First generation - random population
        population = [LSTMTrader() for _ in range(population_size)]
    else:
        # Load previous best and evolve
        best_config = {
            'neurons_layer1': st.session_state.evolved_config['neurons_layer1'],
            'neurons_layer2': st.session_state.evolved_config['neurons_layer2'],
            'dropout': st.session_state.evolved_config['dropout'],
            'lookback': st.session_state.evolved_config['lookback']
        }
        
        # Create population from best config with mutations
        population = []
        population.append(LSTMTrader(best_config))  # Keep best
        
        for _ in range(population_size - 1):
            if random.random() < 0.7:
                trader = mutate(LSTMTrader(best_config), rate=0.3)
            else:
                trader = LSTMTrader()  # Some random
            population.append(trader)
    
    # Evaluate on all stocks
    for trader in population:
        total_fitness = 0
        for data in stock_data:
            fitness = trader.build_and_train(data, epochs=6)
            total_fitness += fitness
        trader.fitness = total_fitness / len(stock_data)
        st.session_state.evolution_stats['total_tested'] += 1
    
    # Sort by fitness
    population.sort(key=lambda x: x.fitness, reverse=True)
    
    # Update if better
    if population[0].fitness > st.session_state.evolved_config['fitness']:
        st.session_state.evolved_config = {
            'neurons_layer1': population[0].config['neurons_layer1'],
            'neurons_layer2': population[0].config['neurons_layer2'],
            'dropout': population[0].config['dropout'],
            'lookback': population[0].config['lookback'],
            'generation': st.session_state.evolution_stats['current_generation'] + 1,
            'fitness': population[0].fitness,
            'training_stocks': ', '.join(training_stocks),
            'last_updated': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        st.session_state.evolution_stats['best_fitness_history'].append(population[0].fitness)
    
    st.session_state.evolution_stats['current_generation'] += 1
    st.session_state.evolution_stats['last_train_time'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # SAVE TO CLOUD after each generation
    save_evolution_state()
    
    return training_stocks

# ==========================================
# AUTO-TRAIN ON LOAD
# ==========================================

if not st.session_state.auto_train_done and NEURAL_NETWORK_AVAILABLE:
    with st.spinner("🧬 AI Evolution in progress... Training on random stocks..."):
        training_stocks = run_single_generation(population_size=15)
        if training_stocks:
            st.session_state.auto_train_done = True
            st.success(f"✅ Generation {st.session_state.evolution_stats['current_generation']} complete! Trained on: {', '.join(training_stocks)}")
            time.sleep(1)
            st.rerun()

# ==========================================
# MAIN APP
# ==========================================

# Header
st.markdown('<p class="main-header">🧠 AI Stock Predictor Pro</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-header">Continuously Evolving Neural Networks • Multi-Stock Training</p>', unsafe_allow_html=True)

# Sidebar
with st.sidebar:
    st.header("⚙️ Mode")
    
    mode = st.radio("", 
        ["📈 Predict Stock", 
         "🔬 Admin Dashboard"],
        label_visibility="collapsed")
    
    st.markdown("---")
    
    # Evolution status (always visible)
    st.subheader("🧬 AI Status")
    
    # Show if loaded from saved state
    if st.session_state.evolved_config['generation'] > 0:
        st.success(f"🟢 Active (Loaded Gen {st.session_state.evolved_config['generation']})")
    else:
        st.success("🟢 Active & Learning")
    
    st.markdown(f"""
    **Current Best:**
    - Generation: **{st.session_state.evolved_config['generation']}**
    - Fitness: **{st.session_state.evolved_config['fitness']:.4f}**
    - Trained on: {st.session_state.evolved_config.get('training_stocks', 'N/A')}
    - Models tested: **{st.session_state.evolution_stats['total_tested']}**
    - Last updated: {st.session_state.evolved_config['last_updated']}
    """)
    
    # Train more button
    if st.button("🚀 Train Next Generation"):
        with st.spinner("Training..."):
            stocks = run_single_generation(population_size=15)
            if stocks:
                st.success(f"✅ Gen {st.session_state.evolution_stats['current_generation']} done!")
                st.rerun()

# ==========================================
# MODE 1: USER PREDICTION
# ==========================================

if mode == "📈 Predict Stock":
    
    if not NEURAL_NETWORK_AVAILABLE:
        st.error("❌ AI engine unavailable")
        st.stop()
    
    st.markdown("### 🎯 Get AI Price Forecast")
    
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        ticker = st.text_input("Stock Symbol", value="AAPL", placeholder="e.g., AAPL, TSLA, NVDA")
    
    with col2:
        period = st.selectbox("Period", ["1mo", "3mo", "6mo", "1y"], index=1)
    
    with col3:
        predict_days = st.slider("Forecast Days", 5, 30, 10)
    
    st.markdown("")
    
    if st.button("🚀 Generate Forecast", type="primary", use_container_width=True):
        
        # Download
        with st.spinner(f"📥 Loading {ticker} data..."):
            data, info, error = download_stock_data(ticker, period, "1d")
        
        if error:
            st.error(f"❌ {error}")
            st.stop()
        
        if len(data) < 60:
            st.error("❌ Not enough data")
            st.stop()
        
        # Current price
        current_price = data['Close'].iloc[-1]
        prev_price = data['Close'].iloc[-2]
        price_change = current_price - prev_price
        price_change_pct = (price_change / prev_price) * 100
        
        st.markdown("### 📊 Market Data")
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Price", f"${current_price:.2f}", f"{price_change:+.2f} ({price_change_pct:+.2f}%)")
        col2.metric("High", f"${data['High'].iloc[-1]:.2f}")
        col3.metric("Low", f"${data['Low'].iloc[-1]:.2f}")
        col4.metric("Volume", f"{data['Volume'].iloc[-1]:,.0f}")
        
        st.markdown("---")
        
        # Use evolved config
        config = st.session_state.evolved_config
        lookback = config['lookback']
        
        # Train
        with st.spinner("🧠 Analyzing patterns..."):
            try:
                X, y, scaler = create_sequences(data, lookback)
                
                split = int(0.8 * len(X))
                X_train, X_test = X[:split], X[split:]
                y_train, y_test = y[:split], y[split:]
                
                model = build_lstm_model(lookback, config)
                
                progress_bar = st.progress(0)
                epochs = 15
                for epoch in range(epochs):
                    model.fit(X_train, y_train, batch_size=32, epochs=1, verbose=0, validation_split=0.1)
                    progress_bar.progress((epoch + 1) / epochs)
                
                progress_bar.empty()
                
            except Exception as e:
                st.error(f"❌ Error: {e}")
                st.stop()
        
        st.success("✅ Analysis complete!")
        
        # Predictions
        y_pred = model.predict(X_test, verbose=0)
        y_pred_prices = scaler.inverse_transform(y_pred)
        y_test_prices = scaler.inverse_transform(y_test.reshape(-1, 1))
        
        mae = np.mean(np.abs(y_test_prices - y_pred_prices))
        accuracy = max(0, 100 - (mae / np.mean(y_test_prices) * 100))
        
        if len(y_test_prices) > 1:
            true_dir = np.diff(y_test_prices.flatten()) > 0
            pred_dir = np.diff(y_pred_prices.flatten()) > 0
            dir_accuracy = np.mean(true_dir == pred_dir) * 100
        else:
            dir_accuracy = 0
        
        st.markdown("### 🎯 AI Performance")
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Price Accuracy", f"{accuracy:.1f}%", "Excellent" if accuracy > 90 else "Good")
        col2.metric("Direction Accuracy", f"{dir_accuracy:.1f}%", "Strong" if dir_accuracy > 65 else "Moderate")
        col3.metric("Avg Error", f"${mae:.2f}")
        
        st.markdown("---")
        
        # Future
        st.markdown("### 🔮 Price Forecast")
        
        last_seq = scaler.transform(data['Close'].values[-lookback:].reshape(-1, 1)).flatten()
        future_preds = predict_future(model, last_seq, scaler, predict_days)
        
        future_dates = pd.date_range(start=data.index[-1] + timedelta(days=1), periods=predict_days, freq='D')
        
        fig = go.Figure()
        
        # Historical
        fig.add_trace(go.Scatter(
            x=data.index[-60:], 
            y=data['Close'].iloc[-60:], 
            name="Historical", 
            line=dict(color='#3b82f6', width=3),
            mode='lines'
        ))
        
        # Connecting line (bridges the gap smoothly)
        fig.add_trace(go.Scatter(
            x=[data.index[-1], future_dates[0]], 
            y=[current_price, future_preds[0]], 
            line=dict(color='#f59e0b', width=3),
            mode='lines',
            showlegend=False,
            hoverinfo='skip'
        ))
        
        # Forecast
        fig.add_trace(go.Scatter(
            x=future_dates, 
            y=future_preds, 
            name="Forecast", 
            line=dict(color='#f59e0b', width=4, dash='dot'), 
            mode='lines+markers', 
            marker=dict(size=8, symbol='diamond')
        ))
        
        fig.update_layout(
            height=500, 
            template="plotly_white", 
            xaxis_title="Date", 
            yaxis_title="Price ($)", 
            hovermode='x unified'
        )
        st.plotly_chart(fig, use_container_width=True)
        
        # Table
        st.markdown("### 📅 Forecast Table")
        forecast_df = pd.DataFrame({
            'Date': future_dates.strftime('%Y-%m-%d'),
            'Price': [f"${p:.2f}" for p in future_preds],
            'Change': [f"{((p - current_price) / current_price * 100):+.2f}%" for p in future_preds]
        })
        st.dataframe(forecast_df, use_container_width=True, hide_index=True)
        
        # Trading signals
        final_price = future_preds[-1]
        total_return = ((final_price - current_price) / current_price) * 100
        
        if total_return > 0:
            take_profit = final_price * 1.02
            stop_loss = current_price * 0.98
        else:
            take_profit = current_price * 1.02
            stop_loss = final_price * 0.98
        
        st.markdown("### 💡 Trading Signals")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if total_return > 5:
                st.success(f"""
                **🚀 Strong Buy**
                
                Predicted: **{total_return:+.2f}%** in {predict_days} days
                
                Entry: ${current_price:.2f}  
                Target: ${final_price:.2f}  
                🎯 Take Profit: ${take_profit:.2f}  
                🛑 Stop Loss: ${stop_loss:.2f}
                """)
            elif total_return > 0:
                st.info(f"""
                **📈 Buy Signal**
                
                Predicted: **{total_return:+.2f}%**
                
                Entry: ${current_price:.2f}  
                Target: ${final_price:.2f}  
                🎯 Take Profit: ${take_profit:.2f}  
                🛑 Stop Loss: ${stop_loss:.2f}
                """)
            elif total_return > -5:
                st.warning(f"""
                **📊 Hold**
                
                Predicted: **{total_return:+.2f}%**
                
                Current: ${current_price:.2f}  
                Target: ${final_price:.2f}
                """)
            else:
                st.error(f"""
                **📉 Sell Signal**
                
                Predicted: **{total_return:+.2f}%**
                
                Current: ${current_price:.2f}  
                Target: ${final_price:.2f}
                """)
        
        with col2:
            st.markdown("#### Risk/Reward")
            risk = abs(current_price - stop_loss)
            reward = abs(take_profit - current_price)
            rr_ratio = reward / risk if risk > 0 else 0
            
            st.metric("Ratio", f"{rr_ratio:.2f}:1", "Good" if rr_ratio > 2 else "Fair")
            st.metric("Potential Gain", f"${reward:.2f}")
            st.metric("Potential Loss", f"${risk:.2f}")
        
        st.caption("⚠️ Educational purposes only. Not financial advice.")

# ==========================================
# MODE 2: ADMIN DASHBOARD
# ==========================================

else:
    st.markdown("### 🔬 Admin Dashboard")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### 📊 Evolution Stats")
        st.write(f"**Generations:** {st.session_state.evolution_stats['current_generation']}")
        st.write(f"**Models Tested:** {st.session_state.evolution_stats['total_tested']}")
        st.write(f"**Last Training:** {st.session_state.evolution_stats['last_train_time']}")
        
        if st.button("📥 Download Config JSON"):
            config_json = json.dumps(st.session_state.evolved_config, indent=2)
            st.download_button(
                label="💾 Download",
                data=config_json,
                file_name=f"evolved_config_gen{st.session_state.evolved_config['generation']}.json",
                mime="application/json"
            )
        
        st.markdown("---")
        
        if st.button("🗑️ Reset All Progress", type="secondary"):
            if os.path.exists(STATE_FILE):
                os.remove(STATE_FILE)
            st.session_state.evolved_config = {
                'neurons_layer1': 50,
                'neurons_layer2': 50,
                'dropout': 0.2,
                'lookback': 50,
                'generation': 0,
                'fitness': 0,
                'training_stocks': 'Reset',
                'last_updated': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            st.session_state.evolution_stats = {
                'total_tested': 0,
                'best_fitness_history': [],
                'current_generation': 0,
                'last_train_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            st.success("✅ Progress reset!")
            st.rerun()
    
    with col2:
        st.markdown("#### 🏆 Best Configuration")
        st.json(st.session_state.evolved_config)
    
    st.markdown("---")
    
    if len(st.session_state.evolution_stats['best_fitness_history']) > 0:
        st.markdown("#### 📈 Fitness Progress")
        fig = go.Figure()
        fig.add_trace(go.Scatter(y=st.session_state.evolution_stats['best_fitness_history'], mode='lines+markers', name="Fitness", line=dict(color='#10b981', width=3)))
        fig.update_layout(height=400, xaxis_title="Generation", yaxis_title="Fitness", template="plotly_white")
        st.plotly_chart(fig, use_container_width=True)

st.markdown("---")
st.caption("🧠 Powered by LSTM • Evolving through Multi-Stock Training")
