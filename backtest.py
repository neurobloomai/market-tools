"""
backtest.py — 4/4 MA Alignment + Quality Framework Validation

5 years of weekly price history. Reconstructs historical 4/4 MA alignment
and measures forward returns vs SPY benchmark.

4/4 alignment definition (matches screener exactly):
  price > SMA10w AND price > SMA20w AND price > SMA43w AND price > SMA87w

Entry types:
  fresh   — first 4/4 week after ≥1 non-4/4 week (the actual breakout signal)
  non-4/4 — weeks when A+ names are NOT 4/4 (quality-without-timing baseline)

Forward windows: 4w · 13w · 26w · 52w
Benchmark: SPY (same calendar window)

Quality buckets (current-snapshot grades — see limitation #2):
  A+  · A  · B/— (structure signal only)

Documented limitations:
  1. Survivorship bias — current universe only; delisted/failed names excluded
  2. Quality look-ahead bias — current grades proxy for historical quality
     (Mild for durable A+ names like MA/AAPL/ITW; real for borderline names)
  3. No transaction costs
  Structural 4/4 signal is fully historical and bias-free.

Run:  python3 backtest.py
Out:  backtest.html
"""

import _yf_cache  # noqa
import yfinance as yf, warnings, os, json, subprocess
import numpy as np
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

warnings.filterwarnings('ignore')

from aligned_screener import TICKERS
from screener import UNIVERSE

PERIODS = [4, 13, 26, 52]
REPO    = os.path.dirname(os.path.abspath(__file__))

# ── data fetching ─────────────────────────────────────────────────────────────

def _fetch(ticker):
    try:
        hist = yf.Ticker(ticker).history(period='5y', interval='1wk', auto_adjust=True)
        if hist.empty or len(hist) < 90:
            return ticker, None
        return ticker, hist[['Close']].copy()
    except Exception:
        return ticker, None


# ── signal computation ────────────────────────────────────────────────────────

def compute_alignment(close):
    """True when price > SMA10w, SMA20w, SMA43w, SMA87w (same as screener)."""
    s10  = close.rolling(10,  min_periods=10).mean()
    s20  = close.rolling(20,  min_periods=20).mean()
    s43  = close.rolling(43,  min_periods=43).mean()
    s87  = close.rolling(87,  min_periods=87).mean()
    return (close > s10) & (close > s20) & (close > s43) & (close > s87)


def fresh_entries(aligned):
    """Indices where 4/4 begins (non-4/4 → 4/4 transition)."""
    arr = aligned.values
    return [i for i in range(1, len(arr)) if arr[i] and not arr[i-1]]


def non_4_4_samples(aligned, step=13):
    """Indices where NOT 4/4, sampled every `step` weeks (quality baseline)."""
    arr = aligned.values
    samples, last = [], -step
    for i in range(len(arr)):
        if not arr[i] and (i - last) >= step:
            samples.append(i)
            last = i
    return samples


# ── return measurement ────────────────────────────────────────────────────────

def measure(ticker_close, spy_close, entry_idx, weeks):
    """
    Return (ticker_ret, spy_ret, max_dd) or None.
    Uses ticker index to find matching SPY dates.
    """
    exit_idx = entry_idx + weeks
    if exit_idx >= len(ticker_close):
        return None

    entry_date = ticker_close.index[entry_idx]
    exit_date  = ticker_close.index[exit_idx]

    # SPY: find closest dates
    spy_entry = spy_close.index.searchsorted(entry_date)
    spy_exit  = spy_close.index.searchsorted(exit_date)
    if spy_entry >= len(spy_close) or spy_exit >= len(spy_close):
        return None

    t_entry = float(ticker_close.iloc[entry_idx])
    t_exit  = float(ticker_close.iloc[exit_idx])
    if t_entry <= 0:
        return None

    ticker_ret = t_exit / t_entry - 1
    spy_ret    = float(spy_close.iloc[spy_exit]) / float(spy_close.iloc[spy_entry]) - 1
    hold_slice = ticker_close.iloc[entry_idx:exit_idx + 1]
    max_dd     = (float(hold_slice.min()) - t_entry) / t_entry

    return (ticker_ret, spy_ret, max_dd)


# ── aggregation ───────────────────────────────────────────────────────────────

def agg(results):
    if not results:
        return None
    rets   = np.array([r[0] for r in results])
    spys   = np.array([r[1] for r in results])
    dds    = np.array([r[2] for r in results])
    alpha  = rets - spys
    return dict(
        n         = len(results),
        win_pct   = float((alpha > 0).mean() * 100),
        avg_ret   = float(rets.mean()   * 100),
        avg_spy   = float(spys.mean()   * 100),
        avg_alpha = float(alpha.mean()  * 100),
        med_alpha = float(np.median(alpha) * 100),
        p25       = float(np.percentile(alpha, 25) * 100),
        p75       = float(np.percentile(alpha, 75) * 100),
        avg_dd    = float(dds.mean()    * 100),
    )


# ── HTML ──────────────────────────────────────────────────────────────────────

CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: 'SF Mono','Fira Code',monospace; background: #0d1117;
       color: #e6edf3; padding: 32px 24px; font-size: 13px;
       max-width: 1100px; margin: 0 auto; line-height: 1.7; }
h1 { font-size: 20px; font-weight: 700; color: #f0883e; margin-bottom: 4px; }
h2 { font-size: 12px; font-weight: 700; color: #f0883e; margin: 36px 0 12px;
     text-transform: uppercase; letter-spacing: .06em; }
p  { color: #8b949e; font-size: 12px; margin-bottom: 10px; }
a  { color: #58a6ff; text-decoration: none; }
.sub { color: #8b949e; font-size: 11px; margin-bottom: 28px; }
table { width: 100%; border-collapse: collapse; margin-bottom: 24px; font-size: 11px; }
th { text-align: right; padding: 6px 10px; color: #8b949e; font-weight: 500;
     border-bottom: 2px solid #21262d; font-size: 10px;
     text-transform: uppercase; letter-spacing: .05em; }
th:first-child { text-align: left; }
td { padding: 7px 10px; border-bottom: 1px solid #161b22;
     color: #8b949e; text-align: right; }
td:first-child { color: #e6edf3; font-weight: 600; text-align: left; }
.pos { color: #3fb950; font-weight: 700; }
.neg { color: #f85149; font-weight: 700; }
.neu { color: #e3b341; font-weight: 700; }
.dim { color: #484f58; }
.sep { border-top: 2px solid #30363d; }
.warn { background: #161b22; border-left: 3px solid #e3b341;
        padding: 12px 16px; border-radius: 0 6px 6px 0; margin: 16px 0 24px; }
.warn p { color: #e6edf3; font-size: 11px; margin-bottom: 4px; }
.warn p:last-child { margin-bottom: 0; color: #8b949e; }
.legend { display: flex; gap: 20px; flex-wrap: wrap; margin: 8px 0 24px; }
.legend span { font-size: 10px; color: #8b949e; }
"""

def _c(v, fmt='+.1f'):
    """Color a percentage value."""
    if v is None:
        return '<span class="dim">—</span>'
    s = format(v, fmt) + '%'
    cls = 'pos' if v > 0.5 else ('neg' if v < -0.5 else 'neu')
    return f'<span class="{cls}">{s}</span>'


def _n(v, fmt='.1f'):
    if v is None:
        return '<span class="dim">—</span>'
    return format(v, fmt) + '%'


def build_html(stats, now, tickers_by_grade, universe_n, warned_tickers):
    """stats: {label: {period: agg_dict}}"""

    period_labels = {4: '4w', 13: '13w', 26: '26w', 52: '52w'}

    rows_html = ''
    for i, (label, by_period) in enumerate(stats.items()):
        sep = ' class="sep"' if i in (3, 4) else ''
        rows_html += f'<tr{sep}><td>{label}</td>'
        for p in PERIODS:
            d = by_period.get(p)
            if not d:
                rows_html += '<td class="dim" colspan="7">—</td>'
                continue
            rows_html += (
                f'<td>{d["n"]}</td>'
                f'<td>{_c(d["avg_alpha"])}</td>'
                f'<td>{_c(d["med_alpha"])}</td>'
                f'<td>{_c(d["win_pct"], fmt="+.0f")}</td>'
                f'<td>{_n(d["avg_ret"])}</td>'
                f'<td>{_n(d["avg_spy"])}</td>'
                f'<td>{_n(d["avg_dd"])}</td>'
            )
        rows_html += '</tr>\n'

    # Period header spans
    period_header = ''
    for p in PERIODS:
        period_header += (
            f'<th colspan="7" style="text-align:center;'
            f'border-left:1px solid #30363d;color:#58a6ff">'
            f'{period_labels[p]} Forward</th>'
        )

    col_header = ''
    for _ in PERIODS:
        col_header += (
            '<th>n</th>'
            '<th>Avg α</th>'
            '<th>Med α</th>'
            '<th>Win%</th>'
            '<th>Ret</th>'
            '<th>SPY</th>'
            '<th>MaxDD</th>'
        )

    grade_breakdown = ''
    for g in ['A+', 'A', 'B', '—']:
        names = tickers_by_grade.get(g, [])
        if names:
            grade_breakdown += (
                f'<p><strong style="color:#e6edf3">{g}</strong>'
                f'<span class="dim"> ({len(names)})</span>  '
                + '  '.join(names) + '</p>'
            )

    warned_html = ''
    if warned_tickers:
        warned_html = (
            '<p style="color:#484f58;font-size:10px">Tickers with insufficient history '
            f'(&lt;90 weekly bars) excluded: {", ".join(sorted(warned_tickers))}</p>'
        )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Backtest — 4/4 MA Framework</title>
<style>{CSS}</style>
</head>
<body>

<h1>4/4 MA Alignment Backtest</h1>
<div class="sub">
  5-year weekly · {universe_n} tickers · fresh-entry vs non-4/4 baseline · {now}
  · <a href="index.html">← Market Tools</a>
</div>

<div class="warn">
  <p>⚠ Documented limitations — read before acting on these numbers</p>
  <p>1. <strong>Survivorship bias</strong>: current universe only; delisted/failed names excluded → overstates returns</p>
  <p>2. <strong>Quality look-ahead bias</strong>: current A+/A grades used as historical proxy → A+ filter result is approximate, not clean</p>
  <p>3. <strong>No transaction costs</strong> included</p>
  <p>Structural 4/4 MA signal is fully historical and bias-free. Quality comparison is directional evidence, not proof.</p>
</div>

<h2>Results — Fresh 4/4 Entry vs Baseline</h2>
<p style="color:#8b949e;font-size:11px">
  <strong style="color:#e6edf3">Fresh entry</strong>: first 4/4 week after ≥1 non-4/4 week.
  <strong style="color:#e6edf3">Non-4/4 baseline</strong>: A+ names during non-aligned weeks (sampled every 13w).
  Alpha = ticker return − SPY return over same window. Win% = % entries beating SPY.
</p>

<div style="overflow-x:auto">
<table>
<thead>
<tr>
  <th rowspan="2" style="text-align:left;vertical-align:bottom">Filter</th>
  {period_header}
</tr>
<tr>
  {col_header}
</tr>
</thead>
<tbody>
{rows_html}
</tbody>
</table>
</div>

<div class="legend">
  <span>α = alpha vs SPY over same window</span>
  <span>Med α = median alpha (less skewed by outliers)</span>
  <span>Win% = % of entries that beat SPY</span>
  <span>MaxDD = avg max drawdown during hold</span>
  <span><span class="pos">green</span> = positive alpha  <span class="neg">red</span> = negative  <span class="neu">yellow</span> = flat</span>
</div>

<h2>Quality Grade Breakdown</h2>
{grade_breakdown}

<h2>Methodology</h2>
<p>
  <strong style="color:#e6edf3">4/4 alignment</strong>: price &gt; SMA10w, SMA20w, SMA43w (10-month), SMA87w (20-month) —
  identical to the live screener. Computed from raw weekly OHLCV history.
</p>
<p>
  <strong style="color:#e6edf3">Fresh entry</strong>: first week a ticker crosses into 4/4 after being non-4/4.
  This is the actionable signal — when structure first aligns. Multiple fresh entries per ticker
  possible across 5 years if structure breaks and recovers.
</p>
<p>
  <strong style="color:#e6edf3">Non-4/4 baseline</strong>: weeks when A+ tickers are NOT 4/4 aligned,
  sampled every 13w to reduce autocorrelation. Tests: does the MA timing filter add value beyond
  quality alone?
</p>
<p>
  <strong style="color:#e6edf3">Data period</strong>: 5 years weekly (yfinance). Minimum 90 weeks required for SMA87 + buffer.
  Tickers with insufficient history excluded.
</p>
{warned_html}

<p style="color:#484f58;font-size:10px;margin-top:32px;border-top:1px solid #21262d;padding-top:12px">
  Educational framework validation only. Not financial advice. Past backtest results do not predict future performance.
  All analysis subject to survivorship bias and data limitations noted above.
</p>

</body>
</html>"""


# ── main ──────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    now = datetime.now(timezone.utc).strftime('%b %d %Y  %H:%M UTC')
    print(f"\n  Backtest — 4/4 MA Alignment Framework  ({now})")

    # Load grade map from cache (populated by aligned_screener runs)
    grade_path = os.path.join(REPO, 'grades_cache.json')
    grade_map  = {}
    if os.path.exists(grade_path):
        with open(grade_path) as f:
            grade_map = json.load(f)

    # Fetch SPY first as the benchmark
    print(f"  Fetching SPY benchmark ...")
    _, spy_hist = _fetch('SPY')
    if spy_hist is None:
        print("  ERROR: could not fetch SPY data")
        raise SystemExit(1)
    spy_close = spy_hist['Close']

    # Fetch all tickers
    all_tickers = list(dict.fromkeys(TICKERS + ['SPY']))
    print(f"  Fetching 5y weekly data for {len(TICKERS)} tickers ...")
    with ThreadPoolExecutor(max_workers=20) as ex:
        raw = list(ex.map(_fetch, TICKERS))

    price_data     = {}
    warned_tickers = []
    for ticker, hist in raw:
        if hist is not None:
            price_data[ticker] = hist['Close']
        else:
            warned_tickers.append(ticker)

    print(f"  Loaded: {len(price_data)} tickers  ({len(warned_tickers)} skipped — insufficient history)")

    # Build tickers_by_grade for display
    tickers_by_grade = {'A+': [], 'A': [], 'B': [], '—': []}
    for t in TICKERS:
        g = grade_map.get(t, '—')
        key = g if g in tickers_by_grade else '—'
        tickers_by_grade[key].append(t)

    # Collect entries and returns
    # buckets: A+_fresh, A_fresh, Bx_fresh (B or —), all_fresh, Aplus_non44
    buckets = {lbl: {p: [] for p in PERIODS}
               for lbl in ('A+', 'A', 'B/—', 'All 4/4', 'A+ non-4/4')}

    processed = 0
    for ticker, close in price_data.items():
        aligned = compute_alignment(close)
        grade   = grade_map.get(ticker, '—')

        # Determine bucket label
        if grade == 'A+':
            blabel = 'A+'
        elif grade == 'A':
            blabel = 'A'
        else:
            blabel = 'B/—'

        # Fresh 4/4 entries
        for idx in fresh_entries(aligned):
            for p in PERIODS:
                r = measure(close, spy_close, idx, p)
                if r:
                    buckets[blabel][p].append(r)
                    buckets['All 4/4'][p].append(r)

        # Non-4/4 baseline (A+ only)
        if grade == 'A+':
            for idx in non_4_4_samples(aligned):
                for p in PERIODS:
                    r = measure(close, spy_close, idx, p)
                    if r:
                        buckets['A+ non-4/4'][p].append(r)

        processed += 1

    print(f"  Processed {processed} tickers")

    # Aggregate
    stats_labels = [
        ('A+ quality  +  4/4 fresh entry',  'A+'),
        ('A quality   +  4/4 fresh entry',  'A'),
        ('B/— quality +  4/4 fresh entry',  'B/—'),
        ('All tickers +  4/4 fresh entry',  'All 4/4'),
        ('A+ quality  +  non-4/4 baseline', 'A+ non-4/4'),
    ]

    stats = {}
    for display_label, bucket_key in stats_labels:
        by_period = {}
        for p in PERIODS:
            d = agg(buckets[bucket_key][p])
            by_period[p] = d
        stats[display_label] = by_period

    # CLI summary — 13w period
    print(f"\n  {'Filter':<42}  {'n':>5}  {'Win%':>6}  {'Avg α':>7}  {'Med α':>7}  {'Avg Ret':>8}  {'AvgSPY':>7}  {'MaxDD':>7}")
    print(f"  {'─'*42}  {'─'*5}  {'─'*6}  {'─'*7}  {'─'*7}  {'─'*8}  {'─'*7}  {'─'*7}")
    for display_label, bucket_key in stats_labels:
        d = stats[display_label].get(13)
        if d:
            sep = '  ←── baseline' if 'non-4/4' in display_label else ''
            print(
                f"  {display_label:<42}  {d['n']:>5}  {d['win_pct']:>5.1f}%"
                f"  {d['avg_alpha']:>+6.1f}%  {d['med_alpha']:>+6.1f}%"
                f"  {d['avg_ret']:>+7.1f}%  {d['avg_spy']:>+6.1f}%  {d['avg_dd']:>+6.1f}%{sep}"
            )

    # Entry count summary
    aplus_entries_13 = len(buckets['A+'][13])
    a_entries_13     = len(buckets['A'][13])
    bx_entries_13    = len(buckets['B/—'][13])
    print(f"\n  Total fresh 4/4 entries (13w window): A+={aplus_entries_13}  A={a_entries_13}  B/—={bx_entries_13}")

    # HTML
    html = build_html(stats, now, tickers_by_grade, len(price_data), warned_tickers)
    out  = os.path.join(REPO, 'backtest.html')
    with open(out, 'w') as f:
        f.write(html)
    print(f"\n  Saved → {out}")

    # Push
    try:
        subprocess.run(['git', '-C', REPO, 'add', 'backtest.html'], check=True)
        diff = subprocess.run(['git', '-C', REPO, 'diff', '--cached', '--quiet'])
        if diff.returncode != 0:
            subprocess.run(['git', '-C', REPO, 'commit',
                            '-m', f'backtest: {now}'], check=True)
            subprocess.run(['git', '-C', REPO, 'push'], check=True)
            print(f"  Pushed → GitHub  (backtest: {now})")
        else:
            print("  GitHub — no changes to push")
    except subprocess.CalledProcessError as e:
        print(f"  Push failed: {e}")
