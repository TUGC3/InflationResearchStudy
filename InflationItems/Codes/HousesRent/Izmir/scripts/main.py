"""
main.py — Izmir Rent Scraper (Modular Architecture)

Key behaviours
──────────────
• PHASE 1 (Discovery) is checkpointed URL-by-URL via the mutable `results`
  list that scraper.py fills in-place. If a CAPTCHA hits mid-discovery the
  partial URL list is saved immediately and never re-visited on the next run.

• PHASE 2 (Extraction) skips any URL that already appears in `scraped_urls`,
  so restarting after a crash never double-scrapes a page.

• District fallback: when discover_bracket signals None (price bracket is a
  single point with >1000 listings), main.py iterates districts one-by-one:
  discover that district's pages → immediately scrape them → save → next
  district. This way data is on disk after each district, not held in RAM
  until all 30 districts are done.

• Trust-score warm-up: on every new browser session the bot visits 2 real
  Sahibinden category pages before touching the guarded search endpoints.
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
    handle_browser_check, IZMIR_DISTRICT_SLUGS,
)

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
    # District fallback progress — persisted so a CAPTCHA mid-district-loop
    # doesn't restart from the first district.
    "district_fallback_done":     {},   # bracket_key → list[slug] already finished
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

_TRUST_WARMUP_PAGES = [
    "https://www.sahibinden.com/kiralik-daire/izmir-bornova",
    "https://www.sahibinden.com/kiralik-daire/izmir-karsiyaka",
    "https://www.sahibinden.com/kiralik-daire/izmir-buca",
    "https://www.sahibinden.com/kiralik-daire/izmir-konak",
    "https://www.sahibinden.com/kiralik-daire/izmir-bayrakli",
]

def warm_up_browser(driver) -> None:
    """
    Build trust on Sahibinden before hitting guarded search endpoints.
    Visits the homepage first (establishes session + cookies), then 2 random
    district listing pages with simulated scrolling.
    """
    logger.info("🔥 Building trust score on Sahibinden...")

    # Step 1: Homepage — establishes session cookies
    logger.info("    ↳ Visiting homepage to establish session...")
    try:
        driver.get("https://www.sahibinden.com/")
        time.sleep(random.uniform(2.0, 4.0))
        handle_browser_check(driver)
        time.sleep(random.uniform(1.0, 2.0))
    except CaptchaDetectedException:
        raise
    except Exception as e:
        logger.debug(f"Homepage warm-up issue: {e}")

    # Step 2: Two random category subpages with scrolling
    for page_url in random.sample(_TRUST_WARMUP_PAGES, 2):
        logger.info(f"    ↳ Visiting: {page_url}")
        try:
            driver.get(page_url)
            time.sleep(random.uniform(2.0, 3.5))
            handle_browser_check(driver)

            # Simulate human scrolling
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight * 0.4);")
            time.sleep(random.uniform(0.7, 1.2))
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight * 0.75);")
            time.sleep(random.uniform(0.7, 1.2))
            driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(random.uniform(1.0, 2.0))
        except CaptchaDetectedException:
            raise
        except Exception as e:
            logger.debug(f"Subpage warm-up skipped ({page_url}): {e}")

    logger.info("✅ Warm-up complete. Proceeding to price-range discovery.")


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
    label: str = "",
) -> int:
    """
    Scrape a list of page URLs, skipping already-done ones.
    Saves to CSV immediately after each page and checkpoints scraped_urls
    every 10 pages. Returns the number of records saved.
    """
    pending = [u for u in pages if u not in scraped_urls]
    already = len(pages) - len(pending)
    if already:
        logger.info(f"      ↳ {already} pages already scraped, skipping.")

    saved = 0
    for idx, url in enumerate(pending):
        logger.info(f"      📄 {label}Page {idx + 1}/{len(pending)} ...")
        records = extractor.extract_from_url(url)
        scraped_urls.add(url)

        if records:
            save_fn(records)
            saved += len(records)

        if (idx + 1) % 10 == 0:
            checkpoint["scraped_urls"] = list(scraped_urls)
            _save_checkpoint(checkpoint)

        time.sleep(random.uniform(2.0, 4.0))

    # Final checkpoint flush
    checkpoint["scraped_urls"] = list(scraped_urls)
    _save_checkpoint(checkpoint)
    return saved


def _run_district_fallback(
    seed_min: int,
    seed_max: int,
    bracket_key: str,
    scanner: CategoryScanner,
    extractor: DataExtractor,
    scraped_urls: set,
    checkpoint: dict,
) -> int:
    """
    District-level fallback: for each Izmir district, discover its pages for
    this price range then immediately scrape them before moving to the next.

    Progress is checkpointed per district so a CAPTCHA mid-loop resumes from
    the next unfinished district rather than starting over.

    Returns total records saved.
    """
    done_slugs: list[str] = checkpoint.setdefault(
        "district_fallback_done", {}
    ).get(bracket_key, [])

    total_saved = 0

    for slug in IZMIR_DISTRICT_SLUGS:
        if slug in done_slugs:
            logger.info(f"   ⏭️  District {slug} already done. Skipping.")
            continue

        logger.info(f"\n   🏙️  District fallback — {slug} ({seed_min}–{seed_max} TL)...")

        # ── Discover this district's pages ────────────────────────────────
        try:
            pages = scanner.get_district_pages(slug, seed_min, seed_max)
        except CaptchaDetectedException:
            raise   # Let main loop handle identity reset
        except Exception as e:
            logger.warning(f"   ⚠️  Error discovering {slug}: {e}. Skipping.")
            continue

        if not pages:
            logger.info(f"   📭 {slug}: 0 listings. Skipping.")
            # Still mark as done so we don't re-check on resume
            done_slugs.append(slug)
            checkpoint["district_fallback_done"][bracket_key] = done_slugs
            _save_checkpoint(checkpoint)
            continue

        logger.info(f"   ✓  {slug}: {len(pages)} pages to scrape.")

        # ── Immediately scrape this district's pages ──────────────────────
        try:
            saved = _scrape_pages(
                pages, extractor, scraped_urls, checkpoint,
                save_incremental, label=f"[{slug}] "
            )
            total_saved += saved
            logger.info(f"   💾 {slug}: saved {saved} records.")
        except CaptchaDetectedException:
            raise   # Let main loop handle identity reset

        # Mark district as fully done
        done_slugs.append(slug)
        checkpoint["district_fallback_done"][bracket_key] = done_slugs
        _save_checkpoint(checkpoint)

        time.sleep(random.uniform(1.0, 3.0))

    # Clean up fallback state for this bracket
    checkpoint["district_fallback_done"].pop(bracket_key, None)
    _save_checkpoint(checkpoint)

    return total_saved

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

                # Check if we're mid-way through a district fallback from a
                # previous run (CAPTCHA hit during district loop).
                in_district_fallback = bracket_key in checkpoint.get("district_fallback_done", {})

                if in_district_fallback:
                    logger.info(
                        f"\n--- 🏙️  RESUMING DISTRICT FALLBACK ({seed_min}–{seed_max} TL) ---"
                    )
                    saved = _run_district_fallback(
                        seed_min, seed_max, bracket_key,
                        scanner, extractor, scraped_urls, checkpoint,
                    )
                    total_saved += saved

                elif bracket_key in fully_discovered:
                    # Normal path: discovery already done, load URLs from checkpoint.
                    logger.info(
                        f"\n--- ⏭️  PHASE 1 SKIPPED ({seed_min}–{seed_max} TL): "
                        f"URLs loaded from checkpoint ---"
                    )
                    target_urls: list[str] = checkpoint["discovered_urls"][bracket_key]

                    # ── PHASE 2: EXTRACTION (normal path) ────────────────────
                    saved = _scrape_pages(
                        target_urls, extractor, scraped_urls, checkpoint,
                        save_incremental,
                    )
                    total_saved += saved

                else:
                    logger.info(
                        f"\n--- 🔍 PHASE 1: DISCOVERING URLS ({seed_min}–{seed_max} TL) ---"
                    )

                    results: list[str] = list(
                        checkpoint.get("discovered_urls", {}).get(bracket_key, [])
                    )
                    if results:
                        logger.info(f"   ↳ Resuming discovery — {len(results)} URLs already saved.")

                    try:
                        outcome = scanner.discover_bracket(seed_min, seed_max, results=results)
                    except CaptchaDetectedException:
                        logger.warning(
                            f"🛑 CAPTCHA during Phase 1! Saving {len(results)} partial URLs..."
                        )
                        checkpoint["discovered_urls"][bracket_key] = list(dict.fromkeys(results))
                        _save_checkpoint(checkpoint)
                        raise

                    if outcome is None:
                        # ── District fallback path ────────────────────────────
                        # scraper.py signalled that this bracket needs per-district
                        # discover+scrape. Initialise the fallback tracker and run.
                        logger.info(
                            f"\n--- 🏙️  DISTRICT FALLBACK ({seed_min}–{seed_max} TL) ---"
                        )
                        checkpoint.setdefault("district_fallback_done", {})[bracket_key] = []
                        _save_checkpoint(checkpoint)

                        saved = _run_district_fallback(
                            seed_min, seed_max, bracket_key,
                            scanner, extractor, scraped_urls, checkpoint,
                        )
                        total_saved += saved

                    else:
                        # ── Normal path ───────────────────────────────────────
                        target_urls = list(dict.fromkeys(results))
                        checkpoint["discovered_urls"][bracket_key]      = target_urls
                        checkpoint["fully_discovered_brackets"].append(bracket_key)
                        _save_checkpoint(checkpoint)
                        logger.info(f"   ✅ Discovery complete: {len(target_urls)} unique URLs.")

                        # ── PHASE 2: EXTRACTION ───────────────────────────────
                        logger.info(f"\n--- ⛏️  PHASE 2: EXTRACTING DATA ---")
                        saved = _scrape_pages(
                            target_urls, extractor, scraped_urls, checkpoint,
                            save_incremental,
                        )
                        total_saved += saved

                # ── Bracket success ───────────────────────────────────────────
                bracket_done = True
                captcha_hits = 0

                completed_brackets.add((seed_min, seed_max))
                checkpoint["completed_brackets"]  = [list(b) for b in completed_brackets]
                checkpoint["scraped_urls"]         = list(scraped_urls)
                checkpoint["discovered_urls"].pop(bracket_key, None)
                checkpoint.get("district_fallback_done", {}).pop(bracket_key, None)
                if bracket_key in checkpoint.get("fully_discovered_brackets", []):
                    checkpoint["fully_discovered_brackets"].remove(bracket_key)
                _save_checkpoint(checkpoint)

                n = saved if "saved" in dir() else 0
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
                wait = random.randint(45, 90) * captcha_hits

                if in_memory_records:
                    logger.warning(f"   💾 Flushing {len(in_memory_records)} in-memory records...")
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
                break

    quit_driver(driver)
    logger.info(f"\n🎉 Process Complete! Saved {total_saved} new records.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Modular Izmir Rent Scraper")
    parser.add_argument("--restart", action="store_true", help="Start over from scratch.")
    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    main()