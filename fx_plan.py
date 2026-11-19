#!/usr/bin/env python3
"""fx_plan: build an entry/stop/target plan for a forex pair.

Given a pair and a side, computes a plan from the current session's opening
range (same data as fx_scan): entry trigger, stop rule, target as an R
multiple, all with pip distances. Writes plan.json for the other tools.

    python3 fx_plan.py EURUSD buy                     # plan at current breakout levels
    python3 fx_plan.py USDJPY sell --target-r 2 --stop or-far
    python3 fx_plan.py EURUSD buy --entry 1.0850 --stop 1.0835 --target 1.0880 --write

Stop rules:
  or-mid   midpoint of the opening range (default)
  or-far   far side of the opening range
  fixed    pass --stop explicitly

This describes levels and arithmetic. It is not advice to trade them.
"""

import argparse
import json
import os
import sys

import fxdata
import fx_scan

PLAN_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "plan.json")


def build_plan(pair, side, target_r, stop_rule, session_open_min, or_bars,
               entry=None, stop=None, target=None, london_session=False):
    fxdata.require_intraday()
    symbol = fxdata.PAIRS[pair]
    bars = fxdata.fetch_yahoo_bars(symbol, rng="5d", interval="5m")
    days = fx_scan.split_days(bars)
    latest = max(days)
    day = days[latest]
    last = day[-1]["close"]
    open_min = session_open_min
    if london_session:
        open_min = fxdata.session_open_utc_minutes(latest) + (session_open_min - 8 * 60)
    orng = fx_scan.opening_range(day, open_min, or_bars)
    if not orng and (entry is None or stop is None):
        raise RuntimeError("no opening-range window formed yet for %s; pass --entry/--stop explicitly" % pair)

    if orng:
        hi, lo, _ = orng
        mid = (hi + lo) / 2.0
    else:
        hi = lo = mid = None

    if entry is None:
        # breakout entry: last close if already beyond the range, else the range edge
        if side == "buy":
            entry = last if last > hi else hi
        else:
            entry = last if last < lo else lo
    if stop is None:
        stop = {"or-mid": mid, "or-far": (lo if side == "buy" else hi)}[stop_rule]
    if target is None:
        risk = abs(entry - stop)
        if risk == 0:
            raise RuntimeError("entry equals stop; cannot size a plan")
        target = entry + target_r * risk if side == "buy" else entry - target_r * risk

    risk = abs(entry - stop)
    reward = abs(target - entry)
    if risk == 0:
        raise RuntimeError("entry equals stop; cannot size a plan")
    if side == "buy" and not (stop < entry < target):
        raise RuntimeError("buy plan needs stop < entry < target (got stop=%.5f entry=%.5f target=%.5f)"
                           % (stop, entry, target))
    if side == "sell" and not (target < entry < stop):
        raise RuntimeError("sell plan needs target < entry < stop (got stop=%.5f entry=%.5f target=%.5f)"
                           % (stop, entry, target))

    return {
        "pair": pair, "side": side, "day": str(latest),
        "entry": round(entry, 6), "stop": round(stop, 6), "target": round(target, 6),
        "risk_pips": round(fxdata.to_pips(pair, risk), 1),
        "reward_pips": round(fxdata.to_pips(pair, reward), 1),
        "target_r": round(reward / risk, 2),
        "session_open_utc": open_min // 60,
        "session_definition": "Europe/London local (DST-aware)" if london_session else "fixed UTC",
        "or_high": hi, "or_low": lo,
        "last": last,
        "note": "Levels from the session opening range on unofficial Yahoo chart data. Simulation only, not advice.",
    }


def main(argv=None):
    p = argparse.ArgumentParser(description="Build an entry/stop/target plan for a forex pair.")
    p.add_argument("pair")
    p.add_argument("side", choices=["buy", "sell"])
    p.add_argument("--target-r", type=float, default=1.0, help="target as a multiple of risk (default 1R)")
    p.add_argument("--stop-rule", choices=["or-mid", "or-far", "fixed"], default="or-mid")
    p.add_argument("--entry", type=float)
    p.add_argument("--stop", type=float)
    p.add_argument("--target", type=float)
    p.add_argument("--session-open", type=int, default=8,
                   help="session open hour in Europe/London local time (default 8; DST-aware)")
    p.add_argument("--session-open-utc", type=int, default=None,
                   help="override: fixed session open hour in UTC")
    p.add_argument("--or-bars", type=int, default=12)
    p.add_argument("--write", action="store_true", help="save plan.json for fx_timemachine/fx_size/fx_ticket")
    p.add_argument("--json", action="store_true")
    a = p.parse_args(argv)

    pair = a.pair.upper()
    if pair not in fxdata.PAIRS:
        sys.exit("unknown pair %s (known: %s)" % (pair, ", ".join(sorted(fxdata.PAIRS))))

    try:
        london = a.session_open_utc is None
        open_min = (a.session_open_utc if a.session_open_utc is not None else a.session_open) * 60
        plan = build_plan(pair, a.side, a.target_r, a.stop_rule,
                          open_min, a.or_bars, a.entry, a.stop, a.target, london_session=london)
    except Exception as e:  # noqa: BLE001
        sys.exit("plan failed: %s" % e)

    if a.write:
        with open(PLAN_PATH, "w") as f:
            json.dump(plan, f, indent=2)

    if a.json:
        print(json.dumps(plan, indent=2))
        return 0
    print("%s %s  day %s  (session open %02d:00 UTC, %s)" % (plan["pair"], plan["side"].upper(), plan["day"], plan["session_open_utc"], plan["session_definition"]))
    if plan["or_high"] is not None:
        print("  opening range  %.5f .. %.5f" % (plan["or_low"], plan["or_high"]))
    print("  entry  %.5f" % plan["entry"])
    print("  stop   %.5f   (%.1f pips risk)" % (plan["stop"], plan["risk_pips"]))
    print("  target %.5f   (%.1f pips reward, %.2fR)" % (plan["target"], plan["reward_pips"], plan["target_r"]))
    print("  last   %.5f" % plan["last"])
    if a.write:
        print("  saved to %s" % PLAN_PATH)
    print(plan["note"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
