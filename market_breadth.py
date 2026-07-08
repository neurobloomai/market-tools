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
        ma200 = s.iloc[-200:].mean() if len(s) >= 200 else None
        a20  = ma20  is not None and price > ma20
        a50  = ma50  is not None and price > ma50
        a200 = ma200 is not None and price > ma200

        if a200 and a50 and a20:
            bucket = 'all3'
        elif a50 and a20:
            bucket = 'ma20_ma50'
        elif a20:
            bucket = 'ma20_only'
        else:
            bucket = 'none'

        rows.append(dict(
            ticker=col,
            price=round(price, 2),
            ma20=round(ma20, 2) if ma20 is not None else None,
            ma50=round(ma50, 2) if ma50 is not None else None,
            ma200=round(ma200, 2) if ma200 is not None else None,
            a20=a20, a50=a50, a200=a200,
            bucket=bucket,
        ))

    total = len(rows)
    pct20  = round(sum(1 for r in rows if r['a20'])  / total * 100, 1) if total else 0
    pct50  = round(sum(1 for r in rows if r['a50'])  / total * 100, 1) if total else 0
    pct200 = round(sum(1 for r in rows if r['a200']) / total * 100, 1) if total else 0

    buckets = {
        'all3':      [r for r in rows if r['bucket'] == 'all3'],
        'ma20_ma50': [r for r in rows if r['bucket'] == 'ma20_ma50'],
        'ma20_only': [r for r in rows if r['bucket'] == 'ma20_only'],
        'none':      [r for r in rows if r['bucket'] == 'none'],
    }
    return dict(total=total, pct20=pct20, pct50=pct50, pct200=pct200,
                rows=rows, buckets=buckets)

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
    BUCKET_COLOR = {
        'all3':      '#3fb950',
        'ma20_ma50': '#ffa657',
        'ma20_only': '#e3b341',
        'none':      '#f85149',
    }
    BUCKET_LABEL = {
        'all3':      'MA20+50+200',
        'ma20_ma50': 'MA20+50',
        'ma20_only': 'MA20 only',
        'none':      'Below all',
    }
    html = ''
    for r in rows:
        color = BUCKET_COLOR[r['bucket']]
        label = BUCKET_LABEL[r['bucket']]
        dot_cell = (f'<td><span style="font-size:10px;font-weight:700;color:{color};'
                    f'background:{color}18;border:1px solid {color}40;'
                    f'border-radius:3px;padding:1px 6px">{label}</span></td>')
        html += f"""<tr>
          <td style="font-weight:700;color:#e6edf3">{r['ticker']}</td>
          <td>${r['price']:.2f}</td>
          {dot_cell}
          {_ma_cell(r['price'], r['ma20'],  r['a20'])}
          {_ma_cell(r['price'], r['ma50'],  r['a50'])}
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
    all3      = b['buckets']['all3']
    ma20_ma50 = b['buckets']['ma20_ma50']
    ma20_only = b['buckets']['ma20_only']
    none_     = b['buckets']['none']

    def bucket_block(label, color, rows):
        return f"""
<div style="margin-bottom:20px">
  <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px">
    <span style="font-size:12px;font-weight:700;color:{color}">{label}</span>
    <span style="font-size:10px;color:#484f58">({len(rows)})</span>
  </div>
  <div style="line-height:2">{_chips(rows, color)}</div>
</div>"""

    table_rows_html = _table_rows(b['rows'])

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
  {_bar(b['pct200'], 'Above MA200d (long-term trend)')}
  <div class="legend">Green ≥70% broad rally · Amber 50–70% mixed · Red &lt;50% narrow / correcting</div>
</div>

<div class="card">
  <div class="card-title">Breakdown by MA Alignment</div>
  {bucket_block('● Above MA20 + MA50 + MA200 — confirmed uptrend', '#3fb950', all3)}
  {bucket_block('● Above MA20 + MA50 only — recovering, not yet long-term', '#ffa657', ma20_ma50)}
  {bucket_block('● Above MA20 only — just lifting off lows', '#e3b341', ma20_only)}
  {bucket_block('● Below all MAs — downtrend', '#f85149', none_)}
</div>

<div class="card">
  <div class="card-title">All Names — MA Detail</div>
  <table>
    <thead>
      <tr>
        <th>Ticker</th><th>Price</th><th>Alignment</th>
        <th>MA20d (vs price)</th><th>MA50d (vs price)</th><th>MA200d (vs price)</th>
      </tr>
    </thead>
    <tbody>{table_rows_html}</tbody>
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
    print(f"  MA20d {b['pct20']}%  ·  MA50d {b['pct50']}%  ·  MA200d {b['pct200']}%  ({b['total']} names)")
    print(f"  all3={len(b['buckets']['all3'])}  ma20+50={len(b['buckets']['ma20_ma50'])}  "
          f"ma20only={len(b['buckets']['ma20_only'])}  below={len(b['buckets']['none'])}\n")

    html = build_html(b)
    out  = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'us_marketbreadth.html')
    with open(out, 'w') as f:
        f.write(html)
    print(f"  Saved → {out}")
    webbrowser.open(f'file://{out}')
