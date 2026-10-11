"""Local price cache (data/prices/*.json) and helpers to read it."""
from __future__ import annotations

import datetime as dt
import json
import math
import pathlib

from . import config, data

ROOT = pathlib.Path(__file__).resolve().parent.parent
PRICES = ROOT / "data" / "prices"
MACRO = ROOT / "data" / "macro"
HISTORY_START = dt.date(2025, 9, 1)   # enough history for 12-week returns and 50-day averages


def _load(path):
    return json.loads(path.read_text()) if path.exists() else []


def _save(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, separators=(",", ":")))


def update(today: dt.date | None = None, log=print):
    today = today or dt.date.today()
    for sym, (_, _, src) in config.ASSETS.items():
        path = PRICES / f"{sym}.json"
        rows = _load(path)
        start = HISTORY_START if not rows else dt.date.fromisoformat(rows[-1]["date"]) - dt.timedelta(days=5)
        fresh = data.asset_daily(src, start, today)
        merged = {r["date"]: r for r in rows}
        merged.update({r["date"]: r for r in fresh})
        out = [merged[k] for k in sorted(merged)]
        _save(path, out)
        log(f"  {sym}: {len(out)} days, last {out[-1]['date'] if out else '—'}")
    for sid in config.MACRO:
        try:
            rows = data.fred(sid, HISTORY_START - dt.timedelta(days=400))
            if rows:
                _save(MACRO / f"{sid}.json", rows)
            log(f"  {sid}: {len(rows)} obs")
        except Exception as e:  # noqa: BLE001 — macro is context only; keep the cached copy
            log(f"  {sid}: FRED unavailable ({e}); keeping cached data")


def series(sym):
    return _load(PRICES / f"{sym}.json")


def macro(sid):
    return _load(MACRO / f"{sid}.json")


def trading_days():
    """Equity trading days = dates present in SPY."""
    return [r["date"] for r in series("SPY")]


def price_on(sym, date, field="close"):
    """Exact price on a date, or None."""
    for r in reversed(series(sym)):
        if r["date"] == date:
            return r[field]
        if r["date"] < date:
            return None
    return None


def last_close(sym, asof):
    """Most recent close on or before asof."""
    for r in reversed(series(sym)):
        if r["date"] <= asof:
            return r["close"], r["date"]
    return None, None


def stats(sym, asof):
    rows = [r for r in series(sym) if r["date"] <= asof]
    if len(rows) < 60:
        return None
    px, d = rows[-1]["close"], rows[-1]["date"]
    def back(days):
        target = (dt.date.fromisoformat(d) - dt.timedelta(days=days)).isoformat()
        for r in reversed(rows):
            if r["date"] <= target:
                return r["close"]
        return rows[0]["close"]
    closes = [r["close"] for r in rows]
    rets = [math.log(closes[i] / closes[i - 1]) for i in range(len(closes) - 20, len(closes))]
    per_year = 365 if config.ASSETS[sym][1] == "crypto" else 252
    vol = (sum(x * x for x in rets) / len(rets)) ** 0.5 * math.sqrt(per_year) * 100
    ma50 = sum(closes[-50:]) / 50
    return {"price": px, "date": d, "r1d": (px / closes[-2] - 1) * 100,
            "r1w": (px / back(7) - 1) * 100, "r4w": (px / back(28) - 1) * 100, "r12w": (px / back(84) - 1) * 100,
            "vol20": vol, "vs_ma50": (px / ma50 - 1) * 100,
            "hi52": (px / max(closes[-252:]) - 1) * 100}
