"""
weekly_snapshot.py — Weekly alignment + squeeze snapshot
Reads UNIVERSE and WATCHLIST from screener.py, runs MA alignment and squeeze,
overwrites weekly_notes.md with the current week's snapshot.
History is preserved in git — each run creates a new commit.
Run: python weekly_snapshot.py
"""

import sys, os, re, json, yfinance as yf, warnings
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path
warnings.filterwarnings('ignore')

HISTORY_FILE = Path(__file__).parent / 'breadth_history.json'

TIER_ORDER = [
    'fully_stacked', 'trend_intact', 'stacked_100',
    'all4_up', 'ma20_50_100', 'ma20_50', 'ma20_only',
    'ma100_200', 'ma200_pullbk', 'none',
]
TIER_LABEL = {
    'fully_stacked': '✦ Fully Stacked',
    'trend_intact':  '◇ Trend Intact',
    'stacked_100':   '◈ Intermediate',
    'all4_up':       'All4 (unordered)',
    'ma20_50_100':   'MA50+100',
    'ma20_50':       'MA50',
    'ma20_only':     'MA20 only',
    'ma100_200':     'MA100+MA200',
    'ma200_pullbk':  'MA200 only',
    'none':          'Below all',
}

def _tier(price, ma4, ma10, ma20, ma40):
    """Breadth tier from approximate weekly-MA equivalents of daily MAs."""
    if None in (ma4, ma10, ma20, ma40):
        return 'unknown'
    if price > ma4 > ma10 > ma20 > ma40:
        return 'fully_stacked'
    if price > ma10 > ma20 > ma40:
        return 'trend_intact'
    if price > ma4 > ma10 > ma20:
        return 'stacked_100'
    if price > ma4 and price > ma10 and price > ma20 and price > ma40:
        return 'all4_up'
    if price > ma4 and price > ma10 and price > ma20:
        return 'ma20_50_100'
    if price > ma4 and price > ma10:
        return 'ma20_50'
    if price > ma4:
        return 'ma20_only'
    if price > ma20 and price > ma40:   # ma20 here = ma20w ≈ MA100d
        return 'ma100_200'
    if price > ma40:
        return 'ma200_pullbk'
    return 'none'

sys.path.insert(0, '.')
from screener import UNIVERSE, WATCHLIST, get_fundamentals, quality_grade, failing_filters
from ma_scanner import liquid_panel_md, liquid_status, LIQUID_NAMES
from notes_renderer import md_to_html

ALL = list(dict.fromkeys(UNIVERSE + WATCHLIST))


def ma_data(ticker):
    try:
        hist  = yf.Ticker(ticker).history(period='2y', interval='1wk')
        close = hist['Close'].dropna()
        vol   = hist['Volume'].dropna()
        if len(close) < 87:
            return None
        price = float(close.iloc[-1])
        ma4w  = float(close.tail(4).mean())   # ≈ MA20d
        ma10w = float(close.tail(10).mean())  # ≈ MA50d
        ma20w = float(close.tail(20).mean())  # ≈ MA100d
        ma40w = float(close.tail(40).mean())  # ≈ MA200d
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

        slope = '↑' if ma10w > float(close.tail(15).mean()) else '↓'

        return {
            'ticker':      ticker,
            'price':       round(price, 2),
            'score':       score,
            'spread':      round(spread, 1),
            'st_gap':      round(st_gap, 1),
            'vol':         round(vol_ratio, 1),
            'slope':       slope,
            'in_universe': ticker in UNIVERSE,
            'tier':        _tier(price, ma4w, ma10w, ma20w, ma40w),
        }
    except:
        return None


def parse_watchlist_notes():
    """Parse per-ticker thesis from inline comments in screener.py WATCHLIST."""
    src = (Path(__file__).parent / 'screener.py').read_text()
    notes = {}
    for ticker in WATCHLIST:
        m = re.search(rf"^\s+'{re.escape(ticker)}',[ \t]+#[ \t]+(.+)$", src, re.MULTILINE)
        if m:
            notes[ticker] = m.group(1).strip()
    return notes


if __name__ == '__main__':
    now   = datetime.utcnow()
    # Anchor label to Monday of current week (consistent regardless of run day/time)
    monday = now - timedelta(days=now.weekday())
    label  = monday.strftime('Week of %b %d %Y')

    print(f'  Fetching {len(ALL)} tickers ...', flush=True)
    with ThreadPoolExecutor(max_workers=20) as ex:
        raw = list(ex.map(ma_data, ALL))

    data      = [d for d in raw if d is not None]
    aligned_4 = sorted([d for d in data if d['score'] == 4], key=lambda x: x['ticker'])
    aligned_3 = sorted([d for d in data if d['score'] == 3], key=lambda x: x['ticker'])
    squeeze   = sorted([d for d in data if d['spread'] <= 5.0], key=lambda x: x['spread'])[:20]

    u4   = [d['ticker'] for d in aligned_4 if d['in_universe']]
    w4   = [d['ticker'] for d in aligned_4 if not d['in_universe']]
    near = [d['ticker'] for d in aligned_3]

    # ── Traceability: tier snapshot + week-over-week movements ───────────────
    current_tiers = {d['ticker']: d['tier'] for d in data if d.get('tier') != 'unknown'}

    history = json.loads(HISTORY_FILE.read_text()) if HISTORY_FILE.exists() else []
    prev_tiers = history[-1]['tiers'] if history else {}

    movements = {
        t: (prev_tiers[t], cur)
        for t, cur in current_tiers.items()
        if t in prev_tiers and prev_tiers[t] != cur and cur != 'unknown'
    }

    history.append({
        'week':  label,
        'date':  monday.strftime('%Y-%m-%d'),
        'tiers': current_tiers,
    })
    HISTORY_FILE.write_text(json.dumps(history, indent=2))

    lines = [f'## {label}\n']

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
            f"| **{d['ticker']}** | [{tag}] | {d['score']}/4 "
            f"| {d['spread']}% | {d['st_gap']}% | {d['vol']}x | {d['slope']} |"
        )

    lines.append('\n### Notes\n')
    lines.append('_Weekly observations — what to watch, what is coiling, what to avoid._\n')
    lines.append('\n> **Disclaimer:** For informational purposes only. Not financial advice.\n')

    # ── Tier Movements ───────────────────────────────────────────────────────
    lines.append('\n### Tier Movements — Week over Week\n')
    if not prev_tiers:
        lines.append('_First run — no previous week to compare._\n')
    elif not movements:
        lines.append('_No tier changes this week._\n')
    else:
        improved  = sorted([(t, p, c) for t, (p, c) in movements.items()
                            if TIER_ORDER.index(c) < TIER_ORDER.index(p)],
                           key=lambda x: TIER_ORDER.index(x[2]))
        downgraded = sorted([(t, p, c) for t, (p, c) in movements.items()
                             if TIER_ORDER.index(c) > TIER_ORDER.index(p)],
                            key=lambda x: TIER_ORDER.index(x[1]))
        if improved:
            parts = ', '.join(f"**{t}** ({TIER_LABEL[p]} → {TIER_LABEL[c]})" for t, p, c in improved)
            lines.append(f'↑ **Improved:** {parts}\n')
        if downgraded:
            parts = ', '.join(f"**{t}** ({TIER_LABEL[p]} → {TIER_LABEL[c]})" for t, p, c in downgraded)
            lines.append(f'↓ **Dropped:** {parts}\n')

    # ── Watchlist Status ──────────────────────────────────────────────────────
    print(f'  Fetching fundamentals for {len(WATCHLIST)} watchlist tickers ...', flush=True)
    with ThreadPoolExecutor(max_workers=10) as ex:
        wl_funds = dict(zip(WATCHLIST, ex.map(get_fundamentals, WATCHLIST)))

    wl_map   = {d['ticker']: d for d in data if d['ticker'] in WATCHLIST}
    notes    = parse_watchlist_notes()
    wl_order = sorted(WATCHLIST, key=lambda t: (-wl_map.get(t, {}).get('score', 0), t))

    # Save watchlist snapshot for newsletter_draft.py
    wl_snap = {}
    for t in WATCHLIST:
        f = wl_funds.get(t)
        if f:
            fails = failing_filters(f)
            wl_snap[t] = {
                'fails': [[n, v, th] for n, v, th in fails] if fails else [],
                'note':  notes.get(t, ''),
                'grade': quality_grade(f),
            }
    Path(HISTORY_FILE.parent / 'watchlist_snapshot.json').write_text(json.dumps(wl_snap, indent=2))
    print(f'  Saved → watchlist_snapshot.json')

    lines.append('\n### Watchlist Status\n')
    lines.append('| Ticker | Price | MA | Grade | Blockers | Thesis |')
    lines.append('|:-------|------:|:--:|:-----:|:---------|:-------|')

    for t in wl_order:
        md  = wl_map.get(t)
        price_str = f"${md['price']:.2f}" if md else '—'
        ma_str    = f"{md['score']}/4"    if md else '—'
        f = wl_funds.get(t)
        if f:
            grade    = quality_grade(f)
            fails    = failing_filters(f)
            blockers = ' / '.join(f"{n} {v}" for n, v, _ in fails) if fails else '—'
        else:
            grade    = 'ETF'
            blockers = '—'
        thesis = notes.get(t, '—')
        thesis_md = (thesis[:70] + '…') if len(thesis) > 70 else thesis
        lines.append(f"| **{t}** | {price_str} | {ma_str} | {grade} | {blockers} | {thesis_md} |")

    header = (
        '# Weekly Market Notes\n\n'
        'Current week snapshot — MA alignment, squeeze setups, and watchlist status.\n'
        'Run `python weekly_snapshot.py` each week to refresh. History is in git.\n\n'
        '---\n\n'
    )

    print(f'  Fetching liquid names panel ...', flush=True)
    with ThreadPoolExecutor(max_workers=8) as ex:
        liquid_rows = list(ex.map(liquid_status, LIQUID_NAMES))
    setups_snap = []
    for row in liquid_rows:
        if row is None:
            continue
        sym, price, w_gate, pct20d, pct10w, m10w, m50d, band, slope, w_gap = row
        if band != 'DATA?':
            setups_snap.append(dict(
                ticker=sym, price=price, w_gate=bool(w_gate),
                pct20d=round(pct20d, 2) if pct20d is not None else None,
                pct10w=round(pct10w, 2) if pct10w is not None else None,
                band=band,
                slope=round(slope, 2) if slope is not None else None,
                w_gap=round(w_gap, 1) if w_gap is not None else None,
                in_universe=sym in UNIVERSE,
            ))
    Path(HISTORY_FILE.parent / 'setups_snapshot.json').write_text(json.dumps(setups_snap, indent=2))
    print(f'  Saved → setups_snapshot.json')

    from ma_scanner import liquid_panel_md as _liquid_md
    md = header + '\n'.join(lines) + '\n' + _liquid_md()

    with open('weekly_notes.md', 'w') as f:
        f.write(md)
    print(f'  Written → weekly_notes.md  ({label})')

    html = md_to_html(md, title=f'US Weekly Notes — {label}')
    with open('weekly_notes.html', 'w') as f:
        f.write(html)
    print(f'  Written → weekly_notes.html  ({label})')
    print(f'  4/4: {len(aligned_4)}   3/4: {len(aligned_3)}   Coils ≤5%: {len([d for d in data if d["spread"] <= 5.0])}')

    import subprocess
    try:
        commit_msg = f'weekly_notes: {label}'
        subprocess.run(['git', 'add', 'weekly_notes.md', 'weekly_notes.html', 'breadth_history.json'], check=True, capture_output=True)
        subprocess.run(['git', 'commit', '-m', commit_msg], check=True, capture_output=True)
        subprocess.run(['git', 'push'], check=True, capture_output=True)
        print(f'  Pushed → GitHub  ({commit_msg})')
    except subprocess.CalledProcessError as e:
        msg = e.stderr.decode().strip() if e.stderr else str(e)
        print(f'  Git push skipped: {msg or "nothing new to commit"}')
