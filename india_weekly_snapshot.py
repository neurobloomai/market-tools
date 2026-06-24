"""
india_weekly_snapshot.py — Weekly alignment + squeeze snapshot (India)
Reads UNIVERSE and WATCHLIST from india_screener.py, runs MA alignment and squeeze,
appends a dated markdown section to india_weekly_notes.md.
Run: python india_weekly_snapshot.py
"""

import sys, yfinance as yf, warnings, subprocess, os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
warnings.filterwarnings('ignore')

sys.path.insert(0, '.')
from india_screener import UNIVERSE, WATCHLIST

ALL = list(dict.fromkeys(UNIVERSE + WATCHLIST))

def disp(t):
    return t.replace('.NS', '').replace('.BO', '')

def ma_data(ticker):
    try:
        hist  = yf.Ticker(ticker).history(period='2y', interval='1wk')
        close = hist['Close'].dropna()
        vol   = hist['Volume'].dropna()
        if len(close) < 87:
            return None
        price = float(close.iloc[-1])
        ma10w = float(close.tail(10).mean())
        ma20w = float(close.tail(20).mean())
        ma10m = float(close.tail(43).mean())
        ma20m = float(close.tail(87).mean())
        ma35w = float(close.tail(35).mean())
        ma50w = float(close.tail(50).mean())

        score  = sum([price > ma10w, price > ma20w, price > ma10m, price > ma20m])
        spread = (max([ma10w, ma20w, ma35w, ma50w]) - min([ma10w, ma20w, ma35w, ma50w])) / price * 100
        st_gap = abs(ma10w - ma20w) / price * 100

        vol_ratio = 0
        if len(vol) >= 11:
            last_vol = float(vol.iloc[-2])
            avg_vol  = float(vol.iloc[-11:-1].mean())
            if avg_vol > 0:
                vol_ratio = round(last_vol / avg_vol, 2)

        slope = '↑' if ma10w > float(close.iloc[-15:-5].mean()) else '↓'

        return {
            'ticker':      ticker,
            'price':       round(price, 2),
            'score':       score,
            'spread':      round(spread, 1),
            'st_gap':      round(st_gap, 1),
            'vol':         round(vol_ratio, 1),
            'slope':       slope,
            'in_universe': ticker in UNIVERSE,
        }
    except:
        return None


if __name__ == '__main__':
    now   = datetime.now()
    label = now.strftime('Week of %b %d %Y')

    print(f'  Fetching {len(ALL)} India tickers ...', flush=True)
    with ThreadPoolExecutor(max_workers=20) as ex:
        raw = list(ex.map(ma_data, ALL))

    data      = [d for d in raw if d is not None]
    aligned_4 = sorted([d for d in data if d['score'] == 4], key=lambda x: disp(x['ticker']))
    aligned_3 = sorted([d for d in data if d['score'] == 3], key=lambda x: disp(x['ticker']))
    squeeze   = sorted([d for d in data if d['spread'] <= 5.0], key=lambda x: x['spread'])[:20]

    u4   = [disp(d['ticker']) for d in aligned_4 if d['in_universe']]
    w4   = [disp(d['ticker']) for d in aligned_4 if not d['in_universe']]
    near = [disp(d['ticker']) for d in aligned_3]

    lines = [f'## {label} (India)\n']

    lines.append(f'### 4/4 Aligned — {len(aligned_4)} names\n')
    if u4:
        lines.append(f'**Universe ({len(u4)}):** {", ".join(u4)}\n')
    if w4:
        lines.append(f'**Watchlist ({len(w4)}):** {", ".join(w4)}\n')

    if near:
        lines.append(f'\n### 3/4 Near-Aligned — {len(aligned_3)} names\n')
        lines.append(f'{", ".join(near)}\n')

    lines.append('\n### Tightest Coils — FullCoil ≤ 5%\n')
    lines.append('| Ticker | | MA | FullCoil | ST Gap | Vol | Slope |')
    lines.append('|--------|--|-----|---------|--------|-----|-------|')
    for d in squeeze:
        tag = 'U' if d['in_universe'] else 'W'
        lines.append(
            f"| **{disp(d['ticker'])}** | [{tag}] | {d['score']}/4 "
            f"| {d['spread']}% | {d['st_gap']}% | {d['vol']}x | {d['slope']} |"
        )

    lines.append('\n### Notes\n')
    lines.append('_Weekly observations — what to watch, what is coiling, what to avoid._\n')
    lines.append('\n> **Disclaimer:** For informational purposes only. Not financial advice.\n')
    lines.append('\n---\n')

    md = '\n'.join(lines)

    notes_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'india_weekly_notes.md')
    if not os.path.exists(notes_file):
        with open(notes_file, 'w') as f:
            f.write('# India Weekly Market Notes\n\n')
            f.write('Alignment + squeeze snapshots from the India quality screener universe.\n')
            f.write('Run `python india_weekly_snapshot.py` each week to append the latest entry.\n\n')
            f.write('---\n\n')

    existing = open(notes_file).read()
    if f'## {label}' in existing:
        print(f'  Already logged for {label} — skipping append')
    else:
        with open(notes_file, 'a') as f:
            f.write(md)
        print(f'  Appended → india_weekly_notes.md')
    print(f'  4/4: {len(aligned_4)}   3/4: {len(aligned_3)}   Coils ≤5%: {len([d for d in data if d["spread"] <= 5.0])}')

    try:
        repo       = os.path.dirname(notes_file)
        commit_msg = f'india_weekly_notes: {label}'
        subprocess.run(['git', 'add', 'india_weekly_notes.md'], cwd=repo, check=True, capture_output=True)
        subprocess.run(['git', 'commit', '-m', commit_msg],     cwd=repo, check=True, capture_output=True)
        subprocess.run(['git', 'push'],                          cwd=repo, check=True, capture_output=True)
        print(f'  Pushed → GitHub  ({commit_msg})')
    except subprocess.CalledProcessError as e:
        msg = e.stderr.decode().strip() if e.stderr else str(e)
        print(f'  Git push skipped: {msg or "nothing new to commit"}')
