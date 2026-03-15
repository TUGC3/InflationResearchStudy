#!/usr/bin/env python3
"""
Yapimaks.com Product Scraper
- Sitemap'i indirir veya lokal dosyadan okur
- Önceki sitemap ile karşılaştırır (yeni URL var mı?)
- Her ürün sayfasından isim, fiyat, product ID scrapelar
- Sonuçları CSV'ye kaydeder
"""

import csv
import os
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from camoufox.sync_api import Camoufox

# ─── AYARLAR ────────────────────────────────────────────────────────────────
SITEMAP_URL = "https://yapimaks.com/sitemap/products1.xml"
LOCAL_SITEMAP_PATH = "products1.xml"
OUTPUT_DIR = "InflationItems/Datas/ConstructionSuppliesMarkets/yapimaks"
OUTPUT_CSV = f"{OUTPUT_DIR}/yapimaks_products.csv"
DELAY_BETWEEN_REQUESTS = 1.5  # saniye (sunucuya nazik ol)
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    )
}
# ─────────────────────────────────────────────────────────────────────────────


def fetch_sitemap(url: str) -> str:
    """Sitemap'i URL'den indir, XML stringi döndür."""
    print(f"[*] Sitemap indiriliyor: {url}")
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.text


def parse_urls_from_sitemap(xml_text: str) -> list[str]:
    """Sitemap XML'inden tüm <loc> URL'lerini çıkar."""
    # Namespace'i yoksay
    xml_text = re.sub(r' xmlns="[^"]+"', '', xml_text)
    root = ET.fromstring(xml_text)
    urls = []
    for url_el in root.findall(".//url"):
        loc = url_el.findtext("loc", "").strip()
        if loc:
            urls.append(loc)
    return urls


def extract_product_id(url: str) -> str:
    """URL sonundaki -pXX pattern'inden product ID çıkar."""
    match = re.search(r'-p(\d+)$', url.rstrip('/'))
    return match.group(1) if match else ""


def is_product_url(url: str) -> bool:
    """Sadece ürün sayfalarını filtrele (sonda -pXX olan)."""
    return bool(re.search(r'-p\d+$', url.rstrip('/')))


# Global Camoufox instance (main'de başlatılır)
_camoufox = None
_browser = None
_page = None

def init_browser():
    global _camoufox, _browser, _page
    _camoufox = Camoufox(headless=True)
    _browser = _camoufox.__enter__()
    _page = _browser.new_page()

def close_browser():
    global _camoufox
    if _camoufox:
        _camoufox.__exit__(None, None, None)


def scrape_product(url: str) -> dict:
    """Ürün sayfasından tüm alanları scrapelar (Playwright ile JS destekli)."""
    product_id = extract_product_id(url)
    result = {
        "product_id": product_id,
        "url": url,
        "name": "",
        "sku": "",
        "marka": "",
        "stok_durumu": "",
        "birim": "",
        "price": "",
        "currency": "TRY",
        "scraped_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    try:
        _page.goto(url, wait_until="networkidle", timeout=30000)
        # JS render için fiyat elementinin gelmesini bekle
        try:
            _page.wait_for_selector("h5.text-primary.font-weight-bold", timeout=8000)
        except Exception:
            pass
        html = _page.content()
        soup = BeautifulSoup(html, "html.parser")

        # ── İSİM ──────────────────────────────────────────────────────────
        name_el = soup.select_one("h5.mb-0")
        if name_el:
            result["name"] = name_el.get_text(strip=True)
        else:
            og = soup.find("meta", property="og:title")
            if og:
                result["name"] = og.get("content", "").split("|")[0].strip()

        # ── FİYAT ─────────────────────────────────────────────────────────
        price_el = soup.select_one("h5.text-primary.font-weight-bold")
        if price_el:
            price_text = price_el.get_text(separator=" ", strip=True)
            match = re.search(r"(\d[\d.]*,\d+)", price_text)
            result["price"] = match.group(1) if match else ""

        if not result["price"]:
            full_text = soup.get_text(separator="\n")
            m = re.search(r"Satış Fiyatı\s*[:\-]?\s*(\d[\d.]*,\d+)", full_text, re.IGNORECASE)
            if m:
                result["price"] = m.group(1)

        # ── SKU ────────────────────────────────────────────────────────────
        sku_el = soup.select_one("small.text-muted")
        if sku_el:
            sku_text = sku_el.get_text(strip=True)
            m = re.search(r"SKU[:\s]+(.+)", sku_text, re.IGNORECASE)
            result["sku"] = m.group(1).strip() if m else sku_text

        # ── MARKA, STOK, BİRİM ────────────────────────────────────────────
        full_text = soup.get_text(separator="\n")
        field_map = {
            "marka":       [r"Marka[:\s]+(.+)"],
            "stok_durumu": [r"Stok Durumu[:\s]+(.+)"],
            "birim":       [r"Birim[:\s]+(.+)"],
        }
        for field, patterns in field_map.items():
            for pat in patterns:
                m = re.search(pat, full_text, re.IGNORECASE)
                if m:
                    result[field] = m.group(1).strip()
                    break

        print(f"  ✓ [{product_id}] {result['name'][:40]!r} | {result['price']} TL | SKU:{result['sku']}")

    except Exception as e:
        print(f"  ✗ [{url}] Hata: {e}")

    return result


def load_local_sitemap_urls() -> set[str]:
    """Daha önce kaydedilmiş sitemap URL'lerini oku."""
    if not os.path.exists(LOCAL_SITEMAP_PATH):
        return set()
    with open(LOCAL_SITEMAP_PATH, "r", encoding="utf-8") as f:
        xml_text = f.read()
    return set(parse_urls_from_sitemap(xml_text))


def save_local_sitemap(xml_text: str):
    """Yeni sitemap'i diske kaydet."""
    with open(LOCAL_SITEMAP_PATH, "w", encoding="utf-8") as f:
        f.write(xml_text)
    print(f"[*] Sitemap kaydedildi → {LOCAL_SITEMAP_PATH}")


def save_csv(products: list[dict], path: str):
    """Ürün listesini CSV'ye yaz."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if not products:
        print("[!] Kaydedilecek ürün yok.")
        return
    fieldnames = ["product_id", "name", "sku", "marka", "stok_durumu", "birim", "price", "currency", "url", "scraped_at"]
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(products)
    print(f"[✓] {len(products)} ürün kaydedildi → {path}")


def main():
    print("=" * 55)
    print("  Yapimaks Scraper")
    print("=" * 55)
    print("[*] Tarayıcı başlatılıyor...")
    init_browser()

    # 1. Yeni sitemapı indir
    new_xml = fetch_sitemap(SITEMAP_URL)
    new_urls = set(parse_urls_from_sitemap(new_xml))
    product_urls = [u for u in new_urls if is_product_url(u)]
    print(f"[*] Toplam URL: {len(new_urls)} | Ürün URL'i: {len(product_urls)}")

    # 2. Eski sitemap ile karşılaştır (sadece bilgi + güncelleme amaçlı)
    old_urls = load_local_sitemap_urls()
    if old_urls:
        new_product_urls = {u for u in product_urls if u not in old_urls}
        removed_urls = {u for u in old_urls if is_product_url(u) and u not in new_urls}
        if new_product_urls:
            print(f"[*] Yeni eklenen ürün URL: {len(new_product_urls)}")
        if removed_urls:
            print(f"[!] Kaldırılan URL sayısı: {len(removed_urls)}")
            with open("removed_urls.txt", "w") as f:
                f.write("\n".join(sorted(removed_urls)))
            print(f"    → removed_urls.txt dosyasına yazıldı")
        if not new_product_urls and not removed_urls:
            print("[*] Sitemap'te değişiklik yok.")
        # Sitemap değiştiyse güncelle
        if new_urls != old_urls:
            save_local_sitemap(new_xml)
    else:
        print("[*] Lokal sitemap bulunamadı — kaydediliyor.")
        save_local_sitemap(new_xml)

    # 3. Her zaman tüm ürünleri scrape et, her ürün anında CSV'ye yaz
    urls_to_scrape = sorted(product_urls)
    print(f"[*] {len(urls_to_scrape)} ürün scrapelanacak...")

    csv_path = get_csv_path()
    file_exists = os.path.isfile(csv_path)
    csv_file = open(csv_path, "a", newline="", encoding="utf-8-sig")
    writer = csv.DictWriter(csv_file, fieldnames=FIELDNAMES)
    if not file_exists:
        writer.writeheader()
    csv_file.flush()

    count = 0
    for i, url in enumerate(urls_to_scrape, 1):
        print(f"[{i}/{len(urls_to_scrape)}] {url}")
        data = scrape_product(url)
        write_row(writer, csv_file, data)
        count += 1
        time.sleep(DELAY_BETWEEN_REQUESTS)

    csv_file.close()
    print(f"[✓] {count} ürün kaydedildi → {csv_path}")

    close_browser()
    print("\n[✓] Tamamlandı!")


if __name__ == "__main__":
    main()