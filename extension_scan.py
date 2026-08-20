"""
extension_scan.py — Weekly MA extension + projection scanner.

For each ticker above its 10w MA, computes how extended it is vs its own
historical ceiling and how much runway remains before reaching that ceiling.

Key metrics:
  ext_now   — current % above 10w MA
  ext_90p   — 90th percentile historical extension (typical ceiling)
  runway    — % of ceiling still unused  (100% = just broke out, 0% = at ceiling)
  ceiling   — implied price at 90th pct ceiling (given current 10w MA)
  RSI       — weekly RSI-14

Usage:
  python3 extension_scan.py               # full universe + watchlist
  python3 extension_scan.py NVDA AAPL     # specific tickers (CLI only)
  python3 extension_scan.py --watchlist   # watchlist only
  python3 extension_scan.py --dividend    # dividend universe
"""

import os
import re
import sys
import types
import warnings
import webbrowser
import yfinance as yf
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from regime import get_regime, regime_html, REGIME_CSS
from event_risk import get_earnings_batch, earnings_html_badge, EVENT_CSS

warnings.filterwarnings('ignore')
sys.modules.setdefault('_yf_cache', types.ModuleType('_yf_cache'))
from screener import UNIVERSE, WATCHLIST
from dividend_plays_for_longterm import UNIVERSE as DIVIDEND_UNIVERSE


# ── Data fetch ────────────────────────────────────────────────────────────────

def _build_current_week_bar(ticker, weekly_hist):
    """
    Fetch this week's daily bars and aggregate into a partial OHLCV bar.
    Appends to weekly_hist if the current week isn't already the last bar,
    otherwise replaces the last bar so mid-week CMF/RSI/slope are live.
    Returns augmented hist DataFrame.
    """
    import pandas as pd
    try:
        daily = yf.Ticker(ticker).history(period='10d', interval='1d')
        if daily is None or daily.empty:
            return weekly_hist

        # Identify Mon of the current week (market week)
        last_daily = daily.index[-1]
        week_start = last_daily - pd.Timedelta(days=last_daily.weekday())  # Monday

        this_week = daily[daily.index >= week_start]
        if this_week.empty:
            return weekly_hist

        # Aggregate: O=Mon open, H=week high, L=week low, C=latest close, V=sum
        partial = {
            'Open':   float(this_week['Open'].iloc[0]),
            'High':   float(this_week['High'].max()),
            'Low':    float(this_week['Low'].min()),
            'Close':  float(this_week['Close'].iloc[-1]),
            'Volume': int(this_week['Volume'].sum()),
        }

        # Use Monday's timestamp as the bar index (same tz as weekly_hist)
        bar_ts = pd.Timestamp(week_start.date(), tz=weekly_hist.index.tz)

        # If last weekly bar is already this week, replace it; else append
        last_wk = weekly_hist.index[-1]
        aug = weekly_hist.copy()
        if abs((last_wk - bar_ts).days) <= 4:
            for col, val in partial.items():
                if col in aug.columns:
                    aug.at[last_wk, col] = val
        else:
            new_row = pd.DataFrame([partial], index=[bar_ts])
            new_row.index.name = weekly_hist.index.name
            for col in aug.columns:
                if col not in new_row.columns:
                    new_row[col] = float('nan')
            aug = pd.concat([aug, new_row[aug.columns]])

        return aug
    except Exception:
        return weekly_hist


def get_extension_data(ticker):
    try:
        hist  = yf.Ticker(ticker).history(period='3y', interval='1wk')
        if hist is None or len(hist) < 55:
            return None

        # Augment with current week's partial bar so CMF/RSI/slope are live
        hist = _build_current_week_bar(ticker, hist)

        close = hist['Close'].dropna()
        if len(close) < 55:
            return None
        price = float(close.iloc[-1])

        ma10w = float(close.rolling(10).mean().iloc[-1])
        ma20w = float(close.rolling(20).mean().iloc[-1])
        ma43w = float(close.rolling(43).mean().iloc[-1])
        ma87w = float(close.rolling(87).mean().iloc[-1]) if len(close) >= 87 else None

        # Historical extension distribution vs 10w MA
        ext_series  = ((close / close.rolling(10).mean()) - 1) * 100
        ext_valid   = ext_series.dropna()
        ext_90p     = float(ext_valid.quantile(0.90))   # typical upside ceiling
        ext_max     = float(ext_valid.max())            # absolute historical max
        ext_now     = (price / ma10w - 1) * 100

        # Runway: how much of the 90th pct ceiling is still unused
        if ext_90p > 0 and ext_now > 0:
            runway = max(0.0, (ext_90p - ext_now) / ext_90p * 100)
        elif ext_now <= 0:
            runway = 100.0   # below MA — full runway theoretically
        else:
            runway = 0.0

        ceiling_90  = ma10w * (1 + ext_90p  / 100)
        ceiling_max = ma10w * (1 + ext_max  / 100)

        # % above 87w MA — structural long-term extension
        pct_vs_87w = round((price / ma87w - 1) * 100, 1) if ma87w else None

        # % from 52w high
        hi52        = float(close.iloc[-52:].max()) if len(close) >= 52 else float(close.max())
        pct_from_hi = (price / hi52 - 1) * 100

        # 10w MA slope (vs 4 weeks ago)
        ma10w_4wk   = float(close.rolling(10).mean().iloc[-5])
        slope       = (ma10w / ma10w_4wk - 1) * 100

        # Weekly RSI-14
        delta = close.diff()
        gain  = delta.clip(lower=0).rolling(14).mean()
        loss  = (-delta.clip(upper=0)).rolling(14).mean()
        rsi   = float((100 - 100 / (1 + gain / loss)).iloc[-1])

        # Weekly CMF-20 (Chaikin Money Flow)
        try:
            high_s   = hist['High'].reindex(close.index)
            low_s    = hist['Low'].reindex(close.index)
            vol_s    = hist['Volume'].reindex(close.index)
            hl_range = (high_s - low_s).replace(0, float('nan'))
            mfm      = ((close - low_s) - (high_s - close)) / hl_range
            mfv      = mfm * vol_s
            cmf      = round(float(mfv.rolling(20).sum().iloc[-1] / vol_s.rolling(20).sum().iloc[-1]), 3)
        except Exception:
            cmf = None

        return {
            'ticker':      ticker,
            'price':       round(price, 2),
            'ma10w':       round(ma10w, 2),
            'ma20w':       round(ma20w, 2),
            'ma43w':       round(ma43w, 2),
            'ext_now':     round(ext_now, 1),
            'ext_90p':     round(ext_90p, 1),
            'ext_max':     round(ext_max, 1),
            'runway':      round(runway, 1),
            'ceiling_90':  round(ceiling_90, 2),
            'ceiling_max': round(ceiling_max, 2),
            'pct_from_hi': round(pct_from_hi, 1),
            'slope':       round(slope, 1),
            'rsi':         round(rsi, 1),
            'cmf':         cmf,
            'pct_vs_87w':  pct_vs_87w,
            'above_10w':   ext_now > 0,
        }
    except Exception:
        return None


# ── Category ──────────────────────────────────────────────────────────────────

def _category(r):
    """Returns (label, bg, border) based on runway consumed and RSI."""
    ext_now  = r['ext_now']
    ext_90p  = r['ext_90p']
    runway   = r['runway']
    rsi      = r['rsi']

    if not r['above_10w']:
        return 'below',    '',        ''

    # RSI overbought or runway nearly gone → near ceiling
    # But if the stock is still far below its 52w high (>15%), the MA-extension
    # ceiling is a stale reference (recovering stock, MA catching up) — reclassify
    # as extended rather than ceiling since real overhead supply isn't there yet.
    pct_from_hi = r.get('pct_from_hi', 0)
    if rsi >= 75 or (ext_90p > 0 and runway < 10):
        if pct_from_hi < -15:
            return 'extended', '#1a1000', '#f0883e'  # amber — blown MA ceiling but far from 52w hi
        return 'ceiling',  '#1a0000', '#f85149'   # red

    if runway >= 67:
        return 'fresh',    '#0d1a0d', '#3fb950'   # green — lots of room
    elif runway >= 34:
        return 'midway',   '#1c1700', '#d4a017'   # gold — moderate
    else:
        return 'extended', '#1a1000', '#f0883e'   # amber — stretched


def _lt_struct(pct):
    """Returns (short_label, ansi_color) for structural 87w MA extension."""
    if pct is None:
        return '—',        '\033[90m'
    if pct > 100:
        return 'extreme',  '\033[31m'       # red
    if pct > 50:
        return 'high',     '\033[38;5;208m' # orange
    if pct > 25:
        return 'moderate', '\033[33m'       # yellow
    if pct > 10:
        return 'mild',     '\033[37m'       # white
    if pct >= 0:
        return 'at base',  '\033[32m'       # green
    return 'below LT',     '\033[34m'       # blue


def _runway_bar(runway, width=12):
    """ASCII progress bar showing runway consumed."""
    if runway is None:
        return '─' * width
    filled = max(0, min(width, round(runway / 100 * width)))
    empty  = width - filled
    return '█' * filled + '░' * empty


# ── HTML builder ──────────────────────────────────────────────────────────────

def _pct_cell(pct, neutral=False):
    if neutral or pct is None:
        return f'<td style="color:#8b949e">{pct:+.1f}%</td>' if pct is not None else '<td style="color:#484f58">—</td>'
    color = '#3fb950' if pct >= 0 else '#f85149'
    return f'<td style="color:{color};font-weight:600">{pct:+.1f}%</td>'


def _rsi_cell(rsi):
    if rsi is None:
        return '<td style="color:#484f58">—</td>'
    if rsi >= 75:
        color = '#f85149'
    elif rsi >= 60:
        color = '#d4a017'
    else:
        color = '#3fb950'
    return f'<td style="color:{color};font-weight:600">{rsi:.0f}</td>'


def _cmf_cell(cmf):
    if cmf is None:
        return '<td style="color:#484f58">—</td>'
    if cmf >= 0.10:
        color = '#3fb950'
    elif cmf >= 0:
        color = '#8b949e'
    elif cmf >= -0.10:
        color = '#d4a017'
    else:
        color = '#f85149'
    return f'<td style="color:{color};font-weight:600">{cmf:+.3f}</td>'


def _lt_struct_cell(pct):
    if pct is None:
        return '<td style="color:#484f58">—</td>'
    label, _ = _lt_struct(pct)
    if pct > 100:
        color, bg = '#f85149', 'rgba(248,81,73,0.10)'
    elif pct > 50:
        color, bg = '#f0883e', 'rgba(240,136,62,0.10)'
    elif pct > 25:
        color, bg = '#d4a017', 'rgba(212,160,23,0.08)'
    elif pct > 10:
        color, bg = '#8b949e', 'transparent'
    elif pct >= 0:
        color, bg = '#3fb950', 'rgba(63,185,80,0.08)'
    else:
        color, bg = '#58a6ff', 'rgba(88,166,255,0.08)'
    sign = '+' if pct >= 0 else ''
    return (f'<td style="background:{bg};border-radius:3px">'
            f'<span style="color:{color};font-weight:600;font-size:11px">{sign}{pct:.1f}%</span>'
            f'<span style="color:{color};font-size:10px;margin-left:4px;opacity:0.8">{label}</span>'
            f'</td>')


def build_html(fresh, midway, extended, ceiling, below, no_data, now, label, regime=None, earnings_map=None):
    def rows_for(group, badge_color, badge_label):
        out = ''
        for r in group:
            cat, bg, border = _category(r)
            row_style = f'background:{bg};border-left:3px solid {border};' if bg else ''
            bar   = _runway_bar(r['runway'])
            slope_str = f"{r['slope']:+.1f}%"
            slope_col = '#3fb950' if r['slope'] > 0 else '#f85149'
            er_badge = earnings_html_badge((earnings_map or {}).get(r['ticker']))
            out += f"""<tr style="{row_style}">
              <td class="ticker">{r['ticker']}{er_badge}</td>
              <td><span class="badge" style="background:{badge_color}">{badge_label}</span></td>
              <td>${r['price']}</td>
              <td style="color:#8b949e">${r['ma10w']:.2f}</td>
              {_pct_cell(r['ext_now'], neutral=False)}
              <td style="color:#8b949e">{r['ext_90p']:+.1f}%</td>
              <td style="font-family:monospace;color:#58a6ff;letter-spacing:-1px">{bar}</td>
              <td style="color:#e6edf3;font-weight:600">${r['ceiling_90']:.2f}</td>
              {_pct_cell(r['pct_from_hi'])}
              <td style="color:{slope_col};font-size:11px">{slope_str}</td>
              {_rsi_cell(r['rsi'])}
              {_cmf_cell(r.get('cmf'))}
              {_lt_struct_cell(r['pct_vs_87w'])}
            </tr>"""
        return out

    def rows_for_below(group):
        out = ''
        for r in sorted(group, key=lambda x: -x['ext_now']):  # closest to MA first
            slope_str = f"{r['slope']:+.1f}%"
            slope_col = '#3fb950' if r['slope'] > 0 else '#f85149'
            hi_c = '#3fb950' if r['pct_from_hi'] >= -5 else ('#d4a017' if r['pct_from_hi'] >= -20 else '#f85149')
            out += f"""<tr style="opacity:0.75">
              <td class="ticker" style="color:#8b949e">{r['ticker']}</td>
              <td><span class="badge" style="background:#21262d;color:#8b949e">↓ below</span></td>
              <td style="color:#8b949e">${r['price']}</td>
              <td style="color:#484f58">${r['ma10w']:.2f}</td>
              <td style="color:#f85149;font-weight:600">{r['ext_now']:+.1f}%</td>
              <td style="color:#484f58">{r['ext_90p']:+.1f}%</td>
              <td style="color:#484f58;font-family:monospace">── n/a ──</td>
              <td style="color:#484f58">${r['ceiling_90']:.2f}</td>
              <td style="color:{hi_c};font-weight:600">{r['pct_from_hi']:+.1f}%</td>
              <td style="color:{slope_col};font-size:11px">{slope_str}</td>
              {_rsi_cell(r['rsi'])}
              {_cmf_cell(r.get('cmf'))}
              {_lt_struct_cell(r['pct_vs_87w'])}
            </tr>"""
        return out

    rows  = rows_for(fresh,    '#1a4731', '▓ fresh')
    rows += rows_for(midway,   '#4a3800', '▒ midway')
    rows += rows_for(extended, '#4a2800', '░ extended')
    rows += rows_for(ceiling,  '#4a0000', '✕ ceiling')

    below_rows = rows_for_below(below) if below else ''
    nd_tickers = '  ·  '.join(no_data) if no_data else '—'

    total_above = len(fresh) + len(midway) + len(extended) + len(ceiling)

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Extension Scan — {now}</title>
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
  .section {{ font-size: 11px; color: #8b949e; margin: 16px 0 6px; border-top: 1px solid #21262d; padding-top: 10px; }}
  .disclaimer {{ color: #484f58; font-size: 10px; margin-top: 24px; border-top: 1px solid #21262d; padding-top: 8px; }}
{REGIME_CSS}
{EVENT_CSS}
</style>
</head>
<body>
<h1>📡 Extension Scan <span style="font-size:13px;color:#8b949e;font-weight:400">— {label}</span></h1>
{regime_html(regime) if regime else ''}
<div class="subtitle">{now} &nbsp;·&nbsp; weekly bars · 3yr history &nbsp;·&nbsp; runway = % of 90th-pct ceiling still unused &nbsp;·&nbsp; ceiling = implied price at historical ceiling</div>

<div style="font-size:11px;color:#8b949e;margin-bottom:8px;padding:8px 12px;background:#161b22;border-radius:6px;border-left:3px solid #30363d;">
  <span style="color:#e6edf3;font-weight:600">87w Struct</span> — how far the price sits above its 87-week (≈20-month) moving average. A different question from the 10w runway: the 10w ceiling tells you short-term momentum extension; the 87w tells you long-term structural extension from the base.
  &nbsp;·&nbsp; <span style="color:#3fb950;font-weight:600">at base</span> ≤10% &nbsp;·&nbsp;
  <span style="color:#8b949e;font-weight:600">mild</span> 10–25% &nbsp;·&nbsp;
  <span style="color:#d4a017;font-weight:600">moderate</span> 25–50% &nbsp;·&nbsp;
  <span style="color:#f0883e;font-weight:600">high</span> 50–100% &nbsp;·&nbsp;
  <span style="color:#f85149;font-weight:600">extreme</span> &gt;100% &nbsp;·&nbsp;
  <span style="color:#58a6ff;font-weight:600">below LT</span> under 87w MA
</div>

<div class="summary">
  <span>{len(fresh)}</span> fresh (runway ≥ 67%) &nbsp;·&nbsp;
  <span>{len(midway)}</span> midway (34–66%) &nbsp;·&nbsp;
  <span>{len(extended)}</span> extended (10–33%) &nbsp;·&nbsp;
  <span>{len(ceiling)}</span> near ceiling / RSI ≥ 75 &nbsp;·&nbsp;
  <span>{len(below)}</span> below 10w MA
</div>

<table>
  <thead>
    <tr>
      <th>Ticker</th><th>Zone</th><th>Price</th>
      <th>10w MA</th><th>vs 10wMA</th><th>Ceiling%</th><th>Runway</th>
      <th>Ceiling $</th><th>vs 52wHi</th><th>Slope</th><th>RSI</th><th>CMF 20w</th>
      <th>87w Struct</th>
    </tr>
  </thead>
  <tbody>{rows}</tbody>
</table>

<div class="section">Below 10w MA — {len(below)} names &nbsp;·&nbsp; <span style="color:#484f58;font-size:10px">sorted by proximity to MA (closest first) · runway n/a · ceiling shown as reference if/when MA is reclaimed</span></div>
<table>
  <thead>
    <tr>
      <th>Ticker</th><th>Zone</th><th>Price</th>
      <th>10w MA</th><th>vs 10wMA</th><th>Ceiling%</th><th>Runway</th>
      <th>Ceiling $</th><th>vs 52wHi</th><th>Slope</th><th>RSI</th><th>CMF 20w</th>
      <th>87w Struct</th>
    </tr>
  </thead>
  <tbody>{below_rows}</tbody>
</table>

<div class="section">No data — {nd_tickers}</div>
<div class="disclaimer">For informational purposes only. Market dynamics change constantly — these outputs are auto-generated from Yahoo Finance data and may not reflect current conditions. Not tailored financial advice. Not a recommendation to buy, sell, or hold any security. Always do your own research. · Ceiling = 10wMA × (1 + 90th-pct historical extension).</div>
</body>
</html>"""


# ── CLI table (used when explicit tickers passed) ─────────────────────────────

_ZONE_LABEL = {'fresh': '▓ fresh', 'midway': '▒ midway', 'extended': '░ extnd', 'ceiling': '✕ ceil', 'below': '  below'}
_ZONE_COLOR = {
    'fresh':    '\033[32m',
    'midway':   '\033[33m',
    'extended': '\033[38;5;208m',
    'ceiling':  '\033[31m',
    'below':    '\033[90m',
}
_RESET = '\033[0m'
_BOLD  = '\033[1m'

_ANSI_RE = re.compile(r'\033\[[0-9;]*m')

def _vlen(s):
    """Visible length of string after stripping ANSI escape codes."""
    return len(_ANSI_RE.sub('', s))

def _ljust(s, w):
    return s + ' ' * max(0, w - _vlen(s))

def _rjust(s, w):
    return ' ' * max(0, w - _vlen(s)) + s

# Column widths (visible chars)
_W = dict(ticker=6, zone=9, price=9, ma10w=9, ext=7, ceil=20, runway=19, rsi=3, slope=7, hi=7, cmf=7, lt=16)


def _cli_row(r):
    cat = _category(r)[0]
    col = _ZONE_COLOR.get(cat, '')

    bar     = _runway_bar(r['runway'], width=14)
    slope_c = '\033[32m' if r['slope'] > 0 else '\033[31m'
    hi_c    = '\033[32m' if r['pct_from_hi'] >= -5 else ('\033[33m' if r['pct_from_hi'] >= -20 else '\033[31m')
    rsi_c   = '\033[31m' if r['rsi'] >= 75 else ('\033[33m' if r['rsi'] >= 60 else '\033[32m')

    ticker_s  = _ljust(_BOLD + r['ticker'] + _RESET, _W['ticker'])
    zone_s    = _ljust(col + _ZONE_LABEL.get(cat, cat) + _RESET, _W['zone'])
    price_s   = _rjust(f"${r['price']:.2f}", _W['price'])
    ma10w_s   = _rjust('\033[90m' + f"${r['ma10w']:.2f}" + _RESET, _W['ma10w'])
    ext_s     = _rjust(col + f"{r['ext_now']:+.1f}%" + _RESET, _W['ext'])
    if r['ext_now'] > r['ext_90p']:
        overshoot = r['ext_now'] - r['ext_90p']
        ceil_s = _rjust('\033[31m' + f"↑ blown +{overshoot:.1f}%" + _RESET, _W['ceil'])
    else:
        upside = (r['ceiling_90'] - r['price']) / r['price'] * 100
        ceil_s = _rjust(f"${r['ceiling_90']:.2f} ({upside:+.1f}%)", _W['ceil'])
    if cat == 'below':
        runway_s = _ljust('\033[90m' + '─' * 14 + '  n/a' + _RESET, _W['runway'])
    else:
        runway_s = _ljust('\033[34m' + bar + _RESET + f" {r['runway']:>3.0f}%", _W['runway'])
    rsi_s     = _rjust(rsi_c + f"{r['rsi']:.0f}" + _RESET, _W['rsi'])
    slope_s   = _rjust(slope_c + f"{r['slope']:+.1f}%" + _RESET, _W['slope'])
    hi_s      = _rjust(hi_c + f"{r['pct_from_hi']:+.1f}%" + _RESET, _W['hi'])

    cmf_val = r.get('cmf')
    if cmf_val is None:
        cmf_col, cmf_str = '\033[90m', '—'
    elif cmf_val >= 0.10:
        cmf_col, cmf_str = '\033[32m', f'{cmf_val:+.3f}'
    elif cmf_val >= 0:
        cmf_col, cmf_str = '\033[37m', f'{cmf_val:+.3f}'
    elif cmf_val >= -0.10:
        cmf_col, cmf_str = '\033[33m', f'{cmf_val:+.3f}'
    else:
        cmf_col, cmf_str = '\033[31m', f'{cmf_val:+.3f}'
    cmf_s = _rjust(cmf_col + cmf_str + _RESET, _W['cmf'])

    lt_label, lt_col = _lt_struct(r.get('pct_vs_87w'))
    pct87 = r.get('pct_vs_87w')
    pct87_str = f"{pct87:+.1f}% {lt_label}" if pct87 is not None else '—'
    lt_s = _ljust(lt_col + pct87_str + _RESET, _W['lt'])

    print(f"  {ticker_s}  {zone_s}  {price_s}  {ma10w_s}  {ext_s}  {ceil_s}  {runway_s}  {rsi_s}  {slope_s}  {hi_s}  {cmf_s}  {lt_s}")


def _cli_header():
    W = _W
    print(f"\n  {'TICKER':<{W['ticker']}}  {'ZONE':<{W['zone']}}  {'PRICE':>{W['price']}}  "
          f"{'10w MA':>{W['ma10w']}}  {'10wMA%':>{W['ext']}}  {'CEIL $ / OVERSHOOT':>{W['ceil']}}  "
          f"{'RUNWAY':<{W['runway']}}  {'RSI':>{W['rsi']}}  {'SLOPE':>{W['slope']}}  {'52wHi':>{W['hi']}}  {'CMF':>{W['cmf']}}  {'87w STRUCT':<{W['lt']}}")
    print(f"  {'─'*W['ticker']}  {'─'*W['zone']}  {'─'*W['price']}  "
          f"{'─'*W['ma10w']}  {'─'*W['ext']}  {'─'*W['ceil']}  {'─'*W['runway']}  "
          f"{'─'*W['rsi']}  {'─'*W['slope']}  {'─'*W['hi']}  {'─'*W['cmf']}  {'─'*W['lt']}")


# ── Main ──────────────────────────────────────────────────────────────────────

def run(tickers, label, cli_only=False):
    print(f'\n  Extension Scan — {len(tickers)} tickers ...', flush=True)
    with ThreadPoolExecutor(max_workers=12) as ex:
        results = list(ex.map(get_extension_data, tickers))

    valid   = [r for r in results if r is not None]
    above   = [r for r in valid if r['above_10w']]
    below   = sorted([r for r in valid if not r['above_10w']], key=lambda x: -x['ext_now'])
    no_data = [t for t, r in zip(tickers, results) if r is None]

    above.sort(key=lambda x: -x['runway'])

    fresh    = [r for r in above if _category(r)[0] == 'fresh']
    midway   = [r for r in above if _category(r)[0] == 'midway']
    extended = [r for r in above if _category(r)[0] == 'extended']
    ceiling  = [r for r in above if _category(r)[0] == 'ceiling']

    print(f'  ▓ {len(fresh)} fresh  ·  ▒ {len(midway)} midway  ·  ░ {len(extended)} extended  ·  ✕ {len(ceiling)} ceiling  ·  {len(below)} below  ·  {len(no_data)} no data')

    if cli_only:
        _cli_header()
        for r in fresh + midway + extended + ceiling + below:
            _cli_row(r)
        if no_data:
            print(f'\n  No data: {", ".join(no_data)}')
        print()
        return

    now    = datetime.utcnow().strftime('%b %d %Y  %H:%M UTC')
    regime = get_regime()
    above_tickers = [r['ticker'] for r in fresh + midway + extended + ceiling]
    earnings_map  = get_earnings_batch(above_tickers) if above_tickers else {}
    html   = build_html(fresh, midway, extended, ceiling, below, no_data, now, label,
                        regime=regime, earnings_map=earnings_map)

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'extension_scan.html')
    with open(out, 'w') as f:
        f.write(html)

    print(f'  Opened → {out}\n')
    webbrowser.open(f'file://{out}')


if __name__ == '__main__':
    args = sys.argv[1:]

    if not args:
        tickers = list(dict.fromkeys(UNIVERSE))
        tickers += [t for t in WATCHLIST if t not in tickers]
        label = 'Universe + Watchlist'
    elif args == ['--universe']:
        tickers = list(dict.fromkeys(UNIVERSE))
        label = 'Universe'
    elif args == ['--watchlist']:
        tickers = list(dict.fromkeys(WATCHLIST))
        label = 'Watchlist'
    elif args == ['--dividend']:
        tickers = list(dict.fromkeys(DIVIDEND_UNIVERSE))
        label = 'Dividend Universe'
    elif args == ['--india']:
        from india_screener import UNIVERSE as IND_U, WATCHLIST as IND_W
        tickers = [t for t in dict.fromkeys(IND_U + IND_W) if '&' not in t]
        label = 'India Universe + Watchlist'
    elif args == ['--india', '--universe']:
        from india_screener import UNIVERSE as IND_U
        tickers = [t for t in dict.fromkeys(IND_U) if '&' not in t]
        label = 'India Universe'
    elif args == ['--india', '--watchlist']:
        from india_screener import WATCHLIST as IND_W
        tickers = [t for t in dict.fromkeys(IND_W) if '&' not in t]
        label = 'India Watchlist'
    else:
        tickers = [t.upper() for t in args if not t.startswith('--')]
        label = ', '.join(tickers)
        run(tickers, label, cli_only=True)
        sys.exit(0)

    run(tickers, label)
