"""
US Market Breadth — standalone page
Uses the same UNIVERSE as screener.py.
Run: python market_breadth.py
Output: us_marketbreadth.html
"""

import yfinance as yf
import warnings, os, webbrowser
from datetime import datetime
warnings.filterwarnings('ignore')

# ── same universe as screener.py ──────────────────────────────────────────────
from screener import UNIVERSE

# ── data ─────────────────────────────────────────────────────────────────────

BUCKETS = [
    ('all4',         '#3fb950'),
    ('ma20_50_100',  '#ffa657'),
    ('ma20_50',      '#e3b341'),
    ('ma20_only',    '#d29922'),
    ('ma200_pullbk', '#58a6ff'),
    ('none',         '#f85149'),
]
BUCKET_LABEL = {
    'all4':         'MA20+50+100+200',
    'ma20_50_100':  'MA20+50+100',
    'ma20_50':      'MA20+50',
    'ma20_only':    'MA20 only',
    'ma200_pullbk': 'Above MA200 only',
    'none':         'Below all',
}
BUCKET_COLOR = {k: c for k, c in BUCKETS}

def _assign_bucket(a20, a50, a100, a200):
    if a20 and a50 and a100 and a200: return 'all4'
    if a20 and a50 and a100:          return 'ma20_50_100'
    if a20 and a50:                   return 'ma20_50'
    if a20:                           return 'ma20_only'
    if a200:                          return 'ma200_pullbk'
    return 'none'

def compute_breadth(tickers):
    import pandas as pd
    print(f"  Downloading daily data for {len(tickers)} names ...", flush=True)
    data = yf.download(tickers, period='1y', interval='1d',
                       auto_adjust=True, progress=False, threads=True)
    closes = data['Close'] if 'Close' in data.columns else data
    if isinstance(closes, pd.Series):
        closes = closes.to_frame()
    closes = closes.dropna(how='all')

    rows = []
    for col in sorted(closes.columns):
        s = closes[col].dropna()
        if len(s) < 20:
            continue
        price = s.iloc[-1]
        ma20  = s.iloc[-20:].mean()  if len(s) >= 20  else None
        ma50  = s.iloc[-50:].mean()  if len(s) >= 50  else None
        ma100 = s.iloc[-100:].mean() if len(s) >= 100 else None
        ma200 = s.iloc[-200:].mean() if len(s) >= 200 else None
        a20  = ma20  is not None and price > ma20
        a50  = ma50  is not None and price > ma50
        a100 = ma100 is not None and price > ma100
        a200 = ma200 is not None and price > ma200

        # fully stacked: price > MA20 > MA50 > MA100 > MA200 (MAs in order too)
        stacked = (all([ma20, ma50, ma100, ma200]) and
                   price > ma20 > ma50 > ma100 > ma200)

        rows.append(dict(
            ticker=col,
            price=round(price, 2),
            ma20=round(ma20, 2)   if ma20  is not None else None,
            ma50=round(ma50, 2)   if ma50  is not None else None,
            ma100=round(ma100, 2) if ma100 is not None else None,
            ma200=round(ma200, 2) if ma200 is not None else None,
            a20=a20, a50=a50, a100=a100, a200=a200,
            stacked=stacked,
            bucket=_assign_bucket(a20, a50, a100, a200),
        ))

    total = len(rows)
    def pct(flag): return round(sum(1 for r in rows if r[flag]) / total * 100, 1) if total else 0

    buckets = {k: [r for r in rows if r['bucket'] == k] for k, _ in BUCKETS}
    stacked = sorted([r for r in rows if r['stacked']], key=lambda r: r['ticker'])
    return dict(total=total,
                pct20=pct('a20'), pct50=pct('a50'), pct100=pct('a100'), pct200=pct('a200'),
                rows=rows, buckets=buckets, stacked=stacked)

# ── html ──────────────────────────────────────────────────────────────────────

def _bar(pct, label):
    color = '#3fb950' if pct >= 70 else ('#ffa657' if pct >= 50 else '#f85149')
    return f"""
<div style="margin-bottom:14px">
  <div style="display:flex;justify-content:space-between;margin-bottom:5px">
    <span style="font-size:11px;color:#8b949e">{label}</span>
    <span style="font-size:12px;color:{color};font-weight:700">{pct}%</span>
  </div>
  <div style="background:#21262d;border-radius:4px;height:8px">
    <div style="width:{pct}%;background:{color};border-radius:4px;height:8px"></div>
  </div>
</div>"""

def _ma_cell(price, ma, above):
    if ma is None:
        return '<td style="color:#484f58">—</td>'
    diff_pct = (price - ma) / ma * 100
    sign = '+' if diff_pct >= 0 else ''
    color = '#3fb950' if above else '#f85149'
    return (f'<td style="color:{color}">'
            f'${ma:.2f} <span style="font-size:9px;color:#484f58">'
            f'({sign}{diff_pct:.1f}%)</span></td>')

def _table_rows(rows):
    html = ''
    for r in rows:
        color = BUCKET_COLOR[r['bucket']]
        label = BUCKET_LABEL[r['bucket']]
        badge = (f'<span style="font-size:10px;font-weight:700;color:{color};'
                 f'background:{color}18;border:1px solid {color}40;'
                 f'border-radius:3px;padding:1px 6px">{label}</span>')
        html += f"""<tr>
          <td style="font-weight:700;color:#e6edf3">{r['ticker']}</td>
          <td>${r['price']:.2f}</td>
          <td>{badge}</td>
          {_ma_cell(r['price'], r['ma20'],  r['a20'])}
          {_ma_cell(r['price'], r['ma50'],  r['a50'])}
          {_ma_cell(r['price'], r['ma100'], r['a100'])}
          {_ma_cell(r['price'], r['ma200'], r['a200'])}
        </tr>"""
    return html

def _chips(rows, color):
    if not rows:
        return '<span style="color:#484f58;font-size:10px">—</span>'
    return ' '.join(
        f'<span style="font-size:10px;font-weight:600;color:{color};background:{color}18;'
        f'border:1px solid {color}40;border-radius:3px;padding:2px 6px">{r["ticker"]}</span>'
        for r in rows
    )

def build_html(b):
    now = datetime.now().strftime('%B %d, %Y  %H:%M')

    def bucket_block(key, label):
        color = BUCKET_COLOR[key]
        rows  = b['buckets'][key]
        return f"""
<div style="margin-bottom:20px">
  <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px">
    <span style="font-size:12px;font-weight:700;color:{color}">● {label}</span>
    <span style="font-size:10px;color:#484f58">({len(rows)})</span>
  </div>
  <div style="line-height:2">{_chips(rows, color)}</div>
</div>"""

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>US Market Breadth — {now}</title>
<style>
  * {{ box-sizing:border-box; margin:0; padding:0; }}
  body {{ font-family:'SF Mono','Fira Code',monospace; background:#0d1117; color:#e6edf3; padding:28px; font-size:12px; }}
  h1 {{ font-size:18px; font-weight:700; color:#58a6ff; margin-bottom:4px; }}
  .sub {{ color:#8b949e; font-size:11px; margin-bottom:24px; }}
  .card {{ background:#161b22; border:1px solid #21262d; border-radius:8px; padding:18px; margin-bottom:20px; }}
  .card-title {{ font-size:11px; color:#8b949e; text-transform:uppercase; letter-spacing:.08em; margin-bottom:14px; }}
  table {{ width:100%; border-collapse:collapse; margin-top:8px; }}
  th {{ text-align:left; padding:7px 10px; color:#8b949e; font-size:10px; text-transform:uppercase;
        letter-spacing:.05em; border-bottom:2px solid #21262d; font-weight:500; }}
  td {{ padding:7px 10px; border-bottom:1px solid #161b22; font-size:11px; }}
  tr:hover td {{ background:#161b22; }}
  .legend {{ font-size:10px; color:#484f58; margin-top:6px; }}
</style>
</head>
<body>
<h1>📊 US Market Breadth</h1>
<div class="sub">{now} &nbsp;·&nbsp; {b['total']} names tracked (Quality Growth Universe)</div>

<div class="card">
  <div class="card-title">% Names Above Moving Average</div>
  {_bar(b['pct20'],  'Above MA20d (short-term momentum)')}
  {_bar(b['pct50'],  'Above MA50d (intermediate trend)')}
  {_bar(b['pct100'], 'Above MA100d (medium-term trend)')}
  {_bar(b['pct200'], 'Above MA200d (long-term trend)')}
  <div class="legend">Green ≥70% broad rally · Amber 50–70% mixed · Red &lt;50% narrow / correcting</div>
</div>

<div class="card" style="border-color:#3fb95040">
  <div class="card-title" style="color:#3fb950">✦ Fully Stacked — Price &gt; MA20 &gt; MA50 &gt; MA100 &gt; MA200</div>
  <div style="font-size:10px;color:#484f58;margin-bottom:14px">
    MAs in perfect ascending order — the cleanest uptrend structure in the universe ({len(b['stacked'])} names)
  </div>
  <div style="line-height:2.2">{_chips(b['stacked'], '#3fb950')}</div>
</div>

<div class="card">
  <div class="card-title">Breakdown by MA Alignment</div>
  {bucket_block('all4',         'Above MA20 + MA50 + MA100 + MA200 — confirmed uptrend')}
  {bucket_block('ma20_50_100',  'Above MA20 + MA50 + MA100 only — recovering, not yet long-term')}
  {bucket_block('ma20_50',      'Above MA20 + MA50 only — short-term momentum')}
  {bucket_block('ma20_only',    'Above MA20 only — early lift')}
  {bucket_block('ma200_pullbk', 'Above MA200 only — long-term intact, pulling back')}
  {bucket_block('none',         'Below all MAs — downtrend')}
</div>

<div class="card">
  <div class="card-title">All Names — MA Detail</div>
  <table>
    <thead>
      <tr>
        <th>Ticker</th><th>Price</th><th>Alignment</th>
        <th>MA20d</th><th>MA50d</th><th>MA100d</th><th>MA200d</th>
      </tr>
    </thead>
    <tbody>{_table_rows(b['rows'])}</tbody>
  </table>
</div>

<div style="color:#484f58;font-size:10px;margin-top:16px;border-top:1px solid #21262d;padding-top:8px">
  Data via Yahoo Finance · For informational purposes only · Not financial advice
</div>
</body>
</html>"""

# ── main ──────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    print(f"\n  US Market Breadth — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    b = compute_breadth(UNIVERSE)
    print(f"  MA20d {b['pct20']}%  ·  MA50d {b['pct50']}%  ·  MA100d {b['pct100']}%  ·  MA200d {b['pct200']}%  ({b['total']} names)")
    for key, _ in BUCKETS:
        print(f"  {BUCKET_LABEL[key]:30} {len(b['buckets'][key])}")
    print()

    html = build_html(b)
    out  = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'us_marketbreadth.html')
    with open(out, 'w') as f:
        f.write(html)
    print(f"  Saved → {out}")
    webbrowser.open(f'file://{out}')
