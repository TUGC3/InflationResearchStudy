"""
inflation.py — Calculate inflation metrics for Bershka product prices.
=======================================================================

Compares today's scraped prices against historical data from 1, 7, 15,
and 30 days ago. Outputs per-product inflation CSV and a daily summary.

Identical logic to the Koton inflation module, adapted for Bershka
file naming and the ``product_id`` key (instead of Koton's ``pk``).
"""

import logging
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

import config

logger = logging.getLogger(__name__)


def calculate_inflation():
    """
    Calculate inflation for Bershka data based on 1, 7, 15, and 30-day intervals.

    Reads today's scraped CSV file, finds historical CSVs, calculates the
    percentage price change for each product by ``product_id``, and outputs:
      - A detailed per-product inflation CSV
      - A daily summary CSV with average inflation figures
    """
    output_dir = Path(config.OUTPUT_DIR)
    today_str = datetime.today().strftime("%Y-%m-%d")
    today_file = output_dir / f"bershka_{today_str}.csv"

    if not today_file.exists():
        logger.warning("Today's data file not found: %s. Cannot calculate inflation.", today_file)
        return

    logger.info("Loading today's CSV for inflation calculation: %s", today_file)

    try:
        df_today = pd.read_csv(today_file)
    except Exception as e:
        logger.error("Failed to read today's CSV: %s", e)
        return

    # Ensure 'sale_price' is numeric
    df_today["sale_price"] = pd.to_numeric(df_today["sale_price"], errors="coerce")

    intervals = [1, 7, 15, 30]
    summary_data = {"date": [today_str]}

    for days in intervals:
        past_date = (datetime.today() - timedelta(days=days)).strftime("%Y-%m-%d")
        past_file = output_dir / f"bershka_{past_date}.csv"

        col_name = f"inflation_{days}d_pct"

        if not past_file.exists():
            logger.info("No historical data for %d days ago (%s). Skipping.", days, past_file)
            df_today[col_name] = None
            summary_data[f"avg_{col_name}"] = [None]
            continue

        logger.info("Loading historical data from %d days ago: %s", days, past_file)
        try:
            df_past = pd.read_csv(past_file)
            df_past["sale_price"] = pd.to_numeric(df_past["sale_price"], errors="coerce")

            # Keep only product_id and sale_price for merging
            df_past_subset = df_past[["product_id", "sale_price"]].rename(
                columns={"sale_price": f"past_price_{days}d"}
            )

            # Merge on product_id
            df_today = df_today.merge(df_past_subset, on="product_id", how="left")

            # Calculate percentage change: ((current - past) / past) * 100
            df_today[col_name] = (
                (df_today["sale_price"] - df_today[f"past_price_{days}d"])
                / df_today[f"past_price_{days}d"]
            ) * 100

            # Average inflation (excluding NaN and infinities)
            avg_inflation = df_today[col_name].replace([float("inf"), float("-inf")], pd.NA).mean()
            summary_data[f"avg_{col_name}"] = [avg_inflation]

            # Drop intermediate column
            df_today = df_today.drop(columns=[f"past_price_{days}d"])

        except Exception as e:
            logger.error("Error processing historical data %s: %s", past_file, e)
            df_today[col_name] = None
            summary_data[f"avg_{col_name}"] = [None]

    inflation_dir = Path(config.INFLATION_DIR)
    inflation_dir.mkdir(parents=True, exist_ok=True)

    # Save detailed data
    output_inflation_file = inflation_dir / f"bershka_inflation_{today_str}.csv"
    df_today.to_csv(output_inflation_file, index=False, encoding="utf-8")
    logger.info("Saved detailed inflation data to: %s", output_inflation_file)

    # Save/Append summary data
    summary_file = inflation_dir / "inflation_summary.csv"
    df_summary = pd.DataFrame(summary_data)

    try:
        if summary_file.exists():
            df_existing = pd.read_csv(summary_file)
            # Remove any existing entry for today
            df_existing = df_existing[df_existing["date"] != today_str]
            df_final = pd.concat([df_existing, df_summary], ignore_index=True)
            df_final.to_csv(summary_file, index=False, encoding="utf-8")
            logger.info("Updated daily inflation summary in: %s", summary_file)
        else:
            df_summary.to_csv(summary_file, index=False, encoding="utf-8")
            logger.info("Created daily inflation summary in: %s", summary_file)
    except Exception as e:
        logger.error("Failed to write summary file: %s", e)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    calculate_inflation()
