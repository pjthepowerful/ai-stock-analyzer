# Paula — Changelog

Version lives in `desktop/frontend/src/App.jsx` as the `VERSION` constant.
Bump it on every shipped change: **patch** for a fix, **minor** for a feature,
**major** for a big release. Add a line here when you bump.

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
