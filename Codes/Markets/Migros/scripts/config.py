"""
Configuration settings for the Migros Türkiye product scraper.
"""

# ── Base URLs ────────────────────────────────────────────────────────────────
BASE_URL = "https://www.migros.com.tr"

# REST product search API endpoint
PRODUCT_SEARCH_URL = f"{BASE_URL}/rest/products/search"

# Category sitemap (lists all category URLs)
CATEGORY_SITEMAP_URL = f"{BASE_URL}/hermes/api/sitemaps/sitemap-categories-1.xml"

# ── Request Headers ──────────────────────────────────────────────────────────
# These headers are required to avoid 403 Forbidden responses from the API.
DEFAULT_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "tr-TR,tr;q=0.9",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "X-Device-PWA": "true",
    "X-FORWARDED-REST": "true",
    "X-PWA": "true",
    "Referer": BASE_URL + "/",
    "Origin": BASE_URL,
}

# ── Scraping Parameters ──────────────────────────────────────────────────────
# Seconds to wait between paginated requests to avoid rate limiting
REQUEST_DELAY = 0.5

# Maximum retries on a failed request before skipping
MAX_RETRIES = 3

# Retry backoff in seconds (doubles each retry)
RETRY_BACKOFF = 2

# Default sort order (onerilenler = recommended)
DEFAULT_SORT = "onerilenler"

# Number of parallel category workers
DEFAULT_WORKERS = 3

# Jitter multiplier range applied to REQUEST_DELAY (uniform random between these)
JITTER_MIN = 0.5
JITTER_MAX = 1.5

# ── Output Settings ──────────────────────────────────────────────────────────
import datetime as _dt
from pathlib import Path as _Path

# Resolve paths relative to this config file so the scraper works regardless
# of the working directory from which main.py is invoked.
_SCRIPTS_DIR    = _Path(__file__).resolve().parent          # …/Codes/Markets/Migros/scripts
_MIGROS_DIR     = _SCRIPTS_DIR.parent                       # …/Codes/Markets/Migros
_PROJECT_ROOT   = _MIGROS_DIR.parent.parent.parent          # …/InflationResearchStudy

# CSV / JSON output  →  Datas/Markets/Migros/
OUTPUT_DIR      = str(_PROJECT_ROOT / "Datas" / "Markets" / "Migros")

# Checkpoint files   →  Codes/Markets/Migros/checkpoints/
CHECKPOINT_DIR  = str(_MIGROS_DIR / "checkpoints")

# Files are named with today's date so each daily run produces its own set.
# Re-running on the same day with --resume picks up where it left off.
_TODAY = _dt.date.today().strftime("%Y-%m-%d")

CSV_OUTPUT_FILE  = str(_Path(OUTPUT_DIR)     / f"migros_{_TODAY}.csv")
JSON_OUTPUT_FILE = str(_Path(OUTPUT_DIR)     / f"migros_{_TODAY}.json")
CHECKPOINT_FILE  = str(_Path(CHECKPOINT_DIR) / f"migros_checkpoint_{_TODAY}.json")

