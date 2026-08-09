"""
internal_dividend.py — Dividend & Value Screener  (GITIGNORED)
Screens quality dividend payers for yield sustainability, margin quality,
low debt, and 4/4 MA alignment. Separate from growth screener.
Run: python internal_dividend.py
"""

import yfinance as yf
import math
import time
import json
import os
import warnings
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

warnings.filterwarnings('ignore')

_CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'dividend_data_cache.json')

def _load_cache():
    try:
        with open(_CACHE_FILE) as f:
            return json.load(f)
    except Exception:
        return {}

def _save_cache(cache):
    try:
        with open(_CACHE_FILE, 'w') as f:
            json.dump(cache, f, indent=2)
    except Exception:
        pass


def _fetch(ticker, fn, retries=3):
    for attempt in range(retries):
        try:
            result = fn(ticker)
            if result is not None:
                return result
        except Exception:
            pass
        if attempt < retries - 1:
            time.sleep(1.5 * (attempt + 1))
    return None

# ─── Universe ────────────────────────────────────────────────────────────────

UNIVERSE = [
    # Asset managers — fee income, capital-light, buyback compounders
    'TROW',  # T. Rowe Price — 37yr div growth, 37% OM, FCF 8%, P/E 12
    'AMP',   # Ameriprise — TROW twin; 37% OM, FCF 8%, P/E 12, aggressive buybacks

    'AB',    # AllianceBernstein Holding L.P. — asset manager structured as a limited partnership; Equitable Holdings (EQH) owns ~65%, unitholders get the rest; LP pass-through = distributes ~100% of earnings each quarter (variable, not fixed); ~9% distribution yield at current price; AUM ~$700B+ across equity, fixed income, alternatives, multi-asset; fwdPE 9.5x cheap; yfinance metrics mostly blank for LP structure — judge by distribution per unit history + AUM trend + EQH parent health; distribution variability is the structural caveat (falls in bad market years); income vehicle, not a compounder — size accordingly

    # Insurance — float-based compounders
    'AFL',   # Aflac — 42yr div growth, supplemental insurance moat, Japan exposure
    'CINF',  # Cincinnati Financial — 63yr dividend king, FCF 10.5%, pure compounder
    'TRV',   # Travelers — FCF 20%+, P/E 9, best underwriter in P&C
    'CB',    # Chubb — global P&C leader, 20% OM, fortress balance sheet
    'AJG',   # Arthur J. Gallagher — insurance broker, fee model, 30yr growth
    'AON',   # Aon — insurance/reinsurance broker, pricing power
    'PRU',   # Prudential Financial — US life insurance + retirement solutions + PGIM asset management ($1.3T+ AUM); PGIM fee income is the floor — stable capital-light earnings regardless of insurance cycle volatility; 4-5% yield, consistent multi-year dividend growth; D/EV reads elevated due to insurance policyholder liabilities (structural, not deteriorating debt — same sector-aware read as VZ on telecom spectrum); moat = scale in group insurance + PGIM distribution; watch payout ratio and FCF coverage each quarter as the qualifying gate

    # Healthcare / pharma
    'ABT',   # Abbott Laboratories — 52yr dividend aristocrat; FreeStyle Libre CGM + Alinity diagnostics + Ensure/Similac nutrition; 2.8% yield, FCF 3.7% covers dividend; Libre growing 20%+ masking COVID test revenue cliff in blended numbers; quality franchise, dividend compounding for decades; SIP on pullbacks
    'JNJ',   # J&J — 62yr dividend king, MedTech + pharma
    'ABBV',  # AbbVie — Skyrizi/Rinvoq replacing Humira; 3.5%+ yield
    'MRK',   # Merck — Keytruda franchise, 2.5% yield
    'BMY',   # Bristol-Myers — Celgene debt near paid; Eliquis+Opdivo FCF
    'NVO',   # Novo Nordisk — GLP-1 franchise (Ozempic/Wegovy/Victoza); ~40% OM, ~30% NM, ROE 80%+, near-zero debt; ~1.5% yield (Danish semi-annual payer); FCF machine; growth + dividend compounder
    'PFE',   # Pfizer — 6.6% yield, FCF 8.4% covers dividend; OM 31.6% (core pharma intact); ROE 8.3% + D/EV 0.323 (Seagen acq) block filter; post-COVID revenue cliff in numbers, grades A
    'CVS',   # CVS Health — pharmacy/PBM/Aetna; 2.6% yield, FCF 4.1%; OM 4.1%/ROE 3.8%/D/EV 0.401 all blocking; Aetna debt + PBM regulatory headwinds; grades B, watch for restructuring

    # Consumer staples — pricing power tollbooths
    'PG',    # P&G — 68yr dividend king, brand moat
    'CL',    # Colgate — 62yr dividend king, oral care dominance
    'KO',    # Coca-Cola — 62yr dividend king, global distribution moat
    'PEP',   # PepsiCo — 51yr aristocrat, snacks + beverages
    'KHC',   # Kraft Heinz — Buffett/3G Capital legacy; 7% yield, FCF 11.9% (covers div 1.7x), OM 20.7% (brands intact); NM -23%/ROE -12.6% (goodwill write-downs)/D/EV 0.478 (LBO debt) all blocking; FCF story is real but balance sheet is the puzzle
    'CLX',   # Clorox — 46yr dividend aristocrat; cleaning/household (Clorox, Glad, Brita, Burt's Bees); OM recovering post-inflation hit, ~3.5% yield, FCF covers dividend
    'KR',    # Kroger — grocery chain, 2.2% yield, FCF 8.9% (covers dividend); OM 3.4%/NM 0.7% (structural grocery thin margins) + D/EV 0.341 block filter; grades B; scale moat, not a margin story
    'GPC',   # Genuine Parts — 68yr dividend king, auto/industrial parts distribution
    'SYY',   # Sysco — food distribution aristocrat, 54yr growth

    # Industrials — durable cash generators
    'ITW',   # Illinois Tool Works — 80/20 model, 50yr aristocrat, 25% OM
    'EMR',   # Emerson Electric — 43yr aristocrat, process automation
    'GWW',   # W.W. Grainger — industrial distribution, pricing power, 53yr growth
    'CMI',   # Cummins — engines + power, 18yr growth
    'DOV',   # Dover Corp — diversified industrial, 69yr dividend king
    'SNA',   # Snap-on — professional tools + diagnostics + repair software; franchise toolbox-on-credit dealer network = sticky recurring relationship with technicians (hard to displace once in the bay); GrossM 51.8%, OM 25.4%, NM 19.6%, ROE 17.9%, D/EV 0.061, FCF 5.1%, yield ~2.6%; 14yr+ consecutive div growth (Aristocrat path); A+; 4/4 MA aligned, RSI 68.6, MACD expanding — strong momentum; added 2026-08-06

    # Specialty Materials — niche chemical compounders
    'CBT',   # Cabot Corporation — specialty chemicals (carbon black for tires/rubber/coatings, activated carbon for water/air/pharma purification, specialty fluids for drilling/processing); niche industrial inputs with meaningful switching costs; OM 14.3%, NM 5.2%, ROE 13.3%, FCF 5.8%, RevG 6.4%; D/EV 0.227 (slightly over gate, structural for a capex-intensive materials co) + GrossM 24.2% (materials structural, not fixable) — both acknowledged; yield ~2.8%, consistent payer; watch D/EV trending toward 0.20 as FCF compounds; added 2026-08-07

    # Franchise / consumer
    'MCD',   # McDonald's — 44% OM franchise royalty, 49yr div growth


    # Technology with growing dividend
    'TXN',   # Texas Instruments — analog semis, 20yr growth, FCF machine
    'MSFT',  # Microsoft — massive FCF, 20yr+ growth, low yield but compounding
    'AAPL',  # Apple — buyback + dividend machine, massive FCF
    'FIS',   # Fidelity National Information Services — banking + payments infrastructure software (core banking, digital banking, fraud, capital markets, wealth mgmt); post-Worldpay spinoff (2023: sold 55% stake for $18.5B) is now a focused banking-tech platform, not a merchant acquirer; ~4% yield, payout 31.8% (dividend well covered by earnings), FCF $2.45B positive (5.6% yield vs 4% payout = real buffer); OM 16.4%, NM 23.3%, ROE 17.2% all clean; fwdPE 6.5x cheap (priced like the debt is permanent); D/EV 0.486 only blocker — $21B Worldpay merger debt (2019 $43B deal); $18.5B Worldpay proceeds + $2.45B/yr FCF = deleveraging path is real; -42% from 52w high ($76 → $44) — price dislocated from business quality; not a quality-filter screener name (D/EV > 0.30 fails) but FCF coverage is honest and dividend trajectory is durable; added 2026-08-05


    # Energy — integrated, durable through cycles
    'CVX',   # Chevron — 37yr aristocrat, integrated oil
    'XOM',   # ExxonMobil — 42yr consecutive increases, massive scale
    'CNQ',   # Canadian Natural Resources — largest Canadian oil producer; oil sands (40-50yr reserve life, near-zero decline post-construction) = cash machine; Berkshire Hathaway holds it; OM 21.8%, NM 25.1%, ROE 22.8%, D/EV 0.191, FCF 6.2%, yield 4.5%, PE 11.8x, payout 46%; A+
    'OXY',   # Occidental Petroleum — largest Permian operator (CrownRock acquisition added scale); OxyChem sold to Berkshire Hathaway for $9.7B cash (Oct 2025) — OXY is now a pure-play Permian E&P, chemicals diversification gone but $9.7B proceeds went straight at CrownRock debt, materially cleaning the balance sheet; Berkshire still holds ~28%+ OXY common + $10B preferred (8% dividend) separately from OxyChem — natural buyer floor remains; Vicki Hollub CEO highly regarded; Direct Air Capture (Stratos plant) = carbon optionality + DOE backing; not a dividend aristocrat (cut in 2020); sits between CVX/XOM (core) and DVN (satellite) — larger Permian scale than DVN but now equally pure-play oil-price exposed; watch debt paydown completion + FCF coverage as qualifying gate each quarter
    'SM',    # SM Energy — mid-cap Permian E&P (Midland Basin + Delaware Basin); fixed + variable dividend model similar to DVN — fixed base small, variable from excess FCF above breakeven; OM 61.3%, FCF 23.1% (real cash generation), GrossM 84.6% (E&P lifting cost economics); D/EV 0.545 is the watch item — higher leverage than DVN/OXY, meaningful at oil trough; ROE 16.1% solid; RevG 227.8% is commodity price spike, not durable; size at 30-40% of what you'd allocate to CVX/XOM for the same energy income thesis; variable dividend evaporates in a sustained oil downturn (same design as DVN); watch FCF coverage + debt paydown progress as qualifying gate each quarter; added 2026-08-07
    'DVN',   # Devon Energy — SATELLITE position, not core; pure Permian (Delaware Basin) E&P with no downstream, no chemicals, no Berkshire floor; fixed + variable dividend model is honest (fixed base ~$40/bbl, variable from excess FCF) but most oil-price naked of the energy names; variable dividend evaporates below ~$50/bbl by design; size at 50-60% of what you'd allocate to CVX/XOM/OXY for the same income thesis; watch FCF coverage and payout ratio each quarter as qualifying gate

    # Banks — deposit franchise compounders
    'PNC',   # PNC Financial Services — #5 US bank by assets; retail + corporate banking + asset management (BBVA acquisition added scale); Main Street + Wall Street balanced model, not Goldman-style trading-heavy; net interest margin expands as rates stay elevated; consistent dividend grower, returned to pre-COVID payout levels fast; D/EV reads elevated (bank deposits = structural liabilities, same sector-aware read as PRU/VZ — not deteriorating debt); fee income from treasury management + capital markets + asset management cushions NII volatility in rate cycles; watch payout ratio and NIM trend each quarter as the qualifying gate
    'CATY',  # Cathay General Bancorp — California regional bank serving the Chinese-American community; unique franchise: deep cultural trust + bilingual staff + trade finance expertise (US-China commerce corridor) = sticky deposit base; OM 62.6%, NM 43.7%, ROE 11.7%, D/EV 0.036 (exceptionally well-capitalized for a bank), RevG 13.8%; FCF/GrossM banking artifacts; yield ~3%, consistent payer; 4/4 MA aligned, RSI 72.4 — strong momentum; added 2026-08-07
    'IBOC',  # International Bancshares — Texas regional bank (US-Mexico border corridor); border franchise = unique moat in cross-border commerce, trade finance, remittances between US and Mexico; OM 63.9%, NM 49.9%, ROE 13.5%; FCF/GrossM are banking artifacts (deposits-as-liabilities, same sector read as PNC/CFG); D/EV 0.151 low for a bank; yield ~3.5%, consistent dividend grower; RevG 5.4% slow but NIM discipline is exceptional for a regional bank; watch NIM trend + ROE stability as qualifying gate each quarter; added 2026-08-07
    'CFG',   # Citizens Financial Group — #7 US regional bank by assets; retail + commercial banking across New England + Mid-Atlantic + Midwest; OM 35.1%, NM 26.1%, RevG 14.7%; ROE 8.3% (below 10% gate — genuine watch item for a bank, below PNC/USB peer range); D/EV 0.459 + FCF 0.0% are structural bank artifacts (deposits = liabilities, FCF doesn't report cleanly for banks — same sector-aware read as PNC); dividend yield ~3.5%, consistent payer; 4/4 MA aligned, slope +4.7%, RSI 71.4 — strong momentum; watch NIM trend + ROE recovery above 10% as rate environment normalizes; added 2026-08-06
    'STT',   # State Street Corporation — global custodian bank duopoly (only BNY Mellon competes globally) + SPDR ETF franchise (SPY, GLD, SLV — one of the largest ETF issuers); custody moat = switching a pension fund's custodian is a multi-year project requiring board approval + legal transfer — structural stickiness; SPDR fee income is recurring royalty on $1T+ AUM; OM 27.8%, NM 23.0%, ROE 12.4%; FCF 0%, GrossM 0%, D/EV 0.000 all banking artifacts (same sector read as PNC/CFG — deposits-as-liabilities, not deteriorating); RevG -2.8% watch item (NII cycle + fee pressure); yield ~3%, consistent payer; RSI 85.5 + 56.2% above 87w MA at time of add = very extended, not an entry — buy on correction; judge by custody AUM + SPDR ETF AUM growth + NIM trend; added 2026-08-08

    # Midstream / MLP — toll-road pipelines, high yield, K-1 tax
    'EPD',   # Enterprise Products Partners — largest US midstream MLP; Permian + Gulf Coast pipeline network (natural gas, NGL, crude) + NGL fractionation + LNG/petrochemical export terminals; fee-based toll contracts = revenue independent of commodity prices (volume matters, not oil price); 25+ consecutive years of distribution growth, never cut; Dan Duncan family owns ~30%+ (founder-aligned, not financial-engineer-aligned); ROE 19.8%, OM 12.7% (pipeline margins look thin because revenue includes commodity pass-through — toll economics better than GAAP shows), yield 5.7%, fwdPE 12.2x; distributable cash flow (DCF) coverage ~1.7x = distribution very conservatively funded; D/EV elevated but investment-grade rated (BBB+) — structural pipeline infrastructure leverage, not deteriorating; caution: MLP issues K-1 (not 1099) + generates UBTI (avoid in IRA/Roth unless you want complexity); income vehicle, not a growth compounder — size for yield

    'ET',    # Energy Transfer LP — MLP peer to EPD; massive midstream network (natural gas, crude, NGL, refined products, LNG export); yield 6.73% (higher than EPD), FCF $1.72B real, RevG 32.1%; more aggressive than EPD: higher leverage (D/EV elevated), Kelcy Warren (founder/CEO) has run acquisitive playbook (Enable Midstream, Crestwood); KEY CAVEAT: ET cut its distribution 50% in 2020 COVID (EPD never has in 25+ years) — that's the trust differential; distribution rebuilt and growing again but the cut happened; same K-1/UBTI caution as EPD (MLP structure); size smaller than EPD given the cut history

    'CQP',   # Cheniere Energy Partners — Sabine Pass LNG terminal MLP; owns/operates the largest LNG export facility in the US (6 liquefaction trains + deepwater marine terminal + cryogenic storage); revenue model = fixed-fee tolling contracts (Cheniere parent + long-term SPAs with global counterparties) — cash flows are volume-based and contracted, not commodity-price exposed; unsexy asset (marine terminal + cryogenic tanks + compressors), sexy numbers: 20-25yr contracted revenue streams + distributions growing consistently; ~5-7% yield; D/EV elevated from infrastructure build-out (same structural read as EPD — investment-grade rated, not deteriorating); same K-1/UBTI caution as EPD/ET (MLP structure — avoid in IRA unless comfortable with complexity); size similar to EPD; added 2026-08-04

    # Telecom — high yield, FCF-covered, structural debt
    'VZ',    # Verizon — 6.1% yield, FCF 10.3% (1.7x dividend coverage), 25% OM, ROE 17%; D/EV 0.517 from 5G spectrum (structural, not deteriorating); income play not a compounder, no rev growth

    # Water & Utilities — regulated moats, infrastructure compounders
    'NEE',   # NextEra Energy — largest US utility by market cap; Florida Power & Light (regulated, ~6M customers, fastest-growing major US state) + NextEra Energy Resources (largest wind + solar operator in North America, ~25 GW); ~2.9% yield, payout 53% (lowest in utility sector = best dividend growth runway); OM 31.5% (best-in-class for a utility); ~10%/yr dividend growth rate sustained for 10+ years = Dividend Aristocrat with growth engine attached; AI datacenter + EV electrification demand = FPL rate base expansion accelerating; the premier utility dividend compounder; DCA name; added 2026-08-09
    'DUK',   # Duke Energy — #2 largest US IOU (Carolinas + Midwest + Florida, ~8M customers); ~3.5% yield, payout 64%, 50+ yr Dividend Aristocrat; OM 27.5%; coal-to-clean transition = $73B capex plan through 2028 = rate base compounding + PUC-approved earnings uplift; Southeast + Midwest geography = above-average load growth demographics; DCA name; added 2026-08-09
    'SO',    # Southern Company — regulated Southeast utility (Georgia Power + Alabama Power + Mississippi Power + Southern Natural Gas) + Southern Power (wholesale); ~3.3% yield, payout 72%, 70+ yr consecutive dividend history; OM 29.6%; Vogtle Units 3+4 (first new US nuclear plant in 30+ years) now fully online = large baseload capacity addition driving rate base + EPS growth; Southeast sunbelt demographics = strong load growth; DCA name; added 2026-08-09
    'AEE',   # Ameren — regulated electric + gas utility (Missouri + Illinois, ~2.4M customers); ~2.8% yield, payout 51% (second-lowest payout in utility sector after NEE = meaningful growth headroom), Dividend Aristocrat; OM 25.2%; Missouri PUC is constructive regulator + Illinois clean energy transition adds rate base from renewables capex; clean, underrated, consistent compounder; DCA name; added 2026-08-09
    'AWK',   # American Water Works — largest US water utility; ~37% OM, ~2.2% yield, regulated monopoly model, 15yr+ div growth; D/EV ~0.22 structural (capex-heavy utility), FCF thin from infrastructure spend; grades A
    'XYL',   # Xylem — water tech (pumps, treatment, smart metering); ~13% OM, ~1.3% yield, Evoqua acquisition adds scale; D/EV ~0.17, FCF covers dividend; grades A/B depending on yield gate
    'WEC',   # WEC Energy Group — regulated Midwest utility (Wisconsin/Illinois/Michigan); ~3.5% yield, 20yr+ consecutive dividend growth; OM 29%, NM 16%; D/E structural IOU capex (PUC-approved rate base) + FCF negative from grid/AI datacenter buildout; ROE PUC-capped ~11%; DCA name — buy regularly, hold long; AI datacenter load growth in Wisconsin corridor = rate base expansion = higher allowed earnings over time
    'XEL',   # Xcel Energy — regulated electric/gas utility (MN, CO, TX Panhandle, NM); ~3% yield, payout 64% (FCF-covered on rate base earnings basis), consistent dividend grower; OM 22.7%, fwd P/E 17x; same structural D/E + FCF negatives as WEC (PUC-approved capex, not deteriorating); datacenter angle: Colorado (Denver metro) + Minnesota hyperscaler load growth = rate base expansion = higher allowed earnings; also largest US wind generator — coal-to-wind transition adds rate base; DCA alongside WEC; gate: dividend growing 5-7%/yr as datacenter contracts convert to rate base additions

    'CNP',   # CenterPoint Energy — regulated electric + natural gas utility (Houston TX + Indiana + Minnesota); ~2.4% yield ($0.96/yr), payout 54% (conservative for a utility — room to grow), OM 24.5%, NM 11.6%; D/EV 0.483 structural (regulated utility capex model, PUC rate base recovery); Houston corridor = fastest-growing major US metro = rate base expansion from residential/commercial load growth + Hurricane Beryl grid hardening capex (PUCT-approved = future earnings uplift); DCA name; added 2026-08-09
    'SRE',   # Sempra — regulated California utilities (SoCalGas + SDG&E) + Sempra Infrastructure LNG (Port Arthur LNG Texas + Energía Costa Azul Mexico Pacific LNG); ~3.1% yield ($2.63/yr), 20yr+ consecutive dividend growth, payout ~75%; D/EV 0.359 + FCF -50% structural during LNG terminal construction — take-or-pay offtake contracts signed, FCF should flip strongly positive once Port Arthur Phase 1 online; dividend covered by regulated utility earnings even during LNG build; OM 28.3%, NM 16.8%; DCA name — the LNG optionality is free on top of the regulated utility dividend base; added 2026-08-09

    # Recovery / dividend watchlist — yield history exists, not yet qualifying; tracked for gate clearance
    'SWKS',  # Skyworks Solutions — RF front-end modules for smartphones (Apple ~55% of revenue) + IoT + automotive; ~4.6% yield, FCF $1.29B (~14% FCF yield on market cap) = dividend covered on cash basis even when GAAP payout ratio looks stretched; GrossM 40%, OM 7.3% (trough), ROE 5.1% (trough), RevG -3.1%; two headwinds: smartphone cycle weakness + Apple in-sourcing RF chips internally (longer-term structural risk, not imminent cliff — Apple transition takes years); TXN analog: deeply embedded in designs, cash generative through cycles; gate: OM recovering above 15% as smartphone volumes stabilize + Apple in-sourcing timeline clarity
    'NKE',   # Nike — OM 6.9%/NM 4.8% abysmal now (DTC transition + China); brand moat intact,
             # SNKRS app + Nike ecosystem = potential network flywheel; watch for margin recovery
    'GM',    # General Motors — Chevrolet, GMC, Cadillac, Buick; ICE dominant + Ultium EV platform;
             # OM 3.2% (auto assembly is structurally thin); NM 1.1%;
             # D/EV 0.696 = GM Financial captive finance arm (~$120B loan book), same structural read as PRU;
             # yield ~0.9% (low payout, conservative post-2009 lessons); FCF strong;
             # gate: OM >8% as GM Pro fleet + Cadillac margin mix improve
    'F',     # Ford Motor — Ford Pro (Transit/Super Duty commercial trucks, highest-margin segment),
             # Ford Blue (ICE legacy), Ford Model e (EV — currently loss-making, dragging NM negative);
             # OM 5.7%, NM -3.2% (EV losses); D/EV 0.808 = Ford Credit captive finance arm (~$130B AUM);
             # yield ~4%; Ford Pro is the crown jewel — fleet penetration in commercial trucks is durable;
             # gate: Model e losses narrow + NM turns positive
    'VFC',   # VF Corporation — Wrangler, Lee, Timberland, Dickies; 50yr Dividend Aristocrat before cut 2023;
             # sold Supreme (2024) for debt paydown; D/EV 0.439 now manageable, ROE 22% intact;
             # OM 3.8% is the only structural gap — cost-out + brand mix stabilization the path;
             # gate: OM >10% sustained + dividend above $0.50/yr
    'FMC',   # FMC Corporation — ag-chem (Rynaxypyr insecticide patent = real pricing power globally);
             # OM went negative (-0.5%) during 2023-24 destocking trough — NOT structural deterioration;
             # NM -72.9% = goodwill impairments, not operations; D/EV 0.823 elevated, needs delevering;
             # gate: OM recovery above 15% as destocking normalizes + D/EV below 0.5


    # Precious Metals — high-margin royalty and mining compounders
    'GFI',   # Gold Fields — South African gold miner (NYSE ADR); mines in Ghana/Australia/Chile/SA; OM 51.8%, NM 40.8%, ROE 51.9%, D/EV 0.046, FCF 8.2%, yield 6%, PE 8.8x; Salares Norte (Chile) online + gold ATH = beast numbers; A+
    'B',     # Barrick Mining — world's #2 gold miner; Nevada/Carlin Trend crown jewels (US rule-of-law, no country risk premium); OM 56.2%, NM 32.1%, ROE 25.2%, D/EV 0.063, FCF 7.8%, yield 1.7%, PE 11.1x; same gross margin as GFI (55%) but lower ROE/ROA — market pays premium for asset geography safety; A+

    # Crossover from growth universe — pass dividend filter
    'ACN',   # Accenture — consulting/IT services; 13.8% OM, 3.9% yield, FCF 11.9%, D/EV 0.082, P/E 13.6; A+
    'CTSH',  # Cognizant Tech — IT services/outsourcing; ~15% OM, ~1.8% yield, FCF covers dividend, D/EV near zero, low-debt capital-light model; A
    'ADP',   # ADP — payroll/HCM platform; 30.2% OM, 3.1% yield, FCF 5.4%, D/EV 0.049, P/E 20.7; A+
    'GIS',   # General Mills — cereal/food staples; 19.2% OM, 7.1% yield, FCF 12.3%, zero debt, P/E 8.4; A+ (yield elevated — stock under pressure, not a cut signal)
    'BR',    # Broadridge Financial — investor comms infra; 18.4% OM, 2.7% yield, FCF 7.1%, D/EV 0.173, P/E 15.4; A
    'CF',    # CF Industries — nitrogen fertilizer; 33.6% OM, 1.9% yield, FCF 6.6%, D/EV 0.175, P/E 9.5; A
    'CME',   # CME Group — futures/derivatives exchange; 69.8% OM, 2.0% yield, FCF 3.2%, D/EV 0.039, P/E 22.7; A (price in downtrend, watch for base)
    # 'CTRA' removed — acquired by DVN (2026)
    'FDS',   # FactSet — financial data/analytics; 29.8% OM, 1.9% yield, FCF 6.8%, D/EV 0.157, P/E 15.3; A
    'HSY',   # Hershey — chocolate/snacks brand moat; 21.3% OM, 3.2% yield, FCF 4.1%, D/EV 0.136, P/E 34; A
    'KMB',   # Kimberly-Clark — tissue/personal care staple; 19.6% OM, 4.9% yield, FCF 3.0%, D/EV 0.172, P/E 20.2; A
    'TRI',   # Thomson Reuters — legal/news data platform; 30.3% OM, 3.1% yield, FCF 4.7%, D/EV 0.072, P/E 23.4; A
    'HD',    # Home Depot — home improvement duopoly; 11.9% OM, 2.8% yield, FCF 3.0%, D/EV 0.160, P/E 23.9; B
    'PPG',   # PPG Industries — global #2 coatings (architectural: Glidden/Olympic/PPG brands + industrial: automotive OEM, aerospace, packaging, protective coatings); 50+ year Dividend Aristocrat, yield ~2.5-3%; GrossM 41.2%, OM 14.0%, NM 9.6%, ROE 19.3%, FCF 4.2%, RevG 7.2%; D/EV 0.229 only blocker — acquisition-driven (serial acquirer model, same structural read as SHW); FCF 4.2% covers dividend; SHW peer in the coatings duopoly — different channel (PPG heavier in industrial/automotive, SHW heavier in architectural contractor); watch D/EV delevering toward 0.20 as FCF compounds; added 2026-08-08

    # REIT — Experiential / Net Lease
    'EPR',   # EPR Properties — experiential net-lease REIT; owns theaters, ski resorts, attractions, early childhood education (La Petite Academy); triple-net leases = tenants pay taxes/insurance/maintenance, EPR collects rent; OM 51.3%, NM 37.7%, ROE 11.7% (passes gate), FCF 7.1% covers 5.8% yield (MOS +1.3%); D/EV 0.392 only blocker — REIT structure debt secured against experiential properties, same read as VICI; judge by AFFO coverage not GAAP earnings; added 2026-07-29
    'VICI',  # VICI Properties — largest gaming/experiential REIT; Caesars (45%), MGM, Venetian, Hard Rock; 15-20yr triple-net leases with CPI escalators = built-in inflation hedge; ~5.5% yield, payout 61% AFFO (conservative for REIT), FCF $1.28B; zero tenant defaults since 2017 IPO; moat = gaming license tied to location (tenants can't relocate); SIP for yield compounding; ROE/D/E block standard filter — REIT-structure artifacts, judge by AFFO coverage and dividend growth

    # BDC — Business Development Company
    'MAIN',  # Main Street Capital — BDC lending to lower middle market; internally managed (removes fee conflict vs externally managed peers); ~8.4% yield paid monthly + semi-annual special dividends; trades at ~1.55x NAV (premium unusual for BDCs, reflects management quality); ROE 14.4%; BDC structure means OM/D/E filters don't apply cleanly — judge by: NAV growth + dividend coverage + management track record
    'ARCC',  # Ares Capital Corporation — largest BDC by assets (~$22B+); externally managed by Ares Management (ARES); lends to middle market companies ($10M–$1B revenue) that can't access public debt markets; scale moat: largest BDC = lowest cost of capital = attracts better borrowers = lower credit losses = virtuous cycle; yield ~9-10%, quarterly distributions; D/EV 0.532 structural (BDCs borrow to lend — leverage is the model), ROE 6.9% mark-to-market distortion — judge by NAV/share growth + dividend coverage ratio + non-accrual rate (credit quality); GrossM 100%, OM 75.7%, 4/4 MA aligned; vs MAIN: ARCC is externally managed (fee conflict exists), larger scale, higher yield; added 2026-08-08

    # Traditional Asset Managers — incumbent active management, yield elevated from structural pressure
    'BEN',   # Franklin Resources (Franklin Templeton) — 40+ year Dividend Aristocrat (~5-6% yield); active fixed income + equity management across global platforms; Western Asset Management acquisition adds scale in institutional fixed income but also integration costs; FCF -17.4% is the real flag: active manager AUM outflows to passive ETFs have been persistent, Western Asset acquisition added debt absorption; OM 13.0%, NM 8.7%, D/EV 0.172, RevG 14.3%, ROE 7.9% (below 10% gate); yield is high because stock is under pressure from secular active→passive shift — not a cut signal yet (40+ yr aristocrat), but FCF negative is the watch gate; judge by: AUM net flow trend + FCF recovery + dividend coverage ratio; added 2026-08-08

]


# ─── MA Alignment ────────────────────────────────────────────────────────────

def _ma_score_inner(ticker):
    hist  = yf.Ticker(ticker).history(period='2y', interval='1wk')
    close = hist['Close']
    if len(close) < 40:
        return None
    price = float(close.iloc[-1])
    ma50d = float(close.tail(10).mean())
    ma20w = float(close.tail(20).mean())
    ma10m = float(close.tail(43).mean())
    ma20m = float(close.tail(87).mean())
    score = sum([price > ma50d, price > ma20w, price > ma10m, price > ma20m])
    return (ticker, round(price, 2), score)

def ma_score(ticker):
    return _fetch(ticker, _ma_score_inner)


# ─── Fundamentals ────────────────────────────────────────────────────────────

def _get_data_inner(ticker):
    info = yf.Ticker(ticker).info
    if not info or 'marketCap' not in info:
        return None

    mc   = info.get('marketCap') or 0
    ev   = info.get('enterpriseValue') or 0
    debt = info.get('totalDebt') or 0
    fcf  = info.get('freeCashflow') or 0
    om   = (info.get('operatingMargins') or 0) * 100
    nm   = (info.get('profitMargins') or 0) * 100
    roe  = (info.get('returnOnEquity') or 0) * 100
    roa  = (info.get('returnOnAssets') or 0) * 100
    pe   = info.get('trailingPE') or 0
    payout_raw = (info.get('payoutRatio') or 0) * 100
    payout = payout_raw if payout_raw <= 200 else 0   # suppress garbled data

    # yfinance dividendYield quirk: sometimes decimal (0.045), sometimes percent (4.5),
    # sometimes garbled (37 for AAPL which should be 0.37%). Heuristic normalization:
    raw = info.get('dividendYield') or info.get('trailingAnnualDividendYield') or 0
    if raw > 20:
        div_yield = raw / 100    # clearly percent*100 — divide back down
    elif raw > 1:
        div_yield = raw          # already in percent form (e.g. 4.7 = 4.7%)
    else:
        div_yield = raw * 100    # decimal form (e.g. 0.047 = 4.7%)
    if div_yield > 15:
        div_yield = 0            # still unreasonable — suppress

    fcf_yield = fcf / mc * 100 if mc else 0
    dev       = debt / ev if ev else 0

    if pe and (math.isinf(pe) or pe <= 0):
        pe = None

    return {
        'div_yield': round(div_yield, 2),
        'payout':    round(payout, 1),
        'fcf_yield': round(fcf_yield, 1),
        'om':        round(om, 1),
        'nm':        round(nm, 1),
        'roe':       round(roe, 1),
        'roa':       round(roa, 1),
        'dev':       round(dev, 3),
        'pe':        round(pe, 1) if pe else None,
    }

def get_data(ticker):
    return _fetch(ticker, _get_data_inner)


# ─── Grading ─────────────────────────────────────────────────────────────────

def dividend_grade(d):
    if d is None:
        return '—'
    pts = 0

    # Yield — entry point, not the driver (1 pt only — high yield on falling price is a trap)
    if d['div_yield'] >= 2.0: pts += 1

    # MOS — FCF buffer above dividend (2 pts — the real sustainability signal)
    mos = d['fcf_yield'] - d['div_yield'] if d['div_yield'] > 0 else d['fcf_yield']
    if mos >= 0:  pts += 1   # FCF covers dividend
    if mos >= 3:  pts += 1   # strong buffer — dividend has room to grow

    # ROE — quality of the business (2 pts — can it sustainably generate returns?)
    if d['roe'] >= 12 or d['roa'] >= 10: pts += 1
    if d['roe'] >= 20:                   pts += 1   # compounder-grade returns

    # Margin quality — earnings durability
    if d['om'] >= 15: pts += 1
    if d['om'] >= 25: pts += 1

    # Debt discipline
    if d['dev'] <= 0.10: pts += 1

    # Value
    if d['pe'] and d['pe'] <= 15: pts += 1

    if pts >= 7: return 'A+'
    if pts >= 5: return 'A'
    if pts >= 3: return 'B'
    return '—'


def passes_filter(d):
    if d is None: return False
    if d['div_yield'] < 1.5:  return False   # meaningful yield gate
    if d['fcf_yield'] <= 0:   return False   # must generate cash
    if d['om'] < 8:           return False   # quality floor
    if d['dev'] > 0.30:       return False   # debt ceiling
    roe_ok = d['roe'] >= 10
    roa_ok = d['roa'] >= 10
    if not roe_ok and not roa_ok: return False
    return True


# ─── HTML Output ─────────────────────────────────────────────────────────────

RECOVERY_TICKERS = {'VFC', 'FMC', 'NWL', 'NKE', 'GM', 'F'}

def _grade_color(g):
    return {'A+': '#3fb950', 'A': '#58a6ff', 'B': '#d29922'}.get(g, '#8b949e')

def _cell(val, color=None, bold=False, align='right'):
    s = f'color:{color};' if color else ''
    b = 'font-weight:600;' if bold else ''
    return f'<td style="padding:7px 10px;text-align:{align};{s}{b}">{val}</td>'

def build_dividend_html(rows, aligned_4, aligned_3, below, now):
    n_total   = len(rows)
    n_4       = len(aligned_4)
    n_aplus   = sum(1 for *_, g, ok in aligned_4 if g == 'A+')
    n_a       = sum(1 for *_, g, ok in aligned_4 if g == 'A')
    n_passing = sum(1 for *_, g, ok in aligned_4 if ok)

    def stat(label, val, color='#e6edf3'):
        return (
            '<div style="background:#161b22;border:1px solid #21262d;border-radius:8px;'
            'padding:12px 20px;text-align:center">'
            f'<div style="font-size:22px;font-weight:700;color:{color}">{val}</div>'
            f'<div style="font-size:11px;color:#8b949e;margin-top:3px">{label}</div>'
            '</div>'
        )

    stats_html = (
        '<div style="display:flex;gap:12px;flex-wrap:wrap;margin-bottom:24px">'
        + stat('Universe', n_total)
        + stat('4/4 Aligned', n_4, '#58a6ff')
        + stat('A+ (4/4)', n_aplus, '#3fb950')
        + stat('A (4/4)', n_a, '#58a6ff')
        + stat('Passes Filter', n_passing, '#3fb950')
        + '</div>'
    )

    tbl_style = (
        'width:100%;border-collapse:collapse;font-size:12px;'
        'background:#0d1117;margin-bottom:32px'
    )
    th_style  = 'padding:8px 10px;text-align:right;color:#8b949e;font-weight:400;border-bottom:1px solid #21262d;font-size:11px'
    th_left   = th_style.replace('right', 'left')

    th_center = th_style.replace('right', 'center')

    def table_header():
        cols   = ['Ticker','Gr','Price','MA','Yield','FCF%','Payout','OM%','D/EV','P/E','MOS','Filter']
        aligns = ['left','left'] + ['right']*9 + ['center']
        ths = ''
        for c, a in zip(cols, aligns):
            sty = th_left if a == 'left' else (th_center if a == 'center' else th_style)
            ths += '<th style="' + sty + '">' + c + '</th>'
        return '<thead><tr>' + ths + '</tr></thead>'

    def grade_badge(g):
        c = _grade_color(g)
        return (
            f'<span style="background:{c}22;color:{c};border:1px solid {c}44;'
            f'border-radius:4px;padding:1px 6px;font-size:11px;font-weight:600">{g}</span>'
        )

    def ma_badge(ma):
        c = '#3fb950' if ma == 4 else '#d29922' if ma == 3 else '#8b949e'
        return f'<span style="color:{c};font-weight:600">{ma}/4</span>'

    def html_row(t, p, ma, d, g, ok):
        is_recovery = t in RECOVERY_TICKERS
        row_bg = ''
        if g == 'A+' and ok:
            row_bg = 'background:rgba(63,185,80,0.05);'
        elif g == 'A' and ok:
            row_bg = 'background:rgba(88,166,255,0.04);'
        elif is_recovery:
            row_bg = 'background:rgba(248,81,73,0.03);'

        hover = f'<tr style="{row_bg}border-bottom:1px solid #21262d14">'

        if d is None:
            return hover + f'<td style="padding:7px 10px">{t}</td>' + '<td colspan="11" style="padding:7px 10px;color:#8b949e">no data</td></tr>'

        ticker_style = 'font-weight:600;'
        if is_recovery:
            ticker_style += 'color:#f0883e;'
        ticker_td = f'<td style="padding:7px 10px;{ticker_style}">{t}</td>'

        yc = '#3fb950' if d['div_yield'] >= 3.5 else '#d29922' if d['div_yield'] >= 2.0 else '#8b949e'
        fc = '#3fb950' if d['fcf_yield'] >= d['div_yield'] else '#f85149' if d['fcf_yield'] <= 0 else '#d29922'
        oc = '#3fb950' if d['om'] >= 25 else '#58a6ff' if d['om'] >= 15 else '#d29922' if d['om'] >= 8 else '#f85149'
        dc = '#3fb950' if d['dev'] <= 0.10 else '#d29922' if d['dev'] <= 0.30 else '#f85149'

        ys   = f"{d['div_yield']:.1f}%" if d['div_yield'] > 0 else '—'
        fs   = f"{d['fcf_yield']:.1f}%"
        pays = f"{d['payout']:.0f}%"   if d['payout'] > 0 else '—'
        oms  = f"{d['om']:.1f}%"
        ds   = f"{d['dev']:.3f}"
        pes  = f"{d['pe']:.1f}x"       if d['pe'] else '—'
        flag = '<span style="color:#3fb950">✓</span>' if ok else '<span style="color:#f85149">✗</span>'
        ps   = f'${p:.2f}'

        mos_val = d['fcf_yield'] - d['div_yield']
        if d['div_yield'] > 0:
            mos_s  = ('+' if mos_val >= 0 else '') + f'{mos_val:.1f}%'
            mos_c  = '#3fb950' if mos_val >= 3 else '#d29922' if mos_val >= 0 else '#f85149'
        else:
            mos_s, mos_c = '—', '#8b949e'

        return (
            hover
            + ticker_td
            + _cell(grade_badge(g), align='left')
            + _cell(ps, '#e6edf3', bold=True)
            + _cell(ma_badge(ma), align='right')
            + _cell(ys, yc)
            + _cell(fs, fc)
            + _cell(pays)
            + _cell(oms, oc)
            + _cell(ds, dc)
            + _cell(pes)
            + _cell(mos_s, mos_c, bold=True)
            + f'<td style="padding:7px 10px;text-align:center">{flag}</td>'
            + '</tr>'
        )

    def section(title, section_rows, grade_groups=False):
        if not section_rows:
            return ''
        hdr = (
            f'<div style="font-size:13px;font-weight:600;color:#e6edf3;margin-bottom:10px">'
            f'{title} <span style="color:#8b949e;font-weight:400">({len(section_rows)} names)</span></div>'
        )
        tbl = f'<table style="{tbl_style}">' + table_header() + '<tbody>'

        if grade_groups:
            last_g = None
            for t, p, ma, d, g, ok in section_rows:
                if g != last_g:
                    label = g if g != '—' else 'Below threshold'
                    tbl += (
                        f'<tr class="grp"><td colspan="12" style="padding:6px 10px 4px;'
                        f'color:#8b949e;font-size:10px;letter-spacing:.06em;text-transform:uppercase;'
                        f'background:#161b22;border-bottom:1px solid #21262d">{label}</td></tr>'
                    )
                    last_g = g
                tbl += html_row(t, p, ma, d, g, ok)
        else:
            for t, p, ma, d, g, ok in section_rows:
                tbl += html_row(t, p, ma, d, g, ok)

        tbl += '</tbody></table>'
        return hdr + tbl

    legend = (
        '<div style="font-size:11px;color:#8b949e;margin-bottom:24px;line-height:1.8">'
        '<span style="color:#3fb950">✓</span> passes all filter gates &nbsp;·&nbsp; '
        '<span style="color:#f85149">✗</span> one or more gates failing &nbsp;·&nbsp; '
        '<span style="color:#f0883e">orange ticker</span> = recovery/watchlist (tracked, not yet qualifying) &nbsp;·&nbsp; '
        'Filter gates: yield ≥1.5% · FCF>0 · OM≥8% · D/EV≤0.30 · ROE or ROA ≥10% &nbsp;·&nbsp; '
        '<strong style="color:#e6edf3">MOS</strong> = FCF yield − Div yield (FCF buffer above dividend; '
        '<span style="color:#3fb950">green ≥+3%</span> · '
        '<span style="color:#d29922">yellow 0–3%</span> · '
        '<span style="color:#f85149">red = dividend not FCF-covered</span>)'
        '</div>'
    )

    body = (
        stats_html
        + legend
        + section('4/4 MA ALIGNED', aligned_4, grade_groups=True)
        + section('3/4 NEAR-ALIGNED', aligned_3)
        + section('BELOW STRUCTURE', below)
    )

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Dividend Screener — {now}</title>
<style>
  body{{background:#0d1117;color:#e6edf3;font-family:'SF Mono','Fira Code',monospace;font-size:13px;padding:28px 32px;margin:0}}
  h1{{font-size:16px;font-weight:600;margin:0 0 4px}}
  .sub{{color:#8b949e;font-size:12px;margin-bottom:20px}}
  table td,table th{{border-bottom:1px solid #21262d22}}
  tr:hover td{{background:#161b2288}}
  a{{color:#58a6ff;text-decoration:none}}
</style>
</head>
<body>
<h1>Dividend &amp; Income Screener</h1>
<div class="sub">{now} UTC &nbsp;·&nbsp; {n_total} names tracked</div>
{body}
</body>
</html>'''


# ─── Main ────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    now = datetime.now().strftime('%b %d %Y  %H:%M')

    print(f'\n  Fetching MA alignment for {len(UNIVERSE)} tickers ...', flush=True)
    with ThreadPoolExecutor(max_workers=6) as ex:
        ma_results = list(ex.map(ma_score, UNIVERSE))

    price_map = {t: (p, s) for r in ma_results if r for t, p, s in [r]}

    cache = _load_cache()

    print(f'  Fetching dividend data ...', flush=True)
    with ThreadPoolExecutor(max_workers=5) as ex:
        fresh = {t: d for t, d in zip(UNIVERSE, ex.map(get_data, UNIVERSE))}

    fund_results = {}
    for t in UNIVERSE:
        d = fresh.get(t)
        if d is not None:
            cache[t] = d          # update cache with fresh data
            fund_results[t] = d
        elif t in cache:
            fund_results[t] = cache[t]   # rate-limited — use last good data
            print(f'  [{t}] yfinance miss — using cached data', flush=True)
        else:
            fund_results[t] = None

    _save_cache(cache)

    # Build full result list
    rows = []
    for t in UNIVERSE:
        p, ma = price_map.get(t, (0, 0))
        d     = fund_results.get(t)
        g     = dividend_grade(d)
        ok    = passes_filter(d)
        rows.append((t, p, ma, d, g, ok))

    aligned_4 = sorted([r for r in rows if r[2] == 4], key=lambda x: (
        {'A+': 0, 'A': 1, 'B': 2, '—': 3}.get(x[4], 4), x[0]
    ))
    aligned_3 = sorted([r for r in rows if r[2] == 3], key=lambda x: x[0])
    below     = sorted([r for r in rows if r[2] < 3],  key=lambda x: x[0])

    HDR = f'  {"Ticker":<7} {"Gr":<4} {"Price":>8}  {"Yield":>6} {"FCF%":>6} {"Payout":>7} {"OM%":>6} {"D/EV":>6} {"P/E":>7} {"MOS":>7}'
    DIV = f'  {"─"*7} {"─"*4} {"─"*8}  {"─"*6} {"─"*6} {"─"*7} {"─"*6} {"─"*6} {"─"*7} {"─"*7}'

    def row_str(t, p, ma, d, g, ok):
        if d is None:
            return f'  {t:<7} {"?":4} {"—":>8}  no data'
        ps    = f'${p:.2f}'
        ys    = f'{d["div_yield"]:.1f}%'  if d["div_yield"] > 0 else '—'
        fs    = f'{d["fcf_yield"]:.1f}%'
        pays  = f'{d["payout"]:.0f}%'     if d["payout"] > 0 else '—'
        oms   = f'{d["om"]:.1f}%'
        ds    = f'{d["dev"]:.3f}'
        pes   = f'{d["pe"]:.1f}x'         if d["pe"] else '—'
        flag  = '' if ok else '  ✗'
        mos   = d["fcf_yield"] - d["div_yield"]
        moss  = ('+' if mos >= 0 else '') + f'{mos:.1f}%' if d["div_yield"] > 0 else '—'
        return f'  {t:<7} {g:<4} {ps:>8}  {ys:>6} {fs:>6} {pays:>7} {oms:>6} {ds:>6} {pes:>7} {moss:>7}{flag}'

    print(f'\n  DIVIDEND & VALUE SCREENER — {now}')
    print(f'  Universe: {len(UNIVERSE)} names\n')

    print(f'  4/4 ALIGNED — {len(aligned_4)} names')
    print(f'  {"─"*65}')
    print(HDR)
    print(DIV)

    last_grade = None
    for t, p, ma, d, g, ok in aligned_4:
        if g != last_grade:
            label = g if g != '—' else 'Below threshold'
            print(f'\n  {label}')
            last_grade = g
        print(row_str(t, p, ma, d, g, ok))

    if aligned_3:
        print(f'\n\n  3/4 NEAR-ALIGNED — {len(aligned_3)} names')
        print(f'  {"─"*65}')
        print(HDR)
        print(DIV)
        for t, p, ma, d, g, ok in aligned_3:
            print(row_str(t, p, ma, d, g, ok))

    if below:
        print(f'\n\n  BELOW STRUCTURE — {len(below)} names')
        print(f'  {"─"*65}')
        print(HDR)
        print(DIV)
        for t, p, ma, d, g, ok in below:
            print(row_str(t, p, ma, d, g, ok))

    # Summary
    passing_4 = [t for t, p, ma, d, g, ok in aligned_4 if ok]
    print(f'\n  {"─"*65}')
    print(f'  {len(passing_4)} names — 4/4 aligned + passes dividend filter')
    print(f'  A+ aligned: {sum(1 for t,p,ma,d,g,ok in aligned_4 if g=="A+")}'
          f'   A: {sum(1 for t,p,ma,d,g,ok in aligned_4 if g=="A")}')
    print()

    # HTML output
    import os, subprocess
    html = build_dividend_html(rows, aligned_4, aligned_3, below, now)
    out  = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'dividend_screener.html')
    with open(out, 'w') as f:
        f.write(html)
    print(f'  Saved → {out}')

    # Git push
    try:
        repo = os.path.dirname(os.path.abspath(__file__))
        subprocess.run(['git', 'add', 'dividend_screener.html', 'dividend_data_cache.json'], cwd=repo, check=True)
        subprocess.run(['git', 'commit', '-m', f'dividend_screener: {now} UTC'], cwd=repo, check=True)
        subprocess.run(['git', 'push', 'origin', 'main'], cwd=repo, check=True)
        print('  Pushed → GitHub')
    except subprocess.CalledProcessError as e:
        print(f'  Git push skipped: {e}')
