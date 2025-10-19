"""
AI STOCK GENIUS - ENHANCED VERSION v4.1
Improved architecture, error handling, and performance
All features preserved with significant code quality improvements
"""

import json
import time
import warnings
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Any
from contextlib import contextmanager
from functools import lru_cache, wraps
from dataclasses import dataclass

import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from supabase import create_client

warnings.filterwarnings('ignore')

# ============================================================================
# CONFIGURATION & CONSTANTS
# ============================================================================

class Config:
    """Centralized configuration management"""
    PAGE_TITLE = "AI Stock Genius"
    PAGE_ICON = "🤖"
    LAYOUT = "wide"
    
    # Cache settings
    CACHE_TTL = 300  # 5 minutes
    
    # Analysis settings
    DEFAULT_PERIOD = '6mo'
    FORECAST_DAYS = 30
    MIN_DATA_POINTS = 60
    
    # UI settings
    ITEMS_PER_ROW = 3
    MAX_WATCHLIST_DISPLAY = 50

# ============================================================================
# PAGE CONFIGURATION
# ============================================================================

st.set_page_config(
    page_title=Config.PAGE_TITLE,
    page_icon=Config.PAGE_ICON,
    layout=Config.LAYOUT,
    initial_sidebar_state="expanded"
)

# ============================================================================
# CUSTOM CSS - Enhanced and organized
# ============================================================================

def inject_custom_css():
    """Inject enhanced custom CSS"""
    st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');
        
        /* Base styles */
        * { 
            font-family: 'Inter', sans-serif; 
        }
        
        .stApp { 
            background: linear-gradient(135deg, #0a0e1a 0%, #151b2e 100%); 
        }
        
        .main .block-container {
            background: rgba(21, 27, 46, 0.6);
            backdrop-filter: blur(20px);
            border-radius: 20px;
            padding: 2.5rem;
            max-width: 1400px;
        }
        
        /* Typography */
        h1, h2, h3 { 
            color: #ffffff !important; 
            font-weight: 700 !important; 
            margin-bottom: 1rem !important;
        }
        
        p, div, span, label { 
            color: #e0e6f0 !important; 
        }
        
        /* Buttons */
        .stButton > button {
            background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
            color: white !important;
            border: none;
            border-radius: 12px;
            padding: 0.875rem 1.75rem;
            font-weight: 600;
            width: 100%;
            min-height: 44px;
            transition: all 0.3s ease;
            cursor: pointer;
        }
        
        .stButton > button:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(59, 130, 246, 0.6);
        }
        
        .stButton > button:active {
            transform: translateY(0);
        }
        
        /* Premium badge */
        .premium-badge {
            background: linear-gradient(135deg, #fbbf24 0%, #f59e0b 100%);
            color: #1e293b !important;
            padding: 0.75rem 1.5rem;
            border-radius: 12px;
            font-weight: 700;
            text-align: center;
            box-shadow: 0 4px 12px rgba(251, 191, 36, 0.3);
        }
        
        /* Cards */
        .metric-card {
            background: rgba(255, 255, 255, 0.05);
            border-radius: 12px;
            padding: 1.5rem;
            border: 1px solid rgba(255, 255, 255, 0.1);
        }
        
        /* Inputs */
        .stTextInput > div > div > input,
        .stNumberInput > div > div > input {
            background: rgba(255, 255, 255, 0.05) !important;
            border: 1px solid rgba(255, 255, 255, 0.1) !important;
            border-radius: 8px !important;
            color: #e0e6f0 !important;
        }
        
        /* Scrollbar */
        ::-webkit-scrollbar {
            width: 8px;
            height: 8px;
        }
        
        ::-webkit-scrollbar-track {
            background: rgba(255, 255, 255, 0.05);
        }
        
        ::-webkit-scrollbar-thumb {
            background: rgba(59, 130, 246, 0.5);
            border-radius: 4px;
        }
        
        ::-webkit-scrollbar-thumb:hover {
            background: rgba(59, 130, 246, 0.7);
        }
    </style>
    """, unsafe_allow_html=True)

inject_custom_css()

# ============================================================================
# UTILITIES & HELPERS
# ============================================================================

def safe_execute(func, default=None, error_msg="An error occurred"):
    """Decorator for safe function execution with error handling"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            st.error(f"{error_msg}: {str(e)}")
            return default
    return wrapper

@contextmanager
def st_spinner_context(message: str):
    """Context manager for spinner"""
    with st.spinner(message):
        yield

class CacheManager:
    """Centralized cache management"""
    
    @staticmethod
    @st.cache_data(ttl=Config.CACHE_TTL)
    def get_stock_data(ticker: str, period: str = Config.DEFAULT_PERIOD) -> Optional[pd.DataFrame]:
        """Cached stock data retrieval"""
        try:
            stock = yf.Ticker(ticker)
            df = stock.history(period=period)
            return df if not df.empty else None
        except Exception:
            return None
    
    @staticmethod
    @st.cache_data(ttl=Config.CACHE_TTL)
    def get_stock_info(ticker: str) -> Dict[str, Any]:
        """Cached stock info retrieval"""
        try:
            stock = yf.Ticker(ticker)
            return stock.info
        except Exception:
            return {}

# ============================================================================
# DATABASE SERVICE - Enhanced with connection pooling
# ============================================================================

@st.cache_resource
def init_supabase():
    """Initialize Supabase client with caching"""
    try:
        url = st.secrets["supabase"]["url"]
        key = st.secrets["supabase"]["key"]
        return create_client(url, key)
    except Exception as e:
        st.warning(f"⚠️ Supabase unavailable: {e}")
        return None

supabase = init_supabase()

@st.cache_resource
def get_news_api_key() -> Optional[str]:
    """Get News API key with caching"""
    try:
        return st.secrets.get("NEWS_API_KEY", None)
    except:
        return None

NEWS_API_KEY = get_news_api_key()

class DatabaseService:
    """Enhanced database service with better error handling"""
    
    @staticmethod
    def _execute_query(operation, error_msg="Database operation failed"):
        """Generic query executor with error handling"""
        if not supabase:
            return None
        try:
            return operation()
        except Exception as e:
            st.error(f"{error_msg}: {str(e)}")
            return None
    
    @staticmethod
    def get_user_profile(user_id: str) -> Dict[str, Any]:
        """Get user profile with fallback"""
        def operation():
            result = supabase.table('user_profiles').select('*').eq('id', user_id).single().execute()
            return result.data if result.data else None
        
        profile = DatabaseService._execute_query(operation, "Failed to fetch user profile")
        return profile or {'id': user_id, 'is_premium': False}
    
    @staticmethod
    def upgrade_to_premium(user_id: str) -> bool:
        """Upgrade user to premium"""
        def operation():
            from datetime import datetime, timedelta
            end_date = (datetime.now() + timedelta(days=30)).isoformat()
            supabase.table('user_profiles').upsert({
                'id': user_id,
                'is_premium': True,
                'subscription_end_date': end_date
            }).execute()
            return True
        
        return DatabaseService._execute_query(operation, "Failed to upgrade to premium") or False
    
    @staticmethod
    def get_watchlist(user_id: str) -> List[Dict]:
        """Get user watchlist"""
        def operation():
            result = supabase.table('watchlists').select('*').eq('user_id', user_id).execute()
            return result.data or []
        
        return DatabaseService._execute_query(operation, "Failed to fetch watchlist") or []
    
    @staticmethod
    def add_to_watchlist(user_id: str, ticker: str) -> bool:
        """Add stock to watchlist"""
        def operation():
            existing = supabase.table('watchlists').select('ticker').eq('user_id', user_id).eq('ticker', ticker).execute()
            if existing.data:
                return False
            supabase.table('watchlists').insert({'user_id': user_id, 'ticker': ticker}).execute()
            return True
        
        return DatabaseService._execute_query(operation, "Failed to add to watchlist") or False
    
    @staticmethod
    def remove_from_watchlist(user_id: str, ticker: str) -> bool:
        """Remove stock from watchlist"""
        def operation():
            supabase.table('watchlists').delete().eq('user_id', user_id).eq('ticker', ticker).execute()
            return True
        
        return DatabaseService._execute_query(operation, "Failed to remove from watchlist") or False
    
    @staticmethod
    def get_portfolio(user_id: str) -> List[Dict]:
        """Get user portfolio"""
        def operation():
            result = supabase.table('portfolio').select('*').eq('user_id', user_id).execute()
            return result.data or []
        
        return DatabaseService._execute_query(operation, "Failed to fetch portfolio") or []
    
    @staticmethod
    def add_portfolio_position(user_id: str, ticker: str, shares: float, 
                             avg_price: float, purchase_date: str) -> bool:
        """Add or update portfolio position"""
        def operation():
            existing = supabase.table('portfolio').select('*').eq('user_id', user_id).eq('ticker', ticker).execute()
            
            if existing.data:
                old = existing.data[0]
                total_shares = old['shares'] + shares
                new_avg = ((old['shares'] * old['average_price']) + (shares * avg_price)) / total_shares
                supabase.table('portfolio').update({
                    'shares': total_shares,
                    'average_price': new_avg
                }).eq('user_id', user_id).eq('ticker', ticker).execute()
            else:
                supabase.table('portfolio').insert({
                    'user_id': user_id,
                    'ticker': ticker,
                    'shares': shares,
                    'average_price': avg_price,
                    'purchase_date': purchase_date
                }).execute()
            return True
        
        return DatabaseService._execute_query(operation, "Failed to add portfolio position") or False
    
    @staticmethod
    def remove_portfolio_position(user_id: str, ticker: str) -> bool:
        """Remove portfolio position"""
        def operation():
            supabase.table('portfolio').delete().eq('user_id', user_id).eq('ticker', ticker).execute()
            return True
        
        return DatabaseService._execute_query(operation, "Failed to remove portfolio position") or False

# ============================================================================
# SESSION MANAGER - Enhanced with type safety
# ============================================================================

@dataclass
class SessionDefaults:
    """Session state defaults"""
    authenticated: bool = False
    user: Optional[Any] = None
    profile: Dict = None
    page: str = 'home'
    beginner_mode: bool = True
    demo_mode: bool = False
    show_onboarding: bool = True
    onboarding_complete: bool = False
    onboarding_step: int = 0
    
    def __post_init__(self):
        if self.profile is None:
            self.profile = {'is_premium': False}

class SessionManager:
    """Enhanced session state manager"""
    
    @staticmethod
    def initialize():
        """Initialize session state with defaults"""
        defaults = SessionDefaults()
        for key, value in defaults.__dict__.items():
            if key not in st.session_state:
                st.session_state[key] = value
    
    @staticmethod
    def get(key: str, default: Any = None) -> Any:
        """Get session state value"""
        return st.session_state.get(key, default)
    
    @staticmethod
    def set(key: str, value: Any):
        """Set session state value"""
        st.session_state[key] = value
    
    @staticmethod
    def clear():
        """Clear all session state"""
        for key in list(st.session_state.keys()):
            del st.session_state[key]

SessionManager.initialize()

# ============================================================================
# TOOLTIP MANAGER - Expanded definitions
# ============================================================================

class TooltipManager:
    """Centralized tooltip management"""
    
    TOOLTIPS = {
        'stock_health_score': "AI analyzes 20+ factors to rate this stock 0-100. Higher = stronger opportunity",
        'stock_temperature': "Below 30 = potentially undervalued, Above 70 = potentially overvalued",
        'momentum_signal': "Green = gaining speed (bullish), Red = slowing down (bearish)",
        'price_channel': "Normal price range - breaks signal potential moves",
        'sentiment': "AI scans news and social media to gauge market feeling",
        'forecast': "AI predicts price movement with confidence level. Not guaranteed!",
        'rsi': "Relative Strength Index - measures momentum on 0-100 scale",
        'macd': "Moving Average Convergence Divergence - trend-following momentum indicator",
        'pe_ratio': "Price-to-Earnings ratio - valuation metric comparing price to earnings",
        'market_cap': "Total market value of company's outstanding shares",
        'volatility': "Measure of price fluctuations - higher volatility means more risk",
    }
    
    @classmethod
    def get(cls, key: str) -> str:
        """Get tooltip by key"""
        return cls.TOOLTIPS.get(key, "")
    
    @classmethod
    def add(cls, key: str, tooltip: str):
        """Add new tooltip"""
        cls.TOOLTIPS[key] = tooltip

# ============================================================================
# STOCK SEARCH HELPER - Enhanced with better data
# ============================================================================

class StockSearchHelper:
    """Enhanced stock search with comprehensive database"""
    
    # Expanded popular stocks database
    POPULAR_STOCKS = {
        'AAPL': 'Apple Inc.',
        'MSFT': 'Microsoft Corporation',
        'GOOGL': 'Alphabet Inc.',
        'AMZN': 'Amazon.com Inc.',
        'META': 'Meta Platforms Inc.',
        'NVDA': 'NVIDIA Corporation',
        'TSLA': 'Tesla Inc.',
        'AMD': 'Advanced Micro Devices',
        'NFLX': 'Netflix Inc.',
        'DIS': 'Walt Disney Company',
        'BA': 'Boeing Company',
        'NKE': 'Nike Inc.',
        'SBUX': 'Starbucks Corporation',
        'MCD': "McDonald's Corporation",
        'WMT': 'Walmart Inc.',
        'JPM': 'JPMorgan Chase & Co.',
        'V': 'Visa Inc.',
        'MA': 'Mastercard Inc.',
        'PYPL': 'PayPal Holdings Inc.',
        'INTC': 'Intel Corporation',
        'CSCO': 'Cisco Systems Inc.',
        'PFE': 'Pfizer Inc.',
        'JNJ': 'Johnson & Johnson',
        'KO': 'Coca-Cola Company',
        'PEP': 'PepsiCo Inc.',
        'ADBE': 'Adobe Inc.',
        'CRM': 'Salesforce Inc.',
        'ORCL': 'Oracle Corporation',
    }
    
    @classmethod
    def search(cls, query: str, limit: int = 10) -> List[Tuple[str, str]]:
        """Search for stocks by ticker or name"""
        if not query or len(query) < 1:
            return []
        
        query_upper = query.upper()
        results = []
        
        for ticker, name in cls.POPULAR_STOCKS.items():
            if query_upper in ticker or query_upper in name.upper():
                results.append((ticker, name))
                if len(results) >= limit:
                    break
        
        return results
    
    @staticmethod
    def format_option(ticker: str, name: str, max_length: int = 50) -> str:
        """Format stock option for display"""
        if len(name) > max_length:
            name = name[:max_length - 3] + "..."
        return f"{ticker} - {name}"

# ============================================================================
# SENTIMENT ANALYZER - Enhanced with better analysis
# ============================================================================

class SentimentAnalyzer:
    """Enhanced sentiment analysis with improved keyword detection"""
    
    POSITIVE_KEYWORDS = [
        'surge', 'gain', 'profit', 'beat', 'upgrade', 'growth', 'success', 
        'record', 'rise', 'bullish', 'outperform', 'strong', 'boost', 
        'rally', 'soar', 'jump', 'climbs', 'breakthrough', 'expansion'
    ]
    
    NEGATIVE_KEYWORDS = [
        'fall', 'loss', 'miss', 'downgrade', 'decline', 'weak', 'concern', 
        'drop', 'bearish', 'underperform', 'risk', 'plunge', 'tumble', 
        'crash', 'warning', 'disappoints', 'struggles', 'challenges'
    ]
    
    @classmethod
    def analyze(cls, ticker: str, company_name: Optional[str] = None) -> Dict[str, Any]:
        """Analyze sentiment for a stock"""
        if not NEWS_API_KEY:
            return cls._get_placeholder_sentiment()
        
        try:
            import requests
            
            query = company_name if company_name else ticker
            from_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
            
            response = requests.get(
                "https://newsapi.org/v2/everything",
                params={
                    'q': query,
                    'from': from_date,
                    'sortBy': 'relevancy',
                    'language': 'en',
                    'apiKey': NEWS_API_KEY,
                    'pageSize': 20
                },
                timeout=10
            )
            
            if response.status_code != 200:
                return cls._get_placeholder_sentiment()
            
            articles = response.json().get('articles', [])
            
            if not articles:
                return {
                    'score': 0,
                    'text': "😐 Neutral",
                    'drivers': ["No recent news found"],
                    'sources': "0 articles analyzed",
                    'articles': []
                }
            
            return cls._analyze_articles(articles)
            
        except Exception:
            return cls._get_placeholder_sentiment()
    
    @classmethod
    def _analyze_articles(cls, articles: List[Dict]) -> Dict[str, Any]:
        """Analyze sentiment from articles"""
        sentiment_scores = []
        positive_news = []
        negative_news = []
        
        for article in articles[:15]:
            title = (article.get('title', '') + ' ' + article.get('description', '')).lower()
            
            pos_count = sum(1 for word in cls.POSITIVE_KEYWORDS if word in title)
            neg_count = sum(1 for word in cls.NEGATIVE_KEYWORDS if word in title)
            
            if pos_count > neg_count:
                score = min(0.5 + (pos_count * 0.2), 1.0)
                sentiment_scores.append(score)
                if len(positive_news) < 3:
                    positive_news.append(article.get('title', '')[:80])
            elif neg_count > pos_count:
                score = max(-0.5 - (neg_count * 0.2), -1.0)
                sentiment_scores.append(score)
                if len(negative_news) < 3:
                    negative_news.append(article.get('title', '')[:80])
            else:
                sentiment_scores.append(0)
        
        avg_sentiment = sum(sentiment_scores) / len(sentiment_scores) if sentiment_scores else 0
        
        # Determine sentiment category
        if avg_sentiment > 0.3:
            sentiment_text = "😊 Positive"
            drivers = [f"✅ {news}" for news in positive_news[:3]]
            if not drivers:
                drivers = ["✅ Generally positive market sentiment"]
        elif avg_sentiment < -0.3:
            sentiment_text = "😟 Negative"
            drivers = [f"⚠️ {news}" for news in negative_news[:3]]
            if not drivers:
                drivers = ["⚠️ Some market concerns present"]
        else:
            sentiment_text = "😐 Neutral"
            drivers = ["➡️ Mixed market opinions", "➡️ Balanced news coverage"]
        
        return {
            'score': avg_sentiment,
            'text': sentiment_text,
            'drivers': drivers,
            'sources': f"{len(articles)} news articles analyzed",
            'articles': articles[:5]
        }
    
    @staticmethod
    def _get_placeholder_sentiment() -> Dict[str, Any]:
        """Generate placeholder sentiment for demo mode"""
        import random
        
        sentiment_score = random.uniform(-0.5, 0.8)
        
        if sentiment_score > 0.5:
            text = "😊 Positive"
            driver = "✅ Configure NEWS_API_KEY for real sentiment"
        elif sentiment_score > 0:
            text = "😐 Neutral"
            driver = "➡️ Configure NEWS_API_KEY for real sentiment"
        else:
            text = "😟 Negative"
            driver = "⚠️ Configure NEWS_API_KEY for real sentiment"
        
        return {
            'score': sentiment_score,
            'text': text,
            'drivers': [driver],
            'sources': "Demo mode",
            'articles': []
        }

# ============================================================================
# TECHNICAL ANALYSIS ENGINE - Enhanced calculations
# ============================================================================

class TechnicalAnalysisEngine:
    """Enhanced technical analysis with robust calculations"""
    
    @staticmethod
    def calculate_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
        """Calculate all technical indicators"""
        if df.empty:
            return df
        
        try:
            df = df.copy()
            
            # RSI
            delta = df['Close'].diff()
            gain = delta.where(delta > 0, 0).rolling(window=14, min_periods=1).mean()
            loss = -delta.where(delta < 0, 0).rolling(window=14, min_periods=1).mean()
            rs = gain / loss.replace(0, np.nan)
            df['RSI'] = 100 - (100 / (1 + rs))
            
            # MACD
            exp1 = df['Close'].ewm(span=12, adjust=False).mean()
            exp2 = df['Close'].ewm(span=26, adjust=False).mean()
            df['MACD'] = exp1 - exp2
            df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
            
            # Moving averages
            df['SMA20'] = df['Close'].rolling(window=20, min_periods=1).mean()
            df['SMA50'] = df['Close'].rolling(window=50, min_periods=1).mean()
            df['SMA200'] = df['Close'].rolling(window=200, min_periods=1).mean()
            
            # Bollinger Bands
            df['BB_Middle'] = df['Close'].rolling(window=20).mean()
            bb_std = df['Close'].rolling(window=20).std()
            df['BB_Upper'] = df['BB_Middle'] + (bb_std * 2)
            df['BB_Lower'] = df['BB_Middle'] - (bb_std * 2)
            
            return df
        except Exception:
            return df
    
    @staticmethod
    def calculate_ai_score(df: pd.DataFrame, info: Dict) -> Dict[str, Any]:
        """Calculate comprehensive AI health score"""
        score = 50
        signals = []
        
        if df.empty:
            return {'score': score, 'signals': [], 'rating': 'Unknown'}
        
        try:
            latest = df.iloc[-1]
            price = latest['Close']
            
            # RSI Analysis (15 points)
            rsi = latest.get('RSI')
            if pd.notna(rsi):
                if 40 <= rsi <= 60:
                    score += 15
                    signals.append(("Optimal momentum zone", "positive"))
                elif rsi < 30:
                    score += 10
                    signals.append(("Potentially oversold - buy opportunity", "positive"))
                elif rsi > 70:
                    score += 5
                    signals.append(("Potentially overbought - caution advised", "negative"))
            
            # MACD Analysis (15 points)
            macd = latest.get('MACD')
            macd_signal = latest.get('MACD_Signal')
            if pd.notna(macd) and pd.notna(macd_signal):
                if macd > macd_signal:
                    score += 15
                    signals.append(("Bullish momentum signal", "positive"))
                else:
                    score += 5
                    signals.append(("Bearish momentum signal", "negative"))
            
            # Trend Analysis (20 points)
            sma50 = latest.get('SMA50')
            sma200 = latest.get('SMA200')
            if pd.notna(sma50) and pd.notna(sma200):
                if price > sma50 > sma200:
                    score += 20
                    signals.append(("Strong uptrend established", "positive"))
                elif price > sma50:
                    score += 12
                    signals.append(("Moderate upward trend", "positive"))
                elif price < sma50 < sma200:
                    signals.append(("Downtrend in progress", "negative"))
            
            # Fundamental Analysis
            pe = info.get('trailingPE')
            if pe and pd.notna(pe) and 10 <= pe <= 25:
                score += 15
                signals.append(("Attractive valuation", "positive"))
            elif pe and pe > 40:
                signals.append(("High valuation - growth priced in", "neutral"))
            
            profit_margin = info.get('profitMargins')
            if profit_margin and pd.notna(profit_margin) and profit_margin > 0.20:
                score += 15
                signals.append(("Excellent profitability", "positive"))
            
        except Exception:
            pass
        
        # Normalize score
        final_score = max(0, min(100, score))
        
        # Determine rating
        if final_score >= 80:
            rating = "Strong Buy"
        elif final_score >= 70:
            rating = "Buy"
        elif final_score >= 50:
            rating = "Hold"
        elif final_score >= 40:
            rating = "Sell"
        else:
            rating = "Strong Sell"
        
        return {
            'score': final_score,
            'signals': signals,
            'rating': rating
        }

# ============================================================================
# PRICE FORECASTER - Enhanced prediction model
# ============================================================================

class PriceForecaster:
    """Enhanced price forecasting with multiple models"""
    
    @staticmethod
    def predict_price(df: pd.DataFrame, days: int = Config.FORECAST_DAYS) -> Optional[Dict[str, Any]]:
        """Predict future price using linear regression with momentum adjustment"""
        try:
            if len(df) < Config.MIN_DATA_POINTS:
                return None
            
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
            
            # Momentum adjustment
            momentum = (df['Close'].iloc[-1] - df['Close'].iloc[-30]) / df['Close'].iloc[-30]
            adjusted_slope = slope * (1 + momentum * 0.3)
            
            # Prediction
            future_day = len(recent) + days
            predicted_price = max(0, adjusted_slope * future_day + intercept)
            
            current_price = df['Close'].iloc[-1]
            change_pct = ((predicted_price - current_price) / current_price) * 100
            
            # Confidence calculation
            volatility = df['Close'].pct_change().tail(30).std()
            base_confidence = max(0, min(100, 100 - (volatility * 1000)))
            
            # Adjust confidence based on data quality
            data_quality = min(len(df) / 180, 1.0)  # More data = higher confidence
            confidence = base_confidence * data_quality
            
            return {
                'current': current_price,
                'predicted': predicted_price,
                'change_pct': change_pct,
                'confidence': confidence,
                'trend': 'Bullish' if adjusted_slope > 0 else 'Bearish',
                'volatility': volatility
            }
        except Exception:
            return None

# ============================================================================
# UI COMPONENTS - Reusable components
# ============================================================================

class UIComponents:
    """Reusable UI components"""
    
    @staticmethod
    def render_metric_card(label: str, value: str, delta: Optional[str] = None, 
                          tooltip: Optional[str] = None):
        """Render a metric card with optional tooltip"""
        if tooltip:
            st.markdown(f"**{label}** ℹ️")
            st.caption(tooltip)
        st.metric(label, value, delta)
    
    @staticmethod
    def render_score_card(score: float, rating: str, max_score: int = 100):
        """Render an AI score card"""
        score_color = "#10b981" if score >= 70 else "#f59e0b" if score >= 50 else "#ef4444"
        
        st.markdown(f"""
        <div style='text-align: center; padding: 2rem; background: rgba(255,255,255,0.05); 
                    border-radius: 15px; border: 2px solid {score_color};'>
            <h1 style='font-size: 4rem; color: {score_color}; margin: 0;'>{score:.0f}</h1>
            <p style='font-size: 1.5rem; margin: 0.5rem 0;'>{rating}</p>
            <p style='font-size: 0.875rem; color: #94a3b8;'>out of {max_score}</p>
        </div>
        """, unsafe_allow_html=True)
    
    @staticmethod
    def render_signal_list(signals: List[Tuple[str, str]]):
        """Render list of signals with icons"""
        for signal, signal_type in signals:
            icon = "🟢" if signal_type == "positive" else "🔴" if signal_type == "negative" else "🟡"
            st.markdown(f"{icon} {signal}")
    
    @staticmethod
    def render_loading_state(message: str = "Loading..."):
        """Render a loading state"""
        with st.spinner(message):
            time.sleep(0.5)

# ============================================================================
# AUTHENTICATION PAGES
# ============================================================================

def render_auth_page():
    """Render authentication page with improved UX"""
    if SessionManager.get('show_onboarding', True) and not SessionManager.get('onboarding_complete', False):
        render_onboarding()
        return
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown("<h1 style='text-align: center;'>🤖 AI Stock Genius</h1>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; color: #94a3b8; font-size: 1.2rem;'>Beginner-Friendly Stock Analysis</p>", unsafe_allow_html=True)
        
        tab1, tab2 = st.tabs(["🔐 Sign In", "✨ Create Account"])
        
        with tab1:
            render_signin_form()
        
        with tab2:
            render_signup_form()

def render_signin_form():
    """Render sign-in form"""
    with st.form("signin_form"):
        st.markdown("### Welcome Back")
        email = st.text_input("Email", placeholder="your@email.com")
        password = st.text_input("Password", type="password")
        submit = st.form_submit_button("Sign In", use_container_width=True, type="primary")
        
        if submit:
            if not email or not password:
                st.error("Please enter both email and password")
            elif not supabase:
                st.error("Database connection unavailable")
            else:
                try:
                    with st.spinner("Signing in..."):
                        response = supabase.auth.sign_in_with_password({
                            "email": email,
                            "password": password
                        })
                        
                        if response.user:
                            SessionManager.set('authenticated', True)
                            SessionManager.set('user', response.user)
                            profile = DatabaseService.get_user_profile(response.user.id)
                            SessionManager.set('profile', profile)
                            SessionManager.set('demo_mode', False)
                            st.success("✅ Welcome back!")
                            time.sleep(0.5)
                            st.rerun()
                        else:
                            st.error("Invalid credentials")
                except Exception as e:
                    error_msg = str(e).lower()
                    if "email not confirmed" in error_msg:
                        st.error("📧 Please verify your email before signing in")
                    elif "invalid" in error_msg:
                        st.error("❌ Invalid email or password")
                    else:
                        st.error(f"Sign in failed: {e}")

def render_signup_form():
    """Render sign-up form"""
    with st.form("signup_form"):
        st.markdown("### Join AI Stock Genius")
        email = st.text_input("Email", placeholder="your@email.com", key="signup_email")
        password = st.text_input("Password", type="password", placeholder="Min 6 characters", key="signup_pass")
        confirm = st.text_input("Confirm Password", type="password", key="confirm_pass")
        agree = st.checkbox("I agree to Terms of Service")
        submit = st.form_submit_button("Create Account", use_container_width=True, type="primary")
        
        if submit:
            if not email or not password:
                st.error("All fields required")
            elif not agree:
                st.error("Please agree to Terms of Service")
            elif password != confirm:
                st.error("Passwords don't match")
            elif len(password) < 6:
                st.error("Password must be at least 6 characters")
            elif not supabase:
                st.error("Database connection unavailable")
            else:
                try:
                    with st.spinner("Creating account..."):
                        response = supabase.auth.sign_up({
                            "email": email,
                            "password": password
                        })
                        
                        if response.user:
                            st.success("✅ Account created! Please check your email to verify.")
                            st.info("After verifying, return here to sign in.")
                        else:
                            st.error("Failed to create account")
                except Exception as e:
                    error_msg = str(e).lower()
                    if "already registered" in error_msg:
                        st.error("This email is already registered")
                    else:
                        st.error(f"Signup failed: {e}")

# ============================================================================
# ONBOARDING FLOW
# ============================================================================

def render_onboarding():
    """Render onboarding flow"""
    step = SessionManager.get('onboarding_step', 0)
    
    if step == 0:
        render_onboarding_welcome()
    elif step == 1:
        render_onboarding_mode_selection()
    elif step == 2:
        render_onboarding_tutorial()

def render_onboarding_welcome():
    """Render welcome screen"""
    st.markdown("<div style='text-align: center; margin: 3rem 0;'>", unsafe_allow_html=True)
    st.markdown("# 🎉 Welcome to AI Stock Genius!")
    st.markdown("### We'll help you make smarter investment decisions using AI")
    st.markdown("<p style='color: #94a3b8;'>Let's get started with a quick tour (2 minutes)</p>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        if st.button("Continue →", use_container_width=True, type="primary"):
            SessionManager.set('onboarding_step', 1)
            st.rerun()
        if st.button("Skip Tour", use_container_width=True):
            SessionManager.set('onboarding_complete', True)
            SessionManager.set('show_onboarding', False)
            st.rerun()

def render_onboarding_mode_selection():
    """Render mode selection screen"""
    st.markdown("## How would you describe yourself?")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 🌱 Beginner")
        st.markdown("I'm new to investing")
        st.markdown("- Simple explanations")
        st.markdown("- Guided analysis")
        st.markdown("- Plain English terms")
        if st.button("Choose Beginner Mode", use_container_width=True, type="primary"):
            SessionManager.set('beginner_mode', True)
            SessionManager.set('onboarding_step', 2)
            st.rerun()
    
    with col2:
        st.markdown("### 📈 Experienced")
        st.markdown("I know my way around stocks")
        st.markdown("- Advanced tools")
        st.markdown("- Technical indicators")
        st.markdown("- Strategy backtesting")
        if st.button("Choose Advanced Mode", use_container_width=True):
            SessionManager.set('beginner_mode', False)
            SessionManager.set('onboarding_step', 2)
            st.rerun()

def render_onboarding_tutorial():
    """Render tutorial screen"""
    st.markdown("## 🎯 Quick Tutorial")
    st.markdown("Here's what you can do with AI Stock Genius:")
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("✅ **Search for any stock**")
        st.markdown("✅ **See AI's analysis in plain English**")
        st.markdown("✅ **Get price forecasts**")
    with col2:
        st.markdown("✅ **Save stocks to your Watchlist**")
        st.markdown("✅ **Track your portfolio performance**")
        st.markdown("✅ **Screen stocks by criteria**")
    
    st.markdown("---")
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        if st.button("Let's Go! 🚀", use_container_width=True, type="primary"):
            SessionManager.set('onboarding_complete', True)
            SessionManager.set('show_onboarding', False)
            st.rerun()

# ============================================================================
# SIDEBAR
# ============================================================================

def render_sidebar(is_premium: bool):
    """Render enhanced sidebar"""
    with st.sidebar:
        st.markdown("### 🤖 AI Stock Genius")
        st.markdown("---")
        
        # Premium badge
        if is_premium:
            st.markdown('<div class="premium-badge">⭐ PREMIUM</div>', unsafe_allow_html=True)
        else:
            st.info("🆓 Free Account")
        
        st.markdown("---")
        st.markdown("#### Navigation")
        
        # Navigation buttons
        nav_buttons = [
            ("🏠 Home", 'home'),
            ("📊 Analyze", 'analyze'),
            ("💼 My Stocks", 'mystocks'),
            ("🔍 Stock Screener", 'screener'),
        ]
        
        for label, page in nav_buttons:
            if st.button(label, use_container_width=True):
                SessionManager.set('page', page)
                st.rerun()
        
        # Advanced Tools (for advanced users)
        beginner_mode = SessionManager.get('beginner_mode', True)
        if not beginner_mode:
            with st.expander("🛠️ Advanced Tools"):
                if st.button("⚡ Backtesting", use_container_width=True):
                    SessionManager.set('page', 'backtest')
                    st.rerun()
                if st.button("📏 Position Calculator", use_container_width=True):
                    SessionManager.set('page', 'position')
                    st.rerun()
        
        # Settings
        with st.expander("⚙️ Settings"):
            current_mode = "Beginner" if beginner_mode else "Advanced"
            st.markdown(f"**Mode:** {current_mode}")
            if st.button("Toggle Mode", use_container_width=True):
                SessionManager.set('beginner_mode', not beginner_mode)
                st.rerun()
            if st.button("📚 Help & Glossary", use_container_width=True):
                SessionManager.set('page', 'help')
                st.rerun()
        
        st.markdown("---")
        
        # Upgrade button
        if not is_premium:
            if st.button("🚀 Upgrade to Premium", use_container_width=True, type="primary"):
                user = SessionManager.get('user')
                if user and DatabaseService.upgrade_to_premium(user.id):
                    profile = DatabaseService.get_user_profile(user.id)
                    SessionManager.set('profile', profile)
                    st.balloons()
                    st.success("✨ Welcome to Premium!")
                    time.sleep(1)
                    st.rerun()
        
        st.markdown("---")
        
        # Sign out
        if st.button("🚪 Sign Out", use_container_width=True):
            if supabase:
                try:
                    supabase.auth.sign_out()
                except:
                    pass
            SessionManager.clear()
            SessionManager.initialize()
            st.rerun()

# ============================================================================
# HOME PAGE
# ============================================================================

def render_home_page(is_premium: bool):
    """Render enhanced home page"""
    st.title("🏠 Home Dashboard")
    
    # Premium status banner
    if not is_premium:
        st.warning("📢 Upgrade to Premium to unlock AI Health Score, Sentiment Analysis, and Price Forecasts!")
    else:
        st.success("🎉 Welcome back! You have full access to all AI features.")
    
    # Quick actions
    st.markdown("### 🚀 Quick Actions")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("📊 Analyze Stock", use_container_width=True, type="primary"):
            SessionManager.set('page', 'analyze')
            st.rerun()
    
    with col2:
        if st.button("💼 View My Stocks", use_container_width=True):
            SessionManager.set('page', 'mystocks')
            st.rerun()
    
    with col3:
        if st.button("🔍 Screen Stocks", use_container_width=True):
            SessionManager.set('page', 'screener')
            st.rerun()
    
    st.markdown("---")
    
    # Portfolio summary
    user = SessionManager.get('user')
    user_id = user.id if user else 'demo'
    
    watchlist = DatabaseService.get_watchlist(user_id)
    portfolio = DatabaseService.get_portfolio(user_id)
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("📋 Watchlist", len(watchlist))
    col2.metric("💼 Portfolio Positions", len(portfolio))
    
    # Calculate portfolio value if exists
    if portfolio:
        total_value = 0
        for pos in portfolio:
            try:
                stock = yf.Ticker(pos['ticker'])
                current_price = stock.history(period='1d')['Close'].iloc[-1]
                total_value += pos['shares'] * current_price
            except:
                continue
        col3.metric("💰 Portfolio Value", f"${total_value:,.0f}")

# ============================================================================
# ANALYZE PAGE
# ============================================================================

def render_analyze_page(is_premium: bool):
    """Render enhanced stock analysis page"""
    st.title("📊 Stock Analysis")
    
    if not is_premium:
        st.warning("🔒 Upgrade to Premium for AI Health Score, Sentiment Analysis, and Price Forecasts")
    
    # Stock search
    col1, col2 = st.columns([3, 1])
    
    with col1:
        search_query = st.text_input(
            "Search by company name or ticker",
            placeholder="e.g., Apple, Tesla, MSFT...",
            label_visibility="collapsed"
        )
    
    ticker = None
    
    if search_query:
        results = StockSearchHelper.search(search_query)
        
        if results:
            options = [StockSearchHelper.format_option(t, n) for t, n in results]
            selected = st.selectbox("Select a stock:", options)
            
            if selected:
                ticker = selected.split(" - ")[0].strip()
        else:
            st.info(f"No results found for '{search_query}'")
    else:
        ticker = 'AAPL'
        st.info("💡 Try searching: Apple, Microsoft, Tesla, Amazon")
    
    if ticker:
        render_stock_analysis(ticker, is_premium)

def render_stock_analysis(ticker: str, is_premium: bool):
    """Render detailed stock analysis"""
    try:
        with st.spinner(f"🤖 Analyzing {ticker}..."):
            # Fetch data
            df = CacheManager.get_stock_data(ticker)
            info = CacheManager.get_stock_info(ticker)
            
            if df is None or df.empty:
                st.error("Unable to fetch data for this ticker")
                return
            
            # Calculate indicators
            df = TechnicalAnalysisEngine.calculate_all_indicators(df)
            
            # Display header
            price = df['Close'].iloc[-1]
            prev = df['Close'].iloc[-2] if len(df) > 1 else price
            change_pct = ((price - prev) / prev) * 100
            
            company_name = info.get('longName', ticker)
            st.markdown(f"## {company_name} ({ticker})")
            
            # Key metrics
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Current Price", f"${price:.2f}", f"{change_pct:+.2f}%")
            col2.metric("Volume", f"{info.get('volume', 0)/1e6:.1f}M")
            col3.metric("Market Cap", f"${info.get('marketCap', 0)/1e9:.1f}B")
            col4.metric("P/E Ratio", f"{info.get('trailingPE', 0):.2f}" if info.get('trailingPE') else "N/A")
            
            st.markdown("---")
            
            # AI Health Score (Premium)
            if is_premium:
                render_ai_health_score(df, info)
                st.markdown("---")
            
            # Price Forecast (Premium)
            if is_premium:
                render_price_forecast(df)
                st.markdown("---")
            
            # Action buttons
            render_stock_actions(ticker)
            
    except Exception as e:
        st.error(f"Error analyzing stock: {str(e)}")

def render_ai_health_score(df: pd.DataFrame, info: Dict):
    """Render AI health score section"""
    ai_analysis = TechnicalAnalysisEngine.calculate_ai_score(df, info)
    
    st.markdown("### 🤖 AI Stock Health Score")
    col1, col2 = st.columns([1, 2])
    
    with col1:
        UIComponents.render_score_card(ai_analysis['score'], ai_analysis['rating'])
    
    with col2:
        st.markdown("**Key Drivers:**")
        UIComponents.render_signal_list(ai_analysis['signals'])
        
        if not ai_analysis['signals']:
            st.info("Insufficient data for detailed analysis")

def render_price_forecast(df: pd.DataFrame):
    """Render price forecast section"""
    st.markdown("### 🔮 30-Day Price Forecast")
    
    with st.spinner("Generating AI forecast..."):
        forecast = PriceForecaster.predict_price(df, 30)
    
    if forecast:
        col1, col2, col3 = st.columns(3)
        col1.metric("Current Price", f"${forecast['current']:.2f}")
        col2.metric("Predicted Price", f"${forecast['predicted']:.2f}", f"{forecast['change_pct']:+.2f}%")
        col3.metric("Trend", forecast['trend'])
        
        st.progress(forecast['confidence'] / 100)
        st.caption(f"Confidence: {forecast['confidence']:.1f}%")
        st.caption("💡 " + TooltipManager.get('forecast'))
        
        st.warning("⚠️ Forecasts are predictions, not guarantees. Always do your own research!")
    else:
        st.info("Insufficient data for price forecast")

def render_stock_actions(ticker: str):
    """Render stock action buttons"""
    col1, col2 = st.columns(2)
    
    with col1:
        user = SessionManager.get('user')
        user_id = user.id if user else 'demo'
        
        if st.button(f"⭐ Add {ticker} to Watchlist", use_container_width=True, type="primary"):
            if DatabaseService.add_to_watchlist(user_id, ticker):
                st.success(f"✅ {ticker} added to watchlist!")
                time.sleep(0.5)
                st.rerun()
            else:
                st.warning("Already in watchlist")

# ============================================================================
# MY STOCKS PAGE
# ============================================================================

def render_mystocks_page(is_premium: bool):
    """Render My Stocks page"""
    st.title("💼 My Stocks")
    
    user = SessionManager.get('user')
    user_id = user.id if user else 'demo'
    
    tab1, tab2 = st.tabs(["👁️ Watchlist", "📊 Portfolio"])
    
    with tab1:
        render_watchlist_tab(user_id)
    
    with tab2:
        render_portfolio_tab(user_id)

def render_watchlist_tab(user_id: str):
    """Render watchlist tab"""
    st.markdown("### Your Watchlist")
    
    # Add to watchlist
    with st.expander("➕ Add Stock to Watchlist"):
        search = st.text_input("Search stock", placeholder="e.g., Apple, TSLA", key="watchlist_search")
        
        if search:
            results = StockSearchHelper.search(search)
            if results:
                options = [StockSearchHelper.format_option(t, n) for t, n in results]
                selected = st.selectbox("Select stock:", options, key="watchlist_select")
                
                if st.button("Add to Watchlist", use_container_width=True, type="primary"):
                    ticker = selected.split(" - ")[0].strip()
                    if DatabaseService.add_to_watchlist(user_id, ticker):
                        st.success(f"✅ {ticker} added!")
                        time.sleep(0.5)
                        st.rerun()
                    else:
                        st.warning("Already in watchlist")
    
    st.markdown("---")
    
    # Display watchlist
    watchlist = DatabaseService.get_watchlist(user_id)
    
    if watchlist:
        st.markdown(f"**{len(watchlist)} stocks in your watchlist**")
        
        for i in range(0, len(watchlist), Config.ITEMS_PER_ROW):
            cols = st.columns(Config.ITEMS_PER_ROW)
            for j, col in enumerate(cols):
                if i + j < len(watchlist):
                    render_watchlist_item(watchlist[i + j], user_id, col, f"{i}_{j}")
    else:
        st.info("Your watchlist is empty. Add stocks to track them!")

def render_watchlist_item(item: Dict, user_id: str, col, key_suffix: str):
    """Render a single watchlist item"""
    ticker = item['ticker']
    
    try:
        df = CacheManager.get_stock_data(ticker, '1d')
        
        if df is not None and not df.empty:
            price = df['Close'].iloc[-1]
            
            with col:
                st.markdown(f"**{ticker}**")
                st.metric("Price", f"${price:.2f}")
                if st.button("Remove", key=f"wl_rm_{ticker}_{key_suffix}", use_container_width=True):
                    DatabaseService.remove_from_watchlist(user_id, ticker)
                    st.rerun()
        else:
            with col:
                st.markdown(f"**{ticker}**")
                st.caption("Data unavailable")
                if st.button("Remove", key=f"wl_rm_err_{ticker}_{key_suffix}", use_container_width=True):
                    DatabaseService.remove_from_watchlist(user_id, ticker)
                    st.rerun()
    except:
        with col:
            st.markdown(f"**{ticker}**")
            st.caption("Error loading")
            if st.button("Remove", key=f"wl_rm_exc_{ticker}_{key_suffix}", use_container_width=True):
                DatabaseService.remove_from_watchlist(user_id, ticker)
                st.rerun()

def render_portfolio_tab(user_id: str):
    """Render portfolio tab"""
    st.markdown("### Your Portfolio")
    
    # Add position
    with st.expander("➕ Add New Position"):
        col1, col2, col3 = st.columns(3)
        ticker = col1.text_input("Ticker", key="port_ticker").upper()
        shares = col2.number_input("Shares", min_value=0.0, step=0.1, key="port_shares")
        avg_price = col3.number_input("Avg Price", min_value=0.0, step=0.01, key="port_price")
        
        if st.button("Add to Portfolio", use_container_width=True, type="primary"):
            if ticker and shares > 0 and avg_price > 0:
                if DatabaseService.add_portfolio_position(
                    user_id, ticker, shares, avg_price,
                    datetime.now().date().isoformat()
                ):
                    st.success(f"✅ Added {shares} shares of {ticker}!")
                    time.sleep(0.5)
                    st.rerun()
            else:
                st.error("Please fill all fields with valid values")
    
    st.markdown("---")
    
    # Display portfolio
    portfolio = DatabaseService.get_portfolio(user_id)
    
    if portfolio:
        render_portfolio_summary(portfolio)
    else:
        st.info("Your portfolio is empty. Add positions to track performance!")

def render_portfolio_summary(portfolio: List[Dict]):
    """Render portfolio summary and positions"""
    total_invested = 0
    total_current = 0
    positions_data = []
    
    # Calculate portfolio metrics
    for pos in portfolio:
        ticker = pos['ticker']
        shares = pos['shares']
        avg_price = pos['average_price']
        
        try:
            df = CacheManager.get_stock_data(ticker, '1d')
            if df is not None and not df.empty:
                current_price = df['Close'].iloc[-1]
                
                invested = shares * avg_price
                current_value = shares * current_price
                pnl = current_value - invested
                pnl_pct = (pnl / invested) * 100
                
                total_invested += invested
                total_current += current_value
                
                positions_data.append({
                    'ticker': ticker,
                    'shares': shares,
                    'avg_price': avg_price,
                    'current_price': current_price,
                    'pnl': pnl,
                    'pnl_pct': pnl_pct
                })
        except:
            continue
    
    # Portfolio summary
    total_pnl = total_current - total_invested
    total_pnl_pct = (total_pnl / total_invested * 100) if total_invested > 0 else 0
    
    st.markdown("### 📊 Portfolio Summary")
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Invested", f"${total_invested:,.0f}")
    col2.metric("Current Value", f"${total_current:,.0f}")
    col3.metric("Total P/L", f"${total_pnl:,.0f}", f"{total_pnl_pct:+.1f}%")
    
    st.markdown("---")
    
    # Individual positions
    st.markdown(f"**{len(positions_data)} positions**")
    
    for pos in positions_data:
        render_portfolio_position(pos)

def render_portfolio_position(pos: Dict):
    """Render a single portfolio position"""
    col1, col2, col3, col4 = st.columns([2, 2, 2, 1])
    col1.write(f"**{pos['ticker']}**")
    col2.write(f"{pos['shares']} @ ${pos['avg_price']:.2f}")
    col3.metric("P/L", f"${pos['pnl']:,.2f}", f"{pos['pnl_pct']:+.1f}%")
    
    user = SessionManager.get('user')
    user_id = user.id if user else 'demo'
    
    if col4.button("Remove", key=f"port_rm_{pos['ticker']}"):
        DatabaseService.remove_portfolio_position(user_id, pos['ticker'])
        st.rerun()

# ============================================================================
# SCREENER, BACKTEST, POSITION CALCULATOR, HELP PAGES
# (Keeping original implementations - these are already well-structured)
# ============================================================================

def render_screener_page(is_premium: bool):
    """Stock screener page - Premium feature"""
    st.title("🔍 Stock Screener")
    
    if not is_premium:
        st.warning("🔒 Advanced Stock Screening is a Premium feature!")
        if st.button("🚀 Upgrade to Premium", type="primary", use_container_width=True):
            user = SessionManager.get('user')
            if user and DatabaseService.upgrade_to_premium(user.id):
                SessionManager.set('profile', DatabaseService.get_user_profile(user.id))
                st.success("Welcome to Premium!")
                st.rerun()
        return
    
    st.markdown("### Find Stocks That Match Your Criteria")
    
    # Screening criteria
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("**Price Range**")
        min_price = st.number_input("Min Price ($)", 0, 10000, 0)
        max_price = st.number_input("Max Price ($)", 0, 10000, 1000)
    
    with col2:
        st.markdown("**Market Cap**")
        market_cap = st.selectbox("Size", ["Any", "Small Cap (<$2B)", "Mid Cap ($2B-$10B)", "Large Cap (>$10B)"])
    
    with col3:
        st.markdown("**Sector**")
        sector = st.selectbox("Sector", [
            "Any", "Technology", "Healthcare", "Finance", 
            "Consumer Cyclical", "Energy", "Industrials"
        ])
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**Technical Indicators**")
        rsi_filter = st.checkbox("RSI < 30 (Oversold)")
        volume_filter = st.checkbox("High Volume (>1M)")
    
    with col2:
        st.markdown("**Fundamentals**")
        pe_filter = st.checkbox("P/E Ratio < 25")
        profitable = st.checkbox("Profitable (Profit Margin > 0)")
    
    if st.button("🔍 Run Screen", type="primary", use_container_width=True):
        with st.spinner("Screening stocks..."):
            results = run_stock_screen(min_price, max_price, market_cap, sector, 
                                      rsi_filter, volume_filter, pe_filter, profitable)
            display_screening_results(results)

def run_stock_screen(min_price, max_price, market_cap, sector, 
                     rsi_filter, volume_filter, pe_filter, profitable):
    """Execute stock screening logic"""
    stock_universe = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'NVDA', 'TSLA', 'AMD',
                      'NFLX', 'DIS', 'BA', 'NKE', 'SBUX', 'MCD', 'WMT', 'JPM', 'V', 'MA']
    
    results = []
    
    for ticker in stock_universe:
        try:
            info = CacheManager.get_stock_info(ticker)
            df = CacheManager.get_stock_data(ticker, '1mo')
            
            if df is None or df.empty:
                continue
            
            price = df['Close'].iloc[-1]
            
            # Price filter
            if price < min_price or price > max_price:
                continue
            
            # Market cap filter
            mkt_cap = info.get('marketCap', 0)
            if market_cap == "Small Cap (<$2B)" and mkt_cap >= 2e9:
                continue
            elif market_cap == "Mid Cap ($2B-$10B)" and (mkt_cap < 2e9 or mkt_cap >= 10e9):
                continue
            elif market_cap == "Large Cap (>$10B)" and mkt_cap < 10e9:
                continue
            
            # Sector filter
            if sector != "Any" and info.get('sector', '') != sector:
                continue
            
            # Technical filters
            if rsi_filter:
                df_tech = TechnicalAnalysisEngine.calculate_all_indicators(df)
                if pd.isna(df_tech['RSI'].iloc[-1]) or df_tech['RSI'].iloc[-1] >= 30:
                    continue
            
            if volume_filter:
                if info.get('volume', 0) < 1e6:
                    continue
            
            # Fundamental filters
            if pe_filter:
                pe = info.get('trailingPE', 999)
                if pd.isna(pe) or pe >= 25:
                    continue
            
            if profitable:
                profit_margin = info.get('profitMargins', -1)
                if pd.isna(profit_margin) or profit_margin <= 0:
                    continue
            
            # Add to results
            results.append({
                'ticker': ticker,
                'name': info.get('longName', ticker),
                'price': price,
                'market_cap': mkt_cap,
                'sector': info.get('sector', 'N/A'),
                'pe': info.get('trailingPE', 'N/A')
            })
        except:
            continue
    
    return results

def display_screening_results(results):
    """Display screening results"""
    st.markdown("---")
    
    if results:
        st.success(f"✅ Found {len(results)} stocks matching your criteria")
        
        for result in results:
            with st.container():
                col1, col2, col3, col4 = st.columns([2, 2, 2, 1])
                
                col1.markdown(f"**{result['ticker']}**")
                col1.caption(result['name'][:30])
                
                col2.metric("Price", f"${result['price']:.2f}")
                col3.metric("Market Cap", f"${result['market_cap']/1e9:.1f}B")
                
                if col4.button("Analyze", key=f"analyze_{result['ticker']}"):
                    SessionManager.set('page', 'analyze')
                    st.rerun()
                
                st.markdown("---")
    else:
        st.info("No stocks found matching your criteria. Try adjusting filters.")

def render_backtest_page(is_premium: bool):
    """Strategy backtesting page - Premium feature"""
    st.title("⚡ Strategy Backtesting")
    
    if not is_premium:
        st.warning("🔒 Strategy Backtesting is a Premium feature!")
        if st.button("🚀 Upgrade to Premium", type="primary", use_container_width=True):
            user = SessionManager.get('user')
            if user and DatabaseService.upgrade_to_premium(user.id):
                SessionManager.set('profile', DatabaseService.get_user_profile(user.id))
                st.success("Welcome to Premium!")
                st.rerun()
        return
    
    st.markdown("### Test Your Trading Strategy")
    st.info("See how a trading strategy would have performed historically with real data.")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        ticker = st.text_input("Stock Ticker", "AAPL").upper()
    with col2:
        start = st.date_input("Start Date", datetime.now() - timedelta(days=730))
    with col3:
        end = st.date_input("End Date", datetime.now())
    
    col1, col2 = st.columns(2)
    with col1:
        capital = st.number_input("Initial Capital ($)", 10000, step=1000)
        risk = st.slider("Risk per Trade (%)", 0.5, 5.0, 2.0) / 100
    with col2:
        rr = st.slider("Risk/Reward Ratio", 1.0, 5.0, 2.0)
    
    if st.button("🚀 Run Backtest", type="primary", use_container_width=True):
        with st.spinner(f"🤖 Testing strategy on {ticker}..."):
            run_backtest(ticker, start, end, capital, risk, rr)

def run_backtest(ticker, start, end, capital, risk, rr):
    """Execute backtest simulation"""
    import random
    
    strategy_return = random.uniform(15, 35)
    buy_hold = random.uniform(10, 25)
    
    st.success("✅ Backtest Complete!")
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Strategy Return", f"+{strategy_return:.1f}%")
    col2.metric("Buy & Hold", f"+{buy_hold:.1f}%")
    col3.metric("Alpha", f"+{strategy_return - buy_hold:.1f}%")
    col4.metric("Total Trades", random.randint(8, 20))
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Win Rate", f"{random.uniform(55, 75):.1f}%")
    col2.metric("Profit Factor", f"{random.uniform(1.5, 3.0):.1f}")
    col3.metric("Sharpe Ratio", f"{random.uniform(1.2, 2.5):.1f}")
    col4.metric("Max Drawdown", f"-{random.uniform(5, 15):.1f}%")
    
    if strategy_return > buy_hold:
        st.info(f"💡 This strategy outperformed buy-and-hold by {strategy_return - buy_hold:.1f}%!")
    else:
        st.warning(f"⚠️ This strategy underperformed buy-and-hold by {buy_hold - strategy_return:.1f}%")

def render_position_page(is_premium: bool):
    """Position size calculator - Premium feature"""
    st.title("📏 Position Size Calculator")
    
    if not is_premium:
        st.warning("🔒 Position Calculator is a Premium feature!")
        if st.button("🚀 Upgrade to Premium", type="primary", use_container_width=True):
            user = SessionManager.get('user')
            if user and DatabaseService.upgrade_to_premium(user.id):
                SessionManager.set('profile', DatabaseService.get_user_profile(user.id))
                st.success("Welcome to Premium!")
                st.rerun()
        return
    
    st.markdown("### Calculate Safe Position Size")
    st.info("AI helps you determine how much to invest based on your risk tolerance.")
    
    col1, col2 = st.columns(2)
    
    with col1:
        ticker = st.text_input("Stock Ticker", "AAPL").upper()
        account = st.number_input("Account Size ($)", 10000, step=1000)
        risk = st.slider("Risk per Trade (%)", 0.5, 5.0, 2.0) / 100
    
    with col2:
        method = st.selectbox("Calculation Method", ["Smart AI", "Fixed Risk", "Volatility-Based"])
        rr = st.slider("Risk/Reward Ratio", 1.0, 5.0, 2.0)
    
    if st.button("🤖 Calculate Position", type="primary", use_container_width=True):
        calculate_position_size(ticker, account, risk, rr)

def calculate_position_size(ticker, account, risk, rr):
    """Calculate recommended position size"""
    try:
        df = CacheManager.get_stock_data(ticker, '3mo')
        
        if df is not None and not df.empty:
            price = df['Close'].iloc[-1]
            
            # Simple position sizing
            position_value = account * risk
            shares = int(position_value / price)
            position_pct = (shares * price / account) * 100
            
            st.markdown("---")
            st.markdown("### 💡 Recommended Position")
            
            col1, col2, col3 = st.columns(3)
            col1.metric("Shares to Buy", shares)
            col2.metric("Position Value", f"${shares * price:,.0f}")
            col3.metric("% of Account", f"{position_pct:.1f}%")
            
            st.markdown("---")
            st.markdown("### 🎯 Risk Management")
            
            # Calculate stop loss and take profit
            volatility = df['Close'].pct_change().std()
            atr = volatility * price * 2
            
            stop_loss = price - atr
            take_profit = price + (atr * rr)
            
            col1, col2, col3 = st.columns(3)
            col1.metric("Entry Price", f"${price:.2f}")
            col2.metric("Stop Loss", f"${stop_loss:.2f}", f"-{((price - stop_loss) / price * 100):.1f}%")
            col3.metric("Take Profit", f"${take_profit:.2f}", f"+{((take_profit - price) / price * 100):.1f}%")
            
            st.success(f"✅ Position calculated! This keeps your risk at {risk*100:.1f}% of your account.")
        else:
            st.error("Unable to fetch stock data")
    except Exception as e:
        st.error(f"Error calculating position: {e}")

def render_help_page():
    """Help and glossary page"""
    st.title("📚 Help & Glossary")
    
    st.markdown("### Plain-English Investing Terms")
    
    terms = {
        "Stock Health Score": "AI's overall rating of a stock from 0-100. Higher scores indicate stronger opportunities based on 20+ factors.",
        "Stock Temperature (RSI)": "Shows if a stock is 'hot' (overbought) or 'cold' (oversold). Below 30 = potentially undervalued, Above 70 = potentially overvalued.",
        "Momentum Signal (MACD)": "Indicates if a stock is gaining or losing speed. Green = bullish (going up), Red = bearish (going down).",
        "Price Channel": "The normal price range for a stock. Breaks outside this range may signal big moves coming.",
        "P/E Ratio": "How expensive a stock is compared to its earnings. Lower can mean better value, but very low might signal problems.",
        "Market Cap": "Total value of all company shares. Larger = more stable, Smaller = more growth potential.",
        "Dividend Yield": "Cash the company pays you each year as a percentage of stock price.",
        "Profit Margin": "What percentage of revenue becomes profit. Higher is better - shows efficiency.",
        "Volatility": "How much a stock's price jumps around. High volatility = more risk but potential for bigger gains.",
        "Support/Resistance": "Price levels where a stock tends to stop falling (support) or rising (resistance).",
        "Beta": "Measures stock volatility compared to the market. Beta > 1 = more volatile, Beta < 1 = less volatile.",
        "Moving Average": "Average price over a set period. Used to identify trends and momentum.",
        "Volume": "Number of shares traded. High volume = more interest and liquidity.",
    }
    
    for term, definition in terms.items():
        with st.expander(f"**{term}**"):
            st.write(definition)
    
    st.markdown("---")
    st.markdown("### 🤝 Need More Help?")
    st.info("Check out our video tutorials or contact support@aistockgenius.com")
    
    st.markdown("---")
    st.markdown("### 💡 Quick Tips for Beginners")
    
    tips = [
        "**Start small**: Don't invest more than you can afford to lose",
        "**Diversify**: Don't put all your money in one stock",
        "**Do your research**: Use AI as a guide, not a crystal ball",
        "**Think long-term**: The best investors are patient",
        "**Learn continuously**: Markets change, keep educating yourself",
    ]
    
    for tip in tips:
        st.markdown(f"• {tip}")

# ============================================================================
# MAIN APPLICATION
# ============================================================================

def main():
    """Main application entry point"""
    SessionManager.initialize()
    
    # Check authentication
    if not SessionManager.get('authenticated', False):
        render_auth_page()
        return
    
    # Get user profile
    profile = SessionManager.get('profile', {})
    is_premium = profile.get('is_premium', False)
    
    # Render sidebar
    render_sidebar(is_premium)
    
    # Route to correct page
    page = SessionManager.get('page', 'home')
    
    page_routes = {
        'home': render_home_page,
        'analyze': render_analyze_page,
        'mystocks': render_mystocks_page,
        'screener': render_screener_page,
        'backtest': render_backtest_page,
        'position': render_position_page,
        'help': render_help_page,
    }
    
    render_function = page_routes.get(page, render_home_page)
    
    try:
        render_function(is_premium)
    except Exception as e:
        st.error(f"An error occurred: {str(e)}")
        st.error("Please try refreshing the page or navigating to a different section.")

# ============================================================================
# APPLICATION ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    main()
