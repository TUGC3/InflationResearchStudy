# Sephora Inflation Calculator

Calculates inflation metrics for Sephora Türkiye cosmetics products
using TUIK 2026 CPI basket weights.  Mirrors the Koton / Migros
calculators so cross-store comparisons remain consistent.

## Overview

Computes three inflation metrics for Sephora products:

1. **Basic Inflation** – basket-level price index change (%) calculated
   as sum of current sale prices vs sum of past sale prices across
   matched products.
2. **Average Inflation** – arithmetic mean of all per-product percentage
   price changes.
3. **TUIK Weighted Average** – weighted average using TUIK 2026 CPI
   basket weights, normalised to the TUIK groups present in the data.

## Data Requirements

### Input Files

- **Location**: `InflationItems/Datas/Cosmetics/Sephora/sephora_YYYY-MM-DD.csv`
- **Required columns**: `id`, `sale_price`, `category`, `category_id`

### Key Columns

- `id`: Unique product identifier used for matching across dates
- `sale_price`: Currently shown price (numeric TRY)
- `category`: Breadcrumb label (used for TUIK mapping)
- `category_id`: Fallback slug used when the breadcrumb is empty

## TUIK Category Mapping

Sephora is almost entirely a personal-care retailer, so the mapping is
deliberately simple:

| TUIK Group | Description                                               | Example Categories                           |
| ---------- | --------------------------------------------------------- | -------------------------------------------- |
| 12         | Kişisel bakım, sosyal koruma ve çeşitli mal ve hizmetler  | `makeup/...`, `skincare/...`, `parfum/...`   |
| 05         | Mobilya, ev aletleri ve ev bakım hizmetleri               | `makyaj-firca`, `makyaj-ayna`, `makyaj-canta` |

Unknown or missing categories default to TUIK group 12.

## Usage

```bash
# Calculate today's inflation with the standard 1d / 7d / 15d / 30d intervals
python inflation.py

# Target a specific date
python inflation.py --date 2026-03-20

# Compare two arbitrary dates
python inflation.py --date 2026-03-20 --compare 2026-03-10
```

## Output Files

### Detailed Data

`sephora_inflation_YYYY-MM-DD.csv`

- Per-product inflation data with percentage price changes
- Columns: all original scraper columns + `tuik_category` +
  `basic_inflation_{interval}` for each available interval
- Location: `Inflations/Datas/Cosmetics/Sephora/`

### Summary Data

`inflation_summary.csv`

- Store-level metrics, one row per target date
- Columns: `date`, `avg_inflation_{interval}`, `tuik_weighted_{interval}`
- Appends new data; overwrites the row if it already exists for the
  same date

## Example Output

### `inflation_summary.csv`

```csv
date,avg_inflation_1d,tuik_weighted_1d,avg_inflation_7d,tuik_weighted_7d,avg_inflation_15d,tuik_weighted_15d,avg_inflation_30d,tuik_weighted_30d
2026-04-22,0.0,0.0,1.214,1.198,2.305,2.299,,
```

### `sephora_inflation_YYYY-MM-DD.csv` (first columns)

```csv
id,sku,name,brand,category,...,tuik_category,basic_inflation_1d,basic_inflation_7d,basic_inflation_15d,basic_inflation_30d
```

## Calculation Methodology

1. **Data matching**: products matched across dates using unique `id`
2. **Per-product inflation**: `((current_price - past_price) / past_price) * 100`
3. **Basic inflation**: sum-based basket index using matched products
4. **Average inflation**: mean of all valid per-product inflation rates
5. **TUIK-weighted**: category-level averages weighted by normalised
   TUIK weights

## Configuration

`tuik_config.py` contains:

- `TUIK_WEIGHTS` – TUIK 2026 CPI main-group weights (base 2025=100)
- `sephora_category_to_tuik()` – breadcrumb / slug → TUIK code mapping
- `normalised_weights()` – rescales weights to the present groups

## Integration

Designed to run automatically after each daily Sephora scrape:

1. The scraper (`InflationItems/Codes/Cosmetics/Sephora/scripts/main.py`)
   saves a CSV to `InflationItems/Datas/Cosmetics/Sephora/`.
2. `main.py` then calls `inflation.calculate_inflation()` which reads
   the daily CSV and writes summary / detail files here.
3. Results land in `Inflations/Datas/Cosmetics/Sephora/`.

## Error Handling

- Missing historical data → `NaN` for affected intervals
- Invalid price data → coerced to `NaN`, excluded from calculations
- Missing categories → default to TUIK group 12 (personal care)
- Price changes of 0/0 → excluded from basket calculations
- Infinite inflation rates → converted to `NaN` and excluded

## Dependencies

- Python 3.8+
- `pandas`
- Standard library: `datetime`, `pathlib`, `logging`, `argparse`
