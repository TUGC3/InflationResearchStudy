"""
Hunger Threshold Calculator — Hapeloglu Market
==============================================================
Basket: Presentation slide 8 — family of 4, monthly quantities.

CSV format: consistent across all files
  Columns: Product Name, Product Cost (float), category, ...
  Price: already float, per-kg for items with "Kg/kg" in name,
         per-piece for items with "Adet" or no unit,
         pack price for items with weight in name (e.g. "500 g").
  Categories: Produce (Meyve/Sebze) | Meat/Poultry/Fish | Dairy/Breakfast |
              Staple Food | Bakery | Beverages | Snacks |
              Bebek | Deterjan, Temizlik | Evcil Hayvan | ...
"""

import re
import pandas as pd
from pathlib import Path

# ── 1. PATHS ────────────────────────────────────────────
BASE_DIR = "/Users/efeyildirim/Downloads/Marketler/Hapeloglu"

FILES = {
    "Feb-24 2026": f"{BASE_DIR}/hapeloglu_2026-02-24.csv",
    "Feb-28 2026": f"{BASE_DIR}/hapeloglu_2026-02-28.csv",
    "Mar 2026":    f"{BASE_DIR}/hapeloglu_2026-03-31.csv",
    "Apr 2026":    f"{BASE_DIR}/hapeloglu_2026-04-30.csv",
    "May 2026":    f"{BASE_DIR}/hapeloglu_2026-05-26.csv",
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
# Notes on Hapeloglu naming:
#   "Elma Golden kg" → price is per-kg already (is_per_kg=True)
#   "Ekmek 250 g"    → price is pack price, weight=250g → normalise to per-kg
#   "Marul Adet"     → price is per-piece
#   "Mandalina"      → no unit → treat as per-kg (market standard for loose produce)

MATCH_RULES = {
    # ── Dairy ─────────────────────────────────────────────────────────
    "Milk": {
        "kat":  ["Süt, Kahvaltılık"],
        "kw":   ["Süt"],
        "ex":   ["Arı Sütü","Kakaolu","Çilek","Muzlu","Aromalı","Soya","Badem","Yulaf",
                 "Kefir","Ayran","Sütlü","Kaymak","Sütlaç","Kido","İçimino","Nesquik",
                 "Devam","Bebek","Krema","Süt Reçeli","Organik","Yüksek Protein",
                 "Büyümix","Laktozsuz","Yemeklik Yağ","Pastorize Süt 200","200 Ml",
                "Tereyağ","Krem Peynir","Eritme","Sütaş Beyaz","Sütaş Dilimli Tost","Sütaş Kaşar","Sütaş Labne","Sütaş Süzme","Sütaş Üçgen","Sütaş Eritme","Sütaş Orman","Teksüt Beyaz","Teksüt Dilimli Kaşar","Teksüt Labne","Teksüt Kaşar","Teksüt Rende","Teksüt Lor","Teksüt Tereyağı","Yeşil Mavi Rize Ömür Tereyağı"],
        "unit": "ml_or_L",
        "max_price_per_kg": 200,
    },
    "Yogurt": {
        "kat":  ["Süt, Kahvaltılık"],
        "kw":   ["Yoğurt"],
        "ex":   ["Meyveli","Organik","Kaymaklı","Çırpılmış","Laktozsuz","Çilek","Aromalı",
                 "Tava","Dip","Cips","Kefir","Bebek","Mama","Puding","Light","Probiyotik",
                 "Fermente","Kayısılı","Sarımsaklı"],
        "unit": "kg",
    },
    "White Cheese": {
        "kat":  ["Süt, Kahvaltılık"],
        "kw":   ["Beyaz Peynir","Klasik Peynir","Taze Peynir"],
        "ex":   ["Kaşar","Lor","Dil","Örgü","Çeçil","Krem","Mozzarella","Labne",
                 "Tulum","Süzme","Laktozsuz","Sepetli","Tost"],
        "unit": "kg",
    },
    "Kashar / Other Cheese": {
        "kat":  ["Süt, Kahvaltılık"],
        "kw":   ["Kaşar"],
        "ex":   ["Sandviç","Köfte","Poğaça","Bisküvi","Burger"],
        "unit": "kg",
    },
    "Minced Meat": {
        "kat":  ["Et, Tavuk, Balık"],
        "kw":   ["Dana Kıyma","Kıyma"],
        "ex":   ["Döner","Burger","Sosis","Köfte","Mantı","Börek","Pişmiş"],
        "unit": "kg",
    },
    "Cubed Meat / Lamb Meat": {
        "kat":  ["Et, Tavuk, Balık"],
        "kw":   ["Kuşbaşı","Dana Kuşbaşı","Kuzu Kuşbaşı"],
        "ex":   ["Döner","Köfte","Sosis"],
        "unit": "kg",
    },
    "Chicken": {
        "kat":  ["Et, Tavuk, Balık"],
        "kw":   ["Piliç","Şenpiliç","Şen Piliç"],
        "ex":   ["Sosis","Salam","Sucuk","Füme","Nugget","Köfte","Döner","Kangal",
                 "Parmak","Şnitzel","Burger","Izgaralık Kanat","Ciğer","Soslu"],
        "unit": "kg",
    },
    "Fish": {
        "kat":  ["Et, Tavuk, Balık"],
        "kw":   ["Levrek Kg","Hamsi Kg","Çupra Kg","Somon Kg","Alabalık Kg",
                 "Levrek kg","Hamsi kg","Çupra kg","Somon kg","Alabalık kg"],
        "ex":   ["Kedi","Köpek","Konserve","Ton","Finger","Çubuk","Füme"],
        "unit": "kg",
    },
    "Eggs": {
        "kat":  ["Süt, Kahvaltılık"],
        "kw":   ["Yumurta"],
        "ex":   ["Bıldırcın","Kedi","Köpek","Waffle","Makarna","Bisküvi","Organik",
                 "Kinder","Çikolata","Sürpriz","Ozmo"],
        "unit": "piece",
    },
    # ── Legumes ───────────────────────────────────────────────────────
    "Dried Beans": {
        "kat":  ["Temel Gıda"],
        "kw":   ["Kuru Fasulye","Dermason Fasulye"],
        "ex":   ["Konserve","Etli","Organik","1 g","Hazır"],
        "unit": "kg",
    },
    "Chickpeas": {
        "kat":  ["Temel Gıda"],
        "kw":   ["Nohut"],
        "ex":   ["Konserve","Haşlanmış","Cipsi","Cips","Organik","1 g","Çorba","Pilav",
                "Pilaki","Hazır"],
        "unit": "kg",
    },
    "Red Lentils": {
        "kat":  ["Temel Gıda"],
        "kw":   ["Kırmızı Mercimek"],
        "ex":   ["Çorba","Organik","1 g","Makarna","Erişte"],
        "unit": "kg",
    },
    "Green Lentils": {
        "kat":  ["Temel Gıda"],
        "kw":   ["Yeşil Mercimek"],
        "ex":   ["Çorba","Organik","1 g","Makarna","Erişte","Haşlanmış",
                "Hazır","Pratik"],
        "unit": "kg",
    },
    # ── Nuts ──────────────────────────────────────────────────────────
    "Walnut / Hazelnut / Peanut": {
        "kat":  ["Atıştırmalık"],
        "kw":   ["Ceviz İçi","Fındık İçi","Yer Fıstığı"],
        "ex":   ["Ezmesi","Kreması","Çikolata","Cips","Soslu","Aromalı","Baklava",
                 "Bisküvi","Granola","Bar","Protein","Gofret"],
        "unit": "kg",
    },
    # ── Grains ────────────────────────────────────────────────────────
    "Bread": {
        "kat":  ["Fırın, Pastane"],
        "kw":   ["Ekmek"],
        "ex":   ["Hamburger","Sandviç","Tost","Lavaş","Tortilla","Gevrek","Kızarmış",
                 "Grissini","Glutensiz","Kıtır","Börek","Poğaça","Kırıntısı","Ekmeküstü"],
        "unit": "kg",
        "min_price_per_kg": 40,
        "max_price_per_kg": 500,
    },
    "Rice": {
        "kat":  ["Temel Gıda"],
        "kw":   ["Pirinç"],
        "ex":   ["Gevreği","Kek","Sirke","Patlağı","Unu","Organik","Sushi",
                 "Risotto","Bebek","Şehriye","Yufkası","Mama","Garnitürlü","Pratik Hazır Yemek","Basmati Pirinç Pilavı","Mısır & Pirinç Rısonı","Mısır Pirinç Elbow","Rısonı","Risonı"],
        "unit": "kg",
        "max_price_per_kg": 250,
    },
    "Bulgur": {
        "kat":  ["Temel Gıda"],
        "kw":   ["Bulgur"],
        "ex":   ["Organik","Pilavı"],
        "unit": "kg",
    },
    "Pasta": {
        "kat":  ["Temel Gıda"],
        "kw":   ["Makarna"],
        "ex":   ["Sosu","Knorr","Tortellini","Lazanya","Peyniri","Kedi","Köpek",
                 "Şehriye",
                "Erişte"],
        "unit": "kg",
    },
    "Flour": {
        "kat":  ["Fırın, Pastane", "Temel Gıda"],
        "kw":   ["Ak Un","Sinangil Un","Söke Un","Ulusoy Un","Yüksel Un",
                 "Hutoğlu Buğday Un","Misun Buğday Un","Sinangil Buğday Un",
                 "Buğday Unu","Misun Un"],
        "ex":   ["Galeta","Mısır","Nişasta","Glutensiz","Keçiboynuzu","Siyez",
                 "Kepekli","Böreklik"],
        "unit": "kg",
        "max_price_per_kg": 100,
    },
    "Semolina": {
        "kat":  ["Fırın, Pastane"],
        "kw":   ["İrmik","Semolina"],
        "ex":   ["Helvası","Bebek","Organik","Un"],
        "unit": "kg",
    },
    # ── Fruits ────────────────────────────────────────────────────────
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
    # ── Vegetables ────────────────────────────────────────────────────
    "Potato": {
        "kat":  ["Meyve, Sebze"],
        "kw":   ["Patates"],
        "ex":   ["Cips","Kroket","Börek","Püresi","Poğaça","Nuggets","Dondurulmuş",
                 "Kızartmalık","Çuval"],
        "unit": "kg",
    },
    "Onion": {
        "kat":  ["Meyve, Sebze"],
        "kw":   ["Soğan"],
        "ex":   ["Taze","Arpacık","Mor","Yahnilik","Dondurulmuş","Tozu"],
        "unit": "kg",
    },
    "Tomato": {
        "kat":  ["Meyve, Sebze"],
        "kw":   ["Domates"],
        "ex":   ["Salça","Kurutulmuş","Konserve","Kokteyl","Sosu"],
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
        "ex":   ["Pul","Toz","Turşu","Salça","Sos","Közlenmiş"],
        "unit": "kg",
    },
    "Eggplant / Zucchini": {
        "kat":  ["Meyve, Sebze"],
        "kw":   ["Patlıcan","Kabak"],
        "ex":   ["Közlenmiş","Turşu","Çekirdeği","Ezmesi","Dolmalık Kabak"],
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
        "kw":   ["Marul","Maydanoz","Roka","Dereotu","Semizotu","Nane Adet",
                 "Taze Soğan","Pazı"],
        "ex":   [],
        "unit": "piece",
    },
    "Other Vegetables": {
        "kat":  ["Meyve, Sebze"],
        "kw":   ["Mantar","Lahana","Ispanak","Brokoli","Enginar","Kereviz","Pırasa"],
        "ex":   ["Konserve","Turşu","Kedi","Köpek","Sarması","Suyu"],
        "unit": "kg",
    },
    # ── Oils ──────────────────────────────────────────────────────────
    "Sunflower Oil": {
        "kat":  ["Temel Gıda"],
        "kw":   ["Ayçiçek Yağı"],
        "ex":   ["Teneke","Sprey","Ton Balık"],
        "unit": "ml_or_L",
    },
    "Olive Oil": {
        "kat":  ["Temel Gıda"],
        "kw":   ["Zeytinyağı","Zeytinyağı"],
        "ex":   ["Ton Balık","Sabun","Sprey","Şampuan","Losyon","Bebek","Konserve",
                 "Yağlı","Zeytinyağlı"],
        "unit": "ml_or_L",
    },
    "Butter": {
        "kat":  ["Süt, Kahvaltılık"],
        "kw":   ["Tereyağ","Tereyağı"],
        "ex":   ["Margarin","Bitkisel","Milföy","Bisküvi","Şeker","Yemeklik Yağ",
                 "Bitter Yemeklik","Helva","Çekme Helva"],
        "unit": "kg",
    },
    "Margarine": {
        "kat":  ["Süt, Kahvaltılık"],
        "kw":   ["Margarin"],
        "ex":   ["Şişe","Ekmeküstü","Tereyağ"],
        "unit": "kg",
    },
    # ── Breakfast ─────────────────────────────────────────────────────
    "Olives": {
        "kat":  ["Süt, Kahvaltılık"],
        "kw":   ["Zeytin"],
        "ex":   ["Yağ","Ezmesi","Sabun","Zeytinyağlı","Bisküvi","Kraker",
                 "Grissini","Köfte","Sandviç","Izgara"],
        "unit": "kg",
    },
    # ── Other Food ────────────────────────────────────────────────────
    "Sugar": {
        "kat":  ["Temel Gıda"],
        "kw":   ["Toz Şeker","Açık Toz Şeker"],
        "ex":   ["Küp","Esmer","Vanilin","Kahverengi","Pudra"],
        "unit": "kg",
    },
    "Tea": {
        "kat":  ["İçecek"],
        "kw":   ["Çay"],
        "ex":   ["Bitki","Soğuk","Meyve","Ihlamur","Papatya","'lü","'li",
                 "Aromalı","Makinesi","Saati","Bardağı","Soda","Elmalı",
                 "Böğürtlen","Nane","Yeşil","Mistik","Ada Çayı",
                 "Zencefil","Maydanoz","Seti","Takımı"],
        "unit": "kg",
        "require_weight": True,
        "max_price_per_kg": 400,
    },
    "Tomato Paste": {
        "kat":  ["Temel Gıda"],
        "kw":   ["Domates Salçası","Domates Salça"],
        "ex":   ["Biber","Acı Biber"],
        "unit": "kg",
    },
    "Jam": {
        "kat":  ["Süt, Kahvaltılık"],
        "kw":   ["Reçel"],
        "ex":   ["Diabetik","Süt Reçeli","Kestane","Ceviz"],
        "unit": "kg",
    },
    "Honey": {
        "kat":  ["Süt, Kahvaltılık"],
        "kw":   ["Bal"],
        "ex":   ["Kabağı","Reçel","Propolis","Bisküvi","Bar","Pasta","Granola",
                 "Çikolata","Kedi","Köpek","Balık","Balsam","Balzamik","Polen",
                 "Arı Sütü","Petek Balı","Arı Poleni","Pekmez","Üzüm","Dut","Balbaşı Üzüm","Limonata","Şampuan","Krem","Cheerios","Nesfit","Cornflakes","Gevrek","Ballı Mısır","Çotanak","Fındık Ezmesi","Ballı Fındık"],
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
        "kat":  ["Temel Gıda"],
        "kw":   ["Tuz"],
        "ex":   ["Tuzlu","Tuzsuz","Bulaşık","Himalaya","Limon","Zeytinli",
                 "Bisküvi","Kurabiye","Turşu","Salamura","Sos","Deterjan",
                 "Sabun","Kaya","Öğütme","Deniz","Sofrada","Tuzluklu",
                 "Sodyumu","Az Tuzlu","Kişisel","Losyon","Krem","Şampuan"],
        "unit": "kg",
        "require_weight": True,
        "max_price_per_kg": 100,
    },
    "Average Spices": {
        "kat":  ["Temel Gıda"],
        "kw":   ["Baharat","Karabiber","Pul Biber"],
        "ex":   ["Cips","Kraker","Bisküvi","Çikolata","Kedi","Köpek",
                 "Salam","Sucuk","Fesleğen","Baklava","Köfte","Hazır","Sarımsak Tozu",
                "Noodle","İndomie","Indomie","Linguine","Knorr Çeşni","Çeşni Kajun","Baharatlı Patates"],
        "unit": "kg",
        "require_weight": True,
        "max_price_per_kg": 750,
    },
    "Linden / Herbal Tea": {
        "kat":  ["İçecek"],
        "kw":   ["Ihlamur","Papatya Çayı"],
        "ex":   ["Adaçayı","Ekinezya","Karışık","Yaprağı Kg","Makinesi",
                 "Seti","Soguk","Ada Çayı","Zencefil","Yüz Otu"],
        "unit": "piece",
        "require_weight": True,
    },
}

# Seasonal fruit: Meyve,Sebze items sold by kg that aren't staples
SEASONAL_FRUIT_KW = ["Armut","Çilek","Greyfurt","Kivi","Nar","Karpuz","Erik",
                     "Kiraz","Vişne","Şeftali","Kayısı","Üzüm","İncir","Dut",
                     "Mango","Ananas","Nar","Nektarin","Kavun"]
SEASONAL_STAPLE_EX = ["Elma","Portakal","Mandalina","Muz","Limon","Avokado",
                      "Domates","Salatalık","Biber","Patlıcan","Kabak","Patates",
                      "Havuç","Soğan","Marul","Maydanoz","Roka","Dereotu","Lahana",
                      "Mantar","Ispanak","Brokoli","Enginar","Kereviz","Pırasa",
                      "Turp","Sarımsak","Zencefil","Pancar","Nane","Semizotu",
                      "Pazı","Arpacık","Hindistan","Kivi","Adet"]

# ── 4. UTILITIES ────────────────────────────────────────
def extract_weight_g(name: str):
    """Extract weight in grams from product name."""
    # Patterns: "500 g", "500 Gr", "1 kg", "2 Kg", "1.5 kg"
    m = re.search(r'(\d+[,.]?\d*)\s*(kg|Kg|KG|gr|Gr|GR|g)\b', name)
    if m:
        v = float(m.group(1).replace(',', '.'))
        return v * 1000 if m.group(2).lower() == 'kg' else v
    return None

def extract_volume_ml(name: str):
    """Extract volume in ml from product name."""
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
    """Extract piece count from product name."""
    m = re.search(r"(\d+)['\u2019]?(LU|Lİ|LI|li|lu)\b", name, re.IGNORECASE)
    if m: return int(m.group(1))
    m2 = re.search(r'(\d+)\s*[Aa]det', name)
    if m2: return int(m2.group(1))
    m3 = re.search(r'(\d+)\s*[Ll][Ii]\b', name)
    if m3: return int(m3.group(1))
    return None

def is_sold_by_kg(name: str) -> bool:
    """True if product name ends with or contains 'Kg/kg' without a preceding number
    (meaning the price IS per-kg, not a pack weight)."""
    # e.g. "Elma Golden kg", "Soğan Kg" — price already per-kg in name
    return bool(re.search(r'\b[Kk][Gg]\.?\s*$', name.strip()))

# ── 5. UNIT PRICE CALCULATOR ────────────────────────────
def get_unit_price(df: pd.DataFrame, product_label: str) -> dict:
    rule = MATCH_RULES[product_label]

    sub = df[df['category'].isin(rule['kat'])].copy()

    if not rule['kw']:
        return {'unit_price': float('nan'), 'n_products': 0, 'matched_names': 'N/A'}

    mask = sub['Product Name'].apply(
        lambda x: any(k.lower() in str(x).lower() for k in rule['kw'])
    )
    sub = sub[mask]
    for exc in rule['ex']:
        sub = sub[~sub['Product Name'].str.contains(exc, case=False, na=False)]

    if sub.empty:
        return {'unit_price': float('nan'), 'n_products': 0, 'matched_names': '—'}

    unit  = rule['unit']
    req_w = rule.get('require_weight', False)
    min_p = rule.get('min_price_per_kg', 0)
    max_p = rule.get('max_price_per_kg', None)
    prices = []

    for _, row in sub.iterrows():
        name  = str(row['Product Name'])
        price = float(row['Product Cost'])

        if unit == 'kg':
            if is_sold_by_kg(name):
                # Items like "Soğan Kg" — unit price already per-kg, no weight parse needed
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
                continue  # require parseable count
            else:
                prices.append(price)

    avg   = sum(prices) / len(prices) if prices else float('nan')
    names = '; '.join(
        n[:45] + ('…' if len(n) > 45 else '') for n in sub['Product Name'].tolist()
    )
    return {'unit_price': round(avg, 2), 'n_products': len(prices), 'matched_names': names}


def get_seasonal_fruit_price(df: pd.DataFrame) -> dict:
    sub = df[df['category'] == 'Meyve, Sebze'].copy()

    # Keep only items matching known fruit keywords
    sub = sub[sub['Product Name'].apply(
        lambda x: any(kw.lower() in str(x).lower() for kw in SEASONAL_FRUIT_KW)
    )]
    # Exclude staples and non-fruit items
    for exc in SEASONAL_STAPLE_EX:
        sub = sub[~sub['Product Name'].str.contains(exc, case=False, na=False)]

    MAX_SEASONAL = 600
    prices = []
    for _, row in sub.iterrows():
        name  = str(row['Product Name'])
        price = float(row['Product Cost'])
        if is_sold_by_kg(name) or not extract_weight_g(name):
            # Sold by kg → price is per-kg
            per_kg = price
        else:
            w = extract_weight_g(name)
            per_kg = price / (w / 1000) if w else price
        if per_kg <= MAX_SEASONAL:
            prices.append(per_kg)

    avg   = sum(prices) / len(prices) if prices else float('nan')
    names = '; '.join(n[:45] for n in sub['Product Name'].tolist())
    return {'unit_price': round(avg, 2), 'n_products': len(prices), 'matched_names': names}

# ── 6. MONTHLY COMPUTATION ──────────────────────────────
def compute_hunger_threshold(csv_path: str, date_label: str) -> pd.DataFrame:
    df = pd.read_csv(csv_path, encoding='utf-8-sig')
    df = df.drop_duplicates(subset=['Product Name'])
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
