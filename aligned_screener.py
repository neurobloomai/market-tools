"""
aligned_screener.py — 4/4 MA Aligned Names + Weekly Squeeze Scanner
Cross-references screener universe + watchlist against full MA structure.
Fetches quality grades for aligned names — shows [U/W] TICKER GRADE $PRICE.
Weekly squeeze: monitors 10w/20w/35w/50w MA compression across all names.
Run: python aligned_screener.py
"""

import yfinance as yf, warnings, os, functools
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
warnings.filterwarnings('ignore')

from screener import UNIVERSE, WATCHLIST, get_fundamentals, passes_quality_filter, quality_grade

# Local tracking — not in public screener, internal watch only
EXTRA = [
    'LYFT',  # ride-sharing FCF story; FCF 22.7%, RevG 14%, OM -0.3% and D/EV 0.274 blocking; 6m thesis
    'OTLY',  # Oatly — oat milk brand, strong product; OM -5.3%, D/EV 0.72, FCF negative blocking; LT thesis: monthly squeeze forming, structural base building, 15.6% rev growth; 0/4 MA, years from qualifying
]

# Special mention — teasing/puzzling setups not yet in alignment
# Price has ripped down or structure is rebuilding; quality or thesis intact, not yet actionable
SPECIAL_MENTION = {
    'LYFT': 'Ride-sharing FCF turning positive; 2/4 recovering — short-term MAs reclaimed, waiting for 10m/20m to align; watch for monthly structure to complete',
    'PLAB': 'Photomask specialist (semiconductor enabler); quality passed filters but cyclical collapse from highs; above 20m MA only — structure rebuilding, patience required',
    'UPWK': 'Freelance marketplace; price ~$8 far below monthly MAs (~$13-14) but monthly 10m/20m compressing (+/-2%) — MA squeeze forming on monthly chart while price bases; downtrend in averages flattening; D/EV 0.44 (converts) only fundamental blocker; watch for monthly structure recovery',
    'MRAM': 'Magnetoresistive RAM (Everspin) — niche non-volatile memory; fundamentals actively strengthening but 6-9 month thesis; RS 2.26x outperforming SPY despite -38% offHi = recovery not leadership yet; CMF distribution into the bounce; 3/4 MA — wait for 20m confirmation + CMF flip before treating as actionable',
    'PLTR': 'Palantir — AI/data analytics platform (AIP + Foundry + Gotham); A+ quality, government + commercial flywheel; 0/4 MA — price pulled back below all MAs, structure rebuilding; valuation stretched (high P/E growth premium); wait for MA reclaim before treating as actionable entry',
    'HUBS': 'HubSpot — CRM/marketing platform; grade A not A+ yet (OM 3.3%, NM 3.0%, ROE 5.0% below threshold); 0/4 MA, -69% from highs; engine intact — RevG 23.4%, FCF 7.4%, D/EV 0.033 (clean debt); margin thesis is the watch item — OM crossing 10% + NM crossing 5% = auto-qualifies A+; not actionable until margin data confirms the inflection',
    'NEM': 'Newmont — world\'s largest gold miner (A+); 1/4 MA after gold cycle pullback — price below 10w/20w/10m but 20m support holding; FullCoil 14.6% still wide; OM 61.4%, NM 33.9%, FCF 8.7%, D/EV 0.049; Newcrest acquisition added copper assets (dual GLD + partial COPX theme); gold structural bid intact (central bank buying, de-dollarization); not actionable until MAs reclaim — watch 10m ($101) as first line to cross',
    'MCO': 'Moody\'s — credit rating duopoly (with SPGI); every debt issuance globally needs a Moody\'s or S&P rating — structural toll collector on global capital markets; OM 45.7%, NM 31.7%, ROE 71.4%, D/EV 0.089, FCF 2.9%, RevG 8.1%; 2/4 MA, price below 10m ($470) and 20m ($473) — both monthly MAs clustered tight; watch $470 as the line to reclaim; great businesses deserve tracking even before alignment',
    'SPGI': 'S&P Global — credit rating + financial data duopoly (with MCO); S&P 500 index licensing, Platts commodity data, Market Intelligence platform; pricing power permanent, toll collector on every index fund globally; 0/4 MA — watch for structure recovery alongside MCO',
    'NOW': 'ServiceNow — enterprise workflow automation platform; grade A (OM borderline); but world-class business moat — deep IT workflow integration means switching cost is near-permanent; 0/4 MA, -58% from highs; every large enterprise runs on ServiceNow; watch for margin inflection to A+ and MA structure recovery',
}

TICKERS = list(dict.fromkeys(UNIVERSE + WATCHLIST + EXTRA + list(SPECIAL_MENTION.keys())))

def ma_score(ticker, spy_13w_ratio=1.0):
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
        w_spread  = round((1 if ma10w >= ma50w else -1) * (max(wmas) - min(wmas)) / price * 100, 2)
        st_spread = round((1 if ma10w >= ma20w else -1) * abs(ma10w - ma20w) / price * 100, 2)
        vol = hist['Volume'].dropna()
        if len(vol) >= 11:
            vol_ratio = round(float(vol.iloc[-2]) / float(vol.iloc[-11:-1].mean()), 2)
        else:
            vol_ratio = None
        slope_up = (float(close.tail(10).mean()) > float(close.iloc[-14:-4].mean())) if len(close) >= 14 else True

        # CMF (Chaikin Money Flow) — 20-week
        # Measures whether volume is weighted toward closes near the high (accumulation)
        # or near the low (distribution). Range -1 to +1.
        # >+0.10 = accumulation  <-0.10 = distribution  in-between = neutral
        cmf = 0.0
        ad_arrow, obv_arrow, ad_div = '→', '→', None
        try:
            high = hist['High'].dropna()
            low  = hist['Low'].dropna()
            idx  = close.index.intersection(vol.index).intersection(high.index).intersection(low.index)
            ca = close.loc[idx]; ha = high.loc[idx]; la = low.loc[idx]; va = vol.loc[idx]
            c20 = ca.tail(20); h20 = ha.tail(20); l20 = la.tail(20); v20 = va.tail(20)
            hl      = (h20 - l20).replace(0, float('nan'))
            mfm     = ((c20 - l20) - (h20 - c20)) / hl
            mfv     = mfm.fillna(0) * v20
            vol_sum = float(v20.sum())
            cmf     = round(float(mfv.sum()) / vol_sum, 3) if vol_sum > 0 else 0.0
            # A/D Line + OBV — 13-week slope for divergence detection
            # A/D Line: cumulative money flow volume — rising = accumulation regardless of price
            # OBV: directional volume — confirms or contradicts price trend
            if len(ca) >= 14:
                hl_a     = (ha - la).replace(0, float('nan'))
                ad_line  = ((((ca - la) - (ha - ca)) / hl_a).fillna(0) * va).cumsum()
                ad_up    = float(ad_line.iloc[-1]) > float(ad_line.iloc[-14])
                obv_dir  = ca.diff().apply(lambda x: 1.0 if x > 0 else (-1.0 if x < 0 else 0.0))
                obv_line = (va * obv_dir).cumsum()
                obv_up   = float(obv_line.iloc[-1]) > float(obv_line.iloc[-14])
                ad_arrow  = '↑' if ad_up  else '↓'
                obv_arrow = '↑' if obv_up else '↓'
                price_up  = price > float(ca.iloc[-14])
                if ad_up and not price_up:
                    ad_div = 'bull'   # smart money accumulating while price weak
                elif not ad_up and price_up:
                    ad_div = 'bear'   # distribution into price strength
        except:
            cmf = 0.0

        # % from 52-week high — proximity to highs = momentum context
        high_52w      = float(close.tail(52).max()) if len(close) >= 52 else float(close.max())
        pct_from_high = round((price - high_52w) / high_52w * 100, 1)

        # RS vs SPY — 13-week relative performance ratio
        # >1.0 = outperforming SPY  <1.0 = underperforming  <0.80 = lagging flag
        rs = None
        if spy_13w_ratio and spy_13w_ratio != 1.0 and len(close) >= 14:
            stock_13w_ratio = float(close.iloc[-1]) / float(close.iloc[-14])
            rs = round(stock_13w_ratio / spy_13w_ratio, 2)

        return {
            't': ticker, 'p': round(price, 2), 's': score,
            'w_spread': w_spread, 'st_spread': st_spread,
            'vol_ratio': vol_ratio, 'slope_up': slope_up,
            'cmf': cmf, 'rs': rs, 'pct_from_high': pct_from_high,
            'ma10w': round(ma10w, 2), 'ma20w': round(ma20w, 2),
            'ma35w': round(ma35w, 2), 'ma50w': round(ma50w, 2),
            'ad_arrow': ad_arrow, 'obv_arrow': obv_arrow, 'ad_div': ad_div,
        }
    except:
        return None


def daily_squeeze_data(ticker):
    try:
        hist  = yf.Ticker(ticker).history(period='6mo', interval='1d')
        close = hist['Close'].dropna()
        if len(close) < 50:
            return None
        price = float(close.iloc[-1])
        ma10d = float(close.tail(10).mean())
        ma20d = float(close.tail(20).mean())
        ma35d = float(close.tail(35).mean()) if len(close) >= 35 else ma20d
        ma50d = float(close.tail(50).mean())
        dmas      = [ma10d, ma20d, ma35d, ma50d]
        d_spread  = round((1 if ma10d >= ma50d else -1) * (max(dmas) - min(dmas)) / price * 100, 2)
        slope_up  = ma10d > float(close.iloc[-11:-1].mean()) if len(close) >= 11 else True
        cmf = 0.0
        try:
            high = hist['High'].dropna(); low = hist['Low'].dropna(); vol = hist['Volume'].dropna()
            idx  = close.index.intersection(vol.index).intersection(high.index).intersection(low.index)
            c20  = close.loc[idx].tail(20); h20 = high.loc[idx].tail(20)
            l20  = low.loc[idx].tail(20);   v20 = vol.loc[idx].tail(20)
            hl   = (h20 - l20).replace(0, float('nan'))
            mfv  = (((c20 - l20) - (h20 - c20)) / hl).fillna(0) * v20
            vs   = float(v20.sum())
            cmf  = round(float(mfv.sum()) / vs, 3) if vs > 0 else 0.0
        except:
            pass
        return {
            't': ticker, 'p': round(price, 2),
            'd_spread': d_spread, 'slope_up': slope_up, 'cmf': cmf,
            'ma10d': round(ma10d, 2), 'ma20d': round(ma20d, 2),
            'ma35d': round(ma35d, 2), 'ma50d': round(ma50d, 2),
        }
    except:
        return None


def monthly_squeeze_data(ticker):
    try:
        hist  = yf.Ticker(ticker).history(period='5y', interval='1mo')
        close = hist['Close'].dropna()
        if len(close) < 20:
            return None
        price = float(close.iloc[-1])
        ma3m  = float(close.tail(3).mean())
        ma6m  = float(close.tail(6).mean())
        ma10m = float(close.tail(10).mean())
        ma20m = float(close.tail(20).mean())
        mmas      = [ma3m, ma6m, ma10m, ma20m]
        m_spread  = round((1 if ma3m >= ma20m else -1) * (max(mmas) - min(mmas)) / price * 100, 2)
        slope_up  = ma3m > float(close.iloc[-4:-1].mean()) if len(close) >= 4 else True
        cmf = 0.0
        try:
            high = hist['High'].dropna(); low = hist['Low'].dropna(); vol = hist['Volume'].dropna()
            idx  = close.index.intersection(vol.index).intersection(high.index).intersection(low.index)
            c6   = close.loc[idx].tail(6); h6 = high.loc[idx].tail(6)
            l6   = low.loc[idx].tail(6);   v6 = vol.loc[idx].tail(6)
            hl   = (h6 - l6).replace(0, float('nan'))
            mfv  = (((c6 - l6) - (h6 - c6)) / hl).fillna(0) * v6
            vs   = float(v6.sum())
            cmf  = round(float(mfv.sum()) / vs, 3) if vs > 0 else 0.0
        except:
            pass
        return {
            't': ticker, 'p': round(price, 2),
            'm_spread': m_spread, 'slope_up': slope_up, 'cmf': cmf,
            'ma3m': round(ma3m, 2), 'ma6m': round(ma6m, 2),
            'ma10m': round(ma10m, 2), 'ma20m': round(ma20m, 2),
        }
    except:
        return None


# ── HTML helpers ─────────────────────────────────────────────────────────────

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

def _c_ad(arrow):
    if arrow == '↑': return '#3fb950'
    if arrow == '↓': return '#f85149'
    return '#8b949e'


def build_aligned_html(valid, aligned, grades, partial, promos,
                       squeezed, st_squeezed, rs_map, hi_map, cmf_map,
                       special_mention, now, UNIVERSE, WATCHLIST, m_cmf_map=None,
                       daily_squeezed=None, monthly_squeezed=None, mtf_set=None,
                       pullback_watch=None):

    def src_tag(t):
        return 'U' if t in UNIVERSE else ('W' if t in WATCHLIST else 'X')

    score_map = {r['t']: r['s'] for r in valid}
    _mtf = mtf_set or set()

    def aligned_row(r, g):
        t    = r['t']
        rs   = rs_map.get(t)
        hi   = hi_map.get(t)
        cmf  = cmf_map.get(t, 0.0)
        ad   = r.get('ad_arrow', '→')
        obv  = r.get('obv_arrow', '→')
        div  = r.get('ad_div')
        rs_s = f'{rs:.2f}x' if rs is not None else '—'
        hi_s = f'{hi:+.1f}%' if hi is not None else '—'
        lag  = ' ↓' if (rs is not None and rs < 0.80) else ''
        div_s = (' <span style="color:#d29922;font-size:10px" title="A/D bullish divergence">◆</span>' if div == 'bull'
                 else (' <span style="color:#8b949e;font-size:10px" title="A/D bearish divergence">◇</span>' if div == 'bear' else ''))
        return (f'<tr>'
                f'<td style="color:#8b949e;font-size:11px">[{src_tag(t)}]</td>'
                f'<td class="ticker">{t}</td>'
                f'<td style="color:{_c_grade(g)};font-weight:600">{g}</td>'
                f'<td>${r["p"]:,.2f}</td>'
                f'<td style="color:{_c_rs(rs)}">{rs_s}{lag}</td>'
                f'<td style="color:{_c_hi(hi or 0)}">{hi_s}</td>'
                f'<td style="color:{_c_cmf(cmf)}">{cmf:+.2f}</td>'
                f'<td><span style="color:{_c_ad(ad)}">{ad}</span> <span style="color:{_c_ad(obv)}">{obv}</span>{div_s}</td>'
                f'</tr>')

    def partial_row(r):
        t    = r['t']
        rs   = rs_map.get(t)
        hi   = hi_map.get(t)
        cmf  = cmf_map.get(t, 0.0)
        ad   = r.get('ad_arrow', '→')
        obv  = r.get('obv_arrow', '→')
        div  = r.get('ad_div')
        rs_s = f'{rs:.2f}x' if rs is not None else '—'
        hi_s = f'{hi:+.1f}%' if hi is not None else '—'
        lag  = ' ↓' if (rs is not None and rs < 0.80) else ''
        div_s = (' <span style="color:#d29922;font-size:10px" title="A/D bullish divergence">◆</span>' if div == 'bull'
                 else (' <span style="color:#8b949e;font-size:10px" title="A/D bearish divergence">◇</span>' if div == 'bear' else ''))
        return (f'<tr>'
                f'<td style="color:#8b949e;font-size:11px">[{src_tag(t)}]</td>'
                f'<td class="ticker">{t}</td>'
                f'<td style="color:{_c_rs(rs)}">{rs_s}{lag}</td>'
                f'<td style="color:{_c_hi(hi or 0)}">{hi_s}</td>'
                f'<td style="color:{_c_cmf(cmf)}">{cmf:+.2f}</td>'
                f'<td><span style="color:{_c_ad(ad)}">{ad}</span> <span style="color:{_c_ad(obv)}">{obv}</span>{div_s}</td>'
                f'<td style="color:{_c_ma(r["s"])}">{r["s"]}/4</td>'
                f'<td>${r["p"]:,.2f}</td>'
                f'</tr>')

    def squeeze_row(r):
        t     = r['t']
        cmf   = r.get('cmf', 0.0)
        rs    = r.get('rs')
        hi    = r.get('pct_from_high', 0.0)
        slp   = '<span style="color:#3fb950">▲</span>' if r.get('slope_up') else '<span style="color:#f85149">▼</span>'
        flag  = '●' if abs(r['w_spread']) < 3.0 else ('○' if abs(r['w_spread']) < 5.0 else '')
        rs_s  = f'{rs:.2f}x' if rs is not None else '—'
        lag   = ' ↓' if (rs is not None and rs < 0.80) else ''
        return (f'<tr>'
                f'<td class="ticker">{t}</td>'
                f'<td style="color:#8b949e;font-size:11px">[{src_tag(t)}]</td>'
                f'<td style="color:{_c_ma(r["s"])}">{r["s"]}/4</td>'
                f'<td>${r["p"]:,.2f}</td>'
                f'<td>{flag} {r["w_spread"]:.1f}%</td>'
                f'<td>{slp}</td>'
                f'<td style="color:{_c_cmf(cmf)}">{cmf:+.2f}</td>'
                f'<td style="color:{_c_rs(rs)}">{rs_s}{lag}</td>'
                f'<td style="color:{_c_hi(hi)}">{hi:+.1f}%</td>'
                f'<td style="color:#484f58;font-size:11px">${r["ma10w"]:,.2f}</td>'
                f'<td style="color:#484f58;font-size:11px">${r["ma20w"]:,.2f}</td>'
                f'<td style="color:#484f58;font-size:11px">${r["ma35w"]:,.2f}</td>'
                f'<td style="color:#484f58;font-size:11px">${r["ma50w"]:,.2f}</td>'
                f'</tr>')

    def st_row(r):
        t     = r['t']
        cmf   = r.get('cmf', 0.0)
        rs    = r.get('rs')
        hi    = r.get('pct_from_high', 0.0)
        slp   = '<span style="color:#3fb950">▲</span>' if r.get('slope_up') else '<span style="color:#f85149">▼</span>'
        flag  = '●' if abs(r['st_spread']) < 2.0 else ('○' if abs(r['st_spread']) < 4.0 else '')
        rs_s  = f'{rs:.2f}x' if rs is not None else '—'
        lag   = ' ↓' if (rs is not None and rs < 0.80) else ''
        return (f'<tr>'
                f'<td class="ticker">{t}</td>'
                f'<td style="color:#8b949e;font-size:11px">[{src_tag(t)}]</td>'
                f'<td style="color:{_c_ma(r["s"])}">{r["s"]}/4</td>'
                f'<td>${r["p"]:,.2f}</td>'
                f'<td>{flag} {r["st_spread"]:.1f}%</td>'
                f'<td>{slp}</td>'
                f'<td style="color:{_c_cmf(cmf)}">{cmf:+.2f}</td>'
                f'<td style="color:{_c_rs(rs)}">{rs_s}{lag}</td>'
                f'<td style="color:{_c_hi(hi)}">{hi:+.1f}%</td>'
                f'<td style="color:#484f58;font-size:11px">${r["ma10w"]:,.2f}</td>'
                f'<td style="color:#484f58;font-size:11px">${r["ma20w"]:,.2f}</td>'
                f'<td style="color:{_c_ma(r["s"])}">{r["w_spread"]:.1f}%</td>'
                f'</tr>')

    def daily_row(r):
        t    = r['t']
        ws   = score_map.get(t)
        hi   = hi_map.get(t, 0.0)
        cmf  = r.get('cmf', 0.0)
        slp  = '<span style="color:#3fb950">▲</span>' if r.get('slope_up') else '<span style="color:#f85149">▼</span>'
        flag = '●' if abs(r['d_spread']) < 3.0 else ('○' if abs(r['d_spread']) < 5.0 else '')
        star = '<span style="color:#d29922" title="MTF">★</span> ' if t in _mtf else ''
        ws_s = f'{ws}/4' if ws is not None else '—'
        return (f'<tr>'
                f'<td class="ticker">{star}{t}</td>'
                f'<td style="color:#8b949e;font-size:11px">[{src_tag(t)}]</td>'
                f'<td style="color:{_c_ma(ws or 0)}">{ws_s}</td>'
                f'<td>${r["p"]:,.2f}</td>'
                f'<td>{flag} {r["d_spread"]:.1f}%</td>'
                f'<td>{slp}</td>'
                f'<td style="color:{_c_cmf(cmf)}">{cmf:+.2f}</td>'
                f'<td style="color:{_c_hi(hi)}">{hi:+.1f}%</td>'
                f'<td style="color:#484f58;font-size:11px">${r["ma10d"]:,.2f}</td>'
                f'<td style="color:#484f58;font-size:11px">${r["ma20d"]:,.2f}</td>'
                f'<td style="color:#484f58;font-size:11px">${r["ma35d"]:,.2f}</td>'
                f'<td style="color:#484f58;font-size:11px">${r["ma50d"]:,.2f}</td>'
                f'</tr>')

    def monthly_row(r):
        t    = r['t']
        ws   = score_map.get(t)
        hi   = hi_map.get(t, 0.0)
        cmf  = r.get('cmf', 0.0)
        slp  = '<span style="color:#3fb950">▲</span>' if r.get('slope_up') else '<span style="color:#f85149">▼</span>'
        flag = '●' if abs(r['m_spread']) < 3.0 else ('○' if abs(r['m_spread']) < 5.0 else '')
        star = '<span style="color:#d29922" title="MTF">★</span> ' if t in _mtf else ''
        ws_s = f'{ws}/4' if ws is not None else '—'
        return (f'<tr>'
                f'<td class="ticker">{star}{t}</td>'
                f'<td style="color:#8b949e;font-size:11px">[{src_tag(t)}]</td>'
                f'<td style="color:{_c_ma(ws or 0)}">{ws_s}</td>'
                f'<td>${r["p"]:,.2f}</td>'
                f'<td>{flag} {r["m_spread"]:.1f}%</td>'
                f'<td>{slp}</td>'
                f'<td style="color:{_c_cmf(cmf)}">{cmf:+.2f}</td>'
                f'<td style="color:{_c_hi(hi)}">{hi:+.1f}%</td>'
                f'<td style="color:#484f58;font-size:11px">${r["ma3m"]:,.2f}</td>'
                f'<td style="color:#484f58;font-size:11px">${r["ma6m"]:,.2f}</td>'
                f'<td style="color:#484f58;font-size:11px">${r["ma10m"]:,.2f}</td>'
                f'<td style="color:#484f58;font-size:11px">${r["ma20m"]:,.2f}</td>'
                f'</tr>')

    # Assemble section rows
    aligned_rows = ''
    for label, subset in [('A+ — structure + quality', [(r,g) for r,g in zip(aligned,grades) if g=='A+']),
                           ('A — structure + quality',  [(r,g) for r,g in zip(aligned,grades) if g=='A']),
                           ('Watchlist / not yet qualifying', [(r,g) for r,g in zip(aligned,grades) if g=='—'])]:
        if subset:
            aligned_rows += f'<tr class="grp"><td colspan="8">{label}</td></tr>'
            for r, g in sorted(subset, key=lambda x: x[0]['t']):
                aligned_rows += aligned_row(r, g)

    partial_rows = ''.join(partial_row(r) for r in partial)
    squeeze_rows = ''.join(squeeze_row(r) for r in squeezed[:25])
    st_rows      = ''.join(st_row(r) for r in st_squeezed[:20])

    _ds = sorted([r for r in (daily_squeezed or []) if r],   key=lambda r: abs(r['d_spread']))
    _ms = sorted([r for r in (monthly_squeezed or []) if r], key=lambda r: abs(r['m_spread']))
    daily_rows   = ''.join(daily_row(r) for r in _ds[:20])
    monthly_rows = ''.join(monthly_row(r) for r in _ms[:20])

    mtf_color = '#d29922' if _mtf else '#484f58'
    mtf_section = ''
    if _mtf:
        mtf_names = ' &nbsp;·&nbsp; '.join(
            f'<span style="font-weight:600;color:#d29922">{t}</span>' for t in sorted(_mtf))
        mtf_section = (
            f'<div class="sh" style="color:#d29922">★ Multi-Timeframe Squeeze — {len(_mtf)} names</div>'
            f'<div class="sub">Daily + Weekly + Monthly all compressed simultaneously — rarest structural setup.</div>'
            f'<div style="background:#161b22;border:1px solid #d29922;border-radius:6px;'
            f'padding:12px 16px;margin-bottom:20px;font-size:13px">{mtf_names}</div>'
        )

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
            auto_badge = '<span style="color:#484f58;font-size:10px">[auto] </span>' if note.startswith('[auto]') else ''
            note_text  = note[7:] if note.startswith('[auto]') else note
            sig = sm_signal(rs, mc[2])
            sig_color = '#3fb950' if sig == '◎' else ('#f85149' if sig == '⚠' else '#8b949e')
            sig_label = 'base building' if sig == '◎' else ('distributing' if sig == '⚠' else 'mixed')
            sig_cell  = f'<span style="color:{sig_color};font-weight:600">{sig}</span><span style="color:{sig_color};font-size:10px"> {sig_label}</span>'
            ad  = r.get('ad_arrow', '→')
            obv = r.get('obv_arrow', '→')
            div = r.get('ad_div')
            if div == 'bull':
                div_badge = f' <span style="color:#d29922;font-size:10px" title="A/D rising while price weak — smart money accumulating">◆bull</span>'
            elif div == 'bear':
                div_badge = f' <span style="color:#8b949e;font-size:10px" title="A/D falling while price rises — distribution">◇bear</span>'
            else:
                div_badge = ''
            flow_cell = (f'<span style="color:{_c_ad(ad)}">AD:{ad}</span>'
                         f' <span style="color:{_c_ad(obv)}">OBV:{obv}</span>{div_badge}')
            sm_rows += (f'<tr>'
                        f'<td class="ticker">{t}</td>'
                        f'<td style="color:{_c_ma(r["s"])}">{r["s"]}/4</td>'
                        f'<td>${r["p"]:,.2f}</td>'
                        f'<td style="color:{_c_rs(rs)}">{rs_s}{lag}</td>'
                        f'<td style="color:{_c_hi(hi)}">{hi:+.1f}%</td>'
                        f'<td style="color:{_c_cmf(cmf)}">{cmf:+.2f}</td>'
                        f'<td>{mcmf_cell}</td>'
                        f'<td>{flow_cell}</td>'
                        f'<td>{sig_cell}</td>'
                        f'<td style="color:#8b949e;font-size:11px">{auto_badge}{note_text}</td>'
                        f'</tr>')

    promo_rows = ''.join(
        f'<tr><td style="color:#8b949e;font-size:11px">[W]</td>'
        f'<td class="ticker">{t}</td>'
        f'<td style="color:{_c_grade(g)}">{g}</td>'
        f'<td>${p:.2f}</td><td style="color:{_c_ma(ma)}">{ma}/4 MA</td></tr>'
        for t, p, g, ma in promos
    )

    _pw = pullback_watch or []
    def pw_row(r, g):
        t    = r['t']
        rs   = rs_map.get(t)
        hi   = hi_map.get(t, 0.0)
        cmf  = cmf_map.get(t, 0.0)
        ad   = r.get('ad_arrow', '→')
        obv  = r.get('obv_arrow', '→')
        div  = r.get('ad_div')
        rs_s = f'{rs:.2f}x' if rs is not None else '—'
        lag  = ' ↓' if (rs is not None and rs < 0.80) else ''
        div_s = (' <span style="color:#d29922;font-size:10px" title="A/D bullish divergence">◆</span>' if div == 'bull'
                 else (' <span style="color:#8b949e;font-size:10px" title="A/D bearish divergence">◇</span>' if div == 'bear' else ''))
        return (f'<tr>'
                f'<td style="color:#8b949e;font-size:11px">[{src_tag(t)}]</td>'
                f'<td class="ticker">{t}</td>'
                f'<td style="color:{_c_grade(g)};font-weight:600">{g}</td>'
                f'<td>${r["p"]:,.2f}</td>'
                f'<td style="color:{_c_rs(rs)}">{rs_s}{lag}</td>'
                f'<td style="color:{_c_hi(hi)}">{hi:+.1f}%</td>'
                f'<td style="color:{_c_cmf(cmf)}">{cmf:+.2f}</td>'
                f'<td><span style="color:{_c_ad(ad)}">{ad}</span> <span style="color:{_c_ad(obv)}">{obv}</span>{div_s}</td>'
                f'<td style="color:#484f58;font-size:11px">20w ${r["ma20w"]:,.2f}</td>'
                f'</tr>')
    pw_rows = ''.join(pw_row(r, g) for r, g in _pw)

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
      .sh{font-size:12px;font-weight:600;color:#58a6ff;margin:28px 0 6px;text-transform:uppercase;letter-spacing:.04em}
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
<title>Aligned — {now}</title><style>{css}</style></head><body>
<h1>Aligned Screener</h1>
<div class="meta">{now} · universe + watchlist · {len(valid)} fetched</div>

<div class="summary">
  <div class="stat"><div class="stat-val" style="color:#3fb950">{len(aligned)}</div><div class="stat-lbl">4/4 Aligned</div></div>
  <div class="stat"><div class="stat-val" style="color:#3fb950">{n_aplus}</div><div class="stat-lbl">A+ Grade</div></div>
  <div class="stat"><div class="stat-val" style="color:#58a6ff">{n_a}</div><div class="stat-lbl">A Grade</div></div>
  <div class="stat"><div class="stat-val" style="color:#d29922">{len(partial)}</div><div class="stat-lbl">3/4 Near-Aligned</div></div>
  <div class="stat"><div class="stat-val">{len(promos)}</div><div class="stat-lbl">Promo Candidates</div></div>
  <div class="stat"><div class="stat-val" style="color:{'#d29922' if _pw else '#484f58'}">{len(_pw)}</div><div class="stat-lbl">Pullback Watch</div></div>
  <div class="stat"><div class="stat-val" style="color:{mtf_color}">{"★ " if _mtf else ""}{len(_mtf)}</div><div class="stat-lbl">MTF Squeeze</div></div>
</div>

{mtf_section}
<div class="sh">4/4 Aligned — {len(aligned)} names</div>
<table><thead><tr>
  <th></th><th>Ticker</th><th>Grade</th><th>Price</th><th>RS vs SPY</th><th>% from 52wH</th><th>CMF</th><th>AD OBV</th>
</tr></thead><tbody>{aligned_rows}</tbody></table>
<div class="legend">RS = 13w price vs SPY &nbsp;·&nbsp; offHi = % below 52w high &nbsp;·&nbsp; CMF &gt;+0.10 accumulation / &lt;–0.10 distribution &nbsp;·&nbsp;
AD/OBV = A/D Line + On Balance Volume 13w slope &nbsp;·&nbsp; <span style="color:#d29922">◆</span> bullish divergence (A/D↑ price↓) &nbsp;·&nbsp;
<span style="color:#f85149">↓ = RS &lt; 0.80 lagging</span></div>

<div class="sh">3/4 Near-Aligned — {len(partial)} names</div>
<table><thead><tr>
  <th></th><th>Ticker</th><th>RS vs SPY</th><th>% from 52wH</th><th>CMF</th><th>AD OBV</th><th>MA</th><th>Price</th>
</tr></thead><tbody>{partial_rows}</tbody></table>

{'<div class="sh">Promotion Candidates</div><table><thead><tr><th></th><th>Ticker</th><th>Grade</th><th>Price</th><th>MA</th></tr></thead><tbody>' + promo_rows + '</tbody></table>' if promos else ''}

<div class="sh">Special Mention — Teasing / Puzzling Setups</div>
<div class="sub">Structure building or price dislocated — not yet actionable but worth watching closely. &nbsp;Mth CMF = 6-month monthly CMF + trend vs prior 6 months (↑ rising / ↓ falling / → flat). &nbsp;Vol Flow = A/D Line + OBV 13w slope — <span style="color:#d29922">◆bull</span> = A/D rising while price weak (smart money accumulating). &nbsp;<span style="color:#3fb950">◎ base building</span> = MthCMF ↑ &nbsp;·&nbsp; <span style="color:#f85149">⚠ distributing</span> = MthCMF ↓ + RS &lt; 1.0 &nbsp;·&nbsp; <span style="color:#8b949e">→ mixed</span> = conflicting signals.</div>
<table><thead><tr>
  <th>Ticker</th><th>MA</th><th>Price</th><th>RS vs SPY</th><th>offHi</th><th>CMF (wkly)</th><th>Mth CMF</th><th>Vol Flow</th><th>Signal</th><th>Note</th>
</tr></thead><tbody>{sm_rows}</tbody></table>

{'<div class="sh" style="color:#d29922">↘ Pullback Watch — ' + str(len(_pw)) + ' names</div><div class="sub">A+/A quality at 2/4 MA — long-term structure intact (10m/20m holding), short-term MAs broken. Different from Special Mention: weeks away from reclaiming, not months. Watch 20w MA as first gate back to 3/4.</div><table><thead><tr><th></th><th>Ticker</th><th>Grade</th><th>Price</th><th>RS vs SPY</th><th>offHi</th><th>CMF</th><th>AD OBV</th><th>Reclaim</th></tr></thead><tbody>' + pw_rows + '</tbody></table>' if _pw else ''}

<div class="sh">Weekly Squeeze — FullCoil (top 25)</div>
<div class="sub">● &lt;3% very tight &nbsp; ○ 3–5% building &nbsp; Slp = 10w MA slope &nbsp; CMF &gt;+0.10 accumulation / &lt;–0.10 distribution &nbsp; RS vs SPY 13w &nbsp; offHi = % from 52w high</div>
<table><thead><tr>
  <th>Ticker</th><th></th><th>MA</th><th>Price</th><th>Spread</th>
  <th>Slp</th><th>CMF</th><th>RS</th><th>offHi</th>
  <th>10w MA</th><th>20w MA</th><th>35w MA</th><th>50w MA</th>
</tr></thead><tbody>{squeeze_rows}</tbody></table>

<div class="sh">ST Squeeze — 10w/20w Convergence (top 20)</div>
<div class="sub">● &lt;2% very tight &nbsp; ○ 2–4% building &nbsp; Slp = 10w MA slope &nbsp; FullCoil = 10w–50w spread for context</div>
<table><thead><tr>
  <th>Ticker</th><th></th><th>MA</th><th>Price</th><th>Gap</th>
  <th>Slp</th><th>CMF</th><th>RS</th><th>offHi</th>
  <th>10w MA</th><th>20w MA</th><th>FullCoil</th>
</tr></thead><tbody>{st_rows}</tbody></table>

<div class="sh">Daily Squeeze — FullCoil 10d/20d/35d/50d (top 20)</div>
<div class="sub">● &lt;3% very tight &nbsp; ○ 3–5% building &nbsp; Slp = 10d MA slope &nbsp; CMF = 20-day &nbsp; Wkly MA = weekly 4/4 score &nbsp; ★ = also MTF (all 3 TFs tight)</div>
<table><thead><tr>
  <th>Ticker</th><th></th><th>Wkly MA</th><th>Price</th><th>Daily Spread</th>
  <th>Slp</th><th>CMF</th><th>offHi</th><th>10d MA</th><th>20d MA</th><th>35d MA</th><th>50d MA</th>
</tr></thead><tbody>{daily_rows}</tbody></table>

<div class="sh">Monthly Squeeze — FullCoil 3m/6m/10m/20m (top 20)</div>
<div class="sub">● &lt;3% very tight &nbsp; ○ 3–5% building &nbsp; Slp = 3m MA slope &nbsp; CMF = 6-month &nbsp; Wkly MA = weekly 4/4 score &nbsp; ★ = also MTF (all 3 TFs tight)</div>
<table><thead><tr>
  <th>Ticker</th><th></th><th>Wkly MA</th><th>Price</th><th>Mthly Spread</th>
  <th>Slp</th><th>CMF</th><th>offHi</th><th>3m MA</th><th>6m MA</th><th>10m MA</th><th>20m MA</th>
</tr></thead><tbody>{monthly_rows}</tbody></table>

<div class="legend" style="margin-top:28px">
  <span style="color:#3fb950">■</span> RS ≥ 1.20 outperforming &nbsp;
  <span style="color:#f85149">■</span> RS &lt; 0.80 lagging &nbsp;
  <span style="color:#3fb950">■</span> CMF &gt;+0.10 accumulation &nbsp;
  <span style="color:#d29922">■</span> CMF &lt;–0.10 distribution &nbsp;
  <span style="color:#3fb950">■</span> offHi ≥ –3% near 52w high
</div>
<div class="legend" style="margin-top:6px">
  ● filled = very tight squeeze (FullCoil &lt;3%, ST Gap &lt;2%) — coil compressed, energy highest &nbsp;·&nbsp;
  ○ unfilled = building squeeze (FullCoil 3–5%, ST Gap 2–4%) — compressing but not fully wound &nbsp;·&nbsp;
  blank = spread still wide, no squeeze
</div>
<div class="legend" style="margin-top:6px">For informational purposes only. Not financial advice.</div>
</body></html>"""


def monthly_cmf_trend(ticker, n=6):
    """Monthly CMF for n months vs prior n months — trend for base-building names."""
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
        cur   = _cmf(c.iloc[-n:],      h.iloc[-n:],      l.iloc[-n:],      v.iloc[-n:])
        prior = _cmf(c.iloc[-n*2:-n],  h.iloc[-n*2:-n],  l.iloc[-n*2:-n],  v.iloc[-n*2:-n])

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

def sm_signal(rs, mcmf_trend):
    """Signal tag for Special Mention names.
    ◎ base building = MthCMF turning up
    ⚠ distributing  = MthCMF falling + RS lagging
    → mixed          = conflicting signals
    """
    if mcmf_trend == '↑':
        return '◎'
    if mcmf_trend == '↓' and (rs is None or rs < 1.0):
        return '⚠'
    return '→'

if __name__ == '__main__':
    # Fetch SPY reference once for RS calculation
    spy_hist      = yf.Ticker('SPY').history(period='1y', interval='1wk')
    spy_close     = spy_hist['Close'].dropna()
    spy_13w_ratio = float(spy_close.iloc[-1]) / float(spy_close.iloc[-14]) if len(spy_close) >= 14 else 1.0
    ma_score_fn   = functools.partial(ma_score, spy_13w_ratio=spy_13w_ratio)

    print(f"\n  Fetching MA alignment for {len(TICKERS)} tickers ...", flush=True)

    with ThreadPoolExecutor(max_workers=20) as ex:
        results = list(ex.map(ma_score_fn, TICKERS))

    valid = [r for r in results if r]

    print(f"  Fetching daily squeeze for {len(TICKERS)} tickers ...", flush=True)
    with ThreadPoolExecutor(max_workers=20) as ex:
        daily_results = list(ex.map(daily_squeeze_data, TICKERS))

    print(f"  Fetching monthly squeeze for {len(TICKERS)} tickers ...", flush=True)
    with ThreadPoolExecutor(max_workers=20) as ex:
        monthly_results = list(ex.map(monthly_squeeze_data, TICKERS))

    daily_valid   = [r for r in daily_results   if r]
    monthly_valid = [r for r in monthly_results if r]

    aligned = sorted([r for r in valid if r['s'] == 4], key=lambda r: r['t'])
    partial = sorted([r for r in valid if r['s'] == 3], key=lambda r: r['t'])

    print(f"  Fetching grades for {len(aligned)} aligned names ...\n", flush=True)
    aligned_tickers = [r['t'] for r in aligned]
    with ThreadPoolExecutor(max_workers=10) as ex:
        grades = list(ex.map(grade_ticker, aligned_tickers))
    grade_map = dict(zip(aligned_tickers, grades))

    now     = datetime.utcnow().strftime('%b %d %Y  %H:%M UTC')
    aplus   = [(r['t'], r['p'], g) for r, g in zip(aligned, grades) if g == 'A+']
    a       = [(r['t'], r['p'], g) for r, g in zip(aligned, grades) if g == 'A']
    watch   = [(r['t'], r['p'], g) for r, g in zip(aligned, grades) if g == '—']
    rs_map  = {r['t']: r.get('rs')            for r in valid}
    hi_map  = {r['t']: r.get('pct_from_high') for r in valid}

    cmf_map = {r['t']: r.get('cmf', 0.0) for r in valid}

    def fmt_rs_hi(t):
        rs_val  = rs_map.get(t)
        hi_val  = hi_map.get(t)
        cmf_val = cmf_map.get(t, 0.0)
        rs_s    = f'{rs_val:.2f}x' if rs_val is not None else '  —  '
        hi_s    = f'{hi_val:+.1f}%' if hi_val is not None else '   —'
        lag     = ' ↓' if (rs_val is not None and rs_val < 0.80) else '  '
        cmf_s   = f'CMF {cmf_val:+.2f}'
        return f'RS {rs_s}{lag}  {hi_s} hi  {cmf_s}'

    print(f"  4/4 ALIGNED — {len(aligned)} names  ({now})")
    print(f"  {'─'*60}")

    if aplus:
        print(f"\n  A+ — structure + quality")
        for t, p, g in sorted(aplus):
            src = 'U' if t in UNIVERSE else ('W' if t in WATCHLIST else 'X')
            print(f"  [{src}]  {t:8}  A+  ${p:>8.2f}   {fmt_rs_hi(t)}")

    if a:
        print(f"\n  A  — structure + quality")
        for t, p, g in sorted(a):
            src = 'U' if t in UNIVERSE else ('W' if t in WATCHLIST else 'X')
            print(f"  [{src}]  {t:8}  A   ${p:>8.2f}   {fmt_rs_hi(t)}")

    if watch:
        print(f"\n  Watchlist / not yet qualifying")
        for t, p, g in sorted(watch):
            src = 'U' if t in UNIVERSE else ('W' if t in WATCHLIST else 'X')
            print(f"  [{src}]  {t:8}  —   ${p:>8.2f}   {fmt_rs_hi(t)}")

    print(f"\n  3/4 NEAR-ALIGNED — {len(partial)} names")
    print(f"  {'─'*60}")
    for r in partial:
        src = 'U' if r['t'] in UNIVERSE else ('W' if r['t'] in WATCHLIST else 'X')
        print(f"  [{src}]  {r['t']:8}       ${r['p']:>8.2f}   {fmt_rs_hi(r['t'])}")

    # Promotion candidates — watchlist names now passing quality filters
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
    promos.sort(key=lambda x: (0 if x[2]=='A+' else 1, x[0]))

    print(f"\n  WATCHLIST PROMOTION CANDIDATES — {len(promos)} qualifying")
    print(f"  {'─'*48}")
    if promos:
        for t, p, g, ma in promos:
            price_str = f'${p:.2f}' if p else '—'
            print(f"  [W]  {t:8}  {g:<3}  {price_str}  [{ma}/4 MA]  ← promote to UNIVERSE?")
    else:
        print(f"  none — all watchlist names below quality threshold")

    # ── Auto-detect Special Mention ──────────────────────────────────────────
    # Quality name (A+/A) + structure broken (≤1/4) + far from highs (<-30%)
    # Manual SPECIAL_MENTION entries take precedence — richer notes, curated thesis
    auto_candidates = [r for r in valid
                       if ((r['s'] <= 1 and (r.get('pct_from_high') or 0) < -25)
                           or (r['s'] == 2 and (r.get('pct_from_high') or 0) < -45))
                       and r['t'] not in SPECIAL_MENTION
                       and (r['t'] in UNIVERSE or r['t'] in WATCHLIST)]
    auto_sm = {}
    if auto_candidates:
        print(f"  Auto-detecting Special Mention: {len(auto_candidates)} candidates ...", flush=True)
        with ThreadPoolExecutor(max_workers=10) as ex:
            auto_grades = list(ex.map(grade_ticker, [r['t'] for r in auto_candidates]))
        for r, g in zip(auto_candidates, auto_grades):
            if g == 'A+':
                hi = r.get('pct_from_high', 0)
                auto_sm[r['t']] = (f'[auto] A+ quality — {r["s"]}/4 MA, {hi:+.1f}% from highs; '
                                   f'structure dislocated, fundamentals intact; watch for MA recovery')

    # Manual entries override auto — merge with manual taking precedence
    combined_sm = {**auto_sm, **SPECIAL_MENTION}

    # ── Pullback Watch — A+/A quality at exactly 2/4, moderate pullback ──────
    # Long-term structure (10m/20m) intact — short-term (10w/20w) broken
    # -10% to -28% from highs: not a trivial dip, not a deep dislocation
    # Explicitly separate from Special Mention — weeks away, not months
    pw_candidates = [r for r in valid
                     if r['s'] == 2
                     and -28 <= (r.get('pct_from_high') or 0) <= -10
                     and r['t'] not in combined_sm
                     and (r['t'] in UNIVERSE or r['t'] in WATCHLIST)]
    pullback_watch = []
    if pw_candidates:
        print(f"  Auto-detecting Pullback Watch: {len(pw_candidates)} candidates ...", flush=True)
        with ThreadPoolExecutor(max_workers=10) as ex:
            pw_grades = list(ex.map(grade_ticker, [r['t'] for r in pw_candidates]))
        for r, g in zip(pw_candidates, pw_grades):
            if g in ('A+', 'A'):
                pullback_watch.append((r, g))
    pullback_watch.sort(key=lambda x: (0 if x[1] == 'A+' else 1, x[0]['t']))

    # Monthly CMF trend for all Special Mention names (auto + manual)
    print(f"  Fetching monthly CMF trend for {len(combined_sm)} Special Mention names ...", flush=True)
    m_cmf_map = {}
    for t in combined_sm:
        cur, prior, trend = monthly_cmf_trend(t)
        m_cmf_map[t] = (cur, prior, trend)

    # ── Special Mention ──────────────────────────────────────────────────────
    sm_data = [(t, note) for t, note in combined_sm.items()]
    print(f"\n  SPECIAL MENTION — Teasing / Puzzling Setups")
    print(f"  {'─'*60}")
    print(f"  Structure building or price dislocated — not yet actionable, worth watching closely.\n")
    for t, note in sm_data:
        r = next((x for x in valid if x['t'] == t), None)
        if r:
            rs_val  = rs_map.get(t)
            hi_val  = hi_map.get(t)
            cmf_val = cmf_map.get(t, 0.0)
            mcmf    = m_cmf_map.get(t, (None, None, '→'))
            rs_s    = f'RS {rs_val:.2f}x' if rs_val is not None else 'RS  —  '
            hi_s    = f'{hi_val:+.1f}% hi' if hi_val is not None else '—'
            mcmf_s  = f'MthCMF {mcmf[0]:+.2f}{mcmf[2]}' if mcmf[0] is not None else 'MthCMF —'
            sig     = sm_signal(rs_val, mcmf[2])
            ad_s    = r.get('ad_arrow', '→')
            obv_s   = r.get('obv_arrow', '→')
            div_s   = ' ◆bull' if r.get('ad_div') == 'bull' else (' ◇bear' if r.get('ad_div') == 'bear' else '')
            print(f"  {sig}  {t:8}  {r['s']}/4  ${r['p']:>8.2f}   {rs_s}   {hi_s}   CMF {cmf_val:+.2f}   {mcmf_s}   AD:{ad_s} OBV:{obv_s}{div_s}")
            print(f"           → {note}\n")
    print(f"  ◎ base building (MthCMF ↑)   ⚠ distributing (MthCMF ↓ + RS < 1.0)   → mixed signals")

    # ── Pullback Watch CLI ───────────────────────────────────────────────────
    print(f"\n  PULLBACK WATCH — {len(pullback_watch)} A+/A names at 2/4")
    print(f"  {'─'*60}")
    print(f"  Long-term structure intact (10m/20m holding) · short-term broken · watch 20w reclaim → 3/4\n")
    for r, g in pullback_watch:
        t       = r['t']
        src     = 'U' if t in UNIVERSE else ('W' if t in WATCHLIST else 'X')
        rs_val  = rs_map.get(t)
        hi_val  = hi_map.get(t, 0.0)
        cmf_val = cmf_map.get(t, 0.0)
        ad_s    = r.get('ad_arrow', '→')
        obv_s   = r.get('obv_arrow', '→')
        div_s   = ' ◆bull' if r.get('ad_div') == 'bull' else (' ◇bear' if r.get('ad_div') == 'bear' else '')
        rs_s    = f'RS {rs_val:.2f}x' if rs_val is not None else 'RS  —  '
        hi_s    = f'{hi_val:+.1f}% hi' if hi_val is not None else '—'
        print(f"  [{src}]  {t:8}  {g:<3}  ${r['p']:>8.2f}   {rs_s}   {hi_s}   CMF {cmf_val:+.2f}   AD:{ad_s} OBV:{obv_s}{div_s}   → 20w ${r['ma20w']:,.2f}")
    if not pullback_watch:
        print(f"  none — no A+/A names at 2/4 within pullback range (-10% to -28%)")

    # ── Squeeze Scanners ─────────────────────────────────────────────────────
    squeezed         = sorted(valid,         key=lambda r: abs(r['w_spread']))
    daily_squeezed   = sorted(daily_valid,   key=lambda r: abs(r['d_spread']))
    monthly_squeezed = sorted(monthly_valid, key=lambda r: abs(r['m_spread']))

    weekly_tight  = {r['t'] for r in squeezed         if abs(r['w_spread']) < 3.0}
    daily_tight   = {r['t'] for r in daily_squeezed   if abs(r['d_spread']) < 2.0}
    monthly_tight = {r['t'] for r in monthly_squeezed if abs(r['m_spread']) < 3.0}
    mtf_set = weekly_tight & daily_tight & monthly_tight

    ws_map = {r['t']: r['s'] for r in valid}

    print(f"\n  WEEKLY SQUEEZE — 10w/20w/35w/50w MA compression  ({now})")
    print(f"  {'─'*84}")
    print(f"  {'Ticker':<8} {'MA':<4} {'Price':>8}  {'Spread':>7}  {'Slp'}  {'CMF':>6}  {'RS':>6}  {'offHi':>6}  {'10w':>8} {'20w':>8} {'35w':>8} {'50w':>8}")
    print(f"  {'─'*8} {'─'*4} {'─'*8}  {'─'*7}  {'─'*3}  {'─'*6}  {'─'*6}  {'─'*6}  {'─'*8} {'─'*8} {'─'*8} {'─'*8}")

    for r in squeezed[:25]:
        t     = r['t']
        src   = 'U' if t in UNIVERSE else ('W' if t in WATCHLIST else 'X')
        flag  = '●' if abs(r['w_spread']) < 3.0 else ('○' if abs(r['w_spread']) < 5.0 else ' ')
        slp_s = '▲' if r.get('slope_up') else '▼'
        cmf_s = f'{r.get("cmf", 0.0):+.2f}'
        rs_v  = r.get('rs')
        rs_s  = f'{rs_v:.2f}x' if rs_v is not None else '  —  '
        hi_s  = f'{r.get("pct_from_high", 0.0):+.1f}%'
        print(f"  {t:<8} {r['s']}/4  ${r['p']:>7.2f}  {flag}{r['w_spread']:>+6.1f}%  {slp_s}  {cmf_s:>6}  {rs_s:>6}  {hi_s:>6}"
              f"  ${r['ma10w']:>7.2f} ${r['ma20w']:>7.2f} ${r['ma35w']:>7.2f} ${r['ma50w']:>7.2f}  [{src}]")

    print(f"\n  ● |<3%| very tight   ○ |3-5%| building   + = bullish MA order (10w>50w)   - = bearish order   Slp = 10w slope   CMF >+0.10 accum  <-0.10 distrib   RS vs SPY 13w   (top 25 shown)")

    # ── ST Squeeze Scanner ───────────────────────────────────────────────────
    # 10w/20w convergence only — faster, short-term momentum signal.
    # Can fire even inside a longer downtrend (35w/50w still wide) — confirm
    # against w_spread/score before treating it as a structural turn.
    st_squeezed = sorted(valid, key=lambda r: abs(r['st_spread']))

    print(f"\n  ST SQUEEZE — 10w/20w SMA convergence  ({now})")
    print(f"  {'─'*72}")
    print(f"  {'Ticker':<8} {'MA':<4} {'Price':>8}  {'Gap':>6}  {'Slp'}  {'CMF':>6}  {'RS':>6}  {'offHi':>6}  {'10w':>8} {'20w':>8}  {'FullCoil':>8}")
    print(f"  {'─'*8} {'─'*4} {'─'*8}  {'─'*6}  {'─'*3}  {'─'*6}  {'─'*6}  {'─'*6}  {'─'*8} {'─'*8}  {'─'*8}")

    for r in st_squeezed[:20]:
        t     = r['t']
        src   = 'U' if t in UNIVERSE else ('W' if t in WATCHLIST else 'X')
        flag  = '●' if abs(r['st_spread']) < 2.0 else ('○' if abs(r['st_spread']) < 4.0 else ' ')
        slp_s = '▲' if r.get('slope_up') else '▼'
        cmf_s = f'{r.get("cmf", 0.0):+.2f}'
        rs_v  = r.get('rs')
        rs_s  = f'{rs_v:.2f}x' if rs_v is not None else '  —  '
        hi_s  = f'{r.get("pct_from_high", 0.0):+.1f}%'
        print(f"  {t:<8} {r['s']}/4  ${r['p']:>7.2f}  {flag}{r['st_spread']:>+5.1f}%"
              f"  {slp_s}  {cmf_s:>6}  {rs_s:>6}  {hi_s:>6}  ${r['ma10w']:>7.2f} ${r['ma20w']:>7.2f}  {r['w_spread']:>+7.1f}%  [{src}]")

    print(f"\n  ● |<2%| very tight   ○ |2-4%| building   + = bullish MA order   - = bearish   FullCoil = signed 10w-50w spread   CMF >+0.10 accum  <-0.10 distrib   RS vs SPY 13w")

    # ── Daily Squeeze CLI ────────────────────────────────────────────────────
    print(f"\n  DAILY SQUEEZE — 10d/20d/35d/50d MA compression  ({now})")
    print(f"  {'─'*78}")
    print(f"  {'Ticker':<9} {'WkMA':<5} {'Price':>8}  {'Spread':>7}  {'Slp'}  {'CMF':>6}  {'offHi':>6}  {'10d':>8} {'20d':>8} {'35d':>8} {'50d':>8}")
    print(f"  {'─'*9} {'─'*5} {'─'*8}  {'─'*7}  {'─'*3}  {'─'*6}  {'─'*6}  {'─'*8} {'─'*8} {'─'*8} {'─'*8}")
    for r in daily_squeezed[:20]:
        t     = r['t']
        src   = 'U' if t in UNIVERSE else ('W' if t in WATCHLIST else 'X')
        flag  = '●' if r['d_spread'] < 3.0 else ('○' if r['d_spread'] < 5.0 else ' ')
        slp_s = '▲' if r.get('slope_up') else '▼'
        ws    = ws_map.get(t, 0)
        star  = '★' if t in mtf_set else ' '
        hi    = hi_map.get(t, 0.0)
        cmf   = r.get('cmf', 0.0)
        print(f"  {star}{t:<8} {ws}/4  ${r['p']:>8.2f}  {flag}{r['d_spread']:>+6.1f}%  {slp_s}  {cmf:>+6.2f}  {hi:>+5.1f}%"
              f"  ${r['ma10d']:>7.2f} ${r['ma20d']:>7.2f} ${r['ma35d']:>7.2f} ${r['ma50d']:>7.2f}  [{src}]")
    print(f"\n  ● |<3%| very tight   ○ |3-5%| building   + bullish MA order   - bearish   CMF 20-day   ★ = MTF (all 3 TFs tight)   (top 20 shown)")

    # ── Monthly Squeeze CLI ──────────────────────────────────────────────────
    print(f"\n  MONTHLY SQUEEZE — 3m/6m/10m/20m MA compression  ({now})")
    print(f"  {'─'*78}")
    print(f"  {'Ticker':<9} {'WkMA':<5} {'Price':>8}  {'Spread':>7}  {'Slp'}  {'CMF':>6}  {'offHi':>6}  {'3m':>8} {'6m':>8} {'10m':>8} {'20m':>8}")
    print(f"  {'─'*9} {'─'*5} {'─'*8}  {'─'*7}  {'─'*3}  {'─'*6}  {'─'*6}  {'─'*8} {'─'*8} {'─'*8} {'─'*8}")
    for r in monthly_squeezed[:20]:
        t     = r['t']
        src   = 'U' if t in UNIVERSE else ('W' if t in WATCHLIST else 'X')
        flag  = '●' if r['m_spread'] < 3.0 else ('○' if r['m_spread'] < 5.0 else ' ')
        slp_s = '▲' if r.get('slope_up') else '▼'
        ws    = ws_map.get(t, 0)
        star  = '★' if t in mtf_set else ' '
        hi    = hi_map.get(t, 0.0)
        cmf   = r.get('cmf', 0.0)
        print(f"  {star}{t:<8} {ws}/4  ${r['p']:>8.2f}  {flag}{r['m_spread']:>+6.1f}%  {slp_s}  {cmf:>+6.2f}  {hi:>+5.1f}%"
              f"  ${r['ma3m']:>7.2f} ${r['ma6m']:>7.2f} ${r['ma10m']:>7.2f} ${r['ma20m']:>7.2f}  [{src}]")
    print(f"\n  ● |<3%| very tight   ○ |3-5%| building   + bullish MA order   - bearish   CMF 6-month   ★ = MTF (all 3 TFs tight)   (top 20 shown)")

    # ── MTF Summary CLI ──────────────────────────────────────────────────────
    if mtf_set:
        print(f"\n  ★ MULTI-TIMEFRAME SQUEEZE — {len(mtf_set)} names (Daily + Weekly + Monthly all tight)")
        print(f"  {'─'*60}")
        for t in sorted(mtf_set):
            ws  = ws_map.get(t, 0)
            src = 'U' if t in UNIVERSE else ('W' if t in WATCHLIST else 'X')
            print(f"  ★  [{src}]  {t:8}  {ws}/4 weekly MA")
    else:
        print(f"\n  ★ MULTI-TIMEFRAME SQUEEZE — 0 names  (rarest signal — none this week)")

    print(f"\n  [U] = Universe   [W] = Watchlist   [X] = Extra\n")

    # ── HTML output ──────────────────────────────────────────────────────────
    import subprocess
    html     = build_aligned_html(valid, aligned, grades, partial, promos,
                                  squeezed, st_squeezed, rs_map, hi_map, cmf_map,
                                  combined_sm, now, UNIVERSE, WATCHLIST, m_cmf_map,
                                  daily_squeezed, monthly_squeezed, mtf_set,
                                  pullback_watch=pullback_watch)
    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'aligned_screener.html')
    with open(out_path, 'w') as f:
        f.write(html)
    print(f"  Saved → {out_path}")
    import platform
    if platform.system() == 'Darwin':
        subprocess.Popen(['open', out_path])

    # Auto-push aligned_screener.html to GitHub after every run
    try:
        repo = os.path.dirname(out_path)
        commit_msg = f"aligned_screener: {now}"
        subprocess.run(['git', 'checkout', '--', 'aligned_screener.html'], cwd=repo, capture_output=True)
        subprocess.run(['git', 'pull', '--rebase', 'origin', 'main'], cwd=repo, check=True, capture_output=True)
        with open(out_path, 'w') as f:
            f.write(html)  # re-write after pull overwrites the file
        subprocess.run(['git', 'add', 'aligned_screener.html'], cwd=repo, check=True, capture_output=True)
        subprocess.run(['git', 'commit', '-m', commit_msg],     cwd=repo, check=True, capture_output=True)
        subprocess.run(['git', 'push'],                          cwd=repo, check=True, capture_output=True)
        print(f"  Pushed → GitHub  ({commit_msg})")
    except subprocess.CalledProcessError as e:
        # Nothing new to commit or push failed — not fatal
        msg = e.stderr.decode().strip() if e.stderr else str(e)
        print(f"  Git push skipped: {msg or 'nothing new to commit'}")
