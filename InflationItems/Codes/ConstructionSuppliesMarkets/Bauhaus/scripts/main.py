"""
main.py — Bauhaus Scraper Orchestrator

This script drives the entire Bauhaus scraping process. It discovers all categories,
filters out those that were already completed (if `--resume` is used), sets up
a ThreadPoolExecutor to scrape multiple categories simultaneously, saves incremental
checkpoints to prevent data loss on crashes, deduplicates the final dataset,
saves the output to CSV/JSON, and finally triggers the inflation calculation module.
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
    logger.info(f"Saved {len(products)} products to {out_path}")

    logger.info(f"Saved {len(products)} products to {out_path}")

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

def scrape_category_worker(cat, limit, cp_path, completed_ids):
    """
    Worker function to scrape a single category. Writes its ID to the checkpoint when done.

    Args:
        cat (dict): The category directory to fetch.
        limit (int): The page limit (for testing).
        cp_path (str): The checkpoint file to update.
        completed_ids (set): The shared set of completed IDs.

    Returns:
        list[dict]: Extracted product data for the category.
    """
    products = product_fetcher.fetch_products_for_category(cat, limit_pages=limit)
    completed_ids.add(cat["id"])
    save_checkpoint(cp_path, completed_ids)
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
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    config.REQUEST_DELAY = args.delay

    cats = category_fetcher.fetch_categories()
    if not cats:
        logger.error("Failed to load categories.")
        sys.exit(1)

    if args.list_categories:
        for c in cats:
            print(f"{c['id']} - {c['name']}")
        sys.exit(0)

    # Filter categories
    if args.category:
        cats = [c for c in cats if c["id"] == args.category]
        if not cats:
            logger.error(f"Category {args.category} not found.")
            sys.exit(1)

    date_str = datetime.now().strftime("%Y-%m-%d")
    checkpoint_file = os.path.join(config.CHECKPOINT_DIR, f"bauhaus_checkpoint_{date_str}.json")
    
    completed_ids = set()
    if args.resume:
        completed_ids = load_checkpoint(checkpoint_file)
        logger.info(f"Resuming with {len(completed_ids)} categories already completed.")

    all_products = []
    
    cats_to_scrape = [c for c in cats if c["id"] not in completed_ids]
    cat_count = len(cats_to_scrape)
    logger.info(f"Beginning scrape for {cat_count} categories using {args.workers} workers...")

    # For thread safety of checking checkpoints
    # Though set operations in python are thread safe, saving is not. 
    # But since workers just add to set and write json, it's fairly safe if we use a lock or just one file per worker. 
    # To be extremely safe, we will collect products and write checkpoint in main thread after future completes.

    completed_count = 0
    count_lock = threading.Lock()

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        future_to_cat = {executor.submit(product_fetcher.fetch_products_for_category, c, None, args.limit): c for c in cats_to_scrape}
        for future in as_completed(future_to_cat):
            cat = future_to_cat[future]
            try:
                cat_prods = future.result()
                all_products.extend(cat_prods)
                completed_ids.add(cat["id"])
                save_checkpoint(checkpoint_file, completed_ids)
                
                with count_lock:
                    completed_count += 1
                    logger.info(f"[{completed_count}/{cat_count}] Merged {len(cat_prods)} products from {cat['name']}")
                    
            except Exception as exc:
                logger.error(f"Category {cat['id']} generated an exception: {exc}")

    # Deduplicate
    unique_products = {p["id"]: p for p in all_products}.values()
    
    # Save Outputs
    if not os.path.exists(config.OUTPUT_DIR):
        os.makedirs(config.OUTPUT_DIR)
        
    base_name = f"bauhaus_{date_str}"
    csv_path = os.path.join(config.OUTPUT_DIR, f"{base_name}.csv")

    save_csv(unique_products, csv_path)

    if inflation:
        logger.info("Calculating inflation metrics...")
        try:
            inflation.calculate_inflation()
        except Exception as e:
            logger.error(f"Failed to calculate inflation: {e}")
    else:
        logger.warning("Skipping inflation calculation because the module could not be imported.")

if __name__ == "__main__":
    main()
