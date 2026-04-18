"""
inflation_engine.py
Core calculation engine for the Inflation Research Study project.
Supports: Markets, Clothing Stores, Construction Markets, House Rent
Uses TÜİK TUFE 2026 weights for official-style weighting.
"""

import os
import glob
import re
import warnings
import pandas as pd
from pathlib import Path

warnings.filterwarnings('ignore')

# ─────────────────────────────────────────────
# TÜİK TUFE weights — loaded from tuik_config
# ─────────────────────────────────────────────
try:
    from tuik_config import (
        MAIN_CATEGORIES,
        DATASET_COICOP_MAP,
        get_dataset_weight,
    )
    TUFE_WEIGHTS = {data['tr']: data['weight'] for data in MAIN_CATEGORIES.values()}
    DATASET_TUFE_MAP = {
        k: MAIN_CATEGORIES.get(v, {}).get('tr', k)
        for k, v in DATASET_COICOP_MAP.items()
    }
except ImportError:
    # Fallback if tuik_config not available
    TUFE_WEIGHTS = {
        "Gıda ve alkolsüz içecekler": 24.4444,
        "Giyim ve ayakkabı":           7.9038,
        "Konut, su, elektrik, gaz":   11.4020,
        "Mobilya ve ev ekipmanları":   7.9201,
    }
    DATASET_TUFE_MAP = {
        "market": "Gıda ve alkolsüz içecekler",
        "clothing": "Giyim ve ayakkabı",
        "construction": "Mobilya ve ev ekipmanları",
        "rent": "Konut, su, elektrik, gaz",
    }
    def get_dataset_weight(t): return TUFE_WEIGHTS.get(DATASET_TUFE_MAP.get(t, ''), 0.0)


def _extract_date(filename: str) -> str | None:
    """Extracts YYYY-MM-DD from a filename."""
    match = re.search(r"(\d{4}-\d{2}-\d{2})", filename)
    return match.group(1) if match else None


def _clean_price(series: pd.Series) -> pd.Series:
    """Cleans Turkish-formatted prices like '2.499,00 TL' → 2499.00"""
    return (
        series.astype(str)
        .str.replace(r'\s*TL\s*', '', regex=True)
        .str.replace('.', '', regex=False)
        .str.replace(',', '.', regex=False)
        .pipe(pd.to_numeric, errors='coerce')
    )


# ─────────────────────────────────────────────
# LOADERS — one per data source type
# ─────────────────────────────────────────────

def load_market_data(input_dir: str) -> pd.DataFrame:
    """
    Loads market/grocery store CSVs.
    Expected columns: ProductName (col 0), Price (col 1), [Category optional]
    Filename pattern: <storename>_YYYY-MM-DD.csv
    """
    files = glob.glob(os.path.join(input_dir, "*.csv"))
    df_list = []
    for file in files:
        date_str = _extract_date(os.path.basename(file))
        if not date_str:
            continue
        try:
            df = pd.read_csv(file, header=0)
            # Normalise columns: first col = ProductName, second col = Price
            df.columns = [c.strip() for c in df.columns]
            if df.shape[1] < 2:
                continue
            df = df.rename(columns={df.columns[0]: 'ProductName', df.columns[1]: 'Price'})
            df['Active_Price'] = _clean_price(df['Price'])
            if 'Category' not in df.columns:
                df['Category'] = 'General'
            df['Date'] = pd.to_datetime(date_str)
            df['Store'] = Path(file).stem.rsplit('_', 1)[0]
            df_list.append(df[['Date', 'Store', 'ProductName', 'Category', 'Active_Price']])
        except Exception as e:
            print(f"  ⚠ Skipping {os.path.basename(file)}: {e}")
    return pd.concat(df_list, ignore_index=True) if df_list else pd.DataFrame()


def load_clothing_data(input_dir: str) -> pd.DataFrame:
    """
    Loads clothing store CSVs.
    Expected columns: ProductName (col 0), Price (col 1), [Category optional]
    """
    return load_market_data(input_dir)   # Same structure


def load_construction_data(input_dir: str) -> pd.DataFrame:
    """
    Loads construction supply market CSVs.
    Expected columns: ProductName (col 0), Price (TL) or Price (col 1), [Category optional]
    """
    files = glob.glob(os.path.join(input_dir, "*.csv"))
    df_list = []
    for file in files:
        date_str = _extract_date(os.path.basename(file))
        if not date_str:
            continue
        try:
            df = pd.read_csv(file, header=0)
            df.columns = [c.strip() for c in df.columns]
            # Find price column (could be 'Price (TL)' or 'Price')
            price_col = next((c for c in df.columns if 'price' in c.lower()), None)
            name_col = df.columns[0]
            if not price_col:
                continue
            df = df.rename(columns={name_col: 'ProductName', price_col: 'Price'})
            df['Active_Price'] = pd.to_numeric(df['Price'], errors='coerce')
            if 'Category' not in df.columns:
                df['Category'] = 'Genel_Yapi'
            df['Date'] = pd.to_datetime(date_str)
            df['Store'] = Path(file).stem.rsplit('_', 1)[0]
            df_list.append(df[['Date', 'Store', 'ProductName', 'Category', 'Active_Price']])
        except Exception as e:
            print(f"  ⚠ Skipping {os.path.basename(file)}: {e}")
    return pd.concat(df_list, ignore_index=True) if df_list else pd.DataFrame()


def load_rent_data(input_dir: str) -> pd.DataFrame:
    """
    Loads house rent CSVs (city-level).
    Expected columns: PriceInt (numeric rent), Rooms
    Filename pattern: <City>_YYYY-MM-DD.csv
    """
    files = glob.glob(os.path.join(input_dir, "*.csv"))
    df_list = []
    for file in files:
        date_str = _extract_date(os.path.basename(file))
        if not date_str:
            continue
        try:
            df = pd.read_csv(file, header=0)
            df.columns = [c.strip() for c in df.columns]
            if 'PriceInt' not in df.columns:
                # Try first numeric column
                num_cols = df.select_dtypes(include='number').columns
                if len(num_cols) == 0:
                    continue
                df = df.rename(columns={num_cols[0]: 'PriceInt'})
            if 'Rooms' not in df.columns:
                df['Rooms'] = 'Unknown'
            df['Active_Price'] = pd.to_numeric(df['PriceInt'], errors='coerce')
            df['Date'] = pd.to_datetime(date_str)
            parts = Path(file).stem.rsplit('_', 1)
            df['Store'] = parts[0]   # City name
            df['Category'] = df['Rooms'].astype(str)
            df['ProductName'] = df['Rooms'].astype(str) + ' oda'
            df_list.append(df[['Date', 'Store', 'ProductName', 'Category', 'Active_Price']])
        except Exception as e:
            print(f"  ⚠ Skipping {os.path.basename(file)}: {e}")
    return pd.concat(df_list, ignore_index=True) if df_list else pd.DataFrame()


# ─────────────────────────────────────────────
# CORE CALCULATION
# ─────────────────────────────────────────────

def calculate_inflation(df: pd.DataFrame, group_col: str = 'Store') -> dict:
    """
    Calculates daily, weekly, and monthly inflation for each store/city,
    per category, and overall (simple + weighted).

    Returns a dict of DataFrames keyed by period.
    """
    if df.empty:
        return {}

    df = df.dropna(subset=['Active_Price', 'Date'])
    df['YearWeek'] = df['Date'].dt.strftime('%G-W%V')
    df['YearMonth'] = df['Date'].dt.strftime('%Y-%m')

    results = {}
    for period, time_col in [('daily', 'Date'), ('weekly', 'YearWeek'), ('monthly', 'YearMonth')]:
        rows = []
        for store, sdf in df.groupby(group_col):
            # --- Per category average price per period ---
            cat_prices = sdf.groupby([time_col, 'Category'])['Active_Price'].mean().unstack()
            cat_counts = sdf.groupby([time_col, 'Category'])['Active_Price'].count().unstack()

            if cat_prices.empty:
                continue

            cat_prices = cat_prices.sort_index()
            cat_counts = cat_counts.sort_index()

            # Overall simple: mean of all prices
            overall_simple = sdf.groupby(time_col)['Active_Price'].mean()

            # Overall weighted: count-weighted across categories
            overall_weighted = (cat_prices * cat_counts).sum(axis=1) / cat_counts.sum(axis=1)

            for period_val in cat_prices.index:
                row = {
                    'Store': store,
                    time_col: period_val,
                    'Avg_Price': round(overall_simple.get(period_val, float('nan')), 2),
                    'Weighted_Avg_Price': round(overall_weighted.get(period_val, float('nan')), 2),
                }
                # Per-category averages
                for cat in cat_prices.columns:
                    val = cat_prices.loc[period_val, cat]
                    row[f'Cat_{cat}_AvgPrice'] = round(val, 2) if pd.notna(val) else None
                rows.append(row)

        if not rows:
            continue

        out = pd.DataFrame(rows)

        # Sort and compute inflation rates per store
        out = out.sort_values(['Store', time_col])

        out['Normal_Inflation_%'] = out.groupby('Store')['Avg_Price'].pct_change() * 100
        out['Weighted_Inflation_%'] = out.groupby('Store')['Weighted_Avg_Price'].pct_change() * 100

        # Category inflations
        for col in [c for c in out.columns if c.startswith('Cat_') and c.endswith('_AvgPrice')]:
            inf_col = col.replace('_AvgPrice', '_Inflation_%')
            out[inf_col] = out.groupby('Store')[col].pct_change() * 100

        out = out.round(2)
        results[period] = out

    return results


def calculate_cross_store_inflation(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compares the same product across different stores on the same date.
    Groups by ProductName + Date to find price spread.
    """
    if df.empty:
        return pd.DataFrame()

    pivot = df.groupby(['Date', 'Store', 'ProductName'])['Active_Price'].mean().reset_index()
    spread = pivot.groupby(['Date', 'ProductName']).agg(
        Min_Price=('Active_Price', 'min'),
        Max_Price=('Active_Price', 'max'),
        Mean_Price=('Active_Price', 'mean'),
        Std_Price=('Active_Price', 'std'),
        Store_Count=('Store', 'nunique'),
    ).reset_index()
    spread['Price_Spread_%'] = ((spread['Max_Price'] - spread['Min_Price']) / spread['Min_Price'] * 100).round(2)
    return spread.sort_values(['Date', 'ProductName'])


def calculate_tufe_weighted_summary(
    market_df: pd.DataFrame = None,
    clothing_df: pd.DataFrame = None,
    construction_df: pd.DataFrame = None,
    rent_df: pd.DataFrame = None,
) -> pd.DataFrame:
    """
    Produces a TÜİK-style weighted composite inflation index
    by combining datasets with their official TUFE category weights.
    """
    datasets = {
        'market':       (market_df,       get_dataset_weight('market')),
        'clothing':     (clothing_df,     get_dataset_weight('clothing')),
        'construction': (construction_df, get_dataset_weight('construction')),
        'rent':         (rent_df,         get_dataset_weight('rent')),
    }

    monthly_inflations = {}
    for name, (df, weight) in datasets.items():
        if df is None or df.empty:
            continue
        df = df.copy()
        df['YearMonth'] = df['Date'].dt.strftime('%Y-%m')
        monthly_avg = df.groupby('YearMonth')['Active_Price'].mean()
        monthly_inf = monthly_avg.pct_change() * 100
        monthly_inflations[name] = {'inflation': monthly_inf, 'weight': weight}

    if not monthly_inflations:
        return pd.DataFrame()

    all_months = sorted(set(
        m for v in monthly_inflations.values() for m in v['inflation'].index
    ))

    rows = []
    total_weight = sum(v['weight'] for v in monthly_inflations.values())
    for month in all_months:
        row = {'YearMonth': month}
        composite = 0.0
        used_weight = 0.0
        for name, v in monthly_inflations.items():
            val = v['inflation'].get(month, float('nan'))
            row[f'{name}_Inflation_%'] = round(val, 2) if pd.notna(val) else None
            row[f'{name}_TUFE_Weight_%'] = v['weight']
            if pd.notna(val):
                composite += val * v['weight']
                used_weight += v['weight']
        row['Composite_TUFE_Weighted_Inflation_%'] = round(composite / used_weight, 2) if used_weight > 0 else None
        rows.append(row)

    return pd.DataFrame(rows)


# ─────────────────────────────────────────────
# RUNNER
# ─────────────────────────────────────────────

def run_pipeline(
    dataset_type: str,
    input_dirs: list[str],
    output_dir: str,
    store_label: str = None,
):
    """
    Main entry: loads data from one or more directories, computes inflation,
    and saves CSV reports to output_dir.

    dataset_type: 'market' | 'clothing' | 'construction' | 'rent'
    input_dirs:   list of paths to scan for dated CSVs
    output_dir:   where to write reports
    store_label:  optional label override for single-store runs
    """
    LOADERS = {
        'market':       load_market_data,
        'clothing':     load_clothing_data,
        'construction': load_construction_data,
        'rent':         load_rent_data,
    }

    loader = LOADERS.get(dataset_type)
    if not loader:
        raise ValueError(f"Unknown dataset_type '{dataset_type}'. Choose from: {list(LOADERS)}")

    print(f"\n{'='*55}")
    print(f"📊 INFLATION PIPELINE — {dataset_type.upper()}")
    print(f"{'='*55}")

    all_frames = []
    for d in input_dirs:
        print(f"  📂 Scanning: {os.path.abspath(d)}")
        df = loader(d)
        if not df.empty:
            all_frames.append(df)
            print(f"     ✅ {len(df):,} records loaded from {df['Store'].nunique()} source(s)")
        else:
            print(f"     ⚠  No valid data found.")

    if not all_frames:
        print("❌ No data to process.")
        return

    full_df = pd.concat(all_frames, ignore_index=True)
    if store_label:
        full_df['Store'] = store_label

    print(f"\n  Total records: {len(full_df):,}")
    print(f"  Date range: {full_df['Date'].min().date()} → {full_df['Date'].max().date()}")
    print(f"  Stores/Cities: {sorted(full_df['Store'].unique())}")
    print(f"  Categories: {sorted(full_df['Category'].unique())}\n")

    results = calculate_inflation(full_df)

    os.makedirs(output_dir, exist_ok=True)

    for period, df_out in results.items():
        path = os.path.join(output_dir, f"{dataset_type}_{period}_inflation.csv")
        df_out.to_csv(path, index=False, encoding='utf-8-sig')
        print(f"  💾 {period.capitalize()} report → {path}")

        # Print last 5 rows of overall columns
        show_cols = ['Store'] + [c for c in df_out.columns if 'Inflation' in c and 'Cat_' not in c]
        print(df_out[show_cols].dropna(subset=['Normal_Inflation_%']).tail(5).to_string(index=False))
        print()

    # Cross-store comparison (if multiple stores)
    if full_df['Store'].nunique() > 1:
        cross = calculate_cross_store_inflation(full_df)
        if not cross.empty:
            path = os.path.join(output_dir, f"{dataset_type}_cross_store_comparison.csv")
            cross.to_csv(path, index=False, encoding='utf-8-sig')
            print(f"  🔀 Cross-store comparison → {path}")

    print(f"\n✅ Pipeline complete.")
    return full_df
