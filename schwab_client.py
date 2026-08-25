"""
Schwab API Client
=================
Setup (one-time):
  1. Register an app at https://developer.schwab.com — set callback URL to https://127.0.0.1
  2. Add your credentials to ~/.zshrc (or equivalent):
       export SCHWAB_APP_KEY=your_app_key_here
       export SCHWAB_APP_SECRET=your_app_secret_here
  3. Run:  python schwab_client.py --auth
     This opens a browser, completes OAuth, and saves ~/.schwab_token.json
  4. Re-auth needed every 7 days (refresh token window):
       python schwab_client.py --auth

Token file (~/.schwab_token.json) is stored outside the repo — never commit it.
"""

import os
import schwab
import json
import sys
from datetime import date
from pathlib import Path

try:
    from schwab_creds import APP_KEY as _CREDS_KEY, APP_SECRET as _CREDS_SECRET, CALLBACK_URL, TOKEN_PATH as _CREDS_TOKEN_PATH
    APP_KEY    = os.environ.get('SCHWAB_APP_KEY')    or _CREDS_KEY
    APP_SECRET = os.environ.get('SCHWAB_APP_SECRET') or _CREDS_SECRET
    TOKEN_PATH = Path(_CREDS_TOKEN_PATH)
except ImportError:
    APP_KEY    = os.environ.get('SCHWAB_APP_KEY',    'your_app_key_here')
    APP_SECRET = os.environ.get('SCHWAB_APP_SECRET', 'your_app_secret_here')
    CALLBACK_URL = 'https://127.0.0.1'
    TOKEN_PATH   = Path.home() / '.schwab_token.json'


def _sym(ticker):
    """yfinance uses BRK-B; Schwab uses BRK/B. Normalize before every API call."""
    return ticker.replace('-', '/')


def get_client():
    if TOKEN_PATH.exists():
        return schwab.auth.client_from_token_file(
            token_path = str(TOKEN_PATH),
            api_key    = APP_KEY,
            app_secret = APP_SECRET,
        )
    return schwab.auth.client_from_manual_flow(
        api_key      = APP_KEY,
        app_secret   = APP_SECRET,
        callback_url = CALLBACK_URL,
        token_path   = str(TOKEN_PATH),
    )


def get_quote(ticker):
    c = get_client()
    r = c.get_quote(_sym(ticker))
    return r.json()


def get_quotes(tickers):
    c = get_client()
    r = c.get_quotes([_sym(t) for t in tickers])
    return r.json()


def get_accounts():
    c = get_client()
    r = c.get_account_numbers()
    return r.json()


def get_positions():
    c = get_client()
    accounts = c.get_account_numbers().json()
    results = {}
    for acct in accounts:
        hash_val = acct['hashValue']
        r = c.get_account(hash_val, fields=[c.Account.Fields.POSITIONS])
        results[acct['accountNumber']] = r.json()
    return results


def get_price_history(ticker, period='3m', bar='daily'):
    """
    Fetch OHLCV history — split-adjusted by Schwab.
    period: '3m' | '6m' | '1y' | '2y'
    bar:    'daily' | 'weekly'
    Returns list of {'datetime': ms_epoch, 'open', 'high', 'low', 'close', 'volume'}
    """
    c = get_client()
    PH = c.PriceHistory

    period_map = {
        '3m': (PH.PeriodType.MONTH,  PH.Period.THREE_MONTHS),
        '6m': (PH.PeriodType.MONTH,  PH.Period.SIX_MONTHS),
        '1y': (PH.PeriodType.YEAR,   PH.Period.ONE_YEAR),
        '2y': (PH.PeriodType.YEAR,   PH.Period.TWO_YEARS),
    }
    freq_map = {
        'daily':  (PH.FrequencyType.DAILY,  PH.Frequency.DAILY),
        'weekly': (PH.FrequencyType.WEEKLY, PH.Frequency.WEEKLY),
    }

    period_type, period_val = period_map.get(period, period_map['3m'])
    freq_type,   freq_val   = freq_map.get(bar,    freq_map['daily'])

    r = c.get_price_history(
        symbol         = _sym(ticker),
        period_type    = period_type,
        period         = period_val,
        frequency_type = freq_type,
        frequency      = freq_val,
    )
    data    = r.json()
    candles = data.get('candles', [])
    if not candles:
        err = data.get('error') or data.get('message') or r.status_code
        print(f"  [Schwab] {ticker}: no candles — {err}", file=sys.stderr)
    return candles


def print_history_summary(ticker, period='3m', bar='daily'):
    candles = get_price_history(ticker, period=period, bar=bar)
    if not candles:
        print(f'  No data returned for {ticker}')
        return
    closes = [c['close'] for c in candles]
    import statistics
    latest  = closes[-1]
    ma10    = statistics.mean(closes[-10:])  if len(closes) >= 10 else None
    ma20    = statistics.mean(closes[-20:])  if len(closes) >= 20 else None
    ma50    = statistics.mean(closes[-50:])  if len(closes) >= 50 else None
    print(f'\n  {ticker}  {bar} bars  ({period})  —  {len(candles)} candles')
    print(f'  Latest close : ${latest:.2f}')
    if ma10:  print(f'  10-bar MA    : ${ma10:.2f}  ({(latest/ma10-1)*100:+.1f}%)')
    if ma20:  print(f'  20-bar MA    : ${ma20:.2f}  ({(latest/ma20-1)*100:+.1f}%)')
    if ma50:  print(f'  50-bar MA    : ${ma50:.2f}  ({(latest/ma50-1)*100:+.1f}%)')
    print(f'  First candle : {candles[0]["datetime"]}  →  ${candles[0]["close"]:.2f}')
    print(f'  Last  candle : {candles[-1]["datetime"]}  →  ${candles[-1]["close"]:.2f}')
    print()


def get_fundamentals(ticker):
    """
    Fetch fundamental data via Instruments endpoint (projection=FUNDAMENTAL).
    Returns normalized dict matching screener.py field names where possible.
    """
    c = get_client()
    r = c.get_instruments(symbols=[_sym(ticker)],
                          projection=c.Instrument.Projection.FUNDAMENTAL)
    instruments = r.json().get('instruments', [])
    if not instruments:
        return None
    raw = instruments[0].get('fundamental', {})
    if not raw:
        return None

    def _pct(v):
        return round(v / 100, 4) if isinstance(v, (int, float)) else None

    return {
        # price / market
        'ticker':              ticker,
        'marketCap':           raw.get('marketCap'),
        'high52':              raw.get('high52'),
        'low52':               raw.get('low52'),
        'beta':                raw.get('beta'),
        # margins (Schwab returns as %, screener expects 0-1 floats)
        'grossMargins':        _pct(raw.get('grossMarginTTM')),
        'grossMarginsMRQ':     _pct(raw.get('grossMarginMRQ')),
        'operatingMargins':    _pct(raw.get('operatingMarginTTM')),
        'operatingMarginsMRQ': _pct(raw.get('operatingMarginMRQ')),
        'profitMargins':       _pct(raw.get('netProfitMarginTTM')),
        'profitMarginsMRQ':    _pct(raw.get('netProfitMarginMRQ')),
        # returns
        'returnOnEquity':      _pct(raw.get('returnOnEquity')),
        'returnOnAssets':      _pct(raw.get('returnOnAssets')),
        'returnOnInvestment':  _pct(raw.get('returnOnInvestment')),
        # growth
        'revenueGrowthTTM':    _pct(raw.get('revChangeTTM')),
        'revenueGrowthYear':   _pct(raw.get('revChangeYear')),
        'epsGrowthTTM':        _pct(raw.get('epsChangePercentTTM')),
        # valuation
        'trailingPE':          raw.get('peRatio'),
        'pegRatio':            raw.get('pegRatio'),
        'pbRatio':             raw.get('pbRatio'),
        'pcfRatio':            raw.get('pcfRatio'),
        # leverage
        'totalDebtToEquity':   raw.get('totalDebtToEquity'),
        'totalDebtToCapital':  raw.get('totalDebtToCapital'),
        'ltDebtToEquity':      raw.get('ltDebtToEquity'),
        'currentRatio':        raw.get('currentRatio'),
        'quickRatio':          raw.get('quickRatio'),
        # dividends
        'dividendYield':       raw.get('dividendYield'),
        'dividendAmount':      raw.get('dividendAmount'),
        'dividendPayAmount':   raw.get('dividendPayAmount'),
        'dividendFreq':        raw.get('dividendFreq'),
        # eps / shares
        'epsTTM':              raw.get('epsTTM'),
        'sharesOutstanding':   raw.get('sharesOutstanding'),
        # raw Schwab dict for anything else
        '_raw':                raw,
    }


def print_fundamentals(ticker):
    f = get_fundamentals(ticker)
    if not f:
        print(f'\n  No fundamental data for {ticker}\n')
        return

    def _fmt_pct(v):
        return f'{v*100:+.1f}%' if isinstance(v, float) else '—'
    def _fmt_f(v, dec=2):
        return f'{v:.{dec}f}' if isinstance(v, (int, float)) else '—'

    cap = f['marketCap']
    cap_str = f'${cap/1e12:.2f}T' if cap and cap >= 1e12 else (f'${cap/1e9:.1f}B' if cap else '—')

    print(f'\n  ── {ticker} fundamentals (Schwab) ──────────────────────────────')
    print(f'  Market Cap     : {cap_str}   Beta: {_fmt_f(f["beta"])}')
    print(f'  52w range      : ${_fmt_f(f["low52"])} – ${_fmt_f(f["high52"])}')
    print()
    print(f'  Gross Margin   : {_fmt_pct(f["grossMargins"])}  (MRQ {_fmt_pct(f["grossMarginsMRQ"])})')
    print(f'  Oper Margin    : {_fmt_pct(f["operatingMargins"])}  (MRQ {_fmt_pct(f["operatingMarginsMRQ"])})')
    print(f'  Net Margin     : {_fmt_pct(f["profitMargins"])}  (MRQ {_fmt_pct(f["profitMarginsMRQ"])})')
    print()
    print(f'  ROE            : {_fmt_pct(f["returnOnEquity"])}')
    print(f'  ROA            : {_fmt_pct(f["returnOnAssets"])}')
    print(f'  ROIC           : {_fmt_pct(f["returnOnInvestment"])}')
    print()
    print(f'  Rev Growth TTM : {_fmt_pct(f["revenueGrowthTTM"])}   YoY: {_fmt_pct(f["revenueGrowthYear"])}')
    print(f'  EPS Growth TTM : {_fmt_pct(f["epsGrowthTTM"])}')
    print()
    print(f'  Trailing P/E   : {_fmt_f(f["trailingPE"])}x   PEG: {_fmt_f(f["pegRatio"])}   P/B: {_fmt_f(f["pbRatio"])}   P/CF: {_fmt_f(f["pcfRatio"])}')
    print()
    print(f'  Debt/Equity    : {_fmt_f(f["totalDebtToEquity"])}%   LT D/E: {_fmt_f(f["ltDebtToEquity"])}%   D/Capital: {_fmt_f(f["totalDebtToCapital"])}%')
    print(f'  Current Ratio  : {_fmt_f(f["currentRatio"])}   Quick: {_fmt_f(f["quickRatio"])}')
    print()
    if f['dividendYield']:
        print(f'  Div Yield      : {f["dividendYield"]:.2f}%   Annual: ${_fmt_f(f["dividendAmount"])}   Quarterly: ${_fmt_f(f["dividendPayAmount"])}')
    else:
        print(f'  Dividend       : —')
    print(f'  EPS TTM        : ${_fmt_f(f["epsTTM"])}')
    print()


def get_option_chain(ticker, expiry_date=None, strikes=None):
    """
    expiry_date: 'YYYY-MM-DD'
    strikes: number of strikes above/below ATM (default 5)
    """
    c = get_client()
    kwargs = {}
    if expiry_date:
        d = date.fromisoformat(expiry_date) if isinstance(expiry_date, str) else expiry_date
        kwargs['from_date'] = d
        kwargs['to_date']   = d
    if strikes:
        kwargs['strike_count'] = strikes
    r = c.get_option_chain(_sym(ticker), **kwargs)
    return r.json()


def print_chain(ticker, expiry_date=None, strikes=10):
    data = get_option_chain(ticker, expiry_date=expiry_date, strikes=strikes)

    if 'error' in data or data.get('status') == 'FAILED':
        print(f'\n  Error: {data}\n')
        return

    underlying = data.get('underlyingPrice', 0)
    expiries   = sorted(set(
        list(data.get('callExpDateMap', {}).keys()) +
        list(data.get('putExpDateMap',  {}).keys())
    ))

    # No expiries returned — date filter matched nothing; fall back to all expiries
    if not expiries and expiry_date:
        print(f'\n  No data for {expiry_date} — fetching all expiries to show available dates...')
        data = get_option_chain(ticker, strikes=strikes)
        underlying = data.get('underlyingPrice', 0)
        expiries   = sorted(set(
            list(data.get('callExpDateMap', {}).keys()) +
            list(data.get('putExpDateMap',  {}).keys())
        ))
        print(f'  Available expiries: {", ".join(k.split(":")[0] for k in expiries)}\n')

    print(f'\n  {ticker}  underlying ${underlying:.2f}')

    for exp_key in expiries:
        exp_label = exp_key.split(':')[0]   # '2026-07-17:32' → '2026-07-17'
        dte       = exp_key.split(':')[1]   # DTE
        calls = data.get('callExpDateMap', {}).get(exp_key, {})
        puts  = data.get('putExpDateMap',  {}).get(exp_key, {})
        all_strikes = sorted(set(list(calls.keys()) + list(puts.keys())), key=float)

        if not all_strikes:
            continue

        atm_dist = min(abs(float(s) - underlying) for s in all_strikes)

        print(f'\n  Expiry: {exp_label}  ({dte} DTE)')
        print(f'  {"Strike":>8}  {"C Bid":>7} {"C Ask":>7} {"IV%":>6} {"Delta":>7}  │  {"P Bid":>7} {"P Ask":>7} {"IV%":>6}')
        print(f'  {"─"*8}  {"─"*7} {"─"*7} {"─"*6} {"─"*7}  │  {"─"*7} {"─"*7} {"─"*6}')

        for strike_str in all_strikes:
            strike = float(strike_str)
            atm    = '►' if abs(strike - underlying) == atm_dist else ' '

            co = (calls.get(strike_str) or [{}])[0]
            po = (puts.get(strike_str)  or [{}])[0]

            cb  = co.get('bid', 0);  ca  = co.get('ask', 0)
            civ = co.get('volatility', 0); cd = co.get('delta', 0)
            pb  = po.get('bid', 0);  pa  = po.get('ask', 0)
            piv = po.get('volatility', 0)

            print(f'{atm} {strike:>8.1f}  {cb:>7.2f} {ca:>7.2f} {civ:>5.1f}% {cd:>7.3f}  │  {pb:>7.2f} {pa:>7.2f} {piv:>5.1f}%')

    print()


def place_spread(account_hash, ticker, long_symbol, short_symbol, quantity, net_debit):
    """
    Place a bull call debit spread as a single NET_DEBIT order.
    long_symbol / short_symbol: full OCC option symbols
    e.g. 'MU   260620C01000000'  (ticker + expiry YYMMDD + C/P + 8-digit strike*1000)
    """
    c = get_client()
    order = (
        schwab.orders.options.bull_call_vertical_open(
            long_call_symbol  = long_symbol,
            short_call_symbol = short_symbol,
            quantity          = quantity,
            net_debit         = net_debit,
        )
    )
    r = c.place_order(account_hash, order)
    return r


def place_bear_put_spread(account_hash, ticker, long_symbol, short_symbol, quantity, net_debit):
    """
    Place a bear put debit spread as a single NET_DEBIT order.
    long_symbol: higher-strike put (buy), short_symbol: lower-strike put (sell).
    """
    c = get_client()
    order = (
        schwab.orders.options.bear_put_vertical_open(
            long_put_symbol  = long_symbol,
            short_put_symbol = short_symbol,
            quantity         = quantity,
            net_debit        = net_debit,
        )
    )
    r = c.place_order(account_hash, order)
    return r


def get_order(account_hash: str, order_id: str) -> dict:
    """Fetch a single order by ID. Returns the raw Schwab order JSON."""
    c = get_client()
    r = c.get_order(int(order_id), account_hash)
    return r.json()


def get_orders_for_account(account_hash: str, max_results: int = 50) -> list:
    """Return recent orders for an account (working + terminal states)."""
    c = get_client()
    r = c.get_orders_for_account(account_hash, max_results=max_results)
    return r.json()


def cancel_order(account_hash: str, order_id: str) -> bool:
    """Cancel a working order. Returns True if accepted (200/204)."""
    c = get_client()
    r = c.cancel_order(int(order_id), account_hash)
    return r.status_code in (200, 204)


if __name__ == '__main__':
    if '--auth' in sys.argv:
        print('\n  Opening browser for Schwab OAuth login ...')
        print('  Log in with your actual Schwab trading account credentials.')
        print(f'  Token will be saved to {TOKEN_PATH}\n')
        get_client()
        print('\n  Auth complete. Token saved.\n')

    elif '--accounts' in sys.argv:
        print(json.dumps(get_accounts(), indent=2))

    elif '--positions' in sys.argv:
        print(json.dumps(get_positions(), indent=2))

    elif '--quote' in sys.argv:
        idx = sys.argv.index('--quote')
        ticker = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else 'MU'
        print(json.dumps(get_quote(ticker), indent=2))

    elif '--history' in sys.argv:
        idx    = sys.argv.index('--history')
        args   = sys.argv[idx + 1:]
        ticker = args[0].upper() if args else 'MNST'
        period = args[1] if len(args) > 1 else '3m'   # 3m | 6m | 1y | 2y
        bar    = args[2] if len(args) > 2 else 'daily' # daily | weekly
        print_history_summary(ticker, period=period, bar=bar)

    elif '--chain' in sys.argv:
        idx    = sys.argv.index('--chain')
        args   = sys.argv[idx + 1:]
        ticker = args[0].upper() if args else 'MU'
        expiry = args[1] if len(args) > 1 else None   # YYYY-MM-DD  (optional)
        n      = int(args[2]) if len(args) > 2 else 10  # strikes ATM (optional)
        print_chain(ticker, expiry_date=expiry, strikes=n)

    elif '--fundamentals' in sys.argv:
        idx    = sys.argv.index('--fundamentals')
        args   = sys.argv[idx + 1:]
        tickers = [t.upper() for t in args if not t.startswith('--')] or ['NVDA']
        for t in tickers:
            print_fundamentals(t)

    else:
        print('\n  Usage:')
        print('    python schwab_client.py --auth                      # first-time OAuth login')
        print('    python schwab_client.py --accounts                  # list accounts')
        print('    python schwab_client.py --positions                 # current positions')
        print('    python schwab_client.py --quote MU                  # get a quote')
        print('    python schwab_client.py --history MNST              # daily MA summary (3m)')
        print('    python schwab_client.py --history MNST 2y weekly    # 2yr weekly bars')
        print('    python schwab_client.py --chain MU                  # full option chain')
        print('    python schwab_client.py --chain MU 2026-07-18       # single expiry')
        print('    python schwab_client.py --chain MU 2026-07-18 15    # 15 strikes ATM')
        print('    python schwab_client.py --fundamentals NVDA          # fundamentals (margins, ROE, growth)')
        print('    python schwab_client.py --fundamentals NVDA AAPL MU  # multiple tickers')
        print()
