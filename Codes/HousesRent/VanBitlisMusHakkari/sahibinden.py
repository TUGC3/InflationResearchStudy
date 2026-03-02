import os
import csv
import time
import random
import shutil
from datetime import datetime
from bs4 import BeautifulSoup
import undetected_chromedriver as uc

# ============================================================
# Doğu Anadolu İlleri İçin Optimize Edilmiş Fiyat Aralıkları
# ============================================================
EAST_REGION_BRACKETS = [
    (0, 12000),
    (12001, 15000),
    (15001, 18000),
    (18001, 22000),
    (22001, 28000),
    (28001, 35000),
    (35001, 9999999),
]

CITIES = {
    'van': {'name': 'Van', 'brackets': EAST_REGION_BRACKETS},
    'bitlis': {'name': 'Bitlis', 'brackets': EAST_REGION_BRACKETS},
    'mus': {'name': 'Mus', 'brackets': EAST_REGION_BRACKETS},
    'hakkari': {'name': 'Hakkari', 'brackets': EAST_REGION_BRACKETS}
}

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

DATA_BASE_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, "../../../Datas/HousesRent/Tum_Ilanlar/"))

_profile_counter = 0


def setup_driver():

    global _profile_counter
    _profile_counter += 1

    options = uc.ChromeOptions()
    profile_path = os.path.join(SCRIPT_DIR, f"SeleniumProfile_{_profile_counter}")
    options.add_argument(f"--user-data-dir={profile_path}")



    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--start-maximized')

    try:

        driver = uc.Chrome(options=options, version_main=145)
    except Exception as e:
        print(f"⚠️ Versiyon hatası: {e}. Otomatik mod deneniyor...")
        driver = uc.Chrome(options=options)

    print(f"🚀 Chrome instance #{_profile_counter} başlatıldı. (Görünür Mod)")
    return driver


def close_driver(driver):
    try:
        driver.quit()
    except:
        pass
    print("🔒 Chrome kapatıldı.")


def save_to_csv_incremental(data_batch):
    today_str = datetime.now().strftime("%Y-%m-%d")
    os.makedirs(DATA_BASE_DIR, exist_ok=True)
    file_path = os.path.join(DATA_BASE_DIR, f"{today_str}.csv")

    file_exists = os.path.isfile(file_path)
    with open(file_path, mode='a', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=["City", "District", "Rooms", "Price"])
        if not file_exists:
            writer.writeheader()
        writer.writerows(data_batch)
    print(f"✅ {len(data_batch)} kayıt '{today_str}.csv' dosyasına eklendi.")


def scrape_city(driver, city_url_name, city_display_name, brackets):
    print(f"\n{'=' * 50}\nŞEHİR BAŞLATILDI: {city_display_name.upper()}\n{'=' * 50}")

    for min_price, max_price in brackets:
        print(f"\n>>> Aralık: {min_price} - {max_price} TL")
        page_num = 1
        url = f"https://www.sahibinden.com/kiralik/{city_url_name}?pagingSize=50&price_min={min_price}&price_max={max_price}"

        driver.get(url)

        time.sleep(random.uniform(6, 9))

        while True:
            page_source = driver.page_source
            soup = BeautifulSoup(page_source, 'html.parser')
            listings = soup.select("#searchResultsTable tbody tr.searchResultsItem")

            if not listings:
                # Eğer sayfa boşsa ve "giriş yap" yazıyorsa engel yemişizdir
                if "giriş yap" in page_source.lower() or "captcha" in page_source.lower():
                    print("🛑 Bot korumasına takıldık! Lütfen tarayıcıda işlemi manuel tamamla veya bekle.")
                    time.sleep(15)  # Manuel müdahale süresi
                    continue
                else:
                    print(f"Bu aralıkta (Sayfa {page_num}) ilan bulunamadı.")
                    break

            print(f"Sayfa {page_num} taranıyor... ({len(listings)} ilan)")
            bracket_data = []

            for row in listings:
                try:
                    price_elem = row.select_one(".searchResultsPriceValue")
                    price = price_elem.text.strip() if price_elem else "N/A"

                    location_elem = row.select_one(".searchResultsLocationValue")
                    district = " / ".join(location_elem.stripped_strings) if location_elem else "N/A"

                    attributes = row.select(".searchResultsAttributeValue")
                    rooms = attributes[1].text.strip() if len(attributes) > 1 else "N/A"

                    if price != "N/A":
                        bracket_data.append({
                            "City": city_display_name,
                            "District": district,
                            "Rooms": rooms,
                            "Price": price
                        })
                except:
                    continue

            if bracket_data:
                save_to_csv_incremental(bracket_data)


            next_button = soup.find('a', title='Sonraki')
            if next_button and 'href' in next_button.attrs:
                next_url = "https://www.sahibinden.com" + next_button['href']
                driver.get(next_url)
                page_num += 1
                time.sleep(random.uniform(4, 7))
            else:
                break

    return driver


def cleanup_profiles():
    for item in os.listdir(SCRIPT_DIR):
        if item.startswith("SeleniumProfile_"):
            try:
                shutil.rmtree(os.path.join(SCRIPT_DIR, item))
            except:
                pass


def main():
    driver = setup_driver()
    try:
        for city_key, city_info in CITIES.items():
            driver = scrape_city(driver, city_key, city_info['name'], city_info['brackets'])

            print(f"--- {city_info['name']} bitti, sonraki şehre geçiliyor... ---")
            time.sleep(random.uniform(10, 15))
    finally:
        close_driver(driver)
        cleanup_profiles()


if __name__ == "__main__":
    main()