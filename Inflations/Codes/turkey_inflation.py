"""
turkey_inflation.py — Turkey-Wide Daily Inflation Calculator

Aggregates all tracked data sources in the InflationResearchStudy codebase across
six sectors and computes three inflation metrics identical to those in Migros/inflation.py:

  1. Basic Inflation   – basket-level price index change (%)
                        (sum_current / sum_past - 1) × 100
  2. Average Inflation – arithmetic mean of per-product percentage changes
  3. TUIK Weighted Avg – weighted average using TÜİK 2026 COICOP basket weights,
                         normalised to the TUIK categories present in the data

Sectors and TUIK groups covered:
  Grocery markets  → group 01  (Gıda ve alkolsüz içecekler)
  Clothing stores  → group 03  (Giyim ve ayakkabı)
  Rent / housing   → group 04  (Konut, su, elektrik, gaz)
  HomeGoods +
  Construction     → group 05  (Mobilya, ev aletleri)
  Tech products    → group 08  (Bilgi ve iletişim)
  Cosmetics        → group 13  (Kişisel bakım)

Deduplication:
  Products appearing in multiple stores within the same TUIK category are matched
  by normalised name (Turkish diacritics stripped, lowercased). Their current and
  past prices are averaged across stores before the basket calculation, preventing
  any product from carrying excess weight.

Rent treatment:
  Rent data is aggregate (city/district level), not product-level.  It is computed
  as a mean rent price change across all cities and injected directly into the
  TUIK-weighted metric as group 04.  It does not appear in the basic-index or
  average-inflation metrics, which are product-level only.

Output files (Inflations/Datas/Final_Reports/):
  turkey_inflation_{YYYY-MM-DD}.csv  — per-product rows with basic_inflation columns,
                                       plus tuik_category, sector, store fields
  turkey_inflation_summary.csv        — time-series row appended per run with all
                                       three metrics per interval plus per-sector
                                       breakdown and data-quality metadata

Usage:
    python turkey_inflation.py                    # today, 1d / 7d / 15d / 30d
    python turkey_inflation.py --date 2026-05-01  # specific target date
    python turkey_inflation.py --date 2026-05-01 --compare 2026-04-01
"""

import logging
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

# ── Path setup ────────────────────────────────────────────────────────────────
_THIS_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _THIS_DIR.parent.parent          # InflationResearchStudy/

sys.path.insert(0, str(_THIS_DIR))
from tuik_config import normalised_weights, TUIK_WEIGHTS

_DATA_ROOT = _PROJECT_ROOT / "InflationItems" / "Datas"
_OUT_DIR = _PROJECT_ROOT / "Inflations" / "Datas" / "Final_Reports"

logger = logging.getLogger(__name__)

# ── Turkish character normalisation ───────────────────────────────────────────
_TR_MAP = str.maketrans("ıİğĞşŞçÇöÖüÜ", "iIgGsScCoOuU")


def _norm(s: str) -> str:
    """Normalise a product name for cross-store deduplication."""
    if not isinstance(s, str):
        return ""
    return re.sub(r"\s+", " ", s.translate(_TR_MAP).lower().strip())


# ── Price parsing ─────────────────────────────────────────────────────────────

def _parse_price(x) -> float | None:
    """
    Parse a price from any format observed in the codebase:
      - Pure numeric (float / int)
      - Turkish: "1.234,56" or "1.250.000" or "149,50"
      - Lira prefix/suffix: "₺149,50"  /  "34,99 ₺"  /  "2.475,00TL"
      - Complex prefix: "Başlangıç:  129.999,00 ₺"
      - Single dot with 3 trailing digits: "50.499" → 50499 (Turkish thousands)
    """
    if x is None:
        return None
    if isinstance(x, (int, float)):
        return None if pd.isna(x) else float(x)

    s = str(x).strip()
    if not s:
        return None

    # Strip lira symbol, TL / TRY suffix, leading labels like "Başlangıç:"
    s = re.sub(r"₺|\bTL\b|\bTRY\b", "", s, flags=re.IGNORECASE).strip()
    # Strip trailing non-numeric suffix (e.g. "/Kg")
    s = re.sub(r"[^\d.,]+$", "", s).strip()
    # If complex prefix remains, extract the longest numeric token (= the price)
    if not re.match(r"^[\d.,]+$", s):
        m = re.findall(r"\d[\d,.]*\d|\d", s)
        if not m:
            return None
        s = max(m, key=len)

    # Normalise separators
    if "." in s and "," in s:
        if s.index(".") < s.index(","):
            # Turkish: "1.234,56"
            s = s.replace(".", "").replace(",", ".")
        else:
            # English thousands: "1,234.56"
            s = s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".")
    elif s.count(".") > 1:
        # Multiple dots → Turkish thousands "1.250.000"
        s = s.replace(".", "")
    elif re.match(r"^\d+\.\d{3}$", s):
        # Single dot with exactly 3 trailing digits: "50.499" → 50499
        s = s.replace(".", "")

    try:
        v = float(s)
        return v if v > 0 else None
    except ValueError:
        return None


# ── File header validation ────────────────────────────────────────────────────

_SKIP_SUBDIRS = {"InflationData", "output", "reports", "archive"}
_STANDARD_COLS = ["canonical_key", "product_key", "price", "store", "sector", "tuik_category"]


def _has_standard_header(fpath: Path) -> bool:
    try:
        with fpath.open(encoding="utf-8", errors="ignore") as fh:
            first = fh.readline().strip().lstrip("﻿")
        return first == "product_name,price"
    except Exception:
        return False


def _find_date_csv(store_dir: Path, date_token: str) -> Path | None:
    for f in store_dir.rglob(f"*{date_token}*.csv"):
        rel_parts = f.relative_to(store_dir).parts[:-1]
        if any(p in _SKIP_SUBDIRS for p in rel_parts):
            continue
        if _has_standard_header(f):
            return f
    return None


def _load_store_csv(fpath: Path, store: str, sector: str, tuik_code: str) -> pd.DataFrame | None:
    try:
        df = pd.read_csv(fpath, dtype=str, on_bad_lines="skip")
        df.columns = [c.lstrip("﻿").strip() for c in df.columns]
        if "product_name" not in df.columns or "price" not in df.columns:
            return None
        out = pd.DataFrame()
        out["product_key"] = df["product_name"].astype(str).str.strip()
        out["canonical_key"] = out["product_key"].apply(_norm)
        # Filter out prices that have a leading minus sign
        out["price"] = df["price"].apply(
            lambda x: _parse_price(x) if (x is None or not str(x).strip().startswith("-")) else None
        )
        out["store"] = store
        out["sector"] = sector
        out["tuik_category"] = tuik_code
        out = out[out["canonical_key"] != ""].dropna(subset=["price"])
        out = out[out["price"] > 0].reset_index(drop=True)
        return out if not out.empty else None
    except Exception as e:
        logger.debug("%s: failed to load %s — %s", store, fpath.name, e)
        return None


# ── Sector-based auto-discovery registry ─────────────────────────────────────

# Maps sector directory name → (tuik_code, sector_label, date_granularity)
# date_granularity: "daily" matches *YYYY-MM-DD*, "monthly" matches *YYYY-MM*
_SECTOR_CONFIG: dict[str, tuple[str, str, str]] = {
    "Markets":                     ("01", "market",       "daily"),
    "ClothingStores":              ("03", "clothing",     "daily"),
    "HomeGoods":                   ("05", "homegoods",    "daily"),
    "ConstructionSuppliesMarkets": ("05", "construction", "daily"),
    "Health":                      ("06", "health",       "monthly"),
    "TechnologicalProducts":       ("08", "tech",         "daily"),
    "TravelTourism":               ("11", "tourism",      "daily"),
    "Cosmetics":                   ("13", "cosmetics",    "daily"),
}


def _load_sector(
    sector_dir: Path,
    date_str: str,
    tuik_code: str,
    sector_label: str,
    date_granularity: str = "daily",
) -> list[pd.DataFrame]:
    date_token = date_str[:7] if date_granularity == "monthly" else date_str
    frames = []
    for store_dir in sorted(sector_dir.iterdir()):
        if not store_dir.is_dir():
            continue
        fpath = _find_date_csv(store_dir, date_token)
        if fpath is None:
            continue
        df = _load_store_csv(fpath, store_dir.name, sector_label, tuik_code)
        if df is not None and not df.empty:
            frames.append(df)
    return frames


# ── Pool loading and deduplication ────────────────────────────────────────────

def _load_all_stores(date_str: str) -> tuple[pd.DataFrame, list[str], int]:
    """
    Load all stores for a given date via sector auto-discovery.

    Returns
    -------
    df          : combined and deduplicated DataFrame
    stores_ok   : list of store names that had data
    n_before    : total product count before deduplication
    """
    frames: list[pd.DataFrame] = []
    for sector_name, (tuik_code, sector_label, date_gran) in _SECTOR_CONFIG.items():
        sector_dir = _DATA_ROOT / sector_name
        if not sector_dir.exists():
            continue
        frames.extend(_load_sector(sector_dir, date_str, tuik_code, sector_label, date_gran))

    if not frames:
        return pd.DataFrame(columns=_STANDARD_COLS), [], 0

    combined = pd.concat(frames, ignore_index=True)
    n_before = len(combined)
    stores_ok = list(combined["store"].unique())

    # Deduplicate within each store (same product appearing twice in one CSV)
    deduped = (
        combined
        .groupby(["store", "canonical_key", "tuik_category", "sector"], as_index=False)
        .agg(
            product_key=("product_key", "first"),
            price=("price", "mean"),
        )
    )
    return deduped, stores_ok, n_before


# ── Rent inflation helper ─────────────────────────────────────────────────────

def _rent_city_prices(date_str: str) -> dict[str, float]:
    rent_root = _DATA_ROOT / "HousesRent"
    city_prices: dict[str, list[float]] = {}
    for fpath in rent_root.rglob(f"*{date_str}*.csv"):
        if fpath.parent == rent_root:  # skip root-level aggregate files
            continue
        if not _has_standard_header(fpath):
            continue
        city_key = fpath.parent.name
        try:
            df = pd.read_csv(fpath, dtype=str, on_bad_lines="skip")
            df.columns = [c.lstrip("﻿").strip() for c in df.columns]
            prices = df["price"].apply(_parse_price).dropna()
            prices = prices[prices > 0]
            if not prices.empty:
                city_prices.setdefault(city_key, []).extend(prices.tolist())
        except Exception:
            continue
    return {k: sum(v) / len(v) for k, v in city_prices.items()}


def _rent_relative(current_str: str, past_str: str) -> float | None:
    cur_city = _rent_city_prices(current_str)
    past_city = _rent_city_prices(past_str)
    common = set(cur_city) & set(past_city)
    if not common:
        return None
    mean_cur  = sum(cur_city[c]  for c in common) / len(common)
    mean_past = sum(past_city[c] for c in common) / len(common)
    if mean_past == 0:
        return None
    return (mean_cur / mean_past - 1) * 100


def _coverage_report(present_codes: list[str]) -> tuple[float, str]:
    total_w = sum(d["weight"] for d in TUIK_WEIGHTS.values())
    covered_w = sum(TUIK_WEIGHTS[c]["weight"] for c in present_codes if c in TUIK_WEIGHTS)
    coverage_pct = covered_w / total_w * 100 if total_w else 0.0

    lines = [f"Covered TUIK basket: {coverage_pct:.2f}%"]
    for code in sorted(TUIK_WEIGHTS):
        status = "✓" if code in present_codes else "✗"
        name = TUIK_WEIGHTS[code]["name"][:35]
        weight = TUIK_WEIGHTS[code]["weight"]
        lines.append(f"  {code}  {name:<35}  {weight:>6.2f}%  {status}")
    return coverage_pct, "\n".join(lines)


# ── Core metric computation ───────────────────────────────────────────────────

def _compute_metrics(
    df_current: pd.DataFrame,
    df_past: pd.DataFrame,
) -> tuple[pd.DataFrame, float | None, float | None, float | None, dict]:
    if df_past.empty:
        return pd.DataFrame(), None, None, None, {}

    merge_keys = ["store", "canonical_key", "tuik_category", "sector"]
    past_sub = df_past[merge_keys + ["price"]].rename(columns={"price": "past_price"})
    matched = df_current.merge(past_sub, on=merge_keys, how="inner")

    if matched.empty:
        return pd.DataFrame(), None, None, None, {}

    # Relative change per (store, product): percentage form
    matched["relative"] = (matched["price"] / matched["past_price"] - 1) * 100
    matched["relative"] = matched["relative"].replace([float("inf"), float("-inf")], pd.NA)

    # Average relative across stores → one row per (canonical_key, tuik_category)
    product_rel = (
        matched
        .groupby(["canonical_key", "tuik_category", "sector"], as_index=False)
        .agg(
            product_key=("product_key", "first"),
            store=("store", lambda s: ",".join(sorted(s.unique()))),
            relative=("relative", "mean"),
        )
    )

    # basic_index: basket-level sum ratio on matched pairs
    sum_cur = matched["price"].sum()
    sum_past = matched["past_price"].sum()
    basic_index = float((sum_cur / sum_past - 1) * 100) if sum_past else None

    # avg_inflation: arithmetic mean of per-product relatives
    valid_rel = product_rel["relative"].dropna()
    avg_inflation = float(valid_rel.mean()) if not valid_rel.empty else None

    # tuik_weighted: category-level TUIK-weighted average
    cat_rel = product_rel.groupby("tuik_category")["relative"].mean()
    present_codes = list(cat_rel.dropna().index)
    norm_w = normalised_weights(present_codes)
    tuik_weighted = (
        float(sum(cat_rel[c] * norm_w[c] / 100.0 for c in norm_w if pd.notna(cat_rel.get(c))))
        if norm_w else None
    )

    # Per-sector metrics: basic_index and avg_inflation per tuik_category
    sector_metrics: dict[str, dict] = {}
    for code, grp in matched.groupby("tuik_category"):
        s_cur = grp["price"].sum()
        s_past = grp["past_price"].sum()
        s_basic = float((s_cur / s_past - 1) * 100) if s_past else None
        s_rel = product_rel.loc[product_rel["tuik_category"] == code, "relative"].dropna()
        s_avg = float(s_rel.mean()) if not s_rel.empty else None
        sector_metrics[str(code)] = {"basic_index": s_basic, "avg_inflation": s_avg}

    return product_rel, basic_index, avg_inflation, tuik_weighted, sector_metrics


# ── Main calculate function ───────────────────────────────────────────────────

def calculate_turkey_inflation(
    target_date: str | None = None,
    compare_date: str | None = None,
) -> None:
    if target_date:
        base_date = datetime.strptime(target_date, "%Y-%m-%d")
    else:
        base_date = datetime.today()
    today_str = base_date.strftime("%Y-%m-%d")

    logger.info("Loading current data for %s …", today_str)
    df_current, stores_today, n_before = _load_all_stores(today_str)

    if df_current.empty:
        logger.warning("No data found for %s — aborting.", today_str)
        return

    logger.info(
        "Loaded %d stores, %d raw rows, %d unique (store, product) pairs",
        len(stores_today), n_before, len(df_current),
    )

    present_codes = list(df_current["tuik_category"].unique())
    if _rent_city_prices(today_str):
        present_codes = list(set(present_codes) | {"04"})
    coverage_pct, coverage_str = _coverage_report(present_codes)
    logger.info("\n%s", coverage_str)

    _OUT_DIR.mkdir(parents=True, exist_ok=True)

    intervals = (
        {compare_date: compare_date}
        if compare_date
        else {
            f"{days}d": (base_date - timedelta(days=days)).strftime("%Y-%m-%d")
            for days in [15, 30]
        }
    )

    category_store_counts = df_current.groupby("tuik_category")["store"].nunique()
    category_product_counts = df_current.groupby("tuik_category")["canonical_key"].nunique()
    rent_cities = _rent_city_prices(today_str)

    summary_row: dict = {
        "date": today_str,
        "n_stores": len(stores_today),
        "n_products_raw": n_before,
        "n_products_deduped": len(df_current),
        "basket_coverage_pct": round(coverage_pct, 2),
    }
    for code, cnt in category_store_counts.items():
        summary_row[f"n_stores_{code}"] = int(cnt)
    if rent_cities:
        summary_row["n_stores_04"] = len(rent_cities)
    for code, cnt in category_product_counts.items():
        summary_row[f"n_products_{code}"] = int(cnt)

    # Detail base: one row per unique (canonical_key, tuik_category) at current date
    detail_base = (
        df_current
        .groupby(["canonical_key", "tuik_category", "sector"], as_index=False)
        .agg(
            product_key=("product_key", "first"),
            store=("store", lambda s: ",".join(sorted(s.unique()))),
        )
    )

    for label, past_str in intervals.items():
        logger.info("Computing interval %s (vs %s) …", label, past_str)
        df_past, _, _ = _load_all_stores(past_str)

        if df_past.empty:
            logger.info("  No past data for %s — skipping interval %s.", past_str, label)
            for key in ["avg_inflation", "basic_index", "tuik_weighted_products",
                        "tuik_weighted_full", "rent_inflation"]:
                summary_row[f"{key}_{label}"] = None
            continue

        product_rel, basic_idx, avg_inf, tuik_w_products, sector_metrics = _compute_metrics(df_current, df_past)

        # Attach per-product relative to detail frame
        if not product_rel.empty:
            rel_col = product_rel[["canonical_key", "tuik_category", "relative"]].rename(
                columns={"relative": f"relative_{label}"}
            )
            detail_base = detail_base.merge(rel_col, on=["canonical_key", "tuik_category"], how="left")

        summary_row[f"avg_inflation_{label}"] = avg_inf
        summary_row[f"basic_index_{label}"] = basic_idx
        summary_row[f"tuik_weighted_products_{label}"] = tuik_w_products

        rent_inf = _rent_relative(today_str, past_str)
        summary_row[f"rent_inflation_{label}"] = rent_inf

        if rent_inf is not None and tuik_w_products is not None:
            cat_rel = product_rel.groupby("tuik_category")["relative"].mean()
            cat_rel_full = cat_rel.copy()
            cat_rel_full["04"] = rent_inf
            present_all = list(cat_rel_full.dropna().index)
            norm_w_all = normalised_weights(present_all)
            tuik_w_full = float(sum(
                cat_rel_full[c] * norm_w_all[c] / 100.0
                for c in norm_w_all
                if pd.notna(cat_rel_full.get(c))
            )) if norm_w_all else tuik_w_products
        else:
            tuik_w_full = tuik_w_products
        summary_row[f"tuik_weighted_full_{label}"] = tuik_w_full

        # Per-sector breakdown
        for code, m in sector_metrics.items():
            summary_row[f"avg_inflation_{code}_{label}"] = m["avg_inflation"]
            summary_row[f"basic_index_{code}_{label}"] = m["basic_index"]
        if rent_inf is not None:
            summary_row[f"avg_inflation_04_{label}"] = rent_inf

        logger.info(
            "  [%s] basic_index=%s  avg=%s  tuik_products=%s  tuik_full=%s",
            label,
            f"{basic_idx:.3f}%" if basic_idx is not None else "N/A",
            f"{avg_inf:.3f}%"   if avg_inf is not None else "N/A",
            f"{tuik_w_products:.3f}%" if tuik_w_products is not None else "N/A",
            f"{tuik_w_full:.3f}%"     if tuik_w_full is not None else "N/A",
        )

    detail_file = _OUT_DIR / f"turkey_inflation_{today_str}.csv"
    detail_base.to_csv(detail_file, index=False, encoding="utf-8")
    logger.info("Saved per-product detail: %s", detail_file)

    summary_file = _OUT_DIR / "turkey_inflation_summary.csv"
    df_new = pd.DataFrame([summary_row])
    try:
        if summary_file.exists():
            df_existing = pd.read_csv(summary_file)
            df_existing = df_existing[df_existing["date"] != today_str]
            df_final = pd.concat([df_existing, df_new], ignore_index=True)
            df_final.to_csv(summary_file, index=False, encoding="utf-8")
        else:
            df_new.to_csv(summary_file, index=False, encoding="utf-8")
        logger.info("Updated summary: %s", summary_file)
    except Exception as e:
        logger.error("Failed to write summary: %s", e)


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Turkey-wide inflation calculator")
    parser.add_argument(
        "--date", default=None,
        help="Target (current) date in YYYY-MM-DD format (default: today)",
    )
    parser.add_argument(
        "--compare", default=None,
        help="Comparison (past) date in YYYY-MM-DD format for a single arbitrary interval",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    calculate_turkey_inflation(args.date, args.compare)
