import re
import pandas as pd
from pathlib import Path

# ── 1. PATHS ────────────────────────────────────────────
BASE_DIR = "/Users/efeyildirim/Downloads/Marketler/Macrocenter"

FILES = {
    "Feb-20 2026": f"{BASE_DIR}/macrocenter_prices_2026-02-20.csv",
    "Feb-27 2026": f"{BASE_DIR}/macrocenter_prices_2026-02-27.csv",
    "Mar 2026":    f"{BASE_DIR}/macrocenter_prices_2026-03-31.csv",
    "Apr 2026":    f"{BASE_DIR}/macrocenter_prices_2026-04-30.csv",
    "May 2026":    f"{BASE_DIR}/macrocenter_prices_2026-05-19.csv",
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
# kat = Category (exact), sub = Subcategory list (optional)
# kw = keywords (ANY must appear in Name), ex = excludes
# unit = "kg" | "ml_or_L" | "piece"
# Items ending with " Kg" → price IS per-kg already (is_sold_by_kg=True)
# Items with weight "500 G", "1 Kg" → normalise price to per-kg

MATCH_RULES = {
    "Milk": {
        "kat": "Süt Ürünleri & Kahvaltılık",
        "sub": ["Tam Yağlı","Yarım Yağlı","Az Yağlı","Pastorize Günlük Süt","Özellikli"],
        "kw":  ["Süt"],
        "ex":  ["Tahin","Kreması","Ezmesi","Kakaolu","Çilek","Aromalı","Soya","Badem",
                "Yulaf","Kefir","Ayran","Sütlü","Kaymak","Sütlaç","Krema","Devam",
                "Bebek","Laktozsuz","Protein","Büyüme","Çikolata","Reçeli","Kido",
                "Süt Reçeli","Peyniri","Kooperatif","Hellim",
                "Tereyağ","Krem Peynir","Eritme","Bonne Maman","Karamel","Dulce De Leche","İzmir Tulumu","Kırıtaklar","Latte","Kinder Süt","Eti Süt Burger","Mövenpick","Danone Doğal Süt 6","Baltalı Keçi Sütü","Arı Sütü","Propolis"],
        "unit": "ml_or_L",
        "max_price_per_kg": 250,
    },
    "Yogurt": {
        "kat": "Süt Ürünleri & Kahvaltılık",
        "sub": ["Sade"],
        "kw":  ["Yoğurt"],
        "ex":  ["Meyveli","Organik","Kaymaklı","Çırpılmış","Laktozsuz","Çilek",
                "Aromalı","Kefir","Bebek","Probiyotik","Dip","Süzme","Tava",
                "Çeçil","Keçi","Puding","Light","Fermente","Mövenpick",
                "Maya","Vivo","Mayası","Manda","Çömlek"],
        "unit": "kg",
        "max_price_per_kg": 300,
    },
    "White Cheese": {
        "kat": "Süt Ürünleri & Kahvaltılık",
        "sub": ["Klasik İnek","Özellikli","Koyun","Keçi"],
        "kw":  ["Beyaz Peynir","Taze Peynir","Klasik Peynir"],
        "ex":  ["Kaşar","Lor","Dil","Örgü","Çeçil","Krem","Mozzarella","Labne",
                "Tulum","Süzme","Laktozsuz","Hellim","Tost"],
        "unit": "kg",
    },
    "Kashar / Other Cheese": {
        "kat": "Süt Ürünleri & Kahvaltılık",
        "sub": ["Taze","Eski"],
        "kw":  ["Kaşar"],
        "ex":  ["Sandviç","Köfte","Bisküvi","Tulum","Gravyer","Gruyere"],
        "unit": "kg",
    },
    "Minced Meat": {
        "kat": "Et & Tavuk & Balık",
        "sub": ["Dana","Dana Eti","Kırmızı Et"],
        "kw":  ["Kıyma"],
        "ex":  ["Köfte","Döner","Burger","Sosis","Mantı","Börek","Pişmiş","Hazır"],
        "unit": "kg",
    },
    "Cubed Meat / Lamb Meat": {
        "kat": "Et & Tavuk & Balık",
        "sub": ["Dana","Dana Eti","Kuzu Eti","Kırmızı Et"],
        "kw":  ["Kuşbaşı"],
        "ex":  ["Kıyma","Köfte","Sosis"],
        "unit": "kg",
    },
    "Chicken": {
        "kat": "Et & Tavuk & Balık",
        "sub": ["Piliç","Organik","Taze"],
        "kw":  ["Piliç","Bütün Piliç","Piliç But","Piliç Göğüs","Piliç Kanat"],
        "ex":  ["Sosis","Salam","Sucuk","Füme","Nugget","Köfte","Döner","Jambon",
                "Schnitzel","Burger","Pastırma","Kavurma","Hindi"],
        "unit": "kg",
    },
    "Fish": {
        "kat": "Et & Tavuk & Balık",
        "sub": ["Taze Balık"],
        "kw":  ["Levrek","Çupra","Hamsi","Somon","Alabalık"],
        "ex":  ["Havyar","Ezmesi","Morina Ezmesi","Füme","Marine","Konserve","Ton","Fileto Paket","Paketli",
                "Dondurulmuş"],
        "unit": "kg",
    },
    "Eggs": {
        "kat": "Süt Ürünleri & Kahvaltılık",
        "sub": ["Organik","Gezen & Özellikli"],
        "kw":  ["Yumurta"],
        "ex":  ["Balığı","Kapelin","Pastası","Makarna","Bisküvi","Pudra","Sünger",
                "Protein Tozu","Plastik"],
        "unit": "piece",
    },
    "Dried Beans": {
        "kat": "Temel Gıda",
        "sub": ["Bakliyat"],
        "kw":  ["Kuru Fasulye","Dermason","Fasulye"],
        "ex":  ["Konserve","Haşlanmış","Etli","Organik","Soya","Barbunya",
                "Barbunya","Şeker Fasulye","Yeşil Fasulye",
                "Zeytinyağlı","Pilaki","Meksika Fasulyeli","Meksika Fasulyesi","Tereyağlı Çayeli","Tat Meksika","Tat Zeytinyağlı","Fasulye Filizi","Dardanel Fasulyeli","Superfresh Meksika","Burcu Meksika"],
        "unit": "kg",
        "max_price_per_kg": 600,
    },
    "Chickpeas": {
        "kat": "Temel Gıda",
        "sub": ["Bakliyat"],
        "kw":  ["Nohut"],
        "ex":  ["Konserve","Haşlanmış","Cips","Pilav","Organik",
                "Etli","Hazır","Yuvarlama","Tada","Pratik","Bulgur","Nohutlu","Tukaş","Haşlama"],
        "unit": "kg",
        "max_price_per_kg": 500,
    },
    "Red Lentils": {
        "kat": "Temel Gıda",
        "sub": ["Bakliyat"],
        "kw":  ["Kırmızı Mercimek"],
        "ex":  ["Çorba","Organik","Makarna","Potamya","Mercimekli Fusilli","Mercimekli Penne"],
        "unit": "kg",
        "max_price_per_kg": 400,
    },
    "Green Lentils": {
        "kat": "Temel Gıda",
        "sub": ["Bakliyat"],
        "kw":  ["Yeşil Mercimek"],
        "ex":  ["Çorba","Organik","Makarna","Haşlanmış",
                "Bulgur","Pilavı","Mercimekli","Biorootzo","Pipe Rigate","Yayla Gurme Fit"],
        "unit": "kg",
        "max_price_per_kg": 400,
    },
    "Walnut / Hazelnut / Peanut": {
        "kat": "Atıştırmalık",
        "sub": [],
        "kw":  ["Ceviz İçi","Fındık İçi","Yer Fıstığı"],
        "ex":  ["Ezmesi","Kreması","Çikolata","Cips","Soslu","Aromalı","Baklava",
                "Granola","Bar","Kavrulmuş","Tuzlu","Kızartılmış","Ezme",
                "Karış","Gigi","Elma Kurusu","Hurma","Muz","Gofret",
                "Atıştırmalık Mix","Eti Bidolu","Parçacık","Kabuklu"],
        "unit": "kg",
        "max_price_per_kg": 2000,
    },
    "Bread": {
        "kat": "Unlu Mamul & Tatlı",
        "sub": ["Ekmek Çeşitleri","Sofra Ekmek"],
        "kw":  ["Ekmek"],
        "ex":  ["Hamburger","Sandviç","Tost","Lavaş","Tortilla","Gevrek","Kızarmış",
                "Glutensiz","Kıtır","Börek","Poğaça","Kırıntısı","Grissini","Natcake","Eti Form Kızartılmış","Kızartılmış Kepekli Ekmek","Cartocci","Çikolatalı Portakallı Ekmek","Ballı Tarçınlı Ekmek"],
        "unit": "kg",
        "min_price_per_kg": 50,
        "max_price_per_kg": 600,
    },
    "Rice": {
        "kat": "Temel Gıda",
        "sub": ["Baldo Pirinç","İthal Pirinç","Pirinç","Pilavlık Pirinç","Osmancık Pirinç"],
        "kw":  ["Pirinç","Pirinc"],
        "ex":  ["Gevreği","Kek","Sirke","Patlağı","Unu","Sushi","Risotto",
                "Bebek","Şehriye","Mama","Garnitürlü","Zeytinyağlı Domates Soslu","Semizotu","Rice Stick","Pirinç Makarnası"],
        "unit": "kg",
        "max_price_per_kg": 600,
    },
    "Bulgur": {
        "kat": "Temel Gıda",
        "sub": ["Pilavlık Bulgur","Köftelik Bulgur","Katkılı Bulgur"],
        "kw":  ["Bulgur"],
        "ex":  ["Organik","Pilavı","Çorbası","Yayla Gurme Fit","Gurme Fit"],
        "unit": "kg",
    },
    "Pasta": {
        "kat": "Temel Gıda",
        "sub": ["Makarna"],
        "kw":  ["Makarna"],
        "ex":  ["Sosu","Tortellini","Ravioli","Taze Makarna","Hazır Yemek",
                "Lazanya","Kedi","Köpek","Şehriye","Çorba","Fettuccine","Soslu","Napoliten","Erişte"],
        "unit": "kg",
    },
    "Flour": {
        "kat": "Temel Gıda",
        "sub": ["Sade","Un Karışımları"],
        "kw":  ["Un"],
        "ex":  ["Galeta","Mısır","Nişasta","Glutensiz","Baklava","Nohut","Kek",
                "Kurabiye","Pirinç","Böreklik","Hindistan","Badem","Yulaf",
                "Siyez","Tam Buğday","Organik","Karabuğday","Tortellini","Ravioli","Un Do Tre","Barbunya",
                "Fasulye","Mercimek","Kemik","İlikli","Çorba","Pirinç",
                "Jungle","Turşu","Erişte","Sauerkraut","Filiz Yumurtalı Uzun Makarna","Sevgisun Erişte","Pastavilla Junior","Sevgisun Mantı","Gaia Pearls","Punica Sadece Nar","Chef Seasons Kajun","Bağdat Cajun Baharatı"],
        "unit": "kg",
        "max_price_per_kg": 150,
    },
    "Semolina": {
        "kat": "Temel Gıda",
        "sub": [],
        "kw":  ["İrmik"],
        "ex":  ["Helvası","Bebek","Organik"],
        "unit": "kg",
    },
    "Apple": {
        "kat": "Meyve & Sebze",
        "sub": ["Meyve"],
        "kw":  ["Elma"],
        "ex":  ["Suyu","Aromalı","Hindistan","Kurusu","Sirke","Çayı","SuperFresh Elma Dilim","Lavi Elma Dilim","Lavi Smoothie","Smoothie","Patates Cipsi"],
        "unit": "kg",
    },
    "Orange / Mandarin": {
        "kat": "Meyve & Sebze",
        "sub": ["Meyve"],
        "kw":  ["Portakal","Mandalina"],
        "ex":  ["Suyu","Gazoz","Aromalı"],
        "unit": "kg",
    },
    "Banana": {
        "kat": "Meyve & Sebze",
        "sub": ["Meyve"],
        "kw":  ["Muz"],
        "ex":  ["Püresi","Bebek","Aromalı","Kurusu","Lavi Smoothie","Smoothie"],
        "unit": "kg",
        "max_price_per_kg": 500,
    },
    "Potato": {
        "kat": "Meyve & Sebze",
        "sub": ["Sebze"],
        "kw":  ["Patates"],
        "ex":  ["Cips","Kroket","Börek","Püresi","Dondurulmuş","Hazır","Kızartmalık",
                "SuperFresh","Superfresh","Feast","Churros","Jumbo","Parmak","Elma Dilim",
                "Çubuk","İnce"],
        "unit": "kg",
    },
    "Onion": {
        "kat": "Meyve & Sebze",
        "sub": ["Sebze"],
        "kw":  ["Soğan"],
        "ex":  ["Taze","Arpacık","Mor","Dondurulmuş","Tozu","Frenk",
                "Salçalı","Bahçe","SuperFresh","Superfresh","Tatlı Beyaz",
                "Halka","Paket","Turşu"],
        "unit": "kg",
    },
    "Tomato": {
        "kat": "Meyve & Sebze",
        "sub": ["Sebze"],
        "kw":  ["Domates"],
        "ex":  ["Salça","Kurutulmuş","Kurusu","Konserve","Kokteyl","Sosu","Cherry",
                "Çeri","Kutu","Tatlı","Hazır"],
        "unit": "kg",
        "max_price_per_kg": 600,
    },
    "Cucumber": {
        "kat": "Meyve & Sebze",
        "sub": ["Sebze"],
        "kw":  ["Salatalık","Hıyar"],
        "ex":  ["Turşu"],
        "unit": "kg",
    },
    "Pepper": {
        "kat": "Meyve & Sebze",
        "sub": ["Sebze"],
        "kw":  ["Biber"],
        "ex":  ["Pul","Toz","Turşu","Salça","Sos","Közlenmiş","Kuru","Isot",
                "Karabiber","Jalapeno","Jalapeño","Acı Biber Turşu","Biberiye",
                "Meksika","Mini Biber","Padron"],
        "unit": "kg",
        "max_price_per_kg": 350,
    },
    "Eggplant / Zucchini": {
        "kat": "Meyve & Sebze",
        "sub": ["Sebze"],
        "kw":  ["Patlıcan","Kabak"],
        "ex":  ["Minyatür","Közlenmiş","Turşu","Çekirdeği","Ezmesi","Kurutulmuş","Sakız"],
        "unit": "kg",
        "max_price_per_kg": 500,
    },
    "Carrot": {
        "kat": "Meyve & Sebze",
        "sub": ["Sebze"],
        "kw":  ["Havuç"],
        "ex":  ["Suyu","Püresi","Bebek","Mini","Kurutulmuş",
                "Salata","Karışımı","Minyatür","Hazır","Karışık","Paket"],
        "unit": "kg",
        "max_price_per_kg": 300,
    },
    "Greens / Lettuce / Parsley": {
        "kat": "Meyve & Sebze",
        "sub": ["Sebze","Yeşillikler","Otlar & Ayıklanmış Sebze"],
        "kw":  ["Marul","Maydanoz","Roka","Dereotu","Kıvırcık","Semizotu"],
        "ex":  [],
        "unit": "piece",
    },
    "Other Vegetables": {
        "kat": "Meyve & Sebze",
        "sub": ["Sebze","Mantar"],
        "kw":  ["Mantar","Lahana","Ispanak","Brokoli","Enginar","Kereviz","Pırasa"],
        "ex":  ["Konserve","Turşu","Kuru"],
        "unit": "kg",
        "max_price_per_kg": 600,
    },
    "Sunflower Oil": {
        "kat": "Temel Gıda",
        "sub": ["Ayçiçek Yağı"],
        "kw":  ["Ayçiçek Yağı"],
        "ex":  ["Ton","Sardin","Sprey","Organik"],
        "unit": "ml_or_L",
    },
    "Olive Oil": {
        "kat": "Temel Gıda",
        "sub": ["Sızma","Özel Zeytinyağı","Riviera","Zeytinyağı"],
        "kw":  ["Zeytinyağı"],
        "ex":  ["Ton","Sabun","Sprey","Hindistan","Sardin","Konserve",
                "Ayıklanmış","Yara","Bebek","Limon Çeşnili","Bergamot Çeşnili","Acı Biber Çeşnili","Trüf Aromalı","Trüf","Royal Trüf","Pearls","Gaia Pearls"],
        "unit": "ml_or_L",
        "max_price_per_kg": 3000,
    },
    "Butter": {
        "kat": "Süt Ürünleri & Kahvaltılık",
        "sub": ["Tereyağı"],
        "kw":  ["Tereyağ","Tereyağı"],
        "ex":  ["Margarin","Bitkisel","Milföy","Bisküvi","Şeker","Yemeklik",
                "Lezzeti","Keyfi","Fıstık"],
        "unit": "kg",
    },
    "Margarine": {
        "kat": "Süt Ürünleri & Kahvaltılık",
        "sub": ["Kase","Paket"],
        "kw":  ["Margarin"],
        "ex":  ["Tereyağ","Zeytinyağlı"],
        "unit": "kg",
    },
    "Olives": {
        "kat": "Süt Ürünleri & Kahvaltılık",
        "sub": ["Siyah","Yeşil"],
        "kw":  ["Zeytin"],
        "ex":  ["Yağı","Ezmesi","Sabun","Zeytinyağlı","Bisküvi","Kraker",
                "Grissini","Dolgulu","Sandviç"],
        "unit": "kg",
    },
    "Sugar": {
        "kat": "Temel Gıda",
        "sub": ["Toz Şeker"],
        "kw":  ["Toz Şeker","Kristal Şeker"],
        "ex":  ["Küp","Esmer","Vanilin","Pudra","Hint","Kahverengi"],
        "unit": "kg",
    },
    "Tea": {
        "kat": "İçecek",
        "sub": ["Dökme Çay"],
        "kw":  ["Çay"],
        "ex":  ["Bardak Poşet","Demlik","Poşet","Bitki","Soğuk","Meyve","Yeşil",
                "Aromalı","Bergamotlu","Earl Grey","Ceylon","Fonksiyonel",
                "Siyah Çay Karışık","Form","Rooibos","Roybos","Mate","Maden",
                "Gazlı","Ml","Nane","Rezene","Zencefil","Ihlamur","Papatya",
                "Beyaz Çay","Ada Çayı","Kış Çayı","Yeşil Çay","Uyku",
                "Kamilya","Kavun","Balkabaklı","Rahat Hisset","Sinameki","Adaçayı","Bitki Çayı Sağlık","Doğadan Rahat","Green Life"],
        "unit": "kg",
        "require_weight": True,
        "max_price_per_kg": 700,
    },
    "Tomato Paste": {
        "kat": "Temel Gıda",
        "sub": ["Domates"],
        "kw":  ["Domates Salçası","Domates Salça"],
        "ex":  ["Biber","Acı","Köy","Organik","Hazır"],
        "unit": "kg",
        "max_price_per_kg": 300,
    },
    "Jam": {
        "kat": "Süt Ürünleri & Kahvaltılık",
        "sub": ["Reçel"],
        "kw":  ["Reçel"],
        "ex":  ["Diabetik","Süt Reçeli","Kestane","Ceviz","Yaban Mersini",
                "Karamel","Çikolata","Sürülebilir"],
        "unit": "kg",
    },
    "Honey": {
        "kat": "Süt Ürünleri & Kahvaltılık",
        "sub": ["Çiçek Balı","Özel Bal Ürünleri"],
        "kw":  ["Bal"],
        "ex":  ["Kabağı","Propolis","Bisküvi","Bar","Granola","Çikolata",
                "Polen","Arısütü","Reçeli","Balsam","Balzamik","Nesfit","Richland Ballı","Güney Adana","Penguen Lütenitsa","Mia Mesa","Dr. Oetker Vitalis","Baltalı Keçi","Ozmo Cool","Eti Süt Burger Sütlü Ballı","Gevrek","Tahıl"],
        "unit": "kg",
        "max_price_per_kg": 5000,
    },
    "Molasses": {
        "kat": "Süt Ürünleri & Kahvaltılık",
        "sub": ["Tahin & Pekmez"],
        "kw":  ["Pekmez"],
        "ex":  ["Tahin","Sucuk","Keçiboynuzu","Immunflex","Zencefilli",
                "Zerdeçallı","Harnup","Hurma"],
        "unit": "kg",
        "max_price_per_kg": 1500,
    },
    "Salt": {
        "kat": "Temel Gıda",
        "sub": ["Tuz"],
        "kw":  ["Tuz"],
        "ex":  ["Tuzlu","Tuzsuz","Turşu","Salamura","Himalaya","Limon",
                "Bisküvi","Simit","Deterjan","Deniz Tuzu Ekstra",
                "Sıvı Tuz","Trüf","Biberli Tuz","Çeşni","Pembe",
                "Değirmen","Sodyumu Azaltılmış","Sarımsaklı","Soğanlı",
                "Baharatlı","Kekikli","Artisan","Soya Sosu","Kikkoman",
                "Aiko","Tamari","Soya",
                "Mayi"],
        "unit": "kg",
        "require_weight": True,
        "max_price_per_kg": 200,
    },
    "Average Spices": {
        "kat": "Temel Gıda",
        "sub": ["Baharat"],
        "kw":  ["Baharat","Karabiber","Pul Biber"],
        "ex":  ["Cips","Kraker","Bisküvi","Köfte Harcı","Pane Harcı",
                "Salam","Sucuk","Tane","Çekirdek","Mahlep","Zencefil",
                "Zerdeçal","Köri","Tarçın","Kekik","Kimyon","Nane","Anason",
                "Linguine","Noodle","İndomie","Indomie","Mr.Delicious Acı Baharatlı Yağ","Salsa Macha","Vegeta Baharatlı","Hayfene Kek Pasta","Mayi Baharatlı Tuz"],
        "unit": "kg",
        "require_weight": True,
        "max_price_per_kg": 2000,
    },
    "Linden / Herbal Tea": {
        "kat": "İçecek",
        "sub": ["Bitki Çayı"],
        "kw":  ["Ihlamur","Papatya"],
        "ex":  ["Yüz","Şampuan","Macun","Makinesi","Seti","Soğuk",
                "Kırmızı Meyve","Zencefil"],
        "unit": "piece",
        "require_weight": True,
    },
}

# Seasonal fruit: items in Meyve & Sebze / Meyve that are not staples
SEASONAL_STAPLE_EX = [
    "Elma","Portakal","Mandalina","Muz","Limon","Avokado","Adet","Suyu",
    "Domates","Salatalık","Biber","Patlıcan","Kabak","Patates","Havuç",
    "Soğan","Marul","Maydanoz","Roka","Dereotu","Lahana","Mantar",
    "Ispanak","Brokoli","Enginar","Kereviz","Pırasa","Turp","Sarımsak",
    "Zencefil","Pancar","Nane","Kuru","Hindistan Cevizi","Demirhindi",
    "Meyve Salatası","Physalis","Yer Kirazı","Verita","Excelente",
    "Taze Dilimlenmiş","Taze Ayıklanmış",
    "Ahududu","Böğürtlen","Nar Taneleri","Saluta","Meyve Miksi",
    "Dilimleri","Doğranmış Meyveler","Üzüm İthal","Çekirdeksiz İthal",
]

# ── 4. UTILITIES ────────────────────────────────────────
def extract_weight_g(name: str):
    # "500 G", "500 Gr", "1 Kg", "1,5 Kg", "750 Ml"
    # Note: Macrocenter uses uppercase " G" at end of product name (e.g. "Tea 1000 G")
    m = re.search(r'(\d+[,.]?\d*)\s*(Kg|KG|kg)\b', name)
    if m:
        raw = m.group(1); sep = re.match(r'^(\d+)[,.](\d{3})$', raw)
        return float(sep.group(1)+sep.group(2))*1000 if sep else float(raw.replace(',','.'))*1000
    m = re.search(r'(\d+[,.]?\d*)\s*(Gr\.|Gr|GR|G|g)\b', name)
    if m:
        raw = m.group(1); sep = re.match(r'^(\d+)[,.](\d{3})$', raw)
        return float(sep.group(1)+sep.group(2)) if sep else float(raw.replace(',','.'))
    return None

def extract_volume_ml(name: str):
    m = re.search(r'(\d+[,.]?\d*)\s*(L|Lt|Lt\.)\b', name)
    if m: return float(m.group(1).replace(',','.'))*1000
    m = re.search(r'(\d+[,.]?\d*)\s*(Ml|ml|ML)\b', name)
    if m: return float(m.group(1).replace(',','.'))
    return None

def extract_piece_count(name: str):
    m = re.search(r"(\d+)['\u2019]?\s*(?:li|lu|lı|lü|'li|'lu)\b", name, re.IGNORECASE)
    if m: return int(m.group(1))
    m2 = re.search(r"(\d+)'?\s*[Ll][Üü]\b", name)
    if m2: return int(m2.group(1))
    m3 = re.search(r"(\d+)\s*[Aa]det", name)
    if m3: return int(m3.group(1))
    return None

def is_sold_by_kg(name: str) -> bool:
    return bool(re.search(r'(?<!\d)\s*Kg\.?\s*$', name.strip()))

# ── 5. UNIT PRICE CALCULATOR ────────────────────────────
def get_unit_price(df: pd.DataFrame, product_label: str) -> dict:
    rule = MATCH_RULES[product_label]

    sub = df[df['Category'] == rule['kat']].copy()

    if not rule['kw']:
        return {'unit_price': float('nan'), 'n_products': 0, 'matched_names': 'N/A'}

    mask = sub['Name'].apply(
        lambda x: any(k.lower() in str(x).lower() for k in rule['kw'])
    )
    sub = sub[mask]
    for exc in rule['ex']:
        sub = sub[~sub['Name'].str.contains(exc, case=False, na=False)]

    if sub.empty:
        return {'unit_price': float('nan'), 'n_products': 0, 'matched_names': '—'}

    unit  = rule['unit']
    req_w = rule.get('require_weight', False)
    min_p = rule.get('min_price_per_kg', 0)
    max_p = rule.get('max_price_per_kg', None)
    prices = []

    for _, row in sub.iterrows():
        name  = str(row['Name'])
        price = float(row['Price'])

        if unit == 'kg':
            if is_sold_by_kg(name):
                per_u = price
            else:
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
        n[:45] + ('…' if len(n) > 45 else '') for n in sub['Name'].tolist()
    )
    return {'unit_price': round(avg, 2), 'n_products': len(prices), 'matched_names': names}


def get_seasonal_fruit_price(df: pd.DataFrame) -> dict:
    sub = df[(df['Category'] == 'Meyve & Sebze') &
             (df['Subcategory'] == 'Meyve')].copy()
    for exc in SEASONAL_STAPLE_EX:
        sub = sub[~sub['Name'].str.contains(exc, case=False, na=False)]

    MAX_SEASONAL = 600   # Macrocenter: cap at ₺600/kg for seasonal fruit
    prices = []
    for _, row in sub.iterrows():
        name  = str(row['Name'])
        price = float(row['Price'])
        if is_sold_by_kg(name):
            per_kg = price
        else:
            w = extract_weight_g(name)
            per_kg = price / (w / 1000) if w and w > 0 else price
        if per_kg <= MAX_SEASONAL:
            prices.append(per_kg)

    avg   = sum(prices) / len(prices) if prices else float('nan')
    names = '; '.join(n[:45] for n in sub['Name'].tolist())
    return {'unit_price': round(avg, 2), 'n_products': len(prices), 'matched_names': names}

# ── 6. MONTHLY COMPUTATION ──────────────────────────────
def compute_hunger_threshold(csv_path: str, date_label: str) -> pd.DataFrame:
    df = pd.read_csv(csv_path, encoding='utf-8-sig')
    df = df.drop_duplicates(subset=['SKU'])
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
