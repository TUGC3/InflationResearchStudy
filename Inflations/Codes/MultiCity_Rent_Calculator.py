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
    Loads rent CSVs safely by strictly taking the first 3 columns.
    Col 0: District, Col 1: Rooms (3+1), Col 2: Price
    """
    files = glob.glob(os.path.join(input_dir, "*.csv"))
    df_list = []
    for file in files:
        date_match = re.search(r"(\d{4}-\d{2}-\d{2})", os.path.basename(file))
        if not date_match:
            continue

        try:
            # on_bad_lines='skip' ignores corrupted rows instead of crashing
            df = pd.read_csv(file, on_bad_lines='skip')

            if df.shape[1] < 3:
                continue

            df = df.iloc[:, 0:3].copy()
            df.columns = ['District', 'Category', 'Price']

            # Clean price
            df['Active_Price'] = _clean_price(df['Price'])

            # 🧹 DATA HYGIENE FIX: Ignore "Daily Rents" (<3000) and Luxury/Sales (>300000)
            df = df[(df['Active_Price'] >= 3000) & (df['Active_Price'] <= 300000)]

            df['Date'] = pd.to_datetime(date_match.group(1))
            df['Store'] = os.path.basename(input_dir)

            df_list.append(df[['Date', 'Store', 'District', 'Category', 'Active_Price']])
        except Exception as e:
            pass  # Silently skip completely broken files

    return pd.concat(df_list, ignore_index=True) if df_list else pd.DataFrame()


def run_multi_city(base_dir, output_dir):
    print("\n" + "=" * 60)
    print("🏠  MULTI-CITY RENT INFLATION CALCULATOR")
    print(f"📂 Searching in: {base_dir}")
    print("=" * 60)

    if not os.path.exists(base_dir):
        print(f"❌ Error: Directory does not exist at {base_dir}")
        return

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
        print("❌ No valid CSV data found.")
        return

    full_df = pd.concat(all_data, ignore_index=True)

    # --- Monthly Calculation (Weighted by Market Size) ---
    full_df['YearMonth'] = full_df['Date'].dt.strftime('%Y-%m')

    # 1. Calculate the mean price AND the number of listings (count) inside EACH city
    city_stats = full_df.groupby(['YearMonth', 'Store'])['Active_Price'].agg(['mean', 'count'])

    report_mean = city_stats['mean'].unstack().round(0)
    report_count = city_stats['count'].unstack()

    # 2. Calculate the inflation percentage inside EACH city
    inflation = (report_mean.pct_change() * 100).round(2)

    # 3. Calculate Simple Average Inflation (Unweighted)
    simple_inflation = inflation.mean(axis=1).round(2)

    # 4. Calculate Weighted Average Inflation
    valid_inflation_mask = inflation.notna()
    weighted_sum = (inflation * report_count).sum(axis=1)
    valid_counts = report_count[valid_inflation_mask].sum(axis=1)

    # Safely handle the zero division error for the first empty month
    weighted_inflation = (weighted_sum / valid_counts.replace(0, float('nan'))).round(2)

    # Rename columns for the final report
    inflation.columns = [f"{c}_Inflation_%" for c in inflation.columns]

    # Combine it all together
    final_report = pd.concat([report_mean, inflation], axis=1)
    final_report['Simple_Average_Inflation_%'] = simple_inflation
    final_report['Weighted_Average_Inflation_%'] = weighted_inflation
    final_report['TOTAL_Inflation_%'] = weighted_inflation

    final_report = final_report.reset_index()

    # 🧹 Drop the first month where inflation is NaN
    final_report = final_report.dropna(subset=['TOTAL_Inflation_%'])

    # Save
    os.makedirs(output_dir, exist_ok=True)
    save_path = os.path.join(output_dir, 'multi_city_rent_report.csv')
    final_report.to_csv(save_path, index=False, encoding='utf-8-sig')

    print(f"\n💾 Report saved to: {save_path}")
    cols_to_show = ['YearMonth', 'Simple_Average_Inflation_%', 'Weighted_Average_Inflation_%', 'TOTAL_Inflation_%']
    print("\n📊 Simple vs. Weighted National Rent Inflation:")
    print(final_report[cols_to_show].tail())


if __name__ == "__main__":
    project_root = os.path.abspath(os.path.join(script_dir, '..', '..'))

    BASE_DIR = os.path.join(project_root, 'InflationItems', 'Datas', 'HousesRent')
    OUTPUT_DIR = os.path.join(project_root, 'Inflations', 'Datas', 'HousesRent', '_MultiCity')

    run_multi_city(BASE_DIR, OUTPUT_DIR)