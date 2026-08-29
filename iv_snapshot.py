#!/usr/bin/env python3
"""
iv_snapshot.py — Daily ATM implied volatility collector

Appends today's ATM IV (~30-day options, call+put average) and HV30
(30-day realized vol) for each SPREAD_UNIVERSE name to iv_data.json.

Over time this builds a proper historical IV database so IV rank and
IV percentile can be computed from actual implied vol history — not
the HV proxy we had to use before we had this data.

IV Rank    = (Current IV - 52w Low IV)  / (52w High IV - 52w Low IV) * 100
IV Pct     = % of past-year days where IV was below today's IV
IV/HV      = options pricing vs what the stock is actually doing
             >1.0 = options expensive (variance risk premium = sell signal)
             <1.0 = realized moves outpacing options (options cheap)

Signal logic (once ≥30 days of IV history):
  IV Rank ≥ 70  AND  IV/HV ≥ 0.90  →  SELL PREMIUM  ◀◀  (both confirm)
  IV Rank ≥ 70  AND  IV/HV <  0.90  →  CAUTION       ◀   (rank high but moves outpacing IV)
  IV Rank ≥ 50                       →  ELEVATED
  IV Rank <  25                      →  LOW — buy options
  else                               →  NORMAL

Run: python iv_snapshot.py
Auto: daily_screener.yml runs this after market close (Tue–Sat 9:30pm UTC)
"""

import json
import os
import numpy as np
import warnings
from datetime import datetime, timedelta, date as _date
from pathlib import Path

import yfinance as yf
warnings.filterwarnings('ignore')


def _use_schwab():
    return os.getenv('SCHWAB_DATA', '').strip() == '1'

DATA_FILE = Path(__file__).parent / 'iv_data.json'

SPREAD_UNIVERSE = [
    'SPY', 'QQQ',
    'NVDA', 'AAPL', 'MSFT', 'META', 'AMZN', 'GOOGL', 'TSLA',
    'MU', 'AMD', 'JPM', 'GS', 'NFLX',
]

TIERS = {
    'SPY': 1, 'QQQ': 1,
    'NVDA': 2, 'AAPL': 2, 'MSFT': 2, 'META': 2,
    'AMZN': 2, 'GOOGL': 2, 'TSLA': 2,
    'MU': 3, 'AMD': 3, 'JPM': 3, 'GS': 3, 'NFLX': 3,
}


def get_atm_iv_schwab(ticker):
    """ATM IV via Schwab option chain — volatility field is already %, no conversion needed."""
    try:
        from schwab_client import get_option_chain
        data = get_option_chain(ticker, strikes=3)
        if 'error' in data or data.get('status') == 'FAILED':
            return None, None
        underlying = data.get('underlyingPrice')
        if not underlying:
            return None, None
        target  = _date.today() + timedelta(days=30)
        all_exp = sorted(set(
            list(data.get('callExpDateMap', {}).keys()) +
            list(data.get('putExpDateMap',  {}).keys())
        ))
        if not all_exp:
            return None, None
        exp = min(all_exp, key=lambda x: abs((_date.fromisoformat(x.split(':')[0]) - target).days))
        calls = data.get('callExpDateMap', {}).get(exp, {})
        puts  = data.get('putExpDateMap',  {}).get(exp, {})
        all_strikes = sorted(set(list(calls.keys()) + list(puts.keys())), key=float)
        if not all_strikes:
            return None, None
        atm   = min(all_strikes, key=lambda s: abs(float(s) - underlying))
        c_iv  = (calls.get(atm) or [{}])[0].get('volatility', 0)
        p_iv  = (puts.get(atm)  or [{}])[0].get('volatility', 0)
        if c_iv < 1.0 or p_iv < 1.0:   # Schwab volatility is already %; < 1% = bad data
            return None, None
        return round((c_iv + p_iv) / 2, 2), round(float(underlying), 2)
    except Exception:
        return None, None


def get_atm_iv(ticker):
    """ATM IV from nearest ~30-day expiry. Routes through Schwab when SCHWAB_DATA=1."""
    if _use_schwab():
        return get_atm_iv_schwab(ticker)
    # yfinance path
    try:
        stock = yf.Ticker(ticker)
        exps = stock.options
        if not exps:
            return None, None
        target = datetime.now() + timedelta(days=30)
        exp = min(exps, key=lambda x: abs((datetime.strptime(x, '%Y-%m-%d') - target).days))
        chain = stock.option_chain(exp)
        price = stock.info.get('currentPrice') or stock.info.get('regularMarketPrice')
        if not price:
            return None, None
        calls = chain.calls.copy()
        puts  = chain.puts.copy()
        calls['dist'] = abs(calls['strike'] - price)
        puts['dist']  = abs(puts['strike']  - price)
        c_iv = calls.loc[calls['dist'].idxmin(), 'impliedVolatility']
        p_iv = puts.loc[puts['dist'].idxmin(),  'impliedVolatility']
        # < 0.01 (1% annualized) catches stale after-hours yfinance returns that
        # are near-zero but not exactly 0 — those slip past the <= 0 check
        if c_iv < 0.01 or p_iv < 0.01:
            return None, None
        atm_iv = round((c_iv + p_iv) / 2 * 100, 2)
        return atm_iv, round(float(price), 2)
    except Exception:
        return None, None


def get_hv30(ticker):
    """30-day realized vol annualized (%). Returns float or None."""
    try:
        hist = yf.Ticker(ticker).history(period='3mo')['Close']
        ret  = hist.pct_change().dropna()
        hv   = ret.rolling(21).std().iloc[-1] * np.sqrt(252) * 100
        return round(float(hv), 2)
    except Exception:
        return None


def compute_rank(ticker, data, current_iv):
    """IV rank + percentile from stored IV history (up to 252 days)."""
    history = data.get(ticker, {})
    values  = [v['iv'] for v in history.values() if v.get('iv') is not None]
    if len(values) < 5:
        return None, None, len(values)
    window = values[-252:]
    lo, hi = min(window), max(window)
    rank = (current_iv - lo) / (hi - lo) * 100 if hi != lo else 50.0
    pct  = sum(1 for v in window if v < current_iv) / len(window) * 100
    return round(rank, 1), round(pct, 1), len(values)


def signal(rank, iv_hv_ratio, days):
    if days < 5:
        return f'building... ({days} days stored)'
    if rank is None:
        return '—'
    if rank >= 70 and iv_hv_ratio and iv_hv_ratio >= 0.90:
        return 'SELL PREMIUM  ◀◀'
    elif rank >= 70:
        return 'CAUTION       ◀  (IV < HV — moves outpacing options)'
    elif rank >= 50:
        return 'ELEVATED      ◀'
    elif rank < 25:
        return 'LOW — buy options'
    else:
        return 'NORMAL'


def load():
    if DATA_FILE.exists():
        with open(DATA_FILE) as f:
            return json.load(f)
    return {}


def save(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=2)


def main():
    today = datetime.now().strftime('%Y-%m-%d')
    data  = load()

    print(f'IV SNAPSHOT — {today}')
    print(f'{"─"*95}')
    print(f'{"Ticker":<7} {"Tier":>4}  {"ATM IV":>7} {"HV30":>7} {"IV/HV":>7}  '
          f'{"IV Rank":>8} {"IV Pct":>7}  Signal')
    print(f'{"─"*95}')

    for ticker in SPREAD_UNIVERSE:
        iv, price = get_atm_iv(ticker)
        hv        = get_hv30(ticker)

        # Store today's snapshot
        if ticker not in data:
            data[ticker] = {}
        data[ticker][today] = {'iv': iv, 'hv': hv, 'price': price}

        tier = TIERS.get(ticker, '?')

        if iv is None:
            print(f'{ticker:<7} {tier:>4}    — no options data today')
            continue

        rank, pct, days = compute_rank(ticker, data, iv)

        ratio     = iv / hv if hv else None
        ratio_str = f'{ratio:.2f}x' if ratio else '  —  '
        hv_str    = f'{hv:>6.1f}%' if hv else '   —  '
        rank_str  = f'{rank:>7.1f}%' if rank is not None else '     —  '
        pct_str   = f'{pct:>6.1f}th' if pct is not None else '    —  '

        sig = signal(rank, ratio, days)
        print(f'{ticker:<7} {tier:>4}   {iv:>6.1f}%  {hv_str}  {ratio_str:>7}  '
              f'{rank_str}  {pct_str}  {sig}')

    save(data)

    depth = max((len(v) for v in data.values()), default=0)
    print(f'\n{"─"*95}')
    print(f'Saved → {DATA_FILE.name}  |  History depth: {depth} day(s)')
    if depth < 30:
        print(f'IV Rank builds signal at 30+ days, becomes sharp at 252 days ({252-depth} to go).')
    elif depth < 252:
        print(f'IV Rank active ({depth}/252 days). Percentile sharpens as history fills.')
    else:
        print(f'Full 252-day IV history. IV Rank and Percentile are reliable.')


if __name__ == '__main__':
    main()
