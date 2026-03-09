"""
config.py — Single source of truth for Bershka Türkiye scraper configurations
=============================================================================

This module contains all constants, settings, and file paths used across
the scraper. It contains no execution logic, only declarations.

Bershka is part of the Inditex group (same as Pull&Bear, Zara, etc.)
and exposes the same itxrest REST API for catalog data.

Authentication
--------------
Bershka uses Akamai anti-bot protection which checks TLS fingerprints.
We use ``curl_cffi`` to impersonate Chrome's TLS stack, which bypasses
the protection without needing hardcoded cookies. A session warmup
(visiting the homepage first) collects the necessary Akamai cookies
automatically.
"""

# ── Inditex API IDs (Bershka Turkey) ─────────────────────────────────────────
STORE_ID = "44109521"
REGION_ID = "40259537"
LANGUAGE_ID = "-43"
APP_ID = "1"

# ── Base URLs ────────────────────────────────────────────────────────────────
BASE_URL = "https://www.bershka.com"
CATALOG_V2_URL = f"{BASE_URL}/itxrest/2/catalog/store/{STORE_ID}/{REGION_ID}"
CATALOG_V3_URL = f"{BASE_URL}/itxrest/3/catalog/store/{STORE_ID}/{REGION_ID}"

# ── Browser Impersonation ────────────────────────────────────────────────────
# curl_cffi impersonation target — matches a modern Chrome TLS fingerprint
# so that Akamai's bot detection allows the request through.
BROWSER_IMPERSONATE = "chrome"

# ── Request Headers ──────────────────────────────────────────────────────────
DEFAULT_HEADERS = {
    "Accept": "*/*",
    "Accept-Encoding": "gzip, deflate, br",
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
    "Connection": "keep-alive",
    "Content-Type": "application/json",
    "Referer": BASE_URL + "/tr/",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
}

# ── Scraping Parameters ──────────────────────────────────────────────────────
REQUEST_DELAY = 2          # Seconds between paginated requests
MAX_RETRIES = 5            # Max retries on a failed request before skipping
RETRY_BACKOFF = 3          # Retry backoff seed (actual wait = RETRY_BACKOFF × attempt)
RATE_LIMIT_BACKOFF = 60    # Extra sleep when 429 / 403 is received
BATCH_SIZE = 20            # Product IDs per batch request

# ── Output Settings ──────────────────────────────────────────────────────────
import datetime as _dt
from pathlib import Path as _Path

# Resolve paths relative to this config file so the scraper works regardless
# of the working directory from which main.py is invoked.
_SCRIPTS_DIR  = _Path(__file__).resolve().parent          # …/Codes/ClothingStores/Bershka/scripts
_BERSHKA_DIR  = _SCRIPTS_DIR.parent                       # …/Codes/ClothingStores/Bershka
_PROJECT_ROOT = _BERSHKA_DIR.parent.parent.parent         # …/InflationResearchStudy

# Base output directory
BASE_OUTPUT_DIR = str(_PROJECT_ROOT / "Datas" / "ClothingStores" / "Bershka")

# CSV / JSON output  →  Datas/ClothingStores/Bershka/ProductData/
OUTPUT_DIR      = str(_Path(BASE_OUTPUT_DIR) / "ProductData")
INFLATION_DIR   = str(_Path(BASE_OUTPUT_DIR) / "InflationData")

# Checkpoint files   →  Codes/ClothingStores/Bershka/checkpoints/
CHECKPOINT_DIR = str(_BERSHKA_DIR / "checkpoints")

# Files are named with today's date so each daily run produces its own set.
_TODAY = _dt.date.today().strftime("%Y-%m-%d")

CSV_OUTPUT_FILE  = str(_Path(OUTPUT_DIR)      / f"bershka_{_TODAY}.csv")
CHECKPOINT_FILE  = str(_Path(CHECKPOINT_DIR)  / f"bershka_checkpoint_{_TODAY}.json")
