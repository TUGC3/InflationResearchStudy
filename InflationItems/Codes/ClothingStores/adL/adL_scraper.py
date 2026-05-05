import requests
import pandas as pd
from datetime import datetime
import time
import os
import random  # <-- ADDED for randomized waiting

# --- Configuration ---
categories = [
    "elbise-c-0005", "bluz-c-0008", "kazak-c-0012", "pantolon-c-0013",
    "dis-giyim-c-0037", "ceket-c-0017", "gomlek-c-0009", "yelek-c-0032",
    "etek-c-0014", "hirka-c-0018", "tulum-c-0006", "sweatshirt-c-0011",
    "tisort-c-0010", "atlet-c-0036", "sort-c-0015", "ayakkabi-c-0021",
    "canta-c-0020", "aksesuar-c-0022"
]

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json"
}


# --- Scraping Function ---
def scrape_adl_api(category_slug):
    category_data = []
    page = 0

    parts = category_slug.split('-c-')
    category_name = parts[0]
    category_id = parts[1]

    while True:
        api_url = f"https://api.adl.com.tr/occ/v2/adl/products/search?fields=FULL%2Cfacets%2Cbreadcrumbs%2Cpagination(DEFAULT)%2Csorts(DEFAULT)%2CfreeTextSearch%2CcurrentQuery&query=%3Arelevance%3AallCategories%3A{category_id}&pageSize=24&lang=tr&curr=TRY&currentPage={page}"

        print(f"  -> Fetching API: {category_name} (Page {page})")

        try:
            # Increased timeout just in case the server is slow
            response = requests.get(api_url, headers=headers, timeout=(5, 10))

            if response.status_code != 200:
                print(f"  -> Failed or reached the end. Status: {response.status_code}")
                break

            json_data = response.json()

        except requests.exceptions.Timeout:
            print(f"  -> Request timed out on page {page}. Moving to next category.")
            break
        except requests.exceptions.RequestException as e:
            print(f"  -> Network error occurred: {e}")
            break
        except ValueError:
            print(f"  -> Failed to parse JSON on page {page}.")
            break

        if "products" not in json_data or len(json_data["products"]) == 0:
            print(f"  -> No products found. Moving to next category.")
            break

        for product in json_data["products"]:
            try:
                name = product.get("name", "No Name")
                price_dict = product.get("price", {})
                current_price = price_dict.get("value", 0.0)

                category_data.append({
                    'Product Name': name,
                    'Price': current_price,
                    'Category': category_name
                })
            except Exception as e:
                print(f"  -> Error parsing product JSON: {e}")

        pagination = json_data.get("pagination", {})
        total_pages = pagination.get("totalPages", 1)

        if page >= total_pages - 1:
            print(f"  -> Reached the final page ({total_pages}).")
            break

        page += 1

        # --- INCREASED PAGE DELAY HERE ---
        # Waits a random amount of time between 2.5 and 5.0 seconds between pages
        sleep_time = random.uniform(2.5, 5.0)
        time.sleep(sleep_time)

    return category_data


# --- Main Execution ---
print("API Scraping started...")

script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(script_dir, '..', '..', '..'))
save_dir = os.path.join(project_root, 'Datas', 'ClothingStores', 'adL')
os.makedirs(save_dir, exist_ok=True)

today_date = datetime.now().strftime('%Y-%m-%d')
filename = os.path.join(save_dir, f'adL_{today_date}.csv')

if os.path.exists(filename):
    print(f"Found existing file for today ({filename}). Overwriting to start fresh...")
    os.remove(filename)

total_scraped = 0

for category in categories:
    print(f"\n--- Starting: {category} ---")

    data = scrape_adl_api(category)

    if data:
        df = pd.DataFrame(data)
        file_exists = os.path.isfile(filename)
        df.to_csv(filename, mode='a', index=False, header=not file_exists, encoding='utf-8-sig')
        total_scraped += len(data)
        print(f"  -> [PARTIAL SAVE] Saved {len(data)} items to CSV. (Total so far: {total_scraped})")
    else:
        print(f"  -> No data found for {category}, nothing to save.")

    # --- INCREASED CATEGORY DELAY HERE ---
    # Waits a random amount of time between 5.0 and 10.0 seconds between major categories
    cat_sleep_time = random.uniform(5.0, 10.0)
    print(f"  -> Resting for {cat_sleep_time:.1f} seconds before the next category...")
    time.sleep(cat_sleep_time)

print(f"\nSUCCESS! Scraping complete. A total of {total_scraped} products are safely saved in: {filename}")