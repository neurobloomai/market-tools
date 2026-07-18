"""
Quality Growth Stock Screener
Universe: ~115 quality growth names across tech, financials, healthcare, industrials, and consumer.
Filters: Low Debt + High ROIC + Strong Margins + Free Cash Flow + Valuation sanity
Run: python screener.py

Data: Yahoo Finance via yfinance
Disclaimer: For informational purposes only. Not financial advice.
"""

import yfinance as yf
import warnings, os, webbrowser, requests
from datetime import datetime, date
from concurrent.futures import ThreadPoolExecutor
warnings.filterwarnings('ignore')

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
    'CRM','NOW','FTNT','PANW','CRWD','ZS','DDOG',
    'ORCL',                    # Oracle — enterprise software franchise (database + ERP) + OCI cloud infra; cloud commitments driving 20% RevG; OM 36%, NM 25%, GrossM 66%, ROE 53%; D/EV 0.305 (Cerner acq + OCI build debt) + FCF -6.1% (contracted OCI datacenter capex, not speculative — same pattern as CEG nuclear build) both blocking; grade B; gates: D/EV ≤ 0.20 + FCF inflection as OCI capex cycle peaks; added 2026-07-08
    'VEEV','WDAY','TTD','PAYC',
    'ZM',                            # Zoom Video — post-COVID valuation reset complete; A+ (7/7): OM 25%, NM 42%, GrossM 78%, ROE 22%, D/E 0.006, FCF $1.98B (~7.6% FCF yield at $87), RevG 5.5%; near-zero debt + massive cash pile; AI Companion + Zoom Contact Center = monetization runway; fwd P/E 13.8x, priced like value, runs like software; 2/4 MA, below MA10w $98 — scan will surface on weekly alignment
    'BRK-B','CB','AFL','TRV','PGR','AJG','AON','WTW','CINF',
    'NVO','ISRG','EW','IDXX','PODD','WST',
    'MCO','SPGI','MSCI','ICE','CME','CBOE','FDS','BR','NDAQ',
    'ODFL','EXPD','XPO','JBHT','SAIA','KNSL','RLI','CASH','FICO',
    'ROL','CTAS','CPRT','ADP','PAYX','EFX','TRI','IHS','VRSK','IT',
    'MU','MPWR','MRVL','ITW','ROP','SYK','BSX','AMZN','APP',
    'MTD','MANH','FAST','POOL','NVR','DHI','LEN','TOL','DOCS','MKTX','ACGL',
    'CHD','CL','HSY','TJX','GIS','NFLX','LULU','WSM','KMB','DECK',
    'HWM','FSLR','PLAB',           # promoted from watchlist — pass all quality filters
    'WPM',                        # Wheaton Precious Metals — streaming model, 85% gross/65% net margin, zero debt, A+
    'NEM',                        # Newmont — world's largest gold miner; 61.4% OM, 33.9% NM, ROE 25.8%, D/EV 0.049, FCF 8.7%, 45.8% rev growth (Newcrest acq); A+
    'CCJ',                        # Cameco — world's largest uranium producer; OM 18%, NM 18%, D/EV 0.022; ROE ~9-10% cycles with uranium price; nuclear fuel supply for the buildout
    'VRSN',                       # VeriSign — .com/.net registry monopoly, 88% gross/68% op margin, ROE distorted by buybacks (ROA 52%), toll collector
    'CRDO',                       # Credo Technology — AI datacenter interconnect silicon (SerDes/AEC), 68% gross/35% op margin, 157% rev growth, zero debt, A+
    'MTSI',                       # MACOM Technology — analog/mixed-signal for 800G/1.6T optical datacenter interconnects; D/EV 0.02, NM 16%, ROE expanding, A
    'SLDE',                       # Slide Insurance Holdings — specialty E&S insurer, 48% op margin, 40% FCF yield, ROE 60%, 38% rev growth, 4.6x P/E, A+
    'INCY',                       # Incyte — Jakafi franchise pharma, zero debt, 26% op margin, 27% net margin, ROE 31%, A
    'UTHR',                       # United Therapeutics — PAH franchise (Tyvaso/Remodulin/Orenitram), zero debt, 41% OM, 40% NM, ROE 20%; xenotransplantation moonshot optionality, A+
    'BMRN',                       # BioMarin Pharmaceutical — rare disease ERT specialist; Voxzogo (achondroplasia, orphan drug moat) + hemophilia + PKU pipeline; OM 18%, GrossM 51%, D/E 0.23, FCF $459M, fwd P/E 9.1x; NM 8.3% (just under 10%) + ROE 4.5% (goodwill from acquired programs, not operational weakness) — 2 soft blockers; A (5/7); 3/4 MA, slope +1.08
    'EQT',                        # EQT — largest US nat gas producer, Appalachia low-cost, vertically integrated; 57% OM, 50% RevG, D/EV 0.14; powers the structures
    'RRC',                        # Range Resources — Appalachia nat gas, D/EV 0.10, 44% OM, ROE 21%; clean balance sheet, powers the structures
    'CF',                         # CF Industries — largest N. American ammonia/nitrogen producer; green ammonia pivot, D/EV 0.17, 34% OM, ROE 27%; foundation for structures, grades A
    'LIN',                        # Linde — world's largest industrial gases (O2/N2/H2); on-site plant model = permanent switching costs; 28% OM, 20% NM, D/EV 0.10, 8% RevG; slow compounder, never exciting, never disappoints; A
    'ETN',                        # Eaton Corp — electrical switchgear, circuit breakers, power distribution; sits above PWR in grid value chain, 16% OM, 14% NM, ROE 21%, D/EV 0.12
    'HEI',                        # HEICO — aviation aftermarket parts monopolies, 30yr compounder; 25% OM, 16% NM, ROE 17%, D/EV 0.052, pricing power on FAA-approved parts, A+
    'CW',                         # Curtiss-Wright — defense electronics (nuclear instrumentation, aerospace actuation); 18% OM, 14% NM, ROE 20%, D/EV 0.04, defense cycle tailwind, A
    'TW',                         # Tradeweb — electronic bond/derivatives trading platform; 46% OM, 40% NM, ROE 14%, D/EV 0.007, structural shift from voice to electronic fixed income, A+
    'ALAB',                       # Astera Labs — AI datacenter connectivity (PCIe/CXL retimers), 68% gross/35% op margin, zero debt, 200%+ rev growth, A+; promoted from watchlist
    'UBER',                       # Uber — rideshare + delivery marketplace; 14.6% OM, 15.9% NM, ROE 35%, D/EV 0.08, FCF 4.4%; platform flywheel, grades A
    'ABNB',                       # Airbnb — asset-light home-sharing marketplace; NM 19.9%, ROE 32%, D/EV 0.037, FCF solid; yfinance OM distorted by SBC/charges (true OM ~12-13%), quality real
    'ANET',                       # Arista Networks — AI/cloud datacenter networking switches; 42.7% OM, 38.3% NM, ROE 31.5%, zero debt, 35% rev growth, A+; stays in universe until MA10w crosses below MA20w (structure break) or AI datacenter networking thesis breaks — slope cooling is not a structural event
    'SCHW',                       # Charles Schwab — brokerage/custody platform; 49.4% OM, 38% NM, ROE 19.1%, 15.8% rev growth; D/EV 0.465 + FCF None fail filter (structural brokerage model, not deterioration); grades A on true business quality
    'IBKR',                       # Interactive Brokers — electronic brokerage; 76.8% OM, 93% gross, ROE 23.6%, 16.8% rev growth, net cash position (D/EV -0.922); FCF None only blocker (yfinance doesn't report for brokerages); grades A+, 4/4 MA aligned at add time
    'KRYS',                       # Krystal Biotech — gene therapy dermatology (B-VEC for RDEB); 94.2% gross/46.1% OM/53.9% NM, near-zero debt, 31.9% rev growth, A+; 4/4 MA aligned at add time
    'NBIX',                       # Neurocrine Biosciences — CNS/endocrine specialist (Ingrezza); 22.8% OM, 21.6% NM, ROE 22.5%, FCF 3.8%, 42.2% rev growth, A+; 4/4 MA aligned at add time
    'HOOD',                       # Robinhood Markets — fintech brokerage/crypto; 92.2% gross, 38.5% OM, 41.1% NM, ROE 21.5%, 15.1% rev growth; D/EV improved to 0.166 (was 0.22 blocker); FCF None (brokerage model); grades A, 3/4 MA at promotion
    'PLTR',                       # Palantir — AI/data analytics platform (AIP + Foundry + Gotham); government + commercial flywheel; A+ quality; promoted from watchlist
    'TSM',                        # Taiwan Semiconductor — world's most advanced foundry (TSMC); 3nm/2nm leader; OM 58.1%, NM 46.5%, D/EV 0.069, FCF 31.8%, RevG 35.1%; Apple/NVIDIA/AMD customer lock-in; A+
    'ASML',                       # ASML — EUV lithography monopoly; only company that makes EUV machines (every advanced chip fab needs them); zero debt, OM 36%, NM 29.7%, D/EV 0.0; A+
    'TER',                        # Teradyne — semiconductor test + collaborative robotics (Universal Robots); OM 37.6%, NM 22.6%, D/EV 0.001, RevG 87%, FCF 0.5%; picks-and-shovels for AI silicon + factory automation; A+
    'LITE',                       # Lumentum — photonics/optical components (datacenter transceivers + 3D sensing + telecom); OM 21.8%, NM 17.7%, D/EV 0.056, RevG 90.1%; AI datacenter interconnect tailwind; A+
    'BWXT',                    # BWX Technologies — sole-source Navy nuclear propulsion (submarines/carriers) + nuclear components + medical isotopes; ROE 29%, OM 10%, D/EV 0.099, government contract moat; grade B, watch for OM expanding above 15%; auto-promoted 2026-06-30 [grade B, 1/4 MA]
    'CIEN',                    # Ciena — optical networking, AI datacenter interconnect tailwind; net margin 4.5% and ROE/P/E blocking, 33% rev growth; auto-promoted 2026-06-30 [grade B, 3/4 MA]
    'CEG',                       # Constellation Energy — largest US nuclear operator; 21.9% OM, 12.7% NM, ROE 16.1%, RevG 63.8%; AI/datacenter PPAs (Microsoft Crane restart); D/EV 0.201 (just over 0.20 threshold) + FCF -5.3% (capex from new nuclear capacity build-out); grade B; added 2026-07-01
    'BLK',                       # BlackRock — world's largest asset manager ($10T+ AUM); iShares ETF franchise (largest globally) + Aladdin risk platform (SaaS-like, used by central banks/SWFs); every index fund = AUM fee; OM 35.6%, NM 24.4%, FCF 4.4%, D/EV 0.095, RevG 27%, fwd P/E 16.1x; A+
    'BX',                        # Blackstone — world's largest alternatives manager ($1T+ AUM); PE + real estate + credit + infrastructure; mgmt fees sticky, carried interest is performance upside; retail alternatives push = decade-long runway; OM 38.0%, NM 21.2%, ROE 29.5%, D/EV 0.130, fwd P/E 15.8x; A
    'ADBE',                    # Adobe — creative cloud monopoly (Photoshop/Illustrator/Acrobat); OM 35.3%, NM 28.7%, GrossM 89.4%, ROE 63%, FCF $9.2B, fwd P/E 8x; D/E 0.61 only blocker (corporate bonds ~$4B, FCF paydown path clear); Figma deal dead Dec 2023 (CMA blocked, $1B termination fee paid); chart 0/4 MA broken on AI disruption fear; Firefly/GenStudio is the AI answer — watch for MA recovery; auto-promoted 2026-07-06 [grade A+, 0/4 MA]
    'INTU',                    # Intuit — TurboTax + QuickBooks + Credit Karma franchise; near-monopoly on SMB accounting + tax prep; OM 47%, NM 21.9%, GrossM 80.8%, ROE 22.5%, FCF $5.2B, fwd P/E 10x; D/E 0.33 only blocker (Credit Karma acq debt, FCF paydown path clear); 0/4 MA, slope -59 — chart badly broken; watch for weekly MA structure recovery; auto-promoted 2026-07-06 [grade A+, 0/4 MA]
    'FCX',                     # Freeport-McMoRan — largest US copper producer (Grasberg mine, Indonesia); AMZN-Rio Tinto 2yr datacenter copper deal confirms AI infrastructure demand thesis; OM 31.1%, ROE 15.6%, FCF $1.7B, fwd P/E 15.4x, D/EV 0.33; NM 10.3% only soft blocker; weekly gate ✓ (MA10w $63.29 > MA20w $62.52, slope +2); price $60.97 below MA10w — entry on MA10w reclaim; auto-promoted 2026-07-06 [grade B, 2/4 MA]
    'ARM',                     # auto-promoted 2026-07-07 [grade A+, 3/4 MA]
    'DUOL',                    # Duolingo — gamified language learning platform, strong engagement moat today; AI is both opportunity (AI tutors, conversation practice) and long-term structural threat (LLMs good enough at real-time translation/conversation coaching reduce core value prop); not imminent but moat question growing; gate: AI integration demonstrably deepens retention and expands addressable market rather than being competed around; auto-promoted 2026-07-13 [grade A+, 2/4 MA]
    'DXCM',                    # Dexcom — CGM platform leader (G7 sensor + pump integrations); A+ metrics but ceiling forming (Abbott Libre gaining share, non-invasive CGM in development, GLP-1 compressing urgency); moved from universe — extended at Fully Stacked, not a clear compounder; gate: market share stabilisation vs Abbott + GLP-1 thesis resolves into expanding TAM (Type 2 non-insulin)
    'MNST',                    # Monster Beverage — energy drink category leader, near-zero debt, 50%+ gross margin, asset-light distribution via Coca-Cola; mature growth, extended at Fully Stacked; moved from universe — wait for 15-20% pullback; gate: price/MA50 pullback + rev growth reaccelerating above 10%
    'FFIV',                    # F5 Networks — legacy ADC/load balancer leader pivoting to multi-cloud app delivery + security; durable installed base, high switching costs; mature growth, extended at Fully Stacked; moved from universe; gate: 15-20% pullback + software/SaaS revenue mix crossing 50%
    'CHRW',                    # C.H. Robinson — largest freight broker in North America; asset-light model, high FCF; cyclical freight market at trough; extended at Fully Stacked; moved from universe; gate: freight cycle upturn visible in volume growth + OM expanding above 4%
    'ALGN',                    # Align Technology — Invisalign category creator; clear aligner technology commoditizing (dental labs making own, generic aligners proliferating); market leader but pricing power eroding as competition closes the gap; metrics still pass filters but ceiling forming — same pattern as DXCM; gate: market share stabilisation + gross margin holding above 70% as commoditisation pressure tests pricing power; auto-promoted 2026-07-13 [grade A, 4/4 MA]
    'ATEN',                    # A10 Networks — application delivery controllers (ADC) + DDoS protection for carriers and enterprises; deeply embedded infrastructure, not flashy; GrossM 79.3%, OM 17.3%, NM 14.9%, ROE 21.4%, FCF margin ~17% ($50M on $299M rev), RevG 13.4%, D/EV 0.091; ROA 5.2% only blocker (cash pile dragging denominator — operating asset returns cleaner than headline); growth angle: AI/5G traffic surge → carrier ADC capacity upgrades + DDoS threat surface expanding; not a dividend play (0.66% yield); gate: ROA crossing 10%+ as revenue scale compounds on the asset base; auto-promoted 2026-07-13 [grade A, 4/4 MA]
    'SEZL',                    # Sezzle — fee-based BNPL pivot, 61% op margin, 92% ROE, 74% gross margin, zero debt, A+; moved from universe — extended/maxed out at Fully Stacked, risk elevated; gate: 20-25% pullback to re-enter; auto-promoted 2026-07-15 [grade A+, 4/4 MA]
    'VRTX',                    # Vertex Pharmaceuticals — CF franchise monopoly (Trikafta/Casgevy), expanding into pain (suzetrigine) + kidney disease; similar technical setup to ABBV; moved from universe — extended, wait for 20-25% pullback; auto-promoted 2026-07-15 [grade A+, 4/4 MA]
    'VCTR',                    # Victory Capital — multi-boutique active asset manager; A+ metrics (NM 25.8%, ROE 21.7%, GrossM 56.3%, zero debt); 76.7% RevG is Amundi US acquisition math not organic; active management = performance-dependent AUM, not a toll booth like MSCI/SPGI; gate: organic AUM growth positive + 2+ quarters post-acquisition showing revenue durability without acquisition tailwind; auto-promoted 2026-07-15 [grade A+, 4/4 MA]
]

# Future contenders — moat proven, one or two filters blocking, no survival risk
# Rule: if the blocker is a number, it belongs here. If the blocker is the business model, it doesn't.
WATCHLIST = [
    'AXON','MELI','SNOW','BILL',   # ALAB promoted to universe; CRWD removed — already in universe; PLTR promoted to universe
    'MDB','NET','HUBS','TEAM','MKC','DPZ',
    'CPAY',  # Corpay (formerly FleetCor) — V/MA-like toll economics on corporate payments: fleet cards, B2B payments, lodging, Brazil tolls; GrossM 79.7%, OpM 41.4%, FCF 9.1%, RevG 25.4%, P/E 21.2x — A+ quality on every metric except debt; D/EV 0.334 only blocker — serial acquirer model means debt is structural (buy payment vertical → extract margin → repeat), FCF strong enough to delever fast if acquisitions pause; gate: D/EV ≤ 0.20 sustained 2+ quarters without a new acquisition resetting it
    'DRI',   # Darden Restaurants — Olive Garden + LongHorn + Fine Dining (Capital Grille/Eddie V's); casual dining scale moat + loyalty data + franchise-like unit economics; ROE 53.7%, FCF 4.6%, OM 14.3%, RevG 13.7%, P/E 19.3x — strong across the board; D/EV 0.259 only blocker (restaurant operating leverage + lease obligations, not acquisition debt); grade B; gate: D/EV ≤ 0.20 as FCF compounds down the debt
    'FROG',  # JFrog — universal artifact repository (Artifactory) + software supply chain security (Xray); every build artifact, package, dependency stored and scanned here; deeply embedded in CI/CD pipelines = extreme switching costs once deployed enterprise-wide; GrossM 77.5%, FCF $170M positive (real cash despite negative GAAP OM), RevG 25.8%, near zero debt ($16M total); OM -7.4% only blocker (stock-comp heavy — FCF is the honest signal); software supply chain security tailwind (Log4j/SolarWinds made artifact scanning mandatory); gate: OM crossing 0% as scale drives leverage on R&D/S&M
    'GTLB',  # GitLab — complete DevSecOps platform (source control + CI/CD + security scanning + project mgmt) in a single application; enterprise moat = single-platform control vs GitHub's patchwork integrations, strong self-hosted/air-gap compliance appeal; GrossM 86.8% (higher than FROG), FCF $313M positive, RevG 23.1%, zero debt; OM -6.0% only blocker — closer to crossing 0% than FROG; fwd PE 31x (vs FROG 82x) = more conservatively priced; 39% off 52w highs; same story as FROG — 2-3 quarters tells it; gate: OM crossing 0% sustained
    'GEV',                       # GE Vernova — picks-and-shovels for entire energy transition; supplies wind turbines, gas turbines, grid (transformers/switchgear/HVDC) — every renewable project + datacenter power need touches GEV; OM 5.5% only blocker (offshore wind losses dragging profitable gas+grid mix; inflects as wind rolls off); D/EV 0.012, ROE 75.7%, FCF +3.0%, fwd P/E 46.8x; grade A+; at 52w highs +113% from low, 42% above 40w MA — wait for 20-25% correction (~$870-920)
    'COPX',  # Global X Copper Miners ETF — AUM $8.0B; copper = AI datacenter + grid + EV structural demand; 21% off 6mo highs ($95), 9.4% above 6mo lows ($69); below MA10 ($81) + MA20 ($83) + MA50 ($83), all slopes negative; chart-only (ETF); entry: daily MA10 reclaim ~$81
    'GLD',   # SPDR Gold ETF — AUM $150B, gold price proxy; 25% off 6mo highs ($496), 1.3% above 6mo lows ($366); below MA10 ($378) + MA50 ($409); chart-only tracking (ETF); entry: MA10 reclaim or hold at 6mo low support
    'SLV',   # iShares Silver ETF — AUM $37B, silver price proxy; 49% off 6mo highs ($106), 3.5% above 6mo lows ($52); below MA10 ($56) + MA50 ($66); deeper correction than gold — higher beta, higher upside on reversal; chart-only tracking (ETF)
    'NLR',   # VanEck Uranium & Nuclear ETF — AUM $4.87B; AI datacenter baseload + uranium supply constraints thesis intact; 24.9% off 52w highs, 8.7% above 52w lows ($105), below all MAs (daily MA10 $121, MA50 $132); 5 consecutive monthly declines — near support, not yet recovering; entry: wait for daily MA10 reclaim (~$121) or bounce off $105-106 support with volume
    'PEG',   # PSEG — integrated NJ utility + nuclear operator (Salem 1&2 + Hope Creek); same AI/datacenter nuclear PPA thesis as CEG but integrated utility (regulated T&D + nuclear generation) vs CEG pure-play; OM 28.4%, NM 17.7%, ROE 13.4% (PUC-capped), RevG 19.4%, P/E 17.8x; D/EV 0.38 (rate-base utility debt, FERC/PUC approved) + FCF -0.4% (barely negative — nuclear refueling cycles + grid modernization capex) both blocking; grade A; gates: D/EV delevering + FCF inflection as nuclear PPAs convert to contracted cash flows
    'NEE',   # NextEra — world's largest renewable platform (wind/solar/battery) + FPL (best-run regulated utility in US); OM 30.2%, NM 29.4%, ROE 10.3%; D/EV 0.352 (Dominion acq debt, can resolve) + FCF -10.2% (renewable capex → contracted cash flows once online, not perpetual like DUK); grade A, 2 blockers both have resolution paths; at 40w MA support, 10% off highs 2026-07-01
    'VICI',  # VICI Properties — largest gaming/experiential REIT; triple-net leases with Caesars (45%), MGM, Venetian, Hard Rock at 15-20yr terms with CPI escalators; GrossM 99.1%, NM 76.8%, FCF $1.28B, ~5.5% yield, payout 61% AFFO (conservative for REIT); ROE 11.3% (gate ≥15%) + D/EV 0.62 (gate ≤0.50) both block — both REIT-structure artifacts: real estate at historical cost compresses ROE, leverage secured by experiential assets generating rent is not deteriorating debt; zero tenant defaults since 2017 IPO; moat = gaming license tied to location (tenants cannot relocate without VICI consent); grade B+; gate to universe: ROE inflecting toward 15% as FFO scales + D/EV delevering organically
    'WEC',   # WEC Energy Group — regulated Midwest utility (Wisconsin/Illinois/Michigan); OM 29%, NM 16.2%, ROE 11.7%, RevG 9%; D/E 1.53 (IOU rate-based capex, FERC/PUC approved — structural not deteriorating) + FCF -$2B (grid modernization + AI datacenter load buildout in Wisconsin corridor) + ROE PUC-capped at ~11%; B (4/7); 4/4 MA aligned, slope +0.12 — cleaner margins than LNT, AI datacenter demand angle (Microsoft/hyperscaler buildout in Wisconsin)
    'LNT',   # Alliant Energy — regulated Midwest utility (Iowa/Wisconsin); OM 21%, NM 18.6%, ROE 11.3%, RevG 5%; D/E 1.60 + FCF -$1.2B + ROE PUC-capped — same structural blockers as WEC; B (4/7); 4/4 MA aligned, slope +1.53; smaller ($20B) and less differentiated than WEC/NEE — watching for margin improvement
    'AMG',   # Affiliated Managers Group — multi-boutique AM (AQR, Tweedy Browne etc.); owns fee economics in independent boutiques, asset-light; OM 22.1%, NM 35.5%, ROE 21.8%, FCF 2.6%, fwd P/E 8.5x; D/EV 0.245 only blocker (structural debt to buy stakes, paying down with FCF); grade A
    'DVN',   # Devon Energy — formed from CTRA+DVN merger; Permian + Appalachia nat gas/oil; NM 14.2%, ROE 15.2%, FCF 3.2%, P/E 11.8x — solid underlying economics; D/EV 0.257 (merger leverage) + OM 6.9% both blocking; gate: D/EV ≤ 0.20 as merger debt amortizes + OM ≥ 10% on commodity price recovery
    'NRG',   # NRG Energy — de-lever play; LS Power acq doubled fleet+debt, targeting 3x net leverage, Fwd P/E 11x, yield-sensitive re-rate when 10yr < 4.0%
    'TLN',   # Talen Energy — independent power producer; Susquehanna nuclear (2.5GW, Pennsylvania) + natural gas fleet; first direct nuclear-to-datacenter PPA in US (Amazon AWS, long-term contracted at premium rates for 24/7 carbon-free power); FCF 7.9% standout (real cash), fwdPE 12.3x cheap for a contracted nuclear asset; GrossM 40.1%, OM 17.2%, NM -0.6% (barely negative), ROE -1.9%, D/EV 0.303 — all blocking; RevG 97% is post-bankruptcy base comparison, not organic; emerged from Ch.11 May 2023, debt is manageable given FCF; "not sure but getting better" thesis — AWS deal is structural but NM still inflecting and debt elevated; grade B; gate: NM turning consistently positive + D/EV ≤ 0.25 as FCF deleverages + second major datacenter PPA validating Susquehanna as a platform asset
    'VST',   # Vistra — deregulated nuclear+gas (Energy Harbor acq), Texas/ERCOT exposure; OM 26.6%, ROE 42.9%, FCF +0.9%, RevG 43.4%, fwd P/E 14.1x; D/EV 0.265 only blocker (closer to threshold than NEE); grade A single blocker — cleaner than CEG on framework metrics; 27.6% off 52w high, below 20w+40w MAs; promote when D/EV ≤ 0.20 + MA structure recovers
    'LNG',   # Cheniere Energy — largest US LNG export terminal operator (Sabine Pass + Corpus Christi); long-term take-or-pay SPAs (20yr contracts) = utility-like contracted cash flows; Europe permanent de-Russian gas = structural LNG demand floor; FCF $1.7B + ROE 28.9% show real economics; D/E 3.2 structural terminal infrastructure debt (same read as telecom capex, not deteriorating); GAAP OM distorted by commodity MTM hedging accounting — FCF is the signal, not OM; B (3/7); MA 3/4, slope negative — below MA20w $249, entry on weekly alignment recovery
    'KTOS',  # Kratos — drone/defense tech; margins thin now, scaling with DoD contracts
    'EXPE',  # Expedia Group — online travel marketplace (Expedia.com, Hotels.com, Vrbo, Orbitz); toll booth on travel bookings, asset-light; GrossM 90.3%, NM 9.8%, FCF 22.9% (standout — structural marketplace cash, not cyclical), D/EV 14.4%, ROE 71.5% (buyback-distorted, ROIC cleaner), RevG 14.7%, P/E 11.7x; OM 7.1% only blocker (just under 8% — one operating leverage step away); VRBO differentiated (family/group vacation rental, different from Airbnb urban focus); market pricing this as cyclical consumer at 11.7x vs actual toll-booth economics; gate: OM ≥ 8% sustained + RevG holding above 10% as travel recovery normalizes
    'FLUT',  # Flutter Entertainment — global online sports betting; FanDuel #1 US (~45% share) + Paddy Power/Betfair (UK/Ireland) + Sportsbet (Australia) + Sisal (Italy) + PokerStars; Betfair exchange model (P2P betting, FLUT takes commission) = structurally lower cost than traditional sportsbook; OM ~12%, NM ~9%, FCF ~4%, RevG ~22%, ROE ~12%; D/EV ~0.30 (serial acquisition debt — Sisal 2022 + PokerStars integration) only blocker; two-speed business: mature international at high margins subsidizing FanDuel US scale-up; gate: D/EV ≤ 0.20 as FCF deleverages
    'SOFI',  # SoFi — neobank scaling; ROE 6.6% and trending right
    'UPWK',  # Upwork — freelance marketplace; D/EV 0.44 (converts) only blocker, margins/FCF solid
    'CLS',   # Celestica — AI infra contract manufacturer (servers, networking), ROE 52%, D/EV 0.02, gross margin 12% blocks universe
    'PRGS',  # Progress Software — serial acquirer of mature enterprise software: OpenEdge (30-40yr installed base low-code apps, near-impossible to rip out), Telerik/Kendo UI (developer UI components), MOVEit (managed file transfer); GrossM 85.6%, FCF 18.6% (exceptional), fwdPE 6.5x = priced like broken, runs like cash cow; OM 18.5% + ROE 18.6% both 1-2% below gate; D/EV 0.461 serial acquisition debt = main blocker; RevG 6.8% — mature, not a growth story; MOVEit 2023 ransomware breach created liability overhang + reputational hit, but customers stayed (switching costs > breach risk); value play: FCF at 6.5x is the signal, not the headline metrics; grade B; gate: D/EV ≤ 0.25 as FCF deleverages + OM crossing 20% as acquired businesses optimize
    'SSNC',  # SS&C Technologies — fund admin infra, $1.28B FCF, extreme switching costs, debt 0.32 only blocker
    'SYM',   # Symbotic — warehouse AI robotics, Walmart-backed; revenue scaling, margins early
    'AMSC',  # American Superconductor — power electronics, grid/defense; OpM 5.1%, one filter away
    'BMY',   # Bristol-Myers Squibb — de-lever + profit growth play; Celgene debt paydown near complete, Eliquis+Opdivo FCF, NI inflecting
    'TGTX',  # TG Therapeutics — Briumvi (ublituximab, anti-CD20 MS); faster infusion than Ocrevus, scaling fast; NM 66%, OM 17%, GrossM 83%, ROE 112%, RevG 69.6%, fwd P/E 18.6x; D/E 1.29 (commercialization converts) + FCF -$30M blocking; watching from distance — wait for real discount before considering
    'VCYT',  # Veracyte — genomic diagnostics; moat = guideline inclusion (NCCN/medical society); Afirma (thyroid indeterminate biopsy, prevents unnecessary surgery) + Decipher Prostate (active surveillance vs treatment, growth engine) + Percepta/Envisia; OM 16.3%, NM 16.2%, GrossM 72.9%, D/E 0.029, FCF $105M, RevG 21.5%; ROE 6.9% only blocker (Decipher acq goodwill, resolves as earnings scale); 4/4 MA aligned, price at MA10d
    'ABT',   # Abbott Laboratories — diversified healthcare: MedTech (FreeStyle Libre CGM, Alinity diagnostics) + Nutrition (Ensure/Similac) + Established Pharma; 52yr dividend aristocrat, 2.8% yield; FreeStyle Libre diabetes CGM growing 20%+ and expanding from monitoring to closed-loop insulin delivery (Omnipod partnership); GrossM 56.5%, OM 13.5%, NM 13.9%, FCF 3.7%, D/EV 0.187, ROE 12.3%; OM/ROE/D/EV all blocking — COVID rapid test revenue cliff normalizing dragging blended margins and growth (RevG 7.8% = Libre growing ~20% masked by COVID base erosion); not structural deterioration; grade B; gate: OM crossing 20% + ROE crossing 20% as Libre scales to majority of device revenue + COVID comp fully absorbed (~2 quarters)
    'MDT',   # Medtronic — largest pure-play medtech (cardiac rhythm mgmt, spine/neuro surgery, diabetes CGM, surgical robotics Hugo); OM 22.0%, NM 13.2%, FCF 4.3%, fwd P/E 13x, RevG 9.9%, ~3.5% dividend; ROE 9.8% (gate ≥10%) + D/EV 0.229 (gate ≤0.20) both blocking — both acquisition artifacts from Covidien ($50B, 2015) and subsequent M&A inflating goodwill and leverage, not structural deterioration; grade B; gate: ROE crossing 10% + D/EV ≤ 0.20 as FCF deleverages acquisition debt
    'BIIB',  # Biogen — neuroscience pure-play; Leqembi (lecanemab, w/ Eisai) first approved Alzheimer's disease-modifier, subcutaneous monthly formulation removes IV burden; zuranolone (depression) via Sage partnership; ROE 7.7% + D/EV 0.21 blocking; MS revenue decline (Tecfidera generics) masking neuro pipeline value
    'COST',  # Costco — membership moat, not a margin story; OM ~3% by design (merchandise passes savings to members, fee stream runs at ~95% margin); screen blocks on OM/NM — low margins are the product, not a flaw; measure by membership fee growth + renewal rate (~93%) + ROIC; currently 0/4 MA (CMF -0.20, distribution); promote to UNIVERSE on 4/4 recovery
    'ORLY',  # O'Reilly Auto Parts — Akre compounder; 18% OM, 14% NM, ROA 13.8% (ROE negative from 20yrs buybacks); ROA just below 15% threshold; D/EV 0.10, P/E 29x, exceptional execution
    'TDG',   # TransDigm — aerospace parts monopolist, 47% OM, 22% NM; D/EV 0.325 structural debt (leveraged rollup model, won't change); watch if debt pays down or FCF re-rates
    'ESE',   # ESCO Technologies — niche industrials: RF/EMC test chambers (ETS-Lindgren), utility grid modernization/power quality, aerospace filtration (VACCO); GrossM 41.9%, OM 15.5%, FCF $320M positive, RevG 33.5%, D/EV 0.024 (near zero debt); ROE 9.2% only blocker — same niche-industrial profile as HEICO but murkier moat (collection of niches vs HEICO's unambiguous FAA-PMA franchise); NM 24.7% > OM 15.5% anomaly — likely one-time tax benefit, watch normalize; fwd PE 36x (cheaper than HEI at 50x); B grade; gate: ROE crossing 12%+ as revenue scale compounds
    'FISV',  # Fiserv — payment processing + Clover POS + banking tech, extreme switching costs; ~33% OM, 15% NM; D/EV ~0.26 from First Data acquisition; ~$3-4B FCF/yr paydown, 1-2yr to threshold
    'APD',   # Air Products — industrial gases, green/blue hydrogen megaproject bet ($15B+, NEOM/Louisiana); D/EV 0.224 + FCF -5.6% from capex cycle both blocking; new CEO reviewing strategy; watch for FCF inflection as projects come online
    'PYPL',  # PayPal — OM 18%, NM 15%, ROE 25%, FCF 11%, P/E 7.8x; D/EV 0.30 only blocker (customer float structural); Chriss margin recovery showing in numbers
    'IOT',   # Samsara — fleet/IoT SaaS, GM 76%, zero debt, 30% RevG, FCF just turned positive; OM 1.5% blocking, 2yr runway to A/A+ as scale drives margin
    'ABBV',  # AbbVie — Allergan amortization masking strong cash earnings; FCF/Debt 28.5%, IC improving 6.3→7.8×, Skyrizi/Rinvoq replacing Humira
    'GFS',   # GlobalFoundries — specialty foundry (RF, automotive, IoT); 5/6 filters pass, ROE 6.8% only blocker (capital-heavy fab structure)
    'PWR',   # Quanta Services — dominant grid/electrical infrastructure contractor; OM 4% blocks now, watch for 7-8% as AI datacenter + grid modernization drives project mix higher
    'SITM',  # SiTime — MEMS precision timing chips; near-monopoly, 65% gross margin, AI datacenter + 5G tailwind; cyclical recovery in progress
    'LSCC',  # Lattice Semiconductor — low-power FPGAs, 60%+ gross margin, zero debt; AI edge + industrial; cyclical trough recovery
    'ONTO',  # Onto Innovation — advanced packaging inspection/metrology; HBM + chiplet complexity = more inspection; picks-and-shovels for AI silicon
    'AMD',   # AMD — AI accelerator (MI300X/MI350) + x86 CPU challenger; OM ~21%, NM scaling; D/EV low; FCF building as datacenter GPU mix grows; watch for ROE/NM qualification
    'INTC',  # Intel — x86 architect in foundry transition (Intel 18A); OM/NM/ROE all blocking post-Gelsinger restructuring; Lip-Bu Tan CEO, cost reset underway; multi-year turnaround
    'TOST',  # Toast — restaurant POS/payments platform; ROE 22.5%, FCF 4%, rev growth 21.9%, near-zero debt; OM 6.7% + NM 6.4% blocking; grades A, 0/4 MA; strong switching costs, margins scaling
    'FIG',   # Figma — design collaboration SaaS; 79.8% gross margin, FCF 8.6%, 46.1% rev growth; OM -41.2% post-IPO investment spend blocking; grades B (OM negative caps grade); Adobe tried $20B acquisition, IPO'd at $9.5B — quality business finding its level
    'COIN',  # Coinbase — digital asset exchange, crypto theme proxy; 85.5% gross margin, FCF 5.4%; OM -7.1% + rev growth -30.8% (crypto volume cycle) blocking; grades B, 0/4 MA; cyclical — watch for volume recovery + OM turning positive
    # --- Photonics / Optical Interconnect ---
    'FTAI',  # FTAI Aviation — CFM56 engine platform (powers 737/A320, largest narrowbody fleet in the world); buys used engines, refurbishes modules, leases/sells back to airlines at discount to OEM — toll booth on aviation, not the airline itself; OM 22.5%, NM 18.9%, ROA 11.3%, RevG 65.5%, fwd PE 18.5x; FCF -$320M ✗ (main blocker — growth capex consuming cash or structural, unclear); D/EV 0.132 manageable (D/E 809 is buyback-distorted equity, not leverage deterioration); infrastructure segment separation adds complexity; Hindenburg short report (2024) raised accounting concerns — not fully resolved; down -34% from highs; gate: FCF turning positive + infrastructure separation complete + short report overhang cleared; Buffett/Munger would disapprove (aviation industry) — but this is the toll booth, not the airline
    'COHR',  # Coherent Corp — optical components (800G/1.6T datacenter interconnect + telecom); OM 13.6%, NM 7.1%, D/EV 0.045; ROE 4.7% + FCF -0.3% blocking; post II-VI merger integration phase; watch FCF inflection
    # --- Defense / Drones ---
    'AVAV',  # AeroVironment — defense drones (Switchblade loitering munition, Puma ISR); RevG 143.4%, D/EV 0.108; OM -5.1% scaling with DoD contracts; proven battlefield platform
    # --- Critical Materials ---
    'ALB',   # Albemarle — largest lithium producer (Chile/Australia mines); OM 24.8%, FCF 4.1%, D/EV 0.095; NM -4.2% from lithium price cycle (not structural); long-term EV battery supply chain position
    # --- Solar ---
    'ENPH',  # Enphase Energy — microinverter monopoly + battery storage (IQ8/Encharge); cycle trough from high-rate residential solar slowdown, not structural; gross margins ~45%+ holding even in trough; OM -9.1% + RevG -20.6% blocking now; 3/4 MA recovering, -61.6% from highs; when rates normalize + installs recover = A+ candidate; engine intact
    'S',     # SentinelOne — AI-native cybersecurity platform, direct CrowdStrike competitor; GrossM 73.2%, RevG 20.8%, FCF 5.0% (positive, unusual for loss-making SaaS); OM -28.8% + NM -30.4% hard blockers; ROE -21.4%; watch OM crossing 0% and trending toward 10%+ over 2-3 quarters as scale drives margin inflection

]

# Future radar — too early for weekly scanning, revisit after 2-3 quarters
# Not fetched, not graded. Documented here so the thesis isn't lost.
# Gate to promote: gross margin consistently positive + OM inflecting toward 0%
FUTURE_RADAR = {
    'ENVX': 'Enovix — silicon-dominant batteries (100% silicon anode); Fab2 Malaysia in ramp; consumer electronics + defense; most commercially advanced silicon anode play (vs AMPX/EOSE); all quality filters blocking now — gate to watchlist: Fab2 ramp execution + gross margin turning consistently positive + OM inflecting toward 0%; revisit Q3/Q4 2026',
    'RKLB': 'Rocket Lab — only end-to-end small launch + space systems provider; real revenue, real launches; path to profit is long and capex-heavy; gate to watchlist: OM turning positive + FCF inflection; revisit when launch cadence drives margin scale',
    'AVAV': 'AeroVironment — battlefield-proven defense drones (Switchblade loitering munition, Puma ISR); DoD contracts real; OM -5.1% scaling but not yet positive; gate to watchlist: OM crossing 0% sustained + FCF turning positive',
    'AAOI': 'Applied Optoelectronics — datacenter optical transceivers (800G/1.6T AI fabric); real revenue, real AI datacenter demand; OM -8.6% not yet turning; gate to watchlist: OM inflecting positive as AI interconnect volumes scale',
    'MP':   'MP Materials — only US rare earth miner + processor (Mountain Pass CA); DoD contract + Tesla partnership; national security supply chain angle; OM -7.9% from processing build-out; gate to watchlist: processing ramp drives OM positive + FCF inflection',
    'CORZ': 'Core Scientific — BTC miner pivoting to high-density AI/HPC datacenter infrastructure; CoreWeave + other AI contracts signed; pivot execution unproven, BTC mining revenue is commodity-priced and non-compounding; gate to watchlist: HPC/AI revenue majority of revenue mix + OM turning consistently positive',
    'MOD':  'Modine Manufacturing — AI datacenter thermal/cooling (heat exchangers); B grade, multiple metrics blocking (NM 3.8%, FCF negative, ROE/ROA below threshold); industrial company riding AI cooling theme, not a platform moat; gate to watchlist: NM crossing 5% + FCF turning positive as datacenter cooling project mix scales',
    'UPST': 'Upstart — AI-powered lending platform; 82.7% gross margin, OM just turning (0.9%); credit cycle exposure structural to lending model; D/EV 0.431 (converts) + FCF -10.1% + ROA 1.8% blocking; gate to watchlist: FCF consistently positive + converts resolved + through-cycle credit performance demonstrated',
    'RIVN': 'Rivian Automotive — EV maker (R1T/R1S + commercial vans for Amazon); gross margin just turned positive (1%) — unit economics no longer underwater, direction is right; VW partnership ($5.8B) extends runway; R2 (mass-market ~$45k) is the volume inflection catalyst; OM -63.8%, FCF -$1.3B, D/E 1.18 — fixed cost absorption gap will close only with volume scale; gate to watchlist: gross margin consistently above 10% + FCF trajectory turning less negative quarter over quarter; 3-4 quarters minimum',
    'ACAD': 'Acadia Pharmaceuticals — CNS/rare disease; Nuplazid (only FDA-approved Parkinson\'s psychosis drug) + DAYBUE (Rett syndrome); NM 34.3%, ROE 37.3%, FCF $154M, D/E 0.041; OM -1.7% only blocker but 2026 earnings outlook bleak; bulak bulak phase — secular move not started yet; gate to watchlist: OM crossing 10% sustained + revenue growth reaccelerating as DAYBUE penetration scales',
    'CBRS': 'Cerebras Systems — Wafer-Scale Engine (WSE-3): entire silicon wafer as single chip, 900K AI cores, 44GB on-chip SRAM; eliminates inter-chip communication latency that limits NVDA GPU clusters; inference specialist — NVDA trains, Cerebras runs models fast; RevG +94%, GrossM 40%, OM -7.8% (close to breakeven); revenue heavily concentrated (G42/UAE deal dominant — geopolitical scrutiny risk); FCF not yet positive; fwd PE 184x priced for perfection; gate to watchlist: OM turning positive + revenue diversification beyond concentrated customers + FCF inflection; few more quarters tells the real story — revisit Q2/Q3 2026 results',
    'QXO':  'QXO — Brad Jacobs (built XPO Logistics $0→$16B, United Rentals same playbook) applying tech-enabled distribution ops to building products; acquired Beacon Roofing Supply ($11B) — largest roofing distributor in North America; thesis: fragmented building products distribution + Jacobs\' operational playbook = margin expansion over time; currently in integration phase — OM -11.8%, FCF -$1.23B, all filters blocking; RevG 12,716% is Beacon consolidation not organic; D/EV ~0.30 acquisition debt; fwd PE 19x = market pricing eventual normalization; price near 52w low ($14 vs $27.61 high) — market skeptical of integration pace; gate: OM turning positive + FCF inflection + D/E delevering as integration costs roll off; revisit 3-4 quarters',
    'PRAX': 'Praxis Precision Medicine — neurological disease pure-play; ulixacaltamide (PRAX-944) targeting essential tremor (7M+ US patients, current beta-blocker/primidone standard-of-care has poor tolerability = large unmet need); PRAX-628/PRAX-562 Nav1.6 epilepsy inhibitors in pipeline; Phase 3 T-CALM data drove $37→$366 in one year — the clinical home run has likely printed, now a binary FDA approval bet; pre-revenue ($9B market cap on zero revenue), FCF -$176M burn, near-zero debt; all quality filters block — not a framework name; gate: FDA approval + early commercial revenue traction; if approval comes, re-evaluate as a commercial-stage specialty pharma',
    'DKNG': 'DraftKings — US online sports betting #2 (behind FanDuel/FLUT); strong brand + same-game parlay product; RevG 30%+, FCF turning positive, adj EBITDA now positive; structural margin ceiling from US state tax rates (NY 51%, PA 36% of gross gaming revenue before DKNG revenue) + perpetual promo costs to compete — these are real cash costs, not stock comp distortions; GAAP NM path to 8%+ uncertain vs FLUT which has mature international margins subsidizing the US ramp; gate to watchlist: NM consistently ≥ 8% through multiple quarters showing the state tax + promo overhang is manageable at scale; revisit when FY margin comps clarify the ceiling',
    'QDEL': 'QuidelOrtho — diagnostics platform formed from Quidel (Sofia/QuickVue rapid POC tests) + Ortho Clinical (hospital immunoassay/clinical chemistry); scale across both POC and centralized lab = durable infrastructure; GrossM 45%, FCF $208M positive — real cash generation; OM -4.1% and NM/ROE deeply negative are Ortho acquisition goodwill impairment distortions, not operational failure; RevG -10.5% from COVID rapid test cliff normalizing; D/E 1.55 structural merger debt; fwd PE 6.9x — priced like it is broken when FCF says it is not; gate to watchlist: OM crossing 0% sustained + revenue growth flat or positive (COVID cliff absorbed) + impairment charges rolling off NM; 1-2 quarters',
    'PGY':  'Pagaya Technologies — AI-powered credit underwriting network; lenders send declined applications to Pagaya AI, approved loans sold to institutional investors (Pagaya earns fee, no credit risk on balance sheet); OM 25.2% + FCF 12.8% show real operating economics; fwdPE 4.95x = market pricing significant risk; D/EV 0.762 hard blocker (dangerous for $1.5B small-cap); moat question valid — same model as Upstart (UPST in watchlist), big banks building similar AI, Zest AI competing directly; credit cycle exposure structural (institutional appetite for alt-credit dries up in downturns); gate to watchlist: D/EV delevering below 0.30 + NM crossing 10% + RevG above 15% sustained (network scaling, not just credit cycle)',
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
    # --- BDC / Income ---
    'MAIN': 'Main Street Capital — BDC lending to lower middle market companies; internally managed (removes fee conflict that plagues most BDCs); ~8.4% yield paid monthly + semi-annual special dividends; trades at ~1.55x NAV (premium unusual for BDCs, reflects management quality); ROE 14.4%; not a growth compounder — a durable income machine; SIP monthly for yield compounding',
    # --- Packaging / Industrial Dividend ---
    'SW':   'Smurfit Westrock — world\'s largest paper-based packaging company (WestRock + Smurfit Kappa merger 2024); corrugated boxes are durable secular demand — every e-commerce shipment (Amazon, Shopify, retail) needs packaging; ~4% dividend yield, FCF $1.36B positive = dividend is FCF-supported not earnings-dependent (NM 1.2% is thin but payout off earnings is misleading); D/E 78.8 is merger debt overhang — same structural pattern as post-acq industrials, manageable given FCF; OM 6.8%, fwd PE 12.9x; ROE 2.1% and NM block quality screener — tracked here as a dividend/income name, not a compounder; SIP on dips for yield accumulation',
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

def get_fundamentals(ticker):
    try:
        t    = yf.Ticker(ticker)
        info = t.info
        if not info or 'marketCap' not in info:
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
        market_cap        = info.get('marketCap', 1) or 1
        fcf_yield         = (fcf / market_cap * 100) if fcf is not None and market_cap else None

        # Price vs MA200d — margin of safety signal
        ma200d            = info.get('twoHundredDayAverage', None)
        _price_raw        = info.get('currentPrice') or info.get('regularMarketPrice')
        price_vs_ma200    = round((_price_raw / ma200d - 1) * 100, 1) if ma200d and _price_raw else None

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
        )
    except Exception as e:
        print(f"  ⚠ {ticker}: {e}")
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

def entry_zone(d):
    """Composite margin-of-safety signal: GREEN / YELLOW / RED."""
    pma200 = d.get('price_vs_ma200')
    fy0    = d.get('fy0_growth')
    grade  = d.get('grade', 'B')
    fpe    = d.get('fwd_pe') or d.get('pe')

    # Base score from technical position vs MA200d
    if pma200 is None:
        base = 1
    elif pma200 <= 5:
        base = 2   # at/below MA200 — base zone
    elif pma200 <= 20:
        base = 1   # moderate extension
    else:
        base = 0   # stretched (>20% above MA200d)

    eps_mod   = (+1 if fy0 is not None and fy0 > 15
                 else -1 if fy0 is not None and fy0 < 0
                 else 0)
    grade_mod = +1 if grade == 'A+' else (0 if grade == 'A' else -1)
    # High PE without matching growth caps at yellow
    pe_pen    = -1 if (fpe and fpe > 50 and (fy0 is None or fy0 < 20)) else 0

    total = base + eps_mod + grade_mod + pe_pen
    if total >= 3: return 'green'
    if total >= 1: return 'yellow'
    return 'red'


def entry_html(d):
    zone = entry_zone(d)
    color = '#3fb950' if zone == 'green' else ('#e3b341' if zone == 'yellow' else '#f85149')
    label = 'ZONE' if zone == 'green' else ('FAIR' if zone == 'yellow' else 'RICH')
    pma   = d.get('price_vs_ma200')
    tip   = f'{pma:+.0f}% vs MA200' if pma is not None else ''
    return (f'<span style="color:{color};font-weight:700;font-size:11px">● {label}</span>'
            f'<span style="color:#484f58;font-size:10px"> {tip}</span>')


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

def signal_html(sig):
    if sig is None: return '<span style="color:#484f58">—</span>'
    direction, source = sig
    color = '#3fb950' if direction == 'bull' else '#f85149'
    arrow = '⬆' if direction == 'bull' else '⬇'
    return f'<span style="color:{color};font-weight:700">{arrow} {direction}</span><span style="color:#484f58;font-size:9px"> {source}</span>'

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
    now  = datetime.now().strftime('%B %d, %Y  %H:%M')
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
          <td>{signal_html(d.get('signal'))}</td>
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
      <th>ROE%</th><th>FCF Yld</th><th>Rev Grw</th><th>P/E</th><th>EPS FY</th><th>Entry</th><th>Signal (wk)</th>
    </tr>
  </thead>
  <tbody>{rows}</tbody>
</table>
{build_universe_failing_section(universe_failing)}
{build_watchlist_section(watchlist)}
<div class="disclaimer">
  Data sourced from Yahoo Finance via yfinance. Prices and fundamentals may be delayed or incomplete.<br>
  For informational purposes only — not financial advice. Always do your own research before making investment decisions.
</div>
</body>
</html>"""

if __name__ == '__main__':
    import sys

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

    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    print(f"\n  Quality Screener — {now}", flush=True)
    print(f"  Screening {len(UNIVERSE)} companies ...", flush=True)

    with ThreadPoolExecutor(max_workers=10) as ex:
        raw = list(ex.map(get_fundamentals, UNIVERSE))

    passed  = [d for d in raw if d is not None and passes_quality_filter(d)]
    failing = [d for d in raw if d is not None and not passes_quality_filter(d)]
    for d in passed:
        d['grade'] = quality_grade(d)
    passed.sort(key=lambda x: (
        0 if x['grade']=='A+' else 1 if x['grade']=='A' else 2,
        1 if (x.get('fy0_growth') is not None and x['fy0_growth'] < 0) else 0,
        -(x['market_cap_b'] or 0)
    ))

    print(f"  ✅  {len(passed)} companies passed filters  ({len(failing)} in universe not yet qualifying)")

    sig_tickers = [d['ticker'] for d in passed if d['grade'] in ('A+', 'A')]
    print(f"  Computing weekly signals for {len(sig_tickers)} A/A+ names ...", flush=True)
    with ThreadPoolExecutor(max_workers=8) as ex:
        sig_vals = list(ex.map(get_tech_signal, sig_tickers))
    sig_map = dict(zip(sig_tickers, sig_vals))
    for d in passed:
        d['signal'] = sig_map.get(d['ticker'])

    print(f"\n  Fetching {len(WATCHLIST)} watchlist contenders ...", flush=True)

    with ThreadPoolExecutor(max_workers=10) as ex:
        watch_raw = list(ex.map(get_fundamentals, WATCHLIST))
    watch_raw = [d for d in watch_raw if d is not None]
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
        subprocess.run(['git', 'add',    'quality_screener.html'], cwd=repo, check=True, capture_output=True)
        subprocess.run(['git', 'commit', '-m', commit_msg],        cwd=repo, check=True, capture_output=True)
        subprocess.run(['git', 'push'],                             cwd=repo, check=True, capture_output=True)
        print(f"  Pushed → GitHub  ({commit_msg})")
    except subprocess.CalledProcessError as e:
        print(f"  Git push skipped: {e.stderr.decode() if e.stderr else e}")
