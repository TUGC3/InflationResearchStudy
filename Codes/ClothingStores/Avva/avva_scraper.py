import requests
from bs4 import BeautifulSoup
import csv
import os
from datetime import datetime
import time
import random

# --- Configuration ---
OUTPUT_DIR = "Datas/ClothingStores/Avva"
TARGET_URL = "https://www.avva.com.tr" # You'll need to find the exact category page URL(s)
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
}

# --- Helper Functions ---
def fetch_page(url, retries=3):
    """Fetch page with retry logic and delays."""
    for i in range(retries):
        try:
            time.sleep(random.uniform(1, 3)) # Be polite, delay between requests
            response = requests.get(url, headers=HEADERS, timeout=10)
            if response.status_code == 200:
                return response.text
            elif response.status_code == 403:
                print(f"Attempt {i+1}: Received 403 Forbidden. Retrying...")
                time.sleep(5) # Wait longer if blocked
            else:
                print(f"Attempt {i+1}: Status code {response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"Attempt {i+1}: Request failed - {e}")
            time.sleep(5)
    return None

def parse_product_listing(html_content):
    """Parse product listings (You'll need to adapt the selectors!)."""
    soup = BeautifulSoup(html_content, 'html.parser')
    products = []
    
    # !!! YOU MUST INSPECT THE WEBSITE TO FIND THE CORRECT SELECTORS !!!
    # Example selectors (these are guesses - replace with actual ones):
    product_cards = soup.find_all('div', class_='product-item') # Change this
    
    for card in product_cards:
        try:
            name = card.find('h3', class_='product-name').text.strip() # Change
            price_text = card.find('span', class_='product-price').text.strip() # Change
            # Clean price (remove currency, convert to float if needed)
            price = ''.join(filter(str.isdigit, price_text)) # Basic digit extraction
            
            # Get product URL for potential category info
            link_tag = card.find('a', href=True)
            category = "Unknown" # You might need to derive this from the URL or another element
            
            products.append({
                'name': name,
                'price': price,
                'category': category,
                'scrape_date': datetime.now().strftime('%Y-%m-%d')
            })
        except Exception as e:
            print(f"Error parsing a product card: {e}")
            continue
    return products

def save_to_csv(products, output_path):
    """Save product list to a CSV file."""
    if not products:
        print("No products to save.")
        return
    
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['name', 'price', 'category', 'scrape_date']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(products)
    print(f"Saved {len(products)} products to {output_path}")

# --- Main Execution ---
def main():
    # You might need to loop through multiple category/subcategory pages
    # For example: categories = ["/erkek", "/kadin", "/cocuk"]
    category_urls = [TARGET_URL] # Replace with actual category page URLs
    
    all_products = []
    for cat_url in category_urls:
        print(f"Fetching category: {cat_url}")
        html = fetch_page(cat_url)
        if html:
            products = parse_product_listing(html)
            # Optionally add category info based on the URL
            all_products.extend(products)
        else:
            print(f"Failed to fetch {cat_url}")
    
    # Generate filename with current date
    today_str = datetime.now().strftime('%Y-%m-%d')
    output_file = os.path.join(OUTPUT_DIR, f"products_{today_str}.csv")
    save_to_csv(all_products, output_file)

if __name__ == "__main__":
    main()
