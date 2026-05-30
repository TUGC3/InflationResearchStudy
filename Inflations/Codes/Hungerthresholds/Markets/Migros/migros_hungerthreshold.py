"""
NOT STOCKED: Bread, Semolina, Nut kernels — N/A for all months
  These will show N/A every month.
"""

import re
import pandas as pd
from pathlib import Path

# ── 1. PATHS ────────────────────────────────────────────
BASE_DIR = "/Users/efeyildirim/Downloads/Marketler/Migros"

FILES = {
    "Feb-24 2026": f"{BASE_DIR}/migros_2026-02-24.csv",
    "Feb-28 2026": f"{BASE_DIR}/migros_2026-02-28.csv",
    "Mar 2026":    f"{BASE_DIR}/migros_2026-03-31.csv",
    "Apr 2026":    f"{BASE_DIR}/migros_2026-04-30.csv",
    "May 2026":    f"{BASE_DIR}/migros_2026-05-26.csv",
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
# cats = list of category names to filter on (exact match)
# kw   = keywords (any must appear in 'name', case-insensitive)
# ex   = excludes
# unit = "kg" | "ml_or_L" | "piece"
# For GRAM unit items: price is already per-kg. For PIECE: normalise.

MATCH_RULES = {
    # ── Dairy ─────────────────────────────────────────────────────────
    "Milk": {
        "cats": ["Uzun Ömürlü Süt","Günlük Süt"],
        "kw":   ["Süt"],
        "ex":   ["Çikolata","Kakao","Çilek","Muzlu","Aromalı","Soya","Badem",
                 "Yulaf","Kefir","Ayran","Sütlü","Kaymak","Sütlaç","Krema",
                 "Devam","Bebek","Laktozsuz","Protein","Organik",
                 "200 Ml","180 Ml","6X180","6 X","Nesquik",
                 "Keçi","Latte","500 Ml"],
        "unit": "ml_or_L",
        "max_price_per_kg": 120,
    },
    "Yogurt": {
        "cats": ["Sade Yoğurt","Diğer Yoğurtlar"],
        "kw":   ["Yoğurt"],
        "ex":   ["Meyveli","Kaymaklı","Çırpılmış","Laktozsuz","Çilek","Aromalı",
                 "Kefir","Bebek","Probiyotik","Süzme","Tava","Puding","Light",
                 "Fermente","Manda","Keçi"],
        "unit": "kg",
    },
    "White Cheese": {
        "cats": ["Yerli Yöresel Peynir","İnek Peyniri"],
        "kw":   ["Beyaz Peynir","Taze Peynir","Klasik Peynir"],
        "ex":   ["Kaşar","Lor","Dil","Örgü","Çeçil","Krem","Mozzarella",
                 "Labne","Tulum","Süzme","Laktozsuz","Hellim","Organik"],
        "unit": "kg",
    },
    "Kashar / Other Cheese": {
        "cats": ["Taze Kaşar","Eski Kaşar"],
        "kw":   ["Kaşar"],
        "ex":   ["Sandviç","Köfte","Bisküvi","Burger","Gravyer"],
        "unit": "kg",
    },
    "Minced Meat": {
        "cats": ["Dana Eti"],
        "kw":   ["Kıymalık","Kıyma"],
        "ex":   ["Köfte","Döner","Burger","Sosis","Mantı","Hazır","Konserve"],
        "unit": "kg",
    },
    "Cubed Meat / Lamb Meat": {
        "cats": ["Dana Eti","Kuzu Eti"],
        "kw":   ["Kuşbaşı"],
        "ex":   ["Köfte","Döner","Sosis"],
        "unit": "kg",
    },
    "Chicken": {
        "cats": ["Piliç"],
        "kw":   ["Piliç","Baget","Kalçalı But","Kanat","Pirzola"],
        "ex":   ["Sosis","Salam","Sucuk","Füme","Nugget","Köfte","Döner",
                 "Şnitzel","Burger","Hazır","Acılı Çıtır","Çıtır","Dürüm"],
        "unit": "kg",
    },
    "Fish": {
        "cats": ["Mevsim Balıkları"],
        "kw":   ["Levrek","Hamsi","Çipura","Alabalık","İstavrit","Karadeniz"],
        "ex":   ["Füme","Marine","Somon","Karides","Jumbo","Mezgit"],
        "unit": "kg",
        "max_price_per_kg": 650,
    },
    "Eggs": {
        "cats": ["Yumurta"],
        "kw":   ["Yumurta"],
        "ex":   ["Bıldırcın","Balığı","Plastik","Sünger","Protein Tozu"],
        "unit": "piece",
    },
    # ── Legumes ───────────────────────────────────────────────────────
    "Dried Beans": {
        "cats": ["Fasulye"],
        "kw":   ["Fasulye"],
        "ex":   ["Pilaki","Haşlanmış","Konserve","Barbunya","Taze","Yeşil",
                 "Maş","Soya","Organik"],
        "unit": "kg",
        "max_price_per_kg": 400,
    },
    "Chickpeas": {
        "cats": ["Nohut"],
        "kw":   ["Nohut"],
        "ex":   ["Haşlanmış","Konserve","Cips","Pilav","Organik"],
        "unit": "kg",
        "max_price_per_kg": 500,
    },
    "Red Lentils": {
        "cats": ["Kırmızı Mercimek"],
        "kw":   ["Mercimek"],
        "ex":   ["Çorba","Organik","Makarna","Yeşil"],
        "unit": "kg",
        "max_price_per_kg": 300,
    },
    "Green Lentils": {
        "cats": ["Yeşil Mercimek"],
        "kw":   ["Mercimek"],
        "ex":   ["Çorba","Organik","Makarna","Kırmızı"],
        "unit": "kg",
        "max_price_per_kg": 300,
    },
    # ── Nuts — only kabuklu/whole nuts sold by kg ──────────────────────
    "Walnut / Hazelnut / Peanut": {
        "cats": ["Kabuklu Kuruyemiş"],
        "kw":   ["Ceviz Kabuklu","Ceviz Kg","Yer Fıstığı Kg"],
        "ex":   ["Badem","Kaju","Antep","Findik"],
        "unit": "kg",
        "max_price_per_kg": 500,
    },
    # ── Grains ────────────────────────────────────────────────────────
    "Bread":     {"cats": [], "kw": [], "ex": [], "unit": "kg"},   # Not stocked
    "Rice": {
        "cats": ["Baldo Pirinç","Osmancık Pirinç","Pilavlık Pirinç","İthal Pirinç"],
        "kw":   ["Pirinç"],
        "ex":   ["Gevreği","Sirke","Bebek","Sushi","Mama","Garnitür"],
        "unit": "kg",
        "max_price_per_kg": 400,
    },
    "Bulgur": {
        "cats": ["Pilavlık Bulgur","Köftelik Bulgur","Katkılı Bulgur"],
        "kw":   ["Bulgur"],
        "ex":   ["Organik","Çorbası","Pilavı"],
        "unit": "kg",
    },
    "Pasta": {
        "cats": ["Makarna"],
        "kw":   ["Makarna"],
        "ex":   ["Sosu","Tortellini","Ravioli","Taze Makarna","Lazanya",
                 "Çorba","Şehriye","Kedi","Erişte"],
        "unit": "kg",
    },
    "Flour": {
        "cats": ["Sade Un"],
        "kw":   ["Un"],
        "ex":   ["Galeta","Mısır","Nişasta","Glutensiz","Baklava","Nohut",
                 "Kek","Kurabiye","Pirinç","Böreklik","Siyez","Organik",
                 "Karışım"],
        "unit": "kg",
        "max_price_per_kg": 80,
    },
    "Semolina":  {"cats": [], "kw": [], "ex": [], "unit": "kg"},   # Not stocked
    # ── Fruits ────────────────────────────────────────────────────────
    "Apple": {
        "cats": ["Sert Meyveler"],
        "kw":   ["Elma"],
        "ex":   ["Suyu","Aromalı","Kurusu","Sirke"],
        "unit": "kg",
    },
    "Orange / Mandarin": {
        "cats": ["Narenciye"],
        "kw":   ["Portakal","Mandalina"],
        "ex":   ["Suyu","Aromalı","Sıkma"],
        "unit": "kg",
    },
    "Banana": {
        "cats": ["Egzotik Meyveler"],
        "kw":   ["Muz"],
        "ex":   ["Kurusu","Aromalı","Püresi"],
        "unit": "kg",
    },
    # ── Vegetables ────────────────────────────────────────────────────
    "Potato": {
        "cats": ["Patates, Soğan, Sarımsak"],
        "kw":   ["Patates"],
        "ex":   ["Tatlı","Organik","Mini","Püresi","Cips"],
        "unit": "kg",
    },
    "Onion": {
        "cats": ["Patates, Soğan, Sarımsak"],
        "kw":   ["Soğan"],
        "ex":   ["Arpacık","Organik","Püresi","Sarımsak"],
        "unit": "kg",
    },
    "Tomato": {
        "cats": ["Mevsim Sebzeleri"],
        "kw":   ["Domates"],
        "ex":   ["Salça","Kurutulmuş","Salkım","Kokteyl","Sosu","Pembe",
                 "Cherry","Rengi","Mini","Gökkuşağı","Tatlı","Domates Ürünleri"],
        "unit": "kg",
    },
    "Cucumber": {
        "cats": ["Mevsim Sebzeleri"],
        "kw":   ["Hıyar","Salatalık"],
        "ex":   ["Turşu","Silor"],
        "unit": "kg",
    },
    "Pepper": {
        "cats": ["Mevsim Sebzeleri"],
        "kw":   ["Biber"],
        "ex":   ["Pul","Toz","Turşu","Salça","Sos","Közlenmiş","Acı Şili",
                 "Padron","Kuru","Meksika"],
        "unit": "kg",
        "max_price_per_kg": 300,
    },
    "Eggplant / Zucchini": {
        "cats": ["Mevsim Sebzeleri"],
        "kw":   ["Patlıcan","Kabak"],
        "ex":   ["Közlenmiş","Turşu","Çekirdeği","Ezmesi","Sakız"],
        "unit": "kg",
    },
    "Carrot": {
        "cats": ["Mevsim Sebzeleri","Patates, Soğan, Sarımsak"],
        "kw":   ["Havuç"],
        "ex":   ["Suyu","Püresi","Mini","Kurutulmuş","Hazır","Salata",
                 "Kap Salata","Lahana"],
        "unit": "kg",
    },
    "Greens / Lettuce / Parsley": {
        "cats": ["Otlar, Yeşillikler"],
        "kw":   ["Marul","Maydanoz","Roka","Dereotu","Kıvırcık"],
        "ex":   [],
        "unit": "piece",
    },
    "Other Vegetables": {
        "cats": ["Egzotik Sebzeler","Mevsim Sebzeleri"],
        "kw":   ["Mantar","Lahana","Ispanak","Brokoli","Enginar","Kereviz","Pırasa"],
        "ex":   ["Konserve","Turşu","Zencefil","Zerdeçal","Tatlı","Patates",
                 "Domates","Hazır","Salata","Kap Salata","Shiitake"],
        "unit": "kg",
        "max_price_per_kg": 500,
    },
    # ── Oils ──────────────────────────────────────────────────────────
    "Sunflower Oil": {
        "cats": ["Ayçicek Yağı"],
        "kw":   ["Ayçiçek"],
        "ex":   ["Ton","Sardin","Sprey"],
        "unit": "ml_or_L",
    },
    "Olive Oil": {
        "cats": ["Sızma Zeytinyağı","Riviera Zeytinyağı"],
        "kw":   ["Zeytinyağı"],
        "ex":   ["Ton","Sabun","Sprey","Sardin","Teneke 5 L x"],
        "unit": "ml_or_L",
        "max_price_per_kg": 3000,
    },
    "Butter": {
        "cats": ["Tereyağı"],
        "kw":   ["Tereyağ","Tereyağı"],
        "ex":   ["Margarin","Bitkisel","Milföy","Bisküvi","Seker","Lezzeti"],
        "unit": "kg",
    },
    "Margarine": {
        "cats": ["Kase Margarin","Paket Margarin"],
        "kw":   ["Margarin"],
        "ex":   ["Tereyağ","Zeytinyağlı","Ekmeküstü"],
        "unit": "kg",
    },
    # ── Breakfast ─────────────────────────────────────────────────────
    "Olives": {
        "cats": ["Siyah Zeytin","Çizik Yeşil Zeytin","Özel Zeytinyağı",
                 "Biberli Yeşil Zeytin","Siyah Zeytin Ezmesi","Özel Yeşil Zeytin",
                 "Kokteyl Yeşil Zeytin"],
        "kw":   ["Zeytin"],
        "ex":   ["Yağı","Ezmesi","Sabun","Zeytinyağlı","Bisküvi","Kraker",
                 "Sandviç","Dolgulu","Sarma"],
        "unit": "kg",
    },
    # ── Other Food ────────────────────────────────────────────────────
    "Sugar": {
        "cats": ["Toz Şeker"],
        "kw":   ["Şeker"],
        "ex":   ["Küp","Esmer","Pudra","Vanilin","Kahverengi"],
        "unit": "kg",
    },
    "Tea": {
        "cats": ["Dökme Çay"],
        "kw":   ["Çay"],
        "ex":   ["Bitki","Soğuk","Meyve","Ihlamur","Papatya","Bergamot",
                 "Earl Grey","Poşet","Demlik","Yeşil","Nane","Form",
                 "Kuşburnu","Rezene","Melisa","Adaçayı","Makinesi"],
        "unit": "kg",
        "require_weight": True,
        "max_price_per_kg": 600,
    },
    "Tomato Paste": {
        "cats": ["Domates Salçası"],
        "kw":   ["Domates Salçası","Domates Salça"],
        "ex":   ["Biber","Acı","Köy","Organik"],
        "unit": "kg",
        "max_price_per_kg": 300,
    },
    "Jam": {
        "cats": ["Reçel"],
        "kw":   ["Reçel"],
        "ex":   ["Diabetik","Süt Reçeli","Ceviz","Kestane","Karamel",
                 "Çikolata","Sürülebilir"],
        "unit": "kg",
        "max_price_per_kg": 700,
    },
    "Honey": {
        "cats": ["Çiçek Balı","Çam Balı","Karışım Bal"],
        "kw":   ["Bal"],
        "ex":   ["Kabağı","Propolis","Bisküvi","Bar","Granola","Çikolata",
                 "Polen","Arısütü","Petek","Balmumu"],
        "unit": "kg",
        "max_price_per_kg": 4000,
    },
    "Molasses": {
        "cats": ["Pekmez"],
        "kw":   ["Pekmez"],
        "ex":   ["Tahin","Sucuk","Keçiboynuzu"],
        "unit": "kg",
    },
    "Salt": {
        "cats": ["Tuz"],
        "kw":   ["Tuz"],
        "ex":   ["Tuzlu","Tuzsuz","Turşu","Salamura","Himalaya","Limon",
                 "Zeytinli","Sos","Tuzluklu","Deniz Tuzu","Değirmenli",
                 "Kaya Tuzu","Sodyumu Azaltılmış","Sıvı"],
        "unit": "kg",
        "require_weight": True,
        "max_price_per_kg": 150,
    },
    "Average Spices": {
        "cats": ["Baharat"],
        "kw":   ["Karabiber","Pul Biber"],
        "ex":   ["Tane","Tuzluklu","Karışım","Harç","Cajun","Mangal",
                 "Izgara","Kanatlı","İtalyan","Koyun","Acı","Organik"],
        "unit": "kg",
        "require_weight": True,
        "max_price_per_kg": 1500,
    },
    "Linden / Herbal Tea": {
        "cats": ["Bitki Çayı"],
        "kw":   ["Ihlamur","Papatya"],
        "ex":   ["Adaçayı","Zencefil","Form","Kış","Rezene","Nane",
                 "Kuşburnu","Melisa","Soğuk","Kırmızı Meyve","Limon"],
        "unit": "piece",
        "require_weight": True,
    },
}

# Seasonal fruit: Hard Fruits + Exotic Fruits + Soft Fruits
# excluding staples (Elma, Portakal, Mandalina, Muz, Limon)
SEASONAL_FRUIT_CATS = ["Sert Meyveler","Egzotik Meyveler","Yumuşak Meyveler"]
SEASONAL_EXCLUDE = ["Elma","Portakal","Mandalina","Muz","Limon","Avokado",
                    "Ananas","Hindistan","Suyu","Kurusu","Aromalı",
                    "Demirhindi","Physalis","Pitahaya","Lime","Limes",
                    "Altın Çilek","Yer Kirazı","Yaban Mersini",
                    "Ahududu","Çağla","Erik Can","Yemeye Hazır"]

# ── 4. UTILITIES ────────────────────────────────────────
def extract_weight_g(name: str):
    m = re.search(r'(\d+[,.]?\d*)\s*(Kg|KG|kg)\b', name)
    if m:
        raw = m.group(1); sep = re.match(r'^(\d+)[,.](\d{3})$', raw)
        return float(sep.group(1)+sep.group(2))*1000 if sep else float(raw.replace(',','.'))*1000
    m = re.search(r'(\d+[,.]?\d*)\s*(G|Gr|GR|Gr\.)\b', name)
    if m:
        raw = m.group(1); sep = re.match(r'^(\d+)[,.](\d{3})$', raw)
        return float(sep.group(1)+sep.group(2)) if sep else float(raw.replace(',','.'))
    return None

def extract_volume_ml(name: str):
    n = re.sub(r'\bL\b', 'L', name, flags=re.IGNORECASE)
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
    if not rule['cats']:
        return {'unit_price': float('nan'), 'n_products': 0, 'matched_names': 'N/A'}

    sub = df[df['category'].isin(rule['cats'])].copy()

    if not rule['kw']:
        return {'unit_price': float('nan'), 'n_products': 0, 'matched_names': 'N/A'}

    mask = sub['name'].apply(
        lambda x: any(k.lower() in str(x).lower() for k in rule['kw'])
    )
    sub = sub[mask]
    for exc in rule['ex']:
        sub = sub[~sub['name'].str.contains(exc, case=False, na=False)]

    if sub.empty:
        return {'unit_price': float('nan'), 'n_products': 0, 'matched_names': '—'}

    unit  = rule['unit']
    req_w = rule.get('require_weight', False)
    min_p = rule.get('min_price_per_kg', 0)
    max_p = rule.get('max_price_per_kg', None)
    prices = []

    for _, row in sub.iterrows():
        name  = str(row['name'])
        price = float(row['shown_price'])
        is_gram = str(row['unit']) == 'GRAM'

        if unit == 'kg':
            if is_gram:
                # GRAM unit = price is already per-kg
                per_u = price
            else:
                w = extract_weight_g(name)
                if req_w and not w: continue
                per_u = price / (w / 1000) if w and w > 0 else price
            if per_u < min_p: continue
            if max_p and per_u > max_p: continue
            prices.append(per_u)

        elif unit == 'ml_or_L':
            if is_gram:
                prices.append(price)  # GRAM = per-kg already
            else:
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
        n[:45] + ('…' if len(n) > 45 else '') for n in sub['name'].tolist()
    )
    return {'unit_price': round(avg, 2), 'n_products': len(prices), 'matched_names': names}


def get_seasonal_fruit_price(df: pd.DataFrame) -> dict:
    sub = df[df['category'].isin(SEASONAL_FRUIT_CATS)].copy()
    for exc in SEASONAL_EXCLUDE:
        sub = sub[~sub['name'].str.contains(exc, case=False, na=False)]

    MAX_SEASONAL = 1000
    prices = []
    for _, row in sub.iterrows():
        name  = str(row['name'])
        price = float(row['shown_price'])
        is_gram = str(row['unit']) == 'GRAM'
        if is_gram:
            per_kg = price
        else:
            w = extract_weight_g(name)
            if not w:
                continue   # skip "Adet" items without parseable weight (per-piece ≠ per-kg)
            per_kg = price / (w / 1000)
        if per_kg <= MAX_SEASONAL:
            prices.append(per_kg)

    avg   = sum(prices) / len(prices) if prices else float('nan')
    names = '; '.join(n[:45] for n in sub['name'].tolist())
    return {'unit_price': round(avg, 2), 'n_products': len(prices), 'matched_names': names}

# ── 6. MONTHLY COMPUTATION ──────────────────────────────
def compute_hunger_threshold(csv_path: str, date_label: str) -> pd.DataFrame:
    df = pd.read_csv(csv_path, encoding='utf-8-sig')
    df = df.drop_duplicates(subset=['sku'])
    rows = []
    for category, product_label, unit_label, monthly_qty in FOOD_BASKET:
        if product_label == 'Seasonal Fruit':
            info = get_seasonal_fruit_price(df)
        else:
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
    print(f"  {date_label}  —  Hunger Threshold: ₺{total:,.2f}{na_note}")
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
print('  MONTHLY HUNGER THRESHOLD SUMMARY')
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
