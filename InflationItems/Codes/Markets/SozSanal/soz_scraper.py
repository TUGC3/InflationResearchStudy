import csv
import os
import re
import time
from collections import deque
from datetime import datetime
from typing import List, Set, Tuple

import requests
from bs4 import BeautifulSoup, Tag

BASE_URL = "https://www.afyonsoz.com"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

PATH_RE = re.compile(r"/hesabim\?path=(\d+)")
PRICE_RE = re.compile(r"(\d{1,3}(?:\.\d{3})*,\d{2})\s*TL", re.IGNORECASE)
TOTAL_PAGES_RE = re.compile(r"\((\d+)\s*Sayfa\)", re.IGNORECASE)

NON_PRODUCT_TITLES = {"alt kategoriler", "kategoriler"}


def repo_root() -> str:
    # Codes/Markets/SozSanal/soz_scraper.py -> repo root
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def fetch_soup(url: str) -> BeautifulSoup:
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return BeautifulSoup(r.text, "html.parser")



def category_url(path_id: int, page: int = 1) -> str:
    if page == 1:
        return f"{BASE_URL}/hesabim?path={path_id}"
    return f"{BASE_URL}/hesabim?page={page}&path={path_id}"


def extract_total_pages(soup: BeautifulSoup) -> int:
    text = " ".join(soup.stripped_strings)
    m = TOTAL_PAGES_RE.search(text)
    if m:
        try:
            return max(1, int(m.group(1)))
        except ValueError:
            return 1
    return 1


def discover_paths_from_soup(soup: BeautifulSoup) -> Set[int]:
    paths: Set[int] = set()
    for a in soup.find_all("a", href=True):
        m = PATH_RE.search(a["href"])
        if m:
            try:
                paths.add(int(m.group(1)))
            except ValueError:
                pass
    return paths


def discover_seed_paths_from_home() -> Set[int]:
    soup = fetch_soup(BASE_URL + "/")
    return discover_paths_from_soup(soup)


def normalize_price(price_str: str) -> str:
    return price_str.replace(".", "").strip()  # keep comma decimal


def parse_products_from_page(soup: BeautifulSoup) -> List[Tuple[str, str]]:
    results: List[Tuple[str, str]] = []
    seen_on_page: Set[Tuple[str, str]] = set()

    for h in soup.find_all(["h4", "h3"]):
        if not isinstance(h, Tag):
            continue

        name = h.get_text(strip=True)
        if not name or len(name) < 2:
            continue

        if name.strip().lower() in NON_PRODUCT_TITLES:
            continue

        container = h.find_parent()
        if not isinstance(container, Tag):
            continue

        container_text = " ".join(container.stripped_strings)
        pm = PRICE_RE.search(container_text)
        if not pm:
            continue

        price = normalize_price(pm.group(1))

        key = (name, price)
        if key in seen_on_page:
            continue
        seen_on_page.add(key)

        results.append((name, price))

    return results


def scrape_path(path_id: int, polite_delay_sec: float = 0.25) -> Tuple[List[Tuple[str, str]], Set[int]]:
    first = fetch_soup(category_url(path_id, 1))
    pages = extract_total_pages(first)

    discovered_paths = discover_paths_from_soup(first)
    products: List[Tuple[str, str]] = []
    products.extend(parse_products_from_page(first))

    for page in range(2, pages + 1):
        soup = fetch_soup(category_url(path_id, page))
        discovered_paths |= discover_paths_from_soup(soup)
        products.extend(parse_products_from_page(soup))
        time.sleep(polite_delay_sec)

    return products, discovered_paths


def count_zero_prices(csv_path: str) -> Tuple[int, int, float]:
    zero_like = {"0", "0,0", "0,00", "0.00"}
    total = 0
    zero = 0

    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        r = csv.DictReader(f)
        for row in r:
            total += 1
            price = (row.get("Price") or "").strip().strip('"')
            if price in zero_like:
                zero += 1

    ratio = (zero / total) if total else 0.0
    return total, zero, ratio


def main() -> None:
    seed_paths = discover_seed_paths_from_home()
    print(f"Seed paths from homepage: {len(seed_paths)}")

    q = deque(sorted(seed_paths))
    visited: Set[int] = set()

    global_seen: Set[Tuple[str, str]] = set()  # dedupe by (name, price)
    final_rows: List[Tuple[int, str, str]] = []
    next_id = 1

    while q:
        path_id = q.popleft()
        if path_id in visited:
            continue
        visited.add(path_id)

        print(f"Scraping path={path_id} ...")
        products, discovered = None, None
        for attempt in range(1, 4):  # up to 3 attempts
            try:
                products, discovered = scrape_path(path_id)
                break
            except Exception as e:
                if attempt < 3:
                    wait = attempt * 10
                    print(f"  !! Attempt {attempt} failed path={path_id}: {e} — retrying in {wait}s")
                    time.sleep(wait)
                else:
                    print(f"  !! Failed path={path_id} after 3 attempts: {e}")

        if products is None:
            continue

        print(f"  -> {len(products)} items found on this path")

        for p in discovered:
            if p not in visited:
                q.append(p)

        for name, price in products:
            key = (name, price)
            if key in global_seen:
                continue
            global_seen.add(key)

            final_rows.append((next_id, name, price))
            next_id += 1

    out_dir = os.path.join(repo_root(), "Datas", "Markets", "SozSanal")
    os.makedirs(out_dir, exist_ok=True)

    today = datetime.now().strftime("%Y-%m-%d")
    out_path = os.path.join(out_dir, f"soz_{today}.csv")

    with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["ID", "Product Name", "Price"])
        w.writerows(final_rows)

    print(f"\nDone. Visited paths: {len(visited)}")
    print(f"Done. Unique products written: {len(final_rows)} -> {out_path}")

    total, zero, ratio = count_zero_prices(out_path)
    print(f"Zero-price rows: {zero}")
    print(f"Zero-price ratio: {ratio:.6f} ({zero}/{total})")


if __name__ == "__main__":
    main()