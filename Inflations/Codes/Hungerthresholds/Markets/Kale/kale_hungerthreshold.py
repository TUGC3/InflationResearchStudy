
import re
import pandas as pd
from pathlib import Path

# ── 1. PATHS ────────────────────────────────────────────
BASE_DIR = "/Users/efeyildirim/Downloads/Marketler/Kale"

FILES = {
    "Mar-01 2026": f"{BASE_DIR}/kalemarketleri_prices_2026-03-01.csv",
    "Mar-30 2026": f"{BASE_DIR}/kalemarketleri_prices_2026-03-30.csv",
    "Apr 2026":    f"{BASE_DIR}/kalemarketleri_prices_2026-04-30.csv",
    "May 2026":    f"{BASE_DIR}/kalemarketleri_prices_2026-05-26.csv",
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
    "Milk": {
        "kat":  ["Süt, Kahvaltılık"],
        "kw":   ["Süt"],
        "ex":   ["Ayran","Kakaolu","Çilek","Muzlu","Aromalı","Soya","Badem","Yulaf",
                 "Kefir","Sütlü","Kaymak","Sütlaç","Kido","İçimino","Nesquik",
                 "Devam","Bebek","Krema","Süt Reçeli","Organik","Laktozsuz",
                 "Proteinli","200 ml","180 ml","Büyümix","Arı Sütü","Sahlep",
                 "Çocuk","Kaymak",
                "Tereyağ","Krem Peynir","Eritme","Sütaş Eritme","Sütaş Süzme Peynir","Sütaş Süzme Yoğurt","Sütaş Kaşar","Sütaş Labne","Sütaş Beyaz","Sütaş Yoğurt","Sütaş Meyve","Sütaş Light","Sütaş Örgü","Sütaş Çeçil","Teksüt Labne","Teksüt Kaşar","Teksüt Dilimli","Kinder Süt Dilimi","Kinder","Hüptirik"],
        "unit": "ml_or_L",
        "max_price_per_kg": 200,
    },
    "Yogurt": {
        "kat":  ["Süt, Kahvaltılık"],
        "kw":   ["Yoğurt"],
        "ex":   ["Meyveli","Organik","Kaymaklı","Çırpılmış","Laktozsuz","Çilek",
                 "Aromalı","Tava","Dip","Cips","Kefir","Bebek","Mama","Puding",
                 "Probiyotik","Fermente","Mix","Süzme","Danone","Activia"],
        "unit": "kg",
        "max_price_per_kg": 500,
    },
    "White Cheese": {
        "kat":  ["Süt, Kahvaltılık"],
        "kw":   ["Beyaz Peynir","Taze Peynir","Klasik Peynir"],
        "ex":   ["Kaşar","Lor","Dil","Örgü","Çeçil","Krem","Mozzarella","Labne",
                 "Tulum","Süzme","Laktozsuz","Tost","Kolot"],
        "unit": "kg",
    },
    "Kashar / Other Cheese": {
        "kat":  ["Süt, Kahvaltılık"],
        "kw":   ["Kaşar"],
        "ex":   ["Sandviç","Köfte","Poğaça","Bisküvi","Burger"],
        "unit": "kg",
    },
    "Minced Meat": {
        "kat":  ["Et, Tavuk"],
        "kw":   ["Dana Kıyma","Kıyma"],
        "ex":   ["Döner","Burger","Sosis","Köfte","Mantı","Börek","Pişmiş","Kalemar"],
        "unit": "kg",
    },
    "Cubed Meat / Lamb Meat": {
        "kat":  ["Et, Tavuk"],
        "kw":   ["Kuşbaşı"],
        "ex":   ["Döner","Köfte","Sosis"],
        "unit": "kg",
    },
    "Chicken": {
        "kat":  ["Et, Tavuk"],
        "kw":   ["Tavuk","Piliç","Gedik","Banvit","Erpiliç"],
        "ex":   ["Sosis","Salam","Sucuk","Füme","Nugget","Köfte","Döner","Kangal",
                 "Şnitzel","Burger","Hazır","Sarma"],
        "unit": "kg",
    },
    "Fish": {
        "kat":  ["Et, Tavuk"],
        "kw":   [], 
        "ex":   [],
        "unit": "kg",
    },
    "Eggs": {
        "kat":  ["Süt, Kahvaltılık"],
        "kw":   ["Yumurta"],
        "ex":   ["Bıldırcın","Kedi","Köpek","Waffle","Makarna","Bisküvi",
                 "Kinder","Çikolata","Ozmo"],
        "unit": "piece",
    },
    "Dried Beans": {
        "kat":  ["Genel Gıda"],
        "kw":   ["Kuru Fasulye","Dermason Fasulye","Şeker Fasulye"],
        "ex":   ["Konserve","Etli","Organik","1 g","Hazır","Konservesi"],
        "unit": "kg",
        "max_price_per_kg": 500,
    },
    "Chickpeas": {
        "kat":  ["Genel Gıda"],
        "kw":   ["Nohut"],
        "ex":   ["Konserve","Haşlanmış","Cipsi","Cips","Organik","1 g","Çorba",
                "Hazır","Nohutlu","Pilaki"],
        "unit": "kg",
        "max_price_per_kg": 400,
    },
    "Red Lentils": {
        "kat":  ["Genel Gıda"],
        "kw":   ["Kırmızı Mercimek"],
        "ex":   ["Çorba","Organik","1 g","Makarna","Erişte"],
        "unit": "kg",
        "max_price_per_kg": 300,
    },
    "Green Lentils": {
        "kat":  ["Genel Gıda"],
        "kw":   ["Yeşil Mercimek"],
        "ex":   ["Çorba","Organik","1 g","Makarna","Erişte","Haşlanmış"],
        "unit": "kg",
        "max_price_per_kg": 300,
    },
    "Walnut / Hazelnut / Peanut": {
        "kat":  ["Bisküvi, Kuruyemiş"],
        "kw":   ["Ceviz İçi Kg","Fındık İçi Kg","Yer Fıstığı Kg"],
        "ex":   [],
        "unit": "kg",
    },
    "Bread": {
        "kat":  ["Unlu Mamuller"],
        "kw":   ["Ekmek"],
        "ex":   ["Hamburger","Sandviç","Tost","Lavaş","Tortilla","Gevrek","Kızarmış",
                 "Grissini","Glutensiz","Kıtır","Börek","Poğaça","Kırıntısı",
                 "Ekmeküstü","Simidi","Simit"],
        "unit": "kg",
        "min_price_per_kg": 40,
        "max_price_per_kg": 600,
    },
    "Rice": {
        "kat":  ["Genel Gıda"],
        "kw":   ["Pirinç"],
        "ex":   ["Gevreği","Kek","Sirke","Patlağı","Unu","Organik","Sushi",
                 "Risotto","Bebek","Şehriye","Yufkası","Mama","Garnitürlü","Glutensiz Mısır Pirinçli Makarna","Glutensiz Risonı"],
        "unit": "kg",
        "max_price_per_kg": 350,
    },
    "Bulgur": {
        "kat":  ["Genel Gıda"],
        "kw":   ["Bulgur"],
        "ex":   ["Organik","Pilavı"],
        "unit": "kg",
    },
    "Pasta": {
        "kat":  ["Genel Gıda"],
        "kw":   ["Makarna"],
        "ex":   ["Sosu","Knorr","Tortellini","Lazanya","Peyniri","Kedi","Köpek",
                 "Şehriye","Çorba",
                "Erişte"],
        "unit": "kg",
    },
    "Flour": {
        "kat":  ["Unlu Mamuller"],
        "kw":   ["Un"],
        "ex":   ["Galeta","Mısır","Nişasta","Glutensiz","Baklava","Nohut","Kek",
                 "Kurabiye","Pirinç","İrmik","Böreklik","Baklavalık","Pidelik",
                 "Organik","Kurabiyesi","Eriş","Mis Un 25","Mis Un 10","Uno Super","Uno Tost","Uno Fırından","Uno Kuruvasan","Uno Grissuno","Uno Sandviç","Uno Geleneksel Lavaş","Uno Tam Buğday","Uno Pasta Tabanı","Uno Otantik","Uno Prenium","Uno Tandır","Uno Susamlı","Uno Denge","Uno Prenıum","Uno Lavaş","Untad Lavaş","Untad Ekmek","Untad Gurme","Untad Kepek"],
        "unit": "kg",
        "max_price_per_kg": 80,
    },
    "Semolina": {
        "kat":  ["Unlu Mamuller"],
        "kw":   ["İrmik"],
        "ex":   ["Helvası","Bebek","Organik","Un"],
        "unit": "kg",
    },
    "Apple": {
        "kat":  ["Meyve, Sebze"],
        "kw":   ["Elma"],
        "ex":   ["Suyu","Aromalı","Hindistan","Kurusu","Kek","Sirke","Granola"],
        "unit": "kg",
    },
    "Orange / Mandarin": {
        "kat":  ["Meyve, Sebze"],
        "kw":   ["Portakal","Mandalina"],
        "ex":   ["Suyu","Gazoz","Aromalı"],
        "unit": "kg",
    },
    "Banana": {
        "kat":  ["Meyve, Sebze"],
        "kw":   ["Muz"],
        "ex":   ["Püresi","Bebek","Aromalı","Kurusu"],
        "unit": "kg",
    },
    "Potato": {
        "kat":  ["Meyve, Sebze"],
        "kw":   ["Patates"],
        "ex":   ["Cips","Kroket","Börek","Püresi","Poğaça","Nuggets","Dondurulmuş",
                 "Kızartmalık"],
        "unit": "kg",
    },
    "Onion": {
        "kat":  ["Meyve, Sebze"],
        "kw":   ["Soğan"],
        "ex":   ["Taze","Arpacık","Yahnilik","Dondurulmuş","Tozu"],
        "unit": "kg",
    },
    "Tomato": {
        "kat":  ["Meyve, Sebze"],
        "kw":   ["Domates"],
        "ex":   ["Salça","Kurutulmuş","Konserve","Kokteyl","Sosu","Çeri"],
        "unit": "kg",
    },
    "Cucumber": {
        "kat":  ["Meyve, Sebze"],
        "kw":   ["Salatalık"],
        "ex":   ["Turşu","Silor"],
        "unit": "kg",
    },
    "Pepper": {
        "kat":  ["Meyve, Sebze"],
        "kw":   ["Biber"],
        "ex":   ["Pul","Toz","Turşu","Salça","Sos","Közlenmiş","Acı"],
        "unit": "kg",
    },
    "Eggplant / Zucchini": {
        "kat":  ["Meyve, Sebze"],
        "kw":   ["Patlıcan","Kabak"],
        "ex":   ["Közlenmiş","Turşu","Çekirdeği","Ezmesi"],
        "unit": "kg",
    },
    "Carrot": {
        "kat":  ["Meyve, Sebze"],
        "kw":   ["Havuç"],
        "ex":   ["Suyu","Püresi","Bebek","Mini"],
        "unit": "kg",
    },
    "Greens / Lettuce / Parsley": {
        "kat":  ["Meyve, Sebze"],
        "kw":   ["Marul","Maydanoz","Roka","Dereotu","Kıvırcık"],
        "ex":   [],
        "unit": "piece",
    },
    "Other Vegetables": {
        "kat":  ["Meyve, Sebze"],
        "kw":   ["Mantar","Lahana","Ispanak","Brokoli","Enginar","Kereviz","Pırasa"],
        "ex":   ["Konserve","Turşu","Kedi","Köpek","Sarması","Suyu"],
        "unit": "kg",
    },
    "Sunflower Oil": {
        "kat":  ["Genel Gıda"],
        "kw":   ["Ayçiçek Yağı"],
        "ex":   ["Teneke","Sprey","Ton Balık"],
        "unit": "ml_or_L",
    },
    "Olive Oil": {
        "kat":  ["Genel Gıda"],
        "kw":   ["Zeytinyağı"],
        "ex":   ["Ton Balık","Sabun","Sprey","Şampuan","Losyon","Bebek","Konserve"],
        "unit": "ml_or_L",
    },
    "Butter": {
        "kat":  ["Süt, Kahvaltılık"],
        "kw":   ["Tereyağ","Tereyağı"],
        "ex":   ["Margarin","Bitkisel","Milföy","Bisküvi","Şeker","Yemeklik","Becel","Sana Tereyağı Lezzeti","Tereyağı Lezzeti"],
        "unit": "kg",
    },
    "Margarine": {
        "kat":  ["Süt, Kahvaltılık"],
        "kw":   ["Margarin"],
        "ex":   ["Şişe","Ekmeküstü","Tereyağ"],
        "unit": "kg",
    },
    "Olives": {
        "kat":  ["Süt, Kahvaltılık"],
        "kw":   ["Zeytin"],
        "ex":   ["Yağ","Ezmesi","Sabun","Zeytinyağlı","Bisküvi","Kraker",
                 "Grissini","Köfte","Sandviç","Teneke"],
        "unit": "kg",
    },
    "Sugar": {
        "kat":  ["Genel Gıda"],
        "kw":   ["Toz Şeker"],
        "ex":   ["Küp","Esmer","Vanilin","Kahverengi","Pudra"],
        "unit": "kg",
    },
    "Tea": {
        "kat":  ["İçecekler"],
        "kw":   ["Çay"],
        "ex":   ["Soğuk","Meyve","Ihlamur","Papatya","Bitki","Aromalı",
                 "Makinesi","Seti","Bardağı","Ayran","Limon","Şeftali",
                 "Yeşil Çay","Beyaz Çay","Ada Çayı","Melisa","Kuşburnu",
                 "Rezene","Zencefil","Karanfil","Ekinezya","Kayısılı",
                 "Kiraz","Hatmi","Form","Soda","Elmalı"],
        "unit": "kg",
        "require_weight": True,
        "max_price_per_kg": 500,
    },
    "Tomato Paste": {
        "kat":  ["Genel Gıda"],
        "kw":   ["Domates Salçası","Domates Salça"],
        "ex":   ["Biber","Acı Biber"],
        "unit": "kg",
    },
    "Jam": {
        "kat":  ["Süt, Kahvaltılık"],
        "kw":   ["Reçel"],
        "ex":   ["Diabetik","Süt Reçeli","Kestane","Ceviz","Likapa"],
        "unit": "kg",
    },
    "Honey": {
        "kat":  ["Süt, Kahvaltılık"],
        "kw":   ["Bal"],
        "ex":   ["Kabağı","Reçel","Propolis","Bisküvi","Bar","Pasta","Granola",
                 "Çikolata","Kedi","Köpek","Balık","Balsam","Balzamik","Polen",
                 "Nesfit","Müsli","Gevrek","Çotanak","Fındık Ezmesi","Muratbey Kaymaklı Ballı"],
        "unit": "kg",
        "max_price_per_kg": 3000,
    },
    "Molasses": {
        "kat":  ["Süt, Kahvaltılık"],
        "kw":   ["Pekmez"],
        "ex":   ["Tahin","Sucuk","Keçiboynuzu"],
        "unit": "kg",
    },
    "Salt": {
        "kat":  ["Genel Gıda"],
        "kw":   ["Tuz"],
        "ex":   ["Tuzlu","Tuzsuz","Bulaşık","Himalaya","Limon","Zeytinli",
                 "Bisküvi","Kurabiye","Simit","Ekmek","Sos","Deterjan","Deniz"],
        "unit": "kg",
        "require_weight": True,
        "max_price_per_kg": 150,
    },
    "Average Spices": {
        "kat":  ["Genel Gıda"],
        "kw":   ["Baharat","Karabiber","Pul Biber"],
        "ex":   ["Cips","Kraker","Bisküvi","Çikolata","Kedi","Köpek",
                 "Salam","Sucuk","Fesleğen","Köfte","Hazır","Garlic"],
        "unit": "kg",
        "require_weight": True,
        "max_price_per_kg": 1000,
    },
    "Linden / Herbal Tea": {
        "kat":  ["İçecekler"],
        "kw":   ["Ihlamur","Papatya"],
        "ex":   ["Rezene","Nane","Yeşil Çay","Form","Kış","Adaçayı","Zencefil",
                 "Kuşburnu","Melisa","Makinesi","Seti","Soğuk"],
        "unit": "piece",
        "require_weight": True,
    },
}

# Seasonal fruit keywords and excludes
SEASONAL_FRUIT_KW = ["Armut","Çilek","Greyfurt","Kivi","Nar","Karpuz","Erik",
                     "Kiraz","Vişne","Şeftali","Kayısı","Üzüm","İncir","Dut",
                     "Mango","Ananas","Nektarin","Kavun","Ayva","Muşmula"]
SEASONAL_STAPLE_EX = ["Elma","Portakal","Mandalina","Muz","Limon","Avokado",
                      "Domates","Salatalık","Biber","Patlıcan","Kabak","Patates",
                      "Havuç","Soğan","Marul","Maydanoz","Roka","Dereotu","Lahana",
                      "Mantar","Ispanak","Brokoli","Enginar","Kereviz","Pırasa",
                      "Turp","Sarımsak","Zencefil","Pancar","Nane","Semizotu",
                      "Pazı","Arpacık","Hindistan","Kivi","Adet"]

# ── 4. UTILITIES ────────────────────────────────────────
def parse_price(s: str) -> float:
    """Handle both decimal comma '89,90' and thousands comma '1,200'."""
    s = str(s).strip()
    m = re.match(r'^(\d{1,3}),(\d+)$', s)
    if m:
        after = m.group(2)
        if len(after) == 2:           # "89,90" → decimal
            return float(s.replace(',', '.'))
        else:                          # "1,200" → thousands
            return float(s.replace(',', ''))
    # Fallback: strip thousands dots, replace decimal comma
    s = re.sub(r'\.(?=\d{3})', '', s)
    return float(s.replace(',', '.'))

def extract_weight_g(name: str):
    m = re.search(r'(\d+[,.]?\d*)\s*(kg|Kg|KG|gr|Gr|GR|g)\b', name)
    if m:
        v = float(m.group(1).replace(',', '.'))
        return v * 1000 if m.group(2).lower() == 'kg' else v
    return None

def extract_volume_ml(name: str):
    n = re.sub(r'\blt\b', 'L', name, flags=re.IGNORECASE)
    n = re.sub(r'\blitre\b', 'L', n, flags=re.IGNORECASE).upper()
    mp = re.search(r'(\d+)[xX](\d+[,.]?\d*)\s*(ML|L)\b', n)
    if mp:
        c = int(mp.group(1)); e = float(mp.group(2).replace(',', '.'))
        return c * e * (1000 if mp.group(3) == 'L' else 1)
    m = re.search(r'(\d+[,.]?\d*)\s*(ML|L)\b', n)
    if m:
        v = float(m.group(1).replace(',', '.'))
        return v * 1000 if m.group(2) == 'L' else v
    return None

def extract_piece_count(name: str):
    # Handle "30lu", "30'lu", "30 lu", "15 li", "15li" etc.
    m = re.search(r"(\d+)\s*['\u2019]?\s*(LU|L\u0130|LI|li|lu)\b", name, re.IGNORECASE)
    if m: return int(m.group(1))
    m2 = re.search(r'(\d+)\s*[Aa]det', name)
    if m2: return int(m2.group(1))
    m3 = re.search(r'(\d+)\s*[Ll][Ii]\b', name)
    if m3: return int(m3.group(1))
    return None

def is_sold_by_kg(name: str) -> bool:
    # True if name ends with 'Kg' with no preceding number (price is per-kg already)
    return bool(re.search(r'(?<!\d)\s*[Kk][Gg]\.?\s*$', name.strip()))

# ── 5. UNIT PRICE CALCULATOR ────────────────────────────
def get_unit_price(df: pd.DataFrame, product_label: str) -> dict:
    rule = MATCH_RULES[product_label]
    sub  = df[df['kategori'].isin(rule['kat'])].copy()

    if not rule['kw']:
        return {'unit_price': float('nan'), 'n_products': 0, 'matched_names': 'N/A'}

    mask = sub['product_name'].apply(
        lambda x: any(k.lower() in str(x).lower() for k in rule['kw'])
    )
    sub = sub[mask]
    for exc in rule['ex']:
        sub = sub[~sub['product_name'].str.contains(exc, case=False, na=False)]

    if sub.empty:
        return {'unit_price': float('nan'), 'n_products': 0, 'matched_names': '—'}

    unit  = rule['unit']
    req_w = rule.get('require_weight', False)
    min_p = rule.get('min_price_per_kg', 0)
    max_p = rule.get('max_price_per_kg', None)
    prices = []

    for _, row in sub.iterrows():
        name  = str(row['product_name'])
        price = parse_price(row['product_price'])

        if unit == 'kg':
            if is_sold_by_kg(name):
                per_u = price
            else:
                w = extract_weight_g(name)
                if req_w and not w:
                    continue
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
                per_sachet = price / cnt
                if product_label == 'Linden / Herbal Tea':
                    prices.append(per_sachet / 0.002)
                else:
                    prices.append(per_sachet)
            elif req_w:
                continue
            else:
                prices.append(price)

    avg   = sum(prices) / len(prices) if prices else float('nan')
    names = '; '.join(
        n[:45] + ('…' if len(n) > 45 else '') for n in sub['product_name'].tolist()
    )
    return {'unit_price': round(avg, 2), 'n_products': len(prices), 'matched_names': names}


def get_seasonal_fruit_price(df: pd.DataFrame) -> dict:
    sub = df[df['kategori'] == 'Meyve, Sebze'].copy()
    sub = sub[sub['product_name'].apply(
        lambda x: any(kw.lower() in str(x).lower() for kw in SEASONAL_FRUIT_KW)
    )]
    for exc in SEASONAL_STAPLE_EX:
        sub = sub[~sub['product_name'].str.contains(exc, case=False, na=False)]

    MAX_SEASONAL = 800
    prices = []
    for _, row in sub.iterrows():
        name  = str(row['product_name'])
        price = parse_price(row['product_price'])
        if is_sold_by_kg(name):
            per_kg = price
        else:
            w = extract_weight_g(name)
            per_kg = price / (w / 1000) if w and w > 0 else price
        if per_kg <= MAX_SEASONAL:
            prices.append(per_kg)

    avg   = sum(prices) / len(prices) if prices else float('nan')
    names = '; '.join(n[:45] for n in sub['product_name'].tolist())
    return {'unit_price': round(avg, 2), 'n_products': len(prices), 'matched_names': names}

# ── 6. MONTHLY COMPUTATION ──────────────────────────────
def compute_hunger_threshold(csv_path: str, date_label: str) -> pd.DataFrame:
    df = pd.read_csv(csv_path, encoding='utf-8-sig', dtype={'product_price': str})
    df = df.drop_duplicates(subset=['product_name'])
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
