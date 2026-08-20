# Pop Scanner — Advanced Features

Internal reference. Documents everything built beyond the base README.

---

## Ranked Setup Scanners

```bash
python pop_scan.py --top10      # top 10 setups across full universe (366 tickers, ~90s)
python pop_scan.py --top20      # top 20
python pop_scan.py --mega10     # top 10 from 26-name pulse list (~30s, more reliable)
python pop_scan.py --mega20     # top 20 from pulse list
```

Two-pass design:
- **Pass 1** — parallel fetch (ext + daily MA + hourly) for all tickers, score without grade bonus
- **Pass 2** — sequential grade fetch for top N×2 candidates only (0.5s sleep between calls)
- **Pass 3** — earnings dates for final top-N from `earnings_cache.json`, live fetch only for unknowns
- Re-score with grade bonus → sort → print

---

## Composite Score

`_top10_score(ext_r, pop_r, hourly_ok, grade)` — higher = better entry setup.

| Component | Max pts | Notes |
|---|---|---|
| Zone (10w runway) | +25 | fresh ≥70% runway; penalizes blown ceiling |
| Weekly CMF | +20 | ≥0.25 = full; below 10w + CMF ≥0.20 gets override (+8 vs -15) |
| Weekly slope | +12 | >3%/wk best; negative penalized |
| RSI | +8 | 45–65 sweet spot; >75 or <35 penalized |
| 87w structure | +8 | near long-term base scores higher |
| Algo tier | +25 | strong: CMF ≥0.15 + slope up + 3/3 MAs |
| Daily zone | +15 | 3/3 daily MAs above |
| Weekly CMF (pop) | +10 | |
| Weekly slope (pop) | +8 | |
| Hourly stack | +5 | |
| Grade | +10 | A+ = 10, A = 6, B = 2 |

---

## Mega-Cap Pulse List

`MEGA_CAP` in `pop_scan.py` — 26 names for `--mega10/--mega20`. Not an S&P definition — a focus pulse:

```
MU AMD NVDA AVGO QCOM ALAB          # core positions + semis
AAPL MSFT GOOGL AMZN META TSLA NFLX # QQQ drivers
JPM V MA GS                          # financials
LLY ABBV UNH                         # healthcare
HD COST ADP                          # consumer + industrials
SPY QQQ IWM                          # structure read (no grade fetch — ETF skip list)
```

---

## Regime Gate

`regime.py` — shared, no scan imports (avoids circular dependency with extension_scan).

```
BULL     VIX < 22, SPY clearly above 10w    → setups live
CAUTION  VIX 22-28 or SPY within ±1.5% 10w → watch for macro overrides
DEFENSE  VIX 28-35 or SPY below 10w >1%    → defined-risk only
STORM    VIX > 35                           → sell premium only
```

SPY 10w MA computed from 10-week rolling mean of weekly closes. VIX from `^VIX` daily.
Regime banner prints **before the scan starts** so market context is visible immediately.

---

## VIX Sizing Signal

`sizing_signal(regime)` in `regime.py` — pure function, no data fetch.

```
FULL     ■■■■  Standard allocation — all setups valid
HALF     ■■░░  Half size — watch for macro overrides before entry
QUARTER  ■░░░  Defined-risk spreads only — smallest size, avoid directional
SELL-IV  ░░░░  Sell premium into elevated VIX — no directional setups
```

Appears as a SIZING line below REGIME in every `--top/--mega` run. HTML pages include
it as a second row inside the regime banner div.

---

## Event Risk Calendar

`event_risk.py` — shared, no scan imports.

Fetches next earnings date via `yf.Ticker().calendar` (not `earnings_dates` — requires lxml).
Falls back to `earningsTimestamp` from `.info`.

Risk levels:
```
HIGH  ≤7 days   ⚠Nd   red     — setup is a trap, do not enter
WARN  8-14 days  ~Nd   amber   — be aware, size down
NEAR  15-30 days  Nd   dim     — on radar, not blocking
blank >30 days          —      — no near-term event risk
```

**CLI `--top/--mega`** → ER column between GR and PRICE.
**CLI individual** (`python pop_scan.py NVDA AMD`) → Earnings line in header.
**HTML** → inline badge next to ticker name on both scan pages.

**Cache**: `earnings_cache.json`, 7-day TTL. Reads from disk first — live fetch only for
unknowns. Pre-seeded for MEGA_CAP names. This prevents silent blanks after a heavy pass1
exhausts Yahoo's rate window.

---

## Grade Caching

`grade_cache.json` — persists fundamental grades between runs.
`_load_grade_cache()` / `_save_grade_cache()` in `pop_scan.py`.

Why it exists: `--top10` run immediately after `--top20` would re-fetch grades from Yahoo
on an already-stressed session → all `—`. With disk cache, second run reads grades instantly.

Grades are computed from: OM ≥10%, NM ≥5%, ROE ≥10%, D/EV ≤20%, FCF yield >0% (to qualify).
Then: A+ (strict: D/EV ≤3%, OM ≥20%, FCF ≥2%, GM ≥60%, RevG ≥5%) → A → B.

ETFs (SPY/QQQ/IWM/GLD/TLT etc.) skip grade fetch entirely via `_ETF_SET`.
yfinance stdout/stderr suppressed during `.info` fetch to prevent HTTP noise.

---

## Shared Module Architecture

```
regime.py        — get_regime(), sizing_signal(), regime_html(), REGIME_CSS
event_risk.py    — get_earnings_batch(), earnings_cli(), earnings_html_badge(), EVENT_CSS
```

Both are import-safe: no circular dependency with pop_scan ↔ extension_scan.
`extension_scan` imports from `pop_scan` → `pop_scan` cannot import from `extension_scan`.
Shared modules sit outside that chain.

---

## Gap Backlog

| # | Gap | Status |
|---|---|---|
| 1 | Macro regime gate | ✅ Done — `regime.py` |
| 2 | Event risk calendar | ✅ Done — `event_risk.py` |
| 3 | VIX sizing signal | ✅ Done — `sizing_signal()` |
| 4 | IV × extension crossover view | 🕐 Waiting — `iv_data.json` hits 30 days ~mid-Sep 2026 |
| 5 | Pre-market gap blindness | Research problem — needs different data source |
| 6 | Rotation prediction | Different problem entirely — sector flow analysis |

---

## Watchlist Additions (Aug 2026)

**DT (Dynatrace)** — AI-powered observability; Davis causal AI; GM 81.6%, FCF 26.1%;
OM/NM/ROE gating (3/7 gates); AI LLM trace + GPU infra angle; added WATCHLIST.

**NTAP (NetApp)** — Hybrid cloud storage; Azure NetApp Files + Google Cloud NetApp Volumes;
GM 70.7%, OM 27.3%, ROE 106.7%, FCF 18.7%; RevG 12.5% sole blocker (gate ≥15%);
AI unstructured data storage tailwind; added WATCHLIST.
