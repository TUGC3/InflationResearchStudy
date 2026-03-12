"""
Bauhaus Türkiye Product Scraper - Main Entry Point and Orchestration Layer
==========================================================================

This module serves as the primary interface for the Bauhaus product scraping system,
providing comprehensive CLI functionality and coordinating all scraping operations
through a high-performance, multi-threaded architecture.

Core Responsibilities
----------------------
- Command-line argument parsing and validation
- HTML navigation-based category discovery coordination
- Parallel product extraction using ThreadPoolExecutor
- Incremental data persistence and batched checkpoint management
- Cross-category product deduplication
- CSV data export with standardized formatting

Execution Pipeline
-----------------
1. Category Discovery: Parses homepage HTML navigation to extract complete taxonomy
2. Checkpoint Management: Loads previous session state when resume mode is enabled
3. Parallel Processing: Dispatches categories to worker threads with optimized sessions
4. Batched Persistence: Saves data and checkpoints every 5 categories for performance
5. Data Deduplication: Removes duplicate products across category boundaries
6. Export Generation: Creates CSV output file with UTF-8 BOM formatting

Performance Architecture
------------------------
- lxml parser for 3-5x faster HTML processing compared to default parsers
- CSS selectors for efficient DOM traversal and element extraction
- HTTP session reuse across categories for connection pooling
- Batched I/O operations to reduce filesystem overhead
- Adaptive rate limiting to prevent detection while optimizing speed

Threading Model
---------------
- ThreadPoolExecutor manages concurrent category processing
- Each worker maintains an independent requests.Session object
- Configurable worker count (default: 2) for performance tuning
- Batched checkpoint writing reduces I/O contention

Optimization Features
---------------------
The scraper implements six key performance optimizations:
1. **lxml Parser**: High-performance XML/HTML processing
2. **CSS Selectors**: Efficient DOM element targeting
3. **Session Reuse**: Persistent HTTP connections
4. **Batched Checkpoints**: Reduced I/O overhead (every 5 categories)
5. **String Optimization**: Efficient price cleaning operations
6. **Adaptive Rate Limiting**: Intelligent request timing

Output Management
-----------------
All file paths are resolved relative to the config.py location, ensuring
consistent operation regardless of execution directory:

- CSV Export: UTF-8 with BOM formatting for Excel compatibility
- Checkpoint Files: Daily session state for resume capability

CLI Interface
-------------
The module provides comprehensive command-line options including:
- Category listing and selective scraping
- Performance tuning (workers, delays, limits)
- Session management (resume functionality)
- Debug mode with verbose logging

Usage Examples
--------------
```bash
# List all available categories
python main.py --list-categories

# Scrape single category for testing
python main.py --category bauhaus-oto --limit 2

# Full catalog extraction with default settings
python main.py

# Parallel processing with custom worker count
python main.py --workers 4

# Rate-limited scraping with custom delay
python main.py --delay 3.0

# Resume interrupted session
python main.py --resume

# Enable debug logging
python main.py --category bauhaus-oto -v
```
"""

import sys
import os
import csv
import json
import logging
import argparse
from datetime import datetime
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import config, category_fetcher, product_fetcher

# Add the location of inflation.py to sys.path
_inflation_dir = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), 
    "..", "..", "..", "..", "..", "Inflations", "Codes", "ConstructionSuppliesMarkets", "Bauhaus"
)
sys.path.append(os.path.abspath(_inflation_dir))
try:
    import inflation
except ImportError as e:
    inflation = None
    print(f"Warning: Could not import inflation module: {e}")

logger = logging.getLogger(__name__)

def parse_args():
    """
    Parses command line arguments for the scraper.

    Returns:
        argparse.Namespace: The parsed arguments including output format,
                            workers count, resume flags, etc.
    """
    p = argparse.ArgumentParser(description="Bauhaus Türkiye Product Scraper")
    p.add_argument("--list-categories", action="store_true", help="Print all categories and exit")
    p.add_argument("--category", type=str, help="Scrape only one category ID")
    p.add_argument("--workers", type=int, default=config.DEFAULT_WORKERS, help="Parallel workers")
    p.add_argument("--delay", type=float, default=config.REQUEST_DELAY, help="Base delay")
    p.add_argument("--limit", type=int, default=0, help="Max pages per category")
    p.add_argument("--resume", action="store_true", help="Resume interrupted run")
    p.add_argument("-v", "--verbose", action="store_true", help="Debug logging")
    return p.parse_args()

def save_csv(products, out_path):
    """
    Writes a list of product dictionaries into a UTF-8 encoded CSV file.

    Args:
        products (list[dict]): Normalised list of products to save.
        out_path (str): The absolute path for the target .csv file.
    """
    if not products:
        return
    fieldnames = ["id", "sku", "name", "brand", "category", "regular_price", "shown_price", "discount_rate", "unit", "status"]
    with open(out_path, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(products)
    logger.info(f"✅ Saved {len(products)} products")

def load_checkpoint(cp_path):
    """
    Loads saved category IDs from a previous run to enable resume functionality.

    Args:
        cp_path (str): Path to the checkpoint JSON file.

    Returns:
        set: A set containing the string IDs of categories already scraped.
    """
    if os.path.exists(cp_path):
        with open(cp_path, 'r', encoding='utf-8') as f:
            return set(json.load(f))
    return set()

def save_checkpoint(cp_path, completed):
    """
    Writes the current set of completed category IDs to the checkpoint file.

    Args:
        cp_path (str): Path to the checkpoint JSON file.
        completed (set): Set of completed string IDs.
    """
    with open(cp_path, 'w', encoding='utf-8') as f:
        json.dump(list(completed), f)

def scrape_category_worker(cat, limit, session, cp_path, completed_ids):
    """
    Worker function to scrape a single category. Writes its ID to the checkpoint when done.

    Args:
        cat (dict): The category directory to fetch.
        limit (int): The page limit (for testing).
        session (requests.Session): Reusable HTTP session for this worker.
        cp_path (str): The checkpoint file to update.
        completed_ids (set): The shared set of completed IDs.

    Returns:
        list[dict]: Extracted product data for the category.
    """
    products = product_fetcher.fetch_products_for_category(cat, session, limit)
    completed_ids.add(cat["id"])
    return products

def main():
    """
    Main orchestrator logic. Loops together all pieces: Category discovery ->
    Parallel Fetching -> Checkpointing -> Deduplication -> File saving -> Inflation.
    """
    args = parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%H:%M:%S'
    )
    
    config.REQUEST_DELAY = args.delay

    cats = category_fetcher.fetch_categories()
    if not cats:
        logger.error("✗  Failed to load categories.")
        sys.exit(1)

    if args.list_categories:
        for c in cats:
            print(f"{c['id']} - {c['name']}")
        sys.exit(0)

    # Filter categories
    if args.category:
        cats = [c for c in cats if c["id"] == args.category]
        if not cats:
            logger.error(f"✗  Category '{args.category}' not found.")
            sys.exit(1)

    date_str = datetime.now().strftime("%Y-%m-%d")
    checkpoint_file = os.path.join(config.CHECKPOINT_DIR, f"bauhaus_checkpoint_{date_str}.json")
    
    completed_ids = set()
    if args.resume:
        completed_ids = load_checkpoint(checkpoint_file)
        logger.info(f"↩  Resuming: {len(completed_ids)} categories already completed.")

    all_products = []
    
    cats_to_scrape = [c for c in cats if c["id"] not in completed_ids]
    cat_count = len(cats_to_scrape)
    logger.info(f"▶  Scraping {cat_count} categor{'y' if cat_count == 1 else 'ies'} with {args.workers} worker(s)…")

    # For thread safety of checking checkpoints
    # Though set operations in python are thread safe, saving is not. 
    # But since workers just add to set and write json, it's fairly safe if we use a lock or just one file per worker. 
    # To be extremely safe, we will collect products and write checkpoint in main thread after future completes.

    completed_count = 0
    count_lock = threading.Lock()
    checkpoint_interval = 5  # Save checkpoint every 5 categories
    
    import time
    start_time = time.time()

    # Create sessions for each worker
    worker_sessions = [product_fetcher.create_session() for _ in range(args.workers)]

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        # Assign each category a session based on worker index
        future_to_cat = {}
        for i, cat in enumerate(cats_to_scrape):
            worker_session = worker_sessions[i % args.workers]
            future = executor.submit(scrape_category_worker, cat, args.limit, worker_session, checkpoint_file, completed_ids)
            future_to_cat[future] = cat
            
        for future in as_completed(future_to_cat):
            cat = future_to_cat[future]
            try:
                cat_prods = future.result()
                all_products.extend(cat_prods)
                
                with count_lock:
                    completed_count += 1
                    logger.info(f"✓  Category '{cat['name']}': +{len(cat_prods)} products (total: {len(all_products)})")
                    
                    # Batch checkpoint updates
                    if completed_count % checkpoint_interval == 0 or completed_count == cat_count:
                        save_checkpoint(checkpoint_file, completed_ids)
                        logger.info(f"💾 Checkpoint saved: {completed_count}/{cat_count} categories completed")
                    
            except Exception as exc:
                logger.error(f"✗  Category '{cat['id']}' failed: {exc}")
        
        # Final checkpoint save
        save_checkpoint(checkpoint_file, completed_ids)

    # Calculate elapsed time
    elapsed_time = time.time() - start_time
    logger.info("Scraping completed in %.1f seconds (%.1f min)", elapsed_time, elapsed_time / 60)
    
    # Deduplicate
    before_count = len(all_products)
    unique_products = list({p["id"]: p for p in all_products}.values())
    after_count = len(unique_products)
    
    if before_count > after_count:
        logger.info(f"Running final deduplication…")
        logger.info(f"Removed {before_count - after_count} duplicate records. Final count: {after_count}")
    
    # Save Outputs
    if not os.path.exists(config.OUTPUT_DIR):
        os.makedirs(config.OUTPUT_DIR)
        
    base_name = f"bauhaus_{date_str}"
    csv_path = os.path.join(config.OUTPUT_DIR, f"{base_name}.csv")

    save_csv(unique_products, csv_path)
    logger.info("Done! ✓  Total unique products: %d", after_count)
    logger.info("Output → %s", csv_path)

    if inflation:
        logger.info("Calculating inflation metrics...")
        try:
            inflation.calculate_inflation()
        except Exception as e:
            logger.error(f"✗  Failed to calculate inflation: {e}")
    else:
        logger.warning("⚠  Skipping inflation calculation (module not imported).")

if __name__ == "__main__":
    main()
