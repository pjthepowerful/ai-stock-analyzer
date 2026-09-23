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

## Environment

Read from `desktop/backend/.env` (or a `backend-v2/.env` override):

| Variable | Needed for |
| --- | --- |
| `JWT_SECRET` | Stable logins across restarts; also keys the encryption of stored broker keys. |
| `GROQ_API_KEY` | Chat answers. Market scans and analysis cards work without it. |
| `POLYGON_API_KEY`, `ALPACA_KEY_ID`, `ALPACA_SECRET` | Market data and the shared paper account. |
| `SEC_USER_AGENT` | Company fundamentals. The SEC returns 403 unless this includes a contact email, e.g. `Paula you@example.com`. |
| `TRUST_PROXY=1` | Only when deployed behind a reverse proxy: lets the guest message limit use `X-Forwarded-For`. Leave unset locally, or the header can be spoofed. |

## Not wired on purpose

- **Autopilot start/stop and placing orders** (`/api/autopilot/start|stop`, buy/sell/short/cover/close-all). These act on a real (paper) Alpaca account and need the owner's explicit go-ahead. `app/services/autopilot_runner.py` exists locally but is not connected. Chat trade requests reply that nothing was sent.
- **Bell alerts**: a background loop that pushes to the owner's phone; running it in both apps would double every notification.
- **Password reset**: email delivery is off (`EMAIL_AUTH_ENABLED`), so codes couldn't be sent.
- **Admin "clear all users"**: too destructive for a button.
