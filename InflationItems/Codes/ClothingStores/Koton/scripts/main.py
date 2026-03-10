"""
main.py — Koton Türkiye Product Scraper — CLI entry point & orchestrator
==========================================================================

This module is the top-level entry point for the scraper. It orchestrates
category discovery, parallel product fetching, incremental output writing,
checkpoint management, and a final deduplication pass.

Pipeline
--------
1. **Category discovery** — ``category_fetcher.fetch_categories()`` probes the
   Koton sitemap and extracts all category slugs.
2. **Checkpoint loading** — when ``--resume`` is passed, the today's checkpoint
   file is loaded and already-completed category slugs are skipped.
3. **Parallel scraping** — each remaining category is dispatched to a
   ``ThreadPoolExecutor`` worker. Every worker creates its own
   ``requests.Session`` so sessions are never shared across threads.
4. **Incremental saving** — product data and checkpoint state are written to
   disk immediately after each category completes. An interruption therefore
   loses at most one in-flight category.
5. **Deduplication** — a final pass removes any products whose internal ID
   was seen more than once across categories.

Usage examples
--------------
  # List all available categories
  python main.py --list-categories

  # Scrape a single category (by slug) and save as CSV
  python main.py --category kadin-giyim

  # Scrape all categories with 5 parallel workers
  python main.py --workers 5

  # Limit pages per category (useful for quick testing)
  python main.py --category kadin-giyim --limit 2

  # Resume an interrupted run (skips already-done categories)
  python main.py --resume
"""

import argparse
import json
import logging
import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
import requests
from tqdm import tqdm

import config
import sys
import os

# Add the new location of inflation.py to sys.path
_inflation_dir = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), 
    "..", "..", "..", "..", "..", "Inflations", "Codes", "ClothingStores", "Koton"
)
sys.path.append(os.path.abspath(_inflation_dir))
import inflation

from category_fetcher import fetch_categories
from product_fetcher import fetch_products_for_category

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── Thread-safety locks ──────────────────────────────────────────────────────
_csv_lock        = threading.Lock()
_checkpoint_lock = threading.Lock()
_counter_lock    = threading.Lock()


# ── Checkpoint helpers ───────────────────────────────────────────────────────

def _load_checkpoint() -> dict:
    if os.path.exists(config.CHECKPOINT_FILE):
        with open(config.CHECKPOINT_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"done": []}


def _save_checkpoint(checkpoint: dict) -> None:
    os.makedirs(config.CHECKPOINT_DIR, exist_ok=True)
    with _checkpoint_lock:
        with open(config.CHECKPOINT_FILE, "w", encoding="utf-8") as f:
            json.dump(checkpoint, f, ensure_ascii=False, indent=2)


# ── Output helpers ───────────────────────────────────────────────────────────

def _append_products(new_products: list[dict]) -> None:
    """Thread-safe append of new products to the CSV file."""
    if not new_products:
        return
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    df_new = pd.DataFrame(new_products)
    with _csv_lock:
        write_header = not os.path.exists(config.CSV_OUTPUT_FILE)
        df_new.to_csv(
            config.CSV_OUTPUT_FILE,
            mode="a",
            index=False,
            header=write_header,
            encoding="utf-8-sig",
        )


def _dedup_csv() -> int:
    """Remove duplicate rows by (pk, sku, name). Returns final row count."""
    if not os.path.exists(config.CSV_OUTPUT_FILE):
        return 0
    df = pd.read_csv(config.CSV_OUTPUT_FILE, encoding="utf-8-sig")
    before = len(df)
    dedup_cols = [c for c in ["pk", "sku", "name"] if c in df.columns]
    if dedup_cols:
        df.drop_duplicates(subset=dedup_cols, inplace=True)
    df.reset_index(drop=True, inplace=True)
    df.to_csv(config.CSV_OUTPUT_FILE, index=False, encoding="utf-8-sig")
    if len(df) < before:
        logger.info("Removed %d duplicate rows. Final count: %d", before - len(df), len(df))
    return len(df)


# ── Per-worker session factory ───────────────────────────────────────────────

def _make_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(config.DEFAULT_HEADERS)
    return session


# ── Worker function (runs in a thread) ──────────────────────────────────────

def _scrape_category(cat: dict, delay: float, page_limit: int) -> list[dict]:
    """Scrape one category in its own thread with its own Session."""
    session = _make_session()
    return fetch_products_for_category(
        category=cat,
        session=session,
        delay=delay,
        page_limit=page_limit,
    )


# ── Core scraping logic ──────────────────────────────────────────────────────

def run_scraper(args: argparse.Namespace) -> None:
    # 1. Fetch category list (single-threaded bootstrap)
    logger.info("Fetching category list…")
    bootstrap_session = _make_session()
    try:
        categories = fetch_categories(session=bootstrap_session)
    except Exception as exc:
        logger.error("Could not fetch categories: %s", exc)
        sys.exit(1)

    if not categories:
        logger.error("No categories found. Exiting.")
        sys.exit(1)

    # 2. Filter to a single category if requested
    if args.category:
        categories = [c for c in categories if c["slug"] == args.category]
        if not categories:
            logger.error(
                "Category slug '%s' not found. "
                "Use --list-categories to see available slugs.",
                args.category,
            )
            sys.exit(1)

    # 3. Load checkpoint for resume support
    checkpoint = _load_checkpoint() if args.resume else {"done": []}

    # 4. On a fresh run, clear old output file for today
    if not args.resume:
        if os.path.exists(config.CSV_OUTPUT_FILE):
            os.remove(config.CSV_OUTPUT_FILE)
            logger.info("Cleared old output file: %s", config.CSV_OUTPUT_FILE)

    categories_to_scrape = [
        c for c in categories if c["slug"] not in checkpoint["done"]
    ]

    if not categories_to_scrape:
        logger.info("All categories already scraped. Run without --resume to start fresh.")
        return

    total_products = 0

    # Count existing products when resuming
    if args.resume and os.path.exists(config.CSV_OUTPUT_FILE):
        try:
            existing_df = pd.read_csv(config.CSV_OUTPUT_FILE, encoding="utf-8-sig")
            total_products = len(existing_df)
            logger.info(
                "Resuming: %d existing products already saved.", total_products
            )
        except Exception as exc:
            logger.warning("Could not count existing products: %s", exc)

    logger.info(
        "Scraping %d categor%s with %d worker(s)…",
        len(categories_to_scrape),
        "y" if len(categories_to_scrape) == 1 else "ies",
        args.workers,
    )

    # 5. Parallel scraping with ThreadPoolExecutor
    futures = {}
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        for cat in categories_to_scrape:
            future = executor.submit(_scrape_category, cat, args.delay, args.limit)
            futures[future] = cat

        with tqdm(total=len(futures), unit="category", desc="Categories") as pbar:
            for future in as_completed(futures):
                cat = futures[future]
                pbar.set_postfix_str(cat["name"])
                try:
                    cat_products = future.result()
                except Exception as exc:
                    logger.error("Category '%s' failed: %s", cat["name"], exc)
                    cat_products = []

                # Save immediately after each category — no data lost on interruption
                if cat_products:
                    _append_products(cat_products)
                    with _counter_lock:
                        total_products += len(cat_products)

                # Mark category done in checkpoint
                with _checkpoint_lock:
                    checkpoint["done"].append(cat["slug"])
                _save_checkpoint(checkpoint)

                if cat_products:
                    logger.info(
                        "Category '%s': +%d products (total so far: %d)",
                        cat["name"], len(cat_products), total_products,
                    )

                pbar.update(1)

    # 6. Final deduplication pass
    logger.info("Running final deduplication…")
    final_count = _dedup_csv()
    logger.info("Done! ✓  Total unique products: %d", final_count)
    logger.info("Output → %s", config.CSV_OUTPUT_FILE)

    # 7. Calculate Inflation
    logger.info("Calculating inflation metrics...")
    inflation.calculate_inflation()



# ── CLI ──────────────────────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="koton-scraper",
        description="Scrape all product data from Koton Türkiye (koton.com).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--list-categories",
        action="store_true",
        help="Print all available categories and exit.",
    )
    parser.add_argument(
        "--category",
        metavar="SLUG",
        default=None,
        help="Scrape only this category slug (e.g. 'kadin-giyim'). Omit to scrape all.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        metavar="N",
        help="Number of parallel category workers (default: 1, increase carefully to avoid rate-limits).",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=config.REQUEST_DELAY,
        metavar="SECONDS",
        help=f"Delay between page requests per worker in seconds (default: {config.REQUEST_DELAY}).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        metavar="PAGES",
        help="Maximum pages to scrape per category (0 = unlimited, useful for testing).",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Skip categories already listed in the checkpoint file.",
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
        session = _make_session()
        try:
            categories = fetch_categories(session=session)
        except Exception as exc:
            logger.error(str(exc))
            sys.exit(1)

        print(f"\n{'Slug':<35} {'Name'}")
        print("-" * 60)
        for cat in categories:
            parent = f"  (sub of {cat['parent_slug']})" if cat.get("parent_slug") else ""
            print(f"{cat['slug']:<35} {cat['name']}{parent}")
        print(f"\nTotal: {len(categories)} categories")
        return

    run_scraper(args)


if __name__ == "__main__":
    main()
