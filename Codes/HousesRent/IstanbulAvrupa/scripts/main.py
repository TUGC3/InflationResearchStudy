"""
main.py — Istanbul Avrupa Rent Scraper (CLI entry point)
=========================================================

This scraper uses ADAPTIVE RECURSIVE BINARY SPLITTING with an EARLY PEEK
strategy. On the first page of any seed range, it parses the total count
of matching listings.
  - If >1000: It splits the range in half immediately.
  - If <=1000: It scrapes all pages normally.

Usage:
  # Full fresh scrape
  python main.py

  # Resume an interrupted run
  python main.py --resume

  # Verbose debug output
  python main.py -v
"""

import argparse
import json
import logging
import os
import sys
import time
import random

import config
from scraper import setup_driver, scrape_range, save_incremental

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ── Checkpoint helpers ────────────────────────────────────────────────────────

def _load_checkpoint() -> dict:
    if os.path.exists(config.CHECKPOINT_FILE):
        with open(config.CHECKPOINT_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"done_ranges": []}


def _save_checkpoint(data: dict) -> None:
    os.makedirs(config.CHECKPOINT_DIR, exist_ok=True)
    with open(config.CHECKPOINT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ── Main run ──────────────────────────────────────────────────────────────────

def run(args: argparse.Namespace) -> None:
    # Load or reset checkpoint
    checkpoint = _load_checkpoint() if args.resume else {"done_ranges": []}

    # Convert stored list-of-lists back to a set of tuples for fast lookup
    done_ranges: set[tuple[int, int]] = {
        tuple(r) for r in checkpoint["done_ranges"]
    }

    # On a fresh run, clear today's CSV so we don't mix stale data
    if not args.resume and os.path.exists(config.CSV_OUTPUT_FILE):
        os.remove(config.CSV_OUTPUT_FILE)
        logger.info("Cleared old CSV: %s", config.CSV_OUTPUT_FILE)

    if not args.resume:
        # Also wipe the checkpoint so there are no stale entries
        _save_checkpoint({"done_ranges": []})
        done_ranges = set()

    # ── Checkpoint callback ───────────────────────────────────────────────────
    def mark_done(min_p: int, max_p: int) -> None:
        done_ranges.add((min_p, max_p))
        checkpoint["done_ranges"] = [list(r) for r in done_ranges]
        _save_checkpoint(checkpoint)

    logger.info(
        "Starting adaptive scrape for Istanbul Avrupa "
        "(%d seed range(s), %d already completed)…",
        len(config.SEED_RANGES),
        len(done_ranges),
    )

    driver = setup_driver()
    total_saved = 0

    try:
        for seed_min, seed_max in config.SEED_RANGES:
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

            time.sleep(random.uniform(
                config.BETWEEN_BRACKET_DELAY_MIN,
                config.BETWEEN_BRACKET_DELAY_MAX,
            ))

    finally:
        driver.quit()

    logger.info("\nDone! ✓  Total new records saved: %d", total_saved)
    logger.info("Output → %s", config.CSV_OUTPUT_FILE)


# ── CLI ───────────────────────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="istanbul-avrupa-scraper",
        description="Scrape house rental listings for Istanbul Avrupa from sahibinden.com using early peek adaptive splitting.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Skip price ranges already completed in today's checkpoint file.",
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

    run(args)


if __name__ == "__main__":
    main()
