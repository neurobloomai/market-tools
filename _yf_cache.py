"""
_yf_cache.py — shared HTTP cache for all screener scripts

Installs a requests-cache session that transparently caches Yahoo Finance
responses. Import this before yfinance in any script that fetches data.

TTL: 4 hours  — data refreshes each session, but repeated script runs
     within the same sitting hit the cache instead of Yahoo's rate limit.

stale_if_error: True — if Yahoo rate-limits mid-run, serve the last cached
     response instead of crashing with YFRateLimitError.
"""
import os
import requests_cache
from datetime import timedelta

_cache_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.yf_cache')

requests_cache.install_cache(
    _cache_path,
    expire_after=timedelta(hours=4),
    allowable_codes=[200],
    stale_if_error=True,
)
