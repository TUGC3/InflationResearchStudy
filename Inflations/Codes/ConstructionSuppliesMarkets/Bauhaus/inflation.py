"""
inflation.py — Bauhaus Daily Inflation Calculator

Computes three inflation metrics for Bauhaus products:
  1. Basic Inflation   – basket-level price index change (%) calculated as sum of current prices vs sum of past prices
  2. Average Inflation – arithmetic mean of all per-product percentage price changes
  3. TUIK Weighted Avg – weighted average using TUIK 2026 CPI basket weights,
                         with weights normalised to the product categories present

Features:
- Calculates inflation for 1d, 7d, 15d, 30d intervals
- Supports comparison between any two arbitrary dates
- Maps 12 Bauhaus categories to 2 TUIK groups (05, 07)
- Outputs detailed per-product data and store-level summaries
- Handles missing historical data gracefully

Bauhaus TUIK mapping:
  - All categories except Tüm Oto Ürünleri → 05 (Mobilya, ev aletleri ve ev bakım hizmetleri)
  - Tüm Oto Ürünleri → 07 (Ulaştırma)

Output Files:
- bauhaus_inflation_YYYY-MM-DD.csv – Detailed per-product data with basic_inflation columns
- inflation_summary.csv – Store-level summary with avg_inflation and tuik_weighted columns

Usage:
    python inflation.py                    # Uses today's date
    python inflation.py --date 2026-03-20  # Specific target date
    python inflation.py --date 2026-03-20 --compare 2026-03-10  # Arbitrary comparison
"""

import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

# ── Path setup ────────────────────────────────────────────────────────────────
_THIS_DIR = Path(__file__).resolve().parent
_CODES_DIR = _THIS_DIR.parent.parent               # .../Inflations/Codes
_PROJECT_ROOT = _CODES_DIR.parent.parent            # .../InflationResearchStudy

sys.path.insert(0, str(_THIS_DIR))
from tuik_config import bauhaus_category_to_tuik, normalised_weights, TUIK_WEIGHTS

# Scraper config for data paths
# Note: Bauhaus uses config.OUTPUT_DIR while other calculators use config.BASE_OUTPUT_DIR
try:
    _scraper_dir = _PROJECT_ROOT / "InflationItems" / "Codes" / "ConstructionSuppliesMarkets" / "Bauhaus" / "scripts"
    sys.path.insert(0, str(_scraper_dir))
    import config
    DATA_DIR = Path(config.OUTPUT_DIR)
except Exception:
    # Fallback to default path if config import fails
    DATA_DIR = _PROJECT_ROOT / "InflationItems" / "Datas" / "ConstructionSuppliesMarkets" / "Bauhaus"

logger = logging.getLogger(__name__)

# ── Output directory ──────────────────────────────────────────────────────────
INFLATION_OUT_DIR = _CODES_DIR.parent / "Datas" / "ConstructionSuppliesMarkets" / "Bauhaus"


def _load_csv(date_str):
    """Load a Bauhaus daily CSV by date string, return DataFrame or None."""
    fpath = DATA_DIR / f"bauhaus_{date_str}.csv"
    if not fpath.exists():
        logger.info(f"Data file not found: {fpath}")
        return None
    try:
        df = pd.read_csv(fpath)
        df['shown_price'] = pd.to_numeric(df['shown_price'], errors='coerce')
        return df
    except Exception as e:
        logger.error(f"Failed to read {fpath}: {e}")
        return None


def _compute_metrics(df_current, df_past):
    """Compute the three inflation metrics between two DataFrames.

    Returns
    -------
    df_detail : DataFrame  – per-product rows with basic_inflation and tuik_category
    basic_inflation_index : float – basket-level price index change (%)
    avg_inflation         : float – arithmetic mean of per-product inflation rates
    tuik_weighted         : float – TUIK-weighted average inflation
    """
    df_current = df_current.copy()
    df_current['tuik_category'] = df_current['category'].apply(bauhaus_category_to_tuik)

    past_subset = df_past[['id', 'shown_price']].rename(columns={'shown_price': 'past_price'})
    merged = df_current.merge(past_subset, on='id', how='left')

    # 1) Basic inflation per product
    merged['basic_inflation'] = ((merged['shown_price'] - merged['past_price']) / merged['past_price']) * 100
    merged['basic_inflation'] = merged['basic_inflation'].replace([float('inf'), float('-inf')], pd.NA)

    # 2) Average inflation
    avg_inflation = merged['basic_inflation'].mean()

    # 3) Basic inflation at basket level
    valid = merged.dropna(subset=['shown_price', 'past_price'])
    sum_current = valid['shown_price'].sum()
    sum_past = valid['past_price'].sum()
    basic_inflation_index = ((sum_current - sum_past) / sum_past) * 100 if sum_past else None

    # 4) TUIK weighted average
    cat_avg = merged.groupby('tuik_category')['basic_inflation'].mean()
    present_codes = list(cat_avg.dropna().index)
    norm_w = normalised_weights(present_codes)
    tuik_weighted = sum(cat_avg[c] * norm_w[c] / 100.0 for c in norm_w if c in cat_avg.index and pd.notna(cat_avg[c]))

    merged = merged.drop(columns=['past_price'], errors='ignore')
    return merged, basic_inflation_index, avg_inflation, tuik_weighted


def calculate_inflation(target_date=None, compare_date=None):
    """Calculate inflation metrics for Bauhaus.

    Parameters
    ----------
    target_date  : str (YYYY-MM-DD) – the "current" date.  Defaults to today.
    compare_date : str (YYYY-MM-DD) – if given, compute metrics only between
                   *compare_date* (past) and *target_date* (current).
                   If omitted, compute for the four standard intervals
                   (1d, 7d, 15d, 30d back from target_date).

    Returns
    -------
    None
        Results are saved to CSV files in the inflation output directory.

    Notes
    -----
    - Uses Bauhaus product IDs ('id') for matching across dates
    - Price column: 'shown_price' (displayed price after discounts)
    - Category column: 'category' (mapped to TUIK groups via tuik_config.py)
    - Missing historical data results in NaN values for affected intervals

    Examples
    --------
    >>> # Calculate today's inflation with standard intervals
    >>> calculate_inflation()

    >>> # Calculate inflation for a specific date
    >>> calculate_inflation('2026-03-20')

    >>> # Compare two arbitrary dates
    >>> calculate_inflation('2026-03-20', '2026-03-10')
    """
    if target_date:
        base_date = datetime.strptime(target_date, "%Y-%m-%d")
    else:
        base_date = datetime.today()
    today_str = base_date.strftime("%Y-%m-%d")

    df_today = _load_csv(today_str)
    if df_today is None:
        logger.warning(f"Cannot calculate inflation – no data for {today_str}.")
        return

    INFLATION_OUT_DIR.mkdir(parents=True, exist_ok=True)

    # ── Determine intervals ──────────────────────────────────────────────────
    if compare_date:
        intervals = {compare_date: compare_date}
    else:
        intervals = {}
        for days in [1, 7, 15, 30]:
            past_str = (base_date - timedelta(days=days)).strftime("%Y-%m-%d")
            intervals[f"{days}d"] = past_str

    # ── Per-interval computation ─────────────────────────────────────────────
    summary_row = {'date': today_str}
    detail_base = df_today.copy()
    detail_base['tuik_category'] = detail_base['category'].apply(bauhaus_category_to_tuik)

    for label, past_str in intervals.items():
        df_past = _load_csv(past_str)

        if df_past is None:
            logger.info(f"Skipping interval {label} – no data for {past_str}.")
            detail_base[f'basic_inflation_{label}'] = None
            summary_row[f'avg_inflation_{label}'] = None
            summary_row[f'tuik_weighted_{label}'] = None
            continue

        merged, basic_idx, avg_inf, tuik_w = _compute_metrics(df_today, df_past)

        detail_base = detail_base.merge(
            merged[['id', 'basic_inflation']].rename(columns={'basic_inflation': f'basic_inflation_{label}'}),
            on='id', how='left'
        )

        summary_row[f'avg_inflation_{label}'] = avg_inf
        summary_row[f'tuik_weighted_{label}'] = tuik_w

    # ── Save detailed data ───────────────────────────────────────────────────
    detail_file = INFLATION_OUT_DIR / f"bauhaus_inflation_{today_str}.csv"
    detail_base.to_csv(detail_file, index=False, encoding='utf-8')
    logger.info(f"Saved detailed inflation data to: {detail_file}")

    # ── Save / update summary ────────────────────────────────────────────────
    summary_file = INFLATION_OUT_DIR / "inflation_summary.csv"
    df_summary = pd.DataFrame([summary_row])

    try:
        if summary_file.exists():
            df_existing = pd.read_csv(summary_file)
            df_existing = df_existing[df_existing['date'] != today_str]
            df_final = pd.concat([df_existing, df_summary], ignore_index=True)
            df_final.to_csv(summary_file, index=False, encoding='utf-8')
            logger.info(f"Updated inflation summary in: {summary_file}")
        else:
            df_summary.to_csv(summary_file, index=False, encoding='utf-8')
            logger.info(f"Created inflation summary in: {summary_file}")
    except Exception as e:
        logger.error(f"Failed to write summary file: {e}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Bauhaus inflation calculator")
    parser.add_argument("--date", help="Target (current) date in YYYY-MM-DD format", default=None)
    parser.add_argument("--compare", help="Comparison (past) date in YYYY-MM-DD format", default=None)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    calculate_inflation(args.date, args.compare)
