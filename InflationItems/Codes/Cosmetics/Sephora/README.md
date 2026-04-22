# Sephora Türkiye Product Scraper

A Python-based scraper that extracts product data from
[sephora.com.tr](https://www.sephora.com.tr) by parsing the category
XML sitemap and the `data-tcproduct` JSON blob embedded in every
product tile on a category page.

Sephora sits behind **Akamai Bot Manager**, which blocks naive HTTP
traffic via TLS / JA3 fingerprinting and server-side JS challenges.
The scraper therefore drives a real Chrome browser through
`undetected-chromedriver` — identical to how the `IstanbulAvrupa`
scraper bypasses Sahibinden's identical Akamai setup.

## Architecture Overview

The scraper is modular and mirrors the structure of the Koton / Migros
/ Bauhaus / IstanbulAvrupa scrapers in this repo:

- **`main.py`** – CLI interface and orchestration controller
- **`category_fetcher.py`** – XML sitemap-based category discovery (plain `requests`)
- **`browser_fetcher.py`** – Scraping backend: real Chrome via `undetected-chromedriver`
- **`config.py`** – Centralised configuration and constants

## Core Functionality

### Category Discovery

`category_fetcher.fetch_categories()` downloads
`sitemap-customsitemap_category_0.xml` with plain `requests` (the
sitemap is served to search crawlers and is **not** Akamai-protected),
parses its `<loc>` entries, and keeps URLs of the form
`/<slug>-c<numeric-id>/`.  By default it returns only the **eight
top-level categories** declared in `config.MAIN_CATEGORY_SLUGS`:

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

### Anti-bot Handling (Browser-Native)

A real Chrome browser is launched through `undetected-chromedriver`.
Akamai's JS challenge runs naturally inside Chrome, which posts
`sensor_data` back to Akamai and receives a valid `_abck` cookie.  If
the cookie is not obtained automatically (rare, e.g. on a flagged IP)
the scraper prompts you to solve the `Press & Hold` / reCAPTCHA
manually in the visible Chrome window, then resumes automatically.

- The Chrome user-data-dir persists in `SeleniumProfile/` so the
  `_abck` cookie survives between runs — at most one CAPTCHA solve
  per day.
- On macOS Apple Silicon the chromedriver binary is pre-patched and
  ad-hoc code-signed to avoid the `SIGKILL` that plain
  `undetected-chromedriver` triggers.
- Runs sequentially (one shared browser) because Chrome drivers do
  not parallelise well and Akamai penalises concurrent traffic.

## Project Structure

```
InflationItems/Codes/Cosmetics/Sephora/
├── scripts/
│   ├── main.py              # CLI entry-point & orchestrator
│   ├── category_fetcher.py  # Sitemap discovery (requests)
│   ├── browser_fetcher.py   # Chrome-based product extraction
│   └── config.py            # Constants, paths, browser tuning
├── SeleniumProfile/         # Chrome user-data-dir (auto-generated, git-ignored)
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
  ├─ 4. setup_driver()  →  fetch_products_for_category_browser(...)
  │       Launches Chrome with the persistent profile, warms it on
  │       the homepage, then visits each category URL sequentially,
  │       paginating with ?page=N and parsing every data-tcproduct
  │       blob into a normalised product record.
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
- Google Chrome installed locally
- Virtual environment (recommended)
- On macOS: `codesign` (bundled with Xcode CLI tools) for Apple
  Silicon chromedriver re-signing

```bash
cd InflationResearchStudy
python3 -m venv venv
source venv/bin/activate
pip install -r InflationItems/Codes/Cosmetics/Sephora/requirements.txt
```

### Dependencies

- `selenium >= 4.20.0` + `undetected-chromedriver >= 3.5.5` – browser
  automation
- `requests >= 2.28.0` – sitemap download (not Akamai-protected)
- `lxml >= 5.0.0` – fast HTML parser for tile extraction
- `pandas >= 1.5.0` – CSV I/O + dedup
- `tqdm >= 4.65.0` – progress bar

The bundled chromedriver binary at
`InflationItems/Codes/HousesRent/chromedriver` (Chrome 147, arm64) is
reused automatically.  If you're on Intel macOS / Linux / Windows the
scraper will ask `undetected-chromedriver` to download a matching
driver.

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
# Scrape all eight top-level categories
python main.py

# Slower per-page delay (raise if Chrome is struggling on your machine)
python main.py --delay 5
```

### Session Management

```bash
# Resume after an interruption – skip categories already completed today
python main.py --resume

# Verbose logging for debugging
python main.py --category cilt-bakimi-c303 -v

# Headless Chrome (not recommended – Akamai detects headless more easily)
python main.py --headless
```

### CLI Parameters

| Parameter             | Default | Description                                                  |
| --------------------- | ------- | ------------------------------------------------------------ |
| `--list-categories`   | –       | Print categories and exit                                    |
| `--all-categories`    | `False` | With `--list-categories`, include sub-categories             |
| `--category SLUG`     | All     | Scrape only this category slug                               |
| `--headless`          | `False` | Run Chrome in headless mode                                  |
| `--delay SECONDS`     | `3.5`   | Base per-page delay (jittered inside browser_fetcher)        |
| `--limit PAGES`       | `0`     | Max pages per category (`0` = unlimited)                     |
| `--resume`            | –       | Skip categories in today's checkpoint                        |
| `-v, --verbose`       | –       | Debug-level logging                                          |

### Output Files

| Path                                                                                | Description                  |
| ----------------------------------------------------------------------------------- | ---------------------------- |
| `InflationItems/Datas/Cosmetics/Sephora/sephora_<DATE>.csv`                         | Daily CSV (UTF-8 with BOM)   |
| `InflationItems/Codes/Cosmetics/Sephora/checkpoints/sephora_checkpoint_<DATE>.json` | Resume state                 |
| `Inflations/Datas/Cosmetics/Sephora/sephora_inflation_<DATE>.csv`                   | Per-product inflation rows   |
| `Inflations/Datas/Cosmetics/Sephora/inflation_summary.csv`                          | Daily store-level summary    |

## Configuration

All knobs live in `scripts/config.py`:

| Parameter                  | Default   | Function                                                     |
| -------------------------- | --------- | ------------------------------------------------------------ |
| `BROWSER_PAGE_LOAD_DELAY`  | `3.5`     | Base per-page sleep after `driver.get()`                     |
| `BROWSER_MAX_WAIT_TILES`   | `30`      | Seconds to wait for `data-tcproduct` before CAPTCHA prompt   |
| `BROWSER_HEADLESS`         | `False`   | Default headless flag (Akamai detects headless more easily)  |
| `BROWSER_VERSION_MAIN`     | `147`     | Chrome major version (must match local Chrome + chromedriver)|
| `CHROMEDRIVER_PATH`        | shared    | Reuses the binary from `HousesRent/chromedriver`             |
| `SELENIUM_PROFILE_DIR`     | `./SeleniumProfile` | Persists cookies / `_abck` between runs            |
| `MAIN_CATEGORY_SLUGS`      | 8 slugs   | Top-level category URLs that cover the full catalogue        |

### Path Configuration

All file paths are computed relative to `config.py`:

- `OUTPUT_DIR`     – target directory for CSV exports
- `CHECKPOINT_DIR` – daily checkpoint JSON files
- Daily file naming uses `YYYY-MM-DD`

## Troubleshooting

| Symptom                                           | Cause                                    | Resolution                                                                      |
| ------------------------------------------------- | ---------------------------------------- | ------------------------------------------------------------------------------- |
| `Akamai bot-challenge detected` prompt            | Akamai JS challenge needs solving        | Solve the Press-&-Hold / CAPTCHA in the Chrome window, press Enter              |
| Chrome crashes with `SIGKILL` on macOS            | Apple Silicon signature invalidated       | The scraper auto-re-signs via `codesign --force -s -` – reinstall Xcode CLI tools if missing |
| `session not created: chromedriver version…`      | Chromedriver and Chrome out of sync       | Update `config.BROWSER_VERSION_MAIN` to match your local Chrome                 |
| `Sitemap returned status 403`                     | Network blocking or IP reputation        | Retry after a few minutes; the sitemap usually responds to plain `requests`     |
| `data-tcproduct not found`                        | Sephora redesigned the tile markup       | Update the XPath in `browser_fetcher._extract_tiles`                            |
| `Category '<slug>' not found`                     | Sephora removed the category             | Remove the slug from `config.MAIN_CATEGORY_SLUGS`                               |
| `Cannot calculate inflation – no data for <date>` | Today's scrape didn't write a CSV        | Check the scraper finished and wrote the daily file                             |

---

**Technical Notice**: Use this tool for research only, and respect the
site's terms of service and rate limits.
