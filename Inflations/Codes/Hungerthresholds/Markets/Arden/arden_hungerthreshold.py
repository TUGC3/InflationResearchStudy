import pandas as pd
import re

# ─────────────────────────────────────────────────────
# 1.  PATHS
# ─────────────────────────────────────────────────────
BASE_DIR = "/Users/efeyildirim/Downloads/Marketler/Arden"

FILES = {
    "Mar 2026":  f"{BASE_DIR}/arden_urunler_2026-03-31.csv",
    "Apr 2026":  f"{BASE_DIR}/arden_urunler_2026-04-30.csv",
    "Apr2 2026": f"{BASE_DIR}/arden_urunler_2026-05-28.csv",
}

OUTPUT_DETAIL  = f"{BASE_DIR}/hunger_threshold_detail.csv"
OUTPUT_SUMMARY = f"{BASE_DIR}/hunger_threshold_summary.csv"

# ─────────────────────────────────────────────────────
# 2.  FOOD BASKET
# ─────────────────────────────────────────────────────
FOOD_BASKET = [
    ("Dairy Products",      "Yogurt",                         "Kg",     59.7),
    ("Dairy Products",      "White Cheese",                   "Kg",      5.7),
    ("Meat and Protein",    "Cubed Meat / Lamb Meat",         "Kg",      4.6),
    ("Meat and Protein",    "Chicken",                        "Kg",     10.3),
    ("Meat and Protein",    "Fish",                           "Kg",      6.9),
    ("Meat and Protein",    "Eggs",                           "Piece", 120.0),
    ("Legumes",             "Chickpeas",                      "Kg",      1.8),
    ("Nuts and Seeds",      "Walnut / Hazelnut / Peanut",     "Kg",      2.7),
    ("Grains",              "Bread",                          "Kg",     18.0),
    ("Fruits",              "Banana",                         "Kg",     16.7),
    ("Fruits",              "Seasonal Fruit",                 "Kg",     12.9),
    ("Vegetables",          "Onion",                          "Kg",     18.0),
    ("Vegetables",          "Eggplant / Zucchini",            "Kg",     23.1),
    ("Vegetables",          "Other Vegetables",               "Kg",     11.8),
    ("Oils",                "Olive Oil",                      "Liter",   1.1),
    ("Other Food Products", "Grissini",                       "Kg",      2.1),
]

# ─────────────────────────────────────────────────────
# 3.  MATCH RULES
# ─────────────────────────────────────────────────────
MATCH_RULES = {
    # ── Dairy ────────────────────────────────────────────────────────
    "Yogurt": {
        "keywords": ["Yoğurt"],
        "exclude": ["Meyveli", "Organik", "Kaymak", "Süzme", "Çırpılmış", "Probiyotik",
                    "Laktozsuz", "Çilek", "Aromalı", "Quark", "Tava", "Cipsi", "Kedi",
                    "Köpek", "Puding", "Mix", "Dip", "Cips", "Meze", "Mama",
                    "Yoğurtlu", "Yoğurt Sütü", "Lay", "Patates", "Çömlek", "Meyve","Şeftali","Knorr","Danone","Activia"],
        "unit": "kg",
    },
    "White Cheese": {
        "keywords": ["Beyaz Peynir", "Taze Peynir", "Klasik Peynir"],
        "exclude": ["Misto", "Laktozsuz", "Sürülebilir", "Ezine", "Kaşar", "Lor",
                    "Tulum", "Çerkez", "Keçi", "Koyun"],
        "unit": "kg",
    },
    # ── Meat & Protein ───────────────────────────────────────────────
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
                    "Taşlık", "Ciğer", "Yürek", "Karaciğer", "Tavukgöğsü", "Noodle", "Bulyon", "Salam", "Pilav", "Cips",
                    "Çeşni", "Baharat", "Çorba", "Jambon", "Çabuk", "Yumurta","Tavuk Göğsü","Püre","Pouch","Ödül","Izgara","Pane","Harcı"],
        "unit": "kg",
    },
    "Fish": {
        "keywords": ["Hamsi", "Levrek", "Somon", "Balık"],
        "exclude": ["Füme", "Konserve", "Kedi", "Köpek", "Maması", "Sosu", "Soslu", "Kraker", "Çikolata", "Şeker",
                    "Mama", "Tava", "Hayvan","Biftek","Pouch","Piliç","Zeytinyağlı","Çıtır","Ton","Maşa","Izgara"],
        "unit": "kg",
    },
    "Eggs": {
        "keywords": ["Yumurta"],
        "exclude": ["Organik", "Bıldırcın", "Toz", "Akı", "Sarısı", "Şeker", "Haribo", "Çikolata", "Sürpriz","Süpriz","Fırça","Ozibox","Elvan","Yumurtalı","Ozmo","Ülker"],
        "unit": "piece",
    },
    # ── Legumes ──────────────────────────────────────────────────────
    "Chickpeas": {
        "keywords": ["Nohut"],
        "exclude": ["Konserve", "Cipsi", "Çerez", "Pilav","Cips","Haşlanmış"],
        "unit": "kg",
    },
    # ── Nuts ─────────────────────────────────────────────────────────
    "Walnut / Hazelnut / Peanut": {
        "keywords": ["Yer Fıstığı", "Fındık İçi", "Çiğ Fındık", "Kavrulmuş Fındık",
                     "İç Ceviz", "Ceviz İçi", "Antep Fıstığı İçi", "İç Fıstık"],
        "exclude": ["Ezmesi", "Kreması", "Bitter", "Çikolata", "Cips", "Soslu", "Aromalı",
                    "Susamlı", "Dolgulu", "Kaplı", "Draje", "Salam", "Helva", "Granola",
                    "Müsli", "Puding", "Gofret", "Bisküvi", "Bar", "Pasta", "SürMix",
                    "Quark", "Lokum", "Kek", "Kurabiye", "Kakaolu", "Ballı", "Parçacıklı",
                    "Hindistan", "Tütsülenmiş","Dolmalık"],
        "unit": "kg",
    },
    # ── Grains ───────────────────────────────────────────────────────
    "Bread": {
        "keywords": ["Ekmek"],
        "exclude": ["Hamburger", "Sandviç", "Tost", "Lavaş", "Tortilla", "Yufka",
                    "Wasa", "Gevrek", "Margarin", "Üstü", "Kırıntı", "Çubuk", "Yer", "Şekersiz", "Kızarmış","Form","Grissini"],
        "unit": "kg",
    },
    # ── Fruits ───────────────────────────────────────────────────────
    "Banana": {
        "keywords": ["Muz"],
        "exclude": ["Cipsi", "Kurutulmuş", "Çikolata", "Süt", "Puding", "Gofret",
                    "Bisküvi", "Kek", "Bar", "Milkshake", "İçecek", "Kefir", "Kahve",
                    "Kremalı", "Aromalı", "Maması", "Helva", "Frappe", "Granola",
                    "Grissini", "Krema","Püresi","Sıkma","Muzlu","Püre","Dovido","Mixmey","Kavanoz","Dimes","Kent"],
        "unit": "kg",
    },
    "Seasonal Fruit": {
        "keywords": ["Çilek", "Kiraz", "Vişne", "Kayısı", "Şeftali",
                     "Erik", "İncir", "Üzüm", "Nar", "Kivi", "Kavun", "Karpuz", "Elma", "Portakal", "Mandalina"],
        "exclude": ["Muz", "Limon", "Avokado", "Suyu", "File", "Paket", "Kutu", "Dondurulmuş", "Püre", "Konserve",
                    "Şeker", "Atıştırmalık", "Çikolata", "Aromalı", "Sakız", "Salam", "Reçel", "Gofret", "Pekmez",
                    "Kurabiye",
                    "İçecek", "Şeker", "Çay", "Şölen", "Ülker", "Lolipop", "Kefir", "Süt", "Peynir", "Milkshake",
                    "Deterjan", "Sabun", "Şampuan", "Freedo", "Un", "Kek", "Cips", "Sosis", "Elseve", "Garnier",
                    "Elidor", "Aroma", "Draje", "Pınar", "Nektarı",
                    "Bisküvi", "Narbaharat", "Sirke", "Kuruyemiş", "Sleepy", "Sprey", "Merhem", "Sek", "Activia",
                    "Kemal", "Kuru", "Sos", "Gevrek", "Parçacıklı", "Fanta", "Temizlik", "Mama", "Bar", "Kreması",
                    "Protein",
                    "Kuş", "Kağıt", "Pestil", "İçeceği", "Topu", "Kahve", "Algida", "Krem", "Yağı", "Bi", "Gazoz",
                    "Narenciye", "Tada", "Brillant", "Somon", "Tsuyoi","Kuru"],
        "unit": "kg",
    },
    # ── Vegetables ───────────────────────────────────────────────────
    "Onion": {
        "keywords": ["Soğan"],
        "exclude": ["Taze", "Pırasa", "Toz", "Pul", "Sarımsak", "Halkası","Cips","Çerezza","Eti","Tatlı","Ülker","Cheetos"],
        "unit": "kg",
    },
    "Eggplant / Zucchini": {
        "keywords": ["Patlıcan", "Kabak"],
        "exclude": ["Konserve", "Turşu", "Tatlısı", "Dondurulmuş", "Çekirdeği",
                    "Çekirdek", "Dolma", "Salatası", "Börek", "Sabun", "Yağı",
                    "Maması", "Granola", "Bar", "Liflı", "Köz","Kuru","Kurutulmuş","Cekirdek","Kızartma"],
        "unit": "kg",
    },
    "Other Vegetables": {
        "keywords": ["Taze Fasulye"],
        "exclude": ["Konserve", "Dondurulmuş", "Zeytinyağ"],
        "unit": "kg",
    },
    # ── Oils ─────────────────────────────────────────────────────────
    "Olive Oil": {
        "keywords": ["Zeytinyağı", "Zeytinyağ"],
        "exclude": ["Spreyı", "Sprey", "Zeytinyağlı", "Sabun", "Krem","Sleepy","Saç","Şampuan"],
        "unit": "ml_or_L",
    },
    # ── Other Food ───────────────────────────────────────────────────
    "Grissini": {
        "keywords": ["Grissini"],
        "exclude": ["Çikolatalı", "Dolgulu", "Çilek", "Muz", "Krema","Kakaolu"],
        "unit": "kg",
    },
}

# ─────────────────────────────────────────────────────
# 4.  SEASONAL FRUIT —
# ─────────────────────────────────────────────────────
FRUIT_KEYWORDS = [
    "Elma Kg", "Armut Kg", "Şeftali Kg", "Kiraz Kg", "Erik Kg",
    "Kayısı Kg", "Üzüm Kg", "Nar Kg", "Kivi Kg", "Çilek Kg",
    "Kavun Kg", "Karpuz Kg", "İncir Kg", "Vişne Kg",
    "Trabzon Hurması Kg", "Mandalina Kg", "Greyfurt Kg", "Portakal Kg",
    "Atıştırmalık Elma", "Atıştırmalık Armut",
]

# ─────────────────────────────────────────────────────
# 5.  UTILITIES
# ─────────────────────────────────────────────────────
def parse_price(s: str) -> float:
    s = str(s).replace("₺", "").replace(".", "").replace(",", ".").strip()
    try:    return float(s)
    except: return float("nan")

def extract_weight_g(name: str):
    m = re.search(r"(\d+[,.]?\d*)\s*(KG|GR|G)\b", name.upper())
    if m:
        v = float(m.group(1).replace(",", "."))
        return v * 1000 if m.group(2) == "KG" else v
    return None

def extract_volume_ml(name: str):
    # "lt" → "L" (Arden convention)
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

    # Fish not available at Arden
    if not rule["keywords"]:
        return {"product_label": product_label, "unit": rule["unit"],
                "unit_price": float("nan"), "n_products": 0, "matched_names": "N/A"}

    kw_mask = df["product_name"].apply(
        lambda x: any(k.lower() in str(x).lower() for k in rule["keywords"])
    )
    sub = df[kw_mask].copy()

    for exc in rule.get("exclude", []):
        sub = sub[~sub["product_name"].str.contains(exc, case=False, na=False)]

    if sub.empty:
        return {"product_label": product_label, "unit": rule["unit"],
                "unit_price": float("nan"), "n_products": 0, "matched_names": "—"}

    sub = sub.copy()
    sub["price"] = sub["price"].apply(parse_price)
    sub = sub.dropna(subset=["price"])

    unit               = rule["unit"]
    min_price_per_unit = rule.get("require_min_price_per_kg", 0)
    prices             = []

    for _, row in sub.iterrows():
        name  = str(row["product_name"])
        price = row["price"]

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

    avg   = sum(prices) / len(prices) if prices else float("nan")
    names = "; ".join(shorten(n) for n in sub["product_name"].tolist())

    return {"product_label": product_label, "unit": unit,
            "unit_price": round(avg, 2), "n_products": len(prices),
            "matched_names": names}


def get_seasonal_fruit_price(df: pd.DataFrame) -> dict:
    """Taze meyvelerin kg fiyatı — 'X Kg' formatındaki keyword'lerle eşleşir."""
    # word-boundary regex ile "Nar" → "Pınar" sorununu önle
    mask = df["product_name"].apply(
        lambda x: any(k.lower() in str(x).lower() for k in FRUIT_KEYWORDS)
    )
    sub = df[mask].copy()

    if sub.empty:
        return {"product_label": "Seasonal Fruit", "unit": "kg",
                "unit_price": float("nan"), "n_products": 0, "matched_names": "—"}

    sub["price"] = sub["price"].apply(parse_price)
    sub = sub.dropna(subset=["price"])

    prices = []
    for _, row in sub.iterrows():
        w = extract_weight_g(str(row["product_name"]))
        prices.append(row["price"] / (w / 1000) if w and w > 0 else row["price"])

    avg   = sum(prices) / len(prices) if prices else float("nan")
    names = "; ".join(shorten(n) for n in sub["product_name"].tolist())
    return {"product_label": "Seasonal Fruit", "unit": "kg",
            "unit_price": round(avg, 2), "n_products": len(prices),
            "matched_names": names}

# ─────────────────────────────────────────────────────
# 7.  COMPUTE ONE MONTH
# ─────────────────────────────────────────────────────
def compute_hunger_threshold(csv_path: str, date_label: str) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    df.columns = ["product_name", "price"]

    rows = []
    for category, product_label, unit_label, monthly_qty in FOOD_BASKET:
        if product_label == "Seasonal Fruit":
            info = get_seasonal_fruit_price(df)
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
# 8.  MAIN
# ─────────────────────────────────────────────────────
all_results  = []
summary_rows = []

for date_label, path in FILES.items():
    df_month = compute_hunger_threshold(path, date_label)
    all_results.append(df_month)
    total = df_month["monthly_cost_TRY"].sum()
    summary_rows.append({"date": date_label, "hunger_threshold_TRY": round(total, 2)})

    print(f"\n{'='*110}")
    print(f"  {date_label}  —  Hunger Threshold: ₺{total:,.2f}")
    print(f"{'='*110}")
    print(f"  {'Category':<22} {'Product':<30} {'Qty':>6} {'Unit Price':>12} {'Monthly Cost':>14}  "
          f"{'N':>4}  Matched Products")
    print(f"  {'-'*22} {'-'*30} {'-'*6} {'-'*12} {'-'*14}  {'-'*4}  {'-'*40}")
    for _, r in df_month.iterrows():
        names_preview = (str(r["matched_products"])[:60] + "…"
                         if len(str(r["matched_products"])) > 60
                         else str(r["matched_products"]))
        price_str = f"₺{r['avg_unit_price_TRY']:>9,.2f}" if pd.notna(r["avg_unit_price_TRY"]) else "       N/A"
        cost_str  = f"₺{r['monthly_cost_TRY']:>11,.2f}"  if pd.notna(r["monthly_cost_TRY"])  else "         N/A"
        print(f"  {r['category']:<22} {r['product']:<30} {r['monthly_qty']:>6.1f} "
              f"  {price_str}   {cost_str}  "
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
    mom = f"{(r['hunger_threshold_TRY'] - prev) / prev * 100:+.1f}%" if prev else "—"
    print(f"  {r['date']:<12} ₺{r['hunger_threshold_TRY']:>14,.2f}  {mom:>12}")
    prev = r["hunger_threshold_TRY"]

all_df.to_csv(OUTPUT_DETAIL,  index=False)
summary_df.to_csv(OUTPUT_SUMMARY, index=False)
print(f"\nDetail  → {OUTPUT_DETAIL}")
print(f"Summary → {OUTPUT_SUMMARY}")
