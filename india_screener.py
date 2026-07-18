"""
India Quality Growth Screener
Universe: Quality names across India's key growth themes —
          Manufacturing, Defense, Capital Goods, Energy, Pharma/CDMO,
          Specialty Chemicals, Financials, IT, Auto, Consumer
Run: python india_screener.py

Data: Yahoo Finance via yfinance (NSE .NS tickers)
Disclaimer: For informational purposes only. Not financial advice.
"""

import yfinance as yf
import warnings, os, webbrowser, math
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
warnings.filterwarnings('ignore')

try:
    from zoneinfo import ZoneInfo
    def _ist_now(): return datetime.now(ZoneInfo('Asia/Kolkata'))
except ImportError:
    from datetime import timezone, timedelta
    def _ist_now():
        return datetime.now(timezone(timedelta(hours=5, minutes=30)))

# --- Universe ---
UNIVERSE = [
    # Capital Goods & Industrials — the backbone of India's buildout
    'LT.NS','SIEMENS.NS','ABB.NS','HAVELLS.NS','THERMAX.NS','CUMMINSIND.NS',
    'KEC.NS','KPIL.NS','GRINDWELL.NS','POLYCAB.NS',

    # Defense — Make in India moment
    'HAL.NS','BEL.NS','MTARTECH.NS','DATAPATTNS.NS','PARAS.NS',

    # Electronics Manufacturing — PLI beneficiaries
    # DIXON and KAYNES moved to watchlist — EMS margin model and capex phase respectively

    # Auto & Components
    'BAJAJ-AUTO.NS','EICHERMOT.NS','FORCEMOT.NS','BHARATFORG.NS','MOTHERSON.NS',
    'BALKRISIND.NS','TIINDIA.NS',

    # Energy & Power Transition
    'NTPC.NS','POWERGRID.NS','TATAPOWER.NS','TORNTPOWER.NS',
    'WAAREEENER.NS',

    # Specialty Chemicals — China+1 beneficiary
    'SRF.NS','NAVINFLUOR.NS','VINATIORGA.NS','AARTIIND.NS','DEEPAKNTR.NS','PIIND.NS',

    # Pharma, CDMO & Diagnostics
    'SUNPHARMA.NS','DIVISLAB.NS','CIPLA.NS','DRREDDY.NS','LAURUSLABS.NS',
    'AUROPHARMA.NS','MANKIND.NS','LALPATHLAB.NS',

    # IT Services & Engineering R&D
    'TCS.NS','INFY.NS','HCLTECH.NS','WIPRO.NS','PERSISTENT.NS',
    'COFORGE.NS','MPHASIS.NS','TATAELXSI.NS','LTTS.NS','KPITTECH.NS',

    # Financials & Asset Management
    'HDFCBANK.NS','ICICIBANK.NS','BAJFINANCE.NS','KOTAKBANK.NS',
    'SBIN.NS','CHOLAFIN.NS','MUTHOOTFIN.NS','HDFCAMC.NS',

    # Consumer & FMCG
    'HINDUNILVR.NS','NESTLEIND.NS','BRITANNIA.NS','DABUR.NS','MARICO.NS',
    'TITAN.NS','PAGEIND.NS','TATACONSUM.NS',
    'ASIANPAINT.NS',  # A+ (7/7) — 50%+ decorative paints market share, pricing power + 3-tier distribution moat; OM 16%, ROE 21%, D/E 0.18, FCF positive, RevG 11%; 4/4 MA aligned slope +209
    'PIDILITIND.NS',  # Pidilite Industries — Fevicol monopoly + construction chemicals (Dr. Fixit, M-seal); 55% gross margin, ROE 23.5%, zero debt, A+; same distribution moat as Asian Paints, deeply embedded in every construction project in India

    # Infrastructure & Logistics
    'ADANIPORTS.NS','CONCOR.NS','IRCTC.NS',

    # Capital Markets & Wealth — India's affluence theme
    'CDSL.NS','BSE.NS','CAMS.NS','ANGELONE.NS',

    # Retail — aspirational consumption
    'TRENT.NS','DMART.NS',
]

# Watchlist — high quality but not yet qualifying
WATCHLIST = [
    'ETERNAL.NS',     # Eternal (formerly Zomato) — food delivery + quick commerce; profitability inflecting
    'NYKAA.NS',       # profitability still building
    'POLICYBZR.NS',   # high growth, early stage
    'DELHIVERY.NS',   # logistics, margins building
    # IRCTC.NS promoted to universe — OM 26%, NM 27%, ROE 35%, P/E 30x
    'ADANIENT.NS',    # conglomerate, debt heavy
    'ARE&M.NS',       # Amara Raja Energy — Op margin just under threshold, clean balance sheet
    'ADANIGREEN.NS',  # Adani Green — heavy capex, debt, P/E stretched but 57% op margin
    'SWIGGY.NS',      # Swiggy — food delivery, profitability inflecting, duopoly with Zomato
    'IXIGO.NS',       # ixigo — travel-tech, recently listed, margins building
    'DIXON.NS',       # Dixon Technologies — EMS/contract manufacturing, ROE 37% but OM ~3% by design (assembler model)
    'KAYNES.NS',      # Kaynes Technology — defense/semi electronics, OM 11% but FCF -10% (heavy capex ramp) + ROE just under threshold
    'APOLLOHOSP.NS',  # Apollo Hospitals — healthcare brand growing well, FCF inconsistent due to hospital capex
    # ANGELONE.NS promoted to universe — A+, OM 32%, ROE 15.5%, D/EV 0.200, passes financial sector gate
    '360ONE.NS',      # 360 ONE WAM (formerly IIFL Wealth) — HNI/ultra-HNI wealth + asset mgmt; OM 57.7%, NM 27.2%; ROE 14.4% just below 15% financial threshold; D/EV 0.262; near-miss, watch for ROE crossing 15%
    'BAJAJHFL.NS',    # Bajaj Housing Finance — fast-growing NBFC, recently listed; ROE building, financial sector rules apply; 2-3yr story
    'ASTRAL.NS',      # Astral Ltd — pipes/adhesives/bathing compounder; OM ~13%, ROE ~18%, low debt; consistent but may grade B by filter thresholds
    'SUPREMEIND.NS',  # Supreme Industries — largest plastic pipes/products company; zero debt, RevG 16.5%, ROE 16.1%; grade B (NM 8.5%, GrossM 32% thinner than POLYCAB); gate: NM crossing 10% + ROE sustaining above 18% as CPVC/composite pipe mix grows
    'ANANDRATHI.NS',  # Anand Rathi Wealth — wealth management, asset-light; OM 40%, NM 32%, ROE 47%, RevG 48%; PE ~82x (just above 80x threshold); watch for earnings growth to bring PE sub-80
    'HSCL.NS',        # Himadri Speciality Chemical — pivoting to battery anode materials + LFP cathodes for EV supply chain; OM 20%, NM 16%, ROE 18%; D/E 16 + FCF -0.4% blocking (heavy capex ramp); watch for FCF turning positive + debt reduction as capacity ramps
    'BHARTIARTL.NS',  # Bharti Airtel — telecom duopoly (Jio + Airtel); OM 32.2%, NM 12.7%, ROE 19.4%, FCF ₹610B, RevG 15.7%; D/E 0.997 only blocker (structural 5G spectrum + tower capex — same read as VZ, not deteriorating); 3/4 MA; A (6/7)
    'MARUTI.NS',      # Maruti Suzuki — 50% India car market share, Suzuki tech, largest dealer network; B (3/7); OM 8.4%/NM 8%/GrossM 28% thin by auto OEM design (not a flaw — same read as COST); near-zero D/E 0.001, RevG 28%, FCF real; 3/4 MA; watch for margin improvement
    'M&M.NS',         # Mahindra & Mahindra — farm equipment + SUV (Scorpio/XUV) + EV; OM 16.4%, ROE 18.8%, RevG 31%; D/E 1.25 inflated by Mahindra Finance NBFC subsidiary (standalone auto/farm D/E much lower); NM 8.5% + GrossM 39% just below threshold; B (4/7); 2/4 MA broken — wait for recovery
    'INDUSTOWER.NS',  # Indus Towers — largest India tower infra company; leases tower space to Airtel/Jio/Vi; permanent passive infrastructure, recurring tenancy rental, 5G rollout = more equipment per tower; Airtel ~42% shareholder; blocker: Vodafone Idea dues (Vi owes thousands of crores unpaid) + potential Vi collapse risk (25-30% revenue exposure); watch for Vi situation resolving — either stabilises or exits cleanly; business model A+ in isolation
    # --- SIP universe additions — scan to grade before promoting ---
    'MCX.NS',         # Multi Commodity Exchange — India's commodity derivatives toll booth (CME analog); every gold/silver/crude/agri futures trade pays MCX; structural monopoly in commodity derivatives; SIP candidate pending quality grade confirmation
    'KFINTECH.NS',    # KFin Technologies — second MF registrar after CAMS (~30% market share); same structural model as CAMS; also diversified into international fund admin + corporate registry; SIP candidate pending quality grade confirmation
    'CRISIL.NS',      # CRISIL — India's dominant credit rating agency, S&P Global subsidiary; SPGI analog for India; every corporate bond needs a CRISIL rating; data + analytics division; SIP candidate pending quality grade confirmation
    'ICRA.NS',        # ICRA — Moody's India subsidiary (~52% Moody's stake); MCO analog for India; CRISIL + ICRA form India's rating duopoly; SIP candidate pending quality grade confirmation
]

# Future radar — too early for weekly scanning, revisit after 2-3 quarters
# Not fetched, not graded. Documented here so the thesis isn't lost.
# Rule: if the blocker is the business model (survival risk, no path to profit), it belongs here not WATCHLIST
FUTURE_RADAR = {
    'OLAELEC.NS':  'Ola Electric — EV two-wheeler, high growth but deeply loss-making; competitive market (Hero, Ather, TVS iQube, Bajaj Chetak all competing) = structural pressure not just cycle; path to profitability unclear; gate to watchlist: OM turning positive sustained + FCF inflection + competitive position stabilising',
    'RELIANCE.NS': 'Reliance Industries — conglomerate discount masking two A-grade businesses: Jio (telecom/digital platform, duopoly with Airtel, growing ARPU) + Reliance Retail (largest Indian retailer); O2C (oil-to-chemicals) is the margin drag blending quality metrics to C grade today; thesis: Jio IPO / Retail listing / O2C demerger expected 2026-2028 — revisit when structure clarifies; gate to watchlist: demerger announced OR Jio/Retail listed separately',
}

# SIP candidates — high-quality toll-booth businesses on India's financial system growth.
# Buy regularly via SIP regardless of short-term price. Not traded — owned.
# Common thread: asset-light, fee/infrastructure income, no balance sheet risk, compound with India's financial deepening.
SIP_WATCHLIST = {
    # --- Mutual Fund Infrastructure ---
    'HDFCAMC.NS':  'HDFC Asset Management — second largest AMC by AUM; fee income as % of AUM, asset-light, 50%+ OM, near-zero debt; every SIP rupee into Indian markets grows their AUM; financialisation of Indian household savings (shift from gold/real estate to MFs) is early innings; own the toll booth on India\'s mutual fund industry',
    'CAMS.NS':     'Computer Age Management Services — processes ~70% of all India MF transactions (SIPs, redemptions, folios) across all AMCs; more defensive than any single AMC — revenue grows with industry AUM regardless of which AMC wins; pure infrastructure toll, zero market risk; A+ in screener',
    'KFINTECH.NS': 'KFin Technologies — second MF registrar/transfer agent after CAMS (~30% market share vs CAMS ~70%); same structural model, same SIP inflow tailwind; more diversified than CAMS into international fund admin and corporate registry; runner-up to CAMS but compounding with the same wave',
    # --- Depository Infrastructure ---
    'CDSL.NS':     'Central Depository Services — every demat account and dematerialised security in India runs through CDSL or NSDL; India adding ~3M demat accounts/month; account maintenance + transaction fees compound with India\'s investor base growth; depository infrastructure is permanent; A+ in screener',
    # --- Exchange Infrastructure ---
    'BSE.NS':      'BSE (Bombay Stock Exchange) — India\'s NDAQ analog; toll on every BSE trade, every SME listing, every currency derivative contract; dominant in currency derivatives and SME listings; gaining options market share; A+ in screener; own the exchange, not the stocks on it',
    'MCX.NS':      'Multi Commodity Exchange — India\'s dominant commodity derivatives exchange (CME analog); every gold/silver/crude/agri futures contract pays MCX; structural monopoly in commodity derivatives; commodity demand growth + financial inclusion in India compounds the fee base',
    # --- Credit Rating / Data ---
    'CRISIL.NS':   'CRISIL — India\'s dominant credit rating agency, S&P Global subsidiary; every corporate bond in India needs a rating; recurring fees from every rated entity; data + analytics division (CRISIL Research) adds subscription revenue; SPGI analog for India; regulatory entrenchment makes it near-impossible to displace',
    'ICRA.NS':     'ICRA — Moody\'s India subsidiary (Moody\'s ~52% stake); credit ratings for corporate bonds, bank loans, structured finance, municipal bonds; research + analytics division; CRISIL + ICRA form India\'s rating duopoly — exact mirror of S&P + Moody\'s globally; MCO analog for India; every rated entity pays recurring surveillance fees',
}

def get_fundamentals(ticker):
    try:
        t    = yf.Ticker(ticker)
        info = t.info
        if not info or 'marketCap' not in info:
            return None

        total_debt       = info.get('totalDebt', 0) or 0
        enterprise_value = info.get('enterpriseValue') or None
        debt_to_ev       = total_debt / enterprise_value if enterprise_value else None

        gross_margin     = info.get('grossMargins', None)
        operating_margin = info.get('operatingMargins', None)
        net_margin       = info.get('profitMargins', None)
        roe              = info.get('returnOnEquity', None)
        roa              = info.get('returnOnAssets', None)

        _pe_raw       = info.get('trailingPE', None)
        _fwd_pe       = info.get('forwardPE', None)
        _pe_raw       = None if isinstance(_pe_raw, float) and math.isinf(_pe_raw) else _pe_raw
        pe            = None if not isinstance(_pe_raw, (int, float)) else _pe_raw
        pe_is_forward = False
        if pe is None or pe > 100:
            _fwd_valid = isinstance(_fwd_pe, (int, float)) and not math.isinf(_fwd_pe) and 5 < _fwd_pe <= 500
            if _fwd_valid:
                pe            = _fwd_pe
                pe_is_forward = True
        pb            = info.get('priceToBook', None)

        fcf              = info.get('freeCashflow', None)
        market_cap       = info.get('marketCap', 1) or 1
        fcf_yield        = (fcf / market_cap * 100) if fcf and market_cap else None
        rev_growth       = info.get('revenueGrowth', None)

        # Price vs MA200d
        ma200d           = info.get('twoHundredDayAverage', None)
        _price_raw       = info.get('currentPrice') or info.get('regularMarketPrice')
        price_vs_ma200   = round((_price_raw / ma200d - 1) * 100, 1) if ma200d and _price_raw else None

        # EPS FY trend
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
            name            = info.get('shortName', ticker).replace('.NS',''),
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
        print(f'  ⚠ {ticker}: {e}')
        return None

def passes_quality_filter(d):
    if d is None: return False
    sector = d.get('sector', '')
    is_financial = 'Financial' in sector

    if not is_financial:
        # D/EV not meaningful for banks/NBFCs — they borrow to lend by design
        if d['debt_to_ev'] is None: return False
        if d['debt_to_ev'] > 0.20: return False

    if d['operating_margin'] is None or d['operating_margin'] < 8: return False
    if d['net_margin'] is None or d['net_margin'] < 5: return False

    roe_ok = d['roe'] is not None and d['roe'] >= 10
    roa_ok = d['roa'] is not None and d['roa'] >= 10
    if not roe_ok and not roa_ok: return False

    if is_financial:
        # ROE ≥ 15% replaces FCF as quality gate for banks/NBFCs
        if d['roe'] is None or d['roe'] < 15: return False
    else:
        if d['fcf_yield'] is None:
            high_growth   = d['rev_growth'] is not None and d['rev_growth'] >= 50
            strong_margin = d['net_margin'] is not None and d['net_margin'] >= 10
            if not (high_growth and strong_margin):
                return False
        elif d['fcf_yield'] < 0:
            return False

    if d['pe'] is not None and d['pe'] > 80: return False
    return True

def failing_filters(d):
    if d is None: return [('No data', '—', '—')]
    sector = d.get('sector', '')
    is_financial = 'Financial' in sector
    fails = []

    if not is_financial:
        if d['debt_to_ev'] is None:
            fails.append(('Debt/EV', 'missing', '≤ 0.20'))
        elif d['debt_to_ev'] > 0.20:
            fails.append(('Debt/EV', f"{d['debt_to_ev']}", '≤ 0.20'))

    if d['operating_margin'] is None or d['operating_margin'] < 8:
        fails.append(('Op Margin', f"{d['operating_margin']}%" if d['operating_margin'] is not None else 'missing', '≥ 8%'))
    if d['net_margin'] is None or d['net_margin'] < 5:
        fails.append(('Net Margin', f"{d['net_margin']}%" if d['net_margin'] is not None else 'missing', '≥ 5%'))

    roe_ok = d['roe'] is not None and d['roe'] >= 10
    roa_ok = d['roa'] is not None and d['roa'] >= 10
    if not roe_ok and not roa_ok:
        fails.append(('ROE/ROA', f"ROE {d['roe']}% / ROA {d['roa']}%", '≥ 10%'))

    if is_financial:
        if d['roe'] is None or d['roe'] < 15:
            fails.append(('ROE (financial)', f"{d['roe']}%" if d['roe'] is not None else 'missing', '≥ 15%'))
    else:
        if d['fcf_yield'] is None or d['fcf_yield'] < 0:
            fails.append(('FCF Yield', f"{d['fcf_yield']}%" if d['fcf_yield'] is not None else 'missing', '> 0%'))

    if d['pe'] is not None and d['pe'] > 80:
        fails.append(('P/E', f"{d['pe']}x", '≤ 80x'))
    return fails if fails else [('Passes all filters', '—', '—')]

def quality_grade(d):
    sector = d.get('sector', '')
    is_financial = 'Financial' in sector
    is_it = 'Technology' in sector or 'Information' in sector

    score = 0
    if d['debt_to_ev'] is not None and d['debt_to_ev'] <= 0.05: score += 2
    elif d['debt_to_ev'] is not None and d['debt_to_ev'] <= 0.20: score += 1

    if is_financial:
        if d['roe'] and d['roe'] >= 15: score += 2
        if d['operating_margin'] and d['operating_margin'] >= 10: score += 2
    elif is_it:
        if d['gross_margin'] and d['gross_margin'] >= 30: score += 1
        if d['operating_margin'] and d['operating_margin'] >= 20: score += 2
    else:
        if d['gross_margin'] and d['gross_margin'] >= 40: score += 1
        if d['operating_margin'] and d['operating_margin'] >= 15: score += 2

    if d['net_margin'] and d['net_margin'] >= 12: score += 1
    if d['roe'] and d['roe'] >= 18: score += 1
    if d['fcf_yield'] and d['fcf_yield'] >= 2: score += 1
    if d['rev_growth'] and d['rev_growth'] >= 12: score += 1

    if score >= 6: return 'A+'
    if score >= 4: return 'A'
    return 'B'

def fmt(val, suffix='', prefix=''):
    if val is None: return '<span style="color:#484f58">—</span>'
    return f'{prefix}{val}{suffix}'

def pe_html(d):
    pe  = d.get('pe')
    fwd = d.get('fwd_pe')
    if pe is None:
        return '<span style="color:#484f58">—</span>'
    if d.get('pe_is_forward') or (pe > 50 and fwd is not None):
        show = fwd if (not d.get('pe_is_forward') and fwd is not None) else pe
        return f'{show:.0f}x<span style="font-size:9px;color:#8b949e">f</span>'
    return f'{pe:.1f}x'

def pct_color(val, good_above=0):
    if val is None: return '<span style="color:#484f58">—</span>'
    c = '#3fb950' if val >= good_above else '#f85149'
    return f'<span style="color:{c}">{val}%</span>'

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
    """Weekly dual confirmation: RSI-14 + MACD histogram divergence must agree."""
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

        MIN_SWING = 0.0075
        MAX_SWING = 0.15

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

        rsi     = calc_rsi(closes, 14).dropna()
        rsi_sig = None
        if len(rsi) >= 5:
            idx     = rsi.index
            rsi_sig = _divergence(rsi.values, highs.loc[idx].values, lows.loc[idx].values, len(rsi))

        ema12         = closes.ewm(span=12, adjust=False).mean()
        ema26         = closes.ewm(span=26, adjust=False).mean()
        histo         = (ema12 - ema26 - (ema12 - ema26).ewm(span=9, adjust=False).mean()).dropna()
        macd_sig      = None
        if len(histo) >= 5:
            idx      = histo.index
            macd_sig = _divergence(histo.values, highs.loc[idx].values, lows.loc[idx].values, len(histo))

        if rsi_sig and macd_sig and rsi_sig == macd_sig:
            return (rsi_sig, 'RSI+MACD')
        return None
    except Exception:
        return None

def entry_zone(d):
    """Composite margin-of-safety signal: GREEN / YELLOW / RED."""
    pma200 = d.get('price_vs_ma200')
    fy0    = d.get('fy0_growth')
    grade  = d.get('grade', 'B')
    fpe    = d.get('fwd_pe') or d.get('pe')

    if pma200 is None:
        base = 1
    elif pma200 <= 5:
        base = 2
    elif pma200 <= 20:
        base = 1
    else:
        base = 0

    eps_mod   = (+1 if fy0 is not None and fy0 > 15
                 else -1 if fy0 is not None and fy0 < 0
                 else 0)
    grade_mod = +1 if grade == 'A+' else (0 if grade == 'A' else -1)
    pe_pen    = -1 if (fpe and fpe > 50 and (fy0 is None or fy0 < 20)) else 0

    total = base + eps_mod + grade_mod + pe_pen
    if total >= 3: return 'green'
    if total >= 1: return 'yellow'
    return 'red'

def entry_html(d):
    zone  = entry_zone(d)
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
    c0     = '#3fb950' if g0 >= 5 else ('#e3b341' if g0 >= 0 else '#f85149')
    prefix = '⚠ ' if g0 < 0 else ''
    g0_str = f'{prefix}{g0:+.0f}%'
    if g1 is not None:
        c1 = '#3fb950' if g1 >= 5 else ('#e3b341' if g1 >= 0 else '#f85149')
        return (f'<span style="color:{c0};font-size:11px">{g0_str}</span>'
                f' <span style="color:{c1};font-size:10px">/{g1:+.0f}%</span>')
    return f'<span style="color:{c0};font-size:11px">{g0_str}</span>'

def signal_html(sig):
    if sig is None: return '<span style="color:#484f58">—</span>'
    direction, source = sig
    color = '#3fb950' if direction == 'bull' else '#f85149'
    arrow = '⬆' if direction == 'bull' else '⬇'
    return (f'<span style="color:{color};font-weight:700">{arrow} {direction}</span>'
            f'<span style="color:#484f58;font-size:9px"> {source}</span>')

def build_watchlist_section(watchlist):
    if not watchlist: return ''
    rows = ''
    for d in watchlist:
        if d is None: continue
        fails = failing_filters(d)
        blockers = ' &nbsp;·&nbsp; '.join(
            f'<span class="blocker">{f[0]}</span> <span class="blocker-val">{f[1]}</span> <span class="blocker-threshold">→ {f[2]}</span>'
            for f in fails
        )
        rows += f"""<tr>
          <td class="ticker">{d['ticker'].replace('.NS','')}</td>
          <td style="color:#8b949e;font-size:11px">{d['name'][:22]}</td>
          <td style="color:#8b949e;font-size:11px">{d['sector'][:15]}</td>
          <td>₹{fmt(d['price'])}</td>
          <td>{pct_color(d['operating_margin'], 8)}</td>
          <td>{pct_color(d['net_margin'], 5)}</td>
          <td>{pct_color(d['roe'], 10)}</td>
          <td>{pct_color(d['fcf_yield'], 0)}</td>
          <td>{pct_color(d['rev_growth'], 12)}</td>
          <td style="color:#e6edf3">{pe_html(d)}</td>
          <td>{eps_trend_html(d)}</td>
          <td>{entry_html(d)}</td>
          <td style="font-size:11px">{blockers}</td>
        </tr>"""
    return f"""
<div class="section-header">👀 Watchlist — Future Contenders</div>
<div class="section-sub">Tracking high-quality businesses not yet qualifying — with exact blockers shown.</div>
<table>
  <thead>
    <tr>
      <th>Ticker</th><th>Name</th><th>Sector</th><th>Price</th>
      <th>Op%</th><th>Net%</th><th>ROE%</th><th>FCF Yld</th><th>Rev Grw</th><th>P/E</th>
      <th>EPS FY</th><th>Entry</th><th>Blocking Filters</th>
    </tr>
  </thead>
  <tbody>{rows}</tbody>
</table>"""

def build_universe_failing_section(failing):
    if not failing: return ''
    rows = ''
    for d in sorted(failing, key=lambda x: x['ticker']):
        fails = failing_filters(d)
        blockers = ' &nbsp;·&nbsp; '.join(
            f'<span class="blocker">{f[0]}</span> <span class="blocker-val">{f[1]}</span> <span class="blocker-threshold">→ {f[2]}</span>'
            for f in fails
        )
        rows += f"""<tr>
          <td class="ticker">{d['ticker'].replace('.NS','')}</td>
          <td style="color:#8b949e;font-size:11px">{d['name'][:22]}</td>
          <td style="color:#8b949e;font-size:11px">{d['sector'][:15]}</td>
          <td>₹{fmt(d['price'])}</td>
          <td>{pct_color(d['operating_margin'], 8)}</td>
          <td>{pct_color(d['net_margin'], 5)}</td>
          <td>{pct_color(d['roe'], 10)}</td>
          <td>{pct_color(d['fcf_yield'], 0)}</td>
          <td>{pct_color(d['rev_growth'], 12)}</td>
          <td style="color:#e6edf3">{pe_html(d)}</td>
          <td>{eps_trend_html(d)}</td>
          <td>{entry_html(d)}</td>
          <td style="font-size:11px">{blockers}</td>
        </tr>"""
    return f"""
<div class="section-header">🔍 Universe — Not Yet Qualifying</div>
<div class="section-sub">In the universe but blocked by one or more filters — good businesses to watch for improvement.</div>
<table>
  <thead>
    <tr>
      <th>Ticker</th><th>Name</th><th>Sector</th><th>Price</th>
      <th>Op%</th><th>Net%</th><th>ROE%</th><th>FCF Yld</th><th>Rev Grw</th><th>P/E</th>
      <th>EPS FY</th><th>Entry</th><th>Blocking Filters</th>
    </tr>
  </thead>
  <tbody>{rows}</tbody>
</table>"""

def build_html(results, watchlist=None, universe_failing=None):
    now   = _ist_now().strftime('%B %d, %Y  %H:%M IST')
    rows  = ''
    for d in results:
        grade     = d['grade']
        grade_cls = 'grade-aplus' if grade == 'A+' else ('grade-a' if grade == 'A' else 'grade-b')
        rows += f"""<tr>
          <td class="ticker">{d['ticker'].replace('.NS','')}</td>
          <td style="color:#8b949e;font-size:11px">{d['name'][:22]}</td>
          <td style="color:#8b949e;font-size:11px">{d['sector'][:15]}</td>
          <td>₹{fmt(d['price'])}</td>
          <td>₹{fmt(d['market_cap_b'])}B</td>
          <td class="grade-col"><span class="badge {grade_cls}">{grade}</span></td>
          <td>{fmt(d['debt_to_ev'])}</td>
          <td>{pct_color(d['gross_margin'], 30)}</td>
          <td>{pct_color(d['operating_margin'], 12)}</td>
          <td>{pct_color(d['net_margin'], 8)}</td>
          <td>{pct_color(d['roe'], 15)}</td>
          <td>{pct_color(d['fcf_yield'], 2)}</td>
          <td>{pct_color(d['rev_growth'], 12)}</td>
          <td>{pe_html(d)}</td>
          <td>{eps_trend_html(d)}</td>
          <td>{entry_html(d)}</td>
          <td>{signal_html(d.get('tech_signal'))}</td>
        </tr>"""

    aplus = sum(1 for d in results if d['grade'] == 'A+')
    a     = sum(1 for d in results if d['grade'] == 'A')

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>India Quality Screener — {now}</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: 'SF Mono','Fira Code',monospace; background: #0d1117; color: #e6edf3; padding: 28px; font-size: 12px; }}
  h1 {{ font-size: 18px; font-weight: 700; color: #f0883e; margin-bottom: 4px; }}
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
  .criteria-item span {{ color: #f0883e; }}
  .section-header {{ font-size: 15px; font-weight: 700; color: #f0883e; margin: 40px 0 6px; }}
  .section-sub {{ color: #8b949e; font-size: 11px; margin-bottom: 16px; }}
  .blocker {{ color: #f85149; font-weight: 600; }}
  .blocker-val {{ color: #ffa657; }}
  .blocker-threshold {{ color: #484f58; }}
  .disclaimer {{ color: #484f58; font-size: 10px; margin-top: 24px; border-top: 1px solid #21262d; padding-top: 8px; line-height: 1.8; }}
</style>
</head>
<body>
<h1>🇮🇳 India Quality Growth Screener</h1>
<div class="subtitle">{now}</div>
<div class="summary">
  Found <span>{len(results)}</span> companies passing all filters —
  <span>{aplus}</span> A+ &nbsp;·&nbsp; <span>{a}</span> A
</div>

<div class="criteria">
  <h2>Filter Criteria (India-calibrated)</h2>
  <div class="criteria-grid">
    <div class="criteria-item">Debt/EV <span>≤ 0.20</span></div>
    <div class="criteria-item">Operating Margin <span>≥ 8%</span></div>
    <div class="criteria-item">Net Margin <span>≥ 5%</span></div>
    <div class="criteria-item">ROE or ROA <span>≥ 10%</span></div>
    <div class="criteria-item">FCF Yield <span>> 0%</span></div>
    <div class="criteria-item">P/E <span>≤ 80x</span></div>
    <div class="criteria-item">A+: Debt/EV <span>≤ 0.05</span> + quality score</div>
    <div class="criteria-item">Sector-aware grading for financials & IT</div>
  </div>
</div>

<table>
  <thead>
    <tr>
      <th>Ticker</th><th>Name</th><th>Sector</th><th>Price</th><th>Mkt Cap</th>
      <th>Grade</th><th>Debt/EV</th><th>Gross%</th><th>Op%</th><th>Net%</th>
      <th>ROE%</th><th>FCF Yld</th><th>Rev Grw</th><th>P/E</th>
      <th>EPS FY</th><th>Entry</th><th>Signal (wk)</th>
    </tr>
  </thead>
  <tbody>{rows}</tbody>
</table>
{build_universe_failing_section(universe_failing)}
{build_watchlist_section(watchlist)}
<div class="disclaimer">
  Data sourced from NSE via Yahoo Finance / yfinance. Prices and fundamentals may be delayed or incomplete.<br>
  For informational purposes only — not financial advice. Always do your own research before making investment decisions.
</div>
</body>
</html>"""

if __name__ == '__main__':
    print(f'\n  Screening {len(UNIVERSE)} Indian companies ...', flush=True)

    with ThreadPoolExecutor(max_workers=10) as ex:
        raw = list(ex.map(get_fundamentals, UNIVERSE))

    fetched = [d for d in raw if d is not None]
    fetch_rate = len(fetched) / len(UNIVERSE) * 100
    print(f'  Fetched {len(fetched)}/{len(UNIVERSE)} tickers ({fetch_rate:.0f}%)', flush=True)

    # Guard: if fewer than 40% of tickers returned data, likely rate-limited — abort
    # rather than overwrite last good output with a blank page
    if fetch_rate < 40:
        print(f'  ⛔ Fetch rate {fetch_rate:.0f}% < 40% — likely rate-limited. Keeping existing HTML.')
        import sys; sys.exit(0)

    passed  = [d for d in fetched if passes_quality_filter(d)]
    failing = [d for d in fetched if not passes_quality_filter(d)]
    for d in passed:
        d['grade'] = quality_grade(d)

    # Weekly signal — A/A+ names only (fetch-heavy; skip B)
    top_grade = [d for d in passed if d['grade'] in ('A+', 'A')]
    if top_grade:
        print(f'  Fetching weekly signals for {len(top_grade)} A/A+ names ...', flush=True)
        with ThreadPoolExecutor(max_workers=8) as ex:
            sigs = list(ex.map(get_tech_signal, [d['ticker'] for d in top_grade]))
        for d, sig in zip(top_grade, sigs):
            d['tech_signal'] = sig

    # Sort: grade bucket → declining EPS last within bucket → debt_to_ev
    def _sort_key(x):
        grade_rank = 0 if x['grade'] == 'A+' else (1 if x['grade'] == 'A' else 2)
        fy0        = x.get('fy0_growth')
        eps_rank   = 1 if (fy0 is not None and fy0 < 0) else 0  # declining EPS last
        return (grade_rank, eps_rank, x['debt_to_ev'] or 1)
    passed.sort(key=_sort_key)

    print(f'  ✅  {len(passed)} companies passed filters  ({len(failing)} in universe not yet qualifying)')
    print(f'\n  Fetching {len(WATCHLIST)} watchlist contenders ...', flush=True)

    with ThreadPoolExecutor(max_workers=10) as ex:
        watch_raw = list(ex.map(get_fundamentals, WATCHLIST))
    watch_raw = [d for d in watch_raw if d is not None]

    print(f'  👀  {len(watch_raw)} watchlist entries fetched\n')

    now  = datetime.utcnow().strftime('%b %d %Y  %H:%M UTC')
    html = build_html(passed, watch_raw, universe_failing=failing)

    import subprocess, os as _os
    out_path   = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), 'india_screener.html')
    commit_msg = f'india_screener: {now}'
    is_ci      = _os.environ.get('CI') == 'true'

    with open(out_path, 'w') as f:
        f.write(html)
    print(f'  Saved → {out_path}')

    if not is_ci:
        webbrowser.open(f'file://{out_path}')

    try:
        repo = _os.path.dirname(out_path)
        subprocess.run(['git', 'stash', '--include-untracked'], cwd=repo, capture_output=True)
        subprocess.run(['git', 'pull', '--rebase', 'origin', 'main'], cwd=repo, check=True, capture_output=True)
        with open(out_path, 'w') as f:
            f.write(html)
        subprocess.run(['git', 'add',    'india_screener.html'], cwd=repo, check=True, capture_output=True)
        subprocess.run(['git', 'commit', '-m', commit_msg],      cwd=repo, check=True, capture_output=True)
        subprocess.run(['git', 'push'],                           cwd=repo, check=True, capture_output=True)
        print(f'  Pushed → GitHub  ({commit_msg})')
    except subprocess.CalledProcessError as e:
        with open(out_path, 'w') as f:   # ensure disk always has good content
            f.write(html)
        print(f'  Git push skipped: {e.stderr.decode() if e.stderr else e}')
