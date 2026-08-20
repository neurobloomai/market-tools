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
    elif v > 22 or (spy_pct is not None and abs(spy_pct) < 1.5):
        label = 'CAUTION'
        note  = 'Setups valid — watch for macro overrides, half-size preferred'
    else:
        label = 'BULL'
        note  = 'Setups live — standard sizing'

    return {'label': label, 'vix': vix, 'spy_pct': spy_pct, 'note': note}


def regime_html(regime):
    """HTML div for the regime banner — insert after <h1> in any scan page."""
    label = regime['label']
    vix_s = f"VIX {regime['vix']:.1f}" if regime['vix'] is not None else 'VIX —'
    spy_s = (f"SPY {regime['spy_pct']:+.1f}% vs 10w"
             if regime['spy_pct'] is not None else 'SPY vs 10w —')
    css   = f'regime-{label.lower()}'
    return (f'<div class="regime-banner {css}">'
            f'<span class="regime-label">REGIME  {label}</span>'
            f'{vix_s} &nbsp;·&nbsp; {spy_s} &nbsp;·&nbsp; {regime["note"]}'
            f'</div>')
