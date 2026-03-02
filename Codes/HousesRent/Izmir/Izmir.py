import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import pandas as pd
import time
import random
import os


def random_sleep(min_seconds=5, max_seconds=10):
    """Pauses execution for a random amount of time to mimic human behavior."""
    time.sleep(random.uniform(min_seconds, max_seconds))


def scrape_all_izmir_districts():
    # Configure Chrome Options for Server Environment (GitHub Actions)
    options = uc.ChromeOptions()

    # CRITICAL: Enable headless mode for GitHub Actions since it has no display
    options.add_argument('--headless=new')
    # Additional arguments to prevent crashes in headless Linux environments
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')

    print("Starting the headless browser...")
    # Removed version_main so it dynamically uses the GitHub runner's Chrome version
    driver = uc.Chrome(options=options)

    all_extracted_data = []

    # List of main Izmir districts to bypass the 1000 item limit per search
    izmir_districts = [
        "izmir-aliaga", "izmir-balcova", "izmir-bayrakli", "izmir-bornova",
        "izmir-buca", "izmir-cigli", "izmir-gaziemir", "izmir-guzelbahce",
        "izmir-karabaglar", "izmir-karsiyaka", "izmir-kemalpasa", "izmir-konak",
        "izmir-menderes", "izmir-menemen", "izmir-narlidere", "izmir-seferihisar",
        "izmir-torbali", "izmir-urla"
    ]

    try:
        for district in izmir_districts:
            print(f"\n{'=' * 50}")
            print(f"STARTING NEW DISTRICT: {district.upper()}")
            print(f"{'=' * 50}")

            # Max 50 pages per district (1000 items limit per district)
            for page in range(1, 51):
                offset = (page - 1) * 20

                if page == 1:
                    url = f"https://www.sahibinden.com/kiralik-daire/{district}"
                else:
                    url = f"https://www.sahibinden.com/kiralik-daire/{district}?pagingOffset={offset}"

                driver.get(url)
                print(f"[{district}] Navigated to page {page}...")

                random_sleep(6, 11)

                try:
                    WebDriverWait(driver, 15).until(
                        EC.presence_of_element_located((By.CLASS_NAME, "searchResultsItem"))
                    )
                except TimeoutException:
                    print(f"\n[WARNING] Listings did not load on {district} Page {page}!")
                    break  # Usually means we hit a captcha or reached the end of this district's pages

                # Scroll down slightly to mimic real user behavior
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight/3);")
                random_sleep(1, 3)

                listings = driver.find_elements(By.CLASS_NAME, "searchResultsItem")

                if not listings:
                    print(f"No more listings found for {district}. Moving to next district.")
                    break

                valid_listings_count = 0
                for listing in listings:
                    try:
                        title_element = listing.find_element(By.CSS_SELECTOR, "a.classifiedTitle")
                        title = title_element.text.strip()

                        if not title:
                            continue

                        columns = listing.find_elements(By.CSS_SELECTOR, "td.searchResultsAttributeValue")
                        room_count = columns[1].text.strip() if len(columns) > 1 else "Not Specified"

                        price_element = listing.find_element(By.CSS_SELECTOR, "td.searchResultsPriceValue")
                        price = price_element.text.strip()

                        all_extracted_data.append({
                            "District": district.replace("izmir-", "").capitalize(),
                            "Title": title,
                            "Room Count": room_count,
                            "Price": price
                        })
                        valid_listings_count += 1

                    except Exception:
                        continue

                print(
                    f"[{district}] Page {page} extracted ({valid_listings_count} items). Total gathered: {len(all_extracted_data)}")

                # If a page has less than 20 items, it's the last page for this district
                if len(listings) < 20:
                    print(f"Reached the last page of {district}. Moving to next district.")
                    break

            # A longer cool-down period before switching to a completely new district
            print(f"Finished {district}. Cooling down for 30-45 seconds to avoid IP ban...")
            time.sleep(random.uniform(30, 45))

    except Exception as e:
        print(f"An unexpected error occurred: {e}")

    finally:
        print("\nClosing the browser...")
        try:
            driver.quit()
        except OSError:
            pass

    # --- Data Processing and File Routing ---
    if all_extracted_data:
        print(f"\nMASSIVE SCRAPE FINISHED! Total items extracted: {len(all_extracted_data)}")
        df = pd.DataFrame(all_extracted_data)

        # 1. Get the directory where this current script (Izmir.py) is located
        script_dir = os.path.dirname(os.path.abspath(__file__))

        # 2. Navigate up 3 levels to find the 'InflationResearchStudy' root folder
        project_root = os.path.abspath(os.path.join(script_dir, "../../.."))

        # 3. Construct the target directory path
        target_dir = os.path.join(project_root, "Datas", "HousesRent", "Izmir")

        # 4. Create the 'Izmir' folder under 'Datas/HousesRent/' if it doesn't exist yet
        os.makedirs(target_dir, exist_ok=True)

        # 5. Define the full file path and save
        file_path = os.path.join(target_dir, "izmir_rentals_full_dataset.csv")
        df.to_csv(file_path, index=False, encoding='utf-8-sig')

        print(f"Success! Massive dataset securely saved to: {file_path}")
    else:
        print("\nNo data was extracted.")


if __name__ == "__main__":
    scrape_all_izmir_districts()