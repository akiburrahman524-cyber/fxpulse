# Changelog

Notable corrections and changes, newest first. This project publishes its
mistakes openly: each entry says what was wrong, what it changed, and where
the measurement lives.

## 2026-11-19 - JPY-pair pip value 100x error in fx_size (5627cb5)

- **Wrong:** `fxdata.pip_value_usd` used 10 quote-currency units per pip per
  standard lot for every pair. For JPY-quote pairs a pip is 0.01, so one pip
  on one standard lot is 1,000 quote units, not 10. `fx_size` understated
  JPY-pair pip values by 100x and would have sized positions about 100x too
  large (USDJPY showed $0.063 per pip per lot instead of $6.29). The offline
  test asserted the wrong value, which is why the error survived review.
- **Fixed:** pip value is now `pip_size(pair) x 100,000` quote units per
  standard lot; the test asserts the corrected value. Verified: USDJPY at
  159.00 now returns $6.29 per pip per standard lot.
- **Not affected:** the research backtest, which sizes from `pip_size`
  directly (correct) - no published backtest number changed.
- Same commit: backtest conversion rates now come from strictly before the
  trade day (removed a one-day lookahead in sizing/P&L conversion; no
  material change in results), and narrative absolutes in the reports were
  scoped ("no parameter set in the tested grid", "unbiased at the daily ECB
  fixing - the one external point checked"). Added the measured
  win-rate-vs-profitability sweep to BACKTESTS.md: a 90% win rate was never
  observed for this rule at any tested target size, and 92% of the tested
  pair/target cells average negative R per trade after costs.

## 2026-11-19 - Spread costs were modeled FAVORABLY, not adversely (ca26892, 71f1a95)

- **Wrong:** `fx_timemachine` and `research/fx_backtest.py` shifted the stop
  and target trigger levels half a spread in the favorable direction (stop
  further away, target nearer) while the comment and the report claimed the
  shift was adverse. Found by re-reading the level arithmetic against the
  comment, not by a bad-looking number - the published conclusions still
  held, which is why it survived.
- **Fixed:** trigger levels stay at the mid-bar levels; the spread is
  charged as an adverse fill cost (entry and every exit half a spread worse
  than mid, R measured against the intended stop distance).
- **Measured impact** (same bars, both models, `research/cost_model_check.py`
  and `research/results/cost_model_check.json`): the old model reported a
  higher average R than the truth in 19 of 20 pair-samples. Corrected
  headline portfolio results: -9.56% on 60 days of 5-minute bars (was
  -4.94%) and -56.45% on 2.8 years of hourly bars (was -41.38%). The
  no-edge conclusion stands, stronger.
- Same commits: position units round DOWN to 100-unit steps (never risk
  more than intended); walk-forward uses the same cost model as the
  headline sim; regression tests for the cost convention; regenerated
  reports with dynamic numbers.

## 2026-11-19 - Research package (8e5c3fb, 39f1c04)

- Independent data validation (internal consistency screens, ECB reference
  cross-check) and profitability backtests of the shipped ORB rule with
  explicit simulated capital, full grids, random-direction controls, cost
  stress tests and intrabar-ambiguity bounds. Open-source tools landscape
  survey. Later corrected by the two entries above - the corrected numbers
  are the ones in the current reports.
