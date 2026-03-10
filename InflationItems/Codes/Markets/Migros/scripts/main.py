"""
main.py — Migros Türkiye Product Scraper — CLI entry point & orchestrator
==========================================================================

This module is the top-level entry point for the scraper.  It orchestrates
category discovery, parallel product fetching, incremental output writing,
checkpoint management, and a final deduplication pass.

Pipeline
--------
1. **Category discovery** — ``category_fetcher.fetch_categories()`` probes the
   Migros REST API and returns all scrapable (sub)categories.
2. **Checkpoint loading** — when ``--resume`` is passed, the today's checkpoint
   file is loaded and already-completed category IDs are skipped.
3. **Parallel scraping** — each remaining category is dispatched to a
   ``ThreadPoolExecutor`` worker.  Every worker creates its own
   ``requests.Session`` so sessions are never shared across threads.
4. **Incremental saving** — product data and checkpoint state are written to
   disk immediately after each category completes.  An interruption therefore
   loses at most one in-flight category.
5. **Deduplication** — a final pass removes any products whose ``id`` was seen
   more than once across categories (can happen for multi-category items).

Output files
------------
All paths are configured in ``config.py`` and are derived relative to that
file, so the scraper works correctly regardless of the CWD.

    InflationItems/Datas/Markets/Migros/migros_<DATE>.csv    — UTF-8-with-BOM CSV
    InflationItems/Datas/Markets/Migros/migros_<DATE>.json   — pretty-printed JSON array
    InflationItems/Codes/Markets/Migros/checkpoints/migros_checkpoint_<DATE>.json

Usage examples
--------------
  # List all available categories
  python main.py --list-categories

  # Scrape a single category (by ID) and save as CSV
  python main.py --category 2 --output csv

  # Scrape all categories with 3 parallel workers
  python main.py --output both --workers 3

  # Scrape all categories, save both CSV and JSON, with a 1-second delay
  python main.py --output both --delay 1.0

  # Limit pages per category (useful for quick testing)
  python main.py --category 2 --output both --limit 2

  # Resume an interrupted run (skips already-done categories)
  python main.py --output csv --resume

  # Enable verbose / debug-level logging
  python main.py --output csv -v
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

import sys
import config

# Add the new location of inflation.py to sys.path
_inflation_dir = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), 
    "..", "..", "..", "..", "..", "Inflations", "Codes", "Markets", "Migros"
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
    """Load today's checkpoint file from disk.

    Returns
    -------
    dict
        Parsed checkpoint dict.  Schema: ``{"done": [<category_id>, ...]}``. 
        Returns ``{"done": []}`` when the checkpoint file does not yet exist.
    """
    if os.path.exists(config.CHECKPOINT_FILE):
        with open(config.CHECKPOINT_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"done": []}


def _save_checkpoint(checkpoint: dict) -> None:
    """Write ``checkpoint`` to ``config.CHECKPOINT_FILE`` atomically under a lock.

    Creates ``config.CHECKPOINT_DIR`` if it does not already exist.  The write
    is protected by ``_checkpoint_lock`` so concurrent worker threads cannot
    corrupt the file.

    Args
    ----
    checkpoint : dict
        Checkpoint dict to serialise.  Expected schema:
        ``{"done": [<category_id>, ...]}``.
    """
    os.makedirs(config.CHECKPOINT_DIR, exist_ok=True)
    with _checkpoint_lock:
        with open(config.CHECKPOINT_FILE, "w", encoding="utf-8") as f:
            json.dump(checkpoint, f, ensure_ascii=False, indent=2)


# ── Output helpers ───────────────────────────────────────────────────────────

def _append_products(new_products: list[dict], output_format: str) -> None:
    """Thread-safely append ``new_products`` to the daily output files.

    Called immediately after each category is scraped so that data is
    persisted to disk even if the process is interrupted mid-run.

    - **CSV**: rows are appended with a header written only for the first
      batch (``mode="a"``).  Uses UTF-8-with-BOM encoding for wide Excel
      compatibility.
    - **JSON**: the entire file is rewritten on every call to maintain a
      valid JSON array.  Existing entries are preserved.

    Writing is serialised via ``_csv_lock`` so concurrent worker threads
    never interleave their writes.

    Args
    ----
    new_products : list[dict]
        Products scraped from a single category (as returned by
        ``fetch_products_for_category``).  A no-op when the list is empty.
    output_format : str
        One of ``"csv"``, ``"json"``, or ``"both"``.
    """
    if not new_products:
        return

    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    df_new = pd.DataFrame(new_products)

    with _csv_lock:
        if output_format in ("csv", "both"):
            write_header = not os.path.exists(config.CSV_OUTPUT_FILE)
            df_new.to_csv(
                config.CSV_OUTPUT_FILE,
                mode="a",
                index=False,
                header=write_header,
                encoding="utf-8-sig",
            )

        if output_format in ("json", "both"):
            # Rewrite the whole JSON each time (needed for valid JSON array)
            existing: list[dict] = []
            if os.path.exists(config.JSON_OUTPUT_FILE):
                try:
                    with open(config.JSON_OUTPUT_FILE, "r", encoding="utf-8") as f:
                        existing = json.load(f)
                except Exception:
                    existing = []
            existing.extend(new_products)
            with open(config.JSON_OUTPUT_FILE, "w", encoding="utf-8") as f:
                json.dump(existing, f, ensure_ascii=False, indent=2)


def _dedup_csv() -> int:
    """Remove rows with duplicate product IDs from the CSV output file in-place.

    Reads the entire CSV, drops duplicates on the ``id`` column (keeping the
    first occurrence), resets the index, and overwrites the file.

    Returns
    -------
    int
        Number of rows in the file after deduplication.  Returns ``0`` when
        the file does not exist.
    """
    if not os.path.exists(config.CSV_OUTPUT_FILE):
        return 0
    df = pd.read_csv(config.CSV_OUTPUT_FILE, encoding="utf-8-sig")
    before = len(df)
    df.drop_duplicates(subset=["id"], inplace=True)
    df.reset_index(drop=True, inplace=True)
    df.to_csv(config.CSV_OUTPUT_FILE, index=False, encoding="utf-8-sig")
    if len(df) < before:
        logger.info("Removed %d duplicate rows. Final count: %d", before - len(df), len(df))
    return len(df)


def _dedup_json() -> None:
    """Remove entries with duplicate product IDs from the JSON output file in-place.

    Reads the JSON array, filters to the first occurrence of each ``id``, and
    overwrites the file.  No-op when the file does not exist.
    """
    if not os.path.exists(config.JSON_OUTPUT_FILE):
        return
    with open(config.JSON_OUTPUT_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    seen: set[str] = set()
    deduped = []
    for item in data:
        pid = str(item.get("id", ""))
        if pid not in seen:
            seen.add(pid)
            deduped.append(item)
    with open(config.JSON_OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(deduped, f, ensure_ascii=False, indent=2)


# ── Per-worker session factory ───────────────────────────────────────────────────

def _make_session() -> requests.Session:
    """Create a new ``requests.Session`` pre-loaded with the required HTTP headers.

    Each worker thread calls this to obtain its own independent session,
    preventing cross-thread state sharing.

    Returns
    -------
    requests.Session
        A session with ``config.DEFAULT_HEADERS`` already applied.
    """
    session = requests.Session()
    session.headers.update(config.DEFAULT_HEADERS)
    return session


# ── Worker function (runs in a thread) ────────────────────────────────────────────

def _scrape_category_worker(cat: dict, delay: float, page_limit: int) -> list[dict]:
    """Scrape one category in an isolated worker thread.

    Creates a private ``requests.Session`` so it does not share connection
    state with the other workers, then delegates to
    ``fetch_products_for_category``.

    Args
    ----
    cat : dict
        Category dict as returned by ``fetch_categories``.
    delay : float
        Base inter-page sleep in seconds (jitter applied inside the fetcher).
    page_limit : int
        Maximum pages to scrape per category (``0`` = unlimited).

    Returns
    -------
    list[dict]
        Normalised product records for all pages of ``cat``.
    """
    session = _make_session()
    return fetch_products_for_category(
        category=cat,
        session=session,
        delay=delay,
        page_limit=page_limit,
    )


# ── Core scraping logic ──────────────────────────────────────────────────────


def run_scraper(args: argparse.Namespace) -> None:
    """Execute the full scraping pipeline according to parsed CLI arguments.

    Steps
    -----
    1. Fetch the full category list (single-threaded bootstrap).
    2. Optionally filter to a single ``--category`` ID.
    3. Load (or initialise) the today's checkpoint.
    4. Clear stale output files when not resuming.
    5. Dispatch remaining categories to a ``ThreadPoolExecutor``; save
       products and update the checkpoint after every completed category.
    6. Run a final deduplication pass on the output files.

    Args
    ----
    args : argparse.Namespace
        Parsed command-line arguments as produced by ``_build_parser().parse_args()``.
        Expected attributes: ``category``, ``output``, ``workers``, ``delay``,
        ``limit``, ``resume``.
    """
    # 1. Fetch categories (single-threaded bootstrap)
    logger.info("Fetching category list…")
    bootstrap_session = _make_session()
    try:
        categories = fetch_categories(session=bootstrap_session)
    except RuntimeError as exc:
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
                "Category ID '%s' not found in sitemap. "
                "Use --list-categories to see available IDs.",
                args.category,
            )
            sys.exit(1)

    # 3. Load checkpoint for resume support
    checkpoint = _load_checkpoint() if args.resume else {"done": []}

    # 4. On a fresh (non-resume) run, clear any old output files
    if not args.resume:
        for fpath in [config.CSV_OUTPUT_FILE, config.JSON_OUTPUT_FILE]:
            if os.path.exists(fpath):
                os.remove(fpath)
                logger.info("Cleared old output file: %s", fpath)

    categories_to_scrape = [
        c for c in categories if c["id"] not in checkpoint["done"]
    ]

    if not categories_to_scrape:
        logger.info("All categories already scraped. Run without --resume to start fresh.")
        return

    total_products = 0

    # Count products already in CSV (when resuming)
    if args.resume and os.path.exists(config.CSV_OUTPUT_FILE):
        try:
            existing_df = pd.read_csv(config.CSV_OUTPUT_FILE, encoding="utf-8-sig")
            total_products = len(existing_df)
            logger.info(
                "Resuming: %d existing products already saved in %s",
                total_products, config.CSV_OUTPUT_FILE,
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
            future = executor.submit(_scrape_category_worker, cat, args.delay, args.limit)
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
                    _append_products(cat_products, args.output)
                    with _counter_lock:
                        total_products += len(cat_products)

                # Mark category done in checkpoint
                with _checkpoint_lock:
                    checkpoint["done"].append(cat["id"])
                _save_checkpoint(checkpoint)

                if cat_products:
                    logger.info(
                        "Category '%s': +%d products (total so far: %d)",
                        cat["name"], len(cat_products), total_products,
                )

                pbar.update(1)

    # 5. Final deduplication pass
    logger.info("Running final deduplication…")
    final_count = _dedup_csv()
    if args.output in ("json", "both"):
        _dedup_json()

    logger.info("Done! ✓  Total unique products: %d", final_count)
    logger.info("Output → %s", config.CSV_OUTPUT_FILE)
    if args.output in ("json", "both"):
        logger.info("Output → %s", config.JSON_OUTPUT_FILE)

    # 6. Calculate Inflation
    logger.info("Calculating inflation metrics...")
    inflation.calculate_inflation()






# ── CLI ──────────────────────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    """Construct and return the CLI argument parser.

    Returns
    -------
    argparse.ArgumentParser
        Configured parser with arguments: ``--list-categories``, ``--category``,
        ``--output``, ``--workers``, ``--delay``, ``--limit``, ``--resume``, ``-v``.
    """
    parser = argparse.ArgumentParser(
        prog="migros-scraper",
        description="Scrape all product data from Migros Türkiye (migros.com.tr).",
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
        help="Scrape only this category ID (e.g. '2'). Omit to scrape all categories.",
    )
    parser.add_argument(
        "--output",
        choices=["csv", "json", "both"],
        default="both",
        help="Output format (default: both).",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=config.DEFAULT_WORKERS,
        metavar="N",
        help=f"Number of parallel category workers (default: {config.DEFAULT_WORKERS}).",
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
    """Parse CLI arguments and run the appropriate action.

    Enables debug logging when ``-v`` / ``--verbose`` is passed, then either
    prints the category list (``--list-categories``) or delegates to
    ``run_scraper()`` for a full scrape.
    """
    parser = _build_parser()
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if args.list_categories:
        session = _make_session()
        try:
            categories = fetch_categories(session=session)
        except RuntimeError as exc:
            logger.error(str(exc))
            sys.exit(1)

        print(f"\n{'ID':<12} {'Name'}")
        print("-" * 50)
        for cat in categories:
            print(f"{cat['id']:<12} {cat['name']}")
        print(f"\nTotal: {len(categories)} categories")
        return

    run_scraper(args)


if __name__ == "__main__":
    main()
