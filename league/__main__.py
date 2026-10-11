"""CLI.

  python -m league update                 # refresh prices and macro data
  python -m league decide [--mock]        # Monday before the open: ask every manager
  python -m league daily                  # after the close: execute pending orders and mark funds
  python -m league brief MANAGER_ID       # print the brief a manager would get
  python -m league ping                   # check the API key and that every model answers
"""
import argparse

from . import brief, config, engine, market


def main():
    ap = argparse.ArgumentParser(prog="league")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("update")
    d = sub.add_parser("decide"); d.add_argument("--mock", action="store_true"); d.add_argument("--only", nargs="*"); d.add_argument("--asof")
    y = sub.add_parser("daily"); y.add_argument("--date")
    sub.add_parser("ping")
    b = sub.add_parser("brief"); b.add_argument("manager", nargs="?", default=config.MANAGERS[0]["id"])
    a = ap.parse_args()

    if a.cmd == "update":
        market.update()
    elif a.cmd == "decide":
        import datetime as dt
        if not a.mock and not a.asof and dt.date.today().isoformat() < config.SEASON["start"]:
            print(f"Season starts {config.SEASON['start']}; no decisions before that.")
            return
        asof = a.asof or market.trading_days()[-1]
        engine.decide(asof, mock=a.mock, only=a.only)
    elif a.cmd == "daily":
        engine.daily(a.date)
    elif a.cmd == "ping":
        from . import models
        total = 0.0
        for m in config.MANAGERS:
            try:
                raw, u = models.ask_openrouter(m["model"], brief.SYSTEM, "Test run. Put 100% in CASH and say 'test' as thesis and note.", tries=1)
                total += u.get("cost_usd") or 0
                print(f"OK   {m['name']:<18} {m['model']:<34} served_by={u.get('served_by')} cost=${u.get('cost_usd') or 0:.4f} {u.get('seconds')}s")
            except Exception as e:  # noqa: BLE001
                print(f"FAIL {m['name']:<18} {m['model']:<34} {e}")
        print(f"Total test cost: ${total:.4f}")
    elif a.cmd == "brief":
        st = engine.load_state()
        f = st["funds"].get(a.manager) or engine.new_fund(None)
        asof = market.trading_days()[-1]
        w, nav = engine.weights_of(f, asof) if f["units"] else ({}, config.START_CAPITAL)
        print(brief.SYSTEM, "\n\n---\n\n", brief.build(asof, f, nav, w, len(st["weeks"]) + 1))


if __name__ == "__main__":
    main()
