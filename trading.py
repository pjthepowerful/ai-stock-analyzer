import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from supabase import create_client
import json

# =============================================================================
# CONFIGURATION & INITIALIZATION
# =============================================================================

st.set_page_config(
    page_title="WealthStockify Professional",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

@st.cache_resource
def init_supabase():
    try:
        return create_client(st.secrets["supabase"]["url"], st.secrets["supabase"]["key"])
    except:
        return None

supabase = init_supabase()

# Professional CSS with modern design
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    
    * {font-family: 'Inter', sans-serif;}
    
    .stApp {
        background: linear-gradient(180deg, #0f172a 0%, #1e293b 100%);
    }
    
    h1, h2, h3, h4, h5, h6 {
        color: #f1f5f9 !important;
        font-weight: 600 !important;
    }
    
    .stButton > button {
        background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
        color: white;
        border: none;
        border-radius: 8px;
        padding: 0.625rem 1.25rem;
        font-weight: 500;
        transition: all 0.3s;
        box-shadow: 0 4px 6px -1px rgba(59, 130, 246, 0.3);
    }
    
    .stButton > button:hover {
        background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%);
        box-shadow: 0 10px 15px -3px rgba(59, 130, 246, 0.4);
        transform: translateY(-1px);
    }
    
    .metric-card {
        background: rgba(30, 41, 59, 0.5);
        backdrop-filter: blur(10px);
        border: 1px solid rgba(148, 163, 184, 0.1);
        border-radius: 12px;
        padding: 1.5rem;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    }
    
    .premium-badge {
        background: linear-gradient(135deg, #fbbf24 0%, #f59e0b 100%);
        color: #000;
        padding: 0.375rem 0.875rem;
        border-radius: 6px;
        font-weight: 600;
        font-size: 0.75rem;
        display: inline-block;
        box-shadow: 0 2px 4px rgba(251, 191, 36, 0.3);
    }
    
    .free-badge {
        background: rgba(100, 116, 139, 0.5);
        color: #e2e8f0;
        padding: 0.375rem 0.875rem;
        border-radius: 6px;
        font-weight: 600;
        font-size: 0.75rem;
        display: inline-block;
    }
    
    .alert-box {
        background: rgba(239, 68, 68, 0.1);
        border-left: 4px solid #ef4444;
        padding: 1rem;
        border-radius: 4px;
        margin: 1rem 0;
    }
    
    .success-box {
        background: rgba(34, 197, 94, 0.1);
        border-left: 4px solid #22c55e;
        padding: 1rem;
        border-radius: 4px;
        margin: 1rem 0;
    }
    
    div[data-testid="stMetricValue"] {
        font-size: 2rem;
        font-weight: 700;
        color: #f1f5f9;
    }
    
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    
    .stTabs [data-baseweb="tab"] {
        background: rgba(30, 41, 59, 0.5);
        border-radius: 8px 8px 0 0;
        padding: 12px 24px;
        border: 1px solid rgba(148, 163, 184, 0.1);
    }
    
    .stTabs [aria-selected="true"] {
        background: rgba(59, 130, 246, 0.2);
        border-bottom: 2px solid #3b82f6;
    }
</style>
""", unsafe_allow_html=True)

# Session State Management
class SessionManager:
    @staticmethod
    def init():
        defaults = {
            'authenticated': False,
            'user': None,
            'profile': None,
            'page': 'dashboard',
            'watchlist_cache': None,
            'analysis_cache': {}
        }
        for key, value in defaults.items():
            if key not in st.session_state:
                st.session_state[key] = value

SessionManager.init()

# =============================================================================
# AUTHENTICATION SERVICE
# =============================================================================

class AuthService:
    @staticmethod
    def signup(email: str, password: str) -> tuple[bool, str]:
        try:
            response = supabase.auth.sign_up({"email": email, "password": password})
            if response.user:
                return True, "Account created successfully! Please check your email."
            return False, "Signup failed. Please try again."
        except Exception as e:
            return False, f"Error: {str(e)}"
    
    @staticmethod
    def signin(email: str, password: str) -> tuple[bool, any, dict]:
        try:
            response = supabase.auth.sign_in_with_password({"email": email, "password": password})
            if response.user:
                profile = DatabaseService.get_user_profile(response.user.id)
                return True, response.user, profile
            return False, None, None
        except Exception as e:
            return False, None, {"error": str(e)}
    
    @staticmethod
    def signout():
        try:
            supabase.auth.sign_out()
        except:
            pass
        st.session_state.clear()
        SessionManager.init()
    
    @staticmethod
    def reset_password(email: str) -> tuple[bool, str]:
        try:
            supabase.auth.reset_password_for_email(email)
            return True, "Password reset email sent successfully!"
        except Exception as e:
            return False, f"Error: {str(e)}"

# =============================================================================
# DATABASE SERVICE
# =============================================================================

class DatabaseService:
    @staticmethod
    def get_user_profile(user_id: str) -> dict:
        try:
            result = supabase.table('user_profiles').select('*').eq('id', user_id).single().execute()
            return result.data if result.data else {'is_premium': False, 'id': user_id}
        except:
            return {'is_premium': False, 'id': user_id}
    
    @staticmethod
    def upgrade_to_premium(user_id: str) -> bool:
        try:
            # Get user email from session
            user_email = st.session_state.user.email
            end_date = (datetime.now() + timedelta(days=30)).isoformat()
            
            supabase.table('user_profiles').upsert({
                'id': user_id,
                'email': user_email,
                'is_premium': True,
                'subscription_end_date': end_date
            }).execute()
            return True
        except Exception as e:
            st.error(f"Upgrade failed: {e}")
            return False
    
    @staticmethod
    def cancel_subscription(user_id: str) -> bool:
        try:
            supabase.table('user_profiles').update({
                'is_premium': False,
                'subscription_end_date': None
            }).eq('id', user_id).execute()
            return True
        except:
            return False
    
    @staticmethod
    def get_watchlist(user_id: str) -> list:
        try:
            result = supabase.table('watchlists').select('*').eq('user_id', user_id).execute()
            return result.data if result.data else []
        except:
            return []
    
    @staticmethod
    def add_to_watchlist(user_id: str, ticker: str, notes: str = "") -> bool:
        try:
            supabase.table('watchlists').insert({
                'user_id': user_id,
                'ticker': ticker,
                'notes': notes,
                'created_at': datetime.now().isoformat()
            }).execute()
            return True
        except:
            return False
    
    @staticmethod
    def remove_from_watchlist(user_id: str, ticker: str) -> bool:
        try:
            supabase.table('watchlists').delete().eq('user_id', user_id).eq('ticker', ticker).execute()
            return True
        except:
            return False
    
    @staticmethod
    def update_watchlist_notes(user_id: str, ticker: str, notes: str) -> bool:
        try:
            supabase.table('watchlists').update({
                'notes': notes
            }).eq('user_id', user_id).eq('ticker', ticker).execute()
            return True
        except:
            return False
    
    @staticmethod
    def get_portfolio(user_id: str) -> list:
        try:
            result = supabase.table('portfolio').select('*').eq('user_id', user_id).execute()
            return result.data if result.data else []
        except:
            return []
    
    @staticmethod
    def add_portfolio_position(user_id: str, ticker: str, shares: float, avg_price: float, purchase_date: str) -> bool:
        try:
            supabase.table('portfolio').insert({
                'user_id': user_id,
                'ticker': ticker,
                'shares': shares,
                'average_price': avg_price,
                'purchase_date': purchase_date,
                'created_at': datetime.now().isoformat()
            }).execute()
            return True
        except:
            return False
    
    @staticmethod
    def remove_portfolio_position(user_id: str, ticker: str) -> bool:
        try:
            supabase.table('portfolio').delete().eq('user_id', user_id).eq('ticker', ticker).execute()
            return True
        except:
            return False
    
    @staticmethod
    def update_portfolio_position(user_id: str, ticker: str, shares: float, avg_price: float) -> bool:
        try:
            supabase.table('portfolio').update({
                'shares': shares,
                'average_price': avg_price
            }).eq('user_id', user_id).eq('ticker', ticker).execute()
            return True
        except:
            return False

# =============================================================================
# TECHNICAL ANALYSIS ENGINE
# =============================================================================

class TechnicalAnalysis:
    @staticmethod
    def calculate_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
        # RSI
        delta = df['Close'].diff()
        gain = delta.where(delta > 0, 0).rolling(window=14).mean()
        loss = -delta.where(delta < 0, 0).rolling(window=14).mean()
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))
        
        # MACD
        exp1 = df['Close'].ewm(span=12, adjust=False).mean()
        exp2 = df['Close'].ewm(span=26, adjust=False).mean()
        df['MACD'] = exp1 - exp2
        df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
        df['MACD_Histogram'] = df['MACD'] - df['MACD_Signal']
        
        # Bollinger Bands
        df['BB_Middle'] = df['Close'].rolling(window=20).mean()
        bb_std = df['Close'].rolling(window=20).std()
        df['BB_Upper'] = df['BB_Middle'] + (bb_std * 2)
        df['BB_Lower'] = df['BB_Middle'] - (bb_std * 2)
        df['BB_Width'] = (df['BB_Upper'] - df['BB_Lower']) / df['BB_Middle']
        
        # Moving Averages
        for period in [20, 50, 100, 200]:
            df[f'SMA_{period}'] = df['Close'].rolling(window=period).mean()
            df[f'EMA_{period}'] = df['Close'].ewm(span=period, adjust=False).mean()
        
        # ATR
        high_low = df['High'] - df['Low']
        high_close = abs(df['High'] - df['Close'].shift())
        low_close = abs(df['Low'] - df['Close'].shift())
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = ranges.max(axis=1)
        df['ATR'] = true_range.rolling(14).mean()
        
        # Volume indicators
        df['Volume_SMA'] = df['Volume'].rolling(20).mean()
        df['Volume_Ratio'] = df['Volume'] / df['Volume_SMA']
        
        # Stochastic Oscillator
        low_14 = df['Low'].rolling(14).min()
        high_14 = df['High'].rolling(14).max()
        df['Stoch_K'] = 100 * ((df['Close'] - low_14) / (high_14 - low_14))
        df['Stoch_D'] = df['Stoch_K'].rolling(3).mean()
        
        # OBV
        df['OBV'] = (np.sign(df['Close'].diff()) * df['Volume']).fillna(0).cumsum()
        
        return df
    
    @staticmethod
    def calculate_ai_score(df: pd.DataFrame, info: dict) -> dict:
        score = 50
        signals = []
        
        try:
            latest = df.iloc[-1]
            
            # Technical Signals (50 points)
            # RSI (15 points)
            rsi = latest['RSI']
            if pd.notna(rsi):
                if 40 <= rsi <= 60:
                    score += 15
                    signals.append(("RSI Neutral", "positive"))
                elif rsi < 30:
                    score += 10
                    signals.append(("RSI Oversold", "positive"))
                elif rsi > 70:
                    score += 5
                    signals.append(("RSI Overbought", "negative"))
            
            # MACD (15 points)
            if pd.notna(latest['MACD']) and pd.notna(latest['MACD_Signal']):
                if latest['MACD'] > latest['MACD_Signal']:
                    score += 15
                    signals.append(("MACD Bullish", "positive"))
                else:
                    score += 5
                    signals.append(("MACD Bearish", "negative"))
            
            # Moving Average Trend (20 points)
            price = latest['Close']
            if pd.notna(latest['SMA_50']) and pd.notna(latest['SMA_200']):
                if price > latest['SMA_50'] > latest['SMA_200']:
                    score += 20
                    signals.append(("Strong Uptrend", "positive"))
                elif price > latest['SMA_50']:
                    score += 10
                    signals.append(("Uptrend", "positive"))
                elif price < latest['SMA_50']:
                    score += 5
                    signals.append(("Downtrend", "negative"))
            
            # Fundamental Signals (50 points)
            pe = info.get('trailingPE')
            if pe and 10 <= pe <= 25:
                score += 15
                signals.append(("Healthy P/E Ratio", "positive"))
            
            profit_margin = info.get('profitMargins')
            if profit_margin and profit_margin > 0.15:
                score += 15
                signals.append(("Strong Margins", "positive"))
            
            roe = info.get('returnOnEquity')
            if roe and roe > 0.15:
                score += 20
                signals.append(("Excellent ROE", "positive"))
            
        except Exception as e:
            signals.append((f"Analysis Error: {str(e)}", "neutral"))
        
        return {
            'score': max(0, min(100, score)),
            'signals': signals,
            'rating': 'Strong Buy' if score >= 80 else 'Buy' if score >= 65 else 'Hold' if score >= 50 else 'Sell'
        }
    
    @staticmethod
    def detect_patterns(df: pd.DataFrame) -> list:
        patterns = []
        try:
            latest = df.tail(20)
            
            # Golden Cross
            if len(latest) >= 2:
                if latest['SMA_50'].iloc[-1] > latest['SMA_200'].iloc[-1] and \
                   latest['SMA_50'].iloc[-2] <= latest['SMA_200'].iloc[-2]:
                    patterns.append(("Golden Cross Detected", "bullish"))
            
            # Death Cross
            if len(latest) >= 2:
                if latest['SMA_50'].iloc[-1] < latest['SMA_200'].iloc[-1] and \
                   latest['SMA_50'].iloc[-2] >= latest['SMA_200'].iloc[-2]:
                    patterns.append(("Death Cross Detected", "bearish"))
            
            # Bollinger Squeeze
            if latest['BB_Width'].iloc[-1] < latest['BB_Width'].mean() * 0.5:
                patterns.append(("Bollinger Squeeze", "neutral"))
            
        except:
            pass
        
        return patterns

# =============================================================================
# STOCK SCREENER ENGINE
# =============================================================================

class StockScreener:
    @staticmethod
    def get_stock_universe():
        """Returns list of popular stocks to screen"""
        return [
            # Tech
            'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'NVDA', 'TSLA', 'AMD', 'INTC', 'NFLX',
            'ADBE', 'CRM', 'ORCL', 'CSCO', 'QCOM', 'AVGO', 'TXN', 'SNOW', 'SHOP', 'SQ',
            # Finance
            'JPM', 'BAC', 'WFC', 'GS', 'MS', 'C', 'BLK', 'SCHW', 'AXP', 'V', 'MA', 'PYPL',
            # Healthcare
            'JNJ', 'UNH', 'PFE', 'ABBV', 'TMO', 'ABT', 'DHR', 'LLY', 'MRK', 'CVS',
            # Consumer
            'WMT', 'HD', 'NKE', 'SBUX', 'MCD', 'COST', 'TGT', 'LOW', 'DIS', 'CMCSA',
            # Energy
            'XOM', 'CVX', 'COP', 'SLB', 'EOG', 'MPC', 'PSX', 'VLO', 'OXY', 'HAL',
            # Industrial
            'BA', 'CAT', 'GE', 'HON', 'UNP', 'UPS', 'RTX', 'LMT', 'DE', 'MMM'
        ]
    
    @staticmethod
    def screen_stocks(criteria: dict, progress_callback=None):
        """Screen stocks based on criteria"""
        universe = StockScreener.get_stock_universe()
        results = []
        
        for idx, ticker in enumerate(universe):
            try:
                if progress_callback:
                    progress_callback(idx / len(universe))
                
                stock = yf.Ticker(ticker)
                info = stock.info
                hist = stock.history(period='6mo')
                
                if hist.empty:
                    continue
                
                hist = TechnicalAnalysis.calculate_all_indicators(hist)
                
                # Get metrics
                price = hist['Close'].iloc[-1]
                rsi = hist['RSI'].iloc[-1]
                pe_ratio = info.get('trailingPE', 0)
                market_cap = info.get('marketCap', 0)
                dividend_yield = info.get('dividendYield', 0)
                profit_margin = info.get('profitMargins', 0)
                
                # Calculate 6-month return
                change_6m = ((price - hist['Close'].iloc[0]) / hist['Close'].iloc[0]) * 100
                
                # Apply filters
                passes_filters = True
                
                if criteria.get('min_price') and price < criteria['min_price']:
                    passes_filters = False
                if criteria.get('max_price') and price > criteria['max_price']:
                    passes_filters = False
                if criteria.get('min_rsi') and rsi < criteria['min_rsi']:
                    passes_filters = False
                if criteria.get('max_rsi') and rsi > criteria['max_rsi']:
                    passes_filters = False
                if criteria.get('min_pe') and pe_ratio < criteria['min_pe']:
                    passes_filters = False
                if criteria.get('max_pe') and pe_ratio > criteria['max_pe']:
                    passes_filters = False
                if criteria.get('min_market_cap') and market_cap < criteria['min_market_cap'] * 1e9:
                    passes_filters = False
                if criteria.get('min_dividend') and dividend_yield < criteria['min_dividend'] / 100:
                    passes_filters = False
                
                if passes_filters:
                    ai_score = TechnicalAnalysis.calculate_ai_score(hist, info)
                    
                    results.append({
                        'Ticker': ticker,
                        'Name': info.get('shortName', ticker),
                        'Price': price,
                        'Change_6M': change_6m,
                        'RSI': rsi,
                        'P/E': pe_ratio if pe_ratio else 0,
                        'Market_Cap': market_cap / 1e9,
                        'Dividend': dividend_yield * 100 if dividend_yield else 0,
                        'AI_Score': ai_score['score'],
                        'Rating': ai_score['rating']
                    })
            except:
                continue
        
        if progress_callback:
            progress_callback(1.0)
        
        return pd.DataFrame(results)

class PredictionEngine:
    @staticmethod
    def predict_price(df: pd.DataFrame, days: int = 30) -> dict:
        try:
            if len(df) < 60:
                return None
            
            # Use last 90 days for prediction
            recent = df.tail(90).copy()
            recent['day_num'] = range(len(recent))
            
            X = recent['day_num'].values
            y = recent['Close'].values
            
            # Linear regression
            x_mean = X.mean()
            y_mean = y.mean()
            
            numerator = ((X - x_mean) * (y - y_mean)).sum()
            denominator = ((X - x_mean) ** 2).sum()
            
            if denominator == 0:
                return None
            
            slope = numerator / denominator
            intercept = y_mean - slope * x_mean
            
            # Adjust for momentum
            momentum = (df['Close'].iloc[-1] - df['Close'].iloc[-30]) / df['Close'].iloc[-30]
            adjusted_slope = slope * (1 + momentum * 0.3)
            
            # Make predictions
            future_days = range(len(recent), len(recent) + days)
            predictions = [max(0, adjusted_slope * day + intercept) for day in future_days]
            
            # Calculate confidence based on recent volatility
            volatility = df['Close'].pct_change().tail(30).std()
            confidence = max(0, min(100, 100 - (volatility * 1000)))
            
            return {
                'predictions': predictions,
                'current_price': df['Close'].iloc[-1],
                'predicted_price': predictions[-1],
                'change_pct': ((predictions[-1] - df['Close'].iloc[-1]) / df['Close'].iloc[-1]) * 100,
                'confidence': confidence,
                'trend': 'Bullish' if adjusted_slope > 0 else 'Bearish'
            }
        except:
            return None

# =============================================================================
# BACKTESTING ENGINE
# =============================================================================

class BacktestEngine:
    @staticmethod
    def run_strategy(ticker: str, start_date, end_date, capital: float = 10000) -> dict:
        try:
            # Fetch data
            stock = yf.Ticker(ticker)
            df = stock.history(start=start_date, end=end_date)
            
            if df.empty:
                return None
            
            df = TechnicalAnalysis.calculate_all_indicators(df)
            
            # Generate signals
            df['Signal'] = 0
            for i in range(1, len(df)):
                if pd.notna(df['MACD'].iloc[i]) and pd.notna(df['RSI'].iloc[i]):
                    # Buy signal
                    if (df['MACD'].iloc[i] > df['MACD_Signal'].iloc[i] and 
                        df['MACD'].iloc[i-1] <= df['MACD_Signal'].iloc[i-1] and 
                        df['RSI'].iloc[i] < 70 and df['RSI'].iloc[i] > 30):
                        df.loc[df.index[i], 'Signal'] = 1
                    # Sell signal
                    elif (df['MACD'].iloc[i] < df['MACD_Signal'].iloc[i] and 
                          df['MACD'].iloc[i-1] >= df['MACD_Signal'].iloc[i-1]):
                        df.loc[df.index[i], 'Signal'] = -1
            
            # Calculate returns
            df['Position'] = df['Signal'].replace(0, np.nan).ffill().fillna(0)
            df['Returns'] = df['Close'].pct_change()
            df['Strategy_Returns'] = df['Position'].shift(1) * df['Returns']
            df['Cumulative_Returns'] = (1 + df['Returns']).cumprod()
            df['Cumulative_Strategy'] = (1 + df['Strategy_Returns']).cumprod()
            
            # Calculate metrics
            total_return = (df['Cumulative_Strategy'].iloc[-1] - 1) * 100
            buy_hold_return = (df['Cumulative_Returns'].iloc[-1] - 1) * 100
            
            trades = df[df['Signal'] != 0]
            num_trades = len(trades)
            
            # Win rate
            winning_trades = len(df[(df['Signal'] == -1) & (df['Strategy_Returns'] > 0)])
            win_rate = (winning_trades / (num_trades / 2) * 100) if num_trades > 0 else 0
            
            # Sharpe ratio
            sharpe = np.sqrt(252) * df['Strategy_Returns'].mean() / df['Strategy_Returns'].std() if df['Strategy_Returns'].std() > 0 else 0
            
            # Max drawdown
            cumulative = df['Cumulative_Strategy']
            running_max = cumulative.expanding().max()
            drawdown = (cumulative - running_max) / running_max
            max_drawdown = drawdown.min() * 100
            
            return {
                'df': df,
                'total_return': total_return,
                'buy_hold_return': buy_hold_return,
                'alpha': total_return - buy_hold_return,
                'num_trades': num_trades,
                'win_rate': win_rate,
                'sharpe_ratio': sharpe,
                'max_drawdown': max_drawdown,
                'final_value': capital * df['Cumulative_Strategy'].iloc[-1]
            }
        except Exception as e:
            st.error(f"Backtest error: {e}")
            return None

# =============================================================================
# AUTHENTICATION UI
# =============================================================================

if not st.session_state.authenticated:
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown("<h1 style='text-align: center;'>WealthStockify Professional</h1>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; color: #94a3b8;'>Advanced Stock Analysis & Trading Platform</p>", unsafe_allow_html=True)
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        tab1, tab2, tab3 = st.tabs(["Sign In", "Create Account", "Reset Password"])
        
        with tab1:
            with st.form("signin_form"):
                email = st.text_input("Email Address", key="signin_email")
                password = st.text_input("Password", type="password", key="signin_password")
                submit = st.form_submit_button("Sign In", use_container_width=True)
                
                if submit:
                    if email and password:
                        success, user, profile = AuthService.signin(email, password)
                        if success:
                            st.session_state.authenticated = True
                            st.session_state.user = user
                            st.session_state.profile = profile
                            st.rerun()
                        else:
                            st.error("Invalid email or password")
                    else:
                        st.warning("Please enter both email and password")
        
        with tab2:
            with st.form("signup_form"):
                email = st.text_input("Email Address", key="signup_email")
                password = st.text_input("Password (minimum 6 characters)", type="password", key="signup_password")
                confirm = st.text_input("Confirm Password", type="password", key="confirm_password")
                submit = st.form_submit_button("Create Account", use_container_width=True)
                
                if submit:
                    if not email or not password or not confirm:
                        st.warning("Please fill in all fields")
                    elif password != confirm:
                        st.error("Passwords do not match")
                    elif len(password) < 6:
                        st.error("Password must be at least 6 characters")
                    else:
                        success, message = AuthService.signup(email, password)
                        if success:
                            st.success(message)
                        else:
                            st.error(message)
        
        with tab3:
            with st.form("reset_form"):
                email = st.text_input("Email Address", key="reset_email")
                submit = st.form_submit_button("Send Reset Link", use_container_width=True)
                
                if submit:
                    if email:
                        success, message = AuthService.reset_password(email)
                        if success:
                            st.success(message)
                        else:
                            st.error(message)
                    else:
                        st.warning("Please enter your email address")
    
    st.stop()

# =============================================================================
# MAIN APPLICATION
# =============================================================================

is_premium = st.session_state.profile.get('is_premium', False)

# Sidebar
with st.sidebar:
    st.markdown("### WealthStockify Pro")
    st.caption(f"👤 {st.session_state.user.email}")
    
    st.markdown("---")
    
    # Subscription status
    if is_premium:
        st.markdown('<div class="premium-badge">PREMIUM ACTIVE</div>', unsafe_allow_html=True)
        sub_end = st.session_state.profile.get('subscription_end_date')
        if sub_end:
            st.caption(f"Valid until: {sub_end[:10]}")
        
        if st.button("Cancel Subscription", use_container_width=True):
            if DatabaseService.cancel_subscription(st.session_state.user.id):
                st.session_state.profile = DatabaseService.get_user_profile(st.session_state.user.id)
                st.success("Subscription cancelled")
                st.rerun()
    else:
        st.markdown('<div class="free-badge">FREE TIER</div>', unsafe_allow_html=True)
        st.caption("Limited to basic features")
        
        if st.button("Upgrade to Premium", use_container_width=True, type="primary"):
            if DatabaseService.upgrade_to_premium(st.session_state.user.id):
                st.session_state.profile = DatabaseService.get_user_profile(st.session_state.user.id)
                st.balloons()
                st.success("Upgraded to Premium!")
                st.rerun()
    
    st.markdown("---")
    
    # Navigation
    st.markdown("#### Navigation")
    
    pages = {
        "dashboard": "📊 Dashboard",
        "analysis": "📈 Stock Analysis",
        "screener": "🔍 Stock Screener",
        "backtest": "⚡ Backtesting",
        "watchlist": "👁️ Watchlist",
        "portfolio": "💼 Portfolio"
    }
    
    for key, label in pages.items():
        if st.button(label, use_container_width=True, key=f"nav_{key}"):
            st.session_state.page = key
    
    st.markdown("---")
    
    # Premium features
    with st.expander("Premium Features"):
        features = [
            "Advanced Technical Indicators",
            "AI-Powered Stock Scoring",
            "Price Predictions (30/90 days)",
            "Pattern Recognition",
            "5-Year Backtesting",
            "Unlimited Watchlist",
            "Portfolio Tracking",
            "Stock Screener (50+ stocks)",
            "Export to CSV/PDF",
            "Priority Support"
        ]
        for f in features:
            icon = "✓" if is_premium else "✗"
            st.caption(f"{icon} {f}")
    
    st.markdown("---")
    
    if st.button("Sign Out", use_container_width=True):
        AuthService.signout()
        st.rerun()

# Main content area
if st.session_state.page == 'dashboard':
    st.title("📊 Dashboard")
    
    if is_premium:
        st.success("Welcome back! You have full access to all premium features.")
    else:
        st.info("You're on the free tier. Upgrade to Premium for advanced analytics!")
    
    st.markdown("### Quick Stats")
    
    col1, col2, col3, col4 = st.columns(4)
    
    watchlist = DatabaseService.get_watchlist(st.session_state.user.id)
    
    col1.metric("Watchlist Stocks", len(watchlist))
    col2.metric("Account Type", "Premium" if is_premium else "Free")
    col3.metric("Features Unlocked", "10/10" if is_premium else "3/10")
    col4.metric("Member Since", st.session_state.profile.get('created_at', 'N/A')[:10] if 'created_at' in st.session_state.profile else 'Today')

elif st.session_state.page == 'analysis':
    st.title("📈 Stock Analysis")
    
    col1, col2, col3 = st.columns([3, 2, 1])
    
    with col1:
        ticker = st.text_input("Enter Stock Ticker", "AAPL", key="analysis_ticker").upper()
    with col2:
        period = st.selectbox("Time Period", ["1mo", "3mo", "6mo", "1y", "2y", "5y"], index=2)
    with col3:
        st.write("")
        st.write("")
        analyze_btn = st.button("Analyze", type="primary")
    
    if ticker:
        try:
            with st.spinner(f"Analyzing {ticker}..."):
                stock = yf.Ticker(ticker)
                df = stock.history(period=period)
                info = stock.info
                
                if df.empty:
                    st.error("Invalid ticker or no data available")
                else:
                    df = TechnicalAnalysis.calculate_all_indicators(df)
                    
                    # Key metrics
                    price = df['Close'].iloc[-1]
                    prev = df['Close'].iloc[-2]
                    change_pct = ((price - prev) / prev) * 100
                    
                    col1, col2, col3, col4 = st.columns(4)
                    
                    col1.metric("Current Price", f"${price:.2f}", f"{change_pct:+.2f}%")
                    
                    if is_premium:
                        ai_analysis = TechnicalAnalysis.calculate_ai_score(df, info)
                        col2.metric("AI Score", f"{ai_analysis['score']:.0f}/100", ai_analysis['rating'])
                    else:
                        col2.metric("AI Score", "Premium Only")
                    
                    volume = info.get('volume', 0)
                    col3.metric("Volume", f"{volume/1e6:.1f}M")
                    
                    market_cap = info.get('marketCap', 0)
                    col4.metric("Market Cap", f"${market_cap/1e9:.1f}B" if market_cap > 0 else "N/A")
                    
                    st.markdown("---")
                    
                    # Chart
                    st.subheader("Price Chart & Technical Indicators")
                    
                    rows = 3 if is_premium else 1
                    fig = make_subplots(
                        rows=rows, cols=1,
                        shared_xaxes=True,
                        vertical_spacing=0.05,
                        row_heights=[0.6, 0.2, 0.2] if is_premium else [1],
                        subplot_titles=([f"{ticker} Price Action", "MACD", "RSI"] if is_premium else [f"{ticker} Price"])
                    )
                    
                    # Candlestick
                    fig.add_trace(go.Candlestick(
                        x=df.index,
                        open=df['Open'],
                        high=df['High'],
                        low=df['Low'],
                        close=df['Close'],
                        name='Price',
                        increasing_line_color='#22c55e',
                        decreasing_line_color='#ef4444'
                    ), row=1, col=1)
                    
                    if is_premium:
                        # Moving averages
                        fig.add_trace(go.Scatter(x=df.index, y=df['SMA_20'], name='SMA 20', line=dict(color='#fbbf24', width=1.5)), row=1, col=1)
                        fig.add_trace(go.Scatter(x=df.index, y=df['SMA_50'], name='SMA 50', line=dict(color='#f97316', width=1.5)), row=1, col=1)
                        fig.add_trace(go.Scatter(x=df.index, y=df['SMA_200'], name='SMA 200', line=dict(color='#ef4444', width=1.5)), row=1, col=1)
                        
                        # Bollinger Bands
                        fig.add_trace(go.Scatter(x=df.index, y=df['BB_Upper'], name='BB Upper', line=dict(color='#6b7280', width=1, dash='dash'), showlegend=False), row=1, col=1)
                        fig.add_trace(go.Scatter(x=df.index, y=df['BB_Lower'], name='BB Lower', line=dict(color='#6b7280', width=1, dash='dash'), fill='tonexty', fillcolor='rgba(107, 114, 128, 0.1)'), row=1, col=1)
                        
                        # MACD
                        colors = ['#22c55e' if val >= 0 else '#ef4444' for val in df['MACD_Histogram']]
                        fig.add_trace(go.Bar(x=df.index, y=df['MACD_Histogram'], name='MACD Histogram', marker_color=colors), row=2, col=1)
                        fig.add_trace(go.Scatter(x=df.index, y=df['MACD'], name='MACD', line=dict(color='#3b82f6', width=2)), row=2, col=1)
                        fig.add_trace(go.Scatter(x=df.index, y=df['MACD_Signal'], name='Signal', line=dict(color='#f97316', width=2)), row=2, col=1)
                        
                        # RSI
                        fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], name='RSI', line=dict(color='#8b5cf6', width=2), fill='tozeroy', fillcolor='rgba(139, 92, 246, 0.1)'), row=3, col=1)
                        fig.add_hline(y=70, line_dash="dash", line_color="#ef4444", annotation_text="Overbought", row=3, col=1)
                        fig.add_hline(y=30, line_dash="dash", line_color="#22c55e", annotation_text="Oversold", row=3, col=1)
                    
                    fig.update_layout(
                        height=800 if is_premium else 500,
                        template='plotly_dark',
                        xaxis_rangeslider_visible=False,
                        showlegend=True,
                        hovermode='x unified'
                    )
                    
                    st.plotly_chart(fig, use_container_width=True)
                    
                    # Premium features
                    if is_premium:
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            st.subheader("AI Analysis")
                            
                            score_color = "#22c55e" if ai_analysis['score'] >= 70 else "#fbbf24" if ai_analysis['score'] >= 50 else "#ef4444"
                            st.markdown(f"<h2 style='color: {score_color};'>{ai_analysis['score']:.0f}/100</h2>", unsafe_allow_html=True)
                            st.markdown(f"**Rating:** {ai_analysis['rating']}")
                            
                            st.markdown("**Signals:**")
                            for signal, sentiment in ai_analysis['signals']:
                                icon = "🟢" if sentiment == "positive" else "🔴" if sentiment == "negative" else "🟡"
                                st.caption(f"{icon} {signal}")
                            
                            # Pattern detection
                            patterns = TechnicalAnalysis.detect_patterns(df)
                            if patterns:
                                st.markdown("**Patterns:**")
                                for pattern, direction in patterns:
                                    icon = "📈" if direction == "bullish" else "📉" if direction == "bearish" else "➡️"
                                    st.caption(f"{icon} {pattern}")
                        
                        with col2:
                            st.subheader("Price Prediction")
                            
                            prediction = PredictionEngine.predict_price(df, 30)
                            if prediction:
                                st.metric(
                                    "30-Day Forecast",
                                    f"${prediction['predicted_price']:.2f}",
                                    f"{prediction['change_pct']:+.2f}%"
                                )
                                st.progress(prediction['confidence'] / 100)
                                st.caption(f"Confidence: {prediction['confidence']:.1f}% | Trend: {prediction['trend']}")
                                
                                st.markdown("**Fundamentals:**")
                                st.caption(f"P/E Ratio: {info.get('trailingPE', 'N/A')}")
                                st.caption(f"Dividend Yield: {info.get('dividendYield', 0)*100:.2f}%")
                                st.caption(f"52W Range: ${info.get('fiftyTwoWeekLow', 0):.2f} - ${info.get('fiftyTwoWeekHigh', 0):.2f}")
                            else:
                                st.warning("Insufficient data for prediction")
                        
                        # Add to watchlist
                        st.markdown("---")
                        if st.button(f"Add {ticker} to Watchlist", use_container_width=True):
                            if DatabaseService.add_to_watchlist(st.session_state.user.id, ticker):
                                st.success(f"Added {ticker} to watchlist!")
                            else:
                                st.error("Failed to add to watchlist")
                    else:
                        st.info("Upgrade to Premium to unlock AI analysis, predictions, and pattern detection")
                        
        except Exception as e:
            st.error(f"Error analyzing {ticker}: {str(e)}")

elif st.session_state.page == 'watchlist':
    st.title("👁️ Watchlist")
    
    if is_premium:
        col1, col2 = st.columns([3, 1])
        
        with col1:
            new_ticker = st.text_input("Add Stock to Watchlist", placeholder="Enter ticker symbol").upper()
        
        with col2:
            st.write("")
            st.write("")
            if st.button("Add Stock", type="primary"):
                if new_ticker:
                    if DatabaseService.add_to_watchlist(st.session_state.user.id, new_ticker):
                        st.success(f"Added {new_ticker}")
                        st.rerun()
                    else:
                        st.error("Failed to add")
        
        watchlist = DatabaseService.get_watchlist(st.session_state.user.id)
        
        if watchlist:
            st.markdown("---")
            
            for item in watchlist:
                ticker = item['ticker']
                
                try:
                    stock = yf.Ticker(ticker)
                    info = stock.info
                    hist = stock.history(period='1d')
                    
                    if not hist.empty:
                        price = hist['Close'].iloc[-1]
                        
                        col1, col2, col3, col4 = st.columns([2, 2, 2, 1])
                        
                        with col1:
                            st.markdown(f"**{ticker}**")
                            st.caption(info.get('shortName', ticker))
                        
                        with col2:
                            st.metric("Price", f"${price:.2f}")
                        
                        with col3:
                            change = info.get('regularMarketChangePercent', 0)
                            st.metric("Change", f"{change:+.2f}%")
                        
                        with col4:
                            if st.button("Remove", key=f"remove_{ticker}"):
                                DatabaseService.remove_from_watchlist(st.session_state.user.id, ticker)
                                st.rerun()
                        
                        st.markdown("---")
                except:
                    st.caption(f"{ticker} - Unable to fetch data")
        else:
            st.info("Your watchlist is empty. Add stocks to start tracking!")
    else:
        st.warning("Watchlist is a Premium feature. Upgrade to track unlimited stocks!")

elif st.session_state.page == 'screener':
    st.title("🔍 Stock Screener")
    
    if is_premium:
        st.markdown("Screen stocks based on technical and fundamental criteria")
        
        with st.expander("Screening Criteria", expanded=True):
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.markdown("**Price**")
                min_price = st.number_input("Min Price ($)", value=0.0, step=10.0)
                max_price = st.number_input("Max Price ($)", value=1000.0, step=10.0)
                
                st.markdown("**RSI**")
                min_rsi = st.slider("Min RSI", 0, 100, 0)
                max_rsi = st.slider("Max RSI", 0, 100, 100)
            
            with col2:
                st.markdown("**Fundamentals**")
                min_pe = st.number_input("Min P/E Ratio", value=0.0, step=1.0)
                max_pe = st.number_input("Max P/E Ratio", value=100.0, step=1.0)
                min_market_cap = st.number_input("Min Market Cap ($B)", value=0.0, step=1.0)
            
            with col3:
                st.markdown("**Income**")
                min_dividend = st.number_input("Min Dividend Yield (%)", value=0.0, step=0.1)
                
                st.markdown("**Sort By**")
                sort_by = st.selectbox("Sort Results By", 
                    ["AI_Score", "Price", "Change_6M", "RSI", "P/E", "Market_Cap", "Dividend"])
                ascending = st.checkbox("Ascending Order", value=False)
        
        if st.button("🔍 Run Screener", type="primary", use_container_width=True):
            criteria = {
                'min_price': min_price if min_price > 0 else None,
                'max_price': max_price if max_price < 1000 else None,
                'min_rsi': min_rsi if min_rsi > 0 else None,
                'max_rsi': max_rsi if max_rsi < 100 else None,
                'min_pe': min_pe if min_pe > 0 else None,
                'max_pe': max_pe if max_pe < 100 else None,
                'min_market_cap': min_market_cap if min_market_cap > 0 else None,
                'min_dividend': min_dividend if min_dividend > 0 else None
            }
            
            progress_bar = st.progress(0)
            status = st.empty()
            
            def update_progress(pct):
                progress_bar.progress(pct)
                status.text(f"Screening stocks... {int(pct * 100)}%")
            
            results = StockScreener.screen_stocks(criteria, update_progress)
            
            progress_bar.empty()
            status.empty()
            
            if not results.empty:
                st.success(f"Found {len(results)} stocks matching your criteria")
                
                # Sort results
                results = results.sort_values(by=sort_by, ascending=ascending)
                
                # Display summary stats
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Stocks Found", len(results))
                col2.metric("Avg AI Score", f"{results['AI_Score'].mean():.1f}")
                col3.metric("Avg P/E", f"{results['P/E'].mean():.1f}")
                col4.metric("Avg Dividend", f"{results['Dividend'].mean():.2f}%")
                
                st.markdown("---")
                
                # Format dataframe
                display_df = results.copy()
                display_df['Price'] = display_df['Price'].apply(lambda x: f"${x:.2f}")
                display_df['Change_6M'] = display_df['Change_6M'].apply(lambda x: f"{x:+.1f}%")
                display_df['RSI'] = display_df['RSI'].apply(lambda x: f"{x:.1f}")
                display_df['P/E'] = display_df['P/E'].apply(lambda x: f"{x:.1f}")
                display_df['Market_Cap'] = display_df['Market_Cap'].apply(lambda x: f"${x:.1f}B")
                display_df['Dividend'] = display_df['Dividend'].apply(lambda x: f"{x:.2f}%")
                display_df['AI_Score'] = display_df['AI_Score'].apply(lambda x: f"{x:.0f}")
                
                st.dataframe(
                    display_df,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Ticker": st.column_config.TextColumn("Ticker", width="small"),
                        "Name": st.column_config.TextColumn("Company", width="medium"),
                        "AI_Score": st.column_config.TextColumn("AI Score", width="small"),
                        "Rating": st.column_config.TextColumn("Rating", width="small")
                    }
                )
                
                # Export option
                if st.button("📥 Export Results to CSV"):
                    csv = results.to_csv(index=False)
                    st.download_button(
                        "Download CSV",
                        csv,
                        f"screener_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                        "text/csv"
                    )
            else:
                st.warning("No stocks match your criteria. Try adjusting the filters.")
    else:
        st.warning("Stock Screener is a Premium feature!")
        st.info("Upgrade to Premium to screen 80+ stocks with advanced filters")

elif st.session_state.page == 'portfolio':
    st.title("💼 Portfolio Tracker")
    
    if is_premium:
        # Add new position
        with st.expander("➕ Add New Position", expanded=False):
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                new_ticker = st.text_input("Ticker", key="portfolio_ticker").upper()
            with col2:
                shares = st.number_input("Shares", min_value=0.0, step=0.1, key="portfolio_shares")
            with col3:
                avg_price = st.number_input("Avg Price ($)", min_value=0.0, step=0.01, key="portfolio_price")
            with col4:
                purchase_date = st.date_input("Purchase Date", datetime.now(), key="portfolio_date")
            
            if st.button("Add Position", use_container_width=True):
                if new_ticker and shares > 0 and avg_price > 0:
                    if DatabaseService.add_portfolio_position(
                        st.session_state.user.id,
                        new_ticker,
                        shares,
                        avg_price,
                        purchase_date.isoformat()
                    ):
                        st.success(f"Added {shares} shares of {new_ticker}")
                        st.rerun()
                    else:
                        st.error("Failed to add position")
                else:
                    st.warning("Please fill all fields")
        
        # Get portfolio
        portfolio = DatabaseService.get_portfolio(st.session_state.user.id)
        
        if portfolio:
            st.markdown("---")
            
            # Calculate totals
            total_invested = 0
            total_current_value = 0
            portfolio_data = []
            
            for position in portfolio:
                ticker = position['ticker']
                shares = position['shares']
                avg_price = position['average_price']
                
                try:
                    stock = yf.Ticker(ticker)
                    current_price = stock.history(period='1d')['Close'].iloc[-1]
                    
                    invested = shares * avg_price
                    current_value = shares * current_price
                    profit_loss = current_value - invested
                    profit_loss_pct = (profit_loss / invested) * 100
                    
                    total_invested += invested
                    total_current_value += current_value
                    
                    portfolio_data.append({
                        'ticker': ticker,
                        'shares': shares,
                        'avg_price': avg_price,
                        'current_price': current_price,
                        'invested': invested,
                        'current_value': current_value,
                        'profit_loss': profit_loss,
                        'profit_loss_pct': profit_loss_pct,
                        'purchase_date': position.get('purchase_date', 'N/A')
                    })
                except:
                    portfolio_data.append({
                        'ticker': ticker,
                        'shares': shares,
                        'avg_price': avg_price,
                        'current_price': 0,
                        'invested': shares * avg_price,
                        'current_value': 0,
                        'profit_loss': 0,
                        'profit_loss_pct': 0,
                        'purchase_date': position.get('purchase_date', 'N/A')
                    })
            
            # Portfolio summary
            total_pl = total_current_value - total_invested
            total_pl_pct = (total_pl / total_invested * 100) if total_invested > 0 else 0
            
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Total Invested", f"${total_invested:,.2f}")
            col2.metric("Current Value", f"${total_current_value:,.2f}")
            col3.metric("Total P/L", f"${total_pl:,.2f}", f"{total_pl_pct:+.2f}%")
            col4.metric("Positions", len(portfolio))
            
            st.markdown("---")
            
            # Individual positions
            for pos in portfolio_data:
                with st.container():
                    col1, col2, col3, col4, col5, col6 = st.columns([2, 1, 1, 1, 1, 1])
                    
                    with col1:
                        st.markdown(f"**{pos['ticker']}**")
                        st.caption(f"{pos['shares']} shares")
                    
                    with col2:
                        st.metric("Avg Price", f"${pos['avg_price']:.2f}")
                    
                    with col3:
                        st.metric("Current", f"${pos['current_price']:.2f}")
                    
                    with col4:
                        st.metric("Invested", f"${pos['invested']:,.0f}")
                    
                    with col5:
                        pl_color = "normal" if pos['profit_loss'] >= 0 else "inverse"
                        st.metric("P/L", f"${pos['profit_loss']:,.0f}", 
                                f"{pos['profit_loss_pct']:+.1f}%", 
                                delta_color=pl_color)
                    
                    with col6:
                        if st.button("Remove", key=f"remove_portfolio_{pos['ticker']}"):
                            DatabaseService.remove_portfolio_position(st.session_state.user.id, pos['ticker'])
                            st.rerun()
                    
                    st.markdown("---")
            
            # Portfolio chart
            if len(portfolio_data) > 0:
                st.subheader("Portfolio Allocation")
                
                fig = go.Figure(data=[go.Pie(
                    labels=[p['ticker'] for p in portfolio_data],
                    values=[p['current_value'] for p in portfolio_data],
                    hole=0.4,
                    marker=dict(colors=['#3b82f6', '#22c55e', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899'])
                )])
                
                fig.update_layout(
                    template='plotly_dark',
                    height=400,
                    showlegend=True
                )
                
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Your portfolio is empty. Add your first position above!")
    else:
        st.warning("Portfolio Tracker is a Premium feature!")
        st.info("Upgrade to Premium to track your investments and see real-time P/L")

elif st.session_state.page == 'backtest':
    st.title("⚡ Backtesting Engine")
    
    if is_premium:
        col1, col2, col3 = st.columns(3)
        
        with col1:
            ticker = st.text_input("Stock Ticker", "AAPL").upper()
        with col2:
            start_date = st.date_input("Start Date", datetime.now() - timedelta(days=365*2))
        with col3:
            end_date = st.date_input("End Date", datetime.now())
        
        capital = st.number_input("Initial Capital ($)", value=10000, min_value=1000, step=1000)
        
        if st.button("Run Backtest", type="primary", use_container_width=True):
            with st.spinner("Running backtest..."):
                result = BacktestEngine.run_strategy(ticker, start_date, end_date, capital)
                
                if result:
                    st.success("Backtest completed!")
                    
                    col1, col2, col3, col4 = st.columns(4)
                    col1.metric("Strategy Return", f"{result['total_return']:.2f}%")
                    col2.metric("Buy & Hold", f"{result['buy_hold_return']:.2f}%")
                    col3.metric("Alpha", f"{result['alpha']:.2f}%")
                    col4.metric("Sharpe Ratio", f"{result['sharpe_ratio']:.2f}")
                    
                    col1, col2, col3, col4 = st.columns(4)
                    col1.metric("Total Trades", result['num_trades'])
                    col2.metric("Win Rate", f"{result['win_rate']:.1f}%")
                    col3.metric("Max Drawdown", f"{result['max_drawdown']:.2f}%")
                    col4.metric("Final Value", f"${result['final_value']:,.0f}")
                    
                    st.markdown("---")
                    
                    fig = go.Figure()
                    
                    fig.add_trace(go.Scatter(
                        x=result['df'].index,
                        y=result['df']['Cumulative_Strategy'] * capital,
                        name='Strategy',
                        line=dict(color='#3b82f6', width=2),
                        fill='tozeroy',
                        fillcolor='rgba(59, 130, 246, 0.1)'
                    ))
                    
                    fig.add_trace(go.Scatter(
                        x=result['df'].index,
                        y=result['df']['Cumulative_Returns'] * capital,
                        name='Buy & Hold',
                        line=dict(color='#6b7280', width=2, dash='dash')
                    ))
                    
                    fig.update_layout(
                        title="Equity Curve",
                        xaxis_title="Date",
                        yaxis_title="Portfolio Value ($)",
                        height=500,
                        template='plotly_dark',
                        hovermode='x unified'
                    )
                    
                    st.plotly_chart(fig, use_container_width=True)
                    
                    # Trade history
                    trades = result['df'][result['df']['Signal'] != 0][['Close', 'Signal', 'RSI', 'MACD']].copy()
                    if not trades.empty:
                        st.subheader("Trade History")
                        trades['Action'] = trades['Signal'].apply(lambda x: 'BUY' if x == 1 else 'SELL')
                        trades['Price'] = trades['Close'].apply(lambda x: f"${x:.2f}")
                        st.dataframe(trades[['Action', 'Price', 'RSI', 'MACD']], use_container_width=True)
                else:
                    st.error("Backtest failed. Check ticker and date range.")
    else:
        st.warning("Backtesting is a Premium feature!")

else:
    st.info(f"{st.session_state.page.title()} - Feature under development")

st.markdown("---")
st.caption("WealthStockify Professional © 2025 | Not financial advice")
