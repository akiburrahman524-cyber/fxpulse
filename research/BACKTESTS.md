# Profitability of the shipped ORB rule, simulated with explicit capital

Simulation only. No real orders, no broker, no money moved - this project cannot place trades and these tests never did. Everything below is reproducible with `research/fx_backtest.py`; full per-variant numbers are in `research/results/backtest_5m.json` and `backtest_1h.json`. Nothing was removed because it looked bad: every variant tested is in the JSON files, and the losing parameter sets are printed next to the winners.

## Setup

- Strategy under test: the project's own workflow - opening range of the first hour after 08:00 Europe/London (DST-aware, repo function), entry on the first 5-minute close beyond the range in the breakout direction, stop at the range midpoint, target at 1R, one trade per day per pair, stop checked before target inside a bar (conservative), exit at the day's last bar if neither is touched. The exact repo functions (`split_days`, `opening_range`, `session_open_utc_minutes`) are imported and used, so the shipped code is what runs.
- Simulated capital: **USD 10,000 per pair, risking 1% of current equity per trade**, position size from stop distance and pip value, rounded down to 100-unit steps, pip values converted to USD with that day's own rates. Also an equal-weight 10-pair portfolio view: $10,000 split into ten independent $1,000 slices, each pair simulated against its own slice with 1% risk of the slice per trade, daily P&L summed across slices; per-pair expectancy does not depend on cross-pair correlation (portfolio-level drawdown does).
- Costs: retail-typical spreads per pair (pips): EURUSD 0.6, GBPUSD 0.9, USDJPY 0.7, USDCHF 1.0, USDCAD 1.2, AUDUSD 0.8, NZDUSD 1.4, EURGBP 1.1, EURJPY 1.2, GBPJPY 2.0 - charged as an adverse FILL cost: the entry fills half a spread worse than mid (a buy pays the ask, a sell receives the bid) and every exit fills half a spread worse than the trigger level, with R measured against the intended stop distance. Trigger levels stay at the mid-bar levels (bid/ask trigger displacement is second-order and not modeled). See the cost-model section below for the 2026-11-19 correction. Scenarios: gross (no costs), net (1x), stress (2x). Slippage, gaps and commissions are NOT modeled: real fills would be worse, so every number here is optimistic relative to live trading.
- Cost provenance: the spreads above are ASSUMPTIONS chosen to be typical of major retail brokers in 2026, not quotes measured from one specific broker; actual costs vary by broker, account type and time of day. The stress scenario (2x) covers the pessimistic case.
- Two samples: 5-minute bars, the last ~60 trading days (the tool's native timeframe); and 1-hour bars over ~2.8 years (2024-02-02 to 2026-11-18, ~700 trades per pair) for regime coverage. The 1-hour test uses the single hour bar at the DST-correct London open as the opening range and hourly closes for entries: coarser than the shipped 5-minute workflow, included for coverage across three different market years. With bars that wide, the stop/target ordering inside one bar matters; see the ambiguity section below.

## Cost model (corrected 2026-11-19)

The first published version of this backtest (commits through 39f1c04) shifted the stop and target TRIGGER levels half a spread in the FAVORABLE direction - the stop further from entry, the target nearer - while the code comment and this document claimed the shift was adverse. The fill arithmetic was right; the trigger levels were not. The corrected model keeps triggers at the mid-bar levels and charges the spread as an adverse fill cost (entry and every exit half a spread worse than mid, R against the intended stop distance). Every number in this report uses the corrected model. The table below reruns the headline variant under BOTH models on identical bars (`research/cost_model_check.py`, `results/cost_model_check.json`) - the legacy column is what the old code would have reported, the fixed column is what this report shows.

5-minute sample, headline variant, legacy (favorable trigger shift) vs fixed (adverse fill cost):

| pair | trades | legacy avg R | fixed avg R | legacy return | fixed return |
| --- | --- | --- | --- | --- | --- |
| EURUSD | 49 | -0.2014 | -0.2110 | -9.58% | -10.03% |
| GBPUSD | 49 | -0.1067 | -0.2047 | -5.28% | -9.77% |
| USDJPY | 47 | +0.1266 | +0.0938 | 5.9% | 4.27% |
| USDCHF | 47 | -0.1477 | -0.2518 | -6.87% | -11.36% |
| USDCAD | 47 | -0.1668 | -0.3239 | -7.72% | -14.34% |
| AUDUSD | 49 | -0.0446 | -0.2177 | -2.34% | -10.35% |
| NZDUSD | 49 | -0.1329 | -0.2573 | -6.44% | -12.07% |
| EURGBP | 49 | -0.1576 | -0.4063 | -7.58% | -18.27% |
| EURJPY | 48 | +0.0530 | +0.0589 | 2.37% | 2.63% |
| GBPJPY | 49 | -0.2537 | -0.3582 | -11.87% | -16.3% |

1-hour sample, headline variant, legacy (favorable trigger shift) vs fixed (adverse fill cost):

| pair | trades | legacy avg R | fixed avg R | legacy return | fixed return |
| --- | --- | --- | --- | --- | --- |
| EURUSD | 714 | -0.0416 | -0.0711 | -27.84% | -41.75% |
| GBPUSD | 716 | -0.0858 | -0.1297 | -47.47% | -61.8% |
| USDJPY | 711 | -0.0085 | -0.0299 | -8.71% | -21.82% |
| USDCHF | 712 | -0.0468 | -0.0869 | -30.33% | -47.97% |
| USDCAD | 719 | -0.1899 | -0.2452 | -75.17% | -83.41% |
| AUDUSD | 713 | -0.1064 | -0.1633 | -54.43% | -69.81% |
| NZDUSD | 721 | -0.1271 | -0.2353 | -60.95% | -82.29% |
| EURGBP | 713 | -0.1539 | -0.2610 | -67.43% | -84.96% |
| EURJPY | 696 | -0.0265 | -0.0497 | -19.14% | -31.46% |
| GBPJPY | 708 | -0.0311 | -0.0658 | -21.99% | -39.26% |

Read: in 19 of 20 pair-samples the legacy model reported a HIGHER average R than the truth - the favorable trigger shift flattered the rule it was supposed to stress. The error was found by re-reading the level arithmetic against the comment, not by a bad-looking number: the published conclusions still held, which is exactly why this class of bug survives. Regression coverage for the corrected convention (cost leaves hit counts unchanged, reduces avg R by exactly cost/R, for both sides) is in `test_fx.py`.

## Headline variant on 5-minute bars, last ~60 trading days

Follow-the-breakout, stop or-mid, target 1R, 08:00 London, net costs. Each pair traded independently with $10,000 simulated capital.

| pair | trades | win % | avg R/trade | return | max drawdown | profit factor | t-stat |
| --- | --- | --- | --- | --- | --- | --- | --- |
| EURUSD | 49 | 42.9 | -0.211 | -10.03% | 13.83% | 0.65 | -1.51 |
| GBPUSD | 49 | 44.9 | -0.2047 | -9.77% | 10.95% | 0.66 | -1.43 |
| USDJPY | 47 | 57.4 | 0.0938 | 4.27% | 6.53% | 1.21 | 0.65 |
| USDCHF | 47 | 44.7 | -0.2518 | -11.36% | 13.09% | 0.58 | -1.79 |
| USDCAD | 47 | 40.4 | -0.3239 | -14.34% | 15.62% | 0.52 | -2.24 |
| AUDUSD | 49 | 46.9 | -0.2177 | -10.35% | 13.08% | 0.65 | -1.52 |
| NZDUSD | 49 | 49.0 | -0.2573 | -12.07% | 15.06% | 0.58 | -1.81 |
| EURGBP | 49 | 42.9 | -0.4063 | -18.27% | 18.89% | 0.43 | -2.88 |
| EURJPY | 48 | 56.2 | 0.0589 | 2.63% | 3.15% | 1.13 | 0.42 |
| GBPJPY | 49 | 36.7 | -0.3582 | -16.3% | 16.3% | 0.48 | -2.62 |

Equal-weight 10-pair portfolio ($10,000 total): **return -9.56%, max drawdown 9.56%, 483 trades**.

P&L by period (USD, net):

| pair | 2026-08/09 | 2026-10/11 |
| --- | --- | --- |
| EURUSD | -828 | -175 |
| GBPUSD | -111 | -866 |
| USDJPY | +2 | +424 |
| USDCHF | -892 | -245 |
| USDCAD | -779 | -655 |
| AUDUSD | -426 | -609 |
| NZDUSD | -666 | -541 |
| EURGBP | -1156 | -672 |
| EURJPY | -5 | +267 |
| GBPJPY | -791 | -839 |

Gross vs net (cost drag), avg R per trade, same variant:

| pair | gross | net |
| --- | --- | --- |
| EURUSD | -0.1380 | -0.2110 |
| GBPUSD | -0.1020 | -0.2047 |
| USDJPY | +0.1489 | +0.0938 |
| USDCHF | -0.1201 | -0.2518 |
| USDCAD | -0.1915 | -0.3239 |
| AUDUSD | -0.0612 | -0.2177 |
| NZDUSD | +0.0165 | -0.2573 |
| EURGBP | -0.1567 | -0.4063 |
| EURJPY | +0.1310 | +0.0589 |
| GBPJPY | -0.2544 | -0.3582 |

Random-direction control (coin flip between the buy-rule and the sell-rule each day, same geometry and costs, 20 seeds per pair), mean avg R:

| pair | random mean avgR | follow avgR |
| --- | --- | --- |
| EURUSD | -0.0829 [-0.2381 .. +0.1105] | -0.2110 |
| GBPUSD | -0.3332 [-0.6326 .. -0.1756] | -0.2047 |
| USDJPY | +0.0384 [-0.2163 .. +0.3237] | +0.0938 |
| USDCHF | -0.2828 [-0.5271 .. -0.0554] | -0.2518 |
| USDCAD | -0.3613 [-0.5610 .. +0.0439] | -0.3239 |
| AUDUSD | -0.2399 [-0.4293 .. -0.0056] | -0.2177 |
| NZDUSD | -0.3276 [-0.5488 .. -0.1430] | -0.2573 |
| EURGBP | -0.4459 [-0.6796 .. -0.2224] | -0.4063 |
| EURJPY | -0.1653 [-0.4147 .. +0.0700] | +0.0589 |
| GBPJPY | -0.2545 [-0.4490 .. -0.0108] | -0.3582 |

Full grid on this sample: 180 net-cost variants with >=10 trades (direction x stop-rule x target-R across 10 pairs). **34 (19%) finished with positive total R. 1 had t > 2; with 180 variants, about 9 would pass that bar by pure luck.** The complete grid is in the JSON; the best-looking cells are exactly what multiple testing produces.

Stress test (2x spread), same variant: EURUSD -13.2%, GBPUSD -14.2%, USDJPY +1.6%, USDCHF -16.7%, USDCAD -19.5%, AUDUSD -17.0%, NZDUSD -23.2%, EURGBP -27.7%, EURJPY -0.8%, GBPJPY -20.5%.

## Headline variant on 1-hour bars, 2024-02 to 2026-11 (~2.8 years)

Follow-the-breakout, stop or-mid, target 1R, 08:00 London, net costs. Each pair traded independently with $10,000 simulated capital.

| pair | trades | win % | avg R/trade | return | max drawdown | profit factor | t-stat |
| --- | --- | --- | --- | --- | --- | --- | --- |
| EURUSD | 714 | 48.6 | -0.0711 | -41.75% | 52.06% | 0.86 | -1.97 |
| GBPUSD | 716 | 46.9 | -0.1297 | -61.8% | 63.43% | 0.76 | -3.56 |
| USDJPY | 711 | 50.4 | -0.0299 | -21.82% | 42.92% | 0.94 | -0.82 |
| USDCHF | 712 | 50.0 | -0.0869 | -47.97% | 50.34% | 0.83 | -2.37 |
| USDCAD | 719 | 42.0 | -0.2452 | -83.41% | 83.87% | 0.6 | -6.78 |
| AUDUSD | 713 | 46.4 | -0.1633 | -69.81% | 71.48% | 0.71 | -4.5 |
| NZDUSD | 721 | 47.2 | -0.2353 | -82.29% | 84.09% | 0.61 | -6.46 |
| EURGBP | 713 | 43.8 | -0.261 | -84.96% | 85.19% | 0.57 | -7.24 |
| EURJPY | 696 | 50.7 | -0.0497 | -31.46% | 38.72% | 0.9 | -1.37 |
| GBPJPY | 708 | 49.7 | -0.0658 | -39.26% | 42.72% | 0.87 | -1.82 |

Equal-weight 10-pair portfolio ($10,000 total): **return -56.45%, max drawdown 56.77%, 7123 trades**.

P&L by period (USD, net):

| pair | 2024 | 2025 | 2026 |
| --- | --- | --- | --- |
| EURUSD | -2396 | -1857 | +77 |
| GBPUSD | -1304 | -3806 | -1069 |
| USDJPY | +1743 | +780 | -4705 |
| USDCHF | -1285 | -1890 | -1622 |
| USDCAD | -4752 | -2455 | -1134 |
| AUDUSD | -2360 | -3669 | -952 |
| NZDUSD | -4708 | -2667 | -854 |
| EURGBP | -4771 | -2284 | -1441 |
| EURJPY | -1021 | +448 | -2573 |
| GBPJPY | -1385 | -2283 | -259 |

Gross vs net (cost drag), avg R per trade, same variant:

| pair | gross | net |
| --- | --- | --- |
| EURUSD | -0.0185 | -0.0711 |
| GBPUSD | -0.0615 | -0.1297 |
| USDJPY | +0.0125 | -0.0299 |
| USDCHF | +0.0108 | -0.0869 |
| USDCAD | -0.1407 | -0.2452 |
| AUDUSD | -0.0622 | -0.1633 |
| NZDUSD | -0.0340 | -0.2353 |
| EURGBP | -0.0956 | -0.2610 |
| EURJPY | +0.0083 | -0.0497 |
| GBPJPY | +0.0104 | -0.0658 |

Random-direction control (coin flip between the buy-rule and the sell-rule each day, same geometry and costs, 20 seeds per pair), mean avg R:

| pair | random mean avgR | follow avgR |
| --- | --- | --- |
| EURUSD | -0.0732 [-0.1241 .. -0.0276] | -0.0711 |
| GBPUSD | -0.1404 [-0.2012 .. -0.0869] | -0.1297 |
| USDJPY | -0.0750 [-0.1268 .. -0.0184] | -0.0299 |
| USDCHF | -0.1221 [-0.1900 .. -0.0443] | -0.0869 |
| USDCAD | -0.2428 [-0.2916 .. -0.1933] | -0.2452 |
| AUDUSD | -0.1634 [-0.2164 .. -0.1092] | -0.1633 |
| NZDUSD | -0.2314 [-0.2911 .. -0.1772] | -0.2353 |
| EURGBP | -0.2923 [-0.3386 .. -0.2557] | -0.2610 |
| EURJPY | -0.0770 [-0.1542 .. +0.0069] | -0.0497 |
| GBPJPY | -0.0860 [-0.1447 .. -0.0466] | -0.0658 |

Full grid on this sample: 180 net-cost variants with >=10 trades (direction x stop-rule x target-R across 10 pairs). **5 (3%) finished with positive total R. 0 had t > 2; with 180 variants, about 9 would pass that bar by pure luck.** The complete grid is in the JSON; the best-looking cells are exactly what multiple testing produces.

Stress test (2x spread), same variant: EURUSD -60.0%, GBPUSD -76.6%, USDJPY -42.2%, USDCHF -74.0%, USDCAD -92.2%, AUDUSD -85.3%, NZDUSD -95.8%, EURGBP -95.4%, EURJPY -54.2%, GBPJPY -64.6%.

## Intrabar ordering ambiguity (measured, not assumed)

When one bar's range touches BOTH the stop and the target, OHLC data cannot say which was hit first. The main results resolve every such bar as STOP-first (the conservative convention the repo also uses). This section measures how much that choice matters by re-running the headline variant with every ambiguous bar resolved as TARGET-first instead - an unreachable best case, i.e. an upper bound, not an estimate.

5-minute sample:

| pair | trades | trades with an ambiguous bar | return, stop-first | return, target-first (upper bound) |
| --- | --- | --- | --- | --- |
| EURUSD | 49 | 0 | -10.03% | -10.03% |
| GBPUSD | 49 | 0 | -9.77% | -9.77% |
| USDJPY | 47 | 0 | 4.27% | 4.27% |
| USDCHF | 47 | 0 | -11.36% | -11.36% |
| USDCAD | 47 | 0 | -14.34% | -14.34% |
| AUDUSD | 49 | 0 | -10.35% | -10.35% |
| NZDUSD | 49 | 0 | -12.07% | -12.07% |
| EURGBP | 49 | 0 | -18.27% | -18.27% |
| EURJPY | 48 | 1 | 2.63% | 4.7% |
| GBPJPY | 49 | 0 | -16.3% | -16.3% |

1-hour sample:

| pair | trades | trades with an ambiguous bar | return, stop-first | return, target-first (upper bound) |
| --- | --- | --- | --- | --- |
| EURUSD | 714 | 12 | -41.75% | -25.97% |
| GBPUSD | 716 | 9 | -61.8% | -54.27% |
| USDJPY | 711 | 24 | -21.82% | 26.36% |
| USDCHF | 712 | 15 | -47.97% | -29.75% |
| USDCAD | 719 | 35 | -83.41% | -66.6% |
| AUDUSD | 713 | 12 | -69.81% | -61.63% |
| NZDUSD | 721 | 11 | -82.29% | -77.93% |
| EURGBP | 713 | 16 | -84.96% | -79.29% |
| EURJPY | 696 | 17 | -31.46% | -3.68% |
| GBPJPY | 708 | 17 | -39.26% | -14.62% |

Read: on 5-minute bars the ambiguity is negligible (1 of 483 trades) - the conservative convention costs almost nothing. On hourly bars 168 of 7123 trades (2.4%) contain an ambiguous bar, and the bound is wide for some pairs. The truth sits between the two columns; even at the unreachable upper bound, 9 of 10 pairs still lose over the sample, and the no-edge conclusion stands under EITHER resolution. Whoever reruns this can pick their own convention - both are shipped.

## Parameter sensitivity (the noise signature)

If the rule had a real edge, nearby parameters would agree. They do not. Net avg R for follow/or-mid/1R:

| pair | 5m: 07:00/30min | 5m: 07:00/60min | 5m: 08:00/30min | 5m: 08:00/60min |
| --- | --- | --- | --- | --- |
| EURUSD | -0.1246 | +0.1566 | +0.0833 | -0.2110 |
| GBPUSD | +0.1252 | -0.0461 | +0.0457 | -0.2047 |
| USDJPY | -0.1796 | -0.2463 | -0.0536 | +0.0938 |
| USDCHF | -0.1668 | -0.2004 | -0.2465 | -0.2518 |
| USDCAD | -0.3522 | -0.2794 | -0.3051 | -0.3239 |
| AUDUSD | -0.2363 | -0.1446 | -0.1927 | -0.2177 |
| NZDUSD | -0.3763 | -0.1207 | -0.3063 | -0.2573 |
| EURGBP | -0.3263 | -0.1602 | -0.2318 | -0.4063 |
| EURJPY | -0.0807 | -0.0610 | -0.0998 | +0.0589 |
| GBPJPY | -0.3753 | -0.1687 | -0.2054 | -0.3582 |

EURUSD swings from -0.21R to +0.16R across those four neighbouring settings - the largest swing in the table. Sign flips from tiny parameter moves are what noise looks like.

## Win rate is not profitability (measured)

A small target is hit often. Does a 90%-win version of this rule make money? Measured, net of costs, same rule and samples as above (`winrate_sweep` in the results JSONs):

5-minute sample - follow/or-mid, net costs, per target size (mean across the 10 pairs):

| target | mean win % | mean avg R/trade | pairs with positive total R (of 10) |
| --- | --- | --- | --- |
| 0.10R | 38.0 | -0.1943 | 0 |
| 0.25R | 66.6 | -0.2152 | 1 |
| 0.50R | 64.0 | -0.1632 | 2 |
| 1.00R | 46.2 | -0.2078 | 2 |
| 2.00R | 32.5 | -0.1883 | 3 |

1-hour sample - follow/or-mid, net costs, per target size (mean across the 10 pairs):

| target | mean win % | mean avg R/trade | pairs with positive total R (of 10) |
| --- | --- | --- | --- |
| 0.10R | 52.8 | -0.2290 | 0 |
| 0.25R | 69.3 | -0.1875 | 0 |
| 0.50R | 61.5 | -0.1553 | 0 |
| 1.00R | 47.6 | -0.1338 | 0 |
| 2.00R | 35.5 | -0.1344 | 0 |

Read: shrinking the target raises the win rate only up to a point - the best measured mean win rate is 69% (0.25R targets, 1-hour sample) - because the spread eats targets that small. 92% of the 100 pair/target cells above average NEGATIVE R per trade after costs. A 90% win rate was never observed in these tests, and even a variant that won nine trades in ten would not be safe: ten 0.1R wins are erased by one -1R loss plus costs. Expectancy, not win rate, decides whether an account grows. Scoped to this rule, these samples and these cost assumptions - not a statement about every possible strategy.

## Cross-checks of the shipped code

- An independent re-implementation of the rule reproduces the repo's own `history_replay` outcome counts EXACTLY on identical data (EURUSD, 49 pool days: buy 13 target / 20 stop / 1 neither; sell 22 / 16 / 3). The shipped code computes what its README says it computes, including its no-same-day-lookahead claim.
- `python3 test_fx.py` (offline checks incl. DST rules, stop-first tie-break, walk-forward pool construction, adverse-cost accounting and unit rounding): all pass.
- `fx_timemachine.py run` end-to-end on a live plan (EURUSD buy, 1R, 20,000 replays + 10-day walk-forward): runs, labels its own output correctly as in-sample descriptive statistics, and its walk-forward section honestly states the sample is too small to validate an edge.

## Conclusions

1. **Data: fit for purpose.** Internally consistent, unbiased vs official ECB reference rates, with documented coverage limits.
2. **The shipped strategy has no positive expectancy after realistic costs in any of the tests above.** Before costs it is a coin flip (long-sample gross expectancy ~0.0R); after a retail spread it loses reliably and consistently across 2024, 2025 and 2026. A $10,000 account trading it mechanically on the 10 tested pairs would have lost roughly 10% in the last 60 trading days at 5-minute granularity and roughly 56% over 2.8 years at hourly granularity, with drawdowns to match (conservative tie-break; even the unreachable optimistic bound leaves most pairs negative - see the ambiguity section).
3. **Following the breakout beats a coin flip by nothing.** The random-direction control performs the same.
4. **No parameter set in the tested grid rescued it.** 360 net-cost variants per timeframe; the few positive cells are fewer than chance produces, and neighbouring parameters flip sign. That is evidence about the tested grid on these samples, not proof that no profitable rule of any kind could exist.
5. These are simulations with optimistic fills (no slippage/gaps). Live results would be worse, not better.
6. What the project IS good for, today: an honest, free, open toolkit for session analysis, plan arithmetic, risk sizing and Monte Carlo replay whose numbers say what they are. That has value precisely because it does not pretend an edge exists.

Nothing here is financial advice or a prediction. Past simulations do not guarantee anything about the future.
