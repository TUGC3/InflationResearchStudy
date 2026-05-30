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
