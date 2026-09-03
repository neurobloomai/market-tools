#!/bin/bash
# Weekly auto-run — called by cron every Monday 8am
# Full chain: dashboard → quality screener → weekly snapshot → breadth → aligned screener (US + India)
# Dashboards run headless (no --browser flag) — auto-commit and push HTML to GitHub Pages

cd /Users/amarnath/neurobloomai/market-tools

# Suppress browser opens — webbrowser module respects BROWSER env var
export BROWSER=echo

# Schwab token preflight — abort if expired, notify if expiring soon
TOKEN_STATUS=$(/Users/amarnath/neurobloomai/market-tools/.venv/bin/python schwab_client.py --check 2>&1)
TOKEN_EXIT=$?
echo "$(date): $TOKEN_STATUS" >> /tmp/aligned_cron.log

if [ $TOKEN_EXIT -ne 0 ]; then
    echo "$(date): ABORT — Schwab token expired. Run: python schwab_client.py --auth" >> /tmp/aligned_cron.log
    osascript -e 'display notification "Schwab token EXPIRED — run: python schwab_client.py --auth" with title "market-tools ⚠" sound name "Basso"'
    exit 1
fi

# Notify if token expires within 24h (WARNING in output)
if echo "$TOKEN_STATUS" | grep -q "WARNING"; then
    HOURS=$(echo "$TOKEN_STATUS" | grep -oE '[0-9]+\.[0-9]+h')
    osascript -e "display notification \"Schwab token expires in $HOURS — reauth before next Monday run\" with title \"market-tools\" sound name \"Ping\""
fi

# US
/Library/Developer/CommandLineTools/usr/bin/python3 dashboard.py              >> /tmp/aligned_cron.log 2>&1
/Library/Developer/CommandLineTools/usr/bin/python3 screener.py               >> /tmp/aligned_cron.log 2>&1
/Library/Developer/CommandLineTools/usr/bin/python3 weekly_snapshot.py        >> /tmp/aligned_cron.log 2>&1
/Library/Developer/CommandLineTools/usr/bin/python3 market_breadth.py         >> /tmp/aligned_cron.log 2>&1
/Library/Developer/CommandLineTools/usr/bin/python3 aligned_screener.py       >> /tmp/aligned_cron.log 2>&1

# India
/Library/Developer/CommandLineTools/usr/bin/python3 india_dashboard.py        >> /tmp/aligned_cron.log 2>&1
/Library/Developer/CommandLineTools/usr/bin/python3 india_screener.py         >> /tmp/aligned_cron.log 2>&1
/Library/Developer/CommandLineTools/usr/bin/python3 india_weekly_snapshot.py  >> /tmp/aligned_cron.log 2>&1
/Library/Developer/CommandLineTools/usr/bin/python3 india_marketbreadth.py    >> /tmp/aligned_cron.log 2>&1
/Library/Developer/CommandLineTools/usr/bin/python3 india_aligned_screener.py >> /tmp/aligned_cron.log 2>&1
