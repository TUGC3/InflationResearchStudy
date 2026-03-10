# Koton Türkiye Product Scraper

A Python tool to scrape all product data from [koton.com](https://www.koton.com) and save it as CSV.

## Features

- 🗂️ Discovers **all categories (311+)** automatically via the XML sitemap.
- 📄 **Pagination** handled automatically — fetches every page per category.
- 🔀 **Parallel scraping** with a configurable number of worker threads (`--workers`).
- 💾 Output as **CSV**, named with today's date.
- ♻️ **Resume support** — restart an interrupted run without re-scraping completed categories.
- ⏱️ Configurable **rate limiting** with per-request jitter and User-Agent rotation to avoid triggering rate limits.
- 🔄 Automatic **retry** with exponential back-off on failed or timeout requests.
- 🧹 Final **deduplication** pass removes any cross-category duplicate products.

## Project Structure

```
InflationItems/Codes/ClothingStores/Koton/
├── scripts/
│   ├── main.py              # CLI entry point & orchestrator
│   ├── category_fetcher.py  # Discovers all categories from the XML sitemap
│   ├── product_fetcher.py   # Paginates through products for a single category
│   └── config.py            # All settings, paths, headers, and API constants
├── checkpoints/
│   └── koton_checkpoint_<DATE>.json   # Resume state (auto-generated)
├── requirements.txt
└── README.md

InflationItems/Datas/ClothingStores/Koton/          ← output lives here (outside Codes/)
├── koton_<DATE>.csv
└── InflationData/
    └── koton_inflation_<DATE>.csv

Inflations/Codes/ClothingStores/Koton/
└── inflation.py             # Inflation calculation script triggered by main.py

Inflations/Datas/ClothingStores/Koton/
└── inflation_summary.csv    # Summary of inflation trends
```

## Scraping Pipeline

```
main.py
  │
  ├─ 1. fetch_categories()          ← category_fetcher.py
  │       Downloads Koton's gzip XML sitemap (`sitemap-categories-1.xml.gz`)
  │       and extracts all unique category slugs.
  │
  ├─ 2. (optional) filter by --category slug
  │
  ├─ 3. Load / initialise checkpoint
  │
  ├─ 4. ThreadPoolExecutor  (--workers N)
  │       └─ _scrape_category()  →  fetch_products_for_category()
  │               Paginates, retries, and normalises product records.
  │               Results saved to disk after every completed category.
  │
  └─ 5. Final deduplication pass  →  CSV output file
```

## Output Fields

| Field           | Type   | Description                                                   |
| --------------- | ------ | ------------------------------------------------------------- |
| `pk`            | string | Koton internal product-variant ID                             |
| `sku`           | string | EAN / barcode                                                 |
| `base_code`     | string | Style code (e.g. `6SAK60098EW`)                               |
| `name`          | string | Full product name                                             |
| `brand`         | string | Brand name (Always `Koton`)                                   |
| `category`      | string | Full taxonomy path (e.g. `WOMEN > WOVEN TOPS > SHIRTS LS`)    |
| `color`         | string | Colour variant                                                |
| `size`          | string | Size variant                                                  |
| `regular_price` | float  | Original price (TRY)                                          |
| `sale_price`    | float  | Discounted price (TRY); equals `regular_price` if no discount |
| `discount_pct`  | float  | Discount percentage (0 if none)                               |
| `currency`      | string | Currency (Always `TRY`)                                       |
| `stock`         | int    | Stock quantity for this variant                               |

## Setup

```bash
# 1. Go to the project root
cd InflationResearchStudy

# 2. Create a virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate   # macOS / Linux
# venv\Scripts\activate    # Windows

# 3. Install dependencies
pip install -r InflationItems/Codes/ClothingStores/Koton/requirements.txt
```

## Usage

Run all commands from inside the `scripts/` directory (so that relative imports resolve correctly):

```bash
cd InflationItems/Codes/ClothingStores/Koton/scripts

# List all discovered categories (311 total)
python main.py --list-categories

# Scrape a single category — quick test (1 page)
python main.py --category kadin-giyim --limit 1

# Scrape a single category fully
python main.py --category kadin-giyim

# Scrape ALL categories with 2 parallel workers (default is 1)
python main.py --workers 2

# Resume an interrupted run
python main.py --resume

# Adjust inter-page delay (default: 2s, jittered ±50%)
python main.py --delay 1.5

# Verbose debug logging
python main.py --category kadin-giyim -v
```

### CLI Reference

| Argument            | Default            | Description                                                                        |
| ------------------- | ------------------ | ---------------------------------------------------------------------------------- |
| `--list-categories` | —                  | Print all discovered categories with their slugs and exit.                         |
| `--category SLUG`   | _(all categories)_ | Scrape only the specified category slug (e.g. 'kadin-giyim').                      |
| `--workers N`       | `1`                | Number of parallel category worker threads (increase carefully).                   |
| `--delay SECONDS`   | `2.0`              | Base delay between page requests per worker (actual delay includes random jitter). |
| `--limit PAGES`     | `0` (unlimited)    | Maximum pages to fetch per category. Useful for quick tests.                       |
| `--resume`          | —                  | Skip categories already recorded in the checkpoint file.                           |
| `-v` / `--verbose`  | —                  | Enable DEBUG-level logging.                                                        |

## Output Files

| File                                                                                 | Description                                            |
| ------------------------------------------------------------------------------------ | ------------------------------------------------------ |
| `InflationItems/Datas/ClothingStores/Koton/koton_<DATE>.csv`                         | All unique products (UTF-8 with BOM for Excel compat.) |
| `InflationItems/Codes/ClothingStores/Koton/checkpoints/koton_checkpoint_<DATE>.json` | Tracks completed category slugs for `--resume` support |

> Output paths are resolved automatically by `config.py` relative to the script's location, regardless of the working directory from which `main.py` is invoked.

## Configuration

Edit `scripts/config.py` to change scraper behaviour:

| Setting                | Default                                      | Description                                                     |
| ---------------------- | -------------------------------------------- | --------------------------------------------------------------- |
| `REQUEST_DELAY`        | `2` s                                        | Base delay between paginated requests (jitter applied on top)   |
| `MAX_RETRIES`          | `5`                                          | Retries before skipping a failed page                           |
| `RETRY_BACKOFF`        | `3` s                                        | Back-off seed: actual wait = `RETRY_BACKOFF × attempt` seconds  |
| `RATE_LIMIT_BACKOFF`   | `60` s                                       | Minimum explicit delay if a 429/403 response is received        |
| `USER_AGENTS`          | `[...]` list                                 | A pool of User-Agents to rotate, specifically per worker thread |
| `CATEGORY_SITEMAP_URL` | URL                                          | The Koton category sitemap XML gz URL                           |
| `OUTPUT_DIR`           | `InflationItems/Datas/ClothingStores/Koton/` | Directory where CSV files are written                           |
| `CHECKPOINT_DIR`       | `.../Koton/checkpoints/`                     | Directory where checkpoint files are stored                     |

## Troubleshooting

| Symptom                        | Likely cause                             | Fix                                                                             |
| ------------------------------ | ---------------------------------------- | ------------------------------------------------------------------------------- |
| HTTP 403 Forbidden             | Rate limited / bot blocked               | Increase `--delay` or rotate User-Agents; reduce `--workers`                    |
| HTTP 429 Too Many Requests     | Rate limit triggered                     | The scraper auto-backs-off using `RATE_LIMIT_BACKOFF`.                          |
| Empty CSV after full run       | Site structure changed                   | Check `js-insider-product` or `js-ga4-product-item` selectors                   |
| Resume doesn't skip categories | Checkpoint file from a different date    | Delete old checkpoint or use the correct `--resume` on same day                 |
| `ModuleNotFoundError: config`  | Script not run from `scripts/` directory | `cd InflationItems/Codes/ClothingStores/Koton/scripts` before running `main.py` |

## Developer Notes

The scraper is split across four modules:

- **`config.py`** — single source of truth for all constants and file paths. No logic, only declarations.
- **`category_fetcher.py`** — stateless; downloads the XML sitemap, decompresses it and parses valid slugs.
- **`product_fetcher.py`** — stateless; parses the Koton HTML listing pages, JSON blobs, and pages.
- **`main.py`** — orchestrator only; handles CLI, threading, I/O, and checkpointing. Imports from the other three modules.

This separation makes each module independently testable and reusable.

---

> **Disclaimer**: This tool is for educational / research purposes. Always respect `robots.txt` and the site's Terms of Service. Do not overload the server.
