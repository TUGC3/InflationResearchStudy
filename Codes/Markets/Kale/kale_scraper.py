import csv
import os
import time
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
    tum_urunler = []

    try:
        for kategori_adi, url in KATEGORILER:
            print(f"🔍 {kategori_adi} taranıyor...")
            try:
                driver.get(url)
                time.sleep(7) 


                for _ in range(3):
                    driver.execute_script("window.scrollBy(0, 1000);")
                    time.sleep(1)

                urun_kartlari = driver.find_elements(By.CLASS_NAME, "product-item") or \
                                driver.find_elements(By.CLASS_NAME, "product-card") or \
                                driver.find_elements(By.CSS_SELECTOR, ".item")
                
                for kart in urun_kartlari:
                    try:

                        isim = (kart.find_elements(By.CLASS_NAME, "product-title") or \
                                kart.find_elements(By.CLASS_NAME, "name"))[0].text.strip()
                        

                        fiyat = (kart.find_elements(By.CLASS_NAME, "product-price") or \
                                 kart.find_elements(By.CLASS_NAME, "price"))[0].text.strip()
                        
                        fiyat = fiyat.replace("TL", "").replace("₺", "").strip()

                        if isim:
                            tum_urunler.append({"kategori": kategori_adi, "product_name": isim, "product_price": fiyat})
                    except: continue
                print(f"✅ {kategori_adi} bitti. Toplam: {len(tum_urunler)}")
            except Exception as e:
                print(f"⚠️ Hata: {e}")
                continue
    finally:
        driver.quit()

    # Ürün bulamasa bile boş CSV oluştur (Action hata vermesin diye)
    with open(csv_dosyasi, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["kategori", "product_name", "product_price"])
        writer.writeheader()
        if tum_urunler:
            writer.writerows(tum_urunler)
            print(f"🎉 {len(tum_urunler)} ürün kaydedildi.")
        else:
            print("⚠️ Ürün bulunamadı ama boş dosya oluşturuldu.")

if __name__ == "__main__":
    main()
