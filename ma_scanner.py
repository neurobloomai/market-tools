"""
ma_scanner.py — MA Proximity Scanner
======================================

Scans UNIVERSE tickers across three timeframes for a specific setup:

    MA10 > MA20                        (alignment intact)
    price within -3% to +3% of MA10   (band: approaching OR just above)
    MA10 is rising                     (slope positive over lookback window)
    MA20 is flat or rising             (no downtrend)
    Daily: price > MA50                (broader trend gate)

The -3% to +3% band gives early signals:
  negative side: price testing MA10 from below — approaching reclaim
  positive side: price just above MA10 — confirmed but not extended

Timeframes
----------
  1H   — hourly bars (market hours only)
  4H   — constructed from 1H via positional grouping (every 4 market bars),
          NOT calendar resample which misaligns with market sessions
  D    — daily bars with MA50 gate

Multi-timeframe confluences (same setup firing on 2–3 TFs) are the
strongest signals and are sorted to the top.

DISCLAIMER
----------
This scanner is a research and framework-building tool.
Output is NOT financial advice and NOT a recommendation to buy or sell
any security. All signals require independent verification against
current fundamentals, position sizing, and personal risk tolerance.
Past scanner performance does not predict future results.
Markets can move against any setup regardless of technical alignment.
The author assumes no liability for trading decisions made using this tool.
Use at your own risk.
"""

import yfinance as yf
import pandas as pd
from concurrent.futures import ThreadPoolExecutor
from datetime import date
import warnings
warnings.filterwarnings('ignore')

from screener import UNIVERSE

# ── Configuration ─────────────────────────────────────────────────────────────

BAND_LOW         = -3.0  # price can be up to 3% BELOW MA10 (early/approaching signal)
BAND_HIGH        =  3.0  # price can be up to 3% ABOVE MA10 (confirmed but not extended)
SLOPE_LOOKBACK_1H = 5    # bars back to measure MA10 slope on 1H
SLOPE_LOOKBACK_4H = 4    # bars back on 4H
SLOPE_LOOKBACK_D  = 5    # bars back on Daily


# ── Core helpers ──────────────────────────────────────────────────────────────

def make_4h(close_1h: pd.Series) -> pd.Series:
    """
    Build 4H close series from 1H by positional grouping (every 4 market bars).

    Calendar-based resampling (resample('4h')) creates misaligned candles
    because market hours (9:30–4pm ET = 6.5h/day) don't divide evenly into
    4-hour calendar blocks. Positional grouping avoids this entirely.
    """
    vals = close_1h.values
    groups = [vals[i:i+4] for i in range(0, len(vals) - 3, 4)]
    return pd.Series([g[-1] for g in groups])


def check_tf(closes, slope_lb, require_ma50=False):
    """
    Evaluate the tight MA setup on a close series.

    Uses iloc[-2] (last confirmed closed bar) to avoid reading an
    incomplete in-progress candle during live market hours.

    Returns a dict with price/MA values and passes=True/False,
    or None if there is insufficient data.
    """
    if len(closes) < 22:
        return None

    ma10 = closes.rolling(10).mean()
    ma20 = closes.rolling(20).mean()

    p   = closes.iloc[-2]   # last closed bar — not the live/incomplete bar
    m10 = ma10.iloc[-2]
    m20 = ma20.iloc[-2]

    if any(pd.isna([p, m10, m20])) or m10 <= 0 or m20 <= 0:
        return None

    pct = (p / m10 - 1) * 100

    # MA10 slope — must be positive (rising)
    if len(ma10) < (2 + slope_lb):
        return None
    m10_prev = ma10.iloc[-2 - slope_lb]
    if pd.isna(m10_prev):
        return None
    m10_slope = m10 - m10_prev

    # MA20 slope — flat or rising
    m20_slope = 0.0
    if len(ma20) >= (2 + slope_lb * 2):
        m20_prev = ma20.iloc[-2 - slope_lb * 2]
        if not pd.isna(m20_prev):
            m20_slope = m20 - m20_prev

    # MA50 gate for daily (broader trend confirmation)
    ma50_ok = True
    if require_ma50 and len(closes) >= 52:
        m50 = closes.rolling(50).mean().iloc[-2]
        ma50_ok = not pd.isna(m50) and p > m50

    passes = (
        m10 > m20 and                    # alignment: MA10 above MA20
        BAND_LOW <= pct <= BAND_HIGH and # price within -3% to +3% of MA10
        m10_slope > 0 and                # MA10 rising
        m20_slope >= 0 and               # MA20 flat or rising
        ma50_ok
    )

    return {
        'price':      round(p, 2),
        'ma10':       round(m10, 2),
        'ma20':       round(m20, 2),
        'pct':        round(pct, 2),
        'ma10_slope': round(m10_slope, 4),
        'passes':     passes,
    }


# ── Per-ticker scan ────────────────────────────────────────────────────────────

def scan_ticker(ticker):
    results = {}

    try:
        t  = yf.Ticker(ticker)
        h1 = t.history(period='60d', interval='1h', prepost=False)
        if len(h1) >= 30:
            r = check_tf(h1['Close'], SLOPE_LOOKBACK_1H)
            if r:
                results['1H'] = r

            h4 = make_4h(h1['Close'])
            if len(h4) >= 22:
                r4 = check_tf(h4, SLOPE_LOOKBACK_4H)
                if r4:
                    results['4H'] = r4
    except Exception:
        pass

    try:
        t  = yf.Ticker(ticker)
        d1 = t.history(period='6mo', interval='1d', prepost=False)
        if len(d1) >= 30:
            rd = check_tf(d1['Close'], SLOPE_LOOKBACK_D, require_ma50=True)
            if rd:
                results['D'] = rd
    except Exception:
        pass

    return ticker, results


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    today = date.today().strftime('%Y-%m-%d')
    print(f"\nMA Proximity Scanner  [{today}]")
    print(f"Setup: MA10 > MA20 | price {BAND_LOW}% to {BAND_HIGH:+}% of MA10 | MA10 rising | MA20 flat+ | Daily: price > MA50")
    print(f"Scanning {len(UNIVERSE)} UNIVERSE tickers across 1H / 4H / Daily...\n")

    with ThreadPoolExecutor(max_workers=20) as ex:
        all_results = list(ex.map(scan_ticker, UNIVERSE))

    hits = {}
    for ticker, res in all_results:
        matched = {tf: v for tf, v in res.items() if v['passes']}
        if matched:
            hits[ticker] = matched

    sorted_hits = sorted(hits.items(), key=lambda x: -len(x[1]))

    print(f"{'Ticker':<8} {'TFs':^7} {'TF':<4} {'Price':>8} {'MA10':>8} {'MA20':>8} {'%>MA10':>8}  MA10 slope")
    print("─" * 72)

    for ticker, tfs in sorted_hits:
        tf_label = '/'.join(tfs.keys())
        first = True
        for tf, v in tfs.items():
            prefix = f"{ticker:<8} {tf_label:^7}" if first else f"{'':8} {'':7}"
            print(f"{prefix}  {tf:<4} {v['price']:>8.2f} {v['ma10']:>8.2f} {v['ma20']:>8.2f} {v['pct']:>7.2f}%  ↑{v['ma10_slope']:.3f}")
            first = False
        print()

    multi  = [x for x in sorted_hits if len(x[1]) >= 2]
    single = [x for x in sorted_hits if len(x[1]) == 1]
    print("─" * 72)
    print(f"Multi-TF confluences : {len(multi)}")
    print(f"Single-TF hits       : {len(single)}")
    print(f"Total                : {len(hits)} / {len(UNIVERSE)} tickers")
    print(f"\nDISCLAIMER: Research tool only. Not financial advice.")
