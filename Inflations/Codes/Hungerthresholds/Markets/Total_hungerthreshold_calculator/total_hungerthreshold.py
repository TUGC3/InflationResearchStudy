"""
Hunger Threshold — Multi-Market Aggregation Calculator
====================================================

Computes the canonical monthly hunger threshold by averaging
prices across all markets for each basket item.

Logic:
  1. Each market × each product → monthly avg unit price (from each market's detail CSV)
  2. For markets with multiple snapshots in the same month, snapshots are averaged
        (e.g. Kale: Mar-01 + Mar-30 → single "Mar 2026" value)
  3. Each product × each month → average unit price across markets that stock it
        (N/A markets excluded)
  4. Avg unit price × basket quantity → monthly cost
  5. All items summed → hunger threshold for that month

Input:
  - 13 market detail CSV (hunger_threshold_*_detail.csv)

Output:
  - aggregate_detail.csv   : per-product monthly average price and cost
  - aggregate_summary.csv  : monthly total hunger threshold
  - Console: detailed table
"""

import pandas as pd
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

# ── 2. DATE → CANONICAL MONTH MAPPING ───────────────────
# Multiple snapshot dates within the same month are averaged.
MONTH_MAP = {
    # February 2026
    "Feb 2026":    "Feb 2026",
    "Feb-20 2026": "Feb 2026",
    "Feb-21 2026": "Feb 2026",
    "Feb-23 2026": "Feb 2026",
    "Feb-24 2026": "Feb 2026",
    "Feb-26 2026": "Feb 2026",
    "Feb-27 2026": "Feb 2026",
    "Feb-28 2026": "Feb 2026",
    # March 2026
    "Mar 2026":    "Mar 2026",
    "Mar-01 2026": "Mar 2026",
    "Mar-30 2026": "Mar 2026",
    # April 2026
    "Apr 2026":    "Apr 2026",
    "Apr2 2026":   "Apr 2026",
    # May 2026
    "May 2026":    "May 2026",
}

MONTH_ORDER = ["Feb 2026", "Mar 2026", "Apr 2026", "May 2026"]

# ── 3. FOOD BASKET (qty per month) ──────────────────────
FOOD_BASKET = [
    # ── Dairy Products ──────────────────────────
    ("Dairy Products",      "Yogurt",                             "Kg",      59.7),
    ("Dairy Products",      "White Cheese",                       "Kg",      5.3),
    # ── Meat and Protein ────────────────────────
    ("Meat and Protein",      "Cubed Meat / Lamb Meat",             "Kg",      3.3),
    ("Meat and Protein",      "Chicken",                            "Kg",      7.0),
    ("Meat and Protein",      "Fish",                               "Kg",      5.1),
    ("Meat and Protein",      "Eggs",                               "Piece",   60.0),
    # ── Legumes ─────────────────────────────────
    ("Legumes",      "Chickpeas",                          "Kg",      5.6),
    # ── Nuts and Seeds ──────────────────────────
    ("Nuts and Seeds",      "Walnut / Hazelnut / Peanut",         "Kg",      2.7),
    # ── Grains ──────────────────────────────────
    ("Grains",      "Bread",                              "Kg",      18.0),
    # ── Fruits ──────────────────────────────────
    ("Fruits",      "Banana",                             "Kg",      16.7),
    ("Fruits",      "Seasonal Fruit",                     "Kg",      12.9),
    # ── Vegetables ──────────────────────────────
    ("Vegetables",      "Onion",                              "Kg",      18.0),
    ("Vegetables",      "Eggplant / Zucchini",                "Kg",      34.7),
    ("Vegetables",      "Other Vegetables",                   "Kg",      14.8),
    # ── Oils ────────────────────────────────────
    ("Oils",      "Olive Oil",                          "Liter",   1.0),
]

BASKET_QTY = {product: qty for _, product, _, qty in FOOD_BASKET}
BASKET_CAT = {product: cat  for cat, product, _, _ in FOOD_BASKET}

# ── 4. LOAD & NORMALISE ALL DETAIL CSVs ─────────────────
def load_market(market_name: str, csv_path: str) -> pd.DataFrame | None:
    if not Path(csv_path).exists():
        print(f"  ⚠  File not found: {csv_path}")
        return None
    df = pd.read_csv(csv_path)
    df["market"]      = market_name
    df["canon_month"] = df["date"].map(MONTH_MAP)
    df = df[df["canon_month"].notna()].copy()
    return df

frames = []
for mkt, path in DETAIL_FILES.items():
    df = load_market(mkt, path)
    if df is not None:
        frames.append(df)

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
        n_markets         =("unit_price", "count"),
        market_list       =("market",     lambda x: ", ".join(sorted(x))),
    )
    .reset_index()
)

# ── 7. COMPUTE MONTHLY COST ──────────────────────────────
agg["category"]        = agg["product"].map(BASKET_CAT)
agg["monthly_qty"]     = agg["product"].map(BASKET_QTY)
agg["monthly_cost_TRY"]= agg["avg_unit_price_TRY"] * agg["monthly_qty"]

# ── 8. MONTHLY TOTALS ────────────────────────────────────
monthly_totals = (
    agg
    .groupby("canon_month")["monthly_cost_TRY"]
    .sum()
    .reindex(MONTH_ORDER)
    .dropna()
    .reset_index()
    .rename(columns={"canon_month": "month", "monthly_cost_TRY": "hunger_threshold_TRY"})
)

# ── 9. PRINT RESULTS ─────────────────────────────────────
print("\n" + "="*100)
print("  PER-PRODUCT AVERAGE PRICES AND MONTHLY COSTS")
print("="*100)

# Pivot: product × month
pivot_price = agg.pivot_table(
    index=["category","product","monthly_qty"],
    columns="canon_month",
    values="avg_unit_price_TRY"
).reindex(columns=MONTH_ORDER, fill_value=float("nan"))

pivot_cost = agg.pivot_table(
    index=["category","product","monthly_qty"],
    columns="canon_month",
    values="monthly_cost_TRY"
).reindex(columns=MONTH_ORDER, fill_value=float("nan"))

pivot_n = agg.pivot_table(
    index=["category","product"],
    columns="canon_month",
    values="n_markets"
).reindex(columns=MONTH_ORDER, fill_value=0)

header = (f"\n  {'Kategori':<22} {'Ürün':<30} {'Adet':>5} | "
          + " | ".join(f"{'Fiyat':>8} {'Maliyet':>9} {'N':>2}" for _ in MONTH_ORDER))
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
            cost_row = pivot_cost.loc[(cat, product, qty)]
            cost = cost_row.get(m, float("nan"))
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
    print(f"    {'':2}{product:<30} {qty:>5.1f} |{months_str}")

# Summary
print("\n\n" + "="*70)
print("  MONTHLY HUNGER THRESHOLD — 13-MARKET AVERAGE")
print("="*70)
print(f"  {'Month':<14} {'Threshold (₺)':>18}  {'Change':>8}")
prev = None
for _, row in monthly_totals.iterrows():
    diff = f"{(row['hunger_threshold_TRY']-prev)/prev*100:+.1f}%" if prev else "—"
    print(f"  {row['month']:<14} ₺{row['hunger_threshold_TRY']:>16,.2f}  {diff:>8}")
    prev = row['hunger_threshold_TRY']

# ── 10. SAVE ─────────────────────────────────────────────
# Detailed output
detail_out = agg[["canon_month","category","product","monthly_qty",
                   "avg_unit_price_TRY","monthly_cost_TRY","n_markets","market_list"]].copy()
detail_out = detail_out.rename(columns={"canon_month":"month"})
detail_out["avg_unit_price_TRY"] = detail_out["avg_unit_price_TRY"].round(2)
detail_out["monthly_cost_TRY"]   = detail_out["monthly_cost_TRY"].round(2)
detail_out.sort_values(["month","category","product"], inplace=True)
detail_out.to_csv(OUTPUT_DETAIL,  index=False)

monthly_totals["hunger_threshold_TRY"] = monthly_totals["hunger_threshold_TRY"].round(2)
monthly_totals.to_csv(OUTPUT_SUMMARY, index=False)

print(f"\nDetay   → {OUTPUT_DETAIL}")
print(f"Summary → {OUTPUT_SUMMARY}")
