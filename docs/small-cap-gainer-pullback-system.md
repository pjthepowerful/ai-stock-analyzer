# Small-Cap Gainer Pullback System — v1.0

Formalization of the "scan gainers → buy the test → sell the strength → average down if wrong" strategy, with concrete parameters and an honest assessment of each component. Educational spec for research and paper trading, not investment advice.

**Verdict up front:** Steps 1–4 formalize into a real, testable intraday momentum system — thin-edged, regime-dependent, and viable only with brutal selectivity, but coherent. Step 5 (averaging down) is not a component of that system; it is the mechanism that undoes it. Section 4 does the math, but the core problem can be stated in one sentence: steps 1–4 are a *momentum* thesis (strength persists, held pullbacks continue up), and step 5 deploys maximum capital at exactly the moment that thesis says the trade is broken.

---

## 1. Universe & Scanner

Run premarket at ~9:00 ET on premarket ranks, then refresh every 1–5 minutes from 9:30 to 11:00. Rank by % gain, take the top 20, apply filters.

| Filter | Spec | What it screens out / why it exists |
|---|---|---|
| Exchange | NASDAQ / NYSE / AMEX listed only. No OTC/pinks. | OTC has no listing standards, no LULD halt protection, endemic promotion, terrible data, and most brokers (including Alpaca) don't route it. This one filter removes the majority of outright scams. |
| Day change | ≥ +10% vs. prior close (premarket gap or intraday) | Below +10% on a small cap is noise; the ranked top-20 usually clears +15% anyway. The threshold defines "something is happening here today." |
| Price | $1.50 – $20.00 | Sub-$1.50 is the delisting-compliance zone (reverse-split candidates, S-1 machines) and the spread as a % of price is brutal. Above $20 with this cap band implies a micro-float (different game) or a name drifting toward mid-cap behavior. Sweet spot in practice: $2–$10. |
| Market cap | $50M – $500M | Below $50M is nano-cap: no institutional floor, dilution treadmill, manipulation-dominant. Above $500M moves slower and the pullback dynamics change. The friend's "$100M give or take" sits mid-band. |
| Float | 5M – 75M shares | See 1.1 — this is the most consequential filter after RVOL. |
| RVOL | ≥ 5× time-adjusted (today's cumulative volume ÷ 20-day average cumulative volume *at the same clock time*); ≥ 3× acceptable after noon | The "is anyone actually here" filter. A +25% name on RVOL 1.5 is a thin tape drifting — no participation, no exit liquidity, no follow-through. Naive RVOL (today ÷ full-day average) is useless at 9:45; it must be time-of-day adjusted. |
| Dollar volume | ≥ $10M traded before your first entry; projected ≥ $30M full-day | Your exit depends on this number, not on the chart. Position sizing in Section 3 keys off it. |
| Catalyst triage | Classify the news: real (earnings beat, FDA action, contract with a dollar figure, named strategic investor) vs. fluff (LOI, "exploring strategic alternatives," buzzword pivot) vs. none (sympathy / promo) | Not a hard filter, but a grade. Fluff/no-news gainers fade at a much higher rate and are disproportionately promotions. Real catalyst = full size eligible; fluff = half size or skip. |
| Filings flag | Active ATM agreement, effective S-3 shelf, fresh S-1 or 424B5, warrants near the money | Hazard grade, not auto-exclusion — see 5.1. A spike in a name with an active ATM is, from the CFO's chair, a financing window. |

### 1.1 Why float changes everything

Price is demand against *tradable supply*, and float is the supply. The same $2M of market buying is a +1% blip on an 80M-share float and a +15% candle straight into a halt on a 6M-share float. Everything about how these names trade scales off that ratio. Volatility and halt frequency rise inversely with float. Spreads widen as float shrinks because market makers carry more inventory risk per share. Float rotation matters: when cumulative volume exceeds the float by midday, the average holder bought *today* — there's no overhead resistance from bagholders, but everyone in the name is a fast-money renter with a finger on the sell key, which is why low-float reversals are vertical in both directions. Dilution severity is measured in percent of float, not dollars: a 4M-share ATM into a 6M float is a 66% supply increase that caps every bounce; the same ATM into a 70M float is background noise. Short-squeeze mechanics scale the same way. Practical regime split: 5–15M floats are the halt-chain lottery — quarter size, retest entries only, assume you may be locked in a halt; 15–75M is the tradable core of this system.

---

## 2. "Testing the market," formalized

The friend's "testing levels" decomposes into six named setups. First, the shared grammar, because retest quality is the actual edge:

A level is only tradable when it's **confluent** — at least two of: VWAP, prior-day high/low, premarket high, opening-range high, a whole or half dollar, a visible high-volume node. And a retest is only valid when it passes this checklist:

1. **Depth** — the pullback retraces less than ~50% of the impulse leg. Shallower is stronger.
2. **Volume signature** — pullback volume runs at half or less of the impulse leg's volume, ideally shrinking bar over bar; the resumption bar expands again. This is the single best real-vs-fake tell.
3. **Speed** — a reclaim within 1–3 bars of the touch beats a grind along the level.
4. **Location** — the whole structure sits above VWAP (for longs).
5. **Tape** — bids reload at the level rather than pulling as price approaches.

The universal *failed*-test tell: the level breaks on **expanding** volume, bounce attempts can't get back above it within 2–3 bars, and lower highs stack up beneath it. That is not a discount — it's the market announcing the test failed. It is also precisely the moment step 5 of the original strategy buys more. Hold that thought for Section 4.

### 2.1 VWAP reclaim

*Context:* A gapper loses VWAP in the first hour, bleeds, then curls back. *Trigger:* a 5-min close back above VWAP after ≥ 20 minutes below it — entered on the **retest of VWAP from above**, not the first poke through. *Stop:* the higher low that produced the reclaim, or VWAP − 1.5×ATR(5m), whichever is tighter. *Window:* 10:00–11:30, and again 13:30–15:00 (afternoon reclaims of morning gainers are a distinct, decent variant, helped by SSR if it triggered). *Real vs. fake:* real reclaims come on an RVOL uptick and VWAP then holds as support on the first retest; fakes are a single-bar poke on fading volume that closes back below within 2–3 bars — which is frequently the start of the day's fade, not a dip.

### 2.2 First pullback to a rising 9/20 EMA (5-min)

*Context:* Post-breakout impulse leg, first rest. *Trigger:* touch of the rising 9EMA (aggressive) or 20EMA (conservative) plus a break of the prior bar's high. *Stop:* the pullback low, or below the 20EMA — and if that's more than ~5% away, the setup is too loose (see 3). *Window:* 9:45–11:00; this is the bread-and-butter window of the whole system. *Real vs. fake:* volume contraction of 50%+ during the pullback with structure above VWAP is real; pullback bars printing *bigger* volume than the pole is distribution — skip. First pullback ≫ third pullback: each successive test of the same EMA carries worse odds.

### 2.3 Prior-day-high retest

*Context:* Breaks yesterday's high, comes back to it. *Trigger:* PDH holds within a tolerance of roughly half the spread plus a quarter ATR(1m); enter on reclaim of the most recent 1-min swing high. *Stop:* 1–1.5% below PDH — the support/resistance flip is the whole thesis, so a clean break of it is full invalidation. *Window:* any time, most commonly 9:45–10:45. *Real vs. fake:* a shallow, low-volume tag that bounces within 3 bars confirms the flip. A knife *through* PDH on expanding volume is a failed breakout — and in this universe a failed breakout is a short setup, not a long entry at a discount.

### 2.4 Opening-range break + retest

*Context:* Define the opening range as the first 15 minutes' high/low (use 5-min OR on the fastest names). *Trigger:* break of ORH, then enter on the **retest of ORH** — not the break itself. Chasing breaks in low floats routinely buys the top tick two seconds before an LUDP halt. *Stop:* the OR midpoint, or ORL only if the range is narrow — if ORL sits more than ~8% away, pass. *Window:* 9:45–10:30. *Real vs. fake:* a retest that holds above ORH while RVOL is still building is real; a break that closes back *inside* the range is a trap, and the trap usually resolves to the other side of the range.

### 2.5 High-of-day break

*Context:* A consolidation ledge just under HOD after a base of at least 15 minutes. *Trigger:* break of HOD on expanding 1-min volume — or, for better fills and fewer traps, the first retest of old HOD from above. *Stop:* below the consolidation base. *Window:* works all day; late-day HOD breaks (after 15:00) on day-one gainers are squeeze-prone but sit next to gap risk — take the profit, don't marry it. *Warning:* this is the setup most likely to fill you seconds before a volatility halt. Partial size, and assume you may be locked in for the reopen. *Real vs. fake:* ascending 1-min lows into the level on quiet volume tends to succeed; a fourth-or-later test of HOD on *declining* RVOL tends to fail.

### 2.6 Flag on declining volume

*Context:* Pole, then a 4–10 bar sideways/down drift, each bar's volume smaller than the last, holding above the 9/20 EMA and VWAP. *Trigger:* break of the flag's upper boundary or the prior bar's high. *Stop:* the flag low. *Window:* 9:45–11:30. Midday flags (12:00–14:00) resolve downward more often — halve size or skip. *Real vs. fake:* the volume taper *is* the setup. A "flag" with steady or growing red volume is distribution wearing a flag costume.

### 2.7 Time-of-day base rates

9:30–9:45 has the widest spreads, the most halts, and the most traps — observation only, or quarter size. 9:45–11:00 is the prime window; most of this system's expectancy lives there. 11:30–14:00 is decay: most day-one small-cap gainers print their high before noon and bleed, so fresh longs at lunch fight the tide. 14:00–15:30 is the afternoon-reclaim window (2.1). 15:30–16:00 is exit-only (Section 6).

And the honest base rate over the whole day: the majority of day-one small-cap spikes close well off their highs. The fade is the dominant tendency — which is why a large professional cohort trades this exact universe from the short side. A long system here works, if it works, through aggressive selectivity: a handful of A-grade setups per week, not a dozen entries a day. Most of the system's job is saying no.

---

## 3. Position sizing & risk

Risk unit: **R = 0.5% of equity** while the system is unproven (first ~100 live trades), 1.0% maximum thereafter. Base share count is the standard fixed-fractional formula:

```
shares = floor( equity × R% ÷ (entry − stop) )
```

Then apply three caps and take the minimum:

1. **Liquidity cap** — position ≤ 1% of 20-day average dollar volume *and* ≤ ~10% of the median 1-minute dollar volume over the last 30 minutes. This is the "can I actually get out" constraint, and it binds hard in the 5–15M float regime.
2. **Catastrophe cap** — notional ≤ 15% of equity, regardless of what the stop math allows. Reason: stops are a fiction through halts and gaps. Assume a worst case of −40% on the position (halt → reopen through your stop) and keep that outcome at ≤ ~6% of the account. This cap is what makes Section 5.3 survivable.
3. **Stop-width sanity** — if the structurally correct stop sits more than ~8% from entry, the trade doesn't fit the system. Pass; don't widen. A wide stop with tiny size in a thin name can't pay for its own slippage, and a wide stop with normal size violates the catastrophe cap. Tight stops at real levels are the whole reason to buy retests instead of chasing.

Portfolio rules: maximum 2–3 concurrent positions — these names are one trade wearing different tickers, and when small-cap momentum dies at 11:00 it dies everywhere simultaneously. Maximum 2 attempts per ticker per day; a third entry is revenge, not analysis. Daily loss limit of −2% of equity → flat and done for the day, enforced in software rather than willpower. Weekly circuit breaker at −5% → half size the following week.

---

## 4. Averaging down — steelman, teardown, least-bad version

### 4.1 The steelman (real, but narrow)

Adding at lower prices has positive expectancy only when it is a **pre-planned scale-in** — an execution tactic, not a reaction. That means: total size and the final stop are fixed *before* the first fill; tranches sit at pre-defined levels; and the risk on the *full* size at the *average* price down to the *final* stop equals one normal R. Under that definition, "averaging down" is just laddering limit orders into a support zone to improve the average entry inside a still-valid setup. It's legitimate, and Section 4.4 formalizes it.

The other places scaling into weakness genuinely works share features this universe lacks: bounded downside plus structural drift plus diversification (dollar-cost averaging a broad index), or a demonstrably mean-reverting, information-light instrument. Notice what every legitimate case has in common — a real invalidation exists, and total risk never grows *because* you're losing.

### 4.2 What the friend described is not that

"If it moves against him, he adds more money" — size conditional on being wrong. That's martingale logic, and in this specific universe it has four failure modes stacked on top of each other.

**It puts the biggest size in the worst trades, by construction.** Winners never receive the adds — they left without you. Only losers reach the lower rungs. Over a hundred trades, the position-size-weighted exposure of the account concentrates exactly in the trades that were failing. No other rule in trading achieves adverse selection this efficiently.

**It manufactures win rate and hides the cost in the tail.** Concrete numbers. Base system: 45% win rate, average winner +2R, average loser −1R → expectancy **+0.35R per trade**. Now the averaging variant on the *same signals*: most drawdowns bounce enough to escape near flat, so the printed win rate jumps to ~80% at maybe +0.4R average — but the ~20% that don't bounce are now three to seven units of size deep with no stop; call it −5R average. Expectancy: 0.8 × 0.4 − 0.2 × 5 = **−0.68R per trade**. Same entries, same tape; the sizing rule alone flipped a profitable system to a losing one. Worse, the equity curve is maximally deceptive — smooth and green for months, then one bar erases it. Which is also why "my friend does this and he's up" isn't evidence: a rare-but-total blowup mode looks exactly like a working strategy from the inside, mid-sample. Right up until it doesn't.

**The arithmetic of deep losses is not symmetric.** Down 40% needs +67% to break even; down 70% needs +233%. And in this universe, down 40% from your basis is rarely noise — it's *information*: an offering priced overnight, a catalyst negated, a promotion completed. Averaging down here isn't buying a discount; it's fading the news flow with escalating size. And yes — a stock down 40% can go down another 90%. That's a 94% total loss, and the $50–500M band produces that exact chart weekly via the mechanisms in Section 5: ATM into the bounce, reverse split, delisting, suspension.

**It contradicts the strategy's own premise.** This is the cleanest argument and the one to remember. Steps 1–4 are a momentum thesis: intraday strength persists, and pullbacks that *hold their level* continue up. If that's true, its mirror is also true — tests that *fail* continue down. Step 5 deploys the account's maximum capital at exactly the moment the system's own logic declares the trade broken. You cannot coherently believe in the entry (persistence) and the add-down (mean reversion) on the same chart in the same hour. One of them is wrong, and the strategy's entire edge depends on it being the second one.

### 4.3 The mirror image: pyramiding winners, scaling out

Pyramiding is the same conditional-sizing idea pointed the other way: add only when price *confirms* — above the entry, at pre-set levels — with the stop trailed under the *combined* position so total open risk never exceeds the original 1R. The adds are financed by open profit. The distributional consequences are the exact mirror of averaging down: win rate *drops* (more breakeven scratches when adds get shaken out), but the P&L becomes right-skewed — the biggest size rides in the best trades, and the worst case on any single trade stays ≈ −1R. Averaging down inflates win rate and left-skews the distribution with an unbounded worst case.

Over a long sample, geometric compounding settles the argument. Capital growth is punished multiplicatively by large fractional losses — a −30% account hit needs +43% to recover, −50% needs +100% — so the structure that *caps* the left tail compounds, and the structure that *fattens* it eventually meets its tail; variance drag does the rest. And under the system's own momentum premise, conditioning size on confirmation is positive selection while conditioning it on contradiction is adverse selection: pyramiding systematically concentrates capital in the trades the market is grading A, averaging down in the trades it's grading F. Selling into strength (scaling out, Section 6) is the exit-side expression of the same principle.

### 4.4 If he's going to do it anyway — the least-bad version

Convert the reaction into a plan, with eight constraints:

1. The ladder is written **before entry**: maximum 3 tranches (e.g., 40/30/30) at levels chosen in advance — the entry trigger, VWAP, PDH — never at round-number pain points invented mid-trade.
2. **Total-risk identity:** full size at the average price down to the final hard stop equals the same 1R any single trade gets. If the math demands more than 1R, the tranches shrink; the stop does not move.
3. The **final stop is real and mechanical**, below the last structural level, entered as a working order.
4. **Thesis invalidation overrides price:** a dilutive filing hits the tape, a halt-down, the catalyst is negated, or VWAP is lost on expanding volume → exit the entire stack immediately, regardless of ladder state or paper loss.
5. **One rescue per ticker per day.** Never re-laddered after a stop-out.
6. **Time stop:** if the trigger level isn't reclaimed within 60–90 minutes, out. Dead money in this universe decays.
7. **Never hold an averaged position overnight.** Section 6 explains why that specific combination is the account-ender.
8. **Journal averaged trades separately.** If after 50 occurrences their aggregate expectancy trails the plain-stop version on identical signals — and it almost certainly will — delete the rule and keep the data as tuition paid in paper.

What survives all eight constraints is no longer "averaging down." It's a scale-in entry with fixed total risk — which is the point.

---

## 5. Structural hazards of this universe

### 5.1 Dilution — the house edge

Companies in the $50–500M band mostly don't earn money; they sell stock. The spike your scanner finds is, from the CFO's chair, a financing window — the spike *is* the event that makes the offering possible. Pre-entry checks, all scriptable against SEC EDGAR full-text search in about two minutes: an effective S-3 shelf and its remaining capacity; recent 424B5 takedowns; an at-the-market (ATM) agreement disclosed in the last 10-Q or an 8-K — sales-agent names like H.C. Wainwright, Maxim, A.G.P., or Aegis on a cover page are the tell; warrants from prior deals, whose exercise prices act as supply ceilings the stock struggles through; and cash versus quarterly burn in the latest 10-Q — runway under ~2 quarters plus today's spike means an offering is imminent, plausibly at 4:05 PM today. One structural nuance: the "baby shelf" rule caps companies with public float under $75M at selling one-third of that float via S-3 in any trailing 12 months — smaller floats can't dump as much at once through the shelf, so they lean on other instruments instead. Services like DilutionTracker productize all of this; for an automated system it's an EDGAR query away.

### 5.2 Reverse splits

A reverse split is a company confessing sustained decline — usually curing the exchange's $1 minimum-bid deficiency after months below it. Post-split names statistically keep bleeding, and the classic sequence is split → price optically "healthy" → offering, now that there's a price to offer into. Freshly split names also carry artificially tiny floats, which makes them ideal pump vehicles — the same trap loaded from both sides. Treat a reverse split within the last 6 months as a hazard flag and a serial splitter (check the split history; some names have done 1-for-10 three times) as a near-disqualifier. Exchanges have recently tightened rules on serial reverse-splitters, which tells you how endemic the pattern is.

### 5.3 Trading halts

Volatility halts (LUDP): under limit-up/limit-down, roughly a 10% move inside 5 minutes for stocks over $3 (about 20% for $0.75–$3, with wider bands near the open and close) pauses trading for 5 minutes — and low floats chain them, three, four, five in a row, in either direction. While halted you can place and cancel orders but nothing executes, and the reopen is an auction that can print far beyond your stop. **Stops do not protect through halts** — that fact alone justifies the catastrophe cap in Section 3. Stop-market versus stop-limit through a flush is pick-your-poison: stop-market exits at a terrible price; stop-limit may not exit at all. Above the volatility tier sit news halts (T1) and the nightmare tier — T12-type "additional information requested" halts and SEC 12(k) suspensions, which can freeze a position for up to two weeks and historically reopen down enormously, sometimes onto the grey market where the bid is approximately a rumor. Practical rule: if a name has already halted twice in twenty minutes, an entry is a coin flip between a fill and a lockup.

### 5.4 Promotion patterns

The tells, most of which your scanner metadata already contains: a +40% move on no filing, or on fluff (an LOI, "exploring strategic alternatives," a buzzword pivot into AI/quantum/crypto via 8-K); a two-year chart on log scale shaped like a heart monitor — spike, 90% collapse, repeat — which is a serial diluter using volatility as its actual product; a premarket ramp on trivially small volume; paid-promotion disclaimers in the PR footer; sudden coordinated social chatter in a name with no institutional ownership. Lifecycle matters: day one's front side can be traded by the fast; day two's "first red day" is where trapped longs discover the exit doesn't fit everyone. The operating rule: if you can't identify the catalyst, you *are* the catalyst — the plan is your exit liquidity.

### 5.5 Liquidity and the exit problem

Entries are easy — you're buying when the crowd is buying, into a stacked bid. Exits cluster: when a level fails, everyone's stop lives within the same 2%, the bid thins at exactly the moment demand for it peaks, and 1–3% slippage on a stop-out in a 10M-float name is normal, worse in a flush. This is why "sell into strength" isn't a slogan but a liquidity statement — the bid you want only exists during green candles. Mechanics: size to the bid (Section 3's caps), use marketable limit orders, and never send a market order into a book showing less than ~$50k within 1% of the inside.

### 5.6 Small-account constraints: PDT and T+1

Margin accounts under $25k get 3 day trades per rolling 5 sessions under the pattern-day-trader rule — this system generates more signals than that, so a small account is forced to pre-commit to A-grades only, which is secretly a feature. Cash accounts dodge PDT entirely but trade only settled funds; since settlement moved to T+1 (May 2024), yesterday's sale proceeds are spendable today, so a cash account can effectively run the strategy daily at full balance — provided it never sells a position bought with still-unsettled funds (a good-faith violation). Either way, the constraint enforces the selectivity the edge requires anyway.

### 5.7 Short-sale restriction and hard-to-borrow

SSR triggers when a stock falls 10% from the prior close and lasts through the next session; shorts may then only enter on upticks, which thins the offer and mechanically helps afternoon-reclaim setups. Hard-to-borrow status — triple-digit borrow fees, scarce locates — removes short-side supply and adds squeeze fuel: HTB plus low float plus a real catalyst is where the +100% days come from, and also where crowding is worst in both directions. Log borrow status at signal time as a feature of the setup, not as a reason to be brave.

---

## 6. Exits

Default bracket, expressed in R: scale out one-third at +1R or at the first obvious liquidity pocket (round number, premarket high), and move the stop to breakeven on the remainder. Scale the second third at +2R **or into a climax** — an RVOL spike with a bar stretched more than ~2×ATR(5m) above the 9EMA; that vertical bar is precisely the "strength" the original strategy says to sell into, because it's the only moment the bid can absorb you without slippage. Trail the final third under 5-min higher lows or a 9EMA close-through, with a hard floor at VWAP.

Why the hybrid rather than pure targets or pure trailing: fixed targets truncate the right tail that pays for the month; pure trailing stops give back 5–10% per reversal in names this whippy; scaling out captures both, and — the liquidity point again — it exits when exiting is *possible* rather than when it's necessary.

Time exit: this is a morning-momentum thesis. A position that's flat and heavy at 11:30 has lost its reason to exist — cut to the runner or go flat, because midday decay (2.7) is the base rate, not the exception.

End of day: **flatten everything by 15:45–15:55, no exceptions inside this system.** The overnight gap distribution after a big green day in this universe is asymmetric by *mechanism*, not by vibes: financing prices into strength. The modal disaster is a +60% close, a 424B5 offering at a 25% discount crossing the wire at 4:05 PM, and a −35% open — with no LULD protection and skeletal books in extended hours between you and it. Upside gaps happen, but day-2 continuation is a different strategy with its own entry criteria; don't back into it by failing to sell a day trade. And the compound rule from Section 4: an averaged-down position held overnight is the single most account-lethal combination this strategy can produce — maximum size, no stop, directly exposed to the financing window.

---

## 7. Validation protocol

### 7.1 Data honesty

Survivorship bias is worse in this universe than almost anywhere else: its failures get delisted at high rates, so a long-side backtest run on today's listed names silently deletes the catastrophic losers and the results become fiction. Requirements: a point-in-time universe **including delisted tickers**; point-in-time shares outstanding and float — floats in this band change monthly via offerings, so applying today's float to 2023 dates corrupts both the scanner and every liquidity assumption; both adjusted and unadjusted prices — a name with three 1-for-10 reverse splits has adjusted "prices" that never traded, which silently breaks price filters, spread models, and RVOL; 1-minute bars including premarket, since VWAP, opening ranges, and time-adjusted RVOL are undefined on dailies; and halt data, or an LULD reconstruction from the published bands. (Polygon covers delisted tickers and both aggregate types; point-in-time float generally has to be reconstructed from filings or bought.)

### 7.2 Cost and halt modeling

Model the spread as a function of price band, float, and time of day — a flat one-cent assumption is fantasy at 9:35 on an 8M float. Fill entries at the ask plus a fraction of the spread; fill stop exits at the bid minus additional slippage of 0.5–2% beyond the level, up to 5% for sub-10M floats. Simulate halts: when a bar's move exceeds the LULD band, freeze the position for the halt window and fill at the reopen print, not at the stop price. Then stress it — double all slippage assumptions. If the edge doesn't survive doubled costs, it was never an edge; it was an artifact of optimistic fills.

### 7.3 Sample size and metrics

At least 300 trades **per setup**, across at least 18 months, spanning a hot tape and a dead one — this edge is more regime-dependent than most, and a backtest that only saw a momentum year is an advertisement, not a test. Report per setup and overall: expectancy in R after costs; profit factor (below ~1.5 after realistic costs, don't bother); maximum drawdown and its duration; win rate *jointly* with average win:loss (either number alone is decoration); worst single trade and worst single day; MAE/MFE distributions, which tell you whether the stops and targets sit where the trades actually breathe; and rolling 3-month expectancy for stability. Then run the A/B that settles Section 4 empirically: identical signals, hard-stop version versus averaging-down version — and compare the *tails* and worst-day distributions, not the means, because the means are exactly what the averaging variant is designed to flatter.

### 7.4 Forward-testing gates

Split the data by time: tune on the first ~two-thirds, validate untouched on the remainder — a strategy that needed re-tuning to survive the holdout didn't survive it. Then 2–3 months of live paper trading on real-time data, with conservatively marked fills: require price to trade *through* a limit rather than touch it, because touch-fills in thin names are the single biggest source of paper-to-live disappointment. Log real-time spreads at signal moments, every halt encountered, and rule adherence. Gate to live: paper expectancy within noise of the backtest and zero rule violations for four consecutive weeks. Then a month at quarter size before full R. Paper cannot model the psychology of an averaging ladder or true fills in a flush — those two facts are most of why the gates exist.

---

## 8. What's sound, what wipes accounts

**Sound, as formalized:** the universe itself — listed, liquid, RVOL-confirmed small caps with the OTC swamp excluded; buying defined retests instead of chasing vertical bars, which is the difference between a 1R risk at a real level and a lottery ticket at the halt line; selling into strength, which in this liquidity regime is the only time selling works properly; catalyst and filings triage; and flat by the close. With fixed-fractional risk and the caps in Section 3, steps 1–4 constitute a coherent, testable system — with the honest caveats that its raw edge is thin, strongly regime-dependent, and consists mostly of *saying no*, because the base rate of day-one spikes is the fade, which is why the professionals in this universe are so often on the other side of the trade. Whether it has positive expectancy for a given operator is exactly what Section 7 exists to answer; nothing here asserts that it does.

**Wipes accounts, in order:** (1) Step 5 as originally described — unplanned size added to failing trades in an information-driven, dilution-financed, halt-prone universe. It inverts the risk asymmetry every other component is built on, and a single occurrence can refund a quarter's worth of edge. (2) Holding overnight into the financing window. (3) Full size in the first fifteen minutes. (4) Skipping the filings check. (5) A third attempt at the same ticker on the same day. The one-line version: steps 1–4 earn in dimes and step 5 pays it back in hundreds — and a green track record from someone running step 5 is what this failure distribution looks like from the inside, mid-sample.

---

## Appendix: mapping onto Paula

The scanner is the existing gap scanner plus four additions: time-adjusted RVOL, float, dollar-volume, and a filings-hazard flag (EDGAR full-text query). Catalyst triage is a natural Groq classification pass over the PR text. The daily loss limit and entry caps mirror the autopilot's existing MAX_DAILY_ENTRIES-style parameters; the 15:45 flatten is already EOD Guardian's job; and the VWAP/EMA logic partially exists in the engine. If step 5 ever gets implemented, only the Section 4.4 scale-in variant, behind hard caps, A/B-logged against the plain-stop autopilot from day one — and the A/B verdict, not the equity curve's mood, decides whether it stays.
