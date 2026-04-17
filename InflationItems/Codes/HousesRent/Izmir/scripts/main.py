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
from scraper import (
    setup_driver, CategoryScanner, DataExtractor,
    CaptchaDetectedException, delete_selenium_profile, save_incremental,
    IZMIR_DISTRICT_SLUGS, IZMIR_SLUG_TO_DISTRICT
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── Checkpoint helpers ────────────────────────────────────────────────────────

_CHECKPOINT_DEFAULTS: dict = {
    "scraped_urls":         [],
    "completed_districts":  [],
    "district_ranges_done": {},
    "discovered_urls":      {},
}

def _load_checkpoint() -> dict:
    if os.path.exists(config.CHECKPOINT_FILE):
        try:
            with open(config.CHECKPOINT_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            for key, default in _CHECKPOINT_DEFAULTS.items():
                if key not in data:
                    data[key] = default
            return data
        except json.JSONDecodeError:
            logger.error("Checkpoint file corrupted. Starting fresh.")
    return {k: (v.copy() if isinstance(v, (list, dict)) else v)
            for k, v in _CHECKPOINT_DEFAULTS.items()}

def _save_checkpoint(data: dict) -> None:
    os.makedirs(config.CHECKPOINT_DIR, exist_ok=True)
    with open(config.CHECKPOINT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ── Trust-score warm-up ───────────────────────────────────────────────────────


def quit_driver(driver) -> None:
    if driver:
        try:
            driver.quit()
        except Exception:
            pass

# ── Helpers ───────────────────────────────────────────────────────────────────

def _scrape_pages(
        pages: list[str],
        extractor: DataExtractor,
        scraped_urls: set,
        checkpoint: dict,
        save_fn,
        district_slug: str,  # <-- Added parameter to know which district we are on
        label: str = "",
) -> int:
    pending = [u for u in pages if u not in scraped_urls]
    already = len(pages) - len(pending)
    if already:
        logger.info(f"      ↳ {already} pages already scraped, skipping.")

    accumulated_records = []
    new_urls = set()
    proper_district = IZMIR_SLUG_TO_DISTRICT.get(district_slug, "Unknown")

    for idx, url in enumerate(pending):
        logger.info(f"      📄 {label}Page {idx + 1}/{len(pending)} ...")

        try:
            records = extractor.extract_from_url(url)
            new_urls.add(url)

            if records:
                # Inject the clean district name, move Sahibinden's raw text to Neighborhood
                for r in records:
                    r["Neighborhood"] = r.get("District", "N/A")
                    r["District"] = proper_district

                accumulated_records.extend(records)

            time.sleep(random.uniform(0.8, 1.8))

        except Exception as e:
            if accumulated_records:
                actual_saved = save_fn(accumulated_records)
                logger.info(f"      💾 HIT A WALL! Saved {actual_saved} valid records.")

            scraped_urls.update(new_urls)
            checkpoint["scraped_urls"] = list(scraped_urls)
            _save_checkpoint(checkpoint)
            raise e

    if accumulated_records:
        actual_saved = save_fn(accumulated_records)
        logger.info(f"      ✅ BATCH COMPLETE! Saved {actual_saved} valid records.")

    scraped_urls.update(new_urls)
    checkpoint["scraped_urls"] = list(scraped_urls)
    _save_checkpoint(checkpoint)

    return len(accumulated_records)


# ── Main run loop ─────────────────────────────────────────────────────────────

def run(args: argparse.Namespace) -> None:
    if args.restart:
        checkpoint = {k: (v.copy() if isinstance(v, (list, dict)) else v)
                      for k, v in _CHECKPOINT_DEFAULTS.items()}
        if os.path.exists(config.CSV_OUTPUT_FILE):
            os.remove(config.CSV_OUTPUT_FILE)
        _save_checkpoint(checkpoint)
        logger.info("Restart flag used — cleared CSV and checkpoint.")
    else:
        checkpoint = _load_checkpoint()

    scraped_urls: set[str] = set(checkpoint["scraped_urls"])
    total_saved = 0
    driver = None

    for slug in IZMIR_DISTRICT_SLUGS:
        if slug in checkpoint["completed_districts"]:
            logger.info(f"⏭️  Skipping completed district: {slug}")
            continue

        district_done = False

        while not district_done:
            if driver is None:
                driver = setup_driver()

            scanner = CategoryScanner(driver)
            extractor = DataExtractor(driver)

            try:
                # ── 1. Determine Execution Path for this District ─────────────
                needs_split = False
                total_listings = 0

                if slug in checkpoint.get("district_ranges_done", {}):
                    needs_split = True
                else:
                    total_listings = scanner.get_district_total(slug)
                    if total_listings > config.MAX_LISTINGS_PER_QUERY:
                        needs_split = True
                    elif total_listings == 0:
                        logger.info(f"📭 District {slug} has 0 listings. Skipping.")
                        district_done = True
                        checkpoint["completed_districts"].append(slug)
                        _save_checkpoint(checkpoint)
                        continue

                # ── 2a. Simple Path (<= 1000 listings) ────────────────────────
                if not needs_split:
                    logger.info(f"\n--- 🏙️  DISTRICT {slug.upper()} ({total_listings} listings) ---")

                    base_key = f"{slug}_base"
                    if base_key in checkpoint["discovered_urls"]:
                        target_urls = checkpoint["discovered_urls"][base_key]
                    else:
                        target_urls = scanner.get_district_pages_no_price(slug, total_listings)
                        checkpoint["discovered_urls"][base_key] = target_urls
                        _save_checkpoint(checkpoint)

                    saved = _scrape_pages(
                        target_urls, extractor, scraped_urls, checkpoint,
                        save_incremental, district_slug=slug, label=f"[{slug}] "
                    )
                    total_saved += saved

                    district_done = True
                    checkpoint["completed_districts"].append(slug)
                    checkpoint["discovered_urls"].pop(base_key, None)
                    _save_checkpoint(checkpoint)

                    time.sleep(random.uniform(5.0, 10.0))

                # ── 2b. Complex Path (> 1000 listings -> Split via Seed Ranges)
                else:
                    logger.info(f"\n--- 🏙️  DISTRICT {slug.upper()} (>1000 listings) -> Splitting ---")
                    checkpoint.setdefault("district_ranges_done", {}).setdefault(slug, [])
                    _save_checkpoint(checkpoint)

                    completed_ranges = [tuple(r) for r in checkpoint["district_ranges_done"][slug]]

                    for seed_min, seed_max in config.SEED_RANGES:
                        if (seed_min, seed_max) in completed_ranges:
                            continue

                        bracket_key = f"{slug}_{seed_min}_{seed_max}"

                        logger.info(f"\n--- 🔍 DISCOVERING: {slug} ({seed_min}–{seed_max} TL) ---")
                        results = checkpoint.setdefault("discovered_urls", {}).get(bracket_key, [])

                        try:
                            scanner.discover_bracket(slug, seed_min, seed_max, results=results)
                        except CaptchaDetectedException:
                            logger.warning(f"🛑 CAPTCHA during discovery! Saving {len(results)} URLs...")
                            checkpoint["discovered_urls"][bracket_key] = list(dict.fromkeys(results))
                            _save_checkpoint(checkpoint)
                            raise

                        target_urls = list(dict.fromkeys(results))
                        checkpoint["discovered_urls"][bracket_key] = target_urls
                        _save_checkpoint(checkpoint)

                        logger.info(f"   ✅ Discovery complete: {len(target_urls)} pages.")
                        logger.info(f"\n--- ⛏️  EXTRACTING: {slug} ({seed_min}–{seed_max} TL) ---")

                        saved = _scrape_pages(
                            target_urls, extractor, scraped_urls, checkpoint,
                            save_incremental, district_slug=slug, label=f"[{slug}|{seed_min}-{seed_max}] "
                        )
                        total_saved += saved

                        # ── Bracket Success & Cool Down ──────────────────────
                        checkpoint["district_ranges_done"][slug].append([seed_min, seed_max])
                        checkpoint["discovered_urls"].pop(bracket_key, None)
                        _save_checkpoint(checkpoint)

                        rest_time = random.uniform(10.0, 18.0)
                        logger.info(f"☕ Bracket done! Resting {rest_time:.1f}s before next bracket...")
                        time.sleep(rest_time)

                    # All ranges for this district complete
                    district_done = True
                    checkpoint["completed_districts"].append(slug)
                    _save_checkpoint(checkpoint)

            except CaptchaDetectedException:
                wait = random.randint(45, 90)

                # Failsafe checkpoint flush
                checkpoint["scraped_urls"] = list(scraped_urls)
                _save_checkpoint(checkpoint)

                logger.warning(
                    f"🛑 CAPTCHA hit for district {slug}. "
                    f"Wiping identity. Waiting {wait}s..."
                )
                quit_driver(driver)
                driver = None
                delete_selenium_profile()
                time.sleep(wait)

            except Exception as e:
                logger.error(f"💥 Unexpected error in district ({slug}): {e}", exc_info=True)
                checkpoint["scraped_urls"] = list(scraped_urls)
                _save_checkpoint(checkpoint)
                quit_driver(driver)
                driver = None
                break

    quit_driver(driver)
    logger.info(f"\n🎉 Process Complete! Saved a total of {total_saved} new records.")

def main() -> None:
    parser = argparse.ArgumentParser(description="Modular Izmir Rent Scraper")
    parser.add_argument("--restart", action="store_true", help="Start over from scratch.")
    args = parser.parse_args()
    run(args)

if __name__ == "__main__":
    main()