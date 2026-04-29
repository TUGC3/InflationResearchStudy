# Vivense Türkiye Product Scraper

Daily product scraper for [Vivense](https://www.vivense.com) — a Turkish online
furniture and home-goods retailer. The scraper walks every top-level navigation
category, paginates through `?page=N` until an empty page is returned, parses the
embedded `data-*` attributes from each product card, and writes a daily CSV.

## Why HTML scraping (not an API)?

Unlike Migros (REST) or Rossmann (GraphQL), Vivense does **not** expose a public
product API. All product cards are server-rendered into category HTML with the
relevant metadata embedded as `data-*` attributes on a
`<div class="product-card product-content parent">` element, so a plain
`requests` + `BeautifulSoup` pipeline is sufficient — Selenium is **not**
required.

## Layout

```
InflationItems/Codes/HomeGoods/Vivense/
├── README.md
├── requirements.txt
├── checkpoints/                 # daily resume state
└── scripts/
    ├── config.py                # base URL, headers, paths, top-level categories
    ├── category_fetcher.py      # returns the curated category list
    ├── product_fetcher.py       # paginated HTML scraper (BeautifulSoup)
    └── main.py                  # CLI orchestrator + ThreadPoolExecutor
```

CSV output is written to `InflationItems/Datas/HomeGoods/Vivense/vivense_YYYY-MM-DD.csv`.

## Output Schema

| Column          | Type  | Notes                                                                                               |
| --------------- | ----- | --------------------------------------------------------------------------------------------------- |
| `id`            | str   | SKU (used as the unique key by the inflation calculator)                                            |
| `sku`           | str   | Same as `id`                                                                                        |
| `name`          | str   | Product display name                                                                                |
| `brand`         | str   | Brand / collection (e.g. `Vivense Collection`). May be empty for some third-party-sourced products. |
| `category`      | str   | Top-level category being scraped (e.g. `Oturma Odası`)                                              |
| `sub_category`  | str   | Most-specific sub-category (e.g. `Köşe Koltuk`)                                                     |
| `regular_price` | float | List price in TRY (= `shown_price` when no discount is active)                                      |
| `shown_price`   | float | Currently displayed (post-discount) price in TRY                                                    |
| `discount_rate` | int   | Discount percent (`0` when none)                                                                    |
| `unit`          | str   | Always `PIECE`                                                                                      |
| `status`        | str   | Always `IN_SALE`                                                                                    |
| `image_url`     | str   | Main product image                                                                                  |
| `product_url`   | str   | Canonical product page                                                                              |

## Pricing & Discount Extraction

Vivense embeds **two** prices per product card:

| Source                                        | Meaning                        | When present                   |
| --------------------------------------------- | ------------------------------ | ------------------------------ |
| `data-product-price` _(or `span.last-price`)_ | Final price the customer pays  | Always                         |
| `span.psf-price`                              | Original / list price          | Only when a discount is active |
| `data-discount-rate`                          | Discount percentage (`""` → 0) | Always                         |

The mapping the scraper uses:

- `shown_price` ← `data-product-price` (fallback: `last-price` text)
- `regular_price` ← `psf-price` (fallback: `shown_price` when not discounted)
- `discount_rate` ← `data-discount-rate` (parsed as int, `""` → 0)

When a product has no discount, `regular_price == shown_price` and
`discount_rate == 0`. When a product is discounted, the inflation calculator
treats `shown_price` as the authoritative current price (matching the
convention used for Migros, Rossmann and Bauhaus).

## Pagination & End-of-Catalogue Detection

Vivense uses 1-indexed `?page=N` pagination, returning ~60 products per page.
The scraper terminates a category on the **first** of these conditions:

1. The page contains zero `product-card.product-content.parent` elements.
2. The set of SKUs on the current page is identical to the previous page
   (defensive guard against the site silently clamping `page` to the last
   valid value).
3. Every card on the page is already in the running SKU set (no new
   products contributed → end of catalogue reached).
4. The `--limit` CLI flag is exceeded.
5. The `PAGE_HARD_LIMIT` constant (200) is hit — final safety net.

## Usage

```bash
# List all available categories
python main.py --list-categories

# Scrape a single category (for testing)
python main.py --category oturma-odasi-mobilyalari --limit 1

# Full daily catalogue extraction (default 3 workers)
python main.py

# Resume an interrupted run
python main.py --resume

# Tune throughput / politeness
python main.py --workers 4 --delay 0.7
```

After a successful scrape the runner automatically invokes the inflation
calculator at `Inflations/Codes/HomeGoods/Vivense/inflation.py`.

## Categories

The scraper hits 15 curated top-level navigation buckets (see
`config.TOP_LEVEL_CATEGORIES`). Brand / promo pages such as
`vivense-collection`, `home-cosmetics` and `vivense-yurt-disinda` are
excluded because they are cross-cuts of the catalogue and would only
duplicate products.

## TUIK Mapping

Every Vivense top-level category maps to TUIK group **05** —
_Mobilya, ev aletleri ve ev bakım hizmetleri_ (weight 7.92 % in the 2026
TÜFE basket). See `Inflations/Codes/HomeGoods/Vivense/tuik_config.py`.
