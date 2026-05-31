# Turkey Inflation Calculator — Revision Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rewrite `Inflations/Codes/turkey_inflation.py` to auto-discover stores via a sector config dict, use `canonical_key` throughout deduplication and cross-date matching, and compute inflation as relative price changes within each store before averaging across stores.

**Architecture:** A `_SECTOR_CONFIG` dict maps data directory names to `(tuik_code, sector_label, date_granularity)`. A generic `_load_sector` function scans store subdirectories for CSVs matching the target date, validates the `product_name,price` header, and loads them. `_compute_metrics` inner-joins on `(store, canonical_key, tuik_category)` and computes `relative = price/past_price - 1` per row before averaging across stores.

**Tech Stack:** Python 3.13, pandas, pytest 9.0.2, pathlib

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `Inflations/Codes/turkey_inflation.py` | Full rewrite | All loader, metric, and orchestration logic |
| `tests/test_turkey_inflation.py` | Create | Pytest unit + integration tests |

---

### Task 1: Test infrastructure + `_has_standard_header`

**Files:**
- Create: `tests/test_turkey_inflation.py`
- Modify: `Inflations/Codes/turkey_inflation.py` (add `_has_standard_header`)

- [ ] **Step 1: Create the test file with imports and the failing test**

```python
# tests/test_turkey_inflation.py
import sys
import pandas as pd
import pytest
from pathlib import Path

sys.path.insert(0, "Inflations/Codes")
from turkey_inflation import _has_standard_header


def test_has_standard_header_valid(tmp_path):
    f = tmp_path / "test.csv"
    f.write_text("product_name,price\nFoo,10.0\n")
    assert _has_standard_header(f) is True


def test_has_standard_header_bom(tmp_path):
    f = tmp_path / "test.csv"
    f.write_bytes(b"\xef\xbb\xbfproduct_name,price\nFoo,10.0\n")
    assert _has_standard_header(f) is True


def test_has_standard_header_wrong_columns(tmp_path):
    f = tmp_path / "test.csv"
    f.write_text("id,shown_price\n123,10.0\n")
    assert _has_standard_header(f) is False


def test_has_standard_header_missing_file(tmp_path):
    assert _has_standard_header(tmp_path / "nonexistent.csv") is False
```

- [ ] **Step 2: Run tests — expect ImportError or AttributeError**

```bash
cd /Users/atahakancildas/Desktop/Docs/Projects/InflationResearchStudy
source venv/bin/activate && python -m pytest tests/test_turkey_inflation.py -v 2>&1 | head -30
```

- [ ] **Step 3: Add `_has_standard_header` to `turkey_inflation.py`**

At the top of `Inflations/Codes/turkey_inflation.py`, after the existing imports and `_norm`/`_parse_price` functions, add:

```python
_SKIP_SUBDIRS = {"InflationData", "output", "reports", "archive"}


def _has_standard_header(fpath: Path) -> bool:
    try:
        with fpath.open(encoding="utf-8", errors="ignore") as fh:
            first = fh.readline().strip().lstrip("﻿")
        return first == "product_name,price"
    except Exception:
        return False
```

- [ ] **Step 4: Run tests — expect all 4 to pass**

```bash
source venv/bin/activate && python -m pytest tests/test_turkey_inflation.py -v
```

Expected: `4 passed`

- [ ] **Step 5: Commit**

```bash
git add tests/test_turkey_inflation.py Inflations/Codes/turkey_inflation.py
git commit -m "feat: add _has_standard_header with BOM handling and tests"
```

---

### Task 2: `_find_date_csv` — auto-discovery with protection

**Files:**
- Modify: `Inflations/Codes/turkey_inflation.py`
- Modify: `tests/test_turkey_inflation.py`

- [ ] **Step 1: Add failing tests**

Append to `tests/test_turkey_inflation.py`:

```python
from turkey_inflation import _find_date_csv


def test_find_date_csv_direct(tmp_path):
    store_dir = tmp_path / "StoreA"
    store_dir.mkdir()
    f = store_dir / "storea_2026-05-01.csv"
    f.write_text("product_name,price\nFoo,10.0\n")
    assert _find_date_csv(store_dir, "2026-05-01") == f


def test_find_date_csv_nested_allowed_subdir(tmp_path):
    store_dir = tmp_path / "Bershka"
    store_dir.mkdir()
    prod_dir = store_dir / "ProductData"
    prod_dir.mkdir()
    f = prod_dir / "bershka_2026-05-01.csv"
    f.write_text("product_name,price\nFoo,10.0\n")
    assert _find_date_csv(store_dir, "2026-05-01") == f


def test_find_date_csv_skips_inflation_data_subdir(tmp_path):
    store_dir = tmp_path / "Bershka"
    store_dir.mkdir()
    bad_dir = store_dir / "InflationData"
    bad_dir.mkdir()
    bad = bad_dir / "bershka_2026-05-01.csv"
    bad.write_text("product_name,price\nFoo,10.0\n")
    assert _find_date_csv(store_dir, "2026-05-01") is None


def test_find_date_csv_skips_wrong_header(tmp_path):
    store_dir = tmp_path / "StoreA"
    store_dir.mkdir()
    f = store_dir / "storea_2026-05-01.csv"
    f.write_text("id,cost\n1,10.0\n")
    assert _find_date_csv(store_dir, "2026-05-01") is None


def test_find_date_csv_no_matching_date(tmp_path):
    store_dir = tmp_path / "StoreA"
    store_dir.mkdir()
    f = store_dir / "storea_2026-04-01.csv"
    f.write_text("product_name,price\nFoo,10.0\n")
    assert _find_date_csv(store_dir, "2026-05-01") is None
```

- [ ] **Step 2: Run — expect 5 failures**

```bash
source venv/bin/activate && python -m pytest tests/test_turkey_inflation.py::test_find_date_csv_direct -v
```

Expected: `ImportError` or `FAILED`

- [ ] **Step 3: Implement `_find_date_csv`**

Add to `Inflations/Codes/turkey_inflation.py` after `_has_standard_header`:

```python
def _find_date_csv(store_dir: Path, date_token: str) -> Path | None:
    for f in store_dir.rglob(f"*{date_token}*.csv"):
        rel_parts = f.relative_to(store_dir).parts[:-1]
        if any(p in _SKIP_SUBDIRS for p in rel_parts):
            continue
        if _has_standard_header(f):
            return f
    return None
```

- [ ] **Step 4: Run — expect all 9 tests to pass**

```bash
source venv/bin/activate && python -m pytest tests/test_turkey_inflation.py -v
```

Expected: `9 passed`

- [ ] **Step 5: Commit**

```bash
git add tests/test_turkey_inflation.py Inflations/Codes/turkey_inflation.py
git commit -m "feat: add _find_date_csv with rglob, skip-subdir, and header protection"
```

---

### Task 3: `_load_store_csv` — generic CSV loader

**Files:**
- Modify: `Inflations/Codes/turkey_inflation.py`
- Modify: `tests/test_turkey_inflation.py`

- [ ] **Step 1: Add failing tests**

Append to `tests/test_turkey_inflation.py`:

```python
from turkey_inflation import _load_store_csv


def test_load_store_csv_basic(tmp_path):
    f = tmp_path / "store_2026-05-01.csv"
    f.write_text("product_name,price\nElma 1 Kg,10.50\nArmut 1 Kg,15.00\n")
    df = _load_store_csv(f, "TestStore", "market", "01")
    assert df is not None
    assert len(df) == 2
    assert set(df.columns) >= {"canonical_key", "product_key", "price", "store", "sector", "tuik_category"}
    assert df["store"].iloc[0] == "TestStore"
    assert df["tuik_category"].iloc[0] == "01"
    assert df["sector"].iloc[0] == "market"
    assert df["canonical_key"].iloc[0] == "elma 1 kg"


def test_load_store_csv_normalises_turkish(tmp_path):
    f = tmp_path / "store_2026-05-01.csv"
    f.write_text("product_name,price\nÇilek Şekeri,25.0\n")
    df = _load_store_csv(f, "TestStore", "market", "01")
    assert df["canonical_key"].iloc[0] == "cilek sekeri"


def test_load_store_csv_drops_invalid_prices(tmp_path):
    f = tmp_path / "store_2026-05-01.csv"
    f.write_text("product_name,price\nElma,10.50\nArmut,abc\nKivi,-5\nMuz,\n")
    df = _load_store_csv(f, "TestStore", "market", "01")
    assert df is not None
    assert len(df) == 1


def test_load_store_csv_parses_turkish_price_format(tmp_path):
    f = tmp_path / "store_2026-05-01.csv"
    f.write_text('product_name,price\nElma,"1.234,56 TL"\n')
    df = _load_store_csv(f, "TestStore", "market", "01")
    assert df is not None
    assert abs(df["price"].iloc[0] - 1234.56) < 0.01


def test_load_store_csv_wrong_header_returns_none(tmp_path):
    f = tmp_path / "store_2026-05-01.csv"
    f.write_text("id,cost\n1,10.0\n")
    assert _load_store_csv(f, "TestStore", "market", "01") is None


def test_load_store_csv_empty_after_filtering_returns_none(tmp_path):
    f = tmp_path / "store_2026-05-01.csv"
    f.write_text("product_name,price\nElma,abc\nArmut,-1\n")
    assert _load_store_csv(f, "TestStore", "market", "01") is None
```

- [ ] **Step 2: Run — expect 6 failures**

```bash
source venv/bin/activate && python -m pytest tests/test_turkey_inflation.py -k "load_store_csv" -v
```

- [ ] **Step 3: Implement `_load_store_csv`**

Add to `Inflations/Codes/turkey_inflation.py`:

```python
_STANDARD_COLS = ["canonical_key", "product_key", "price", "store", "sector", "tuik_category"]


def _load_store_csv(fpath: Path, store: str, sector: str, tuik_code: str) -> pd.DataFrame | None:
    try:
        df = pd.read_csv(fpath, dtype=str, on_bad_lines="skip")
        df.columns = [c.lstrip("﻿").strip() for c in df.columns]
        if "product_name" not in df.columns or "price" not in df.columns:
            return None
        out = pd.DataFrame()
        out["product_key"] = df["product_name"].astype(str).str.strip()
        out["canonical_key"] = out["product_key"].apply(_norm)
        out["price"] = df["price"].apply(_parse_price)
        out["store"] = store
        out["sector"] = sector
        out["tuik_category"] = tuik_code
        out = out[out["canonical_key"] != ""].dropna(subset=["price"])
        out = out[out["price"] > 0].reset_index(drop=True)
        return out if not out.empty else None
    except Exception as e:
        logger.debug("%s: failed to load %s — %s", store, fpath.name, e)
        return None
```

- [ ] **Step 4: Run — expect all 15 tests to pass**

```bash
source venv/bin/activate && python -m pytest tests/test_turkey_inflation.py -v
```

Expected: `15 passed`

- [ ] **Step 5: Commit**

```bash
git add tests/test_turkey_inflation.py Inflations/Codes/turkey_inflation.py
git commit -m "feat: add _load_store_csv generic loader with canonical_key"
```

---

### Task 4: `_load_sector` + `_load_all_stores`

**Files:**
- Modify: `Inflations/Codes/turkey_inflation.py`
- Modify: `tests/test_turkey_inflation.py`

- [ ] **Step 1: Add failing tests**

Append to `tests/test_turkey_inflation.py`:

```python
from turkey_inflation import _load_sector, _load_all_stores, _SECTOR_CONFIG, _DATA_ROOT


def _make_store(base: Path, sector: str, store: str, date: str, rows: str) -> None:
    d = base / sector / store
    d.mkdir(parents=True)
    (d / f"{store.lower()}_{date}.csv").write_text(f"product_name,price\n{rows}")


def test_load_sector_discovers_two_stores(tmp_path):
    _make_store(tmp_path, "Markets", "StoreA", "2026-05-01", "Elma,10\nArmut,15\n")
    _make_store(tmp_path, "Markets", "StoreB", "2026-05-01", "Elma,11\nArmut,16\n")
    frames = _load_sector(tmp_path / "Markets", "2026-05-01", "01", "market")
    assert len(frames) == 2
    stores = {df["store"].iloc[0] for df in frames}
    assert stores == {"StoreA", "StoreB"}


def test_load_sector_skips_store_missing_date(tmp_path):
    _make_store(tmp_path, "Markets", "StoreA", "2026-04-01", "Elma,10\n")
    frames = _load_sector(tmp_path / "Markets", "2026-05-01", "01", "market")
    assert frames == []


def test_load_sector_monthly_matches_yyyy_mm(tmp_path):
    d = tmp_path / "Health" / "HealthStore"
    d.mkdir(parents=True)
    (d / "health_prices_2026-05.csv").write_text("product_name,price\nAspirin,5.0\n")
    frames = _load_sector(tmp_path / "Health", "2026-05-15", "06", "health", date_granularity="monthly")
    assert len(frames) == 1
    assert frames[0]["store"].iloc[0] == "HealthStore"


def test_load_all_stores_deduplicates_within_store(tmp_path, monkeypatch):
    monkeypatch.setattr("turkey_inflation._DATA_ROOT", tmp_path)
    monkeypatch.setattr("turkey_inflation._SECTOR_CONFIG", {
        "Markets": ("01", "market", "daily"),
    })
    d = tmp_path / "Markets" / "StoreA"
    d.mkdir(parents=True)
    # Same product listed twice in one store
    (d / "storea_2026-05-01.csv").write_text(
        "product_name,price\nElma,10\nElma,12\nArmut,15\n"
    )
    df, stores, n_before = _load_all_stores("2026-05-01")
    assert n_before == 3
    elma_rows = df[(df["store"] == "StoreA") & (df["canonical_key"] == "elma")]
    assert len(elma_rows) == 1
    assert abs(elma_rows["price"].iloc[0] - 11.0) < 0.01  # averaged
```

- [ ] **Step 2: Run — expect 4 failures**

```bash
source venv/bin/activate && python -m pytest tests/test_turkey_inflation.py -k "load_sector or load_all_stores" -v
```

- [ ] **Step 3: Implement `_SECTOR_CONFIG`, `_load_sector`, `_load_all_stores`**

Replace the existing `_STORE_LOADERS` list and `_load_all_stores` function in `Inflations/Codes/turkey_inflation.py` with:

```python
# Maps sector directory name → (tuik_code, sector_label, date_granularity)
# date_granularity: "daily" matches *YYYY-MM-DD*, "monthly" matches *YYYY-MM*
_SECTOR_CONFIG: dict[str, tuple[str, str, str]] = {
    "Markets":                     ("01", "market",       "daily"),
    "ClothingStores":              ("03", "clothing",     "daily"),
    "HomeGoods":                   ("05", "homegoods",    "daily"),
    "ConstructionSuppliesMarkets": ("05", "construction", "daily"),
    "Health":                      ("06", "health",       "monthly"),
    "TechnologicalProducts":       ("08", "tech",         "daily"),
    "TravelTourism":               ("11", "tourism",      "daily"),
    "Cosmetics":                   ("13", "cosmetics",    "daily"),
}


def _load_sector(
    sector_dir: Path,
    date_str: str,
    tuik_code: str,
    sector_label: str,
    date_granularity: str = "daily",
) -> list[pd.DataFrame]:
    date_token = date_str[:7] if date_granularity == "monthly" else date_str
    frames = []
    for store_dir in sorted(sector_dir.iterdir()):
        if not store_dir.is_dir():
            continue
        fpath = _find_date_csv(store_dir, date_token)
        if fpath is None:
            continue
        df = _load_store_csv(fpath, store_dir.name, sector_label, tuik_code)
        if df is not None and not df.empty:
            frames.append(df)
    return frames


def _load_all_stores(date_str: str) -> tuple[pd.DataFrame, list[str], int]:
    frames: list[pd.DataFrame] = []
    for sector_name, (tuik_code, sector_label, date_gran) in _SECTOR_CONFIG.items():
        sector_dir = _DATA_ROOT / sector_name
        if not sector_dir.exists():
            continue
        frames.extend(_load_sector(sector_dir, date_str, tuik_code, sector_label, date_gran))

    if not frames:
        return pd.DataFrame(columns=_STANDARD_COLS), [], 0

    combined = pd.concat(frames, ignore_index=True)
    n_before = len(combined)
    stores_ok = list(combined["store"].unique())

    # Deduplicate within each store (same product appearing twice in one CSV)
    deduped = (
        combined
        .groupby(["store", "canonical_key", "tuik_category", "sector"], as_index=False)
        .agg(
            product_key=("product_key", "first"),
            price=("price", "mean"),
        )
    )
    return deduped, stores_ok, n_before
```

- [ ] **Step 4: Run — expect all 19 tests to pass**

```bash
source venv/bin/activate && python -m pytest tests/test_turkey_inflation.py -v
```

Expected: `19 passed`

- [ ] **Step 5: Commit**

```bash
git add tests/test_turkey_inflation.py Inflations/Codes/turkey_inflation.py
git commit -m "feat: add _SECTOR_CONFIG, _load_sector, _load_all_stores with auto-discovery"
```

---

### Task 5: `_compute_metrics` — relative price approach

**Files:**
- Modify: `Inflations/Codes/turkey_inflation.py`
- Modify: `tests/test_turkey_inflation.py`

- [ ] **Step 1: Add failing tests**

Append to `tests/test_turkey_inflation.py`:

```python
from turkey_inflation import _compute_metrics


def _pool(*rows):
    return pd.DataFrame(
        rows,
        columns=["store", "canonical_key", "tuik_category", "sector", "product_key", "price"],
    )


def test_compute_metrics_both_stores_same_change():
    cur = _pool(
        ("Migros", "elma", "01", "market", "Elma", 110.0),
        ("A101",   "elma", "01", "market", "Elma", 220.0),
    )
    past = _pool(
        ("Migros", "elma", "01", "market", "Elma", 100.0),
        ("A101",   "elma", "01", "market", "Elma", 200.0),
    )
    product_rel, basic_idx, avg_inf, _ = _compute_metrics(cur, past)
    assert abs(avg_inf - 10.0) < 0.01
    assert abs(basic_idx - 10.0) < 0.01


def test_compute_metrics_excludes_new_store_in_current():
    # A101 only appears in current — must be excluded from relative calc
    cur = _pool(
        ("Migros", "elma", "01", "market", "Elma", 110.0),
        ("A101",   "elma", "01", "market", "Elma", 220.0),
    )
    past = _pool(
        ("Migros", "elma", "01", "market", "Elma", 100.0),
    )
    _, _, avg_inf, _ = _compute_metrics(cur, past)
    # Only Migros row matched; 10% change
    assert abs(avg_inf - 10.0) < 0.01


def test_compute_metrics_averages_relative_not_price():
    # Migros: 10% change. A101: 20% change. Average = 15%, not price-level average
    cur = _pool(
        ("Migros", "elma", "01", "market", "Elma", 110.0),
        ("A101",   "elma", "01", "market", "Elma", 240.0),
    )
    past = _pool(
        ("Migros", "elma", "01", "market", "Elma", 100.0),
        ("A101",   "elma", "01", "market", "Elma", 200.0),
    )
    product_rel, _, avg_inf, _ = _compute_metrics(cur, past)
    assert abs(avg_inf - 15.0) < 0.01
    assert len(product_rel) == 1  # one unique product


def test_compute_metrics_empty_past_returns_nones():
    cur = _pool(("Migros", "elma", "01", "market", "Elma", 110.0))
    past = pd.DataFrame(columns=["store", "canonical_key", "tuik_category", "sector", "product_key", "price"])
    _, basic_idx, avg_inf, tuik_w = _compute_metrics(cur, past)
    assert basic_idx is None
    assert avg_inf is None
    assert tuik_w is None


def test_compute_metrics_product_rel_has_one_row_per_product():
    cur = _pool(
        ("Migros", "elma", "01", "market", "Elma", 110.0),
        ("A101",   "elma", "01", "market", "Elma", 220.0),
        ("Migros", "armut", "01", "market", "Armut", 55.0),
    )
    past = _pool(
        ("Migros", "elma",  "01", "market", "Elma",  100.0),
        ("A101",   "elma",  "01", "market", "Elma",  200.0),
        ("Migros", "armut", "01", "market", "Armut",  50.0),
    )
    product_rel, _, _, _ = _compute_metrics(cur, past)
    assert len(product_rel) == 2  # elma and armut
```

- [ ] **Step 2: Run — expect 5 failures**

```bash
source venv/bin/activate && python -m pytest tests/test_turkey_inflation.py -k "compute_metrics" -v
```

- [ ] **Step 3: Replace `_compute_metrics` in `turkey_inflation.py`**

Replace the existing `_compute_metrics` function entirely:

```python
def _compute_metrics(
    df_current: pd.DataFrame,
    df_past: pd.DataFrame,
) -> tuple[pd.DataFrame, float | None, float | None, float | None]:
    if df_past.empty:
        return pd.DataFrame(), None, None, None

    merge_keys = ["store", "canonical_key", "tuik_category", "sector"]
    past_sub = df_past[merge_keys + ["price"]].rename(columns={"price": "past_price"})
    matched = df_current.merge(past_sub, on=merge_keys, how="inner")

    if matched.empty:
        return pd.DataFrame(), None, None, None

    # Relative change per (store, product): percentage form
    matched["relative"] = (matched["price"] / matched["past_price"] - 1) * 100
    matched["relative"] = matched["relative"].replace([float("inf"), float("-inf")], pd.NA)

    # Average relative across stores → one row per (canonical_key, tuik_category)
    product_rel = (
        matched
        .groupby(["canonical_key", "tuik_category", "sector"], as_index=False)
        .agg(
            product_key=("product_key", "first"),
            store=("store", lambda s: ",".join(sorted(s.unique()))),
            relative=("relative", "mean"),
        )
    )

    # basic_index: basket-level sum ratio on matched pairs
    sum_cur = matched["price"].sum()
    sum_past = matched["past_price"].sum()
    basic_index = float((sum_cur / sum_past - 1) * 100) if sum_past else None

    # avg_inflation: arithmetic mean of per-product relatives
    valid_rel = product_rel["relative"].dropna()
    avg_inflation = float(valid_rel.mean()) if not valid_rel.empty else None

    # tuik_weighted: category-level TUIK-weighted average
    cat_rel = product_rel.groupby("tuik_category")["relative"].mean()
    present_codes = list(cat_rel.dropna().index)
    norm_w = normalised_weights(present_codes)
    tuik_weighted = (
        float(sum(cat_rel[c] * norm_w[c] / 100.0 for c in norm_w if pd.notna(cat_rel.get(c))))
        if norm_w else None
    )

    return product_rel, basic_index, avg_inflation, tuik_weighted
```

- [ ] **Step 4: Run — expect all 24 tests to pass**

```bash
source venv/bin/activate && python -m pytest tests/test_turkey_inflation.py -v
```

Expected: `24 passed`

- [ ] **Step 5: Commit**

```bash
git add tests/test_turkey_inflation.py Inflations/Codes/turkey_inflation.py
git commit -m "feat: rewrite _compute_metrics with inner-join relative price approach"
```

---

### Task 6: `_rent_city_prices` + `_rent_relative`

**Files:**
- Modify: `Inflations/Codes/turkey_inflation.py`
- Modify: `tests/test_turkey_inflation.py`

- [ ] **Step 1: Add failing tests**

Append to `tests/test_turkey_inflation.py`:

```python
from turkey_inflation import _rent_city_prices, _rent_relative
import turkey_inflation


def _make_rent_city(base: Path, city: str, date: str, prices: list) -> None:
    d = base / "HousesRent" / city
    d.mkdir(parents=True)
    lines = "\n".join(f"Daire {i+1},{p}" for i, p in enumerate(prices))
    (d / f"rent_{date}.csv").write_text(f"product_name,price\n{lines}\n")


def test_rent_city_prices_mean_per_city(tmp_path, monkeypatch):
    monkeypatch.setattr(turkey_inflation, "_DATA_ROOT", tmp_path)
    _make_rent_city(tmp_path, "Ankara", "2026-05-01", [10000, 20000])
    _make_rent_city(tmp_path, "Istanbul", "2026-05-01", [30000, 40000])
    result = _rent_city_prices("2026-05-01")
    assert abs(result["Ankara"] - 15000.0) < 0.01
    assert abs(result["Istanbul"] - 35000.0) < 0.01


def test_rent_city_prices_skips_root_files(tmp_path, monkeypatch):
    monkeypatch.setattr(turkey_inflation, "_DATA_ROOT", tmp_path)
    rent_root = tmp_path / "HousesRent"
    rent_root.mkdir()
    (rent_root / "2026-05-01_all.csv").write_text("product_name,price\nDaire,15000\n")
    result = _rent_city_prices("2026-05-01")
    assert result == {}


def test_rent_relative_computes_percentage_change(tmp_path, monkeypatch):
    monkeypatch.setattr(turkey_inflation, "_DATA_ROOT", tmp_path)
    _make_rent_city(tmp_path, "Ankara",   "2026-05-01", [11000, 16500])
    _make_rent_city(tmp_path, "Istanbul", "2026-05-01", [11000, 16500])
    _make_rent_city(tmp_path, "Ankara",   "2026-04-01", [10000, 15000])
    _make_rent_city(tmp_path, "Istanbul", "2026-04-01", [10000, 15000])
    result = _rent_relative("2026-05-01", "2026-04-01")
    # mean_past=12500, mean_cur=13750 → 10% increase
    assert result is not None
    assert abs(result - 10.0) < 0.01


def test_rent_relative_only_common_cities(tmp_path, monkeypatch):
    monkeypatch.setattr(turkey_inflation, "_DATA_ROOT", tmp_path)
    _make_rent_city(tmp_path, "Ankara",  "2026-05-01", [11000])
    _make_rent_city(tmp_path, "Ankara",  "2026-04-01", [10000])
    # Izmir only in current — excluded
    _make_rent_city(tmp_path, "Izmir",   "2026-05-01", [50000])
    result = _rent_relative("2026-05-01", "2026-04-01")
    assert result is not None
    assert abs(result - 10.0) < 0.01


def test_rent_relative_no_common_cities_returns_none(tmp_path, monkeypatch):
    monkeypatch.setattr(turkey_inflation, "_DATA_ROOT", tmp_path)
    _make_rent_city(tmp_path, "Ankara",  "2026-05-01", [10000])
    _make_rent_city(tmp_path, "Istanbul","2026-04-01", [20000])
    assert _rent_relative("2026-05-01", "2026-04-01") is None
```

- [ ] **Step 2: Run — expect 5 failures**

```bash
source venv/bin/activate && python -m pytest tests/test_turkey_inflation.py -k "rent" -v
```

- [ ] **Step 3: Replace `_rent_city_prices` and `_rent_inflation` in `turkey_inflation.py`**

Remove the old `_rent_city_prices` and `_rent_inflation` functions entirely and replace with:

```python
def _rent_city_prices(date_str: str) -> dict[str, float]:
    rent_root = _DATA_ROOT / "HousesRent"
    city_prices: dict[str, list[float]] = {}
    for fpath in rent_root.rglob(f"*{date_str}*.csv"):
        if fpath.parent == rent_root:  # skip root-level aggregate files
            continue
        if not _has_standard_header(fpath):
            continue
        city_key = fpath.parent.name
        try:
            df = pd.read_csv(fpath, dtype=str, on_bad_lines="skip")
            df.columns = [c.lstrip("﻿").strip() for c in df.columns]
            prices = df["price"].apply(_parse_price).dropna()
            prices = prices[prices > 0]
            if not prices.empty:
                city_prices.setdefault(city_key, []).extend(prices.tolist())
        except Exception:
            continue
    return {k: sum(v) / len(v) for k, v in city_prices.items()}


def _rent_relative(current_str: str, past_str: str) -> float | None:
    cur_city = _rent_city_prices(current_str)
    past_city = _rent_city_prices(past_str)
    common = set(cur_city) & set(past_city)
    if not common:
        return None
    mean_cur  = sum(cur_city[c]  for c in common) / len(common)
    mean_past = sum(past_city[c] for c in common) / len(common)
    if mean_past == 0:
        return None
    return (mean_cur / mean_past - 1) * 100
```

- [ ] **Step 4: Run — expect all 29 tests to pass**

```bash
source venv/bin/activate && python -m pytest tests/test_turkey_inflation.py -v
```

Expected: `29 passed`

- [ ] **Step 5: Commit**

```bash
git add tests/test_turkey_inflation.py Inflations/Codes/turkey_inflation.py
git commit -m "feat: rewrite rent loader using rglob, standard header, relative change"
```

---

### Task 7: `_coverage_report`

**Files:**
- Modify: `Inflations/Codes/turkey_inflation.py`
- Modify: `tests/test_turkey_inflation.py`

- [ ] **Step 1: Add failing tests**

Append to `tests/test_turkey_inflation.py`:

```python
from turkey_inflation import _coverage_report
from tuik_config import TUIK_WEIGHTS


def test_coverage_report_full_coverage():
    all_codes = list(TUIK_WEIGHTS.keys())
    pct, report = _coverage_report(all_codes)
    assert abs(pct - 100.0) < 0.01
    assert "100.00%" in report


def test_coverage_report_partial():
    total_w = sum(d["weight"] for d in TUIK_WEIGHTS.values())
    expected_pct = (TUIK_WEIGHTS["01"]["weight"] + TUIK_WEIGHTS["03"]["weight"]) / total_w * 100
    pct, report = _coverage_report(["01", "03"])
    assert abs(pct - expected_pct) < 0.01
    assert "✓" in report
    assert "✗" in report


def test_coverage_report_empty():
    pct, _ = _coverage_report([])
    assert pct == 0.0


def test_coverage_report_unknown_code_ignored():
    pct1, _ = _coverage_report(["01"])
    pct2, _ = _coverage_report(["01", "99"])  # "99" doesn't exist
    assert abs(pct1 - pct2) < 0.01
```

- [ ] **Step 2: Run — expect 4 failures**

```bash
source venv/bin/activate && python -m pytest tests/test_turkey_inflation.py -k "coverage_report" -v
```

- [ ] **Step 3: Implement `_coverage_report`**

Add to `Inflations/Codes/turkey_inflation.py`:

```python
def _coverage_report(present_codes: list[str]) -> tuple[float, str]:
    total_w = sum(d["weight"] for d in TUIK_WEIGHTS.values())
    covered_w = sum(TUIK_WEIGHTS[c]["weight"] for c in present_codes if c in TUIK_WEIGHTS)
    coverage_pct = covered_w / total_w * 100 if total_w else 0.0

    lines = [f"Covered TUIK basket: {coverage_pct:.2f}%"]
    for code in sorted(TUIK_WEIGHTS):
        status = "✓" if code in present_codes else "✗"
        name = TUIK_WEIGHTS[code]["name"][:35]
        weight = TUIK_WEIGHTS[code]["weight"]
        lines.append(f"  {code}  {name:<35}  {weight:>6.2f}%  {status}")
    return coverage_pct, "\n".join(lines)
```

- [ ] **Step 4: Run — expect all 33 tests to pass**

```bash
source venv/bin/activate && python -m pytest tests/test_turkey_inflation.py -v
```

Expected: `33 passed`

- [ ] **Step 5: Commit**

```bash
git add tests/test_turkey_inflation.py Inflations/Codes/turkey_inflation.py
git commit -m "feat: add _coverage_report for TUIK basket coverage tracking"
```

---

### Task 8: `calculate_turkey_inflation` — orchestration + outputs

**Files:**
- Modify: `Inflations/Codes/turkey_inflation.py` (replace `calculate_turkey_inflation`)
- Modify: `tests/test_turkey_inflation.py` (integration test)

- [ ] **Step 1: Add integration test**

Append to `tests/test_turkey_inflation.py`:

```python
import shutil
from turkey_inflation import calculate_turkey_inflation


def test_calculate_turkey_inflation_runs_and_writes_outputs(tmp_path, monkeypatch):
    # Point output dir to tmp_path so we don't pollute real data
    out_dir = tmp_path / "Final_Reports"
    monkeypatch.setattr("turkey_inflation._OUT_DIR", out_dir)

    # Run against real data — 2026-05-26 vs 2026-05-01 (both dates have 50+ store files)
    calculate_turkey_inflation(target_date="2026-05-26", compare_date="2026-05-01")

    detail_file = out_dir / "turkey_inflation_2026-05-26.csv"
    summary_file = out_dir / "turkey_inflation_summary.csv"

    assert detail_file.exists(), "Detail CSV not written"
    assert summary_file.exists(), "Summary CSV not written"

    detail = pd.read_csv(detail_file)
    summary = pd.read_csv(summary_file)

    assert len(detail) > 0, "Detail CSV is empty"
    assert "canonical_key" in detail.columns
    assert "relative_2026-05-01" in detail.columns

    assert len(summary) == 1
    assert summary["date"].iloc[0] == "2026-05-26"
    assert summary["n_stores"].iloc[0] > 0
    assert "basket_coverage_pct" in summary.columns
    coverage = summary["basket_coverage_pct"].iloc[0]
    assert 60.0 < coverage < 100.0
```

- [ ] **Step 2: Run — expect 1 failure (function exists but wrong output)**

```bash
source venv/bin/activate && python -m pytest tests/test_turkey_inflation.py::test_calculate_turkey_inflation_runs_and_writes_outputs -v
```

- [ ] **Step 3: Replace `calculate_turkey_inflation` in `turkey_inflation.py`**

Remove the old `calculate_turkey_inflation` and replace with:

```python
def calculate_turkey_inflation(
    target_date: str | None = None,
    compare_date: str | None = None,
) -> None:
    if target_date:
        base_date = datetime.strptime(target_date, "%Y-%m-%d")
    else:
        base_date = datetime.today()
    today_str = base_date.strftime("%Y-%m-%d")

    logger.info("Loading current data for %s …", today_str)
    df_current, stores_today, n_before = _load_all_stores(today_str)

    if df_current.empty:
        logger.warning("No data found for %s — aborting.", today_str)
        return

    logger.info(
        "Loaded %d stores, %d raw rows, %d unique (store, product) pairs",
        len(stores_today), n_before, len(df_current),
    )

    present_codes = list(df_current["tuik_category"].unique())
    coverage_pct, coverage_str = _coverage_report(present_codes)
    logger.info("\n%s", coverage_str)

    _OUT_DIR.mkdir(parents=True, exist_ok=True)

    intervals = (
        {compare_date: compare_date}
        if compare_date
        else {
            f"{days}d": (base_date - timedelta(days=days)).strftime("%Y-%m-%d")
            for days in [15, 30]
        }
    )

    summary_row: dict = {
        "date": today_str,
        "n_stores": len(stores_today),
        "n_products_raw": n_before,
        "n_products_deduped": len(df_current),
        "basket_coverage_pct": round(coverage_pct, 2),
    }

    # Detail base: one row per unique (canonical_key, tuik_category) at current date
    detail_base = (
        df_current
        .groupby(["canonical_key", "tuik_category", "sector"], as_index=False)
        .agg(
            product_key=("product_key", "first"),
            store=("store", lambda s: ",".join(sorted(s.unique()))),
        )
    )

    for label, past_str in intervals.items():
        logger.info("Computing interval %s (vs %s) …", label, past_str)
        df_past, _, _ = _load_all_stores(past_str)

        if df_past.empty:
            logger.info("  No past data for %s — skipping interval %s.", past_str, label)
            for key in ["avg_inflation", "basic_index", "tuik_weighted_products",
                        "tuik_weighted_full", "rent_inflation"]:
                summary_row[f"{key}_{label}"] = None
            continue

        product_rel, basic_idx, avg_inf, tuik_w_products = _compute_metrics(df_current, df_past)

        # Attach per-product relative to detail frame
        if not product_rel.empty:
            rel_col = product_rel[["canonical_key", "tuik_category", "relative"]].rename(
                columns={"relative": f"relative_{label}"}
            )
            detail_base = detail_base.merge(rel_col, on=["canonical_key", "tuik_category"], how="left")

        summary_row[f"avg_inflation_{label}"] = avg_inf
        summary_row[f"basic_index_{label}"] = basic_idx
        summary_row[f"tuik_weighted_products_{label}"] = tuik_w_products

        rent_inf = _rent_relative(today_str, past_str)
        summary_row[f"rent_inflation_{label}"] = rent_inf

        if rent_inf is not None and tuik_w_products is not None:
            cat_rel = product_rel.groupby("tuik_category")["relative"].mean()
            cat_rel_full = cat_rel.copy()
            cat_rel_full["04"] = rent_inf
            present_all = list(cat_rel_full.dropna().index)
            norm_w_all = normalised_weights(present_all)
            tuik_w_full = float(sum(
                cat_rel_full[c] * norm_w_all[c] / 100.0
                for c in norm_w_all
                if pd.notna(cat_rel_full.get(c))
            )) if norm_w_all else tuik_w_products
        else:
            tuik_w_full = tuik_w_products
        summary_row[f"tuik_weighted_full_{label}"] = tuik_w_full

        logger.info(
            "  [%s] basic_index=%s  avg=%s  tuik_products=%s  tuik_full=%s",
            label,
            f"{basic_idx:.3f}%" if basic_idx is not None else "N/A",
            f"{avg_inf:.3f}%"   if avg_inf is not None else "N/A",
            f"{tuik_w_products:.3f}%" if tuik_w_products is not None else "N/A",
            f"{tuik_w_full:.3f}%"     if tuik_w_full is not None else "N/A",
        )

    detail_file = _OUT_DIR / f"turkey_inflation_{today_str}.csv"
    detail_base.to_csv(detail_file, index=False, encoding="utf-8")
    logger.info("Saved per-product detail: %s", detail_file)

    summary_file = _OUT_DIR / "turkey_inflation_summary.csv"
    df_new = pd.DataFrame([summary_row])
    try:
        if summary_file.exists():
            df_existing = pd.read_csv(summary_file)
            df_existing = df_existing[df_existing["date"] != today_str]
            df_final = pd.concat([df_existing, df_new], ignore_index=True)
            df_final.to_csv(summary_file, index=False, encoding="utf-8")
        else:
            df_new.to_csv(summary_file, index=False, encoding="utf-8")
        logger.info("Updated summary: %s", summary_file)
    except Exception as e:
        logger.error("Failed to write summary: %s", e)
```

- [ ] **Step 4: Run — expect all 34 tests to pass**

```bash
source venv/bin/activate && python -m pytest tests/test_turkey_inflation.py -v
```

Expected: `34 passed`

- [ ] **Step 5: Remove all now-dead code from `turkey_inflation.py`**

Delete these functions that are replaced by the new architecture (no longer called anywhere):
- All `_load_migros`, `_load_a101`, `_load_gurmar`, `_load_hapeloglu`, `_load_marketzade`, `_load_arden`, `_load_baskent`, `_load_kale`, `_load_kim`, `_load_cagri`, `_load_basdas` functions
- All `_load_civil`, `_load_koton`, `_load_lufian`, `_load_stradivarius`, `_load_vakko`, `_load_adl`, `_load_altinyildiz`, `_load_lcwaikiki`, `_load_loft`, `_load_defacto` functions
- All `_load_samsung`, `_load_dr`, `_load_pozitif`, `_load_beymen_tech`, `_load_huawei` functions
- All `_load_rossmann`, `_load_avon`, `_load_dermomarket`, `_load_goldenrose`, `_load_loccitane`, `_load_watsons` functions
- All `_load_vivense`, `_load_karaca`, `_load_englishhome`, `_load_bellona`, `_load_madamecoco`, `_load_jysk`, `_load_istikbal`, `_load_chakra`, `_load_ikea` functions
- All `_load_bauhaus`, `_load_filtasyapi`, `_load_hausmart`, `_load_nalburadam`, `_load_hancivata`, `_load_nalburcuk`, `_load_nalburdayim`, `_load_sanatyapi`, `_load_tasciyapi`, `_load_yapimaks`, `_load_ereyon`, `_load_afeks` functions
- All `_migros_to_tuik`, `_a101_to_tuik`, `_HAPELOGLU_MAP`, `_hapeloglu_to_tuik`, `_GURMAR_MAP`, `_gurmar_to_tuik`, `_MARKETZADE_MAP`, `_marketzade_to_tuik` functions and maps
- `_load_no_header` function
- `_load_csv` function (replaced by `_load_store_csv`)
- `_load_no_header` function
- `_md`, `_underscore_date`, `_ddmmyyyy`, `_yyyymmdd` date helper functions
- `_sector_avg` function
- `_STORE_LOADERS` list (if still present)
- Old `_STANDARD_COLS` definition (replaced by the new one in Task 3)

- [ ] **Step 6: Run full test suite to confirm nothing broke**

```bash
source venv/bin/activate && python -m pytest tests/test_turkey_inflation.py -v
```

Expected: `34 passed`

- [ ] **Step 7: Smoke-test the CLI directly**

```bash
source venv/bin/activate && python Inflations/Codes/turkey_inflation.py --date 2026-05-26 --compare 2026-05-01
```

Expected: log output showing stores loaded, intervals computed, files written to `Inflations/Datas/Final_Reports/`

- [ ] **Step 8: Commit**

```bash
git add tests/test_turkey_inflation.py Inflations/Codes/turkey_inflation.py
git commit -m "feat: complete turkey_inflation.py rewrite — auto-discover, canonical_key, relative metrics"
```
