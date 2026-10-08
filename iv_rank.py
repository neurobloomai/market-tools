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

# TIERS used to be duplicated here AND in iv_snapshot.py -- caught live
# 2026-10-08: PLTR was added to iv_snapshot.py's TIERS/SPREAD_UNIVERSE on
# 2026-10-07 but not here, so internal_iv_structure_scanner.py's bare/full
# scan (which reads THIS module's TIERS for its default universe) silently
# excluded PLTR even though its IV data was being collected correctly --
# no error, just absent. Single source of truth now: import from
# iv_snapshot.py, the file that actually gets updated when a ticker is
# added, so this can't drift out of sync again.
from iv_snapshot import TIERS

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

    # IV rank + percentile (last 252 or all available) -- suppressed to None
    # below 5 days of history rather than returning the hi==lo fallback
    # (50.0) as if it were a real rank. Caught live 2026-10-08: PLTR had
    # only 2 days of history, got the 50.0 fallback, and
    # internal_iv_structure_scanner.py (which doesn't check `days` before
    # using the rank) confidently printed "BULL CALL DEBIT SPREAD, IV rank
    # 50.0%" off essentially no data. iv_snapshot.py's own compute_rank()
    # already had this discipline (returns None below 5 days) -- this
    # brings compute() in line with it so EVERY consumer gets a clear
    # "not enough data" signal instead of a fake number, not just the ones
    # that happen to check `days` themselves.
    window = ivs[-252:]
    lo, hi = min(window), max(window)
    if days < 5:
        rank, pct = None, None
    else:
        rank = (current_iv - lo) / (hi - lo) * 100 if hi != lo else 50.0
        pct  = sum(1 for v in window if v < current_iv) / len(window) * 100
        rank = round(rank, 1)
        pct  = round(pct, 1)

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
        'rank':      rank,
        'pct':       pct,
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
    # None (still-building history) sorts to the bottom regardless of direction
    results.sort(key=lambda x: x['rank'] if x['rank'] is not None else -1, reverse=True)

    # SPY/QQQ are a regime read (market-wide IV), not a single-name spread
    # candidate — sectioned off from the individual tickers below rather
    # than interleaved into the same rank-sorted table, same split
    # internal_cmf_trend_scanner.py already applies to its own index rows.
    stock_results = [r for r in results if r['tier'] != 1]
    index_results = [r for r in results if r['tier'] == 1]

    latest_date = max(r['date'] for r in results)
    depth       = max(r['days'] for r in results)

    # Column widths — fixed throughout
    C = {
        'ticker': 6, 'tier': 1, 'iv': 7, 'hv': 7,
        'ratio': 7, 'rank': 7, 'pct': 7,
        't5': 3, 't20': 3, 'range': 13,
    }
    DIVIDER = '  ' + '─' * 92

    print()
    print(f'  IV RANK — SPREAD UNIVERSE')
    print(f'  Last snapshot : {latest_date}  |  History: {depth} day(s)')
    if depth < 30:
        print(f'  Status        : building ({30-depth} days to rank signal) — IV/HV ratio reliable now')
    elif depth == 30:
        print(f'  Status        : ★ IV RANK NOW ACTIVE (30 days reached)')
        print(f'  Next step     : add extension scan × IV/HV cross-signal view in extension_scan.py')
    elif depth < 252:
        print(f'  Status        : rank active ({depth}/252 days) — percentile sharpens as history fills')
    else:
        print(f'  Status        : full 252-day history — IV Rank and Percentile reliable')
    print()

    hdr = (f'  {"Ticker":<{C["ticker"]}}  {"T":{C["tier"]}}'
           f'  {"ATM IV":>{C["iv"]}}'
           f'  {"HV30":>{C["hv"]}}'
           f'  {"IV/HV":>{C["ratio"]}}'
           f'  {"Rank":>{C["rank"]}}'
           f'  {"Pct":>{C["pct"]}}'
           f'  {"5d":{C["t5"]}}'
           f'  {"20d":{C["t20"]}}'
           f'  {"Range (lo–hi)":>{C["range"]}}'
           f'  Signal')

    def print_row(r):
        building = r['days'] < 5

        iv_str    = f'{r["iv"]:>6.1f}%'
        hv_str    = f'{r["hv"]:>6.1f}%'   if r['hv']    else f'{"—":>6}'
        ratio_str = f'{r["ratio"]:>6.2f}x' if r['ratio'] else f'{"—":>6}'
        rank_str  = f'{"—":>6}'            if building   else f'{r["rank"]:>6.1f}%'
        pct_str   = f'{"—":>6}'            if building   else f'{r["pct"]:>5.0f}th '
        t5_str    = f'{r["t5"]:^{C["t5"]}}'
        t20_str   = f'{r["t20"]:^{C["t20"]}}'
        range_str = f'{r["iv_lo"]:.1f}–{r["iv_hi"]:.1f}%'

        sig = r['signal']
        if   'SELL'     in sig: marker = '●'
        elif 'ELEVATED' in sig: marker = '○'
        elif 'LOW'      in sig: marker = '▽'
        else:                   marker = ' '

        print(f'  {r["ticker"]:<{C["ticker"]}}'
              f'  {r["tier"]:>{C["tier"]}}'
              f'  {iv_str:>{C["iv"]}}'
              f'  {hv_str:>{C["hv"]}}'
              f'  {ratio_str:>{C["ratio"]}}'
              f'  {rank_str:>{C["rank"]}}'
              f'  {pct_str:>{C["pct"]}}'
              f'  {t5_str}'
              f'  {t20_str}'
              f'  {range_str:>{C["range"]}}'
              f'  {marker} {sig}')

    print(hdr)
    print(DIVIDER)
    for r in stock_results:
        print_row(r)
    print(DIVIDER)

    if index_results:
        print()
        print(f'  INDEX PROXIES  (SPY/QQQ — market-wide IV regime read, not a single-name spread candidate)')
        print(hdr)
        print(DIVIDER)
        for r in index_results:
            print_row(r)
        print(DIVIDER)
    print(f'  Rank  : 0 = 52w IV low · 100 = 52w IV high · ≥70 sell zone · <25 buy options')
    print(f'  IV/HV : >1.0 options expensive vs realized moves (variance risk premium = sell signal)')
    print(f'  Trend : ↑ rising · ↓ falling · → flat  (over last 5 and 20 daily snapshots)')
    print()


if __name__ == '__main__':
    main()
