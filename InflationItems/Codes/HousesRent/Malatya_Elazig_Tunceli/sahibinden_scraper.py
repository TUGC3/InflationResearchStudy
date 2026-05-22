"""
sahibinden_scraper.py — Mevcut Chrome'a baglanan scraper
=========================================================
Malatya, Elazig ve Tunceli kiralik daire ilanlarini sahibinden.com'dan ceker.

Strateji:
  1. Kullanici Chrome'u --remote-debugging-port=9222 ile acar
  2. Sahibinden.com'a gidip Cloudflare'i manual gecer
  3. Script ayni Chrome'a CDP uzerinden baglanir
  4. Otomasyon izi YOK — normal Chrome, sadece CDP port acik

Kullanim:
  Adim 1 — Chrome'u kapat, sonra su komutla ac:
    "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe" --remote-debugging-port=9222

  Adim 2 — Chrome'da sahibinden.com/kiralik adresine git, Cloudflare'i gec

  Adim 3 — Script'i calistir:
    python sahibinden_scraper.py --cities malatya
    python sahibinden_scraper.py
    python sahibinden_scraper.py --resume
"""

import argparse
import csv
import datetime
import json
import logging
import random
import re
import time
from pathlib import Path

from DrissionPage import ChromiumPage
from lxml import html as lxml_html

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── Sabitler ───────────────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).resolve().parent
TODAY      = datetime.date.today().strftime("%Y.%m.%d")

# ── Repo-relative output paths ────────────────────────────────────────────────
REPO_ROOT  = Path(__file__).resolve().parents[4]
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
    "elazig":  {"url_slug": "elazig",  "label": "Elazig"},
    "tunceli": {"url_slug": "tunceli", "label": "Tunceli"},
}

SEED_RANGES            = [(0, 9_999_999)]
MAX_LISTINGS_PER_QUERY = 1000
MIN_BRACKET_WIDTH      = 50
PAGE_SIZE              = 50

REQUEST_DELAY_MIN      = 2.0
REQUEST_DELAY_MAX      = 4.0
BETWEEN_BRACKET_DELAY  = (1.5, 3.0)


# ══════════════════════════════════════════════════════════════════════════════
# BROWSER CONNECTION
# ══════════════════════════════════════════════════════════════════════════════

def connect_to_chrome() -> ChromiumPage:
    """
    Chrome'a baglanir. Zaten port 9222'de aciksa ona baglanir,
    yoksa Chrome'u otomatik baslatir.
    """
    import subprocess, socket

    def _port_open():
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            return s.connect_ex(("127.0.0.1", 9222)) == 0

    # 1. Zaten acik mi?
    if _port_open():
        logger.info("Port 9222 acik — mevcut Chrome'a baglaniyor.")
    else:
        # 2. Chrome'u debug port ile baslat
        logger.info("Chrome baslatiliyor (port 9222)...")
        chrome_paths = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        ]
        chrome_exe = None
        for p in chrome_paths:
            if Path(p).exists():
                chrome_exe = p
                break

        if not chrome_exe:
            logger.error("Chrome bulunamadi!")
            raise SystemExit(1)

        subprocess.Popen([
            chrome_exe,
            "--remote-debugging-port=9222",
        ])
        # Chrome'un acilmasini bekle
        for _ in range(15):
            time.sleep(1)
            if _port_open():
                break
        else:
            logger.error("Chrome baslatilamadi.")
            raise SystemExit(1)

    page = ChromiumPage(addr_or_opts="127.0.0.1:9222")
    logger.info("Chrome'a basariyla baglandi.")
    return page


def wait_for_listings(page, timeout: int = 120) -> bool:
    """Ilan listesinin yuklenmesini bekler."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            html = page.html
            if "searchResultsTable" in html or "searchResultsItem" in html:
                return True
            if "result-text" in html and "ilan" in html.lower():
                return True
        except Exception:
            pass
        time.sleep(2)
    return False


def fetch_page(page, url: str) -> str | None:
    """Sayfa yukler, tablo renderini bekler ve HTML doner."""
    try:
        page.get(url)

        # Tablo renderini bekle (max 15 sn)
        for _ in range(30):
            time.sleep(0.5)
            html = page.html
            if "searchResultsItem" in html:
                # Tablo yuklendi, ekstra kisa bekleme
                time.sleep(random.uniform(0.5, 1.0))
                return page.html
            # Cloudflare challenge kontrolu
            if "basili tutun" in html.lower() or "baglantiniz kontrol" in html.lower():
                logger.warning("Cloudflare challenge cikti — manual gecis gerekiyor.")
                print("\n  >>> Cloudflare challenge cikti! Lutfen gecin... <<<\n")
                if not wait_for_listings(page, timeout=60):
                    return None
                return page.html

        # 15 sn doldu, tablo bulunamadi — yine de HTML don
        logger.warning("Tablo elementi bulunamadi, mevcut HTML donduruluyor.")
        time.sleep(random.uniform(REQUEST_DELAY_MIN, REQUEST_DELAY_MAX))
        return page.html
    except Exception as exc:
        logger.error("Sayfa yukleme hatasi: %s", exc)
        return None


# ══════════════════════════════════════════════════════════════════════════════
# HTML PARSERS
# ══════════════════════════════════════════════════════════════════════════════

def extract_total_listings(html: str) -> int | None:
    """Sayfadaki toplam ilan sayisini parse eder."""
    tree = lxml_html.fromstring(html)

    result_texts = tree.xpath('//*[contains(@class, "result-text")]//text()')
    full_text = " ".join(t.strip() for t in result_texts if t.strip())
    if full_text:
        clean = full_text.replace(".", "")
        m = re.search(r"(\d+)\s*ilan", clean, re.IGNORECASE)
        if m:
            return int(m.group(1))

    all_text = tree.text_content()
    clean = all_text.replace(".", "")
    m = re.search(r"(\d+)\s*ilan\s*(?:bulundu|var)", clean, re.IGNORECASE)
    if m:
        return int(m.group(1))

    return None


def resolve_rooms_index(tree) -> int | None:
    """Tablo header'larindan 'oda' sutununun index'ini bulur."""
    headers = tree.xpath(
        '//table[@id="searchResultsTable"]//thead//th[contains(@class, "searchResultsAttributeHeader")]'
    )
    for idx, th in enumerate(headers):
        text = (th.text_content() or "").strip().lower().replace("\u0131", "i")
        if "oda" in text:
            return idx
    return None


def parse_listings(html: str, rooms_idx: int | None) -> list[dict]:
    """Listing tablosundan kayitlari cikarir."""
    tree = lxml_html.fromstring(html)
    records = []

    rows = tree.xpath('//table[@id="searchResultsTable"]//tbody//tr[contains(@class, "searchResultsItem")]')
    logger.debug("parse_listings: %d row bulundu", len(rows))

    # Fallback: id olmadan class-based ara
    if not rows:
        rows = tree.xpath('//tr[contains(@class, "searchResultsItem")]')
        logger.debug("parse_listings fallback: %d row bulundu", len(rows))

    if rooms_idx is None:
        rooms_idx = resolve_rooms_index(tree)

    for row in rows:
        try:
            price_elems = row.xpath('.//*[contains(@class, "searchResultsPriceValue")]//text()')
            price = " ".join(t.strip() for t in price_elems if t.strip()) or None

            loc_elems = row.xpath('.//*[contains(@class, "searchResultsLocationValue")]//text()')
            district = " / ".join(t.strip() for t in loc_elems if t.strip()) or "N/A"

            attrs = row.xpath('.//*[contains(@class, "searchResultsAttributeValue")]')
            if rooms_idx is not None and len(attrs) > rooms_idx:
                rooms = (attrs[rooms_idx].text_content() or "").strip()
            elif len(attrs) > 1:
                rooms = (attrs[1].text_content() or "").strip()
            else:
                rooms = "N/A"

            if price:
                records.append({"District": district, "Rooms": rooms, "Price": price})
        except Exception as exc:
            logger.debug("Satir parse hatasi: %s", exc)

    return records


# ══════════════════════════════════════════════════════════════════════════════
# SCRAPER
# ══════════════════════════════════════════════════════════════════════════════

class SahibindenScraper:
    """Tek sehir icin scraper."""

    def __init__(self, city_key: str, browser_page, resume: bool = False):
        self.city_key = city_key
        self.page     = browser_page
        self.resume   = resume

    def _fetch(self, url: str) -> str | None:
        return fetch_page(self.page, url)

    # ── Checkpoint ─────────────────────────────────────────────────────────────

    def _checkpoint_path(self) -> Path:
        return SCRIPT_DIR / f"checkpoint_{self.city_key}_{TODAY}.json"

    def _load_checkpoint(self) -> dict:
        path = self._checkpoint_path()
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"done_ranges": []}

    def _save_checkpoint(self, data: dict) -> None:
        with open(self._checkpoint_path(), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    # ── CSV output ─────────────────────────────────────────────────────────────

    def _csv_path(self) -> Path:
        return CITY_OUT_DIRS[self.city_key] / f"{self.city_key}_rentals_{TODAY}.csv"

    def _save_to_csv(self, records: list[dict]) -> None:
        path = self._csv_path()
        file_exists = path.exists()
        with open(path, mode="a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["District", "Rooms", "Price"])
            if not file_exists:
                writer.writeheader()
            writer.writerows(records)

    # ── Core: adaptive binary split ────────────────────────────────────────────

    def _scrape_range(
        self,
        url_slug: str,
        min_price: int,
        max_price: int,
        done_ranges: set[tuple[int, int]],
        checkpoint: dict,
        indent: int = 0,
    ) -> int:
        pad = "  " * indent

        if (min_price, max_price) in done_ranges:
            logger.info("%s  Zaten tamamlandi: %d-%d TL", pad, min_price, max_price)
            return 0

        width = max_price - min_price
        logger.info("%s>  Kontrol: %d-%d TL...", pad, min_price, max_price)

        url = (
            f"https://www.sahibinden.com/kiralik/{url_slug}"
            f"?pagingSize={PAGE_SIZE}&price_min={min_price}&price_max={max_price}"
        )
        html = self._fetch(url)

        if html is None:
            logger.error("%s   X  Sayfa alinamadi. Durduruluyor.", pad)
            return 0

        total_listings = extract_total_listings(html)

        if (
            total_listings is not None
            and total_listings > MAX_LISTINGS_PER_QUERY
            and width > MIN_BRACKET_WIDTH
        ):
            logger.info("%s   %d ilan — ikiye bolunuyor...", pad, total_listings)
            mid = (min_price + max_price) // 2
            saved  = self._scrape_range(url_slug, min_price, mid,    done_ranges, checkpoint, indent+1)
            time.sleep(random.uniform(*BETWEEN_BRACKET_DELAY))
            saved += self._scrape_range(url_slug, mid+1, max_price, done_ranges, checkpoint, indent+1)
            return saved

        if total_listings is None:
            logger.info("%s   Sonuc yok, atlaniyor: %d-%d TL", pad, min_price, max_price)
            done_ranges.add((min_price, max_price))
            checkpoint["done_ranges"] = [list(r) for r in done_ranges]
            self._save_checkpoint(checkpoint)
            return 0

        if total_listings > MAX_LISTINGS_PER_QUERY:
            logger.warning("%s   Min genislikte cap asildi, mevcut veri kaydediliyor.", pad)
        else:
            logger.info("%s   %d ilan — sayfalar cekiliyor.", pad, total_listings)

        records: list[dict] = []
        rooms_idx = None
        page_num  = 1

        while True:
            if html is None:
                break
            page_records = parse_listings(html, rooms_idx)
            records.extend(page_records)
            if page_records:
                logger.info(
                    "%s     Sayfa %2d: %2d ilan (toplam: %d) | %d-%d TL",
                    pad, page_num, len(page_records), len(records), min_price, max_price,
                )

            tree = lxml_html.fromstring(html)
            next_links = tree.xpath('//a[@title="Sonraki"]/@href')
            if page_num >= 20 or not next_links:
                break

            next_url = "https://www.sahibinden.com" + next_links[0]
            html = self._fetch(next_url)
            page_num += 1

        if records:
            self._save_to_csv(records)
            logger.info("%s  %d kayit kaydedildi (%d-%d TL).", pad, len(records), min_price, max_price)

        done_ranges.add((min_price, max_price))
        checkpoint["done_ranges"] = [list(r) for r in done_ranges]
        self._save_checkpoint(checkpoint)
        return len(records)

    # ── Public ─────────────────────────────────────────────────────────────────

    def scrape_city(self) -> int:
        city_cfg = CITIES[self.city_key]
        label    = city_cfg["label"]
        csv_path = self._csv_path()

        logger.info("")
        logger.info("=" * 55)
        logger.info("  %s baslatiliyor...", label)
        logger.info("  Cikti: %s", csv_path)
        logger.info("=" * 55)

        checkpoint  = self._load_checkpoint() if self.resume else {"done_ranges": []}
        done_ranges = {tuple(r) for r in checkpoint["done_ranges"]}

        if not self.resume:
            if csv_path.exists():
                csv_path.unlink()
                logger.info("Eski CSV silindi: %s", csv_path)
            self._save_checkpoint({"done_ranges": []})
            done_ranges = set()

        total_saved = 0
        for seed_min, seed_max in SEED_RANGES:
            total_saved += self._scrape_range(
                city_cfg["url_slug"], seed_min, seed_max, done_ranges, checkpoint,
            )
            time.sleep(random.uniform(*BETWEEN_BRACKET_DELAY))

        logger.info("  %s tamamlandi. Toplam kayit: %d", label, total_saved)
        return total_saved


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="sahibinden_scraper",
        description="Malatya, Elazig, Tunceli kiralik daire scraper.",
    )
    parser.add_argument("--resume", action="store_true",
                        help="Bugunku checkpoint'ten devam et.")
    parser.add_argument("--cities", nargs="+", choices=list(CITIES.keys()),
                        metavar="CITY",
                        help="Sadece bu sehirleri cek.")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Debug loglama.")
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    cities = args.cities or list(CITIES.keys())

    # 1. Mevcut Chrome'a baglan
    page = connect_to_chrome()

    # 2. Kullanicinin Cloudflare'i gecmesini bekle (script navigate ETMEZ)
    print("\n" + "=" * 60)
    print("  Chrome'a baglandi!")
    print("  " + "-" * 54)
    print("  Simdi Chrome'da su adimlari yapin:")
    print("    1. sahibinden.com/kiralik adresine gidin")
    print("    2. Cloudflare challenge'i gecin (basili tut vs.)")
    print("    3. Ilan listesinin gorundugundan emin olun")
    print("=" * 60)
    input("  Ilanlar gorunuyor mu? ENTER'a basin... ")

    # Dogrulama: ilan listesi var mi?
    html = page.html
    if "searchResultsTable" not in html and "searchResultsItem" not in html:
        logger.warning("Ilan listesi tespit edilemedi, yine de devam ediliyor...")

    logger.info("Baglanti basarili — scraping basliyor.")

    # 3. Sehirleri sirayla calistir
    results: dict[str, int | Exception] = {}

    for city_key in cities:
        try:
            scraper = SahibindenScraper(city_key, page, resume=args.resume)
            count = scraper.scrape_city()
            results[city_key] = count
        except Exception as exc:
            results[city_key] = exc
            logger.error("[%s] Hata: %s", city_key, exc)

    # 4. Ozet
    print(f"\n{'='*55}")
    print("  Tamamlandi!")
    for city_key in cities:
        label  = CITIES[city_key]["label"]
        result = results.get(city_key, "—")
        if isinstance(result, Exception):
            print(f"  X  {label}: HATA — {result}")
        else:
            csv_p = CITY_OUT_DIRS[city_key] / f"{city_key}_rentals_{TODAY}.csv"
            mark  = "+" if csv_p.exists() else "X"
            print(f"  {mark}  {label}: {result} kayit -> {csv_p}")
    print(f"{'='*55}\n")


if __name__ == "__main__":
    main()
