import requests
import time
from config import CATALOG_URL, LANGUAGE_ID, APP_ID, HEADERS, BATCH_SIZE


def get_product_ids_for_category(category_id):
    """Step 1: Get all product IDs for a category."""
    url = (
        f"{CATALOG_URL}/category/{category_id}/product"
        f"?languageId={LANGUAGE_ID}&showProducts=false&priceFilter=true&appId={APP_ID}"
    )
    
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        product_ids = data.get("productIds", [])
        return [str(pid) for pid in product_ids]
    except Exception as e:
        print(f"  Error fetching product IDs for category {category_id}: {e}")
        return []


def get_products_detail(product_ids, category_id):
    """Step 2: Fetch product details in batches."""
    all_products = []
    
    for i in range(0, len(product_ids), BATCH_SIZE):
        batch = product_ids[i:i + BATCH_SIZE]
        ids_str = ",".join(batch)
        
        url = (
            f"{CATALOG_URL}/productsArray"
            f"?languageId={LANGUAGE_ID}&productIds={ids_str}&categoryId={category_id}&appId={APP_ID}"
        )
        
        try:
            resp = requests.get(url, headers=HEADERS, timeout=20)
            resp.raise_for_status()
            data = resp.json()
            products = data.get("products", [])
            all_products.extend(products)
            time.sleep(0.3)
        except Exception as e:
            print(f"  Error fetching products batch: {e}")
    
    return all_products


def extract_name_price(product):
    """Extract name and price from a product object."""
    name = product.get("name", "").strip()
    
    try:
        summaries = product.get("bundleProductSummaries", [])
        if not summaries:
            return None
        
        detail = summaries[0].get("detail", {})
        colors = detail.get("colors", [])
        
        if not colors:
            return None
        
        # Find first buyable size across all colors
        for color in colors:
            sizes = color.get("sizes", [])
            for size in sizes:
                if size.get("isBuyable", False):
                    price_cents = size.get("price")
                    if price_cents is not None:
                        price_try = int(price_cents) / 100
                        return {"name": name, "price": price_try}
        
        # If nothing buyable, just take first price available
        for color in colors:
            sizes = color.get("sizes", [])
            for size in sizes:
                price_cents = size.get("price")
                if price_cents is not None:
                    price_try = int(price_cents) / 100
                    return {"name": name, "price": price_try}
    
    except (IndexError, KeyError, TypeError, ValueError):
        pass
    
    return None
