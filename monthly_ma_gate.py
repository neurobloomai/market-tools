"""
monthly_ma_gate.py — Pre-recovery Monthly MA Gate Screen

On-demand only. Run it just before or early in a recovery cycle to catch
names hovering at their long-term monthly moving average floors.

Tier 1  ±2%   On the gate     — imminent decision point, price testing MA
Tier 2  ±5%   In the zone     — approaching the gate, watch for resolution

MA definitions (weekly bars):
  10m SMA = 43-week SMA   (~10 months)
  20m SMA = 87-week SMA   (~20 months)

◎ = closest distance is to 10mSMA
→ = closest distance is to 20mSMA

Covers:
  US  — universe + watchlist + cyclicals + special mention
  India — universe + watchlist

Run:  python3 monthly_ma_gate.py
Out:  monthly_ma_gate.html  (same directory)
"""

import yfinance as yf, warnings, os, subprocess
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
warnings.filterwarnings('ignore')

# ── pull ticker lists from existing modules ───────────────────────────────────
from screener import UNIVERSE, WATCHLIST
from aligned_screener import CYCLICALS, SPECIAL_MENTION, EXTRA, TICKERS as _us_all
from india_aligned_screener import TICKERS as _india_all

US_TICKERS     = _us_all
INDIA_TICKERS  = _india_all

# ── fetch ─────────────────────────────────────────────────────────────────────

def _fetch(ticker):
    try:
        hist  = yf.Ticker(ticker).history(period='2y', interval='1wk')
        close = hist['Close'].dropna()
        if len(close) < 43:
            return None
        price  = float(close.iloc[-1])
        ma10m  = float(close.tail(43).mean())
        ma20m  = float(close.tail(87).mean()) if len(close) >= 87 else float(close.mean())
        vs10m  = (price - ma10m) / ma10m * 100
        vs20m  = (price - ma20m) / ma20m * 100
        best   = min(abs(vs10m), abs(vs20m))
        span   = abs(vs10m) + abs(vs20m)   # sum of both distances — lower = more sandwiched
        closer = '10m' if abs(vs10m) <= abs(vs20m) else '20m'
        return dict(ticker=ticker, price=price,
                    ma10m=ma10m, ma20m=ma20m,
                    vs10m=vs10m, vs20m=vs20m,
                    best=best, span=span, closer=closer)
    except Exception:
        return None


def _screen(tickers):
    results = []
    with ThreadPoolExecutor(max_workers=20) as ex:
        for r in ex.map(_fetch, tickers):
            if r:
                results.append(r)
    tier1 = sorted([r for r in results if r['best'] <= 2.0], key=lambda r: r['span'])
    tier2 = sorted([r for r in results if 2.0 < r['best'] <= 5.0], key=lambda r: r['span'])
    return tier1, tier2, len(results)


# ── CLI output ────────────────────────────────────────────────────────────────

def _print_table(rows, header, currency):
    print(f"\n  {header}")
    if not rows:
        print("  (none)")
        return
    print(f"  {'Ticker':<14} {'Price':>10}   {'10mSMA':>10}   {'vs10m':>7}   {'20mSMA':>10}   {'vs20m':>7}   {'nearest':>7}   {'span':>6}")
    print(f"  {'-'*92}")
    for r in rows:
        sym   = '◎' if r['closer'] == '10m' else '→'
        s_tag = '●' if r['span'] <= 3.0 else ('○' if r['span'] <= 7.0 else ' ')
        print(
            f"  {sym} {r['ticker']:<12} {currency}{r['price']:>10,.2f}"
            f"   {currency}{r['ma10m']:>10,.2f}  {r['vs10m']:>+7.1f}%"
            f"   {currency}{r['ma20m']:>10,.2f}  {r['vs20m']:>+7.1f}%"
            f"   {r['best']:>5.1f}%"
            f"   {s_tag}{r['span']:>4.1f}%"
        )


def _print_section(label, tier1, tier2, n_total, currency):
    sep = '=' * 74
    print(f"\n  {sep}")
    print(f"  {label}  ({n_total} screened)")
    print(f"  {sep}")
    _print_table(tier1, f"TIER 1 — On the gate  (±2% of 10m or 20mSMA)  [{len(tier1)} names]", currency)
    _print_table(tier2, f"TIER 2 — In the zone  (±5% of 10m or 20mSMA)  [{len(tier2)} names]", currency)


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
  .gi-key{color:#e6edf3;font-weight:700;min-width:90px;flex-shrink:0}
  .gi-val{color:#8b949e;line-height:1.5}
  .guide-home{float:right;color:#58a6ff;font-size:10px;text-decoration:none}
  .section-break{border:none;border-top:1px solid #21262d;margin:32px 0}
"""


def _c_vs(v):
    if v >= 1.5:   return '#3fb950'
    if v >= 0:     return '#57ab5a'
    if v >= -1.5:  return '#e3b341'
    return '#f85149'


def _c_span(span):
    if span <= 2.0:  return '#3fb950'   # both MAs very tight — sandwiched
    if span <= 4.0:  return '#e3b341'   # building toward sandwich
    return '#8b949e'                    # only one side close


def _span_dot(span):
    if span <= 3.0:  return '● '
    if span <= 7.0:  return '○ '
    return ''


def _html_table(rows, currency):
    if not rows:
        return '<div class="none">(none)</div>'
    body = ''
    for r in rows:
        sym   = '◎' if r['closer'] == '10m' else '→'
        p10c  = _c_vs(r['vs10m'])
        p20c  = _c_vs(r['vs20m'])
        bestc = '#3fb950' if r['best'] <= 1.0 else ('#e3b341' if r['best'] <= 3.0 else '#8b949e')
        spanc = _c_span(r['span'])
        dot   = _span_dot(r['span'])
        body += (
            f'<tr>'
            f'<td style="color:#8b949e;font-size:11px">{sym}</td>'
            f'<td class="ticker">{r["ticker"]}</td>'
            f'<td>{currency}{r["price"]:,.2f}</td>'
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
        '<th>10mSMA</th><th>vs 10m</th>'
        '<th>20mSMA</th><th>vs 20m</th>'
        '<th>Nearest</th><th>Span ↑</th>'
        '</tr></thead>'
        f'<tbody>{body}</tbody></table>'
    )


def _html_block(label, color_class, tier1, tier2, currency, n_total):
    t1_html = _html_table(tier1, currency)
    t2_html = _html_table(tier2, currency)
    return f"""
<div class="sh {color_class}">{label} — {n_total} screened</div>
<div class="sh t1" style="font-size:11px;margin-top:12px;margin-bottom:4px">
  Tier 1 — On the gate ±2%&nbsp;&nbsp;<span style="color:#484f58">({len(tier1)} names)</span>
</div>
<div class="sub">Price within ±2% of 10mSMA or 20mSMA — testing the monthly floor right now</div>
{t1_html}
<div class="sh t2" style="font-size:11px;margin-top:16px;margin-bottom:4px">
  Tier 2 — In the zone ±5%&nbsp;&nbsp;<span style="color:#484f58">({len(tier2)} names)</span>
</div>
<div class="sub">Approaching the monthly gate — watch for price to drift into Tier 1</div>
{t2_html}
<div class="legend">Sorted by Span (tightest coil first) &nbsp;·&nbsp; ◎ = closer to 10mSMA &nbsp;·&nbsp; → = closer to 20mSMA &nbsp;·&nbsp;
  green = price above SMA &nbsp;·&nbsp; red = price below SMA &nbsp;·&nbsp;
  Nearest = closest single MA &nbsp;·&nbsp; Span = sum of both distances — ● &lt;3% sandwiched &nbsp;○ &lt;7% building</div>
"""


def build_html(us_t1, us_t2, us_n, ind_t1, ind_t2, ind_n, now):
    us_block    = _html_block('US Universe', 'us',    us_t1,  us_t2,  '$', us_n)
    india_block = _html_block('India Universe', 'india', ind_t1, ind_t2, '₹', ind_n)
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<title>Monthly MA Gate — {now}</title><style>{_CSS}</style></head><body>
<h1>Monthly MA Gate <a class="guide-home" href="index.html">← Home</a></h1>
<div class="meta">{now} · on-demand · pre-recovery / early-recovery screen</div>

<details class="guide">
  <summary>How to read this screen</summary>
  <div class="guide-body">
    <div class="gi"><span class="gi-key">Tier 1 ±2%</span><span class="gi-val">Price is on the gate — sitting within 2% of the 10-month or 20-month SMA. A decision point: either breaks through and starts recovering, or gets rejected back down.</span></div>
    <div class="gi"><span class="gi-key">Tier 2 ±5%</span><span class="gi-val">In the zone — price approaching the monthly MA gate. Watch for it to drift into Tier 1 as the next stage.</span></div>
    <div class="gi"><span class="gi-key">10mSMA</span><span class="gi-val">43-week simple moving average. First recovery gate. Reclaiming this is the initial sign that structure is rebuilding.</span></div>
    <div class="gi"><span class="gi-key">20mSMA</span><span class="gi-val">87-week simple moving average. Long-term floor. Strong support when price is below 10m. Can also act as ceiling on the way back up.</span></div>
    <div class="gi"><span class="gi-key">◎ vs →</span><span class="gi-val">◎ = price is closer to 10mSMA · → = price is closer to 20mSMA. Tells you which gate is the immediate test.</span></div>
    <div class="gi"><span class="gi-key">vs 10m / vs 20m</span><span class="gi-val">Green = price above that SMA. Red = price below. A name can be above one and below the other — that's the gate zone.</span></div>
    <div class="gi"><span class="gi-key">Span (sort key)</span><span class="gi-val">Sum of distances to both MAs. Low span = price sandwiched between 10m and 20m — both acting as guardrails simultaneously. ● &lt;3% = tightest coil. Sorted ascending so best setups surface first.</span></div>
    <div class="gi"><span class="gi-key">When to use</span><span class="gi-val">Run this screen just before or early in a recovery. Low-span names are the most compressed — energy building between two long-term moving averages waiting for a directional break.</span></div>
    <div class="gi"><span class="gi-key">No stack needed</span><span class="gi-val">10m and 20m don't need to be stacked. This screen is about proximity to the gate, not full alignment. Full alignment shows up in the aligned screener once price reclaims both.</span></div>
  </div>
</details>

<div class="summary">
  <div class="stat"><div class="stat-val" style="color:#3fb950">{len(us_t1)}</div><div class="stat-lbl">US Tier 1 (±2%)</div></div>
  <div class="stat"><div class="stat-val" style="color:#e3b341">{len(us_t2)}</div><div class="stat-lbl">US Tier 2 (±5%)</div></div>
  <div class="stat"><div class="stat-val" style="color:#bc8cff">{len(ind_t1)}</div><div class="stat-lbl">India Tier 1 (±2%)</div></div>
  <div class="stat"><div class="stat-val" style="color:#bc8cff;opacity:.7">{len(ind_t2)}</div><div class="stat-lbl">India Tier 2 (±5%)</div></div>
</div>

{us_block}
<hr class="section-break">
{india_block}

</body></html>"""


# ── main ──────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    now = datetime.now(timezone.utc).strftime('%b %d %Y  %H:%M UTC')
    repo = os.path.dirname(os.path.abspath(__file__))

    print(f"\n  Monthly MA Gate — {now}")
    print(f"  Fetching US ({len(US_TICKERS)} tickers) ...")
    us_t1, us_t2, us_n = _screen(US_TICKERS)

    print(f"  Fetching India ({len(INDIA_TICKERS)} tickers) ...")
    ind_t1, ind_t2, ind_n = _screen(INDIA_TICKERS)

    # CLI
    _print_section('US Universe + Watchlist + Cyclicals + Special Mention', us_t1, us_t2, us_n, '$')
    _print_section('India Universe + Watchlist', ind_t1, ind_t2, ind_n, '₹')

    print(f"\n  US   — {us_n} screened  |  Tier1: {len(us_t1)}  |  Tier2: {len(us_t2)}")
    print(f"  India — {ind_n} screened  |  Tier1: {len(ind_t1)}  |  Tier2: {len(ind_t2)}")

    # HTML
    html     = build_html(us_t1, us_t2, us_n, ind_t1, ind_t2, ind_n, now)
    out_path = os.path.join(repo, 'monthly_ma_gate.html')
    with open(out_path, 'w') as f:
        f.write(html)
    print(f"\n  Saved → {out_path}")
