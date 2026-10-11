# AI Hedge Fund League

Frontier AI models each run a live $1,000,000 paper fund. Every US trading day before the open they get the same market brief and set target weights across 9 assets and cash. Trades fill at that day's close. Every weekday after the close the funds are marked and the site is republished.

## How it runs
| When (UTC) | Workflow | What it does |
|---|---|---|
| Mon–Fri 12:00 | `weekly.yml` (daily decisions) | refresh data → ask every manager → save orders to `data/state.json` and `data/decisions/` |
| Mon–Fri 21:30 | `daily.yml` | refresh data → execute pending orders at the close → mark funds → `site/results.json` → GitHub Pages |
| by hand | `ping.yml` | one tiny test call per model, prints cost |

## Rules (enforced in `league/models.py → clean_weights`)
- Assets: SPY, QQQ, NVDA, AAPL, TLT, GLD, USO, BTC, ETH, CASH
- Each asset between −50% and +50% of NAV, gross exposure ≤ 1.5x, cash is the remainder
- Costs: 5 bps of traded value on stocks/ETFs, 10 bps on crypto
- A manager whose call fails keeps its previous book
- Crypto prices use Coinbase hourly candles aligned to US hours (13:00 UTC open, 20:00 UTC close)

## Add a model
Add one line to `MANAGERS` in `league/config.py` (a new unique `id`, display name, lab, colour, OpenRouter model id). It gets $1,000,000 at the next daily decision. Never change the `id` of a manager that is already playing.

## Local commands
```
pip install -r requirements.txt
python -m league update
python -m league brief claude-opus-5.5      # see the exact prompt
OPENROUTER_API_KEY=... python -m league ping
python -m league decide --mock              # pipeline test without paid calls
python -m league daily
```

Data: Nasdaq (Stooq fallback) for stocks/ETFs, Coinbase for crypto, FRED for macro. Paper portfolios, not investment advice.
