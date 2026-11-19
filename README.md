# fxpulse

Free, open analysis tools for the forex market: session scanner, entry/stop/target planner, Monte Carlo replay of a plan from a pair's own recent bars, risk-based position sizing, currency news, and a paper-trade journal with an explicit human yes before anything is recorded.

Everything is plain Python 3.8+, standard library only. Nothing to install. Nothing here connects to a broker, places an order, or moves money. Nothing here is financial advice.

Inspired by the methodology of [Jakeschincariol/day-trader-skill](https://github.com/Jakeschincariol/day-trader-skill) (US stocks), re-implemented from scratch for forex.

## The tools

| command | what it does |
| --- | --- |
| `python3 fx_scan.py` | Session opening-range scan of the major pairs: where price sits against the first hour after 08:00 Europe/London (DST-aware), any breakout, and the age of the newest bar. |
| `python3 fx_plan.py EURUSD buy --write` | Builds an entry/stop/target plan from the session range (stop rules: range midpoint or far side; target as an R multiple). Saves `plan.json`. |
| `python3 fx_timemachine.py run` | Replays the plan 10,000 times by resampling the pair's own recent 5-minute bars (seeded, reproducible), plus re-runs the same rule on every full past day in the data. Reports target-first / stop-first shares against the break-even share. |
| `python3 fx_size.py --balance 5000 --risk 50` | Lot sizing from your risk amount and the plan's stop distance, with pip values from official central-bank reference rates. |
| `python3 fx_ticket.py confirm --lots 0.37` | Shows a plain-words paper ticket; only after you type `yes` does it append a SIMULATED trade to `journal.json`. |
| `python3 fx_news.py --ccy EUR USD` | Currency news from the GDELT Project's official API, deduplicated. Headlines are leads, not facts. |
| `python3 test_fx.py` | Offline test suite (no network). |

## Data sources, labeled honestly

| source | what it is | freshness | terms |
| --- | --- | --- | --- |
| Yahoo Finance chart endpoint (`query2.finance.yahoo.com`) | Unofficial intraday bars, e.g. `EURUSD=X` | Near-real-time but can lag or rate-limit | Unofficial; Yahoo's terms are personal-use. **Enforced in code:** intraday tools refuse to run until the local user activates personal use once (`python3 fxdata.py --acknowledge-personal-use`), and never run when `FXPULSE_MODE=public`. No intraday data is bundled or redistributed. |
| Frankfurter (`api.frankfurter.dev`) | Official reference rates from 112 central banks (ECB etc.), free, no key | A few times a day. These are reference rates, not live quotes. | Free API; ECB content free to use with conditions (attribution). |
| GDELT DOC 2.0 (`api.gdeltproject.org`) | The GDELT Project's official news API, free, no key | Near-real-time global news | GDELT describes itself as a free open platform. Rate limit ~1 request per 5 seconds (the tool paces itself). |
| Twelve Data | Optional, disabled by default, bring-your-own-key | Real-time forex | Free tier is internal-use only; set your own key in `config.json` only if your use fits your plan's terms. |

## What the numbers mean (and do not mean)

The Time Machine resamples the pair's last ~60 days of 5-minute bars. Its percentages are **in-sample descriptive statistics** about the recent past under a stated, seeded, reproducible method. They are **not calibrated probabilities and not evidence of predictive edge**. Specifically:

- The pool contains only FULL UTC days strictly before the plan day (an explicit date cutoff, not a bar-count heuristic), so no same-day bars leak in. `--holdout N` excludes the most recent N days from the pool: that is a SENSITIVITY check on the training window, not out-of-sample validation. The actual out-of-sample check is `--walkforward N`: for each of the last N untouched days the pool is rebuilt from strictly earlier days and the rule's outcome on that day is compared with what the sim would have said beforehand. Small samples are stated as transparency, not proof.
- The history re-run uses only each day's OWN bars, and the opening range is fully formed before the entry is taken: no lookahead.
- Sessions are defined in Europe/London local time (default 08:00 London) and converted to UTC per date with DST rules; a fixed-UTC override exists. "London open" means the strategy's 08:00 London-local anchor, not an exchange bell (forex has none).
- Bar resampling weakens serial dependence. `--block N` draws consecutive bars from one past day to preserve short-range dependence; compare block 1 vs block 6 before reading anything into the numbers.
- Costs: a configurable spread (default 1 pip) shifts ALL levels adversely. Slippage, fees, and gaps are NOT modeled; a gap through the stop counts -1R in the sim while a real fill can be worse. Real results are worse than the sim.
- Data freshness is printed with every run (age of the newest bar, pool window dates). The intraday feed is an unofficial endpoint with no SLA; if it lags or dies, the tool says so rather than silently analyzing stale candles.

No output of this project is a recommendation to trade, and past resampled behavior does not guarantee anything.

## Quick start

```bash
python3 test_fx.py                                  # offline sanity check
python3 fx_scan.py                                  # what are the majors doing this session
python3 fx_plan.py EURUSD sell --target-r 1 --write # build a plan
python3 fx_timemachine.py run --entry-time 08:15    # replay it 10,000 times
python3 fx_size.py --balance 5000 --risk-pct 1      # size it
python3 fx_ticket.py confirm --lots 0.37            # paper ticket, your yes required
python3 fx_ticket.py journal                        # your simulated trades
```

Config: copy `config.example.json` to `config.json` (only needed for an optional Twelve Data key).

Activation: intraday features need one-time local personal-use activation (`python3 fxdata.py --acknowledge-personal-use`). Without it - or with `FXPULSE_MODE=public` - scan/plan/timemachine refuse to run and only official reference-rate data (Frankfurter/ECB, a few updates a day, NOT live quotes) is used. This is how the project keeps Yahoo's personal-use terms rather than papering over them.

## License

Copyright (c) 2026 Akibur Rahman. Released under the MIT License (see LICENSE): others may use, copy, modify and distribute this software, including commercially, provided the copyright notice and license are kept. See NOTICE for data-provider and inspiration attribution.
