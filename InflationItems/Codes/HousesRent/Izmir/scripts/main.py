"""
main.py — Izmir Rent Scraper (Modular Architecture)
"""

import argparse
import json
import logging
import os
import time
import random

import config
from scraper import setup_driver, CategoryScanner, DataExtractor, CaptchaDetectedException, delete_selenium_profile

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger(__name__)

def _load_checkpoint() -> dict:
    default_state = {"scraped_urls": [], "completed_brackets": []}
    if os.path.exists(config.CHECKPOINT_FILE):
        try:
            with open(config.CHECKPOINT_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if "completed_brackets" not in data:
                    data["completed_brackets"] = []
                if "scraped_urls" not in data:
                    data["scraped_urls"] = []
                return data
        except json.JSONDecodeError:
            logger.error("Checkpoint file corrupted. Starting fresh.")
            return default_state
    return default_state

def _save_checkpoint(data: dict) -> None:
    os.makedirs(config.CHECKPOINT_DIR, exist_ok=True)
    with open(config.CHECKPOINT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def run(args: argparse.Namespace) -> None:
    checkpoint = _load_checkpoint() if not args.restart else {"scraped_urls": [], "completed_brackets": []}

    scraped_urls: set[str] = set(checkpoint["scraped_urls"])
    completed_brackets: set[tuple[int, int]] = {tuple(b) for b in checkpoint["completed_brackets"]}

    if args.restart and os.path.exists(config.CSV_OUTPUT_FILE):
        os.remove(config.CSV_OUTPUT_FILE)
        logger.info("Restart flag used. Cleared old CSV and checkpoints.")
        _save_checkpoint({"scraped_urls": [], "completed_brackets": []})
        scraped_urls = set()
        completed_brackets = set()

    total_saved = 0

    # 1. Initialize driver variable OUTSIDE the loops
    driver = None

    for seed_min, seed_max in config.SEED_RANGES:
        if (seed_min, seed_max) in completed_brackets:
            logger.info(f"⏭️ Skipping fully completed bracket: {seed_min} - {seed_max} TL")
            continue

        bracket_complete = False

        while not bracket_complete:
            # 2. Only spin up a new browser if we don't currently have one
            if driver is None:
                driver = setup_driver()

            scanner = CategoryScanner(driver)
            extractor = DataExtractor(driver)

            try:
                # --- PHASE 1: DISCOVERY ---
                logger.info(f"\n--- 🔍 PHASE 1: DISCOVERING URLS ({seed_min} - {seed_max} TL) ---")
                target_urls = scanner.discover_bracket(seed_min, seed_max)

                pending_urls = [url for url in target_urls if url not in scraped_urls]
                logger.info(f"Generated {len(target_urls)} URLs. {len(pending_urls)} left to scrape.")

                # --- PHASE 2: EXTRACTION ---
                if pending_urls:
                    logger.info(f"\n--- ⛏️ PHASE 2: EXTRACTING DATA ---")

                    for idx, url in enumerate(pending_urls):
                        logger.info(f"Extracting page {idx + 1}/{len(pending_urls)}...")

                        records = extractor.extract_from_url(url)

                        if not records:
                            logger.info("📭 No listings found on this page. Reached the end.")
                            scraped_urls.add(url)
                            checkpoint["scraped_urls"] = list(scraped_urls)
                            _save_checkpoint(checkpoint)
                            break

                        extractor.save_to_csv(records)
                        total_saved += len(records)
                        scraped_urls.add(url)

                        checkpoint["scraped_urls"] = list(scraped_urls)
                        _save_checkpoint(checkpoint)

                        #time.sleep(random.uniform(1, 3))

                bracket_complete = True
                completed_brackets.add((seed_min, seed_max))
                checkpoint["completed_brackets"] = [list(b) for b in completed_brackets]
                _save_checkpoint(checkpoint)

                bracket_sleep = random.randint(1, 5)
                logger.info(f"☕ Bracket complete! Taking a {bracket_sleep}-second break...")
                time.sleep(bracket_sleep)

            except CaptchaDetectedException:
                logger.warning("🛑 CAPTCHA/Block detected! Wiping identity and restarting...")

                # 3. Quit the current blocked driver and set it to None so a new one is made next loop
                if driver:
                    driver.quit()
                driver = None

                delete_selenium_profile()
                time.sleep(random.randint(30, 60))

            except Exception as e:
                logger.error(f"Critical Error: {e}")
                break

            # 4. REMOVED the `finally` block from here so the browser doesn't quit on success!

    # 5. Quit the driver safely when all brackets are completely done
    if driver:
        try:
            driver.quit()
        except Exception:
            pass

    logger.info(f"\nProcess Complete! 🎉 Saved {total_saved} new records.")

def main() -> None:
    parser = argparse.ArgumentParser(description="Modular Izmir Rent Scraper")
    parser.add_argument("--restart", action="store_true", help="Start over from scratch.")
    args = parser.parse_args()
    run(args)

if __name__ == "__main__":
    main()