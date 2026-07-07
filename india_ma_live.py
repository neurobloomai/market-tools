"""
india_ma_live.py — Live MA Scanner for India Markets (currentPrice + iloc[-1])
===============================================================================
Companion to ma_live.py for NSE-listed names. Uses live price from yfinance
info and iloc[-1] (latest bar, possibly incomplete intraday) instead of the
confirmed-close iloc[-2] used by the weekly scanner.

Use this for a real-time read during NSE market hours (9:15am–3:30pm IST).
Run: python india_ma_live.py

DISCLAIMER
----------
Research and framework-building tool only.
Output is NOT financial advice and NOT a recommendation to buy or sell
any security. All signals require independent verification.
Use at your own risk.
"""

import yfinance as yf, warnings
from concurrent.futures import ThreadPoolExecutor
from datetime import date
warnings.filterwarnings('ignore')

from india_screener import UNIVERSE, WATCHLIST

# Most liquid Nifty 50 names — high volume, tight spreads, index heavyweights
LIQUID_INDIA = [
    'RELIANCE.NS',
    'HDFCBANK.NS',
    'ICICIBANK.NS',
    'INFY.NS',
    'TCS.NS',
    'KOTAKBANK.NS',
    'SBIN.NS',
    'BAJFINANCE.NS',
    'HINDUNILVR.NS',
    'WIPRO.NS',
]

BAND_LOW  = -3.0
BAND_HIGH =  3.0


def live_scan(ticker):
    try:
        t     = yf.Ticker(ticker)
        info  = t.info
        price = info.get('currentPrice') or info.get('regularMarketPrice')
        if not price:
            return None

        wk = t.history(period='1y', interval='1wk', prepost=False)['Close'].dropna()
        dy = t.history(period='6mo', interval='1d', prepost=False)['Close'].dropna()
        if len(wk) < 22 or len(dy) < 52:
            return None

        m10w = float(wk.rolling(10).mean().iloc[-1])
        m20w = float(wk.rolling(20).mean().iloc[-1])
        m10d = float(dy.rolling(10).mean().iloc[-1])
        m20d = float(dy.rolling(20).mean().iloc[-1])
        m50d = float(dy.rolling(50).mean().iloc[-1])
        m10m = float(wk.rolling(43).mean().iloc[-1])
        m20m = float(wk.rolling(87).mean().iloc[-1])

        w_slope = m10w - float(wk.rolling(10).mean().iloc[-4])
        w_gate  = m10w > m20w and w_slope > 0
        score   = sum([price > m10w, price > m20w, price > m10m, price > m20m])

        pct10d = (price / m10d - 1) * 100
        pct10w = (price / m10w - 1) * 100
        pct20d = (price / m20d - 1) * 100
        band   = 'IN' if BAND_LOW <= pct10d <= BAND_HIGH else ('+EXT' if pct10d > BAND_HIGH else '-EXT')

        d_pass = (w_gate and m10d > m20d and BAND_LOW <= pct10d <= BAND_HIGH
                  and w_slope > 0 and price > m50d)

        sym = ticker.replace('.NS', '')
        return dict(ticker=sym, price=price, score=score, w_gate=w_gate,
                    pct10d=pct10d, pct10w=pct10w, pct20d=pct20d,
                    m10w=m10w, m20w=m20w, band=band, w_slope=w_slope, d_pass=d_pass)
    except Exception:
        return None


def print_liquid(rows):
    print(f"\n{'─'*74}")
    print(f"  LIQUID NAMES (INDIA) — LIVE")
    print(f"{'─'*74}")
    print(f"  {'Ticker':<12} {'Price':>9}  {'Wkly':>5}  {'vs MA20d':>9}  {'vs MA10w':>9}  {'MA10w':>9}  {'Band':>5}  {'W.Slope':>8}")
    print(f"  {'─'*12} {'─'*9}  {'─'*5}  {'─'*9}  {'─'*9}  {'─'*9}  {'─'*5}  {'─'*8}")
    for r in rows:
        if not r:
            continue
        wg = '✓' if r['w_gate'] else '✗'
        print(f"  {r['ticker']:<12} ₹{r['price']:>8.2f}  {wg:>5}  {r['pct20d']:>+8.1f}%  {r['pct10w']:>+8.1f}%  ₹{r['m10w']:>8.2f}  {r['band']:>5}  {r['w_slope']:>+8.2f}")


def print_setups(hits, label):
    print(f"\n{'─'*74}")
    print(f"  {label} — LIVE SETUPS (D-aligned)")
    print(f"{'─'*74}")
    if not hits:
        print("  No setups.")
        return
    print(f"  {'Ticker':<12} {'Price':>9}  {'MA':>4}  {'vs MA10d':>9}  {'vs MA10w':>9}  {'Band':>5}")
    for r in sorted(hits, key=lambda x: -x['score']):
        print(f"  {r['ticker']:<12} ₹{r['price']:>8.2f}  {r['score']}/4  {r['pct10d']:>+8.1f}%  {r['pct10w']:>+8.1f}%  {r['band']}")


if __name__ == '__main__':
    print(f"\nLIVE MA Scanner — India — {date.today()}  (currentPrice + iloc[-1] MAs)")
    print("="*74)

    with ThreadPoolExecutor(max_workers=10) as ex:
        liquid_rows = list(ex.map(live_scan, LIQUID_INDIA))
    print_liquid(liquid_rows)

    print(f"\n  Scanning {len(WATCHLIST)} WATCHLIST tickers ...", flush=True)
    with ThreadPoolExecutor(max_workers=20) as ex:
        wrows = list(ex.map(live_scan, WATCHLIST))
    print_setups([r for r in wrows if r and r['d_pass']], 'WATCHLIST')

    print(f"\n  Scanning {len(UNIVERSE)} UNIVERSE tickers ...", flush=True)
    with ThreadPoolExecutor(max_workers=20) as ex:
        urows = list(ex.map(live_scan, UNIVERSE))
    print_setups([r for r in urows if r and r['d_pass']], 'UNIVERSE')

    w_hits = sum(1 for r in wrows if r and r['d_pass'])
    u_hits = sum(1 for r in urows if r and r['d_pass'])
    print(f"\n  Watchlist: {w_hits}/{len(WATCHLIST)}  |  Universe: {u_hits}/{len(UNIVERSE)}")
    print(f"  Note: live price + iloc[-1] — intraday bar may be incomplete")
    print(f"  NSE hours: 9:15am–3:30pm IST  |  Data via yfinance (.NS suffix)")
    print(f"\n  DISCLAIMER: Research tool only. Not financial advice.")
