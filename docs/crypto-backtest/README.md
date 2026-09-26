# Crypto backtest (Sep 26 2026)

Scripts behind `intraday_crypto.py`. `fetch.py` pulls 180 days of 5-min Alpaca bars into the
current folder; `bt.py` compares strategies; `bt2.py` compares entry/exit check speeds.
Costs: 0.25% Alpaca fee + 0.05% slippage per side. Split: first 90 days (crypto fell) to pick,
last 90 days (crypto rose) to check. 32 tokens, equal weight.

| Strategy | First 90d | Last 90d |
|---|---|---|
| Buy & hold | −19.3% (dd −33.9%) | +69.2% (dd −11.4%) |
| UTC-day noise area, 5/15/30/60-min checks | −97/−77/−62/−49% | −97/−79/−60/−38% |
| **72h-high breakout / 24h-low exit, entries hourly, exits 15 min** (live) | **−4.1% (dd −6.5%)** | **+15.2% (dd −6.5%)** |
| same, exits hourly | −4.7% (dd −12.7%) | +22.8% |
| same, entries every 5 min | −13.7% (dd −22.1%) | +40.6% |

Faster checks trade more and lose more to fees. Only 6 months of data: treat as indicative.
