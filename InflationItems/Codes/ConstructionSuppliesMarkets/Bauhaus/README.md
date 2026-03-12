# Bauhaus Türkiye Product Scraper

A Python tool to scrape all product data from [bauhaus.com.tr](https://www.bauhaus.com.tr) using HTML-based web scraping.

## Features

- 🗂️ Discovers **~600 subcategories** automatically via HTML navigation parsing
- 📄 **Pagination** handled seamlessly — fetches every page per category
- 🔀 **Parallel scraping** with a configurable number of worker threads (`--workers`)
- ⚡ **Performance optimized** with lxml parser, CSS selectors, and session reuse (35-55% faster)
- 💾 Output as **CSV**, named with today's date
- ♻️ **Resume support** — restart an interrupted run without re-scraping completed categories
- ⏱️ **Adaptive rate limiting** with per-request jitter to avoid triggering rate limits
- 🔄 Automatic **retry** with exponential back-off on failed or timeout requests
- 🧹 Final **deduplication** pass removes any cross-category duplicate products

## Project Structure

```
InflationItems/Codes/ConstructionSuppliesMarkets/Bauhaus/
├── scripts/
│   ├── main.py              # CLI entry point & orchestrator
│   ├── category_fetcher.py  # Discovers all scrapable categories via HTML navigation
│   ├── product_fetcher.py   # Paginates through products for a single category
│   └── config.py            # All settings, paths, and delay constants
├── checkpoints/
│   └── bauhaus_checkpoint_<DATE>.json   # Resume state (auto-generated)
├── requirements.txt
└── README.md

InflationItems/Datas/ConstructionSuppliesMarkets/Bauhaus/           ← output lives here
├── bauhaus_<DATE>.csv
└── InflationData/
    └── bauhaus_inflation_<DATE>.csv

Inflations/Codes/ConstructionSuppliesMarkets/Bauhaus/
└── inflation.py      # Inflation calculation script triggered by main.py

Inflations/Datas/ConstructionSuppliesMarkets/Bauhaus/
└── inflation_summary.csv # Summary of inflation trends
```

## Scraping Pipeline

```
main.py
  │
  ├─ 1. fetch_categories()          ← category_fetcher.py
  │       Parses homepage HTML to extract all category links
  │       starting with 'bauhaus-' pattern.
  │
  ├─ 2. (optional) filter by --category ID
  │
  ├─ 3. Load / initialise checkpoint
  │
  ├─ 4. ThreadPoolExecutor  (--workers N)
  │       └─ scrape_category_worker()  →  fetch_products_for_category()
  │               Paginates, retries, and normalises product records.
  │               Uses optimized lxml parser and CSS selectors.
  │               Results saved to disk after every 5 categories.
  │
  └─ 5. Final deduplication pass  →  CSV output file
```

## Output Fields

| Field           | Type   | Description                                      |
| --------------- | ------ | ------------------------------------------------ |
| `id`            | string | Unique product ID (SKU)                          |
| `sku`           | string | SKU / barcode                                    |
| `name`          | string | Product name (Turkish)                           |
| `brand`         | string | Brand name                                       |
| `category`      | string | Subcategory label                                |
| `regular_price` | float  | Original shelf price in TL                       |
| `shown_price`   | float  | Currently displayed price in TL                  |
| `discount_rate` | int    | Discount percentage (0 when no active promotion) |
| `unit`          | string | Unit of measurement (default: "PIECE")           |
| `status`        | string | Availability status (default: "IN_SALE")         |

## Performance Optimizations

This scraper includes 6 performance optimizations that achieve **35-55% speedup** without increasing request rate:

1. **lxml parser** - 3-5x faster HTML parsing vs default parser
2. **CSS selectors** - Faster DOM traversal vs lambda-based selectors
3. **Session reuse** - Reuses HTTP connections across categories
4. **Batched checkpoints** - Reduces I/O overhead (saves every 5 categories)
5. **String optimization** - Faster price cleaning with chained operations
6. **Adaptive rate limiting** - Intelligent delays prevent rate limiting while optimizing speed

## Setup

```bash
# 1. Go to the project root
cd InflationResearchStudy

# 2. Create a virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate   # macOS / Linux
# venv\Scripts\activate    # Windows

# 3. Install dependencies
pip install -r InflationItems/Codes/ConstructionSuppliesMarkets/Bauhaus/requirements.txt
```

## Usage

Run all commands from inside the `scripts/` directory (so that relative imports resolve correctly):

```bash
cd InflationItems/Codes/ConstructionSuppliesMarkets/Bauhaus/scripts

# List all discovered categories and their IDs
python main.py --list-categories

# Scrape a single category (ID "bauhaus-oto") - CSV only
python main.py --category bauhaus-oto

# Scrape all categories with default workers (2)
python main.py

# Increase parallelism (use with care — higher values risk rate limiting)
python main.py --workers 4

# Continue an interrupted full scrape
python main.py --resume

# Quick test — only 2 pages per category
python main.py --category bauhaus-oto --limit 2

# Verbose debug logging
python main.py --category bauhaus-oto -v
```

### CLI Reference

| Argument            | Default            | Description                                                                        |
| ------------------- | ------------------ | ---------------------------------------------------------------------------------- |
| `--list-categories` | —                  | Print all discovered categories with their IDs and exit.                           |
| `--category ID`     | _(all categories)_ | Scrape only the specified category ID.                                             |
| `--workers N`       | `2`                | Number of parallel category worker threads.                                        |
| `--delay SECONDS`   | `2.0`              | Base delay between page requests per worker (actual delay includes random jitter). |
| `--limit PAGES`     | `0` (unlimited)    | Maximum pages to fetch per category. Useful for quick tests.                       |
| `--resume`          | —                  | Skip categories already recorded in the checkpoint file.                           |
| `-v` / `--verbose`  | —                  | Enable DEBUG-level logging.                                                        |

## Output Files

| File                                                                                                  | Description                                            |
| ----------------------------------------------------------------------------------------------------- | ------------------------------------------------------ |
| `InflationItems/Datas/ConstructionSuppliesMarkets/Bauhaus/bauhaus_<DATE>.csv`                         | All unique products (UTF-8 with BOM for Excel compat.) |
| `InflationItems/Codes/ConstructionSuppliesMarkets/Bauhaus/checkpoints/bauhaus_checkpoint_<DATE>.json` | Tracks completed category IDs for `--resume` support   |

## Configuration

Edit `scripts/config.py` to change scraper behaviour:

| Setting           | Default                                                                 | Description                                                     |
| ----------------- | ----------------------------------------------------------------------- | --------------------------------------------------------------- |
| `REQUEST_DELAY`   | `2.0` s                                                                 | Base delay between paginated requests (jitter applied on top)   |
| `MAX_RETRIES`     | `5`                                                                     | Retries before skipping a failed page                           |
| `RETRY_BACKOFF`   | `3` s                                                                   | Back-off seed: actual wait = `RETRY_BACKOFF × attempt` seconds  |
| `DEFAULT_WORKERS` | `2`                                                                     | Default number of parallel worker threads                       |
| `JITTER_MIN`      | `1.0`                                                                   | Lower bound of the jitter multiplier applied to `REQUEST_DELAY` |
| `JITTER_MAX`      | `2.0`                                                                   | Upper bound of the jitter multiplier applied to `REQUEST_DELAY` |
| `OUTPUT_DIR`      | `InflationItems/Datas/ConstructionSuppliesMarkets/Bauhaus/`             | Directory where CSV files are written                           |
| `CHECKPOINT_DIR`  | `InflationItems/Codes/ConstructionSuppliesMarkets/Bauhaus/checkpoints/` | Directory where checkpoint files are stored                     |

## Category Discovery

`category_fetcher.py` parses the **homepage HTML** to extract all navigation links that start with `bauhaus-` pattern. This automatically discovers ~600 subcategories across all product departments without requiring manual configuration.

Categories are extracted from `<a>` tags where `href` starts with either:

- `https://www.bauhaus.com.tr/bauhaus-` (full URLs)
- `/bauhaus-` (relative URLs)

## Troubleshooting

| Symptom                        | Likely cause                             | Fix                                                                                            |
| ------------------------------ | ---------------------------------------- | ---------------------------------------------------------------------------------------------- |
| HTTP 429 Too Many Requests     | Rate limit triggered                     | Increase `--delay` and reduce `--workers` (adaptive rate limiting helps)                       |
| Empty CSV after full run       | HTML structure changed                   | Check CSS selectors in `product_fetcher.py` (`.col-6.col-sm-4`, etc.)                          |
| Resume doesn't skip categories | Checkpoint file from a different date    | Delete old checkpoint or use the correct `--resume` on same day                                |
| `ModuleNotFoundError: config`  | Script not run from `scripts/` directory | `cd InflationItems/Codes/ConstructionSuppliesMarkets/Bauhaus/scripts` before running `main.py` |
| Slow performance               | Using default HTML parser                | Ensure lxml is installed (included in requirements.txt)                                        |

## Developer Notes

The scraper is split across four modules:

- **`config.py`** — single source of truth for all constants and file paths. No logic, only declarations.
- **`category_fetcher.py`** — stateless; takes an optional session and returns a flat list of category dicts.
- **`product_fetcher.py`** — stateless; takes a category dict and an optional session, returns a list of normalised product dicts. Includes adaptive rate limiting.
- **`main.py`** — orchestrator only; handles CLI, threading, I/O, and checkpointing. Imports from the other three modules.

This separation makes each module independently testable and reusable.

---

> **Disclaimer**: This tool is for educational / research purposes. Always respect `robots.txt` and the site's Terms of Service. Do not overload the server.
