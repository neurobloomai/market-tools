"""
market_data.py — unified price history adapter.

Default backend: yfinance (no auth required).
Schwab backend:  set SCHWAB_DATA=1 in shell for split-adjusted data.
                 Requires valid ~/.schwab_token.json (7-day refresh window).

Usage:
    from market_data import fetch_daily, fetch_weekly
    hist   = fetch_daily(ticker)    # DataFrame with Open/High/Low/Close/Volume
    hist_w = fetch_weekly(ticker)   # same, weekly bars
"""

import os
import pandas as pd

_USE_SCHWAB = os.getenv('SCHWAB_DATA', '').strip() == '1'


def _candles_to_df(candles):
    """Convert Schwab candle list → pandas DataFrame matching yfinance shape."""
    df = pd.DataFrame(candles)
    df['datetime'] = pd.to_datetime(df['datetime'], unit='ms', utc=True)
    df = df.set_index('datetime')
    df = df.rename(columns={
        'open': 'Open', 'high': 'High',
        'low':  'Low',  'close': 'Close', 'volume': 'Volume',
    })
    return df[['Open', 'High', 'Low', 'Close', 'Volume']]


def fetch_daily(ticker, months=3):
    """
    Return daily OHLCV DataFrame (~3 months).
    Schwab: properly split-adjusted. yfinance: may lag on recent splits.
    """
    if _USE_SCHWAB:
        from schwab_client import get_price_history
        period = '3m' if months <= 3 else ('6m' if months <= 6 else '1y')
        candles = get_price_history(ticker, period=period, bar='daily')
        return _candles_to_df(candles)
    else:
        import yfinance as yf
        period_str = f'{months}mo'
        return yf.Ticker(ticker).history(period=period_str, interval='1d')


def fetch_weekly(ticker, years=2):
    """
    Return weekly OHLCV DataFrame (~2 years).
    Schwab: properly split-adjusted. yfinance: may lag on recent splits.
    """
    if _USE_SCHWAB:
        from schwab_client import get_price_history
        period = '2y' if years >= 2 else '1y'
        candles = get_price_history(ticker, period=period, bar='weekly')
        return _candles_to_df(candles)
    else:
        import yfinance as yf
        period_str = f'{years}y'
        return yf.Ticker(ticker).history(period=period_str, interval='1wk')


def active_source():
    return 'schwab' if _USE_SCHWAB else 'yfinance'
