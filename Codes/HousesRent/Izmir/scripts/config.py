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
# İzmir için bu aralıklar gayet yeterli olacaktır.
SEED_RANGES = [
    (0,      19_999),   # High density, will trigger multiple splits
    (20_000, 39_999),   # High density
    (40_000, 59_999),
    (60_000, 99_999),
    (100_000, 9_999_999), # Low density, likely won't split at all
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