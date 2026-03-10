# Bauhaus Türkiye Product Scraper

A Python tool to scrape all product data from [bauhaus.com.tr](https://www.bauhaus.com.tr) using HTML-based web scraping.

## Overview

Unlike other sites, Bauhaus does not expose an internal JSON API for fetching categorised products. This scraper dynamically parses the Bauhaus website's Server-Side Rendered (SSR) HTML to discover categories, navigate pagination, and extract product details using `BeautifulSoup`.

It includes:
- **Automatic Category Discovery**: Extracts ~600 subcategories directly from the homepage.
- **Deep Pagination**: Scrapes every product card dynamically.
- **Multithreading**: Uses `ThreadPoolExecutor` for parallelized scraping logic.
- **Resilience**: Saves iterative checkpoints, includes request jitter, and uses exponential backoff to handle network errors safely.

## Project Structure

```text
InflationItems/Codes/ConstructionSuppliesMarkets/Bauhaus/
├── scripts/
│   ├── main.py              # CLI entry point & orchestrator
│   ├── category_fetcher.py  # Discovers all scrapable categories via HTML navigation links
│   ├── product_fetcher.py   # Paginates and scrapes product cards for a single category
│   └── config.py            # All settings, paths, and delay constants
├── checkpoints/
│   └── bauhaus_checkpoint_<DATE>.json  # Resume state (auto-generated)
├── requirements.txt
└── README.md
```

## Setup & Installation

All dependencies are standard requests and scraping libraries.

```bash
# From project root
pip install -r InflationItems/Codes/ConstructionSuppliesMarkets/Bauhaus/requirements.txt
```

## Usage

You must run all commands from inside the `scripts/` directory to ensure relative Python imports resolve correctly, OR set the `PYTHONPATH` accordingly.

```bash
cd InflationItems/Codes/ConstructionSuppliesMarkets/Bauhaus/scripts

# Run a complete scrape with the default number of workers (4):
python3 main.py

# Run a complete scrape with a custom number of workers (e.g., 8):
python3 main.py --workers 8

# List all discovered categories without scraping them:
python3 main.py --list-categories

# Scrape a specific subset (by ID slug) and limit to 2 pages (for testing):
python3 main.py --category bauhaus-banyo-banyo-dolaplari --limit 2

# Resume an interrupted scrape:
python3 main.py --resume

# Enable verbose logging:
python3 main.py -v
```

## Output Data

Data will be automatically dumped to the following location with today's date:

* `InflationItems/Datas/ConstructionSuppliesMarkets/Bauhaus/bauhaus_YYYY-MM-DD.csv`

## Inflation Calculation

At the end of a full scrape run in `main.py`, the orchestrator automatically loads our inflation script located at:

`Inflations/Codes/ConstructionSuppliesMarkets/Bauhaus/inflation.py`

This computes the trailing 1d, 7d, 15d, and 30d percentage price changes per product and saves the findings natively to `Inflations/Datas/ConstructionSuppliesMarkets/Bauhaus/`.
