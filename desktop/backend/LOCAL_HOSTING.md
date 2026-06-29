# Running Paula's backend 24/7 from your Mac (free)

This runs the backend on your own machine instead of Railway, for $0.
Tradeoff: your Mac must stay on/awake/online, and (without a domain) the public
URL changes each restart. Upside: your home IP isn't throttled by Yahoo like a
datacenter IP, so scans tend to be *more* reliable.

## One-time setup

1. **Keys** — put them in a `.env` file (never type them in the terminal):
   ```
   cd desktop/backend
   cp .env.example .env
   # open .env and fill in your real ALPACA / GROQ / POLYGON / JWT_SECRET / etc.
   ```
   `.env` is gitignored, so it's never committed.

2. **Tunnel tool** — installs the thing that gives your local server a public URL:
   ```
   brew install cloudflared
   ```

3. **Python deps** (if not already):
   ```
   source venv/bin/activate
   pip install -r requirements.txt
   ```

## Run it

```
cd desktop/backend
./run-local.sh
```

This keeps the Mac awake, runs the backend (auto-restarting on crash), and opens
a public tunnel. It prints a URL like `https://abcd-1234.trycloudflare.com`.

## Point the frontend at it

In your **Vercel** project → Settings → Environment Variables, set the backend
URL (the `VITE_`/`BACKEND` var the frontend uses) to the printed tunnel URL, then
redeploy. Your live site now talks to the backend on your Mac.

## Keep it alive

- The Mac must not sleep. `caffeinate` (built into the script) keeps it awake
  while running, but also check System Settings → Lock Screen / Battery so the
  machine itself doesn't sleep on a schedule.
- Keep it plugged in and on stable internet.
- If the Mac reboots, just run `./run-local.sh` again (and update Vercel with the
  new tunnel URL).

## Annoyance: the URL changes

Without a domain, every restart gives a new `trycloudflare.com` URL, so you must
update Vercel each time. A ~$10/yr domain added to Cloudflare lets you create a
**named tunnel** with a permanent URL — worth it if you restart often, but not
required to stay at $0.

## Alternative: ngrok instead of Cloudflare

Prefer ngrok? Use `run-local-ngrok.sh` instead (same behavior, ngrok tunnel):
```
brew install ngrok
./run-local-ngrok.sh
```
It prints a `https://....ngrok-free.app` URL — copy that into Vercel.

Without an ngrok account the URL also changes each restart. But a **free ngrok
account** includes one permanent **static domain**: create it in the ngrok
dashboard → Domains, add your authtoken once (`ngrok config add-authtoken ...`),
then run `ngrok http --url=YOUR-DOMAIN.ngrok-free.app 8080` for a URL that never
changes. That's the easiest path to a stable free URL.

