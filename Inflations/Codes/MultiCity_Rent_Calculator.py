"""
MultiCity_Rent_Calculator.py
Runs rent inflation for ALL cities found under HousesRent/
and produces a city-vs-city comparison report.

Filename pattern expected: <CityName>_YYYY-MM-DD.csv
Required columns: PriceInt (numeric), Rooms

Usage:
    python MultiCity_Rent_Calculator.py
    python MultiCity_Rent_Calculator.py --cities Izmir Istanbul Ankara
"""

import os
import sys
import argparse
import pandas as pd
import glob
import re

# Ensure the script can find neighbors
script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, script_dir)

from inflation_engine import _clean_price


def load_rent_data_custom(input_dir):
    """
    Loads rent CSVs where:
    Col 0: District, Col 1: Rooms (3+1), Col 2: Price
    """
    files = glob.glob(os.path.join(input_dir, "*.csv"))
    df_list = []
    for file in files:
        # Extract date from filename (YYYY-MM-DD)
        date_match = re.search(r"(\d{4}-\d{2}-\d{2})", os.path.basename(file))
        if not date_match:
            continue

        try:
            # Load without assuming headers first to handle raw scrapes
            df = pd.read_csv(file)
            if df.shape[1] < 3:
                continue

            # Map based on your requirements
            df = df.rename(columns={
                df.columns[0]: 'District',
                df.columns[1]: 'Category',  # Rooms like 3+1
                df.columns[2]: 'Price'
            })

            # Clean price (handles both int and strings like '25.000 TL')
            df['Active_Price'] = _clean_price(df['Price'])
            df['Date'] = pd.to_datetime(date_match.group(1))

            # Use folder name as City/Store
            df['Store'] = os.path.basename(input_dir)

            df_list.append(df[['Date', 'Store', 'District', 'Category', 'Active_Price']])
        except Exception as e:
            print(f"  ⚠️ Skipping {os.path.basename(file)}: {e}")

    return pd.concat(df_list, ignore_index=True) if df_list else pd.DataFrame()


def run_multi_city(base_dir, output_dir):
    print("\n" + "=" * 60)
    print("🏠  MULTI-CITY RENT INFLATION CALCULATOR")
    print(f"📂 Searching in: {base_dir}")
    print("=" * 60)

    if not os.path.exists(base_dir):
        print(f"❌ Error: Directory does not exist at {base_dir}")
        return

    # Find city folders (Izmir, Istanbul, etc.)
    cities = [d for d in os.listdir(base_dir) if os.path.isdir(os.path.join(base_dir, d))]

    if not cities:
        print("❌ No city subdirectories found.")
        return

    all_data = []
    for city in cities:
        city_path = os.path.join(base_dir, city)
        df = load_rent_data_custom(city_path)
        if not df.empty:
            all_data.append(df)
            print(f"✅ {city}: Loaded {len(df):,} listings")

    if not all_data:
        print("❌ No valid CSV data found in any city folder.")
        return

    full_df = pd.concat(all_data, ignore_index=True)

    # --- Monthly Calculation ---
    full_df['YearMonth'] = full_df['Date'].dt.strftime('%Y-%m')

    # Total average per city per month
    report = full_df.groupby(['YearMonth', 'Store'])['Active_Price'].mean().unstack().round(0)

    # Calculate Inflation %
    inflation = report.pct_change() * 100
    inflation.columns = [f"{c}_Inflation_%" for c in inflation.columns]

    final_report = pd.concat([report, inflation], axis=1).reset_index()

    # Save
    os.makedirs(output_dir, exist_ok=True)
    save_path = os.path.join(output_dir, 'multi_city_rent_report.csv')
    final_report.to_csv(save_path, index=False, encoding='utf-8-sig')

    print(f"\n💾 Report saved to: {save_path}")
    print(final_report.tail())


if __name__ == "__main__":
    # FIX: Correcting the project root path logic
    # This assumes the script is in InflationResearchStudy/Inflations/Codes/
    project_root = os.path.abspath(os.path.join(script_dir, '..', '..'))

    BASE_DIR = os.path.join(project_root, 'InflationItems', 'Datas', 'HousesRent')
    OUTPUT_DIR = os.path.join(project_root, 'Inflations', 'Datas', 'HousesRent', '_MultiCity')

    run_multi_city(BASE_DIR, OUTPUT_DIR)