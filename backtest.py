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

Analyses:
  1. Forward return summary — win%, avg/median alpha, maxDD
  2. Left-tail distribution — % of entries below alpha thresholds at 13w
  3. Vol regime at entry — SPY 13w realized vol bucketed: low/med/high

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
    s10 = close.rolling(10,  min_periods=10).mean()
    s20 = close.rolling(20,  min_periods=20).mean()
    s43 = close.rolling(43,  min_periods=43).mean()
    s87 = close.rolling(87,  min_periods=87).mean()
    return (close > s10) & (close > s20) & (close > s43) & (close > s87)


def fresh_entries(aligned):
    """Indices where 4/4 begins (non-4/4 → 4/4 transition)."""
    arr = aligned.values
    return [i for i in range(1, len(arr)) if arr[i] and not arr[i-1]]


def non_4_4_samples(aligned, step=13):
    """Indices where NOT 4/4, sampled every step weeks (quality-without-timing baseline)."""
    arr = aligned.values
    samples, last = [], -step
    for i in range(len(arr)):
        if not arr[i] and (i - last) >= step:
            samples.append(i)
            last = i
    return samples


# ── return measurement ────────────────────────────────────────────────────────

def measure(ticker_close, spy_close, spy_vol, entry_idx, weeks):
    """
    Return (ticker_ret, spy_ret, max_dd, spy_vol_at_entry) or None.
    spy_vol: precomputed SPY 13w rolling annualized realized vol series.
    """
    exit_idx = entry_idx + weeks
    if exit_idx >= len(ticker_close):
        return None

    entry_date = ticker_close.index[entry_idx]
    exit_date  = ticker_close.index[exit_idx]

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

    vol_val = None
    if spy_entry < len(spy_vol):
        v = spy_vol.iloc[spy_entry]
        if not np.isnan(v):
            vol_val = float(v)

    return (ticker_ret, spy_ret, max_dd, vol_val)


# ── aggregation ───────────────────────────────────────────────────────────────

def agg(results):
    if not results:
        return None
    rets  = np.array([r[0] for r in results])
    spys  = np.array([r[1] for r in results])
    dds   = np.array([r[2] for r in results])
    alpha = rets - spys
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


def left_tail_dist(results, thresholds=(-0.20, -0.10, -0.05, 0.0, 0.05, 0.10, 0.20)):
    """% of entries whose 13w alpha falls below each threshold."""
    if not results:
        return None
    alphas = np.array([r[0] - r[1] for r in results])
    return {t: float((alphas < t).mean() * 100) for t in thresholds}


def vol_regime_stats(results):
    """
    Group entries by SPY annualized realized vol at entry.
    Returns dict: regime_label -> agg_dict + entry_pct
    """
    total = len(results)
    bins = [
        ('Low   (<15%)',   lambda v: v is not None and v < 0.15),
        ('Med  (15-25%)',  lambda v: v is not None and 0.15 <= v < 0.25),
        ('High  (>25%)',   lambda v: v is not None and v >= 0.25),
    ]
    out = {}
    for label, test in bins:
        subset = [r for r in results if test(r[3])]
        d = agg(subset)
        if d:
            d['entry_pct'] = len(subset) / total * 100
        out[label] = d
    return out


# ── HTML ──────────────────────────────────────────────────────────────────────

CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: 'SF Mono','Fira Code',monospace; background: #0d1117;
       color: #e6edf3; padding: 32px 24px; font-size: 13px;
       max-width: 1100px; margin: 0 auto; line-height: 1.7; }
h1 { font-size: 20px; font-weight: 700; color: #f0883e; margin-bottom: 4px; }
h2 { font-size: 12px; font-weight: 700; color: #f0883e; margin: 36px 0 12px;
     text-transform: uppercase; letter-spacing: .06em; }
h3 { font-size: 11px; font-weight: 700; color: #e6edf3; margin: 20px 0 8px; }
p  { color: #8b949e; font-size: 12px; margin-bottom: 10px; }
a  { color: #58a6ff; text-decoration: none; }
.sub { color: #8b949e; font-size: 11px; margin-bottom: 28px; }
table { width: 100%; border-collapse: collapse; margin-bottom: 20px; font-size: 11px; }
th { text-align: right; padding: 6px 10px; color: #8b949e; font-weight: 500;
     border-bottom: 2px solid #21262d; font-size: 10px;
     text-transform: uppercase; letter-spacing: .05em; }
th:first-child { text-align: left; }
td { padding: 7px 10px; border-bottom: 1px solid #161b22;
     color: #8b949e; text-align: right; }
td:first-child { color: #e6edf3; font-weight: 600; text-align: left; }
.pos  { color: #3fb950; font-weight: 700; }
.neg  { color: #f85149; font-weight: 700; }
.neu  { color: #e3b341; font-weight: 700; }
.dim  { color: #484f58; }
.sep  { border-top: 2px solid #30363d; }
.warn { background: #161b22; border-left: 3px solid #e3b341;
        padding: 12px 16px; border-radius: 0 6px 6px 0; margin: 16px 0 24px; }
.warn p { color: #e6edf3; font-size: 11px; margin-bottom: 4px; }
.warn p:last-child { margin-bottom: 0; color: #8b949e; }
.legend { display: flex; gap: 20px; flex-wrap: wrap; margin: 8px 0 24px; }
.legend span { font-size: 10px; color: #8b949e; }
.insight { background: #161b22; border-left: 3px solid #3fb950;
           padding: 12px 16px; border-radius: 0 6px 6px 0; margin: 12px 0 20px; }
.insight p { color: #e6edf3; font-size: 11px; margin-bottom: 4px; }
.insight p:last-child { color: #8b949e; margin-bottom: 0; }
.bar { display: inline-block; height: 8px; background: #3fb950;
       border-radius: 2px; vertical-align: middle; margin-right: 4px; }
.bar-neg { background: #f85149; }
.bar-neu { background: #e3b341; }
"""


def _c(v, fmt='+.1f'):
    if v is None:
        return '<span class="dim">—</span>'
    s   = format(v, fmt) + '%'
    cls = 'pos' if v > 0.5 else ('neg' if v < -0.5 else 'neu')
    return f'<span class="{cls}">{s}</span>'


def _n(v, fmt='.1f', suffix='%'):
    if v is None:
        return '<span class="dim">—</span>'
    return format(v, fmt) + suffix


def _bar(pct, max_pct=100, width=60, cls=''):
    w = max(1, int(pct / max_pct * width))
    return f'<span class="bar {cls}" style="width:{w}px"></span>{pct:.1f}%'


def _tail_cell(v, threshold):
    """Color left-tail cells: high % below threshold = bad (red), low = good (green)."""
    if v is None:
        return '<td class="dim">—</td>'
    cls = 'neg' if threshold < 0 and v > 30 else ('pos' if threshold < 0 and v < 20 else '')
    return f'<td class="{cls}">{v:.1f}%</td>'


def build_html(stats, dist_data, vol_data, now, tickers_by_grade, universe_n, warned_tickers):
    period_labels = {4: '4w', 13: '13w', 26: '26w', 52: '52w'}

    # ── Section 1: forward return summary table ──
    period_header = ''.join(
        f'<th colspan="7" style="text-align:center;border-left:1px solid #30363d;color:#58a6ff">'
        f'{period_labels[p]} Forward</th>'
        for p in PERIODS
    )
    col_header = ''.join(
        '<th>n</th><th>Avg α</th><th>Med α</th><th>Win%</th>'
        '<th>Ret</th><th>SPY</th><th>MaxDD</th>'
        for _ in PERIODS
    )
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

    # ── Section 2: left-tail distribution ──
    THRESH = (-0.20, -0.10, -0.05, 0.0, 0.05, 0.10, 0.20)
    tail_header = '<th>Filter</th>' + ''.join(
        f'<th>α&lt;{int(t*100):+d}%</th>' for t in THRESH
    )
    tail_rows = ''
    dist_order = [
        'A+ quality  +  4/4 fresh entry',
        'A+ quality  +  non-4/4 baseline',
        'B/— quality +  4/4 fresh entry',
        'All tickers +  4/4 fresh entry',
    ]
    for i, label in enumerate(dist_order):
        d = dist_data.get(label)
        sep = ' class="sep"' if i == 1 else ''
        tail_rows += f'<tr{sep}><td>{label}</td>'
        for t in THRESH:
            tail_rows += _tail_cell(d.get(t) if d else None, t)
        tail_rows += '</tr>\n'

    # key insight: compare A+ 4/4 vs A+ non-4/4 at <-10%
    d44   = dist_data.get('A+ quality  +  4/4 fresh entry',   {})
    dbase = dist_data.get('A+ quality  +  non-4/4 baseline',  {})
    tail_4_4  = d44.get(-0.10, None)
    tail_base = dbase.get(-0.10, None)
    if tail_4_4 is not None and tail_base is not None:
        diff = tail_base - tail_4_4
        if diff > 1:
            tail_insight = (
                f'<div class="insight"><p>4/4 timing cuts the left tail: '
                f'{tail_4_4:.1f}% of A+ 4/4 entries finish with alpha &lt;−10%, '
                f'vs {tail_base:.1f}% for A+ non-4/4 entries — '
                f'<strong>{diff:.1f}pp fewer severe underperformers</strong>.</p>'
                f'<p>The MA alignment filter is doing real work, even when average alpha looks similar.</p></div>'
            )
        elif diff < -1:
            tail_insight = (
                f'<div class="insight" style="border-color:#f85149"><p>A+ non-4/4 has a tighter left tail: '
                f'{tail_base:.1f}% vs {tail_4_4:.1f}% for 4/4 entries below −10% alpha. '
                f'4/4 entries may be chasing momentum and catching reversals.</p></div>'
            )
        else:
            tail_insight = (
                f'<div class="insight" style="border-color:#e3b341"><p>Left tails are similar: '
                f'{tail_4_4:.1f}% (4/4) vs {tail_base:.1f}% (non-4/4) below −10% alpha. '
                f'The MA filter does not materially reduce the worst-case frequency at 13w.</p></div>'
            )
    else:
        tail_insight = ''

    # ── Section 3: volatility regime ──
    vol_rows = ''
    vol_order = [
        ('A+ quality  +  4/4 fresh entry',  'A+ 4/4 fresh'),
        ('A+ quality  +  non-4/4 baseline', 'A+ non-4/4'),
        ('All tickers +  4/4 fresh entry',  'All 4/4'),
    ]
    regime_labels = ['Low   (<15%)', 'Med  (15-25%)', 'High  (>25%)']
    vol_header = '<th>Filter</th>' + ''.join(
        f'<th colspan="3">{r}</th>' for r in regime_labels
    )
    vol_subheader = '<th></th>' + '<th>n%</th><th>Avg α</th><th>Win%</th>' * 3

    for label, short in vol_order:
        vd = vol_data.get(label, {})
        vol_rows += f'<tr><td>{short}</td>'
        for regime in regime_labels:
            rd = vd.get(regime)
            if not rd:
                vol_rows += '<td class="dim">—</td><td class="dim">—</td><td class="dim">—</td>'
            else:
                vol_rows += (
                    f'<td>{rd["entry_pct"]:.0f}%</td>'
                    f'<td>{_c(rd["avg_alpha"])}</td>'
                    f'<td>{_c(rd["win_pct"], fmt="+.0f")}</td>'
                )
        vol_rows += '</tr>\n'

    # vol insight
    aplus_vd = vol_data.get('A+ quality  +  4/4 fresh entry', {})
    base_vd  = vol_data.get('A+ quality  +  non-4/4 baseline', {})
    a44_low  = aplus_vd.get('Low   (<15%)', {}) or {}
    b44_low  = base_vd.get('Low   (<15%)', {}) or {}
    a44_pct  = a44_low.get('entry_pct')
    b44_pct  = b44_low.get('entry_pct')
    if a44_pct is not None and b44_pct is not None:
        diff = a44_pct - b44_pct
        if diff > 8:
            vol_insight = (
                f'<div class="insight"><p>4/4 entries cluster in low-vol environments: '
                f'{a44_pct:.0f}% of A+ 4/4 entries occur when SPY realized vol &lt;15%, '
                f'vs {b44_pct:.0f}% for non-4/4 entries — <strong>{diff:.0f}pp skew toward calm markets</strong>.</p>'
                f'<p>This partially explains similar average alpha: 4/4 is selecting for trending, '
                f'low-vol regimes. On a risk-adjusted basis, 4/4 alpha is higher quality.</p></div>'
            )
        else:
            vol_insight = (
                f'<div class="insight" style="border-color:#e3b341"><p>Vol regime distribution is similar: '
                f'{a44_pct:.0f}% (4/4) vs {b44_pct:.0f}% (non-4/4) of entries in low-vol periods. '
                f'The MA filter is not systematically selecting calmer market environments.</p></div>'
            )
    else:
        vol_insight = ''

    # ── grade breakdown ──
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
            '<p style="color:#484f58;font-size:10px">Excluded (insufficient history): '
            + ', '.join(sorted(warned_tickers)) + '</p>'
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
<div class="sub">5-year weekly · {universe_n} tickers · {now} · <a href="index.html">← Market Tools</a></div>

<div class="warn">
  <p>⚠ Documented limitations</p>
  <p>1. <strong>Survivorship bias</strong>: current universe only; delisted/failed names excluded → overstates returns</p>
  <p>2. <strong>Quality look-ahead bias</strong>: current A+/A grades used as historical proxy</p>
  <p>3. <strong>No transaction costs</strong> included. Structural 4/4 MA signal is fully historical and bias-free.</p>
</div>

<h2>1 · Forward Return Summary</h2>
<p style="color:#8b949e;font-size:11px">
  <strong style="color:#e6edf3">Fresh entry</strong> = first 4/4 week after ≥1 non-4/4 week.
  <strong style="color:#e6edf3">Non-4/4 baseline</strong> = A+ names during non-aligned weeks, sampled every 13w.
  Alpha = ticker − SPY over same window. Win% = % entries beating SPY.
</p>
<div style="overflow-x:auto">
<table>
<thead>
<tr>
  <th rowspan="2" style="text-align:left;vertical-align:bottom">Filter</th>
  {period_header}
</tr>
<tr>{col_header}</tr>
</thead>
<tbody>{rows_html}</tbody>
</table>
</div>
<div class="legend">
  <span>α = alpha vs SPY · Med α = median alpha (less skewed by outliers)</span>
  <span>Win% = % beating SPY · MaxDD = avg max drawdown during hold</span>
  <span><span class="pos">green</span> positive · <span class="neg">red</span> negative · <span class="neu">yellow</span> flat</span>
</div>

<h2>2 · Left-Tail Distribution — 13w Alpha</h2>
<p style="color:#8b949e;font-size:11px">
  % of entries finishing below each alpha threshold at 13 weeks.
  Lower % in the left columns = fewer bad outcomes = tighter left tail.
  <strong style="color:#e6edf3">Key question: does 4/4 reduce the &lt;−10% tail vs non-4/4?</strong>
</p>
<table>
<thead><tr>{tail_header}</tr></thead>
<tbody>{tail_rows}</tbody>
</table>
{tail_insight}

<h2>3 · Volatility Regime at Entry — 13w</h2>
<p style="color:#8b949e;font-size:11px">
  SPY 13-week rolling annualized realized vol at the week of entry.
  <strong style="color:#e6edf3">Key question: does 4/4 systematically enter during calmer (low-vol) periods?</strong>
  If yes, similar average alpha to non-4/4 is actually better on a risk-adjusted basis.
  n% = share of entries in this vol regime.
</p>
<table>
<thead>
<tr>{vol_header}</tr>
<tr>{vol_subheader}</tr>
</thead>
<tbody>{vol_rows}</tbody>
</table>
{vol_insight}

<h2>Quality Grade Breakdown</h2>
{grade_breakdown}

<h2>Methodology</h2>
<p><strong style="color:#e6edf3">4/4 alignment</strong>: price &gt; SMA10w, SMA20w, SMA43w (10-month), SMA87w (20-month) — identical to live screener.</p>
<p><strong style="color:#e6edf3">Realized vol</strong>: SPY 13-week rolling std of weekly returns × √52 (annualized). Computed from same 5-year price history.</p>
<p><strong style="color:#e6edf3">Vol regimes</strong>: Low &lt;15% (calm/trending), Medium 15-25% (normal), High &gt;25% (elevated/crisis).</p>
<p><strong style="color:#e6edf3">Non-4/4 baseline</strong>: weeks when A+ tickers are NOT 4/4 aligned, sampled every 13w to reduce autocorrelation. Tests whether MA timing adds value beyond quality alone.</p>
{warned_html}

<p style="color:#484f58;font-size:10px;margin-top:32px;border-top:1px solid #21262d;padding-top:12px">
  Educational framework validation only. Not financial advice.
  Past backtest results do not predict future performance.
</p>
</body>
</html>"""


# ── main ──────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    now = datetime.now(timezone.utc).strftime('%b %d %Y  %H:%M UTC')
    print(f"\n  Backtest — 4/4 MA Alignment Framework  ({now})")

    # Grades
    grade_path = os.path.join(REPO, 'grades_cache.json')
    grade_map  = {}
    if os.path.exists(grade_path):
        with open(grade_path) as f:
            grade_map = json.load(f)

    # SPY benchmark + realized vol
    print(f"  Fetching SPY benchmark ...")
    _, spy_hist = _fetch('SPY')
    if spy_hist is None:
        print("  ERROR: could not fetch SPY"); raise SystemExit(1)
    spy_close = spy_hist['Close']
    # 13w rolling annualized realized vol
    spy_vol = spy_close.pct_change().rolling(13).std() * np.sqrt(52)

    # All tickers
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

    print(f"  Loaded: {len(price_data)} tickers  ({len(warned_tickers)} skipped)")

    # Grade display
    tickers_by_grade = {'A+': [], 'A': [], 'B': [], '—': []}
    for t in TICKERS:
        g = grade_map.get(t, '—')
        tickers_by_grade[g if g in tickers_by_grade else '—'].append(t)

    # Collect entries
    bucket_keys = ('A+', 'A', 'B/—', 'All 4/4', 'A+ non-4/4')
    buckets = {k: {p: [] for p in PERIODS} for k in bucket_keys}

    for ticker, close in price_data.items():
        aligned = compute_alignment(close)
        grade   = grade_map.get(ticker, '—')
        blabel  = 'A+' if grade == 'A+' else ('A' if grade == 'A' else 'B/—')

        for idx in fresh_entries(aligned):
            for p in PERIODS:
                r = measure(close, spy_close, spy_vol, idx, p)
                if r:
                    buckets[blabel][p].append(r)
                    buckets['All 4/4'][p].append(r)

        if grade == 'A+':
            for idx in non_4_4_samples(aligned):
                for p in PERIODS:
                    r = measure(close, spy_close, spy_vol, idx, p)
                    if r:
                        buckets['A+ non-4/4'][p].append(r)

    print(f"  Processed {len(price_data)} tickers")

    # Aggregate stats
    stats_labels = [
        ('A+ quality  +  4/4 fresh entry',  'A+'),
        ('A quality   +  4/4 fresh entry',  'A'),
        ('B/— quality +  4/4 fresh entry',  'B/—'),
        ('All tickers +  4/4 fresh entry',  'All 4/4'),
        ('A+ quality  +  non-4/4 baseline', 'A+ non-4/4'),
    ]
    stats = {}
    for label, bkey in stats_labels:
        stats[label] = {p: agg(buckets[bkey][p]) for p in PERIODS}

    # Left-tail distributions (13w only)
    dist_data = {}
    for label, bkey in stats_labels:
        dist_data[label] = left_tail_dist(buckets[bkey][13])

    # Vol regime analysis (13w only)
    vol_data = {}
    for label, bkey in stats_labels:
        vol_data[label] = vol_regime_stats(buckets[bkey][13])

    # ── CLI output ──
    print(f"\n  13w FORWARD RETURN SUMMARY")
    print(f"  {'Filter':<42}  {'n':>5}  {'Win%':>6}  {'Avg α':>7}  {'Med α':>7}  {'Avg Ret':>8}  {'MaxDD':>7}")
    print(f"  {'─'*42}  {'─'*5}  {'─'*6}  {'─'*7}  {'─'*7}  {'─'*8}  {'─'*7}")
    for label, bkey in stats_labels:
        d = stats[label].get(13)
        if d:
            note = '  ←── baseline' if 'non-4/4' in label else ''
            print(f"  {label:<42}  {d['n']:>5}  {d['win_pct']:>5.1f}%"
                  f"  {d['avg_alpha']:>+6.1f}%  {d['med_alpha']:>+6.1f}%"
                  f"  {d['avg_ret']:>+7.1f}%  {d['avg_dd']:>+6.1f}%{note}")

    print(f"\n  13w LEFT-TAIL DISTRIBUTION  (% of entries with alpha below threshold)")
    THRESH = (-0.20, -0.10, -0.05, 0.0)
    hdr = f"  {'Filter':<42}" + ''.join(f"  {'<'+str(int(t*100))+'%':>7}" for t in THRESH)
    print(hdr)
    print(f"  {'─'*42}" + '  ─────'*len(THRESH))
    for label, bkey in stats_labels:
        d = dist_data.get(label)
        if d:
            row = f"  {label:<42}"
            for t in THRESH:
                row += f"  {d.get(t, 0):>6.1f}%"
            print(row)

    print(f"\n  13w VOL REGIME AT ENTRY  (SPY 13w annualized realized vol)")
    for label, bkey in stats_labels[:1] + stats_labels[-1:]:  # A+ 4/4 + A+ non-4/4
        vd = vol_data.get(label, {})
        print(f"\n  {label}")
        for regime in ['Low   (<15%)', 'Med  (15-25%)', 'High  (>25%)']:
            rd = vd.get(regime)
            if rd:
                print(f"    {regime}  n={rd['n']:>4} ({rd['entry_pct']:>4.0f}%)  "
                      f"avg α={rd['avg_alpha']:>+5.1f}%  win%={rd['win_pct']:>4.0f}%")

    # HTML + push
    html = build_html(stats, dist_data, vol_data, now, tickers_by_grade,
                      len(price_data), warned_tickers)
    out  = os.path.join(REPO, 'backtest.html')
    with open(out, 'w') as f:
        f.write(html)
    print(f"\n  Saved → {out}")

    try:
        subprocess.run(['git', '-C', REPO, 'add', 'backtest.html', 'backtest.py'], check=True)
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
