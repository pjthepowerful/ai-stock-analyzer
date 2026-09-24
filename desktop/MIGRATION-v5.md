# Moving production to Paula 5 (v2)

Everything below is prepared on `v2-rewrite`; nothing changes in production
until these steps are done.

## What v2 does not have yet
- **Autopilot** (the background trading loop the current Railway server runs).
- **Placing orders** from chat.

Switching Railway to v2 stops autopilot. Options: keep the old backend running
as a second Railway service for autopilot, or port autopilot first.

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
