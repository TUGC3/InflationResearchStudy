# Turkey Inflation Calculator — Revision Design

**Date:** 2026-05-31
**File:** `Inflations/Codes/turkey_inflation.py`

## Problem Statement

All CSV data files have been standardized to `product_name,price` column structure. The current `turkey_inflation.py` has ~40 per-store loader functions with hardcoded, store-specific column names that are now invalid. Additionally, the metric computation averages price levels across stores before computing change, which produces incorrect results when a product's store availability differs between dates.

Two pieces of supervisor feedback drive this revision:

1. Use `canonical_key` (normalized product name) as the join key throughout — for deduplication and cross-date matching.
2. Compute relative price changes (`current/past - 1`) within each store first, then average across stores — never average price levels across stores.

## Architecture

### Sector Config Dict

Replaces all per-store loader functions. Maps data directory name → `(tuik_code, sector_label)`:

```python
_SECTOR_CONFIG = {
    "Markets":                     ("01", "market"),
    "ClothingStores":              ("03", "clothing"),
    "HousesRent":                  ("04", "rent"),       # special loader
    "HomeGoods":                   ("05", "homegoods"),
    "ConstructionSuppliesMarkets": ("05", "construction"),
    "Health":                      ("06", "health"),     # monthly files
    "TechnologicalProducts":       ("08", "tech"),
    "TravelTourism":               ("11", "tourism"),
    "Cosmetics":                   ("13", "cosmetics"),
}
```

Adding a future sector (e.g. Transport group 07) = one dict entry.

### Data Flow

```
_DATA_ROOT/
  SectorDir/
    StoreDir/
      store_YYYY-MM-DD.csv   ← discovered by date + header validation

For each sector:
  scan StoreDir/ subdirs → find CSV by date in filename → validate header
  → load as (canonical_key, product_key, price, store, sector, tuik_category)

Pool all frames → compute relative-price metrics → write outputs
```

## Auto-Discovery & Protection Rules

```python
_SKIP_SUBDIRS = {"InflationData", "output", "reports", "archive"}
```

Five protection rules applied in order:

1. **Skip known output subdirs** — any intermediate subdir whose name is in `_SKIP_SUBDIRS` is skipped (e.g. `Bershka/InflationData/`); the scanner uses `rglob` so it handles stores like Bershka where CSVs sit one extra level deep (`Bershka/ProductData/*.csv`)
2. **Header validation** — CSV must have `product_name,price` as exact first line; anything else is silently skipped
3. **Date in filename** — only files containing `date_str` in their name are candidates
4. **Recursive within store dir** — scanner uses `store_dir.rglob(f"*{date_str}*.csv")` and skips any path whose intermediate parts include a `_SKIP_SUBDIRS` name; HousesRent and Health still have dedicated loaders
5. **Store name from dir** — store label is taken from the immediate subdirectory name under the sector dir (e.g. `ClothingStores/Bershka/` → store `"Bershka"`); no hardcoding

## Canonical Key

`canonical_key = _norm(product_name)` — Turkish diacritics stripped, lowercased, whitespace collapsed.

- Added at read time in the generic loader
- Used as the join key for both deduplication and cross-date matching
- `product_key` (original name) retained for display in output CSV only

## Metric Computation (Relative Price Approach)

### Why relative, not absolute

If Store A sells a product at 100 → 110 (+10%) and Store B only has the product in the current snapshot (not past), averaging price levels gives a spurious +65%. Joining on `(store, canonical_key, tuik_category)` ensures only store-matched pairs are used.

### Algorithm

```
current pool: (store, canonical_key, tuik_category, price)
past pool:    (store, canonical_key, tuik_category, price) → past_price

Step 1: Inner join on (store, canonical_key, tuik_category)
        → only products present in the SAME store on BOTH dates

Step 2: relative = current_price / past_price - 1  (per row)

Step 3: groupby(canonical_key, tuik_category) → mean(relative) across stores
        → one relative-change value per unique product

Step 4: groupby(tuik_category) → mean(relative) across products
        → one value per TUIK category

Step 5: Apply TUIK weights across categories → tuik_weighted metric
        Rent injected as group "04" (city-level mean change, not product-level)
```

### Three output metrics (unchanged names)

- `basic_index` — basket-level: `sum(current_prices) / sum(past_prices) - 1` on matched pairs
- `avg_inflation` — arithmetic mean of per-product relative changes (Step 3 mean across all products)
- `tuik_weighted` — Step 5 result, with and without rent

## Special Cases

### HousesRent (group 04)

- Recursive scan: city dirs may contain sub-city dirs; scan all levels for CSVs matching the date
- `product_name` column = listing description (not a product); `price` = rent amount
- Compute mean price per city-dir, then relative change across cities present on both dates
- Result injected into TUIK-weighted metric only; excluded from product-level `basic_index` and `avg_inflation`

### Health (group 06)

- Files use monthly granularity: `health_prices_YYYY-MM.csv`
- Match by extracting `YYYY-MM` prefix from target date
- If no matching month file exists, sector is skipped for that run (no interpolation)

## TUIK Basket Coverage

Current coverage: **73.19%**

| Code | Category | Weight | Status |
|------|----------|--------|--------|
| 01 | Gıda ve alkolsüz içecekler | 24.44% | covered |
| 03 | Giyim ve ayakkabı | 7.90% | covered |
| 04 | Konut, su, elektrik, gaz | 11.40% | covered |
| 05 | Mobilya, mefruşat ve ev ekipmanları | 7.92% | covered |
| 06 | Sağlık | 2.79% | covered |
| 08 | Bilgi ve iletişim | 3.10% | covered |
| 11 | Lokantalar ve konaklama | 11.13% | covered |
| 13 | Kişisel bakım ve diğer | 4.49% | covered |
| 07 | Ulaştırma | 16.62% | pending supervisor feedback |
| 02 | Alkollü içecekler, tütün | 2.75% | pending supervisor feedback |
| 09 | Eğlence, dinlence, spor ve kültür | 4.34% | pending supervisor feedback |
| 10 | Eğitim hizmetleri | 2.02% | pending supervisor feedback |
| 12 | Sigorta ve finansal hizmetler | 1.07% | pending supervisor feedback |

Coverage report is printed to the log and written as a column block in `turkey_inflation_summary.csv` each run.

## Output Format (unchanged)

- `Inflations/Datas/Final_Reports/turkey_inflation_{YYYY-MM-DD}.csv`
  Per-product rows: `canonical_key`, `product_key`, `store`, `sector`, `tuik_category`, `relative_{interval}` per computed interval
- `Inflations/Datas/Final_Reports/turkey_inflation_summary.csv`
  Time-series row appended per run: date, n_stores, n_products_raw, n_products_deduped, all three metrics per interval, rent_inflation, basket_coverage_pct

## CLI (unchanged)

```
python turkey_inflation.py                    # today, 15d / 30d intervals
python turkey_inflation.py --date 2026-05-01  # specific target date
python turkey_inflation.py --date 2026-05-01 --compare 2026-04-01
```
