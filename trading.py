import time
import json
import os

SAVE_FILE = "countdown_save.json"

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
    print("⚙️ App will be down for a while...")
    
    try:
        while remaining > 0:
            print(f"\r⏳ Time remaining: {remaining} seconds", end="")
            time.sleep(1)
            remaining -= 1
            save_remaining_time(remaining)
    except KeyboardInterrupt:
        print("\n🔒 Countdown paused.")
        save_remaining_time(remaining)
        return

    print("\n✅ App is back online!")
    os.remove(SAVE_FILE)  # remove save file when done

if __name__ == "__main__":
    total_time = 60  # change this to how many seconds you want
    countdown(total_time)
