# Open-source trading tools: what exists, and where an honest toolkit fits

Survey date: 2026-11-19. Purpose: map existing free and open-source trading tools before anyone extends
fxpulse toward crypto, gold, oil or other markets. Scope note: this survey exists so a tooling decision can be
made on evidence. The strategy results in [BACKTESTS.md](BACKTESTS.md) are negative after costs, so nothing
below argues for selling signals or promising returns. Sources are linked at the end; claims about each tool
come from the linked comparisons and project pages, checked on the survey date.

## 1. Backtesting engines (Python)

From a July 2026 seven-way comparison [1]:

| framework | best at | maintenance (mid-2026) | live trading |
| --- | --- | --- | --- |
| vectorbt | large parameter sweeps, research speed | open-source version in maintenance mode; active work behind vectorbt PRO at about $25/month | no |
| backtrader | legacy projects, tutorial volume | effectively frozen since about 2023 | aging broker bridges |
| backtesting.py | simplest credible start, single-asset | active | no |
| NautilusTrader | production-grade event-driven simulation, intraday, multi-venue | very active (v1.228.0, June 2026) | yes, same code backtest and live |
| PyBroker | ML strategies; walk-forward and bootstrapped metrics built in | active | via Alpaca |
| Zipline Reloaded | US equity factor research | active community fork | research only |
| RQAlpha | China-market workflows | active, Chinese-first docs | China brokers |

QuantConnect Lean [3] sits beside this list: a C# engine with a Python API and managed data, fast for long
minute-resolution history, at the cost of platform coupling.

## 2. Crypto bots (self-hosted)

From an April 2026 three-way comparison [2]:

| tool | focus | backtesting | stars (Apr 2026) | license |
| --- | --- | --- | --- | --- |
| Freqtrade | ready-to-trade spot bot, 20+ exchanges via CCXT, hyperopt tuning, web UI, dry-run mode | built-in | ~49,400 | GPLv3 |
| Jesse | research-driven backtesting plus live | built-in, candle-based | ~7,800 | LGPL-3.0 |
| Hummingbot | market making and arbitrage, 30+ CEX/DEX connectors | limited, execution-focused | ~18,400 | Apache 2.0 |

## 3. Free data sources and their terms

- Frankfurter [4]: official central-bank reference rates (ECB and others), free API, no key; daily reference
  prints, not intraday quotes. Already fxpulse's reference and sizing source.
- Yahoo Finance chart endpoint: unofficial, personal use under Yahoo's terms, can lag or rate-limit. Covers
  forex pairs and, with the same limits, gold (XAUUSD=X, GC=F) and oil (CL=F, BZ=F). fxpulse already labels
  and gates this source; the same handling would apply to metals and energy symbols.
- Stooq [5]: free daily CSV history across forex, commodities and indices; intraday access is limited and the
  site guards automated access, so it suits daily checks, not intraday feeds.
- Crypto exchange public market data (for example Binance klines, commonly reached through CCXT, which is how
  Freqtrade connects to 20+ exchanges [2]): free and keyless for public candles. Redistribution and use terms
  are per exchange and would need checking before any data is bundled, same discipline this project already
  applies to Yahoo.
- Tiingo and Alpha Vantage [5]: free tiers exist with attribution and rate limits; Alpha Vantage's free tier
  is personal use.

## 4. The gap this project can actually fill

Per [1], what the engines do not give you out of the box is the validation workflow: out-of-sample splits,
walk-forward, Monte Carlo, parameter perturbation, run on every candidate every time. PyBroker pre-wires
walk-forward and bootstrap; the rest leave it to the user. And across the whole landscape, the norm is to show
the best backtest, not every backtest.

fxpulse's research harness (this directory) already does the unfashionable parts that the big tools skip:

- explicit simulated capital and stated cost assumptions with provenance;
- every variant published, losing ones included, with a multiple-comparisons count;
- a random-direction control next to each result;
- measured intrabar stop/target ambiguity with conservative and optimistic bounds;
- labeled in-sample vs out-of-sample statements, and measured-vs-hypothesized labeling on data checks;
- zero dependencies: plain Python 3.8+ standard library, so anyone can audit and rerun every number.

That is the realistic niche: not another engine (NautilusTrader, Lean and Freqtrade are far bigger), but an
honesty-first analysis and education toolkit whose evidence rules could be pointed at any market.

## 5. If a multi-market extension is pursued anyway

Contingent on the owner's decision after reading the evidence, the defensible shape is:

1. Keep the validation harness as the centerpiece; any new market adapter must pass DATA-CORRECTNESS-style
   checks before its numbers are shown.
2. Crypto adapter: public klines via CCXT or an exchange's own public API, no key, terms checked per exchange;
   crypto trades 24/7, so the session concept needs redefining per market rather than copied from forex.
3. Gold/oil adapter: same Yahoo endpoint and same personal-use gate already in the code; Stooq daily for a
   second opinion.
4. Any website: static published reports plus on-demand local analysis, no accounts, no execution, no
   performance promises. The MIT license already permits others to build on it.

What not to build: a signal service, a "profitable bot" claim, or any paywalled promise of returns. The
evidence assembled here says exactly the opposite, and publishing it is the useful part.

## Sources

1. [Python Backtesting Frameworks (2026): 7 Compared Honestly, quanttradingtools.com, 2026-07-20](https://quanttradingtools.com/python-backtesting-frameworks/)
2. [Freqtrade vs Jesse vs Hummingbot: Self-Hosted Algorithmic Trading Guide 2026, pistack.xyz, 2026-04-27](https://www.pistack.xyz/posts/2026-04-27-freqtrade-vs-jesse-vs-hummingbot-self-hosted-algorithmic-trading-guide-2026/)
3. [QuantConnect Lean engine](https://www.lean.io/) and [github.com/QuantConnect/Lean](https://github.com/QuantConnect/Lean)
4. [Frankfurter: free exchange rate API, license and terms](https://frankfurter.dev/license/)
5. [Free equity/FX price API data card: yfinance / Stooq / Tiingo / Alpha Vantage (ASSIP 2026 textbook)](https://edwardlg.github.io/assip-2026-empirical-finance/textbook/data-cards/free-equity-apis.html)

Nothing here is financial advice or a promise of future results.
