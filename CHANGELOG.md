# Paula — Changelog

Version lives in `desktop/frontend/src/App.jsx` as the `VERSION` constant.
Bump it on every shipped change: **patch** for a fix, **minor** for a feature,
**major** for a big release. Add a line here when you bump.

## 4.11.1 — August 14, 2026
- The end-of-day flatten rail in `smallcap_pullback.manage_positions` ran before
  the ownership check, so it closed **every** open position — including ones the
  Core engine opened and intends to hold overnight. Switching modes with a Core
  book open would have liquidated it at 15:45 on the first afternoon, and
  `alpaca_cancel_all_orders()` would have taken Core's brackets with it.
- Each mode now flattens only positions recorded in its own state, and logs a
  warning naming any foreign position it finds rather than acting on it.
- 3 regression tests covering own / foreign / mixed books at flatten time.

## 4.11.0 — August 13, 2026
- Class-schedule alerts (`bell_alerts.py`). Pushes a watchlist via ntfy a
  configurable number of minutes before each class period ends. Advisory only:
  the path never places, sizes or cancels an order.
- Schedule is stored in school-local time (default `America/Chicago`) and
  converted to ET for every market check. `GET /api/bell-alerts` reports each
  period's fire time in both zones and separates periods that can fire from ones
  that can't — 7th ends 15:15 CT = 16:15 ET, after the close, so it is surfaced
  as dead rather than silently never arriving.
- Alert scans respect the active `STRATEGY_MODE`. Small-cap modes route through
  a new `smallcap_pullback.run(candidates_only=True)` read-only path that reuses
  the live scan, so an alert can't describe a setup autopilot wouldn't take.
- Loop auto-resumes on boot and has a restart watchdog; `POST /api/bell-alerts/test`
  fires one immediately to confirm the phone actually buzzes.
- 16 tests, including the school-time-vs-ET conversion and DST.

## 4.10.2 — August 13, 2026
- **Autopilot config writes never reached the engine.** `server.py` resolved
  `autopilot_config.json` relative to itself (`desktop/backend/`) while
  `trading.py` resolved it relative to the repo root. Six call sites — the
  strategy-mode switch, `save_profile`, the auto-tuner, and the scan slot count
  — read and wrote a file the autopilot never opened. Every one now goes through
  `engine.autopilot_cfg_path()`. This predates 4.10.0; the mode switch inherited
  it.
- Config now resolves to `$DB_DIR` when a persistent volume is mounted, with a
  one-time migration from either legacy location. Previously any saved setting
  reverted to the git contents on the next Railway deploy.
- `POST /api/autopilot/mode` reads the value back through the engine's own
  loader and returns an error if it didn't persist, instead of reporting
  success regardless.
- Three regression tests, including a static check that no `server.py` site
  bypasses the shared path again.

## 4.10.1 — August 12, 2026
- Fixed the strategy picker rendering as unclickable text. The CSS referenced
  four variables that don't exist in this stylesheet (`--border`, `--accent`,
  `--warn`, `--sell`; the real names are `--brd`, `--grn`, `--amb`, `--red`), so
  seven declarations were invalid at computed-value time — taking out the card
  borders and the radio dots. Clicks were registering; there was just no
  affordance to click and no visual change afterwards.
- Selected mode now carries a filled dot, a green border and a "running" badge.
- The picker distinguishes "still loading" from "backend unreachable" instead of
  silently rendering an empty card, and rows are properly `disabled` (with a
  tooltip) while autopilot is running rather than only erroring on click.

## 4.10.0 — August 12, 2026
- Autopilot strategy modes. `STRATEGY_MODE` in `autopilot_config.json` selects
  between `core` (the original engine, unchanged), `strict` and `aggro`. The
  latter two are the small-cap gainer pullback system in `smallcap_pullback.py`,
  which owns its own universe scan, setup detection, sizing and exits — none of
  the core config keys apply to it.
- `strict`: $1.50–$20, $50–500M cap, 15–75M float, time-adjusted RVOL ≥5,
  retest-only entries at confluent levels, 0.5% R, 2 positions, −2% daily stop.
- `aggro`: wider bands, breaks allowed, midday allowed at half size, 1% R,
  3 positions, and the pre-planned 3-tranche scale-in ladder with a fixed final
  stop and total risk pinned at 1R.
- Universe filters that actually matter here: time-of-day-adjusted RVOL, float
  and cap bands, traded/projected dollar volume, halt-frequency proxy, SEC
  filings hazard grade (424B5/S-3/S-1, reverse splits, serial splitters) and a
  Groq catalyst triage (real / fluff / none).
- Exits scale out — a third at target, a third at the next target or into a
  climax bar, runner trailed on 9EMA closes with a VWAP floor — plus a time stop
  on dead money and a hard flatten before the close in both modes.
- Every entry is journaled to `smallcap_ab_log.json` with its mode and whether a
  ladder was used, so strict-vs-aggro can be settled on fills rather than vibes.
- `POST /api/autopilot/mode` refuses to switch while autopilot is running; the
  mode that opened a position is the one that knows how to exit it.

## 3.7.1 — June 2026
- Fixed the AI repeating the entry price as the target (e.g. CSCO showing entry
  $121.10 / target $121.10). Valid buy setups now hand the AI one exact
  pre-formatted trade line to quote verbatim, so levels cant get garbled.

## 3.7.0 — June 2026
- Portfolio-aware AI: when you ask about adding to, trimming, or your risk on a
  position, Paula now sees your real buying power, equity, and open positions
  (with P&L) and factors in concentration + existing exposure — not blind advice.

## 3.6.0 — June 2026
- AI understands more of what you ask: the intent router now handles longer,
  more natural phrasings (up to ~25 words) instead of only short exact phrases.
- AI answers the real question and admits when data does not cover it, instead
  of padding with invented specifics.
- Fewer starter prompts on the welcome screen (2 instead of 5).

## 3.5.1 — June 2026
- Polish: removed an orphaned old Settings screen; added a clear note in Settings
  explaining that your own Alpaca keys trade your own account.

## 3.5.0 — June 2026
- Per-user Alpaca accounts: add your own paper keys in Settings and Paula trades
  YOUR account (encrypted at rest). Falls back to the shared account if unset.
  Autopilot uses the owner's keys too. Track record is now per-account.

## 3.4.0 — June 2026
- Autopilot now scans a much wider universe (up to ~400 names via the large
  liquid list) using fast batch fetching, instead of a hardcoded 80.

## 3.3.1 — June 2026
- Delisted/acquired guard (e.g. MASI after the Danaher buyout) — stale-data
  stocks are filtered from scans and flagged in Analyze.
- Per-account autopilot sounds (only the owning account hears them).
- Email-dependent auth (2FA, verification, reset) gated off until a Resend
  sending domain exists.
- Trailer rebuilt; settings gear refreshed.

## 3.3.0 — June 2026
- Scanner widened to 1,000+ liquid stocks + full-NYSE mode via live listing.
- Batch data fetching — hundreds of stocks scanned in seconds.
- Themed scans: energy, defense, biotech, crypto, value.
- AI references your real trade track record for advice.
- Groq rate-limit handling (model fallback + caching).
- IPO / new-listing guard.
- Redesigned welcome screen and Analyze view; new hover rail.
- Real login ticker data; live intraday (1D/5D) charts.
- Signal fixes: directional trend score, no collapsed/hallucinated trade levels.

## 3.2 — earlier
- Named setups, 52-week-high & VCP detection, honest backtest, overnight holds.
- Live news, web search, private-company awareness, market-hours awareness.
- Per-chat memory, stop-mid-stream, always-on cloud hosting, consistent scores.
