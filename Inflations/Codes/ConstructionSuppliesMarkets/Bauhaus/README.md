# Bauhaus Inflation Calculator

Calculates inflation metrics for Bauhaus home improvement and construction products using TUIK 2026 CPI basket weights.

## Overview

Computes three inflation metrics for Bauhaus products:

1. **Basic Inflation** - Per-product percentage price change between two dates
2. **Average Inflation** - Arithmetic mean of all per-product basic inflation rates
3. **TUIK Weighted Average** - Weighted average using TUIK 2026 CPI basket weights

## Data Requirements

### Input Files

- **Location**: `InflationItems/Datas/ConstructionSuppliesMarkets/Bauhaus/bauhaus_YYYY-MM-DD.csv`
- **Required columns**: `id`, `shown_price`, `category`

### Key Columns

- `id`: Unique product identifier for matching across dates
- `shown_price`: Displayed price after discounts (numeric)
- `category`: Product category (mapped to TUIK groups)

## TUIK Category Mapping

Maps 12 Bauhaus categories to 2 TUIK groups:

| Bauhaus Category                   | TUIK Group | Description                                 |
| ---------------------------------- | ---------- | ------------------------------------------- |
| Bahçe                              | 05         | Mobilya, ev aletleri ve ev bakım hizmetleri |
| Banyo                              | 05         | Mobilya, ev aletleri ve ev bakım hizmetleri |
| Boya ve İnşaat                     | 05         | Mobilya, ev aletleri ve ev bakım hizmetleri |
| Dekorasyon ve Ev Gereçleri         | 05         | Mobilya, ev aletleri ve ev bakım hizmetleri |
| Hırdavat ve El Aletleri            | 05         | Mobilya, ev aletleri ve ev bakım hizmetleri |
| Makine                             | 05         | Mobilya, ev aletleri ve ev bakım hizmetleri |
| Mobilya                            | 05         | Mobilya, ev aletleri ve ev bakım hizmetleri |
| Mutfak                             | 05         | Mobilya, ev aletleri ve ev bakım hizmetleri |
| Parke ve Kapılar                   | 05         | Mobilya, ev aletleri ve ev bakım hizmetleri |
| Tüm Aydınlatma ve Elektro Ürünleri | 05         | Mobilya, ev aletleri ve ev bakım hizmetleri |
| Tüm Isıtma ve Soğutma Ürünleri     | 05         | Mobilya, ev aletleri ve ev bakım hizmetleri |
| Tüm Oto Ürünleri                   | 07         | Ulaştırma                                   |

## Usage

```bash
# Calculate today's inflation
python inflation.py

# Calculate for specific date
python inflation.py --date 2026-03-20

# Compare two arbitrary dates
python inflation.py --date 2026-03-20 --compare 2026-03-10
```

## Output Files

### Detailed Data

`bauhaus_inflation_YYYY-MM-DD.csv`

- Per-product inflation data
- Columns: `id`, `name`, `category`, `tuik_category`, `basic_inflation_{interval}` for each available interval
- Location: `Inflations/Datas/ConstructionSuppliesMarkets/Bauhaus/`

### Summary Data

`inflation_summary.csv`

- Store-level metrics, one row per date
- Columns: `date`, `avg_inflation_{interval}`, `tuik_weighted_{interval}` for each interval
- Appends new data, updates existing dates

## Example Output

### inflation_summary.csv

```csv
date,avg_inflation_1d,tuik_weighted_1d,avg_inflation_7d,tuik_weighted_7d,avg_inflation_15d,tuik_weighted_15d,avg_inflation_30d,tuik_weighted_30d
2026-03-19,0.0331,0.0378,0.2252,0.2181,,,
```

### bauhaus_inflation_YYYY-MM-DD.csv (first columns)

```csv
id,sku,name,brand,category,...,tuik_category,basic_inflation_1d,basic_inflation_7d,basic_inflation_15d,basic_inflation_30d
```

## Configuration

The `tuik_config.py` file contains:

- TUIK 2026 CPI basket weights
- `bauhaus_category_to_tuik()` mapping function
- `normalised_weights()` helper function

## Integration

Designed to run after daily Bauhaus scraping completes:

1. Bauhaus scraper saves data to `InflationItems/Datas/ConstructionSuppliesMarkets/Bauhaus/`
2. Run `python inflation.py` to calculate metrics
3. Results saved to `Inflations/Datas/ConstructionSuppliesMarkets/Bauhaus/`

## Error Handling

- Missing historical data → NaN values for affected intervals
- Invalid price data → Coerced to NaN and excluded
- Unknown categories → Default to TUIK group 05 (household goods)

## Dependencies

- Python 3.8+
- pandas
- Standard library: datetime, pathlib, logging
