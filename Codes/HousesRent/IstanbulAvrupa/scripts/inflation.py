import os
import glob
import logging
from datetime import datetime, timedelta
import pandas as pd
from pathlib import Path

import config

logger = logging.getLogger(__name__)

def parse_price(price_str):
    """Convert a price string like '8.000 TL' to a float 8000.0."""
    try:
        if pd.isna(price_str):
            return None
        # Remove " TL", dots used as thousands separators, and any commas if they exist
        clean_str = str(price_str).replace(' TL', '').replace('.', '').strip()
        return float(clean_str)
    except Exception:
        return None

def calculate_inflation():
    """Calculates inflation for the IstanbulAvrupa data based on 1-day, 7-day, 15-day, and 30-day intervals.
    
    Reads today's scraped CSV file, finds historical CSVs, and calculates median prices 
    grouped by 'District' and 'Rooms'. Then calculates the percentage price change 
    for each group and outputs a new summarized CSV file containing the inflation data.
    """
    output_dir = Path(config.OUTPUT_DIR)
    folder_name = config.FOLDER_NAME # IstanbulAvrupa
    today_str = datetime.today().strftime("%Y-%m-%d")
    today_file = output_dir / f"{folder_name}_{today_str}.csv"
    
    if not today_file.exists():
        logger.warning(f"Today's data file not found: {today_file}. Cannot calculate inflation.")
        return

    logger.info(f"Loading today's CSV for inflation calculation: {today_file}")
    
    try:
        df_today = pd.read_csv(today_file)
    except Exception as e:
        logger.error(f"Failed to read today's CSV: {e}")
        return

    # Parse prices and calculate median per segment
    df_today['Price_Num'] = df_today['Price'].apply(parse_price)
    df_today_grouped = df_today.groupby(['District', 'Rooms'])['Price_Num'].median().reset_index()
    df_today_grouped.rename(columns={'Price_Num': 'Median_Price_Today'}, inplace=True)
    
    intervals = [1, 7, 15, 30]
    summary_data = {'date': [today_str]}
    
    for days in intervals:
        past_date = (datetime.today() - timedelta(days=days)).strftime("%Y-%m-%d")
        past_file = output_dir / f"{folder_name}_{past_date}.csv"
        
        col_name = f"inflation_{days}d_pct"
        
        if not past_file.exists():
            logger.info(f"No historical data found for {days} days ago ({past_file}). Skipping interval.")
            df_today_grouped[col_name] = None
            summary_data[f"avg_{col_name}"] = [None]
            continue
            
        logger.info(f"Loading historical data from {days} days ago: {past_file}")
        try:
            df_past = pd.read_csv(past_file)
            df_past['Price_Num'] = df_past['Price'].apply(parse_price)
            df_past_grouped = df_past.groupby(['District', 'Rooms'])['Price_Num'].median().reset_index()
            df_past_grouped.rename(columns={'Price_Num': f'past_price_{days}d'}, inplace=True)
            
            # Merge on segment criteria
            df_today_grouped = df_today_grouped.merge(df_past_grouped, on=['District', 'Rooms'], how='left')
            
            # Calculate percentage change
            current_median = df_today_grouped['Median_Price_Today']
            past_median = df_today_grouped[f'past_price_{days}d']
            
            df_today_grouped[col_name] = ((current_median - past_median) / past_median) * 100
            
            # Calculate average inflation for the day across all groups
            avg_inflation = df_today_grouped[col_name].replace([float('inf'), float('-inf')], pd.NA).mean()
            summary_data[f"avg_{col_name}"] = [avg_inflation]
            
            # Drop the intermediate historical price column (optional, but requested for cleanliness)
            df_today_grouped = df_today_grouped.drop(columns=[f'past_price_{days}d'])
            
        except Exception as e:
            logger.error(f"Error processing historical data {past_file}: {e}")
            df_today_grouped[col_name] = None
            summary_data[f"avg_{col_name}"] = [None]

    inflation_dir = Path(config.INFLATION_DIR)
    inflation_dir.mkdir(parents=True, exist_ok=True)

    # Save detailed data (it's essentially a grouped summary since listings don't have unique IDs)
    output_inflation_file = inflation_dir / f"{folder_name}_inflation_{today_str}.csv"
    df_today_grouped.to_csv(output_inflation_file, index=False, encoding='utf-8')
    logger.info(f"Saved grouped inflation data to: {output_inflation_file}")
    
    # Save/Append summary data
    summary_file = inflation_dir / "inflation_summary.csv"
    df_summary = pd.DataFrame(summary_data)
    
    header = not summary_file.exists()
    try:
        df_summary.to_csv(summary_file, mode='a', index=False, header=header, encoding='utf-8')
        logger.info(f"Appended daily inflation summary to: {summary_file}")
    except Exception as e:
        logger.error(f"Failed to write summary file: {e}")

if __name__ == "__main__":
    # Configure basic logging for standalone execution
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    calculate_inflation()
