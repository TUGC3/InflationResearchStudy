import asyncio
import aiohttp
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from datetime import datetime
import csv
import os
import random
import re
import json

BASE_URL = "https://www.bellona.com.tr"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

CONCURRENT_CATEGORIES = 3 
DELAY_RANGE = (1.0, 2.5)

class CategoryScanner:
    def __init__(self, base_url):
        self.base_url = base_url

    async def get_categories(self, session):
        print("Fetching homepage for categories...")
        async with session.get(self.base_url) as response:
            html = await response.text()

        soup = BeautifulSoup(html, "html.parser")
        categories = {} 

        nav_items = soup.select('.category-level-1 a, .slick-track a')

        valid_paths = ["/kategori/", "/koleksiyon/", "/urunler/"]

        for item in nav_items:
            href = item.get("href", "")
            if href and any(path in href for path in valid_paths):
                title_el = item.select_one('span, .product-category-list-title')
                name = title_el.get_text(strip=True) if title_el else item.get_text(strip=True)
                
                url = urljoin(self.base_url, href)
                if url != self.base_url and name:
                    categories[url] = {"name": name, "url": url}

        final_categories = list(categories.values())
        print(f"Total unique categories to parse: {len(final_categories)}")
        return final_categories

class LinkCollector:
    def __init__(self):
        self.semaphore = asyncio.Semaphore(CONCURRENT_CATEGORIES)

    async def fetch_with_retry(self, session, url, retries=3):
        for attempt in range(retries):
            try:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=20)) as response:
                    if response.status == 200:
                        return await response.text()
                    else:
                        print(f"Status {response.status} for {url}. Attempt {attempt + 1}/{retries}")
            except Exception as e:
                if attempt == retries - 1:
                    print(f"Error on {url}: {type(e).__name__} - {e}")
                    return None
            await asyncio.sleep(random.uniform(2.0, 4.0))
        return None

    async def collect_pages(self, session, category):
        async with self.semaphore:
            page = 1
            all_category_pages = []
            seen_signatures = set() 
            
            while True:
                separator = "&" if "?" in category["url"] else "?"
                url = f"{category['url']}{separator}sayfa={page}&page={page}"
                
                html = await self.fetch_with_retry(session, url)
                if not html:
                    break 
                    
                soup = BeautifulSoup(html, "html.parser")
                items = soup.select(".showcase") 
                
                if not items:
                    break

                current_page_signatures = set()
                for item in items:
                    ga4_data_str = item.get("data-prd-ga4-config")
                    title = ""
                    if ga4_data_str:
                        try:
                            title = json.loads(ga4_data_str).get("name", "")
                        except: pass
                    
                    if not title:
                        title_el = item.select_one(".showcase-title a")
                        title = title_el.get_text(strip=True) if title_el else "N/A"
                        
                    sku = item.get("data-set-id") or item.get("data-id") or ""
                    current_page_signatures.add(f"{sku}_{title}")
                
                if not current_page_signatures or current_page_signatures.issubset(seen_signatures):
                    break
                    
                seen_signatures.update(current_page_signatures)

                all_category_pages.append({
                    "category": category["name"],
                    "url": url,
                    "html": html
                })
                
                print(f"[{category['name']}] page parsed {page}")
                page += 1
                await asyncio.sleep(random.uniform(*DELAY_RANGE))

            return all_category_pages

class DataExtractor:
    def clean_price(self, price_str: str) -> float:
        if not price_str:
            return 0.0
        
        cleaned = re.sub(r'[^\d.,]', '', price_str)
        
        if '.' in cleaned and ',' in cleaned:
            cleaned = cleaned.replace('.', '').replace(',', '.')
        elif ',' in cleaned:
            cleaned = cleaned.replace(',', '.')
            
        try:
            return float(cleaned)
        except ValueError:
            return 0.0

    def extract(self, page_data):
        soup = BeautifulSoup(page_data["html"], "html.parser")
        extracted_items = []
        items = soup.select(".showcase")

        for item in items:
            ga4_data_str = item.get("data-prd-ga4-config")
            if ga4_data_str:
                try:
                    ga4_data = json.loads(ga4_data_str)
                    sku = ga4_data.get("sku", "")
                    title = ga4_data.get("name", "")
                    price = round(float(ga4_data.get("price", 0.0)), 2)
                    
                    if sku and title:
                        extracted_items.append({
                            "sku": sku,
                            "title": title,
                            "price": price
                        })
                        continue 
                except (json.JSONDecodeError, ValueError, TypeError):
                    pass

            sku = item.get("data-set-id") or item.get("data-id", "")
            
            title_el = item.select_one(".showcase-title a")
            title = title_el.get_text(strip=True) if title_el else "N/A"
            
            price_el = item.select_one(".showcase-price-new")
            raw_price = price_el.get_text(strip=True) if price_el else ""
            numeric_price = self.clean_price(raw_price)
            
            extracted_items.append({
                "sku": sku,
                "title": title,
                "price": numeric_price  
            })
            
        return extracted_items

class Storage:
    @staticmethod
    def data_dir_for_market():
        return os.path.join("InflationItems", "Datas", "HomeGoods", "Bellona")

    @staticmethod
    def save(rows: list[dict]) -> str:
        if not rows:
            print("No data for saving.")
            return ""

        path = Storage.data_dir_for_market()
        os.makedirs(path, exist_ok=True)

        today = datetime.now().strftime("%Y-%m-%d")
        filename = f"Bellona_{today}.csv"
        out_path = os.path.join(path, filename)

        with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
            fieldnames = ["title", "price"] 
            w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
            
            w.writeheader()
            w.writerows(rows)

        print(f"Saved {len(rows)} unique items to {out_path}")
        return out_path

class Scraper:
    def __init__(self):
        self.scanner = CategoryScanner(BASE_URL)
        self.collector = LinkCollector()
        self.extractor = DataExtractor()

    async def run(self):
        async with aiohttp.ClientSession(headers=HEADERS) as session:
            categories = await self.scanner.get_categories(session)
            
            tasks = [self.collector.collect_pages(session, cat) for cat in categories]
            results = await asyncio.gather(*tasks)

            all_data = []
            for pages in results:
                if pages:
                    for page in pages:
                        all_data.extend(self.extractor.extract(page))

            unique_items = {}
            for item in all_data:
                key = f"{item.get('sku', '')}_{item.get('title', '')}_{item.get('price', 0)}"
                if item.get("title") and item.get("title") != "N/A":
                    unique_items[key] = item

            final_list = list(unique_items.values())
            Storage.save(final_list)

if __name__ == "__main__":
    asyncio.run(Scraper().run())