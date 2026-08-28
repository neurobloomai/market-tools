# market-tools

Free, open-source market dashboards and quality stock screeners powered by Yahoo Finance.

## Open Source · Commercial Services

The tools, screeners, and frameworks in this repository are **free and open-sourced** — clone them, fork them, adapt them.

**Future premium features, managed services, and neurobloom.ai platform offerings are not free.** Open-source tooling and paid services built on top of it are separate things. If and when services like personalized risk profiling, automated execution, or portfolio construction layers are built and offered — they will be offered commercially.

Open-source is the foundation. It is not a commitment that everything built on that foundation will also be free.

## The Idea

Two filters before touching anything.

First — is it a quality business with durability? Profitable, generates cash, not drowning in debt.

Second — is the price trend confirmed? Four moving averages, price above all four.

Both have to say yes. If only one says yes, you wait. That's it.

The rest of this README is the manual for how those two filters are built and applied.

## Tools

| File | Market | What it does |
|---|---|---|
| `dashboard.py` | 🇺🇸 US | Sector ETF momentum dashboard — MA signals across 50D/20W/10M/20M |
| `india_dashboard.py` | 🇮🇳 India | NSE sector index briefing — same MA framework for Indian markets |
| `screener.py` | 🇺🇸 US | Quality growth screener — low debt, high ROIC, strong margins, FCF · weekly signal column (RSI+MACD dual confirmation, A/A+ only) |
| `india_screener.py` | 🇮🇳 India | India quality growth screener — NSE universe across key themes |
| `aligned_screener.py` | 🇺🇸 US | Weekly MA alignment scanner — 4/4 aligned names, squeeze setups, CMF, RS vs SPY, A/D Line + OBV divergence |
| `weekly_snapshot.py` | 🇺🇸 US | Appends weekly alignment snapshot to `weekly_notes.md` |
| `india_aligned_screener.py` | 🇮🇳 India | Weekly MA alignment scanner for India — same framework, RS vs NIFTY 50, A/D Line + OBV divergence |
| `india_weekly_snapshot.py` | 🇮🇳 India | Appends weekly India alignment snapshot to `india_weekly_notes.md` |
| `ma_scanner.py` | 🇺🇸 US | MA Proximity Scanner — timeframe hierarchy (Weekly → Daily → 4H → 1H), UNIVERSE or WATCHLIST |
| `ma_scanner_india.py` | 🇮🇳 India | MA Proximity Scanner — same hierarchy for NSE universe |
| `ma_live.py` | 🇺🇸 US | **Live** MA Scanner — uses `currentPrice` + `iloc[-1]`; run during market hours for intraday read |
| `india_ma_live.py` | 🇮🇳 India | **Live** MA Scanner — same as `ma_live.py` for NSE names; run during IST market hours |
| `dividend_plays_for_longterm.py` | 🇺🇸 US | Curated long-term dividend universe — quality-filtered, thesis-annotated |
| `daily_alert.py` | 🇺🇸 US | Mid-week alert for the 9 liquid names — fires email only when a crossing occurs **and** the weekly gate is open |
| `top_setups.py` | 🇺🇸 US | Convergence drill — reads last-run HTML outputs, scores every name across quality + RS + CMF + A/D + OBV, fetches monthly MA distance for top 20, prints ranked table in seconds |
| `india_top_setups.py` | 🇮🇳 India | Same convergence drill for India �� reads `india_screener.html` + `india_aligned_screener.html`, adds sector column (India setups are sector-wave driven), RS vs NIFTY |
| `monthly_ma_gate.py` | 🇺🇸🇮🇳 Both | Pre-recovery Monthly MA Gate — names within ±2% (Tier 1, on the gate) or ±5% (Tier 2, in the zone) of their 10-month or 20-month SMA · sorted by span (sum of both MA distances) so names sandwiched between both MAs surface first · on-demand only |
| `pop_scan.py` | 🇺🇸 US | Daily Pop Scanner — price vs 10d/20d/50d MAs · ranked setup modes (`--top10` / `--mega10`) score the full 366-name universe or 32-name pulse list · regime gate + VIX sizing signal + event risk calendar on every ranked run · gold/green/amber range bands · ◎ coiling setups · on-demand |
| `extension_scan.py` | 🇺🇸🇮🇳 Both | Weekly MA Extension + Projection Scanner — for each ticker above its 10w MA, shows current extension vs historical 90th-pct ceiling, runway remaining before ceiling, implied ceiling price, weekly RSI and 10w slope · answers "how much further can this go?" · flags blown-ceiling names in red · supports `--universe`, `--watchlist`, `--dividend`, `--india`, `--india --universe`, `--india --watchlist`, or explicit tickers (CLI-only) · on-demand |
| `iv_snapshot.py` | 🇺🇸 US | Daily IV + HV30 snapshot — captures implied volatility and 30-day historical volatility for all `SPREAD_UNIVERSE` names · appends one row per name to `iv_data.json` · run by GitHub Actions after market close (Tue–Sat) · run locally anytime: `python3 iv_snapshot.py` |
| `iv_rank.py` | 🇺🇸 US | IV Rank reader — reads `iv_data.json`, computes IV Rank (position of today's IV within the 30-day range) and IV/HV ratio for each `SPREAD_UNIVERSE` name · requires ≥30 days of data for a valid signal · at depth==30 prints self-announcement banner with next-step reminder |
| `ticker_score.py` | 🇺🇸 US | On-demand single-ticker deep dive — fundamentals grade, weekly technical (MA alignment, RSI, MACD), weekly momentum, and daily momentum scored in one CLI pass · `python ticker_score.py AAPL` |
| `buffett_kinda_check.py` | 🇺🇸 US | Buffett-style quality lens — 5 low-fog checks (GM>40%, NM>20%, FCF>0, Cash>Debt, D/EV≤0.10) applied to full Universe + Watchlist · parity column shows where our standards agree or diverge · on-demand · _we borrowed the name; the checks are his kinda standard, not an official Berkshire framework_ |
| `run_aligned.sh` | — | Cron entry point — runs all four scripts (US + India), auto-pushes to GitHub |

## Live Outputs

**GitHub Pages → https://neurobloomai.github.io/market-tools/**

Updated automatically every Monday via GitHub Actions — no server, no local machine needed:

| Page | Market | What it shows | Schedule |
|---|---|---|---|
| [market_briefing.html](https://neurobloomai.github.io/market-tools/market_briefing.html) | 🇺🇸 US | Sector ETF momentum dashboard — MA signals, day change, volume, yield | Monday 2:30am UTC |
| [quality_screener.html](https://neurobloomai.github.io/market-tools/quality_screener.html) | 🇺🇸 US | Quality growth screener — margins, ROE, FCF, debt filter · EPS FY trend · Entry zone | Monday 2:30am UTC |
| [aligned_screener.html](https://neurobloomai.github.io/market-tools/aligned_screener.html) | 🇺🇸 US | 4/4 MA alignment · FullCoil squeeze · MTF · CMF · RS vs SPY · A/D Line · OBV | Monday 2:30am UTC |
| [india_briefing.html](https://neurobloomai.github.io/market-tools/india_briefing.html) | 🇮🇳 India | NSE sector index dashboard — same MA framework, RS vs NIFTY | Monday 2:30am UTC |
| [india_screener.html](https://neurobloomai.github.io/market-tools/india_screener.html) | 🇮🇳 India | India quality screener — same filters, NSE universe | Monday 2:30am UTC |
| [india_aligned_screener.html](https://neurobloomai.github.io/market-tools/india_aligned_screener.html) | 🇮🇳 India | 4/4 MA alignment · FullCoil squeeze · MTF · CMF · RS vs NIFTY 50 · A/D Line · OBV | Monday 2:30am UTC |
| [us_marketbreadth.html](https://neurobloomai.github.io/market-tools/us_marketbreadth.html) | 🇺🇸 US | Market breadth — MA20/50/100/200 participation · NH/NL ratio · Elder breadth signal | Tue–Sat after close |
| [monthly_ma_gate.html](https://neurobloomai.github.io/market-tools/monthly_ma_gate.html) | 🇺🇸🇮🇳 Both | Pre-recovery monthly MA gate — names within ±2%/±5% of 10m or 20m SMA, sorted by coil tightness | **On-demand** — trigger from GitHub Actions |
| [backtest.html](https://neurobloomai.github.io/market-tools/backtest.html) | 🇺🇸 US | 5-year framework validation — forward returns, left-tail distribution, vol regime at entry | **On-demand** — `python3 backtest.py` |

Weekly snapshots: [`weekly_notes.md`](weekly_notes.md) · [`india_weekly_notes.md`](india_weekly_notes.md)

## Automation

Runs entirely on GitHub's infrastructure via a single scheduled workflow:

| Workflow | Schedule | What runs |
|---|---|---|
| [Weekly Screener — US + India](.github/workflows/weekly_us.yml) | Monday 2:30am UTC (8am IST / Sunday 9:30pm EST) | US: `dashboard.py` → `weekly_snapshot.py` → `market_breadth.py` → `screener.py` → `aligned_screener.py` · India: `india_dashboard.py` → `india_weekly_snapshot.py` → `india_screener.py` → `india_aligned_screener.py` → `india_marketbreadth.py` · Then: `alert_check.py` → `newsletter_draft.py` |
| [Daily Screener — US](.github/workflows/daily_screener.yml) | Tue–Sat 9:30pm UTC (5:30pm ET, after market close) | `market_breadth.py` → `aligned_screener.py` — keeps breadth + alignment fresh through the week without the full weekly run |
| [Monthly MA Gate — On Demand](.github/workflows/monthly_ma_gate.yml) | **workflow_dispatch only** — no schedule | `monthly_ma_gate.py` — trigger manually from the GitHub Actions UI when market conditions warrant a pre-recovery scan |

The schedule runs at 2:30am UTC Monday — after both the US Friday close and the India Friday close are confirmed, before either market opens for the new week. Clean data both ways, single run.

The workflow checks out the repo, installs dependencies, runs all scripts in sequence, and commits updated HTML and markdown files back — fully automated, zero manual steps.

You can also trigger the workflow manually anytime from the **Actions** tab on GitHub.

`run_aligned.sh` is available as a local fallback if you want to run everything on your own machine:

```bash
bash run_aligned.sh
# log output → /tmp/aligned_cron.log
```

## Weekly Alignment Framework

`aligned_screener.py` scans the quality universe every week across six signals:

| Signal | What it means |
|---|---|
| **4/4 MA aligned** | Price above 10w, 20w, 10m (43w), 20m (87w) SMAs — full structure intact |
| **FullCoil squeeze** | 10w/20w/35w/50w spread compressed — energy building, potential move ahead |
| **CMF (Chaikin Money Flow)** | Volume weighted to close position in range — accumulation vs distribution (20-week) |
| **RS vs SPY / NIFTY** | 13-week price ratio vs benchmark — outperforming or lagging the market |
| **A/D Line** | Cumulative money flow — 13-week slope rising = institutions accumulating regardless of price action |
| **OBV (On Balance Volume)** | Volume conviction — more volume on up days vs down days over 13 weeks |

**Divergence signals** — `◆bull` = A/D Line rising while price is weak (smart money accumulating before price confirms). `◇bear` = A/D falling while price rises (distribution into strength).

**Confluence progression:**

| Pattern | Reading |
|---|---|
| `⚠ + AD:↓ OBV:↓` | Pure distribution — avoid |
| `⚠ + AD:↑ OBV:↑ ◆` | Early accumulation inside distribution — watch closely |
| `◎ + AD:↓ OBV:↑` | Monthly regime turned, weekly volume confirming |
| `◎ + AD:↑ OBV:↑` | Full confluence — strongest setup |

**Special Mention** — names where price has dislocated far from MAs but structure is quietly rebuilding. Not actionable yet. Monthly CMF trend + A/D Line + OBV tracked together for base-building thesis.

**Pullback Watch** — A+/A quality names at exactly 2/4 MA, -10% to -28% from highs. Long-term structure (10m/20m) intact, short-term MAs broken. Different from Special Mention: weeks away from reclaiming, not months. Watch 20w MA as the first gate back to 3/4.

**Philosophy:** medium and long-term orientation. The framework is not built for scalping or short-term noise. Quality names in full MA alignment with tight coils and accumulation signals — hold the structure, wait for the move.

## MA Proximity Scanner

`ma_scanner.py` (US) and `ma_scanner_india.py` (India / NSE) scan the quality universe for names where price is close to a rising MA10 — but only after confirming the higher timeframe structure is intact. The key principle: **higher timeframe alignment gates lower timeframe signals.** Checking 1H when the weekly is broken is noise, not signal.

### Timeframe hierarchy

```
Weekly  → MA10 > MA20, slope rising       (mandatory gate — no band check)
Daily   → MA10 > MA20, price in band      (first actionable signal)
4H      → MA10 > MA20, price in band      (only if Daily passes)
1H      → MA10 > MA20, price in band      (only if 4H passes)
```

If the weekly is not aligned, the ticker is skipped entirely. If the daily is not in setup, 4H and 1H are not evaluated. Each level must hold before the next one is checked.

### Signal levels

| Signal | What it means |
|---|---|
| `D+4H+1H` | Full waterfall — all three tradeable TFs aligned under a confirmed weekly. Strongest. |
| `D+4H` | Daily + 4H aligned, 1H not yet in band. Structure is there, waiting for 1H confirmation. |
| `D` | Daily aligned under weekly, 4H not yet confirming. Earlier stage. |

### Band — ▲ vs ▽

Price within **-3% to +3% of MA10**:
- `▲` — price above MA10 (confirmed, not extended)
- `▽` — price approaching MA10 from below (early signal — MA alignment still intact, price pulling back into MA10)

### Usage

```bash
# US — confirmed closes (weekly cadence)
python3 ma_scanner.py                   # scan UNIVERSE (confirmed close, iloc[-2])
python3 ma_scanner.py --watchlist       # scan WATCHLIST

# India / NSE — confirmed closes (weekly cadence)
python3 ma_scanner_india.py             # scan India UNIVERSE
python3 ma_scanner_india.py --watchlist # scan India WATCHLIST

# Live — intraday read (run during market hours)
python3 ma_live.py                      # US live: liquid panel + watchlist + universe
python3 india_ma_live.py                # India live: liquid panel + watchlist + universe
```

> **`ma_scanner.py` vs `ma_live.py`:** The weekly scanner uses `iloc[-2]` (last confirmed closed bar) — safe and stable for weekly notes. The live scanner uses `currentPrice` + `iloc[-1]` (latest bar, possibly incomplete intraday) — use it during market hours to catch moves before the close confirms.

### Convergence Drill — `top_setups.py`

After the weekly run, `top_setups.py` synthesizes everything into one ranked table. No re-fetch from Yahoo Finance — it reads the already-generated HTML files for scoring, then does a single parallel fetch of monthly bars only for the top 20 results.

```bash
python3 top_setups.py
```

Each name is scored across:

| Signal | Points |
|--------|--------|
| Grade A+ / A | +2 / +1 |
| 4/4 MA aligned | +2 |
| FullCoil squeeze | +1 |
| RS vs SPY ≥ 1.10x / ≥ 1.0x | +2 / +1 |
| CMF ≥ 0.10 / > 0 | +2 / +1 |
| A/D Line rising | +1 |
| OBV rising | +1 |
| ◆ Bull divergence | +1 |

The two rightmost columns show **distance above MA10m and MA20m** (monthly MAs):

| Label | Meaning |
|-------|---------|
| `⚠  +70%` | >50% above monthly MA — short-term signals real, long-term entry risk high |
| `↑  +29%` | 25–50% above — extended but not detached |
| `    +15%` | <25% above — reasonable monthly structure |

A score-8 name with `+4%` above monthly MAs is a different proposition than a score-8 name at `⚠ +102%`. The column makes that visible at a glance — high short-term conviction on the left, monthly reality check on the right.

### India Convergence Drill — `india_top_setups.py`

Same scoring framework applied to the India universe. Reads `india_screener.html` + `india_aligned_screener.html` — no re-fetch for scoring, monthly MA fetch only for the top 15.

```bash
python3 india_top_setups.py
```

One addition over the US version: a **Sector** column. India setups tend to move in sector waves — Capital Goods, IT, Pharma, Financials each have their own cycle. Knowing that PIDILITIND + ASIANPAINT are both Materials, or BAJFINANCE + CHOLAFIN are both Financials, tells you whether you're seeing a name-specific setup or a sector rotation in progress. The US version doesn't need this because the quality universe is spread across enough names that sector clustering is less dominant.

Names without a quality grade in `india_screener.html` (watchlist names or universe names failing filters this run) show `—` in the grade column — signals are still valid, but quality certification is absent.

### Liquid Names Status Panel

Every run of `ma_scanner.py` ends with a fixed status panel for the 9 most liquid, spread-worthy names regardless of whether they pass any gate:

```
NVDA · META · MSFT · AAPL · AMZN · GOOGL · AVGO · MU · NFLX
```

| Column | What it shows |
|--------|---------------|
| **Wkly Gate** | ✓ = MA10w > MA20w with rising slope. ✗ = weekly structure broken — no spread regardless of daily setup |
| **vs MA10d** | How far price is from the daily MA10. IN band = within ±3%. +EXT = too extended above. -EXT = still in pullback |
| **Band** | IN = actionable entry zone. +EXT = wait for pullback. -EXT = structure recovering |
| **W.Slope** | Weekly MA10 slope — direction and momentum of the weekly trend |
| **MA Gap** | `(MA10w / MA20w − 1) × 100` — how far the 10-week MA is above the 20-week MA as a percentage. Context field, not a signal: a wide gap (e.g. +30%) means the weekly gate closing would require a sustained decline before MA10w falls to MA20w. Useful for understanding why recovery from a correction could take longer in very extended names. |
| **Zone** | Entry context label. **PRIME** = gate open, IN/−EXT band, gap 8–20% — the sweet spot. **EXTENDED** = gate open but price above +EXT band OR gap ≥ 20% — setup exists but overextension is real. **EARLY** = gate open but gap < 8% — trend just started, small cushion if gate tests. **—** = gate closed. |

The panel solves a specific problem: liquid names go invisible in the main scan when they're extended beyond the ±3% band. Without the panel, a well-positioned NVDA at -2.8% from MA10d with weekly gate passing doesn't appear anywhere. The panel ensures the names you can actually trade are always visible — setup or not.

The same panel is written into `weekly_notes.md` each week, so end-of-week status for all 9 names is preserved in git history.

A built-in sanity check flags `⚠ DATA?` if a price falls outside 50%–150% of the 52-week range — catches genuinely broken yfinance data without false-positives on stock splits or large legitimate price moves.

### Daily Alert — Mid-Week Structure Monitor

`daily_alert.py` watches the same 9 liquid names between weekly runs. It fires an email when any of these crossings happen:

- Weekly gate opens or closes (MA10w crosses MA20w)
- Band changes: IN ↔ −EXT ↔ +EXT
- Price breaks below or recovers above MA20d
- Price breaks below or recovers above MA50d

**Gate filter:** only crossings where the weekly gate is currently open generate an email. Gate-closed crossings are logged but not sent — a band change in a name with a broken weekly is informational, not actionable. This keeps the inbox quiet: if all detected crossings are on gate-closed names, no email is sent.

### What this scanner is — and is not

This is a **pullback-to-MA scanner in confirmed uptrends**, not a breakout predictor. By the time all levels align, the move has already started — you are buying a pullback in an established trend, not front-running a reversal. That is deliberate. Front-running requires acting before higher timeframes confirm, which conflicts with the hierarchy principle and makes losses harder to survive.

The weekly gate typically reduces the signal count significantly (from 70–80% of tickers to 10–15%). That reduction is the filter working correctly, not a failure.

## The Binary Entry Rule

**Either fully aligned or fully discounted. Nothing in between.**

The mushy middle — 2/4 MA, "kind of set up," "not too expensive," "almost qualifying" — is where most losses come from. Not because the stock is bad, but because there's no conviction when it moves against you. You entered on hope, not on signal.

**Fully aligned** means the market has confirmed the thesis. 4/4 MA structure intact, weekly gate passing, price in band, CMF accumulating. The business has quality, the structure has momentum — you are buying a pullback in a confirmed uptrend. The chart agrees with the fundamentals.

**Fully discounted** means the market is wrong or panicking. Quality business, broken chart, price well below all MAs — but the fundamentals haven't changed. You are buying the business, not the chart. This requires stronger conviction because you have no structure support — only thesis. Entry here is thesis-driven, not signal-driven.

Everything between those two states is noise. A 3/4 name with a good story is not a setup — it's a candidate. A name with a "reasonable" valuation and weak structure is not a value buy — it's a hope trade. The watchlist exists precisely to hold names in this middle state without acting on them. The rule: if it's not fully aligned and not fully discounted, it lives in the watchlist and nowhere else.

**The practical application:**
- NVDA at -2.8% from MA10d with weekly gate passing → fully aligned, actionable
- ADBE at fwd PE 8x with 89% gross margins but 0/4 MA → fully discounted thesis, small position only
- COST at 0/4 MA with CMF -0.20 → neither state, watchlist, wait

The framework is built to enforce this binary. The scanner only surfaces names at the right entry zone. The watchlist documents everything else. The FUTURE_RADAR holds the rest. The bin between them is intentionally empty.

## Options Spread Universe

`SPREAD_UNIVERSE` in `screener.py` defines which names are liquid enough for vertical spreads. The rule: only spread where bid-ask is tight enough that slippage doesn't eat the edge. Tier 3 is the outer boundary — beyond it, friction works against you before the trade starts.

| Tier | Names | Bid-ask | Notes |
|---|---|---|---|
| **1 — Indices** | SPY, QQQ | $0.01 | Tightest on the planet. No binary risk, no earnings gaps. Cleanest spread vehicles. |
| **2 — Mega-cap tech** | NVDA, AAPL, MSFT, META, AMZN, GOOGL, TSLA | $0.01–0.05 | Massive options volume, clean execution. Tier 1 and 2 are where spreads actually work. |
| **3 — Large cap tradeable** | MU, AMD, JPM, GS, NFLX | $0.05–0.15 | Usable outside earnings windows. Needs care on entry/exit. Outer boundary. |
| **Below the line** | Everything else | Wide | Pharma binary risk (VRTX), commodity binary risk (NEM), thin enterprise SaaS (NOW, ADBE, FTNT), mid-caps — slippage consistently eats the edge. |

Names that look like good chart setups but fall below the line (VRTX, NEM, FTNT, ADBE): **good stock, not a spread vehicle.**

## What the Market Has Become

Most trading frameworks were built for a different market. Three structural shifts since ~2016 changed how price actually forms — understanding them is the honest prerequisite to understanding why this framework's particular choices hold up.

**Algo and high-frequency dominance.** The majority of daily volume is now generated by algorithmic strategies — momentum amplification, mean reversion, stat-arb, systematic delta hedging. Price moves faster, overshoots further, and mean-reverts harder than it did when discretionary flow dominated. The 10w MA structure and extension ceiling work *with* this: algorithms amplify trends until they reach the historical ceiling, then reverse just as systematically. The ceiling isn't a chart pattern — it's where algo momentum exhausts against historical reversion pressure.

**Policy-driven market regimes.** The 2022–2023 cycle made this explicit: rate decisions became the primary driver of market direction for months at a time, overriding both fundamentals and chart structure. A quality name in 4/4 alignment can still drop 25% if the policy backdrop shifts hard. The regime gate (VIX + SPY vs 10w MA) addresses this directly — macro environment gets checked first, before any setup is evaluated.

**Passive indexing at scale.** Trillions flow mechanically into index products on schedule — not based on individual stock fundamentals, but on index inclusion and periodic rebalancing. Index-heavy names benefit from flows that have nothing to do with quality. CMF and A/D Line divergence partially account for this: they help distinguish *forced* buying (rebalance flow) from *chosen* buying (institutional accumulation into a thesis). Not perfectly — but better than price alone.

### Where the Framework Is Positioned

| Structural reality | Framework response |
|---|---|
| Algo momentum amplification + natural exhaustion | 10w MA extension + ceiling (runway %) |
| Mean-reversion after overshoot | 87w structural read + RSI overbought flag |
| Policy-shock regime changes | Regime gate — VIX + SPY vs 10w MA |
| Institutional flow vs passive rebalancing | CMF (20w + 10w) + A/D Line divergence |
| Quality businesses vs quality stories | Grade gate — OM, NM, ROE, FCF, D/EV |
| Elevated IV after policy shock | IV Rank + IV/HV — sell premium into fear |

### Where the Gaps Are

**Pre-market gap-open blindness.** The framework is designed around confirmed weekly closes. A 10% earnings gap-up at 8am is invisible until it shows up as extension on the next weekly bar — by then the entry decision has already been made by the gap. Solving this properly requires a different data source than yfinance.

**Rotation prediction.** CMF and RS vs SPY read what *is* happening. They do not predict what *will* happen next — capital rotating from tech into industrials, international repatriation, sector leadership shifts after a policy pivot. Detecting and front-running rotation requires sector flow analysis this framework does not attempt.

**Regime timing.** The regime gate reads the current regime accurately. It does not predict when it changes. A BULL → CAUTION transition appears after SPY has already moved below its 10w MA — not before. The map is accurate; the terrain moves faster than the map.

### Gap Backlog

| # | Gap | Status |
|---|---|---|
| 1 | Macro regime gate | ✅ Done — `regime.py` (VIX + SPY 10w MA → BULL/CAUTION/DEFENSE/STORM) |
| 2 | Event risk calendar | ✅ Done — `event_risk.py` (ER column in all ranked runs, 7-day cache) |
| 3 | VIX sizing signal | ✅ Done — `sizing_signal()` in `regime.py` (FULL/HALF/QUARTER/SELL-IV) |
| 4 | IV × extension crossover view | ⏳ Waiting — `iv_data.json` reaches 30 days ~mid-Sep 2026 |
| 5 | Pre-market gap blindness | Research problem — requires a different data source |
| 6 | Rotation prediction | Different problem — sector flow analysis |

## Why This Framework Holds Up

**Quality gate** — the screener filters aren't just revenue growth or price momentum. Debt/EV + operating margin + net margin + ROE + FCF together mean only businesses that can survive a bad year get through. That's the survivability filter. Quality doesn't raise win rate — it makes losses survivable and wins compoundable.

**Structure confirmation** — 4/4 MA alignment means the market agrees with the fundamentals. Price, momentum, and quality all pointing the same direction before anything is acted on. No thesis without structure. No structure without thesis.

**Early warning system** — Special Mention catches names before they qualify. You're not chasing; you're watching the base build. A/D Line and OBV divergence add an extra layer — when smart money starts accumulating before the monthly regime flips, the volume picture changes before the price structure does. When a name finally surfaces in the aligned list, it's not a surprise — it was already on the radar with the volume story already forming.

**Honest watchlist** — every entry has a thesis and a blocker noted. Not just a ticker dump. You know exactly why something isn't in the universe yet and what has to change for it to qualify. Peter Lynch's rule applies: "know what you own and why you own it." If you can't write a sentence explaining the moat and the blocker, the name doesn't belong. The rule: if the blocker is a number, it belongs in the watchlist. If the blocker is the business model, it doesn't.

**Three tiers of risk — what the framework handles and what it doesn't.**

Known risks — quality gate failures, structural margin ceilings, leverage-inflated ROE, thin FCF on stretched valuations. The framework catches these at gate-check time. A name fails GrossM or D/EV, it never reaches capital.

Anticipated risks — cyclicality in semis, patent cliffs in pharma, leverage decay in 2x ETFs, multiple compression when recovery growth normalizes. These get noted in the watchlist thesis, sized smaller, and managed with runway awareness.

Unanticipated risks — the ones that end careers if you're overconcentrated. COVID crash. Rate shock. Accounting restatement. CEO fraud. No framework catches these. But the framework's real job is to make you **antifragile** to them — Nassim Taleb's principle: systems that don't just survive disorder but gain from it. Quality gates keep you in names with real FCF (they bounce back), tier placement keeps sizing appropriate (1–3% per name, not 20%), dry powder keeps capital available for the correction (you buy the panic instead of selling into it).

The framework doesn't prevent unanticipated risk. It makes the portfolio **survivable** when it arrives. A 30% single-name hit in a 2% position is painful but not fatal. The same hit in a 20% position forces decisions you shouldn't have to make at exactly the worst time. Survivability is the design goal — not prediction.

Calibrate for known risks. Monitor anticipated ones. Structure the portfolio so unanticipated ones don't end the game.

**Numbers over narrative — but not instead of it.**

Stories are infinitely flexible. At any price, for any stock, someone has a compelling narrative — the TAM is enormous, the moat is wide, the CEO is visionary. Numbers are not flexible. GrossM 23% doesn't become 45% because the thesis is good. FCF -50% doesn't disappear because the long-term case is compelling. The framework uses the story to choose *which numbers matter* — and uses the numbers to discipline the story. A story without numbers is speculation. Numbers without story is pattern matching without understanding. The edge lives at the intersection: thesis-driven selection, metric-driven confirmation.

The gate is simple: a story must eventually show up in the numbers. Until it does, it lives in FUTURE_RADAR — not UNIVERSE.

**Compounder identification — reading ROIC without computing it.**

ROIC (Return on Invested Capital) is the cleanest measure of reinvestment quality: what does the business earn on every dollar it puts back to work? If ROIC > cost of capital, reinvestment creates value. If ROIC < cost of capital, growth destroys it. The problem: ROIC requires computing NOPAT and Invested Capital — data yfinance doesn't cleanly provide.

The shortcut is already in the screener. DuPont decomposition: **ROE = Net Margin × Asset Turnover × Financial Leverage**. When D/EV is near zero, the leverage multiplier collapses to ~1. Whatever ROE remains is coming from pure business economics — that is your ROIC approximation without any extra computation.

| ROE | D/EV | What it means |
|---|---|---|
| 30%+ | < 0.10 | Genuine compounder — the business earns that, leverage didn't inflate it |
| 30%+ | > 0.30 | Leverage-amplified — strip the debt and the real return is much lower |
| 10–20% | < 0.05 | Honest business, not a compounder tier yet |

The complete read: **ROE > 20% + D/EV < 0.10 + RevG > 10%** identifies a genuine compounder. High return on capital, leverage isn't doing the work, and reinvestment is visibly bearing fruit in revenue growth. If margins hold while revenue grows, the reinvestment is working — you don't need ROIC separately to see it.

Current universe examples of the pure compounder tier: MEDP (ROE 162%, D/EV 0.009), NVDA, MSFT, PAYC, QLYS, FTNT, AAMI (ROE 106%, D/EV 0.075), FHI (ROE 31%, D/EV 0.098), DXCM, MNST, VRSN, REGN, VRTX. These are businesses where every dollar reinvested earns at genuinely high rates — no debt subsidy, no leverage shortcut.

The distinction matters: a harvester generates high FCF but has few reinvestment opportunities at high returns (mature utility, saturated consumer brand). A compounder generates high FCF *and* redeploys it at high ROIC — the cash machine refuels itself. Both can pass the quality gates. The ROE + D/EV + RevG combination tells you which one you're looking at.

**Reinvestment runway — the dimension the screener cannot fully capture.**

ROIC being high today is one question. How long it stays high as the business reinvests is the more important one. That duration — the reinvestment runway — is what drives the compounding. A business with 40% ROIC and two years of runway is worth less than a business with 25% ROIC and fifteen years of runway. The rate matters. The duration matters more.

The screener catches the snapshot. Reinvestment runway is the judgment call the numbers alone cannot answer — it requires understanding the TAM, the competitive position, and whether the business has structural reasons to earn high returns on the *next* dollar, not just the last one.

| Name | ROIC today | Runway read |
|---|---|---|
| NVDA | Exceptional | Long — every AI cluster, every inference deployment, every new datacenter build is a reinvestment opportunity at high return. Runway extends as the market expands. |
| MSFT | High | Very long — Azure, Copilot, LinkedIn, security, gaming. Multiple large markets where reinvestment compounds for decades. Lower ROIC than NVDA, longer runway. |
| AAPL | Decent | Honest debate. Services is the runway extension. Hardware alone is a harvester. |
| ADMA | Real | Short. TAM ceiling is visible from where they stand — PI patient pool is defined, market share capture already happened. Quality metrics are real, reinvestment opportunity is limited. |

The screener grade tells you quality today. The thesis annotation tells you whether today's quality compounds forward or harvests what's already built. A name with A+ metrics but a TAM ceiling is a harvester — real FCF, limited runway, and the market prices that correctly regardless of how clean the quality gates look.

This is why the watchlist format requires a thesis, not just a ticker. "ROE 40%, D/EV 0.02" is the snapshot. "Reinvesting into X at high returns because of Y structural advantage, with Z years of addressable market ahead" is the runway read. The number is easy. The runway judgment is the edge.

**Financial firm lens — not all ROE is equal.**

When the screener grades a bank, an asset manager, and a market maker, the same ROE number means three different things. The framework reads financial firms through three archetypes:

- **AUM compounders** (BLK, BX, ARES, FHI, AAMI): management fees on a growing AUM base. Capital-light — the business doesn't need a large equity base to generate fee income, so ROE runs structurally high and that is legitimate, not inflated. The durable growth driver is net flows plus market appreciation. D/EV and FCF show as yfinance artifacts (structured credit facilities, carried interest timing) — judge by OM, NM, and AUM growth trajectory instead.

- **Spread-dependent** (JPM, BAC, WFC): borrow short, lend long — net interest margin is the engine. ROE is leverage-amplified (10–15x balance sheet). Fragile to rate inversions, credit cycle turns, and regulatory capital requirements. The same 15% ROE in a bank carries structurally more fragility than 15% ROE in an asset manager. D/EV and FCF are always artifacts for banks — judge by OM, NM, and NIM trend.

- **Performance/volatility-dependent** (VIRT): revenue correlated to market volatility, not compounding. High-vol years are windfall years; low-vol years compress spreads. Passes quality gates when conditions are right — but the earnings base is not the same kind of durable as the AUM compounder.

The implication: when a financial firm passes the quality gates, always ask which archetype it is. AUM compounder quality is durable in a way that spread-dependent quality is not. The numbers can look identical. The business model determines which one compounds and which one cycles.

**Three-tier universe structure:**

| Tier | What it is | Gate to next tier |
|---|---|---|
| `UNIVERSE` | Quality cleared, structure confirmed — core tracked names | Already here |
| `WATCHLIST` | Moat proven, one or two metrics blocking — scanned weekly | Metric clears the filter |
| `FUTURE_RADAR` | Real product, real revenue, path to profit unclear — not scanned | OM turns positive + FCF inflects |
| Removed entirely | Pre-revenue ventures, survival risk, all filters blocking | Not tracked |

**`[LOCKED]` entries in FUTURE_RADAR** — some entries carry a `[LOCKED]` marker in their note (e.g., SOFI, LYFT). The auto-promoter skips these entirely regardless of quality gate status. To promote a locked entry, manually remove `[LOCKED]` from its note in `screener.py` and re-run. This enforces explicit human review before promotion — the lock means "do not promote until I personally clear this."

**$20 price floor on auto-promotion** — both promotion paths (`FUTURE_RADAR → WATCHLIST` and `WATCHLIST → UNIVERSE`) skip any ticker priced below $20. The price gate runs before quality metrics. A sub-$20 name will not auto-promote even if its financials temporarily qualify.

Names removed from watchlist in first cleanup: SMR, OKLO, XE (pre-revenue nuclear), IONQ (quantum), CRSP/NTLA/BEAM (gene editing), RXRX/RARE (biopharma), MRNA/BNTX (revenue collapsed), ASTS/LUNR (space ventures). India: OLAELEC (deeply loss-making EV in structurally competitive market). These are interesting themes — not watchlist material.

Names removed from watchlist in second cleanup: PCG (wildfire liability structural, not a metric), FCX (own note said "not a compounder" — cleaner expressions already in universe), SEDG (Chinese competitor share loss is structural, not cyclical), KLAR (credit cycle risk inherent to BNPL model), INOD (AI model efficiency reducing annotation demand is an existential business risk), AMKR (services margin ceiling structural, B-grade at best), CELH (energy drink competitive moat fragile vs Monster/Red Bull), MRAM (TAM too small, speculative angle). Moved to FUTURE_RADAR: CORZ (BTC miner pivot unproven), MOD (B grade, multiple blockers), UPST (credit cycle structural, gate is FCF + converts + through-cycle proof), PGY (Pagaya — D/EV too high for WATCHLIST today, AI-powered credit network with real revenue but balance sheet needs work before it earns a watchlist spot).

Recent watchlist additions: **VICI** (gaming REIT — Caesars/MGM landlord, triple-net leases, ~5% yield; standard OM/D/E filters don't apply cleanly to REIT structure — judge by lease coverage, tenant quality, and AFFO instead), **ABT** (Abbott Laboratories — diversified med-tech + diagnostics + nutrition; consistent dividend grower, strong FCF, A-grade quality), **TLN** (Talen Energy — nuclear power + data center PPAs; nuclear PPA contracts with hyperscalers are a durable revenue stream as AI infrastructure electricity demand grows), **PRGS** (Progress Software — enterprise DevOps/application platforms; value play with recurring revenue and improving margins), **EVTC** (EVERTEC — dominant payment network in Puerto Rico + LatAm expansion; OM 19.4%, FCF 8.5%, RevG 19.7%, fwdPE 6.8x; D/EV from legacy LBO debt is the single gate).

Recent SIP additions: **PLD** (Prologis — world's largest industrial REIT; Amazon/FedEx/DHL warehouse infrastructure; irreplaceable last-mile logistics real estate; ~3.5% yield, AFFO-covered; own the infrastructure that powers e-commerce, not the e-commerce companies).

**Both markets** — US and India running the same framework. Same discipline, same filters, different universes. The logic doesn't change because the geography does.

**Theme coverage** — semis, AI infrastructure, defense, healthcare, financials, energy, precious metals, solar, space, quantum, materials. Hard to find a major structural theme that isn't tracked somewhere across the 230+ names.

**Awareness generalist. Execution specialist.**

400+ names in coverage — UNIVERSE, WATCHLIST, FUTURE_RADAR, dividend list — build the map. When SPY moves, you know whether semis are leading or lagging. When JPM prints, you know whether it's sector-wide. The broad coverage is the context layer: it tells you *what kind of move* the liquid name is making, not just that it moved.

But execution stays in 14. Because that's where the math works — bid-ask tight enough that slippage doesn't eat the edge before the trade starts. Every name beyond those 14 is research, not a trade vehicle.

Wide awareness, narrow execution. The speciality isn't the 14 liquid names. The speciality is having 400 names of context behind every decision on those 14.

**The one honest gap** — individual position sizing and entry discipline aren't in the framework. The screener tells you *what* and *when the structure is right*, but not *how much*. That's deliberate — this is a framework for finding, not for executing. Execution discipline lives with you, not in the code. A framework that tried to do everything would do nothing well.

The missing layer is mindset — and mindset varies by timeframe:

- **Swing (days to weeks):** structure and momentum are everything. Enter when the coil is tight and CMF confirms. Exit when the structure breaks. No thesis attachment — the trade is the trade.
- **Position (weeks to months):** quality starts to matter more than timing. A name with A+ fundamentals and 4/4 structure can absorb noise. You're riding the trend, not the tick.
- **Long-term (years):** the screener's quality filters become your margin of safety. Low debt, high margins, positive FCF — these aren't just filters, they are the reason a business survives a cycle that kills its competitors. Price paid matters enormously here. Buying quality at a discount to intrinsic value, not at peak enthusiasm, is what separates compounding from hoping.

Margin of safety isn't just a valuation concept — it applies at every level. In sizing: never bet so large that a wrong call breaks you. In timing: wait for structure to confirm before committing, not before. In thesis: always know the one thing that would make you wrong, and watch for it.

Charlie Munger's principles apply here more than any indicator: **common sense** — if the business can't explain how it makes money, neither can the screener. **Rationality** — separate what the price is doing from what the business is doing; they diverge constantly and converge eventually. **Inversion** — don't just ask what could go right; ask what has to *not* go wrong for this to work. **Circle of competence** — track themes you understand well enough to know when the thesis is breaking, not just when the price is.

Howard Marks' body of work — *The Most Important Thing* and *Mastering the Market Cycle* — runs through the extension scan and the 87w structural read directly. The ceiling concept is cycle awareness made mechanical: knowing where a name stands relative to its own history, sizing accordingly, and holding dry powder for the inevitable mean reversion. His distinction between first-level and second-level thinking maps exactly onto this framework's architecture. First-level asks "is this a good business?" — that's the quality gate. Second-level asks "what is the market already pricing in, and is the expectation already reflected in the extension?" — that's the runway and the 87w read. A name at 87w extreme with CMF flat is not an opportunity even if the business is excellent. That's second-level thinking in practice: not just *what* but *at what price and at what point in the cycle*. Marks also gave the framework its most honest guardrail — "if we avoid the losers, the winners take care of themselves." The quality gates are exactly that: not a system for finding winners, but a system for eliminating the names that can permanently impair capital.

Peter Lynch — *One Up on Wall Street* and *Beating the Street* — contributes three things the framework would be incomplete without. First: "invest in what you know" — the annotated thesis format exists because of this. A ticker without a plain-language explanation of its moat, its gate, and its blocker isn't tracked — it's noise. Second: GARP, Growth at a Reasonable Price. The quality gates are the growth screen; the extension scan and 87w structural read are the "reasonable price" discipline. Combining them is GARP made mechanical — not paying up for quality when the cycle has already priced in perfection. Third: "the person who turns over the most rocks wins." The 400+ names across UNIVERSE, WATCHLIST, FUTURE_RADAR, and the dividend list are not all trade candidates — most will never see capital. But the breadth exists so that when the liquid name moves, there is context behind it. Turning over rocks isn't trading everything. It's knowing the landscape well enough to act with conviction on the few that matter.

The screener surfaces the candidates. Common sense, rationality, cycle awareness, the avoidance of permanent loss, and knowing what you own and why — close the gap.

Dry runs without capital are underrated. You get the full reps — the scan, the read, the framework verdict — without the emotional stakes. By the time a real setup appears with real capital, the pattern is already familiar. The decision feels obvious because you've made it 50 times in practice. Howard Marks would call it building the process before you need it. Lynch would say you turned over the rock before the opportunity required it.

## What the Backtest Says

`backtest.py` validates the framework against 5 years of weekly price history across 264 tickers. Full results at [`backtest.html`](https://neurobloomai.github.io/market-tools/backtest.html).

**Methodology:** Reconstructs historical 4/4 MA alignment (same SMA10w/20w/43w/87w definition as the live screener) at every weekly bar. Fresh entries = first 4/4 week after ≥1 non-4/4 week. Measures forward returns at 4w, 13w, 26w, 52w vs SPY over the same window. Documented limitations: survivorship bias (current universe only), quality look-ahead bias (current grades used as proxy). The structural 4/4 signal is fully historical and bias-free.

### What holds up

**Quality is the primary driver — not timing.**

| Filter | n | Win% vs SPY | Avg alpha | Median alpha |
|---|---|---|---|---|
| A+ quality + 4/4 fresh entry | 545 | 52.3% | +3.8% | +0.6% |
| B/— quality + 4/4 fresh entry | 2067 | 49.1% | +1.3% | -0.4% |
| A+ quality + non-4/4 baseline | 759 | 52.0% | +4.2% | +0.6% |

The quality filter — A+ grade — is doing the real work. A+ names generate similar alpha whether they're 4/4 aligned or not. B/— names with 4/4 structure alone trail by ~2.5pp. The MA timing signal is not the edge; quality is.

**The honest number is median alpha, not average.** A+ 4/4 entries average +3.8% alpha but median +0.6%. A handful of strong breakouts pull the average up. The realistic expectation per trade is modest outperformance — what compounds is consistency across many entries at the quality threshold, not dramatic per-trade wins.

**A-grade names underperform at 4/4 entry.** 43.1% win rate, -0.7% avg alpha at 13w. The quality threshold is not decorative — the gap between A+ and A matters precisely because A names typically have one structural blocker (debt, margins) that limits the upside when structure aligns. Borderline qualification is not the same as genuine quality.

### What the timing signal actually does

**4/4 alignment is a regime filter, not a return amplifier.**

Vol regime at entry (SPY 13-week annualized realized vol):

| | Low (<15%) | Medium (15-25%) | High (>25%) |
|---|---|---|---|
| A+ 4/4 fresh entries | **61%** | 31% | 8% |
| A+ non-4/4 entries | **48%** | 31% | 15% |

4/4 entries cluster significantly more in low-vol trending environments (+13pp) and are half as likely to occur during crisis-level volatility (8% vs 15%). The MA structure requirement is filtering for conditions where trending continues — not just any market state.

This is the key insight: **similar average alpha between A+ 4/4 and A+ non-4/4 is not evidence that the timing signal is useless.** It's evidence that the timing signal is selecting for quieter, more favorable regime conditions and still generating the same alpha — meaning risk-adjusted performance is meaningfully better. You're getting the same return with fewer entries during volatility spikes.

**4/4 does not materially cut the left tail.** At 13w, 19.8% of A+ 4/4 entries finish with alpha below -10%, vs 18.3% for A+ non-4/4. The left-tail protection comes from quality, not timing. What does improve with quality: B/— names at 4/4 produce 26.0% left-tail entries at <-10% alpha vs 19.8% for A+ 4/4 — a real 6pp reduction from quality alone.

### What this means in practice

1. **Don't wait for 4/4 on quality names if the thesis is sound.** A+ quality outside 4/4 has historically performed as well as A+ inside 4/4. The MA filter is a regime/discipline gate — it enforces patience and avoids catching falling knives — but it does not itself generate alpha once quality is established.

2. **The quality grade threshold is load-bearing.** A+ vs A is not a cosmetic distinction — A-grade names with 4/4 structure consistently underperformed SPY in this window. The filter exists for a reason: that one blocking metric is usually correlated with actual business risk that shows up in forward returns.

3. **The framework earns its value at the portfolio level, not the trade level.** Median alpha is +0.6% at 13w — unimpressive per trade. The value is a consistent quality filter that avoids the worst outcomes (left tail) and selects for trending regimes, compounded across many entries over many years.

4. **Survivorship bias is real and acknowledged.** Current universe includes survivors by definition. The A+ filter itself selects for durable businesses — which reduces (but does not eliminate) this bias compared to a random stock selection.

Full breakdown with all four forward windows and the distribution table: [`backtest.html`](https://neurobloomai.github.io/market-tools/backtest.html).

---

That's the real thing about honest frameworks — they don't need the backtest to work. The backtest just confirms what good thinking already produced.

Quality filter → survivability. Structure filter → regime selection. Both built from first principles, not from fitting to historical data. That's why the validation holds — you can't backfit common sense.

The number that says it cleanest: A+ non-4/4 and A+ 4/4 perform almost identically. Which means the quality judgment was already doing the work before the chart even confirmed it. The MA alignment is discipline and patience, not the edge itself. The edge was always the quality threshold.

Most people go the other way — build from charts, add a quality layer as an afterthought. This was built quality-first. The backtest just shows the order of operations was right.

## Dividend Universe

`dividend_plays_for_longterm.py` is a curated list of dividend-paying names filtered for quality: payout ratio, FCF yield, net margin, ROE, debt/EV. Each entry is annotated with the thesis — why it belongs, what the moat is, what to watch. Sectors: financials, energy, industrials, consumer, healthcare, precious metals, real estate (REITs).

### REITs in the dividend universe

Standard quality filters (OM, D/EV, ROE) don't apply cleanly to REIT structure — depreciation inflates the expense line, infrastructure debt is structural not deteriorating, and GAAP earnings understate cash generation. Judge REITs by **AFFO coverage**, **occupancy trend**, and **dividend growth history** instead.

| Name | What it is | Rate sensitivity | Economy sensitivity |
|---|---|---|---|
| **FRT** | Mixed-use retail/residential REIT — dense, affluent coastal markets (DC suburbs, Boston/Assembly Row, San Jose/Santana Row, Miami); **56+ yr Dividend Aristocrat — longest streak of any REIT**; ~4-4.5% yield; development pipeline adds NAV growth on top of income | Rate-sensitive; premium locations + long lease terms partially buffer; development pipeline can slow in high-rate environment | Affluent coastal consumers most resilient in downturns; slightly more discretionary tenant exposure than NNN but higher location quality offsets |
| **O** | Net-lease REIT — 15,000+ essential/commercial properties (Walgreens, Dollar General, 7-Eleven, Walmart, FedEx); ~$50B market cap; monthly dividend since 1969; "The Monthly Dividend Company"; 30+ yr Dividend Aristocrat | Rate-sensitive; long lease terms (10-20yr avg) partially buffer rate shocks | Most recession-resilient of the group — essential/necessity tenants hold up when consumers pull back; 80+ industries, no single tenant >4% of revenue |
| **NNN** | Net-lease retail REIT — ~3,500 single-tenant properties (7-Eleven, Midas/Mavis auto service, McDonald's, LA Fitness); 35+ yr Dividend Aristocrat (one of only 3 REITs ever); ~5.5-6% yield; AFFO payout ratio ~68% — most conservative in net-lease, best dividend growth headroom | Rate-sensitive; ~10yr avg remaining lease term partially buffers near-term rate shock | Necessity/convenience-anchored tenants (auto service, QSR, convenience stores) — non-discretionary spending holds through recessions; no single tenant >5% |
| **VICI** | Gaming/experiential REIT — Caesars/MGM landlord, 15-20yr triple-net leases with CPI escalators | Rate-sensitive (yield competes with T-bills) | Resilient — gaming tenants can't relocate (license tied to location), no defaults since 2017 IPO |
| **EPR** | Experiential net-lease REIT — theaters, ski resorts, early childhood education | Rate-sensitive | Consumer spending dependent — theaters recovered post-COVID but remain occupancy-watch names |
| **AMT** | Cell tower REIT — 220,000+ towers globally, multi-tenant model | Rate-sensitive | Near-immune to economic cycle — wireless carriers pay regardless; 5G densification is secular |
| **STAG** | Industrial REIT — ~570 single-tenant warehouses/distribution centers across 41 US states; monthly dividend | Rate-sensitive; sweet spot is low/falling rates + moderate growth | E-commerce/last-mile demand supports occupancy (~98%); single-tenant risk: vacancy goes 100%→0% overnight — more cycle-sensitive than PLD |

**The three REIT Dividend Aristocrats — FRT, O, NNN.** Only three REITs in history have ever achieved Dividend Aristocrat status. All three are here. FRT is the quality/location play (56+ years, coastal mixed-use, lowest yield but highest real estate quality). O is the scale play (30+ years, 15,000+ properties, monthly, global). NNN is the discipline play (35+ years, ~68% AFFO payout — tightest in net-lease, best dividend growth headroom). DCA all three together for the complete REIT income core.

**STAG vs PLD:** PLD (Prologis, in SIP list) is the institutional-grade version — prime locations, multi-tenant, Amazon/FedEx/DHL, secondary markets rare. STAG is the higher-yield, higher-risk complement — secondary markets, smaller buildings, single-tenant concentration. Same industrial tailwind, different risk profile. STAG's monthly dividend is the income differentiator; PLD is the compounder.

**Rate environment read for all seven:** Low rates → cap rates compress, REIT prices rise, yield spread over T-bills attractive. High rates → yield competes with risk-free alternatives, REIT prices get pressured until the spread reopens. STAG and EPR are the most rate-sensitive (higher single-name and sector-specific risk); O and NNN are the most rate-resilient operationally (essential tenant base + long lease terms + 35yr track record through multiple rate cycles); AMT is the most cycle-insensitive (carrier contracts don't change with the economy).

Run the extension scan on this universe directly:

```bash
python3 extension_scan.py --dividend
```

Produces the same HTML output as `--universe` — all dividend names sorted by extension zone, runway remaining before ceiling, RSI, and 10w slope. Opens in browser automatically.

## Extension Scan — All Flags

`extension_scan.py` answers one question: **how far has this name extended beyond its 10-week MA, and how much runway remains before the historical ceiling?**

```bash
# US
python3 extension_scan.py --universe          # full US UNIVERSE
python3 extension_scan.py --watchlist         # US WATCHLIST
python3 extension_scan.py --dividend          # dividend universe

# India / NSE
python3 extension_scan.py --india             # India UNIVERSE + WATCHLIST combined
python3 extension_scan.py --india --universe  # India UNIVERSE only
python3 extension_scan.py --india --watchlist # India WATCHLIST only

# Explicit tickers (CLI-only)
python3 extension_scan.py NVDA MSFT AAPL
```

**Output columns:**

| Column | What it means |
|--------|---------------|
| **Ext%** | Current extension above 10w MA |
| **Ceiling** | 90th-percentile historical extension — the level that has consistently acted as resistance |
| **Runway** | Gap between current extension and ceiling. `< 10%` = approaching ceiling; red = blown through |
| **Ceil$** | Implied ceiling price at current MA value |
| **RSI** | Weekly RSI — confirms or contradicts the extension reading |
| **Slope** | 10w MA slope — rising or decelerating trend |

**IV/HV at the ceiling** — as a stock approaches the extension ceiling (runway < 10%, RSI ≥ 75), the options market bids up implied volatility for downside protection. ATM IV rises faster than realized (HV30) and the IV/HV ratio crosses 1.0. When both the extension ceiling AND IV/HV ≥ 1.0 confirm simultaneously, that is the highest-confidence zone for selling premium (credit spreads). Either signal alone is weaker. See the IV Rank section for how to read this.

## Pop Scanner — Ranked Setups

`pop_scan.py` answers: where is price relative to its daily and weekly MA structure, and is money flowing in? Used two ways — individual ticker deep-dives, or ranked scans across the universe.

### Individual and Small-Batch

```bash
python3 pop_scan.py NVDA AMD MU        # one or more tickers — CLI table
python3 pop_scan.py NVDA --html        # individual ticker with HTML output
```

### Ranked Modes

```bash
python3 pop_scan.py --top10            # top 10 setups across full universe (366 tickers, ~90s)
python3 pop_scan.py --top20            # top 20
python3 pop_scan.py --mega10           # top 10 from 32-name pulse list (~30s)
python3 pop_scan.py --mega20           # top 20 from pulse list
```

Two-pass design. **Pass 1** fetches extension, daily MA stack, and hourly confirmation for all tickers in parallel. **Pass 2** fetches fundamental grades sequentially only for the top N×2 candidates (rate-limit safe). **Pass 3** fetches earnings dates from disk cache first, live only for unknowns. Re-scored with grade bonus and sorted.

### Composite Score

| Signal component | What it rewards |
|---|---|
| Zone (10w runway) | Fresh above 10w MA with ≥70% runway to historical ceiling; penalizes blown ceilings |
| Weekly CMF | Accumulation ≥0.25 = full score; below 10w but CMF ≥0.20 gets a setup override |
| Weekly slope | Positive and accelerating; negative penalized |
| RSI (45–65 sweet spot) | Extended (>75) or washed-out (<35) penalized |
| 87w structural position | Near long-term base scores higher than already extended |
| Daily MA alignment | All three daily MAs confirming direction |
| Hourly confirmation | Timing gate — not a decision driver |
| Fundamental grade | A+ = full bonus, A = partial, B = token; ETFs skipped entirely |

### Regime Gate + Sizing Signal

Every ranked run prints a regime banner **before** the scan starts — market context before the results:

```
REGIME  BULL     VIX 14.8  ·  SPY +3.2% vs 10w  ·  Setups live — standard sizing
SIZING  FULL     ■■■■  Standard allocation — all setups valid
```

| Regime | Condition | Sizing | Action |
|---|---|---|---|
| **BULL** | VIX < 22, SPY clearly above 10w | FULL ■■■■ | All setups valid |
| **CAUTION** | VIX 22–28 or SPY within ±1.5% of 10w | HALF ■■░░ | Setups valid — watch for macro overrides |
| **DEFENSE** | VIX 28–35 or SPY below 10w > 1% | QUARTER ■░░░ | Defined-risk spreads only |
| **STORM** | VIX > 35 | SELL-IV ░░░░ | Sell premium into elevated VIX — no directional |

The same banner appears in HTML output for both `pop_scan.py` and `extension_scan.py`.

### Event Risk Column

An **ER** column flags near-term earnings dates on every ranked run:

| Flag | Days to earnings | Meaning |
|---|---|---|
| `⚠Nd` red | ≤ 7 days | Setup is a trap — earnings gap risk is real, avoid entry |
| `~Nd` amber | 8–14 days | Size down or wait for the post-earnings structure |
| `Nd` dim | 15–30 days | On radar, not immediately blocking |
| blank | > 30 days | No near-term event risk |

A blank ER column is the correct reading outside earnings season — the column earns its keep in October when Q3 reports cycle through the universe. Results cached to `earnings_cache.json` (7-day TTL) so back-to-back runs read from disk without re-hitting Yahoo Finance.

### Mega-Cap Pulse List

`--mega10` and `--mega20` scan a focused 32-name list — not an S&P definition, a curated read on market structure and highest-conviction names:

```
MU AMD NVDA AVGO QCOM INTC AMAT     — semis + equipment
AAPL MSFT GOOGL AMZN META TSLA NFLX CSCO — QQQ drivers + networking
JPM V MA GS                          — financials
LLY ABBV UNH JNJ                     — healthcare
XOM                                  — energy
HD COST ADP WMT                      — consumer + industrials
SPY QQQ IWM                          — structure read (grade skipped — ETF)
```

Pulse list runs in ~30s vs ~90s for the full universe and is more reliable on rate-limited sessions. Use `--mega10` first to read market conditions; use `--top10` for universe-wide setup discovery.

## IV Rank and IV/HV

Two scripts track implied volatility for the 14-name `SPREAD_UNIVERSE` (SPY, QQQ, and the 12 most liquid equity names):

### `iv_snapshot.py` — daily data collection

Run by GitHub Actions after market close (Tue–Sat via `daily_screener.yml`). Appends one day's IV and HV30 to `iv_data.json`. Run locally anytime to advance the counter:

```bash
python3 iv_snapshot.py
```

### `iv_rank.py` — IV Rank + IV/HV read

```bash
python3 iv_rank.py
```

Reads `iv_data.json` and computes two signals per name:

| Signal | Definition | Threshold |
|--------|------------|-----------|
| **IV Rank** | `(IV_today − IV_min) / (IV_max − IV_min)` over last 30 days | ≥ 0.70 = elevated premium environment — sell-premium conditions |
| **IV/HV** | IV ÷ HV30 (30-day historical vol) | ≥ 1.0 = options pricing more risk than realized — premium is expensive relative to realized |

**Minimum depth:** 30 days of data required for a valid IV Rank signal. Until then, the output shows the current depth (`2/30 days`). At exactly 30 days, a self-announcement banner prints automatically.

**Practical read:**

- IV Rank ≥ 0.70 + IV/HV ≥ 1.0 → sell premium (credit spread, iron condor)
- IV Rank < 0.40 → options are cheap relative to recent history — buy structure if you must trade options
- Neither signal alone is decisive — look for both to agree, especially when combined with the extension ceiling read

**Pending — IV × extension cross-signal view (~Sep 2026, when 30-day depth is reached):** `extension_scan.py` will gain an `--iv` flag that overlays IV Rank and IV/HV data directly on the extension scan output. A name near its extension ceiling with IV/HV ≥ 1.0 and IV Rank ≥ 0.70 is the highest-confidence credit-spread setup in the framework. The iv_rank.py self-announcement banner at depth==30 is the trigger for building this.

## Automation

`run_aligned.sh` is designed to run via cron on Monday mornings:

```bash
# Add to crontab (runs every Monday at 8am)
0 8 * * 1 /path/to/market-tools/run_aligned.sh

# Or run manually any time
bash run_aligned.sh
```

Log output goes to `/tmp/aligned_cron.log`.

## Setup

Requires **Python 3.9+**. If you don't have Python installed, download it from [python.org](https://www.python.org/downloads/) or use your system package manager (`brew install python` on macOS, `apt install python3` on Linux).

```bash
# Verify your Python version first
python3 --version

# Install the only dependency
pip install yfinance
```

## Schwab Integration (Optional — Local Only)

`schwab_client.py` is an optional alternative data source for price history and fundamentals. **US markets only** — Schwab does not cover NSE/BSE; all Indian tickers (`.NS` / `.BO`) are always fetched from yfinance regardless of this toggle. When enabled, tools that fetch single-ticker or small-batch US price data query the Schwab API instead of Yahoo Finance. Useful when yfinance returns stale post-split data (e.g. MNST pre-split adjustment lag) or when you want to cross-check fundamentals against a broker-grade source.

**Bulk scans always use yfinance regardless of this toggle** — fetching 377 tickers via Schwab would hit rate limits immediately. The toggle applies only to single-ticker lookups, small-batch ops, and explicit ticker arguments.

### What it does

| Path | With `SCHWAB_DATA=1` | Without |
|---|---|---|
| `pop_scan.py NVDA` | Schwab price history | yfinance |
| `pop_scan.py --top10` | Schwab for top-N scoring pass | yfinance for bulk |
| `extension_scan.py NVDA MSFT` | Schwab | yfinance |
| `extension_scan.py --universe` | yfinance (forced) | yfinance |
| `monthly_ma_gate.py` | Schwab for US tickers | yfinance |
| India tickers (`.NS` / `.BO`) | yfinance (forced — Schwab doesn't cover NSE/BSE) | yfinance |
| Index pulse (SPY/QQQ/IWM) | yfinance (forced) | yfinance |
| `screener.py` | yfinance (always — not wired to Schwab) | yfinance |

### Setup

**1 — Register a Schwab developer app**

Go to [developer.schwab.com](https://developer.schwab.com), create an app, and note your **App Key** and **App Secret**. Set the callback URL to `https://127.0.0.1`.

**2 — Add credentials to your shell environment**

```bash
# Add to ~/.zshrc (or ~/.bashrc)
export SCHWAB_APP_KEY=your_app_key_here
export SCHWAB_APP_SECRET=your_app_secret_here
```

Then reload: `source ~/.zshrc`

**3 — Authenticate once**

```bash
python schwab_auth.py
```

This opens a browser OAuth flow. After approval, the token is saved to `~/.schwab_token.json` (gitignored — never committed). The token auto-refreshes on subsequent runs.

**4 — Verify**

```bash
python schwab_client.py --fundamentals NVDA
```

Should print Schwab's fundamentals for NVDA: margins, ROE, P/E, PEG, debt ratios, dividend data, beta, 52-week range.

### Commands

```bash
# Single ticker — Schwab price history
SCHWAB_DATA=1 python pop_scan.py NVDA

# Small batch — Schwab for all
SCHWAB_DATA=1 python extension_scan.py NVDA MSFT AAPL

# Ranked modes — Schwab for top-N scoring pass, yfinance for bulk
SCHWAB_DATA=1 python pop_scan.py --top10
SCHWAB_DATA=1 python pop_scan.py --mega10

# Monthly MA gate — Schwab for US tickers
SCHWAB_DATA=1 python monthly_ma_gate.py
SCHWAB_DATA=1 python monthly_ma_gate.py --dividend

# Fundamentals endpoint — broker-grade metrics for any ticker
python schwab_client.py --fundamentals NVDA AAPL MSFT
```

### Symbol normalization

Schwab uses `/` for share classes; yfinance uses `-`. `schwab_client.py` normalizes automatically — `BRK-B` becomes `BRK/B` on the wire, results come back correctly.

### Why Schwab vs yfinance

yfinance sometimes lags on split adjustments (prices look wrong for several days after a split). Schwab provides correctly adjusted data immediately. The toggle lets you switch to Schwab for a specific ticker without changing anything else. For routine weekly scans, yfinance is fine — the cache handles rate limits.

### Disk cache (yfinance path)

All yfinance price fetches go through a TTL-based pickle cache at `~/.cache/market-tools/`. Daily bars: 20-minute TTL. Weekly bars: 4-hour TTL. Back-to-back runs within those windows skip Yahoo entirely. Schwab path bypasses cache (always live from broker).

## Usage

```bash
# US dashboard
python dashboard.py                        # CLI only
python dashboard.py --refresh              # force fresh data
python dashboard.py --refresh --browser    # refresh + open in browser

# India dashboard
python india_dashboard.py
python india_dashboard.py --refresh
python india_dashboard.py --refresh --browser

# US screener (full run)
python screener.py

# Ad-hoc signal check — no full run, instant result
python screener.py --signal TICKER [TICKER ...]
# e.g. python screener.py --signal COST TXN BSX GOOGL

# India screener
python india_screener.py
```

Both dashboards output a CLI table and save an HTML file locally (`~/market_briefing.html` and `~/india_briefing.html`). Browser launch is opt-in via `--browser`.

`--refresh` forces a fresh data fetch and clears the 15-minute cache. Use it when the output shows blank rows or "no data" — that means the cache was written empty. After `--refresh`, all rows repopulate from live data.

## Screener — Quality Filters

### US (`screener.py`)
- Debt/EV ≤ 0.20 · Operating margin ≥ 10% · Net margin ≥ 5%
- ROE ≥ 10% · FCF yield ≥ 0% · P/E ≤ 100x (forward P/E used as fallback)
- FCF gap relief: None allowed when rev growth ≥ 50% AND net margin ≥ 10%
- Grading: A+ ≥ 6pts · A ≥ 4pts · OM weighted at 2pts (primary signal)

### EPS FY Trend Column

Shows each name's earnings growth trajectory using analyst estimates: **current FY growth %** (how much EPS is expected to grow this fiscal year vs last) and **next FY growth %** (the year after). Companies with declining EPS in their current fiscal year are deprioritized within each grade bucket — they still appear but sort below flat/growing peers.

Color coding: green = ≥15% growth, orange = 0–15%, red = negative.

This catches a real pattern: a company can grade A on historical quality metrics (margins, ROE, FCF) while analysts expect *declining* earnings this fiscal year. The screener doesn't disqualify them — historical quality matters — but it flags the headwind so you're not buying into a deteriorating earnings trend without knowing.

### Entry Zone Column

Color-coded distance from the 200-day moving average. No label, no verdict — just context.

| Color | Threshold | What it means |
|-------|-----------|---------------|
| **● Green** | ≤+5% vs MA200d | At or near the long-term trend line — margin of safety intact |
| **● Amber** | +5% to +20% vs MA200d | Moderate extension — price has moved, but not detached |
| **● Red** | >+20% vs MA200d | Stretched above the long-term trend — extension is real |

Not a buy/sell signal. The framework provides context — you compose the read. A red dot on a recovering stock with A+ fundamentals is a different situation than a red dot on a B-grade name at peak earnings. Same color, different meaning — that's why the verdict is yours, not the tool's.

### Weekly Signal Column — `Signal (wk)`

Shown only for A and A+ names. Three signal types, evaluated on weekly bars over 1 year of history.

| Signal | Condition | Meaning |
|---|---|---|
| `BullDiv` | Price lower low + both RSI-14 and MACD(12,26,9) histogram higher low | Momentum recovering ahead of price — divergence at a low |
| `BearDiv` | Price higher high + both RSI-14 and MACD(12,26,9) histogram lower high | Momentum fading into an extension — divergence at a high |
| `Trend` | Price above rising 10w MA + positive weekly slope + RSI > 50 | Uptrend pullback to the 10w MA — structure intact, momentum behind it |
| `—` | No confirmed signal, or B grade (not evaluated) | |

**Priority:** `BullDiv`/`BearDiv` take precedence over `Trend` when both conditions are present.

Single-indicator divergence signals are silenced. Contradictions (RSI says bull, MACD says bear) are silenced. Near-flat swing pairs (< 0.75% price move between swing points) are silenced. What remains is a narrow, high-conviction read on weekly structure — not a trade trigger, but a directional bias on quality names worth attention.

### India (`india_screener.py`)
- Debt/EV ≤ 0.20 · Operating margin ≥ 8% · Net margin ≥ 5%
- ROE or ROA ≥ 10% · FCF yield ≥ 0% · P/E ≤ 80x
- FCF gap relief: None allowed when rev growth ≥ 50% AND net margin ≥ 10%
- Grading: A+ ≥ 6pts · A ≥ 4pts · OM weighted at 2pts (primary signal)
- Sector-aware thresholds for Financials and IT

**India precision manufacturing additions (Aug 2026):**

| Name | Tier | Thesis |
|------|------|--------|
| SANSERA.NS | UNIVERSE | Complex precision forged + machined components (auto + aerospace + non-auto). OM 13.8%, GrossM 58.4%, ROE 11.1%, near-zero debt. FCF -6% is capex expansion into aerospace, not distress. Grade A (6/7, structural exception). |
| SCHAEFFLER.NS | UNIVERSE | Precision bearings + linear motion components (German parent FAG/LuK/INA). OM 14.8%, ROE 21.6%, zero debt, FCF 3.8%. GrossM 38.4% is structural for precision metal manufacturing — not a blocker. Grade A (6/7, structural exception). |
| CRAFTSMAN.NS | WATCHLIST | Precision machined components + aluminum die casting (auto + industrial). Visible gates pass. ROE + FCF missing from yfinance (data gap, not operational absence); grade B until confirmed. Gate: ROE ≥10% + FCF >0 data normalizing. |
| TIMKEN.NS | WATCHLIST | Precision tapered roller bearings (US parent, 120yr bearing heritage). OM 15.5%, NM 11.8% excellent. ROE + FCF missing from yfinance; grade B until data confirms. Gate: ROE/FCF data normalizing + GrossM structural exception review. |

**Precision manufacturing GrossM exception** — bearings, machined parts, and forgings structurally peak at 38–42% GrossM due to material input costs. This is not the same story as software, pharma, or branded consumer where GrossM >60% is achievable. When OM, ROE, FCF, and D/EV all clear, GrossM below 40% is not a blocker for this sector.

**Note on `&` tickers** — ARE&M.NS (Amara Raja) and M&M.NS (Mahindra) contain ampersands that break shell argument parsing. They remain in `india_screener.py` and appear in screener output, but `extension_scan.py --india` skips them to avoid shell errors.

## Dashboard Signals

- **ALIGNED** — price above all 4 MAs (50D, 20W, 10M, 20M)
- **PULLBACK** — above long-term MAs, below short-term (potential entry)
- **AVOID** — below long-term structure

Volume shown as `x(C)` = closed-day vs 20-day avg · `x(P)` = partial intraday

### vs87w Column

Price vs the 87-week MA, expressed as a percentage. Same metric as `ext87` in the extension scan — how far above or below the long-cycle structural mean. Positive = above, negative = below.

Color thresholds are context-aware by asset type:

| Asset type | Green (at/near) | Yellow (caution) | Red (extreme) |
|---|---|---|---|
| **ETFs** (NLR, GRID, COPX, SMH, IGV, IWM, etc.) | 0% to +25% | +25% to +50% or −1% to −15% | > +50% or < −15% |
| **Individual names** (metals, equities) | 0% to +50% | +50% to +80% or −1% to −20% | > +80% or < −20% |

ETFs dampen swings by construction — a +30% ETF extension is already stretched. Individual commodity names (FCX, WPM) can sustain wider extensions through cycle runs before mean-reverting.

### RS/SPY Column

13-week relative strength vs SPY, in percentage points. Ticker's 13-week return minus SPY's 13-week return. Positive = outperforming SPY over the past quarter, negative = underperforming.

Green when positive, red when negative. The magnitude matters: +15pp means the name returned 15 percentage points more than SPY over 13 weeks — sector leadership confirmed. −10pp means the name lagged SPY by 10pp — sector headwind visible.

## A Personal Note

I never had success with markets or a successful track record. I never made $100k or a million from trading (or investing) so far in my life. These frameworks were built through failures and learnings — not victories.

They might provide insights, or they might not. They are not tailored advice or suggestions for anyone. They are simply one person's attempt to build a framework for understanding a few themes in the market — quality, structure, momentum, and discipline.

I never found the holy grail. I could never fully resolve the puzzles of the market. I had only learnings. That is what this repository is: a record of those learnings, shared openly in case they are useful to someone else on the same journey.

## These Tools Are a Starting Point

Even when tools work, they rarely work fully for your specific needs. Every investor has a different universe, different themes they follow, different thresholds that make sense for their context.

These screeners cover what came into my radar — the companies I tracked, the sectors I followed, the filters that made sense to me. They will miss things. Many things. That is not a bug — it is the nature of any framework built by one person with one perspective.

If a name matters to you, add it. If a threshold feels wrong for a sector you understand better, change it. If a theme is missing, build it in. The code is simple enough that most customizations take a few lines.

Think of this as a basic scaffold — not a finished house. The value is in bending it to fit your own thinking, your own watchlist, your own sense of what quality means in the industries you follow. More data points, more puzzle pieces. Fewer blind spots.

## Multiple Lenses, Honest Limitations

No single tool closes the loop. RSI divergence catches momentum exhaustion. MACD histogram confirms it. MA alignment tells you where price lives structurally. Market breadth tells you if a move is broad or narrow. Each one has a blind spot the others partially cover.

These are filters for reducing confusion, not tools for eliminating uncertainty. A name that fails the weekly signal but sits above all four MAs isn't a contradiction — it's two different questions being asked on different timeframes. The weekly signal asks "is momentum turning?" The MA stack asks "where is price relative to its own history?"

### Top-down or bottom-up — your choice

The framework was designed with multiple entry points. Use whichever lens fits how you think.

**Top-down** — start from the macro and drill in:
1. **Market breadth** (`us_marketbreadth.html`) — is the rally broad or narrow? NH/NL ratio, participation across MA20/50/100/200. If breadth is thin, even strong individual names carry more risk.
2. **Sector dashboard** (`market_briefing.html`) — which sectors are structurally aligned? ALIGNED → PULLBACK → AVOID across four timeframes. Ride the sector tailwind, not against it.
3. **Aligned screener** (`aligned_screener.html`) — within the leading sectors, which names are 4/4 with accumulation? Cycle Watch and Pullback Watch for the ones not yet aligned but approaching.
4. **Quality screener** (`quality_screener.html`) — confirm the shortlist has the fundamentals to survive. A+ quality + 4/4 structure is the full signal.

**Bottom-up** — start from a name or thesis and verify the context:
1. **Quality screener** — does the business pass the durability filters? Grade, margins, ROE, FCF, debt.
2. **Aligned screener** — is the price structure confirmed? 4/4, or approaching through Pullback Watch / Cycle Watch?
3. **Monthly MA gate** (`monthly_ma_gate.html`) — if it's not yet aligned, is it at least near the long-term MA floor? Names sandwiched between their 10-month and 20-month SMA with a tight span are the highest-conviction pre-recovery setups.
4. **Sector dashboard** — does the sector support the individual thesis? Or is the sector headwind working against you?

**Monthly MA Gate — the pre-recovery lens**

The monthly MA gate screen exists for a specific moment: just before or early in a recovery cycle, when names are still below their 4/4 threshold but hovering at the long-term floor. Growth names need a confirmed MA reclaim before entry. Cyclicals can be entered on cycle thesis alone. But both benefit from knowing where the gate is.

The screen sorts by **span** — the sum of distances to both the 10-month and 20-month SMA. A name with a tight span (● < 3%) is sandwiched between both MAs simultaneously — both acting as guardrails, energy building for a directional break. That is a different and more compressed setup than a name that is close to only one of the two MAs.

Run it when you sense the market is finding a bottom. Close it when the recovery is underway and the aligned screener takes over.

**Divergence is also context**

When two lenses disagree, that is the framework working — not a contradiction to resolve.

MA200d extension at +68% and 10w MA at -9.5% are both true simultaneously: the long-term trend has run far, and the short-term is digesting. The 52w high at -24% adds a third truth: the digestion has been real. RSI 62 with a positive slope adds a fourth: the digestion may be ending.

None of these contradict each other. The skill is holding all of them at once and knowing which one is load-bearing for the decision you're making.

This is the core distinction: the framework does not collapse multiple signals into one verdict. It keeps them separate. Each lens answers a different question. You supply the judgment; the tools supply the material. Context, not conclusions.

A signal that works on one timeframe can look like failure on another. That isn't failure — it's limitation. Good coverage means knowing what each lens sees and what it cannot. No framework is supposed to be complete.

Completeness would be a bug, not a feature. If the framework said "buy this, definitely" it would be lying.

**Technicals reflect correlations that existed. They don't guarantee correlations that will exist.**

The extension scan, the runway, the 87w structural read — these are real. IWR at 10% runway with RSI 79 is a factual price/structure reading. But the interpretation layered on top — "mid-caps topping precedes consolidation, next leg comes from tech" — is a pattern from past cycles being applied to this one. And every cycle has a reason the pattern behaves differently.

2020: small caps lagged the initial recovery, then caught up violently in the vaccine rotation. 2022: QQQ had the most runway by extension metrics in early January — it led the crash. 2023: the Magnificent 7 decoupled from the rest of SPY entirely; IWM went nowhere while SPY looked healthy. Each cycle the correlations shifted, and the shift was driven by the macro underneath — not by the technicals.

Correlations are emergent. They come from the underlying macro conditions: rate trajectory, credit availability, geopolitical friction, earnings cycle, sector-specific catalysts. The technicals reflect correlations that already formed. They don't lock in correlations going forward. If rates re-accelerate sharply, small caps (more floating-rate debt) get hit hardest regardless of how much runway the extension scan shows. The map changes faster than anyone can redraw it.

This is why the framework is quality-first and structure-second. MA alignment breaks in every crash — it's a regime filter, not a survival guarantee. Quality FCF, low debt, durable margins — those are what allow a business to outlast the correlation breakdown, whatever form it takes.

The technicals are the map. The macro is the terrain. The terrain changes faster than the map. Sit with that every time a technical read feels conclusive.

These tools do not recommend. They do not provide tailored advice. They are one person's attempt to organize a few questions about quality, structure, and momentum — and share that attempt openly. What you do with the output is entirely your own judgment, your own context, and your own responsibility.

## SIP Watchlist — US

`SIP_WATCHLIST` in `screener.py` — toll-booth businesses on durable US infrastructure. Not traded. Owned regularly via DCA regardless of short-term price. Common thread: asset-light, fee/royalty/toll income, compound with secular structural growth.

**Financial Market Infrastructure:**

| Name | What it is | Why SIP |
|---|---|---|
| **NDAQ** | Nasdaq, Inc. — exchange + technology + data | Every trade, listing, index product (QQQ pays NDAQ) pays NDAQ; own the exchange not the stocks |
| **MSCI** | Index royalty — MSCI EM, MSCI World, MSCI ACWI | Every ETF tracking these indices pays MSCI forever; purest royalty model in financial markets |
| **MCO** | Moody's — ratings duopoly (~80% global share with S&P) | Every bond issued globally needs a rating; Buffett-proven, near-impossible to displace |
| **SPGI** | S&P Global — S&P 500 licensing + ratings + data | Every SPY/VOO/IVV pays SPGI; combines index royalty + ratings oligopoly |
| **ICE** | Intercontinental Exchange — NYSE + futures + mortgage tech | Toll on NYSE trades + futures contracts + mortgage origination platform |

**Payment Networks:**

| Name | What it is | Why SIP |
|---|---|---|
| **V** | Visa — global card network | Toll on every card transaction globally; no credit risk; cashless transition compounds it |
| **MA** | Mastercard — Visa's global duopoly partner | Same model, slightly more international mix; cross-border fees compound with global commerce |

**Payroll Infrastructure:**

| Name | What it is | Why SIP |
|---|---|---|
| **ADP** | Automatic Data Processing — payroll for millions of US businesses | Extreme switching costs; every new US job = more ADP revenue; already A+ in UNIVERSE |

**Waste Infrastructure:**

| Name | What it is | Why SIP |
|---|---|---|
| **WM** | Waste Management — regulated waste oligopoly | Every community needs waste removed; landfill permit moat; recycling + renewable gas tailwind |

**BDC / Income:**

| Name | What it is | Why SIP |
|---|---|---|
| **MAIN** | Main Street Capital — BDC lending to lower middle market companies | ~8.4% yield paid monthly + semi-annual specials; internally managed (removes fee conflict vs externally managed BDC peers); trades at premium to NAV — rare for BDCs, reflects management quality; not a growth compounder, a durable income machine |

Note: MAIN is judged differently from the rest of this list — standard OM/D/E filters don't apply cleanly to BDC structure. Judge by NAV growth, dividend coverage, and management track record instead.

Note: NDAQ ≠ Nasdaq Composite ≠ QQQ. QQQ pays licensing fees *to* NDAQ. Owning NDAQ means owning the company that collects those fees.

## India SIP Watchlist

`SIP_WATCHLIST` in `india_screener.py` — high-quality toll-booth businesses on India's financial system growth. Not traded. Owned regularly via SIP regardless of short-term price.

Common thread: asset-light, fee or infrastructure income, no balance sheet risk, compound directly with India's financial deepening.

**Mutual Fund Infrastructure:**

| Name | What it is | Why SIP |
|---|---|---|
| **HDFCAMC** | HDFC Asset Management — second largest AMC by AUM | Fee income as % of AUM; every SIP rupee in India grows their AUM; financialisation of Indian savings early innings |
| **CAMS** | Computer Age Management — processes ~70% of all India MF transactions | More defensive than any single AMC; wins regardless of which AMC wins; pure infrastructure toll |
| **KFintech** | KFin Technologies — second MF registrar after CAMS (~30% share) | Same model as CAMS, same tailwind; diversified into international fund admin + corporate registry |

**Depository Infrastructure:**

| Name | What it is | Why SIP |
|---|---|---|
| **CDSL** | Central Depository Services — every demat account in India | India adding ~3M demat accounts/month; permanent infrastructure, no structural competition |

**Exchange Infrastructure:**

| Name | What it is | Why SIP |
|---|---|---|
| **BSE** | Bombay Stock Exchange — India's NDAQ analog | Toll on every BSE trade, SME listing, currency derivative; own the exchange not the stocks |
| **MCX** | Multi Commodity Exchange — India's CME analog | Every gold/silver/crude/agri futures trade pays MCX; structural monopoly in commodity derivatives |

**Credit Rating / Data:**

| Name | What it is | Why SIP |
|---|---|---|
| **CRISIL** | India's dominant credit rating agency, S&P Global subsidiary | Every corporate bond needs a rating; SPGI analog for India; regulatory entrenchment permanent |
| **ICRA** | Moody's India subsidiary (~52% Moody's stake) | CRISIL + ICRA = India's rating duopoly, mirrors S&P + Moody's globally; MCO analog for India |

The hierarchy: CAMS owns the road, CDSL owns the parking lot, HDFCAMC owns one of the cars, BSE owns the building — all compound with India's financial deepening.

## India FUTURE_RADAR

`FUTURE_RADAR` in `india_screener.py` — not scanned, not graded. Real businesses with real revenue but path to profitability unclear, or structural change pending before the thesis activates.

| Name | Gate to watchlist |
|------|------------------|
| **OLAELEC** | OM turning positive sustained + FCF inflection + competitive position stabilising in EV two-wheeler market |
| **RELIANCE** | Jio IPO / Reliance Retail listing / O2C demerger announced — today's C grade is conglomerate blending; Jio + Retail in isolation are A-grade businesses trapped inside O2C margin drag |

RELIANCE note: the thesis is not the stock today — it's what the stock becomes when the O2C (oil-to-chemicals) refining business is separated. Jio is a telecom duopoly platform. Reliance Retail is India's largest retailer. Both would grade A+ as standalone listed entities. The demerger timeline is 2026–2028. Until then, the blended entity grades C and belongs here, not in the watchlist.

## Future Vision — The Missing Layer

The framework finds the setup. It cannot tell you how much to size it.

That gap is real and acknowledged. Position sizing is where most losses actually happen — not from wrong stock picks, but from right picks sized incorrectly that get shaken out before the thesis plays out. A 25% drawdown on a 2% position is noise. The same drawdown on a 20% position forces a decision you shouldn't have to make.

The vision: a personal risk profile layer that takes the screener's signal quality as one input and the user's actual financial parameters as another — account size, income stability, time horizon, obligations — and returns a position size that survives the specific drawdown that setup could produce. Not a static conservative/moderate/aggressive bucket. Dynamic: a 4/4 + CMF+ + RS 1.5x + A+ confluence earns more size than a borderline 3/4 setup. The setup quality and the personal risk profile together determine how much.

This is not a feature that can be added with a few lines of code. The reasoning layer is solvable — LLMs can already do this kind of contextual sizing analysis if inputs are structured correctly. What's hard is everything around it: regulatory (personalized sizing guidance in the US touches SEC/FINRA territory), accuracy (people systematically overestimate drawdown tolerance until they're actually in one), and trust (a sizing recommendation is only as good as what the user inputs honestly about their real situation).

Whether this gets built here, somewhere else, or not at all — the gap it would close is real. The screener half works. The survivability half doesn't exist yet at the individual stock level, personalized to who you actually are financially. That combination is where the value is.

**Portfolio construction and risk — the deeper layer**

What makes this hard isn't the math. Beta decomposition, correlation mapping, tail risk estimation — those are solved problems. What's unsolved at the personal scale is the *inputs*.

Large institutions have had this for decades. BlackRock's Aladdin does exactly this — factor exposure, beta decomposition, correlation across thousands of holdings — for pension funds and sovereign wealth funds at millions per year. The personal investor version doesn't exist in any honest form. Robo-advisors give you a static allocation based on a one-time questionnaire. Brokerage risk tools describe your portfolio's beta after the fact. Neither knows that you hold six semiconductor names with combined market beta of ~2x, that your income is variable, and that a 20% drawdown over the next six months would force you to liquidate at exactly the wrong time.

The three layers that would actually work together:

**1 — Portfolio beta decomposition.** You input your holdings. It tells you: your effective market beta is 1.7x, 40% of your risk is sector-specific (idiosyncratic — semiconductor cycle, earnings, geopolitics), 60% is macro. If SPY drops 15%, here is your expected drawdown range — not as a generic percentage, but specific to what you actually own.

**2 — Real risk capacity.** Not a questionnaire. Actual parameters: account size, income stability, upcoming obligations in the next 12 months, time horizon. From these it derives the answer to the question that actually matters: what drawdown can you survive without being *forced* to sell? That number is different from what most people think it is when markets are calm. A $50k account with stable income and no near-term obligations can absorb more risk than a $200k account with variable income and an obligation coming in 14 months. Account size alone tells you almost nothing.

**3 — Dynamic position sizing.** Combines 1 and 2. A 4/4 + CMF+ + A+ quality setup in a 1.2x beta name earns more size than a borderline 3/4 setup in a 2.0x beta name. The output is personalized to your actual risk capacity — not a generic conservative/moderate/aggressive bucket.

**The personality layer — the part most tools miss entirely**

Most financial tools either ignore an investor's personality or try to standardize it away — fitting everyone into three buckets and calling it personalization. That's not personalization. That's categorization.

The right orientation is different: **complement the investor's natural tendencies, then tweak where needed — don't replace them.** A momentum-oriented investor shouldn't be forced into a value framework. A patient, thesis-driven investor shouldn't be pushed toward short-term signals. The goal is to understand how someone naturally thinks about risk and reward, work with that grain, and make targeted adjustments at the edges where their tendencies create blind spots — not override the whole personality.

This matters because behavior under stress is personality-driven, not logic-driven. When a position is down 20%, whether someone holds or folds is determined less by the framework they built in calm conditions and more by who they are. A risk tool that ignores this is giving advice to a person who doesn't exist — the calm, rational, spreadsheet-reading version — not the actual person who will make the decision at 2am during a correction.

The goal is not to make every investor identical. It is to help each investor become a *better version of themselves* — maximizing what they're already good at, minimizing the specific risks their personality creates, and sizing positions to survive the drawdown that will eventually test them.

LLMs are well-suited for this — not to replace the math, but to gather honest inputs. A conversational interface can ask the right questions in the right order, detect inconsistencies ("you said high risk tolerance but also said you'd need this money in 18 months"), and translate real life context into structured risk parameters. The math is easy. Getting honest, self-aware inputs from real people — in their actual life context, not their idealized version of themselves — is the hard part. Conversation solves it better than any form.

**Control — the core objective**

Markets are random a significant portion of the time. Outlier events — tariffs, rate shocks, geopolitical surprises, earnings gaps — are not predictable and not controllable. Most people spend most of their mental energy on exactly this: watching macro, reading predictions, worrying about what the Fed will do next. None of it is within reach.

What is within reach is a different list entirely:

- **Which opportunities to seek** — you choose the universe, the quality threshold, the themes you understand
- **When to enter** — you choose the timing, the structure confirmation, the patience to wait for alignment
- **How much to size** — you choose the exposure, calibrated to your actual risk capacity not a generic bucket
- **Which strategies to use** — long equity, spreads, DCA, cash-secured puts — you choose the instrument that fits your capital and temperament
- **Whether to hold when it moves against you** — you choose whether the thesis is intact or broken

This is the correct frame for what personalization at scale means. Not predicting markets — that is the wrong goal and it is not achievable. But giving every person maximum agency over the things they actually control, calibrated to who they specifically are.

The right column looks different for everyone. Which opportunities to seek depends on what you understand deeply. When to enter depends on your time horizon. How much to size depends on your real obligations and drawdown capacity. Which strategies to use depends on your capital, your temperament, your tax situation. Whether to hold depends on your conviction in the original thesis — not the current price.

A robo-advisor gives everyone the same right column. That is not personalization. That is a template with your name on it.

The real objective: **control over your money, through control over your decisions, through clarity about what is actually within your reach.** The screener surfaces the opportunities. The framework disciplines the entry. The missing layer — personalization at scale — closes the loop on sizing, strategy, and response. Together they give you the only kind of edge that compounds: not prediction, but agency.

**Responsible sizing — the ethical layer**

There is one more dimension that belongs here, and it is not optional.

Any system that makes sizing recommendations — or even sizing suggestions — carries a responsibility that goes beyond math. It is not enough to say "here is the optimal position size given your portfolio." The system must also enforce guardrails that protect the person from themselves, from overconfidence, from the specific behavioral failures that markets reliably produce.

This means: sizing recommendations must be bounded by portfolio size. A person with a $5,000 portfolio should never be in a position where a single trade — regardless of how high-conviction — can permanently impair their ability to stay in the game. A person with a $500,000 portfolio has different absolute limits but the same principle applies. The guardrail is not about the quality of the setup. It is about survival. A right thesis sized incorrectly can still end the game.

This applies irrespective of who the user is — individual investor, small fund, institution. The size of the portfolio does not change the principle. It only changes the numbers. Responsible sizing means the system will not recommend — or allow — a position that exceeds what the portfolio can survive if the trade goes to zero. Not because it is likely to go to zero. Because the role of a responsible system is to make sure that even the unlikely outcome does not end the journey.

The projected growth dimension matters too. A portfolio that is growing should have sizing that reflects where it is going, not just where it is today. A portfolio that is shrinking should have sizing that protects the remaining capital more aggressively, not less. Static percentage rules miss this entirely — 5% of a growing portfolio and 5% of a declining portfolio are not the same decision.

This is the layer that separates a tool from a responsible system. Tools give you outputs. Responsible systems refuse to give you certain outputs — not because they can't compute them, but because giving them would be wrong. That refusal is not a limitation. It is the feature.

Calling a system's guardrails "restrictive" gets this backwards. Guardrails don't restrict your agency — they keep you at the table long enough to exercise it. If the system lets you blow up, you lose all future decisions. A system that protects your survival is what makes every future choice possible. The guardrail is not the constraint. Losing the account is.

Heavy? Yes. Needed? Without question. This is not regulatory compliance language. It is the design principle that makes the difference between a system that helps people build wealth and one that helps people lose it faster with more sophistication.

**Auto-sensing on-demand triggers — the next automation layer**

Today, on-demand tools like the monthly MA gate require a human to notice that conditions are right and click "Run workflow." That is one manual step too many at exactly the moment when timing matters most.

The next layer: an AI reading the scheduled screener outputs and deciding when to fire the on-demand screens automatically. The signals already exist in the data — NH/NL ratio inverting, multiple quality names clustering near monthly MAs simultaneously, CMF turning negative across a broad swath, breadth dropping below threshold. These are the same signals a human would use to decide "it's time to run the gate screen." An LLM with access to the latest HTML outputs can detect that pattern and trigger the GitHub Actions `workflow_dispatch` endpoint programmatically.

The Anthropic API + GitHub Actions API is the natural bridge. The `workflow_dispatch` design already makes every on-demand tool triggerable via a single API call. The sensing layer on top — reading structured screener data, detecting inflection conditions, firing the right tool at the right moment — is where AI earns its place in the loop. Not replacing judgment, but making sure the right question gets asked at the right time without a human having to remember to ask it.

## The System vs The Single Trade

The practitioner's answer when asked "what is the one trade you would do if you had only one trade?": sell a naked put on /ES, 45 DTE, 12 delta, take off at 50% profit. Sound strategy. But one literal trade is just an 88/12 coin flip. The system — mechanically repeating that setup across 100 trades — is what generates the edge.

We didn't build a system for that trade. We built one for quality, alignment, structure, and timing. It's more sophisticated than one variable repeated mechanically. It has six orthogonal layers that compound.

| Layer | What it removes | What passes through |
|---|---|---|
| **Quality gates** (GrossM / OM / NM / ROE / FCF / D/EV) | Companies that die in adversity | Only businesses that survive and compound |
| **Tier placement** (UNIVERSE / WATCHLIST / FUTURE_RADAR) | Premature capital allocation | Capital goes where conviction is earned |
| **Extension scan** (10w MA, ceiling, RSI, slope, 87w) | Wrong timing on right names | Right name at structurally sound entry zone |
| **CMF / A/D Line** | Dips with distribution behind them | Dips with institutional accumulation behind them |
| **IV Rank / IV/HV** | Selling premium when it's cheap | Premium selling only when options are expensive |
| **Entry + exit rules** (4/4 alignment, pullback to MA, 50% take-off) | Discretionary drift | Mechanical discipline at both ends |

Each filter alone is ~55–60% signal. But they are **orthogonal** — quality says nothing about timing, timing says nothing about IV, IV says nothing about structure. When all six align, the joint edge compounds. That is the architecture.

The deeper point: the system works because it removes the human from the decision after setup. The same discipline is built into every layer here — the $20 price floor, the `[LOCKED]` gate, the 50% take-off rule, the A/A+ only rule. None of those are predictions. They are friction that prevents bad decisions at emotional moments.

One quality screen on a name is just a data point. Running it through all six layers — quality ✓, tier placement ✓, below 10w MA but CMF accumulating ✓, ceiling runway intact ✓, slope positive ✓ — that is the system speaking. The system does not predict. It removes everything that is not signal.

---

## Capital Deployment Principles

Finding the right name is half the job. How you deploy capital once you've found it is the other half — and it's where most frameworks go silent. These principles are not aspirational. They are the practical output of running the six-layer system.

**1 — Quality gates before anything else**  
No capital moves before the quality screen passes. This is not a formality. A name that fails even one gate (OM, NM, ROE, FCF, D/EV, RevG) is not a borderline candidate — it is not a candidate. Quality is not a tiebreaker. It is the entry requirement. The $20 price floor and the `[LOCKED]` mechanism enforce this mechanically so it does not become a negotiation at a moment of excitement.

**2 — Tier placement determines priority, not price action**  
UNIVERSE names get first allocation. WATCHLIST names get smaller, patient sizing — they are there because one gate is failing, not because the thesis is weak. FUTURE_RADAR names get zero capital until the unlock condition is met. This ordering is not about being conservative. It is about deploying capital where conviction is earned by the framework, not by the story.

**3 — Extension zone determines timing, not urgency**  
Fresh (just above 10w MA) earns full position size. Midway earns a partial. Extended earns a trim or a wait. Ceiling (87w extreme) earns nothing — let it correct first. Chasing a name at 87w extreme when a fresh entry exists elsewhere is not high-conviction. It is capital misallocation dressed as confidence.

**4 — CMF overrides the wait when accumulation is confirmed**  
If a name is below its 10w MA but CMF is +0.20 or better, institutional money is entering the dip. You do not have to wait for the 10w reclaim — that is already happening below the surface. CMF negative or flat at a dip means the dip is not being bought. Wait. Same quality, same tier, same extension — the CMF reading alone determines whether the dip is an entry or a falling knife.

**5 — Position size scales with confluence, not conviction alone**  
A single positive signal is context. All six layers aligned — quality A+, tier UNIVERSE, fresh zone, CMF accumulating, IV rank elevated, slope positive — earns the full position. Each layer missing drops the size: a borderline 3/4 signal with neutral CMF earns half or less. Conviction without confluence is the most expensive mistake in position sizing.

**6 — Discipline is the mechanism, not a value**  
The $20 floor, the 50% take-off rule, the `[LOCKED]` gate, the A/A+ only filter — none of these are about being cautious. Each one is mechanical friction that removes a specific bad decision from the table at the moment when emotion is most likely to override logic. The rules do not restrict agency. They preserve it by keeping you at the table.

**7 — Dry powder is a position**  
Not being deployed is a decision, not a failure. A name at 87w extreme with CMF flat is not an opportunity — it is a trap. The capital you don't deploy there is available when the same name corrects to the 10w MA with CMF turning positive. Patient capital compounds. Impatient capital funds other people's exits.

**The summary read:** quality first → tier sets the priority → extension zone sets the timing → CMF confirms the dip or flags the knife → confluence determines size → mechanical rules enforce the exit. Nothing in that sequence requires prediction. All of it requires discipline.

---

## Not Losing > Making

The math is asymmetric and unforgiving. Lose 50%, need 100% to recover. Lose 30%, need 43%. And while you're recovering, you're not compounding — that's the hidden cost nobody counts. Dead time is dead capital.

Losses carry three costs, not one:
- The capital gone
- The time to recover it
- The opportunity you couldn't take because the capital was stuck healing

Dry powder isn't just safety — it's optionality. The person who didn't lose in the drawdown is the one who can buy at the bottom. The person who lost 40% is just trying to get back to even.

This is why the quality gate is the first filter, not the last. Non-quality names don't just correct — they impair permanently. Quality corrects and recovers. That asymmetry matters more than any upside captured by owning lower-quality names.

Position sizing matters more than entry timing. A 15% drawdown in a 3% position is a rounding error. The same drawdown in a 25% position is a psychological event that triggers bad decisions — and converts a temporary drawdown into a permanent loss.

**Drawdowns are the price of admission, not a failure of the framework.** Ultra-easy markets are rare. Volatility is the permanent condition, not the exception. Always ready for it, never surprised by it. Quality endures — but only if the position was sized to survive the time it takes to endure.

Volatility is the filter. Quality passes through it. Non-quality corrects and doesn't come back. Position size determines whether you're still there when quality does what quality does.

Not losing is active. It's the real edge.

---

## The Honest Edge

Most frameworks are built for a world of certain inputs and stable systems. Markets don't live there.

Investing is **uncertain inputs in a dynamic system** — the two conditions where both precision and approximation fail on their own. The inputs change. Correlations shift. Regimes rotate. A measurement that was accurate yesterday anchors you to a world that no longer exists. Precise models on dynamic systems produce confident wrongness. Approximations on uncertain inputs produce honest humility — but neither alone closes the loop.

In that domain, the right move isn't prediction. It's knowing what you can actually know:

- **Approximate reward** — the spread ceiling, the 50% take-off target, the runway remaining. Not the exact outcome. The shape of the upside if you're right.
- **Known risk** — max loss is computable even when direction isn't. The spread defines it exactly. The quality gate defines it structurally. The sizing rule caps the portfolio exposure precisely.

That asymmetry is the whole game: **you don't need to know the reward precisely. You need to know the risk exactly.**

Because if you know the risk exactly and size it correctly, you survive being wrong. And surviving wrong long enough — while being approximately right often enough — is what compounds.

The quality gates don't guarantee the stock goes up. They guarantee that if it goes against you, the business underneath doesn't collapse. Survivability is the known floor. The reward is approximate — and that's fine. You don't need to know how high it goes. You need to know how bad it can get — and that you'll still be standing.

**Humility isn't weakness here. It's the mechanism.** Not pretending to know what you can't know is what prevents oversizing into a conviction you shouldn't have. The gap between what you know and what you're claiming to know — keeping that gap honest — is what keeps you at the table.

The edge isn't prediction. It's **asymmetric position in an uncertain, dynamic world**: capped downside, open upside, quality underneath, patience on top. Ranges instead of points. Scenarios instead of forecasts. Known risk, approximate reward.

That combination — not any single signal — is the real edge.

---

## The Confluence Lens

The market is always simultaneously broadcasting everything — price, volume, flow, sentiment, macro, narrative. The noise is real and relentless. The framework's answer isn't to process more of it. It's to process in the right order.

```
Quality gate          → is this worth owning at all?
  ↓ (if yes)
87w STRUCT            → where are we in the long cycle? room or stretched?
  ↓
Weekly extension zone → where is price vs its own mean (10w MA)?
  ↓
CMF (20w then 10w)    → what is money actually doing, not just price?
  ↓
Slope                 → is the trend direction confirmed?
  ↓
Daily MA alignment    → does the shorter timeframe agree or diverge?
  ↓
Hourly (⚡H)          → timing confirmation only — not a decision signal
```

CMF sits above zone in the hierarchy because price can lie — a name can look "fresh" on price while distributing underneath. Money flow cuts through that. When the 20-week and 10-week CMF agree, the signal is clean. When they diverge (20w positive, 10w negative), that divergence is itself information — longer accumulation but recent distribution — not a green light.

**Confluence means all lenses agree, not just most.** When every layer points the same direction simultaneously — quality gate clear, 87w structure mild, price at the 10w MA, CMF positive on both windows, slope up, daily confirming — that is the framework speaking at full conviction. Each layer that contradicts another is a signal of uncertainty, not opportunity.

**Divergence across lenses is not a contradiction to resolve. It's the framework working.** A name at 87w extreme with daily price below all MAs and CMF turning negative is not a "mixed signal" — it's three lenses independently saying the same thing from different directions. Hold multiple reads simultaneously. Know which one is load-bearing for the decision at hand.

The edge isn't finding more signals. It's having fewer, cleaner ones all pointing the same direction — and the patience to wait for that alignment before committing capital.

Most people never get there because they're optimizing for action, not clarity. The framework is built for clarity.

---

## Simple Entry Strategies

Four repeatable setups extracted from the framework. Not prediction. Each has defined conditions, a defined edge, and a defined exit.

### 1 — IV Rank Credit Spread

**Conditions:** IV Rank ≥ 0.70 + IV/HV ≥ 1.0 on any `SPREAD_UNIVERSE` name (SPY, QQQ, or Tier 1–2 liquid equity names)  
**Setup:** Sell a vertical credit spread 2–3 weeks to expiration. Bear call spread if price is near extension ceiling; bull put spread if at support with elevated IV  
**Edge:** Selling premium when options are expensive relative to realized volatility. Both IV Rank and IV/HV confirming = highest-conviction sell-premium environment. Strongest when combined with extension ceiling proximity (runway < 10%)  
**Exit:** 50% of max profit captured, or close before expiry if IV collapses

### 2 — 4/4 Alignment Entry

**Conditions:** A+ name transitions from 3/4 → 4/4 MA alignment for the first time after ≥1 non-4/4 week  
**Setup:** Enter on the first confirmed 4/4 weekly close  
**Edge:** Regime filter selects for trending environments (A+ 4/4 fresh entries cluster in low-vol trending regimes 61% of the time). Quality filter ensures the business survives adverse moves. Backtest: 52.3% win rate vs SPY at 13w for A+ 4/4 fresh entries  
**Exit:** At extension ceiling (runway < 10% + RSI ≥ 75), or when structure breaks (price closes below 10w MA)

### 3 — Pullback to MA

**Conditions:** A+ name in 4/4 alignment pulls back to 10w or 20w MA, with A/D Line still rising (no distribution into the pullback)  
**Setup:** Enter on the first green weekly close off the MA  
**Edge:** Buying structure at a defined support level in an established uptrend. Lower entry cost, tighter stop, rising A/D Line confirms smart money is not distributing into the dip  
**Exit:** At extension ceiling or structure break (price closes below the same MA that provided support)

### 4 — SPY Put Credit Spread (Mechanical)

The accessible version of the "one trade" philosophy — sell a naked put on /ES at 12 delta, 45 DTE, take off at 50% profit. Same mechanics, defined risk, doable at retail capital levels.

**Conditions:** No IV filter required — run this mechanically on a schedule, not on signal. SPY only (most liquid, tightest spreads, no earnings gap risk)  
**Setup:** Sell a bull put spread on SPY. 45 DTE. Short put at 12 delta (~88% probability OTM). Buy put 5–10 points lower for defined risk  
**Edge:** Volatility risk premium — the options market structurally overprices implied volatility vs realized because institutions must buy puts for portfolio hedging regardless of price. You are the insurance company. Over many trades, the 88% win rate at 12 delta compounds into a measurable edge. The 50% take-off rule captures the early theta decay and cuts gamma exposure before the final weeks  
**Exit:** 50% of max credit collected — close the spread, don't hold to expiration. Frees capital to reload the next cycle  
**Sizing:** 1–2% of account per trade. This is a system, not a single bet — the edge emerges over 50–100+ repetitions, not one trade  
**Why not naked /ES:** Same directional thesis, same delta, same DTE — but /ES naked puts require $25–40k+ margin per contract. The spread is the retail-accessible wrapper around the identical strategy

**What the philosophy actually means:** The "one trade" soundbite is shorthand for a discipline — be *mechanically* short premium in elevated IV environments, take profits early, repeat relentlessly. One literal trade is just an 88/12 coin flip. The system is what generates the edge

**Concrete example — SPY near $800:**

> SPY at ~$800 · 45 DTE · CMF +0.378 (institutional buffer — dips get bought)
>
> Sell $735 put / Buy $725 put (10-point wide spread)  
> Credit collected: ~$0.80 ($80/contract)  
> 50% take-off target: $0.40 profit ($40/contract)  
> Breakeven at expiration: $734.20 (SPY must fall **8.2%** in 45 days to lose)  
> Max loss: $920/contract (spread width minus credit)

| Outcome | Probability | P&L per contract |
|---|---|---|
| SPY stays above $735 (OTM — wins here) | ~88% | +$40 (50% take-off) |
| SPY between $735–$734.20 (near breakeven) | ~2% | near zero |
| SPY below $734.20 (loss territory) | ~10% | −$40 to −$920 |

10-trade run at 88% win rate: 8 wins × $40 = +$320, 2 losses × −$460 avg = −$920. Net: **+$400 on ~$9,200 margin deployed** over ~6 months. That's the system — not the single trade

**Capital reality — "somehow capital required, somehow safe":**  
Not capital-intensive like /ES naked puts ($25–40k margin per contract). But proper sizing still requires ~$45k to keep one SPY spread at 1–2% account risk. At $5k, a $920 max-loss is an 18% drawdown — the math doesn't hold. The "safe" part comes from three layers working together: defined max loss (spread caps the downside), CMF buffer (institutional accumulation at elevated levels means dips get bought), and the 88% base rate at 12 delta. Remove any one layer and it's just a directional bet

**Rules common to all three:**
- $20 price floor — no exceptions, no matter how clean the setup looks
- Quality A or A+ only — the A/A+ distinction is load-bearing (A-grade at 4/4 historically underperformed SPY; see backtest). A borderline grade is not the same as a passing grade
- Options strategies (1) use SPREAD_UNIVERSE names only — execution outside that set means slippage eats the edge before the trade starts
- Confluence over single signals — one condition alone is context, not a trade

## Disclaimer

For informational purposes only. Market dynamics change constantly — these outputs are auto-generated from Yahoo Finance data and may not reflect current conditions. Not tailored financial advice. Not a recommendation to buy, sell, or hold any security. Always do your own research.
