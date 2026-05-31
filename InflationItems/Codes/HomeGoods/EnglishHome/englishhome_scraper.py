"""
englishhome_scraper.py — English Home Günlük Ürün Fiyat Scraper'ı

Selenium + headless Chrome, paralel worker, görseller kapalı.
Ticimax altyapısı — sayfa bazlı pagination: ?sayfa=N

Gereksinimler:
    pip install selenium webdriver-manager beautifulsoup4 lxml

Kullanım:
    python englishhome_scraper.py

Çıktı:
    englishhome_YYYY-MM-DD.csv  →  item_name | price | category | date
"""

import csv
import logging
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta
from pathlib import Path

# ── Repo-relative output path ─────────────────────────────────────────────────
# Bu dosya: InflationItems/Codes/HomeGoods/EnglishHome/englishhome_scraper.py
# Veri:     InflationItems/Datas/HomeGoods/EnglishHome/
REPO_ROOT = Path(__file__).resolve().parents[4]
OUT_DIR   = REPO_ROOT / "InflationItems" / "Datas" / "HomeGoods" / "EnglishHome"
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

BASE_URL = "https://www.englishhome.com"

# Hocanın talimatı: Home, Home Decoration, Living kategorileri
# Kozmetik dahil — farklı COICOP kodu ile mapping'lenir
CATEGORIES = [
    {"name": "Yatak Odası",       "slug": "c-yatak-odasi"},
    {"name": "Sofra",             "slug": "c-sofra"},
    {"name": "Mutfak",            "slug": "c-mutfak"},
    {"name": "Küçük Ev Aletleri", "slug": "c-kucuk-ev-aletleri"},
    {"name": "Dekorasyon",        "slug": "c-dekorasyon"},
    {"name": "Banyo",             "slug": "c-banyo"},
    {"name": "Kozmetik",          "slug": "c-kisisel-bakim-kozmetik"},
    {"name": "Halı&Kilim",        "slug": "c-hali-kilim"},
    {"name": "Çeyiz Ürünleri",    "slug": "c-ceyiz-listesi"},
    {"name": "Hediye",            "slug": "yeni-ev-hediyesi"},
]

PAGE_LOAD_TIMEOUT = 30
PRODUCT_WAIT      = 15
POST_LOAD_SLEEP   = 1.5
PAGE_DELAY        = 1.0
DEFAULT_WORKERS   = 3

# Fiyat regex: "₺499,99" veya "₺1.199,99"  veya "499,99" veya "1.199,99"
_PRICE_RE = re.compile(r"[₺]?([\d]{1,3}(?:\.[\d]{3})*,\d{2})")

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
            f"   Bugün ikinci kez çalıştırıyorsunuz."
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
    """'₺1.199,99' veya '1.199,99' → 1199.99 float. Bulamazsa None.

    İLK eşleşmeyi alır. Ticimax kart metninde fiyatlar şu sırada listelenir:
    önce indirimli (satış) fiyat, sonra üstü çizili 'regular' fiyat. Bu yüzden
    SON token DEĞİL ilk token = gerçek satış fiyatıdır. (Eskiden son token
    alınıyordu; indirim rozeti olan üründe regular/şişirilmiş fiyatı kaydedip
    ×N hatalı sıçramalara yol açıyordu.)
    """
    matches = _PRICE_RE.findall(text)
    if not matches:
        return None
    try:
        value = float(matches[0].replace(".", "").replace(",", "."))
        return value if value > 0 else None
    except ValueError:
        return None


# Ticimax kartında MÜŞTERİNİN ÖDEDİĞİ fiyatı taşıyan elementler (öncelik sırası).
# English Home kartı 3 katmanlı fiyat gösterir:
#   .sptPrice / .KatSepetFiyat        = "sepette ek indirim" SEPET fiyatı (varsa EN DÜŞÜK = gerçek ödenen)
#   .discountPriceSpan / .discountPrice = indirimli satış fiyatı
#   .regularPriceSpan  / .regularPrice  = üstü çizili MSRP (asla istemeyiz)
# Gerçek satış fiyatı = sepet fiyatı (varsa), yoksa indirimli fiyat. regularPrice
# yalnızca hiçbiri yoksa son çare. (discountPriceSpan tek başına bazen şişirilmiş
# MSRP'ye eşit oluyor; o yüzden önce sptPrice okunmalı.)
_PRICE_SELECTORS = (
    "span.sptPrice", "div.KatSepetFiyat",
    "span.discountPriceSpan", "div.discountPrice",
    "span.regularPriceSpan", "div.regularPrice",
)


def extract_card_price(card) -> float | None:
    """Ürün kartından müşterinin ÖDEDİĞİ (sepet) fiyatı DOM elementinden çeker.

    Önce 'sepette ek indirim' (sptPrice) fiyatını, yoksa indirimli satış fiyatını
    alır. Kartın tüm metnine regex uygulamayız; böylece üstü çizili MSRP veya
    kampanya yüzdesi gibi fazladan token'lar yanlışlıkla alınmaz. Hiçbir fiyat
    elementi yoksa son çare olarak kart metnindeki İLK fiyatı kullanır.
    """
    for sel in _PRICE_SELECTORS:
        el = card.select_one(sel)
        if el:
            price = parse_price(el.get_text(" ", strip=True))
            if price:
                return price
    return parse_price(card.get_text(separator=" ", strip=True))

# ── Sayfa parse ───────────────────────────────────────────────────────────────

def parse_page(html: str, category_name: str, date_str: str) -> list[dict]:
    """
    Ticimax HTML'den ürünleri çıkarır.

    Ürün kartı yapısı:
        div.productItem[data-id]
          └─ a.detailLink[title]  → ürün adı
          └─ div.productDetail[data-category] → kategori
          └─ fiyat: kart içindeki ₺XXX,XX pattern
    """
    soup = BeautifulSoup(html, "lxml")
    products = []
    seen_names = set()

    cards = soup.select("div.productItem")

    for card in cards:
        # Ürün adı: a.detailLink[title] veya a.detailUrl[title]
        link = card.select_one("a.detailLink, a.detailUrl")
        if not link:
            continue

        name = link.get("title", "").strip()
        if not name or name in seen_names:
            continue

        # Fiyat: kart içindeki GÖRÜNEN satış fiyatı elementinden alınır
        # (son token = üstü çizili regular fiyat olduğu için kullanılmaz).
        price = extract_card_price(card)

        if price is None:
            continue

        # Kategori: scraper'ın ana kategori adını kullan (TUIK mapping tutarlılığı için)
        # data-category alt kategori döner (Peçete, Kupa vs.) — mapping'i bozar

        seen_names.add(name)
        products.append({
            "product_name": name,
            "price":        price,
        })

    return products

# ── Toplam sayfa sayısını bul ─────────────────────────────────────────────────

def get_total_pages(html: str) -> int:
    """Pagination'dan toplam sayfa sayısını çıkarır."""
    soup = BeautifulSoup(html, "lxml")

    # Sayfa linkleri: ?sayfa=N
    max_page = 1
    page_links = soup.select("a[href*='sayfa=']")
    for link in page_links:
        href = link.get("href", "")
        match = re.search(r"sayfa=(\d+)", href)
        if match:
            pg = int(match.group(1))
            if pg > max_page:
                max_page = pg

    # Fallback: sayfa numarası butonlarından
    if max_page == 1:
        for el in soup.select("ul.pagination li a, .pager a, nav a"):
            text = el.get_text(strip=True)
            if text.isdigit():
                pg = int(text)
                if pg > max_page:
                    max_page = pg

    return max_page

# ── Kategori scraper ──────────────────────────────────────────────────────────

def scrape_category(driver: webdriver.Chrome, category: dict, date_str: str) -> list[dict]:
    """Bir kategorinin tüm sayfalarını ?sayfa=N ile dolaşır."""
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
                (By.CSS_SELECTOR, "div.productItem")
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
            url = f"{cat_url}?sayfa={page}"
            try:
                driver.get(url)
                WebDriverWait(driver, PRODUCT_WAIT).until(
                    EC.presence_of_element_located(
                        (By.CSS_SELECTOR, "div.productItem")
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

# ── Plausibility (data-error) filtresi ────────────────────────────────────────
# English Home'un kendi sitesi zaman zaman bazı ürünlerde hatalı/şişik fiyat
# servis ediyor (aynı ürün Trendyol/LCW'de ve bizim geçmiş verimizde ~5× düşük;
# 2026-05-31'de doğrulandı). Bir ürünün fiyatı bir önceki güne göre bu faktör
# bandı dışına çıkıyorsa, yanlış fiyatı CSV'ye yazmak yerine o ürünü ATLARIZ —
# böylece günlük CSV temiz kalır (paylaşılan ulusal pipeline için de güvenli).
PLAUSIBLE_MIN = 0.25   # fiyat 1/4'ün altına düştüyse → hatalı
PLAUSIBLE_MAX = 4.0    # fiyat 4 katından fazla arttıysa → hatalı


def _load_prev_prices(days_back: int = 7) -> dict:
    """Son birkaç günün CSV'lerinden BİRLEŞİK {product_name: price} bazı döner.

    En yeni günden geriye doğru gider, her ürün için ilk (en yeni) bulunan fiyatı
    kullanır. Tek bir günün kısa/eksik scrape'i bazı zayıflatıp glitch ürünlerin
    filtreden kaçmasına yol açmasın diye birden çok gün birleştirilir.
    """
    prices = {}
    for back in range(1, days_back + 1):
        d = date.today() - timedelta(days=back)
        f = OUT_DIR / f"englishhome_{d}.csv"
        if not f.exists():
            continue
        try:
            with open(f, encoding="utf-8-sig", newline="") as fh:
                for row in csv.DictReader(fh):
                    name = row.get("product_name")
                    if not name or name in prices:   # daha yeni gün zaten yazdı
                        continue
                    try:
                        prices[name] = float(row["price"])
                    except (ValueError, TypeError):
                        continue
        except Exception as e:
            logger.warning(f"Önceki gün okunamadı ({f.name}): {e}")
    if prices:
        logger.info(f"Plausibility bazı: son {days_back} günden {len(prices)} ürün")
    else:
        logger.info("Plausibility bazı bulunamadı — filtre uygulanmadan devam.")
    return prices


def _apply_plausibility_filter(products: list) -> list:
    """Fiyatı düne göre mantıksız değişen ürünleri (site hatası) eler."""
    prev = _load_prev_prices()
    if not prev:
        return products
    kept, dropped = [], 0
    for p in products:
        base = prev.get(p["product_name"])
        if base and base > 0:
            ratio = p["price"] / base
            if not (PLAUSIBLE_MIN <= ratio <= PLAUSIBLE_MAX):
                dropped += 1
                continue
        kept.append(p)
    if dropped:
        logger.warning(
            f"⚠️ Plausibility filtresi: {dropped} ürün mantıksız fiyat (siteden "
            f"gelen hatalı/aşırı değer) nedeniyle atlandı. Kalan: {len(kept)}"
        )
    return kept


# ── Ana çalıştırıcı ───────────────────────────────────────────────────────────

def main():
    today_str = str(date.today())
    csv_path = OUT_DIR / f"englishhome_{today_str}.csv"

    _check_existing(csv_path)

    logger.info("=" * 55)
    logger.info(f"  English Home Scraper — {today_str}")
    logger.info(f"  Kategori: {len(CATEGORIES)} | Worker: {DEFAULT_WORKERS}")
    logger.info("=" * 55)

    fieldnames = ["product_name", "price"]
    all_products = []
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

    # Site kaynaklı hatalı/şişik fiyatları yazmadan önce ele (düne göre mantıksız
    # sıçrayanlar atlanır → CSV temiz kalır).
    all_products = _apply_plausibility_filter(all_products)

    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_products)

    logger.info("=" * 55)
    logger.info(f"  TAMAMLANDI — {len(all_products)} ürün → '{csv_path}'")
    logger.info("=" * 55)


if __name__ == "__main__":
    main()