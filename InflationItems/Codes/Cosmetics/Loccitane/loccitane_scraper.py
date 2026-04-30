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

BASE_URL = "https://www.loccitane.com.tr"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

CONCURRENT_CATEGORIES = 3 
DELAY_RANGE = (1.0, 2.5)

class CategoryScanner:
    def __init__(self, base_url):
        self.base_url = base_url

    async def get_categories(self, session):
        async with session.get(self.base_url) as response:
            html = await response.text()

        soup = BeautifulSoup(html, "html.parser")
        categories = []

        nav_items = soup.select('.navigation__desktop-item > a.navigation__desktop-link')

        for item in nav_items:
            name = item.get_text(strip=True)
            url = urljoin(self.base_url, item.get("href"))
            
            if url != self.base_url and name:
                categories.append({"name": name, "url": url})

        print(f"categories found: {len(categories)}")
        return categories

    async def expand_subcategories(self, session, categories):
        expanded_categories = []
        
        print("searching for subcategories...")
        for cat in categories:
            try:
                async with session.get(cat["url"], timeout=15) as response:
                    if response.status != 200:
                        expanded_categories.append(cat)
                        continue
                    html = await response.text()
                    
                soup = BeautifulSoup(html, "html.parser")
                
                sub_menu = soup.select("ul.m-0.p-0.pt-4.pt-md-0.position-relative > li > a")
                
                if sub_menu:
                    print(f"[{cat['name']}] found {len(sub_menu)} subcategories.")
                    for link in sub_menu:
                        sub_name = link.get_text(strip=True)
                        sub_url = urljoin(self.base_url, link.get("href"))
                        expanded_categories.append({
                            "name": f"{cat['name']} -> {sub_name}", 
                            "url": sub_url
                        })
                else:
                    expanded_categories.append(cat)
                    
                await asyncio.sleep(random.uniform(0.5, 1.0))
                
            except Exception as e:
                print(f"error {cat['name']}: {type(e).__name__}")
                expanded_categories.append(cat)

        print(f"total num of categories to parse: {len(expanded_categories)}")
        return expanded_categories

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
                        print(f"status {response.status} for {url}. attempt {attempt + 1}/{retries}")
            except Exception as e:
                if attempt == retries - 1:
                    print(f"error на {url}: {type(e).__name__} - {e}")
                    return None
            await asyncio.sleep(random.uniform(2.0, 4.0))
        return None

    async def collect_pages(self, session, category):
        async with self.semaphore:
            page = 1
            all_category_pages = []
            seen_skus = set()
            
            while True:
                url = f"{category['url']}?page={page}"
                html = await self.fetch_with_retry(session, url)
                
                if not html:
                    break 
                    
                soup = BeautifulSoup(html, "html.parser")
                items = soup.select(".product-item") 
                
                if not items:
                    break

                current_page_skus = set()
                for item in items:
                    sku = item.get("data-sku")
                    if sku:
                        current_page_skus.add(sku)
                
                if not current_page_skus or current_page_skus.issubset(seen_skus):
                    break
                    
                seen_skus.update(current_page_skus)

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
        items = soup.select(".product-item")

        for item in items:
            title = "N/A"
            numeric_price = 0.0
            sku = item.get("data-sku", "")
            
            json_div = item.select_one(".js-product-wrapper-analytics")
            if json_div:
                try:
                    data = json.loads(json_div.get_text(strip=True))
                    title = data.get("item_name", "N/A")
                    numeric_price = float(data.get("price", 0.0))
                    
                    extracted_items.append({
                        "sku": sku,
                        "title": title,
                        "price": numeric_price
                    })
                    continue  
                except json.JSONDecodeError:
                    pass
            
            title_el = item.select_one(".product-item__desc-name")
            if title_el:
                title = title_el.get_text(strip=True)
                
            cart_el = item.select_one(".product-item__add-to-card")
            raw_price = cart_el.get("data-basket-sale_price") if cart_el else ""
            
            if not raw_price:
                price_el = item.select_one(".product-item__sale-price")
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
        return os.path.join("InflationItems", "Datas", "Cosmetics", "LOccitane")

    @staticmethod
    def save(rows: list[dict]) -> str:
        if not rows:
            print("no data for saving.")
            return ""

        path = Storage.data_dir_for_market()
        os.makedirs(path, exist_ok=True)

        today = datetime.now().strftime("%Y-%m-%d")
        filename = f"LOccitane_{today}.csv"
        out_path = os.path.join(path, filename)

        with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
            fieldnames = ["title", "price"]
            w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
            
            w.writeheader()
            w.writerows(rows)

        print(f"saved {len(rows)} unique goods to {out_path}")
        return out_path

class Scraper:
    def __init__(self):
        self.scanner = CategoryScanner(BASE_URL)
        self.collector = LinkCollector()
        self.extractor = DataExtractor()

    async def run(self):
        async with aiohttp.ClientSession(headers=HEADERS) as session:
            main_categories = await self.scanner.get_categories(session)
            final_categories = await self.scanner.expand_subcategories(session, main_categories)
            
            tasks = [self.collector.collect_pages(session, cat) for cat in final_categories]
            results = await asyncio.gather(*tasks)

            all_data = []
            for pages in results:
                if pages:
                    for page in pages:
                        all_data.extend(self.extractor.extract(page))

            unique_items = {}
            for item in all_data:
                key = item.get("sku") or item.get("title")
                unique_items[key] = item

            Storage.save(list(unique_items.values()))

if __name__ == "__main__":
    asyncio.run(Scraper().run())