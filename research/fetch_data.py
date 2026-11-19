#!/usr/bin/env python3
"""Fetch and cache Yahoo bars for fxpulse validation. Personal-use, paced."""
import json, os, sys, time, urllib.request, urllib.error

UA = {"User-Agent": "fxpulse/0.1 python-urllib"}
DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
PAIRS = ["EURUSD","GBPUSD","USDJPY","USDCHF","USDCAD","AUDUSD","NZDUSD",
         "EURGBP","EURJPY","GBPJPY"]

def fetch(symbol, rng, interval, path):
    if os.path.exists(path):
        return "cached"
    err = None
    for attempt in range(6):
        for host in ("query2","query1"):
            url = "https://%s.finance.yahoo.com/v8/finance/chart/%s?range=%s&interval=%s" % (host, symbol, rng, interval)
            try:
                req = urllib.request.Request(url, headers=UA)
                raw = urllib.request.urlopen(req, timeout=30).read()
                data = json.loads(raw)
                result = (data.get("chart") or {}).get("result") or []
                if not result:
                    raise RuntimeError("no result")
                r = result[0]
                ts = r.get("timestamp") or []
                q = (r.get("indicators") or {}).get("quote",[{}])[0]
                bars = []
                for i,t in enumerate(ts):
                    try:
                        o,h,l,c = q["open"][i],q["high"][i],q["low"][i],q["close"][i]
                    except (KeyError,IndexError,TypeError):
                        continue
                    if None in (o,h,l,c):
                        continue
                    bars.append({"ts":int(t),"open":float(o),"high":float(h),"low":float(l),"close":float(c)})
                if not bars:
                    raise RuntimeError("zero usable bars")
                with open(path,"w") as f:
                    json.dump(bars,f)
                return "ok %d bars" % len(bars)
            except urllib.error.HTTPError as e:
                err = "HTTP %s" % e.code
                if e.code not in (429,500,502,503,504):
                    return "fail %s" % err
            except Exception as e:
                err = str(e)
        time.sleep(15 * (attempt+1))
    return "fail %s" % err

jobs = []
for p in PAIRS:
    jobs.append((p+"=X","60d","5m", os.path.join(DATA,"%s-5m.json"%p)))
    jobs.append((p+"=X","730d","1h", os.path.join(DATA,"%s-1h.json"%p)))
for sym,rng,iv,path in jobs:
    name = os.path.basename(path)
    print(name, fetch(sym,rng,iv,path), flush=True)
    time.sleep(3)
