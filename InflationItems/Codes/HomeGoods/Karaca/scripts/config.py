"""Configuration for the Karaca scraper."""

from __future__ import annotations

import datetime as _dt
from pathlib import Path as _Path

BASE_URL = "https://www.karaca.com"
HOME_URL = f"{BASE_URL}/"

DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Referer": HOME_URL,
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
}

REQUEST_DELAY = 0.35
MAX_RETRIES = 3
RETRY_BACKOFF = 2

PROMOTIONAL_MAIN_CATEGORIES = {
    "Hediye",
    "Anneler Günü",
    "Çeyiz Seti",
    "Çok Satan",
    "Markalar",
    "Kampanyalar",
}

NON_LISTING_PATHS = {
    "/gift-card",
    "/marka",
    "/perde",
}

MAIN_CATEGORY_PRIORITY = {
    "Sofra": 10,
    "Mutfak": 20,
    "Küçük Ev Aletleri": 30,
    "Ev ve Yaşam": 40,
    "Hobi Eğlence": 50,
    "Hediye": 60,
    "Anneler Günü": 70,
    "Çeyiz Seti": 80,
    "Çok Satan": 90,
    "Markalar": 100,
    "Kampanyalar": 110,
}

CSV_FIELDNAMES = [
    "Product Name",
    "Product Cost",
    "Product Original Cost",
    "Discount Amount",
    "Discount Rate",
    "Currency",
    "Product ID",
    "Stock Quantity",
    "In Stock",
    "Main Category",
    "Top Category",
    "Category ID",
    "Category Path",
    "Source Category",
    "Source Category URL",
    "Product URL",
    "Image URL",
    "Color",
    "Size",
]

_SCRIPTS_DIR = _Path(__file__).resolve().parent
_SCRAPER_DIR = _SCRIPTS_DIR.parent
_PROJECT_ROOT = _SCRAPER_DIR.parents[3]

OUTPUT_DIR = _PROJECT_ROOT / "InflationItems" / "Datas" / "HomeGoods" / "Karaca"
CHECKPOINT_DIR = _SCRAPER_DIR / "checkpoints"

_TODAY = _dt.date.today().strftime("%Y-%m-%d")

CSV_OUTPUT_FILE = OUTPUT_DIR / f"karaca_{_TODAY}.csv"
CHECKPOINT_FILE = CHECKPOINT_DIR / f"karaca_checkpoint_{_TODAY}.json"
