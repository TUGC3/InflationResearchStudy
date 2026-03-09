"""
main.py — Istanbul Avrupa Rent Scraper — CLI entry point & orchestrator
========================================================================

This module is the top-level entry point for the Istanbul Avrupa rent scraper.
It orchestrates bracket extraction, scraper iteration, checkpoint management,
and terminal logging.

Pipeline
--------
1. **Adaptive bracket discovery** — ``scraper.scrape_and_resolve()`` probes
   the listing count for wide price ranges and recursively splits them until
   every leaf bracket is safely under the limit.
2. **Page scraping** — ``scraper.scrape_leaf_bracket()`` iterates over the
   pages of safe brackets, extracting listing records.
3. **Checkpoint loading** — when ``--resume`` is passed, today's checkpoint
   file is loaded, and already-completed brackets and cached resolutions are
   re-used to skip redunant work.
4. **Incremental saving** — product data and checkpoint state are written to
   disk incrementally after safe boundaries.

Output files
------------
All paths are configured in ``config.py`` and derived from the project structure.

    Datas/HousesRent/IstanbulAvrupa/IstanbulAvrupa_<DATE>.csv
    Codes/HousesRent/IstanbulAvrupa/checkpoints/checkpoint_<DATE>.json

Usage examples
--------------
  # Full scrape (starts fresh)
  python main.py

  # Resume an interrupted run (skips already-done brackets)
  python main.py --resume

  # Limit number of leaf brackets (useful for quick testing)
  python main.py --limit-brackets 3

  # Slow down page requests
  python main.py --delay 4.0

  # Enable verbose / debug-level logging
  python main.py -v
"""

import argparse
import json
import logging
import os
import random
import time

import config
import inflation
from scraper import (
    setup_driver,
    scrape_and_resolve,
    save_incremental,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ── Checkpoint helpers ────────────────────────────────────────────────────────

def _load_checkpoint() -> dict:
    """Load today's checkpoint file from disk.

    Returns
    -------
    dict
        Parsed checkpoint dict. Schema: ``{"done_ranges": [[min, max], ...], "brackets": [...]}``.
        Returns default dict when the checkpoint file does not yet exist.
    """
    if os.path.exists(config.CHECKPOINT_FILE):
        with open(config.CHECKPOINT_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"done_ranges": [], "brackets": None}


def _save_checkpoint(data: dict) -> None:
    """Write ``data`` to ``config.CHECKPOINT_FILE``.

    Creates ``config.CHECKPOINT_DIR`` if it does not already exist.

    Args
    ----
    data : dict
        Checkpoint dict to serialise. Expected schema:
        ``{"done_ranges": [[min, max], ...], "brackets": [...]}``.
    """
    os.makedirs(config.CHECKPOINT_DIR, exist_ok=True)
    with open(config.CHECKPOINT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ── Output helpers ────────────────────────────────────────────────────────────

def _append_records(new_records: list[dict]) -> None:
    """Append a batch of records to the CSV incrementally.

    Args
    ----
    new_records : list[dict]
        Products scraped from a bracket.
    """
    if not new_records:
        return
    save_incremental(new_records)


# ── Core run ──────────────────────────────────────────────────────────────────

def run(args: argparse.Namespace) -> None:
    """Execute the full scraping pipeline according to parsed CLI arguments.

    Steps
    -----
    1. Load (or reset) the today's checkpoint.
    2. Setup the uc.Chrome driver instance.
    3. Loop through brackets and execute scraping logically.
    4. Save incremental values to disk.

    Args
    ----
    args : argparse.Namespace
        Parsed command-line arguments as produced by ``_build_parser().parse_args()``.
        Expected attributes: ``delay``, ``limit_brackets``, ``resume``, ``verbose``.
    """
    # ── Load / reset checkpoint ───────────────────────────────────────────────
    checkpoint = _load_checkpoint() if args.resume else {"done_ranges": []}
    done_ranges: set[tuple[int, int]] = {
        tuple(r) for r in checkpoint.get("done_ranges", [])
    }

    if not args.resume:
        if os.path.exists(config.CSV_OUTPUT_FILE):
            os.remove(config.CSV_OUTPUT_FILE)
            logger.info("Cleared old CSV: %s", config.CSV_OUTPUT_FILE)
        _save_checkpoint({"done_ranges": []})
        done_ranges = set()

    # ── Checkpoint callback ───────────────────────────────────────────────────
    def mark_done(min_p: int, max_p: int) -> None:
        done_ranges.add((min_p, max_p))
        checkpoint["done_ranges"] = [list(r) for r in done_ranges]
        _save_checkpoint(checkpoint)

    driver = setup_driver()
    total_saved = 0

    try:
        brackets_scraped = 0

        for seed_min, seed_max in config.SEED_RANGES:
            logger.info("Seed range: %d – %d TL", seed_min, seed_max)
            saved = scrape_and_resolve(
                driver, seed_min, seed_max,
                done_ranges=done_ranges,
                save_fn=_append_records,
                mark_done_fn=mark_done,
                bracket_cache=None,
                delay=args.delay,
            )
            total_saved += saved
            brackets_scraped += 1

            # --limit-brackets logic
            # Note: limit-brackets originally used len(bracket_cache), which counted leaf brackets.
            # Without bracket_cache, we'll check how many ranges are in done_ranges.
            if args.limit_brackets and args.limit_brackets > 0:
                if len(done_ranges) >= args.limit_brackets:
                    logger.info(
                        "Reached --limit-brackets (%d). Stopping early.",
                        args.limit_brackets,
                    )
                    break

            time.sleep(random.uniform(
                config.BETWEEN_BRACKET_DELAY_MIN,
                config.BETWEEN_BRACKET_DELAY_MAX,
            ))

    finally:
        driver.quit()

    logger.info("Done! ✓  Total records saved: %d", total_saved)
    logger.info("Output → %s", config.CSV_OUTPUT_FILE)
    
    # Calculate Inflation
    logger.info("Calculating inflation metrics...")
    inflation.calculate_inflation()

# ── CLI ───────────────────────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    """Construct and return the CLI argument parser.

    Returns
    -------
    argparse.ArgumentParser
        Configured parser with arguments: ``--delay``, ``--limit-brackets``,
        ``--resume``, ``-v``.
    """
    parser = argparse.ArgumentParser(
        prog="istanbul-avrupa-scraper",
        description=(
            "Scrape house rental listings for Istanbul Avrupa from sahibinden.com. "
            "Uses adaptive bracket splitting + single-pass scraping (no duplicate page loads)."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=config.PAGE_LOAD_DELAY,
        metavar="SECONDS",
        help=f"Per-page wait time in seconds (default: {config.PAGE_LOAD_DELAY}). Actual waits are ±50%% jittered.",
    )
    parser.add_argument(
        "--limit-brackets",
        type=int,
        default=0,
        metavar="N",
        help="Stop after scraping N leaf brackets (0 = unlimited, useful for testing).",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help=(
            "Skip brackets already completed in today’s checkpoint. "
            "If the bracket list from a previous run is cached in the checkpoint, "
            "listing-count checks are skipped entirely and scraping resumes directly."
        ),
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable debug-level logging.",
    )
    return parser


def main() -> None:
    """Parse CLI arguments and run the appropriate action.

    Enables debug logging when ``-v`` / ``--verbose`` is passed, then delegates to
    ``run()`` for the scrape lifecycle.
    """
    parser = _build_parser()
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    run(args)


if __name__ == "__main__":
    main()
