# -*- coding: utf-8 -*-
"""
Created on Sun Mar  8 15:46:51 2026

@author: orenl
"""

import os
import csv
import time
import random
from datetime import datetime
from bs4 import BeautifulSoup
import undetected_chromedriver as uc
import re

# Yeni Şehirler ve İlçeleri
CITIES_DATA = {
    "Eskisehir": {
        "eskisehir-odunpazari": "Eskisehir_Odunpazari",
        "eskisehir-tepebasi": "Eskisehir_Tepebasi",
        "eskisehir-alpu": "Eskisehir_Alpu",
        "eskisehir-beylikova": "Eskisehir_Beylikova",
        "eskisehir-cifteler": "Eskisehir_Cifteler",
        "eskisehir-gunyuzu": "Eskisehir_Gunyuzu",
        "eskisehir-han": "Eskisehir_Han",
        "eskisehir-inonu": "Eskisehir_Inonu",
        "eskisehir-mahmudiye": "Eskisehir_Mahmudiye",
        "eskisehir-mihalalgazi": "Eskisehir_Mihalgazi",
        "eskisehir-mihaliccik": "Eskisehir_Mihaliccik",
        "eskisehir-saricakaya": "Eskisehir_Saricakaya",
        "eskisehir-seyitgazi": "Eskisehir_Seyitgazi",
        "eskisehir-sivrihisar": "Eskisehir_Sivrihisar",
    },
    "Bolu": {
        "bolu-merkez": "Bolu_Merkez",
        "bolu-dortdivan": "Bolu_Dortdivan",
        "bolu-gerede": "Bolu_Gerede",
        "bolu-goynuk": "Bolu_Goynuk",
        "bolu-kibriscik": "Bolu_Kibriscik",
        "bolu-mengen": "Bolu_Mengen",
        "bolu-mudurnu": "Bolu_Mudurnu",
        "bolu-seben": "Bolu_Seben",
        "bolu-yenicaga": "Bolu_Yenicaga",
    },
    "Bartin": {
        "bartin-merkez": "Bartin_Merkez",
        "bartin-amasra": "Bartin_Amasra",
        "bartin-kurucasile": "Bartin_Kurucasile",
        "bartin-ulus": "Bartin_Ulus",
    },
    "Zonguldak": {
        "zonguldak-merkez": "Zonguldak_Merkez",
        "zonguldak-alapli": "Zonguldak_Alapli",
        "zonguldak-caycuma": "Zonguldak_Caycuma",
        "zonguldak-devrek": "Zonguldak_Devrek",
        "zonguldak-eregli": "Zonguldak_Eregli",
        "zonguldak-gokcebey": "Zonguldak_Gokcebey",
        "zonguldak-kilimli": "Zonguldak_Kilimli",
        "zonguldak-kozlu": "Zonguldak_Kozlu",
    }
}

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DESKTOP_PATH = os.path.join(os.path.expanduser("~"), "Desktop", "Datas", "HousesRent")

def setup_driver():
    options = uc.ChromeOptions()
    profile_path = os.path.join(SCRIPT_DIR, "SeleniumProfile")
    options.add_argument(f"--user-data-dir={profile_path}")
    driver = uc.Chrome(options=options, version_main=145)
    return driver

def scrape_city(driver, city_url_name, folder_name, base_dir):
    url = f"https://www.sahibinden.com/kiralik/{city_url_name}?pagingSize=50"
    print(f"\nLoading {url}...")
    driver.get(url)

    all_scraped_data = []
    page_num = 1

    while True:
        time.sleep(2.5)
        soup = BeautifulSoup(driver.page_source, "html.parser")
        listings = soup.select("#searchResultsTable tbody tr.searchResultsItem")
        room_index = resolve_rooms_index(soup)

        if not listings:
            print("\n" + "=" * 50)
            print("ACTION REQUIRED: No listings found.")
            print(f"Current URL: {driver.current_url}")
            print("=" * 50)
            input("After you can see listings, press ENTER here...")
            
            max_checks = 10
            for attempt in range(1, max_checks + 1):
                time.sleep(2)
                soup = BeautifulSoup(driver.page_source, "html.parser")
                listings = soup.select("#searchResultsTable tbody tr.searchResultsItem")
                if listings:
                    break
                print(f"Still no listings (check {attempt}/{max_checks}). Refreshing page...")
                driver.refresh()

            if not listings:
                break

        print(f"Scraping {folder_name} page {page_num}...")

        for row in listings:
            try:
                price_elem = row.select_one(".searchResultsPriceValue")
                price_raw = price_elem.text.strip() if price_elem else "N/A"
                price = normalize_price(price_raw)

                location_elem = row.select_one(".searchResultsLocationValue")
                district = location_elem.text.strip().replace("\n", " ") if location_elem else "N/A"

                attributes = row.select(".searchResultsAttributeValue")
                rooms = extract_rooms(attributes, room_index)

                if price is not None and district != "N/A":
                    all_scraped_data.append({"District": district, "Rooms": rooms, "Price": price})
            except Exception as exc:
                continue

        next_button = soup.find("a", title="Sonraki")
        if next_button and "href" in next_button.attrs:
            next_url = "https://www.sahibinden.com" + next_button["href"]
            driver.get(next_url)
            page_num += 1
            time.sleep(random.uniform(2, 4))
        else:
            break

    if all_scraped_data:
        save_to_csv(folder_name, all_scraped_data, base_dir)

def resolve_rooms_index(soup):
    headers = [th.get_text(strip=True) for th in soup.select("#searchResultsTable thead th.searchResultsAttributeHeader")]
    for idx, header in enumerate(headers):
        header_norm = header.lower().replace("ı", "i")
        if "oda" in header_norm: return idx
    return None

def extract_rooms(attributes, room_index):
    if room_index is not None and len(attributes) > room_index: return attributes[room_index].text.strip()
    if len(attributes) > 1: return attributes[1].text.strip()
    return "N/A"

def save_to_csv(folder_name, data, base_dir):
    today_str = datetime.now().strftime("%Y-%m-%d")
    target_dir = os.path.join(base_dir, folder_name)
    os.makedirs(target_dir, exist_ok=True)
    file_path = os.path.join(target_dir, f"{today_str}.csv")

    with open(file_path, mode="w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=["District", "Rooms", "Price"])
        writer.writeheader()
        writer.writerows(data)
    print(f"✓ Saved {len(data)} records to {file_path}")

def normalize_price(price_text):
    if not price_text or price_text == "N/A": return None
    cleaned = price_text.lower().replace("tl", "").replace("₺", "").strip()
    cleaned = re.sub(r"[^\d,\.]", "", cleaned)
    if not cleaned: return None
    if "." in cleaned and "," in cleaned:
        cleaned = cleaned.replace(".", "").replace(",", ".")
    else:
        if "," in cleaned: cleaned = cleaned.replace(",", ".")
        elif "." in cleaned:
            parts = cleaned.split(".")
            if len(parts) > 1 and all(len(p) == 3 for p in parts[1:]): cleaned = "".join(parts)
    try: return float(cleaned)
    except: return None

def main():
    driver = setup_driver()
    try:
        for city_main_name, districts in CITIES_DATA.items():
            city_base_dir = os.path.join(DESKTOP_PATH, city_main_name)
            print(f"\n🚀 STARTING CITY: {city_main_name.upper()}")
            
            for i, (city_url_name, folder_name) in enumerate(districts.items(), 1):
                print(f"\n[{i}/{len(districts)}] {folder_name}...")
                scrape_city(driver, city_url_name, folder_name, city_base_dir)
                wait = random.uniform(5, 10)
                time.sleep(wait)
    finally:
        driver.quit()
        print("\nAll tasks completed!")

if __name__ == "__main__":
    main()
