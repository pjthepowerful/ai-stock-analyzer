# =============================================================================
# RUN THE APPLICATION
# =============================================================================

# Initialize session state defaults
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'user' not in st.session_state:
    st.session_state.user = None
if 'profile' not in st.session_state:
    st.session_state.profile = None
if 'page' not in st.session_state:
    st.session_state.page = 'home'
if 'beginner_mode' not in st.session_state:
    st.session_state.beginner_mode = True
if 'onboarding_complete' not in st.session_state:
    st.session_state.onboarding_complete = False
if 'onboarding_step' not in st.session_state:
    st.session_state.onboarding_step = 0
if 'show_onboarding' not in st.session_state:
    st.session_state.show_onboarding = True
if 'demo_ticker' not in st.session_state:
    st.session_state.demo_ticker = 'AAPL'

# Check authentication
if not st.session_state.authenticated:
    render_auth_page()
    st.stop()

# Check if onboarding needed
if st.session_state.show_onboarding and not st.session_state.onboarding_complete:
    render_onboarding()
    st.stop()

# Get user profile
profile = st.session_state.profile or {}
is_premium = profile.get('is_premium', False)

# Render sidebar
render_sidebar(is_premium)

# Route to appropriate page
current_page = st.session_state.page

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
