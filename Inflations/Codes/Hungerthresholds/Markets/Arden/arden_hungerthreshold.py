"""

Note: Fish is not available at Arden (no fresh fish section) → NaN for that item.
"""

import pandas as pd
import re
from pathlib import Path

# ─────────────────────────────────────────────────────
# 1.  PATHS  ←  edit BASE_DIR to your folder
# ─────────────────────────────────────────────────────
BASE_DIR = "/Users/efeyildirim/Downloads/Marketler/Arden"

FILES = {
    "Mar 2026":  f"{BASE_DIR}/arden_urunler_2026-03-02.csv",
    "Apr 2026":  f"{BASE_DIR}/arden_urunler_2026-04-01.csv",
    "Apr2 2026": f"{BASE_DIR}/arden_urunler_2026-04-21.csv",
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
# Arden uses a single "kategori" column (no alt_kategori).
#
# ITEM NOTES
# ----------
# Milk          Kahvaltilik category; "lt" used instead of "L" in product names
#               (handled in volume parser). Yogurt/cheese/butter also in same
#               category — excluded explicitly.
# Yogurt        Across Kahvaltilik + Sut Urunleri; only plain homojenize yogurt.
# White Cheese  Keyword-matched from Kahvaltilik + Sut Urunleri.
# Fish          NOT AVAILABLE at Arden → NaN, excluded from total.
# Tea           Only loose-leaf (weight in grams); sachet packs and NxM.Xg
#               multi-sachet formats excluded to avoid normalisation errors.
# Bread         Min ₺50/kg filter to exclude subsidised/anomalous items.
# Greens        Sold per piece (Adet); 4 kg/month → 16 pieces at 250 g/piece.
# Seasonal Fruit Average of all non-staple fruits available that month.

MATCH_RULES = {
    "Milk": {
        "kat": ["Kahvaltilik","Sut Urunleri"],
        "kw":  ["Süt"],
        "ex":  ["Çocuk","Laktozsuz","Kakao","Çilek","Aromalı","Ayran","Krema",
                "Malt","Yoğurt","Peynir","Kaymak","Sütlaç","Kefir","Dondurma",
                "Bisküvi","Bebek","Keçi","Manda","Sütlü","Muzlu","Latte",
                "Devam","Tereyağ","Labne","Cacık","Salep","Protein",
                "Mısır","Mısırlı","Bakım","Badem Sütü","Yulaf Sütü",
                "Tozu","Coffee","Komili","Sabun","Kinder","Kido",
                "İçimino","Alpimik","Tatlım","Crunch","Popcorn",
                "Cips","Çerez","Gofret","Çikolatalı Gofret",
                "Fit Süt","Barista","Reçel","Gofret","Dilimi",
                "200 Ml","180 Ml","400 Ml","100 Gr"],
        "unit": "ml_or_L",
        "max_price_per_kg": 130,
    },
    "Yogurt": {
        "kat": ["Sut Urunleri","Kahvaltilik"],
        "kw":  ["Yoğurt"],
        "ex":  ["Meyveli","Organik","Kaymaklı","Süzme","Çırpılmış","Probiyotik",
                "Laktozsuz","Çilek","Aromalı","Quark","Tava","Bidon","Sarımsaklı",
                "Light","Cacık","Şeftali Kayısı","Şeftali Kayısılı","Activia","İncirli","Muzlu","Çilekli","Seftali"],
        "unit": "kg",
    },
    "White Cheese": {
        "kat": ["Kahvaltilik","Sut Urunleri"],
        "kw":  ["Beyaz Peynir","Klasik Peynir","Taze Peynir","Ekici","Tahsildaroğlu"],
        "ex":  ["Kaşar","Lor","Dil","Örgü","Çeçil","Misto","Laktozsuz",
                "Sürülebilir","Tulum","Krem","Mozzarella","Hellim","Süzme","Tereyağ","Tereyağı"],
        "unit": "kg",
    },
    "Kashar / Other Cheese": {
        "kat": ["Kahvaltilik","Sut Urunleri"],
        "kw":  ["Kaşar"],
        "ex":  [],
        "unit": "kg",
    },
    "Minced Meat": {
        "kat": ["Et Ve Tavuk"],
        "kw":  ["Kıyma"],
        "ex":  ["Köfte","Döner","Burger","Sosis","Kaşarlı","Soslu"],
        "unit": "kg",
    },
    "Cubed Meat / Lamb Meat": {
        "kat": ["Et Ve Tavuk"],
        "kw":  ["Kuşbaşı"],
        "ex":  ["Döner","Köfte"],
        "unit": "kg",
    },
    "Chicken": {
        "kat": ["Et Ve Tavuk"],
        "kw":  ["Tavuk","Piliç"],
        "ex":  ["Döner","Nugget","Köfte","Kroket","Çıtır","Kebap","Lokma","Soslu","Sarma"],
        "unit": "kg",
    },
    "Fish": {
        "kat": [],   # not available at Arden
        "kw":  [],
        "ex":  [],
        "unit": "kg",
    },
    "Eggs": {
        "kat": ["Kahvaltilik","Firsat Urunleri"],
        "kw":  ["Yumurta"],
        "ex":  ["Bıldırcın"],
        "unit": "piece",
    },
    "Dried Beans": {
        "kat": ["Temel Gida"],
        "kw":  ["Kuru Fasulye","Dermason Fasulye"],
        "ex":  ["Konserve","Haşlanmış","Turşu","Taze","Yeşil","Zeytinyağlı",
                "Barbunya","Soya","Organik","Pilaki","Meksika"],
        "unit": "kg",
        "max_price_per_kg": 350,
    },
    "Chickpeas": {
        "kat": ["Temel Gida"],
        "kw":  ["Nohut"],
        "ex":  ["Konserve","Haşlanmış","Pilav"],
        "unit": "kg",
    },
    "Red Lentils": {
        "kat": ["Temel Gida"],
        "kw":  ["Kırmızı Mercimek"],
        "ex":  ["Çorba"],
        "unit": "kg",
    },
    "Green Lentils": {
        "kat": ["Temel Gida"],
        "kw":  ["Yeşil Mercimek"],
        "ex":  [],
        "unit": "kg",
    },
    "Walnut / Hazelnut / Peanut": {
        "kat": ["Atistirmalik","Temel Gida"],
        "kw":  ["Fındık İçi","Ceviz İçi","Yer Fıstığı İçi"],
        "ex":  ["Krem","Krema","Çikolata","Helva","Ezmesi","Tuzlu","Kavrulmuş",
                "Cips","Soslu","Aromalı","Granola","Bar","Bisküvi","Gofret",
                "Rüyası","Karışık","Tortop"],
        "unit": "kg",
        "max_price_per_kg": 2500,
    },
    "Bread": {
        "kat": ["Unlu Mamul Tatli"],
        "kw":  ["Ekmek"],
        "ex":  ["Hamburger","Sandviç","Tost","Lavaş","Tortilla","Gevrek",
                "Kızarmış","Etimek","Grissini"],
        "unit": "kg",
        "min_price_per_kg": 50,
    },
    "Rice": {
        "kat": ["Temel Gida"],
        "kw":  ["Pirinç"],
        "ex":  ["Kırık","Basmati","Pilav Yemeğe"],
        "unit": "kg",
    },
    "Bulgur": {
        "kat": ["Temel Gida"],
        "kw":  ["Bulgur"],
        "ex":  [],
        "unit": "kg",
    },
    "Pasta": {
        "kat": ["Temel Gida"],
        "kw":  ["Makarna"],
        "ex":  ["Knorr","Tortellini","Lazanya",
                "Soslu","Napoliten","Erişte","Arabiata","Bolonez","Hazır Arabiata","Bolonez Soslu","Napoliten Soslu","Makarna Sos","Pesto Soslu","Pesto"],
        "unit": "kg",
    },
    "Flour": {
        "kat": ["Temel Gida","Firsat Urunleri"],
        "kw":  ["Sinangil Un","Hekimoğlu Un","Söke Un","Ankara Un",
                "Filiz Un","Misun Un","Un 1 Kg","Un 2 Kg","Un 5 Kg"],
        "ex":  ["Mısır","Galeta","Glutensiz","Nişasta","Karma","Buğday",
                "Pirinç","Badem","Nohut"],
        "unit": "kg",
        "max_price_per_kg": 150,
    },
    "Semolina": {
        "kat": ["Temel Gida","Unlu Mamul Tatli"],
        "kw":  ["İrmik"],
        "ex":  ["Tatlı","Oetker"],
        "unit": "kg",
    },
    "Apple": {
        "kat": ["Meyve Ve Sebze"],
        "kw":  ["Elma"],
        "ex":  ["Suyu","Derisi"],
        "unit": "kg",
    },
    "Orange / Mandarin": {
        "kat": ["Meyve Ve Sebze"],
        "kw":  ["Portakal","Mandalina"],
        "ex":  ["Suyu"],
        "unit": "kg",
    },
    "Banana": {
        "kat": ["Meyve Ve Sebze"],
        "kw":  ["Muz"],
        "ex":  [],
        "unit": "kg",
    },
    "Potato": {
        "kat": ["Meyve Ve Sebze"],
        "kw":  ["Patates"],
        "ex":  ["Kızartmalık","Cips","Dondurulmuş","Harcı"],
        "unit": "kg",
    },
    "Onion": {
        "kat": ["Meyve Ve Sebze"],
        "kw":  ["Soğan Kuru","Soğan Beyaz","Soğan Kırmızı"],
        "ex":  ["Arpacık","Sarımsak","Taze","Turşu","Tozu"],
        "unit": "kg",
        "max_price_per_kg": 200,
    },
    "Tomato": {
        "kat": ["Meyve Ve Sebze"],
        "kw":  ["Domates Kg","Domates Salkım","Domates Pembe","Domates Sırık"],
        "ex":  ["Salça","Kurutulmuş","Kuru Domates","Çeri","Kokteyl","Sosero",
                "Sosu","Cherry","Rengi","Rengi"],
        "unit": "kg",
    },
    "Cucumber": {
        "kat": ["Meyve Ve Sebze"],
        "kw":  ["Salatalık"],
        "ex":  ["Turşu"],
        "unit": "kg",
    },
    "Pepper": {
        "kat": ["Meyve Ve Sebze"],
        "kw":  ["Biber"],
        "ex":  ["Pul","Toz","Turşu","Salça","Sos","Közlenmiş","Kurutulmuş",
                "Biberon","Crax","Doritos","Çizi","Lays","Cipsi","Cips",
                "Isot","Karabiber","Karışık Dolmalık","Dolmalık 20",
                "Acı Biber Sosu","Yemeklik"],
        "unit": "kg",
        "max_price_per_kg": 500,
    },
    "Eggplant / Zucchini": {
        "kat": ["Meyve Ve Sebze"],
        "kw":  ["Patlıcan","Kabak"],
        "ex":  ["Közlenmiş","Konserve","Turşu"],
        "unit": "kg",
    },
    "Carrot": {
        "kat": ["Meyve Ve Sebze"],
        "kw":  ["Havuç"],
        "ex":  [],
        "unit": "kg",
    },
    "Greens / Lettuce / Parsley": {
        "kat": ["Meyve Ve Sebze"],
        "kw":  ["Marul","Maydanoz","Roka","Dereotu","Kıvırcık"],
        "ex":  [],
        "unit": "piece",
    },
    "Other Vegetables": {
        "kat": ["Meyve Ve Sebze"],
        "kw":  ["Mantar","Lahana","Ispanak","Brokoli","Enginar"],
        "ex":  ["Konserve","Turşu"],
        "unit": "kg",
    },
    "Sunflower Oil": {
        "kat": ["Temel Gida","Firsat Urunleri"],
        "kw":  ["Ayçiçek Yağı"],
        "ex":  ["Teneke"],
        "unit": "ml_or_L",
    },
    "Olive Oil": {
        "kat": ["Temel Gida"],
        "kw":  ["Zeytinyağı","Zeytinyağ"],
        "ex":  ["Ton","Balığı","Balık","Kedi","Sabun","Sprey","Sardin",
                "Konserve","Somon","Norveç","Füme"],
        "unit": "ml_or_L",
        "max_price_per_kg": 2000,
    },
    "Butter": {
        "kat": ["Kahvaltilik","Sut Urunleri"],
        "kw":  ["Tereyağ","Tereyağı"],
        "ex":  ["Margarin","Bitkisel"],
        "unit": "kg",
    },
    "Margarine": {
        "kat": ["Sut Urunleri"],
        "kw":  ["Margarin"],
        "ex":  ["Şişe"],
        "unit": "kg",
    },
    "Olives": {
        "kat": ["Kahvaltilik"],
        "kw":  ["Zeytin"],
        "ex":  ["Yağ","Ezmesi","Sabun"],
        "unit": "kg",
    },
    "Sugar": {
        "kat": ["Temel Gida"],
        "kw":  ["Toz Şeker","Şeker Kg"],
        "ex":  ["Küp","Esmer","Vanilin"],
        "unit": "kg",
    },
    "Tea": {
        "kat": ["Icecekler"],
        "kw":  ["Çay"],
        "ex":  ["Soğuk","Meyve","Ihlamur","Papatya","Bitki","Aromalı",
                "Makinesi","Seti","Bardağı","Tabağı","Süzgeci","Maden Su",
                "Yeşil","Bergamot","Earl Grey","Kış","Zencefil",
                "Adaçayı","Tarçın","Elma","Karanfil","Ayvalı","Ada Çayı",
                "Poşet","Demlik","Limon","Nane","Rezene","Kuşburnu",
                "Melisa","Paket","Kapsül","Taze","Form","Fit","Şifalıköy"],
        "unit": "kg",
        "require_weight": True,
        "max_price_per_kg": 600,
    },
    "Tomato Paste": {
        "kat": ["Temel Gida"],
        "kw":  ["Salça"],
        "ex":  ["Turşu","Rende","Konserve"],
        "unit": "kg",
    },
    "Jam": {
        "kat": ["Kahvaltilik"],
        "kw":  ["Reçel"],
        "ex":  ["Süt Reçeli","Diabetik"],
        "unit": "kg",
    },
    "Honey": {
        "kat": ["Kahvaltilik"],
        "kw":  ["Bal"],
        "ex":  ["Kabağı","Reçel","Propolis","Petek","Tahin","Aromalı"],
        "unit": "kg",
    },
    "Molasses": {
        "kat": ["Kahvaltilik"],
        "kw":  ["Pekmez"],
        "ex":  ["Tahin","Fındık"],
        "unit": "kg",
    },
    "Salt": {
        "kat": ["Temel Gida"],
        "kw":  ["Tuz"],
        "ex":  ["Baharat","Biber","Limon","Himalaya","Zeytinyağlı",
                "Deniz","Kaya","Öğütme","Tuzluklu","Soya","Bulaşık",
                "Turşu","Tuzlu","Safir","Kristal Kaya","Az Tuz",
                "Sodyumu %50","Sodyumu Az"],
        "unit": "kg",
        "require_weight": True,
        "max_price_per_kg": 150,
    },
    "Average Spices": {
        "kat": ["Temel Gida","Baharat"],
        "kw":  ["Karabiber","Pul Biber"],
        "ex":  ["Tane","Tuzluklu","Harç","Cajun","Mangal","Izgara","Kanatlı",
                "İtalyan","Koyun","Acı","Çeşnile","Soğan Halkası","Noodle"],
        "unit": "kg",
        "require_weight": True,
        "max_price_per_kg": 2000,
    },
    "Linden / Herbal Tea": {
        "kat": ["Icecekler"],
        "kw":  ["Ihlamur","Papatya"],
        "ex":  ["Adaçayı","Ekinezya","Karışık","Form","Fit","Zencefil",
                "Meyveli","Kış","Rezene","Nane","Kuşburnu","Ada Çayı"],
        "unit": "piece",
        "require_weight": True,
        "max_price_per_kg": 3000,
    },
}

# ─────────────────────────────────────────────────────
# 4.  UTILITIES
# ─────────────────────────────────────────────────────

def parse_price(s: str) -> float:
    s = str(s).replace("₺","").replace(".","").replace(",",".").strip()
    try:    return float(s)
    except: return float("nan")

def extract_weight_g(name: str):
    m = re.search(r"(\d+[,.]?\d*)\s*(KG|GR|G)\b", name.upper())
    if m:
        v = float(m.group(1).replace(",","."))
        return v * 1000 if m.group(2) == "KG" else v
    return None

def extract_volume_ml(name: str):
    # Normalise "lt" → "L" (Arden uses "1 lt" instead of "1 L")
    n = re.sub(r"\blt\b", "L", name, flags=re.IGNORECASE).upper()
    mp = re.search(r"(\d+)\s*[xX]\s*(\d+[,.]?\d*)\s*(ML|L)\b", n)
    if mp:
        count = int(mp.group(1))
        each  = float(mp.group(2).replace(",","."))
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

    if not rule["kat"]:   # not available at this market
        return {"product_label": product_label, "unit": rule["unit"],
                "unit_price": float("nan"), "n_products": 0, "matched_names": "N/A"}

    sub  = df[df["kategori"].isin(rule["kat"])].copy()
    kw_m = sub["isim"].apply(lambda x: any(k.lower() in str(x).lower() for k in rule["kw"]))
    sub  = sub[kw_m]
    for exc in rule["ex"]:
        sub = sub[~sub["isim"].str.contains(exc, case=False, na=False)]

    if sub.empty:
        return {"product_label": product_label, "unit": rule["unit"],
                "unit_price": float("nan"), "n_products": 0, "matched_names": "—"}

    sub = sub.copy()
    sub["price"] = sub["fiyat"].apply(parse_price)
    sub = sub.dropna(subset=["price"])

    unit            = rule["unit"]
    req_weight      = rule.get("require_weight", False)
    min_price_per_u = rule.get("min_price_per_kg", 0)
    prices = []

    for _, row in sub.iterrows():
        name  = str(row["isim"])
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
                per_sachet = price / cnt
                if product_label == "Linden / Herbal Tea":
                    prices.append(per_sachet / 0.002)
                else:
                    prices.append(per_sachet)
            elif req_weight:
                continue  # skip if no parseable piece count and require_weight=True
            elif product_label == "Linden / Herbal Tea":
                prices.append((price / 20) / 0.002)  # assume 20 bags
            else:
                prices.append(price)

    avg   = sum(prices) / len(prices) if prices else float("nan")
    names = "; ".join(shorten(n) for n in sub["isim"].tolist())
    return {"product_label": product_label, "unit": unit,
            "unit_price": round(avg, 2), "n_products": len(prices),
            "matched_names": names}

def get_seasonal_fruit_price(df: pd.DataFrame) -> dict:
    sub = df[df["kategori"] == "Meyve Ve Sebze"].copy()
    excl = ["Elma","Portakal","Mandalina","Muz","Limon","Avokado",
            "Adet","Suyu","File","Kabağı","Karpuz","Kavun",
            "Patates","Soğan","Domates","Salatalık","Biber",
            "Patlıcan","Kabak","Havuç","Marul","Maydanoz",
            "Roka","Dereotu","Kıvırcık","Mantar","Lahana","Ispanak",
            "Asma Yaprak","Enginar","Salamura","Yaprak","Turşu",
            "Pancar","Kereviz","Pırasa","Sarımsak","Brokoli",
            "Tere","Pazı","Nane","Zerdeçal","Barbunya","Bakla",
            "Fasulye","Ceviz Kabuklu","Kestane","Kumkuat","Pitahaya",
            "Yaban Mersini","Paket","Kutu","Dondurulmuş",
            "Zencefil","Turp","Karnabahar","Bezelye","Börülce",
            "Kuşkonmaz","Bamya","Semizotu"]
    for exc in excl:
        sub = sub[~sub["isim"].str.contains(exc, case=False, na=False)]
    sub = sub.copy()
    sub["price"] = sub["fiyat"].apply(parse_price)
    sub = sub.dropna(subset=["price"])
    prices = []
    for _, row in sub.iterrows():
        w = extract_weight_g(str(row["isim"]))
        prices.append(row["price"] / (w / 1000) if w and w > 0 else row["price"])
    avg   = sum(prices) / len(prices) if prices else float("nan")
    names = "; ".join(shorten(n) for n in sub["isim"].tolist())
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
        names_preview = names_preview[:60]+"…" if len(names_preview) > 60 else names_preview
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
