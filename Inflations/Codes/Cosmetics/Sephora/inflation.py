"""
inflation.py — Sephora Daily Inflation Calculator

Computes three inflation metrics for Sephora products:
  1. Basic Inflation   – basket-level price index change (%), i.e. sum of
                         current sale prices vs sum of past sale prices
                         across matched products.
  2. Average Inflation – arithmetic mean of per-product percentage price
                         changes.
  3. TUIK Weighted Avg – category-weighted average using TUIK 2026 CPI
                         basket weights, normalised to only the TUIK
                         groups that have data for the interval.

Intervals
---------
- Default: 1d / 7d / 15d / 30d relative to *target_date*.
- A pair of ``target_date`` + ``compare_date`` also allows arbitrary
  two-date comparisons.

Sephora TUIK mapping
--------------------
Sephora is a pure-play cosmetics retailer so practically every SKU maps
to TUIK group 12 (Kişisel bakım).  A small set of accessories
(brushes, mirrors, makeup pouches) maps to TUIK group 05 (household).
See ``tuik_config.sephora_category_to_tuik``.

Output Files
------------
- ``sephora_inflation_YYYY-MM-DD.csv`` — Detailed per-product records
  with per-interval ``basic_inflation_{label}`` columns added.
- ``inflation_summary.csv``            — Store-level summary (one row
  per target_date) with ``avg_inflation_{label}`` and
  ``tuik_weighted_{label}`` columns.

Usage
-----
```
python inflation.py                             # today's date, 1d/7d/15d/30d
python inflation.py --date 2026-03-20           # specific target date
python inflation.py --date 2026-03-20 --compare 2026-03-10
```
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

# ── Path setup ────────────────────────────────────────────────────────────────
_THIS_DIR     = Path(__file__).resolve().parent                 # …/Inflations/Codes/Cosmetics/Sephora
_CODES_DIR    = _THIS_DIR.parent.parent                         # …/Inflations/Codes
_PROJECT_ROOT = _CODES_DIR.parent.parent                        # …/InflationResearchStudy

sys.path.insert(0, str(_THIS_DIR))
from tuik_config import (  # noqa: E402  – import after sys.path setup
    TUIK_WEIGHTS,
    normalised_weights,
    sephora_category_to_tuik,
)

# Scraper config for data paths
_scraper_dir = _PROJECT_ROOT / "InflationItems" / "Codes" / "Cosmetics" / "Sephora" / "scripts"
sys.path.insert(0, str(_scraper_dir))
import config  # noqa: E402  – scraper-side config

logger = logging.getLogger(__name__)

# ── Directories ───────────────────────────────────────────────────────────────
DATA_DIR          = Path(config.BASE_OUTPUT_DIR)
INFLATION_OUT_DIR = _CODES_DIR.parent / "Datas" / "Cosmetics" / "Sephora"


def _load_csv(date_str: str):
    """Load a Sephora daily CSV by date string, return DataFrame or None."""
    fpath = DATA_DIR / f"sephora_{date_str}.csv"
    if not fpath.exists():
        logger.info("Data file not found: %s", fpath)
        return None
    try:
        df = pd.read_csv(fpath, encoding="utf-8-sig")
        if "sale_price" in df.columns:
            df["sale_price"] = pd.to_numeric(df["sale_price"], errors="coerce")
        return df
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to read %s: %s", fpath, exc)
        return None


def _assign_tuik_category(df: pd.DataFrame) -> pd.DataFrame:
    """Attach a ``tuik_category`` column by mapping the breadcrumb /
    fallback ``category_id`` column through
    :func:`sephora_category_to_tuik`."""
    df = df.copy()
    # Prefer the breadcrumb label when it's non-empty; fall back to the
    # scraper's category slug (``category_id``) otherwise.
    if "category" in df.columns:
        primary = df["category"].fillna("").astype(str)
    else:
        primary = pd.Series([""] * len(df))
    if "category_id" in df.columns:
        fallback = df["category_id"].fillna("").astype(str)
    else:
        fallback = pd.Series([""] * len(df))

    combined = primary.where(primary.str.strip().astype(bool), fallback)
    df["tuik_category"] = combined.apply(sephora_category_to_tuik)
    return df


def _compute_metrics(df_current: pd.DataFrame, df_past: pd.DataFrame):
    """Compute the three inflation metrics between two daily DataFrames.

    Returns
    -------
    merged                : DataFrame with ``basic_inflation`` column
    basic_inflation_index : float – basket-level price index change (%)
    avg_inflation         : float – arithmetic mean of per-product rates
    tuik_weighted         : float – TUIK-weighted average inflation
    """
    df_current = _assign_tuik_category(df_current)

    past_subset = df_past[["id", "sale_price"]].rename(columns={"sale_price": "past_price"})
    merged = df_current.merge(past_subset, on="id", how="left")

    # 1) Per-product inflation rates
    merged["basic_inflation"] = (
        (merged["sale_price"] - merged["past_price"]) / merged["past_price"]
    ) * 100
    merged["basic_inflation"] = merged["basic_inflation"].replace(
        [float("inf"), float("-inf")], pd.NA
    )

    # 2) Arithmetic mean
    avg_inflation = merged["basic_inflation"].mean()

    # 3) Basket-level index (sum-based)
    valid = merged.dropna(subset=["sale_price", "past_price"])
    sum_current = valid["sale_price"].sum()
    sum_past = valid["past_price"].sum()
    basic_inflation_index = (
        ((sum_current - sum_past) / sum_past) * 100 if sum_past else None
    )

    # 4) TUIK-weighted average across present categories
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


def calculate_inflation(target_date: str | None = None, compare_date: str | None = None) -> None:
    """Calculate inflation metrics for Sephora.

    Parameters
    ----------
    target_date  : str (YYYY-MM-DD), optional
        The *current* date.  Defaults to today.
    compare_date : str (YYYY-MM-DD), optional
        If given, compute metrics only between ``compare_date`` (past)
        and ``target_date`` (current).  If omitted, compute for the
        four standard intervals (1d / 7d / 15d / 30d back).
    """
    base_date = (
        datetime.strptime(target_date, "%Y-%m-%d") if target_date else datetime.today()
    )
    today_str = base_date.strftime("%Y-%m-%d")

    df_today = _load_csv(today_str)
    if df_today is None:
        logger.warning("Cannot calculate inflation – no data for %s.", today_str)
        return

    INFLATION_OUT_DIR.mkdir(parents=True, exist_ok=True)

    if compare_date:
        intervals = {compare_date: compare_date}
    else:
        intervals = {
            f"{days}d": (base_date - timedelta(days=days)).strftime("%Y-%m-%d")
            for days in (1, 7, 15, 30)
        }

    summary_row: dict[str, object] = {"date": today_str}
    detail_base = _assign_tuik_category(df_today)

    for label, past_str in intervals.items():
        df_past = _load_csv(past_str)
        if df_past is None:
            logger.info("Skipping interval %s – no data for %s.", label, past_str)
            detail_base[f"basic_inflation_{label}"] = None
            summary_row[f"avg_inflation_{label}"] = None
            summary_row[f"tuik_weighted_{label}"] = None
            continue

        merged, _basic_idx, avg_inf, tuik_w = _compute_metrics(df_today, df_past)

        detail_base = detail_base.merge(
            merged[["id", "basic_inflation"]].rename(
                columns={"basic_inflation": f"basic_inflation_{label}"}
            ),
            on="id",
            how="left",
        )

        summary_row[f"avg_inflation_{label}"] = avg_inf
        summary_row[f"tuik_weighted_{label}"] = tuik_w

    # ── Save detailed per-product data ────────────────────────────────────
    detail_file = INFLATION_OUT_DIR / f"sephora_inflation_{today_str}.csv"
    detail_base.to_csv(detail_file, index=False, encoding="utf-8")
    logger.info("Saved detailed inflation data to: %s", detail_file)

    # ── Save / update store-level summary ─────────────────────────────────
    summary_file = INFLATION_OUT_DIR / "inflation_summary.csv"
    df_summary = pd.DataFrame([summary_row])
    try:
        if summary_file.exists():
            df_existing = pd.read_csv(summary_file)
            df_existing = df_existing[df_existing["date"] != today_str]
            df_final = pd.concat([df_existing, df_summary], ignore_index=True)
            df_final.to_csv(summary_file, index=False, encoding="utf-8")
            logger.info("Updated inflation summary in: %s", summary_file)
        else:
            df_summary.to_csv(summary_file, index=False, encoding="utf-8")
            logger.info("Created inflation summary in: %s", summary_file)
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to write summary file: %s", exc)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sephora inflation calculator")
    parser.add_argument("--date", help="Target (current) date in YYYY-MM-DD format", default=None)
    parser.add_argument("--compare", help="Comparison (past) date in YYYY-MM-DD format", default=None)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    calculate_inflation(args.date, args.compare)
