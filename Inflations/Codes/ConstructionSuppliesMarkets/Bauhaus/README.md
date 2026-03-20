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

Maps 12 Bauhaus categories to 3 TUIK groups:

| Bauhaus Category | TUIK Group | Description |
|------------------|------------|-------------|
| Boya ve İnşaat | 04 | Konut, su, elektrik, gaz ve diğer yakıtlar |
| Parke ve Kapılar | 04 | Konut, su, elektrik, gaz ve diğer yakıtlar |
| Tüm Isıtma ve Soğutma Ürünleri | 04 | Konut, su, elektrik, gaz ve diğer yakıtlar |
| Tüm Oto Ürünleri | 07 | Ulaştırma |
| Bahçe | 05 | Mobilya, ev aletleri ve ev bakım hizmetleri |
| Banyo | 05 | Mobilya, ev aletleri ve ev bakım hizmetleri |
| Dekorasyon ve Ev Gereçleri | 05 | Mobilya, ev aletleri ve ev bakım hizmetleri |
| Hırdavat ve El Aletleri | 05 | Mobilya, ev aletleri ve ev bakım hizmetleri |
| Makine | 05 | Mobilya, ev aletleri ve ev bakım hizmetleri |
| Mobilya | 05 | Mobilya, ev aletleri ve ev bakım hizmetleri |
| Mutfak | 05 | Mobilya, ev aletleri ve ev bakım hizmetleri |
| Tüm Aydınlatma ve Elektro Ürünleri | 05 | Mobilya, ev aletleri ve ev bakım hizmetleri |

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
- Columns: `basic_inflation_{interval}`, `tuik_category`, plus store-level aggregates
- Location: `Inflations/Datas/ConstructionSuppliesMarkets/Bauhaus/`

### Summary Data  
`inflation_summary.csv`
- Store-level metrics, one row per date
- Columns: `basic_inflation_{interval}`, `avg_inflation_{interval}`, `tuik_weighted_{interval}`
- Appends new data, updates existing dates

## Example Output

### inflation_summary.csv
```csv
date,basic_inflation_1d,avg_inflation_1d,tuik_weighted_1d,basic_inflation_7d,avg_inflation_7d,tuik_weighted_7d,basic_inflation_15d,avg_inflation_15d,tuik_weighted_15d,basic_inflation_30d,avg_inflation_30d,tuik_weighted_30d
2026-03-19,0.0173,0.0331,0.0378,0.9374,0.2252,0.2181,,,,
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
