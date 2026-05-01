"""
inflation.py — Samsung Daily Inflation Calculator
=================================================

Computes three inflation metrics for Samsung Türkiye SKUs:

  1. Basic Inflation   – basket-level price index change (%)
                         (sum of current prices vs sum of past prices)
  2. Average Inflation – arithmetic mean of all per-product percentage
                         price changes
  3. TUIK Weighted Avg – weighted average using TUIK 2026 CPI basket
                         weights, normalised to the product categories
                         present in the scraped catalogue

Features
--------
- Calculates inflation for 1d, 7d, 15d, 30d intervals
- Supports comparison between any two arbitrary dates
- Maps 20 Samsung top-level categories to 3 TUIK main groups (05, 08, 09)
- Outputs detailed per-product data and store-level summaries
- Handles missing historical data gracefully

Output Files
------------
- ``samsung_inflation_YYYY-MM-DD.csv`` – per-product detail file
- ``inflation_summary.csv``             – store-level summary, append-only

Both live in ``Inflations/Datas/TechnologicalProducts/Samsung/``.

Usage
-----
    python inflation.py                    # Uses today's date
    python inflation.py --date 2026-04-29  # Specific target date
    python inflation.py --date 2026-04-29 --compare 2026-04-22
"""

import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

# ── Path setup ────────────────────────────────────────────────────────────────
_THIS_DIR     = Path(__file__).resolve().parent
_CODES_DIR    = _THIS_DIR.parent.parent              # .../Inflations/Codes
_PROJECT_ROOT = _CODES_DIR.parent.parent             # .../InflationResearchStudy

sys.path.insert(0, str(_THIS_DIR))
from tuik_config import (  # noqa: E402  (intentional path-side-effect import)
    samsung_category_to_tuik,
    normalised_weights,
    TUIK_WEIGHTS,
)

# Scraper config for data paths (best-effort — fall back to the canonical
# layout if the import fails so the module is still useful standalone).
try:
    _scraper_dir = (
        _PROJECT_ROOT
        / "InflationItems" / "Codes" / "TechnologicalProducts"
        / "Samsung" / "scripts"
    )
    sys.path.insert(0, str(_scraper_dir))
    import config  # type: ignore  # noqa: E402
    DATA_DIR = Path(config.OUTPUT_DIR)
except Exception:
    DATA_DIR = (
        _PROJECT_ROOT
        / "InflationItems" / "Datas" / "TechnologicalProducts" / "Samsung"
    )

logger = logging.getLogger(__name__)

# ── Output directory ──────────────────────────────────────────────────────────
INFLATION_OUT_DIR = _CODES_DIR.parent / "Datas" / "TechnologicalProducts" / "Samsung"


def _load_csv(date_str: str):
    """Load a Samsung daily CSV by date string and return its DataFrame.

    Args
    ----
    date_str : str
        Date stamp in ``YYYY-MM-DD`` format used in the scraper's daily
        filename (e.g. ``"2026-04-29"`` → ``samsung_2026-04-29.csv``).

    Returns
    -------
    pandas.DataFrame or None
        The CSV loaded from :data:`DATA_DIR` with ``shown_price``
        coerced to numeric.  ``None`` when the file does not exist
        or cannot be parsed.
    """
    fpath = DATA_DIR / f"samsung_{date_str}.csv"
    if not fpath.exists():
        logger.info(f"Data file not found: {fpath}")
        return None
    try:
        # The scraper writes UTF-8-with-BOM to keep Excel happy.
        df = pd.read_csv(fpath, encoding="utf-8-sig")
        df["shown_price"] = pd.to_numeric(df["shown_price"], errors="coerce")
        return df
    except Exception as e:
        logger.error(f"Failed to read {fpath}: {e}")
        return None


def _compute_metrics(df_current: pd.DataFrame, df_past: pd.DataFrame):
    """Compute the three inflation metrics between two daily DataFrames.

    Returns
    -------
    df_detail : DataFrame
        Per-product rows with ``basic_inflation`` and ``tuik_category``.
    basic_inflation_index : float
        Basket-level price-index change (%).
    avg_inflation : float
        Arithmetic mean of per-product inflation rates (%).
    tuik_weighted : float
        TUIK-weighted average inflation (%).
    """
    df_current = df_current.copy()
    df_current["tuik_category"] = df_current["category"].apply(
        samsung_category_to_tuik
    )

    past_subset = (
        df_past[["id", "shown_price"]]
        .rename(columns={"shown_price": "past_price"})
    )
    merged = df_current.merge(past_subset, on="id", how="left")

    # 1) Basic inflation per product
    merged["basic_inflation"] = (
        (merged["shown_price"] - merged["past_price"]) / merged["past_price"]
    ) * 100
    merged["basic_inflation"] = merged["basic_inflation"].replace(
        [float("inf"), float("-inf")], pd.NA
    )

    # 2) Average inflation – arithmetic mean of per-product rates
    avg_inflation = merged["basic_inflation"].mean()

    # 3) Basket-level price-index change
    valid = merged.dropna(subset=["shown_price", "past_price"])
    sum_current = valid["shown_price"].sum()
    sum_past = valid["past_price"].sum()
    basic_inflation_index = (
        ((sum_current - sum_past) / sum_past) * 100 if sum_past else None
    )

    # 4) TUIK weighted average
    cat_avg = merged.groupby("tuik_category")["basic_inflation"].mean()
    present_codes = list(cat_avg.dropna().index)
    norm_w = normalised_weights(present_codes)
    tuik_weighted = sum(
        cat_avg[c] * norm_w[c] / 100.0
        for c in norm_w
        if c in cat_avg.index and pd.notna(cat_avg[c])
    )

    merged = merged.drop(columns=["past_price"], errors="ignore")
    return merged, basic_inflation_index, avg_inflation, tuik_weighted


def calculate_inflation(target_date=None, compare_date=None):
    """Calculate inflation metrics for Samsung Türkiye.

    Parameters
    ----------
    target_date : str, optional
        Target ("current") date in ``YYYY-MM-DD`` format.  Defaults to
        today.
    compare_date : str, optional
        Past date to compare against.  When provided, only that single
        comparison is computed.  When omitted, the four standard
        intervals (1d, 7d, 15d, 30d) are computed.

    Returns
    -------
    None
        Results are saved to:

        - ``Inflations/Datas/TechnologicalProducts/Samsung/samsung_inflation_<date>.csv``
        - ``Inflations/Datas/TechnologicalProducts/Samsung/inflation_summary.csv``
          (append-only)

    Notes
    -----
    - Matching across dates uses the ``id`` column (Samsung modelCode).
    - Price column: ``shown_price`` (post-promotion price).
    - Category column: ``category`` (mapped to TUIK groups via
      ``tuik_config.samsung_category_to_tuik``).
    - Missing historical data results in ``NaN`` values for the
      affected interval(s).
    """
    base_date = (
        datetime.strptime(target_date, "%Y-%m-%d")
        if target_date
        else datetime.today()
    )
    today_str = base_date.strftime("%Y-%m-%d")

    df_today = _load_csv(today_str)
    if df_today is None:
        logger.warning(
            f"Cannot calculate inflation – no data for {today_str}."
        )
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
    summary_row = {"date": today_str}
    detail_base = df_today.copy()
    detail_base["tuik_category"] = detail_base["category"].apply(
        samsung_category_to_tuik
    )

    for label, past_str in intervals.items():
        df_past = _load_csv(past_str)

        if df_past is None:
            logger.info(
                f"Skipping interval {label} – no data for {past_str}."
            )
            detail_base[f"basic_inflation_{label}"] = None
            summary_row[f"avg_inflation_{label}"] = None
            summary_row[f"tuik_weighted_{label}"] = None
            continue

        merged, basic_idx, avg_inf, tuik_w = _compute_metrics(df_today, df_past)

        # Attach per-product basic inflation to the detail frame
        detail_base = detail_base.merge(
            merged[["id", "basic_inflation"]].rename(
                columns={"basic_inflation": f"basic_inflation_{label}"}
            ),
            on="id",
            how="left",
        )

        summary_row[f"avg_inflation_{label}"] = avg_inf
        summary_row[f"tuik_weighted_{label}"] = tuik_w

    # ── Save detailed data ───────────────────────────────────────────────────
    detail_file = INFLATION_OUT_DIR / f"samsung_inflation_{today_str}.csv"
    detail_base.to_csv(detail_file, index=False, encoding="utf-8")
    logger.info(f"Saved detailed inflation data to: {detail_file}")

    # ── Save / update summary ────────────────────────────────────────────────
    summary_file = INFLATION_OUT_DIR / "inflation_summary.csv"
    df_summary = pd.DataFrame([summary_row])

    try:
        if summary_file.exists():
            df_existing = pd.read_csv(summary_file)
            df_existing = df_existing[df_existing["date"] != today_str]
            df_final = pd.concat([df_existing, df_summary], ignore_index=True)
            df_final.to_csv(summary_file, index=False, encoding="utf-8")
            logger.info(f"Updated inflation summary in: {summary_file}")
        else:
            df_summary.to_csv(summary_file, index=False, encoding="utf-8")
            logger.info(f"Created inflation summary in: {summary_file}")
    except Exception as e:
        logger.error(f"Failed to write summary file: {e}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Samsung inflation calculator")
    parser.add_argument(
        "--date",
        help="Target (current) date in YYYY-MM-DD format",
        default=None,
    )
    parser.add_argument(
        "--compare",
        help="Comparison (past) date in YYYY-MM-DD format",
        default=None,
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    calculate_inflation(args.date, args.compare)
