"""
Turnaround Screener — Small / Mid / Micro Cap US
==================================================
Finds early-stage operational turnarounds before the market reprices.

The core signal: Inventory Falling 📉 + Revenue Rising 📈
When a company that was over-inventoried starts selling through while revenue grows,
operating leverage kicks in hard — margins expand, FCF inflects, street upgrades follow.

Six turnaround signals scored:

  1. Inventory Falling + Revenue Rising  (+3)   THE signal — destocking complete
  2. Gross Margin Inflecting             (+2)   cost cuts / pricing starting to show
  3. FCF Improving                       (+2)   negative → less negative → positive
  4. Revenue After Decline               (+1)   prior year down, current year up
  5. Cheap on Revenue  P/S < 1          (+1)   market pricing in permanent impairment
  6. Asset Backstop    P/B < 1.5        (+1)   book value limits downside

TURN Score (0–10):
  Strong Signal  ≥ 7  — multiple signals firing, likely early innings
  Building       4–6  — 1–2 signals confirmed, watch for confirmation
  Early Stage    2–3  — single signal, needs follow-through

Universe: ~120 beaten-down small/mid/micro cap names across retail, industrial,
consumer, healthcare, media, gaming, tech hardware — inventory-sensitive sectors.

Data: Yahoo Finance via yfinance
Run:  python turnaround_screener.py
"""

import yfinance as yf
import warnings, os, webbrowser
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
warnings.filterwarnings('ignore')

# ── Universe ──────────────────────────────────────────────────────────────────
# Small / mid / micro cap beaten-down names across inventory-sensitive sectors.
# Deliberately excludes companies already recovered or too speculative (pre-revenue).

UNIVERSE = [
    # Apparel & footwear — most inventory-sensitive consumer sector
    'M', 'KSS', 'GPS', 'ANF', 'AEO', 'RL', 'PVH', 'VFC',
    'CROX', 'SKX', 'BIRD', 'BOOT', 'CAL',

    # Specialty retail
    'DKS', 'HIBB', 'FIVE', 'BURL', 'OLLI', 'BIG', 'PRTY',
    'WSM', 'RH', 'ARKO',

    # Online / omni retail
    'W', 'CHWY', 'ETSY', 'REAL', 'OSTK',

    # Home improvement / building products
    'AZEK', 'TREX', 'DOOR', 'MHK', 'LZB', 'FBHS',
    'SWK', 'ALLE', 'JELD',

    # Industrial / manufacturing (destocking cycle)
    'GNRC', 'NDSN', 'MIDD', 'RXO', 'ENOV', 'FORM',
    'ACCO', 'ESAB', 'REXR', 'NN', 'AIRC',

    # Transportation / logistics
    'ARCB', 'SAIA', 'XPO', 'GXO', 'RXO',
    'CHRW', 'ECHO', 'HUBG',

    # Tech hardware — memory / storage cycles
    'WDC', 'STX', 'NTAP', 'PSTG', 'COHU',
    'SMCI', 'UCTT', 'FORM',

    # Consumer tech / digital
    'SNAP', 'PINS', 'RBLX', 'U', 'DUOL', 'UDMY',

    # Gaming & leisure
    'PENN', 'CZR', 'DKNG', 'AGS', 'EVRI',

    # Cruise & airlines (post-cycle normalization)
    'CCL', 'NCLH', 'AAL', 'SAVE', 'CNK', 'AMC',

    # Food & beverage
    'SAM', 'TAP', 'CELH', 'COKE', 'FIZZ',
    'SFM', 'GO', 'WINA',

    # Healthcare — specialty pharma / diagnostics turnarounds
    'PRGO', 'VTRS', 'QDEL', 'HIMS', 'ACCD',
    'PDCO', 'XRAY', 'PNTG', 'OPCH',

    # Media / streaming
    'WBD', 'FUBO', 'SIRI', 'LYV',

    # Small-cap defense / gov services
    'KTOS', 'CACI', 'MANT', 'POWL', 'DY',

    # Energy small / mid
    'SM', 'CIVI', 'MTDR', 'REX', 'MGY', 'CTRA',

    # Homebuilders — inventory cycle plays
    'TMHC', 'MTH', 'KBH', 'LGIH', 'GRBK', 'MHO',

    # Specialty / other
    'LUMN', 'XPEV', 'NIO', 'RIDE',
    'OPFI', 'CURO', 'ELVN',
]
UNIVERSE = list(dict.fromkeys(UNIVERSE))   # deduplicate

# ── Data fetch ────────────────────────────────────────────────────────────────

def safe_div(a, b):
    try:
        return a / b if (a is not None and b and b != 0) else None
    except Exception:
        return None


def get_turnaround_data(ticker):
    try:
        t    = yf.Ticker(ticker)
        info = t.info
        if not info or 'marketCap' not in info:
            return None

        market_cap  = info.get('marketCap', 0) or 0
        if market_cap < 30_000_000:   # skip sub-$30M names
            return None

        price   = info.get('currentPrice') or info.get('regularMarketPrice')
        high_52 = info.get('fiftyTwoWeekHigh')
        low_52  = info.get('fiftyTwoWeekLow')

        # ── Inventory signal — from balance sheet ──────────────────────────
        inv_curr = inv_prev = None
        try:
            bs = t.balance_sheet
            if bs is not None and not bs.empty:
                for idx in bs.index:
                    if 'inventory' in str(idx).lower():
                        row = bs.loc[idx]
                        if len(row) >= 2:
                            inv_curr = row.iloc[0]
                            inv_prev = row.iloc[1]
                        break
        except Exception:
            pass

        # ── Revenue + gross margin — from financials ───────────────────────
        rev_curr = rev_prev = rev_2yr = None
        gp_curr  = gp_prev  = None
        ni_curr  = ni_prev  = None
        try:
            fin = t.financials
            if fin is not None and not fin.empty:
                for idx in fin.index:
                    sl = str(idx).lower()
                    if 'total revenue' in sl or (sl == 'revenue'):
                        row = fin.loc[idx]
                        if len(row) >= 1: rev_curr = row.iloc[0]
                        if len(row) >= 2: rev_prev = row.iloc[1]
                        if len(row) >= 3: rev_2yr  = row.iloc[2]
                    if 'gross profit' in sl:
                        row = fin.loc[idx]
                        if len(row) >= 1: gp_curr = row.iloc[0]
                        if len(row) >= 2: gp_prev = row.iloc[1]
                    if 'net income' in sl and 'minority' not in sl:
                        row = fin.loc[idx]
                        if len(row) >= 1: ni_curr = row.iloc[0]
                        if len(row) >= 2: ni_prev = row.iloc[1]
        except Exception:
            pass

        # ── FCF — from cash flow ───────────────────────────────────────────
        fcf_curr = fcf_prev = None
        try:
            cf = t.cashflow
            if cf is not None and not cf.empty:
                oc_row = cx_row = None
                for idx in cf.index:
                    sl = str(idx).lower()
                    if 'operating' in sl and 'cash' in sl:
                        oc_row = cf.loc[idx]
                    if 'capital expenditure' in sl:
                        cx_row = cf.loc[idx]
                if oc_row is not None and cx_row is not None:
                    if len(oc_row) >= 1 and len(cx_row) >= 1:
                        fcf_curr = oc_row.iloc[0] + cx_row.iloc[0]
                    if len(oc_row) >= 2 and len(cx_row) >= 2:
                        fcf_prev = oc_row.iloc[1] + cx_row.iloc[1]
        except Exception:
            pass

        # ── Derived ────────────────────────────────────────────────────────
        rev_growth   = safe_div(rev_curr - rev_prev, abs(rev_prev)) * 100 if rev_curr and rev_prev and rev_prev != 0 else None
        # Was revenue declining the year before? (prior yr vs 2yr ago)
        rev_was_down = (rev_prev is not None and rev_2yr is not None and rev_prev < rev_2yr)

        inv_falling  = (inv_curr is not None and inv_prev is not None and inv_curr < inv_prev)
        inv_chg_pct  = safe_div(inv_curr - inv_prev, abs(inv_prev)) * 100 if inv_curr and inv_prev and inv_prev != 0 else None

        gm_curr      = safe_div(gp_curr, rev_curr) * 100 if gp_curr and rev_curr else None
        gm_prev      = safe_div(gp_prev, rev_prev) * 100 if gp_prev and rev_prev else None
        gm_inflect   = (gm_curr is not None and gm_prev is not None and gm_curr > gm_prev)

        fcf_improving = (fcf_curr is not None and fcf_prev is not None and fcf_curr > fcf_prev)
        fcf_positive  = (fcf_curr is not None and fcf_curr > 0)

        p_s = safe_div(market_cap, rev_curr) if rev_curr else None
        p_b = info.get('priceToBook')
        if not isinstance(p_b, (int, float)):
            p_b = None

        return dict(
            ticker        = ticker,
            name          = info.get('shortName', ticker),
            sector        = info.get('sector', ''),
            industry      = info.get('industry', ''),
            price         = round(price, 2) if price else None,
            market_cap_b  = round(market_cap / 1e9, 2),
            high_52       = round(high_52, 2) if high_52 else None,
            low_52        = round(low_52, 2) if low_52 else None,
            vs_52h        = round(price / high_52, 2) if price and high_52 else None,
            # Inventory
            inv_falling   = inv_falling,
            inv_chg_pct   = round(inv_chg_pct, 1) if inv_chg_pct else None,
            has_inventory = (inv_curr is not None),
            # Revenue
            rev_growth    = round(rev_growth, 1) if rev_growth is not None else None,
            rev_was_down  = rev_was_down,
            # Gross margin
            gm_curr       = round(gm_curr, 1) if gm_curr else None,
            gm_prev       = round(gm_prev, 1) if gm_prev else None,
            gm_inflect    = gm_inflect,
            gm_delta      = round(gm_curr - gm_prev, 1) if gm_curr and gm_prev else None,
            # FCF
            fcf_curr_m    = round(fcf_curr / 1e6, 0) if fcf_curr else None,
            fcf_improving = fcf_improving,
            fcf_positive  = fcf_positive,
            # Valuation
            p_s           = round(p_s, 2) if p_s else None,
            p_b           = round(p_b, 2) if p_b else None,
            pe_fwd        = round(info.get('forwardPE'), 1) if info.get('forwardPE') and isinstance(info.get('forwardPE'), (int, float)) and info.get('forwardPE') < 500 else None,
            net_margin    = round(info.get('profitMargins', 0) * 100, 1) if info.get('profitMargins') else None,
        )
    except Exception as e:
        print(f"  ⚠ {ticker}: {e}")
        return None


# ── Score ─────────────────────────────────────────────────────────────────────

def turn_score(d):
    score = 0
    flags = []

    # 1. THE signal — inventory falling while revenue rising
    if d['has_inventory']:
        if d['inv_falling'] and d['rev_growth'] is not None and d['rev_growth'] > 2:
            score += 3
            flags.append(f"📉 Inventory {d['inv_chg_pct']}%  📈 Revenue +{d['rev_growth']}%")
        elif d['inv_falling']:
            score += 1
            flags.append(f"Inventory falling {d['inv_chg_pct']}% (rev flat)")
        elif d['rev_growth'] is not None and d['rev_growth'] > 5:
            score += 1
            flags.append(f"Revenue +{d['rev_growth']}% (inventory not tracked)")

    # Services companies (no inventory) — revenue signal alone
    if not d['has_inventory'] and d['rev_growth'] is not None and d['rev_growth'] > 5:
        score += 2
        flags.append(f"Revenue +{d['rev_growth']}% (services)")

    # 2. Gross margin inflecting
    if d['gm_inflect'] and d['gm_delta']:
        score += 2
        flags.append(f"GM +{d['gm_delta']}pp ({d['gm_prev']}% → {d['gm_curr']}%)")
    elif d['gm_inflect']:
        score += 1
        flags.append(f"GM improving ({d['gm_curr']}%)")

    # 3. FCF improving — the most important confirmation
    if d['fcf_improving'] and d['fcf_positive']:
        score += 2
        flags.append(f"FCF +${d['fcf_curr_m']:.0f}M (positive & improving)")
    elif d['fcf_improving']:
        score += 1
        flags.append(f"FCF improving (${d['fcf_curr_m']:.0f}M)")

    # 4. Revenue bounce after prior-year decline
    if d['rev_was_down'] and d['rev_growth'] is not None and d['rev_growth'] > 0:
        score += 1
        flags.append(f"Rev bounce: prior yr was down, now +{d['rev_growth']}%")

    # 5. Cheap on revenue — market pricing in permanent impairment
    if d['p_s'] is not None and d['p_s'] < 1.0:
        score += 1
        flags.append(f"P/S {d['p_s']}× (priced for zero recovery)")

    # 6. Asset backstop
    if d['p_b'] is not None and 0 < d['p_b'] < 1.5:
        score += 1
        flags.append(f"P/B {d['p_b']}×")

    return score, flags


def category(score):
    if score >= 7: return 'Strong Signal'
    if score >= 4: return 'Building'
    if score >= 2: return 'Early Stage'
    return None


# ── HTML ──────────────────────────────────────────────────────────────────────

def clr(val, good, warn=None, rev=False):
    if val is None:
        return '<span style="color:#484f58">—</span>'
    if not rev:
        c = '#3fb950' if val >= good else ('#ffa657' if warn and val >= warn else '#f85149')
    else:
        c = '#3fb950' if val <= good else ('#ffa657' if warn and val <= warn else '#f85149')
    return f'<span style="color:{c}">{val}</span>'


def build_html(results):
    now = datetime.now().strftime('%B %d, %Y  %H:%M')

    strong   = [d for d in results if d['category'] == 'Strong Signal']
    building = [d for d in results if d['category'] == 'Building']
    early    = [d for d in results if d['category'] == 'Early Stage']

    def row_html(d):
        cat = d['category']
        cat_cls = {
            'Strong Signal': 'cat-strong',
            'Building':      'cat-build',
            'Early Stage':   'cat-early',
        }[cat]
        vs_h = f"{d['vs_52h']*100:.0f}%" if d['vs_52h'] else '—'
        vs_color = '#f85149' if d['vs_52h'] and d['vs_52h'] < 0.5 else \
                   '#ffa657' if d['vs_52h'] and d['vs_52h'] < 0.75 else '#8b949e'
        inv_str = f"{d['inv_chg_pct']}%" if d['inv_chg_pct'] else ('N/A' if not d['has_inventory'] else '—')
        inv_color = '#3fb950' if d['inv_falling'] else '#8b949e'
        gm_str = f"{d['gm_curr']}%" if d['gm_curr'] else '—'
        gm_arrow = ' <span style="color:#3fb950">↑</span>' if d['gm_inflect'] else \
                   (' <span style="color:#f85149">↓</span>' if d['gm_inflect'] is False else '')
        fcf_str = f"${d['fcf_curr_m']:.0f}M" if d['fcf_curr_m'] is not None else '—'
        fcf_color = '#3fb950' if d['fcf_positive'] else ('#ffa657' if d['fcf_improving'] else '#f85149')
        flags_html = '<br>'.join(
            f'<span style="color:#ffa657;font-size:10px">{f}</span>'
            for f in d['flags']
        ) if d['flags'] else '<span style="color:#484f58">—</span>'
        return f"""<tr>
          <td class="ticker">{d['ticker']}</td>
          <td style="color:#8b949e;font-size:11px">{d['name'][:22]}</td>
          <td style="color:#8b949e;font-size:11px">{d['sector'][:13]}</td>
          <td style="color:#e6edf3">${d['price'] if d['price'] else '—'}</td>
          <td style="color:#e6edf3">${d['market_cap_b']}B</td>
          <td class="grade-col"><span class="badge {cat_cls}">{cat}</span></td>
          <td style="color:#58a6ff;font-weight:700">{d['score']}/10</td>
          <td><span style="color:{inv_color}">{inv_str}</span></td>
          <td>{clr(d['rev_growth'], 5, 0)}{('%' if d['rev_growth'] is not None else '')}</td>
          <td>{gm_str}{gm_arrow}</td>
          <td><span style="color:{fcf_color}">{fcf_str}</span></td>
          <td style="color:{vs_color}">{vs_h}</td>
          <td>{clr(d['p_s'], 0, 2, rev=True)}{'×' if d['p_s'] else ''}</td>
          <td style="color:#8b949e">{d['p_b'] if d['p_b'] else '—'}{'×' if d['p_b'] else ''}</td>
          <td style="line-height:1.6">{flags_html}</td>
        </tr>"""

    rows = ''
    for section, label, sub, color in [
        (strong,   '🚀 Strong Signal — Multiple turnaround signals confirmed',
         'Inventory falling + revenue rising + margin inflecting', '#3fb950'),
        (building, '🔧 Building — Key signals emerging, watch for confirmation',
         '1–2 turnaround signals confirmed, trajectory positive', '#58a6ff'),
        (early,    '🌱 Early Stage — Single signal, needs follow-through',
         'First sign of change — monitor quarterly', '#ffa657'),
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
<title>Turnaround Screener — {now}</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: 'SF Mono','Fira Code',monospace; background: #0d1117; color: #e6edf3; padding: 28px; font-size: 12px; }}
  h1 {{ font-size: 18px; font-weight: 700; color: #ffa657; margin-bottom: 4px; }}
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
  .cat-strong {{ background: #1a3a1a; color: #3fb950; }}
  .cat-build  {{ background: #1c2e4a; color: #58a6ff; }}
  .cat-early  {{ background: #2d2208; color: #ffa657; }}
  .thesis {{ background: #161b22; border: 1px solid #21262d; border-radius: 8px; padding: 16px; margin-bottom: 20px; }}
  .thesis h2 {{ font-size: 11px; color: #8b949e; margin-bottom: 10px; text-transform: uppercase; letter-spacing: .08em; }}
  .thesis-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }}
  .thesis-item {{ font-size: 11px; color: #8b949e; line-height: 1.6; }}
  .thesis-item strong {{ color: #e6edf3; display: block; margin-bottom: 2px; }}
  .thesis-item span {{ color: #ffa657; }}
  .disclaimer {{ color: #484f58; font-size: 10px; margin-top: 24px; border-top: 1px solid #21262d; padding-top: 8px; line-height: 1.8; }}
</style>
</head>
<body>
<h1>📦📈 Turnaround Screener — Small / Mid / Micro Cap</h1>
<div class="subtitle">{now} · Inventory-led operational turnarounds before the street reprices</div>
<div class="summary">
  <span>{len(results)}</span> turnaround candidates —
  <span>{len(strong)}</span> Strong Signal &nbsp;·&nbsp;
  <span>{len(building)}</span> Building &nbsp;·&nbsp;
  <span>{len(early)}</span> Early Stage
</div>

<div class="thesis">
  <h2>The Turnaround Signal</h2>
  <div class="thesis-grid">
    <div class="thesis-item">
      <strong>Why inventory matters most</strong>
      Over-inventoried companies suppress margins and burn cash. When inventory
      falls while revenue rises, <span>destocking is complete</span> — operating leverage
      kicks in, margins expand, FCF inflects. Street upgrades follow 1–2 quarters later.
    </div>
    <div class="thesis-item">
      <strong>Six signals scored (0–10)</strong>
      <span>Inv ↓ + Rev ↑</span> +3 (THE signal) ·
      <span>GM inflecting</span> +2 ·
      <span>FCF improving</span> +2 ·
      <span>Rev bounce after decline</span> +1 ·
      <span>P/S &lt;1</span> +1 ·
      <span>P/B &lt;1.5</span> +1
    </div>
    <div class="thesis-item">
      <strong>When to act</strong>
      Strong Signal = multiple confirmations, early innings.
      Building = trend visible, wait for 1 more quarter.
      Early Stage = first sign, needs follow-through before sizing up.
    </div>
  </div>
</div>

<table>
  <thead>
    <tr>
      <th>Ticker</th><th>Name</th><th>Sector</th><th>Price</th><th>Mkt Cap</th>
      <th>Category</th><th>Score</th><th>Inv Δ</th><th>Rev Grw</th>
      <th>Gr Mgn</th><th>FCF</th><th>vs 52wH</th><th>P/S</th><th>P/B</th>
      <th>Signals</th>
    </tr>
  </thead>
  <tbody>{rows}</tbody>
</table>

<div class="disclaimer">
  Inv Δ = YoY inventory change (negative = falling = good for this thesis).<br>
  vs 52wH = price as % of 52-week high — lower = more fear priced in.<br>
  FCF = trailing annual free cash flow. GM = gross margin with ↑↓ YoY direction.<br>
  Universe: small/mid/micro cap inventory-sensitive sectors. Not financial advice.
</div>
</body>
</html>"""


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    print(f"\n  Turnaround Screener — {len(UNIVERSE)} companies", flush=True)
    print("  Small / Mid / Micro Cap · Inventory + Revenue signal", flush=True)
    print("  (fetching data — takes ~90s)\n", flush=True)

    with ThreadPoolExecutor(max_workers=8) as ex:
        raw = list(ex.map(get_turnaround_data, UNIVERSE))

    results = []
    for d in raw:
        if d is None: continue
        score, flags = turn_score(d)
        cat = category(score)
        if cat is None: continue
        d['score']    = score
        d['flags']    = flags
        d['category'] = cat
        results.append(d)

    results.sort(key=lambda x: (
        0 if x['category'] == 'Strong Signal' else
        1 if x['category'] == 'Building' else 2,
        -x['score'],
    ))

    strong   = sum(1 for d in results if d['category'] == 'Strong Signal')
    building = sum(1 for d in results if d['category'] == 'Building')
    early    = sum(1 for d in results if d['category'] == 'Early Stage')

    print(f"  ✅  {len(results)} turnaround candidates")
    print(f"      {strong} Strong Signal  ·  {building} Building  ·  {early} Early Stage\n")

    for cat_name in ['Strong Signal', 'Building']:
        group = [d for d in results if d['category'] == cat_name]
        if group:
            print(f"  {cat_name}:")
            for d in group:
                flag_preview = d['flags'][0] if d['flags'] else ''
                print(f"    {d['ticker']:<6} {d['score']:>2}/10  ${d['market_cap_b']}B  {flag_preview}")
        print()

    html = build_html(results)
    path = os.path.expanduser('~/turnaround_screener.html')
    with open(path, 'w') as f:
        f.write(html)
    print(f"  Saved → {path}")
    webbrowser.open(f'file://{path}')
