"""
Merge daily CSVs and analyze price trends.

Usage:
    cd hapeloglu-price-tracker/
    python -m scripts.run_analysis
"""

import os
import sys
import glob

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import OUTPUT_DIR


RAW_DIR = OUTPUT_DIR
PROCESSED_DIR = "data/processed"


def load_all_days() -> pd.DataFrame:
    files = sorted(glob.glob(os.path.join(RAW_DIR, "hapeloglu_*.csv")))
    if not files:
        print(f"No CSVs found in {RAW_DIR}/")
        return pd.DataFrame()

    print(f"Found {len(files)} daily snapshot(s)")
    dfs = [pd.read_csv(f) for f in files]
    df = pd.concat(dfs, ignore_index=True)
    df["scrape_date"] = pd.to_datetime(df["scrape_date"])
    print(f"Combined: {len(df)} rows, {df['product_id'].nunique()} products, "
          f"{df['scrape_date'].nunique()} days\n")
    return df


def price_changes(df: pd.DataFrame) -> pd.DataFrame:
    if df["scrape_date"].nunique() < 2:
        print("Need 2+ days of data for price change detection.\n")
        return pd.DataFrame()

    df = df.sort_values(["product_id", "scrape_date"])
    df["prev_price"] = df.groupby("product_id")["current_price"].shift(1)
    df["price_change"] = df["current_price"] - df["prev_price"]
    df["price_change_pct"] = (df["price_change"] / df["prev_price"] * 100).round(2)

    changes = df[df["price_change"] != 0].dropna(subset=["price_change"])
    return changes[["product_id", "name", "category", "scrape_date",
                     "prev_price", "current_price", "price_change", "price_change_pct"]]


def category_summary(df: pd.DataFrame) -> pd.DataFrame:
    latest = df[df["scrape_date"] == df["scrape_date"].max()]
    return latest.groupby("category").agg(
        products=("product_id", "count"),
        avg_price=("current_price", "mean"),
        median_price=("current_price", "median"),
        min_price=("current_price", "min"),
        max_price=("current_price", "max"),
    ).round(2).sort_values("products", ascending=False)


def main():
    df = load_all_days()
    if df.empty:
        return

    print("=" * 60)
    print("CATEGORY SUMMARY")
    print("=" * 60)
    print(category_summary(df).to_string())

    changes = price_changes(df)
    if not changes.empty:
        print(f"\n{'=' * 60}")
        print(f"PRICE CHANGES ({len(changes)} detected)")
        print("=" * 60)
        print(changes.head(20).to_string(index=False))

    os.makedirs(PROCESSED_DIR, exist_ok=True)
    merged_path = os.path.join(PROCESSED_DIR, "all_days_merged.csv")
    df.to_csv(merged_path, index=False, encoding="utf-8-sig")
    print(f"\nMerged data -> {merged_path}")


if __name__ == "__main__":
    main()
