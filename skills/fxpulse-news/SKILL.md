---
name: fxpulse-news
description: Currency and central-bank news from the GDELT Project's official free API. Use when the user asks what news is moving a currency.
---

Run `python3 fx_news.py --ccy EUR USD JPY GBP --timespan 1d` from the fxpulse
directory. Summarize the headlines with their source links and seendate
timestamps, and remind the user that headlines are leads to open and verify,
not facts. The API paces itself at one request per 5 seconds, so expect a few
seconds of wait between currencies.
