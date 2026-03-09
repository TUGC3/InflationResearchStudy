"""
main.py — Bershka Türkiye Product Scraper — CLI entry point & orchestrator
==========================================================================

This module is the top-level entry point for the scraper. It orchestrates
category discovery, parallel product fetching, incremental output writing,
checkpoint management, and both live and final deduplication passes.

Pipeline
--------
1. **Category discovery** — ``category_fetcher.fetch_categories()`` queries the
   Inditex catalog API and extracts all leaf category IDs.
2. **Checkpoint loading** — when ``--resume`` is passed, today's checkpoint
   file is loaded and already-completed category IDs are skipped.
3. **Parallel scraping** — categories are partitioned across N worker threads.
   Each worker creates **one** ``curl_cffi.Session`` and reuses it for all
   its assigned categories (avoids per-category warmup overhead).
4. **Live deduplication** — a thread-safe global set tracks all product IDs
   seen so far. Duplicate products from overlapping categories are filtered
   out before writing, saving disk I/O and reducing final dedup work.
5. **Incremental saving** — product data and checkpoint state are written to
   disk immediately after each category completes.
6. **Final deduplication** — a safety-net pass removes any remaining dupes.
7. **Inflation** — calculates price changes vs historical data.

Usage examples
--------------
  # List all available categories
  python main.py --list-categories

  # Scrape a single category (by ID) and save as CSV
  python main.py --category 1010593678

  # Scrape all categories with 2 parallel workers
  python main.py --workers 2

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
from curl_cffi import requests
from tqdm import tqdm

import config
import inflation
from category_fetcher import fetch_categories
from product_fetcher import fetch_products_for_category

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── Thread-safety primitives ─────────────────────────────────────────────────
_csv_lock        = threading.Lock()
_checkpoint_lock = threading.Lock()
_counter_lock    = threading.Lock()
_seen_lock       = threading.Lock()

# Global set of product_ids already collected — used for live deduplication
# across categories processed by different workers.
_seen_product_ids: set[str] = set()


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


def _filter_new_products(products: list[dict]) -> list[dict]:
    """
    Filter out products whose product_id was already seen.

    This is the live deduplication step: it checks every incoming product
    against the global ``_seen_product_ids`` set and only returns genuinely
    new products. Thread-safe.
    """
    new_products = []
    with _seen_lock:
        for p in products:
            pid = p.get("product_id", "")
            if pid and pid not in _seen_product_ids:
                _seen_product_ids.add(pid)
                new_products.append(p)
    return new_products


def _dedup_csv() -> int:
    """Remove duplicate rows by product_id. Returns final row count."""
    if not os.path.exists(config.CSV_OUTPUT_FILE):
        return 0
    df = pd.read_csv(config.CSV_OUTPUT_FILE, encoding="utf-8-sig")
    before = len(df)
    if "product_id" in df.columns:
        df.drop_duplicates(subset=["product_id"], inplace=True)
    df.reset_index(drop=True, inplace=True)
    df.to_csv(config.CSV_OUTPUT_FILE, index=False, encoding="utf-8-sig")
    if len(df) < before:
        logger.info("Final dedup removed %d duplicate rows. Final count: %d", before - len(df), len(df))
    return len(df)


# ── Per-worker session factory ───────────────────────────────────────────────

def _make_session() -> requests.Session:
    """Create a new curl_cffi Session with Chrome impersonation and cookie warmup."""
    session = requests.Session(impersonate=config.BROWSER_IMPERSONATE)
    session.headers.update(config.DEFAULT_HEADERS)
    # Warmup: visit homepage to get Akamai cookies
    try:
        session.get(f"{config.BASE_URL}/tr/", timeout=20)
        logger.debug("Session warmup successful.")
    except Exception as exc:
        logger.warning("Session warmup failed: %s", exc)
    return session


# ── Worker function (runs in a thread) ──────────────────────────────────────

def _worker_scrape_chunk(
    chunk: list[dict],
    delay: float,
    checkpoint: dict,
    pbar: tqdm,
    counter: list,  # mutable list holding [total_products]
) -> None:
    """
    Scrape a chunk of categories on a single thread with one reusable session.

    This avoids creating a new session (and hitting the homepage) for every
    single category, which was causing "Failed to connect" errors from
    Bershka's connection throttling.
    """
    session = _make_session()

    for cat in chunk:
        try:
            cat_products = fetch_products_for_category(
                category=cat,
                session=session,
                delay=delay,
            )
        except Exception as exc:
            logger.error("Category '%s' failed: %s", cat["name"], exc)
            cat_products = []

        # Live dedup: filter out products already seen from other categories
        unique_products = _filter_new_products(cat_products)
        skipped = len(cat_products) - len(unique_products)

        # Save immediately after each category
        if unique_products:
            _append_products(unique_products)
            with _counter_lock:
                counter[0] += len(unique_products)

        # Mark category done in checkpoint
        with _checkpoint_lock:
            checkpoint["done"].append(cat["id"])
        _save_checkpoint(checkpoint)

        pbar.set_postfix_str(cat["name"])
        pbar.update(1)

        if unique_products:
            skip_msg = f" ({skipped} dupes skipped)" if skipped else ""
            logger.info(
                "Category '%s': +%d new products%s (total unique so far: %d)",
                cat["name"], len(unique_products), skip_msg, counter[0],
            )
        elif cat_products:
            logger.debug(
                "Category '%s': all %d products were duplicates.",
                cat["name"], len(cat_products),
            )


# ── Core scraping logic ──────────────────────────────────────────────────────

def run_scraper(args: argparse.Namespace) -> None:
    global _seen_product_ids

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
        categories = [c for c in categories if c["id"] == args.category]
        if not categories:
            logger.error(
                "Category ID '%s' not found. "
                "Use --list-categories to see available IDs.",
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
        _seen_product_ids = set()
    else:
        # When resuming, pre-load seen product IDs from existing CSV
        _seen_product_ids = set()
        if os.path.exists(config.CSV_OUTPUT_FILE):
            try:
                existing_df = pd.read_csv(config.CSV_OUTPUT_FILE, encoding="utf-8-sig")
                if "product_id" in existing_df.columns:
                    _seen_product_ids = set(existing_df["product_id"].astype(str).tolist())
                logger.info(
                    "Resuming: %d existing products loaded into dedup set.",
                    len(_seen_product_ids),
                )
            except Exception as exc:
                logger.warning("Could not load existing products for dedup: %s", exc)

    categories_to_scrape = [
        c for c in categories if c["id"] not in checkpoint["done"]
    ]

    if not categories_to_scrape:
        logger.info("All categories already scraped. Run without --resume to start fresh.")
        return

    total_products = len(_seen_product_ids)
    # Use a mutable list so worker threads can update it
    counter = [total_products]

    n_workers = min(args.workers, len(categories_to_scrape))
    logger.info(
        "Scraping %d categor%s with %d worker(s)…",
        len(categories_to_scrape),
        "y" if len(categories_to_scrape) == 1 else "ies",
        n_workers,
    )

    # 5. Partition categories into chunks (one per worker) for session reuse
    chunks = [[] for _ in range(n_workers)]
    for i, cat in enumerate(categories_to_scrape):
        chunks[i % n_workers].append(cat)

    with tqdm(total=len(categories_to_scrape), unit="category", desc="Categories") as pbar:
        with ThreadPoolExecutor(max_workers=n_workers) as executor:
            futures = []
            for chunk in chunks:
                future = executor.submit(
                    _worker_scrape_chunk, chunk, args.delay, checkpoint, pbar, counter
                )
                futures.append(future)

            # Wait for all workers and propagate exceptions
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as exc:
                    logger.error("Worker failed: %s", exc)

    # 6. Final deduplication pass (safety net — live dedup should catch most)
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
        prog="bershka-scraper",
        description="Scrape all product data from Bershka Türkiye (bershka.com/tr/).",
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
        metavar="ID",
        default=None,
        help="Scrape only this category ID. Omit to scrape all.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        metavar="N",
        help="Number of parallel category workers (default: 1).",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=config.REQUEST_DELAY,
        metavar="SECONDS",
        help=f"Delay between requests per worker (default: {config.REQUEST_DELAY}s).",
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

        print(f"\n{'ID':<15} {'Name':<35} {'Parent'}")
        print("-" * 70)
        for cat in categories:
            parent = cat.get("parent_name") or ""
            print(f"{cat['id']:<15} {cat['name']:<35} {parent}")
        print(f"\nTotal: {len(categories)} categories")
        return

    run_scraper(args)


if __name__ == "__main__":
    main()
