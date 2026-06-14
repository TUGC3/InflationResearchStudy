# Hunger Threshold ("Açlık Sınırı") Module — Methodology

## 1. Concept

The "hunger threshold" is a classic Turkish socioeconomic indicator (used by Türk-İş and others):
**the minimum monthly cost of a basic, nutritionally-adequate food basket for a household**.

This module re-creates that concept from scratch using **real scraped prices from 13 Turkish
online supermarkets** — A101, Arden, Basdas, Baskent, CarrefourSA, Gurmar, Hapeloglu, Kale, Kim,
Macrocenter, Marketzade, Migros, and Sozsanal — so the team gets an independently-computed,
up-to-date food-basket cost rather than relying on official figures.

## 2. The Food Basket (the "what")

A fixed basket of **16 food items across 8 categories**, each with a **monthly quantity**. This
basket and the quantities are identical and hardcoded in every per-market script and in the
aggregator — it's the common "ruler" applied to every market's catalog.

| Category | Item | Unit | Monthly Qty |
|---|---|---|---|
| Dairy Products | Yogurt | Kg | 59.7 |
| Dairy Products | White Cheese | Kg | 5.7 |
| Meat and Protein | Cubed Meat / Lamb Meat | Kg | 4.6 |
| Meat and Protein | Chicken | Kg | 10.3 |
| Meat and Protein | Fish | Kg | 6.9 |
| Meat and Protein | Eggs | Piece | 120.0 |
| Legumes | Chickpeas | Kg | 1.8 |
| Nuts and Seeds | Walnut / Hazelnut / Peanut | Kg | 2.7 |
| Grains | Bread | Kg | 18.0 |
| Fruits | Banana | Kg | 16.7 |
| Fruits | Seasonal Fruit | Kg | 12.9 |
| Vegetables | Onion | Kg | 18.0 |
| Vegetables | Eggplant / Zucchini | Kg | 23.1 |
| Vegetables | Other Vegetables | Kg | 11.8 |
| Oils | Olive Oil | Liter | 1.1 |
| Other Food Products | Grissini | Kg | 2.1 |

## 3. Pipeline Architecture — Two Stages

### Stage 1: Per-market scripts (13 files, one per supermarket)

Each script (e.g. `a101_hungerthreshold.py`) does the same job for one chain.

**a) Input data**
Monthly CSV snapshots of that market's scraped catalog (`product_name`, `price`), e.g.
`a101_kapida_2026-03-31.csv`, `...-04-30.csv`, `...-05-29.csv`.

**b) Matching real products to basket items (`MATCH_RULES`)**
Real product catalogs have thousands of messy Turkish product names (e.g. "Sek Tam Yağlı Yoğurt
1 Kg", "Pınar Süzme Yoğurt 500 G"). Each basket item has:
- `keywords` — substrings that must appear (e.g. "Yoğurt" matches yogurt items)
- `exclude` — substrings that disqualify a match (e.g. exclude "Süzme", "Probiyotik", "Mama"
  [pet food], "Cips" [chips] — products that *contain* the keyword but aren't the right category)
- `unit` — how to normalize the price (`kg`, `ml_or_L`, `piece`)

This is a **rule-based text classifier** that maps real SKUs onto the 16 standardized basket
categories.

**c) Unit-price normalization**
Real products come in different pack sizes (500g, 1kg, 1.5L, "6'lı" egg packs, etc.). The script
uses regex (`extract_weight_g`, `extract_volume_ml`, `extract_piece_count`) to pull the pack size
out of the product name and convert every matched product's price to a **standard unit price**
(TRY per kg, per liter, or per piece). Without this step, a 200g yogurt and a 1kg yogurt would be
compared on raw price, which would be meaningless.

**d) Averaging within a market**
All matching products for a basket item (after exclusions) are averaged → one **average unit
price** per item per month for that market.

**e) Monthly cost & total**
`monthly_cost = avg_unit_price × monthly_qty` for each of the 16 items, then summed → that
market's hunger threshold for that month.

**f) Output**
- `hunger_threshold_detail.csv` — per item, per month, with unit price, cost, number of matched
  products, and the actual matched product names (for auditability)
- `hunger_threshold_summary.csv` — month-by-month total + MoM % change

### Stage 2: Total aggregator (`total_hungerthreshold.py`)

Combines the 13 per-market `hunger_threshold_detail.csv` files into one national-level figure.

**a) Date normalization**
Different markets label their snapshots differently (e.g. "Feb-20 2026" vs "Apr2 2026" for
Arden's second April snapshot). `to_canon_month()` converts everything to a canonical "Mon YYYY"
label, using pandas parsing → regex fallback → hardcoded alias table as a last resort.

**b) Within-market monthly averaging**
If a market has multiple snapshots in the same month (e.g. Kale sampled on both Mar-01 and
Mar-30), those are averaged into one price per product per month for that market.

**c) Cross-market averaging**
For each (month, product), the script averages the unit price across however many of the 13
markets reported that product that month, and records `n_markets` (how many markets contributed)
for transparency.

**d) Coverage check (the key safeguard)**
This is the most important methodological detail. By default, `pandas.sum()` silently skips
`NaN` values. If, say, "Fish" has no price data for May across all 13 markets, a naive `.sum()`
would just compute the total for the other 15 items and **understate the threshold without any
warning**. The aggregator explicitly checks: for each month, are **all 16 required items**
priced?
- If yes → compute the total normally.
- If no → set the threshold to `None` / "INCOMPLETE" for that month, and report exactly which
  items are missing and the coverage rate (e.g. "14/16 = 87.5%").

This means the final monthly hunger-threshold series **only contains months where the basket is
fully priced** — a deliberate "don't report a misleading number" choice.

**e) Output**
- `aggregate_detail.csv` — per product per month, with avg price, cost, number of contributing
  markets, and which markets
- `aggregate_summary.csv` — final monthly hunger threshold in TRY, MoM % change, coverage stats,
  missing items

## 4. Key Points & Caveats

- **Methodology choice**: this is a *bottom-up, basket-cost* approach — fixed quantities each
  month, only prices change — so month-to-month changes in the threshold directly reflect food
  price inflation, not consumption changes.
- **Cross-market average is unweighted** — each of the 13 markets contributes equally regardless
  of market share/size, a simplifying assumption.
- **Matching is rule-based** (keyword include/exclude lists), not ML — transparent and auditable
  (every match is visible via `matched_products`), but requires manual maintenance as catalogs
  change.
- **Conservative reporting**: incomplete months are excluded rather than estimated/imputed,
  trading completeness of the time series for accuracy.
- **Reproducibility note**: the scripts currently point at a hardcoded local path
  (`/Users/efeyildirim/Downloads/Marketler/...`), so they are currently set up for one
  collaborator's machine — worth flagging if the pipeline needs to run on other machines.
