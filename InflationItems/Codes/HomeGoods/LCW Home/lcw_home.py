import csv
import html
import math
import random
import re
import time

from datetime import date
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError


class LCWHomeScraper:
    BASE_URL = "https://www.lcw.com"
    START_URL = "https://www.lcw.com/marka/lcw-home-b-307"

    OUTPUT_FILE = f"lcw_home - {date.today().isoformat()}.csv"

    PRICE_RE = re.compile(
        r"(\d{1,3}(?:\.\d{3})*(?:,\d{2})?|\d+)(?:\s*)TL\b",
        re.IGNORECASE
    )

    TOTAL_RE = re.compile(
        r"(\d[\d\.]*)\s+üründen\s+(\d[\d\.]*)\s+ürün\s+görüntüledin",
        re.IGNORECASE
    )

    PAGE_RE = re.compile(
        r"Daha Fazla Ürün Gör\s*\((\d+)/(\d+)\)",
        re.IGNORECASE
    )

    HEADERS_USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )

    def __init__(self):
        self.seen_product_urls = set()
        self.total_written = 0

    @staticmethod
    def clean_text(text):
        text = html.unescape(text or "")
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def extract_price(self, text):
        matches = list(self.PRICE_RE.finditer(text or ""))

        if not matches:
            return None

        # İndirimli ürünlerde bazen eski + yeni fiyat olabilir.
        # Listing textinde genelde en sonda görünen fiyatı almak daha stabil.
        return self.clean_text(matches[-1].group(0))

    def extract_name(self, text):
        text = self.clean_text(text)

        price_match = self.PRICE_RE.search(text)

        if price_match:
            text = text[:price_match.start()]

        junk_words = [
            "Favorilerime Ekle",
            "Sepete Ekle",
            "Hızlı Bakış",
            "Ürün Detayı",
            "Daha Fazla Ürün Gör",
            "Önceki Ürünleri Gör",
        ]

        for word in junk_words:
            text = text.replace(word, " ")

        text = re.sub(r"\bSON\s+\d+\b", " ", text, flags=re.IGNORECASE)
        text = re.sub(r"\+\s*\d+\s*$", " ", text)
        text = self.clean_text(text)

        return text

    def build_page_url(self, page_no):
        if page_no == 1:
            return self.START_URL

        return f"{self.START_URL}?sayfa={page_no}"

    def fetch_html(self, page, url):
        for attempt in range(1, 4):
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(1800)
                return page.content()

            except PlaywrightTimeoutError:
                print(f"Timeout oldu, tekrar deneniyor: {url}")
                time.sleep(5 * attempt)

            except Exception as e:
                print(f"Sayfa açılamadı: {url} | {e}")
                time.sleep(5 * attempt)

        return None

    def get_page_info(self, soup):
        page_text = self.clean_text(soup.get_text(" "))

        total_count = None
        shown_count = None
        total_pages = None

        total_match = self.TOTAL_RE.search(page_text)

        if total_match:
            try:
                total_count = int(total_match.group(1).replace(".", ""))
                shown_count = int(total_match.group(2).replace(".", ""))
            except ValueError:
                pass

        page_match = self.PAGE_RE.search(page_text)

        if page_match:
            try:
                total_pages = int(page_match.group(2))
            except ValueError:
                pass

        if total_pages is None and total_count and shown_count:
            total_pages = math.ceil(total_count / shown_count)

        return total_count, shown_count, total_pages

    def parse_products_from_page(self, html_text):
        soup = BeautifulSoup(html_text, "lxml")

        products = []

        for a in soup.find_all("a", href=True):
            href = a.get("href", "")
            product_url = urljoin(self.BASE_URL, href)
            product_url_lower = product_url.lower().split("?")[0]

            text = self.clean_text(a.get_text(" "))

            if "TL" not in text:
                continue

            # LCW ürün URL'lerinde genelde -o- var.
            if "-o-" not in product_url_lower:
                continue

            price = self.extract_price(text)
            name = self.extract_name(text)

            if not name or not price:
                continue

            if len(name) < 4:
                continue

            products.append((name, price, product_url_lower))

        return products, soup

    def run(self):
        with sync_playwright() as p:
            browser = p.firefox.launch(headless=True)

            page = browser.new_page(
                user_agent=self.HEADERS_USER_AGENT,
                locale="tr-TR",
                viewport={"width": 1366, "height": 900},
            )

            with open(self.OUTPUT_FILE, "w", encoding="utf-8-sig", newline="") as csv_file:
                writer = csv.writer(csv_file, delimiter=";")

                max_pages = None
                empty_page_streak = 0
                page_no = 1

                while True:
                    url = self.build_page_url(page_no)
                    print(f"LCW sayfa başladı: {page_no}")

                    html_text = self.fetch_html(page, url)

                    if not html_text:
                        empty_page_streak += 1

                        if empty_page_streak >= 2:
                            print("2 sayfa üst üste okunamadı, durduruldu.")
                            break

                        page_no += 1
                        continue

                    products, soup = self.parse_products_from_page(html_text)

                    total_count, shown_count, total_pages = self.get_page_info(soup)

                    if max_pages is None:
                        if total_pages:
                            max_pages = total_pages + 2
                        else:
                            max_pages = 50

                        print(f"Tahmini toplam ürün: {total_count if total_count else 'bilinmiyor'}")
                        print(f"Tahmini sayfa sayısı: {max_pages}")

                    new_count = 0

                    for name, price, product_url in products:
                        if product_url in self.seen_product_urls:
                            continue

                        self.seen_product_urls.add(product_url)

                        # CSV formatı: isim;fiyat
                        # Header yok.
                        writer.writerow([name, price])

                        self.total_written += 1
                        new_count += 1

                    csv_file.flush()

                    print(
                        f"Sayfa {page_no}/{max_pages} | "
                        f"yeni ürün: {new_count} | "
                        f"toplam: {self.total_written}"
                    )

                    if page_no > 2 and new_count == 0:
                        empty_page_streak += 1
                    else:
                        empty_page_streak = 0

                    if empty_page_streak >= 2:
                        print("2 sayfa üst üste yeni ürün yok, LCW bitiriliyor.")
                        break

                    if max_pages is not None and page_no >= max_pages:
                        break

                    page_no += 1

                    time.sleep(random.uniform(0.7, 1.4))

            browser.close()

        print("\nBitti.")
        print(f"Dosya: {self.OUTPUT_FILE}")
        print(f"Toplam yazılan ürün: {self.total_written}")


if __name__ == "__main__":
    scraper = LCWHomeScraper()
    scraper.run()