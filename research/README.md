# research/

Independent validation of fxpulse, November 2026. Simulation only - no real orders were or can be placed from this project.

- **DATA-CORRECTNESS.md** - are the free data feeds any good? Internal consistency screens plus a 711-day cross-check against official ECB reference rates. Short answer: yes for analysis, with documented limits.
- **DAILY-TREND.md** - does classic medium-term TREND FOLLOWING (the strongest published simple-rule class) make money on 21 years of daily bars? Short answer: no reliable edge after costs - CAGRs -0.6% to +0.8%, every confidence interval through zero.
- **BACKTESTS.md** - does the shipped opening-range-breakout rule make money with explicit simulated capital ($10,000/pair, 1% risk, realistic spreads, all variants shown)? Short answer: no - gross it is a coin flip, net it loses reliably across 2.8 years and 10 pairs. The full grids, controls and stress tests are included, losing variants too.
- `fetch_data.py`, `fx_validate.py`, `fx_backtest.py`, `cost_model_check.py` - the exact code that produced every number (stdlib only).
- `results/` - raw JSON outputs the docs were generated from.

## Reproduce

```bash
python3 fetch_data.py        # caches Yahoo bars to ./data (personal use, paced)
python3 fx_validate.py       # data correctness -> results/validate_results.json
python3 fx_backtest.py --timeframe 5m   # -> results/backtest_5m.json
python3 fx_backtest.py --timeframe 1h   # -> results/backtest_1h.json
python3 cost_model_check.py  # legacy vs corrected cost model -> results/cost_model_check.json
python3 fetch_daily.py        # caches Yahoo DAILY bars to ./data (personal use, paced)
python3 fx_daily_trend.py     # daily trend study -> results/daily_trend.json
python3 fx_daily_trend.py extra  # execution-lag sensitivity -> results/daily_trend_extra.json
python3 gen_daily_docs.py     # rebuild DAILY-TREND.md from the JSONs
python3 test_daily_trend.py     # regression tests: USD conversion, lag mechanics, controls, costs, ruin
python3 gen_docs.py          # rebuild the markdown reports from the JSONs
```

The scripts expect the repo one directory up on `sys.path` (they import `fxdata`/`fx_scan` so the shipped code itself is tested) and a `data/` cache folder. Intraday bars are NOT committed: Yahoo's endpoint is personal-use, so raw market data is never redistributed from this repository - only aggregated statistics and a handful of individual quotes for error examples.

None of this is financial advice or a promise about the future.
