import csv
import re
import time
import os
from datetime import datetime
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
    ("Kişisel Bakım, Kozmetik", "https://www.kalemarketleri.com/kisisel-bakin-kozmetik"),
    ("Kağıt Ürünleri", "https://www.kalemarketleri.com/kagit-urunleri"),
    ("Bebek Ürünleri", "https://www.kalemarketleri.com/bebek-urunleri"),
    ("Ev, Yaşam", "https://www.kalemarketleri.com/ev-yasam"),
]

def make_driver():
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu") # Ekstra stabilite için
    opts.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    # Sürücü kurulumunu arkadaşınınkiyle birebir aynı ve daha sade hale getirdik
    return webdriver.Chrome(options=opts)

def main():

    bugunun_tarihi = datetime.now().strftime("%Y-%m-%d")
    target_dir = "Datas/Markets/Kale"
    os.makedirs(target_dir, exist_ok=True)
    csv_dosyasi = os.path.join(target_dir, f"kalemarketleri_{bugunun_tarihi}.csv")

    driver = make_driver()
    driver.set_page_load_timeout(60)
    tum_urunler = []

    try:
        for kategori_adi, url in KATEGORILER:
            print(f"🔍 {kategori_adi} taranıyor...")
            driver.get(url)
            time.sleep(5)

            # Sayfayı sona kadar kaydır (Daha fazla ürün yüklemesi için)
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(3)

            urun_kartlari = driver.find_elements(By.CSS_SELECTOR, "div.product-item")
            
            for kart in urun_kartlari:
                try:
                    isim = kart.find_element(By.CSS_SELECTOR, "div.product-title").text.strip()
                    fiyat_text = kart.find_element(By.CSS_SELECTOR, "div.product-price").text.strip()
                    
                    fiyat = fiyat_text.replace("TL", "").replace("₺", "").strip()

                    tum_urunler.append({
                        "kategori": kategori_adi,
                        "product_name": isim,
                        "product_price": fiyat
                    })
                except:
                    continue
            print(f"✅ {kategori_adi} bitti. Şu ana kadar toplam: {len(tum_urunler)}")

    finally:
        driver.quit()

    # CSV'ye yazma
    with open(csv_dosyasi, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["kategori", "product_name", "product_price"])
        writer.writeheader()
        writer.writerows(tum_urunler)

    print(f"\n🎉 Bitti! {len(tum_urunler)} ürün kaydedildi: {csv_dosyasi}")

if __name__ == "__main__":
    main()
