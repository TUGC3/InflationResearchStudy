"""
run_full_inflation.py — Run Batu's inflation calculators, auto-filling gaps.

For each scraper (Bershka, Hapeloglu, Nalburadam, ErzurumErzincanBayburt,
Karaca, GoldenRose, DR), finds all dates that have scraped data but no
inflation output yet, and runs the calculator for each missing date.

Usage:
    python run_full_inflation.py            # Auto-fill all gaps
    python run_full_inflation.py --force    # Recalculate ALL dates (overwrites)
"""

import argparse
import importlib.util
import re
import sys
import time
from datetime import datetime
from pathlib import Path

# ── Path setup ───────────────────────────────────────────────────────────────
_THIS_DIR = Path(__file__).resolve().parent
_CODES_DIR = _THIS_DIR.parent.parent          # .../Inflations/Codes
_PROJECT_ROOT = _CODES_DIR.parent.parent      # .../InflationResearchStudy

sys.path.insert(0, str(_CODES_DIR / "ClothingStores" / "Bershka"))
sys.path.insert(0, str(_CODES_DIR / "Markets" / "Hapeloglu"))
sys.path.insert(0, str(_CODES_DIR / "ConstructionSuppliesMarkets" / "Nalburadam"))
sys.path.insert(0, str(_CODES_DIR / "HousesRent" / "ErzurumErzincanBayburt"))
sys.path.insert(0, str(_CODES_DIR))

# ── Colors ───────────────────────────────────────────────────────────────────
CYAN    = "\033[96m"
GREEN   = "\033[92m"
YELLOW  = "\033[93m"
RED     = "\033[91m"
MAGENTA = "\033[95m"
BOLD    = "\033[1m"
RESET   = "\033[0m"


def _extract_dates_from_files(directory, pattern):
    """Extract all YYYY-MM-DD dates from filenames matching a glob pattern."""
    dates = set()
    for f in directory.glob(pattern):
        match = re.search(r"(\d{4}-\d{2}-\d{2})", f.name)
        if match:
            dates.add(match.group(1))
    return sorted(dates)


def _load_calculator_from_path(module_name, file_path):
    """Load a calculator module from an explicit file path."""
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load calculator module from {file_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.calculate_inflation


def _get_scraper_dates():
    """Get all available scraped data dates for each scraper."""
    data_root = _PROJECT_ROOT / "InflationItems" / "Datas"
    return {
        "Bershka": _extract_dates_from_files(
            data_root / "ClothingStores" / "Bershka" / "ProductData", "bershka_*.csv"
        ),
        "Hapeloglu": _extract_dates_from_files(
            data_root / "Markets" / "Hapeloglu", "hapeloglu_*.csv"
        ),
        "Nalburadam": _extract_dates_from_files(
            data_root / "ConstructionSuppliesMarkets" / "Nalburadam", "nalburadam_*.csv"
        ),
        "ErzurumErzincanBayburt": _extract_dates_from_files(
            data_root / "HousesRent" / "ErzurumErzincanBayburt" / "Erzurum", "Erzurum_*.csv"
        ),
        "Karaca": _extract_dates_from_files(
            data_root / "HomeGoods" / "Karaca", "karaca_*.csv"
        ),
        "GoldenRose": _extract_dates_from_files(
            data_root / "Cosmetics" / "GoldenRose", "goldenrose_*.csv"
        ),
        "DR": _extract_dates_from_files(
            data_root / "TechnologicalProducts" / "DR", "dr_*.csv"
        ),
    }


def _get_inflation_dates():
    """Get all dates that already have inflation output."""
    inflation_root = _CODES_DIR.parent / "Datas"
    return {
        "Bershka": _extract_dates_from_files(
            inflation_root / "ClothingStores" / "Bershka", "bershka_inflation_*.csv"
        ),
        "Hapeloglu": _extract_dates_from_files(
            inflation_root / "Markets" / "Hapeloglu", "hapeloglu_inflation_*.csv"
        ),
        "Nalburadam": _extract_dates_from_files(
            inflation_root / "ConstructionSuppliesMarkets" / "Nalburadam", "nalburadam_inflation_*.csv"
        ),
        "ErzurumErzincanBayburt": _extract_dates_from_files(
            inflation_root / "HousesRent" / "ErzurumErzincanBayburt" / "Erzurum", "Erzurum_rent_inflation_*.csv"
        ),
        "Karaca": _extract_dates_from_files(
            inflation_root / "HomeGoods" / "Karaca", "karaca_inflation_*.csv"
        ),
        "GoldenRose": _extract_dates_from_files(
            inflation_root / "Cosmetics" / "GoldenRose", "goldenrose_inflation_*.csv"
        ),
        "DR": _extract_dates_from_files(
            inflation_root / "TechnologicalProducts" / "DR", "dr_inflation_*.csv"
        ),
    }


def _run_calculator(name, date_str):
    """Run the appropriate inflation calculator for a given scraper and date."""
    if name == "Bershka":
        from bershka_inflation import calculate_inflation
    elif name == "Hapeloglu":
        from hapeloglu_inflation import calculate_inflation
    elif name == "Nalburadam":
        from nalburadam_inflation import calculate_inflation
    elif name == "ErzurumErzincanBayburt":
        from rent_inflation import calculate_inflation
    elif name == "Karaca":
        calculate_inflation = _load_calculator_from_path(
            "karaca_inflation_module",
            _CODES_DIR / "HomeGoods" / "Karaca" / "inflation.py",
        )
    elif name == "GoldenRose":
        calculate_inflation = _load_calculator_from_path(
            "goldenrose_inflation_module",
            _CODES_DIR / "Cosmetics" / "GoldenRose" / "inflation.py",
        )
    elif name == "DR":
        calculate_inflation = _load_calculator_from_path(
            "dr_inflation_module",
            _CODES_DIR / "TechnologicalProducts" / "DR" / "inflation.py",
        )
    else:
        return False

    try:
        calculate_inflation(date_str)
        return True
    except Exception as e:
        print(f"  {RED}ERROR: {e}{RESET}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Run all inflation calculators with gap-filling")
    parser.add_argument("--force", action="store_true", help="Recalculate ALL dates, not just gaps")
    args = parser.parse_args()

    start_time = time.time()

    print(f"\n{MAGENTA}{BOLD}   Batu Koray Masak — Full Inflation Calculator{RESET}\n")

    scraper_dates = _get_scraper_dates()
    inflation_dates = _get_inflation_dates()

    total_calculated = 0
    total_skipped = 0

    for name in ["Bershka", "Hapeloglu", "Nalburadam", "ErzurumErzincanBayburt", "Karaca", "GoldenRose", "DR"]:
        available = scraper_dates[name]
        existing = set(inflation_dates[name])

        if args.force:
            to_calculate = available
        else:
            to_calculate = [d for d in available if d not in existing]

        print(f"{'═' * 70}")
        print(f"{BOLD}{name}{RESET}")
        print(f"  Scraped dates: {CYAN}{len(available)}{RESET}")
        print(f"  Already calculated: {GREEN}{len(existing)}{RESET}")
        print(f"  To calculate: {YELLOW}{len(to_calculate)}{RESET}")

        if not to_calculate:
            print(f"  {GREEN}Nothing to do — all up to date!{RESET}")
            total_skipped += len(available)
            continue

        for i, date_str in enumerate(to_calculate, 1):
            status = f"  [{i}/{len(to_calculate)}] {date_str}"
            success = _run_calculator(name, date_str)
            if success:
                print(f"{status} {GREEN}OK{RESET}")
                total_calculated += 1
            else:
                print(f"{status} {RED}FAILED{RESET}")

    elapsed = time.time() - start_time
    print(f"\n{'═' * 70}")
    print(f"{GREEN}{BOLD}DONE!{RESET}")
    print(f"  Calculated: {CYAN}{total_calculated}{RESET} dates")
    print(f"  Skipped (already done): {total_skipped}")
    print(f"  Duration: {YELLOW}{elapsed:.1f}s{RESET}\n")


if __name__ == "__main__":
    main()
