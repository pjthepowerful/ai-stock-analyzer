# Moving production to Paula 5 (v2)

Everything below is prepared on `v2-rewrite`; nothing changes in production
until these steps are done.

## Autopilot and orders
v2 has both: the same 5-minute loop (`backend-v2/app/services/autopilot_runner.py`,
strategy code unchanged) and chat orders behind a confirm card
(`POST /api/trade/execute`).

- v2 keeps its own state file (`autopilot_state_v2.json`) and refuses to start
  while the original app's autopilot is on, so the two can never trade the
  same account at once.
- **Switching production:** set `AUTOPILOT_ADOPT_ORIGINAL=1` on the v2 service.
  On first boot, if the old backend's autopilot was on, v2 takes it over (same
  owner) and marks the old state off. Never run both backends against the same
  data at once.
- Not ported (on purpose): the pre-market scan, hourly status and P&L-milestone
  phone pings. Trade, error and start/stop pings are kept. The EOD guardian is
  a no-op in swing mode, which is what runs today.

## Preview (safe to run alongside production)
A preview backend must **not** share production's data or Alpaca keys, and
must not set `AUTOPILOT_ADOPT_ORIGINAL`. Give it its own `JWT_SECRET`,
`DB_DIR` and (optionally) its own paper keys.

## Frontend (Vercel)
- Project root directory: `desktop/frontend` → `desktop/frontend-v2`
  (it has its own `vercel.json`, same caching headers).
- `VITE_API_URL` stays the same if Railway keeps serving the API at the same URL.

## Backend (Railway)
- Start command (in `railway.json` and `nixpacks.toml`):
  `cd desktop/backend-v2 && uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- No new Python dependencies (root `requirements.txt` already covers v2).
- Same env as today (`JWT_SECRET`, Alpaca, Groq, …) and the same `paula.db` —
  v2 reads the original database, so accounts and chats carry over.
- CORS already allows the production Vercel domains; override with
  `FRONTEND_ORIGIN_REGEX` or add exact URLs in `ALLOWED_ORIGINS`.

## Rollback
Point Vercel back at `desktop/frontend` and restore the old start command.
