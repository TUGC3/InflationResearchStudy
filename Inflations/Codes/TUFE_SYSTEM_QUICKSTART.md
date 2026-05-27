# TUFE-Based Inflation Calculation System - Quick Start Guide

## Overview

This system calculates inflation using the **Turkish Consumer Price Index (TUFE)** file to:
1. **Map products** from all data sources to TUFE categories
2. **Calculate category-level inflation** using TUFE weights
3. **Aggregate across sectors** into a composite TUFE inflation rate
4. **Handle rent specially** by grouping cities and room types

## System Components

### Core Modules

| Module | Purpose |
|--------|---------|
| `tufe_parser.py` | Parses TUFE file → hierarchical category tree with weights |
| `product_mapper.py` | Maps product names → TUFE categories (fuzzy + keyword matching) |
| `inflation_engine_tufe.py` | Loads all data sources, tags with TUFE categories |
| `tufe_cross_store_compare.py` | Calculates category-level inflation using TUFE weights |
| `rent_inflation_tufe.py` | Specialized rent calc: city + room-count grouping |
| `full_calculate_tufe.py` | Aggregates all categories → composite TUFE inflation |
| `run_tufe.py` | Orchestrator: runs all stages end-to-end |

### Output Directory Structure

```
Inflations/Datas/Final_Reports/
├── TUFE_Markets/
│   ├── markets_tufe_category_inflation.csv      # Category-level MoM %
│   ├── markets_tufe_store_weighted_inflation.csv # Store inflation (TUFE-weighted)
│   ├── markets_tufe_total_inflation.csv          # Overall market inflation
│   └── markets_tufe_mapping_quality.csv          # Mapping statistics
├── TUFE_ClothingStores/
├── TUFE_Cosmetics/
├── TUFE_ConstructionSuppliesMarkets/
├── TUFE_TechnologicalProducts/
├── TUFE_HomeGoods/
├── TUFE_Rent/
│   ├── rent_city_roomcount_aggregated.csv       # City × Room Count prices
│   ├── rent_city_inflation.csv                   # City-level inflation
│   └── rent_country_inflation.csv                # Country-level rent inflation
├── TUFE_Total_Inflation_Composite.csv           # **MAIN OUTPUT: Composite inflation**
├── TUFE_Total_Inflation_Detailed.csv            # Detailed breakdown by category
├── TUFE_Total_Inflation_Validation.csv          # Quality metrics
└── TUFE_Pipeline_Summary.json                   # Pipeline execution log
```

## Quick Start

### 1. Run Full Pipeline (All Stages)

```bash
cd c:\Users\onurk\Desktop\Projects\InflationResearchStudy\Inflations\Codes
python run_tufe.py
```

**Expected output:**
- ✓ Loads TUFE file with all categories
- ✓ Processes Markets, Clothing, Cosmetics, Construction, Tech, HomeGoods
- ✓ Analyzes rent data by city + room count
- ✓ Generates 30+ CSV reports
- ✓ Creates composite TUFE inflation file
- ⏱️ Takes 5-15 minutes depending on data volume

### 2. Run Specific Stages

```bash
# Only run category analysis (stages 1 only)
python run_tufe.py --stage 1

# Skip rent, run categories and aggregation (stages 1, 3)
python run_tufe.py --stage 1 3

# Custom project root
python run_tufe.py --project-root c:\path\to\project --stage 1 2 3
```

### 3. Run Individual Components

#### Parse TUFE File
```bash
python tufe_parser.py
# Output: Prints TUFE category tree structure
```

#### Test Product Mapper
```bash
python product_mapper.py
# Output: Shows mapping accuracy for test products
```

#### Test Data Loading with TUFE Tags
```bash
python inflation_engine_tufe.py
# Output: Shows sample records with TUFE mappings
```

#### Analyze Single Category (e.g., Markets)
```bash
python tufe_cross_store_compare.py --type Markets
```

#### Analyze Rent Data
```bash
python rent_inflation_tufe.py
```

#### Aggregate Final Reports
```bash
python full_calculate_tufe.py
```

## Understanding Output Reports

### Main Output: `TUFE_Total_Inflation_Composite.csv`

```
YearMonth  Markets_Inflation_%  ClothingStores_Inflation_%  HomeGoods_Inflation_%  ...  Composite_TUFE_Inflation_%
2026-02    0.74                 -1.23                       2.15                   ...  0.85
2026-03    1.25                 0.45                        1.98                   ...  1.15
2026-04    2.54                 -0.11                       4.23                   ...  2.00
...
```

**Interpretation:**
- Each column = category inflation for that month
- `Composite_TUFE_Inflation_%` = overall Turkey inflation using TUFE weights
- Values can be negative (deflation)

### Category Report Example: `TUFE_Markets_tufe_category_inflation.csv`

```
YearMonth  TUFE_Code  TUFE_Name                    Inflation_%  NumProducts  NumStores
2026-03    1_1_1      Cereals                      0.50         15           5
2026-03    1_1_2      Bread and bakery products    1.20         8            4
2026-03    1_2_1      Meat, fresh, chilled         2.10         12           6
...
```

**Shows:**
- Month-over-month inflation per TUFE category
- How many products/stores contributed to the calculation
- Detailed category breakdown (e.g., "Meat" vs "Bread" vs "Cereals")

### Rent Report: `rent_country_inflation.csv`

```
YearMonth  Rent_Inflation_%
2026-03    1.50
2026-04    1.75
2026-05    2.10
```

**How it was calculated:**
1. Loaded rent data from all cities
2. Grouped by (city, room_count): Istanbul_1BR, Istanbul_2BR, Ankara_1BR, etc.
3. Calculated inflation per city/room-count pair
4. Aggregated to country level using sample-size weighting

## Product Mapping Quality

Each category analysis generates a mapping quality report showing:
- **Total records loaded** (all products)
- **Mapped** (assigned TUFE category)
- **Unmapped** (no matching TUFE category found)
- **Mapping rate %** (Mapped / Total × 100)
- **Average confidence** (0.0 - 1.0, higher = more confident match)

Example:
```
Category            Total_Records  Mapped  Unmapped  MappingRate_%  AvgConfidence
Overall             50000          48500   1500      97.00%         0.875
Store: A101         10000          9800    200       98.00%         0.890
Store: Migros       8000           7700    300       96.25%         0.865
```

**Interpretation:**
- > 90% mapping rate = good quality
- Average confidence > 0.7 = high-quality matches
- Low mapping rate on specific store = may need manual override additions

## TUFE Category Hierarchy

The TUFE file uses a hierarchical structure:

```
1  Food (22.10% weight)
├─ 1_1  Cereals and cereal products (4.45%)
│  ├─ 1_1_1  Cereals (0.47%)
│  ├─ 1_1_2  Bread and bakery (3.39%)
│  └─ 1_1_3  Breakfast cereals (0.03%)
├─ 1_2  Meat (4.61%)
│  ├─ 1_2_1  Fresh meat (3.67%)
│  └─ 1_2_2  Processed meat (0.61%)
...

2  Clothing (7.90% weight)
3  Housing (11.40% weight)
...
```

**For inflation calculation:**
- **Detailed level (4-digit codes)**: Shows inflation per specific item (e.g., "Bread" vs "Cereals")
- **Aggregated level (2-digit codes)**: Shows inflation per major category (e.g., "Food" vs "Clothing")
- **Weights** at each level are used to calculate composite inflation

## Troubleshooting

### Issue: "TUFE file not found"
**Solution:** Ensure file exists at `Inflations/Codes/TUFE`

### Issue: "No data loaded for Markets"
**Solution:** Check that CSV files exist in `InflationItems/Datas/Markets/`

### Issue: Low mapping rate (< 80%)
**Solution:** 
- Some products are too generic or misspelled
- Consider adding manual overrides to `product_mapper.py`
- Review unmatched samples in mapping quality report

### Issue: Rent inflation shows NaN values
**Solution:**
- Rent data may be missing for certain months/cities
- Check `rent_city_roomcount_aggregated.csv` for gaps
- Ensure rent file names contain dates (YYYY-MM-DD format)

## Advanced: Customization

### Add Manual Product Mapping Override

In `product_mapper.py`, add to `_load_manual_overrides()`:

```python
self.manual_overrides = {
    ...
    'my_product_keyword': '2_1_1',  # Maps to specific TUFE code
    'another_keyword': '1_7_3',
}
```

### Adjust TUFE Weights

Weights are loaded from the TUFE file. To override:

```python
# In any calculation module
category_weight = 25.0  # Override with your custom weight
```

### Change Category Hints

In `inflation_engine_tufe.py`, modify the category hint passed to loaders:

```python
df = self._tag_with_tufe(df, 'custom_hint')  # Instead of 'food', 'clothing', etc.
```

## Performance Notes

- **Full pipeline**: 5-15 minutes depending on data volume
- **Category analysis**: 1-3 minutes per category
- **Rent analysis**: 2-5 minutes (depends on # cities × # room types)
- **Full aggregation**: < 1 minute
- **Memory usage**: Typically < 1GB

## Next Steps

1. **Run the full pipeline:**
   ```bash
   python run_tufe.py
   ```

2. **Check the main output:**
   ```
   Inflations/Datas/Final_Reports/TUFE_Total_Inflation_Composite.csv
   ```

3. **Review category breakdown:**
   ```
   Inflations/Datas/Final_Reports/TUFE_Markets/markets_tufe_category_inflation.csv
   ```

4. **Compare with existing system:**
   - Compare `TUFE_Total_Inflation_Composite.csv` inflation % with current system
   - Differences < 5% = system is working well
   - Check mapping quality reports for any issues

## Documentation Files Generated

After running the pipeline:
- `TUFE_Pipeline_Summary.json` - Complete execution log with all file paths
- `TUFE_*_mapping_quality.csv` - Product mapping statistics per category
- `rent_quality_report.csv` - Rent data quality statistics

---

**Questions or Issues?**
- Check the mapping quality reports
- Review TUFE category names in output files
- Verify data files exist in expected locations
- Check console output for specific error messages
