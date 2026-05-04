#!/bin/bash
# Paula auto-restart watchdog
# API keys are loaded from DB automatically — no env vars needed after first save
cd "$(dirname "$0")"
source venv/bin/activate 2>/dev/null

# Fallback env vars (used only if DB has no keys saved)
export ALPACA_KEY_ID="${ALPACA_KEY_ID:-}"
export ALPACA_SECRET="${ALPACA_SECRET:-}"
export GROQ_API_KEY="${GROQ_API_KEY:-}"
export POLYGON_API_KEY="${POLYGON_API_KEY:-}"

echo "🟢 Paula watchdog started"
echo "   Keys will load from DB if saved in Settings"

while true; do
    echo "$(date) — Starting Paula backend..."
    python server.py
    EXIT_CODE=$?
    echo "$(date) — Paula exited with code $EXIT_CODE"
    if [ $EXIT_CODE -eq 0 ] || [ $EXIT_CODE -eq 130 ]; then
        echo "Clean shutdown — exiting watchdog"
        break
    fi
    echo "Restarting in 5 seconds..."
    sleep 5
done
