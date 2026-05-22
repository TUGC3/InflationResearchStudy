"""
run_all.py
----------
Tüm scraper'ları, ardından tüm inflation hesaplama scriptlerini sırayla çalıştırır.
Her script ayrı bir subprocess olarak çalışır; hata olursa loglanır ve devam edilir.

Kullanım:
    python run_all.py
"""

import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent

# ── Scraper'lar (sırayla çalışır) ────────────────────────────────────────────
SCRAPERS = [
    REPO_ROOT / "InflationItems/Codes/HousesRent/Malatya_Elazig_Tunceli/sahibinden_scraper.py",  # ilk sırada — Chrome + Cloudflare manual geçiş gerekir
    REPO_ROOT / "InflationItems/Codes/Markets/Marketzade/scraper_claude.py",
    REPO_ROOT / "InflationItems/Codes/Cosmetics/Dermomarket/dermomarket_scraper.py",
    REPO_ROOT / "InflationItems/Codes/HomeGoods/EnglishHome/englishhome_scraper.py",
    REPO_ROOT / "InflationItems/Codes/ConstructionSuppliesMarkets/Hausmart/hausmart_scraper.py",
    REPO_ROOT / "InflationItems/Codes/TechnologicalProducts/Koçtaş/koctas_scraper.py",
    REPO_ROOT / "InflationItems/Codes/ClothingStores/Stradivarius/StradivariusScraper.py",
]

# ── Inflation scriptleri (sırayla çalışır) ───────────────────────────────────
INFLATION_SCRIPTS = [
    REPO_ROOT / "Inflations/Codes/Markets/Marketzade/marketzade_inflation.py",
    REPO_ROOT / "Inflations/Codes/Cosmetics/Dermomarket/dermomarket_inflation.py",
    REPO_ROOT / "Inflations/Codes/HomeGoods/EnglishHome/englishhome_inflation.py",
    REPO_ROOT / "Inflations/Codes/ConstructionSuppliesMarkets/Hausmart/hausmart_inflation.py",
    REPO_ROOT / "Inflations/Codes/TechnologicalProducts/Koçtaş/koctas_inflation.py",
    REPO_ROOT / "Inflations/Codes/ClothingStores/Stradivarius/stradivarius_inflation.py",
    REPO_ROOT / "Inflations/Codes/HousesRent/Malatya_Elazig_Tunceli/sahibinden_inflation.py",
]


def run_script(script_path: Path) -> tuple[bool, float]:
    """
    Verilen scripti subprocess olarak çalıştırır.
    (success, elapsed_seconds) döner.
    """
    label = script_path.relative_to(REPO_ROOT)
    print(f"\n{'─' * 60}")
    print(f"▶  {label}")
    print(f"{'─' * 60}")

    start = time.time()
    try:
        result = subprocess.run(
            [sys.executable, str(script_path)],
            cwd=str(script_path.parent),
        )
        elapsed = time.time() - start
        if result.returncode == 0:
            print(f"✓  Tamamlandı  ({elapsed:.1f}s)")
            return True, elapsed
        else:
            print(f"✗  Hata — return code {result.returncode}  ({elapsed:.1f}s)")
            return False, elapsed
    except Exception as exc:
        elapsed = time.time() - start
        print(f"✗  Exception: {exc}  ({elapsed:.1f}s)")
        return False, elapsed


def run_group(scripts: list[Path], group_label: str) -> list[tuple[Path, bool, float]]:
    """Bir grup scripti sırayla çalıştırır, sonuçları döner."""
    print(f"\n{'═' * 60}")
    print(f"  {group_label}")
    print(f"{'═' * 60}")
    results = []
    for script in scripts:
        success, elapsed = run_script(script)
        results.append((script, success, elapsed))
    return results


def print_summary(scraper_results: list, inflation_results: list) -> None:
    """Başarılı/başarısız özetini yazdırır."""
    all_results = scraper_results + inflation_results
    ok  = [(p, e) for p, s, e in all_results if s]
    err = [(p, e) for p, s, e in all_results if not s]

    print(f"\n{'═' * 60}")
    print(f"  ÖZET  —  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'═' * 60}")
    print(f"  Toplam  : {len(all_results)}")
    print(f"  Başarılı: {len(ok)}")
    print(f"  Hatalı  : {len(err)}")

    if ok:
        print("\n  ✓ Başarılı:")
        for path, elapsed in ok:
            print(f"      {path.relative_to(REPO_ROOT)}  ({elapsed:.1f}s)")

    if err:
        print("\n  ✗ Hatalı:")
        for path, elapsed in err:
            print(f"      {path.relative_to(REPO_ROOT)}  ({elapsed:.1f}s)")

    print(f"\n  Toplam süre: {sum(e for _, _, e in all_results):.1f}s")
    print(f"{'═' * 60}\n")


def main():
    print(f"{'═' * 60}")
    print(f"  run_all.py  —  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Repo: {REPO_ROOT}")
    print(f"{'═' * 60}")

    scraper_results   = run_group(SCRAPERS,          "SCRAPERS")
    inflation_results = run_group(INFLATION_SCRIPTS, "INFLATION SCRIPTS")

    print_summary(scraper_results, inflation_results)


if __name__ == "__main__":
    main()
