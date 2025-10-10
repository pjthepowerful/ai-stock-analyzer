import streamlit as st
from datetime import datetime, timedelta
import time
import pytz

# ============================================
# MAINTENANCE END TIME - CHANGE THIS!
# ============================================
CST = pytz.timezone('America/Chicago')
MAINTENANCE_END = CST.localize(datetime(2025, 10, 10, 22, 0, 0))
# ============================================

# Page configuration
st.set_page_config(
    page_title="We'll Be Right Back! 🚀",
    page_icon="🛠️",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# Custom CSS for smooth, modern design
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap');
    
    .main {
        background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 50%, #d946ef 100%);
        font-family: 'Inter', sans-serif;
    }
    
    .maintenance-container {
        text-align: center;
        padding: 1rem 2rem 3rem;
        margin: 0 auto;
        max-width: 700px;
    }
    
    .maintenance-icon {
        font-size: 6rem;
        margin: 1rem 0;
        display: inline-block;
    }
    
    .main-title {
        font-size: 2.5rem;
        font-weight: 800;
        color: white;
        margin: 0 0 1rem 0;
        padding-top: 0;
        line-height: 1.2;
        text-shadow: 0 2px 10px rgba(0, 0, 0, 0.2);
    }
    
    .subtitle {
        font-size: 1.2rem;
        color: rgba(255, 255, 255, 0.95);
        margin: 1rem 0 2rem;
        font-weight: 400;
        line-height: 1.6;
    }
    
    .countdown-container {
        display: flex;
        justify-content: center;
        gap: 1.5rem;
        margin: 2.5rem 0;
        flex-wrap: wrap;
    }
    
    .countdown-unit {
        background: rgba(255, 255, 255, 0.15);
        backdrop-filter: blur(10px);
        border-radius: 20px;
        padding: 1.5rem 1.2rem;
        min-width: 100px;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
        border: 2px solid rgba(255, 255, 255, 0.2);
    }
    
    .countdown-number {
        font-size: 3.5rem;
        font-weight: 800;
        display: block;
        color: white;
        line-height: 1;
        margin-bottom: 0.5rem;
        text-shadow: 0 2px 10px rgba(0, 0, 0, 0.3);
    }
    
    .countdown-label {
        font-size: 0.875rem;
        color: rgba(255, 255, 255, 0.9);
        text-transform: uppercase;
        letter-spacing: 1px;
        font-weight: 600;
    }
    
    .status-badge {
        display: inline-block;
        padding: 0.75rem 1.5rem;
        background: linear-gradient(135deg, #fef3c7, #fde68a);
        border-radius: 50px;
        font-size: 0.95rem;
        font-weight: 600;
        color: #92400e;
        margin: 1rem 0;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    }
    
    .status-badge-success {
        background: linear-gradient(135deg, #d1fae5, #a7f3d0);
        color: #065f46;
    }
    
    .progress-container {
        margin: 2rem 0;
        padding: 0 1rem;
    }
    
    .fun-facts {
        background: transparent;
        border-radius: 16px;
        padding: 1.5rem;
        margin: 2rem 0;
        border: none;
    }
    
    .fun-facts h4 {
        color: white;
        font-weight: 700;
        margin-bottom: 1rem;
        font-size: 1.1rem;
    }
    
    .fun-facts ul {
        text-align: left;
        color: rgba(255, 255, 255, 0.9);
        line-height: 1.8;
    }
    
    .fun-facts li {
        margin: 0.5rem 0;
    }
    
    /* Hide Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* Improve Streamlit elements */
    .stProgress > div > div > div > div {
        background: linear-gradient(90deg, #6366f1, #8b5cf6, #d946ef);
        border-radius: 10px;
        height: 12px;
    }
    
    .stExpander {
        border: 2px solid rgba(255, 255, 255, 0.2);
        border-radius: 16px;
        background: rgba(0, 0, 0, 0.4);
        backdrop-filter: blur(10px);
    }
    </style>
""", unsafe_allow_html=True)

def get_time_remaining():
    """Calculate time remaining until maintenance ends"""
    now = datetime.now(CST)
    remaining = MAINTENANCE_END - now
    
    if remaining.total_seconds() <= 0:
        return None
    
    days = remaining.days
    hours, remainder = divmod(remaining.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    
    return {
        'days': days,
        'hours': hours,
        'minutes': minutes,
        'seconds': seconds,
        'total_seconds': remaining.total_seconds()
    }

# Fun messages based on time remaining
def get_fun_message(time_left):
    if time_left is None:
        return "🎉 We're back, baby!"
    elif time_left['total_seconds'] < 300:  # Less than 5 minutes
        return "⚡ Almost there! Grab a coffee, we're in the final stretch!"
    elif time_left['total_seconds'] < 1800:  # Less than 30 minutes
        return "🚀 Finishing touches being applied... greatness incoming!"
    elif time_left['hours'] < 1:
        return "⏰ Shouldn't be long now! Perfect time for a quick snack break!"
    elif time_left['hours'] < 3:
        return "🛠️ Our digital elves are working their magic!"
    else:
        return "🎨 Taking our time to make everything perfect for you!"

# Main content
st.markdown('<div class="maintenance-container">', unsafe_allow_html=True)

# Title and subtitle
st.markdown('<h1 class="main-title">We\'re making your money moves more awesome!</h1>', unsafe_allow_html=True)
st.markdown('<p class="subtitle">Brief tune-up in progress — we\'ll be back before the next market move.</p>', unsafe_allow_html=True)

# Get time remaining
time_left = get_time_remaining()

# Fun message
fun_message = get_fun_message(time_left)

if time_left is None:
    st.markdown(
        '<div class="status-badge status-badge-success">✅ We\'re Back Online!</div>',
        unsafe_allow_html=True
    )
    st.balloons()
    st.success("🎊 Maintenance complete! Hit that refresh button and let's get back to business!")
    st.progress(1.0)
else:
    # Status badge with fun message
    st.markdown(f'<div class="status-badge">{fun_message}</div>', unsafe_allow_html=True)
    
    # Countdown timer
    st.markdown(f"""
        <div class="countdown-container">
            <div class="countdown-unit">
                <span class="countdown-number">{time_left['days']:02d}</span>
                <span class="countdown-label">Days</span>
            </div>
            <div class="countdown-unit">
                <span class="countdown-number">{time_left['hours']:02d}</span>
                <span class="countdown-label">Hours</span>
            </div>
            <div class="countdown-unit">
                <span class="countdown-number">{time_left['minutes']:02d}</span>
                <span class="countdown-label">Minutes</span>
            </div>
            <div class="countdown-unit">
                <span class="countdown-number">{time_left['seconds']:02d}</span>
                <span class="countdown-label">Seconds</span>
            </div>
        </div>
    """, unsafe_allow_html=True)
    
    # Progress bar
    total_maintenance_seconds = 2.5 * 3600
    progress = max(0.0, min(1.0, (time_left['total_seconds'] / total_maintenance_seconds)))
    st.markdown('<div class="progress-container">', unsafe_allow_html=True)
    st.progress(max(0.01, min(1.0, 1.0 - progress)))
    st.markdown('</div>', unsafe_allow_html=True)

# What's happening section
with st.expander("🎯 What's Being Upgraded?"):
    st.markdown("""
    <div class="fun-facts">
        <ul>
            <li>🎨 <b>Sleeker Interface</b> - Making everything prettier and easier to navigate</li>
            <li>🧠 <b>Smarter Tools</b> - New algorithms to help you make better money moves</li>
            <li>⚡ <b>Faster Performance</b> - Because waiting is so last season</li>
            <li>🔒 <b>Enhanced Security</b> - Your data is getting an extra layer of protection</li>
            <li>🎉 <b>Surprise Features</b> - We've got some goodies we can't wait to show you!</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)

# Fun facts while you wait
with st.expander("💡 Did You Know? (Fun Facts While You Wait)"):
    st.markdown("""
    <div class="fun-facts">
        <ul>
            <li>☕ The average person spends 1 year of their life waiting for web pages to load</li>
            <li>🎵 Spotify has over 100 million songs. You could listen for 247 years straight!</li>
            <li>🚀 NASA's internet speed is 91 GB/s. This maintenance would take 0.001 seconds there</li>
            <li>🐝 A honey bee visits about 2,000 flowers per day. Talk about productivity!</li>
            <li>💪 You're doing great! Thanks for your patience while we level up! 🙌</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)

st.markdown('</div>', unsafe_allow_html=True)

# Footer message
st.markdown("""
    <div style="text-align: center; margin-top: 2rem; color: white; font-size: 0.9rem;">
        <p>Questions? Concerns? Just want to chat? <br>
        Reach out to our support team - we're always here! 💬</p>
    </div>
""", unsafe_allow_html=True)

# Auto-refresh
time.sleep(1)
st.rerun()
