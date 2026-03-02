import time
import csv
import os
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options

# --- HEADLESS AYARLARI ---
chrome_options = Options()
chrome_options.add_argument("--headless") 
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--window-size=1920,1080")
chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
wait = WebDriverWait(driver, 20)

KATEGORILER = [
    "https://ardenmarket.com.tr/et-ve-tavuk.html",
    "https://ardenmarket.com.tr/meyve-ve-sebze.html",
    "https://ardenmarket.com.tr/kahvaltilik.html",
    "https://ardenmarket.com.tr/sut-urunleri.html",
    "https://ardenmarket.com.tr/temel-gida.html",
    "https://ardenmarket.com.tr/dondurulmus-urunler.html",
    "https://ardenmarket.com.tr/unlu-mamul-tatli.html",
    "https://ardenmarket.com.tr/dondurma.html",
    "https://ardenmarket.com.tr/atistirmalik.html",
    "https://ardenmarket.com.tr/icecekler.html",
    "https://ardenmarket.com.tr/temizlik-urunleri.html",
    "https://ardenmarket.com.tr/kisisel-bakim.html",
    "https://ardenmarket.com.tr/bebek.html",
    "https://ardenmarket.com.tr/evcil-hayvan-urunleri.html",
    "https://ardenmarket.com.tr/ev-yasam-oyuncak.html",
    "https://ardenmarket.com.tr/ofis-ve-teknoloji.html",
    "https://ardenmarket.com.tr/firsat-urunleri.html",
    "https://ardenmarket.com.tr/catalog/category/view/s/sarkuteri-urunleri/id/4463/",
]

tum_urunler = []

def konum_sec():
    driver.get("https://ardenmarket.com.tr/")
    time.sleep(4)
    konum_btn = wait.until(EC.element_to_be_clickable((By.ID, "delivery-button")))
    konum_btn.click()
    time.sleep(2)
    Select(wait.until(EC.presence_of_element_located((By.ID, "delivery_state")))).select_by_value("İstanbul")
    time.sleep(2)
    ilce = Select(driver.find_element(By.ID, "delivery_city"))
    for o in ilce.options:
        if o.get_attribute("value") != "":
            ilce.select_by_value(o.get_attribute("value"))
            break
    time.sleep(2)
    mahalle = Select(driver.find_element(By.ID, "delivery_neighborhood"))
    for o in mahalle.options:
        if o.get_attribute("value") != "":
            mahalle.select_by_value(o.get_attribute("value"))
            break
    time.sleep(2)
    driver.find_element(By.CSS_SELECTOR, "#delivery-form button[type='submit']").click()
    print("✅ Konum seçildi")
    time.sleep(8)

def scroll_to_bottom():
    onceki = 0
    while True:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)
        yeni = driver.execute_script("return document.body.scrollHeight")
        if yeni == onceki:
            break
        onceki = yeni


def son_sayfa_numarasini_al():
    try:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)

        sayfa_linkleri = driver.find_elements(By.CSS_SELECTOR, ".pages-items .item a.page span:last-child")
        numaralar = []
        for span in sayfa_linkleri:
            try:
                numara = int(span.text.strip())
                numaralar.append(numara)
            except:
                continue 

        son = max(numaralar) if numaralar else 1
        print(f"  🔍 Bulunan sayfalar: {numaralar} → Son: {son}")
        return son
    except:
        return 1

def urunleri_topla(kategori_adi):
    urunler = driver.find_elements(By.CSS_SELECTOR, "li.product-item")
    sayfa_urunleri = []

    for u in urunler:
        try:
            isim = ""
            for sel in [".product-name", ".product-title", "h2", "h3", "[class*='name']"]:
                try:
                    isim = u.find_element(By.CSS_SELECTOR, sel).text.strip()
                    if isim:
                        break
                except:
                    continue

            fiyat = ""
            for sel in [".price-wrapper .price", ".price", "[class*='price']"]:
                try:
                    fiyat = u.find_element(By.CSS_SELECTOR, sel).text.strip()
                    if fiyat:
                        break
                except:
                    continue

            link = ""
            try:
                link = u.find_element(By.TAG_NAME, "a").get_attribute("href")
            except:
                pass

            resim = ""
            try:
                resim = u.find_element(By.TAG_NAME, "img").get_attribute("src")
            except:
                pass

            if isim or link:
                sayfa_urunleri.append({
                    "kategori": kategori_adi,
                    "isim": isim,
                    "fiyat": fiyat,
                    "link": link,
                    "resim": resim,
                })
        except:
            continue

    return sayfa_urunleri

try:
    konum_sec()

    for kategori_url in KATEGORILER:
        kategori_adi = kategori_url.split("/")[-1].replace(".html", "").replace("-", " ").title()
        print(f"\n📂 Kategori: {kategori_adi}")

        if "?" in kategori_url:
            base_url = kategori_url.split("?")[0]
        else:
            base_url = kategori_url

        driver.get(base_url)
        time.sleep(3)
        scroll_to_bottom()

        son_sayfa = son_sayfa_numarasini_al()
        print(f"  📊 Toplam sayfa: {son_sayfa}")

        for sayfa_no in range(1, son_sayfa + 1):
            if sayfa_no == 1:
                sayfa_url = base_url
            else:
                sayfa_url = f"{base_url}?p={sayfa_no}"

            print(f"  📄 Sayfa {sayfa_no}/{son_sayfa}: {sayfa_url}", end=" → ")

            if sayfa_no > 1:
                driver.get(sayfa_url)
                time.sleep(3)
                scroll_to_bottom()

            bulunanlar = urunleri_topla(kategori_adi)

            mevcut_linkler = {u["link"] for u in tum_urunler}
            yeni = [u for u in bulunanlar if u["link"] not in mevcut_linkler]
            tum_urunler.extend(yeni)

            print(f"{len(bulunanlar)} ürün, {len(yeni)} yeni | Toplam: {len(tum_urunler)}")

    #KAYIT VE DOSYALAMA BÖLÜMÜ (GÜNCELLENDİ)
    
    # os.getcwd() ana dizini verir. Veriler ana dizindeki 'data' klasörüne gider.
    # --- ÖZEL VERİ YOLU KAYDI ---
    
    # Projenin ana dizininden itibaren Datas/Markets/Arden yolunu oluşturur
    hedef_klasor = os.path.join(os.getcwd(), 'Datas', 'Markets', 'Arden')
    
    if not os.path.exists(hedef_klasor):
        os.makedirs(hedef_klasor)

    tarih_str = datetime.now().strftime("%Y-%m-%d")
    dosya_adi = os.path.join(hedef_klasor, f"arden_urunler_{tarih_str}.csv")

    with open(dosya_adi, "w", newline="", encoding="utf-8-sig") as f:
        fieldnames = ["kategori", "isim", "fiyat", "link", "resim"]
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(tum_urunler)

    print(f"\n{'='*50}")
    print(f"🎉 TOPLAM ÜRÜN: {len(tum_urunler)}")
    print(f"💾 {dosya_adi} başarıyla kaydedildi")
    print(f"{'='*50}")

finally:
    driver.quit()
