import re
import pandas as pd
from pathlib import Path

# ── 1. PATHS ────────────────────────────────────────────
BASE_DIR = "/Users/efeyildirim/Downloads/Marketler/Gurmar"

FILES = {
    "Feb-21 2026": f"{BASE_DIR}/gurmar_prices_2026-02-21.csv",
    "Feb-28 2026": f"{BASE_DIR}/gurmar_prices_2026-02-28.csv",
    "Mar 2026":    f"{BASE_DIR}/gurmar_prices_2026-03-31.csv",
    "May 2026":    f"{BASE_DIR}/gurmar_prices_2026-05-22.csv",
    # Apr-30 is empty — skipped
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
# kat = kategori list (used only when file has kategori column)
# kw  = keywords (all must be lowercase-contained in product name)
# ex  = excludes
# unit = "kg" | "ml_or_L" | "piece"
# require_weight = True → skip products with no detectable weight/volume
# min/max_price_per_kg = filter outliers

MATCH_RULES = {
    "Milk": {
        "kat":  ["Süt, Kahvaltılık, Sark."],
        "kw":   ["Tam Yağlı Süt","Yarım Yağlı Süt","Yağlı Süt","Uht Süt","Pastörize Süt"],
        "ex":   ["Kakaolu","Çilek","Muz","Aromalı","Hindistan","Badem","Yulaf",
                 "Laktozsuz","Kefir","Ayran","Kido","İçimino","Nesquik",
                 "Devam","Bebek","200 Ml","180 Ml","Latte","Sütlaç","Krema",
                 "Protein","Organik","Günlük","Sütlü","Büyümix","Hüptrik",
                 "Peynir","Tereyağ","Reçel"],
        "unit": "ml_or_L",
        "max_price_per_kg": 200,
    },
    "Yogurt": {
        "kat":  ["Süt, Kahvaltılık, Sark."],
        "kw":   ["Yoğurt"],
        "ex":   ["Meyveli","Organik","Kaymaklı","Çırpılmış","Laktozsuz",
                 "Çilek","Muz","Aromalı","Activia","Tava","Fermente",
                 "Dip","Cips","Kefir","Bebek","Mama","Puding","Light",
                 "Kaymaksız Yoğurt 500","Sarımsaklı","Probiyotik","Mix"],
        "unit": "kg",
    },
    "White Cheese": {
        "kat":  ["Süt, Kahvaltılık, Sark."],
        "kw":   ["Beyaz Peynir","Klasik Peynir","Taze Peynir"],
        "ex":   ["Kaşar","Lor","Dil","Örgü","Çeçil","Krem","Mozzarella",
                 "Labne","Tulum","Süzme","Laktozsuz","Pınar Tam Yağlı Taze"],
        "unit": "kg",
    },
    "Kashar / Other Cheese": {
        "kat":  ["Süt, Kahvaltılık, Sark."],
        "kw":   ["Kaşar"],
        "ex":   ["Sandviç","Köfte","Poğaça","Bisküvi"],
        "unit": "kg",
    },
    "Minced Meat": {
        "kat":  ["Et ve Tavuk"],
        "kw":   ["Kıymalık"],
        "ex":   ["Kuşbaşı","Döner","Pişmiş","Burger","Sosis","Köfte","Mantı"],
        "unit": "kg",
    },
    "Cubed Meat / Lamb Meat": {
        "kat":  ["Et ve Tavuk"],
        "kw":   ["Kuşbaşı"],
        "ex":   ["Kıymalık","Döner","Köfte","Sosis"],
        "unit": "kg",
    },
    "Chicken": {
        "kat":  ["Et ve Tavuk"],
        "kw":   ["Piliç"],
        "ex":   ["Döner","Nugget","Köfte","Kroket","Çıtır","Sosis","Salam",
                 "Füme","Sucuk","Şnitzel","Burger","Kangal"],
        "unit": "kg",
    },
    "Fish": {
        "kat":  ["Et ve Tavuk"],
        "kw":   ["Levrek","Hamsi","Çupra","Alabalık","Somon Dilim","Balık Fileto"],
        "ex":   ["Kedi","Köpek","Kraker","Konserve","Ton","Finger","Çubuk",
                 "Füme","Marine","Teriyaki","Onigiri","Sushida","Dardanel"],
        "unit": "kg",
    },
    "Eggs": {
        "kat":  ["Süt, Kahvaltılık, Sark."],
        "kw":   ["Yumurta"],
        "ex":   ["Bıldırcın","Kedi","Köpek","Waffle","Makarna","Bisküvi","Organik",
                 "Kinder","Ozmo","Çikolata","Sürpriz","Kanky"],
        "unit": "piece",
    },
    "Dried Beans": {
        "kat":  ["Temel Gıda"],
        "kw":   ["Kuru Fasulye","Dermasyon Fasulye","Dermason Fasulye"],
        "ex":   ["Konserve","Etli","Organik","1 g"],
        "unit": "kg",
    },
    "Chickpeas": {
        "kat":  ["Temel Gıda"],
        "kw":   ["Nohut"],
        "ex":   ["Konserve","Cips","Cipsi","Organik","1 g","Çorba","Erişte",
                "Nohutlu","Haşlanmış","Pratik","Pilav"],
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
        "ex":   ["Çorba","Organik","1 g","Makarna","Erişte","Haşlanmış","Konserve",
                "Pilavı","Bulgur Pilavı","Mercimekli"],
        "unit": "kg",
        "max_price_per_kg": 400,
    },
    "Walnut / Hazelnut / Peanut": {
        "kat":  ["Temel Gıda"],
        "kw":   ["Ceviz İçi","Fındık İçi","Yer Fıstığı"],
        "ex":   ["Ezmesi","Kreması","Çikolata","Cips","Soslu","Aromalı",
                 "Baklava","Bisküvi","Granola","Bar","Protein","Turp","Krem"],
        "unit": "kg",
    },
    "Bread": {
        "kat":  ["Temel Gıda"],
        "kw":   ["Ekmek"],
        "ex":   ["Hamburger","Sandviç","Tost","Lavaş","Tortilla","Gevrek",
                 "Kızarmış","Grissini","Glutensiz","Kıtır","Börek","Poğaça",
                 "Ekmeküstü","Kırıntısı","1/3","1/2"],
        "unit": "kg",
        "min_price_per_kg": 40,
        "max_price_per_kg": 600,
    },
    "Rice": {
        "kat":  ["Temel Gıda"],
        "kw":   ["Pirinç"],
        "ex":   ["Gevreği","Kek","Sirke","Patlağı","Unu","Organik","Sushi",
                 "Risotto","Bebek","Şehriye","Yufkası","Mama","Maması",
                 "Bebelac","Hero","Milupa","Garnitürlü Pirinç Pilavı"],
        "unit": "kg",
        "max_price_per_kg": 200,
    },
    "Bulgur": {
        "kat":  ["Temel Gıda"],
        "kw":   ["Bulgur"],
        "ex":   ["Organik"],
        "unit": "kg",
    },
    "Pasta": {
        "kat":  ["Temel Gıda"],
        "kw":   ["Makarna"],
        "ex":   ["Sosu","Knorr","Tortellini","Lazanya","Peyniri","Kedi","Köpek",
                "Soslu","Erişte","Napoliten"],
        "unit": "kg",
    },
    "Flour": {
        "kat":  ["Temel Gıda"],
        "kw":   ["Çok Amaçlı Un","Ekmeklik Un","Buğday Unu","Sinangil Un",
                 "Söke Un","Nuhun Un","Gürmar Un"],
        "ex":   ["Galeta","Mısır","Nişasta","Glutensiz","Baklava","Nohut",
                 "Kek","Kurabiye","Pirinç","İrmik","Börek"],
        "unit": "kg",
    },
    "Semolina": {
        "kat":  ["Temel Gıda"],
        "kw":   ["İrmik"],
        "ex":   ["Helvası","Bebek","Organik","Vakumlu İrmik"],
        "unit": "kg",
    },
    "Apple": {
        "kat":  ["Meyve ve Sebze"],
        "kw":   ["Elma"],
        "ex":   ["Suyu","Aromalı","Hindistan","Kurusu","Kek","Bisküvi","Granola",
                 "Sirke","Topu","Lifalif","Soda","Gazoz","Detoks",
                 "Mayonez","Ketçap","Patates","Bebelac","Hero","Milupa",
                 "Mama","Maması","Cookies","Frambuaz","Hellmann"],
        "unit": "kg",
        "require_weight": True,
        "max_price_per_kg": 400,
    },
    "Orange / Mandarin": {
        "kat":  ["Meyve ve Sebze"],
        "kw":   ["Portakal","Mandalina"],
        "ex":   ["Suyu","Gazoz","Aromalı","Maden","Kefir","Çikolata","Bisküvi",
                 "Deterjan","Sabun","Maske","Krem","Organik","Nektar","Nektarı",
                 "Uludağ","Ben Organıc","Benorganic","Cappy","Dimes","Fanta",
                 "Schweppes","Yedigün","Meysu","Pronto","Selin","Duru",
                 "Gofret","Jöle","Jelibon","Şeker","Toffe","Bar","Kek",
                 "Ülker","Hero Baby","Mama","Puding","Draje","Halkası"],
        "unit": "kg",
        "max_price_per_kg": 200,
        "require_weight": True,
    },
    "Banana": {
        "kat":  ["Meyve ve Sebze"],
        "kw":   ["Muz"],
        "ex":   ["Püresi","Bebek","Aromalı","Kurusu","Kefir","Süt","Yoğurt",
                 "Probiyotik","Activia","Bowl","Puding","Granola","Bar",
                 "Dondurma","Carte","Gofret","Bisküvi","Kek","Şeker",
                 "Oetker","Milkshake","Sakız","Mama","Milupa","Hero",
                 "Kakaolu","Çokomel","Big Babol"],
        "unit": "kg",
        "max_price_per_kg": 250,
        "require_weight": True,
    },
    "Potato": {
        "kat":  ["Meyve ve Sebze"],
        "kw":   ["Patates"],
        "ex":   ["Cips","Kroket","Börek","Püresi","Poğaça","Nuggets","Dondurulmuş",
                 "Kızartmalık","Garnitür","Churros","Cajun","Superfresh","Feast",
                 "Frytime","Çubuk","Elma Dilim","Jumbo"],
        "unit": "kg",
        "max_price_per_kg": 150,
    },
    "Onion": {
        "kat":  ["Meyve ve Sebze"],
        "kw":   ["Soğan"],
        "ex":   ["Taze","Pırasa","Arpacık","Kurutulmuş","Kroket","Dondurulmuş",
                 "Yahnilik","Tozu","Halka","Cipsi","Baharat","Çerezza","Ruffles",
                 "Çizi","Feast","Superfresh"],
        "unit": "kg",
        "max_price_per_kg": 200,
    },
    "Tomato": {
        "kat":  ["Meyve ve Sebze"],
        "kw":   ["Domates"],
        "ex":   ["Salça","Kurutulmuş","Konserve","Cherry","Sosu","Atıştırmalık",
                 "Çorbası","Çorba","Rende","Labne","Kuru Domatesli","Ezme",
                 "Dip","Knorr","Eti Form","Fasulye","Bamya","Bisküvi"],
        "unit": "kg",
        "max_price_per_kg": 350,
    },
    "Cucumber": {
        "kat":  ["Meyve ve Sebze"],
        "kw":   ["Salatalık"],
        "ex":   ["Turşu","Silör"],
        "unit": "kg",
    },
    "Pepper": {
        "kat":  ["Meyve ve Sebze"],
        "kw":   ["Biber"],
        "ex":   ["Pul","Toz","Turşu","Salça","Sos","Acı Biber Sosu",
                 "Peynir","Füme","Biberiye","Biberon","Dolgu","Zeytin",
                 "Közlenmiş","Baharat","Cips","Doritos","Kraker","Eti Crax"],
        "unit": "kg",
        "max_price_per_kg": 800,
    },
    "Eggplant / Zucchini": {
        "kat":  ["Meyve ve Sebze"],
        "kw":   ["Patlıcan","Kabak"],
        "ex":   ["Közlenmiş","Turşu","Çekirdeği","Ezmesi","Kedi","Köpek",
                 "Maması","Bal Kabağı","Balkabak","Salatası","Granola","Kek",
                 "Nohut","Yayla","Kellogg","Meze","Kızartma","Dolma","Kuru"],
        "unit": "kg",
        "max_price_per_kg": 400,
    },
    "Carrot": {
        "kat":  ["Meyve ve Sebze"],
        "kw":   ["Havuç"],
        "ex":   ["Suyu","Püresi","Bebek","Mini","Kefir","Aromalı","Erüst",
                 "Kek","Çorbası","Zerdeçal","Pedigree","Kedi","Köpek","Maması","Felix"],
        "unit": "kg",
        "max_price_per_kg": 200,
    },
    "Greens / Lettuce / Parsley": {
        "kat":  ["Meyve ve Sebze"],
        "kw":   ["Marul","Maydanoz","Roka","Dereotu","Tere Demet"],
        "ex":   [],
        "unit": "piece",
    },
    "Other Vegetables": {
        "kat":  ["Meyve ve Sebze"],
        "kw":   ["Mantar","Lahana","Ispanak","Brokoli","Enginar"],
        "ex":   ["Konserve","Turşu","Kedi","Köpek","Suyu","Paket","Beyaz Kabak",
                 "La Lorraine","Lahana Rulosu","Sarma"],
        "unit": "kg",
        "max_price_per_kg": 300,
    },
    "Sunflower Oil": {
        "kat":  ["Temel Gıda"],
        "kw":   ["Ayçiçek Yağı"],
        "ex":   ["Teneke","Sprey","Ton Balık"],
        "unit": "ml_or_L",
    },
    "Olive Oil": {
        "kat":  ["Temel Gıda"],
        "kw":   ["Zeytinyağı"],
        "ex":   ["Ton Balık","Sabun","Sprey","Enginar","Şampuan","Losyon",
                 "Bebek","Konserve","Bakım","Kreme"],
        "unit": "ml_or_L",
    },
    "Butter": {
        "kat":  ["Süt, Kahvaltılık, Sark."],
        "kw":   ["Tereyağ","Tereyağı"],
        "ex":   ["Margarin","Bitkisel","Milföy","Bisküvi","Şeker","Yayık"],
        "unit": "kg",
    },
    "Margarine": {
        "kat":  ["Süt, Kahvaltılık, Sark."],
        "kw":   ["Margarin"],
        "ex":   ["Şişe","Ekmeküstü"],
        "unit": "kg",
    },
    "Olives": {
        "kat":  ["Süt, Kahvaltılık, Sark."],
        "kw":   ["Zeytin"],
        "ex":   ["Yağ","Ezmesi","Sabun","Zeytinyağlı","Bisküvi","Kraker",
                 "Grissini","Köfte","Sandviç"],
        "unit": "kg",
    },
    "Sugar": {
        "kat":  ["Temel Gıda"],
        "kw":   ["Toz Şeker"],
        "ex":   ["Küp","Esmer","Vanilin","Kahverengi","Pudra"],
        "unit": "kg",
    },
    "Tea": {
        "kat":  ["İçecekler"],
        "kw":   ["Çay"],
        "ex":   ["Bitki","Soğuk","Meyve","Ihlamur","Papatya","'lü","'li",
                 "Aromalı","Makinesi","Saati","Bardağı","Soda","Buz","Limon",
                 "Buz","Ice","Yeşil Çay","Poşet"],
        "unit": "kg",
        "require_weight": True,
        "max_price_per_kg": 600,
    },
    "Tomato Paste": {
        "kat":  ["Temel Gıda"],
        "kw":   ["Domates Salçası","Domates Salça"],
        "ex":   ["Biber","Acı"],
        "unit": "kg",
    },
    "Jam": {
        "kat":  ["Süt, Kahvaltılık, Sark."],
        "kw":   ["Reçel"],
        "ex":   ["Diabetik","Süt Reçeli","Kestane","Ceviz"],
        "unit": "kg",
    },
    "Honey": {
        "kat":  ["Süt, Kahvaltılık, Sark."],
        "kw":   ["Çiçek Balı","Çam Balı","Kestane Balı","Karakovan Balı",
                 "Yayla Balı","Narenciye Balı","Bingöl Balı","Krem Bal",
                 "Süzme Bal","Anavarza","Balparmak"],
        "ex":   ["Kabağı","Reçel","Propolis","Bisküvi","Bar","Pasta","Granola",
                 "Çikolata","Kedi","Köpek","Balık","Balsam","Balzamik",
                 "Balküpü","Saç","Gong","Elidor","Nivea","Palette","Mısır"],
        "unit": "kg",
        "max_price_per_kg": 3500,
    },
    "Molasses": {
        "kat":  ["Süt, Kahvaltılık, Sark.", "Temel Gıda"],
        "kw":   ["Pekmez"],
        "ex":   ["Tahin","Tüp","Sucuk"],
        "unit": "kg",
    },
    "Salt": {
        "kat":  ["Temel Gıda"],
        "kw":   ["Tuz"],
        "ex":   ["Tuzlu","Tuzsuz","Bulaşık","Salamura","Limon","Zeytinli",
                 "Bisküvi","Kurabiye","Simit","Ekmek","Sos","Deterjan",
                 "Himalaya","Himalife","Kaya Tuzu","Deniz Tuzu","Öğütme",
                 "Klorak","Sabun","Turşu","Soya","Baharatı","Leblebi",
                 "Çikolata","Tulum","Zeytin","Fındık","Fıstık"],
        "unit": "kg",
        "require_weight": True,
        "max_price_per_kg": 100,
    },
    "Average Spices": {
        "kat":  ["Temel Gıda"],
        "kw":   ["Baharat","Karabiber","Pul Biber"],
        "ex":   ["Cips","Kraker","Noodle","Bisküvi","Çikolata","Kedi","Köpek",
                 "Salam","Sucuk","Fesleğen","Baklava","Köfte","Hazır","Salep",
                 "Hindi","Füme","Pastırma","Sucuk"],
        "unit": "kg",
        "require_weight": True,
        "max_price_per_kg": 750,
    },
    "Linden / Herbal Tea": {
        "kat":  ["İçecekler"],
        "kw":   ["Ihlamur","Papatya Çayı","Bitki Çay"],
        "ex":   ["Pastil","Havlu","Sabun","Şampuan","Macun","Makinesi"],
        "unit": "piece",
    },
}

# Seasonal fruit: items in "Meyve ve Sebze" that are seasonal, packaged in 500 Gr
# Explicit list of seasonal fruits to include (by keyword in name)
SEASONAL_FRUIT_KW = [
    "Armut","Çilek","Greyfurt","Kivi","Kumkuat","Nar","Nektarin","Şeftali",
    "Kavun","Karpuz","Erik","Kiraz","Vişne","Üzüm","İncir","Kayısı","Dut",
    "Muşmula","Mango","Ejder Meyvesi","Yaban Mersini","Çağla Badem","Ananas",
    "Pomelo","Papaya","Kestane",
]
SEASONAL_FRUIT_EX = [
    "Suyu","Gazoz","Aromalı","Konserve","Kuru","Bisküvi","Kurabiye","Bar",
    "Çikolata","Kek","Gofret","Sakız","Dondurma","Şeker","Reçel","Pekmez",
    "Granola","Bebek","Mama","Kefir","Yoğurt","Süt","Deterjan","Sabun",
    "Şampuan","Losyon","Boya","Kolonya","Şeftali Aromalı","Vişne Aromalı",
    "Çilek Aromalı","Karpuz Aromalı","Nektar","Nektarı","Kremsi","Draje","Toffe",
]

# ── 4. FILE LOADER ──────────────────────────────────────
def parse_price_str(s: str):
    """Parse price string in any Gürmar format to float."""
    s = str(s).strip()
    # "(124,90 / Kg)" → extract 124,90
    m = re.search(r'[\d.,]+', s.replace(' ', ''))
    if not m:
        return None
    raw = m.group()
    # "1.199,50" → thousands dot before 3-digit group → remove it
    raw = re.sub(r'\.(?=\d{3}[,])', '', raw)
    raw = re.sub(r'\.(?=\d{3}$)', '', raw)
    raw = raw.replace(',', '.')
    try:
        return float(raw)
    except ValueError:
        return None

def is_per_kg_price(s: str) -> bool:
    """True if the price string is already per-kg (Feb-21 format: '(124,90 / Kg)')."""
    return '/ Kg' in str(s) or '/Kg' in str(s)

def load_file(path: str) -> pd.DataFrame:
    """Load any Gurmar CSV into normalised DataFrame:
       columns: name | kategori | price_float | is_per_kg
    """
    with open(path, encoding='utf-8-sig', errors='replace') as f:
        header = f.readline()

    semicolon = ';' in header

    if semicolon:
        # May-22 format
        df = pd.read_csv(path, sep=';', on_bad_lines='skip', encoding='utf-8-sig')
        df.columns = ['name', 'price_raw', 'product_id']
        df['kategori'] = None
        df['is_per_kg'] = False
        df['price'] = pd.to_numeric(df['price_raw'], errors='coerce')
    elif 'kategori' in header:
        # Feb-28 / Mar-31
        df = pd.read_csv(path, on_bad_lines='skip', encoding='utf-8-sig')
        df = df.rename(columns={'product-name': 'name', 'product_price': 'price_raw'})
        df['is_per_kg'] = False
        df['price'] = df['price_raw'].apply(parse_price_str)
    else:
        # Feb-21: no kategori column
        df = pd.read_csv(path, on_bad_lines='skip', encoding='utf-8-sig')
        df = df.rename(columns={'product-name': 'name', 'product_price': 'price_raw'})
        df['kategori'] = None
        df['is_per_kg'] = df['price_raw'].apply(is_per_kg_price)
        df['price'] = df['price_raw'].apply(parse_price_str)

    df = df.dropna(subset=['price'])
    df = df[df['price'] > 0]
    df = df.drop_duplicates(subset=['name'])
    return df[['name', 'kategori', 'price', 'is_per_kg']].copy()

# ── 5. UNIT EXTRACTION ──────────────────────────────────
def extract_weight_g(name: str):
    m = re.search(r'[-–]?\s*(\d+[,.]?\d*)\s*(Kg|kg|KG|Gr|gr|GR)\b', name)
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
    m = re.search(r"(\d+)['\u2019]?(LU|Lİ|LI|li|lu)\b", name, re.IGNORECASE)
    if m: return int(m.group(1))
    m2 = re.search(r'(\d+)\s*[Aa]det', name)
    if m2: return int(m2.group(1))
    return None

# ── 6. UNIT PRICE CALCULATOR ────────────────────────────
def get_unit_price(df: pd.DataFrame, product_label: str) -> dict:
    rule = MATCH_RULES[product_label]
    has_kat = df['kategori'].notna().any()

    # Apply kategori filter only when file has kategori
    if has_kat and rule['kat']:
        sub = df[df['kategori'].isin(rule['kat'])].copy()
    else:
        sub = df.copy()

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

    unit     = rule['unit']
    req_w    = rule.get('require_weight', False)
    min_p    = rule.get('min_price_per_kg', 0)
    max_p    = rule.get('max_price_per_kg', None)
    prices   = []

    for _, row in sub.iterrows():
        name = str(row['name']); price = float(row['price'])
        is_per_kg = bool(row.get('is_per_kg', False))

        if unit == 'kg':
            if is_per_kg:
                per_u = price
            else:
                w = extract_weight_g(name)
                if req_w and not w: continue
                per_u = price / (w / 1000) if w and w > 0 else price
            if per_u < min_p: continue
            if max_p and per_u > max_p: continue
            prices.append(per_u)

        elif unit == 'ml_or_L':
            if is_per_kg:
                prices.append(price)
            else:
                v = extract_volume_ml(name) or extract_weight_g(name)
                per_u = price / (v / 1000) if v and v > 0 else price
                if max_p and per_u > max_p: continue
                prices.append(per_u)

        elif unit == 'piece':
            cnt = extract_piece_count(name)
            if cnt and cnt > 0:
                prices.append(price / cnt)
            elif product_label == 'Linden / Herbal Tea':
                prices.append(price / 20 / 0.002)
            else:
                prices.append(price)

    avg   = sum(prices) / len(prices) if prices else float('nan')
    names = '; '.join(str(r['name'])[:45] + ('…' if len(str(r['name'])) > 45 else '')
                      for _, r in sub.iterrows())
    return {'unit_price': round(avg, 2), 'n_products': len(prices), 'matched_names': names}


def get_seasonal_fruit_price(df: pd.DataFrame) -> dict:
    has_kat = df['kategori'].notna().any()

    if has_kat:
        sub = df[df['kategori'] == 'Meyve ve Sebze'].copy()
    else:
        # No kategori — match known fruit keywords + require "500 Gr" or "_1kg" in name
        sub = df[df['name'].apply(
            lambda x: any(kw.lower() in str(x).lower() for kw in SEASONAL_FRUIT_KW)
            and ('500 Gr' in str(x) or '_1kg' in str(x))
        )].copy()

    # Exclude non-fruit items remaining in Meyve ve Sebze
    always_exclude = [
        "Elma","Portakal","Mandalina","Muz","Limon","Avokado",
        "Suyu","Kabağı","Cherry","Brokoli","Patates","Soğan","Domates",
        "Salatalık","Biber","Patlıcan","Kabak","Havuç","Marul","Maydanoz",
        "Roka","Dereotu","Lahana","Mantar","Ispanak","Enginar","Bakla",
        "Bezelye","Karnabahar","Kereviz","Pırasa","Turp","Fasulye","Börülce",
        "Tere","Sarımsak","Zencefil","Zerdeçal","Hindistan Cevizi","Pancar",
        "Yer Elması","Pazı","Kivi","Adet",
        # Specialty/exotic items that inflate price
        "Manav Erüst","Manav Verita","Erüst","Verita","Demirhindi",
        "Kuşkonmaz","Maskolin","Yaban Mersini","Kekik","Lime",
        "Salam","Peynir","Mayonez","Ketçap","Hardal","Sos",
        "Süt","Tereyağ","Yoğurt","Dondurma","Kefir",
        "Bisküvi","Kek","Gofret","Çikolata","Kraker",
        "Paket","Kutu","Konserve","Reçel","Turşu",
    ]
    # Plus the seasonal exclude list
    for exc in always_exclude + SEASONAL_FRUIT_EX:
        sub = sub[~sub['name'].str.contains(exc, case=False, na=False)]

    # Cap per-kg price to remove obvious outliers (specialty/exotic)
    MAX_SEASONAL_PER_KG = 600

    prices = []
    for _, row in sub.iterrows():
        name = str(row['name']); price = float(row['price'])
        is_per_kg = bool(row.get('is_per_kg', False))
        if is_per_kg:
            per_kg = price
        else:
            w = extract_weight_g(name)
            if w and w > 0:
                per_kg = price / (w / 1000)
            else:
                continue  # skip — can't normalise
        if per_kg <= MAX_SEASONAL_PER_KG:
            prices.append(per_kg)

    avg   = sum(prices) / len(prices) if prices else float('nan')
    names = '; '.join(str(r['name'])[:45] for _, r in sub.iterrows())
    return {'unit_price': round(avg, 2), 'n_products': len(prices), 'matched_names': names}

# ── 7. MONTHLY COMPUTATION ──────────────────────────────
def compute_hunger_threshold(csv_path: str, date_label: str) -> pd.DataFrame:
    df   = load_file(csv_path)
    rows = []
    for category, product_label, unit_label, monthly_qty in FOOD_BASKET:
        if product_label == 'Seasonal Fruit':
            info = get_seasonal_fruit_price(df)
        else:
            info = get_unit_price(df, product_label)
        unit_price   = info['unit_price']
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

# ── 8. MAIN ─────────────────────────────────────────────
all_results  = []
summary_rows = []

for date_label, path in FILES.items():
    if not Path(path).exists():
        print(f"  ⚠  File not found, skipping: {path}")
        continue

    df_month = compute_hunger_threshold(path, date_label)
    total    = df_month['monthly_cost_TRY'].sum()
    n_na     = df_month['avg_unit_price_TRY'].isna().sum()
    all_results.append(df_month)
    summary_rows.append({'date': date_label, 'hunger_threshold_TRY': round(total, 2), 'n_na': int(n_na)})

    na_note = f'  [{n_na} items N/A — not in catalog]' if n_na else ''
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
