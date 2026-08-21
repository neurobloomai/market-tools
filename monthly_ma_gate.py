"""
monthly_ma_gate.py — Pre-recovery Monthly MA Gate Screen

On-demand only. Run it just before or early in a recovery cycle to catch
names hovering at their long-term monthly moving average floors.

MA definitions (weekly bars):
  6m  SMA = 26-week SMA   (~6 months)
  10m SMA = 43-week SMA   (~10 months)
  20m SMA = 87-week SMA   (~20 months)

Stack tiers:
  GREEN  — Fully Stacked:  price > 6m > 10m > 20m  (already recovering)
  YELLOW — Building:       6m > 10m > 20m, price > 10m but < 6m  (one step away)
  Tier 1 — On the gate:    price within ±2% of 10m or 20m
  Tier 2 — In the zone:    price within ±5% of 10m or 20m

◎ = closest distance is to 10mSMA
→ = closest distance is to 20mSMA

Run:  python monthly_ma_gate.py
Out:  monthly_ma_gate.html  (opens in browser automatically)
"""

import _yf_cache  # noqa: F401 — install HTTP cache before yfinance fetches
import yfinance as yf, warnings, os, subprocess, webbrowser
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
warnings.filterwarnings('ignore')

from screener import UNIVERSE, WATCHLIST
from aligned_screener import CYCLICALS, SPECIAL_MENTION, EXTRA, TICKERS as _us_all
from india_aligned_screener import TICKERS as _india_all

US_TICKERS    = _us_all
INDIA_TICKERS = _india_all


# ── fetch ─────────────────────────────────────────────────────────────────────

def _fetch(ticker):
    try:
        hist  = yf.Ticker(ticker).history(period='2y', interval='1wk')
        close = hist['Close'].dropna()
        if len(close) < 43:
            return None
        price = float(close.iloc[-1])
        ma6m  = float(close.tail(26).mean())
        ma10m = float(close.tail(43).mean())
        ma20m = float(close.tail(87).mean()) if len(close) >= 87 else float(close.mean())
        vs6m  = (price - ma6m)  / ma6m  * 100
        vs10m = (price - ma10m) / ma10m * 100
        vs20m = (price - ma20m) / ma20m * 100
        best  = min(abs(vs10m), abs(vs20m))
        span  = abs(vs10m) + abs(vs20m)
        closer = '10m' if abs(vs10m) <= abs(vs20m) else '20m'

        fully_stacked = price > ma6m > ma10m > ma20m
        building      = (ma6m > ma10m > ma20m) and (price > ma10m) and (price < ma6m)

        return dict(ticker=ticker, price=price,
                    ma6m=ma6m, ma10m=ma10m, ma20m=ma20m,
                    vs6m=vs6m, vs10m=vs10m, vs20m=vs20m,
                    best=best, span=span, closer=closer,
                    fully_stacked=fully_stacked, building=building)
    except Exception:
        return None


def _screen(tickers):
    results = []
    with ThreadPoolExecutor(max_workers=20) as ex:
        for r in ex.map(_fetch, tickers):
            if r:
                results.append(r)

    fully_stacked = sorted([r for r in results if r['fully_stacked']],
                           key=lambda r: r['vs6m'])          # closest to 6m first
    tier1 = sorted([r for r in results if not r['fully_stacked'] and r['best'] <= 2.0],
                   key=lambda r: r['span'])
    tier2 = sorted([r for r in results if not r['fully_stacked'] and 2.0 < r['best'] <= 5.0],
                   key=lambda r: r['span'])
    return fully_stacked, tier1, tier2, len(results)


# ── HTML ──────────────────────────────────────────────────────────────────────

_CSS = """
  *{box-sizing:border-box;margin:0;padding:0}
  body{background:#0d1117;color:#e6edf3;font-family:'SF Mono','Fira Code',monospace;font-size:13px;padding:28px 32px}
  h1{font-size:18px;font-weight:600;margin-bottom:4px}
  .meta{color:#8b949e;font-size:12px;margin-bottom:24px}
  .summary{display:flex;gap:16px;flex-wrap:wrap;margin-bottom:28px}
  .stat{background:#161b22;border:1px solid #21262d;border-radius:8px;padding:12px 20px}
  .stat-val{font-size:22px;font-weight:600}
  .stat-lbl{font-size:11px;color:#8b949e;margin-top:2px}
  .sh{font-size:12px;font-weight:600;margin:28px 0 6px;text-transform:uppercase;letter-spacing:.04em}
  .sh.us{color:#58a6ff}
  .sh.india{color:#bc8cff}
  .sh.t-green{color:#3fb950}
  .sh.t-yellow{color:#e3b341}
  .sh.t1{color:#3fb950}
  .sh.t2{color:#e3b341}
  .sub{color:#8b949e;font-size:11px;margin-bottom:10px}
  table{border-collapse:collapse;width:100%;margin-bottom:4px}
  th{color:#8b949e;font-weight:400;font-size:11px;text-align:left;padding:4px 12px 6px 8px;border-bottom:1px solid #21262d;white-space:nowrap}
  td{padding:5px 12px 5px 8px;border-bottom:1px solid #161b22;white-space:nowrap}
  tr:hover td{background:#161b22}
  .ticker{font-weight:600;color:#e6edf3}
  .legend{color:#8b949e;font-size:11px;margin-top:8px;margin-bottom:24px}
  .none{color:#484f58;font-size:12px;padding:10px 8px}
  details.guide{background:#161b22;border:1px solid #21262d;border-radius:6px;margin-bottom:18px;font-size:11px}
  details.guide summary{padding:8px 14px;cursor:pointer;color:#8b949e;user-select:none;list-style:none}
  details.guide summary::before{content:'▶ ';font-size:9px}
  details[open].guide summary::before{content:'▼ ';font-size:9px}
  details.guide .guide-body{padding:12px 16px 14px;border-top:1px solid #21262d;display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:8px 24px}
  .gi{display:flex;gap:8px;align-items:baseline}
  .gi-key{color:#e6edf3;font-weight:700;min-width:110px;flex-shrink:0}
  .gi-val{color:#8b949e;line-height:1.5}
  .guide-home{float:right;color:#58a6ff;font-size:10px;text-decoration:none}
  .section-break{border:none;border-top:1px solid #21262d;margin:32px 0}
  tr.row-green td{background:rgba(63,185,80,0.08);}
  tr.row-green td:first-child{border-left:3px solid #3fb950;}
  tr.row-green:hover td{background:rgba(63,185,80,0.14);}
  tr.row-yellow td{background:rgba(227,179,65,0.07);}
  tr.row-yellow td:first-child{border-left:3px solid #e3b341;}
  tr.row-yellow:hover td{background:rgba(227,179,65,0.13);}
"""


def _c_vs(v):
    if v >= 1.5:  return '#3fb950'
    if v >= 0:    return '#57ab5a'
    if v >= -1.5: return '#e3b341'
    return '#f85149'


def _c_vs20m_ext(v):
    """Color for vs20m in the fully-stacked table — higher = more extended = more LT risk."""
    if v < 15:  return '#3fb950'   # healthy — room to run
    if v < 30:  return '#e3b341'   # mild extension — watch
    if v < 50:  return '#f0883e'   # high extension — caution
    return '#f85149'               # extreme — LT danger zone


def _c_span(span):
    if span <= 2.0: return '#3fb950'
    if span <= 4.0: return '#e3b341'
    return '#8b949e'


def _span_dot(span):
    if span <= 3.0: return '● '
    if span <= 7.0: return '○ '
    return ''


def _html_table(rows, currency, show_stack_colors=False):
    if not rows:
        return '<div class="none">(none)</div>'
    body = ''
    for r in rows:
        sym   = '◎' if r['closer'] == '10m' else '→'
        p6c   = _c_vs(r['vs6m'])
        p10c  = _c_vs(r['vs10m'])
        p20c  = _c_vs(r['vs20m'])
        bestc = '#3fb950' if r['best'] <= 1.0 else ('#e3b341' if r['best'] <= 3.0 else '#8b949e')
        spanc = _c_span(r['span'])
        dot   = _span_dot(r['span'])

        if show_stack_colors:
            if r['fully_stacked']:
                row_cls = ' class="row-green"'
            elif r['building']:
                row_cls = ' class="row-yellow"'
            else:
                row_cls = ''
        else:
            row_cls = ''

        body += (
            f'<tr{row_cls}>'
            f'<td style="color:#8b949e;font-size:11px">{sym}</td>'
            f'<td class="ticker">{r["ticker"]}</td>'
            f'<td>{currency}{r["price"]:,.2f}</td>'
            f'<td style="color:#8b949e">{currency}{r["ma6m"]:,.2f}</td>'
            f'<td style="color:{p6c}">{r["vs6m"]:+.1f}%</td>'
            f'<td>{currency}{r["ma10m"]:,.2f}</td>'
            f'<td style="color:{p10c}">{r["vs10m"]:+.1f}%</td>'
            f'<td>{currency}{r["ma20m"]:,.2f}</td>'
            f'<td style="color:{p20c}">{r["vs20m"]:+.1f}%</td>'
            f'<td style="color:{bestc}">{r["best"]:.1f}%</td>'
            f'<td style="color:{spanc};font-weight:600">{dot}{r["span"]:.1f}%</td>'
            f'</tr>'
        )
    return (
        '<table><thead><tr>'
        '<th></th><th>Ticker</th><th>Price</th>'
        '<th>6mSMA</th><th>vs 6m</th>'
        '<th>10mSMA</th><th>vs 10m</th>'
        '<th>20mSMA</th><th>vs 20m</th>'
        '<th>Nearest</th><th>Span ↑</th>'
        '</tr></thead>'
        f'<tbody>{body}</tbody></table>'
    )


def _html_stacked_table(rows, currency):
    """Dedicated table for fully-stacked names — sorted closest to 6m first."""
    if not rows:
        return '<div class="none">(none)</div>'
    body = ''
    for r in rows:
        p6c  = _c_vs(r['vs6m'])
        p10c = _c_vs(r['vs10m'])
        p20c = _c_vs20m_ext(r['vs20m'])
        body += (
            f'<tr class="row-green">'
            f'<td class="ticker">{r["ticker"]}</td>'
            f'<td>{currency}{r["price"]:,.2f}</td>'
            f'<td style="color:#8b949e">{currency}{r["ma6m"]:,.2f}</td>'
            f'<td style="color:{p6c}">{r["vs6m"]:+.1f}%</td>'
            f'<td>{currency}{r["ma10m"]:,.2f}</td>'
            f'<td style="color:{p10c}">{r["vs10m"]:+.1f}%</td>'
            f'<td>{currency}{r["ma20m"]:,.2f}</td>'
            f'<td style="color:{p20c};font-weight:600">{r["vs20m"]:+.1f}%</td>'
            f'</tr>'
        )
    return (
        '<table><thead><tr>'
        '<th>Ticker</th><th>Price</th>'
        '<th>6mSMA</th><th>vs 6m</th>'
        '<th>10mSMA</th><th>vs 10m</th>'
        '<th>20mSMA</th><th>vs 20m</th>'
        '</tr></thead>'
        f'<tbody>{body}</tbody></table>'
    )


def _html_block(label, color_class, stacked, tier1, tier2, currency, n_total):
    stacked_html = _html_stacked_table(stacked, currency)
    t1_html      = _html_table(tier1, currency, show_stack_colors=True)
    t2_html      = _html_table(tier2, currency, show_stack_colors=True)
    return f"""
<div class="sh {color_class}">{label} — {n_total} screened</div>

<div class="sh t-green" style="font-size:11px;margin-top:12px;margin-bottom:4px">
  ■ Fully Stacked &nbsp;<span style="color:#484f58">price &gt; 6m &gt; 10m &gt; 20m &nbsp;({len(stacked)} names)</span>
</div>
<div class="sub">All three MAs ascending with price on top — structure already recovering. Sorted by vs 6m (closest first). &nbsp;<span style="color:#3fb950">vs 20m &lt;15% healthy</span> · <span style="color:#e3b341">&lt;30% mild ext</span> · <span style="color:#f0883e">&lt;50% high ext</span> · <span style="color:#f85149">50%+ LT danger</span></div>
{stacked_html}

<div class="sh t1" style="font-size:11px;margin-top:20px;margin-bottom:4px">
  Tier 1 — On the gate ±2% &nbsp;<span style="color:#484f58">({len(tier1)} names)</span>
</div>
<div class="sub">Price within ±2% of 10mSMA or 20mSMA — testing the monthly floor right now. &nbsp;<span style="color:#e3b341">Yellow = MAs stacked, price between 10m and 6m — one step from green.</span></div>
{t1_html}

<div class="sh t2" style="font-size:11px;margin-top:20px;margin-bottom:4px">
  Tier 2 — In the zone ±5% &nbsp;<span style="color:#484f58">({len(tier2)} names)</span>
</div>
<div class="sub">Approaching the monthly gate — watch for drift into Tier 1.</div>
{t2_html}

<div class="legend">
  Sorted by Span (tightest coil first) &nbsp;·&nbsp; ◎ = closer to 10mSMA &nbsp;·&nbsp; → = closer to 20mSMA &nbsp;·&nbsp;
  green = above SMA &nbsp;·&nbsp; red = below SMA &nbsp;·&nbsp;
  Nearest = closest single MA &nbsp;·&nbsp; Span = sum of 10m+20m distances &nbsp;·&nbsp; ● &lt;3% sandwiched &nbsp;○ &lt;7% building
</div>
"""


def build_html(us_stacked, us_t1, us_t2, us_n,
               ind_stacked, ind_t1, ind_t2, ind_n, now):
    us_block    = _html_block('US Universe', 'us',
                              us_stacked, us_t1, us_t2, '$', us_n)
    india_block = _html_block('India Universe', 'india',
                              ind_stacked, ind_t1, ind_t2, '₹', ind_n)
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<title>Monthly MA Gate — {now}</title><style>{_CSS}</style></head><body>
<h1>Monthly MA Gate <a class="guide-home" href="index.html">← Home</a></h1>
<div class="meta">{now} · on-demand · pre-recovery / early-recovery screen</div>

<details class="guide">
  <summary>How to read this screen</summary>
  <div class="guide-body">
    <div class="gi"><span class="gi-key">■ Green rows</span><span class="gi-val">Fully Stacked — price &gt; 6m &gt; 10m &gt; 20m. All three MAs in ascending order with price on top. Structure is already recovering — not a gate play, a confirmation play.</span></div>
    <div class="gi"><span class="gi-key">■ Yellow rows</span><span class="gi-val">Building — 6m &gt; 10m &gt; 20m (MAs stacked) but price is above 10m and below 6m. One MA reclaim away from fully stacked. Highest-quality Tier 1/2 setups.</span></div>
    <div class="gi"><span class="gi-key">Tier 1 ±2%</span><span class="gi-val">Price within ±2% of 10mSMA or 20mSMA — at the gate. A decision point: either breaks through and recovers, or gets rejected back down.</span></div>
    <div class="gi"><span class="gi-key">Tier 2 ±5%</span><span class="gi-val">In the zone — approaching the monthly MA gate. Watch for drift into Tier 1 as the next stage.</span></div>
    <div class="gi"><span class="gi-key">6mSMA</span><span class="gi-val">26-week SMA (~6 months). The intermediate trend filter. Price crossing above this is the first sign of momentum rebuilding before the longer MAs catch up.</span></div>
    <div class="gi"><span class="gi-key">10mSMA</span><span class="gi-val">43-week SMA. First recovery gate. Reclaiming this is the initial sign that long-term structure is rebuilding.</span></div>
    <div class="gi"><span class="gi-key">20mSMA</span><span class="gi-val">87-week SMA. Long-term floor. Strong support when price is below 10m. Can also act as ceiling on the way back up.</span></div>
    <div class="gi"><span class="gi-key">Span (sort key)</span><span class="gi-val">Sum of distances to 10m and 20m. Low span = price sandwiched between both MAs — energy building. ● &lt;3% tightest coil · ○ &lt;7% building. Sorted ascending so best setups surface first.</span></div>
    <div class="gi"><span class="gi-key">When to use</span><span class="gi-val">Run this just before or early in a recovery cycle. Green = already recovering. Yellow = one step away. Tier 1 = at the gate, watch for resolution.</span></div>
  </div>
</details>

<div class="summary">
  <div class="stat"><div class="stat-val" style="color:#3fb950">{len(us_stacked)}</div><div class="stat-lbl">US Fully Stacked</div></div>
  <div class="stat"><div class="stat-val" style="color:#3fb950;opacity:.7">{len(us_t1)}</div><div class="stat-lbl">US Tier 1 (±2%)</div></div>
  <div class="stat"><div class="stat-val" style="color:#e3b341">{len(us_t2)}</div><div class="stat-lbl">US Tier 2 (±5%)</div></div>
  <div class="stat"><div class="stat-val" style="color:#bc8cff">{len(ind_stacked)}</div><div class="stat-lbl">India Fully Stacked</div></div>
  <div class="stat"><div class="stat-val" style="color:#bc8cff;opacity:.7">{len(ind_t1)}</div><div class="stat-lbl">India Tier 1 (±2%)</div></div>
  <div class="stat"><div class="stat-val" style="color:#bc8cff;opacity:.5">{len(ind_t2)}</div><div class="stat-lbl">India Tier 2 (±5%)</div></div>
</div>

{us_block}
<hr class="section-break">
{india_block}

<p style="color:#484f58;font-size:10px;margin-top:24px;border-top:1px solid #21262d;padding-top:8px">For informational purposes only. Not financial advice. Auto-generated from Yahoo Finance data.</p>
</body></html>"""


# ── main ──────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    now  = datetime.now(timezone.utc).strftime('%b %d %Y  %H:%M UTC')
    repo = os.path.dirname(os.path.abspath(__file__))

    print(f"\n  Monthly MA Gate — {now}")
    print(f"  Fetching US ({len(US_TICKERS)} tickers) ...")
    us_stacked, us_t1, us_t2, us_n = _screen(US_TICKERS)

    print(f"  Fetching India ({len(INDIA_TICKERS)} tickers) ...")
    ind_stacked, ind_t1, ind_t2, ind_n = _screen(INDIA_TICKERS)

    print(f"\n  US    — {us_n} screened  |  Stacked: {len(us_stacked)}  |  Tier1: {len(us_t1)}  |  Tier2: {len(us_t2)}")
    print(f"  India — {ind_n} screened  |  Stacked: {len(ind_stacked)}  |  Tier1: {len(ind_t1)}  |  Tier2: {len(ind_t2)}")

    html     = build_html(us_stacked, us_t1, us_t2, us_n,
                          ind_stacked, ind_t1, ind_t2, ind_n, now)
    out_path = os.path.join(repo, 'monthly_ma_gate.html')
    with open(out_path, 'w') as f:
        f.write(html)
    print(f"\n  Saved → {out_path}")
    webbrowser.open(f'file://{out_path}')

    try:
        subprocess.run(['git', '-C', repo, 'add', 'monthly_ma_gate.html'], check=True)
        result = subprocess.run(['git', '-C', repo, 'diff', '--cached', '--quiet'])
        if result.returncode != 0:
            subprocess.run(['git', '-C', repo, 'commit',
                            '-m', f'monthly_ma_gate: {now}'], check=True)
            subprocess.run(['git', '-C', repo, 'push'], check=True)
            print(f"  Pushed → GitHub  (monthly_ma_gate: {now})")
        else:
            print("  GitHub — no changes to push")
    except subprocess.CalledProcessError as e:
        print(f"  Push failed: {e}")
