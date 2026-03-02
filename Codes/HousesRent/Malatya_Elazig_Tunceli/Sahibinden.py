import os
import csv
import time
import random
from datetime import datetime
from bs4 import BeautifulSoup
import undetected_chromedriver as uc
import re

# Şehir ve Alt Sorgu Konfigürasyonu
CITIES_CONFIG = {
    "malatya": [
        "malatya?price_max=16000",
        "malatya?price_min=16001"
    ],
    "elazig": [
        "elazig?price_max=16000",
        "elazig?price_min=16001"
    ],
    "tunceli": [
        "tunceli?price_max=16000",
        "tunceli?price_min=16001"
    ]
}

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_BASE_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, "ScrapedData"))


def setup_driver():
    options = uc.ChromeOptions()
    profile_path = os.path.join(SCRIPT_DIR, "SeleniumProfile")
    options.add_argument(f"--user-data-dir={profile_path}")
    driver = uc.Chrome(options=options, version_main=145)
    return driver


def scrape_segment(driver, url_suffix, city_name):
    base_path = f"https://www.sahibinden.com/kiralik-daire/{url_suffix}"
    url = f"{base_path}&pagingSize=50" if "?" in url_suffix else f"{base_path}?pagingSize=50"

    print(f"\nSorgu Başlatıldı: {url}")
    driver.get(url)

    all_data = []
    page_num = 1

    while True:
        time.sleep(random.uniform(3.5, 5.5))
        soup = BeautifulSoup(driver.page_source, "html.parser")
        listings = soup.select("#searchResultsTable tbody tr.searchResultsItem")

        if not listings:
            print("\n" + "=" * 50)
            print(f"WAF ENGELİ: {city_name} ilanları yüklenemedi.")
            input("Lütfen tarayıcıda doğrulamayı geçin ve ardından ENTER'a basın.")
            print("=" * 50)
            driver.refresh()
            continue

        print(f"[{city_name.upper()}] Sayfa {page_num} işleniyor...")

        for row in listings:
            try:
                price_elem = row.select_one(".searchResultsPriceValue")
                price = normalize_price(price_elem.text.strip()) if price_elem else None

                location_elem = row.select_one(".searchResultsLocationValue")
                district = location_elem.get_text(separator=" ", strip=True) if location_elem else "N/A"

                attributes = row.select(".searchResultsAttributeValue")
                rooms = extract_rooms(attributes)

                if price is not None and district != "N/A":
                    all_data.append({
                        "District": district,
                        "Rooms": rooms,
                        "Price": price
                    })
            except Exception:
                continue

        next_button = soup.find("a", title="Sonraki")
        if next_button and "href" in next_button.attrs:
            next_url = "https://www.sahibinden.com" + next_button["href"]
            driver.get(next_url)
            page_num += 1
            time.sleep(random.uniform(4, 8))
        else:
            break

    return all_data


def extract_rooms(attributes):
    if not attributes: return "N/A"
    room_pattern = re.compile(r'(\d\+\d|Stüdyo|Studio|\d\.5\+\d)', re.IGNORECASE)
    for attr in attributes:
        text = attr.get_text(strip=True)
        if room_pattern.search(text):
            return text
    return "N/A"


def save_to_csv(city_name, data):
    """Verileri o güne özel tarihli CSV dosyasına yazar (İçerikte Date sütunu yoktur)."""
    today_str = datetime.now().strftime("%Y-%m-%d")
    os.makedirs(DATA_BASE_DIR, exist_ok=True)

    # Dosya ismi tarih bilgisini taşımaya devam eder
    file_path = os.path.join(DATA_BASE_DIR, f"{today_str}_{city_name}.csv")

    file_exists = os.path.isfile(file_path)
    # Date sütunu fieldnames listesinden çıkartıldı
    fieldnames = ["District", "Rooms", "Price"]

    with open(file_path, mode="a", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerows(data)
    print(f"{len(data)} satır {file_path} dosyasına eklendi.")


def normalize_price(price_text):
    try:
        return float(re.sub(r"[^\d]", "", price_text.split("TL")[0].replace(".", "")))
    except:
        return None


def main():
    driver = setup_driver()
    try:
        for city_name, segments in CITIES_CONFIG.items():
            print(f"\n--- {city_name.upper()} İÇİN VERİ TOPLAMA BAŞLADI ---")
            for segment_url in segments:
                segment_data = scrape_segment(driver, segment_url, city_name)
                if segment_data:
                    save_to_csv(city_name, segment_data)
                time.sleep(random.uniform(8, 15))
    finally:
        driver.quit()


if __name__ == "__main__":
    main()