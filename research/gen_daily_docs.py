#!/usr/bin/env python3
"""Render research/DAILY-TREND.md from results/daily_trend.json."""
import json, os
HERE = os.path.dirname(os.path.abspath(__file__))
R = json.load(open(os.path.join(HERE, "results", "daily_trend.json")))
EXTRA_PATH = os.path.join(HERE, "results", "daily_trend_extra.json")
EXTRA = json.load(open(EXTRA_PATH)) if os.path.exists(EXTRA_PATH) else {"lags": {}}
PAIRS = ["EURUSD","GBPUSD","USDJPY","USDCHF","USDCAD","AUDUSD","NZDUSD",
         "EURGBP","EURJPY","GBPJPY"]
HEADLINE = ["tsmom-63d","tsmom-126d","tsmom-252d","donchian-55/20","macross-50/200"]
NEIGHBOUR = ["tsmom-42d","tsmom-84d","tsmom-168d","tsmom-336d",
             "donchian-40/15","donchian-70/25","macross-25/100","macross-100/300"]
L = []
A = L.append
A("# Daily trend following on 21 years of free data: the strongest published strategy class, tested the same way")
A("")
A("Simulation only. No real orders, no broker, no money moved - this project cannot place trades and these tests never did. Reproduce with `research/fx_daily_trend.py`; every number below comes from `research/results/daily_trend.json`. Nothing was removed because it looked bad: the full pre-registered grid is printed, losing cells included.")
A("")
A("## Why this study")
A("")
A("BACKTESTS.md showed the project's intraday opening-range-breakout rule is a coin flip before costs and loses reliably after them - the spread is paid every day, on a rule whose daily edge is smaller than the spread. The owner's standing question is whether ANY simple rule can be profitable. The strongest published evidence for a simple FX rule is medium-term trend following (time-series momentum): positions held for weeks to months, so the spread is paid a handful of times per year, not every day. Daily bars also unlock ~21 years of free history (2003-2026) instead of 60 days. This study tests exactly that class, pre-registered, with the same honesty rules as before.")
A("")
A("## Setup")
A("")
A("- Data: Yahoo daily bars, %s to %s, %d pairs, ~5,300-6,600 bars per pair, personal-use feed, raw bars cached locally and NOT committed. Bar timestamps label the session START (23:00 UTC): the week's first daily bar carries a Sunday UTC date and the week's last covers Friday's session under a Thursday UTC date. All pairs share the convention, so cross-pair alignment is unaffected; the ECB cross-check below allows for it." % ("2003-12-01", "2026-11-20", 10))
A("- Spot cross-check of the daily closes against official ECB reference rates (Frankfurter), 5 dates x 3 pairs: deviations +0.1% to +1.0% except GBPUSD 2020-03-18 (+2.2%, a COVID-crash day) - consistent with the several hours between the ECB 16:00 CET fixing and the 23:00 UTC session close. Same conclusion as the hourly cross-check in DATA-CORRECTNESS.md: unbiased, not execution-grade.")
A("- Rules (chosen before looking at any result): **tsmom-63/126/252** (long if the close is above its close 63/126/252 trading days ago, else short), **donchian-55/20** (enter long on a 55-day-high close, exit on a 20-day-low close; symmetric short; the classic Turtle geometry), **macross-50/200** (long while SMA50 > SMA200, else short). Neighbour parameters (tsmom 42/84/168/336, donchian 40/15 and 70/25, macross 25/100 and 100/300) are the sensitivity table below - 13 variants x 10 pairs = 130 cells in total.")
A("- Execution convention: the signal at a day's close sets the position for the NEXT close-to-close return. No same-close lookahead. No stops - all exits are signal-based, so the intrabar stop/target ambiguity of the intraday study does not arise.")
A("- Sizing: on segment entry, units = 1%% of current slice equity per 1xATR(20) (volatility-based, the standard trend-following sizing); units are then FIXED for the segment. Simulated capital: $1,000 per pair, $10,000 equal-weight portfolio. If a slice's equity reaches zero it is ruined and stops (recorded, not hidden).")
A("- Costs: the same retail spread assumptions as BACKTESTS.md (pips: %s), charged as an adverse fill cost - half a spread on every entry, exit and reversal leg. Scenarios: gross (0x), net (1x), stress (2x). NOT modeled, stated openly: **swap/rollover interest** - for positions held weeks to months this is MATERIAL and can add to or subtract from returns depending on the pair's rate differential; slippage and gaps; commissions. Real results would differ, mostly for the worse." % ", ".join("%s %s" % (p, R["spread_pips"][p]) for p in PAIRS))
A("- Random-direction control: same segment boundaries, direction re-drawn per segment, %d seeds per cell." % 20)
A("")
A("## Portfolio results ($10,000 across 10 pairs, net costs, ~21 years)")
A("")
A("| rule | return | CAGR | max drawdown | trades | avg R/trade | 95% CI |")
A("| --- | --- | --- | --- | --- | --- | --- |")
for name in HEADLINE:
    pf = R["portfolio"][name]
    ci = pf["avg_r_ci95"]
    A("| %s | %+.2f%% | %+.2f%% | %.2f%% | %d | %+.4f | [%s .. %s] |" % (
        name, pf["return_pct"], pf["cagr_pct"], pf["max_drawdown_pct"],
        pf["trades"], pf["avg_r"],
        ("%.4f" % ci[0]) if ci else "n/a", ("%+.4f" % ci[1]) if ci else "n/a"))
A("")
A("Read: over 21 years, NONE of the five pre-registered trend rules beats break-even meaningfully on 10 spot FX pairs at retail spreads. Total returns range from about -17%% to +5%% over TWO DECADES (CAGR -0.9%% to +0.2%%), and every pooled 95%% confidence interval straddles zero - the samples cannot distinguish any of these rules from break-even. Published trend-following results are stronger, but those are futures portfolios across equity indices, bonds and commodities with institutional costs, leverage and continuous vol-target rebalancing; that is not what a retail spot-FX account can run. Scoped claim: these rules, these pairs, these costs, this sample - not proof that no trend implementation could work.")
A("")
A("## Per-pair detail, net costs")
A("")
for name in HEADLINE:
    A("### %s" % name)
    A("")
    A("| pair | trades | win %% | avg R | 95%% CI | return | CAGR | max DD | ruined |")
    A("| --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for p in PAIRS:
        c = R["pairs"][name][p]
        ci = c.get("avg_r_bootstrap_ci95")
        A("| %s | %d | %.1f | %+.4f | %s | %+.2f%% | %+.2f%% | %.2f%% | %s |" % (
            p, c["trades"], c["win_pct"], c["avg_r"],
            ("[%.3f .. %+.3f]" % (ci[0], ci[1])) if ci else "n/a",
            c["return_pct"], c["cagr_pct"], c["max_drawdown_pct"],
            "YES" if c.get("ruined") else "no"))
    A("")
A("## Gross vs net (cost drag), portfolio return")
A("")
A("| rule | gross return | net return | stress (2x spread) |")
A("| --- | --- | --- | --- |")
for name in HEADLINE:
    g = sum(R["gross"][name][p]["return_pct"] for p in PAIRS) / len(PAIRS)
    s = sum(R["stress2x"][name][p]["return_pct"] for p in PAIRS) / len(PAIRS)
    A("| %s | %+.2f%% | %+.2f%% | %+.2f%% |" % (name, g, R["portfolio"][name]["return_pct"], s))
A("")
A("(gross/stress shown as the mean of per-pair slice returns)")
A("")
A("## Random-direction control (mean avg R over %d seeds, same segments)" % 20)
A("")
A("| rule | pair | random mean avg R | random range | actual avg R |")
A("| --- | --- | --- | --- | --- |")
for name in HEADLINE:
    for p in PAIRS:
        c = R["controls"][name][p]
        a = R["pairs"][name][p]["avg_r"]
        A("| %s | %s | %+.4f | [%+.4f .. %+.4f] | %+.4f |" % (
            name, p, c["mean_avg_r"], c["min_avg_r"], c["max_avg_r"], a))
A("")
A("## Parameter sensitivity (all neighbour variants, net costs)")
A("")
A("| rule | pair | trades | avg R | return | CAGR | max DD |")
A("| --- | --- | --- | --- | --- | --- | --- |")
for name in NEIGHBOUR:
    for p in PAIRS:
        c = R["pairs"][name][p]
        A("| %s | %s | %d | %+.4f | %+.2f%% | %+.2f%% | %.2f%% |" % (
            name, p, c["trades"], c["avg_r"], c["return_pct"], c["cagr_pct"], c["max_drawdown_pct"]))
A("")
A("With 130 cells in the full grid (13 variants x 10 pairs), about 6-7 cells would show a |t| > 2 by pure luck; treat any isolated positive cell accordingly.")
A("")
A("## P&L by year (USD per $1,000 slice, net, portfolio rules)")
A("")
for name in HEADLINE:
    A("### %s" % name)
    years = sorted({y for p in PAIRS for y in R["pairs"][name][p]["year_pnl"]})
    A("| pair | " + " | ".join(years) + " |")
    A("| --- | " + " | ".join(["---"] * len(years)) + " |")
    for p in PAIRS:
        yp = R["pairs"][name][p]["year_pnl"]
        A("| %s | %s |" % (p, " | ".join(str(yp.get(y, 0)) for y in years)))
    A("")

A("## Execution timing: the same-close assumption, measured")
A("")
A("The headline convention acts AT the signal close: the close print that generates the signal is also the assumed fill price (mid +/- half-spread). That identity cannot be verified with free data, so this section re-runs every headline rule acting 1 and 2 closes LATER - a strictly more conservative, realistic-lag execution - same sizing, same costs.")
A("")
A("| rule | lag 0 return (CAGR) | lag 1 return (CAGR) | lag 2 return (CAGR) | all-lags 95% CI straddles zero? |")
A("| --- | --- | --- | --- | --- |")
for name in HEADLINE:
    p0 = R["portfolio"][name]
    row = "| %s | %+.2f%% (%+.2f%%)" % (name, p0["return_pct"], p0["cagr_pct"])
    cis = [p0["avg_r_ci95"]]
    for lag in ("1", "2"):
        pf = EXTRA["lags"].get(lag, {}).get(name, {}).get("_portfolio")
        if pf:
            row += " | %+.2f%% (%+.2f%%)" % (pf["return_pct"], pf["cagr_pct"])
            cis.append(pf["avg_r_ci95"])
    straddle = all(ci and ci[0] <= 0 <= ci[1] for ci in cis)
    A(row + " | %s |" % ("yes" if straddle else "NO"))
A("")
A("Read: the no-edge conclusion is NOT an artifact of the same-close assumption - under 1- and 2-day execution lags every pooled confidence interval still straddles zero (CAGRs 0.0%% to +1.3%% over 21 years). Lagged execution comes out slightly BETTER for several rules, which is the known daily-frequency short-term reversal effect (entering a day late buys the small pullback) and is equally consistent with noise across this many cells; either way nothing crosses break-even significance, and the headline convention is not flattered relative to realistic lag. Per-pair lag numbers are in results/daily_trend_extra.json.")
A("")
A("## Results by era (portfolio, net costs)")
A("")
A("| rule | 2003-2010 | 2011-2015 | 2016-2020 | 2021-2026 |")
A("| --- | --- | --- | --- | --- |")
for name in HEADLINE:
    er = R.get("eras", {}).get(name, {})
    A("| %s | %s | %s | %s | %s |" % (
        name,
        ("%+.2f%%" % er.get("2003..2010", 0)) if "2003..2010" in er else "n/a",
        ("%+.2f%%" % er.get("2011..2015", 0)) if "2011..2015" in er else "n/a",
        ("%+.2f%%" % er.get("2016..2020", 0)) if "2016..2020" in er else "n/a",
        ("%+.2f%%" % er.get("2021..2026", 0)) if "2021..2026" in er else "n/a"))
A("")
A("Read: every rule looked better in 2003-2010 and most are negative in the two most recent eras. That decay pattern is what a published anomaly being arbitraged away looks like - and also what noise looks like across slices of a zero-edge process. Either reading argues against betting on the recent sample.")
A("")
A("## Selection and out-of-sample limits")
A("")
A("- Nothing is FITTED: parameters are pre-registered literature standards, so there is no training sample to leak into the results. The multiple-comparisons count (130 cells; 390 across the three execution lags) is stated, not hidden.")
A("- Selection still operates one level up: WHICH rules to test (trend following) was chosen from published evidence, so this study is best read as an independent replication attempt on retail spot FX, not a fresh discovery. The 10 pairs are today's liquid majors - a present-day choice; pairs that died are not in the frame (for major FX this is a mild form of the survivorship caveat, and the euro itself only exists from 1999, three years before this sample starts).")
A("- The era table above is the honest out-of-sample-style check available for unfitted rules: results are era-unstable, with the recent decade the weakest.")
A("- Regression coverage for this harness now lives in research/test_daily_trend.py: quote-currency risk conversion in USD (the bug class fixed on 2026-11-19 and caught again pre-publish on 2026-11-20), no-future conversion lookups, execution-lag mechanics, control boundary preservation, cost ordering and ruin flooring.")
A("")
A("## Conclusions")
A("")
A("1. On ~21 years of free daily data, the classic trend-following rules that have the best published evidence do NOT show a reliable edge on 10 spot FX pairs after retail spreads: portfolio CAGRs of -0.9%% to +0.2%%, every confidence interval through zero, and the random-direction controls land in the same range.")
A("2. Costs are no longer the main killer at this horizon (gross vs net is a few points over two decades) - the gross edges themselves are approximately zero on these pairs and rules. The intraday study's problem (spread >> edge) is replaced by a simpler one: no measured edge at all.")
A("3. Swap/rollover interest is unmodeled and material at these holding periods; for some pairs (e.g. long high-yield vs low-yield) it would add a carry component, for others subtract. It does not change the shape of the result: carry is a known, separately measurable term, not a hidden edge in these rules.")
A("4. Combined with BACKTESTS.md: two independent strategy classes (intraday breakout on 5m/1h, multi-month trend on daily) both fail to beat costs on free spot-FX data. The honest answer to 'can this tool always profit' remains no - and the published evidence for THAT keeps getting stronger, which is the useful output.")
A("5. Robustness of the harness itself (added 2026-11-20, second round): the conclusion is insensitive to the same-close execution assumption (1- and 2-day lags change nothing material), era-split results show the recent decade is the weakest for every rule, and deterministic reruns reproduce the published numbers exactly. Regression tests cover the conversion and execution machinery.")
A("6. fxpulse's defensible niche is unchanged: an honesty-first analysis toolkit - every variant shown, controls next to claims, corrections published - not a signal service.")
A("")
A("Nothing here is financial advice or a prediction. Past simulations do not guarantee anything about the future.")
open(os.path.join(HERE, "DAILY-TREND.md"), "w").write(("\n".join(L) + "\n").replace("%%", "%"))
print("wrote DAILY-TREND.md", len(L), "lines")
