"""
daily_alert.py — Mid-week alert for liquid names.
Fetches fresh data (9 names only — lightweight), fires email on new crossings:
  - w_gate open → closed (or closed → open)
  - Band change: IN ↔ -EXT ↔ +EXT
  - Price crosses below MA20d (daily structure break)
  - Price recovers above MA50d (recovery signal)
Run: python daily_alert.py
"""

import json, os, requests, warnings
import yfinance as yf
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

warnings.filterwarnings('ignore')

import sys
sys.path.insert(0, '.')
from ma_scanner import liquid_status, LIQUID_NAMES

HERE       = Path(__file__).parent
STATE_FILE = HERE / 'daily_alert_state.json'
RESEND_KEY = os.environ.get('RESEND_API_KEY', '')


def _load_subscribers():
    env = os.environ.get('SUBSCRIBERS', '')
    if env:
        return json.loads(env)
    path = HERE / 'subscribers.json'
    if path.exists():
        return json.loads(path.read_text())
    return [os.environ.get('NEWSLETTER_TO', 'amarnath@neurobloom.ai')]


def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {}


def save_state(state):
    STATE_FILE.write_text(json.dumps(state, indent=2))


def daily_ma_check(ticker):
    """Check price vs MA20d and MA50d on daily bars."""
    try:
        hist  = yf.Ticker(ticker).history(period='3mo', interval='1d')
        close = hist['Close'].dropna()
        if len(close) < 50:
            return None
        price = float(close.iloc[-1])
        ma20  = float(close.tail(20).mean())
        ma50  = float(close.tail(50).mean())
        return {
            'price':        round(price, 2),
            'above_ma20d':  price > ma20,
            'above_ma50d':  price > ma50,
            'pct_ma20d':    round((price - ma20) / ma20 * 100, 1),
            'pct_ma50d':    round((price - ma50) / ma50 * 100, 1),
        }
    except:
        return None


def fetch_current(name):
    row    = liquid_status(name)
    daily  = daily_ma_check(name)
    if row is None:
        return name, None
    sym, price, w_gate, pct20d, pct10w, m10w, m50d, band, slope, w_gap = row
    return name, {
        'w_gate':      bool(w_gate),
        'band':        band,
        'slope':       round(slope, 2) if slope else None,
        'pct10w':      round(pct10w, 2) if pct10w else None,
        'above_ma20d': daily['above_ma20d'] if daily else None,
        'above_ma50d': daily['above_ma50d'] if daily else None,
        'pct_ma20d':   daily['pct_ma20d']   if daily else None,
        'pct_ma50d':   daily['pct_ma50d']   if daily else None,
        'price':       daily['price']        if daily else price,
    }


def detect_crossings(current, prev):
    # No prior state — send current snapshot of actionable names
    if not prev:
        alerts = []
        for ticker, cur in current.items():
            if cur and cur.get('w_gate') and cur.get('band') in ('IN', '-EXT'):
                alerts.append((ticker, f"Gate open · {cur['band']} band", 'snapshot'))
        return alerts

    alerts = []
    for ticker, cur in current.items():
        if cur is None:
            continue
        p = prev.get(ticker)
        if p is None:
            continue

        # w_gate flip
        if p.get('w_gate') != cur['w_gate']:
            direction = 'OPENED' if cur['w_gate'] else 'CLOSED'
            alerts.append((ticker, f"Weekly gate {direction}", 'gate'))

        # band crossing (only meaningful transitions)
        MEANINGFUL = {('IN', '-EXT'), ('-EXT', 'IN'), ('IN', '+EXT'), ('+EXT', 'IN')}
        if (p.get('band'), cur['band']) in MEANINGFUL:
            alerts.append((ticker, f"Band {p.get('band')} → {cur['band']}", 'band'))

        # daily MA20 cross
        if p.get('above_ma20d') is not None and cur['above_ma20d'] is not None:
            if p['above_ma20d'] and not cur['above_ma20d']:
                alerts.append((ticker, f"Broke below MA20d ({cur['pct_ma20d']:+.1f}%)", 'daily'))
            elif not p['above_ma20d'] and cur['above_ma20d']:
                alerts.append((ticker, f"Recovered above MA20d ({cur['pct_ma20d']:+.1f}%)", 'daily'))

        # daily MA50 cross
        if p.get('above_ma50d') is not None and cur['above_ma50d'] is not None:
            if p['above_ma50d'] and not cur['above_ma50d']:
                alerts.append((ticker, f"Broke below MA50d ({cur['pct_ma50d']:+.1f}%)", 'daily'))
            elif not p['above_ma50d'] and cur['above_ma50d']:
                alerts.append((ticker, f"Recovered above MA50d ({cur['pct_ma50d']:+.1f}%)", 'daily'))

    return alerts


def build_html(alerts, current):
    date_str = datetime.utcnow().strftime('%b %d %Y %H:%M UTC')
    rows = ['<ul style="padding-left:20px">']
    for ticker, msg, kind in alerts:
        cur   = current.get(ticker, {})
        price = cur.get('price', '—')
        gate  = '✓ gate open' if cur.get('w_gate') else '✗ gate closed'
        band  = cur.get('band', '—')
        rows.append(
            f'<li style="margin-bottom:8px">'
            f'<b>{ticker}</b> ${price} — {msg} '
            f'<span style="color:#888">({gate} · {band})</span>'
            f'</li>'
        )
    rows.append('</ul>')
    return f"""
<div style="font-family:system-ui,sans-serif;max-width:560px;margin:0 auto;padding:24px">
  <p style="font-size:12px;color:#888;margin:0 0 16px">neurobloom · {date_str}</p>
  <h2 style="margin:0 0 12px;font-size:18px">Daily Structure Alert</h2>
  {''.join(rows)}
  <hr style="margin:24px 0;border:none;border-top:1px solid #eee">
  <p style="font-size:11px;color:#aaa">Liquid names only · Not financial advice · neurobloom.ai</p>
</div>
"""


def send_alert(subject, html):
    if not RESEND_KEY:
        print('  RESEND_API_KEY not set — skipping email')
        return
    recipients = _load_subscribers()
    resp = requests.post(
        'https://api.resend.com/emails',
        headers={'Authorization': f'Bearer {RESEND_KEY}', 'Content-Type': 'application/json'},
        json={
            'from': 'Market Pulse <newsletter@neurobloom.ai>',
            'to':   recipients,
            'subject': subject,
            'html': html,
        },
        timeout=15,
    )
    if resp.status_code in (200, 201):
        print(f'  Alert sent → {len(recipients)} recipient(s)')
    else:
        print(f'  Resend error: {resp.status_code} {resp.text}')


if __name__ == '__main__':
    print(f'  Fetching {len(LIQUID_NAMES)} liquid names ...', flush=True)
    with ThreadPoolExecutor(max_workers=9) as ex:
        results = dict(ex.map(fetch_current, LIQUID_NAMES))

    prev    = load_state()
    alerts  = detect_crossings(results, prev)

    if alerts:
        print(f'  Crossings: {len(alerts)}')
        for t, msg, kind in alerts:
            print(f'    {t}: {msg}')
        subject = f'neurobloom alert — {datetime.utcnow().strftime("%b %d")}'
        html    = build_html(alerts, results)
        send_alert(subject, html)
    else:
        print('  No new crossings — no alert sent')

    save_state(results)
    print('  Saved → daily_alert_state.json')
