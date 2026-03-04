#!/usr/bin/env python3

import csv
import os
import random
import shutil
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import undetected_chromedriver as uc
from bs4 import BeautifulSoup
from selenium.common.exceptions import WebDriverException

# City configuration
CITIES: Dict[str, str] = {
    "maras": "https://www.sahibinden.com/kiralik/kahramanmaras",
    "antep": "https://www.sahibinden.com/kiralik/gaziantep",
    "kilis": "https://www.sahibinden.com/kiralik/kilis",
}

# Configuration
HEADLESS = os.environ.get("HEADLESS", "true").lower() == "true"
SLEEP_MIN = 2.5
SLEEP_MAX = 4.5
PAGING_SIZE = 50
MAX_PAGES_PER_BRACKET = 120

# Price brackets
PRICE_BRACKETS_DEFAULT: List[Tuple[int, int]] = [
    (0, 7999), (8000, 9999), (10000, 11999), (12000, 13999),
    (14000, 15999), (16000, 17999), (18000, 19999),
    (20000, 22999), (23000, 26999), (27000, 9999999),
]

PRICE_BRACKETS_ANTEP: List[Tuple[int, int]] = [
    (0, 9999), (10000, 12999), (13000, 14999), (15000, 16999),
    (17000, 18999), (19000, 20999), (21000, 22999), (23000, 24999),
    (25000, 27999), (28000, 31999), (32000, 37999), (38000, 44999),
    (45000, 54999), (55000, 9999999),
]

def is_github_actions() -> bool:
    """Check if running in GitHub Actions"""
    return os.getenv("GITHUB_ACTIONS") == "true"

def get_browser_path() -> str:
    """Get browser executable path"""
    # Check for Chrome in GitHub Actions
    if os.path.exists("/usr/bin/google-chrome"):
        return "/usr/bin/google-chrome"
    if os.path.exists("/usr/bin/chromium-browser"):
        return "/usr/bin/chromium-browser"
    return ""

def setup_driver() -> uc.Chrome:
    """Setup undetected Chrome driver"""
    options = uc.ChromeOptions()
    
    # Use temporary profile in GitHub Actions
    profile_path = "/tmp/chrome-profile" if is_github_actions() else "ChromeProfile"
    
    # Basic options
    options.add_argument(f"--user-data-dir={profile_path}")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1400,900")
    options.add_argument("--lang=tr-TR")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    # GitHub Actions specific options
    if is_github_actions():
        options.add_argument("--headless=new")
        options.add_argument("--disable-setuid-sandbox")
        options.add_argument("--remote-debugging-port=9222")
        options.add_argument("--single-process")
        options.add_argument("--disable-accelerated-2d-canvas")
    elif HEADLESS:
        options.add_argument("--headless=new")
    
    browser_path = get_browser_path()
    
    return uc.Chrome(
        options=options,
        browser_executable_path=browser_path if browser_path else None,
        version_main=120,
        headless=is_github_actions() or HEADLESS
    )

def close_driver(driver: Optional[uc.Chrome]) -> None:
    """Safely close the driver"""
    if driver:
        try:
            driver.quit()
        except Exception:
            pass

def polite_sleep() -> None:
    """Sleep with random duration"""
    time.sleep(random.uniform(SLEEP_MIN, SLEEP_MAX))

def get_data_dir(city: str) -> str:
    """Get data directory for a specific city"""
    city_folder_map = {
        "maras": "Maras",
        "antep": "Antep",
        "kilis": "Kilis"
    }
    city_folder = city_folder_map.get(city, city.capitalize())
    
    # Get the repository root (works in GitHub Actions)
    repo_root = os.getcwd()
    return os.path.join(repo_root, "Datas", "HousesRent", city_folder)

def is_block_page(html: str) -> bool:
    """Check if page is blocked by Cloudflare or similar"""
    soup = BeautifulSoup(html, "html.parser")
    
    if soup.select_one("#searchResultsTable"):
        return False
    
    lower = html.lower()
    signals = [
        "just a moment", "bir dakika lütfen", "lütfen bekleyiniz",
        "cf-challenge", "access denied", "forbidden", 
        "güvenlik doğrulama", "robot olmadığınızı", "captcha",
        "cloudflare", "403 forbidden"
    ]
    return any(s in lower for s in signals)

def ensure_access(driver: uc.Chrome, url: str, max_retries: int = 3) -> bool:
    """Ensure we can access the page with retries"""
    for attempt in range(max_retries):
        try:
            driver.get(url)
            polite_sleep()
            
            if not is_block_page(driver.page_source):
                return True
            
            print(f"Block detected (attempt {attempt + 1}/{max_retries})")
            if is_github_actions():
                wait_time = 30 * (attempt + 1)
                print(f"Waiting {wait_time} seconds before retry...")
                time.sleep(wait_time)
            else:
                input("Solve verification in browser, then press Enter...")
                
        except Exception as e:
            print(f"Error accessing URL: {e}")
            time.sleep(5)
    
    return False

def extract_listings_from_html(html: str) -> List[dict]:
    """Extract listings from HTML"""
    soup = BeautifulSoup(html, "html.parser")
    
    # Try multiple selectors for robustness
    rows = (soup.select("#searchResultsTable tbody tr") or 
            soup.select(".searchResultsItem") or 
            soup.select("tr[class*='search']"))
    
    listings = []
    for row in rows:
        try:
            price_elem = row.select_one(".searchResultsPriceValue")
            loc_elem = row.select_one(".searchResultsLocationValue")
            attr_elems = row.select(".searchResultsAttributeValue")
            
            price = price_elem.get_text(strip=True) if price_elem else ""
            district = " / ".join(loc_elem.stripped_strings) if loc_elem else ""
            rooms = attr_elems[1].get_text(strip=True) if len(attr_elems) > 1 else ""
            
            if price and district:
                listings.append({
                    "District": district,
                    "Rooms": rooms,
                    "Price": price,
                    "Scraped_Date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                })
        except Exception as e:
            print(f"Error parsing row: {e}")
            continue
    
    return listings

def find_next_url(html: str) -> Optional[str]:
    """Find next page URL"""
    soup = BeautifulSoup(html, "html.parser")
    next_a = soup.find("a", title="Sonraki")
    if next_a and next_a.get("href"):
        href = next_a["href"]
        if href.startswith("http"):
            return href
        return "https://www.sahibinden.com" + href
    return None

def save_to_csv(city: str, rows: List[dict]) -> str:
    """Save listings to daily CSV file"""
    city_dir = get_data_dir(city)
    os.makedirs(city_dir, exist_ok=True)
    
    today = datetime.now().strftime("%Y-%m-%d")
    filename = f"{city.lower()}_{today}.csv"
    out_path = os.path.join(city_dir, filename)
    
    file_exists = os.path.isfile(out_path)
    with open(out_path, "a", newline="", encoding="utf-8-sig") as f:
        fieldnames = ["District", "Rooms", "Price", "Scraped_Date"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerows(rows)
    
    return out_path

def build_bracket_url(base_url: str, min_p: int, max_p: int) -> str:
    """Build URL with price bracket"""
    return f"{base_url}?pagingSize={PAGING_SIZE}&price_min={min_p}&price_max={max_p}"

def scrape_city(driver: uc.Chrome, city: str, base_url: str) -> Tuple[uc.Chrome, str]:
    """Scrape all listings for a city"""
    print(f"\n{'='*50}")
    print(f"Scraping: {city.upper()}")
    print(f"{'='*50}")
    
    last_out_path = ""
    brackets = PRICE_BRACKETS_ANTEP if city == "antep" else PRICE_BRACKETS_DEFAULT
    
    for min_p, max_p in brackets:
        print(f"\n--- Price Bracket: {min_p} - {max_p} TL ---")
        url = build_bracket_url(base_url, min_p, max_p)
        
        page_num = 0
        while page_num < MAX_PAGES_PER_BRACKET:
            page_num += 1
            
            # Access page with retry
            if not ensure_access(driver, url):
                print(f"Failed to access page after retries, skipping bracket")
                break
            
            # Extract listings
            rows = extract_listings_from_html(driver.page_source)
            print(f"Page {page_num}: Found {len(rows)} listings")
            
            if rows:
                last_out_path = save_to_csv(city, rows)
                print(f"Saved {len(rows)} listings to {last_out_path}")
            
            # Check for next page
            next_url = find_next_url(driver.page_source)
            if not next_url:
                print("No more pages in this bracket")
                break
            
            url = next_url
            polite_sleep()
    
    return driver, last_out_path

def main():
    """Main function"""
    print("Starting Sahibinden.com scraper...")
    print(f"Running in GitHub Actions: {is_github_actions()}")
    
    driver = None
    try:
        driver = setup_driver()
        
        for city, url in CITIES.items():
            try:
                driver, out_path = scrape_city(driver, city, url)
                if out_path:
                    print(f"\n✓ Completed {city}: Data saved to {out_path}")
                else:
                    print(f"\n✓ Completed {city}: No data found")
                
                # Wait between cities
                time.sleep(3)
                
            except Exception as e:
                print(f"Error scraping {city}: {e}")
                # Try to recover driver
                close_driver(driver)
                time.sleep(5)
                driver = setup_driver()
                continue
        
        print("\n✓ All cities processed successfully!")
        
    except Exception as e:
        print(f"Fatal error: {e}")
        raise
    finally:
        close_driver(driver)
        # Clean up profile in GitHub Actions
        if is_github_actions() and os.path.exists("/tmp/chrome-profile"):
            shutil.rmtree("/tmp/chrome-profile", ignore_errors=True)

if __name__ == "__main__":
    main()
