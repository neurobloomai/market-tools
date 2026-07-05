"""
ma_scanner.py — MA Proximity Scanner  (Timeframe Hierarchy Edition)
=====================================================================

Timeframe hierarchy — each level gates the one below it:

  Weekly  MA10 > MA20, slope rising     — mandatory top gate, no band check
  Daily   MA10 > MA20, price in band    — first actionable signal
  4H      MA10 > MA20, price in band    — only shown if Daily passes
  1H      MA10 > MA20, price in band    — only shown if 4H passes

If Weekly is not aligned the ticker is skipped entirely.
If Daily does not show a setup, 4H and 1H are not evaluated.

Band: -3% to +3% of MA10
  negative side — price approaching MA10 from below (early/approaching signal)
  positive side — price just above MA10 (confirmed, not extended)

Daily additionally requires price > MA50 as broader trend gate.

4H is constructed from 1H via positional grouping (every 4 market bars),
NOT calendar resampling which misaligns with market session hours.

DISCLAIMER
----------
Research and framework-building tool only.
Output is NOT financial advice and NOT a recommendation to buy or sell
any security. All signals require independent verification against
current fundamentals, position sizing, and personal risk tolerance.
Use at your own risk.
"""

import yfinance as yf
import pandas as pd
from concurrent.futures import ThreadPoolExecutor
from datetime import date
import warnings
warnings.filterwarnings('ignore')

import argparse
from screener import UNIVERSE, WATCHLIST

# ── Configuration ─────────────────────────────────────────────────────────────

BAND_LOW          = -3.0   # price up to 3% BELOW MA10 (approaching from below)
BAND_HIGH         =  3.0   # price up to 3% ABOVE MA10 (confirmed, not extended)

SLOPE_LOOKBACK_W  =  3     # weekly bars for slope measurement
SLOPE_LOOKBACK_D  =  5     # daily bars
SLOPE_LOOKBACK_4H =  4     # 4H bars
SLOPE_LOOKBACK_1H =  5     # hourly bars


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_4h(close_1h: pd.Series) -> pd.Series:
    """
    Build 4H close series from 1H by positional grouping (every 4 market bars).
    Calendar resampling creates misaligned candles due to 9:30–4pm market hours.
    """
    vals = close_1h.values
    groups = [vals[i:i+4] for i in range(0, len(vals) - 3, 4)]
    return pd.Series([g[-1] for g in groups])


def check_weekly_gate(closes) -> bool:
    """
    Weekly alignment gate. MA10 > MA20 with both slopes rising/flat.
    No band check — weekly is trend confirmation, not an entry signal.
    """
    if len(closes) < 22:
        return False
    ma10 = closes.rolling(10).mean()
    ma20 = closes.rolling(20).mean()
    m10  = ma10.iloc[-2]
    m20  = ma20.iloc[-2]
    if any(pd.isna([m10, m20])) or m10 <= 0:
        return False
    lb = SLOPE_LOOKBACK_W
    if len(ma10) < (2 + lb):
        return False
    m10_prev = ma10.iloc[-2 - lb]
    if pd.isna(m10_prev):
        return False
    m10_slope = m10 - m10_prev
    m20_slope = 0.0
    if len(ma20) >= (2 + lb * 2):
        m20_prev = ma20.iloc[-2 - lb * 2]
        if not pd.isna(m20_prev):
            m20_slope = m20 - m20_prev
    return m10 > m20 and m10_slope > 0 and m20_slope >= 0


def check_tf(closes, slope_lb, require_ma50=False):
    """
    Evaluate MA proximity setup on a close series.
    Uses iloc[-2] (last confirmed closed bar — safe during intraday).
    Returns dict with passes=True/False, or None if insufficient data.
    """
    if len(closes) < 22:
        return None
    ma10 = closes.rolling(10).mean()
    ma20 = closes.rolling(20).mean()
    p    = closes.iloc[-2]
    m10  = ma10.iloc[-2]
    m20  = ma20.iloc[-2]
    if any(pd.isna([p, m10, m20])) or m10 <= 0 or m20 <= 0:
        return None
    pct = (p / m10 - 1) * 100
    if len(ma10) < (2 + slope_lb):
        return None
    m10_prev = ma10.iloc[-2 - slope_lb]
    if pd.isna(m10_prev):
        return None
    m10_slope = m10 - m10_prev
    m20_slope = 0.0
    if len(ma20) >= (2 + slope_lb * 2):
        m20_prev = ma20.iloc[-2 - slope_lb * 2]
        if not pd.isna(m20_prev):
            m20_slope = m20 - m20_prev
    ma50_ok = True
    if require_ma50 and len(closes) >= 52:
        m50 = closes.rolling(50).mean().iloc[-2]
        ma50_ok = not pd.isna(m50) and p > m50
    passes = (
        m10 > m20 and
        BAND_LOW <= pct <= BAND_HIGH and
        m10_slope > 0 and
        m20_slope >= 0 and
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
    # Step 1: Weekly gate — skip entirely if not aligned
    try:
        wk = yf.Ticker(ticker).history(period='1y', interval='1wk', prepost=False)
        if len(wk) < 22 or not check_weekly_gate(wk['Close']):
            return ticker, {}
    except Exception:
        return ticker, {}

    results = {}

    # Step 2: Daily — must pass for any signal to be reported
    try:
        d1 = yf.Ticker(ticker).history(period='6mo', interval='1d', prepost=False)
        if len(d1) >= 30:
            rd = check_tf(d1['Close'], SLOPE_LOOKBACK_D, require_ma50=True)
            if rd and rd['passes']:
                results['D'] = rd
    except Exception:
        pass

    if 'D' not in results:
        return ticker, {}  # Daily not in setup — 4H/1H irrelevant

    # Step 3: 4H — only since Daily passed; reuse 1H fetch for Step 4
    try:
        h1_data = yf.Ticker(ticker).history(period='60d', interval='1h', prepost=False)
        if len(h1_data) >= 30:
            h4 = make_4h(h1_data['Close'])
            if len(h4) >= 22:
                r4 = check_tf(h4, SLOPE_LOOKBACK_4H)
                if r4 and r4['passes']:
                    results['4H'] = r4

            # Step 4: 1H — only if 4H passed
            if '4H' in results:
                r1 = check_tf(h1_data['Close'], SLOPE_LOOKBACK_1H)
                if r1 and r1['passes']:
                    results['1H'] = r1
    except Exception:
        pass

    return ticker, results


# ── Output ────────────────────────────────────────────────────────────────────

def print_results(all_results, total, label):
    hits = {t: r for t, r in all_results if r}
    sorted_hits = sorted(hits.items(), key=lambda x: -len(x[1]))

    print(f"{'Ticker':<8} {'Signal':^9} {'TF':<4} {'Price':>8} {'MA10':>8} {'MA20':>8} {'%MA10':>7}  slope")
    print("─" * 74)

    for ticker, tfs in sorted_hits:
        depth = 'D+4H+1H' if len(tfs) == 3 else ('D+4H' if '4H' in tfs else 'D')
        first = True
        for tf in ['D', '4H', '1H']:
            if tf not in tfs:
                continue
            v = tfs[tf]
            arrow = '▽' if v['pct'] < 0 else '▲'
            prefix = f"{ticker:<8} {depth:^9}" if first else f"{'':8} {'':9}"
            print(f"{prefix}  {tf:<4} {v['price']:>8.2f} {v['ma10']:>8.2f} {v['ma20']:>8.2f} {v['pct']:>+6.2f}%{arrow}  ↑{v['ma10_slope']:.3f}")
            first = False
        print()

    full    = [x for x in sorted_hits if len(x[1]) == 3]
    partial = [x for x in sorted_hits if '4H' in x[1] and '1H' not in x[1]]
    d_only  = [x for x in sorted_hits if list(x[1].keys()) == ['D']]

    print("─" * 74)
    print(f"Full waterfall D+4H+1H : {len(full)}")
    print(f"D+4H                   : {len(partial)}")
    print(f"D only (W+D aligned)   : {len(d_only)}")
    print(f"Total                  : {len(hits)} / {total}  [{label}]")


# ── Liquid Names Status Panel ─────────────────────────────────────────────────

LIQUID_NAMES = ['NVDA', 'META', 'MSFT', 'AAPL', 'AMZN', 'GOOGL', 'AVGO', 'MU', 'NFLX']


def liquid_status(ticker):
    try:
        t  = yf.Ticker(ticker)
        wk = t.history(period='1y', interval='1wk', prepost=False)['Close'].dropna()
        dy = t.history(period='3mo', interval='1d', prepost=False)['Close'].dropna()
        if len(wk) < 22 or len(dy) < 52:
            return None
        price    = float(dy.iloc[-1])

        # Sanity check: flag if price is outside the 52-week range (genuinely broken data)
        info  = t.info
        lo52  = info.get('fiftyTwoWeekLow')
        hi52  = info.get('fiftyTwoWeekHigh')
        live  = info.get('currentPrice') or info.get('regularMarketPrice')
        ref   = live or price
        if lo52 and hi52 and (ref < lo52 * 0.5 or ref > hi52 * 1.5):
            return (ticker, ref, None, None, None, 'DATA?', None)

        m10w     = float(wk.rolling(10).mean().iloc[-2])
        m20w     = float(wk.rolling(20).mean().iloc[-2])
        w_slope  = m10w - float(wk.rolling(10).mean().iloc[-2 - SLOPE_LOOKBACK_W])
        w_gate   = m10w > m20w and w_slope > 0
        m10d     = float(dy.rolling(10).mean().iloc[-2])
        m50d     = float(dy.rolling(50).mean().iloc[-2])
        pct10d   = (price / m10d - 1) * 100
        pct50d   = (price / m50d - 1) * 100
        band_str = 'IN' if BAND_LOW <= pct10d <= BAND_HIGH else ('+EXT' if pct10d > BAND_HIGH else '-EXT')
        return (ticker, price, w_gate, pct10d, pct50d, band_str, w_slope)
    except Exception:
        return None


def liquid_panel_md() -> str:
    with ThreadPoolExecutor(max_workers=8) as ex:
        rows = list(ex.map(liquid_status, LIQUID_NAMES))
    lines = [
        '\n### Liquid Names — Status Panel\n',
        '| Ticker | Price | Wkly Gate | vs MA10d | vs MA50d | Band | W.Slope |',
        '|:------:|------:|:---------:|---------:|---------:|:----:|--------:|',
    ]
    for row in rows:
        if row is None:
            continue
        sym, price, wg, p10, p50, band, slope = row
        if band == 'DATA?':
            lines.append(f"| **{sym}** | ${price:.2f} | — | — | — | ⚠ DATA? | — |")
        else:
            wg_s = '✓' if wg else '✗'
            lines.append(f"| **{sym}** | ${price:.2f} | {wg_s} | {p10:+.1f}% | {p50:+.1f}% | {band} | {slope:+.2f} |")
    return '\n'.join(lines) + '\n'


def print_liquid_panel():
    with ThreadPoolExecutor(max_workers=8) as ex:
        rows = list(ex.map(liquid_status, LIQUID_NAMES))

    print(f"\n{'─' * 74}")
    print(f"  LIQUID NAMES — STATUS PANEL")
    print(f"{'─' * 74}")
    print(f"  {'Ticker':<7} {'Price':>8}  {'Wkly':>5}  {'vs MA10d':>9}  {'vs MA50d':>9}  {'Band':>5}  {'W.Slope':>8}")
    print(f"  {'─'*7} {'─'*8}  {'─'*5}  {'─'*9}  {'─'*9}  {'─'*5}  {'─'*8}")
    for row in rows:
        if row is None:
            continue
        sym, price, wg, p10, p50, band, slope = row
        if band == 'DATA?':
            print(f"  {sym:<7} ${price:>7.2f}  {'—':>5}  {'—':>9}  {'—':>9}  ⚠ DATA?")
        else:
            wg_s = '✓' if wg else '✗'
            print(f"  {sym:<7} ${price:>7.2f}  {wg_s:>5}  {p10:>+8.1f}%  {p50:>+8.1f}%  {band:>5}  {slope:>+8.2f}")


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='MA Proximity Scanner')
    parser.add_argument('--watchlist', action='store_true', help='Scan WATCHLIST instead of UNIVERSE')
    args = parser.parse_args()

    tickers = WATCHLIST if args.watchlist else UNIVERSE
    label   = 'WATCHLIST' if args.watchlist else 'UNIVERSE'

    today = date.today().strftime('%Y-%m-%d')
    print(f"\nMA Scanner — Timeframe Hierarchy  [{today}]")
    print(f"Weekly gate → Daily in band → 4H (if D passes) → 1H (if 4H passes)")
    print(f"Band: {BAND_LOW}% to {BAND_HIGH:+}% of MA10  |  Daily requires price > MA50")
    print(f"Scanning {len(tickers)} {label} tickers...\n")

    with ThreadPoolExecutor(max_workers=20) as ex:
        all_results = list(ex.map(scan_ticker, tickers))

    print_results(all_results, len(tickers), label)
    print_liquid_panel()
    print(f"\nDISCLAIMER: Research tool only. Not financial advice.")
