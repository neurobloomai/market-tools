#!/bin/bash
# Weekly auto-run — called by cron every Monday 8am
# Full chain: dashboard → quality screener → weekly snapshot → aligned screener (US + India)
# Dashboards run headless (no --browser flag) — auto-commit and push HTML to GitHub Pages

cd /Users/amarnath/neurobloomai/market-tools

# US
/Library/Developer/CommandLineTools/usr/bin/python3 dashboard.py              >> /tmp/aligned_cron.log 2>&1
/Library/Developer/CommandLineTools/usr/bin/python3 screener.py               >> /tmp/aligned_cron.log 2>&1
/Library/Developer/CommandLineTools/usr/bin/python3 weekly_snapshot.py        >> /tmp/aligned_cron.log 2>&1
/Library/Developer/CommandLineTools/usr/bin/python3 aligned_screener.py       >> /tmp/aligned_cron.log 2>&1

# India
/Library/Developer/CommandLineTools/usr/bin/python3 india_dashboard.py        >> /tmp/aligned_cron.log 2>&1
/Library/Developer/CommandLineTools/usr/bin/python3 india_screener.py         >> /tmp/aligned_cron.log 2>&1
/Library/Developer/CommandLineTools/usr/bin/python3 india_weekly_snapshot.py  >> /tmp/aligned_cron.log 2>&1
/Library/Developer/CommandLineTools/usr/bin/python3 india_aligned_screener.py >> /tmp/aligned_cron.log 2>&1
