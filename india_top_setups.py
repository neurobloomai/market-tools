"""
india_top_setups.py — Highest-conviction India convergence from last screener run.

Reads india_screener.html + india_aligned_screener.html (zero re-fetch for scoring).
For top 15, fetches monthly bars to compute MA10m/MA20m extension.

Usage: python3 india_top_setups.py
"""

import yfinance as yf
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor


# ── Parse quality grades + sectors ────────────────────────────────────────────

def load_grades(path='india_screener.html'):
    soup    = BeautifulSoup(open(path).read(), 'html.parser')
    grades  = {}
    sectors = {}
    for row in soup.find_all('tr'):
        cols = [td.get_text(strip=True) for td in row.find_all('td')]
        # cols: [ticker, name, sector, price, mktcap, grade, ...]
        if len(cols) >= 6 and cols[0] and cols[5] in ('A+', 'A', 'B'):
            grades[cols[0]]  = cols[5]
            sectors[cols[0]] = cols[2]
    return grades, sectors


# ── Parse aligned screener signals ────────────────────────────────────────────

def load_aligned(path='india_aligned_screener.html'):
    soup    = BeautifulSoup(open(path).read(), 'html.parser')
    signals      = {}
    aligned_4of4 = set()
    fullcoil     = set()
    grades_extra = {}   # grade from aligned screener (fallback for watchlist / failing names)
    section      = ''

    for tag in soup.find_all(['div', 'tr']):
        if tag.name == 'div':
            cls  = tag.get('class', [])
            text = tag.get_text(strip=True).lower()
            if 'sh' in cls or 'section-header' in cls or tag.get('class') == ['sh']:
                if '4/4 aligned' in text:
                    section = '4of4'
                elif 'weekly squeeze' in text and 'fullcoil' in text:
                    section = 'coil'
                elif any(x in text for x in ['3/4 near', 'promotion', 'special mention',
                                              'pullback', 'st squeeze', 'daily squeeze',
                                              'monthly squeeze']):
                    section = 'other'
            continue

        if tag.name != 'tr':
            continue

        cols = [td.get_text(strip=True) for td in tag.find_all('td')]
        if len(cols) < 4:
            continue

        if section == '4of4' and len(cols) >= 8:
            # [list_tag, ticker, grade, price, RS, offHi, CMF, AD+OBV]
            if cols[0] not in ('[U]', '[W]'):
                continue
            ticker  = cols[1].strip()
            grade   = cols[2].strip()
            if grade in ('A+', 'A', 'B'):
                grades_extra[ticker] = grade
            rs_raw  = cols[4]
            cmf_raw = cols[6]
            adObv   = cols[7]
            try:    rs  = float(rs_raw.replace('x', ''))
            except: rs  = None
            try:    cmf = float(cmf_raw)
            except: cmf = None
            ad   = adObv[0] if len(adObv) > 0 else ''
            obv  = adObv[1] if len(adObv) > 1 else ''
            bull = '◆' in adObv
            bear = '◇' in adObv
            signals[ticker] = {'rs': rs, 'cmf': cmf, 'ad': ad, 'obv': obv, 'bull': bull, 'bear': bear}
            aligned_4of4.add(ticker)

        elif section == 'coil' and len(cols) >= 8:
            # [ticker, list_tag, ma_count, price, spread, slope, CMF, RS, offHi, ...]
            if cols[1] not in ('[U]', '[W]'):
                continue
            ticker  = cols[0].strip()
            cmf_raw = cols[6]
            rs_raw  = cols[7]
            try:    rs  = float(rs_raw.replace('x', ''))
            except: rs  = None
            try:    cmf = float(cmf_raw)
            except: cmf = None
            if ticker not in signals:
                signals[ticker] = {'rs': rs, 'cmf': cmf, 'ad': '', 'obv': '', 'bull': False, 'bear': False}
            fullcoil.add(ticker)

    return signals, aligned_4of4, fullcoil, grades_extra


# ── Score ──────────────────────────────────────────────────────────────────────

def score(ticker, grade, sig, is_4of4, is_coil):
    s       = 0
    reasons = []

    if grade == 'A+':  s += 2; reasons.append('A+')
    elif grade == 'A': s += 1; reasons.append('A')

    if is_4of4: s += 2; reasons.append('4/4')
    if is_coil: s += 1; reasons.append('coil')

    if sig:
        rs = sig.get('rs')
        if rs and rs >= 1.10:  s += 2; reasons.append(f'RS {rs:.2f}x')
        elif rs and rs >= 1.0: s += 1; reasons.append(f'RS {rs:.2f}x')

        cmf = sig.get('cmf')
        if cmf and cmf >= 0.10:  s += 2; reasons.append(f'CMF {cmf:+.2f}')
        elif cmf and cmf > 0:    s += 1; reasons.append(f'CMF {cmf:+.2f}')

        if sig.get('ad') == '↑':  s += 1; reasons.append('A/D ↑')
        if sig.get('obv') == '↑': s += 1; reasons.append('OBV ↑')
        if sig.get('bull'):       s += 1; reasons.append('◆ bull div')

    return s, reasons


# ── Monthly MA extension ───────────────────────────────────────────────────────

def monthly_extension(ticker):
    """Returns (pct_above_ma10m, pct_above_ma20m) or (None, None)."""
    try:
        t     = yf.Ticker(f'{ticker}.NS')
        mo    = t.history(period='5y', interval='1mo', prepost=False)['Close'].dropna()
        dy    = t.history(period='1y', interval='1d',  prepost=False)['Close'].dropna()
        if len(mo) < 22 or len(dy) < 2:
            return None, None
        price = float(dy.iloc[-1])
        m10m  = float(mo.rolling(10).mean().iloc[-2])
        m20m  = float(mo.rolling(20).mean().iloc[-2])
        return (price / m10m - 1) * 100, (price / m20m - 1) * 100
    except Exception:
        return None, None


def extension_label(pct):
    """Fixed 8-char label. sym(2) + num right-padded to 6."""
    if pct is None:
        return '       —'
    num  = f'{pct:+.0f}%'
    num6 = f'{num:>6}'
    sym  = '⚠ ' if pct > 50 else ('↑ ' if pct > 25 else '  ')
    return f'{sym}{num6}'


# ── Sector shorthand ──────────────────────────────────────────────────────────

SECTOR_SHORT = {
    'Industrials':          'Industrials',
    'Technology':           'IT / Tech',
    'Information':          'IT / Tech',
    'Healthcare':           'Pharma / Health',
    'Consumer Defensive':   'Consumer Def',
    'Consumer Cyclical':    'Consumer Cyc',
    'Financial Services':   'Financials',
    'Financial':            'Financials',
    'Energy':               'Energy',
    'Basic Materials':      'Materials',
    'Communication':        'Telecom',
    'Real Estate':          'Real Estate',
    'Utilities':            'Utilities',
}

def short_sector(raw):
    for key, val in SECTOR_SHORT.items():
        if key.lower() in raw.lower():
            return val
    return raw[:14]


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    grades, sectors           = load_grades()
    signals, f4, coil, g_ext = load_aligned()

    # Merge: quality_screener grades are primary; aligned_screener grades fill gaps
    # (watchlist names and universe-failing names that still show up in aligned)
    merged_grades = {**g_ext, **grades}   # grades overrides g_ext

    all_tickers = set(merged_grades) | set(signals)

    scored = []
    for t in all_tickers:
        g   = merged_grades.get(t, '')
        sig = signals.get(t)
        sc, reasons = score(t, g, sig, t in f4, t in coil)
        if sc > 0:
            # Tag watchlist names so they're visible
            tag = ' [W]' if t not in grades and t in g_ext else ''
            scored.append((t, sc, g, reasons, tag))

    scored.sort(key=lambda x: (-x[1], x[0]))
    top = scored[:15]

    print('  Fetching monthly MA data for top 15 ...', flush=True)
    top_tickers = [t for t, *_ in top]
    with ThreadPoolExecutor(max_workers=8) as ex:
        ext_results = list(ex.map(monthly_extension, top_tickers))
    ext_map = dict(zip(top_tickers, ext_results))

    W = 102
    print(f"\n{'─'*W}")
    print(f"  INDIA TOP SETUPS — quality · alignment · volume convergence  ({len(scored)} names scored)")
    print(f"{'─'*W}")
    print(f"  {'Ticker':<14}  {'Sc':>2}  {'Gr':<3}  {'Sector':<15}  {'MA10m':>8}  {'MA20m':>8}  Signals")
    print(f"  {'─'*14}  {'─'*2}  {'─'*3}  {'─'*15}  {'─'*8}  {'─'*8}  {'─'*32}")

    for t, sc, g, reasons, tag in top:
        p10m, p20m = ext_map.get(t, (None, None))
        l10     = extension_label(p10m)
        l20     = extension_label(p20m)
        sec     = short_sector(sectors.get(t, ''))
        label   = f'{t}{tag}'
        gr_str  = g if g else '—'
        sig_str = ' · '.join(reasons)
        print(f"  {label:<14}  {sc:>2}  {gr_str:<3}  {sec:<15}  {l10}  {l20}  {sig_str}")

    print(f"{'─'*W}")
    print(f"  ⚠ >50% above monthly MA = wary  ·  ↑ 25–50%  ·  [W] = watchlist  ·  RS vs NIFTY  ·  not financial advice\n")
