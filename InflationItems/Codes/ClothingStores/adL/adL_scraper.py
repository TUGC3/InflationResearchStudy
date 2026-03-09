import requests
import pandas as pd
from datetime import datetime
import time
import os

# Your original list - no need to change it!
categories = [
    "elbise-c-0005", "bluz-c-0008", "kazak-c-0012", "pantolon-c-0013",
    "dis-giyim-c-0037", "ceket-c-0017", "gomlek-c-0009", "yelek-c-0032",
    "etek-c-0014", "hirka-c-0018", "tulum-c-0006", "sweatshirt-c-0011",
    "tisort-c-0010", "atlet-c-0036", "sort-c-0015", "ayakkabi-c-0021",
    "canta-c-0020", "aksesuar-c-0022"
]

# Tell the server we specifically want JSON data back
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json"
}


def scrape_adl_api(category_slug):
    category_data = []
    page = 0  # SAP APIs start pagination at 0

    # Split the string to get the name for the CSV and the ID for the API
    parts = category_slug.split('-c-')
    category_name = parts[0]
    category_id = parts[1]

    while True:
        # We inject your category ID and the current page into the URL you found
        api_url = f"https://api.adl.com.tr/occ/v2/adl/products/search?fields=FULL%2Cfacets%2Cbreadcrumbs%2Cpagination(DEFAULT)%2Csorts(DEFAULT)%2CfreeTextSearch%2CcurrentQuery&query=%3Arelevance%3AallCategories%3A{category_id}&pageSize=24&lang=tr&curr=TRY&currentPage={page}"

        print(f"  -> Fetching API: {category_name} (Page {page})")

        response = requests.get(api_url, headers=headers)

        if response.status_code != 200:
            print(f"  -> Failed or reached the end. Status: {response.status_code}")
            break

        # Instantly convert the response to a Python dictionary
        json_data = response.json()

        # If there is no "products" list, or it's empty, we are done with this category
        if "products" not in json_data or len(json_data["products"]) == 0:
            print(f"  -> No products found. Moving to next category.")
            break

        # Loop through the clean JSON data
        for product in json_data["products"]:
            try:
                name = product.get("name", "No Name")

                # SAP structures prices inside a nested dictionary
                price_dict = product.get("price", {})
                price_value = price_dict.get("value", 0.0)

                category_data.append({
                    'Category': category_name,
                    'Product Name': name,
                    'Price (TRY)': price_value
                })
            except Exception as e:
                print(f"Error parsing product JSON: {e}")

        # Let's check if we hit the total number of pages the API told us about
        pagination = json_data.get("pagination", {})
        total_pages = pagination.get("totalPages", 1)

        if page >= total_pages - 1:
            print(f"  -> Reached the final page ({total_pages}).")
            break

        page += 1
        time.sleep(1.5)  # Be polite to the API

    return category_data


# --- Main Execution ---
all_scraped_data = []

print("API Scraping started...")
for category in categories:
    print(f"\n--- Starting: {category} ---")
    data = scrape_adl_api(category)
    all_scraped_data.extend(data)
    time.sleep(2)

# Save to CSV
if all_scraped_data:
    df = pd.DataFrame(all_scraped_data)

    # --- PATH FIX START ---
    # 1. Get the exact folder where this Python script lives (.../Codes/ClothingStores/adL)
    script_dir = os.path.dirname(os.path.abspath(__file__))

    # 2. Go UP 3 folder levels to reach your main Project Root
    # (Up from adL -> ClothingStores -> Codes -> Root)
    project_root = os.path.abspath(os.path.join(script_dir, '..', '..', '..'))

    # 3. Build the exact path into your Datas folder
    save_dir = os.path.join(project_root, 'Datas', 'ClothingStores', 'adL')
    # --- PATH FIX END ---

    # Create the folder if it doesn't exist
    os.makedirs(save_dir, exist_ok=True)

    today_date = datetime.now().strftime('%Y-%m-%d')

    # Safely join the path and the filename together
    filename = os.path.join(save_dir, f'adL_{today_date}.csv')

    df.to_csv(filename, index=False, encoding='utf-8-sig')
    print(f"\nSUCCESS! Saved {len(df)} total products to: {filename}")
else:
    print("\nNo data was scraped.")