import pytest
import pandas as pd
from pathlib import Path

from turkey_inflation import _has_standard_header, _find_date_csv, _load_store_csv
from turkey_inflation import _load_sector, _load_all_stores, _SECTOR_CONFIG, _DATA_ROOT
from turkey_inflation import _rent_city_prices, _rent_relative
import turkey_inflation


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


def _make_rent_city(base: Path, city: str, date: str, prices: list) -> None:
    d = base / "HousesRent" / city
    d.mkdir(parents=True, exist_ok=True)
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
