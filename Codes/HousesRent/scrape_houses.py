import os
import csv
import time
import random
from datetime import datetime
from bs4 import BeautifulSoup
import undetected_chromedriver as uc

# Configuration
# HEAVY_BRACKETS: 23 micro-brackets for massive cities to avoid the 1,000 limit
HEAVY_BRACKETS = [
    (0, 9999), (10000, 10999), (11000, 11999), (12000, 12999),
    (13000, 13999), (14000, 14999), (15000, 15999), (16000, 16999),
    (17000, 17999), (18000, 18999), (19000, 19999), (20000, 20999),
    (21000, 21999), (22000, 22999), (23000, 24999), (25000, 27499),
    (27500, 29999), (30000, 34999), (35000, 39999), (40000, 49999),
    (50000, 74999), (75000, 149999), (150000, 9999999)
]

# LIGHT_BRACKETS: Just 3 wide brackets for smaller cities to complete the scrape in seconds
# We use 3 instead of 1 just in case a smaller city slightly exceeds 1,000 total listings.
LIGHT_BRACKETS = [
    (0, 15000),
    (15001, 25000),
    (25001, 9999999)
]

# Map the cities to their specific folder names AND their required bracket strategy
CITIES = {
    'bursa': {'folder': 'Bursa', 'brackets': HEAVY_BRACKETS},
    'yalova': {'folder': 'Yalova', 'brackets': LIGHT_BRACKETS},
    'bilecik': {'folder': 'Bilecik', 'brackets': LIGHT_BRACKETS},
    'kutahya': {'folder': 'Kütahya', 'brackets': LIGHT_BRACKETS}
}

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_BASE_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, "../../Datas/HousesRent/"))


def setup_driver():
    """Sets up an undetected Chrome driver with a persistent profile."""
    options = uc.ChromeOptions()
    profile_path = os.path.join(SCRIPT_DIR, "SeleniumProfile")
    options.add_argument(f"--user-data-dir={profile_path}")
    driver = uc.Chrome(options=options, version_main=145)
    return driver


def save_to_csv_incremental(folder_name, data_batch):
    """Appends a batch of scraped data to the daily CSV file to prevent data loss."""
    today_str = datetime.now().strftime("%Y-%m-%d")
    target_dir = os.path.join(DATA_BASE_DIR, folder_name)
    os.makedirs(target_dir, exist_ok=True)
    file_path = os.path.join(target_dir, f"{today_str}.csv")

    # Check if file exists to decide whether to write headers
    file_exists = os.path.isfile(file_path)

    with open(file_path, mode='a', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=["District", "Rooms", "Price"])
        if not file_exists:
            writer.writeheader()  # Only write headers if the file is brand new
        writer.writerows(data_batch)

    print(f"✅ Appended {len(data_batch)} records to {file_path}")


def scrape_city(driver, city_url_name, folder_name, brackets): # <-- Added 'brackets'
    """Scrapes data by looping through dynamically assigned price brackets."""
    print(f"\n{'='*50}")
    print(f"STARTING FULL SCRAPE FOR: {folder_name}")
    print(f"{'='*50}")

    for min_price, max_price in brackets:
        print(f"\n>>> Targeting Price Range: {min_price} TL to {max_price} TL")

        url = f"https://www.sahibinden.com/kiralik/{city_url_name}?pagingSize=50&price_min={min_price}&price_max={max_price}"
        driver.get(url)

        bracket_data = []  # Stores data ONLY for the current price bracket
        page_num = 1

        while True:
            time.sleep(2.5)

            soup = BeautifulSoup(driver.page_source, 'html.parser')
            listings = soup.select("#searchResultsTable tbody tr.searchResultsItem")

            if not listings:
                page_source_lower = driver.page_source.lower()
                if "ilan bulunamadı" in page_source_lower or "bulunamamıştır" in page_source_lower:
                    print(f"No houses exist between {min_price}-{max_price} TL. Moving to next bracket.")
                    break

                print("\n" + "=" * 50)
                print("⚠️ ACTION REQUIRED: Script blocked by CAPTCHA or Login.")
                print("1. Look at the Chrome window and solve the puzzle.")
                print("2. Wait until you clearly see the list of houses.")
                print("=" * 50)
                input("Press ENTER here in the terminal ONLY AFTER you see the listings...")

                soup = BeautifulSoup(driver.page_source, 'html.parser')
                listings = soup.select("#searchResultsTable tbody tr.searchResultsItem")

                if not listings:
                    print(f"Still failing to load {min_price}-{max_price} TL. Skipping bracket.")
                    break

            print(f"Scraping page {page_num} for bracket {min_price}-{max_price} TL...")

            for row in listings:
                try:
                    price_elem = row.select_one(".searchResultsPriceValue")
                    price = price_elem.text.strip() if price_elem else "N/A"

                    location_elem = row.select_one(".searchResultsLocationValue")
                    district = " / ".join(location_elem.stripped_strings) if location_elem else "N/A"

                    attributes = row.select(".searchResultsAttributeValue")
                    rooms = attributes[1].text.strip() if len(attributes) > 1 else "N/A"

                    if price != "N/A" and district != "N/A":
                        bracket_data.append({
                            "District": district,
                            "Rooms": rooms,
                            "Price": price
                        })
                except Exception as e:
                    print(f"Error parsing a row: {e}")
                    continue

            # Pagination
            next_button = soup.find('a', title='Sonraki')
            if next_button and 'href' in next_button.attrs:
                next_url = "https://www.sahibinden.com" + next_button['href']
                driver.get(next_url)
                page_num += 1
                time.sleep(random.uniform(2, 4))
            else:
                print(f"Finished gathering all houses in the {min_price}-{max_price} TL range.")
                break

        # Save the data for this specific bracket before moving to the next one
        if bracket_data:
            save_to_csv_incremental(folder_name, bracket_data)

        # Brief pause between price brackets
        time.sleep(random.uniform(2, 4))


def main():
    driver = setup_driver()
    try:
        # Delete old test files to prevent duplicates
        today_str = datetime.now().strftime("%Y-%m-%d")
        for city_data in CITIES.values():
            file_path = os.path.join(DATA_BASE_DIR, city_data['folder'], f"{today_str}.csv")
            if os.path.exists(file_path):
                os.remove(file_path)
                print(f"Removed old test file: {file_path}")

        # Loop through the cities and pass their specific brackets
        for city_url_name, city_data in CITIES.items():
            scrape_city(driver, city_url_name, city_data['folder'], city_data['brackets'])
            time.sleep(5)
    finally:
        driver.quit()


if __name__ == "__main__":
    main()