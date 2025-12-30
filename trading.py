import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import warnings
import time
import google.generativeai as genai
import json
import os
from dotenv import load_dotenv

warnings.filterwarnings('ignore')
load_dotenv()

st.set_page_config(
    page_title="AI Trading Assistant",
    page_icon="💬",
    layout="wide",
    initial_sidebar_state="collapsed"
)

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
    .stChatFloatingInputContainer {
        background: rgba(255, 255, 255, 0.05);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 12px;
    }
    .stChatMessage {
        background: rgba(255, 255, 255, 0.05);
        border-radius: 12px;
        padding: 1rem;
        margin: 0.5rem 0;
    }
</style>
""", unsafe_allow_html=True)

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

if 'chat_messages' not in st.session_state:
    st.session_state.chat_messages = []
if 'account_size' not in st.session_state:
    st.session_state.account_size = 100000
if 'risk_per_trade' not in st.session_state:
    st.session_state.risk_per_trade = 1.0
if 'show_settings' not in st.session_state:
    st.session_state.show_settings = False

@st.cache_data(ttl=300)
def get_stock_data_optimized(ticker, period='3mo', interval='1d'):
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
    try:
        qqq = yf.Ticker('QQQ')
        hist = qqq.history(period='1y')
        if len(hist) < 200:
            return 'NEUTRAL', 0
        current_price = hist['Close'].iloc[-1]
        sma_200 = hist['Close'].rolling(window=200).mean().iloc[-1]
        sma_50 = hist['Close'].rolling(window=50).mean().iloc[-1]
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
    if df.empty or len(df) < 2:
        return df
    df['EMA_9'] = df['Close'].ewm(span=9, adjust=False).mean()
    df['EMA_20'] = df['Close'].ewm(span=20, adjust=False).mean()
    df['SMA_50'] = df['Close'].rolling(window=50).mean()
    df['SMA_200'] = df['Close'].rolling(window=200).mean()
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    exp1 = df['Close'].ewm(span=12, adjust=False).mean()
    exp2 = df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = exp1 - exp2
    df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    df['MACD_Histogram'] = df['MACD'] - df['MACD_Signal']
    high_low = df['High'] - df['Low']
    high_close = np.abs(df['High'] - df['Close'].shift())
    low_close = np.abs(df['Low'] - df['Close'].shift())
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = np.max(ranges, axis=1)
    df['ATR'] = true_range.rolling(14).mean()
    df['Volume_SMA_20'] = df['Volume'].rolling(window=20).mean()
    df['Volume_Ratio'] = df['Volume'] / df['Volume_SMA_20']
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
    df['Distance_EMA20'] = ((df['Close'] - df['EMA_20']) / df['EMA_20']) * 100
    df['Distance_SMA50'] = ((df['Close'] - df['SMA_50']) / df['SMA_50']) * 100
    return df

def identify_setup_type(df, info):
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
    uptrend = current_price > sma_50 > sma_200 if pd.notna(sma_200) else current_price > sma_50
    if not uptrend:
        return None, 0, 0, 0, 0, "Not in uptrend structure"
    if pd.notna(ema_20):
        distance_to_ema20 = abs(current_price - ema_20) / ema_20 * 100
        rsi_prev = df['RSI'].iloc[-2] if len(df) > 1 else rsi
        rsi_rising = rsi > rsi_prev
        
        if (distance_to_ema20 < 2.5 and current_price > ema_20 and rsi > 40 and rsi < 60 and macd_hist > 0 and rsi_rising):
            quality = 85
            if volume_ratio > 1.2:
                quality += 5
            if df['Close'].iloc[-3:].min() <= ema_20 <= df['High'].iloc[-3:].max():
                quality += 5
            entry = current_price
            stop = entry * 0.97
            risk = entry - stop
            target = entry + (risk * 3)
            setups.append({
                'type': 'EMA_20_PULLBACK',
                'quality': quality,
                'entry': entry,
                'stop': stop,
                'target': target,
                'reason': f'Pullback to 20 EMA in uptrend. RSI: {rsi:.0f} rising, Vol: {volume_ratio:.1f}x'
            })
    if pd.notna(sma_50):
        distance_to_sma50 = abs(current_price - sma_50) / sma_50 * 100
        rsi_prev = df['RSI'].iloc[-2] if len(df) > 1 else rsi
        rsi_rising = rsi > rsi_prev
        
        if (distance_to_sma50 < 3.0 and current_price > sma_50 and rsi > 35 and rsi < 55 and sma_50 > sma_200 and rsi_rising):
            quality = 75
            if volume_ratio > 1.0:
                quality += 5
            if df['Close'].iloc[-5:].min() <= sma_50:
                quality += 5
            entry = current_price
            stop = entry * 0.97
            risk = entry - stop
            target = entry + (risk * 2.5)
            setups.append({
                'type': 'SMA_50_PULLBACK',
                'quality': quality,
                'entry': entry,
                'stop': stop,
                'target': target,
                'reason': f'Pullback to 50 SMA support. RSI: {rsi:.0f} rising'
            })
    recent_high = df['High'].iloc[-20:].max()
    distance_from_high = (recent_high - current_price) / current_price * 100
    if distance_from_high < 3:
        last_10_range = (df['High'].iloc[-10:].max() - df['Low'].iloc[-10:].min()) / current_price * 100
        rsi_prev = df['RSI'].iloc[-2] if len(df) > 1 else rsi
        rsi_rising = rsi > rsi_prev
        
        if (last_10_range < 8 and current_price > ema_20 and volume_ratio > 1.3 and rsi > 50 and rsi < 70 and rsi_rising):
            quality = 80
            if current_price > recent_high:
                quality += 10
            entry = current_price
            stop = entry * 0.97
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
    if not setups:
        return None, 0, 0, 0, 0, "No valid setup identified"
    best_setup = max(setups, key=lambda x: x['quality'])
    return (best_setup['type'], best_setup['quality'], best_setup['entry'], best_setup['stop'], best_setup['target'], best_setup['reason'])

def calculate_position_size(account_size, risk_percent, entry, stop):
    if entry <= stop or stop <= 0:
        return 0, 0
    risk_amount = account_size * (risk_percent / 100)
    risk_per_share = entry - stop
    shares = int(risk_amount / risk_per_share)
    position_value = shares * entry
    return shares, position_value

def scan_nasdaq_for_setups(timeframe='1d', top_n=20, min_quality=65, progress_callback=None):
    market_regime, market_strength = get_market_regime()
    if market_regime not in ['BULLISH', 'NEUTRAL_BULLISH']:
        return pd.DataFrame(), market_regime, market_strength
    results = []
    total_stocks = len(NASDAQ_100)
    
    for idx, ticker in enumerate(NASDAQ_100):
        try:
            if progress_callback:
                progress_callback(idx, total_stocks, ticker)
            
            if idx > 0 and idx % 10 == 0:
                time.sleep(1)
            period = '3mo' if timeframe == '1d' else '1mo'
            hist, info = get_stock_data_optimized(ticker, period=period, interval=timeframe)
            if hist.empty or len(hist) < 60:
                continue
            avg_volume = info.get('averageVolume', 0)
            if avg_volume < 500000:
                continue
            hist = calculate_swing_indicators(hist)
            setup_type, quality, entry, stop, target, reason = identify_setup_type(hist, info)
            if setup_type and quality >= min_quality:
                risk_per_share = entry - stop
                reward = target - entry
                reward_risk = reward / risk_per_share if risk_per_share > 0 else 0
                shares, position_value = calculate_position_size(st.session_state.account_size, st.session_state.risk_per_trade, entry, stop)
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
                })
        except Exception as e:
            continue
    
    if results:
        df = pd.DataFrame(results)
        df = df.sort_values(by=['Quality', 'R_R_Ratio'], ascending=[False, False]).reset_index(drop=True)
        return df.head(top_n), market_regime, market_strength
    return pd.DataFrame(), market_regime, market_strength

def scan_stock_tool(ticker, timeframe='1d'):
    try:
        period = '6mo' if timeframe == '1d' else '2mo'
        hist, info = get_stock_data_optimized(ticker, period=period, interval=timeframe)
        
        if hist.empty or len(hist) < 60:
            return {"success": False, "error": f"Unable to fetch sufficient data for {ticker}"}
        
        hist = calculate_swing_indicators(hist)
        setup_type, quality, entry, stop, target, reason = identify_setup_type(hist, info)
        
        current_price = hist['Close'].iloc[-1]
        prev_close = hist['Close'].iloc[-2]
        change_pct = ((current_price - prev_close) / prev_close) * 100
        
        if setup_type:
            shares, position_value = calculate_position_size(
                st.session_state.account_size,
                st.session_state.risk_per_trade,
                entry,
                stop
            )
            risk_amount = st.session_state.account_size * (st.session_state.risk_per_trade / 100)
            potential_profit = shares * (target - entry)
            reward_risk_ratio = (target - entry) / (entry - stop) if entry > stop else 0
            
            return {
                "success": True,
                "ticker": ticker,
                "current_price": round(current_price, 2),
                "price_change_pct": round(change_pct, 2),
                "setup_type": setup_type,
                "quality": quality,
                "entry": round(entry, 2),
                "stop": round(stop, 2),
                "target": round(target, 2),
                "reason": reason,
                "rsi": round(hist['RSI'].iloc[-1], 1),
                "volume_ratio": round(hist['Volume_Ratio'].iloc[-1], 1),
                "shares": shares,
                "position_value": round(position_value, 2),
                "risk_amount": round(risk_amount, 2),
                "potential_profit": round(potential_profit, 2),
                "reward_risk_ratio": round(reward_risk_ratio, 2)
            }
        else:
            return {
                "success": False,
                "ticker": ticker,
                "current_price": round(current_price, 2),
                "price_change_pct": round(change_pct, 2),
                "error": f"No valid setup found: {reason}",
                "rsi": round(hist['RSI'].iloc[-1], 1),
                "volume_ratio": round(hist['Volume_Ratio'].iloc[-1], 1)
            }
    except Exception as e:
        return {"success": False, "error": f"Error analyzing {ticker}: {str(e)}"}

def scan_nasdaq_tool(timeframe='1d', top_n=20, min_quality=70):
    try:
        progress_placeholder = st.empty()
        
        def progress_callback(idx, total, ticker):
            progress_placeholder.text(f"Scanning {ticker}... ({idx + 1}/{total})")
        
        results_df, regime, strength = scan_nasdaq_for_setups(
            timeframe=timeframe,
            top_n=top_n,
            min_quality=min_quality,
            progress_callback=progress_callback
        )
        
        progress_placeholder.empty()
        
        if results_df.empty:
            return {
                "success": False,
                "market_regime": regime,
                "market_strength": round(strength, 2),
                "message": "No setups found meeting criteria"
            }
        
        setups = []
        for _, row in results_df.iterrows():
            setups.append({
                "ticker": row['Ticker'],
                "setup": row['Setup'],
                "quality": row['Quality'],
                "entry": round(row['Entry'], 2),
                "stop": round(row['Stop'], 2),
                "target": round(row['Target'], 2),
                "r_r_ratio": round(row['R_R_Ratio'], 2),
                "shares": row['Shares'],
                "position_value": round(row['Position_$'], 2),
                "rsi": round(row['RSI'], 1),
                "volume_ratio": round(row['Volume_Ratio'], 1),
                "reason": row['Reason']
            })
        
        return {
            "success": True,
            "market_regime": regime,
            "market_strength": round(strength, 2),
            "total_setups": len(setups),
            "setups": setups
        }
    except Exception as e:
        return {"success": False, "error": f"Error scanning Nasdaq: {str(e)}"}

def calculate_position_tool(entry, stop, target=None, account_size=None, risk_percent=None):
    try:
        acc_size = account_size if account_size else st.session_state.account_size
        risk_pct = risk_percent if risk_percent else st.session_state.risk_per_trade
        
        if entry <= stop:
            return {"success": False, "error": "Entry price must be greater than stop loss"}
        
        shares, position_value = calculate_position_size(acc_size, risk_pct, entry, stop)
        risk_amount = acc_size * (risk_pct / 100)
        risk_per_share = entry - stop
        
        result = {
            "success": True,
            "shares": shares,
            "position_value": round(position_value, 2),
            "risk_amount": round(risk_amount, 2),
            "risk_per_share": round(risk_per_share, 2),
            "portfolio_pct": round((position_value / acc_size) * 100, 2),
            "account_size": acc_size,
            "risk_percent": risk_pct
        }
        
        if target:
            reward_per_share = target - entry
            potential_profit = shares * reward_per_share
            reward_risk_ratio = reward_per_share / risk_per_share
            
            result.update({
                "target": round(target, 2),
                "potential_profit": round(potential_profit, 2),
                "reward_risk_ratio": round(reward_risk_ratio, 2),
                "reward_per_share": round(reward_per_share, 2)
            })
        
        return result
    except Exception as e:
        return {"success": False, "error": f"Error calculating position: {str(e)}"}

def get_market_regime_tool():
    try:
        regime, strength = get_market_regime()
        return {
            "success": True,
            "regime": regime,
            "strength": round(strength, 2),
            "description": {
                "BULLISH": "Market is in a strong uptrend. Good environment for swing trading.",
                "NEUTRAL_BULLISH": "Market is above 200 SMA but not strongly trending. Trade with caution.",
                "BEARISH": "Market is in a downtrend. Cash is a position.",
                "NEUTRAL": "Market is choppy. Wait for clearer direction."
            }.get(regime, "Unknown market condition")
        }
    except Exception as e:
        return {"success": False, "error": f"Error checking market regime: {str(e)}"}

def process_chatbot_message(user_message, conversation_history):
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        return "⚠️ Please set your GOOGLE_API_KEY environment variable."
    
    # Configure Gemini
    genai.configure(api_key=api_key)
    
    # Define function declarations for Gemini
    tools = [
        genai.protos.Tool(
            function_declarations=[
                genai.protos.FunctionDeclaration(
                    name="scan_stock",
                    description="Scan an individual stock ticker for swing trading setups. Returns setup type, quality score, entry/stop/target prices, position sizing, and technical indicators.",
                    parameters=genai.protos.Schema(
                        type=genai.protos.Type.OBJECT,
                        properties={
                            "ticker": genai.protos.Schema(type=genai.protos.Type.STRING, description="Stock ticker symbol (e.g., AAPL, TSLA, NVDA)"),
                            "timeframe": genai.protos.Schema(type=genai.protos.Type.STRING, description="Chart timeframe: '1d' for daily or '1h' for hourly")
                        },
                        required=["ticker"]
                    )
                ),
                genai.protos.FunctionDeclaration(
                    name="scan_nasdaq_100",
                    description="Scan all Nasdaq 100 stocks for high-quality swing trading setups. Returns top setups ranked by quality score.",
                    parameters=genai.protos.Schema(
                        type=genai.protos.Type.OBJECT,
                        properties={
                            "timeframe": genai.protos.Schema(type=genai.protos.Type.STRING, description="Chart timeframe"),
                            "top_n": genai.protos.Schema(type=genai.protos.Type.INTEGER, description="Maximum number of setups to return"),
                            "min_quality": genai.protos.Schema(type=genai.protos.Type.INTEGER, description="Minimum quality score (60-90)")
                        }
                    )
                ),
                genai.protos.FunctionDeclaration(
                    name="calculate_position_size",
                    description="Calculate optimal position size and risk/reward metrics for a trade.",
                    parameters=genai.protos.Schema(
                        type=genai.protos.Type.OBJECT,
                        properties={
                            "entry": genai.protos.Schema(type=genai.protos.Type.NUMBER, description="Entry price"),
                            "stop": genai.protos.Schema(type=genai.protos.Type.NUMBER, description="Stop loss price"),
                            "target": genai.protos.Schema(type=genai.protos.Type.NUMBER, description="Target price (optional)"),
                            "account_size": genai.protos.Schema(type=genai.protos.Type.NUMBER, description="Account size (uses default if not provided)"),
                            "risk_percent": genai.protos.Schema(type=genai.protos.Type.NUMBER, description="Risk percentage (uses default if not provided)")
                        },
                        required=["entry", "stop"]
                    )
                ),
                genai.protos.FunctionDeclaration(
                    name="get_market_regime",
                    description="Check the current market regime (BULLISH, NEUTRAL_BULLISH, BEARISH, or NEUTRAL) based on QQQ's position relative to moving averages.",
                    parameters=genai.protos.Schema(
                        type=genai.protos.Type.OBJECT,
                        properties={}
                    )
                )
            ]
        )
    ]
    
    system_instruction = f"""You are a professional swing trading assistant with expertise in technical analysis and risk management.

**User's Current Settings:**
- Account Size: ${st.session_state.account_size:,}
- Risk Per Trade: {st.session_state.risk_per_trade}%
- Risk Amount: ${st.session_state.account_size * (st.session_state.risk_per_trade / 100):,.0f} per trade

**Your Trading Strategy:**
- Only trade stocks in confirmed uptrends
- Focus on 5 setup types: EMA 20 Pullback, SMA 50 Pullback, Consolidation Breakout, Support Bounce, Mean Reversion
- Quality scores: 85+ (exceptional), 75-84 (strong), 65-74 (good)
- Strict risk management with predefined entries, stops, and targets

**Communication Style:**
- Be professional but conversational
- Explain setups clearly with technical reasoning
- Always emphasize risk management
- Provide actionable trade plans
- Be honest when no good setups exist
- Use emojis sparingly (🔥 for strong setups, ✅ for good, ⚠️ for warnings)

**CRITICAL:**
- This is educational content, NOT financial advice
- Remind users to verify data before trading
- Never guarantee profits
- Encourage proper position sizing

When users ask about stocks or setups, use your tools to get real data and provide clear, actionable responses."""

    # Create model with tools
    model = genai.GenerativeModel(
        'gemini-1.5-flash',
        tools=tools,
        system_instruction=system_instruction
    )
    
    # Build conversation history for Gemini
    history = []
    for msg in conversation_history:
        if msg["role"] == "user":
            history.append({"role": "user", "parts": [msg["content"]]})
        elif msg["role"] == "assistant":
            history.append({"role": "model", "parts": [msg["content"]]})
    
    # Start chat
    chat = model.start_chat(history=history)
    
    max_iterations = 5
    iteration = 0
    
    while iteration < max_iterations:
        iteration += 1
        
        try:
            # Send message
            response = chat.send_message(user_message)
            
            # Check if model wants to call a function
            if response.candidates[0].content.parts[0].function_call:
                function_call = response.candidates[0].content.parts[0].function_call
                function_name = function_call.name
                function_args = {}
                
                # Extract arguments
                for key, value in function_call.args.items():
                    function_args[key] = value
                
                # Execute the function
                if function_name == "scan_stock":
                    result = scan_stock_tool(
                        ticker=function_args.get("ticker"),
                        timeframe=function_args.get("timeframe", "1d")
                    )
                elif function_name == "scan_nasdaq_100":
                    result = scan_nasdaq_tool(
                        timeframe=function_args.get("timeframe", "1d"),
                        top_n=function_args.get("top_n", 20),
                        min_quality=function_args.get("min_quality", 70)
                    )
                elif function_name == "calculate_position_size":
                    result = calculate_position_tool(
                        entry=function_args.get("entry"),
                        stop=function_args.get("stop"),
                        target=function_args.get("target"),
                        account_size=function_args.get("account_size"),
                        risk_percent=function_args.get("risk_percent")
                    )
                elif function_name == "get_market_regime":
                    result = get_market_regime_tool()
                else:
                    result = {"error": f"Unknown function: {function_name}"}
                
                # Send function response back to model
                response = chat.send_message(
                    genai.protos.Content(
                        parts=[
                            genai.protos.Part(
                                function_response=genai.protos.FunctionResponse(
                                    name=function_name,
                                    response={"result": result}
                                )
                            )
                        ]
                    )
                )
                
                # Update user_message for next iteration
                user_message = ""
                continue
            
            # Return final text response
            return response.text
            
        except Exception as e:
            return f"❌ Error communicating with AI: {str(e)}\n\nPlease check your API key and try again."
    
    return "⚠️ Response took too long. Please try a simpler question."

col1, col2 = st.columns([4, 1])
with col1:
    st.title("💬 AI Trading Assistant")
    st.markdown("*Professional swing trading analysis powered by Google Gemini*")
with col2:
    if st.button("⚙️ Settings", use_container_width=True):
        st.session_state.show_settings = not st.session_state.show_settings

if st.session_state.show_settings:
    with st.expander("⚙️ Account Settings", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            st.session_state.account_size = st.number_input(
                "Account Size ($)",
                min_value=10000,
                value=st.session_state.account_size,
                step=10000
            )
        with col2:
            st.session_state.risk_per_trade = st.slider(
                "Risk Per Trade (%)",
                min_value=0.5,
                max_value=2.0,
                value=st.session_state.risk_per_trade,
                step=0.1
            )
        
        risk_amount = st.session_state.account_size * (st.session_state.risk_per_trade / 100)
        st.info(f"💰 Risk per trade: **${risk_amount:,.0f}** ({st.session_state.risk_per_trade}% of ${st.session_state.account_size:,})")

st.markdown("---")

api_key = os.environ.get("GOOGLE_API_KEY")
if not api_key:
    st.error("⚠️ **Google API Key not found!**")
    st.markdown("""
    **To use the AI assistant:**
    
    1. Get your FREE API key at: **https://aistudio.google.com/app/apikey**
    2. Create a `.env` file in your project directory
    3. Add this line: `GOOGLE_API_KEY=your-key-here`
    4. Restart the app
    
    **Note:** Gemini is completely FREE for up to 1,500 requests per day!
    """)
    st.stop()

st.markdown("### ⚡ Quick Actions")
col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    if st.button("🔍 Scan Nasdaq", use_container_width=True):
        st.session_state.chat_messages.append({
            "role": "user",
            "content": "Scan the Nasdaq 100 for the best swing trading setups"
        })
        st.rerun()

with col2:
    if st.button("📊 Market Check", use_container_width=True):
        st.session_state.chat_messages.append({
            "role": "user",
            "content": "What's the current market regime?"
        })
        st.rerun()

with col3:
    if st.button("🎯 Top 5", use_container_width=True):
        st.session_state.chat_messages.append({
            "role": "user",
            "content": "Show me the top 5 highest quality setups"
        })
        st.rerun()

with col4:
    if st.button("📈 Analyze", use_container_width=True):
        st.session_state.chat_messages.append({
            "role": "user",
            "content": "Analyze AAPL for swing trading"
        })
        st.rerun()

with col5:
    if st.button("🧹 Clear", use_container_width=True):
        st.session_state.chat_messages = []
        st.rerun()

st.markdown("---")

for message in st.session_state.chat_messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("Ask about stocks, setups, position sizing, or market conditions..."):
    st.session_state.chat_messages.append({"role": "user", "content": prompt})
    
    with st.chat_message("user"):
        st.markdown(prompt)
    
    with st.chat_message("assistant"):
        with st.spinner("Analyzing..."):
            response = process_chatbot_message(prompt, st.session_state.chat_messages[:-1])
        st.markdown(response)
    
    st.session_state.chat_messages.append({"role": "assistant", "content": response})
    st.rerun()

if len(st.session_state.chat_messages) == 0:
    st.markdown("### 💡 Try asking:")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
        **General Analysis:**
        - "Scan the Nasdaq 100"
        - "What's the market regime?"
        - "Show me the best setups today"
        - "Find stocks with quality scores above 85"
        """)
    
    with col2:
        st.markdown("""
        **Specific Stocks:**
        - "Analyze NVDA for swing trading"
        - "Is TSLA a good buy right now?"
        - "Calculate position size for AAPL at $185, stop $180"
        - "Compare MSFT and GOOGL setups"
        """)

st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #888; padding: 1rem;'>
    <p><strong>AI Trading Assistant</strong> | Powered by Google Gemini (FREE)</p>
    <p style='font-size: 0.85rem;'>⚠️ This is educational content. Not financial advice. Always verify data before trading.</p>
</div>
""", unsafe_allow_html=True)
