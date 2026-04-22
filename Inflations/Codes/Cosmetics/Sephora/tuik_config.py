"""
tuik_config.py — TUIK CPI basket weights and Sephora category mapping.

Provides:
  - TUIK_WEIGHTS: 2026 CPI main-group weights (base year 2025=100)
  - normalised_weights(): rescale weights for a subset of present groups
  - sephora_category_to_tuik(): map Sephora breadcrumb strings to TUIK codes

Sephora only sells cosmetics / personal-care / perfumery, so the vast
majority of products map to TUIK group **12** ("Kişisel bakım, sosyal
koruma ve çeşitli mal ve hizmetler", weight 4.49%).  A small number of
tile-based accessories (brushes, mirrors, pouches, travel kits) map to
group **05** (Mobilya, ev aletleri ve ev bakım hizmetleri) to match how
the Migros / Koton calculators classify identical items.
"""

# ── TUIK 2026 TÜFE Main-Group Weights ────────────────────────────────────────
# Source: TÜİK, published 2026-03-03, base year 2025=100.  Kept identical to
# the Koton / Migros calculators so downstream cross-store comparisons use
# consistent weights.
TUIK_WEIGHTS = {
    "01": {"name": "Gıda ve alkolsüz içecekler",                                "weight": 24.44},
    "02": {"name": "Alkollü içecekler, tütün ve tütün ürünleri",                 "weight": 2.75},
    "03": {"name": "Giyim ve ayakkabı",                                          "weight": 7.90},
    "04": {"name": "Konut, su, elektrik, gaz ve diğer yakıtlar",                 "weight": 11.40},
    "05": {"name": "Mobilya, ev aletleri ve ev bakım hizmetleri",                "weight": 7.92},
    "06": {"name": "Sağlık",                                                     "weight": 2.79},
    "07": {"name": "Ulaştırma",                                                  "weight": 16.62},
    "08": {"name": "Bilgi ve iletişim",                                          "weight": 3.10},
    "09": {"name": "Eğlence, dinlence, spor ve kültür",                          "weight": 4.34},
    "10": {"name": "Eğitim",                                                     "weight": 2.02},
    "11": {"name": "Lokantalar ve konaklama hizmetleri",                         "weight": 11.13},
    "12": {"name": "Kişisel bakım, sosyal koruma ve çeşitli mal ve hizmetler",   "weight": 4.49},
    "13": {"name": "Sigorta ve finansal hizmetler",                              "weight": 1.07},
}


def normalised_weights(present_codes):
    """Return a dict {code: normalised_weight} for the TUIK groups in *present_codes*.

    Weights are rescaled so that they sum to 100.0 among the present
    groups.  Codes not in :data:`TUIK_WEIGHTS` are ignored.
    """
    raw = {c: TUIK_WEIGHTS[c]["weight"] for c in present_codes if c in TUIK_WEIGHTS}
    total = sum(raw.values())
    if total == 0:
        return {}
    return {c: (w / total) * 100.0 for c, w in raw.items()}


# ─── Sephora Category → TUIK Group ───────────────────────────────────────────
# Sephora tiles expose two category-ish fields:
#   - ``category`` : breadcrumb label (e.g. "makeup/dudak/lipstick")
#   - ``category_id``: slug of the category page the tile was scraped from
#                       (e.g. "makyaj-c302", "sac-c307", "vucut-ve-banyo-c304").
# Both are lower-cased strings.  The mapping below works on either.

# Keywords that push a product into TUIK group 05 (household / small
# appliances).  These cover the small non-cosmetic accessories Sephora
# stocks alongside cosmetics.
_TUIK_05_KEYWORDS = (
    "firca",              # brushes (Turkish: fırça)
    "fırça",
    "ayna",               # mirrors
    "canta",              # bags / pouches (Turkish: çanta)
    "çanta",
    "sac-firca",
    "saç fırça",
    "makyaj-canta",
    "makyaj-firca",
    "makyaj çanta",
    "makyaj fırça",
)

# Default for everything else: TUIK 12 (personal care & cosmetics).
_DEFAULT_TUIK_CODE = "12"


def sephora_category_to_tuik(category_value) -> str:
    """Map a Sephora category string to its TUIK main-group code.

    Accepts either the breadcrumb label (``category`` column) or the
    category slug (``category_id`` column).  Falls back to TUIK group 12
    for unknown / missing values because Sephora is overwhelmingly a
    personal-care retailer.
    """
    if not category_value or not isinstance(category_value, str):
        return _DEFAULT_TUIK_CODE

    haystack = category_value.strip().lower()
    if not haystack:
        return _DEFAULT_TUIK_CODE

    for kw in _TUIK_05_KEYWORDS:
        if kw in haystack:
            return "05"
    return _DEFAULT_TUIK_CODE
