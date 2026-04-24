import argparse
import json
import logging
import os
import time
import random
from seleniumbase import SB
import config
from scraper import CategoryScanner, DataExtractor, save_incremental, IZMIR_DISTRICT_SLUGS, IZMIR_SLUG_TO_DISTRICT, \
    warmup_session

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger(__name__)

_CHECKPOINT_DEFAULTS = {"scraped_urls": [], "completed_districts": [], "district_ranges_done": {},
                        "discovered_urls": {}}


def _load_checkpoint():
    if os.path.exists(config.CHECKPOINT_FILE):
        with open(config.CHECKPOINT_FILE, "r", encoding="utf-8") as f: return json.load(f)
    return {k: (v.copy() if isinstance(v, (list, dict)) else v) for k, v in _CHECKPOINT_DEFAULTS.items()}


def _save_checkpoint(data):
    os.makedirs(config.CHECKPOINT_DIR, exist_ok=True)
    with open(config.CHECKPOINT_FILE, "w", encoding="utf-8") as f: json.dump(data, f, indent=2)


def run(args):
    checkpoint = _load_checkpoint() if not args.restart else {k: v.copy() for k, v in _CHECKPOINT_DEFAULTS.items()}
    scraped_urls = set(checkpoint["scraped_urls"])

    with SB(uc=True, page_load_strategy="eager", user_data_dir=config.SELENIUM_PROFILE_DIR) as sb:
        warmup_session(sb.driver)

        for slug in IZMIR_DISTRICT_SLUGS:
            if slug in checkpoint["completed_districts"]:
                logger.info(f"⏭️  Skipping completed district: {slug}")
                continue

            scanner = CategoryScanner(sb.driver)
            extractor = DataExtractor(sb.driver)

            try:
                # Path Decision
                total = scanner.get_district_total(slug)
                if total == 0:
                    checkpoint["completed_districts"].append(slug)
                    _save_checkpoint(checkpoint)
                    continue

                logger.info(f"\n--- 🏙️  DISTRICT {slug.upper()} ({total} listings) ---")

                # URL Discovery
                if total <= config.MAX_LISTINGS_PER_QUERY:
                    target_urls = scanner.get_district_pages_no_price(slug, total)
                else:
                    logger.info(f"--- 🏙️  DISTRICT {slug.upper()} (>1000 listings) -> Splitting ---")
                    target_urls = []
                    for s_min, s_max in config.SEED_RANGES:
                        logger.info(f"\n--- 🔍 DISCOVERING: {slug} ({s_min}–{s_max} TL) ---")
                        bracket_urls = scanner.discover_bracket(slug, s_min, s_max)
                        target_urls.extend(bracket_urls)

                # Deduplicate
                target_urls = list(dict.fromkeys(target_urls))
                pending_urls = [u for u in target_urls if u not in scraped_urls]

                # Extraction Loop
                for idx, url in enumerate(pending_urls):
                    logger.info(f"      📄 [{slug}] Page {idx + 1}/{len(pending_urls)} ...")

                    recs = extractor.extract_from_url(url)

                    if recs:
                        for r in recs:
                            r["District"] = IZMIR_SLUG_TO_DISTRICT.get(slug, "Unknown")

                        saved_count = save_incremental(recs)
                        logger.info(f"      ✅ BATCH COMPLETE! Saved {saved_count} valid records.")

                    scraped_urls.add(url)
                    checkpoint["scraped_urls"] = list(scraped_urls)
                    _save_checkpoint(checkpoint)

                    # Cool down before moving to next page (Reduced for 6-7s total budget)
                    time.sleep(random.uniform(0.5, 1.5))

                checkpoint["completed_districts"].append(slug)
                _save_checkpoint(checkpoint)

            except Exception as e:
                logger.error(f"💥 Unexpected error in {slug}: {e}", exc_info=True)
                break

    logger.info("\n🎉 Process Complete! Check your CSV for results.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--restart", action="store_true")
    run(parser.parse_args())