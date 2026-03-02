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

DATA_GROUP_FOLDER = "Antep_Maras_Kilis"
HEADLESS = os.environ.get("HEADLESS", "").strip().lower() in {"1", "true", "yes"}

SLEEP_MIN = 2.5
SLEEP_MAX = 4.5

BROWSER_MAJOR_VERSION = 145

# Persistent profile so manual verification/cookies stick
PROFILE_DIR_NAME = "SeleniumProfile_PERSISTENT"

PAGING_SIZE = 50
MAX_PAGES_PER_BRACKET = 120  # raise a bit; antep can be big

# Default brackets
PRICE_BRACKETS_DEFAULT: List[Tuple[int, int]] = [
    (0, 7999),
    (8000, 9999),
    (10000, 11999),
    (12000, 13999),
    (14000, 15999),
    (16000, 17999),
    (18000, 19999),
    (20000, 22999),
    (23000, 26999),
    (27000, 9999999),
]

# More granular brackets for antep (bigger market)
PRICE_BRACKETS_antep: List[Tuple[int, int]] = [
    (0, 9999),
    (10000, 12999),
    (13000, 14999),
    (15000, 16999),
    (17000, 18999),
    (19000, 20999),
    (21000, 22999),
    (23000, 24999),
    (25000, 27999),
    (28000, 31999),
    (32000, 37999),
    (38000, 44999),
    (45000, 54999),
    (55000, 9999999),
]

# =========================
# Paths
# =========================

def repo_root() -> str:
    """Get the repository root directory"""
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))

def data_dir_for_city(city: str) -> str:
    """Get data directory for a specific city"""
    # Map city names to folder names
    city_folder_map = {
        "maras": "Maras",
        "antep": "Antep",
        "kilis": "Kilis"
    }
    city_folder = city_folder_map.get(city, city.capitalize())
    return os.path.join(repo_root(), "Datas", "HousesRent", city_folder)

# =========================
# Brave path for GitHub Actions
# =========================

def find_brave_exe() -> str:
    """Find Brave executable path - works locally and in GitHub Actions"""
    env_brave = os.environ.get("BRAVE_PATH", "").strip()
    if env_brave and os.path.isfile(env_brave):
        return env_brave

    # Check if running in GitHub Actions (Chrome is available)
    if os.path.exists("/usr/bin/google-chrome"):
        return "/usr/bin/google-chrome"
    
    if os.path.exists("/usr/bin/chromium-browser"):
        return "/usr/bin/chromium-browser"

    # Windows paths for local development
    candidates = [
        r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
        r"C:\Program Files (x86)\BraveSoftware\Brave-Browser\Application\brave.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\BraveSoftware\Brave-Browser\Application\brave.exe"),
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",  # Fallback to Chrome
    ]
    
    for p in candidates:
        if p and os.path.isfile(p):
            return p

    # Default to Chrome in Linux (GitHub Actions)
    return "/usr/bin/google-chrome"

# =========================
# Driver setup for GitHub Actions
# =========================

def setup_driver() -> uc.Chrome:
    """Setup undetected Chrome driver"""
    browser_exe = find_brave_exe()

    options = uc.ChromeOptions()
    
    # Use temporary profile in GitHub Actions
    if os.getenv("GITHUB_ACTIONS"):
        profile_path = "/tmp/chrome-profile"
    else:
        profile_path = os.path.join(os.path.dirname(__file__), PROFILE_DIR_NAME)
    
    options.add_argument(f"--user-data-dir={profile_path}")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1400,900")
    options.add_argument("--lang=tr-TR")
    options.add_argument("--disable-blink-features=AutomationControlled")
    
    # Additional arguments for GitHub Actions
    if os.getenv("GITHUB_ACTIONS"):
        options.add_argument("--headless=new")
        options.add_argument("--disable-setuid-sandbox")
        options.add_argument("--remote-debugging-port=9222")
    elif HEADLESS:
        options.add_argument("--headless=new")

    return uc.Chrome(
        options=options,
        browser_executable_path=browser_exe,
        version_main=BROWSER_MAJOR_VERSION,
    )

def close_driver(driver: Optional[uc.Chrome]) -> None:
    """Safely close the driver"""
    if driver is None:
        return
    try:
        driver.quit()
    except Exception:
        pass

def polite_sleep() -> None:
    """Sleep with random duration"""
    time.sleep(random.uniform(SLEEP_MIN, SLEEP_MAX))

# =========================
# Block detection
# =========================

def is_block_page(html: str) -> bool:
    """Check if page is blocked by Cloudflare or similar"""
    soup = BeautifulSoup(html, "html.parser")

    # If listings table exists, not blocked
    if soup.select_one("#searchResultsTable"):
        return False

    lower = html.lower()
    signals = [
        "just a moment",
        "bir dakika lütfen",
        "lütfen bekleyiniz",
        "cf-challenge",
        "challenge-error-text",
        "access denied",
        "forbidden",
        "güvenlik doğrulama",
        "robot olmadığınızı",
        "captcha",
        "üye girişi",
        "giriş yap",
        "cloudflare",
    ]
    return any(s in lower for s in signals)

def ensure_access(driver: uc.Chrome, url: str) -> None:
    """Ensure we can access the page"""
    driver.get(url)
    polite_sleep()

    if is_block_page(driver.page_source):
        print("\n[BLOCK DETECTED]")
        if os.getenv("GITHUB_ACTIONS"):
            print("Block detected in GitHub Actions - cannot solve manually")
            print("Waiting 60 seconds and retrying...")
            time.sleep(60)
            driver.get(url)
            polite_sleep()
        else:
            print("Solve the verification in the opened browser window.")
            input("When the real listings page is visible, press ENTER here to continue...")
            driver.get(url)
            polite_sleep()

# =========================
# Parsing
# =========================

def extract_listings_from_html(html: str) -> List[dict]:
    """Extract listings from HTML"""
    soup = BeautifulSoup(html, "html.parser")
    
    # Try multiple selectors for robustness
    rows = soup.select("#searchResultsTable tbody tr")
    if not rows:
        rows = soup.select(".searchResultsItem")
    if not rows:
        rows = soup.select("tr[class*='search']")

    out: List[dict] = []
    for row in rows:
        price_elem = row.select_one(".searchResultsPriceValue")
        loc_elem = row.select_one(".searchResultsLocationValue")
        attr_elems = row.select(".searchResultsAttributeValue")

        price = price_elem.get_text(strip=True) if price_elem else ""
        district = " / ".join(loc_elem.stripped_strings) if loc_elem else ""
        rooms = attr_elems[1].get_text(strip=True) if len(attr_elems) > 1 else ""

        if price and district:
            out.append({"District": district, "Rooms": rooms, "Price": price})

    return out

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

# =========================
# CSV handling
# =========================

def append_to_daily_csv(city: str, rows: List[dict]) -> str:
    """Append listings to daily CSV file"""
    city_dir = data_dir_for_city(city)
    os.makedirs(city_dir, exist_ok=True)

    today = datetime.now().strftime("%Y-%m-%d")
    filename = f"{city.lower()}_{today}.csv"
    out_path = os.path.join(city_dir, filename)

    file_exists = os.path.isfile(out_path)
    with open(out_path, "a", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["District", "Rooms", "Price"])
        if not file_exists:
            w.writeheader()
        w.writerows(rows)

    return out_path

# =========================
# Bracket URL
# =========================

def build_bracket_url(base_url: str, min_p: int, max_p: int) -> str:
    """Build URL with price bracket"""
    return f"{base_url}?pagingSize={PAGING_SIZE}&price_min={min_p}&price_max={max_p}"

# =========================
# Scraper
# =========================

def scrape_city(driver: uc.Chrome, city: str, base_url: str) -> Tuple[uc.Chrome, str]:
    """Scrape all listings for a city"""
    print(f"\n=== Scraping: {city} ===")
    last_out_path = ""

    brackets = PRICE_BRACKETS_antep if city == "antep" else PRICE_BRACKETS_DEFAULT

    for (min_p, max_p) in brackets:
        print(f"\n--- Bracket {min_p} - {max_p} ---")
        url = build_bracket_url(base_url, min_p, max_p)

        page_idx = 0
        while True:
            page_idx += 1
            if page_idx > MAX_PAGES_PER_BRACKET:
                print("Bracket page limit reached. Consider splitting brackets smaller.")
                break

            try:
                ensure_access(driver, url)
                html = driver.page_source

                # If still blocked, pause/retry
                if is_block_page(html):
                    print("Still blocked on this bracket page.")
                    if os.getenv("GITHUB_ACTIONS"):
                        print("Waiting 30 seconds and retrying...")
                        time.sleep(30)
                        continue
                    else:
                        input("Solve it in browser, then press ENTER to retry this page...")
                        continue

                rows = extract_listings_from_html(html)
                print(f"Page {page_idx}: {len(rows)} listings")

                # Handle zero listings
                if len(rows) == 0:
                    print("Zero listings on page. URL:", driver.current_url)
                    # Check if it's the last page
                    next_url = find_next_url(html)
                    if not next_url:
                        print("No next page found - this might be the last page")
                        break
                    
                    if os.getenv("GITHUB_ACTIONS"):
                        print("Waiting 10 seconds and continuing to next page...")
                        time.sleep(10)
                        if next_url:
                            url = next_url
                            continue
                    else:
                        input("Check browser. If it's blocked/empty, fix it, then press ENTER to retry...")
                        continue

                last_out_path = append_to_daily_csv(city, rows)
                print(f"Appended {len(rows)} rows -> {last_out_path}")

                next_url = find_next_url(html)
                if not next_url:
                    break

                url = next_url
                polite_sleep()

            except WebDriverException as e:
                msg = str(e).lower()
                if "connection refused" in msg or "max retries exceeded" in msg or "disconnected" in msg:
                    print("\n[DRIVER DIED] Recreating driver and continuing...")
                    close_driver(driver)
                    time.sleep(2.0)
                    driver = setup_driver()
                    continue
                raise

    return driver, last_out_path

def main() -> None:
    """Main function"""
    driver: Optional[uc.Chrome] = None
    try:
        driver = setup_driver()
        for city, url in CITIES.items():
            driver, out_path = scrape_city(driver, city, url)
            if out_path:
                print(f"\nDone: {city} -> {out_path}")
            else:
                print(f"\nDone: {city} (no output file written)")
            time.sleep(2.0)
    except Exception as e:
        print(f"Error in main: {e}")
        raise
    finally:
        close_driver(driver)
        # Clean up profile in GitHub Actions
        if os.getenv("GITHUB_ACTIONS") and os.path.exists("/tmp/chrome-profile"):
            shutil.rmtree("/tmp/chrome-profile", ignore_errors=True)

if __name__ == "__main__":
    main()
