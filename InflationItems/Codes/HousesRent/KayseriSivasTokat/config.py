"""
config.py — Kayseri / Sivas / Tokat Kiralık Konut Scraper
Tüm ayarlar, şehir tanımları, path'ler ve timing sabitleri.
"""

import datetime as _dt
from pathlib import Path as _Path

# ============================================================
# PATH YAPISI
# ============================================================
# Bu dosya: .../Codes/HousesRent/KayseriSivasTokat/config.py
_SCRIPTS_DIR  = _Path(__file__).resolve().parent          # .../KayseriSivasTokat/
_PROJECT_ROOT = _SCRIPTS_DIR.parent.parent.parent         # .../InflationResearchStudy/

# ============================================================
# ŞEHİR TANIMLARI
# ============================================================
DEFAULT_BRACKETS = [
    (0,       19_999),
    (20_000,  39_999),
    (40_000,  59_999),
    (60_000,  99_999),
    (100_000, 9_999_999),
]

CITIES = [
    {"url_slug": "kayseri", "name": "Kayseri", "brackets": DEFAULT_BRACKETS},
    {"url_slug": "sivas",   "name": "Sivas",   "brackets": DEFAULT_BRACKETS},
    {"url_slug": "tokat",   "name": "Tokat",   "brackets": DEFAULT_BRACKETS},
]

# ============================================================
# ÇIKTI PATH'LERİ
# ============================================================
TODAY = _dt.date.today().strftime("%Y-%m-%d")

OUTPUT_BASE_DIR = str(_PROJECT_ROOT / "Datas" / "HousesRent")
CHECKPOINT_DIR  = str(_SCRIPTS_DIR / "checkpoints")


def get_city_output_dir(city_name: str) -> str:
    return str(_Path(OUTPUT_BASE_DIR) / city_name)


def get_city_csv_path(city_name: str) -> str:
    return str(_Path(OUTPUT_BASE_DIR) / city_name / f"{TODAY}.csv")


def get_checkpoint_file() -> str:
    return str(_Path(CHECKPOINT_DIR) / f"checkpoint_{TODAY}.json")


# ============================================================
# ZAMANLAMA SABİTLERİ  (min, max) — saniye cinsinden
# ============================================================
PAGE_LOAD_AFTER_GOTO  = (8.3,  12.7)   # goto() sonrası bekleme
BETWEEN_BRACKETS      = (4.2,   6.3)   # Bracket geçişi molası
BETWEEN_PAGES         = (8.1,  12.9)   # Sayfalama geçişi
LOGIN_RETRY_WAIT      = (10.1, 15.2)   # Login sayfası tekrar denemesi
GOTO_RETRY_WAIT       = (13.3, 18.8)   # goto() timeout retry arası
TURNSTILE_TOKEN_WAIT  = (13.9, 17.3)   # Turnstile widget sonrası bekleme
POST_CHECK_WAIT       = (4.3,   6.2)   # Koruma sayfası geçildikten sonra
HOMEPAGE_WAIT         = (8.1,   9.2)   # Ana sayfa yüklendikten sonra
CITY_CLOSE_WAIT       = 30             # Tarayıcı kapandıktan sonra (sabit)

# ============================================================
# CAMOUFOX AYARLARI
# ============================================================
CAMOUFOX_OS     = "windows"
CAMOUFOX_LOCALE = "tr-TR"

# ============================================================
# SCRAPER AYARLARI
# ============================================================
MAX_RESTARTS_PER_CITY = 3    # Bir şehirde max kaç kez tarayıcı yeniden başlar
MAX_PAGES_PER_BRACKET = 20   # Sonsuz döngüye karşı güvenlik kapağı
PAGE_SIZE             = 50   # Sayfa başına ilan sayısı
