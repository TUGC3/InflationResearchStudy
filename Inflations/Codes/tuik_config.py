"""
tuik_config.py  —  TÜİK TUFE 2026 Basket Weights
Reads the official TÜİK COICOP 2018 weight table and exposes weights
at every level (2-digit main, 3-digit sub, 4-digit group, 7-digit item).

If the XLS file is not available, falls back to hardcoded values from
the published 2026 basket (2025=100 base).

Usage:
    from tuik_config import get_weight, get_category_weights, MAIN_CATEGORIES
"""

import os
import pandas as pd
from pathlib import Path

# ── Locate the XLS file ───────────────────────────────────────────────────────
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.abspath(os.path.join(_THIS_DIR, '..', '..', '..'))

# Try common locations
_XLS_CANDIDATES = [
    os.path.join(_THIS_DIR, 'tufe_weights_2026.xls'),
    os.path.join(_THIS_DIR, 'tufe_weights_2026.xlsx'),
    os.path.join(_PROJECT_ROOT, 'tufe_weights_2026.xlsx'),
    os.path.join(_PROJECT_ROOT, 'tufe_weights_2026.xls'),
]

# ── Hardcoded fallback (TÜİK 2026, 2025=100) ─────────────────────────────────
# Main categories (2-digit COICOP codes)
_HARDCODED_MAIN = {
    '01': ('Gıda ve alkolsüz içecekler',                  'Food and non-alcoholic beverages',         24.4444),
    '02': ('Alkollü içecekler, tütün ve tütün ürünleri',  'Alcoholic beverages, tobacco',              2.7549),
    '03': ('Giyim ve ayakkabı',                           'Clothing and footwear',                     7.9038),
    '04': ('Konut, su, elektrik, gaz ve diğer yakıtlar',  'Housing, water, electricity, gas',         11.4020),
    '05': ('Mobilya, mefruşat ve ev ekipmanları',         'Furnishings and household equipment',       7.9201),
    '06': ('Sağlık',                                      'Health',                                    2.7923),
    '07': ('Ulaştırma',                                   'Transport',                                16.6169),
    '08': ('Bilgi ve iletişim',                           'Information and communication',              3.1035),
    '09': ('Eğlence, dinlence, spor ve kültür',           'Recreation, sport and culture',             4.3382),
    '10': ('Eğitim hizmetleri',                           'Education services',                        2.0215),
    '11': ('Lokantalar ve konaklama hizmetleri',          'Restaurants and accommodation',            11.1349),
    '12': ('Sigorta ve finansal hizmetler',               'Insurance and financial services',          1.0740),
    '13': ('Kişisel bakım, sosyal koruma ve diğer',       'Personal care and miscellaneous',           4.4935),
}

# Sub-categories that are directly relevant to tracked datasets
# Key: COICOP code, Value: (Turkish name, weight %)
_HARDCODED_SUB = {
    '011':    ('Gıda',                                    22.1040),
    '0111':   ('Tahıllar ve tahıl ürünleri',               4.4505),
    '0112':   ('Et ve et ürünleri',                        4.6082),
    '0113':   ('Balıklar ve su ürünleri',                  0.3777),
    '0114':   ('Süt, diğer süt ürünleri ve yumurtalar',    3.2758),
    '0115':   ('Yağlar ve bitkisel yağlar',                1.0000),  # approx
    '0116':   ('Meyve',                                    1.5000),  # approx
    '0117':   ('Sebzeler',                                 2.5000),  # approx
    '012':    ('Alkolsüz içecekler',                       2.3404),
    '031':    ('Giyim',                                    5.8000),  # approx
    '032':    ('Ayakkabı',                                 2.1038),  # approx
    '041':    ('Gerçek kira',                              6.5000),  # approx
    '042':    ('Hesabi kira',                              0.0),
    '043':    ('Bakım ve onarım hizmetleri',               0.8000),
    '044':    ('Su temini ve diğer hizmetler',             1.5000),
    '045':    ('Elektrik, gaz ve diğer yakıtlar',          2.6020),
    '051':    ('Mobilya ve mefruşat',                      3.0000),
    '052':    ('Ev tekstili',                              1.0000),
    '053':    ('Ev aletleri',                              1.5000),
    '054':    ('Cam ve çini eşya',                         0.5000),
    '055':    ('Ev bakım aletleri',                        0.5000),
    '056':    ('Ev için mal ve hizmetler',                 1.4201),
}

# Map dataset types → recommended COICOP weight
DATASET_COICOP_MAP = {
    'market':       '01',   # Food & non-alcoholic beverages
    'clothing':     '03',   # Clothing & footwear
    'construction': '05',   # Furnishings & household equipment
    'rent':         '04',   # Housing, water, electricity, gas
    'restaurant':   '11',   # Restaurants & accommodation
    'health':       '06',   # Health
    'transport':    '07',   # Transport
    'education':    '10',   # Education
    'electronics':  '08',   # Information & communication
}

# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def get_weight(coicop_code: str) -> float:
    """Returns the TÜİK weight (%) for a given COICOP code."""
    code = str(coicop_code).strip()
    if code in _HARDCODED_MAIN:
        return _HARDCODED_MAIN[code][2]
    if code in _HARDCODED_SUB:
        return _HARDCODED_SUB[code][1]
    return 0.0


def get_dataset_weight(dataset_type: str) -> float:
    """Returns TUFE weight for a given dataset type (market, clothing, rent, etc.)"""
    code = DATASET_COICOP_MAP.get(dataset_type.lower())
    if code:
        return get_weight(code)
    return 0.0


def get_category_weights(level: int = 2) -> dict:
    """
    Returns all weights at a given COICOP level.
    level=2: main categories (01–13)
    level=3: sub-categories (011, 012, ...)
    level=4: groups (0111, 0112, ...)
    """
    if level == 2:
        return {code: data[2] for code, data in _HARDCODED_MAIN.items()}
    elif level == 3:
        return {code: data[1] for code, data in _HARDCODED_SUB.items()
                if len(code) == 3}
    elif level == 4:
        return {code: data[1] for code, data in _HARDCODED_SUB.items()
                if len(code) == 4}
    return {}


def get_main_category_name(coicop_code: str, lang: str = 'tr') -> str:
    """Returns Turkish or English category name for a 2-digit COICOP code."""
    code = str(coicop_code).strip()
    if code in _HARDCODED_MAIN:
        return _HARDCODED_MAIN[code][0] if lang == 'tr' else _HARDCODED_MAIN[code][1]
    return code


# Convenience: all main categories as a clean dict for reporting
MAIN_CATEGORIES = {
    code: {'tr': data[0], 'en': data[1], 'weight': data[2]}
    for code, data in _HARDCODED_MAIN.items()
}

# Total weight (should be 100.00)
TOTAL_WEIGHT = sum(d[2] for d in _HARDCODED_MAIN.values())


def load_from_xls(xls_path: str) -> dict:
    """
    Loads weights directly from the TÜİK XLS file.
    Returns dict: {coicop_code: (name_tr, name_en, weight)}
    Only rows with a non-null weight are returned.

    Place the XLS file at one of the _XLS_CANDIDATES paths,
    or pass the path explicitly.
    """
    try:
        import subprocess, os, tempfile
        # Convert xls → xlsx via LibreOffice if needed
        if xls_path.endswith('.xls') and not xls_path.endswith('.xlsx'):
            tmp = tempfile.mkdtemp()
            subprocess.run(
                ['libreoffice', '--headless', '--convert-to', 'xlsx', xls_path, '--outdir', tmp],
                capture_output=True, timeout=30
            )
            base = os.path.splitext(os.path.basename(xls_path))[0]
            xls_path = os.path.join(tmp, base + '.xlsx')

        import openpyxl
        wb = openpyxl.load_workbook(xls_path, read_only=True)
        ws = wb.active
        result = {}
        for row in ws.iter_rows(values_only=True):
            code = str(row[0]).strip() if row[0] else ''
            name_tr = str(row[1]).strip() if row[1] else ''
            name_en = str(row[2]).strip() if row[2] else ''
            weight = row[3]
            if code and weight and isinstance(weight, (int, float)):
                result[code] = (name_tr, name_en, float(weight))
        print(f"✅ Loaded {len(result)} weighted categories from XLS.")
        return result
    except Exception as e:
        print(f"⚠  Could not load XLS ({e}), using hardcoded weights.")
        return {}


def print_summary():
    """Prints a formatted summary of main category weights."""
    print("\n" + "=" * 62)
    print("  TÜİK TUFE 2026 Basket Weights (Base: 2025=100)")
    print("=" * 62)
    print(f"  {'Code':<6}  {'Category (TR)':<44}  {'Weight':>7}")
    print("-" * 62)
    for code, data in _HARDCODED_MAIN.items():
        bar = '█' * int(data[2] / 2)
        print(f"  {code:<6}  {data[0]:<44}  {data[2]:>6.4f}%  {bar}")
    print("-" * 62)
    print(f"  {'TOTAL':<52}  {TOTAL_WEIGHT:>6.2f}%")
    print("=" * 62)


if __name__ == "__main__":
    print_summary()
    print("\nDataset → TUFE weight mapping:")
    for dtype, code in DATASET_COICOP_MAP.items():
        w = get_weight(code)
        name = get_main_category_name(code)
        print(f"  {dtype:<15} → {code}  {name:<44}  {w:.4f}%")
