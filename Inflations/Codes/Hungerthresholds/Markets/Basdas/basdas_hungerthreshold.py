import pandas as pd
import re
from pathlib import Path

# ─────────────────────────────────────────────────────
# 1.  PATHS
# ─────────────────────────────────────────────────────
BASE_DIR = "/Users/efeyildirim/Downloads/Marketler/Basdas"

FILES = {
    "Feb 2026": f"{BASE_DIR}/basdas_2026-02-28.csv",
    "Mar 2026": f"{BASE_DIR}/basdas_2026-03-31.csv",
    "Apr 2026": f"{BASE_DIR}/basdas_2026-04-29.csv",
    "May 2026": f"{BASE_DIR}/basdas_2026-05-31.csv",
}

OUTPUT_DETAIL  = f"{BASE_DIR}/hunger_threshold_detail.csv"
OUTPUT_SUMMARY = f"{BASE_DIR}/hunger_threshold_summary.csv"

# ─────────────────────────────────────────────────────
# 2.  FOOD BASKET
# ─────────────────────────────────────────────────────
FOOD_BASKET = [
    ("Dairy Products",      "Yogurt",                         "Kg",      59.7),
    ("Dairy Products",      "White Cheese",                   "Kg",       5.7),
    ("Meat and Protein",    "Cubed Meat / Lamb Meat",         "Kg",       4.6),
    ("Meat and Protein",    "Chicken",                        "Kg",      10.3),
    ("Meat and Protein",    "Fish",                           "Kg",       6.9),
    ("Meat and Protein",    "Eggs",                           "Piece",  120.0),
    ("Legumes",             "Chickpeas",                      "Kg",       1.8),
    ("Nuts and Seeds",      "Walnut / Hazelnut / Peanut",     "Kg",       2.7),
    ("Grains",              "Bread",                          "Kg",      18.0),
    ("Fruits",              "Banana",                         "Kg",      16.7),
    ("Fruits",              "Seasonal Fruit",                 "Kg",      12.9),
    ("Vegetables",          "Onion",                          "Kg",      18.0),
    ("Vegetables",          "Eggplant / Zucchini",            "Kg",      23.1),
    ("Vegetables",          "Other Vegetables",               "Kg",      11.8),
    ("Oils",                "Olive Oil",                      "Liter",    1.1),
    ("Other Food Products", "Grissini",                       "Kg",       2.1),
]

# ─────────────────────────────────────────────────────
# 3.  MATCH RULES
# ─────────────────────────────────────────────────────
MATCH_RULES = {
    "Yogurt": {
        "keywords": ["Yoğurt"],
        "exclude": ["Meyveli", "Organik", "Kaymak", "Süzme", "Çırpılmış", "Probiyotik",
                    "Laktozsuz", "Çilek", "Aromalı", "Quark", "Tava", "Cipsi", "Kedi",
                    "Köpek", "Puding", "Mix", "Dip", "Cips", "Meze", "Mama",
                    "Yoğurtlu", "Yoğurt Sütü", "Lay", "Patates", "Çömlek", "Meyve",
                    "Şeftali", "Knorr", "Danone", "Activia"],
        "unit": "kg",
    },
    "White Cheese": {
        "keywords": ["Beyaz Peynir", "Taze Peynir", "Klasik Peynir"],
        "exclude": ["Misto", "Laktozsuz", "Sürülebilir", "Ezine", "Kaşar", "Lor",
                    "Tulum", "Çerkez", "Keçi", "Koyun"],
        "unit": "kg",
    },
    "Cubed Meat / Lamb Meat": {
        "keywords": ["Kuşbaşı"],
        "exclude": ["Döner", "Köfte", "Kedi", "Köpek", "Kıyma", "Hazır", "Kavurma",
                    "Pastırma", "Sucuk", "Sosis", "Dondurulmuş"],
        "unit": "kg",
    },
    "Chicken": {
        "keywords": ["Tavuk", "Piliç"],
        "exclude": ["Döner", "Nugget", "Şinitzel", "Sarma", "Köfte", "Kroket", "Çıtır",
                    "Kebap", "Lokma", "Parmak Bonfile", "Jumbo Fileto", "Izgara Dilimli",
                    "Soslu Kanat", "Kedi", "Köpek", "Mama", "Sucuk", "Sosis", "Füme",
                    "Taşlık", "Ciğer", "Yürek", "Karaciğer", "Tavukgöğsü", "Noodle",
                    "Bulyon", "Salam", "Pilav", "Cips", "Çeşni", "Baharat", "Çorba",
                    "Jambon", "Çabuk", "Yumurta", "Tavuk Göğsü", "Püre", "Pouch",
                    "Ödül", "Izgara", "Pane", "Harcı"],
        "unit": "kg",
    },
    "Fish": {
        "keywords": ["Hamsi", "Levrek", "Somon", "Balık"],
        "exclude": ["Füme", "Konserve", "Kedi", "Köpek", "Maması", "Sosu", "Soslu",
                    "Kraker", "Çikolata", "Şeker", "Mama", "Tava", "Hayvan", "Biftek",
                    "Pouch", "Piliç", "Zeytinyağlı", "Çıtır", "Ton", "Maşa", "Izgara"],
        "unit": "kg",
    },
    "Eggs": {
        "keywords": ["Yumurta"],
        "exclude": ["Organik", "Bıldırcın", "Toz", "Akı", "Sarısı", "Şeker", "Haribo",
                    "Çikolata", "Sürpriz", "Süpriz", "Fırça", "Ozibox", "Elvan",
                    "Yumurtalı", "Ozmo", "Ülker"],
        "unit": "piece",
    },
    "Chickpeas": {
        "keywords": ["Nohut"],
        "exclude": ["Konserve", "Cipsi", "Çerez", "Pilav", "Cips", "Haşlanmış"],
        "unit": "kg",
    },
    "Walnut / Hazelnut / Peanut": {
        "keywords": ["Yer Fıstığı", "Fındık İçi", "Çiğ Fındık", "Kavrulmuş Fındık",
                     "İç Ceviz", "Ceviz İçi", "Antep Fıstığı İçi", "İç Fıstık"],
        "exclude": ["Ezmesi", "Kreması", "Bitter", "Çikolata", "Cips", "Soslu", "Aromalı",
                    "Susamlı", "Dolgulu", "Kaplı", "Draje", "Salam", "Helva", "Granola",
                    "Müsli", "Puding", "Gofret", "Bisküvi", "Bar", "Pasta", "SürMix",
                    "Quark", "Lokum", "Kek", "Kurabiye", "Kakaolu", "Ballı",
                    "Parçacıklı", "Hindistan", "Tütsülenmiş", "Dolmalık"],
        "unit": "kg",
    },
    "Bread": {
        "keywords": ["Ekmek"],
        "exclude": ["Hamburger", "Sandviç", "Tost", "Lavaş", "Tortilla", "Yufka",
                    "Wasa", "Gevrek", "Margarin", "Üstü", "Kırıntı", "Çubuk", "Yer",
                    "Şekersiz", "Kızarmış", "Form", "Grissini"],
        "unit": "kg",
    },
    "Banana": {
        "keywords": ["Muz"],
        "exclude": ["Cipsi", "Kurutulmuş", "Çikolata", "Süt", "Puding", "Gofret",
                    "Bisküvi", "Kek", "Bar", "Milkshake", "İçecek", "Kefir", "Kahve",
                    "Kremalı", "Aromalı", "Maması", "Helva", "Frappe", "Granola",
                    "Grissini", "Krema", "Püresi", "Sıkma", "Muzlu", "Püre", "Dovido",
                    "Mixmey", "Kavanoz", "Dimes", "Kent"],
        "unit": "kg",
    },
    "Seasonal Fruit": {
        "keywords": ["Çilek", "Kiraz", "Vişne", "Kayısı", "Şeftali", "Erik", "İncir",
                     "Üzüm", "Nar", "Kivi", "Kavun", "Karpuz", "Elma", "Portakal",
                     "Mandalina"],
        "exclude": ["Muz", "Limon", "Avokado", "Suyu", "File", "Paket", "Kutu",
                    "Dondurulmuş", "Püre", "Konserve", "Şeker", "Atıştırmalık",
                    "Çikolata", "Aromalı", "Sakız", "Salam", "Reçel", "Gofret",
                    "Pekmez", "Kurabiye", "İçecek", "Çay", "Şölen", "Ülker", "Lolipop",
                    "Kefir", "Süt", "Peynir", "Milkshake", "Deterjan", "Sabun",
                    "Şampuan", "Freedo", "Un", "Kek", "Cips", "Sosis", "Elseve",
                    "Garnier", "Elidor", "Aroma", "Draje", "Pınar", "Nektarı",
                    "Bisküvi", "Narbaharat", "Sirke", "Kuruyemiş", "Sleepy", "Sprey",
                    "Merhem", "Sek", "Activia", "Kemal", "Kuru", "Sos", "Gevrek",
                    "Parçacıklı", "Fanta", "Temizlik", "Mama", "Bar", "Kreması",
                    "Protein", "Kuş", "Kağıt", "Pestil", "İçeceği", "Topu", "Kahve",
                    "Algida", "Krem", "Yağı", "Bi", "Gazoz", "Narenciye", "Tada",
                    "Brillant", "Somon", "Tsuyoi", "Kuru"],
        "unit": "kg",
    },
    "Onion": {
        "keywords": ["Soğan"],
        "exclude": ["Taze", "Pırasa", "Toz", "Pul", "Sarımsak", "Halkası", "Cips",
                    "Çerezza", "Eti", "Tatlı", "Ülker", "Cheetos", "Halka", "Kızartılmış"],
        "unit": "kg",
    },
    "Eggplant / Zucchini": {
        "keywords": ["Patlıcan", "Kabak"],
        "exclude": ["Konserve", "Turşu", "Tatlısı", "Dondurulmuş", "Çekirdeği",
                    "Çekirdek", "Dolma", "Salatası", "Börek", "Sabun", "Yağı",
                    "Maması", "Granola", "Bar", "Liflı", "Köz", "Kuru", "Kurutulmuş",
                    "Cekirdek", "Kızartma"],
        "unit": "kg",
    },
    "Other Vegetables": {
        "keywords": ["Taze Fasulye"],
        "exclude": ["Konserve", "Dondurulmuş", "Zeytinyağ"],
        "unit": "kg",
    },
    "Olive Oil": {
        "keywords": ["Zeytinyağı", "Zeytinyağ"],
        "exclude": ["Spreyı", "Sprey", "Zeytinyağlı", "Sabun", "Krem", "Sleepy",
                    "Saç", "Şampuan"],
        "unit": "ml_or_L",
    },
    "Grissini": {
        "keywords": ["Grissini"],
        "exclude": ["Çikolatalı", "Dolgulu", "Çilek", "Muz", "Krema", "Kakaolu"],
        "unit": "kg",
    },
}

# ─────────────────────────────────────────────────────
# 4.  SEASONAL FRUIT
# ─────────────────────────────────────────────────────
SEASONAL_EXCLUDE = ["Elma","Portakal","Mandalina","Muz","Limon","Avokado",
                    "Adet","Suyu","Gazoz","Aromalı","Saç","Boyası","Kedi","Su","Jel",
                    "Kayganlaştırıcı","Kolonya","Şampuan","Deterjan","Losyon","Sabun",
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

FRUIT_KEYWORDS = ["Kg", "Adet"]
FRUIT_NAMES    = ["Üzüm","Armut","Kiraz","Erik","Şeftali","Kayısı","İncir",
                  "Kivi","Çilek","Karpuz","Kavun","Nar"]

# ─────────────────────────────────────────────────────
# 5.  UTILITIES
# ─────────────────────────────────────────────────────
def parse_price(s) -> float:
    try:
        return float(s)
    except:
        return float("nan")

def extract_weight_g(name: str):
    m = re.search(r"(\d+[,.]?\d*)\s*(KG|G)\b", name.upper())
    if m:
        v = float(m.group(1).replace(",", "."))
        return v * 1000 if m.group(2) == "KG" else v
    return None

def extract_volume_ml(name: str):
    n = re.sub(r"\blt\b", "L", name, flags=re.IGNORECASE).upper()
    mp = re.search(r"(\d+)\s*[xX]\s*(\d+[,.]?\d*)\s*(ML|L)\b", n)
    if mp:
        count = int(mp.group(1))
        each  = float(mp.group(2).replace(",", "."))
        return count * each * (1000 if mp.group(3) == "L" else 1)
    m = re.search(r"(\d+[,.]?\d*)\s*(ML|L)\b", n)
    if m:
        v = float(m.group(1).replace(",", "."))
        return v * 1000 if m.group(2) == "L" else v
    return None

def extract_piece_count(name: str):
    m = re.search(r"(\d+)['\u2019]?\s*(LU|Lİ|LI|li|lu)\b", name, re.IGNORECASE)
    return int(m.group(1)) if m else None

def shorten(name: str, max_len: int = 38) -> str:
    return name if len(name) <= max_len else name[:max_len - 1] + "…"

# ─────────────────────────────────────────────────────
# 6.  COMPUTE UNIT PRICE FOR ONE BASKET ITEM
# ─────────────────────────────────────────────────────
def get_unit_price(df: pd.DataFrame, product_label: str) -> dict:
    rule = MATCH_RULES[product_label]

    if not rule["keywords"]:
        return {"product_label": product_label, "unit": rule["unit"],
                "avg_unit_price": float("nan"), "median_unit_price": float("nan"),
                "n_products": 0, "matched_names": "N/A"}

    kw_mask = df["product_name"].apply(
        lambda x: any(k.lower() in str(x).lower() for k in rule["keywords"])
    )
    sub = df[kw_mask].copy()

    for exc in rule.get("exclude", []):
        sub = sub[~sub["product_name"].str.contains(exc, case=False, na=False)]

    if sub.empty:
        return {"product_label": product_label, "unit": rule["unit"],
                "avg_unit_price": float("nan"), "median_unit_price": float("nan"),
                "n_products": 0, "matched_names": "—"}

    sub = sub.copy()
    sub["_price"] = sub["price"].apply(parse_price)
    sub = sub.dropna(subset=["_price"])

    unit               = rule["unit"]
    min_price_per_unit = rule.get("require_min_price_per_kg", rule.get("min_price_per_kg", 0))
    prices             = []

    for _, row in sub.iterrows():
        name  = str(row["product_name"])
        price = row["_price"]

        if unit == "kg":
            w     = extract_weight_g(name)
            per_u = price / (w / 1000) if w and w > 0 else price
            if per_u < min_price_per_unit:
                continue
            prices.append(per_u)

        elif unit == "ml_or_L":
            v = extract_volume_ml(name) or extract_weight_g(name)
            prices.append(price / (v / 1000) if v and v > 0 else price)

        elif unit == "piece":
            cnt = extract_piece_count(name)
            if cnt and cnt > 0:
                prices.append(price / cnt)
            else:
                prices.append(price)

    avg    = sum(prices) / len(prices) if prices else float("nan")
    median = float(pd.Series(prices).median()) if prices else float("nan")
    names  = "; ".join(shorten(n) for n in sub["product_name"].tolist())

    return {"product_label": product_label, "unit": unit,
            "avg_unit_price": round(avg, 2), "median_unit_price": round(median, 2),
            "n_products": len(prices), "matched_names": names}


def get_seasonal_fruit_price(df: pd.DataFrame) -> dict:
    sub = df[df["product_name"].apply(
        lambda x: any(f.lower() in str(x).lower() for f in FRUIT_NAMES)
    )].copy()

    for exc in SEASONAL_EXCLUDE:
        sub = sub[~sub["product_name"].str.contains(exc, case=False, na=False)]

    sub = sub.copy()
    sub["_price"] = sub["price"].apply(parse_price)
    sub = sub.dropna(subset=["_price"])

    prices = []
    for _, row in sub.iterrows():
        w = extract_weight_g(str(row["product_name"]))
        prices.append(row["_price"] / (w / 1000) if w and w > 0 else row["_price"])

    avg    = sum(prices) / len(prices) if prices else float("nan")
    median = float(pd.Series(prices).median()) if prices else float("nan")
    names  = "; ".join(shorten(n) for n in sub["product_name"].tolist())

    return {"product_label": "Seasonal Fruit", "unit": "kg",
            "avg_unit_price": round(avg, 2), "median_unit_price": round(median, 2),
            "n_products": len(prices), "matched_names": names}

# ─────────────────────────────────────────────────────
# 7.  COMPUTE ONE MONTH
# ─────────────────────────────────────────────────────
def compute_hunger_threshold(csv_path: str, date_label: str) -> pd.DataFrame:
    df = pd.read_csv(csv_path, sep=",")
    df.columns = ["product_name", "price"]

    rows = []
    for category, product_label, unit_label, monthly_qty in FOOD_BASKET:
        if product_label == "Seasonal Fruit":
            info = get_seasonal_fruit_price(df)
        else:
            info = get_unit_price(df, product_label)

        avg_price    = info["avg_unit_price"]
        median_price = info["median_unit_price"]

        rows.append({
            "date":                    date_label,
            "category":                category,
            "product":                 product_label,
            "unit":                    unit_label,
            "monthly_qty":             monthly_qty,
            "avg_unit_price_TRY":      avg_price,
            "avg_monthly_cost_TRY":    round(avg_price    * monthly_qty, 2) if pd.notna(avg_price)    else float("nan"),
            "median_unit_price_TRY":   median_price,
            "median_monthly_cost_TRY": round(median_price * monthly_qty, 2) if pd.notna(median_price) else float("nan"),
            "n_matched":               info["n_products"],
            "matched_products":        info["matched_names"],
        })

    result = pd.DataFrame(rows)
    result["avg_monthly_cost_TRY"]    = pd.to_numeric(result["avg_monthly_cost_TRY"],    errors="coerce")
    result["median_monthly_cost_TRY"] = pd.to_numeric(result["median_monthly_cost_TRY"], errors="coerce")
    return result

# ─────────────────────────────────────────────────────
# 8.  MAIN
# ─────────────────────────────────────────────────────
all_results  = []
summary_rows = []

for date_label, path in FILES.items():
    df_month = compute_hunger_threshold(path, date_label)
    all_results.append(df_month)

    avg_total    = df_month["avg_monthly_cost_TRY"].sum()
    median_total = df_month["median_monthly_cost_TRY"].sum()
    summary_rows.append({
        "date":                        date_label,
        "avg_hunger_threshold_TRY":    round(avg_total,    2),
        "median_hunger_threshold_TRY": round(median_total, 2),
    })

    print(f"\n{'='*100}")
    print(f"  {date_label}  —  Avg: ₺{avg_total:,.2f}  |  Median: ₺{median_total:,.2f}")
    print(f"{'='*100}")
    print(f"  {'Category':<22} {'Product':<30} {'Qty':>6} {'Avg Price':>11} {'Avg Cost':>12} {'Med Price':>11} {'Med Cost':>12}  {'N':>4}")
    print(f"  {'-'*22} {'-'*30} {'-'*6} {'-'*11} {'-'*12} {'-'*11} {'-'*12}  {'-'*4}")
    for _, r in df_month.iterrows():
        ap = f"₺{r['avg_unit_price_TRY']:>8,.2f}"      if pd.notna(r['avg_unit_price_TRY'])     else "       N/A"
        ac = f"₺{r['avg_monthly_cost_TRY']:>9,.2f}"    if pd.notna(r['avg_monthly_cost_TRY'])   else "        N/A"
        mp = f"₺{r['median_unit_price_TRY']:>8,.2f}"   if pd.notna(r['median_unit_price_TRY'])  else "       N/A"
        mc = f"₺{r['median_monthly_cost_TRY']:>9,.2f}" if pd.notna(r['median_monthly_cost_TRY']) else "        N/A"
        print(f"  {r['category']:<22} {r['product']:<30} {r['monthly_qty']:>6.1f}  {ap}  {ac}  {mp}  {mc}  {r['n_matched']:>4}")

all_df     = pd.concat(all_results, ignore_index=True)
summary_df = pd.DataFrame(summary_rows)

print("\n\n" + "="*65)
print("  MONTHLY HUNGER THRESHOLD SUMMARY")
print("="*65)
print(f"  {'Date':<14} {'Avg (₺)':>16}  {'Median (₺)':>16}  {'MoM Avg':>8}  {'MoM Median':>10}")
print(f"  {'-'*14} {'-'*16}  {'-'*16}  {'-'*8}  {'-'*10}")
prev_avg = prev_med = None
for _, r in summary_df.iterrows():
    mom_avg = f"{(r['avg_hunger_threshold_TRY']    - prev_avg) / prev_avg * 100:+.1f}%" if prev_avg else "—"
    mom_med = f"{(r['median_hunger_threshold_TRY'] - prev_med) / prev_med * 100:+.1f}%" if prev_med else "—"
    print(f"  {r['date']:<14} ₺{r['avg_hunger_threshold_TRY']:>14,.2f}  ₺{r['median_hunger_threshold_TRY']:>14,.2f}  {mom_avg:>8}  {mom_med:>10}")
    prev_avg = r["avg_hunger_threshold_TRY"]
    prev_med = r["median_hunger_threshold_TRY"]

all_df.to_csv(OUTPUT_DETAIL,  index=False)
summary_df.to_csv(OUTPUT_SUMMARY, index=False)
print(f"\nDetail  → {OUTPUT_DETAIL}")
print(f"Summary → {OUTPUT_SUMMARY}")
