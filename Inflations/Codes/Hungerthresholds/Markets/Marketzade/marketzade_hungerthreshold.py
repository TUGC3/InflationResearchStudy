"""
Marketzade is an online non-perishables market.
The following basket items are NOT stocked and will show as N/A:
  Yogurt, White Cheese, Kashar, Minced Meat, Cubed Meat, Chicken,
  Fish, Eggs, Bread, Nuts, Apple, Orange, Banana, Seasonal Fruit,
  Potato, Onion, Tomato, Cucumber, Pepper, Eggplant, Carrot,
  Greens, Other Vegetables, Butter, Margarine
"""

import re
import pandas as pd
from pathlib import Path

# ── 1. PATHS ────────────────────────────────────────────
BASE_DIR = "/Users/efeyildirim/Downloads/Marketler/Marketzade"

FILES = {
    "Feb-24 2026": f"{BASE_DIR}/2026-02-24.csv",
    "Feb-28 2026": f"{BASE_DIR}/2026-02-28.csv",
    "Mar 2026":    f"{BASE_DIR}/2026-03-31.csv",
    "Apr 2026":    f"{BASE_DIR}/2026-04-30.csv",
    "May 2026":    f"{BASE_DIR}/2026-05-27.csv",
}

OUTPUT_DETAIL  = f"{BASE_DIR}/hunger_threshold_detail.csv"
OUTPUT_SUMMARY = f"{BASE_DIR}/hunger_threshold_summary.csv"

# ── 2. FOOD BASKET ──────────────────────────────────────
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

# ── 3. MATCH RULES ──────────────────────────────────────
MATCH_RULES = {
    # ── Dairy ─────────────────────────────────────────────────────────
    "Milk": {
        "kat": ["icecek"],
        "kw":  ["Süt"],
        "ex":  ["Çikolata","Kakao","Çilek","Muzlu","Aromalı","Soya","Badem","Yulaf",
                "Kefir","Ayran","Sütlü","Kaymak","Sütlaç","Krema","Devam","Bebek",
                "Laktozsuz","Protein","Organik","200 Ml","180 Ml","6 X 180",
                "6X180","Sabun","Hindistan","Nesquik"],
        "unit": "ml_or_L",
        "max_price_per_kg": 200,
    },
    "Yogurt":                    {"kat": [], "kw": [], "ex": [], "unit": "kg"},
    "White Cheese":              {"kat": [], "kw": [], "ex": [], "unit": "kg"},
    "Kashar / Other Cheese":     {"kat": [], "kw": [], "ex": [], "unit": "kg"},
    "Minced Meat":               {"kat": [], "kw": [], "ex": [], "unit": "kg"},
    "Cubed Meat / Lamb Meat":    {"kat": [], "kw": [], "ex": [], "unit": "kg"},
    "Chicken":                   {"kat": [], "kw": [], "ex": [], "unit": "kg"},
    "Fish":                      {"kat": [], "kw": [], "ex": [], "unit": "kg"},
    "Eggs":                      {"kat": [], "kw": [], "ex": [], "unit": "piece"},
    # ── Legumes ───────────────────────────────────────────────────────
    "Dried Beans": {
        "kat": ["temel-gida"],
        "kw":  ["Dermason Fasulye","Kuru Fasulye"],
        "ex":  ["Pilaki","Haşlanmış","Konserve","Organik","Maş"],
        "unit": "kg",
        "max_price_per_kg": 400,
    },
    "Chickpeas": {
        "kat": ["temel-gida"],
        "kw":  ["Nohut"],
        "ex":  ["Haşlanmış","Konserve","Pilav","Cips","Organik"],
        "unit": "kg",
        "max_price_per_kg": 500,
    },
    "Red Lentils": {
        "kat": ["temel-gida"],
        "kw":  ["Kırmızı Mercimek"],
        "ex":  ["Çorba","Organik","Makarna","Erişte"],
        "unit": "kg",
        "max_price_per_kg": 400,
    },
    "Green Lentils": {
        "kat": ["temel-gida"],
        "kw":  ["Yeşil Mercimek"],
        "ex":  ["Çorba","Organik","Makarna"],
        "unit": "kg",
        "max_price_per_kg": 400,
    },
    "Walnut / Hazelnut / Peanut": {"kat": [], "kw": [], "ex": [], "unit": "kg"},
    "Bread":                      {"kat": [], "kw": [], "ex": [], "unit": "kg"},
    # ── Grains ────────────────────────────────────────────────────────
    "Rice": {
        "kat": ["temel-gida"],
        "kw":  ["Pirinç"],
        "ex":  ["Gevreği","Sirke","Bebek","Sushi","Unu","Mama","Pilav Karışım"],
        "unit": "kg",
        "max_price_per_kg": 300,
    },
    "Bulgur": {
        "kat": ["temel-gida"],
        "kw":  ["Bulgur"],
        "ex":  ["Organik","Pilavı","Çorbası","Karışımı"],
        "unit": "kg",
    },
    "Pasta": {
        "kat": ["temel-gida"],
        "kw":  ["Makarna"],
        "ex":  ["Sosu","Hazır","Çorba","Kedi","Bebek","Erişte"],
        "unit": "kg",
    },
    "Flour": {
        "kat": ["temel-gida"],
        "kw":  ["Un"],
        "ex":  ["Galeta","Mısır","Nişasta","Glutensiz","Baklava","Nohut","Cajun","Baharat","Yulaf",
                "Kek","Kurabiye","Pirinç","Böreklik","Siyez","Tam Buğday",
                "Organik","Karışım","Pasta","Makarna","Uno","Erişte",
                "Barbunya","Fasulye","Şehriye","Haşlanmış","Pilaki"],
        "unit": "kg",
        "max_price_per_kg": 150,
    },
    "Semolina": {
        "kat": ["temel-gida"],
        "kw":  ["İrmik"],
        "ex":  ["Helvası","Bebek","Organik"],
        "unit": "kg",
        "max_price_per_kg": 200,
    },
    # ── Fruits / Vegetables — NOT STOCKED ─────────────────────────────
    "Apple":                     {"kat": [], "kw": [], "ex": [], "unit": "kg"},
    "Orange / Mandarin":         {"kat": [], "kw": [], "ex": [], "unit": "kg"},
    "Banana":                    {"kat": [], "kw": [], "ex": [], "unit": "kg"},
    "Seasonal Fruit":            {"kat": [], "kw": [], "ex": [], "unit": "kg"},
    "Potato":                    {"kat": [], "kw": [], "ex": [], "unit": "kg"},
    "Onion":                     {"kat": [], "kw": [], "ex": [], "unit": "kg"},
    "Tomato":                    {"kat": [], "kw": [], "ex": [], "unit": "kg"},
    "Cucumber":                  {"kat": [], "kw": [], "ex": [], "unit": "kg"},
    "Pepper":                    {"kat": [], "kw": [], "ex": [], "unit": "kg"},
    "Eggplant / Zucchini":       {"kat": [], "kw": [], "ex": [], "unit": "kg"},
    "Carrot":                    {"kat": [], "kw": [], "ex": [], "unit": "kg"},
    "Greens / Lettuce / Parsley":{"kat": [], "kw": [], "ex": [], "unit": "piece"},
    "Other Vegetables":          {"kat": [], "kw": [], "ex": [], "unit": "kg"},
    # ── Oils ──────────────────────────────────────────────────────────
    "Sunflower Oil": {
        "kat": ["temel-gida"],
        "kw":  ["Ayçiçek Yağı"],
        "ex":  ["Ton","Sardin","Sprey"],
        "unit": "ml_or_L",
    },
    "Olive Oil": {
        "kat": ["temel-gida"],
        "kw":  ["Zeytinyağı"],
        "ex":  ["Ton","Sabun","Sprey","Konserve","Sarma","Sızma Zeytinyağı 5 lt x 4"],
        "unit": "ml_or_L",
        "max_price_per_kg": 3000,
    },
    "Butter":   {"kat": [], "kw": [], "ex": [], "unit": "kg"},
    "Margarine":{"kat": [], "kw": [], "ex": [], "unit": "kg"},
    # ── Breakfast ─────────────────────────────────────────────────────
    "Olives": {
        "kat": ["kahvaltilik"],
        "kw":  ["Zeytin"],
        "ex":  ["Yağı","Ezmesi","Sabun","Zeytinyağlı","Bisküvi","Kraker",
                "Sarma","Dolgulu","Reçeli"],
        "unit": "kg",
    },
    # ── Other Food ────────────────────────────────────────────────────
    "Sugar": {
        "kat": ["temel-gida"],
        "kw":  ["Toz Şeker"],
        "ex":  ["Küp","Esmer","Kahverengi","Pudra","Vanilin"],
        "unit": "kg",
    },
    "Tea": {
        "kat": ["icecek"],
        "kw":  ["Çay"],
        "ex":  ["Bitki","Soğuk","Meyve","Ihlamur","Papatya","Adaçayı","Yeşil",
                "Bergamot","Earl Grey","Poşet","Demlik","Zencefil","Nane",
                "Elma","Limon","Ada Çayı","Kış","Form","Kuşburnu","Rezene",
                "Melisa","Makinesi","Seti","Beyaz Çay","Rooibos","Mate"],
        "unit": "kg",
        "require_weight": True,
        "max_price_per_kg": 700,
    },
    "Tomato Paste": {
        "kat": ["temel-gida"],
        "kw":  ["Domates Salçası","Domates Salça"],
        "ex":  ["Biber","Acı","Köy","Hazır"],
        "unit": "kg",
        "max_price_per_kg": 300,
    },
    "Jam": {
        "kat": ["kahvaltilik"],
        "kw":  ["Reçel"],
        "ex":  ["Diabetik","Süt Reçeli","Ceviz","Kestane",
                "Piknik","100 Lü","x 36","36 Adet","30 Gr x"],
        "unit": "kg",
        "max_price_per_kg": 600,
    },
    "Honey": {
        "kat": ["kahvaltilik"],
        "kw":  ["Bal"],
        "ex":  ["Kabağı","Propolis","Bisküvi","Bar","Granola","Çikolata",
                "Polen","Arısütü","Sabun","Şampuan","Puding",
                "Piknik","100 Lü","x 100","Muhallebi","Nesfit",
                "Gevrek","Kahvaltılık","Ballı","Dr. Oetker"],
        "unit": "kg",
        "max_price_per_kg": 4000,
    },
    "Molasses": {
        "kat": ["kahvaltilik"],
        "kw":  ["Pekmez"],
        "ex":  ["Tahin","Sucuk","Keçiboynuzu","Harnup"],
        "unit": "kg",
        "max_price_per_kg": 800,
    },
    "Salt": {
        "kat": ["temel-gida"],
        "kw":  ["Tuz"],
        "ex":  ["Tuzlu","Tuzsuz","Turşu","Salamura","Limon","Zeytinli",
                "Sos","Tuzluklu","Himalaya","Sodyumu Azaltılmış","Deniz Tuzu",
                "Değirmenli","Kaya Tuzu","Biber Tuzluklu"],
        "unit": "kg",
        "require_weight": True,
        "max_price_per_kg": 150,
    },
    "Average Spices": {
        "kat": ["temel-gida"],
        "kw":  ["Karabiber","Pul Biber"],
        "ex":  ["Tuzluklu","Tane","Hindistan","Dolmalık","Harç","Cajun",
                "Izgara","Baharatı","Kedi","Köpek"],
        "unit": "kg",
        "require_weight": True,
        "max_price_per_kg": 1000,
    },
    "Linden / Herbal Tea": {
        "kat": ["icecek"],
        "kw":  ["Ihlamur","Papatya"],
        "ex":  ["Adaçayı","Zencefil","Form","Kış","Kayısı","Soğuk",
                "Rahat Hisset","Passifloralı","Rezene"],
        "unit": "piece",
        "require_weight": True,
    },
}

# ── 4. UTILITIES ────────────────────────────────────────
def extract_weight_g(name: str):
    m = re.search(r'(\d+[,.]?\d*)\s*(Kg|kg|KG)\b', name)
    if m:
        raw = m.group(1); sep = re.match(r'^(\d+)[,.](\d{3})$', raw)
        return float(sep.group(1)+sep.group(2))*1000 if sep else float(raw.replace(',','.'))*1000
    m = re.search(r'(\d+[,.]?\d*)\s*(Gr|gr|GR|G)\b', name)
    if m:
        raw = m.group(1); sep = re.match(r'^(\d+)[,.](\d{3})$', raw)
        return float(sep.group(1)+sep.group(2)) if sep else float(raw.replace(',','.'))
    return None

def extract_volume_ml(name: str):
    n = re.sub(r'\bLt\b', 'L', name, flags=re.IGNORECASE)
    n = re.sub(r'\bLitre\b', 'L', n, flags=re.IGNORECASE).upper()
    mp = re.search(r'(\d+)[xX](\d+[,.]?\d*)\s*(ML|L)\b', n)
    if mp:
        c = int(mp.group(1)); e = float(mp.group(2).replace(',','.'))
        return c * e * (1000 if mp.group(3) == 'L' else 1)
    m = re.search(r'(\d+[,.]?\d*)\s*(ML|L)\b', n)
    if m:
        v = float(m.group(1).replace(',','.')); return v*1000 if m.group(2)=='L' else v
    return None

def extract_piece_count(name: str):
    m = re.search(r"(\d+)['\u2019]?\s*(LU|Lİ|LI|li|lu)\b", name, re.IGNORECASE)
    if m: return int(m.group(1))
    m2 = re.search(r"(\d+)'?\s*[Ll][İi]\b", name)
    if m2: return int(m2.group(1))
    m3 = re.search(r'(\d+)\s*[Aa]det', name)
    if m3: return int(m3.group(1))
    return None

# ── 5. UNIT PRICE CALCULATOR ────────────────────────────
def get_unit_price(df: pd.DataFrame, product_label: str) -> dict:
    rule = MATCH_RULES[product_label]
    if not rule['kat']:
        return {'unit_price': float('nan'), 'n_products': 0, 'matched_names': 'N/A'}

    sub = df[df['kategori'].isin(rule['kat'])].copy()

    if not rule['kw']:
        return {'unit_price': float('nan'), 'n_products': 0, 'matched_names': 'N/A'}

    mask = sub['item_name'].apply(
        lambda x: any(k.lower() in str(x).lower() for k in rule['kw'])
    )
    sub = sub[mask]
    for exc in rule['ex']:
        sub = sub[~sub['item_name'].str.contains(exc, case=False, na=False)]

    if sub.empty:
        return {'unit_price': float('nan'), 'n_products': 0, 'matched_names': '—'}

    unit  = rule['unit']
    req_w = rule.get('require_weight', False)
    min_p = rule.get('min_price_per_kg', 0)
    max_p = rule.get('max_price_per_kg', None)
    prices = []

    for _, row in sub.iterrows():
        name  = str(row['item_name'])
        price = float(row['price'])

        if unit == 'kg':
            w = extract_weight_g(name)
            if req_w and not w: continue
            per_u = price / (w / 1000) if w and w > 0 else price
            if per_u < min_p: continue
            if max_p and per_u > max_p: continue
            prices.append(per_u)

        elif unit == 'ml_or_L':
            v = extract_volume_ml(name) or extract_weight_g(name)
            per_u = price / (v / 1000) if v and v > 0 else price
            if max_p and per_u > max_p: continue
            prices.append(per_u)

        elif unit == 'piece':
            cnt = extract_piece_count(name)
            if cnt and cnt > 0:
                per_each = price / cnt
                if product_label == 'Linden / Herbal Tea':
                    prices.append(per_each / 0.002)
                else:
                    prices.append(per_each)
            elif req_w:
                continue
            else:
                prices.append(price)

    avg   = sum(prices) / len(prices) if prices else float('nan')
    names = '; '.join(
        n[:45] + ('…' if len(n) > 45 else '') for n in sub['item_name'].tolist()
    )
    return {'unit_price': round(avg, 2), 'n_products': len(prices), 'matched_names': names}

# ── 6. MONTHLY COMPUTATION ──────────────────────────────
def compute_hunger_threshold(csv_path: str, date_label: str) -> pd.DataFrame:
    df = pd.read_csv(csv_path, encoding='utf-8-sig')
    df = df.drop_duplicates(subset=['item_name'])
    rows = []
    for category, product_label, unit_label, monthly_qty in FOOD_BASKET:
        # Seasonal fruit handled same as other not-stocked items
        info = get_unit_price(df, product_label)
        unit_price = info['unit_price']
        if product_label == 'Greens / Lettuce / Parsley':
            monthly_cost = unit_price * (monthly_qty / 0.25)
        else:
            monthly_cost = unit_price * monthly_qty
        rows.append({
            'date': date_label, 'category': category,
            'product': product_label, 'unit': unit_label,
            'monthly_qty': monthly_qty,
            'avg_unit_price_TRY': unit_price,
            'monthly_cost_TRY': round(monthly_cost, 2) if pd.notna(unit_price) else float('nan'),
            'n_matched': info['n_products'],
            'matched_products': info['matched_names'],
        })
    return pd.DataFrame(rows)

# ── 7. MAIN ─────────────────────────────────────────────
all_results  = []
summary_rows = []

for date_label, path in FILES.items():
    if not Path(path).exists():
        print(f"  ⚠  File not found: {path}"); continue

    df_month = compute_hunger_threshold(path, date_label)
    total    = df_month['monthly_cost_TRY'].sum()
    n_na     = df_month['avg_unit_price_TRY'].isna().sum()
    all_results.append(df_month)
    summary_rows.append({'date': date_label, 'hunger_threshold_TRY': round(total, 2), 'n_na': int(n_na)})

    na_note = f'  [{n_na} N/A]' if n_na else ''
    print(f"\n{'='*100}")
    print(f"  {date_label}  —  Partial Hunger Threshold: ₺{total:,.2f}{na_note}")
    print(f"{'='*100}")
    print(f"  {'Category':<22} {'Product':<30} {'Qty':>5} {'Unit Price':>12} {'Monthly Cost':>14}  {'N':>4}  Matched Products")
    print(f"  {'-'*22} {'-'*30} {'-'*5} {'-'*12} {'-'*14}  {'-'*4}  {'-'*40}")
    for _, r in df_month.iterrows():
        preview   = str(r['matched_products'])[:60]
        price_str = f"₺{r['avg_unit_price_TRY']:>9,.2f}" if pd.notna(r['avg_unit_price_TRY']) else '       N/A'
        cost_str  = f"₺{r['monthly_cost_TRY']:>11,.2f}"  if pd.notna(r['monthly_cost_TRY'])  else '         N/A'
        print(f"  {r['category']:<22} {r['product']:<30} {r['monthly_qty']:>5.1f}   {price_str}   {cost_str}  {r['n_matched']:>4}  {preview}")

all_df     = pd.concat(all_results, ignore_index=True)
summary_df = pd.DataFrame(summary_rows)

print('\n\n' + '='*55)
print('  MONTHLY PARTIAL HUNGER THRESHOLD SUMMARY')
print('  (only stocked items — ~22 of 47 basket items)')
print('='*55)
print(f"  {'Date':<14} {'Threshold (₺)':>16}  {'MoM':>8}  {'N/A':>5}")
print(f"  {'-'*14} {'-'*16}  {'-'*8}  {'-'*5}")
prev = None
for _, r in summary_df.iterrows():
    mom = f"{(r['hunger_threshold_TRY']-prev)/prev*100:+.1f}%" if prev else '—'
    na  = f"[{r['n_na']} N/A]" if r['n_na'] else ''
    print(f"  {r['date']:<14} ₺{r['hunger_threshold_TRY']:>14,.2f}  {mom:>8}  {na}")
    prev = r['hunger_threshold_TRY']

all_df.to_csv(OUTPUT_DETAIL,  index=False)
summary_df.to_csv(OUTPUT_SUMMARY, index=False)
print(f"\nDetail  → {OUTPUT_DETAIL}")
print(f"Summary → {OUTPUT_SUMMARY}")
