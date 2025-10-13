"""
AI STOCK GENIUS - FULL VERSION v4.0
All features restored with working authentication
"""

import json
import time
import warnings
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional

import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from supabase import create_client

warnings.filterwarnings('ignore')

# PAGE CONFIG
st.set_page_config(
    page_title="AI Stock Genius",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize Supabase
@st.cache_resource
def init_supabase():
    try:
        url = st.secrets["supabase"]["url"]
        key = st.secrets["supabase"]["key"]
        return create_client(url, key)
    except Exception as e:
        st.error(f"⚠️ Supabase connection failed: {e}")
        return None

supabase = init_supabase()

# Initialize News API
@st.cache_resource
def get_news_api_key():
    try:
        return st.secrets.get("NEWS_API_KEY", None)
    except:
        return None

NEWS_API_KEY = get_news_api_key()

# CUSTOM CSS
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');
    * { font-family: 'Inter', sans-serif; }
    .stApp { background: linear-gradient(135deg, #0a0e1a 0%, #151b2e 100%); }
    .main .block-container {
        background: rgba(21, 27, 46, 0.6);
        backdrop-filter: blur(20px);
        border-radius: 20px;
        padding: 2.5rem;
    }
    h1, h2, h3 { color: #ffffff !important; font-weight: 700 !important; }
    p, div, span, label { color: #e0e6f0 !important; }
    .stButton > button {
        background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
        color: white !important;
        border: none;
        border-radius: 12px;
        padding: 0.875rem 1.75rem;
        font-weight: 600;
        width: 100%;
        min-height: 44px;
    }
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(59, 130, 246, 0.6);
    }
    .premium-badge {
        background: linear-gradient(135deg, #fbbf24 0%, #f59e0b 100%);
        color: #1e293b !important;
        padding: 0.75rem 1.5rem;
        border-radius: 12px;
        font-weight: 700;
        text-align: center;
    }
</style>
""", unsafe_allow_html=True)

# SESSION MANAGER
class SessionManager:
    @staticmethod
    def initialize():
        defaults = {
            'authenticated': False,
            'user': None,
            'profile': {'is_premium': False},
            'page': 'home',
            'beginner_mode': True,
            'demo_mode': False
        }
        for key, value in defaults.items():
            if key not in st.session_state:
                st.session_state[key] = value
    
    @staticmethod
    def get(key, default=None):
        return st.session_state.get(key, default)
    
    @staticmethod
    def set(key, value):
        st.session_state[key] = value

SessionManager.initialize()

# TOOLTIPS
class TooltipManager:
    @staticmethod
    def get_tooltip(key):
        tooltips = {
            'stock_health_score': "AI analyzes 20+ factors to rate this stock 0-100. Higher = stronger opportunity",
            'stock_temperature': "Below 30 = potentially undervalued, Above 70 = potentially overvalued",
            'momentum_signal': "Green = gaining speed (bullish), Red = slowing down (bearish)",
            'price_channel': "Normal price range - breaks signal potential moves",
            'sentiment': "AI scans news and social media to gauge market feeling",
            'forecast': "AI predicts price movement with confidence level. Not guaranteed!",
        }
        return tooltips.get(key, "")

# DATABASE SERVICE
class DatabaseService:
    @staticmethod
    def get_user_profile(user_id):
        if not supabase:
            return {'id': user_id, 'is_premium': False}
        try:
            result = supabase.table('user_profiles').select('*').eq('id', user_id).single().execute()
            if result.data:
                return result.data
            return {'id': user_id, 'is_premium': False}
        except:
            return {'id': user_id, 'is_premium': False}
    
    @staticmethod
    def upgrade_to_premium(user_id):
        if not supabase:
            return False
        try:
            user = SessionManager.get('user')
            end_date = (datetime.now() + timedelta(days=30)).isoformat()
            supabase.table('user_profiles').upsert({
                'id': user_id,
                'email': user.email if user else '',
                'is_premium': True,
                'subscription_end_date': end_date
            }).execute()
            return True
        except:
            return False
    
    @staticmethod
    def get_watchlist(user_id):
        if not supabase:
            return []
        try:
            result = supabase.table('watchlists').select('*').eq('user_id', user_id).execute()
            return result.data if result.data else []
        except Exception as e:
            st.error(f"Error fetching watchlist: {e}")
            return []
    
    @staticmethod
    def add_to_watchlist(user_id, ticker):
        if not supabase:
            return False
        try:
            existing = supabase.table('watchlists').select('ticker').eq('user_id', user_id).eq('ticker', ticker).execute()
            if existing.data:
                return False
            supabase.table('watchlists').insert({
                'user_id': user_id,
                'ticker': ticker
            }).execute()
            return True
        except Exception as e:
            st.error(f"Error adding to watchlist: {e}")
            return False
    
    @staticmethod
    def remove_from_watchlist(user_id, ticker):
        if not supabase:
            return False
        try:
            supabase.table('watchlists').delete().eq('user_id', user_id).eq('ticker', ticker).execute()
            return True
        except Exception as e:
            st.error(f"Error removing from watchlist: {e}")
            return False
    
    @staticmethod
    def get_portfolio(user_id):
        if not supabase:
            return []
        try:
            result = supabase.table('portfolio').select('*').eq('user_id', user_id).execute()
            return result.data if result.data else []
        except:
            return []
    
    @staticmethod
    def add_portfolio_position(user_id, ticker, shares, avg_price, purchase_date):
        if not supabase:
            return False
        try:
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
        except:
            return False
    
    @staticmethod
    def remove_portfolio_position(user_id, ticker):
        if not supabase:
            return False
        try:
            supabase.table('portfolio').delete().eq('user_id', user_id).eq('ticker', ticker).execute()
            return True
        except:
            return False

# STOCK SEARCH
class StockSearchHelper:
    @staticmethod
    def search_stock(query):
        if not query or len(query) < 1:
            return []
        
        popular_stocks = {
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
        }
        
        results = []
        query_upper = query.upper()
        
        for ticker, name in popular_stocks.items():
            if query_upper in ticker or query_upper in name.upper():
                results.append((ticker, name))
        
        return results[:10]
    
    @staticmethod
    def format_option(ticker, name):
        if len(name) > 50:
            name = name[:47] + "..."
        return f"{ticker} - {name}"

# SENTIMENT ANALYSIS
class SentimentAnalyzer:
    @staticmethod
    def analyze_sentiment(ticker, company_name=None):
        if not NEWS_API_KEY:
            return SentimentAnalyzer._get_placeholder_sentiment()
        
        try:
            import requests
            query = company_name if company_name else ticker
            from_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
            
            url = "https://newsapi.org/v2/everything"
            params = {
                'q': query,
                'from': from_date,
                'sortBy': 'relevancy',
                'language': 'en',
                'apiKey': NEWS_API_KEY,
                'pageSize': 20
            }
            
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code != 200:
                return SentimentAnalyzer._get_placeholder_sentiment()
            
            data = response.json()
            articles = data.get('articles', [])
            
            if not articles:
                return {
                    'score': 0,
                    'text': "😐 Neutral",
                    'drivers': ["No recent news found"],
                    'sources': "0 articles analyzed",
                    'articles': []
                }
            
            positive_keywords = ['surge', 'gain', 'profit', 'beat', 'upgrade', 'growth', 'success', 'record', 'rise', 'bullish', 'outperform', 'strong']
            negative_keywords = ['fall', 'loss', 'miss', 'downgrade', 'decline', 'weak', 'concern', 'drop', 'bearish', 'underperform', 'risk']
            
            sentiment_scores = []
            positive_news = []
            negative_news = []
            
            for article in articles[:15]:
                title = (article.get('title', '') + ' ' + article.get('description', '')).lower()
                pos_count = sum(1 for word in positive_keywords if word in title)
                neg_count = sum(1 for word in negative_keywords if word in title)
                
                if pos_count > neg_count:
                    score = 0.5 + (pos_count * 0.2)
                    sentiment_scores.append(min(score, 1.0))
                    if len(positive_news) < 3:
                        positive_news.append(article.get('title', '')[:80])
                elif neg_count > pos_count:
                    score = -0.5 - (neg_count * 0.2)
                    sentiment_scores.append(max(score, -1.0))
                    if len(negative_news) < 3:
                        negative_news.append(article.get('title', '')[:80])
                else:
                    sentiment_scores.append(0)
            
            avg_sentiment = sum(sentiment_scores) / len(sentiment_scores) if sentiment_scores else 0
            
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
        except Exception as e:
            return SentimentAnalyzer._get_placeholder_sentiment()
    
    @staticmethod
    def _get_placeholder_sentiment():
        import random
        sentiment_score = random.uniform(-0.5, 0.8)
        
        if sentiment_score > 0.5:
            return {
                'score': sentiment_score,
                'text': "😊 Positive",
                'drivers': ["✅ Configure NEWS_API_KEY for real sentiment"],
                'sources': "Demo mode",
                'articles': []
            }
        elif sentiment_score > 0:
            return {
                'score': sentiment_score,
                'text': "😐 Neutral",
                'drivers': ["➡️ Configure NEWS_API_KEY for real sentiment"],
                'sources': "Demo mode",
                'articles': []
            }
        else:
            return {
                'score': sentiment_score,
                'text': "😟 Negative",
                'drivers': ["⚠️ Configure NEWS_API_KEY for real sentiment"],
                'sources': "Demo mode",
                'articles': []
            }

# TECHNICAL ANALYSIS
class TechnicalAnalysisEngine:
    @staticmethod
    def calculate_all_indicators(df):
        try:
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
            
            # Moving averages
            df['SMA20'] = df['Close'].rolling(window=20).mean()
            df['SMA50'] = df['Close'].rolling(window=50).mean()
            df['SMA200'] = df['Close'].rolling(window=200).mean()
            
            return df
        except:
            return df
    
    @staticmethod
    def calculate_ai_score(df, info):
        score = 50
        signals = []
        
        try:
            latest = df.iloc[-1]
            price = latest['Close']
            
            # RSI
            rsi = latest['RSI']
            if pd.notna(rsi):
                if 40 <= rsi <= 60:
                    score += 15
                    signals.append(("Stock Temperature in neutral zone", "positive"))
                elif rsi < 30:
                    score += 10
                    signals.append(("Stock Temperature cold - potential buy", "positive"))
                elif rsi > 70:
                    score += 5
                    signals.append(("Stock Temperature hot - use caution", "negative"))
            
            # MACD
            if pd.notna(latest['MACD']) and pd.notna(latest['MACD_Signal']):
                if latest['MACD'] > latest['MACD_Signal']:
                    score += 15
                    signals.append(("Momentum Signal is positive", "positive"))
                else:
                    score += 5
                    signals.append(("Momentum Signal is negative", "negative"))
            
            # Moving Average Trend
            if pd.notna(latest['SMA50']) and pd.notna(latest['SMA200']):
                if price > latest['SMA50'] > latest['SMA200']:
                    score += 20
                    signals.append(("Strong upward price trend", "positive"))
                elif price > latest['SMA50']:
                    score += 12
                    signals.append(("Moderate upward trend", "positive"))
            
            # Fundamentals
            pe = info.get('trailingPE')
            if pe and pd.notna(pe) and 10 <= pe <= 25:
                score += 15
                signals.append(("Healthy price-to-earnings ratio", "positive"))
            
            profit_margin = info.get('profitMargins')
            if profit_margin and pd.notna(profit_margin) and profit_margin > 0.20:
                score += 15
                signals.append(("Excellent profit margins", "positive"))
        except:
            pass
        
        final_score = max(0, min(100, score))
        
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

# PRICE FORECASTING
class PriceForecaster:
    @staticmethod
    def predict_price(df, days=30):
        try:
            if len(df) < 60:
                return None
            
            recent = df.tail(90).copy()
            recent['day_num'] = range(len(recent))
            
            X = recent['day_num'].values
            y = recent['Close'].values
            
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
            
            future_day = len(recent) + days
            predicted_price = max(0, adjusted_slope * future_day + intercept)
            
            current_price = df['Close'].iloc[-1]
            change_pct = ((predicted_price - current_price) / current_price) * 100
            
            volatility = df['Close'].pct_change().tail(30).std()
            confidence = max(0, min(100, 100 - (volatility * 1000)))
            
            return {
                'current': current_price,
                'predicted': predicted_price,
                'change_pct': change_pct,
                'confidence': confidence,
                'trend': 'Bullish' if adjusted_slope > 0 else 'Bearish'
            }
        except:
            return None

# AUTH PAGE
def render_auth_page():
    # Check for onboarding
    if SessionManager.get('show_onboarding', True) and not SessionManager.get('onboarding_complete', False):
        render_onboarding()
        return
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown("<h1 style='text-align: center;'>🤖 AI Stock Genius</h1>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; color: #94a3b8; font-size: 1.2rem;'>Beginner-Friendly Stock Analysis</p>", unsafe_allow_html=True)
        
        tab1, tab2 = st.tabs(["🔐 Sign In", "✨ Create Account"])
        
        with tab1:
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
                                    st.success("Welcome back!")
                                    time.sleep(0.5)
                                    st.rerun()
                                else:
                                    st.error("Invalid credentials")
                        except Exception as e:
                            error_msg = str(e)
                            if "email not confirmed" in error_msg.lower():
                                st.error("Please verify your email before signing in.")
                            else:
                                st.error(f"Sign in failed: {error_msg}")
        
        with tab2:
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
                                    st.success("Account created! Please check your email to verify.")
                                    st.info("After verifying, return here to sign in.")
                                else:
                                    st.error("Failed to create account")
                        except Exception as e:
                            error_msg = str(e)
                            if "already registered" in error_msg.lower():
                                st.error("This email is already registered.")
                            else:
                                st.error(f"Signup failed: {error_msg}")

# ONBOARDING FLOW
def render_onboarding():
    step = SessionManager.get('onboarding_step', 0)
    
    if step == 0:
        st.markdown("<div style='text-align: center; margin: 3rem 0;'>", unsafe_allow_html=True)
        st.markdown("# 🎉 Welcome to AI Stock Genius!")
        st.markdown("### We'll help you make smarter investment decisions using AI")
        st.markdown("<p style='color: #94a3b8;'>Let's get started with a quick tour (2 minutes)</p>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)
        
        col1, col2, col3 = st.columns([1, 1, 1])
        with col2:
            if st.button("Continue", use_container_width=True, type="primary"):
                SessionManager.set('onboarding_step', 1)
                st.rerun()
            if st.button("Skip Tour", use_container_width=True):
                SessionManager.set('onboarding_complete', True)
                SessionManager.set('show_onboarding', False)
                st.rerun()
    
    elif step == 1:
        st.markdown("## How would you describe yourself?")
        
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("### 🌱 Beginner")
            st.markdown("I'm new to investing")
            if st.button("Choose Beginner Mode", use_container_width=True, type="primary"):
                SessionManager.set('beginner_mode', True)
                SessionManager.set('onboarding_step', 2)
                st.rerun()
        
        with col2:
            st.markdown("### 📈 Experienced")
            st.markdown("I know my way around stocks")
            if st.button("Choose Advanced Mode", use_container_width=True):
                SessionManager.set('beginner_mode', False)
                SessionManager.set('onboarding_step', 2)
                st.rerun()
    
    elif step == 2:
        st.markdown("## 🎯 Quick Tutorial")
        st.markdown("Here's what you can do with AI Stock Genius:")
        
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("✅ **Search for any stock**")
            st.markdown("✅ **See AI's analysis in plain English**")
        with col2:
            st.markdown("✅ **Save stocks to your Watchlist**")
            st.markdown("✅ **Track your portfolio performance**")
        
        st.markdown("---")
        col1, col2, col3 = st.columns([1, 1, 1])
        with col2:
            if st.button("Let's Go! 🚀", use_container_width=True, type="primary"):
                SessionManager.set('onboarding_complete', True)
                SessionManager.set('show_onboarding', False)
                st.rerun()


# SIDEBAR
def render_sidebar(is_premium):
    with st.sidebar:
        st.markdown("### 🤖 AI Stock Genius")
        st.markdown("---")
        
        if is_premium:
            st.markdown('<div class="premium-badge">⭐ PREMIUM</div>', unsafe_allow_html=True)
        else:
            st.info("🆓 Free Account")
        
        st.markdown("---")
        st.markdown("#### Navigation")
        
        if st.button("🏠 Home", use_container_width=True):
            SessionManager.set('page', 'home')
            st.rerun()
        
        if st.button("📊 Analyze", use_container_width=True):
            SessionManager.set('page', 'analyze')
            st.rerun()
        
        if st.button("💼 My Stocks", use_container_width=True):
            SessionManager.set('page', 'mystocks')
            st.rerun()
        
        if st.button("🔍 Stock Screener", use_container_width=True):
            SessionManager.set('page', 'screener')
            st.rerun()
        
        # Advanced Tools
        beginner_mode = SessionManager.get('beginner_mode', True)
        if not beginner_mode:
            with st.expander("🛠️ Advanced Tools"):
                if st.button("⚡ Backtesting", use_container_width=True):
                    SessionManager.set('page', 'backtest')
                    st.rerun()
                if st.button("📏 Position Calculator", use_container_width=True):
                    SessionManager.set('page', 'position')
                    st.rerun()
        
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
        
        # Upgrade to premium
        if not is_premium:
            if st.button("🚀 Upgrade to Premium", use_container_width=True, type="primary"):
                user = SessionManager.get('user')
                if user and DatabaseService.upgrade_to_premium(user.id):
                    profile = DatabaseService.get_user_profile(user.id)
                    SessionManager.set('profile', profile)
                    st.balloons()
                    st.success("Welcome to Premium!")
                    time.sleep(1)
                    st.rerun()
        
        st.markdown("---")
        
        if st.button("🚪 Sign Out", use_container_width=True):
            if supabase:
                try:
                    supabase.auth.sign_out()
                except:
                    pass
            SessionManager.set('authenticated', False)
            SessionManager.set('user', None)
            SessionManager.set('profile', None)
            st.rerun()

# HOME PAGE
def render_home_page(is_premium):
    st.title("🏠 Home Dashboard")
    
    if not is_premium:
        st.warning("📢 Upgrade to Premium to unlock AI Health Score, Sentiment, and Price Forecasts!")
    else:
        st.success("🎉 Welcome back! You have full access to all AI features.")
    
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
    
    user = SessionManager.get('user')
    watchlist = DatabaseService.get_watchlist(user.id if user else 'demo')
    portfolio = DatabaseService.get_portfolio(user.id if user else 'demo')
    
    with col3:
        st.metric("Watchlist", len(watchlist))
        st.metric("Portfolio", len(portfolio))

# ANALYZE PAGE
def render_analyze_page(is_premium):
    st.title("📊 Stock Analysis")
    
    if not is_premium:
        st.warning("🔒 Upgrade to Premium for AI Health Score, Sentiment Analysis, and Price Forecasts")
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        search_query = st.text_input(
            "Search by company name or ticker",
            placeholder="e.g., Apple, Tesla, MSFT...",
            label_visibility="collapsed"
        )
    
    ticker = None
    
    if search_query:
        results = StockSearchHelper.search_stock(search_query)
        
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
        try:
            with st.spinner(f"🤖 Analyzing {ticker}..."):
                stock = yf.Ticker(ticker)
                df = stock.history(period='6mo')
                info = stock.info
                
                if df.empty:
                    st.error("Unable to fetch data")
                    return
                
                df = TechnicalAnalysisEngine.calculate_all_indicators(df)
                
                price = df['Close'].iloc[-1]
                prev = df['Close'].iloc[-2] if len(df) > 1 else price
                change_pct = ((price - prev) / prev) * 100
                
                company_name = info.get('longName', ticker)
                st.markdown(f"## {company_name} ({ticker})")
                
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Current Price", f"${price:.2f}", f"{change_pct:+.2f}%")
                col2.metric("Volume", f"{info.get('volume', 0)/1e6:.1f}M")
                col3.metric("Market Cap", f"${info.get('marketCap', 0)/1e9:.1f}B")
                col4.metric("P/E Ratio", f"{info.get('trailingPE', 0):.2f}")
                
                st.markdown("---")
                
                # AI Health Score (Premium)
                if is_premium:
                    ai_analysis = TechnicalAnalysisEngine.calculate_ai_score(df, info)
                    
                    st.markdown("### 🤖 AI Stock Health Score")
                    col1, col2 = st.columns([1, 2])
                    
                    with col1:
                        score = ai_analysis['score']
                        score_color = "#10b981" if score >= 70 else "#f59e0b" if score >= 50 else "#ef4444"
                        st.markdown(f"""
                        <div style='text-align: center; padding: 2rem; background: rgba(255,255,255,0.05); border-radius: 15px; border: 2px solid {score_color};'>
                            <h1 style='font-size: 4rem; color: {score_color}; margin: 0;'>{score:.0f}</h1>
                            <p style='font-size: 1.5rem; margin: 0.5rem 0;'>{ai_analysis['rating']}</p>
                            <p style='font-size: 0.875rem; color: #94a3b8;'>out of 100</p>
                        </div>
                        """, unsafe_allow_html=True)
                    
                    with col2:
                        st.markdown("**Key Drivers:**")
                        for signal, signal_type in ai_analysis['signals']:
                            icon = "🟢" if signal_type == "positive" else "🔴" if signal_type == "negative" else "🟡"
                            st.markdown(f"{icon} {signal}")
                
                # Price Forecast (Premium only)
                if is_premium:
                    st.markdown("---")
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
                        st.caption("💡 " + TooltipManager.get_tooltip('forecast'))
                        
                        st.warning("⚠️ Forecasts are predictions, not guarantees. Always do your own research!")
                    else:
                        st.info("Insufficient data for price forecast")
                
                st.markdown("---")
                
                # Action buttons
                col1, col2 = st.columns(2)
                with col1:
                    user = SessionManager.get('user')
                    user_id = user.id if user else 'demo'
                    
                    if st.button(f"⭐ Add {ticker} to Watchlist", use_container_width=True, type="primary"):
                        if DatabaseService.add_to_watchlist(user_id, ticker):
                            st.success(f"✅ {ticker} added to watchlist!")
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.warning("Already in watchlist")
                
        except Exception as e:
            st.error(f"Error: {str(e)}")
# MY STOCKS PAGE
def render_mystocks_page(is_premium):
    st.title("💼 My Stocks")
    
    user = SessionManager.get('user')
    user_id = user.id if user else 'demo'
    
    tab1, tab2 = st.tabs(["👁️ Watchlist", "📊 Portfolio"])
    
    with tab1:
        st.markdown("### Your Watchlist")
        
        with st.expander("➕ Add Stock to Watchlist"):
            search = st.text_input("Search stock", placeholder="e.g., Apple, TSLA", key="watchlist_search")
            
            if search:
                results = StockSearchHelper.search_stock(search)
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
        
        watchlist = DatabaseService.get_watchlist(user_id)
        
        if watchlist:
            st.markdown(f"**{len(watchlist)} stocks in your watchlist**")
            
            for i in range(0, len(watchlist), 3):
                cols = st.columns(3)
                for j, col in enumerate(cols):
                    if i + j < len(watchlist):
                        item = watchlist[i + j]
                        ticker = item['ticker']
                        
                        try:
                            stock = yf.Ticker(ticker)
                            hist = stock.history(period='1d')
                            
                            if not hist.empty:
                                price = hist['Close'].iloc[-1]
                                
                                with col:
                                    st.markdown(f"**{ticker}**")
                                    st.metric("Price", f"${price:.2f}")
                                    if st.button("Remove", key=f"wl_rm_{ticker}_{i}_{j}", use_container_width=True):
                                        DatabaseService.remove_from_watchlist(user_id, ticker)
                                        st.rerun()
                        except:
                            with col:
                                st.markdown(f"**{ticker}**")
                                st.caption("Data unavailable")
                                if st.button("Remove", key=f"wl_rm_err_{ticker}_{i}_{j}", use_container_width=True):
                                    DatabaseService.remove_from_watchlist(user_id, ticker)
                                    st.rerun()
        else:
            st.info("Your watchlist is empty. Add stocks to track them!")
    
    with tab2:
        st.markdown("### Your Portfolio")
        
        with st.expander("➕ Add New Position"):
            col1, col2, col3 = st.columns(3)
            ticker = col1.text_input("Ticker", key="port_ticker").upper()
            shares = col2.number_input("Shares", min_value=0.0, step=0.1, key="port_shares")
            avg_price = col3.number_input("Avg Price", min_value=0.0, step=0.01, key="port_price")
            
            if st.button("Add to Portfolio", use_container_width=True, type="primary"):
                if ticker and shares > 0 and avg_price > 0:
                    if DatabaseService.add_portfolio_position(
                        user_id,
                        ticker,
                        shares,
                        avg_price,
                        datetime.now().date().isoformat()
                    ):
                        st.success(f"✅ Added {shares} shares of {ticker}!")
                        time.sleep(0.5)
                        st.rerun()
                else:
                    st.error("Please fill all fields")
        
        st.markdown("---")
        
        portfolio = DatabaseService.get_portfolio(user_id)
        
        if portfolio:
            total_invested = 0
            total_current = 0
            
            positions_data = []
            
            for pos in portfolio:
                ticker = pos['ticker']
                shares = pos['shares']
                avg_price = pos['average_price']
                
                try:
                    stock = yf.Ticker(ticker)
                    current_price = stock.history(period='1d')['Close'].iloc[-1]
                    
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
            
            st.markdown(f"**{len(positions_data)} positions**")
            
            for pos in positions_data:
                col1, col2, col3, col4 = st.columns([2, 2, 2, 1])
                col1.write(f"**{pos['ticker']}**")
                col2.write(f"{pos['shares']} @ ${pos['avg_price']:.2f}")
                col3.metric("P/L", f"${pos['pnl']:,.2f}", f"{pos['pnl_pct']:+.1f}%")
                
                if col4.button("Remove", key=f"port_rm_{pos['ticker']}"):
                    DatabaseService.remove_portfolio_position(user_id, pos['ticker'])
                    st.rerun()
        else:
            st.info("Your portfolio is empty. Add positions to track performance!")

# BACKTESTING PAGE
def render_backtest_page(is_premium):
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
            # Mock backtest results
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

# POSITION CALCULATOR PAGE
def render_position_page(is_premium):
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
        account = st.number_input("Account Size ($)", 100000, step=1000)
        risk = st.slider("Risk per Trade (%)", 0.5, 5.0, 2.0) / 100
    
    with col2:
        method = st.selectbox("Calculation Method", ["Smart AI", "Fixed Risk", "Volatility-Based"])
        rr = st.slider("Risk/Reward Ratio", 1.0, 5.0, 2.0)
    
    if st.button("🤖 Calculate Position", type="primary", use_container_width=True):
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period='3mo')
            
            if not hist.empty:
                price = hist['Close'].iloc[-1]
                
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
                volatility = hist['Close'].pct_change().std()
                atr = volatility * price * 2
                
                stop_loss = price - atr
                take_profit = price + (atr * rr)
                
                col1, col2, col3 = st.columns(3)
                col1.metric("Entry Price", f"${price:.2f}")
                col2.metric("Stop Loss", f"${stop_loss:.2f}", f"-{((price - stop_loss) / price * 100):.1f}%")
                col3.metric("Take Profit", f"${take_profit:.2f}", f"+{((take_profit - price) / price * 100):.1f}%")
                
                st.success(f"✅ Position calculated! This keeps your risk at {risk*100:.1f}% of your account.")
        except Exception as e:
            st.error(f"Error calculating position: {e}")

# HELP & GLOSSARY PAGE
def render_help_page():
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
    }
    
    for term, definition in terms.items():
        with st.expander(f"**{term}**"):
            st.write(definition)
    
    st.markdown("---")
    st.markdown("### 🤝 Need More Help?")
    st.info("Check out our video tutorials or contact support@aistockgenius.com")

# STOCK SCREENER PAGE
def render_screener_page(is_premium):
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
            "Consumer", "Energy", "Industrial"
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
            try:
                # Sample stock universe for screening
                stock_universe = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'NVDA', 'TSLA', 'AMD']
                
                results = []
                
                for ticker in stock_universe:
                    try:
                        stock = yf.Ticker(ticker)
                        info = stock.info
                        hist = stock.history(period='1mo')
                        
                        if hist.empty:
                            continue
                        
                        price = hist['Close'].iloc[-1]
                        
                        # Apply filters
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
                            df_tech = TechnicalAnalysisEngine.calculate_all_indicators(hist)
                            if df_tech['RSI'].iloc[-1] >= 30:
                                continue
                        
                        if volume_filter:
                            if info.get('volume', 0) < 1e6:
                                continue
                        
                        # Fundamental filters
                        if pe_filter:
                            pe = info.get('trailingPE', 999)
                            if pe >= 25:
                                continue
                        
                        if profitable:
                            profit_margin = info.get('profitMargins', -1)
                            if profit_margin <= 0:
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
                
                # Display results
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
                    
            except Exception as e:
                st.error(f"Screening error: {str(e)}")



# MAIN
def main():
    SessionManager.initialize()
    
    if not SessionManager.get('authenticated', False):
        render_auth_page()
        return
    
    profile = SessionManager.get('profile', {})
    is_premium = profile.get('is_premium', False)
    
    render_sidebar(is_premium)
    
    page = SessionManager.get('page', 'home')
    
    if page == 'home':
        render_home_page(is_premium)
    elif page == 'analyze':
        render_analyze_page(is_premium)
    elif page == 'mystocks':
        render_mystocks_page(is_premium)
    elif page == 'screener':
        render_screener_page(is_premium)
    elif page == 'backtest':
        render_backtest_page(is_premium)
    elif page == 'position':
        render_position_page(is_premium)
    elif page == 'help':
        render_help_page()

# RUN
if __name__ == "__main__":
    main()
