---
name: fxpulse-plan
description: Build an entry/stop/target plan for a forex pair from the session opening range, then replay it 10,000 times with the Time Machine before any money is involved. Use when the user wants to evaluate a specific trade idea.
---

1. `python3 fx_plan.py PAIR buy|sell --target-r 1 --write` (ask the user for pair, side and target R if missing).
2. `python3 fx_timemachine.py run --entry-time HH:MM` (UTC entry time).
3. `python3 fx_size.py --balance B --risk-pct P` only if the user gives a balance and risk.
4. `python3 fx_ticket.py confirm --lots L` only if the user explicitly wants to paper-trade it; their typed "yes" is required.

Always repeat the Time Machine caveat: resampled recent bars are statistics
about the recent past, not a prediction; stop-first rule is conservative;
real fills can be worse through gaps. Never frame the verdict as advice.
