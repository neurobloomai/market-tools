"""
regime.py — Market regime classifier.

Shared by pop_scan.py and extension_scan.py. No scan imports — avoids
circular dependencies. Returns pure data; callers add their own styling.
"""

import yfinance as yf

# CSS block for the regime banner — include inside <style> in any scan page
REGIME_CSS = """
  .regime-banner { font-size:11px; font-weight:500; padding:9px 14px; border-radius:6px; margin-bottom:14px; line-height:1.7; }
  .regime-label  { font-weight:700; font-size:12px; letter-spacing:.08em; margin-right:12px; }
  .regime-bull    { background:rgba(63,185,80,0.10);  border-left:3px solid #3fb950; color:#3fb950; }
  .regime-caution { background:rgba(212,160,23,0.10); border-left:3px solid #d4a017; color:#d4a017; }
  .regime-defense { background:rgba(240,136,62,0.10); border-left:3px solid #f0883e; color:#f0883e; }
  .regime-storm   { background:rgba(248,81,73,0.12);  border-left:3px solid #f85149; color:#f85149; }
  .regime-unknown { background:rgba(139,148,158,0.10);border-left:3px solid #484f58; color:#8b949e; }"""


def get_regime():
    """
    Fetch SPY 10w MA position + VIX and classify market regime.

    Returns dict:
      label    — 'BULL' | 'CAUTION' | 'DEFENSE' | 'STORM' | 'UNKNOWN'
      vix      — float or None
      spy_pct  — % above/below SPY 10w MA, float or None
      note     — one-line action guidance
    """
    try:
        vix_hist = yf.Ticker('^VIX').history(period='5d', interval='1d')
        vix      = float(vix_hist['Close'].iloc[-1]) if not vix_hist.empty else None

        spy_hist = yf.Ticker('SPY').history(period='3mo', interval='1wk')
        if len(spy_hist) >= 10:
            spy_price = float(spy_hist['Close'].iloc[-1])
            ma10w     = float(spy_hist['Close'].iloc[-10:].mean())
            spy_pct   = (spy_price - ma10w) / ma10w * 100
        else:
            spy_pct = None
    except Exception:
        return {'label': 'UNKNOWN', 'vix': None, 'spy_pct': None,
                'note': 'regime data unavailable'}

    v         = vix or 0
    spy_below = spy_pct is not None and spy_pct < -1.0

    if v > 35:
        label = 'STORM'
        note  = 'Sell-premium only — directional setups unreliable'
    elif v > 28 or spy_below:
        label = 'DEFENSE'
        note  = 'Elevated risk — size down, defined-risk structures only'
    elif v > 22 or (spy_pct is not None and abs(spy_pct) < 1.0):
        label = 'CAUTION'
        note  = 'Setups valid — watch for macro overrides, half-size preferred'
    else:
        label = 'BULL'
        note  = 'Setups live — standard sizing'

    return {'label': label, 'vix': vix, 'spy_pct': spy_pct, 'note': note}


_SIZE_BARS = {
    'FULL':    '■■■■',
    'HALF':    '■■░░',
    'QUARTER': '■░░░',
    'SELL-IV': '░░░░',
}
_SIZE_HTML_COLOR = {
    'FULL':    '#3fb950',
    'HALF':    '#d4a017',
    'QUARTER': '#f0883e',
    'SELL-IV': '#f85149',
}
_SIZE_TO_REGIME = {
    'FULL':    'BULL',
    'HALF':    'CAUTION',
    'QUARTER': 'DEFENSE',
    'SELL-IV': 'STORM',
}


def sizing_signal(regime):
    """
    Derive position sizing guidance from regime. Pure function — no data fetch.

    Returns dict:
      size  — 'FULL' | 'HALF' | 'QUARTER' | 'SELL-IV'
      bar   — ASCII progress bar (4 chars)
      note  — one-line actionable guidance
      html_color — hex color for HTML rendering
    """
    label = regime.get('label', 'UNKNOWN')

    if label == 'STORM':
        size = 'SELL-IV'
        note = 'Sell premium into elevated VIX — no directional setups'
    elif label == 'DEFENSE':
        size = 'QUARTER'
        note = 'Defined-risk spreads only — smallest size, avoid directional'
    elif label == 'CAUTION':
        size = 'HALF'
        note = 'Half size — watch for macro overrides before entry'
    else:
        size = 'FULL'
        note = 'Standard allocation — all setups valid'

    return {
        'size':       size,
        'bar':        _SIZE_BARS.get(size, '????'),
        'note':       note,
        'html_color': _SIZE_HTML_COLOR.get(size, '#8b949e'),
    }


def regime_html(regime):
    """HTML div for the regime + sizing banner — insert after <h1> in any scan page."""
    label = regime['label']
    vix_s = f"VIX {regime['vix']:.1f}" if regime['vix'] is not None else 'VIX —'
    spy_s = (f"SPY {regime['spy_pct']:+.1f}% vs 10w"
             if regime['spy_pct'] is not None else 'SPY vs 10w —')
    css   = f'regime-{label.lower()}'
    sz    = sizing_signal(regime)
    sc    = sz['html_color']
    return (f'<div class="regime-banner {css}">'
            f'<span class="regime-label">REGIME  {label}</span>'
            f'{vix_s} &nbsp;·&nbsp; {spy_s} &nbsp;·&nbsp; {regime["note"]}'
            f'<br>'
            f'<span style="color:{sc};font-weight:700;letter-spacing:.06em;margin-right:10px">'
            f'SIZING  {sz["size"]}</span>'
            f'<span style="font-family:monospace;color:{sc};margin-right:10px">{sz["bar"]}</span>'
            f'<span style="color:#8b949e;font-size:10px">{sz["note"]}</span>'
            f'</div>')
