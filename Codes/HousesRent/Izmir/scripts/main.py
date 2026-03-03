"""
main.py — Izmir Rent Scraper (Continuous Full-Scrape Version)
=========================================================

This version is designed to run continuously. It will iterate through
EVERY price range defined in config.SEED_RANGES without stopping,
while still utilizing the anti-bot evasion and resuming features.
"""

import argparse
import json
import logging
import os
import time
import random

import config
# All necessary functions are imported from scraper.py
from scraper import setup_driver, scrape_range, save_incremental, CaptchaDetectedException, delete_selenium_profile

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ── Checkpoint Operations ─────────────────────────────────────────────────────

def _load_checkpoint() -> dict:
    if os.path.exists(config.CHECKPOINT_FILE):
        with open(config.CHECKPOINT_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"done_ranges": []}

def _save_checkpoint(data: dict) -> None:
    os.makedirs(config.CHECKPOINT_DIR, exist_ok=True)
    with open(config.CHECKPOINT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ── Main Execution Function ───────────────────────────────────────────────────

def run(args: argparse.Namespace) -> None:
    # Always resume from where it left off unless --restart is used
    checkpoint = _load_checkpoint() if not args.restart else {"done_ranges": []}

    done_ranges: set[tuple[int, int]] = {
        tuple(r) for r in checkpoint["done_ranges"]
    }

    if args.restart and os.path.exists(config.CSV_OUTPUT_FILE):
        os.remove(config.CSV_OUTPUT_FILE)
        logger.info("Cleared old CSV file: %s", config.CSV_OUTPUT_FILE)
        _save_checkpoint({"done_ranges": []})
        done_ranges = set()

    def mark_done(min_p: int, max_p: int) -> None:
        done_ranges.add((min_p, max_p))
        checkpoint["done_ranges"] = [list(r) for r in done_ranges]
        _save_checkpoint(checkpoint)

    logger.info(
        "Starting continuous Izmir data scraping... "
        "(Total %d ranges in config, %d already completed)",
        len(config.SEED_RANGES),
        len(done_ranges),
    )

    total_saved = 0

    try:
        # Iterate through every single range defined in config.py
        for seed_min, seed_max in config.SEED_RANGES:
            if (seed_min, seed_max) in done_ranges:
                continue

            success = False

            while not success:
                logger.info(f"\n--- STARTING NEW BROWSER SESSION ({seed_min} - {seed_max} TL) ---")
                driver = setup_driver()

                try:
                    saved = scrape_range(
                        driver=driver,
                        min_price=seed_min,
                        max_price=seed_max,
                        done_ranges=done_ranges,
                        save_fn=save_incremental,
                        save_checkpoint_fn=mark_done,
                        indent=0,
                    )
                    total_saved += saved
                    success = True  # Mark as success to exit the while loop and move to next range

                except CaptchaDetectedException:
                    logger.warning(f"🛑 Blocked while scraping the {seed_min}-{seed_max} range!")
                    driver.quit()  # Close the flagged browser
                    delete_selenium_profile()  # Wipe the identity

                    sleep_time = random.randint(60, 120)
                    logger.info(f"⏳ Waiting {sleep_time} seconds before retrying with a new identity...")
                    time.sleep(sleep_time)
                    # Loop restarts to try the same range again

                except Exception as e:
                    logger.error(f"An error occurred: {e}")
                    break  # Break out of the while loop to skip this specific range if it's a critical unknown error

                finally:
                    try:
                        if 'driver' in locals() and driver is not None:
                            driver.quit()
                    except Exception:
                        pass

            # Once the range is fully scraped, take a short breather before starting the next one
            if success:
                logger.info("✅ Range %d–%d TL successfully scraped.", seed_min, seed_max)

                # Check if it's the very last range in the list to avoid unnecessary sleeping at the end
                if (seed_min, seed_max) != config.SEED_RANGES[-1]:
                    cool_down = random.randint(30, 60)
                    logger.info(f"⏳ Cooling down for {cool_down} seconds before tackling the next bracket...")
                    time.sleep(cool_down)

    except KeyboardInterrupt:
        logger.info("Manually stopped by the user.")

    logger.info("\nProcess Complete! 🎉")
    logger.info("Number of new listings saved in this session: %d", total_saved)
    logger.info("Output File → %s", config.CSV_OUTPUT_FILE)


# ── Command Line Interface (CLI) Settings ─────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="izmir-scraper",
        description="Scrape house rental listings for Izmir continuously from sahibinden.com.",
    )
    parser.add_argument(
        "--restart",
        action="store_true",
        help="Deletes all records and the CSV file for the day and starts over.",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Shows detailed (debug) logs.",
    )
    return parser

def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    run(args)

if __name__ == "__main__":
    main()