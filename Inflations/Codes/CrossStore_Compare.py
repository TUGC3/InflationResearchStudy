"""
CrossStore_Compare.py
Compares multiple stores of the SAME type side-by-side.
Works for: markets vs markets, clothing vs clothing, construction vs construction.

For each store it computes monthly inflation, then ranks stores by:
  - Cheapest overall average price
  - Lowest inflation rate
  - Best/worst price per category
"""

import os
import sys
import argparse
import pandas as pd
import re

# Ensure the script can find inflation_engine in the same folder
script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, script_dir)

from inflation_engine import (
    load_market_data,
    load_clothing_data,
    load_construction_data,
)

LOADERS = {
    'market': load_market_data,
    'clothing': load_clothing_data,
    'construction': load_construction_data,
}

TYPE_BASE_DIRS = {
    'market': os.path.join('InflationItems', 'Datas', 'Markets'),
    'clothing': os.path.join('InflationItems', 'Datas', 'ClothingStores'),
    'construction': os.path.join('InflationItems', 'Datas', 'ConstructionSuppliesMarkets'),
}

TYPE_OUT_DIRS = {
    'market': os.path.join('Inflations', 'Datas', 'Markets', '_CrossStore'),
    'clothing': os.path.join('Inflations', 'Datas', 'ClothingStores', '_CrossStore'),
    'construction': os.path.join('Inflations', 'Datas', 'ConstructionSuppliesMarkets', '_CrossStore'),
}


def normalize_product_names(df):
    """Cleans, standardizes, and groups similar product names together."""
    print("🧹 Normalizing and merging similar products...")

    def clean_text(text):
        if pd.isna(text): return "UNKNOWN"

        # 1. Uppercase everything
        t = str(text).upper()

        # 2. Remove useless store tags
        t = re.sub(r'\s*1\s*ADET\b', '', t)
        t = re.sub(r'\bADET\b', '', t)

        # 3. Standardize weights and volumes
        t = re.sub(r'\s+GR\b', 'G', t)
        t = re.sub(r'\s+G\b', 'G', t)
        t = re.sub(r'\s+ML\b', 'ML', t)
        t = re.sub(r'\s+KG\b', 'KG', t)
        t = re.sub(r'\s+LT\b', 'L', t)

        # 4. Remove punctuation
        t = re.sub(r'[,\-]', ' ', t)

        # 5. Remove extra whitespace
        t = re.sub(r'\s+', ' ', t).strip()

        # 6. Alphabetical Sorting (Matches "Arko Cool 90G" with "Arko 90G Cool")
        words = t.split()
        words.sort()
        return ' '.join(words)

    df['ProductName'] = df['ProductName'].apply(clean_text)
    return df


def load_all_stores(dataset_type, base_dir, store_filter=None):
    loader = LOADERS[dataset_type]
    if not os.path.exists(base_dir):
        print(f"❌ Error: Base directory not found: {base_dir}")
        return pd.DataFrame()

    store_folders = [d for d in os.listdir(base_dir) if os.path.isdir(os.path.join(base_dir, d))]
    frames = []

    for store in store_folders:
        if store_filter and store not in store_filter:
            continue

        path = os.path.join(base_dir, store)
        df = loader(path)

        if df is not None and not df.empty:
            # Drop duplicate columns to prevent InvalidIndexError during concat
            df = df.loc[:, ~df.columns.duplicated()].copy()
            df['Store'] = store
            frames.append(df)
            print(f"   ✅ {store}: {len(df):,} records")

    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def inflation_comparison(df):
    """Generates matched-product monthly inflation (Apples-to-Apples)."""
    df = df.copy()
    df['YearMonth'] = df['Date'].dt.strftime('%Y-%m')

    if 'ProductName' not in df.columns:
        df['ProductName'] = 'UNKNOWN'

    # --- TOTAL (Global) Calculations ---
    product_monthly = df.groupby(['YearMonth', 'ProductName'])['Active_Price'].mean().unstack('ProductName')

    total_monthly = pd.DataFrame({
        'TOTAL_AvgPrice': product_monthly.mean(axis=1).round(2),
        'TOTAL_Inflation_%': (product_monthly.pct_change() * 100).mean(axis=1).round(2)
    }).reset_index()

    # --- Per Store Calculations ---
    store_mom = {}
    store_price = {}
    for store in df['Store'].unique():
        sdf = df[df['Store'] == store]
        sprod = sdf.groupby(['YearMonth', 'ProductName'])['Active_Price'].mean().unstack('ProductName')

        store_mom[f'{store}_MoM_%'] = (sprod.pct_change() * 100).mean(axis=1)
        store_price[f'{store}_AvgPrice'] = sprod.mean(axis=1)

    pivot_mom = pd.DataFrame(store_mom).round(2)
    pivot_price = pd.DataFrame(store_price).round(2)

    combined = pd.concat([total_monthly.set_index('YearMonth'), pivot_price, pivot_mom], axis=1)

    # 🧹 Drop the first month where inflation is NaN
    combined = combined.dropna(subset=['TOTAL_Inflation_%'])

    return combined.reset_index()


def product_monthly_tracker(df):
    """Creates a matrix of Products (rows) by Monthly Inflation % (columns)."""
    df = df.copy()

    if 'ProductName' not in df.columns:
        df['ProductName'] = 'UNKNOWN'

    df['YearMonth'] = df['Date'].dt.strftime('%Y-%m')

    # 1. Pivot: Products as rows, Months as columns, Average Prices as values
    monthly_price = df.groupby(['ProductName', 'YearMonth'])['Active_Price'].mean().unstack('YearMonth')
    monthly_price = monthly_price.sort_index(axis=1)

    # 2. Forward-fill missing months
    monthly_price_filled = monthly_price.ffill(axis=1)

    # 3. Calculate month-over-month percentage change and force rounding
    monthly_inflation = (monthly_price_filled.pct_change(axis=1) * 100).round(2)

    # 4. Drop the very first month
    if len(monthly_inflation.columns) > 0:
        first_col = monthly_inflation.columns[0]
        monthly_inflation = monthly_inflation.drop(columns=[first_col])

    monthly_inflation.columns = [f"{c}_Change_%" for c in monthly_inflation.columns]

    # 5. Add an overall period change column for easy sorting, force rounding
    first_valid = monthly_price.bfill(axis=1).iloc[:, 0]
    last_valid = monthly_price.ffill(axis=1).iloc[:, -1]
    total_change = ((last_valid - first_valid) / first_valid * 100).round(2)

    monthly_inflation.insert(0, 'Total_Period_Change_%', total_change)

    # 6. Fill remaining NaNs with 0.0 to prevent artifacting
    monthly_inflation = monthly_inflation.fillna(0.0)

    return monthly_inflation.reset_index()


def run_cross_store(dataset_type, project_root, store_filter=None):
    base_path = os.path.join(project_root, TYPE_BASE_DIRS[dataset_type])
    output_dir = os.path.join(project_root, TYPE_OUT_DIRS[dataset_type])

    print(f"\n🚀 PROCESSING: {dataset_type.upper()}")
    print(f"📂 Scanning: {base_path}")

    full_df = load_all_stores(dataset_type, base_path, store_filter)

    if full_df.empty:
        print(f"⚠️ No data found for {dataset_type}. Skipping...")
        return

    # 🧹 NEW: Apply the NLP Product Merger before doing any math!
    full_df = normalize_product_names(full_df)

    # 1. Generate standard store comparison
    print("📊 Calculating matched-basket inflation...")
    inf_table = inflation_comparison(full_df)

    # 2. Generate new Product Monthly Tracker
    print("🔍 Generating product-level monthly changes...")
    prod_tracker = product_monthly_tracker(full_df)

    os.makedirs(output_dir, exist_ok=True)

    # Save standard report
    save_path = os.path.join(output_dir, f'{dataset_type}_store_inflation_comparison.csv')
    inf_table.to_csv(save_path, index=False, encoding='utf-8-sig')

    # Save product tracker
    prod_path = os.path.join(output_dir, f'{dataset_type}_product_monthly_changes.csv')
    prod_tracker.to_csv(prod_path, index=False, encoding='utf-8-sig')

    print(f"💾 Reports saved to: {output_dir}")
    if not inf_table.empty:
        print(
            f"📈 Overall {dataset_type.capitalize()} Inflation (Latest MoM): {inf_table['TOTAL_Inflation_%'].iloc[-1]}%")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Cross-store inflation comparison")
    parser.add_argument('--type', default='all', choices=['all', 'market', 'clothing', 'construction'])
    parser.add_argument('--stores', nargs='+', default=None)

    args = parser.parse_args()
    _project_root = os.path.abspath(os.path.join(script_dir, '..', '..'))

    if args.type == 'all':
        for t in LOADERS.keys():
            run_cross_store(t, _project_root, args.stores)
    else:
        run_cross_store(args.type, _project_root, args.stores)

    print("\n✅ All requested processing complete.")