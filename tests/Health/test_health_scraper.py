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

def test_extract_date_archive_year_path():
    url = "https://titck.gov.tr/storage/Archive/2026/dynamicModulesAttachment/LISTE.xlsx"
    assert _extract_date_from_url(url) == date(2026, 12, 31)

def test_extract_date_uuid_digits_rejected_falls_back_to_archive():
    # UUID like ede284aa-9979-4009-b573-... would produce year 9979 — rejected
    url = "https://titck.gov.tr/storage/Archive/2026/dma/FILE_ede284aa-9979-4009-b573.xlsx"
    assert _extract_date_from_url(url) == date(2026, 12, 31)

def test_extract_date_archive_old_year_excluded_by_cutoff():
    url = "https://titck.gov.tr/storage/Archive/2023/dynamicModulesAttachment/LISTE.xlsx"
    assert _extract_date_from_url(url) == date(2023, 12, 31)


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


# ── fetch_titck_medicine_prices ───────────────────────────────────────────────

import io
import requests as req_lib
from unittest.mock import MagicMock, patch
from health_scraper import fetch_titck_medicine_prices


SAMPLE_TITCK_HTML = """
<html><body>
<a href="/files/liste-2026-03-01.xlsx">Mart 2026</a>
<a href="/files/liste-2026-04-01.xlsx">Nisan 2026</a>
</body></html>
"""

def _make_excel_bytes(data: dict) -> bytes:
    buf = io.BytesIO()
    pd.DataFrame(data).to_excel(buf, index=False)
    return buf.getvalue()


def test_fetch_titck_returns_dataframe_on_success():
    excel_bytes = _make_excel_bytes({"İlaç Adı": ["Aspirin 100mg"], "Fiyat": ["45,50"]})

    html_mock = MagicMock()
    html_mock.text = SAMPLE_TITCK_HTML
    html_mock.raise_for_status = MagicMock()

    excel_mock = MagicMock()
    excel_mock.content = excel_bytes
    excel_mock.raise_for_status = MagicMock()

    with patch("health_scraper.requests.get", side_effect=[html_mock, excel_mock, excel_mock]):
        result = fetch_titck_medicine_prices()

    assert not result.empty
    assert "product-name" in result.columns
    assert "product-price" in result.columns
    assert (result["category"] == "İlaç").all()
    assert (result["source"] == "TİTCK").all()


def test_fetch_titck_returns_empty_on_network_error():
    with patch("health_scraper.requests.get", side_effect=req_lib.RequestException("timeout")):
        result = fetch_titck_medicine_prices()
    assert result.empty


def test_fetch_titck_returns_empty_when_no_excel_links():
    html_mock = MagicMock()
    html_mock.text = "<html><body><p>no links</p></body></html>"
    html_mock.raise_for_status = MagicMock()

    with patch("health_scraper.requests.get", return_value=html_mock):
        result = fetch_titck_medicine_prices()
    assert result.empty


# ── fetch_sgk_optical_prices ──────────────────────────────────────────────

from health_scraper import fetch_sgk_optical_prices


SAMPLE_SGK_HTML = """
<html><body>
<table>
  <tr><th>KURUM VE KURULUŞLAR</th><th>ÇERÇEVE</th><th>CAM</th></tr>
  <tr><td>GARANTİ BANKASI(2026)</td><td>2.025,00 TL</td><td>2.025,00 TL</td></tr>
  <tr><td>İŞ BANKASI(2026)</td><td>2.750,00 TL</td><td>2.750,00 TL</td></tr>
</table>
</body></html>
"""


def test_fetch_sgk_optical_returns_dataframe():
    mock_resp = MagicMock()
    mock_resp.text = SAMPLE_SGK_HTML
    mock_resp.raise_for_status = MagicMock()

    with patch("health_scraper.requests.get", return_value=mock_resp):
        result = fetch_sgk_optical_prices()

    assert not result.empty
    assert set(result["category"].unique()).issubset({"Gözlük Camı", "Gözlük Çerçevesi"})
    assert (result["source"] == "SGK").all()
    frame_rows = result[result["category"] == "Gözlük Çerçevesi"]
    assert len(frame_rows) == 2  # 2 institutions × 1 frame each
    assert frame_rows["product-price"].iloc[0] == 2025.0


def test_fetch_sgk_optical_returns_empty_on_network_error():
    with patch("health_scraper.requests.get", side_effect=req_lib.RequestException("timeout")):
        result = fetch_sgk_optical_prices()
    assert result.empty


# ── save_consolidated ─────────────────────────────────────────────────────────

import health_scraper
from health_scraper import save_consolidated


def _make_medicine_df() -> pd.DataFrame:
    return pd.DataFrame({
        "date": ["2026-03-01"],
        "product-name": ["Aspirin 100mg"],
        "product-price": [45.50],
        "category": ["İlaç"],
        "source": ["TİTCK"],
    })


def _make_optical_df() -> pd.DataFrame:
    return pd.DataFrame({
        "date": ["2026-05-30"],
        "product-name": ["Tek Odaklı Cam"],
        "product-price": [150.0],
        "category": ["Gözlük Camı"],
        "source": ["SGK"],
    })


def test_save_consolidated_writes_correct_csv(tmp_path):
    health_scraper.OUTPUT_DIR = tmp_path
    health_scraper.OUTPUT_PATH = tmp_path / "health_prices_3months.csv"

    save_consolidated(_make_medicine_df(), _make_optical_df())

    assert health_scraper.OUTPUT_PATH.exists()
    result = pd.read_csv(health_scraper.OUTPUT_PATH)
    assert len(result) == 2
    assert list(result.columns) == ["date", "product-name", "product-price", "category", "source"]
    assert set(result["category"]) == {"İlaç", "Gözlük Camı"}


def test_save_consolidated_column_order(tmp_path):
    health_scraper.OUTPUT_DIR = tmp_path
    health_scraper.OUTPUT_PATH = tmp_path / "health_prices_3months.csv"

    save_consolidated(_make_medicine_df(), pd.DataFrame())

    result = pd.read_csv(health_scraper.OUTPUT_PATH)
    assert list(result.columns) == ["date", "product-name", "product-price", "category", "source"]


def test_save_consolidated_both_empty_does_not_write(tmp_path):
    health_scraper.OUTPUT_DIR = tmp_path
    health_scraper.OUTPUT_PATH = tmp_path / "health_prices_3months.csv"

    save_consolidated(pd.DataFrame(), pd.DataFrame())

    assert not health_scraper.OUTPUT_PATH.exists()
