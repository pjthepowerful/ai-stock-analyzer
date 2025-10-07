# =============================================================================
# PERFORMANCE ANALYTICS
# =============================================================================

class PerformanceAnalytics:
    """Portfolio performance and risk analytics"""
    
    @staticmethod
    def calculate_portfolio_metrics(portfolio: List[Dict]) -> Dict:
        """Calculate comprehensive portfolio metrics"""
        try:
            total_invested = 0
            total_current = 0
            positions_data = []
            
            for position in portfolio:
                ticker = position['ticker']
                shares = position['shares']
                avg_price = position['average_price']
                
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
                        'invested': invested,
                        'current': current_value,
                        'pnl': pnl,
                        'pnl_pct': pnl_pct
                    })
                except:
                    continue
            
            total_pnl = total_current - total_invested
            total_pnl_pct = (total_pnl / total_invested * 100) if total_invested > 0 else 0
            
            result = {
                'total_invested': total_invested,
                'total_current': total_current,
                'total_pnl': total_pnl,
                'total_pnl_pct': total_pnl_pct,
                'positions': positions_data,
                'num_positions': len(positions_data)
            }
            return result
            
        except:
            result = {
                'total_invested': 0,
                'total_current': 0,
                'total_pnl': 0,
                'total_pnl_pct': 0,
                'positions': [],
                'num_positions': 0
            }
            return result

# =============================================================================
# AUTHENTICATION PAGE
# =============================================================================

def render_authentication_page():
    """Render the authentication page"""
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown("<div style='text-align: center; margin-top: 4rem;'><h1 style='font-size: 4rem; margin-bottom: 0.5rem;'>🤖 AI Stock Genius</h1></div>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; color: rgba(255, 255, 255, 0.9); font-size: 1.3rem; margin-bottom: 3rem; font-weight: 600;'>AI-Powered Stock Analysis & Trading Intelligence</p>", unsafe_allow_html=True)
        
        tab1, tab2, tab3 = st.tabs(["🔐 Sign In", "✨ Create Account", "🔑 Reset Password"])
        
        with tab1:
            with st.form("signin_form", clear_on_submit=False):
                st.markdown("### Welcome Back to AI Stock Genius")
                email = st.text_input("Email Address", key="signin_email", placeholder="your@email.com")
                password = st.text_input("Password", type="password", key="signin_password", placeholder="Enter your password")
                
                col1, col2 = st.columns(2)
                with col1:
                    remember = st.checkbox("Remember me")
                
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
                                st.success("Welcome back to AI Stock Genius!")
                                time.sleep(0.5)
                                st.rerun()
                            else:
                                st.error("Invalid email or password. Please try again.")
        
        with tab2:
            with st.form("signup_form", clear_on_submit=False):
                st.markdown("### Join AI Stock Genius")
                email = st.text_input("Email Address", key="signup_email", placeholder="your@email.com")
                password = st.text_input("Password", type="password", key="signup_password", placeholder="At least 6 characters")
                confirm = st.text_input("Confirm Password", type="password", key="confirm_password", placeholder="Re-enter password")
                
                agree = st.checkbox("I agree to the Terms of Service and Privacy Policy")
                
                submit = st.form_submit_button("Create Account", use_container_width=True, type="primary")
                
                if submit:
                    if not email or not password or not confirm:
                        st.error("Please fill in all fields")
                    elif not agree:
                        st.error("Please agree to the Terms of Service")
                    elif password != confirm:
                        st.error("Passwords do not match")
                    elif len(password) < 6:
                        st.error("Password must be at least 6 characters")
                    else:
                        with st.spinner("Creating account..."):
                            success, message = AuthenticationService.signup(email, password)
                            
                            if success:
                                st.success(message)
                                st.info("Please check your email to verify your account, then sign in.")
                            else:
                                st.error(message)
        
        with tab3:
            with st.form("reset_form", clear_on_submit=False):
                st.markdown("### Reset Your Password")
                st.caption("Enter your email address and we'll send you a link to reset your password.")
                
                email = st.text_input("Email Address", key="reset_email", placeholder="your@email.com")
                
                submit = st.form_submit_button("Send Reset Link", use_container_width=True, type="primary")
                
                if submit:
                    if not email:
                        st.error("Please enter your email address")
                    else:
                        with st.spinner("Sending reset link..."):
                            success, message = AuthenticationService.reset_password(email)
                            
                            if success:
                                st.success(message)
                            else:
                                st.error(message)

# =============================================================================
# SIDEBAR
# =============================================================================

def render_sidebar(is_premium: bool):
    """Render the sidebar navigation"""
    with st.sidebar:
        st.markdown("### 🤖 AI Stock Genius")
        st.caption(f"👤 {SessionManager.get('user').email}")
        
        st.markdown("---")
        
        if is_premium:
            st.markdown('<div class="premium-badge">⭐ PREMIUM ACTIVE</div>', unsafe_allow_html=True)
            sub_end = SessionManager.get('profile', {}).get('subscription_end_date')
            if sub_end:
                st.caption(f"Valid until: {sub_end[:10]}")
            
            if st.button("Cancel Subscription", use_container_width=True):
                if DatabaseService.cancel_subscription(SessionManager.get('user').id):
                    SessionManager.set('profile', DatabaseService.get_user_profile(SessionManager.get('user').id))
                    st.success("Subscription cancelled")
                    time.sleep(0.5)
                    st.rerun()
        else:
            st.markdown('<div class="free-badge">FREE TIER</div>', unsafe_allow_html=True)
            st.caption("Upgrade for AI-powered features")
            
            if st.button("🚀 Upgrade to Premium - $9.99/mo", use_container_width=True, type="primary"):
                with st.spinner("Upgrading account..."):
                    if DatabaseService.upgrade_to_premium(SessionManager.get('user').id):
                        SessionManager.set('profile', DatabaseService.get_user_profile(SessionManager.get('user').id))
                        st.balloons()
                        st.success("Welcome to Premium!")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("Upgrade failed. Please try again.")
        
        st.markdown("---")
        
        st.markdown("#### 🎯 Navigation")
        
        pages = {
            'dashboard': '📊 Dashboard',
            'analysis': '📈 Stock Analysis',
            'screener': '🔍 Stock Screener',
            'backtest': '⚡ Backtesting',
            'position_sizer': '📏 Position Sizer',
            'watchlist': '👁️ Watchlist',
            'portfolio': '💼 Portfolio'
        }
        
        for key, label in pages.items():
            if st.button(label, use_container_width=True, key=f"nav_{key}"):
                SessionManager.set('page', key)
        
        st.markdown("---")
        
        with st.expander("✨ Premium Features"):
            features = [
                "AI Stock Scoring",
                "Advanced Charts",
                "Technical Patterns",
                "Stock Screener",
                "Price Predictions",
                "Position Sizing",
                "Backtesting Engine",
                "Unlimited Watchlist",
                "Portfolio Tracking",
                "CSV Exports"
            ]
            for f in features:
                icon = "✅" if is_premium else "🔒"
                st.caption(f"{icon} {f}")
        
        st.markdown("---")
        
        if st.button("🚪 Sign Out", use_container_width=True):
            AuthenticationService.signout()
            st.rerun()

# =============================================================================
# PAGE RENDERERS
# =============================================================================

def render_dashboard_page(is_premium: bool):
    """Render the dashboard page"""
    st.title("🤖 AI Stock Genius Dashboard")
    
    if is_premium:
        st.markdown('<div class="alert-success">🎉 Welcome back! You have full access to all AI-powered premium features.</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="alert-info">📢 You are on the free tier. Upgrade to Premium for AI analytics and unlimited features!</div>', unsafe_allow_html=True)
    
    st.markdown("### 📊 Quick Stats")
    
    col1, col2, col3, col4 = st.columns(4)
    
    watchlist = DatabaseService.get_watchlist(SessionManager.get('user').id)
    portfolio = DatabaseService.get_portfolio(SessionManager.get('user').id)
    
    col1.metric("Account Type", "💎 Premium" if is_premium else "🆓 Free")
    col2.metric("Watchlist Stocks", len(watchlist))
    col3.metric("Portfolio Positions", len(portfolio))
    col4.metric("Features Unlocked", "10/10" if is_premium else "3/10")
    
    st.markdown("---")
    
    st.markdown("### 🚀 Quick Actions")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("📈 Analyze a Stock", use_container_width=True, type="primary"):
            SessionManager.set('page', 'analysis')
            st.rerun()
    
    with col2:
        if st.button("🔍 Screen Stocks", use_container_width=True):
            SessionManager.set('page', 'screener')
            st.rerun()
    
    with col3:
        if st.button("💼 View Portfolio", use_container_width=True):
            SessionManager.set('page', 'portfolio')
            st.rerun()
    
    st.markdown("---")
    
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
        pass

def render_analysis_page(is_premium: bool):
    """Render the stock analysis page"""
    st.title("📈 AI-Powered Stock Analysis")
    
    col1, col2, col3 = st.columns([3, 2, 1])
    
    with col1:
        ticker = st.text_input("Enter Stock Ticker", value="AAPL", placeholder="e.g., AAPL, TSLA, MSFT").upper()
    
    with col2:
        period = st.selectbox("Time Period", ["1mo", "3mo", "6mo", "1y", "2y", "5y"], index=2)
    
    with col3:
        st.write("")
        st.write("")
        analyze_btn = st.button("🔍 Analyze", type="primary")
    
    if ticker:
        try:
            with st.spinner(f"🤖 AI analyzing {ticker}..."):
                stock = yf.Ticker(ticker)
                df = stock.history(period=period)
                info = stock.info
                
                if df.empty:
                    st.error("Invalid ticker or no data available")
                else:
                    df = TechnicalAnalysisEngine.calculate_all_indicators(df)
                    
                    price = df['Close'].iloc[-1]
                    prev = df['Close'].iloc[-2] if len(df) > 1 else price
                    change_pct = ((price - prev) / prev) * 100
                    
                    col1, col2, col3, col4 = st.columns(4)
                    
                    col1.metric("Current Price", f"${price:.2f}", f"{change_pct:+.2f}%")
                    
                    if is_premium:
                        ai_analysis = TechnicalAnalysisEngine.calculate_ai_score(df, info)
                        col2.metric("🤖 AI Score", f"{ai_analysis['score']:.0f}/100", ai_analysis['rating'])
                    else:
                        col2.metric("🤖 AI Score", "🔒 Premium")
                    
                    volume = info.get('volume', 0)
                    col3.metric("Volume", f"{volume/1e6:.1f}M")
                    
                    market_cap = info.get('marketCap', 0)
                    col4.metric("Market Cap", f"${market_cap/1e9:.1f}B" if market_cap > 0 else "N/A")
                    
                    st.markdown("---")
                    
                    st.subheader("📊 Price Chart & Technical Indicators")
                    
                    rows = 3 if is_premium else 1
                    fig = make_subplots(
                        rows=rows, cols=1,
                        shared_xaxes=True,
                        vertical_spacing=0.05,
                        row_heights=[0.6, 0.2, 0.2] if is_premium else [1]
                    )
                    
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
                        fig.add_trace(go.Scatter(x=df.index, y=df['SMA20'], name='SMA 20', line=dict(color='#fbbf24', width=2)), row=1, col=1)
                        fig.add_trace(go.Scatter(x=df.index, y=df['SMA50'], name='SMA 50', line=dict(color='#f97316', width=2)), row=1, col=1)
                        fig.add_trace(go.Scatter(x=df.index, y=df['SMA200'], name='SMA 200', line=dict(color='#ef4444', width=2)), row=1, col=1)
                        
                        colors = ['#22c55e' if val >= 0 else '#ef4444' for val in df['MACD_Histogram']]
                        fig.add_trace(go.Bar(x=df.index, y=df['MACD_Histogram'], name='MACD Histogram', marker_color=colors, showlegend=False), row=2, col=1)
                        fig.add_trace(go.Scatter(x=df.index, y=df['MACD'], name='MACD', line=dict(color='#3b82f6', width=2)), row=2, col=1)
                        fig.add_trace(go.Scatter(x=df.index, y=df['MACD_Signal'], name='Signal', line=dict(color='#f97316', width=2)), row=2, col=1)
                        
                        fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], name='RSI', line=dict(color='#8b5cf6', width=2), fill='tozeroy', fillcolor='rgba(139, 92, 246, 0.2)'), row=3, col=1)
                        fig.add_hline(y=70, line_dash="dash", line_color="#ef4444", row=3, col=1)
                        fig.add_hline(y=30, line_dash="dash", line_color="#22c55e", row=3, col=1)
                    
                    fig.update_layout(
                        height=800 if is_premium else 500,
                        template='plotly_dark',
                        xaxis_rangeslider_visible=False,
                        showlegend=True,
                        hovermode='x unified',
                        paper_bgcolor='rgba(0,0,0,0)',
                        plot_bgcolor='rgba(0,0,0,0.3)'
                    )
                    
                    st.plotly_chart(fig, use_container_width=True)
                    
                    if is_premium:
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            st.subheader("🤖 AI Analysis")
                            for signal, sentiment in ai_analysis['signals']:
                                icon = "🟢" if sentiment == "positive" else "🔴" if sentiment == "negative" else "🟡"
                                st.caption(f"{icon} {signal}")
                            
                            patterns = TechnicalAnalysisEngine.detect_chart_patterns(df)
                            if patterns:
                                st.markdown("**📈 Patterns Detected:**")
                                for pattern, direction in patterns:
                                    icon = "🚀" if direction == "bullish" else "📉" if direction == "bearish" else "➡️"
                                    st.caption(f"{icon} {pattern}")
                        
                        with col2:
                            st.subheader("🔮 Price Prediction")
                            prediction = PredictionEngine.predict_price(df, 30)
                            if prediction:
                                st.metric("30-Day Forecast", f"${prediction['predicted_price']:.2f}", f"{prediction['change_pct']:+.2f}%")
                                st.progress(prediction['confidence'] / 100)
                                st.caption(f"Confidence: {prediction['confidence']:.1f}% | Trend: {prediction['trend']}")
                            
                            st.markdown("**💼 Fundamentals:**")
                            st.caption(f"P/E Ratio: {info.get('trailingPE', 'N/A')}")
                            st.caption(f"Dividend Yield: {info.get('dividendYield', 0)*100:.2f}%")
                            st.caption(f"Profit Margin: {info.get('profitMargins', 0)*100:.2f}%")
                        
                        st.markdown("---")
                        
                        if st.button(f"⭐ Add {ticker} to Watchlist", use_container_width=True, type="primary"):
                            if DatabaseService.add_to_watchlist(SessionManager.get('user').id, ticker):
                                st.success(f"✅ {ticker} added to watchlist!")
                            else:
                                st.warning("Already in watchlist")
                    else:
                        st.markdown('<div class="alert-info">🔒 Upgrade to Premium for AI analysis, predictions, and pattern detection</div>', unsafe_allow_html=True)
                        
        except Exception as e:
            st.error(f"Error analyzing stock: {e}")

def render_screener_page(is_premium: bool):
    """Render the stock screener page"""
    st.title("🔍 AI Stock Screener")
    
    if is_premium:
        with st.expander("🎯 Screening Criteria", expanded=True):
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.markdown("**💵 Price Range**")
                min_price = st.number_input("Min Price ($)", value=0.0, step=10.0)
                max_price = st.number_input("Max Price ($)", value=1000.0, step=10.0)
                
                st.markdown("**📊 RSI**")
                min_rsi = st.slider("Min RSI", 0, 100, 0)
                max_rsi = st.slider("Max RSI", 0, 100, 100)
            
            with col2:
                st.markdown("**💼 Fundamentals**")
                min_pe = st.number_input("Min P/E", value=0.0)
                max_pe = st.number_input("Max P/E", value=100.0)
                min_market_cap = st.number_input("Min Market Cap ($B)", value=0.0)
            
            with col3:
                st.markdown("**📈 Profitability**")
                min_dividend = st.number_input("Min Dividend (%)", value=0.0)
                min_profit_margin = st.number_input("Min Profit Margin (%)", value=0.0)
                
                sort_by = st.selectbox("Sort By", ["AI_Score", "Price", "Change_6M", "RSI", "PE"])
        
        if st.button("🚀 Run AI Screener", type="primary", use_container_width=True):
            criteria = {
                'min_price': min_price if min_price > 0 else None,
                'max_price': max_price if max_price < 1000 else None,
                'min_rsi': min_rsi if min_rsi > 0 else None,
                'max_rsi': max_rsi if max_rsi < 100 else None,
                'min_pe': min_pe if min_pe > 0 else None,
                'max_pe': max_pe if max_pe < 100 else None,
                'min_market_cap': min_market_cap if min_market_cap > 0 else None,
                'min_dividend': min_dividend if min_dividend > 0 else None,
                'min_profit_margin': min_profit_margin if min_profit_margin > 0 else None
            }
            
            progress = st.progress(0)
            status = st.empty()
            
            def update_progress(pct):
                progress.progress(pct)
                status.text(f"🤖 AI Screening... {int(pct * 100)}%")
            
            results = StockScreener.screen_stocks(criteria, update_progress)
            
            progress.empty()
            status.empty()
            
            if not results.empty:
                st.success(f"✅ Found {len(results)} stocks matching your criteria!")
                
                results = results.sort_values(by=sort_by, ascending=False).reset_index(drop=True)
                
                col1, col2, col3 = st.columns(3)
                col1.metric("Stocks Found", len(results))
                col2.metric("Avg AI Score", f"{results['AI_Score'].mean():.1f}")
                col3.metric("Avg P/E", f"{results['PE'].mean():.1f}")
                
                display_df = results.copy()
                display_df['Price'] = display_df['Price'].apply(lambda x: f"${x:.2f}")
                display_df['Change_6M'] = display_df['Change_6M'].apply(lambda x: f"{x:+.2f}%")
                display_df['RSI'] = display_df['RSI'].apply(lambda x: f"{x:.2f}")
                display_df['PE'] = display_df['PE'].apply(lambda x: f"{x:.2f}" if x > 0 else "N/A")
                display_df['Market_Cap_B'] = display_df['Market_Cap_B'].apply(lambda x: f"${x:.2f}B")
                display_df['Dividend'] = display_df['Dividend'].apply(lambda x: f"{x:.2f}%")
                display_df['Profit_Margin'] = display_df['Profit_Margin'].apply(lambda x: f"{x:.2f}%")
                display_df['AI_Score'] = display_df['AI_Score'].apply(lambda x: f"{x:.0f}/100")
                
                st.dataframe(display_df, use_container_width=True, hide_index=True)
                
                csv = results.to_csv(index=False)
                st.download_button("📥 Export Results (CSV)", csv, f"ai_stock_genius_screener_{datetime.now().strftime('%Y%m%d')}.csv", "text/csv", use_container_width=True)
            else:
                st.warning("No stocks match your criteria. Try adjusting the filters.")
    else:
        st.markdown('<div class="alert-warning">🔒 Stock Screener is a Premium feature! Upgrade to unlock AI-powered stock screening.</div>', unsafe_allow_html=True)
        if st.button("🚀 Upgrade Now", type="primary", use_container_width=True):
            with st.spinner("Upgrading..."):
                if DatabaseService.upgrade_to_premium(SessionManager.get('user').id):
                    SessionManager.set('profile', DatabaseService.get_user_profile(SessionManager.get('user').id))
                    st.success("Welcome to Premium!")
                    st.rerun()

def render_backtest_page(is_premium: bool):
    """Render the backtesting page"""
    st.title("⚡ Advanced Backtesting Engine")
    
    if is_premium:
        col1, col2, col3 = st.columns(3)
        
        with col1:
            ticker = st.text_input("Ticker Symbol", "AAPL").upper()
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
            with st.spinner(f"🤖 AI backtesting {ticker}..."):
                result = AdvancedTradingStrategy.run_advanced_backtest(ticker, start, end, capital, risk, rr)
                
                if result:
                    st.success("✅ Backtest Complete!")
                    
                    col1, col2, col3, col4 = st.columns(4)
                    col1.metric("Strategy Return", f"{result['total_return']:.2f}%")
                    col2.metric("Buy & Hold", f"{result['buy_hold_return']:.2f}%")
                    col3.metric("Alpha", f"{result['alpha']:.2f}%")
                    col4.metric("Total Trades", result['num_trades'])
                    
                    col1, col2, col3, col4 = st.columns(4)
                    col1.metric("Win Rate", f"{result['win_rate']:.1f}%")
                    col2.metric("Profit Factor", f"{result['profit_factor']:.2f}")
                    col3.metric("Sharpe Ratio", f"{result['sharpe_ratio']:.2f}")
                    col4.metric("Max Drawdown", f"{result['max_drawdown']:.2f}%")
                    
                    st.markdown("---")
                    
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(
                        x=list(range(len(result['equity_curve']))), 
                        y=result['equity_curve'], 
                        name='Equity Curve', 
                        fill='tozeroy',
                        line=dict(color='#22c55e', width=3)
                    ))
                    fig.update_layout(
                        height=500, 
                        template='plotly_dark',
                        title="Equity Curve",
                        paper_bgcolor='rgba(0,0,0,0)',
                        plot_bgcolor='rgba(0,0,0,0.3)'
                    )
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.error("Backtest failed. Please try different parameters.")
    else:
        st.markdown('<div class="alert-warning">🔒 Backtesting Engine is Premium only!</div>', unsafe_allow_html=True)

def render_position_sizer_page(is_premium: bool):
    """Render the position sizer page"""
    st.title("📏 AI Position Size Calculator")
    
    if is_premium:
        col1, col2 = st.columns(2)
        
        with col1:
            ticker = st.text_input("Ticker Symbol", "AAPL").upper()
            account = st.number_input("Account Size ($)", 100000, step=1000)
            risk = st.slider("Risk per Trade (%)", 0.5, 5.0, 2.0) / 100
        
        with col2:
            method = st.selectbox("Sizing Method", ["Kelly Criterion", "Fixed Risk", "Volatility", "All Methods"])
            rr = st.slider("Risk/Reward Ratio", 1.0, 5.0, 2.0)
        
        if st.button("🤖 Calculate Position Size", type="primary", use_container_width=True):
            try:
                stock = yf.Ticker(ticker)
                hist = stock.history(period='3mo')
                df = TechnicalAnalysisEngine.calculate_all_indicators(hist)
                
                price = df['Close'].iloc[-1]
                vol = df['Close'].pct_change().std()
                atr = df['ATR'].iloc[-1]
                
                method_map = {
                    "Kelly Criterion": "kelly", 
                    "Fixed Risk": "fixed", 
                    "Volatility": "volatility", 
                    "All Methods": "all"
                }
                sizes = PositionSizingEngine.calculate_position_size(account, price, vol, method_map[method], risk)
                stops = PositionSizingEngine.calculate_stop_loss_take_profit(price, atr, rr)
                
                st.markdown("---")
                st.subheader("Position Sizing Results")
                if method == "All Methods":
                    for m, data in sizes.items():
                        st.write(f"**{m.title()}:** {data['shares']} shares (${data['position_value']:,.0f})")
                else:
                    data = sizes[method_map[method]]
                    col1, col2, col3 = st.columns(3)
                    col1.metric("Shares to Buy", data['shares'])
                    col2.metric("Position Value", f"${data['position_value']:,.0f}")
                    col3.metric("% of Account", f"{data['position_pct']:.1f}%")
                
                st.markdown("---")
                st.subheader("Risk Management Levels")
                col1, col2, col3 = st.columns(3)
                col1.metric("Entry Price", f"${stops['entry_price']:.2f}")
                col2.metric("Stop Loss", f"${stops['stop_loss']:.2f}", f"-{stops['stop_loss_pct']:.1f}%")
                col3.metric("Take Profit", f"${stops['take_profit']:.2f}", f"+{stops['take_profit_pct']:.1f}%")
            except Exception as e:
                st.error(f"Error calculating position size: {e}")
    else:
        st.markdown('<div class="alert-warning">🔒 Premium feature</div>', unsafe_allow_html=True)

def render_watchlist_page(is_premium: bool):
    """Render the watchlist page"""
    st.title("👁️ Watchlist")
    
    if is_premium:
        col1, col2 = st.columns([3, 1])
        with col1:
            new_ticker = st.text_input("Add ticker to watchlist").upper()
        with col2:
            st.write("")
            st.write("")
            if st.button("Add Stock", type="primary"):
                if new_ticker:
                    if DatabaseService.add_to_watchlist(SessionManager.get('user').id, new_ticker):
                        st.success(f"✅ Added {new_ticker}!")
                        time.sleep(0.5)
                        st.rerun()
                    else:
                        st.warning("Already in watchlist")
        
        st.markdown("---")
        
        watchlist = DatabaseService.get_watchlist(SessionManager.get('user').id)
        
        if watchlist:
            st.subheader(f"📋 Your Watchlist ({len(watchlist)} stocks)")
            
            for item in watchlist:
                ticker = item['ticker']
                try:
                    stock = yf.Ticker(ticker)
                    hist = stock.history(period='1d')
                    
                    if not hist.empty:
                        price = hist['Close'].iloc[-1]
                        
                        col1, col2, col3 = st.columns([2, 2, 1])
                        col1.write(f"**{ticker}**")
                        col2.write(f"${price:.2f}")
                        if col3.button("Remove", key=ticker):
                            DatabaseService.remove_from_watchlist(SessionManager.get('user').id, ticker)
                            st.rerun()
                except:
                    col1, col2 = st.columns([4, 1])
                    col1.write(f"**{ticker}**")
                    if col2.button("Remove", key=ticker):
                        DatabaseService.remove_from_watchlist(SessionManager.get('user').id, ticker)
                        st.rerun()
        else:
            st.info("Your watchlist is empty. Add stocks to track them!")
    else:
        st.markdown('<div class="alert-warning">🔒 Premium feature</div>', unsafe_allow_html=True)

def render_portfolio_page(is_premium: bool):
    """Render the portfolio page"""
    st.title("💼 Portfolio Tracker")
    
    if is_premium:
        with st.expander("➕ Add New Position"):
            col1, col2, col3 = st.columns(3)
            ticker = col1.text_input("Ticker Symbol").upper()
            shares = col2.number_input("Number of Shares", 0.0, step=0.1)
            price = col3.number_input("Average Price", 0.0, step=0.01)
            
            if st.button("Add to Portfolio", type="primary", use_container_width=True):
                if ticker and shares > 0 and price > 0:
                    if DatabaseService.add_portfolio_position(SessionManager.get('user').id, ticker, shares, price, datetime.now().date().isoformat()):
                        st.success(f"✅ Added {shares} shares of {ticker}!")
                        time.sleep(0.5)
                        st.rerun()
                else:
                    st.error("Please fill in all fields")
        
        st.markdown("---")
        
        portfolio = DatabaseService.get_portfolio(SessionManager.get('user').id)
        
        if portfolio:
            metrics = PerformanceAnalytics.calculate_portfolio_metrics(portfolio)
            
            st.subheader("📊 Portfolio Summary")
            col1, col2, col3 = st.columns(3)
            col1.metric("Total Invested", f"${metrics['total_invested']:,.0f}")
            col2.metric("Current Value", f"${metrics['total_current']:,.0f}")
            col3.metric("Total P/L", f"${metrics['total_pnl']:,.0f}", f"{metrics['total_pnl_pct']:+.1f}%")
            
            st.markdown("---")
            
            st.subheader(f"📈 Positions ({len(portfolio)})")
            
            for pos in portfolio:
                ticker = pos['ticker']
                shares = pos['shares']
                avg_price = pos['average_price']
                
                try:
                    stock = yf.Ticker(ticker)
                    current_price = stock.history(period='1d')['Close'].iloc[-1]
                    pnl = (current_price - avg_price) * shares
                    pnl_pct = ((current_price - avg_price) / avg_price) * 100
                    
                    col1, col2, col3, col4 = st.columns([2, 2, 2, 1])
                    col1.write(f"**{ticker}**")
                    col2.write(f"{shares} shares @ ${avg_price:.2f}")
                    col3.metric("P/L", f"${pnl:,.2f}", f"{pnl_pct:+.1f}%")
                    if col4.button("Remove", key=ticker):
                        DatabaseService.remove_portfolio_position(SessionManager.get('user').id, ticker)
                        st.rerun()
                except:
                    col1, col2 = st.columns([4, 1])
                    col1.write(f"{ticker}: {shares} @ ${avg_price:.2f}")
                    if col2.button("Remove", key=ticker):
                        DatabaseService.remove_portfolio_position(SessionManager.get('user').id, ticker)
                        st.rerun()
        else:
            st.info("Your portfolio is empty. Add positions to track performance!")
    else:
        st.markdown('<div class="alert-warning">🔒 Premium feature</div>', unsafe_allow_html=True)

def render_footer():
    """Render the footer"""
    st.markdown("---")
    st.markdown("""
    <div style='text-align: center; padding: 2rem; color: rgba(255, 255, 255, 0.7);'>
        <p style='font-size: 1.1rem; font-weight: 600;'>🤖 AI Stock Genius Professional Platform</p>
        <p style='font-size: 0.9rem;'>Powered by Advanced AI & Machine Learning</p>
        <p style='font-size: 0.85rem;'>© 2025 AI Stock Genius | For educational purposes only</p>
        <p style='font-size: 0.8rem; margin-top: 1rem;'>⚠️ Investment decisions involve risk. Past performance does not guarantee future results.</p>
    </div>
    """, unsafe_allow_html=True)

# =============================================================================
# MAIN APPLICATION ENTRY POINT
# =============================================================================

def main():
    """Main application entry point"""
    
    # Check authentication status
    if not SessionManager.get('authenticated'):
        render_authentication_page()
        st.stop()
    
    # Get premium status
    is_premium = SessionManager.get('profile', {}).get('is_premium', False)
    
    # Render sidebar
    render_sidebar(is_premium)
    
    # Route to appropriate page
    current_page = SessionManager.get('page', 'dashboard')
    
    if current_page == 'dashboard':
        render_dashboard_page(is_premium)
    elif current_page == 'analysis':
        render_analysis_page(is_premium)
    elif current_page == 'screener':
        render_screener_page(is_premium)
    elif current_page == 'backtest':
        render_backtest_page(is_premium)
    elif current_page == 'position_sizer':
        render_position_sizer_page(is_premium)
    elif current_page == 'watchlist':
        render_watchlist_page(is_premium)
    elif current_page == 'portfolio':
        render_portfolio_page(is_premium)
    
    # Render footer
    render_footer()

# =============================================================================
# RUN APPLICATION
# =============================================================================

if __name__ == "__main__":
    main()

"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                           AI STOCK GENIUS                                     ║
║                   Professional Stock Analysis Platform                        ║
║                                                                              ║
║  Version: 3.0.0                                                              ║
║  Author: AI Stock Genius Development Team                                   ║
║  Description: AI-Powered Stock Analysis & Trading Intelligence Platform     ║
║  License: Proprietary                                                        ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

# =============================================================================
# IMPORTS - STANDARD LIBRARY
# =============================================================================
import json
import time
import warnings
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional

# =============================================================================
# IMPORTS - THIRD PARTY LIBRARIES
# =============================================================================
import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from supabase import create_client

# =============================================================================
# CONFIGURATION
# =============================================================================
warnings.filterwarnings('ignore')

# Streamlit Page Configuration - Must be first Streamlit command
st.set_page_config(
    page_title="AI Stock Genius",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        'Get Help': 'https://aistockgenius.com/help',
        'Report a bug': 'https://aistockgenius.com/bug',
        'About': 'AI-Powered Stock Analysis Platform v3.0'
    }
)

# =============================================================================
# DATABASE CONNECTION
# =============================================================================

@st.cache_resource
def init_supabase():
    """
    Initialize Supabase client with caching
    
    Returns:
        Supabase client instance or None if connection fails
    """
    try:
        url = st.secrets["supabase"]["url"]
        key = st.secrets["supabase"]["key"]
        return create_client(url, key)
    except Exception as e:
        st.error(f"⚠️ Database connection failed: {e}")
        return None

supabase = init_supabase()

# =============================================================================
# CUSTOM CSS STYLING - MODERN GRADIENT UI
# =============================================================================

def load_custom_css():
    """Load custom CSS for modern gradient UI"""
    st.markdown("""
    <style>
        /* Import Modern Fonts */
        @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800;900&family=Space+Grotesk:wght@400;500;600;700&display=swap');
        
        /* Global Styles */
        * {
            font-family: 'Outfit', -apple-system, BlinkMacSystemFont, sans-serif;
        }
        
        /* Main App Background - Dynamic Gradient */
        .stApp {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 25%, #f093fb 50%, #4facfe 75%, #00f2fe 100%);
            background-size: 400% 400%;
            animation: gradientShift 15s ease infinite;
        }
        
        @keyframes gradientShift {
            0% { background-position: 0% 50%; }
            50% { background-position: 100% 50%; }
            100% { background-position: 0% 50%; }
        }
        
        /* Glass Morphism Container */
        .main .block-container {
            background: rgba(255, 255, 255, 0.05);
            backdrop-filter: blur(20px);
            border-radius: 30px;
            border: 1px solid rgba(255, 255, 255, 0.15);
            padding: 2rem;
            box-shadow: 0 8px 32px 0 rgba(31, 38, 135, 0.37);
        }
        
        /* Headers with Gradient Text */
        h1, h2, h3, h4, h5, h6 {
            background: linear-gradient(135deg, #ffffff 0%, #e0e7ff 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            font-weight: 800 !important;
            letter-spacing: -0.03em;
            font-family: 'Space Grotesk', sans-serif;
        }
        
        h1 {
            font-size: 3.5rem !important;
            margin-bottom: 1.5rem !important;
            text-shadow: 0 0 80px rgba(255, 255, 255, 0.5);
        }
        
        h2 {
            font-size: 2.25rem !important;
            margin-top: 2.5rem !important;
            margin-bottom: 1.5rem !important;
            position: relative;
            padding-bottom: 1rem;
        }
        
        h2::after {
            content: '';
            position: absolute;
            bottom: 0;
            left: 0;
            width: 100px;
            height: 4px;
            background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
            border-radius: 2px;
        }
        
        h3 {
            font-size: 1.75rem !important;
            color: #f0f4ff !important;
            margin-bottom: 1rem !important;
        }
        
        /* Modern Button Styles */
        .stButton > button {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 15px;
            padding: 1rem 2rem;
            font-weight: 700;
            font-size: 1rem;
            transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
            box-shadow: 0 10px 25px -5px rgba(102, 126, 234, 0.6),
                        0 0 50px -12px rgba(118, 75, 162, 0.3);
            width: 100%;
            text-transform: uppercase;
            letter-spacing: 1px;
            position: relative;
            overflow: hidden;
        }
        
        .stButton > button::before {
            content: '';
            position: absolute;
            top: 0;
            left: -100%;
            width: 100%;
            height: 100%;
            background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.3), transparent);
            transition: left 0.5s;
        }
        
        .stButton > button:hover::before {
            left: 100%;
        }
        
        .stButton > button:hover {
            transform: translateY(-5px) scale(1.02);
            box-shadow: 0 20px 40px -5px rgba(102, 126, 234, 0.8),
                        0 0 80px -12px rgba(118, 75, 162, 0.5);
        }
        
        .stButton > button:active {
            transform: translateY(-2px) scale(0.98);
        }
        
        /* Primary Button Variant */
        .stButton > button[kind="primary"] {
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
            box-shadow: 0 10px 25px -5px rgba(240, 147, 251, 0.6);
        }
        
        .stButton > button[kind="primary"]:hover {
            box-shadow: 0 20px 40px -5px rgba(240, 147, 251, 0.8);
        }
        
        /* Glassmorphic Metrics */
        div[data-testid="stMetricValue"] {
            font-size: 2.5rem;
            font-weight: 900;
            background: linear-gradient(135deg, #ffffff 0%, #e0e7ff 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            text-shadow: 0 0 30px rgba(255, 255, 255, 0.3);
        }
        
        div[data-testid="stMetricLabel"] {
            font-size: 0.95rem;
            color: rgba(255, 255, 255, 0.9);
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.1em;
        }
        
        div[data-testid="stMetricDelta"] {
            font-size: 1.1rem;
            font-weight: 700;
        }
        
        /* Premium Badges with Animation */
        .premium-badge {
            background: linear-gradient(135deg, #ffd700 0%, #ffed4e 50%, #ffd700 100%);
            background-size: 200% 200%;
            animation: shimmer 3s ease infinite;
            color: #000;
            padding: 0.75rem 1.5rem;
            border-radius: 50px;
            font-weight: 900;
            font-size: 0.85rem;
            display: inline-block;
            box-shadow: 0 4px 15px rgba(255, 215, 0, 0.6),
                        inset 0 -2px 5px rgba(0, 0, 0, 0.2);
            text-transform: uppercase;
            letter-spacing: 0.1em;
            border: 2px solid rgba(255, 255, 255, 0.5);
        }
        
        @keyframes shimmer {
            0% { background-position: 0% 50%; }
            50% { background-position: 100% 50%; }
            100% { background-position: 0% 50%; }
        }
        
        .free-badge {
            background: rgba(148, 163, 184, 0.2);
            color: rgba(255, 255, 255, 0.9);
            padding: 0.75rem 1.5rem;
            border-radius: 50px;
            font-weight: 800;
            font-size: 0.85rem;
            display: inline-block;
            border: 2px solid rgba(148, 163, 184, 0.4);
            text-transform: uppercase;
            letter-spacing: 0.1em;
            backdrop-filter: blur(10px);
        }
        
        /* Alert Boxes with Glow */
        .alert-success {
            background: rgba(34, 197, 94, 0.15);
            border: 2px solid #22c55e;
            border-left: 6px solid #22c55e;
            padding: 1.25rem 1.5rem;
            border-radius: 15px;
            margin: 1.5rem 0;
            color: #86efac;
            backdrop-filter: blur(10px);
            box-shadow: 0 0 30px rgba(34, 197, 94, 0.3);
            font-weight: 600;
        }
        
        .alert-warning {
            background: rgba(251, 191, 36, 0.15);
            border: 2px solid #fbbf24;
            border-left: 6px solid #fbbf24;
            padding: 1.25rem 1.5rem;
            border-radius: 15px;
            margin: 1.5rem 0;
            color: #fde047;
            backdrop-filter: blur(10px);
            box-shadow: 0 0 30px rgba(251, 191, 36, 0.3);
            font-weight: 600;
        }
        
        .alert-error {
            background: rgba(239, 68, 68, 0.15);
            border: 2px solid #ef4444;
            border-left: 6px solid #ef4444;
            padding: 1.25rem 1.5rem;
            border-radius: 15px;
            margin: 1.5rem 0;
            color: #fca5a5;
            backdrop-filter: blur(10px);
            box-shadow: 0 0 30px rgba(239, 68, 68, 0.3);
            font-weight: 600;
        }
        
        .alert-info {
            background: rgba(59, 130, 246, 0.15);
            border: 2px solid #3b82f6;
            border-left: 6px solid #3b82f6;
            padding: 1.25rem 1.5rem;
            border-radius: 15px;
            margin: 1.5rem 0;
            color: #93c5fd;
            backdrop-filter: blur(10px);
            box-shadow: 0 0 30px rgba(59, 130, 246, 0.3);
            font-weight: 600;
        }
        
        /* Sidebar with Gradient */
        section[data-testid="stSidebar"] {
            background: linear-gradient(180deg, rgba(102, 126, 234, 0.3) 0%, rgba(118, 75, 162, 0.3) 100%);
            backdrop-filter: blur(20px);
            border-right: 2px solid rgba(255, 255, 255, 0.1);
        }
        
        section[data-testid="stSidebar"] > div {
            padding-top: 2rem;
        }
        
        /* Modern Tabs */
        .stTabs [data-baseweb="tab-list"] {
            gap: 12px;
            background: rgba(255, 255, 255, 0.05);
            padding: 0.75rem;
            border-radius: 20px;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.1);
        }
        
        .stTabs [data-baseweb="tab"] {
            background: transparent;
            border-radius: 12px;
            padding: 1rem 2rem;
            color: rgba(255, 255, 255, 0.7);
            font-weight: 700;
            transition: all 0.3s ease;
            border: 2px solid transparent;
        }
        
        .stTabs [data-baseweb="tab"]:hover {
            background: rgba(255, 255, 255, 0.1);
            color: rgba(255, 255, 255, 0.95);
            border-color: rgba(255, 255, 255, 0.2);
        }
        
        .stTabs [aria-selected="true"] {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white !important;
            box-shadow: 0 4px 15px rgba(102, 126, 234, 0.5);
            border-color: rgba(255, 255, 255, 0.3);
        }
        
        /* Input Fields with Glow */
        .stTextInput > div > div > input,
        .stNumberInput > div > div > input,
        .stSelectbox > div > div {
            background: rgba(255, 255, 255, 0.08);
            border: 2px solid rgba(255, 255, 255, 0.2);
            border-radius: 12px;
            color: #ffffff;
            font-size: 1rem;
            padding: 1rem 1.25rem;
            transition: all 0.3s ease;
            font-weight: 600;
            backdrop-filter: blur(10px);
        }
        
        .stTextInput > div > div > input:focus,
        .stNumberInput > div > div > input:focus {
            border-color: #667eea;
            box-shadow: 0 0 0 4px rgba(102, 126, 234, 0.2),
                        0 0 20px rgba(102, 126, 234, 0.4);
            background: rgba(255, 255, 255, 0.12);
        }
        
        /* DataFrames with Style */
        .stDataFrame {
            background: rgba(255, 255, 255, 0.05);
            border-radius: 15px;
            border: 2px solid rgba(255, 255, 255, 0.1);
            overflow: hidden;
            backdrop-filter: blur(10px);
        }
        
        /* Sliders with Gradient */
        .stSlider > div > div > div {
            background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        }
        
        /* Expander */
        .streamlit-expanderHeader {
            background: rgba(255, 255, 255, 0.08);
            border-radius: 15px;
            padding: 1.25rem;
            font-weight: 700;
            border: 2px solid rgba(255, 255, 255, 0.15);
            backdrop-filter: blur(10px);
            transition: all 0.3s ease;
        }
        
        .streamlit-expanderHeader:hover {
            background: rgba(255, 255, 255, 0.12);
            border-color: rgba(255, 255, 255, 0.25);
        }
        
        /* Progress Bars */
        .stProgress > div > div {
            background: linear-gradient(90deg, #667eea 0%, #764ba2 50%, #f093fb 100%);
            border-radius: 10px;
        }
        
        /* Custom Scrollbar */
        ::-webkit-scrollbar {
            width: 12px;
            height: 12px;
        }
        
        ::-webkit-scrollbar-track {
            background: rgba(255, 255, 255, 0.05);
            border-radius: 10px;
        }
        
        ::-webkit-scrollbar-thumb {
            background: linear-gradient(180deg, #667eea 0%, #764ba2 100%);
            border-radius: 10px;
            border: 2px solid rgba(255, 255, 255, 0.1);
        }
        
        ::-webkit-scrollbar-thumb:hover {
            background: linear-gradient(180deg, #764ba2 0%, #667eea 100%);
        }
        
        /* Loading Spinner */
        .stSpinner > div {
            border-top-color: #667eea !important;
            border-right-color: #764ba2 !important;
        }
        
        /* Caption Text */
        .caption {
            color: rgba(255, 255, 255, 0.7);
            font-size: 0.95rem;
            font-weight: 500;
        }
        
        /* Divider */
        hr {
            border-color: rgba(255, 255, 255, 0.2);
            margin: 3rem 0;
            border-width: 2px;
        }
        
        /* Text Colors */
        p, span, div {
            color: rgba(255, 255, 255, 0.95);
        }
        
        /* Link Styles */
        a {
            color: #93c5fd;
            text-decoration: none;
            transition: all 0.3s ease;
        }
        
        a:hover {
            color: #dbeafe;
            text-shadow: 0 0 10px rgba(147, 197, 253, 0.5);
        }
    </style>
    """, unsafe_allow_html=True)

# =============================================================================
# SESSION STATE MANAGER
# =============================================================================

class SessionManager:
    """Centralized session state management"""
    
    @staticmethod
    def initialize():
        """Initialize all session state variables"""
        defaults = {
            'authenticated': False,
            'user': None,
            'profile': None,
            'page': 'dashboard',
            'watchlist_cache': None,
            'portfolio_cache': None,
            'analysis_cache': {},
            'screener_results': None,
            'backtest_results': None,
            'theme': 'gradient'
        }
        
        for key, value in defaults.items():
            if key not in st.session_state:
                st.session_state[key] = value
    
    @staticmethod
    def clear():
        """Clear all session state"""
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        SessionManager.initialize()
    
    @staticmethod
    def get(key: str, default=None):
        """Safely get session state value"""
        return st.session_state.get(key, default)
    
    @staticmethod
    def set(key: str, value):
        """Safely set session state value"""
        st.session_state[key] = value

# =============================================================================
# INITIALIZE APPLICATION
# =============================================================================

# Load custom CSS
load_custom_css()

# Initialize session state
SessionManager.initialize()

# =============================================================================
# AUTHENTICATION SERVICE
# =============================================================================

class AuthenticationService:
    """Handle all authentication operations"""
    
    @staticmethod
    def signup(email: str, password: str) -> Tuple[bool, str]:
        """Create new user account"""
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
                return True, "Account created successfully! Please check your email to verify."
            
            return False, "Failed to create account. Please try again."
            
        except Exception as e:
            error_msg = str(e)
            if "already registered" in error_msg.lower():
                return False, "This email is already registered"
            return False, f"Signup error: {error_msg}"
    
    @staticmethod
    def signin(email: str, password: str) -> Tuple[bool, Optional[any], Optional[Dict]]:
        """Sign in existing user"""
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
            
        except Exception as e:
            return False, None, None
    
    @staticmethod
    def signout():
        """Sign out current user and clear session"""
        try:
            if supabase:
                supabase.auth.sign_out()
        except:
            pass
        finally:
            SessionManager.clear()
    
    @staticmethod
    def reset_password(email: str) -> Tuple[bool, str]:
        """Send password reset email"""
        try:
            if not email:
                return False, "Email is required"
            
            if supabase is None:
                return False, "Database unavailable"
            
            supabase.auth.reset_password_for_email(email)
            return True, "Password reset email sent! Check your inbox."
            
        except Exception as e:
            return False, f"Error: {str(e)}"
    
    @staticmethod
    def get_current_user():
        """Get currently authenticated user"""
        try:
            if supabase:
                return supabase.auth.get_user()
            return None
        except:
            return None

# =============================================================================
# DATABASE SERVICE
# =============================================================================

class DatabaseService:
    """Handle all database operations"""
    
    @staticmethod
    def get_user_profile(user_id: str) -> Dict:
        """Get user profile from database"""
        try:
            if supabase is None:
                return {'id': user_id, 'is_premium': False, 'subscription_end_date': None}
            
            result = supabase.table('user_profiles').select('*').eq('id', user_id).single().execute()
            if result.data:
                return result.data
            return {'id': user_id, 'is_premium': False, 'subscription_end_date': None}
        except:
            return {'id': user_id, 'is_premium': False, 'subscription_end_date': None}
    
    @staticmethod
    def upgrade_to_premium(user_id: str) -> bool:
        """Upgrade user to premium status"""
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
            
        except Exception as e:
            st.error(f"Upgrade failed: {e}")
            return False
    
    @staticmethod
    def cancel_subscription(user_id: str) -> bool:
        """Cancel premium subscription"""
        try:
            if supabase is None:
                return False
            
            supabase.table('user_profiles').update({
                'is_premium': False,
                'subscription_end_date': None
            }).eq('id', user_id).execute()
            
            return True
            
        except:
            return False
    
    @staticmethod
    def get_watchlist(user_id: str) -> List[Dict]:
        """Get user's watchlist"""
        try:
            if supabase is None:
                return []
            result = supabase.table('watchlists').select('*').eq('user_id', user_id).execute()
            return result.data if result.data else []
        except:
            return []
    
    @staticmethod
    def add_to_watchlist(user_id: str, ticker: str, notes: str = "") -> bool:
        """Add stock to watchlist"""
        try:
            if supabase is None:
                return False
            
            existing = supabase.table('watchlists').select('ticker').eq('user_id', user_id).eq('ticker', ticker).execute()
            
            if existing.data:
                return False
            
            supabase.table('watchlists').insert({
                'user_id': user_id,
                'ticker': ticker,
                'notes': notes,
                'created_at': datetime.now().isoformat()
            }).execute()
            
            return True
            
        except Exception as e:
            st.error(f"Failed to add to watchlist: {e}")
            return False
    
    @staticmethod
    def remove_from_watchlist(user_id: str, ticker: str) -> bool:
        """Remove stock from watchlist"""
        try:
            if supabase is None:
                return False
            supabase.table('watchlists').delete().eq('user_id', user_id).eq('ticker', ticker).execute()
            return True
        except:
            return False
    
    @staticmethod
    def get_portfolio(user_id: str) -> List[Dict]:
        """Get user's portfolio"""
        try:
            if supabase is None:
                return []
            result = supabase.table('portfolio').select('*').eq('user_id', user_id).execute()
            return result.data if result.data else []
        except:
            return []
    
    @staticmethod
    def add_portfolio_position(user_id: str, ticker: str, shares: float, 
                             avg_price: float, purchase_date: str) -> bool:
        """Add or update portfolio position"""
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
            
        except Exception as e:
            st.error(f"Failed to add position: {e}")
            return False
    
    @staticmethod
    def remove_portfolio_position(user_id: str, ticker: str) -> bool:
        """Remove position from portfolio"""
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
    """Advanced technical analysis and indicator calculations"""
    
    @staticmethod
    def calculate_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
        """Calculate comprehensive technical indicators"""
        try:
            # RSI (Relative Strength Index)
            delta = df['Close'].diff()
            gain = delta.where(delta > 0, 0).rolling(window=14).mean()
            loss = -delta.where(delta < 0, 0).rolling(window=14).mean()
            rs = gain / loss
            df['RSI'] = 100 - (100 / (1 + rs))
            
            # MACD (Moving Average Convergence Divergence)
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
                df[f'SMA{period}'] = df['Close'].rolling(window=period).mean()
                df[f'EMA{period}'] = df['Close'].ewm(span=period, adjust=False).mean()
            
            # ATR (Average True Range)
            high_low = df['High'] - df['Low']
            high_close = abs(df['High'] - df['Close'].shift())
            low_close = abs(df['Low'] - df['Close'].shift())
            ranges = pd.concat([high_low, high_close, low_close], axis=1)
            true_range = ranges.max(axis=1)
            df['ATR'] = true_range.rolling(14).mean()
            
            # Volume Indicators
            df['Volume_SMA'] = df['Volume'].rolling(20).mean()
            df['Volume_Ratio'] = df['Volume'] / df['Volume_SMA']
            
            # Stochastic Oscillator
            low_14 = df['Low'].rolling(14).min()
            high_14 = df['High'].rolling(14).max()
            df['Stoch_K'] = 100 * ((df['Close'] - low_14) / (high_14 - low_14))
            df['Stoch_D'] = df['Stoch_K'].rolling(3).mean()
            
            # OBV (On-Balance Volume)
            df['OBV'] = (np.sign(df['Close'].diff()) * df['Volume']).fillna(0).cumsum()
            
            # Momentum
            df['Momentum'] = df['Close'].diff(10)
            
            # Rate of Change
            df['ROC'] = ((df['Close'] - df['Close'].shift(10)) / df['Close'].shift(10)) * 100
            
            return df
            
        except Exception as e:
            st.error(f"Technical analysis error: {e}")
            return df
    
    @staticmethod
    def calculate_ai_score(df: pd.DataFrame, info: Dict) -> Dict:
        """Calculate AI-based stock score with detailed breakdown"""
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
                    signals.append(("RSI Neutral Zone", "positive"))
                elif rsi < 30:
                    score += 10
                    signals.append(("RSI Oversold", "positive"))
                elif 30 <= rsi < 40:
                    score += 8
                    signals.append(("RSI Approaching Oversold", "neutral"))
                elif rsi > 70:
                    score += 5
                    signals.append(("RSI Overbought", "negative"))
                else:
                    score += 7
                    signals.append(("RSI Moderate", "neutral"))
            
            # MACD Analysis
            if pd.notna(latest['MACD']) and pd.notna(latest['MACD_Signal']):
                if latest['MACD'] > latest['MACD_Signal']:
                    score += 15
                    signals.append(("MACD Bullish", "positive"))
                elif latest['MACD_Histogram'] > 0:
                    score += 10
                    signals.append(("MACD Positive Histogram", "positive"))
                else:
                    score += 5
                    signals.append(("MACD Bearish", "negative"))
            
            # Moving Average Trend
            if pd.notna(latest['SMA50']) and pd.notna(latest['SMA200']):
                if price > latest['SMA50'] > latest['SMA200']:
                    score += 20
                    signals.append(("Strong Uptrend", "positive"))
                elif price > latest['SMA50']:
                    score += 12
                    signals.append(("Uptrend", "positive"))
                elif price > latest['SMA200']:
                    score += 8
                    signals.append(("Long-term Uptrend", "neutral"))
                else:
                    score += 4
                    signals.append(("Downtrend", "negative"))
            
            # Fundamental Analysis (50 points)
            pe = info.get('trailingPE')
            if pe and pd.notna(pe):
                if 10 <= pe <= 25:
                    score += 15
                    signals.append(("Healthy P/E Ratio", "positive"))
                elif 5 <= pe < 10:
                    score += 10
                    signals.append(("Low P/E - Value Play", "positive"))
                elif 25 < pe <= 35:
                    score += 8
                    signals.append(("Moderate P/E", "neutral"))
                else:
                    score += 5
                    signals.append(("High P/E", "negative"))
            
            profit_margin = info.get('profitMargins')
            if profit_margin and pd.notna(profit_margin):
                if profit_margin > 0.20:
                    score += 15
                    signals.append(("Excellent Margins", "positive"))
                elif profit_margin > 0.15:
                    score += 12
                    signals.append(("Strong Margins", "positive"))
                elif profit_margin > 0.10:
                    score += 8
                    signals.append(("Good Margins", "neutral"))
                else:
                    score += 5
                    signals.append(("Weak Margins", "negative"))
            
            roe = info.get('returnOnEquity')
            if roe and pd.notna(roe):
                if roe > 0.20:
                    score += 20
                    signals.append(("Outstanding ROE", "positive"))
                elif roe > 0.15:
                    score += 15
                    signals.append(("Excellent ROE", "positive"))
                elif roe > 0.10:
                    score += 10
                    signals.append(("Good ROE", "neutral"))
                else:
                    score += 5
                    signals.append(("Low ROE", "negative"))
            
        except Exception as e:
            signals.append((f"Analysis Error: {str(e)}", "neutral"))
        
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
    
    @staticmethod
    def detect_chart_patterns(df: pd.DataFrame) -> List[Tuple[str, str]]:
        """Detect common chart patterns"""
        patterns = []
        
        try:
            recent = df.tail(20)
            
            if len(recent) >= 2:
                if recent['SMA50'].iloc[-1] > recent['SMA200'].iloc[-1] and \
                   recent['SMA50'].iloc[-2] <= recent['SMA200'].iloc[-2]:
                    patterns.append(("Golden Cross Detected", "bullish"))
            
            if len(recent) >= 2:
                if recent['SMA50'].iloc[-1] < recent['SMA200'].iloc[-1] and \
                   recent['SMA50'].iloc[-2] >= recent['SMA200'].iloc[-2]:
                    patterns.append(("Death Cross Detected", "bearish"))
            
            if recent['BB_Width'].iloc[-1] < recent['BB_Width'].mean() * 0.5:
                patterns.append(("Bollinger Squeeze - Breakout Pending", "neutral"))
            
            if recent['Close'].iloc[-1] > recent['High'].iloc[-10:-1].max():
                patterns.append(("Breakout Above Resistance", "bullish"))
            
            if recent['Close'].iloc[-1] < recent['Low'].iloc[-10:-1].min():
                patterns.append(("Breakdown Below Support", "bearish"))
            
        except:
            pass
        
        return patterns

# =============================================================================
# POSITION SIZING ENGINE
# =============================================================================

class PositionSizingEngine:
    """Advanced position sizing and risk management"""
    
    @staticmethod
    def calculate_position_size(account_size: float, stock_price: float, 
                               volatility: float, method: str = 'kelly',
                               risk_per_trade: float = 0.02,
                               win_rate: float = 0.55,
                               avg_win: float = 2.0,
                               avg_loss: float = 1.0) -> Dict:
        """Calculate optimal position size using multiple methods"""
        results = {}
        
        try:
            # Kelly Criterion
            if method in ['kelly', 'all']:
                q = 1 - win_rate
                b = avg_win / avg_loss
                kelly_pct = (win_rate * b - q) / b
                kelly_pct = max(0, min(kelly_pct * 0.5, 0.25))
                kelly_shares = int((account_size * kelly_pct) / stock_price)
                
                results['kelly'] = {
                    'shares': kelly_shares,
                    'position_value': kelly_shares * stock_price,
                    'position_pct': kelly_pct * 100,
                    'description': 'Optimal growth sizing based on edge'
                }
            
            # Fixed Risk
            if method in ['fixed', 'all']:
                risk_amount = account_size * risk_per_trade
                fixed_shares = int(risk_amount / stock_price)
                
                results['fixed'] = {
                    'shares': fixed_shares,
                    'position_value': fixed_shares * stock_price,
                    'position_pct': (fixed_shares * stock_price / account_size) * 100,
                    'description': 'Fixed percentage of account'
                }
            
            # Volatility-Based
            if method in ['volatility', 'all']:
                target_risk = account_size * risk_per_trade
                vol_shares = int(target_risk / (volatility * stock_price))
                
                results['volatility'] = {
                    'shares': vol_shares,
                    'position_value': vol_shares * stock_price,
                    'position_pct': (vol_shares * stock_price / account_size) * 100,
                    'description': 'Adjusted for stock volatility'
                }
            
        except Exception as e:
            st.error(f"Position sizing error: {e}")
        
        return results
    
    @staticmethod
    def calculate_stop_loss_take_profit(entry_price: float, atr: float,
                                        risk_reward_ratio: float = 2.0) -> Dict:
        """Calculate stop loss and take profit levels"""
        try:
            stop_loss = entry_price - (2 * atr)
            risk_per_share = entry_price - stop_loss
            reward_per_share = risk_per_share * risk_reward_ratio
            take_profit = entry_price + reward_per_share
            
            return {
                'entry_price': entry_price,
                'stop_loss': stop_loss,
                'take_profit': take_profit,
                'risk_per_share': risk_per_share,
                'reward_per_share': reward_per_share,
                'risk_reward_ratio': risk_reward_ratio,
                'stop_loss_pct': ((entry_price - stop_loss) / entry_price) * 100,
                'take_profit_pct': ((take_profit - entry_price) / entry_price) * 100
            }
            
        except Exception as e:
            st.error(f"Stop loss calculation error: {e}")
            return None

# =============================================================================
# TRADING STRATEGY ENGINE
# =============================================================================

class AdvancedTradingStrategy:
    """Sophisticated multi-factor trading strategy"""
    
    @staticmethod
    def generate_trading_signals(df: pd.DataFrame) -> pd.DataFrame:
        """Generate advanced trading signals using multiple factors"""
        df['Signal'] = 0
        df['Signal_Strength'] = 0
        df['Entry_Reason'] = ''
        
        for i in range(50, len(df)):
            strength = 0
            reasons = []
            
            try:
                if (df['MACD'].iloc[i] > df['MACD_Signal'].iloc[i] and
                    df['MACD'].iloc[i-1] <= df['MACD_Signal'].iloc[i-1] and
                    30 < df['RSI'].iloc[i] < 70):
                    strength += 3
                    reasons.append("MACD Bullish Cross")
                
                if (df['Close'].iloc[i] > df['SMA20'].iloc[i] > 
                    df['SMA50'].iloc[i] > df['SMA200'].iloc[i]):
                    strength += 4
                    reasons.append("MA Uptrend Alignment")
                
                if df['Volume_Ratio'].iloc[i] > 1.5:
                    strength += 2
                    reasons.append("High Volume")
                
                if (df['BB_Width'].iloc[i] < df['BB_Width'].iloc[i-10:i].mean() * 0.7 and
                    df['Close'].iloc[i] > df['BB_Upper'].iloc[i]):
                    strength += 3
                    reasons.append("BB Breakout")
                
                if (df['Stoch_K'].iloc[i-1] < 20 and 
                    df['Stoch_K'].iloc[i] > 20):
                    strength += 2
                    reasons.append("Stoch Oversold Recovery")
                
                if df['Momentum'].iloc[i] > 0:
                    strength += 1
                    reasons.append("Positive Momentum")
                
                if strength >= 5:
                    df.loc[df.index[i], 'Signal'] = 1
                    df.loc[df.index[i], 'Signal_Strength'] = strength
                    df.loc[df.index[i], 'Entry_Reason'] = ', '.join(reasons)
                
                elif ((df['MACD'].iloc[i] < df['MACD_Signal'].iloc[i] and
                       df['MACD'].iloc[i-1] >= df['MACD_Signal'].iloc[i-1]) or
                      df['RSI'].iloc[i] > 80 or
                      (df['Close'].iloc[i] < df['SMA50'].iloc[i] and
                       df['Close'].iloc[i-1] >= df['SMA50'].iloc[i-1])):
                    df.loc[df.index[i], 'Signal'] = -1
                    df.loc[df.index[i], 'Entry_Reason'] = "Exit Signal"
                    
            except:
                continue
        
        return df
    
    @staticmethod
    def run_advanced_backtest(ticker: str, start_date, end_date,
                             initial_capital: float = 10000,
                             risk_per_trade: float = 0.02,
                             risk_reward_ratio: float = 2.0) -> Optional[Dict]:
        """Run comprehensive backtest with advanced risk management"""
        try:
            stock = yf.Ticker(ticker)
            df = stock.history(start=start_date, end=end_date)
            
            if df.empty:
                return None
            
            df = TechnicalAnalysisEngine.calculate_all_indicators(df)
            df = AdvancedTradingStrategy.generate_trading_signals(df)
            
            cash = initial_capital
            position = 0
            entry_price = 0
            stop_loss = 0
            take_profit = 0
            trades = []
            equity_curve = []
            
            for i in range(len(df)):
                current_price = df['Close'].iloc[i]
                signal = df['Signal'].iloc[i]
                
                if position > 0:
                    if current_price <= stop_loss:
                        pnl = position * (stop_loss - entry_price)
                        cash += position * stop_loss
                        trades.append({
                            'entry': entry_price,
                            'exit': stop_loss,
                            'pnl': pnl,
                            'type': 'stop_loss',
                            'date': df.index[i]
                        })
                        position = 0
                    
                    elif current_price >= take_profit:
                        pnl = position * (take_profit - entry_price)
                        cash += position * take_profit
                        trades.append({
                            'entry': entry_price,
                            'exit': take_profit,
                            'pnl': pnl,
                            'type': 'take_profit',
                            'date': df.index[i]
                        })
                        position = 0
                    
                    elif signal == -1:
                        pnl = position * (current_price - entry_price)
                        cash += position * current_price
                        trades.append({
                            'entry': entry_price,
                            'exit': current_price,
                            'pnl': pnl,
                            'type': 'signal_exit',
                            'date': df.index[i]
                        })
                        position = 0
                
                if signal == 1 and position == 0:
                    atr = df['ATR'].iloc[i]
                    volatility = df['Close'].iloc[i-20:i].pct_change().std() if i >= 20 else 0.02
                    
                    size_info = PositionSizingEngine.calculate_position_size(
                        cash, current_price, volatility, 'kelly', risk_per_trade
                    )
                    
                    shares = size_info['kelly']['shares']
                    
                    if shares > 0 and shares * current_price <= cash:
                        stops = PositionSizingEngine.calculate_stop_loss_take_profit(
                            current_price, atr, risk_reward_ratio
                        )
                        
                        if stops:
                            position = shares
                            entry_price = current_price
                            stop_loss = stops['stop_loss']
                            take_profit = stops['take_profit']
                            cash -= shares * current_price
                
                total_equity = cash + (position * current_price if position > 0 else 0)
                equity_curve.append(total_equity)
            
            if position > 0:
                pnl = position * (df['Close'].iloc[-1] - entry_price)
                cash += position * df['Close'].iloc[-1]
                trades.append({
                    'entry': entry_price,
                    'exit': df['Close'].iloc[-1],
                    'pnl': pnl,
                    'type': 'final_exit',
                    'date': df.index[-1]
                })
            
            final_equity = cash
            total_return = ((final_equity - initial_capital) / initial_capital) * 100
            
            winning_trades = [t for t in trades if t['pnl'] > 0]
            losing_trades = [t for t in trades if t['pnl'] <= 0]
            
            win_rate = (len(winning_trades) / len(trades) * 100) if trades else 0
            avg_win = np.mean([t['pnl'] for t in winning_trades]) if winning_trades else 0
            avg_loss = np.mean([abs(t['pnl']) for t in losing_trades]) if losing_trades else 0
            
            profit_factor = (sum([t['pnl'] for t in winning_trades]) /
                           sum([abs(t['pnl']) for t in losing_trades])) if losing_trades and sum([abs(t['pnl']) for t in losing_trades]) > 0 else 0
            
            buy_hold_return = ((df['Close'].iloc[-1] - df['Close'].iloc[0]) / df['Close'].iloc[0]) * 100
            
            returns = pd.Series(equity_curve).pct_change()
            sharpe = np.sqrt(252) * returns.mean() / returns.std() if returns.std() > 0 else 0
            
            equity_series = pd.Series(equity_curve)
            running_max = equity_series.expanding().max()
            drawdown = (equity_series - running_max) / running_max
            max_drawdown = drawdown.min() * 100
            
            return {
                'df': df,
                'trades': trades,
                'equity_curve': equity_curve,
                'total_return': total_return,
                'buy_hold_return': buy_hold_return,
                'alpha': total_return - buy_hold_return,
                'num_trades': len(trades),
                'win_rate': win_rate,
                'avg_win': avg_win,
                'avg_loss': avg_loss,
                'profit_factor': profit_factor,
                'sharpe_ratio': sharpe,
                'max_drawdown': max_drawdown,
                'final_equity': final_equity,
                'winning_trades': len(winning_trades),
                'losing_trades': len(losing_trades)
            }
            
        except Exception as e:
            st.error(f"Backtest error: {e}")
            return None

# =============================================================================
# STOCK SCREENER ENGINE
# =============================================================================

class StockScreener:
    """Advanced stock screening with multiple criteria"""
    
    @staticmethod
    def get_stock_universe() -> List[str]:
        """Get list of stocks to screen"""
        return [
            'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'NVDA', 'TSLA', 'AMD', 'INTC', 'NFLX',
            'ADBE', 'CRM', 'ORCL', 'CSCO', 'QCOM', 'AVGO', 'TXN', 'SNOW', 'SHOP', 'SQ',
            'UBER', 'LYFT', 'TWLO', 'DDOG', 'NET', 'CRWD', 'ZM', 'DOCU', 'OKTA', 'MDB',
            'JPM', 'BAC', 'WFC', 'GS', 'MS', 'C', 'BLK', 'SCHW', 'AXP', 'V',
            'MA', 'PYPL', 'COIN', 'SOFI', 'HOOD', 'AFRM', 'NU', 'UPST', 'LC', 'JNJ',
            'UNH', 'PFE', 'ABBV', 'TMO', 'ABT', 'DHR', 'LLY', 'MRK', 'CVS', 'GILD',
            'AMGN', 'VRTX', 'REGN', 'BIIB', 'ILMN', 'MRNA', 'BNTX', 'EXAS', 'TDOC', 'WMT',
            'HD', 'NKE', 'SBUX', 'MCD', 'COST', 'TGT', 'LOW', 'DIS', 'CMCSA', 'KO',
            'PEP', 'PM', 'MO', 'EL', 'CLX', 'PG', 'KMB', 'CL', 'CHD', 'XOM',
            'CVX', 'COP', 'SLB', 'EOG', 'MPC', 'PSX', 'VLO', 'OXY', 'HAL', 'BA',
            'CAT', 'GE', 'HON', 'UNP', 'UPS', 'RTX', 'LMT', 'DE', 'MMM'
        ]
    
    @staticmethod
    def screen_stocks(criteria: Dict, progress_callback=None) -> pd.DataFrame:
        """Screen stocks based on multiple criteria"""
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
                
                hist = TechnicalAnalysisEngine.calculate_all_indicators(hist)
                
                price = hist['Close'].iloc[-1]
                rsi = hist['RSI'].iloc[-1] if 'RSI' in hist.columns else 0
                pe_ratio = info.get('trailingPE', 0)
                market_cap = info.get('marketCap', 0)
                dividend_yield = info.get('dividendYield', 0) or 0
                profit_margin = info.get('profitMargins', 0) or 0
                
                change_6m = ((price - hist['Close'].iloc[0]) / hist['Close'].iloc[0]) * 100
                
                passes = True
                
                if criteria.get('min_price') and price < criteria['min_price']:
                    passes = False
                if criteria.get('max_price') and price > criteria['max_price']:
                    passes = False
                if criteria.get('min_rsi') and rsi < criteria['min_rsi']:
                    passes = False
                if criteria.get('max_rsi') and rsi > criteria['max_rsi']:
                    passes = False
                if criteria.get('min_pe') and pe_ratio and pe_ratio < criteria['min_pe']:
                    passes = False
                if criteria.get('max_pe') and pe_ratio and pe_ratio > criteria['max_pe']:
                    passes = False
                if criteria.get('min_market_cap') and market_cap < criteria['min_market_cap'] * 1e9:
                    passes = False
                if criteria.get('min_dividend') and dividend_yield < criteria['min_dividend'] / 100:
                    passes = False
                if criteria.get('min_profit_margin') and profit_margin < criteria['min_profit_margin'] / 100:
                    passes = False
                
                if passes:
                    ai_analysis = TechnicalAnalysisEngine.calculate_ai_score(hist, info)
                    
                    results.append({
                        'Ticker': ticker,
                        'Name': info.get('shortName', ticker)[:30],
                        'Price': price,
                        'Change_6M': change_6m,
                        'RSI': rsi,
                        'PE': pe_ratio if pe_ratio else 0,
                        'Market_Cap_B': market_cap / 1e9 if market_cap else 0,
                        'Dividend': dividend_yield * 100,
                        'Profit_Margin': profit_margin * 100,
                        'AI_Score': ai_analysis['score'],
                        'Rating': ai_analysis['rating']
                    })
                    
            except Exception as e:
                continue
        
        if progress_callback:
            progress_callback(1.0)
        
        return pd.DataFrame(results) if results else pd.DataFrame()

# =============================================================================
# PREDICTION ENGINE
# =============================================================================

class PredictionEngine:
    """AI-powered price prediction"""
    
    @staticmethod
    def predict_price(df: pd.DataFrame, days: int = 30) -> Optional[Dict]:
        """Predict future price using linear regression with momentum"""
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
            
            momentum = (df['Close'].iloc[-1] - df['Close'].iloc[-30]) / df['Close'].iloc[-30]
            adjusted_slope = slope * (1 + momentum * 0.3)
            
            future_days = range(len(recent), len(recent) + days)
            predictions = [max(0, adjusted_slope * day + intercept) for day in future_days]
            
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
# PERFORMANCE ANALYTICS
# =============================================================================

class PerformanceAnalytics:
    """Portfolio performance and risk analytics"""
    
    @staticmethod
    def calculate_portfolio_metrics(portfolio: List[Dict]) -> Dict:
        """Calculate comprehensive portfolio metrics"""
        try:
            total_invested = 0
            total_current = 0
            positions_data = []
            
            for position in portfolio:
                ticker = position['ticker']
                shares = position['shares']
                avg_price = position['average_price']
                
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
                        'invested': invested,
                        'current': current_value,
                        'pnl': pnl,
                        'pnl_pct': pnl_pct
                    })
                except:
                    continue
            
            total_pnl = total_current - total_invested
            total_pnl_pct = (total_pnl / total_invested * 100) if total_invested > 0 else 0
            
            return {
                'total_invested': total_invested,
                'total_current': total_current,
                'total_pnl': total_pnl,
                'total_pnl_pct': total_pnl_pct,
                'positions': positions_data,
                'num_positions': len(positions_data)
            }
            
        except:
            return {
                'total_invested': 0,
