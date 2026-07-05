"""
internal_dividend.py — Dividend & Value Screener  (GITIGNORED)
Screens quality dividend payers for yield sustainability, margin quality,
low debt, and 4/4 MA alignment. Separate from growth screener.
Run: python internal_dividend.py
"""

import yfinance as yf
import math
import warnings
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

warnings.filterwarnings('ignore')

# ─── Universe ────────────────────────────────────────────────────────────────

UNIVERSE = [
    # Asset managers — fee income, capital-light, buyback compounders
    'TROW',  # T. Rowe Price — 37yr div growth, 37% OM, FCF 8%, P/E 12
    'AMP',   # Ameriprise — TROW twin; 37% OM, FCF 8%, P/E 12, aggressive buybacks
    'BEN',   # Franklin Templeton — higher yield, AUM flow challenged

    # Insurance — float-based compounders
    'AFL',   # Aflac — 42yr div growth, supplemental insurance moat, Japan exposure
    'CINF',  # Cincinnati Financial — 63yr dividend king, FCF 10.5%, pure compounder
    'TRV',   # Travelers — FCF 20%+, P/E 9, best underwriter in P&C
    'CB',    # Chubb — global P&C leader, 20% OM, fortress balance sheet
    'AJG',   # Arthur J. Gallagher — insurance broker, fee model, 30yr growth
    'AON',   # Aon — insurance/reinsurance broker, pricing power
    'PRU',   # Prudential Financial — US life insurance + retirement solutions + PGIM asset management ($1.3T+ AUM); PGIM fee income is the floor — stable capital-light earnings regardless of insurance cycle volatility; 4-5% yield, consistent multi-year dividend growth; D/EV reads elevated due to insurance policyholder liabilities (structural, not deteriorating debt — same sector-aware read as VZ on telecom spectrum); moat = scale in group insurance + PGIM distribution; watch payout ratio and FCF coverage each quarter as the qualifying gate

    # Healthcare / pharma
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

    # Franchise / consumer
    'MCD',   # McDonald's — 44% OM franchise royalty, 49yr div growth

    # Technology with growing dividend
    'TXN',   # Texas Instruments — analog semis, 20yr growth, FCF machine
    'MSFT',  # Microsoft — massive FCF, 20yr+ growth, low yield but compounding
    'AAPL',  # Apple — buyback + dividend machine, massive FCF

    # Energy — integrated, durable through cycles
    'CVX',   # Chevron — 37yr aristocrat, integrated oil
    'XOM',   # ExxonMobil — 42yr consecutive increases, massive scale
    'CNQ',   # Canadian Natural Resources — largest Canadian oil producer; oil sands (40-50yr reserve life, near-zero decline post-construction) = cash machine; Berkshire Hathaway holds it; OM 21.8%, NM 25.1%, ROE 22.8%, D/EV 0.191, FCF 6.2%, yield 4.5%, PE 11.8x, payout 46%; A+
    'OXY',   # Occidental Petroleum — largest Permian operator (CrownRock acquisition added scale); OxyChem sold to Berkshire Hathaway for $9.7B cash (Oct 2025) — OXY is now a pure-play Permian E&P, chemicals diversification gone but $9.7B proceeds went straight at CrownRock debt, materially cleaning the balance sheet; Berkshire still holds ~28%+ OXY common + $10B preferred (8% dividend) separately from OxyChem — natural buyer floor remains; Vicki Hollub CEO highly regarded; Direct Air Capture (Stratos plant) = carbon optionality + DOE backing; not a dividend aristocrat (cut in 2020); sits between CVX/XOM (core) and DVN (satellite) — larger Permian scale than DVN but now equally pure-play oil-price exposed; watch debt paydown completion + FCF coverage as qualifying gate each quarter
    'DVN',   # Devon Energy — SATELLITE position, not core; pure Permian (Delaware Basin) E&P with no downstream, no chemicals, no Berkshire floor; fixed + variable dividend model is honest (fixed base ~$40/bbl, variable from excess FCF) but most oil-price naked of the energy names; variable dividend evaporates below ~$50/bbl by design; size at 50-60% of what you'd allocate to CVX/XOM/OXY for the same income thesis; watch FCF coverage and payout ratio each quarter as qualifying gate

    # Telecom — high yield, FCF-covered, structural debt
    'VZ',    # Verizon — 6.1% yield, FCF 10.3% (1.7x dividend coverage), 25% OM, ROE 17%; D/EV 0.517 from 5G spectrum (structural, not deteriorating); income play not a compounder, no rev growth

    # Water & Utilities — regulated moats, infrastructure compounders
    'AWK',   # American Water Works — largest US water utility; ~37% OM, ~2.2% yield, regulated monopoly model, 15yr+ div growth; D/EV ~0.22 structural (capex-heavy utility), FCF thin from infrastructure spend; grades A
    'XYL',   # Xylem — water tech (pumps, treatment, smart metering); ~13% OM, ~1.3% yield, Evoqua acquisition adds scale; D/EV ~0.17, FCF covers dividend; grades A/B depending on yield gate

    # Recovery / future flywheel — watching, not yet qualifying
    'NKE',   # Nike — OM 6.9%/NM 4.8% abysmal now (DTC transition + China); brand moat intact,
             # SNKRS app + Nike ecosystem = potential network flywheel; watch for margin recovery

    # Consumer internet with dividend
    'MTCH',  # Match Group — Tinder/Hinge/OkCupid portfolio; 27.4% OM, 18.8% NM, FCF yield 9.5% covers 2.14% div, ROA 15.2%, P/E 13.9x; D/EV 0.346 from M&A debt only blocker (structural); grades A+, 4/4 MA aligned

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
    'CTRA',  # Coterra Energy — nat gas/oil E&P; 28.2% OM, 2.7% yield, FCF 5.1%, D/EV 0.132, P/E 15.0; A
    'FDS',   # FactSet — financial data/analytics; 29.8% OM, 1.9% yield, FCF 6.8%, D/EV 0.157, P/E 15.3; A
    'HSY',   # Hershey — chocolate/snacks brand moat; 21.3% OM, 3.2% yield, FCF 4.1%, D/EV 0.136, P/E 34; A
    'KMB',   # Kimberly-Clark — tissue/personal care staple; 19.6% OM, 4.9% yield, FCF 3.0%, D/EV 0.172, P/E 20.2; A
    'TRI',   # Thomson Reuters — legal/news data platform; 30.3% OM, 3.1% yield, FCF 4.7%, D/EV 0.072, P/E 23.4; A
    'HD',    # Home Depot — home improvement duopoly; 11.9% OM, 2.8% yield, FCF 3.0%, D/EV 0.160, P/E 23.9; B

    # BDC — Business Development Company
    'MAIN',  # Main Street Capital — BDC lending to lower middle market; internally managed (removes fee conflict vs externally managed peers); ~8.4% yield paid monthly + semi-annual special dividends; trades at ~1.55x NAV (premium unusual for BDCs, reflects management quality); ROE 14.4%; BDC structure means OM/D/E filters don't apply cleanly — judge by: NAV growth + dividend coverage + management track record

    # Dividend ETF — diversified quality basket
    'SCHD',  # Schwab U.S. Dividend Equity ETF — tracks Dow Jones U.S. Dividend 100 Index; screens for 10yr+ consecutive dividend payment + composite score (FCF/debt, ROE, yield, 5yr div growth); ~$60B+ AUM, 0.06% ER; ~3.5%+ yield, ~10% div CAGR over 10yr; partial overlap with this universe (CVX, ABBV, VZ, KO, TXN) but diverges in two ways: (1) SCHD is yield-weighted — excludes low-yield compounders like MSFT/AAPL that we track; (2) SCHD requires 10yr proven payer history — excludes recovery names (NKE, KHC, CVS) that we carry with a thesis; think of SCHD as what this universe looks like filtered for yield + dividend history — a quality subset, not a mirror; chart-only tracking (ETF)
]


# ─── MA Alignment ────────────────────────────────────────────────────────────

def ma_score(ticker):
    try:
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
    except:
        return None


# ─── Fundamentals ────────────────────────────────────────────────────────────

def get_data(ticker):
    try:
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
    except:
        return None


# ─── Grading ─────────────────────────────────────────────────────────────────

def dividend_grade(d):
    if d is None:
        return '—'
    pts = 0

    # Yield — meaningful income
    if d['div_yield'] >= 2.0: pts += 1
    if d['div_yield'] >= 3.5: pts += 1

    # FCF coverage — sustainability
    if d['fcf_yield'] > 0:              pts += 1
    if d['fcf_yield'] >= d['div_yield']: pts += 1   # FCF covers dividend

    # Margin quality
    if d['om'] >= 15: pts += 1
    if d['om'] >= 25: pts += 1

    # Debt discipline
    if d['dev'] <= 0.10: pts += 1

    # Value
    if d['pe'] and d['pe'] <= 15: pts += 1

    # Return on capital
    if d['roe'] >= 15 or d['roa'] >= 12: pts += 1

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


# ─── Main ────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    now = datetime.now().strftime('%b %d %Y  %H:%M')

    print(f'\n  Fetching MA alignment for {len(UNIVERSE)} tickers ...', flush=True)
    with ThreadPoolExecutor(max_workers=20) as ex:
        ma_results = list(ex.map(ma_score, UNIVERSE))

    price_map = {t: (p, s) for r in ma_results if r for t, p, s in [r]}

    print(f'  Fetching dividend data ...', flush=True)
    with ThreadPoolExecutor(max_workers=10) as ex:
        fund_results = {t: d for t, d in zip(UNIVERSE, ex.map(get_data, UNIVERSE))}

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

    HDR = f'  {"Ticker":<7} {"Gr":<4} {"Price":>8}  {"Yield":>6} {"FCF%":>6} {"Payout":>7} {"OM%":>6} {"D/EV":>6} {"P/E":>7}'
    DIV = f'  {"─"*7} {"─"*4} {"─"*8}  {"─"*6} {"─"*6} {"─"*7} {"─"*6} {"─"*6} {"─"*7}'

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
        return f'  {t:<7} {g:<4} {ps:>8}  {ys:>6} {fs:>6} {pays:>7} {oms:>6} {ds:>6} {pes:>7}{flag}'

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
