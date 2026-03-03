from bs4 import BeautifulSoup
from datetime import datetime
import time
import csv
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
import os

# ==============================
# KATEGORİ LINKLERİ
# ==============================

categories = [
    "https://www.bizimtoptan.com.tr/temel-gida",
    "https://www.bizimtoptan.com.tr/sivi-yag-margarin",
    "https://www.bizimtoptan.com.tr/atistirmalik",
    "https://www.bizimtoptan.com.tr/icecek",
    "https://www.bizimtoptan.com.tr/sarkuteri-kahvaltilik",
    "https://www.bizimtoptan.com.tr/et-urunleri-ve-sarkuteri",
    "https://www.bizimtoptan.com.tr/unlu-mamuller",
    "https://www.bizimtoptan.com.tr/bebek-urunleri",
    "https://www.bizimtoptan.com.tr/evcil-hayvan",
    "https://www.bizimtoptan.com.tr/temizlik",
    "https://www.bizimtoptan.com.tr/kisisel-bakim",
    "https://www.bizimtoptan.com.tr/gida-disi"
]

# ==============================
# DRIVER
# ==============================

options = Options()
options.add_argument("--start-maximized")
driver = webdriver.Chrome(
    service=Service(ChromeDriverManager().install()),
    options=options
)

# ==============================
# CSV DOSYA
# ==============================

data_dir = "Datas/Markets/BizimToptan"
os.makedirs(data_dir, exist_ok=True)
date = datetime.now().strftime("%Y-%m-%d")
filename = f"{data_dir}/bizimtoptan_{date}.csv"

with open(filename, "w", newline="", encoding="utf-8-sig") as f:
    writer = csv.writer(f)
    writer.writerow(["category", "product_name", "price_TL"])

# ==============================
# SCRAPING
# ==============================

for url in categories:

    category_name = url.split("/")[-1]
    print(f"\n📂 Kategori başlıyor: {category_name}")

    page = 1

    while True:

        page_url = f"{url}?pagenumber={page}&paginationType=10"
        print(f"Sayfa: {page_url}")

        driver.get(page_url)
        time.sleep(4)

        soup = BeautifulSoup(driver.page_source, "html.parser")
        cards = soup.find_all("div", class_="product-box-container")

        # Eğer ürün yoksa kategori bitmiştir
        if len(cards) == 0:
            print("Kategori tamamlandı (ürün yok).")
            break

        # Ürün sayısı 7 veya daha az ise bu sayfayı kaydetme ve diğer kategoriye geç
        if len(cards) <= 7:
            print(f"Son sayfa veya eksik ürün ({len(cards)} ürün). Kayıt edilmiyor, kategori tamamlandı.")
            break

        print("Bulunan ürün:", len(cards))

        with open(filename, "a", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)

            for card in cards:
                img_tag = card.find("img")
                name = img_tag.get("alt") if img_tag else None

                price = None
                price_tag = card.find("span", class_="price")

                if price_tag:
                    raw_price = (
                        price_tag.text
                        .replace("TL", "")
                        .replace(",", ".")
                        .strip()
                    )
                    try:
                        price = float(raw_price)
                    except:
                        price = None

                if name and price is not None:
                    writer.writerow([category_name, name, price])
                    print("Ürün:", name, "| Fiyat:", price)

        page += 1
        time.sleep(1)

driver.quit()
print("\n✅ BİTTİ! Dosya oluşturuldu:", filename)
