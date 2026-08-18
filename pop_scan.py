"""
Daily Pop Scanner — on-demand internal tool.

Checks price vs 10d / 20d / 50d daily MAs across our full universe.
Useful for spotting M&A burst pops, momentum setups, and sudden breakouts.

Usage:
  python pop_scan.py               # scan full UNIVERSE + WATCHLIST
  python pop_scan.py MKTX NVDA     # scan specific tickers
  python pop_scan.py --universe    # universe only
  python pop_scan.py --watchlist   # watchlist only
"""

import json
import os
import sys
import types
import warnings
import webbrowser
import yfinance as yf
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

warnings.filterwarnings('ignore')

# mock _yf_cache so screener.py imports cleanly without requests_cache installed
sys.modules.setdefault('_yf_cache', types.ModuleType('_yf_cache'))

from screener import UNIVERSE, WATCHLIST

_CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'screener_data_cache.json')

def _load_grades():
    try:
        with open(_CACHE_FILE) as f:
            cache = json.load(f)
        grades = {}
        for t, d in cache.items():
            if not d:
                continue
            om  = d.get('operating_margin') or 0
            nm  = d.get('net_margin') or 0
            roe = d.get('roe') or 0
            dev = d.get('debt_to_ev') or 1
            fcf = d.get('fcf_yield') or 0
            gm  = d.get('gross_margin') or 0
            rg  = d.get('rev_growth') or 0
            passes = om >= 0.10 and nm >= 0.05 and roe >= 0.10 and dev <= 0.20 and fcf > 0
            if not passes:
                grades[t] = None
                continue
            aplus = (dev <= 0.03 and om >= 0.20 and nm >= 0.10 and roe >= 0.20
                     and fcf >= 0.02 and gm >= 0.60 and rg >= 0.05)
            a     = (dev <= 0.10 and om >= 0.15 and nm >= 0.08 and roe >= 0.15 and fcf >= 0.01)
            grades[t] = 'A+' if aplus else ('A' if a else 'B')
        return grades
    except Exception:
        return {}

def _range_band(pct50):
    if 1 <= pct50 <= 6:
        return 3, 'gold',  '#1c1700', '#d4a017'   # freshest — tightest breakout
    elif 7 <= pct50 <= 15:
        return 2, 'green', '#0d1a0d', '#3fb950'   # confirmed momentum
    elif 16 <= pct50 <= 30:
        return 1, 'amber', '#1a1000', '#f0883e'   # extended but in range
    else:
        return 0, 'none',  '',        ''           # <1% or >30% — no highlight

def _setup_score(r, grades):
    grade  = grades.get(r['ticker'])
    g_pts  = {'A+': 3, 'A': 2, 'B': 1}.get(grade, 0)
    ma_pts = 2 if r['all3'] else 1
    range_pts, _, _, _ = _range_band(r['pct50'])
    return g_pts + ma_pts + range_pts, grade

def _daily_cmf(hist, period=20):
    try:
        hl = (hist['High'] - hist['Low']).replace(0, float('nan'))
        mfm = ((hist['Close'] - hist['Low']) - (hist['High'] - hist['Close'])) / hl
        mfv = mfm * hist['Volume']
        vol_sum = hist['Volume'].rolling(period).sum().iloc[-1]
        if not vol_sum or vol_sum == 0:
            return float('nan')
        return round(float(mfv.rolling(period).sum().iloc[-1] / vol_sum), 3)
    except Exception:
        return float('nan')

def get_daily_ma_pos(ticker):
    try:
        hist = yf.Ticker(ticker).history(period='3mo', interval='1d')
        if hist is None or len(hist) < 52:
            return None
        close = hist['Close'].dropna()
        price = close.iloc[-1]
        ma10  = close.iloc[-10:].mean()
        ma20  = close.iloc[-20:].mean()
        ma50  = close.iloc[-50:].mean()
        count = sum([price > ma10, price > ma20, price > ma50])
        near  = sum([price >= ma10*0.95, price >= ma20*0.95, price >= ma50*0.95])
        # slope: % change in 10d MA over last 5 sessions
        ma10_series = close.rolling(10).mean().dropna()
        slope = round((ma10_series.iloc[-1] / ma10_series.iloc[-6] - 1) * 100, 1) if len(ma10_series) >= 6 else float('nan')
        cmf   = _daily_cmf(hist)
        return {
            'ticker': ticker,
            'price':  round(price, 2),
            'pct10':  round((price / ma10 - 1) * 100, 1),
            'pct20':  round((price / ma20 - 1) * 100, 1),
            'pct50':  round((price / ma50 - 1) * 100, 1),
            'above':  count,
            'all3':   count == 3,
            'near':   near,
            'cmf':    cmf,
            'slope':  slope,
        }
    except Exception:
        return None

def get_hourly_stack(ticker):
    """Returns True if price above 10hMA, 20hMA, 50hMA on hourly bars (not necessarily stacked)."""
    try:
        hist = yf.Ticker(ticker).history(period='10d', interval='1h')
        if hist is None or len(hist) < 52:
            return False
        close = hist['Close'].dropna()
        price = close.iloc[-1]
        ma10  = close.iloc[-10:].mean()
        ma20  = close.iloc[-20:].mean()
        ma50  = close.iloc[-50:].mean()
        return price > ma10 and price > ma20 and price > ma50
    except Exception:
        return False

def _pct_cell(pct):
    color = '#3fb950' if pct > 0 else '#f85149'
    sign  = '+' if pct > 0 else ''
    return f'<td style="color:{color};font-weight:600">{sign}{pct}%</td>'

def _cmf_cell(cmf):
    import math
    if cmf is None or (isinstance(cmf, float) and math.isnan(cmf)):
        return '<td style="color:#484f58">—</td>'
    if cmf >= 0.15:
        color = '#3fb950'
    elif cmf <= -0.15:
        color = '#f85149'
    else:
        color = '#8b949e'
    sign = '+' if cmf > 0 else ''
    return f'<td style="color:{color};font-weight:600">{sign}{cmf:.3f}</td>'

def _slope_cell(slope):
    import math
    if slope is None or (isinstance(slope, float) and math.isnan(slope)):
        return '<td style="color:#484f58">—</td>'
    color = '#3fb950' if slope > 0 else '#f85149'
    sign  = '+' if slope > 0 else ''
    return f'<td style="color:{color};font-size:11px">{sign}{slope}%</td>'

def build_html(all3, two, tight, misses, no_data, now, label, grades, hourly):
    def rows_for(group, badge_color, badge_label, is_tight=False):
        out = ''
        for r in group:
            score, grade   = _setup_score(r, grades)
            if is_tight:
                row_style = 'border-left:3px solid #1a6b7a;'
            else:
                _, _, bg, border = _range_band(r['pct50'])
                row_style = f'background:{bg};border-left:3px solid {border};' if bg else ''
            grade_str   = f'<span style="color:#8b949e;font-size:10px">{grade}</span>' if grade else ''
            hourly_flag = '<span title="Hourly: price above 10hMA, 20hMA, 50hMA (not necessarily stacked)" style="color:#58a6ff;font-size:10px;margin-left:4px">⚡H</span>' if hourly.get(r['ticker']) else ''
            out += f"""<tr style="{row_style}">
              <td class="ticker">{r['ticker']} {grade_str}{hourly_flag}</td>
              <td><span class="badge" style="background:{badge_color}">{badge_label}</span></td>
              <td>${r['price']}</td>
              {_pct_cell(r['pct10'])}
              {_pct_cell(r['pct20'])}
              {_pct_cell(r['pct50'])}
              {_cmf_cell(r.get('cmf'))}
              {_slope_cell(r.get('slope'))}
            </tr>"""
        return out

    rows  = rows_for(all3,  '#6e40c9', '● 3/3')
    rows += rows_for(two,   '#1a4731', '◐ 2/3')
    rows += rows_for(tight, '#1a4a4a', '◎ tight', is_tight=True)

    miss_rows  = rows_for(misses, '#3d1212', '✕ below')
    nd_tickers = '  ·  '.join(no_data) if no_data else '—'

    thead = """<thead>
    <tr>
      <th>Ticker</th><th>MAs</th><th>Price</th>
      <th>vs 10dMA</th><th>vs 20dMA</th><th>vs 50dMA</th><th>CMF</th><th>Slope</th>
    </tr>
  </thead>"""

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Pop Scan — {now}</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: 'SF Mono','Fira Code',monospace; background: #0d1117; color: #e6edf3; padding: 28px; font-size: 12px; }}
  h1 {{ font-size: 18px; font-weight: 700; color: #58a6ff; margin-bottom: 4px; }}
  .subtitle {{ color: #8b949e; font-size: 11px; margin-bottom: 20px; }}
  .summary {{ color: #8b949e; font-size: 12px; margin-bottom: 20px; }}
  .summary span {{ color: #e6edf3; font-weight: 700; }}
  table {{ width: 100%; border-collapse: collapse; margin-bottom: 32px; }}
  th {{ text-align: left; padding: 8px 10px; color: #8b949e; font-weight: 500;
        border-bottom: 2px solid #21262d; font-size: 10px; text-transform: uppercase; letter-spacing: .05em; }}
  td {{ padding: 8px 10px; border-bottom: 1px solid #161b22; }}
  tr:hover td {{ background: rgba(255,255,255,0.03); }}
  .ticker {{ font-weight: 700; color: #e6edf3; font-size: 13px; }}
  .badge {{ font-size: 11px; font-weight: 700; padding: 2px 8px; border-radius: 3px; color: #fff; }}
  .section-header {{ font-size: 11px; font-weight: 600; color: #8b949e; margin: 24px 0 8px;
                     border-top: 1px solid #21262d; padding-top: 12px; text-transform: uppercase; letter-spacing: .05em; }}
  .disclaimer {{ color: #484f58; font-size: 10px; margin-top: 24px; border-top: 1px solid #21262d; padding-top: 8px; }}
</style>
</head>
<body>
<h1>📈 Daily Pop Scanner <span style="font-size:13px;color:#8b949e;font-weight:400">— {label}</span></h1>
<div class="subtitle">{now} &nbsp;·&nbsp; price vs 10d / 20d / 50d daily MAs &nbsp;·&nbsp; not necessarily stacked &nbsp;·&nbsp; gold 1-6% · green 7-15% · amber 16-30% vs 50dMA &nbsp;·&nbsp; ◎ tight = within -5% of 2+ MAs</div>

<div class="summary">
  <span>{len(all3)}</span> above all 3 &nbsp;·&nbsp;
  <span>{len(two)}</span> above 2 of 3 &nbsp;·&nbsp;
  <span>{len(tight)}</span> tight (within -5%) &nbsp;·&nbsp;
  <span>{len(misses)}</span> below &nbsp;·&nbsp;
  <span>{len(no_data)}</span> no data
</div>

<table>
  {thead}
  <tbody>{rows}</tbody>
</table>

<div class="section-header">Below All MAs — {len(misses)} tickers</div>
<table>
  {thead}
  <tbody>{miss_rows}</tbody>
</table>

<div class="section-header">No data — {nd_tickers}</div>
<div class="disclaimer">For informational purposes only. Market dynamics change constantly — these outputs are auto-generated from Yahoo Finance data and may not reflect current conditions. Not tailored financial advice. Not a recommendation to buy, sell, or hold any security. Always do your own research.</div>
</body>
</html>"""

def run(tickers, label):
    print(f'\n  Pop Scan — {len(tickers)} tickers ...', flush=True)
    grades = _load_grades()
    with ThreadPoolExecutor(max_workers=12) as ex:
        results  = list(ex.map(get_daily_ma_pos, tickers))
        h_stacks = list(ex.map(get_hourly_stack, tickers))

    hourly  = {t: s for t, s in zip(tickers, h_stacks)}
    valid   = [r for r in results if r is not None]
    hits    = sorted([r for r in valid if r['above'] >= 2], key=lambda x: (-x['above'], -x['pct50']))
    below   = [r for r in valid if r['above'] < 2]
    tight   = sorted([r for r in below if r.get('near', 0) >= 2], key=lambda x: -x['pct50'])
    misses  = sorted([r for r in below if r.get('near', 0) < 2],  key=lambda x: -x['above'])
    no_data = [t for t, r in zip(tickers, results) if r is None]
    all3    = [h for h in hits if h['all3']]
    two     = [h for h in hits if h['above'] == 2]

    now  = datetime.utcnow().strftime('%b %d %Y  %H:%M UTC')
    html = build_html(all3, two, tight, misses, no_data, now, label, grades, hourly)

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'pop_scan.html')
    with open(out, 'w') as f:
        f.write(html)

    print(f'  ● {len(all3)} above all 3  ·  ◐ {len(two)} above 2  ·  ◎ {len(tight)} tight  ·  {len(misses)} below  ·  {len(no_data)} no data')
    print(f'  Opened → {out}\n')
    webbrowser.open(f'file://{out}')

if __name__ == '__main__':
    args = sys.argv[1:]

    if not args:
        tickers = list(dict.fromkeys(UNIVERSE))
        tickers += [t for t in WATCHLIST if t not in tickers]
        label = 'Universe + Watchlist'
    elif args == ['--universe']:
        tickers = list(dict.fromkeys(UNIVERSE))
        label = 'Universe'
    elif args == ['--watchlist']:
        tickers = list(dict.fromkeys(WATCHLIST))
        label = 'Watchlist'
    else:
        tickers = [t.upper() for t in args if not t.startswith('--')]
        label = ', '.join(tickers)

    run(tickers, label)
