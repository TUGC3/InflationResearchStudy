import datetime as _dt
from pathlib import Path as _Path

# ── Paths ─────────────────────────────────────────────────────────────────────
_SCRIPTS_DIR   = _Path(__file__).resolve().parent          # …/Izmir/scripts
_SCRAPER_DIR   = _SCRIPTS_DIR.parent                       # …/Izmir
_PROJECT_ROOT  = _SCRAPER_DIR.parent.parent.parent         # …/InflationResearchStudy

# ── City Settings ─────────────────────────────────────────────────────────────
CITY_URL_NAME = "izmir"
FOLDER_NAME   = "Izmir"

# ── Seed Ranges ───────────────────────────────────────────────────────────────
SEED_RANGES = [
    (0,      19_999),
    (20_000, 39_999),
    (40_000, 99_999),
    (100_000, 9_999_999)
]

# ── Adaptive Splitting Settings ───────────────────────────────────────────────
MAX_LISTINGS_PER_QUERY = 1000
MIN_BRACKET_WIDTH = 50
PAGE_SIZE = 50
BETWEEN_BRACKET_DELAY_MIN = 1.0
BETWEEN_BRACKET_DELAY_MAX = 2.0

# ── Browser Settings ──────────────────────────────────────────────────────────
SELENIUM_PROFILE_DIR = str(_SCRAPER_DIR / "SeleniumProfile")
CHROMEDRIVER_PATH = r"C:\chromedriver\chromedriver.exe"  # ← your actual path

# ── Output Settings ───────────────────────────────────────────────────────────
_TODAY = _dt.date.today().strftime("%Y-%m-%d")
OUTPUT_DIR      = str(_PROJECT_ROOT / "Datas" / "HousesRent" / FOLDER_NAME)
CHECKPOINT_DIR  = str(_SCRAPER_DIR / "checkpoints")
CSV_OUTPUT_FILE = str(_Path(OUTPUT_DIR)     / f"{FOLDER_NAME}_{_TODAY}.csv")
CHECKPOINT_FILE = str(_Path(CHECKPOINT_DIR) / f"checkpoint_{_TODAY}.json")