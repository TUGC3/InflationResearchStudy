"""
config.py — Nalburadam scraper configuration settings.

This module defines the constants, headers, paths, and delay settings used
by the Nalburadam scraper pipeline.
"""

import os

# --- Request Settings ---
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
}

BASE_URL = "https://www.nalburadam.com"

REQUEST_DELAY = 1.2  # Base delay between requests (mean)
JITTER_MIN = 1.0     # Jitter multiplier min
JITTER_MAX = 2.0     # Jitter multiplier max
MAX_RETRIES = 5      # Retry attempts for failed requests
RETRY_BACKOFF = 3    # Exponential backoff seed

DEFAULT_WORKERS = 4  # Number of parallel workers

# --- Paths ---
SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPTS_DIR, "../../../../../"))

OUTPUT_DIR = os.path.join(PROJECT_ROOT, "InflationItems", "Datas", "ConstructionSuppliesMarkets", "Nalburadam")
CHECKPOINT_DIR = os.path.join(SCRIPTS_DIR, "..", "checkpoints")

# Ensure directories exist
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(CHECKPOINT_DIR, exist_ok=True)
