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
