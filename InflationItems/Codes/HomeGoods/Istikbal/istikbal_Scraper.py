import os
import time
import csv
import re
import math
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import NoSuchElementException


def setup_driver():
    """Sets up the Selenium Chrome driver."""
    chrome_options = Options()
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")

    driver = webdriver.Chrome(options=chrome_options)
    driver.maximize_window()
    return driver


def get_expected_product_count(driver):
    """Finds the 'Toplam X ürün' text and extracts the total number of products."""
    try:
        # Wait a moment for the dynamic count to render
        time.sleep(2)
        # Look for the span/div containing "Toplam" and "ürün"
        count_element = driver.find_element(By.XPATH, "//*[contains(text(), 'Toplam') and contains(text(), 'ürün')]")
        text = count_element.text

        # Extract the number (e.g., "Toplam 228 ürün" -> 228)
        match = re.search(r'(\d+)', text)
        if match:
            return int(match.group(1))
    except NoSuchElementException:
        pass
    return None


def scroll_page_slowly(driver):
    """Slowly scrolls down the current page to ensure lazy-loaded images/prices render."""
    last_height = driver.execute_script("return document.body.scrollHeight")
    scroll_step = 600

    current_position = 0
    while current_position < last_height:
        current_position += scroll_step
        driver.execute_script(f"window.scrollTo(0, {current_position});")
        time.sleep(0.5)
        # Update last height in case infinite scrolling adds to the DOM
        last_height = driver.execute_script("return document.body.scrollHeight")


def scrape_istikbal():
    categories = [
        {"name": "Oturma Odası", "url": "https://www.istikbal.com.tr/kategori/oturma-odasi"},
        {"name": "Yemek Odası", "url": "https://www.istikbal.com.tr/kategori/yemek-odasi-takimlari"},
        {"name": "Yatak Odası", "url": "https://www.istikbal.com.tr/kategori/yatak-odasi-takimlari"},
        {"name": "Yatak", "url": "https://www.istikbal.com.tr/kategori/yatak"},
        {"name": "Baza ve Başlık", "url": "https://www.istikbal.com.tr/kategori/yatak-baza"},
        {"name": "Genç ve Çocuk Odası", "url": "https://www.istikbal.com.tr/kategori/cocuk-genc-odasi-takimlari"},
        {"name": "Bahçe Mobilyası", "url": "https://www.istikbal.com.tr/kategori/bahce-mobilyalari"},
        {"name": "Tamamlayıcı Ürünler", "url": "https://www.istikbal.com.tr/kategori/tamamlayici-urunler"}
    ]

    items_per_page = 30
    all_products = []
    driver = setup_driver()

    try:
        for category in categories:
            print(f"\n--- Scraping category: {category['name']} ---")

            # Load the first page to get the total item count
            driver.get(category["url"])
            time.sleep(3)

            total_items = get_expected_product_count(driver)

            if total_items:
                total_pages = math.ceil(total_items / items_per_page)
                print(f"  -> Found {total_items} total items. Calculating {total_pages} page(s).")
            else:
                total_pages = 1
                print("  -> Could not determine total items. Defaulting to 1 page.")

            # Loop through the calculated number of pages
            for page_number in range(1, total_pages + 1):
                print(f"  -> Scraping Page {page_number}/{total_pages}...")

                # If we are past page 1, construct the URL with ?tp=X and navigate
                if page_number > 1:
                    page_url = f"{category['url']}?tp={page_number}"
                    driver.get(page_url)
                    time.sleep(3)  # Wait for page to fully load

                scroll_page_slowly(driver)
                time.sleep(1)

                # Extract data
                product_cards = driver.find_elements(By.CSS_SELECTOR, "div.showcase-content")
                items_on_page = 0

                for card in product_cards:
                    try:
                        name_elem = card.find_element(By.CSS_SELECTOR, ".showcase-title h3")
                        product_name = name_elem.text.strip()

                        product_price = ""
                        try:
                            price_elem = card.find_element(By.CSS_SELECTOR, ".showcase-price-new")
                            product_price = price_elem.text.strip()
                        except NoSuchElementException:
                            try:
                                price_elem = card.find_element(By.CSS_SELECTOR, ".showcase-price")
                                product_price = price_elem.text.strip()
                            except NoSuchElementException:
                                pass

                        if product_name and product_price:
                            all_products.append([product_name, product_price, category['name']])
                            items_on_page += 1

                    except Exception:
                        continue

                print(f"  -> Collected {items_on_page} items.")

    finally:
        driver.quit()

    return all_products


def save_to_csv(data):
    """Saves the scraped data to a CSV file in the specified directory structure."""
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../"))
    target_dir = os.path.join(base_dir, "InflationItems", "Datas", "HomeGoods", "Istikbal")

    os.makedirs(target_dir, exist_ok=True)

    date_str = datetime.now().strftime("%Y_%m_%d")
    filename = f"istikbal_{date_str}.csv"
    file_path = os.path.join(target_dir, filename)

    with open(file_path, mode='w', newline='', encoding='utf-8-sig') as file:
        writer = csv.writer(file)
        writer.writerow(['Product Name', 'Price', 'Category'])
        writer.writerows(data)

    print(f"\nData successfully saved to: {file_path}")
    print(f"Total records collected across all categories: {len(data)}")


if __name__ == "__main__":
    print("Starting Istikbal Scraper with URL-based pagination...")
    scraped_data = scrape_istikbal()
    if scraped_data:
        save_to_csv(scraped_data)
    else:
        print("No data was collected.")