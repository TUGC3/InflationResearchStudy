# Sephora Türkiye Product Scraper

A Python-based scraper that extracts product data from
[sephora.com.tr](https://www.sephora.com.tr) by parsing the category
XML sitemap and the `data-tcproduct` JSON blob embedded in every
product tile on a category page.

## Architecture Overview

The scraper is modular and mirrors the structure of the Koton / Migros
/ Bauhaus scrapers in this repo:

- **`main.py`** – CLI interface and orchestration controller
- **`category_fetcher.py`** – XML sitemap-based category discovery
- **`product_fetcher.py`** – HTML parsing and product data extraction
- **`config.py`** – Centralised configuration and constants

## Core Functionality

### Category Discovery

`category_fetcher.fetch_categories()` downloads
`sitemap-customsitemap_category_0.xml`, parses its `<loc>` entries,
and keeps URLs of the form `/<slug>-c<numeric-id>/`. By default it
returns only the **eight top-level categories** declared in
`config.MAIN_CATEGORY_SLUGS`:

- `makyaj-c302` (Makeup)
- `parfum-c301` (Perfume)
- `parfum-parfum-setleri-c7601` (Perfume sets)
- `nis-parfum-c300501` (Niche perfume)
- `cilt-bakimi-c303` (Skincare)
- `cilt-bakimi-erkek-yuz-bakimi-anti-aging-c508` (Men's skincare / anti-aging)
- `vucut-ve-banyo-c304` (Body & bath)
- `sac-c307` (Hair)

Pass `level="all"` (or `--all-categories` on the CLI) to include every
sub-category URL found in the sitemap.

### Data Extraction

Sephora ships a rich JSON blob with every product tile under the
`data-tcproduct` attribute.  The scraper unescapes that blob, parses
it, and normalises the fields into a flat CSV schema.

- **HTML parsing**: `lxml` XPath selector `//*[@data-tcproduct]`
- **JSON decoding**: `html.unescape` + `json.loads`
- **Pagination**: `?page=N` (detected from the paginator controls on
  page 1; the loop exits as soon as a page returns zero tiles).

### Anti-bot Handling

Sephora sits behind **Akamai Bot Manager** which blocks naive
`requests` traffic via TLS / JA3 fingerprinting.  The scraper uses
`curl_cffi` with Safari 17 impersonation by default and rotates to
other Chrome / Safari profiles whenever a bot-challenge page is
returned.  It also:

- Warms every fresh session with a homepage GET before the first
  category request
- Sleeps `config.RATE_LIMIT_BACKOFF` (default 90 s) on HTTP 403/429
- Sleeps `config.EMPTY_RESPONSE_BACKOFF` (default 60 s) on 200
  responses whose body is the Akamai challenge HTML (no tiles)
- Applies jittered delays between pages (`REQUEST_DELAY × uniform(JITTER_MIN, JITTER_MAX)`)

## Project Structure

```
InflationItems/Codes/Cosmetics/Sephora/
├── scripts/
│   ├── main.py              # CLI entry-point & orchestrator
│   ├── category_fetcher.py  # Sitemap discovery
│   ├── product_fetcher.py   # Per-category pagination + parsing
│   └── config.py            # Constants, paths, anti-bot tuning
├── checkpoints/
│   └── sephora_checkpoint_<DATE>.json   # Resume state (auto-generated)
├── requirements.txt
└── README.md

InflationItems/Datas/Cosmetics/Sephora/            ← CSV output
└── sephora_<DATE>.csv

Inflations/Codes/Cosmetics/Sephora/
├── inflation.py             # Triggered by main.py at end of scrape
├── tuik_config.py           # TUIK 2026 weights + Sephora → TUIK mapping
└── README.md

Inflations/Datas/Cosmetics/Sephora/
├── sephora_inflation_<DATE>.csv  # Per-product detailed inflation rows
└── inflation_summary.csv         # Store-level summary, one row per date
```

## Scraping Pipeline

```
main.py
  │
  ├─ 1. fetch_categories()          ← category_fetcher.py
  │       Downloads Sephora's uncompressed sitemap and extracts the
  │       category URLs.  Filters to the eight top-level slugs.
  │
  ├─ 2. (optional) filter by --category slug
  │
  ├─ 3. Load / initialise today's checkpoint
  │
  ├─ 4. ThreadPoolExecutor  (--workers N)
  │       └─ _scrape_category()  →  fetch_products_for_category()
  │               Warms a curl_cffi session, paginates through the
  │               category, parses every `data-tcproduct` blob, and
  │               returns normalised records.
  │
  ├─ 5. Incremental CSV append + checkpoint save after each category
  │
  ├─ 6. Final deduplication pass (by product `id`)
  │
  └─ 7. inflation.calculate_inflation() → summary + detailed CSVs
```

## Data Schema

| Field           | Type   | Description                                                  |
| --------------- | ------ | ------------------------------------------------------------ |
| `id`            | string | Product identifier (uppercased `product_pid`)                |
| `sku`           | string | Internal SKU / barcode                                       |
| `name`          | string | Product display name                                         |
| `brand`         | string | Brand / trademark (lower-case as Sephora ships it)           |
| `category`      | string | Breadcrumb label from the tile (e.g. `makeup/dudak/lipstick`) |
| `category_id`   | string | Slug of the category page the tile was scraped under         |
| `regular_price` | float  | Non-discounted list price (TRY)                              |
| `sale_price`    | float  | Currently shown price (TRY)                                  |
| `discount_pct`  | float  | Computed percentage discount (0 when none)                   |
| `currency`      | string | Currency code (always `TRY`)                                 |
| `in_stock`      | bool   | `True` when the tile reports stock available                 |
| `url`           | string | Canonical product page URL                                   |

## Installation & Setup

### Prerequisites

- Python 3.8+
- Virtual environment (recommended)

```bash
cd InflationResearchStudy
python3 -m venv venv
source venv/bin/activate
pip install -r InflationItems/Codes/Cosmetics/Sephora/requirements.txt
```

### Dependencies

- `curl_cffi >= 0.7.0` – TLS-impersonating HTTP client (required to pass
  Akamai Bot Manager)
- `lxml >= 5.0.0` – fast HTML parser for tile extraction
- `pandas >= 1.5.0` – CSV I/O + dedup
- `tqdm >= 4.65.0` – progress bar

## Operation Guide

All commands are run from the scripts directory:

```bash
cd InflationItems/Codes/Cosmetics/Sephora/scripts
```

### Category Discovery

```bash
# Print the eight top-level categories
python main.py --list-categories

# Print every category URL in the sitemap (186 entries)
python main.py --list-categories --all-categories
```

### Targeted Scraping

```bash
# Scrape one category with a 1-page limit (quick smoke test)
python main.py --category cilt-bakimi-c303 --limit 1

# Full scrape of one category
python main.py --category cilt-bakimi-c303
```

### Full Catalogue Extraction

```bash
# Scrape all eight top-level categories sequentially
python main.py

# Slower per-page delay (raise if you see 403 / challenge pages)
python main.py --delay 4
```

### Session Management

```bash
# Resume after an interruption – skip categories already completed today
python main.py --resume

# Verbose logging for debugging
python main.py --category cilt-bakimi-c303 -v
```

### CLI Parameters

| Parameter             | Default | Description                                     |
| --------------------- | ------- | ----------------------------------------------- |
| `--list-categories`   | –       | Print categories and exit                       |
| `--all-categories`    | `False` | With `--list-categories`, include sub-categories |
| `--category SLUG`     | All     | Scrape only this category slug                  |
| `--workers N`         | `1`     | Parallel category workers (keep ≤ 2)            |
| `--delay SECONDS`     | `2.5`   | Base per-page delay (jittered)                  |
| `--limit PAGES`       | `0`     | Max pages per category (`0` = unlimited)        |
| `--resume`            | –       | Skip categories in today's checkpoint           |
| `-v, --verbose`       | –       | Debug-level logging                             |

### Output Files

| Path                                                                                | Description                  |
| ----------------------------------------------------------------------------------- | ---------------------------- |
| `InflationItems/Datas/Cosmetics/Sephora/sephora_<DATE>.csv`                         | Daily CSV (UTF-8 with BOM)   |
| `InflationItems/Codes/Cosmetics/Sephora/checkpoints/sephora_checkpoint_<DATE>.json` | Resume state                 |
| `Inflations/Datas/Cosmetics/Sephora/sephora_inflation_<DATE>.csv`                   | Per-product inflation rows   |
| `Inflations/Datas/Cosmetics/Sephora/inflation_summary.csv`                          | Daily store-level summary    |

## Configuration

All knobs live in `scripts/config.py`.  The defaults are tuned for
Akamai:

| Parameter                | Default | Function                                              |
| ------------------------ | ------- | ----------------------------------------------------- |
| `REQUEST_DELAY`          | `2.5`   | Base per-page delay (seconds)                         |
| `JITTER_MIN / JITTER_MAX`| `0.7 / 1.4` | Random multiplier range                           |
| `MAX_RETRIES`            | `5`     | Max retries per page                                  |
| `RETRY_BACKOFF`          | `4`     | Linear back-off seed for network errors              |
| `RATE_LIMIT_BACKOFF`     | `90`    | Sleep seconds on HTTP 403 / 429                       |
| `EMPTY_RESPONSE_BACKOFF` | `60`    | Sleep seconds on bot-challenge HTML                  |
| `DEFAULT_WORKERS`        | `1`     | Parallel category workers                             |
| `IMPERSONATE_PROFILES`   | Safari + Chrome | `curl_cffi` profile pool for rotation         |

### Path Configuration

All file paths are computed relative to `config.py`:

- `OUTPUT_DIR`     – target directory for CSV exports
- `CHECKPOINT_DIR` – daily checkpoint JSON files
- Daily file naming uses `YYYY-MM-DD`

## Troubleshooting

| Symptom                                         | Cause                              | Resolution                                                |
| ----------------------------------------------- | ---------------------------------- | --------------------------------------------------------- |
| `HTTP 403 / Access Denied`                      | Akamai flagged the IP              | Raise `--delay`, drop `--workers` to 1, let IP cool 10 min |
| Many `Bot-challenge / empty response` warnings  | TLS fingerprint blocked            | The scraper rotates automatically; raise delay if needed  |
| `data-tcproduct not found`                      | Sephora redesigned the tile markup | Update the XPath in `product_fetcher._extract_tiles`      |
| `Category '<slug>' not found`                   | Sephora removed the category       | Remove the slug from `config.MAIN_CATEGORY_SLUGS`         |
| `Cannot calculate inflation – no data for <date>` | Today's scrape didn't write a CSV  | Check the scraper finished and wrote the daily file       |

---

**Technical Notice**: Use this tool for research only, and respect the
site's terms of service and rate limits.
