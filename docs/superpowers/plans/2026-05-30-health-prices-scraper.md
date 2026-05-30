# Health Prices Scraper Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a single Python scraper that downloads the last 3 months of official Turkish medicine, glasses frame, and eyeglass lens prices from TİTCK and SGK, and saves them as one consolidated CSV under `InflationItems/Datas/Health/Medicine_Glasses_Lenses/`.

**Architecture:** Three focused functions (`fetch_titck_medicine_prices`, `fetch_sgk_optical_prices`, `save_consolidated`) are called in sequence by `main()`. Pure helper functions handle price parsing, optical classification, date extraction, and DataFrame normalisation — these are tested independently of HTTP. HTTP-dependent functions are tested with `unittest.mock`.

**Tech Stack:** `requests`, `beautifulsoup4`, `pandas`, `openpyxl` (for `.xlsx`), `pytest`, `unittest.mock`

---

## File Map

| Action | Path | Responsibility |
|---|---|---|
| Create | `InflationItems/Codes/Health/Medicine_Glasses_Lenses/health_scraper.py` | Entire scraper (all functions + main) |
| Create | `tests/__init__.py` | Make `tests/` a package for pytest discovery |
| Create | `tests/Health/__init__.py` | Make `tests/Health/` a sub-package |
| Create | `tests/Health/test_health_scraper.py` | All unit tests |
| Modify | `requirements.txt` | Add `openpyxl` |
| Created at runtime | `InflationItems/Datas/Health/Medicine_Glasses_Lenses/health_prices_3months.csv` | Final output |

---

## Task 1: Add dependency and scaffold directories

**Files:**
- Modify: `requirements.txt`
- Create: `InflationItems/Codes/Health/Medicine_Glasses_Lenses/health_scraper.py` (empty scaffold)
- Create: `tests/__init__.py`
- Create: `tests/Health/__init__.py`
- Create: `tests/Health/test_health_scraper.py` (empty scaffold)

- [ ] **Step 1: Add openpyxl to requirements.txt**

Open `requirements.txt` and add this line under the `# ── Data & Analysis` block:

```
openpyxl>=3.1.0
```

- [ ] **Step 2: Install openpyxl**

```bash
pip install openpyxl
```

Expected: `Successfully installed openpyxl-...`

- [ ] **Step 3: Create the directory and scaffold health_scraper.py**

Create `InflationItems/Codes/Health/Medicine_Glasses_Lenses/health_scraper.py` with this scaffold (full content will be filled in by later tasks):

```python
from __future__ import annotations

import io
import re
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup

TITCK_URL = "https://www.titck.gov.tr/dinamikmodul/100"
SGK_OPTICAL_URL = (
    "https://www.sgk.gov.tr/Content/Post/"
    "29aa9928-48df-47af-9fc6-03c74da9cc0a/"
    "Optik-Gormeye-Yardimci-Malzeme-Nedir-Ne-Sekilde-Temin-Edilir-"
    "2026-01-09-03-59-14"
)
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "tr,tr-TR;q=0.9,en-US;q=0.8",
}

_SCRIPT_DIR = Path(__file__).resolve().parent
_INFLATION_ITEMS = _SCRIPT_DIR.parents[2]   # InflationItems/Codes/Health/MGL/ → [0]=Health [1]=Codes [2]=InflationItems
OUTPUT_DIR = _INFLATION_ITEMS / "Datas" / "Health" / "Medicine_Glasses_Lenses"
OUTPUT_PATH = OUTPUT_DIR / "health_prices_3months.csv"
```

- [ ] **Step 4: Create empty test package files**

Create `tests/__init__.py` — empty file.
Create `tests/Health/__init__.py` — empty file.

Create `tests/Health/test_health_scraper.py` with this scaffold:

```python
import sys
from pathlib import Path

sys.path.insert(
    0,
    str(Path(__file__).resolve().parents[2] / "InflationItems" / "Codes" / "Health" / "Medicine_Glasses_Lenses"),
)
```

- [ ] **Step 5: Verify pytest can discover the test file**

Run from the project root:
```bash
pytest tests/Health/test_health_scraper.py -v
```
Expected: `no tests ran` (0 collected) — no errors.

- [ ] **Step 6: Commit**

```bash
git add requirements.txt InflationItems/Codes/Health/Medicine_Glasses_Lenses/health_scraper.py tests/
git commit -m "feat: scaffold health scraper and test files, add openpyxl dependency"
```

---

## Task 2: Implement and test pure helper functions

These three helpers have no I/O — test them directly.

**Files:**
- Modify: `InflationItems/Codes/Health/Medicine_Glasses_Lenses/health_scraper.py`
- Modify: `tests/Health/test_health_scraper.py`

- [ ] **Step 1: Write the failing tests for all three helpers**

Append to `tests/Health/test_health_scraper.py`:

```python
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
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
pytest tests/Health/test_health_scraper.py -v
```
Expected: `ImportError: cannot import name '_parse_price' from 'health_scraper'`

- [ ] **Step 3: Implement the three helpers in health_scraper.py**

Add after the `OUTPUT_PATH` line in `health_scraper.py`:

```python
def _parse_price(text: str) -> float | None:
    if not text:
        return None
    cleaned = str(text).replace("TL", "").replace("₺", "").replace("\xa0", "").replace(" ", "").strip()
    if "," in cleaned and "." in cleaned:
        cleaned = cleaned.replace(".", "").replace(",", ".")
    elif "," in cleaned:
        cleaned = cleaned.replace(",", ".")
    try:
        val = float(cleaned)
        return val if val > 0 else None
    except ValueError:
        return None


def _classify_optical(name: str) -> str:
    upper = name.upper()
    if any(k in upper for k in ["ÇERÇEVE", "CERCEVE", "FRAME"]):
        return "Gözlük Çerçevesi"
    return "Gözlük Camı"


def _extract_date_from_url(url: str) -> date | None:
    match = re.search(r"(\d{4})[-_.]?(\d{2})[-_.]?(\d{2})", url)
    if match:
        try:
            return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
        except ValueError:
            return None
    return None
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
pytest tests/Health/test_health_scraper.py -v
```
Expected: `14 passed`

- [ ] **Step 5: Commit**

```bash
git add InflationItems/Codes/Health/Medicine_Glasses_Lenses/health_scraper.py tests/Health/test_health_scraper.py
git commit -m "feat: add and test _parse_price, _classify_optical, _extract_date_from_url helpers"
```

---

## Task 3: Implement and test _normalise_medicine_df

**Files:**
- Modify: `InflationItems/Codes/Health/Medicine_Glasses_Lenses/health_scraper.py`
- Modify: `tests/Health/test_health_scraper.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/Health/test_health_scraper.py`:

```python
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
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
pytest tests/Health/test_health_scraper.py::test_normalise_medicine_df_standard_columns -v
```
Expected: `ImportError: cannot import name '_normalise_medicine_df'`

- [ ] **Step 3: Implement _normalise_medicine_df in health_scraper.py**

Add after `_extract_date_from_url`:

```python
def _normalise_medicine_df(df: pd.DataFrame, snapshot_date: date) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]

    name_col = next(
        (c for c in df.columns if any(k in c.upper() for k in ["İLAÇ", "ILAC", "ÜRÜN", "URUN", "ADI", "NAME"])),
        df.columns[0],
    )
    price_col = next(
        (c for c in df.columns if any(k in c.upper() for k in ["FİYAT", "FIYAT", "PRICE", "PSF", "KDV", "SATIŞ"])),
        None,
    )
    if price_col is None:
        print(f"  ⚠ No price column detected. Columns: {list(df.columns)}")
        return pd.DataFrame()

    result = pd.DataFrame({
        "date": snapshot_date.strftime("%Y-%m-%d"),
        "product-name": df[name_col].astype(str).str.strip(),
        "product-price": df[price_col].apply(lambda x: _parse_price(str(x))),
        "category": "İlaç",
        "source": "TİTCK",
    })
    return result[
        result["product-price"].notna()
        & (result["product-name"] != "")
        & (result["product-name"] != "nan")
    ].reset_index(drop=True)
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
pytest tests/Health/test_health_scraper.py -v
```
Expected: `17 passed`

- [ ] **Step 5: Commit**

```bash
git add InflationItems/Codes/Health/Medicine_Glasses_Lenses/health_scraper.py tests/Health/test_health_scraper.py
git commit -m "feat: add and test _normalise_medicine_df"
```

---

## Task 4: Implement and test fetch_titck_medicine_prices

**Files:**
- Modify: `InflationItems/Codes/Health/Medicine_Glasses_Lenses/health_scraper.py`
- Modify: `tests/Health/test_health_scraper.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/Health/test_health_scraper.py`:

```python
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
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
pytest tests/Health/test_health_scraper.py::test_fetch_titck_returns_dataframe_on_success -v
```
Expected: `ImportError: cannot import name 'fetch_titck_medicine_prices'`

- [ ] **Step 3: Implement fetch_titck_medicine_prices in health_scraper.py**

Add after `_normalise_medicine_df`:

```python
def fetch_titck_medicine_prices() -> pd.DataFrame:
    cutoff = date.today() - timedelta(days=90)

    try:
        resp = requests.get(TITCK_URL, headers=HEADERS, timeout=20)
        resp.raise_for_status()
    except requests.RequestException as exc:
        print(f"⚠ TİTCK unreachable: {exc}")
        return pd.DataFrame()

    soup = BeautifulSoup(resp.text, "html.parser")
    excel_hrefs = [
        a["href"] for a in soup.find_all("a", href=True)
        if a["href"].lower().endswith((".xls", ".xlsx"))
    ]

    if not excel_hrefs:
        print("⚠ No Excel links found on TİTCK page.")
        return pd.DataFrame()

    dated: list[tuple[date, str]] = []
    for href in excel_hrefs:
        d = _extract_date_from_url(href)
        if d is None or d >= cutoff:
            dated.append((d or date.today(), href))

    if not dated:
        print("⚠ No files within 3-month window. Using latest available.")
        dated = [(date.today(), excel_hrefs[0])]

    base = "https://www.titck.gov.tr"
    frames = []
    for snap_date, href in dated:
        url = href if href.startswith("http") else base + href
        try:
            r = requests.get(url, headers=HEADERS, timeout=60)
            r.raise_for_status()
            df = pd.read_excel(io.BytesIO(r.content))
            normed = _normalise_medicine_df(df, snap_date)
            if not normed.empty:
                frames.append(normed)
                print(f"  ✓ {snap_date} — {len(normed):,} medicines")
        except Exception as exc:
            print(f"  ⚠ Skipping {href}: {exc}")

    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
pytest tests/Health/test_health_scraper.py -v
```
Expected: `20 passed`

- [ ] **Step 5: Commit**

```bash
git add InflationItems/Codes/Health/Medicine_Glasses_Lenses/health_scraper.py tests/Health/test_health_scraper.py
git commit -m "feat: add and test fetch_titck_medicine_prices"
```

---

## Task 5: Implement and test fetch_sgk_optical_prices

**Files:**
- Modify: `InflationItems/Codes/Health/Medicine_Glasses_Lenses/health_scraper.py`
- Modify: `tests/Health/test_health_scraper.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/Health/test_health_scraper.py`:

```python
from health_scraper import fetch_sgk_optical_prices


SAMPLE_SGK_HTML = """
<html><body>
<table>
  <tr><td>Tek Odaklı Cam (sferik ≤4 dioptri)</td><td>150,00 TL</td></tr>
  <tr><td>Çerçeve (14 yaş altı)</td><td>200,00 TL</td></tr>
  <tr><td>Progressif Cam</td><td>300,00 TL</td></tr>
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
    assert len(frame_rows) == 1
    assert frame_rows["product-price"].iloc[0] == 200.0


def test_fetch_sgk_optical_returns_empty_on_network_error():
    with patch("health_scraper.requests.get", side_effect=req_lib.RequestException("timeout")):
        result = fetch_sgk_optical_prices()
    assert result.empty
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
pytest tests/Health/test_health_scraper.py::test_fetch_sgk_optical_returns_dataframe -v
```
Expected: `ImportError: cannot import name 'fetch_sgk_optical_prices'`

- [ ] **Step 3: Implement fetch_sgk_optical_prices in health_scraper.py**

Add after `fetch_titck_medicine_prices`:

```python
def fetch_sgk_optical_prices() -> pd.DataFrame:
    try:
        resp = requests.get(SGK_OPTICAL_URL, headers=HEADERS, timeout=20)
        resp.raise_for_status()
    except requests.RequestException as exc:
        print(f"⚠ SGK page unreachable: {exc}")
        return pd.DataFrame()

    soup = BeautifulSoup(resp.text, "html.parser")
    today = date.today().strftime("%Y-%m-%d")
    rows = []

    for table in soup.find_all("table"):
        for tr in table.find_all("tr"):
            cells = [td.get_text(" ", strip=True) for td in tr.find_all(["td", "th"])]
            if len(cells) < 2:
                continue
            name = cells[0].strip()
            price = _parse_price(cells[1])
            if not name or price is None:
                continue
            rows.append({
                "date": today,
                "product-name": name,
                "product-price": price,
                "category": _classify_optical(name),
                "source": "SGK",
            })

    if not rows:
        print("⚠ No optical rows parsed from SGK page.")
    else:
        print(f"  ✓ {len(rows)} optical products from SGK")

    return pd.DataFrame(rows)
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
pytest tests/Health/test_health_scraper.py -v
```
Expected: `22 passed`

- [ ] **Step 5: Commit**

```bash
git add InflationItems/Codes/Health/Medicine_Glasses_Lenses/health_scraper.py tests/Health/test_health_scraper.py
git commit -m "feat: add and test fetch_sgk_optical_prices"
```

---

## Task 6: Implement and test save_consolidated, then wire up main()

**Files:**
- Modify: `InflationItems/Codes/Health/Medicine_Glasses_Lenses/health_scraper.py`
- Modify: `tests/Health/test_health_scraper.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/Health/test_health_scraper.py`:

```python
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
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
pytest tests/Health/test_health_scraper.py::test_save_consolidated_writes_correct_csv -v
```
Expected: `ImportError: cannot import name 'save_consolidated'`

- [ ] **Step 3: Implement save_consolidated and main() in health_scraper.py**

Add after `fetch_sgk_optical_prices`:

```python
def save_consolidated(medicines_df: pd.DataFrame, optical_df: pd.DataFrame) -> None:
    frames = [df for df in (medicines_df, optical_df) if not df.empty]
    if not frames:
        print("❌ No data collected — output file not written.")
        return

    combined = pd.concat(frames, ignore_index=True)
    combined = combined[["date", "product-name", "product-price", "category", "source"]]
    combined = combined.dropna(subset=["product-price"])

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    combined.to_csv(OUTPUT_PATH, index=False, encoding="utf-8-sig")
    print(f"\n✅ {len(combined):,} rows saved → {OUTPUT_PATH}")


def main() -> None:
    print("=" * 55)
    print("HEALTH PRICES SCRAPER")
    print("=" * 55)

    print("\n💊 Fetching medicine prices from TİTCK...")
    medicines_df = fetch_titck_medicine_prices()

    print("\n👓 Fetching optical prices from SGK...")
    optical_df = fetch_sgk_optical_prices()

    save_consolidated(medicines_df, optical_df)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run all tests to confirm they pass**

```bash
pytest tests/Health/test_health_scraper.py -v
```
Expected: `25 passed`

- [ ] **Step 5: Commit**

```bash
git add InflationItems/Codes/Health/Medicine_Glasses_Lenses/health_scraper.py tests/Health/test_health_scraper.py
git commit -m "feat: add save_consolidated, main(), and their tests — scraper feature complete"
```

---

## Task 7: Run the scraper live and verify output

- [ ] **Step 1: Run the scraper from the project root**

```bash
python InflationItems/Codes/Health/Medicine_Glasses_Lenses/health_scraper.py
```

Expected output (approximate):
```
=======================================================
HEALTH PRICES SCRAPER
=======================================================

💊 Fetching medicine prices from TİTCK...
  ✓ 2026-03-01 — 14,523 medicines
  ✓ 2026-04-01 — 14,612 medicines

👓 Fetching optical prices from SGK...
  ✓ 8 optical products from SGK

✅ 29,143 rows saved → .../InflationItems/Datas/Health/Medicine_Glasses_Lenses/health_prices_3months.csv
```

If TİTCK is unreachable: `⚠ TİTCK unreachable: ...` — this is expected; the SGK data should still be saved.
If the medicine Excel column names differ from expected, you will see `⚠ No price column detected. Columns: [...]` — update the keyword list in `_normalise_medicine_df` to match the actual column names shown.

- [ ] **Step 2: Verify the output file**

```bash
python -c "
import pandas as pd
df = pd.read_csv('InflationItems/Datas/Health/Medicine_Glasses_Lenses/health_prices_3months.csv', encoding='utf-8-sig')
print('Shape:', df.shape)
print('Columns:', list(df.columns))
print('Categories:', df['category'].value_counts().to_dict())
print(df.head(3))
"
```

Expected: columns are `['date', 'product-name', 'product-price', 'category', 'source']`, categories include `İlaç`, `Gözlük Camı`, `Gözlük Çerçevesi`.

- [ ] **Step 3: Commit the output data file**

```bash
git add InflationItems/Datas/Health/Medicine_Glasses_Lenses/health_prices_3months.csv
git commit -m "data: add 3-month health prices snapshot (medicine, glasses, lenses)"
```
