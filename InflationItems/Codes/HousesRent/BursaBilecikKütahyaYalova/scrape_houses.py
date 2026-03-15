import os
import csv
import time
import random
from datetime import datetime
from bs4 import BeautifulSoup
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

# Configuration
# HEAVY_BRACKETS: 17 micro-brackets for massive cities to avoid the 1,000 limit
HEAVY_BRACKETS = [
    (0, 11999), (12000, 13999), (14000, 14999), (15000, 15999), (16000, 16999),
    (17000, 17999), (18000, 18999), (19000, 19999), (20000, 20999),
    (21000, 22999), (23000, 24999), (25000, 26999),
    (27000, 29999), (30000, 34999), (35000, 39999), (40000, 49999),
    (50000, 9999999)
]

# LIGHT_BRACKETS: Just 5 wide brackets for smaller cities
LIGHT_BRACKETS = [
    (0, 10000), (10001, 15000), (15001, 20000), (20001, 25000), (25001, 9999999)
]

# Map the cities to their specific folder names AND their required bracket strategy
CITIES = {
    'bursa':   {'folder': 'Bursa',   'brackets': HEAVY_BRACKETS},
    'yalova':  {'folder': 'Yalova',  'brackets': LIGHT_BRACKETS},
    'bilecik': {'folder': 'Bilecik', 'brackets': LIGHT_BRACKETS},
    'kutahya': {'folder': 'Kütahya', 'brackets': LIGHT_BRACKETS}
}

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_BASE_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, "../../../Datas/HousesRent/"))


def setup_driver():
    """Sets up an undetected Chrome driver with a persistent profile."""
    options = uc.ChromeOptions()
    # SeleniumProfile lives in the same directory as this script
    profile_path = os.path.join(SCRIPT_DIR, "SeleniumProfile")
    options.add_argument(f"--user-data-dir={profile_path}")
    driver = uc.Chrome(options=options, version_main=145)
    return driver


def save_to_csv_incremental(folder_name, data_batch):
    """Appends a batch of scraped data to the daily CSV file to prevent data loss."""
    today_str = datetime.now().strftime("%Y-%m-%d")
    target_dir = os.path.join(DATA_BASE_DIR, folder_name)
    os.makedirs(target_dir, exist_ok=True)
    file_path = os.path.join(target_dir, f"{folder_name}_{today_str}.csv")

    file_exists = os.path.isfile(file_path)

    with open(file_path, mode='a', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=["District", "Rooms", "Price"])
        if not file_exists:
            writer.writeheader()
        writer.writerows(data_batch)

    print(f"✅ Appended {len(data_batch)} records to {file_path}")


def wait_for_listings(driver, timeout=15):
    """
    Waits up to `timeout` seconds for the results table to be present in the DOM.
    Falls back gracefully if the element never appears (e.g. CAPTCHA page).
    Returns True if listings are visible, False otherwise.
    """
    try:
        WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, "#searchResultsTable tbody tr.searchResultsItem")
            )
        )
        return True
    except TimeoutException:
        return False


def scrape_city(driver, city_url_name, folder_name, brackets):
    """Scrapes data by looping through dynamically assigned price brackets."""
    print(f"\n{'='*50}")
    print(f"STARTING FULL SCRAPE FOR: {folder_name}")
    print(f"{'='*50}")

    for min_price, max_price in brackets:
        print(f"\n>>> Targeting Price Range: {min_price} TL to {max_price} TL")

        url = (
            f"https://www.sahibinden.com/kiralik/{city_url_name}"
            f"?pagingSize=50&price_min={min_price}&price_max={max_price}"
        )
        driver.get(url)

        # Initial page load delay — give the site time to breathe
        time.sleep(random.uniform(3.5, 5.0))

        bracket_data = []
        page_num = 1

        while True:
            listings_visible = wait_for_listings(driver, timeout=15)

            soup = BeautifulSoup(driver.page_source, 'lxml')
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

                soup = BeautifulSoup(driver.page_source, 'lxml')
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
                # Slower inter-page delay to avoid getting banned
                time.sleep(random.uniform(3.0, 5.0))
            else:
                print(f"Finished gathering all houses in the {min_price}-{max_price} TL range.")
                break

        if bracket_data:
            save_to_csv_incremental(folder_name, bracket_data)

        # Slower inter-bracket delay to avoid getting banned
        time.sleep(random.uniform(3.5, 7.0))


def main():
    driver = setup_driver()
    try:
        for city_url_name, city_data in CITIES.items():
            scrape_city(
                driver,
                city_url_name,
                city_data['folder'],
                city_data['brackets'],
            )
            # Slower inter-city delay
            time.sleep(random.uniform(4.0, 8.0))
    finally:
        driver.quit()


if __name__ == "__main__":
    main()