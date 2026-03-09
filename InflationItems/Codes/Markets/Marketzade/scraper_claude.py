"""
=============================================================
  Marketzade Web Scraper — AI201 Intro to Data Science
  Sınıf Adı  : scraper_claude
  CSV Çıktısı: YYYY-MM-DD.csv  (o günün tarihi)

  KURULUM (PyCharm Terminali):
      pip install selenium webdriver-manager beautifulsoup4 lxml
=============================================================
"""

import csv
import time
import os
import re
import logging
import sys
from datetime import    date

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


class scraper_claude:

    CSV_HEADERS = ["tarih", "kategori", "urun_adi", "fiyat", "para_birimi"]

    CATEGORIES = {
        "temel-gida":    "https://marketzade.com/temel-gida/",
        "kahvaltilik":   "https://marketzade.com/kahvaltiliklar/",
        "atistirmalik":  "https://marketzade.com/atistirmalik/",
        "icecek":        "https://marketzade.com/icecek/",
        "anne-bebek":    "https://marketzade.com/anne-bebek/",
        "kisisel-bakim": "https://marketzade.com/kisisel-bakim-kozmetik/",
        "temizlik":      "https://marketzade.com/temizlik-urunleri/",
        "petshop":       "https://marketzade.com/petshop/",
        "ev-yasam":      "https://marketzade.com/ev-yasam-hirdavat/",
    }

    PAGE_LOAD_WAIT = 15
    SCROLL_PAUSE   = 3.0
    MAX_STALE      = 5

    def __init__(self):
        self.today         = str(date.today())
        self.csv_file      = f"{self.today}.csv"
        self.total_scraped = 0
        self._ensure_file()
        self.driver = self._init_driver()

    # ── CHROME DRIVER ─────────────────────────────────────────
    def _init_driver(self) -> webdriver.Chrome:
        opts = Options()
        opts.add_argument("--headless=new")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")
        opts.add_argument("--window-size=1920,1080")
        opts.add_argument("--disable-blink-features=AutomationControlled")
        opts.add_experimental_option("excludeSwitches", ["enable-automation"])
        opts.add_experimental_option("useAutomationExtension", False)
        opts.add_argument(
            "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        )
        service = Service(ChromeDriverManager().install())
        driver  = webdriver.Chrome(service=service, options=opts)
        driver.execute_cdp_cmd(
            "Page.addScriptToEvaluateOnNewDocument",
            {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"}
        )
        log.info("Chrome driver başlatıldı (headless mod)")
        return driver

    # ── DOSYA YÖNETİMİ ────────────────────────────────────────
    def _ensure_file(self):
        if os.path.exists(self.csv_file):
            log.error(
                f"⛔ DURDURULDU: {self.today} için '{self.csv_file}' zaten mevcut!\n"
                f"   Bugün ikinci kez çalıştırıyorsunuz. Tekrar veri eklenmedi."
            )
            sys.exit(0)

        with open(self.csv_file, "w", newline="", encoding="utf-8-sig") as f:
            csv.DictWriter(f, fieldnames=self.CSV_HEADERS).writeheader()
        log.info(f"Dosya oluşturuldu: {self.csv_file}")

    def _save_products(self, products: list):
        if not products:
            return
        with open(self.csv_file, "a", newline="", encoding="utf-8-sig") as f:
            csv.DictWriter(f, fieldnames=self.CSV_HEADERS).writerows(products)
        self.total_scraped += len(products)

    # ── INFINITE SCROLL ───────────────────────────────────────
    def _load_all_products(self, url: str):
        try:
            self.driver.get(url)
            WebDriverWait(self.driver, self.PAGE_LOAD_WAIT).until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "li.product, .wd-product, .product-grid-item")
                )
            )
        except TimeoutException:
            log.warning(f"Timeout — ilk ürünler {self.PAGE_LOAD_WAIT}sn'de gelmedi: {url}")
            return BeautifulSoup(self.driver.page_source, "lxml")
        except Exception as e:
            log.error(f"Sayfa açılamadı: {url} | {e}")
            return None

        stale_count  = 0
        last_count   = 0
        scroll_round = 0

        while stale_count < self.MAX_STALE:
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(self.SCROLL_PAUSE)
            cards = self.driver.find_elements(
                By.CSS_SELECTOR, "li.product, .wd-product, .product-grid-item"
            )
            current_count = len(cards)
            scroll_round += 1
            if current_count > last_count:
                log.info(f"  Scroll {scroll_round}: {current_count} ürün yüklendi (+{current_count - last_count})")
                last_count  = current_count
                stale_count = 0
            else:
                stale_count += 1
                log.info(f"  Scroll {scroll_round}: yeni ürün yok ({stale_count}/{self.MAX_STALE})")

        log.info(f"  Toplam {last_count} ürün yüklendi, parse ediliyor...")
        return BeautifulSoup(self.driver.page_source, "lxml")

    # ── ÜRÜN AYIKLAMA ─────────────────────────────────────────
    def _parse_products(self, soup: BeautifulSoup, category: str) -> list:
        products   = []
        seen_names = set()

        cards = (
            soup.select("li.product")
            or soup.select(".wd-product")
            or soup.select(".product-grid-item")
            or soup.select("[class*='product type-product']")
        )

        if not cards:
            log.warning("  Ürün kartı bulunamadı.")
            return products

        for card in cards:
            name  = self._extract_name(card)
            fiyat = self._extract_price(card)
            if not name or name in seen_names:
                continue
            seen_names.add(name)
            products.append({
                "tarih":       self.today,
                "kategori":    category,
                "urun_adi":    name,
                "fiyat":       fiyat,
                "para_birimi": "TRY",
            })

        return products

    def _extract_name(self, card) -> str:
        for sel in [
            ".woocommerce-loop-product__title",
            "h2.title", "h3.title", ".product-title", "h2", "h3",
        ]:
            el = card.select_one(sel)
            if el:
                return el.get_text(strip=True)
        return ""

    def _extract_price(self, card) -> str:
        box = card.select_one(".price")
        if not box:
            return ""
        ins_t = box.select_one("ins .woocommerce-Price-amount bdi, ins .amount")
        if ins_t:
            return self._clean(ins_t.get_text())
        single = box.select_one(".woocommerce-Price-amount bdi, .amount")
        if single:
            return self._clean(single.get_text())
        return self._clean(box.get_text(strip=True))

    @staticmethod
    def _clean(raw: str) -> str:
        s = raw.replace("₺", "").replace("TL", "").strip()
        s = s.replace(".", "").replace(",", ".")
        return re.sub(r"[^\d.]", "", s)

    # ── KATEGORİ SCRAPE ───────────────────────────────────────
    def _scrape_category(self, category: str, url: str):
        log.info(f"▶ Kategori: {category}")
        soup = self._load_all_products(url)
        if not soup:
            log.error(f"  {category} atlandı.")
            return
        products = self._parse_products(soup, category)
        self._save_products(products)
        log.info(f"  ✓ {category}: {len(products)} ürün kaydedildi.\n")

    # ── ANA ÇALIŞTIRICI ───────────────────────────────────────
    def run(self):
        log.info("=" * 55)
        log.info(f"  Marketzade Scraper — {self.today}")
        log.info("=" * 55)
        try:
            for category, url in self.CATEGORIES.items():
                try:
                    self._scrape_category(category, url)
                except Exception as e:
                    log.error(f"Kategori '{category}' hatası: {e}")
        finally:
            self.driver.quit()
            log.info("Chrome driver kapatıldı.")
        log.info("=" * 55)
        log.info(f"  TAMAMLANDI — {self.total_scraped} ürün → '{self.csv_file}'")
        log.info("=" * 55)


if __name__ == "__main__":
    scraper = scraper_claude()
    scraper.run()