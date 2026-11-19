#!/usr/bin/env python3
"""fx_ticket: paper-trade ticket with an explicit human yes.

Reads plan.json (+ optional sizing from fx_size.py), shows one ticket in
plain words, and only after you type "yes" appends it to journal.json as a
SIMULATED trade. This tool cannot reach any broker and never will from this
command; it writes a local journal file only.

    python3 fx_ticket.py show
    python3 fx_ticket.py confirm --lots 0.05      # asks for your yes
    python3 fx_ticket.py journal
"""

import argparse
import datetime
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PLAN_PATH = os.path.join(HERE, "plan.json")
JOURNAL_PATH = os.path.join(HERE, "journal.json")


def load_plan():
    if not os.path.exists(PLAN_PATH):
        sys.exit("no plan.json - run fx_plan.py --write first")
    with open(PLAN_PATH) as f:
        return json.load(f)


def ticket_text(plan, lots=None):
    lines = [
        "PAPER TRADE - SIMULATION, no broker involved",
        "  %s %s" % (plan["pair"], plan["side"].upper()) + ("  %.4f std lots" % lots if lots else ""),
        "  entry  %.5f" % plan["entry"],
        "  stop   %.5f  (%.1f pips)" % (plan["stop"], plan["risk_pips"]),
        "  target %.5f  (%.1f pips, %.2fR)" % (plan["target"], plan["reward_pips"], plan["target_r"]),
    ]
    if lots:
        risk_usd = plan["risk_pips"] * 10.0 * lots if plan["pair"][3:] == "USD" else None
        if risk_usd:
            lines.append("  approx risk at stop: $%.2f (USD-quote pair arithmetic)" % risk_usd)
    lines.append("Status: READY - nothing is recorded until you confirm with 'yes'.")
    return "\n".join(lines)


def main(argv=None):
    p = argparse.ArgumentParser(description="Paper-trade ticket with explicit confirmation.")
    p.add_argument("cmd", choices=["show", "confirm", "journal"])
    p.add_argument("--lots", type=float, help="standard lots from fx_size.py")
    p.add_argument("--yes", action="store_true", help="skip the interactive prompt (scripts only)")
    a = p.parse_args(argv)

    if a.cmd == "journal":
        if not os.path.exists(JOURNAL_PATH):
            print("journal is empty")
            return 0
        with open(JOURNAL_PATH) as f:
            entries = json.load(f)
        for e in entries:
            print("%s  %s %s %s  entry %.5f stop %.5f target %.5f%s"
                  % (e["time_utc"], e["pair"], e["side"].upper(),
                     ("%.4f lots" % e["lots"]) if e.get("lots") else "no size",
                     e["entry"], e["stop"], e["target"],
                     ("  -> " + e["outcome"]) if e.get("outcome") else ""))
        print("(%d simulated trades, all paper)" % len(entries))
        return 0

    plan = load_plan()
    print(ticket_text(plan, a.lots))
    if a.cmd == "show":
        return 0

    if not a.yes:
        answer = input("Type 'yes' to record this SIMULATED trade in the local journal: ").strip().lower()
        if answer != "yes":
            print("not recorded.")
            return 1
    entries = []
    if os.path.exists(JOURNAL_PATH):
        with open(JOURNAL_PATH) as f:
            entries = json.load(f)
    entries.append({
        "time_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        "pair": plan["pair"], "side": plan["side"],
        "entry": plan["entry"], "stop": plan["stop"], "target": plan["target"],
        "lots": a.lots, "outcome": None, "simulation": True,
    })
    with open(JOURNAL_PATH, "w") as f:
        json.dump(entries, f, indent=2)
    print("recorded in %s as a simulated trade. Track the outcome yourself; this journal does not watch prices." % JOURNAL_PATH)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
