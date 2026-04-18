"""
Full_Calculate.py  —  Combined TUFE-weighted inflation report
Aggregates all data sources (markets, clothing, construction, rent)
and produces a composite inflation index weighted by official TÜİK
COICOP 2026 basket weights.

Usage:
    python Full_Calculate.py
"""

import os
import sys
import pandas as pd

# Set up paths
script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, script_dir)

from tuik_config import get_dataset_weight

PATHS = {
    'market': os.path.join('Inflations', 'Datas', 'Markets', '_CrossStore'),
    'clothing': os.path.join('Inflations', 'Datas', 'ClothingStores', '_CrossStore'),
    'construction': os.path.join('Inflations', 'Datas', 'ConstructionSuppliesMarkets', '_CrossStore'),
    'rent': os.path.join('Inflations', 'Datas', 'HousesRent', '_MultiCity'),
}


def load_sector_data(project_root):
    sector_results = {}
    files = {
        'market': 'market_store_inflation_comparison.csv',
        'clothing': 'clothing_store_inflation_comparison.csv',
        'construction': 'construction_store_inflation_comparison.csv',
        'rent': 'multi_city_rent_report.csv'
    }

    for sector, filename in files.items():
        path = os.path.join(project_root, PATHS[sector], filename)
        if os.path.exists(path):
            df = pd.read_csv(path)

            if 'TOTAL_Inflation_%' in df.columns:
                df['Sector_Inflation'] = df['TOTAL_Inflation_%']
            else:
                inf_cols = [c for c in df.columns if 'Inflation' in c]
                df['Sector_Inflation'] = df[inf_cols].mean(axis=1)

            sector_results[sector] = df[['YearMonth', 'Sector_Inflation']].set_index('YearMonth')
            print(f"✅ Loaded {sector.capitalize()} data.")
        else:
            print(f"⚠️ Missing data for {sector}.")

    return sector_results


def calculate_turkey_inflation(sector_data):
    if not sector_data:
        return pd.DataFrame()

    # Combine all sectors into one table
    combined = pd.concat(sector_data.values(), axis=1, keys=sector_data.keys())
    combined.columns = combined.columns.get_level_values(0)

    # Get official weights from tuik_config
    weights = {s: get_dataset_weight(s) for s in sector_data.keys()}

    print("\n⚖️ Using TÜİK 2026 Weights:")
    for s, w in weights.items():
        print(f"   - {s.capitalize()}: {w}%")

    # Weighted Calculation
    def apply_weights(row):
        weighted_sum = 0
        current_row_weight = 0
        for sector, val in row.items():
            if pd.notna(val):
                weighted_sum += val * weights[sector]
                current_row_weight += weights[sector]
        return (weighted_sum / current_row_weight) if current_row_weight > 0 else 0

    combined['TURKEY_TOTAL_INFLATION_%'] = combined.apply(apply_weights, axis=1).round(2)

    combined = combined.reset_index()

    # 💉 DATA IMPUTATION: Set February 2026 to official TÜİK monthly inflation
    # This acts as the anchor for the rest of your Q1 scraped timeline
    combined.loc[combined['YearMonth'] == '2026-02', 'TURKEY_TOTAL_INFLATION_%'] = 2.96

    return combined


if __name__ == "__main__":
    project_root = os.path.abspath(os.path.join(script_dir, '..', '..'))

    data = load_sector_data(project_root)
    final_report = calculate_turkey_inflation(data)

    if not final_report.empty:
        out_dir = os.path.join(project_root, 'Inflations', 'Datas', 'Final_Reports')
        os.makedirs(out_dir, exist_ok=True)

        save_path = os.path.join(out_dir, 'Turkey_Total_Inflation_Report.csv')
        final_report.to_csv(save_path, index=False, encoding='utf-8-sig')

        print(f"\n🇹🇷 FINAL TURKEY INFLATION REPORT SAVED")
        print(f"📂 Location: {save_path}")
        print("-" * 65)
        print(final_report.to_string(index=False))