import requests
import pandas as pd
import time
import os
import re
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from bs4 import BeautifulSoup
from urllib.parse import urljoin

# -----------------------------------------------------------------------------
# CONFIG
# -----------------------------------------------------------------------------
BASE_URL = "https://www.pazarium.com.tr"
# Pazarium'da ayrı bir Kozmetik kategorisi var: /kozmetik (toplam ~959 ürün).
# Bu, "kozmetik" araması yapmaktan daha geniş ve kararlıdır.
CATEGORY_URL = f"{BASE_URL}/kozmetik"

MAX_WORKERS = 5
REQUEST_TIMEOUT = 30
RETRY_COUNT = 3
RETRY_DELAY = 2  # saniye

# 1. Mevcut dosyanın (pazarium_scraper.py) konumunu al
current_script_path = os.path.abspath(__file__)

# 2. 'Codes/Cosmetics/Pazarium' klasöründen 3 seviye yukarı çıkarak
#    InflationItems klasörüne ulaş
# InflationItems/Codes/Cosmetics/Pazarium/pazarium_scraper.py  ->  InflationItems
base_project_dir = os.path.dirname(
    os.path.dirname(
        os.path.dirname(
            os.path.dirname(current_script_path)
        )
    )
)

# 3. Data klasörünü oluştur (yoksa)
data_dir = os.path.join(base_project_dir, "Datas", "Cosmetics", "Pazarium")
os.makedirs(data_dir, exist_ok=True)

OUTPUT_FILE = os.path.join(
    data_dir, f"pazarium_{datetime.now().strftime('%Y-%m-%d')}.csv"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8",
    "Referer": BASE_URL + "/",
}

session = requests.Session()
session.headers.update(HEADERS)

# -----------------------------------------------------------------------------
# REGEX / HELPERS
# -----------------------------------------------------------------------------
# Fiyat formatı: "1.234,56 TL" veya "99,90 TL"
PRICE_RE = re.compile(r"(\d{1,3}(?:\.\d{3})*,\d{2})\s*TL")

# "Toplam 959 ürün bulunmaktadır." içindeki sayıyı yakalamak için
TOTAL_RE = re.compile(r"Toplam\s+(\d[\d.,]*)\s+ürün", re.IGNORECASE)

# Ürün sayfası URL'leri tek segmentlidir: /some-product-slug
# Menü, kategori, hesap sayfası URL'leri de tek segmentli olabilir;
# onları ayırt etmek için ürün kartlarında fiyat olmasından yararlanıyoruz.
NON_PRODUCT_PATHS = {
    "", "anasayfa", "sepet", "uye-girisi-sayfasi", "uye-alisveris-listesi",
    "uye-kayit", "uye-sifre-hatirlat", "siparis-takip",
    "kozmetik", "giyim", "erkek-giyim", "tesettur-giyim", "pijama-takimi",
    "ic-giyim", "basortusu", "pantolon-etek", "tesettur-dis-giyim",
    "indirim-tesettur-giyim", "cok-satanlar", "yeni-sezon-tesettur-giyim",
}


def parse_price(text: str) -> float | None:
    """'1.234,56 TL' -> 1234.56. Eşleşme yoksa None döner."""
    m = PRICE_RE.search(text)
    if not m:
        return None
    return float(m.group(1).replace(".", "").replace(",", "."))


def fetch_page(page_num: int) -> str | None:
    """Belirli sayfayı indirir, başarısızsa retry yapar."""
    url = f"{CATEGORY_URL}?pg={page_num}"
    last_err = None
    for attempt in range(1, RETRY_COUNT + 1):
        try:
            r = session.get(url, timeout=REQUEST_TIMEOUT)
            r.raise_for_status()
            return r.text
        except Exception as e:
            last_err = e
            if attempt < RETRY_COUNT:
                time.sleep(RETRY_DELAY * attempt)
    print(f"[ERROR] Sayfa {page_num} alınamadı ({RETRY_COUNT} deneme): {last_err}")
    return None


# -----------------------------------------------------------------------------
# PARSING
# -----------------------------------------------------------------------------
def parse_products(html: str, page_num: int) -> list[dict]:
    """
    Bir HTML sayfasındaki ürün kartlarını parse eder.

    Strateji: Her <img> etiketinden başlayıp yukarı doğru gezerek
    (1) ürün linkini içeren <a> ve (2) fiyat içeren konteyneri bul.
    Fiyat kontrolü, menü/logo görselleri gibi ürün olmayan öğeleri
    otomatik olarak eler.
    """
    soup = BeautifulSoup(html, "lxml")
    products: list[dict] = []
    seen_urls: set[str] = set()

    for img in soup.find_all("img"):
        # 1) Sarmalayan <a> etiketini bul -> ürün URL'si
        parent_a = img.find_parent("a")
        if not parent_a:
            continue

        href = parent_a.get("href", "") or ""
        if not href or href.startswith("#") or href.startswith("javascript:"):
            continue

        full_url = urljoin(BASE_URL, href)
        if not full_url.startswith(BASE_URL):
            continue

        # Path'i kontrol et - ürün URL'leri tek segmentli
        path = full_url[len(BASE_URL):].lstrip("/")
        # Query veya fragment varsa kaldır (sadece path baz alınsın)
        path = path.split("?", 1)[0].split("#", 1)[0]
        if "/" in path:  # /Data/..., /srv/... gibi iç yollar ürün değildir
            continue
        if path in NON_PRODUCT_PATHS:
            continue

        if full_url in seen_urls:
            continue

        # 2) Fiyat içeren üst konteyneri bul (en fazla 5 seviye yukarı).
        # <body>/<html>'e ulaşırsak dururuz; aksi halde sayfanın başka
        # bir yerindeki fiyatı bu <a>'ya yanlışlıkla atayabiliriz.
        container = parent_a
        price = None
        for _ in range(5):
            if container is None or container.name in ("body", "html"):
                break
            price = parse_price(container.get_text(" ", strip=True))
            if price is not None:
                break
            container = container.parent

        if price is None:
            # Fiyat yoksa muhtemelen ürün kartı değil (menü, logo, footer vb.)
            continue

        # 3) Stok kontrolü: Tükendi olan ürünleri atla.
        # T-Soft şablonunda: <span class="out-of-stock">Tükendi</span>
        if container.select_one(".out-of-stock") is not None:
            continue
        # Bazı varyantlarda sınıf yerine sadece metin olabilir; yedek kontrol:
        if "Tükendi" in container.get_text(" ", strip=True):
            continue

        # 4) Ürün adı ve alt kategori
        alt = (img.get("alt") or "").strip()
        name = alt
        subcategory = ""
        if " - " in alt:
            # T-Soft şablonunda alt: "Ürün Adı - Alt Kategori"
            parts = alt.rsplit(" - ", 1)
            name = parts[0].strip()
            subcategory = parts[1].strip()

        # Alt yoksa linkteki görünür metinden ismi al
        if not name:
            link_text = parent_a.get_text(" ", strip=True)
            if link_text and not PRICE_RE.search(link_text):
                name = link_text

        # url alanı iç tarafta tutuluyor (sayfalar arası tekrar elemek için),
        # CSV'ye yazılmayacak.
        products.append({
            "name": name,
            "subcategory": subcategory,
            "price": price,
            "url": full_url,
        })
        seen_urls.add(full_url)

    return products


def get_total_count_and_page1(html: str):
    """
    Sayfa 1 HTML'inden toplam ürün sayısını, sayfadaki ürünleri ve
    sayfa başına ürün sayısını çıkarır.
    """
    soup = BeautifulSoup(html, "lxml")
    page_text = soup.get_text(" ", strip=True)

    m = TOTAL_RE.search(page_text)
    total_products = None
    if m:
        total_products = int(m.group(1).replace(".", "").replace(",", ""))

    page1_products = parse_products(html, 1)
    per_page = len(page1_products) if page1_products else 0
    return total_products, per_page, page1_products


# -----------------------------------------------------------------------------
# MAIN
# -----------------------------------------------------------------------------
def main():
    t0 = time.time()
    today_str = datetime.now().strftime("%Y-%m-%d")
    print("=" * 70)
    print(f"Pazarium Kozmetik Scraper  |  {today_str}")
    print(f"Hedef: {CATEGORY_URL}")
    print(f"Çıktı: {OUTPUT_FILE}")
    print("=" * 70)

    # --- 1. Sayfa: Toplam sayı ve ilk sayfa ürünleri ---
    print("[1/3] Sayfa 1 indiriliyor (toplam sayı belirlenecek)...")
    html1 = fetch_page(1)
    if not html1:
        print("[FATAL] Sayfa 1 alınamadı, çıkılıyor.")
        return

    total_products, per_page, page1_products = get_total_count_and_page1(html1)
    print(f"   -> Sayfa başına ürün: {per_page}")
    if total_products is not None:
        print(f"   -> Toplam ürün (siteye göre): {total_products}")
    else:
        print("   -> Toplam sayı bulunamadı, sayfalar boş gelene kadar ilerleyecek.")

    all_products: list[dict] = list(page1_products)
    seen_urls: set[str] = {p["url"] for p in all_products}

    # --- 2. Kalan sayfalar ---
    if total_products is not None and per_page > 0:
        total_pages = (total_products + per_page - 1) // per_page
        print(f"[2/3] Hesaplanan sayfa sayısı: {total_pages}")
        remaining = list(range(2, total_pages + 1))

        if remaining:
            print(f"   -> {len(remaining)} sayfa paralel indiriliyor "
                  f"(workers={MAX_WORKERS})...")
            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                future_to_page = {
                    executor.submit(fetch_page, p): p for p in remaining
                }
                for future in as_completed(future_to_page):
                    page = future_to_page[future]
                    html = future.result()
                    if not html:
                        continue
                    new_products = parse_products(html, page)
                    added = 0
                    for prod in new_products:
                        if prod["url"] not in seen_urls:
                            all_products.append(prod)
                            seen_urls.add(prod["url"])
                            added += 1
                    print(f"   [sayfa {page:>3}] {len(new_products)} ürün "
                          f"bulundu, {added} yeni")
    else:
        # Fallback: toplam sayı yoksa boş sayfa görene kadar sıralı ilerle
        print("[2/3] Sıralı sayfalama (toplam belirsiz)...")
        page = 2
        empty_streak = 0
        while empty_streak < 2:
            html = fetch_page(page)
            if not html:
                empty_streak += 1
                page += 1
                continue
            new_products = parse_products(html, page)
            added = 0
            for prod in new_products:
                if prod["url"] not in seen_urls:
                    all_products.append(prod)
                    seen_urls.add(prod["url"])
                    added += 1
            print(f"   [sayfa {page:>3}] {len(new_products)} bulundu, "
                  f"{added} yeni")
            empty_streak = empty_streak + 1 if added == 0 else 0
            page += 1

    # --- 3. CSV yaz ---
    if not all_products:
        print("[FATAL] Hiç ürün çıkarılamadı. Sayfa şablonu değişmiş olabilir.")
        return

    df = pd.DataFrame(all_products)

    # Kolon sırası: sadece istenen 3 alan (url sadece iç dedup için tutuluyordu)
    df = df[["name", "subcategory", "price"]]
    df = df.sort_values(["subcategory", "name"]).reset_index(drop=True)

    # utf-8-sig: Excel'de Türkçe karakterler düzgün görünsün
    df.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")

    elapsed = time.time() - t0
    print("=" * 70)
    print(f"[3/3] TAMAMLANDI")
    print(f"   Toplam ürün: {len(df)}")
    print(f"   Çıktı: {OUTPUT_FILE}")
    print(f"   Süre: {elapsed:.1f} sn")
    print("=" * 70)


if __name__ == "__main__":
    main()