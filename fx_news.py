#!/usr/bin/env python3
"""fx_news: currency news from the GDELT Project's official DOC 2.0 API.

GDELT (gdeltproject.org) describes itself as a free open platform; no key is
needed. Queries run per currency and results are deduplicated.

    python3 fx_news.py                          # majors keywords, last 24h
    python3 fx_news.py --ccy EUR USD JPY --timespan 6h
    python3 fx_news.py --query "central bank" --timespan 12h
    python3 fx_news.py --json

Headlines are leads, not facts: open the story before relying on it.
"""

import argparse
import json
import sys

import fxdata

CCY_KEYWORDS = {
    "EUR": "(euro OR ECB OR \"european central bank\")",
    "USD": "(dollar OR \"federal reserve\" OR fed)",
    "JPY": "(yen OR \"bank of japan\")",
    "GBP": "(pound sterling OR \"bank of england\")",
    "CHF": "(swiss franc OR \"swiss national bank\")",
    "CAD": "(canadian dollar OR \"bank of canada\")",
    "AUD": "(australian dollar OR \"reserve bank of australia\")",
    "NZD": "(new zealand dollar OR \"reserve bank of new zealand\")",
}


def collect(ccys, timespan, maxrecords, extra_query=None, lang=None):
    import time
    seen = {}
    errors = []
    queries = list(ccys)
    if extra_query:
        queries.append(extra_query)
    first = True
    for q in queries:
        if not first:
            time.sleep(6)  # GDELT DOC API rate limit: about one request per 5 seconds
        first = False
        text = CCY_KEYWORDS.get(q, q)
        if lang:
            text = "%s sourcelang:%s" % (text, lang)
        try:
            arts = fxdata.gdelt_articles(text, timespan=timespan, maxrecords=maxrecords)
        except Exception as e:  # noqa: BLE001
            errors.append((q, str(e)))
            continue
        for art in arts:
            key = art["url"] or art["title"]
            if key and key not in seen:
                art = dict(art)
                art["matched"] = q
                seen[key] = art
    return list(seen.values()), errors


def main(argv=None):
    p = argparse.ArgumentParser(description="Currency news from GDELT's official API.")
    p.add_argument("--ccy", nargs="+", default=["EUR", "USD", "JPY", "GBP"],
                   help="currency codes (default EUR USD JPY GBP)")
    p.add_argument("--timespan", default="1d", help="GDELT timespan, e.g. 6h, 1d, 3d")
    p.add_argument("--max", type=int, default=15, help="max articles per query")
    p.add_argument("--query", help="extra free-text GDELT query")
    p.add_argument("--lang", help="restrict to a source language, e.g. english")
    p.add_argument("--json", action="store_true")
    a = p.parse_args(argv)

    articles, errors = collect([c.upper() for c in a.ccy], a.timespan, a.max, a.query, a.lang)
    if a.json:
        print(json.dumps({"articles": articles, "errors": errors}, indent=2))
        return 0
    print("GDELT DOC 2.0, timespan %s: %d unique articles (newest seen first as returned by GDELT)"
          % (a.timespan, len(articles)))
    for art in articles[:40]:
        when = art.get("seendate", "")
        print("[%s] %-14s %s" % (when, art.get("matched", "?"), art.get("title", "")[:110]))
        print("    %s  (%s)" % (art.get("url", ""), art.get("source", "")))
    for q, err in errors:
        print("!! %s: %s" % (q, err), file=sys.stderr)
    if not articles and not errors:
        print("no articles matched - widen --timespan or adjust the query")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
