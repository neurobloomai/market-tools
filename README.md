# market-tools

Free, open-source market dashboards and quality stock screeners powered by Yahoo Finance.

## Tools

| File | Market | What it does |
|---|---|---|
| `dashboard.py` | 🇺🇸 US | Sector ETF momentum dashboard — MA signals across 50D/20W/10M/20M |
| `india_dashboard.py` | 🇮🇳 India | NSE sector index briefing — same MA framework for Indian markets |
| `screener.py` | 🇺🇸 US | Quality growth screener — low debt, high ROIC, strong margins, FCF |
| `india_screener.py` | 🇮🇳 India | India quality growth screener — NSE universe across key themes |

## Setup

```bash
pip install yfinance
```

## Usage

```bash
# US dashboard
python dashboard.py
python dashboard.py --refresh   # force fresh data
python dashboard.py --refresh --browser   # for browser rendering

# India dashboard  
python india_dashboard.py
python india_dashboard.py --refresh

# US screener
python screener.py

# India screener
python india_screener.py
```

Both dashboards output a CLI table and save an HTML file locally.

## Signals

- **ALIGNED** — price above all 4 MAs (50D, 20W, 10M, 20M)
- **PULLBACK** — above long-term MAs, below short-term (potential entry)
- **AVOID** — below long-term structure

Volume shown as `x(C)` = closed-day vs 20-day avg · `x(P)` = partial intraday

## Disclaimer

For informational purposes only. Not financial advice.
