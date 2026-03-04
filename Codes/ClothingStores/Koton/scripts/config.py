"""
Configuration settings for the Koton Türkiye product scraper.
"""

# ── Base URLs ────────────────────────────────────────────────────────────────
BASE_URL = "https://www.koton.com"

# ── Request Headers ──────────────────────────────────────────────────────────
# Standard browser headers to avoid blocks.
DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Referer": BASE_URL + "/",
}

# ── Scraping Parameters ──────────────────────────────────────────────────────
# Seconds to wait between paginated requests to avoid rate limiting
REQUEST_DELAY = 1

# Maximum retries on a failed request before skipping
MAX_RETRIES = 3

# Retry backoff in seconds (doubles each retry)
RETRY_BACKOFF = 2

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

# CSV / JSON output  →  Datas/ClothingStores/Koton/
OUTPUT_DIR    = str(_PROJECT_ROOT / "Datas" / "ClothingStores" / "Koton")

# Checkpoint files   →  Codes/ClothingStores/Koton/checkpoints/
CHECKPOINT_DIR = str(_KOTON_DIR / "checkpoints")

# Files are named with today's date so each daily run produces its own set.
# Re-running on the same day with --resume picks up where it left off.
_TODAY = _dt.date.today().strftime("%Y-%m-%d")

CSV_OUTPUT_FILE  = str(_Path(OUTPUT_DIR)      / f"koton_{_TODAY}.csv")
CHECKPOINT_FILE  = str(_Path(CHECKPOINT_DIR)  / f"koton_checkpoint_{_TODAY}.json")
