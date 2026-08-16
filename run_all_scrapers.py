from pathlib import Path
import argparse
import subprocess
import sys
import time
import shutil

REPO_ROOT = Path(__file__).resolve().parent
CODES_ROOT = REPO_ROOT / "InflationItems" / "Codes"

CATEGORIES = [
    "Markets",
    "ClothingStores",
    "ConstructionSuppliesMarkets",
    "Cosmetics",
    "HomeGoods",
    "HousesRent",
    "TechnologicalProducts",
    "Health",
    "BooksStationery",
    "PublicTransportation",
    "RestaurantMealPricesVenueHallRentalFees",
    "TravelTourism",
    "motor_bicyle_car",
]

IGNORE_FILES = {
    "__init__.py",
    "config.py",
    "utils.py",
    "product_fetcher.py",
    "category_fetcher.py",
    "price_fixer.py",
    "run_analysis.py",
}

PREFERRED_NAMES = [
    "run_scraper.py",
    "daily_runner.py",
    "main.py",
]


def is_candidate(path: Path) -> bool:
    name = path.name.lower()

    if name in IGNORE_FILES:
        return False

    keywords = (
        "scraper",
        "scrape",
        "runner",
        "main",
    )

    return any(word in name for word in keywords)


def choose_entrypoint(folder: Path):
    files = [
        p for p in folder.rglob("*.py")
        if p.name not in IGNORE_FILES
    ]

    if not files:
        return None

    # 1. Prefer known runner filenames
    for preferred in PREFERRED_NAMES:
        matches = [
            p for p in files
            if p.name.lower() == preferred.lower()
        ]

        if matches:
            # Prefer scripts/run_scraper.py etc.
            matches.sort(
                key=lambda p: (
                    0 if "scripts" in p.parts else 1,
                    len(p.parts),
                )
            )
            return matches[0]

    # 2. Prefer files containing scraper/scrape
    candidates = [p for p in files if is_candidate(p)]

    if candidates:
        candidates.sort(
            key=lambda p: (
                0 if "scraper" in p.name.lower() else 1,
                0 if "scrape" in p.name.lower() else 1,
                len(p.parts),
            )
        )
        return candidates[0]

    return None


def discover_scrapers():
    discovered = {}

    for category_name in CATEGORIES:
        category = CODES_ROOT / category_name

        if not category.exists():
            continue

        entries = []

        # Scripts directly inside category
        direct_files = [
            p for p in category.glob("*.py")
            if is_candidate(p)
        ]

        for file in direct_files:
            entries.append(
                (file.stem, file)
            )

        # Store/source subdirectories
        for folder in sorted(
            [p for p in category.iterdir() if p.is_dir()],
            key=lambda p: p.name.lower()
        ):
            entry = choose_entrypoint(folder)

            if entry:
                entries.append(
                    (folder.name, entry)
                )

        discovered[category_name] = entries

    return discovered


def run_scraper(name, script_path):
    start = time.time()

    print(f"\n[RUNNING] {name}")
    print(f"          {script_path.relative_to(REPO_ROOT)}")

    try:
        result = subprocess.run(
            [sys.executable, str(script_path)],
            cwd=str(REPO_ROOT),
	    timeout=7200,
        )

        elapsed = time.time() - start

        return (
            result.returncode == 0,
            elapsed,
            result.returncode,
        )
    except subprocess.TimeoutExpired:
        elapsed = time.time() - start
        print(f"[TIMEOUT] {name} ({elapsed:.1f}s)")
        return False, elapsed, -1

    except Exception as exc:
        elapsed = time.time() - start

        print(f"[EXCEPTION] {exc}")

        return False, elapsed, None


def print_dry_run(discovered):
    total = 0

    print("\nMASTER SCRAPER RUNNER")
    print("=" * 70)
    print("DRY RUN — hiçbir scraper çalıştırılmayacak.\n")

    for category, entries in discovered.items():
        print(f"\n## {category}")

        if not entries:
            print("   [NONE]")
            continue

        for store, script in entries:
            total += 1


            print(
                f"   [READY] {store:<25} "
                f"{script.relative_to(REPO_ROOT)}"
            )

    print("\n" + "=" * 70)
    print(f"Categories: {len(discovered)}")
    print(f"Scrapers found: {total}")
    print("=" * 70)

def _csv_meta(path):
    try:
        st = path.stat()
        return (st.st_mtime_ns, st.st_size)
    except OSError:
        return None


def _has_real_data(path):
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            first = f.readline()
            second = f.readline()
        return bool(first and second)
    except Exception:
        return False


def snapshot_csvs(script_path, category, source):
    roots = [
        script_path.parent,
        REPO_ROOT / "InflationItems" / "Datas" / category / source,
    ]

    snapshot = {}

    for root in roots:
        if not root.exists():
            continue

        for csv_file in root.rglob("*.csv"):
            try:
                snapshot[csv_file.resolve()] = _csv_meta(csv_file)
            except Exception:
                pass

    return snapshot


def move_new_csvs(script_path, category, source, before_csvs):
    target_dir = (
        REPO_ROOT
        / "InflationItems"
        / "Datas"
        / category
        / source
    )
    target_dir.mkdir(parents=True, exist_ok=True)

    after_csvs = snapshot_csvs(script_path, category, source)

    changed = []
    for csv_path, meta in after_csvs.items():
        if csv_path not in before_csvs or before_csvs.get(csv_path) != meta:
            changed.append(csv_path)

    if not changed:
        print(f"[NO_DATA] {source}: no new or updated CSV")
        return False

    valid = []

    for csv_path in changed:
        current = Path(csv_path)

        try:
            inside_target = target_dir.resolve() in current.resolve().parents
        except Exception:
            inside_target = False

        if not inside_target and current.exists():
            destination = target_dir / current.name

            try:
                if current.resolve() != destination.resolve():
                    shutil.move(str(current), str(destination))
                    current = destination
                    print(f"[DATA] Moved: {current.relative_to(REPO_ROOT)}")
            except Exception as exc:
                print(f"[DATA MOVE ERROR] {exc}")
                continue

        if current.exists() and _has_real_data(current):
            valid.append(current)

    if valid:
        print(f"[DATA_OK] {source}: {len(valid)} valid CSV")
        return True

    print(f"[NO_DATA] {source}: CSV empty/header-only")
    return False


def main():
    parser = argparse.ArgumentParser(
        description="Inflation Research Study master scraper runner"
    )

    parser.add_argument(
        "--run",
        action="store_true",
        help="Actually run scrapers"
    )

    parser.add_argument(
        "--all",
        action="store_true",
        help="Run every discovered category"
    )

    parser.add_argument(
        "--category",
        type=str,
        help="Run only one category"
    )
    parser.add_argument(
    	"--source",
    	type=str,
	help="Run only one source/store inside a category"
    )
    args = parser.parse_args()

    discovered = discover_scrapers()

    # Default = completely safe dry run
    if not args.run:
        print_dry_run(discovered)
        return

    # Extra safety: --run alone is NOT enough
    if not args.all and not args.category:
        print(
            "Safety stop: --run requires either "
            "--category CATEGORY or --all"
        )
        return

    if args.category:
        if args.category not in discovered:
            print(f"Unknown category: {args.category}")
            print("Available:")
            for category in discovered:
                print(f"  - {category}")
            return

        selected = {
            args.category: discovered[args.category]
        }

    else:
        selected = discovered
    if args.source:
        if not args.category:
            print("Safety stop: --source requires --category")
            return

        matches = [
            (store, script)
            for store, script in selected[args.category]
            if store.lower() == args.source.lower()
        ]

        if not matches:
            print(f"Source '{args.source}' not found in category '{args.category}'.")
            return

        selected = {
            args.category: matches
        }
    results = []

    for category, entries in selected.items():
        print(f"\n{'=' * 70}")
        print(f"CATEGORY: {category}")
        print("=" * 70)

        for store, script in entries:
            before_csvs = snapshot_csvs(script, category, store)
            process_success, elapsed, returncode = run_scraper(
                store,
                script,
            )

            data_ok = move_new_csvs(
                script,
                category,
                store,
                before_csvs,
            )

            success = data_ok

            if not process_success:
                print(
                    f"[PROCESS_ERROR] {store} "
                    f"(exit={returncode})"
                )
            results.append(
                (
                    category,
                    store,
                    script,
                    success,
                    elapsed,
                    returncode,
                )
            )

            status = "DATA_OK" if success else "NO_DATA"

            print(
                f"[{status}] {store} "
                f"({elapsed:.1f}s)"
            )

    print("\n" + "=" * 70)
    print("FINAL SUMMARY")
    print("=" * 70)

    success_count = sum(
        1 for r in results if r[3]
    )

    error_count = len(results) - success_count

    print(f"Total:      {len(results)}")
    print(f"Successful: {success_count}")
    print(f"Failed:     {error_count}")

    if error_count:
        print("\nFailed scrapers:")

        for category, store, script, success, elapsed, code in results:
            if not success:
                print(
                    f" - {category} / {store}: "
                    f"{script.relative_to(REPO_ROOT)}"
                )


if __name__ == "__main__":
    main()
