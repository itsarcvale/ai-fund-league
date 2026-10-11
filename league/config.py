"""League configuration: assets, managers, rules."""

START_CAPITAL = 1_000_000.0
MAX_GROSS = 1.5          # sum of |weights| of risk assets
MAX_SINGLE = 0.5         # max |weight| per asset
COST_BPS = {"equity": 5, "crypto": 10}   # trading cost per traded notional

# symbol -> (display name, asset class, data source id)
ASSETS = {
    "SPY":  ("S&P 500 ETF",              "equity", ("nasdaq", "SPY", "etf")),
    "QQQ":  ("Nasdaq-100 ETF",           "equity", ("nasdaq", "QQQ", "etf")),
    "NVDA": ("Nvidia",                   "equity", ("nasdaq", "NVDA", "stocks")),
    "AAPL": ("Apple",                    "equity", ("nasdaq", "AAPL", "stocks")),
    "TLT":  ("20+ Year Treasury ETF",    "equity", ("nasdaq", "TLT", "etf")),
    "GLD":  ("Gold ETF",                 "equity", ("nasdaq", "GLD", "etf")),
    "USO":  ("Oil ETF",                  "equity", ("nasdaq", "USO", "etf")),
    "BTC":  ("Bitcoin",                  "crypto", ("coinbase", "BTC-USD", None)),
    "ETH":  ("Ether",                    "crypto", ("coinbase", "ETH-USD", None)),
}
TRADABLE = list(ASSETS)          # CASH is implicit

MACRO = {  # FRED series id -> label
    "DGS10": "US 10y Treasury yield (%)",
    "DGS2": "US 2y Treasury yield (%)",
    "DFF": "Fed funds rate (%)",
    "VIXCLS": "VIX",
    "DTWEXBGS": "Broad US dollar index",
    "CPIAUCSL": "CPI index (monthly)",
}

# Managers. id is the stable key used in data files; never change it once a season starts.
MANAGERS = [
    {"id": "claude-opus-5.5",  "name": "Claude Opus 5.5",   "lab": "Anthropic", "color": "#D9772B", "model": "anthropic/claude-opus-5.5"},
    {"id": "gpt-6-astra",      "name": "GPT-6 Astra",       "lab": "OpenAI",    "color": "#10A37F", "model": "openai/gpt-6-astra"},
    {"id": "grok-4.7",         "name": "Grok 4.7",          "lab": "xAI",       "color": "#7A7F8C", "model": "x-ai/grok-4.7"},
    {"id": "gemini-3.8-flash", "name": "Gemini 3.8 Flash",  "lab": "Google",    "color": "#4C7DF0", "model": "google/gemini-3.8-flash"},
    {"id": "deepseek-v4-pro",  "name": "DeepSeek V4 Pro",   "lab": "DeepSeek",  "color": "#5B5FE0", "model": "deepseek/deepseek-v4-pro-0813"},
    {"id": "qwen-3.8-max",     "name": "Qwen3.8 Max",       "lab": "Alibaba",   "color": "#8F5BD9", "model": "qwen/qwen3.8-max-prime"},
    {"id": "kimi-k3",          "name": "Kimi K3",           "lab": "Moonshot",  "color": "#C04BD0", "model": "moonshotai/kimi-k3"},
    {"id": "step-5",           "name": "Step 5 Preview",    "lab": "StepFun",   "color": "#2BB3C0", "model": "stepfun/step-5-preview"},
]

BENCHMARKS = {
    "sp500": {"name": "S&P 500 index fund", "weights": {"SPY": 1.0}},
    "6040":  {"name": "60/40 portfolio",    "weights": {"SPY": 0.6, "TLT": 0.4}},
}

SEASON = {"id": 1, "start": "2026-10-19"}
