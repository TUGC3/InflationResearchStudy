import os
import csv
import time
import random
from datetime import datetime
from bs4 import BeautifulSoup
import undetected_chromedriver as uc
import re

# Configuration for assigned cities
CITIES = {
    "mugla": "Mugla",
    "aydin": "Aydin",
    "denizli": "Denizli",
}

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# Save data under Datas/HousesRent/MuglaDenizliAydin/<City>/
DATA_BASE_DIR = os.path.abspath(
    os.path.join(SCRIPT_DIR, "../../../Datas/HousesRent/MuglaDenizliAydin/")
)


def setup_driver():
    """Sets up an undetected Chrome driver with a persistent profile."""
    options = uc.ChromeOptions()

    # Create a persistent profile directory so you stay logged in
    profile_path = os.path.join(SCRIPT_DIR, "SeleniumProfile")
    options.add_argument(f"--user-data-dir={profile_path}")

    # Initialize undetected-chromedriver
    driver = uc.Chrome(options=options, version_main=145)
    return driver


def scrape_city(driver, city_url_name, folder_name):
    """Scrapes data for a specific city, handling CAPTCHAs and all pages."""
    url = f"https://www.sahibinden.com/kiralik/{city_url_name}?pagingSize=50"

    print(f"\nLoading {url}...")
    driver.get(url)

    all_scraped_data = []
    page_num = 1

    while True:
        time.sleep(2.5)

        soup = BeautifulSoup(driver.page_source, "html.parser")
        listings = soup.select("#searchResultsTable tbody tr.searchResultsItem")

        # CAPTCHA / LOGIN check
        if not listings:
            print("\n" + "=" * 50)
            print("ACTION REQUIRED: No listings found.")
            print("Likely CAPTCHA or login page appeared.")
            print("1. Check the Chrome window and solve CAPTCHA or log in.")
            print("2. Wait until listings appear.")
            print(f"Current URL: {driver.current_url}")
            print("=" * 50)
            input("After you can see listings, press ENTER here...")

            # Auto-retry with refresh to avoid getting stuck after CAPTCHA
            max_checks = 10
            for attempt in range(1, max_checks + 1):
                time.sleep(2)
                soup = BeautifulSoup(driver.page_source, "html.parser")
                listings = soup.select("#searchResultsTable tbody tr.searchResultsItem")
                if listings:
                    break
                print(
                    f"Still no listings (check {attempt}/{max_checks}). "
                    "Refreshing page..."
                )
                driver.refresh()

            if not listings:
                print(f"Still no listings for {folder_name}. Skipping.")
                break

        print(f"Scraping {folder_name} page {page_num} (50 per page)...")

        for row in listings:
            try:
                price_elem = row.select_one(".searchResultsPriceValue")
                price_raw = price_elem.text.strip() if price_elem else "N/A"
                price = normalize_price(price_raw)

                location_elem = row.select_one(".searchResultsLocationValue")
                district = (
                    location_elem.text.strip().replace("\n", " ")
                    if location_elem
                    else "N/A"
                )

                attributes = row.select(".searchResultsAttributeValue")
                rooms = attributes[0].text.strip() if len(attributes) > 0 else "N/A"

                if price is not None and district != "N/A":
                    all_scraped_data.append(
                        {"District": district, "Rooms": rooms, "Price": price}
                    )
            except Exception as exc:
                print(f"Row parse error: {exc}")
                continue

        # Next page
        next_button = soup.find("a", title="Sonraki")
        if next_button and "href" in next_button.attrs:
            next_url = "https://www.sahibinden.com" + next_button["href"]
            driver.get(next_url)
            page_num += 1
            time.sleep(random.uniform(2, 4))
        else:
            print(f"Finished all pages for {folder_name}.")
            break

    if all_scraped_data:
        save_to_csv(folder_name, all_scraped_data)


def save_to_csv(folder_name, data):
    """Saves the scraped data to a daily CSV file in the correct directory."""
    today_str = datetime.now().strftime("%Y-%m-%d")

    target_dir = os.path.join(DATA_BASE_DIR, folder_name)
    os.makedirs(target_dir, exist_ok=True)

    file_path = os.path.join(target_dir, f"{today_str}.csv")

    with open(file_path, mode="w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=["District", "Rooms", "Price"])
        writer.writeheader()
        writer.writerows(data)

    print(f"Saved {len(data)} records to {file_path}")


def normalize_price(price_text):
    """Convert Turkish price text like '12.500 TL' to float 12500.0."""
    if not price_text or price_text == "N/A":
        return None
    cleaned = price_text.lower()
    cleaned = cleaned.replace("tl", "").replace("₺", "").strip()
    cleaned = re.sub(r"[^\d,\.]", "", cleaned)
    if not cleaned:
        return None
    # If both dot and comma exist, assume dot is thousands and comma is decimal.
    if "." in cleaned and "," in cleaned:
        cleaned = cleaned.replace(".", "").replace(",", ".")
    else:
        # If only comma, treat as decimal separator.
        if "," in cleaned:
            cleaned = cleaned.replace(",", ".")
        elif "." in cleaned:
            # If dot looks like thousands separator (e.g., 29.000), remove it.
            # If dot looks like decimal (e.g., 29.5 or 29.50), keep it.
            parts = cleaned.split(".")
            if len(parts) > 1 and all(part.isdigit() for part in parts):
                # If every group after the first has exactly 3 digits, treat as thousands.
                if all(len(part) == 3 for part in parts[1:]):
                    cleaned = "".join(parts)
    try:
        return float(cleaned)
    except ValueError:
        return None


def main():
    driver = setup_driver()
    try:
        for city_url_name, folder_name in CITIES.items():
            print(f"\n--- Scraping {folder_name} ---")
            scrape_city(driver, city_url_name, folder_name)
            time.sleep(5)
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
