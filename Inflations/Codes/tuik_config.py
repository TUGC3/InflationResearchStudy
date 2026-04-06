"""
tuik_config.py — Shared TUIK CPI basket weights and normalisation utility.

Provides:
  - TUIK_WEIGHTS: 2026 CPI main-group weights (base year 2025=100)
  - normalised_weights(): rescale weights for a subset of present groups
"""

# Source: TUIK, published 2026-03-03, base year 2025=100
TUIK_WEIGHTS = {
    "01": {"name": "Gida ve alkolsuz icecekler",                                "weight": 24.44},
    "02": {"name": "Alkollu icecekler, tutun ve tutun urunleri",                 "weight": 2.75},
    "03": {"name": "Giyim ve ayakkabi",                                          "weight": 7.90},
    "04": {"name": "Konut, su, elektrik, gaz ve diger yakitlar",                 "weight": 11.40},
    "05": {"name": "Mobilya, ev aletleri ve ev bakim hizmetleri",                "weight": 7.92},
    "06": {"name": "Saglik",                                                     "weight": 2.79},
    "07": {"name": "Ulastirma",                                                  "weight": 16.62},
    "08": {"name": "Bilgi ve iletisim",                                          "weight": 3.10},
    "09": {"name": "Eglence, dinlence, spor ve kultur",                          "weight": 4.34},
    "10": {"name": "Egitim",                                                     "weight": 2.02},
    "11": {"name": "Lokantalar ve konaklama hizmetleri",                         "weight": 11.13},
    "12": {"name": "Kisisel bakim, sosyal koruma ve cesitli mal ve hizmetler",   "weight": 4.49},
    "13": {"name": "Sigorta ve finansal hizmetler",                              "weight": 1.07},
}


def normalised_weights(present_codes):
    """Return {code: normalised_weight} for only the TUIK groups in *present_codes*.

    Weights are rescaled so they sum to 100.0 among the present groups.
    """
    raw = {c: TUIK_WEIGHTS[c]["weight"] for c in present_codes if c in TUIK_WEIGHTS}
    total = sum(raw.values())
    if total == 0:
        return {}
    return {c: (w / total) * 100.0 for c, w in raw.items()}
