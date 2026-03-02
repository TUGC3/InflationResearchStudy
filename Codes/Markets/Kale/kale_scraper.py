import csv
import os
import time
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

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

    opts.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option('useAutomationExtension', False)
    return webdriver.Chrome(options=opts)

def main():
    bugunun_tarihi = datetime.now().strftime("%Y-%m-%d")
    target_dir = "Datas/Markets/Kale"
    os.makedirs(target_dir, exist_ok=True)
    csv_dosyasi = os.path.join(target_dir, f"kalemarketleri_{bugunun_tarihi}.csv")

    driver = make_driver()

    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
    tum_urunler = []

    try:
        for kategori_adi, url in KATEGORILER:
            print(f"🔍 {kategori_adi} taranıyor...")
            driver.get(url)
            

            try:
                WebDriverWait(driver, 15).until(
                    EC.presence_of_element_located((By.CLASS_NAME, "product-item"))
                )
            except:
                print(f"⚠️ {kategori_adi} sayfasında ürünler zamanında yüklenmedi.")

            # Daha fazla ürün için aşağı kaydır
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
            time.sleep(2)
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(3)

            urun_kartlari = driver.find_elements(By.CSS_SELECTOR, ".product-item, .product-card, [class*='product-item']")
            
            for kart in urun_kartlari:
                try:

                    isim_elemanlari = kart.find_elements(By.CSS_SELECTOR, ".product-title, .name, h3")
                    fiyat_elemanlari = kart.find_elements(By.CSS_SELECTOR, ".product-price, .price, .current-price")
                    
                    if isim_elemanlari and fiyat_elemanlari:
                        isim = isim_elemanlari[0].text.strip()
                        fiyat = fiyat_elemanlari[0].text.strip().replace("TL", "").replace("₺", "").strip()
                        
                        if isim and fiyat:
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

    # Verileri CSV'ye yaz
    with open(csv_dosyasi, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["kategori", "product_name", "product_price"])
        writer.writeheader()
        writer.writerows(tum_urunler)

    print(f"\n🎉 Tamamlandı! Toplam {len(tum_urunler)} ürün kaydedildi.")

if __name__ == "__main__":
    main()
