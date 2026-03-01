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
    "diyarbakir": "Diyarbakir",
    "sanliurfa": "Sanliurfa",
    "mardin": "Mardin",
}

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_BASE_DIR = os.path.abspath(
    os.path.join(SCRIPT_DIR, "../../../Datas/HousesRent/DiyarbakirSanliurfaMardin/")
)

# If running in CI (GitHub Actions), use headless mode
IS_CI = os.environ.get("CI", "false").lower() == "true"


def setup_driver():
    """Sets up an undetected Chrome driver."""
    options = uc.ChromeOptions()

    if IS_CI:
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
    else:
        profile_path = os.path.join(SCRIPT_DIR, "SeleniumProfile")
        options.add_argument(f"--user-data-dir={profile_path}")

    version = int(os.environ.get("CHROME_VERSION", "0")) or None
    driver = uc.Chrome(options=options, version_main=version)
    return driver


def scrape_city(driver, city_url_name, folder_name):
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
            if IS_CI:
                print(f"No listings found for {folder_name} (possible CAPTCHA). Skipping.")
                break
            else:
                print("\n" + "=" * 50)
                print("ACTION REQUIRED: No listings found.")
                print("Likely CAPTCHA or login page appeared.")
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
                    print(f"Still no listings (check {attempt}/{max_checks}). Refreshing...")
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
                    location_elem.text.strip().replace("\n", " ") if location_elem else "N/A"
                )

                attributes = row.select(".searchResultsAttributeValue")
                rooms = extract_rooms(attributes, room_index)

                if price is not None and district != "N/A":
                    all_scraped_data.append({"District": district, "Rooms": rooms, "Price": price})
            except Exception as exc:
                print(f"Row parse error: {exc}")
                continue

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


def resolve_rooms_index(soup):
    headers = [
        th.get_text(strip=True)
        for th in soup.select("#searchResultsTable thead th.searchResultsAttributeHeader")
    ]
    for idx, header in enumerate(headers):
        if "oda" in header.lower().replace("ı", "i"):
            return idx
    return None


def extract_rooms(attributes, room_index):
    if room_index is not None and len(attributes) > room_index:
        return attributes[room_index].text.strip()
    if len(attributes) > 1:
        return attributes[1].text.strip()
    if len(attributes) == 1:
        return attributes[0].text.strip()
    return "N/A"


def save_to_csv(folder_name, data):
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
    if not price_text or price_text == "N/A":
        return None
    cleaned = price_text.lower().replace("tl", "").replace("₺", "").strip()
    cleaned = re.sub(r"[^\d,\.]", "", cleaned)
    if not cleaned:
        return None
    if "." in cleaned and "," in cleaned:
        cleaned = cleaned.replace(".", "").replace(",", ".")
    elif "," in cleaned:
        cleaned = cleaned.replace(",", ".")
    elif "." in cleaned:
        parts = cleaned.split(".")
        if len(parts) > 1 and all(p.isdigit() for p in parts):
            if all(len(p) == 3 for p in parts[1:]):
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
