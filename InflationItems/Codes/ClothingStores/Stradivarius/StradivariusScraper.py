"""
stradivarius_scraper.py
=======================
Stradivarius Türkiye ürün verisi çekici.

Kullanım:
    python stradivarius_scraper.py

Çıktı: stradivarius_YYYY-MM-DD.csv
Kolonlar: category, product_name, price

Bağımlılıklar:
    pip install curl_cffi tqdm

API Sabitleri (STORE_ID / REGION_ID):
    DevTools → Network → itxrest filtresi ile doğrudan URL'den okunabilir:
    https://www.stradivarius.com/itxrest/2/catalog/store/54009571/50331081/...
    STORE_ID  = 54009571   (Stradivarius TR mağaza tanımlayıcısı)
    REGION_ID = 50331081   (Inditex TR bölge tanımlayıcısı)
"""

import csv
import logging
import time
import random
from datetime import date
from pathlib import Path
from typing import Optional

from curl_cffi import requests
from tqdm import tqdm

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Sabitler
# ---------------------------------------------------------------------------

# Stradivarius menüsünde hem gerçek ürün kategorileri (Tişört, Jean vb.)
# hem de editoryal/kampanya kategorileri (Yeni koleksiyon, Tümü vb.) var.
# Dedup first-seen kazanır; gerçek kategorileri önce işleyerek doğru etiket atılır.
EDITORIAL_PARENTS = {
    "yeni koleksiyon", "yeni", "tümü", "ürüne göre alışveriş",
    "ürüne göre satın al", "stradimarket", "denim hub",
}

# Stradivarius iç SEO etiketleri — örn. "Sweatshirt > STR_VER_SUDA_GRISES_SEO"
# Bu prefix'i içeren child kategoriler parent ismiyle değiştirilir.
SEO_PREFIX = "STR_VER_SUDA_"


# ---------------------------------------------------------------------------
# Kategori yolu temizleyici
# ---------------------------------------------------------------------------

def _clean_category(parent: Optional[str], cat_name: str) -> str:
    """
    Ham kategori ağacından okunabilir kategori yolu üretir.

    Kurallar (öncelik sırasıyla):
    1. cat_name STR_VER_SUDA_ ile başlıyorsa        → parent'ı kullan
       Örn: "Sweatshirt > STR_VER_SUDA_GRISES_SEO"  → "Sweatshirt"

    2. cat_name "Tümünü gör" veya "Tümü" ise:
       - parent "Tümü" ise                           → "Aksesuar"
       - diğer durumlarda                            → parent'ı kullan
       Örn: "Jean > Tümünü gör"                      → "Jean"
       Örn: "Tümü > Tümü"                            → "Aksesuar"

    3. parent "Tümü" ise                             → cat_name'i kullan
       Örn: "Tümü > Güneş gözlüğü"                  → "Güneş gözlüğü"
       Örn: "Tümü > Parfüm"                          → "Parfüm"

    4. Diğer durumlarda                              → "parent > cat_name"
       Örn: "Jean > D91"                             → "Jean > D91"
       Örn: (None, "Bijuteri")                       → "Bijuteri"
    """
    # Kural 1: SEO etiketleri
    if cat_name.startswith(SEO_PREFIX):
        return parent if parent else cat_name

    # Kural 2: "Tümünü gör" / "Tümü" child
    if cat_name.strip() in ("Tümünü gör", "Tümü"):
        if parent and parent.strip().lower() == "tümü":
            return "Aksesuar"
        return parent if parent else cat_name

    # Kural 3: parent "Tümü" → child daha anlamlı
    if parent and parent.strip().lower() == "tümü":
        return cat_name

    # Kural 4: normal
    return f"{parent} > {cat_name}" if parent else cat_name


# ---------------------------------------------------------------------------
# Scraper
# ---------------------------------------------------------------------------

class StradivariusScraper:

    STORE_ID    = "54009571"
    REGION_ID   = "50331081"
    LANGUAGE_ID = "-43"
    APP_ID      = "1"

    BASE_URL       = "https://www.stradivarius.com"
    CATALOG_V2_URL = f"{BASE_URL}/itxrest/2/catalog/store/{STORE_ID}/{REGION_ID}"
    CATALOG_V3_URL = f"{BASE_URL}/itxrest/3/catalog/store/{STORE_ID}/{REGION_ID}"

    BATCH_SIZE       = 20
    MAX_RETRIES      = 5
    RETRY_BACKOFF    = 3
    RATE_LIMIT_SLEEP = 60

    DEFAULT_HEADERS = {
        "Accept":          "*/*",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
        "Connection":      "keep-alive",
        "Content-Type":    "application/json",
        "Referer":         "https://www.stradivarius.com/tr/",
        "Sec-Fetch-Dest":  "empty",
        "Sec-Fetch-Mode":  "cors",
        "Sec-Fetch-Site":  "same-origin",
    }

    def __init__(self, output_dir: str = ".", delay: float = 0.5):
        self.output_dir = Path(output_dir)
        self.delay      = delay
        self._session: Optional[requests.Session] = None

    # ── Session ──────────────────────────────────────────────────────────────

    def _make_session(self) -> requests.Session:
        session = requests.Session(impersonate="chrome")
        session.headers.update(self.DEFAULT_HEADERS)
        return session

    def _warmup(self) -> None:
        """Akamai cookie'lerini toplamak için homepage'i ziyaret eder."""
        try:
            resp = self._session.get(f"{self.BASE_URL}/tr/", timeout=20)
            logger.debug("Warmup tamamlandi: HTTP %d", resp.status_code)
        except Exception as exc:
            logger.warning("Warmup basarisiz (devam ediliyor): %s", exc)

    # ── HTTP ─────────────────────────────────────────────────────────────────

    def _get(self, url: str, timeout: int = 25) -> Optional[dict]:
        """Retry + exponential backoff ile GET isteği atar."""
        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                resp = self._session.get(url, timeout=timeout)

                if resp.status_code == 404:
                    return None

                if resp.status_code in (403, 429):
                    wait = max(
                        int(resp.headers.get("Retry-After", self.RATE_LIMIT_SLEEP)),
                        self.RATE_LIMIT_SLEEP,
                    )
                    logger.warning(
                        "Rate limit (%d). %ds bekleniyor (deneme %d/%d)...",
                        resp.status_code, wait, attempt, self.MAX_RETRIES,
                    )
                    time.sleep(wait)
                    self._warmup()
                    continue

                resp.raise_for_status()
                return resp.json()

            except Exception as exc:
                if attempt == self.MAX_RETRIES:
                    logger.error("Tum %d deneme basarisiz -- %s: %s",
                                 self.MAX_RETRIES, url, exc)
                    return None
                wait = self.RETRY_BACKOFF * attempt
                logger.warning("Deneme %d basarisiz (%s). %ds sonra tekrar...",
                               attempt, exc, wait)
                time.sleep(wait)
        return None

    def _sleep(self) -> None:
        time.sleep(self.delay * random.uniform(0.5, 1.5))

    # ── Kategoriler ───────────────────────────────────────────────────────────

    def fetch_categories(self) -> list[dict]:
        """
        v2 catalog/category endpoint'inden tam agaci ceker, leaf node'lari doner.

        Siralama: gercek urun kategorileri once (Tisort, Jean, Etek vb.),
        editoryal kategoriler sonra (Yeni koleksiyon, Tumu vb.).
        Boylece dedup first-seen mantigi dogru kategori etiketini atar.
        """
        url = (
            f"{self.CATALOG_V2_URL}/category"
            f"?languageId={self.LANGUAGE_ID}"
            f"&typeCatalog=1"
            f"&appId={self.APP_ID}"
        )
        logger.info("Kategori agaci cekiliyor...")
        data = self._get(url)
        if not data:
            logger.error("Kategori verisi alinamadi.")
            return []

        categories: list[dict] = []

        def walk(items: list, parent_name: Optional[str] = None) -> None:
            for item in items or []:
                name = item.get("name", "")
                subs = item.get("subcategories") or item.get("subCategories") or []
                if subs:
                    walk(subs, parent_name=name)
                else:
                    cid = item.get("id") or item.get("categoryId")
                    if not cid:
                        continue
                    view_id = item.get("viewCategoryId")
                    product_cat_id = str(view_id) if view_id else str(cid)
                    categories.append({
                        "id":                  str(cid),
                        "product_category_id": product_cat_id,
                        "name":                name,
                        "parent_name":         parent_name,
                    })

        if isinstance(data, list):
            walk(data)
        elif isinstance(data, dict):
            walk(data.get("categories") or data.get("items") or [data])

        # Kategori ID bazlı deduplikasyon
        seen: set[str] = set()
        unique = []
        for cat in categories:
            if cat["id"] not in seen:
                seen.add(cat["id"])
                unique.append(cat)

        # Gercek urun kategorileri once, editoryal sonra
        def is_editorial(cat: dict) -> bool:
            p = (cat.get("parent_name") or "").strip().lower()
            return p in EDITORIAL_PARENTS

        unique.sort(key=is_editorial)

        real_count      = sum(1 for c in unique if not is_editorial(c))
        editorial_count = len(unique) - real_count
        logger.info(
            "%d leaf kategori bulundu (%d gercek, %d editoryal).",
            len(unique), real_count, editorial_count,
        )
        return unique

    # ── Ürün ID'leri ──────────────────────────────────────────────────────────

    def fetch_product_ids(self, category_id: str) -> list[str]:
        """showNoStock=false ile stokta olan urun ID'lerini doner."""
        url = (
            f"{self.CATALOG_V3_URL}/category/{category_id}/product"
            f"?languageId={self.LANGUAGE_ID}"
            f"&showProducts=false"
            f"&showNoStock=false"
            f"&appId={self.APP_ID}"
            f"&locale=tr_TR"
        )
        data = self._get(url)
        if not data:
            return []
        return [str(pid) for pid in data.get("productIds", [])]

    # ── Ürün detayları ────────────────────────────────────────────────────────

    def fetch_product_details(self, product_ids: list[str], category_id: str) -> list[dict]:
        """BATCH_SIZE'lik parcalar halinde productsArray endpoint'inden detay ceker."""
        all_products: list[dict] = []
        for i in range(0, len(product_ids), self.BATCH_SIZE):
            batch   = product_ids[i : i + self.BATCH_SIZE]
            ids_str = ",".join(batch)
            url = (
                f"{self.CATALOG_V3_URL}/productsArray"
                f"?languageId={self.LANGUAGE_ID}"
                f"&productIds={ids_str}"
                f"&categoryId={category_id}"
                f"&appId={self.APP_ID}"
                f"&locale=tr_TR"
            )
            data = self._get(url)
            if data:
                all_products.extend(data.get("products", []))
            time.sleep(0.3)
        return all_products

    # ── Kayıt çıkarımı ────────────────────────────────────────────────────────

    def extract_record(self, raw: dict, category_path: str) -> Optional[dict]:
        """
        Ham Inditex urun dict'inden tek CSV satiri uretir.

        Fiyat olarak ilk rengin ilk bedeninin fiyati alinir.
        Ayni urunun farkli renkleri her zaman ayni fiyata sahip oldugu icin
        renk bazinda ayirma yapmak gereksizdir.

        price: o gunun satis fiyati (TRY).
            Indirimli urunde indirimli, indirimsizde normal fiyat.
            Enflasyon takibi icin dogru kolon budur.
        """
        if not raw or not isinstance(raw, dict):
            return None

        name = (raw.get("name") or "").strip()
        if not name:
            return None

        try:
            summaries = raw.get("bundleProductSummaries") or []
            if not summaries:
                return None
            detail = summaries[0].get("detail") or {}
            colors = detail.get("colors") or []

            for color in colors:
                for size in color.get("sizes") or []:
                    price_cents = size.get("price")
                    if price_cents is not None:
                        return {
                            "category":     category_path,
                            "product_name": name,
                            "price":        round(int(price_cents) / 100, 2),
                        }
        except Exception:
            return None

        return None

    # ── Ana pipeline ──────────────────────────────────────────────────────────

    def run(self) -> Path:
        """
        Pipeline:
            1. Session + Akamai warmup
            2. Kategorileri cek (gercek kategoriler once)
            3. Her kategori: product ID'leri → detaylar → CSV'ye yaz

        Cikti: output_dir/stradivarius_YYYY-MM-DD.csv
        Kolonlar: category, product_name, price
        Dedup: seen_ids (product_id bazli, cross-category)
        """
        today_str   = date.today().strftime("%Y-%m-%d")
        output_file = self.output_dir / f"stradivarius_{today_str}.csv"

        self._session = self._make_session()
        self._warmup()

        categories = self.fetch_categories()
        if not categories:
            logger.error("Hic kategori bulunamadi. Scraper durduruluyor.")
            return output_file

        fieldnames = ["category", "product_name", "price"]
        self.output_dir.mkdir(parents=True, exist_ok=True)

        total_products = 0
        seen_ids: set[str] = set()  # product_id bazli cross-category dedup

        with open(output_file, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for cat in tqdm(categories, unit="kategori", desc="Scraping"):
                cat_id   = cat["product_category_id"]
                cat_name = cat["name"]
                parent   = cat.get("parent_name")
                cat_path = _clean_category(parent, cat_name)

                product_ids = self.fetch_product_ids(cat_id)
                if not product_ids:
                    logger.debug("'%s' -- urun yok, atlaniyor.", cat_name)
                    continue

                raw_products = self.fetch_product_details(product_ids, cat_id)

                new_in_category = 0
                for raw in raw_products:
                    pid = str(raw.get("id", ""))
                    if not pid or pid in seen_ids:
                        continue  # Bu product_id zaten baska kategoriden alindi
                    record = self.extract_record(raw, cat_path)
                    if record is None:
                        continue
                    seen_ids.add(pid)
                    writer.writerow(record)
                    new_in_category += 1

                total_products += new_in_category
                if new_in_category:
                    logger.info("'%s': +%d urun (toplam: %d)",
                                cat_name, new_in_category, total_products)

                self._sleep()

        logger.info("Tamamlandi. Toplam %d urun --> %s", total_products, output_file)
        return output_file


if __name__ == "__main__":
    scraper = StradivariusScraper(output_dir=".", delay=0.5)
    scraper.run()