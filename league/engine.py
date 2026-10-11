"""League engine: weekly decisions, execution at close, daily marking, results for the site."""
from __future__ import annotations

import datetime as dt
import json
import pathlib

from . import brief, config, market, models

ROOT = pathlib.Path(__file__).resolve().parent.parent
STATE = ROOT / "data" / "state.json"
DECISIONS = ROOT / "data" / "decisions"
RESULTS = ROOT / "site" / "results.json"


# ---------- state ----------
def load_state():
    if STATE.exists():
        return json.loads(STATE.read_text())
    return {"season": config.SEASON["id"], "start": config.SEASON["start"], "funds": {}, "benchmarks": {}, "pending": None, "weeks": []}


def save_state(st):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(st, indent=1))


def new_fund(joined):
    return {"cash": config.START_CAPITAL, "units": {}, "joined": joined, "nav": [], "decisions": []}


def nav_of(fund, asof):
    total = fund["cash"]
    for sym, u in fund["units"].items():
        px, _ = market.last_close(sym, asof)
        total += u * px
    return total


def weights_of(fund, asof):
    nav = nav_of(fund, asof)
    out = {}
    for sym, u in fund["units"].items():
        px, _ = market.last_close(sym, asof)
        out[sym] = u * px / nav
    return out, nav


# ---------- weekly: decide ----------
def decide(asof: str, mock=False, only=None, log=print):
    """Run before Monday's open. asof = last completed trading day (usually Friday)."""
    st = load_state()
    week_no = len(st["weeks"]) + 1
    pending = {"asof": asof, "created": dt.datetime.utcnow().isoformat(timespec="seconds") + "Z", "week": week_no, "orders": {}}
    total_cost = 0.0
    for m in config.MANAGERS:
        if only and m["id"] not in only:
            continue
        fund = st["funds"].get(m["id"]) or new_fund(None)
        w_now, nav = weights_of(fund, asof) if fund["units"] else ({}, fund["cash"] if fund["nav"] else config.START_CAPITAL)
        user = brief.build(asof, fund, nav, w_now, week_no)
        try:
            raw, usage = models.ask_mock(m["id"], asof) if mock else models.ask_openrouter(m["model"], brief.SYSTEM, user)
            w = models.clean_weights(raw.get("weights", {}))
            order = {"weights": w, "thesis": str(raw.get("thesis", ""))[:200], "note": str(raw.get("note", ""))[:500],
                     "model": m["model"], "usage": usage, "status": "ok"}
            total_cost += usage.get("cost_usd") or 0
            log(f"  {m['name']:<18} ok   gross {sum(abs(v) for v in w.values()):.2f}  cost ${usage.get('cost_usd') or 0:.4f}")
        except Exception as e:  # noqa: BLE001  — a failed manager keeps last week's book
            order = {"weights": None, "thesis": "", "note": "", "model": m["model"], "usage": None, "status": f"error: {e}"[:300]}
            log(f"  {m['name']:<18} FAILED {e}")
        order["brief"] = user
        pending["orders"][m["id"]] = order
    st["pending"] = pending
    save_state(st)
    DECISIONS.mkdir(parents=True, exist_ok=True)
    (DECISIONS / f"week-{week_no:02d}-{asof}.json").write_text(json.dumps(pending, indent=1))
    log(f"Week {week_no}: decisions saved. Model cost ${total_cost:.4f}")
    return pending


# ---------- daily: execute pending + mark ----------
def _execute_fund(fund, target, date, nav_before):
    cost = 0.0
    new_units = {}
    for sym in set(fund["units"]) | set(target):
        px = market.price_on(sym, date) if config.ASSETS[sym][1] == "equity" else market.last_close(sym, date)[0]
        tgt_units = target.get(sym, 0) * nav_before / px
        traded = abs(tgt_units - fund["units"].get(sym, 0)) * px
        cost += traded * config.COST_BPS[config.ASSETS[sym][1]] / 10_000
        if abs(tgt_units) > 1e-12:
            new_units[sym] = tgt_units
    invested = 0.0
    for sym, u in new_units.items():
        px = market.price_on(sym, date) if config.ASSETS[sym][1] == "equity" else market.last_close(sym, date)[0]
        invested += u * px
    fund["units"] = new_units
    fund["cash"] = nav_before - cost - invested
    return cost


def daily(today: str | None = None, log=print):
    st = load_state()
    days = market.trading_days()
    today = today or days[-1]
    if today not in days:
        log(f"{today} is not a trading day with data yet; nothing to do.")
        return
    p = st.get("pending")
    if p and today > p["asof"]:
        log(f"Executing week {p['week']} at the close of {today}")
        for mid, order in p["orders"].items():
            fund = st["funds"].get(mid)
            if fund is None:
                fund = st["funds"][mid] = new_fund(today)
            nav_before = nav_of(fund, today) if fund["nav"] else config.START_CAPITAL
            if order["weights"] is not None:
                c = _execute_fund(fund, order["weights"], today, nav_before)
                log(f"  {mid:<18} rebalanced, cost ${c:,.0f}")
            fund["decisions"].append({"week": p["week"], "date": today, "weights": order["weights"], "thesis": order["thesis"],
                                      "note": order["note"], "status": order["status"], "usage": order["usage"]})
        for bid, b in config.BENCHMARKS.items():
            bench = st["benchmarks"].get(bid) or new_fund(today)
            nav_before = nav_of(bench, today) if bench["nav"] else config.START_CAPITAL
            _execute_fund(bench, b["weights"], today, nav_before)
            st["benchmarks"][bid] = bench
        st["weeks"].append({"week": p["week"], "asof": p["asof"], "executed": today})
        st["pending"] = None
    # mark
    for group in ("funds", "benchmarks"):
        for fid, f in st[group].items():
            nav = nav_of(f, today)
            if f["nav"] and f["nav"][-1][0] == today:
                f["nav"][-1][1] = round(nav, 2)
            elif not f["nav"] or f["nav"][-1][0] < today:
                f["nav"].append([today, round(nav, 2)])
    save_state(st)
    write_results(st, today)
    log(f"Marked {today}.")


# ---------- results for the site ----------
def _dd(series):
    pk, worst = 0, 0.0
    for _, v in series:
        pk = max(pk, v)
        worst = min(worst, v / pk - 1)
    return worst * 100


def _weekly(series, exec_dates):
    pts = [v for d, v in series if d in set(exec_dates)] + ([series[-1][1]] if series else [])
    return [(pts[i] / pts[i - 1] - 1) * 100 for i in range(1, len(pts))]


def write_results(st, today):
    exec_dates = [w["executed"] for w in st["weeks"]]
    meta = {m["id"]: m for m in config.MANAGERS}
    funds = []
    for fid, f in st["funds"].items():
        m = meta.get(fid, {"name": fid, "lab": "", "color": "#888"})
        w, nav = weights_of(f, today)
        last = f["decisions"][-1] if f["decisions"] else {}
        wk = _weekly(f["nav"], exec_dates)
        cost = sum((d.get("usage") or {}).get("cost_usd") or 0 for d in f["decisions"])
        funds.append({"id": fid, "name": m["name"], "lab": m["lab"], "color": m["color"], "model": m.get("model"),
                      "joined": f["joined"], "nav": f["nav"], "value": round(nav, 2),
                      "return": round((nav / config.START_CAPITAL - 1) * 100, 3), "maxdd": round(_dd(f["nav"]), 3),
                      "book": {k: round(v, 4) for k, v in w.items()}, "cash": round(1 - sum(w.values()), 4),
                      "thesis": last.get("thesis", ""), "note": last.get("note", ""), "status": last.get("status", ""),
                      "best_week": round(max(wk), 2) if wk else None, "worst_week": round(min(wk), 2) if wk else None,
                      "model_cost_usd": round(cost, 4),
                      "history": [{"week": d["week"], "date": d["date"], "thesis": d.get("thesis", ""),
                                   "weights": d.get("weights") or {}, "status": d.get("status", "")}
                                  for d in f["decisions"]]})
    funds.sort(key=lambda x: -x["return"])
    bench = []
    for bid, b in st["benchmarks"].items():
        nav = nav_of(b, today)
        bench.append({"id": bid, "name": config.BENCHMARKS[bid]["name"], "nav": b["nav"], "value": round(nav, 2),
                      "return": round((nav / config.START_CAPITAL - 1) * 100, 3), "maxdd": round(_dd(b["nav"]), 3),
                      "book": config.BENCHMARKS[bid]["weights"]})
    tape = {}
    for sym in config.ASSETS:
        px, _ = market.last_close(sym, today)
        rows = [r for r in market.series(sym) if r["date"] <= today]
        ref = next((r["close"] for r in reversed(rows) if r["date"] <= (dt.date.fromisoformat(today) - dt.timedelta(days=7)).isoformat()), None)
        if px:
            tape[sym] = {"price": round(px, 2), "w1": round((px / ref - 1) * 100, 2) if ref else None}
    out = {"season": st["season"], "start": st["start"], "updated": today, "week": len(st["weeks"]), "tape": tape,
           "pending": bool(st.get("pending")), "assets": {k: v[0] for k, v in config.ASSETS.items()},
           "roster": [{k: m[k] for k in ("id", "name", "lab", "color", "model")} for m in config.MANAGERS],
           "funds": funds, "benchmarks": bench}
    RESULTS.parent.mkdir(parents=True, exist_ok=True)
    RESULTS.write_text(json.dumps(out, separators=(",", ":")))
    try:
        from . import og
        og.render(out)
    except Exception as e:  # noqa: BLE001 — the preview image is optional
        print(f"og image skipped: {e}")
