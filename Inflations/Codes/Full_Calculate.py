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

# The Output folders where your previous scripts saved data
PATHS = {
    'market': os.path.join('Inflations', 'Datas', 'Markets', '_CrossStore'),
    'clothing': os.path.join('Inflations', 'Datas', 'ClothingStores', '_CrossStore'),
    'construction': os.path.join('Inflations', 'Datas', 'ConstructionSuppliesMarkets', '_CrossStore'),
    'rent': os.path.join('Inflations', 'Datas', 'HousesRent', '_MultiCity'),
}


def load_sector_data(project_root):
    sector_results = {}

    # Mapping filenames to internal sector keys
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
            # We only need the Date and the TOTAL Inflation column we created
            col_name = 'TOTAL_Inflation_%' if sector != 'rent' else None

            # Rent uses a slightly different structure from the previous multi-city script
            if sector == 'rent':
                # Dynamically find the inflation column for Rent (e.g., Izmir_Inflation_%)
                inf_cols = [c for c in df.columns if 'Inflation' in c]
                df['Sector_Inflation'] = df[inf_cols].mean(axis=1)  # Average across cities
            else:
                df = df.rename(columns={col_name: 'Sector_Inflation'})

            sector_results[sector] = df[['YearMonth', 'Sector_Inflation']].set_index('YearMonth')
            print(f"✅ Loaded {sector.capitalize()} data.")
        else:
            print(f"⚠️ Missing data for {sector}. Run specific sector scripts first.")

    return sector_results


def calculate_turkey_inflation(sector_data):
    if not sector_data:
        return pd.DataFrame()

    # Combine all sectors into one table
    combined = pd.concat(sector_data.values(), axis=1, keys=sector_data.keys())
    combined.columns = combined.columns.get_level_values(0)

    # Get official weights from tuik_config
    weights = {s: get_dataset_weight(s) for s in sector_data.keys()}
    total_weight = sum(weights.values())

    print("\n⚖️ Using TÜİK 2026 Weights:")
    for s, w in weights.items():
        print(f"   - {s.capitalize()}: {w}%")

    # Weighted Calculation: (Inflation * Weight) / Total Tracked Weight
    def apply_weights(row):
        weighted_sum = 0
        current_row_weight = 0
        for sector, val in row.items():
            if pd.notna(val):
                weighted_sum += val * weights[sector]
                current_row_weight += weights[sector]
        return (weighted_sum / current_row_weight) if current_row_weight > 0 else 0

    combined['TURKEY_TOTAL_INFLATION_%'] = combined.apply(apply_weights, axis=1).round(2)

    return combined.reset_index()


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
        print("-" * 30)
        print(final_report.tail(5).to_string(index=False))