"""
turkey_inflation.py — Turkey-Wide Daily Inflation Calculator

Aggregates all tracked data sources in the InflationResearchStudy codebase across
six sectors and computes three inflation metrics identical to those in Migros/inflation.py:

  1. Basic Inflation   – basket-level price index change (%)
                        (sum_current / sum_past - 1) × 100
  2. Average Inflation – arithmetic mean of per-product percentage changes
  3. TUIK Weighted Avg – weighted average using TÜİK 2026 COICOP basket weights,
                         normalised to the TUIK categories present in the data

Sectors and TUIK groups covered:
  Grocery markets  → group 01  (Gıda ve alkolsüz içecekler)
  Clothing stores  → group 03  (Giyim ve ayakkabı)
  Rent / housing   → group 04  (Konut, su, elektrik, gaz)
  HomeGoods +
  Construction     → group 05  (Mobilya, ev aletleri)
  Tech products    → group 08  (Bilgi ve iletişim)
  Cosmetics        → group 13  (Kişisel bakım)

Deduplication:
  Products appearing in multiple stores within the same TUIK category are matched
  by normalised name (Turkish diacritics stripped, lowercased). Their current and
  past prices are averaged across stores before the basket calculation, preventing
  any product from carrying excess weight.

Rent treatment:
  Rent data is aggregate (city/district level), not product-level.  It is computed
  as a mean rent price change across all cities and injected directly into the
  TUIK-weighted metric as group 04.  It does not appear in the basic-index or
  average-inflation metrics, which are product-level only.

Output files (Inflations/Datas/Final_Reports/):
  turkey_inflation_{YYYY-MM-DD}.csv  — per-product rows with basic_inflation columns,
                                       plus tuik_category, sector, store fields
  turkey_inflation_summary.csv        — time-series row appended per run with all
                                       three metrics per interval plus per-sector
                                       breakdown and data-quality metadata

Usage:
    python turkey_inflation.py                    # today, 1d / 7d / 15d / 30d
    python turkey_inflation.py --date 2026-05-01  # specific target date
    python turkey_inflation.py --date 2026-05-01 --compare 2026-04-01
"""

import logging
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

# ── Path setup ────────────────────────────────────────────────────────────────
_THIS_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _THIS_DIR.parent.parent          # InflationResearchStudy/

sys.path.insert(0, str(_THIS_DIR))
from tuik_config import normalised_weights, TUIK_WEIGHTS

_DATA_ROOT = _PROJECT_ROOT / "InflationItems" / "Datas"
_OUT_DIR = _PROJECT_ROOT / "Inflations" / "Datas" / "Final_Reports"

logger = logging.getLogger(__name__)

# ── Turkish character normalisation ───────────────────────────────────────────
_TR_MAP = str.maketrans("ıİğĞşŞçÇöÖüÜ", "iIgGsScCoOuU")


def _norm(s: str) -> str:
    """Normalise a product name for cross-store deduplication."""
    if not isinstance(s, str):
        return ""
    return re.sub(r"\s+", " ", s.translate(_TR_MAP).lower().strip())


# ── Price parsing ─────────────────────────────────────────────────────────────

def _parse_price(x) -> float | None:
    """
    Parse a price from any format observed in the codebase:
      - Pure numeric (float / int)
      - Turkish: "1.234,56" or "1.250.000" or "149,50"
      - Lira prefix/suffix: "₺149,50"  /  "34,99 ₺"  /  "2.475,00TL"
      - Complex prefix: "Başlangıç:  129.999,00 ₺"
      - Single dot with 3 trailing digits: "50.499" → 50499 (Turkish thousands)
    """
    if x is None:
        return None
    if isinstance(x, (int, float)):
        return None if pd.isna(x) else float(x)

    s = str(x).strip()
    if not s:
        return None

    # Strip lira symbol, TL / TRY suffix, leading labels like "Başlangıç:"
    s = re.sub(r"₺|\bTL\b|\bTRY\b", "", s, flags=re.IGNORECASE).strip()
    # Strip trailing non-numeric suffix (e.g. "/Kg")
    s = re.sub(r"[^\d.,]+$", "", s).strip()
    # If complex prefix remains, extract the longest numeric token (= the price)
    if not re.match(r"^[\d.,]+$", s):
        m = re.findall(r"\d[\d,.]*\d|\d", s)
        if not m:
            return None
        s = max(m, key=len)

    # Normalise separators
    if "." in s and "," in s:
        if s.index(".") < s.index(","):
            # Turkish: "1.234,56"
            s = s.replace(".", "").replace(",", ".")
        else:
            # English thousands: "1,234.56"
            s = s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".")
    elif s.count(".") > 1:
        # Multiple dots → Turkish thousands "1.250.000"
        s = s.replace(".", "")
    elif re.match(r"^\d+\.\d{3}$", s):
        # Single dot with exactly 3 trailing digits: "50.499" → 50499
        s = s.replace(".", "")

    try:
        v = float(s)
        return v if v > 0 else None
    except ValueError:
        return None


# ── File header validation ────────────────────────────────────────────────────

_SKIP_SUBDIRS = {"InflationData", "output", "reports", "archive"}


def _has_standard_header(fpath: Path) -> bool:
    try:
        with fpath.open(encoding="utf-8", errors="ignore") as fh:
            first = fh.readline().strip().lstrip("﻿")
        return first == "product_name,price"
    except Exception:
        return False


def _find_date_csv(store_dir: Path, date_token: str) -> Path | None:
    for f in store_dir.rglob(f"*{date_token}*.csv"):
        rel_parts = f.relative_to(store_dir).parts[:-1]
        if any(p in _SKIP_SUBDIRS for p in rel_parts):
            continue
        if _has_standard_header(f):
            return f
    return None


def _load_store_csv(fpath: Path, store: str, sector: str, tuik_code: str) -> pd.DataFrame | None:
    try:
        df = pd.read_csv(fpath, dtype=str, on_bad_lines="skip")
        df.columns = [c.lstrip("﻿").strip() for c in df.columns]
        if "product_name" not in df.columns or "price" not in df.columns:
            return None
        out = pd.DataFrame()
        out["product_key"] = df["product_name"].astype(str).str.strip()
        out["canonical_key"] = out["product_key"].apply(_norm)
        # Filter out prices that have a leading minus sign
        out["price"] = df["price"].apply(
            lambda x: _parse_price(x) if (x is None or not str(x).strip().startswith("-")) else None
        )
        out["store"] = store
        out["sector"] = sector
        out["tuik_category"] = tuik_code
        out = out[out["canonical_key"] != ""].dropna(subset=["price"])
        out = out[out["price"] > 0].reset_index(drop=True)
        return out if not out.empty else None
    except Exception as e:
        logger.debug("%s: failed to load %s — %s", store, fpath.name, e)
        return None


# ── TUIK category mappers (inlined from per-store configs) ────────────────────

def _migros_to_tuik(cat: str) -> str:
    """Map a Migros category string to its TUIK 2-digit group code."""
    if not isinstance(cat, str):
        return "01"
    c = cat.strip()
    kw12 = ["Şampuan", "Krem", "Deodorant", "Parfüm", "Makyaj", "Tıraş", "Diş",
             "Ağız", "Ağda", "Saç ", "Oje", "Güzellik", "Nemlendirici", "Vücut",
             "Kolonya", "Güneş", "Islak Mendil", "Bebek", "Bez ", "Mama ", "Emzik",
             "Losyon", "Göz Kremi", "Yüz Temizleyici", "Peeling", "Tonik",
             "Serum", "Ruj", "Maskara", "Fondöten"]
    kw05 = ["Temizlik", "Deterjan", "Çamaşır", "Bulaşık", "Tencere", "Tava",
             "Bıçak", "Süpürge", "Pil ", "Ampul", "Mop", "Fırça", "Klozet",
             "Çöp", "Naylon", "Folyo", "Streç", "Ev Bakım", "Yüzey", "Kova",
             "Havlu Kağıt", "Kağıt Havlu", "Tuvalet Kağıdı", "Peçete",
             "Ütü", "Çakmak", "Mum ", "Priz", "Uzatma", "Hortum", "Bahçe",
             "Yapıştırıcı", "Vinil", "Plastik", "Cam ", "Ayna"]
    kw09 = ["Kitap", "Dergi", "Oyuncak", "Spor", "Kamp", "Müzik", "Film",
             "Puzzle", "Boyama", "Satranç", "Evcil Hayvan", "Kedi ", "Köpek "]
    kw06 = ["İlk Yardım", "Hasta", "Takviye"]
    kw08 = ["Telefon", "Tablet", "HDMI", "Kulaklık", "Televizyon", "Şarj"]
    kw07 = ["Oto ", "Araç "]
    kw02 = ["Malt İçeceği", "Sigara"]
    kw03 = ["Giyim", "Çorap", "İç Çamaşır", "Pijama", "Bere", "Eldiven"]
    for kw in kw12:
        if kw in c:
            return "12"
    for kw in kw05:
        if kw in c:
            return "05"
    for kw in kw09:
        if kw in c:
            return "09"
    for kw in kw06:
        if kw in c:
            return "06"
    for kw in kw08:
        if kw in c:
            return "08"
    for kw in kw07:
        if kw in c:
            return "07"
    for kw in kw02:
        if kw in c:
            return "02"
    for kw in kw03:
        if kw in c:
            return "03"
    return "01"


def _a101_to_tuik(cat: str) -> str:
    if not isinstance(cat, str):
        return "01"
    c = cat.lower()
    if any(x in c for x in ["meyve", "sebze", "et", "tavuk", "süt", "sut", "kahvalt",
                              "gıda", "gida", "atıştırma", "atistirma", "içecek", "icecek",
                              "yemek", "meze", "dondurma", "fırın", "firin"]):
        return "01"
    if any(x in c for x in ["temizlik", "kağıt", "kagit", "ev yaşam", "ev yasam"]):
        return "05"
    if any(x in c for x in ["kişisel", "kisisel", "bebek", "sağlık", "saglik"]):
        return "12"
    if "elektronik" in c:
        return "08"
    if "evcil" in c:
        return "09"
    return "01"


_HAPELOGLU_MAP = {
    "Atıştırmalık": "01", "Et, Tavuk, Balık": "01", "Fırın, Pastane": "01",
    "Meyve, Sebze": "01", "Süt, Kahvaltılık": "01", "Temel Gıda": "01",
    "İçecek": "01", "Deterjan, Temizlik": "05", "Ev, Yaşam": "05",
    "Kişisel Bakım, Kozmetik": "12", "Kağıt, Islak Mendil": "12", "Evcil Hayvan": "12",
}


def _hapeloglu_to_tuik(cat: str) -> str:
    return _HAPELOGLU_MAP.get(str(cat).strip(), "01") if isinstance(cat, str) else "01"


_GURMAR_MAP = {
    "Meyve ve Sebze": "01", "Et ve Tavuk": "01", "Süt, Kahvaltılık, Sark.": "01",
    "Temel Gıda": "01", "İçecekler": "01", "Atıştırmalıklar": "01",
    "Bebek Ürünleri": "12", "Deterjan ve Temizlik": "05", "Kişisel Bakım": "12",
    "Ev ve Yaşam": "05", "Kitap, Kırtasiye": "09", "Petshop": "09",
}


def _gurmar_to_tuik(cat: str) -> str:
    return _GURMAR_MAP.get(str(cat).strip(), "01") if isinstance(cat, str) else "01"


_MARKETZADE_MAP = {
    "temel-gida": "01", "kahvaltilik": "01", "atistirmalik": "01", "icecek": "01",
    "anne-bebek": "06", "kisisel-bakim": "13", "temizlik": "05", "ev-yasam": "05",
    "petshop": "01",
}


def _marketzade_to_tuik(cat: str) -> str:
    return _MARKETZADE_MAP.get(str(cat).strip().lower(), "01") if isinstance(cat, str) else "01"


# ── Generic CSV loader ────────────────────────────────────────────────────────

_STANDARD_COLS = ["canonical_key", "product_key", "price", "store", "sector", "tuik_category"]


def _load_csv(
    fpath: Path,
    name_col: str,
    price_col: str,
    store: str,
    sector: str,
    default_tuik: str,
    sep: str = ",",
    category_col: str | None = None,
    tuik_mapper=None,
    encoding: str = "utf-8",
    skip_rows: int = 0,
) -> pd.DataFrame | None:
    """Load one store CSV and return a normalised DataFrame or None on failure."""
    if not fpath.exists():
        return None
    try:
        df = pd.read_csv(
            fpath, sep=sep, encoding=encoding,
            skiprows=skip_rows, on_bad_lines="skip",
            dtype=str,
        )
        # Strip BOM from column names
        df.columns = [c.lstrip("﻿").strip() for c in df.columns]

        if name_col not in df.columns:
            logger.debug("%s: name column '%s' not found in %s", store, name_col, fpath.name)
            return None
        if price_col not in df.columns:
            logger.debug("%s: price column '%s' not found in %s", store, price_col, fpath.name)
            return None

        out = pd.DataFrame()
        out["product_key"] = df[name_col].astype(str).str.strip()
        out["price"] = df[price_col].apply(_parse_price)
        out["store"] = store
        out["sector"] = sector

        if category_col and category_col in df.columns and tuik_mapper:
            out["tuik_category"] = df[category_col].apply(
                lambda c: tuik_mapper(c) if pd.notna(c) else default_tuik
            )
        else:
            out["tuik_category"] = default_tuik

        out = out.dropna(subset=["price"]).reset_index(drop=True)
        out = out[out["price"] > 0].reset_index(drop=True)
        return out if not out.empty else None
    except Exception as e:
        logger.debug("%s: failed to load %s — %s", store, fpath.name, e)
        return None


def _load_no_header(
    fpath: Path,
    store: str,
    sector: str,
    default_tuik: str,
    sep: str = ",",
    name_idx: int = 0,
    price_idx: int = 1,
) -> pd.DataFrame | None:
    """Load a CSV with no header row."""
    if not fpath.exists():
        return None
    try:
        df = pd.read_csv(fpath, sep=sep, header=None, on_bad_lines="skip", dtype=str)
        out = pd.DataFrame()
        out["product_key"] = df.iloc[:, name_idx].astype(str).str.strip()
        out["price"] = df.iloc[:, price_idx].apply(_parse_price)
        out["store"] = store
        out["sector"] = sector
        out["tuik_category"] = default_tuik
        out = out.dropna(subset=["price"])
        out = out[out["price"] > 0].reset_index(drop=True)
        return out if not out.empty else None
    except Exception as e:
        logger.debug("%s: failed to load %s — %s", store, fpath.name, e)
        return None


# ── Date-pattern helpers ───────────────────────────────────────────────────────

def _md(date_str: str) -> str:
    """'2026-03-10' → '3-10'  (month-day, no leading zeros)."""
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    return f"{dt.month}-{dt.day}"


def _underscore_date(date_str: str) -> str:
    """'2026-05-22' → '2026_05_22'."""
    return date_str.replace("-", "_")


def _ddmmyyyy(date_str: str) -> str:
    """'2026-05-22' → '22-05-2026'."""
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    return dt.strftime("%d-%m-%Y")


def _yyyymmdd(date_str: str) -> str:
    """'2026-03-01' → '20260301'."""
    return date_str.replace("-", "")


# ── Per-store loader functions ────────────────────────────────────────────────

def _load_migros(date_str: str) -> pd.DataFrame | None:
    d = _DATA_ROOT / "Markets" / "Migros"
    return _load_csv(d / f"migros_{date_str}.csv", "id", "shown_price",
                     "Migros", "market", "01",
                     category_col="category", tuik_mapper=_migros_to_tuik)


def _load_a101(date_str: str) -> pd.DataFrame | None:
    d = _DATA_ROOT / "Markets" / "A101"
    df = _load_csv(d / f"a101_kapida_{date_str}.csv", "urun_id", "fiyat",
                   "A101", "market", "01",
                   category_col="ana_kategori", tuik_mapper=_a101_to_tuik)
    return df


def _load_gurmar(date_str: str) -> pd.DataFrame | None:
    d = _DATA_ROOT / "Markets" / "Gurmar"
    return _load_csv(d / f"gurmar_prices_{date_str}.csv", "product-name", "product-price",
                     "Gurmar", "market", "01", sep=";")


def _load_hapeloglu(date_str: str) -> pd.DataFrame | None:
    d = _DATA_ROOT / "Markets" / "Hapeloglu"
    return _load_csv(d / f"hapeloglu_{date_str}.csv", "Product Name", "Product Cost",
                     "Hapeloglu", "market", "01",
                     category_col="category", tuik_mapper=_hapeloglu_to_tuik)


def _load_marketzade(date_str: str) -> pd.DataFrame | None:
    d = _DATA_ROOT / "Markets" / "Marketzade"
    return _load_csv(d / f"{date_str}.csv", "item_name", "price",
                     "Marketzade", "market", "01",
                     category_col="kategori", tuik_mapper=_marketzade_to_tuik)


def _load_arden(date_str: str) -> pd.DataFrame | None:
    d = _DATA_ROOT / "Markets" / "Arden"
    return _load_csv(d / f"arden_urunler_{date_str}.csv", "isim", "fiyat",
                     "Arden", "market", "01")


def _load_baskent(date_str: str) -> pd.DataFrame | None:
    d = _DATA_ROOT / "Markets" / "Baskent"
    return _load_csv(d / f"baskent_{date_str}.csv", "product_name", "product_price",
                     "Baskent", "market", "01")


def _load_kale(date_str: str) -> pd.DataFrame | None:
    d = _DATA_ROOT / "Markets" / "Kale"
    return _load_csv(d / f"kalemarketleri_prices_{date_str}.csv",
                     "product_name", "product_price", "Kale", "market", "01")


def _load_kim(date_str: str) -> pd.DataFrame | None:
    d = _DATA_ROOT / "Markets" / "Kim"
    fname = f"products{_md(date_str)}.csv"
    return _load_no_header(d / fname, "Kim", "market", "01", sep=",",
                           name_idx=0, price_idx=1)


def _load_cagri(date_str: str) -> pd.DataFrame | None:
    d = _DATA_ROOT / "Markets" / "Cagri"
    prefix = f"cagri_products_{_yyyymmdd(date_str)}_"
    matches = sorted(d.glob(f"{prefix}*.csv"))
    if not matches:
        return None
    return _load_csv(matches[0], "product_name", "price_tl",
                     "Cagri", "market", "01")


def _load_basdas(date_str: str) -> pd.DataFrame | None:
    """Basdas stores all data in one file with a tarih (date) column."""
    d = _DATA_ROOT / "Markets" / "Basdas"
    fpath = d / "basdas_fiyat_takip.csv"
    if not fpath.exists():
        return None
    try:
        df = pd.read_csv(fpath, dtype=str, on_bad_lines="skip")
        df.columns = [c.lstrip("﻿").strip() for c in df.columns]
        if "tarih" not in df.columns:
            return None
        df = df[df["tarih"].str.startswith(date_str, na=False)]
        if df.empty:
            return None
        out = pd.DataFrame()
        out["product_key"] = df["urun_adi"].astype(str).str.strip()
        out["price"] = df["fiyat"].apply(_parse_price)
        out["store"] = "Basdas"
        out["sector"] = "market"
        out["tuik_category"] = "01"
        out = out.dropna(subset=["price"])
        out = out[out["price"] > 0].reset_index(drop=True)
        return out if not out.empty else None
    except Exception as e:
        logger.debug("Basdas: failed — %s", e)
        return None


# Clothing stores ──────────────────────────────────────────────────────────────

def _load_civil(date_str: str) -> pd.DataFrame | None:
    d = _DATA_ROOT / "ClothingStores" / "Civil"
    return _load_csv(d / f"civilim_{date_str}.csv", "isim", "fiyat",
                     "Civil", "clothing", "03", sep=";")


def _load_koton(date_str: str) -> pd.DataFrame | None:
    d = _DATA_ROOT / "ClothingStores" / "Koton"
    return _load_csv(d / f"koton_{date_str}.csv", "name", "sale_price",
                     "Koton", "clothing", "03")


def _load_lufian(date_str: str) -> pd.DataFrame | None:
    d = _DATA_ROOT / "ClothingStores" / "Lufian"
    return _load_csv(d / f"lufian_urunler_{date_str}.csv", "title", "price",
                     "Lufian", "clothing", "03")


def _load_stradivarius(date_str: str) -> pd.DataFrame | None:
    d = _DATA_ROOT / "ClothingStores" / "Stradivarius"
    return _load_csv(d / f"stradivarius_{date_str}.csv", "item_name", "price",
                     "Stradivarius", "clothing", "03")


def _load_vakko(date_str: str) -> pd.DataFrame | None:
    d = _DATA_ROOT / "ClothingStores" / "Vakko"
    return _load_csv(d / f"vakko_{date_str}.csv", "product-name", "product-price",
                     "Vakko", "clothing", "03")


def _load_adl(date_str: str) -> pd.DataFrame | None:
    d = _DATA_ROOT / "ClothingStores" / "adL"
    return _load_csv(d / f"adL_{date_str}.csv", "Product Name", "Price",
                     "adL", "clothing", "03")


def _load_altinyildiz(date_str: str) -> pd.DataFrame | None:
    d = _DATA_ROOT / "ClothingStores" / "Altınyıldız"
    return _load_csv(d / f"altinyildiz_tum_urunler_{date_str}.csv", "urun", "fiyat",
                     "Altinyildiz", "clothing", "03")


def _load_lcwaikiki(date_str: str) -> pd.DataFrame | None:
    d = _DATA_ROOT / "ClothingStores" / "LCWaikiki"
    return _load_csv(d / f"LCWaikiki_{date_str}.csv", "name", "price_tl",
                     "LCWaikiki", "clothing", "03")


def _load_loft(date_str: str) -> pd.DataFrame | None:
    d = _DATA_ROOT / "ClothingStores" / "Loft"
    return _load_csv(d / f"loft_{date_str}.csv", "Product Name", "Price",
                     "Loft", "clothing", "03")


def _load_defacto(date_str: str) -> pd.DataFrame | None:
    d = _DATA_ROOT / "ClothingStores" / "Defacto"
    fname = f"Clothes{_md(date_str)}.csv"
    return _load_csv(d / fname, "ProductName", "Price",
                     "Defacto", "clothing", "03")


# Tech stores ──────────────────────────────────────────────────────────────────

def _load_samsung(date_str: str) -> pd.DataFrame | None:
    d = _DATA_ROOT / "TechnologicalProducts" / "Samsung"
    return _load_csv(d / f"samsung_{date_str}.csv", "id", "shown_price",
                     "Samsung", "tech", "08")


def _load_dr(date_str: str) -> pd.DataFrame | None:
    d = _DATA_ROOT / "TechnologicalProducts" / "DR"
    return _load_csv(d / f"dr_{date_str}.csv", "Product Name", "Product Cost",
                     "DR", "tech", "08")


def _load_pozitif(date_str: str) -> pd.DataFrame | None:
    d = _DATA_ROOT / "TechnologicalProducts" / "PozitifTeknoloji"
    return _load_csv(d / f"pozitifTeknoloji_{date_str}.csv", "name", "price",
                     "PozitifTeknoloji", "tech", "08")


def _load_beymen_tech(date_str: str) -> pd.DataFrame | None:
    d = _DATA_ROOT / "TechnologicalProducts" / "Beymen"
    return _load_csv(d / f"beymen_tech_{date_str}.csv", "product-name", "product-price",
                     "BeymenTech", "tech", "08")


def _load_huawei(date_str: str) -> pd.DataFrame | None:
    d = _DATA_ROOT / "TechnologicalProducts" / "Huawei"
    return _load_csv(d / f"huawei_{date_str}.csv", "Product Name", "Price",
                     "Huawei", "tech", "08")


# Cosmetics stores ─────────────────────────────────────────────────────────────

def _load_rossmann(date_str: str) -> pd.DataFrame | None:
    d = _DATA_ROOT / "Cosmetics" / "Rossmann"
    return _load_csv(d / f"rossmann_{date_str}.csv", "id", "shown_price",
                     "Rossmann", "cosmetics", "13")


def _load_avon(date_str: str) -> pd.DataFrame | None:
    d = _DATA_ROOT / "Cosmetics" / "Avon"
    return _load_csv(d / f"all_products_{date_str}.csv", "name", "price",
                     "Avon", "cosmetics", "13", sep=";")


def _load_dermomarket(date_str: str) -> pd.DataFrame | None:
    d = _DATA_ROOT / "Cosmetics" / "Dermomarket"
    return _load_csv(d / f"dermomarket_{date_str}.csv", "item_name", "price",
                     "Dermomarket", "cosmetics", "13")


def _load_goldenrose(date_str: str) -> pd.DataFrame | None:
    d = _DATA_ROOT / "Cosmetics" / "GoldenRose"
    return _load_csv(d / f"goldenrose_{date_str}.csv", "Product Name", "Product Cost",
                     "GoldenRose", "cosmetics", "13")


def _load_loccitane(date_str: str) -> pd.DataFrame | None:
    d = _DATA_ROOT / "Cosmetics" / "LOccitane"
    return _load_csv(d / f"LOccitane_{date_str}.csv", "title", "price",
                     "LOccitane", "cosmetics", "13")


def _load_watsons(date_str: str) -> pd.DataFrame | None:
    d = _DATA_ROOT / "Cosmetics" / "Watsons"
    fname = f"watsons_{_ddmmyyyy(date_str)}.csv"
    return _load_csv(d / fname, "name", "price",
                     "Watsons", "cosmetics", "13", sep=";")


# HomeGoods stores ─────────────────────────────────────────────────────────────

def _load_vivense(date_str: str) -> pd.DataFrame | None:
    d = _DATA_ROOT / "HomeGoods" / "Vivense"
    return _load_csv(d / f"vivense_{date_str}.csv", "id", "shown_price",
                     "Vivense", "homegoods", "05")


def _load_karaca(date_str: str) -> pd.DataFrame | None:
    d = _DATA_ROOT / "HomeGoods" / "Karaca"
    return _load_csv(d / f"karaca_{date_str}.csv", "Product Name", "Product Cost",
                     "Karaca", "homegoods", "05")


def _load_englishhome(date_str: str) -> pd.DataFrame | None:
    d = _DATA_ROOT / "HomeGoods" / "EnglishHome"
    return _load_csv(d / f"englishhome_{date_str}.csv", "item_name", "price",
                     "EnglishHome", "homegoods", "05")


def _load_bellona(date_str: str) -> pd.DataFrame | None:
    d = _DATA_ROOT / "HomeGoods" / "Bellona"
    return _load_csv(d / f"Bellona_{date_str}.csv", "title", "price",
                     "Bellona", "homegoods", "05")


def _load_madamecoco(date_str: str) -> pd.DataFrame | None:
    d = _DATA_ROOT / "HomeGoods" / "MadameCoco"
    return _load_csv(d / f"madamecoco_{date_str}.csv", "name", "price",
                     "MadameCoco", "homegoods", "05")


def _load_jysk(date_str: str) -> pd.DataFrame | None:
    d = _DATA_ROOT / "HomeGoods" / "jysk"
    return _load_csv(d / f"jysk_prices_{date_str}.csv", "urun_adi", "fiyat",
                     "Jysk", "homegoods", "05")


def _load_istikbal(date_str: str) -> pd.DataFrame | None:
    d = _DATA_ROOT / "HomeGoods" / "Istikbal"
    fname = f"istikbal_{_underscore_date(date_str)}.csv"
    return _load_csv(d / fname, "Product Name", "Price",
                     "Istikbal", "homegoods", "05")


def _load_chakra(date_str: str) -> pd.DataFrame | None:
    d = _DATA_ROOT / "HomeGoods" / "Chakra"
    fname = f"chakra_all_categories_{_underscore_date(date_str)}.csv"
    return _load_csv(d / fname, "name", "price",
                     "Chakra", "homegoods", "05")


def _load_ikea(date_str: str) -> pd.DataFrame | None:
    d = _DATA_ROOT / "HomeGoods" / "Ikea"
    fname = f"HomeGoods{_md(date_str)}.csv"
    return _load_no_header(d / fname, "Ikea", "homegoods", "05", sep=",",
                           name_idx=0, price_idx=1)


# Construction stores ──────────────────────────────────────────────────────────

def _load_bauhaus(date_str: str) -> pd.DataFrame | None:
    d = _DATA_ROOT / "ConstructionSuppliesMarkets" / "Bauhaus"
    return _load_csv(d / f"bauhaus_{date_str}.csv", "id", "shown_price",
                     "Bauhaus", "construction", "05")


def _load_filtasyapi(date_str: str) -> pd.DataFrame | None:
    d = _DATA_ROOT / "ConstructionSuppliesMarkets" / "FiltasYapi"
    return _load_csv(d / f"FiltaşYapı_{date_str}.csv", "title", "price",
                     "FiltasYapi", "construction", "05")


def _load_hausmart(date_str: str) -> pd.DataFrame | None:
    d = _DATA_ROOT / "ConstructionSuppliesMarkets" / "Hausmart"
    return _load_csv(d / f"hausmart_{date_str}.csv", "item_name", "price",
                     "Hausmart", "construction", "05")


def _load_nalburadam(date_str: str) -> pd.DataFrame | None:
    d = _DATA_ROOT / "ConstructionSuppliesMarkets" / "Nalburadam"
    return _load_csv(d / f"nalburadam_{date_str}.csv", "Product Name", "Product Cost",
                     "Nalburadam", "construction", "05")


def _load_hancivata(date_str: str) -> pd.DataFrame | None:
    d = _DATA_ROOT / "ConstructionSuppliesMarkets" / "HanCivata"
    return _load_csv(d / f"han_civata_{date_str}.csv", "urun_adi", "fiyat",
                     "HanCivata", "construction", "05")


def _load_nalburcuk(date_str: str) -> pd.DataFrame | None:
    d = _DATA_ROOT / "ConstructionSuppliesMarkets" / "Nalburcuk"
    return _load_csv(d / f"nalburcuk_{date_str}.csv", "Product Name", "Price (TL)",
                     "Nalburcuk", "construction", "05")


def _load_nalburdayim(date_str: str) -> pd.DataFrame | None:
    d = _DATA_ROOT / "ConstructionSuppliesMarkets" / "Nalburdayim"
    return _load_csv(d / f"nalburdayim_{date_str}.csv", "ProductName", "Price",
                     "Nalburdayim", "construction", "05")


def _load_sanatyapi(date_str: str) -> pd.DataFrame | None:
    d = _DATA_ROOT / "ConstructionSuppliesMarkets" / "SanatYapiOnline"
    return _load_csv(d / f"sanatyapionline_{date_str}.csv", "Name", "Current Price",
                     "SanatYapi", "construction", "05")


def _load_tasciyapi(date_str: str) -> pd.DataFrame | None:
    d = _DATA_ROOT / "ConstructionSuppliesMarkets" / "TasciYapiMarket"
    return _load_csv(d / f"tasciyapi_products_{date_str}.csv", "Product Name", "Price",
                     "TasciYapi", "construction", "05")


def _load_yapimaks(date_str: str) -> pd.DataFrame | None:
    d = _DATA_ROOT / "ConstructionSuppliesMarkets" / "yapimaks"
    return _load_csv(d / f"{date_str}.csv", "name", "price",
                     "Yapimaks", "construction", "05")


def _load_ereyon(date_str: str) -> pd.DataFrame | None:
    d = _DATA_ROOT / "ConstructionSuppliesMarkets" / "Ereyon"
    return _load_csv(d / f"{date_str}_Ereyonprices.csv", "Urun_Adi", "Fiyat",
                     "Ereyon", "construction", "05")


def _load_afeks(date_str: str) -> pd.DataFrame | None:
    d = _DATA_ROOT / "ConstructionSuppliesMarkets" / "AfeksYapiMarket"
    fname = f"ConstructionProduct{_md(date_str)}.csv"
    return _load_csv(d / fname, "Product Title", "Price(TL)",
                     "Afeks", "construction", "05")


# ── All store loaders registry ────────────────────────────────────────────────

_STORE_LOADERS = [
    # Grocery markets
    _load_migros, _load_a101, _load_gurmar, _load_hapeloglu, _load_marketzade,
    _load_arden, _load_baskent, _load_kale, _load_kim, _load_cagri, _load_basdas,
    # Clothing
    _load_civil, _load_koton, _load_lufian, _load_stradivarius, _load_vakko,
    _load_adl, _load_altinyildiz, _load_lcwaikiki, _load_loft, _load_defacto,
    # Tech
    _load_samsung, _load_dr, _load_pozitif, _load_beymen_tech, _load_huawei,
    # Cosmetics
    _load_rossmann, _load_avon, _load_dermomarket, _load_goldenrose,
    _load_loccitane, _load_watsons,
    # HomeGoods
    _load_vivense, _load_karaca, _load_englishhome, _load_bellona,
    _load_madamecoco, _load_jysk, _load_istikbal, _load_chakra, _load_ikea,
    # Construction
    _load_bauhaus, _load_filtasyapi, _load_hausmart, _load_nalburadam,
    _load_hancivata, _load_nalburcuk, _load_nalburdayim, _load_sanatyapi,
    _load_tasciyapi, _load_yapimaks, _load_ereyon, _load_afeks,
]


# ── Pool loading and deduplication ────────────────────────────────────────────

def _load_all_stores(date_str: str) -> tuple[pd.DataFrame, list[str], int]:
    """
    Load all stores for a given date.

    Returns
    -------
    df          : combined and deduplicated DataFrame
    stores_ok   : list of store names that had data
    n_before    : total product count before deduplication
    """
    frames = []
    stores_ok = []
    for loader in _STORE_LOADERS:
        df = loader(date_str)
        if df is not None and not df.empty:
            frames.append(df)
            stores_ok.append(df["store"].iloc[0])

    if not frames:
        return pd.DataFrame(columns=_STANDARD_COLS), [], 0

    combined = pd.concat(frames, ignore_index=True)
    n_before = len(combined)

    # Normalise product keys for cross-store deduplication
    combined["_norm_key"] = combined["product_key"].apply(_norm)

    # Drop empty-name rows
    combined = combined[combined["_norm_key"] != ""]

    # Average prices for (normalised_name, tuik_category) pairs that appear
    # in more than one store (prevents excess basket weight)
    deduped = (
        combined
        .groupby(["_norm_key", "tuik_category", "sector"], as_index=False)
        .agg(
            product_key=("product_key", "first"),
            price=("price", "mean"),
            store=("store", lambda s: ",".join(sorted(s.unique()))),
        )
    )
    deduped = deduped.drop(columns=["_norm_key"])

    return deduped, stores_ok, n_before


# ── Rent inflation helper ─────────────────────────────────────────────────────

def _rent_city_prices(date_str: str) -> dict[str, float]:
    """
    Return {city_dir_name: mean_price} for all cities that have rent data on date_str.
    Only cities with at least one valid price are included.
    """
    rent_root = _DATA_ROOT / "HousesRent"
    result: dict[str, float] = {}
    for city_dir in rent_root.iterdir():
        if not city_dir.is_dir():
            continue
        matches = list(city_dir.glob(f"*{date_str}*.csv"))
        if not matches:
            continue
        try:
            df = pd.read_csv(matches[0], dtype=str, on_bad_lines="skip")
            df.columns = [c.lstrip("﻿").strip() for c in df.columns]
            price_col = next(
                (c for c in df.columns if "price" in c.lower() or "fiyat" in c.lower()), None
            )
            if price_col is None:
                continue
            city_prices = df[price_col].apply(_parse_price).dropna()
            city_prices = city_prices[city_prices > 0]
            if not city_prices.empty:
                result[city_dir.name] = city_prices.mean()
        except Exception:
            continue
    return result


def _rent_inflation(current_str: str, past_str: str) -> float | None:
    """
    Return % change in mean rent price between two dates.
    Only cities present on BOTH dates are included, preventing composition
    bias from cities that join or leave the dataset between snapshots.
    """
    cur_city = _rent_city_prices(current_str)
    past_city = _rent_city_prices(past_str)
    common = set(cur_city) & set(past_city)
    if not common:
        return None
    mean_cur  = sum(cur_city[c]  for c in common) / len(common)
    mean_past = sum(past_city[c] for c in common) / len(common)
    if mean_past == 0:
        return None
    logger.debug(
        "Rent: %d common cities, mean_cur=%.0f mean_past=%.0f",
        len(common), mean_cur, mean_past,
    )
    return (mean_cur - mean_past) / mean_past * 100


# ── Core metric computation ───────────────────────────────────────────────────

def _compute_metrics(
    df_current: pd.DataFrame,
    df_past: pd.DataFrame,
) -> tuple[pd.DataFrame, float | None, float | None, float | None]:
    """
    Merge current and past deduplicated pools and compute the three metrics.

    Matching is done on (product_key, tuik_category, sector) — the deduplicated
    canonical name plus category.

    Returns
    -------
    merged              : DataFrame with basic_inflation per product
    basic_index         : float | None
    avg_inflation       : float | None
    tuik_weighted       : float | None
    """
    merge_keys = ["product_key", "tuik_category", "sector"]
    past_sub = df_past[merge_keys + ["price"]].rename(columns={"price": "past_price"})
    merged = df_current.merge(past_sub, on=merge_keys, how="left")

    # 1) Per-product basic inflation
    merged["basic_inflation"] = (
        (merged["price"] - merged["past_price"]) / merged["past_price"]
    ) * 100
    merged["basic_inflation"] = merged["basic_inflation"].replace(
        [float("inf"), float("-inf")], pd.NA
    )

    # 2) Average inflation — arithmetic mean of per-product rates
    avg_inflation = merged["basic_inflation"].mean()
    avg_inflation = float(avg_inflation) if pd.notna(avg_inflation) else None

    # 3) Basic inflation index — basket-level sum ratio
    valid = merged.dropna(subset=["price", "past_price"])
    sum_current = valid["price"].sum()
    sum_past = valid["past_price"].sum()
    basic_index = float((sum_current - sum_past) / sum_past * 100) if sum_past else None

    # 4) TUIK-weighted average (product categories only; rent handled separately)
    cat_avg = merged.groupby("tuik_category")["basic_inflation"].mean()
    present_codes = list(cat_avg.dropna().index)
    norm_w = normalised_weights(present_codes)
    tuik_weighted = sum(
        cat_avg[c] * norm_w[c] / 100.0
        for c in norm_w
        if c in cat_avg.index and pd.notna(cat_avg[c])
    )
    tuik_weighted = float(tuik_weighted) if norm_w else None

    return merged, basic_index, avg_inflation, tuik_weighted


# ── Per-sector breakdown ──────────────────────────────────────────────────────

def _sector_avg(merged: pd.DataFrame) -> dict[str, float | None]:
    """Return average inflation per sector column for summary reporting."""
    result = {}
    for sector in merged["sector"].unique():
        sub = merged[merged["sector"] == sector]["basic_inflation"]
        result[f"avg_inflation_{sector}"] = float(sub.mean()) if not sub.dropna().empty else None
    return result


# ── Main calculate function ───────────────────────────────────────────────────

def calculate_turkey_inflation(
    target_date: str | None = None,
    compare_date: str | None = None,
) -> None:
    """
    Calculate Turkey-wide inflation metrics for the given date.

    Parameters
    ----------
    target_date  : 'YYYY-MM-DD' string (defaults to today).
    compare_date : if given, compute metrics only between this past date and
                   target_date.  Otherwise, compute for 1d, 7d, 15d, 30d.
    """
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

    logger.info("Loaded %d stores, %d unique products (after dedup: %d)",
                len(stores_today), n_before, len(df_current))

    _OUT_DIR.mkdir(parents=True, exist_ok=True)

    # ── Intervals ─────────────────────────────────────────────────────────────
    if compare_date:
        intervals = {compare_date: compare_date}
    else:
        intervals = {
            f"{days}d": (base_date - timedelta(days=days)).strftime("%Y-%m-%d")
            for days in [15, 30]
        }

    # ── Per-interval computation ──────────────────────────────────────────────
    summary_row: dict = {
        "date": today_str,
        "n_stores": len(stores_today),
        "n_products_raw": n_before,
        "n_products_deduped": len(df_current),
    }
    detail_base = df_current.copy()

    for label, past_str in intervals.items():
        logger.info("Computing interval %s (vs %s) …", label, past_str)
        df_past, _, _ = _load_all_stores(past_str)

        if df_past.empty:
            logger.info("  No past data for %s — skipping interval %s.", past_str, label)
            detail_base[f"basic_inflation_{label}"] = pd.NA
            for key in ["avg_inflation", "basic_index", "tuik_weighted_products",
                        "tuik_weighted_full", "rent_inflation"]:
                summary_row[f"{key}_{label}"] = None
            continue

        merged, basic_idx, avg_inf, tuik_w_products = _compute_metrics(df_current, df_past)

        # Attach per-product inflation to detail frame
        detail_base = detail_base.merge(
            merged[["product_key", "tuik_category", "sector", "basic_inflation"]].rename(
                columns={"basic_inflation": f"basic_inflation_{label}"}
            ),
            on=["product_key", "tuik_category", "sector"],
            how="left",
        )

        summary_row[f"avg_inflation_{label}"] = avg_inf
        summary_row[f"basic_index_{label}"] = basic_idx
        summary_row[f"tuik_weighted_products_{label}"] = tuik_w_products

        # Rent (TUIK group 04) — injected into TUIK-weighted metric only
        rent_inf = _rent_inflation(today_str, past_str)
        summary_row[f"rent_inflation_{label}"] = rent_inf
        if rent_inf is not None and tuik_w_products is not None:
            # Re-compute TUIK-weighted including rent
            cat_avg_products = (
                merged.groupby("tuik_category")["basic_inflation"].mean().dropna()
            )
            cat_avg_full = cat_avg_products.copy()
            cat_avg_full["04"] = rent_inf
            present_all = list(cat_avg_full.index)
            norm_w_all = normalised_weights(present_all)
            tuik_w_full = sum(
                cat_avg_full[c] * norm_w_all[c] / 100.0
                for c in norm_w_all
                if pd.notna(cat_avg_full.get(c))
            )
            summary_row[f"tuik_weighted_full_{label}"] = float(tuik_w_full)
        else:
            summary_row[f"tuik_weighted_full_{label}"] = tuik_w_products

        logger.info(
            "  [%s] basic_index=%.3f%%  avg=%.3f%%  tuik_products=%.3f%%  tuik_full=%s",
            label,
            basic_idx or float("nan"),
            avg_inf or float("nan"),
            tuik_w_products or float("nan"),
            f"{summary_row[f'tuik_weighted_full_{label}']:.3f}%"
            if summary_row[f"tuik_weighted_full_{label}"] is not None else "N/A",
        )

    # ── Save detailed product-level CSV ───────────────────────────────────────
    detail_file = _OUT_DIR / f"turkey_inflation_{today_str}.csv"
    detail_base.to_csv(detail_file, index=False, encoding="utf-8")
    logger.info("Saved per-product detail: %s", detail_file)

    # ── Update summary CSV ────────────────────────────────────────────────────
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


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Turkey-wide inflation calculator")
    parser.add_argument(
        "--date", default=None,
        help="Target (current) date in YYYY-MM-DD format (default: today)",
    )
    parser.add_argument(
        "--compare", default=None,
        help="Comparison (past) date in YYYY-MM-DD format for a single arbitrary interval",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    calculate_turkey_inflation(args.date, args.compare)
