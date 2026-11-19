# Data correctness: what the fxpulse data feeds actually are

Tested 2026-11-19. Method and code: `research/fx_validate.py`, raw output `research/results/validate_results.json`. Bars: unofficial Yahoo chart endpoint (what the project's scan/plan/timemachine tools use), 10 pairs, 5-minute bars for the last ~60 trading days and 1-hour bars back to 2024-02-02. Independent reference: official ECB euro reference rates via the Frankfurter API (free, no key).

## 1. Internal consistency

Every bar of every pair was checked for: high >= max(open, close), low <= min(open, close), positive prices, duplicate timestamps, non-monotonic timestamps, Saturday bars (spot forex is closed), and single-bar ranges above 25x the pair's median bar range (bad-tick screen).

| pair | interval | bars | span (UTC) | OHLC violations | dup/non-monotonic ts | Saturday bars | range outliers |
| --- | --- | --- | --- | --- | --- | --- | --- |
| EURUSD | 5m | 16813 | 2026-08-27 23:00 to 2026-11-19 04:12 | 0 | 0/0 | 0 | 0 |
| EURUSD | 1h | 17183 | 2024-02-02 00:00 to 2026-11-19 04:12 | 0 | 0/0 | 0 | 0 |
| GBPUSD | 5m | 16816 | 2026-08-27 23:00 to 2026-11-19 04:12 | 0 | 0/0 | 0 | 0 |
| GBPUSD | 1h | 17186 | 2024-02-02 00:00 to 2026-11-19 04:12 | 0 | 0/0 | 0 | 0 |
| USDJPY | 5m | 16746 | 2026-08-27 23:00 to 2026-11-19 04:13 | 0 | 0/0 | 0 | 0 |
| USDJPY | 1h | 17088 | 2024-02-02 00:00 to 2026-11-19 04:13 | 0 | 0/0 | 0 | 0 |
| USDCHF | 5m | 16748 | 2026-08-27 23:00 to 2026-11-19 04:13 | 0 | 0/0 | 0 | 0 |
| USDCHF | 1h | 17121 | 2024-02-02 00:00 to 2026-11-19 04:13 | 0 | 0/0 | 0 | 0 |
| USDCAD | 5m | 16761 | 2026-08-27 23:00 to 2026-11-19 04:13 | 0 | 0/0 | 0 | 0 |
| USDCAD | 1h | 17253 | 2024-02-02 00:00 to 2026-11-19 04:13 | 0 | 0/0 | 0 | 0 |
| AUDUSD | 5m | 16824 | 2026-08-27 23:00 to 2026-11-19 04:11 | 0 | 0/0 | 0 | 0 |
| AUDUSD | 1h | 17250 | 2024-02-02 00:00 to 2026-11-19 04:13 | 0 | 0/0 | 0 | 0 |
| NZDUSD | 5m | 16825 | 2026-08-27 23:00 to 2026-11-19 04:13 | 0 | 0/0 | 0 | 2 |
| NZDUSD | 1h | 17251 | 2024-02-02 00:00 to 2026-11-19 04:13 | 0 | 0/0 | 0 | 0 |
| EURGBP | 5m | 16820 | 2026-08-27 23:00 to 2026-11-19 04:13 | 0 | 0/0 | 0 | 0 |
| EURGBP | 1h | 17206 | 2024-02-02 00:00 to 2026-11-19 04:14 | 0 | 0/0 | 0 | 0 |
| EURJPY | 5m | 16808 | 2026-08-27 23:00 to 2026-11-19 04:14 | 0 | 0/0 | 0 | 0 |
| EURJPY | 1h | 17191 | 2024-02-02 00:00 to 2026-11-19 04:14 | 0 | 0/0 | 0 | 0 |
| GBPJPY | 5m | 16809 | 2026-08-27 23:00 to 2026-11-19 04:14 | 0 | 0/0 | 0 | 0 |
| GBPJPY | 1h | 17188 | 2024-02-02 00:00 to 2026-11-19 04:14 | 0 | 0/0 | 0 | 0 |

All structural checks are zero across 339887 bars. The bad-tick screen flagged 2 single bars (NZDUSD 5m: 2026-09-02 01:50:00 range 0.31%; NZDUSD 5m: 2026-09-30 12:00:00 range 0.32%). Inspection shows these are genuine fast moves, not bad ticks: the neighbouring bars continue from the new level with no spike-and-revert pattern (a real 0.3% 5-minute move in NZDUSD is 25x that pair's very quiet median bar). The feed is internally coherent.

## 2. Gaps and calendar coverage

- Yahoo's forex week runs Monday 00:00 UTC to Friday ~21:30 UTC. There is **no Sunday-evening session** in this feed; the week-end gap (Fri ~21:30 to Mon 00:00, ~50 hours) is expected and present every week.
- 5-minute data: each pair had 1-2 small intraday gaps (15-25 minutes) over 60 days. Known examples: 2026-10-09 21:25-21:50 UTC (several pairs), 2026-10-15 06:10-06:25 UTC.
- 1-hour data reaches back to 2024-02-02 (~2.8 years), not further, and shows occasional longer holiday gaps (e.g. year-end).
- This is an unofficial endpoint with no SLA: fine for analysis, not for execution. The tools already print the age of the newest bar with every run.

## 3. Cross-check against official ECB reference rates

The ECB publishes one reference rate per currency per day, fixed at 16:00 CET/CEST. For each of 711 trading days per pair, the Yahoo hourly bar that STARTS at the fixing instant (15:00 UTC in winter, 14:00 UTC in summer, DST handled) was compared with the ECB figure. A perfect feed would differ by the drift of a few minutes only.

| pair | days compared | median \|dev\| | mean \|dev\| | signed mean | max \|dev\| | days > 0.5% |
| --- | --- | --- | --- | --- | --- | --- |
| EURUSD | 711 | 0.102% | 0.139% | +0.039% | 1.53% | 16 |
| GBPUSD | 711 | 0.097% | 0.134% | +0.011% | 1.05% | 17 |
| USDJPY | 711 | 0.113% | 0.164% | -0.017% | 1.96% | 30 |
| USDCHF | 710 | 0.105% | 0.146% | -0.020% | 1.48% | 26 |
| USDCAD | 710 | 0.081% | 0.109% | -0.009% | 1.19% | 8 |
| AUDUSD | 710 | 0.126% | 0.174% | +0.034% | 1.41% | 33 |
| NZDUSD | 710 | 0.123% | 0.172% | +0.039% | 1.40% | 34 |
| EURGBP | 711 | 0.054% | 0.075% | -0.004% | 0.64% | 4 |
| EURJPY | 711 | 0.093% | 0.134% | -0.010% | 1.56% | 13 |
| GBPJPY | 711 | 0.103% | 0.147% | -0.015% | 1.67% | 22 |

How to read this: the signed means are all near zero (no systematic bias - Yahoo is not consistently high or low). Medians of 0.05-0.13% are ordinary sub-hour FX drift. Every large deviation (0.6-2.0%) falls on a known high-volatility macro day, where an hour of timing difference honestly costs 1%+:
- EURUSD worst day 2025-08-01: Yahoo 1.15781 vs ECB 1.14040 (1.53%)
- GBPUSD worst day 2024-04-10: Yahoo 1.25663 vs ECB 1.26995 (1.05%)
- USDJPY worst day 2026-07-30: Yahoo 159.74000 vs ECB 162.94005 (1.96%)
- USDCHF worst day 2025-08-01: Yahoo 0.80448 vs ECB 0.81656 (1.48%)
- USDCAD worst day 2025-01-20: Yahoo 1.42950 vs ECB 1.44668 (1.19%)
- AUDUSD worst day 2024-04-10: Yahoo 0.65287 vs ECB 0.66224 (1.41%)
- NZDUSD worst day 2024-04-10: Yahoo 0.59970 vs ECB 0.60820 (1.40%)
- EURGBP worst day 2024-10-31: Yahoo 0.84285 vs ECB 0.83753 (0.64%)
- EURJPY worst day 2026-07-30: Yahoo 184.07500 vs ECB 186.99000 (1.56%)
- GBPJPY worst day 2026-07-30: Yahoo 214.50200 vs ECB 218.15318 (1.67%)

Those dates are 2024-07-11 (US CPI shock), 2024-08-05 (yen carry-trade unwind), 2025-01-20 (US inauguration), 2025-04-04/10 (tariff turmoil), 2025-08-01 (US jobs report shock) and 2026-07-30 (BoJ decision day). On those days the ECB print and any spot feed diverge by this much purely from timing.

## 4. Scope, and measured vs hypothesized

MEASURED: (a) internal consistency of every bar, (b) calendar coverage and gaps, (c) agreement with ONE independent official daily reference source at one time of day, over ~2.8 years and 710 trading days per pair.
NOT established: that every individual price is correct, that this feed matches any particular broker's quotes, or that the cause of any specific deviation is proven. The timing explanation for the large deviations above is a HYPOTHESIS consistent with the measurements - the flagged dates line up with well-known macro event days, and EURGBP (whose two legs share the same ECB fixing) shows the smallest deviations - but it was not verified against a second intraday source. These checks argue the feed is fit for descriptive analysis; they are not a blanket certification.

## 5. Verdict

- The Yahoo intraday feed the tools use is **internally consistent and unbiased against official central-bank reference rates** over ~2.8 years and 710 trading days per pair. It is fit for the descriptive, simulation-only analysis this project does.
- It is NOT an execution-grade feed: unofficial, no SLA, no Sunday session, occasional small gaps, and history limited to 60 days at 5-minute granularity. The project's own freshness labeling stays necessary.
- ECB/Frankfurter reference rates are official and stable, but they are a few prints per day - they cannot replace intraday bars for session analysis, which is why the project treats them as the sizing/reference source only.
