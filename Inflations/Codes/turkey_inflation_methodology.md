# Turkey-Wide Inflation Calculator — Methodology

**Script:** `turkey_inflation.py`  
**Data root:** `InflationItems/Datas/`  
**Output:** `Inflations/Datas/Final_Reports/`  
**Base:** TÜİK COICOP 2018, basket year 2025=100

---

## Overview

`turkey_inflation.py` aggregates daily scraped price data from 100+ Turkish retail stores across 9 sectors and computes three inflation metrics:

| Metric | Description |
|---|---|
| **Basic Inflation** | Basket-level price index change: `(Σ current prices / Σ past prices − 1) × 100` |
| **Average Inflation** | Arithmetic mean of per-product percentage changes |
| **TÜİK Weighted (Products)** | Category-level weighted average using TÜİK COICOP 2026 basket weights, normalised to covered categories |
| **TÜİK Weighted (Full)** | Same as above but includes rent (group 04) injected from housing data |

Metrics are computed for **15-day** and **30-day** intervals by default. A custom comparison date can be passed via `--compare`.

---

## TÜİK COICOP 2026 Basket Weights

Source: TÜİK TÜFE 2026, base year 2025=100.

| Code | Category (TR) | Category (EN) | Weight (%) | Covered |
|---|---|---|---|---|
| 01 | Gıda ve alkolsüz içecekler | Food and non-alcoholic beverages | 24.44 | ✓ |
| 02 | Alkollü içecekler, tütün ve tütün ürünleri | Alcoholic beverages and tobacco | 2.75 | ✗ |
| 03 | Giyim ve ayakkabı | Clothing and footwear | 7.90 | ✓ |
| 04 | Konut, su, elektrik, gaz ve diğer yakıtlar | Housing, water, electricity, gas | 11.40 | ✓ (rent only) |
| 05 | Mobilya, mefruşat ve ev ekipmanları | Furnishings and household equipment | 7.92 | ✓ |
| 06 | Sağlık | Health | 2.79 | ✓ (monthly) |
| 07 | Ulaştırma | Transport | 16.62 | ✗ |
| 08 | Bilgi ve iletişim | Information and communication | 3.10 | ✓ |
| 09 | Eğlence, dinlence, spor ve kültür | Recreation, sport and culture | 4.34 | ✗ |
| 10 | Eğitim hizmetleri | Education services | 2.02 | ✗ |
| 11 | Lokantalar ve konaklama hizmetleri | Restaurants and accommodation | 11.13 | ✓ |
| 12 | Sigorta ve finansal hizmetler | Insurance and financial services | 1.07 | ✗ |
| 13 | Kişisel bakım, sosyal koruma ve diğer | Personal care and miscellaneous | 4.49 | ✓ |

**Maximum achievable basket coverage:** ~73% (groups 01+03+04+05+06+08+11+13).  
Uncovered groups (02, 07, 09, 10, 12) lack scraped data sources.

When TÜİK Weighted metrics are computed, weights are **re-normalised** to sum to 100% across only the groups present in the data for that run.

---

## Data Sources by Sector

### Group 01 — Food & Non-Alcoholic Beverages (`Markets/`)

Daily scrape frequency.

| Store | Notes |
|---|---|
| A101 | National discount chain |
| Arden | Regional market |
| Basdas | Regional market |
| Baskent | Regional market |
| BizimMarket | National chain |
| Cagri | Regional market |
| CarrefourSA | National hypermarket |
| Gurmar | Regional market |
| Hapeloglu | Online grocery |
| HappyCenter | Regional market |
| Ideal | Regional market |
| Kale | Regional market |
| Kim | Regional market |
| Macrocenter | Premium supermarket |
| Marketzade | Online market |
| Migros | National supermarket chain |
| Mopas | Regional market |
| Onur | Regional market |
| Sariyer | Regional market |
| SozSanal | Online market |
| Tarım Kredi Kooperatif | Agricultural cooperative market |
| sehzade | Regional market |
| sok_market | National discount chain |

---

### Group 03 — Clothing & Footwear (`ClothingStores/`)

Daily scrape frequency.

| Store | Notes |
|---|---|
| Altınyıldız | Men's fashion |
| Avva | Men's fashion |
| Bershka | Fast fashion (Inditex) |
| Civil | Denim & casual |
| Colins | Denim & casual |
| Defacto | National fast fashion |
| H&M | International fast fashion |
| Koton | National fashion chain |
| LCWaikiki | National mass-market fashion |
| Loft | Mid-range fashion |
| Lufian | Premium casual |
| Mudo | Mid-range lifestyle |
| PullandBear | Fast fashion (Inditex) |
| Stradivarius | Fast fashion (Inditex) |
| Vakko | Luxury fashion |
| Zara | International fast fashion (Inditex) |
| adL | Casual fashion |
| addax | Casual fashion |
| beymenclub | Premium casual |

> **Note:** EnglishHome (HomeGoods) is permanently excluded from calculations due to highly volatile flash-sale pricing that creates systematic distortion (40%+ of matched products showing >50% price swings within 15 days).

---

### Group 05 — Furnishings & Household Equipment

Two sub-sectors both mapped to COICOP 05.

#### `HomeGoods/` — Home Furnishings

Daily scrape frequency.

| Store | Notes |
|---|---|
| Bellona | Furniture chain |
| Chakra | Home décor |
| Ikea | International furniture |
| Istikbal | National furniture chain |
| Karaca | Kitchen & home accessories |
| LCW Home | Home textiles |
| MadameCoco | Home textiles & décor |
| Vivense | Online furniture |
| jysk | Scandinavian home goods |
| tcshbo | Home goods |

#### `ConstructionSuppliesMarkets/` — Hardware & Building Materials

Daily scrape frequency.

| Store | Notes |
|---|---|
| AfeksYapiMarket | Online hardware |
| Bauhaus | International DIY chain |
| Ereyon | Online hardware |
| FiltasYapi | Construction supplies |
| HanCivata | Fasteners & hardware |
| Hausmart | Online hardware |
| LoyaMakina | Machinery & tools |
| Nalburadam | Hardware market |
| Nalburcuk | Hardware market |
| Nalburdayim | Hardware market |
| Nalburtek | Hardware market |
| SanatYapiOnline | Construction supplies |
| TasciYapiMarket | Building materials |
| Yapıyoz | Online hardware |
| yapimaks | Hardware market |

---

### Group 06 — Health (`Health/`)

**Monthly** scrape frequency (matched by `YYYY-MM` date token).

| Store | Notes |
|---|---|
| Dentist | Dental service prices |
| Diagnostic & Surgical Services | Diagnostic procedure prices |
| Doctor | General practitioner fees |
| Medicine & Glasses & Lenses | Pharmacy & optical prices |
| Physical_Therapy | Physiotherapy session fees |

---

### Group 08 — Information & Communication (`TechnologicalProducts/`)

Daily scrape frequency.

| Store | Notes |
|---|---|
| Beymen | Premium electronics |
| DR | Books, electronics & multimedia |
| Huawei | Brand store |
| Koçtaş | DIY & electronics |
| PozitifTeknoloji | Apple reseller |
| Samsung | Brand store |
| Teknoraks | Consumer electronics |
| Vatan Computer | National electronics chain |
| Xiaomi | Brand store |

---

### Group 11 — Restaurants & Accommodation

Two sub-sectors both mapped to COICOP 11.

#### `TravelTourism/` — Travel & Accommodation

Daily scrape frequency.

| Store | Notes |
|---|---|
| HajjUmrah | Pilgrimage package prices |
| HolidayPackages | Package holiday prices |
| Hotels | Hotel accommodation prices |

#### `RestaurantMealPricesVenueHallRentalFees/` — Restaurant & Venue Prices

Daily scrape frequency. Files sit directly in the sector root (no store subdirectories); each file's name prefix is used as the source identifier.

| Source | Notes |
|---|---|
| menufiyati_com_tr | Restaurant menu prices aggregator |
| menufiyati_tr | Restaurant menu prices aggregator |
| menufiyatlar | Restaurant menu prices aggregator |
| menufiyatlistesi | Restaurant menu prices aggregator |
| duguncom_dugun_mekanlari_istanbul | Wedding venue prices (Istanbul) |
| duguncom_dugun_salonlari_istanbul | Wedding hall prices (Istanbul) |
| duguncom_kir_dugunu_istanbul | Garden wedding venue prices (Istanbul) |
| duguncom_soz_nisan_mekanlari_istanbul | Engagement venue prices (Istanbul) |
| dugunbuketi_dugun_mekanlari_istanbul | Wedding venue prices (Istanbul) |
| dugunbuketi_dugun_salonlari_istanbul | Wedding hall prices (Istanbul) |

---

### Group 04 — Housing / Rent (`HousesRent/`) — Special Handling

Rent data is **not** processed through the standard product pipeline. Instead:

1. For each run date, mean rent prices are computed per city/district from scraped listing data.
2. The same is done for the comparison date.
3. Rent inflation = mean price change across all cities common to both dates.
4. This single figure is injected into the **TÜİK Weighted (Full)** metric as group 04.
5. Rent does **not** appear in Basic Inflation or Average Inflation (which are product-level only).

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
_load_all_stores()         — concat all sectors, deduplicate within store
        │
        ▼
merge(current, past)       — inner join on (store, canonical_key, tuik_category, sector)
        │
        ▼
Outlier filter             — drop |price change| > 80% (scraping anomalies)
        │
        ▼
_compute_metrics()         — basic_index, avg_inflation, tuik_weighted
        │
        ▼
_rent_relative()           — city-level rent change injected as group 04
        │
        ▼
Output CSVs
```

---

## Deduplication

Products appearing in **multiple stores** within the same TUIK category are matched by normalised name (Turkish diacritics stripped, lowercased, whitespace collapsed). Their current and past prices are averaged across stores before the basket calculation, preventing any product from carrying excess weight.

Products appearing **twice in the same store file** are averaged within that store before cross-store deduplication.

---

## Outlier Filter

Price changes with `|relative change| > 80%` within a single comparison interval are excluded before metric computation. This filters out scraping errors (e.g. prices recorded at 10× scale on a given date) without affecting genuine large but plausible price movements. Excluded pair counts are logged per run.

---

## Output Files

### `turkey_inflation_{YYYY-MM-DD}.csv`

One row per unique `(canonical_key, tuik_category)` pair found on the target date.

| Column | Description |
|---|---|
| `canonical_key` | Normalised product name (deduplication key) |
| `product_key` | Original product name |
| `tuik_category` | COICOP 2-digit code |
| `sector` | Internal sector label |
| `store` | Store name(s), comma-separated if matched across multiple |
| `relative_15d` | % price change vs 15 days prior |
| `relative_30d` | % price change vs 30 days prior |

### `turkey_inflation_summary.csv`

Append-only time series. One row per run date.

| Column Group | Columns |
|---|---|
| **Date & coverage** | `date`, `n_stores`, `n_products_raw`, `n_products_deduped`, `basket_coverage_pct` |
| **Store counts per category** | `n_stores_01`, `n_stores_03`, `n_stores_04`, … |
| **Product counts per category** | `n_products_01`, `n_products_03`, … |
| **15-day metrics** | `avg_inflation_15d`, `basic_index_15d`, `tuik_weighted_products_15d`, `tuik_weighted_full_15d`, `rent_inflation_15d` |
| **30-day metrics** | `avg_inflation_30d`, `basic_index_30d`, `tuik_weighted_products_30d`, `tuik_weighted_full_30d`, `rent_inflation_30d` |
| **Per-category 15d** | `avg_inflation_01_15d`, `basic_index_01_15d`, `avg_inflation_03_15d`, … |
| **Per-category 30d** | `avg_inflation_01_30d`, `basic_index_01_30d`, `avg_inflation_03_30d`, … |

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

| Limitation | Impact |
|---|---|
| Groups 02, 07, 09, 10, 12 not covered | Max basket coverage ~73%; TÜİK weighted metric re-normalises to covered groups |
| EnglishHome excluded (flash-sale volatility) | HomeGoods sector coverage reduced |
| Rent covers listing prices only, not actual transaction prices | Group 04 is an approximation |
| Health data is monthly, not daily | Group 06 may lag by up to 30 days |
| Scraper availability varies by day | Low-data days (fewer stores) produce less reliable estimates |
| Restaurant data currently limited to Istanbul venues | Group 11 has geographic bias |
