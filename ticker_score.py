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

def run_schwab_score(tickers):
    """0-100 composite fundamentals score using Schwab API data. Single or multi-ticker."""
    try:
        from schwab_client import get_fundamentals as schwab_fundamentals
        from internal_fundamentals_score import (score_fundamentals_schwab, score_band,
                                                 cap_tier, cap_str, risk_adjusted_score)
    except ImportError as e:
        print(f'\n  Cannot load Schwab scorer: {e}\n')
        return

    if len(tickers) == 1:
        # ── single ticker: vertical view ─────────────────────────────────────
        ticker = tickers[0]
        W = 52
        print(f'\n  {"═"*W}')
        print(f'  FUNDAMENTALS SCORE (Schwab) — {ticker}')
        print(f'  {"═"*W}')
        d = schwab_fundamentals(ticker)
        if d is None:
            print(f'\n  No Schwab fundamental data for {ticker}\n')
            return
        score, breakdown = score_fundamentals_schwab(d)
        mcap = d.get('marketCap')
        tier_label, mult = cap_tier(mcap)
        adj   = risk_adjusted_score(score, mcap)
        cstr  = cap_str(mcap)
        print(f'\n  {ticker}  ·  Cap {cstr}  ·  Beta {d.get("beta") or "—"}\n')
        BAR = 10
        for key, label, mx in [('profitability','Profitability',35),('growth','Growth',20),
                                ('valuation','Valuation',20),('balance_sheet','Balance Sheet',25)]:
            s = breakdown[key]['score']
            bar = '█' * round(s/mx*BAR) + '░' * (BAR - round(s/mx*BAR))
            print(f'  {label:<16}  {s:>2}/{mx:<2}  {round(s/mx*100):>3}%  {bar}')
        print(f'\n  {"─"*W}')
        print(f'  COMPOSITE SCORE   {score:>3} / 100  —  {score_band(score)}')
        print(f'  Cap Tier          {tier_label}  ({cstr})  ×{mult:.2f}')
        print(f'  RISK-ADJ SCORE    {adj:>3} / 100  —  {score_band(adj)}')
        print(f'  {"═"*W}\n')
        return

    # ── multi-ticker: side-by-side table ─────────────────────────────────────
    from concurrent.futures import ThreadPoolExecutor
    print(f'\n  Fetching Schwab fundamentals for {len(tickers)} tickers ...', flush=True)
    with ThreadPoolExecutor(max_workers=6) as ex:
        raw_data = list(ex.map(schwab_fundamentals, tickers))

    all_data = {}
    for t, d in zip(tickers, raw_data):
        score, breakdown = score_fundamentals_schwab(d) if d else (None, {})
        mcap = (d or {}).get('marketCap')
        adj  = risk_adjusted_score(score, mcap)
        all_data[t] = (score, breakdown, d or {}, mcap, adj)

    # sort by risk-adjusted score descending
    ordered = sorted(tickers, key=lambda t: all_data[t][4] or 0, reverse=True)

    BAR  = 10
    COL  = 22          # chars per data column including 2-space prefix
    LBL  = 24          # label column width (2 prefix + 22 content)
    W    = LBL + COL * len(ordered)
    def pct(v):  return f'{v*100:+.1f}%' if isinstance(v, (int, float)) else '—'
    def raw(v):  return f'{v:.1f}'       if isinstance(v, (int, float)) else '—'
    def col(s):  return f'  {s:<{COL-2}}'   # pad any string to one full column

    print(f'\n  FUNDAMENTALS SCORE — Side by Side (Schwab)')
    print(f'  {"═"*W}')
    print(f'  {"":22}' + ''.join(col(t) for t in ordered))
    print(f'  {"─"*W}')

    # composite row
    print(f'  {"COMPOSITE":22}' + ''.join(
        col(f'{all_data[t][0]}/100  {score_band(all_data[t][0])}')
        if all_data[t][0] is not None else col('—')
        for t in ordered))

    # cap tier + risk-adjusted score rows
    print(f'  {"Cap Tier":22}' + ''.join(
        col(f'{cap_tier(all_data[t][3])[0]}  ×{cap_tier(all_data[t][3])[1]:.2f}')
        for t in ordered))
    print(f'  {"Risk-Adj Score":22}' + ''.join(
        col(f'{all_data[t][4]}/100  {score_band(all_data[t][4])}')
        if all_data[t][4] is not None else col('—')
        for t in ordered))
    print(f'  {"─"*W}')

    for key, label, mx in [('profitability','Profitability',35),('growth','Growth',20),
                            ('valuation','Valuation',20),('balance_sheet','Balance Sheet',25)]:
        row = f'  {label:<22}'
        for t in ordered:
            bd = all_data[t][1]
            if not bd:
                row += col('—')
                continue
            s      = bd[key]['score']
            filled = round(s / mx * BAR)
            bar    = '█' * filled + '░' * (BAR - filled)
            row   += col(f'{s:>2}/{mx:<2} {bar}')
        print(row)

    print(f'  {"─"*W}')

    for label, fn in [
        ('Gross Margin',   lambda d: pct(d.get('grossMargins'))),
        ('Op Margin',      lambda d: pct(d.get('operatingMargins'))),
        ('Net Margin',     lambda d: pct(d.get('profitMargins'))),
        ('ROE',            lambda d: pct(d.get('returnOnEquity'))),
        ('Rev Growth TTM', lambda d: pct(d.get('revenueGrowthTTM'))),
        ('EPS Growth TTM', lambda d: pct(d.get('epsGrowthTTM'))),
        ('PEG',            lambda d: raw(d.get('pegRatio'))),
        ('P/E',            lambda d: raw(d.get('trailingPE'))),
        ('P/CF',           lambda d: raw(d.get('pcfRatio'))),
        ('D/E (%)',        lambda d: raw(d.get('totalDebtToEquity'))),
        ('Current Ratio',  lambda d: raw(d.get('currentRatio'))),
    ]:
        row = f'  {label:<22}'
        for t in ordered:
            val = fn(all_data[t][2]) if all_data[t][2] else '—'
            row += col(val)
        print(row)

    print(f'  {"═"*W}\n')


def run_full_score(tickers):
    """
    Combined fundamentals + technical score with sizing weight.
    Requires both --schwab and --technical flags.
    """
    try:
        from schwab_client import get_fundamentals as schwab_fundamentals
        from internal_fundamentals_score import (score_fundamentals_schwab, score_band,
                                                  cap_tier, cap_str, risk_adjusted_score)
        from internal_technical_score import (score_technical, tech_score_band,
                                               sizing_weight, regime_multiplier,
                                               event_multiplier)
        from pop_scan import get_daily_ma_pos
        from extension_scan import get_extension_data
        from regime import get_regime
        from event_risk import get_earnings_batch, earnings_risk
    except ImportError as e:
        print(f'\n  Cannot load scorer: {e}\n')
        return

    from concurrent.futures import ThreadPoolExecutor

    print(f'\n  Fetching data for {len(tickers)} ticker(s) ...', flush=True)
    with ThreadPoolExecutor(max_workers=8) as ex:
        fund_raw  = list(ex.map(schwab_fundamentals, tickers))
        pop_raw   = list(ex.map(get_daily_ma_pos,    tickers))
        ext_raw   = list(ex.map(get_extension_data,  tickers))

    regime   = get_regime()
    vix      = regime.get('vix')
    reg_lbl  = regime.get('label', 'UNKNOWN')
    reg_mult = regime_multiplier(vix)

    er_dates = get_earnings_batch(tickers)

    all_data = {}
    for t, fd, pop, ext in zip(tickers, fund_raw, pop_raw, ext_raw):
        f_score, f_bd = score_fundamentals_schwab(fd) if fd else (None, {})
        mcap    = (fd or {}).get('marketCap')
        f_adj   = risk_adjusted_score(f_score, mcap)
        t_score, t_bd = score_technical(pop, ext)
        er_days, er_level = earnings_risk(er_dates.get(t))
        sw = sizing_weight(f_adj, t_score, vix, er_level)
        all_data[t] = (f_score, f_bd, fd or {}, mcap, f_adj,
                       t_score, t_bd, pop or {}, ext or {}, sw,
                       er_days, er_level, er_dates.get(t))

    if len(tickers) == 1:
        _print_full_single(tickers[0], all_data[tickers[0]], vix, reg_lbl, reg_mult)
    else:
        ordered = sorted(tickers, key=lambda t: all_data[t][9] or 0, reverse=True)
        _print_full_table(ordered, all_data, vix, reg_lbl, reg_mult)


def _print_full_single(ticker, data, vix, reg_lbl, reg_mult):
    from internal_fundamentals_score import score_band, cap_tier, cap_str
    from internal_technical_score import tech_score_band

    f_score, f_bd, fd, mcap, f_adj, t_score, t_bd, pop, ext, sw, er_days, er_level, er_date = data
    from internal_technical_score import event_multiplier
    tier_lbl, mult = cap_tier(mcap)
    cstr    = cap_str(mcap)
    ev_mult = event_multiplier(er_level)
    BAR     = 10
    W       = 64

    def bar(s, mx):
        f = round(s / mx * BAR)
        return '█' * f + '░' * (BAR - f)

    vix_hdr = f'{vix:.1f}' if vix else '—'
    print(f'\n  {"═"*W}')
    print(f'  FULL SCORE — {ticker}  ·  {cstr}  ·  Regime {reg_lbl}  VIX {vix_hdr}')
    print(f'  {"═"*W}')

    # side-by-side header
    print(f'\n  {"FUNDAMENTALS (Schwab)":<32}  {"TECHNICAL (Live)":<30}')
    print(f'  {"─"*30}  {"─"*30}')

    f_pillars = [('Profitability', 35), ('Growth', 20), ('Valuation', 20), ('Balance Sheet', 25)]
    t_pillars = [('MA Structure', 25), ('CMF', 25), ('Slope', 20), ('RSI Zone', 15), ('Runway', 15)]
    fkeys     = ['profitability', 'growth', 'valuation', 'balance_sheet']
    tkeys     = ['ma_structure', 'cmf', 'slope', 'rsi', 'runway']

    for i in range(max(len(f_pillars), len(t_pillars))):
        if i < len(f_pillars) and f_bd:
            flbl, fmx = f_pillars[i]
            fs = f_bd[fkeys[i]]['score']
            fcol = f'  {flbl:<16} {fs:>2}/{fmx:<2} {bar(fs, fmx)}'
        else:
            fcol = f'  {"":16} {"":>2} {"":3} {"":10}'
        if i < len(t_pillars) and t_bd:
            tlbl, tmx = t_pillars[i]
            ts = t_bd[tkeys[i]]['score']
            tcol = f'  {tlbl:<14} {ts:>2}/{tmx:<2} {bar(ts, tmx)}'
        else:
            tcol = ''
        print(fcol + tcol)

    print(f'\n  {"─"*W}')

    vix_str = f'{vix:.1f}' if vix else '—'
    print(f'  {"COMPOSITE":<20} {(str(f_score)+"/100"):>7}  {score_band(f_score):<12}'
          f'  {"TECHNICAL":<16} {(str(t_score)+"/100"):>7}  {tech_score_band(t_score)}')
    print(f'  {"Cap Tier":<20} {tier_lbl+" ×"+f"{mult:.2f}":>7}  {cstr:<12}'
          f'  {"Regime":<16} {reg_lbl:>7}  VIX {vix_str}')
    print(f'  {"Risk-Adj Score":<20} {(str(f_adj)+"/100"):>7}  {score_band(f_adj):<12}'
          f'  {"Regime mult":<16} {f"×{reg_mult:.2f}":>7}')

    # event risk line — only shown when relevant
    if er_level:
        er_date_str = er_date.strftime('%b %d') if er_date else '—'
        er_flag = {'HIGH': '⚠ HIGH', 'WARN': '~ WARN', 'NEAR': 'NEAR', 'WATCH': 'WATCH'}.get(er_level, er_level)
        print(f'  {"Event Risk":<20} {"ER "+er_date_str:>7}  {er_days}d  {er_flag:<8}'
              f'  {"ER mult":<16} {f"×{ev_mult:.2f}":>7}')

    print(f'\n  {"═"*W}')
    sw_bar = '█' * round((sw or 0) * 10) + '░' * (10 - round((sw or 0) * 10)) if sw is not None else '—'
    if sw is not None:
        formula = f'({f_adj}% fund × {t_score}% tech × ×{reg_mult:.2f} regime'
        formula += f' × ×{ev_mult:.2f} ER)' if er_level else ')'
        print(f'  SIZING WEIGHT   {sw:.3f}  {sw_bar}   {formula}')
    else:
        print(f'  SIZING WEIGHT   — (insufficient data)')
    print(f'  {"═"*W}\n')


def _print_full_table(ordered, all_data, vix, reg_lbl, reg_mult):
    from internal_fundamentals_score import score_band, cap_tier, cap_str
    from internal_technical_score import tech_score_band

    BAR = 8
    COL = 22
    LBL = 24
    W   = LBL + COL * len(ordered)

    def col(s): return f'  {s:<{COL-2}}'
    def bar(s, mx):
        f = round(s / mx * BAR)
        return '█' * f + '░' * (BAR - f)

    vix_str = f'{vix:.1f}' if vix else '—'
    print(f'\n  FULL SCORE — Fundamentals + Technical  ·  Regime {reg_lbl}  VIX {vix_str}')
    print(f'  {"═"*W}')
    print(f'  {"":22}' + ''.join(col(t) for t in ordered))
    print(f'  {"─"*W}')

    # ── fundamentals block ────────────────────────────────────────────────────
    def fcol(t, key):
        bd = all_data[t][1]
        if not bd: return col('—')
        s, mx = bd[key]['score'], bd[key]['max']
        return col(f'{s:>2}/{mx:<2} {bar(s, mx)}')

    def tcol(t, key):
        bd = all_data[t][6]
        if not bd: return col('—')
        s, mx = bd[key]['score'], bd[key]['max']
        return col(f'{s:>2}/{mx:<2} {bar(s, mx)}')

    print(f'  {"— FUNDAMENTALS —":22}')
    print(f'  {"COMPOSITE":22}' + ''.join(
        col(f'{all_data[t][0]}/100  {score_band(all_data[t][0])}') if all_data[t][0] is not None else col('—')
        for t in ordered))
    print(f'  {"Cap Tier":22}' + ''.join(
        col(f'{cap_tier(all_data[t][3])[0]}  ×{cap_tier(all_data[t][3])[1]:.2f}')
        for t in ordered))
    print(f'  {"Risk-Adj Score":22}' + ''.join(
        col(f'{all_data[t][4]}/100  {score_band(all_data[t][4])}') if all_data[t][4] is not None else col('—')
        for t in ordered))
    print(f'  {"─"*W}')

    for key, label in [('profitability','Profitability'),('growth','Growth'),
                       ('valuation','Valuation'),('balance_sheet','Balance Sheet')]:
        print(f'  {label:<22}' + ''.join(fcol(t, key) for t in ordered))

    print(f'  {"─"*W}')
    print(f'  {"— TECHNICAL —":22}')
    print(f'  {"TECHNICAL":22}' + ''.join(
        col(f'{all_data[t][5]}/100  {tech_score_band(all_data[t][5])}') if all_data[t][5] is not None else col('—')
        for t in ordered))
    print(f'  {"─"*W}')

    for key, label in [('ma_structure','MA Structure'),('cmf','CMF'),
                       ('slope','Slope'),('rsi','RSI Zone'),('runway','Runway')]:
        print(f'  {label:<22}' + ''.join(tcol(t, key) for t in ordered))

    print(f'  {"─"*W}')

    # raw technical values
    for label, fn in [
        ('MA above (0-3)', lambda t: str(all_data[t][7].get('above', '—'))),
        ('CMF-20',         lambda t: f'{all_data[t][8].get("cmf"):+.3f}' if all_data[t][8].get("cmf") is not None else '—'),
        ('Slope 10w %',    lambda t: f'{all_data[t][8].get("slope"):+.1f}%' if all_data[t][8].get("slope") is not None else '—'),
        ('RSI-14 (wkly)',  lambda t: f'{all_data[t][8].get("rsi"):.0f}' if all_data[t][8].get("rsi") is not None else '—'),
        ('Runway %',       lambda t: f'{all_data[t][8].get("runway"):.0f}%' if all_data[t][8].get("runway") is not None else '—'),
    ]:
        print(f'  {label:<22}' + ''.join(col(fn(t)) for t in ordered))

    print(f'  {"─"*W}')

    # event risk block
    from internal_technical_score import event_multiplier
    print(f'  {"— EVENT RISK —":22}')

    def er_str(t):
        er_days, er_level, er_date = all_data[t][10], all_data[t][11], all_data[t][12]
        if not er_level:
            return 'clear' if er_days is not None else '—'
        date_s = er_date.strftime('%b %d') if er_date else '—'
        flag   = {'HIGH': '⚠ HIGH', 'WARN': '~ WARN', 'NEAR': 'NEAR', 'WATCH': 'WATCH?'}.get(er_level, er_level)
        return f'{flag} {date_s} ({er_days}d)'

    print(f'  {"Earnings":22}' + ''.join(col(er_str(t)) for t in ordered))
    print(f'  {"ER mult":22}' + ''.join(
        col(f'×{event_multiplier(all_data[t][11]):.2f}') for t in ordered))

    print(f'  {"─"*W}')
    print(f'  {"═"*W}')
    sw_bar = lambda sw: ('█' * round(sw * 8) + '░' * (8 - round(sw * 8))) if sw is not None else '—'
    print(f'  {"SIZING WEIGHT":22}' + ''.join(
        col(f'{all_data[t][9]:.3f}  {sw_bar(all_data[t][9])}') if all_data[t][9] is not None else col('—')
        for t in ordered))
    print(f'  {"(×regime ×ER)":22}' + ''.join(
        col(f'(×{reg_mult:.2f} ×{event_multiplier(all_data[t][11]):.2f})')
        for t in ordered))
    print(f'  {"═"*W}\n')


if __name__ == '__main__':
    args    = sys.argv[1:]
    flags   = [a for a in args if a.startswith('--')]
    tickers = [a.upper() for a in args if not a.startswith('--')]
    if not tickers:
        print('\n  Usage: python ticker_score.py TICKER [TICKER ...] [--schwab] [--technical]\n')
        sys.exit(1)
    if '--schwab' in flags and '--technical' in flags:
        run_full_score(tickers)
    elif '--schwab' in flags:
        run_schwab_score(tickers)
    elif len(tickers) == 1:
        run(tickers[0])
    else:
        for t in tickers:
            run(t)
