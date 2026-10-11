"""Free market data: Nasdaq (stocks/ETFs), Coinbase (crypto), FRED (macro).

All functions return plain lists of dicts sorted by date ascending.
"""
from __future__ import annotations

import csv
import datetime as dt
import io
import time

import requests

UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36",
      "Accept": "application/json, text/plain, */*"}


def _get(url, params=None, tries=4, timeout=40, headers=None):
    err = None
    for i in range(tries):
        try:
            r = requests.get(url, params=params, headers=headers or UA, timeout=timeout)
            if r.status_code == 200:
                return r
            err = RuntimeError(f"HTTP {r.status_code} for {url}")
        except requests.RequestException as e:
            err = e
        time.sleep(3 * (i + 1))
    raise err


def _num(s):
    return float(str(s).replace("$", "").replace(",", ""))


def nasdaq_daily(symbol: str, assetclass: str, start: dt.date, end: dt.date):
    try:
        return _nasdaq_daily(symbol, assetclass, start, end)
    except Exception:  # noqa: BLE001 — fall back to Stooq if Nasdaq blocks the runner
        return stooq_daily(symbol, start, end)


def stooq_daily(symbol: str, start: dt.date, end: dt.date):
    r = _get("https://stooq.com/q/d/l/", {"s": symbol.lower() + ".us", "i": "d",
                                          "d1": start.strftime("%Y%m%d"), "d2": end.strftime("%Y%m%d")})
    out = []
    for row in csv.DictReader(io.StringIO(r.text)):
        try:
            out.append({"date": row["Date"], "open": float(row["Open"]), "close": float(row["Close"])})
        except (KeyError, ValueError):
            pass
    if not out:
        raise RuntimeError(f"no data for {symbol}")
    return out


def _nasdaq_daily(symbol: str, assetclass: str, start: dt.date, end: dt.date):
    r = _get(f"https://api.nasdaq.com/api/quote/{symbol}/historical",
             {"assetclass": assetclass, "fromdate": start.isoformat(), "todate": end.isoformat(), "limit": 9999})
    rows = ((r.json().get("data") or {}).get("tradesTable") or {}).get("rows") or []
    out = []
    for x in rows:
        d = dt.datetime.strptime(x["date"], "%m/%d/%Y").date()
        out.append({"date": d.isoformat(), "open": _num(x["open"]), "close": _num(x["close"])})
    if not out:
        raise RuntimeError(f"no Nasdaq rows for {symbol}")
    return sorted(out, key=lambda r: r["date"])


def coinbase_hourly(product: str, start: dt.datetime, end: dt.datetime):
    """Hourly candles. Coinbase format: [time, low, high, open, close, volume]; max 300 per call."""
    out = {}
    cur = start
    while cur < end:
        nxt = min(end, cur + dt.timedelta(hours=290))
        r = _get(f"https://api.exchange.coinbase.com/products/{product}/candles",
                 {"granularity": 3600, "start": cur.isoformat(), "end": nxt.isoformat()})
        for t, lo, hi, o, c, v in r.json():
            out[t] = {"ts": t, "open": o, "close": c}
        cur = nxt
        time.sleep(0.4)
    return [out[k] for k in sorted(out)]


def coinbase_daily_at(product: str, start: dt.date, end: dt.date, open_utc_hour=13, close_utc_hour=20):
    """Crypto 'daily' bars aligned to US market hours: open = 13:00 UTC hourly open, close = 20:00 UTC hourly close."""
    s = dt.datetime.combine(start, dt.time(0), tzinfo=dt.timezone.utc)
    e = dt.datetime.combine(end + dt.timedelta(days=1), dt.time(0), tzinfo=dt.timezone.utc)
    hours = {h["ts"]: h for h in coinbase_hourly(product, s, e)}
    out = []
    d = start
    while d <= end:
        o = hours.get(int(dt.datetime.combine(d, dt.time(open_utc_hour), tzinfo=dt.timezone.utc).timestamp()))
        c = hours.get(int(dt.datetime.combine(d, dt.time(close_utc_hour - 1), tzinfo=dt.timezone.utc).timestamp()))
        if o and c:
            out.append({"date": d.isoformat(), "open": o["open"], "close": c["close"]})
        d += dt.timedelta(days=1)
    return out


def fred(series: str, start: dt.date):
    r = _get("https://fred.stlouisfed.org/graph/fredgraph.csv", {"id": series}, timeout=60, headers={"User-Agent": "curl/8.5.0"})
    out = []
    for row in csv.DictReader(io.StringIO(r.text)):
        k = [c for c in row if c != "observation_date" and c.upper() != "DATE"][0]
        dkey = row.get("observation_date") or row.get("DATE")
        try:
            if dkey >= start.isoformat():
                out.append({"date": dkey, "value": float(row[k])})
        except ValueError:
            pass
    return out


def asset_daily(source, start: dt.date, end: dt.date):
    kind, sym, cls = source
    if kind == "nasdaq":
        return nasdaq_daily(sym, cls, start, end)
    if kind == "coinbase":
        return coinbase_daily_at(sym, start, end)
    raise ValueError(kind)
