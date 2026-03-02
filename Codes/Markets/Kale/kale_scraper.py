import csv
import os
import time
import re
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options


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
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
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
            try:
                driver.get(url)
                time.sleep(5)

                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(3)


                urun_kartlari = driver.find_elements(By.CSS_SELECTOR, "div.product-item")
                
                cekilen_kategori_sayisi = 0
                for kart in urun_kartlari:
                    try:

                        isim = kart.find_element(By.CSS_SELECTOR, "div.product-title").text.strip()
                        fiyat_text = kart.find_element(By.CSS_SELECTOR, "div.product-price").text.strip()
                        
                        fiyat = fiyat_text.replace("TL", "").replace("₺", "").strip()

                        if isim:
                            tum_urunler.append({
                                "kategori": kategori_adi,
                                "product_name": isim,
                                "product_price": fiyat
                            })
                            cekilen_kategori_sayisi += 1
                    except:
                        continue
                print(f"✅ {kategori_adi} bitti. Çekilen: {cekilen_kategori_sayisi}")
            except Exception as e:
                print(f"⚠️ {kategori_adi} taranırken hata oluştu: {e}")
                continue

    finally:
        driver.quit()

    if tum_urunler:
        with open(csv_dosyasi, "w", newline="", encoding="utf-8-sig") as f:
            fieldnames = ["kategori", "product_name", "product_price"]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(tum_urunler)
        print(f"\n🎉 İşlem tamam! {len(tum_urunler)} ürün '{csv_dosyasi}' dosyasına kaydedildi.")
    else:
        print("\n❌ Hiç ürün çekilemedi, dosya oluşturulmadı.")

if __name__ == "__main__":
    main()
