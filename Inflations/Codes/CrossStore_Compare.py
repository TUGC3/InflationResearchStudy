"""
CrossStore_Compare.py
Compares multiple stores of the SAME type side-by-side.
Works for: markets vs markets, clothing vs clothing, construction vs construction.

For each store it computes monthly inflation, then ranks stores by:
  - Cheapest overall average price
  - Lowest inflation rate
  - Best/worst price per category

Usage:
    python CrossStore_Compare.py --type market
    python CrossStore_Compare.py --type clothing
    python CrossStore_Compare.py --type construction
    python CrossStore_Compare.py --type market --stores Baskent Migros CarsiMarket
"""

import os
import sys
import argparse
import pandas as pd

# Ensure the script can find inflation_engine and tuik_config in the same folder
script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, script_dir)

from inflation_engine import (
    load_market_data,
    load_clothing_data,
    load_construction_data,
)

# Configuration for loaders and paths
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
            # FIX: Remove duplicate columns that cause the InvalidIndexError
            df = df.loc[:, ~df.columns.duplicated()].copy()

            df['Store'] = store
            frames.append(df)
            print(f"   ✅ {store}: {len(df):,} records")

    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def inflation_comparison(df):
    """Generates monthly inflation pivot table + TOTAL inflation calculation."""
    df = df.copy()
    df['YearMonth'] = df['Date'].dt.strftime('%Y-%m')

    # Per Store Calculations
    monthly_avg = df.groupby(['YearMonth', 'Store'])['Active_Price'].mean().reset_index()
    monthly_avg = monthly_avg.sort_values(['Store', 'YearMonth'])
    monthly_avg['MoM_Inflation_%'] = (
            monthly_avg.groupby('Store')['Active_Price']
            .pct_change() * 100
    ).round(2)

    pivot_price = monthly_avg.pivot(index='YearMonth', columns='Store', values='Active_Price').round(2)
    pivot_mom = monthly_avg.pivot(index='YearMonth', columns='Store', values='MoM_Inflation_%')

    pivot_price.columns = [f'{c}_AvgPrice' for c in pivot_price.columns]
    pivot_mom.columns = [f'{c}_MoM_%' for c in pivot_mom.columns]

    # TOTAL (Global) Calculations for the category
    total_monthly = df.groupby('YearMonth')['Active_Price'].mean().reset_index()
    total_monthly = total_monthly.sort_values('YearMonth')
    total_monthly['TOTAL_AvgPrice'] = total_monthly['Active_Price'].round(2)
    total_monthly['TOTAL_Inflation_%'] = (total_monthly['Active_Price'].pct_change() * 100).round(2)

    total_cols = total_monthly[['YearMonth', 'TOTAL_AvgPrice', 'TOTAL_Inflation_%']].set_index('YearMonth')

    combined = pd.concat([total_cols, pivot_price, pivot_mom], axis=1)
    return combined.reset_index()


def run_cross_store(dataset_type, project_root, store_filter=None):
    base_path = os.path.join(project_root, TYPE_BASE_DIRS[dataset_type])
    output_dir = os.path.join(project_root, TYPE_OUT_DIRS[dataset_type])

    print(f"\n🚀 PROCESSING: {dataset_type.upper()}")
    print(f"📂 Scanning: {base_path}")

    full_df = load_all_stores(dataset_type, base_path, store_filter)

    if full_df.empty:
        print(f"⚠️ No data found for {dataset_type}. Skipping...")
        return

    inf_table = inflation_comparison(full_df)

    os.makedirs(output_dir, exist_ok=True)
    save_path = os.path.join(output_dir, f'{dataset_type}_store_inflation_comparison.csv')
    inf_table.to_csv(save_path, index=False, encoding='utf-8-sig')

    print(f"💾 Report saved → {save_path}")
    print(f"📈 Overall {dataset_type.capitalize()} Inflation (Latest): {inf_table['TOTAL_Inflation_%'].iloc[-1]}%")


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