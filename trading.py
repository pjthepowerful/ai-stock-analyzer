import streamlit as st
import time
import json
import os

SAVE_FILE = "countdown_data.json"
TOTAL_TIME = 120  # ⏰ how long the app stays down (in seconds)

def save_remaining_time(remaining):
    with open(SAVE_FILE, "w") as f:
        json.dump({"remaining_time": remaining, "last_update": time.time()}, f)

def load_remaining_time():
    # if save file exists, adjust for elapsed time since last update
    if os.path.exists(SAVE_FILE):
        with open(SAVE_FILE, "r") as f:
            data = json.load(f)
        remaining = data.get("remaining_time", TOTAL_TIME)
        elapsed = time.time() - data.get("last_update", time.time())
        remaining = max(0, remaining - int(elapsed))
        return remaining
    return TOTAL_TIME

def main():
    st.title("🚧 App Maintenance Mode")

    remaining = load_remaining_time()

    if remaining > 0:
        st.warning("The app is currently down for maintenance.")
        mins, secs = divmod(remaining, 60)
        st.subheader(f"⏳ Time Remaining: {mins:02d}:{secs:02d}")

        # update saved time
        save_remaining_time(remaining - 1)

        # auto-refresh every second
        st.session_state["_refresh"] = time.time()
        st_autorefresh(interval=1000, key="down_timer")  # refresh every 1s
    else:
        # cleanup
        if os.path.exists(SAVE_FILE):
            os.remove(SAVE_FILE)
        st.success("✅ The app is now back online!")

# this is needed for st_autorefresh
from streamlit_autorefresh import st_autorefresh

if __name__ == "__main__":
    main()
