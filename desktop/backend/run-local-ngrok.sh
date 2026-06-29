#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# Paula — run the backend 24/7 from your Mac, using ngrok (free, random URL).
#
# Same idea as run-local.sh but uses ngrok instead of Cloudflare Tunnel:
#   1. Keeps the Mac awake (caffeinate).
#   2. Runs the backend with auto-restart on crash.
#   3. Opens an ngrok tunnel so the internet (your Vercel frontend) can reach it.
#
# ONE-TIME SETUP:
#   • Keys in a .env file (never typed in the terminal):
#         cp .env.example .env        # then edit .env with real values
#   • Install ngrok:
#         brew install ngrok
#
# RUN IT:
#         chmod +x run-local-ngrok.sh   # first time only
#         ./run-local-ngrok.sh
#
# It prints an ngrok URL like https://abcd-1234.ngrok-free.app — copy that into
# your Vercel project's backend URL setting and redeploy the frontend.
#
# NOTE: without an ngrok account the URL CHANGES on every restart, so you'll
# update Vercel each time. (A free ngrok account gives one permanent static
# domain — then run:  ngrok http --url=YOUR-DOMAIN.ngrok-free.app $PORT)
# ─────────────────────────────────────────────────────────────────────────────

cd "$(dirname "$0")" || exit 1

# ── Checks ──────────────────────────────────────────────────────────────────
if [ ! -f ".env" ]; then
  echo "❌ No .env file found. Run:  cp .env.example .env   then fill in your keys."
  exit 1
fi
if ! command -v ngrok >/dev/null 2>&1; then
  echo "❌ ngrok not installed. Run:  brew install ngrok"
  exit 1
fi

source venv/bin/activate 2>/dev/null

# Force the backend onto a known port so ngrok matches it. (server.py otherwise
# defaults to 3141 locally, which wouldn't match the tunnel.)
export PORT="${PORT:-8080}"
PORT="${PORT:-8080}"

# ── Backend watchdog (auto-restart) in the background ───────────────────────
run_backend() {
  while true; do
    echo "$(date) — 🟢 Starting Paula backend on port $PORT..."
    caffeinate -s python server.py     # caffeinate keeps the Mac awake
    CODE=$?
    echo "$(date) — backend exited ($CODE)"
    if [ $CODE -eq 0 ] || [ $CODE -eq 130 ]; then break; fi
    echo "Restarting in 5s..."
    sleep 5
  done
}

run_backend &
BACKEND_PID=$!

# Give the server a moment to bind the port before ngrok connects.
sleep 4

echo ""
echo "🌐 Opening ngrok tunnel — copy the https URL below into Vercel:"
echo "   (look for the 'Forwarding  https://....ngrok-free.app' line)"
echo "────────────────────────────────────────────────────────────────"

cleanup() {
  echo ""
  echo "🔴 Shutting down..."
  kill "$BACKEND_PID" 2>/dev/null
  pkill -P "$BACKEND_PID" 2>/dev/null
  exit 0
}
trap cleanup INT TERM

# ── ngrok (foreground) — Ctrl-C here stops everything ───────────────────────
ngrok http "$PORT"

cleanup
