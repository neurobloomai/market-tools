# market-tools

Free, open-source market dashboards and quality stock screeners powered by Yahoo Finance.

## Tools

| File | Market | What it does |
|---|---|---|
| `dashboard.py` | 🇺🇸 US | Sector ETF momentum dashboard — MA signals across 50D/20W/10M/20M |
| `india_dashboard.py` | 🇮🇳 India | NSE sector index briefing — same MA framework for Indian markets |
| `screener.py` | 🇺🇸 US | Quality growth screener — low debt, high ROIC, strong margins, FCF |
| `india_screener.py` | 🇮🇳 India | India quality growth screener — NSE universe across key themes |
| `aligned_screener.py` | 🇺🇸 US | Weekly MA alignment scanner — 4/4 aligned names, squeeze setups, CMF, RS vs SPY, A/D Line + OBV divergence |
| `weekly_snapshot.py` | 🇺🇸 US | Appends weekly alignment snapshot to `weekly_notes.md` |
| `india_aligned_screener.py` | 🇮🇳 India | Weekly MA alignment scanner for India — same framework, RS vs NIFTY 50, A/D Line + OBV divergence |
| `india_weekly_snapshot.py` | 🇮🇳 India | Appends weekly India alignment snapshot to `india_weekly_notes.md` |
| `dividend_plays_for_longterm.py` | 🇺🇸 US | Curated long-term dividend universe — quality-filtered, thesis-annotated |
| `run_aligned.sh` | — | Cron entry point — runs all four scripts (US + India), auto-pushes to GitHub |

## Live Outputs

**GitHub Pages → https://neurobloomai.github.io/market-tools/**

Updated automatically every Monday via GitHub Actions — no server, no local machine needed:

| Page | Market | What it shows | Schedule |
|---|---|---|---|
| [market_briefing.html](https://neurobloomai.github.io/market-tools/market_briefing.html) | 🇺🇸 US | Sector ETF momentum dashboard — MA signals, day change, volume, yield | Monday 8am EST |
| [quality_screener.html](https://neurobloomai.github.io/market-tools/quality_screener.html) | 🇺🇸 US | Quality growth screener — margins, ROE, FCF, debt filter | Monday 8am EST |
| [aligned_screener.html](https://neurobloomai.github.io/market-tools/aligned_screener.html) | 🇺🇸 US | 4/4 MA alignment · FullCoil squeeze · MTF · CMF · RS vs SPY · A/D Line · OBV | Monday 8am EST |
| [india_briefing.html](https://neurobloomai.github.io/market-tools/india_briefing.html) | 🇮🇳 India | NSE sector index dashboard — same MA framework, RS vs NIFTY | Monday 8am IST |
| [india_screener.html](https://neurobloomai.github.io/market-tools/india_screener.html) | 🇮🇳 India | India quality screener — same filters, NSE universe | Monday 8am IST |
| [india_aligned_screener.html](https://neurobloomai.github.io/market-tools/india_aligned_screener.html) | 🇮🇳 India | 4/4 MA alignment · FullCoil squeeze · MTF · CMF · RS vs NIFTY 50 · A/D Line · OBV | Monday 8am IST |

Weekly snapshots: [`weekly_notes.md`](weekly_notes.md) · [`india_weekly_notes.md`](india_weekly_notes.md)

## Automation

Runs entirely on GitHub's infrastructure via two scheduled workflows:

| Workflow | Schedule | What runs |
|---|---|---|
| [Weekly Screener — US](.github/workflows/weekly_us.yml) | Monday 8am EST | `dashboard.py` → `weekly_snapshot.py` → `screener.py` → `aligned_screener.py` |
| [Weekly Screener — India](.github/workflows/weekly_india.yml) | Monday 8am IST | `india_dashboard.py` → `india_weekly_snapshot.py` → `india_screener.py` → `india_aligned_screener.py` |

Each workflow checks out the repo, installs `yfinance`, runs the scripts, and commits the updated HTML and markdown files back — fully automated, zero manual steps.

You can also trigger either workflow manually anytime from the **Actions** tab on GitHub.

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

**Three-tier universe structure:**

| Tier | What it is | Gate to next tier |
|---|---|---|
| `UNIVERSE` | Quality cleared, structure confirmed — core tracked names | Already here |
| `WATCHLIST` | Moat proven, one or two metrics blocking — scanned weekly | Metric clears the filter |
| `FUTURE_RADAR` | Real product, real revenue, path to profit unclear — not scanned | OM turns positive + FCF inflects |
| Removed entirely | Pre-revenue ventures, survival risk, all filters blocking | Not tracked |

Names removed from watchlist in first cleanup: SMR, OKLO, XE (pre-revenue nuclear), IONQ (quantum), CRSP/NTLA/BEAM (gene editing), RXRX/RARE (biopharma), MRNA/BNTX (revenue collapsed), ASTS/LUNR (space ventures). India: OLAELEC (deeply loss-making EV in structurally competitive market). These are interesting themes — not watchlist material.

Names removed from watchlist in second cleanup: PCG (wildfire liability structural, not a metric), FCX (own note said "not a compounder" — cleaner expressions already in universe), SEDG (Chinese competitor share loss is structural, not cyclical), KLAR (credit cycle risk inherent to BNPL model), INOD (AI model efficiency reducing annotation demand is an existential business risk), AMKR (services margin ceiling structural, B-grade at best), CELH (energy drink competitive moat fragile vs Monster/Red Bull), MRAM (TAM too small, speculative angle). Moved to FUTURE_RADAR: CORZ (BTC miner pivot unproven), MOD (B grade, multiple blockers), UPST (credit cycle structural, gate is FCF + converts + through-cycle proof).

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

## Dividend Universe

`dividend_plays_for_longterm.py` is a curated list of 57 dividend-paying names filtered for quality: payout ratio, FCF yield, net margin, ROE, debt/EV. Each entry is annotated with the thesis — why it belongs, what the moat is, what to watch. Sectors: financials, energy, industrials, consumer, healthcare, precious metals.

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

# US screener
python screener.py

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

## India SIP Watchlist

`SIP_WATCHLIST` in `india_screener.py` — high-quality toll-booth businesses on India's financial system growth. Not traded. Owned regularly via SIP regardless of short-term price.

Common thread: asset-light, fee or infrastructure income, no balance sheet risk, compound directly with India's financial deepening.

| Name | What it is | Why SIP |
|---|---|---|
| **HDFCAMC** | HDFC Asset Management — second largest AMC by AUM | Fee income as % of AUM; every SIP rupee in India grows their AUM; financialisation of Indian savings is early innings |
| **CAMS** | Computer Age Management Services — processes ~70% of all India MF transactions | More defensive than any single AMC — wins regardless of which AMC wins market share; pure infrastructure toll |
| **CDSL** | Central Depository Services — every demat account runs through CDSL | India adding ~3M demat accounts/month; account maintenance + transaction fees compound with investor base growth |

All three are A+ in the India screener. The hierarchy: CAMS owns the road, CDSL owns the parking lot, HDFCAMC owns one of the cars — all three compound with the same structural tailwind.

## Future Vision — The Missing Layer

The framework finds the setup. It cannot tell you how much to size it.

That gap is real and acknowledged. Position sizing is where most losses actually happen — not from wrong stock picks, but from right picks sized incorrectly that get shaken out before the thesis plays out. A 25% drawdown on a 2% position is noise. The same drawdown on a 20% position forces a decision you shouldn't have to make.

The vision: a personal risk profile layer that takes the screener's signal quality as one input and the user's actual financial parameters as another — account size, income stability, time horizon, obligations — and returns a position size that survives the specific drawdown that setup could produce. Not a static conservative/moderate/aggressive bucket. Dynamic: a 4/4 + CMF+ + RS 1.5x + A+ confluence earns more size than a borderline 3/4 setup. The setup quality and the personal risk profile together determine how much.

This is not a feature that can be added with a few lines of code. The reasoning layer is solvable — LLMs can already do this kind of contextual sizing analysis if inputs are structured correctly. What's hard is everything around it: regulatory (personalized sizing guidance in the US touches SEC/FINRA territory), accuracy (people systematically overestimate drawdown tolerance until they're actually in one), and trust (a sizing recommendation is only as good as what the user inputs honestly about their real situation).

Whether this gets built here, somewhere else, or not at all — the gap it would close is real. The screener half works. The survivability half doesn't exist yet at the individual stock level, personalized to who you actually are financially. That combination is where the value is.

## Disclaimer

For informational purposes only. Not financial advice.
