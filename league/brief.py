"""Daily market brief: identical for every manager except the 'your fund' block."""
from __future__ import annotations

import datetime as dt

from . import config, market


def market_block(asof: str) -> str:
    lines = [f"MARKET BRIEF — data through {asof} (closing prices)", "",
             "ASSETS (price | 1d | 1w | 4w | 12w | 20d vol, annualised | vs 50-day avg | vs 52-week high)"]
    for sym, (name, cls, _) in config.ASSETS.items():
        s = market.stats(sym, asof)
        if not s:
            continue
        lines.append(f"{sym:<5} {name:<24} {s['price']:>12,.2f} | {s['r1d']:+5.1f}% | {s['r1w']:+6.1f}% | {s['r4w']:+6.1f}% | {s['r12w']:+6.1f}% | "
                     f"{s['vol20']:5.1f}% | {s['vs_ma50']:+6.1f}% | {s['hi52']:+6.1f}%")
    lines += ["", "MACRO (latest | change over 4 weeks)"]
    for sid, label in config.MACRO.items():
        rows = [r for r in market.macro(sid) if r["date"] <= asof]
        if not rows:
            continue
        last = rows[-1]
        if sid == "CPIAUCSL":
            prev = [r for r in rows if r["date"] <= (dt.date.fromisoformat(last["date"]) - dt.timedelta(days=360)).isoformat()]
            if prev:
                lines.append(f"- CPI inflation, year over year: {(last['value'] / prev[-1]['value'] - 1) * 100:.1f}% (as of {last['date'][:7]})")
            continue
        ref = [r for r in rows if r["date"] <= (dt.date.fromisoformat(last["date"]) - dt.timedelta(days=28)).isoformat()]
        chg = f"{last['value'] - ref[-1]['value']:+.2f}" if ref else "n/a"
        lines.append(f"- {label}: {last['value']:.2f} ({chg})")
    return "\n".join(lines)


def fund_block(fund: dict, nav: float, weights: dict, week_no: int) -> str:
    book = ", ".join(f"{k} {v * 100:.0f}%" for k, v in sorted(weights.items(), key=lambda x: -abs(x[1])) if abs(v) >= 0.005) or "100% cash"
    ret = (nav / config.START_CAPITAL - 1) * 100
    last = fund["decisions"][-1]["thesis"] if fund.get("decisions") else "none yet"
    return (f"YOUR FUND — day {week_no}\n"
            f"- Net asset value: ${nav:,.0f} ({ret:+.2f}% since you started with ${config.START_CAPITAL:,.0f})\n"
            f"- Current book (share of NAV): {book}\n"
            f"- Your last thesis: {last}")


SYSTEM = """You are the portfolio manager of a $1,000,000 fund competing in a public league of AI fund managers.
Every US trading day, before the market opens, you get the same market brief as every other manager and set target weights for the day.
Your trades execute at today's closing prices. You will not see any news or prices beyond the brief.

Rules:
- Assets you can hold: SPY, QQQ, NVDA, AAPL, TLT, GLD, USO, BTC, ETH, and CASH.
- Weights are fractions of fund value. Negative weight = short position.
- Each asset weight must be between -0.5 and 0.5.
- Gross exposure (sum of absolute weights, excluding CASH) must be at most 1.5.
- All weights including CASH must sum to 1.0.
- Every rebalance pays trading costs, so only trade when you have a reason.

Goal: the highest risk-adjusted return over the season. You are judged publicly every day.

Answer with JSON only:
{"weights": {"SPY": 0.0, "QQQ": 0.0, "NVDA": 0.0, "AAPL": 0.0, "TLT": 0.0, "GLD": 0.0, "USO": 0.0, "BTC": 0.0, "ETH": 0.0, "CASH": 1.0},
 "thesis": "one sentence, max 20 words, your view today",
 "note": "2-3 sentences, max 60 words, what you changed and why"}"""


def build(asof: str, fund: dict, nav: float, weights: dict, week_no: int) -> str:
    return market_block(asof) + "\n\n" + fund_block(fund, nav, weights, week_no) + "\n\nSet your target weights for today."
