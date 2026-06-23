"""
india_aligned_screener.py — 4/4 MA Aligned Names + Weekly Squeeze Scanner (India)
Cross-references India screener universe + watchlist against full MA structure.
Fetches quality grades for aligned names. RS computed vs NIFTY 50.
Run: python india_aligned_screener.py
"""

import yfinance as yf, warnings, os, functools
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
warnings.filterwarnings('ignore')

from india_screener import UNIVERSE, WATCHLIST, get_fundamentals, passes_quality_filter, quality_grade

EXTRA = []

# Special mention — teasing/puzzling setups not yet in alignment
SPECIAL_MENTION = {
    'ETERNAL.NS': 'Eternal (formerly Zomato) — food delivery + quick commerce duopoly; profitability inflecting, FCF turning positive; MA structure not yet complete; wait for full 4/4 alignment and quality filter pass',
    'SWIGGY.NS': 'Food delivery + quick commerce; loss-making but narrowing fast; similar inflection thesis to Zomato; monthly structure building — 12-18 month patience play',
}

TICKERS = list(dict.fromkeys(UNIVERSE + WATCHLIST + EXTRA + list(SPECIAL_MENTION.keys())))

def disp(t):
    return t.replace('.NS', '').replace('.BO', '')

def ma_score(ticker, nifty_13w_ratio=1.0):
    try:
        hist  = yf.Ticker(ticker).history(period='2y', interval='1wk')
        close = hist['Close'].dropna()
        if len(close) < 40:
            return None
        price = float(close.iloc[-1])
        ma10w = float(close.tail(10).mean())
        ma20w = float(close.tail(20).mean())
        ma35w = float(close.tail(35).mean()) if len(close) >= 35 else ma20w
        ma50w = float(close.tail(50).mean()) if len(close) >= 50 else ma20w
        ma10m = float(close.tail(43).mean())
        ma20m = float(close.tail(87).mean()) if len(close) >= 87 else float(close.mean())
        score = sum([price > ma10w, price > ma20w, price > ma10m, price > ma20m])
        wmas  = [ma10w, ma20w, ma35w, ma50w]
        w_spread  = round((max(wmas) - min(wmas)) / price * 100, 2)
        st_spread = round(abs(ma10w - ma20w) / price * 100, 2)
        vol = hist['Volume'].dropna()
        if len(vol) >= 11:
            vol_ratio = round(float(vol.iloc[-2]) / float(vol.iloc[-11:-1].mean()), 2)
        else:
            vol_ratio = None
        slope_up = (float(close.tail(10).mean()) > float(close.iloc[-14:-4].mean())) if len(close) >= 14 else True

        # CMF (Chaikin Money Flow) — 20-week
        cmf = 0.0
        try:
            high = hist['High'].dropna()
            low  = hist['Low'].dropna()
            idx  = close.index.intersection(vol.index).intersection(high.index).intersection(low.index)
            c20  = close.loc[idx].tail(20)
            h20  = high.loc[idx].tail(20)
            l20  = low.loc[idx].tail(20)
            v20  = vol.loc[idx].tail(20)
            hl   = (h20 - l20).replace(0, float('nan'))
            mfm  = ((c20 - l20) - (h20 - c20)) / hl
            mfv  = mfm.fillna(0) * v20
            vol_sum = float(v20.sum())
            cmf  = round(float(mfv.sum()) / vol_sum, 3) if vol_sum > 0 else 0.0
        except:
            cmf = 0.0

        high_52w      = float(close.tail(52).max()) if len(close) >= 52 else float(close.max())
        pct_from_high = round((price - high_52w) / high_52w * 100, 1)

        rs = None
        if nifty_13w_ratio and nifty_13w_ratio != 1.0 and len(close) >= 14:
            stock_13w_ratio = float(close.iloc[-1]) / float(close.iloc[-14])
            rs = round(stock_13w_ratio / nifty_13w_ratio, 2)

        return {
            't': ticker, 'p': round(price, 2), 's': score,
            'w_spread': w_spread, 'st_spread': st_spread,
            'vol_ratio': vol_ratio, 'slope_up': slope_up,
            'cmf': cmf, 'rs': rs, 'pct_from_high': pct_from_high,
            'ma10w': round(ma10w, 2), 'ma20w': round(ma20w, 2),
            'ma35w': round(ma35w, 2), 'ma50w': round(ma50w, 2),
        }
    except:
        return None


def monthly_cmf_trend(ticker, n=6):
    try:
        hist  = yf.Ticker(ticker).history(period='3y', interval='1mo')
        close = hist['Close'].dropna()
        high  = hist['High'].dropna()
        low   = hist['Low'].dropna()
        vol   = hist['Volume'].dropna()
        idx   = close.index.intersection(vol.index).intersection(high.index).intersection(low.index)
        if len(idx) < n * 2:
            return None, None, '→'

        def _cmf(c, h, l, v):
            hl  = (h - l).replace(0, float('nan'))
            mfm = ((c - l) - (h - c)) / hl
            vs  = float(v.sum())
            return round(float((mfm.fillna(0) * v).sum()) / vs, 3) if vs > 0 else 0.0

        c = close.loc[idx]; h = high.loc[idx]; l = low.loc[idx]; v = vol.loc[idx]
        cur   = _cmf(c.iloc[-n:],     h.iloc[-n:],     l.iloc[-n:],     v.iloc[-n:])
        prior = _cmf(c.iloc[-n*2:-n], h.iloc[-n*2:-n], l.iloc[-n*2:-n], v.iloc[-n*2:-n])
        trend = '↑' if cur > prior + 0.05 else ('↓' if cur < prior - 0.05 else '→')
        return cur, prior, trend
    except:
        return None, None, '→'


def grade_ticker(ticker):
    d = get_fundamentals(ticker)
    if d is None:
        return '—'
    if not passes_quality_filter(d):
        return '—'
    return quality_grade(d)


# ── HTML helpers ──────────────────────────────────────────────────────────────

def _c_rs(v):
    if v is None:  return '#8b949e'
    if v >= 1.20:  return '#3fb950'
    if v <  0.80:  return '#f85149'
    return '#e6edf3'

def _c_cmf(v):
    if v >  0.10: return '#3fb950'
    if v < -0.10: return '#d29922'
    return '#8b949e'

def _c_hi(v):
    if v >= -3:  return '#3fb950'
    if v >= -10: return '#e6edf3'
    return '#8b949e'

def _c_grade(g):
    if g == 'A+': return '#3fb950'
    if g == 'A':  return '#58a6ff'
    return '#8b949e'

def _c_ma(s):
    if s == 4: return '#3fb950'
    if s == 3: return '#d29922'
    return '#8b949e'

def _c_trend(arrow):
    if arrow == '↑': return '#3fb950'
    if arrow == '↓': return '#f85149'
    return '#8b949e'


def build_aligned_html(valid, aligned, grades, partial, promos,
                       squeezed, st_squeezed, rs_map, hi_map, cmf_map,
                       special_mention, now, UNIVERSE, WATCHLIST, m_cmf_map=None):

    def src_tag(t):
        return 'U' if t in UNIVERSE else ('W' if t in WATCHLIST else 'X')

    def aligned_row(r, g):
        t    = r['t']
        rs   = rs_map.get(t)
        hi   = hi_map.get(t)
        cmf  = cmf_map.get(t, 0.0)
        rs_s = f'{rs:.2f}x' if rs is not None else '—'
        hi_s = f'{hi:+.1f}%' if hi is not None else '—'
        lag  = ' ↓' if (rs is not None and rs < 0.80) else ''
        return (f'<tr>'
                f'<td style="color:#8b949e;font-size:11px">[{src_tag(t)}]</td>'
                f'<td class="ticker">{disp(t)}</td>'
                f'<td style="color:{_c_grade(g)};font-weight:600">{g}</td>'
                f'<td>₹{r["p"]:,.2f}</td>'
                f'<td style="color:{_c_rs(rs)}">{rs_s}{lag}</td>'
                f'<td style="color:{_c_hi(hi or 0)}">{hi_s}</td>'
                f'<td style="color:{_c_cmf(cmf)}">{cmf:+.2f}</td>'
                f'</tr>')

    def partial_row(r):
        t    = r['t']
        rs   = rs_map.get(t)
        hi   = hi_map.get(t)
        cmf  = cmf_map.get(t, 0.0)
        rs_s = f'{rs:.2f}x' if rs is not None else '—'
        hi_s = f'{hi:+.1f}%' if hi is not None else '—'
        lag  = ' ↓' if (rs is not None and rs < 0.80) else ''
        return (f'<tr>'
                f'<td style="color:#8b949e;font-size:11px">[{src_tag(t)}]</td>'
                f'<td class="ticker">{disp(t)}</td>'
                f'<td style="color:{_c_rs(rs)}">{rs_s}{lag}</td>'
                f'<td style="color:{_c_hi(hi or 0)}">{hi_s}</td>'
                f'<td style="color:{_c_cmf(cmf)}">{cmf:+.2f}</td>'
                f'<td style="color:{_c_ma(r["s"])}">{r["s"]}/4</td>'
                f'<td>₹{r["p"]:,.2f}</td>'
                f'</tr>')

    def squeeze_row(r):
        t     = r['t']
        cmf   = r.get('cmf', 0.0)
        rs    = r.get('rs')
        hi    = r.get('pct_from_high', 0.0)
        vol_s = f'{r["vol_ratio"]:.1f}x' if r.get('vol_ratio') is not None else '—'
        slp   = '↑' if r.get('slope_up') else '↓'
        flag  = '●' if r['w_spread'] < 3.0 else ('○' if r['w_spread'] < 5.0 else '')
        rs_s  = f'{rs:.2f}x' if rs is not None else '—'
        lag   = ' ↓' if (rs is not None and rs < 0.80) else ''
        return (f'<tr>'
                f'<td class="ticker">{disp(t)}</td>'
                f'<td style="color:#8b949e;font-size:11px">[{src_tag(t)}]</td>'
                f'<td style="color:{_c_ma(r["s"])}">{r["s"]}/4</td>'
                f'<td>₹{r["p"]:,.2f}</td>'
                f'<td>{flag} {r["w_spread"]:.1f}%</td>'
                f'<td>{vol_s}</td><td>{slp}</td>'
                f'<td style="color:{_c_cmf(cmf)}">{cmf:+.2f}</td>'
                f'<td style="color:{_c_rs(rs)}">{rs_s}{lag}</td>'
                f'<td style="color:{_c_hi(hi)}">{hi:+.1f}%</td>'
                f'<td style="color:#484f58;font-size:11px">₹{r["ma10w"]:,.2f}</td>'
                f'<td style="color:#484f58;font-size:11px">₹{r["ma20w"]:,.2f}</td>'
                f'<td style="color:#484f58;font-size:11px">₹{r["ma35w"]:,.2f}</td>'
                f'<td style="color:#484f58;font-size:11px">₹{r["ma50w"]:,.2f}</td>'
                f'</tr>')

    def st_row(r):
        t     = r['t']
        cmf   = r.get('cmf', 0.0)
        rs    = r.get('rs')
        hi    = r.get('pct_from_high', 0.0)
        vol_s = f'{r["vol_ratio"]:.1f}x' if r.get('vol_ratio') is not None else '—'
        slp   = '↑' if r.get('slope_up') else '↓'
        flag  = '●' if r['st_spread'] < 2.0 else ('○' if r['st_spread'] < 4.0 else '')
        rs_s  = f'{rs:.2f}x' if rs is not None else '—'
        lag   = ' ↓' if (rs is not None and rs < 0.80) else ''
        return (f'<tr>'
                f'<td class="ticker">{disp(t)}</td>'
                f'<td style="color:#8b949e;font-size:11px">[{src_tag(t)}]</td>'
                f'<td style="color:{_c_ma(r["s"])}">{r["s"]}/4</td>'
                f'<td>₹{r["p"]:,.2f}</td>'
                f'<td>{flag} {r["st_spread"]:.1f}%</td>'
                f'<td>{vol_s}</td><td>{slp}</td>'
                f'<td style="color:{_c_cmf(cmf)}">{cmf:+.2f}</td>'
                f'<td style="color:{_c_rs(rs)}">{rs_s}{lag}</td>'
                f'<td style="color:{_c_hi(hi)}">{hi:+.1f}%</td>'
                f'<td style="color:#484f58;font-size:11px">₹{r["ma10w"]:,.2f}</td>'
                f'<td style="color:#484f58;font-size:11px">₹{r["ma20w"]:,.2f}</td>'
                f'<td style="color:{_c_ma(r["s"])}">{r["w_spread"]:.1f}%</td>'
                f'</tr>')

    aligned_rows = ''
    for label, subset in [('A+ — structure + quality', [(r,g) for r,g in zip(aligned,grades) if g=='A+']),
                           ('A — structure + quality',  [(r,g) for r,g in zip(aligned,grades) if g=='A']),
                           ('Watchlist / not yet qualifying', [(r,g) for r,g in zip(aligned,grades) if g=='—'])]:
        if subset:
            aligned_rows += f'<tr class="grp"><td colspan="7">{label}</td></tr>'
            for r, g in sorted(subset, key=lambda x: disp(x[0]['t'])):
                aligned_rows += aligned_row(r, g)

    partial_rows = ''.join(partial_row(r) for r in partial)
    squeeze_rows = ''.join(squeeze_row(r) for r in squeezed[:25])
    st_rows      = ''.join(st_row(r) for r in st_squeezed[:20])

    sm_rows = ''
    for t, note in special_mention.items():
        r = next((x for x in valid if x['t'] == t), None)
        if r:
            rs  = rs_map.get(t)
            hi  = hi_map.get(t, 0.0)
            cmf = cmf_map.get(t, 0.0)
            rs_s = f'{rs:.2f}x' if rs is not None else '—'
            lag  = ' ↓' if (rs is not None and rs < 0.80) else ''
            mc   = (m_cmf_map or {}).get(t, (None, None, '→'))
            if mc[0] is not None:
                mcmf_cell = (f'<span style="color:{_c_cmf(mc[0])}">{mc[0]:+.2f}</span>'
                             f'<span style="color:{_c_trend(mc[2])};font-weight:600"> {mc[2]}</span>')
            else:
                mcmf_cell = '<span style="color:#484f58">—</span>'
            sm_rows += (f'<tr>'
                        f'<td class="ticker">{disp(t)}</td>'
                        f'<td style="color:{_c_ma(r["s"])}">{r["s"]}/4</td>'
                        f'<td>₹{r["p"]:,.2f}</td>'
                        f'<td style="color:{_c_rs(rs)}">{rs_s}{lag}</td>'
                        f'<td style="color:{_c_hi(hi)}">{hi:+.1f}%</td>'
                        f'<td style="color:{_c_cmf(cmf)}">{cmf:+.2f}</td>'
                        f'<td>{mcmf_cell}</td>'
                        f'<td style="color:#8b949e;font-size:11px">{note}</td>'
                        f'</tr>')

    promo_rows = ''.join(
        f'<tr><td style="color:#8b949e;font-size:11px">[W]</td>'
        f'<td class="ticker">{disp(t)}</td>'
        f'<td style="color:{_c_grade(g)}">{g}</td>'
        f'<td>₹{p:.2f}</td><td style="color:{_c_ma(ma)}">{ma}/4 MA</td></tr>'
        for t, p, g, ma in promos
    )

    n_aplus = sum(1 for _, g in zip(aligned, grades) if g == 'A+')
    n_a     = sum(1 for _, g in zip(aligned, grades) if g == 'A')

    css = """
      *{box-sizing:border-box;margin:0;padding:0}
      body{background:#0d1117;color:#e6edf3;font-family:'SF Mono','Fira Code',monospace;font-size:13px;padding:28px 32px}
      h1{font-size:18px;font-weight:600;margin-bottom:4px}
      .meta{color:#8b949e;font-size:12px;margin-bottom:24px}
      .summary{display:flex;gap:16px;flex-wrap:wrap;margin-bottom:28px}
      .stat{background:#161b22;border:1px solid #21262d;border-radius:8px;padding:12px 20px}
      .stat-val{font-size:22px;font-weight:600}
      .stat-lbl{font-size:11px;color:#8b949e;margin-top:2px}
      .sh{font-size:12px;font-weight:600;color:#f0883e;margin:28px 0 6px;text-transform:uppercase;letter-spacing:.04em}
      .sub{color:#8b949e;font-size:11px;margin-bottom:8px}
      table{border-collapse:collapse;width:100%;margin-bottom:4px}
      th{color:#8b949e;font-weight:400;font-size:11px;text-align:left;padding:4px 12px 6px 8px;border-bottom:1px solid #21262d;white-space:nowrap}
      td{padding:5px 12px 5px 8px;border-bottom:1px solid #161b22;white-space:nowrap}
      tr:hover td{background:#161b22}
      .ticker{font-weight:600;color:#e6edf3}
      tr.grp td{background:#161b22;color:#8b949e;font-size:11px;padding:6px 8px 4px;letter-spacing:.05em;text-transform:uppercase;border-bottom:none}
      .legend{color:#8b949e;font-size:11px;margin-top:8px}
    """

    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<title>India Aligned — {now}</title><style>{css}</style></head><body>
<h1>🇮🇳 India Aligned Screener</h1>
<div class="meta">{now} · universe + watchlist · {len(valid)} fetched · RS vs NIFTY 50</div>

<div class="summary">
  <div class="stat"><div class="stat-val" style="color:#3fb950">{len(aligned)}</div><div class="stat-lbl">4/4 Aligned</div></div>
  <div class="stat"><div class="stat-val" style="color:#3fb950">{n_aplus}</div><div class="stat-lbl">A+ Grade</div></div>
  <div class="stat"><div class="stat-val" style="color:#58a6ff">{n_a}</div><div class="stat-lbl">A Grade</div></div>
  <div class="stat"><div class="stat-val" style="color:#d29922">{len(partial)}</div><div class="stat-lbl">3/4 Near-Aligned</div></div>
  <div class="stat"><div class="stat-val">{len(promos)}</div><div class="stat-lbl">Promo Candidates</div></div>
</div>

<div class="sh">4/4 Aligned — {len(aligned)} names</div>
<table><thead><tr>
  <th></th><th>Ticker</th><th>Grade</th><th>Price</th><th>RS vs NIFTY</th><th>% from 52wH</th><th>CMF</th>
</tr></thead><tbody>{aligned_rows}</tbody></table>
<div class="legend">RS = 13w price vs NIFTY 50 &nbsp;·&nbsp; offHi = % below 52w high &nbsp;·&nbsp; CMF &gt;+0.10 accumulation / &lt;–0.10 distribution &nbsp;·&nbsp;
<span style="color:#f85149">↓ = RS &lt; 0.80 lagging</span></div>

<div class="sh">3/4 Near-Aligned — {len(partial)} names</div>
<table><thead><tr>
  <th></th><th>Ticker</th><th>RS vs NIFTY</th><th>% from 52wH</th><th>CMF</th><th>MA</th><th>Price</th>
</tr></thead><tbody>{partial_rows}</tbody></table>

{'<div class="sh">Promotion Candidates</div><table><thead><tr><th></th><th>Ticker</th><th>Grade</th><th>Price</th><th>MA</th></tr></thead><tbody>' + promo_rows + '</tbody></table>' if promos else ''}

<div class="sh">Special Mention — Teasing / Puzzling Setups</div>
<div class="sub">Structure building or price dislocated — not yet actionable but worth watching closely. &nbsp;Mth CMF = 6-month monthly CMF + trend vs prior 6 months (↑ rising / ↓ falling / → flat).</div>
<table><thead><tr>
  <th>Ticker</th><th>MA</th><th>Price</th><th>RS vs NIFTY</th><th>offHi</th><th>CMF (wkly)</th><th>Mth CMF</th><th>Note</th>
</tr></thead><tbody>{sm_rows}</tbody></table>

<div class="sh">Weekly Squeeze — FullCoil (top 25)</div>
<div class="sub">● &lt;3% very tight &nbsp; ○ 3–5% building &nbsp; CMF &gt;+0.10 accumulation / &lt;–0.10 distribution &nbsp; RS vs NIFTY 13w &nbsp; offHi = % from 52w high</div>
<table><thead><tr>
  <th>Ticker</th><th></th><th>MA</th><th>Price</th><th>Spread</th>
  <th>Vol</th><th>Slp</th><th>CMF</th><th>RS</th><th>offHi</th>
  <th>10w MA</th><th>20w MA</th><th>35w MA</th><th>50w MA</th>
</tr></thead><tbody>{squeeze_rows}</tbody></table>

<div class="sh">ST Squeeze — 10w/20w Convergence (top 20)</div>
<div class="sub">● &lt;2% very tight &nbsp; ○ 2–4% building &nbsp; FullCoil = 10w–50w spread for context</div>
<table><thead><tr>
  <th>Ticker</th><th></th><th>MA</th><th>Price</th><th>Gap</th>
  <th>Vol</th><th>Slp</th><th>CMF</th><th>RS</th><th>offHi</th>
  <th>10w MA</th><th>20w MA</th><th>FullCoil</th>
</tr></thead><tbody>{st_rows}</tbody></table>

<div class="legend" style="margin-top:28px">
  <span style="color:#3fb950">■</span> RS ≥ 1.20 outperforming &nbsp;
  <span style="color:#f85149">■</span> RS &lt; 0.80 lagging &nbsp;
  <span style="color:#3fb950">■</span> CMF &gt;+0.10 accumulation &nbsp;
  <span style="color:#d29922">■</span> CMF &lt;–0.10 distribution &nbsp;
  <span style="color:#3fb950">■</span> offHi ≥ –3% near 52w high
</div>
<div class="legend" style="margin-top:6px">For informational purposes only. Not financial advice.</div>
</body></html>"""


if __name__ == '__main__':
    # Fetch NIFTY 50 reference once for RS calculation
    nifty_hist      = yf.Ticker('^NSEI').history(period='1y', interval='1wk')
    nifty_close     = nifty_hist['Close'].dropna()
    nifty_13w_ratio = float(nifty_close.iloc[-1]) / float(nifty_close.iloc[-14]) if len(nifty_close) >= 14 else 1.0
    ma_score_fn     = functools.partial(ma_score, nifty_13w_ratio=nifty_13w_ratio)

    print(f"\n  Fetching MA alignment for {len(TICKERS)} India tickers ...", flush=True)
    with ThreadPoolExecutor(max_workers=20) as ex:
        results = list(ex.map(ma_score_fn, TICKERS))

    valid   = [r for r in results if r]
    aligned = sorted([r for r in valid if r['s'] == 4], key=lambda r: disp(r['t']))
    partial = sorted([r for r in valid if r['s'] == 3], key=lambda r: disp(r['t']))

    print(f"  Fetching grades for {len(aligned)} aligned names ...\n", flush=True)
    aligned_tickers = [r['t'] for r in aligned]
    with ThreadPoolExecutor(max_workers=10) as ex:
        grades = list(ex.map(grade_ticker, aligned_tickers))

    now     = datetime.now().strftime('%b %d %Y  %H:%M')
    aplus   = [(r['t'], r['p'], g) for r, g in zip(aligned, grades) if g == 'A+']
    a       = [(r['t'], r['p'], g) for r, g in zip(aligned, grades) if g == 'A']
    watch   = [(r['t'], r['p'], g) for r, g in zip(aligned, grades) if g == '—']
    rs_map  = {r['t']: r.get('rs')            for r in valid}
    hi_map  = {r['t']: r.get('pct_from_high') for r in valid}
    cmf_map = {r['t']: r.get('cmf', 0.0)      for r in valid}

    def fmt_rs_hi(t):
        rs_val  = rs_map.get(t)
        hi_val  = hi_map.get(t)
        cmf_val = cmf_map.get(t, 0.0)
        rs_s    = f'{rs_val:.2f}x' if rs_val is not None else '  —  '
        hi_s    = f'{hi_val:+.1f}%' if hi_val is not None else '   —'
        lag     = ' ↓' if (rs_val is not None and rs_val < 0.80) else '  '
        return f'RS {rs_s}{lag}  {hi_s} hi  CMF {cmf_val:+.2f}'

    print(f"  4/4 ALIGNED — {len(aligned)} names  ({now})")
    print(f"  {'─'*60}")

    if aplus:
        print(f"\n  A+ — structure + quality")
        for t, p, g in sorted(aplus, key=lambda x: disp(x[0])):
            src = 'U' if t in UNIVERSE else ('W' if t in WATCHLIST else 'X')
            print(f"  [{src}]  {disp(t):12}  A+  ₹{p:>10.2f}   {fmt_rs_hi(t)}")
    if a:
        print(f"\n  A  — structure + quality")
        for t, p, g in sorted(a, key=lambda x: disp(x[0])):
            src = 'U' if t in UNIVERSE else ('W' if t in WATCHLIST else 'X')
            print(f"  [{src}]  {disp(t):12}  A   ₹{p:>10.2f}   {fmt_rs_hi(t)}")
    if watch:
        print(f"\n  Watchlist / not yet qualifying")
        for t, p, g in sorted(watch, key=lambda x: disp(x[0])):
            src = 'U' if t in UNIVERSE else ('W' if t in WATCHLIST else 'X')
            print(f"  [{src}]  {disp(t):12}  —   ₹{p:>10.2f}   {fmt_rs_hi(t)}")

    print(f"\n  3/4 NEAR-ALIGNED — {len(partial)} names")
    print(f"  {'─'*60}")
    for r in partial:
        src = 'U' if r['t'] in UNIVERSE else ('W' if r['t'] in WATCHLIST else 'X')
        print(f"  [{src}]  {disp(r['t']):12}       ₹{r['p']:>10.2f}   {fmt_rs_hi(r['t'])}")

    # Promotion candidates
    price_map = {r['t']: r['p'] for r in valid}
    score_map = {r['t']: r['s'] for r in valid}
    promos = []
    for t in WATCHLIST:
        d = get_fundamentals(t)
        if d and passes_quality_filter(d):
            g  = quality_grade(d)
            p  = price_map.get(t, 0)
            ma = score_map.get(t, 0)
            promos.append((t, round(p, 2), g, ma))
    promos.sort(key=lambda x: (0 if x[2]=='A+' else 1, disp(x[0])))

    print(f"\n  WATCHLIST PROMOTION CANDIDATES — {len(promos)} qualifying")
    print(f"  {'─'*48}")
    if promos:
        for t, p, g, ma in promos:
            print(f"  [W]  {disp(t):12}  {g:<3}  ₹{p:.2f}  [{ma}/4 MA]  ← promote to UNIVERSE?")
    else:
        print(f"  none — all watchlist names below quality threshold")

    # Monthly CMF trend for Special Mention
    print(f"  Fetching monthly CMF trend for Special Mention names ...", flush=True)
    m_cmf_map = {}
    for t in SPECIAL_MENTION:
        cur, prior, trend = monthly_cmf_trend(t)
        m_cmf_map[t] = (cur, prior, trend)

    print(f"\n  SPECIAL MENTION — Teasing / Puzzling Setups")
    print(f"  {'─'*60}")
    for t, note in SPECIAL_MENTION.items():
        r = next((x for x in valid if x['t'] == t), None)
        if r:
            rs_val  = rs_map.get(t)
            hi_val  = hi_map.get(t)
            cmf_val = cmf_map.get(t, 0.0)
            mcmf    = m_cmf_map.get(t, (None, None, '→'))
            rs_s    = f'RS {rs_val:.2f}x' if rs_val is not None else 'RS  —  '
            hi_s    = f'{hi_val:+.1f}% hi' if hi_val is not None else '—'
            mcmf_s  = f'MthCMF {mcmf[0]:+.2f}{mcmf[2]}' if mcmf[0] is not None else 'MthCMF —'
            print(f"  {disp(t):12}  {r['s']}/4  ₹{r['p']:>10.2f}   {rs_s}   {hi_s}   CMF {cmf_val:+.2f}   {mcmf_s}")
            print(f"               → {note}\n")

    # Weekly Squeeze
    squeezed = sorted(valid, key=lambda r: r['w_spread'])
    print(f"\n  WEEKLY SQUEEZE — 10w/20w/35w/50w MA compression  ({now})")
    print(f"  {'─'*84}")
    print(f"  {'Ticker':<12} {'MA':<4} {'Price':>10}  {'Spread':>7}  {'Vol':>4}  {'Slp'}  {'CMF':>6}  {'RS':>6}  {'offHi':>6}")
    print(f"  {'─'*12} {'─'*4} {'─'*10}  {'─'*7}  {'─'*4}  {'─'*3}  {'─'*6}  {'─'*6}  {'─'*6}")
    for r in squeezed[:25]:
        t     = r['t']
        src   = 'U' if t in UNIVERSE else ('W' if t in WATCHLIST else 'X')
        flag  = '●' if r['w_spread'] < 3.0 else ('○' if r['w_spread'] < 5.0 else ' ')
        vol_s = f'{r["vol_ratio"]:.1f}x' if r.get('vol_ratio') is not None else ' —  '
        slp_s = '↑' if r.get('slope_up') else '↓'
        cmf_s = f'{r.get("cmf", 0.0):+.2f}'
        rs_v  = r.get('rs')
        rs_s  = f'{rs_v:.2f}x' if rs_v is not None else '  —  '
        hi_s  = f'{r.get("pct_from_high", 0.0):+.1f}%'
        print(f"  {disp(t):<12} {r['s']}/4  ₹{r['p']:>9.2f}  {flag}{r['w_spread']:>5.1f}%  {vol_s:>4}  {slp_s}  {cmf_s:>6}  {rs_s:>6}  {hi_s:>6}  [{src}]")

    # ST Squeeze
    st_squeezed = sorted(valid, key=lambda r: r['st_spread'])
    print(f"\n  ST SQUEEZE — 10w/20w SMA convergence  ({now})")
    print(f"  {'─'*72}")
    print(f"  {'Ticker':<12} {'MA':<4} {'Price':>10}  {'Gap':>6}  {'Vol':>4}  {'Slp'}  {'CMF':>6}  {'RS':>6}  {'offHi':>6}  {'FullCoil':>8}")
    print(f"  {'─'*12} {'─'*4} {'─'*10}  {'─'*6}  {'─'*4}  {'─'*3}  {'─'*6}  {'─'*6}  {'─'*6}  {'─'*8}")
    for r in st_squeezed[:20]:
        t     = r['t']
        src   = 'U' if t in UNIVERSE else ('W' if t in WATCHLIST else 'X')
        flag  = '●' if r['st_spread'] < 2.0 else ('○' if r['st_spread'] < 4.0 else ' ')
        vol_s = f'{r["vol_ratio"]:.1f}x' if r.get('vol_ratio') is not None else ' —  '
        slp_s = '↑' if r.get('slope_up') else '↓'
        cmf_s = f'{r.get("cmf", 0.0):+.2f}'
        rs_v  = r.get('rs')
        rs_s  = f'{rs_v:.2f}x' if rs_v is not None else '  —  '
        hi_s  = f'{r.get("pct_from_high", 0.0):+.1f}%'
        print(f"  {disp(t):<12} {r['s']}/4  ₹{r['p']:>9.2f}  {flag}{r['st_spread']:>4.1f}%"
              f"  {vol_s:>4}  {slp_s}  {cmf_s:>6}  {rs_s:>6}  {hi_s:>6}  {r['w_spread']:>7.1f}%  [{src}]")

    print(f"\n  ● <2% very tight   ○ 2-4% building   FullCoil = 10w-50w spread   CMF >+0.10 accum  <-0.10 distrib   RS vs NIFTY 13w")
    print(f"\n  [U] = Universe   [W] = Watchlist   [X] = Extra\n")

    # HTML output + auto-push
    import subprocess
    html     = build_aligned_html(valid, aligned, grades, partial, promos,
                                  squeezed, st_squeezed, rs_map, hi_map, cmf_map,
                                  SPECIAL_MENTION, now, UNIVERSE, WATCHLIST, m_cmf_map)
    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'india_aligned_screener.html')
    with open(out_path, 'w') as f:
        f.write(html)
    print(f"  Saved → {out_path}")
    subprocess.Popen(['open', out_path])

    try:
        repo       = os.path.dirname(out_path)
        commit_msg = f"india_aligned_screener: {now}"
        subprocess.run(['git', 'add', 'india_aligned_screener.html'], cwd=repo, check=True, capture_output=True)
        subprocess.run(['git', 'commit', '-m', commit_msg],           cwd=repo, check=True, capture_output=True)
        subprocess.run(['git', 'push'],                                cwd=repo, check=True, capture_output=True)
        print(f"  Pushed → GitHub  ({commit_msg})")
    except subprocess.CalledProcessError as e:
        msg = e.stderr.decode().strip() if e.stderr else str(e)
        print(f"  Git push skipped: {msg or 'nothing new to commit'}")
