"""
India Market Selective Briefing — CLI + HTML Dashboard
Tracks key NSE sector ETFs and indices across MA timeframes.
Usage: python india_dashboard.py
       python india_dashboard.py --refresh

Data: Yahoo Finance via yfinance (NSE tickers)
Disclaimer: For informational purposes only. Not financial advice.
"""

import yfinance as yf
import warnings, json, os, time, webbrowser
from datetime import datetime, date
from concurrent.futures import ThreadPoolExecutor, as_completed
warnings.filterwarnings('ignore')

try:
    from zoneinfo import ZoneInfo
    def _ist_now(): return datetime.now(ZoneInfo('Asia/Kolkata'))
except ImportError:
    from datetime import timezone, timedelta
    def _ist_now():
        return datetime.now(timezone(timedelta(hours=5, minutes=30)))

# NSE holidays 2025–2027 (verify against official NSE calendar each year)
NSE_HOLIDAYS = {
    date(2025, 2, 26), date(2025, 3, 14), date(2025, 3, 31),
    date(2025, 4, 10), date(2025, 4, 14), date(2025, 4, 18),
    date(2025, 5, 1), date(2025, 8, 15), date(2025, 8, 27),
    date(2025, 10, 2), date(2025, 10, 2), date(2025, 10, 21),
    date(2025, 10, 22), date(2025, 11, 5), date(2025, 12, 25),
    date(2026, 1, 26), date(2026, 3, 25), date(2026, 4, 3),
    date(2026, 4, 14), date(2026, 5, 1), date(2026, 8, 15),
    date(2026, 10, 2), date(2026, 11, 9), date(2026, 11, 10),
    date(2026, 12, 25),
    date(2027, 1, 26), date(2027, 3, 29), date(2027, 4, 2),
    date(2027, 4, 14), date(2027, 8, 15), date(2027, 8, 30),
    date(2027, 10, 2), date(2027, 10, 29), date(2027, 11, 19),
    date(2027, 12, 25),
}

def market_status():
    ist = _ist_now()
    if ist.weekday() >= 5:
        day = 'Saturday' if ist.weekday() == 5 else 'Sunday'
        return False, f'{day} — NSE closed'
    if ist.date() in NSE_HOLIDAYS:
        return False, 'NSE holiday — markets closed today'
    if ist.hour < 9 or (ist.hour == 9 and ist.minute < 15):
        return False, 'Pre-market — NSE opens 9:15 AM IST'
    if ist.hour >= 15 and ist.minute >= 30:
        return False, 'After hours — NSE closed at 3:30 PM IST'
    return True, 'NSE open'

CACHE_FILE = os.path.expanduser('~/.india_dashboard_cache.json')
CACHE_TTL  = 900

# All index tickers — reliable MA data from yfinance (no volume for indices, shown as N/A)
TICKERS = [
    '^NSEI', '^NSMIDCP', '^INDIAVIX',
    '^CNXIT', '^NSEBANK', '^CNXPSUBANK',
    '^CNXPSE', '^CNXINFRA',
    '^CNXPHARMA', '^CNXAUTO', '^CNXENERGY', '^CNXMETAL',
    '^CNXFMCG', '^CNXREALTY',
]

THEMES = {
    '^NSEI':       'Nifty50',
    '^NSMIDCP':    'Midcap',
    '^INDIAVIX':   'India VIX',
    '^CNXIT':      'IT',
    '^NSEBANK':    'Banks',
    '^CNXPSUBANK': 'PSUBanks',
    '^CNXPSE':     'PSU/Capex',
    '^CNXINFRA':   'Infra',
    '^CNXPHARMA':  'Pharma',
    '^CNXAUTO':    'Auto',
    '^CNXENERGY':  'Energy',
    '^CNXMETAL':   'Metal',
    '^CNXFMCG':    'FMCG',
    '^CNXREALTY':  'Realty',
}

GROUPS = [
    ('BENCHMARK',    ['^NSEI', '^NSMIDCP', '^INDIAVIX']),
    ('TECH & BANKS', ['^CNXIT', '^NSEBANK', '^CNXPSUBANK']),
    ('PSU / CAPEX',  ['^CNXPSE', '^CNXINFRA']),
    ('SECTORS',      ['^CNXPHARMA', '^CNXAUTO', '^CNXENERGY', '^CNXMETAL']),
    ('CONSUMER',     ['^CNXFMCG', '^CNXREALTY']),
]

G  = '\033[92m'
R  = '\033[91m'
Y  = '\033[93m'
GR = '\033[90m'
B  = '\033[94m'
RS = '\033[0m'

def after_close():
    ist = _ist_now()
    return ist.hour >= 15 and ist.minute >= 30

def load_cache():
    try:
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE) as f:
                c = json.load(f)
            if time.time() - c.get('_ts', 0) < CACHE_TTL:
                return c
    except Exception:
        pass
    return {}

def save_cache(data):
    try:
        data['_ts'] = time.time()
        with open(CACHE_FILE, 'w') as f:
            json.dump(data, f)
    except Exception:
        pass

def fetch(ticker, period, interval):
    return yf.Ticker(ticker).history(period=period, interval=interval, auto_adjust=True)

def above_ma(ticker, interval, period, ma):
    try:
        df = fetch(ticker, period, interval)
        if len(df) < ma + 1: return None
        return float(df['Close'].iloc[-1]) > float(df['Close'].rolling(ma).mean().iloc[-1])
    except Exception:
        return None

def get_data(ticker):
    try:
        df = fetch(ticker, '3mo', '1d')
        if df is None or len(df) < 6:
            print(f'  ⚠ {ticker}: insufficient data')
            return None

        price   = float(df['Close'].iloc[-1])
        prev    = float(df['Close'].iloc[-2])
        day_chg = (price - prev) / prev * 100

        # Volume — use last non-zero bar (after-close the last bar is 0 for indices)
        nonzero_vol = df[df['Volume'] > 0]
        if len(nonzero_vol) == 0:
            vol_rat, vol_lbl = None, ''
        elif after_close():
            avg_vol = float(nonzero_vol['Volume'].iloc[-21:-1].mean()) if len(nonzero_vol) > 1 else 0
            last_vol = float(nonzero_vol['Volume'].iloc[-1])
            vol_rat = last_vol / avg_vol if avg_vol > 0 else None
            vol_lbl = 'C'
        else:
            avg_vol = float(nonzero_vol['Volume'].iloc[-21:-1].mean()) if len(nonzero_vol) > 1 else 0
            vol_rat = float(df['Volume'].iloc[-1]) / avg_vol if avg_vol > 0 else None
            vol_lbl = 'P'

        chg5    = (price - float(df['Close'].iloc[-6])) / float(df['Close'].iloc[-6]) * 100
        trend   = 'up' if chg5 > 0.5 else ('dn' if chg5 < -0.5 else 'flat')

        ma50    = float(df['Close'].rolling(50).mean().iloc[-1])
        ma20    = float(df['Close'].rolling(20).mean().iloc[-1])
        ma_dist = (price - ma20) / ma20 * 100

        d_above   = price > ma50
        w_above   = above_ma(ticker, '1wk', '2y', 20)
        m10_above = above_ma(ticker, '1mo', '5y', 10)
        m20_above = above_ma(ticker, '1mo', '5y', 20)

        return dict(
            ticker=ticker, theme=THEMES[ticker], price=price,
            day_chg=day_chg, vol_rat=vol_rat, vol_lbl=vol_lbl,
            trend=trend, ma_dist=ma_dist,
            d=d_above, w=w_above, m10=m10_above, m20=m20_above,
        )
    except Exception as e:
        print(f'  ⚠ {ticker}: {e}')
        return None

def fmt_chg(v):
    c = G if v > 0 else R
    return f'{c}{v:+.2f}%{RS}'

def fmt_vol(v, lbl):
    if v is None: return f'{GR}N/A{RS}'
    c = Y if v > 1.5 else (GR if v < 0.5 else '')
    return f'{c}{v:.2f}x({lbl}){RS}'

def fmt_ma(v):
    c = G if v > 0 else R
    return f'{c}{v:+.1f}%{RS}'

def fmt_tf(above):
    if above is None: return f'{GR}?{RS}'
    return f'{G}▲{RS}' if above else f'{R}▼{RS}'

def momentum_score(d):
    return sum(1 for x in [d['d'], d['w'], d['m10'], d['m20']] if x)

def fmt_score(s):
    c = G if s >= 3 else (Y if s == 2 else R)
    return f'{c}[{s}/4]{RS}'

def signal(d):
    above = momentum_score(d)
    if above == 4:                          return f'{G}ALIGNED{RS}'
    if d['m20'] and d['w'] and not d['d']: return f'{B}PULLBACK{RS}'
    if not d['m20'] and not d['w']:        return f'{R}AVOID{RS}'
    return ''

def signal_html(d):
    above = momentum_score(d)
    if above == 4:                          return '<span style="color:#3fb950;font-weight:700">ALIGNED</span>'
    if d['m20'] and d['w'] and not d['d']: return '<span style="color:#58a6ff;font-weight:700">PULLBACK</span>'
    if not d['m20'] and not d['w']:        return '<span style="color:#f85149;font-weight:700">AVOID</span>'
    return '<span style="color:#484f58">—</span>'

def score_html(s):
    c = '#3fb950' if s >= 3 else ('#e3b341' if s == 2 else '#f85149')
    return f'<span style="color:{c};font-weight:700">{s}/4</span>'

def tf_html(above):
    if above is None: return '<span style="color:#484f58">?</span>'
    return '<span style="color:#3fb950">▲</span>' if above else '<span style="color:#f85149">▼</span>'

def chg_html(v):
    c = '#3fb950' if v > 0 else '#f85149'
    return f'<span style="color:{c}">{v:+.2f}%</span>'

def vol_html(v, lbl):
    if v is None: return '<span style="color:#484f58">N/A</span>'
    c = '#e3b341' if v > 1.5 else ('#484f58' if v < 0.5 else '#8b949e')
    return f'<span style="color:{c}">{v:.2f}x({lbl})</span>'

def ma_html(v):
    c = '#3fb950' if v > 0 else '#f85149'
    return f'<span style="color:{c}">{v:+.1f}%</span>'

def build_html(data, is_open=True, status_msg=''):
    now  = _ist_now().strftime('%B %d, %Y  %H:%M IST')
    rows = ''
    for group, tickers in GROUPS:
        rows += f'<tr><td colspan="13" style="padding:14px 10px 4px;color:#8b949e;font-size:10px;text-transform:uppercase;letter-spacing:.08em;border-bottom:none">{group}</td></tr>'
        for t in tickers:
            d = data.get(t)
            if not d:
                rows += f'<tr><td class="ticker">{THEMES.get(t,t)}</td><td colspan="12" style="color:#484f58">— no data</td></tr>'
                continue
            rows += f"""<tr>
              <td class="ticker">{d['theme']}</td>
              <td style="color:#8b949e;font-size:11px">{d['ticker']}</td>
              <td>₹{d['price']:.1f}</td>
              <td>{chg_html(d['day_chg'])}</td>
              <td>{vol_html(d['vol_rat'], d['vol_lbl'])}</td>
              <td>{'<span style="color:#3fb950">▲</span>' if d['trend']=='up' else ('<span style="color:#f85149">▼</span>' if d['trend']=='dn' else '<span style="color:#8b949e">→</span>')}</td>
              <td>{ma_html(d['ma_dist'])}</td>
              <td>{tf_html(d['d'])}</td>
              <td>{tf_html(d['w'])}</td>
              <td>{tf_html(d['m10'])}</td>
              <td>{tf_html(d['m20'])}</td>
              <td>{score_html(momentum_score(d))}</td>
              <td>{signal_html(d)}</td>
            </tr>"""

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>India Market Briefing — {now}</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: 'SF Mono','Fira Code',monospace; background: #0d1117; color: #e6edf3; padding: 28px; font-size: 12px; }}
  h1 {{ font-size: 18px; font-weight: 700; color: #f0883e; margin-bottom: 4px; }}
  .subtitle {{ color: #8b949e; margin-bottom: 20px; font-size: 11px; }}
  table {{ width: 100%; border-collapse: collapse; }}
  th {{ text-align: left; padding: 8px 10px; color: #8b949e; font-weight: 500;
        border-bottom: 2px solid #21262d; font-size: 10px; text-transform: uppercase; letter-spacing: .05em; }}
  td {{ padding: 7px 10px; border-bottom: 1px solid #161b22; }}
  tr:hover td {{ background: #161b22; }}
  .ticker {{ font-weight: 700; color: #e6edf3; }}
  .market-closed {{ background: #2d1f00; border: 1px solid #e3b341; color: #e3b341; font-size: 11px; padding: 8px 12px; border-radius: 6px; margin-bottom: 16px; }}
  .legend {{ color: #484f58; font-size: 10px; margin-top: 16px; line-height: 1.8; }}
  .disclaimer {{ color: #484f58; font-size: 10px; margin-top: 8px; border-top: 1px solid #21262d; padding-top: 8px; }}
</style>
</head>
<body>
<h1>🇮🇳 India Market Briefing</h1>
<div class="subtitle">{now} IST</div>
{'<div class="market-closed">⚠ ' + status_msg + ' — showing last available data</div>' if not is_open else ''}
<table>
  <thead>
    <tr>
      <th>Theme</th><th>Ticker</th><th>Price</th><th>Day%</th><th>Vol/Avg</th>
      <th>5D</th><th>vs20D</th><th>50D</th><th>20W</th><th>10M</th><th>20M</th>
      <th>Mom</th><th>Signal</th>
    </tr>
  </thead>
  <tbody>{rows}</tbody>
</table>
<div class="legend">
  ▲ above MA &nbsp;▼ below MA &nbsp;|&nbsp; 50D=50-day MA &nbsp;20W=20-week MA &nbsp;10M=10-month MA &nbsp;20M=20-month MA<br>
  Vol/Avg: N/A — all tickers are indices (no volume data)<br>
  Signals: ALIGNED=all 4 MAs bullish &nbsp;PULLBACK=long-term up, short-term dip &nbsp;AVOID=below long-term MAs
</div>
<div class="disclaimer">
  Data sourced from NSE via Yahoo Finance / yfinance. Prices may be delayed.<br>
  For informational purposes only — not financial advice. Always do your own research.
</div>
</body>
</html>"""

def print_dashboard(data, is_open, status_msg):
    now = _ist_now().strftime('%b %d %Y  %H:%M IST')
    w   = 100
    hdr = f"  {'THEME':<12}  {'PRICE':>9}  {'DAY%':>8}  {'VOL/AVG':>10}  {'5D':>2}  {'vs20D':>6}   50D  20W  10M  20M   MOM   SIGNAL"
    print()
    print(f"  {Y}🇮🇳 INDIA MARKET BRIEFING  —  {now}{RS}")
    if not is_open:
        print(f"  {Y}⚠  {status_msg} — showing last available data{RS}")
    print('─' * w)
    print(hdr)

    for group, tickers in GROUPS:
        print(f"\n  {GR}{group}{RS}")
        for t in tickers:
            d = data.get(t)
            if not d:
                print(f"  {THEMES.get(t,t):<12}  — no data")
                continue
            vol_str = fmt_vol(d['vol_rat'], d['vol_lbl'])
            print(
                f"  {d['theme']:<12}  "
                f"₹{d['price']:>8.1f}  "
                f"{fmt_chg(d['day_chg']):>8}  "
                f"{vol_str:>10}  "
                f"{(G+'▲'+RS) if d['trend']=='up' else ((R+'▼'+RS) if d['trend']=='dn' else '→'):>2}  "
                f"{fmt_ma(d['ma_dist']):>6}   "
                f"{fmt_tf(d['d'])} {fmt_tf(d['w'])} {fmt_tf(d['m10'])} {fmt_tf(d['m20'])}   "
                f"{fmt_score(momentum_score(d))}  "
                f"{signal(d)}"
            )

    print()
    print('─' * w)
    print(f"  {GR}▲/▼ = above/below MA  |  NSE hours: 9:15 AM – 3:30 PM IST  |  Vol N/A = indices have no volume{RS}")
    print(f"  {GR}For informational purposes only — not financial advice.{RS}")
    print()

if __name__ == '__main__':
    import sys
    is_open, status_msg = market_status()
    force   = '--refresh' in sys.argv
    browser = '--browser' in sys.argv
    cache   = {} if force else load_cache()
    if cache:
        age = int((time.time() - cache['_ts']) / 60)
        print(f"\n  Using cached data ({age}m old) — run with --refresh to force update")
        cache.pop('_ts', None)
        data = cache
    else:
        print('\n  Loading', end='', flush=True)
        data = {}
        with ThreadPoolExecutor(max_workers=len(TICKERS)) as ex:
            futures = {ex.submit(get_data, t): t for t in TICKERS}
            for f in as_completed(futures):
                print('.', end='', flush=True)
                t = futures[f]
                data[t] = f.result()
        print()
        save_cache({k: v for k, v in data.items() if v})

    print_dashboard(data, is_open, status_msg)

    path = os.path.expanduser('~/india_briefing.html')
    with open(path, 'w') as f:
        f.write(build_html(data, is_open, status_msg))
    print(f"  Saved → {path}")
    if browser:
        webbrowser.open(f'file://{path}')
