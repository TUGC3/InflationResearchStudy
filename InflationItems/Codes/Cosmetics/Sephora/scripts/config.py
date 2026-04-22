"""
Sephora Scraper Configuration Module
====================================

Central configuration for the Sephora Türkiye (sephora.com.tr) product
scraping system.  Sephora serves its storefront through Salesforce
Commerce Cloud (Demandware) and protects it with Akamai Bot Manager, so
the scraper relies on ``curl_cffi`` with browser-grade TLS
impersonation instead of plain ``requests``.

Configuration Sections
----------------------
Base URLs and Endpoints
    Root domain, sitemap, and category endpoint definitions.

HTTP Request Configuration
    Headers, impersonation profiles, and session parameters required
    to pass Akamai's TLS / JA3 fingerprinting.

Scraping Parameters
    Delays, retries, concurrency, and rate-limit back-off tuning.

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

# ── Base URLs ────────────────────────────────────────────────────────────────
BASE_URL = "https://www.sephora.com.tr"

# Sitemap index containing the per-type sitemaps (category, product, content, ...)
SITEMAP_INDEX_URL = f"{BASE_URL}/sitemap_index.xml"

# Category-only sitemap (URLs of the form .../slug-c<id>/)
CATEGORY_SITEMAP_URL = f"{BASE_URL}/sitemap-customsitemap_category_0.xml"

# ── curl_cffi Impersonation Targets ──────────────────────────────────────────
# Safari profiles are the most reliable for bypassing Sephora's Akamai
# TLS / JA3 fingerprint check.  Akamai rotates which fingerprints are
# accepted per source IP, so the scraper tries these in order and
# rotates on bot-challenge failures.  ``safari17_2_ios`` and
# ``safari15_3`` have empirically been the most consistently-accepted
# profiles against category pages.
IMPERSONATE_PROFILES = [
    "safari17_2_ios",
    "safari15_3",
    "safari17_0",
    "safari15_5",
    "chrome124",
    "chrome120",
]

# ── Request Headers ──────────────────────────────────────────────────────────
# curl_cffi sets most browser headers automatically per impersonation
# profile, but we still need an explicit ``Accept-Language`` so Sephora
# returns the Turkish locale and the product tiles' data-tcproduct
# attribute is populated.
DEFAULT_HEADERS = {
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,image/apng,*/*;q=0.8,"
        "application/signed-exchange;v=b3;q=0.7"
    ),
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
    "Upgrade-Insecure-Requests": "1",
}

# ── Main (top-level) categories ──────────────────────────────────────────────
# Sephora's sitemap exposes 8 root-level category URLs.  Scraping just
# these covers the whole catalog (sub-category products are duplicated
# inside their parent).  The sub-category URLs are kept in the sitemap
# output in case a caller wants fine-grained slicing – see
# ``category_fetcher.fetch_categories(level="sub")``.
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

# ── Scraping Parameters ──────────────────────────────────────────────────────
# Conservative defaults because Akamai aggressively rate-limits bots.
REQUEST_DELAY = 2.5          # base delay between page requests (seconds)
JITTER_MIN = 0.7             # jitter multiplier lower bound
JITTER_MAX = 1.4             # jitter multiplier upper bound

MAX_RETRIES = 5              # maximum retry attempts on transient errors
RETRY_BACKOFF = 4            # linear back-off seed (seconds × attempt)

# Akamai-specific back-off for 403 / bot-challenge responses.  Mirrors the
# ``RATE_LIMIT_BACKOFF`` used by the Koton scraper but longer because the
# challenge pages usually need > 60 s to unblock.
RATE_LIMIT_BACKOFF = 90

# Empty-response back-off: when a page returns HTTP 200 but no product
# tiles (typical Akamai behavioural-challenge HTML), treat it as soft
# rate-limiting and sleep this many seconds before retrying.
EMPTY_RESPONSE_BACKOFF = 60

# Number of parallel category workers.  Keep low (1–2) – higher values
# get the whole IP flagged quickly.
DEFAULT_WORKERS = 1

# ── Output / Checkpoint Paths ────────────────────────────────────────────────
_SCRIPTS_DIR  = _Path(__file__).resolve().parent                       # …/Cosmetics/Sephora/scripts
_SEPHORA_DIR  = _SCRIPTS_DIR.parent                                    # …/Cosmetics/Sephora
_PROJECT_ROOT = _SEPHORA_DIR.parent.parent.parent.parent               # …/InflationResearchStudy

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
