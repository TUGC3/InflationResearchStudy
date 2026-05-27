# Turkey-Wide Inflation Calculator — Methodology Documentation

**Script:** `Inflations/Codes/turkey_inflation.py`  
**Output directory:** `Inflations/Datas/Final_Reports/`  
**Base year:** 2025 = 100 (TÜİK COICOP 2026 basket)  
**Prepared for:** Teaching assistant review

---

## Table of Contents

1. [Research Context and Motivation](#1-research-context-and-motivation)
2. [Data Sources](#2-data-sources)
3. [Algorithm Overview](#3-algorithm-overview)
4. [Step 1 — Price Parsing](#4-step-1--price-parsing)
5. [Step 2 — Store Loading and Normalisation](#5-step-2--store-loading-and-normalisation)
6. [Step 3 — Cross-Store Deduplication](#6-step-3--cross-store-deduplication)
7. [Step 4 — Inflation Metric Computation](#7-step-4--inflation-metric-computation)
8. [Step 5 — Rent Inflation (TUIK Group 04)](#8-step-5--rent-inflation-tuik-group-04)
9. [TUIK COICOP 2026 Basket Weights](#9-tuik-coicop-2026-basket-weights)
10. [TUIK Category Mapping Per Store](#10-tuik-category-mapping-per-store)
11. [Output Files](#11-output-files)
12. [Validation and Cross-Checks](#12-validation-and-cross-checks)
13. [Results](#13-results)
14. [Known Limitations](#14-known-limitations)
15. [Usage](#15-usage)

---

## 1. Research Context and Motivation

This script produces a daily, Turkey-wide consumer inflation estimate by aggregating micro-level product price data from 47 tracked retailers across six consumer spending sectors. The goal is to compute the same three inflation metrics used in the per-store Migros calculator — Basic Inflation Index, Average Inflation, and TÜİK-Weighted Average — but applied to a pooled national basket rather than a single store's catalogue.

The motivation is twofold:

- **Coverage**: No single retailer covers all expenditure categories. A Turkey-wide figure requires pooling food, clothing, housing, technology, personal care, and construction data.
- **Comparability**: By replicating the exact same metric formulas as the Migros per-store script, the Turkey-wide result can be directly compared with and validated against individual store outputs.

The script is designed for reproducibility: all methodology decisions are encoded explicitly in the source and documented here, with no manual adjustments or post-hoc corrections.

---

## 2. Data Sources

The project scrapes daily price data from 47 retailers organised into six sectors. All raw data is stored in `InflationItems/Datas/` under sector subdirectories.

### Grocery Markets (TUIK group 01 — Food and non-alcoholic beverages)

| Store | Directory | File Pattern | Key Columns |
|-------|-----------|-------------|-------------|
| Migros | `Markets/Migros/` | `migros_{date}.csv` | `id`, `shown_price`, `category` |
| A101 | `Markets/A101/` | `a101_kapida_{date}.csv` | `urun_id`, `fiyat`, `ana_kategori` |
| Gurmar | `Markets/Gurmar/` | `gurmar_prices_{date}.csv` | `product-name`, `product-price` |
| Hapeloglu | `Markets/Hapeloglu/` | `hapeloglu_{date}.csv` | `Product Name`, `Product Cost`, `category` |
| Marketzade | `Markets/Marketzade/` | `{date}.csv` | `item_name`, `price`, `kategori` |
| Arden | `Markets/Arden/` | `arden_urunler_{date}.csv` | `isim`, `fiyat` |
| Başkent | `Markets/Baskent/` | `baskent_{date}.csv` | `product_name`, `product_price` |
| Kale | `Markets/Kale/` | `kalemarketleri_prices_{date}.csv` | `product_name`, `product_price` |
| Kim | `Markets/Kim/` | `products{M}-{D}.csv` | column 0 (name), column 1 (price) — no header |
| Çağrı | `Markets/Cagri/` | `cagri_products_{YYYYMMDD}_*.csv` | `product_name`, `price_tl` |
| Başdaş | `Markets/Basdas/` | `basdas_fiyat_takip.csv` (cumulative) | `urun_adi`, `fiyat`, `tarih` |

### Clothing Stores (TUIK group 03 — Clothing and footwear)

| Store | Directory | File Pattern | Key Columns |
|-------|-----------|-------------|-------------|
| Civil | `ClothingStores/Civil/` | `civilim_{date}.csv` | `isim`, `fiyat` |
| Koton | `ClothingStores/Koton/` | `koton_{date}.csv` | `name`, `sale_price` |
| Lufian | `ClothingStores/Lufian/` | `lufian_urunler_{date}.csv` | `title`, `price` |
| Stradivarius | `ClothingStores/Stradivarius/` | `stradivarius_{date}.csv` | `item_name`, `price` |
| Vakko | `ClothingStores/Vakko/` | `vakko_{date}.csv` | `product-name`, `product-price` |
| adL | `ClothingStores/adL/` | `adL_{date}.csv` | `Product Name`, `Price` |
| Altınyıldız | `ClothingStores/Altınyıldız/` | `altinyildiz_tum_urunler_{date}.csv` | `urun`, `fiyat` |
| LCWaikiki | `ClothingStores/LCWaikiki/` | `LCWaikiki_{date}.csv` | `name`, `price_tl` |
| Loft | `ClothingStores/Loft/` | `loft_{date}.csv` | `Product Name`, `Price` |
| Defacto | `ClothingStores/Defacto/` | `Clothes{M}-{D}.csv` | `ProductName`, `Price` |

### Technology Products (TUIK group 08 — Information and communication)

| Store | Directory | File Pattern | Key Columns |
|-------|-----------|-------------|-------------|
| Samsung | `TechnologicalProducts/Samsung/` | `samsung_{date}.csv` | `id`, `shown_price` |
| DR | `TechnologicalProducts/DR/` | `dr_{date}.csv` | `Product Name`, `Product Cost` |
| Pozitif Teknoloji | `TechnologicalProducts/PozitifTeknoloji/` | `pozitifTeknoloji_{date}.csv` | `name`, `price` |
| Beymen Tech | `TechnologicalProducts/Beymen/` | `beymen_tech_{date}.csv` | `product-name`, `product-price` |
| Huawei | `TechnologicalProducts/Huawei/` | `huawei_{date}.csv` | `Product Name`, `Price` |

### Cosmetics (TUIK group 13 — Personal care and miscellaneous)

| Store | Directory | File Pattern | Key Columns |
|-------|-----------|-------------|-------------|
| Rossmann | `Cosmetics/Rossmann/` | `rossmann_{date}.csv` | `id`, `shown_price` |
| Avon | `Cosmetics/Avon/` | `all_products_{date}.csv` | `name`, `price` |
| Dermomarket | `Cosmetics/Dermomarket/` | `dermomarket_{date}.csv` | `item_name`, `price` |
| GoldenRose | `Cosmetics/GoldenRose/` | `goldenrose_{date}.csv` | `Product Name`, `Product Cost` |
| L'Occitane | `Cosmetics/LOccitane/` | `LOccitane_{date}.csv` | `title`, `price` |
| Watsons | `Cosmetics/Watsons/` | `watsons_{DD-MM-YYYY}.csv` | `name`, `price` |

### Home Goods (TUIK group 05 — Furnishings and household equipment)

| Store | Directory | File Pattern | Key Columns |
|-------|-----------|-------------|-------------|
| Vivense | `HomeGoods/Vivense/` | `vivense_{date}.csv` | `id`, `shown_price` |
| Karaca | `HomeGoods/Karaca/` | `karaca_{date}.csv` | `Product Name`, `Product Cost` |
| EnglishHome | `HomeGoods/EnglishHome/` | `englishhome_{date}.csv` | `item_name`, `price` |
| Bellona | `HomeGoods/Bellona/` | `Bellona_{date}.csv` | `title`, `price` |
| MadameCoco | `HomeGoods/MadameCoco/` | `madamecoco_{date}.csv` | `name`, `price` |
| Jysk | `HomeGoods/jysk/` | `jysk_prices_{date}.csv` | `urun_adi`, `fiyat` |
| İstikbal | `HomeGoods/Istikbal/` | `istikbal_{YYYY_MM_DD}.csv` | `Product Name`, `Price` |
| Chakra | `HomeGoods/Chakra/` | `chakra_all_categories_{YYYY_MM_DD}.csv` | `name`, `price` |
| IKEA | `HomeGoods/Ikea/` | `HomeGoods{M}-{D}.csv` | column 0 (name), column 1 (price) — no header |

### Construction Supplies (TUIK group 05 — Furnishings and household equipment)

| Store | Directory | File Pattern | Key Columns |
|-------|-----------|-------------|-------------|
| Bauhaus | `ConstructionSuppliesMarkets/Bauhaus/` | `bauhaus_{date}.csv` | `id`, `shown_price` |
| FiltaşYapı | `ConstructionSuppliesMarkets/FiltasYapi/` | `FiltaşYapı_{date}.csv` | `title`, `price` |
| Hausmart | `ConstructionSuppliesMarkets/Hausmart/` | `hausmart_{date}.csv` | `item_name`, `price` |
| Nalburadam | `ConstructionSuppliesMarkets/Nalburadam/` | `nalburadam_{date}.csv` | `Product Name`, `Product Cost` |
| HanCivata | `ConstructionSuppliesMarkets/HanCivata/` | `han_civata_{date}.csv` | `urun_adi`, `fiyat` |
| Nalburcuk | `ConstructionSuppliesMarkets/Nalburcuk/` | `nalburcuk_{date}.csv` | `Product Name`, `Price (TL)` |
| Nalburdayim | `ConstructionSuppliesMarkets/Nalburdayim/` | `nalburdayim_{date}.csv` | `ProductName`, `Price` |
| SanatYapi | `ConstructionSuppliesMarkets/SanatYapiOnline/` | `sanatyapionline_{date}.csv` | `Name`, `Current Price` |
| TasciYapi | `ConstructionSuppliesMarkets/TasciYapiMarket/` | `tasciyapi_products_{date}.csv` | `Product Name`, `Price` |
| Yapimaks | `ConstructionSuppliesMarkets/yapimaks/` | `{date}.csv` | `name`, `price` |
| Ereyon | `ConstructionSuppliesMarkets/Ereyon/` | `{date}_Ereyonprices.csv` | `Urun_Adi`, `Fiyat` |
| Afeks Yapı | `ConstructionSuppliesMarkets/AfeksYapiMarket/` | `ConstructionProduct{M}-{D}.csv` | `Product Title`, `Price(TL)` |

### Rent / Housing (TUIK group 04 — Housing, water, electricity, gas)

Rent data is stored at `InflationItems/Datas/HousesRent/{city_name}/{date}*.csv`. Each file contains listing-level rental prices for one city on one day. Rent is treated differently from product data (see Section 8).

---

## 3. Algorithm Overview

The computation pipeline runs in five sequential stages:

```
1. PRICE PARSING       — Convert heterogeneous string/numeric price fields to float
2. STORE LOADING       — Load each store's CSV for target date → standard 5-column frame
3. DEDUPLICATION       — Pool all stores; average prices for cross-store duplicates
4. METRIC COMPUTATION  — Merge current vs past pools; compute three inflation metrics
5. RENT INJECTION      — Compute rent price change separately; incorporate into TUIK weight
```

The result is two output files per run: a per-product detail CSV and an appended row in the summary time-series CSV.

---

## 4. Step 1 — Price Parsing

### The Problem

Prices across 47 retailers arrive in at least eight distinct string formats. A single parser must handle all of them without ambiguity. The formats encountered in the data are:

| Format Example | Interpretation | Rule Applied |
|---------------|----------------|--------------|
| `149.50` | decimal float | direct parse |
| `149,50` | Turkish decimal comma | replace `,` with `.` |
| `1.234,56` | Turkish thousands + decimal | strip `.`, replace `,` with `.` |
| `1.250.000` | Turkish multi-dot thousands | strip all `.` |
| `50.499` | ambiguous single dot + 3 digits | treat as thousands → `50499` |
| `₺149,50` or `34,99 TL` | lira prefix/suffix | strip `₺`, `TL`, `TRY` then parse |
| `"171,00 TL"` | quoted with suffix | strip quotes, then suffix rule |
| `"Başlangıç:  129.999,00 ₺"` | complex text prefix | extract longest numeric token |

### The `_parse_price` Function

```python
def _parse_price(x) -> float | None:
    if x is None: return None
    if isinstance(x, (int, float)):
        return None if pd.isna(x) else float(x)

    s = str(x).strip()
    if not s: return None

    # Strip lira symbol and TL/TRY suffix
    s = re.sub(r"₺|\bTL\b|\bTRY\b", "", s, flags=re.IGNORECASE).strip()
    # Strip trailing non-numeric characters (e.g. "/Kg")
    s = re.sub(r"[^\d.,]+$", "", s).strip()

    # If a complex prefix remains (e.g. "Başlangıç:"), extract the longest
    # contiguous numeric token — this is reliably the price, not a footnote
    if not re.match(r"^[\d.,]+$", s):
        m = re.findall(r"\d[\d,.]*\d|\d", s)
        if not m: return None
        s = max(m, key=len)   # longest token = full price with its separators

    # Resolve separator ambiguity
    if "." in s and "," in s:
        if s.index(".") < s.index(","):
            s = s.replace(".", "").replace(",", ".")   # Turkish: "1.234,56"
        else:
            s = s.replace(",", "")                    # English: "1,234.56"
    elif "," in s:
        s = s.replace(",", ".")
    elif s.count(".") > 1:
        s = s.replace(".", "")                         # "1.250.000"
    elif re.match(r"^\d+\.\d{3}$", s):
        s = s.replace(".", "")                         # "50.499" → 50499

    try:
        v = float(s)
        return v if v > 0 else None
    except ValueError:
        return None
```

### Design Notes

**Why `max(m, key=len)` instead of `m[-1]`?**  
An early version used `m[-1]` (the last token). This failed for Huawei's format `"Başlangıç:  129.999,00 ₺"`: after stripping `₺`, the regex found tokens `["129.999", "00"]` and `m[-1] = "00"` → parsed to `0.0` → filtered by the `v > 0` guard → returned `None`. The fix selects the longest token, which for any well-formed price string is always the price itself.

**Why the `^\d+\.\d{3}$` heuristic?**  
In Turkish price data, a bare string like `"50.499"` is almost always a thousands-formatted integer (50,499 TL), not a decimal fraction. An exact three-digit suffix after a single dot is therefore treated as a thousands separator. A string like `"50.49"` (two-digit suffix) is treated as a decimal.

---

## 5. Step 2 — Store Loading and Normalisation

### Generic Loader

Every store is loaded through one of two generic functions:

**`_load_csv`** — for files with a header row:
```
Parameters: fpath, name_col, price_col, store, sector, default_tuik,
            sep=",", category_col=None, tuik_mapper=None, encoding="utf-8"
Returns:    DataFrame with columns [product_key, price, tuik_category, store, sector]
            or None if the file does not exist or has no valid rows
```

**`_load_no_header`** — for files without a header row (Kim, IKEA):
```
Parameters: fpath, store, sector, default_tuik, sep=",",
            name_idx=0, price_idx=1
Returns:    same standard 5-column DataFrame or None
```

Both functions:
- Strip the UTF-8 BOM character (`﻿`) from column names — a common artefact in CSV files exported from Excel
- Apply `_parse_price` to the price column
- Drop rows where the price is null or non-positive
- Apply the TUIK category mapper if one is provided; otherwise assign the sector's default TUIK code

### Non-Standard Date File Patterns

Four date format conversion helpers handle stores that deviate from the standard `YYYY-MM-DD` file naming convention:

| Helper | Example input → output | Used by |
|--------|----------------------|---------|
| `_md(date_str)` | `2026-03-10` → `3-10` | Kim, IKEA, Defacto, AfeksYapı |
| `_underscore_date(date_str)` | `2026-05-22` → `2026_05_22` | İstikbal, Chakra |
| `_ddmmyyyy(date_str)` | `2026-05-22` → `22-05-2026` | Watsons |
| `_yyyymmdd(date_str)` | `2026-03-01` → `20260301` | Çağrı (prefix glob) |

### Special Case: Başdaş (Cumulative File)

Başdaş stores all historical data in a single file (`basdas_fiyat_takip.csv`) with a `tarih` (date) column. The loader filters rows where `tarih` starts with the target date string, which correctly handles both `2026-05-01` and any timestamp extensions like `2026-05-01 14:32:00`.

### Special Case: Çağrı (Timestamped Files)

Çağrı files are named with a timestamp suffix (e.g., `cagri_products_20260501_143215.csv`). The loader uses `glob(f"cagri_products_{_yyyymmdd(date_str)}_*.csv")` and takes the first alphabetical match, which is the earliest scrape of that day.

---

## 6. Step 3 — Cross-Store Deduplication

### Motivation

If a product (e.g., "Ariel 3 kg çamaşır deterjanı") is sold by both Migros and a second grocery store and both are included in the pool, it would contribute two rows with potentially different prices. Without deduplication, this product carries double the basket weight of a product tracked at only one store — a systematic bias that grows as more stores are added.

### Turkish Name Normalisation

Before deduplication, all product names are normalised to make cross-store name matching robust to case differences and Turkish diacritics:

```python
_TR_MAP = str.maketrans("ıİğĞşŞçÇöÖüÜ", "iIgGsScCoOuU")

def _norm(s: str) -> str:
    if not isinstance(s, str): return ""
    return re.sub(r"\s+", " ", s.translate(_TR_MAP).lower().strip())
```

The translation table maps each Turkish-specific character to its ASCII base letter (e.g., `ı` → `i`, `İ` → `I`, `ğ` → `g`). After translation, the name is lowercased and whitespace-collapsed. This means `"Ariel 3 KG Çamaşır"` and `"ARİEL 3 kg camasir"` both normalise to `"ariel 3 kg camasir"`.

### Deduplication Rule

Products are grouped by `(normalised_name, tuik_category, sector)`. Within each group:
- `product_key` — the first observed canonical name is kept
- `price` — the **mean** price across all stores in the group
- `store` — a sorted, comma-joined list of all contributing stores (for traceability)

```python
deduped = (
    combined
    .groupby(["_norm_key", "tuik_category", "sector"], as_index=False)
    .agg(
        product_key=("product_key", "first"),
        price=("price", "mean"),
        store=("store", lambda s: ",".join(sorted(s.unique()))),
    )
)
```

Averaging prices (rather than taking one store's price) serves two purposes: (1) it prevents the specific store chosen for the canonical price from having undue influence, and (2) it reflects the average cost a consumer faces across stores.

### When Deduplication Fires

In practice, deduplication collapses relatively few rows, because most stores carry distinct product catalogues. The dominant driver of raw vs. deduplicated count differences is not cross-store duplicates but rather near-identical product variant listings within a single store (e.g., the same phone in two memory configurations). These are collapsed if and only if their normalised names are identical after the Turkish normalisation step.

---

## 7. Step 4 — Inflation Metric Computation

### Matching Current and Past Data

For each time interval (15-day, 30-day), the past date's deduplicated pool is loaded independently through the same pipeline. The current and past pools are then merged on `(product_key, tuik_category, sector)` — the canonical deduplicated keys — using a left join so that new products (present only in the current pool) are included but contribute `NaN` to the inflation calculation.

### Metric 1 — Per-Product Basic Inflation

For each matched product:

```
basic_inflation_i = (price_current_i − price_past_i) / price_past_i × 100
```

Products present in the current pool but absent from the past pool receive `NaN`. Products with a past price of zero are excluded (produce `±∞`, which are replaced with `NaN`).

### Metric 2 — Average Inflation

The arithmetic mean of all per-product basic inflation values, across all matched products and all sectors:

```
avg_inflation = (1 / N) × Σ basic_inflation_i
```

where N is the number of products with a valid (non-NaN) inflation figure.

This is the simplest metric. It treats every tracked product equally regardless of how much consumers spend on it.

### Metric 3 — Basic Inflation Index (Basket-Level)

A Laspeyres-style price ratio at the basket level:

```
basic_index = (Σ price_current_i − Σ price_past_i) / Σ price_past_i × 100
```

The summation runs over matched products only (those present on both dates with valid prices). Unlike the average inflation metric, this gives implicit weight proportional to price level: a 10,000 TL phone contributes more to the index than a 10 TL spice, even if both rose by the same percentage.

### Metric 4 — TUIK-Weighted Average (Product Categories)

Products are grouped by their assigned TUIK COICOP 2-digit code. The mean inflation within each category is computed, and these category means are combined using TÜİK 2026 basket weights — normalised to the categories actually present in the data:

```
# Step 1: category means
cat_avg[c] = mean(basic_inflation_i  for all i in category c)

# Step 2: normalise weights to present categories only
norm_w[c] = TUIK_WEIGHTS[c] / Σ_{c' in present} TUIK_WEIGHTS[c']  × 100

# Step 3: weighted sum
tuik_weighted = Σ_c  cat_avg[c] × norm_w[c] / 100
```

Normalising weights to the present categories ensures the weighted average sums correctly even when some TUIK groups are not represented in the data. For example, if only food (01) and clothing (03) are present, their combined raw weights are 24.44 + 7.90 = 32.34; the normalised weights become 75.6% and 24.4% respectively, and the weighted average equals these rescaled proportions.

### Metric 5 — TUIK-Weighted Average Including Rent

Rent (TUIK group 04) is not product-level data and cannot be included in the product-pool merge. Instead, after computing `tuik_weighted_products`, the rent inflation figure is injected as an additional category:

```python
cat_avg_full = cat_avg_products.copy()
cat_avg_full["04"] = rent_inf          # inject rent as group 04
norm_w_all = normalised_weights(list(cat_avg_full.index))
tuik_weighted_full = Σ_c cat_avg_full[c] × norm_w_all[c] / 100
```

This produces `tuik_weighted_full`, which incorporates housing costs (11.40% of the TÜİK basket) into the weighted average.

---

## 8. Step 5 — Rent Inflation (TUIK Group 04)

### Data Structure

Rent data is stored per city, not per product. Each city directory under `HousesRent/` contains one file per date with individual rental listing prices. There is no product identifier to match across dates.

### Composition Bias Problem

A naive implementation might compute:

```
rent_inflation = mean_price(current_date) / mean_price(past_date) − 1
```

But this approach is biased when the set of cities present on the two dates is different. If high-rent cities (e.g., Istanbul metropolitan areas) are available on one date but not the other, the national mean changes due to city composition rather than actual rent movement. This is a composition bias, analogous to the index number problem in price index theory.

### Solution: Common-City Mean

The implementation restricts both the current and past means to the intersection of cities that have data on **both** dates:

```python
cur_city  = {city: mean_price(city, current_date) for city in cities_with_data(current_date)}
past_city = {city: mean_price(city, past_date)    for city in cities_with_data(past_date)}
common    = set(cur_city) & set(past_city)

mean_cur  = mean(cur_city[c]  for c in common)
mean_past = mean(past_city[c] for c in common)
rent_inflation = (mean_cur − mean_past) / mean_past × 100
```

Within each city, the mean is taken across all listings in that city's file. The city-level means are then averaged equally across the common set (unweighted by city size, which is a known limitation — see Section 14).

### Bug Discovered During Development

An early version computed `mean(all_current_city_prices)` vs `mean(all_past_city_prices)` without restricting to common cities. For the 30-day interval on 2026-05-01 vs 2026-04-01:
- April 1 had 22 cities including several high-rent Istanbul-area cities
- May 1 had 18 cities, missing 4 high-rent cities
- This caused April's mean to appear artificially inflated (51K TL vs a true 27K TL), producing a spurious 8.95% rent inflation figure

After restricting to the 18 cities common to both dates, the figure corrected to **3.22%** — consistent with observed market trends.

---

## 9. TUIK COICOP 2026 Basket Weights

All weights are from the official TÜİK TÜFE 2026 publication with base year 2025 = 100. These are hardcoded in `Inflations/Codes/tuik_config.py`.

| COICOP Code | Category (Turkish) | Category (English) | Weight (%) | Tracked? |
|------------|-------------------|--------------------|-----------|---------|
| 01 | Gıda ve alkolsüz içecekler | Food and non-alcoholic beverages | 24.4444 | Yes — Grocery |
| 02 | Alkollü içecekler, tütün | Alcoholic beverages, tobacco | 2.7549 | No |
| 03 | Giyim ve ayakkabı | Clothing and footwear | 7.9038 | Yes — Clothing |
| 04 | Konut, su, elektrik, gaz | Housing, water, electricity, gas | 11.4020 | Yes — Rent (partial) |
| 05 | Mobilya, mefruşat ve ev ekipmanları | Furnishings and household equipment | 7.9201 | Yes — HomeGoods + Construction |
| 06 | Sağlık | Health | 2.7923 | No |
| 07 | Ulaştırma | Transport | 16.6169 | No |
| 08 | Bilgi ve iletişim | Information and communication | 3.1035 | Yes — Tech |
| 09 | Eğlence, dinlence, spor ve kültür | Recreation, sport and culture | 4.3382 | No |
| 10 | Eğitim hizmetleri | Education services | 2.0215 | No |
| 11 | Lokantalar ve konaklama | Restaurants and accommodation | 11.1349 | No |
| 12 | Sigorta ve finansal hizmetler | Insurance and financial services | 1.0740 | No |
| 13 | Kişisel bakım ve diğer | Personal care and miscellaneous | 4.4935 | Yes — Cosmetics |
| **TOTAL** | | | **100.00** | |

**Tracked weight coverage:** Groups 01 + 03 + 04 + 05 + 08 + 13 = 55.27% of the full basket. The TUIK-weighted metric normalises over present categories, so it is internally consistent but represents only the tracked portion of household expenditure.

---

## 10. TUIK Category Mapping Per Store

Stores with rich category data use keyword-based mappers to assign sub-categories. Most grocery and sector-uniform stores default to their sector's TUIK code.

### Migros Category Mapper

Migros product names are matched against keyword lists (Turkish) to redirect non-food items to their correct TUIK group. Examples:

- Products containing "Şampuan", "Deodorant", "Parfüm" → group 12 (Personal care, note: remapped to 13 in later normalisation)
- Products containing "Deterjan", "Tencere", "Süpürge" → group 05 (Furnishings)
- Products containing "Kitap", "Oyuncak", "Spor" → group 09 (Recreation)
- Products containing "Telefon", "Tablet", "HDMI" → group 08 (Tech)
- Default → group 01 (Food)

### A101 Category Mapper

A101's `ana_kategori` column is a short Turkish category slug. It is mapped by checking for keyword presence in the lowercased value:

- Keywords "meyve", "et", "süt", "gıda", etc. → group 01
- Keywords "temizlik", "kağıt" → group 05
- Keywords "kişisel", "bebek", "sağlık" → group 12
- Keyword "elektronik" → group 08

### Hapeloglu, Gurmar, Marketzade

These stores' category columns are mapped via lookup dictionaries — exact string matches between the category field and a predefined dictionary. Unmapped categories fall back to group 01 (Food) as a conservative default given these are grocery stores.

---

## 11. Output Files

### Per-Product Detail CSV

**Path:** `Inflations/Datas/Final_Reports/turkey_inflation_{YYYY-MM-DD}.csv`

One row per deduplicated product. Columns:

| Column | Description |
|--------|-------------|
| `product_key` | Canonical product name (first observed spelling across stores) |
| `price` | Current price after deduplication (mean if multi-store) |
| `tuik_category` | TUIK 2-digit COICOP group code |
| `store` | Comma-separated list of contributing stores |
| `sector` | Internal sector label (market, clothing, tech, etc.) |
| `basic_inflation_15d` | % price change vs 15 days ago (NaN if not matched) |
| `basic_inflation_30d` | % price change vs 30 days ago (NaN if not matched) |

### Summary Time-Series CSV

**Path:** `Inflations/Datas/Final_Reports/turkey_inflation_summary.csv`

One row per run date. Existing rows for the same date are replaced (idempotent). Columns:

| Column | Description |
|--------|-------------|
| `date` | Target date (YYYY-MM-DD) |
| `n_stores` | Number of stores with data on this date |
| `n_products_raw` | Total product rows before deduplication |
| `n_products_deduped` | Unique product rows after deduplication |
| `avg_inflation_15d` | Arithmetic mean of per-product inflation (15-day) |
| `basic_index_15d` | Basket-level sum ratio (15-day) |
| `tuik_weighted_products_15d` | TUIK-weighted average, product data only (15-day) |
| `tuik_weighted_full_15d` | TUIK-weighted average including rent (15-day) |
| `rent_inflation_15d` | Mean rent change across common cities (15-day) |
| `avg_inflation_30d` | Same metrics for 30-day interval |
| `basic_index_30d` | |
| `tuik_weighted_products_30d` | |
| `tuik_weighted_full_30d` | |
| `rent_inflation_30d` | |

---

## 12. Validation and Cross-Checks

### Cross-check 1: Migros Standalone vs Turkey Output

The most direct validation: filter the Turkey output to Migros-only rows and recompute the average inflation. The result should match Migros's own per-store summary CSV exactly.

**Result (30-day interval, 2026-05-01 vs 2026-04-01):**

| Source | avg_inflation_30d |
|--------|-----------------|
| Migros standalone (`migros_inflation_summary.csv`) | 4.270640 |
| Turkey output, Migros-only rows | 4.270640 |

Exact match to 6 decimal places, confirming identical methodology.

### Cross-check 2: March 1 Returns All NaN

The project began collecting data on approximately 2026-02-24. The 15-day look-back from 2026-03-01 falls on 2026-02-14 and the 30-day falls on 2026-01-30 — both before any data exists. The script correctly returns `NaN` for all metrics on March 1, with 8 stores loaded and 40,742 deduplicated products recorded but no comparison possible.

### Cross-check 3: Match Rate Analysis

For the 30-day interval on 2026-05-01 (current) vs 2026-04-01 (past):
- Raw match rate: ~57% of current products matched a past product
- 30 stores were active on May 1 vs 22 on April 1 — 8 new stores contributed entirely new products with no past counterpart
- For stores present on both dates: ~86.2% match rate, consistent with seasonal catalogue churn in clothing and construction

### Bug Fix Log

Two bugs were discovered and fixed during validation:

**Bug 1 — `_parse_price` selecting wrong token for complex prefix prices**

- Input: `"Başlangıç:  129.999,00 ₺"` (Huawei price format)
- Original: `re.findall(r"[\d]+[.,]?[\d]*", s)` → `["129.999", "00"]`, then `m[-1]` = `"00"` → `0.0` → filtered → `None`
- Fixed: regex changed to `r"\d[\d,.]*\d|\d"` (matches full numeric tokens including internal separators), selection changed to `max(m, key=len)` → `"129.999,00"` → `129999.0`

**Bug 2 — Composition bias in rent calculation**

- Original: computed national mean from all cities present on each date independently
- Effect: April's mean was 51K TL (22 cities, including high-rent cities absent in May), May's was 55K TL (18 cities), giving a spurious 8.95%
- Fixed: restrict both dates' means to the intersection of cities present on both dates
- Result after fix: 3.22% (18 common cities, both dates from the same city set)

---

## 13. Results

### Summary Table (2026 Monthly Snapshots)

| Date | Stores | Products (raw) | Products (deduped) | avg_inf_15d | basic_idx_15d | tuik_w_full_15d | avg_inf_30d | basic_idx_30d | tuik_w_full_30d | rent_inf_30d |
|------|--------|---------------|-------------------|------------|--------------|-----------------|------------|--------------|-----------------|-------------|
| 2026-03-01 | 8 | 42,453 | 40,742 | — | — | — | — | — | — | — |
| 2026-04-01 | 22 | 154,092 | 140,007 | 2.19% | 0.68% | 1.69% | 2.81% | 0.44% | 2.92% | 4.19% |
| 2026-05-01 | 30 | 215,857 | 192,840 | 1.55% | −0.23% | 2.42% | 1.95% | −0.33% | 3.89% | 3.22% |

All percentages are month-on-month changes.

### Interpretation Notes

- **Basic index vs. average inflation diverge**: The basic index (sum ratio) is pulled toward zero or negative by the largest-price items (furniture, electronics), which may have had price reductions. The average inflation (arithmetic mean over products) treats each item equally, so is more sensitive to small-price everyday items, which tend to rise faster in high-inflation environments.

- **TUIK-weighted full > TUIK-weighted products**: The rent component (groups 04, weight 11.40%) has been rising consistently at 3–4%, and when incorporated into the weighted average it raises the composite figure above the product-only estimate.

- **Store expansion effect**: Between March 1 and May 1, the panel grew from 8 to 30 stores. This expansion increases the raw product count 5x and the deduplicated count ~4.7x. Inflation metrics should not be compared across dates where the panel composition differs significantly (such as March 1 to April 1); comparisons are more meaningful within stable panels.

---

## 14. Known Limitations

### 14.1 Coverage Gap (44.73% of basket untracked)

The seven TUIK groups not tracked — transport (07, 16.6%), restaurants (11, 11.1%), health (06, 2.8%), recreation (09, 4.3%), education (10, 2.0%), tobacco (02, 2.8%), and insurance (12, 1.1%) — together represent 44.73% of the household basket. The TUIK-weighted average is normalised only over present categories. This means the reported weighted figure reflects the tracked sectors' behaviour and should not be interpreted as a full CPI estimate.

### 14.2 Rent City Weighting

In the rent calculation, all cities are given equal weight in the mean. Istanbul, with a far larger rental market and higher price level than smaller cities, should arguably receive greater weight. City-population-weighted rent aggregation is not currently implemented.

### 14.3 Product Matching Across Dates

Products are matched by their normalised canonical name. If a store renames a product between the current and past date (e.g., reformulation, size change), it will appear as a new product and the old listing will have no current match — both are excluded from inflation computation. This is conservative (no inflation attributed) but may undercount price changes due to package size reductions (shrinkflation).

### 14.4 Panel Stability

The set of stores providing data changes over time as new scrapers are added. Inflation figures computed across dates when the panel differs substantially should be interpreted with caution.

### 14.5 Online Prices Only

All tracked prices are from online retail listings. These may differ from in-store prices and do not capture informal markets, wet markets (for fresh produce), or negotiated prices.

---

## 15. Usage

```bash
# Compute inflation for today (15d and 30d intervals)
python Inflations/Codes/turkey_inflation.py

# Compute inflation for a specific historical date
python Inflations/Codes/turkey_inflation.py --date 2026-05-01

# Compute inflation between two arbitrary dates
python Inflations/Codes/turkey_inflation.py --date 2026-05-01 --compare 2026-03-15

# Enable detailed logging
python Inflations/Codes/turkey_inflation.py --date 2026-05-01 2>&1 | tee run.log
```

Outputs are written to `Inflations/Datas/Final_Reports/`. The summary CSV is appended idempotently: re-running for the same date replaces the existing row rather than duplicating it.
