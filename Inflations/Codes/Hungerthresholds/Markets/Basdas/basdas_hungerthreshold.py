"""
Note: Basdas has limited SKU range. Many basket items are not stocked
(mince, bread, chickpeas, beans, olive oil, honey, semolina etc.) → NaN for those.
"""

import pandas as pd
import re
from pathlib import Path

# ─────────────────────────────────────────────────────
# 1.  PATHS  ←  edit BASE_DIR to your folder
# ─────────────────────────────────────────────────────
BASE_DIR = "/Users/efeyildirim/Downloads/Marketler/Basdas"

FILES = {
    "Feb-21 2026": f"{BASE_DIR}/basdas_2026-02-21.csv",
    "Feb-28 2026": f"{BASE_DIR}/basdas_2026-02-28.csv",
    "Mar 2026":    f"{BASE_DIR}/basdas_2026-03-31.csv",
    "Apr 2026":    f"{BASE_DIR}/basdas_2026-04-29.csv",
    "May 2026":    f"{BASE_DIR}/basdas_2026-05-24.csv",
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
# Basdas has NO category column — matching is purely keyword-based.
# Items not stocked: kw=[] → NaN.
#
# ITEM NOTES
# ----------
# Milk          "Süt" (milk) keyword — must exclude confectionery/non-dairy items.
# Chicken       "Piliç"/"Tavuk" (chicken) keywords — exclude pet food.
# Fish          Not stocked → NaN.
# Minced Meat   Not stocked → NaN.
# Bread         Not stocked → NaN.
# Semolina      Not stocked → NaN.
# Honey         Standalone "Bal" not found, only in compound names → NaN.
# Olive Oil     Only shampoo/soap results → NaN.
# Chickpeas     Not stocked → NaN.
# Dried Beans   Only fresh green beans → NaN.
# Tea           Loose-leaf only (require_weight); sachet packs excluded.
# Greens        Sold per piece/demet; 4 kg → 16 pieces at 250 g each.
# Seasonal Fruit Average of non-staple fruits available each month.

MATCH_RULES = {
    "Milk": {
        "kw":  ["Süt"],
        "ex":  ["Çocuk","Kakao","Çikolatalı","Çilekli","Aromalı","Ayran","Krema","Malt",
                "Yoğurt","Peynir","Kaymak","Kefir","Salep","Labne","Tereyağ",
                "Sütlü","Puding","Şampuan","Sabun","Bisküvi","Kedi","Köpek",
                "Bebek","Devam","Muzlu","Latte","Kaf","Büyümix","Sütlaç",
                "Dilimi","Lor","Krispi"],
        "unit": "ml_or_L",
        "max_price_per_kg": 120,
    },
    "Yogurt": {
        "kw":  ["Yoğurt"],
        "ex":  ["Meyveli","Organik","Kaymaklı","Süzme","Çırpılmış","Probiyotik",
                "Laktozsuz","Çilek","Aromalı","Quark","Cipsi","Kedi","Köpek","Puding"],
        "unit": "kg",
    },
    "White Cheese": {
        "kw":  ["Beyaz Peynir","Klasik Peynir","Taze Peynir"],
        "ex":  ["Kaşar","Lor","Dil","Örgü","Çeçil","Misto","Laktozsuz",
                "Tulum","Krem","Mozzarella","Hellim","Bisküvi"],
        "unit": "kg",
    },
    "Kashar / Other Cheese": {
        "kw":  ["Kaşar"],
        "ex":  ["Bisküvi","Cipsi"],
        "unit": "kg",
    },
    "Minced Meat": {
        "kw":  ["Kıyma","Kıymalık"],
        "ex":  ["Köfte","Döner","Burger","Sosis","Kaşarlı","Soslu","Kedi","Köpek"],
        "unit": "kg",
    },
    "Cubed Meat / Lamb Meat": {
        "kw":  ["Kuşbaşı","Dana Kuşbaşı","Kuzu Kuşbaşı"],
        "ex":  ["Kedi","Köpek","Köfte"],
        "unit": "kg",
    },
    "Chicken": {
        "kw":  ["Piliç","Bütün Tavuk","Tavuk But","Tavuk Göğüs","Tavuk Kanat",
                "Tavuk Baget","Tavuk Bonfile"],
        "ex":  ["Kedi","Köpek","Maması","Döner","Nugget","Köfte","Kroket",
                "Çıtır","Kebap","Soslu","Sarma","Yumurta"],
        "unit": "kg",
    },
    "Fish": {
        "kw":  [],   # not stocked
        "ex":  [],
        "unit": "kg",
    },
    "Eggs": {
        "kw":  ["Yumurta"],
        "ex":  ["Kedi","Köpek","Maması","Ülker","Bisküvi","Mini"],
        "unit": "piece",
    },
    "Dried Beans": {
        "kw":  ["Kuru Fasulye"],
        "ex":  ["Konserve","Haşlanmış","Turşu"],
        "unit": "kg",
    },
    "Chickpeas": {
        "kw":  ["Nohut"],
        "ex":  ["Konserve","Haşlanmış","Pilav"],
        "unit": "kg",
    },
    "Red Lentils": {
        "kw":  ["Kırmızı Mercimek"],
        "ex":  ["Çorba"],
        "unit": "kg",
    },
    "Green Lentils": {
        "kw":  ["Yeşil Mercimek"],
        "ex":  [],
        "unit": "kg",
    },
    "Walnut / Hazelnut / Peanut": {
        "kw":  ["Ceviz İç","Fındık İç","Yer Fıstığı"],
        "ex":  ["Ezmesi","Kreması","Çikolata","Cips","Soslu","Aromalı",
                "Kedi","Köpek","Bisküvi","Kurabiye","Gofret","Bar","Turp"],
        "unit": "kg",
    },
    "Bread": {
        "kw":  [],   # not stocked
        "ex":  [],
        "unit": "kg",
    },
    "Rice": {
        "kw":  ["Pirinç"],
        "ex":  ["Kırık","Basmati","Köpek","Kedi","Pilav Yemeğe"],
        "unit": "kg",
    },
    "Bulgur": {
        "kw":  ["Bulgur"],
        "ex":  [],
        "unit": "kg",
    },
    "Pasta": {
        "kw":  ["Makarna"],
        "ex":  ["Knorr","Tortellini","Lazanya","Mac Cheese"],
        "unit": "kg",
    },
    "Flour": {
        "kw":  ["Tellioğlu Un","Söke Un","Hekimoğlu Un","Sinangil Un",
                "Misun Un","Filiz Un","Un 1 Kg","Un 2 Kg","Un 5 Kg","Un 10 Kg"],
        "ex":  ["Mısır","Galeta","Glutensiz","Nişasta","Karma","Buğday"],
        "unit": "kg",
        "max_price_per_kg": 100,
    },
    "Semolina": {
        "kw":  [],   # not stocked
        "ex":  [],
        "unit": "kg",
    },
    "Apple": {
        "kw":  ["Elma"],
        "ex":  ["Suyu","Saç","Boyası","Renkler","Aromalı","Bisküvi"],
        "unit": "kg",
    },
    "Orange / Mandarin": {
        "kw":  ["Portakal","Mandalina"],
        "ex":  ["Suyu","Gazoz","Aromalı","Fanta"],
        "unit": "kg",
    },
    "Banana": {
        "kw":  ["Muz"],
        "ex":  ["Muzlu","Kurusu","Bebek","Aromalı","Püresi","Kefir",
                "Sütlü","Dondurma","Süt","Çikolata","Kek","Bisküvi",
                "Hero","Baby","Mama","Gerber","Hipp","Bebek Maması"],
        "unit": "kg",
        "max_price_per_kg": 250,
    },
    "Potato": {
        "kw":  ["Patates"],
        "ex":  ["Cipsi","Cips","Kroket","Püresi","Börek","Hazır","Superfresh",
                "Süperfresh","Dondurulmuş","Tatlı","Parmak","Kedi","Köpek",
                "Maması","Friskies","Whiskas"],
        "unit": "kg",
    },
    "Onion": {
        "kw":  ["Soğan"],
        "ex":  ["Kızartılmış","Taze","Arpacık","Tozu","Sarımsak","Çizi","Ülker","Kraker","Bisküvi",
                "Çipso","Cips","Kraker","Popzz","Nutzz","Kaplamalı",
                "Halka","Turşu"],
        "unit": "kg",
    },
    "Tomato": {
        "kw":  ["Domates"],
        "ex":  ["Salça","Kurutulmuş","Konserve","Rende","Kedi","Köpek","Maması",
                "Knorr","Çabuk","Bardak","Hazır Yemek"],
        "unit": "kg",
    },
    "Cucumber": {
        "kw":  ["Salatalık"],
        "ex":  ["Turşu"],
        "unit": "kg",
    },
    "Pepper": {
        "kw":  ["Biber"],
        "ex":  ["Pul","Toz","Turşu","Konserve","Közlenmiş","Cipsi","Eti Crax","Hanımeller","Çizi","Kraker","Bisküvi","Kek","Gofret"],
        "unit": "kg",
    },
    "Eggplant / Zucchini": {
        "kw":  ["Patlıcan","Kabak"],
        "ex":  ["Közlenmiş","Konserve","Turşu","Kedi","Köpek"],
        "unit": "kg",
    },
    "Carrot": {
        "kw":  ["Havuç"],
        "ex":  ["Kedi","Köpek","Maması"],
        "unit": "kg",
    },
    "Greens / Lettuce / Parsley": {
        "kw":  ["Marul","Maydanoz","Roka","Dereotu","Kıvırcık","Semizotu"],
        "ex":  ["Bisküvi","Kraker","Ballı","Bademli","Çikolata","Ülker",
                "Kedi","Köpek","Paket"],
        "unit": "piece",
    },
    "Other Vegetables": {
        "kw":  ["Mantar","Lahana","Ispanak","Brokoli","Enginar"],
        "ex":  ["Konserve","Turşu","Kedi","Köpek","Knorr","Çabuk","Hazır Çorba"],
        "unit": "kg",
    },
    "Sunflower Oil": {
        "kw":  ["Ayçiçek Yağı"],
        "ex":  ["Teneke","Şampuan","Sabun"],
        "unit": "ml_or_L",
    },
    "Olive Oil": {
        "kw":  [],   # only soap/shampoo results → not stocked as food
        "ex":  [],
        "unit": "ml_or_L",
    },
    "Butter": {
        "kw":  ["Tereyağ","Tereyağı"],
        "ex":  ["Margarin","Bitkisel","Şampuan","Sabun"],
        "unit": "kg",
    },
    "Margarine": {
        "kw":  ["Margarin"],
        "ex":  ["Şişe"],
        "unit": "kg",
    },
    "Olives": {
        "kw":  ["Zeytin"],
        "ex":  ["Yağ","Ezmesi","Sabun","Şampuan","Zeytinyağlı"],
        "unit": "kg",
    },
    "Sugar": {
        "kw":  ["Toz Şeker"],
        "ex":  ["Küp","Esmer","Vanilin","Kahve","Şekersiz"],
        "unit": "kg",
    },
    "Tea": {
        "kw":  ["Çay"],
        "ex":  ["Bitki","Soğuk","Meyve","Ihlamur","Papatya","Poşet","Demlik",
                "'lü","'li","Aromalı","Bardağı","Seti","Tabağı","Çaycı",
                "x1,","x2,","Gazoz","Form","Fit","Yeşil","Bergamot","Earl Grey"],
        "unit": "kg",
        "require_weight": True,
        "max_price_per_kg": 600,
    },
    "Tomato Paste": {
        "kw":  ["Salça","Domates Salçası"],
        "ex":  ["Turşu","Rende","Konserve"],
        "unit": "kg",
    },
    "Jam": {
        "kw":  ["Reçel"],
        "ex":  ["Süt Reçeli","Diabetik"],
        "unit": "kg",
    },
    "Honey": {
        "kw":  [],   # only pumpkin (Bal Kabağı), pet food, hair dye → not stocked
        "ex":  [],
        "unit": "kg",
    },
    "Molasses": {
        "kw":  ["Pekmez"],
        "ex":  ["Tahin","Fındık"],
        "unit": "kg",
    },
    "Salt": {
        "kw":  ["Tuz"],
        "ex":  ["Baharat","Biber","Salamura","Karabiber","Pul","Limon Tuzu",
                "Himalaya","Tuzluklu","Kaya Tuzu","Deniz Tuzu","Öğütme",
                "Peynir","Az Tuzlu","Tuzlu Kraker","Tuzlu Bisküvi",
                "Kedi","Köpek","Bulaşık","Turşu"],
        "unit": "kg",
        "require_weight": True,
        "max_price_per_kg": 150,
    },
    "Average Spices": {
        "kw":  ["Karabiber","Pul Biber"],
        "ex":  ["Tane","Tuzluklu","Harç","Cajun","Mangal","Izgara",
                "Kraker","Cips","Çizi","Popcorn","Patlak","Mısır"],
        "unit": "kg",
        "require_weight": True,
        "max_price_per_kg": 2500,
    },
    "Linden / Herbal Tea": {
        "kw":  ["Ihlamur","Papatya Çay"],
        "ex":  ["Havlu","Sabun","Mendil","Rezene","Form","Adaçayı","Zencefil",
                "Kış","Nane","Kuşburnu"],
        "unit": "piece",
        "require_weight": True,
    },
}

# Seasonal fruit: exclude staples + non-food items
SEASONAL_EXCLUDE = ["Elma","Portakal","Mandalina","Muz","Limon","Avokado",
                    "Adet","Suyu","Gazoz","Aromalı","Saç","Boyası","Kedi","Su","Jel","Kayganlaştırıcı","Kolonya","Şampuan","Deterjan","Losyon","Sabun",
                    "Köpek","Maması","Bisküvi","Patates","Soğan","Domates",
                    "Salatalık","Biber","Patlıcan","Kabak","Havuç","Marul",
                    "Lahana","Ispanak","Mantar","Enginar","Kabağı",
                    "Kekstra","Kanky","Dankek","Dido","Hoşbeş","Cornetto",
                    "Puding","Reçeli","Reçel","Çikolata","Yoğurtlu","Milka",
                    "Sütlü","Süt ","Kefir","Sosis","Salam","Peynir","Mayonez",
                    "Sensodyne","Parodontax","Eyüp Sabri","Parex","Paket ",
                    "Algida","Hero Baby","Dondurma","Büyümix","Büzgülü",
                    "Çöp","Torba","Diş","Fırça","Macun","Ağız","Temizlik",
                    "Saç","Parfüm","Deodorant","Krem","Losyon",
                    "Lipton Form","Çay ","Çayı","Kayısılı Çay","Form Plus",
                    "Pınar Sı","Pınar Su","Su ","Eti Gong","Yoğurt "]

FRUIT_KEYWORDS = ["Kg","Adet"]
FRUIT_NAMES    = ["Üzüm","Armut","Kiraz","Erik","Şeftali","Kayısı","İncir",
                  "Kivi","Çilek","Karpuz","Kavun","Nar"]

# ─────────────────────────────────────────────────────
# 4.  UTILITIES
# ─────────────────────────────────────────────────────

def extract_weight_g(name: str):
    m = re.search(r"(\d+[,.]?\d*)\s*(KG|G)\b", name.upper())
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

def shorten(name: str, max_len: int = 38) -> str:
    return name if len(name) <= max_len else name[:max_len-1] + "…"

# ─────────────────────────────────────────────────────
# 5.  COMPUTE UNIT PRICE FOR ONE BASKET ITEM
# ─────────────────────────────────────────────────────

def get_unit_price(df: pd.DataFrame, product_label: str) -> dict:
    rule = MATCH_RULES[product_label]

    if not rule["kw"]:   # not stocked
        return {"product_label": product_label, "unit": rule["unit"],
                "unit_price": float("nan"), "n_products": 0, "matched_names": "N/A"}

    sub  = df.copy()
    kw_m = sub["isim"].apply(lambda x: any(k.lower() in str(x).lower() for k in rule["kw"]))
    sub  = sub[kw_m]
    for exc in rule["ex"]:
        sub = sub[~sub["isim"].str.contains(exc, case=False, na=False)]

    if sub.empty:
        return {"product_label": product_label, "unit": rule["unit"],
                "unit_price": float("nan"), "n_products": 0, "matched_names": "—"}

    sub  = sub.copy()
    unit            = rule["unit"]
    req_weight      = rule.get("require_weight", False)
    min_price_per_u = rule.get("min_price_per_kg", 0)
    prices = []

    for _, row in sub.iterrows():
        name  = str(row["isim"])
        price = float(row["fiyat"])

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
    names = "; ".join(shorten(n) for n in sub["isim"].tolist())
    return {"product_label": product_label, "unit": unit,
            "unit_price": round(avg, 2), "n_products": len(prices),
            "matched_names": names}

def get_seasonal_fruit_price(df: pd.DataFrame) -> dict:
    # Match any fruit keyword
    sub = df[df["isim"].apply(
        lambda x: any(f.lower() in str(x).lower() for f in FRUIT_NAMES)
    )].copy()
    for exc in SEASONAL_EXCLUDE:
        sub = sub[~sub["isim"].str.contains(exc, case=False, na=False)]
    prices = []
    for _, row in sub.iterrows():
        w = extract_weight_g(str(row["isim"]))
        prices.append(row["fiyat"] / (w / 1000) if w and w > 0 else row["fiyat"])
    avg   = sum(prices) / len(prices) if prices else float("nan")
    names = "; ".join(shorten(n) for n in sub["isim"].tolist())
    return {"product_label": "Seasonal Fruit", "unit": "kg",
            "unit_price": round(avg, 2), "n_products": len(prices),
            "matched_names": names}

# ─────────────────────────────────────────────────────
# 6.  COMPUTE ONE MONTH
# ─────────────────────────────────────────────────────

def compute_hunger_threshold(csv_path: str, date_label: str) -> pd.DataFrame:
    df   = pd.read_csv(csv_path, sep=";")
    rows = []

    for category, product_label, unit_label, monthly_qty in FOOD_BASKET:
        if product_label == "Seasonal Fruit":
            info = get_seasonal_fruit_price(df)
        else:
            info = get_unit_price(df, product_label)

        unit_price = info["unit_price"]

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
        names_preview = str(r["matched_products"])
        names_preview = names_preview[:60] + "…" if len(names_preview) > 60 else names_preview
        price_str = f"₺{r['avg_unit_price_TRY']:>9,.2f}" if pd.notna(r['avg_unit_price_TRY']) else "       N/A"
        cost_str  = f"₺{r['monthly_cost_TRY']:>11,.2f}" if pd.notna(r['monthly_cost_TRY']) else "         N/A"
        print(f"  {r['category']:<22} {r['product']:<30} {r['monthly_qty']:>6.1f} "
              f"  {price_str}   {cost_str}  "
              f"{r['n_matched']:>4}  {names_preview}")

all_df     = pd.concat(all_results, ignore_index=True)
summary_df = pd.DataFrame(summary_rows)

print("\n\n" + "="*55)
print("  MONTHLY HUNGER THRESHOLD SUMMARY")
print("="*55)
print(f"  {'Date':<14} {'Threshold (₺)':>16}  {'MoM Change':>12}")
print(f"  {'-'*14} {'-'*16}  {'-'*12}")
prev = None
for _, r in summary_df.iterrows():
    mom = f"{(r['hunger_threshold_TRY']-prev)/prev*100:+.1f}%" if prev else "—"
    print(f"  {r['date']:<14} ₺{r['hunger_threshold_TRY']:>14,.2f}  {mom:>12}")
    prev = r["hunger_threshold_TRY"]

all_df.to_csv(OUTPUT_DETAIL,  index=False)
summary_df.to_csv(OUTPUT_SUMMARY, index=False)
print(f"\nDetail  → {OUTPUT_DETAIL}")
print(f"Summary → {OUTPUT_SUMMARY}")
