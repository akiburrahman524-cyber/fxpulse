#!/usr/bin/env python3
"""Daily trend-following study, pre-registered small rule set.

Simulation only - no real orders, no broker, no money moved.

Why this study exists: the project's intraday opening-range-breakout rule
has no edge after costs (BACKTESTS.md). The owner asked to keep testing
honestly. The strongest published evidence for any simple FX rule is
medium-term TREND FOLLOWING on daily bars, where the spread is paid a few
times per year instead of every day. This script tests exactly that, with
the same honesty rules as the intraday study:

- a small PRE-REGISTERED rule set chosen before looking at results
  (time-series momentum, Donchian channel breakout, moving-average cross),
  plus stated neighbour parameters for the sensitivity table;
- explicit simulated capital ($1,000 per pair slice, $10,000 portfolio),
  volatility-based sizing (1% of slice equity per 1xATR(20) at entry);
- the same retail spread assumptions as BACKTESTS.md, charged as adverse
  fill cost on every entry, exit and reversal;
- GROSS and NET results side by side, losing cells included;
- a random-direction control on identical segment boundaries;
- signals use only data up to the signal close; the position earns the
  NEXT close-to-close return (no same-close lookahead);
- every variant in the grid is reported; the multiple-comparisons count
  is stated in the report.

NOT modeled (stated, not hidden): swap/rollover interest (material for
multi-week holds, can add to or subtract from results depending on the
pair's rate differential), slippage and gaps (daily closes are assumed
fillable at mid +/- half-spread), commissions. Daily Yahoo bars are mid
price, personal-use feed; raw bars are cached locally, never committed.
"""
import json, os, sys, math, random, datetime, statistics

PAIRS = ["EURUSD","GBPUSD","USDJPY","USDCHF","USDCAD","AUDUSD","NZDUSD",
         "EURGBP","EURJPY","GBPJPY"]
SPREAD_PIPS = {"EURUSD":0.6,"GBPUSD":0.9,"USDJPY":0.7,"USDCHF":1.0,"USDCAD":1.2,
               "AUDUSD":0.8,"NZDUSD":1.4,"EURGBP":1.1,"EURJPY":1.2,"GBPJPY":2.0}
DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
RESULTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
RISK_FRAC = 0.01          # 1% of slice equity risked per 1xATR(20) at segment entry
SLICE_USD = 1000.0        # per-pair slice of the $10,000 portfolio
N_CONTROL_SEEDS = 20

def pip_size(pair):
    return 0.01 if pair.endswith("JPY") else 0.0001

def utc_date(ts):
    return datetime.datetime.utcfromtimestamp(ts).date()

def load_bars(pair):
    with open(os.path.join(DATA, "%s-1d.json" % pair)) as f:
        bars = json.load(f)
    out, seen = [], set()
    for b in bars:  # dedupe by day, keep last
        d = utc_date(b["ts"])
        if d in seen:
            out[-1] = b
        else:
            seen.add(d); out.append(b)
    return out

def usd_per_quote_series(pair, bars_by_pair):
    quote = pair[3:]
    if quote == "USD":
        return None
    src = "USD" + quote if ("USD" + quote) in bars_by_pair else quote + "USD"
    inv = src.startswith("USD")
    out = {}
    for b in bars_by_pair[src]:
        out[utc_date(b["ts"])] = (1.0 / b["close"]) if inv else b["close"]
    return out

def usd_per_quote_on(pair, d, cache):
    if pair[3:] == "USD":
        return 1.0
    s = cache[pair]
    for k in range(8):
        dd = d - datetime.timedelta(days=k)
        if dd in s:
            return s[dd]
    prior = [dd for dd in s if dd <= d]
    return s[max(prior)] if prior else s[min(s)]

def atr20(bars, i):
    """Mean true range over the 20 bars ENDING at index i (inclusive)."""
    lo = max(1, i - 19)
    trs = []
    for j in range(lo, i + 1):
        h, l, pc = bars[j]["high"], bars[j]["low"], bars[j-1]["close"]
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    return sum(trs) / len(trs)

def sma(closes, i, n):
    if i + 1 < n:
        return None
    return sum(closes[i + 1 - n:i + 1]) / n

def signal_tsmom(closes, i, L):
    if i < L:
        return 0
    return 1 if closes[i] > closes[i - L] else -1

def signal_donchian(bars, i, n_in, n_out, state):
    if i < n_in:
        return 0
    hh = max(b["high"] for b in bars[i - n_in:i])
    ll = min(b["low"] for b in bars[i - n_in:i])
    c = bars[i]["close"]
    if state == 0:
        if c > hh: return 1
        if c < ll: return -1
        return 0
    if state == 1:
        exit_ll = min(b["low"] for b in bars[i - n_out:i])
        return 0 if c < exit_ll else 1
    exit_hh = max(b["high"] for b in bars[i - n_out:i])
    return 0 if c > exit_hh else -1

def signal_macross(closes, i, fast, slow):
    f, s = sma(closes, i, fast), sma(closes, i, slow)
    if f is None or s is None:
        return 0
    return 1 if f > s else -1

def simulate(pair, bars, rule, conv_cache, bars_by_pair, cost_mult=1.0,
             sign_override=None, exec_lag=0):
    """rule: (kind, params). Returns dict with equity curve, trades, stats.
    sign_override: optional list of signs (+1/-1) per segment for the
    random-direction control (same boundaries, randomized direction).
    exec_lag: days between the signal close and the position taking effect.
    0 = act AT the signal close (the headline convention; assumes the close
    print is achievable at mid +/- half-spread). 1 or 2 = act at a LATER
    close, breaking the signal-price-equals-fill-price identity - the
    realistic-lag sensitivity."""
    kind, params = rule
    closes = [b["close"] for b in bars]
    n = len(bars)
    # positions: pos[i] held from close of day i to close of day i+1
    pos = [0] * n
    if kind == "tsmom":
        L = params
        for i in range(n):
            pos[i] = signal_tsmom(closes, i, L)
    elif kind == "donchian":
        n_in, n_out = params
        st = 0
        for i in range(n):
            st = signal_donchian(bars, i, n_in, n_out, st)
            pos[i] = st
    elif kind == "macross":
        fast, slow = params
        for i in range(n):
            pos[i] = signal_macross(closes, i, fast, slow)
    if exec_lag:
        pos = ([0] * exec_lag + pos[:n - exec_lag])
    # conversion-availability gate: never size or settle a position with a
    # rate dated AFTER the trade day. When the conversion series starts
    # later than this pair (EURGBP: 2001-09 vs GBPUSD: 2003-12), the days
    # before its first rate are simply not traded. (Found 2026-11-21: the
    # walk-back fallback in usd_per_quote_on would otherwise have used the
    # FIRST available rate, up to ~2 years in the future, for early EURGBP
    # trades - contradicting the published never-future claim.)
    conv0 = conv_cache.get(pair)
    if conv0:
        min_conv = min(conv0)
        for i in range(n):
            if pos[i] and utc_date(bars[i]["ts"]) < min_conv:
                pos[i] = 0
    # segments of constant nonzero position
    seg_id = [ -1 ] * n
    segs = []
    cur = -1
    for i in range(n):
        if pos[i] != 0 and i > 0 and pos[i] == pos[i-1] and cur >= 0:
            seg_id[i] = cur
        elif pos[i] != 0:
            cur += 1; segs.append([i, i, pos[i]]); seg_id[i] = cur
    for k, s in enumerate(segs):
        s[1] = s[0]
    for i in range(n):
        if seg_id[i] >= 0:
            segs[seg_id[i]][1] = i
    if sign_override is not None:
        for k, s in enumerate(segs):
            sgn = sign_override[k]
            for i in range(s[0], s[1] + 1):
                pos[i] = sgn
    half_spread = SPREAD_PIPS[pair] * pip_size(pair) / 2.0 * cost_mult
    equity = SLICE_USD
    ruined = False
    curve = []           # (date, equity) marked daily
    trades = []          # per-segment R multiples
    year_pnl = {}
    units = 0.0
    entry_risk_usd = None
    seg_pnl = 0.0
    seg_start_equity = None
    for i in range(n - 1):
        d = utc_date(bars[i]["ts"])
        # position change at close of day i?
        if i == 0 or pos[i] != pos[i-1]:
            # close old segment
            if units != 0.0 and entry_risk_usd:
                trades.append(seg_pnl / entry_risk_usd)
            if pos[i] != 0:
                a = atr20(bars, i)
                # units so that a 1xATR move is 1% of equity IN USD: the
                # quote-currency ATR must be converted (a yen ATR is ~150x
                # more units per dollar than a dollar ATR)
                conv0 = usd_per_quote_on(pair, d, conv_cache)
                if a <= 0 or conv0 <= 0:
                    pos[i] = 0; units = 0.0
                else:
                    units = RISK_FRAC * equity / (a * conv0)
                    entry_risk_usd = RISK_FRAC * equity
                    seg_pnl = 0.0
                    seg_start_equity = equity
            else:
                units = 0.0; entry_risk_usd = None
            legs = abs(pos[i] - (pos[i-1] if i > 0 else 0))
            if legs and (units or True):
                u = units if units else prev_units
                cost = legs * u * half_spread * usd_per_quote_on(pair, d, conv_cache)
                equity -= cost
                if entry_risk_usd:
                    seg_pnl -= cost
        prev_units = units
        if units:
            conv = usd_per_quote_on(pair, utc_date(bars[i+1]["ts"]), conv_cache)
            pnl = pos[i] * units * (closes[i+1] - closes[i]) * conv
            equity += pnl
            seg_pnl += pnl
            y = utc_date(bars[i+1]["ts"]).year
            year_pnl[y] = year_pnl.get(y, 0.0) + pnl
        if equity <= 0:
            # ruin: a real account is stopped out by the broker long before
            # here; the slice is marked ruined and stops trading
            equity = 0.0
            ruined = True
            units = 0.0
            if entry_risk_usd:
                trades.append(seg_pnl / entry_risk_usd)
                entry_risk_usd = None
        curve.append((d, equity))
    if units != 0.0 and entry_risk_usd:
        trades.append(seg_pnl / entry_risk_usd)
    # stats
    eq0, eq1 = SLICE_USD, curve[-1][1]
    days = (curve[-1][0] - curve[0][0]).days or 1
    cagr = -100.0 if eq1 <= 0 else 100.0 * ((eq1 / eq0) ** (365.25 / days) - 1)
    peak, maxdd = eq0, 0.0
    for _, e in curve:
        peak = max(peak, e)
        maxdd = max(maxdd, (peak - e) / peak)
    wins = [r for r in trades if r > 0]
    avg_r = sum(trades) / len(trades) if trades else 0.0
    tstat = (avg_r / (statistics.pstdev(trades) / math.sqrt(len(trades)))
             if len(trades) > 1 and statistics.pstdev(trades) > 0 else 0.0)
    return {
        "pair": pair, "rule": kind, "params": params, "exec_lag": exec_lag,
        "start": str(curve[0][0]), "end": str(curve[-1][0]), "days": days,
        "trades": len(trades),
        "win_pct": round(100.0 * len(wins) / len(trades), 1) if trades else 0.0,
        "avg_r": round(avg_r, 4), "t_stat": round(tstat, 2),
        "return_pct": round(100.0 * (eq1 / eq0 - 1), 2),
        "cagr_pct": round(cagr, 2),
        "ruined": ruined,
        "max_drawdown_pct": round(100.0 * maxdd, 2),
        "trade_rs": [round(r, 4) for r in trades],
        "year_pnl": {str(k): round(v, 2) for k, v in sorted(year_pnl.items())},
        "curve": [(str(d), round(e, 2)) for d, e in curve],
        "segments": [[str(utc_date(bars[s[0]]["ts"])), str(utc_date(bars[s[1]]["ts"]))] for s in segs],
    }

def bootstrap_ci(rs, n_boot=10000, seed=7):
    if len(rs) < 5:
        return None
    rng = random.Random(seed)
    n = len(rs); means = []
    for _ in range(n_boot):
        s = sum(rs[rng.randrange(n)] for _ in range(n))
        means.append(s / n)
    means.sort()
    return (round(means[int(0.025*n_boot)], 4), round(means[int(0.975*n_boot)], 4))

RULES_HEADLINE = [("tsmom", 63), ("tsmom", 126), ("tsmom", 252),
                  ("donchian", (55, 20)), ("macross", (50, 200))]
RULES_NEIGHBOUR = [("tsmom", 42), ("tsmom", 84), ("tsmom", 168), ("tsmom", 336),
                   ("donchian", (40, 15)), ("donchian", (70, 25)),
                   ("macross", (25, 100)), ("macross", (100, 300))]

def rule_name(kind, params):
    if kind == "tsmom": return "tsmom-%dd" % params
    if kind == "donchian": return "donchian-%d/%d" % params
    return "macross-%d/%d" % params

def portfolio_from_curves(curves_by_pair, trade_rs_all):
    """curves_by_pair: pair -> {date_str: equity}. Equal-weight slices summed
    across pairs once every pair has a value (last value carried forward)."""
    curves = {p: dict(c) for p, c in curves_by_pair.items()}
    all_days = sorted({d for c in curves.values() for d in c})
    port, last = [], {}
    for d in all_days:
        for p in curves:
            if d in curves[p]:
                last[p] = curves[p][d]
        if len(last) == len(curves):
            port.append((d, sum(last.values())))
    if not port:
        return None
    eq0 = SLICE_USD * len(curves)
    peak, maxdd = eq0, 0.0
    for _, e in port:
        peak = max(peak, e); maxdd = max(maxdd, (peak - e) / peak)
    days = (datetime.date.fromisoformat(port[-1][0]) -
            datetime.date.fromisoformat(port[0][0])).days or 1
    return {
        "start": port[0][0], "end": port[-1][0], "curve": port,
        "return_pct": round(100.0 * (port[-1][1] / eq0 - 1), 2),
        "cagr_pct": round(100.0 * ((port[-1][1] / eq0) ** (365.25 / days) - 1), 2)
                    if port[-1][1] > 0 else -100.0,
        "max_drawdown_pct": round(100.0 * maxdd, 2),
        "trades": len(trade_rs_all),
        "avg_r": round(sum(trade_rs_all)/len(trade_rs_all), 4) if trade_rs_all else 0.0,
        "avg_r_ci95": bootstrap_ci(trade_rs_all)}

ERAS = [("2003-12-01", "2010-12-31"), ("2011-01-01", "2015-12-31"),
        ("2016-01-01", "2020-12-31"), ("2021-01-01", "2026-11-20")]

def era_returns(port_curve):
    """Compound return of the portfolio within each era window."""
    out = {}
    for a, b in ERAS:
        before = [p for p in port_curve if p[0] < a]
        inside = [p for p in port_curve if a <= p[0] <= b]
        if not inside:
            continue
        base = before[-1][1] if before else port_curve[0][1]
        out["%s..%s" % (a[:4], b[:4])] = round(100.0 * (inside[-1][1] / base - 1), 2)
    return out

def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    assert mode in ("base", "extra", "all"), "mode: base | extra | all"
    bars_by_pair = {p: load_bars(p) for p in PAIRS}
    conv_cache = {p: usd_per_quote_series(p, bars_by_pair) for p in PAIRS}
    out = {"generated_utc": datetime.datetime.utcnow().isoformat() + "Z",
           "risk_frac": RISK_FRAC, "slice_usd": SLICE_USD,
           "spread_pips": SPREAD_PIPS, "pairs": {}, "portfolio": {},
           "controls": {}, "gross": {}, "stress2x": {}, "neighbour": {},
           "lags": {}, "eras": {}}
    all_rules = RULES_HEADLINE + RULES_NEIGHBOUR
    if mode in ("extra",):
        all_rules = []  # extra mode: lag/era sensitivity only
    for kind, params in all_rules:
        name = rule_name(kind, params)
        for p in PAIRS:
            r = simulate(p, bars_by_pair[p], (kind, params), conv_cache, bars_by_pair)
            r["avg_r_ci95"] = bootstrap_ci(r["trade_rs"])
            out["pairs"].setdefault(name, {})[p] = {k: v for k, v in r.items()
                if k not in ("curve", "trade_rs", "segments")}
            out["pairs"][name][p]["avg_r_bootstrap_ci95"] = r["avg_r_ci95"]
            # store curve/trades internally for portfolio & controls
            out.setdefault("_full", {}).setdefault(name, {})[p] = r
            # gross (no cost) rerun for headline rules only
            if (kind, params) in RULES_HEADLINE:
                g = simulate(p, bars_by_pair[p], (kind, params), conv_cache,
                             bars_by_pair, cost_mult=0.0)
                out["gross"].setdefault(name, {})[p] = {
                    "return_pct": g["return_pct"], "avg_r": g["avg_r"]}
                s2 = simulate(p, bars_by_pair[p], (kind, params), conv_cache,
                              bars_by_pair, cost_mult=2.0)
                out["stress2x"].setdefault(name, {})[p] = {
                    "return_pct": s2["return_pct"], "avg_r": s2["avg_r"]}
                # random-direction control on identical segment boundaries
                nseg = len(r["segments"])
                means = []
                for seed in range(N_CONTROL_SEEDS):
                    rng = random.Random(1000 + seed)
                    signs = [rng.choice((1, -1)) for _ in range(nseg)]
                    c = simulate(p, bars_by_pair[p], (kind, params), conv_cache,
                                 bars_by_pair, sign_override=signs)
                    if c["trades"]:
                        means.append(c["avg_r"])
                out["controls"].setdefault(name, {})[p] = {
                    "n_seeds": len(means),
                    "mean_avg_r": round(sum(means)/len(means), 4) if means else None,
                    "min_avg_r": round(min(means), 4) if means else None,
                    "max_avg_r": round(max(means), 4) if means else None}
    # portfolio: equal-weight slices summed across pairs, headline rules
    for kind, params in (RULES_HEADLINE if mode in ("base", "all") else []):
        name = rule_name(kind, params)
        curves = {p: out["_full"][name][p]["curve"] for p in PAIRS}
        all_rs = [r for p in PAIRS for r in out["_full"][name][p]["trade_rs"]]
        pf = portfolio_from_curves(curves, all_rs)
        if pf:
            out["eras"][name] = era_returns(pf.pop("curve"))
            out["portfolio"][name] = pf
    # execution-lag sensitivity: headline rules re-run acting 1 and 2 closes
    # after the signal close (net costs; same sizing and conventions)
    for lag in (() if mode == "base" else (1, 2)):
        for kind, params in RULES_HEADLINE:
            name = rule_name(kind, params)
            curves, all_rs = {}, []
            for p in PAIRS:
                r = simulate(p, bars_by_pair[p], (kind, params), conv_cache,
                             bars_by_pair, exec_lag=lag)
                out["lags"].setdefault(str(lag), {}).setdefault(name, {})[p] = {
                    "trades": r["trades"], "avg_r": r["avg_r"],
                    "return_pct": r["return_pct"], "cagr_pct": r["cagr_pct"],
                    "max_drawdown_pct": r["max_drawdown_pct"], "ruined": r["ruined"]}
                curves[p] = r["curve"]
                all_rs += r["trade_rs"]
            pf = portfolio_from_curves(curves, all_rs)
            if pf:
                pf.pop("curve")
                out["lags"][str(lag)][name]["_portfolio"] = pf
    out.pop("_full", None)
    os.makedirs(RESULTS, exist_ok=True)
    if mode in ("base", "all"):
        with open(os.path.join(RESULTS, "daily_trend.json"), "w") as f:
            json.dump(out, f, indent=1)
        print("wrote results/daily_trend.json")
        for name in out["portfolio"]:
            pf = out["portfolio"][name]
            print("%-16s ret %8.2f%%  cagr %6.2f%%  maxdd %6.2f%%  trades %5d  avgR %7.4f CI %s"
                  % (name, pf["return_pct"], pf["cagr_pct"], pf["max_drawdown_pct"],
                     pf["trades"], pf["avg_r"], pf["avg_r_ci95"]))
    if mode in ("extra", "all"):
        extra = {"lags": out["lags"]}
        with open(os.path.join(RESULTS, "daily_trend_extra.json"), "w") as f:
            json.dump(extra, f, indent=1)
        print("wrote results/daily_trend_extra.json")
        for lag in sorted(out["lags"]):
            for name in out["lags"][lag]:
                pf = out["lags"][lag][name].get("_portfolio")
                if pf:
                    print("lag%s %-16s ret %8.2f%%  cagr %6.2f%%  avgR %7.4f CI %s"
                          % (lag, name, pf["return_pct"], pf["cagr_pct"],
                             pf["avg_r"], pf["avg_r_ci95"]))

if __name__ == "__main__":
    main()
