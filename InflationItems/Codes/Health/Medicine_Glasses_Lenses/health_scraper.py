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
