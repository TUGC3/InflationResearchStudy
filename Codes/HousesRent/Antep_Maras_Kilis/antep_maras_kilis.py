#!/usr/bin/env python3
"""
Sahibinden.com rental scraper for Kahramanmaras, Gaziantep, and Kilis
Automated daily scraping with GitHub Actions
"""

import csv
import os
import random
import shutil
import time
import subprocess
import signal
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import sys

import undetected_chromedriver as uc
from bs4 import BeautifulSoup
from selenium.common.exceptions import WebDriverException, TimeoutException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By

# City configuration
CITIES: Dict[str, str] = {
    "maras": "https://www.sahibinden.com/kiralik/kahramanmaras",
    "antep": "https://www.sahibinden.com/kiralik/gaziantep",
    "kilis": "https://www.sahibinden.com/kiralik/kilis",
}

# Configuration
HEADLESS = os.environ.get("HEADLESS", "true").lower() == "true"
SLEEP_MIN = 1.0  # Reduced sleep times
SLEEP_MAX = 2.0
PAGING_SIZE = 50
MAX_PAGES_PER_BRACKET = 50  # Reduced from 120
MAX_BRACKETS_PER_CITY = 5  # Limit brackets to test first
TIMEOUT_SECONDS = 30  # Page load timeout

# Price brackets - use fewer for testing
PRICE_BRACKETS_DEFAULT: List[Tuple[int, int]] = [
    (0, 9999999),  # Just one bracket for testing
]

PRICE_BRACKETS_ANTEP: List[Tuple[int, int]] = [
    (0, 9999999),  # Just one bracket for testing
]

def is_github_actions() -> bool:
    """Check if running in GitHub Actions"""
    return os.getenv("GITHUB_ACTIONS") == "true"

def get_chrome_version() -> str:
    """Get installed Chrome version"""
    try:
        result = subprocess.run(['google-chrome', '--version'], 
                              capture_output=True, text=True, timeout=5)
        version = result.stdout.strip().split()[-1]
        print(f"Detected Chrome version: {version}")
        return version.split('.')[0]
    except Exception as e:
        print(f"Error detecting Chrome version: {e}")
        return "120"

def setup_driver() -> uc.Chrome:
    """Setup undetected Chrome driver"""
    chrome_version = get_chrome_version()
    print(f"Setting up driver for Chrome version: {chrome_version}")
    
    options = uc.ChromeOptions()
    
    # Use a more realistic profile
    profile_path = "/tmp/chrome-profile" if is_github_actions() else "ChromeProfile"
    
    # Add more stealth options
    options.add_argument(f"--user-data-dir={profile_path}")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1400,900")
    options.add_argument("--lang=tr-TR")
    options.add_argument("--disable-blink-features=AutomationControlled")
    
    # Remove headless for GitHub Actions? Sometimes headless is detected
    # Let's try without headless first
    options.add_argument("--headless=new")  # Keep headless for now
    
    # Add random user agent
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ]
    options.add_argument(f"--user-agent={random.choice(user_agents)}")
    
    # Additional stealth arguments
    options.add_argument("--disable-web-security")
    options.add_argument("--disable-features=IsolateOrigins,site-per-process")
    options.add_argument("--disable-site-isolation-trials")
    
    browser_path = "/usr/bin/google-chrome" if os.path.exists("/usr/bin/google-chrome") else None
    
    try:
        driver = uc.Chrome(
            options=options,
            browser_executable_path=browser_path,
            version_main=int(chrome_version) if chrome_version.isdigit() else None,
            headless=is_github_actions() or HEADLESS
        )
        
        # Execute stealth scripts
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        driver.execute_cdp_cmd('Network.setUserAgentOverride', {
            "userAgent": random.choice(user_agents)
        })
        
        driver.set_page_load_timeout(TIMEOUT_SECONDS)
        return driver
    except Exception as e:
        print(f"Error setting up driver: {e}")
        raise

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
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(script_dir, "../../../"))
    
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

def wait_for_element(driver: uc.Chrome, selector: str, timeout: int = 10) -> bool:
    """Wait for element to be present"""
    try:
        WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, selector))
        )
        return True
    except TimeoutException:
        return False

def ensure_access(driver: uc.Chrome, url: str, max_retries: int = 2) -> bool:
    """Ensure we can access the page with retries"""
    for attempt in range(max_retries):
        try:
            print(f"Accessing URL: {url[:100]}...")
            driver.get(url)
            
            # Wait for either results table or block indicator
            if wait_for_element(driver, "#searchResultsTable", timeout=10):
                print("Page loaded successfully")
                return True
            
            # Check if blocked
            if is_block_page(driver.page_source):
                print(f"Block detected (attempt {attempt + 1}/{max_retries})")
                if is_github_actions():
                    time.sleep(10)
                    continue
            else:
                # No block but also no results - might be empty page
                print("Page loaded but no results table found")
                return True
                
        except TimeoutException:
            print(f"Timeout loading page (attempt {attempt + 1}/{max_retries})")
        except Exception as e:
            print(f"Error accessing URL: {e}")
        
        time.sleep(5)
    
    return False

def extract_listings_from_html(html: str) -> List[dict]:
    """Extract listings from HTML"""
    soup = BeautifulSoup(html, "html.parser")
    
    # Try multiple selectors
    rows = soup.select("#searchResultsTable tbody tr")
    if not rows:
        rows = soup.select(".searchResultsItem")
    
    print(f"Found {len(rows)} listing rows")
    
    listings = []
    for i, row in enumerate(rows[:10]):  # Limit to first 10 for testing
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
            print(f"Error parsing row {i}: {e}")
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
    if not rows:
        return ""
        
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
    
    total_listings = 0
    start_time = time.time()
    
    for bracket_idx, (min_p, max_p) in enumerate(brackets[:MAX_BRACKETS_PER_CITY]):
        print(f"\n--- Bracket {bracket_idx + 1}/{len(brackets)}: {min_p} - {max_p} TL ---")
        url = build_bracket_url(base_url, min_p, max_p)
        
        page_num = 0
        while page_num < MAX_PAGES_PER_BRACKET:
            page_num += 1
            
            # Check time limit (20 minutes max per city)
            if time.time() - start_time > 1200:  # 20 minutes
                print("Time limit reached for this city")
                break
            
            print(f"\nPage {page_num}:")
            
            if not ensure_access(driver, url):
                print(f"Failed to access page, moving to next bracket")
                break
            
            rows = extract_listings_from_html(driver.page_source)
            print(f"Found {len(rows)} listings on this page")
            
            if rows:
                total_listings += len(rows)
                last_out_path = save_to_csv(city, rows)
                print(f"Saved {len(rows)} listings")
            
            # Check for next page
            next_url = find_next_url(driver.page_source)
            if not next_url:
                print("No next page found")
                break
            
            url = next_url
            polite_sleep()
        
        if time.time() - start_time > 1200:
            break
    
    print(f"\n✓ City {city} complete: {total_listings} total listings in {time.time()-start_time:.1f} seconds")
    return driver, last_out_path

def main():
    """Main function"""
    print("="*60)
    print("Starting Sahibinden.com scraper...")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Running in GitHub Actions: {is_github_actions()}")
    print("="*60)
    
    driver = None
    overall_start = time.time()
    
    try:
        driver = setup_driver()
        
        for city, url in CITIES.items():
            try:
                print(f"\n{'#'*60}")
                print(f"Processing city: {city}")
                print(f"{'#'*60}")
                
                driver, out_path = scrape_city(driver, city, url)
                
                if out_path:
                    print(f"✓ Data saved to: {out_path}")
                else:
                    print(f"✓ No data found for {city}")
                
                # Brief pause between cities
                time.sleep(2)
                
            except Exception as e:
                print(f"Error scraping {city}: {e}")
                # Try to recover
                close_driver(driver)
                time.sleep(5)
                driver = setup_driver()
                continue
        
        total_time = time.time() - overall_start
        print(f"\n{'='*60}")
        print(f"✓ All cities processed successfully!")
        print(f"Total execution time: {total_time:.1f} seconds")
        print(f"{'='*60}")
        
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        raise
    finally:
        close_driver(driver)
        if is_github_actions() and os.path.exists("/tmp/chrome-profile"):
            shutil.rmtree("/tmp/chrome-profile", ignore_errors=True)

if __name__ == "__main__":
    main()
