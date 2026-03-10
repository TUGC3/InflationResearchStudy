"""
config.py — Single source of truth for Koton Türkiye scraper configurations
=============================================================================

This module contains all constants, settings, and file paths used across
the scraper. It contains no execution logic, only declarations.
"""

# ── Base URLs ────────────────────────────────────────────────────────────────
BASE_URL = "https://www.koton.com"

# ── User-Agent pool (rotated per worker session) ─────────────────────────────
# Using a variety of real browser UAs makes it much harder to fingerprint
# the scraper as a bot when multiple workers run concurrently.
USER_AGENTS = [
    # Chrome on macOS
    (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    # Chrome on Windows
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    ),
    # Firefox on Windows
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) "
        "Gecko/20100101 Firefox/124.0"
    ),
    # Firefox on Linux
    (
        "Mozilla/5.0 (X11; Linux x86_64; rv:123.0) "
        "Gecko/20100101 Firefox/123.0"
    ),
    # Safari on macOS
    (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) "
        "Version/17.4 Safari/605.1.15"
    ),
    # Edge on Windows
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36 Edg/123.0.0.0"
    ),
    # Chrome on Android
    (
        "Mozilla/5.0 (Linux; Android 14; Pixel 8) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.6312.80 Mobile Safari/537.36"
    ),
]

# ── Request Headers ──────────────────────────────────────────────────────────
# Base headers — User-Agent is injected per-session from USER_AGENTS pool.
DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Referer": BASE_URL + "/",
}

# ── Scraping Parameters ──────────────────────────────────────────────────────
# Seconds to wait between paginated requests to avoid rate limiting.
# Increase this if you keep seeing 429 / 403 errors.
REQUEST_DELAY = 2

# Maximum retries on a failed request before skipping
MAX_RETRIES = 5

# Retry backoff in seconds (multiplied by attempt number)
RETRY_BACKOFF = 3

# Extra sleep when a 429 or 403 "rate limited" response is received.
# The scraper will pause this many seconds before the next retry attempt.
RATE_LIMIT_BACKOFF = 60

# Category sitemap (lists all 2500+ category URLs)
CATEGORY_SITEMAP_URL = "https://s3.eu-central-1.amazonaws.com/f58f3a/sitemaps/sitemaps/sitemap-categories-1.xml.gz"

# ── Output Settings ──────────────────────────────────────────────────────────
import datetime as _dt
from pathlib import Path as _Path

# Resolve paths relative to this config file so the scraper works regardless
# of the working directory from which main.py is invoked.
_SCRIPTS_DIR  = _Path(__file__).resolve().parent          # …/Codes/ClothingStores/Koton/scripts
_KOTON_DIR    = _SCRIPTS_DIR.parent                       # …/Codes/ClothingStores/Koton
_PROJECT_ROOT = _KOTON_DIR.parent.parent.parent           # …/InflationResearchStudy

# Base output directory
BASE_OUTPUT_DIR = str(_PROJECT_ROOT / "Datas" / "ClothingStores" / "Koton")

# CSV / JSON output  →  InflationItems/Datas/ClothingStores/Koton/
OUTPUT_DIR      = str(_Path(BASE_OUTPUT_DIR))
INFLATION_DIR   = str(_Path(BASE_OUTPUT_DIR) / "InflationData")

# Checkpoint files   →  InflationItems/Codes/ClothingStores/Koton/checkpoints/
CHECKPOINT_DIR = str(_KOTON_DIR / "checkpoints")

# Files are named with today's date so each daily run produces its own set.
# Re-running on the same day with --resume picks up where it left off.
_TODAY = _dt.date.today().strftime("%Y-%m-%d")

CSV_OUTPUT_FILE  = str(_Path(OUTPUT_DIR)      / f"koton_{_TODAY}.csv")
CHECKPOINT_FILE  = str(_Path(CHECKPOINT_DIR)  / f"koton_checkpoint_{_TODAY}.json")
