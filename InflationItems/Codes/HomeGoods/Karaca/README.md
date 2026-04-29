# Karaca Scraper

Scrapes Karaca's catalog from `https://www.karaca.com/` by:

- discovering top-level catalog categories from the live mega menu
- extracting products from inline `window.catalog_products` payloads
- writing a dated CSV snapshot under `InflationItems/Datas/HomeGoods/Karaca/`
- checkpointing completed categories for safe resume support

## Usage

From this directory:

```bash
uv run python -m scripts.run_scraper --list-categories
uv run python -m scripts.run_scraper
uv run python -m scripts.run_scraper --category yemek-takimlari
uv run python -m scripts.run_scraper --resume
uv run python -m scripts.run_scraper --include-promotions
```

The CSV output always writes `Product Name` as column 1 and `Product Cost` as column 2.
