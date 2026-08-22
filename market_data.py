"""
market_data.py — unified price history adapter.

Default backend: yfinance (no auth required).
Schwab backend:  set SCHWAB_DATA=1 in shell for split-adjusted data.
                 Requires valid ~/.schwab_token.json (7-day refresh window).

Cache: yfinance results are cached to ~/.cache/market-tools/ (20min daily,
       4h weekly) to avoid Yahoo rate limits on back-to-back bulk scans.
       Schwab path bypasses cache — it's used for split-correction accuracy.

Usage:
    from market_data import fetch_daily, fetch_weekly
    hist   = fetch_daily(ticker)    # DataFrame with Open/High/Low/Close/Volume
    hist_w = fetch_weekly(ticker)   # same, weekly bars
"""

import os
import pickle
import time
import pandas as pd
from pathlib import Path

_CACHE_DIR   = Path.home() / '.cache' / 'market-tools'
_TTL_DAILY   = 20 * 60        # 20 minutes
_TTL_WEEKLY  = 4  * 60 * 60   # 4 hours


def _use_schwab(force_yf=False):
    return not force_yf and os.getenv('SCHWAB_DATA', '').strip() == '1'


def _cache_path(ticker, bar, key):
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return _CACHE_DIR / f'{ticker}_{bar}_{key}.pkl'


def _read_cache(path, ttl):
    if path.exists() and (time.time() - path.stat().st_mtime) < ttl:
        try:
            with open(path, 'rb') as f:
                return pickle.load(f)
        except Exception:
            pass
    return None


def _write_cache(path, df):
    try:
        with open(path, 'wb') as f:
            pickle.dump(df, f)
    except Exception:
        pass


def _candles_to_df(candles):
    df = pd.DataFrame(candles)
    df['datetime'] = pd.to_datetime(df['datetime'], unit='ms', utc=True)
    df = df.set_index('datetime')
    df = df.rename(columns={
        'open': 'Open', 'high': 'High',
        'low':  'Low',  'close': 'Close', 'volume': 'Volume',
    })
    return df[['Open', 'High', 'Low', 'Close', 'Volume']]


def fetch_daily(ticker, months=3, force_yf=False):
    """
    Return daily OHLCV DataFrame.
    Schwab (SCHWAB_DATA=1, force_yf=False): split-adjusted, no cache.
    yfinance: cached for 20 minutes to absorb back-to-back bulk scans.
    """
    if _use_schwab(force_yf):
        from schwab_client import get_price_history
        period = '3m' if months <= 3 else ('6m' if months <= 6 else '1y')
        candles = get_price_history(ticker, period=period, bar='daily')
        return _candles_to_df(candles)

    path   = _cache_path(ticker, 'daily', f'{months}mo')
    cached = _read_cache(path, _TTL_DAILY)
    if cached is not None:
        return cached

    import yfinance as yf
    df = yf.Ticker(ticker).history(period=f'{months}mo', interval='1d')
    if df is not None and not df.empty:
        _write_cache(path, df)
    return df


def fetch_weekly(ticker, years=2, force_yf=False):
    """
    Return weekly OHLCV DataFrame.
    Schwab (SCHWAB_DATA=1, force_yf=False): split-adjusted, no cache.
    yfinance: cached for 4 hours.
    """
    if _use_schwab(force_yf):
        from schwab_client import get_price_history
        period = '2y' if years >= 2 else '1y'
        candles = get_price_history(ticker, period=period, bar='weekly')
        return _candles_to_df(candles)

    path   = _cache_path(ticker, 'weekly', f'{years}y')
    cached = _read_cache(path, _TTL_WEEKLY)
    if cached is not None:
        return cached

    import yfinance as yf
    df = yf.Ticker(ticker).history(period=f'{years}y', interval='1wk')
    if df is not None and not df.empty:
        _write_cache(path, df)
    return df


def active_source():
    return 'schwab' if _use_schwab() else 'yfinance'
