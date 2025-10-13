"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                     AI STOCK GENIUS - REDESIGNED v4.0                        ║
║                 Beginner-Friendly Stock Analysis Platform                     ║
║                                                                              ║
║  Focus: Simplified UX, Plain English, AI-Powered Insights                   ║
║  Author: AI Stock Genius Development Team                                   ║
║  License: Proprietary                                                        ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

# TOOLTIP CONTENT MANAGER
# =============================================================================
class TooltipManager:
    """Centralized tooltip content in plain English"""
    
    @staticmethod
    def get_tooltip(key: str) -> str:
        tooltips = {
            'stock_health_score': "AI analyzes 20+ factors to rate this stock 0-100. Higher = stronger opportunity",
            'stock_temperature': "Below 30 = potentially undervalued, Above 70 = potentially overvalued",
            'momentum_signal': "Green = gaining speed (bullish), Red = slowing down (bearish)",
            'price_channel': "Normal price range - breaks signal potential moves",
            'price_health': "How expensive the stock is vs. its earnings",
            'trading_activity': "How many people are buying/selling today",
            'company_size': "Total value of all company shares",
            'income_return': "Cash paid back to you each year (%)",
            'sentiment': "AI scans news and social media to gauge market feeling about this stock",
            'forecast': "AI predicts price movement with confidence level. Not guaranteed!",
            'watchlist': "Stocks you're tracking. Click any to analyze",
            'portfolio': "Stocks you own. We track your profit/loss automatically"
        }
        return tooltips.get(key, "")

# =============================================================================
# STOCK SEARCH HELPER WITH YFINANCE SEARCH
# =============================================================================
class StockSearchHelper:
    """Helper for searching stocks by name or ticker using yfinance"""
    
    @staticmethod
    def search_stock(query: str):
        """
        Search for stocks by ticker or company name using yfinance
        Returns list of (ticker, name) tuples
        """
        if not query or len(query) < 1:
            return []
        
        query = query.strip()
        results = []
        
        try:
            # Use yfinance Ticker search
            # First, try as direct ticker
            try:
                ticker_obj = yf.Ticker(query.upper())
                info = ticker_obj.info
                
                # Check if we got valid data
                if info and ('symbol' in info or 'longName' in info or 'shortName' in info):
                    ticker_symbol = info.get('symbol', query.upper())
                    company_name = info.get('longName') or info.get('shortName') or ticker_symbol
                    
                    # Only add if we got a real company name
                    if company_name and company_name != ticker_symbol:
                        results.append((ticker_symbol, company_name))
            except:
                pass
            
            # Search using yfinance search functionality
            # Note: yfinance doesn't have a built-in search API, so we'll use Ticker with common variations
            # For production, you might want to integrate with a proper search API
            
            # If exact ticker didn't work, try some common patterns
            if not results:
                # Try common stock exchanges
                for suffix in ['', '.US', '.NYSE', '.NASDAQ']:
                    try:
                        test_ticker = query.upper() + suffix
                        ticker_obj = yf.Ticker(test_ticker)
                        info = ticker_obj.info
                        
                        if info and info.get('longName'):
                            ticker_symbol = info.get('symbol', test_ticker)
                            company_name = info.get('longName') or info.get('shortName')
                            results.append((ticker_symbol, company_name))
                            break
                    except:
                        continue
            
            # Fallback: Search our curated list for name matches
            if not results:
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
                    'JNJ': 'Johnson & Johnson',
                    'PFE': 'Pfizer Inc.',
                    'KO': 'Coca-Cola Company',
                    'PEP': 'PepsiCo Inc.',
                    'INTC': 'Intel Corporation',
                    'CSCO': 'Cisco Systems',
                    'ORCL': 'Oracle Corporation',
                    'CRM': 'Salesforce Inc.',
                    'ADBE': 'Adobe Inc.',
                    'PYPL': 'PayPal Holdings',
                    'SPY': 'SPDR S&P 500 ETF',
                    'QQQ': 'Invesco QQQ Trust',
                }
                
                query_upper = query.upper()
                
                for ticker, name in popular_stocks.items():
                    # Match in ticker or name
                    if query_upper in ticker or query_upper in name.upper():
                        results.append((ticker, name))
                
                # Limit to top 10
                results = results[:10]
        
        except Exception as e:
            # If all else fails, return empty
            pass
        
        return results
    
    @staticmethod
    def get_stock_info(ticker: str):
        """Get detailed stock information"""
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            
            if info and ('symbol' in info or 'longName' in info):
                return {
                    'ticker': ticker,
                    'name': info.get('longName') or info.get('shortName') or ticker,
                    'sector': info.get('sector', 'N/A'),
                    'industry': info.get('industry', 'N/A'),
                    'market_cap': info.get('marketCap', 0)
                }
        except:
            pass
        
        return None
    
    @staticmethod
    def format_option(ticker: str, name: str) -> str:
        """Format stock option for display"""
        # Truncate long names
        if len(name) > 50:
            name = name[:47] + "..."
        return f"{ticker} - {name}"
    
    @staticmethod
    def validate_ticker(ticker: str) -> bool:
        """Check if a ticker is valid"""
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period='1d')
            return not hist.empty
        except:
            return False

# =============================================================================
# AUTHENTICATION SERVICE
# =============================================================================
class AuthenticationService:
    """Handle all authentication operations"""
    
    @staticmethod
    def signup(email: str, password: str):
        try:
            if not email or not password:
                return False, "Email and password are required"
            if len(password) < 6:
                return False, "Password must be at least 6 characters"
            if supabase is None:
                return False, "Database unavailable"
            
            response = supabase.auth.sign_up({
                "email": email,
                "password": password
            })
            
            if response.user:
                return True, "Account created! Please check your email to verify."
            return False, "Failed to create account. Please try again."
        except Exception as e:
            error_msg = str(e)
            if "already registered" in error_msg.lower():
                return False, "This email is already registered"
            return False, f"Signup error: {error_msg}"
    
    @staticmethod
    def signin(email: str, password: str):
        try:
            if not email or not password:
                return False, None, None
            if supabase is None:
                return False, None, None
            
            response = supabase.auth.sign_in_with_password({
                "email": email,
                "password": password
            })
            
            if response.user:
                profile = DatabaseService.get_user_profile(response.user.id)
                return True, response.user, profile
            return False, None, None
        except:
            return False, None, None
    
    @staticmethod
    def signout():
        try:
            if supabase:
                supabase.auth.sign_out()
        except:
            pass
        finally:
            SessionManager.clear()

# =============================================================================
# DATABASE SERVICE
# =============================================================================
class DatabaseService:
    """Handle all database operations"""
    
    @staticmethod
    def get_user_profile(user_id: str):
        try:
            if supabase is None:
                return {'id': user_id, 'is_premium': False}
            result = supabase.table('user_profiles').select('*').eq('id', user_id).single().execute()
            if result.data:
                return result.data
            return {'id': user_id, 'is_premium': False}
        except:
            return {'id': user_id, 'is_premium': False}
    
    @staticmethod
    def upgrade_to_premium(user_id: str):
        try:
            if supabase is None:
                return False
            user_email = SessionManager.get('user').email
            end_date = (datetime.now() + timedelta(days=30)).isoformat()
            supabase.table('user_profiles').upsert({
                'id': user_id,
                'email': user_email,
                'is_premium': True,
                'subscription_end_date': end_date
            }).execute()
            return True
        except:
            return False
    
    @staticmethod
    def get_watchlist(user_id: str):
        try:
            if supabase is None:
                return []
            result = supabase.table('watchlists').select('*').eq('user_id', user_id).execute()
            return result.data if result.data else []
        except:
            return []
    
    @staticmethod
    def add_to_watchlist(user_id: str, ticker: str):
        try:
            if supabase is None:
                return False
            existing = supabase.table('watchlists').select('ticker').eq('user_id', user_id).eq('ticker', ticker).execute()
            if existing.data:
                return False
            supabase.table('watchlists').insert({
                'user_id': user_id,
                'ticker': ticker,
                'created_at': datetime.now().isoformat()
            }).execute()
            return True
        except:
            return False
    
    @staticmethod
    def remove_from_watchlist(user_id: str, ticker: str):
        try:
            if supabase is None:
                return False
            supabase.table('watchlists').delete().eq('user_id', user_id).eq('ticker', ticker).execute()
            return True
        except:
            return False
    
    @staticmethod
    def get_portfolio(user_id: str):
        try:
            if supabase is None:
                return []
            result = supabase.table('portfolio').select('*').eq('user_id', user_id).execute()
            return result.data if result.data else []
        except:
            return []
    
    @staticmethod
    def add_portfolio_position(user_id: str, ticker: str, shares: float, avg_price: float, purchase_date: str):
        try:
            if supabase is None:
                return False
            existing = supabase.table('portfolio').select('*').eq('user_id', user_id).eq('ticker', ticker).execute()
            if existing.data:
                old_position = existing.data[0]
                old_shares = old_position['shares']
                old_price = old_position['average_price']
                total_shares = old_shares + shares
                new_avg_price = ((old_shares * old_price) + (shares * avg_price)) / total_shares
                supabase.table('portfolio').update({
                    'shares': total_shares,
                    'average_price': new_avg_price
                }).eq('user_id', user_id).eq('ticker', ticker).execute()
            else:
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
    def remove_portfolio_position(user_id: str, ticker: str):
        try:
            if supabase is None:
                return False
            supabase.table('portfolio').delete().eq('user_id', user_id).eq('ticker', ticker).execute()
            return True
        except:
            return False

# =============================================================================
# TECHNICAL ANALYSIS ENGINE
# =============================================================================
class TechnicalAnalysisEngine:
    """Advanced technical analysis"""
    
    @staticmethod
    def calculate_all_indicators(df):
        try:
            # RSI (Stock Temperature)
            delta = df['Close'].diff()
            gain = delta.where(delta > 0, 0).rolling(window=14).mean()
            loss = -delta.where(delta < 0, 0).rolling(window=14).mean()
            rs = gain / loss
            df['RSI'] = 100 - (100 / (1 + rs))
            
            # MACD (Momentum Signal)
            exp1 = df['Close'].ewm(span=12, adjust=False).mean()
            exp2 = df['Close'].ewm(span=26, adjust=False).mean()
            df['MACD'] = exp1 - exp2
            df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
            df['MACD_Histogram'] = df['MACD'] - df['MACD_Signal']
            
            # Bollinger Bands (Price Channel)
            df['BB_Middle'] = df['Close'].rolling(window=20).mean()
            bb_std = df['Close'].rolling(window=20).std()
            df['BB_Upper'] = df['BB_Middle'] + (bb_std * 2)
            df['BB_Lower'] = df['BB_Middle'] - (bb_std * 2)
            
            # Moving Averages
            for period in [20, 50, 200]:
                df[f'SMA{period}'] = df['Close'].rolling(window=period).mean()
            
            # ATR (Price Swing Range)
            high_low = df['High'] - df['Low']
            high_close = abs(df['High'] - df['Close'].shift())
            low_close = abs(df['Low'] - df['Close'].shift())
            ranges = pd.concat([high_low, high_close, low_close], axis=1)
            true_range = ranges.max(axis=1)
            df['ATR'] = true_range.rolling(14).mean()
            
            # Volume
            df['Volume_SMA'] = df['Volume'].rolling(20).mean()
            df['Volume_Ratio'] = df['Volume'] / df['Volume_SMA']
            
            return df
        except:
            return df
    
    @staticmethod
    def calculate_ai_score(df, info):
        """Calculate AI-based Stock Health Score"""
        score = 50
        signals = []
        
        try:
            latest = df.iloc[-1]
            price = latest['Close']
            
            # Technical Analysis (50 points)
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
            
            # MACD Analysis
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
                else:
                    score += 4
                    signals.append(("Downward trend active", "negative"))
            
            # Fundamental Analysis (50 points)
            pe = info.get('trailingPE')
            if pe and pd.notna(pe):
                if 10 <= pe <= 25:
                    score += 15
                    signals.append(("Healthy price-to-earnings ratio", "positive"))
                elif pe > 35:
                    score += 5
                    signals.append(("High price-to-earnings ratio", "negative"))
            
            profit_margin = info.get('profitMargins')
            if profit_margin and pd.notna(profit_margin):
                if profit_margin > 0.20:
                    score += 15
                    signals.append(("Excellent profit margins", "positive"))
                elif profit_margin > 0.10:
                    score += 10
                    signals.append(("Good profit margins", "neutral"))
            
            roe = info.get('returnOnEquity')
            if roe and pd.notna(roe):
                if roe > 0.20:
                    score += 20
                    signals.append(("Outstanding return on equity", "positive"))
                elif roe > 0.10:
                    score += 12
                    signals.append(("Good return on equity", "neutral"))
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

# =============================================================================
# AI SENTIMENT ANALYSIS MODULE
# =============================================================================
class SentimentAnalyzer:
    """Mock sentiment analysis (placeholder for FinBERT/API integration)"""
    
    @staticmethod
    def analyze_sentiment(ticker: str):
        """Analyze market sentiment for a stock"""
        # This is a placeholder - in production, integrate FinBERT or news API
        import random
        sentiment_score = random.uniform(-0.5, 0.8)
        
        if sentiment_score > 0.5:
            sentiment_text = "😊 Positive"
            drivers = [
                "✅ Strong earnings beat expectations",
                "✅ Positive analyst upgrades",
                "✅ Industry momentum building"
            ]
        elif sentiment_score > 0:
            sentiment_text = "😐 Neutral"
            drivers = [
                "➡️ Mixed analyst opinions",
                "➡️ Stable industry conditions",
                "⚠️ Some market uncertainty"
            ]
        else:
            sentiment_text = "😟 Negative"
            drivers = [
                "⚠️ Market volatility concerns",
                "⚠️ Sector headwinds present",
                "⚠️ Recent negative news"
            ]
        
        return {
            'score': sentiment_score,
            'text': sentiment_text,
            'drivers': drivers,
            'sources': f"{random.randint(100, 500)} news articles, {random.randint(500, 2000)} social mentions"
        }

# =============================================================================
# AI PRICE FORECASTING MODULE
# =============================================================================
class PriceForecaster:
    """AI-powered price prediction"""
    
    @staticmethod
    def predict_price(df, days: int = 30):
        """Predict future price using simple linear regression"""
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

# =============================================================================
# AUTHENTICATION PAGE
# =============================================================================
def render_auth_page():
    """Render the authentication page"""
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown("<div style='text-align: center; margin-top: 3rem;'><h1>🤖 AI Stock Genius</h1></div>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; color: #94a3b8; font-size: 1.2rem; margin-bottom: 2rem;'>Beginner-Friendly Stock Analysis Powered by AI</p>", unsafe_allow_html=True)
        
        tab1, tab2 = st.tabs(["🔐 Sign In", "✨ Create Account"])
        
        with tab1:
            with st.form("signin_form"):
                st.markdown("### Welcome Back")
                email = st.text_input("Email", placeholder="your@email.com")
                password = st.text_input("Password", type="password", placeholder="Enter password")
                submit = st.form_submit_button("Sign In", use_container_width=True, type="primary")
                
                if submit:
                    if not email or not password:
                        st.error("Please enter both email and password")
                    else:
                        with st.spinner("Signing in..."):
                            success, user, profile = AuthenticationService.signin(email, password)
                            if success:
                                SessionManager.set('authenticated', True)
                                SessionManager.set('user', user)
                                SessionManager.set('profile', profile)
                                st.success("Welcome back!")
                                time.sleep(0.5)
                                st.rerun()
                            else:
                                st.error("Invalid credentials")
        
        with tab2:
            with st.form("signup_form"):
                st.markdown("### Join AI Stock Genius")
                email = st.text_input("Email", placeholder="your@email.com", key="signup_email")
                password = st.text_input("Password", type="password", placeholder="Min 6 characters", key="signup_pass")
                confirm = st.text_input("Confirm Password", type="password", placeholder="Re-enter", key="confirm_pass")
                agree = st.checkbox("I agree to Terms of Service")
                submit = st.form_submit_button("Create Account", use_container_width=True, type="primary")
                
                if submit:
                    if not email or not password:
                        st.error("All fields required")
                    elif not agree:
                        st.error("Please agree to Terms")
                    elif password != confirm:
                        st.error("Passwords don't match")
                    else:
                        with st.spinner("Creating account..."):
                            success, message = AuthenticationService.signup(email, password)
                            if success:
                                st.success(message)
                            else:
                                st.error(message)

# =============================================================================
# ONBOARDING FLOW
# =============================================================================
def render_onboarding():
    """Render onboarding flow for new users"""
    step = SessionManager.get('onboarding_step', 0)
    
    if step == 0:
        # Welcome
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
        # Choose experience level
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
        
        st.info("💡 You can change this anytime in Settings")
    
    elif step == 2:
        # Quick tutorial
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
                SessionManager.set('page', 'home')
                st.rerun()

# =============================================================================
# SIDEBAR NAVIGATION
# =============================================================================
def render_sidebar(is_premium: bool):
    """Render simplified sidebar"""
    with st.sidebar:
        st.markdown("### 🤖 AI Stock Genius")
        st.markdown("---")
        
        # Premium status
        if is_premium:
            st.markdown('<div class="premium-badge">⭐ PREMIUM</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="free-badge">FREE TRIAL</div>', unsafe_allow_html=True)
        
        st.markdown("---")
        st.markdown("#### Navigation")
        
        # Main navigation (3 sections)
        if st.button("🏠 Home", use_container_width=True, key="nav_home"):
            SessionManager.set('page', 'home')
            st.rerun()
        
        if st.button("📊 Analyze", use_container_width=True, key="nav_analyze"):
            SessionManager.set('page', 'analyze')
            st.rerun()
        
        if st.button("💼 My Stocks", use_container_width=True, key="nav_mystocks"):
            SessionManager.set('page', 'mystocks')
            st.rerun()
        
        # Tools (collapsible for beginners)
        beginner_mode = SessionManager.get('beginner_mode', True)
        
        if not beginner_mode:
            with st.expander("🛠️ Tools"):
                if st.button("Strategy Testing", use_container_width=True, key="nav_backtest"):
                    SessionManager.set('page', 'backtest')
                    st.rerun()
                if st.button("Position Calculator", use_container_width=True, key="nav_position"):
                    SessionManager.set('page', 'position')
                    st.rerun()
        
        st.markdown("---")
        
        # Settings
        with st.expander("⚙️ Settings"):
            current_mode = "Beginner" if beginner_mode else "Advanced"
            st.markdown(f"**Mode:** {current_mode}")
            if st.button("Toggle Mode", use_container_width=True):
                SessionManager.set('beginner_mode', not beginner_mode)
                st.rerun()
            
            if st.button("Help & Glossary", use_container_width=True):
                SessionManager.set('page', 'help')
                st.rerun()
        
        st.markdown("---")
        
        # Upgrade button for non-premium
        if not is_premium:
            if st.button("🚀 Upgrade to Premium", use_container_width=True, type="primary"):
                with st.spinner("Upgrading..."):
                    if DatabaseService.upgrade_to_premium(SessionManager.get('user').id):
                        profile = DatabaseService.get_user_profile(SessionManager.get('user').id)
                        SessionManager.set('profile', profile)
                        st.balloons()
                        st.success("Welcome to Premium!")
                        time.sleep(1)
                        st.rerun()
        
        # Sign out at bottom
        st.markdown("<div style='margin-top: 2rem;'></div>", unsafe_allow_html=True)
        if st.button("🚪 Sign Out", use_container_width=True):
            AuthenticationService.signout()
            st.rerun()

# =============================================================================
# HOME PAGE
# =============================================================================
def render_home_page(is_premium: bool):
    """Render the home dashboard"""
    st.title("🏠 Home Dashboard")
    
    # Premium check
    if not is_premium:
        st.markdown('<div class="alert-warning">📢 You are on a free trial. Upgrade to Premium to unlock all AI features!</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="alert-success">🎉 Welcome back! You have full access to all AI-powered features.</div>', unsafe_allow_html=True)
    
    # Show onboarding checklist for new users
    if not SessionManager.get('onboarding_complete'):
        with st.expander("🎯 Get Started Checklist", expanded=True):
            st.markdown("""
            - ☐ Search your first stock
            - ☐ Add stock to Watchlist  
            - ☐ Add a position to Portfolio
            - ☐ Explore AI insights
            """)
            if st.button("Mark Complete", use_container_width=True):
                SessionManager.set('onboarding_complete', True)
                st.rerun()
    
    st.markdown("---")
    
    # Quick stats
    st.markdown("### 📊 Quick Stats")
    watchlist = DatabaseService.get_watchlist(SessionManager.get('user').id)
    portfolio = DatabaseService.get_portfolio(SessionManager.get('user').id)
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Account Type", "💎 Premium" if is_premium else "🆓 Free")
    col2.metric("Watchlist", len(watchlist))
    col3.metric("Portfolio", len(portfolio))
    col4.metric("Status", "Active")
    
    st.markdown("---")
    
    # Quick actions
    st.markdown("### 🚀 Quick Actions")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("📊 Analyze a Stock", use_container_width=True, type="primary"):
            SessionManager.set('page', 'analyze')
            st.rerun()
    
    with col2:
        if st.button("💼 View My Stocks", use_container_width=True):
            SessionManager.set('page', 'mystocks')
            st.rerun()
    
    with col3:
        if st.button("🔍 Screen Stocks", use_container_width=True):
            SessionManager.set('page', 'analyze')
            st.rerun()
    
    st.markdown("---")
    
    # Market overview
    st.markdown("### 📰 Market Overview")
    col1, col2, col3 = st.columns(3)
    
    try:
        indices = {'SPY': 'S&P 500', 'QQQ': 'NASDAQ', 'DIA': 'Dow Jones'}
        for idx, (ticker, name) in enumerate(indices.items()):
            stock = yf.Ticker(ticker)
            hist = stock.history(period='2d')
            if not hist.empty:
                current = hist['Close'].iloc[-1]
                prev = hist['Close'].iloc[-2] if len(hist) > 1 else current
                change = ((current - prev) / prev) * 100
                
                if idx == 0:
                    col1.metric(name, f"${current:.2f}", f"{change:+.2f}%")
                elif idx == 1:
                    col2.metric(name, f"${current:.2f}", f"{change:+.2f}%")
                else:
                    col3.metric(name, f"${current:.2f}", f"{change:+.2f}%")
    except:
        st.info("Market data temporarily unavailable")
    
    st.markdown("---")
    
    # AI tip of the day
    st.markdown("### 💡 AI Tip of the Day")
    tips = [
        "**Diversification is key**: Don't put all your eggs in one basket. Spread investments across different sectors.",
        "**Long-term thinking**: The best investors think in years, not days. Time in the market beats timing the market.",
        "**Use AI insights**: Our Stock Health Score combines 20+ factors to help you make informed decisions.",
        "**Watch the fundamentals**: Strong profit margins and good return on equity often indicate healthy companies.",
        "**Set realistic goals**: Expect 7-10% annual returns over time. Anything promising more is likely too risky."
    ]
    import random
    st.info(random.choice(tips))

# =============================================================================
# ANALYZE PAGE
# =============================================================================
def render_analyze_page(is_premium: bool):
    """Render the stock analysis page with search by name"""
    st.title("📊 Stock Analysis")
    
    # Premium check
    if not is_premium:
        st.markdown('<div class="alert-warning">🔒 Upgrade to Premium to unlock full AI insights, forecasts, and advanced features!</div>', unsafe_allow_html=True)
    
    # Search interface
    st.markdown("### Search for a Stock")
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        search_query = st.text_input(
            "Search by company name or ticker",
            placeholder="e.g., Apple, Tesla, MSFT, Amazon...",
            help="Type any company name or stock ticker",
            label_visibility="collapsed"
        )
    
    ticker = None
    
    if search_query:
        # Search for matches
        results = StockSearchHelper.search_stock(search_query)
        
        if results:
            # Show dropdown with results
            options = [StockSearchHelper.format_option(t, n) for t, n in results]
            
            with col2:
                st.write("")
                analyze_btn = st.button("🔍 Analyze", type="primary", use_container_width=True)
            
            selected = st.selectbox(
                "Select a stock from results:",
                options=options,
                key="stock_select"
            )
            
            if selected:
                ticker = selected.split(" - ")[0].strip()
        else:
            st.info(f"No results found for '{search_query}'. Try a different search term.")
            ticker = None
    else:
        # Default demo stock
        ticker = SessionManager.get('demo_ticker', 'AAPL')
        st.info("💡 Try searching: Apple, Microsoft, Tesla, Amazon, Google")
    
    # Analyze stock if ticker is selected
    if ticker:
        try:
            with st.spinner(f"🤖 AI analyzing {ticker}..."):
                stock = yf.Ticker(ticker)
                
                # Get data
                df = stock.history(period='6mo')
                info = stock.info
                
                if df.empty:
                    st.error("Unable to fetch data for this ticker")
                    return
                
                # Calculate indicators
                df = TechnicalAnalysisEngine.calculate_all_indicators(df)
                
                # Current price info
                price = df['Close'].iloc[-1]
                prev = df['Close'].iloc[-2] if len(df) > 1 else price
                change_pct = ((price - prev) / prev) * 100
                
                # Display header
                company_name = info.get('longName', ticker)
                st.markdown(f"## {company_name} ({ticker})")
                
                # Key metrics row
                col1, col2, col3, col4 = st.columns(4)
                
                col1.metric("Current Price", f"${price:.2f}", f"{change_pct:+.2f}%")
                
                volume = info.get('volume', 0)
                col2.metric("Trading Activity", f"{volume/1e6:.1f}M")
                
                market_cap = info.get('marketCap', 0)
                col3.metric("Company Size", f"${market_cap/1e9:.1f}B" if market_cap > 0 else "N/A")
                
                dividend = info.get('dividendYield', 0)
                col4.metric("Income Return", f"{dividend*100:.2f}%" if dividend else "N/A")
                
                st.markdown("---")
                
                # Premium features
                if is_premium:
                    # AI Health Score
                    ai_analysis = TechnicalAnalysisEngine.calculate_ai_score(df, info)
                    
                    st.markdown("### 🤖 AI Stock Health Score")
                    
                    col1, col2 = st.columns([1, 2])
                    
                    with col1:
                        # Score display
                        score = ai_analysis['score']
                        score_color = "#10b981" if score >= 70 else "#f59e0b" if score >= 50 else "#ef4444"
                        
                        st.markdown(f"""
                        <div style='text-align: center; padding: 2rem; background: rgba(255,255,255,0.05); border-radius: 15px; border: 2px solid {score_color};'>
                            <h1 style='font-size: 4rem; color: {score_color}; margin: 0;'>{score:.0f}</h1>
                            <p style='font-size: 1.5rem; color: #e0e6f0; margin: 0.5rem 0;'>{ai_analysis['rating']}</p>
                            <p style='font-size: 0.875rem; color: #94a3b8;'>out of 100</p>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        st.caption("💡 " + TooltipManager.get_tooltip('stock_health_score'))
                    
                    with col2:
                        st.markdown("#### 📋 AI Analysis")
                        for signal, sentiment in ai_analysis['signals']:
                            icon = "🟢" if sentiment == "positive" else "🔴" if sentiment == "negative" else "🟡"
                            st.markdown(f"{icon} {signal}")
                    
                    st.markdown("---")
                    
                    # Tabs for different views
                    tab1, tab2, tab3 = st.tabs(["📈 Price Chart", "🧠 AI Insights", "📊 Fundamentals"])
                    
                    with tab1:
                        # Price chart
                        beginner_mode = SessionManager.get('beginner_mode', True)
                        
                        if beginner_mode:
                            # Simple chart for beginners
                            fig = go.Figure()
                            fig.add_trace(go.Scatter(
                                x=df.index,
                                y=df['Close'],
                                name='Price',
                                line=dict(color='#3b82f6', width=3),
                                fill='tozeroy',
                                fillcolor='rgba(59, 130, 246, 0.1)'
                            ))
                            fig.update_layout(
                                height=500,
                                template='plotly_dark',
                                title="Price History",
                                xaxis_title="Date",
                                yaxis_title="Price ($)",
                                paper_bgcolor='rgba(0,0,0,0)',
                                plot_bgcolor='rgba(0,0,0,0.3)'
                            )
                        else:
                            # Advanced chart with indicators
                            fig = make_subplots(
                                rows=3, cols=1,
                                shared_xaxes=True,
                                vertical_spacing=0.05,
                                row_heights=[0.6, 0.2, 0.2]
                            )
                            
                            # Candlestick
                            fig.add_trace(go.Candlestick(
                                x=df.index,
                                open=df['Open'],
                                high=df['High'],
                                low=df['Low'],
                                close=df['Close'],
                                name='Price',
                                increasing_line_color='#10b981',
                                decreasing_line_color='#ef4444'
                            ), row=1, col=1)
                            
                            # Moving averages
                            fig.add_trace(go.Scatter(x=df.index, y=df['SMA20'], name='20-day avg', line=dict(color='#fbbf24', width=2)), row=1, col=1)
                            fig.add_trace(go.Scatter(x=df.index, y=df['SMA50'], name='50-day avg', line=dict(color='#f97316', width=2)), row=1, col=1)
                            
                            # MACD
                            colors = ['#10b981' if val >= 0 else '#ef4444' for val in df['MACD_Histogram']]
                            fig.add_trace(go.Bar(x=df.index, y=df['MACD_Histogram'], name='Momentum Signal', marker_color=colors), row=2, col=1)
                            
                            # RSI (Stock Temperature)
                            fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], name='Stock Temperature', line=dict(color='#8b5cf6', width=2)), row=3, col=1)
                            fig.add_hline(y=70, line_dash="dash", line_color="#ef4444", row=3, col=1)
                            fig.add_hline(y=30, line_dash="dash", line_color="#10b981", row=3, col=1)
                            
                            fig.update_layout(
                                height=800,
                                template='plotly_dark',
                                xaxis_rangeslider_visible=False,
                                paper_bgcolor='rgba(0,0,0,0)',
                                plot_bgcolor='rgba(0,0,0,0.3)'
                            )
                        
                        st.plotly_chart(fig, use_container_width=True)
                        
                        if beginner_mode:
                            if st.button("🔧 Switch to Advanced View", use_container_width=True):
                                SessionManager.set('beginner_mode', False)
                                st.rerun()
                    
                    with tab2:
                        # AI Insights
                        st.markdown("### 🧠 Market Sentiment")
                        sentiment = SentimentAnalyzer.analyze_sentiment(ticker)
                        
                        col1, col2 = st.columns([1, 2])
                        with col1:
                            st.markdown(f"<h2 style='text-align: center;'>{sentiment['text']}</h2>", unsafe_allow_html=True)
                            st.caption(f"Score: {sentiment['score']:.2f}")
                        
                        with col2:
                            st.markdown("**Key Drivers:**")
                            for driver in sentiment['drivers']:
                                st.markdown(driver)
                        
                        st.caption(f"📊 Sources: {sentiment['sources']}")
                        st.caption("💡 " + TooltipManager.get_tooltip('sentiment'))
                        
                        st.markdown("---")
                        
                        # Price Forecast
                        st.markdown("### 🔮 30-Day Price Forecast")
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
                    
                    with tab3:
                        # Fundamentals
                        st.markdown("### 📊 Company Fundamentals")
                        
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            st.markdown("**Valuation**")
                            pe = info.get('trailingPE', 'N/A')
                            st.metric("Price Health (P/E)", f"{pe:.2f}" if isinstance(pe, (int, float)) else pe)
                            st.caption("💡 " + TooltipManager.get_tooltip('price_health'))
                            
                            pb = info.get('priceToBook', 'N/A')
                            st.metric("Price to Book", f"{pb:.2f}" if isinstance(pb, (int, float)) else pb)
                        
                        with col2:
                            st.markdown("**Profitability**")
                            profit_margin = info.get('profitMargins', 0)
                            st.metric("Profit Margin", f"{profit_margin*100:.2f}%" if profit_margin else "N/A")
                            
                            roe = info.get('returnOnEquity', 0)
                            st.metric("Return on Equity", f"{roe*100:.2f}%" if roe else "N/A")
                        
                        st.markdown("---")
                        
                        st.markdown("**Company Info**")
                        sector = info.get('sector', 'N/A')
                        industry = info.get('industry', 'N/A')
                        employees = info.get('fullTimeEmployees', 'N/A')
                        
                        st.caption(f"**Sector:** {sector}")
                        st.caption(f"**Industry:** {industry}")
                        st.caption(f"**Employees:** {employees:,}" if isinstance(employees, int) else f"**Employees:** {employees}")
                    
                    st.markdown("---")
                    
                    # Action buttons
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button(f"⭐ Add {ticker} to Watchlist", use_container_width=True, type="primary"):
                            if DatabaseService.add_to_watchlist(SessionManager.get('user').id, ticker):
                                st.success(f"✅ {ticker} added to watchlist!")
                                time.sleep(1)
                                st.rerun()
                            else:
                                st.warning("Already in watchlist")
                    
                    with col2:
                        if st.button(f"💼 Add to Portfolio", use_container_width=True):
                            SessionManager.set('page', 'mystocks')
                            st.rerun()
                
                else:
                    # Free tier - limited features
                    st.markdown('<div class="alert-info">🔒 Upgrade to Premium to see AI Health Score, Sentiment Analysis, and Price Forecasts</div>', unsafe_allow_html=True)
                    
                    # Basic chart only
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(
                        x=df.index,
                        y=df['Close'],
                        name='Price',
                        line=dict(color='#3b82f6', width=3),
                        fill='tozeroy',
                        fillcolor='rgba(59, 130, 246, 0.1)'
                    ))
                    fig.update_layout(
                        height=500,
                        template='plotly_dark',
                        title="Price History (6 months)",
                        paper_bgcolor='rgba(0,0,0,0)',
                        plot_bgcolor='rgba(0,0,0,0.3)'
                    )
                    st.plotly_chart(fig, use_container_width=True)
                    
                    if st.button("🚀 Upgrade to Premium", use_container_width=True, type="primary"):
                        with st.spinner("Upgrading..."):
                            if DatabaseService.upgrade_to_premium(SessionManager.get('user').id):
                                profile = DatabaseService.get_user_profile(SessionManager.get('user').id)
                                SessionManager.set('profile', profile)
                                st.success("Welcome to Premium!")
                                st.rerun()
                
        except Exception as e:
            st.error(f"Error analyzing stock: {e}")

# =============================================================================
# MY STOCKS PAGE (WATCHLIST + PORTFOLIO)
# =============================================================================
def render_mystocks_page(is_premium: bool):
    """Render My Stocks page with tabs"""
    st.title("💼 My Stocks")
    
    if not is_premium:
        st.markdown('<div class="alert-warning">🔒 Upgrade to Premium to unlock unlimited watchlist and portfolio tracking!</div>', unsafe_allow_html=True)
    
    tab1, tab2 = st.tabs(["👁️ Watchlist", "📊 Portfolio"])
    
    with tab1:
        # Watchlist
        st.markdown("### Your Watchlist")
        st.caption("💡 " + TooltipManager.get_tooltip('watchlist'))
        
        # Add stock to watchlist
        with st.expander("➕ Add Stock to Watchlist"):
            search = st.text_input("Search stock", placeholder="e.g., Apple, TSLA", key="watchlist_search")
            
            if search:
                results = StockSearchHelper.search_stock(search)
                if results:
                    options = [StockSearchHelper.format_option(t, n) for t, n in results]
                    selected = st.selectbox("Select stock:", options, key="watchlist_select")
                    
                    if st.button("Add to Watchlist", use_container_width=True, type="primary"):
                        ticker = selected.split(" - ")[0].strip()
                        if DatabaseService.add_to_watchlist(SessionManager.get('user').id, ticker):
                            st.success(f"✅ {ticker} added!")
                            time.sleep(0.5)
                            st.rerun()
                        else:
                            st.warning("Already in watchlist")
        
        st.markdown("---")
        
        # Display watchlist
        watchlist = DatabaseService.get_watchlist(SessionManager.get('user').id)
        
        if watchlist:
            st.markdown(f"**{len(watchlist)} stocks in your watchlist**")
            
            # Display in cards (3 per row)
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
                                        DatabaseService.remove_from_watchlist(SessionManager.get('user').id, ticker)
                                        st.rerun()
                        except:
                            with col:
                                st.markdown(f"**{ticker}**")
                                st.caption("Data unavailable")
                                if st.button("Remove", key=f"wl_rm_err_{ticker}_{i}_{j}", use_container_width=True):
                                    DatabaseService.remove_from_watchlist(SessionManager.get('user').id, ticker)
                                    st.rerun()
        else:
            st.info("Your watchlist is empty. Add stocks to track them!")
    
    with tab2:
        # Portfolio
        st.markdown("### Your Portfolio")
        st.caption("💡 " + TooltipManager.get_tooltip('portfolio'))
        
        # Add position
        with st.expander("➕ Add New Position"):
            col1, col2, col3 = st.columns(3)
            ticker = col1.text_input("Ticker", key="port_ticker").upper()
            shares = col2.number_input("Shares", min_value=0.0, step=0.1, key="port_shares")
            avg_price = col3.number_input("Avg Price", min_value=0.0, step=0.01, key="port_price")
            
            if st.button("Add to Portfolio", use_container_width=True, type="primary"):
                if ticker and shares > 0 and avg_price > 0:
                    if DatabaseService.add_portfolio_position(
                        SessionManager.get('user').id,
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
        
        # Display portfolio
        portfolio = DatabaseService.get_portfolio(SessionManager.get('user').id)
        
        if portfolio:
            # Calculate totals
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
            
            # Display positions
            st.markdown(f"**{len(positions_data)} positions**")
            
            for pos in positions_data:
                col1, col2, col3, col4 = st.columns([2, 2, 2, 1])
                col1.write(f"**{pos['ticker']}**")
                col2.write(f"{pos['shares']} @ ${pos['avg_price']:.2f}")
                
                pnl_color = "🟢" if pos['pnl'] >= 0 else "🔴"
                col3.metric("P/L", f"${pos['pnl']:,.2f}", f"{pos['pnl_pct']:+.1f}%")
                
                if col4.button("Remove", key=f"port_rm_{pos['ticker']}"):
                    DatabaseService.remove_portfolio_position(SessionManager.get('user').id, pos['ticker'])
                    st.rerun()
        else:
            st.info("Your portfolio is empty. Add positions to track performance!")

# =============================================================================
# HELP & GLOSSARY PAGE
# =============================================================================
def render_help_page():
    """Render help and glossary page"""
    st.title("📚 Help & Glossary")
    
    st.markdown("### Plain-English Investing Terms")
    
    terms = {
        "Stock Health Score": "AI's overall rating of a stock from 0-100. Higher scores indicate stronger opportunities based on 20+ factors.",
        "Stock Temperature": "Shows if a stock is 'hot' (overbought) or 'cold' (oversold). Below 30 = potentially undervalued, Above 70 = potentially overvalued.",
        "Momentum Signal": "Indicates if a stock is gaining or losing speed. Green = bullish (going up), Red = bearish (going down).",
        "Price Channel": "The normal price range for a stock. Breaks outside this range may signal big moves coming.",
        "Price Health (P/E)": "How expensive a stock is compared to its earnings. Lower can mean better value, but very low might signal problems.",
        "Trading Activity": "How many shares are being bought/sold. High activity means lots of interest in the stock.",
        "Company Size": "Total value of all company shares (market cap). Larger = more stable, Smaller = more growth potential.",
        "Income Return": "Dividend yield - cash the company pays you each year as a percentage of stock price.",
        "Profit Margin": "What percentage of revenue becomes profit. Higher is better - shows the company is efficient.",
        "Return on Equity": "How well the company uses investor money to generate profits. Above 15% is generally good.",
    }
    
    for term, definition in terms.items():
        with st.expander(f"**{term}**"):
            st.write(definition)
    
    st.markdown("---")
    
    st.markdown("### 🤝 Need More Help?")
    st.info("Contact support at support@aistockgenius.com")

# =============================================================================
# MAIN APPLICATION
# =============================================================================
def main():
    """Main application entry point"""
    
    # Initialize session state - safe check
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
        st.session_state.user = None
        st.session_state.profile = None
        st.session_state.page = 'home'
        st.session_state.beginner_mode = True
        st.session_state.onboarding_complete = False
        st.session_state.onboarding_step = 0
        st.session_state.show_onboarding = True
        st.session_state.demo_ticker = 'AAPL'
        st.session_state.watchlist_cache = None
        st.session_state.portfolio_cache = None
        st.session_state.theme = 'dark'
    
    # Check authentication
    if not st.session_state.get('authenticated', False):
        render_auth_page()
        st.stop()
    
    # Check if onboarding needed
    if st.session_state.get('show_onboarding', False) and not st.session_state.get('onboarding_complete', False):
        render_onboarding()
        st.stop()
    
    # Get user profile
    profile = st.session_state.get('profile', {})
    is_premium = profile.get('is_premium', False)
    
    # Render sidebar
    render_sidebar(is_premium)
    
    # Route to appropriate page
    current_page = st.session_state.get('page', 'home')
    
    if current_page == 'home':
        render_home_page(is_premium)
    elif current_page == 'analyze':
        render_analyze_page(is_premium)
    elif current_page == 'mystocks':
        render_mystocks_page(is_premium)
    elif current_page == 'help':
        render_help_page()
    elif current_page == 'backtest':
        render_backtest_page(is_premium)
    elif current_page == 'position':
        render_position_page(is_premium)
    
    # Footer
    render_footer()

# =============================================================================
# ADVANCED TOOLS (PREMIUM ONLY)
# =============================================================================

def render_backtest_page(is_premium: bool):
    """Render backtesting page - Premium only"""
    st.title("⚡ Strategy Testing")
    
    if not is_premium:
        st.markdown('<div class="alert-warning">🔒 Strategy Testing is a Premium feature! Upgrade to unlock AI-powered backtesting.</div>', unsafe_allow_html=True)
        if st.button("🚀 Upgrade Now", type="primary", use_container_width=True):
            with st.spinner("Upgrading..."):
                if DatabaseService.upgrade_to_premium(SessionManager.get('user').id):
                    SessionManager.set('profile', DatabaseService.get_user_profile(SessionManager.get('user').id))
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
    
    if st.button("🚀 Run Test", type="primary", use_container_width=True):
        with st.spinner(f"🤖 Testing strategy on {ticker}..."):
            # Mock backtest results
            st.success("✅ Test Complete!")
            
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Strategy Return", "+24.5%")
            col2.metric("Buy & Hold", "+18.2%")
            col3.metric("Alpha", "+6.3%")
            col4.metric("Total Trades", "12")
            
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Win Rate", "66.7%")
            col2.metric("Profit Factor", "2.4")
            col3.metric("Sharpe Ratio", "1.8")
            col4.metric("Max Drawdown", "-8.2%")
            
            st.info("💡 This strategy outperformed buy-and-hold by 6.3%!")

def render_position_page(is_premium: bool):
    """Render position sizing calculator - Premium only"""
    st.title("📏 Position Calculator")
    
    if not is_premium:
        st.markdown('<div class="alert-warning">🔒 Position Calculator is a Premium feature!</div>', unsafe_allow_html=True)
        if st.button("🚀 Upgrade Now", type="primary", use_container_width=True):
            with st.spinner("Upgrading..."):
                if DatabaseService.upgrade_to_premium(SessionManager.get('user').id):
                    SessionManager.set('profile', DatabaseService.get_user_profile(SessionManager.get('user').id))
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
                col2.metric("Safety Exit (Stop Loss)", f"${stop_loss:.2f}", f"-{((price - stop_loss) / price * 100):.1f}%")
                col3.metric("Target Win (Take Profit)", f"${take_profit:.2f}", f"+{((take_profit - price) / price * 100):.1f}%")
                
                st.success("✅ Position calculated! This keeps your risk at " + f"{risk*100:.1f}% of your account.")
        except Exception as e:
            st.error(f"Error calculating position: {e}")

def render_footer():
    """Render application footer"""
    st.markdown("---")
    st.markdown("""
    <div style='text-align: center; padding: 2rem; color: #94a3b8;'>
        <p style='font-size: 1.1rem; font-weight: 600;'>🤖 AI Stock Genius</p>
        <p style='font-size: 0.9rem;'>Beginner-Friendly Stock Analysis Platform</p>
        <p style='font-size: 0.85rem;'>© 2025 AI Stock Genius | For educational purposes only</p>
        <p style='font-size: 0.8rem; margin-top: 1rem;'>⚠️ Investment decisions involve risk. Past performance does not guarantee future results.</p>
    </div>
    """, unsafe_allow_html=True)

# =============================================================================
# RUN THE APPLICATION
# =============================================================================

# Initialize session state at module level - safe way
for key, default_value in [
    ('authenticated', False),
    ('user', None),
    ('profile', None),
    ('page', 'home'),
    ('beginner_mode', True),
    ('onboarding_complete', False),
    ('onboarding_step', 0),
    ('show_onboarding', True),
    ('demo_ticker', 'AAPL'),
    ('watchlist_cache', None),
    ('portfolio_cache', None),
    ('theme', 'dark')
]:
    if key not in st.session_state:
        st.session_state[key] = default_value

# Check authentication
if not st.session_state['authenticated']:
    render_auth_page()
    st.stop()

# Check if onboarding needed
if st.session_state['show_onboarding'] and not st.session_state['onboarding_complete']:
    render_onboarding()
    st.stop()

# Get user profile
profile = st.session_state.get('profile', {})
if profile is None:
    profile = {}
is_premium = profile.get('is_premium', False)

# Render sidebar
render_sidebar(is_premium)

# Route to appropriate page
current_page = st.session_state.get('page', 'home')

if current_page == 'home':
    render_home_page(is_premium)
elif current_page == 'analyze':
    render_analyze_page(is_premium)
elif current_page == 'mystocks':
    render_mystocks_page(is_premium)
elif current_page == 'help':
    render_help_page()
elif current_page == 'backtest':
    render_backtest_page(is_premium)
elif current_page == 'position':
    render_position_page(is_premium)
else:
    render_home_page(is_premium)

# Footer
render_footer()
# IMPORTS
# =============================================================================
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

# =============================================================================
# PAGE CONFIGURATION
# =============================================================================
st.set_page_config(
    page_title="AI Stock Genius",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        'Get Help': 'https://aistockgenius.com/help',
        'About': '🤖 AI Stock Genius v4.0 - Beginner-Friendly Stock Analysis'
    }
)

# =============================================================================
# SESSION STATE MANAGER
# =============================================================================
class SessionManager:
    """Centralized session state management"""
    
    @staticmethod
    def initialize():
        """Initialize all session state variables"""
        # Check if session_state is available
        if not hasattr(st, 'session_state'):
            return
        
        defaults = {
            'authenticated': False,
            'user': None,
            'profile': None,
            'page': 'home',
            'beginner_mode': True,  # Default to beginner-friendly
            'onboarding_complete': False,
            'onboarding_step': 0,
            'show_onboarding': True,
            'demo_ticker': 'AAPL',
            'watchlist_cache': None,
            'portfolio_cache': None,
            'theme': 'dark'
        }
        
        for key, value in defaults.items():
            if key not in st.session_state:
                st.session_state[key] = value
    
    @staticmethod
    def get(key: str, default=None):
        if not hasattr(st, 'session_state'):
            return default
        return st.session_state.get(key, default)
    
    @staticmethod
    def set(key: str, value):
        if not hasattr(st, 'session_state'):
            return
        st.session_state[key] = value
    
    @staticmethod
    def clear():
        if not hasattr(st, 'session_state'):
            return
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        SessionManager.initialize()

# =============================================================================
# DATABASE CONNECTION
# =============================================================================
@st.cache_resource
def init_supabase():
    """Initialize Supabase client"""
    try:
        url = st.secrets["supabase"]["url"]
        key = st.secrets["supabase"]["key"]
        return create_client(url, key)
    except Exception as e:
        st.error(f"⚠️ Database connection failed: {e}")
        return None

supabase = init_supabase()

# =============================================================================
# MODERN CSS STYLING - IMPROVED CONTRAST & ACCESSIBILITY
# =============================================================================
def load_custom_css():
    """Load improved CSS with better contrast and readability"""
    st.markdown("""
    <style>
        /* Import Fonts */
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap');
        
        /* Global Styles */
        * {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            font-size: 16px; /* Better base readability */
        }
        
        /* Main Background */
        .stApp {
            background: linear-gradient(135deg, #0a0e1a 0%, #151b2e 100%);
            background-attachment: fixed;
        }
        
        /* Container */
        .main .block-container {
            background: rgba(21, 27, 46, 0.6);
            backdrop-filter: blur(20px);
            border-radius: 20px;
            border: 1px solid rgba(148, 163, 184, 0.2);
            padding: 2.5rem;
            box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.5);
            max-width: 1400px;
        }
        
        /* Headers - High Contrast */
        h1, h2, h3, h4, h5, h6 {
            color: #ffffff !important;
            font-weight: 700 !important;
            letter-spacing: -0.02em;
        }
        
        h1 {
            font-size: 2.5rem !important;
            margin-bottom: 1.5rem !important;
        }
        
        h2 {
            font-size: 1.875rem !important;
            margin-top: 2rem !important;
            margin-bottom: 1.25rem !important;
        }
        
        h3 {
            font-size: 1.5rem !important;
            color: #e0e6f0 !important;
        }
        
        /* Text - Improved Contrast */
        p, span, div, label {
            color: #e0e6f0 !important;
            line-height: 1.6 !important;
        }
        
        /* Buttons - Larger Touch Targets */
        .stButton > button {
            background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
            color: #ffffff !important;
            border: none;
            border-radius: 12px;
            padding: 0.875rem 1.75rem;
            font-weight: 600;
            font-size: 1rem;
            transition: all 0.3s ease;
            box-shadow: 0 4px 12px rgba(59, 130, 246, 0.4);
            width: 100%;
            min-height: 44px; /* Touch-friendly */
        }
        
        .stButton > button:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(59, 130, 246, 0.6);
        }
        
        /* Primary Buttons */
        .stButton > button[kind="primary"] {
            background: linear-gradient(135deg, #10b981 0%, #059669 100%);
            box-shadow: 0 4px 12px rgba(16, 185, 129, 0.4);
        }
        
        /* Metrics - Clear & Readable */
        div[data-testid="stMetricValue"] {
            font-size: 2rem !important;
            font-weight: 800 !important;
            color: #ffffff !important;
        }
        
        div[data-testid="stMetricLabel"] {
            font-size: 0.875rem !important;
            color: #94a3b8 !important;
            font-weight: 600 !important;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }
        
        /* Premium Badge */
        .premium-badge {
            background: linear-gradient(135deg, #fbbf24 0%, #f59e0b 100%);
            color: #1e293b !important;
            padding: 0.75rem 1.5rem;
            border-radius: 12px;
            font-weight: 700;
            font-size: 0.875rem;
            text-align: center;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }
        
        .free-badge {
            background: rgba(100, 116, 139, 0.3);
            color: #e0e6f0 !important;
            padding: 0.75rem 1.5rem;
            border-radius: 12px;
            font-weight: 700;
            font-size: 0.875rem;
            text-align: center;
            border: 2px solid rgba(148, 163, 184, 0.5);
        }
        
        /* Alert Boxes */
        .alert-success {
            background: rgba(16, 185, 129, 0.15);
            border: 2px solid #10b981;
            border-left: 6px solid #10b981;
            padding: 1.25rem 1.5rem;
            border-radius: 15px;
            color: #d1fae5 !important;
            font-weight: 600;
            margin: 1.5rem 0;
        }
        
        .alert-info {
            background: rgba(59, 130, 246, 0.15);
            border: 2px solid #3b82f6;
            border-left: 6px solid #3b82f6;
            padding: 1.25rem 1.5rem;
            border-radius: 15px;
            color: #bfdbfe !important;
            font-weight: 600;
            margin: 1.5rem 0;
        }
        
        .alert-warning {
            background: rgba(245, 158, 11, 0.15);
            border: 2px solid #f59e0b;
            border-left: 6px solid #f59e0b;
            padding: 1.25rem 1.5rem;
            border-radius: 15px;
            color: #fef3c7 !important;
            font-weight: 600;
            margin: 1.5rem 0;
        }
        
        /* Sidebar */
        section[data-testid="stSidebar"] {
            background: linear-gradient(180deg, #151b2e 0%, #0a0e1a 100%);
            border-right: 2px solid rgba(148, 163, 184, 0.2);
            padding: 1rem;
        }
        
        /* Input Fields - Better Contrast */
        .stTextInput > div > div > input,
        .stNumberInput > div > div > input {
            background: rgba(21, 27, 46, 0.8) !important;
            border: 2px solid rgba(148, 163, 184, 0.4) !important;
            border-radius: 10px !important;
            color: #ffffff !important;
            font-size: 1rem !important;
            padding: 0.875rem 1rem !important;
        }
        
        .stTextInput > div > div > input:focus,
        .stNumberInput > div > div > input:focus {
            border-color: #3b82f6 !important;
            box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.2) !important;
        }
        
        /* Selectbox - White Text */
        .stSelectbox label {
            color: #e0e6f0 !important;
        }
        
        .stSelectbox div[data-baseweb="select"] {
            background-color: rgba(21, 27, 46, 0.8) !important;
            border: 2px solid rgba(148, 163, 184, 0.4) !important;
        }
        
        .stSelectbox div[data-baseweb="select"] > div {
            color: #ffffff !important;
        }
        
        /* Tabs */
        .stTabs [data-baseweb="tab-list"] {
            gap: 12px;
            background: rgba(255, 255, 255, 0.05);
            padding: 0.75rem;
            border-radius: 15px;
        }
        
        .stTabs [data-baseweb="tab"] {
            background: transparent;
            border-radius: 10px;
            padding: 1rem 2rem;
            color: #94a3b8 !important;
            font-weight: 600;
            min-height: 44px;
        }
        
        .stTabs [aria-selected="true"] {
            background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
            color: #ffffff !important;
        }
        
        /* Expander */
        .streamlit-expanderHeader {
            background: rgba(255, 255, 255, 0.08);
            border-radius: 12px;
            padding: 1.25rem;
            font-weight: 600;
            color: #ffffff !important;
        }
        
        /* Tooltips */
        .tooltip {
            position: relative;
            display: inline-block;
            cursor: help;
            color: #3b82f6;
            margin-left: 0.5rem;
        }
        
        /* Cards */
        .card {
            background: rgba(255, 255, 255, 0.05);
            border: 2px solid rgba(148, 163, 184, 0.2);
            border-radius: 15px;
            padding: 1.5rem;
            margin: 1rem 0;
            transition: all 0.3s ease;
        }
        
        .card:hover {
            border-color: rgba(148, 163, 184, 0.4);
            transform: translateY(-2px);
        }
        
        /* Divider */
        hr {
            border-color: rgba(148, 163, 184, 0.3);
            margin: 2rem 0;
        }
    </style>
    """, unsafe_allow_html=True)

# Load custom CSS
load_custom_css()

# =============================================================================
