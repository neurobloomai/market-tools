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
import warnings, os, webbrowser
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
    'KEC.NS','KALPATPOWR.NS','GRINDWELL.NS',

    # Defense — Make in India moment
    'HAL.NS','BEL.NS','MTARTECH.NS','DATAPATTNS.NS','PARAS.NS',

    # Electronics Manufacturing — PLI beneficiaries
    'DIXON.NS','KAYNES.NS',

    # Auto & Components
    'BAJAJ-AUTO.NS','EICHERMOT.NS','BHARATFORG.NS','MOTHERSUMI.NS',
    'BALKRISIND.NS','TIINDIA.NS',

    # Energy & Power Transition
    'NTPC.NS','POWERGRID.NS','TATAPOWER.NS','TORNTPOWER.NS',
    'WAAREEENER.NS',

    # Specialty Chemicals — China+1 beneficiary
    'SRF.NS','NAVINFLUOR.NS','AARTIIND.NS','DEEPAKNTR.NS','PIIND.NS',

    # Pharma & CDMO
    'SUNPHARMA.NS','DIVISLAB.NS','CIPLA.NS','DRREDDY.NS','LAURUSLABS.NS',
    'AUROPHARMA.NS','MANKIND.NS',

    # IT Services
    'TCS.NS','INFY.NS','HCLTECH.NS','WIPRO.NS','PERSISTENT.NS',
    'COFORGE.NS','MPHASIS.NS',

    # Financials
    'HDFCBANK.NS','ICICIBANK.NS','BAJFINANCE.NS','KOTAKBANK.NS',
    'SBIN.NS','CHOLAFIN.NS','MUTHOOTFIN.NS',

    # Consumer & FMCG
    'HINDUNILVR.NS','NESTLEIND.NS','BRITANNIA.NS','DABUR.NS','MARICO.NS',
    'TITAN.NS','PAGEIND.NS','TATACONSUM.NS',

    # Infrastructure & Logistics
    'ADANIPORTS.NS','CONCOR.NS',

    # Capital Markets & Wealth — India's affluence theme
    'CDSL.NS','BSE.NS','360ONE.NS',

    # Retail — aspirational consumption
    'TRENT.NS',
]

# Watchlist — high quality but not yet qualifying
WATCHLIST = [
    'ZOMATO.NS',      # not yet profitable on all metrics
    'NYKAA.NS',       # profitability still building
    'POLICYBZR.NS',   # high growth, early stage
    'DELHIVERY.NS',   # logistics, margins building
    'IRCTC.NS',       # monopoly but valuation often stretched
    'ADANIENT.NS',    # conglomerate, debt heavy
    'ARE&M.NS',       # Amara Raja Energy — Op margin just under threshold, clean balance sheet
    'ADANIGREEN.NS',  # Adani Green — heavy capex, debt, P/E stretched but 57% op margin
    'SWIGGY.NS',      # Swiggy — food delivery, profitability inflecting, duopoly with Zomato
    'IXIGO.NS',       # ixigo — travel-tech, recently listed, margins building
]

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

        _pe_raw          = info.get('trailingPE', None)
        pe               = None if not isinstance(_pe_raw, (int, float)) else _pe_raw
        pb               = info.get('priceToBook', None)

        fcf              = info.get('freeCashflow', None)
        market_cap       = info.get('marketCap', 1) or 1
        fcf_yield        = (fcf / market_cap * 100) if fcf and market_cap else None
        rev_growth       = info.get('revenueGrowth', None)

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
            pb              = round(pb, 1) if pb is not None else None,
            fcf_yield       = round(fcf_yield, 1) if fcf_yield is not None else None,
            rev_growth      = round(rev_growth * 100, 1) if rev_growth is not None else None,
        )
    except Exception as e:
        print(f'  ⚠ {ticker}: {e}')
        return None

def passes_quality_filter(d):
    if d is None: return False
    if d['debt_to_ev'] is None: return False
    if d['debt_to_ev'] > 0.20: return False          # slightly wider for India — capital-intensive sectors
    if d['operating_margin'] is None or d['operating_margin'] < 8: return False   # 8% vs 10% for US
    if d['net_margin'] is None or d['net_margin'] < 5: return False
    roe_ok = d['roe'] is not None and d['roe'] >= 10
    roa_ok = d['roa'] is not None and d['roa'] >= 10
    if not roe_ok and not roa_ok: return False
    if d['fcf_yield'] is None or d['fcf_yield'] < 0: return False
    if d['pe'] is not None and d['pe'] > 80: return False   # Indian market P/E tends to be lower
    return True

def failing_filters(d):
    if d is None: return [('No data', '—', '—')]
    fails = []
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
        if d['operating_margin'] and d['operating_margin'] >= 10: score += 1
    elif is_it:
        if d['gross_margin'] and d['gross_margin'] >= 30: score += 1
        if d['operating_margin'] and d['operating_margin'] >= 20: score += 1
    else:
        if d['gross_margin'] and d['gross_margin'] >= 40: score += 1
        if d['operating_margin'] and d['operating_margin'] >= 15: score += 1

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

def pct_color(val, good_above=0):
    if val is None: return '<span style="color:#484f58">—</span>'
    c = '#3fb950' if val >= good_above else '#f85149'
    return f'<span style="color:{c}">{val}%</span>'

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
          <td style="color:#e6edf3">{fmt(d['pe'], 'x')}</td>
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
      <th>Blocking Filters</th>
    </tr>
  </thead>
  <tbody>{rows}</tbody>
</table>"""

def build_html(results, watchlist=None):
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
          <td>{fmt(d['pe'], 'x')}</td>
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
    </tr>
  </thead>
  <tbody>{rows}</tbody>
</table>
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

    passed = [d for d in raw if passes_quality_filter(d)]
    for d in passed:
        d['grade'] = quality_grade(d)
    passed.sort(key=lambda x: (0 if x['grade']=='A+' else 1 if x['grade']=='A' else 2, x['debt_to_ev'] or 1))

    print(f'  ✅  {len(passed)} companies passed filters')
    print(f'\n  Fetching {len(WATCHLIST)} watchlist contenders ...', flush=True)

    with ThreadPoolExecutor(max_workers=10) as ex:
        watch_raw = list(ex.map(get_fundamentals, WATCHLIST))
    watch_raw = [d for d in watch_raw if d is not None]

    print(f'  👀  {len(watch_raw)} watchlist entries fetched\n')

    html = build_html(passed, watch_raw)
    path = os.path.expanduser('~/india_screener.html')
    with open(path, 'w') as f:
        f.write(html)

    print(f'  Saved → {path}')
    webbrowser.open(f'file://{path}')
