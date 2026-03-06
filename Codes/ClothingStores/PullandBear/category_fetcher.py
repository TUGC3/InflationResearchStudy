import requests
import json
from config import CATALOG_URL, LANGUAGE_ID, APP_ID, HEADERS

def get_all_category_ids():
    """Fetch all leaf category IDs from Pull & Bear Turkey navigation."""
    url = f"{CATALOG_URL}/menu?languageId={LANGUAGE_ID}&appId={APP_ID}"
    
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"Error fetching menu: {e}")
        return []
    
    categories = []
    
    def extract_categories(items):
        if not items:
            return
        for item in items:
            cat_id = item.get("id") or item.get("categoryId")
            children = item.get("subcategories") or item.get("children") or []
            
            if children:
                extract_categories(children)
            elif cat_id:
                categories.append(str(cat_id))
    
    # Try common response structures
    menu = data.get("menus") or data.get("categories") or data.get("items") or []
    if isinstance(menu, list):
        extract_categories(menu)
    
    print(f"Found {len(categories)} categories")
    return list(set(categories))


def get_category_ids_from_sitemap():
    """Alternative: extract category IDs from known Pull & Bear TR categories via search."""
    # Fallback: use the category listing endpoint directly
    url = f"{CATALOG_URL}/category?languageId={LANGUAGE_ID}&appId={APP_ID}"
    
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        
        categories = []
        
        def walk(items):
            if not items:
                return
            for item in items:
                cid = item.get("id")
                if cid:
                    categories.append(str(cid))
                sub = item.get("subcategories") or item.get("subCategories") or []
                walk(sub)
        
        walk(data if isinstance(data, list) else [data])
        return list(set(categories))
        
    except Exception as e:
        print(f"Sitemap category fetch error: {e}")
        return []
