import sys
from pathlib import Path

sys.path.insert(
    0,
    str(Path(__file__).resolve().parents[2] / "InflationItems" / "Codes" / "Health" / "Medicine_Glasses_Lenses"),
)

from health_scraper import _parse_price, _classify_optical, _extract_date_from_url
from datetime import date


# ── _parse_price ──────────────────────────────────────────────────────────────

def test_parse_price_standard_decimal():
    assert _parse_price("45.50") == 45.50

def test_parse_price_turkish_decimal():
    assert _parse_price("45,50") == 45.50

def test_parse_price_turkish_thousands():
    assert _parse_price("1.234,56") == 1234.56

def test_parse_price_with_tl_suffix():
    assert _parse_price("99,90 TL") == 99.90

def test_parse_price_empty_returns_none():
    assert _parse_price("") is None

def test_parse_price_non_numeric_returns_none():
    assert _parse_price("Fiyat yok") is None

def test_parse_price_zero_returns_none():
    assert _parse_price("0") is None


# ── _classify_optical ─────────────────────────────────────────────────────────

def test_classify_optical_frame():
    assert _classify_optical("Gözlük Çerçevesi") == "Gözlük Çerçevesi"

def test_classify_optical_frame_uppercase():
    assert _classify_optical("ÇERÇEVE 14 yaş altı") == "Gözlük Çerçevesi"

def test_classify_optical_lens():
    assert _classify_optical("Tek Odaklı Cam") == "Gözlük Camı"

def test_classify_optical_progressive():
    assert _classify_optical("Progressif Cam") == "Gözlük Camı"


# ── _extract_date_from_url ────────────────────────────────────────────────────

def test_extract_date_dashed():
    assert _extract_date_from_url("/files/liste-2026-03-15.xlsx") == date(2026, 3, 15)

def test_extract_date_underscored():
    assert _extract_date_from_url("/files/liste_20260301.xlsx") == date(2026, 3, 1)

def test_extract_date_no_date_returns_none():
    assert _extract_date_from_url("/files/guncel_liste.xlsx") is None


# ── _normalise_medicine_df ────────────────────────────────────────────────────

import pandas as pd
from health_scraper import _normalise_medicine_df


def test_normalise_medicine_df_standard_columns():
    raw = pd.DataFrame({
        "İlaç Adı": ["Aspirin 100mg", "Parol 500mg"],
        "Fiyat":    ["45,50",          "32,00"],
        "Barkod":   ["1234567890",      "0987654321"],
    })
    result = _normalise_medicine_df(raw, date(2026, 3, 1))
    assert list(result.columns) == ["date", "product-name", "product-price", "category", "source"]
    assert result["date"].iloc[0] == "2026-03-01"
    assert result["product-name"].iloc[0] == "Aspirin 100mg"
    assert result["product-price"].iloc[0] == 45.50
    assert result["category"].iloc[0] == "İlaç"
    assert result["source"].iloc[0] == "TİTCK"


def test_normalise_medicine_df_drops_unparseable_prices():
    raw = pd.DataFrame({
        "İlaç Adı": ["Aspirin", "Bilinmiyor"],
        "Fiyat":    ["45,50",   "N/A"],
    })
    result = _normalise_medicine_df(raw, date(2026, 3, 1))
    assert len(result) == 1
    assert result["product-name"].iloc[0] == "Aspirin"


def test_normalise_medicine_df_no_price_column_returns_empty():
    raw = pd.DataFrame({"İlaç Adı": ["X"], "Barkod": ["123"]})
    result = _normalise_medicine_df(raw, date(2026, 3, 1))
    assert result.empty
