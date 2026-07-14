"""
alert_check.py — Fires an email when setup or watchlist thresholds cross.
Reads setups_snapshot.json + watchlist_snapshot.json (written by weekly_snapshot.py).
Tracks alerted state in alert_state.json so repeat alerts don't fire.
"""

import json, os, requests
from pathlib import Path
from datetime import datetime

HERE          = Path(__file__).parent
SETUPS_SNAP   = HERE / 'setups_snapshot.json'
WL_SNAP       = HERE / 'watchlist_snapshot.json'
STATE_FILE    = HERE / 'alert_state.json'

RESEND_KEY    = os.environ.get('RESEND_API_KEY', '')


def _load_subscribers():
    path = HERE / 'subscribers.json'
    if path.exists():
        return json.loads(path.read_text())
    return [os.environ.get('NEWSLETTER_TO', 'amarnath@neurobloom.ai')]


def _load(path):
    return json.loads(path.read_text()) if path.exists() else None


def current_setups():
    snap = _load(SETUPS_SNAP)
    if not snap:
        return {}
    return {
        row['ticker']: row['band']
        for row in snap
        if row.get('w_gate') and row.get('band') in ('IN', '-EXT')
    }


def current_watchlist():
    snap = _load(WL_SNAP)
    if not snap:
        return {}
    return {
        t: len(v['fails'])
        for t, v in snap.items()
        if len(v['fails']) <= 1
    }


def load_state():
    s = _load(STATE_FILE)
    return s if s else {'setups': {}, 'watchlist': {}}


def save_state(setups, watchlist):
    STATE_FILE.write_text(json.dumps({'setups': setups, 'watchlist': watchlist}, indent=2))


def _band_label(band):
    return 'In Band' if band == 'IN' else 'Extended — watch'


def build_html(new_setups, new_watchlist):
    date_str = datetime.utcnow().strftime('%b %d %Y')
    rows = []

    if new_setups:
        rows.append('<h3 style="margin:16px 0 6px;color:#1a1a1a">Setups Entering Zone</h3><ul style="padding-left:20px">')
        for t, band in sorted(new_setups.items()):
            rows.append(f'<li><b>{t}</b> &mdash; {_band_label(band)}, weekly gate cleared</li>')
        rows.append('</ul>')

    if new_watchlist:
        rows.append('<h3 style="margin:16px 0 6px;color:#1a1a1a">Watchlist Approaching Promotion</h3><ul style="padding-left:20px">')
        for t, fails in sorted(new_watchlist.items(), key=lambda x: x[1]):
            note = 'All gates cleared ✓' if fails == 0 else '1 blocker remaining'
            rows.append(f'<li><b>{t}</b> &mdash; {note}</li>')
        rows.append('</ul>')

    body = ''.join(rows)
    return f"""
<div style="font-family:system-ui,sans-serif;max-width:560px;margin:0 auto;padding:24px">
  <p style="font-size:12px;color:#888;margin:0 0 16px">neurobloom &middot; {date_str}</p>
  <h2 style="margin:0 0 4px;font-size:20px">Alert</h2>
  {body}
  <hr style="margin:24px 0;border:none;border-top:1px solid #eee">
  <p style="font-size:11px;color:#aaa">Not financial advice &middot; neurobloom.ai</p>
</div>
"""


def send_alert(subject, html):
    if not RESEND_KEY:
        print('  RESEND_API_KEY not set — skipping email')
        return
    recipients = _load_subscribers()
    for i in range(0, len(recipients), 50):
        batch = recipients[i:i+50]
        resp  = requests.post(
            'https://api.resend.com/emails',
            headers={'Authorization': f'Bearer {RESEND_KEY}', 'Content-Type': 'application/json'},
            json={'from': 'Market Pulse <newsletter@neurobloom.ai>', 'to': batch, 'subject': subject, 'html': html},
        )
        if resp.status_code in (200, 201):
            print(f'  Alert sent → {len(batch)} recipient(s)')
        else:
            print(f'  Resend error: {resp.status_code} {resp.text}')


if __name__ == '__main__':
    setups    = current_setups()
    watchlist = current_watchlist()
    state     = load_state()

    prev_s = state.get('setups', {})
    prev_w = state.get('watchlist', {})

    # New: ticker not previously alerted, or watchlist improved (1→0 fails)
    new_setups    = {t: b for t, b in setups.items()    if t not in prev_s}
    new_watchlist = {t: f for t, f in watchlist.items()
                     if t not in prev_w or prev_w[t] > f}

    if new_setups or new_watchlist:
        print(f'  Crossings: {len(new_setups)} setup(s), {len(new_watchlist)} watchlist')
        subject = f'neurobloom alert — {datetime.utcnow().strftime("%b %d")}'
        html    = build_html(new_setups, new_watchlist)
        send_alert(subject, html)
    else:
        print('  No new crossings — no alert sent')

    # State = what's currently in-zone (exit → re-entry will alert again)
    save_state(setups, watchlist)
    print('  Saved → alert_state.json')
