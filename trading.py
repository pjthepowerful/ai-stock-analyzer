import streamlit as st
import time
import json
import os

SAVE_FILE = "countdown_data.json"

def save_remaining_time(remaining):
    with open(SAVE_FILE, "w") as f:
        json.dump({"remaining_time": remaining}, f)

def load_remaining_time(default_time):
    if os.path.exists(SAVE_FILE):
        with open(SAVE_FILE, "r") as f:
            data = json.load(f)
            return data.get("remaining_time", default_time)
    return default_time

def countdown(total_seconds):
    remaining = load_remaining_time(total_seconds)
    st.title("🚧 App Maintenance Mode")
    st.write("The app will be down for the remaining countdown time below.")

    countdown_placeholder = st.empty()

    while remaining > 0:
        mins, secs = divmod(remaining, 60)
        countdown_placeholder.subheader(f"⏳ Time Remaining: {mins:02d}:{secs:02d}")
        time.sleep(1)
        remaining -= 1
        save_remaining_time(remaining)
        st.experimental_rerun()

    # When done
    if os.path.exists(SAVE_FILE):
        os.remove(SAVE_FILE)
    st.success("✅ The app is now back online!")

def main():
    total_time = st.number_input("Enter downtime (seconds):", min_value=1, value=60)
    if st.button("Start Countdown"):
        countdown(int(total_time))

    if os.path.exists(SAVE_FILE):
        with open(SAVE_FILE, "r") as f:
            data = json.load(f)
            remaining = data.get("remaining_time", 0)
            if remaining > 0:
                st.warning(f"⚠️ App currently in maintenance mode for another {remaining} seconds.")
                if st.button("Resume Countdown"):
                    countdown(remaining)

if __name__ == "__main__":
    main()
