"""
config.py — Bauhaus scraper configuration settings.

This module defines the constants, headers, paths, and delay settings used
by the Bauhaus scraper pipeline. It centralized all configuration so that
the scraper components (category_fetcher, product_fetcher, main) can reference
a single source of truth.
"""

import os

# --- Request Settings ---
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
}

BASE_URL = "https://www.bauhaus.com.tr"

REQUEST_DELAY = 2.0  # Base delay between requests
JITTER_MIN = 1.0     # Jitter multiplier min
JITTER_MAX = 2.0     # Jitter multiplier max
MAX_RETRIES = 5      # Retry attempts for failed requests
RETRY_BACKOFF = 3    # Exponential backoff seed

DEFAULT_WORKERS = 2  # Number of parallel workers

# --- Paths ---
# By default, save to InflationItems/Datas/ConstructionSuppliesMarkets/Datas/
# Compute absolute paths relative to this config file's location to be robust
SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPTS_DIR, "../../../../../"))

OUTPUT_DIR = os.path.join(PROJECT_ROOT, "InflationItems", "Datas", "ConstructionSuppliesMarkets", "Bauhaus")
CHECKPOINT_DIR = os.path.join(SCRIPTS_DIR, "..", "checkpoints")

# Ensure directories exist
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(CHECKPOINT_DIR, exist_ok=True)
