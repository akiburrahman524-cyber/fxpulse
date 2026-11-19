#!/usr/bin/env python3
"""fx_size: risk-based position sizing for a forex plan.

    python3 fx_size.py --balance 5000 --risk 50             # uses plan.json
    python3 fx_size.py --pair EURUSD --stop-pips 15 --balance 5000 --risk-pct 1
    python3 fx_size.py --balance 5000 --risk 50 --json

Arithmetic only: lots = risk amount / (stop pips x pip value). Pip values use
Frankfurter reference rates (official reference rates, updated a few times a
day, not live quotes). Simulation aid, not advice.
"""

import argparse
import json
import os
import sys

import fxdata

HERE = os.path.dirname(os.path.abspath(__file__))
PLAN_PATH = os.path.join(HERE, "plan.json")


def size_position(pair, stop_pips, balance, risk_amount=None, risk_pct=None, price=None):
    if risk_amount is None:
        if risk_pct is None:
            raise RuntimeError("pass --risk or --risk-pct")
        risk_amount = balance * risk_pct / 100.0
    if stop_pips <= 0:
        raise RuntimeError("stop must be a positive number of pips")
    pv = fxdata.pip_value_usd(pair, price=price)
    lots = risk_amount / (stop_pips * pv)
    units = int(round(lots * 100000, -2))  # round to 100 units (common broker step)
    return {
        "pair": pair,
        "balance_usd": balance,
        "risk_usd": round(risk_amount, 2),
        "stop_pips": stop_pips,
        "pip_value_usd_per_std_lot": round(pv, 4),
        "standard_lots": round(lots, 4),
        "units_approx": units,
        "max_loss_usd_at_stop": round(stop_pips * pv * lots, 2),
        "note": ("Sizing arithmetic with Frankfurter reference rates for pip values. "
                 "Brokers quote their own pip values and lot steps; check yours. "
                 "Simulation aid, not advice."),
    }


def main(argv=None):
    p = argparse.ArgumentParser(description="Risk-based lot sizing for a forex plan.")
    p.add_argument("--pair")
    p.add_argument("--stop-pips", type=float)
    p.add_argument("--balance", type=float, required=True, help="account balance in USD")
    p.add_argument("--risk", type=float, help="fixed risk amount in USD")
    p.add_argument("--risk-pct", type=float, help="risk as %% of balance")
    p.add_argument("--json", action="store_true")
    a = p.parse_args(argv)

    pair, stop_pips = a.pair, a.stop_pips
    if (not pair or stop_pips is None) and os.path.exists(PLAN_PATH):
        with open(PLAN_PATH) as f:
            plan = json.load(f)
        pair = pair or plan["pair"]
        stop_pips = stop_pips if stop_pips is not None else plan["risk_pips"]
    if not pair or stop_pips is None:
        sys.exit("pass --pair and --stop-pips, or run fx_plan.py --write first")
    pair = pair.upper()
    if pair not in fxdata.PAIRS:
        sys.exit("unknown pair %s" % pair)

    try:
        out = size_position(pair, stop_pips, a.balance, a.risk, a.risk_pct)
    except Exception as e:  # noqa: BLE001
        sys.exit("sizing failed: %s" % e)

    if a.json:
        print(json.dumps(out, indent=2))
        return 0
    print("%s  balance $%.2f  risk $%.2f over %.1f pips"
          % (out["pair"], out["balance_usd"], out["risk_usd"], out["stop_pips"]))
    print("  pip value $%.4f per standard lot -> %.4f standard lots (~%d units)"
          % (out["pip_value_usd_per_std_lot"], out["standard_lots"], out["units_approx"]))
    print("  max loss at the stop: $%.2f" % out["max_loss_usd_at_stop"])
    print("  %s" % out["note"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
