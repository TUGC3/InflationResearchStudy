import os
import sys
import csv
import time
import random
import shutil
from datetime import datetime
from bs4 import BeautifulSoup

os.chdir(os.path.dirname(os.path.abspath(__file__)))

try:
    import undetected_chromedriver as uc
except ImportError:
    print("undetected-chromedriver paketi bulunamadi!")
    print("Terminal'de su komutu calistir:")
    print("pip install undetected-chromedriver beautifulsoup4")
    sys.exit(1)

CUSTOM_OUTPUT_DIR = None
CHROME_VERSION = 145

GENERAL_BRACKETS = [
    (0, 12000),
    (12001, 15000),
    (15001, 18000),
    (18001, 22000),
    (22001, 28000),
    (28001, 35000),
    (35001, 9999999),
]

CITIES = {
    'isparta': 'Isparta',
    'burdur': 'Burdur',
    'igdir': 'Igdir',
    'agri': 'Agri',
    'ardahan': 'Ardahan',
    'batman': 'Batman',
    'siirt': 'Siirt',
    'sirnak': 'Sirnak',
    'kastamonu': 'Kastamonu',
}

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

if CUSTOM_OUTPUT_DIR:
    DATA_BASE_DIR = CUSTOM_OUTPUT_DIR
else:
    DATA_BASE_DIR = os.path.join(
        SCRIPT_DIR,
        "Datas", "HouseRent",
        "Isparta_Burdur_Igdir_Agri_Ardahan_Batman_Siirt_Sirnak_Kastamonu"
    )

_profile_counter = 0


def setup_driver():
    global _profile_counter
    _profile_counter += 1

    options = uc.ChromeOptions()
    profile_path = os.path.join(SCRIPT_DIR, "SeleniumProfile_" + str(_profile_counter))
    options.add_argument("--user-data-dir=" + profile_path)
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--start-maximized')
    options.add_argument('--log-level=3')

    try:
        if CHROME_VERSION:
            driver = uc.Chrome(options=options, version_main=CHROME_VERSION)
        else:
            driver = uc.Chrome(options=options)
    except Exception as e:
        print("Chrome baslatma hatasi: " + str(e))
        raise

    print("Chrome basladi.")
    return driver


def close_driver(driver):
    try:
        driver.quit()
    except Exception:
        pass
    print("Chrome kapatildi.")


def save_to_csv_incremental(data_batch):
    today_str = datetime.now().strftime("%Y-%m-%d")
    os.makedirs(DATA_BASE_DIR, exist_ok=True)
    file_path = os.path.join(DATA_BASE_DIR, today_str + ".csv")

    file_exists = os.path.isfile(file_path)
    with open(file_path, mode='a', newline='', encoding='utf-8-sig') as file:
        writer = csv.DictWriter(file, fieldnames=["City", "District", "Rooms", "Price"])
        if not file_exists:
            writer.writeheader()
        writer.writerows(data_batch)
    print(str(len(data_batch)) + " kayit eklendi -> " + file_path)


def scrape_city(driver, city_url_name, city_display_name):
    print("\n" + "=" * 50)
    print("SEHIR: " + city_display_name.upper())
    print("=" * 50)

    total_saved = 0

    for min_price, max_price in GENERAL_BRACKETS:
        print("\n>>> Aralik: " + str(min_price) + " - " + str(max_price) + " TL")
        page_num = 1
        url = (
            "https://www.sahibinden.com/kiralik/" + city_url_name +
            "?pagingSize=50&price_min=" + str(min_price) + "&price_max=" + str(max_price)
        )

        driver.get(url)
        time.sleep(random.uniform(6, 9))

        while True:
            page_source = driver.page_source
            soup = BeautifulSoup(page_source, 'html.parser')
            listings = soup.select("#searchResultsTable tbody tr.searchResultsItem")

            if not listings:
                if "giris yap" in page_source.lower() or "captcha" in page_source.lower():
                    print("Bot korumasi! Tarayicida islemi tamamla, bekleniyor...")
                    time.sleep(15)
                    continue
                else:
                    print("  Sayfa " + str(page_num) + ": ilan bulunamadi.")
                    break

            print("  Sayfa " + str(page_num) + " -> " + str(len(listings)) + " ilan bulundu")
            batch = []

            for row in listings:
                try:
                    price_elem = row.select_one(".searchResultsPriceValue")
                    price = price_elem.text.strip() if price_elem else "N/A"

                    location_elem = row.select_one(".searchResultsLocationValue")
                    district = " / ".join(location_elem.stripped_strings) if location_elem else "N/A"

                    attributes = row.select(".searchResultsAttributeValue")
                    rooms = attributes[1].text.strip() if len(attributes) > 1 else "N/A"

                    if price != "N/A":
                        batch.append({
                            "City": city_display_name,
                            "District": district,
                            "Rooms": rooms,
                            "Price": price
                        })

                except Exception as e:
                    print("  Satir hatasi: " + str(e))
                    continue

            if batch:
                save_to_csv_incremental(batch)
                total_saved += len(batch)

            next_button = soup.find('a', title='Sonraki')
            if next_button and 'href' in next_button.attrs:
                next_url = "https://www.sahibinden.com" + next_button['href']
                driver.get(next_url)
                page_num += 1
                time.sleep(random.uniform(4, 7))
            else:
                break

    print("\n" + city_display_name + " TAMAMLANDI - Toplam kaydedilen: " + str(total_saved))
    return driver


def cleanup_profiles():
    for item in os.listdir(SCRIPT_DIR):
        if item.startswith("SeleniumProfile_"):
            try:
                shutil.rmtree(os.path.join(SCRIPT_DIR, item))
            except Exception:
                pass


def main():
    print("=" * 50)
    print("Sahibinden.com Kiralik Ilan Scraper")
    print("=" * 50)
    print("Cikti klasoru: " + DATA_BASE_DIR)
    print("Sehir sayisi : " + str(len(CITIES)))

    driver = setup_driver()

    try:
        for city_key, city_name in CITIES.items():
            driver = scrape_city(driver, city_key, city_name)
            print("\n--- " + city_name + " bitti, sonraki sehre geciliyor... ---")
            time.sleep(random.uniform(10, 15))

    except KeyboardInterrupt:
        print("\nKullanici tarafindan durduruldu.")

    finally:
        close_driver(driver)
        cleanup_profiles()
        print("\nTum sehirler tamamlandi!")


if __name__ == "__main__":
    main()
