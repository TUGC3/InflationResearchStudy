"""
category_fetcher.py — Discovers and lists Bauhaus categories.

This module is responsible for parsing the main Bauhaus homepage to locate
all the subcategory URLs. By dynamically scanning the navigation and page
links with specific patterns, it identifies any scrapable category automatically.
"""

import requests
from bs4 import BeautifulSoup
import logging
import config

logger = logging.getLogger(__name__)

def fetch_categories(session=None):
    """
    Fetches the homepage and extracts all valid category URLs.
    
    This function parses the Bauhaus homepage HTML, looking for <a> tags
    whose href starts with 'bauhaus-' or '/bauhaus-'. These are identified
    as valid category or subcategory hubs.

    Args:
        session (requests.Session, optional): A pre-configured requests Session.
                                              If None, a new one is created.

    Returns:
        list[dict]: A list of category dictionaries, each containing:
            - 'id': The category slug (e.g., 'bauhaus-banyo-banyo-dolaplari')
            - 'url': The absolute URL to the category page
            - 'name': The human-readable name of the category
    """
    req_session = session or requests.Session()
    req_session.headers.update(config.DEFAULT_HEADERS)

    logger.info(f"Fetching categories from {config.BASE_URL}...")
    try:
        response = req_session.get(config.BASE_URL, timeout=10)
        response.raise_for_status()
    except Exception as e:
        logger.error(f"Failed to fetch homepage for categories: {e}")
        return []

    soup = BeautifulSoup(response.text, 'lxml')
    
    categories = {}
    
    # In Bauhaus, menus usually have links starting with 'bauhaus-'
    for a in soup.find_all('a', href=True):
        href = a['href']
        # Also ensure it's a full URL or relative
        if href.startswith('https://www.bauhaus.com.tr/bauhaus-'):
            slug = href.split('/')[-1]
            name = a.text.strip() or slug.replace('-', ' ').title()
            categories[slug] = {
                "id": slug,
                "url": href,
                "name": name
            }
        elif href.startswith('/bauhaus-'):
            slug = href.split('/')[-1]
            full_url = config.BASE_URL + href
            name = a.text.strip() or slug.replace('-', ' ').title()
            categories[slug] = {
                "id": slug,
                "url": full_url,
                "name": name
            }

    cat_list = list(categories.values())
    logger.info(f"Discovered {len(cat_list)} unique categories.")
    return cat_list

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    cats = fetch_categories()
    for c in cats[:5]:
        print(c)
