import os
import glob
import logging
from datetime import datetime, timedelta
import pandas as pd
from pathlib import Path

import config

logger = logging.getLogger(__name__)

def calculate_inflation():
    """Calculates inflation for the Koton data based on 1-day, 7-day, 15-day, and 30-day intervals.
    
    Reads today's scraped CSV file, finds historical CSVs, calculates the percentage price change
    for each product based on its 'pk', and outputs a new combined CSV file containing the inflation data
    along with a summary CSV for the daily average inflation.
    """
    output_dir = Path(config.OUTPUT_DIR)
    today_str = datetime.today().strftime("%Y-%m-%d")
    today_file = output_dir / f"koton_{today_str}.csv"
    
    if not today_file.exists():
        logger.warning(f"Today's data file not found: {today_file}. Cannot calculate inflation.")
        return

    logger.info(f"Loading today's CSV for inflation calculation: {today_file}")
    
    try:
        df_today = pd.read_csv(today_file)
    except Exception as e:
        logger.error(f"Failed to read today's CSV: {e}")
        return

    # Ensure 'sale_price' is numeric
    df_today['sale_price'] = pd.to_numeric(df_today['sale_price'], errors='coerce')
    
    intervals = [1, 7, 15, 30]
    summary_data = {'date': [today_str]}
    
    for days in intervals:
        past_date = (datetime.today() - timedelta(days=days)).strftime("%Y-%m-%d")
        past_file = output_dir / f"koton_{past_date}.csv"
        
        col_name = f"inflation_{days}d_pct"
        
        if not past_file.exists():
            logger.info(f"No historical data found for {days} days ago ({past_file}). Skipping interval.")
            df_today[col_name] = None
            summary_data[f"avg_{col_name}"] = [None]
            continue
            
        logger.info(f"Loading historical data from {days} days ago: {past_file}")
        try:
            df_past = pd.read_csv(past_file)
            df_past['sale_price'] = pd.to_numeric(df_past['sale_price'], errors='coerce')
            
            # Keep only pk and sale_price for merging
            df_past_subset = df_past[['pk', 'sale_price']].rename(columns={'sale_price': f'past_price_{days}d'})
            
            # Merge on product pk
            df_today = df_today.merge(df_past_subset, on='pk', how='left')
            
            # Calculate percentage change: ((current - past) / past) * 100
            df_today[col_name] = ((df_today['sale_price'] - df_today[f'past_price_{days}d']) / df_today[f'past_price_{days}d']) * 100
            
            # Calculate average inflation for the day (excluding NaNs and infinities)
            avg_inflation = df_today[col_name].replace([float('inf'), float('-inf')], pd.NA).mean()
            summary_data[f"avg_{col_name}"] = [avg_inflation]
            
            # Drop the intermediate historical price column
            df_today = df_today.drop(columns=[f'past_price_{days}d'])
            
        except Exception as e:
            logger.error(f"Error processing historical data {past_file}: {e}")
            df_today[col_name] = None
            summary_data[f"avg_{col_name}"] = [None]

    inflation_dir = Path(config.INFLATION_DIR)
    inflation_dir.mkdir(parents=True, exist_ok=True)

    # Save detailed data
    output_inflation_file = inflation_dir / f"koton_inflation_{today_str}.csv"
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
    # Configure basic logging for standalone execution
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    calculate_inflation()
