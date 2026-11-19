# Profitability of the shipped ORB rule, simulated with explicit capital

Simulation only. No real orders, no broker, no money moved - this project cannot place trades and these tests never did. Everything below is reproducible with `research/fx_backtest.py`; full per-variant numbers are in `research/results/backtest_5m.json` and `backtest_1h.json`. Nothing was removed because it looked bad: every variant tested is in the JSON files, and the losing parameter sets are printed next to the winners.

## Setup

- Strategy under test: the project's own workflow - opening range of the first hour after 08:00 Europe/London (DST-aware, repo function), entry on the first 5-minute close beyond the range in the breakout direction, stop at the range midpoint, target at 1R, one trade per day per pair, stop checked before target inside a bar (conservative), exit at the day's last bar if neither is touched. The exact repo functions (`split_days`, `opening_range`, `session_open_utc_minutes`) are imported and used, so the shipped code is what runs.
- Simulated capital: **USD 10,000 per pair, risking 1% of current equity per trade**, position size from stop distance and pip value, rounded down to 100-unit steps, pip values converted to USD with that day's own rates. Also an equal-weight 10-pair portfolio view: $10,000 split into ten independent $1,000 slices, each pair simulated against its own slice with 1% risk of the slice per trade, daily P&L summed across slices; per-pair expectancy does not depend on cross-pair correlation (portfolio-level drawdown does).
- Costs: retail-typical spreads per pair (pips): EURUSD 0.6, GBPUSD 0.9, USDJPY 0.7, USDCHF 1.0, USDCAD 1.2, AUDUSD 0.8, NZDUSD 1.4, EURGBP 1.1, EURJPY 1.2, GBPJPY 2.0 - applied adversely at entry AND exit (the repo's own convention). Scenarios: gross (no costs), net (1x), stress (2x). Slippage, gaps and commissions are NOT modeled: real fills would be worse, so every number here is optimistic relative to live trading.
- Cost provenance: the spreads above are ASSUMPTIONS chosen to be typical of major retail brokers in 2026, not quotes measured from one specific broker; actual costs vary by broker, account type and time of day. The stress scenario (2x) covers the pessimistic case.
- Two samples: 5-minute bars, the last ~60 trading days (the tool's native timeframe); and 1-hour bars over ~2.8 years (2024-02-02 to 2026-11-18, ~700 trades per pair) for regime coverage. The 1-hour test uses the single hour bar at the DST-correct London open as the opening range and hourly closes for entries: coarser than the shipped 5-minute workflow, included for coverage across three different market years. With bars that wide, the stop/target ordering inside one bar matters; see the ambiguity section below.

## Headline variant on 5-minute bars, last ~60 trading days

Follow-the-breakout, stop or-mid, target 1R, 08:00 London, net costs. Each pair traded independently with $10,000 simulated capital.

| pair | trades | win % | avg R/trade | return | max drawdown | profit factor | t-stat |
| --- | --- | --- | --- | --- | --- | --- | --- |
| EURUSD | 49 | 42.9 | -0.2014 | -9.6% | 13.13% | 0.64 | -1.54 |
| GBPUSD | 49 | 49.0 | -0.1067 | -5.29% | 6.97% | 0.79 | -0.82 |
| USDJPY | 47 | 59.6 | 0.1266 | 5.92% | 4.39% | 1.31 | 0.93 |
| USDCHF | 47 | 48.9 | -0.1477 | -6.87% | 8.38% | 0.7 | -1.19 |
| USDCAD | 47 | 46.8 | -0.1668 | -7.72% | 9.0% | 0.69 | -1.29 |
| AUDUSD | 49 | 55.1 | -0.0446 | -2.34% | 6.98% | 0.9 | -0.36 |
| NZDUSD | 49 | 53.1 | -0.1329 | -6.44% | 10.76% | 0.7 | -1.21 |
| EURGBP | 49 | 53.1 | -0.1576 | -7.58% | 9.51% | 0.66 | -1.38 |
| EURJPY | 48 | 56.2 | 0.053 | 2.37% | 2.97% | 1.12 | 0.4 |
| GBPJPY | 49 | 40.8 | -0.2537 | -11.87% | 11.87% | 0.56 | -2.01 |

Equal-weight 10-pair portfolio ($10,000 total): **return -4.94%, max drawdown 4.96%, 483 trades**.

P&L by period (USD, net):

| pair | 2026-08/09 | 2026-10/11 |
| --- | --- | --- |
| EURUSD | -783 | -176 |
| GBPUSD | -83 | -447 |
| USDJPY | +204 | +387 |
| USDCHF | -633 | -54 |
| USDCAD | -333 | -439 |
| AUDUSD | -198 | -36 |
| NZDUSD | -362 | -282 |
| EURGBP | -474 | -284 |
| EURJPY | -2 | +239 |
| GBPJPY | -721 | -467 |

Gross vs net (cost drag), avg R per trade, same variant:

| pair | gross | net |
| --- | --- | --- |
| EURUSD | -0.1380 | -0.2014 |
| GBPUSD | -0.1020 | -0.1067 |
| USDJPY | +0.1489 | +0.1266 |
| USDCHF | -0.1201 | -0.1477 |
| USDCAD | -0.1915 | -0.1668 |
| AUDUSD | -0.0612 | -0.0446 |
| NZDUSD | +0.0165 | -0.1329 |
| EURGBP | -0.1567 | -0.1576 |
| EURJPY | +0.1310 | +0.0530 |
| GBPJPY | -0.2544 | -0.2537 |

Random-direction control (coin flip between the buy-rule and the sell-rule each day, same geometry and costs, 20 seeds per pair), mean avg R:

| pair | random mean avgR | follow avgR |
| --- | --- | --- |
| EURUSD | -0.0776 [-0.2273 .. +0.1080] | -0.2014 |
| GBPUSD | -0.2453 [-0.5700 .. -0.1158] | -0.1067 |
| USDJPY | +0.0576 [-0.2103 .. +0.3596] | +0.1266 |
| USDCHF | -0.1747 [-0.3603 .. +0.0463] | -0.1477 |
| USDCAD | -0.2217 [-0.3748 .. +0.1527] | -0.1668 |
| AUDUSD | -0.0292 [-0.1538 .. +0.1466] | -0.0446 |
| NZDUSD | -0.2035 [-0.3562 .. +0.0041] | -0.1329 |
| EURGBP | -0.2092 [-0.4398 .. -0.0294] | -0.1576 |
| EURJPY | -0.1519 [-0.3868 .. +0.0638] | +0.0530 |
| GBPJPY | -0.1324 [-0.3221 .. +0.1080] | -0.2537 |

Full grid on this sample: 180 net-cost variants with >=10 trades (direction x stop-rule x target-R across 10 pairs). **45 (25%) finished with positive total R. 1 had t > 2; with 180 variants, about 9 would pass that bar by pure luck.** The complete grid is in the JSON; the best-looking cells are exactly what multiple testing produces.

Stress test (2x spread), same variant: EURUSD -11.9%, GBPUSD -5.4%, USDJPY +4.9%, USDCHF -9.3%, USDCAD -6.8%, AUDUSD -1.7%, NZDUSD -8.5%, EURGBP -6.1%, EURJPY -0.8%, GBPJPY -14.6%.

## Headline variant on 1-hour bars, 2024-02 to 2026-11 (~2.8 years)

Follow-the-breakout, stop or-mid, target 1R, 08:00 London, net costs. Each pair traded independently with $10,000 simulated capital.

| pair | trades | win % | avg R/trade | return | max drawdown | profit factor | t-stat |
| --- | --- | --- | --- | --- | --- | --- | --- |
| EURUSD | 714 | 50.0 | -0.0416 | -27.88% | 41.68% | 0.91 | -1.21 |
| GBPUSD | 716 | 48.7 | -0.0858 | -47.51% | 49.64% | 0.83 | -2.51 |
| USDJPY | 711 | 51.2 | -0.0085 | -8.71% | 35.96% | 0.98 | -0.25 |
| USDCHF | 712 | 51.7 | -0.0468 | -30.37% | 35.95% | 0.9 | -1.4 |
| USDCAD | 719 | 43.8 | -0.1899 | -75.22% | 76.14% | 0.65 | -5.78 |
| AUDUSD | 713 | 48.8 | -0.1064 | -54.47% | 58.9% | 0.78 | -3.23 |
| NZDUSD | 721 | 51.2 | -0.1271 | -60.99% | 64.28% | 0.72 | -4.2 |
| EURGBP | 713 | 47.5 | -0.1539 | -67.46% | 68.45% | 0.68 | -4.95 |
| EURJPY | 696 | 51.4 | -0.0265 | -19.12% | 30.6% | 0.94 | -0.78 |
| GBPJPY | 708 | 51.1 | -0.0311 | -22.02% | 26.63% | 0.93 | -0.93 |

Equal-weight 10-pair portfolio ($10,000 total): **return -41.38%, max drawdown 41.89%, 7123 trades**.

P&L by period (USD, net):

| pair | 2024 | 2025 | 2026 |
| --- | --- | --- | --- |
| EURUSD | -1371 | -1790 | +373 |
| GBPUSD | -531 | -3253 | -968 |
| USDJPY | +2298 | +1310 | -4479 |
| USDCHF | -556 | -1174 | -1307 |
| USDCAD | -3862 | -2484 | -1176 |
| AUDUSD | -734 | -3794 | -919 |
| NZDUSD | -3047 | -2095 | -958 |
| EURGBP | -3463 | -1761 | -1522 |
| EURJPY | -593 | +795 | -2114 |
| GBPJPY | -794 | -1660 | +251 |

Gross vs net (cost drag), avg R per trade, same variant:

| pair | gross | net |
| --- | --- | --- |
| EURUSD | -0.0185 | -0.0416 |
| GBPUSD | -0.0615 | -0.0858 |
| USDJPY | +0.0125 | -0.0085 |
| USDCHF | +0.0108 | -0.0468 |
| USDCAD | -0.1407 | -0.1899 |
| AUDUSD | -0.0622 | -0.1064 |
| NZDUSD | -0.0340 | -0.1271 |
| EURGBP | -0.0956 | -0.1539 |
| EURJPY | +0.0083 | -0.0265 |
| GBPJPY | +0.0104 | -0.0311 |

Random-direction control (coin flip between the buy-rule and the sell-rule each day, same geometry and costs, 20 seeds per pair), mean avg R:

| pair | random mean avgR | follow avgR |
| --- | --- | --- |
| EURUSD | -0.0463 [-0.0910 .. -0.0099] | -0.0416 |
| GBPUSD | -0.0953 [-0.1483 .. -0.0476] | -0.0858 |
| USDJPY | -0.0499 [-0.0946 .. +0.0066] | -0.0085 |
| USDCHF | -0.0753 [-0.1438 .. -0.0119] | -0.0468 |
| USDCAD | -0.1803 [-0.2188 .. -0.1252] | -0.1899 |
| AUDUSD | -0.1030 [-0.1520 .. -0.0553] | -0.1064 |
| NZDUSD | -0.1304 [-0.1773 .. -0.0810] | -0.1271 |
| EURGBP | -0.1600 [-0.1943 .. -0.1184] | -0.1539 |
| EURJPY | -0.0492 [-0.1299 .. +0.0304] | -0.0265 |
| GBPJPY | -0.0522 [-0.1083 .. -0.0153] | -0.0311 |

Full grid on this sample: 180 net-cost variants with >=10 trades (direction x stop-rule x target-R across 10 pairs). **22 (12%) finished with positive total R. 0 had t > 2; with 180 variants, about 9 would pass that bar by pure luck.** The complete grid is in the JSON; the best-looking cells are exactly what multiple testing produces.

Stress test (2x spread), same variant: EURUSD -45.3%, GBPUSD -56.8%, USDJPY -17.7%, USDCHF -46.2%, USDCAD -74.8%, AUDUSD -62.8%, NZDUSD -76.9%, EURGBP -74.0%, EURJPY -32.6%, GBPJPY -32.6%.

## Intrabar ordering ambiguity (measured, not assumed)

When one bar's range touches BOTH the stop and the target, OHLC data cannot say which was hit first. The main results resolve every such bar as STOP-first (the conservative convention the repo also uses). This section measures how much that choice matters by re-running the headline variant with every ambiguous bar resolved as TARGET-first instead - an unreachable best case, i.e. an upper bound, not an estimate.

5-minute sample:

| pair | trades | trades with an ambiguous bar | return, stop-first | return, target-first (upper bound) |
| --- | --- | --- | --- | --- |
| EURUSD | 49 | 0 | -9.6% | -9.6% |
| GBPUSD | 49 | 0 | -5.29% | -5.29% |
| USDJPY | 47 | 0 | 5.92% | 5.92% |
| USDCHF | 47 | 0 | -6.87% | -6.87% |
| USDCAD | 47 | 0 | -7.72% | -7.72% |
| AUDUSD | 49 | 0 | -2.34% | -2.34% |
| NZDUSD | 49 | 0 | -6.44% | -6.44% |
| EURGBP | 49 | 0 | -7.58% | -7.58% |
| EURJPY | 48 | 1 | 2.37% | 4.3% |
| GBPJPY | 49 | 0 | -11.87% | -11.87% |

1-hour sample:

| pair | trades | trades with an ambiguous bar | return, stop-first | return, target-first (upper bound) |
| --- | --- | --- | --- | --- |
| EURUSD | 714 | 13 | -27.88% | -7.97% |
| GBPUSD | 716 | 7 | -47.51% | -40.49% |
| USDJPY | 711 | 22 | -8.71% | 38.18% |
| USDCHF | 712 | 15 | -30.37% | -9.19% |
| USDCAD | 719 | 41 | -75.22% | -49.4% |
| AUDUSD | 713 | 13 | -54.47% | -42.65% |
| NZDUSD | 721 | 11 | -60.99% | -53.51% |
| EURGBP | 713 | 23 | -67.46% | -53.01% |
| EURJPY | 696 | 16 | -19.12% | 8.79% |
| GBPJPY | 708 | 14 | -22.02% | 0.14% |

Read: on 5-minute bars the ambiguity is negligible (1 trade in 483) - the conservative convention costs nothing. On hourly bars 175 of 7,123 trades (2.5%) contain an ambiguous bar, and the bound is wide for a few JPY pairs (USDJPY -8.7% to +38.2%). The truth sits between the two columns; even at the unreachable upper bound, 7 of 10 pairs still lose 8-53% over the sample, and the no-edge conclusion stands under EITHER resolution. Whoever reruns this can pick their own convention - both are shipped.

## Parameter sensitivity (the noise signature)

If the rule had a real edge, nearby parameters would agree. They do not. Net avg R for follow/or-mid/1R:

| pair | 5m: 07:00/30min | 5m: 07:00/60min | 5m: 08:00/30min | 5m: 08:00/60min |
| --- | --- | --- | --- | --- |
| EURUSD | -0.0727 | +0.2288 | +0.1124 | -0.2014 |
| GBPUSD | +0.2512 | +0.0338 | +0.1178 | -0.1067 |
| USDJPY | -0.1683 | -0.1540 | -0.0144 | +0.1266 |
| USDCHF | -0.0314 | -0.0562 | -0.1256 | -0.1477 |
| USDCAD | -0.1876 | -0.2427 | -0.2165 | -0.1668 |
| AUDUSD | -0.2072 | -0.0923 | -0.0561 | -0.0446 |
| NZDUSD | -0.0909 | +0.0242 | -0.1457 | -0.1329 |
| EURGBP | -0.1443 | -0.0187 | -0.0233 | -0.1576 |
| EURJPY | -0.0437 | -0.0180 | -0.0888 | +0.0530 |
| GBPJPY | -0.3178 | -0.1515 | -0.1452 | -0.2537 |

EURUSD goes from +0.23R to -0.20R by moving the session anchor one hour; GBPUSD from +0.25R to -0.11R. Sign flips from tiny parameter moves are what noise looks like.

## Cross-checks of the shipped code

- An independent re-implementation of the rule reproduces the repo's own `history_replay` outcome counts EXACTLY on identical data (EURUSD, 49 pool days: buy 13 target / 20 stop / 1 neither; sell 22 / 16 / 3). The shipped code computes what its README says it computes, including its no-same-day-lookahead claim.
- `python3 test_fx.py` (28 offline checks incl. DST rules, stop-first tie-break, walk-forward pool construction): all pass.
- `fx_timemachine.py run` end-to-end on a live plan (EURUSD buy, 1R, 20,000 replays + 10-day walk-forward): runs, labels its own output correctly as in-sample descriptive statistics, and its walk-forward section honestly states the sample is too small to validate an edge.

## Conclusions

1. **Data: fit for purpose.** Internally consistent, unbiased vs official ECB reference rates, with documented coverage limits.
2. **The shipped strategy has no positive expectancy after realistic costs in any meaningful test.** Before costs it is a coin flip (long-sample gross expectancy ~0.0R); after a retail spread it loses reliably and consistently across 2024, 2025 and 2026. A $10,000 account trading it mechanically on the 10 tested pairs would have lost roughly 5% in the last 60 trading days at 5-minute granularity and roughly 41% over 2.8 years at hourly granularity, with drawdowns to match (conservative tie-break; even the unreachable optimistic bound leaves 7 of 10 pairs negative - see the ambiguity section).
3. **Following the breakout beats a coin flip by nothing.** The random-direction control performs the same.
4. **No parameter set rescued it.** 360 net-cost variants per timeframe; the few positive cells are fewer than chance produces, and neighbouring parameters flip sign.
5. These are simulations with optimistic fills (no slippage/gaps). Live results would be worse, not better.
6. What the project IS good for, today: an honest, free, open toolkit for session analysis, plan arithmetic, risk sizing and Monte Carlo replay whose numbers say what they are. That has value precisely because it does not pretend an edge exists.

Nothing here is financial advice or a prediction. Past simulations do not guarantee anything about the future.
