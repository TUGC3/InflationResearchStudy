import csv
import re
import time
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

KATEGORILER = [
    ("Meyve, Sebze", "https://www.kalemarketleri.com/meyve-sebze"),
    ("Et, Tavuk", "https://www.kalemarketleri.com/et-tavuk"),
    ("Süt, Kahvaltılık", "https://www.kalemarketleri.com/sut-kahvaltilik"),
    ("Genel Gıda", "https://www.kalemarketleri.com/genel-gida"),
    ("İçecekler", "https://www.kalemarketleri.com/icecekler"),
    ("Unlu Mamuller", "https://www.kalemarketleri.com/unlu-mamuller"),
    ("Bisküvi, Kuruyemiş", "https://www.kalemarketleri.com/biskuvi-kuruyemis"),
    ("Deterjan, Temizlik", "https://www.kalemarketleri.com/deterjan-temizlik"),
    ("Kişisel Bakım, Kozmetik", "https://www.kalemarketleri.com/kisisel-bakim-kozmetik"),
    ("Kağıt Ürünleri", "https://www.kalemarketleri.com/kagit-unlock"),
    ("Bebek Ürünleri", "https://www.kalemarketleri.com/bebek-urunleri"),
    ("Ev, Yaşam", "https://www.kalemarketleri.com/ev-yasam"),
]

# DOSYA YOLU AYARI: Codes/markets içinden 2 kat yukarı çıkıp Datas/markets/kale'ye gider
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
OUT_DIR = REPO_ROOT / "Datas" / "Markets" / "Kale"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def make_driver() -> webdriver.Chrome:
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=opts)
    driver.set_page_load_timeout(60)
    return driver


def scroll_sona_kadar(driver, max_scroll=60, bekle=1.5):
    last_height = driver.execute_script("return document.body.scrollHeight")
    sabit_sayac = 0
    for _ in range(max_scroll):
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(bekle)
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            sabit_sayac += 1
            if sabit_sayac >= 3: break
        else:
            sabit_sayac = 0
            last_height = new_height


def fiyat_temizle(text: str) -> str:
    if not text: return ""
    t = re.sub(r'[^\d.,]', '', text)
    if "," in t and "." in t:
        t = t.replace(".", "").replace(",", ".")
    elif "," in t:
        t = t.replace(",", ".")
    return t


def main():
    bugun = datetime.now(ZoneInfo("Europe/Istanbul")).strftime("%Y-%m-%d")
    csv_path = OUT_DIR / f"kalemarketleri_{bugun}.csv"

    driver = make_driver()
    seen = set()
    rows = []

    try:
        for kategori_adi, link in KATEGORILER:
            print(f"🔍 İşleniyor: {kategori_adi}")
            try:
                driver.get(link)
                time.sleep(4)
                scroll_sona_kadar(driver)

                urun_kartlari = driver.find_elements(By.CSS_SELECTOR, "div.productItem, div.ProductItem")

                for kart in urun_kartlari:
                    try:
                        isim = kart.find_element(By.CSS_SELECTOR, ".productName, .product-name").text.strip()
                        fiyat_ham = kart.find_element(By.CSS_SELECTOR, ".productPrice, .price").text.strip()
                        fiyat = fiyat_temizle(fiyat_ham)

                        if isim and fiyat:
                            key = (isim.lower(), fiyat)
                            if key not in seen:
                                seen.add(key)
                                rows.append({
                                    "tarih": bugun,
                                    "kategori": kategori_adi,
                                    "product_name": isim,
                                    "product_price": fiyat,
                                })
                    except:
                        continue
                print(f"  ✅ {kategori_adi} bitti.")
            except Exception as e:
                print(f"  ❌ {kategori_adi} hatası: {e}")

    finally:
        driver.quit()

    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["tarih", "kategori", "product_name", "product_price"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"\n🎉 İşlem tamamlandı. Dosya: {csv_path}")


if __name__ == "__main__":
    main()
