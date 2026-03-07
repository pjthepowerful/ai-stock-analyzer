#!/bin/bash
# Paula Desktop — Start Script
# Runs the Python backend and opens the frontend

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "🟢 Starting Paula Desktop..."
echo ""

# ── 1. Start Python backend ──
echo "Starting backend on http://127.0.0.1:3141 ..."
cd backend
python server.py &
BACKEND_PID=$!
cd ..

# Wait for backend
sleep 2
echo "Backend PID: $BACKEND_PID"

# ── 2. Start frontend ──
echo "Starting frontend on http://localhost:1420 ..."
cd frontend
npm run dev &
FRONTEND_PID=$!
cd ..

echo ""
echo "════════════════════════════════════════"
echo "  Paula Desktop is running!"
echo ""
echo "  Backend:  http://127.0.0.1:3141"
echo "  Frontend: http://localhost:1420"
echo "  API docs: http://127.0.0.1:3141/docs"
echo ""
echo "  Press Ctrl+C to stop"
echo "════════════════════════════════════════"

# Trap Ctrl+C to kill both
trap "echo ''; echo 'Shutting down...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0" SIGINT SIGTERM

wait
