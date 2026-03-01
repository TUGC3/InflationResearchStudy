"""
Sahibinden House Rental Scraper
GitHub: InflationResearchStudy/Codes/HousesRent/Antep_Maras_Kilis/antep_maras_kilis.py
"""

import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import re
from datetime import datetime
from pathlib import Path
import random

# ========== CONFIGURATION ==========
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0',
]

def get_headers():
    """Get random headers for each request"""
    return {
        'User-Agent': random.choice(USER_AGENTS),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'tr-TR,tr;q=0.9,en;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
        'Cache-Control': 'max-age=0',
    }

# Base path
BASE_PATH = Path("Datas/HousesRent")

# Cities
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

REQUEST_DELAY = 5
MAX_PAGES = 3

def get_soup(url):
    """Get BeautifulSoup object with session handling"""
    try:
        session = requests.Session()
        
        # First visit homepage
        print(f"    Visiting homepage...")
        session.get('https://www.sahibinden.com', headers=get_headers(), timeout=30)
        time.sleep(2)
        
        # Then fetch the page
        print(f"    Fetching: {url}")
        headers = get_headers()
        response = session.get(url, headers=headers, timeout=30)
        print(f"    Status code: {response.status_code}")
        
        if response.status_code == 200:
            return BeautifulSoup(response.content, 'html.parser')
        else:
            print(f"    Error: HTTP {response.status_code}")
            return None
    except Exception as e:
        print(f"    Error: {e}")
        return None

def extract_price(price_text):
    if not price_text:
        return None
    price = re.sub(r'[^0-9]', '', price_text)
    return int(price) if price else None

def scrape_city(city_key, city_info):
    """Scrape rental listings for a specific city"""
    print(f"\n📁 Scraping {city_info['name']}...")
    
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
            print(f"  Failed to get page {page}")
            continue
        
        # Find listings
        listings = soup.find_all('tr', {'class': 'searchResultsItem'})
        print(f"    Found {len(listings)} listings")
        
        if not listings:
            print(f"  No listings found on page {page}")
            break
        
        for item in listings:
            try:
                # Title
                title_elem = item.find('a', {'class': 'classifiedTitle'})
                if not title_elem:
                    continue
                
                title = title_elem.text.strip()
                link = 'https://www.sahibinden.com' + title_elem.get('href', '')
                
                # Price
                price_elem = item.find('div', {'class': 'searchResultsPriceValue'})
                price_text = price_elem.text.strip() if price_elem else None
                price = extract_price(price_text)
                
                # District
                location_elem = item.find('td', {'class': 'searchResultsLocationValue'})
                district = location_elem.text.strip() if location_elem else None
                
                # Rooms
                room_elem = item.find('span', {'class': 'searchResultsAttributeValue'})
                rooms = None
                if room_elem:
                    room_match = re.search(r'(\d+)\+', room_elem.text.strip())
                    rooms = int(room_match.group(1)) if room_match else None
                
                today_date = datetime.now().strftime('%Y-%m-%d')
                
                listing = {
                    'city': city_info['name'],
                    'title': title,
                    'price_tl': price,
                    'district': district,
                    'rooms': rooms,
                    'url': link,
                    'scrape_date': today_date,
                }
                
                all_listings.append(listing)
                
            except Exception as e:
                print(f"    Error: {e}")
                continue
        
        time.sleep(REQUEST_DELAY)
    
    print(f"  ✅ Found {len(all_listings)} listings")
    return all_listings

def save_city_data(city_key, city_info, listings):
    """Save data with date in filename"""
    if not listings:
        return False
    
    df = pd.DataFrame(listings)
    city_info['folder'].mkdir(parents=True, exist_ok=True)
    
    today_date = datetime.now().strftime('%Y-%m-%d')
    filename = city_info['folder'] / f"{city_key}_{today_date}.csv"
    
    df.to_csv(filename, index=False, encoding='utf-8-sig')
    print(f"  💾 Saved: {filename}")
    return True

def main():
    print("="*60)
    print("SAHIBINDEN HOUSE RENTAL SCRAPER")
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    
    total = 0
    
    for city_key, city_info in CITIES.items():
        listings = scrape_city(city_key, city_info)
        if listings:
            save_city_data(city_key, city_info, listings)
            total += len(listings)
    
    print(f"\n{'='*60}")
    print(f"TOTAL: {total} listings today")
    print("="*60)

if __name__ == "__main__":
    main()
