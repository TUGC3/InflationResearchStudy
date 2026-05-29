"""
dermomarket_scraper.py — Dermomarket Günlük Ürün Fiyat Scraper'ı

Selenium + headless Chrome kullanır (site ürünleri JavaScript ile yükler).
Sayfa bazlı pagination: ?pg=N

Gereksinimler:
    pip install selenium webdriver-manager beautifulsoup4 lxml

Kullanım:
    python dermomarket_scraper.py

Çıktı:
    dermomarket_YYYY-MM-DD.csv  →  item_name | price | category | date
"""

import csv
import logging
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path

# ── Repo-relative output path ─────────────────────────────────────────────────
# Bu dosya: InflationItems/Codes/Cosmetics/Dermomarket/dermomarket_scraper.py
# Veri:     InflationItems/Datas/Cosmetics/Dermomarket/
REPO_ROOT = Path(__file__).resolve().parents[4]
OUT_DIR   = REPO_ROOT / "InflationItems" / "Datas" / "Cosmetics" / "Dermomarket"
OUT_DIR.mkdir(parents=True, exist_ok=True)

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

# ── Konfigürasyon ─────────────────────────────────────────────────────────────

BASE_URL = "https://www.dermomarket.com"

CATEGORIES = [
    {"name": "Ağız Bakımı",          "slug": "agiz-bakimi"},
    {"name": "Anne Bebek",           "slug": "anne-bebek"},
    {"name": "Cilt Bakımı",          "slug": "cilt-bakimi"},
    {"name": "Ev ve Yaşam",          "slug": "ev-ve-yasam"},
    {"name": "Güneş Bakımı",         "slug": "gunes-bakimi"},
    {"name": "Kişisel Bakım",        "slug": "kisisel-bakim"},
    {"name": "Makyaj",               "slug": "makyaj"},
    {"name": "Parfüm ve Deodorant",  "slug": "parfum-ve-deodorant"},
    {"name": "Saç Bakımı",           "slug": "sac-bakimi"},
    {"name": "Vitamin ve Sağlık",    "slug": "vitamin-ve-saglik"},
]

PAGE_LOAD_TIMEOUT = 30
PRODUCT_WAIT      = 15
POST_LOAD_SLEEP   = 1.5
PAGE_DELAY        = 1.0    # Sayfa geçişleri arası bekleme

# Fiyat regex: "633,25 TL" veya "1.993,25 TL"
_PRICE_RE = re.compile(r"([\d]{1,3}(?:\.[\d]{3})*,\d{2})\s*TL")

# ── Logging ───────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── CSV dosya koruması ────────────────────────────────────────────────────────

def _check_existing(csv_path: str):
    """Bugünün CSV'si zaten varsa çalıştırmayı durdur."""
    if os.path.exists(csv_path):
        logger.error(
            f"⛔ DURDURULDU: '{csv_path}' zaten mevcut!\n"
            f"   Bugün ikinci kez çalıştırıyorsunuz. Tekrar veri eklenmedi."
        )
        sys.exit(0)

# ── Chrome Driver ─────────────────────────────────────────────────────────────

def create_driver() -> webdriver.Chrome:
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    # Görselleri devre dışı bırak — mobil veri tasarrufu + hızlı yükleme
    options.add_argument("--blink-settings=imagesEnabled=false")
    options.add_experimental_option("prefs", {
        "profile.managed_default_content_settings.images": 2,
    })
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--lang=tr-TR")

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT)
    return driver

# ── Fiyat parse ───────────────────────────────────────────────────────────────

def parse_price(text: str) -> float | None:
    """'1.993,25 TL' → 1993.25 float. Bulamazsa None."""
    matches = _PRICE_RE.findall(text)
    if not matches:
        return None
    try:
        # Son eşleşmeyi al — indirimli fiyat varsa o sonuncu
        value = float(matches[-1].replace(".", "").replace(",", "."))
        return value if value > 0 else None
    except ValueError:
        return None

# ── Sayfa parse ───────────────────────────────────────────────────────────────

def parse_page(html: str, category_name: str, date_str: str) -> list[dict]:
    """
    Render edilmiş HTML'den ürünleri çıkarır.

    Ürün kartı yapısı (DevTools'tan):
        div.product-item
          └─ a[href][title]  → ürün adı (title attribute)
          └─ fiyat text      → "633,25 TL" veya "Sepette %15 indirimli fiyat 633,25 TL"
    """
    soup = BeautifulSoup(html, "lxml")
    products = []
    seen_names = set()

    # Ürün kartları: product-item class'lı div'ler
    cards = soup.select("div.product-item")
    if not cards:
        # Fallback: product-detail-card data-selector'ü
        cards = soup.select("[data-selector='.product-detail-card']")

    for card in cards:
        # Ürün adı: a[title] veya kart içindeki text
        link = card.select_one("a[title]")
        if not link:
            continue

        name = link.get("title", "").strip()
        if not name or name in seen_names:
            continue

        # Fiyat: kart içindeki tüm text'ten parse et
        card_text = card.get_text(separator=" ", strip=True)
        price = parse_price(card_text)

        if price is None:
            continue

        seen_names.add(name)
        products.append({
            "product_name": name,
            "price":        price,
        })

    return products

# ── Toplam sayfa sayısını bul ─────────────────────────────────────────────────

def get_total_pages(html: str) -> int:
    """
    Pagination'dan toplam sayfa sayısını çıkarır.
    'Toplam 4050 ürün bulunmaktadır.' text'inden veya
    son sayfa numarasından alınır.
    """
    soup = BeautifulSoup(html, "lxml")

    # Yöntem 1: Pagination linklerinden son sayfa numarasını bul
    page_links = soup.select("a[href*='pg=']")
    max_page = 1
    for link in page_links:
        href = link.get("href", "")
        match = re.search(r"pg=(\d+)", href)
        if match:
            pg = int(match.group(1))
            if pg > max_page:
                max_page = pg

    # Yöntem 2: Sayfa numarası butonlarından
    if max_page == 1:
        page_nums = soup.select("ul.pagination li a, .pager a, nav a")
        for el in page_nums:
            text = el.get_text(strip=True)
            if text.isdigit():
                pg = int(text)
                if pg > max_page:
                    max_page = pg

    return max_page

# ── Kategori scraper ──────────────────────────────────────────────────────────

def scrape_category(driver: webdriver.Chrome, category: dict, date_str: str) -> list[dict]:
    """Bir kategorinin tüm sayfalarını ?pg=N ile dolaşır."""
    cat_name = category["name"]
    cat_slug = category["slug"]
    cat_url = f"{BASE_URL}/{cat_slug}"

    all_products = []
    seen_names = set()

    logger.info(f"▶ Kategori: {cat_name}")

    # İlk sayfayı yükle
    try:
        driver.get(cat_url)
        WebDriverWait(driver, PRODUCT_WAIT).until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, "div.product-item, [data-selector='.product-detail-card']")
            )
        )
        time.sleep(POST_LOAD_SLEEP)
    except Exception:
        logger.warning(f"  {cat_name}: ilk sayfa yüklenemedi, atlanıyor.")
        return []

    # Toplam sayfa sayısını bul
    total_pages = get_total_pages(driver.page_source)
    logger.info(f"  Toplam sayfa: {total_pages}")

    # Tüm sayfaları dolaş
    for page in range(1, total_pages + 1):
        if page > 1:
            url = f"{cat_url}?pg={page}"
            try:
                driver.get(url)
                WebDriverWait(driver, PRODUCT_WAIT).until(
                    EC.presence_of_element_located(
                        (By.CSS_SELECTOR, "div.product-item, [data-selector='.product-detail-card']")
                    )
                )
                time.sleep(POST_LOAD_SLEEP)
            except Exception:
                logger.warning(f"  Sayfa {page}: yüklenemedi, atlanıyor.")
                continue

        page_products = parse_page(driver.page_source, cat_name, date_str)

        # Cross-page dedup
        new_products = []
        for p in page_products:
            if p["product_name"] not in seen_names:
                seen_names.add(p["product_name"])
                new_products.append(p)

        all_products.extend(new_products)

        if page % 10 == 0 or page == total_pages:
            logger.info(f"  Sayfa {page}/{total_pages}: toplam {len(all_products)} ürün")

        if not page_products:
            logger.info(f"  Sayfa {page}: ürün bulunamadı → pagination bitti.")
            break

        time.sleep(PAGE_DELAY)

    logger.info(f"  ✓ {cat_name}: {len(all_products)} ürün\n")
    return all_products

# ── Worker ─────────────────────────────────────────────────────────────────────

def worker(category: dict, date_str: str) -> list[dict]:
    """Her thread kendi Chrome driver'ını açar ve kapatır."""
    driver = create_driver()
    try:
        return scrape_category(driver, category, date_str)
    finally:
        driver.quit()


# ── Konfigürasyon ─────────────────────────────────────────────────────────────

DEFAULT_WORKERS = 3

# ── Ana çalıştırıcı ───────────────────────────────────────────────────────────

def main():
    today_str = str(date.today())
    csv_path = OUT_DIR / f"dermomarket_{today_str}.csv"

    _check_existing(csv_path)

    logger.info("=" * 55)
    logger.info(f"  Dermomarket Scraper — {today_str}")
    logger.info(f"  Kategori: {len(CATEGORIES)} | Worker: {DEFAULT_WORKERS}")
    logger.info("=" * 55)

    fieldnames = ["product_name", "price"]
    all_products = []

    # Global dedup: aynı ürün birden fazla kategoride olabilir
    # İlk görülen kategoriyi tut
    global_seen = set()

    with ThreadPoolExecutor(max_workers=DEFAULT_WORKERS) as executor:
        future_to_cat = {
            executor.submit(worker, cat, today_str): cat
            for cat in CATEGORIES
        }
        for future in as_completed(future_to_cat):
            cat = future_to_cat[future]
            try:
                cat_products = future.result()

                new_count = 0
                for p in cat_products:
                    key = p["product_name"]
                    if key not in global_seen:
                        global_seen.add(key)
                        all_products.append(p)
                        new_count += 1

                logger.info(
                    f"  [{cat['name']}] merge edildi → +{new_count} ürün "
                    f"(genel toplam: {len(all_products)})"
                )

                if new_count < len(cat_products):
                    logger.info(
                        f"  Cross-category dedup: {len(cat_products) - new_count} "
                        f"duplicate atlandı"
                    )

            except Exception as exc:
                logger.error(f"  [{cat['name']}] Hata: {exc}")

    # CSV kaydet
    all_products.sort(key=lambda p: p["product_name"])

    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_products)

    logger.info("=" * 55)
    logger.info(f"  TAMAMLANDI — {len(all_products)} ürün → '{csv_path}'")
    logger.info("=" * 55)


if __name__ == "__main__":
    main()