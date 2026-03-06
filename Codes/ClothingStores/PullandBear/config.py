STORE_ID = "25009521"
REGION_ID = "20309457"
LANGUAGE_ID = "-43"
APP_ID = "1"

BASE_URL = "https://www.pullandbear.com"
CATALOG_V2_URL = f"{BASE_URL}/itxrest/2/catalog/store/{STORE_ID}/{REGION_ID}"
CATALOG_V3_URL = f"{BASE_URL}/itxrest/3/catalog/store/{STORE_ID}/{REGION_ID}"

FULL_COOKIE = "ITXSESSIONID=aee09b64bd61f01f7149942cc40761f5; PBSESSION=fb7871b1c5b074f3c61bfe8967b90ad9; bm_sv=C18BB0AB6359AF95186E6B19C8209E4B~YAAQtbOvw8wxra6cAQAAoJYIxB864hwAh/UAT5OlF2r4Z8+KcMby3IsQjqcKPGcxf0aXY0BN6/5rVJeEhurngdNeTzJ+1k8bw4Mw/DJ4MYhZVULbmHz13EIS8JiTneZARg6gMMzWU7nwZhDfE326XP5D34p68qZNLdE8AXyytVTXGthw2BsHzAgOoAMGWmIG6CyRFqYgvYI/valmjhJqKT0cunUxcih+mlHDUKHovxdeMawM/sIqgvWS8rxYr1kGeqWvz72Nuw==~1; CookiesConsent=C0001; gbuuid=3e2547e4-e3f3-42f3-adab-cfb150e0a123; IDROSTA=eb244e2b5b8d:10f62bcaa5566dfcce12c1f73; TS01a139e1=01e7ba8b9780bac09b95414d040a6493cfbae33844413b8cc004e3f0b7508a616df5d93f6f63401b8cc6a057cbbc4ee4c774225da3"

HEADERS = {
    "Accept": "*/*",
    "Accept-Encoding": "gzip, deflate, br",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
    "Content-Type": "application/json",
    "Cookie": FULL_COOKIE,
    "Referer": "https://www.pullandbear.com/",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0.1 Safari/605.1.15",
}

OUTPUT_FILE = "../../Datas/ClothingStores/PullandBear/pullandbear_prices.csv"
BATCH_SIZE = 20
