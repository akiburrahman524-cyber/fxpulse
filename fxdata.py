#!/usr/bin/env python3
"""Shared data layer for fxpulse. Standard library only.

Data sources and what they actually are:

  Frankfurter (https://frankfurter.dev/) - free, no key. Official reference
  rates from central banks (ECB and others), published once or a few times a
  day. NOT live market quotes. Daily history back decades.

  Yahoo Finance chart endpoint (query2.finance.yahoo.com) - unofficial, free,
  no key. Intraday bars for forex pairs as e.g. EURUSD=X. Personal use under
  Yahoo's terms; can lag, rate-limit or change without notice. Every user of
  this project calls it from their own machine for their own analysis.

  Twelve Data (https://twelvedata.com) - DISABLED by default. Their free tier
  is internal-use only under their terms (https://twelvedata.com/terms). If
  you set your own key in config.json you are confirming your use stays
  within what your Twelve Data plan allows. This project never sends a key
  anywhere except Twelve Data's own API.

Nothing here places trades. Nothing here is financial advice.
"""

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

UA = "fxpulse/0.1 python-urllib"

# pair -> yahoo symbol. Pip size: 0.01 for JPY pairs, else 0.0001.
PAIRS = {
    "EURUSD": "EURUSD=X", "GBPUSD": "GBPUSD=X", "USDJPY": "USDJPY=X",
    "USDCHF": "USDCHF=X", "USDCAD": "USDCAD=X", "AUDUSD": "AUDUSD=X",
    "NZDUSD": "NZDUSD=X", "EURGBP": "EURGBP=X", "EURJPY": "EURJPY=X",
    "GBPJPY": "GBPJPY=X", "AUDJPY": "AUDJPY=X", "EURAUD": "EURAUD=X",
    "EURCHF": "EURCHF=X", "EURCAD": "EURCAD=X", "GBPCAD": "GBPCAD=X",
    "GBPAUD": "GBPAUD=X", "AUDCAD": "AUDCAD=X", "AUDNZD": "AUDNZD=X",
    "CADJPY": "CADJPY=X", "NZDJPY": "NZDJPY=X", "CHFJPY": "CHFJPY=X",
}

YAHOO_CHART = "https://%s.finance.yahoo.com/v8/finance/chart/%s?range=%s&interval=%s"
FRANKFURTER = "https://api.frankfurter.dev/v1"
GDELT_DOC = "https://api.gdeltproject.org/api/v2/doc/doc"

CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".cache")


def _last_sunday(year, month):
    import datetime
    d = datetime.date(year, month, 28)
    while True:
        nxt = d + datetime.timedelta(days=1)
        if nxt.month != month:
            break
        d = nxt
    while d.weekday() != 6:
        d -= datetime.timedelta(days=1)
    return d


def london_utc_offset_hours(day):
    """Europe/London UTC offset in hours for a UTC date: +1 during BST
    (last Sunday of March 01:00 UTC to last Sunday of October 01:00 UTC),
    else 0."""
    import datetime
    start = _last_sunday(day.year, 3)
    end = _last_sunday(day.year, 10)
    if day > start and day < end:
        return 1
    if day == start or day == end:
        # switch happens at 01:00 UTC; for session-open purposes the local
        # morning is already on the new offset on the switch day
        return 1 if day == start else 0
    return 0


def session_open_utc_minutes(day, local_hour=8, local_minute=0):
    """UTC minute-of-day of the session open on a UTC date, for a session
    defined in Europe/London local time (default 08:00 London)."""
    local = local_hour * 60 + local_minute
    return (local - london_utc_offset_hours(day) * 60) % (24 * 60)


def bars_age_seconds(bars, now_ts=None):
    """Age of the newest bar's close vs now (epoch). Negative = clock skew."""
    import time
    if not bars:
        return None
    now = now_ts if now_ts is not None else time.time()
    return now - bars[-1]["ts"]


def pip_size(pair):
    return 0.01 if "JPY" in pair else 0.0001


def to_pips(pair, distance):
    return distance / pip_size(pair)


def from_pips(pair, pips):
    return pips * pip_size(pair)


def load_config(path=None):
    path = path or os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {}


def _get(url, timeout=25):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    return urllib.request.urlopen(req, timeout=timeout).read()


def _cache_path(kind, key):
    os.makedirs(CACHE_DIR, exist_ok=True)
    safe = "".join(c if c.isalnum() else "_" for c in key)
    return os.path.join(CACHE_DIR, "%s-%s.json" % (kind, safe))


def fetch_yahoo_bars(symbol, rng="60d", interval="5m", max_age=300):
    """Return list of bars: dict(ts, open, high, low, close), UTC epoch ts.

    Uses a short-lived cache so repeated commands do not hammer the endpoint.
    Falls back from query2 to query1 on 429/5xx. Raises RuntimeError with a
    plain message when no bars come back.
    """
    key = "%s-%s-%s" % (symbol, rng, interval)
    path = _cache_path("yh", key)
    if os.path.exists(path) and time.time() - os.path.getmtime(path) < max_age:
        with open(path) as f:
            return json.load(f)
    err = None
    for host in ("query2", "query1"):
        url = YAHOO_CHART % (host, urllib.parse.quote(symbol), rng, interval)
        try:
            raw = _get(url)
            data = json.loads(raw)
            result = (data.get("chart") or {}).get("result") or []
            if not result:
                raise RuntimeError("Yahoo returned no chart result for %s" % symbol)
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
                raise RuntimeError("Yahoo returned zero usable bars for %s" % symbol)
            with open(path, "w") as f:
                json.dump(bars, f)
            return bars
        except urllib.error.HTTPError as e:
            err = e
            if e.code not in (429, 500, 502, 503, 504):
                break
        except Exception as e:  # noqa: BLE001 - reported plainly below
            err = e
    raise RuntimeError("could not fetch %s from Yahoo chart endpoint: %s" % (symbol, err))


def frankfurter_latest(base="USD", quotes=None):
    url = "%s/latest?base=%s" % (FRANKFURTER, base)
    if quotes:
        url += "&symbols=" + ",".join(quotes)
    return json.loads(_get(url))


def frankfurter_series(start, end=None, base="USD", quotes=None):
    rng = "%s..%s" % (start, end or "")
    url = "%s/%s?base=%s" % (FRANKFURTER, rng, base)
    if quotes:
        url += "&symbols=" + ",".join(quotes)
    return json.loads(_get(url))


def usd_per_unit(currency, config=None):
    """Approximate USD value of 1 unit of `currency` using Frankfurter
    reference rates (reference rates, not live quotes). USD itself -> 1.0."""
    if currency == "USD":
        return 1.0
    data = frankfurter_latest("USD", [currency])
    rate = data["rates"].get(currency)
    if not rate:
        raise RuntimeError("Frankfurter has no USD->%s reference rate" % currency)
    return 1.0 / float(rate)


def pip_value_usd(pair, price=None, config=None):
    """USD value of one pip for one standard lot (100,000 units of base).

    A pip is worth 10 units of the quote currency per standard lot.
    Convert quote currency to USD with Frankfurter reference rates.
    `price` (current pair price) is used for USD-base pairs when given;
    otherwise reference rates are used.
    """
    base, quote = pair[:3], pair[3:]
    pip_quote = 10.0  # quote-currency units per pip per standard lot
    if quote == "USD":
        return pip_quote
    if base == "USD":
        if price:
            return pip_quote / price
        return pip_quote * usd_per_unit(quote, config)
    return pip_quote * usd_per_unit(quote, config)


def gdelt_articles(query, timespan="1d", maxrecords=25):
    """Query the GDELT Project's official DOC 2.0 API (api.gdeltproject.org).
    GDELT describes itself as a free open platform (gdeltproject.org).
    Returns list of dicts(title, url, source, seendate)."""
    params = {
        "query": query,
        "mode": "artlist",
        "maxrecords": str(maxrecords),
        "format": "json",
        "timespan": timespan,
        "sort": "datedesc",
    }
    url = GDELT_DOC + "?" + urllib.parse.urlencode(params)
    raw = None
    err = None
    for attempt, wait in enumerate((0, 12, 25)):
        if wait:
            time.sleep(wait)
        try:
            raw = _get(url)
            break
        except urllib.error.HTTPError as e:
            err = e
            if e.code != 429:
                raise
    if raw is None:
        raise RuntimeError("GDELT rate-limited the request (429); wait a minute and retry (%s)" % err)
    data = json.loads(raw)
    out = []
    for a in data.get("articles", []):
        out.append({
            "title": a.get("title", ""),
            "url": a.get("url", ""),
            "source": a.get("domain", a.get("sourcecountry", "")),
            "seendate": a.get("seendate", ""),
        })
    return out


# --- personal-use gate for restricted endpoints ----------------------------

ACK_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".personal-use-ack")

YAHOO_NOTICE = (
    "Yahoo Finance's chart endpoint is unofficial and personal-use under Yahoo's terms "
    "(https://legal.yahoo.com/us/en/yahoo/terms/otos/index.html). This software is built "
    "so each person runs it locally for their own analysis. No intraday data is bundled "
    "or redistributed by the project."
)


def personal_use_allowed(config=None):
    """Intraday endpoints (Yahoo) activate only when BOTH:
      - the environment is not declared public (FXPULSE_MODE != 'public'), and
      - a per-install acknowledgment exists (file .personal-use-ack), or
        config.json sets personal_use_acknowledged: true, or
        env FXPULSE_PERSONAL_USE=1 (for the user's own scripts/CI).
    Otherwise callers must run in limited mode (official reference rates only)."""
    if os.environ.get("FXPULSE_MODE", "").lower() == "public":
        return False
    if os.environ.get("FXPULSE_PERSONAL_USE") == "1":
        return True
    if os.path.exists(ACK_PATH):
        return True
    config = config if config is not None else load_config()
    return bool(config.get("personal_use_acknowledged"))


def acknowledge_personal_use():
    with open(ACK_PATH, "w") as f:
        f.write(YAHOO_NOTICE + "\nacknowledged: personal, non-redistributing local use\n")
    return ACK_PATH


def require_intraday(config=None):
    """Gate for tools that need intraday bars. Exits with a clear message when
    intraday is not allowed, instead of silently calling restricted endpoints."""
    if personal_use_allowed(config):
        return
    raise SystemExit(
        "Intraday data is OFF.\n"
        + YAHOO_NOTICE + "\n"
        "If you are running this locally for your own personal analysis, activate it once with:\n"
        "    python3 fxdata.py --acknowledge-personal-use\n"
        "Without activation, tools fall back to official central-bank reference rates only "
        "(Frankfurter/ECB: a few updates per day, not live quotes), and intraday features "
        "(scan/plan/timemachine) will not run."
    )



if __name__ == "__main__":
    import sys as _sys
    if "--acknowledge-personal-use" in _sys.argv:
        print("wrote %s" % acknowledge_personal_use())
        print(YAHOO_NOTICE)
    else:
        print("personal-use intraday active:", personal_use_allowed())
