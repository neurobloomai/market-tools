#!/usr/bin/env python3
"""
iv_rank.py — IV rank viewer

Reads iv_data.json (built daily by iv_snapshot.py) and displays:
  - IV Rank      : where today's IV sits vs stored history (0=cheapest, 100=most expensive)
  - IV Percentile: % of days IV was below today
  - IV/HV ratio  : options pricing vs realized moves (>1.0 = sell premium signal)
  - Trend        : IV direction over last 5 and 20 snapshots
  - Signal       : actionable read once enough history exists

Run anytime: python iv_rank.py
No network calls — reads local iv_data.json only.
"""

import json
import sys
from datetime import datetime
from pathlib import Path

DATA_FILE = Path(__file__).parent / 'iv_data.json'

TIERS = {
    'SPY': 1, 'QQQ': 1,
    'NVDA': 2, 'AAPL': 2, 'MSFT': 2, 'META': 2,
    'AMZN': 2, 'GOOGL': 2, 'TSLA': 2,
    'MU': 3, 'AMD': 3, 'JPM': 3, 'GS': 3, 'NFLX': 3,
}

SELL_THRESHOLD = 70   # IV rank above this = elevated
BUY_THRESHOLD  = 25   # IV rank below this = cheap options


def load():
    if not DATA_FILE.exists():
        print(f'ERROR: {DATA_FILE} not found. Run iv_snapshot.py first.')
        sys.exit(1)
    with open(DATA_FILE) as f:
        return json.load(f)


def compute(ticker, history):
    """Compute IV rank, percentile, trend from stored history."""
    dates  = sorted(history.keys())
    values = [(d, history[d]) for d in dates if history[d].get('iv') is not None]
    if not values:
        return None

    dates_v = [v[0] for v in values]
    ivs     = [v[1]['iv'] for v in values]
    hvs     = [v[1].get('hv') for v in values]

    current_iv  = ivs[-1]
    current_hv  = hvs[-1]
    current_date = dates_v[-1]
    days         = len(ivs)

    # IV rank + percentile (last 252 or all available)
    window = ivs[-252:]
    lo, hi = min(window), max(window)
    rank   = (current_iv - lo) / (hi - lo) * 100 if hi != lo else 50.0
    pct    = sum(1 for v in window if v < current_iv) / len(window) * 100

    # IV/HV ratio
    ratio = current_iv / current_hv if current_hv else None

    # Trend: direction over last 5 and 20 snapshots
    def trend_arrow(n):
        if len(ivs) < n + 1:
            return '—'
        delta = current_iv - ivs[-(n+1)]
        if delta >  1.0: return '↑'
        if delta < -1.0: return '↓'
        return '→'

    t5  = trend_arrow(5)
    t20 = trend_arrow(20)

    # Signal
    if days < 5:
        sig = f'building... ({days}/30 days)'
    elif rank >= SELL_THRESHOLD and ratio and ratio >= 0.90:
        sig = 'SELL PREMIUM  ◀◀'
    elif rank >= SELL_THRESHOLD:
        sig = 'CAUTION  ◀  (moves outpacing options)'
    elif rank >= 50:
        sig = 'ELEVATED      ◀'
    elif rank < BUY_THRESHOLD:
        sig = 'LOW — consider buying options'
    else:
        sig = 'NORMAL'

    return {
        'ticker':    ticker,
        'tier':      TIERS.get(ticker, '?'),
        'date':      current_date,
        'days':      days,
        'iv':        current_iv,
        'hv':        current_hv,
        'ratio':     ratio,
        'rank':      round(rank, 1),
        'pct':       round(pct, 1),
        't5':        t5,
        't20':       t20,
        'signal':    sig,
        'iv_lo':     round(lo, 1),
        'iv_hi':     round(hi, 1),
    }


def main():
    data    = load()
    results = []

    for ticker in TIERS:
        if ticker not in data:
            continue
        r = compute(ticker, data[ticker])
        if r:
            results.append(r)

    if not results:
        print('No data yet. Run iv_snapshot.py first.')
        return

    # Sort by IV rank descending (highest = most interesting for selling)
    results.sort(key=lambda x: x['rank'], reverse=True)

    latest_date = max(r['date'] for r in results)
    depth       = max(r['days'] for r in results)

    print()
    print(f'  IV RANK — SPREAD UNIVERSE')
    print(f'  Last snapshot: {latest_date}  |  History: {depth} day(s)')
    if depth < 30:
        print(f'  ⚠  Rank signal builds at 30 days ({30-depth} to go) — IV/HV ratio is reliable now')
    elif depth < 252:
        print(f'  ◎  Rank active ({depth}/252 days) — percentile sharpens as history fills')
    else:
        print(f'  ✓  Full 252-day history — IV Rank and Percentile are reliable')
    print()
    print(f'  {"Ticker":<7} {"T":>2}  {"IV":>7} {"HV":>7} {"IV/HV":>7}  '
          f'{"Rank":>7} {"Pct":>6}  {"5d":>3} {"20d":>4}  '
          f'{"Range (lo–hi)":>16}  Signal')
    print(f'  {"─"*105}')

    for r in results:
        ratio_str = f'{r["ratio"]:.2f}x' if r['ratio'] else '   —  '
        hv_str    = f'{r["hv"]:.1f}%'    if r['hv']    else '   —  '
        range_str = f'{r["iv_lo"]:.1f}–{r["iv_hi"]:.1f}%'

        # Highlight strong signals
        sig = r['signal']
        marker = '●' if 'SELL' in sig else ('○' if 'ELEVATED' in sig else ' ')

        print(f'  {r["ticker"]:<7} {r["tier"]:>2}  '
              f'{r["iv"]:>6.1f}%  {hv_str:>7}  {ratio_str:>7}  '
              f'{r["rank"]:>6.1f}%  {r["pct"]:>5.1f}th  '
              f'{r["t5"]:>3}  {r["t20"]:>4}  '
              f'{range_str:>16}  {marker} {sig}')

    print()
    print(f'  IV Rank: 0=52w cheapest  100=52w most expensive  |  ≥70 = sell zone  |  <25 = buy options zone')
    print(f'  IV/HV:   >1.0 = options expensive vs realized moves (variance risk premium = sell signal)')
    print(f'  Trend:   ↑↓→ = IV rising/falling/flat over last 5d and 20d snapshots')
    print()


if __name__ == '__main__':
    main()
