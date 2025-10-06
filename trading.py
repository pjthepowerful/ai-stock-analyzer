import streamlit as st
from datetime import datetime, timedelta
import time

# Page configuration
st.set_page_config(
    page_title="Maintenance Mode",
    page_icon="🔧",
    layout="centered"
)

# Custom CSS for styling
st.markdown("""
    <style>
    .main {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    }
    .maintenance-container {
        text-align: center;
        padding: 2rem;
        background: white;
        border-radius: 20px;
        box-shadow: 0 10px 40px rgba(0,0,0,0.2);
        margin: 2rem auto;
    }
    .countdown {
        font-size: 3rem;
        font-weight: bold;
        color: #667eea;
        margin: 2rem 0;
        font-family: 'Courier New', monospace;
    }
    .countdown-unit {
        display: inline-block;
        margin: 0 1rem;
    }
    .countdown-number {
        font-size: 4rem;
        display: block;
        color: #667eea;
    }
    .countdown-label {
        font-size: 1rem;
        color: #666;
        text-transform: uppercase;
        letter-spacing: 2px;
    }
    .maintenance-icon {
        font-size: 5rem;
        margin: 1rem 0;
    }
    </style>
""", unsafe_allow_html=True)

# Initialize session state for the end time if not exists
if 'maintenance_end' not in st.session_state:
    # Set your maintenance end time here
    # Example: maintenance ends in 2 hours from now
    st.session_state.maintenance_end = datetime.now() + timedelta(hours=2, minutes=30)
    
    # You can also set a specific date/time:
    # st.session_state.maintenance_end = datetime(2025, 10, 6, 18, 0, 0)

MAINTENANCE_END = st.session_state.maintenance_end

def get_time_remaining():
    """Calculate time remaining until maintenance ends"""
    now = datetime.now()
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

# Main content
st.markdown('<div class="maintenance-container">', unsafe_allow_html=True)

# Icon
st.markdown('<div class="maintenance-icon">🔧</div>', unsafe_allow_html=True)

# Title
st.title("🚧 System Maintenance")

# Description
st.markdown("""
### We'll be back soon!

We're currently performing scheduled maintenance to improve your experience.
Thank you for your patience.
""")

# Get time remaining
time_left = get_time_remaining()

if time_left is None:
    st.markdown(
        '<div class="countdown">✅ Maintenance Complete!</div>',
        unsafe_allow_html=True
    )
    st.success("System is now online. Please refresh the page.")
    st.progress(1.0)
else:
    # Display countdown with styled boxes
    st.markdown(f"""
        <div class="countdown">
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
    
    # Status message
    if time_left['days'] > 0:
        st.info(f"⏱️ Estimated completion: {time_left['days']} days, {time_left['hours']} hours")
    elif time_left['hours'] > 0:
        st.info(f"⏱️ Estimated completion: {time_left['hours']} hours, {time_left['minutes']} minutes")
    else:
        st.warning(f"⏱️ Almost done: {time_left['minutes']} minutes, {time_left['seconds']} seconds")
    
    # Update progress bar (inverse progress - starts at 100% and goes down)
    total_maintenance_seconds = 2.5 * 3600  # 2.5 hours in seconds
    progress = max(0, (time_left['total_seconds'] / total_maintenance_seconds))
    st.progress(1.0 - progress)

# Information
with st.expander("ℹ️ What's happening?"):
    st.write("""
    - **Database optimization** - Improving performance
    - **Security updates** - Keeping your data safe
    - **New features** - Adding exciting functionality
    """)

st.markdown('</div>', unsafe_allow_html=True)

# Auto-refresh every second
time.sleep(1)
st.rerun()
