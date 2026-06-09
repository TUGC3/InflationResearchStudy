import pandas as pd
import re
import os
from pathlib import Path

# ── 1. PATHS ────────────────────────────────────────────
BASE_DIR = "/Users/efeyildirim/Downloads/Marketler"

DETAIL_FILES = {
    "A101":         f"{BASE_DIR}/A101/hunger_threshold_detail.csv",
    "Arden":        f"{BASE_DIR}/Arden/hunger_threshold_detail.csv",
    "Basdas":       f"{BASE_DIR}/Basdas/hunger_threshold_detail.csv",
    "Baskent":      f"{BASE_DIR}/Baskent/hunger_threshold_detail.csv",
    "CarrefourSA":  f"{BASE_DIR}/CarrefourSA/hunger_threshold_detail.csv",
    "Gurmar":       f"{BASE_DIR}/Gurmar/hunger_threshold_detail.csv",
    "Hapeloglu":    f"{BASE_DIR}/Hapeloglu/hunger_threshold_detail.csv",
    "Kale":         f"{BASE_DIR}/Kale/hunger_threshold_detail.csv",
    "Kim":          f"{BASE_DIR}/Kim/hunger_threshold_detail.csv",
    "Macrocenter":  f"{BASE_DIR}/Macrocenter/hunger_threshold_detail.csv",
    "Marketzade":   f"{BASE_DIR}/Marketzade/hunger_threshold_detail.csv",
    "Migros":       f"{BASE_DIR}/Migros/hunger_threshold_detail.csv",
    "Sozsanal":     f"{BASE_DIR}/Sozsanal/hunger_threshold_detail.csv",
}

OUTPUT_DETAIL  = f"{BASE_DIR}/aggregate_detail.csv"
OUTPUT_SUMMARY = f"{BASE_DIR}/aggregate_summary.csv"

MONTH_ORDER = ["Feb 2026", "Mar 2026", "Apr 2026", "May 2026"]

# ── 2. ROBUST DATE → CANONICAL MONTH ────────────────────
# Handles any date format a market script might produce.
# Strategy:
#   a) Try pandas date parse on the raw string → strftime("%b %Y")
#   b) Fallback: regex extract "Mon[-]?DD? YYYY" or "Mon YYYY" patterns
#   c) Hard-coded aliases for known non-standard labels (e.g. "Apr2 2026")

MONTH_ALIASES = {
    "Apr2 2026": "Apr 2026",   # Arden's second April snapshot
}

def to_canon_month(date_str: str) -> str | None:
    """Convert any date string to 'Mon YYYY' canonical form, or None if unrecognisable."""
    s = str(date_str).strip()

    # 1. Check aliases first
    if s in MONTH_ALIASES:
        return MONTH_ALIASES[s]

    # 2. Try pandas parse (handles ISO dates, "Feb-20 2026", "Feb 2026", etc.)
    try:
        parsed = pd.to_datetime(s, dayfirst=False, errors="raise")
        canon = parsed.strftime("%b %Y")
        if canon in MONTH_ORDER or True:   # accept any valid month
            return canon
    except Exception:
        pass

    # 3. Regex fallback: "MMM[-]?DD? YYYY" or "MMM YYYY"
    m = re.match(
        r"^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
        r"(?:-\d{1,2})?\s+(\d{4})$",
        s, re.IGNORECASE
    )
    if m:
        return f"{m.group(1).capitalize()} {m.group(2)}"

    return None   # unrecognisable — row will be dropped with a warning


# ── 3. FOOD BASKET (qty per month) ──────────────────────
FOOD_BASKET = [
    # ── Dairy Products ──────────────────────────
    ("Dairy Products",      "Yogurt",                             "Kg",      59.7),
    ("Dairy Products",      "White Cheese",                       "Kg",      5.7),
    # ── Meat and Protein ────────────────────────
    ("Meat and Protein",      "Cubed Meat / Lamb Meat",             "Kg",      4.6),
    ("Meat and Protein",      "Chicken",                            "Kg",      10.3),
    ("Meat and Protein",      "Fish",                               "Kg",      6.9),
    ("Meat and Protein",      "Eggs",                               "Piece",   120.0),
    # ── Legumes ─────────────────────────────────
    ("Legumes",      "Chickpeas",                          "Kg",      1.8),
    # ── Nuts and Seeds ──────────────────────────
    ("Nuts and Seeds",      "Walnut / Hazelnut / Peanut",         "Kg",      2.7),
    # ── Grains ──────────────────────────────────
    ("Grains",      "Bread",                              "Kg",      18.0),
    # ── Fruits ──────────────────────────────────
    ("Fruits",      "Banana",                             "Kg",      16.7),
    ("Fruits",      "Seasonal Fruit",                     "Kg",      12.9),
    # ── Vegetables ──────────────────────────────
    ("Vegetables",      "Onion",                              "Kg",      18.0),
    ("Vegetables",      "Eggplant / Zucchini",                "Kg",      23.1),
    ("Vegetables",      "Other Vegetables",                   "Kg",      11.8),
    # ── Oils ────────────────────────────────────
    ("Oils",      "Olive Oil",                          "Liter",   1.1),
    # ── Grissini ────────────────────────────────────
    ("Other Food Products", "Grissini", "Kg", 2.1),
]

BASKET_QTY      = {p: qty for _, p, _, qty in FOOD_BASKET}
BASKET_CAT      = {p: cat for cat, p, _, _  in FOOD_BASKET}
REQUIRED_ITEMS  = set(BASKET_QTY.keys())          # all 15 items are required

# ── 4. LOAD & NORMALISE ALL DETAIL CSVs ─────────────────
def load_market(market_name: str, csv_path: str) -> pd.DataFrame | None:
    if not Path(csv_path).exists():
        print(f"  ⚠  File not found: {csv_path}")
        return None
    df = pd.read_csv(csv_path)
    df["market"] = market_name

    # Robust date mapping
    df["canon_month"] = df["date"].apply(to_canon_month)

    dropped = df["canon_month"].isna().sum()
    if dropped:
        bad = df.loc[df["canon_month"].isna(), "date"].unique()
        print(f"  ⚠  {market_name}: {dropped} rows dropped — unrecognised dates: {bad}")

    df = df[df["canon_month"].isin(MONTH_ORDER)].copy()
    return df

frames = []
for mkt, path in DETAIL_FILES.items():
    df = load_market(mkt, path)
    if df is not None and len(df):
        frames.append(df)

if not frames:
    raise RuntimeError("No market data loaded — check DETAIL_FILES paths.")

all_df = pd.concat(frames, ignore_index=True)

# ── 5. AVERAGE WITHIN-MONTH SNAPSHOTS PER MARKET ────────
# e.g. Kale has Mar-01 and Mar-30 → average to get one "Mar 2026" per product
market_monthly = (
    all_df
    .dropna(subset=["avg_unit_price_TRY"])
    .groupby(["market", "canon_month", "product"])
    ["avg_unit_price_TRY"]
    .mean()
    .reset_index()
    .rename(columns={"avg_unit_price_TRY": "unit_price"})
)

# ── 6. CROSS-MARKET AVERAGE PER PRODUCT × MONTH ─────────
agg = (
    market_monthly
    .groupby(["canon_month", "product"])
    .agg(
        avg_unit_price_TRY=("unit_price", "mean"),
        n_markets          =("unit_price", "count"),
        market_list        =("market",     lambda x: ", ".join(sorted(x))),
    )
    .reset_index()
)

# ── 7. COMPUTE MONTHLY COST ──────────────────────────────
agg["category"]         = agg["product"].map(BASKET_CAT)
agg["monthly_qty"]      = agg["product"].map(BASKET_QTY)
agg["monthly_cost_TRY"] = agg["avg_unit_price_TRY"] * agg["monthly_qty"]

# ── 8. COVERAGE CHECK — DO NOT SUM INCOMPLETE MONTHS ────
#
# For each month, check whether every required basket item has a price.
# pandas .sum() silently skips NaN — so if an item is missing, the total
# is underreported without any warning. We fix this by:
#   - computing per-month coverage stats
#   - only including months where ALL required items are priced
#   - printing a clear warning (and recording in the summary CSV) when a
#     month is incomplete

def coverage_for_month(month: str) -> dict:
    """Return coverage stats for one canonical month."""
    priced = set(
        agg.loc[
            (agg["canon_month"] == month) &
            agg["avg_unit_price_TRY"].notna(),
            "product"
        ]
    )
    available = REQUIRED_ITEMS & priced
    missing   = REQUIRED_ITEMS - priced
    return {
        "n_required":  len(REQUIRED_ITEMS),
        "n_available": len(available),
        "n_missing":   len(missing),
        "missing":     sorted(missing),
        "coverage":    len(available) / len(REQUIRED_ITEMS),
        "complete":    len(missing) == 0,
    }

coverage = {m: coverage_for_month(m) for m in MONTH_ORDER}

# ── 9. MONTHLY TOTALS (complete months only) ─────────────
summary_rows = []
for month in MONTH_ORDER:
    cov = coverage[month]
    month_data = agg[agg["canon_month"] == month]
    if month_data.empty:
        continue

    if not cov["complete"]:
        threshold = None   # refuse to compute a misleading total
    else:
        threshold = month_data["monthly_cost_TRY"].sum()

    summary_rows.append({
        "month":                month,
        "hunger_threshold_TRY": round(threshold, 2) if threshold is not None else None,
        "n_required_items":     cov["n_required"],
        "n_available_items":    cov["n_available"],
        "n_missing_items":      cov["n_missing"],
        "missing_items":        "; ".join(cov["missing"]) if cov["missing"] else "",
        "coverage_rate":        round(cov["coverage"] * 100, 1),
    })

monthly_totals = pd.DataFrame(summary_rows)

# ── 10. PRINT RESULTS ────────────────────────────────────
print("\n" + "="*100)
print("  PER-PRODUCT AVERAGE PRICES AND MONTHLY COSTS")
print("="*100)

pivot_price = agg.pivot_table(
    index=["category", "product", "monthly_qty"],
    columns="canon_month",
    values="avg_unit_price_TRY"
).reindex(columns=MONTH_ORDER, fill_value=float("nan"))

pivot_cost = agg.pivot_table(
    index=["category", "product", "monthly_qty"],
    columns="canon_month",
    values="monthly_cost_TRY"
).reindex(columns=MONTH_ORDER, fill_value=float("nan"))

pivot_n = agg.pivot_table(
    index=["category", "product"],
    columns="canon_month",
    values="n_markets"
).reindex(columns=MONTH_ORDER, fill_value=0)

header = (f"\n  {'Category':<22} {'Product':<30} {'Qty':>5} | "
          + " | ".join(f"{'Price':>8} {'Cost':>9} {'N':>2}" for _ in MONTH_ORDER))
print(header)
print(f"  {'─'*22} {'─'*30} {'─'*5}-+-"
      + "-+-".join(f"{'─'*8} {'─'*9} {'─'*2}" for _ in MONTH_ORDER))

prev_cat = None
for (cat, product, qty), row_p in pivot_price.iterrows():
    if cat != prev_cat:
        print(f"\n  {cat}")
        prev_cat = cat
    months_str = ""
    for m in MONTH_ORDER:
        price = row_p.get(m, float("nan"))
        try:
            cost = pivot_cost.loc[(cat, product, qty)].get(m, float("nan"))
        except KeyError:
            cost = float("nan")
        try:
            n = int(pivot_n.loc[(cat, product)].get(m, 0))
        except KeyError:
            n = 0
        if pd.isna(price):
            months_str += f"  {'N/A':>8} {'N/A':>9}  0 |"
        else:
            months_str += f"  ₺{price:>7,.0f} ₺{cost:>8,.0f} {n:>2} |"
    print(f"    {product:<30} {qty:>5.1f} |{months_str}")

# Summary with coverage
print("\n\n" + "="*80)
print("  MONTHLY HUNGER THRESHOLD — 13-MARKET AVERAGE")
print("="*80)
print(f"  {'Month':<14} {'Threshold (₺)':>16}  {'Change':>8}  {'Coverage':>10}  {'Missing'}")
print(f"  {'─'*14} {'─'*16}  {'─'*8}  {'─'*10}  {'─'*30}")

prev = None
for _, row in monthly_totals.iterrows():
    thresh = row["hunger_threshold_TRY"]
    if pd.isna(thresh):
        thresh_str = f"  {'INCOMPLETE':>16}"
        diff_str   = "       —"
    else:
        thresh_str = f"  ₺{thresh:>14,.2f}"
        diff_str   = f"{(thresh-prev)/prev*100:+.1f}%" if prev is not None else "       —"
        prev = thresh

    cov_str     = f"{row['coverage_rate']:.1f}% ({row['n_available_items']}/{row['n_required_items']})"
    missing_str = row["missing_items"] if row["missing_items"] else "—"
    print(f"  {row['month']:<14}{thresh_str}  {diff_str:>8}  {cov_str:>10}  {missing_str}")

# Warn loudly if any month is incomplete
incomplete = monthly_totals[monthly_totals["hunger_threshold_TRY"].isna()]
if len(incomplete):
    print("\n  ⚠  WARNING — threshold NOT computed for incomplete months:")
    for _, row in incomplete.iterrows():
        print(f"     {row['month']}: missing → {row['missing_items']}")
    print("     Add market data or accept N/A for these months.\n")

# ── 11. SAVE ─────────────────────────────────────────────
detail_out = agg[[
    "canon_month", "category", "product", "monthly_qty",
    "avg_unit_price_TRY", "monthly_cost_TRY", "n_markets", "market_list"
]].copy()
detail_out = detail_out.rename(columns={"canon_month": "month"})
detail_out["avg_unit_price_TRY"] = detail_out["avg_unit_price_TRY"].round(2)
detail_out["monthly_cost_TRY"]   = detail_out["monthly_cost_TRY"].round(2)
detail_out.sort_values(["month", "category", "product"], inplace=True)
detail_out.to_csv(OUTPUT_DETAIL, index=False)

monthly_totals.to_csv(OUTPUT_SUMMARY, index=False)

print(f"Detail  → {OUTPUT_DETAIL}")
print(f"Summary → {OUTPUT_SUMMARY}")
