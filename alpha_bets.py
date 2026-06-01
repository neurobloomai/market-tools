"""
Alpha Bets Screener — US Companies
=====================================
Finds mispriced companies with an identifiable, resolving catalyst.

Alpha comes from being right when consensus is wrong — not just good companies
but good companies mispriced for a SPECIFIC, DATABLE reason that's clearing.

Six alpha sources:
  1. GAAP/FCF divergence   — real earnings >> reported (amortization/impairments)
  2. Interest savings       — mechanical NI boost calculable from current paydown rate
  3. Fear discount          — price far below 52w high with intact FCF
  4. Cheap on FCF           — P/FCF < 12 while business quality holds
  5. Credit upgrade path    — D/EV approaching investment-grade threshold
  6. Self-funding flywheel  — FCF yield >> estimated borrowing cost

Alpha Score (0–12):
  FCF/NI ratio > 2×                  +3   GAAP massively understating real earnings
  FCF/NI ratio > 1.5×                +2
  Est. interest savings > 5% NI      +2   mechanical EPS lift next year
  Price < 65% of 52w high            +2   fear discount
  P/FCF < 10                         +2   cheap on real cash
  P/FCF 10–15                        +1
  D/EV 0.20–0.38 (upgrade zone)      +1   approaching credit upgrade threshold
  FCF yield > 10%                    +1   flywheel speed

Categories:
  High Conviction  ≥ 8  — multiple alpha sources converging, timing visible
  Developing       5–7  — 1–2 clear sources, catalyst forming
  Speculative      3–4  — single source, timing uncertain

Data: Yahoo Finance via yfinance
Run:  python alpha_bets.py
"""

import yfinance as yf
import warnings, os, webbrowser
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
warnings.filterwarnings('ignore')

# ── Universe ──────────────────────────────────────────────────────────────────
# Broader than de-lever screener — includes GAAP/FCF divergence plays,
# fear-discount names, telecom de-lever, gaming, media, and spinoffs

UNIVERSE = [
    # Pharma — GAAP/FCF divergence from acquisition amortization
    'ABBV', 'BMY', 'PFE', 'AMGN', 'GILD', 'BIIB', 'VTRS', 'MRK', 'REGN',

    # Telecom de-lever — massive debt, FCF machines, interest savings compounding
    'T', 'VZ', 'CHTR', 'LUMN',

    # Media — GAAP impairments masking real FCF
    'WBD', 'FOX', 'FOXA', 'DIS', 'NFLX',

    # Industrials — spinoffs + post-M&A
    'GE', 'GEV', 'FTV', 'OTIS', 'CARR', 'EMR', 'HON', 'ETN', 'ROP',
    'HII', 'TXT', 'LHX', 'RTX', 'NOC',

    # Healthcare — managed care overhang + services
    'HCA', 'UNH', 'ELV', 'CI',

    # Financial data / exchanges
    'ICE', 'SPGI', 'MSCI', 'CME', 'NDAQ',

    # Consumer
    'MCD', 'SBUX', 'DPZ', 'YUM', 'QSR',
    'DG', 'DLTR', 'TGT', 'WMT',

    # Gaming — de-lever + FCF recovery post-covid build
    'CZR', 'MGM', 'LVS', 'WYNN',

    # Tech with debt
    'DELL', 'HPQ', 'HPE', 'CSCO', 'QCOM', 'AVGO', 'INTC',

    # Energy (E&P, not refiners)
    'COP', 'OXY', 'DVN', 'EOG',

    # Real estate / infrastructure
    'VICI', 'AMT', 'CCI',

    # Waste / infrastructure (durable FCF)
    'WM', 'RSG',

    # Specialty
    'ICE', 'FICO', 'VRSK', 'CPRT',
    'UBER', 'LYFT',
]
UNIVERSE = list(dict.fromkeys(UNIVERSE))   # deduplicate, preserve order

# Industries to exclude — commodity-cycle FCF not structural
EXCLUDED_INDUSTRIES = {
    'Oil & Gas Refining & Marketing',
    'Oil & Gas Integrated',
}

# ── Data fetch ────────────────────────────────────────────────────────────────

def safe_div(a, b):
    try:
        return a / b if a and b and b != 0 else None
    except Exception:
        return None


def get_alpha_data(ticker):
    try:
        t    = yf.Ticker(ticker)
        info = t.info
        if not info or 'marketCap' not in info:
            return None

        market_cap       = info.get('marketCap', 1) or 1
        total_debt       = info.get('totalDebt', 0) or 0
        enterprise_value = info.get('enterpriseValue') or None
        fcf              = info.get('freeCashflow') or None
        ni               = info.get('netIncomeToCommon') or None
        interest_exp     = None

        # Pull interest expense and NI from annual financials for accuracy
        try:
            fin = t.financials
            if fin is not None and not fin.empty:
                for idx in fin.index:
                    if 'interest expense' in str(idx).lower():
                        interest_exp = abs(fin.loc[idx].iloc[0]) if fin.loc[idx].iloc[0] else None
                    if ni is None and 'net income' in str(idx).lower():
                        ni = fin.loc[idx].iloc[0]
        except Exception:
            pass

        # Derived metrics
        debt_to_ev       = safe_div(total_debt, enterprise_value)
        fcf_yield        = safe_div(fcf, market_cap) * 100 if fcf and market_cap else None
        p_fcf            = safe_div(market_cap, fcf) if fcf and fcf > 0 else None
        fcf_ni_ratio     = safe_div(fcf, ni) if fcf and ni and ni > 0 else None

        # Average borrowing rate = interest expense / total debt
        avg_rate         = safe_div(interest_exp, total_debt) if interest_exp and total_debt else None

        # Estimated annual interest savings if they pay down at FCF rate × 50%
        # Conservative — assumes half of FCF goes to debt reduction
        est_paydown      = (fcf * 0.5) if fcf and fcf > 0 else None
        est_int_savings  = (est_paydown * avg_rate) if est_paydown and avg_rate else None
        # As % of current NI — how much mechanical EPS lift next year?
        savings_pct_ni   = safe_div(est_int_savings, abs(ni)) * 100 if est_int_savings and ni else None

        # Fear discount: price vs 52w high
        price            = info.get('currentPrice') or info.get('regularMarketPrice')
        high_52w         = info.get('fiftyTwoWeekHigh')
        fear_discount    = safe_div(price, high_52w) if price and high_52w else None  # <0.65 = fear

        return dict(
            ticker          = ticker,
            name            = info.get('shortName', ticker),
            sector          = info.get('sector', ''),
            industry        = info.get('industry', ''),
            price           = round(price, 2) if price else None,
            market_cap_b    = round(market_cap / 1e9, 1),
            debt_to_ev      = round(debt_to_ev, 3) if debt_to_ev is not None else None,
            fcf_yield       = round(fcf_yield, 1) if fcf_yield is not None else None,
            p_fcf           = round(p_fcf, 1) if p_fcf is not None else None,
            fcf_ni_ratio    = round(fcf_ni_ratio, 2) if fcf_ni_ratio is not None else None,
            avg_rate_pct    = round(avg_rate * 100, 1) if avg_rate is not None else None,
            savings_pct_ni  = round(savings_pct_ni, 1) if savings_pct_ni is not None else None,
            fear_discount   = round(fear_discount, 2) if fear_discount is not None else None,
            high_52w        = round(high_52w, 2) if high_52w else None,
            rev_growth      = round(info.get('revenueGrowth', 0) * 100, 1) if info.get('revenueGrowth') else None,
            net_margin      = round(info.get('profitMargins', 0) * 100, 1) if info.get('profitMargins') else None,
            pe_fwd          = round(info.get('forwardPE'), 1) if info.get('forwardPE') and isinstance(info.get('forwardPE'), (int, float)) else None,
            roe             = round(info.get('returnOnEquity', 0) * 100, 1) if info.get('returnOnEquity') else None,
        )
    except Exception as e:
        print(f"  ⚠ {ticker}: {e}")
        return None


# ── Filters ───────────────────────────────────────────────────────────────────

def passes_filter(d):
    """Minimum bar: must have FCF, must not be a commodity-cycle name."""
    if d is None: return False
    if d.get('industry') in EXCLUDED_INDUSTRIES: return False
    if d['fcf_yield'] is None or d['fcf_yield'] < 3.0: return False
    if d['market_cap_b'] < 1.0: return False   # no micro-caps
    return True


# ── Alpha Score ───────────────────────────────────────────────────────────────

def alpha_score(d):
    score = 0
    flags = []

    # 1. GAAP/FCF divergence — FCF significantly above reported NI
    if d['fcf_ni_ratio'] is not None:
        if d['fcf_ni_ratio'] > 2.0:
            score += 3
            flags.append(f"GAAP gap {d['fcf_ni_ratio']}× (FCF >> NI)")
        elif d['fcf_ni_ratio'] > 1.5:
            score += 2
            flags.append(f"GAAP gap {d['fcf_ni_ratio']}×")

    # 2. Mechanical interest savings on the horizon
    if d['savings_pct_ni'] is not None and d['savings_pct_ni'] > 5:
        score += 2
        flags.append(f"~{d['savings_pct_ni']:.0f}% NI boost from interest savings")
    elif d['savings_pct_ni'] is not None and d['savings_pct_ni'] > 2:
        score += 1
        flags.append(f"~{d['savings_pct_ni']:.0f}% NI boost est.")

    # 3. Fear discount — price well below 52w high (specific overhang)
    if d['fear_discount'] is not None:
        if d['fear_discount'] < 0.65:
            score += 2
            flags.append(f"Fear: {d['fear_discount']*100:.0f}% of 52w high")
        elif d['fear_discount'] < 0.80:
            score += 1
            flags.append(f"Discount: {d['fear_discount']*100:.0f}% of 52w high")

    # 4. Cheap on real cash (P/FCF)
    if d['p_fcf'] is not None:
        if d['p_fcf'] < 10:
            score += 2
            flags.append(f"P/FCF {d['p_fcf']}×")
        elif d['p_fcf'] < 15:
            score += 1
            flags.append(f"P/FCF {d['p_fcf']}×")

    # 5. Credit upgrade proximity (D/EV in upgrade zone)
    if d['debt_to_ev'] is not None and 0.20 <= d['debt_to_ev'] <= 0.38:
        score += 1
        flags.append(f"D/EV {d['debt_to_ev']} → upgrade zone")

    # 6. Flywheel speed
    if d['fcf_yield'] is not None and d['fcf_yield'] > 10:
        score += 1
        flags.append(f"FCF yield {d['fcf_yield']}%")

    return score, flags


def category(score):
    if score >= 8: return 'High Conviction'
    if score >= 5: return 'Developing'
    if score >= 3: return 'Speculative'
    return None


# ── HTML ──────────────────────────────────────────────────────────────────────

def fmt(val, suffix='', prefix=''):
    if val is None:
        return '<span style="color:#484f58">—</span>'
    return f"{prefix}{val}{suffix}"


def color_val(val, good_above, warn_above=None, reverse=False):
    if val is None:
        return '<span style="color:#484f58">—</span>'
    if not reverse:
        if val >= good_above:
            c = '#3fb950'
        elif warn_above and val >= warn_above:
            c = '#ffa657'
        else:
            c = '#f85149'
    else:
        if val <= good_above:
            c = '#3fb950'
        elif warn_above and val <= warn_above:
            c = '#ffa657'
        else:
            c = '#f85149'
    return f'<span style="color:{c}">{val}</span>'


def build_html(results):
    now = datetime.now().strftime('%B %d, %Y  %H:%M')

    high_conv  = [d for d in results if d['category'] == 'High Conviction']
    developing = [d for d in results if d['category'] == 'Developing']
    spec       = [d for d in results if d['category'] == 'Speculative']

    def row_html(d):
        cat = d['category']
        cat_cls = {
            'High Conviction': 'cat-high',
            'Developing':      'cat-dev',
            'Speculative':     'cat-spec',
        }[cat]
        fear_str = f"{d['fear_discount']*100:.0f}%" if d['fear_discount'] else '—'
        fear_color = '#f85149' if (d['fear_discount'] and d['fear_discount'] < 0.65) else \
                     '#ffa657' if (d['fear_discount'] and d['fear_discount'] < 0.80) else '#8b949e'
        flags_html = '<br>'.join(
            f'<span style="color:#bc8cff;font-size:10px">▸ {f}</span>'
            for f in d['flags']
        ) if d['flags'] else '<span style="color:#484f58">—</span>'
        return f"""<tr>
          <td class="ticker">{d['ticker']}</td>
          <td style="color:#8b949e;font-size:11px">{d['name'][:22]}</td>
          <td style="color:#8b949e;font-size:11px">{d['sector'][:14]}</td>
          <td style="color:#e6edf3">${fmt(d['price'])}</td>
          <td style="color:#e6edf3">${fmt(d['market_cap_b'])}B</td>
          <td class="grade-col"><span class="badge {cat_cls}">{cat}</span></td>
          <td style="color:#58a6ff;font-weight:700">{d['alpha_score']}/12</td>
          <td>{color_val(d['fcf_yield'], 10, 5)}{'%' if d['fcf_yield'] else ''}</td>
          <td>{color_val(d['p_fcf'], 0, 15, reverse=True) if d['p_fcf'] else '<span style="color:#484f58">—</span>'}{'×' if d['p_fcf'] else ''}</td>
          <td>{color_val(d['fcf_ni_ratio'], 2.0, 1.5)}{'×' if d['fcf_ni_ratio'] else ''}</td>
          <td><span style="color:{fear_color}">{fear_str}</span></td>
          <td style="color:#8b949e">{fmt(d['debt_to_ev'])}</td>
          <td style="color:#8b949e">{fmt(d['savings_pct_ni'], '%')}</td>
          <td style="color:#8b949e">{fmt(d['pe_fwd'], '×')}</td>
          <td style="line-height:1.6">{flags_html}</td>
        </tr>"""

    rows = ''
    for section, label, sub, color in [
        (high_conv,  '🎯 High Conviction — Multiple alpha sources converging',
         'GAAP gap + fear discount + cheap on FCF + catalyst visible', '#f0883e'),
        (developing, '🔭 Developing — 1–2 clear alpha sources, catalyst forming',
         'At least one strong signal with improving trajectory', '#58a6ff'),
        (spec,       '🎲 Speculative — Single source, timing uncertain',
         'Alpha source identified but catalyst timing unclear', '#8b949e'),
    ]:
        if section:
            rows += f'''<tr><td colspan="15" style="padding:20px 10px 6px;font-size:13px;font-weight:700;color:{color};border-bottom:2px solid #21262d">
              {label}
              <span style="color:#8b949e;font-size:10px;font-weight:400;margin-left:12px">{sub}</span>
            </td></tr>'''
            for d in section:
                rows += row_html(d)

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Alpha Bets Screener — {now}</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: 'SF Mono','Fira Code',monospace; background: #0d1117; color: #e6edf3; padding: 28px; font-size: 12px; }}
  h1 {{ font-size: 18px; font-weight: 700; color: #bc8cff; margin-bottom: 4px; }}
  .subtitle {{ color: #8b949e; margin-bottom: 8px; font-size: 11px; }}
  .summary {{ color: #8b949e; margin-bottom: 20px; font-size: 12px; }}
  .summary span {{ color: #e6edf3; font-weight: 700; }}
  table {{ width: 100%; border-collapse: collapse; }}
  th {{ text-align: left; padding: 8px 10px; color: #8b949e; font-weight: 500;
        border-bottom: 2px solid #21262d; font-size: 10px; text-transform: uppercase; letter-spacing: .05em; }}
  td {{ padding: 7px 10px; border-bottom: 1px solid #161b22; vertical-align: top; }}
  tr:hover td {{ background: #161b22; }}
  .ticker {{ font-weight: 700; color: #e6edf3; }}
  .badge {{ font-size: 10px; font-weight: 700; padding: 2px 7px; border-radius: 3px; white-space: nowrap; }}
  .cat-high {{ background: #2d1f54; color: #bc8cff; }}
  .cat-dev  {{ background: #1c2e4a; color: #58a6ff; }}
  .cat-spec {{ background: #1e2a1e; color: #8b949e; }}
  .thesis {{ background: #161b22; border: 1px solid #21262d; border-radius: 8px; padding: 16px; margin-bottom: 20px; }}
  .thesis h2 {{ font-size: 11px; color: #8b949e; margin-bottom: 10px; text-transform: uppercase; letter-spacing: .08em; }}
  .thesis-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }}
  .thesis-item {{ font-size: 11px; color: #8b949e; line-height: 1.6; }}
  .thesis-item strong {{ color: #e6edf3; display: block; margin-bottom: 2px; }}
  .thesis-item span {{ color: #bc8cff; }}
  .disclaimer {{ color: #484f58; font-size: 10px; margin-top: 24px; border-top: 1px solid #21262d; padding-top: 8px; line-height: 1.8; }}
</style>
</head>
<body>
<h1>🎯 Alpha Bets Screener</h1>
<div class="subtitle">{now} · Mispriced companies with identifiable, resolving catalysts</div>
<div class="summary">
  <span>{len(results)}</span> alpha candidates —
  <span>{len(high_conv)}</span> High Conviction &nbsp;·&nbsp;
  <span>{len(developing)}</span> Developing &nbsp;·&nbsp;
  <span>{len(spec)}</span> Speculative
</div>

<div class="thesis">
  <h2>Alpha Framework</h2>
  <div class="thesis-grid">
    <div class="thesis-item">
      <strong>What creates alpha</strong>
      Being right when consensus is wrong. Not just good companies — companies
      mispriced for a <span>specific, datable reason</span> that's clearing.
    </div>
    <div class="thesis-item">
      <strong>Six alpha sources scored</strong>
      <span>GAAP/FCF gap</span> · <span>Interest savings</span> (mechanical EPS lift) ·
      <span>Fear discount</span> · <span>Cheap on FCF</span> ·
      <span>Credit upgrade path</span> · <span>Flywheel speed</span>
    </div>
    <div class="thesis-item">
      <strong>Score (0–12)</strong>
      GAAP gap >2× <span>+3</span> · Int savings >5% NI <span>+2</span> ·
      Fear <65% high <span>+2</span> · P/FCF <10 <span>+2</span> ·
      Upgrade zone <span>+1</span> · FCF >10% <span>+1</span>
    </div>
  </div>
</div>

<table>
  <thead>
    <tr>
      <th>Ticker</th><th>Name</th><th>Sector</th><th>Price</th><th>Mkt Cap</th>
      <th>Category</th><th>Score</th><th>FCF Yld</th><th>P/FCF</th>
      <th>FCF/NI</th><th>vs 52wH</th><th>D/EV</th><th>Int Svgs</th><th>Fwd P/E</th>
      <th>Alpha Flags</th>
    </tr>
  </thead>
  <tbody>{rows}</tbody>
</table>

<div class="disclaimer">
  FCF/NI = free cash flow ÷ net income — values >1.5× suggest GAAP significantly understates real earnings.<br>
  vs 52wH = current price as % of 52-week high — lower values indicate fear/overhang priced in.<br>
  Int Svgs = estimated annual interest expense savings (50% of FCF → debt paydown) as % of current NI.<br>
  Data sourced from Yahoo Finance via yfinance. For informational purposes only — not financial advice.
</div>
</body>
</html>"""


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    print(f"\n  Alpha Bets Screener — {len(UNIVERSE)} companies", flush=True)
    print("  (fetching data — takes ~60s)\n", flush=True)

    with ThreadPoolExecutor(max_workers=8) as ex:
        raw = list(ex.map(get_alpha_data, UNIVERSE))

    filtered = [d for d in raw if passes_filter(d)]

    results = []
    for d in filtered:
        score, flags = alpha_score(d)
        cat = category(score)
        if cat is None:
            continue
        d['alpha_score'] = score
        d['flags']       = flags
        d['category']    = cat
        results.append(d)

    results.sort(key=lambda x: (
        0 if x['category'] == 'High Conviction' else
        1 if x['category'] == 'Developing' else 2,
        -x['alpha_score'],
    ))

    high_conv  = sum(1 for d in results if d['category'] == 'High Conviction')
    developing = sum(1 for d in results if d['category'] == 'Developing')
    spec       = sum(1 for d in results if d['category'] == 'Speculative')

    print(f"  🎯  {len(results)} alpha candidates")
    print(f"      {high_conv} High Conviction  ·  {developing} Developing  ·  {spec} Speculative\n")

    for cat_name in ['High Conviction', 'Developing']:
        group = [d for d in results if d['category'] == cat_name]
        if group:
            print(f"  {cat_name}:")
            for d in group:
                print(f"    {d['ticker']:<6} {d['alpha_score']:>2}/12  {', '.join(d['flags'][:2])}")
        print()

    html = build_html(results)
    path = os.path.expanduser('~/alpha_bets.html')
    with open(path, 'w') as f:
        f.write(html)
    print(f"  Saved → {path}")
    webbrowser.open(f'file://{path}')
