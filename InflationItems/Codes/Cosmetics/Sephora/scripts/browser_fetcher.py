"""
Sephora Browser-Based Product Fetcher
=====================================

Scraper backend for Sephora Türkiye. Drives a real Chrome browser
through ``undetected-chromedriver`` so Akamai Bot Manager's JS
challenge runs naturally and the resulting ``_abck`` cookie keeps the
session trusted for the rest of the run.

Public Interface
----------------
setup_driver(headless=False, profile_dir=None) -> uc.Chrome
    Launch a stealth Chrome driver with a persistent profile directory.

fetch_products_for_category_browser(category, driver, *, delay=<cfg>, page_limit=0) -> list[dict]
    Paginate a Sephora category URL with Selenium and return
    normalised product dicts.

Data Extraction
---------------
Each product tile on a category page carries a ``data-tcproduct``
attribute whose value is an HTML-escaped JSON blob with the full
product record (id / sku / name / brand / breadcrumb / prices /
currency / url / stock).  The ``_extract_tiles`` + ``_normalise``
helpers turn these blobs into the flat schema used downstream by the
CSV writer and inflation calculator.

Akamai JS Challenge
-------------------
Akamai injects a ~500-byte JS challenge page when it can't verify the
client.  Real Chrome executes that JS, posts ``sensor_data`` back to
Akamai, and receives a valid ``_abck`` cookie.  The scraper waits for
product tiles (``data-tcproduct``) to appear; if they don't within
:data:`config.BROWSER_MAX_WAIT_TILES` seconds the user is prompted to
solve any CAPTCHA in the Chrome window.  Once resolved, the scraper
resumes automatically and the cookie persists through the
``user-data-dir`` so subsequent category pages load without prompting.

macOS Apple Silicon Note
------------------------
``undetected-chromedriver`` patches the chromedriver binary at runtime
to strip ``cdc_*`` identifiers.  On Apple Silicon that invalidates the
Mach-O signature and the OS kills the process with SIGKILL (``-9``).
:func:`_ensure_patched_and_signed` pre-patches + re-signs the bundled
binary so ``uc.Chrome`` finds it already patched and skips its own
unsigned patch step.  This matches the approach used by the
IstanbulAvrupa (Sahibinden) scraper in this repo.
"""

from __future__ import annotations

import html as _html
import json
import logging
import os
import random
import re
import subprocess
import threading
import time
from typing import Optional

import undetected_chromedriver as uc  # type: ignore
from lxml import html as lxml_html

import config

logger = logging.getLogger(__name__)

# One CAPTCHA prompt at a time (future-proof if workers > 1).
_captcha_lock = threading.Lock()

# Regex used to cap the maximum page number when the first page renders
# a full pagination control.  Lets us short-circuit the page loop when
# the category is exhausted.
_PAGE_RE = re.compile(r"[?&]page=(\d+)")


# ── Tile parsing helpers ────────────────────────────────────────────────────


def _parse_tc_product(raw: str) -> dict:
    """Decode the ``data-tcproduct`` attribute into a dict.

    The raw attribute is HTML-entity-encoded JSON.  Returns ``{}`` on
    decoding errors so the caller can skip malformed tiles.
    """
    if not raw:
        return {}
    try:
        return json.loads(_html.unescape(raw))
    except (json.JSONDecodeError, ValueError):
        return {}


def _to_float(value) -> float:
    """Best-effort float parsing.  Returns ``0.0`` on failure."""
    if value in (None, "", "null"):
        return 0.0
    try:
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return 0.0


def _normalise(tile_data: dict, category_slug: str) -> Optional[dict]:
    """Transform a raw ``data-tcproduct`` dict into the output schema.

    Returns ``None`` when the tile lacks a product identifier (malformed
    or a rendered placeholder).
    """
    pid = (tile_data.get("product_pid") or "").strip()
    if not pid:
        return None

    regular_price = _to_float(
        tile_data.get("product_old_price_ati") or tile_data.get("product_price_ati")
    )
    sale_price = _to_float(
        tile_data.get("product_price_ati") or tile_data.get("product_old_price_ati")
    )
    # Coalesce so downstream inflation maths never divides by zero.
    if regular_price <= 0:
        regular_price = sale_price

    discount_pct = 0.0
    if regular_price > 0 and sale_price < regular_price:
        discount_pct = round((1 - sale_price / regular_price) * 100, 2)

    in_stock_flag = str(tile_data.get("product_instock") or "").strip().lower() == "y"
    currency = (tile_data.get("product_currency") or "try").upper()

    return {
        "id":            pid.upper(),
        "sku":           str(tile_data.get("product_sku") or "").strip(),
        "name":          (tile_data.get("product_pid_name") or "").strip(),
        "brand":         (tile_data.get("product_trademark") or "").strip(),
        "category":      (tile_data.get("product_breadcrumb_label") or "").strip(),
        "category_id":   category_slug,
        "regular_price": round(regular_price, 2),
        "sale_price":    round(sale_price, 2),
        "discount_pct":  discount_pct,
        "currency":      currency,
        "in_stock":      in_stock_flag,
        "url":           (tile_data.get("product_url_page") or "").strip(),
    }


def _extract_tiles(page_html: str) -> list[dict]:
    """Extract all ``data-tcproduct`` payloads from a rendered HTML page."""
    if not page_html or "data-tcproduct" not in page_html:
        return []
    tree = lxml_html.fromstring(page_html)
    return [_parse_tc_product(el.get("data-tcproduct", ""))
            for el in tree.xpath('//*[@data-tcproduct]')]


def _max_page_number(page_html: str) -> int:
    """Return the highest ``page=N`` number referenced on this page.

    Used as a safety bound so we stop paginating once Sephora's
    paginator has no higher page to offer.
    """
    if not page_html:
        return 1
    matches = _PAGE_RE.findall(page_html)
    if not matches:
        return 1
    return max(int(m) for m in matches)


# ── Driver factory ──────────────────────────────────────────────────────────


def _ensure_patched_and_signed(executable_path: str) -> None:
    """Pre-patch and re-sign chromedriver for macOS Apple Silicon.

    ``undetected-chromedriver`` rewrites the binary at runtime to strip
    ``cdc_*`` JavaScript identifiers Selenium stealth checks look for.
    That invalidates the Mach-O signature on Apple Silicon so macOS
    kills the process with SIGKILL.  Pre-patching + ad-hoc codesign
    sidesteps that: uc sees an already-patched binary, skips its own
    patch step, and the valid signature is preserved.
    """
    if not os.path.exists(executable_path):
        logger.warning(
            "CHROMEDRIVER_PATH does not exist: %s – undetected-chromedriver "
            "will attempt to download a compatible driver automatically.",
            executable_path,
        )
        return

    try:
        from undetected_chromedriver.patcher import Patcher  # type: ignore
    except Exception as exc:  # noqa: BLE001
        logger.warning("Cannot import uc.Patcher (%s) – uc will self-patch.", exc)
        return

    try:
        patcher = Patcher(executable_path=executable_path)
        if not patcher.is_binary_patched():
            logger.info("Pre-patching chromedriver binary…")
            patcher.patch_exe()
            result = subprocess.run(
                ["codesign", "--force", "-s", "-", executable_path],
                capture_output=True,
            )
            if result.returncode == 0:
                logger.info("chromedriver re-signed successfully.")
            else:
                logger.warning("codesign failed: %s", result.stderr.decode())
        else:
            logger.debug("chromedriver already patched — skipping re-patch.")
    except Exception as exc:  # noqa: BLE001
        logger.warning("Patcher step failed (%s) – uc.Chrome will handle patching.", exc)


def setup_driver(
    headless: bool = config.BROWSER_HEADLESS,
    profile_dir: Optional[str] = None,
) -> uc.Chrome:
    """Launch a stealth Chrome driver for Sephora.

    Args
    ----
    headless : bool
        Run Chrome headless.  Akamai detects headless mode more easily,
        so the default (:data:`config.BROWSER_HEADLESS`) is ``False``.
    profile_dir : str, optional
        Directory that persists cookies / Akamai ``_abck`` state across
        runs.  Defaults to :data:`config.SELENIUM_PROFILE_DIR`.
    """
    profile_dir = profile_dir or config.SELENIUM_PROFILE_DIR
    os.makedirs(profile_dir, exist_ok=True)

    driver_path = config.CHROMEDRIVER_PATH
    _ensure_patched_and_signed(driver_path)

    options = uc.ChromeOptions()
    options.add_argument(f"--user-data-dir={profile_dir}")
    options.add_argument("--lang=tr-TR")
    options.add_argument("--window-size=1400,900")
    if headless:
        options.add_argument("--headless=new")

    uc_kwargs: dict = {
        "options": options,
        "version_main": config.BROWSER_VERSION_MAIN,
    }
    if os.path.exists(driver_path):
        uc_kwargs["driver_executable_path"] = driver_path

    logger.info(
        "Launching Chrome (headless=%s, profile=%s)…",
        headless, profile_dir,
    )
    driver = uc.Chrome(**uc_kwargs)
    driver.set_page_load_timeout(60)
    return driver


# ── Page-readiness & CAPTCHA handling ───────────────────────────────────────


def _current_html(driver: uc.Chrome) -> str:
    """Return the current fully-rendered DOM, falling back to page_source."""
    try:
        return driver.execute_script("return document.documentElement.outerHTML;")
    except Exception:  # noqa: BLE001
        return driver.page_source or ""


def _is_bot_challenge(body: str) -> bool:
    """Return True if the body looks like an Akamai challenge / denied page.

    Heuristics (any-of):
      * body shorter than 5 KB (real pages are 100 KB+)
      * contains the Akamai challenge container id
      * contains "Access Denied"
    """
    if not body:
        return True
    if len(body) < 5_000:
        return True
    if "sec-if-cpt-container" in body:
        return True
    if "Access Denied" in body:
        return True
    return False


def _prompt_captcha(driver: uc.Chrome) -> str:
    """Block in the foreground while the user resolves an Akamai CAPTCHA.

    Returns the DOM HTML once product tiles are visible or a legitimate
    empty-category page is shown.
    """
    with _captcha_lock:
        while True:
            print("\n" + "=" * 62)
            print("⚠️  Akamai bot-challenge detected on Sephora.")
            print(f"   Current URL: {driver.current_url}")
            print("   1. Look at the Chrome window that just opened.")
            print("   2. Solve any CAPTCHA / 'Press & Hold' puzzle shown.")
            print("   3. Wait until you can see product tiles on the page.")
            print("=" * 62)
            input("   ▶ Press ENTER here once the products are visible… ")
            time.sleep(2)
            html = _current_html(driver)
            if "data-tcproduct" in html or not _is_bot_challenge(html):
                return html
            print(f"   ⚠  Still looks blocked (size={len(html)}). Retry or navigate manually…")


def _wait_for_tiles(driver: uc.Chrome, max_wait: int = config.BROWSER_MAX_WAIT_TILES) -> str:
    """Block until the page renders product tiles or the user resolves a CAPTCHA.

    Returns the current page HTML once one of the following becomes true:

      * ``data-tcproduct`` is present (tiles rendered), or
      * the page is a legitimate empty-category page (full layout,
        no bot-challenge markers), or
      * the user manually confirms the page is ready after solving a
        CAPTCHA shown in the Chrome window.
    """
    deadline = time.time() + max_wait
    html = ""
    while time.time() < deadline:
        html = _current_html(driver)
        if "data-tcproduct" in html:
            return html
        if not _is_bot_challenge(html):
            # Full layout but no tiles → legitimate empty category.
            return html
        time.sleep(1.0)

    return _prompt_captcha(driver)


# ── Public API ──────────────────────────────────────────────────────────────


def fetch_products_for_category_browser(
    category: dict,
    driver: uc.Chrome,
    delay: float = config.BROWSER_PAGE_LOAD_DELAY,
    page_limit: int = 0,
) -> list[dict]:
    """Paginate a Sephora category URL with Selenium and return
    normalised product records.

    Mirrors :func:`product_fetcher.fetch_products_for_category` so the
    ``main.py`` orchestrator can treat either backend uniformly.

    Args
    ----
    category : dict
        Category dict produced by
        :func:`category_fetcher.fetch_categories` (needs ``url`` and
        ``slug``).
    driver : uc.Chrome
        An active driver created by :func:`setup_driver`.  Reuse one
        driver across categories – the Akamai ``_abck`` cookie lives
        on the session.
    delay : float
        Base per-page sleep in seconds (jittered on every page).
    page_limit : int
        Maximum pages per category (``0`` = unlimited).
    """
    category_url = category["url"]
    category_slug = category["slug"]

    all_products: list[dict] = []
    seen_ids: set[str] = set()
    page = 1
    known_max_page: Optional[int] = None

    while True:
        if page_limit and page > page_limit:
            break
        if known_max_page is not None and page > known_max_page:
            break

        url = category_url if page == 1 else f"{category_url}?page={page}"
        try:
            driver.get(url)
        except Exception as exc:  # noqa: BLE001
            logger.warning("driver.get failed for %s: %s – retrying once.", url, exc)
            time.sleep(delay)
            try:
                driver.get(url)
            except Exception as exc2:  # noqa: BLE001
                logger.error("driver.get failed twice: %s – stopping category.", exc2)
                break

        body = _wait_for_tiles(driver)
        tiles = _extract_tiles(body)

        if not tiles:
            logger.debug("  page %d returned no tiles – stopping.", page)
            break

        if page == 1:
            known_max_page = _max_page_number(body)
            logger.info(
                "  Category '%s' — detected %d page(s) of products",
                category.get("name", category_slug), known_max_page,
            )

        new_on_page = 0
        for tile in tiles:
            product = _normalise(tile, category_slug)
            if product is None:
                continue
            pid = product["id"]
            if pid in seen_ids:
                continue
            seen_ids.add(pid)
            all_products.append(product)
            new_on_page += 1

        if page % 5 == 0 or page == 1:
            logger.info(
                "  page %2d: +%d products (total so far: %d)",
                page, new_on_page, len(all_products),
            )
        else:
            logger.debug(
                "  page %2d: +%d products (total so far: %d)",
                page, new_on_page, len(all_products),
            )

        page += 1
        time.sleep(delay * random.uniform(0.7, 1.4))

    return all_products


def close_driver(driver: uc.Chrome) -> None:
    """Safely close the Chrome driver, swallowing shutdown exceptions."""
    if driver is None:
        return
    try:
        driver.quit()
    except Exception as exc:  # noqa: BLE001
        logger.debug("driver.quit() raised: %s", exc)
