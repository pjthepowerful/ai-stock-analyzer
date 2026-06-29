#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# Paula — run the backend 24/7 from your own Mac, for free.
#
# What this does:
#   1. Keeps your Mac awake while it runs (caffeinate).
#   2. Runs the backend with auto-restart if it crashes.
#   3. Opens a free Cloudflare Tunnel so the internet (your Vercel frontend)
#      can reach the backend running on this machine.
#
# ONE-TIME SETUP:
#   • Put your keys in a .env file (never type them in the terminal):
#         cp .env.example .env        # then edit .env with your real values
#   • Install the tunnel tool:
#         brew install cloudflared
#
# RUN IT:
#         chmod +x run-local.sh        # first time only
#         ./run-local.sh
#
# Then copy the printed https://....trycloudflare.com URL into your Vercel
# project's backend URL setting and redeploy the frontend.
#
# NOTE (no domain): the free tunnel URL CHANGES every time you restart this
# script, so you'll need to update Vercel each time. A ~$10/yr domain on
# Cloudflare would give you a permanent URL — but this keeps it $0.
# ─────────────────────────────────────────────────────────────────────────────

cd "$(dirname "$0")" || exit 1

# ── Checks ──────────────────────────────────────────────────────────────────
if [ ! -f ".env" ]; then
  echo "❌ No .env file found. Run:  cp .env.example .env   then fill in your keys."
  exit 1
fi
if ! command -v cloudflared >/dev/null 2>&1; then
  echo "❌ cloudflared not installed. Run:  brew install cloudflared"
  exit 1
fi

source venv/bin/activate 2>/dev/null

PORT="${PORT:-8080}"

# ── Backend watchdog (auto-restart) runs in the background ──────────────────
run_backend() {
  while true; do
    echo "$(date) — 🟢 Starting Paula backend on port $PORT..."
    # caffeinate -s keeps the Mac awake for as long as the server runs.
    caffeinate -s python server.py
    CODE=$?
    echo "$(date) — backend exited ($CODE)"
    # Clean exit (Ctrl-C) → stop; crash → restart after 5s.
    if [ $CODE -eq 0 ] || [ $CODE -eq 130 ]; then break; fi
    echo "Restarting in 5s..."
    sleep 5
  done
}

run_backend &
BACKEND_PID=$!

# Give the server a moment to bind the port before the tunnel connects.
sleep 4

echo ""
echo "🌐 Opening public tunnel — copy the https URL below into Vercel:"
echo "────────────────────────────────────────────────────────────────"

# ── Tunnel (foreground) — Ctrl-C here stops everything ──────────────────────
cleanup() {
  echo ""
  echo "🔴 Shutting down..."
  kill "$BACKEND_PID" 2>/dev/null
  pkill -P "$BACKEND_PID" 2>/dev/null
  exit 0
}
trap cleanup INT TERM

cloudflared tunnel --url "http://localhost:$PORT"

cleanup
