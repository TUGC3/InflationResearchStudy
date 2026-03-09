# Migros Türkiye Product Scraper

A Python tool to scrape all product data from [migros.com.tr](https://www.migros.com.tr) using their internal REST API.

## Features

- 🗂️ Discovers **all sub-categories** automatically via the API's own aggregation data (13 top-level categories × N subcategories)
- 📄 **Pagination** handled automatically — fetches every page per category
- 🔀 **Parallel scraping** with a configurable number of worker threads (`--workers`)
- 💾 Output as **CSV** and/or **JSON**, named with today's date
- ♻️ **Resume support** — restart an interrupted run without re-scraping completed categories
- ⏱️ Configurable **rate limiting** with per-request jitter to avoid triggering rate limits
- 🔄 Automatic **retry** with exponential back-off on failed or timeout requests
- 🧹 Final **deduplication** pass removes any cross-category duplicate products

## Project Structure

```
Codes/Markets/Migros/
├── scripts/
│   ├── main.py              # CLI entry point & orchestrator
│   ├── category_fetcher.py  # Discovers all scrapable (sub)categories via the REST API
│   ├── product_fetcher.py   # Paginates through products for a single category
│   └── config.py            # All settings, paths, and API constants
├── checkpoints/
│   └── migros_checkpoint_<DATE>.json   # Resume state (auto-generated)
├── requirements.txt
└── README.md

Datas/Markets/Migros/                   ← output lives here (outside Codes/)
├── migros_<DATE>.csv
└── migros_<DATE>.json
```

## Scraping Pipeline

```
main.py
  │
  ├─ 1. fetch_categories()          ← category_fetcher.py
  │       Probes 13 top-level category IDs against the REST API
  │       and extracts sub-category filters from aggregationGroups.
  │
  ├─ 2. (optional) filter by --category ID
  │
  ├─ 3. Load / initialise checkpoint
  │
  ├─ 4. ThreadPoolExecutor  (--workers N)
  │       └─ _scrape_category_worker()  →  fetch_products_for_category()
  │               Paginates, retries, and normalises product records.
  │               Results saved to disk after every completed category.
  │
  └─ 5. Final deduplication pass  →  CSV / JSON output files
```

## Output Fields

| Field           | Type   | Description                                                   |
| --------------- | ------ | ------------------------------------------------------------- |
| `id`            | string | Unique product ID                                             |
| `sku`           | string | SKU / barcode                                                 |
| `name`          | string | Product name (Turkish)                                        |
| `brand`         | string | Brand name                                                    |
| `category`      | string | Subcategory label                                             |
| `regular_price` | float  | Original shelf price in TL                                    |
| `shown_price`   | float  | Currently displayed price in TL (may differ during campaigns) |
| `discount_rate` | int    | Discount percentage (0 when no active promotion)              |
| `unit`          | string | Unit of measurement (e.g. `GRAM`, `PIECE`)                    |
| `status`        | string | Availability status (e.g. `IN_SALE`)                          |
| `image_url`     | string | Product listing image URL                                     |
| `product_url`   | string | Full URL to the product detail page                           |

> **Price note**: the Migros API returns prices in kuruş (1/100 of a TL).
> Both price fields are divided by 100 and rounded to 2 decimal places before saving.

## Setup

```bash
# 1. Go to the project root
cd InflationResearchStudy

# 2. Create a virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate   # macOS / Linux
# venv\Scripts\activate    # Windows

# 3. Install dependencies
pip install -r Codes/Markets/Migros/requirements.txt
```

## Usage

Run all commands from inside the `scripts/` directory (so that relative imports resolve correctly):

```bash
cd Codes/Markets/Migros/scripts

# List all discovered categories and their IDs
python main.py --list-categories

# Scrape a single category (ID "2" = Meyve, Sebze) — CSV only
python main.py --category 2 --output csv

# Scrape all categories, save both CSV and JSON
python main.py --output both

# Quick test — only 2 pages per category
python main.py --category 2 --limit 2 --output json

# Continue an interrupted full scrape
python main.py --output csv --resume

# Slow down requests (useful if getting 429 / 403 errors)
python main.py --delay 1.5 --output csv

# Increase parallelism (use with care — higher values risk rate limiting)
python main.py --workers 5 --output both

# Verbose debug logging
python main.py --category 2 -v
```

### CLI Reference

| Argument            | Default            | Description                                                                        |
| ------------------- | ------------------ | ---------------------------------------------------------------------------------- |
| `--list-categories` | —                  | Print all discovered categories with their IDs and exit.                           |
| `--category ID`     | _(all categories)_ | Scrape only the specified category ID.                                             |
| `--output`          | `both`             | Output format: `csv`, `json`, or `both`.                                           |
| `--workers N`       | `3`                | Number of parallel category worker threads.                                        |
| `--delay SECONDS`   | `0.5`              | Base delay between page requests per worker (actual delay includes random jitter). |
| `--limit PAGES`     | `0` (unlimited)    | Maximum pages to fetch per category. Useful for quick tests.                       |
| `--resume`          | —                  | Skip categories already recorded in the checkpoint file.                           |
| `-v` / `--verbose`  | —                  | Enable DEBUG-level logging.                                                        |

## Output Files

| File                                                             | Description                                            |
| ---------------------------------------------------------------- | ------------------------------------------------------ |
| `Datas/Markets/Migros/migros_<DATE>.csv`                         | All unique products (UTF-8 with BOM for Excel compat.) |
| `Datas/Markets/Migros/migros_<DATE>.json`                        | Same data as a pretty-printed JSON array               |
| `Codes/Markets/Migros/checkpoints/migros_checkpoint_<DATE>.json` | Tracks completed category IDs for `--resume` support   |

> Output paths are resolved automatically by `config.py` relative to the script's location, regardless of the working directory from which `main.py` is invoked.

## Configuration

Edit `scripts/config.py` to change scraper behaviour:

| Setting           | Default                             | Description                                                     |
| ----------------- | ----------------------------------- | --------------------------------------------------------------- |
| `REQUEST_DELAY`   | `0.5` s                             | Base delay between paginated requests (jitter applied on top)   |
| `MAX_RETRIES`     | `3`                                 | Retries before skipping a failed page                           |
| `RETRY_BACKOFF`   | `2` s                               | Back-off seed: actual wait = `RETRY_BACKOFF × attempt` seconds  |
| `DEFAULT_SORT`    | `onerilenler`                       | `sirala` query-parameter value sent to the API                  |
| `DEFAULT_WORKERS` | `3`                                 | Default number of parallel worker threads                       |
| `JITTER_MIN`      | `0.5`                               | Lower bound of the jitter multiplier applied to `REQUEST_DELAY` |
| `JITTER_MAX`      | `1.5`                               | Upper bound of the jitter multiplier applied to `REQUEST_DELAY` |
| `OUTPUT_DIR`      | `Datas/Markets/Migros/`             | Directory where CSV / JSON files are written                    |
| `CHECKPOINT_DIR`  | `Codes/Markets/Migros/checkpoints/` | Directory where checkpoint files are stored                     |

## Category Discovery

`category_fetcher.py` probes **13 top-level category IDs** against the `/rest/products/search` endpoint and extracts sub-category filter options from the `aggregationGroups[kategoriler].aggregationInfos` array. Sub-categories with `count == 0` are automatically skipped.

| ID  | Name                            |
| --- | ------------------------------- |
| 2   | Meyve, Sebze                    |
| 3   | Et, Tavuk, Balık                |
| 4   | Süt, Kahvaltılık                |
| 5   | Temel Gıda                      |
| 6   | İçecek                          |
| 7   | Deterjan, Temizlik              |
| 8   | Kişisel Bakım, Kozmetik, Sağlık |
| 9   | Bebek                           |
| 10  | Ev, Yaşam                       |
| 158 | Oyuncak                         |
| 160 | Evcil Hayvan                    |
| 165 | Kitap, Dergi, Gazete            |
| 166 | Elektronik                      |

If the API returns no sub-category filters for a top-level category, that category is scraped directly using only the `category-id` parameter (no `kategoriler` filter).

## Troubleshooting

| Symptom                        | Likely cause                             | Fix                                                                |
| ------------------------------ | ---------------------------------------- | ------------------------------------------------------------------ |
| HTTP 403 Forbidden             | Too many requests / missing headers      | Increase `--delay`; ensure `DEFAULT_HEADERS` are not overridden    |
| HTTP 429 Too Many Requests     | Rate limit triggered                     | Increase `--delay` and reduce `--workers`                          |
| Empty CSV after full run       | API changed product key names            | Check `storeProductInfos` / `products` key in `product_fetcher.py` |
| Resume doesn't skip categories | Checkpoint file from a different date    | Delete old checkpoint or use the correct `--resume` on same day    |
| `ModuleNotFoundError: config`  | Script not run from `scripts/` directory | `cd Codes/Markets/Migros/scripts` before running `main.py`         |

## Developer Notes

The scraper is split across four modules:

- **`config.py`** — single source of truth for all constants and file paths. No logic, only declarations.
- **`category_fetcher.py`** — stateless; takes an optional session and returns a flat list of category dicts.
- **`product_fetcher.py`** — stateless; takes a category dict and an optional session, returns a list of normalised product dicts.
- **`main.py`** — orchestrator only; handles CLI, threading, I/O, and checkpointing. Imports from the other three modules.

This separation makes each module independently testable and reusable.

---

> **Disclaimer**: This tool is for educational / research purposes. Always respect `robots.txt` and the site's Terms of Service. Do not overload the server.
