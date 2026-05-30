"""
N/A items (not stocked or unusable price):
  Minced Meat (₺0), Cubed Meat, Fish, Walnut/Hazelnut,
  Bread, Onion, Cucumber, Pepper, Eggplant/Zucchini, Carrot,
  Other Vegetables
"""

import re
import pandas as pd
from pathlib import Path

# ── 1. PATHS ────────────────────────────────────────────
BASE_DIR = "/Users/efeyildirim/Downloads/Marketler/Sozsanal"

FILES = {
    "Feb-26 2026": f"{BASE_DIR}/soz_2026-02-26.csv",
    "Feb-28 2026": f"{BASE_DIR}/soz_2026-02-28.csv",
    "Mar 2026":    f"{BASE_DIR}/soz_2026-03-31.csv",
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
        "kw":  ["ICIM SUT UHT","ICIM SUT Y","ICIM SUT %",
                "PINAR SUT UHT","PINAR  T.Y. SUT",
                "SUTAS SUT UHT","SUTAS SUT Y",
                "TORKU 1/1 LT UHT","TORKU 1/1 UHT",
                "MEYSU SUT","JERSEY SUT"],
        "ex":  ["CIKOLATA","CIKOLATALI","CILEK","MUZLU","AROMALI","KEFIR","AYRAN",
                "SÜTLÜ","KAYMAK","SUTLAC","KREMA","DEVAM","BEBEK","LAKTOZSUZ",
                "PROTEIN","ORGANIK","180ML","200ML","180 ML","200 ML",
                "KIDO","ICIMINO","NESQUIK","SAMPUAN","SABUN","LATTE",
                "SALEP","KREM SANTI","KEFIR"],
        "unit": "ml_or_L",
        "max_price_per_kg": 120,
    },
    "Yogurt": {
        "kw":  ["YOGURT"],
        "ex":  ["BEBEK","MAMA","HERO","ARI MAMA","KAYMAKLI","MEYVELI","AROMALI",
                "KEFIR","SUZME","PROBIYOTIK","LAKTOZSUZ","ORGANIK","CIRPILMIS",
                "ACTIVIA","DANONE CILEKLI","CIPSO","LAYS","PERITOS","GONG",
                "SEFTALI","TAVA","PUDING","LIGHT","MANDA","KEFI"],
        "unit": "kg",
        "max_price_per_kg": 250,
    },
    "White Cheese": {
        "kw":  ["BEYAZ PEYNIR","TAZE PEYNIR"],
        "ex":  ["KASAR","LOR","DIL","ORGU","CECIL","KREM","MOZZARELLA","LABNE",
                "TULUM","SUZME","LAKTOZSUZ","TOST","KOLOT","FUSILLI","SANDVIC",
                "PEYNIRLIM"],
        "unit": "kg",
        "max_price_per_kg": 600,
    },
    "Kashar / Other Cheese": {
        "kw":  ["KASAR PEYNIR","KASAR PIKNIK","KASAR 200GR","KASAR 400GR",
                "KASAR 600GR","KASAR PEYNIRI"],
        "ex":  ["SANDVIC","KOFTE","BISKUVI","BURGER","DIRSEK","GOFRET","KASARLI"],
        "unit": "kg",
        "max_price_per_kg": 700,
    },
    "Minced Meat":           {"kw": [], "ex": [], "unit": "kg"},  # ₺0 placeholder
    "Cubed Meat / Lamb Meat":{"kw": [], "ex": [], "unit": "kg"},  # not stocked
    "Chicken": {
        "kw":  ["BUTUN PILIC KG","BÜTÜN PİLİÇ KG"],
        "ex":  ["SOSIS","SALAM","SUCUK","FUME","NUGGET","KOFTE","DONER",
                "BAHARAT","CESNI","CIZIRDA","CITIR"],
        "unit": "kg",
    },
    "Fish":                  {"kw": [], "ex": [], "unit": "kg"},   # not stocked
    "Eggs": {
        "kw":  ["YUMURTA 15 LI","YUMURTA 30 LU","YUMURTA 10 LU",
                "YUMURTA 30LU","YUMURTA 15LI","YUMURTA 10LU",
                "SOZ YUMURTA","BOLVADIN","EVRENKAYA KOYUM YUMURTA",
                "TAKTAK GEZEN","SELENYUMLU TAVA"],
        "ex":  ["BILDIRCIN","KEDI","KOPEK","WAFFLE","MAKARNA","BISKUVI",
                "KINDER","CIKOLATA","SURPRIZ","OZMO","SUPRIZ","OYUNCAK",
                "TOYBOX","MEGA TOYS","THOR","PJ MASKS","KANKY","LOL",
                "TOY JOY","OZIGUARD"],
        "unit": "piece",
    },
    "Dried Beans": {
        "kw":  ["DERMASON FASULYE","KURU FASULYE","SIRA FASULYE"],
        "ex":  ["KONSERVE","HASLANMIS","PILAKI","HAZIR","PASTIRMALI","ETLI"],
        "unit": "kg",
        "max_price_per_kg": 300,
    },
    "Chickpeas": {
        "kw":  ["KOCBASI NOHUT","IRI NOHUT","KOÇBAŞI NOHUT"],
        "ex":  ["KONSERVE","HASLANMIS","CIPS","BULGUR","YEMEGI","ETLI"],
        "unit": "kg",
        "max_price_per_kg": 300,
    },
    "Red Lentils": {
        "kw":  ["MERCIMEK KIRMIZI","KIRMIZI MERCIMEK"],
        "ex":  ["CORBA","ORGANIK","MAKARNA","ERISTESI"],
        "unit": "kg",
        "max_price_per_kg": 250,
    },
    "Green Lentils": {
        "kw":  ["MERCIMEK YESIL","YESIL MERCIMEK"],
        "ex":  ["CORBA","ORGANIK","MAKARNA","BULGUR PILAVI"],
        "unit": "kg",
        "max_price_per_kg": 250,
    },
    "Walnut / Hazelnut / Peanut": {"kw": [], "ex": [], "unit": "kg"},  # not stocked
    "Bread":                       {"kw": [], "ex": [], "unit": "kg"},  # not stocked
    "Rice": {
        "kw":  ["PIRINC GONEN","PIRINC OSMANCIK","PIRINC BALDO",
                "BALDO PIRINC","OSMANCIK PIRINC","PILAVLIK PIRINC",
                "BASMATI PIRINC","KIRIK PIRINC"],
        "ex":  ["PATLAGI","PATLAG","UNU","GEVREGI","SIRKE","BEBEK","SUSHI",
                "MAMA","GARNITUR","SEHRIYELI PIRINC PILAVI","GONG","SOLEN",
                "CORBA","BISCOLATA"],
        "unit": "kg",
        "max_price_per_kg": 250,
    },
    "Bulgur": {
        "kw":  ["BULGUR"],
        "ex":  ["ORGANIK","PILAVI","CORBASI","NOHUTLU","KINOALI","MERCIMEKLI"],
        "unit": "kg",
    },
    "Pasta": {
        "kw":  ["MAKARNA"],
        "ex":  ["SOSU","HAZIR","CORBA","BEBEK","ERISTESI","SEHRIYELI",
                "SEBZELI BURGU MAKARNA","NUHUN GEMISI","LASAGNE"],
        "unit": "kg",
    },
    "Flour": {
        "kw":  ["HEKIMOGLU UN","SINANGIL UN","SOKE UN","ANKARA UN",
                "BASKENT UN","MISUN UN","ERKEK UN","FILIZ UN"],
        "ex":  ["GALETA","MISIR","NOEL","PIZZA","KABARTMA","BOHCA",
                "YOGURTLU","TATLI","KARISMIK"],
        "unit": "kg",
        "max_price_per_kg": 80,
    },
    "Semolina": {
        "kw":  ["FILIZ IRMIK","IRMIK 500 GR","MAKARNASI IRMIK"],
        "ex":  ["BEBEK","MAMA","HELVASI","ORGANIK"],
        "unit": "kg",
        "max_price_per_kg": 200,
    },
    "Apple": {
        "kw":  ["ELMA EGIRDIR","ELMA KG","GRANDSMITH ELMA"],
        "ex":  ["SUYU","AROMALI","KURUSU","SIRKE","DETERJANI","BULASIK",
                "SODA","ICECEGI","HIPP","ICIMINO","SUPERFRESH"],
        "unit": "kg",
    },
    "Orange / Mandarin": {
        "kw":  ["PORTAKAL  KG","PORTAKAL KG","PORTAKAL FINIKE","MANDALINA GREMENTIN"],
        "ex":  ["SUYU","GAZOZ","AROMALI","RECELI","DETERJANI","BISKÜVI",
                "BISKUVI","TATLI","KOLONI","SEKER","CIPSO","CANDY",
                "ICECEGI","MEYVE SUYU","BULASIK","HAVLU","KABUGU"],
        "unit": "kg",
    },
    "Banana": {
        "kw":  ["MUZ YERLI-KG","MUZ KG","MUZ  KG"],
        "ex":  ["AROMALI","KURUSU","BEBEK","KREMALI","MUZLU","PUDING"],
        "unit": "kg",
    },
    "Potato": {
        "kw":  ["TAZE PATATES KG","PATATES KG"],
        "ex":  ["CIPSO","CIPS","LAYS","KROKET","PURESI","POGACA","HAZIR",
                "PARMAK","CITIR","SUPERFRESH","RULO BOREK","PEK FOOD"],
        "unit": "kg",
    },
    "Onion":                 {"kw": [], "ex": [], "unit": "kg"},  # not stocked fresh
    "Tomato": {
        "kw":  ["DOMATES KG"],
        "ex":  ["SALCA","KURUTULMUS","KONSERVE","CORBA","SOSU","RENDE",
                "PURESI","KOKTEYL"],
        "unit": "kg",
    },
    "Cucumber":              {"kw": [], "ex": [], "unit": "kg"},  # only pickled cucumber (turşu) — skip
    "Pepper":                {"kw": [], "ex": [], "unit": "kg"},  # not stocked fresh
    "Eggplant / Zucchini":   {"kw": [], "ex": [], "unit": "kg"},  # not stocked fresh
    "Carrot":                {"kw": [], "ex": [], "unit": "kg"},  # not stocked fresh
    "Greens / Lettuce / Parsley": {
        "kw":  ["KIVIRCIK MARUL","MARUL ADET","TERE-ROKA","ROKA ADET","MAYDANOZ ADET"],
        "ex":  [],
        "unit": "piece",
    },
    "Other Vegetables":      {"kw": [], "ex": [], "unit": "kg"},  # not stocked
    "Sunflower Oil": {
        "kw":  ["AYCICEK YAGI"],
        "ex":  ["TON","SARDIN","SPREY"],
        "unit": "ml_or_L",
    },
    "Olive Oil": {
        "kw":  ["ZEYTINYAGI ZS","SIZMA ZEYTINYAGI","RIVIERA ZEYTINYAGI",
                "AHSAF","MARMARA BIRLIK","KRISTAL ZEYTINYAGI"],
        "ex":  ["TON","SABUN","SPREY","KONSERVE","DETERJAN","SAMPUAN",
                "KREMA","LOSYON","OSTWINT"],
        "unit": "ml_or_L",
        "max_price_per_kg": 1000,
    },
    "Butter": {
        "kw":  ["KEBIR GURME TEREYAGI","KEBIR TRABZON TEREYAGI",
                "ONAL TEREYAG KG","SUTAS TEREYAGI","SUTAS YK YAYIK",
                "TORKU TEREYAGI","ICIM TEREYAGI","PINAR TEREYAGI"],
        "ex":  ["MARGARIN","BITKISEL","MILFOY","BISKUVI","SEKER","LEZZETI",
                "MISSBON","KREM SANTI","EKMEK USTU","EKMEKKUSTU"],
        "unit": "kg",
    },
    "Margarine": {
        "kw":  ["MARGARIN"],
        "ex":  ["TEREYAG","ZEYTINYAGLI","EKMEK USTU","EKMEKKUSTU"],
        "unit": "kg",
    },
    "Olives": {
        "kw":  ["AYDAR","MARMARA BIRLIK DILIMLI","ONDA ZEYTIN","ONCU YAGLI SELE ZEYTIN"],
        "ex":  ["YAGI","EZMESI","SABUN","ZEYTINYAGLI","BISKUVI","KRAKER",
                "SARMA","PANYWICH","SANDVIC","OSTWINT","BIBERLI YESIL"],
        "unit": "kg",
    },
    "Sugar": {
        "kw":  ["SOZ TOZ SEKER","TOZ SEKER - DOKME","TURKSEKER TOZ SEKER"],
        "ex":  ["KUP","ESMER","PUDRA","VANILIN","KAHVERENGI"],
        "unit": "kg",
    },
    "Tea": {
        "kw":  ["CAYKUR CAY","DOGUS FILIZ CAY","OFCAY","EFOR FILIZ CAY",
                "SOZ TURK CAYI","BETA TEA TURK","LIPTON DOKME"],
        "ex":  ["BITKI","SOGUK","MEYVE","IHLAMUR","PAPATYA","BERGAMOT",
                "EARL GREY","POSET","DEMLIK","YESIL","NANE","FORM",
                "KUSBURNU","REZENE","MAKINESI","BARDAK","SETI","AROMATIK",
                "CAY BARDAGI","CAY TABAGI","SANTI","SALEP"],
        "unit": "kg",
        "require_weight": True,
        "max_price_per_kg": 700,
    },
    "Tomato Paste": {
        "kw":  ["DOMATES SALCA"],
        "ex":  ["BIBER","ACI","KOY","HAZIR"],
        "unit": "kg",
        "max_price_per_kg": 200,
    },
    "Jam": {
        "kw":  ["METIN RECEL","ANNE RECEL","ANNE KABAK RECEL","ANNE NAR RECEL"],
        "ex":  ["DIABETIK","SUT RECELI","CEVIZ","KESTANE","LIQUER",
                "BIBER RECELI","ACI BIBER"],
        "unit": "kg",
        "max_price_per_kg": 600,
    },
    "Honey": {
        "kw":  ["BALPARMAK"],
        "ex":  ["KABAGI","PROPOLIS","BISKUVI","BAR","GRANOLA","CIKOLATA",
                "POLEN","ARISUTÜ","HONEYBANA"],
        "unit": "kg",
        "max_price_per_kg": 2000,
    },
    "Molasses": {
        "kw":  ["METIN PEKMEZ"],
        "ex":  ["TAHIN","SUCUK","KECIBOYNUZU","IKILI"],
        "unit": "kg",
        "max_price_per_kg": 600,
    },
    "Salt": {
        "kw":  ["BILLUR TUZ"],
        "ex":  ["TUZLU","TURSU","SALAMURA","HIMALAYA","LIMON","ZEYTINLI",
                "SOS","TUZLUKLU","FINISH","BULASIK","DENIZ","DEGIRMEN",
                "KAYA TUZU"],
        "unit": "kg",
        "require_weight": True,
        "max_price_per_kg": 150,
    },
    "Average Spices": {
        "kw":  ["KARABIBER","PUL BIBER"],
        "ex":  ["TANE","TUZLUKLU","DOLMALIK","HARC","CAJUN","MANGAL",
                "IZGARA","KANATLI","ITALYAN","KOYUN","ACI","KNORR CESNI",
                "KNORR BAHARAT","KEDI","KOPEK"],
        "unit": "kg",
        "require_weight": True,
        "max_price_per_kg": 2000,
    },
    "Linden / Herbal Tea": {
        "kw":  ["BAGDAT IHLAMUR","AKTAR IHLAMUR","ZIYA DEDE IHLAMUR",
                "PAPATYA CAY","IHLAMUR CAY"],
        "ex":  ["PROPOLIS","MAKINESI","SETI","SOGUK","ZENCEFIL","LIMON"],
        "unit": "kg",
        "require_weight": True,
        "max_price_per_kg": 3000,
    },
}

# Seasonal fruit: items ending in "KG" with seasonal fruit keywords
SEASONAL_KG_NAMES = [
    "KIVI  KG","KIVI KG","ALIM UZUM ENERJI KG",
    "ARMUT KG","SEFTALI KG","ERIK KG","CILEK KG","NAR KG","KAVUN KG",
]

# ── 4. UTILITIES ────────────────────────────────────────
def parse_price(s: str) -> float:
    s = str(s).strip()
    s = re.sub(r'\.(?=\d{3})', '', s)
    return float(s.replace(',', '.'))

def extract_weight_g(name: str):
    # Handle multipack: "30*15GR" or "30x15GR" → total grams
    mp = re.search(r'(\d+)\s*[xX\*]\s*(\d+[,.]?\d*)\s*(KG|GR|G)\b', name.upper())
    if mp:
        count = int(mp.group(1)); uw = float(mp.group(2).replace(',','.'))
        return count * uw * (1000 if mp.group(3) == 'KG' else 1)
    m = re.search(r'(\d+[,.]?\d*)\s*(KG|KGR)\b', name.upper())
    if m:
        raw = m.group(1); sep = re.match(r'^(\d+)[,.](\d{3})$', raw)
        return float(sep.group(1)+sep.group(2))*1000 if sep else float(raw.replace(',','.'))*1000
    m = re.search(r'(\d+[,.]?\d*)\s*(GR|G)\b', name.upper())
    if m:
        raw = m.group(1); sep = re.match(r'^(\d+)[,.](\d{3})$', raw)
        return float(sep.group(1)+sep.group(2)) if sep else float(raw.replace(',','.'))
    return None

def extract_volume_ml(name: str):
    n = name.upper()
    mp = re.search(r'(\d+)\s*[xX\*]\s*(\d+[,.]?\d*)\s*(ML|LT|L)\b', n)
    if mp:
        c = int(mp.group(1)); e = float(mp.group(2).replace(',','.'))
        return c * e * (1000 if mp.group(3) in ('LT','L') else 1)
    m = re.search(r'(\d+[,.]?\d*)\s*(LT|L)\b', n)
    if m: return float(m.group(1).replace(',','.'))*1000
    m = re.search(r'(\d+[,.]?\d*)\s*(ML)\b', n)
    if m: return float(m.group(1).replace(',','.'))
    return None

def extract_piece_count(name: str):
    m = re.search(r'(\d+)\s*LU\b', name.upper())
    if m: return int(m.group(1))
    m2 = re.search(r'(\d+)\s*LI\b', name.upper())
    if m2: return int(m2.group(1))
    m3 = re.search(r'(\d+)\s*ADET\b', name.upper())
    if m3: return int(m3.group(1))
    return None

# ── 5. UNIT PRICE CALCULATOR ────────────────────────────
def get_unit_price(df: pd.DataFrame, product_label: str) -> dict:
    rule = MATCH_RULES[product_label]
    if not rule['kw']:
        return {'unit_price': float('nan'), 'n_products': 0, 'matched_names': 'N/A'}

    mask = df['Product Name'].apply(
        lambda x: any(kw.upper() in str(x).upper() for kw in rule['kw'])
    )
    sub = df[mask].copy()
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
        price = parse_price(row['Price'])
        if price <= 0:
            continue  # skip placeholder prices

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
        n[:45] + ('…' if len(n) > 45 else '') for n in sub['Product Name'].tolist()
    )
    return {'unit_price': round(avg, 2), 'n_products': len(prices), 'matched_names': names}


def get_seasonal_fruit_price(df: pd.DataFrame) -> dict:
    exact_upper = {n.upper() for n in SEASONAL_KG_NAMES}
    sub = df[df['Product Name'].str.strip().str.upper().isin(exact_upper)].copy()
    prices = []
    for _, row in sub.iterrows():
        price = parse_price(row['Price'])
        if price > 0:
            prices.append(price)
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
