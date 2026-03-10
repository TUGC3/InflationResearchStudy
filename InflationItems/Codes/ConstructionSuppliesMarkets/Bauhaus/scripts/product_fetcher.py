"""
product_fetcher.py — Paginates and scrapes products from Bauhaus categories.

This module is responsible for loading a Bauhaus category page, traversing
through its pagination iteratively, parsing the HTML to locate product
details (name, price, SKU), and returning a list of structured product
dictionaries.
"""

import time
import random
import logging
from bs4 import BeautifulSoup
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import config

logger = logging.getLogger(__name__)

def create_session():
    """
    Creates a requests session configured with retry adapters and headers.

    Returns:
        requests.Session: A session object with custom headers and exponential
                          backoff retry logic for resilience against 5xx and 429 errors.
    """
    session = requests.Session()
    session.headers.update(config.DEFAULT_HEADERS)
    retries = Retry(
        total=config.MAX_RETRIES,
        backoff_factor=config.RETRY_BACKOFF,
        status_forcelist=[429, 500, 502, 503, 504]
    )
    session.mount('http://', HTTPAdapter(max_retries=retries))
    session.mount('https://', HTTPAdapter(max_retries=retries))
    return session

def clean_price(price_str):
    """
    Parses a string price (e.g. "5.950,00 TL") into a float.

    Args:
        price_str (str): The raw string extracted from the HTML price element.

    Returns:
        float: The numeric value of the price, or 0.0 if parsing fails.
    """
    if not price_str:
        return 0.0
    # "5.950,00 TL" -> 5950.0
    # Remove " TL"
    price_str = price_str.replace("TL", "").strip()
    # Remove thousand separators
    price_str = price_str.replace(".", "")
    # Replace comma decimal with dot
    price_str = price_str.replace(",", ".")
    try:
        return float(price_str)
    except ValueError:
        return 0.0

def fetch_products_for_category(category_dict, session=None, limit_pages=0):
    """
    Iterates through the pages of a single category and extracts product data.

    Fetches the HTML of the category URL, appends the '?pg=X' pagination parameter,
    finds product item blocks via BeautifulSoup, extracts relevant properties,
    and returns a normalized list of item dictionaries.

    Args:
        category_dict (dict): A category definition loaded from category_fetcher.
                              Requires 'id', 'url', and 'name'.
        session (requests.Session, optional): The HTTP session to use for requests.
        limit_pages (int, optional): Maximum number of pages to scrape. Restricts
                                     the loop if > 0. Useful for testing.

    Returns:
        list[dict]: A list of scraped products matching standard output fields.
    """
    cat_id = category_dict["id"]
    cat_url = category_dict["url"]
    name = category_dict["name"]
    req_session = session or create_session()
    
    products = []
    page = 1
    last_page_skus = set()
    
    logger.info(f"[{name}] Starting scrape from {cat_url}")
    
    while True:
        if limit_pages > 0 and page > limit_pages:
            logger.info(f"[{name}] Reached limit of {limit_pages} pages.")
            break
            
        url = f"{cat_url}?pg={page}"
        logger.debug(f"[{name}] Fetching page {page}")
        
        try:
            resp = req_session.get(url, timeout=15)
            resp.raise_for_status()
        except Exception as e:
            logger.error(f"[{name}] Error fetching page {page}: {e}")
            break
            
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # Look for product cards
        items = soup.find_all('li', class_=lambda c: c and 'col-6' in c and 'col-sm-4' in c)
        
        if not items:
            logger.info(f"[{name}] No items found on page {page}. Ending pagination.")
            break
            
        current_page_skus = set()
        new_products_found = False
        
        for item in items:
            # Check price, some items without price might be hidden or placeholders
            price_span = item.find('span', class_='price')
            if not price_span:
                continue
                
            sku_span = item.find('span', class_='addToWishlist')
            sku = sku_span['data-sku'] if sku_span and sku_span.has_attr('data-sku') else None
            
            # If SKU is completely missing, we might need to look at href
            a_tag = item.find('a', href=True)
            if not sku and a_tag:
                sku = a_tag['href'].split('-')[-1]
            if not sku:
                continue
                
            current_page_skus.add(sku)
            
            # Extract data
            title_tag = item.find('h3', class_='prodName')
            title = title_tag.text.strip() if title_tag else ""
            
            brand_tag = item.find('span', class_='subInfo')
            brand = brand_tag.text.strip() if brand_tag else ""
            
            price_val = clean_price(price_span.text)
            
            # Determine images
            img_tag = item.find('img', class_='owl-lazy')
            if img_tag and img_tag.has_attr('data-src'):
                image_url = img_tag['data-src']
            elif img_tag and img_tag.has_attr('src'):
                image_url = img_tag['src']
            else:
                image_url = ""
            
            product_url = ""
            if a_tag:
                 href = a_tag['href']
                 product_url = config.BASE_URL + href if href.startswith('/') else href

            products.append({
                "id": sku,
                "sku": sku,
                "name": title,
                "brand": brand,
                "category": name,
                "regular_price": price_val,
                "shown_price": price_val,
                "discount_rate": 0, # usually hidden inside specific banners on Bauhaus, simplifying here
                "unit": "PIECE", # default assumption for Bauhaus
                "status": "IN_SALE"
            })
            new_products_found = True
            
        # Stop condition: if this page's SKUs are identical to last page
        if current_page_skus == last_page_skus or not new_products_found:
            logger.info(f"[{name}] Page {page} has same items as previous or empty. Ending.")
            break
            
        last_page_skus = current_page_skus
        page += 1
        
        # Jitter delay
        delay = config.REQUEST_DELAY * random.uniform(config.JITTER_MIN, config.JITTER_MAX)
        time.sleep(delay)
        
    logger.info(f"[{name}] Completed. Found {len(products)} products across {page-1} pages.")
    return products
