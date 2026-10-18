"""
Relative-strength tracker: index pairs + GICS sector ETFs vs SPY.

Same discipline already used for price trend elsewhere in this framework
(screener.get_ma_detail / get_signal_detail): a ratio crossing its own MA
once is noise, not a signal. A lean only counts once it has held for
SUSTAIN_WEEKS consecutive weeks.
"""
import pandas as pd
import yfinance as yf

from screener import calc_rsi

INDEX_PAIRS = [
    ('SPY', 'RSP', 'cap-weight (SPY)', 'equal-weight (RSP)'),
    ('QQQ', 'QQQE', 'cap-weight (QQQ)', 'equal-weight (QQQE)'),
    ('VOO', 'VXUS', 'US (VOO)', 'International (VXUS)'),
]

SECTOR_ETFS = {
    'XLK': 'Technology', 'XLF': 'Financials', 'XLV': 'Health Care',
    'XLY': 'Cons. Discretionary', 'XLP': 'Cons. Staples', 'XLE': 'Energy',
    'XLI': 'Industrials', 'XLB': 'Materials', 'XLU': 'Utilities',
    'XLRE': 'Real Estate', 'XLC': 'Communication Svcs',
}

SUSTAIN_WEEKS = 4

_cache = {}


def _weekly_closes(ticker):
    if ticker not in _cache:
        h = yf.Ticker(ticker).history(period='2y', interval='1wk')
        s = h['Close'].dropna()
        if s.index.tz is not None:
            s.index = s.index.tz_localize(None)
        _cache[ticker] = s
    return _cache[ticker]


def ratio_trend(ticker_a, ticker_b, sustain_weeks=SUSTAIN_WEEKS):
    """MA-alignment/slope/RSI treatment applied to the A/B ratio series,
    same as screener.py applies to raw price. Returns None if insufficient
    history for either leg."""
    a = _weekly_closes(ticker_a)
    b = _weekly_closes(ticker_b)
    idx = a.index.intersection(b.index)
    ratio = (a.loc[idx] / b.loc[idx]).dropna()
    n = len(ratio)
    if n < 25:
        return None

    ma10 = ratio.rolling(10).mean()
    ma20 = ratio.rolling(20).mean()
    ma43 = ratio.rolling(43).mean() if n >= 43 else None

    p = ratio.iloc[-1]
    cur_ma10, cur_ma20 = ma10.iloc[-1], ma20.iloc[-1]
    cur_ma43 = ma43.iloc[-1] if ma43 is not None and not pd.isna(ma43.iloc[-1]) else None

    mas = [m for m in (cur_ma10, cur_ma20, cur_ma43) if m is not None and not pd.isna(m)]
    align = sum(1 for m in mas if p > m)

    slope = (cur_ma10 - ma10.iloc[-11]) / ma10.iloc[-11] * 100 if n >= 11 else None
    rsi = float(calc_rsi(ratio, 14).dropna().iloc[-1])

    # Sustain check: has the ratio been on the same side of its 20w MA
    # (the core lean indicator) for the last `sustain_weeks` weeks running?
    above20 = (ratio > ma20).dropna()
    recent = above20.iloc[-sustain_weeks:]
    sustained = recent.nunique() == 1

    return {
        'align': align, 'total': len(mas),
        'vs_10w': (p - cur_ma10) / cur_ma10 * 100,
        'slope': slope, 'rsi': rsi,
        'favored_a': bool(above20.iloc[-1]),
        'sustained': bool(sustained),
    }


def print_relative_strength():
    print("\n=== INDEX RELATIVE STRENGTH (ratio vs its own 20w MA) ===")
    for a, b, label_a, label_b in INDEX_PAIRS:
        d = ratio_trend(a, b)
        if d is None:
            print(f"{a}/{b}: insufficient data")
            continue
        lean = label_a if d['favored_a'] else label_b
        tag = "" if d['sustained'] else "  (recent flip, not yet sustained)"
        print(f"{a}/{b:<5s} align {d['align']}/{d['total']}  vs10w {d['vs_10w']:+6.2f}%  "
              f"slope {d['slope']:+6.2f}%  RSI {d['rsi']:5.1f}  -> {lean} favored{tag}")

    print("\n=== SECTOR RELATIVE STRENGTH vs SPY ===")
    rows = []
    for etf, name in SECTOR_ETFS.items():
        d = ratio_trend(etf, 'SPY')
        if d is not None:
            rows.append((etf, name, d))
    rows.sort(key=lambda r: r[2]['vs_10w'], reverse=True)
    for etf, name, d in rows:
        lean = "OUTPERFORMING" if d['favored_a'] else "underperforming"
        tag = "" if d['sustained'] else "  (recent flip)"
        print(f"{etf:<5s} {name:<22s} align {d['align']}/{d['total']}  vs10w {d['vs_10w']:+6.2f}%  "
              f"slope {d['slope']:+6.2f}%  RSI {d['rsi']:5.1f}  -> {lean}{tag}")


if __name__ == '__main__':
    print_relative_strength()
