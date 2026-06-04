#!/usr/bin/env python3
"""
Quarterly Screener Review
Re-evaluates qualification status across quality screeners. Reports watchlist
promotions and universe demotions. Requires confirmation before modifying
source files or committing to git.

Run:                  python quarterly_review.py
Non-interactive mode: python quarterly_review.py --no-interactive
  Applies all promotions automatically, skips git steps (for remote/CI use).
"""

import importlib.util, re, subprocess, sys, warnings
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

NON_INTERACTIVE = '--no-interactive' in sys.argv

warnings.filterwarnings('ignore')

MARKET_TOOLS = Path(__file__).resolve().parent


# ── Module Loader ─────────────────────────────────────────────────────────────

def load_module(filename):
    path = MARKET_TOOLS / filename
    spec = importlib.util.spec_from_file_location(Path(filename).stem, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ── Source File Patching ──────────────────────────────────────────────────────

def add_to_universe(filepath, tickers, label):
    """Append promoted tickers to UNIVERSE list before the closing ]."""
    lines = Path(filepath).read_text().splitlines(keepends=True)
    in_universe, insert_idx = False, None
    for i, line in enumerate(lines):
        if re.match(r'\s*UNIVERSE\s*=\s*\[', line):
            in_universe = True
        elif in_universe and re.match(r'\s*\]\s*$', line):
            insert_idx = i
            break
    if insert_idx is None:
        print(f"  ⚠  Could not locate UNIVERSE closing bracket in {filepath.name}")
        return False
    ticker_str = ', '.join(f"'{t}'" for t in tickers)
    lines.insert(insert_idx, f"    {ticker_str},   # promoted {label}\n")
    Path(filepath).write_text(''.join(lines))
    return True


def remove_from_watchlist(filepath, tickers):
    """Remove ticker entries from WATCHLIST. Handles both solo and grouped lines."""
    text = Path(filepath).read_text()
    match = re.search(r'(WATCHLIST\s*=\s*\[)(.*?)(\n\s*\])', text, re.DOTALL)
    if not match:
        print(f"  ⚠  Could not locate WATCHLIST in {filepath.name}")
        return []

    block = match.group(2)
    removed = []
    for t in tickers:
        # Try removing whole line if ticker is alone on it (preserves other lines' comments)
        pattern_solo = rf"\n[ \t]*['\"]({re.escape(t)})['\"],?[ \t]*(#[^\n]*)?"
        new_block, n = re.subn(pattern_solo, '', block)
        if n:
            block = new_block
            removed.append(t)
        else:
            # Ticker is grouped with others — remove just the token
            pattern_inline = rf"['\"]({re.escape(t)})['\"],?[ \t]*"
            new_block, n = re.subn(pattern_inline, '', block)
            if n:
                block = new_block
                removed.append(t)

    new_text = text[:match.start(2)] + block + text[match.end(2):]
    Path(filepath).write_text(new_text)
    return removed


# ── Review Logic ──────────────────────────────────────────────────────────────

def review_quality_screener(mod, label):
    universe = mod.UNIVERSE
    watchlist = getattr(mod, 'WATCHLIST', [])
    all_tickers = list(dict.fromkeys(universe + watchlist))

    print(f"\n  Fetching {len(all_tickers)} tickers for {label} ...", flush=True)
    with ThreadPoolExecutor(max_workers=15) as ex:
        raw = list(ex.map(mod.get_fundamentals, all_tickers))

    data = {d['ticker']: d for d in raw if d is not None}
    errors = [t for t in all_tickers if t not in data]

    # Universe members that no longer pass
    failing_universe = [
        t for t in universe
        if t not in data or not mod.passes_quality_filter(data.get(t))
    ]
    # Watchlist members that now pass — ready to promote
    promoting = [
        t for t in watchlist
        if t in data and mod.passes_quality_filter(data[t])
    ]

    return dict(
        label=label, universe=universe, watchlist=watchlist,
        failing_universe=failing_universe, promoting=promoting,
        data=data, errors=errors, mod=mod,
    )


def review_delever_screener(mod):
    universe = mod.UNIVERSE
    print(f"\n  Fetching {len(universe)} tickers for De-lever Screener ...", flush=True)
    with ThreadPoolExecutor(max_workers=15) as ex:
        raw = list(ex.map(mod.get_fundamentals, universe))

    data = {d['ticker']: d for d in raw if d is not None}
    errors = [t for t in universe if t not in data]
    passing = [t for t in universe if t in data and mod.passes_filter(data[t])]
    failing = [t for t in universe if t in data and not mod.passes_filter(data[t])]
    monitor = [t for t in universe if t in data and mod.passes_monitor(data.get(t))]

    return dict(
        label='De-lever Screener', universe=universe,
        passing=passing, failing=failing, monitor=monitor,
        data=data, errors=errors,
    )


# ── Reporting ─────────────────────────────────────────────────────────────────

SEP = '─' * 56

def print_quality_report(r):
    print(f"\n  {SEP}")
    print(f"  {r['label']}  ({len(r['universe'])} universe · {len(r['watchlist'])} watchlist)")
    print(f"  {SEP}")

    if r['promoting']:
        print(f"\n  ✅  PROMOTE to UNIVERSE  ({len(r['promoting'])})")
        for t in r['promoting']:
            d = r['data'][t]
            print(f"      {t:<12}  OpM:{d['operating_margin']}%  NetM:{d['net_margin']}%  "
                  f"ROE:{d['roe']}%  FCF:{d['fcf_yield']}%  PE:{d['pe']}x")
    else:
        print(f"\n  ✅  No watchlist promotions.")

    if r['failing_universe']:
        print(f"\n  ⚠   FAILING in UNIVERSE  ({len(r['failing_universe'])}) — review manually:")
        for t in r['failing_universe']:
            d = r['data'].get(t)
            if d:
                fails = r['mod'].failing_filters(d)
                blockers = '  '.join(
                    f"{f[0]}:{f[1]}→{f[2]}" for f in fails if f[0] != 'Passes all filters'
                )
                print(f"      {t:<12}  {blockers}")
            else:
                print(f"      {t:<12}  no data")
    else:
        print(f"  ✅  All universe members qualify.")

    if r['errors']:
        print(f"\n  ⚠   Data errors: {', '.join(r['errors'])}")


def print_delever_report(r):
    print(f"\n  {SEP}")
    print(f"  {r['label']}  ({len(r['universe'])} universe)")
    print(f"  {SEP}")
    print(f"\n  Passing: {len(r['passing'])}  |  Monitor: {len(r['monitor'])}  |  "
          f"No longer qualifying: {len(r['failing'])}")

    if r['failing']:
        print(f"\n  ⚠   No longer qualifying  ({len(r['failing'])}) — review manually:")
        for t in r['failing']:
            d = r['data'].get(t)
            if d:
                print(f"      {t:<12}  D/EV:{d['debt_to_ev']}  FCF:{d['fcf_yield']}%  "
                      f"NetM:{d['net_margin']}%  RevGrw:{d['rev_growth']}%")
    else:
        print(f"  ✅  All universe members qualify.")

    if r['errors']:
        print(f"\n  ⚠   Data errors: {', '.join(r['errors'])}")


# ── Git Helpers ───────────────────────────────────────────────────────────────

def git(args, capture=True):
    r = subprocess.run(['git'] + args, cwd=MARKET_TOOLS,
                       capture_output=capture, text=True)
    return r


def show_diff():
    diff = git(['diff']).stdout.strip()
    if diff:
        print(f"\n  Git diff:\n")
        for line in diff.splitlines():
            print(f"  {line}")
    return bool(diff)


# ── Confirmation ──────────────────────────────────────────────────────────────

def confirm(prompt):
    if NON_INTERACTIVE:
        print(f"\n  [auto-yes] {prompt}")
        return True
    try:
        return input(f"\n  {prompt} [y/N] ").strip().lower() == 'y'
    except (EOFError, KeyboardInterrupt):
        print()
        return False


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    now = datetime.now()
    quarter = f"Q{(now.month - 1) // 3 + 1} {now.year}"

    print(f"\n  ╔══════════════════════════════════════════════╗")
    print(f"  ║  Quarterly Screener Review — {quarter:<15}║")
    print(f"  ╚══════════════════════════════════════════════╝")

    us_mod     = load_module('screener.py')
    india_mod  = load_module('india_screener.py')
    delever_mod = load_module('delever_screener.py')

    us     = review_quality_screener(us_mod,    'US Quality Screener')
    india  = review_quality_screener(india_mod, 'India Quality Screener')
    delever = review_delever_screener(delever_mod)

    print_quality_report(us)
    print_quality_report(india)
    print_delever_report(delever)

    total_promotions = len(us['promoting']) + len(india['promoting'])
    total_failing    = len(us['failing_universe']) + len(india['failing_universe']) + len(delever['failing'])

    print(f"\n  {'═' * 56}")
    print(f"  {total_promotions} promotion(s) ready  |  {total_failing} demotion(s) to review")
    print(f"  {'═' * 56}")

    if total_promotions == 0 and total_failing == 0:
        print(f"\n  No changes needed. Screeners are up to date.\n")
        return

    # ── Apply file changes ────────────────────────────────────────────────────

    has_changes = False

    for result, filename in [(us, 'screener.py'), (india, 'india_screener.py')]:
        if not result['promoting']:
            continue
        tickers_str = ', '.join(result['promoting'])
        if confirm(f"Promote {tickers_str} → UNIVERSE in {filename}?"):
            fp = MARKET_TOOLS / filename
            add_to_universe(fp, result['promoting'], quarter)
            removed = remove_from_watchlist(fp, result['promoting'])
            print(f"  ✅  {filename}: promoted {removed}, removed from WATCHLIST.")
            has_changes = True

    if us['failing_universe'] or india['failing_universe'] or delever['failing']:
        print(f"\n  ℹ   Failing entries above are NOT auto-removed — edit manually when ready.")

    if not has_changes:
        print(f"\n  No file changes applied.\n")
        return

    # ── Git commit + push ─────────────────────────────────────────────────────

    show_diff()

    if NON_INTERACTIVE:
        print(f"\n  Changes written. Skipping git steps — caller is responsible for commit/PR.\n")
        return

    commit_msg = f"quarterly: promote screener tickers — {quarter}"
    if confirm(f"Commit? ('{commit_msg}')"):
        git(['add', 'screener.py', 'india_screener.py'])
        r = git(['commit', '-m', commit_msg], capture=False)
        if r.returncode == 0:
            print(f"  ✅  Committed.")
            if confirm("Push to remote?"):
                r = git(['push'], capture=False)
                if r.returncode != 0:
                    print(f"  ✗   Push failed — check remote.")
        else:
            print(f"  ✗   Commit failed.")

    print()


if __name__ == '__main__':
    main()
