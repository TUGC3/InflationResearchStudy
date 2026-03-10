"""
config.py — Configuration settings for the Istanbul Avrupa rent scraper.
========================================================================

Configuration settings for the Istanbul Avrupa (European Side) rent scraper.
Source: sahibinden.com

Sections
--------
Paths
    Directory paths for the scraper, output, and checkpoints.

City Settings
    Constants defining the target city for URLs and folders.

Seed Ranges
    Wide starting price ranges that the scraper automatically splits into
    optimal leaf brackets using the adaptive bracket splitting strategy.

Adaptive Splitting Settings
    Constants related to the algorithm that works around sahibinden.com's
    limits per query (e.g. threshold caps and minimum bracket width).

Request / Timing Settings
    Timing configurations for page loads and delays to prevent detection by
    anti-scraping mechanisms.

Browser Settings
    Location configurations for the persistent Selenium profile.

Output Settings
    Output directories and daily-stamped filenames for CSVs and checkpoints.
"""

import datetime as _dt
from pathlib import Path as _Path

# ── Paths ─────────────────────────────────────────────────────────────────────
_SCRIPTS_DIR   = _Path(__file__).resolve().parent          # …/InflationItems/Codes/HousesRent/IstanbulAvrupa/scripts
_SCRAPER_DIR   = _SCRIPTS_DIR.parent                       # …/InflationItems/Codes/HousesRent/IstanbulAvrupa
_PROJECT_ROOT  = _SCRAPER_DIR.parent.parent.parent.parent  # …/InflationResearchStudy

# ── City Settings ─────────────────────────────────────────────────────────────
CITY_URL_NAME = "istanbul-avrupa"
FOLDER_NAME   = "IstanbulAvrupa"

# ── Seed Ranges ───────────────────────────────────────────────────────────────
# Wide starting ranges. The scraper will automatically slice these into optimal
# brackets using the "Total Listings" count on the first page.
SEED_RANGES = [
    (0,      19_999),   # High density, will trigger multiple splits
    (20_000, 39_999),   # High density
    (40_000, 59_999),
    (60_000, 99_999),
    (100_000, 9_999_999), # Low density, likely won't split at all
]

# ── Adaptive Splitting Settings ─────────────────────────────────────────────────
# Sahibinden limits queries to 1000 listings (20 pages of 50).
# We split if the total count exceeds this threshold.
MAX_LISTINGS_PER_QUERY = 1000

# Minimum bracket width (TL). A safety valve against infinite recursion if >1000
# listings share the exact same price.
MIN_BRACKET_WIDTH = 50

# ── Request / Timing Settings ─────────────────────────────────────────────────
PAGE_SIZE              = 50             # Listings per page (sahibinden max)
PAGE_LOAD_DELAY        = 2.5            # Seconds to wait after a page loads
                                        # Also the base for the per-page jitter:
                                        #   actual wait = PAGE_LOAD_DELAY * uniform(0.5, 1.5)
BETWEEN_BRACKET_DELAY_MIN = 1.0         # Random range between splits during discovery (s)
BETWEEN_BRACKET_DELAY_MAX = 2.0

# ── Browser Settings ──────────────────────────────────────────────────────────
SELENIUM_PROFILE_DIR = str(_SCRAPER_DIR / "SeleniumProfile")

# ── Output Settings ───────────────────────────────────────────────────────────
_TODAY = _dt.date.today().strftime("%Y-%m-%d")

# Base output directory
BASE_OUTPUT_DIR = str(_PROJECT_ROOT / "InflationItems" / "Datas" / "HousesRent" / FOLDER_NAME)

OUTPUT_DIR      = str(_Path(BASE_OUTPUT_DIR))
INFLATION_DIR   = str(_Path(BASE_OUTPUT_DIR) / "InflationData")

CHECKPOINT_DIR  = str(_SCRAPER_DIR / "checkpoints")

CSV_OUTPUT_FILE = str(_Path(OUTPUT_DIR)     / f"{FOLDER_NAME}_{_TODAY}.csv")
CHECKPOINT_FILE = str(_Path(CHECKPOINT_DIR) / f"checkpoint_{_TODAY}.json")
