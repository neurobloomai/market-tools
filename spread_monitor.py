#!/usr/bin/env python3
"""
spread_monitor.py — Open spread position monitor + exit signal engine

Reads positions.json, checks current market conditions, and flags exit signals.
Does NOT execute trades — signals are advisory. Execute manually on Fidelity/Schwab,
then set status to "closed" in positions.json.

Exit rules (checked in priority order):
  1. VIX ≥ 28          → EXIT ALL   (regime shifts to DEFENSE — vol expansion kills credit spreads)
  2. DTE ≤ 1           → EXIT       (pin risk + potential assignment)
  3. P&L ≥ 50% target  → EXIT       (spread clock — theta edge is captured, don't give it back)
  4. Loss ≥ 2× credit  → EXIT       (stop loss — a loser should not become a disaster)

Run:  python spread_monitor.py
Auto: spread_monitor.yml runs weekdays 7pm UTC (3pm ET) — 1hr before close, liquid prices

Execution hook: future Schwab auto-close layer goes in execute_close() below.
"""

import json
import warnings
from datetime import date, datetime
from pathlib import Path

import yfinance as yf
warnings.filterwarnings('ignore')

POSITIONS_FILE      = Path(__file__).parent / 'positions.json'
VIX_EXIT_THRESHOLD  = 28.0   # DEFENSE regime boundary
PROFIT_TARGET_PCT   = 0.50   # close at 50% of max profit
LOSS_LIMIT_MULTIPLE = 2.0    # close if loss exceeds 2× the credit/debit
DTE_FLOOR           = 1      # close if ≤ 1 DTE


# ── Data fetchers ─────────────────────────────────────────────────────────────

def get_vix():
    try:
        info = yf.Ticker("^VIX").fast_info
        v = info.get('lastPrice') or info.get('last_price')
        return float(v) if v else None
    except Exception:
        return None


def get_option_mid(ticker, expiry, strike, option_type):
    """Bid/ask mid for a specific strike. option_type: 'calls' or 'puts'."""
    try:
        df = getattr(yf.Ticker(ticker).option_chain(expiry), option_type).copy()
        df['_d'] = (df['strike'] - float(strike)).abs()
        row = df.loc[df['_d'].idxmin()]
        bid, ask = float(row['bid']), float(row['ask'])
        if bid <= 0 and ask <= 0:
            return float(row['lastPrice'])
        if bid <= 0:
            return ask
        return round((bid + ask) / 2, 3)
    except Exception:
        return None


def get_spread_value(pos):
    """Current mark-to-market value of the spread (per share)."""
    t, exp, st, lt = pos['ticker'], pos['expiry'], pos['short_strike'], pos['long_strike']
    if pos['type'] == 'bull_put':
        sm = get_option_mid(t, exp, st, 'puts')
        lm = get_option_mid(t, exp, lt, 'puts')
        return round(sm - lm, 3) if sm is not None and lm is not None else None
    if pos['type'] == 'bull_call':
        lm = get_option_mid(t, exp, lt, 'calls')
        sm = get_option_mid(t, exp, st, 'calls')
        return round(lm - sm, 3) if lm is not None and sm is not None else None
    return None


# ── P&L logic ─────────────────────────────────────────────────────────────────

def compute_pnl(pos, current_value):
    """Returns (pnl_per_share, max_profit). Positive pnl = profit."""
    ev = pos['entry_value']
    if pos['type'] == 'bull_put':
        return round(ev - current_value, 3), round(ev, 3)
    width = abs(pos['short_strike'] - pos['long_strike'])
    return round(current_value - ev, 3), round(width - ev, 3)


def exit_signals(pos, current_value, vix, dte):
    """Returns list of triggered exit reason strings."""
    signals = []

    if vix and vix >= VIX_EXIT_THRESHOLD:
        signals.append(f'VIX {vix:.1f} ≥ {VIX_EXIT_THRESHOLD:.0f} — regime shift to DEFENSE, EXIT ALL')

    if dte <= DTE_FLOOR:
        signals.append(f'DTE {dte} — pin/assignment risk, EXIT')

    if current_value is not None:
        pnl, max_profit = compute_pnl(pos, current_value)
        ev = pos['entry_value']

        if max_profit > 0:
            pnl_pct = pnl / max_profit * 100
            if pnl_pct >= PROFIT_TARGET_PCT * 100:
                signals.append(f'{pnl_pct:.0f}% of max profit captured (${pnl:.2f}/sh) — CLOSE')

        if pos['type'] == 'bull_put':
            if current_value > ev * (1 + LOSS_LIMIT_MULTIPLE):
                signals.append(f'Loss limit — spread ${current_value:.2f} vs ${ev:.2f} entry, > {LOSS_LIMIT_MULTIPLE:.0f}× credit — EXIT')
        else:
            loss = ev - current_value if current_value < ev else 0
            if loss >= ev * LOSS_LIMIT_MULTIPLE:
                signals.append(f'Loss limit — down ${loss:.2f}/sh (> {LOSS_LIMIT_MULTIPLE:.0f}× debit) — EXIT')

    return signals


# ── Execution hook (future Schwab layer) ──────────────────────────────────────

def execute_close(pos):
    """Placeholder for Schwab auto-close. Wire when execution stack is ready."""
    raise NotImplementedError('Schwab auto-close not yet wired — execute manually on Fidelity/Schwab')


# ── Helpers ───────────────────────────────────────────────────────────────────

def dte_of(expiry_str):
    return (date.fromisoformat(expiry_str) - date.today()).days


def vix_regime(vix):
    if vix is None: return '—'
    if vix < 20:    return 'BULL'
    if vix < 28:    return 'CAUTION'
    if vix < 35:    return 'DEFENSE'
    return 'STORM'


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    now_str = datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')
    print(f'SPREAD MONITOR — {now_str}')
    print('─' * 92)

    vix    = get_vix()
    regime = vix_regime(vix)
    print(f'VIX: {f"{vix:.1f}" if vix else "—"}  ({regime})')

    if vix and vix >= VIX_EXIT_THRESHOLD:
        print(f'  *** REGIME ALERT — VIX ≥ {VIX_EXIT_THRESHOLD:.0f}: EXIT ALL OPEN SPREADS NOW ***')

    if not POSITIONS_FILE.exists():
        print('\npositions.json not found. Create it and add spreads to start monitoring.')
        return

    with open(POSITIONS_FILE) as f:
        all_data = json.load(f)

    open_pos = [p for p in all_data.get('spreads', []) if p.get('status') == 'open']

    if not open_pos:
        print('\nNo open positions to monitor.')
        return

    print()
    print(f'{"TICKER":<7} {"TYPE":<10} {"EXPIRY":<12} {"DTE":>4}  '
          f'{"ENTRY":>7} {"CURR":>7} {"P&L/SH":>8} {"P&L%":>7}  STATUS')
    print('─' * 92)

    exit_count = 0
    updates    = {}

    for pos in open_pos:
        dte  = dte_of(pos['expiry'])
        curr = get_spread_value(pos)

        pnl, max_profit = compute_pnl(pos, curr) if curr is not None else (None, None)
        pnl_pct = (pnl / max_profit * 100) if (pnl is not None and max_profit and max_profit > 0) else None

        signals = exit_signals(pos, curr, vix, dte)
        flag    = '⚑ EXIT' if signals else '✓ hold'
        if signals:
            exit_count += 1

        curr_str    = f'${curr:>5.2f}' if curr is not None else '    —  '
        pnl_str     = f'${pnl:>+5.2f}' if pnl is not None else '    —  '
        pnl_pct_str = f'{pnl_pct:>+5.0f}%' if pnl_pct is not None else '    —  '

        print(f'{pos["ticker"]:<7} {pos["type"]:<10} {pos["expiry"]:<12} {dte:>4}  '
              f'${pos["entry_value"]:>5.2f}  {curr_str} {pnl_str} {pnl_pct_str}  {flag}')

        for s in signals:
            print(f'         → {s}')

        updates[pos['id']] = {
            'last_checked': now_str,
            'last_vix':     vix,
            'last_value':   curr,
            'last_pnl_pct': round(pnl_pct, 1) if pnl_pct is not None else None,
            'exit_flagged': bool(signals),
            'exit_reasons': signals,
        }

    print('─' * 92)

    if exit_count:
        print(f'\n{exit_count} EXIT signal(s) fired.')
        print('Execute manually on Fidelity/Schwab, then set status → "closed" in positions.json.')
    else:
        print('\nAll positions within hold range.')

    # Write last_checked status back
    for pos in all_data.get('spreads', []):
        if pos.get('id') in updates:
            pos.update(updates[pos['id']])
    with open(POSITIONS_FILE, 'w') as f:
        json.dump(all_data, f, indent=2)

    print(f'Updated positions.json — {len(updates)} position(s) checked.')


if __name__ == '__main__':
    main()
