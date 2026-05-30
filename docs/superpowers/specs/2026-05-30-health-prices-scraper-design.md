# Health Prices Scraper — Design Spec
**Date:** 2026-05-30  
**Status:** Approved

---

## Goal

Collect the previous 3 months of official Turkish price data for medicine, glasses frames, and eyeglass lenses, and store it as a single consolidated CSV under `InflationItems/Datas/Health/Medicine_Glasses_Lenses/`.

---

## Data Sources

| Category | Source | URL | Update Frequency |
|---|---|---|---|
| İlaç (Medicine) | TİTCK — Referans İlaç Fiyat Listesi | `https://www.titck.gov.tr/dinamikmodul/100` | Monthly/semi-monthly Excel files |
| Gözlük Çerçevesi (Glasses frame) | SGK — Optik SUT page | `https://www.sgk.gov.tr/Content/Post/29aa9928-48df-47af-9fc6-03c74da9cc0a/Optik-Gormeye-Yardimci-Malzeme-Nedir-Ne-Sekilde-Temin-Edilir-2026-01-09-03-59-14` | Annual (Jan 2026) |
| Gözlük Camı (Eyeglass lens) | SGK — Optik SUT page | same as above | Annual (Jan 2026) |

**TİTCK note:** The page lists multiple dated Excel files. The scraper downloads all files published within the last 3 months. If only the latest file is accessible, it uses that single snapshot with today's date.

**SGK note:** Optical prices are set annually via Sağlık Uygulama Tebliği (SUT). For a 3-month window, these values do not change — each month row will carry the same SGK official rate.

---

## File & Folder Structure

```
InflationItems/
  Codes/Health/
    Medicine_Glasses_Lenses/
      health_scraper.py        ← single entry-point script
  Datas/Health/
    Medicine_Glasses_Lenses/
      health_prices_3months.csv  ← consolidated output (one file)
```

---

## Script Architecture

**File:** `InflationItems/Codes/Health/Medicine_Glasses_Lenses/health_scraper.py`

Three functions, called in sequence from `main()`:

### 1. `fetch_titck_medicine_prices() → pd.DataFrame`

- GET `https://www.titck.gov.tr/dinamikmodul/100`
- Parse all anchor tags with `.xls` / `.xlsx` hrefs
- Filter to files whose name or link contains a date within the last 3 months (Feb–May 2026)
- Download each Excel file, parse with `pandas.read_excel()`
- Normalise to: `date`, `product-name`, `product-price`, `category="İlaç"`, `source="TİTCK"`
- Return concatenated DataFrame

### 2. `fetch_sgk_optical_prices() → pd.DataFrame`

- GET the SGK optical SUT page
- Parse the HTML table listing frame and lens reimbursement prices
- For each row: extract product name (e.g. "Tek Odaklı Cam", "Çerçeve"), price (TL)
- Assign `category` = `"Gözlük Çerçevesi"` or `"Gözlük Camı"` based on product name
- Record `date` as today's date (prices are annual; one row per product)
- Return DataFrame

### 3. `save_consolidated(medicines_df, optical_df) → None`

- Concatenate both DataFrames
- Ensure column order: `date`, `product-name`, `product-price`, `category`, `source`
- Drop rows where `product-price` is null or non-numeric
- Write to `InflationItems/Datas/Health/Medicine_Glasses_Lenses/health_prices_3months.csv`
  using `encoding="utf-8-sig"`, `index=False`

---

## Output CSV Format

| Column | Type | Example |
|---|---|---|
| `date` | YYYY-MM-DD | `2026-03-01` |
| `product-name` | string | `Aspirin 100mg 20 Tablet` |
| `product-price` | float | `45.50` |
| `category` | string | `İlaç` / `Gözlük Çerçevesi` / `Gözlük Camı` |
| `source` | string | `TİTCK` / `SGK` |

---

## Error Handling

- If TİTCK page is unreachable: print warning, skip medicine rows (don't crash)
- If no dated Excel files found within 3-month window: fall back to downloading the first available file on the page
- If SGK page is unreachable: print warning, skip optical rows
- If an individual Excel file fails to parse: skip it with a warning, continue to next

---

## Dependencies

Uses libraries already present in the project's `requirements.txt`:
- `requests`
- `beautifulsoup4`
- `pandas`
- `openpyxl` (for `.xlsx` parsing — verify it's in requirements.txt; add if missing)
