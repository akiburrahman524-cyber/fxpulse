#!/usr/bin/env python3
"""fx_timemachine: replay a forex plan before any money is involved.

Monte Carlo over the pair's OWN recent 5-minute bars (Yahoo chart endpoint,
unofficial, personal use), plus an empirical re-run of the same
opening-range-breakout rule on every past full day in the data.

    python3 fx_timemachine.py run                       # uses plan.json
    python3 fx_timemachine.py run --write               # save timemachine.json
    python3 fx_timemachine.py run --pair EURUSD --side buy --entry 1.0850 \
        --stop 1.0835 --target 1.0880 --entry-time 08:15
    python3 fx_timemachine.py run --seed 7 --replays 20000 --json

Method (stated so anyone can check it):
  1. Fetch 60 days of 5-minute bars. Keep FULL UTC days before the plan day
     (a full day has ~288 bars; days with <270 bars are dropped).
  2. Pool: for every slot j of the day, each past day's bar as ratios to the
     previous bar's close: (open, high, low, close) / prev close.
  3. One replay starts at the entry price at the entry slot and walks to
     --until. For each step i it picks slot j = i + randint(-window, window)
     and one random past bar from pool[j], scaled to the current price. The
     stop is checked before the target within a bar (conservative).
  4. Outcomes: target / stop (first touch) or neither at --until. R = +targetR
     at the target, -1 at the stop, else (exit-entry)/risk with sign by side.
     The spread is then charged once per replay as an adverse fill cost in R
     (entry and exit each half a spread worse than mid); trigger levels are
     not moved.
  5. Verdict: among replays that hit a side, compare target share with the
     break-even share 1/(1+R). <5 points gap = close to break-even, 5-15 =
     leans, 15+ = strongly. Same plan, same data, same seed = same numbers.
  6. History: the same ORB rule re-run on each full past day.

A resampling of recent bars is descriptive statistics about the recent past.
It is not a prediction: news, gaps and thin liquidity can do what the last 60
days never did. A gap through the stop counts -1R here; a real fill can be
worse. Simulation only, not financial advice.
"""

import argparse
import datetime
import json
import os
import random
import statistics
import sys

import fxdata
import fx_scan

HERE = os.path.dirname(os.path.abspath(__file__))
PLAN_PATH = os.path.join(HERE, "plan.json")
OUT_PATH = os.path.join(HERE, "timemachine.json")

BARS_PER_DAY = 288
MIN_DAY_BARS = 270


def utc_minutes(ts):
    d = datetime.datetime.fromtimestamp(ts, datetime.timezone.utc)
    return d.hour * 60 + d.minute


def full_days(bars, before_date, exclude_last=0):
    """Full UTC days strictly before `before_date` (no same-day bars, so no
    same-day lookahead), optionally also excluding the most recent
    `exclude_last` full days (chronological holdout)."""
    days = fx_scan.split_days(bars)
    out = []
    for d in sorted(days):
        if before_date is not None and d >= before_date:
            continue
        if len(days[d]) >= MIN_DAY_BARS:
            out.append((d, days[d]))
    if exclude_last:
        out = out[:-exclude_last]
    return out


def build_pool(sessions):
    """Returns (pool, series):
    pool: slot -> list of (open, high, low, close) ratios vs previous bar close
    series: list of days, each a list of (slot, ratios) keeping day identity
    for block resampling that preserves serial dependence within a day."""
    pool = {}
    series = []
    for day in sessions:
        prev_close = None
        seq = []
        for i, b in enumerate(day):
            if prev_close:
                pc = prev_close
                ratios = (b["open"] / pc, b["high"] / pc, b["low"] / pc, b["close"] / pc)
                pool.setdefault(i, []).append(ratios)
                seq.append((i, ratios))
            prev_close = b["close"]
        series.append(seq)
    return pool, series


def simulate(pool, entry, stop, target, start_slot, end_slot, replays, seed, window, side, block=1, series=None, cost_r=0.0):
    """cost_r: adverse round-trip cost in R units (spread / intended risk),
    subtracted once from every replay's R: entry and exit fills are each half
    a spread worse than mid. Trigger levels are NOT moved - bid/ask trigger
    displacement is a second-order effect and is not modeled."""
    rng = random.Random(seed)
    max_slot = max(pool)
    start_slot = max(1, min(start_slot, max_slot))
    end_slot = max(start_slot, min(end_slot, max_slot))
    counts = {"target": 0, "stop": 0, "neither": 0}
    r_sum = 0.0
    finals = []
    risk = abs(entry - stop)
    long = side == "buy"
    block = max(1, block)
    for _ in range(replays):
        price = entry
        outcome = "neither"
        streak = []  # consecutive bars from one past day, preserves serial dependence
        for i in range(start_slot, end_slot + 1):
            if streak:
                o, h, l, c = streak.pop(0)
            else:
                j = i + rng.randint(-window, window)
                j = max(1, min(j, max_slot))
                if block > 1 and series:
                    day_seq = series[rng.randrange(len(series))]
                    take = [(s, r) for (s, r) in day_seq if s >= j][:block]
                    if take:
                        o, h, l, c = take[0][1]
                        streak = [r for (_, r) in take[1:]]
                    else:
                        o, h, l, c = pool[j][rng.randrange(len(pool[j]))]
                else:
                    o, h, l, c = pool[j][rng.randrange(len(pool[j]))]
            hi, lo = price * h, price * l
            hit_stop = (lo <= stop) if long else (hi >= stop)
            hit_target = (hi >= target) if long else (lo <= target)
            if hit_stop:  # stop first, conservative
                outcome = "stop"
                r_sum += -1.0 - cost_r
                price = stop
                break
            if hit_target:
                outcome = "target"
                r_sum += abs(target - entry) / risk - cost_r
                price = target
                break
            price = price * c
        counts[outcome] += 1
        if outcome == "neither":
            r = ((price - entry) if long else (entry - price)) / risk
            r_sum += r - cost_r
        finals.append(price)
    finals.sort()
    n = len(finals)
    return {
        "replays": replays, "seed": seed, "window": window, "block": block,
        "cost_r_per_trade": cost_r,
        "counts": counts,
        "avg_r": r_sum / replays,
        "median_final": finals[n // 2],
        "p5_final": finals[int(0.05 * n)],
        "p95_final": finals[min(n - 1, int(0.95 * n))],
    }


def verdict(sim, target_r):
    t, s = sim["counts"]["target"], sim["counts"]["stop"]
    if t + s == 0:
        return "no replay hit either side; nothing to compare"
    share = t / (t + s)
    be = 1.0 / (1.0 + target_r)
    gap = (share - be) * 100.0
    if abs(gap) < 5:
        word = "close to break-even"
    elif abs(gap) < 15:
        word = "leans toward the target" if gap > 0 else "leans toward the stop"
    else:
        word = "strongly toward the target" if gap > 0 else "strongly toward the stop"
    return ("target first %.1f%% of decided replays vs %.1f%% break-even at %.1fR -> %s (%+.1f pts)"
            % (share * 100, be * 100, target_r, word, gap))


def history_replay(sessions, pair, side, or_bars, session_open_min, target_r, london_session=False):
    """Re-run the ORB rule on every full past day. Each day's opening range
    uses only that day's own bars, and the range is fully formed before the
    entry is taken, so there is no same-day lookahead. First close beyond the
    range = entry; stop at range midpoint; stop checked first."""
    results = {"target": 0, "stop": 0, "neither": 0, "days": 0, "fired": 0}
    for day_date, day in sessions:
        results["days"] += 1
        open_min = session_open_min
        if london_session:
            open_min = fxdata.session_open_utc_minutes(day_date) + (session_open_min - 8 * 60)
        orng = fx_scan.opening_range(day, open_min, or_bars)
        if not orng:
            continue
        hi, lo, _ = orng
        mid = (hi + lo) / 2.0
        formed_after = open_min + or_bars * 5
        entry = None
        for idx, b in enumerate(day):
            if utc_minutes(b["ts"]) < formed_after:
                continue
            if side == "buy" and b["close"] > hi:
                entry = b["close"]
                stop = mid
                target = entry + target_r * (entry - stop)
                rest = day[idx + 1:]
                break
            if side == "sell" and b["close"] < lo:
                entry = b["close"]
                stop = mid
                target = entry - target_r * (stop - entry)
                rest = day[idx + 1:]
                break
        if entry is None:
            continue
        results["fired"] += 1
        outcome = "neither"
        for b in rest:
            if side == "buy":
                if b["low"] <= stop:
                    outcome = "stop"; break
                if b["high"] >= target:
                    outcome = "target"; break
            else:
                if b["high"] >= stop:
                    outcome = "stop"; break
                if b["low"] <= target:
                    outcome = "target"; break
        results[outcome] += 1
    return results


def walk_forward(all_sessions, pair, side, or_bars, target_r, n_days, replays, seed,
                 start_slot, end_slot, window, block, cost_r=0.0):
    """Genuine out-of-sample evaluation: for each of the last n_days full days
    D, the pool is rebuilt from days strictly before D only; the rule is then
    evaluated on D's own untouched bars (range formed before entry). The MC
    share from D's pool is recorded next to D's actual outcome, so the user
    can see what the sim would have said BEFORE that day versus what happened."""
    rows = []
    if n_days <= 0 or len(all_sessions) <= n_days + 5:
        return rows
    for k in range(len(all_sessions) - n_days, len(all_sessions)):
        day_date, day = all_sessions[k]
        prior = all_sessions[:k]
        pool, series = build_pool([d for (_, d) in prior])
        open_min = fxdata.session_open_utc_minutes(day_date)
        orng = fx_scan.opening_range(day, open_min, or_bars)
        row = {"day": str(day_date), "pool_days": len(prior), "fired": False}
        if orng:
            hi, lo, _ = orng
            mid = (hi + lo) / 2.0
            formed_after = open_min + or_bars * 5
            entry = stop = target = None
            for idx, b in enumerate(day):
                if utc_minutes(b["ts"]) < formed_after:
                    continue
                if side == "buy" and b["close"] > hi:
                    entry, stop, target = b["close"], mid, b["close"] + target_r * (b["close"] - mid)
                    rest = day[idx + 1:]
                    break
                if side == "sell" and b["close"] < lo:
                    entry, stop, target = b["close"], mid, b["close"] - target_r * (mid - b["close"])
                    rest = day[idx + 1:]
                    break
            if entry is not None:
                row["fired"] = True
                outcome = "neither"
                for b in rest:
                    if side == "buy":
                        if b["low"] <= stop:
                            outcome = "stop"; break
                        if b["high"] >= target:
                            outcome = "target"; break
                    else:
                        if b["high"] >= stop:
                            outcome = "stop"; break
                        if b["low"] <= target:
                            outcome = "target"; break
                sim = simulate(pool, entry, stop, target, start_slot, end_slot,
                               replays, seed, window, side, block=block, series=series, cost_r=cost_r)
                t, s = sim["counts"]["target"], sim["counts"]["stop"]
                row["sim_target_share_pct"] = round(100.0 * t / (t + s), 1) if (t + s) else None
                row["actual"] = outcome
        rows.append(row)
    return rows


def slot_of_time(text):
    hh, mm = text.split(":")
    return (int(hh) * 60 + int(mm)) // 5


def main(argv=None):
    p = argparse.ArgumentParser(description="Monte Carlo replay of a forex plan from the pair's own recent bars.")
    p.add_argument("cmd", choices=["run"])
    p.add_argument("--pair")
    p.add_argument("--side", choices=["buy", "sell"])
    p.add_argument("--entry", type=float)
    p.add_argument("--stop", type=float)
    p.add_argument("--target", type=float)
    p.add_argument("--entry-time", default="08:15", help="UTC HH:MM of the entry (default 08:15)")
    p.add_argument("--until", default="23:55", help="UTC HH:MM to end each replay (default 23:55)")
    p.add_argument("--replays", type=int, default=10000)
    p.add_argument("--seed", type=int, default=19)
    p.add_argument("--window", type=int, default=2)
    p.add_argument("--or-bars", type=int, default=12)
    p.add_argument("--min-days", type=int, default=20)
    p.add_argument("--holdout", type=int, default=0,
                   help="exclude the most recent N full days from the simulation pool (pool sensitivity check - NOT out-of-sample validation)")
    p.add_argument("--walkforward", type=int, default=0,
                   help="evaluate the rule on the last N full days, each against a pool of strictly earlier days (out-of-sample on untouched days; slower)")
    p.add_argument("--block", type=int, default=1,
                   help="resample blocks of N consecutive bars from one past day (default 1 = independent bars). Blocks preserve short-range serial dependence.")
    p.add_argument("--spread-pips", type=float, default=1.0,
                   help="assumed spread, charged as an adverse fill cost on entry AND exit (default 1 pip): each replay's R is reduced by spread/stop-distance. It changes what outcomes pay, not which level is touched first. Slippage and fees are NOT modeled and make real results worse.")
    p.add_argument("--write", action="store_true")
    p.add_argument("--json", action="store_true")
    a = p.parse_args(argv)

    plan = None
    if a.pair and a.entry and a.stop and a.target and a.side:
        plan = {"pair": a.pair.upper(), "side": a.side, "entry": a.entry,
                "stop": a.stop, "target": a.target, "day": None}
    elif os.path.exists(PLAN_PATH):
        with open(PLAN_PATH) as f:
            plan = json.load(f)
    else:
        sys.exit("no plan.json and no --pair/--side/--entry/--stop/--target given")

    pair = plan["pair"].upper()
    side = plan["side"]
    entry, stop, target = plan["entry"], plan["stop"], plan["target"]
    if pair not in fxdata.PAIRS:
        sys.exit("unknown pair %s" % pair)
    risk = abs(entry - stop)
    if risk == 0:
        sys.exit("entry equals stop")
    target_r = abs(target - entry) / risk

    fxdata.require_intraday()
    bars = fxdata.fetch_yahoo_bars(fxdata.PAIRS[pair], rng="60d", interval="5m")
    age = fxdata.bars_age_seconds(bars)
    before = None
    if plan.get("day"):
        before = datetime.date.fromisoformat(plan["day"])
    else:
        # no plan day given: exclude today's UTC date explicitly - a bar-count
        # threshold alone cannot guarantee a late-day partial day stays out
        before = datetime.datetime.fromtimestamp(bars[-1]["ts"], datetime.timezone.utc).date()
    sessions = full_days(bars, before, exclude_last=a.holdout)
    if len(sessions) < a.min_days:
        sys.exit("only %d full days of bars in the pool (need %d); refusing to simulate on too little data"
                 % (len(sessions), a.min_days))
    pool, series = build_pool([day for (_, day) in sessions])
    pool_window = "%s .. %s" % (sessions[0][0], sessions[-1][0])
    start_slot = slot_of_time(a.entry_time)
    end_slot = slot_of_time(a.until)

    # Costs: the spread is an adverse FILL cost, not a shift of the trigger
    # levels. A buy pays the ask (half a spread worse than mid) at entry and
    # receives the bid (half a spread worse) at every exit; a sell the
    # reverse. Charged in R against the intended stop distance, so every
    # replay pays cost_r = spread / risk exactly once per round trip. Which
    # level is touched first does not change (bid/ask trigger displacement
    # is a second-order effect and is not modeled).
    cost_r = fxdata.from_pips(pair, a.spread_pips) / risk

    sim = simulate(pool, entry, stop, target, start_slot, end_slot,
                   a.replays, a.seed, a.window, side, block=a.block, series=series, cost_r=cost_r)
    hist = history_replay(sessions, pair, side, a.or_bars, 8 * 60, target_r, london_session=True)
    wf = []
    if a.walkforward:
        all_sessions = full_days(bars, before, exclude_last=0)
        wf = walk_forward(all_sessions, pair, side, a.or_bars, target_r, a.walkforward,
                          min(a.replays, 2000), a.seed, start_slot, end_slot, a.window, a.block,
                          cost_r=cost_r)
    result = {
        "pair": pair, "side": side, "entry": entry, "stop": stop, "target": target,
        "spread_pips": a.spread_pips,
        "cost_r_per_trade": round(cost_r, 4),
        "target_r": round(target_r, 2), "sessions": len(sessions),
        "pool_window": pool_window, "holdout_days_excluded": a.holdout,
        "data_age_min": round(age / 60.0, 1) if age is not None else None,
        "entry_time_utc": a.entry_time, "until_utc": a.until,
        "simulation": sim, "observation": verdict(sim, target_r), "history": hist,
        "walkforward": wf,
        "caveat": ("IN-SAMPLE resampling of this pool's recent bars: descriptive statistics about the recent past, "
                   "NOT calibrated probabilities and NOT evidence of predictive edge. Bar resampling "
                   "weakens serial dependence (use --block to preserve some). Stop-first within each bar is "
                   "conservative. The spread is charged as an adverse fill cost on every replay's R; it does "
                   "not change which level is touched first. Gaps, slippage and fees are not modeled and make "
                   "real results worse. "
                   "The history re-run uses only each day's own bars (range formed before entry: no same-day "
                   "lookahead). Simulation only, not financial advice."),
    }
    if a.write:
        with open(OUT_PATH, "w") as f:
            json.dump(result, f, indent=2)

    if a.json:
        print(json.dumps(result, indent=2))
        return 0
    c = sim["counts"]
    print("%s %s  entry %.5f stop %.5f target %.5f (%.2fR); %.1f-pip spread = %.3fR adverse cost per trade (fills worse, trigger levels unchanged)"
          % (pair, side.upper(), entry, stop, target, target_r, a.spread_pips, cost_r))
    print("  pool: %d full days, %s%s, bars age %.1f min"
          % (len(sessions), pool_window,
             (" (holdout: last %d excluded)" % a.holdout) if a.holdout else "", age / 60.0 if age else -1))
    print("  %d replays (seed %d, block %d): target %d (%.1f%%)  stop %d (%.1f%%)  open at %s %d (%.1f%%)"
          % (sim["replays"], sim["seed"], sim["block"],
             c["target"], 100.0 * c["target"] / sim["replays"],
             c["stop"], 100.0 * c["stop"] / sim["replays"],
             a.until, c["neither"], 100.0 * c["neither"] / sim["replays"]))
    print("  avg R %+.3f   price at %s: median %.5f (p5 %.5f .. p95 %.5f)"
          % (sim["avg_r"], a.until, sim["median_final"], sim["p5_final"], sim["p95_final"]))
    print("  observation (in-sample, not calibrated, not evidence of edge): %s" % result["observation"])
    print("  history (%d past days, rule fired %d): target %d  stop %d  neither %d"
          % (hist["days"], hist["fired"], hist["target"], hist["stop"], hist["neither"]))
    if wf:
        fired = [r for r in wf if r["fired"]]
        hit = sum(1 for r in fired if r["actual"] == "target")
        stopped = sum(1 for r in fired if r["actual"] == "stop")
        print("  walk-forward on %d untouched days: rule fired %d -> target %d, stop %d, neither %d"
              % (len(wf), len(fired), hit, stopped, len(fired) - hit - stopped))
        print("    (this is the genuine out-of-sample check; with this few fires it cannot validate or kill an edge - treat as transparency, not proof)")
        for r in wf:
            if r["fired"]:
                print("    %s: sim-from-prior-days said %.1f%% target-first, actual: %s"
                      % (r["day"], r["sim_target_share_pct"], r["actual"]))
    print("  %s" % result["caveat"])
    if a.write:
        print("  saved to %s" % OUT_PATH)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
