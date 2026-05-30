"""
NOT AVAILABLE AT BASKENT (N/A for all months):
  Milk, Yogurt, White Cheese, Kashar, Minced Meat, Cubed Meat,
  Chicken, Fish, Eggs, Bread, Flour (standard wheat), Semolina,
  Apple, Orange/Mandarin, Banana, Seasonal Fruit,
  Potato, Onion, Tomato, Cucumber, Pepper, Eggplant/Zucchini,
  Carrot, Greens, Other Vegetables,
  Sunflower Oil, Butter, Margarine, Sugar, Honey (standalone)

AVAILABLE (Feb only, Mart+ has very limited stock):
  Red/Green Lentils, Chickpeas, Dried Beans, Bulgur, Rice, Pasta,
  Olive Oil, Olives, Tea, Tomato Paste, Jam, Molasses, Salt,
  Average Spices, Linden/Herbal Tea, Nuts, Honey (Feb has honey)
"""

import pandas as pd
import re
from pathlib import Path

# ─────────────────────────────────────────────────────
# 1.  PATHS  ←  edit BASE_DIR to your folder
# ─────────────────────────────────────────────────────
BASE_DIR = "/Users/efeyildirim/Downloads/Marketler/Baskent"

FILES = {
    "Feb-24 2026": f"{BASE_DIR}/baskent_2026-02-24.csv",
    "Feb-28 2026": f"{BASE_DIR}/baskent_2026-02-28.csv",
    "Mar 2026":    f"{BASE_DIR}/baskent_2026-03-31.csv",
    "Apr 2026":    f"{BASE_DIR}/baskent_2026-04-30.csv",
    "May 2026":    f"{BASE_DIR}/baskent_2026-05-27.csv",
}

OUTPUT_DETAIL  = f"{BASE_DIR}/hunger_threshold_detail.csv"
OUTPUT_SUMMARY = f"{BASE_DIR}/hunger_threshold_summary.csv"

# ─────────────────────────────────────────────────────
# 2.  FOOD BASKET  
# ─────────────────────────────────────────────────────
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

# ─────────────────────────────────────────────────────
# 3.  MATCH RULES
# ─────────────────────────────────────────────────────
# kw=[] means not stocked → N/A
MATCH_RULES = {
    # ── Not available ──────────────────────────────────
    "Milk":                       {"kw": [], "ex": [], "unit": "ml_or_L"},
    "Yogurt":                     {"kw": [], "ex": [], "unit": "kg"},
    "White Cheese":               {"kw": [], "ex": [], "unit": "kg"},
    "Kashar / Other Cheese":      {"kw": [], "ex": [], "unit": "kg"},
    "Minced Meat":                {"kw": [], "ex": [], "unit": "kg"},
    "Cubed Meat / Lamb Meat":     {"kw": [], "ex": [], "unit": "kg"},
    "Chicken":                    {"kw": [], "ex": [], "unit": "kg"},
    "Fish":                       {"kw": [], "ex": [], "unit": "kg"},
    "Eggs":                       {"kw": [], "ex": [], "unit": "piece"},
    "Bread": {
        "kw":  ["Ekmek"],
        "ex":  ["Hamburger","Sandviç","Tost","Lavaş","Tortilla","Gevrek",
                "Kızarmış","Etimek","Grissini","Fıstıklı","Sütlü","Patatesli",
                "Fındıklı","Üzümlü","Çikolata"],
        "unit": "kg",
        "min_price_per_kg": 50,
    },
    "Flour":                      {"kw": [], "ex": [], "unit": "kg"},
    "Semolina":                   {"kw": [], "ex": [], "unit": "kg"},
    "Apple":                      {"kw": [], "ex": [], "unit": "kg"},
    "Orange / Mandarin":          {"kw": [], "ex": [], "unit": "kg"},
    "Banana":                     {"kw": [], "ex": [], "unit": "kg"},
    "Seasonal Fruit":             {"kw": [], "ex": [], "unit": "kg"},
    "Potato":                     {"kw": [], "ex": [], "unit": "kg"},
    "Onion":                      {"kw": [], "ex": [], "unit": "kg"},
    "Tomato":                     {"kw": [], "ex": [], "unit": "kg"},
    "Cucumber":                   {"kw": [], "ex": [], "unit": "kg"},
    "Pepper":                     {"kw": [], "ex": [], "unit": "kg"},
    "Eggplant / Zucchini":        {"kw": [], "ex": [], "unit": "kg"},
    "Carrot":                     {"kw": [], "ex": [], "unit": "kg"},
    "Greens / Lettuce / Parsley": {"kw": [], "ex": [], "unit": "piece"},
    "Other Vegetables":           {"kw": [], "ex": [], "unit": "kg"},
    "Sunflower Oil":              {"kw": [], "ex": [], "unit": "ml_or_L"},
    "Butter":                     {"kw": [], "ex": [], "unit": "kg"},
    "Margarine":                  {"kw": [], "ex": [], "unit": "kg"},
    "Sugar":                      {"kw": [], "ex": [], "unit": "kg"},
    # ── Available ──────────────────────────────────────
    "Dried Beans": {
        "kw":  ["Kuru Fasulye","Fasulye"],
        "ex":  ["Konserve","Haşlanmış","Turşu","Un","Çorba"],
        "unit": "kg",
    },
    "Chickpeas": {
        "kw":  ["Nohut"],
        "ex":  ["Konserve","Haşlanmış","Un","Çorba"],
        "unit": "kg",
    },
    "Red Lentils": {
        "kw":  ["Kırmızı Mercimek"],
        "ex":  ["Un","Çorba"],
        "unit": "kg",
    },
    "Green Lentils": {
        "kw":  ["Yeşil Mercimek"],
        "ex":  ["Un","Çorba"],
        "unit": "kg",
    },
    "Walnut / Hazelnut / Peanut": {
        "kw":  ["Yer Fıstığı","Fındık","Ceviz"],
        "ex":  ["Ezmesi","Kreması","Çikolata","Aromalı","Reçel","Kek","Baklava",
                "Kurabiye","Tuzlu Fıstık Ezmesi","Kids","Vitamini","Keçiboynu"],
        "unit": "kg",
    },
    "Rice": {
        "kw":  ["Pirinç"],
        "ex":  ["Kırık","Basmati","Un","Çorba","Pilav Yemeğe"],
        "unit": "kg",
    },
    "Bulgur": {
        "kw":  ["Bulgur"],
        "ex":  ["Un"],
        "unit": "kg",
    },
    "Pasta": {
        "kw":  ["Makarna"],
        "ex":  ["Knorr","Tortellini","Lazanya","Glutensiz","Organik"],
        "unit": "kg",
    },
    "Olive Oil": {
        "kw":  ["Zeytinyağı","Zeytinyağ"],
        "ex":  ["Sabun","Şampuan","Sprey","Sirke","Zeytin "],
        "unit": "ml_or_L",
    },
    "Olives": {
        "kw":  ["Zeytin"],
        "ex":  ["Yağ","Ezmesi","Sabun","Şampuan","Zeytinyağ"],
        "unit": "kg",
    },
    "Tea": {
        "kw":  ["Çay"],
        "ex":  ["Bitki","Meyve","Ihlamur","Papatya","'lü","'li",
                "Rahatlama","Kış","Poşet","Aromalı"],
        "unit": "kg",
        "require_weight": True,
    },
    "Tomato Paste": {
        "kw":  ["Domates Salçası","Domates Salça"],
        "ex":  ["Biber"],
        "unit": "kg",
    },
    "Jam": {
        "kw":  ["Reçel"],
        "ex":  ["Diabetik","Ceviz Reçeli","Biber Reçeli","Havuç Reçeli"],
        "unit": "kg",
    },
    "Honey": {
        "kw":  ["Bal"],
        "ex":  ["Pekmez","Sucuk","Yarma","Un","Mercimek","Mısır","Nohut",
                "Balsamik","Kitir","Çorbalık","Koop . Yarma"],
        "unit": "kg",
    },
    "Molasses": {
        "kw":  ["Pekmez"],
        "ex":  ["Sucuk","Tahin"],
        "unit": "kg",
    },
    "Salt": {
        "kw":  ["Tuz"],
        "ex":  ["Tuzlu","Fıstık","Kurabiye","Ekmek","Zeytin","Bisküvi",
                "Bulaşık","Salamura"],
        "unit": "kg",
    },
    "Average Spices": {
        "kw":  ["Baharat","Karabiber","Pul Biber"],
        "ex":  ["Kurabiye","Bisküvi","Kraker","Cipsi","Tuzlu","Cips",
                "Çerez","Patlak","Popcorn","Mısır","Kedi","Köpek"],
        "unit": "kg",
        "require_weight": True,
        "max_price_per_kg": 2500,
    },
    "Linden / Herbal Tea": {
        "kw":  ["Ihlamur","Papatya","Rahatlama","Kış Çayı","Bitki Çay"],
        "ex":  ["Meyve"],
        "unit": "piece",
    },
}

# ─────────────────────────────────────────────────────
# 4.  UTILITIES
# ─────────────────────────────────────────────────────

def parse_price(s: str) -> float:
    # Format: "1.234,00 TL"
    s = str(s).replace("TL","").replace(".","").replace(",",".").strip()
    try:    return float(s)
    except: return float("nan")

def extract_weight_g(name: str):
    # Baskent uses "GR" instead of standard "G"
    m = re.search(r"(\d+[,.]?\d*)\s*(KG|GR|G)\b", name.upper())
    if m:
        v = float(m.group(1).replace(",","."))
        return v * 1000 if m.group(2) == "KG" else v
    return None

def extract_volume_ml(name: str):
    n = re.sub(r"\blt\b", "L", name, flags=re.IGNORECASE).upper()
    mp = re.search(r"(\d+)\s*[xX]\s*(\d+[,.]?\d*)\s*(ML|L)\b", n)
    if mp:
        count = int(mp.group(1)); each = float(mp.group(2).replace(",","."))
        return count * each * (1000 if mp.group(3) == "L" else 1)
    m = re.search(r"(\d+[,.]?\d*)\s*(ML|L)\b", n)
    if m:
        v = float(m.group(1).replace(",","."))
        return v * 1000 if m.group(2) == "L" else v
    return None

def extract_piece_count(name: str):
    m = re.search(r"(\d+)['\u2019]?\s*(LU|Lİ|LI|li|lu)\b", name, re.IGNORECASE)
    return int(m.group(1)) if m else None

def shorten(name: str, max_len: int = 45) -> str:
    return name if len(name) <= max_len else name[:max_len-1] + "…"

# ─────────────────────────────────────────────────────
# 5.  COMPUTE UNIT PRICE FOR ONE BASKET ITEM
# ─────────────────────────────────────────────────────

def get_unit_price(df: pd.DataFrame, product_label: str) -> dict:
    rule = MATCH_RULES[product_label]

    if not rule["kw"]:
        return {"product_label": product_label, "unit": rule["unit"],
                "unit_price": float("nan"), "n_products": 0, "matched_names": "N/A"}

    sub  = df.copy()
    kw_m = sub["Product Name"].apply(
        lambda x: any(k.lower() in str(x).lower() for k in rule["kw"])
    )
    sub  = sub[kw_m]
    for exc in rule["ex"]:
        sub = sub[~sub["Product Name"].str.contains(exc, case=False, na=False)]

    if sub.empty:
        return {"product_label": product_label, "unit": rule["unit"],
                "unit_price": float("nan"), "n_products": 0, "matched_names": "—"}

    sub  = sub.copy()
    sub["price"] = sub["Price"].apply(parse_price)
    sub  = sub.dropna(subset=["price"])

    unit            = rule["unit"]
    req_weight      = rule.get("require_weight", False)
    min_price_per_u = rule.get("min_price_per_kg", 0)
    prices = []

    for _, row in sub.iterrows():
        name  = str(row["Product Name"])
        price = row["price"]

        if unit == "kg":
            w = extract_weight_g(name)
            if req_weight and not w:
                continue
            per_u = price / (w / 1000) if w and w > 0 else price
            if per_u < min_price_per_u:
                continue
            prices.append(per_u)

        elif unit == "ml_or_L":
            v = extract_volume_ml(name) or extract_weight_g(name)
            prices.append(price / (v / 1000) if v and v > 0 else price)

        elif unit == "piece":
            cnt = extract_piece_count(name)
            if cnt and cnt > 0:
                prices.append(price / cnt)
            elif product_label == "Linden / Herbal Tea":
                cnt2 = extract_piece_count(name) or 20
                prices.append((price / cnt2) / 0.002)
            else:
                prices.append(price)

    avg   = sum(prices) / len(prices) if prices else float("nan")
    names = "; ".join(shorten(n) for n in sub["Product Name"].tolist())
    return {"product_label": product_label, "unit": unit,
            "unit_price": round(avg, 2), "n_products": len(prices),
            "matched_names": names}

# ─────────────────────────────────────────────────────
# 6.  COMPUTE ONE MONTH
# ─────────────────────────────────────────────────────

def compute_hunger_threshold(csv_path: str, date_label: str) -> pd.DataFrame:
    df   = pd.read_csv(csv_path)
    rows = []

    for category, product_label, unit_label, monthly_qty in FOOD_BASKET:
        # Seasonal Fruit: not available at Baskent
        if product_label == "Seasonal Fruit":
            info = {"product_label": "Seasonal Fruit", "unit": "kg",
                    "unit_price": float("nan"), "n_products": 0, "matched_names": "N/A"}
        else:
            info = get_unit_price(df, product_label)

        unit_price   = info["unit_price"]
        monthly_cost = unit_price * monthly_qty

        rows.append({
            "date":               date_label,
            "category":           category,
            "product":            product_label,
            "unit":               unit_label,
            "monthly_qty":        monthly_qty,
            "avg_unit_price_TRY": unit_price,
            "monthly_cost_TRY":   round(monthly_cost, 2),
            "n_matched":          info["n_products"],
            "matched_products":   info["matched_names"],
        })

    result = pd.DataFrame(rows)
    result["monthly_cost_TRY"] = pd.to_numeric(result["monthly_cost_TRY"], errors="coerce")
    return result

# ─────────────────────────────────────────────────────
# 7.  MAIN
# ─────────────────────────────────────────────────────

all_results  = []
summary_rows = []

for date_label, path in FILES.items():
    df_month = compute_hunger_threshold(path, date_label)
    all_results.append(df_month)

    total    = df_month["monthly_cost_TRY"].sum()
    n_na     = df_month["avg_unit_price_TRY"].isna().sum()
    summary_rows.append({
        "date":               date_label,
        "hunger_threshold_TRY": round(total, 2),
        "n_na_items":         int(n_na),
    })

    print(f"\n{'='*100}")
    print(f"  {date_label}  —  Partial Threshold (available items only): ₺{total:,.2f}  "
          f"  [{n_na} items N/A]")
    print(f"{'='*100}")
    print(f"  {'Category':<22} {'Product':<30} {'Qty':>6} {'Unit Price':>12} {'Monthly Cost':>14}  "
          f"{'N':>4}  Matched Products")
    print(f"  {'-'*22} {'-'*30} {'-'*6} {'-'*12} {'-'*14}  {'-'*4}  {'-'*40}")
    for _, r in df_month.iterrows():
        names_preview = str(r["matched_products"])
        names_preview = names_preview[:60]+"…" if len(names_preview) > 60 else names_preview
        price_str = f"₺{r['avg_unit_price_TRY']:>9,.2f}" if pd.notna(r['avg_unit_price_TRY']) else "       N/A"
        cost_str  = f"₺{r['monthly_cost_TRY']:>11,.2f}" if pd.notna(r['monthly_cost_TRY']) else "         N/A"
        print(f"  {r['category']:<22} {r['product']:<30} {r['monthly_qty']:>6.1f} "
              f"  {price_str}   {cost_str}  "
              f"{r['n_matched']:>4}  {names_preview}")

all_df     = pd.concat(all_results, ignore_index=True)
summary_df = pd.DataFrame(summary_rows)

print("\n\n" + "="*65)
print("  MONTHLY HUNGER THRESHOLD SUMMARY  (partial — N/A items excluded)")
print("="*65)
print(f"  {'Date':<14} {'Partial Threshold':>18}  {'N/A Items':>10}  {'MoM Change':>12}")
print(f"  {'-'*14} {'-'*18}  {'-'*10}  {'-'*12}")
prev = None
for _, r in summary_df.iterrows():
    mom = f"{(r['hunger_threshold_TRY']-prev)/prev*100:+.1f}%" if prev else "—"
    print(f"  {r['date']:<14} ₺{r['hunger_threshold_TRY']:>16,.2f}  "
          f"{r['n_na_items']:>10}  {mom:>12}")
    prev = r["hunger_threshold_TRY"]

all_df.to_csv(OUTPUT_DETAIL,  index=False)
summary_df.to_csv(OUTPUT_SUMMARY, index=False)
print(f"\nDetail  → {OUTPUT_DETAIL}")
print(f"Summary → {OUTPUT_SUMMARY}")
