"""
Hunger Threshold Calculator — v2
================================================
Data source : A101 Kapida online grocery prices
Basket      : Presentation slide 8 (family of 4, monthly quantities)

MATCHING STRATEGY
-----------------
Each basket item is matched against the CSV using:
  • alt_kategori  – A101 sub-category column
  • keywords      – Turkish words that must appear in the product name (any match)
  • exclude       – words that disqualify a product

Every matched product's price is normalised to TRY/kg (or TRY/litre, TRY/piece)
by parsing the package size from the product name. The basket cost uses the
simple average of all matched unit prices — outliers are intentionally kept
because they reflect the real market spread a household faces.

ITEM NOTES
----------
Yogurt          Only plain homogenised/bucket/tub yogurt; excluded: creamy,
                strained, whisked, probiotic, lactose-free, flavoured, premium brands
Minced Meat     Fresh beef mince preferred; Feb-2026 CSV has no fresh mince so beef
                meatball variants used as proxy (filtered to beef-only, no chicken/burger)
Tea             "30x15 G" style multi-sachet pack excluded to avoid /kg normalisation bug
Greens          Sold per piece (Adet); 4 kg/month → 16 pieces (250 g/piece assumed)
Seasonal Fruit  Average of all non-staple fruits available that month
"""

import pandas as pd
import re

# ─────────────────────────────────────────────────────
# 1.  PATHS  ←  edit BASE_DIR to your folder
# ─────────────────────────────────────────────────────
BASE_DIR = "/Users/efeyildirim/Downloads/Marketler/A101"

FILES = {
    "Feb 2026": f"{BASE_DIR}/a101_kapida_2026-02-28.csv",
    "Mar 2026": f"{BASE_DIR}/a101_kapida_2026-03-31.csv",
    "Apr 2026": f"{BASE_DIR}/a101_kapida_2026-04-30.csv",
    "May 2026": f"{BASE_DIR}/a101_kapida_2026-05-18.csv",
}

OUTPUT_DETAIL  = f"{BASE_DIR}/hunger_threshold_detail.csv"
OUTPUT_SUMMARY = f"{BASE_DIR}/hunger_threshold_summary.csv"

# ─────────────────────────────────────────────────────
# 2.  FOOD BASKET  (slide 8)
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
MATCH_RULES = {
    # ── Dairy ────────────────────────────────────────────────────────
    "Milk": {
        "alt_kategori": ["Süt"],
        "keywords": ["Süt"],
        "exclude": ["Çocuk","Laktozsuz","Kavun","Meyve","Çikolata","Latte","Salep",
                    "Proteinli","Karamel","Macchiato","Kakaolu","Çilekli","Milkino",
                    "Danone","Aromalı","ml","Badem Sütü","Yulaf Sütü","Bakım Sütü","Elidor","Losyon","Tereyağ","Krem","Alpro","Vegan"],
        "unit": "ml_or_L",
    },
    "Yogurt": {
        "alt_kategori": ["Yoğurt"],
        "keywords": ["Yoğurt"],
        # Only plain homojenize / bidon / kova yogurt — no premium/specialty forms
        "exclude": ["Meyveli","Organik","Kaymaklı","Kaymaksız","Süzme","Çırpılmış",
                    "Probiyotik","Laktozsuz","Hurmalı","Disney","Danone","Activia",
                    "Hüptrik","Çilek","Aromalı","Parçalı","Çıtırdat","Çölek",
                    "Gurme","Efsane","Quark","Tava"],
        "unit": "kg",
    },
    "White Cheese": {
        "alt_kategori": ["Beyaz Peynir"],
        "keywords": ["Peynir"],
        "exclude": ["Misto","Laktozsuz","Sürülebilir"],
        "unit": "kg",
    },
    "Kashar / Other Cheese": {
        "alt_kategori": ["Kaşar Peyniri"],
        "keywords": ["Kaşar","Tost Peyniri"],
        "exclude": [],
        "unit": "kg",
    },
    # ── Meat & Protein ───────────────────────────────────────────────
    "Minced Meat": {
        "alt_kategori": ["Kırmızı Et"],
        # Only fresh/frozen raw minced meat — no ready-made meatballs
        "keywords": ["Kıyma"],
        "exclude": ["Piliç","Sosis","Füme","Kavurma","Roast","Kokoreç",
                    "Köfte","Burger","Kaşarlı","Soslu","Sulu"],
        "unit": "kg",
    },
    "Cubed Meat / Lamb Meat": {
        "alt_kategori": ["Kırmızı Et"],
        "keywords": ["Kuşbaşı"],
        "exclude": ["Döner","Köfte","Kedi","Köpek","Kıyma","Hazır","Kavurma","Pastırma","Sucuk","Sosis"],
        "unit": "kg",
    },
    "Chicken": {
        "alt_kategori": ["Beyaz Et"],
        "keywords": ["Tavuk","Piliç"],
        "exclude": ["Döner","Nugget","Şinitzel","Sarma","Köfte","Kroket","Çıtır","Kebap","Lokma","Parmak Bonfile","Jumbo Fileto","Izgara Dilimli","Soslu Kanat"],
        "unit": "kg",
    },
    "Fish": {
        "alt_kategori": ["Deniz Ürünleri"],
        "keywords": ["Hamsi","Levrek","Somon","Balık"],
        "exclude": ["Füme","Konserve"],
        "unit": "kg",
    },
    "Eggs": {
        "alt_kategori": ["Yumurta"],
        "keywords": ["Yumurta"],
        "exclude": ["Organik","Bıldırcın"],
        "unit": "piece",
    },
    # ── Legumes ──────────────────────────────────────────────────────
    "Dried Beans": {
        "alt_kategori": ["Bakliyat"],
        "keywords": ["Fasulye"],
        "exclude": ["Yeşil","Barbunya","Maş","Konserve"],
        "unit": "kg",
    },
    "Chickpeas": {
        "alt_kategori": ["Bakliyat"],
        "keywords": ["Nohut"],
        "exclude": ["Konserve"],
        "unit": "kg",
    },
    "Red Lentils": {
        "alt_kategori": ["Bakliyat"],
        "keywords": ["Kırmızı Mercimek"],
        "exclude": [],
        "unit": "kg",
    },
    "Green Lentils": {
        "alt_kategori": ["Bakliyat"],
        "keywords": ["Yeşil Mercimek"],
        "exclude": [],
        "unit": "kg",
    },
    # ── Nuts ─────────────────────────────────────────────────────────
    "Walnut / Hazelnut / Peanut": {
        "alt_kategori": ["Kuruyemiş, Kuru Meyve"],
        "keywords": ["Fıstık","Fındık","Ceviz"],
        "exclude": ["Ezmesi","Kreması","Bitter","Çikolata","Cips","Pop Fıstık","Soslu","Aromalı","Susamlı"],
        "unit": "kg",
    },
    # ── Grains ───────────────────────────────────────────────────────
    "Bread": {
        "alt_kategori": ["Ekmek"],
        "keywords": ["Ekmek"],
        "exclude": ["Hamburger","Sandviç","Tost","Lavaş","Tortilla","Yufka","Wasa","Gevrek"],
        "require_min_price_per_kg": 50,
        "unit": "kg",
    },
    "Rice": {
        "alt_kategori": ["Bakliyat"],
        "keywords": ["Pirinç"],
        "exclude": ["Kırık","Basmati","Yasemin"],
        "unit": "kg",
    },
    "Bulgur": {
        "alt_kategori": ["Bakliyat"],
        "keywords": ["Bulgur"],
        "exclude": [],
        "unit": "kg",
    },
    "Pasta": {
        "alt_kategori": ["Makarna, Noodle"],
        "keywords": ["Makarna"],
        "exclude": ["Noodle","Erişte","Tortellini","Knorr","Lazanya","Granoro","Rummo"],
        "unit": "kg",
    },
    "Flour": {
        "alt_kategori": ["Un"],
        "keywords": ["Un"],
        "exclude": ["Mısır","Nişasta","Galeta","Glutensiz"],
        "unit": "kg",
    },
    "Semolina": {
        "alt_kategori": ["Hamur Pasta Malzemeleri"],
        "keywords": ["İrmik"],
        "exclude": [],
        "unit": "kg",
    },
    # ── Fruits ───────────────────────────────────────────────────────
    "Apple": {
        "alt_kategori": ["Meyve"],
        "keywords": ["Elma"],
        "exclude": [],
        "unit": "kg",
    },
    "Orange / Mandarin": {
        "alt_kategori": ["Meyve"],
        "keywords": ["Portakal","Mandalina"],
        "exclude": ["Suyu","File"],
        "unit": "kg",
    },
    "Banana": {
        "alt_kategori": ["Meyve"],
        "keywords": ["Muz"],
        "exclude": [],
        "unit": "kg",
    },
    # ── Vegetables ───────────────────────────────────────────────────
    "Potato": {
        "alt_kategori": ["Sebze"],
        "keywords": ["Patates"],
        "exclude": ["Kızartmalık","Cips","Dondurulmuş"],
        "unit": "kg",
    },
    "Onion": {
        "alt_kategori": ["Sebze"],
        "keywords": ["Soğan"],
        "exclude": ["Taze","Pırasa"],
        "unit": "kg",
    },
    "Tomato": {
        "alt_kategori": ["Sebze"],
        "keywords": ["Domates"],
        "exclude": ["Kokteyl","Salça","Kurutulmuş","Paket"],
        "unit": "kg",
    },
    "Cucumber": {
        "alt_kategori": ["Sebze"],
        "keywords": ["Salatalık"],
        "exclude": [],
        "unit": "kg",
    },
    "Pepper": {
        "alt_kategori": ["Sebze"],
        "keywords": ["Biber"],
        "exclude": ["Pul","Toz"],
        "unit": "kg",
    },
    "Eggplant / Zucchini": {
        "alt_kategori": ["Sebze"],
        "keywords": ["Patlıcan","Kabak"],
        "exclude": [],
        "unit": "kg",
    },
    "Carrot": {
        "alt_kategori": ["Yeşillik"],
        "keywords": ["Havuç"],
        "exclude": [],
        "unit": "kg",
    },
    "Greens / Lettuce / Parsley": {
        "alt_kategori": ["Yeşillik"],
        "keywords": ["Marul","Maydanoz","Roka","Dereotu","Kıvırcık"],
        "exclude": [],
        "unit": "piece",
    },
    "Other Vegetables": {
        "alt_kategori": ["Sebze"],
        "keywords": ["Mantar","Lahana","Ispanak","Brokoli","Enginar"],
        "exclude": [],
        "unit": "kg",
    },
    # ── Oils ─────────────────────────────────────────────────────────
    "Sunflower Oil": {
        "alt_kategori": ["Sıvı Yağlar"],
        "keywords": ["Ayçiçek"],
        "exclude": ["Teneke","18 L"],
        "unit": "ml_or_L",
    },
    "Olive Oil": {
        "alt_kategori": ["Sıvı Yağlar"],
        "keywords": ["Zeytinyağ","Zeytin Yağ"],
        "exclude": [],
        "unit": "ml_or_L",
    },
    "Butter": {
        "alt_kategori": ["Tereyağ, Margarin"],
        "keywords": ["Tereyağ"],
        "exclude": ["Margarin","Bitkisel"],
        "unit": "kg",
    },
    "Margarine": {
        "alt_kategori": ["Tereyağ, Margarin"],
        "keywords": ["Margarin"],
        "exclude": ["Şişe","Profesyonel"],
        "unit": "kg",
    },
    # ── Breakfast ────────────────────────────────────────────────────
    "Olives": {
        "alt_kategori": ["Zeytin"],
        "keywords": ["Zeytin"],
        "exclude": ["Yağ","Ezmesi"],
        "unit": "kg",
    },
    # ── Other Food ───────────────────────────────────────────────────
    "Sugar": {
        "alt_kategori": ["Şeker"],
        "keywords": ["Toz Şeker"],
        "exclude": ["Küp"],
        "unit": "kg",
    },
    "Tea": {
        "alt_kategori": ["Çay"],
        "keywords": ["Çay"],
        # Keep only loose-leaf tea sold by weight (KG or G in name).
        # Sachet packs (100-ct, 48-ct etc.) have no parseable weight → raw price
        # used as per-kg which is wildly wrong (₺30–₺240 instead of ₺750–₺1500).
        "exclude": ["Bitki","Soğuk","Meyve","x15","x20","x25","x30","x40","Poşet","'lü","'li"],
        "unit": "kg",
        "require_weight": True,
    },
    "Tomato Paste": {
        "alt_kategori": ["Salça"],
        "keywords": ["Domates Salça"],
        "exclude": [],
        "unit": "kg",
    },
    "Jam": {
        "alt_kategori": ["Bal, Reçel"],
        "keywords": ["Reçel"],
        "exclude": ["Süt Reçeli"],
        "unit": "kg",
    },
    "Honey": {
        "alt_kategori": ["Bal, Reçel"],
        "keywords": ["Bal"],
        "exclude": ["Reçel","Şeker","Küp","Propolis","x7"],
        "unit": "kg",
    },
    "Molasses": {
        "alt_kategori": ["Helva, Tahin, Pekmez"],
        "keywords": ["Pekmez"],
        "exclude": ["Tahin","Tüp","Pektamin","ml"],
        "unit": "kg",
    },
    "Salt": {
        "alt_kategori": ["Tuz, Baharat, Harç"],
        "keywords": ["Tuz"],
        "exclude": ["Baharat","Biber","Salamura","Karabiber","Pul","Limon Tuzu",
                    "Himalaya","Tuzluklu","Kaya Tuzu","Deniz Tuzu","Öğütme"],
        "unit": "kg",
        "require_weight": True,
        "max_price_per_kg": 150,
    },
    "Average Spices": {
        "alt_kategori": ["Tuz, Baharat, Harç"],
        "keywords": ["Baharat","Karabiber","Pul Biber"],
        "exclude": ["Çam Fıstık","Karanfil","Kuş Üzümü","Patates Çeşnisi","Hindistan Cevizi","Tarçın"],
        "unit": "kg",
    },
    "Linden / Herbal Tea": {
        "alt_kategori": ["Bitki Çayları"],
        "keywords": ["Ihlamur","Bitki Çay","Papatya"],
        "exclude": [],
        "unit": "piece",
    },
}

# ─────────────────────────────────────────────────────
# 4.  UTILITIES
# ─────────────────────────────────────────────────────
def parse_price(s: str) -> float:
    """Convert '₺1.234,56' → 1234.56"""
    s = str(s).replace("₺","").replace(".","").replace(",",".").strip()
    try:    return float(s)
    except: return float("nan")

def extract_weight_g(name: str):
    """Extract package weight in grams from product name."""
    m = re.search(r"(\d+[,.]?\d*)\s*(KG|G)\b", name.upper())
    if m:
        v = float(m.group(1).replace(",","."))
        return v * 1000 if m.group(2) == "KG" else v
    return None

def extract_volume_ml(name: str):
    """Extract package volume in ml from product name."""
    m = re.search(r"(\d+[,.]?\d*)\s*(ML|L)\b", name.upper())
    if m:
        v = float(m.group(1).replace(",","."))
        return v * 1000 if m.group(2) == "L" else v
    return None

def extract_piece_count(name: str):
    """Extract pack count from name like '30'lu', '20'li'."""
    m = re.search(r"(\d+)['\u2019]?\s*(LU|Lİ|LI|li|lu)\b", name, re.IGNORECASE)
    return int(m.group(1)) if m else None

def shorten(name: str, max_len: int = 38) -> str:
    """Trim product name for display."""
    return name if len(name) <= max_len else name[:max_len-1] + "…"

# ─────────────────────────────────────────────────────
# 5.  COMPUTE UNIT PRICE FOR ONE BASKET ITEM
# ─────────────────────────────────────────────────────
def get_unit_price(df: pd.DataFrame, product_label: str) -> dict:
    rule = MATCH_RULES[product_label]
    sub  = df[df["alt_kategori"].isin(rule["alt_kategori"])].copy()
    kw_m = sub["ad"].apply(
        lambda x: any(k.lower() in str(x).lower() for k in rule["keywords"])
    )
    sub  = sub[kw_m]
    for exc in rule["exclude"]:
        sub = sub[~sub["ad"].str.contains(exc, case=False, na=False)]

    if sub.empty:
        return {"product_label": product_label, "unit": rule["unit"],
                "unit_price": float("nan"), "n_products": 0, "matched_names": "—"}

    sub = sub.copy()
    sub["price"] = sub["fiyat"].apply(parse_price)
    sub = sub.dropna(subset=["price"])

    unit   = rule["unit"]
    require_weight     = rule.get("require_weight", False)
    min_price_per_unit = rule.get("require_min_price_per_kg", 0)
    prices = []

    for _, row in sub.iterrows():
        name  = str(row["ad"])
        price = row["price"]

        if unit == "kg":
            w = extract_weight_g(name)
            if require_weight and not w:
                continue   # skip sachet/pack products with no weight in name
            per_u = price / (w / 1000) if w and w > 0 else price
            if per_u < min_price_per_unit:
                continue   # skip suspiciously cheap outliers
            prices.append(per_u)
            continue

        elif unit == "ml_or_L":
            # Handle multipacks like "4x1 L" or "6x200 ml"
            mp = re.search(r"(\d+)\s*[xX]\s*(\d+[,.]?\d*)\s*(ML|L)", name.upper())
            if mp:
                count = int(mp.group(1))
                each  = float(mp.group(2).replace(",","."))
                v     = count * each * (1000 if mp.group(3)=="L" else 1)
            else:
                v = extract_volume_ml(name) or extract_weight_g(name)
            prices.append(price / (v / 1000) if v and v > 0 else price)

        elif unit == "piece":
            cnt = extract_piece_count(name)
            if cnt and cnt > 0:
                prices.append(price / cnt)
            elif product_label == "Linden / Herbal Tea":
                cnt2 = extract_piece_count(name) or 20
                prices.append((price / cnt2) / 0.002)   # per-kg equivalent
            else:
                prices.append(price)

    avg   = sum(prices) / len(prices) if prices else float("nan")
    names = "; ".join(shorten(n) for n in sub["ad"].tolist())

    return {
        "product_label": product_label,
        "unit":          unit,
        "unit_price":    round(avg, 2),
        "n_products":    len(prices),
        "matched_names": names,
    }

def get_seasonal_fruit_price(df: pd.DataFrame) -> dict:
    """Average price of all non-staple fruits available that month."""
    sub = df[df["alt_kategori"] == "Meyve"].copy()
    for exc in ["Elma","Portakal","Mandalina","Muz","Limon","Avokado","Adet","Suyu","File",
                   "Yaban Mersini","Paket","Kutu","Dondurulmuş","Püre","Konserve"]:
        sub = sub[~sub["ad"].str.contains(exc, case=False, na=False)]
    sub = sub.copy()
    sub["price"] = sub["fiyat"].apply(parse_price)
    sub = sub.dropna(subset=["price"])
    prices = []
    for _, row in sub.iterrows():
        w = extract_weight_g(str(row["ad"]))
        prices.append(row["price"] / (w / 1000) if w and w > 0 else row["price"])
    avg   = sum(prices) / len(prices) if prices else float("nan")
    names = "; ".join(shorten(n) for n in sub["ad"].tolist())
    return {"product_label": "Seasonal Fruit", "unit": "kg",
            "unit_price": round(avg, 2), "n_products": len(prices),
            "matched_names": names}

# ─────────────────────────────────────────────────────
# 6.  COMPUTE ONE MONTH
# ─────────────────────────────────────────────────────
def compute_hunger_threshold(csv_path: str, date_label: str) -> pd.DataFrame:
    df   = pd.read_csv(csv_path)
    rows = []

    for category, product_label, unit_label, monthly_qty in FOOD_BASKET:
        if product_label == "Seasonal Fruit":
            info = get_seasonal_fruit_price(df)
        else:
            info = get_unit_price(df, product_label)

        unit_price = info["unit_price"]

        # Greens sold per piece; convert 4 kg/month → pieces at 250 g/piece
        if product_label == "Greens / Lettuce / Parsley":
            monthly_cost = unit_price * (monthly_qty / 0.25)
        else:
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
    total = df_month["monthly_cost_TRY"].sum()
    summary_rows.append({"date": date_label, "hunger_threshold_TRY": round(total, 2)})

    print(f"\n{'='*100}")
    print(f"  {date_label}  —  Hunger Threshold: ₺{total:,.2f}")
    print(f"{'='*100}")
    print(f"  {'Category':<22} {'Product':<30} {'Qty':>6} {'Unit Price':>12} {'Monthly Cost':>14}  "
          f"{'N':>4}  Matched Products")
    print(f"  {'-'*22} {'-'*30} {'-'*6} {'-'*12} {'-'*14}  {'-'*4}  {'-'*40}")
    for _, r in df_month.iterrows():
        names_preview = r["matched_products"][:60] + "…" \
                        if len(str(r["matched_products"])) > 60 \
                        else r["matched_products"]
        print(f"  {r['category']:<22} {r['product']:<30} {r['monthly_qty']:>6.1f} "
              f"  ₺{r['avg_unit_price_TRY']:>9,.2f}   ₺{r['monthly_cost_TRY']:>11,.2f}  "
              f"{r['n_matched']:>4}  {names_preview}")

all_df     = pd.concat(all_results, ignore_index=True)
summary_df = pd.DataFrame(summary_rows)

print("\n\n" + "="*55)
print("  MONTHLY HUNGER THRESHOLD SUMMARY")
print("="*55)
print(f"  {'Date':<12} {'Threshold (₺)':>16}  {'MoM Change':>12}")
print(f"  {'-'*12} {'-'*16}  {'-'*12}")
prev = None
for _, r in summary_df.iterrows():
    mom = f"{(r['hunger_threshold_TRY']-prev)/prev*100:+.1f}%" if prev else "—"
    print(f"  {r['date']:<12} ₺{r['hunger_threshold_TRY']:>14,.2f}  {mom:>12}")
    prev = r["hunger_threshold_TRY"]

all_df.to_csv(OUTPUT_DETAIL,  index=False)
summary_df.to_csv(OUTPUT_SUMMARY, index=False)
print(f"\nDetail  → {OUTPUT_DETAIL}")
print(f"Summary → {OUTPUT_SUMMARY}")
