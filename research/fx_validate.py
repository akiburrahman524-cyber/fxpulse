#!/usr/bin/env python3
"""fxpulse data-correctness validation. See report string at bottom."""
import datetime, json, math, os, statistics, sys, time, urllib.request

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
PAIRS = ["EURUSD","GBPUSD","USDJPY","USDCHF","USDCAD","AUDUSD","NZDUSD",
         "EURGBP","EURJPY","GBPJPY"]
UA = {"User-Agent": "fxpulse/0.1 python-urllib"}

def load(pair, iv):
    with open(os.path.join(DATA, "%s-%s.json" % (pair, iv))) as f:
        return json.load(f)

def utc(ts):
    return datetime.datetime.utcfromtimestamp(ts)

def internal_checks(pair, iv, bars):
    r = {"pair": pair, "interval": iv, "bars": len(bars),
         "first": str(utc(bars[0]["ts"])), "last": str(utc(bars[-1]["ts"]))}
    bad_ohlc = neg = dup = nonmono = 0
    interval_s = 300 if iv == "5m" else 3600
    prev = None
    ranges = []
    weekend_bars = 0
    for b in bars:
        o,h,l,c = b["open"],b["high"],b["low"],b["close"]
        tol = 1e-9 * max(1.0, o)
        if h < max(o,c) - tol or l > min(o,c) + tol or h < l - tol:
            bad_ohlc += 1
        if min(o,h,l,c) <= 0:
            neg += 1
        if prev is not None:
            if b["ts"] == prev:
                dup += 1
            if b["ts"] < prev:
                nonmono += 1
        d = utc(b["ts"])
        if d.weekday() == 5:
            weekend_bars += 1
        if prev and b["ts"] - prev == interval_s and c:
            ranges.append((h - l) / c)
        prev = b["ts"]
    r["bad_ohlc"] = bad_ohlc
    r["nonpositive"] = neg
    r["duplicate_ts"] = dup
    r["nonmonotonic_ts"] = nonmono
    r["saturday_bars"] = weekend_bars
    bucket = {"weekly_or_weekend": 0, "one_bar_missing": 0, "intraday_gap_lt24h": 0, "long_gap_gt24h": 0}
    unexpected = []
    for i in range(1, len(bars)):
        dt = bars[i]["ts"] - bars[i-1]["ts"]
        if dt <= interval_s:
            continue
        a, b2 = utc(bars[i-1]["ts"]), utc(bars[i]["ts"])
        weekendish = (a.weekday() == 4 and b2.weekday() >= 5) or (a.weekday() == 6 and b2.weekday() == 0)
        if dt <= 2*interval_s:
            bucket["one_bar_missing"] += 1
        elif weekendish:
            bucket["weekly_or_weekend"] += 1
        elif dt > 86400:
            bucket["long_gap_gt24h"] += 1
            if len(unexpected) < 6:
                unexpected.append("%s -> %s (%.1fh)" % (a, b2, dt/3600.0))
        else:
            bucket["intraday_gap_lt24h"] += 1
            if len(unexpected) < 6:
                unexpected.append("%s -> %s (%.1fh)" % (a, b2, dt/3600.0))
    r["gaps"] = bucket
    r["unexpected_gap_examples"] = unexpected
    if ranges:
        med = statistics.median(ranges)
        outliers = [(i, x) for i, x in enumerate(ranges) if med > 0 and x > 25*med]
        r["median_bar_range_pct"] = round(100*med, 4)
        r["range_outliers_gt25x"] = len(outliers)
        r["outlier_examples"] = ["%s range %.2f%%" % (utc(bars[i]["ts"]) if i < len(bars) else "?", 100*x) for i, x in outliers[:5]]
    return r

def frankfurter_history(start, end):
    path = os.path.join(DATA, "ecb-%s-%s.json" % (start, end))
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    url = "https://api.frankfurter.dev/v1/%s..%s?base=EUR&symbols=USD,GBP,JPY,CHF,CAD,AUD,NZD" % (start, end)
    req = urllib.request.Request(url, headers=UA)
    data = json.loads(urllib.request.urlopen(req, timeout=60).read())
    with open(path, "w") as f:
        json.dump(data, f)
    return data

def ecb_pair_rate(rates, pair):
    base, quote = pair[:3], pair[3:]
    per_eur = dict(rates); per_eur["EUR"] = 1.0
    if base not in per_eur or quote not in per_eur:
        return None
    return per_eur[quote] / per_eur[base]

def europe_summer(day):
    import datetime as _dt
    def last_sun(y, m):
        d = _dt.date(y, m, 28)
        while (d + _dt.timedelta(days=1)).month == m:
            d += _dt.timedelta(days=1)
        while d.weekday() != 6:
            d -= _dt.timedelta(days=1)
        return d
    return last_sun(day.year, 3) < day < last_sun(day.year, 10)

def cross_source_checks(pair, bars_1h, ecb):
    by_day = {}
    for b in bars_1h:
        d = utc(b["ts"]).date()
        by_day.setdefault(d, []).append(b)
    devs, worst = [], []
    for day, day_bars in sorted(by_day.items()):
        ds = str(day)
        if ds not in ecb.get("rates", {}):
            continue
        ref = ecb_pair_rate(ecb["rates"][ds], pair)
        if ref is None:
            continue
        # ECB euro reference rate is fixed at 16:00 CET/CEST = 15:00 UTC
        # (winter) or 14:00 UTC (summer). Use the OPEN of the hourly bar that
        # starts at the fixing instant (drift ~ minutes, not hours).
        fix_hour = 14 if europe_summer(day) else 15
        tgt = None
        for b in day_bars:
            h = utc(b["ts"])
            if h.hour == fix_hour and h.minute == 0:
                tgt = b
        if tgt is None:
            continue
        y = tgt["open"]
        dev = (y - ref) / ref
        devs.append(dev)
        worst.append((abs(dev), ds, y, ref))
    if not devs:
        return {"pair": pair, "compared_days": 0}
    worst.sort(reverse=True)
    return {
        "pair": pair, "compared_days": len(devs),
        "median_abs_dev_pct": round(100*statistics.median(abs(d) for d in devs), 4),
        "mean_abs_dev_pct": round(100*statistics.fmean(abs(d) for d in devs), 4),
        "mean_signed_dev_pct": round(100*statistics.fmean(devs), 4),
        "max_abs_dev_pct": round(100*worst[0][0], 4),
        "days_over_0p5pct": sum(1 for d in devs if abs(d) > 0.005),
        "worst5": [{"day": w[1], "yahoo": round(w[2],6), "ecb": round(w[3],6),
                    "dev_pct": round(100*w[0],3)} for w in worst[:5]],
    }

def main():
    print("=== fxpulse data correctness report ===")
    print("run at %s UTC" % datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M"))
    internal = []
    for p in PAIRS:
        for iv in ("5m", "1h"):
            internal.append(internal_checks(p, iv, load(p, iv)))
    start = min(r["first"][:10] for r in internal)
    end = max(r["last"][:10] for r in internal)
    ecb = frankfurter_history(start, end)
    cross = [cross_source_checks(p, load(p, "1h"), ecb) for p in PAIRS]
    out = {"run_utc": datetime.datetime.utcnow().isoformat(), "internal": internal, "ecb_cross": cross, "ecb_method": "Yahoo hourly bar OPEN at ECB fixing instant (16:00 CET/CEST, DST-aware) vs Frankfurter/ECB daily reference rate"}
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "results", "validate_results.json"), "w") as f:
        json.dump(out, f, indent=2)
    for r in internal:
        print("\n%s %s: %d bars  %s .. %s" % (r["pair"], r["interval"], r["bars"], r["first"], r["last"]))
        print("  OHLC violations: %d  non-positive: %d  dup ts: %d  non-monotonic: %d  Saturday bars: %d"
              % (r["bad_ohlc"], r["nonpositive"], r["duplicate_ts"], r["nonmonotonic_ts"], r["saturday_bars"]))
        print("  gaps: %s" % r["gaps"])
        if r["unexpected_gap_examples"]:
            print("  gap examples: %s" % "; ".join(r["unexpected_gap_examples"]))
        print("  median bar range %.4f%%  outliers>25x: %d %s"
              % (r.get("median_bar_range_pct", -1), r.get("range_outliers_gt25x", -1),
                 r.get("outlier_examples", [])))
    print("\n=== Yahoo hourly vs ECB/Frankfurter daily reference (16:00 UTC bar) ===")
    for c in cross:
        print("%s: %d days, median |dev| %.4f%%, mean |dev| %.4f%%, signed mean %+.4f%%, max %.3f%%, days>0.5%%: %d"
              % (c["pair"], c["compared_days"], c.get("median_abs_dev_pct",-1),
                 c.get("mean_abs_dev_pct",-1), c.get("mean_signed_dev_pct",-1),
                 c.get("max_abs_dev_pct",-1), c.get("days_over_0p5pct",-1)))
        for w in c.get("worst5", [])[:3]:
            print("    worst: %s yahoo %.5f ecb %.5f dev %.3f%%" % (w["day"], w["yahoo"], w["ecb"], w["dev_pct"]))

if __name__ == "__main__":
    main()
