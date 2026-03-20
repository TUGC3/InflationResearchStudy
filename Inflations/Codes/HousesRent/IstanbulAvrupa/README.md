# IstanbulAvrupa Rent Inflation Calculator

Calculates inflation metrics for IstanbulAvrupa rental listings using TUIK 2026 CPI basket weights.

## Overview

Computes three inflation metrics for rental listings:

1. **Basic Inflation** - Per-segment (District × Rooms) median price change (%)
2. **Average Inflation** - Arithmetic mean of all per-segment basic inflation rates
3. **TUIK Weighted Average** - Weighted average using TUIK 2026 CPI basket weights

## Special Methodology

Since rental listings have no stable product IDs, this calculator:

- Groups listings by `(District, Rooms)` segments
- Compares median prices between dates
- Maps all segments to TUIK group 04 (Housing)

## Data Requirements

### Input Files

- **Location**: `InflationItems/Datas/HousesRent/IstanbulAvrupa/IstanbulAvrupa_YYYY-MM-DD.csv`
- **Required columns**: `District`, `Rooms`, `Price`

### Key Columns

- `District`: Istanbul district name
- `Rooms`: Number of rooms (string like "3+1", "2+1")
- `Price`: Rental price string (format: "X XXX TL")

## Price Parsing

The calculator automatically parses Turkish price strings:

- Input: "8.000 TL", "12.500 TL"
- Process: Remove " TL", remove thousand separators, convert to float
- Output: `8000.0`, `12500.0`

## TUIK Category Mapping

All rental segments map to a single TUIK group:

| Segment                           | TUIK Group | Description                                |
| --------------------------------- | ---------- | ------------------------------------------ |
| All District × Rooms combinations | 04         | Konut, su, elektrik, gaz ve diğer yakıtlar |

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

`IstanbulAvrupa_inflation_YYYY-MM-DD.csv`

- Per-segment inflation data
- Columns: `District`, `Rooms`, `tuik_category`, `basic_inflation_{interval}` for each available interval
- Location: `Inflations/Datas/HousesRent/IstanbulAvrupa/`

### Summary Data

`inflation_summary.csv`

- Store-level metrics, one row per date
- Columns: `date`, `avg_inflation_{interval}`, `tuik_weighted_{interval}` for each interval
- Appends new data, updates existing dates

## Example Output

### inflation_summary.csv

```csv
date,avg_inflation_1d,tuik_weighted_1d,avg_inflation_7d,tuik_weighted_7d,avg_inflation_15d,tuik_weighted_15d,avg_inflation_30d,tuik_weighted_30d
2026-03-19,0.3594,0.3594,4.2618,4.2618,0.0,0.0,,
```

### IstanbulAvrupa_inflation_YYYY-MM-DD.csv (first columns)

```csv
District,Rooms,median_price,tuik_category,basic_inflation_1d,basic_inflation_7d,basic_inflation_15d,basic_inflation_30d
```

## Configuration

The `tuik_config.py` file contains:

- TUIK 2026 CPI basket weights
- `istanbul_avrupa_category_to_tuik()` function (always returns "04")
- `normalised_weights()` helper function

## Integration

Designed to run after daily IstanbulAvrupa scraping completes:

1. Scraper saves data to `InflationItems/Datas/HousesRent/IstanbulAvrupa/`
2. Run `python inflation.py` to calculate metrics
3. Results saved to `Inflations/Datas/HousesRent/IstanbulAvrupa/`

## Error Handling

- Missing historical data → NaN values for affected intervals
- Invalid price strings → Parsed as NaN and excluded
- Empty segments → Skipped in calculations

## Dependencies

- Python 3.8+
- pandas
- Standard library: datetime, pathlib, logging
