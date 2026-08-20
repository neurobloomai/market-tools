"""
Quality Growth Stock Screener
Universe: ~115 quality growth names across tech, financials, healthcare, industrials, and consumer.
Filters: Low Debt + High ROIC + Strong Margins + Free Cash Flow + Valuation sanity
Run: python screener.py

Data: Yahoo Finance via yfinance
Disclaimer: For informational purposes only. Not financial advice.
"""

import _yf_cache  # noqa: F401 — install HTTP cache before yfinance fetches
import yfinance as yf
import warnings, os, json, webbrowser, requests
from datetime import datetime, date
from concurrent.futures import ThreadPoolExecutor
warnings.filterwarnings('ignore')

_SCREENER_CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'screener_data_cache.json')
_SCREENER_CACHE = None  # module-level singleton — loaded once, reused across all get_fundamentals() calls

def _load_screener_cache():
    try:
        with open(_SCREENER_CACHE_FILE) as f:
            return json.load(f)
    except Exception:
        return {}

def _save_screener_cache(cache):
    try:
        with open(_SCREENER_CACHE_FILE, 'w') as f:
            json.dump(cache, f, indent=2)
    except Exception:
        pass

def _get_cache():
    global _SCREENER_CACHE
    if _SCREENER_CACHE is None:
        _SCREENER_CACHE = _load_screener_cache()
    return _SCREENER_CACHE

FMP_API_KEY = os.environ.get('FMP_API_KEY', '')

def get_fmp_forward_pe(ticker, price):
    """FMP fallback for forward P/E — only called when yfinance returns implausible data."""
    if not FMP_API_KEY or not price:
        return None
    try:
        url = f"https://financialmodelingprep.com/api/v3/analyst-estimates/{ticker}?apikey={FMP_API_KEY}"
        resp = requests.get(url, timeout=5)
        if resp.status_code != 200:
            return None
        data = resp.json()
        if not data or not isinstance(data, list):
            return None
        today = date.today().isoformat()
        future = [e for e in data if e.get('date', '') > today]
        if not future:
            return None
        eps = future[0].get('estimatedEpsAvg')
        if not eps or eps <= 0:
            return None
        return round(price / eps, 1)
    except Exception:
        return None

def calc_rsi(closes, period=14):
    delta    = closes.diff()
    gain     = delta.clip(lower=0)
    loss     = (-delta).clip(lower=0)
    avg_gain = gain.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    avg_loss = avg_loss.replace(0, 1e-10)
    rs       = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def get_tech_signal(ticker):
    """
    Dual confirmation on weekly bars (1 year history):
    RSI-14 divergence AND MACD(12,26,9) histogram divergence must agree.
    Single-indicator signals and contradictions are silenced.
    Returns ('bull'|'bear', 'RSI+MACD') or None.
    """
    try:
        hist = yf.Ticker(ticker).history(period='1y', interval='1wk')
        if len(hist) < 35:
            return None
        closes = hist['Close'].dropna()
        highs  = hist['High'].reindex(closes.index)
        lows   = hist['Low'].reindex(closes.index)
        RECENCY = 4

        def _swings(arr, mode='high'):
            if mode == 'high':
                return [i for i in range(1, len(arr)-1) if arr[i] >= arr[i-1] and arr[i] >= arr[i+1]]
            return [i for i in range(1, len(arr)-1) if arr[i] <= arr[i-1] and arr[i] <= arr[i+1]]

        MIN_SWING = 0.0075  # price must move ≥ 0.75% between swings — eliminates flat noise
        MAX_SWING = 0.15    # price must NOT move > 15% between swings — eliminates distress/freefall signals
                            # true divergence: price barely makes new extreme, momentum clearly disagrees
                            # if price crashes 15-20% between swing lows, that's continuation, not divergence

        def _divergence(indicator_vals, price_h, price_l, n):
            sh = _swings(price_h, 'high')
            if len(sh) >= 2:
                i2, i1 = sh[-1], sh[-2]
                if (n-1-i2) <= RECENCY and price_h[i2] > price_h[i1] and indicator_vals[i2] < indicator_vals[i1]:
                    swing = (price_h[i2] - price_h[i1]) / price_h[i1]
                    if MIN_SWING <= swing <= MAX_SWING:
                        return 'bear'
            sl = _swings(price_l, 'low')
            if len(sl) >= 2:
                i2, i1 = sl[-1], sl[-2]
                if (n-1-i2) <= RECENCY and price_l[i2] < price_l[i1] and indicator_vals[i2] > indicator_vals[i1]:
                    swing = (price_l[i1] - price_l[i2]) / price_l[i1]
                    if MIN_SWING <= swing <= MAX_SWING:
                        return 'bull'
            return None

        # RSI-14 divergence
        rsi = calc_rsi(closes, 14).dropna()
        rsi_sig = None
        if len(rsi) >= 5:
            idx = rsi.index
            rsi_sig = _divergence(rsi.values, highs.loc[idx].values, lows.loc[idx].values, len(rsi))

        # MACD(12,26,9) histogram divergence
        ema12    = closes.ewm(span=12, adjust=False).mean()
        ema26    = closes.ewm(span=26, adjust=False).mean()
        macd     = ema12 - ema26
        macd_sig_line = macd.ewm(span=9, adjust=False).mean()
        histo    = (macd - macd_sig_line).dropna()
        macd_sig = None
        if len(histo) >= 5:
            idx = histo.index
            macd_sig = _divergence(histo.values, highs.loc[idx].values, lows.loc[idx].values, len(histo))

        # Only fire when both agree — contradictions and lone signals are silenced
        if rsi_sig and macd_sig and rsi_sig == macd_sig:
            return (rsi_sig, 'RSI+MACD')

        return None
    except Exception:
        return None

# Broad universe — S&P 500 quality names worth screening
UNIVERSE = [
    'AAPL','MSFT','META','NVDA','GOOGL','V','MA','UNH','LLY','JPM',
    'JNJ','PG','HD','ABBV','MRK','TMO','ACN','AVGO','TXN',
    'QCOM','DHR','AMAT','LRCX','KLAC','MCHP','ADI','SNPS','CDNS',
    'NXPI',                       # NXP Semiconductors — auto semiconductor leader (EV power management, ADAS radar processing, V2X communication, secure NFC/payments); every EV has 2-3x NXP content vs ICE; Qualcomm bid $44B for them (blocked by China regulators) — tells you the franchise quality; GrossM 56.1%, OM 30.4%, NM 22.6%, ROE 27.9%, FCF 6.0%, D/EV 16.2%, RevG 19.5%; 6/6 gates; A+; fwdPE 12.9x cheap for this quality (market pricing it as commodity chipmaker, not EV content compounder); added 2026-08-12
    'CRM','NOW','FTNT','PANW',
    'CHKP',                       # Check Point Software — original network firewall pioneer (Israel); NGFWs + Harmony (endpoint/mobile/email) + CloudGuard (CSPM/workload) + Quantum (network); deeply embedded in enterprise security stacks globally; GrossM 86.7%, OM 30.5%, NM 38.8%, ROE 36.7%, D/EV 0.149, FCF 43.0%, RevG 1.3% — passes all 7 gates (A+); RevG 1.3% is the honest concern: PANW/FTNT/CRWD are taking share as enterprises migrate to SASE/zero-trust away from legacy perimeter firewall; fwdPE 11.3x = market pricing slow-growth toll collector correctly; moat = installed base stickiness (ripping out firewalls requires network re-architecture, not a software swap) + certification/compliance requirements lock in government/financial clients; grade A+; watch: RevG trajectory — flat is manageable, decline is the exit signal; added 2026-08-07
    'ORCL',                    # Oracle — enterprise software franchise (database + ERP) + OCI cloud infra; cloud commitments driving 20% RevG; OM 36%, NM 25%, GrossM 66%, ROE 53%; D/EV 0.305 (Cerner acq + OCI build debt) + FCF -6.1% (contracted OCI datacenter capex, not speculative — same pattern as CEG nuclear build) both blocking; grade B; gates: D/EV ≤ 0.20 + FCF inflection as OCI capex cycle peaks; added 2026-07-08
    'VEEV','WDAY','TTD','PAYC',
    'PCTY',                       # Paylocity — cloud-native HCM/payroll for mid-market employers (50-5,000 employees); modern UI + community features vs legacy ADP/Paychex = structural churn disadvantage for incumbents; GrossM 69.3%, OM 19.1%, NM 15.2%, ROE 22.0%, FCF 4.5%, D/EV 1.8%, RevG 11.0%; 6/6 gates; A+; fwdPE 15.0x cheap for quality SaaS with PAYC already in universe; added 2026-08-12
    'LRN',                      # Stride Inc. (formerly K12) — #1 US virtual K-12 public school operator; state per-pupil funding follows the enrolled student → government contract model with sticky recurring revenue; regulatory moat: launching a virtual school requires state approval, district contracts, accreditation — not replicable quickly; Career Learning programs (Destinations Career Academy) expanding into workforce/vocational education; GrossM 38.4%, OM 20.8%, NM 12.2%, ROE 20.1%, D/EV 0.176, FCF 7.0%, RevG 2.7% (post-COVID enrollment normalization, not structural decline), fwdPE 8.9x — very cheap; -51% from 52w high ($171 → $84) — post-COVID enrollment reset + state legislative uncertainty in some markets (states occasionally revisit virtual school funding caps); grade A; risk: state-by-state regulatory changes could cap enrollment or reduce per-pupil rates — watch for state legislation each year; added 2026-08-05
    'TYL',                      # Tyler Technologies — GovTech monopoly; courts, property tax, public safety (CAD/e-Citations), utilities billing for US local/county/state governments; installed bases are 15-30yr relationships — government agencies cannot self-migrate (compliance + data continuity + staff retraining make switching effectively impossible); cloud migration from on-premise licenses = revenue inflection + margin expansion runway; GrossM 46.8% (services mix drags blended — software-only ~75%), OM 17%, NM 13.3%, D/EV 0.003 (near-zero debt), ROE 8.9% (acquisition intangibles suppress — ROIC cleaner), RevG 8.6% TTM but FY1 15.1% (cloud ARR accelerating); fwd P/E 22.5x; blockers: GrossM/ROE/RevG all 1-2% below gates, all have resolution paths as cloud mix grows; gate: cloud revenue crossing majority of ARR + ROE toward 12% as acquisition goodwill amortizes + RevG reaccelerating above 10%; added 2026-07-29
    'ZM',                            # Zoom Video — post-COVID valuation reset complete; A+ (7/7): OM 25%, NM 42%, GrossM 78%, ROE 22%, D/E 0.006, FCF $1.98B (~7.6% FCF yield at $87), RevG 5.5%; near-zero debt + massive cash pile; AI Companion + Zoom Contact Center = monetization runway; fwd P/E 13.8x, priced like value, runs like software; 2/4 MA, below MA10w $98 — scan will surface on weekly alignment
    'BRK-B','CB','AFL','TRV','ALL','PGR','AJG','AON','WTW','CINF',
    'NVO','ISRG','EW','IDXX','PODD','WST',
    'ZTS',                        # Zoetis — #1 global animal health company (Pfizer spinoff 2013); companion animal biologics Librela (dog OA) + Cytopoint (atopy) = monoclonal antibodies with no generic pathway (biologics have no Hatch-Waxman); vet brand loyalty + treatment protocol embeds = pricing power; livestock segment (cattle/swine/poultry) diversifies; pet humanization = secular demand regardless of cycle; GrossM 71.7%, OM 38.0%, NM 28.2%, ROE 80.2% (buyback-suppressed equity), D/EV 0.233 only blocker, FCF 24.1%, RevG 0.3%; grade B; gate: D/EV ≤ 0.20 as debt amortizes + RevG reaccelerating; added 2026-08-07
    'MCO','SPGI','MSCI','ICE','CME','CBOE','FDS','BR','NDAQ',
    'MORN',                       # Morningstar — financial data + research franchise; Morningstar star rating is THE global reference standard for mutual fund/ETF quality (brand moat = advisors and retail investors use it as a shortcut, can't be replicated); PitchBook (private market VC/PE deal data) is the growth engine competing with Bloomberg/Preqin; Morningstar Direct deeply embedded in institutional investment workflows (portfolio analytics, compliance, reporting = high switching costs); DBRS credit ratings + Sustainalytics ESG data add diversification; GrossM 61.0%, OM 20.6%, NM 15.3%, ROE 30.6%, D/EV 0.153, FCF 18.1%, RevG 9.6% — all 7 gates pass (A+); fwdPE 14.2x cheap for the data moat quality; added 2026-08-07
    'ODFL','EXPD','XPO','JBHT','SAIA','KNSL','RLI','CASH','FICO',
    'ROL','CTAS','CPRT','ADP','PAYX','TRI','VRSK','IT',
    'JKHY',                    # Jack Henry & Associates — core banking + payments software for community banks and credit unions (9,000+ clients); three segments: Core (core banking systems), Payments (ACH/check/card processing), Complementary (digital banking, treasury, fraud); same structural DNA as BR (Broadridge) — recurring subscription + processing fees on deeply embedded financial infrastructure, 80%+ recurring revenue; switching cost = 18-24mo core banking migration project with regulatory examination risk, not an IT decision; GrossM 44.1%, OM 24.4%, NM 20.6%, ROE 24.9%, D/EV 0.012 (near-zero debt, pristine balance sheet), FCF 3.3%; RevG 8.7% (slow, steady — community bank market is mature, not a grower but durable); fwdPE 22.1x; -19% from 52w high ($193 → $157); grade A; added 2026-08-05
    'CRUS',                        # Cirrus Logic — fabless audio + power management chips for Apple (80-85% revenue); audio codecs + HANA noise-canceling chips (AirPods) + PMICs custom-designed per iPhone generation; once spec'd into an iPhone cycle Apple can't swap mid-generation without re-certifying audio quality — 13yrs of deep collaboration creates real switching costs; expanding into PMICs (power management ICs) reduces pure audio concentration; GrossM 52.8%, OM 20.1%, NM 20.7%, ROE 20.3%, D/EV 0.022 (net cash: $888M cash vs $134M debt), FCF 8.4%, RevG 5.7%, fwdPE 13.8x; -28% from 52w high ($180 → $130) — market discounting Apple concentration risk; same discount structure as EXEL (real business, visible risk, low multiple); grade A; added 2026-08-05
    # ── Memory / Storage cluster ──────────────────────────────────────────────
    'MU',    # Micron Technology — primary US supplier of HBM (High Bandwidth Memory) for NVIDIA AI GPUs; every H100/H200/B200 ships with HBM3E, MU alongside SK Hynix and Samsung; also DRAM + NAND but HBM is the structural AI demand floor with longer contracted pricing cycles than commodity memory; GrossM 72.6%, OM 80.4%, NM 55.9%, ROE 66.6%, D/EV 0.007 (near-zero debt), FCF 0.9% (capex-heavy fab = thin FCF at cycle peak, structural not deterioration); RevG strong; A+ 7/7; memory is cyclical but HBM contracted duration reduces amplitude vs commodity DRAM/NAND; key lens: HBM supply share vs SK Hynix as AI GPU volumes compound
    'SNDK',  # SanDisk — pure-play NAND flash spun out of Western Digital (Feb 2025); enterprise + consumer SSDs via 50/50 JV with Kioxia (BiCS NAND — one of only 3 fully integrated NAND stacks globally alongside Samsung/Micron); A+ grade; 87w STRUCT blank (insufficient spinoff history); NAND more commoditized than DRAM — pricing cycles more violent; no HBM exposure (DRAM-only for AI accelerators); QQQ constituent; added UNIVERSE 2026-08-19
    'STX',   # Seagate Technology — world's largest pure-play HDD maker; nearline (datacenter/cloud) dominant; HAMR (Heat-Assisted Magnetic Recording) density roadmap to 30TB→40TB+ drives = premium ASP moat; AI creates data faster than NAND can store it cheaply (HDD ~10x cheaper per TB) = structural hyperscaler cold-storage demand; GrossM 45.6%, OM 43.1%, NM 26.1%, D/EV 0.021, FCF 1.1%, RevG 48.5%; ROE 371.5% artifact (negative book equity from buybacks, real ROIC strong); A+ 7/7; HDD ≠ NAND ≠ DRAM — complementary in the datacenter stack, not competing; added 2026-08-08
    # ─────────────────────────────────────────────────────────────────────────
    'MPWR','MRVL','ITW','ROP','SYK','BSX','AMZN',
    'GEHC',                       # GE HealthCare — GE spinoff 2023; medical imaging (MRI, CT, PET, X-ray), ultrasound, patient monitoring, pharmaceutical diagnostics; installed base of hospital imaging systems = 10-15yr replacement cycles + mandatory service contracts (hospitals can't self-maintain these machines); GrossM 40.0%, OM 13.4%, NM 10.1%, ROE 20.1%, FCF 7.3%, RevG 5.8%; D/EV 0.277 only blocker (spinoff debt — same profile as TRU 0.279); grade B; gate: D/EV ≤ 0.20 as spinoff debt amortizes; added 2026-08-07
    'MTD','MANH','FAST','POOL','NVR','DHI','LEN','TOL','MKTX',  # MKTX: ICE acquisition offer 2026-08 — will be removed once deal closes; DOCS removed from inline — annotated entry below
    'ACGL',
    'CHD','CL','HSY','TJX','GIS','NFLX','LULU','WSM','KMB','DECK','RL',
    'ROST',                       # Ross Stores — off-price retail (#2 US off-price behind TJX); treasure-hunt model: buys excess/closeout inventory from brands at 20-60% below wholesale, passes savings to consumers; recession-resistant (trade-down effect) + expansion-resistant (off-price doesn't lose to e-commerce — discovery experience drives the model); GrossM 32.7% structural (off-price retail, same model exception as COST/TJX — margin is low by design, not quality failure); OM 13.4%, NM 9.7%, ROE 39.0%, FCF 2.6%, D/EV 6.0%, RevG 20.6%; 6/6 gates (GrossM exception); A+; fwdPE 28.7x; added 2026-08-14
    'COCO',                         # Vita Coco — coconut water category creator (60%+ US market share); asset-light distributor model; RevG 28.1%, GM 41%, OM 29.2% (rare for F&B), NM 15.5%, ROE 31.4%, D/EV 0.4%, FCF $105M — A+ all 7 filters; same playbook as MNST at earlier stage; 3/4 MA at add, sitting on MA20w ~$65.68 support after -21.5% pullback; gate to 4/4: MA10w reclaim above ~$74
    'HWM','FSLR','PLAB',           # promoted from watchlist — pass all quality filters
    'NXT',                        # Nextracker — solar tracker manufacturer (spun from Flex 2023); the motorized mounting systems that rotate solar panels to follow the sun throughout the day, improving output 20-25% vs fixed-tilt; every utility-scale solar farm needs trackers — Nextracker + Array Technologies = duopoly; GrossM 23.0% only blocker (hardware: steel frames, motors, controllers — structural, not a software margin story); OM 20.9%, NM 16.4%, ROE 27.2%, D/EV 0.003 (near-zero debt), FCF 2.2%, RevG 8.2%; grade A+; 1/4 MA at add time, slope -11.6% falling — structure broken in current solar sector rotation; UNIVERSE placement on fundamental quality + duopoly moat; gate to watch: 10w MA reclaim as solar buildout demand resumes; added 2026-08-06
    'WPM',                        # Wheaton Precious Metals — streaming model, 85% gross/65% net margin, zero debt, A+
    'VMC',                        # Vulcan Materials — largest US aggregates producer (crushed stone, sand, gravel, asphalt); geological moat: quarry permits near population centers take decades to get, competitors literally cannot replicate your deposit; infrastructure supercycle tailwind (IIJA/roads/bridges); OM 21.6%, NM 13.7%, ROE 13.2%, D/EV 0.119, FCF 2.3%, RevG 2.5%; GrossM 27.5% structural (mining — same exception as GE/GLW); grade A; added 2026-08-08
    'MLM',                        # Martin Marietta Materials — #2 US aggregates (crushed stone, sand, gravel, ready-mix concrete, asphalt); same geological moat as VMC — duopoly with VMC on US aggregates infrastructure; Sun Belt exposure (Texas, Southeast, Florida) = housing + infrastructure demand concentrated in fastest-growing US markets; OM 20.2%, NM 36.7% (NM>OM — asset sale gains likely in mix, watch for normalization), ROE 8.9% (1.1% below gate — acquisition equity base dilution from Blue Water/CRHM deals), D/EV 0.162, FCF 1.8%, RevG 21.0%; GrossM 28.2% structural (mining); grade B; added 2026-08-08
    'SHW',                        # Sherwin-Williams — architectural + industrial coatings; contractor channel moat: 5,000+ company-owned stores, PRO loyalty program (credit accounts, job-site delivery, color matching) = professional painters specify Sherwin by brand and don't switch; Valspar acquisition added industrial coatings + global reach; GrossM 49.0%, OM 18.1%, NM 11.0%, ROE 65.1%, D/EV 0.145, FCF 2.8%, RevG 7.5%; 7/7 gates; scorer grades B (artifact — grading system rewards GrossM ≥ 60% + OM ≥ 20% calibrated for software, not coatings manufacturing; moat supports UNIVERSE on fundamentals); 4/4 MA, RSI 61.5, MACD expanding; added 2026-08-08
    'ECL',                        # Ecolab — water treatment + hygiene + infection prevention embedded in every restaurant kitchen, hospital OR, hotel laundry, and food processing plant; you can't swap sanitation systems mid-operation = near-permanent customer relationships; GrossM 44.2%, OM 18.5%, NM 12.6%, ROE 22.0%, FCF 1.9%, D/EV 15.7%, RevG 9.7%; 6/6 gates; A+; 30+ yr Dividend Aristocrat; fwdPE 29.5x; added 2026-08-12
    'ZWS',                        # Zurn Elkay Water Solutions — commercial plumbing products (Zurn: drains, valves, flush valves, carriers spec'd into every commercial building) + drinking water (Elkay: bottle-filling stations now mandatory in schools/airports post-PFAS/lead concern); spec'd into architect drawings = switching cost before the building is built; GrossM 49.0%, OM 31.4%, NM 15.5%, ROE 16.9%, FCF 3.8%, D/EV 6.4%, RevG 10.5%; 6/6 gates; A+; fwdPE 25.0x; -7.2% from 52wH; added 2026-08-12
    'AWI',                        # Armstrong World Industries — commercial ceiling systems (mineral fiber + fiberglass acoustic tiles) + Architectural Specialties (metal/wood/glass custom ceilings); specification moat: architects write "Armstrong" into building specs by brand, contractors install by default — 60+ yr category dominance = brand is the spec; renovation cycle every 10-15yr on commercial ceilings = recurring demand; GrossM 40.3%, OM 21.6%, NM 18.6%, ROE 36.6%, D/EV 0.070, FCF 2.8%, RevG 11.2%; A+ 7/7; 4/4 MA, RSI 62.9, MACD expanding; added 2026-08-08
    'WDFC',                       # WD-40 Company — the brand that IS the category; sold in 176 countries, 2,000+ documented uses, consumers ask for "WD-40" not "lubricant" = brand pricing power with no generic substitution risk; emerging markets (Asia, India, Middle East) = structural multi-decade runway as manufacturing/auto maintenance grows; asset-light (brand-driven, no manufacturing moat needed); GrossM 55.8%, OM 20.7%, NM 13.2%, ROE 33.3% (D/EV 3.6% = genuine, not leverage-inflated), FCF 2.2%, RevG 24.3%, EPS G 45.5%; A+ 8/8; 3/4 MA (-1.9% below 10w, approaching reclaim), RSI 59.6, -22% from 52w high, vs 10m MA +8.2% (modest) — pullback from $298→$233 has done real work; added 2026-08-12
    'NEM',                        # Newmont — world's largest gold miner; 61.4% OM, 33.9% NM, ROE 25.8%, D/EV 0.049, FCF 8.7%, 45.8% rev growth (Newcrest acq); A+
    'HL',                         # Hecla Mining — largest US silver producer (Lucky Friday Idaho + Greens Creek Alaska — both Tier 1 deposits with decades of mine life); silver demand = monetary hedge + industrial (solar panels use silver paste, EVs, electronics) = structural tailwind beyond gold; OM 44.3% exceptional for a miner, GrossM 61.4%, NM 19.2%, ROE 22.2%, D/EV 0.002 (near-zero debt — remarkable for mining), FCF 3.0%, RevG 52.4%; A+ 7/7; caution: all metrics commodity-price sensitive — silver cycle amplifies everything; 2/4 MA (above 10w/87w, below 20w/43w), correcting from rally; slope -3.9%; added 2026-08-08
    'CDE',                        # Coeur Mining — silver + gold miner (Rochester Nevada silver mine expansion recently completed + Kensington Alaska gold + Wharf South Dakota gold + Silvertip BC); OM 20.3%, NM 26.8% (NM>OM — asset gains in mix, watch for normalization), ROE 12.8%, D/EV 0.041, FCF 4.5%, GrossM 56.6%, RevG 125.9% (Rochester expansion ramp + silver price cycle — not steady-state); A+ 7/7; same corrective chart as HL (2/4 MA, slope -4.2%); more junior than HL — Rochester ramp is the event, not a multi-decade deposit moat like Lucky Friday/Greens Creek; watch RevG normalizing as the base effect compresses; added 2026-08-08
    'CCJ',                        # Cameco — world's largest uranium producer; OM 18%, NM 18%, D/EV 0.022; ROE ~9-10% cycles with uranium price; nuclear fuel supply for the buildout
    'VRSN',                       # VeriSign — .com/.net registry monopoly, 88% gross/68% op margin, ROE distorted by buybacks (ROA 52%), toll collector
    'DLB',                        # Dolby Laboratories — audio + imaging IP licensor; Dolby Atmos (spatial audio) + Dolby Vision (HDR) + Dolby Digital on every smartphone, TV, laptop, cinema, gaming console globally; pure royalty model — device makers pay per unit shipped, near-zero marginal cost; GrossM 87.4%, OM 29.1%, NM 17.9%, D/EV 0.011 (near-zero debt), FCF 5.8%; ROE 9.4% is the only blocker — suppressed by large cash balance on the equity denominator, not weak returns on invested capital (ROIC is significantly higher); RevG 7.1% (mature, not a grower — but royalty stream is durable and growing with device volumes); gate: ROE crossing 10% as cash is deployed via buybacks or acquisitions; added 2026-07-29
    'RMBS',                       # Rambus — semiconductor IP licensing for memory interfaces (DDR4/DDR5/HBM/LPDDR5); every DRAM chip maker (Samsung/SK Hynix/Micron) licenses Rambus IP; HBM in all AI accelerators (Nvidia H100/H200/Blackwell) = every AI chip sale compounds the royalty stream; GrossM 80.4%, OM 36.7%, NM 31.7%, ROE 17.8%, D/EV 0.002, FCF 1.8%, RevG 20.4%; A+ 7/7; chart broken right now (1/4 MA, RSI 45.4, 10w slope -9.8% falling) — quality earns UNIVERSE, broken chart is the timing signal; watch for weekly MA recovery; added 2026-08-08
    'CRDO',                       # Credo Technology — AI datacenter interconnect silicon (SerDes/AEC), 68% gross/35% op margin, 157% rev growth, zero debt, A+
    'MTSI',                       # MACOM Technology — analog/mixed-signal for 800G/1.6T optical datacenter interconnects; D/EV 0.02, NM 16%, ROE expanding, A
    'SLDE',                       # Slide Insurance Holdings — specialty E&S insurer, 48% op margin, 40% FCF yield, ROE 60%, 38% rev growth, 4.6x P/E, A+
    'LGND',                       # Ligand Pharmaceuticals — pharma royalty owner + Captisol IP; Captisol is proprietary cyclodextrin drug formulation technology (improves solubility/stability) licensed to pharma manufacturers — once a drug is FDA-approved with Captisol, reformulating without it requires new regulatory studies = extreme switching costs baked into drug chemistry itself; royalty portfolio of ~130+ programs (approved + development-stage) diversifies single-drug risk; OmniAb transgenic antibody platform (spun off 2022) retained economic interest; GrossM 83.2%, OM 33.6%, NM 55.9%, ROE 17.1%, D/EV 0.081, FCF 2.5%, RevG 14.1%; A+; added 2026-07-29
    'EXEL',                       # Exelixis — oncology franchise anchored by cabozantinib (Cabometyx): RCC first-line (+ Opdivo combo), HCC second-line, differentiated thyroid cancer; GrossM 96.4% (near-royalty economics), OM 41.1%, NM 35.1%, ROE 41.0%, D/EV 0.013 (net cash: $777M cash vs $170M debt), FCF 4.8%, RevG 10%; fwdPE 13.9x — cheap relative to metrics because the market is pricing the cabozantinib patent cliff (~2030-2031); all 5 quality filters pass cleanly; grade A; the one-drug concentration risk is real (95%+ revenue from cabozantinib) — durability is conditional on zanzalintinib (XL092, Phase 3): broader kinase inhibitor, next-gen successor across RCC/colorectal/other; if Phase 3 delivers, EXEL re-rates and extends franchise a decade; if not, 2030 is the visible horizon; near 52w high ($56 vs $57.57 high); added 2026-08-05
    'ALNY',                       # Alnylam Pharmaceuticals — RNAi therapeutics platform (RNA interference silences disease-causing genes at the source); approved drugs: ONPATTRO (transthyretin amyloidosis), LEQVIO (cholesterol, Novartis partnership — royalty stream), GIVLAARI, OXLUMO; pipeline depth real; GrossM 79.7%, OM 17.9%, NM 16.1%, ROE 96.6% (exceptional), D/EV 0.103, FCF 0.9% (barely clears — commercial ramp capex), RevG 66.9%; A 7/7; technical: RSI 29.7, 0/4 MA, -33% below 87w MA — fully discounted entry zone, something hit this hard; watch for MA base formation; added 2026-08-08
    'REGN',                       # Regeneron Pharmaceuticals — Dupixent (dupilumab, IL-4/IL-13 blocker) is the franchise: atopic dermatitis + asthma + COPD (newly approved) + eosinophilic esophagitis = expanding indication runway; Eylea (anti-VEGF) facing biosimilar pressure but Dupixent more than offsetting; GrossM 44.5% (drug economics, low for biotech — real product not platform), OM 33.1%, NM 27.9%, ROE 14.0%, D/EV 0.037 (near-zero debt), FCF 3.8%, RevG 16.7%; A+ 7/7; 4/4 MA aligned, RSI 63.4, MACD expanding — not extended, clean entry; added 2026-08-08
    'INCY',                       # Incyte — Jakafi franchise pharma, zero debt, 26% op margin, 27% net margin, ROE 31%, A
    'UTHR',                       # United Therapeutics — PAH franchise (Tyvaso/Remodulin/Orenitram), zero debt, 41% OM, 40% NM, ROE 20%; xenotransplantation moonshot optionality, A+
    'BMRN',                       # BioMarin Pharmaceutical — rare disease ERT specialist; Voxzogo (achondroplasia, orphan drug moat) + hemophilia + PKU pipeline; OM 18%, GrossM 51%, D/E 0.23, FCF $459M, fwd P/E 9.1x; NM 8.3% (just under 10%) + ROE 4.5% (goodwill from acquired programs, not operational weakness) — 2 soft blockers; A (5/7); 3/4 MA, slope +1.08
    'EQT',                        # EQT — largest US nat gas producer, Appalachia low-cost, vertically integrated; 57% OM, 50% RevG, D/EV 0.14; powers the structures
    'RRC',                        # Range Resources — Appalachia nat gas, D/EV 0.10, 44% OM, ROE 21%; clean balance sheet, powers the structures
    'CF',                         # CF Industries — largest N. American ammonia/nitrogen producer; green ammonia pivot, D/EV 0.17, 34% OM, ROE 27%; foundation for structures, grades A
    'LIN',                        # Linde — world's largest industrial gases (O2/N2/H2); on-site plant model = permanent switching costs; 28% OM, 20% NM, D/EV 0.10, 8% RevG; slow compounder, never exciting, never disappoints; A
    'GWW',                        # W.W. Grainger — largest North American MRO (maintenance, repair, operations) distributor; 1.7M+ SKUs across safety, electrical, tools, HVAC, plumbing, janitorial — one-stop industrial supply; structural moat: scale + next-day delivery + customer credit accounts make switching painful for procurement teams; 53yr consecutive dividend growth (Aristocrat); OM 16.1%, NM 9.9%, ROE 46.1%, D/EV 0.045, FCF 2.1%, RevG 10.3%; GrossM 39.4% (0.6% below gate — structural for industrial distribution, same exception as FERG/FIX); grade A; added 2026-08-08
    'ZBRA',                       # Zebra Technologies — industrial IoT: barcode scanners, mobile computers, RFID readers, label printers for warehouse + retail + healthcare + manufacturing; every Amazon/UPS/FedEx fulfillment center runs on Zebra hardware; warehouse automation tailwind = every robotics/WMS deployment needs Zebra endpoints; software layer (Zebra Reflexis + Zebra Workcloud) adds recurring SaaS on top of hardware = razor/blades; GrossM 49.6%, OM 21.3%, NM 9.2%, ROE 15.3%, D/EV 0.144, FCF 3.2%, RevG 20.4%; 7/7 gates; grade A (NM 9.2% + ROE 15.3% both just below scoring thresholds — real business quality is higher than the scorer suggests); 4/4 MA fully aligned; RSI 88.6 overbought caution — quality earns UNIVERSE, RSI 88 says don't chase, wait for mean reversion; CMF +0.194 accumulation (run is real, just extended); 87w ext 30.6% moderate; added 2026-08-09
    'APH',                        # Amphenol — world's best-run precision connector + interconnect maker; every AI datacenter GPU board, every defense platform, every EV powertrain, every smartphone uses Amphenol connectors; three durable tailwinds: (1) AI: high-speed copper/optical interconnects inside server racks scale with GPU density — Amphenol is the design-win incumbent; (2) defense: sole-source qualifications on fighter jets/missiles/radars lock in decades of orders; (3) EV: high-voltage automotive connectors (800V architectures) growing faster than traditional auto; serial acquirer (~100+ bolt-ons in 20 years, all accretive — management discipline is the moat on top of the moat); GrossM 39.0% (1% below gate — precision manufacturing structural; GrossM has climbed from ~32% five years ago, trajectory is the signal), OM 29.8%, NM 17.7%, ROE 38.1%, D/EV 0.085, FCF 1.8%, RevG 55.0%; 6/7 gates (GrossM blocker only); grade A; 4/4 MA fully aligned, price $169 vs 87w $112 (+50.6% high extension), RSI 67.7, CMF -0.064 mild caution; gate to expand: GrossM crossing 40% sustained; added 2026-08-09
    'DOV',                        # Dover Corporation — diversified industrial manufacturer; 69yr dividend king; pump/compression equipment (biopharma, food, energy) + digital commerce (retail fueling tech, DEF payment systems) + climate & sustainable tech; GrossM 40.1%, OM 18.7%, NM 13.5%, ROE 14.9%, D/EV 0.109, FCF 3.2%, RevG 6.9%; grade A (7/7); added 2026-08-06
    'AYI',                        # Acuity Brands (Acuity Inc.) — #1 North American commercial LED lighting + controls (ABL segment) + Intelligent Spaces Group (ISG: atrius building management software + space intelligence); moat = lighting controls integration: once Acuity's control system is spec'd into a commercial building (schools, offices, warehouses, retail), switching requires electrical re-wiring + software migration + contractor retraining — sticky infrastructure install base; ISG software layer creates recurring revenue on top of the hardware; GrossM 48.7%, OM 16.1%, NM 10.3%, ROE 17.4%, D/EV 0.078, FCF 4.5%, RevG 1.6% (LED transition largely complete, future growth from controls/software mix shift), fwdPE 16.5x; near 52w high ($358 vs $380 high); grade A; slow compounder, not a flashy name — the infrastructure moat is real; added 2026-08-05
    'ETN',                        # Eaton Corp — electrical switchgear, circuit breakers, power distribution; sits above PWR in grid value chain, 16% OM, 14% NM, ROE 21%, D/EV 0.12
    'ROK',                        # Rockwell Automation — factory automation + industrial control systems (FactoryTalk suite); every auto/pharma/food/mining plant's OT layer; switching cost = multi-year recertification + production shutdown risk = nobody rips out a running Rockwell system; GrossM 49.1%, OM 21.0%, NM 13.4%, ROE 30.6%, FCF 2.6%, D/EV 6.8%, RevG 7.9%; 6/6 gates; A+; fwdPE 30.4x; added 2026-08-12
    'FIX',                        # Comfort Systems USA — mechanical/HVAC/electrical contractor; installs the cooling, plumbing, and power systems inside datacenters, hospitals, and industrial facilities; every hyperscaler build is a FIX contract (mechanical systems = 30-40% of datacenter construction cost); ROE 55.3% (exceptional for a contractor — asset-light execution model), D/EV 0.005 (near-zero debt), FCF 3.2%, NM 12.8%; GrossM 25.7% + OM 7.9% below services gate (contractor model — margins are thin gross, real economics in EBITDA/ROE); RevG 1.0% TTM distorted (FY0 69.9% acq math, FY1 23.6% clean look); grades A; fwd P/E 26.8x; gate: OM crossing 15% as datacenter project mix grows (higher complexity = better margins) + RevG normalizing above 10%; added 2026-07-29
    'NVT',                        # nVent Electric — electrical enclosures (HOFFMAN/SCHROFF brands) + cable management (CADDY/ERICO) + thermal management; picks-and-shovels for grid substations and AI datacenter builds (enclosures protect switchgear/power distribution, thermal mgmt = rack cooling); spun off from Pentair 2018; GrossM 37.0% (industrial, structural), OM 16%, NM 11.4%, ROE 13%, D/EV 0.069, FCF 0.9% (acquisition integration drag — Trafox/enclosure buys), RevG 53.5% (acq math, FY1 24.6%); fwd P/E 24.7x; blockers: GrossM (structural) + FCF (cyclical); gate: FCF crossing 3%+ as integration costs normalize + datacenter enclosure/cooling mix grows; added 2026-07-29
    'GLW',                        # Corning — specialty glass + optical fiber; #1 global optical fiber maker (~40% market share); AI datacenter GPU clusters need massive fiber runs between racks/switches/spine — every hyperscaler buildout compounds Corning's fiber volume; also: display glass (LCD/OLED panels, Gorilla Glass), semiconductor glass substrates (advanced packaging for AI chips), pharma vials; GrossM 36.0% only blocker (specialty materials manufacturing — glass + fiber = energy/raw material cost structure, structural not fixable); OM 14.6%, NM 10.2%, ROE 13.5%, D/EV 0.065, FCF 9.0%, RevG 16.6%; grade A; LT thesis: AI datacenter fiber demand is multi-year secular, not a one-cycle event; added 2026-08-07
    'HEI',                        # HEICO — aviation aftermarket parts monopolies, 30yr compounder; 25% OM, 16% NM, ROE 17%, D/EV 0.052, pricing power on FAA-approved parts, A+
    'CW',                         # Curtiss-Wright — defense electronics (nuclear instrumentation, aerospace actuation); 18% OM, 14% NM, ROE 20%, D/EV 0.04, defense cycle tailwind, A
    'WWD',                        # Woodward — energy control systems for aerospace (fuel/air metering on GE LEAP + P&W GTF engines) and industrial (natural gas engines, turbines, compressors); design-in moat: once Woodward's fuel system is spec'd onto an engine platform it rides that platform for 20-30yr production life — same embedded compounding logic as HEI but on the OEM side rather than aftermarket; OM 15.4%, ROE 21.1%, RevG 23.4%, low debt; slow compounder, not a flashy name; added 2026-07-30
    'GE',                         # GE Aerospace — world's #1 jet engine maker (LEAP for 737MAX/A320neo + GE9X for 777X); razor/blades model: engines sold at thin gross margins, real economics in 20yr service/parts contracts (LEAP fleet hours compounding for decades); GrossM 31.5% only blocker (structural OEM hardware — same exception as NXT/HWM); OM 18.9%, NM 19.0%, ROE 46.6%, D/EV 0.052, FCF 15.8%, RevG 21.1%; grade A; added 2026-08-07
    'GD',                         # General Dynamics — diversified defense prime; four segments: Aerospace (Gulfstream business jets, highest-margin ~20%+ OM), Marine (nuclear submarines + destroyers for US Navy, sole-source), Combat Systems (Abrams M1A2 tanks, Stryker, Piranha), Technologies (DoD/IC IT services + software); Gulfstream G700/G800 backlog surging as Boeing 737/787 delays redirect corporate fleet buyers; submarine builds are decade-long sole-source contracts (Virginia-class + Columbia-class nuclear); Abrams is the US Army's primary battle tank for 30+ years; GrossM 15.4% (defense prime structural — cost-plus contracts compress gross, economics live in operating/FCF), OM 10.4%, NM 8.2%, ROE 17.8%, D/EV 0.087, FCF 4.1%, RevG 8.1%, fwdPE 20.8x; near 52w high ($385 vs $400 high) — market already pricing the defense supercycle; grade B; added 2026-08-05
    'LMT',                        # Lockheed Martin — world's largest defense contractor ($77B revenue, $165B+ backlog = 2yr+ revenue locked); F-35 Joint Strike Fighter (~$12B/yr program, 30yr production + sustainment lifecycle), PAC-3 missile defense, HIMARS (demand surge from Ukraine/NATO), Javelin anti-tank missiles, Aegis combat system, Sikorsky helicopters, C2BMC nuclear command-and-control; backlog visibility is the moat — governments sign multi-year production contracts, not spot orders; GrossM 11.8% (thinner than GD — more cost-plus heavy across all segments), OM 12.0%, NM 8.2%, ROE 89.2% (buyback-distorted: aggressive share repurchases have reduced equity book value denominator to near-zero — headline is misleading, judge by FCF generation + ROIC instead), D/EV 0.134, FCF 3.6%, RevG 10.5%, fwdPE 18.0x; -15% from 52w high ($692 → $589); grade B; added 2026-08-05
    'TW',                         # Tradeweb — electronic bond/derivatives trading platform; 46% OM, 40% NM, ROE 14%, D/EV 0.007, structural shift from voice to electronic fixed income, A+
    'EFX',                        # Equifax — credit bureau oligopoly (Equifax/Experian/TransUnion = 3 players, regulatory + data network effects make entry near-impossible); 800M+ consumer credit records globally; GrossM 55.5%, OM 17.3%, NM 10.7%, ROE 14.3%, FCF 4.6%, RevG 10.6%; D/EV 0.208 only blocker (0.008 above 0.20 threshold — acquisition-driven, amortizes on FCF); moat = data network compounding: more lenders → more credit inquiries → more data → more accurate scores → more lenders can't opt out; EWS (The Work Number, employment/income verification) is the second moat inside Equifax — sole holder of 600M+ employment records from payroll providers, used for mortgage underwriting + benefits verification; grade B; 2/4 MA, -19.9% below 87w — in base, not yet recovering; added 2026-08-06
    'TRU',                        # TransUnion — same credit bureau oligopoly as EFX (Equifax/Experian/TransUnion); GrossM 58.7%, OM 19.7%, NM 15.1%, ROE 15.6%, FCF 5.3%, RevG 14.9% — metrics slightly stronger than EFX across the board; D/EV 0.279 only blocker (PE-era LBO debt from Advent/Goldman taking it private pre-2015 IPO, amortizing on real FCF); same data network moat: credit file on 1B+ consumers globally, lenders structurally dependent on all three bureaus for risk decisioning — switching out one is not an option; international mix (India, Canada, UK, Africa) adds geographic diversification EFX has less of; grade B; 3/4 MA aligned, slope +3.6%, RSI 54.8, MACD expanding — better technical structure than EFX at add time; added 2026-08-06
    'ALAB',                       # Astera Labs — AI datacenter connectivity (PCIe/CXL retimers), 68% gross/35% op margin, zero debt, 200%+ rev growth, A+; promoted from watchlist
    'UBER',                       # Uber — rideshare + delivery marketplace; 14.6% OM, 15.9% NM, ROE 35%, D/EV 0.08, FCF 4.4%; platform flywheel, grades A
    'ABNB',                       # Airbnb — asset-light home-sharing marketplace; NM 19.9%, ROE 32%, D/EV 0.037, FCF solid; yfinance OM distorted by SBC/charges (true OM ~12-13%), quality real
    'BKNG',                       # Booking Holdings — Booking.com/Priceline/Kayak/OpenTable; near-monopoly on European online hotel bookings; asset-light merchant model (no hotel ownership); GrossM 87.2%, OM 34.4%, NM 25.5%, FCF 4.8%, D/EV 12.8%, RevG 8.1%; ROE yfinance gap (negative book equity from buybacks — same artifact as MCD/CTAS, not real); 5/6 gates; A+; fwdPE 17.1x cheap for dominant OTA; added 2026-08-12
    'HLT',                        # Hilton — asset-light hotel brand franchise (owns almost no hotels, earns management + franchise fees on 8,000+ properties globally); GrossM 79.0%, OM 63.0% (pure fee income, no hotel capex drag), NM 31.0%, FCF 1.9%, D/EV 16.7%, RevG 2.5%; ROE yfinance gap (negative book equity from aggressive buybacks — structural, not deteriorating); 5/6 gates; A+; same franchise fee model as MCD; added 2026-08-12
    'ANET',                       # Arista Networks — AI/cloud datacenter networking switches; 42.7% OM, 38.3% NM, ROE 31.5%, zero debt, 35% rev growth, A+; stays in universe until MA10w crosses below MA20w (structure break) or AI datacenter networking thesis breaks — slope cooling is not a structural event
    'SCHW',                       # Charles Schwab — brokerage/custody platform; 49.4% OM, 38% NM, ROE 19.1%, 15.8% rev growth; D/EV 0.465 + FCF None fail filter (structural brokerage model, not deterioration); grades A on true business quality
    'IBKR',                       # Interactive Brokers — electronic brokerage; 76.8% OM, 93% gross, ROE 23.6%, 16.8% rev growth, net cash position (D/EV -0.922); FCF None only blocker (yfinance doesn't report for brokerages); grades A+, 4/4 MA aligned at add time
    'KRYS',                       # Krystal Biotech — gene therapy dermatology (B-VEC for RDEB); 94.2% gross/46.1% OM/53.9% NM, near-zero debt, 31.9% rev growth, A+; 4/4 MA aligned at add time
    'NBIX',                       # Neurocrine Biosciences — CNS/endocrine specialist (Ingrezza); 22.8% OM, 21.6% NM, ROE 22.5%, FCF 3.8%, 42.2% rev growth, A+; 4/4 MA aligned at add time
    'HOOD',                       # Robinhood Markets — fintech brokerage/crypto; 92.2% gross, 38.5% OM, 41.1% NM, ROE 21.5%, 15.1% rev growth; D/EV improved to 0.166 (was 0.22 blocker); FCF None (brokerage model); grades A, 3/4 MA at promotion
    'PLTR',                       # Palantir — AI/data analytics platform (AIP + Foundry + Gotham); government + commercial flywheel; A+ quality; promoted from watchlist
    'RDDT',                       # Reddit — social platform + AI data licensing; GrossM 91.4%, OM 27.6%, NM 28.6%, ROE 26.2%, D/EV 0.001, RevG 69.1%; already profitable on operating basis faster than anyone expected post-IPO (March 2024); AI data licensing (Google, OpenAI pay Reddit for authentic human-generated training data) = new revenue layer on top of maturing ad business; Reddit is the last place on the internet with authentic community discussion at scale — scarce and increasingly valuable; FCF 1.6% thin but positive; fwdPE 19.5x cheap for 69% growth; A+; added 2026-07-30
    'TSM',                        # Taiwan Semiconductor — world's most advanced foundry (TSMC); 3nm/2nm leader; OM 58.1%, NM 46.5%, D/EV 0.069, FCF 31.8%, RevG 35.1%; Apple/NVIDIA/AMD customer lock-in; A+
    'ASML',                       # ASML — EUV lithography monopoly; only company that makes EUV machines (every advanced chip fab needs them); zero debt, OM 36%, NM 29.7%, D/EV 0.0; A+
    'TER',                        # Teradyne — semiconductor test + collaborative robotics (Universal Robots); OM 37.6%, NM 22.6%, D/EV 0.001, RevG 87%, FCF 0.5%; picks-and-shovels for AI silicon + factory automation; A+
    'A',                          # Agilent Technologies — analytical instruments (LC/MS, GC, spectroscopy) + consumables (HPLC columns, reagents, standards) + informatics software for pharma QC, food safety, environmental testing, chemical analysis; spun from HP 1999, then spun off Keysight (electronic test) 2014 — now purely life sciences/chemical analysis; consumables flywheel: once a pharma lab validates methods on Agilent columns with ChemStation software, FDA documentation + method revalidation make switching genuinely painful = installed base generates recurring revenue regardless of new instrument sales; GrossM 52.6%, OM 23.7%, NM 19.6%, ROE 21.3%, D/EV 0.082, FCF 2.2%, RevG 10.0%; A+ 7/7; 4/4 MA + 4/4 weekly momentum, RSI 65.4, MACD expanding; 87w ext +17.3% mild; added 2026-08-10
    'KEYS',                       # Keysight Technologies — electronic test & measurement (oscilloscopes, network analyzers, signal generators, spectrum analyzers); spun from Agilent 2014; serves 5G/wireless, semiconductor validation, aerospace/defense, and automotive (EV power electronics test); deeply embedded in R&D labs and production lines — engineers design hardware to work with Keysight instruments, switching cost is curriculum + workflow, not just tool; GrossM ~55%, OM ~20%, low debt; revenue cyclical with semiconductor capex cycles (2023-2024 trough from semi inventory correction), recovering as AI chip demand restarts lab capex; added 2026-07-30
    'LITE',                       # Lumentum — photonics/optical components (datacenter transceivers + 3D sensing + telecom); OM 21.8%, NM 17.7%, D/EV 0.056, RevG 90.1%; AI datacenter interconnect tailwind; A+
    'STE',                       # STERIS plc — sterilization infrastructure for healthcare + pharma manufacturing; sterilization of medical devices (gamma, EO, electron beam) + procedural infection prevention products (surgical drapes, gowns) + life sciences contract sterilization for drug manufacturers; regulatory permanence moat — sterilization is legally mandated at every step of medical device and drug manufacturing, cannot be skipped or deferred regardless of budget cycle; hospitals and pharma manufacturers can't change sterilization vendors mid-process without FDA notification + revalidation = structural switching cost; GrossM 44.4%, OM 19.2%, NM 13.3%, ROE 11.4%, D/EV 0.083, FCF 3.5%, RevG 7.3%; 7/7 gates; grade B (ROE 11.4% just above gate, RevG 7.3% slow — steady compounder not a high-growth name); 4/4 MA, RSI 59.0, MACD expanding; 87w ext +2.9% essentially at base — rational entry; added 2026-08-10
    'BWXT',                    # BWX Technologies — sole-source Navy nuclear propulsion (submarines/carriers) + nuclear components + medical isotopes; ROE 29%, OM 10%, D/EV 0.099, government contract moat; grade B, watch for OM expanding above 15%; auto-promoted 2026-06-30 [grade B, 1/4 MA]
    'CIEN',                    # Ciena — optical networking, AI datacenter interconnect tailwind; net margin 4.5% and ROE/P/E blocking, 33% rev growth; auto-promoted 2026-06-30 [grade B, 3/4 MA]
    'CEG',                       # Constellation Energy — largest US nuclear operator; 21.9% OM, 12.7% NM, ROE 16.1%, RevG 63.8%; AI/datacenter PPAs (Microsoft Crane restart); D/EV 0.201 (just over 0.20 threshold) + FCF -5.3% (capex from new nuclear capacity build-out); grade B; added 2026-07-01
    'FHI',                       # Federated Hermes — active asset manager (money market, fixed income, equity, ESG); $800B+ AUM; money market funds are the core flywheel — rate normalization drove AUM surge; ESG integration (Hermes acquisition) adds institutional mandate differentiation; OM 26.4%, NM 21.3%, GrossM 68.7%, ROE 31.1%, FCF 7.8%, RevG 18.3%, D/EV 0.098; A+ 7/7; added 2026-08-07
    'AAMI',                      # Acadian Asset Management — systematic/quant equity asset manager; factor-based strategies across global markets, deep quant DNA (founded MIT/academic roots); capital-light fee business = high ROE on small equity base (same structure as BLK/FHI); GrossM 40.9%, OM 17.6%, NM 15.2%, ROE 106.8% (capital-light artifact — legitimate, not inflated), D/EV 0.075, FCF 7.4%, RevG 45.3%; A+ 7/7; 4/4 MA, RSI 78.1 overbought, MACD expanding; 87w ext +94.0% high extension — quality intact, chart extended; added 2026-08-09
    'MEDP',                      # Medpace Holdings — contract research organization (CRO) specializing in cardiology, metabolism, and oncology clinical trials; not a generalist CRO (ICON/Parexel) — therapeutic focus = deeper protocol expertise, faster startup times, lower amendment rates; capital-light services model (no manufacturing, no inventory) = structurally high ROE on thin equity base; GrossM 72.4%, OM 20.8%, NM 17.7%, ROE 162.2% (capital-light legitimate), D/EV 0.009, FCF 3.1%, RevG 17.2%; A+ 7/7; 4/4 MA, RSI 63.2, MACD fading; 87w ext +34.2% moderate — rational zone; added 2026-08-09
    'DOCS',                      # Doximity — physician professional network and clinical communication platform; 80%+ of all US physicians on the platform (actual penetration, not TAM) = structurally indispensable professional network; revenue model: (1) pharma/biotech pay for physician-targeted drug detailing + CME content to captive, credentialed audience at scale; (2) health system subscriptions for secure clinical messaging + telehealth + workflow software; GrossM 88.07% (exceptional — purest network economics in healthcare), FCF 36.56% (cash machine), D/EV 0.0023 (near-zero debt, earns interest income on cash — why NM 25.48% exceeds OM 21.54%), OM 21.54%, ROE 17.21%, RevG 7.30%; NM computed manually — yfinance netMargins null but netIncomeToCommon/totalRevenue = 25.48% clean; A+ 7/7; chart broken: 2/4 MA, above 10w (+16.0%) + 20w (+15.1%), below 43w (-19.4%) + 87w (-45.5% extreme); stock crashed from $76+ peak to $17.15 low (now $25.63 recovering) — multiple compression as RevG decelerated from 30%+ COVID-era to 7.3% as pharma ad budgets normalized; fully discounted quality scenario; gate: RevG reaccelerating + 43w/87w MA recovery; added UNIVERSE 2026-08-10
    'AXP',                        # American Express — closed-loop payment network + premium card issuer; Platinum/Gold cardholder base = affluent spenders who default less and spend more; closed-loop = AXP owns both the network AND the issuer relationship (unlike V/MA which are pure toll collectors) = richer data + stronger merchant/cardholder loyalty; Berkshire Hathaway ~21% owner (20+ yr conviction hold); OM 20.3%, NM 16.1%, ROE 34.4% (exceptional — earns like software, not a bank), GrossM 62.3%, RevG 12.8%; D/EV 0.243 + FCF 0.0% both yfinance artifacts (card receivables funded by structured debt + banking FCF measurement — same issue as all card issuers); judge by OM/NM/ROE; 4/4 MA, RSI 54.2, 87w ext +7.7% near-base — best entry timing of any financial in UNIVERSE; A (5 real metrics, 2 artifacts); added 2026-08-09
    'BLK',                       # BlackRock — world's largest asset manager ($10T+ AUM); iShares ETF franchise (largest globally) + Aladdin risk platform (SaaS-like, used by central banks/SWFs); every index fund = AUM fee; OM 35.6%, NM 24.4%, FCF 4.4%, D/EV 0.095, RevG 27%, fwd P/E 16.1x; A+
    'BX',                        # Blackstone — world's largest alternatives manager ($1T+ AUM); PE + real estate + credit + infrastructure; mgmt fees sticky, carried interest is performance upside; retail alternatives push = decade-long runway; OM 38.0%, NM 21.2%, ROE 29.5%, D/EV 0.130, fwd P/E 15.8x; A
    'ARES',  # Ares Management — largest alternative credit manager globally (~$550B+ AUM across credit, PE, real estate, infrastructure); manages ARCC (largest BDC) among other vehicles; GP of the Ares ecosystem — management fees on $550B+ is the recurring revenue base; OM 21.6%, NM 10.6%, RevG 5.8% (slower than AUM growth suggests — worth verifying); ROE 0% + FCF 0% + GrossM 35.8% all yfinance artifacts (alt manager reporting same issue as BX/APO — carried interest + complex equity structures); D/EV 0.286 (credit facilities, structural); 3/4 MA aligned; moat: institutional LP relationships with 10-year lockups, decades of credit track record — switching is structurally difficult; gate: RevG re-accelerating above 15% as AUM compounds + yfinance data normalizing on ROE/FCF; added WATCHLIST 2026-08-08
    'VIRT',                      # Virtu Financial — electronic market maker across 25,000+ instruments in 50+ countries (equities, FX, fixed income, commodities); captures bid-ask spreads algorithmically at scale; ITG acquisition added institutional execution services (diversifies away from pure volatility dependence); OM 36.2%, GrossM 65.8%, RevG 29.3%, fwdPE 9x cheap; NM/ROE/FCF blank (financial firm yfinance artifact), D/EV very elevated (market-maker leverage is structural capital, same as IBKR — not deteriorating debt); revenue highly correlated with VIX — high volatility years (2020, 2022) are windfall years, low vol compresses spreads; added 2026-07-30
    'ADBE',                    # Adobe — creative cloud monopoly (Photoshop/Illustrator/Acrobat); OM 35.3%, NM 28.7%, GrossM 89.4%, ROE 63%, FCF $9.2B, fwd P/E 8x; D/E 0.61 only blocker (corporate bonds ~$4B, FCF paydown path clear); Figma deal dead Dec 2023 (CMA blocked, $1B termination fee paid); chart 0/4 MA broken on AI disruption fear; Firefly/GenStudio is the AI answer — watch for MA recovery; auto-promoted 2026-07-06 [grade A+, 0/4 MA]
    'INTU',                    # Intuit — TurboTax + QuickBooks + Credit Karma franchise; near-monopoly on SMB accounting + tax prep; OM 47%, NM 21.9%, GrossM 80.8%, ROE 22.5%, FCF $5.2B, fwd P/E 10x; D/E 0.33 only blocker (Credit Karma acq debt, FCF paydown path clear); 0/4 MA, slope -59 — chart badly broken; watch for weekly MA structure recovery; auto-promoted 2026-07-06 [grade A+, 0/4 MA]
    'FCX',                     # Freeport-McMoRan — largest US copper producer (Grasberg mine, Indonesia); AMZN-Rio Tinto 2yr datacenter copper deal confirms AI infrastructure demand thesis; OM 31.1%, ROE 15.6%, FCF $1.7B, fwd P/E 15.4x, D/EV 0.33; NM 10.3% only soft blocker; weekly gate ✓ (MA10w $63.29 > MA20w $62.52, slope +2); price $60.97 below MA10w — entry on MA10w reclaim; auto-promoted 2026-07-06 [grade B, 2/4 MA]
    'ARM',                     # auto-promoted 2026-07-07 [grade A+, 3/4 MA]
    'DUOL',                    # Duolingo — gamified language learning platform, strong engagement moat today; AI is both opportunity (AI tutors, conversation practice) and long-term structural threat (LLMs good enough at real-time translation/conversation coaching reduce core value prop); not imminent but moat question growing; gate: AI integration demonstrably deepens retention and expands addressable market rather than being competed around; auto-promoted 2026-07-13 [grade A+, 2/4 MA]
    'DXCM',                    # Dexcom — CGM platform leader (G7 sensor + pump integrations); A+ metrics but ceiling forming (Abbott Libre gaining share, non-invasive CGM in development, GLP-1 compressing urgency); moved from universe — extended at Fully Stacked, not a clear compounder; gate: market share stabilisation vs Abbott + GLP-1 thesis resolves into expanding TAM (Type 2 non-insulin)
    'MNST',                    # Monster Beverage — energy drink category leader, near-zero debt, 50%+ gross margin, asset-light distribution via Coca-Cola; mature growth, extended at Fully Stacked; moved from universe — wait for 15-20% pullback; gate: price/MA50 pullback + rev growth reaccelerating above 10%
    'FFIV',                    # F5 Networks — legacy ADC/load balancer leader pivoting to multi-cloud app delivery + security; durable installed base, high switching costs; mature growth, extended at Fully Stacked; moved from universe; gate: 15-20% pullback + software/SaaS revenue mix crossing 50%

    'ALGN',                    # Align Technology — Invisalign category creator; clear aligner technology commoditizing (dental labs making own, generic aligners proliferating); market leader but pricing power eroding as competition closes the gap; metrics still pass filters but ceiling forming — same pattern as DXCM; gate: market share stabilisation + gross margin holding above 70% as commoditisation pressure tests pricing power; auto-promoted 2026-07-13 [grade A, 4/4 MA]
    'ATEN',                    # A10 Networks — application delivery controllers (ADC) + DDoS protection for carriers and enterprises; deeply embedded infrastructure, not flashy; GrossM 79.3%, OM 17.3%, NM 14.9%, ROE 21.4%, FCF margin ~17% ($50M on $299M rev), RevG 13.4%, D/EV 0.091; ROA 5.2% only blocker (cash pile dragging denominator — operating asset returns cleaner than headline); growth angle: AI/5G traffic surge → carrier ADC capacity upgrades + DDoS threat surface expanding; not a dividend play (0.66% yield); gate: ROA crossing 10%+ as revenue scale compounds on the asset base; auto-promoted 2026-07-13 [grade A, 4/4 MA]
    'SEZL',                    # Sezzle — fee-based BNPL pivot, 61% op margin, 92% ROE, 74% gross margin, zero debt, A+; moved from universe — extended/maxed out at Fully Stacked, risk elevated; gate: 20-25% pullback to re-enter; auto-promoted 2026-07-15 [grade A+, 4/4 MA]
    'VRTX',                    # Vertex Pharmaceuticals — CF franchise monopoly (Trikafta/Casgevy), expanding into pain (suzetrigine) + kidney disease; similar technical setup to ABBV; moved from universe — extended, wait for 20-25% pullback; auto-promoted 2026-07-15 [grade A+, 4/4 MA]
    'VCTR',                    # Victory Capital — multi-boutique active asset manager; A+ metrics (NM 25.8%, ROE 21.7%, GrossM 56.3%, zero debt); 76.7% RevG is Amundi US acquisition math not organic; active management = performance-dependent AUM, not a toll booth like MSCI/SPGI; gate: organic AUM growth positive + 2+ quarters post-acquisition showing revenue durability without acquisition tailwind; auto-promoted 2026-07-15 [grade A+, 4/4 MA]
    'HIG',                     # Hartford Financial Services — P&C + Group Benefits (life/disability insurance) + Mutual Funds; ROE 22.1%, FCF 13.8%, OM 17.6%, NM 14.9%, D/EV 0.109, PE 10.1x — passes all quality filters; business is solid but forward earnings trajectory not converging with TRV/ALL over the next 2-3 years (TRV and ALL repricing tailwind stronger); grade A on current metrics; gate: earnings growth reaccelerating to match TRV/ALL trajectory; added 2026-07-30; auto-promoted 2026-07-30 [grade A+, 4/4 MA]
    'ABT',                     # Abbott Laboratories — diversified healthcare: MedTech (FreeStyle Libre CGM, Alinity diagnostics) + Nutrition (Ensure/Similac) + Established Pharma; 52yr dividend aristocrat, 2.8% yield; FreeStyle Libre diabetes CGM growing 20%+ and expanding from monitoring to closed-loop insulin delivery (Omnipod partnership); GrossM 56.5%, OM 13.5%, NM 13.9%, FCF 3.7%, D/EV 0.187, ROE 12.3%; OM/ROE/D/EV all blocking — COVID rapid test revenue cliff normalizing dragging blended margins and growth (RevG 7.8% = Libre growing ~20% masked by COVID base erosion); not structural deterioration; grade B; gate: OM crossing 20% + ROE crossing 20% as Libre scales to majority of device revenue + COVID comp fully absorbed (~2 quarters); auto-promoted 2026-07-30 [grade B, 3/4 MA]
    'ENPH',                    # Enphase Energy — microinverter monopoly + battery storage (IQ8/Encharge); cycle trough from high-rate residential solar slowdown, not structural; gross margins ~45%+ holding even in trough; OM -9.1% + RevG -20.6% blocking now; 3/4 MA recovering, -61.6% from highs; when rates normalize + installs recover = A+ candidate; engine intact; auto-promoted 2026-07-30 [grade B, 0/4 MA]
    'BE',                      # Bloom Energy — solid oxide fuel cell systems for stationary power generation; thesis: AI datacenters need always-on baseload power that solar/wind can't guarantee — solid oxide fuel cells (running on natural gas + hydrogen blend) fill that gap as dispatchable 24/7 power inside hyperscaler campuses; RevG 165.5% = datacenter demand surge is real and accelerating; OM 17.1%, NM 7.9%, ROE 22.2%, D/EV 0.041 (near-zero debt), FCF 0.8% (thin but positive); GrossM 31.7% only blocker (fuel cell hardware — structural, won't easily cross 40% gate); grade A+; 2/4 MA (above 43w +33%, 87w +126.8%, but below 10w/20w), slope -8.8% falling — short-term correction after a massive run; gate to UNIVERSE: GrossM approaching 35%+ as software/service attach rate grows on installed base + FCF expanding past 3%; added WATCHLIST 2026-08-06
    'FTAI',                    # FTAI Aviation — CFM56 engine platform (powers 737/A320, largest narrowbody fleet in the world); buys used engines, refurbishes modules, leases/sells back to airlines at discount to OEM — toll booth on aviation, not the airline itself; OM 22.5%, NM 18.9%, ROA 11.3%, RevG 65.5%, fwd PE 18.5x; FCF -$320M ✗ (main blocker — growth capex consuming cash or structural, unclear); D/EV 0.132 manageable (D/E 809 is buyback-distorted equity, not leverage deterioration); infrastructure segment separation adds complexity; Hindenburg short report (2024) raised accounting concerns — not fully resolved; down -34% from highs; gate: FCF turning positive + infrastructure separation complete + short report overhang cleared; Buffett/Munger would disapprove (aviation industry) — but this is the toll booth, not the airline; auto-promoted 2026-07-31 [grade A+, 1/4 MA]
    'CMG',                     # Chipotle Mexican Grill — fast-casual leader; company-owned model (not franchise like MCD) = real operations, real margin discipline; OM 16.1%, NM 11.4%, ROE 49.6%, D/EV 0.114, FCF 2.6%, GrossM 39.4%, RevG 9.3%; grade B structurally — restaurant ceiling on OM/GM (39% gross margin is exceptional for company-owned; won't hit 60% ever, not a blocker that clears); digital ordering 60%+ of transactions via app = loyalty flywheel + throughput efficiency; international (UK/Canada/Europe/Middle East) early innings = long runway; every quality filter passes cleanly; added 2026-08-04; auto-promoted 2026-08-04 [grade B, 2/4 MA]
    'PEGA',                    # Pegasystems — enterprise BPM/CRM/decisioning platform; Pega Platform (low-code workflow automation) + Customer Decision Hub (real-time next-best-action AI) embedded in banking, insurance, telco, and government operations; moat = regulatory switching cost: a bank's credit decisioning or compliance workflow running on Pega requires regulatory re-approval to migrate off — not a 6-month IT project, minimum 3-5 years + exam risk; ACV model ~80%+ recurring = sticky, ratable revenue base; GrossM 75.6%, NM 18.7% (passes our ≥5% gate), ROE 54.7%, D/EV 0.015 (net cash: $362M cash vs $72M debt), FCF 10.4% — all strong; OM 4.6% the one blocker (GAAP gap vs NM explained by interest income on net cash + R&D tax credits + SaaS transition ratable timing; FCF 10.4% is the honest signal); RevG 9.4%, fwdPE 12.0x cheap for enterprise software of this embeddedness; -53% from 52w high ($68 → $31) — price dislocated from moat depth; moat override: UNIVERSE placement on structural embeddedness + FCF quality; gate: OM crossing 10% as ACV base compounds and SaaS transition headwinds normalize; added 2026-08-05
    'ACAD',                    # Acadia Pharmaceuticals — CNS/rare disease; auto-promoted from FUTURE_RADAR 2026-07-29 [grade B, blocking: Op Margin -1.7%]; auto-promoted 2026-08-05 [grade A+, 4/4 MA]
    'QRVO',                    # Qorvo — RF front-end duopoly partner to SWKS (TriQuint + RF Micro Devices merger 2015); filters phones + 5G base stations + defense/aerospace + IoT with RF modules; more diversified than SWKS (defense ~20% of revenue = less Apple concentration) but messier: higher debt, lower capital discipline, no dividend; OM 15.8%, ROE 11.6%, GrossM 48.5%, FCF $476M, fwdPE 11.3x; RevG -4.2% (trough, same Apple cycle as SWKS) + NM blank in yfinance blocking; same structural overhang as SWKS: Apple in-sourcing RF into modem SoC is the 5-7yr slow fade risk; gate: RevG turning positive as smartphone cycle recovers + NM confirmed ≥5%; added 2026-07-30; auto-promoted 2026-08-05 [grade B, 4/4 MA]
    'SHOP',                    # Shopify — commerce infrastructure platform; merchant OS for 4M+ businesses globally (payments, logistics, capital, POS, international expansion); passes all quality filters: OM 15.7%, NM 10.8%, ROE 11.3%, D/EV 0.001 (near-zero debt), FCF 0.8%; GrossM 48%, RevG 34.3%; grade B (FCF 0.8% close to 1% A gate, ROE 11.3% close to 15% A gate — one strong quarter moves it); operating leverage story: as attach rate on Shopify Payments + Capital + Shipping deepens, NM expands without proportional opex; fwdPE 53x — growth premium; added 2026-08-05; auto-promoted 2026-08-05 [grade B, 4/4 MA]
    'AMD',                     # AMD — AI accelerator (MI300X/MI350) + x86 CPU challenger; OM ~21%, NM scaling; D/EV low; FCF building as datacenter GPU mix grows; watch for ROE/NM qualification; auto-promoted 2026-08-06 [grade A, 3/4 MA]
    'RELY',                    # Remitly — digital cross-border remittances; immigrant-to-family corridor, mobile-first; GrossM 60.8%, OM 14.4%, NM 6.1%, ROE 13.0%, D/EV 0.009 (net cash), FCF 3.5%, RevG 25.2%; 7/7 gates pass, grade A; 4/4 MA aligned, slope +2.5%, MACD expanding — clean setup; gate: OM ≥ 20% + NM ≥ 10% as scale drives operating leverage; added 2026-08-06; auto-promoted 2026-08-06 [grade A, 4/4 MA]
    'EXPE',                    # Expedia Group — online travel marketplace (Expedia.com, Hotels.com, Vrbo, Orbitz); toll booth on travel bookings, asset-light; GrossM 90.3%, NM 9.8%, FCF 22.9% (standout — structural marketplace cash, not cyclical), D/EV 14.4%, ROE 71.5% (buyback-distorted, ROIC cleaner), RevG 14.7%, P/E 11.7x; OM 7.1% only blocker (just under 8% — one operating leverage step away); VRBO differentiated (family/group vacation rental, different from Airbnb urban focus); market pricing this as cyclical consumer at 11.7x vs actual toll-booth economics; gate: OM ≥ 8% sustained + RevG holding above 10% as travel recovery normalizes; auto-promoted 2026-08-07 [grade A, 4/4 MA]
    'GLBE',                    # Global-E Online — cross-border e-commerce enablement (Israel); exclusive Shopify partner; handles localization, FX, duties/taxes, compliance, local payment methods for brands selling internationally; toll-collector model on global commerce flows; GrossM 45.3%, FCF 29.2%, RevG 32.8% — growth + cash generation real; OM 7.4% + ROE 7.3% both below gate; D/EV 0.003 (near-zero debt); fwdPE 21.8x; gate: OM crossing 10% + ROE crossing 10% as revenue scale absorbs fixed costs; added WATCHLIST 2026-08-07; auto-promoted 2026-08-07 [grade A, 4/4 MA]
    'MKSI',                    # MKS Instruments — process control subsystems inside semiconductor fab tools (AMAT/Lam/KLA); pressure, flow, power, gas management + Newport photonics/lasers; design-in moat real (re-qualification cost locks in MKS components once qualified); GrossM 46.7%, OM 14.4%, NM 7.5%, ROE 10.8%, D/EV 0.183, FCF 12.6%, RevG 28.3% — all 7 gates pass on current numbers; watchlist over UNIVERSE: (1) high cyclicality with semicon capex — metrics deteriorate sharply in downturns; (2) $4.45B Atotech acquisition debt (PCB chemicals — less defensible than instruments); (3) D/EV 0.183 too close to gate for comfort; gate to UNIVERSE: D/EV ≤ 0.15 as Atotech debt pays down + NM solidly above 10% through a full semicon cycle; moved to WATCHLIST 2026-08-07; auto-promoted 2026-08-07 [grade B, 2/4 MA]
    'RTX',                     # RTX Corp (Raytheon + Pratt & Whitney) — two-segment defense/aero prime; Raytheon (missiles, Patriot/PAC-3, AMRAAM, StormBreaker, defense electronics) + Pratt & Whitney (GTF turbofan engines for A320neo/A220); GrossM 20.1% only structural blocker (cost-plus defense + engine hardware — same exception logic as GD/LMT in UNIVERSE); OM 10.5%, NM 7.6%, ROE 10.3%, D/EV 0.119, FCF 8.4%, RevG 14.5% — rest all pass; watchlist vs UNIVERSE: P&W GTF powder-metal contamination recall is a real near-term margin headwind (engine inspections + accelerated shop visits = cost absorption through 2025-26); gate to UNIVERSE: GTF recall costs rolling off + GrossM structural exception confirmed; added WATCHLIST 2026-08-07; auto-promoted 2026-08-07 [grade B, 4/4 MA]
    'QLYS',                    # Qualys — cloud-native vulnerability management + security (VMDR, TotalCloud, WAS, CSAM); A+ 7/7 (GrossM 83.4%, OM 34%, ROE 38.6%, D/EV 0.009); blocker: RevG 11% — slow for current market pricing; RSI 82, blown 10w ceiling +18.5%, at 52w high = market pricing RevG re-acceleration to 15%+ that hasn't printed yet; standalone VM platform facing bundling pressure from PANW/CRWD platform consolidation; gate to universe: RevG demonstrably re-accelerating + price pulls back to rational entry (vs MA200 <20%); added WATCHLIST 2026-08-07; auto-promoted 2026-08-07 [grade A+, 4/4 MA]
    'MMM',                     # 3M Company — post-Solventum industrial conglomerate (Safety/Industrial: PPE, abrasives, adhesives + Transportation/Electronics: auto films, display components + Consumer: Post-it, Scotch); GrossM 39.4% (0.6% below gate — manufacturing structural), OM 20.4%, NM 11.9%, ROE 81.9% (buyback-compressed equity base), D/EV 0.129, FCF 6.7%, RevG 2.5%; 6/7 gates; 4/4 MA, RSI 69.8, MACD expanding — technically strong; two WATCHLIST reasons: (1) PFAS liability settlements still partially unresolved — real cash cost not fully captured in metrics; (2) RevG 2.5% very slow post-Solventum spinoff, no clear re-acceleration visible; gate to UNIVERSE: GrossM crossing 40% + PFAS tail liability quantified/settled + RevG re-accelerating above 7% as restructuring completes; added WATCHLIST 2026-08-08; auto-promoted 2026-08-08 [grade A+, 4/4 MA]
    'AEIS',                    # Advanced Energy Industries — precision power conversion systems for semiconductor fab equipment (RF power generators/DC supplies inside AMAT/Lam/KLA plasma etch + CVD + PVD tools) + data center power (Artesyn acquisition 2019: server PSUs, telecom rectifiers); design-in moat: once qualified inside a tool, replacing power supply requires 6-18mo re-qualification = sticky; OM 17.0%, NM 10.8%, ROE 16.3%, D/EV 0.106, RevG 30.0%; 7/7 gates but two at the wire: GrossM exactly 40.0% + FCF 0.3% (zero headroom on both); semicon equipment = inherently cyclical, threshold metrics flip in a soft quarter; same archetype as MKSI (WATCHLIST) but thinner margins; +58.0% above 87w MA = high structural extension; gate to UNIVERSE: GrossM sustaining above 43% + FCF above 5% through a full semicon capex cycle; added WATCHLIST 2026-08-08; auto-promoted 2026-08-08 [grade A, 3/4 MA]
    'CRS',   # Carpenter Technology — specialty alloys manufacturer (nickel/titanium/cobalt superalloys) for aerospace jet engine hot-section components, medical implants, defense; aerospace certification moat = years to re-qualify suppliers on a program, customers don't switch mid-contract; cyclical-flavored (ties to aerospace production cycles) but not commodity cyclical — long-term supply agreements with GE Aerospace/Pratt & Whitney + LEAP engine demand provide multi-year contracted backlog; GrossM 30.6% structural miss (metals processing — raw material costs are the ceiling, same structural compression as defense primes and aggregates; OM 24.3% and NM 17.0% are exceptional for the category — operating leverage is real); D/EV 0.024 near-zero debt (exceptional for a capital-intensive manufacturer), FCF 0.9% thin, RevG 12.6%; 6/7 gates; 4/4 MA, RSI 63.3, MACD fading; 87w ext +82.1% high — extended; gate to UNIVERSE: GrossM trending toward 35%+ as aerospace premium-alloy mix grows + FCF above 3% sustained; added WATCHLIST 2026-08-09
    'HUBB',                    # Hubbell — electrical products + grid infrastructure; Electrical Solutions (wiring devices, switchgear, commercial lighting) + Utility Solutions (distribution transformers, transmission connectors, smart grid hardware); Utility Solutions is the growth engine — every grid upgrade, EV charging buildout, and AI datacenter power feed needs Hubbell utility hardware; GrossM 35.3% (well below 40% gate — electrical equipment manufacturing has copper/aluminum raw material cost structure, structural compression); OM 21.7%, NM 14.5%, ROE 24.4%, D/EV 0.172 (close to 0.20 ceiling), FCF 1.8%, RevG 15.3%; 6/7 gates (GrossM blocker); grade B; chart is actually the best of any WATCHLIST name: 4/4 MA, RSI 60.5, CMF +0.129 accumulation, 87w ext only 17.6% (mildest extension in weeks — rational entry zone if metrics clear); gate to UNIVERSE: GrossM crossing 38%+ as Utility Solutions mix grows (higher-margin vs commodity wiring devices) + FCF above 3% + D/EV staying under 0.17; added 2026-08-09
    'TREX',                    # Trex Company — composite decking (wood-alternative, recycled polyethylene + sawdust); THE brand in composite decking — contractors specify Trex, homeowners ask for Trex; renovation cycle tailwind (deck replacement every 15-20yr, composite outpacing wood on share); GrossM 38.2% (1.8% below gate — manufactured product, should improve with pricing/scale), OM 20.6%, NM 14.7%, ROE 17.7%, D/EV 0.057, FCF 1.4%, RevG 7.8%; 6/7 gates; 3/4 MA (above 10w/20w/43w, below 87w — recovering from trough); RSI 59.6, MACD expanding; housing cycle sensitive — deck activity tracks home improvement spend; gate to UNIVERSE: GrossM crossing 40% sustained + FCF expanding past 5% as volume absorbs fixed manufacturing cost; added WATCHLIST 2026-08-08; auto-promoted 2026-08-08 [grade A, 3/4 MA]
    'RMD',                     # ResMed — dominant CPAP/BiPAP device + connected care platform for sleep apnea and respiratory disease; only two real competitors (ResMed + Philips — and Philips had a massive foam degradation recall in 2021 that handed RMD durable market share gains it has not given back); myAir software + AirSense connected device = recurring engagement layer on top of hardware that creates switching cost beyond the mask; GLP-1 narrative broke the chart (fear: obesity drugs eliminate sleep apnea, reducing TAM) — overblown: sleep apnea is structurally underdiagnosed, GLP-1 reduces severity not cure, and CPAP compliance (consistent device use) is the real TAM driver; GrossM 61.6%, OM 31.0%, NM 26.9%, ROE 24.3%, D/EV 0.028, FCF 3.1%, RevG 8.6%; A+ 7/7; 2/4 MA (above 10w/20w, below 43w -7.9% + 87w -11.0% — recovering from GLP-1 selloff), MACD expanding, RSI 48.1 neutral; gate: 43w/87w reclaim for UNIVERSE; added WATCHLIST 2026-08-09; auto-promoted 2026-08-10 [grade A+, 0/4 MA]
    'DVN',                     # Devon Energy — formed from CTRA+DVN merger; Permian + Appalachia nat gas/oil; NM 14.2%, ROE 15.2%, FCF 3.2%, P/E 11.8x — solid underlying economics; D/EV 0.257 (merger leverage) + OM 6.9% both blocking; gate: D/EV ≤ 0.20 as merger debt amortizes + OM ≥ 10% on commodity price recovery; auto-promoted 2026-08-10 [grade A, 4/4 MA]
    'APP',                     # AppLovin — AI-driven mobile advertising platform (AXON engine); largest mobile ad network globally; GrossM 74.7%, OM 35.6%, NM 27.4%, ROE 72.4%, D/EV 0.092, FCF 28.9%, RevG 73.4% — A+ across all 7 gates, fundamentals intact; moved to WATCHLIST 2026-08-18 on deep structural correction: price $307 vs 10w MA $416 (-26.1% below), 52w hi -57.4%, 87w STRUCT -31.3% below LT mean (full mean-reversion overshot to downside); active distribution: CMF -0.228 (20w) + -0.449 (10w) — institutions exiting at scale, not accumulating; slope -15.8% (10w MA in freefall, not flattening); RSI 33 (approaching washed-out, not yet); chart is broken across every timeframe — business is not; gate to UNIVERSE: CMF turning toward 0 (institutions stop exiting) + RSI washes below 30 and recovers (capitulation) + slope flattens + price stabilizes for several weeks (base building); do not re-enter on price alone — wait for CMF confirmation; auto-promoted 2026-08-18 [grade A+, 0/4 MA]
    'ILMN',                    # Illumina — dominant NGS (next-generation sequencing) platform; 80%+ global market share in research sequencing (NovaSeq X+, MiSeq, NextSeq); razor/blade model: instruments placed in every major research hospital + pharma company + sequencing lab globally, reagents/consumables are sticky recurring revenue; lost 3 years to the GRAIL acquisition saga (bought 2021 for $8B, blocked by EU/FTC, forced divestiture 2024) — billions in charges explain NM None (not structural); post-GRAIL: new CEO (Jacob Thaysen), cost discipline, core sequencing refocus; GrossM 67.9% ✓, OM 21.1% ✓, ROE 32.3% ✓, D/EV 8.4% ✓, RevG 9.4% ✓ — 5/7 gates; NM None (GRAIL noise) + FCF 2.77% (just below 3% gate) = 2 blockers; just misses UNIVERSE — WATCHLIST until NM normalizes post-GRAIL + FCF crosses 3%; chart: at ceiling by tight historical distribution (RSI 76, slope +9.9%), CMF +0.112 modest; gate: NM consistently positive + FCF ≥ 3% as GRAIL charges roll off; added WATCHLIST 2026-08-17',; auto-promoted 2026-08-18 [grade A+, 4/4 MA]
    'CHRD',                    # Chord Energy — Bakken/Williston Basin pure-play E&P (Oasis + Whiting merger 2022); one of the lowest-cost Bakken operators; GrossM 48.1% ✓, OM 34.7% ✓, ROE 10.3% ✓, FCF 12.8% ✓, D/EV 17.9% ✓ — 5/7 gates passing; NM shows None (E&P hedging mark-to-market + D&D non-cash items = yfinance artifact, not operational failure); fwdPE 9.8x cheap; ~3.8% yield + variable dividend return-of-capital model; UNIVERSE-quality metrics but commodity cycle risk keeps it WATCHLIST — oil price drops, all metrics deteriorate simultaneously; chart: extended +7.2%, CMF -0.103 distribution, 23% runway — not entry zone today; gate to UNIVERSE: NM data normalizing + sustained OM ≥ 10% through a full oil cycle trough; added WATCHLIST 2026-08-17',; auto-promoted 2026-08-18 [grade A, 4/4 MA]
    'FORM',                    # FormFactor — leading probe card maker (~40%+ share in advanced probe cards) for wafer-level semiconductor testing; every advanced chip (NVDA GPU, HBM from SK Hynix/Samsung/MU, TSMC leading-edge logic) needs probe cards before packaging — picks-and-shovels for the entire AI silicon supply chain; HBM4 + 2nm nodes require higher-precision cards = structural ASP uplift; probe card design is co-developed with chipmaker process engineers = deep switching costs; GrossM 46.2% ✓, OM 24.1% ✓, NM 12.8% ✓, ROE 11.0% ✓, D/EV 0.3% ✓ (near-zero debt), RevG 31.9% ✓ — 6/7 gates; FCF 1.1% ✗ only blocker (capex-heavy capacity build for HBM demand surge); gate: FCF ≥ 3% as HBM probe card volume scales and capacity capex normalizes; added WATCHLIST 2026-08-18; auto-promoted 2026-08-18 [grade A, 3/4 MA]
    'NTAP',                    # NetApp — enterprise hybrid cloud storage; ONTAP OS + StorageGRID object storage + Azure NetApp Files (Microsoft's preferred high-performance NFS for enterprise Azure workloads) + Google Cloud NetApp Volumes — hyperscaler integration is the durable distribution moat; GrossM 70.7%, OM 27.3%, NM 18.4%, ROE 106.7% (buyback artifact — same read as STX), D/EV 7.0%, FCF 18.7% of revenue; RevG 12.5% sole blocker (gate ≥15%); 6/7 gates; A+ quality on every metric except RevG; AI unstructured data storage = durable structural tailwind (LLM fine-tuning datasets, inference logs, RAG vector stores all compound NTAP's addressable volume); fwdPE 19.4x reasonable; at ceiling ($194.48 vs $195.85 ceiling), RSI 74, -2.6% below 10d — already rolling off; gate: RevG ≥ 15% as AI storage demand + Azure/GCP NetApp volume accelerates + price pulls back to 10w MA zone; added WATCHLIST 2026-08-19; auto-promoted 2026-08-20 [grade A+, 4/4 MA]
    'HAE',                     # Haemonetics — blood management technology: NexSys PCS apheresis machines (plasma + platelet collection), BloodTrack hospital blood management software, vascular closure devices; plasma collection is structurally growing — immunoglobulin therapies (IVIG, SCIG) for immune deficiency, neurology, transplant are demand-compounding; HAE machines are contracted with major plasma center operators (CSL, BioLife, Grifols) = recurring disposables revenue on a placed-machine base; GrossM 59.3%, OM 17.9%, NM 7.1%, ROE 11.2%, FCF 7.8%, RevG 5.6%; D/EV 0.237 only blocker — acquisition/restructuring debt; FCF 7.8% is the paydown engine; 6/7 gates; 4/4 MA, RSI 70.0, MACD expanding, 87w ext +31.1% moderate — technically strongest of recent WATCHLIST additions; gate: D/EV below 0.20 via FCF paydown (2-3 quarters at current pace); added WATCHLIST 2026-08-10; auto-promoted 2026-08-20 [grade B, 4/4 MA]
]

# Future contenders — moat proven, one or two filters blocking, no survival risk
# Rule: if the blocker is a number, it belongs here. If the blocker is the business model, it doesn't.
WATCHLIST = [
    'AXON','MELI','SNOW','BILL',   # ALAB promoted to universe; CRWD removed — already in universe; PLTR promoted to universe
    'CRWD',                    # CrowdStrike — cloud-native endpoint + identity + cloud security platform (Falcon); dominant market share in EDR/XDR; GrossM 75.1%, RevG 25.6%, D/EV 0.004 (near-zero debt), FCF 0.9%; OM -2.2%, NM -0.6%, ROE -0.2% — all three blocking; same spend-before-earn profile as DDOG: S&M + R&D consuming gross profit, platform moat is real, margin expansion is the bet; 4/4 MA aligned, slope +4.7%, RSI 69 — technically strong, but that's the market pricing future earnings not current; gate: OM crossing 10% as ARR compounds and S&M normalizes as % of revenue; moved from UNIVERSE 2026-08-06
    'ZS',                      # Zscaler — zero-trust network security (ZIA + ZPA + ZDX); every enterprise moving to cloud needs ZTNA to replace VPN — ZS is the category leader; GrossM 76.7%, RevG 25.4%, D/EV 0.076, FCF 4.2% (healthier than CRWD); OM -3.3%, NM -2.4%, ROE -3.7% — all blocking; structurally same story as CRWD/DDOG: massive S&M spend to win enterprise contracts, gross economics are real, operating leverage hasn't printed; FCF 4.2% is the one honest signal — cash generation above the GAAP losses; 2/4 MA, slope -1.9% flat — technically weaker than CRWD; gate: OM turning positive + sustained positive + crossing 10%; moved from UNIVERSE 2026-08-06
    'DDOG',                    # Datadog — cloud observability + security platform (infrastructure monitoring, APM, logs, SIEM); every cloud-native app needs observability — DDOG is the default for DevOps/SRE teams; GrossM 79.9%, RevG 32.2%, D/EV 0.013 (net cash); OM 0.8%, NM 3.7%, ROE 3.9% — all three blocking; $100B+ market cap on near-zero operating earnings = paying 40-50x forward revenue for margin expansion that hasn't printed; the spend is real (R&D + S&M consuming all gross profit), the platform is real, the ARR compounding is real — but the current metrics don't support UNIVERSE placement; gate: OM crossing 10% as RevG compounds and S&M/R&D as % of revenue normalizes; moved from UNIVERSE 2026-08-06
    'DT',    # Dynatrace — AI-powered observability platform (infrastructure + APM + logs + security + digital experience monitoring); Davis causal AI engine auto-detects root cause without manual alert configuration — differentiated vs DDOG's query-first model; GrossM 81.6%, RevG 16.2%, D/EV 1.2% (near-zero debt), FCF 26.1% of revenue; OM 12.9%, NM 7.2%, ROE 5.9% — all three blocking; context: OM 12.9% already ahead of DDOG (0.8%), CRWD (-2.2%), ZS (-3.3%) — margin path shorter than peers; AI observability angle is real new TAM: monitoring LLM traces, AI model latency, GPU infra performance as enterprises deploy AI at scale; fwdPE 21.6x reasonable; 4/7 gates; at ceiling (+0.2% blown), RSI 75, 3/3 daily ⚡H — technically extended, wait for pullback; gate: OM ≥ 20% + NM ≥ 10% + ROE ≥ 10% as SBC normalizes and ARR scale drives leverage; added WATCHLIST 2026-08-19
    'MDB','HUBS','TEAM','MKC','DPZ',
    'ON',    # ON Semiconductor — SiC (silicon carbide) power semiconductors for EV inverters + ADAS power management; every EV drivetrain needs SiC MOSFETs/modules — ON is top-3 globally (alongside Infineon/STMicro); GrossM 42.8%, OM 19.5%, NM 10.2%, FCF 5.1%, D/EV 14.5%, RevG 9.2%; ROE 8.3% sole blocker (below 10% gate — transitional as SiC capacity ramps and EV volumes absorb fixed wafer fab costs); fwdPE 18.4x; gate: ROE crossing 10% as SiC mix grows; added 2026-08-12
    'GWRE',  # Guidewire — insurance core system software (PolicyCenter/BillingCenter/ClaimCenter) for P&C insurers globally; replacing a core system requires 3-5yr migration + regulatory re-approval = maximum switching cost; GrossM 64.0%, NM 11.2%, ROE 11.9%, FCF 2.0%, D/EV 4.8%, RevG 26.9%; OM 8.2% sole blocker (1.8% below 10% gate — SaaS cloud transition timing, not structural); fwdPE 42.5x; gate: OM crossing 10% as cloud migration mix shift absorbs R&D; added 2026-08-12
    'WING',  # Wingstop — asset-light franchise QSR (owns ~1% of restaurants, earns royalties on all); digital ordering ~70% of sales; GrossM 49.4%, OM 29.8%, NM 16.2%, FCF 3.2%, RevG 6.4%; D/EV 30.5% sole blocker (franchise brand debt — structural for capital-return QSR, same read as QSR/MCD); ROE yfinance gap (negative book equity from buybacks); fwdPE 20.9x cheap for franchise quality; gate: D/EV trending below 20% as system cash flow amortizes brand debt; added 2026-08-12
    'MNDY',  # Monday.com — work OS (project mgmt + CRM + dev + marketing) built on a flexible canvas; Israel-based; GrossM 89.2%, FCF 25.2%, RevG 24.5% — the three honest signals; OM -0.1% (essentially breakeven, hairline below gate) + ROE 9.5% (hairline below 10% gate) both blocking; D/EV 0.064 (near-zero debt); fwdPE 16.9x; differentiated from MSFT Project/Asana/Smartsheet by flexibility (no-code automation, cross-team use cases) + Shopify/Salesforce integrations; gate: OM crossing 10% as S&M leverage builds + ROE crossing 10%; 2 hairline blockers — could clear in 1-2 quarters; added WATCHLIST 2026-08-07
    'AAOI',  # Applied Optoelectronics — fiber-optic transceiver maker for AI datacenters (100G/400G/800G optical modules for hyperscaler GPU cluster interconnects); RevG 86.4% = hyperscaler 800G transceiver demand is real and accelerating; D/EV 2.4% clean; GrossM 28.9% (hardware components — can improve with volume but structural ceiling question vs fabless peers), OM -12.9%, FCF -$887M, ROE -5.5% — all blocking, deep investment phase; 87w +159.6% extreme = stock recovered from near-zero ($2→$150), artifact not ceiling risk; slope -15.0% (10w MA still declining sharply), CMF +0.030 essentially zero — not being accumulated yet despite RevG; borderline FUTURE_RADAR on the numbers but optical transceiver moat + 800G datacenter timing earns WATCHLIST; gate: GrossM ≥ 35% as 800G volume absorbs fixed cost + OM turning positive + FCF inflecting; added WATCHLIST 2026-08-17',
    'MXL',   # MaxLinear — high-speed analog/mixed-signal semiconductors; PAM4 DSPs for 400G/800G optical datacenter interconnects (AI GPU cluster bandwidth), DOCSIS 3.1/4.0 broadband access SoCs, Wi-Fi; revenue collapsed 2023-2024 from broadband/cable inventory correction (ISPs over-ordered post-COVID), recovering now as datacenter interconnect mix grows; GrossM 57.5%, D/EV 1.9% (clean), RevG 55.2% — recovery ramp real; OM -2.4% (at zero, one quarter from positive), NM neg, ROE -21.3%, FCF 0.2% — cyclical trough artifacts, not structural ceilings; 87w +190.2% extreme is a recovery-from-collapse artifact (stock: $90→$7→$84), not dangerous extension; gate: OM ≥ 10% + FCF ≥ 3% as PAM4 datacenter interconnect revenue becomes majority mix; added WATCHLIST 2026-08-15',
    'SLAB', # Silicon Laboratories — pure-play IoT wireless MCU maker; divested infrastructure & automotive to Skyworks in 2021 ($2.75B) and went all-in on IoT; EFR32 wireless MCUs handle Bluetooth + Zigbee + Z-Wave + Thread + Wi-Fi in a single chip — Matter protocol (Apple/Google/Amazon/Samsung smart home standard) runs on SLAB silicon; industrial IoT + medical IoT = longer design cycles, stickier revenue than consumer; GrossM 59.3% (fabless model, underlying quality real); RevG 20.1% = IoT inventory correction ending, demand recovering; OM -8.0% + ROE -4.6% + FCF ~0 all blocking — losses are scale-gap, not business-model failure; fwdPE 51x priced for recovery; gate: OM crossing 0% sustained + FCF building above 5% as IoT volume absorbs fixed R&D cost base; added 2026-07-30
    'P',     # Everpure (formerly Pure Storage / PSTG) — all-flash storage platform for enterprise + AI workloads; AI training/inference data lives on flash, not spinning disk = durable demand floor as AI scales; GrossM 70.2% (software-like storage economics), ROE 16.8%, D/EV 0.031 (nearly debt-free), FCF 0.9%; OM -18.5% GAAP blocker (stock-comp heavy, same structural pattern as NET/MNDY — non-GAAP OM meaningfully better); NM 5.7% > OM = non-operating income offsetting GAAP drag; RevG 0% — transition year or data gap from ticker/name change; 4/4 MA aligned, RSI 62.2; gate: OM crossing 0% GAAP sustained + RevG re-accelerating as AI storage demand ramps; added WATCHLIST 2026-08-08
    'DELL',  # Dell Technologies — largest US server + PC + storage vendor; ISG (Infrastructure Solutions Group) AI server business (PowerEdge + Nvidia GPU) driving RevG 87.5%; GrossM 19.2% (hardware assembler structural, same as SMCI but clean accounting) + OM 8.9% (1.1% below gate) + ROE 0% (negative book equity from aggressive buybacks — artifact, not failure) — all structural or artifacts; D/EV 0.102, FCF 1.9%; 4/4 MA aligned but +172.5% above 87w MA = extreme structural extension; gate: OM crossing 10% as AI server mix grows + price pulling back to rational entry zone; added WATCHLIST 2026-08-08
    'FERG',  # Ferguson Enterprises — largest North American wholesale distributor of plumbing + HVAC products; 1,600+ branches, next-day delivery, deep contractor credit relationships = switching cost moat (same distribution archetype as GWW); serves residential, commercial, civil infrastructure, and industrial customers; $50B market cap on ~$30B revenue; OM 8.1% (just below 10% gate — structural for distribution) + GrossM 30.7% (structural, same as GWW) + ROE/FCF likely yfinance artifacts from UK→US re-domicile (Ferguson plc → Ferguson Enterprises, NYSE 2022); NM 6.3%, D/EV 0.110, RevG 3.6%; gate: OM crossing 10% sustained + yfinance data normalizing post re-domicile; added WATCHLIST 2026-08-08
    'CHTR',  # Charter Communications — #2 US cable/broadband (Spectrum brand, ~32M passings); broadband infrastructure moat — last-mile coax/fiber built over decades, expensive to replicate; OM 23.5%, NM 9.1%, ROE 27.2%, FCF 10.6%, GrossM 55.2%; D/EV 0.806 primary blocker (levered cable buyout structure) + RevG -1.7% (cable TV subscriber bleed offsetting broadband); price $153 is -42.8% below 87w MA — market pricing secular cable decline; key risk: fiber overbuild (AT&T), fixed wireless (T-Mobile Home Internet) eating broadband share; counter: CHTR all-digital network + RDOF rural buildout funded by govt grants; gate: D/EV trending toward 0.50 via FCF deleveraging + RevG turning positive as broadband holds + streaming DTC deals stabilize video ARPU; added WATCHLIST 2026-08-07
    'RJF',  # Raymond James Financial — independent full-service wealth management + investment banking + asset management; ~9,000 financial advisors in Private Client Group (PCG) = recurring AUM fee base that grows with markets and net new asset flows regardless of trading activity; PCG is the flywheel: advisors bring clients, clients bring AUM, AUM fees compound; not a bulge-bracket (Goldman trading-desk risk), not a robo-advisor (Betterment commoditization) — the trusted-advisor middle path at scale; OM 19.4%, fwdPE 12.3x cheap, RevG 15.2%, GrossM 93.2%; NM/ROE/FCF blank in yfinance (financial firm reporting artifact — same sector gap as PNC/PRU, not actual failures); gate: yfinance data stabilizing on NM/ROE so screener can grade fairly; added 2026-07-30
    'DFIN',  # Donnelley Financial Solutions — regulatory compliance SaaS for capital markets; EDGAR/SEC filing software (ActiveDisclosure), investor relations platform, compliance reporting tools for public companies and M&A transactions; spun from RR Donnelley 2016 — the software platform survived, the print legacy did not; GrossM 64.2% (software-driven revenue, not print), OM 25.8% genuinely strong; NM 4.5% (just under 5% gate) + ROE 8.6% (just under 10% gate) both close — interest expense from debt is the drag; D/EV 0.157 manageable, FCF 11.4%; RevG 2.8% slow — capital markets activity (M&A, IPO volumes) is lumpy and drives deal-spike revenue; 5/7 gates; 3/4 MA (above 10w/20w/43w, below 87w at -7.0%), RSI 52.6 neutral, MACD above signal but fading; gate: NM crossing 5% as D/EV deleverages via FCF + ROE crossing 10% as earnings compound + RevG reaccelerating on M&A/IPO cycle recovery; added WATCHLIST 2026-08-09
    'MKL',  # Markel Group — "baby Berkshire"; specialty insurance float funds a diversified investment portfolio (Markel Ventures = private operating businesses + public equities); Tom Gayner (CEO/CIO) runs capital allocation the same way Buffett does — insurance float is the low-cost funding mechanism; NM 11.1%, ROE 10.0%, D/EV 0.18; OM -9.7% + FCF -4.3% both blocking but both GAAP artifacts: investment income flows below operating line (same as TRV/AFL), Markel Ventures acquisitions coded as investing outflows not operating (same as RPRX/TPL); PE 10.4x trailing — historically cheap for Gayner's track record; judge by book value per share growth over time, not GAAP OM/FCF; different from KNSL (pure E&S underwriter) — MKL is a capital allocator wearing insurance clothes; gate: FCF inflecting positive + RevG turning positive as underwriting cycle hardens; added 2026-07-30
    'AKAM', # Akamai — original CDN pioneer (4,000+ global PoPs, deeply embedded in enterprise infrastructure) pivoting to security (Guardicore microsegmentation, WAF, Bot Manager, API security, MFA) + cloud compute (Linode/Akamai Cloud); CDN maturity is priced in (fwdPE 16.4x), security pivot is not; GrossM 58.9%, OM 14.9%, NM 10.7%, FCF 16.6%, RevG 5.8%; ROE 9.1% (0.9% shy of gate) + D/EV 0.258 both blocking; FCF 16.6% strong enough to delever fast; gate: ROE crossing 10% as security/cloud mix improves margins + D/EV ≤ 0.20 via FCF paydown; added WATCHLIST 2026-08-07
    'NET',  # Cloudflare — global network infrastructure platform; CDN + DDoS protection + Zero Trust/SASE (Cloudflare One) + AI inference at the edge (Workers AI runs on 300+ PoPs globally); platform consolidation play: enterprises replacing 5-10 point security vendors with a single Cloudflare stack — each new product (CASB, DLP, RBI, ZTNA) sold into the existing base with near-zero CAC; GrossM 73.3%, RevG 33.5%, FCF 0.8% (barely positive), D/EV 0.037 (near-zero debt); OM -9.7% only blocker — stock-comp heavy GAAP drag, FCF is the honest signal (already crossing zero); Workers AI is an emerging edge inference network — low-latency AI calls at 300+ locations globally without GPU datacenter dependency; gate: OM crossing 0% sustained + trending toward 10% as S&M leverage kicks in at scale; fwdPE 170.9x rich but compresses fast as OM inflects; added 2026-07-30
    'TREE',  # LendingTree — online financial marketplace connecting consumers with lenders (mortgages, personal loans, auto, credit cards, insurance); pure lead-gen model = GrossM 96.3%, near-zero marginal cost per match; got crushed when rates went 3%→7%+ (mortgage origination volume collapsed — that's their core product); RevG 36.5% = rate normalization recovery is real and accelerating; FCF $61.7M on $442M market cap (14% FCF yield), fwdPE 4.8x — priced like it stays broken; OM 9.8% just below gate + D/EV elevated (debt from accumulated losses during rate shock) both blocking; gate: OM crossing 10% sustained + D/EV compressing as FCF pays down debt; rate environment is the macro lever — this is a recovery story, not a compounder; added 2026-07-30
    'ALC',   # Alcon — global #1 in surgical eye care (cataract IOLs, vitreoretinal surgery, glaucoma equipment) + vision care (DAILIES contact lenses); Novartis spinoff 2019; surgical moat = surgeons train on specific equipment and don't switch, hospital preferred-vendor relationships, IOL is a consumable in every cataract surgery worldwide; DAILIES brand loyalty sticky (daily disposable repeat purchase through eye doctors); GrossM 55.2%, OM 13.1%, NM 9.4%, D/EV 0.015, FCF 15.5%, RevG 9.4%; ROE 4.5% only blocker — structural from massive $22B equity base inherited at Novartis spinoff (not acquisition goodwill distortion — genuine ROE dilution); gate: ROE crossing 10% as NI compounds into the equity base; added WATCHLIST 2026-08-07
    'WAT',   # Waters Corporation — premium HPLC + mass spectrometry instruments for pharma QC, protein analysis, biopolymer characterization; most precise analytical chemistry instruments in pharma (Acquity UPLC, Xevo MS); consumables moat same as Agilent — validated pharma methods locked to Waters columns + software; Wyatt Technology acquisition 2023 (~$1.36B, light scattering for biologics) distorting all margin metrics: NM 3.6%, ROE 1.9%, FCF 0.0%, RevG 113.3% all yfinance acquisition artifacts — real Waters is historically ROE 30%+, NM 20%+; GrossM 56.3%, OM 10.0%, D/EV 0.114 real; 4/4 MA + 4/4 weekly momentum, RSI 64.5, MACD expanding; 87w ext +17.3% mild — chart confirming recovery; ⚠ no MOS at current price — full suite of life sciences tools running simultaneously; gate: data normalizing post-Wyatt + ROE recovering toward 20%; added WATCHLIST 2026-08-10
    'BIO',   # Bio-Rad Laboratories — PCR/qPCR instruments, gel electrophoresis, western blot, ddPCR (Droplet Digital PCR — most accurate low-abundance nucleic acid quantification, specialty moat for liquid biopsy + food safety + environmental); also clinical quality control products for hospital labs; Sartorius stake accounting drag: owns ~13% of Sartorius AG (~$2.5B), Sartorius corrected -60%+ from peak — unrealized losses flooded through balance sheet, suppressing stated ROE 3.1% (not operational failure); RevG -0.1% barely negative — essentially flat from biotech funding cycle; GrossM 52.0%, OM 11.2%, NM 8.6%, D/EV 0.149, FCF 3.0%; 5/7 gates; 4/4 MA + 4/4 weekly momentum, RSI 67.3, MACD expanding; 87w ext +23.9% moderate — no MOS currently; gate: RevG turning positive + Sartorius stake stabilizing/recovering as ROE corrects upward; added WATCHLIST 2026-08-10
    'RVTY',  # Revvity (formerly PerkinElmer) — life sciences instruments + diagnostics; sold industrial/environmental segment 2023, rebranded to focus purely on life sciences; newborn screening infrastructure moat: ~80% of all US newborn screens run through Revvity's platform (every baby screened for 50+ genetic diseases at birth) — mandatory healthcare toll-booth with government relationships and regulatory depth that makes displacement structurally impossible; also: immunoassay detection instruments (VICTOR, EnVision plate readers), reproductive health diagnostics, biobanking; GrossM 55.0%, OM 17.0%, NM 8.2%, FCF 4.6%, RevG 1.3% (biotech funding cycle hangover, recovering); ROE 3.2% (massive goodwill from historical acquisitions + PerkinElmer separation accounting — structural artifact, not operational failure) + D/EV 0.219 (0.019 above gate — acquisition debt); 5/7 gates; 4/4 MA, RSI 63.2, MACD fading; 87w ext +16.3% mild; gate: ROE crossing 10% as NI scales into the equity base + D/EV below 0.20 via FCF paydown + RevG reaccelerating above 5% as biotech cycle recovers; added WATCHLIST 2026-08-10
    'ZBH',   # Zimmer Biomet — orthopedic implants (knee/hip replacement systems) + spine surgery; large installed base of surgeons trained on ZBH instruments = switching cost real but not as deep as ISRG or PODD (SYK/JNJ ortho/Smith+Nephew compete directly — no specialty monopoly); GrossM 69.9%, OM 18.0%, NM 9.5%, FCF 5.9%, RevG 4.8%; D/EV 0.297 (Biomet 2015 acquisition debt, paying down via FCF) + ROE 6.4% (goodwill from Biomet suppressing stated ROE — ROTCE materially higher) both blocking; chart is the best signal here: 4/4 MA, RSI 58.5, MACD expanding, daily above all 3 — price sitting +1.2% above 87w MA base with momentum building; generalist implant maker vs specialist moat — tracked for completeness, not as a compounder; gate: D/EV below 0.20 as FCF deleverages + ROE above 10% as goodwill amortizes; added WATCHLIST 2026-08-09
    'TMDX',  # TransMedics Group — Organ Care System (OCS): normothermic machine perfusion keeps donor hearts, lungs, livers warm and viable during transport; extends transplant window dramatically vs traditional static cold storage (cold = 4hr window, OCS = 8-12hr+) = more transplants from marginal donors, longer-distance matching; FDA-approved, real clinical utility, genuinely saves lives; built own aviation network (TransMedics Air) to control end-to-end organ logistics — expensive but creates a logistics moat no competitor can replicate quickly; GrossM 58.7%, OM 12.5%, NM 22.7% (NM > OM = non-operating income component, watch normalize), ROE 36.3%, FCF 1.5%, RevG 20.7%; D/EV 0.263 only blocker — aviation network capex, amortizes as volume scales; 6/7 gates; 2/4 MA (above 10w/20w, well below 43w -22.2% + 87w -17.9% — chart corrected hard after a major run); RSI 46.6, daily bounce above 10d/20d/50d; gate: D/EV ≤ 0.20 as transplant volume + aviation utilization scales + weekly MA structure recovers (43w/87w reclaim first); added WATCHLIST 2026-08-09
    'CNC',   # Centene Corporation — #2 US Medicaid managed care (behind UNH); govnt-contracted health insurance across Medicaid + Medicare (Wellcare brand) + ACA marketplace (Ambetter brand); 26 states; recession-resistant moat: Medicaid enrollment grows in downturns (more people qualify when economy weakens); $180B revenue, $33B market cap = 0.18x P/S; FCF $9.6B = 28.8% FCF yield on market cap; fwdPE 12.7x; GrossM 11.4% structural exception (medical loss ratio — same lens as UNH, not a quality blocker); OM 3.76% + NM negative both blocking — Medicaid redetermination headwinds (2023-2024: post-COVID continuous enrollment ended, states re-checked eligibility, disenrolled millions, revenue/margin pressure real but transient); ROE -20.4% headwind artifact; CMF +0.439 exceptional — strongest accumulation signal in healthcare right now, institutions pricing in headwind resolution; gate: OM ≥ 10% + NM consistently positive as redetermination cycle completes and medical cost inflation normalizes; added WATCHLIST 2026-08-15',
    'COR',   # Cencora (fmr AmerisourceBergen) — #2 US pharmaceutical distributor (McKesson/COR/Cardinal Health = ~90% US drug distribution oligopoly); every GLP-1 prescription (Ozempic/Wegovy/tirzepatide), oncology biologic, and specialty drug reaching a US hospital or pharmacy flows through this network; $332B revenue, $60B market cap; GrossM 3.96% structural exception (drug pass-through model — distributor earns a fee spread on drug cost, not a margin on product; same lens as FERG/GWW distribution model); OM 1.4% + NM negative blocking; ROE 96.9% leverage artifact (D/E 446% = insurance float analog — working capital funded by supplier credit); FCF $2B = 3.4% yield (the real economics); GLP-1 structural tailwind: specialty drug volumes compounding as GLP-1 prescriptions scale nationally, specialty drugs carry higher distribution fees than generics; fwdPE 15.8x; gate: OM crossing 3%+ sustained + NM turning positive + FCF expanding as specialty/GLP-1 mix grows as % of volume; added WATCHLIST 2026-08-15',
    'COO',   # Cooper Companies — #2 global contact lens maker (CooperVision: Biofinity, MyDay, clariti) + CooperSurgical (fertility clinic media/devices, OBGYN instruments); contact lens moat = FDA-regulated, eye doctor channel loyalty, patients don't switch brands; daily disposable + myopia management tailwinds secular; GrossM 65.5%, OM 16.7%, NM 9.2%, D/EV ~0.065, FCF 10.6%, RevG 7.9%; ROE 4.6% only blocker — goodwill ($3.85B) from acquisitions suppresses stated ROE; ROTCE ~8.5% ex-goodwill, still below gate; gate: ROE crossing 10% as NI scales; added WATCHLIST 2026-08-07
    'CELH',  # Celsius Holdings — energy drink challenger (PepsiCo distribution deal = real national shelf presence); RevG 137%, GM 50.4%, OM 19.8%, NM 5.9%, FCF $178M — 6/7; ROE 8.1% only blocker (gate ≥ 10%); 0/4 MA, -58% from highs — structure badly broken post-PepsiCo inventory reset; gate: ROE ≥ 10% as scale drives equity returns + MA structure recovers from 0/4
    'SAM',   # Boston Beer Company — craft + flavored malt beverage portfolio: Samuel Adams (premium craft, loyal following), Twisted Tea (hard iced tea, the real growth engine — consistent share gains, working-class/sports audience with strong repeat purchase), Truly Hard Seltzer (category peaked and collapsed post-COVID, significant write-downs dragging GAAP NM negative), Angry Orchard (cider, stable niche), Dogfish Head (craft, acquired 2019); GrossM 48.9%, D/EV 0.019 (near-zero debt, pristine balance sheet), FCF 23.0% (exceptional — operating cash machine intact despite GAAP losses); OM 9.3% (0.7% from gate), NM -3.6% (Truly inventory/impairment charges, not structural operating failure), ROE -8.6% (follows NM); RevG -3.3% (Truly drag on blended; Twisted Tea growing independently); fwdPE 17.5x; -30% from 52w high ($264 → $184); LT play — Twisted Tea alone is a durable brand with pricing power and no obvious AI/substitution threat; gate: OM ≥ 10% + NM ≥ 5% as Truly charges roll off and Twisted Tea scale lifts blended margins; added 2026-08-05
    'STNE',  # StoneCo — Brazilian SMB payments + credit platform; V/MA-like toll on Brazil's merchant ecosystem (2M+ active merchants, stone-branded POS/software/banking); GrossM 73.6%, OM 44.3%, NM 25.9%, ROE 30.7%, FCF 86.6% — A+ on every quality metric; D/EV 1.835 only blocker — structural credit book artifact (StoneCo lends to merchants, funds loans through debt, same read as IBKR/SCHW where leverage is the business model not deterioration); RevG 4.3% slow (payment volume growth steady, credit portfolio being managed conservatively post-2021 credit loss episode); Nubank (NU) + MercadoPago (MELI) are real competitors — StoneCo differentiates on SMB software integration (vertical POS + ERP + banking in one platform); Brazil macro + BRL currency = structural risk layer; price $10.97 (-22.9% from 200MA) — dislocated from quality; gate: RevG reaccelerating above 10% as merchant base compounds + credit loss ratios holding stable (2021 episode was a stress test the model survived) + D/EV declining as credit book matures; added 2026-07-29
    'CPAY',  # Corpay (formerly FleetCor) — V/MA-like toll economics on corporate payments: fleet cards, B2B payments, lodging, Brazil tolls; GrossM 79.7%, OpM 41.4%, FCF 9.1%, RevG 25.4%, P/E 21.2x — A+ quality on every metric except debt; D/EV 0.334 only blocker — serial acquirer model means debt is structural (buy payment vertical → extract margin → repeat), FCF strong enough to delever fast if acquisitions pause; gate: D/EV ≤ 0.20 sustained 2+ quarters without a new acquisition resetting it
    'DRI',   # Darden Restaurants — Olive Garden + LongHorn + Fine Dining (Capital Grille/Eddie V's); casual dining scale moat + loyalty data + franchise-like unit economics; ROE 53.7%, FCF 4.6%, OM 14.3%, RevG 13.7%, P/E 19.3x — strong across the board; D/EV 0.259 only blocker (restaurant operating leverage + lease obligations, not acquisition debt); grade B; gate: D/EV ≤ 0.20 as FCF compounds down the debt
    'FROG',  # JFrog — universal artifact repository (Artifactory) + software supply chain security (Xray); every build artifact, package, dependency stored and scanned here; deeply embedded in CI/CD pipelines = extreme switching costs once deployed enterprise-wide; GrossM 77.5%, FCF $170M positive (real cash despite negative GAAP OM), RevG 25.8%, near zero debt ($16M total); OM -7.4% only blocker (stock-comp heavy — FCF is the honest signal); software supply chain security tailwind (Log4j/SolarWinds made artifact scanning mandatory); gate: OM crossing 0% as scale drives leverage on R&D/S&M
    'GTLB',  # GitLab — complete DevSecOps platform (source control + CI/CD + security scanning + project mgmt) in a single application; enterprise moat = single-platform control vs GitHub's patchwork integrations, strong self-hosted/air-gap compliance appeal; GrossM 86.8% (higher than FROG), FCF $313M positive, RevG 23.1%, zero debt; OM -6.0% only blocker — closer to crossing 0% than FROG; fwd PE 31x (vs FROG 82x) = more conservatively priced; 39% off 52w highs; same story as FROG — 2-3 quarters tells it; gate: OM crossing 0% sustained
    'GEV',                       # GE Vernova — picks-and-shovels for entire energy transition; supplies wind turbines, gas turbines, grid (transformers/switchgear/HVDC) — every renewable project + datacenter power need touches GEV; OM 5.5% only blocker (offshore wind losses dragging profitable gas+grid mix; inflects as wind rolls off); D/EV 0.012, ROE 75.7%, FCF +3.0%, fwd P/E 46.8x; grade A+; at 52w highs +113% from low, 42% above 40w MA — wait for 20-25% correction (~$870-920)
    'LHX',                       # L3Harris Technologies — defense electronics prime (EW/jamming, SIGINT/ISR systems, tactical comms, space payloads); formed from L3 + Harris merger 2019; differentiated from GD/LMT on electronic warfare + intelligence systems rather than platforms; GrossM 25.7% (defense prime structural — cost-plus), OM 9.8% (0.2% shy of gate), NM 7.3%, ROE 8.2% (merger goodwill suppressing), D/EV 0.174, FCF 12.3% (exceptional — real cash machine), RevG 1.9%; 3 blockers: GrossM structural, OM hairline below gate, ROE below 10% from L3 acquisition goodwill amortizing; same structural defense profile as GD/LMT but not yet at UNIVERSE OM threshold; gate: OM crossing 10% sustained + ROE crossing 10% as goodwill amortizes; added WATCHLIST 2026-08-07
    'COPX',  # Global X Copper Miners ETF — AUM $8.0B; copper = AI datacenter + grid + EV structural demand; 21% off 6mo highs ($95), 9.4% above 6mo lows ($69); below MA10 ($81) + MA20 ($83) + MA50 ($83), all slopes negative; chart-only (ETF); entry: daily MA10 reclaim ~$81
    'GLD',   # SPDR Gold ETF — AUM $150B, gold price proxy; 25% off 6mo highs ($496), 1.3% above 6mo lows ($366); below MA10 ($378) + MA50 ($409); chart-only tracking (ETF); entry: MA10 reclaim or hold at 6mo low support
    'SLV',   # iShares Silver ETF — AUM $37B, silver price proxy; 49% off 6mo highs ($106), 3.5% above 6mo lows ($52); below MA10 ($56) + MA50 ($66); deeper correction than gold — higher beta, higher upside on reversal; chart-only tracking (ETF)
    'NLR',   # VanEck Uranium & Nuclear ETF — AUM $4.87B; AI datacenter baseload + uranium supply constraints thesis intact; 24.9% off 52w highs, 8.7% above 52w lows ($105), below all MAs (daily MA10 $121, MA50 $132); 5 consecutive monthly declines — near support, not yet recovering; entry: wait for daily MA10 reclaim (~$121) or bounce off $105-106 support with volume
    'PEG',   # PSEG — integrated NJ utility + nuclear operator (Salem 1&2 + Hope Creek); same AI/datacenter nuclear PPA thesis as CEG but integrated utility (regulated T&D + nuclear generation) vs CEG pure-play; OM 28.4%, NM 17.7%, ROE 13.4% (PUC-capped), RevG 19.4%, P/E 17.8x; D/EV 0.38 (rate-base utility debt, FERC/PUC approved) + FCF -0.4% (barely negative — nuclear refueling cycles + grid modernization capex) both blocking; grade A; gates: D/EV delevering + FCF inflection as nuclear PPAs convert to contracted cash flows
    'NEE',   # NextEra — world's largest renewable platform (wind/solar/battery) + FPL (best-run regulated utility in US); OM 30.2%, NM 29.4%, ROE 10.3%; D/EV 0.352 (Dominion acq debt, can resolve) + FCF -10.2% (renewable capex → contracted cash flows once online, not perpetual like DUK); grade A, 2 blockers both have resolution paths; at 40w MA support, 10% off highs 2026-07-01
    'VICI',  # VICI Properties — largest gaming/experiential REIT; triple-net leases with Caesars (45%), MGM, Venetian, Hard Rock at 15-20yr terms with CPI escalators; GrossM 99.1%, NM 76.8%, FCF $1.28B, ~5.5% yield, payout 61% AFFO (conservative for REIT); ROE 11.3% (gate ≥15%) + D/EV 0.62 (gate ≤0.50) both block — both REIT-structure artifacts: real estate at historical cost compresses ROE, leverage secured by experiential assets generating rent is not deteriorating debt; zero tenant defaults since 2017 IPO; moat = gaming license tied to location (tenants cannot relocate without VICI consent); grade B+; gate to universe: ROE inflecting toward 15% as FFO scales + D/EV delevering organically
    'WEC',   # WEC Energy Group — regulated Midwest utility (Wisconsin/Illinois/Michigan); OM 29%, NM 16.2%, ROE 11.7%, RevG 9%; D/E 1.53 (IOU rate-based capex, FERC/PUC approved — structural not deteriorating) + FCF -$2B (grid modernization + AI datacenter load buildout in Wisconsin corridor) + ROE PUC-capped at ~11%; B (4/7); 4/4 MA aligned, slope +0.12 — cleaner margins than LNT, AI datacenter demand angle (Microsoft/hyperscaler buildout in Wisconsin)
    'LNT',   # Alliant Energy — regulated Midwest utility (Iowa/Wisconsin); OM 21%, NM 18.6%, ROE 11.3%, RevG 5%; D/E 1.60 + FCF -$1.2B + ROE PUC-capped — same structural blockers as WEC; B (4/7); 4/4 MA aligned, slope +1.53; smaller ($20B) and less differentiated than WEC/NEE — watching for margin improvement
    'XEL',   # Xcel Energy — regulated electric/gas utility (MN, CO, TX Panhandle, NM; ~3.7M customers); OM 22.7%, ROE 9.9% (PUC-capped — just under 10% gate), D/E 173 (structural rate-base capex, FERC/PUC approved), FCF -$7.9B (capex-heavy buildout) + RevG -5.1%; same blocker profile as WEC/LNT (not deteriorating, structural); dividend yield ~3%, payout 64%, fwd P/E 17x; datacenter angle: Colorado (Denver metro hyperscaler cluster) + Minnesota = rate base expansion as datacenter load grows; also largest wind generator in the US (coal-to-wind transition = rate base additions); gate: ROE inflecting above 10% + RevG turning positive as datacenter contracts come online; added 2026-08-03
    'AMG',   # Affiliated Managers Group — multi-boutique AM (AQR, Tweedy Browne etc.); owns fee economics in independent boutiques, asset-light; OM 22.1%, NM 35.5%, ROE 21.8%, FCF 2.6%, fwd P/E 8.5x; D/EV 0.245 only blocker (structural debt to buy stakes, paying down with FCF); grade A
    'NTRS',  # Northern Trust — UHNW wealth management + global asset servicing (custody for institutional); deep trust bank franchise: serves family offices, endowments, ultra-high-net-worth individuals where relationships are generational and switching is rare; OM 42.5% exceptional (best-in-class among banks), NM 24.7%, ROE 17.1%, RevG 36.4%; D/EV 0.397 primary blocker (real bank debt — structured notes + long-term borrowings, not a yfinance artifact); FCF 0%, GrossM 0% banking artifacts; 4/4 MA aligned, RSI 74.9; gate: D/EV compressing below 0.25 as structured note maturity schedule reduces leverage; judge by: UHNW AUM + trust fee revenue + NIM trend; added WATCHLIST 2026-08-08
    'JLL',   # Jones Lang LaSalle — global #1 commercial real estate services (leasing brokerage, property management, capital markets, project management, workplace consulting); franchise moat: multinational corporations use JLL globally, no regional player can match the cross-border service network; GrossM 51.2%, FCF 9.0%, RevG 10.8%, ROE 13.5%, D/EV 0.164; OM 4.6% + NM 3.6% both well below gates — CRE services are structurally thin-margin (high-touch labor-intensive: brokers, PMs, project managers), structural not fixable; 5/7 gates; 4/4 MA aligned, RSI 63.8; gate to UNIVERSE: OM crossing 10% sustained as capital markets revenue recovers with transaction volumes + CRE services mix shifts toward higher-margin advisory/tech-enabled platforms; added WATCHLIST 2026-08-08
    'CRH',   # CRH plc — largest building materials company globally (aggregates, cement, asphalt, ready-mix concrete, construction products); redomiciled primary listing to NYSE 2023; same geological moat profile as VMC/MLM (permit scarcity near population centers) but broader: also includes downstream concrete products + building envelope; GrossM 36.2% structural (mining + manufacturing — same exception as VMC/MLM), OM 19.0%, NM 9.9%, ROE 15.8%, D/EV 0.233 (serial acquisitor — real leverage, primary blocker), FCF 3.0%, RevG 5.6%; 5/7 gates; 0/4 MA, RSI 42.9, MACD below signal — chart broken right now; gate to UNIVERSE: D/EV ≤ 0.20 as FCF deleverages + MA structure recovers (0/4 is the tell — don't touch until weekly alignment improves); added WATCHLIST 2026-08-08
    'NRG',   # NRG Energy — de-lever play; LS Power acq doubled fleet+debt, targeting 3x net leverage, Fwd P/E 11x, yield-sensitive re-rate when 10yr < 4.0%
    'TLN',   # Talen Energy — independent power producer; Susquehanna nuclear (2.5GW, Pennsylvania) + natural gas fleet; first direct nuclear-to-datacenter PPA in US (Amazon AWS, long-term contracted at premium rates for 24/7 carbon-free power); FCF 7.9% standout (real cash), fwdPE 12.3x cheap for a contracted nuclear asset; GrossM 40.1%, OM 17.2%, NM -0.6% (barely negative), ROE -1.9%, D/EV 0.303 — all blocking; RevG 97% is post-bankruptcy base comparison, not organic; emerged from Ch.11 May 2023, debt is manageable given FCF; "not sure but getting better" thesis — AWS deal is structural but NM still inflecting and debt elevated; grade B; gate: NM turning consistently positive + D/EV ≤ 0.25 as FCF deleverages + second major datacenter PPA validating Susquehanna as a platform asset
    'VST',   # Vistra — deregulated nuclear+gas (Energy Harbor acq), Texas/ERCOT exposure; OM 26.6%, ROE 42.9%, FCF +0.9%, RevG 43.4%, fwd P/E 14.1x; D/EV 0.265 only blocker (closer to threshold than NEE); grade A single blocker — cleaner than CEG on framework metrics; 27.6% off 52w high, below 20w+40w MAs; promote when D/EV ≤ 0.20 + MA structure recovers
    'LNG',   # Cheniere Energy — largest US LNG export terminal operator (Sabine Pass + Corpus Christi); long-term take-or-pay SPAs (20yr contracts) = utility-like contracted cash flows; Europe permanent de-Russian gas = structural LNG demand floor; FCF $1.7B + ROE 28.9% show real economics; D/E 3.2 structural terminal infrastructure debt (same read as telecom capex, not deteriorating); GAAP OM distorted by commodity MTM hedging accounting — FCF is the signal, not OM; B (3/7); MA 3/4, slope negative — below MA20w $249, entry on weekly alignment recovery
    'LDOS',  # Leidos — #1 US defense IT services company; Defense & Intelligence (DoD/IC classified IT + cyber), Civil (FAA NextGen air traffic, TSA biometrics, DHS border systems), Health (VA/DoD electronic health records, federal health IT); Dynetics acquisition (2020, $1.65B) added space + hypersonic defense R&D; government IT = long-term IDIQ contracts + classified clearances = sticky revenue; GrossM 17.9%, OM 12.2%, NM 8.2%, ROE 30.6%, FCF 5.6%; D/EV 0.323 only blocker (Dynetics acquisition debt — not structural to business model, paying down via FCF); fwdPE 9.9x cheap; -37% from 52w high ($205 → $130) — significant dislocation; gate: D/EV ≤ 0.20 as Dynetics debt amortizes via $5.6% FCF yield; 2-3 quarters; added 2026-08-05
    'MOD',   # Modine Manufacturing — AI datacenter thermal/cooling (heat exchangers, liquid cooling); structural picks-and-shovels for AI power density problem; NM 4.3% (needs 5%) + FCF -0.7% (needs >0%) both blocking — metrics improving from 3.8%/−1.0% at FUTURE_RADAR promotion, direction right; gate: NM ≥ 5% + FCF turning consistently positive as datacenter cooling volumes scale; promoted FUTURE_RADAR → WATCHLIST 2026-07-29
    'KTOS',  # Kratos — drone/defense tech; margins thin now, scaling with DoD contracts
    'FLUT',  # Flutter Entertainment — global online sports betting; FanDuel #1 US (~45% share) + Paddy Power/Betfair (UK/Ireland) + Sportsbet (Australia) + Sisal (Italy) + PokerStars; Betfair exchange model (P2P betting, FLUT takes commission) = structurally lower cost than traditional sportsbook; OM ~12%, NM ~9%, FCF ~4%, RevG ~22%, ROE ~12%; D/EV ~0.30 (serial acquisition debt — Sisal 2022 + PokerStars integration) only blocker; two-speed business: mature international at high margins subsidizing FanDuel US scale-up; gate: D/EV ≤ 0.20 as FCF deleverages
    'PGY',   # Pagaya Technologies — AI-powered credit underwriting network; embeds into bank/lender origination flows, expands credit access via ML risk models; NM 9.1%, ROE 19.5%, FCF 11.3% all strong; D/EV 0.593 the one blocker — improved from 0.81 at FUTURE_RADAR promotion but still well above 0.20 gate; gate: D/EV ≤ 0.20 as credit book matures and debt amortizes; promoted FUTURE_RADAR → WATCHLIST 2026-07-29
    'UPWK',  # Upwork — freelance marketplace; D/EV 0.44 (converts) only blocker, margins/FCF solid
    'CLS',   # Celestica — AI infra contract manufacturer (servers, networking), ROE 52%, D/EV 0.02, gross margin 12% blocks universe
    'PRGS',  # Progress Software — serial acquirer of mature enterprise software: OpenEdge (30-40yr installed base low-code apps, near-impossible to rip out), Telerik/Kendo UI (developer UI components), MOVEit (managed file transfer); GrossM 85.6%, FCF 18.6% (exceptional), fwdPE 6.5x = priced like broken, runs like cash cow; OM 18.5% + ROE 18.6% both 1-2% below gate; D/EV 0.461 serial acquisition debt = main blocker; RevG 6.8% — mature, not a growth story; MOVEit 2023 ransomware breach created liability overhang + reputational hit, but customers stayed (switching costs > breach risk); value play: FCF at 6.5x is the signal, not the headline metrics; grade B; gate: D/EV ≤ 0.25 as FCF deleverages + OM crossing 20% as acquired businesses optimize
    'SSNC',  # SS&C Technologies — fund admin infra, $1.28B FCF, extreme switching costs, debt 0.32 only blocker
    'SYM',   # Symbotic — warehouse AI robotics, Walmart-backed; revenue scaling, margins early
    'AMSC',  # American Superconductor — power electronics, grid/defense; OpM 5.1%, one filter away
    'BMY',   # Bristol-Myers Squibb — de-lever + profit growth play; Celgene debt paydown near complete, Eliquis+Opdivo FCF, NI inflecting
    'TGTX',  # TG Therapeutics — Briumvi (ublituximab, anti-CD20 MS); faster infusion than Ocrevus, scaling fast; NM 66%, OM 17%, GrossM 83%, ROE 112%, RevG 69.6%, fwd P/E 18.6x; D/E 1.29 (commercialization converts) + FCF -$30M blocking; watching from distance — wait for real discount before considering
    'VCYT',  # Veracyte — genomic diagnostics; moat = guideline inclusion (NCCN/medical society); Afirma (thyroid indeterminate biopsy, prevents unnecessary surgery) + Decipher Prostate (active surveillance vs treatment, growth engine) + Percepta/Envisia; OM 16.3%, NM 16.2%, GrossM 72.9%, D/E 0.029, FCF $105M, RevG 21.5%; ROE 6.9% only blocker (Decipher acq goodwill, resolves as earnings scale); 4/4 MA aligned, price at MA10d
    'MDT',   # Medtronic — largest pure-play medtech (cardiac rhythm mgmt, spine/neuro surgery, diabetes CGM, surgical robotics Hugo); OM 22.0%, NM 13.2%, FCF 4.3%, fwd P/E 13x, RevG 9.9%, ~3.5% dividend; ROE 9.8% (gate ≥10%) + D/EV 0.229 (gate ≤0.20) both blocking — both acquisition artifacts from Covidien ($50B, 2015) and subsequent M&A inflating goodwill and leverage, not structural deterioration; grade B; gate: ROE crossing 10% + D/EV ≤ 0.20 as FCF deleverages acquisition debt
    'BIIB',  # Biogen — neuroscience pure-play; Leqembi (lecanemab, w/ Eisai) first approved Alzheimer's disease-modifier, subcutaneous monthly formulation removes IV burden; zuranolone (depression) via Sage partnership; ROE 7.7% + D/EV 0.21 blocking; MS revenue decline (Tecfidera generics) masking neuro pipeline value
    'COST',  # Costco — membership moat, not a margin story; OM ~3% by design (merchandise passes savings to members, fee stream runs at ~95% margin); screen blocks on OM/NM — low margins are the product, not a flaw; measure by membership fee growth + renewal rate (~93%) + ROIC; currently 0/4 MA (CMF -0.20, distribution); promote to UNIVERSE on 4/4 recovery
    'ORLY',  # O'Reilly Auto Parts — Akre compounder; 18% OM, 14% NM, ROA 13.8% (ROE negative from 20yrs buybacks); ROA just below 15% threshold; D/EV 0.10, P/E 29x, exceptional execution
    'TDG',   # TransDigm — aerospace parts monopolist, 47% OM, 22% NM; D/EV 0.325 structural debt (leveraged rollup model, won't change); watch if debt pays down or FCF re-rates
    'ESE',   # ESCO Technologies — niche industrials: RF/EMC test chambers (ETS-Lindgren), utility grid modernization/power quality, aerospace filtration (VACCO); GrossM 41.9%, OM 15.5%, FCF $320M positive, RevG 33.5%, D/EV 0.024 (near zero debt); ROE 9.2% only blocker — same niche-industrial profile as HEICO but murkier moat (collection of niches vs HEICO's unambiguous FAA-PMA franchise); NM 24.7% > OM 15.5% anomaly — likely one-time tax benefit, watch normalize; fwd PE 36x (cheaper than HEI at 50x); B grade; gate: ROE crossing 12%+ as revenue scale compounds
    'FISV',  # Fiserv — payment processing + Clover POS + banking tech, extreme switching costs; ~33% OM, 15% NM; D/EV ~0.26 from First Data acquisition; ~$3-4B FCF/yr paydown, 1-2yr to threshold
    'APD',   # Air Products — industrial gases, green/blue hydrogen megaproject bet ($15B+, NEOM/Louisiana); D/EV 0.224 + FCF -5.6% from capex cycle both blocking; new CEO reviewing strategy; watch for FCF inflection as projects come online
    'PYPL',  # PayPal — OM 18%, NM 15%, ROE 25%, FCF 11%, P/E 7.8x; D/EV 0.30 only blocker (customer float structural); Chriss margin recovery showing in numbers
    'EVTC',  # EVERTEC — dominant payment processing network in Puerto Rico (~75% market share in captive US-regulated geography) + expanding LatAm (Colombia, Chile, Costa Rica, Ecuador); processes credit/debit, ACH, ATM networks; revenue = recurring transaction fees on every payment in those markets; LatAm digital payment penetration still early-innings = structural growth runway; GrossM 51.1% (payment network infra, structural), OM 19.4%, NM 9.8%, ROE 14.8%, FCF 8.5%, RevG 19.7% — five gates clear; D/EV only blocker (legacy Apollo LBO debt, not deteriorating); fwdPE 6.8x cheap for payment infra with 19.7% growth; gate: D/EV ≤ 0.20 as 8.5% FCF yield systematically deleverages
    'IOT',   # Samsara — fleet/IoT SaaS, GM 76%, zero debt, 30% RevG, FCF just turned positive; OM 1.5% blocking, 2yr runway to A/A+ as scale drives margin
    'GFS',   # GlobalFoundries — specialty foundry (RF, automotive, IoT); 5/6 filters pass, ROE 6.8% only blocker (capital-heavy fab structure)
    'PWR',   # Quanta Services — dominant grid/electrical infrastructure contractor; OM 4% blocks now, watch for 7-8% as AI datacenter + grid modernization drives project mix higher
    'DY',    # Dycom Industries — dominant specialty telecom contractor (fiber optic cable installation, aerial/underground construction); primary customers AT&T/Comcast/Verizon/Charter; BEAD program ($42.5B federal rural broadband funding) = multi-year contracted backlog; RevG 56.1% shows demand surge is real; OM 7.3% + GrossM 20.5% structural contractor ceilings (same archetype as PWR — labor-intensive, margin expansion is the gate); D/EV 0.204 hairline above gate; ROE 19.7%, FCF 2.0%; 4/7; 2/4 MA; gate: OM crossing 10% as BEAD project mix + crew utilization improves; added WATCHLIST 2026-08-08
    'SITM',  # SiTime — MEMS-based silicon timing near-monopoly (~70% share) displacing quartz crystal oscillators across 5G base stations, AI datacenter synchronization, automotive ADAS, industrial IoT; fabless, TSMC-manufactured; moat = MEMS expertise + software-programmable frequency (quartz is fixed, silicon is tunable) + qualification switching costs in telecom/auto; GrossM 58.7%, OM 10.6% (just clearing gate for first time post-trough), NM 3.0% + ROE 1.3% blocking — cyclical recovery from brutal 2022-23 inventory correction, earnings lagging revenue; RevG 126.5% = recovery base effect + real demand, not steady-state; D/EV 0.063; 4/4 MA but +116.2% above 87w MA = extreme structural extension (price $725, 87w MA $335) — market pricing years of monopoly earnings ahead of actual earnings; 10w slope -5.9% turning down; gate to UNIVERSE: NM ≥ 5% + ROE ≥ 10% as revenue scale absorbs fixed R&D/opex — likely 2-3 quarters if RevG sustains at 40-50%
    'LSCC',  # Lattice Semiconductor — low-power FPGAs, 60%+ gross margin, zero debt; AI edge + industrial; cyclical trough recovery
    'ONTO',  # Onto Innovation — advanced packaging inspection/metrology; HBM + chiplet complexity = more inspection; picks-and-shovels for AI silicon
    'INTC',  # Intel — x86 architect in foundry transition (Intel 18A); OM/NM/ROE all blocking post-Gelsinger restructuring; Lip-Bu Tan CEO, cost reset underway; multi-year turnaround
    'TOST',  # Toast — restaurant POS/payments platform; ROE 22.5%, FCF 4%, rev growth 21.9%, near-zero debt; OM 6.7% + NM 6.4% blocking; grades A, 0/4 MA; strong switching costs, margins scaling
    'FIG',   # Figma — design collaboration SaaS; 79.8% gross margin, FCF 8.6%, 46.1% rev growth; OM -41.2% post-IPO investment spend blocking; grades B (OM negative caps grade); Adobe tried $20B acquisition, IPO'd at $9.5B — quality business finding its level
    'COIN',  # Coinbase — digital asset exchange, crypto theme proxy; 85.5% gross margin, FCF 5.4%; OM -7.1% + rev growth -30.8% (crypto volume cycle) blocking; grades B, 0/4 MA; cyclical — watch for volume recovery + OM turning positive
    'CRCL',  # Circle Internet Group — USDC stablecoin issuer; revenue model = interest on $50-60B Treasury reserves backing USDC; at 5% rates × $50B = ~$2.5B revenue; NOT a trading platform (contrast with COIN) — pure infrastructure/toll-road; USDC is the institutional stablecoin (fully audited vs Tether's opacity), real switching costs in DeFi/payments rails; structural blocker: Coinbase revenue-share eats 50%+ of interest income → gross margin compresses to 8% despite near-100% theoretical spread; net margin -2.8% + FCF -$141M blocking now; rate sensitivity is the core risk (Fed cuts = revenue cuts, mechanically — every -100bps on $50B = -$500M revenue); bull case: GENIUS Act stablecoin regulation = compliance moat + higher entry barrier for banks/competitors; Arc blockchain (own L1) = toll on currency + rails if it scales; RevG 20%, fwd PE 33x, zero debt ($15M), $1.5B cash — balance sheet clean; gate: OM > 10% sustained (needs rate stability + Coinbase share renegotiation or USDC supply growth offsetting cuts) + FCF turning positive; IPO'd at ~$193 (Apr 2026), -66% to $65 — peak rate + peak hype unwind; watch at 0/4 MA for structure recovery alongside rate cycle clarity
    # --- Photonics / Optical Interconnect ---
    'COHR',  # Coherent Corp — optical components (800G/1.6T datacenter interconnect + telecom); OM 13.6%, NM 7.1%, D/EV 0.045; ROE 4.7% + FCF -0.3% blocking; post II-VI merger integration phase; watch FCF inflection
    'FN',    # Fabrinet — precision optical/photonic contract manufacturer (clean-room assembly of optical transceivers, networking hardware, medical devices); primary manufacturer for Coherent, Lumentum, Ciena — the factory behind AI datacenter optical interconnects without owning the IP; GrossM 12.0% structural exception (contract manufacturing model — same lens as FERG/COR, margin is for process precision not IP ownership; 12% is exceptional for a CM); OM 9.9% ✗ (one quarter from 10% gate), NM 9.9% ✓, ROE 20.0% ✓ (strong capital efficiency despite thin GrossM), D/EV 0.0% ✓ (zero debt — exceptional for manufacturing), RevG 39.3% ✓; FCF -$79M ✗ (capex ramp for AI optical volume surge); 2 real blockers: OM 9.9% + FCF negative; Thailand manufacturing base = cost advantage + geopolitical concentration risk; gate: OM crossing 10% sustained + FCF turning positive as 800G/1.6T optical capex normalizes; added WATCHLIST 2026-08-18
    # --- Defense / Drones ---
    'AVAV',  # AeroVironment — defense drones (Switchblade loitering munition, Puma ISR); RevG 143.4%, D/EV 0.108; OM -5.1% scaling with DoD contracts; proven battlefield platform
    # --- Critical Materials ---
    'ALB',   # Albemarle — largest lithium producer (Chile/Australia mines); OM 24.8%, FCF 4.1%, D/EV 0.095; NM -4.2% from lithium price cycle (not structural); long-term EV battery supply chain position
    # --- Solar ---
    'S',     # SentinelOne — AI-native cybersecurity platform, direct CrowdStrike competitor; GrossM 73.2%, RevG 20.8%, FCF 5.0% (positive, unusual for loss-making SaaS); OM -28.8% + NM -30.4% hard blockers; ROE -21.4%; watch OM crossing 0% and trending toward 10%+ over 2-3 quarters as scale drives margin inflection

    'CAVA',    # CAVA Group — Mediterranean fast-casual (hummus/pita/bowls); the CMG analog in a less-penetrated cuisine category; company-owned model, same unit economics playbook; RevG 32.1% (still expanding rapidly, ~350 locations vs CMG's ~3,500 = long runway); GrossM 37.7% (restaurant ceiling, same as CMG); OM 6.4% (needs 10%), NM 4.8% (needs 5%), ROE 8.0% (needs 10%), FCF -0.2% (essentially breakeven) — all 4 within 2-3 quarters of clearing as new units mature and operating leverage kicks in; D/EV 0.066 (near-zero debt, clean balance sheet); fwd P/E 84x (growth premium, not a value entry); gate: OM ≥ 10% + NM ≥ 5% + FCF positive + ROE ≥ 10% — unit-level AUV growth + store maturity is the path, not a business model change; added 2026-08-04

    'PINS',    # Pinterest — visual discovery + social commerce platform; 570M+ MAU, strong advertiser demand signal; GrossM 80%, FCF 7.5%, NM 7.6%, RevG 17.8%, D/EV 0.085, fwdPE 11x; OM -3.3% (needs 10%) + ROE 8.9% (needs 10%) the only two blockers — both within 1-2 quarters of clearing as ad platform operating leverage kicks in; shopping/commerce integration (Amazon, Salesforce partnerships) expanding monetization per user beyond standard display ads; added 2026-08-05

    'FVRR',    # Fiverr — two-sided freelance marketplace (Fiverr Business, Pro, Seller Plus); GrossM 82%, FCF 23.7% (exceptional for marketplace — structural cash generation), NM 7.2%, D/EV 0.026; OM 6.0% (needs 10%) + ROE 7.1% (needs 10%) + RevG -10.0% (declining — AI reducing demand for some commodity freelance categories) all blocking; the FCF at 23.7% is the honest signal — the business is generating real cash even while revenue contracts; gate: RevG stabilizing/turning positive as higher-value professional services replace commodity gigs + OM ≥ 10% as take-rate expands on Fiverr Business tier; added 2026-08-05

    'ETSY',    # Etsy — handmade/vintage marketplace; pure two-sided marketplace (no inventory, no fulfillment): 7.5M active sellers + 90M active buyers; GMS-based take rate ~21% = near-zero marginal cost per transaction once marketplace is liquid; GrossM 72.6%, FCF 16.3% (exceptional for marketplace), D/EV 0.13, fwd P/E 14.8x; OM 10.4% just above gate, NM 11.6%, ROE 2.3% (gate ≥10%) only blocker (buyback-distorted equity base, ROIC cleaner signal); RevG -1.0% (post-COVID normalization — GMS peaked 2021, now stabilizing at higher baseline); differentiated from Amazon/Shopify: handmade/vintage category = not commoditizable (buyers come for uniqueness, not price), high repeat purchase intent; Depop (gen-z resale) + Reverb (music gear) extend addressable categories; gate: ROE inflecting toward 10% as earnings rebuild equity base + RevG turning positive as GMS stabilizes; added 2026-08-04
    'W',       # Wayfair — online furniture/home goods marketplace; largest pure-play e-commerce home category in US + Germany/UK/Canada; CastleGate (Wayfair-owned fulfillment network for large-parcel items) = structural moat for heavy/bulky goods that Amazon doesn't optimize for; GrossM 30.4%, RevG 2.8%; OM -2.4% + NM -4.2% + ROE -136% (distorted from accumulated losses) + FCF -$107M all blocking — housing market + consumer discretionary trough hit Wayfair hard (furniture is the most deferrable home purchase category); fwd P/E 33.6x pricing recovery that hasn't printed yet; D/EV 0.52 converts (structural capital raise, not acquisition debt); 2024-2025 cost reset: 3 rounds of layoffs, advertising efficiency improved, contribution margin per order now positive; gate: OM crossing 0% sustained + FCF turning positive as housing cycle recovers + D/EV compressing; recovery timing tied to housing starts/mortgage rate normalization — rate environment is the macro lever; added 2026-08-04

    'APTV',    # Aptiv — vehicle electrical architecture + ADAS components; makes the wiring harnesses and high-voltage distribution systems that connect every sensor, actuator, and ECU in a modern vehicle; EV vehicles require 2-3× more electrical content than ICE → Aptiv revenue per vehicle grows as EV mix rises regardless of who wins the EV platform war; Signal & Power Solutions (70% of revenue, high-voltage wiring/connectors) + Advanced Safety & User Experience (ADAS sensors, domain controllers); GrossM 13.1% (auto-supplier margins, volume leverage story), OM 7.0% (below 10% gate), NM 4.3% (below 5%), D/EV 0.28, RevG 2.3% sluggish; all filters blocking — auto-supplier margins thin in trough; Motional autonomous driving JV (w/ Hyundai) written down in 2024, cleaned off balance sheet = cleaner story going forward; gate: OM ≥ 10% + NM ≥ 5% as EV platform launches drive content-per-vehicle expansion + D/EV ≤ 0.20 as FCF deleverages; added 2026-08-04

    'TPL',     # Texas Pacific Land — largest private landowner in Permian Basin (~880K acres); land royalty owner: leases surface + mineral acres to Permian operators (Pioneer, Occidental, Devon etc.) and collects a royalty % of every barrel/mcf produced on their land — no drilling, no capex, no operational risk; also runs water services (sourcing + disposal for Permian operators); GrossM 93.2%, OM 77.2%, NM 60.0%, ROE 36.5%, ROA 25.2%, D/EV 0.001 (zero debt), RevG 20.8% — A+ on every metric; FCF -0.2% only blocker (almost certainly yfinance artifact — a passive land royalty business with 60% NM doesn't structurally burn cash); gate: FCF confirmed positive next quarter data refresh; added WATCHLIST 2026-07-29
    'RPRX',    # Royalty Pharma — largest pharma royalty acquirer; owns royalty rights on ~35+ approved drugs (Vertex CF franchise/Trikafta, J&J Imbruvica, AZ Farxiga, Biogen Leqembi, Novartis Promacta, BMS Opdivo); same model as TPL but for drugs: funds late-stage trials or buys existing royalty streams from universities/biotechs, then collects % of drug sales for patent life — no clinical risk, no manufacturing, no sales force; NM 33.9%, ROE 13.8%, RevG 11.0%; D/EV 0.236 (deliberate leverage to fund royalty acquisitions, amortizes on incoming royalty cash — gate ≤ 0.20) + FCF -2.8% (royalty acquisition spend coded as investing outflow, same artifact as TPL — not structural cash burn) both blocking; grade A; added WATCHLIST 2026-07-29
    'CBRS',    # Cerebras Systems — Wafer-Scale Engine (WSE-3): entire silicon wafer as single chip, 900K AI cores, 44GB on-chip SRAM; auto-promoted from FUTURE_RADAR 2026-07-29 [grade B, blocking: Op Margin -7.8%, P/E 183.3x]
    'GCT',     # GigaCloud Technology — B2B marketplace for large-parcel goods (furniture, appliances, fitness equipment, home décor); connects Chinese manufacturers to overseas resellers/retailers; marketplace model with logistics integration (handles warehousing + last-mile for oversized goods) = not pure software; GrossM 23.4% (structural — physical logistics drag, not a SaaS platform), OM 11.8%, NM 10.8%, ROE 32.1% (exceptional), D/EV 0.262, FCF 4.2%, RevG 32.2%; 5/7 gates, grade —; blockers: GrossM 23.4% (structural, marketplace with logistics overhead vs 40% gate) + D/EV 0.262 (above 0.20 — debt vs EV); caution: currently +44.8% above 10w MA — very extended, not an entry, monitor for base; gate to UNIVERSE: GrossM approaching 30%+ as take-rate improves + D/EV ≤ 0.20 via FCF deleveraging; added 2026-08-06
    'SMCI',    # Super Micro Computer — high-density AI GPU server systems integrator; auto-promoted from FUTURE_RADAR 2026-08-20 [grade B, blocking: Debt/EV 0.327, FCF Yield -34.9%]
]

# Future radar — too early for weekly scanning, revisit after 2-3 quarters
# Not fetched, not graded. Documented here so the thesis isn't lost.
# Gate to promote: gross margin consistently positive + OM inflecting toward 0%
FUTURE_RADAR = {
    'SOFI': '[LOCKED] SoFi Technologies — neobank with bank charter (Jan 2022, transformative: hold deposits + fund loans at lower cost than warehouse lines); Galileo B2B banking-as-a-service platform (B2B fee revenue diversifier); GrossM 83.7%, OM 17.0%, RevG 42.6%; ROE 7.1% only quality blocker (bank ROE takes years to ramp after charter conversion — deposits still scaling, loan book seasoning); gate: price $20+ + ROE 10% + FCF positive; do not auto-promote until all three gates clear; added FUTURE_RADAR 2026-07',
    'LYFT': '[LOCKED] Lyft — US-only ride-sharing (~28% US market share vs Uber 72%); FCF 17.0% is the honest signal (cash machine), but OM 2.58% + GrossM 38.0% + D/EV 0.214 all block quality gates; NM 42.3% is a one-time legal settlement gain, not operational — ignore it; moat question: Uber dominance + international optionality = structural disadvantage; gate: price $20+ + OM 10% + GrossM 40% + D/EV ≤ 0.20; do not auto-promote until all four gates clear; added FUTURE_RADAR 2026-07',
    'NEXA': '[LOCKED] Nexa Resources — zinc/lead miner (Peru: Cerro Lindo, El Porvenir; Brazil: Vazante); OM 19.8%, NM 8.0%, ROE 29.9%, FCF 19.2% (exceptional for mining); D/EV 50.7% only quality blocker; zinc secular tailwind: EV chassis galvanization + zinc-air battery chemistry; gate: price $20+ + D/EV ≤ 0.20 as FCF pays down debt; [LOCKED] — below $20 floor ($14.57 as of 2026-08-12); added FUTURE_RADAR 2026-08-12',
    'CABO': 'Cable One (Spark Light) — rural/suburban cable/broadband operator; 3/7 gates; D/EV 0.977 (debt ≈ entire EV), NM -21.9%, ROE -19.9%, RevG -7.3% declining — all critical filters blocking; GrossM 73.8% + FCF 8.2% show the underlying pipe economics are real but the debt load is crushing them; price $38.91 is -74.7% below 87w MA — market pricing existential risk; fiber overbuild + fixed wireless (T-Mobile) intensifying in smaller markets where CABO has no scale advantage vs CHTR; gate to watchlist: D/EV below 0.50 via asset sales or debt restructuring + RevG turning positive + NM crossing 0%; realistically 4-6 quarters minimum; added FUTURE_RADAR 2026-08-07',
    'INSM': 'Insmed — specialty pharma, brensocatib (oral neutrophil elastase inhibitor, FDA approved for bronchiectasis, ASPEN trial); rare lung disease with limited treatment alternatives = real unmet need; GrossM 81.8% (drug economics solid), RevG 229.6% (commercial launch ramp real); OM -65.5%, NM -144.4%, FCF -2.1% — deep investment phase, all margin gates blocking; moat uncertain: bronchiectasis has limited competition now but single-product concentration + patent cliff visibility unknown + pipeline depth TBD; gate to watchlist: OM inflecting toward 0% as launch spend normalizes + FCF turning positive + pipeline asset beyond brensocatib de-risked; added FUTURE_RADAR 2026-08-06',
    'RKLB': 'Rocket Lab — only end-to-end small launch + space systems provider; real revenue, real launches; path to profit is long and capex-heavy; gate to watchlist: OM turning positive + FCF inflection; revisit when launch cadence drives margin scale',

    'AAOI': 'Applied Optoelectronics — datacenter optical transceivers (800G/1.6T AI fabric); real revenue, real AI datacenter demand; OM -8.6% not yet turning; gate to watchlist: OM inflecting positive as AI interconnect volumes scale',
    'MP':   'MP Materials — only US rare earth miner + processor (Mountain Pass CA); DoD contract + Tesla partnership; national security supply chain angle; OM -7.9% from processing build-out; gate to watchlist: processing ramp drives OM positive + FCF inflection',
    'UPST': 'Upstart — AI-powered lending platform; 82.7% gross margin, OM just turning (0.9%); credit cycle exposure structural to lending model; D/EV 0.431 (converts) + FCF -10.1% + ROA 1.8% blocking; gate to watchlist: FCF consistently positive + converts resolved + through-cycle credit performance demonstrated',
    'PRAX': 'Praxis Precision Medicine — neurological disease pure-play; ulixacaltamide (PRAX-944) targeting essential tremor (7M+ US patients, current beta-blocker/primidone standard-of-care has poor tolerability = large unmet need); PRAX-628/PRAX-562 Nav1.6 epilepsy inhibitors in pipeline; Phase 3 T-CALM data drove $37→$366 in one year — the clinical home run has likely printed, now a binary FDA approval bet; pre-revenue ($9B market cap on zero revenue), FCF -$176M burn, near-zero debt; all quality filters block — not a framework name; gate: FDA approval + early commercial revenue traction; if approval comes, re-evaluate as a commercial-stage specialty pharma',
    'DKNG': 'DraftKings — US online sports betting #2 (behind FanDuel/FLUT); strong brand + same-game parlay product; RevG 30%+, FCF turning positive, adj EBITDA now positive; structural margin ceiling from US state tax rates (NY 51%, PA 36% of gross gaming revenue before DKNG revenue) + perpetual promo costs to compete — these are real cash costs, not stock comp distortions; GAAP NM path to 8%+ uncertain vs FLUT which has mature international margins subsidizing the US ramp; gate to watchlist: NM consistently ≥ 8% through multiple quarters showing the state tax + promo overhang is manageable at scale; revisit when FY margin comps clarify the ceiling',
    'FPS':  'Forgent Power Solutions — electrical distribution equipment for data centers, power grid and energy-intensive industrial facilities (ATS, switchgear, transformers, PDUs, substation gear); pure-play AI power infrastructure enabler — every hyperscaler buildout needs this equipment before the servers even arrive; RevG 103% YoY = the demand wave is real and accelerating; OM 10.4% (borderline), NM 2.2% (too thin), ROE/FCF unavailable, P/E 1828x = market pricing massive margin expansion that hasn\'t printed yet; clean balance sheet (D/EV 6.9%); -45% from 52w high = price corrected hard while the business is still on fire; gate to watchlist: NM crossing 5% + FCF turning positive + ROE measurable as volume scale drives operating leverage; the AI power infrastructure thesis is early innings — revisit when margin data catches up to revenue growth',
    'AMR':  'Alpha Metallurgical Resources — pure-play metallurgical coal (coking coal); NOT thermal/power coal — this is the carbon reductant every blast furnace on earth needs to convert iron ore to steel; 70%+ of global steel still made via blast furnace (BF-BOF route), green steel (EAF/hydrogen-DRI) transition is a 20-30yr horizon, not a near-term threat; India + Southeast Asia still building new blast furnaces = structural met coal demand floor; emerged from Alpha Natural Resources bankruptcy as lean operator with near-zero debt (D/EV 0.008) — survived the cycle, balance sheet clean; FCF 3.3% positive even in current trough; currently in met coal price trough (OM -3.1%, NM -1.8%, all quality filters blocking) — fwd PE 5.3x priced for trough not recovery; 18.9% float short (DTC 7.4d) = significant short positioning that amplifies any price recovery; gate to watchlist: OM turning positive sustained (met coal price recovery + cost discipline) + RevG inflecting positive as steel demand recovers; added CYCLICALS 2026-07-29',
    'LMND': 'Lemonade — AI-native insurance platform (renters, homeowners, pet, auto, life); ML underwriting + automated claims = structural cost advantage over legacy carriers IF loss ratios normalize; GrossM 29.3%, OM -14.2%, NM -14.2%, ROE -27%, FCF negative — all quality filters blocking; RevG 79.4% is the standout (premium in-force accelerating fast); the bear case: reinsurance costs + catastrophe exposure + regulatory constraints on AI underwriting = the loss ratio may never reach profitability at scale; D/E clean (0.17); gate to watchlist: loss ratio sustained below 75% for 2+ quarters + OM inflecting toward 0% + FCF turning positive; the RevG is real, the unit economics are not yet; added FUTURE_RADAR 2026-08-05',
    'RBLX': 'Roblox — UGC gaming metaverse platform; 100M+ DAU (primarily Gen Z/Alpha); economy is developer-created: Robux virtual currency + creator royalties = flywheel with near-zero content cost for Roblox itself; GrossM 26.0% (infrastructure-heavy vs pure software peers), OM -13.3%, NM -17.6%, ROE -432% (deficit driven by stock comp + early losses), FCF +5.6% positive (bookings vs deferred revenue accounting creates FCF/GAAP timing gap); RevG 27.8%; D/EV 0.162; all quality filters blocking on margins; thesis: as the user base ages into higher-spending adults + advertising tier launches + more sophisticated dev monetization, GrossM expands past 40% and OM follows; the FCF positive signal is the one honest indicator the cash machine is real; gate to watchlist: GrossM consistently above 40% + OM inflecting toward 0% + NM credibly on path to 5%; revisit 3-4 quarters; added FUTURE_RADAR 2026-08-05',
    'U':    'Unity Technologies — runtime engine for 3D/real-time content (games, simulation, AR/VR, automotive/industrial digital twin); Create + Grow segments; ~50% market share in mobile game engines; went through CEO change + IronSource merger reversal + controversial runtime fee pricing fiasco (2023) that damaged developer trust; GrossM 77.1% (software), OM -15.2%, NM -35%, ROE -20.1%, FCF +3.9% (positive but thin); RevG 16.8%; D/EV 0.119; the turnaround thesis: new CEO (Matt Bromberg, ex-EA) reverting controversial pricing, rebuilding developer trust, refocusing on Create monetization + enterprise simulation (Weta Digital, BMW, Toyota use cases); gate to watchlist: OM inflecting toward 0% on cost discipline + FCF expanding past 10% + RevG accelerating as enterprise wins close + developer NPS recovering; the engine moat is real — developer switching costs are years of workflow investment; risk: Unreal Engine (Epic Games) gaining mobile share while Unity rebuilds; added FUTURE_RADAR 2026-08-05',
    'AADX': 'Applied Aerospace & Defense — aerospace & defense components supplier; positioned as a supplier into the space/defense supply chain (SPCX-adjacent); RevG 21.0% is the one bright spot; GrossM 27.2%, OM -2.1%, NM -4.8%, ROE 0.0%, FCF 0.0%, D/EV 0.224 — all quality filters blocking, margins negative/zero; thinly traded (yfinance API errors on historical data), suggesting recent listing or micro-float; not enough history or margin trajectory to watchlist yet; gate to watchlist: OM turning consistently positive + GrossM approaching 30%+ + FCF measurable positive; revisit 2-3 quarters; added FUTURE_RADAR 2026-08-06',
    'FSLY': 'Fastly — edge cloud platform (CDN + Compute@Edge + application security); Compute@Edge uses WebAssembly to run custom logic at the network edge — the right architecture for AI inference at the edge, real-time APIs, IoT, and latency-sensitive apps; Signal Sciences (acquired) adds WAF/bot management; GrossM 57.1%, FCF 7.7% positive (honest signal), RevG 23.3%, D/EV 0.11 (clean); OM -19.0%, NM -19.5% — deep blockers; NET overlap is narrower than it looks: NET\'s core growth engine is Zero Trust/SASE (ZTNA, CASB, DLP — replacing enterprise VPNs, competing with ZS/CRWD/PANW) — FSLY has nothing in that space; real overlap is CDN pricing + edge compute mindshare (Workers vs Compute@Edge) + WAF; FSLY\'s TAM is smaller but distinct — pure CDN/edge compute/application security developer platform, not enterprise network security; LT runway: edge compute becomes mandatory infrastructure as AI inference moves to the network edge + latency-sensitive workloads (gaming, IoT, real-time fintech) need programmable edge close to users; Fastly 2021 outage damaged reliability trust — watch for recurrence; gate to watchlist: OM inflecting toward 0% as Compute@Edge mix grows + FCF expanding past 10%; added FUTURE_RADAR 2026-08-07',
    'TEM': 'Tempus AI — AI-driven precision medicine platform (Eric Lefkofsky, Groupon founder); largest structured oncology dataset in the US (de-identified genomic + clinical + imaging records from millions of cancer patients); physicians use Tempus to match patients to clinical trials + select treatments based on molecular profiling; TIME-1 trial (AI-guided care protocol) showing measurable outcome improvement = early proof the data moat translates to clinical decisions; GrossM 62.7% (data licensing + genomic sequencing blend), RevG 21.6% — the two honest signals; OM -19.9%, NM -19.3%, ROE -49.9%, FCF -19.3% — heavy investment phase, all margin gates blocking; 2/7 gates; gate to watchlist: OM inflecting toward 0% as data licensing revenue grows as % of mix + FCF turning positive + clinical validation expanding beyond oncology into cardiology/neuropsych; added FUTURE_RADAR 2026-08-07',
    'WGS':  'GeneDx Holdings — clinical genomic sequencing for rare and undiagnosed disease (exome + whole genome sequencing); Mount Sinai-backed (Sema4 merger 2022, Sema4 was the clinical genomics spinout from Mount Sinai Health System); thesis: largest rare disease variant database in the US — the more genomes sequenced, the better the AI interpretation of variants of uncertain significance (VUS), which compounds into more accurate diagnoses and better reimbursement; data moat scales with volume in a way that standalone sequencers cannot replicate; GrossM 69.4% (diagnostics platform economics real), RevG 11.4%; OM -15.2%, NM negative, ROE -40.8%, FCF -10.5% — investment phase, all margin gates blocking; 1/7 gates; gate to watchlist: OM inflecting toward 0% as sequencing volume scales + FCF turning positive as AI-assisted variant interpretation improves ASP and payer coverage; added FUTURE_RADAR 2026-08-15',
    'GH':   "Guardant Health — liquid biopsy platform for cancer detection via blood draw (ctDNA = circulating tumor DNA); Shield: FDA-approved colorectal cancer screening test (2024) for the 50M Americans who need colonoscopy screening but don't get it — noninvasive blood test is the wedge; also Guardant360 (companion diagnostics for oncologists selecting targeted therapy) + LUNAR (recurrence monitoring post-treatment); GrossM 65.0% (diagnostics platform economics real), RevG 44.3% (Shield commercial launch ramp), D/EV 7.8% (manageable); OM -38.2% — deep investment phase, all-in on Shield commercial launch; NM negative, ROE negative, FCF barely positive ($26.6M, thin); 2/7 gates; key binary: CMS (Medicare) coverage decision for Shield — without national reimbursement, Shield adoption stalls at cash-pay/commercial-insured; gate to watchlist: CMS coverage removing binary risk + OM inflecting toward 0% as Shield lab volume scales and manufacturing spreads fixed cost + FCF expanding as Guardant360 + LUNAR provide base revenue while Shield ramps; added FUTURE_RADAR 2026-08-17",
    'TWST': 'Twist Bioscience — synthetic DNA on silicon chips; writes DNA sequences at scale using silicon-based oligo synthesis (faster, cheaper, more accurate than traditional phosphoramidite chemistry); enables NGS library prep tools, antibody discovery, drug design, agricultural genomics, and early-stage DNA data storage; real technology, real multi-decade synthetic biology theme; GrossM 52.0% (platform economics real), D/EV 0.015 (near-zero debt), RevG 23.2%; OM -30.6%, NM -31.7%, FCF -0.9% — investment phase, not yet profitable; chart is wildly extended: 4/4 MA but 87w ext +153.6% extreme, RSI 78.2 overbought, running on narrative momentum; 3/7 gates; gate to watchlist: OM inflecting toward 0% + FCF turning consistently positive; note: US company (SF-based, Emily Leproust founder), not Israeli; added FUTURE_RADAR 2026-08-10',
    'VRNS': 'Varonis Systems — data-centric security platform (Israeli-founded: Yakov Faitelson + Ohad Keren, R&D in Israel); detects who has access to what data, flags anomalous access patterns (ransomware touching files, insider exfiltration), automates GDPR/HIPAA compliance classification; differentiated from CRWD/PANW/ZS (perimeter/endpoint) — Varonis lives inside the data layer, different niche entirely; GrossM 77.1% (software quality), FCF 2.8% positive (honest signal — cash generating despite GAAP losses), RevG 18.3%, D/EV 0.109; OM -22.6%, NM -20.5%, ROE -36.0% — SaaS transition from perpetual license compressing reported revenue while ARR builds (accounting timing, not business failure); 4/4 MA, RSI 61.2, 87w ext +6.8% near-base — technically clean and not extended; 4/7 gates; closer to WATCHLIST boundary than deep FUTURE_RADAR (FCF positive + 77% GrossM + 4/4 MA); gate: OM crossing -10% showing SaaS transition converging → 0% → WATCHLIST; added FUTURE_RADAR 2026-08-10',
    # Removed entirely — pre-revenue or survival risk (not FUTURE_RADAR material):
    # SMR (NuScale — first project cancelled), OKLO, XE (pre-revenue nuclear ventures)
    # IONQ (quantum — deeply pre-scale, survival timeline)
    # CRSP, NTLA, BEAM (gene editing — pre-profit, all filters blocking, binary clinical risk)
    # RXRX, RARE (pre-profit biopharma, survival timeline)
    # MRNA (OM -131%), BNTX (OM -576%) — revenue base collapsed, rebuild uncertain
    # ASTS (pre-revenue space), LUNR (pre-profit lunar)
}

# SIP candidates — toll-booth businesses on durable US infrastructure.
# Buy regularly via DCA regardless of short-term price. Not traded — owned.
# Common thread: asset-light, fee/royalty/toll income, compound with secular structural growth.
SIP_WATCHLIST = {
    # --- Financial Market Infrastructure ---
    'NDAQ': 'Nasdaq, Inc. — owns Nasdaq exchange + Nordic exchanges + market technology + financial data; QQQ pays NDAQ licensing fees to use the Nasdaq 100 index; own the exchange, not the stocks on it; Adenza acquisition debt temporary overhang, business model unchanged',
    'MSCI': 'MSCI Inc. — purest index royalty in the world; licenses MSCI EM, MSCI World, MSCI ACWI indices; every ETF tracking these (Vanguard, BlackRock, State Street) pays MSCI a fee forever; no market risk, no execution risk — pure royalty; global passive investing growth = MSCI royalty growth; most asset-light toll booth in financial markets',
    'MCO':  'Moody\'s — ratings duopoly (Moody\'s + S&P = ~80% global market share), entrenched by regulation; every bond issued globally needs a rating; recurring monitoring fees from every rated entity; Buffett held for decades; near-impossible to displace; asset-light, extreme pricing power, debt issuance grows structurally over time',
    'SPGI': 'S&P Global — owns S&P 500 index licensing (every SPY/VOO/IVV pays them) + Platts commodity data + credit ratings + market intelligence; every S&P 500 index fund that exists or will ever exist pays SPGI; combines index royalty + ratings oligopoly + data subscriptions',
    'ICE':  'Intercontinental Exchange — owns NYSE + ICE futures exchanges + large mortgage technology platform (Encompass); toll on every NYSE trade, every ICE futures contract; mortgage tech adds recurring software revenue on top of exchange infrastructure; most operationally complex of the five but dominant positions across asset classes',
    'CME':  'CME Group — owns CME + CBOT + NYMEX + COMEX; toll on every futures contract globally — interest rates, equity index (S&P 500 futures), commodities (oil, gold, corn), crypto; derivatives market notional dwarfs equities; electronic trading scales at near-zero marginal cost; NDAQ analog for derivatives',
    # --- Credit Scoring Infrastructure ---
    'FICO': 'Fair Isaac (FICO) — owns the FICO credit score standard; Fannie Mae + Freddie Mac mandate FICO on every US mortgage; 90%+ of top lenders use it; pure licensing model — banks pay per score query; same score sold billions of times at near-zero marginal cost; regulatory entrenchment makes displacement near-impossible; people know the product, nobody watches the stock',
    # --- Payment Networks ---
    'V':    'Visa — global payment network toll; every card transaction worldwide pays Visa a small %; does not hold credit risk (that\'s the banks); pure toll on global commerce; compound with cashless transition globally; already A+ 4/4 in UNIVERSE — SIP on pullbacks',
    'MA':   'Mastercard — Visa\'s global duopoly partner; same model, slightly more international revenue mix; every cross-border transaction is incremental fee income; global commerce growth = MA growth; already in UNIVERSE',
    # --- Payroll / HR Infrastructure ---
    'ADP':  'Automatic Data Processing — processes paychecks for millions of US businesses; extreme switching costs (HR/payroll systems deeply embedded, re-implementation risk keeps customers locked in); recurring subscription revenue, float income on payroll cash; every new US job added = more ADP revenue; already A+ in UNIVERSE',
    # --- Waste Infrastructure ---
    'WM':   'Waste Management — regulated waste collection oligopoly (WM + RSG = ~50% US market); every community needs waste removed, pricing power structural; long-term municipal contracts, landfill permit moat (impossible to build new landfills); secular tailwind from recycling + renewable natural gas from landfills; quietly compounding business',
    'RSG':  'Republic Services — WM\'s duopoly partner; same landfill permit moat + municipal contract lock-in + route density economics; OM 20.2%, ROE 18.3%, D/EV 0.173, FCF 2.7%; RevG 2.6% (waste is slow-growth by nature — but the compounding is durable and nearly unlosable); not a trading name, not a thesis name — a patient accumulation name; SIP on dips alongside WM',
    # --- BDC / Income ---
    'MAIN': 'Main Street Capital — BDC lending to lower middle market companies; internally managed (removes fee conflict that plagues most BDCs); ~8.4% yield paid monthly + semi-annual special dividends; trades at ~1.55x NAV (premium unusual for BDCs, reflects management quality); ROE 14.4%; not a growth compounder — a durable income machine; SIP monthly for yield compounding',
    # --- AI Memory Infrastructure ---
    'MU':   'Micron Technology — primary US supplier of HBM (High Bandwidth Memory) for NVIDIA AI GPUs; every H100/H200/B200 ships with HBM3E, MU supplies it alongside SK Hynix and Samsung; memory is cyclical but HBM has longer contracted pricing cycles than commodity DRAM/NAND — structural AI demand floor; NM 55.9%, OM 80.4%, ROE 66.6%, near-zero debt (D/EV 0.007), GrossM 72.6%; capex-heavy fab model = FCF thin at cycle peak (0.9%) but that is structural not deterioration; sitting on 20w MA at ~$741 after -22% from 10w ($955) — distribution from cycle highs, long-term structure (43w $509, 87w $305) intact; "enduku ala goli vesaru" = classic semi cycle profit-taking + NAND/DRAM supply concern, not HBM story breaking; SIP at 20w support, add if it flushes to 43w (~$509); gate for full size: 4/4 MA recovery (10w bending back up to price)',
    # --- Rare Disease / Specialty Gene Therapy ---
    'KRYS': 'Krystal Biotech — Vyjuvek (beremagene geperpavec) is the only FDA-approved gene therapy for dystrophic epidermolysis bullosa (DEB), a devastating rare skin disease; monopoly drug with no approved competition; $119.2M Q2 2026 revenue (+24% YoY), $1.1B cash, near-zero debt, A+ on all 7 quality gates; pipeline: KB803 (Netherton syndrome) top-line data Q4 2026, KB407 (CF) + KB111 interim data H2 2026 — multiple shots on goal; dropped -8.5% on clean Q2 beat (Aug 2026) landing exactly on 20wMA at ~$308 — market wanted "beat + raise", got "beat + maintain", punished it; SIP at 20wMA ($308), add on flush to 43wMA (~$271); full size gate: 4/4 weekly MA recovery + pipeline readout catalyst',

    # --- Packaging / Industrial Dividend ---
    'SW':   'Smurfit Westrock — world\'s largest paper-based packaging company (WestRock + Smurfit Kappa merger 2024); corrugated boxes are durable secular demand — every e-commerce shipment (Amazon, Shopify, retail) needs packaging; ~4% dividend yield, FCF $1.36B positive = dividend is FCF-supported not earnings-dependent (NM 1.2% is thin but payout off earnings is misleading); D/E 78.8 is merger debt overhang — same structural pattern as post-acq industrials, manageable given FCF; OM 6.8%, fwd PE 12.9x; ROE 2.1% and NM block quality screener — tracked here as a dividend/income name, not a compounder; SIP on dips for yield accumulation',

    # --- Logistics Real Estate Infrastructure ---
    'PLD':  'Prologis — world\'s largest industrial REIT ($137B mktcap); owns ~1.2B sq ft of logistics real estate clustered near major population centers globally (last-mile delivery hubs for Amazon, FedEx, DHL, UPS, Walmart); properties are irreplaceable — you cannot permit and build a 1M sq ft warehouse next to a major metro in 2026; e-commerce structural growth = permanent logistics infrastructure demand floor; GrossM 75.5%, OM 43%, NM 43.6%, FCF 3.9%, RevG 12.3% — excellent operating metrics; ROE 7.7% + D/EV block via standard filter — both REIT-structure artifacts (same read as VICI: real estate at historical cost compresses ROE, leverage secured by income-generating real assets is not deteriorating debt); ~3.5% dividend yield, payout 92% AFFO (REIT mandatory distribution, FCF-backed); judge by AFFO growth + occupancy rate (historically >95%) + dividend coverage ratio; SIP on pullbacks — own the infrastructure that powers e-commerce, not the e-commerce companies',
}
# Spread universe — tiered by options liquidity
# Rule: only spread where bid-ask is tight enough that slippage doesn't eat the edge
# Tier 1 — indices: tightest spreads, no binary risk, no earnings gaps
# Tier 2 — mega-cap tech: $0.01-0.05 wide near-the-money, massive volume, clean execution
# Tier 3 — large cap tradeable: $0.05-0.15 wide, usable but needs care on entry/exit; avoid earnings windows
#           Tier 3 is the outer boundary — beyond this slippage eats the edge
# Below the line: everything else (pharma binary risk, thin enterprise SaaS, mid-caps, sector ETFs with wide spreads)
SPREAD_UNIVERSE = {
    # Tier 1 — indices
    'SPY':  1,
    'QQQ':  1,
    # Tier 2 — mega-cap tech
    'NVDA': 2,
    'AAPL': 2,
    'MSFT': 2,
    'META': 2,
    'AMZN': 2,
    'GOOGL':2,
    'TSLA': 2,
    # Tier 3 — large cap, tradeable outside earnings (outer boundary)
    'MU':   3,  # semi, $0.05-0.15 wide, avoid earnings window
    'AMD':  3,  # AI accelerator challenger, similar liquidity profile to MU
    'JPM':  3,  # financials, decent volume, macro-driven not binary
    'GS':   3,  # same tier as JPM
    'NFLX': 3,  # consumer streaming, surprisingly liquid options; avoid earnings (8-12% moves)
    'AVGO': 3,  # Broadcom — $1.7T, AI networking + custom silicon; options liquid enough; avoid earnings (10-15% moves)
}

def _get_fundamentals_inner(ticker):
        t    = yf.Ticker(ticker)
        info = t.info
        if not info or ('marketCap' not in info and 'enterpriseValue' not in info):
            return None

        # Debt metrics
        total_debt        = info.get('totalDebt', 0) or 0
        enterprise_value  = info.get('enterpriseValue') or None
        debt_to_ev        = total_debt / enterprise_value if enterprise_value else None

        # Profitability
        gross_margin      = info.get('grossMargins', None)
        operating_margin  = info.get('operatingMargins', None)
        net_margin        = info.get('profitMargins', None)
        roe               = info.get('returnOnEquity', None)
        roa               = info.get('returnOnAssets', None)

        # Valuation — prefer trailing P/E; fall back to forward P/E for high-growth where trailing is distorted
        _pe_raw           = info.get('trailingPE', None)
        _fwd_pe           = info.get('forwardPE', None)
        import math
        _pe_raw           = None if isinstance(_pe_raw, float) and math.isinf(_pe_raw) else _pe_raw
        pe                = None if not isinstance(_pe_raw, (int, float)) else _pe_raw
        pe_is_forward     = False
        if pe is None or pe > 100:
            # Trailing P/E missing/infinite (pre-profit) or stretched (high-growth) — try forward P/E
            _fwd_valid = isinstance(_fwd_pe, (int, float)) and 5 < _fwd_pe <= 500
            if not _fwd_valid:
                _price = info.get('currentPrice') or info.get('regularMarketPrice')
                _fmp   = get_fmp_forward_pe(ticker, _price)
                if _fmp is not None and _fmp > 5:
                    _fwd_pe    = _fmp
                    _fwd_valid = True
            if _fwd_valid:
                pe            = _fwd_pe
                pe_is_forward = True
        # For display: if trailing PE is 50-100 and yfinance has no forwardPE, try FMP as fallback
        if pe is not None and pe > 50 and not pe_is_forward:
            _fwd_valid2 = isinstance(_fwd_pe, (int, float)) and 5 < _fwd_pe <= 500
            if not _fwd_valid2:
                _price = info.get('currentPrice') or info.get('regularMarketPrice')
                _fmp2  = get_fmp_forward_pe(ticker, _price)
                if _fmp2 is not None and _fmp2 > 5:
                    _fwd_pe = _fmp2
        pb                = info.get('priceToBook', None)

        # FCF
        fcf               = info.get('freeCashflow', None)
        market_cap        = info.get('marketCap') or info.get('enterpriseValue') or 1
        fcf_yield         = (fcf / market_cap * 100) if fcf is not None and market_cap else None

        # Price vs MA200d — margin of safety signal
        ma200d            = info.get('twoHundredDayAverage', None)
        _price_raw        = info.get('currentPrice') or info.get('regularMarketPrice')
        price_vs_ma200    = round((_price_raw / ma200d - 1) * 100, 1) if ma200d and _price_raw else None

        # Short interest
        short_pct_float   = info.get('shortPercentOfFloat', None)
        float_shares      = info.get('floatShares', None)
        avg_volume        = info.get('averageVolume', None)
        _short_shares     = (short_pct_float * float_shares) if short_pct_float and float_shares else None
        days_to_cover     = round(_short_shares / avg_volume, 1) if _short_shares and avg_volume else None

        # Revenue growth
        rev_growth        = info.get('revenueGrowth', None)

        # EPS trend — current FY vs prior FY, next FY vs current FY
        fy0_growth = None
        fy1_growth = None
        try:
            ae = t.get_earnings_estimate()
            if ae is not None and '0y' in ae.index and '+1y' in ae.index:
                g0 = ae.loc['0y', 'growth']
                g1 = ae.loc['+1y', 'growth']
                if g0 is not None and not (isinstance(g0, float) and math.isnan(g0)):
                    fy0_growth = round(float(g0) * 100, 1)
                if g1 is not None and not (isinstance(g1, float) and math.isnan(g1)):
                    fy1_growth = round(float(g1) * 100, 1)
        except Exception:
            pass

        return dict(
            ticker          = ticker,
            name            = info.get('shortName', ticker),
            sector          = info.get('sector', ''),
            price           = info.get('currentPrice', None),
            market_cap_b    = round(market_cap / 1e9, 1),
            debt_to_ev      = round(debt_to_ev, 3) if debt_to_ev is not None else None,
            gross_margin    = round(gross_margin * 100, 1) if gross_margin is not None else None,
            operating_margin= round(operating_margin * 100, 1) if operating_margin is not None else None,
            net_margin      = round(net_margin * 100, 1) if net_margin is not None else None,
            roe             = round(roe * 100, 1) if roe is not None else None,
            roa             = round(roa * 100, 1) if roa is not None else None,
            pe              = round(pe, 1) if pe is not None else None,
            pe_is_forward   = pe_is_forward,
            fwd_pe          = round(_fwd_pe, 1) if isinstance(_fwd_pe, (int, float)) and not math.isinf(_fwd_pe) and 5 < _fwd_pe <= 500 else None,
            pb              = round(pb, 1) if pb is not None else None,
            fcf_yield       = round(fcf_yield, 1) if fcf_yield is not None else None,
            rev_growth      = round(rev_growth * 100, 1) if rev_growth is not None else None,
            fy0_growth      = fy0_growth,
            fy1_growth      = fy1_growth,
            price_vs_ma200  = price_vs_ma200,
            short_pct_float = round(short_pct_float * 100, 1) if short_pct_float is not None else None,
            days_to_cover   = days_to_cover,
        )

def get_fundamentals(ticker):
    import time
    # Cache-first: use screener_data_cache.json if available (populated by quality screener run).
    # Prevents duplicate yfinance calls when aligned screener runs after quality screener.
    cache = _get_cache()
    if ticker in cache:
        return cache[ticker]
    # Cache miss — hit yfinance with retries
    for attempt in range(3):
        try:
            result = _get_fundamentals_inner(ticker)
            if result is not None:
                cache[ticker] = result
                _save_screener_cache(cache)
                return result
        except Exception as e:
            print(f"  ⚠ {ticker}: {e}", flush=True)
        if attempt < 2:
            time.sleep(1.5 * (attempt + 1))
    return None

def passes_quality_filter(d):
    """Multi-factor quality filter — not just debt."""
    if d is None: return False

    # Debt filter — the primary ask
    if d['debt_to_ev'] is None: return False
    if d['debt_to_ev'] > 0.20: return False

    # Profitability must be real
    if d['operating_margin'] is None or d['operating_margin'] < 10: return False
    if d['net_margin'] is None or d['net_margin'] < 5: return False

    # Returns on capital — ROA fallback for buyback-heavy companies with distorted book equity
    roe_ok = d['roe'] is not None and d['roe'] >= 10
    roa_ok = d['roa'] is not None and d['roa'] >= 15
    if not roe_ok and not roa_ok: return False

    # FCF positive — if yfinance has no FCF data, allow pass if:
    # (a) high-growth SaaS: rev_growth ≥ 50% + NM ≥ 10%, or
    # (b) strong-margin business (financial services, etc.): NM ≥ 15%
    #     yfinance doesn't report FCF for brokerages/banks — data gap, not negative FCF
    if d['fcf_yield'] is None:
        high_growth_saas = (d['rev_growth'] is not None and d['rev_growth'] >= 50
                            and d['net_margin'] is not None and d['net_margin'] >= 10)
        strong_margin    = d['net_margin'] is not None and d['net_margin'] >= 15
        if not (high_growth_saas or strong_margin):
            return False
    elif d['fcf_yield'] < 0:
        return False

    # Valuation sanity check — stretched P/E rarely ends well
    if d['pe'] is not None and d['pe'] > 100: return False

    return True

def failing_filters(d):
    """Returns list of (filter_name, current_value, threshold) tuples for what's blocking qualification."""
    if d is None: return [('No data', '—', '—')]
    fails = []
    if d['debt_to_ev'] is None:
        fails.append(('Debt/EV', 'missing', '≤ 0.20'))
    elif d['debt_to_ev'] > 0.20:
        fails.append(('Debt/EV', f"{d['debt_to_ev']}", '≤ 0.20'))
    if d['operating_margin'] is None or d['operating_margin'] < 10:
        fails.append(('Op Margin', f"{d['operating_margin']}%" if d['operating_margin'] is not None else 'missing', '≥ 10%'))
    if d['net_margin'] is None or d['net_margin'] < 5:
        fails.append(('Net Margin', f"{d['net_margin']}%" if d['net_margin'] is not None else 'missing', '≥ 5%'))
    roe_ok = d['roe'] is not None and d['roe'] >= 10
    roa_ok = d['roa'] is not None and d['roa'] >= 15
    if not roe_ok and not roa_ok:
        fails.append(('ROE/ROA', f"ROE {d['roe']}% / ROA {d['roa']}%", '≥ 10% / ≥ 15%'))
    if d['fcf_yield'] is None:
        high_growth = d['rev_growth'] is not None and d['rev_growth'] >= 50
        strong_margin = d['net_margin'] is not None and d['net_margin'] >= 10
        if not (high_growth and strong_margin):
            fails.append(('FCF Yield', 'missing (no data relief)', '> 0% or rev>50%+margin>10%'))
    elif d['fcf_yield'] < 0:
        fails.append(('FCF Yield', f"{d['fcf_yield']}%", '> 0%'))
    if d['pe'] is not None and d['pe'] > 100:
        fails.append(('P/E', f"{d['pe']}x", '≤ 100x'))
    return fails if fails else [('Passes all filters', '—', '—')]

def quality_grade(d):
    sector = d.get('sector', '')
    is_financial = 'Financial' in sector
    is_services = sector in ('Industrials',) or any(x in d.get('name', '') for x in ('Accenture', 'Consulting'))

    score = 0
    if d['debt_to_ev'] is not None and d['debt_to_ev'] <= 0.03: score += 2
    elif d['debt_to_ev'] is not None and d['debt_to_ev'] <= 0.15: score += 1

    if is_financial:
        # Gross margin is meaningless for insurers/financials — use FCF yield twice instead
        if d['fcf_yield'] and d['fcf_yield'] >= 5: score += 1
        if d['operating_margin'] and d['operating_margin'] >= 12: score += 2   # OM weighted x2
    elif is_services:
        # Consulting/labour-heavy — gross margin threshold lowered
        if d['gross_margin'] and d['gross_margin'] >= 30: score += 1
        if d['operating_margin'] and d['operating_margin'] >= 15: score += 2   # OM weighted x2
    else:
        if d['gross_margin'] and d['gross_margin'] >= 60: score += 1
        if d['operating_margin'] and d['operating_margin'] >= 20: score += 2   # OM weighted x2

    if d['net_margin'] and d['net_margin'] >= 15: score += 1
    if d['roe'] and d['roe'] >= 20: score += 1
    if d['fcf_yield'] and d['fcf_yield'] >= 3: score += 1
    if d['rev_growth'] and d['rev_growth'] >= 10: score += 1

    # Max score: 9 (D/EV 2 + GM 1 + OM 2 + NM 1 + ROE 1 + FCF 1 + RevG 1)
    # Thresholds unchanged — OM reweighting rewards strong OM, doesn't penalize rest
    if score >= 6: grade = 'A+'
    elif score >= 4: grade = 'A'
    else: grade = 'B'

    # Cap at B when operating margin is negative — pre-profit businesses can score on
    # gross margin + FCF + growth, but an A/A+ alongside OM -40% is misleading
    om = d.get('operating_margin')
    if om is not None and om < 0 and grade in ('A+', 'A'):
        grade = 'B'
    return grade

def fmt(val, suffix='', prefix=''):
    if val is None: return '<span style="color:#484f58">—</span>'
    return f"{prefix}{val}{suffix}"

def pe_html(d):
    pe  = d.get('pe')
    fwd = d.get('fwd_pe')
    if pe is None:
        return '<span style="color:#484f58">—</span>'
    if d.get('pe_is_forward') or (pe > 50 and fwd is not None):
        show = fwd if (not d.get('pe_is_forward') and fwd is not None) else pe
        return f'{show:.0f}x<span style="font-size:9px;color:#8b949e">f</span>'
    return f'{pe:.1f}x'

def entry_html(d):
    """Color-coded % vs MA200d — green ≤5%, amber 5-20%, red >20%. No label: let the reader interpret."""
    pma = d.get('price_vs_ma200')
    if pma is None:
        return '<span style="color:#484f58">—</span>'
    if pma <= 5:
        color = '#3fb950'   # green  — at or near MA200
    elif pma <= 20:
        color = '#e3b341'   # amber  — moderate extension
    else:
        color = '#f85149'   # red    — stretched
    return (f'<span style="color:{color};font-weight:700;font-size:11px">●</span>'
            f'<span style="color:{color};font-size:11px"> {pma:+.0f}%</span>'
            f'<span style="color:#484f58;font-size:10px"> vs MA200</span>')


def eps_trend_html(d):
    g0 = d.get('fy0_growth')
    g1 = d.get('fy1_growth')
    if g0 is None:
        return '<span style="color:#484f58">—</span>'
    c0 = '#3fb950' if g0 >= 5 else ('#e3b341' if g0 >= 0 else '#f85149')
    prefix = '⚠ ' if g0 < 0 else ''
    g0_str = f'{prefix}{g0:+.0f}%'
    if g1 is not None:
        c1 = '#3fb950' if g1 >= 5 else ('#e3b341' if g1 >= 0 else '#f85149')
        return f'<span style="color:{c0};font-size:11px">{g0_str}</span> <span style="color:{c1};font-size:10px">/{g1:+.0f}%</span>'
    return f'<span style="color:{c0};font-size:11px">{g0_str}</span>'

def pct_color(val, good_above=0):
    if val is None: return '<span style="color:#484f58">—</span>'
    c = '#3fb950' if val >= good_above else '#f85149'
    return f'<span style="color:{c}">{val}%</span>'

def build_watchlist_section(watchlist):
    if not watchlist: return ''
    rows = build_watchlist_rows(watchlist)
    return f"""
<div class="section-header">👀 Watchlist — Future Contenders</div>
<div class="section-sub">Exceptional businesses not yet qualifying. Tracked for when valuation or fundamentals cross the threshold.</div>
<table>
  <thead>
    <tr>
      <th>Ticker</th><th>Name</th><th>Sector</th><th>Price</th>
      <th>Op%</th><th>Net%</th><th>ROE%</th><th>FCF Yld</th><th>Rev Grw</th><th>P/E</th><th>EPS FY</th><th>Entry</th>
      <th>Blocking Filters</th>
    </tr>
  </thead>
  <tbody>{rows}</tbody>
</table>"""

def build_watchlist_rows(watchlist):
    rows = ''
    for d in watchlist:
        if d is None: continue
        fails = failing_filters(d)
        blockers = ' &nbsp;·&nbsp; '.join(
            f'<span class="blocker">{f[0]}</span> <span class="blocker-val">{f[1]}</span> <span class="blocker-threshold">→ {f[2]}</span>'
            for f in fails
        )
        rows += f"""<tr>
          <td class="ticker">{d['ticker']}</td>
          <td style="color:#8b949e;font-size:11px">{d['name'][:20]}</td>
          <td style="color:#8b949e;font-size:11px">{d['sector'][:15]}</td>
          <td>${fmt(d['price'])}</td>
          <td>{pct_color(d['operating_margin'], 10)}</td>
          <td>{pct_color(d['net_margin'], 5)}</td>
          <td>{pct_color(d['roe'], 10)}</td>
          <td>{pct_color(d['fcf_yield'], 0)}</td>
          <td>{pct_color(d['rev_growth'], 10)}</td>
          <td style="color:#e6edf3">{pe_html(d)}</td>
          <td>{eps_trend_html(d)}</td>
          <td>{entry_html(d)}</td>
          <td style="font-size:11px">{blockers}</td>
        </tr>"""
    return rows

def build_universe_failing_section(failing):
    if not failing: return ''
    rows = build_watchlist_rows(sorted(failing, key=lambda x: x['ticker']))
    return f"""
<div class="section-header">🔍 Universe — Not Yet Qualifying</div>
<div class="section-sub">In the universe but blocked by one or more filters — good businesses to watch for improvement.</div>
<table>
  <thead>
    <tr>
      <th>Ticker</th><th>Name</th><th>Sector</th><th>Price</th>
      <th>Op%</th><th>Net%</th><th>ROE%</th><th>FCF Yld</th><th>Rev Grw</th><th>P/E</th><th>EPS FY</th><th>Entry</th>
      <th>Blocking Filters</th>
    </tr>
  </thead>
  <tbody>{rows}</tbody>
</table>"""

def build_html(results, watchlist=None, universe_failing=None):
    now  = datetime.utcnow().strftime('%B %d, %Y  %H:%M UTC')
    rows = ''

    for d in results:
        grade    = d['grade']
        grade_cls = 'grade-aplus' if grade == 'A+' else ('grade-a' if grade == 'A' else 'grade-b')

        rows += f"""<tr>
          <td class="ticker">{d['ticker']}</td>
          <td style="color:#8b949e;font-size:11px">{d['name'][:20]}</td>
          <td style="color:#8b949e;font-size:11px">{d['sector'][:15]}</td>
          <td>${fmt(d['price'])}</td>
          <td>${fmt(d['market_cap_b'])}B</td>
          <td class="grade-col"><span class="badge {grade_cls}">{grade}</span></td>
          <td>{fmt(d['debt_to_ev'])}</td>
          <td>{pct_color(d['gross_margin'], 50)}</td>
          <td>{pct_color(d['operating_margin'], 15)}</td>
          <td>{pct_color(d['net_margin'], 10)}</td>
          <td>{pct_color(d['roe'], 15)}</td>
          <td>{pct_color(d['fcf_yield'], 2)}</td>
          <td>{pct_color(d['rev_growth'], 5)}</td>
          <td>{pe_html(d)}</td>
          <td>{eps_trend_html(d)}</td>
          <td>{entry_html(d)}</td>
        </tr>"""

    aplus = sum(1 for d in results if d['grade'] == 'A+')
    a     = sum(1 for d in results if d['grade'] == 'A')

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Quality Growth Screener — {now}</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: 'SF Mono','Fira Code',monospace; background: #0d1117; color: #e6edf3; padding: 28px; font-size: 12px; }}
  h1 {{ font-size: 18px; font-weight: 700; color: #58a6ff; margin-bottom: 4px; }}
  .subtitle {{ color: #8b949e; margin-bottom: 8px; font-size: 11px; }}
  .summary {{ color: #8b949e; margin-bottom: 20px; font-size: 12px; }}
  .summary span {{ color: #e6edf3; font-weight: 700; }}
  table {{ width: 100%; border-collapse: collapse; }}
  th {{ text-align: left; padding: 8px 10px; color: #8b949e; font-weight: 500;
        border-bottom: 2px solid #21262d; font-size: 10px; text-transform: uppercase; letter-spacing: .05em; }}
  td {{ padding: 8px 10px; border-bottom: 1px solid #161b22; }}
  tr:hover td {{ background: #161b22; }}
  .ticker {{ font-weight: 700; color: #e6edf3; }}
  .badge {{ font-size: 11px; font-weight: 700; padding: 2px 8px; border-radius: 3px; }}
  .grade-aplus {{ background: #6e40c9; color: #fff; }}
  .grade-a     {{ background: #1a4731; color: #3fb950; }}
  .grade-b     {{ background: #1f2937; color: #9ca3af; }}
  .criteria {{ background: #161b22; border: 1px solid #21262d; border-radius: 8px; padding: 16px; margin-bottom: 20px; }}
  .criteria h2 {{ font-size: 11px; color: #8b949e; margin-bottom: 10px; text-transform: uppercase; letter-spacing: .08em; }}
  .criteria-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; }}
  .criteria-item {{ font-size: 11px; color: #8b949e; }}
  .criteria-item span {{ color: #58a6ff; }}
  .section-header {{ font-size: 15px; font-weight: 700; color: #f0883e; margin: 40px 0 6px; }}
  .section-sub {{ color: #8b949e; font-size: 11px; margin-bottom: 16px; }}
  .blocker {{ color: #f85149; font-weight: 600; }}
  .blocker-val {{ color: #ffa657; }}
  .blocker-threshold {{ color: #484f58; }}
  .disclaimer {{ color: #484f58; font-size: 10px; margin-top: 24px; border-top: 1px solid #21262d; padding-top: 8px; line-height: 1.8; }}
  details.guide {{ background: #161b22; border: 1px solid #21262d; border-radius: 6px; margin-bottom: 20px; font-size: 11px; }}
  details.guide summary {{ padding: 8px 14px; cursor: pointer; color: #8b949e; user-select: none; list-style: none; }}
  details.guide summary::before {{ content: '▶ '; font-size: 9px; }}
  details[open].guide summary::before {{ content: '▼ '; font-size: 9px; }}
  details.guide .guide-body {{ padding: 12px 16px 14px; border-top: 1px solid #21262d; display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 8px 24px; }}
  .gi {{ display: flex; gap: 8px; align-items: baseline; }}
  .gi-key {{ color: #e6edf3; font-weight: 700; min-width: 80px; flex-shrink: 0; }}
  .gi-val {{ color: #8b949e; line-height: 1.5; }}
  .gi-val .g {{ color: #3fb950; }}
  .gi-val .y {{ color: #e3b341; }}
  .gi-val .r {{ color: #f85149; }}
  .guide-home {{ float: right; color: #58a6ff; font-size: 10px; text-decoration: none; }}
  .guide-home:hover {{ text-decoration: underline; }}
</style>
</head>
<body>
<h1>🔍 Quality Growth Screener <a class="guide-home" href="index.html">← Home</a></h1>
<div class="subtitle">{now}</div>

<details class="guide">
  <summary>How to read this screen</summary>
  <div class="guide-body">
    <div class="gi"><span class="gi-key">Grade A+/A/B</span><span class="gi-val">Quality score — margins, ROE, FCF, debt. <b>A+</b> = all boxes checked. Start here.</span></div>
    <div class="gi"><span class="gi-key">EPS FY</span><span class="gi-val">Analyst estimate: current FY / next FY EPS growth. <span class="g">+15%</span> = growing. <span class="r">⚠ -8%</span> = declining this year.</span></div>
    <div class="gi"><span class="gi-key">Entry</span><span class="gi-val"><span class="g">● ZONE</span> = near MA200, good price. <span class="y">● FAIR</span> = moderate. <span class="r">● RICH</span> = extended, thin margin of safety.</span></div>
    <div class="gi"><span class="gi-key">Signal (wk)</span><span class="gi-val">Weekly RSI+MACD dual confirmation. <span class="g">⬆ bull</span> = momentum recovering. <span class="r">⬇ bear</span> = fading. Fires rarely by design.</span></div>
    <div class="gi"><span class="gi-key">Debt/EV</span><span class="gi-val">Debt as fraction of enterprise value. ≤ 0.05 = near-zero debt. > 0.20 = filtered out.</span></div>
    <div class="gi"><span class="gi-key">FCF Yld</span><span class="gi-val">Free cash flow yield. Positive = generates real cash. Negative = consumes it.</span></div>
    <div class="gi"><span class="gi-key">Best setup</span><span class="gi-val"><b>A+ · ZONE · growing EPS</b> — quality confirmed, price reasonable, earnings trajectory positive.</span></div>
    <div class="gi"><span class="gi-key">Cross-check</span><span class="gi-val">Find the same name in the <a href="aligned_screener.html">Aligned Screener</a> → 4/4 section. Both must say yes.</span></div>
  </div>
</details>

<div class="summary">
  Found <span>{len(results)}</span> companies passing all filters —
  <span>{aplus}</span> A+ &nbsp;·&nbsp; <span>{a}</span> A
</div>

<div class="criteria">
  <h2>Filter Criteria</h2>
  <div class="criteria-grid">
    <div class="criteria-item">Debt/EV <span>≤ 0.20</span></div>
    <div class="criteria-item">Operating Margin <span>≥ 10%</span></div>
    <div class="criteria-item">Net Margin <span>≥ 5%</span></div>
    <div class="criteria-item">ROE <span>≥ 10%</span></div>
    <div class="criteria-item">FCF Yield <span>> 0%</span></div>
    <div class="criteria-item">P/E <span>≤ 100x</span></div>
    <div class="criteria-item">A+: Debt/EV <span>≤ 0.03</span> + 5 more</div>
    <div class="criteria-item">A+: Gross Margin <span>≥ 60%</span> (tech/semis)</div>
    <div class="criteria-item">A+: Op Margin <span>≥ 20%</span> / <span>≥ 12%</span> financials</div>
  </div>
</div>

<table>
  <thead>
    <tr>
      <th>Ticker</th><th>Name</th><th>Sector</th><th>Price</th><th>Mkt Cap</th>
      <th>Grade</th><th>Debt/EV</th><th>Gross%</th><th>Op%</th><th>Net%</th>
      <th>ROE%</th><th>FCF Yld</th><th>Rev Grw</th><th>P/E</th><th>EPS FY</th><th>Entry</th>
    </tr>
  </thead>
  <tbody>{rows}</tbody>
</table>
{build_universe_failing_section(universe_failing)}
{build_watchlist_section(watchlist)}
<div class="disclaimer">
  Data sourced from Yahoo Finance via yfinance. Prices and fundamentals may be delayed or incomplete.<br>
  For informational purposes only. Market dynamics change constantly — these outputs are auto-generated from Yahoo Finance data and may not reflect current conditions. Not tailored financial advice. Not a recommendation to buy, sell, or hold any security. Always do your own research.
</div>
</body>
</html>"""

if __name__ == '__main__':
    import sys
    _SCREENER_CACHE = {}  # force fresh yfinance fetches; aligned_screener reads the populated file cache afterward

    # Ad-hoc signal check: python screener.py --signal TICKER [TICKER ...]
    if len(sys.argv) > 1 and sys.argv[1] == '--signal':
        tickers = [t.upper() for t in sys.argv[2:]]
        if not tickers:
            print("Usage: python screener.py --signal TICKER [TICKER ...]")
            sys.exit(1)
        print()
        with ThreadPoolExecutor(max_workers=8) as ex:
            funds = list(ex.map(get_fundamentals, tickers))
            sigs  = list(ex.map(get_tech_signal,  tickers))
        for t, d, s in zip(tickers, funds, sigs):
            if s:
                arrow  = '⬆' if s[0] == 'bull' else '⬇'
                sig_str = f'{arrow} {s[0]:4}  {s[1]}'
            else:
                sig_str = '—'
            if d:
                grade   = quality_grade(d) if passes_quality_filter(d) else '–'
                blocker = ''
                if not passes_quality_filter(d):
                    blocker = '  blockers: ' + ', '.join(f[0] for f in failing_filters(d) if f[0] != 'Passes all filters')
                print(f"  {t:6}  signal: {sig_str:20}  ${d['price']}  grade: {grade}{blocker}")
            else:
                print(f"  {t:6}  no data")
        print()
        sys.exit(0)

    now = datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')
    print(f"\n  Quality Screener — {now}", flush=True)
    print(f"  Screening {len(UNIVERSE)} companies ...", flush=True)

    cache = _load_screener_cache()

    with ThreadPoolExecutor(max_workers=10) as ex:
        fresh = list(ex.map(get_fundamentals, UNIVERSE))

    raw = []
    for t, d in zip(UNIVERSE, fresh):
        if d is not None:
            cache[t] = d
            raw.append(d)
        elif t in cache:
            print(f"  [{t}] yfinance miss — using cached data", flush=True)
            raw.append(cache[t])

    _save_screener_cache(cache)

    passed  = [d for d in raw if passes_quality_filter(d)]
    failing = [d for d in raw if not passes_quality_filter(d)]
    for d in passed:
        d['grade'] = quality_grade(d)
    passed.sort(key=lambda x: (
        0 if x['grade']=='A+' else 1 if x['grade']=='A' else 2,
        1 if (x.get('fy0_growth') is not None and x['fy0_growth'] < 0) else 0,
        -(x['market_cap_b'] or 0)
    ))

    print(f"  ✅  {len(passed)} companies passed filters  ({len(failing)} in universe not yet qualifying)")

    print(f"\n  Fetching {len(WATCHLIST)} watchlist contenders ...", flush=True)

    with ThreadPoolExecutor(max_workers=10) as ex:
        watch_fresh = list(ex.map(get_fundamentals, WATCHLIST))

    watch_raw = []
    for t, d in zip(WATCHLIST, watch_fresh):
        if d is not None:
            cache[t] = d
            watch_raw.append(d)
        elif t in cache:
            watch_raw.append(cache[t])
    _save_screener_cache(cache)
    watch_raw.sort(key=lambda x: -(x['market_cap_b'] or 0))

    print(f"  👀  {len(watch_raw)} watchlist entries fetched\n")

    now  = datetime.utcnow().strftime('%b %d %Y  %H:%M UTC')
    html = build_html(passed, watch_raw, universe_failing=failing)

    import subprocess, os as _os
    out_path    = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), 'quality_screener.html')
    commit_msg  = f'quality_screener: {now}'
    is_ci       = _os.environ.get('CI') == 'true'

    with open(out_path, 'w') as f:
        f.write(html)
    print(f"  Saved → {out_path}")

    if not is_ci:
        webbrowser.open(f'file://{out_path}')

    if FUTURE_RADAR:
        print(f"\n  FUTURE RADAR — revisit in 2-3 quarters (not scanned)")
        print(f"  {'─'*60}")
        for t, note in FUTURE_RADAR.items():
            print(f"  {t:8}  {note}")

    try:
        repo = _os.path.dirname(out_path)
        subprocess.run(['git', 'pull', '--rebase', '--autostash', 'origin', 'main'], cwd=repo, check=True, capture_output=True)
        with open(out_path, 'w') as f:
            f.write(html)
        subprocess.run(['git', 'add',    'quality_screener.html', 'screener_data_cache.json'], cwd=repo, check=True, capture_output=True)
        subprocess.run(['git', 'commit', '-m', commit_msg],        cwd=repo, check=True, capture_output=True)
        subprocess.run(['git', 'push'],                             cwd=repo, check=True, capture_output=True)
        print(f"  Pushed → GitHub  ({commit_msg})")
    except subprocess.CalledProcessError as e:
        print(f"  Git push skipped: {e.stderr.decode() if e.stderr else e}")
