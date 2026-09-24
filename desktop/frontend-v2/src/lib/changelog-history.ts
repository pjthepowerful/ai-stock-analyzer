// Release history carried over from Paula 4.x (App.jsx CHANGELOG_DATA).
// Newer releases live in changelog.ts; this file is append-only history.
export const HISTORY: { v: string; d: string; changes: string[] }[] = [
  {
    "v": "4.24.0",
    "d": "September 22, 2026",
    "changes": [
      "The bug-report button used a native browser prompt to ask what went wrong — that kind of dialog freezes the whole window until it’s dismissed. Replaced it with a normal in-app modal.",
      "Fonts were loaded through a render-blocking @import, and duplicated across two stylesheets — on a slow connection this showed as a blank, unstyled flash on first load. Fixed to load once, without blocking.",
      "A pass on the visual design itself: dropped the soft drop-shadow that every card and the message box carried (the generic default-dashboard look), de-glassed the frosted sign-in card, merged three near-identical “Unlock with Paula Plus” boxes in Settings into one list, and dropped the filled chat bubble on your own messages in favor of plain right-aligned text — closer to how Perplexity and other answer-first products separate the question from the answer."
    ]
  },
  {
    "v": "4.23.0",
    "d": "September 21, 2026",
    "changes": [
      "The forecast now makes TWO calls per company, not one: whether it beats, and whether its stock has historically gone up when it beats. These come apart constantly — a company beats, guides down on the call, and the stock drops anyway.",
      "Nothing free can read a conference call before it happens. But a company whose stock has fallen on most of its recent beats is one whose calls keep disappointing, and that pattern is measurable. Each row now shows it: “FELL on 3 of its last 4 beats”.",
      "Also measured: how far the stock has already run into the print. Up 30% going in means a beat may already be in the price.",
      "The two leans are deliberately never averaged together. A company that reliably beats whose stock reliably sells off is the single most useful thing to spot here, and blending would show it as a mild positive."
    ]
  },
  {
    "v": "4.22.2",
    "d": "September 19, 2026",
    "changes": [
      "The earnings forecast list now runs worst to best by default, with a button in the header to flip it back."
    ]
  },
  {
    "v": "4.22.1",
    "d": "September 19, 2026",
    "changes": [
      "Fixed: every company on the earnings calendar said “Watch”. That was a design flaw, not a data problem — a name could only get a different label if it had reported in the last two sessions or reported before the next open, and a calendar is almost entirely neither, so everything fell through to the default.",
      "Future dates now show which way the print leans, using analyst estimate revisions and the company’s own beat history: “Leans beat”, “Leans miss”, or “No lean” when nothing is published. A lean is still never a buy — autopilot does not hold through prints."
    ]
  },
  {
    "v": "4.22.0",
    "d": "September 19, 2026",
    "changes": [
      "New Earnings forecast section: companies reporting in the next three weeks, ranked by how likely they look to beat. It reads analyst estimate revisions (the best free predictor of a surprise), whether consensus has been rising, and how often the company has actually beaten in past quarters.",
      "Every row shows how much that specific stock typically MOVES on earnings day, next to the call rather than behind a click. A company beating and its stock rising are different questions — plenty beat and fall on weak guidance — so the gap figure is what your money is exposed to, not the lean.",
      "Leans are directions, not percentages. Nothing here has been tested against outcomes, and a number like \"73%\" would invite trust it has not earned.",
      "Live progress bars: the earnings calendar rebuild, the research scan and the forecast scan now show what they are working on and how far along they are, instead of a spinner that looks identical to a hang.",
      "Autopilot is unchanged and still refuses to hold a position through a print."
    ]
  },
  {
    "v": "4.21.0",
    "d": "September 19, 2026",
    "changes": [
      "New Research section in Co-Pilot: a longer-term book, separate from autopilot. It ranks companies that have ALREADY reported and beat, using the actual figures from their SEC filings — revenue growth, profitability, and share-count dilution — alongside recent news.",
      "It never places an order. It shows you the case for each name and you decide. Autopilot is untouched and still flattens daily.",
      "The rule autopilot follows — never hold through an earnings print — is about putting 10-20% of the account into one volatile small cap, where a gap is unsurvivable. It is not a rule about the calendar, so a diversified book at small size can hold for weeks. That is what this is.",
      "A PDT exposure meter sits at the top: equity, total held overnight, and the across-the-board drop that would put you under $25,000 and switch off day trading. Positions are sized individually with no sleeve total, so this meter is what keeps the accumulated pile visible."
    ]
  },
  {
    "v": "4.20.0",
    "d": "September 19, 2026",
    "changes": [
      "The earnings calendar now runs off the Nasdaq earnings calendar instead of looking each ticker up one at a time. It used to only know about companies already on the watch universe list — roughly 250 names — so anything reporting outside that list simply never appeared. Nasdaq answers the question the calendar actually asks (who reports on this date), so coverage is now every reporting company.",
      "Names are filtered to a small-cap band, since a $900B company is never a setup for this strategy. Anything you actually hold stays on the calendar regardless of its size.",
      "Each name now shows whether it reports before the open (BMO) or after the close (AMC).",
      "If Nasdaq is unreachable the old per-ticker scan still runs, and the calendar says which source built it."
    ]
  },
  {
    "v": "4.19.1",
    "d": "September 19, 2026",
    "changes": [
      "The earnings calendar now says what actually went wrong instead of “Could not load”. A backend running an older build, an expired login and a real server error are three different problems, and each now names itself.",
      "An empty calendar now distinguishes “never built” from “built, but every lookup failed” — the second means the backend cannot reach the earnings provider, which is a server-side fix, not a Rebuild."
    ]
  },
  {
    "v": "4.19.0",
    "d": "September 19, 2026",
    "changes": [
      "The Co-Pilot earnings section is now a month calendar. Click any date to see which companies report that day, what the street expects, and whether the system would touch them.",
      "Each name gets a plain verdict: “Tradable now” (already reported and beat, reaction still has volume), “Not into it” (reports before the next open — autopilot will not hold through a print), “Missed”, “Watch”, or “Out of range” for names outside the mode’s price and size bands.",
      "Nothing is ever marked a buy BEFORE a report, because the strategy flattens daily and never holds through one — a stop does not execute through an earnings gap."
    ]
  },
  {
    "v": "4.18.0",
    "d": "September 19, 2026",
    "changes": [
      "Earnings are now part of how Intense picks trades. It used to judge whether a gap had a real reason behind it by asking an AI to read the headlines — which can’t reliably tell \"revenue up 40%\" from \"exploring opportunities\". A recent earnings report can be checked against the actual numbers, so when one explains the move it now overrides the guess, and a confirmed beat earns slightly larger size.",
      "A stock that rallied despite MISSING is graded down rather than up — the move is a bounce against the news, not a reaction to it.",
      "Autopilot will no longer open a position in a company reporting before the next open, in either mode. A stop does not execute through an earnings gap.",
      "New Earnings panel in Co-Pilot: what your positions report next with the street’s estimate, and how recent reports actually landed. Add any ticker to check it.",
      "Asking about earnings in chat now answers with the expected EPS and how last quarter came in, not just the date."
    ]
  },
  {
    "v": "4.17.0",
    "d": "August 31, 2026",
    "changes": [
      "Security: the trading endpoints now require a logged-in, trade-authorised account. Previously anyone who knew the backend address could place or close orders on the connected account without logging in.",
      "Security: browser access is now restricted to this app’s own deployments. The old rule accepted any site hosted on vercel.app.",
      "Security: chat-title generation now requires a login, so the AI quota cannot be used by strangers."
    ]
  },
  {
    "v": "4.16.1",
    "d": "August 31, 2026",
    "changes": [
      "Fixed positions coming out roughly a twentieth of their intended size. The limits that keep a position small relative to available liquidity were measuring only the sliver of volume visible on the free data feed, so a trade meant to risk 1% of the account risked about 0.12% instead.",
      "A protective stop is no longer placed until the buy actually fills. An unfilled entry previously left a live sell-stop against a position that did not exist; partial fills now get a stop sized to what filled."
    ]
  },
  {
    "v": "4.16.0",
    "d": "August 18, 2026",
    "changes": [
      "Loosened Intense so it can actually find trades: wider price range, higher float and market-cap ceilings, and lower relative-volume, volatility and setup-quality bars. Risk per trade, position size, the daily stop and the PDT guard are all unchanged — this buys frequency, not leverage.",
      "When a scan finds nothing, it now lists the names that missed by a single filter and by how much, so a threshold can be moved for a reason rather than guessed at.",
      "Every Intense threshold can now be set from an environment variable, so tuning takes a variable change instead of a deploy."
    ]
  },
  {
    "v": "4.15.1",
    "d": "August 18, 2026",
    "changes": [
      "Fixed relative-volume being calculated against an incomplete history. The 20-day baseline needs more bars than one request returns, and the missing pages were the most recent days — so every RVOL reading was measured against a stale average.",
      "Widened the candidate pool. The gainer list is top movers by percentage, which skews to penny stocks and large caps — on the first live run, 16 of 30 names were outside the tradable price range before anything else was checked. It now also pulls the most-active names and prices them in a single request."
    ]
  },
  {
    "v": "4.15.0",
    "d": "August 18, 2026",
    "changes": [
      "The scanner can now run without a paid Polygon plan. Polygon’s free tier does not include the endpoints used to find gainers, which is why scans were coming back empty. It now falls back to Alpaca’s screener, which is free on the account you already have.",
      "Because that fallback’s volume data covers only part of the market, volume thresholds scale down automatically and the log says plainly which data source it is using."
    ]
  },
  {
    "v": "4.14.0",
    "d": "August 18, 2026",
    "changes": [
      "Trade notifications now name what was bought — ticker, share count, entry and stop — instead of just “2 bought”.",
      "Every scan cycle now explains itself. If nothing was bought, the log says which stage rejected the candidates rather than going quiet, and each scan reports how many names died at each filter.",
      "Added a startup self-test that reports on boot whether the market feed, API keys, notification topic and persistent storage are all working, so a broken setup announces itself instead of producing silent empty days.",
      "Setup quality is now re-checked immediately before ordering, not only during detection."
    ]
  },
  {
    "v": "4.13.1",
    "d": "August 17, 2026",
    "changes": [
      "Added a “Why no trades?” button under Autopilot strategy. It runs a read-only scan and tells you exactly where candidates are being lost — missing API key, data feed refusing the request, or a specific filter rejecting everything — instead of leaving you to infer it from “0 ranked”.",
      "Removed a hardcoded Polygon API key that was used as a silent fallback. A missing or misspelled key now fails visibly rather than quietly running on an old key’s data plan."
    ]
  },
  {
    "v": "4.13.0",
    "d": "August 17, 2026",
    "changes": [
      "Migrated off the Llama models Groq retired on August 16 — every AI feature (chat, news analysis, ticker resolution, catalyst grading) was calling a model that no longer answers. Now on GPT-OSS 120B with a 20B fallback for rate limits.",
      "Model names are set in one place and can be overridden with an environment variable, so the next retirement is a config change rather than a code change."
    ]
  },
  {
    "v": "4.12.3",
    "d": "August 17, 2026",
    "changes": [
      "When a scan finds nothing, it now says why. “0 ranked” previously covered three completely different situations — no API key, a data plan that does not include the endpoints being called, and a genuinely quiet market — and gave no way to tell them apart. The log now names which one it was, with the HTTP status when the feed refused."
    ]
  },
  {
    "v": "4.12.2",
    "d": "August 17, 2026",
    "changes": [
      "Added a pattern-day-trader floor guard. Below $25,000 equity a margin account is barred from day trading entirely, so the strategy would simply stop existing. The daily stop now automatically tightens to whatever room the account actually has above that line, and new entries stop before it is crossed. Existing positions are still managed either way.",
      "Applies to both modes and switches itself off on accounts large enough for it to be irrelevant."
    ]
  },
  {
    "v": "4.12.1",
    "d": "August 17, 2026",
    "changes": [
      "Intense no longer caps how many trades it can take in a day. The daily loss limit is what stops the session now — it halts on losses rather than on trade count, which is the number that actually matters. Disciplined keeps its cap."
    ]
  },
  {
    "v": "4.12.0",
    "d": "August 17, 2026",
    "changes": [
      "Two strategies now, no middle option: Disciplined and Intense. Intense replaces Aggressive — it leads with volatility rather than market cap, buys dips inside a range that is still holding, and sells quickly when momentum stops confirming rather than waiting for a target.",
      "Volatility is now an actual filter. A name that gapped in the morning and went quiet gets skipped, as does one whose spread is wider than the few cents you are trying to capture. Stops scale to each name’s own ATR instead of a flat percentage.",
      "Market cap around $100M is treated as a hint, not a rule — names in the sweet spot trade full size, ones outside it trade smaller rather than being ignored.",
      "Intense concentrates 10–20% of capital in one name, but that is the size after it has added on dips, not where it starts. It opens around 7% and ladders up to roughly 18%, with one fixed stop for the whole position."
    ]
  },
  {
    "v": "4.11.3",
    "d": "August 17, 2026",
    "changes": [
      "Fixed the small-cap modes never scanning while positions from another strategy were open. A leftover Core book of four names counted against Aggressive’s three-position limit, so the bot considered itself full and skipped the scan every cycle — all day, without ever saying anything more specific than “max positions held”.",
      "Each mode now counts only the positions it opened against its own limit, and names any it finds from another strategy."
    ]
  },
  {
    "v": "4.11.2",
    "d": "August 17, 2026",
    "changes": [
      "Scan results now say “0 stocks scanned” instead of “? stocks scanned” when a scan legitimately finds nothing — a real zero was being displayed as an unknown."
    ]
  },
  {
    "v": "4.11.1",
    "d": "August 14, 2026",
    "changes": [
      "Fixed a small-cap mode being able to liquidate positions it did not open. Switching to Disciplined or Aggressive while the Core engine held swing positions would have closed all of them at the end-of-day flatten. Each mode now only closes what it opened, and flags anything else it finds so you can decide."
    ]
  },
  {
    "v": "4.11.0",
    "d": "August 13, 2026",
    "changes": [
      "Class-schedule alerts. Paula can now push a watchlist to your phone a couple of minutes before each period ends, so there is something waiting when you check between classes. Set it up under Settings → Class-schedule alerts.",
      "The schedule is in school time and the card shows the market-time equivalent next to each period, so it is obvious which bells land while the market is actually open. Last period ends after the close, so it is greyed out rather than silently never arriving.",
      "Alerts are advisory only — they never place, size or cancel an order. Whichever strategy mode is selected is the one the alert scan uses."
    ]
  },
  {
    "v": "4.10.2",
    "d": "August 13, 2026",
    "changes": [
      "Fixed autopilot settings not actually reaching the bot. The API saved changes to a different file than the trading engine reads, so strategy mode, trader profile and auto-tuner results were all being written somewhere nothing looked at. Both now use one file.",
      "Autopilot settings now live on the persistent volume when one is mounted, so they survive a redeploy instead of resetting to defaults on every push.",
      "Switching strategy now verifies the change actually landed and reports an error if it did not, rather than reporting success either way."
    ]
  },
  {
    "v": "4.10.1",
    "d": "August 12, 2026",
    "changes": [
      "Fixed the Autopilot strategy picker being impossible to use — the mode cards had no visible borders and the selection dots never rendered, so there was nothing to click and no feedback when you did. Modes now show a clear selected state with a “running” badge, and the picker says so plainly when it can’t reach the backend."
    ]
  },
  {
    "v": "4.10.0",
    "d": "August 12, 2026",
    "changes": [
      "Autopilot now has selectable strategies. Alongside the original engine (“Core”), there are two small-cap gainer modes: “Disciplined” only takes A-grade pullback retests at 0.5% risk with hard stops, and “Aggressive” trades a wider universe at 1% risk and can ladder into a pre-planned support zone. Pick one under Settings → Autopilot strategy.",
      "Both small-cap modes screen for what actually matters in that universe — time-adjusted relative volume, float and market cap bands, real traded dollar volume, recent halts, SEC dilution filings and reverse splits — and skip names where the spike looks like a financing window.",
      "Small-cap exits scale out into strength instead of dumping at once: a third at target, a third at the next target or into a climax bar, and the rest trailed. Everything flattens before the close, every day."
    ]
  },
  {
    "v": "4.9.4",
    "d": "August 12, 2026",
    "changes": [
      "Better answers about who reports earnings today: Paula now knows the exact day of week and searches the real date, so “what reports tonight?” pulls today’s calendar instead of guessing."
    ]
  },
  {
    "v": "4.9.3",
    "d": "August 6, 2026",
    "changes": [
      "More active autopilot exits for the same-day book: a full take-profit that banks the runner at target (not just half), quicker exits from dead/mildly-losing positions, and an end-of-day wind-down that locks in green positions before the forced close instead of dumping everything at 2:45."
    ]
  },
  {
    "v": "4.9.2",
    "d": "August 6, 2026",
    "changes": [
      "Fixed a serious bug where a typed ticker could be silently swapped for a similar one (e.g. COF analyzed as CLF). A ticker you type is now analyzed as-is — never auto-corrected to a different stock."
    ]
  },
  {
    "v": "4.9.1",
    "d": "August 6, 2026",
    "changes": [
      "Cleaner sources: web-search citations no longer show ugly redirect links — just the publisher and a real link.",
      "Stronger sell/exit logic: Paula now always tells you where to exit and what would make it a sell, not just where to buy.",
      "Autopilot exits sooner: positions now leave on a plain SELL signal or a broken setup instead of riding to the end-of-day close, with a clear reason logged."
    ]
  },
  {
    "v": "4.9.0",
    "d": "August 6, 2026",
    "changes": [
      "Scan picks now explain what’s actually distinctive about each one — the “why” leads with the standout signals (volume spike, news, breakout, RSI) instead of the same generic trend bullets every uptrend shares."
    ]
  },
  {
    "v": "4.8.5",
    "d": "August 6, 2026",
    "changes": [
      "Restyled the “Too new” badge and a stray button hover from purple to match the app’s theme."
    ]
  },
  {
    "v": "4.8.4",
    "d": "August 6, 2026",
    "changes": [
      "You can now scroll up freely while a reply is still streaming — it won’t yank you back to the bottom. Scroll back down to re-follow the live response."
    ]
  },
  {
    "v": "4.8.3",
    "d": "August 5, 2026",
    "changes": [
      "Fixed the You vs S&P 500 card never appearing — the S&P benchmark data wasn’t being fetched. Your portfolio return now shows next to the index on the Portfolio page."
    ]
  },
  {
    "v": "4.8.2",
    "d": "August 5, 2026",
    "changes": [
      "Landing top bar is now fixed to the top of the screen at all times, simplified to just the logo and a Sign in button."
    ]
  },
  {
    "v": "4.8.1",
    "d": "August 4, 2026",
    "changes": [
      "The landing page top bar now stays pinned at the top while you scroll."
    ]
  },
  {
    "v": "4.8.0",
    "d": "August 4, 2026",
    "changes": [
      "The whole app now matches the dark landing theme by default — chats, tabs, and panels share one look end to end. (You can still switch to light in settings.)",
      "Added more motion on the landing: cards lift on hover, the preview card breathes, the primary button pulses, and the hero accent shimmers."
    ]
  },
  {
    "v": "4.7.4",
    "d": "August 4, 2026",
    "changes": [
      "Fixed the landing page not scrolling — you can now scroll down through the hero, copilot demo, scanner, and tracker sections. (The app dashboard still stays fixed as before.)"
    ]
  },
  {
    "v": "4.7.3",
    "d": "August 4, 2026",
    "changes": [
      "Copilot demo now unfolds as you scroll — each question and answer reveals one after another down the page, instead of clicking or auto-cycling through them."
    ]
  },
  {
    "v": "4.7.2",
    "d": "August 4, 2026",
    "changes": [
      "Landing page: removed the little pill/badge boxes that read as generic, and the copilot demo questions now auto-cycle so you watch them change instead of clicking through."
    ]
  },
  {
    "v": "4.7.1",
    "d": "August 4, 2026",
    "changes": [
      "Sign-in modal is now wider and scrolls if it’s taller than the screen, so nothing gets cut off on smaller displays."
    ]
  },
  {
    "v": "4.7.0",
    "d": "August 4, 2026",
    "changes": [
      "Merged sign-in into the landing page — one continuous site. Clicking Sign in / Launch now opens a login modal right over the landing instead of jumping to a separate screen."
    ]
  },
  {
    "v": "4.6.5",
    "d": "August 3, 2026",
    "changes": [
      "Fixed “setup for [stock]” running a generic scan instead of analyzing that stock — naming a ticker with “setup” or “plan” now reliably analyzes that ticker."
    ]
  },
  {
    "v": "4.6.4",
    "d": "August 3, 2026",
    "changes": [
      "Fixed “make a trade plan for [stock]” sometimes running a full backtest instead of analyzing that stock — it now reliably gives the trade plan for the ticker you named."
    ]
  },
  {
    "v": "4.6.3",
    "d": "August 3, 2026",
    "changes": [
      "Fixed the written analysis occasionally stating the profit target as the entry price (the trade card was always correct). The target is now stated explicitly and can’t be confused with the entry."
    ]
  },
  {
    "v": "4.6.2",
    "d": "August 2, 2026",
    "changes": [
      "Earnings dates now work by company name and for several at once — “when are Netflix and CrowdStrike earnings?” returns the actual scheduled dates instead of a generic “check a calendar” answer."
    ]
  },
  {
    "v": "4.6.1",
    "d": "August 2, 2026",
    "changes": [
      "Earnings and news questions (“what stocks will beat earnings?”) now go to the research/chat answer with live news instead of dead-ending in the technical scanner — which can’t predict earnings anyway."
    ]
  },
  {
    "v": "4.6.0",
    "d": "August 2, 2026",
    "changes": [
      "Smarter scans: describe a theme in plain language (“AI infrastructure plays”, “recession-proof names”, “green energy”) and Paula now maps it to the right sector instead of only matching fixed keywords."
    ]
  },
  {
    "v": "4.5.0",
    "d": "August 1, 2026",
    "changes": [
      "Smarter, context-aware stock recognition: Paula now uses the AI (with the conversation) to figure out which stock you mean — so follow-ups like “look at the pattern” stay on the stock you’re discussing — and every ticker it picks is validated as real before use."
    ]
  },
  {
    "v": "4.4.0",
    "d": "July 31, 2026",
    "changes": [
      "New on the Portfolio page: You vs S&P 500 — see your return next to the index over any period, and whether you’re beating the market or would’ve been better off in an index fund."
    ]
  },
  {
    "v": "4.3.2",
    "d": "July 31, 2026",
    "changes": [
      "Fixed Paula sometimes analyzing the wrong stock — words like “pattern” or “so” were being mistaken for tickers (PTRN, SO). Vague follow-ups now stay on the stock you’re discussing instead of inventing a new one."
    ]
  },
  {
    "v": "4.3.1",
    "d": "July 30, 2026",
    "changes": [
      "Cleaner look: brand elements (avatars, buttons, nav) are now ink black in light mode so green means only gains, and removed the emoji from Paula’s messages."
    ]
  },
  {
    "v": "4.3.0",
    "d": "July 30, 2026",
    "changes": [
      "New editorial-mono light theme (now the default): warm off-white, ink black, deepened green/red on P/L only — cleaner and less generic. Toggle back to dark anytime in settings."
    ]
  },
  {
    "v": "4.2.2",
    "d": "July 30, 2026",
    "changes": [
      "Fixed the daily change % in the stock header sometimes disagreeing with the chart — it now computes the change from the previous close like the chart does, instead of the day’s open."
    ]
  },
  {
    "v": "4.2.1",
    "d": "July 29, 2026",
    "changes": [
      "High-conviction alert banner now triggers at a slightly higher bar (score 92+ instead of 90+), so it fires only on the strongest setups."
    ]
  },
  {
    "v": "4.2.0",
    "d": "July 28, 2026",
    "changes": [
      "Autopilot now takes profits faster — it scales out of winners sooner and starts protecting gains earlier, tightest in day-trade mode so intraday moves aren’t round-tripped."
    ]
  },
  {
    "v": "4.1.3",
    "d": "July 28, 2026",
    "changes": [
      "Made the Co-Pilot text larger and easier to read."
    ]
  },
  {
    "v": "4.1.2",
    "d": "July 28, 2026",
    "changes": [
      "Buying power now shows full cents (1,299.50 instead of 1,299.5) once you finish typing."
    ]
  },
  {
    "v": "4.1.1",
    "d": "July 28, 2026",
    "changes": [
      "Co-Pilot now shows the exact dollar amount you’d gain if your target hits and lose if your stop hits — both on each position and as a preview before you buy (with the reward-to-risk ratio)."
    ]
  },
  {
    "v": "4.1.0",
    "d": "July 28, 2026",
    "changes": [
      "Co-Pilot price alerts: set a stop and target when you add a position, and get an on-screen badge (plus a browser notification) the moment price crosses your level — so you don’t miss an exit. You set the levels; it just watches them."
    ]
  },
  {
    "v": "4.0.3",
    "d": "July 28, 2026",
    "changes": [
      "Co-Pilot P/L now updates live — refreshes every 60 seconds (and the moment you return to the tab), with a “last updated” time. Pauses in the background to save data."
    ]
  },
  {
    "v": "4.0.2",
    "d": "July 28, 2026",
    "changes": [
      "Co-Pilot no longer dumps all your buying power into one stock — you now choose how many positions to spread across (default 4), separate from the autopilot bot’s cap."
    ]
  },
  {
    "v": "4.0.1",
    "d": "July 28, 2026",
    "changes": [
      "Buying power now shows thousands separators as you type (e.g. 1,172.30)."
    ]
  },
  {
    "v": "4.0.0",
    "d": "July 28, 2026",
    "changes": [
      "Co-Pilot now respects a position cap like autopilot — it won’t suggest more stocks than you can hold, showing the top picks as actionable and the rest as over-cap.",
      "Fixed a chart bug where moving-average overlays could error out while switching tickers.",
      "Charts load faster and hit the data source less — recently viewed charts are cached, and the chart no longer rebuilds when it doesn’t need to.",
      "Reliability cleanup under the hood."
    ]
  },
  {
    "v": "3.50.0",
    "d": "July 28, 2026",
    "changes": [
      "New Co-Pilot (under Autopilot): enter your buying power, scan for picks, and it suggests a position size for each — you confirm the ones you actually buy.",
      "Tracks your positions with live P/L, refreshing every 5 minutes, and re-scans for new picks automatically.",
      "Fractional shares supported. Everything stays on your device."
    ]
  },
  {
    "v": "3.49.0",
    "d": "July 27, 2026",
    "changes": [
      "Ask about specific stocks by name (“when should I buy TSLA and GOOG?”) and Paula now analyzes those tickers instead of running a generic market scan.",
      "Fixed shorthand tickers like GOOG resolving to the right stock in multi-stock questions."
    ]
  },
  {
    "v": "3.48.0",
    "d": "July 26, 2026",
    "changes": [
      "New admin Signal Validation panel: runs a real decile / rank-IC study on the score and shows whether it actually predicts forward returns — an honest instrument, not a confluence display."
    ]
  },
  {
    "v": "3.47.0",
    "d": "July 24, 2026",
    "changes": [
      "Ask about companies by name and Paula pulls live data for all of them — “Tesla or Google”, “Netflix vs Disney” now price both, not just one.",
      "If live data can’t be pulled for one stock in your question, Paula now says so plainly instead of glossing over it.",
      "Fixed some company questions (like Disney) being mistaken for private companies and answered without live data."
    ]
  },
  {
    "v": "3.46.0",
    "d": "July 24, 2026",
    "changes": [
      "Your chats now sync across devices — start on your laptop, pick it up on your phone, all under the same account.",
      "Paula follows the thread better: say “analyze it”, “compare them”, or “the second one” and it knows which stocks you mean from earlier in the chat."
    ]
  },
  {
    "v": "3.45.0",
    "d": "July 19, 2026",
    "changes": [
      "Fixed a stock in your portfolio occasionally showing “no data” even though it’s actively trading — price lookups now recover from rate-limits instead of coming back empty.",
      "Ask something simple while a big market scan is running and it’s answered right away — a scan no longer holds up other requests.",
      "The market scan progress bar is more accurate — it now tracks the whole scan (fetching, scoring, finalizing) and climbs smoothly instead of racing to 100% and stalling."
    ]
  },
  {
    "v": "3.44.0",
    "d": "July 3, 2026",
    "changes": [
      "Added a 🐞 Report Bug button in the top bar — tap it to send the current chat to the developer for testing."
    ]
  },
  {
    "v": "3.43.2",
    "d": "July 3, 2026",
    "changes": [
      "Fixed stocks showing “NO_DATA” with no score even though the chart loaded — analysis now falls back to a second data source when the main one is blocked."
    ]
  },
  {
    "v": "3.43.1",
    "d": "July 3, 2026",
    "changes": [
      "Cleaned up the scan list — removed companies that were acquired and no longer trade, and fixed two tickers that changed symbols. Scans waste less time and the errors are gone."
    ]
  },
  {
    "v": "3.43.0",
    "d": "July 3, 2026",
    "changes": [
      "Paula understands what you mean more often — improved how she reads requests so she misfires less on natural phrasing."
    ]
  },
  {
    "v": "3.42.0",
    "d": "July 3, 2026",
    "changes": [
      "Tighter risk rules — no single position can exceed 10% of your account, and Paula’s advice now holds a firmer line on stops, cutting losses, and not over-concentrating."
    ]
  },
  {
    "v": "3.41.2",
    "d": "July 3, 2026",
    "changes": [
      "Sized the welcome screen down a bit and fixed the stat row so the cells fill evenly (no empty gap after Positions)."
    ]
  },
  {
    "v": "3.41.1",
    "d": "July 3, 2026",
    "changes": [
      "Fixed the SPY change % mismatch — the stat row and market card now agree (both show the real day change)."
    ]
  },
  {
    "v": "3.41.0",
    "d": "July 3, 2026",
    "changes": [
      "Autopilot now trims back down if it’s ever holding more positions than its limit — closing the weakest setups first, and never selling a position that’s in profit."
    ]
  },
  {
    "v": "3.40.0",
    "d": "July 3, 2026",
    "changes": [
      "The market snapshot now loads first on the welcome screen.",
      "Polished the wording of scan recommendations."
    ]
  },
  {
    "v": "3.39.6",
    "d": "July 3, 2026",
    "changes": [
      "Welcome screen scales up on big/full-screen displays so it no longer feels small — bigger greeting and roomier cards."
    ]
  },
  {
    "v": "3.39.5",
    "d": "July 3, 2026",
    "changes": [
      "The rotating prompts under the greeting switch a little quicker now."
    ]
  },
  {
    "v": "3.39.4",
    "d": "July 3, 2026",
    "changes": [
      "Autopilot now recognizes market holidays — it stays idle on days the market is closed (like July 3) instead of trying to trade."
    ]
  },
  {
    "v": "3.39.3",
    "d": "July 3, 2026",
    "changes": [
      "Corrected the dates on recent updates."
    ]
  },
  {
    "v": "3.39.2",
    "d": "July 3, 2026",
    "changes": [
      "Fixed the sidebar still highlighting your chat as active when you’re on the Analyze or Portfolio tab."
    ]
  },
  {
    "v": "3.39.1",
    "d": "July 3, 2026",
    "changes": [
      "Bigger stop icon on the send button while a reply is generating."
    ]
  },
  {
    "v": "3.39.0",
    "d": "July 3, 2026",
    "changes": [
      "Scans now keep running when you switch chats — the result lands back in the chat that started it, even if you’ve moved on. You’ll get a heads-up when it’s ready."
    ]
  },
  {
    "v": "3.38.5",
    "d": "July 3, 2026",
    "changes": [
      "Fixed the scan footer showing raw asterisks — those lines are now properly bold."
    ]
  },
  {
    "v": "3.38.4",
    "d": "June 29, 2026",
    "changes": [
      "Cleaner font on the performance chart tooltip and axis labels."
    ]
  },
  {
    "v": "3.38.3",
    "d": "June 28, 2026",
    "changes": [
      "Reverted the app icon back to the previous one."
    ]
  },
  {
    "v": "3.38.1",
    "d": "June 28, 2026",
    "changes": [
      "“What should I buy?” now shows ONLY the definite buys — the setups that clear autopilot’s full bar — instead of mixing in watch-list names. If nothing qualifies, it says so plainly."
    ]
  },
  {
    "v": "3.38.0",
    "d": "June 28, 2026",
    "changes": [
      "Smarter “what should I buy?” — the scan now gives a real recommendation, judging each pick the way autopilot does: would-buy vs watch vs pass, the reasoning, the risk, and a bottom-line takeaway."
    ]
  },
  {
    "v": "3.37.4",
    "d": "June 28, 2026",
    "changes": [
      "More even spacing on the welcome screen — greeting, stats, market card, and actions have more room to breathe."
    ]
  },
  {
    "v": "3.37.3",
    "d": "June 28, 2026",
    "changes": [
      "Removed the P logo from the welcome screen for a cleaner greeting."
    ]
  },
  {
    "v": "3.37.2",
    "d": "June 28, 2026",
    "changes": [
      "Removed the regime label from the Today’s market card for a cleaner look."
    ]
  },
  {
    "v": "3.37.1",
    "d": "June 28, 2026",
    "changes": [
      "Cleaner portfolio number font, and the font-size setting now applies across the whole app — not just chat.",
      "Daily balance up top now shows a + for gains and a − for losses."
    ]
  },
  {
    "v": "3.37.0",
    "d": "June 27, 2026",
    "changes": [
      "Leaving a chat or closing the tab now cancels an in-progress request (like a scan), so the server isn’t left working on something you’ve walked away from."
    ]
  },
  {
    "v": "3.36.4",
    "d": "June 27, 2026",
    "changes": [
      "Simplified the Today’s market card — removed the VIX and RSI line for a cleaner look."
    ]
  },
  {
    "v": "3.36.3",
    "d": "June 26, 2026",
    "changes": [
      "Fixed scans crashing the server — they were spawning too many threads for the host. Scans are now resource-safe and reliable."
    ]
  },
  {
    "v": "3.36.2",
    "d": "June 26, 2026",
    "changes": [
      "Fixed scans timing out — the live connection now stays alive during long scans, so results actually come back instead of hanging."
    ]
  },
  {
    "v": "3.36.1",
    "d": "June 26, 2026",
    "changes": [
      "Chat names now update instantly from your question, before Paula replies.",
      "Fixed autopilot quirks — stopping it no longer posts a stray message to the wrong chat, and toggling it no longer renames your chat."
    ]
  },
  {
    "v": "3.36.0",
    "d": "June 26, 2026",
    "changes": [
      "You can now scan the entire NASDAQ — just ask. It’s a big scan and takes several minutes (and may return partial data when the free data source throttles)."
    ]
  },
  {
    "v": "3.35.2",
    "d": "June 26, 2026",
    "changes": [
      "Scans finish more reliably — tuned the size and added a clear message if the data source is too slow, instead of an unexplained timeout."
    ]
  },
  {
    "v": "3.35.1",
    "d": "June 26, 2026",
    "changes": [
      "Scans cover more of the market again (~1,000 stocks for Plus) now that they run in the background and can’t time out."
    ]
  },
  {
    "v": "3.35.0",
    "d": "June 26, 2026",
    "changes": [
      "Scans no longer time out — they run in the background and the results stream in when ready, even for big scans."
    ]
  },
  {
    "v": "3.34.3",
    "d": "June 26, 2026",
    "changes": [
      "Faster scans — tuned the market scan so it finishes reliably instead of timing out with “Connection lost.”"
    ]
  },
  {
    "v": "3.34.2",
    "d": "June 26, 2026",
    "changes": [
      "Scans are more reliable — fixed a bug where live stocks got wrongly skipped as “delisted” when the data source briefly blocked us, plus cleaned out more genuinely-delisted tickers."
    ]
  },
  {
    "v": "3.34.1",
    "d": "June 26, 2026",
    "changes": [
      "Free scans now cover the ~100 most-liquid stocks; Paula Plus scans the full ~1,000-name universe."
    ]
  },
  {
    "v": "3.34.0",
    "d": "June 26, 2026",
    "changes": [
      "High-conviction alerts — when autopilot’s scan flags a setup scoring 90+, an in-app banner pops up so you don’t miss the best ones.",
      "Bigger default scan (~1000 stocks, up from ~500) for wider coverage.",
      "Scan progress now shows a percentage as it works."
    ]
  },
  {
    "v": "3.33.1",
    "d": "June 26, 2026",
    "changes": [
      "Maintenance mode now appears for users automatically — no refresh needed (flips instantly over the live connection, and falls back to a fast poll)."
    ]
  },
  {
    "v": "3.33.0",
    "d": "June 26, 2026",
    "changes": [
      "Autopilot now syncs with your real account each cycle — it counts today’s actual trades and respects open positions, even after a restart, so daily limits are accurate."
    ]
  },
  {
    "v": "3.32.4",
    "d": "June 26, 2026",
    "changes": [
      "Cleaned delisted/acquired tickers (Ansys, Paramount, Dun & Bradstreet, Hess) out of the scan universe so scans stop wasting time on dead symbols."
    ]
  },
  {
    "v": "3.32.3",
    "d": "June 26, 2026",
    "changes": [
      "Charts are far more reliable — added a Polygon fallback so they stop showing “chart data is busy” when Yahoo rate-limits the server."
    ]
  },
  {
    "v": "3.32.2",
    "d": "June 25, 2026",
    "changes": [
      "Clearer errors — says “API limit reached” when rate-limited (and “server busy” on restarts) instead of a blanket “Connection lost.”"
    ]
  },
  {
    "v": "3.32.1",
    "d": "June 25, 2026",
    "changes": [
      "Today’s market card now reliably shows a top gainer and loser (added a fallback when the data source is limited), and no longer repeats the SPY line."
    ]
  },
  {
    "v": "3.32.0",
    "d": "June 25, 2026",
    "changes": [
      "Live progress bar on the big market scan — watch Paula work through the stocks in real time instead of staring at a spinner."
    ]
  },
  {
    "v": "3.31.2",
    "d": "June 25, 2026",
    "changes": [
      "Redid the \"Today’s market\" card — now shows if the market is up or down plus the day’s top gainer and top loser, instead of repeating the SPY price."
    ]
  },
  {
    "v": "3.31.1",
    "d": "June 25, 2026",
    "changes": [
      "Cleaner welcome screen — solid greeting color and more even spacing.",
      "Closed a couple of paywall gaps so Plus features stay Plus-only."
    ]
  },
  {
    "v": "3.31.0",
    "d": "June 24, 2026",
    "changes": [
      "Autopilot now keeps running on its own — it survives the server restarting and resumes automatically, so it trades unattended even with your laptop closed."
    ]
  },
  {
    "v": "3.30.0",
    "d": "June 24, 2026",
    "changes": [
      "New \"Today’s market\" summary on the welcome screen — regime, SPY, VIX, and RSI at a glance.",
      "Clearer error messages when a ticker, the data source, or your brokerage has a problem.",
      "Mobile polish — bigger tap targets and better-fitting cards on phones."
    ]
  },
  {
    "v": "3.29.10",
    "d": "June 24, 2026",
    "changes": [
      "Backend stability — fixed memory leaks that were causing the server to restart under load."
    ]
  },
  {
    "v": "3.29.9",
    "d": "June 22, 2026",
    "changes": [
      "Removed the “Autopilot active” banner under the chat input."
    ]
  },
  {
    "v": "3.29.8",
    "d": "June 22, 2026",
    "changes": [
      "Removed the timestamps under messages for a cleaner chat."
    ]
  },
  {
    "v": "3.29.7",
    "d": "June 22, 2026",
    "changes": [
      "Free tier is now 3 messages a day."
    ]
  },
  {
    "v": "3.29.6",
    "d": "June 22, 2026",
    "changes": [
      "The app now reliably self-heals after an update instead of ever loading unstyled or half-broken."
    ]
  },
  {
    "v": "3.29.5",
    "d": "June 22, 2026",
    "changes": [
      "Reverted two recent changes."
    ]
  },
  {
    "v": "3.29.2",
    "d": "June 21, 2026",
    "changes": [
      "More breathing room between section headings and their content on the Analyze and Portfolio pages."
    ]
  },
  {
    "v": "3.29.1",
    "d": "June 21, 2026",
    "changes": [
      "Tidied the sidebar — Automation now sits above Chats, and removed a duplicate Automation heading."
    ]
  },
  {
    "v": "3.29.0",
    "d": "June 21, 2026",
    "changes": [
      "Execute now opens a buy panel — see your buying power, pick how many shares, and it warns (and caps) if you’d go over."
    ]
  },
  {
    "v": "3.28.4",
    "d": "June 21, 2026",
    "changes": [
      "Fixed the big gap in the background theme picker — the swatches now sit neatly under the label."
    ]
  },
  {
    "v": "3.28.3",
    "d": "June 21, 2026",
    "changes": [
      "Gradient backgrounds now only apply in dark mode (they looked off on light) — light mode stays clean.",
      "Cleaned up the broker key fields — removed the example text in the inputs."
    ]
  },
  {
    "v": "3.28.2",
    "d": "June 21, 2026",
    "changes": [
      "You can now cancel all open orders — just ask, and confirm. Your positions stay open."
    ]
  },
  {
    "v": "3.28.1",
    "d": "June 21, 2026",
    "changes": [
      "Smart/auto buys now ask for confirmation too — closing the last path that could trade without a tap.",
      "Autopilot chats are now grouped under an \"Automation\" heading in the sidebar."
    ]
  },
  {
    "v": "3.28.0",
    "d": "June 21, 2026",
    "changes": [
      "Trades now ask for confirmation first — buying, selling, or shorting shows a Confirm/Cancel card, and nothing is placed until you tap Confirm."
    ]
  },
  {
    "v": "3.27.1",
    "d": "June 21, 2026",
    "changes": [
      "Fixed a serious bug where quoting a reply that mentioned \"buy\" could place a real trade — questions and quotes never execute trades now.",
      "Quoted text now shows as a clean \"replying to\" card above the message box instead of raw text."
    ]
  },
  {
    "v": "3.27.0",
    "d": "June 21, 2026",
    "changes": [
      "Highlight any part of Paula’s reply to quote it and ask a follow-up about that specific bit.",
      "The Plus crown is now part of your name and slides in with it."
    ]
  },
  {
    "v": "3.26.5",
    "d": "June 21, 2026",
    "changes": [
      "Removed the redundant \"Analyze\" button that appeared under a stock you were already analyzing."
    ]
  },
  {
    "v": "3.26.4",
    "d": "June 21, 2026",
    "changes": [
      "Deep stock analysis is now properly Plus-only everywhere — including in chat — not just the Analyze tab."
    ]
  },
  {
    "v": "3.26.3",
    "d": "June 21, 2026",
    "changes": [
      "Charts no longer fail when the data source is busy — they now cache, retry automatically, and show a clear message instead of a blank chart."
    ]
  },
  {
    "v": "3.26.2",
    "d": "June 21, 2026",
    "changes": [
      "Fixed chat and data failing to load on the live site (a cross-origin/CORS issue between the app and its server)."
    ]
  },
  {
    "v": "3.26.1",
    "d": "June 21, 2026",
    "changes": [
      "Scans are faster and stop getting rate-limited — the default scan now focuses on the ~500 most liquid stocks and remembers recent results.",
      "Closed a way to open Analyze without Plus from the welcome screen."
    ]
  },
  {
    "v": "3.26.0",
    "d": "June 21, 2026",
    "changes": [
      "Tap \"Analyze\" right under any stock Paula suggests to pull up its full breakdown.",
      "Fixed scans coming back empty — they were getting rate-limited by being too aggressive; now they retry and stay under the limit.",
      "Paula no longer makes up market-cap figures or stale company facts."
    ]
  },
  {
    "v": "3.25.1",
    "d": "June 21, 2026",
    "changes": [
      "Scans are faster again — the whole market now downloads fully in parallel instead of in waves."
    ]
  },
  {
    "v": "3.25.0",
    "d": "June 21, 2026",
    "changes": [
      "Faster scans — the market is now downloaded in parallel chunks and briefly cached, so big scans finish quicker.",
      "Definition popups now have an × button to close them."
    ]
  },
  {
    "v": "3.24.6",
    "d": "June 21, 2026",
    "changes": [
      "Stopped showing a wrong CEO name on company cards — if the CEO can’t be confidently identified, the line is now hidden instead of guessing."
    ]
  },
  {
    "v": "3.24.5",
    "d": "June 21, 2026",
    "changes": [
      "Cleaned up the Analyze, Performance, and Settings tabs by removing the small subtitle text under each header."
    ]
  },
  {
    "v": "3.24.4",
    "d": "June 21, 2026",
    "changes": [
      "Fixed the crown getting clipped at the edge of the profile box."
    ]
  },
  {
    "v": "3.24.3",
    "d": "June 21, 2026",
    "changes": [
      "Brought back the gold crown for Plus members."
    ]
  },
  {
    "v": "3.24.2",
    "d": "June 21, 2026",
    "changes": [
      "Fixed the \"What’s new\" list not showing the newest versions, and gave Plus members a nicer star icon."
    ]
  },
  {
    "v": "3.24.1",
    "d": "June 21, 2026",
    "changes": [
      "Plus members now get a clean star icon by their name instead of the stacked text."
    ]
  },
  {
    "v": "3.24.0",
    "d": "June 18, 2026",
    "changes": [
      "Paula will now honestly tell you when NOT to trade — no forcing a mediocre idea just to have one.",
      "Fixed the version number sometimes showing stale after an update."
    ]
  },
  {
    "v": "3.23.0",
    "d": "June 18, 2026",
    "changes": [
      "Plus members can pick a gradient background theme for the whole app — midnight, forest, deep sea, twilight, ember, and more.",
      "Cleaned up how Plus shows in the sidebar."
    ]
  },
  {
    "v": "3.22.1",
    "d": "June 18, 2026",
    "changes": [
      "Chat sticks to the bottom while a reply streams in — but scrolling up stops it, so you can read freely.",
      "Definition popups now close when you scroll."
    ]
  },
  {
    "v": "3.22.0",
    "d": "June 18, 2026",
    "changes": [
      "Fixed market-cap scans — \"small caps under $1 billion\" now filters by company size, not share price.",
      "Trading terms in Paula’s replies (RSI, oversold, death cross…) are highlighted — tap one for a plain-English definition."
    ]
  },
  {
    "v": "3.21.6",
    "d": "June 18, 2026",
    "changes": [
      "Made the Plus badge a bit bigger."
    ]
  },
  {
    "v": "3.21.5",
    "d": "June 18, 2026",
    "changes": [
      "The Plus \"+\" badge is now a clean glowing green mark, no background."
    ]
  },
  {
    "v": "3.21.4",
    "d": "June 18, 2026",
    "changes": [
      "Plus members are now marked with a simple \"+\" badge by their name instead of the crown."
    ]
  },
  {
    "v": "3.21.3",
    "d": "June 18, 2026",
    "changes": [
      "The Plus page now has a soft gradient backdrop to make it feel a bit more premium."
    ]
  },
  {
    "v": "3.21.2",
    "d": "June 18, 2026",
    "changes": [
      "Removed the @ mention highlighting in chat — your messages just read as plain text now."
    ]
  },
  {
    "v": "3.21.1",
    "d": "June 18, 2026",
    "changes": [
      "Buying Plus now ends with the full unlock celebration, right on the page.",
      "Cleaned up the Plus crown placement — it now sits neatly by your name."
    ]
  },
  {
    "v": "3.21.0",
    "d": "June 18, 2026",
    "changes": [
      "Buy Paula Plus right on the Plus page — pick monthly or annual and confirm, no extra popup.",
      "A \"Get Plus\" shortcut in the sidebar so upgrading is always one tap away."
    ]
  },
  {
    "v": "3.20.0",
    "d": "June 18, 2026",
    "changes": [
      "A gold crown now marks Paula Plus members in the sidebar and header.",
      "Plus members can pick an accent color — emerald, ocean, violet, amber, rose, or cyan.",
      "Brought back the animated welcome prompt."
    ]
  },
  {
    "v": "3.19.0",
    "d": "June 18, 2026",
    "changes": [
      "Paula Plus now unlocks all settings (Connections & Sounds) — theme, font size, and your account stay free for everyone.",
      "Gifted Plus arrives in real time, with an optional personal note from the team.",
      "A richer Plus page showing exactly what you get.",
      "Guests get a quick sign-up prompt to save and sync their chats.",
      "A cleaner, calmer interface and a refreshed settings icon."
    ]
  },
  {
    "v": "3.18.0",
    "d": "June 18, 2026",
    "changes": [
      "Use Paula without signing in — tap \"Continue as guest\" to try it with 3 messages a day.",
      "Guest chats are saved on your device, and move into your account when you sign up."
    ]
  },
  {
    "v": "3.17.1",
    "d": "June 18, 2026",
    "changes": [
      "Fixed the mobile layout — the sidebar is now a proper slide-in menu (tap the ☰ to open, tap outside to close) instead of a stuck strip of icons, and content fills the screen."
    ]
  },
  {
    "v": "3.17.0",
    "d": "June 18, 2026",
    "changes": [
      "Faster first load — the charting code now loads only when a chart is shown, cutting the initial download roughly in half.",
      "Less battery + data use — Paula pauses background refreshing when the tab isn’t visible, and the login ticker is cached."
    ]
  },
  {
    "v": "3.16.4",
    "d": "June 18, 2026",
    "changes": [
      "Nicer loading screen — an animated logo, the Paula wordmark, and a progress shimmer instead of a bare black screen."
    ]
  },
  {
    "v": "3.16.3",
    "d": "June 18, 2026",
    "changes": [
      "Small fixes: corrected a few theme color variables, and position sizing now explains clearly when your risk budget is too small for even one share."
    ]
  },
  {
    "v": "3.16.2",
    "d": "June 18, 2026",
    "changes": [
      "Light theme now covers the sidebar too, with a smooth color fade when you switch themes."
    ]
  },
  {
    "v": "3.16.1",
    "d": "June 18, 2026",
    "changes": [
      "Fixed compare/earnings/position-sizing not working with lowercase tickers (e.g. \"compare tsla and nvda\")."
    ]
  },
  {
    "v": "3.16.0",
    "d": "June 17, 2026",
    "changes": [
      "Annual Paula Plus — $99/year (2 months free) alongside the $9.99/mo plan.",
      "A dedicated Plus page with full plan comparison, reachable from Settings."
    ]
  },
  {
    "v": "3.15.0",
    "d": "June 17, 2026",
    "changes": [
      "Light theme — switch between dark and light in Settings → Appearance. Your choice is remembered."
    ]
  },
  {
    "v": "3.14.0",
    "d": "June 17, 2026",
    "changes": [
      "Earnings calendar — ask \"when does NVDA report earnings\" and Paula tells you the date, how soon it is, and warns if it’s close."
    ]
  },
  {
    "v": "3.13.0",
    "d": "June 17, 2026",
    "changes": [
      "The \"What’s new\" history is now collapsible — tap any version to expand its changes, with the date shown next to each version."
    ]
  },
  {
    "v": "3.12.0",
    "d": "June 17, 2026",
    "changes": [
      "Position sizing — ask \"how many shares of NVDA if I risk $200\" and Paula calculates the share count from the stop distance."
    ]
  },
  {
    "v": "3.11.0",
    "d": "June 17, 2026",
    "changes": [
      "Autopilot trailing stops — once a position is up ~3%, the stop ratchets up to lock in gains (and never moves back down)."
    ]
  },
  {
    "v": "3.10.0",
    "d": "June 17, 2026",
    "changes": [
      "Compare two stocks head-to-head — ask \"NVDA vs AMD\" or \"should I buy TSLA or RIVN\" and Paula scores both and picks a winner."
    ]
  },
  {
    "v": "3.9.8",
    "d": "June 16, 2026",
    "changes": [
      "The \"What’s new\" screen is now a full scrollable history — every version, its date, and what changed."
    ]
  },
  {
    "v": "3.9.6",
    "d": "June 16, 2026",
    "changes": [
      "New \"Hey Paula — for everything trading\" branding on the trailer and login.",
      "Free tier is a clean 3 messages per day."
    ]
  },
  {
    "v": "3.9.0",
    "d": "June 15, 2026",
    "changes": [
      "Introducing Paula Plus ($9.99/mo): unlimited messages, unlimited chats, and full access.",
      "Free tier: 3 messages a day, one chat, with Analyze & Portfolio reserved for Plus.",
      "Smooth upgrade flow with an unlock celebration.",
      "Admins can grant or revoke Plus from the admin panel."
    ]
  },
  {
    "v": "3.8.0",
    "d": "June 14, 2026",
    "changes": [
      "Maintenance mode — a clean full-screen notice when Paula is getting an upgrade.",
      "\"Look it up\" now actually searches the web for current info.",
      "Trade levels never collapse — entry, stop, and target are always distinct.",
      "Smoother chat scrolling that no longer fights you while a reply streams in."
    ]
  },
  {
    "v": "3.7.0",
    "d": "June 13, 2026",
    "changes": [
      "Portfolio-aware advice — ask about adding to or trimming a position and Paula factors in your real buying power, holdings, and risk.",
      "Sharper understanding of what you actually asked."
    ]
  },
  {
    "v": "3.5.0",
    "d": "June 11, 2026",
    "changes": [
      "Per-account trading — connect your own Alpaca keys and Paula trades your account (encrypted, private to you).",
      "Your win rate and recent trades inform Paula’s advice."
    ]
  },
  {
    "v": "3.4.0",
    "d": "June 10, 2026",
    "changes": [
      "Autopilot now scans a much wider universe — hundreds of names per cycle via fast batch fetching."
    ]
  },
  {
    "v": "3.3.0",
    "d": "June 8, 2026",
    "changes": [
      "Scanner widened to 1,000+ liquid stocks, plus a full-NYSE mode.",
      "Themed scans: energy, defense, biotech, crypto, value.",
      "Delisted, acquired, and brand-new IPO stocks filtered out — no fake scores.",
      "Redesigned welcome screen and Analyze view; new hover navigation rail.",
      "Real market data on login; live intraday (1D/5D) charts."
    ]
  },
  {
    "v": "3.2.0",
    "d": "May 28, 2026",
    "changes": [
      "Named setups — every pick comes with its thesis (pullback, breakout, oversold bounce, coiling).",
      "52-week-high & VCP detection; honest multi-position backtest.",
      "True swing trading — positions held overnight, no end-of-day force-close.",
      "Live news, web search, market-hours awareness."
    ]
  },
  {
    "v": "3.1.0",
    "d": "May 20, 2026",
    "changes": [
      "Per-chat memory — each conversation stays its own.",
      "Stop a reply mid-stream; always-on cloud hosting.",
      "Consistent scores between Analyze and chat."
    ]
  },
  {
    "v": "3.0.0",
    "d": "May 12, 2026",
    "changes": [
      "Paula reborn as a desktop app — a full swing-trading copilot.",
      "Multi-factor scoring engine: RSI, MACD, Bollinger Bands, ATR, momentum, fundamentals.",
      "Alpaca paper trading, AI news analysis, and an autopilot that trades for you."
    ]
  }
]
