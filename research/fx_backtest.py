#!/usr/bin/env python3
"""fxpulse profitability backtest with explicit simulated capital.

Reimplements the shipped opening-range-breakout (ORB) workflow end-to-end
(fx_scan -> fx_plan -> simulated execution) on cached historical bars,
REUSING the repo's own functions where the rule is defined
(fx_scan.split_days / fx_scan.opening_range / fxdata.session_open_utc_minutes),
so the shipped code paths are the ones under test.

Simulated capital: USD 10,000 per pair, risk 1% of current equity per trade,
position size from stop distance and pip value, rounded to 100 units.
Costs: per-pair retail-typical spread applied adversely at entry AND exit
(half-spread each side, same convention as the repo). Scenarios: gross (0x),
net (1x), stress (2x). Slippage and gaps NOT modeled: real results are worse.

Simulation only. Not financial advice. No real orders are possible here.
"""
import argparse, datetime, json, math, os, random, statistics, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import fxdata, fx_scan  # repo code under test

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
PAIRS = ["EURUSD","GBPUSD","USDJPY","USDCHF","USDCAD","AUDUSD","NZDUSD",
         "EURGBP","EURJPY","GBPJPY"]
SPREAD_PIPS = {"EURUSD":0.6,"GBPUSD":0.9,"USDJPY":0.7,"USDCHF":1.0,"USDCAD":1.2,
               "AUDUSD":0.8,"NZDUSD":1.4,"EURGBP":1.1,"EURJPY":1.2,"GBPJPY":2.0}
START_EQUITY = 10000.0
RISK_PCT = 1.0

def utc_minutes(ts):
    d = datetime.datetime.utcfromtimestamp(ts)
    return d.hour*60 + d.minute

def utc_date(ts):
    return datetime.datetime.utcfromtimestamp(ts).date()

def load_bars(pair, iv):
    with open(os.path.join(DATA, "%s-%s.json" % (pair, iv))) as f:
        return json.load(f)

def usd_per_quote_series(pair, bars_by_pair):
    """date -> USD value of 1 unit of `pair`'s quote currency, from daily last closes."""
    quote = pair[3:]
    if quote == "USD":
        return None  # 1.0
    src = "USD" + quote if ("USD" + quote) in bars_by_pair else quote + "USD"
    inv = src.startswith("USD")
    out = {}
    for b in bars_by_pair[src]:
        d = utc_date(b["ts"])
        out[d] = (1.0 / b["close"]) if inv else b["close"]
    return out

def usd_per_quote_on(pair, d, series_cache):
    quote = pair[3:]
    if quote == "USD":
        return 1.0
    s = series_cache[pair]
    # walk back up to 7 days for weekends/holidays
    for k in range(8):
        dd = d - datetime.timedelta(days=k)
        if dd in s:
            return s[dd]
    return list(s.values())[-1]

def day_events(day_bars, open_min, or_bars):
    """Precompute opening range and first breakout events for a day.
    Returns dict or None. Uses the repo's opening_range()."""
    orng = fx_scan.opening_range(day_bars, open_min, or_bars)
    if not orng:
        return None
    hi, lo, n = orng
    mid = (hi + lo) / 2.0
    formed_after = open_min + or_bars * 5
    ev = {"hi": hi, "lo": lo, "mid": mid, "buy": None, "sell": None, "any": None}
    for idx, b in enumerate(day_bars):
        if utc_minutes(b["ts"]) < formed_after:
            continue
        if ev["buy"] is None and b["close"] > hi:
            ev["buy"] = (idx, b["close"])
        if ev["sell"] is None and b["close"] < lo:
            ev["sell"] = (idx, b["close"])
        if ev["any"] is None and (b["close"] > hi or b["close"] < lo):
            ev["any"] = (idx, b["close"], "buy" if b["close"] > hi else "sell")
        if ev["buy"] and ev["sell"] and ev["any"]:
            break
    return ev

def run_trade(day_bars, ev, direction, stop_rule, target_r, half_spread, rng=None, tie="stop"):
    """Simulate one ORB trade. Returns (side, entry, exit, r_multiple) or None."""
    if direction == "follow":
        if not ev["any"]:
            return None
        idx, close, side = ev["any"]
    elif direction in ("buy", "sell"):
        e = ev[direction]
        if not e:
            return None
        idx, close = e
        side = direction
    else:  # random control: coin-flip between the buy-rule and sell-rule
        # for the day, so entry/stop/target geometry is always valid
        pick = rng.choice(["buy", "sell"])
        e = ev[pick]
        if not e:
            return None
        idx, close = e
        side = pick
    hi, lo, mid = ev["hi"], ev["lo"], ev["mid"]
    entry = close
    stop = mid if stop_rule == "or-mid" else (lo if side == "buy" else hi)
    risk = abs(entry - stop)
    if risk <= 0:
        return None
    target = entry + target_r * risk if side == "buy" else entry - target_r * risk
    adv = half_spread if side == "buy" else -half_spread
    e_entry = entry + adv
    e_stop = stop - adv
    e_target = target - adv
    e_risk = abs(e_entry - e_stop)
    exit_price = None
    ambiguous = 0
    for b in day_bars[idx + 1:]:
        if side == "buy":
            hs = b["low"] <= e_stop
            ht = b["high"] >= e_target
        else:
            hs = b["high"] >= e_stop
            ht = b["low"] <= e_target
        if hs and ht:
            ambiguous += 1
            # bar touched BOTH levels: intrabar order unknowable from OHLC.
            # tie="stop" is conservative, tie="target" optimistic; report both.
            exit_price = e_stop if tie == "stop" else e_target
            break
        if hs:
            exit_price = e_stop; break
        if ht:
            exit_price = e_target; break
    if exit_price is None:  # day-end exit at last close, adverse half-spread
        last = day_bars[-1]["close"]
        exit_price = last - adv
    r_mult = ((exit_price - e_entry) if side == "buy" else (e_entry - exit_price)) / e_risk
    return side, e_entry, exit_price, r_mult, e_risk, ambiguous

def backtest_pair(pair, bars, iv, direction, stop_rule, target_r, session_hour,
                  or_bars, spread_mult, series_cache, rng=None, trade_log=False, tie="stop"):
    pip = fxdata.pip_size(pair)
    half_spread = SPREAD_PIPS[pair] * spread_mult * pip / 2.0
    days = fx_scan.split_days(bars)
    min_bars = 270 if iv == "5m" else 20
    day_list = [(d, days[d]) for d in sorted(days) if len(days[d]) >= min_bars]
    equity = START_EQUITY
    curve = []  # (date, equity)
    rs, pnls = [], []
    log = []
    n_days = 0
    n_amb = 0
    for d, day_bars in day_list:
        n_days += 1
        open_min = fxdata.session_open_utc_minutes(d) + (session_hour - 8) * 60
        ev = day_events(day_bars, open_min, or_bars)
        res = run_trade(day_bars, ev, direction, stop_rule, target_r, half_spread, rng, tie=tie) if ev else None
        if res:
            side, e_entry, e_exit, r_mult, e_risk, amb = res
            n_amb += amb
            risk_usd = equity * RISK_PCT / 100.0
            stop_pips = e_risk / pip
            pv_unit = pip * usd_per_quote_on(pair, d, series_cache)  # USD per pip per unit
            if pv_unit > 0 and stop_pips > 0:
                units = max(100, int(round(risk_usd / (stop_pips * pv_unit), -2)))
                # P&L in quote currency -> USD at that day's conversion rate
                pnl_quote = (e_exit - e_entry) * (1 if side == "buy" else -1) * units
                pnl = pnl_quote * usd_per_quote_on(pair, d, series_cache)
            else:
                pnl = 0.0
            equity += pnl
            rs.append(r_mult); pnls.append(pnl)
            if trade_log:
                log.append({"day": str(d), "side": side, "entry": round(e_entry, 6),
                            "exit": round(e_exit, 6), "r": round(r_mult, 3),
                            "pnl_usd": round(pnl, 2), "equity": round(equity, 2)})
        curve.append((str(d), equity))
    out = summarize(curve, rs, pnls, n_days, log)
    out["trades_with_ambiguous_bar"] = n_amb
    out["tie_break"] = tie
    return out

def summarize(curve, rs, pnls, n_days, log=None):
    n = len(rs)
    peak = START_EQUITY
    maxdd = 0.0
    for _, eq in curve:
        peak = max(peak, eq)
        maxdd = max(maxdd, (peak - eq) / peak)
    wins = [r for r in rs if r > 0]
    losses = [r for r in rs if r <= 0]
    pf = (sum(wins) / abs(sum(losses))) if losses and sum(losses) != 0 else None
    # daily returns for sharpe
    rets = []
    prev = START_EQUITY
    for _, eq in curve:
        if prev > 0:
            rets.append(eq / prev - 1.0)
        prev = eq
    sharpe = None
    if len(rets) > 2 and statistics.pstdev(rets) > 0:
        sharpe = statistics.fmean(rets) / statistics.pstdev(rets) * math.sqrt(252)
    streak = mx = 0
    for r in rs:
        streak = streak + 1 if r <= 0 else 0
        mx = max(mx, streak)
    t_stat = None
    if n > 2 and statistics.pstdev(rs) > 0:
        t_stat = statistics.fmean(rs) / (statistics.pstdev(rs) / math.sqrt(n))
    out = {
        "days": n_days, "trades": n,
        "win_rate": round(100.0 * len(wins) / n, 1) if n else None,
        "avg_r": round(statistics.fmean(rs), 4) if n else None,
        "expectancy_t": round(t_stat, 2) if t_stat is not None else None,
        "total_r": round(sum(rs), 2) if n else 0,
        "net_pnl_usd": round(sum(pnls), 2),
        "return_pct": round(100.0 * (curve[-1][1] / START_EQUITY - 1.0), 2) if curve else 0.0,
        "max_drawdown_pct": round(100.0 * maxdd, 2),
        "profit_factor": round(pf, 2) if pf else None,
        "daily_sharpe": round(sharpe, 2) if sharpe is not None else None,
        "max_losing_streak": mx,
        "final_equity": round(curve[-1][1], 2) if curve else START_EQUITY,
    }
    if log is not None:
        out["trade_log"] = log
    return out

def bootstrap_ci(rs, n_boot=10000, seed=7):
    if len(rs) < 5:
        return None
    rng = random.Random(seed)
    n = len(rs)
    means = []
    for _ in range(n_boot):
        s = 0.0
        for _ in range(n):
            s += rs[rng.randrange(n)]
        means.append(s / n)
    means.sort()
    return (round(means[int(0.025*n_boot)], 4), round(means[int(0.975*n_boot)], 4))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--timeframe", choices=["5m", "1h"], required=True)
    a = ap.parse_args()
    iv = a.timeframe
    bars_by_pair = {p: load_bars(p, iv) for p in PAIRS}
    series_cache = {p: usd_per_quote_series(p, bars_by_pair) for p in PAIRS if p[3:] != "USD"}
    for p in PAIRS:
        if p[3:] != "USD":
            series_cache[p] = series_cache[p]

    results = {"timeframe": iv, "start_equity": START_EQUITY, "risk_pct": RISK_PCT,
               "spread_pips": SPREAD_PIPS, "grid": [], "headline": None,
               "random_control": None, "portfolio": None,
               "run_utc": datetime.datetime.utcnow().isoformat()}
    or_bars = 12 if iv == "5m" else 1

    grid = []
    for pair in PAIRS:
        for direction in ("follow", "buy", "sell"):
            for stop_rule in ("or-mid", "or-far"):
                for target_r in (1.0, 1.5, 2.0):
                    for spread_mult, scen in ((0.0, "gross"), (1.0, "net")):
                        r = backtest_pair(pair, bars_by_pair[pair], iv, direction,
                                          stop_rule, target_r, 8, or_bars, spread_mult, series_cache)
                        grid.append({"pair": pair, "direction": direction,
                                     "stop": stop_rule, "target_r": target_r,
                                     "scenario": scen, **{k: v for k, v in r.items() if k != "trade_log"}})
    results["grid"] = grid

    # headline = shipped defaults: follow breakout, or-mid, 1R, 08:00 London, 1h range, net costs
    headline = {}
    headline_opt = {}
    for pair in PAIRS:
        r = backtest_pair(pair, bars_by_pair[pair], iv, "follow", "or-mid", 1.0, 8, or_bars, 1.0,
                          series_cache, trade_log=True)
        headline[pair] = r
        r_opt = backtest_pair(pair, bars_by_pair[pair], iv, "follow", "or-mid", 1.0, 8, or_bars, 1.0,
                              series_cache, tie="target")
        headline_opt[pair] = {k: v for k, v in r_opt.items() if k != "trade_log"}
    results["headline"] = headline
    results["headline_optimistic_tiebreak"] = headline_opt

    # random-direction control on headline geometry, 20 seeds
    control = {}
    for pair in PAIRS:
        exps = []
        for seed in range(20):
            rng = random.Random(1000 + seed)
            r = backtest_pair(pair, bars_by_pair[pair], iv, "random", "or-mid", 1.0, 8, or_bars, 1.0,
                              series_cache, rng=rng)
            if r["avg_r"] is not None:
                exps.append(r["avg_r"])
        if exps:
            control[pair] = {"seeds": len(exps), "mean_avg_r": round(statistics.fmean(exps), 4),
                             "min_avg_r": round(min(exps), 4), "max_avg_r": round(max(exps), 4)}
    results["random_control"] = control

    # sensitivity: session 07:00 vs 08:00, range 30m vs 60m (5m only), follow/or-mid/1R/net
    sens = []
    for pair in PAIRS:
        for sh in (7, 8):
            for ob in ([6, 12] if iv == "5m" else [1, 2]):
                r = backtest_pair(pair, bars_by_pair[pair], iv, "follow", "or-mid", 1.0, sh, ob, 1.0, series_cache)
                sens.append({"pair": pair, "session_hour": sh, "or_bars": ob,
                             **{k: v for k, v in r.items() if k != "trade_log"}})
    results["sensitivity"] = sens

    # stress costs: 2x spread, headline variant
    stress = {}
    for pair in PAIRS:
        r = backtest_pair(pair, bars_by_pair[pair], iv, "follow", "or-mid", 1.0, 8, or_bars, 2.0, series_cache)
        stress[pair] = {k: v for k, v in r.items() if k != "trade_log"}
    results["stress_2x_spread"] = stress

    # equal-weight portfolio of all 10 pairs (headline variant, net), $10k total
    port_curves = []
    for pair in PAIRS:
        r = backtest_pair(pair, bars_by_pair[pair], iv, "follow", "or-mid", 1.0, 8, or_bars, 1.0,
                          series_cache, trade_log=True)
        port_curves.append((pair, r["trade_log"]))
    # rebuild daily portfolio equity from trade logs (each pair contributes 1/10 of its $10k sim)
    daily = {}
    for pair, log in port_curves:
        for t in log:
            daily.setdefault(t["day"], 0.0)
            daily[t["day"]] += t["pnl_usd"] / 10.0
    eq = START_EQUITY
    curve = []
    for d in sorted(daily):
        eq += daily[d]
        curve.append((d, eq))
    peak = START_EQUITY; maxdd = 0.0
    for _, e in curve:
        peak = max(peak, e)
        maxdd = max(maxdd, (peak - e) / peak)
    results["portfolio"] = {"pairs": PAIRS, "days_with_trades": len(daily),
                            "final_equity": round(eq, 2), "return_pct": round(100*(eq/START_EQUITY-1), 2),
                            "max_drawdown_pct": round(100*maxdd, 2),
                            "total_trades": sum(len(l) for _, l in port_curves)}

    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "results", "backtest_%s.json" % iv), "w") as f:
        json.dump(results, f, indent=2)

    # console summary
    print("=== %s backtest: headline (follow/or-mid/1R/08:00 London/net costs) ===" % iv)
    print("%-7s %6s %6s %8s %8s %9s %7s %7s" % ("pair","trades","win%","avgR","ret%","maxDD%","PF","t"))
    for p in PAIRS:
        h = headline[p]
        print("%-7s %6d %6s %8s %8s %9s %7s %7s" % (p, h["trades"], h["win_rate"], h["avg_r"],
              h["return_pct"], h["max_drawdown_pct"], h["profit_factor"], h["expectancy_t"]))
    print("\nrandom-direction control (mean avg R over 20 seeds):")
    for p, c in control.items():
        print("  %-7s mean %+.4f  range [%+.4f, %+.4f]" % (p, c["mean_avg_r"], c["min_avg_r"], c["max_avg_r"]))
    print("\nportfolio (10 pairs, $10k split equally, net): return %.2f%%, maxDD %.2f%%, trades %d"
          % (results["portfolio"]["return_pct"], results["portfolio"]["max_drawdown_pct"], results["portfolio"]["total_trades"]))
    net_cells = [g for g in grid if g["scenario"] == "net" and g["trades"] >= 10]
    pos = sum(1 for g in net_cells if g["total_r"] > 0)
    print("\ngrid (net scenario, %d cells with >=10 trades): %d positive total R (%.0f%%)"
          % (len(net_cells), pos, 100.0*pos/max(1,len(net_cells))))
    sig = sum(1 for g in net_cells if g["expectancy_t"] is not None and g["expectancy_t"] > 2.0)
    print("cells with t>2: %d (with %d cells, ~%d would pass by chance alone at p<0.05)"
          % (sig, len(net_cells), int(len(net_cells)*0.05)))

if __name__ == "__main__":
    main()
