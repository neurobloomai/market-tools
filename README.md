# market-tools

Free, open-source market dashboards and quality stock screeners powered by Yahoo Finance.

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
| `pop_scan.py` | 🇺🇸 US | Daily Pop Scanner — price vs 10d/20d/50d MAs across full universe · gold/green/amber range bands · ◎ tight band for coiling setups within -5% of MAs · hourly MA confirmation flag · on-demand |
| `extension_scan.py` | 🇺🇸 US | Weekly MA Extension + Projection Scanner — for each ticker above its 10w MA, shows current extension vs historical 90th-pct ceiling, runway remaining before ceiling, implied ceiling price, weekly RSI and 10w slope · answers "how much further can this go?" · flags blown-ceiling names in red · supports `--universe`, `--watchlist`, `--dividend`, or explicit tickers (CLI-only) · on-demand |
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

## Why This Framework Holds Up

**Quality gate** — the screener filters aren't just revenue growth or price momentum. Debt/EV + operating margin + net margin + ROE + FCF together mean only businesses that can survive a bad year get through. That's the survivability filter. Quality doesn't raise win rate — it makes losses survivable and wins compoundable.

**Structure confirmation** — 4/4 MA alignment means the market agrees with the fundamentals. Price, momentum, and quality all pointing the same direction before anything is acted on. No thesis without structure. No structure without thesis.

**Early warning system** — Special Mention catches names before they qualify. You're not chasing; you're watching the base build. A/D Line and OBV divergence add an extra layer — when smart money starts accumulating before the monthly regime flips, the volume picture changes before the price structure does. When a name finally surfaces in the aligned list, it's not a surprise — it was already on the radar with the volume story already forming.

**Honest watchlist** — every entry has a thesis and a blocker noted. Not just a ticker dump. You know exactly why something isn't in the universe yet and what has to change for it to qualify. The rule: if the blocker is a number, it belongs in the watchlist. If the blocker is the business model, it doesn't.

**Numbers over narrative — but not instead of it.**

Stories are infinitely flexible. At any price, for any stock, someone has a compelling narrative — the TAM is enormous, the moat is wide, the CEO is visionary. Numbers are not flexible. GrossM 23% doesn't become 45% because the thesis is good. FCF -50% doesn't disappear because the long-term case is compelling. The framework uses the story to choose *which numbers matter* — and uses the numbers to discipline the story. A story without numbers is speculation. Numbers without story is pattern matching without understanding. The edge lives at the intersection: thesis-driven selection, metric-driven confirmation.

The gate is simple: a story must eventually show up in the numbers. Until it does, it lives in FUTURE_RADAR — not UNIVERSE.

**Three-tier universe structure:**

| Tier | What it is | Gate to next tier |
|---|---|---|
| `UNIVERSE` | Quality cleared, structure confirmed — core tracked names | Already here |
| `WATCHLIST` | Moat proven, one or two metrics blocking — scanned weekly | Metric clears the filter |
| `FUTURE_RADAR` | Real product, real revenue, path to profit unclear — not scanned | OM turns positive + FCF inflects |
| Removed entirely | Pre-revenue ventures, survival risk, all filters blocking | Not tracked |

Names removed from watchlist in first cleanup: SMR, OKLO, XE (pre-revenue nuclear), IONQ (quantum), CRSP/NTLA/BEAM (gene editing), RXRX/RARE (biopharma), MRNA/BNTX (revenue collapsed), ASTS/LUNR (space ventures). India: OLAELEC (deeply loss-making EV in structurally competitive market). These are interesting themes — not watchlist material.

Names removed from watchlist in second cleanup: PCG (wildfire liability structural, not a metric), FCX (own note said "not a compounder" — cleaner expressions already in universe), SEDG (Chinese competitor share loss is structural, not cyclical), KLAR (credit cycle risk inherent to BNPL model), INOD (AI model efficiency reducing annotation demand is an existential business risk), AMKR (services margin ceiling structural, B-grade at best), CELH (energy drink competitive moat fragile vs Monster/Red Bull), MRAM (TAM too small, speculative angle). Moved to FUTURE_RADAR: CORZ (BTC miner pivot unproven), MOD (B grade, multiple blockers), UPST (credit cycle structural, gate is FCF + converts + through-cycle proof), PGY (Pagaya — D/EV too high for WATCHLIST today, AI-powered credit network with real revenue but balance sheet needs work before it earns a watchlist spot).

Recent watchlist additions: **VICI** (gaming REIT — Caesars/MGM landlord, triple-net leases, ~5% yield; standard OM/D/E filters don't apply cleanly to REIT structure — judge by lease coverage, tenant quality, and AFFO instead), **ABT** (Abbott Laboratories — diversified med-tech + diagnostics + nutrition; consistent dividend grower, strong FCF, A-grade quality), **TLN** (Talen Energy — nuclear power + data center PPAs; nuclear PPA contracts with hyperscalers are a durable revenue stream as AI infrastructure electricity demand grows), **PRGS** (Progress Software — enterprise DevOps/application platforms; value play with recurring revenue and improving margins).

**Both markets** — US and India running the same framework. Same discipline, same filters, different universes. The logic doesn't change because the geography does.

**Theme coverage** — semis, AI infrastructure, defense, healthcare, financials, energy, precious metals, solar, space, quantum, materials. Hard to find a major structural theme that isn't tracked somewhere across the 230+ names.

**The one honest gap** — individual position sizing and entry discipline aren't in the framework. The screener tells you *what* and *when the structure is right*, but not *how much*. That's deliberate — this is a framework for finding, not for executing. Execution discipline lives with you, not in the code. A framework that tried to do everything would do nothing well.

The missing layer is mindset — and mindset varies by timeframe:

- **Swing (days to weeks):** structure and momentum are everything. Enter when the coil is tight and CMF confirms. Exit when the structure breaks. No thesis attachment — the trade is the trade.
- **Position (weeks to months):** quality starts to matter more than timing. A name with A+ fundamentals and 4/4 structure can absorb noise. You're riding the trend, not the tick.
- **Long-term (years):** the screener's quality filters become your margin of safety. Low debt, high margins, positive FCF — these aren't just filters, they are the reason a business survives a cycle that kills its competitors. Price paid matters enormously here. Buying quality at a discount to intrinsic value, not at peak enthusiasm, is what separates compounding from hoping.

Margin of safety isn't just a valuation concept — it applies at every level. In sizing: never bet so large that a wrong call breaks you. In timing: wait for structure to confirm before committing, not before. In thesis: always know the one thing that would make you wrong, and watch for it.

Charlie Munger's principles apply here more than any indicator: **common sense** — if the business can't explain how it makes money, neither can the screener. **Rationality** — separate what the price is doing from what the business is doing; they diverge constantly and converge eventually. **Inversion** — don't just ask what could go right; ask what has to *not* go wrong for this to work. **Circle of competence** — track themes you understand well enough to know when the thesis is breaking, not just when the price is.

The screener surfaces the candidates. Common sense and rationality close the gap.

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

`dividend_plays_for_longterm.py` is a curated list of dividend-paying names filtered for quality: payout ratio, FCF yield, net margin, ROE, debt/EV. Each entry is annotated with the thesis — why it belongs, what the moat is, what to watch. Sectors: financials, energy, industrials, consumer, healthcare, precious metals.

Run the extension scan on this universe directly:

```bash
python3 extension_scan.py --dividend
```

Produces the same HTML output as `--universe` — all dividend names sorted by extension zone, runway remaining before ceiling, RSI, and 10w slope. Opens in browser automatically.

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

Shown only for A and A+ names. Fires only when **both** RSI-14 divergence and MACD(12,26,9) histogram divergence agree on the same direction — on weekly bars, over 1 year of history.

| Signal | Meaning |
|---|---|
| `⬆ bull · RSI+MACD` | Price made a lower low, both RSI and MACD histogram made a higher low — momentum recovering ahead of price |
| `⬇ bear · RSI+MACD` | Price made a higher high, both RSI and MACD histogram made a lower high — momentum fading into the extension |
| `—` | No confirmed signal, or B grade (not evaluated) |

Single-indicator signals are silenced. Contradictions (RSI says bull, MACD says bear) are silenced. Near-flat swing pairs (< 0.75% price move between swing points) are silenced. What remains is a narrow, high-conviction read on weekly structure — not a trade trigger, but a directional bias on quality names worth attention.

### India (`india_screener.py`)
- Debt/EV ≤ 0.20 · Operating margin ≥ 8% · Net margin ≥ 5%
- ROE or ROA ≥ 10% · FCF yield ≥ 0% · P/E ≤ 80x
- FCF gap relief: None allowed when rev growth ≥ 50% AND net margin ≥ 10%
- Grading: A+ ≥ 6pts · A ≥ 4pts · OM weighted at 2pts (primary signal)
- Sector-aware thresholds for Financials and IT

## Dashboard Signals

- **ALIGNED** — price above all 4 MAs (50D, 20W, 10M, 20M)
- **PULLBACK** — above long-term MAs, below short-term (potential entry)
- **AVOID** — below long-term structure

Volume shown as `x(C)` = closed-day vs 20-day avg · `x(P)` = partial intraday

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

**Auto-sensing on-demand triggers — the next automation layer**

Today, on-demand tools like the monthly MA gate require a human to notice that conditions are right and click "Run workflow." That is one manual step too many at exactly the moment when timing matters most.

The next layer: an AI reading the scheduled screener outputs and deciding when to fire the on-demand screens automatically. The signals already exist in the data — NH/NL ratio inverting, multiple quality names clustering near monthly MAs simultaneously, CMF turning negative across a broad swath, breadth dropping below threshold. These are the same signals a human would use to decide "it's time to run the gate screen." An LLM with access to the latest HTML outputs can detect that pattern and trigger the GitHub Actions `workflow_dispatch` endpoint programmatically.

The Anthropic API + GitHub Actions API is the natural bridge. The `workflow_dispatch` design already makes every on-demand tool triggerable via a single API call. The sensing layer on top — reading structured screener data, detecting inflection conditions, firing the right tool at the right moment — is where AI earns its place in the loop. Not replacing judgment, but making sure the right question gets asked at the right time without a human having to remember to ask it.

## Disclaimer

For informational purposes only. Market dynamics change constantly — these outputs are auto-generated from Yahoo Finance data and may not reflect current conditions. Not tailored financial advice. Not a recommendation to buy, sell, or hold any security. Always do your own research.
