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

# Broad universe — S&P 500 quality names worth screening
UNIVERSE = [
    'AAPL','MSFT','GOOGL','META','NVDA','V','MA','UNH','LLY','JPM',
    'JNJ','PG','HD','COST','ABBV','MRK','TMO','ACN','AVGO','TXN',
    'QCOM','DHR','AMAT','LRCX','KLAC','MCHP','ADI','SNPS','CDNS',
    'ADBE','CRM','NOW','INTU','ORCL','FTNT','PANW','CRWD','ZS','DDOG',
    'VEEV','WDAY','TTD','PAYC',
    'BRK-B','CB','AFL','TRV','PGR','AJG','AON','WTW','CINF',
    'NVO','ISRG','EW','ALGN','IDXX','MASI','PODD','WST',
    'MCO','SPGI','MSCI','ICE','CME','CBOE','FDS','BR','NDAQ','COIN',
    'ODFL','EXPD','CHRW','XPO','JBHT','SAIA','KNSL','RLI','CASH','FICO',
    'ROL','CTAS','CPRT','ADP','PAYX','EFX','TRI','IHS','VRSK','IT',
    'MU','MPWR','MRVL','ITW','ROP','SYK','BSX','AMZN','APP',
    'MTD','MANH','FAST','MNST','POOL','NVR','DOCS','MKTX','ACGL',
    'CHD','CL','HSY','TJX','GIS','NFLX','LULU','WSM','KMB','VRTX','DECK',
    'HWM','FSLR','DUOL','PLAB',   # promoted from watchlist — pass all quality filters
    'WPM',                        # Wheaton Precious Metals — streaming model, 85% gross/65% net margin, zero debt, A+
    'VRSN',                       # VeriSign — .com/.net registry monopoly, 88% gross/68% op margin, ROE distorted by buybacks (ROA 52%), toll collector
    'CRDO',                       # Credo Technology — AI datacenter interconnect silicon (SerDes/AEC), 68% gross/35% op margin, 157% rev growth, zero debt, A+
    'MTSI',                       # MACOM Technology — analog/mixed-signal for 800G/1.6T optical datacenter interconnects; D/EV 0.02, NM 16%, ROE expanding, A
    'SLDE',                       # Slide Insurance Holdings — specialty E&S insurer, 48% op margin, 40% FCF yield, ROE 60%, 38% rev growth, 4.6x P/E, A+
    'SEZL',                       # Sezzle — fee-based BNPL pivot, 61% op margin, 92% ROE, 74% gross margin, zero debt, A+
    'INCY',                       # Incyte — Jakafi franchise pharma, zero debt, 26% op margin, 27% net margin, ROE 31%, A
    'UTHR',                       # United Therapeutics — PAH franchise (Tyvaso/Remodulin/Orenitram), zero debt, 41% OM, 40% NM, ROE 20%; xenotransplantation moonshot optionality, A+
    'EQT',                        # EQT — largest US nat gas producer, Appalachia low-cost, vertically integrated; 57% OM, 50% RevG, D/EV 0.14; powers the structures
    'RRC',                        # Range Resources — Appalachia nat gas, D/EV 0.10, 44% OM, ROE 21%; clean balance sheet, powers the structures
    'CTRA',                       # Coterra Energy — nat gas + oil, D/EV 0.13, 28% OM, 23% NM; diversified Appalachia/Permian, powers the structures
    'CF',                         # CF Industries — largest N. American ammonia/nitrogen producer; green ammonia pivot, D/EV 0.17, 34% OM, ROE 27%; foundation for structures, grades A
    'ETN',                        # Eaton Corp — electrical switchgear, circuit breakers, power distribution; sits above PWR in grid value chain, 16% OM, 14% NM, ROE 21%, D/EV 0.12
    'HEI',                        # HEICO — aviation aftermarket parts monopolies, 30yr compounder; 25% OM, 16% NM, ROE 17%, D/EV 0.052, pricing power on FAA-approved parts, A+
    'CW',                         # Curtiss-Wright — defense electronics (nuclear instrumentation, aerospace actuation); 18% OM, 14% NM, ROE 20%, D/EV 0.04, defense cycle tailwind, A
    'TW',                         # Tradeweb — electronic bond/derivatives trading platform; 46% OM, 40% NM, ROE 14%, D/EV 0.007, structural shift from voice to electronic fixed income, A+
    'ALAB',                       # Astera Labs — AI datacenter connectivity (PCIe/CXL retimers), 68% gross/35% op margin, zero debt, 200%+ rev growth, A+; promoted from watchlist
    'UBER',                       # Uber — rideshare + delivery marketplace; 14.6% OM, 15.9% NM, ROE 35%, D/EV 0.08, FCF 4.4%; platform flywheel, grades A
    'ABNB',                       # Airbnb — asset-light home-sharing marketplace; NM 19.9%, ROE 32%, D/EV 0.037, FCF solid; yfinance OM distorted by SBC/charges (true OM ~12-13%), quality real
    'ANET',                       # Arista Networks — AI/cloud datacenter networking switches; 42.7% OM, 38.3% NM, ROE 31.5%, zero debt, 35% rev growth, A+; already 4/4 weekly MA aligned at add time
    'SCHW',                       # Charles Schwab — brokerage/custody platform; 49.4% OM, 38% NM, ROE 19.1%, 15.8% rev growth; D/EV 0.465 + FCF None fail filter (structural brokerage model, not deterioration); grades A on true business quality
    'IBKR',                       # Interactive Brokers — electronic brokerage; 76.8% OM, 93% gross, ROE 23.6%, 16.8% rev growth, net cash position (D/EV -0.922); FCF None only blocker (yfinance doesn't report for brokerages); grades A+, 4/4 MA aligned at add time
    'KRYS',                       # Krystal Biotech — gene therapy dermatology (B-VEC for RDEB); 94.2% gross/46.1% OM/53.9% NM, near-zero debt, 31.9% rev growth, A+; 4/4 MA aligned at add time
    'NBIX',                       # Neurocrine Biosciences — CNS/endocrine specialist (Ingrezza); 22.8% OM, 21.6% NM, ROE 22.5%, FCF 3.8%, 42.2% rev growth, A+; 4/4 MA aligned at add time
]

# Future contenders — great businesses not yet qualifying, tracked separately
WATCHLIST = [
    'PLTR','AXON','MELI','ARM','SNOW','BILL',   # ALAB promoted to universe; CRWD removed — already in universe
    'MDB','NET','HUBS','TEAM','MKC','DPZ','GEV','CEG',
    'NEE',   # NextEra — utility debt heavy; clean energy moat, Dominion merger / long-term value
    'NRG',   # NRG Energy — de-lever play; LS Power acq doubled fleet+debt, targeting 3x net leverage, Fwd P/E 11x, yield-sensitive re-rate when 10yr < 4.0%
    'PCG',   # PG&E — regulated CA utility, NOT a datacenter play (unlike CEG/NEE/VST); wildfire liability + rate-case risk, de-lever story only
    'VST',   # Vistra — nuclear+gas deregulated moat; D/EV 0.27, qualifies as debt pays down
    'KTOS',  # Kratos — drone/defense tech; margins thin now, scaling with DoD contracts
    'CELH',  # Celsius — ROE at 8.1%, one point under threshold; margin recovery play
    'HOOD',  # Robinhood — profitability inflecting; D/EV 0.22 only blocker
    'SOFI',  # SoFi — neobank scaling; ROE 6.6% and trending right
    'UPWK',  # Upwork — freelance marketplace; D/EV 0.44 (converts) only blocker, margins/FCF solid
    'CORZ',  # Core Scientific — leadership in high-density infrastructure; BTC miner label masks AI/HPC pivot
    'CLS',   # Celestica — AI infra contract manufacturer (servers, networking), ROE 52%, D/EV 0.02, gross margin 12% blocks universe
    'MRAM',  # Everspin Technologies — MRAM chips, non-volatile fast RAM, AI edge inference angle; Op margin -18% and FCF negative blocking
    'SSNC',  # SS&C Technologies — fund admin infra, $1.28B FCF, extreme switching costs, debt 0.32 only blocker
    'SMR',   # NuScale Power — small modular reactors; pre-revenue but first-mover in licensed SMR tech
    'OKLO',  # Oklo — micro-reactors, Sam Altman-backed; nuclear theme beneath NLR ETF
    'SYM',   # Symbotic — warehouse AI robotics, Walmart-backed; revenue scaling, margins early
    'RKLB',  # Rocket Lab — only end-to-end small launch + space systems; revenue real, path to profit
    'AMSC',  # American Superconductor — power electronics, grid/defense; OpM 5.1%, one filter away
    'BMY',   # Bristol-Myers Squibb — de-lever + profit growth play; Celgene debt paydown near complete, Eliquis+Opdivo FCF, NI inflecting
    'ORLY',  # O'Reilly Auto Parts — Akre compounder; 18% OM, 14% NM, ROA 13.8% (ROE negative from 20yrs buybacks); ROA just below 15% threshold; D/EV 0.10, P/E 29x, exceptional execution
    'TDG',   # TransDigm — aerospace parts monopolist, 47% OM, 22% NM; D/EV 0.325 structural debt (leveraged rollup model, won't change); watch if debt pays down or FCF re-rates
    'FISV',  # Fiserv — payment processing + Clover POS + banking tech, extreme switching costs; ~33% OM, 15% NM; D/EV ~0.26 from First Data acquisition; ~$3-4B FCF/yr paydown, 1-2yr to threshold
    'PYPL',  # PayPal — OM 18%, NM 15%, ROE 25%, FCF 11%, P/E 7.8x; D/EV 0.30 only blocker (customer float structural); Chriss margin recovery showing in numbers
    'IOT',   # Samsara — fleet/IoT SaaS, GM 76%, zero debt, 30% RevG, FCF just turned positive; OM 1.5% blocking, 2yr runway to A/A+ as scale drives margin
    'ABBV',  # AbbVie — Allergan amortization masking strong cash earnings; FCF/Debt 28.5%, IC improving 6.3→7.8×, Skyrizi/Rinvoq replacing Humira
    'CIEN',  # Ciena — optical networking, AI datacenter interconnect tailwind; net margin 4.5% and ROE/P/E blocking, 33% rev growth
    'GFS',   # GlobalFoundries — specialty foundry (RF, automotive, IoT); 5/6 filters pass, ROE 6.8% only blocker (capital-heavy fab structure)
    'PWR',   # Quanta Services — dominant grid/electrical infrastructure contractor; OM 4% blocks now, watch for 7-8% as AI datacenter + grid modernization drives project mix higher
    'SITM',  # SiTime — MEMS precision timing chips; near-monopoly, 65% gross margin, AI datacenter + 5G tailwind; cyclical recovery in progress
    'LSCC',  # Lattice Semiconductor — low-power FPGAs, 60%+ gross margin, zero debt; AI edge + industrial; cyclical trough recovery
    'ONTO',  # Onto Innovation — advanced packaging inspection/metrology; HBM + chiplet complexity = more inspection; picks-and-shovels for AI silicon
    'AMKR',  # Amkor Technology — OSAT advanced packaging + test; HBM stacking, chiplet assembly; lower margins (services model) may block universe
    'MOD',   # Modine Manufacturing — AI datacenter thermal/cooling (heat exchangers); 47.5% rev growth, D/EV 0.037; NM 3.8% + FCF -0.7% + ROE/ROA below threshold blocking; grades B, 4/4 MA aligned at add time
    'TOST',  # Toast — restaurant POS/payments platform; ROE 22.5%, FCF 4%, rev growth 21.9%, near-zero debt; OM 6.7% + NM 6.4% blocking; grades A, 0/4 MA; strong switching costs, margins scaling
    'FIG',   # Figma — design collaboration SaaS; 79.8% gross margin, FCF 8.6%, 46.1% rev growth; OM -41.2% post-IPO investment spend blocking; grades A, 0/4 MA; Adobe tried $20B acquisition, IPO'd at $9.5B — quality business finding its level
    'KLAR',  # Klarna — BNPL/payments platform; 44.4% rev growth; OM 1.7%, FCF -23.8%, D/EV 0.391 blocking; grades B, 2/4 MA; credit cycle risk inherent to BNPL model, watch margin inflection
    'UPST',  # Upstart — AI-powered lending platform; 82.7% gross margin, 44.6% rev growth, OM 0.9% (just turning); FCF -10.1% + D/EV 0.431 (converts) + ROA 1.8% blocking; grades B, 2/4 MA; platform gross margin story, watch FCF inflection
    'COIN',  # Coinbase — digital asset exchange, crypto theme proxy; 85.5% gross margin, FCF 5.4%; OM -7.1% + rev growth -30.8% (crypto volume cycle) blocking; grades B, 0/4 MA; cyclical — watch for volume recovery + OM turning positive
]

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
        pb                = info.get('priceToBook', None)

        # FCF
        fcf               = info.get('freeCashflow', None)
        market_cap        = info.get('marketCap', 1) or 1
        fcf_yield         = (fcf / market_cap * 100) if fcf is not None and market_cap else None

        # Revenue growth
        rev_growth        = info.get('revenueGrowth', None)

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
            pb              = round(pb, 1) if pb is not None else None,
            fcf_yield       = round(fcf_yield, 1) if fcf_yield is not None else None,
            rev_growth      = round(rev_growth * 100, 1) if rev_growth is not None else None,
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
    if score >= 6: return 'A+'
    if score >= 4: return 'A'
    return 'B'

def fmt(val, suffix='', prefix=''):
    if val is None: return '<span style="color:#484f58">—</span>'
    return f"{prefix}{val}{suffix}"

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
      <th>Op%</th><th>Net%</th><th>ROE%</th><th>FCF Yld</th><th>Rev Grw</th><th>P/E</th>
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
          <td style="color:#e6edf3">{fmt(d['pe'], 'x')}{'<span style="font-size:9px;color:#8b949e">f</span>' if d.get('pe_is_forward') else ''}</td>
          <td style="font-size:11px">{blockers}</td>
        </tr>"""
    return rows

def build_html(results, watchlist=None):
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
          <td>{fmt(d['pe'], 'x')}{'<span style="font-size:9px;color:#8b949e">f</span>' if d.get('pe_is_forward') else ''}</td>
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
</style>
</head>
<body>
<h1>🔍 Quality Growth Screener</h1>
<div class="subtitle">{now}</div>
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
      <th>ROE%</th><th>FCF Yld</th><th>Rev Grw</th><th>P/E</th>
    </tr>
  </thead>
  <tbody>{rows}</tbody>
</table>
{build_watchlist_section(watchlist)}
<div class="disclaimer">
  Data sourced from Yahoo Finance via yfinance. Prices and fundamentals may be delayed or incomplete.<br>
  For informational purposes only — not financial advice. Always do your own research before making investment decisions.
</div>
</body>
</html>"""

if __name__ == '__main__':
    print(f"\n  Screening {len(UNIVERSE)} companies ...", flush=True)

    with ThreadPoolExecutor(max_workers=10) as ex:
        raw = list(ex.map(get_fundamentals, UNIVERSE))

    passed = [d for d in raw if passes_quality_filter(d)]
    for d in passed:
        d['grade'] = quality_grade(d)
    passed.sort(key=lambda x: (0 if x['grade']=='A+' else 1 if x['grade']=='A' else 2, -(x['market_cap_b'] or 0)))

    print(f"  ✅  {len(passed)} companies passed filters")
    print(f"\n  Fetching {len(WATCHLIST)} watchlist contenders ...", flush=True)

    with ThreadPoolExecutor(max_workers=10) as ex:
        watch_raw = list(ex.map(get_fundamentals, WATCHLIST))
    watch_raw = [d for d in watch_raw if d is not None]
    watch_raw.sort(key=lambda x: -(x['market_cap_b'] or 0))

    print(f"  👀  {len(watch_raw)} watchlist entries fetched\n")

    html = build_html(passed, watch_raw)
    path = os.path.expanduser('~/quality_screener.html')
    with open(path, 'w') as f:
        f.write(html)

    print(f"  Saved → {path}")
    webbrowser.open(f'file://{path}')
