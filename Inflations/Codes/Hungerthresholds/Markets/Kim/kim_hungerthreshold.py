import re
import pandas as pd
from pathlib import Path

# ── 1. PATHS ────────────────────────────────────────────
BASE_DIR = "/Users/efeyildirim/Downloads/Marketler/Kim"

FILES = {
    "Feb-23 2026": f"{BASE_DIR}/products-02-23.csv",
    "Feb-28 2026": f"{BASE_DIR}/products2-28.csv",
    "Mar 2026":    f"{BASE_DIR}/products3-31.csv",
    "Apr 2026":    f"{BASE_DIR}/products4-30.csv",
    "May 2026":    f"{BASE_DIR}/products5-26.csv",
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
# Kim Market has NO category column — keyword-only matching
# All product names are UPPERCASE
MATCH_RULES = {
    "Milk": {
        "kw":  ["SUTAS SUT","ICIM SUT","PINAR SUT","YORUKOGLU SUT","TORKU SUT",
                "TEKSUT SUT","DANONE SUT"],
        "ex":  ["AYRAN","KAKAO","CILEK","MUZLU","AROMALI","SOYA","BADEM","YULAF",
                "KEFIR","SUTLU","KAYMAK","SUTLAC","KIDO","ICIMINO","NESQUIK",
                "DEVAM","BEBEK","KREMA","SUT RECELI","ORGANIK","LAKTOZSUZ",
                "PROTEINLI","200 ML","180 ML","SATIN","PROTEIN","COCUK",
                "AROMALI SUT","KIDO","UYUMIX","BUYUMIX","6*180","UHT 200"],
        "unit": "ml_or_L",
        "max_price_per_kg": 200,
    },
    "Yogurt": {
        "kw":   ["YOGURT","YOĞURT"],
        "ex":   ["MEYVELI","ORGANIK","KAYMAKLI","CIRPILMIS","LAKTOZSUZ","CILEK",
                 "AROMALI","TAVA","DIP","CIPS","KEFIR","BEBEK","MAMA","PUDING",
                 "PROBIYOTIKLI","FERMENTE","SUZME","CIPSO","LAYS","ACTIVIA",
                 "DANONE YOGURT","LIGHT","TAHILLI","SHOT","MINIMIX","TATLIM",
                 "KABI","KASE","TITIZ","HERO BABY"],
        "unit": "kg",
        "max_price_per_kg": 400,
    },
    "White Cheese": {
        "kw":   ["BEYAZ PEYNIR","TAZE PEYNIR","KLASIK PEYNIR","LUKS TAZE PEY"],
        "ex":   ["KASAR","LOR","DIL","ORGU","CECIL","KREM","MOZZARELLA","LABNE",
                 "TULUM","SUZME","LAKTOZSUZ","TOST","KOLOT","EZINE","DONDURMA",
                 "LIGHT"],
        "unit": "kg",
        "max_price_per_kg": 600,
    },
    "Kashar / Other Cheese": {
        "kw":   ["KASAR","TAZE KASAR"],
        "ex":   ["SANDVIC","KOFTE","POGACA","BISKUVI","BURGER","DIRSEK",
                 "DONDURMA","GOFRET","TOST PEYNIRI","KASARLI","DILIMLI 150","225 GR"],
        "unit": "kg",
        "max_price_per_kg": 700,
    },
    "Minced Meat": {
        "kw":  ["DANA YEMEKLIK KIYMA","KIYMA KG"],
        "ex":  ["DONER","BURGER","SOSIS","KOFTE","MANTI","BOREK","PISMIS"],
        "unit": "kg",
    },
    "Cubed Meat / Lamb Meat": {
        "kw":  ["DANA KUSBASI KG","KUSBASI KG"],
        "ex":  [],
        "unit": "kg",
    },
    "Chicken": {
        "kw":  ["ASPILIC TAB","GEDIK TAB","BEYPILIC TAB","ASPILIC BUTUN PILIC",
                "ASPILIC TAB. BUT"],
        "ex":  ["SOSIS","SALAM","SUCUK","FUME","NUGGET","KOFTE","DONER",
                "KANGAL","SCHNITZEL","BURGER","HARC","BAHARAT"],
        "unit": "kg",
    },
    "Fish": {
        "kw":  [],  
        "ex":  [],
        "unit": "kg",
    },
    "Eggs": {
        "kw":   ["KUMBASAR","YUMURTA","ISTIRANCA GEZEN TAVUK YUMURTASI",
                 "DEL PAKKÖY GEZEN TAVUK YUMURTASI","SAKLIKOY ORGANIK YUMURTA"],
        "ex":   ["BILDIRCIN","KEDI","KOPEK","WAFFLE","MAKARNA","BISKUVI",
                 "KINDER","CIKOLATA","SURPRIZ","OZMO","BABY","TOYBOX"],
        "unit": "piece",
    },
    "Dried Beans": {
        "kw":  ["DERMASON FASULYE","FASULYE DERMASON","KURU FASULYE"],
        "ex":  ["KONSERVE","HASLANMIS","ETLI","ORGANIK"],
        "unit": "kg",
    },
    "Chickpeas": {
        "kw":   ["NOHUT"],
        "ex":   ["KONSERVE","HASLANMIS","CIPSI","CIPS","ORGANIK","CORBA","PILAV",
                 "BULGUR","TAMEK","YUVAM"],
        "unit": "kg",
    },
    "Red Lentils": {
        "kw":  ["KIRMIZI MERCIMEK","IC MERCIMEK"],
        "ex":  ["CORBA","ORGANIK","MAKARNA","ERISTESI"],
        "unit": "kg",
    },
    "Green Lentils": {
        "kw":  ["YESIL MERCIMEK"],
        "ex":  ["CORBA","ORGANIK","MAKARNA"],
        "unit": "kg",
    },
    "Walnut / Hazelnut / Peanut": {
        "kw":  ["CEVIZ ICI","FINDIK ICI","YER FISTIGI"],
        "ex":  ["EZMESI","KREMASI","CIKOLATA","CIPS","SOSLU","AROMALI","BAKLAVA",
                "BISKUVI","GRANOLA","BAR","PROTEIN","GOFRET","KIZARTILMIS",
                "KABUKLU","BAHCEDEN","TUZLU FISTIK","PEYMAN","TADIM","MASTER NUT",
                "KAVSEK","KARISIK","ANTEP"],
        "unit": "kg",
        "max_price_per_kg": 2500,
    },
    "Bread": {
        "kw":   ["EKMEK ADET","SICAK TAVA BAZLAMA","SICAK TAVA KANEPE"],
        "ex":   ["KRAKER","BISKUVI","KIZARMIS","SANDVIC","HAMBURGER","GRISSUNO"],
        "unit": "kg",
        "min_price_per_kg": 40,
        "max_price_per_kg": 300,
    },
    "Rice": {
        "kw":   ["PIRINC","PIRINÇ"],
        "ex":   ["GEVREGI","KEK","SIRKE","PATLAĞI","UNU","ORGANIK","SUSHI",
                 "RISOTTO","BEBEK","SEHRIYE","MAMA","GARNITURLU",
                 "GONG","PATLAK","HERO BABY","NAPOLITEN"],
        "unit": "kg",
        "max_price_per_kg": 350,
    },
    "Bulgur": {
        "kw":  ["BULGUR"],
        "ex":  ["ORGANIK","PILAVI","CORBASI","NOHUTLU","KINOALI","SIYEZLI"],
        "unit": "kg",
    },
    "Pasta": {
        "kw":  ["MAKARNA"],
        "ex":  ["SOSU","KNORR","TORTELLINI","LAZANYA","PEYNIRI","KEDI","KOPEK",
                "SEHRIYE","CORBA","ERTESI","ERISTESI","INDOMIE","BARDAK",
                "PAK.","PAKET SEBZELI","INDOMIE",
                "Soslu","Napoliten","SOSLU","NAPOLITEN"],
        "unit": "kg",
    },
    "Flour": {
        "kw":  ["SOKE UN","TELLIOGLU UN","ERIS UN","DEL.ERIS UN"],
        "ex":  ["GALETA","MISIR","NISASTA","GLUTENSIZ","BAKLAVA","NOHUT","PIRINC"],
        "unit": "kg",
    },
    "Semolina": {
        "kw":  ["IRMIK","İRMİK"],
        "ex":  ["HELVASI","BEBEK","ORGANIK","HERO","PAKMAYA BUĞDAY","PIRINC UNU",
                "HELVASI","OETKER","DR OETKER","ANKARA PIRINC"],
        "unit": "kg",
        "max_price_per_kg": 200,
    },
    "Apple": {
        "kw":  ["ELMA GOLDEN","ELMA STARKING","ELMA GRANNY","ELMA STARKIG"],
        "ex":  ["SUYU","AROMALI","HINDISTAN","KURUSU","KEK","BISKUVI",
                "GRANOLA","SIRKE","SIRKESI","LIFALIF","SODA","GAZOZ"],
        "unit": "kg",
        "max_price_per_kg": 300,
    },
    "Orange / Mandarin": {
        "kw":   ["PORTAKAL","MANDALİNA","MANDALINA"],
        "ex":   ["SUYU","GAZOZ","AROMALI","JOLE","BAR","RECEL","LIMONATA",
                 "ETI CIN","ULKER YUPO","KENT OLIPS","DURU","EKER KEFIR",
                 "CIK.","CIKOLATA","SABUN","SIVI SABUN","TATLI","STICK","CAMLICA","CAPPY","PULPY","AVSAR C PLUS","SIRMA C VITAMINLI","FANTA","YEDIGUN","KOLONYA","DEL.EST","1,5 LT","1.5 LT"],
        "unit": "kg",
    },
    "Banana": {
        "kw":  ["MUZ KG","MUZ İTHAL","MEYVE MUZ"],
        "ex":  ["PURESI","BEBEK","AROMALI","KURUSU","KEFIR","SUT",
                "DANONE","SUTAS","ICIM","PINAR","ACTIVIA","SAKIZ",
                "SIPSEVDI","SIPPO","BIG BABOL","HARIBO","MILKA",
                "NESTLE","KOPUK","BAR","CIPSO","POPKEK","DANKEK"],
        "unit": "kg",
    },
    "Potato": {
        "kw":   ["PATATES TAZE","PATATES KG","PATATES BEYBİ","PATATES BEYBI",
                 "PATATES"],
        "ex":   ["CIPS","KROKET","BOREK","PURESI","POGACA","NUGGETS","DONDURULMUS",
                 "KIZARTMALI","CUMALI","GARNITUR","ELMA DILIMLI","S.FRESH",
                 "FEAST","JUMBO","CITIR","DILIMLEYICI","PENA","WENKEN"],
        "unit": "kg",
    },
    "Onion": {
        "kw":  ["SOĞAN KURU","SOĞAN MOR","SOGAN KURU","SOGAN MOR"],
        "ex":  ["TAZE","ARPACIK","YAHNILIK","DONDURULMUS","TOZU","KROKET","HALKA"],
        "unit": "kg",
    },
    "Tomato": {
        "kw":  ["DOMATES"],
        "ex":  ["SALCA","KURUTULMUS","KONSERVE","KOKTEYL","SOSU","CORBA","RENDE",
                "PEMBE","SALKIM",
                "PURE","Püresi","Pure"],
        "unit": "kg",
    },
    "Cucumber": {
        "kw":  ["SALATALIK"],
        "ex":  ["TURSU","SILOR"],
        "unit": "kg",
    },
    "Pepper": {
        "kw":  ["BİBER KIRMIZI","BİBER KÖY","ÇARLİSTON BİBER","DOLMA BİBER",
                "SİVRİ BİBER","BIBER KIRMIZI","BIBER KOY","CARLISTON BIBER",
                "DOLMA BIBER","SIVRI BIBER"],
        "ex":  [],
        "unit": "kg",
    },
    "Eggplant / Zucchini": {
        "kw":   ["PATLICAN","KABAK"],
        "ex":   ["KOZLENMIS","TURSU","CEKIRDEGI","EZMESI","KEDI","KOPEK",
                 "MAMA","BAL KABAK","SIFALIKOY","DOLMALIK","S.FRESH",
                 "FEAST","KIMIN CIFTE","BULUT","KARNABAHAR","NEVSEHIR",
                 "SALATASI","KOZLEMIS","PATLICAN SALATASI"],
        "unit": "kg",
        "max_price_per_kg": 300,
    },
    "Carrot": {
        "kw":  ["HAVUÇ","HAVUC"],
        "ex":  ["SUYU","PURESI","BEBEK","MINI","KEFIR","AROMALI",
                "FELIX","DANKEK","EKER","KEFIR"],
        "unit": "kg",
        "max_price_per_kg": 200,
    },
    "Greens / Lettuce / Parsley": {
        "kw":  ["GOBEK SALATA","KIVIRCIK ADET","ROKA","DEREOTU DEMET","NANE DEMET",
                "PIRASA"],
        "ex":  [],
        "unit": "piece",
    },
    "Other Vegetables": {
        "kw":   ["MANTAR","LAHANA","ISPANAK","KARNIBAHAR KG","PANCAR KG"],
        "ex":   ["KONSERVE","TURSU","KEDI","KOPEK","SUYU","S.FRESH",
                 "BRUKSEL","PAKETLI","KNORR","BIZIM CORBA","CORBASI",
                 "SOS MAKARNA","MELIS"],
        "unit": "kg",
        "max_price_per_kg": 500,
    },
    "Sunflower Oil": {
        "kw":  ["KOMILI AYCICEK YAGI","YUDUM AYCICEK YAGI"],
        "ex":  ["TENEKE","SPREY"],
        "unit": "ml_or_L",
    },
    "Olive Oil": {
        "kw":  ["KOMILI Z.YAGI","TARIS Z.YAGI","DEL.TARIS"],
        "ex":  ["SABUN","SPREY","SAMPUAN","LOSYON","BEBEK","KONSERVE"],
        "unit": "ml_or_L",
    },
    "Butter": {
        "kw":   ["TEREYAG","TEREYAGI","TEKSUT TEREYAG","SUTAS TEREYAG",
                 "KARLIDAG TEREYAG","KEBIR GURME TEREYAG","TORKU TEREYAG",
                 "PINAR TEREYAG","ICIM TEREYAG"],
        "ex":   ["MARGARIN","BITKISEL","MILFOY","BISKUVI","SEKER","YEMEKLIK",
                 "LEZZETI","KEYFI","KENT","MISSBON","SAKIZ","KARAMEL",
                 "TATLI","CIKO"],
        "unit": "kg",
    },
    "Margarine": {
        "kw":   ["MARGARIN"],
        "ex":   ["TEREYAG","ZEYTINYAGLI","6 LI"],
        "unit": "kg",
    },
    "Olives": {
        "kw":  ["SIYAH ZEYTIN","YESIL ZEYTIN","M.BIRLIK","OLEA","AYDOGMUS"],
        "ex":  ["YAGI","EZMESI","SABUN","ZEYTINYAGLI","BISKUVI","KRAKER",
                "KOFTE","SANDVIC","TURSU"],
        "unit": "kg",
    },
    "Sugar": {
        "kw":  ["TOZ SEKER","SEKER KG"],
        "ex":  ["DOKME","ESMER","KAHVERENGI","ACIK"],
        "unit": "kg",
    },
    "Tea": {
        "kw":  [],  
        "ex":  [],
        "unit": "kg",
    },
    "Tomato Paste": {
        "kw":  ["ONCU SALCA DOMATES","TAMEK DOMATES SALCASI","TAT DOMATES SALCASI",
                "TUKAS SALCA DOMATES","IPEK SALCA","DEL.ONCU SALCA"],
        "ex":  ["BIBER","ACI BIBER"],
        "unit": "kg",
    },
    "Jam": {
        "kw":  ["RECEL","REÇEL"],
        "ex":  ["DIABETIK","SUT RECELI","KESTANE","CEVIZ","JOLE"],
        "unit": "kg",
    },
    "Honey": {
        "kw":   ["BALPARMAK","CANPETEK BAL","CANPETEK TABAKLI"],
        "ex":   ["KABAGI","PROPOLIS","BISKUVI","BAR","PASTA","GRANOLA","NESFIT",
                 "CIKOLATA","MUSLI","BADEM SEKERI"],
        "unit": "kg",
        "max_price_per_kg": 2000,
    },
    "Molasses": {
        "kw":  ["PEKMEZ"],
        "ex":  ["TAHIN","SUCUK","KECIBOYNUZU","ZILE PEKMEZI"],
        "unit": "kg",
    },
    "Salt": {
        "kw":  ["BILLUR TUZ","SALINA TUZ"],
        "ex":  ["HIMALAYA","LIMON","ZEYTINLI","SALAMURA","IYOTSUZ TUZ","TUZLUKLU"],
        "unit": "kg",
        "require_weight": True,
    },
    "Average Spices": {
        "kw":   ["KARABIBER","PUL BIBER"],
        "ex":   ["CIPS","KRAKER","BISKUVI","CIKOLATA","KEDI","KOPEK",
                 "SALAM","SUCUK","ETI CRAX","GRETA","TANE","TUZLUKLU"],
        "unit": "kg",
        "require_weight": True,
        "max_price_per_kg": 1000,
    },
    "Linden / Herbal Tea": {
        "kw":  ["IHLAMUR","PAPATYA CAYI","BITKI CAY"],
        "ex":  ["MAKINESI","SETI","SOGUK"],
        "unit": "piece",
        "require_weight": True,
    },
}



# ── 4. UTILITIES ────────────────────────────────────────
def parse_price(s: str) -> float:
    """Strip ₺ and parse decimal comma format."""
    s = str(s).strip()
    s = re.sub(r'[₺\s]', '', s)
    m = re.match(r'^(\d{1,3}),(\d+)$', s)
    if m:
        after = m.group(2)
        return float(s.replace(',', '.')) if len(after) == 2 else float(s.replace(',', ''))
    s = re.sub(r'\.(?=\d{3})', '', s)
    return float(s.replace(',', '.'))

def extract_weight_g(name: str):
    m = re.search(r'(\d+[,.]?\d*)\s*(KG|GR|G)\b', name.upper())
    if m:
        raw = m.group(1)
        sep_m = re.match(r'^(\d+)[,.](\d{3})$', raw)
        if sep_m:
            v = float(sep_m.group(1) + sep_m.group(2))
        else:
            v = float(raw.replace(',', '.'))
        return v * 1000 if m.group(2) == 'KG' else v
    return None

def extract_volume_ml(name: str):
    n = re.sub(r'\bLT\b', 'L', name, flags=re.IGNORECASE).upper()
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
    m = re.search(r"(\d+)\s*['\u2019]?\s*(LU|Lİ|LI|LU|li|lu)\b", name, re.IGNORECASE)
    if m: return int(m.group(1))
    m2 = re.search(r'(\d+)\s*[Ll][Ii]\b', name)
    if m2: return int(m2.group(1))
    m3 = re.search(r'(\d+)\s*[Aa][Dd][Ee][Tt]', name)
    if m3: return int(m3.group(1))
    return None

def is_sold_by_kg(name: str) -> bool:
    return bool(re.search(r'(?<!\d)\s*KG\.?\s*$', name.strip().upper()))

# ── 5. UNIT PRICE CALCULATOR ────────────────────────────
def get_unit_price(df: pd.DataFrame, product_label: str) -> dict:
    rule = MATCH_RULES[product_label]
    sub  = df.copy()

    if not rule['kw']:
        return {'unit_price': float('nan'), 'n_products': 0, 'matched_names': 'N/A'}

    mask = sub['product_name'].apply(
        lambda x: any(k.upper() in str(x).upper() for k in rule['kw'])
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
        n[:45] + ('…' if len(n) > 45 else '') for n in sub['product_name'].tolist()
    )
    return {'unit_price': round(avg, 2), 'n_products': len(prices), 'matched_names': names}


# Exact standalone fruit names that exist in Kim Market catalog
# Using fullmatch to avoid substring matches (e.g. "CILEK" matching "CILEKLI")
SEASONAL_EXACT_NAMES = [
    'ARMUT DEVECİ', 'ARMUT SANTAMARİA', 'ARMUT KG',
    'GREYFURT', 'GREYFURT KG',
    'NAR', 'NAR KG',
    'KARPUZ', 'KARPUZ KG',
    'KİVİ KG',
    'HÜNNAP',
    'ÜZÜM REDGLOBE', 'ÜZÜM KG',
    'ÇİLEK', 'ÇİLEK KG',
    'KAYISI', 'KAYISI KG',
    'ERİK', 'ERİK KG',
    'KIRAZ', 'KIRAZ KG',
    'ŞEFTALİ', 'ŞEFTALİ KG',
    # Removed: KİVİ 4-PACK, MANGO PIECE, PINEAPPLE PIECE (sold per unit → kg parse fails)
]

def get_seasonal_fruit_price(df: pd.DataFrame) -> dict:
    # Use exact match only — Kim Market names these as standalone items
    # "CILEK" (strawberry) keyword matches hundreds of snacks; only exact "ÇİLEK" name is safe
    exact_upper = {n.upper() for n in SEASONAL_EXACT_NAMES}
    sub = df[df['product_name'].str.strip().str.upper().isin(exact_upper)].copy()

    prices = []
    for _, row in sub.iterrows():
        name  = str(row['product_name'])
        price = parse_price(row['product_price'])
        
        prices.append(price)

    avg   = sum(prices) / len(prices) if prices else float('nan')
    names = '; '.join(n[:45] for n in sub['product_name'].tolist())
    return {'unit_price': round(avg, 2), 'n_products': len(prices), 'matched_names': names}

# ── 6. MONTHLY COMPUTATION ──────────────────────────────
def compute_hunger_threshold(csv_path: str, date_label: str) -> pd.DataFrame:
    df = pd.read_csv(csv_path, header=None, names=['product_name', 'product_price'],
                     encoding='utf-8-sig', dtype=str)
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
