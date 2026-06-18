# Turkey-Wide Inflation Calculator — Methodology

**Script:** `turkey_inflation.py`  
**Data root:** `InflationItems/Datas/`  
**Output:** `Inflations/Datas/Final_Reports/`  
**Base:** TÜİK COICOP 2018, basket year 2025=100

---

## Overview

`turkey_inflation.py` aggregates daily scraped price data from 100+ Turkish retail stores across 9 sectors and computes the following inflation metrics:

| Metric                       | Description                                                                                             |
| ---------------------------- | ------------------------------------------------------------------------------------------------------- |
| **Basic Inflation**          | Basket-level price index change: `(Σ current prices / Σ past prices − 1) × 100`                         |
| **Average Inflation**        | Arithmetic mean of per-product percentage changes                                                       |
| **Median Inflation**         | Median of per-product percentage changes (typically 0%, see below)                                      |
| **Median Inflation (Nonzero)** | Median percentage change among only the products whose price actually changed                        |
| **% Increased / Decreased / Unchanged** | Share of matched products whose price went up, down, or stayed the same                    |
| **TÜİK Weighted (Products)** | Category-level weighted average using TÜİK COICOP 2026 basket weights, normalised to covered categories |
| **TÜİK Weighted (Full)**     | Same as above but includes rent (group 04) injected from housing data                                   |

> **Note on Median Inflation:** In practice, `median_inflation` is **0.0% in nearly every period**, because 76–87% of tracked SKUs show no price change between monthly snapshots — most stores do not reprice every item every month. This is a structural property of the data, not a bug. `median_inflation_nonzero` and the `pct_increased`/`pct_decreased`/`pct_unchanged` breakdown are reported alongside it to give a meaningful picture of repricing behaviour: the median magnitude of change *when a change occurs*, and how common changes actually are.

Metrics are computed for **15-day** and **30-day** intervals by default. A custom comparison date can be passed via `--compare`, in which case all interval-suffixed columns use the generic `compare` label and the comparison date is recorded separately in the `compare_date` column.

---

## TÜİK COICOP 2026 Basket Weights

Source: TÜİK TÜFE 2026, base year 2025=100.

| Code | Category (TR)                              | Category (EN)                       | Weight (%) | Covered       |
| ---- | ------------------------------------------ | ----------------------------------- | ---------- | ------------- |
| 01   | Gıda ve alkolsüz içecekler                 | Food and non-alcoholic beverages    | 24.44      | ✓             |
| 02   | Alkollü içecekler, tütün ve tütün ürünleri | Alcoholic beverages and tobacco     | 2.75       | ✗             |
| 03   | Giyim ve ayakkabı                          | Clothing and footwear               | 7.90       | ✓             |
| 04   | Konut, su, elektrik, gaz ve diğer yakıtlar | Housing, water, electricity, gas    | 11.40      | ✓ (rent only) |
| 05   | Mobilya, mefruşat ve ev ekipmanları        | Furnishings and household equipment | 7.92       | ✓             |
| 06   | Sağlık                                     | Health                              | 2.79       | ✓ (monthly)   |
| 07   | Ulaştırma                                  | Transport                           | 16.62      | ✗             |
| 08   | Bilgi ve iletişim                          | Information and communication       | 3.10       | ✓             |
| 09   | Eğlence, dinlence, spor ve kültür          | Recreation, sport and culture       | 4.34       | ✗             |
| 10   | Eğitim hizmetleri                          | Education services                  | 2.02       | ✗             |
| 11   | Lokantalar ve konaklama hizmetleri         | Restaurants and accommodation       | 11.13      | ✓             |
| 12   | Sigorta ve finansal hizmetler              | Insurance and financial services    | 1.07       | ✗             |
| 13   | Kişisel bakım, sosyal koruma ve diğer      | Personal care and miscellaneous     | 4.49       | ✓             |

**Maximum achievable basket coverage:** ~73% (groups 01+03+04+05+06+08+11+13).  
Uncovered groups (02, 07, 09, 10, 12) lack scraped data sources.

When TÜİK Weighted metrics are computed, weights are **re-normalised** to sum to 100% across only the groups present in the data for that run.

---

## Data Sources by Sector

### Group 01 — Food & Non-Alcoholic Beverages (`Markets/`)

Daily scrape frequency.

| Store                  | Notes                           |
| ---------------------- | ------------------------------- |
| A101                   | National discount chain         |
| Arden                  | Regional market                 |
| Basdas                 | Regional market                 |
| Baskent                | Regional market                 |
| BizimMarket            | National chain                  |
| Cagri                  | Regional market                 |
| CarrefourSA            | National hypermarket            |
| Gurmar                 | Regional market                 |
| Hapeloglu              | Online grocery                  |
| HappyCenter            | Regional market                 |
| Ideal                  | Regional market                 |
| Kale                   | Regional market                 |
| Kim                    | Regional market                 |
| Macrocenter            | Premium supermarket             |
| Marketzade             | Online market                   |
| Migros                 | National supermarket chain      |
| Mopas                  | Regional market                 |
| Onur                   | Regional market                 |
| Sariyer                | Regional market                 |
| SozSanal               | Online market                   |
| Tarım Kredi Kooperatif | Agricultural cooperative market |
| sehzade                | Regional market                 |
| sok_market             | National discount chain         |

---

### Group 03 — Clothing & Footwear (`ClothingStores/`)

Daily scrape frequency.

| Store        | Notes                                |
| ------------ | ------------------------------------ |
| Altınyıldız  | Men's fashion                        |
| Avva         | Men's fashion                        |
| Bershka      | Fast fashion (Inditex)               |
| Civil        | Denim & casual                       |
| Colins       | Denim & casual                       |
| Defacto      | National fast fashion                |
| H&M          | International fast fashion           |
| Koton        | National fashion chain               |
| LCWaikiki    | National mass-market fashion         |
| Loft         | Mid-range fashion                    |
| Lufian       | Premium casual                       |
| Mudo         | Mid-range lifestyle                  |
| PullandBear  | Fast fashion (Inditex)               |
| Stradivarius | Fast fashion (Inditex)               |
| Vakko        | Luxury fashion                       |
| Zara         | International fast fashion (Inditex) |
| adL          | Casual fashion                       |
| addax        | Casual fashion                       |
| beymenclub   | Premium casual                       |

> **Note:** EnglishHome (HomeGoods) is permanently excluded from calculations due to highly volatile flash-sale pricing that creates systematic distortion (40%+ of matched products showing >50% price swings within 15 days).

---

### Group 05 — Furnishings & Household Equipment

Two sub-sectors both mapped to COICOP 05.

#### `HomeGoods/` — Home Furnishings

Daily scrape frequency.

| Store      | Notes                      |
| ---------- | -------------------------- |
| Bellona    | Furniture chain            |
| Chakra     | Home décor                 |
| Ikea       | International furniture    |
| Istikbal   | National furniture chain   |
| Karaca     | Kitchen & home accessories |
| LCW Home   | Home textiles              |
| MadameCoco | Home textiles & décor      |
| Vivense    | Online furniture           |
| jysk       | Scandinavian home goods    |
| tcshbo     | Home goods                 |

#### `ConstructionSuppliesMarkets/` — Hardware & Building Materials

Daily scrape frequency.

| Store           | Notes                   |
| --------------- | ----------------------- |
| AfeksYapiMarket | Online hardware         |
| Bauhaus         | International DIY chain |
| Ereyon          | Online hardware         |
| FiltasYapi      | Construction supplies   |
| HanCivata       | Fasteners & hardware    |
| Hausmart        | Online hardware         |
| LoyaMakina      | Machinery & tools       |
| Nalburadam      | Hardware market         |
| Nalburcuk       | Hardware market         |
| Nalburdayim     | Hardware market         |
| Nalburtek       | Hardware market         |
| SanatYapiOnline | Construction supplies   |
| TasciYapiMarket | Building materials      |
| Yapıyoz         | Online hardware         |
| yapimaks        | Hardware market         |

---

### Group 06 — Health (`Health/`)

**Monthly** scrape frequency (matched by `YYYY-MM` date token).

| Store                          | Notes                       |
| ------------------------------ | --------------------------- |
| Dentist                        | Dental service prices       |
| Diagnostic & Surgical Services | Diagnostic procedure prices |
| Doctor                         | General practitioner fees   |
| Medicine & Glasses & Lenses    | Pharmacy & optical prices   |
| Physical_Therapy               | Physiotherapy session fees  |

---

### Group 08 — Information & Communication (`TechnologicalProducts/`)

Daily scrape frequency.

| Store            | Notes                           |
| ---------------- | ------------------------------- |
| Beymen           | Premium electronics             |
| DR               | Books, electronics & multimedia |
| Huawei           | Brand store                     |
| Koçtaş           | DIY & electronics               |
| PozitifTeknoloji | Apple reseller                  |
| Samsung          | Brand store                     |
| Teknoraks        | Consumer electronics            |
| Vatan Computer   | National electronics chain      |
| Xiaomi           | Brand store                     |

---

### Group 11 — Restaurants & Accommodation

Two sub-sectors both mapped to COICOP 11.

#### `TravelTourism/` — Travel & Accommodation

Daily scrape frequency.

| Store           | Notes                      |
| --------------- | -------------------------- |
| HajjUmrah       | Pilgrimage package prices  |
| HolidayPackages | Package holiday prices     |
| Hotels          | Hotel accommodation prices |

#### `RestaurantMealPricesVenueHallRentalFees/` — Restaurant & Venue Prices

Daily scrape frequency. Files sit directly in the sector root (no store subdirectories); each file's name prefix is used as the source identifier.

| Source                                | Notes                                  |
| ------------------------------------- | -------------------------------------- |
| menufiyati_com_tr                     | Restaurant menu prices aggregator      |
| menufiyati_tr                         | Restaurant menu prices aggregator      |
| menufiyatlar                          | Restaurant menu prices aggregator      |
| menufiyatlistesi                      | Restaurant menu prices aggregator      |
| duguncom_dugun_mekanlari_istanbul     | Wedding venue prices (Istanbul)        |
| duguncom_dugun_salonlari_istanbul     | Wedding hall prices (Istanbul)         |
| duguncom_kir_dugunu_istanbul          | Garden wedding venue prices (Istanbul) |
| duguncom_soz_nisan_mekanlari_istanbul | Engagement venue prices (Istanbul)     |
| dugunbuketi_dugun_mekanlari_istanbul  | Wedding venue prices (Istanbul)        |
| dugunbuketi_dugun_salonlari_istanbul  | Wedding hall prices (Istanbul)         |

---

### Group 13 — Personal Care (`Cosmetics/`)

Daily scrape frequency.

| Store        | Notes                          |
| ------------ | ------------------------------- |
| Avon         | Direct-sales cosmetics          |
| Beymen Beauty | Premium cosmetics retailer      |
| Boyner       | Department store cosmetics      |
| Dermomarket  | Pharmacy / dermo-cosmetics       |
| GoldenRose   | Mass-market cosmetics            |
| Gratis       | National drugstore chain         |
| L'Occitane   | International premium cosmetics |
| M&S          | Department store cosmetics       |
| Pazarium     | Online cosmetics                 |
| Rossmann     | International drugstore chain    |
| Watsons      | International drugstore chain    |

---

### Group 04 — Housing / Rent (`HousesRent/`) — Special Handling

Rent data is **not** processed through the standard product pipeline. Instead:

1. For each run date, the mean rent listing price is computed per city/district from all scraped files matching that date.
2. The same is done for the comparison date.
3. Rent inflation is computed as the **Carli index across cities**: arithmetic mean of `(mean_rent_city_t / mean_rent_city_0 − 1) × 100` over all cities present in both snapshots. Each city receives equal weight regardless of population or market size. If fewer than **3** cities are common to both dates, a warning is logged noting the result may not be representative, but the figure is still computed.
4. This single figure is injected into the **TÜİK Weighted (Full)** metric as group 04. Weights are re-normalised to include group 04 alongside the tracked product categories.
5. Rent does **not** appear in Basic Inflation, Average Inflation, or TÜİK Weighted (Products), which are product-level metrics only.

**44 city/district coverage:**

Adana, Ağrı, Ankara, Antalya, Antep, Ardahan, BalıkesirManisaUşakAfyonkarahisar, Batman, Bilecik, Burdur, Bursa, Çankırı, Çorum, Diyarbakır, Düzce/Kocaeli/Sakarya, ErzurumErzincanBayburt, Eskişehir/Bolu/Bartın/Zonguldak, Giresun, Iğdır, Isparta, İstanbul (Avrupa), İzmir, Kastamonu, Kayseri, Kilis, Kırıkkale, Kırşehir, Kütahya, Malatya/Elazığ/Tunceli, Maraş, Mardin, Mersin, Muğla/Denizli/Aydın, Ordu, Samsun, Şanlıurfa, Şırnak, Siirt, Sinop, Sivas, Tokat, Trabzon/Rize/Artvin/Gümüşhane, VanBitlisMusHakkari, Yalova

---

## Computation Pipeline

```
Raw CSVs (per store, per date)
        │
        ▼
_load_store_csv()          — parse prices, normalise Turkish characters
        │
        ▼
_load_sector() / _load_flat_sector()   — discover files by date token
        │
        ▼
_load_all_stores()         — concat all sectors; Stage 1 dedup: average
                              duplicate rows within each (store, product, sector)
        │
        ▼
merge(current, past)       — inner join on (store, canonical_key, tuik_category, sector)
        │
        ▼
Outlier filter             — nullify relative AND prices for |change| > 80%
        │
        ▼
Stage 2 dedup (cross-store) — average prices and relatives across stores for
                              each (canonical_key, tuik_category, sector)
        │
        ▼
Stage 3 dedup (cross-sector) — collapse same canonical_key × tuik_category
                              across sectors (e.g. HomeGoods + Construction → 05)
        │
        ▼
_compute_metrics()         — basic_index (Dutot), avg_inflation (Carli),
                              median_inflation, median_inflation_nonzero,
                              pct_increased/decreased/unchanged,
                              tuik_weighted_products
        │
        ▼
_rent_relative()           — Carli across cities; injected as group 04
                              → tuik_weighted_full
        │
        ▼
Output CSVs
```

---

## Deduplication

Deduplication runs in three stages, all keyed on the normalised product name (Turkish diacritics stripped, lowercased, whitespace collapsed):

**Stage 1 — within store:** Duplicate rows for the same product in one store's CSV are collapsed to a single row by averaging prices.

**Stage 2 — cross-store:** After matching current and past snapshots, products appearing in multiple stores within the same sector are averaged across stores (equal store weight). This produces one price and one relative per `(canonical_key, tuik_category, sector)` triplet.

**Stage 3 — cross-sector:** Some sectors share a TUIK category (HomeGoods and ConstructionSupplies both map to group 05). After stage 2, rows are further collapsed across sectors within the same `(canonical_key, tuik_category)` pair, again by simple averaging. This prevents the same physical product from being counted twice in the basket sum or the weighted index.

---

## Outlier Filter

Price changes with `|relative change| > 80%` within a single comparison interval are excluded before metric computation. This filters out scraping errors (e.g. prices recorded at 10× scale on a given date) without affecting genuine large but plausible price movements. Both the relative and the underlying current/past prices are nullified for excluded rows, so outlier products do not bias the Dutot (basket-sum) index either. Excluded pair counts are logged per run.

The threshold is defined as `_OUTLIER_THRESHOLD = 80.0` at module level for reproducibility. Sensitivity analyses can be run by adjusting this constant (±20 pp).

---

## Output Files

### `turkey_inflation_{YYYY-MM-DD}.csv`

One row per unique `(canonical_key, tuik_category, sector)` triplet found on the target date.

| Column          | Description                                               |
| --------------- | --------------------------------------------------------- |
| `canonical_key` | Normalised product name (deduplication key)               |
| `product_key`   | Original product name                                     |
| `tuik_category` | COICOP 2-digit code                                       |
| `sector`        | Internal sector label                                     |
| `store`         | All store names carrying this product on the current date, comma-separated |
| `relative_{label}` | Cross-sector-averaged % price change vs the comparison date. `{label}` is `15d`/`30d` in default mode, or `compare` when run with `--compare`. NaN if the product had no match on the comparison date. |

### `turkey_inflation_summary.csv`

Time series, sorted by `date`. One row per `(date, compare_date)` pair. When a row with the same `(date, compare_date)` is re-computed, it replaces the existing row; runs with the same target date but a different comparison date produce separate rows.

Interval-suffixed columns use `{label}` = `15d`/`30d` in default mode, or `compare` when run with `--compare` (with the actual comparison date recorded in `compare_date`).

| Column Group                    | Columns                                                                                                              |
| ------------------------------- | -------------------------------------------------------------------------------------------------------------------- |
| **Date & coverage**             | `date`, `compare_date`, `n_stores`, `n_products_raw`, `n_products_deduped`, `basket_coverage_pct`, `basket_coverage_full_pct` |
| **Store counts per category**   | `n_stores_01`, `n_stores_03`, `n_stores_04`, …                                                                       |
| **Product counts per category** | `n_products_01`, `n_products_03`, …                                                                                  |
| **Overall metrics per interval** | `avg_inflation_{label}`, `median_inflation_{label}`, `median_inflation_nonzero_{label}`, `pct_increased_{label}`, `pct_decreased_{label}`, `pct_unchanged_{label}`, `basic_index_{label}`, `tuik_weighted_products_{label}`, `tuik_weighted_full_{label}`, `n_products_matched_{label}` |
| **Per-category metrics**        | `avg_inflation_{code}_{label}`, `median_inflation_{code}_{label}`, `median_inflation_nonzero_{code}_{label}`, `basic_index_{code}_{label}` for each covered TÜİK code; `rent_inflation_04_{label}` when rent data is available |

---

## Usage

```bash
# Today, 15-day and 30-day intervals
python turkey_inflation.py

# Specific target date
python turkey_inflation.py --date 2026-05-01

# Specific target date with a custom comparison date
python turkey_inflation.py --date 2026-05-01 --compare 2026-04-01
```

---

## Known Limitations

| Limitation                                                     | Impact                                                                         |
| -------------------------------------------------------------- | ------------------------------------------------------------------------------ |
| Groups 02, 07, 09, 10, 12 not covered                          | Max basket coverage ~73% (`basket_coverage_full_pct`); TÜİK weighted metric re-normalises to covered groups. `basket_coverage_pct` reports product-only coverage (excludes group 04 rent); `basket_coverage_full_pct` includes group 04 when city-level rent data is present |
| EnglishHome excluded (flash-sale volatility)                   | HomeGoods sector coverage reduced                                              |
| Rent covers listing prices only, not actual transaction prices | Group 04 is an approximation                                                   |
| Health data is monthly, not daily                              | Group 06 may lag by up to 30 days                                              |
| Scraper availability varies by day                             | Low-data days (fewer stores) produce less reliable estimates                   |
| Restaurant data currently limited to Istanbul venues           | Group 11 has geographic bias                                                   |
| Most SKUs are unchanged month-to-month                         | `median_inflation` is ~0% in nearly every period; use `median_inflation_nonzero` and `pct_increased`/`pct_decreased`/`pct_unchanged` instead for distributional insight |
| `InflationItems/Datas/PublicTransportation/` exists but is not wired into `_SECTOR_CONFIG` | Group 07 (Transport) remains uncovered despite some scraped data being available |
