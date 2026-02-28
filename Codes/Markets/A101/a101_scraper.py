"""
A101.com.tr Ürün Scraper - Playwright Versiyonu
JavaScript ile yüklenen sayfaları destekler.

Kurulum:
    pip install playwright
    playwright install chromium
"""

import asyncio
import csv
import json
import logging
import re
from playwright.async_api import async_playwright, TimeoutError as PWTimeout

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

BASE_URL = "https://www.a101.com.tr"

# Bilinen A101 kategorileri
KNOWN_CATEGORIES = [
    {"name": "Market",         "url": f"{BASE_URL}/market"},
    {"name": "Elektronik",     "url": f"{BASE_URL}/elektronik"},
    {"name": "Ev & Yasam",     "url": f"{BASE_URL}/ev-ve-yasam"},
    {"name": "Tekstil",        "url": f"{BASE_URL}/tekstil"},
    {"name": "Oyuncak",        "url": f"{BASE_URL}/oyuncak"},
    {"name": "Spor",           "url": f"{BASE_URL}/spor"},
    {"name": "Kozmetik",       "url": f"{BASE_URL}/kozmetik"},
    {"name": "Kirtasiye",      "url": f"{BASE_URL}/kirtasiye"},
    {"name": "Anne & Bebek",   "url": f"{BASE_URL}/anne-bebek"},
    {"name": "Pet Shop",       "url": f"{BASE_URL}/pet-shop"},
    {"name": "Oto & Bahce",    "url": f"{BASE_URL}/oto-bahce"},
    {"name": "Aktuel Urunler", "url": f"{BASE_URL}/aldin-aldin"},
]


async def scrape_category(page, category: dict, max_pages: int = 30) -> list[dict]:
    """Bir kategorinin tum urunlerini ceker."""
    products = []
    url = category["url"]
    cat_name = category["name"]

    logger.info(f"Kategori: {cat_name} -> {url}")

    try:
        await page.goto(url, wait_until="networkidle", timeout=30000)
    except PWTimeout:
        logger.warning(f"Timeout: {url}")
        return products

    page_num = 1
    while page_num <= max_pages:
        await page.wait_for_timeout(2000)

        # Urun kartlarini bul
        items = await page.query_selector_all(
            ".product-item, .product-card, [class*='ProductCard'], "
            "[class*='product-card'], .prd-item, "
            "[data-testid*='product'], [class*='ProductItem']"
        )

        # Fallback: urun linkleri
        if not items:
            items = await page.query_selector_all("a[href*='/p/'], a[href*='/urun/']")

        logger.info(f"  Sayfa {page_num}: {len(items)} urun ogesi")

        if not items:
            break

        for item in items:
            product = {"category": cat_name}

            # Isim
            for sel in [".product-name", ".p-name", "h2", "h3",
                        "[class*='name']", "[class*='Name']", "[class*='title']"]:
                el = await item.query_selector(sel)
                if el:
                    product["name"] = (await el.inner_text()).strip()
                    break

            # Fiyat
            for sel in [".product-price", ".price", ".p-price",
                        "[class*='price']", "[class*='Price']"]:
                el = await item.query_selector(sel)
                if el:
                    product["price"] = (await el.inner_text()).strip()
                    break

            # Link
            href = await item.get_attribute("href")
            if not href:
                a = await item.query_selector("a[href]")
                if a:
                    href = await a.get_attribute("href")
            if href:
                product["url"] = href if href.startswith("http") else BASE_URL + href

            # Resim
            img = await item.query_selector("img")
            if img:
                src = (await img.get_attribute("src") or
                       await img.get_attribute("data-src") or "")
                product["image"] = src

            if product.get("name") or product.get("url"):
                products.append(product)

        # Sonraki sayfaya gec
        next_btn = await page.query_selector(
            "a[rel='next'], .pagination .next, [aria-label='Sonraki'], "
            "button.next-page, [class*='next']:not([disabled])"
        )

        if next_btn:
            try:
                await next_btn.click()
                await page.wait_for_load_state("networkidle", timeout=15000)
                page_num += 1
            except Exception as e:
                logger.warning(f"Sonraki sayfa gecisi basarisiz: {e}")
                break
        else:
            # URL tabanli sayfalama dene
            next_url = f"{url}?page={page_num + 1}"
            current_url = page.url
            try:
                await page.goto(next_url, wait_until="networkidle", timeout=20000)
                page_title = await page.title()
                if page.url == current_url or "404" in page_title:
                    break
                page_num += 1
            except PWTimeout:
                break

    logger.info(f"  -> Toplam {len(products)} urun bulundu ({cat_name})")
    return products


async def get_dynamic_categories(page) -> list[dict]:
    """Anasayfadan dinamik kategorileri ceker."""
    try:
        await page.goto(BASE_URL, wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(3000)

        links = await page.query_selector_all("nav a[href], header a[href], .menu a[href]")
        categories = []
        seen = set()

        for link in links:
            href = await link.get_attribute("href") or ""
            text = (await link.inner_text()).strip()

            if not href or href in ("#", "/") or not text:
                continue

            full_url = href if href.startswith("http") else BASE_URL + href

            skip_keywords = ["sitemap", ".xml", "login", "giris", "hesap",
                             "sepet", "odeme", "blog", "yardim", "iletisim"]

            if (full_url not in seen
                    and BASE_URL in full_url
                    and not any(kw in full_url for kw in skip_keywords)):
                seen.add(full_url)
                categories.append({"name": text, "url": full_url})

        if categories:
            logger.info(f"Anasayfadan {len(categories)} kategori alindi.")
            return categories

    except Exception as e:
        logger.warning(f"Dinamik kategori alimi basarisiz: {e}")

    logger.info("Bilinen sabit kategoriler kullaniliyor.")
    return KNOWN_CATEGORIES


async def scrape_all(
    max_categories: int = None,
    max_pages: int = 30,
    output_csv: str = "a101_urunler.csv",
    output_json: str = "a101_urunler.json",
    headless: bool = True,
):
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=headless)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
            locale="tr-TR",
        )
        page = await context.new_page()

        # Gorsel/analytics isteklerini engelle (hizlanma)
        await page.route(
            re.compile(r"\.(gif|png|jpg|jpeg|svg|woff2?)(\?.*)?$"
                       r"|google-analytics|doubleclick|facebook\.net"),
            lambda route: route.abort()
        )

        logger.info("Kategoriler aliniyor...")
        categories = await get_dynamic_categories(page)
        logger.info(f"{len(categories)} kategori bulundu.")

        if max_categories:
            categories = categories[:max_categories]

        all_products = []
        for i, cat in enumerate(categories, 1):
            logger.info(f"\n[{i}/{len(categories)}]")
            products = await scrape_category(page, cat, max_pages=max_pages)
            all_products.extend(products)

        await browser.close()

    # Tekrarlari temizle
    seen_urls: set = set()
    unique = []
    for p in all_products:
        key = p.get("url") or p.get("name", "")
        if key and key not in seen_urls:
            seen_urls.add(key)
            unique.append(p)

    logger.info(f"\nToplam benzersiz urun: {len(unique)}")

    # CSV kaydet
    if unique:
        fieldnames = ["category", "name", "price", "url", "image"]
        with open(output_csv, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(unique)
        logger.info(f"CSV kaydedildi: {output_csv}")

    # JSON kaydet
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(unique, f, ensure_ascii=False, indent=2)
    logger.info(f"JSON kaydedildi: {output_json}")

    # Onizleme
    print("\n--- Ilk 3 Urun ---")
    for p in unique[:3]:
        print(json.dumps(p, ensure_ascii=False, indent=2))

    return unique


# ─────────────────────────────────────────────
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="A101.com.tr Playwright Scraper")
    parser.add_argument("--max-categories", type=int, default=None,
                        help="Test icin kategori sayisi siniri (varsayilan: hepsi)")
    parser.add_argument("--max-pages", type=int, default=30,
                        help="Kategori basina max sayfa (varsayilan: 30)")
    parser.add_argument("--output-csv", default="a101_urunler.csv")
    parser.add_argument("--output-json", default="a101_urunler.json")
    parser.add_argument("--show-browser", action="store_true",
                        help="Tarayiciyi gorunur sec (debug icin)")
    args = parser.parse_args()

    asyncio.run(scrape_all(
        max_categories=args.max_categories,
        max_pages=args.max_pages,
        output_csv=args.output_csv,
        output_json=args.output_json,
        headless=not args.show_browser,
    ))
