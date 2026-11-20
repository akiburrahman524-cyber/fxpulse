#!/usr/bin/env python3
"""Fetch and cache Yahoo DAILY bars for the fxpulse daily-trend study.
Personal-use, paced, same discipline as fetch_data.py. Raw bars are NOT
committed to the repository (Yahoo terms, personal use)."""
import json, os, sys, time, urllib.request, urllib.error
PAIRS = ["EURUSD","GBPUSD","USDJPY","USDCHF","USDCAD","AUDUSD","NZDUSD",
         "EURGBP","EURJPY","GBPJPY"]
UA = {"User-Agent": "fxpulse/0.1 python-urllib"}
DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
os.makedirs(DATA, exist_ok=True)

def fetch_daily(symbol, path):
    if os.path.exists(path):
        return "cached"
    now = int(time.time())
    err = None
    for attempt in range(6):
        for host in ("query2", "query1"):
            url = ("https://%s.finance.yahoo.com/v8/finance/chart/%s"
                   "?period1=1000000000&period2=%d&interval=1d&events=history"
                   % (host, symbol, now))
            try:
                req = urllib.request.Request(url, headers=UA)
                data = json.loads(urllib.request.urlopen(req, timeout=30).read())
                result = (data.get("chart") or {}).get("result") or []
                if not result:
                    raise RuntimeError("no result")
                r = result[0]
                ts = r.get("timestamp") or []
                q = (r.get("indicators") or {}).get("quote", [{}])[0]
                bars = []
                for i, t in enumerate(ts):
                    try:
                        o, h, l, c = q["open"][i], q["high"][i], q["low"][i], q["close"][i]
                    except (KeyError, IndexError, TypeError):
                        continue
                    if None in (o, h, l, c):
                        continue
                    bars.append({"ts": int(t), "open": float(o), "high": float(h),
                                 "low": float(l), "close": float(c)})
                if not bars:
                    raise RuntimeError("zero usable bars")
                with open(path, "w") as f:
                    json.dump(bars, f)
                return "ok %d bars" % len(bars)
            except urllib.error.HTTPError as e:
                err = "HTTP %s" % e.code
                if e.code not in (429, 500, 502, 503, 504):
                    return "fail %s" % err
            except Exception as e:
                err = str(e)
        time.sleep(15 * (attempt + 1))
    return "fail %s" % err

for p in PAIRS:
    path = os.path.join(DATA, "%s-1d.json" % p)
    print(p, fetch_daily(p + "=X", path), flush=True)
    time.sleep(3)
