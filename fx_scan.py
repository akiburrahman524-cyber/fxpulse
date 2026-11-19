#!/usr/bin/env python3
"""fx_scan: session opening-range scanner for forex pairs.

For each pair, fetches recent 5-minute bars (Yahoo chart endpoint, unofficial,
personal use), takes the latest UTC day, builds the opening range from the
first bars after the session open (default 07:00 UTC, the London open hour),
and reports where the price sits against that range.

    python3 fx_scan.py                      # all configured pairs
    python3 fx_scan.py --pairs EURUSD USDJPY GBPJPY
    python3 fx_scan.py --session-open 7 --or-bars 12   # 07:00 UTC, first hour
    python3 fx_scan.py --json

This is descriptive analysis of public data, not a recommendation to trade.
"""

import argparse
import datetime
import json
import sys

import fxdata


def utc_day(ts):
    return datetime.datetime.utcfromtimestamp(ts).date()


def utc_minutes(ts):
    d = datetime.datetime.utcfromtimestamp(ts)
    return d.hour * 60 + d.minute


def split_days(bars):
    days = {}
    for b in bars:
        days.setdefault(utc_day(b["ts"]), []).append(b)
    for v in days.values():
        v.sort(key=lambda b: b["ts"])
    return days


def opening_range(day_bars, session_open_min, or_bars):
    """Opening range = high/low of the first `or_bars` bars at/after the
    session open minute. Returns (high, low, n_bars_used) or None."""
    window = [b for b in day_bars if utc_minutes(b["ts"]) >= session_open_min]
    window = window[:or_bars]
    if not window:
        return None
    return (max(b["high"] for b in window), min(b["low"] for b in window), len(window))


def scan_pair(pair, session_open_min, or_bars, per_day_session=False):
    symbol = fxdata.PAIRS[pair]
    bars = fxdata.fetch_yahoo_bars(symbol, rng="5d", interval="5m")
    days = split_days(bars)
    latest = max(days)
    day = days[latest]
    open_min = session_open_min
    if per_day_session:
        open_min = fxdata.session_open_utc_minutes(latest) + (session_open_min - 8 * 60)
    orng = opening_range(day, open_min, or_bars)
    last = day[-1]
    age = fxdata.bars_age_seconds(bars)
    out = {
        "pair": pair, "day": str(latest), "bars_today": len(day),
        "last": last["close"],
        "last_bar_utc": datetime.datetime.utcfromtimestamp(last["ts"]).strftime("%H:%M"),
        "data_age_min": round(age / 60.0, 1) if age is not None else None,
        "session_open_utc": "%02d:%02d" % (open_min // 60, open_min % 60),
    }
    if orng:
        hi, lo, n = orng
        out["or_high"], out["or_low"], out["or_bars"] = hi, lo, n
        out["or_width_pips"] = round(fxdata.to_pips(pair, hi - lo), 1)
        if last["close"] > hi:
            out["position"] = "above range"
        elif last["close"] < lo:
            out["position"] = "below range"
        else:
            out["position"] = "inside range"
        # first close beyond the range after it formed = breakout marker
        out["breakout"] = None
        formed_after = open_min + or_bars * 5
        for b in day:
            if utc_minutes(b["ts"]) < formed_after:
                continue
            if b["close"] > hi:
                out["breakout"] = {"side": "up",
                                   "at_utc": datetime.datetime.utcfromtimestamp(b["ts"]).strftime("%H:%M"),
                                   "close": b["close"]}
                break
            if b["close"] < lo:
                out["breakout"] = {"side": "down",
                                   "at_utc": datetime.datetime.utcfromtimestamp(b["ts"]).strftime("%H:%M"),
                                   "close": b["close"]}
                break
    else:
        out["position"] = "no session window yet"
    return out


def main(argv=None):
    p = argparse.ArgumentParser(description="Session opening-range scanner for forex pairs.")
    p.add_argument("--pairs", nargs="+", default=None,
                   help="pairs to scan (default: the 7 USD majors)")
    p.add_argument("--session-open", type=int, default=8,
                   help="session open hour in Europe/London local time (default 8, the London morning open; converted to UTC per date with DST)")
    p.add_argument("--session-open-utc", type=int, default=None,
                   help="override: fixed session open hour in UTC (no DST handling)")
    p.add_argument("--or-bars", type=int, default=12,
                   help="5-min bars in the opening range (default 12 = first hour)")
    p.add_argument("--json", action="store_true")
    a = p.parse_args(argv)

    pairs = [x.upper() for x in (a.pairs or
             ["EURUSD", "GBPUSD", "USDJPY", "USDCHF", "USDCAD", "AUDUSD", "NZDUSD"])]
    unknown = [x for x in pairs if x not in fxdata.PAIRS]
    if unknown:
        sys.exit("unknown pairs: %s (known: %s)" % (", ".join(unknown), ", ".join(sorted(fxdata.PAIRS))))

    per_day = a.session_open_utc is None
    open_min = (a.session_open_utc if a.session_open_utc is not None else a.session_open) * 60
    fxdata.require_intraday()
    results, errors = [], []
    for pair in pairs:
        try:
            results.append(scan_pair(pair, open_min, a.or_bars, per_day_session=per_day))
        except Exception as e:  # noqa: BLE001
            errors.append((pair, str(e)))

    if a.json:
        print(json.dumps({"results": results, "errors": errors}, indent=2))
        return 0

    if per_day:
        print("Session open %02d:00 Europe/London local (UTC conversion per date incl. DST), opening range = first %d x 5-min bars."
              % (a.session_open, a.or_bars))
    else:
        print("Session open %02d:00 UTC (fixed override), opening range = first %d x 5-min bars."
              % (a.session_open_utc, a.or_bars))
    print("Data: Yahoo chart endpoint, unofficial, personal use, can lag. Each row shows the newest bar's age.")
    print("%-7s %-5s %-6s %10s %10s %8s %6s  %-13s %s" % ("PAIR", "DAY", "OPEN", "OR-HIGH", "OR-LOW", "LAST", "AGE-M", "POSITION", "BREAKOUT"))
    for r in results:
        bo = r.get("breakout")
        bo_txt = "%s @%s (%s)" % (bo["side"], bo["at_utc"], bo["close"]) if bo else "-"
        print("%-7s %-5s %-6s %10s %10s %8s %6s  %-13s %s" % (
            r["pair"], r["day"][5:], r["session_open_utc"],
            ("%.5f" % r["or_high"]) if "or_high" in r else "-",
            ("%.5f" % r["or_low"]) if "or_low" in r else "-",
            "%.5f" % r["last"], str(r["data_age_min"]), r["position"], bo_txt))
    for pair, err in errors:
        print("!! %s: %s" % (pair, err), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
