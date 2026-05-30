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
