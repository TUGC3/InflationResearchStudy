"""
main.py — Izmir Rent Scraper (Modular Architecture)

Key behaviours
──────────────
• PHASE 1 (Discovery) is checkpointed URL-by-URL via the mutable `results`
  list that scraper.py fills in-place. If a CAPTCHA hits mid-discovery the
  partial URL list is saved immediately and never re-visited on the next run.

• PHASE 2 (Extraction) skips any URL that already appears in `scraped_urls`,
  so restarting after a crash never double-scrapes a page.

• Trust-score warm-up: on every new browser session the bot visits 2 pages
  on Sahibinden itself before touching the guarded search endpoints.
"""

import argparse
import json
import logging
import os
import time
import random

import config
from scraper import setup_driver, CategoryScanner, DataExtractor, CaptchaDetectedException, delete_selenium_profile, save_incremental, handle_browser_check

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── Checkpoint helpers ────────────────────────────────────────────────────────

_CHECKPOINT_DEFAULTS: dict = {
    "scraped_urls":               [],   # URLs whose data is already in the CSV
    "completed_brackets":         [],   # (min, max) brackets fully done
    "discovered_urls":            {},   # bracket_key → list[url]
    "fully_discovered_brackets":  [],   # bracket_keys where Phase 1 is 100% done
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

def quit_driver(driver) -> None:
    """Safely closes the browser to prevent zombie processes."""
    if driver:
        try:
            driver.quit()
        except Exception:
            pass

# ── Trust-score warm-up ───────────────────────────────────────────────────────

# Real Sahibinden category pages — build cookie history on the actual target
# domain before any bot-guarded price-range query is fired.
_TRUST_WARMUP_PAGES = [
    "https://www.sahibinden.com/",
    "https://www.sahibinden.com/kiralik-daire",
    "https://www.sahibinden.com/kiralik/izmir",
    "https://www.sahibinden.com/kiralik-daire/izmir-bornova",
    "https://www.sahibinden.com/kiralik-daire/izmir-karsiyaka",
    "https://www.sahibinden.com/kiralik-daire/izmir-konak",
]


def warm_up_browser(driver) -> None:
    warmup_sites = [
        "https://www.sahibinden.com/kiralik-daire/izmir-bornova",
        "https://www.sahibinden.com/kiralik-daire/izmir-karsiyaka",
        "https://www.sahibinden.com/kiralik-daire/izmir-buca"
    ]

    logger.info("🔥 Building trust score on Sahibinden...")

    # --- STEP 1: Visit Homepage First ---
    logger.info("    ↳ Visiting homepage first to establish session and cookies...")
    try:
        driver.get("https://www.sahibinden.com/")
        time.sleep(random.uniform(2.0, 4.0))

        # Catch the initial front-door browser check
        handle_browser_check(driver)
        time.sleep(random.uniform(1.0, 3.0))
    except CaptchaDetectedException:
        raise
    except Exception as e:
        logger.debug(f"Homepage warm-up encountered an issue: {e}")

    # --- STEP 2: Visit Random Subpages ---
    # Pick 2 random pages to visit to build history
    for site in random.sample(warmup_sites, 2):
        logger.info(f"    ↳ Visiting subpage: {site}")
        try:
            driver.get(site)
            time.sleep(random.uniform(1.0, 2.0))

            # Check for security screens again just in case
            handle_browser_check(driver)

            time.sleep(random.uniform(2.0, 4.0))
        except CaptchaDetectedException:
            # If it gets hard-blocked, trigger the rescue protocol
            raise
        except Exception as e:
            logger.debug(f"Subpage warm-up skipped due to error: {e}")

    logger.info("✅ Warm-up complete. Proceeding to price-range discovery.")

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

    scraped_urls: set[str]         = set(checkpoint["scraped_urls"])
    completed_brackets: set[tuple] = {tuple(b) for b in checkpoint["completed_brackets"]}

    total_saved = 0
    driver      = None

    for seed_min, seed_max in config.SEED_RANGES:

        if (seed_min, seed_max) in completed_brackets:
            logger.info(f"⏭️  Skipping completed bracket: {seed_min}–{seed_max} TL")
            continue

        bracket_key  = f"{seed_min}_{seed_max}"
        bracket_done = False
        captcha_hits = 0

        while not bracket_done:

            if driver is None:
                driver = setup_driver()
                warm_up_browser(driver)

            scanner   = CategoryScanner(driver)
            extractor = DataExtractor(driver)
            in_memory_records: list[dict] = []

            try:
                # ── PHASE 1: DISCOVERY ────────────────────────────────────────
                fully_discovered = checkpoint.get("fully_discovered_brackets", [])

                if bracket_key in fully_discovered:
                    logger.info(
                        f"\n--- ⏭️  PHASE 1 SKIPPED ({seed_min}–{seed_max} TL): "
                        f"URLs loaded from checkpoint ---"
                    )
                    target_urls: list[str] = checkpoint["discovered_urls"][bracket_key]

                else:
                    logger.info(
                        f"\n--- 🔍 PHASE 1: DISCOVERING URLS ({seed_min}–{seed_max} TL) ---"
                    )

                    # Resume from partial discovery if a previous CAPTCHA interrupted us.
                    # `results` is passed by reference — every new URL is appended live,
                    # so even a mid-discovery exception leaves us with what was found.
                    results: list[str] = list(
                        checkpoint.get("discovered_urls", {}).get(bracket_key, [])
                    )
                    if results:
                        logger.info(f"   ↳ Resuming discovery — {len(results)} URLs already saved.")

                    try:
                        scanner.discover_bracket(seed_min, seed_max, results=results)
                    except CaptchaDetectedException:
                        logger.warning(
                            f"🛑 CAPTCHA during Phase 1! Saving {len(results)} partial URLs..."
                        )
                        checkpoint["discovered_urls"][bracket_key] = list(dict.fromkeys(results))
                        _save_checkpoint(checkpoint)
                        raise   # bubble up to the CAPTCHA handler below

                    # Mark discovery as fully complete for this bracket
                    target_urls = list(dict.fromkeys(results))  # dedup, preserve order
                    checkpoint["discovered_urls"][bracket_key]      = target_urls
                    checkpoint["fully_discovered_brackets"].append(bracket_key)
                    _save_checkpoint(checkpoint)
                    logger.info(f"   ✅ Discovery complete: {len(target_urls)} unique URLs.")

                # ── PHASE 2: EXTRACTION ───────────────────────────────────────
                # Skip URLs whose data is already saved — safe against any crash.
                pending_urls = [u for u in target_urls if u not in scraped_urls]
                already_done = len(target_urls) - len(pending_urls)
                logger.info(
                    f"\n--- ⛏️  PHASE 2: EXTRACTING DATA "
                    f"({len(pending_urls)} pending, {already_done} already done) ---"
                )

                for idx, url in enumerate(pending_urls):
                    logger.info(f"   Page {idx + 1}/{len(pending_urls)} ...")

                    records = extractor.extract_from_url(url)

                    # Mark as scraped regardless of result — even empty pages are done.
                    scraped_urls.add(url)

                    if records:
                        in_memory_records.extend(records)

                    # Persist scraped_urls to disk every 10 pages
                    # so a mid-bracket crash loses at most 10 pages of progress.
                    if (idx + 1) % 10 == 0:
                        checkpoint["scraped_urls"] = list(scraped_urls)
                        _save_checkpoint(checkpoint)

                    # Polite delay between pages
                    time.sleep(random.uniform(2.0, 4.0))

                # ── Bracket success ───────────────────────────────────────────
                bracket_done = True
                captcha_hits = 0

                if in_memory_records:
                    save_incremental(in_memory_records)
                    total_saved += len(in_memory_records)

                completed_brackets.add((seed_min, seed_max))
                checkpoint["completed_brackets"]  = [list(b) for b in completed_brackets]
                checkpoint["scraped_urls"]         = list(scraped_urls)
                checkpoint["discovered_urls"].pop(bracket_key, None)
                if bracket_key in checkpoint["fully_discovered_brackets"]:
                    checkpoint["fully_discovered_brackets"].remove(bracket_key)
                _save_checkpoint(checkpoint)

                # Dynamic sleep — longer rest after heavier work
                n = len(in_memory_records)
                if n < 100:
                    sleep_t = random.uniform(1.0, 3.0)
                elif n < 500:
                    sleep_t = random.uniform(5.0, 10.0)
                else:
                    sleep_t = random.uniform(12.0, 20.0)

                logger.info(
                    f"☕ Bracket done! Saved {n} records. "
                    f"Resting {sleep_t:.1f}s before next bracket..."
                )
                time.sleep(sleep_t)

            except CaptchaDetectedException:
                captcha_hits += 1
                wait = random.randint(45, 90) * captcha_hits  # escalating backoff

                if in_memory_records:
                    logger.warning(
                        f"   💾 Flushing {len(in_memory_records)} in-memory records before reset..."
                    )
                    save_incremental(in_memory_records)
                    total_saved += len(in_memory_records)

                checkpoint["scraped_urls"] = list(scraped_urls)
                _save_checkpoint(checkpoint)

                logger.warning(
                    f"🛑 CAPTCHA hit #{captcha_hits} for bracket {seed_min}–{seed_max}. "
                    f"Wiping identity. Waiting {wait}s..."
                )
                quit_driver(driver)
                driver = None
                delete_selenium_profile()
                time.sleep(wait)

            except Exception as e:
                logger.error(
                    f"💥 Unexpected error in bracket ({seed_min}–{seed_max}): {e}",
                    exc_info=True,
                )
                if in_memory_records:
                    save_incremental(in_memory_records)
                    total_saved += len(in_memory_records)
                checkpoint["scraped_urls"] = list(scraped_urls)
                _save_checkpoint(checkpoint)
                quit_driver(driver)
                driver = None
                break  # Move to next bracket — don't retry unknown errors

    quit_driver(driver)
    logger.info(f"\n🎉 Process Complete! Saved {total_saved} new records.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Modular Izmir Rent Scraper")
    parser.add_argument("--restart", action="store_true", help="Start over from scratch.")
    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    main()