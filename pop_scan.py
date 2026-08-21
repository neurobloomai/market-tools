"""
Daily Pop Scanner — on-demand internal tool.

Checks price vs 10d / 20d / 50d daily MAs across our full universe.
Useful for spotting M&A burst pops, momentum setups, and sudden breakouts.

Usage:
  python pop_scan.py               # scan full UNIVERSE + WATCHLIST
  python pop_scan.py MKTX NVDA     # scan specific tickers (CLI, no browser)
  python pop_scan.py --universe    # universe only
  python pop_scan.py --watchlist   # watchlist only
  python pop_scan.py --top10       # top 10 setups ranked by composite score
  python pop_scan.py --top20       # top 20 setups (any N works: --top5, --top15 ...)
  python pop_scan.py --mega10      # top 10 from mega-cap list only (~30s, more reliable)
  python pop_scan.py --mega20      # top 20 from mega-cap list
"""

import json
import os
import sys
import types
import warnings
import webbrowser
import yfinance as yf
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

warnings.filterwarnings('ignore')

# mock _yf_cache so screener.py imports cleanly without requests_cache installed
sys.modules.setdefault('_yf_cache', types.ModuleType('_yf_cache'))

from screener import UNIVERSE, WATCHLIST
from regime import get_regime, regime_html, sizing_signal, REGIME_CSS
from event_risk import get_earnings_batch, earnings_cli, earnings_html_badge, EVENT_CSS

_CACHE_FILE       = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'screener_data_cache.json')
_GRADE_CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'grade_cache.json')

def _load_grade_cache():
    try:
        with open(_GRADE_CACHE_FILE) as f:
            return json.load(f)
    except Exception:
        return {}

def _save_grade_cache(new_grades):
    existing = _load_grade_cache()
    existing.update({k: v for k, v in new_grades.items() if v is not None})
    try:
        with open(_GRADE_CACHE_FILE, 'w') as f:
            json.dump(existing, f, indent=2)
    except Exception:
        pass

# Market pulse list — names to quick-scan with --mega10/--mega20
# Covers: user positions + spread universe + key QQQ/SPY movers
MEGA_CAP = [
    # Semis + equipment
    'MU', 'AMD', 'NVDA', 'AVGO', 'QCOM', 'INTC', 'AMAT',
    # Mega-cap tech (QQQ drivers)
    'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'TSLA', 'NFLX', 'CSCO',
    # Financials
    'JPM', 'V', 'MA', 'GS',
    # Healthcare / Pharma
    'LLY', 'ABBV', 'UNH', 'JNJ',
    # Energy
    'XOM',
    # Consumer + Industrials
    'HD', 'COST', 'ADP', 'WMT',
    # Indices (structure read)
    'SPY', 'QQQ', 'IWM',
]

def _load_grades():
    try:
        with open(_CACHE_FILE) as f:
            cache = json.load(f)
        grades = {}
        for t, d in cache.items():
            if not d:
                continue
            om  = d.get('operating_margin') or 0
            nm  = d.get('net_margin') or 0
            roe = d.get('roe') or 0
            dev = d.get('debt_to_ev') or 1
            fcf = d.get('fcf_yield') or 0
            gm  = d.get('gross_margin') or 0
            rg  = d.get('rev_growth') or 0
            passes = om >= 0.10 and nm >= 0.05 and roe >= 0.10 and dev <= 0.20 and fcf > 0
            if not passes:
                grades[t] = None
                continue
            aplus = (dev <= 0.03 and om >= 0.20 and nm >= 0.10 and roe >= 0.20
                     and fcf >= 0.02 and gm >= 0.60 and rg >= 0.05)
            a     = (dev <= 0.10 and om >= 0.15 and nm >= 0.08 and roe >= 0.15 and fcf >= 0.01)
            grades[t] = 'A+' if aplus else ('A' if a else 'B')
        return grades
    except Exception:
        return {}

def _range_band(pct50):
    if 1 <= pct50 <= 6:
        return 3, 'gold',  '#1c1700', '#d4a017'   # freshest — tightest breakout
    elif 7 <= pct50 <= 15:
        return 2, 'green', '#0d1a0d', '#3fb950'   # confirmed momentum
    elif 16 <= pct50 <= 30:
        return 1, 'amber', '#1a1000', '#f0883e'   # extended but in range
    else:
        return 0, 'none',  '',        ''           # <1% or >30% — no highlight

def _setup_score(r, grades):
    grade  = grades.get(r['ticker'])
    g_pts  = {'A+': 3, 'A': 2, 'B': 1}.get(grade, 0)
    ma_pts = 2 if r['all3'] else 1
    range_pts, _, _, _ = _range_band(r['pct50'])
    return g_pts + ma_pts + range_pts, grade

def _weekly_cmf(hist_w, period=10):
    try:
        hl = (hist_w['High'] - hist_w['Low']).replace(0, float('nan'))
        mfm = ((hist_w['Close'] - hist_w['Low']) - (hist_w['High'] - hist_w['Close'])) / hl
        mfv = mfm * hist_w['Volume']
        vol_sum = hist_w['Volume'].rolling(period).sum().iloc[-1]
        if not vol_sum or vol_sum == 0:
            return float('nan')
        return round(float(mfv.rolling(period).sum().iloc[-1] / vol_sum), 3)
    except Exception:
        return float('nan')

def get_daily_ma_pos(ticker):
    try:
        tkr    = yf.Ticker(ticker)
        hist   = tkr.history(period='3mo',  interval='1d')
        hist_w = tkr.history(period='26mo', interval='1wk')
        if hist is None or len(hist) < 52:
            return None
        close = hist['Close'].dropna()
        price = close.iloc[-1]
        ma10  = close.iloc[-10:].mean()
        ma20  = close.iloc[-20:].mean()
        ma50  = close.iloc[-50:].mean()
        count = sum([price > ma10, price > ma20, price > ma50])
        near  = sum([price >= ma10*0.95, price >= ma20*0.95, price >= ma50*0.95])
        # weekly slope: % change in 10wk MA over last 5 weekly bars
        wk_close = hist_w['Close'].dropna() if hist_w is not None and len(hist_w) >= 15 else None
        if wk_close is not None:
            ma10w_series = wk_close.rolling(10).mean().dropna()
            wk_slope = round((ma10w_series.iloc[-1] / ma10w_series.iloc[-6] - 1) * 100, 1) if len(ma10w_series) >= 6 else float('nan')
            wk_cmf = _weekly_cmf(hist_w)
        else:
            wk_slope = float('nan')
            wk_cmf   = float('nan')
        return {
            'ticker':   ticker,
            'price':    round(price, 2),
            'pct10':    round((price / ma10 - 1) * 100, 1),
            'pct20':    round((price / ma20 - 1) * 100, 1),
            'pct50':    round((price / ma50 - 1) * 100, 1),
            'above':    count,
            'all3':     count == 3,
            'near':     near,
            'wk_cmf':   wk_cmf,
            'wk_slope': wk_slope,
        }
    except Exception:
        return None

def get_hourly_stack(ticker):
    """Returns True if price above 10hMA, 20hMA, 50hMA on hourly bars (not necessarily stacked)."""
    try:
        hist = yf.Ticker(ticker).history(period='10d', interval='1h')
        if hist is None or len(hist) < 52:
            return False
        close = hist['Close'].dropna()
        price = close.iloc[-1]
        ma10  = close.iloc[-10:].mean()
        ma20  = close.iloc[-20:].mean()
        ma50  = close.iloc[-50:].mean()
        return price > ma10 and price > ma20 and price > ma50
    except Exception:
        return False

def _pct_cell(pct):
    color = '#3fb950' if pct > 0 else '#f85149'
    sign  = '+' if pct > 0 else ''
    return f'<td style="color:{color};font-weight:600">{sign}{pct}%</td>'

def _cmf_cell(cmf):
    import math
    if cmf is None or (isinstance(cmf, float) and math.isnan(cmf)):
        return '<td style="color:#484f58">—</td>'
    if cmf >= 0.15:
        color = '#3fb950'
    elif cmf <= -0.15:
        color = '#f85149'
    else:
        color = '#8b949e'
    sign = '+' if cmf > 0 else ''
    return f'<td style="color:{color};font-weight:600">{sign}{cmf:.3f}</td>'

def _slope_cell(slope):
    import math
    if slope is None or (isinstance(slope, float) and math.isnan(slope)):
        return '<td style="color:#484f58">—</td>'
    color = '#3fb950' if slope > 0 else '#f85149'
    sign  = '+' if slope > 0 else ''
    return f'<td style="color:{color};font-size:11px">{sign}{slope}%</td>'

def _algo_tier(r):
    import math
    cmf   = r.get('wk_cmf',   float('nan'))
    slope = r.get('wk_slope', float('nan'))
    cmf_ok   = not (isinstance(cmf,   float) and math.isnan(cmf))
    slope_ok = not (isinstance(slope, float) and math.isnan(slope))
    if not cmf_ok or not slope_ok or slope <= 0:
        return None
    above = r.get('above', 0)
    # strong: all three signals at max conviction
    if cmf >= 0.15 and above == 3:
        return 'strong'
    # positive: good confluence, price structure holding
    if cmf >= 0.10 and above >= 2:
        return 'positive'
    return None

def _top10_score(ext_r, pop_r, hourly_ok, grade):
    """Composite setup quality score. Higher = better current entry setup."""
    import math
    nan = float('nan')

    def _ok(v):  return v is not None and not (isinstance(v, float) and math.isnan(v))

    score = 0

    # Grade bonus
    score += {'A+': 10, 'A': 6, 'B': 2}.get(grade or '', 0)

    # ── Extension scan ────────────────────────────────────────────────────
    if ext_r is not None:
        runway    = ext_r.get('runway', 0)
        above_10w = ext_r.get('above_10w', False)
        cmf       = ext_r.get('cmf', nan)
        slope     = ext_r.get('slope', nan)
        rsi       = ext_r.get('rsi', nan)
        pct_87w   = ext_r.get('pct_vs_87w', nan)

        # Zone / runway
        if above_10w:
            if runway >= 70:    score += 25   # fresh — room to run
            elif runway >= 40:  score += 15   # midway
            elif runway >= 10:  score +=  5   # near ceiling
            else:               score -=  5   # blown ceiling
        else:
            # below 10w MA — CMF override rule (≥+0.20 = accumulation underneath)
            if _ok(cmf) and cmf >= 0.20:
                score +=  8
            else:
                score -= 15

        # Weekly CMF (extension)
        if _ok(cmf):
            if   cmf >= 0.25:  score += 20
            elif cmf >= 0.15:  score += 14
            elif cmf >= 0.10:  score +=  8
            elif cmf >= 0:     score +=  2
            else:              score -= 12

        # Weekly slope (10w MA trend)
        if _ok(slope):
            if   slope > 3:  score += 12
            elif slope > 1:  score +=  7
            elif slope > 0:  score +=  2
            else:            score -=  8

        # RSI (sweet spot = momentum without exhaustion)
        if _ok(rsi):
            if   45 <= rsi <= 65:  score +=  8
            elif 65 < rsi <= 75:   score +=  3
            elif rsi > 75:         score -=  5
            elif rsi < 35:         score -=  5

        # 87w structural position
        if _ok(pct_87w):
            if   pct_87w < 0:    score +=  5   # below LT mean — recovery setup
            elif pct_87w <= 10:  score +=  8   # at base — cleanest
            elif pct_87w <= 25:  score +=  4   # mild
            elif pct_87w <= 50:  score +=  0   # moderate
            elif pct_87w <= 100: score -=  5   # high
            else:                score -= 12   # extreme

    # ── Daily pop scan ────────────────────────────────────────────────────
    if pop_r is not None:
        wk_cmf   = pop_r.get('wk_cmf',   nan)
        wk_slope = pop_r.get('wk_slope', nan)
        above    = pop_r.get('above', 0)
        pct10    = pop_r.get('pct10', nan)
        near     = pop_r.get('near',  0)

        # Algo tier — highest conviction signal
        tier = _algo_tier(pop_r)
        if tier == 'strong':    score += 25
        elif tier == 'positive': score += 15

        # Daily MA zone
        if   above == 3:              score += 15
        elif above == 2:              score +=  8
        elif above == 1:              score +=  2
        elif near >= 2:               score +=  0   # tight
        else:                         score -= 10

        # vs 10d MA momentum check
        if _ok(pct10):
            if   pct10 > 1:   score +=  5
            elif pct10 >= -1: score +=  0
            else:             score -=  3

        # WkCMF (pop version)
        if _ok(wk_cmf):
            if   wk_cmf >= 0.25:  score += 10
            elif wk_cmf >= 0.15:  score +=  6
            elif wk_cmf >= 0.10:  score +=  3
            elif wk_cmf >= 0:     score +=  1
            else:                 score -=  8

        # WkSlope (pop version)
        if _ok(wk_slope):
            if   wk_slope > 3:  score +=  8
            elif wk_slope > 1:  score +=  4
            elif wk_slope > 0:  score +=  1
            else:               score -=  5

    if hourly_ok:
        score += 5

    return score


_ETF_SET = {'SPY','QQQ','IWM','GLD','TLT','SLV','DIA','XLF','XLK','XLE','ARKK','VTI','VOO'}

def _fetch_grade_live(ticker):
    """Fetch fundamental grade from yfinance. Returns 'A+', 'A', 'B', or None."""
    if ticker in _ETF_SET:
        return None
    try:
        import io, contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            info = yf.Ticker(ticker).info
        gm   = info.get('grossMargins')   or 0
        om   = info.get('operatingMargins') or 0
        nm   = info.get('profitMargins')  or 0
        roe  = info.get('returnOnEquity') or 0
        ev   = info.get('enterpriseValue') or 0
        debt = info.get('totalDebt') or 0
        fcf  = info.get('freeCashflow') or 0
        mktcap = info.get('marketCap') or 1
        rg   = info.get('revenueGrowth') or 0
        d_ev = (debt / ev) if ev > 0 else 1.0
        fcf_y = fcf / mktcap
        passes = om >= 0.10 and nm >= 0.05 and roe >= 0.10 and d_ev <= 0.20 and fcf_y > 0
        if not passes:
            return None
        aplus = (d_ev <= 0.03 and om >= 0.20 and nm >= 0.10 and roe >= 0.20
                 and fcf_y >= 0.02 and gm >= 0.60 and rg >= 0.05)
        a     = (d_ev <= 0.10 and om >= 0.15 and nm >= 0.08 and roe >= 0.15 and fcf_y >= 0.01)
        return 'A+' if aplus else ('A' if a else 'B')
    except Exception:
        return None


def _ext_zone_label(ext_r):
    """Short zone label from extension data."""
    if ext_r is None:
        return '—'
    if not ext_r.get('above_10w', False):
        return '⬇ below'
    runway = ext_r.get('runway', 0)
    if runway >= 70:   return '▓ fresh'
    if runway >= 40:   return '▒ midway'
    if runway >= 10:   return '⬡ near ceil'
    return '✕ blown'


_PINNED_INDICES = ['SPY', 'QQQ', 'IWM']

def _print_index_pulse(index_tickers):
    """Fetch and print a pinned INDEX PULSE section for the given index tickers."""
    import math
    with ThreadPoolExecutor(max_workers=3) as ex:
        idx_pop = list(ex.map(get_daily_ma_pos, index_tickers))

    # Pad visible text FIRST, then wrap in color — keeps column alignment intact
    def _pct_col(v, w=7):
        if v is None or (isinstance(v, float) and math.isnan(v)):
            return f'{_DIM}{"—":>{w}}{_RST}'
        sign = '+' if v > 0 else ''
        return _c(_G if v > 0 else _R, f'{sign}{v}%'.rjust(w))

    def _cmf_col(cmf, w=7):
        if cmf is None or (isinstance(cmf, float) and math.isnan(cmf)):
            return f'{_DIM}{"—":>{w}}{_RST}'
        raw = f'{cmf:+.3f}'
        col = _G if cmf >= 0.15 else _R if cmf <= -0.15 else '\033[37m'
        return _c(col, raw.rjust(w))

    def _slp_col(slope, w=7):
        if slope is None or (isinstance(slope, float) and math.isnan(slope)):
            return f'{_DIM}{"—":>{w}}{_RST}'
        return _c(_G if slope > 0 else _R, f'{slope:+.1f}%'.rjust(w))

    SEP = '─' * 66
    print(f'  {_DIM}{SEP}{_RST}')
    print(f'  {_BLD}{"INDEX PULSE":<10}{_RST}  '
          f'{_DIM}{"PRICE":>9}  {"vs10m":>7}  {"vs20m":>7}  {"vs50m":>7}  {"WkCMF":>7}  {"WkSlp":>7}{_RST}')
    print(f'  {_DIM}{SEP}{_RST}')
    for t, r in zip(index_tickers, idx_pop):
        if r is None:
            print(f'  {_BLD}{t:<10}{_RST}  {_DIM}no data{_RST}')
            continue
        pr_s = f'${r["price"]:>8,.2f}'
        print(f'  {_BLD}{t:<10}{_RST}  {pr_s}'
              f'  {_pct_col(r["pct10"])}'
              f'  {_pct_col(r["pct20"])}'
              f'  {_pct_col(r["pct50"])}'
              f'  {_cmf_col(r.get("wk_cmf",   float("nan")))}'
              f'  {_slp_col(r.get("wk_slope", float("nan")))}')
    print(f'  {_DIM}{SEP}{_RST}')
    print()

def run_top10(n=10, tickers_override=None):
    import math
    from extension_scan import get_extension_data

    mega_mode     = tickers_override is not None
    index_tickers = _PINNED_INDICES
    if mega_mode:
        tickers = [t for t in tickers_override if isinstance(t, str) and t not in _PINNED_INDICES]
    else:
        tickers_raw = list(dict.fromkeys(UNIVERSE))
        tickers_raw += [t for t in WATCHLIST if t not in tickers_raw]
        tickers = [t for t in tickers_raw if isinstance(t, str) and t not in _PINNED_INDICES]

    candidates = min(n * 2, len(tickers))   # oversample before grade re-score
    label = 'Mega-Cap' if mega_mode else 'Universe + Watchlist'
    eta   = '~30s' if mega_mode else '~90s'

    # Regime gate — fetch before scan so user sees market context immediately
    regime = get_regime()
    now    = datetime.utcnow().strftime('%b %d %Y  %H:%M UTC')
    print(f'\n  {_BLD}TOP {n} SETUPS — {label}{_RST}  {_DIM}{now}{_RST}')
    _print_regime_banner(regime)

    # Always show index pulse at the top of any scan
    print(f'\n  Fetching index pulse ...', flush=True)
    _print_index_pulse(index_tickers)

    print(f'  Scanning {len(tickers)} tickers  ({eta}) ...', flush=True)

    # Pass 1 — parallel fetch, score without grade bonus
    with ThreadPoolExecutor(max_workers=8) as ex:
        ext_results = list(ex.map(get_extension_data, tickers))
        pop_results = list(ex.map(get_daily_ma_pos,   tickers))
        h_stacks    = list(ex.map(get_hourly_stack,   tickers))

    pass1 = []
    for ticker, ext_r, pop_r, h_ok in zip(tickers, ext_results, pop_results, h_stacks):
        if pop_r is None:
            continue
        sc = _top10_score(ext_r, pop_r, h_ok, None)
        pass1.append((sc, ticker, ext_r, pop_r, h_ok))

    if len(pass1) < 20:
        print(f'\n  {_R}⚠ Only {len(pass1)} tickers returned data — Yahoo likely rate-limited.{_RST}')
        print(f'  {_DIM}Wait 2-3 minutes and retry.{_RST}\n')
        return

    pass1.sort(key=lambda x: -x[0])
    pool = pass1[:candidates]

    # Pass 2 — fetch grades sequentially; read disk cache first to survive rate limits
    import time
    pool_tickers = [t for _, t, *_ in pool]
    print(f'  Fetching grades for top {len(pool_tickers)} candidates ...', flush=True)
    disk_grades  = _load_grade_cache()
    mem_grades   = _load_grades()          # screener_data_cache.json (usually sparse)
    pre_loaded   = {**mem_grades, **disk_grades}
    needs_live   = [t for t in pool_tickers if pre_loaded.get(t) is None]
    live_grades  = {}
    for t in needs_live:
        live_grades[t] = _fetch_grade_live(t)
        time.sleep(0.5)
    if live_grades:
        _save_grade_cache(live_grades)     # persist for next run
    all_grades = {**pre_loaded, **live_grades}

    # Re-score with grades and take top n
    scored = []
    for sc0, ticker, ext_r, pop_r, h_ok in pool:
        grade = all_grades.get(ticker)
        sc = _top10_score(ext_r, pop_r, h_ok, grade)
        scored.append((sc, ticker, ext_r, pop_r, h_ok, grade))

    scored.sort(key=lambda x: -x[0])
    top = scored[:n]

    # Fetch earnings dates for final top-N only (fast — small set)
    print(f'  Fetching event calendar ...', flush=True)
    top_tickers  = [ticker for _, ticker, *_ in top]
    earnings_map = get_earnings_batch(top_tickers)
    print()

    # Header
    H = {'rk': 2, 'tk': 8, 'gr': 2, 'er': 5, 'pr': 8, 'wz': 11, 'wc': 7, 'ws': 7, 'dz': 7, 'al': 10, 'sc': 5}
    hdr = (f"  {'#':>{H['rk']}}  {'TICKER':<{H['tk']}}  {'GR':>{H['gr']}}"
           f"  {'ER':<{H['er']}}"
           f"  {'PRICE':>{H['pr']}}"
           f"  {'Wk Zone':<{H['wz']}}  {'WkCMF':>{H['wc']}}  {'WkSlp':>{H['ws']}}"
           f"  {'Daily':<{H['dz']}}  {'Algo':<{H['al']}}  {'Score':>{H['sc']}}")
    print(f'{_DIM}{hdr}{_RST}')
    print(f'{_DIM}  {"─" * (len(hdr) - 2)}{_RST}')

    for rank, (sc, ticker, ext_r, pop_r, h_ok, grade) in enumerate(top, 1):
        wk_cmf   = pop_r.get('wk_cmf',   float('nan'))
        wk_slope = pop_r.get('wk_slope', float('nan'))
        above    = pop_r.get('above', 0)
        near     = pop_r.get('near',  0)
        price    = pop_r.get('price', 0)

        wz = _ext_zone_label(ext_r)
        dz = ('● 3/3' if above == 3 else '◐ 2/3' if above == 2
              else '◎ tight' if near >= 2 else '✕ below')

        tier = _algo_tier(pop_r)
        algo_parts = []
        if h_ok:                     algo_parts.append(f'{_B}⚡H{_RST}')
        if tier == 'strong':         algo_parts.append(f'{_Y}◆ str{_RST}')
        elif tier == 'positive':     algo_parts.append(f'{_B}▲ pos{_RST}')
        algo_str = ' '.join(algo_parts)

        gr_s  = grade or '—'
        er_s  = earnings_cli(earnings_map.get(ticker))
        pr_s  = f'${price:,.2f}'
        cmf_s = _cli_cmf(wk_cmf)
        slp_s = _cli_slope(wk_slope)
        wz_c  = (_c(_G,          wz.ljust(H['wz'])) if 'fresh'  in wz else
                 _c('\033[32m', wz.ljust(H['wz'])) if 'midway' in wz else
                 _c(_DIM,       wz.ljust(H['wz'])) if 'blown'  in wz or 'below' in wz else
                 wz.ljust(H['wz']))
        dz_c  = (_c(_G,          dz.ljust(H['dz'])) if '3/3' in dz else
                 _c('\033[32m',  dz.ljust(H['dz'])) if '2/3' in dz else
                 _c(_DIM,        dz.ljust(H['dz'])))
        sc_c  = _c(_G, f'{sc:>5}') if sc >= 60 else _c('\033[37m', f'{sc:>5}')

        rank_s = f'{_BLD}{rank:>2}{_RST}'
        tick_s = f'{_BLD}{ticker:<{H["tk"]}}{_RST}'
        gr_col = f'{_DIM}{gr_s:>{H["gr"]}}{_RST}'

        print(
            f'  {rank_s}  {tick_s}  {gr_col}'
            f'  {_rpad(er_s,    H["er"])}'
            f'  {_lpad(pr_s,    H["pr"])}'
            f'  {wz_c}'
            f'  {_lpad(cmf_s,   H["wc"])}'
            f'  {_lpad(slp_s,   H["ws"])}'
            f'  {dz_c}'
            f'  {_rpad(algo_str, H["al"])}'
            f'  {_lpad(sc_c,    H["sc"])}'
        )

    print()
    print(f'  {_DIM}Score = zone(25) + ext CMF(20) + slope(12) + RSI(8) + 87w(8)'
          f' + algo(25) + daily(15) + WkCMF(10) + WkSlp(8) + ⚡H(5) + grade(10){_RST}')
    print()


def build_html(all3, two, tight, misses, no_data, now, label, grades, hourly, regime=None, earnings_map=None):
    def rows_for(group, badge_color, badge_label, is_tight=False):
        out = ''
        for r in group:
            score, grade = _setup_score(r, grades)
            tier = _algo_tier(r)

            # base background from range band
            _, _, bg, rng_border = _range_band(r['pct50'])
            bg_style = f'background:{bg};' if bg else ''

            # border: algo overrides range band; tight overrides both
            if is_tight:
                border_style = 'border-left:3px solid #1a6b7a;'
            elif tier == 'strong':
                border_style = 'border-left:3px solid #d4a017;'
                bg_style = bg_style or 'background:rgba(212,160,23,0.07);'
            elif tier == 'positive':
                border_style = 'border-left:3px solid #58a6ff;'
                bg_style = bg_style or 'background:rgba(88,166,255,0.05);'
            elif rng_border:
                border_style = f'border-left:3px solid {rng_border};'
            else:
                border_style = ''

            row_style  = bg_style + border_style
            grade_str  = f'<span style="color:#8b949e;font-size:10px">{grade}</span>' if grade else ''
            er_badge   = earnings_html_badge((earnings_map or {}).get(r['ticker']))
            hourly_flag = '<span title="Hourly stack" style="color:#58a6ff;font-size:10px;margin-left:4px">⚡H</span>' if hourly.get(r['ticker']) else ''
            algo_flag   = (
                '<span title="Strong algo: Wk CMF ≥0.15 + slope up + 3/3 MAs" style="color:#d4a017;font-size:11px;margin-left:4px">◆</span>'
                if tier == 'strong' else
                '<span title="Algo positive: Wk CMF ≥0.10 + slope up + 2+/3 MAs" style="color:#58a6ff;font-size:11px;margin-left:4px">▲</span>'
                if tier == 'positive' else ''
            )
            out += f"""<tr style="{row_style}">
              <td class="ticker">{r['ticker']} {grade_str}{er_badge}{hourly_flag}{algo_flag}</td>
              <td><span class="badge" style="background:{badge_color}">{badge_label}</span></td>
              <td>${r['price']}</td>
              {_pct_cell(r['pct10'])}
              {_pct_cell(r['pct20'])}
              {_pct_cell(r['pct50'])}
              {_cmf_cell(r.get('wk_cmf'))}
              {_slope_cell(r.get('wk_slope'))}
            </tr>"""
        return out

    rows  = rows_for(all3,  '#6e40c9', '● 3/3')
    rows += rows_for(two,   '#1a4731', '◐ 2/3')
    rows += rows_for(tight, '#1a4a4a', '◎ tight', is_tight=True)

    miss_rows  = rows_for(misses, '#3d1212', '✕ below')
    nd_tickers = '  ·  '.join(no_data) if no_data else '—'

    thead = """<thead>
    <tr>
      <th>Ticker</th><th>MAs</th><th>Price</th>
      <th>vs 10dMA</th><th>vs 20dMA</th><th>vs 50dMA</th><th>Wk CMF</th><th>Wk Slope</th>
    </tr>
  </thead>"""

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Pop Scan — {now}</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: 'SF Mono','Fira Code',monospace; background: #0d1117; color: #e6edf3; padding: 28px; font-size: 12px; }}
  h1 {{ font-size: 18px; font-weight: 700; color: #58a6ff; margin-bottom: 4px; }}
  .subtitle {{ color: #8b949e; font-size: 11px; margin-bottom: 20px; }}
  .summary {{ color: #8b949e; font-size: 12px; margin-bottom: 20px; }}
  .summary span {{ color: #e6edf3; font-weight: 700; }}
  table {{ width: 100%; border-collapse: collapse; margin-bottom: 32px; }}
  th {{ text-align: left; padding: 8px 10px; color: #8b949e; font-weight: 500;
        border-bottom: 2px solid #21262d; font-size: 10px; text-transform: uppercase; letter-spacing: .05em; }}
  td {{ padding: 8px 10px; border-bottom: 1px solid #161b22; }}
  tr:hover td {{ background: rgba(255,255,255,0.03); }}
  .ticker {{ font-weight: 700; color: #e6edf3; font-size: 13px; }}
  .badge {{ font-size: 11px; font-weight: 700; padding: 2px 8px; border-radius: 3px; color: #fff; }}
  .section-header {{ font-size: 11px; font-weight: 600; color: #8b949e; margin: 24px 0 8px;
                     border-top: 1px solid #21262d; padding-top: 12px; text-transform: uppercase; letter-spacing: .05em; }}
  .disclaimer {{ color: #484f58; font-size: 10px; margin-top: 24px; border-top: 1px solid #21262d; padding-top: 8px; }}
{REGIME_CSS}
{EVENT_CSS}
</style>
</head>
<body>
<h1>📈 Daily Pop Scanner <span style="font-size:13px;color:#8b949e;font-weight:400">— {label}</span></h1>
{regime_html(regime) if regime else ''}
<div class="subtitle">{now} &nbsp;·&nbsp; price vs 10d / 20d / 50d daily MAs &nbsp;·&nbsp; not necessarily stacked &nbsp;·&nbsp; gold 1-6% · green 7-15% · amber 16-30% vs 50dMA &nbsp;·&nbsp; ◎ tight = within -5% of 2+ MAs</div>

<div class="summary">
  <span>{len(all3)}</span> above all 3 &nbsp;·&nbsp;
  <span>{len(two)}</span> above 2 of 3 &nbsp;·&nbsp;
  <span>{len(tight)}</span> tight (within -5%) &nbsp;·&nbsp;
  <span>{len(misses)}</span> below &nbsp;·&nbsp;
  <span>{len(no_data)}</span> no data
</div>

<table>
  {thead}
  <tbody>{rows}</tbody>
</table>

<div class="section-header">Below All MAs — {len(misses)} tickers</div>
<table>
  {thead}
  <tbody>{miss_rows}</tbody>
</table>

<div class="section-header">No data — {nd_tickers}</div>
<div class="disclaimer">For informational purposes only. Market dynamics change constantly — these outputs are auto-generated from Yahoo Finance data and may not reflect current conditions. Not tailored financial advice. Not a recommendation to buy, sell, or hold any security. Always do your own research.</div>
</body>
</html>"""

# ── ANSI helpers ────────────────────────────────────────────────────────────
_G   = '\033[92m'
_R   = '\033[91m'
_Y   = '\033[93m'
_B   = '\033[94m'
_DIM = '\033[2m'
_RST = '\033[0m'
_BLD = '\033[1m'

import re as _re
_ANSI_RE = _re.compile(r'\033\[[0-9;]*m')

def _vlen(s):
    s = _ANSI_RE.sub('', s)
    # ⚡ ◆ ▲ are ambiguous-width chars that render as 2 terminal cols
    extra = sum(1 for c in s if c in ('⚡', '◆', '▲'))
    return len(s) + extra

def _lpad(s, w):
    """Right-align s in w visible characters (left-pad with spaces)."""
    return ' ' * max(0, w - _vlen(s)) + s

def _rpad(s, w):
    """Left-align s in w visible characters (right-pad with spaces)."""
    return s + ' ' * max(0, w - _vlen(s))

def _c(val, text):
    return f'{val}{text}{_RST}'

def _cli_pct(pct):
    import math
    if pct is None or (isinstance(pct, float) and math.isnan(pct)):
        return f'{_DIM}  —  {_RST}'
    s = f'{pct:+.1f}%'
    return _c(_G, s) if pct >= 0 else _c(_R, s)

def _cli_cmf(cmf):
    import math
    if cmf is None or (isinstance(cmf, float) and math.isnan(cmf)):
        return f'{_DIM}  —  {_RST}'
    s = f'{cmf:+.3f}'
    if cmf >= 0.15:   return _c(_G, s)
    if cmf <= -0.15:  return _c(_R, s)
    return f'\033[37m{s}{_RST}'

def _cli_slope(slope):
    import math
    if slope is None or (isinstance(slope, float) and math.isnan(slope)):
        return f'{_DIM}  —  {_RST}'
    s = f'{slope:+.1f}%'
    return _c(_G, s) if slope > 0 else _c(_R, s)

_REGIME_ANSI = {
    'BULL':    '\033[92m',
    'CAUTION': '\033[93m',
    'DEFENSE': '\033[33m',
    'STORM':   '\033[91m',
    'UNKNOWN': '\033[2m',
}

def _print_regime_banner(regime):
    rc    = _REGIME_ANSI.get(regime['label'], _DIM)
    rl    = regime['label']
    vix_s = f"VIX {regime['vix']:.1f}" if regime['vix'] is not None else 'VIX —'
    spy_s = (f"SPY {regime['spy_pct']:+.1f}% vs 10w"
             if regime['spy_pct'] is not None else 'SPY vs 10w —')
    print(f'  {_BLD}REGIME{_RST}  {rc}{_BLD}{rl:7}{_RST}  '
          f'{_DIM}{vix_s}  ·  {spy_s}{_RST}')
    sz = sizing_signal(regime)
    sc = _REGIME_ANSI.get({'FULL':'BULL','HALF':'CAUTION','QUARTER':'DEFENSE','SELL-IV':'STORM'}.get(sz['size']), _DIM)
    print(f'  {_BLD}SIZING{_RST}  {sc}{_BLD}{sz["size"]:7}{_RST}  '
          f'{sc}{sz["bar"]}{_RST}  {_DIM}{sz["note"]}{_RST}')


def print_cli_table(all3, two, tight, misses, no_data, label, grades, hourly, show_title=True):
    if show_title:
        now = datetime.utcnow().strftime('%b %d %Y  %H:%M UTC')
        print(f'\n  {_BLD}Pop Scan — {label}{_RST}  {_DIM}{now}{_RST}')
    print()

    # column widths (fixed, no ANSI in header)
    COL = {'tick': 14, 'zone': 10, 'price': 9, 'pct': 8, 'cmf': 9, 'slope': 9}
    hdr = (
        f"  {'TICKER':<{COL['tick']}} {'ZONE':<{COL['zone']}} {'PRICE':>{COL['price']}}"
        f"  {'vs10d':>{COL['pct']}}  {'vs20d':>{COL['pct']}}  {'vs50d':>{COL['pct']}}"
        f"  {'WkCMF':>{COL['cmf']}}  {'WkSlope':>{COL['slope']}}"
    )
    sep = '  ' + '─' * (len(hdr) - 2)
    print(f'{_DIM}{hdr}{_RST}')
    print(f'{_DIM}{sep}{_RST}')

    def _row(r, zone_label, section_color=''):
        tier = _algo_tier(r)
        grade = grades.get(r['ticker'])
        g_str = f' {_DIM}{grade}{_RST}' if grade else ''
        h_str = f' {_B}⚡H{_RST}' if hourly.get(r['ticker']) else ''
        a_str = (f' {_Y}◆{_RST}' if tier == 'strong' else f' {_B}▲{_RST}' if tier == 'positive' else '')
        tick  = r['ticker'] + g_str + h_str + a_str
        # Compute visible tick width; ⚡ renders as 2 terminal cols but len() counts 1
        raw_tick = (r['ticker']
                    + (f' {grade}' if grade else '')
                    + (' ⚡H' if hourly.get(r['ticker']) else '')
                    + (' ◆' if tier == 'strong' else ' ▲' if tier == 'positive' else ''))
        extra_w = raw_tick.count('⚡')          # each ⚡ steals 1 extra terminal col
        pad = ' ' * max(0, COL['tick'] - len(raw_tick) - extra_w)

        # Pad zone label to fixed width before adding color so terminal width is locked
        zone_col = f'{section_color}{zone_label.ljust(COL["zone"])}{_RST}'
        price_col = f'${r["price"]:>{COL["price"] - 1}.2f}'

        print(
            f'  {tick}{pad} {zone_col} {price_col}'
            f'  {_lpad(_cli_pct(r["pct10"]),        COL["pct"])}'
            f'  {_lpad(_cli_pct(r["pct20"]),        COL["pct"])}'
            f'  {_lpad(_cli_pct(r["pct50"]),        COL["pct"])}'
            f'  {_lpad(_cli_cmf(r.get("wk_cmf")),  COL["cmf"])}'
            f'  {_lpad(_cli_slope(r.get("wk_slope")), COL["slope"])}'
        )

    groups = [
        (all3,   '● 3/3',    _G),
        (two,    '◐ 2/3',    '\033[32m'),
        (tight,  '◎ tight',  '\033[36m'),
        (misses, '✕ below',  _R),
    ]
    for group, label_z, color in groups:
        if not group:
            continue
        for r in group:
            _row(r, label_z, color)

    if no_data:
        print(f'\n  {_DIM}No data: {", ".join(no_data)}{_RST}')
    print()

def print_combined_cli(tickers, ext_results, pop_results, h_stacks, label, grades):
    from extension_scan import _cli_header, _cli_row
    from event_risk import get_earnings_batch, earnings_risk
    now = datetime.utcnow().strftime('%b %d %Y  %H:%M UTC')
    print(f'\n  {_BLD}{label}{_RST}  {_DIM}{now}{_RST}')

    # Earnings event line — shows any ticker with earnings ≤30 days out
    earnings_map = get_earnings_batch(tickers)
    _ER_COLOR = {'HIGH': _R, 'WARN': '\033[33m', 'NEAR': _Y}
    er_parts = []
    for t in tickers:
        days, level = earnings_risk(earnings_map.get(t))
        if level:
            c = _ER_COLOR.get(level, _DIM)
            er_parts.append(f'{c}{t} {earnings_map[t].strftime("%b %d")} ({days}d){_RST}')
    if er_parts:
        print(f'  {_BLD}Earnings:{_RST}  {" · ".join(er_parts)}')

    # ── Weekly extension lens ──────────────────────────────────────────────
    print(f'\n  {_DIM}── Weekly Extension ──────────────────────────────────────────────────────────────────────────────────────────────{_RST}')
    ext_map = {r['ticker']: r for r in ext_results if r is not None}
    _cli_header()
    for t in tickers:
        r = ext_map.get(t)
        if r:
            _cli_row(r)
        else:
            print(f'  {t:<12}  {_DIM}no data{_RST}')

    # ── Daily MA lens ──────────────────────────────────────────────────────
    print(f'\n  {_DIM}── Daily MA Position ─────────────────────────────────────────────────────{_RST}')
    hourly = {t: s for t, s in zip(tickers, h_stacks)}
    valid  = [r for r in pop_results if r is not None]
    hits   = sorted([r for r in valid if r['above'] >= 2], key=lambda x: (-x['above'], -x['pct50']))
    below  = [r for r in valid if r['above'] < 2]
    tight  = sorted([r for r in below if r.get('near', 0) >= 2], key=lambda x: -x['pct50'])
    misses = sorted([r for r in below if r.get('near', 0) < 2],  key=lambda x: -x['above'])
    nd     = [t for t, r in zip(tickers, pop_results) if r is None]
    all3   = [h for h in hits if h['all3']]
    two    = [h for h in hits if h['above'] == 2]
    print_cli_table(all3, two, tight, misses, nd, label, grades, hourly, show_title=False)


def run(tickers, label, cli_only=False):
    print(f'\n  Scanning {len(tickers)} tickers ...', flush=True)
    grades = _load_grades()

    if cli_only:
        from extension_scan import get_extension_data
        with ThreadPoolExecutor(max_workers=16) as ex:
            ext_results = list(ex.map(get_extension_data, tickers))
            pop_results = list(ex.map(get_daily_ma_pos,   tickers))
            h_stacks    = list(ex.map(get_hourly_stack,   tickers))
        print_combined_cli(tickers, ext_results, pop_results, h_stacks, label, grades)
        return

    with ThreadPoolExecutor(max_workers=12) as ex:
        results  = list(ex.map(get_daily_ma_pos, tickers))
        h_stacks = list(ex.map(get_hourly_stack, tickers))

    hourly  = {t: s for t, s in zip(tickers, h_stacks)}
    valid   = [r for r in results if r is not None]
    hits    = sorted([r for r in valid if r['above'] >= 2], key=lambda x: (-x['above'], -x['pct50']))
    below   = [r for r in valid if r['above'] < 2]
    tight   = sorted([r for r in below if r.get('near', 0) >= 2], key=lambda x: -x['pct50'])
    misses  = sorted([r for r in below if r.get('near', 0) < 2],  key=lambda x: -x['above'])
    no_data = [t for t, r in zip(tickers, results) if r is None]
    all3    = [h for h in hits if h['all3']]
    two     = [h for h in hits if h['above'] == 2]

    now    = datetime.utcnow().strftime('%b %d %Y  %H:%M UTC')
    regime = get_regime()
    hit_tickers  = [r['ticker'] for r in all3 + two]
    earnings_map = get_earnings_batch(hit_tickers) if hit_tickers else {}
    html   = build_html(all3, two, tight, misses, no_data, now, label, grades, hourly,
                        regime=regime, earnings_map=earnings_map)

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'pop_scan.html')
    with open(out, 'w') as f:
        f.write(html)

    print(f'  ● {len(all3)} above all 3  ·  ◐ {len(two)} above 2  ·  ◎ {len(tight)} tight  ·  {len(misses)} below  ·  {len(no_data)} no data')
    print(f'  Opened → {out}\n')
    webbrowser.open(f'file://{out}')

if __name__ == '__main__':
    args = sys.argv[1:]

    if not args:
        tickers = list(dict.fromkeys(UNIVERSE))
        tickers += [t for t in WATCHLIST if t not in tickers]
        label = 'Universe + Watchlist'
        run(tickers, label)
    elif args == ['--universe']:
        run(list(dict.fromkeys(UNIVERSE)), 'Universe')
    elif args == ['--watchlist']:
        run(list(dict.fromkeys(WATCHLIST)), 'Watchlist')
    elif args[0].startswith('--top'):
        suffix = args[0][5:]
        n = int(suffix) if suffix.isdigit() else (int(args[1]) if len(args) > 1 and args[1].isdigit() else 10)
        run_top10(n)
    elif args[0].startswith('--mega'):
        suffix = args[0][6:]
        n = int(suffix) if suffix.isdigit() else (int(args[1]) if len(args) > 1 and args[1].isdigit() else 10)
        run_top10(n, tickers_override=MEGA_CAP)
    else:
        tickers = [t.upper() for t in args if not t.startswith('--')]
        run(tickers, ', '.join(tickers), cli_only=True)
