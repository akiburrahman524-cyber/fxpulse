#!/usr/bin/env python3
"""Measure the effect of the 2026-11-19 cost-model correction on identical data.

The pre-fix backtest shifted the stop and target TRIGGER levels half a spread
in the FAVORABLE direction (stop further away, target nearer) while its
comment claimed the shift was adverse. The corrected model keeps triggers at
the mid-bar levels and charges the spread as an adverse fill cost: entry and
every exit fill half a spread worse than mid, R measured against the intended
stop distance.

This script runs the headline variant (follow/or-mid/1R, 08:00 London, 1x
spread) both ways on the same cached bars and writes
results/cost_model_check.json. Stdlib only. Simulation only, not advice.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HERE = os.path.dirname(os.path.abspath(__file__))
import fx_backtest as bt  # noqa: E402


def run(iv):
    bars_by_pair = {p: bt.load_bars(p, iv) for p in bt.PAIRS}
    series_cache = {p: bt.usd_per_quote_series(p, bars_by_pair) for p in bt.PAIRS if p[3:] != "USD"}
    or_bars = 12 if iv == "5m" else 1
    out = {}
    for p in bt.PAIRS:
        fixed = bt.backtest_pair(p, bars_by_pair[p], iv, "follow", "or-mid", 1.0, 8, or_bars,
                                 1.0, series_cache, cost_model="fill")
        legacy = bt.backtest_pair(p, bars_by_pair[p], iv, "follow", "or-mid", 1.0, 8, or_bars,
                                  1.0, series_cache, cost_model="legacy-shift")
        out[p] = {
            "trades": fixed["trades"],
            "legacy_avg_r": legacy["avg_r"], "fixed_avg_r": fixed["avg_r"],
            "legacy_win_rate": legacy["win_rate"], "fixed_win_rate": fixed["win_rate"],
            "legacy_return_pct": legacy["return_pct"], "fixed_return_pct": fixed["return_pct"],
            "legacy_total_r": legacy["total_r"], "fixed_total_r": fixed["total_r"],
        }
    return out


res = {"5m": run("5m"), "1h": run("1h")}
path = os.path.join(HERE, "results", "cost_model_check.json")
with open(path, "w") as f:
    json.dump(res, f, indent=2)
print("wrote", path)
for iv in ("5m", "1h"):
    print("\n%s headline variant, identical bars, legacy (favorable trigger shift) vs fixed (adverse fill cost):" % iv)
    print("%-7s %7s %12s %12s %12s %12s" % ("pair", "trades", "legacy avgR", "fixed avgR", "legacy ret%", "fixed ret%"))
    for p in bt.PAIRS:
        r = res[iv][p]
        print("%-7s %7d %12s %12s %12s %12s" % (p, r["trades"], r["legacy_avg_r"], r["fixed_avg_r"],
                                                r["legacy_return_pct"], r["fixed_return_pct"]))
