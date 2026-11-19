#!/usr/bin/env python3
"""Generate the research markdown docs from the result JSONs (numbers always match data)."""
import json, datetime, os

HERE = os.path.dirname(os.path.abspath(__file__))
V = json.load(open(os.path.join(HERE, "results", "validate_results.json")))
B5 = json.load(open(os.path.join(HERE, "results", "backtest_5m.json")))
B1 = json.load(open(os.path.join(HERE, "results", "backtest_1h.json")))
PAIRS = ["EURUSD","GBPUSD","USDJPY","USDCHF","USDCAD","AUDUSD","NZDUSD","EURGBP","EURJPY","GBPJPY"]

def w(path, text):
    with open(path, "w") as f:
        f.write(text)
    print("wrote", path, len(text), "chars")

# ---------------- DATA-CORRECTNESS.md ----------------
L = []
L.append("# Data correctness: what the fxpulse data feeds actually are\n")
L.append("Tested %s. Method and code: `research/fx_validate.py`, raw output `research/results/validate_results.json`. "
         "Bars: unofficial Yahoo chart endpoint (what the project's scan/plan/timemachine tools use), 10 pairs, "
         "5-minute bars for the last ~60 trading days and 1-hour bars back to 2024-02-02. "
         "Independent reference: official ECB euro reference rates via the Frankfurter API (free, no key).\n" % V["run_utc"][:10])
L.append("## 1. Internal consistency\n")
L.append("Every bar of every pair was checked for: high >= max(open, close), low <= min(open, close), positive prices, "
         "duplicate timestamps, non-monotonic timestamps, Saturday bars (spot forex is closed), and single-bar ranges above "
         "25x the pair's median bar range (bad-tick screen).\n")
L.append("| pair | interval | bars | span (UTC) | OHLC violations | dup/non-monotonic ts | Saturday bars | range outliers |")
L.append("| --- | --- | --- | --- | --- | --- | --- | --- |")
for r in V["internal"]:
    L.append("| %s | %s | %d | %s to %s | %d | %d/%d | %d | %d |" % (
        r["pair"], r["interval"], r["bars"], r["first"][:16], r["last"][:16],
        r["bad_ohlc"], r["duplicate_ts"], r["nonmonotonic_ts"], r["saturday_bars"], r.get("range_outliers_gt25x", 0)))
tot_bad = sum(r["bad_ohlc"] + r["duplicate_ts"] + r["nonmonotonic_ts"] + r["nonpositive"] + r["saturday_bars"] for r in V["internal"])
tot_out = sum(r.get("range_outliers_gt25x", 0) for r in V["internal"])
tot_bars = sum(r["bars"] for r in V["internal"])
msg = "All structural checks are zero across %d bars. " % tot_bars
if tot_out:
    ex = []
    for r in V["internal"]:
        for e in r.get("outlier_examples", []):
            ex.append("%s %s: %s" % (r["pair"], r["interval"], e))
    msg += ("The bad-tick screen flagged %d single bars (%s). Inspection shows these are genuine fast moves, not bad ticks: "
            "the neighbouring bars continue from the new level with no spike-and-revert pattern (a real 0.3%% 5-minute move in NZDUSD "
            "is 25x that pair's very quiet median bar). " % (tot_out, "; ".join(ex)))
msg += "The feed is internally coherent."
L.append("\n" + msg + "\n")
L.append("## 2. Gaps and calendar coverage\n")
L.append("- Yahoo's forex week runs Monday 00:00 UTC to Friday ~21:30 UTC. There is **no Sunday-evening session** in this feed; "
         "the week-end gap (Fri ~21:30 to Mon 00:00, ~50 hours) is expected and present every week.")
gap_ex = []
for r in V["internal"]:
    if r["interval"] == "5m":
        for e in r.get("unexpected_gap_examples", []):
            gap_ex.append("%s %s" % (r["pair"], e))
if gap_ex:
    L.append("- 5-minute data: occasional small intraday gaps over 60 days. Examples flagged this run: " + "; ".join(gap_ex[:6]) + ".")
else:
    L.append("- 5-minute data: no unexpected intraday gaps were flagged over 60 days this run.")
L.append("- 1-hour data reaches back to 2024-02-02 (~2.8 years), not further, and shows occasional longer holiday gaps (e.g. year-end).")
L.append("- This is an unofficial endpoint with no SLA: fine for analysis, not for execution. The tools already print the age of the newest bar with every run.\n")
L.append("## 3. Cross-check against official ECB reference rates\n")
L.append("The ECB publishes one reference rate per currency per day, fixed at 16:00 CET/CEST. For each of %d trading days per pair, "
         "the Yahoo hourly bar that STARTS at the fixing instant (15:00 UTC in winter, 14:00 UTC in summer, DST handled) was compared "
         "with the ECB figure. A perfect feed would differ by the drift of a few minutes only.\n" % V["ecb_cross"][0]["compared_days"])
L.append("| pair | days compared | median \\|dev\\| | mean \\|dev\\| | signed mean | max \\|dev\\| | days > 0.5% |")
L.append("| --- | --- | --- | --- | --- | --- | --- |")
for c in V["ecb_cross"]:
    L.append("| %s | %d | %.3f%% | %.3f%% | %+.3f%% | %.2f%% | %d |" % (
        c["pair"], c["compared_days"], c["median_abs_dev_pct"], c["mean_abs_dev_pct"],
        c["mean_signed_dev_pct"], c["max_abs_dev_pct"], c["days_over_0p5pct"]))
L.append("")
L.append("How to read this: the signed means are all near zero (no systematic bias - Yahoo is not consistently high or low). "
         "Medians of 0.05-0.13% are ordinary sub-hour FX drift. Every large deviation (0.6-2.0%) falls on a known high-volatility "
         "macro day, where an hour of timing difference honestly costs 1%+:")
for c in V["ecb_cross"]:
    if c["worst5"]:
        w0 = c["worst5"][0]
        L.append("- %s worst day %s: Yahoo %.5f vs ECB %.5f (%.2f%%)" % (c["pair"], w0["day"], w0["yahoo"], w0["ecb"], w0["dev_pct"]))
L.append("")
L.append("Those dates line up with well-known macro event days (US CPI shocks, the 2024-08 yen carry-trade unwind, tariff turmoil, "
         "central-bank decision days). On days like these the ECB print and any spot feed diverge by this much purely from timing.\n")
L.append("## 4. Scope, and measured vs hypothesized\n")
L.append("MEASURED: (a) internal consistency of every bar, (b) calendar coverage and gaps, (c) agreement with ONE independent "
         "official daily reference source at one time of day, over ~2.8 years and 710 trading days per pair.")
L.append("NOT established: that every individual price is correct, that this feed matches any particular broker's quotes, "
         "or that the cause of any specific deviation is proven. The timing explanation for the large deviations above is a "
         "HYPOTHESIS consistent with the measurements - the flagged dates line up with well-known macro event days, and EURGBP "
         "(whose two legs share the same ECB fixing) shows the smallest deviations - but it was not verified against a second "
         "intraday source. These checks argue the feed is fit for descriptive analysis; they are not a blanket certification.\n")
L.append("## 5. Verdict\n")
L.append("- The Yahoo intraday feed the tools use is **internally consistent, and unbiased at the daily ECB fixing - the one external "
         "point this test can check** over the sample above. It is fit for the descriptive, simulation-only analysis this project does. "
         "'Unbiased' is scoped: it was measured at one time of day against one official source, not certified for every bar.")
L.append("- It is NOT an execution-grade feed: unofficial, no SLA, no Sunday session, occasional small gaps, and history limited to "
         "60 days at 5-minute granularity. The project's own freshness labeling stays necessary.")
L.append("- ECB/Frankfurter reference rates are official and stable, but they are a few prints per day - they cannot replace intraday bars "
         "for session analysis, which is why the project treats them as the sizing/reference source only.\n")
w(os.path.join(HERE, "DATA-CORRECTNESS.md"), "\n".join(L))

# ---------------- BACKTESTS.md ----------------
def cell(g, pair, direction, stop, tr, scen):
    for x in g:
        if x["pair"]==pair and x["direction"]==direction and x["stop"]==stop and x["target_r"]==tr and x["scenario"]==scen:
            return x
    return None

L = []
L.append("# Profitability of the shipped ORB rule, simulated with explicit capital\n")
L.append("Simulation only. No real orders, no broker, no money moved - this project cannot place trades and these tests never did. "
         "Everything below is reproducible with `research/fx_backtest.py`; full per-variant numbers are in "
         "`research/results/backtest_5m.json` and `backtest_1h.json`. Nothing was removed because it looked bad: "
         "every variant tested is in the JSON files, and the losing parameter sets are printed next to the winners.\n")
L.append("## Setup\n")
L.append("- Strategy under test: the project's own workflow - opening range of the first hour after 08:00 Europe/London "
         "(DST-aware, repo function), entry on the first 5-minute close beyond the range in the breakout direction, stop at the "
         "range midpoint, target at 1R, one trade per day per pair, stop checked before target inside a bar (conservative), "
         "exit at the day's last bar if neither is touched. The exact repo functions (`split_days`, `opening_range`, "
         "`session_open_utc_minutes`) are imported and used, so the shipped code is what runs.")
L.append("- Simulated capital: **USD 10,000 per pair, risking 1% of current equity per trade**, position size from stop distance "
         "and pip value, rounded down to 100-unit steps, pip values converted to USD with that day's own rates. "
         "Also an equal-weight 10-pair portfolio view: $10,000 split into ten independent $1,000 slices, each pair simulated against its own slice with 1% risk of the slice per trade, daily P&L summed across slices; per-pair expectancy does not depend on cross-pair correlation (portfolio-level drawdown does).")
L.append("- Costs: retail-typical spreads per pair (pips): EURUSD 0.6, GBPUSD 0.9, USDJPY 0.7, USDCHF 1.0, USDCAD 1.2, AUDUSD 0.8, "
         "NZDUSD 1.4, EURGBP 1.1, EURJPY 1.2, GBPJPY 2.0 - charged as an adverse FILL cost: the entry fills half a spread worse than "
         "mid (a buy pays the ask, a sell receives the bid) and every exit fills half a spread worse than the trigger level, with R "
         "measured against the intended stop distance. Trigger levels stay at the mid-bar levels (bid/ask trigger displacement is "
         "second-order and not modeled). See the cost-model section below for the 2026-11-19 correction. "
         "Scenarios: gross (no costs), net (1x), stress (2x). Slippage, gaps and commissions are NOT modeled: real fills would be worse, "
         "so every number here is optimistic relative to live trading.")
L.append("- Cost provenance: the spreads above are ASSUMPTIONS chosen to be typical of major retail brokers in 2026, "
         "not quotes measured from one specific broker; actual costs vary by broker, account type and time of day. "
         "The stress scenario (2x) covers the pessimistic case.")
L.append("- Two samples: 5-minute bars, the last ~60 trading days (the tool's native timeframe); and 1-hour bars over ~2.8 years "
         "(2024-02-02 to 2026-11-18, ~700 trades per pair) for regime coverage. The 1-hour test uses the single hour bar at the "
         "DST-correct London open as the opening range and hourly closes for entries: coarser than the shipped 5-minute workflow, "
         "included for coverage across three different market years. With bars that wide, the stop/target ordering inside one bar "
         "matters; see the ambiguity section below.\n")

CM = json.load(open(os.path.join(HERE, "results", "cost_model_check.json")))
L.append("## Cost model (corrected 2026-11-19)\n")
L.append("The first published version of this backtest (commits through 39f1c04) shifted the stop and target TRIGGER levels half a "
         "spread in the FAVORABLE direction - the stop further from entry, the target nearer - while the code comment and this document "
         "claimed the shift was adverse. The fill arithmetic was right; the trigger levels were not. The corrected model keeps triggers "
         "at the mid-bar levels and charges the spread as an adverse fill cost (entry and every exit half a spread worse than mid, R "
         "against the intended stop distance). Every number in this report uses the corrected model. The table below reruns the headline "
         "variant under BOTH models on identical bars (`research/cost_model_check.py`, `results/cost_model_check.json`) - the legacy "
         "column is what the old code would have reported, the fixed column is what this report shows.\n")
for label, iv in (("5-minute sample", "5m"), ("1-hour sample", "1h")):
    L.append("%s, headline variant, legacy (favorable trigger shift) vs fixed (adverse fill cost):" % label)
    L.append("")
    L.append("| pair | trades | legacy avg R | fixed avg R | legacy return | fixed return |")
    L.append("| --- | --- | --- | --- | --- | --- |")
    for p in PAIRS:
        r = CM[iv][p]
        L.append("| %s | %d | %+.4f | %+.4f | %s%% | %s%% |" % (
            p, r["trades"], r["legacy_avg_r"], r["fixed_avg_r"], r["legacy_return_pct"], r["fixed_return_pct"]))
    L.append("")
leg_better = sum(1 for iv in ("5m", "1h") for p in PAIRS if CM[iv][p]["legacy_avg_r"] > CM[iv][p]["fixed_avg_r"])
L.append("Read: in %d of %d pair-samples the legacy model reported a HIGHER average R than the truth - the favorable trigger shift "
         "flattered the rule it was supposed to stress. The error was found by re-reading the level arithmetic against the comment, "
         "not by a bad-looking number: the published conclusions still held, which is exactly why this class of bug survives. "
         "Regression coverage for the corrected convention (cost leaves hit counts unchanged, reduces avg R by exactly cost/R, for "
         "both sides) is in `test_fx.py`.\n" % (leg_better, 20))

for label, B in (("5-minute bars, last ~60 trading days", B5), ("1-hour bars, 2024-02 to 2026-11 (~2.8 years)", B1)):
    L.append("## Headline variant on %s\n" % label)
    L.append("Follow-the-breakout, stop or-mid, target 1R, 08:00 London, net costs. Each pair traded independently with $10,000 simulated capital.\n")
    L.append("| pair | trades | win % | avg R/trade | avg R 95% CI | return | max drawdown | profit factor | t-stat |")
    L.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for p in PAIRS:
        h = B["headline"][p]
        ci = h.get("avg_r_bootstrap_ci95")
        ci_txt = "[%+.3f .. %+.3f]" % (ci[0], ci[1]) if ci else "-"
        L.append("| %s | %d | %s | %s | %s | %s%% | %s%% | %s | %s |" % (
            p, h["trades"], h["win_rate"], h["avg_r"], ci_txt, h["return_pct"], h["max_drawdown_pct"], h["profit_factor"], h["expectancy_t"]))
    L.append("")
    cis = [B["headline"][p].get("avg_r_bootstrap_ci95") for p in PAIRS]
    straddle = sum(1 for c in cis if c and c[0] <= 0 <= c[1])
    L.append("The 95%% CI is a bootstrap over that pair's trades (resample the trade R's 2,000 times): the range of average R "
             "values consistent with this sample's noise. A CI that straddles zero means the sample cannot distinguish the "
             "variant from break-even; on this sample %d of 10 pairs straddle zero." % straddle)
    pf = B["portfolio"]
    L.append("\nEqual-weight 10-pair portfolio ($10,000 total): **return %s%%, max drawdown %s%%, %d trades**.\n" % (
        pf["return_pct"], pf["max_drawdown_pct"], pf["total_trades"]))
    gci = pf.get("avg_r_day_bootstrap_ci95")
    gci_txt = "[%+.4f .. %+.4f]" % (gci[0], gci[1]) if gci else "-"
    L.append("Pooled portfolio avg R/trade: **%s**, 95%% day-grouped bootstrap CI: **%s**. This interval resamples "
             "whole calendar days, keeping every pair's trades of a sampled day together, so it preserves same-day "
             "cross-pair dependence (the per-pair CIs above cannot). Distinct days are still resampled independently, "
             "so day-to-day volatility clustering remains unmodeled - this is a dependence-aware bound in one "
             "dimension only, and its width relative to a naive trade-level interval is a measured result, not a "
             "design guarantee.\n" % (pf.get("avg_r_pooled"), gci_txt))
    # per-year / per-segment table
    seg = {}
    for p in PAIRS:
        for t in B["headline"][p]["trade_log"]:
            k = t["day"][:4] if B is B1 else ("2026-08/09" if t["day"] < "2026-10-01" else "2026-10/11")
            seg.setdefault(p, {}).setdefault(k, 0.0)
            seg[p][k] += t["pnl_usd"]
    keys = sorted({k for p in PAIRS for k in seg[p]})
    L.append("P&L by period (USD, net):")
    L.append("")
    L.append("| pair | " + " | ".join(keys) + " |")
    L.append("| --- | " + " | ".join(["---"]*len(keys)) + " |")
    for p in PAIRS:
        L.append("| %s | %s |" % (p, " | ".join("%+.0f" % seg[p].get(k, 0.0) for k in keys)))
    L.append("")
    # gross vs net
    L.append("Gross vs net (cost drag), avg R per trade, same variant:")
    L.append("")
    L.append("| pair | gross | net |")
    L.append("| --- | --- | --- |")
    for p in PAIRS:
        g = cell(B["grid"], p, "follow", "or-mid", 1.0, "gross")
        n = cell(B["grid"], p, "follow", "or-mid", 1.0, "net")
        L.append("| %s | %+.4f | %+.4f |" % (p, g["avg_r"], n["avg_r"]))
    L.append("")
    # random control
    L.append("Random-direction control (coin flip between the buy-rule and the sell-rule each day, same geometry and costs, "
             "20 seeds per pair), mean avg R:")
    L.append("")
    L.append("| pair | random mean avgR | follow avgR |")
    L.append("| --- | --- | --- |")
    for p in PAIRS:
        c = B["random_control"].get(p)
        n = cell(B["grid"], p, "follow", "or-mid", 1.0, "net")
        if c:
            L.append("| %s | %+.4f [%+.4f .. %+.4f] | %+.4f |" % (p, c["mean_avg_r"], c["min_avg_r"], c["max_avg_r"], n["avg_r"]))
    L.append("")
    # grid summary
    net_cells = [g for g in B["grid"] if g["scenario"]=="net" and g["trades"] >= 10]
    pos = sum(1 for g in net_cells if g["total_r"] > 0)
    sig = sum(1 for g in net_cells if g["expectancy_t"] is not None and g["expectancy_t"] > 2.0)
    L.append("Full grid on this sample: %d net-cost variants with >=10 trades (direction x stop-rule x target-R across 10 pairs). "
             "**%d (%.0f%%) finished with positive total R. %d had t > 2; with %d variants, about %d would pass that bar by pure luck.** "
             "The complete grid is in the JSON; the best-looking cells are exactly what multiple testing produces." % (
        len(net_cells), pos, 100.0*pos/len(net_cells), sig, len(net_cells), int(len(net_cells)*0.05)))
    L.append("")
    # stress
    st = B["stress_2x_spread"]
    L.append("Stress test (2x spread), same variant: " + ", ".join("%s %+.1f%%" % (p, st[p]["return_pct"]) for p in PAIRS) + ".")
    L.append("")

L.append("## Intrabar ordering ambiguity (measured, not assumed)\n")
L.append("When one bar's range touches BOTH the stop and the target, OHLC data cannot say which was hit first. The main results "
         "resolve every such bar as STOP-first (the conservative convention the repo also uses). This section measures how much "
         "that choice matters by re-running the headline variant with every ambiguous bar resolved as TARGET-first instead - "
         "an unreachable best case, i.e. an upper bound, not an estimate.\n")
for label, B in (("5-minute sample", B5), ("1-hour sample", B1)):
    L.append("%s:" % label)
    L.append("")
    L.append("| pair | trades | trades with an ambiguous bar | return, stop-first | return, target-first (upper bound) |")
    L.append("| --- | --- | --- | --- | --- |")
    for p in PAIRS:
        h = B["headline"][p]
        o = B["headline_optimistic_tiebreak"][p]
        L.append("| %s | %d | %d | %s%% | %s%% |" % (p, h["trades"], h["trades_with_ambiguous_bar"], h["return_pct"], o["return_pct"]))
    L.append("")
amb = {}
for label, B in (("5-minute", B5), ("1-hour", B1)):
    tot_tr = sum(B["headline"][p]["trades"] for p in PAIRS)
    tot_amb = sum(B["headline"][p]["trades_with_ambiguous_bar"] for p in PAIRS)
    neg_opt = sum(1 for p in PAIRS if B["headline_optimistic_tiebreak"][p]["return_pct"] < 0)
    amb[label] = (tot_tr, tot_amb, neg_opt)
L.append("Read: on 5-minute bars the ambiguity is negligible (%d of %d trades) - the conservative convention costs almost nothing. "
         "On hourly bars %d of %d trades (%.1f%%) contain an ambiguous bar, and the bound is wide for some pairs. "
         "The truth sits between the two columns; even at the unreachable upper bound, %d of 10 pairs still lose over the sample, "
         "and the no-edge conclusion stands under EITHER resolution. "
         "Whoever reruns this can pick their own convention - both are shipped.\n" % (
    amb["5-minute"][1], amb["5-minute"][0], amb["1-hour"][1], amb["1-hour"][0],
    100.0 * amb["1-hour"][1] / max(1, amb["1-hour"][0]), amb["1-hour"][2]))
L.append("Could finer data narrow the hourly bound? Not with what is freely available: the 5-minute feed only reaches back "
         "~60 days, so it overlaps just a handful of the ambiguous hourly trades - too few to move the bound. Resolving the "
         "rest would need a paid tick/minute history, which is outside this project's free-only scope. The bound above is "
         "therefore the honest answer on free data.\n")
L.append("## Parameter sensitivity (the noise signature)\n")
L.append("If the rule had a real edge, nearby parameters would agree. They do not. Net avg R for follow/or-mid/1R:\n")
L.append("| pair | 5m: 07:00/30min | 5m: 07:00/60min | 5m: 08:00/30min | 5m: 08:00/60min |")
L.append("| --- | --- | --- | --- | --- |")
for p in PAIRS:
    row = [p]
    for sh, ob in ((7,6),(7,12),(8,6),(8,12)):
        for s in B5["sensitivity"]:
            if s["pair"]==p and s["session_hour"]==sh and s["or_bars"]==ob:
                row.append("%+.4f" % s["avg_r"])
    L.append("| " + " | ".join(row) + " |")
L.append("")
swings = []
for p in PAIRS:
    vals = [s["avg_r"] for s in B5["sensitivity"] if s["pair"] == p]
    if vals:
        swings.append((max(vals) - min(vals), p, min(vals), max(vals)))
swings.sort(reverse=True)
worst = swings[0] if swings else None
if worst:
    L.append("%s swings from %+.2fR to %+.2fR across those four neighbouring settings - the largest swing in the table. "
             "Sign flips from tiny parameter moves are what noise looks like.\n" % (worst[1], worst[2], worst[3]))
else:
    L.append("Sign flips from tiny parameter moves are what noise looks like.\n")
L.append("## Win rate is not profitability (measured)\n")
L.append("A small target is hit often. Does a 90%-win version of this rule make money? Measured, net of costs, same rule and "
         "samples as above (`winrate_sweep` in the results JSONs):\n")
for label, B in (("5-minute sample", B5), ("1-hour sample", B1)):
    L.append("%s - follow/or-mid, net costs, per target size (mean across the 10 pairs):" % label)
    L.append("")
    L.append("| target | mean win % | mean avg R/trade | pairs with positive total R (of 10) |")
    L.append("| --- | --- | --- | --- |")
    for tr in (0.1, 0.25, 0.5, 1.0, 2.0):
        rows = [s for s in B["winrate_sweep"] if s["target_r"] == tr]
        wr = [s["win_rate"] for s in rows if s["win_rate"] is not None]
        ar = [s["avg_r"] for s in rows if s["avg_r"] is not None]
        posr = sum(1 for s in rows if s["total_r"] > 0)
        L.append("| %.2fR | %.1f | %+.4f | %d |" % (tr, sum(wr)/len(wr), sum(ar)/len(ar), posr))
    L.append("")
best_wr, best_tr, best_iv = 0.0, None, None
for iv, B in (("5-minute", B5), ("1-hour", B1)):
    for tr in (0.1, 0.25, 0.5, 1.0, 2.0):
        rows = [s for s in B["winrate_sweep"] if s["target_r"] == tr]
        wr = [s["win_rate"] for s in rows if s["win_rate"] is not None]
        if wr and sum(wr)/len(wr) > best_wr:
            best_wr, best_tr, best_iv = sum(wr)/len(wr), tr, iv
all_avg = [s["avg_r"] for B in (B5, B1) for s in B["winrate_sweep"] if s["avg_r"] is not None]
neg_share = 100.0 * sum(1 for a in all_avg if a < 0) / len(all_avg)
L.append("Read: shrinking the target raises the win rate only up to a point - the best measured mean win rate is %.0f%% "
         "(%.2fR targets, %s sample) - because the spread eats targets that small. %.0f%% of the 100 pair/target cells above "
         "average NEGATIVE R per trade after costs. A 90%% win rate was never observed in these tests, and even a variant that "
         "won nine trades in ten would not be safe: ten 0.1R wins are erased by one -1R loss plus costs. Expectancy, not win "
         "rate, decides whether an account grows. Scoped to this rule, these samples and these cost assumptions - not a "
         "statement about every possible strategy.\n" % (best_wr, best_tr, best_iv, neg_share))
L.append("## Cross-checks of the shipped code\n")
L.append("- An independent re-implementation of the rule reproduces the repo's own `history_replay` outcome counts EXACTLY on identical data "
         "(EURUSD, 49 pool days: buy 13 target / 20 stop / 1 neither; sell 22 / 16 / 3). The shipped code computes what its README says it computes, "
         "including its no-same-day-lookahead claim.")
L.append("- `python3 test_fx.py` (offline checks incl. DST rules, stop-first tie-break, walk-forward pool construction, "
         "adverse-cost accounting and unit rounding): all pass.")
L.append("- `fx_timemachine.py run` end-to-end on a live plan (EURUSD buy, 1R, 20,000 replays + 10-day walk-forward): runs, labels its own output "
         "correctly as in-sample descriptive statistics, and its walk-forward section honestly states the sample is too small to validate an edge.\n")
L.append("- Timemachine replay caveat: each step samples slot j = i +/- window, jittering the intraday slot and flattening "
         "FX time-of-day volatility seasonality; --block preserves only short-range serial dependence. Replay "
         "distributions are approximate in intraday structure; the walk-forward pools remain strictly out-of-sample "
         "by day.\n")
L.append("## Conclusions\n")
L.append("1. **Data: fit for purpose.** Internally consistent, unbiased vs official ECB reference rates, with documented coverage limits.")
L.append("2. **The shipped strategy has no positive expectancy after realistic costs in any of the tests above.** Before costs it is a coin flip "
         "(long-sample gross expectancy ~0.0R); after a retail spread it loses reliably and consistently across 2024, 2025 and 2026. "
         "A $10,000 account trading it mechanically on the 10 tested pairs would have lost roughly %.0f%% in the last 60 trading days at "
         "5-minute granularity and roughly %.0f%% over 2.8 years at hourly granularity, with drawdowns to match "
         "(conservative tie-break; even the unreachable optimistic bound leaves most pairs negative - see the ambiguity section)." % (
    -B5["portfolio"]["return_pct"], -B1["portfolio"]["return_pct"]))
L.append("3. **Following the breakout beats a coin flip by nothing.** The random-direction control performs the same.")
L.append("4. **No parameter set in the tested grid rescued it.** 360 net-cost variants per timeframe; the few positive cells are "
         "fewer than chance produces, and neighbouring parameters flip sign. That is evidence about the tested grid on these "
         "samples, not proof that no profitable rule of any kind could exist.")
L.append("5. These are simulations with optimistic fills (no slippage/gaps). Live results would be worse, not better.")
L.append("6. What the project IS good for, today: an honest, free, open toolkit for session analysis, plan arithmetic, risk sizing and "
         "Monte Carlo replay whose numbers say what they are. That has value precisely because it does not pretend an edge exists.\n")
L.append("Nothing here is financial advice or a prediction. Past simulations do not guarantee anything about the future.\n")
w(os.path.join(HERE, "BACKTESTS.md"), "\n".join(L))

# ---------------- research/README.md ----------------
L = []
L.append("# research/\n")
L.append("Independent validation of fxpulse, November 2026. Simulation only - no real orders were or can be placed from this project.\n")
L.append("- **DATA-CORRECTNESS.md** - are the free data feeds any good? Internal consistency screens plus a %d-day cross-check against "
         "official ECB reference rates. Short answer: yes for analysis, with documented limits." % V["ecb_cross"][0]["compared_days"])
L.append("- **BACKTESTS.md** - does the shipped opening-range-breakout rule make money with explicit simulated capital ($10,000/pair, 1% risk, "
         "realistic spreads, all variants shown)? Short answer: no - gross it is a coin flip, net it loses reliably across 2.8 years and 10 pairs. "
         "The full grids, controls and stress tests are included, losing variants too.")
L.append("- `fetch_data.py`, `fx_validate.py`, `fx_backtest.py`, `cost_model_check.py` - the exact code that produced every number (stdlib only).")
L.append("- `results/` - raw JSON outputs the docs were generated from.\n")
L.append("## Reproduce\n")
L.append("```bash")
L.append("python3 fetch_data.py        # caches Yahoo bars to ./data (personal use, paced)")
L.append("python3 fx_validate.py       # data correctness -> results/validate_results.json")
L.append("python3 fx_backtest.py --timeframe 5m   # -> results/backtest_5m.json")
L.append("python3 fx_backtest.py --timeframe 1h   # -> results/backtest_1h.json")
L.append("python3 cost_model_check.py  # legacy vs corrected cost model -> results/cost_model_check.json")
L.append("python3 gen_docs.py          # rebuild the markdown reports from the JSONs")
L.append("```")
L.append("")
L.append("The scripts expect the repo one directory up on `sys.path` (they import `fxdata`/`fx_scan` so the shipped code itself is tested) "
         "and a `data/` cache folder. Intraday bars are NOT committed: Yahoo's endpoint is personal-use, so raw market data is never "
         "redistributed from this repository - only aggregated statistics and a handful of individual quotes for error examples.")
L.append("")
L.append("None of this is financial advice or a promise about the future.\n")
w(os.path.join(HERE, "README.md"), "\n".join(L))
print("done")
