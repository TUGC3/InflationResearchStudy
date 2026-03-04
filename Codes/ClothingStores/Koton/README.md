# Koton Türkiye Product Scraper

Scrapes product listing data from [koton.com](https://www.koton.com) and saves it as CSV.

## Folder structure

```
Koton/
├── scripts/
│   ├── config.py            # URLs, headers, delay, output paths
│   ├── category_fetcher.py  # Discovers all categories from the XML sitemap
│   ├── product_fetcher.py   # Fetches & parses products from listing pages
│   └── main.py              # CLI entry point
├── checkpoints/             # Auto-created; stores resume state per day
└── requirements.txt
```

## Setup

```bash
pip install -r requirements.txt
```

## Usage

Run all commands from inside the `scripts/` directory:

```bash
cd scripts/

# List all discovered categories (311 total)
python main.py --list-categories

# Scrape a single category — quick test (1 page)
python main.py --category kadin-giyim --limit 1

# Scrape a single category fully
python main.py --category kadin-giyim

# Scrape ALL categories with 2 parallel workers (default)
python main.py

# Use more workers (careful: too many triggers rate limiting)
python main.py --workers 3

# Resume an interrupted run
python main.py --resume

# Adjust inter-page delay (default: 1s, jittered ±50%)
python main.py --delay 1.5
```

## How it works

1. **Category discovery**: downloads Koton's gzip XML sitemap (`sitemap-categories-1.xml.gz`) and extracts all 311 unique category slugs.
2. **Parallel scraping**: categories are scraped concurrently using `ThreadPoolExecutor` (default: 2 workers). Each worker gets its own HTTP session. The inter-page delay is randomised (±50%) to avoid bot detection.
3. **Product parsing**: each product card contains two hidden JSON blobs:
   - `js-insider-product` → name, prices, stock, colour, size
   - `js-ga4-product-item` → brand, category hierarchy, style code (`base_code`)
4. **Incremental output**: CSV is written after every category so nothing is lost on interruption. A deduplication pass runs at the end.

## Output columns

| Column          | Description                                                   |
| --------------- | ------------------------------------------------------------- |
| `pk`            | Koton internal product-variant ID                             |
| `sku`           | EAN / barcode                                                 |
| `base_code`     | Style code (e.g. `6SAK60098EW`)                               |
| `name`          | Full product name                                             |
| `brand`         | Always `Koton`                                                |
| `category`      | Full taxonomy path (e.g. `WOMEN > WOVEN TOPS > SHIRTS LS`)    |
| `color`         | Colour variant                                                |
| `size`          | Size variant                                                  |
| `regular_price` | Original price (TRY)                                          |
| `sale_price`    | Discounted price (TRY); equals `regular_price` if no discount |
| `discount_pct`  | Discount percentage (0 if none)                               |
| `currency`      | Always `TRY`                                                  |
| `stock`         | Stock quantity for this variant                               |

## Output files

Files are stored in `Datas/ClothingStores/Koton/` and named by date:

- `koton_YYYY-MM-DD.csv`

Checkpoint files (for `--resume`) are stored in `Codes/ClothingStores/Koton/checkpoints/`.
