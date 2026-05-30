"""
Hunger Threshold Calculator — CarrefourSA
=========================================================
Data source : CarrefourSA online grocery prices
Basket      : Presentation slide 8 (family of 4, monthly quantities)

CSV structure:
  product_name, price (TL)   (comma separator, price already float)
"""

import pandas as pd
import re
from pathlib import Path

# ─────────────────────────────────────────────────────
# 1.  PATHS  ←  edit BASE_DIR to your folder
# ─────────────────────────────────────────────────────
BASE_DIR = "/Users/efeyildirim/Downloads/Marketler/CarrefourSA"

FILES = {
    "Feb-23 2026": f"{BASE_DIR}/carrefourSA_2026-02-23.csv",
    "Feb-27 2026": f"{BASE_DIR}/carrefourSA_2026-02-27.csv",
    "Mar 2026":    f"{BASE_DIR}/carrefourSA_2026-03-31.csv",
    "Apr 2026":    f"{BASE_DIR}/carrefourSA_2026-04-30.csv",
    "May 2026":    f"{BASE_DIR}/carrefourSA_2026-05-18.csv",
}

OUTPUT_DETAIL  = f"{BASE_DIR}/hunger_threshold_detail.csv"
OUTPUT_SUMMARY = f"{BASE_DIR}/hunger_threshold_summary.csv"

# ─────────────────────────────────────────────────────
# 2.  FOOD BASKET  (slide 8, family of 4)
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
MATCH_RULES = {
    # ── Dairy ────────────────────────────────────────
    "Milk": {
        "kw":  ["Süt"],
        "ex":  ["Çocuk","Bebek","Devam Sütü","Arı Sütü","Süt Reçeli","Süt Köpürtücü",
                "Süt Saklama","Laktozsuz","Aromalı","Karamel","Çikolatalı","Muzlu",
                "Çilekli","Soya","Badem","Yulaf","Hindistan","Fındık","Yemeklik",
                "Krema","Peynir","Kefir","Ayran","Sütlü","Kaymak","Sütlaç","Salep",
                "İçimino","Kido","Milkshake","Şekersiz","Labne","Keçi","Pirinç",
                "Yoğurt","Tereyağ","Reçel","Köpürtücü","Hipp","Aptamil","Bebelac",
                "Sma","Latte","Barista","Organik","Cam Şişe","Protein","Mısır",
                "Dilimi","Burger","Köpük","Vücut Sütü","Duş Jeli","Şampuan",
                "Losyon","Bakım","Dondurma","Baltalı","Danette","Bubble","Babymix",
                "Massimo","Milka","Dp Saç"],
        "unit": "ml_or_L",
        "max_price_per_kg": 150,
    },
    "Yogurt": {
        "kw":  ["Yoğurt"],
        "ex":  ["Meyveli","Organik","Kaymaklı","Süzme","Çırpılmış","Probiyotik",
                "Laktozsuz","Çilek","Aromalı","Quark","Tava","Cipsi","Kedi","Köpek",
                "Puding","Mix","Dip","Cips","Meze","Babymix","Babyplus","Mama",
                "Fermente Yoğurt","Movenpick","Movenpic","Yoğurtlu","Yoğurt Sütü","Yoğurt Filling","Lay's","Lays","Sek Pastörize Yoğurt Sütü"],
        "unit": "kg",
    },
    "White Cheese": {
        "kw":  ["Beyaz Peynir","Klasik Peynir"],
        "ex":  ["Kaşar","Lor","Dil","Örgü","Çeçil","Misto","Laktozsuz","Sürülebilir",
                "Tulum","Krem","Mozzarella","Hellim","Süzme","Labne","Tost","Bisküvi"],
        "unit": "kg",
    },
    "Kashar / Other Cheese": {
        "kw":  ["Kaşar"],
        "ex":  ["Bisküvi","Cipsi","Soslu","Sandviç","Köfte","Poğaça"],
        "unit": "kg",
    },
    # ── Meat & Protein ───────────────────────────────
    "Minced Meat": {
        "kw":  ["Dana Kıyma","Kıyma"],
        "ex":  ["Köfte","Döner","Burger","Sosis","Kaşarlı","Soslu","Hindi","Map",
                "Börek","Mantı","Lahmacun","Pide","Hazır","Donuk","Gül Böreği","Hamur"],
        "unit": "kg",
    },
    "Cubed Meat / Lamb Meat": {
        "kw":  ["Dana Kuşbaşı","Kuzu Kuşbaşı","Kuşbaşı"],
        "ex":  ["Hindi","Sote","Köfte"],
        "unit": "kg",
    },
    "Chicken": {
        "kw":  ["Piliç","Bütün Tavuk","Tavuk But","Tavuk Göğüs","Tavuk Kanat",
                "Tavuk Baget","Tavuk Bonfile","Tavuk Pirzola"],
        "ex":  ["Döner","Nugget","Köfte","Kroket","Çıtır","Kebap","Soslu","Sarma",
                "Kedi","Köpek","Suyu","Organik","Salam","Sosis","Füme","Sucuk",
                "Jambon","Schnitzel","Burger","Baharatlı","Baharat","Jülyen",
                "Kazandibi","Sandviç","Tütsülenmiş","Macar"],
        "unit": "kg",
    },
    "Fish": {
        "kw":  ["Levrek","Çupra","Somon Dilim","Hamsi","Alabalık"],
        "ex":  ["Füme","Konserve","Marine","Poşet","Kedi","Köpek","Leröy","Dardanel"],
        "unit": "kg",
    },
    "Eggs": {
        "kw":  ["Yumurta"],
        "ex":  ["Kedi","Köpek","Maması","Mini","Şeker","Kurabiye","Tatlı",
                "Makarna","Erişte","Waffle","Ozmo","Çikolata","Bisküvi","Kinder Sürpriz","Ferrero"],
        "unit": "piece",
    },
    # ── Legumes ──────────────────────────────────────
    "Dried Beans": {
        "kw":  ["Kuru Fasulye","İri Kuru Fasulye","Dermason Fasulye"],
        "ex":  ["Konserve","Haşlanmış","Turşu","Soya","Siyah","Chung","Lee",
                "Etli","Organik","1 g","Çayeli"],
        "unit": "kg",
        "min_price_per_kg": 10,
        "max_price_per_kg": 500,
    },
    "Chickpeas": {
        "kw":  ["Nohut"],
        "ex":  ["Konserve","Haşlanmış","Pilav","Un","Çorba","Organik","1 g",
                "Cipsi","Cips","Fırınlanmış","Dr. Oetker","Dr.Oetker","Knorr",
                "Ülker","Eti ","Mentos","Palette","Maxx","Bisküvi","Çikolata",
                "Köpek","Kedi","Reflex","Magic","Sakız","Hero","Erişte","Baharatlı",
                "Etli","Hazır Yemek"],
        "unit": "kg",
        "min_price_per_kg": 10,
        "max_price_per_kg": 500,
    },
    "Red Lentils": {
        "kw":  ["Kırmızı Mercimek"],
        "ex":  ["Çorba","Un","Organik","1 g","Makarna","Erişte",
                "Dr. Oetker","Dr.Oetker","Knorr","Ülker","Eti ","Mentos",
                "Palette","Maxx","Bisküvi","Köpek","Kedi","Reflex","Magic","Sakız"],
        "unit": "kg",
        "min_price_per_kg": 10,
        "max_price_per_kg": 500,
    },
    "Green Lentils": {
        "kw":  ["Yeşil Mercimek"],
        "ex":  ["Çorba","Un","Organik","1 g","Makarna","Erişte",
                "Dr. Oetker","Dr.Oetker","Knorr","Ülker","Eti ","Mentos",
                "Palette","Maxx","Bisküvi","Köpek","Kedi","Reflex","Magic","Sakız"],
        "unit": "kg",
        "min_price_per_kg": 10,
        "max_price_per_kg": 500,
    },
    # ── Nuts ─────────────────────────────────────────
    "Walnut / Hazelnut / Peanut": {
        "kw":  ["Ceviz İçi","Fındık İçi","Fıstık İçi","Yer Fıstığı","Tuzlu Yer Fıstığı",
                "Tuzsuz Yer Fıstığı","Fındık İçi Kg","Kabuklu Yer Fıstığı","İç Yer Fıstığı"],
        "ex":  ["Ezmesi","Kreması","Çikolata","Cips","Soslu","Aromalı","Kedi","Köpek",
                "Bisküvi","Kurabiye","Gofret","Bar","Hindistan","Baklava","Salam","Sucuk",
                "Turp","Granola","Protein","Çıtır Kaplamalı","Taco","Acı Baharatlı"],
        "unit": "kg",
    },
    # ── Grains ───────────────────────────────────────
    "Bread": {
        "kw":  ["Ekmek"],
        "ex":  ["Hamburger","Sandviç","Tost","Lavaş","Tortilla","Gevrek","Kızarmış",
                "Panko","Kırıntısı","Grissini","Wasa","Kıtır","Humus","Organik",
                "Cips","Glutensiz","Makinesi","Schar","Eti Form","Cicibebe",
                "Bruschette","Ruşeymi","Altınçörek","Unabella"],
        "unit": "kg",
        "min_price_per_kg": 50,
        "max_price_per_kg": 350,
    },
    "Rice": {
        "kw":  ["Pirinç"],
        "ex":  ["Gevreği","Gevrek","Kek","Sirke","Kraker","Vafle","Köpek","Kedi",
                "Bebek","Organik","Patlağı","Patlak","Sushi Pirinç","Yufkası",
                "Risotto","Şehriye","Unu","Vermicelli","Bebelac","Hipp","Hero",
                "Aptamil","Soul Kitchen","Scotti","Tilda","Okomesan","Riso",
                "Gong","Kupiec","Benlian","Şölen","Rice Up","Sade Organik",
                "Organik Gurme","City Farm","Doyum","Milupa","Bebek Çorbası","Pirinçli Tavuk Çorbası"],
        "unit": "kg",
        "max_price_per_kg": 400,
    },
    "Bulgur": {
        "kw":  ["Bulgur"],
        "ex":  ["Kek","Çorba"],
        "unit": "kg",
    },
    "Pasta": {
        "kw":  ["Makarna"],
        "ex":  ["Sosu","Peyniri","Knorr","Tortellini","Lazanya","Rendelenmiş","Erişte","Tas Brand","Pirinç Makarna"],
        "unit": "kg",
    },
    "Flour": {
        "kw":  ["Söke Un","Sinangil Un","Carrefour Un","Nuh'un Un","Beypazarı Un","Organik Un","Çavdar Un"],
        "ex":  ["Sosis","Sucuk","Salam","Köfte","Hindi","Dana","Peynir","Krema","Ezmesi",
                "Galeta","Mısır","Nişasta","Glutensiz","Hazır","Karışımı","Kek","Kurabiye",
                "Keçiboynu","Semolina","Baklavalık","Böreklik","Kepekli","Tam Buğday"],
        "unit": "kg",
    },
    "Semolina": {
        "kw":  ["İrmik"],
        "ex":  ["Helvası","Tatlı","Bebek","Hero","Aptamil","Bebelac","Organik",
                "Soul Kitchen"],
        "unit": "kg",
    },
    # ── Fruits ───────────────────────────────────────
    "Apple": {
        "kw":  ["Elma"],
        "ex":  ["Suyu","Kurusu","Kek","Kurabiye","Aromalı","Saç","Boyası","Şampuan",
                "Hindistan","Meyve Topu","Çayı","Sirke","Granola","Mantı","Püresi",
                "Maması","Barı","Gofreti","Bebek","Organik","Dilim Patates","Bebe",
                "Milupa","Gerber","Hero","Hipp","Bebelac","Frenk","Deterjani","Puf",
                "Missbon","Rawberry","Anamour","Tırtıklı","La Lorraine","Cookies",
                "Nektarı","Tetra","Pet","Cam","Kefir","Detoks","Sırma","Sarıkız",
                "Uludağ","Palette","Sabun","Naren","Cappy","Dimes","Sizzle","Corny","Protein Bar","Freeze Dried","Golf Manav","Meyve Suyu","Smoothie","Cipsi","Cipsleri"],
        "unit": "kg",
        "require_weight": False,
        "max_price_per_kg": 300,
    },
    "Orange / Mandarin": {
        "kw":  ["Portakal","Mandalina"],
        "ex":  ["Suyu","Gazoz","Aromalı","Schweppes","Fanta","Reçel","Çayı","Sirke",
                "Püresi","Bebek","Bisküvi","Draje","Jöle","Puding","Tofita","Tart",
                "Çikolata","Gofret","Kek","Bar","Soda","Nektarı","Tetra","Pet","Cam",
                "Cappy","Dimes","Yedigün","Kefir","Beta Fusion","Duru","Selin",
                "Pereja","Rebul","Colonya","Kolonya","Pronto","Cif","Air Wick",
                "Pril","Bingo","Sleepy","Fibril","Havlusu","Mendil","San Pellegrino",
                "Uludağ","Sarıkız","Sırma","Fellas","Hopbidi","Balanu","Dalin",
                "Naren","Olips","Ülker Piko","Ülker 9 Kat","Ülker Yupo","Şölen",
                "Eti","Züber","Go Ahead","Dovido","Beyoğlu","Portakal Çiçeği","Kakao Portakal","Kurabiye","Hipp","Bebek Püresi","U Green Clean","Sabun","Yüzey Temizleme","Deterjan"],
        "unit": "kg",
        "require_weight": False,
        "max_price_per_kg": 300,
    },
    "Banana": {
        "kw":  ["Muz"],
        "ex":  ["Muzlu","Kurusu","Aromalı","Püresi","Bebek","Tahıl","Bar",
                "Gofret","Çikolata","Kek","Bisküvi","Corny","Eti","Dovido",
                "Hazz","Fellas","Gerber","Hero","Mama","Protein","Granola",
                "Şıpsevdi","Multi","Furito","Parisian","Organik Muz Elma",
                "Kakao-Muz","Muz-Çilek",
                "Activia","Naren","Bowl","Probiyotikli"],
        "unit": "kg",
        "max_price_per_kg": 300,
    },
    # ── Vegetables ───────────────────────────────────
    "Potato": {
        "kw":  ["Patates"],
        "ex":  ["Kızartmalık","Cips","Dondurulmuş","Harcı","Köpek","Kedi","Tatlı",
                "Baby","Gnocchi","Kroket","Börek","Nuggets","Püresi","Sosu",
                "Çeşnisi","Garnitür","Parmak","Churros","Superfresh","Feast",
                "Frytime","Onefis","Pek","La Lorraine","Poğaça","Privegi","Büyük Gül",
                "Tavuk","Soslu","Tada"],
        "unit": "kg",
        "require_weight": False,
        "max_price_per_kg": 100,
    },
    "Onion": {
        "kw":  ["Soğan"],
        "ex":  ["Taze","Arpacık","Mor","Dondurulmuş","Aromalı","Turşu",
                "Frenk","Toz","Kurutulmuş","Çerez","Cips","Kraker","Fıstık",
                "Burgu","Peynirli","Ekşi","Karamel","Kaju","Kroket","Halka",
                "Küp","Superfresh","Feast",
                "Gerber","Kaplamalı","Barbekü","Bisküvi"],
        "unit": "kg",
        "require_weight": False,
        "max_price_per_kg": 100,
    },
    "Tomato": {
        "kw":  ["Domates"],
        "ex":  ["Salça","Kurutulmuş","Konserve","Rende","Sosu","Suyu","Çorba",
                "Köpek","Kedi","Kokteyl","Şeker","Püresi","Kraker","Cips",
                "Bruschetta","Grissini","Ekmek","Bar","Fesleğen","Sos","Mini Domates","Doğranmış","Kepekli Domatesli","Kurusu","Gerber","Atıştırmalık","Form "],
        "unit": "kg",
        "require_weight": False,
        "max_price_per_kg": 300,
    },
    "Cucumber": {
        "kw":  ["Salatalık"],
        "ex":  ["Turşu","Deodorant","Şampuan","Temizlik","Kühne"],
        "unit": "kg",
    },
    "Pepper": {
        "kw":  ["Biber"],
        "ex":  ["Pul","Toz","Turşu","Konserve","Közlenmiş","Aromalı","Salam","Sucuk",
                "Cips","Çerez","Kraker","Sos","Reçel","Frenk","Karabiber","Peynir",
                "Salça","Zeytinyağı","Zeytin","Füme","Ezmesi","Dolma","Dolgu",
                "Biberon","Biberiye","Emzik","Sarımsak","Isot","İsot","Öğütülmüş",
                "Tane","Çikolata","Grissini","Organik","Baharat","Primavera","Gouda Biberli","Edam Biberli","Bağdat Tatlı Kırmızı Biber","Bağdat Acı Kırmızı Biber","Bağdat Değirmen","Hatice Teyze Yakan","Crax Thins","Eti Crax","Oddly","Hibiscus"],
        "unit": "kg",
        "require_weight": False,
        "max_price_per_kg": 400,
    },
    "Eggplant / Zucchini": {
        "kw":  ["Patlıcan","Kabak"],
        "ex":  ["Közlenmiş","Konserve","Turşu","Kedi","Köpek","Çekirdeği","Çekirdek",
                "Ezmesi","Salatası","Mücveri","Dolma","Börek","Kızartma",
                "Yoğurtlu","Lifi","Kesesi","Boyası","Granola","Çorbası",
                "Püresi","Bebek","Sarması","Karışımı","Kavrulmuş","İç Kabak",
                "Bahçeden","Hero","Balmy"],
        "unit": "kg",
    },
    "Carrot": {
        "kw":  ["Havuç"],
        "ex":  ["Kedi","Köpek","Maması","Kek","Kurabiye","Püresi","Bebek","Suyu",
                "Köftesi","Çorbası","Kefir","Organik","Sızma","Şampuan",
                "Gurvita","Sizzle","Dimes","Exotic","Naren","Elite","Hipp",
                "Milupa","Gerber","Hero"],
        "unit": "kg",
        "require_weight": False,
        "max_price_per_kg": 200,
    },
    "Greens / Lettuce / Parsley": {
        "kw":  ["Marul","Maydanoz","Roka","Dereotu","Kıvırcık"],
        "ex":  ["Kedi","Köpek","Krokan","Falafel","Keratin","Şampuan","Bakım",
                "Saç","Serum","Kürü"],
        "unit": "piece",
    },
    "Other Vegetables": {
        "kw":  ["Mantar","Lahana","Ispanak","Brokoli","Enginar"],
        "ex":  ["Konserve","Turşu","Kedi","Köpek","Aromalı","Börek","Çorba",
                "Sos","Risotto","Pesto","Zeytinyağı","Ezmesi","Sarması",
                "Köftesi","Mantı","Lasagne","Organik","Fettuccini",
                "Kavanoz","Gurvita","Hatice","Queen","Kühne","Monini",
                "Knorr","Bizim Mutfak","Superfresh","Feast","Pek","Galez",
                "Onefis","Elmasoğlu","Veg & Bones","Scotti","Bemtat"],
        "unit": "kg",
    },
    # ── Oils ─────────────────────────────────────────
    "Sunflower Oil": {
        "kw":  ["Ayçiçek Yağı"],
        "ex":  ["Teneke","Sprey","Ton Balık"],
        "unit": "ml_or_L",
    },
    "Olive Oil": {
        "kw":  ["Zeytinyağı"],
        "ex":  ["Ton Balık","Kedi","Sabun","Sprey","Margarin","Salam","Sucuk",
                "Şampuan","Kekikli","Füme","Zeytinli","Mantarlı","Sarımsaklı",
                "Acıbiberli","Islak Havlu","Nemlendirici","Bakım","Kolonya",
                "Losyon","Duş","Bebek","Peros"],
        "unit": "ml_or_L",
        "max_price_per_kg": 2000,
    },
    "Butter": {
        "kw":  ["Tereyağ","Tereyağı"],
        "ex":  ["Margarin","Bitkisel","Kekikli","Donuk","Salyangoz","Soslu","Kremalı",
                "Kurabiye","Bisküvi","Şeker","Milföy","Kruvasan","Karides",
                "Kırıkkırak","Fasulyesi","Sarımsaklı","Biberiyeli"],
        "unit": "kg",
    },
    "Margarine": {
        "kw":  ["Margarin"],
        "ex":  ["Şişe","Profesyonel","Kruvasan","Tereyağ"],
        "unit": "kg",
    },
    # ── Breakfast ────────────────────────────────────
    "Olives": {
        "kw":  ["Zeytin"],
        "ex":  ["Yağ","Ezmesi","Sabun","Şampuan","Zeytinyağlı","Kekikli","Marine",
                "Hamsi","Labne","Salam","Sucuk","Füme","Bisküvi","Kraker","Köfte",
                "Sandviç","Açma","Kırıkkırak","Grissini","Gevrek","Lifi","Baharatı",
                "Salatası","Eti Form","Danvıta","Galez","Tada","Sürmix","Komili Ege"],
        "unit": "kg",
    },
    # ── Other Food ───────────────────────────────────
    "Sugar": {
        "kw":  ["Toz Şeker"],
        "ex":  ["Küp","Esmer","Vanilin","Şekersiz","Aromalı"],
        "unit": "kg",
    },
    "Tea": {
        "kw":  ["Çay"],
        "ex":  ["Bitki","Soğuk","Meyve","Ihlamur","Papatya","Poşet","'lü","'li",
                "Aromalı","Kek","Fasulye","Bardağı","Seti","Tabağı","Saati","Çaycı",
                "Fuse","Soda","x15","x20","x25","x30","x40","Şampuan","Sabun",
                "Makinesi","Semaver","Deterjan","Çamaşır","Macun","Diş","Kireç",
                "Kurabiye","Kefir","Elma Çayı","Çay Makinesi","Buzlu Çay","Ice Tea","Soğuk Çay","Didi","Deodorant","Çay Makinası","Arnica","Arzum"],
        "unit": "kg",
        "require_weight": True,
        "max_price_per_kg": 1000,
    },
    "Tomato Paste": {
        "kw":  ["Domates Salçası","Domates Salça"],
        "ex":  ["Biber"],
        "unit": "kg",
    },
    "Jam": {
        "kw":  ["Reçel"],
        "ex":  ["Diabetik","Ceviz","Biber","Havuç","Goji","Aronya","Süt Reçeli",
                "Karamelize","Kestane","Ganik","Korovka","Carrefour Süt","Ülker Dido",
                "Bonne Maman Karamelize","Bonne Maman Sürülebilir"],
        "unit": "kg",
    },
    "Honey": {
        "kw":  ["Süzme Bal","Çiçek Balı","Çam Balı","Kestane Balı","Karakovan Balı",
                "Yayla Balı","Narenciye Balı","Bingöl Balı","Krem Bal"],
        "ex":  ["Köpüğü","Balsam","Balzamik","Balık","Baldo","Balmy","Balanu",
                "Balacco","Balküpü","Baltalı","Ödül","Havlu","Sabun","Kedi","Köpek",
                "Bebek","Macun","Şampuan","Makinesi"],
        "unit": "kg",
        "max_price_per_kg": 2000,
    },
    "Molasses": {
        "kw":  ["Pekmez"],
        "ex":  ["Sucuk","Tahin","Hero Baby","Mama","Bebek","Tahıllı"],
        "unit": "kg",
    },
    "Salt": {
        "kw":  ["Tuz"],
        "ex":  ["Tuzlu","Tuzsuz","Bulaşık","Salamura","Himalaya","Limon","Zeytinli",
                "Bisküvi","Kurabiye","Peynir","Tereyağ","Az Tuzlu","Lurpak","Turşu",
                "Soya","Duş Jeli","Şampuan","Lifi","Makinesi","Ekmek","Fıstık",
                "Çekirdek","Etimek","Palmolive","Duru","Mayi","Kaya","Deniz","Öğütme","Tuzot","Çeşni","Maldon","Değirmeni","Finish","Temizlik","Kalahari","Çöl Tuzu"],
        "unit": "kg",
        "require_weight": True,
        "max_price_per_kg": 200,
    },
    "Average Spices": {
        "kw":  ["Baharat","Karabiber","Pul Biber"],
        "ex":  ["Patates","Çam Fıstık","Kedi","Köpek","Kek","Salam","Sucuk","Füme",
                "Cips","Çerez","Kraker","Noodle","Erişte","Mısır","Nohut","Cipsi",
                "Bisküvi","Çikolata","Saç","Fıstık","Grissini","Zeytin","Fesleğen",
                "Magic","Lay","Eti Crax","Ülker","Gong","Züber","Çerezza","Master",
                "Carrefour Veggie","Saksı","Rozmarin","Nane","Gouda","Rozbif",
                "Indomie","Marmarabirlik","Taze Baharat","Çeşitleri","Susam",
                "Tarçın","Zencefil","Kajun","Tavuk Çeşnisi","Piliç Baharatı",
                "Kanatlı","Mangal","Roasbeef","Tereyağ","Kaşar","Tahsildaroğlu","Tadım Acı Baharatlı Yer Fıstığı","Tadım Taco Baharatlı","Çıtır Kaplamalı Yer Fıstığı","Sarımsak Baharatlı Püre"],
        "unit": "kg",
        "require_weight": True,
        "max_price_per_kg": 2000,
    },
    "Linden / Herbal Tea": {
        "kw":  ["Ihlamur","Papatya Çayı","Bitki Çay"],
        "ex":  ["Meyve","Havlu","Sabun","Mendil","Mama","Yüz","Şampuan",
                "Losyon","Macun","Makinesi","Pastil","Ekmek","Mate",
                "Beta Tea","Beta Herbtea","Herby","Naturali"],
        "unit": "piece",
    },
}

SEASONAL_EXCLUDE = ["Elma","Portakal","Mandalina","Muz","Limon","Avokado","Adet",
                    "Suyu","Gazoz","Aromalı","Kedi","Köpek","Kurusu","Kek","Bisküvi",
                    "Patates","Soğan","Domates","Salatalık","Biber","Patlıcan","Kabak",
                    "Havuç","Marul","Lahana","Ispanak","Mantar","Enginar","File",
                    "Hindistan","Saç","Boyası","Pirinç","Risotto","İncir Tatlısı",
                    "Milföy","Börek","Hamur","Yufka","Krep","Sütlaç","Dondurma",
                    "Çikolata","Bisküvi","Kek","Gofret","Kavanoz","Konserve","Reçel"]

FRUIT_KEYWORDS = ["Elma","Armut","Kiraz","Erik","Şeftali","Kayısı","İncir","Kivi",
                  "Çilek","Karpuz","Kavun","Nar","Üzüm","Vişne","Greyfurt","Limon"]

# ─────────────────────────────────────────────────────
# 4.  UTILITIES
# ─────────────────────────────────────────────────────

def extract_weight_g(name: str):
    m = re.search(r"(\d+[,.]?\d*)\s*(KG|GR|G)\b", name.upper())
    if m:
        v = float(m.group(1).replace(",","."))
        return v * 1000 if m.group(2) == "KG" else v
    return None

def extract_volume_ml(name: str):
    # Normalise "Litre"/"litre"/"lt" → "L"
    n = re.sub(r"\blitre\b", "L", name, flags=re.IGNORECASE)
    n = re.sub(r"\blt\b",    "L", n,    flags=re.IGNORECASE)
    n = n.upper()
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
    m = re.search(r"(\d+)['\u2019]?(LU|Lİ|LI|li|lu)\b", name, re.IGNORECASE)
    if m:
        return int(m.group(1))
    m2 = re.search(r"(\d+)\s*Adet", name, re.IGNORECASE)
    if m2:
        return int(m2.group(1))
    return None

def shorten(name: str, max_len: int = 45) -> str:
    return name if len(name) <= max_len else name[:max_len-1] + "…"

# ─────────────────────────────────────────────────────
# 5.  COMPUTE UNIT PRICE FOR ONE BASKET ITEM
# ─────────────────────────────────────────────────────

def get_unit_price(df: pd.DataFrame, product_label: str) -> dict:
    rule = MATCH_RULES[product_label]

    if not rule["kw"]:
        return {"product_label": product_label, "unit": rule["unit"],
                "unit_price": float("nan"), "n_products": 0, "matched_names": "N/A"}

    sub  = df.copy()
    kw_m = sub["product_name"].apply(
        lambda x: any(k.lower() in str(x).lower() for k in rule["kw"])
    )
    sub  = sub[kw_m]
    for exc in rule["ex"]:
        sub = sub[~sub["product_name"].str.contains(exc, case=False, na=False)]

    if sub.empty:
        return {"product_label": product_label, "unit": rule["unit"],
                "unit_price": float("nan"), "n_products": 0, "matched_names": "—"}

    sub  = sub.copy()
    sub["price"] = pd.to_numeric(sub["price (TL)"], errors="coerce")
    sub  = sub.dropna(subset=["price"])

    unit            = rule["unit"]
    req_weight      = rule.get("require_weight", False)
    min_price_per_u = rule.get("min_price_per_kg", 0)
    max_price_per_u = rule.get("max_price_per_kg", None)
    prices = []

    for _, row in sub.iterrows():
        name  = str(row["product_name"])
        price = row["price"]

        if unit == "kg":
            w = extract_weight_g(name)
            if not w:
                # If "kg" appears in name without a number, item is sold by weight
                # and the price IS already per-kg (e.g. "Starking Elma kg")
                if "kg" in name.lower():
                    per_u = price  # already per-kg
                elif req_weight:
                    continue  # no weight info at all → skip
                else:
                    per_u = price
            else:
                per_u = price / (w / 1000)
            if per_u < min_price_per_u:
                continue
            if max_price_per_u and per_u > max_price_per_u:
                continue
            prices.append(per_u)

        elif unit == "ml_or_L":
            v = extract_volume_ml(name) or extract_weight_g(name)
            per_u_vol = price / (v / 1000) if v and v > 0 else price
            if max_price_per_u and per_u_vol > max_price_per_u:
                continue
            prices.append(per_u_vol)

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
    names = "; ".join(shorten(n) for n in sub["product_name"].tolist())
    return {"product_label": product_label, "unit": unit,
            "unit_price": round(avg, 2), "n_products": len(prices),
            "matched_names": names}

def get_seasonal_fruit_price(df: pd.DataFrame) -> dict:
    sub = df[df["product_name"].apply(
        lambda x: any(f.lower() in str(x).lower() for f in FRUIT_KEYWORDS) and
                  "kg" in str(x).lower()
    )].copy()
    for exc in SEASONAL_EXCLUDE:
        sub = sub[~sub["product_name"].str.contains(exc, case=False, na=False)]
    prices = []
    for _, row in sub.iterrows():
        w = extract_weight_g(str(row["product_name"]))
        price = float(row["price (TL)"])
        prices.append(price / (w / 1000) if w and w > 0 else price)
    avg   = sum(prices) / len(prices) if prices else float("nan")
    names = "; ".join(shorten(n) for n in sub["product_name"].tolist())
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
