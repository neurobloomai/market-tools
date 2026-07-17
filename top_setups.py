"""
top_setups.py — Highest-conviction convergence from last run outputs.

Reads already-generated HTML (no re-fetch from Yahoo Finance) for scoring.
For the top 20 results, fetches monthly bars to compute distance from
MA10m and MA20m — so overextended names are immediately visible.

Usage: python3 top_setups.py
"""

import yfinance as yf
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor
from ma_scanner import LIQUID_NAMES

EXCLUDE = set(LIQUID_NAMES)  # NVDA META MSFT AAPL AMZN GOOGL AVGO MU NFLX


# ── Parse quality grades ───────────────────────────────────────────────────────

def load_grades(path='quality_screener.html'):
    soup = BeautifulSoup(open(path).read(), 'html.parser')
    grades = {}
    for row in soup.find_all('tr'):
        cols = [td.get_text(strip=True) for td in row.find_all('td')]
        if len(cols) >= 6 and cols[0] and cols[5] in ('A+', 'A', 'B'):
            grades[cols[0]] = cols[5]
    return grades


# ── Parse aligned screener signals ────────────────────────────────────────────

def load_aligned(path='aligned_screener.html'):
    soup = BeautifulSoup(open(path).read(), 'html.parser')

    # Detect 4/4 aligned and FullCoil names from section headers
    aligned_4of4  = set()
    fullcoil      = set()
    current_section = ''

    signals = {}  # ticker → {rs, cmf, ad, obv, bull, bear}

    for tag in soup.find_all(['h2', 'h3', 'tr']):
        if tag.name in ('h2', 'h3'):
            current_section = tag.get_text(strip=True).lower()
            continue

        cols = [td.get_text(strip=True) for td in tag.find_all('td')]
        if len(cols) < 7:
            continue

        # cols: [list_tag, ticker, grade, price, rs, pct52wH, cmf, adObv]
        ticker = cols[1].strip()
        if not ticker or ticker == 'Ticker':
            continue

        rs_raw  = cols[4]   # e.g. "1.16x"
        cmf_raw = cols[6]   # e.g. "+0.15"
        adObv   = cols[7]   # e.g. "↑↑" "↑↓◆" "↓↓◇"

        try:
            rs  = float(rs_raw.replace('x', ''))
        except:
            rs  = None
        try:
            cmf = float(cmf_raw)
        except:
            cmf = None

        ad   = adObv[0] if len(adObv) > 0 else ''
        obv  = adObv[1] if len(adObv) > 1 else ''
        bull = '◆' in adObv
        bear = '◇' in adObv

        signals[ticker] = {
            'rs': rs, 'cmf': cmf,
            'ad': ad, 'obv': obv,
            'bull': bull, 'bear': bear,
        }

        if '4/4' in current_section or 'full alignment' in current_section:
            aligned_4of4.add(ticker)
        if 'coil' in current_section or 'squeeze' in current_section:
            fullcoil.add(ticker)

    return signals, aligned_4of4, fullcoil


# ── Score each name ────────────────────────────────────────────────────────────

def score(ticker, grade, sig, is_4of4, is_coil):
    s = 0
    reasons = []

    if grade == 'A+':
        s += 2; reasons.append('A+')
    elif grade == 'A':
        s += 1; reasons.append('A')

    if is_4of4:
        s += 2; reasons.append('4/4 aligned')
    if is_coil:
        s += 1; reasons.append('coil')

    if sig:
        rs = sig.get('rs')
        if rs and rs >= 1.10:
            s += 2; reasons.append(f'RS {rs:.2f}x')
        elif rs and rs >= 1.0:
            s += 1; reasons.append(f'RS {rs:.2f}x')

        cmf = sig.get('cmf')
        if cmf and cmf >= 0.10:
            s += 2; reasons.append(f'CMF {cmf:+.2f}')
        elif cmf and cmf > 0:
            s += 1; reasons.append(f'CMF {cmf:+.2f}')

        if sig.get('ad') == '↑':
            s += 1; reasons.append('A/D ↑')
        if sig.get('obv') == '↑':
            s += 1; reasons.append('OBV ↑')
        if sig.get('bull'):
            s += 1; reasons.append('◆ bull div')

    return s, reasons


# ── Monthly MA distance (fetch only top N) ────────────────────────────────────

def monthly_extension(ticker):
    """Returns (pct_above_ma10m, pct_above_ma20m) or (None, None) on failure."""
    try:
        mo    = yf.Ticker(ticker).history(period='5y', interval='1mo', prepost=False)['Close'].dropna()
        dy    = yf.Ticker(ticker).history(period='1y',  interval='1d',  prepost=False)['Close'].dropna()
        if len(mo) < 22 or len(dy) < 2:
            return None, None
        price = float(dy.iloc[-1])
        m10m  = float(mo.rolling(10).mean().iloc[-2])
        m20m  = float(mo.rolling(20).mean().iloc[-2])
        return (price / m10m - 1) * 100, (price / m20m - 1) * 100
    except:
        return None, None


def extension_label(pct):
    """Traffic-light label for monthly MA distance."""
    if pct is None:
        return '  —  '
    if pct > 50:
        return f'⚠ {pct:+.0f}%'   # very extended — be wary
    if pct > 25:
        return f'↑ {pct:+.0f}%'   # extended
    if pct > 0:
        return f'  {pct:+.0f}%'   # above but reasonable
    return f'  {pct:+.0f}%'       # below monthly MA — deep value zone


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    grades            = load_grades()
    signals, f4, coil = load_aligned()

    all_tickers = set(grades) | set(signals)
    all_tickers -= EXCLUDE

    scored = []
    for t in all_tickers:
        g   = grades.get(t, '')
        sig = signals.get(t)
        sc, reasons = score(t, g, sig, t in f4, t in coil)
        if sc > 0:
            scored.append((t, sc, g, reasons))

    scored.sort(key=lambda x: -x[1])
    top = scored[:20]

    # Fetch monthly extension for top 20 in parallel
    print('  Fetching monthly MA data for top 20 ...', flush=True)
    top_tickers = [t for t, *_ in top]
    with ThreadPoolExecutor(max_workers=10) as ex:
        ext_results = list(ex.map(monthly_extension, top_tickers))
    ext_map = dict(zip(top_tickers, ext_results))

    print(f"\n{'─'*82}")
    print(f"  TOP SETUPS — convergence across quality + alignment + volume")
    print(f"  Excluding: {', '.join(sorted(EXCLUDE))}")
    print(f"{'─'*82}")
    print(f"  {'Ticker':<8} {'Sc':>3}  {'Gr':<3}  {'vsMA10m':>8}  {'vsMA20m':>8}  Signals")
    print(f"  {'─'*7} {'─'*3}  {'─'*3}  {'─'*8}  {'─'*8}  {'─'*42}")

    for t, sc, g, reasons in top:
        p10m, p20m = ext_map.get(t, (None, None))
        l10 = extension_label(p10m)
        l20 = extension_label(p20m)
        sig_str = ' · '.join(reasons)
        print(f"  {t:<8} {sc:>3}  {g:<3}  {l10:>8}  {l20:>8}  {sig_str}")

    print(f"{'─'*82}")
    print(f"  ⚠ = >50% above monthly MA — wary zone  ·  {len(scored)} names scored  ·  not financial advice\n")
