# -*- coding: utf-8 -*-
"""
Created on Thu Mar 12 00:11:17 2026

@author: orenl
"""

# -*- coding: utf-8 -*-
"""
Bizim Toptan Scraper
- Tüm ana kategorileri alır
- Ana kategorilerin alt kategorilerini alır
- Alt kategorilerdeki tüm sayfaları gezer
- Ürün ID, ürün adı, kategori ve fiyat toplar
- Aynı ürün ID tekrar geldiyse yeniden eklemez
- CSV olarak kaydeder
- Kategori bazında görünen toplam ürün sayısı ile scrape edilen ürün sayısını karşılaştırır
"""

import os
import re
import csv
import time
import html
import json
from urllib.parse import urljoin, urlparse, parse_qs

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.bizimtoptan.com.tr"
START_URL = BASE_URL

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8",
    "Referer": BASE_URL,
}

REQUEST_DELAY = 0.7
TIMEOUT = 30

OUTPUT_DIR = "bizimtoptan_output"
PRODUCTS_CSV = os.path.join(OUTPUT_DIR, "bizimtoptan_urunler.csv")
CHECK_CSV = os.path.join(OUTPUT_DIR, "bizimtoptan_kontrol.csv")

session = requests.Session()
session.headers.update(HEADERS)


def safe_get(url, max_retries=3):
    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            resp = session.get(url, timeout=TIMEOUT)
            resp.raise_for_status()
            time.sleep(REQUEST_DELAY)
            return resp
        except Exception as e:
            last_error = e
            print(f"[HATA] {url} alınamadı. Deneme {attempt}/{max_retries} -> {e}")
            time.sleep(2)
    raise last_error


def get_soup(url):
    resp = safe_get(url)
    return BeautifulSoup(resp.text, "html.parser")


def clean_text(text):
    if text is None:
        return ""
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def absolute_url(href):
    if not href:
        return None
    return urljoin(BASE_URL, href)


def normalize_price(price_text):
    if not price_text:
        return ""
    price_text = clean_text(price_text)
    m = re.search(r"(\d{1,3}(?:\.\d{3})*,\d{2}\s*TL)", price_text, flags=re.I)
    if m:
        return m.group(1).replace(" ", "")
    return price_text


def parse_total_product_count(soup):
    page_text = soup.get_text(" ", strip=True)

    matches = re.findall(r"\((\d+)\)", page_text)
    if matches:
        nums = [int(x) for x in matches]
        if nums:
            return max(nums)

    matches2 = re.findall(r"(\d+)\s*ürün", page_text, flags=re.I)
    if matches2:
        nums = [int(x) for x in matches2]
        if nums:
            return max(nums)

    return None


def parse_page_count(soup):
    max_page = 1

    last_page_a = soup.select_one("li.last-page a")
    if last_page_a:
        title = last_page_a.get("title")
        href = last_page_a.get("href", "")
        if title and title.isdigit():
            return int(title)

        qs = parse_qs(urlparse(href).query)
        if "pagenumber" in qs:
            try:
                return int(qs["pagenumber"][0])
            except:
                pass

    for a in soup.select("div.pager-container a, ul a"):
        href = a.get("href", "")
        title = a.get("title", "")
        text = clean_text(a.get_text())

        if title.isdigit():
            max_page = max(max_page, int(title))

        if text.isdigit():
            max_page = max(max_page, int(text))

        qs = parse_qs(urlparse(href).query)
        if "pagenumber" in qs:
            try:
                max_page = max(max_page, int(qs["pagenumber"][0]))
            except:
                pass

    return max_page


def discover_main_categories():
    soup = get_soup(START_URL)
    categories = []
    seen = set()

    for a in soup.select("a.main-menu-link"):
        href = a.get("href")
        name_el = a.select_one(".main-menu-name")
        name = clean_text(name_el.get_text()) if name_el else clean_text(a.get_text())

        if not href or not name:
            continue

        full_url = absolute_url(href)
        if not full_url.startswith(BASE_URL):
            continue

        key = (name, full_url)
        if key not in seen:
            seen.add(key)
            categories.append({
                "main_category": name,
                "url": full_url
            })

    return categories


def discover_subcategories(main_cat_name, main_cat_url):
    soup = get_soup(main_cat_url)
    subcategories = []
    seen = set()

    candidates = soup.select("a.parents")
    if not candidates:
        candidates = soup.select("ul.spec-list a[href]")

    for a in candidates:
        href = a.get("href")
        name = clean_text(a.get_text())

        if not href or not name:
            continue

        full_url = absolute_url(href)

        key = (name, full_url)
        if key not in seen:
            seen.add(key)
            subcategories.append({
                "main_category": main_cat_name,
                "sub_category": name,
                "url": full_url
            })

    if not subcategories:
        subcategories.append({
            "main_category": main_cat_name,
            "sub_category": "",
            "url": main_cat_url
        })

    return subcategories


def build_page_url(category_url, page_num):
    parsed = urlparse(category_url)
    qs = parse_qs(parsed.query)
    qs["pagenumber"] = [str(page_num)]
    qs["paginationType"] = ["10"]

    query_parts = []
    for k, values in qs.items():
        for v in values:
            query_parts.append(f"{k}={v}")

    new_query = "&".join(query_parts)
    rebuilt = parsed._replace(query=new_query)
    return rebuilt.geturl()


def extract_product_id(card):
    """
    Ürün ID:
    <div class="product-box-container ..." data-productid="13856">
    """
    pid = card.get("data-productid")
    if pid:
        return clean_text(pid)

    # fallback: data-enhanced-productclick içinden item_id
    a = card.select_one("a.product-item")
    if a:
        data_json = a.get("data-enhanced-productclick")
        if data_json:
            try:
                obj = json.loads(data_json)
                item_id = obj.get("item_id", "")
                if item_id:
                    return clean_text(str(item_id))
            except:
                pass

    return ""


def extract_name_from_card(card):
    a = card.select_one("a.product-item")
    if a:
        data_json = a.get("data-enhanced-productclick")
        if data_json:
            try:
                obj = json.loads(data_json)
                name = clean_text(obj.get("item_name", ""))
                if name:
                    return name
            except:
                pass

    text_candidates = []
    for tag in card.select("a.product-item, .product-box-image-container a, .product-box-container a"):
        t = clean_text(tag.get_text(" ", strip=True))
        if t:
            text_candidates.append(t)

    if text_candidates:
        text_candidates = sorted(text_candidates, key=len, reverse=True)
        return text_candidates[0]

    return ""


def extract_price_from_card(card):
    text = card.get_text(" ", strip=True)
    text = clean_text(text)

    matches = re.findall(r"\d{1,3}(?:\.\d{3})*,\d{2}\s*TL", text, flags=re.I)
    if matches:
        return normalize_price(matches[0])

    matches2 = re.findall(r"\d{1,3}(?:\.\d{3})*\s*TL", text, flags=re.I)
    if matches2:
        return normalize_price(matches2[0])

    return ""


def extract_products_from_page(soup, category_text):
    products = []
    cards = soup.select("div.product-box-container")

    for card in cards:
        product_id = extract_product_id(card)
        product_name = extract_name_from_card(card)
        price = extract_price_from_card(card)

        if not product_id:
            continue

        if not product_name and not price:
            continue

        products.append({
            "product_id": product_id,
            "product_name": product_name,
            "category": category_text,
            "price": price
        })

    return products


def scrape_subcategory(main_category, sub_category, subcat_url):
    print("\n" + "=" * 80)
    print(f"Kategori taranıyor: {main_category} | {sub_category if sub_category else 'Ana kategori'}")
    print(f"URL: {subcat_url}")

    first_soup = get_soup(subcat_url)
    total_products_reported = parse_total_product_count(first_soup)
    total_pages = parse_page_count(first_soup)

    print(f"Sayfada görünen toplam ürün: {total_products_reported}")
    print(f"Toplam sayfa: {total_pages}")

    category_text = f"{main_category} > {sub_category}" if sub_category else main_category
    all_products = []

    for page in range(1, total_pages + 1):
        page_url = subcat_url if page == 1 else build_page_url(subcat_url, page)
        print(f"  -> Sayfa {page}/{total_pages}: {page_url}")

        try:
            soup = get_soup(page_url)
            page_products = extract_products_from_page(soup, category_text)
            print(f"     Bu sayfadaki bulunan ürün: {len(page_products)}")
            all_products.extend(page_products)
        except Exception as e:
            print(f"     [HATA] Sayfa okunamadı: {e}")

    # kategori içi unique ID sayısı
    unique_ids_in_category = {p["product_id"] for p in all_products if p["product_id"]}
    scraped_count = len(unique_ids_in_category)

    result = {
        "main_category": main_category,
        "sub_category": sub_category,
        "url": subcat_url,
        "reported_total": total_products_reported,
        "scraped_total": scraped_count,
        "page_count": total_pages,
        "match": (
            "UNKNOWN" if total_products_reported is None
            else "OK" if total_products_reported == scraped_count
            else "MISMATCH"
        )
    }

    print(f"Unique scrape edilen ürün sayısı: {scraped_count}")
    print(f"Karşılaştırma sonucu: {result['match']}")

    return all_products, result


def deduplicate_products_by_id(products):
    """
    Global olarak product_id bazında tekilleştirir.
    Aynı ID tekrar geldiyse ilk görüleni alır.
    """
    unique_products = []
    seen_ids = set()

    for p in products:
        pid = p["product_id"]
        if not pid:
            continue
        if pid in seen_ids:
            continue
        seen_ids.add(pid)
        unique_products.append(p)

    return unique_products


def save_products_csv(products, filepath):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)

    fieldnames = [
        "product_id",
        "product_name",
        "category",
        "price"
    ]

    with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(products)


def save_check_csv(check_rows, filepath):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)

    fieldnames = [
        "main_category",
        "sub_category",
        "url",
        "reported_total",
        "scraped_total",
        "page_count",
        "match"
    ]

    with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(check_rows)


def main():
    print("Ana kategoriler alınıyor...")
    main_categories = discover_main_categories()
    print(f"Bulunan ana kategori sayısı: {len(main_categories)}")

    if not main_categories:
        print("Hiç ana kategori bulunamadı.")
        return

    all_products = []
    all_checks = []

    for cat in main_categories:
        main_name = cat["main_category"]
        main_url = cat["url"]

        print("\n" + "#" * 80)
        print(f"Ana kategori: {main_name}")
        print(f"URL: {main_url}")

        try:
            subcategories = discover_subcategories(main_name, main_url)
            print(f"Bulunan alt kategori sayısı: {len(subcategories)}")
        except Exception as e:
            print(f"[HATA] Alt kategoriler alınamadı: {e}")
            subcategories = [{
                "main_category": main_name,
                "sub_category": "",
                "url": main_url
            }]

        for sub in subcategories:
            try:
                products, check_row = scrape_subcategory(
                    main_category=sub["main_category"],
                    sub_category=sub["sub_category"],
                    subcat_url=sub["url"]
                )
                all_products.extend(products)
                all_checks.append(check_row)
            except Exception as e:
                print(f"[HATA] Alt kategori scrape edilemedi: {sub['url']} -> {e}")
                all_checks.append({
                    "main_category": sub["main_category"],
                    "sub_category": sub["sub_category"],
                    "url": sub["url"],
                    "reported_total": None,
                    "scraped_total": 0,
                    "page_count": None,
                    "match": "ERROR"
                })

    unique_products = deduplicate_products_by_id(all_products)

    save_products_csv(unique_products, PRODUCTS_CSV)
    save_check_csv(all_checks, CHECK_CSV)

    print("\n" + "=" * 80)
    print("Scraping tamamlandı.")
    print(f"Toplam ham kayıt sayısı: {len(all_products)}")
    print(f"Unique ürün sayısı: {len(unique_products)}")
    print(f"Ürün CSV: {PRODUCTS_CSV}")
    print(f"Kontrol CSV: {CHECK_CSV}")

    mismatch_count = sum(1 for x in all_checks if x["match"] == "MISMATCH")
    error_count = sum(1 for x in all_checks if x["match"] == "ERROR")

    print(f"Eşleşmeyen kategori sayısı: {mismatch_count}")
    print(f"Hatalı kategori sayısı: {error_count}")


if __name__ == "__main__":
    main()