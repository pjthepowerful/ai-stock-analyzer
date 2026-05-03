#!/bin/bash
# Paula auto-restart watchdog — restarts on crash during market hours
cd "$(dirname "$0")"
source venv/bin/activate 2>/dev/null

export ALPACA_KEY_ID="${ALPACA_KEY_ID:-PKW2FMYEUHRNKNLSR6XC3NX25N}"
export ALPACA_SECRET="${ALPACA_SECRET:-CkKDNZSWjaAqNMsXvgia15BBHihYQ6nnt6kD3G5jPoXH}"
export GROQ_API_KEY="${GROQ_API_KEY:-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}"
export POLYGON_API_KEY="${POLYGON_API_KEY:-wzJ5v31KgEA_rwFQxViseXokW5TLoSrG}"

echo "🟢 Paula watchdog started"

while true; do
    echo "$(date) — Starting Paula backend..."
    python server.py
    EXIT_CODE=$?
    echo "$(date) — Paula crashed with exit code $EXIT_CODE"
    
    # If it was a clean shutdown (Ctrl+C), don't restart
    if [ $EXIT_CODE -eq 0 ] || [ $EXIT_CODE -eq 130 ]; then
        echo "Clean shutdown — exiting watchdog"
        break
    fi
    
    echo "Restarting in 5 seconds..."
    sleep 5
done
