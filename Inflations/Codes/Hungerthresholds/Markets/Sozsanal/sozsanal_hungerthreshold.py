import re
import pandas as pd
from pathlib import Path

# ── 1. PATHS ────────────────────────────────────────────
BASE_DIR = "/Users/efeyildirim/Downloads/Marketler/Sozsanal"

FILES = {
    "Feb 2026": f"{BASE_DIR}/soz_2026-02-28.csv",
    "Mar 2026": f"{BASE_DIR}/soz_2026-03-31.csv",
}

OUTPUT_DETAIL  = f"{BASE_DIR}/hunger_threshold_detail.csv"
OUTPUT_SUMMARY = f"{BASE_DIR}/hunger_threshold_summary.csv"

# ── 2. FOOD BASKET ──────────────────────────────────────
FOOD_BASKET = [
    ("Dairy Products",      "Yogurt",                         "Kg",     59.7),
    ("Dairy Products",      "White Cheese",                   "Kg",      5.7),
    ("Meat and Protein",    "Cubed Meat / Lamb Meat",         "Kg",      4.6),
    ("Meat and Protein",    "Chicken",                        "Kg",     10.3),
    ("Meat and Protein",    "Fish",                           "Kg",      6.9),
    ("Meat and Protein",    "Eggs",                           "Piece", 120.0),
    ("Legumes",             "Chickpeas",                      "Kg",      1.8),
    ("Nuts and Seeds",      "Walnut / Hazelnut / Peanut",     "Kg",      2.7),
    ("Grains",              "Bread",                          "Kg",     18.0),
    ("Fruits",              "Banana",                         "Kg",     16.7),
    ("Fruits",              "Seasonal Fruit",                 "Kg",     12.9),
    ("Vegetables",          "Onion",                          "Kg",     18.0),
    ("Vegetables",          "Eggplant / Zucchini",            "Kg",     23.1),
    ("Vegetables",          "Other Vegetables",               "Kg",     11.8),
    ("Oils",                "Olive Oil",                      "Liter",   1.1),
    ("Other Food Products", "Grissini",                       "Kg",      2.1),
]

# ── 3. MATCH RULES ──────────────────────────────────────
MATCH_RULES = {
    "Yogurt": {
        "keywords": ["Yoğurt"],
        "exclude": ["Meyveli", "Organik", "Kaymaklı", "Süzme", "Çırpılmış", "Probiyotik",
                    "Laktozsuz", "Çilek", "Aromalı", "Quark", "Tava", "Cipsi", "Kedi",
                    "Köpek", "Puding", "Mix", "Dip", "Cips", "Meze", "Mama", "Yoğurtlu",
                    "Lay", "Patates", "Çömlek", "Meyve", "Şeftali", "Knorr", "Danone",
                    "Activia", "Frambuazlı", "Züber", "Kayısılı", "İncirli", "Vişne",
                    "Kiraz", "Dr.Oetker", "Dr. Oetker", "Eker Kefir", "Maya", "Protein"],
        "unit": "kg",
    },
    "White Cheese": {
        "keywords": ["Beyaz Peynir", "Taze Peynir", "Klasik Peynir"],
        "exclude": ["Misto", "Laktozsuz", "Sürülebilir", "Ezine", "Kaşar", "Lor",
                    "Tulum", "Çerkez", "Keçi", "Koyun"],
        "unit": "kg",
    },
    "Cubed Meat / Lamb Meat": {
        "keywords": ["Kuşbaşı"],
        "exclude": ["Döner", "Köfte", "Kedi", "Köpek", "Kıyma", "Hazır", "Kavurma",
                    "Pastırma", "Sucuk", "Sosis", "Dondurulmuş", "Pide", "Kokoreç",
                    "Piliç", "Tavuk","BANVIT"],
        "unit": "kg",
    },
    "Chicken": {
        "keywords": ["Tavuk", "Piliç"],
        "exclude": ["Döner", "Nugget", "Şinitzel", "Sarma", "Köfte", "Kroket", "Çıtır",
                    "Kebap", "Lokma", "Parmak Bonfile", "Jumbo Fileto", "Izgara Dilimli",
                    "Soslu Kanat", "Kedi", "Köpek", "Mama", "Sucuk", "Sosis", "Füme",
                    "Taşlık", "Ciğer", "Yürek", "Karaciğer", "Tavukgöğsü", "Noodle",
                    "Bulyon", "Salam", "Pilav", "Cips", "Çeşni", "Baharat", "Çorba",
                    "Jambon", "Çabuk", "Yumurta", "Tavuk Göğsü", "Püre", "Pouch", "Balığı",
                    "Ödül", "Izgara", "Pane", "Harcı", "Tavuk Göğüsü", "Ördeği",
                    "Oyuncak", "Hipp", "Suyu", "Mr", "Burcu", "Mister", "Köri", "Lego",
                    "Yatakta", "Pounch", "Teriyaki", "Bonisa", "Harçı", "Schnitzel",
                    "indomie", "hindi", "şnitzel", "Yayla", "Güveç", "Tada", "Dreamıes",
                    "Kuru", "Konserve", "Felix", "Gourmet","LAYS"],
        "unit": "kg",
    },
    "Fish": {
        "keywords": ["Hamsi", "Levrek", "Somon", "Balık"],
        "exclude": ["Füme", "Konserve", "Kedi", "Köpek", "Maması", "Sosu", "Soslu",
                    "Kraker", "Çikolata", "Şeker", "Mama", "Tava", "Hayvan", "Biftek",
                    "Pouch", "Piliç", "Zeytinyağlı", "Çıtır", "Ton", "Maşa", "Izgara",
                    "Erişte", "Dardanel", "Kaşık", "Köfte", "Whiskas", "Dreamies", "Ödül",
                    "Tabak", "Onigiri", "Sushida", "Fish Finger", "Mister No", "Yem",
                    "Kolonya", "Eti", "Anason", "Çeşni", "Bonisa", "Celenes", "Bay",
                    "Brix", "Peluş", "Lego", "Tavuklu", "Burger", "Havlu",
                    "Felix", "Baharat", "Çorbalık", "Eşofman", "Şapka"],
        "unit": "kg",
    },
    "Eggs": {
        "keywords": ["Yumurta"],
        "exclude": ["Organik", "Bıldırcın", "Toz", "Akı", "Sarısı", "Şeker", "Haribo",
                    "Çikolata", "Sürpriz", "Süpriz", "Fırça", "Ozibox", "Elvan",
                    "Yumurtalı", "Ozmo", "Ülker", "Mini", "Kinder", "Toto", "Toybox",
                    "Makarna", "Sünger", "İç", "Parlak", "Dino", "Kavanoz", "et","Toy","OZIGUARD"],
        "unit": "piece",
    },
    "Chickpeas": {
        "keywords": ["Nohut"],
        "exclude": ["Konserve", "Cipsi", "Çerez", "Pilav", "Cips", "Haşlanmış",
                    "Unu", "Unlu", "Patlağı", "Erişte", "Organik", "Etli", "Hazır",
                    "Yayla", "Kraker", "Salata"],
        "unit": "kg",
    },
    "Walnut / Hazelnut / Peanut": {
        "keywords": ["Yer Fıstığı", "Fındık İçi", "Çiğ Fındık", "Kavrulmuş Fındık",
                     "İç Ceviz", "Ceviz İçi", "Antep Fıstığı İçi", "İç Fıstık"],
        "exclude": ["Ezmesi", "Kreması", "Bitter", "Çikolata", "Cips", "Soslu", "Aromalı",
                    "Susamlı", "Dolgulu", "Kaplı", "Draje", "Salam", "Helva", "Granola",
                    "Müsli", "Puding", "Gofret", "Bisküvi", "Bar", "Pasta", "SürMix",
                    "Quark", "Lokum", "Kek", "Kurabiye", "Kakaolu", "Ballı",
                    "Parçacıklı", "Hindistan", "Tütsülenmiş", "Dolmalık", "Koska"],
        "unit": "kg",
    },
    "Bread": {
        "keywords": ["Ekmek"],
        "exclude": ["Hamburger", "Sandviç", "Tost", "Lavaş", "Tortilla", "Yufka",
                    "Wasa", "Gevrek", "Margarin", "Üstü", "Kırıntı", "Çubuk", "Yer",
                    "Şekersiz", "Kızarmış", "Form", "Grissini", "Ekmekli", "Kızartma",
                    "Makine", "Makina", "Un", "Unu", "Bıçak", "Bıçağı", "Tepsi",
                    "Tepsisi", "Kadayıfı", "tatlı", "Sepet", "Şermin", "kitap"],
        "unit": "kg",
    },
    "Banana": {
        "keywords": ["Muz"],
        "exclude": ["Cipsi", "Kurutulmuş", "Çikolata", "Süt", "Puding", "Gofret",
                    "Bisküvi", "Kek", "Bar", "Milkshake", "İçecek", "Kefir", "Kahve",
                    "Kremalı", "Aromalı", "Maması", "Helva", "Frappe", "Granola",
                    "Grissini", "Krema", "Püresi", "Sıkma", "Muzlu", "Püre", "Dovido",
                    "Mixmey", "Kavanoz", "Dimes", "Kent", "Activia", "Hero", "Gerber",
                    "Bebek", "Makaron", "Şıpsevdi", "Dr.Oetker", "Dr. Oetker",
                    "Nesquik", "Pınar", "Ülker", "Züber", "Arılac", "Milupa", "Hurma",
                    "Freeze", "Sakız", "Pasta", "Dankek", "Eker", "Sütaş", "İçim",
                    "Rondo", "Eyüp", "Çıtır", "Algida", "big", "bal", "smoothie",
                    "biber", "pols", "torku", "domuz", "omuz", "dondurma"],
        "unit": "kg",
    },
    "Seasonal Fruit": {
        "keywords": ["Çilek", "Kiraz", "Vişne", "Kayısı", "Şeftali", "Erik", "İncir",
                     "Üzüm", "Nar", "Kivi", "Kavun", "Karpuz", "Elma", "Portakal",
                     "Mandalina"],
        "exclude": [
            "Suyu", "Nektar", "Gazoz", "İçecek", "İçeceği", "Çay", "Kahve", "Kefir",
            "Ml", "Lt", "Litre", "Meysu", "Fanta", "Dimes", "Yedigün", "Erikli", "Kıvırcık",
            "Süt", "Yoğurt", "Peynir", "Danone", "Activia", "Dr.Oetker", "Dr. Oetker",
            "Pınar", "Salam", "Sucuk", "Köfte", "Füme", "Sosis", "Falım", "Şölen",
            "Karışık", "Sleepy", "Vivident", "Hero", "Fuse", "Kısır", "Makarna",
            "Marmelat", "Çikolata", "Şeker", "Reçel", "Gofret", "Bisküvi", "Büskivi",
            "Kurabiye", "Papilla", "Sek", "Freeze", "Berg", "Sorbet", "Matcha",
            "Narenciye", "Buzluk", "Meyve Suyu", "Kek", "Bar", "Kreması", "Puding",
            "Dondurma", "Helva", "Lokum", "Draje", "Sakız", "Pestil", "Protein",
            "Granola", "Gevrek", "Nestle", "Oreo", "Ülker", "Mayonez", "Ketçap", "Sos",
            "Sirke", "Salça", "Baharat", "Aroma", "Aromalı", "Börek", "Mantı", "Un",
            "Nişasta", "Deterjan", "Sabun", "Şampuan", "Torbası", "Çöp", "Temizlik",
            "Sprey", "Jeli", "Serum", "Fırçası", "Çamaşır", "Garnier", "Sensodyne",
            "Koroplast", "Ernet", "L'Oreal", "Freze", "Cips", "Milıpa", "Çekirdeği",
            "Mama", "Maması", "Bebek", "Kedi", "Köpek", "Evcil", "Ödül", "Pouch",
            "Dondurulmuş", "Konserve", "Kutu", "Paket", "Granül", "Dantel",
            "Kuru", "Kurutulmuş", "Bağdat", "İçim", "Yemi", "Çıtır", "Sarı", "Mılıpa",
            "Verita", "Fersan", "Öncü", "Züber", "Lipton", "Jacobs", "Helmann",
            "Superfresh", "Master Farm", "Yer Elması", "Enginar", "Avokado", "Limon",
            "Muz", "File", "Püre", "Pekmez", "Kraker", "Merhem", "Organik", "Krem",
            "Ozmo", "Eti", "Orsev", "Domestos", "Torku", "Parex", "Çınar", "Bonisa",
            "Çiçek", "Çiçeği", "Zeytin", "First", "Islak", "Kokulu", "Özü", "Yayla",
            "Kent", "Perwoll", "Meze", "Su", "Sap", "Uludağ", "Turşu", "Kuş", "Ezici",
            "Koleston", "Diş", "Kız", "Cappy", "Köme", "Chupa", "olips", "tatlı",
            "nar ekşisi", "yağ", "Smoothie", "Çocuk", "Servis", "Hipster", "Lego",
            "Battaniye", "Pin", "Doctor", "Gök", "Dolma", "Schweppes", "Balım", "Hello",
            "raz", "kitap", "ruj",
        ],
        "unit": "kg",
    },
    "Onion": {
        "keywords": ["Soğan"],
        "exclude": ["Taze", "Pırasa", "Toz", "Pul", "Sarımsak", "Halkası", "Cips",
                    "Halka", "Kızartılmış", "Frenk", "Kurutulmuş", "Aromalı", "Kraker",
                    "Çıtır", "Küp", "Bebek", "Çerez", "Kaplamalı", "Kuru", "Tozu",
                    "Dondurulmuş", "Turşu", "Kroket", "Lahmacun", "Superfresh", "Peynir",
                    "Ruffles", "Ruflles", "Turşusu", "Nutzz", "Çizi", "Baharat", "Cipsi",
                    "Eti Crax", "Tadım", "Krema", "Balzamik", "Granül", "Karamelize","Cheetos","asse"],
        "unit": "kg",
    },
    "Eggplant / Zucchini": {
        "keywords": ["Patlıcan", "Kabak"],
        "exclude": ["Konserve", "Turşu", "Tatlısı", "Dondurulmuş", "Çekirdeği",
                    "Çekirdek", "Dolma", "Salatası", "Börek", "Sabun", "Yağı",
                    "Maması", "Granola", "Bar", "Liflı", "Köz", "Kuru", "Kurutulmuş",
                    "Kızartma", "Ezme", "Salata", "Boya", "Çorba", "Meze", "Yemeği",
                    "Loofah", "Lifi", "Banyo", "Vücut", "Eldiven", "Karışımı", "Yoğurtlu",
                    "İç Kabak", "Peyman", "Koleston", "Nohut", "TADIM", "mücver",
                    "reçel", "soslu","asse","ALIM"],
        "unit": "kg",
    },
    "Other Vegetables": {
        "keywords": ["Taze Fasulye", "Fasulye Ayşe", "Fasulye Çalı"],
        "exclude": ["Konserve", "Dondurulmuş", "Zeytinyağ", "Kuru", "Super Fresh",
                    "Superfresh", "*"],
        "unit": "kg",
    },
    "Olive Oil": {
        "keywords": ["Zeytinyağı", "Zeytinyağ"],
        "exclude": ["Spreyı", "Sprey", "Zeytinyağlı", "Sabun", "Krem", "Sleepy",
                    "Saç", "Şampuan", "Eyüp"],
        "unit": "ml_or_L",
    },
    "Grissini": {
        "keywords": ["Grissini"],
        "exclude": ["Çikolatalı", "Dolgulu", "Çilek", "Muz", "Krema", "Kakaolu",
                    "Fındık Kreması", "Kakao", "Tahin"],
        "unit": "kg",
    },
}

# Seasonal fruit: exact kg items in Sözsanal catalog
SEASONAL_KG_NAMES = [
    "KIVI  KG", "KIVI KG", "ALIM UZUM ENERJI KG",
    "ARMUT KG", "SEFTALI KG", "ERIK KG", "CILEK KG", "NAR KG", "KAVUN KG",
]

# ── 4. FILE LOADER ──────────────────────────────────────
def parse_price(s: str) -> float:
    s = str(s).strip().strip('"')
    s = re.sub(r'\.(?=\d{3})', '', s)
    return float(s.replace(',', '.'))

def load_file(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, encoding='utf-8-sig', on_bad_lines='skip', dtype=str)
    df.columns = [c.strip() for c in df.columns]
    df = df.rename(columns={'product_name': 'name'})
    df['price'] = df['price'].apply(parse_price)
    df = df.dropna(subset=['price'])
    df = df[df['price'] > 0]
    df = df.drop_duplicates(subset=['name'])
    return df[['name', 'price']].copy()

# ── 5. UNIT EXTRACTION ──────────────────────────────────
def extract_weight_g(name: str):
    n = str(name).upper()
    # Multi-pack: "30*15GR"
    mp = re.search(r'(\d+)\s*[xX*]\s*(\d+[,.]?\d*)\s*(KG|GR|G)\b', n)
    if mp:
        cnt = int(mp.group(1)); uw = float(mp.group(2).replace(',', '.'))
        return cnt * uw * (1000 if mp.group(3) == 'KG' else 1)
    m = re.search(r'(\d{1,3})\.(\d{3})\s*(KG|GR|G)\b', n)
    if m:
        v = float(m.group(1) + m.group(2))
        return v * 1000 if m.group(3) == 'KG' else v
    m = re.search(r'(\d+),(\d{1,2})\s*(KG|KGR)\b', n)
    if m:
        return float(m.group(1) + '.' + m.group(2)) * 1000
    m = re.search(r'(\d{1,3}),(\d{3})\s*(GR|G)\b', n)
    if m:
        return float(m.group(1) + m.group(2))
    m = re.search(r'(\d+[,.]?\d*)\s*(KG|KGR)\b', n)
    if m:
        return float(m.group(1).replace(',', '.')) * 1000
    m = re.search(r'(\d+[,.]?\d*)\s*(GR|G)\b', n)
    if m:
        return float(m.group(1).replace(',', '.'))
    return None

def extract_volume_and_count(name: str):
    n = str(name).upper()
    # Multi-pack: "6*200ML", "4xLT"
    mp = re.search(r'(\d+)\s*[xX*]\s*(\d+[,.]?\d*)\s*(ML|LT|L)\b', n)
    if mp:
        cnt = int(mp.group(1)); v = float(mp.group(2).replace(',', '.'))
        unit = mp.group(3)
        return (v * 1000 if unit in ('LT', 'L') else v), cnt
    # "5 LT x 4 Adet"
    m = re.search(r'(\d+[,.]?\d*)\s*(ML|LT|L)\s*[xX*]\s*(\d+)', n)
    if m:
        v = float(m.group(1).replace(',', '.')); unit = m.group(2); cnt = int(m.group(3))
        return (v * 1000 if unit in ('LT', 'L') else v), cnt
    # Standard single
    m = re.search(r'(\d+[,.]?\d*)\s*(LT|L)\b', n)
    if m:
        return float(m.group(1).replace(',', '.')) * 1000, 1
    m = re.search(r'(\d+[,.]?\d*)\s*(ML)\b', n)
    if m:
        return float(m.group(1).replace(',', '.')), 1
    return None, 1

def extract_piece_count(name: str):
    n = str(name).upper()
    m = re.search(r'(\d+)\s*LU\b', n)
    if m: return int(m.group(1))
    m2 = re.search(r'(\d+)\s*LI\b', n)
    if m2: return int(m2.group(1))
    m3 = re.search(r'(\d+)\s*ADET\b', n)
    if m3: return int(m3.group(1))
    return None

# ── 6. UNIT PRICE CALCULATOR ────────────────────────────
def get_unit_price(df: pd.DataFrame, product_label: str) -> dict:
    rule = MATCH_RULES[product_label]

    if not rule['keywords']:
        return {'unit_price': float('nan'), 'n_products': 0, 'matched_names': 'N/A'}

    # Sözsanal ürün adları UPPERCASE ve Türkçe karaktersiz (ğ→g, ş→s vs.)
    # Keyword matching için ASCII normalize ediyoruz
    _tr = str.maketrans('çÇğĞıİöÖşŞüÜ', 'cCgGiIoOsSuU')
    def _norm(s): return str(s).translate(_tr).upper()

    mask = df['name'].apply(
        lambda x: any(_norm(kw) in _norm(x) for kw in rule['keywords'])
    )
    sub = df[mask].copy()

    for exc in rule['exclude']:
        exc_norm = re.escape(_norm(exc))
        sub = sub[~sub['name'].apply(_norm).str.contains(exc_norm, na=False)]

    # Seasonal Fruit: limit to exact Kg items only (no packaged snacks)
    if product_label == 'Seasonal Fruit':
        exact_upper = {n.upper() for n in SEASONAL_KG_NAMES}
        sub = sub[sub['name'].str.strip().str.upper().isin(exact_upper)]

    if sub.empty:
        return {'unit_price': float('nan'), 'n_products': 0, 'matched_names': '—'}

    unit  = rule['unit']
    min_p = rule.get('min_price_per_kg', 0)
    max_p = rule.get('max_price_per_kg', None)
    prices = []

    for _, row in sub.iterrows():
        name  = str(row['name'])
        price = float(row['price'])

        if unit == 'kg':
            w = extract_weight_g(name)
            per_u = price / (w / 1000) if w and w > 0 else price
            if per_u < min_p: continue
            if max_p and per_u > max_p: continue
            prices.append(per_u)

        elif unit == 'ml_or_L':
            v, cnt = extract_volume_and_count(name)
            if not v:
                v = extract_weight_g(name); cnt = 1
            per_u = (price / cnt) / (v / 1000) if v and v > 0 else price
            if max_p and per_u > max_p: continue
            prices.append(per_u)

        elif unit == 'piece':
            cnt = extract_piece_count(name)
            if cnt and cnt > 0:
                prices.append(price / cnt)
            else:
                prices.append(price)

    avg   = sum(prices) / len(prices) if prices else float('nan')
    names = '; '.join(str(r['name'])[:45] + ('…' if len(str(r['name'])) > 45 else '')
                      for _, r in sub.iterrows())
    return {'unit_price': round(avg, 2), 'n_products': len(prices), 'matched_names': names}

# ── 7. MONTHLY COMPUTATION ──────────────────────────────
def compute_hunger_threshold(csv_path: str, date_label: str) -> pd.DataFrame:
    df = load_file(csv_path)
    rows = []
    for category, product_label, unit_label, monthly_qty in FOOD_BASKET:
        info         = get_unit_price(df, product_label)
        unit_price   = info['unit_price']
        monthly_cost = unit_price * monthly_qty
        rows.append({
            'date':               date_label,
            'category':           category,
            'product':            product_label,
            'unit':               unit_label,
            'monthly_qty':        monthly_qty,
            'avg_unit_price_TRY': unit_price,
            'monthly_cost_TRY':   round(monthly_cost, 2) if pd.notna(unit_price) else float('nan'),
            'n_matched':          info['n_products'],
            'matched_products':   info['matched_names'],
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

if not all_results:
    print("No data to summarise.")
else:
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
