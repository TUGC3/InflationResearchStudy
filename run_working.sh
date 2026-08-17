#!/bin/bash

cd /root/InflationResearchStudy || exit 1
source venv/bin/activate

mkdir -p logs
DATE=$(date +%Y-%m-%d)
LOG="logs/daily_all_${DATE}.log"

# Clean up stale browser processes left from previous runs
pkill -f chromedriver 2>/dev/null || true
pkill -f "/opt/google/chrome/chrome" 2>/dev/null || true
sleep 2

echo "===== DAILY ALL-96 SCRAPE START: $(date) =====" | tee -a "$LOG"

python run_all_scrapers.py --run --all 2>&1 | tee -a "$LOG"

echo "===== DAILY ALL-96 SCRAPE END: $(date) =====" | tee -a "$LOG"
