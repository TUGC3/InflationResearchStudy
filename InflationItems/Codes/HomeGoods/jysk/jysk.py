import csv, os, re, sys, time, random, shutil
from datetime import datetime
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup

try:
    import undetected_chromedriver as uc
except ImportError:
    print("pip install undetected-chromedriver beautifulsoup4")
    sys.exit(1)

CHROME_VERSION = 147
SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
OUT_DIR     = os.path.join(SCRIPT_DIR, "Datas", "JYSK")
PROFILE_DIR = os.path.join(SCRIPT_DIR, "SeleniumProfile_JYSK")

SABIT_KATEGORILER = [
    "https://jysk.com.tr/yatak-odasi",
    "https://jysk.com.tr/yatak-odasi/yataklar",
    "https://jysk.com.tr/yatak-odasi/yataklar/yayli-yataklar",
    "https://jysk.com.tr/yatak-odasi/yataklar/sunger-yataklar",
    "https://jysk.com.tr/yatak-odasi/yataklar-ve-yatak-aksesuarlari/continental-yataklar",
    "https://jysk.com.tr/yatak-odasi/divan-tabanlari",
    "https://jysk.com.tr/yatak-odasi/yataklar/yatak-silteleri",
    "https://jysk.com.tr/yatak-odasi/yataklar/yatak-pedleri",
    "https://jysk.com.tr/yatak-odasi/yataklar-ve-yatak-aksesuarlari/karyolalar-ve-yatak-citalari/karyolalar",
    "https://jysk.com.tr/yatak-odasi/yataklar-ve-yatak-aksesuarlari/karyolalar-ve-yatak-citalari/yatak-citalari",
    "https://jysk.com.tr/yatak-odasi/yataklar/cocuk-yataklari",
    "https://jysk.com.tr/yatak-odasi/yataklar-ve-yatak-aksesuarlari/cocuk-ranza-ve-karyolalari",
    "https://jysk.com.tr/yatak-odasi/yorganlar",
    "https://jysk.com.tr/yatak-odasi/yastiklar",
    "https://jysk.com.tr/yatak-odasi/carsaflar",
    "https://jysk.com.tr/banyo",
    "https://jysk.com.tr/banyo/havlular",
    "https://jysk.com.tr/banyo/banyo-aksesuarlari",
    "https://jysk.com.tr/ofis",
    "https://jysk.com.tr/oturma-odasi",
    "https://jysk.com.tr/oturma-odasi/orta-ve-yan-sehpalar",
    "https://jysk.com.tr/oturma-odasi/tv-unitesi",
    "https://jysk.com.tr/oturma-odasi/mobilya-bakimi",
    "https://jysk.com.tr/yemek-odasi",
    "https://jysk.com.tr/depolama",
    "https://jysk.com.tr/antre",
    "https://jysk.com.tr/antre/antre-uniteleri",
    "https://jysk.com.tr/perdeler",
    "https://jysk.com.tr/perdeler/hazir-perdeler",
    "https://jysk.com.tr/perdeler/stor-perdeler",
    "https://jysk.com.tr/perdeler/sineklikler",
    "https://jysk.com.tr/perdeler/cam-filmi",
    "https://jysk.com.tr/bahce",
    "https://jysk.com.tr/bahce/bahce-mobilyalari/bahce-dinlenme-mobilyalari",
    "https://jysk.com.tr/bahce/bahce-mobilyalari/bahce-masalari",
    "https://jysk.com.tr/bahce/bahce-mobilyalari/bahce-sandalyeleri",
    "https://jysk.com.tr/bahce/sezlonglar",
    "https://jysk.com.tr/bahce/bahce-minderleri",
    "https://jysk.com.tr/bahce/dis-mekan-depolama",
    "https://jysk.com.tr/bahce/dis-mekan-aydinlatma",
    "https://jysk.com.tr/bahce/kamp",
    "https://jysk.com.tr/ev-esyalari",
    "https://jysk.com.tr/ev-esyalari/dekorasyon",
    "https://jysk.com.tr/ev-esyalari/aydinlatma",
    "https://jysk.com.tr/ev-esyalari/temizlik-aksesuarlari",
    "https://jysk.com.tr/ev-esyalari/camasir-gereksinimleri",
    "https://jysk.com.tr/yeni-gelenler",
    "https://jysk.com.tr/indirimli-urunler",
    "https://jysk.com.tr/her-gun-uygun-fiyat",
    "https://jysk.com.tr/outlet",
]

seen_products: set = set()
seen_urls: set     = set()


def setup_driver():
    opts = uc.ChromeOptions()
    opts.add_argument(f"--user-data-dir={PROFILE_DIR}")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--start-maximized")
    opts.add_argument("--log-level=3")
    driver = uc.Chrome(options=opts, version_main=CHROME_VERSION)
    driver.set_page_load_timeout(60)
    print("✅ Chrome başlatıldı.")
    return driver


def get_csv_path():
    os.makedirs(OUT_DIR, exist_ok=True)
    tarih = datetime.now(ZoneInfo("Europe/Istanbul")).strftime("%Y-%m-%d")
    return os.path.join(OUT_DIR, f"jysk_prices_{tarih}.csv")


def save_batch(rows, csv_path):
    file_exists = os.path.isfile(csv_path)
    with open(csv_path, "a", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["urun_adi", "fiyat"])
        if not file_exists:
            writer.writeheader()
        writer.writerows(rows)


def fiyat_cek(kart):
    
    el = kart.select_one(".product-price-unit-current")
    if el:
        txt = el.get_text(" ", strip=True)
        m = re.search(r"\d[\d.,]*", txt)
        if m:
            return m.group(0).replace(".", ",") if "." in m.group(0) and "," not in m.group(0) else m.group(0)

    el = kart.select_one(".product-price-value")
    if el:
        txt = el.get_text(" ", strip=True)
        
        m = re.search(r"\d[\d.]*,\d{2}", txt)   
        if m:
            return m.group(0)
        m = re.search(r"\d[\d.,]*", txt)
        if m:
            return m.group(0)

  
    el = kart.select_one(".product-price")
    if el:
        txt = el.get_text(" ", strip=True)
        m = re.search(r"\d[\d.]*,\d{2}", txt)
        if m:
            return m.group(0)

    return ""


def parse_urunler(soup):
    kartlar = soup.select("div.product-teaser-wrapper")
    if not kartlar:
        kartlar = soup.select("div.product-container")

    batch = []
    for kart in kartlar:
       
        seri  = kart.select_one(".product-teaser-title__series")
        model = kart.select_one(".product-teaser-title__name")
        seri_txt  = seri.get_text(" ", strip=True)  if seri  else ""
        model_txt = model.get_text(" ", strip=True) if model else ""
        isim = f"{seri_txt} {model_txt}".strip() if seri_txt or model_txt else ""
        if not isim:
            continue

        fiyat = fiyat_cek(kart)
        if not fiyat:
            continue

        anahtar = (isim.lower().strip(), fiyat)
        if anahtar in seen_products:
            continue
        seen_products.add(anahtar)
        batch.append({"urun_adi": isim, "fiyat": fiyat})

    return batch


def scroll_tamamen(driver, bekle=1.5, max_tur=80):
    stable, son = 0, driver.execute_script("return document.body.scrollHeight")
    for _ in range(max_tur):
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(bekle)
        yeni = driver.execute_script("return document.body.scrollHeight")
        if yeni == son:
            stable += 1
            if stable >= 3: break
        else:
            stable, son = 0, yeni


def max_sayfa_bul(soup):
    mx = 1
    for a in soup.select("a[href]"):
        for p in ("page", "p", "sayfa"):
            m = re.search(rf"[?&]{p}=(\d+)", a.get("href", ""))
            if m: mx = max(mx, int(m.group(1)))
    for el in soup.select("li.pager-item, li.page-item, .pagination li"):
        t = el.get_text(strip=True)
        if t.isdigit(): mx = max(mx, int(t))
    return mx


def sayfa_url(base, sayfa):
    sep = "&" if "?" in base else "?"
    return f"{base}{sep}page={sayfa}"


def kategori_scrape(driver, url, csv_path):
    if url in seen_urls:
        return 0
    seen_urls.add(url)
    print(f"\n  📄 {url}")
    toplam, sayfa = 0, 1

    while True:
        driver.get(url if sayfa == 1 else sayfa_url(url, sayfa))
        time.sleep(random.uniform(3, 5))
        scroll_tamamen(driver)

        soup  = BeautifulSoup(driver.page_source, "html.parser")
        batch = parse_urunler(soup)

        if not batch and sayfa == 1:
            print("    ⚠️  Ürün bulunamadı.")
            break

        if batch:
            save_batch(batch, csv_path)
            toplam += len(batch)
            print(f"    ✅ Sayfa {sayfa}: {len(batch)} ürün (toplam: {toplam})")

        if sayfa >= max_sayfa_bul(soup): break
        sayfa += 1
        time.sleep(random.uniform(2, 4))

    return toplam


def cleanup():
    if os.path.exists(PROFILE_DIR):
        try: shutil.rmtree(PROFILE_DIR)
        except: pass


def main():
    print("=" * 60)
    print("  JYSK.com.tr Ürün Scraper  —  v6")
    print("=" * 60)
    csv_path = get_csv_path()
    print(f"  Çıktı: {csv_path}\n")
    driver = setup_driver()
    try:
        for url in SABIT_KATEGORILER:
            kategori_scrape(driver, url, csv_path)
            time.sleep(random.uniform(2, 5))
    except KeyboardInterrupt:
        print("\n⚠️  Durduruldu.")
    finally:
        driver.quit()
        cleanup()
        print(f"\n{'='*60}")
        print(f"  Toplam: {len(seen_products)} ürün → {csv_path}")
        print(f"{'='*60}")


if __name__ == "__main__":
    main()
