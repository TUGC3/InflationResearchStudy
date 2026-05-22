"""
sahibinden_scraper.py
=====================
Malatya, Elazığ ve Tunceli kiralık daire ilanlarını sahibinden.com'dan çeker.
Her çalıştırmada script'in yanına 3 CSV bırakır:
    malatya_rentals_2026.03.03.csv
    elazig_rentals_2026.03.03.csv
    tunceli_rentals_2026.03.03.csv

Kullanım:
    python sahibinden_scraper.py
    python sahibinden_scraper.py --resume
    python sahibinden_scraper.py --cities malatya tunceli
    python sahibinden_scraper.py -v
"""

import argparse
import csv
import datetime
import json
import logging
import os
import random
import re
import sys
import time
from pathlib import Path
from typing import Callable

import undetected_chromedriver as uc
from bs4 import BeautifulSoup

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── Sabitler ───────────────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).resolve().parent   # Checkpoint ve SeleniumProfile buraya yazılır
TODAY      = datetime.date.today().strftime("%Y.%m.%d")

# ── Repo-relative output paths ────────────────────────────────────────────────
# Bu dosya: InflationItems/Codes/HousesRent/Malatya_Elazig_Tunceli/sahibinden_scraper.py
# Veri:     InflationItems/Datas/HousesRent/Malatya_Elazig_Tunceli/<Şehir>/
REPO_ROOT = Path(__file__).resolve().parents[4]
_BASE_DATA = REPO_ROOT / "InflationItems" / "Datas" / "HousesRent" / "Malatya_Elazig_Tunceli"
CITY_OUT_DIRS = {
    "malatya": _BASE_DATA / "Malatya",
    "elazig":  _BASE_DATA / "Elazig",
    "tunceli": _BASE_DATA / "Tunceli",
}
for _d in CITY_OUT_DIRS.values():
    _d.mkdir(parents=True, exist_ok=True)

CITIES = {
    "malatya": {"url_slug": "malatya", "label": "Malatya"},
    "elazig":  {"url_slug": "elazig",  "label": "Elazığ"},
    "tunceli": {"url_slug": "tunceli", "label": "Tunceli"},
}

SEED_RANGES              = [(0, 9_999_999)]   # Küçük şehirler, tek aralık yeterli
MAX_LISTINGS_PER_QUERY   = 1000               # sahibinden hard cap
MIN_BRACKET_WIDTH        = 50                 # Sonsuz recursionu önler

PAGE_SIZE                 = 50
PAGE_LOAD_DELAY           = 2.5
PAGE_TURN_DELAY_MIN       = 2.0
PAGE_TURN_DELAY_MAX       = 4.0
BETWEEN_BRACKET_DELAY_MIN = 1.0
BETWEEN_BRACKET_DELAY_MAX = 2.0
BETWEEN_CITY_DELAY_MIN    = 5.0
BETWEEN_CITY_DELAY_MAX    = 10.0

SELENIUM_PROFILE_DIR = str(SCRIPT_DIR / "SeleniumProfile")


# ══════════════════════════════════════════════════════════════════════════════
class SahibindenScraper:
    """
    sahibinden.com kiralık daire scraper'ı.
    Adaptive recursive binary splitting + early peek stratejisi kullanır:
      - Herhangi bir price range için sayfa 1 yüklenir, toplam ilan sayısı okunur.
      - count > 1000 → aralık ikiye bölünür, her yarı recursive olarak işlenir.
      - count <= 1000 → tüm sayfalar sırayla çekilir.
    """

    def __init__(self, resume: bool = False):
        self.resume = resume
        self.driver = self._setup_driver()

    # ── Driver ─────────────────────────────────────────────────────────────────

    def _setup_driver(self) -> uc.Chrome:
        options = uc.ChromeOptions()
        options.add_argument(f"--user-data-dir={SELENIUM_PROFILE_DIR}")
        return uc.Chrome(options=options, version_main=147)

    def quit(self):
        self.driver.quit()

    # ── Checkpoint ─────────────────────────────────────────────────────────────

    def _checkpoint_path(self, city_key: str) -> Path:
        return SCRIPT_DIR / f"checkpoint_{city_key}_{TODAY}.json"

    def _load_checkpoint(self, city_key: str) -> dict:
        path = self._checkpoint_path(city_key)
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"done_ranges": []}

    def _save_checkpoint(self, city_key: str, data: dict) -> None:
        with open(self._checkpoint_path(city_key), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    # ── HTML Helpers ───────────────────────────────────────────────────────────

    def _extract_total_listings(self, soup: BeautifulSoup) -> int | None:
        """Sayfadaki toplam ilan sayısını parse eder."""
        res_elem = soup.select_one(".result-text")
        if res_elem:
            text = res_elem.get_text(strip=True).replace(".", "")
            m = re.search(r"(\d+)\s*ilan", text, re.IGNORECASE)
            if m:
                return int(m.group(1))

        for tag in soup.find_all(string=lambda t: t and "ilan" in t.lower()):
            parent = tag.parent
            if parent and parent.name not in ("script", "style", "title"):
                clean = tag.strip().replace(".", "")
                m = re.search(r"(\d+)\s*ilan\s*(?:bulundu|var)", clean, re.IGNORECASE)
                if m:
                    return int(m.group(1))
        return None

    def _resolve_rooms_index(self, soup: BeautifulSoup) -> int | None:
        """Tablo header'larından 'oda' sütununun index'ini bulur."""
        headers = [
            th.get_text(strip=True)
            for th in soup.select(
                "#searchResultsTable thead th.searchResultsAttributeHeader"
            )
        ]
        for idx, header in enumerate(headers):
            if "oda" in header.lower().replace("ı", "i"):
                return idx
        return None

    def _parse_listings(self, soup: BeautifulSoup, rooms_idx: int | None) -> list[dict]:
        records = []
        for row in soup.select("#searchResultsTable tbody tr.searchResultsItem"):
            try:
                price_elem = row.select_one(".searchResultsPriceValue")
                price = price_elem.text.strip() if price_elem else None

                loc_elem = row.select_one(".searchResultsLocationValue")
                district = " / ".join(loc_elem.stripped_strings) if loc_elem else "N/A"

                attrs = row.select(".searchResultsAttributeValue")
                if rooms_idx is not None and len(attrs) > rooms_idx:
                    rooms = attrs[rooms_idx].text.strip()
                elif len(attrs) > 1:
                    rooms = attrs[1].text.strip()
                else:
                    rooms = "N/A"

                if price:
                    records.append({"District": district, "Rooms": rooms, "Price": price})
            except Exception as exc:
                logger.debug("Satır parse hatası: %s", exc)
        return records

    def _wait_for_listings(self) -> BeautifulSoup:
        """Sayfa yüklenmesini bekler. CAPTCHA tespit ederse kullanıcıdan müdahale ister."""
        time.sleep(PAGE_LOAD_DELAY)
        soup = BeautifulSoup(self.driver.page_source, "html.parser")
        listings = soup.select("#searchResultsTable tbody tr.searchResultsItem")

        if not listings:
            page_lower = self.driver.page_source.lower()
            if "ilan bulunamadı" in page_lower or "bulunamamıştır" in page_lower:
                return soup  # Gerçekten boş

            print("\n" + "=" * 60)
            print("⚠️  CAPTCHA veya giriş engeli tespit edildi!")
            print("   1. Chrome penceresini açın ve doğrulamayı tamamlayın.")
            print("   2. İlan listesinin göründüğünden emin olun.")
            print("=" * 60)
            input("   ▶ İlanlar görününce ENTER'a basın… ")
            soup = BeautifulSoup(self.driver.page_source, "html.parser")

        return soup

    # ── CSV Output ─────────────────────────────────────────────────────────────

    def _csv_path(self, city_key: str) -> Path:
        return CITY_OUT_DIRS[city_key] / f"{city_key}_rentals_{TODAY}.csv"

    def _save_to_csv(self, records: list[dict], city_key: str) -> None:
        path = self._csv_path(city_key)
        file_exists = path.exists()
        with open(path, mode="a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["District", "Rooms", "Price"])
            if not file_exists:
                writer.writeheader()
            writer.writerows(records)

    # ── Core: Adaptive Scrape ──────────────────────────────────────────────────

    def _scrape_range(
        self,
        city_key: str,
        url_slug: str,
        min_price: int,
        max_price: int,
        done_ranges: set[tuple[int, int]],
        save_checkpoint_fn: Callable[[int, int], None],
        indent: int = 0,
    ) -> int:
        """
        [min_price, max_price] için early peek uygular.
        Gerekirse ikiye böler (recursive), güvenliyse tüm sayfaları çeker.
        """
        pad = "  " * indent

        if (min_price, max_price) in done_ranges:
            logger.info("%s↩  Zaten tamamlandı, atlıyorum: %d–%d TL", pad, min_price, max_price)
            return 0

        width = max_price - min_price
        logger.info("%s▶  Kontrol ediliyor: %d–%d TL…", pad, min_price, max_price)

        url = (
            f"https://www.sahibinden.com/kiralik/{url_slug}"
            f"?pagingSize={PAGE_SIZE}&price_min={min_price}&price_max={max_price}"
        )
        self.driver.get(url)
        soup = self._wait_for_listings()

        total_listings = self._extract_total_listings(soup)

        # ── Split kararı ──────────────────────────────────────────────────────
        if (
            total_listings is not None
            and total_listings > MAX_LISTINGS_PER_QUERY
            and width > MIN_BRACKET_WIDTH
        ):
            logger.info("%s   ✂️  Çok yoğun (%d ilan). İkiye bölünüyor…", pad, total_listings)
            mid = (min_price + max_price) // 2
            saved  = self._scrape_range(city_key, url_slug, min_price, mid,
                                        done_ranges, save_checkpoint_fn, indent + 1)
            time.sleep(random.uniform(BETWEEN_BRACKET_DELAY_MIN, BETWEEN_BRACKET_DELAY_MAX))
            saved += self._scrape_range(city_key, url_slug, mid + 1, max_price,
                                        done_ranges, save_checkpoint_fn, indent + 1)
            return saved

        if total_listings is not None and total_listings > MAX_LISTINGS_PER_QUERY:
            logger.warning("%s   ⚠  Min genişliğe ulaşıldı ama count hâlâ >1000. Mevcut veri kaydediliyor.", pad)
        elif total_listings is not None:
            logger.info("%s   ✓  Güvenli aralık (%d ilan). Tüm sayfalar çekiliyor.", pad, total_listings)
        else:
            # total_listings parse edilemiyorsa sahibinden'in önerilen ilanlar
            # sayfası gösterdiği anlamına gelir — gerçek sonuç yok, atla.
            logger.info("%s   ⊘  Sonuç yok (önerilen ilanlar), atlanıyor: %d–%d TL", pad, min_price, max_price)
            save_checkpoint_fn(min_price, max_price)
            done_ranges.add((min_price, max_price))
            return 0

        # ── Tüm sayfaları çek ─────────────────────────────────────────────────
        records: list[dict] = []
        rooms_idx = self._resolve_rooms_index(soup)
        page_num = 1

        while True:
            page_records = self._parse_listings(soup, rooms_idx)
            records.extend(page_records)

            if page_records:
                logger.info(
                    "%s     Sayfa %2d: %2d ilan (toplam: %d) | %d–%d TL",
                    pad, page_num, len(page_records), len(records), min_price, max_price,
                )

            next_btn = soup.find("a", title="Sonraki")
            if page_num >= 20 or not next_btn:
                break

            next_url = "https://www.sahibinden.com" + next_btn["href"]
            self.driver.get(next_url)
            page_num += 1
            time.sleep(random.uniform(PAGE_TURN_DELAY_MIN, PAGE_TURN_DELAY_MAX))
            soup = self._wait_for_listings()

            if rooms_idx is None:
                rooms_idx = self._resolve_rooms_index(soup)

        # ── Kaydet & checkpoint ───────────────────────────────────────────────
        if records:
            self._save_to_csv(records, city_key)
            logger.info("%s✅ %d kayıt kaydedildi (%d–%d TL).", pad, len(records), min_price, max_price)

        save_checkpoint_fn(min_price, max_price)
        done_ranges.add((min_price, max_price))
        return len(records)

    # ── Public: Şehir Çek ──────────────────────────────────────────────────────

    def scrape_city(self, city_key: str) -> int:
        city_cfg = CITIES[city_key]
        label    = city_cfg["label"]
        csv_path = self._csv_path(city_key)

        logger.info("")
        logger.info("=" * 60)
        logger.info("  🏙️  %s scrape'i başlatılıyor…", label)
        logger.info("  📄  Çıktı: %s", csv_path)
        logger.info("=" * 60)

        checkpoint  = self._load_checkpoint(city_key) if self.resume else {"done_ranges": []}
        done_ranges = {tuple(r) for r in checkpoint["done_ranges"]}

        if not self.resume:
            if csv_path.exists():
                csv_path.unlink()
                logger.info("Eski CSV silindi: %s", csv_path)
            self._save_checkpoint(city_key, {"done_ranges": []})
            done_ranges = set()

        def mark_done(min_p: int, max_p: int) -> None:
            done_ranges.add((min_p, max_p))
            checkpoint["done_ranges"] = [list(r) for r in done_ranges]
            self._save_checkpoint(city_key, checkpoint)

        total_saved = 0
        for seed_min, seed_max in SEED_RANGES:
            total_saved += self._scrape_range(
                city_key=city_key,
                url_slug=city_cfg["url_slug"],
                min_price=seed_min,
                max_price=seed_max,
                done_ranges=done_ranges,
                save_checkpoint_fn=mark_done,
            )
            time.sleep(random.uniform(BETWEEN_BRACKET_DELAY_MIN, BETWEEN_BRACKET_DELAY_MAX))

        logger.info("✅ %s tamamlandı. Toplam kayıt: %d", label, total_saved)
        return total_saved

    # ── Public: Tüm Şehirler ──────────────────────────────────────────────────

    def scrape_all(self, cities: list[str] | None = None) -> None:
        targets = cities if cities else list(CITIES.keys())

        for idx, city_key in enumerate(targets):
            self.scrape_city(city_key)

            if idx < len(targets) - 1:
                delay = random.uniform(BETWEEN_CITY_DELAY_MIN, BETWEEN_CITY_DELAY_MAX)
                logger.info("Sonraki şehir için %.1f saniye bekleniyor…", delay)
                time.sleep(delay)

        logger.info("")
        logger.info("=" * 60)
        logger.info("  🎉  Tüm şehirler tamamlandı!")
        logger.info("  📁  CSV'ler repo'ya yazıldı:")
        for city_key in targets:
            p = self._csv_path(city_key)
            logger.info("  %s  %s", "✓" if p.exists() else "✗", p)
        logger.info("=" * 60)


# ── CLI ────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="sahibinden_scraper",
        description="Malatya, Elazığ, Tunceli kiralık daire scraper.",
    )
    parser.add_argument("--resume", action="store_true",
                        help="Bugünkü checkpoint'ten kaldığı yerden devam et.")
    parser.add_argument("--cities", nargs="+", choices=list(CITIES.keys()),
                        metavar="CITY",
                        help="Sadece belirtilen şehirleri çek. Örnek: --cities malatya")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Debug seviyesinde loglama.")
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    scraper = SahibindenScraper(resume=args.resume)
    try:
        scraper.scrape_all(cities=args.cities)
    finally:
        scraper.quit()


if __name__ == "__main__":
    main()