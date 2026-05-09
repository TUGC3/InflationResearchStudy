import requests
from bs4 import BeautifulSoup
import csv
import time
import os
from datetime import datetime

# --- Path & Timestamp Configuration  ---
# 1. Get the directory where this script is located
script_dir = os.path.dirname(os.path.abspath(__file__))

# 2. Navigate up 3 levels to the main 'InflationItems' project root
project_root = os.path.abspath(os.path.join(script_dir, '..', '..', '..'))

# 3. Define the correct save directory
save_dir = os.path.join(project_root, 'Datas', 'ConstructionSuppliesMarkets', 'TasciYapiMarket')

# 4. Create the directory if it doesn't exist
os.makedirs(save_dir, exist_ok=True)

# 5. Generate date and final filename
today_date = datetime.now().strftime('%Y-%m-%d')
csv_file_path = os.path.join(save_dir, f'tasciyapi_products_{today_date}.csv')

# --- Scraping Configuration ---
categories = [
    'alarm',
    'bahce-ve-balkon',
    'banyo',
    'beyaz-esya',
    'dekorasyon-ve-ev-gerecleri',
    'elektrik-ve-aydinlatma',
    'elektrikli-el-aletleri',
    'hirdavat-el-aletleri-ve-oto',
    'hobi-boyalari',
    'insaat-malzemeleri',
    'isitma-ve-sogutma',
    'kamp-kapcilik-malzemeleri',
    'kisisel-bakim-setleri',
    'mobilya',
    'mutfak',
    'temizlik',
    'tesisat-malzemesi'
]

# Upgraded headers to mimic a real browser closely
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
    'Accept-Language': 'tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1'
}

# --- Execution ---
print(f"Data will be saved to: {csv_file_path}")

# Initialize a Session to maintain connection pooling and cookies
session = requests.Session()
session.headers.update(headers)

with open(csv_file_path, 'w', newline='', encoding='utf-8') as file:
    writer = csv.writer(file)
    writer.writerow(['Product Name', 'Price', 'Category'])

    for category in categories:
        offset = 0
        print(f"\n--- Starting category: {category} ---")

        while True:
            if offset == 0:
                url = f"https://www.tasciyapi.com.tr/kategori/{category}"
            else:
                url = f"https://www.tasciyapi.com.tr/kategori/{category}/sayfa/{offset}"

            print(f"Scraping: {url}")

            # Robust error handling for the network request
            try:
                response = session.get(url, timeout=15)

                if response.status_code != 200:
                    print(f"Received status code {response.status_code}. Moving to next category.")
                    break

            except requests.exceptions.ConnectionError as e:
                print(f"Connection aborted by server (10054). Waiting 5 seconds before moving to next category...")
                time.sleep(5)
                break
            except requests.exceptions.Timeout:
                print(f"Request timed out. Moving to next category...")
                break
            except Exception as e:
                print(f"An unexpected error occurred: {e}. Moving to next category...")
                break

            # Parse the response
            soup = BeautifulSoup(response.content, 'html.parser')
            products = soup.find_all('div', class_='product-item-container')

            if not products:
                print(f"End of category {category} reached.")
                break

            for item in products:
                name_tag = item.find('h4')
                name = name_tag.text.strip() if name_tag else "Unknown Name"

                price_tag = item.find('span', class_='price-new')
                if not price_tag:
                    price_tag = item.find('div', class_='price')

                clean_price = 0.0
                if price_tag:
                    price_text = price_tag.text.replace('TL', '').strip()
                    if price_text:
                        try:
                            formatted_price = price_text.replace('.', '').replace(',', '.')
                            clean_price = float(formatted_price)
                        except ValueError:
                            pass

                if clean_price > 0:
                    writer.writerow([name, clean_price, category])

            offset += 15

            # Sleep to prevent rapid-fire requests from triggering bot protection
            time.sleep(2)

print(f"\nScraping complete! Data saved successfully to:\n{csv_file_path}")