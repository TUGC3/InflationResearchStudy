# TUFE Inflation System - Technical Architecture

## System Overview

The TUFE Inflation System is a Python-based multi-stage pipeline that calculates inflation using the Turkish Consumer Price Index (TUFE) file. It transforms raw product prices into category-level and composite inflation metrics using TUFE's hierarchical weighting scheme.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                    run_tufe.py (Orchestrator)                   │
│  Coordinates all stages, validates setup, generates reports    │
└──────────┬──────────────────────────────────────────────────────┘
           │
           ├─────────────────┬─────────────────┬──────────────────┐
           │                 │                 │                  │
        STAGE 1           STAGE 2           STAGE 3            SUMMARY
        Category       Rent Analysis      Full Aggreg        Report Gen
        Analysis       (rent_inflation    (full_calculate)    (JSON log)
        (tufe_cross_   _tufe.py)          Final composite
         store_compare)                   TUFE inflation
           │                 │                 │
           ▼                 ▼                 ▼
    ┌─────────────────┐ ┌──────────────┐ ┌──────────────────┐
    │   6 Categories  │ │ Cities ×     │ │ Aggregate all    │
    │ Markets         │ │ Room Counts  │ │ categories with  │
    │ Clothing        │ │              │ │ TUFE weights     │
    │ Cosmetics       │ │ Country-wide │ │                  │
    │ Construction    │ │ rent inflation│ │ Output:          │
    │ Tech            │ │ (weighted)   │ │ - Composite      │
    │ HomeGoods       │ │              │ │ - Detailed       │
    │                 │ │              │ │ - Validation     │
    └────────┬────────┘ └──────┬───────┘ └────────┬─────────┘
             │                 │                  │
             └─────────┬───────┴──────────────────┘
                       │
        ┌──────────────▼──────────────────┐
        │   Output: 30+ CSV Reports       │
        │   TUFE_Total_Inflation_*.csv    │
        │   TUFE_*_category_inflation.csv │
        │   + Mapping quality reports     │
        └─────────────────────────────────┘
```

## Data Flow

```
Raw Data                 Data Loading          TUFE Tagging       Calculation
┌────────────┐
│ Market     │ ──┐                           
│ CSV Files  │   │  ┌──────────────────┐    ┌────────────┐    ┌──────────────┐
└────────────┘   ├─→│inflation_engine  │───→│ product_   │───→│ tufe_cross_  │
                 │  │_tufe.py          │    │ mapper.py  │    │ store_       │
┌────────────┐   │  ├──────────────────┤    │            │    │ compare.py   │
│ Clothing   │   │  │• Loads CSVs      │    │• Fuzzy     │    │              │
│ CSV Files  │   ├─→│• Cleans prices   │    │  match     │    │• Per-        │
└────────────┘   │  │• Handles diverse │    │• Keyword   │    │  category    │
                 │  │  formats         │    │  match     │    │  inflation   │
┌────────────┐   │  │• Tags TUFE codes │    │• Fallback  │    │• Store-level │
│ Rent       │   │  └──────────────────┘    │  mapping   │    │  weighted    │
│ CSV Files  │   │                          └────────────┘    │• Quality     │
│ by City    │   │  ┌──────────────────┐                      │  metrics     │
└────────────┘   └─→│rent_inflation_   │                      └──────────────┘
                    │tufe.py           │                               │
                    ├──────────────────┤                               │
                    │• City grouping   │                               │
                    │• Room extraction │                               │
                    │• Aggregation     │                               │
                    └──────────────────┘                               │
                                                                       │
    ┌──────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────┐
│ full_calculate_tufe.py      │
├─────────────────────────────┤
│• Load all category reports  │
│• Apply TUFE weights         │
│• Calculate composite        │
│• Generate final reports     │
└─────────────────────────────┘
    │
    ▼
COMPOSITE TUFE INFLATION (Main Output)
```

## Detailed Component Specifications

### 1. tufe_parser.py

**Purpose:** Parse TUFE file and build searchable category hierarchy

**Key Classes:**
- `TUFEParser` - Main parser class

**Key Methods:**
```python
parse() → Dict
  Returns: {categories, tree, count, total_weight}

get_category_by_code(code) → Dict
  Returns: {name_tr, name_en, weight, level, keywords, children}

search_by_keyword(keyword) → List[str]
  Returns: List of matching category codes

get_all_descendants(parent_code) → List[str]
  Returns: All subcategories recursively

print_tree(code=None, indent=0)
  Prints hierarchy structure
```

**Data Structure:**
```python
categories[code] = {
    'code': 'code_str',
    'name_tr': 'Turkish name',
    'name_en': 'English name',
    'weight': 22.1040,  # TUFE weight
    'level': 0,  # Hierarchy level (0=root, 1-4=subcategories)
    'keywords': ['keyword1', 'keyword2'],
    'parent_code': 'parent_code_str',
    'children': ['child_code1', 'child_code2']
}
```

**Input:** TUFE file (tab-separated: Turkish | English | Weight)

**Output:** Searchable category tree with hierarchical structure

### 2. product_mapper.py

**Purpose:** Map product names to TUFE categories

**Key Classes:**
- `ProductMapper` - Main mapper class

**Matching Strategy (Priority Order):**

1. **Manual Overrides** (confidence: 0.95)
   - Pre-defined mappings for known product keywords
   - ~100+ mappings covering common products
   - Example: "pirinç" → "1_1_1_2" (Rice)

2. **Keyword Matching** (confidence: 0.7-0.8)
   - Search TUFE keywords extracted from names
   - Match longest overlapping keyword
   - Example: "Arko Cool Deodorant" → matches "deodorant"

3. **Fuzzy String Matching** (confidence: 0.6-0.7)
   - SequenceMatcher ratio against category names
   - Compare both Turkish and English names
   - Example: "Beyaz Peynir" ↔ "White brined cheese"

4. **Category Hint Fallback** (confidence: 0.3)
   - Use generic category for hint (food → 1_1)
   - Example: "Unknown product name" + hint="food" → "1_1"

5. **Unmapped** (confidence: 0.0)
   - Product not mapped to any category
   - Logged for review

**Text Normalization:**
- Convert to lowercase
- Remove Turkish diacritics: ç→c, ğ→g, ı→i, ö→o, ş→s, ü→u
- Remove special characters (except spaces)
- Collapse multiple spaces

**Caching:** All mappings cached after first lookup

### 3. inflation_engine_tufe.py

**Purpose:** Load data from all sources with TUFE tagging

**Key Classes:**
- `TUFEInflationEngine` - Extended data loader

**Supported Data Sources:**

| Source | Format | Example File |
|--------|--------|--------------|
| Markets | CSV: productname,price,category | a101_kapida_2026-05-18.csv |
| Clothing | CSV: kategori,urun_id,barcode,urun_ismi,fiyat | adax_urunler_2026-03-14.csv |
| Cosmetics | Semicolon-delimited: name;price | watsons_22-05-2026.csv |
| Construction | CSV: Title,Price(TL) | Bauhaus_2026-05-18.csv |
| Tech | CSV: Product Name,Price,Category | huawei_2026-05-26.csv |
| HomeGoods | CSV: title,price | Bellona_2026-05-18.csv |
| Rent | CSV by city directory: room descriptions + prices | Ankara/file.csv |

**Price Format Handling:**
- Turkish: 1.250.000 (thousands), 1.250,00 (decimal)
- English: 1250000, 1250.00
- With labels: "Başlangıç: 129.999,00 ₺"
- Smart detection: if both . and , → Turkish format

**Output Schema:**
```python
DataFrame columns: [
    'Date': datetime,           # Extracted from filename YYYY-MM-DD
    'Store': str,               # Store/city name
    'ProductName': str,         # Raw product name
    'Category': str,            # Local category if available
    'Active_Price': float,      # Cleaned price
    'TUFE_Code': str,          # Mapped TUFE code
    'TUFE_Confidence': float    # Confidence 0.0-1.0
]
```

### 4. tufe_cross_store_compare.py

**Purpose:** Calculate category-level inflation using TUFE weights

**Key Classes:**
- `TUFECrossStoreCompare` - Main analyzer
- Methods for three types of analysis

**Inflation Calculation Formula:**

```
For each TUFE category:
  MoM Inflation % = (Σ(product % change) / n_products)
  
For store-level:
  Weighted Inflation % = Σ(category_inflation × category_weight) / Σ(weights)
  
For country-level:
  Total Inflation % = Σ(category_inflation × category_weight) / Σ(weights)
```

**Three Output Reports:**

1. **Category Inflation Report**
   - Format: [YearMonth, TUFE_Code, TUFE_Name, Inflation_%, NumProducts, NumStores]
   - Shows inflation per TUFE category
   - Tracks data quality (# products, # stores)

2. **Store-Weighted Inflation Report**
   - Format: [YearMonth, Store, Weighted_Inflation_%]
   - Each store's inflation using TUFE category weights
   - Enables store comparison within category

3. **Total Inflation Report**
   - Format: [YearMonth, TUFE_Inflation_%]
   - Overall inflation for entire category
   - Used in full aggregation

**Example Calculation:**

Markets category (Feb 2026):
- Bread inflation: +1.2%, weight: 3.39% → contribution: 0.041%
- Meat inflation: +2.1%, weight: 4.61% → contribution: 0.097%
- Dairy inflation: +0.8%, weight: 3.28% → contribution: 0.026%
- ... (13 more subcategories)

Total market inflation = 0.041 + 0.097 + 0.026 + ... ≈ 0.74%

### 5. rent_inflation_tufe.py

**Purpose:** Calculate rent inflation with city and room-count grouping

**Rent Data Handling:**

Step 1: **Load by City**
- Each city is a subdirectory: Ankara/, Istanbul/, Izmir/, etc.
- Load all CSV files from city directory

Step 2: **Extract Room Count**
- Patterns: "(\d+)\s*(bedroom|br|oda)" → 2
- Studio/T0 → 0
- Unknown → None

Step 3: **Aggregate by (City, RoomCount, YearMonth)**
```
Istanbul_1BR_2026-03: avg_price = (900K + 920K + 880K) / 3 = 900K
Istanbul_2BR_2026-03: avg_price = (1.3M + 1.4M + 1.25M) / 3 = 1.32M
Ankara_1BR_2026-03: avg_price = 600K
...
```

Step 4: **Calculate City-Level Inflation**
- Month-over-month % change per (city, room_count)
- Tracks sample size for weighting

Step 5: **Aggregate to Country Level**
- Weight each (city, room_count) pair by its sample size
- Country inflation = Σ(city_inflation × sample_size) / Σ(sample_size)

**Example (Feb-Mar 2026):**

City Data:
- Istanbul 1BR: 900K → 920K (change: +2.2%)
- Istanbul 2BR: 1.3M → 1.4M (change: +7.7%)
- Ankara 1BR: 600K → 620K (change: +3.3%)
- Ankara 2BR: 850K → 875K (change: +2.9%)

Sample Sizes (# of observations):
- Istanbul 1BR: 50 observations
- Istanbul 2BR: 40 observations
- Ankara 1BR: 35 observations
- Ankara 2BR: 25 observations

Country-level inflation = (2.2×50 + 7.7×40 + 3.3×35 + 2.9×25) / (50+40+35+25)
                        = (110 + 308 + 115.5 + 72.5) / 150
                        = 606 / 150 = 4.04%

### 6. full_calculate_tufe.py

**Purpose:** Aggregate all categories into composite TUFE inflation

**Category Weight Mapping:**

```python
Categories → TUFE Root Codes → Weights:
Markets → 1 → 22.1040% (Food)
ClothingStores → 2 → 7.9038% (Clothing)
HousesRent → 3 → 11.4020% (Housing)
Furniture/HomeGoods/Construction → 4 → 7.9201% (Furnishings)
Tech/TechnologicalProducts → 6 → 3.1035% (Communication)
Cosmetics → 11 → 1.8720% (Personal Care)
```

**Composite Calculation:**

```
TUFE_Composite_Inflation% = 
    (Markets% × 22.1040 +
     Clothing% × 7.9038 +
     Housing% × 11.4020 +
     Furnishings% × 7.9201 +
     Communication% × 3.1035 +
     PersonalCare% × 1.8720) 
    / (22.1040 + 7.9038 + 11.4020 + 7.9201 + 3.1035 + 1.8720)
```

**Example (April 2026):**

If actual category inflations are:
- Markets: 2.54%
- Clothing: -0.11%
- Housing: 0.77%
- Furnishings: 4.23%
- Communication: 1.50%
- PersonalCare: 2.10%

Composite = (2.54×22.1 + (-0.11)×7.90 + 0.77×11.40 + 4.23×7.92 + 1.50×3.10 + 2.10×1.87) 
           / (22.1 + 7.90 + 11.40 + 7.92 + 3.10 + 1.87)
         = (56.13 - 0.87 + 8.78 + 33.50 + 4.65 + 3.93) / 54.1
         = 106.12 / 54.1
         = 1.96%

**Output Reports:**

1. **Composite Report**
   - All category inflations + composite total
   - Used for trend analysis

2. **Detailed Report**
   - Includes category weights for reference
   - Breakdown by TUFE 2-digit categories

3. **Validation Report**
   - Coverage statistics per category
   - Data quality metrics

### 7. run_tufe.py

**Purpose:** Orchestrate entire pipeline

**Pipeline Stages:**

```
Setup
  ├─ Validate directories
  ├─ Load TUFE file
  └─ Initialize logging

Stage 1: Category Analysis
  ├─ Markets (tufe_cross_store_compare)
  ├─ Clothing
  ├─ Cosmetics
  ├─ Construction
  ├─ Tech
  └─ HomeGoods
  
Stage 2: Rent Analysis
  └─ rent_inflation_tufe
  
Stage 3: Full Aggregation
  └─ full_calculate_tufe
  
Summary Report Generation
  └─ TUFE_Pipeline_Summary.json
```

**Command-Line Interface:**

```bash
python run_tufe.py [options]

Options:
  --project-root PATH     Root directory (default: auto-detect)
  --stage 1 2 3          Which stages to run (default: all)

Examples:
  python run_tufe.py                    # All stages
  python run_tufe.py --stage 1          # Only category analysis
  python run_tufe.py --stage 1 3        # Skip rent
```

## Error Handling & Quality Assurance

### Product Mapping Quality Thresholds

- **High Quality (>90% mapping rate):** 
  - All data used in inflation calculation
  - Confidence threshold: > 0.6

- **Medium Quality (70-90% mapping rate):**
  - Monitor for issues
  - Consider reviewing unmatched products

- **Low Quality (<70% mapping rate):**
  - Investigate root cause
  - May need manual mapping additions
  - Could indicate data quality issues

### Data Validation Checks

1. **Date Format Validation**
   - All files must contain YYYY-MM-DD date pattern
   - Invalid dates logged and skipped

2. **Price Format Validation**
   - Prices cleaned and converted to float
   - NaN prices dropped

3. **Store/Category Consistency**
   - Each record must have valid Store name
   - Missing categories filled with default

4. **Temporal Consistency**
   - Each category tracks dates present
   - Missing months flagged in validation report

### Logging & Debugging

- Console output shows progress per stage
- Errors logged but don't stop pipeline
- `TUFE_Pipeline_Summary.json` contains:
  - Start/end timestamps
  - Stage completion status
  - List of all generated files
  - Data quality metrics

## Performance Characteristics

### Time Complexity

| Component | Time | Notes |
|-----------|------|-------|
| TUFE parsing | O(n) | n = # lines in TUFE file (~1000) |
| Product mapping | O(n×m) | n = # products, m = # TUFE categories |
| Data loading | O(n) | n = # CSV files |
| Inflation calculation | O(n×k) | n = # records, k = # months |
| Aggregation | O(k) | k = # months (~12-24) |
| **Total** | **O(n×m)** | Usually 5-15 minutes |

### Memory Usage

- TUFE tree: ~1-2 MB
- Product cache: ~5-10 MB per 10K products
- In-memory DataFrames: ~50-200 MB
- **Total:** < 1 GB for typical dataset

### Optimization Opportunities

1. **Parallel Category Processing**
   - Categories can be processed in parallel
   - Use multiprocessing.Pool for category analysis

2. **Caching Product Mappings**
   - Already implemented in ProductMapper
   - Save cache to disk between runs

3. **Vectorized Operations**
   - Already using pandas groupby/apply
   - Could use numpy for price cleaning

4. **Lazy Loading**
   - Load data as needed instead of all at once
   - Useful for very large datasets

## Testing Strategy

### Unit Tests (Recommended)

```python
# Test TUFE parser
test_parse_tufe_file()
test_get_category_by_code()
test_search_keywords()
test_category_hierarchy()

# Test product mapper
test_manual_override_match()
test_fuzzy_matching()
test_turkish_normalization()
test_cache_performance()

# Test data loading
test_load_market_data()
test_price_cleaning()
test_rent_room_extraction()
test_date_parsing()

# Test calculations
test_category_inflation()
test_weighted_inflation()
test_country_aggregation()
```

### Integration Tests (Recommended)

```python
# Test full pipeline
test_full_pipeline_with_sample_data()
test_output_file_generation()
test_report_consistency()
```

### Data Validation Tests

```python
# Sanity checks on outputs
assert composite_inflation is not None
assert all(composite_inflation['Composite_TUFE_Inflation_%'].abs() < 100)  # No extreme values
assert len(composite_inflation) == len(all_months)  # All months present
```

## Future Enhancements

1. **Seasonal Adjustment**
   - Remove seasonal patterns (e.g., winter heating costs)
   - Use X-13ARIMA-SEATS methodology

2. **Confidence Intervals**
   - Calculate 95% CI around point estimates
   - Show uncertainty ranges

3. **Store Entry/Exit Tracking**
   - Handle store openings/closings
   - Adjust for composition effects

4. **Real-Time Updates**
   - Process new data incrementally
   - Maintain rolling window instead of full recalculation

5. **Visualization Dashboard**
   - Interactive charts of inflation trends
   - Category-level drill-down capabilities
   - Store comparison views

6. **Statistical Testing**
   - Significance tests for inflation changes
   - Outlier detection and handling

---

**System Version:** 1.0 (May 2026)
**Python Version Required:** 3.8+
**Dependencies:** pandas, numpy
