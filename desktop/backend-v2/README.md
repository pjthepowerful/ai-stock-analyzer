# Paula v2 backend (local preview)

Reuses the real `engine.py` / `auth.py` / `trading.py` from `desktop/backend`
unchanged (see `app/bridge.py`) — same signal logic, same user database.
Only the API layer (routing, request/response typing, error status codes,
WebSocket handling) is new.

Runs on port **4141** so it never collides with the original backend (3141).

## Run

Uses the SAME Python venv as `desktop/backend` (all dependencies — fastapi,
pandas, yfinance, alpaca-py, groq, etc. — already installed there):

```bash
cd desktop/backend-v2
source ../backend/venv/bin/activate
uvicorn app.main:app --reload --port 4141
```

## Verify

```bash
curl http://127.0.0.1:4141/api/health
curl http://127.0.0.1:4141/api/quick/AAPL
```
