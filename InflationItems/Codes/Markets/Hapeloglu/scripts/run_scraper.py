"""
Run the daily scraper.

Usage:
    cd hapeloglu-price-tracker/
    python -m scripts.run_scraper
"""

import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import OUTPUT_DIR
from src.utils import setup_logger
from src.scraper import scrape_all


def main():
    setup_logger()
    timestamp = datetime.now()

    df = scrape_all()
    if df.empty:
        print("No products scraped. Check logs.")
        return

    df["scrape_date"] = timestamp.strftime("%Y-%m-%d")
    df["scrape_timestamp"] = timestamp.isoformat()

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    filename = f"hapeloglu_{timestamp.strftime('%Y-%m-%d')}.csv"
    filepath = os.path.join(OUTPUT_DIR, filename)
    # Save CSV
    df.to_csv(filepath, index=False, encoding="utf-8-sig")

    # Save TSV
    tsv_filepath = filepath.replace(".csv", ".tsv")
    df.to_csv(tsv_filepath, index=False, encoding="utf-8-sig", sep="\t")

    print(f"\nDone! {len(df)} products -> {filepath}")
    print(f"TSV copy -> {tsv_filepath}")


if __name__ == "__main__":
    main()
