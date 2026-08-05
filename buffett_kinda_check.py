"""
buffett_kinda_check.py — Buffett-style quality lens applied to our universe.

Five low-fog checks drawn from the Buffett criteria card, cross-referenced
against our own quality standards:

  B1  Gross Margin > 40%     card #1  — pricing power proxy
  B2  Net Margin  > 20%      card #7  — tightest income test (our gate: ≥5%)
  B3  FCF yield   > 0        our add  — fog-reducer: confirms NM is real cash
  B4  Cash > Debt            card #9  — solvency, hard and zero-fog
  B5  D/EV ≤ 0.10            card #5  — interest burden proxy, low fog

Intentionally skipped (with reasoning):
  SG&A/GP, R&D/GP   — needs income-stmt line items not in cache; sector-blind on R&D
  Depreciation/GP   — high fog: schedule-driven, management-chosen
  Adj D/E           — overlaps B5; D/EV cleaner for non-financial sectors
  EPS growth        — buyback-distortable; 2yr window ≠ duration
  Treasury stock    — diluted share-count trend is the real test
  Retained Earnings — accumulation ≠ productivity; ROIC is the missing question
  Capex/NI          — needs cashflow fetch; FCF yield (B3) is the practical proxy

Parity note column:
  aligned   — our grade A/A+ and Buffett score ≥ 4 agree
  NM gap    — we grade A on ≥5% NM gate; Buffett wants >20% (capital-heavy sector divergence)
  debt      — passes our D/EV gate but fails Cash>Debt (structural leverage, not distress)
  B→Buff+   — grades B with us, but Buffett score ≥ 4 (different angle, not wrong)
  —→Buff?   — fails our filter but Buffett basics look ok (usually high-growth pre-profit)

Usage:
  python3 buffett_kinda_check.py               # Universe + Watchlist
  python3 buffett_kinda_check.py --universe    # Universe only
  python3 buffett_kinda_check.py --watchlist   # Watchlist only
  python3 buffett_kinda_check.py NVDA AAPL     # Specific tickers
"""

import json
import os
import sys
import types
import warnings
import webbrowser
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

warnings.filterwarnings('ignore')
sys.modules.setdefault('_yf_cache', types.ModuleType('_yf_cache'))

import yfinance as yf
from screener import UNIVERSE, WATCHLIST

_DIR        = os.path.dirname(os.path.abspath(__file__))
_CACHE_FILE = os.path.join(_DIR, 'screener_data_cache.json')


# ── Data ──────────────────────────────────────────────────────────────────────

def _load_cache():
    try:
        with open(_CACHE_FILE) as f:
            return json.load(f)
    except Exception:
        return {}

def _fetch_cash_debt(ticker):
    try:
        info = yf.Ticker(ticker).info
        cash = info.get('totalCash') or 0
        debt = info.get('totalDebt') or 0
        return ticker, cash > debt
    except Exception:
        return ticker, None


# ── Scoring ───────────────────────────────────────────────────────────────────

def _buffett_flags(d, cash_gt_debt):
    # Cache stores margins as percentages (48.7 = 48.7%), D/EV as decimal ratio
    gm  = d.get('gross_margin')
    nm  = d.get('net_margin')
    fcf = d.get('fcf_yield')
    dev = d.get('debt_to_ev')
    return {
        'GM>40': gm  is not None and gm  > 40,
        'NM>20': nm  is not None and nm  > 20,
        'FCF>0': fcf is not None and fcf > 0,
        'Ca>Dt': cash_gt_debt is True,
        'D≤.10': dev is not None and dev <= 0.10,
    }

def _parity(grade, score, flags):
    if grade in ('A+', 'A') and score >= 4:
        return 'aligned'
    if grade in ('A+', 'A') and score <= 2:
        return 'NM gap' if not flags.get('NM>20') else ('debt' if not flags.get('Ca>Dt') else 'diverge')
    if grade == 'B' and score >= 4:
        return 'B→Buff+'
    if grade == '—' and score >= 3:
        return '—→Buff?'
    return ''

def _score_color(sc):
    return {5: ('#0d1a0d', '#3fb950'),
            4: ('#0d1220', '#58a6ff'),
            3: ('#1c1700', '#d4a017'),
            2: ('#1a1000', '#f0883e')}.get(sc, ('#1a0000', '#f85149'))

def _build_rows(tickers, cache, cd_map):
    rows = []
    for t in tickers:
        d      = cache.get(t) or {}
        c_gt_d = cd_map.get(t)
        grade  = (d.get('grade') or '—') if d else '—'
        flags  = _buffett_flags(d, c_gt_d)
        sc     = sum(flags.values())
        note   = _parity(grade, sc, flags)
        rows.append((t, grade, d, sc, flags, note))
    grade_order = {'A+': 0, 'A': 1, 'B': 2, '—': 3}
    rows.sort(key=lambda x: (-x[3], grade_order.get(x[1], 4), x[0]))
    return rows


# ── HTML ──────────────────────────────────────────────────────────────────────

def _pct(v, decimals=0):
    if v is None:
        return '—'
    fmt = f'{{:+.{decimals}f}}%' if decimals else f'{{:.0f}}%'
    return fmt.format(v)

def _chk_html(v):
    if v:
        return '<span style="color:#3fb950;font-weight:700">✓</span>'
    return '<span style="color:#484f58">·</span>'

def _grade_badge(g):
    c = {'A+': '#3fb950', 'A': '#58a6ff', 'B': '#d29922'}.get(g, '#484f58')
    return (f'<span style="background:{c}22;color:{c};border:1px solid {c}44;'
            f'border-radius:3px;padding:1px 6px;font-size:11px;font-weight:600">{g}</span>')

def _parity_badge(note):
    cfg = {
        'aligned':  ('#3fb950', '#0d1a0d'),
        'NM gap':   ('#d4a017', '#1c1700'),
        'debt':     ('#f0883e', '#1a1000'),
        'B→Buff+':  ('#58a6ff', '#0d1220'),
        '—→Buff?':  ('#8b949e', '#161b22'),
        'diverge':  ('#f85149', '#1a0000'),
    }
    if not note:
        return ''
    color, bg = cfg.get(note, ('#8b949e', '#161b22'))
    return (f'<span style="background:{bg};color:{color};border:1px solid {color}44;'
            f'border-radius:3px;padding:1px 6px;font-size:10px">{note}</span>')

def _score_badge(sc):
    bg, border = _score_color(sc)
    return (f'<span style="background:{bg};color:{border};border:1px solid {border}44;'
            f'border-radius:3px;padding:2px 8px;font-size:12px;font-weight:700">{sc}/5</span>')

def _nm_cell(nm):
    if nm is None:
        return '<td style="color:#484f58;text-align:right">—</td>'
    color = '#3fb950' if nm > 20 else '#d4a017' if nm > 10 else '#f85149'
    return f'<td style="color:{color};font-weight:600;text-align:right">{nm:.0f}%</td>'

def _gm_cell(gm):
    if gm is None:
        return '<td style="color:#484f58;text-align:right">—</td>'
    color = '#3fb950' if gm > 40 else '#d4a017' if gm > 25 else '#8b949e'
    return f'<td style="color:{color};text-align:right">{gm:.0f}%</td>'

def _html_row(t, gr, d, sc, flags, note):
    bg, border = _score_color(sc)
    gm  = d.get('gross_margin')
    nm  = d.get('net_margin')
    fcf = d.get('fcf_yield')
    dev = d.get('debt_to_ev')
    fcf_s = _pct(fcf, decimals=1) if fcf is not None else '—'
    fcf_c = '#3fb950' if (fcf or 0) > 0 else '#f85149'
    dev_s = f'{dev:.3f}' if dev is not None else '—'
    dev_c = '#3fb950' if (dev or 1) <= 0.10 else '#d4a017' if (dev or 1) <= 0.20 else '#f85149'

    return f"""<tr style="background:{bg};border-left:3px solid {border}">
      <td style="padding:7px 10px;font-weight:700;color:#e6edf3">{t}</td>
      <td style="padding:7px 10px">{_grade_badge(gr)}</td>
      {_gm_cell(gm)}
      {_nm_cell(nm)}
      <td style="padding:7px 10px;text-align:right;color:{fcf_c}">{fcf_s}</td>
      <td style="padding:7px 10px;text-align:right;color:{dev_c}">{dev_s}</td>
      <td style="padding:7px 10px;text-align:center">{_chk_html(flags['GM>40'])}</td>
      <td style="padding:7px 10px;text-align:center">{_chk_html(flags['NM>20'])}</td>
      <td style="padding:7px 10px;text-align:center">{_chk_html(flags['FCF>0'])}</td>
      <td style="padding:7px 10px;text-align:center">{_chk_html(flags['Ca>Dt'])}</td>
      <td style="padding:7px 10px;text-align:center">{_chk_html(flags['D≤.10'])}</td>
      <td style="padding:7px 10px;text-align:center">{_score_badge(sc)}</td>
      <td style="padding:7px 10px">{_parity_badge(note)}</td>
    </tr>"""

def _html_section(title, rows):
    if not rows:
        return ''
    tbl_rows = ''
    last_sc  = -1
    for t, gr, d, sc, flags, note in rows:
        if sc != last_sc:
            bg, border = _score_color(sc)
            tbl_rows += (
                f'<tr><td colspan="13" style="padding:5px 10px 3px;font-size:10px;'
                f'letter-spacing:.06em;text-transform:uppercase;color:{border};'
                f'background:#161b22;border-top:1px solid #21262d">'
                f'{sc}/5 — {"★ full Buffett" if sc==5 else "near" if sc==4 else "partial" if sc==3 else "weak" if sc==2 else "minimal"}'
                f'</td></tr>'
            )
            last_sc = sc
        tbl_rows += _html_row(t, gr, d, sc, flags, note)

    scores = [r[3] for r in rows]
    summary = ' &nbsp;·&nbsp; '.join(
        f'<span style="color:#e6edf3;font-weight:700">{scores.count(i)}</span> {i}/5'
        for i in [5, 4, 3, 2, 1, 0] if scores.count(i)
    )

    return f'''
<div style="margin-bottom:36px">
  <div style="font-size:13px;font-weight:600;color:#e6edf3;margin-bottom:6px">{title}
    <span style="color:#8b949e;font-weight:400;font-size:11px">({len(rows)} names)</span>
  </div>
  <div style="font-size:11px;color:#8b949e;margin-bottom:12px">{summary}</div>
  <table style="width:100%;border-collapse:collapse;font-size:12px">
    <thead>
      <tr style="border-bottom:2px solid #21262d">
        <th style="padding:7px 10px;text-align:left;color:#8b949e;font-weight:500;font-size:10px;text-transform:uppercase">Ticker</th>
        <th style="padding:7px 10px;text-align:left;color:#8b949e;font-weight:500;font-size:10px;text-transform:uppercase">Gr</th>
        <th style="padding:7px 10px;text-align:right;color:#8b949e;font-weight:500;font-size:10px;text-transform:uppercase">GM%</th>
        <th style="padding:7px 10px;text-align:right;color:#8b949e;font-weight:500;font-size:10px;text-transform:uppercase">NM%</th>
        <th style="padding:7px 10px;text-align:right;color:#8b949e;font-weight:500;font-size:10px;text-transform:uppercase">FCF%</th>
        <th style="padding:7px 10px;text-align:right;color:#8b949e;font-weight:500;font-size:10px;text-transform:uppercase">D/EV</th>
        <th style="padding:7px 10px;text-align:center;color:#3fb950;font-weight:500;font-size:10px">B1<br><span style="font-size:9px;color:#484f58">GM>40</span></th>
        <th style="padding:7px 10px;text-align:center;color:#3fb950;font-weight:500;font-size:10px">B2<br><span style="font-size:9px;color:#484f58">NM>20</span></th>
        <th style="padding:7px 10px;text-align:center;color:#3fb950;font-weight:500;font-size:10px">B3<br><span style="font-size:9px;color:#484f58">FCF>0</span></th>
        <th style="padding:7px 10px;text-align:center;color:#3fb950;font-weight:500;font-size:10px">B4<br><span style="font-size:9px;color:#484f58">Ca>Dt</span></th>
        <th style="padding:7px 10px;text-align:center;color:#3fb950;font-weight:500;font-size:10px">B5<br><span style="font-size:9px;color:#484f58">D≤.10</span></th>
        <th style="padding:7px 10px;text-align:center;color:#8b949e;font-weight:500;font-size:10px;text-transform:uppercase">Score</th>
        <th style="padding:7px 10px;text-align:left;color:#8b949e;font-weight:500;font-size:10px;text-transform:uppercase">Parity</th>
      </tr>
    </thead>
    <tbody>{tbl_rows}</tbody>
  </table>
</div>'''

def build_html(sections, now, label):
    body = ''.join(_html_section(title, rows) for title, rows in sections)
    return f'''<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Buffett-Kinda Check — {now}</title>
<style>
  * {{ box-sizing:border-box; margin:0; padding:0; }}
  body {{ font-family:'SF Mono','Fira Code',monospace; background:#0d1117; color:#e6edf3; padding:28px; font-size:12px; }}
  h1 {{ font-size:18px; font-weight:700; color:#58a6ff; margin-bottom:4px; }}
  .sub {{ color:#8b949e; font-size:11px; margin-bottom:6px; }}
  .legend {{ color:#8b949e; font-size:11px; margin-bottom:24px; line-height:1.8; }}
  tr:hover td {{ background:rgba(255,255,255,0.03); }}
  .disclaimer {{ color:#484f58; font-size:10px; margin-top:24px; border-top:1px solid #21262d; padding-top:8px; }}
</style>
</head>
<body>
<h1>🧾 Buffett-Kinda Check <span style="font-size:13px;color:#8b949e;font-weight:400">— {label}</span></h1>
<div class="sub">{now} &nbsp;·&nbsp; 5 low-fog checks from Buffett criteria card, cross-referenced with our quality standards</div>
<div class="legend">
  <strong style="color:#e6edf3">B1</strong> Gross Margin &gt;40% &nbsp;·&nbsp;
  <strong style="color:#e6edf3">B2</strong> Net Margin &gt;20% <span style="color:#484f58">(our gate: ≥5% — capital-heavy sectors diverge here)</span> &nbsp;·&nbsp;
  <strong style="color:#e6edf3">B3</strong> FCF &gt;0 <span style="color:#484f58">(fog-reducer: confirms NM is real cash)</span> &nbsp;·&nbsp;
  <strong style="color:#e6edf3">B4</strong> Cash &gt; Debt &nbsp;·&nbsp;
  <strong style="color:#e6edf3">B5</strong> D/EV ≤ 0.10 &nbsp;·&nbsp;
  <span style="color:#3fb950">aligned</span> = our grade + Buffett agree &nbsp;·&nbsp;
  <span style="color:#d4a017">NM gap</span> = we grade A on ≥5%, Buffett needs &gt;20% &nbsp;·&nbsp;
  <span style="color:#58a6ff">B→Buff+</span> = grades B with us, Buffett score ≥4 &nbsp;·&nbsp;
  <span style="color:#8b949e">—→Buff?</span> = fails our filter, Buffett basics ok
</div>
{body}
<div class="disclaimer">For informational purposes only. Market dynamics change constantly — these outputs are auto-generated from Yahoo Finance data and may not reflect current conditions. Not tailored financial advice. Not a recommendation to buy, sell, or hold any security. Always do your own research. &nbsp;·&nbsp; Buffett criteria adapted from publicly known heuristics — not an official Berkshire Hathaway framework.</div>
</body>
</html>'''


# ── CLI print ─────────────────────────────────────────────────────────────────

def _cli_print(title, rows):
    W = 104
    print(f'\n{"─"*W}')
    print(f'  {title} — {len(rows)} names')
    print(f'  {"─"*W}')
    print(f'  {"Ticker":<7} {"Gr":<3}  {"GM%":>5} {"NM%":>5} {"FCF%":>6} {"D/EV":>5}  B1 B2 B3 B4 B5  Score  Parity')
    print(f'  {"─"*7} {"─"*3}  {"─"*5} {"─"*5} {"─"*6} {"─"*5}  ── ── ── ── ──  ─────  ──────────')
    last_sc = -1
    for t, gr, d, sc, flags, note in rows:
        if sc != last_sc:
            print(f'\n  ── {sc}/5 ──')
            last_sc = sc
        gm_s  = _pct(d.get('gross_margin'))
        nm_s  = _pct(d.get('net_margin'))
        fcf_s = _pct(d.get('fcf_yield'), decimals=1)
        dev_s = f"{d.get('debt_to_ev'):.3f}" if d.get('debt_to_ev') is not None else '—'
        chk   = lambda v: '✓' if v else '·'
        print(f'  {t:<7} {gr:<3}  {gm_s:>5} {nm_s:>5} {fcf_s:>6} {dev_s:>5}  '
              f'{chk(flags["GM>40"])} {chk(flags["NM>20"])} {chk(flags["FCF>0"])} '
              f'{chk(flags["Ca>Dt"])} {chk(flags["D≤.10"])}  {sc:>3}/5  {note}')
    scores = [r[3] for r in rows]
    print(f'\n  5/5:{scores.count(5)}  4/5:{scores.count(4)}  3/5:{scores.count(3)}  '
          f'2/5:{scores.count(2)}  1/5:{scores.count(1)}  0/5:{scores.count(0)}')


# ── Main ──────────────────────────────────────────────────────────────────────

def run(sections_spec, label):
    """sections_spec: list of (title, tickers)"""
    all_tickers = list(dict.fromkeys(t for _, ticks in sections_spec for t in ticks))
    print(f'\n  Buffett-Kinda Check — fetching cash/debt for {len(all_tickers)} tickers ...', flush=True)
    with ThreadPoolExecutor(max_workers=16) as ex:
        cd_results = list(ex.map(_fetch_cash_debt, all_tickers))
    cd_map  = dict(cd_results)
    cache   = _load_cache()

    sections_html = []
    for title, tickers in sections_spec:
        rows = _build_rows(tickers, cache, cd_map)
        _cli_print(title, rows)
        sections_html.append((title, rows))

    now  = datetime.utcnow().strftime('%b %d %Y  %H:%M UTC')
    html = build_html(sections_html, now, label)
    out  = os.path.join(_DIR, 'buffett_kinda_check.html')
    with open(out, 'w') as f:
        f.write(html)
    print(f'\n  Opened → {out}\n')
    webbrowser.open(f'file://{out}')


if __name__ == '__main__':
    args = sys.argv[1:]

    if not args:
        run([('Universe', list(dict.fromkeys(UNIVERSE))),
             ('Watchlist', list(dict.fromkeys(WATCHLIST)))],
            label='Universe + Watchlist')
    elif args == ['--universe']:
        run([('Universe', list(dict.fromkeys(UNIVERSE)))], label='Universe')
    elif args == ['--watchlist']:
        run([('Watchlist', list(dict.fromkeys(WATCHLIST)))], label='Watchlist')
    else:
        tickers = [t.upper() for t in args if not t.startswith('--')]
        run([('Custom', tickers)], label=', '.join(tickers))
