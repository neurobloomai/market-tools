"""
event_risk.py — Per-ticker earnings date fetch and risk flagging.

Shared by pop_scan and extension_scan. No scan imports.
Only flags earnings within 30 days — beyond that it's not a near-term setup risk.

Caches results to earnings_cache.json (7-day TTL) so back-to-back runs
don't re-hit Yahoo after a heavy pass1 scan has already stressed the session.
"""

import json
import os
import time
import yfinance as yf
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor

EVENT_CSS = """
  .er-high { font-size:10px; font-weight:700; color:#f85149; margin-left:5px;
             background:rgba(248,81,73,0.12); padding:1px 5px; border-radius:3px; }
  .er-warn { font-size:10px; font-weight:600; color:#f0883e; margin-left:5px;
             background:rgba(240,136,62,0.10); padding:1px 5px; border-radius:3px; }
  .er-near { font-size:10px; color:#d4a017; margin-left:5px; }"""

_R   = '\033[91m'
_ORG = '\033[33m'
_DIM = '\033[2m'
_RST = '\033[0m'

_CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'earnings_cache.json')
_TTL_DAYS   = 7


# ── Cache helpers ─────────────────────────────────────────────────────────────

def _load_cache():
    try:
        with open(_CACHE_FILE) as f:
            return json.load(f)
    except Exception:
        return {}

def _save_cache(new_entries):
    """Merge new_entries into cache. new_entries: {ticker: date_or_None}."""
    existing  = _load_cache()
    today_str = datetime.now(timezone.utc).date().isoformat()
    for ticker, date in new_entries.items():
        existing[ticker] = {
            'date':    date.isoformat() if date else None,
            'fetched': today_str,
        }
    try:
        with open(_CACHE_FILE, 'w') as f:
            json.dump(existing, f, indent=2)
    except Exception:
        pass

def _check_cache(ticker, cache, today):
    """Returns (date_or_None, hit) — hit=True means use cached value."""
    entry = cache.get(ticker)
    if not isinstance(entry, dict):
        return None, False
    try:
        fetched = datetime.fromisoformat(entry['fetched']).date()
        if (today - fetched).days > _TTL_DAYS:
            return None, False
    except Exception:
        return None, False
    date_str = entry.get('date')
    if not date_str:
        return None, True   # cached as None (ETF / no earnings)
    try:
        return datetime.fromisoformat(date_str).date(), True
    except Exception:
        return None, False


# ── Live fetch ────────────────────────────────────────────────────────────────

def get_earnings_date(ticker):
    """Return next upcoming earnings date as datetime.date, or None (live fetch)."""
    today = datetime.now(timezone.utc).date()
    try:
        t   = yf.Ticker(ticker)
        cal = t.calendar
        if isinstance(cal, dict):
            dates = cal.get('Earnings Date') or []
            if isinstance(dates, list):
                future = [d for d in dates if hasattr(d, 'year') and d >= today]
                if future:
                    return min(future)
            elif hasattr(dates, 'year') and dates >= today:
                return dates
        # fallback: earningsTimestamp from info
        ts = (t.info or {}).get('earningsTimestamp')
        if ts:
            d = datetime.fromtimestamp(ts, tz=timezone.utc).date()
            if d >= today:
                return d
    except Exception:
        pass
    return None


def get_earnings_batch(tickers, max_workers=4):
    """
    Batch fetch with disk cache.
    - Cache-hits skip live calls (7-day TTL).
    - Live fetches use max_workers=4 (lower than pass1 to avoid rate limits).
    - 1s pause before live calls so post-scan Yahoo session can recover.
    Returns {ticker: date_or_None}.
    """
    cache  = _load_cache()
    today  = datetime.now(timezone.utc).date()
    result = {}
    needs  = []

    for t in tickers:
        date, hit = _check_cache(t, cache, today)
        if hit:
            result[t] = date
        else:
            needs.append(t)

    if needs:
        time.sleep(1.0)   # let Yahoo recover after heavy pass1 traffic
        with ThreadPoolExecutor(max_workers=max_workers) as ex:
            dates = list(ex.map(get_earnings_date, needs))
        new_entries = dict(zip(needs, dates))
        result.update(new_entries)
        _save_cache(new_entries)

    return result


# ── Risk classification ───────────────────────────────────────────────────────

def earnings_risk(earnings_date):
    """
    Returns (days, level) or (None, None).
    level: 'HIGH' ≤7d · 'WARN' 8-14d · 'NEAR' 15-30d · 'WATCH' 31-45d · None >45d

    Threshold is 45d (not 30d) to cover the full 30-45 DTE spread holding window —
    earnings at day 33 falls squarely inside a position entered today at 45 DTE.
    """
    if earnings_date is None:
        return None, None
    today = datetime.now(timezone.utc).date()
    days  = (earnings_date - today).days
    if days < 0:
        return None, None
    if days <= 7:
        return days, 'HIGH'
    if days <= 14:
        return days, 'WARN'
    if days <= 30:
        return days, 'NEAR'
    if days <= 45:
        return days, 'WATCH'
    return days, None


def earnings_cli(earnings_date):
    """ANSI CLI string for ER column. Empty string if >45d or unknown."""
    days, level = earnings_risk(earnings_date)
    if level == 'HIGH':
        return f'{_R}⚠{days}d{_RST}'
    if level == 'WARN':
        return f'{_ORG}~{days}d{_RST}'
    if level == 'NEAR':
        return f'{_DIM}{days}d{_RST}'
    if level == 'WATCH':
        return f'{_DIM}{days}d?{_RST}'
    return ''


def earnings_html_badge(earnings_date):
    """Inline HTML badge. Empty string if >30d or unknown."""
    days, level = earnings_risk(earnings_date)
    if level == 'HIGH':
        return f'<span class="er-high" title="Earnings in {days} days">⚠ ER {days}d</span>'
    if level == 'WARN':
        return f'<span class="er-warn" title="Earnings in {days} days">ER {days}d</span>'
    if level == 'NEAR':
        return f'<span class="er-near" title="Earnings in {days} days">ER {days}d</span>'
    if level == 'WATCH':
        return f'<span class="er-near" title="Earnings in {days} days">ER {days}d?</span>'
    return ''


if __name__ == '__main__':
    import sys
    tickers = [t.upper() for t in sys.argv[1:]] if len(sys.argv) > 1 else []
    if not tickers:
        print('Usage: python event_risk.py TICKER [TICKER ...]')
        sys.exit(1)
    dates = get_earnings_batch(tickers)
    for ticker in tickers:
        ed = dates.get(ticker)
        days, level = earnings_risk(ed)
        if ed is None:
            print(f'  {ticker}: no earnings date found')
        elif level is None:
            print(f'  {ticker}: {ed}  ({days}d out — beyond 45d window, clear)')
        else:
            flag = {'HIGH': '⚠ HIGH', 'WARN': '~ WARN', 'NEAR': 'NEAR', 'WATCH': 'WATCH?'}.get(level, level)
            print(f'  {ticker}: {ed}  ({days}d)  {flag}')
