#!/bin/bash
# Weekly auto-run — called by cron every Monday 8am
# Runs weekly snapshot + aligned screener, pushes both to GitHub

cd /Users/amarnath/neurobloomai/market-tools
/Library/Developer/CommandLineTools/usr/bin/python3 weekly_snapshot.py >> /tmp/aligned_cron.log 2>&1
/Library/Developer/CommandLineTools/usr/bin/python3 aligned_screener.py >> /tmp/aligned_cron.log 2>&1
