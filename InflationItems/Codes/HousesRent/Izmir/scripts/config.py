"""
Configuration settings for the Izmir rent scraper.
Source: sahibinden.com

Bracket Strategy: Smart Adaptive Brackets with Early Peek
---------------------------------------------------------
Instead of static brackets, we use wide seed ranges. On the first page of any
range, the scraper peeks at the "Total Listings Found" text.
  - If <= 1000: It safely scrapes all pages.
  - If > 1000: It immediately splits the range in half and recurses.
This guarantees speed (no wasted scraping) and complete data capture.
"""

import datetime as _dt
from pathlib import Path as _Path

# ── Paths ─────────────────────────────────────────────────────────────────────
_SCRIPTS_DIR   = _Path(__file__).resolve().parent          # …/Izmir/scripts
_SCRAPER_DIR   = _SCRIPTS_DIR.parent                       # …/Izmir
_PROJECT_ROOT  = _SCRAPER_DIR.parent.parent.parent         # …/InflationResearchStudy

# ── City Settings ─────────────────────────────────────────────────────────────
CITY_URL_NAME = "izmir"
FOLDER_NAME   = "Izmir"

# ── Seed Ranges ───────────────────────────────────────────────────────────────
# Wide starting ranges. The scraper will automatically slice these into optimal
# brackets using the "Total Listings" count on the first page.
# These ranges will be quite sufficient for Izmir.
SEED_RANGES = [
    (0,      9_999),
    (10_000, 14_999),
    (15_000, 16_249),
    (16_249, 17_499),
    (17_500, 18_749),
    (18_750, 19_999),
    (20_000, 20_039),
    (20_040, 20_078),
    (20_079, 20_156),
    (20_157, 20_312),
    (20_313, 20_624),
    (20_625, 21_249),
    (21_250, 22_499),
    (22_500, 23_593),
    (23_594, 24_687),
    (24_688, 24_961),
    (24_962, 24_996),
    (24_997, 25_030),
    (25_031, 25_098),
    (25_099, 25_234),
    (25_235, 25_781),
    (25_782, 26_874),
    (26_874, 27_968),
    (27_969, 29_062),
    (29_063, 29_609),
    (29_610, 29_883),
    (29_884, 29_952),
    (29_953, 29_986),
    (29_987, 30_020),
    (30_021, 30_156),
    (30_157, 31_249),
    (31_250, 33_437),
    (33_438, 34_531),
    (34_532, 34_805),
    (34_806, 34_942),
    (34_943, 35_259),
    (35_260, 35_575),
    (35_576, 36_207),
    (36_208, 37_471),
    (37_472, 39_999),
    (40_000, 44_999),
    (45_000, 49_999),
    (50_000, 59_999),
    (60_000, 79_999),
    (80_000, 99_999),
    (100_000, 718_749),
    (718_750, 1_337_499),
    (1_337_500, 2_574_999),
    (2_575_000, 5_049_999),
    (5_050_000, 9_999_999)
]

# ── Adaptive Splitting Settings ───────────────────────────────────────────────
# Sahibinden limits queries to 1000 listings (20 pages of 50).
# We split if the total count exceeds this threshold.
MAX_LISTINGS_PER_QUERY = 1000

# Minimum bracket width (TL). A safety valve against infinite recursion if >1000
# listings share the exact same price.
MIN_BRACKET_WIDTH = 50

# ── Request / Timing Settings ─────────────────────────────────────────────────
PAGE_SIZE              = 50             # Listings per page (sahibinden max)
PAGE_LOAD_DELAY        = 2.5            # Seconds to wait after a page loads
PAGE_TURN_DELAY_MIN    = 2.0            # Random range between page turns (s)
PAGE_TURN_DELAY_MAX    = 4.0
BETWEEN_BRACKET_DELAY_MIN = 1.0         # Random range between brackets (s)
BETWEEN_BRACKET_DELAY_MAX = 2.0

# ── Browser Settings ──────────────────────────────────────────────────────────
SELENIUM_PROFILE_DIR = str(_SCRAPER_DIR / "SeleniumProfile")

# ── Output Settings ───────────────────────────────────────────────────────────
_TODAY = _dt.date.today().strftime("%Y-%m-%d")

OUTPUT_DIR      = str(_PROJECT_ROOT / "Datas" / "HousesRent" / FOLDER_NAME)
CHECKPOINT_DIR  = str(_SCRAPER_DIR / "checkpoints")

CSV_OUTPUT_FILE = str(_Path(OUTPUT_DIR)     / f"{FOLDER_NAME}_{_TODAY}.csv")
CHECKPOINT_FILE = str(_Path(CHECKPOINT_DIR) / f"checkpoint_{_TODAY}.json")