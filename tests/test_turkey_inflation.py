import pytest
import pandas as pd
from pathlib import Path

from turkey_inflation import _has_standard_header, _find_date_csv, _load_store_csv


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
