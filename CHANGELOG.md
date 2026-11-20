# Changelog

Notable corrections and changes, newest first. This project publishes its
mistakes openly: each entry says what was wrong, what it changed, and where
the measurement lives.

## 2026-11-20 - Daily trend-following study (21 years), plus a quote-currency sizing fix caught pre-publish

- New study `research/DAILY-TREND.md` (`research/fx_daily_trend.py`, `results/daily_trend.json`): the strongest published simple-strategy class - medium-term trend following - tested pre-registered on ~21 years of free daily bars (2003-2026, 10 pairs) with the project's honesty rules: explicit simulated capital, adverse fill costs, gross/net/stress side by side, random-direction controls, all 130 grid cells published. Result: no reliable edge after costs. Portfolio CAGRs -0.6% to +0.8% over two decades, every pooled 95% CI straddles zero, controls land in the same range. Swap/rollover interest is unmodeled and stated as a material caveat. Scoped: these rules, pairs, costs and sample - not proof that no trend implementation could work.
- **Caught before publish:** the first internal run sized positions in QUOTE currency terms (1% of equity per ATR without converting the ATR to USD), understating JPY-quote risk ~150x - the same bug family as the 2026-11-19 pip-value fix. Fixed before any number was published; the shipped script sizes in USD (`units = risk / (ATR x USD-per-quote)`).
- Daily-bar date convention documented: Yahoo daily FX bars are timestamped at session START (23:00 UTC), so the week's first bar carries a Sunday UTC date and Friday's session sits under a Thursday UTC date; all pairs share the convention, cross-pair alignment unaffected, ECB spot cross-check (Frankfurter, 5 dates x 3 pairs) consistent with close-vs-fixing timing.

## 2026-11-19 - Dependence-aware portfolio uncertainty, replay caveat

- The portfolio view now reports a pooled average R with a 95% day-grouped
  bootstrap CI: whole calendar days are resampled together, keeping every
  pair's trades of a sampled day in the same draw, so same-day cross-pair
  dependence is preserved (the per-pair trade-level CIs cannot express it).
  Measured on this sample: 5-minute portfolio avg R -0.209, CI
  [-0.3336 .. -0.0808]; 1-hour avg R -0.1343, CI [-0.1639 .. -0.1041]. Both
  intervals came out wider than the naive trade-level interval and still
  exclude zero: within these samples the pooled negative expectancy is not
  explained by same-day correlated noise. The bounds still treat distinct
  days as independent (day-to-day volatility clustering unmodeled) and say
  nothing about future performance; the reports state this next to the
  numbers.
- `fx_timemachine` documentation now states the replay's slot-jitter
  approximation plainly: sampling slot j = i +/- window flattens intraday
  volatility seasonality, so replay paths are approximate in time-of-day
  structure (walk-forward pools remain strictly out-of-sample by day).

## 2026-11-19 - Uncertainty reporting and input hardening (9393457)

- Headline backtest tables now carry a bootstrap 95% confidence interval
  for average R per pair (the `bootstrap_ci` helper existed but was never
  called). On the 5-minute sample 7 of 10 pairs are statistically
  indistinguishable from break-even; on the 1-hour sample 4 of 10. The
  negative drift after costs is consistent across samples, but at these
  sample sizes most individual cells cannot be proven different from zero -
  the reports now say so with numbers.
- `fx_size` rejects non-positive balance/risk and risk above the balance
  (previously produced negative or absurd sizes silently).
- `fx_plan --stop-rule fixed` without `--stop` gives a clear error instead
  of a bare KeyError.

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
