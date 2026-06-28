#!/bin/bash
# Weekly auto-run — called by cron every Monday 8am
# Full chain: quality screener → weekly snapshot → aligned screener (US + India)
# Dashboard (dashboard.py / india_dashboard.py) runs manually — requires display

cd /Users/amarnath/neurobloomai/market-tools

# US
/Library/Developer/CommandLineTools/usr/bin/python3 screener.py               >> /tmp/aligned_cron.log 2>&1
/Library/Developer/CommandLineTools/usr/bin/python3 weekly_snapshot.py        >> /tmp/aligned_cron.log 2>&1
/Library/Developer/CommandLineTools/usr/bin/python3 aligned_screener.py       >> /tmp/aligned_cron.log 2>&1

# India
/Library/Developer/CommandLineTools/usr/bin/python3 india_screener.py         >> /tmp/aligned_cron.log 2>&1
/Library/Developer/CommandLineTools/usr/bin/python3 india_weekly_snapshot.py  >> /tmp/aligned_cron.log 2>&1
/Library/Developer/CommandLineTools/usr/bin/python3 india_aligned_screener.py >> /tmp/aligned_cron.log 2>&1
