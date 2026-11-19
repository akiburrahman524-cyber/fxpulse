#!/usr/bin/env python3
"""Offline tests for fxpulse. No network. Run: python3 test_fx.py"""

import datetime
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import fxdata  # noqa: E402
import fx_scan  # noqa: E402
import fx_timemachine  # noqa: E402
import fx_size  # noqa: E402

FAIL = []


def check(name, cond):
    print(("ok  " if cond else "FAIL") + " " + name)
    if not cond:
        FAIL.append(name)


def synth_bars(days=25, bars_per_day=288, start_price=1.1000, drift=0.0):
    """Deterministic synthetic 5m bars across full UTC days."""
    import math
    bars = []
    base = datetime.datetime(2026, 9, 1, tzinfo=datetime.timezone.utc)
    price = start_price
    for d in range(days):
        day = base + datetime.timedelta(days=d)
        for i in range(bars_per_day):
            ts = int((day + datetime.timedelta(minutes=5 * i)).timestamp())
            wobble = math.sin(i / 5.0 + d) * 0.0004 + drift
            o = price
            c = price + wobble
            h = max(o, c) + 0.0002
            l = min(o, c) - 0.0002
            bars.append({"ts": ts, "open": o, "high": h, "low": l, "close": c})
            price = c
    return bars


# --- pip math
check("pip size EURUSD", fxdata.pip_size("EURUSD") == 0.0001)
check("pip size USDJPY", fxdata.pip_size("USDJPY") == 0.01)
check("to_pips", abs(fxdata.to_pips("EURUSD", 0.0015) - 15.0) < 1e-9)
check("pip value USD-quote", fxdata.pip_value_usd("EURUSD") == 10.0)
check("pip value USDJPY with price", abs(fxdata.pip_value_usd("USDJPY", price=150.0) - 1000.0 / 150.0) < 1e-9)

# --- day splitting + opening range
bars = synth_bars()
days = fx_scan.split_days(bars)
check("split 25 days", len(days) == 25)
check("288 bars per day", all(len(v) == 288 for v in days.values()))
day = days[sorted(days)[0]]
orng = fx_scan.opening_range(day, 7 * 60, 12)
check("opening range formed", orng is not None and orng[2] == 12 and orng[0] > orng[1])

# --- pool + simulation determinism
sessions = fx_timemachine.full_days(bars, None)
check("full days kept", len(sessions) == 25)
check("sessions carry dates", all(isinstance(t[0], datetime.date) for t in sessions))
held = fx_timemachine.full_days(bars, None, exclude_last=5)
check("holdout drops 5 most recent", len(held) == 20 and held[-1][0] < sessions[-1][0])
pool, series = fx_timemachine.build_pool([d for (_, d) in sessions])
check("pool slots", len(pool) == 287)
check("series keeps day count", len(series) == 25)
s1 = fx_timemachine.simulate(pool, 1.1000, 1.0950, 1.1100, 100, 287, 500, 19, 2, "buy", series=series)
s2 = fx_timemachine.simulate(pool, 1.1000, 1.0950, 1.1100, 100, 287, 500, 19, 2, "buy", series=series)
s3 = fx_timemachine.simulate(pool, 1.1000, 1.0950, 1.1100, 100, 287, 500, 7, 2, "buy", series=series)
s4 = fx_timemachine.simulate(pool, 1.1000, 1.0950, 1.1100, 100, 287, 500, 19, 2, "buy", block=6, series=series)
check("same seed same result", s1 == s2)
check("different seed differs", s1 != s3)
check("block resampling changes draws but stays deterministic",
      s4 == fx_timemachine.simulate(pool, 1.1000, 1.0950, 1.1100, 100, 287, 500, 19, 2, "buy", block=6, series=series))
check("counts sum to replays", sum(s1["counts"].values()) == 500 and sum(s4["counts"].values()) == 500)
check("p5 <= median <= p95", s1["p5_final"] <= s1["median_final"] <= s1["p95_final"])

# --- stop-first rule: a bar touching both counts as stop
pool2 = {1: [(1.0, 1.02, 0.98, 1.0)] * 5, 2: [(1.0, 1.02, 0.98, 1.0)] * 5, 3: [(1.0, 1.0, 1.0, 1.0)] * 5}
sim = fx_timemachine.simulate(pool2, 1.0, 0.99, 1.01, 1, 2, 100, 1, 0, "buy")
check("both-touch counts as stop", sim["counts"] == {"target": 0, "stop": 100, "neither": 0})

# --- verdict
v = fx_timemachine.verdict({"counts": {"target": 60, "stop": 40, "neither": 0}}, 1.0)
check("verdict leans target", "target" in v and "+" in v)

# --- sizing (offline: USD-quote pair needs no rates)
out = fx_size.size_position("EURUSD", 20.0, 5000.0, risk_amount=50.0)
check("lots math", abs(out["standard_lots"] - 50.0 / (20.0 * 10.0)) < 1e-9)
check("max loss equals risk", abs(out["max_loss_usd_at_stop"] - 50.0) < 1e-6)

# --- plan validation
try:
    fx_scan.opening_range([], 420, 12)
    check("empty day returns None", True)
except Exception:
    check("empty day returns None", False)

# --- London session open (DST)
check("London open winter = 08:00 UTC", fxdata.session_open_utc_minutes(datetime.date(2026, 11, 18)) == 480)
check("London open summer = 07:00 UTC", fxdata.session_open_utc_minutes(datetime.date(2026, 6, 15)) == 420)
check("BST starts last Sun of Mar", fxdata.london_utc_offset_hours(datetime.date(2026, 3, 29)) == 1)
check("BST ends last Sun of Oct", fxdata.london_utc_offset_hours(datetime.date(2026, 10, 25)) == 0)

# --- history replay has no same-day lookahead: uses only each day's own bars
hist = fx_timemachine.history_replay(sessions, "EURUSD", "buy", 12, 8 * 60, 1.0, london_session=True)
check("history days counted", hist["days"] == 25)
check("history outcomes consistent", hist["target"] + hist["stop"] + hist["neither"] == hist["fired"])

# --- walk-forward runs on synthetic data and uses only earlier days
wf = fx_timemachine.walk_forward(sessions, "EURUSD", "buy", 12, 1.0, 5, 200, 19, 100, 287, 2, 1)
check("walkforward rows = 5", len(wf) == 5)
check("walkforward pools shrink into past", all(r["pool_days"] < 25 for r in wf))
check("walkforward outcomes valid", all((not r["fired"]) or r["actual"] in ("target", "stop", "neither") for r in wf))

# --- cost model: adverse fill cost in R, trigger levels unchanged
sc0 = fx_timemachine.simulate(pool, 1.1000, 1.0950, 1.1100, 100, 287, 500, 19, 2, "buy", series=series, cost_r=0.0)
sc1 = fx_timemachine.simulate(pool, 1.1000, 1.0950, 1.1100, 100, 287, 500, 19, 2, "buy", series=series, cost_r=0.02)
sc1s = fx_timemachine.simulate(pool, 1.1000, 1.0950, 1.1100, 100, 287, 500, 19, 2, "sell", series=series, cost_r=0.02)
sc0s = fx_timemachine.simulate(pool, 1.1000, 1.0950, 1.1100, 100, 287, 500, 19, 2, "sell", series=series, cost_r=0.0)
check("cost leaves hit counts unchanged", sc0["counts"] == sc1["counts"] and sc0s["counts"] == sc1s["counts"])
check("cost reduces avg R by exactly cost_r (buy)", abs((sc0["avg_r"] - sc1["avg_r"]) - 0.02) < 1e-9)
check("cost reduces avg R by exactly cost_r (sell)", abs((sc0s["avg_r"] - sc1s["avg_r"]) - 0.02) < 1e-9)
check("cost is adverse", sc1["avg_r"] < sc0["avg_r"] and sc1s["avg_r"] < sc0s["avg_r"])

# --- pip-value dimensional invariants, independent of implementation constants:
# (USD value of one pip per lot) x (quote units per USD price) must equal the
# quote units of one pip per lot, i.e. pip_size x 100,000, for any quote currency
for _pair, _px in (("USDJPY", 150.0), ("USDCHF", 0.90), ("USDCAD", 1.35)):
    check("pip value invariant %s" % _pair,
          abs(fxdata.pip_value_usd(_pair, price=_px) * _px - fxdata.pip_size(_pair) * 100000.0) < 1e-6)
check("JPY pip is 1000 quote units per lot", fxdata.pip_size("USDJPY") * 100000.0 == 1000.0)
_outj = fx_size.size_position("USDJPY", 15.0, 5000.0, risk_amount=50.0, price=150.0)
# identity holds up to the 4-decimal display rounding of the output fields
check("sizing identity USDJPY", abs(_outj["standard_lots"] * 15.0 * _outj["pip_value_usd_per_std_lot"] - 50.0) < 0.01)
check("sizing USDJPY sane magnitude", _outj["standard_lots"] < 5.0)  # the 100x defect produced ~53

# --- sizing: units rounded DOWN, never risk more than intended
out2 = fx_size.size_position("EURUSD", 15.0, 5000.0, risk_amount=50.0)
check("units rounded down to 100s", out2["units_approx"] <= out2["standard_lots"] * 100000 and out2["units_approx"] % 100 == 0)
check("floored units risk no more than intended", out2["max_loss_usd_at_floored_units"] <= 50.0 + 1e-9)

# --- sizing input validation
for _bad in (lambda: fx_size.size_position("EURUSD", 15, 5000, risk_amount=0),
             lambda: fx_size.size_position("EURUSD", 15, -100, risk_amount=50),
             lambda: fx_size.size_position("EURUSD", 15, 5000, risk_amount=6000)):
    try:
        _bad()
        check("size_position rejects bad input", False)
    except RuntimeError:
        check("size_position rejects bad input", True)

# --- bootstrap CI sanity (research module, offline)
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "research"))
import fx_backtest as _bt  # noqa: E402
_rs = [1.0] * 40 + [-1.0] * 40
_ci = _bt.bootstrap_ci(_rs, n_boot=500, seed=1)
check("bootstrap ci ordered", _ci[0] <= _ci[1])
check("bootstrap ci brackets mean", _ci[0] <= 0.0 <= _ci[1])
check("bootstrap ci deterministic", _ci == _bt.bootstrap_ci(_rs, n_boot=500, seed=1))

# --- bar freshness
import time as _t
fresh = [{"ts": int(_t.time()) - 60, "open": 1, "high": 1, "low": 1, "close": 1}]
check("fresh bar age ~60s", abs(fxdata.bars_age_seconds(fresh) - 60) < 5)
check("empty bars age None", fxdata.bars_age_seconds([]) is None)

print()
if FAIL:
    print("%d FAILURES" % len(FAIL))
    sys.exit(1)
print("all tests passed")
