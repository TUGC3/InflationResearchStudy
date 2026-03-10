"""
inflation.py — Bauhaus Daily Inflation Calculator

This script reads the raw daily CSV outputs from the Bauhaus scraper
and computes the percentage inflation (price change) for each product
over 1-day, 7-day, 15-day, and 30-day trailing windows.

It outputs a detailed row-by-row CSV of inflation per product, as well
as appending to a summary CSV that tracks average daily inflation.
"""

import logging
from datetime import datetime, timedelta
import pandas as pd
import sys
import os
from pathlib import Path

# Fix relative imports depending on how this script is run
try:
    # If run directly from Inflations/Codes/ConstructionSuppliesMarkets/Bauhaus/
    scraper_dir = Path(__file__).resolve().parent.parent.parent.parent.parent / "InflationItems" / "Codes" / "ConstructionSuppliesMarkets" / "Bauhaus" / "scripts"
    sys.path.append(str(scraper_dir))
    import config
    OUTPUT_DIR = Path(config.OUTPUT_DIR)
except Exception:
    # Fallback to absolute if the structure is known
    base = Path(__file__).resolve().parent.parent.parent.parent.parent
    OUTPUT_DIR = base / "InflationItems" / "Datas" / "ConstructionSuppliesMarkets" / "Bauhaus"

logger = logging.getLogger(__name__)

def calculate_inflation(target_date=None):
    """Calculates inflation for the Bauhaus data based on 1-day, 7-day, 15-day, and 30-day intervals.
    
    Reads today's scraped CSV file, finds historical CSVs, calculates the percentage price change
    for each product based on its 'id', and outputs a new combined CSV file containing the inflation data
    along with a summary CSV for the daily average inflation.
    """
    if target_date:
        today_str = target_date
        base_date = datetime.strptime(target_date, "%Y-%m-%d")
    else:
        base_date = datetime.today()
        today_str = base_date.strftime("%Y-%m-%d")
        
    today_file = OUTPUT_DIR / f"bauhaus_{today_str}.csv"
    
    if not today_file.exists():
        logger.warning(f"Today's data file not found: {today_file}. Cannot calculate inflation.")
        return

    logger.info(f"Loading today's CSV for inflation calculation: {today_file}")
    
    try:
        df_today = pd.read_csv(today_file)
    except Exception as e:
        logger.error(f"Failed to read today's CSV: {e}")
        return

    df_today['shown_price'] = pd.to_numeric(df_today['shown_price'], errors='coerce')
    
    intervals = [1, 7, 15, 30]
    summary_data = {'date': [today_str]}
    
    for days in intervals:
        past_date = (base_date - timedelta(days=days)).strftime("%Y-%m-%d")
        past_file = OUTPUT_DIR / f"bauhaus_{past_date}.csv"
        
        col_name = f"inflation_{days}d_pct"
        
        if not past_file.exists():
            logger.info(f"No historical data found for {days} days ago ({past_file}). Skipping interval.")
            df_today[col_name] = None
            summary_data[f"avg_{col_name}"] = [None]
            continue
            
        logger.info(f"Loading historical data from {days} days ago: {past_file}")
        try:
            df_past = pd.read_csv(past_file)
            df_past['shown_price'] = pd.to_numeric(df_past['shown_price'], errors='coerce')
            
            # Keep only id and shown_price for merging
            df_past_subset = df_past[['id', 'shown_price']].rename(columns={'shown_price': f'past_price_{days}d'})
            
            # Merge on product id
            df_today = df_today.merge(df_past_subset, on='id', how='left')
            
            # Calculate percentage change: ((current - past) / past) * 100
            df_today[col_name] = ((df_today['shown_price'] - df_today[f'past_price_{days}d']) / df_today[f'past_price_{days}d']) * 100
            
            # Calculate average inflation for the day (excluding NaNs and infinities)
            avg_inflation = df_today[col_name].replace([float('inf'), float('-inf')], pd.NA).mean()
            summary_data[f"avg_{col_name}"] = [avg_inflation]
            
            # Drop the intermediate historical price column
            df_today = df_today.drop(columns=[f'past_price_{days}d'])
            
        except Exception as e:
            logger.error(f"Error processing historical data {past_file}: {e}")
            df_today[col_name] = None
            summary_data[f"avg_{col_name}"] = [None]

    # Output to the Inflations/Datas hierarchy
    project_inflations_dir = Path(__file__).resolve().parent.parent.parent.parent
    inflation_dir = project_inflations_dir / "Datas" / "ConstructionSuppliesMarkets" / "Bauhaus"
    inflation_dir.mkdir(parents=True, exist_ok=True)

    # Save detailed data
    output_inflation_file = inflation_dir / f"bauhaus_inflation_{today_str}.csv"
    df_today.to_csv(output_inflation_file, index=False, encoding='utf-8')
    logger.info(f"Saved detailed inflation data to: {output_inflation_file}")
    
    # Save/Append summary data
    summary_file = inflation_dir / "inflation_summary.csv"
    df_summary = pd.DataFrame(summary_data)
    
    try:
        if summary_file.exists():
            df_existing = pd.read_csv(summary_file)
            # Remove any existing entry for today's date
            df_existing = df_existing[df_existing['date'] != today_str]
            # Append new data
            df_final = pd.concat([df_existing, df_summary], ignore_index=True)
            df_final.to_csv(summary_file, index=False, encoding='utf-8')
            logger.info(f"Updated daily inflation summary in: {summary_file}")
        else:
            df_summary.to_csv(summary_file, index=False, encoding='utf-8')
            logger.info(f"Created daily inflation summary in: {summary_file}")
    except Exception as e:
        logger.error(f"Failed to write summary file: {e}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", help="Target date in YYYY-MM-DD format", default=None)
    args = parser.parse_args()

    # Configure basic logging for standalone execution
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    calculate_inflation(args.date)
