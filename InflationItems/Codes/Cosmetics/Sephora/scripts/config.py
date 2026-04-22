"""
Sephora Scraper Configuration Module
====================================

Central configuration for the Sephora Türkiye (sephora.com.tr) product
scraping system.  Sephora serves its storefront through Salesforce
Commerce Cloud (Demandware) and protects it with **Akamai Bot
Manager**.  Naive HTTP clients (including TLS-impersonating ones like
``curl_cffi``) get flagged quickly across every fingerprint Akamai
knows about, so the scraper drives a real Chrome browser through
``undetected-chromedriver`` — the same approach the IstanbulAvrupa
scraper uses against Sahibinden's identical Akamai setup.

Configuration Sections
----------------------
Base URLs and Endpoints
    Root domain, sitemap, and category endpoint definitions.

Main Categories
    Top-level category slugs that together cover the full catalogue.

Browser Automation
    Chromedriver path, persistent user-profile directory, pacing, and
    Chrome version matching.

Path Management
    File paths for CSV output and daily checkpoints, resolved
    relative to this config so the scraper works regardless of the
    working directory from which ``main.py`` is launched.

Daily File Naming
-----------------
Files use a ``YYYY-MM-DD`` suffix so each daily run produces its own set:

- CSV Export : ``sephora_YYYY-MM-DD.csv``
- Checkpoint : ``sephora_checkpoint_YYYY-MM-DD.json``
"""

import datetime as _dt
from pathlib import Path as _Path

# ── Path helpers ─────────────────────────────────────────────────────────────
_SCRIPTS_DIR  = _Path(__file__).resolve().parent              # …/Cosmetics/Sephora/scripts
_SEPHORA_DIR  = _SCRIPTS_DIR.parent                           # …/Cosmetics/Sephora
_PROJECT_ROOT = _SEPHORA_DIR.parent.parent.parent.parent      # …/InflationResearchStudy

# ── Base URLs ────────────────────────────────────────────────────────────────
BASE_URL = "https://www.sephora.com.tr"

# Sitemap index containing the per-type sitemaps (category, product, content, ...)
SITEMAP_INDEX_URL = f"{BASE_URL}/sitemap_index.xml"

# Category-only sitemap (URLs of the form .../slug-c<id>/)
CATEGORY_SITEMAP_URL = f"{BASE_URL}/sitemap-customsitemap_category_0.xml"

# ── Main (top-level) categories ──────────────────────────────────────────────
# Sephora's sitemap exposes 8 root-level category URLs.  Scraping just
# these covers the whole catalogue (sub-category products are duplicated
# inside their parent).  ``category_fetcher.fetch_categories(level="all")``
# returns every sub-category URL as well for fine-grained slicing.
MAIN_CATEGORY_SLUGS = [
    "makyaj-c302",
    "parfum-c301",
    "parfum-parfum-setleri-c7601",
    "nis-parfum-c300501",
    "cilt-bakimi-c303",
    "cilt-bakimi-erkek-yuz-bakimi-anti-aging-c508",
    "vucut-ve-banyo-c304",
    "sac-c307",
]

# ── Output / Checkpoint Paths ────────────────────────────────────────────────
# Base output directory  →  InflationItems/Datas/Cosmetics/Sephora/
BASE_OUTPUT_DIR = str(_PROJECT_ROOT / "InflationItems" / "Datas" / "Cosmetics" / "Sephora")

# CSV output and helper inflation sub-directory
OUTPUT_DIR    = str(_Path(BASE_OUTPUT_DIR))
INFLATION_DIR = str(_Path(BASE_OUTPUT_DIR) / "InflationData")

# Checkpoint directory  →  InflationItems/Codes/Cosmetics/Sephora/checkpoints/
CHECKPOINT_DIR = str(_SEPHORA_DIR / "checkpoints")

# Daily filenames
_TODAY = _dt.date.today().strftime("%Y-%m-%d")

CSV_OUTPUT_FILE = str(_Path(OUTPUT_DIR)     / f"sephora_{_TODAY}.csv")
CHECKPOINT_FILE = str(_Path(CHECKPOINT_DIR) / f"sephora_checkpoint_{_TODAY}.json")

# ── Browser Automation (undetected-chromedriver) ─────────────────────────────
# The scraper reuses the chromedriver binary already bundled with the
# IstanbulAvrupa (Sahibinden) scraper – they target the same local
# Chrome installation so keeping one copy simplifies version matching.
SELENIUM_PROFILE_DIR = str(_SEPHORA_DIR / "SeleniumProfile")
CHROMEDRIVER_PATH    = str(_PROJECT_ROOT / "InflationItems" / "Codes" / "HousesRent" / "chromedriver")

# Browser pacing.  Chrome's normal page load + humanised behaviour is
# enough stealth; aggressive delay is unnecessary.
BROWSER_PAGE_LOAD_DELAY = 3.5   # seconds between category-page loads
BROWSER_MAX_WAIT_TILES  = 30    # seconds waited for product tiles before prompting
BROWSER_HEADLESS        = False # default to headful – Akamai detects headless more easily

# Main Chrome version that matches the bundled chromedriver (147).
BROWSER_VERSION_MAIN = 147
