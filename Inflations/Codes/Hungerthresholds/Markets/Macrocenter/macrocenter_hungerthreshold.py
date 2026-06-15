import re
import pandas as pd
from pathlib import Path

# ── 1. PATHS ────────────────────────────────────────────
BASE_DIR = "/Users/efeyildirim/Downloads/Marketler/Macrocenter"

FILES = {
    "Feb 2026": f"{BASE_DIR}/macrocenter_prices_2026-02-27.csv",
    "Mar 2026": f"{BASE_DIR}/macrocenter_prices_2026-03-31.csv",
    "Apr 2026": f"{BASE_DIR}/macrocenter_prices_2026-04-30.csv",
    "May 2026": f"{BASE_DIR}/macrocenter_prices_2026-05-19.csv",
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
                    "Pastırma", "Sucuk", "Sosis", "Dondurulmuş", "Pide"],
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
                    "Oyuncak", "Hipp", "Suyu", "Mr", "Burcu", "Mister", "Köri",
                    "Teriyaki", "Bonisa", "Harçı", "Schnitzel", "indomie", "hindi",
                    "şnitzel", "Yayla", "Güveç", "Tada"],
        "unit": "kg",
    },
    "Fish": {
        "keywords": ["Hamsi", "Levrek", "Somon", "Balık"],
        "exclude": ["Füme", "Konserve", "Kedi", "Köpek", "Maması", "Sosu", "Soslu",
                    "Kraker", "Çikolata", "Şeker", "Mama", "Tava", "Hayvan", "Biftek",
                    "Pouch", "Piliç", "Zeytinyağlı", "Çıtır", "Ton", "Maşa", "Izgara",
                    "Dardanel", "Kaşık", "Köfte", "Whiskas", "Dreamies", "Ödül", "Tabak",
                    "Onigiri", "Sushida", "Fish Finger", "Mister No", "Yem", "Kolonya",
                    "Eti", "Anason", "Çeşni", "Bonisa", "Celenes"],
        "unit": "kg",
    },
    "Eggs": {
        "keywords": ["Yumurta"],
        "exclude": ["Organik", "Bıldırcın", "Toz", "Akı", "Sarısı", "Şeker", "Haribo",
                    "Çikolata", "Sürpriz", "Süpriz", "Fırça", "Ozibox", "Elvan",
                    "Yumurtalı", "Ozmo", "Ülker", "Mini", "Kinder", "Toto", "Toybox",
                    "Makarna", "Sünger"],
        "unit": "piece",
    },
    "Chickpeas": {
        "keywords": ["Nohut"],
        "exclude": ["Konserve", "Cipsi", "Çerez", "Pilav", "Cips", "Haşlanmış", "Haşlama",
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
                    "Tepsisi", "Kadayıfı", "tatlı"],
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
                    "biber", "pols"],
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
            "Meyve Suyu", "Kek", "Bar", "Kreması", "Puding", "Dondurma", "Helva",
            "Lokum", "Draje", "Sakız", "Pestil", "Protein", "Granola", "Gevrek",
            "Nestle", "Oreo", "Ülker", "Mayonez", "Ketçap", "Sos", "Sirke", "Salça",
            "Baharat", "Aroma", "Aromalı", "Börek", "Mantı", "Un", "Nişasta",
            "Deterjan", "Sabun", "Şampuan", "Torbası", "Çöp", "Temizlik", "Sprey",
            "Jeli", "Serum", "Fırçası", "Çamaşır", "Garnier", "Sensodyne", "Koroplast",
            "Ernet", "L'Oreal", "Freze", "Cips",
            "Mama", "Maması", "Bebek", "Kedi", "Köpek", "Evcil", "Ödül", "Pouch",
            "Dondurulmuş", "Konserve", "Kutu", "Paket",
            "Kuru", "Kurutulmuş", "Bağdat", "İçim",
            "Verita", "Fersan", "Öncü", "Züber", "Lipton", "Jacobs", "Helmann",
            "Superfresh", "Master Farm", "Yer Elması", "Enginar", "Avokado", "Limon",
            "Muz", "File", "Püre", "Pekmez", "Kraker", "Merhem", "Organik", "Krem",
            "Ozmo", "Eti", "Orsev", "Domestos", "Torku", "Parex", "Çınar", "Bonisa",
            "Çiçek", "Çiçeği", "Zeytin", "First", "Islak", "Kokulu", "Özü", "Yayla",
            "Kent", "Perwoll", "Meze", "Su", "Sap", "Uludağ", "Turşu", "Kuş", "Ezici",
            "Koleston", "Diş", "Kız", "Cappy", "Köme", "Chupa", "olips", "tatlı",
            "nar ekşisi", "yağ", "Smoothie", "Çocuk",
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
                    "Eti Crax", "Tadım", "Krema", "Balzamik"],
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
                    "reçel", "soslu"],
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

# ── 4. FILE LOADER ──────────────────────────────────────
def load_file(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, encoding='utf-8-sig', on_bad_lines='skip')
    df.columns = [c.strip() for c in df.columns]
    df = df.rename(columns={'product_name': 'name'})
    df['price']     = pd.to_numeric(df['price'], errors='coerce')
    df['is_per_kg'] = df['name'].apply(is_sold_by_kg)
    df = df.dropna(subset=['price'])
    df = df[df['price'] > 0]
    df = df.drop_duplicates(subset=['name'])
    return df[['name', 'price', 'is_per_kg']].copy()

# ── 5. UNIT EXTRACTION ──────────────────────────────────
def is_sold_by_kg(name: str) -> bool:
    return bool(re.search(r'(?<!\d)\s*Kg\.?\s*$', str(name).strip()))

def extract_weight_g(name: str):
    if re.search(r'\d+[*xX]\d+[,.]?\d*\s*(G|Gr|GR|Kg|KG|kg)\b', name):
        return None
    m = re.search(r'(\d{1,3})\.(\d{3})\s*(Kg|KG|kg|Gr\.|Gr|GR|G|g)\b', name)
    if m:
        v = float(m.group(1) + m.group(2))
        return v * 1000 if m.group(3).lower() in ('kg',) else v
    m = re.search(r'(\d+),(\d{1,2})\s*(Kg|KG|kg)\b', name)
    if m:
        return float(m.group(1) + '.' + m.group(2)) * 1000
    m = re.search(r'(\d{1,3}),(\d{3})\s*(Gr\.|Gr|GR|G|g)\b', name)
    if m:
        return float(m.group(1) + m.group(2))
    m = re.search(r'(\d+[,.]?\d*)\s*(Kg|KG|kg)\b', name)
    if m:
        return float(m.group(1).replace(',', '.')) * 1000
    m = re.search(r'(\d+[,.]?\d*)\s*(Gr\.|Gr|GR|G|g)\b', name)
    if m:
        return float(m.group(1).replace(',', '.'))
    return None

def extract_volume_ml(name: str):
    m = re.search(r'(\d+[,.]?\d*)\s*(L|Lt|Lt\.)\b', name)
    if m: return float(m.group(1).replace(',', '.')) * 1000
    m = re.search(r'(\d+[,.]?\d*)\s*(Ml|ml|ML)\b', name)
    if m: return float(m.group(1).replace(',', '.'))
    return None

def extract_piece_count(name: str):
    m = re.search(r"(\d+)['\u2019]?\s*(?:li|lu|lı|lü|'li|'lu)\b", name, re.IGNORECASE)
    if m: return int(m.group(1))
    m2 = re.search(r"(\d+)'?\s*[Ll][Üü]\b", name)
    if m2: return int(m2.group(1))
    m3 = re.search(r"(\d+)\s*[Aa]det", name)
    if m3: return int(m3.group(1))
    return None

# ── 6. UNIT PRICE CALCULATOR ────────────────────────────
def get_unit_price(df: pd.DataFrame, product_label: str) -> dict:
    rule = MATCH_RULES[product_label]

    if not rule['keywords']:
        return {'avg_unit_price': float('nan'), 'median_unit_price': float('nan'),
                'n_products': 0, 'matched_names': 'N/A'}

    mask = df['name'].apply(
        lambda x: any(re.search(r'\b' + re.escape(k) + r'\b', str(x), re.IGNORECASE)
                      for k in rule['keywords'])
    )
    sub = df[mask].copy()

    for exc in rule['exclude']:
        sub = sub[~sub['name'].str.contains(re.escape(exc), case=False, na=False)]

    if sub.empty:
        return {'avg_unit_price': float('nan'), 'median_unit_price': float('nan'),
                'n_products': 0, 'matched_names': '—'}

    unit  = rule['unit']
    min_p = rule.get('min_price_per_kg', 0)
    max_p = rule.get('max_price_per_kg', None)
    prices = []

    for _, row in sub.iterrows():
        name      = str(row['name'])
        price     = float(row['price'])
        is_per_kg = bool(row['is_per_kg'])

        if unit == 'kg':
            if is_per_kg:
                per_u = price
            else:
                w = extract_weight_g(name)
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
            else:
                prices.append(price)

    avg    = sum(prices) / len(prices) if prices else float('nan')
    median = float(pd.Series(prices).median()) if prices else float('nan')
    names  = '; '.join(str(r['name'])[:45] + ('…' if len(str(r['name'])) > 45 else '')
                       for _, r in sub.iterrows())
    return {'avg_unit_price': round(avg, 2), 'median_unit_price': round(median, 2),
            'n_products': len(prices), 'matched_names': names}

# ── 7. MONTHLY COMPUTATION ──────────────────────────────
def compute_hunger_threshold(csv_path: str, date_label: str) -> pd.DataFrame:
    df = load_file(csv_path)
    rows = []
    for category, product_label, unit_label, monthly_qty in FOOD_BASKET:
        info         = get_unit_price(df, product_label)
        avg_price    = info['avg_unit_price']
        median_price = info['median_unit_price']
        rows.append({
            'date':                    date_label,
            'category':                category,
            'product':                 product_label,
            'unit':                    unit_label,
            'monthly_qty':             monthly_qty,
            'avg_unit_price_TRY':      avg_price,
            'avg_monthly_cost_TRY':    round(avg_price    * monthly_qty, 2) if pd.notna(avg_price)    else float('nan'),
            'median_unit_price_TRY':   median_price,
            'median_monthly_cost_TRY': round(median_price * monthly_qty, 2) if pd.notna(median_price) else float('nan'),
            'n_matched':               info['n_products'],
            'matched_products':        info['matched_names'],
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
    avg_total    = df_month['avg_monthly_cost_TRY'].sum()
    median_total = df_month['median_monthly_cost_TRY'].sum()
    n_na         = df_month['avg_unit_price_TRY'].isna().sum()
    all_results.append(df_month)
    summary_rows.append({
        'date':                        date_label,
        'avg_hunger_threshold_TRY':    round(avg_total,    2),
        'median_hunger_threshold_TRY': round(median_total, 2),
        'n_na':                        int(n_na),
    })

    na_note = f'  [{n_na} items N/A — not in catalog]' if n_na else ''
    print(f"\n{'='*100}")
    print(f"  {date_label}  —  Avg: ₺{avg_total:,.2f}  |  Median: ₺{median_total:,.2f}{na_note}")
    print(f"{'='*100}")
    print(f"  {'Category':<22} {'Product':<30} {'Qty':>5} {'Avg Price':>11} {'Avg Cost':>12} {'Med Price':>11} {'Med Cost':>12}  {'N':>4}")
    print(f"  {'-'*22} {'-'*30} {'-'*5} {'-'*11} {'-'*12} {'-'*11} {'-'*12}  {'-'*4}")
    for _, r in df_month.iterrows():
        ap = f"₺{r['avg_unit_price_TRY']:>8,.2f}"      if pd.notna(r['avg_unit_price_TRY'])     else "       N/A"
        ac = f"₺{r['avg_monthly_cost_TRY']:>9,.2f}"    if pd.notna(r['avg_monthly_cost_TRY'])   else "        N/A"
        mp = f"₺{r['median_unit_price_TRY']:>8,.2f}"   if pd.notna(r['median_unit_price_TRY'])  else "       N/A"
        mc = f"₺{r['median_monthly_cost_TRY']:>9,.2f}" if pd.notna(r['median_monthly_cost_TRY']) else "        N/A"
        print(f"  {r['category']:<22} {r['product']:<30} {r['monthly_qty']:>5.1f}  {ap}  {ac}  {mp}  {mc}  {r['n_matched']:>4}")

if not all_results:
    print("No data to summarise.")
else:
    all_df     = pd.concat(all_results, ignore_index=True)
    summary_df = pd.DataFrame(summary_rows)

    print('\n\n' + '='*65)
    print('  MONTHLY HUNGER THRESHOLD SUMMARY')
    print('='*65)
    print(f"  {'Date':<14} {'Avg (₺)':>16}  {'Median (₺)':>16}  {'MoM Avg':>8}  {'MoM Median':>10}  {'N/A':>5}")
    print(f"  {'-'*14} {'-'*16}  {'-'*16}  {'-'*8}  {'-'*10}  {'-'*5}")
    prev_avg = prev_med = None
    for _, r in summary_df.iterrows():
        mom_avg = f"{(r['avg_hunger_threshold_TRY']    - prev_avg) / prev_avg * 100:+.1f}%" if prev_avg else '—'
        mom_med = f"{(r['median_hunger_threshold_TRY'] - prev_med) / prev_med * 100:+.1f}%" if prev_med else '—'
        na      = f"[{r['n_na']} N/A]" if r['n_na'] else ''
        print(f"  {r['date']:<14} ₺{r['avg_hunger_threshold_TRY']:>14,.2f}  ₺{r['median_hunger_threshold_TRY']:>14,.2f}  {mom_avg:>8}  {mom_med:>10}  {na}")
        prev_avg = r['avg_hunger_threshold_TRY']
        prev_med = r['median_hunger_threshold_TRY']

    all_df.to_csv(OUTPUT_DETAIL,  index=False)
    summary_df.to_csv(OUTPUT_SUMMARY, index=False)
    print(f"\nDetail  → {OUTPUT_DETAIL}")
    print(f"Summary → {OUTPUT_SUMMARY}")
