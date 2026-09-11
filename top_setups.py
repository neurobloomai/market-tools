"""
top_setups.py — Highest-conviction convergence from last run outputs.

Reads already-generated HTML (no re-fetch from Yahoo Finance) for scoring.
For the top 20 results, fetches monthly bars to compute distance from
MA10m and MA20m — so overextended names are immediately visible.

Usage: python3 top_setups.py
"""

import re
import yfinance as yf
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor
from ma_scanner import LIQUID_NAMES

EXCLUDE = set(LIQUID_NAMES)  # NVDA META MSFT AAPL AMZN GOOGL AVGO MU NFLX


# ── ANSI helpers (same palette as pop_scan.py) ─────────────────────────────────
_G   = '\033[92m'   # bright green  — good
_Y   = '\033[93m'   # bright yellow — slightly good / building
_R   = '\033[91m'   # bright red    — wary / caution
_DIM = '\033[2m'     # dim           — okay / below par / structural text
_RST = '\033[0m'

_ANSI_RE = re.compile(r'\033\[[0-9;]*m')

def _vlen(s):
    return len(_ANSI_RE.sub('', s))

def _rpad(s, w):
    """Left-align s in w visible characters (ignores ANSI codes when measuring)."""
    return s + ' ' * max(0, w - _vlen(s))

def _c(color, text):
    return f'{color}{text}{_RST}'


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
        # strip badge chars (●, ○, ★ etc.) that aligned_screener injects into ticker cells
        ticker = re.sub(r'[^A-Z0-9\-]', '', cols[1].strip().upper())
        if not ticker or ticker == 'TICKER':
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
        s += 2
    elif grade == 'A':
        s += 1

    if is_4of4:
        s += 2; reasons.append(_c(_G, '4/4 aligned'))
    if is_coil:
        s += 1; reasons.append(_c(_Y, 'coil'))

    if sig:
        rs = sig.get('rs')
        if rs is not None:
            color = _G if rs >= 1.10 else _Y if rs >= 1.0 else _DIM
            reasons.append(_c(color, f'RS {rs:.2f}x'))
            if rs >= 1.10:
                s += 2
            elif rs >= 1.0:
                s += 1

        cmf = sig.get('cmf')
        if cmf is not None:
            color = _G if cmf >= 0.10 else _Y if cmf > 0 else _DIM
            reasons.append(_c(color, f'CMF {cmf:+.2f}'))
            if cmf >= 0.10:
                s += 2
            elif cmf > 0:
                s += 1

        if sig.get('ad') == '↑':
            s += 1; reasons.append(_c(_G, 'A/D ↑'))
        if sig.get('obv') == '↑':
            s += 1; reasons.append(_c(_G, 'OBV ↑'))
        if sig.get('bull'):
            s += 1

    bull_div = bool(sig and sig.get('bull'))
    return s, reasons, bull_div


# ── Monthly MA distance (fetch only top N) ────────────────────────────────────

def monthly_extension(ticker):
    """Returns (price, pct_above_ma10m, pct_above_ma20m) or (None, None, None) on failure."""
    try:
        mo    = yf.Ticker(ticker).history(period='5y', interval='1mo', prepost=False)['Close'].dropna()
        dy    = yf.Ticker(ticker).history(period='1y',  interval='1d',  prepost=False)['Close'].dropna()
        if len(mo) < 22 or len(dy) < 2:
            return None, None, None
        price = float(dy.iloc[-1])
        m10m  = float(mo.rolling(10).mean().iloc[-2])
        m20m  = float(mo.rolling(20).mean().iloc[-2])
        return price, (price / m10m - 1) * 100, (price / m20m - 1) * 100
    except:
        return None, None, None


PRICE_W = 10

def price_label(price):
    """Fixed 10-char right-aligned price, e.g. ' $1,016.59' or '         —'."""
    if price is None:
        return f'{"—":>{PRICE_W}}'
    return f'{f"${price:,.2f}":>{PRICE_W}}'


def extension_label(pct):
    """Fixed 8-char label for monthly MA distance. sym(2) + num right-padded to 6."""
    if pct is None:
        return '       —'          # 7 spaces + em-dash = 8 chars
    num = f'{pct:+.0f}%'          # e.g. "+70%" or "+102%"
    num6 = f'{num:>6}'            # right-aligned to 6 chars: "  +70%" or " +102%"
    if pct > 50:
        sym, color = '⚠︎ ', _R    # ⚠ (VS15 = force narrow text glyph) + space = 2 cols — wary
    elif pct > 25:
        sym, color = '↑︎ ', _Y    # ↑ (VS15 = force narrow text glyph) + space = 2 cols — building
    else:
        sym, color = '  ', _G     # 2 spaces — healthy, room to run
    return _c(color, f'{sym}{num6}')   # always 8 display columns (ANSI + VS15 are zero-width)


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
        sc, reasons, bull_div = score(t, g, sig, t in f4, t in coil)
        if sc > 0:
            scored.append((t, sc, g, reasons, bull_div))

    scored.sort(key=lambda x: -x[1])
    top = scored[:20]
    max_sc = max((sc for _, sc, *_ in top), default=0)

    # Fetch monthly extension for top 20 in parallel
    print('  Fetching monthly MA data for top 20 ...', flush=True)
    top_tickers = [t for t, *_ in top]
    with ThreadPoolExecutor(max_workers=10) as ex:
        ext_results = list(ex.map(monthly_extension, top_tickers))
    ext_map = dict(zip(top_tickers, ext_results))

    rows = []
    for t, sc, g, reasons, bull_div in top:
        price, p10m, p20m = ext_map.get(t, (None, None, None))
        price_s = price_label(price)  # 10 visible cols, fixed
        l10 = extension_label(p10m)   # 8 visible cols, fixed
        l20 = extension_label(p20m)   # 8 visible cols, fixed
        sig_str = ' · '.join(reasons)

        sc_color = _G if sc == max_sc else _Y if sc >= max_sc - 1 else _DIM
        sc_s = _c(sc_color, f'{sc:>2}')

        g_color = _G if g == 'A+' else _Y if g == 'A' else ''
        g_s = _c(g_color, f'{g:<3}') if g_color else f'{g:<3}'

        div_str = _c(_G, '◆ bull') if bull_div else ''

        rows.append((t, price_s, sc_s, g_s, l10, l20, sig_str, div_str))

    SIG_W = max((_vlen(r[6]) for r in rows), default=8)

    W = 94
    print(f"\n{_DIM}{'─'*W}{_RST}")
    print(f"  {_DIM}TOP SETUPS — quality · alignment · volume convergence{_RST}")
    print(f"  {_DIM}Excl: {', '.join(sorted(EXCLUDE))}{_RST}")
    print(f"{_DIM}{'─'*W}{_RST}")
    print(f"  {_DIM}{'Ticker':<8}  {'Price':>{PRICE_W}}  {'Sc':>2}  {'Gr':<3}  {'MA10m (mo)':>10}  {'MA20m (mo)':>10}  {'Signals':<{SIG_W}}  Div{_RST}")
    print(f"  {_DIM}{'─'*8}  {'─'*PRICE_W}  {'─'*2}  {'─'*3}  {'─'*10}  {'─'*10}  {'─'*SIG_W}  {'─'*6}{_RST}")

    for t, price_s, sc_s, g_s, l10, l20, sig_str, div_str in rows:
        print(f"  {t:<8}  {price_s}  {sc_s}  {g_s}  {l10}    {l20}  {_rpad(sig_str, SIG_W)}  {div_str}")

    print(f"{_DIM}{'─'*W}{_RST}")
    print(f"  {_DIM}⚠ >50% above monthly MA = wary  ·  ↑ 25–50%  ·  {len(scored)} names scored  ·  not financial advice{_RST}\n")
