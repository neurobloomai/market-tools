"""
Ticker Score — on-demand CLI analysis tool.
Scores a single ticker across fundamentals, weekly technical, weekly momentum, and daily momentum.

Usage:
  python ticker_score.py AAPL
  python ticker_score.py IRWD
"""

import sys
import types
import warnings
import numpy as np

warnings.filterwarnings('ignore')

sys.modules.setdefault('_yf_cache', types.ModuleType('_yf_cache'))
import yfinance as yf
from screener import get_fundamentals, passes_quality_filter, failing_filters, quality_grade

# ── helpers ──────────────────────────────────────────────────────────────────

def _ema(series, span):
    return series.ewm(span=span, adjust=False).mean()

def _rsi(close, period=14):
    delta = close.diff()
    gain  = delta.clip(lower=0)
    loss  = (-delta).clip(lower=0)
    avg_g = gain.ewm(alpha=1/period, adjust=False).mean()
    avg_l = loss.ewm(alpha=1/period, adjust=False).mean()
    rs    = avg_g / avg_l.replace(0, np.nan)
    return 100 - (100 / (1 + rs))

def _macd(close, fast=12, slow=26, signal=9):
    macd_line = _ema(close, fast) - _ema(close, slow)
    sig_line  = _ema(macd_line, signal)
    histogram = macd_line - sig_line
    return macd_line, sig_line, histogram

def _slope_label(series, lookback=4):
    if len(series) < lookback + 1:
        return 'unknown', 0
    delta = series.iloc[-1] - series.iloc[-lookback]
    pct   = (delta / series.iloc[-lookback]) * 100
    if pct > 1:    return 'rising',  round(pct, 1)
    if pct < -1:   return 'falling', round(pct, 1)
    return 'flat', round(pct, 1)

def _tick(val): return '✓' if val else '✗'
def _arrow(val): return '↑' if val else '↓'

# ── scoring layers ────────────────────────────────────────────────────────────

def score_fundamentals(d):
    if d is None:
        return None, []
    checks = [
        ('OM ≥ 10%',      (d.get('operating_margin') or 0) >= 10),
        ('NM ≥ 5%',       (d.get('net_margin')        or 0) >= 5),
        ('ROE ≥ 10%',     (d.get('roe')               or 0) >= 10),
        ('D/EV ≤ 0.20',   (d.get('debt_to_ev')        or 1) <= 0.20),
        ('FCF > 0%',      (d.get('fcf_yield')         or 0) >  0),
        ('GrossM ≥ 40%',  (d.get('gross_margin')      or 0) >= 40),
        ('RevG > 0%',     (d.get('rev_growth')        or 0) >  0),
    ]
    score = sum(1 for _, v in checks if v)
    return score, checks

def score_weekly_tech(ticker):
    try:
        hist = yf.Ticker(ticker).history(period='2y', interval='1wk')
        if hist is None or len(hist) < 90:
            return None
        close = hist['Close'].dropna()
        price = close.iloc[-1]

        def ma(n):
            return close.iloc[-n:].mean() if len(close) >= n else None

        ma10 = ma(10); ma20 = ma(20); ma43 = ma(43); ma87 = ma(87)

        ma10_series = close.rolling(10).mean().dropna()
        slope_lbl, slope_pct = _slope_label(ma10_series, lookback=4)

        alignment = [
            ('10w', ma10, price > ma10 if ma10 else False),
            ('20w', ma20, price > ma20 if ma20 else False),
            ('43w', ma43, price > ma43 if ma43 else False),
            ('87w', ma87, price > ma87 if ma87 else False),
        ]
        score = sum(1 for _, _, v in alignment if v)

        return {
            'price':     round(price, 2),
            'alignment': alignment,
            'score':     score,
            'slope_lbl': slope_lbl,
            'slope_pct': slope_pct,
        }
    except Exception as e:
        return None

def score_weekly_momentum(ticker):
    try:
        hist = yf.Ticker(ticker).history(period='2y', interval='1wk')
        if hist is None or len(hist) < 35:
            return None
        close = hist['Close'].dropna()

        rsi_series  = _rsi(close)
        rsi_val     = round(rsi_series.iloc[-1], 1)

        macd_line, sig_line, histogram = _macd(close)
        macd_val  = macd_line.iloc[-1]
        sig_val   = sig_line.iloc[-1]
        hist_val  = histogram.iloc[-1]
        hist_prev = histogram.iloc[-2] if len(histogram) >= 2 else 0

        macd_above_signal  = macd_val > sig_val
        hist_expanding     = abs(hist_val) > abs(hist_prev) and hist_val > 0
        hist_contracting   = abs(hist_val) > abs(hist_prev) and hist_val < 0

        score = 0
        if rsi_val > 50: score += 1
        if rsi_val > 60: score += 1
        if macd_above_signal: score += 1
        if hist_expanding:    score += 1

        if rsi_val > 50:
            rsi_zone = 'bullish zone'
        elif rsi_val < 30:
            rsi_zone = 'oversold'
        elif rsi_val > 70:
            rsi_zone = 'overbought'
        else:
            rsi_zone = 'bearish zone'

        if macd_above_signal and hist_expanding:
            macd_read = 'above signal, histogram expanding ↑'
        elif macd_above_signal:
            macd_read = 'above signal, histogram fading'
        elif not macd_above_signal and hist_contracting:
            macd_read = 'below signal, histogram expanding ↓'
        else:
            macd_read = 'below signal, histogram fading'

        return {
            'rsi':       rsi_val,
            'rsi_zone':  rsi_zone,
            'macd_read': macd_read,
            'score':     score,
        }
    except Exception:
        return None

def score_daily_momentum(ticker):
    try:
        hist = yf.Ticker(ticker).history(period='3mo', interval='1d')
        if hist is None or len(hist) < 52:
            return None
        close = hist['Close'].dropna()
        price = close.iloc[-1]
        ma10  = close.iloc[-10:].mean()
        ma20  = close.iloc[-20:].mean()
        ma50  = close.iloc[-50:].mean()
        checks = [
            ('10d', ma10, price > ma10, round((price/ma10-1)*100, 1)),
            ('20d', ma20, price > ma20, round((price/ma20-1)*100, 1)),
            ('50d', ma50, price > ma50, round((price/ma50-1)*100, 1)),
        ]
        score = sum(1 for _, _, v, _ in checks if v)
        return {'checks': checks, 'score': score}
    except Exception:
        return None

# ── verdict ───────────────────────────────────────────────────────────────────

def verdict(f_score, w_score, m_score, d_score):
    lines = []

    if f_score is None:
        lines.append('Fundamentals : API error')
    elif f_score >= 6:
        lines.append('Fundamentals : strong — passes most quality gates')
    elif f_score >= 4:
        lines.append('Fundamentals : mixed — a few blockers, worth watching')
    else:
        lines.append('Fundamentals : not in coverage universe — too many blockers')

    if w_score is None:
        lines.append('Weekly tech  : API error')
    elif w_score >= 3:
        lines.append('Weekly tech  : well structured — price above most MAs')
    elif w_score >= 2:
        lines.append('Weekly tech  : mixed — partial MA support')
    else:
        lines.append('Weekly tech  : broken structure — below most MAs')

    if m_score is None:
        lines.append('Wk momentum  : API error')
    elif m_score >= 3:
        lines.append('Wk momentum  : strong — RSI bullish + MACD confirming')
    elif m_score >= 1:
        lines.append('Wk momentum  : neutral — partial momentum signals')
    else:
        lines.append('Wk momentum  : weak — RSI bearish, MACD not confirming')

    if d_score is None:
        lines.append('Daily        : API error')
    elif d_score == 3:
        lines.append('Daily        : above all 3 daily MAs — momentum active')
    elif d_score == 2:
        lines.append('Daily        : above 2 of 3 daily MAs')
    else:
        lines.append('Daily        : below daily MAs — no short-term momentum')

    return lines

# ── main ─────────────────────────────────────────────────────────────────────

def run(ticker):
    W = 52
    print(f'\n  {"═"*W}')
    print(f'  TICKER SCORE — {ticker}')
    print(f'  {"═"*W}')

    # fundamentals
    print(f'\n  FUNDAMENTALS', flush=True)
    print(f'  {"─"*W}')
    d = get_fundamentals(ticker)
    if d is None:
        print(f'  API error — yfinance returned no data for {ticker}')
        f_score = None
    else:
        f_score, checks = score_fundamentals(d)
        name = d.get('name', ticker)
        sector = d.get('sector', '—')
        price = d.get('price', '—')
        print(f'  {name}  ·  {sector}  ·  ${price}')
        print()
        for label, passed in checks:
            raw_map = {
                'OM ≥ 10%':     f"{(d.get('operating_margin') or 0):.1f}%",
                'NM ≥ 5%':      f"{(d.get('net_margin')       or 0):.1f}%",
                'ROE ≥ 10%':    f"{(d.get('roe')              or 0):.1f}%",
                'D/EV ≤ 0.20':  f"{(d.get('debt_to_ev')       or 0):.3f}",
                'FCF > 0%':     f"{(d.get('fcf_yield')        or 0):.1f}%",
                'GrossM ≥ 40%': f"{(d.get('gross_margin')     or 0):.1f}%",
                'RevG > 0%':    f"{(d.get('rev_growth')       or 0):.1f}%",
            }
            val = raw_map.get(label, '—')
            print(f'  {_tick(passed)}  {label:<16}  {val}')
        if passes_quality_filter(d):
            grade = quality_grade(d)
            print(f'\n  Grade: {grade}  ({f_score}/7 gates)')
        else:
            blockers = [f[0] for f in failing_filters(d) if f[0] != 'Passes all filters']
            print(f'\n  Grade: —  ({f_score}/7)  blockers: {", ".join(blockers[:3])}')

    # weekly technical
    print(f'\n  WEEKLY MA STRUCTURE')
    print(f'  {"─"*W}')
    wt = score_weekly_tech(ticker)
    if wt is None:
        print(f'  API error — could not fetch weekly history')
        w_score = None
    else:
        w_score = wt['score']
        for label, ma_val, above, in wt['alignment']:
            if ma_val:
                pct = round((wt['price']/ma_val - 1)*100, 1)
                sign = '+' if pct >= 0 else ''
                print(f'  {_tick(above)}  Price vs {label} MA  ${ma_val:.2f}   {sign}{pct}%')
            else:
                print(f'  —  {label} MA   insufficient history')
        slope_sign = '+' if wt['slope_pct'] >= 0 else ''
        print(f'\n  10w MA slope : {wt["slope_lbl"]}  ({slope_sign}{wt["slope_pct"]}% over 4 weeks)')
        print(f'  Alignment    : price above {w_score}/4 MAs')

    # weekly momentum
    print(f'\n  WEEKLY MOMENTUM  (RSI-14 + MACD 12/26/9)')
    print(f'  {"─"*W}')
    wm = score_weekly_momentum(ticker)
    if wm is None:
        print(f'  API error — could not compute momentum')
        m_score = None
    else:
        m_score = wm['score']
        print(f'  RSI-14  : {wm["rsi"]}  — {wm["rsi_zone"]}')
        print(f'  MACD    : {wm["macd_read"]}')
        print(f'  Score   : {m_score}/4')

    # daily momentum
    print(f'\n  DAILY MOMENTUM  (10d / 20d / 50d MA)')
    print(f'  {"─"*W}')
    dm = score_daily_momentum(ticker)
    if dm is None:
        print(f'  API error — could not fetch daily history')
        d_score = None
    else:
        d_score = dm['score']
        for label, ma_val, above, pct in dm['checks']:
            sign = '+' if pct >= 0 else ''
            print(f'  {_tick(above)}  vs {label} MA  ${ma_val:.2f}   {sign}{pct}%')
        print(f'\n  Above : {d_score}/3 daily MAs')

    # verdict
    print(f'\n  VERDICT')
    print(f'  {"─"*W}')
    for line in verdict(f_score, w_score, m_score, d_score):
        print(f'  {line}')
    print(f'\n  {"═"*W}\n')

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('\n  Usage: python ticker_score.py TICKER\n')
        sys.exit(1)
    run(sys.argv[1].upper())
