"""
Vivense Scraper Configuration Module
====================================

Central configuration for the Vivense (vivense.com) product scraping system.
Vivense is a Turkish online furniture / home-goods retailer.  The site does
NOT expose a public REST/GraphQL API for product listings — every product
card is server-rendered into the category HTML with all attributes embedded
as ``data-*`` properties.  We therefore scrape the HTML directly using
``requests`` + ``BeautifulSoup`` (same pattern as the Bauhaus scraper).

Sections
--------
- Base URL & request headers
- Curated top-level category list (Vivense's main navigation entries)
- Performance parameters (delays, retries, workers, jitter)
- Path resolution for daily CSV / checkpoint files

Pagination
----------
Vivense uses simple URL pagination via the ``?page=N`` query parameter.
A request returning zero product cards signals the end of the catalogue
for that category.  Each page returns up to 60 products.

Paths
-----
All paths are resolved relative to this config file so the scraper works
regardless of the working directory from which ``main.py`` is invoked.

- CSV output  → ``InflationItems/Datas/HomeGoods/Vivense/vivense_YYYY-MM-DD.csv``
- Checkpoints → ``InflationItems/Codes/HomeGoods/Vivense/checkpoints/vivense_checkpoint_YYYY-MM-DD.json``
"""

import datetime as _dt
from pathlib import Path as _Path

# ── Base URLs ────────────────────────────────────────────────────────────────
BASE_URL = "https://www.vivense.com"

# ── Request Headers ──────────────────────────────────────────────────────────
# Realistic browser headers.  Vivense returns full HTML for any standard UA;
# no special tokens or cookies are required.
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Referer": BASE_URL + "/",
}

# ── Top-Level Categories ─────────────────────────────────────────────────────
# Curated list of Vivense's main navigation buckets.  Each entry maps
# directly to the canonical ``.html`` slug used by the public site.
#
# Brand / promo buckets such as ``vivense-collection`` and
# ``home-cosmetics`` are deliberately excluded — they are cross-cuts of
# the catalogue and would only duplicate products.
TOP_LEVEL_CATEGORIES = [
    {"id": "oturma-odasi-mobilyalari",     "name": "Oturma Odası",
     "url": f"{BASE_URL}/oturma-odasi-mobilyalari.html"},
    {"id": "yatak-odasi",                  "name": "Yatak Odası",
     "url": f"{BASE_URL}/yatak-odasi.html"},
    {"id": "yemek-odasi-mutfak",           "name": "Yemek Odası ve Mutfak",
     "url": f"{BASE_URL}/yemek-odasi-mutfak.html"},
    {"id": "bebek-cocuk-genc-odasi-takimi","name": "Bebek, Çocuk ve Genç Odası",
     "url": f"{BASE_URL}/bebek-cocuk-genc-odasi-takimi.html"},
    {"id": "calisma-odasi",                "name": "Çalışma Odası",
     "url": f"{BASE_URL}/calisma-odasi.html"},
    {"id": "bahce-mobilyalari",            "name": "Bahçe Mobilyaları",
     "url": f"{BASE_URL}/bahce-mobilyalari.html"},
    {"id": "aydinlatma-modelleri",         "name": "Aydınlatma",
     "url": f"{BASE_URL}/aydinlatma-modelleri.html"},
    {"id": "hali-modelleri",               "name": "Halı",
     "url": f"{BASE_URL}/hali-modelleri.html"},
    {"id": "ev-tekstili",                  "name": "Ev Tekstili",
     "url": f"{BASE_URL}/ev-tekstili.html"},
    {"id": "ev-dekorasyonu",               "name": "Ev Dekorasyonu",
     "url": f"{BASE_URL}/ev-dekorasyonu.html"},
    {"id": "banyo",                        "name": "Banyo",
     "url": f"{BASE_URL}/banyo.html"},
    {"id": "antre-dekorasyonu",            "name": "Antre Dekorasyonu",
     "url": f"{BASE_URL}/antre-dekorasyonu.html"},
    {"id": "sofra",                        "name": "Sofra",
     "url": f"{BASE_URL}/sofra.html"},
    {"id": "uyku-grubu-1764057275",        "name": "Uyku Grubu",
     "url": f"{BASE_URL}/uyku-grubu-1764057275.html"},
    {"id": "yapi-market",                  "name": "Yapı Market",
     "url": f"{BASE_URL}/yapi-market.html"},
]

# ── Scraping Parameters ──────────────────────────────────────────────────────
# Seconds to wait between paginated requests (jitter applied).
REQUEST_DELAY = 1.0

# Maximum retries on a failed request before skipping.
MAX_RETRIES = 4

# Retry backoff seed in seconds (actual wait = seed × attempt).
RETRY_BACKOFF = 3

# Number of parallel category workers.
DEFAULT_WORKERS = 3

# Jitter multiplier range applied to REQUEST_DELAY (uniform random).
JITTER_MIN = 0.7
JITTER_MAX = 1.5

# Hard upper bound on pages per category — defensive guard against runaway
# scraping if Vivense ever returns a non-empty page indefinitely.  No real
# Vivense category currently exceeds 60 pages.
PAGE_HARD_LIMIT = 200

# ── Path resolution ──────────────────────────────────────────────────────────
# Paths are resolved relative to this config file so the scraper works
# regardless of the working directory from which main.py is invoked.
_SCRIPTS_DIR  = _Path(__file__).resolve().parent              # …/HomeGoods/Vivense/scripts
_VIVENSE_DIR  = _SCRIPTS_DIR.parent                           # …/HomeGoods/Vivense
_PROJECT_ROOT = _VIVENSE_DIR.parent.parent.parent.parent      # …/InflationResearchStudy

# CSV output → InflationItems/Datas/HomeGoods/Vivense/
BASE_OUTPUT_DIR = str(_PROJECT_ROOT / "InflationItems" / "Datas" / "HomeGoods" / "Vivense")
OUTPUT_DIR      = BASE_OUTPUT_DIR

# Checkpoints → InflationItems/Codes/HomeGoods/Vivense/checkpoints/
CHECKPOINT_DIR  = str(_VIVENSE_DIR / "checkpoints")

# Daily-dated file names so each run produces its own set and --resume picks
# up where it left off.
_TODAY = _dt.date.today().strftime("%Y-%m-%d")

CSV_OUTPUT_FILE = str(_Path(OUTPUT_DIR)     / f"vivense_{_TODAY}.csv")
CHECKPOINT_FILE = str(_Path(CHECKPOINT_DIR) / f"vivense_checkpoint_{_TODAY}.json")
