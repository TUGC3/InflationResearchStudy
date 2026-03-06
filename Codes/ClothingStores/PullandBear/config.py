STORE_ID = "25009521"
REGION_ID = "20309457"
LANGUAGE_ID = "-43"
APP_ID = "1"

BASE_URL = "https://www.pullandbear.com"
CATALOG_URL = f"{BASE_URL}/itxrest/3/catalog/store/{STORE_ID}/{REGION_ID}"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Accept-Language": "tr-TR,tr;q=0.9",
    "Referer": "https://www.pullandbear.com/tr/",
}

OUTPUT_FILE = "pullandbear_prices.csv"
BATCH_SIZE = 20
