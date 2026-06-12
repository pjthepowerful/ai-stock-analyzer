# Paula — Changelog

Version lives in `desktop/frontend/src/App.jsx` as the `VERSION` constant.
Bump it on every shipped change: **patch** for a fix, **minor** for a feature,
**major** for a big release. Add a line here when you bump.

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
