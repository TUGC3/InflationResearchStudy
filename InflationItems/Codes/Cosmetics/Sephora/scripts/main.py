"""
Sephora Türkiye Product Scraper — Main Entry Point and Orchestration Layer
==========================================================================

CLI orchestrator for the Sephora Türkiye product scraper.  Mirrors the
shape of the Koton / Migros / Bauhaus / IstanbulAvrupa scrapers so the
whole project has a consistent interface.

Backend
-------
Sephora sits behind **Akamai Bot Manager**, which blocks naive HTTP
traffic via TLS / JA3 fingerprinting and server-side JS challenges.
The scraper drives a real Chrome browser through
``undetected-chromedriver`` so Akamai's JS challenge runs naturally
(identical approach to the IstanbulAvrupa / Sahibinden scraper in this
repo).  A single Chrome instance is reused across categories so the
Akamai ``_abck`` cookie is preserved — the expensive CAPTCHA (if any)
is solved at most once per day.

Pipeline
--------
1. Download ``sitemap-customsitemap_category_0.xml`` and filter to the
   eight top-level category URLs (see ``config.MAIN_CATEGORY_SLUGS``).
2. Optionally filter to a single category via ``--category SLUG``.
3. Load (or reset) today's checkpoint.
4. Walk the categories sequentially with the shared Chrome driver,
   appending each category's products to the daily CSV and updating
   the checkpoint as they complete.
5. Deduplicate the CSV by ``id`` and invoke the matching inflation
   calculator located under
   ``Inflations/Codes/Cosmetics/Sephora/inflation.py``.

Usage Examples
--------------
```bash
# List every category the scraper can reach
python main.py --list-categories

# Full catalog scrape
python main.py

# Only skincare, 2-page smoke test
python main.py --category cilt-bakimi-c303 --limit 2

# Resume an interrupted run
python main.py --resume

# Headless Chrome (Akamai detects this more easily)
python main.py --headless
```
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time

import pandas as pd
from tqdm import tqdm

import config

# Make the matching inflation.py importable (sits outside InflationItems/).
_INFLATION_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "..", "..", "..", "..",
    "Inflations", "Codes", "Cosmetics", "Sephora",
)
sys.path.append(os.path.abspath(_INFLATION_DIR))
import inflation  # noqa: E402

from category_fetcher import fetch_categories  # noqa: E402
from browser_fetcher import (  # noqa: E402
    close_driver,
    fetch_products_for_category_browser,
    setup_driver,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ── Checkpoint helpers ───────────────────────────────────────────────────────


def _load_checkpoint() -> dict:
    """Load today's checkpoint or an empty skeleton when it doesn't exist."""
    if os.path.exists(config.CHECKPOINT_FILE):
        with open(config.CHECKPOINT_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"done": []}


def _save_checkpoint(checkpoint: dict) -> None:
    """Persist ``checkpoint`` atomically."""
    os.makedirs(config.CHECKPOINT_DIR, exist_ok=True)
    with open(config.CHECKPOINT_FILE, "w", encoding="utf-8") as f:
        json.dump(checkpoint, f, ensure_ascii=False, indent=2)


# ── Output helpers ───────────────────────────────────────────────────────────


def _append_products(new_products: list[dict]) -> None:
    """Append ``new_products`` to the daily CSV (write header only once)."""
    if not new_products:
        return
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    df_new = pd.DataFrame(new_products)
    write_header = not os.path.exists(config.CSV_OUTPUT_FILE)
    df_new.to_csv(
        config.CSV_OUTPUT_FILE,
        mode="a",
        index=False,
        header=write_header,
        encoding="utf-8-sig",
    )


def _dedup_csv() -> int:
    """Drop duplicate rows by ``id`` and return the post-dedup count."""
    if not os.path.exists(config.CSV_OUTPUT_FILE):
        return 0
    df = pd.read_csv(config.CSV_OUTPUT_FILE, encoding="utf-8-sig")
    before = len(df)
    if "id" in df.columns:
        df.drop_duplicates(subset=["id"], inplace=True)
    df.reset_index(drop=True, inplace=True)
    df.to_csv(config.CSV_OUTPUT_FILE, index=False, encoding="utf-8-sig")
    if len(df) < before:
        logger.info("Removed %d duplicate rows. Final count: %d", before - len(df), len(df))
    return len(df)


# ── Core scraping logic ──────────────────────────────────────────────────────


def _persist_category(
    cat: dict,
    cat_products: list[dict],
    checkpoint: dict,
    total_products: int,
) -> int:
    """Append products to CSV, update checkpoint, log progress.

    Returns the updated ``total_products`` counter.
    """
    if cat_products:
        _append_products(cat_products)
        total_products += len(cat_products)

    checkpoint["done"].append(cat["slug"])
    _save_checkpoint(checkpoint)

    if cat_products:
        logger.info(
            "✓  Category '%s': +%d products (total: %d)",
            cat["name"], len(cat_products), total_products,
        )
        logger.info("💾 Checkpoint saved")
    return total_products


def run_scraper(args: argparse.Namespace) -> None:
    """Execute the end-to-end scraping pipeline."""
    logger.info("▶  Fetching category list from sitemap...")
    try:
        level = "all" if args.all_categories else "main"
        categories = fetch_categories(level=level)
    except Exception as exc:  # noqa: BLE001
        logger.error("✗  Could not fetch categories: %s", exc)
        sys.exit(1)

    if not categories:
        logger.error("✗  No categories returned by sitemap. Exiting.")
        sys.exit(1)

    if args.category:
        categories = [c for c in categories if c["slug"] == args.category]
        if not categories:
            logger.error(
                "✗  Category '%s' not found. Use --list-categories to see available slugs.",
                args.category,
            )
            sys.exit(1)

    checkpoint = _load_checkpoint() if args.resume else {"done": []}

    if not args.resume and os.path.exists(config.CSV_OUTPUT_FILE):
        os.remove(config.CSV_OUTPUT_FILE)
        logger.info("🗑  Cleared old CSV: %s", config.CSV_OUTPUT_FILE)

    categories_to_scrape = [c for c in categories if c["slug"] not in checkpoint["done"]]

    if not categories_to_scrape:
        logger.info("✓  All categories already scraped. Run without --resume to start fresh.")
        return

    total_products = 0
    if args.resume and os.path.exists(config.CSV_OUTPUT_FILE):
        try:
            existing_df = pd.read_csv(config.CSV_OUTPUT_FILE, encoding="utf-8-sig")
            total_products = len(existing_df)
            logger.info("↩  Resuming: %d existing products already saved.", total_products)
        except Exception as exc:  # noqa: BLE001
            logger.warning("⚠  Could not count existing products: %s", exc)

    logger.info(
        "▶  Scraping %d categor%s with Chrome…",
        len(categories_to_scrape),
        "y" if len(categories_to_scrape) == 1 else "ies",
    )

    start_time = time.time()

    driver = None
    try:
        driver = setup_driver(headless=args.headless)
        # Warm up: visit the homepage so Akamai can run its challenge
        # once before we start paginating deeply into categories.
        try:
            driver.get(config.BASE_URL + "/")
            time.sleep(2.0)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Homepage warm-up failed: %s", exc)

        with tqdm(total=len(categories_to_scrape), unit="category", desc="Categories") as pbar:
            for cat in categories_to_scrape:
                pbar.set_postfix_str(cat["name"])
                try:
                    cat_products = fetch_products_for_category_browser(
                        category=cat,
                        driver=driver,
                        delay=args.delay,
                        page_limit=args.limit,
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.error("✗  Category '%s' failed: %s", cat["name"], exc)
                    cat_products = []

                total_products = _persist_category(
                    cat=cat,
                    cat_products=cat_products,
                    checkpoint=checkpoint,
                    total_products=total_products,
                )
                pbar.update(1)
    finally:
        close_driver(driver)

    elapsed = time.time() - start_time
    logger.info("⏱  Scraping completed in %.1fs (%.1f min)", elapsed, elapsed / 60)

    logger.info("🔄 Running final deduplication...")
    final_count = _dedup_csv()
    logger.info("Done! ✓  Total unique products: %d", final_count)
    logger.info("Output → %s", config.CSV_OUTPUT_FILE)

    logger.info("📈 Calculating inflation metrics...")
    try:
        inflation.calculate_inflation()
        logger.info("✅ Inflation calculation complete")
    except Exception as exc:  # noqa: BLE001
        logger.error("✗  Failed to calculate inflation: %s", exc)


# ── CLI ──────────────────────────────────────────────────────────────────────


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sephora-scraper",
        description="Scrape product data from Sephora Türkiye (sephora.com.tr).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    # Category discovery / filtering
    parser.add_argument(
        "--list-categories",
        action="store_true",
        help="Print every category the scraper can reach and exit.",
    )
    parser.add_argument(
        "--all-categories",
        action="store_true",
        help=(
            "Include every category URL from the sitemap instead of the eight "
            "top-level ones.  Rarely useful – the default already covers the "
            "full catalogue with fewer duplicate products."
        ),
    )
    parser.add_argument(
        "--category",
        metavar="SLUG",
        default=None,
        help="Scrape only this category slug (e.g. 'cilt-bakimi-c303').",
    )

    # Browser controls
    parser.add_argument(
        "--headless",
        action="store_true",
        default=config.BROWSER_HEADLESS,
        help=(
            "Run Chrome in headless mode.  Akamai detects headless Chrome "
            "more easily, so leaving this off is recommended unless you "
            "are running on a server."
        ),
    )

    # Scraping knobs
    parser.add_argument(
        "--delay",
        type=float,
        default=config.BROWSER_PAGE_LOAD_DELAY,
        metavar="SECONDS",
        help=(
            f"Base delay between category page loads "
            f"(default: {config.BROWSER_PAGE_LOAD_DELAY})."
        ),
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        metavar="PAGES",
        help="Maximum pages to scrape per category (0 = unlimited).",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Skip categories already listed in today's checkpoint file.",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable debug-level logging.",
    )
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if args.list_categories:
        level = "all" if args.all_categories else "main"
        try:
            categories = fetch_categories(level=level)
        except Exception as exc:  # noqa: BLE001
            logger.error(str(exc))
            sys.exit(1)

        print(f"\n{'Slug':<52} Name")
        print("-" * 80)
        for cat in categories:
            print(f"{cat['slug']:<52} {cat['name']}")
        print(f"\nTotal: {len(categories)} categories")
        return

    run_scraper(args)


if __name__ == "__main__":
    main()
