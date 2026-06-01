"""
De-lever + Profit Growth Screener
===================================
Finds companies paying down debt toward D/EV ≤ 0.20 while profits grow.

The thesis: Lower debt → lower interest expense → net income grows mechanically,
even before revenue tailwinds. Best companies have both.

Filters:
  ▸ D/EV currently 0.15–0.60  (has debt, heading down — not already clean)
  ▸ FCF yield > 4%             (generating cash to pay debt down)
  ▸ Net income positive        (not a turnaround, a de-lever story)
  ▸ Revenue growth > 2%        (organic growth on top)
  ▸ Net income growing YoY     (profit trajectory confirmed)
  ▸ Interest coverage > 3×     (can service the debt comfortably)

Momentum score (0–10):
  FCF yield > 7%               +2  (fast debt paydown possible)
  FCF yield > 4%               +1
  Net income growing > 10%     +2
  Net income growing > 0%      +1
  Interest coverage improving  +2
  Revenue growth > 5%          +1
  Gross margin stable/up       +1
  D/EV 0.15–0.30 (close)      +1  (already near target)

Categories:
  Strong   ≥ 7   — clear path to sub-0.20, profits accelerating
  On Track 5–6   — solid trajectory, watch closely
  Watch    3–4   — direction right but pace uncertain

Data: Yahoo Finance via yfinance
Run:  python delever_screener.py
"""

import yfinance as yf
import warnings, os, webbrowser
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
warnings.filterwarnings('ignore')

# ── Universe ──────────────────────────────────────────────────────────────────
# Companies with meaningful debt AND strong FCF AND profit trajectory
# Deliberately excludes companies already at D/EV < 0.15 (see quality screener)

UNIVERSE = [
    # Pharma post-acquisition (biggest de-lever stories)
    'ABBV', 'BMY', 'PFE', 'AMGN', 'MRK', 'GILD', 'BIIB', 'REGN',
    'VTRS',  # Viatris — textbook debt paydown ($18B→$12B), FCF solid; GAAP losses are non-cash impairments

    # Industrials post-M&A
    'PH', 'HON', 'ETN', 'GE', 'ROK', 'FTV', 'CARR', 'OTIS', 'EMR',
    'ITW', 'DOV', 'XYL', 'GNRC', 'AME', 'ROP',

    # Energy FCF machines (pay down aggressively when prices hold)
    'COP', 'DVN', 'FANG', 'OXY', 'EOG', 'MPC', 'PSX', 'VLO',
    'HES', 'CTRA', 'APA',

    # Defense (stable government cash flows, de-lever post-acquisition)
    'RTX', 'LMT', 'NOC', 'GD', 'LHX', 'HII', 'TXT',

    # Healthcare services
    'HCA', 'UNH', 'ELV', 'CI', 'HUM', 'CNC', 'MOH',

    # Financial data / exchanges (moderate debt, strong FCF)
    'MSCI', 'ICE', 'SPGI', 'CME', 'NDAQ',

    # Consumer / Retail (strong operators with moderate leverage)
    'MCD', 'SBUX', 'YUM', 'QSR', 'DPZ',
    'TGT', 'WMT', 'DG', 'DLTR',

    # Media de-lever (aggressive stated commitments)
    'WBD', 'PARA', 'FOX', 'FOXA',

    # Tech with some debt
    'DELL', 'HPQ', 'HPE', 'CSCO', 'QCOM', 'AVGO',

    # Waste / infrastructure (durable FCF)
    'WM', 'RSG', 'CWST',

    # Specialty / other
    'VICI', 'O',             # REITs with manageable debt
    'CTAS', 'CPRT', 'FICO', 'VRSK',   # already near-clean but worth tracking
    'MTZ', 'PWR', 'PRIM',  # infrastructure buildout
    'DKNG',                # path to profitability, debt watch
    'UBER', 'LYFT',        # FCF inflecting
    'ABNB',                # near net cash
]

# ── Data fetch ────────────────────────────────────────────────────────────────

def safe_divide(a, b):
    try:
        if a and b and b != 0:
            return a / b
        return None
    except Exception:
        return None


def get_yoy_metrics(ticker_obj):
    """Pull net income growth and interest coverage trend from annual financials."""
    try:
        fin = ticker_obj.financials
        if fin is None or fin.empty or fin.shape[1] < 2:
            return None, None, None, None

        def find_row(keywords):
            for idx in fin.index:
                if any(k.lower() in str(idx).lower() for k in keywords):
                    return fin.loc[idx]
            return None

        ni_row   = find_row(['net income'])
        ebit_row = find_row(['ebit', 'operating income'])
        int_row  = find_row(['interest expense'])
        gp_row   = find_row(['gross profit'])
        rev_row  = find_row(['total revenue', 'revenue'])

        ni_growth = None
        if ni_row is not None:
            ni_curr = ni_row.iloc[0]
            ni_prev = ni_row.iloc[1]
            if ni_prev and ni_prev != 0 and ni_curr is not None:
                ni_growth = (ni_curr - ni_prev) / abs(ni_prev) * 100

        ic_curr = ic_prev = None
        if ebit_row is not None and int_row is not None:
            e_curr = ebit_row.iloc[0]
            e_prev = ebit_row.iloc[1]
            i_curr = abs(int_row.iloc[0]) if int_row.iloc[0] else None
            i_prev = abs(int_row.iloc[1]) if int_row.iloc[1] else None
            ic_curr = safe_divide(e_curr, i_curr)
            ic_prev = safe_divide(e_prev, i_prev)

        gm_improving = None
        if gp_row is not None and rev_row is not None:
            gm_curr = safe_divide(gp_row.iloc[0], rev_row.iloc[0])
            gm_prev = safe_divide(gp_row.iloc[1], rev_row.iloc[1])
            if gm_curr is not None and gm_prev is not None:
                gm_improving = gm_curr >= (gm_prev - 0.005)   # allow 0.5pp tolerance

        return ni_growth, ic_curr, ic_prev, gm_improving

    except Exception:
        return None, None, None, None


def get_fundamentals(ticker):
    try:
        t    = yf.Ticker(ticker)
        info = t.info
        if not info or 'marketCap' not in info:
            return None

        total_debt       = info.get('totalDebt', 0) or 0
        enterprise_value = info.get('enterpriseValue') or None
        market_cap       = info.get('marketCap', 1) or 1
        debt_to_ev       = safe_divide(total_debt, enterprise_value)

        fcf              = info.get('freeCashflow', None)
        fcf_yield        = (fcf / market_cap * 100) if fcf and market_cap else None
        fcf_to_debt      = safe_divide(fcf, total_debt)   # years-to-payoff proxy (inverted)

        gross_margin     = info.get('grossMargins', None)
        operating_margin = info.get('operatingMargins', None)
        net_margin       = info.get('profitMargins', None)
        rev_growth       = info.get('revenueGrowth', None)
        roe              = info.get('returnOnEquity', None)
        pe               = info.get('trailingPE', None)
        if not isinstance(pe, (int, float)):
            pe = None

        ni_growth, ic_curr, ic_prev, gm_improving = get_yoy_metrics(t)
        # Cap NI growth display — turnaround years (near-zero base) produce extreme %
        if ni_growth is not None and abs(ni_growth) > 500:
            ni_growth = 500.0 if ni_growth > 0 else -500.0
        ic_improving = (ic_curr is not None and ic_prev is not None and ic_curr > ic_prev)

        return dict(
            ticker           = ticker,
            name             = info.get('shortName', ticker),
            sector           = info.get('sector', ''),
            industry         = info.get('industry', ''),
            price            = info.get('currentPrice', None),
            market_cap_b     = round(market_cap / 1e9, 1),
            debt_to_ev       = round(debt_to_ev, 3) if debt_to_ev is not None else None,
            fcf_yield        = round(fcf_yield, 1) if fcf_yield is not None else None,
            fcf_to_debt_pct  = round(fcf_to_debt * 100, 1) if fcf_to_debt is not None else None,
            gross_margin     = round(gross_margin * 100, 1) if gross_margin is not None else None,
            operating_margin = round(operating_margin * 100, 1) if operating_margin is not None else None,
            net_margin       = round(net_margin * 100, 1) if net_margin is not None else None,
            rev_growth       = round(rev_growth * 100, 1) if rev_growth is not None else None,
            ni_growth        = round(ni_growth, 1) if ni_growth is not None else None,
            ic_curr          = round(ic_curr, 1) if ic_curr is not None else None,
            ic_prev          = round(ic_prev, 1) if ic_prev is not None else None,
            ic_improving     = ic_improving,
            gm_improving     = gm_improving,
            roe              = round(roe * 100, 1) if roe is not None else None,
            pe               = round(pe, 1) if pe is not None else None,
        )
    except Exception as e:
        print(f"  ⚠ {ticker}: {e}")
        return None


# ── Sector exclusions ─────────────────────────────────────────────────────────
# Refiners and commodity processors: FCF driven by crack spreads / commodity cycles,
# not structural debt paydown. Debt trends follow capex cycles, not business quality.
EXCLUDED_INDUSTRIES = {
    'Oil & Gas Refining & Marketing',
    'Oil & Gas Integrated',
}


# ── Filters ───────────────────────────────────────────────────────────────────

def passes_filter(d):
    if d is None:
        return False
    # Exclude pure refiners — crack-spread FCF ≠ structural de-lever
    if d.get('industry') in EXCLUDED_INDUSTRIES:
        return False
    # Must have debt — this is a de-lever screener, not quality screener
    if d['debt_to_ev'] is None:
        return False
    if not (0.15 <= d['debt_to_ev'] <= 0.60):
        return False
    # Must generate FCF to pay it down
    if d['fcf_yield'] is None or d['fcf_yield'] < 4.0:
        return False
    # Must be profitable
    if d['net_margin'] is None or d['net_margin'] < 3.0:
        return False
    # Must have revenue growth
    if d['rev_growth'] is None or d['rev_growth'] < 2.0:
        return False
    # Net income must be broadly stable or growing
    # -2% tolerance absorbs non-cash acquisition amortization (e.g. ABBV/Allergan)
    # while still excluding companies with genuine profit deterioration
    if d['ni_growth'] is None or d['ni_growth'] < -2.0:
        return False
    # Interest coverage must be comfortable
    if d['ic_curr'] is not None and d['ic_curr'] < 3.0:
        return False
    return True


def momentum_score(d):
    score = 0

    # FCF generation speed
    if d['fcf_yield'] is not None:
        if d['fcf_yield'] > 7:
            score += 2
        elif d['fcf_yield'] > 4:
            score += 1

    # Net income trajectory
    if d['ni_growth'] is not None:
        if d['ni_growth'] > 10:
            score += 2
        elif d['ni_growth'] > 0:
            score += 1

    # Interest coverage improving (debt servicing getting easier)
    if d['ic_improving']:
        score += 2

    # Revenue growth (organic tailwind on top of de-lever)
    if d['rev_growth'] is not None and d['rev_growth'] > 5:
        score += 1

    # Gross margin holding/improving (operating quality)
    if d['gm_improving']:
        score += 1

    # Already close to target (D/EV 0.15–0.30)
    if d['debt_to_ev'] is not None and d['debt_to_ev'] <= 0.30:
        score += 1

    return score


def category(score):
    if score >= 7: return 'Strong'
    if score >= 5: return 'On Track'
    return 'Watch'


def passes_monitor(d):
    """Monitor Closely: FCF + debt paydown confirmed but GAAP NI distorted by non-cash items.
    Fails the main NI filter but FCF/Debt ratio proves real cash generation.
    Excludes commodity cycles (oil E&P) and genuine margin deterioration (managed care)."""
    if d is None: return False
    if passes_filter(d): return False                          # already in main list
    if d.get('industry') in EXCLUDED_INDUSTRIES: return False
    # Must have meaningful debt in range (slightly wider ceiling — 0.65)
    if d['debt_to_ev'] is None or not (0.15 <= d['debt_to_ev'] <= 0.65): return False
    # Real FCF generation — the whole point
    if d['fcf_yield'] is None or d['fcf_yield'] < 5.0: return False
    # FCF/Debt proves actual paydown capacity
    if d['fcf_to_debt_pct'] is None or d['fcf_to_debt_pct'] < 10.0: return False
    # Exclude commodity cycles — oil E&P FCF swings with crude, not business quality
    if d.get('industry') in {'Oil & Gas E&P', 'Oil & Gas Midstream'}: return False
    # Exclude managed care — NI decline here is real medical cost ratio deterioration
    if d.get('industry') in {'Healthcare Plans'}: return False
    # Exclude retail margin compression — structural, not non-cash
    if d.get('industry') in {'Discount Stores', 'Department Stores'}: return False
    # Must have some revenue — not a pure balance-sheet play
    if d['rev_growth'] is None: return False
    return True


# ── HTML ──────────────────────────────────────────────────────────────────────

def fmt(val, suffix='', prefix='', dash_color='#484f58'):
    if val is None:
        return f'<span style="color:{dash_color}">—</span>'
    return f"{prefix}{val}{suffix}"


def pct_color(val, good_above=0, bad_below=None):
    if val is None:
        return '<span style="color:#484f58">—</span>'
    if bad_below is not None and val < bad_below:
        c = '#f85149'
    elif val >= good_above:
        c = '#3fb950'
    else:
        c = '#ffa657'
    return f'<span style="color:{c}">{val}%</span>'


def ic_cell(curr, prev, improving):
    if curr is None:
        return '<span style="color:#484f58">—</span>'
    arrow = ' <span style="color:#3fb950">↑</span>' if improving else (' <span style="color:#f85149">↓</span>' if prev is not None else '')
    color = '#3fb950' if (curr >= 5) else ('#ffa657' if curr >= 3 else '#f85149')
    return f'<span style="color:{color}">{curr}×</span>{arrow}'


def build_html(results, monitor):
    now   = datetime.now().strftime('%B %d, %Y  %H:%M')
    rows  = ''

    strong   = [d for d in results if d['category'] == 'Strong']
    on_track = [d for d in results if d['category'] == 'On Track']
    watch    = [d for d in results if d['category'] == 'Watch']

    def row_html(d):
        cat = d['category']
        cat_cls = {'Strong': 'cat-strong', 'On Track': 'cat-ontrack', 'Watch': 'cat-watch', 'Monitor': 'cat-monitor'}[cat]
        ic_trend = ic_cell(d['ic_curr'], d['ic_prev'], d['ic_improving'])
        gm_arrow = (' <span style="color:#3fb950">↑</span>' if d['gm_improving'] is True
                    else (' <span style="color:#f85149">↓</span>' if d['gm_improving'] is False else ''))
        return f"""<tr>
          <td class="ticker">{d['ticker']}</td>
          <td style="color:#8b949e;font-size:11px">{d['name'][:22]}</td>
          <td style="color:#8b949e;font-size:11px">{d['sector'][:14]}</td>
          <td style="color:#e6edf3">${fmt(d['price'])}</td>
          <td style="color:#e6edf3">${fmt(d['market_cap_b'])}B</td>
          <td class="grade-col"><span class="badge {cat_cls}">{cat}</span></td>
          <td style="color:#58a6ff;font-weight:700">{fmt(d['debt_to_ev'])}</td>
          <td>{pct_color(d['fcf_yield'], 7, 4)}</td>
          <td>{fmt(d['fcf_to_debt_pct'], '%') if d['fcf_to_debt_pct'] else '<span style="color:#484f58">—</span>'}</td>
          <td>{pct_color(d['ni_growth'], 10, 0)}</td>
          <td>{pct_color(d['rev_growth'], 5, 2)}</td>
          <td>{pct_color(d['operating_margin'], 15)}</td>
          <td>{pct_color(d['net_margin'], 10, 3)}{gm_arrow}</td>
          <td>{ic_trend}</td>
          <td style="color:#e6edf3;font-weight:700">{d['score']}/10</td>
          <td style="color:#8b949e">{fmt(d['pe'], 'x')}</td>
        </tr>"""

    for section, label, sub in [
        (strong,   '💪 Strong — Clear path to sub-0.20, profits accelerating',
                   'FCF > 7% · NI growing > 10% · Interest coverage improving'),
        (on_track, '📈 On Track — Solid trajectory, watch closely',
                   'FCF healthy · Profits growing · Coverage improving'),
        (watch,    '👀 Watch — Direction right, pace uncertain',
                   'De-lever trend confirmed but FCF or growth slower'),
    ]:
        if section:
            rows += f'''<tr><td colspan="16" style="padding:20px 10px 6px;font-size:13px;font-weight:700;color:#f0883e;border-bottom:2px solid #21262d">
              {label}
              <span style="color:#8b949e;font-size:10px;font-weight:400;margin-left:12px">{sub}</span>
            </td></tr>'''
            for d in section:
                rows += row_html(d)

    if monitor:
        rows += '''<tr><td colspan="16" style="padding:28px 10px 6px;font-size:13px;font-weight:700;color:#bc8cff;border-bottom:2px solid #21262d">
          🔬 Monitor Closely — FCF confirmed, GAAP NI distorted by non-cash items
          <span style="color:#8b949e;font-size:10px;font-weight:400;margin-left:12px">Real debt paydown underway · NI drag from impairments / acquisition amortization · Watch for GAAP inflection</span>
        </td></tr>'''
        for d in monitor:
            rows += row_html(d)

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>De-lever + Profit Growth Screener — {now}</title>
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
  td {{ padding: 7px 10px; border-bottom: 1px solid #161b22; }}
  tr:hover td {{ background: #161b22; }}
  .ticker {{ font-weight: 700; color: #e6edf3; }}
  .badge {{ font-size: 11px; font-weight: 700; padding: 2px 8px; border-radius: 3px; }}
  .cat-strong  {{ background: #1a4731; color: #3fb950; }}
  .cat-ontrack {{ background: #1c2e4a; color: #58a6ff; }}
  .cat-watch   {{ background: #2d2208; color: #ffa657; }}
  .cat-monitor {{ background: #1e1b2e; color: #bc8cff; }}
  .thesis {{ background: #161b22; border: 1px solid #21262d; border-radius: 8px; padding: 16px; margin-bottom: 20px; }}
  .thesis h2 {{ font-size: 11px; color: #8b949e; margin-bottom: 10px; text-transform: uppercase; letter-spacing: .08em; }}
  .thesis-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }}
  .thesis-item {{ font-size: 11px; color: #8b949e; line-height: 1.6; }}
  .thesis-item span {{ color: #58a6ff; }}
  .thesis-item strong {{ color: #e6edf3; display: block; margin-bottom: 2px; }}
  .disclaimer {{ color: #484f58; font-size: 10px; margin-top: 24px; border-top: 1px solid #21262d; padding-top: 8px; line-height: 1.8; }}
</style>
</head>
<body>
<h1>📉 De-lever + Profit Growth Screener</h1>
<div class="subtitle">{now}</div>
<div class="summary">
  Found <span>{len(results)}</span> companies on a confirmed de-lever + profit growth trajectory —
  <span>{len(strong)}</span> Strong &nbsp;·&nbsp;
  <span>{len(on_track)}</span> On Track &nbsp;·&nbsp;
  <span>{len(watch)}</span> Watch
  &nbsp;·&nbsp; <span style="color:#bc8cff">{len(monitor)}</span> <span style="color:#bc8cff">Monitor Closely</span>
</div>

<div class="thesis">
  <h2>The Mechanical Thesis</h2>
  <div class="thesis-grid">
    <div class="thesis-item">
      <strong>Why de-levering beats the market</strong>
      Lower debt → lower interest expense → net income grows <span>mechanically</span>,
      even before revenue tailwinds. Most investors miss this compounding effect.
    </div>
    <div class="thesis-item">
      <strong>Filter logic</strong>
      D/EV <span>0.15–0.60</span> (has debt, heading down) ·
      FCF yield <span>> 4%</span> (cash to pay it) ·
      NI growth <span>> 0%</span> · Rev growth <span>> 2%</span> ·
      Interest coverage <span>> 3×</span>
    </div>
    <div class="thesis-item">
      <strong>Momentum score (0–10)</strong>
      FCF yield > 7% <span>+2</span> · NI growth > 10% <span>+2</span> ·
      Coverage improving <span>+2</span> · Rev > 5% <span>+1</span> ·
      Gross margin stable <span>+1</span> · D/EV ≤ 0.30 <span>+1</span>
    </div>
  </div>
</div>

<table>
  <thead>
    <tr>
      <th>Ticker</th><th>Name</th><th>Sector</th><th>Price</th><th>Mkt Cap</th>
      <th>Category</th><th>D/EV</th><th>FCF Yld</th><th>FCF/Debt</th>
      <th>NI Grw</th><th>Rev Grw</th><th>Op Mgn</th><th>Net Mgn</th>
      <th>Int Cov</th><th>Score</th><th>P/E</th>
    </tr>
  </thead>
  <tbody>{rows}</tbody>
</table>

<div class="disclaimer">
  FCF/Debt = annual free cash flow as % of total debt — higher means faster paydown.<br>
  Int Cov = EBIT ÷ Interest Expense · ↑ = improving YoY · NI Grw = net income growth YoY from annual financials.<br>
  Data sourced from Yahoo Finance via yfinance. For informational purposes only — not financial advice.
</div>
</body>
</html>"""


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    print(f"\n  Screening {len(UNIVERSE)} companies for de-lever + profit growth ...", flush=True)
    print("  (fetching annual financials — takes ~60s)\n", flush=True)

    with ThreadPoolExecutor(max_workers=8) as ex:
        raw = list(ex.map(get_fundamentals, UNIVERSE))

    passed = [d for d in raw if passes_filter(d)]
    for d in passed:
        d['score']    = momentum_score(d)
        d['category'] = category(d['score'])

    passed.sort(key=lambda x: (
        0 if x['category'] == 'Strong' else 1 if x['category'] == 'On Track' else 2,
        -x['score'],
        x['debt_to_ev'] or 1,
    ))

    monitor = [d for d in raw if passes_monitor(d)]
    for d in monitor:
        d['score']    = momentum_score(d)
        d['category'] = 'Monitor'
    monitor.sort(key=lambda x: -(x['fcf_to_debt_pct'] or 0))

    strong   = sum(1 for d in passed if d['category'] == 'Strong')
    on_track = sum(1 for d in passed if d['category'] == 'On Track')
    watch    = sum(1 for d in passed if d['category'] == 'Watch')

    print(f"  ✅  {len(passed)} companies passed filters")
    print(f"      {strong} Strong  ·  {on_track} On Track  ·  {watch} Watch")
    print(f"  🔬  {len(monitor)} Monitor Closely\n")

    html = build_html(passed, monitor)
    path = os.path.expanduser('~/delever_screener.html')
    with open(path, 'w') as f:
        f.write(html)

    print(f"  Saved → {path}")
    webbrowser.open(f'file://{path}')
