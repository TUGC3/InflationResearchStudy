
import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import re
from datetime import datetime
from pathlib import Path
import random

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'tr-TR,tr;q=0.9,en;q=0.8',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
}


BASE_PATH = Path("Datas/HousesRent")
CITIES = {
    'Antep': {
        'name': 'Gaziantep',
        'url': 'https://www.sahibinden.com/kiralik-daire/gaziantep',
        'folder': BASE_PATH / 'Antep'
    },
    'Maras': {
        'name': 'Kahramanmaras',
        'url': 'https://www.sahibinden.com/kiralik-daire/kahramanmaras',
        'folder': BASE_PATH / 'Maras'
    },
    'Kilis': {
        'name': 'Kilis',
        'url': 'https://www.sahibinden.com/kiralik-daire/kilis',
        'folder': BASE_PATH / 'Kilis'
    }
}

REQUEST_DELAY = 3  # seconds between requests
MAX_PAGES = 10  # Maximum pages to scrape per city

def get_soup(url):
    """Get BeautifulSoup object from URL"""
    try:
        response = requests.get(url, headers=HEADERS, timeout=30)
        response.raise_for_status()
        return BeautifulSoup(response.content, 'html.parser')
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return None

def extract_price(price_text):
    """Extract numeric price from text"""
    if not price_text:
        return None
    # Remove TL and non-numeric characters
    price = re.sub(r'[^0-9]', '', price_text)
    return int(price) if price else None

def extract_rooms(room_text):
    """Extract room count from text (e.g., '3+1' -> 3)"""
    if not room_text:
        return None
    match = re.search(r'(\d+)\+', room_text)
    if match:
        return int(match.group(1))
    return None

def scrape_city(city_key, city_info):
    """Scrape rental listings for a specific city"""
    print(f"\nScraping {city_info['name']}...")
    
    all_listings = []
    base_url = city_info['url']
    
    for page in range(1, MAX_PAGES + 1):
        if page == 1:
            url = base_url
        else:
            url = f"{base_url}?pagingOffset={(page-1)*20}"
        
        print(f"  Page {page}...")
        
        soup = get_soup(url)
        if not soup:
            break
        
        # Find listing items
        listings = soup.find_all('tr', {'class': 'searchResultsItem'})
        
        if not listings:
            print(f"  No more listings found")
            break
        
        for item in listings:
            try:
                # Title and link
                title_elem = item.find('a', {'class': 'classifiedTitle'})
                if not title_elem:
                    continue
                
                title = title_elem.text.strip()
                link = 'https://www.sahibinden.com' + title_elem.get('href', '')
                
                # Price
                price_elem = item.find('div', {'class': 'searchResultsPriceValue'})
                price_text = price_elem.text.strip() if price_elem else None
                price = extract_price(price_text)
                
                # Location/District
                location_elem = item.find('td', {'class': 'searchResultsLocationValue'})
                district = location_elem.text.strip() if location_elem else None
                
                # Room count
                room_elem = item.find('span', {'class': 'searchResultsAttributeValue'})
                rooms = extract_rooms(room_elem.text.strip() if room_elem else None)
                
                # Square meters
                size_elem = item.find_all('td', {'class': 'searchResultsAttributeValue'})
                size = None
                if len(size_elem) > 1:
                    size_text = size_elem[1].text.strip()
                    size_match = re.search(r'(\d+)', size_text)
                    size = int(size_match.group(1)) if size_match else None
                
                today_date = datetime.now().strftime('%Y-%m-%d')
                
                listing = {
                    'city': city_info['name'],
                    'title': title,
                    'price_tl': price,
                    'district': district,
                    'rooms': rooms,
                    'size_m2': size,
                    'url': link,
                    'scrape_date': today_date,
                    'scrape_time': datetime.now().strftime('%H:%M:%S')
                }
                
                all_listings.append(listing)
                
            except Exception as e:
                print(f"    Error parsing listing: {e}")
                continue
        
        # Random delay to be respectful
        time.sleep(REQUEST_DELAY + random.uniform(0, 2))
    
    print(f"  Found {len(all_listings)} listings for {city_info['name']}")
    return all_listings

def save_city_data(city_key, city_info, listings):
    """Save data for a specific city with date in filename"""
    if not listings:
        print(f"No listings to save for {city_info['name']}")
        return
    
    df = pd.DataFrame(listings)
    
    # Create folder if it doesn't exist
    city_info['folder'].mkdir(parents=True, exist_ok=True)
    
    # Create filename with date
    today_date = datetime.now().strftime('%Y-%m-%d')
    filename = city_info['folder'] / f"{city_key}_{today_date}.csv"
    
    # Save to CSV
    df.to_csv(filename, index=False, encoding='utf-8-sig')
    print(f"Saved: {filename} ({len(listings)} listings)")

def main():
    """Main function"""
    
    total_listings = 0
    
    for city_key, city_info in CITIES.items():
        listings = scrape_city(city_key, city_info)
        if listings:
            save_city_data(city_key, city_info, listings)
            total_listings += len(listings)
    
    print(f"\n{'='*50}")
    print(f"TOTAL: {total_listings} listings scraped today")
    print("="*50)

if __name__ == "__main__":
    main()
