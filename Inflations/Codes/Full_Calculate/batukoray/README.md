# Full Inflation Calculator — Batu Koray Masak

Calculates TUIK-weighted inflation for all 4 scrapers:

| Scraper | Domain | TUIK Category |
|---------|--------|---------------|
| Bershka | Clothing | 03 - Giyim ve ayakkabi |
| Hapeloglu | Grocery market | 01, 05, 12 (mixed) |
| Nalburadam | Construction supplies | 05 - Mobilya, ev aletleri |
| ErzurumErzincanBayburt | Rent (3 cities) | 04 - Konut |

## Usage

```bash
# Auto-fill gaps (only calculates missing dates)
uv run python calc_inflation.py

# Recalculate everything from scratch
uv run python calc_inflation.py --force
```

## How it works

1. Scans all scraped data files to find available dates
2. Scans inflation output files to find already-calculated dates
3. Fills the gap — runs the calculator only for missing dates
4. Each calculator matches products present in both the target date and the comparison date
5. Computes per-item inflation: `((new_price - old_price) / old_price) * 100`
6. Computes average inflation and TUIK-weighted inflation for 1d, 7d, 15d, 30d intervals

## Output

Each calculator produces:
- **Detailed CSV** — per-product inflation rates (e.g., `bershka_inflation_2026-04-05.csv`)
- **Summary CSV** — daily avg_inflation and tuik_weighted values (`inflation_summary.csv`)

Rent data is output per-city (Erzurum, Erzincan, Bayburt) plus a combined summary.

## Note

This script only calculates inflation — it does NOT scrape data.
If no scraped data exists for a date, that date is skipped.
Run `fullscrape.py` (under InflationItems) first to collect price data, or use the integrated workflow which runs both automatically.
