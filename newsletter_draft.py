"""
newsletter_draft.py — Auto-draft weekly newsletter from live data.
Sections: Posture · What Moved · Setups · Watchlist Watch · One Thought
Output: newsletter_draft.md

Run: python newsletter_draft.py
Requires: ANTHROPIC_API_KEY env var for One Thought section (skipped if absent).
"""

import os, json, re, warnings
from datetime import datetime, timedelta
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

warnings.filterwarnings('ignore')

import sys
sys.path.insert(0, '.')
from screener import UNIVERSE, WATCHLIST, get_fundamentals, quality_grade, failing_filters
from market_breadth import compute_breadth
from ma_scanner import liquid_status, scan_ticker, LIQUID_NAMES

HISTORY_FILE = Path(__file__).parent / 'breadth_history.json'
SCREENER_SRC = Path(__file__).parent / 'screener.py'


# ── Helpers ───────────────────────────────────────────────────────────────────

def _posture_label(pct200):
    if pct200 >= 70: return 'Broad Rally'
    if pct200 >= 50: return 'Mixed'
    return 'Correcting'

def _breadth_descriptor(pct20, pct100):
    diff = pct100 - pct20
    if diff >= 8:  return 'Breadth Diverging'   # long-term intact, short-term pulling back
    if diff <= -8: return 'Short-term Leading'   # short-term outpacing long-term
    return 'Aligned'

def _parse_watchlist_notes():
    src = SCREENER_SRC.read_text()
    notes = {}
    for ticker in WATCHLIST:
        m = re.search(rf"^\s+'{re.escape(ticker)}',[ \t]+#[ \t]+(.+)$", src, re.MULTILINE)
        if m:
            notes[ticker] = m.group(1).strip()
    return notes


# ── Section builders ──────────────────────────────────────────────────────────

def build_posture(us_b, india_b):
    u20, u50, u100, u200 = us_b['pct20'], us_b['pct50'], us_b['pct100'], us_b['pct200']
    i20, i50, i100, i200 = india_b['pct20'], india_b['pct50'], india_b['pct100'], india_b['pct200']
    us_stacked    = len(us_b['stacked'])
    india_stacked = len(india_b['stacked'])

    us_posture    = _posture_label(u200)
    india_posture = _posture_label(i200)
    us_desc       = _breadth_descriptor(u20, u100)

    # Prose interpretation
    if u100 > u20:
        us_line = (f"US: {u20}% above MA20, {u100}% above MA100 — more names intact "
                   f"long-term than short-term. Short-term pullbacks within healthy structure. "
                   f"{us_stacked} names Fully Stacked.")
    else:
        us_line = (f"US: {u20}% above MA20, {u100}% above MA100 — short-term momentum "
                   f"leading. {us_stacked} names Fully Stacked.")

    india_line = (f"India: {i20}% above MA20, {i100}% above MA100 — "
                  f"{'broad strength' if i200 >= 70 else ('mixed, structure holding' if i200 >= 50 else 'correcting, structure under pressure')}. "
                  f"{india_stacked} names Fully Stacked.")

    return us_posture, india_posture, us_desc, f"{us_line} {india_line}"


def build_movements(history):
    if len(history) < 2:
        return [], [], "First run — no previous week to compare."

    TIER_ORDER = [
        'fully_stacked', 'trend_intact', 'stacked_100',
        'all4_up', 'ma20_50_100', 'ma20_50', 'ma20_only',
        'ma100_200', 'ma200_pullbk', 'none',
    ]
    prev = history[-2]['tiers']
    curr = history[-1]['tiers']

    fs_entered, fs_left = [], []
    for t, cur in curr.items():
        if t not in prev or prev[t] == cur:
            continue
        prev_t = prev[t]
        if cur == 'fully_stacked':
            fs_entered.append((t, prev_t))
        elif prev_t == 'fully_stacked':
            fs_left.append((t, cur))

    return fs_entered, fs_left, None


def build_setups():
    """Scan liquid names + full universe; surface weekly gate ✓ with -EXT or IN band."""
    print("  Scanning setups ...", flush=True)
    # Liquid names with detailed band/slope data
    with ThreadPoolExecutor(max_workers=8) as ex:
        liquid_rows = list(ex.map(liquid_status, LIQUID_NAMES))

    setups = []
    for row in liquid_rows:
        if row is None:
            continue
        sym, price, w_gate, pct20d, pct10w, m10w, m50d, band, slope = row
        if w_gate and band in ('IN', '-EXT') and slope is not None:
            setups.append(dict(ticker=sym, price=price, band=band,
                               pct10w=pct10w, slope=slope,
                               in_universe=sym in UNIVERSE))

    # Sort: -EXT first (pullback > in-band), then by slope desc
    setups.sort(key=lambda x: (0 if x['band'] == '-EXT' else 1, -x['slope']))
    return setups[:3]


def build_watchlist_watch():
    """Find watchlist name closest to promotion — fewest blockers or nearest gate."""
    print("  Fetching watchlist fundamentals ...", flush=True)
    with ThreadPoolExecutor(max_workers=10) as ex:
        funds = dict(zip(WATCHLIST, ex.map(get_fundamentals, WATCHLIST)))

    notes = _parse_watchlist_notes()
    candidates = []
    for t in WATCHLIST:
        f = funds.get(t)
        if not f:
            continue
        fails = failing_filters(f)
        if fails is not None:
            candidates.append((t, fails, notes.get(t, '')))

    # Closest = fewest failing filters (and among those, first alphabetically)
    candidates.sort(key=lambda x: (len(x[1]), x[0]))
    return candidates[:2]   # top 2 closest


def build_one_thought(posture_text, fs_entered, fs_left, setups, wl_watch, label):
    """Call Claude API for the interpretive paragraph. Returns template if no key."""
    api_key = os.environ.get('ANTHROPIC_API_KEY', '')
    if not api_key:
        return "_[ONE THOUGHT — add ANTHROPIC_API_KEY to generate this section]_"

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)

        entered_str = ', '.join(t for t, _ in fs_entered) if fs_entered else 'none'
        left_str    = ', '.join(t for t, _ in fs_left)    if fs_left    else 'none'
        setup_str   = ', '.join(s['ticker'] for s in setups) if setups else 'none'
        wl_str      = '; '.join(f"{t} ({len(f)} blocker{'s' if len(f)!=1 else ''})" for t, f, _ in wl_watch) if wl_watch else 'none'

        prompt = f"""You are writing the "One Thought" section of a weekly market newsletter for context-driven investors (not signal-seekers).

Week: {label}
Posture summary: {posture_text}
Fully Stacked entered: {entered_str}
Fully Stacked left: {left_str}
Top setups (weekly gate open, near MA): {setup_str}
Watchlist closest to promotion: {wl_str}

Write ONE short paragraph (3-5 sentences). This is NOT a buy/sell recommendation. It is an observation about what the data says together — the thing that took judgment to notice. Frame it as context, not a signal. No hype, no hedging, no "this week's theme is...". Just a clean, direct observation that a thoughtful investor would find useful. Do not start with "This week"."""

        msg = client.messages.create(
            model='claude-haiku-4-5-20251001',
            max_tokens=200,
            messages=[{'role': 'user', 'content': prompt}],
        )
        return msg.content[0].text.strip()
    except Exception as e:
        return f"_[ONE THOUGHT generation failed: {e}]_"


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    now    = datetime.utcnow()
    monday = now - timedelta(days=now.weekday())
    label  = monday.strftime('Week of %b %d %Y')

    print(f"\n  Newsletter Draft — {label}")

    # ── Breadth ───────────────────────────────────────────────────────────────
    print("  Computing US breadth ...", flush=True)
    us_b = compute_breadth(UNIVERSE)

    print("  Computing India breadth ...", flush=True)
    from india_screener import UNIVERSE as INDIA_UNIVERSE
    from india_marketbreadth import compute_breadth as india_compute_breadth
    india_b = india_compute_breadth(INDIA_UNIVERSE)

    # ── History ───────────────────────────────────────────────────────────────
    history = json.loads(HISTORY_FILE.read_text()) if HISTORY_FILE.exists() else []

    # ── Build sections ────────────────────────────────────────────────────────
    us_posture, india_posture, us_desc, posture_text = build_posture(us_b, india_b)
    fs_entered, fs_left, _ = build_movements(history)
    setups    = build_setups()
    wl_watch  = build_watchlist_watch()

    print("  Generating One Thought ...", flush=True)
    one_thought = build_one_thought(posture_text, fs_entered, fs_left, setups, wl_watch, label)

    # ── Subject line ──────────────────────────────────────────────────────────
    subject = f"Market Pulse — {label} · {us_posture} / {us_desc}"

    # ── Render ────────────────────────────────────────────────────────────────
    TIER_LABEL = {
        'fully_stacked': 'Fully Stacked', 'trend_intact': 'Trend Intact',
        'stacked_100': 'Intermediate', 'all4_up': 'All4',
        'ma20_50_100': 'MA50+100', 'ma20_50': 'MA50',
        'ma20_only': 'MA20 only', 'ma100_200': 'MA100+MA200',
        'ma200_pullbk': 'MA200 only', 'none': 'Below all',
    }

    lines = [
        f'**Subject:** {subject}\n',
        '---\n',

        '**POSTURE**\n',
        f'{posture_text}\n',
        '',

        '**WHAT MOVED**\n',
    ]

    if fs_entered:
        u = [t for t, _ in fs_entered if t in UNIVERSE]
        w = [t for t, _ in fs_entered if t not in UNIVERSE]
        if u: lines.append(f'Entered Fully Stacked — Universe: {", ".join(u)}')
        if w: lines.append(f'Entered Fully Stacked — Watchlist: {", ".join(w)}')
    else:
        lines.append('No new Fully Stacked entries this week.')

    if fs_left:
        u = [t for t, _ in fs_left if t in UNIVERSE]
        w = [t for t, _ in fs_left if t not in UNIVERSE]
        if u: lines.append(f'Left Fully Stacked — Universe: {", ".join(u)}')
        if w: lines.append(f'Left Fully Stacked — Watchlist: {", ".join(w)}')
    else:
        lines.append('No exits from Fully Stacked.')

    lines += ['', '**SETUPS WORTH WATCHING**\n']
    if setups:
        for s in setups:
            tag   = 'Universe' if s['in_universe'] else 'Watchlist'
            lines.append(
                f"**{s['ticker']}** [{tag}] — weekly gate open, {s['band']}, "
                f"{s['pct10w']:+.1f}% vs MA10w, W.slope {s['slope']:+.2f}"
            )
    else:
        lines.append('No setups with weekly gate open and band in range this week.')

    lines += ['', '**WATCHLIST WATCH**\n']
    if wl_watch:
        notes = _parse_watchlist_notes()
        for t, fails, note in wl_watch:
            blockers = ' / '.join(f"{n} {v}" for n, v, _ in fails) if fails else 'all gates cleared'
            short_note = (note[:80] + '…') if len(note) > 80 else note
            lines.append(f"**{t}** — {blockers}. _{short_note}_")
    else:
        lines.append('No watchlist names approaching gate this week.')

    lines += [
        '',
        '**ONE THOUGHT**\n',
        one_thought,
        '',
        '---\n',
        f'→ Full context: [neurobloom.ai](https://neurobloom.ai)',
        '',
        f'_Draft generated {datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")} · Not financial advice_',
    ]

    md = '\n'.join(lines)

    out = Path(__file__).parent / 'newsletter_draft.md'
    out.write_text(md)
    print(f"\n  Written → newsletter_draft.md")
    print(f"  Subject: {subject}")
    print(f"\n{'─'*60}")
    print(md)
    print(f"{'─'*60}\n")
