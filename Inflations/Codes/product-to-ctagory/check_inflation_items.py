#!/usr/bin/env python3
"""
Recursively scan InflationItems/Datas for folders containing CSV files.

For each folder that directly contains one or more source .csv files, this script:
  1. Reads every source CSV in that folder.
  2. Checks column index 0 in every row.
  3. Prints:
       InflationItems/Datas/x index=0 reached string
     if every checked value in column 0 is a non-empty string-like value.
     Otherwise prints:
       InflationItems/Datas/x broken
  4. Collects all distinct string-like names found in column 0 across all source
     CSVs in that folder.

After all folders have been traversed, this script writes:
  - InflationItems/Datas/broken_subfolders.csv
      Contains the names/paths of all broken folders.
  - InflationItems/Datas/x/collected_first_column_strings.json
      Created inside each processed folder and contains that folder's distinct
      first-column strings as a JSON array.
  - InflationItems/Datas/all_collected_first_column_strings.json
      One big JSON array containing every distinct collected string from all
      per-folder JSON files. Strings longer than 75 characters are removed from
      this big JSON because they are assumed not to be product names.
  - InflationItems/Datas/product-category-map.csv
      Contains collected strings matched to category/product names from the
      category CSV.

Category matching:
  - The category CSV is expected to be named tuik_cpi_categories_comma.csv and
    to be in the same folder as this script.
  - Only leaf category rows are used as product/category match candidates.
  - Longer names are checked first, so a specific name like "Fıstık ezmesi" is
    tried before a shorter name like "Fıstık".
  - If a collected string contains a category/product name, it is mapped to that
    category/product row.

Generated output files are ignored during scanning so re-running the script does
not cause previous output files to be read as input.

"String-like" means: non-empty and not parseable as a number.
This avoids treating values such as 123, 45.6, or 1,234 as names.

Usage:
    python check_inflation_items.py
    python check_inflation_items.py --root InflationItems/Datas
    python check_inflation_items.py --skip-header
    python check_inflation_items.py --category-csv tuik_cpi_categories_comma.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple


DEFAULT_ROOT = Path("../../../InflationItems") / "Datas"
DEFAULT_CATEGORY_CSV_FILENAME = "tuik_cpi_categories_comma.csv"
COLLECTED_STRINGS_FILENAME = "collected_first_column_strings.json"
OLD_COLLECTED_STRINGS_CSV_FILENAME = "collected_first_column_strings.csv"
BROKEN_SUBFOLDERS_FILENAME = "broken_subfolders.csv"
ALL_COLLECTED_STRINGS_FILENAME = "all_collected_first_column_strings.json"
PRODUCT_CATEGORY_MAP_FILENAME = "product-category-map.csv"
MAX_PRODUCT_NAME_LENGTH = 75

GENERATED_FILENAMES = {
    COLLECTED_STRINGS_FILENAME,
    OLD_COLLECTED_STRINGS_CSV_FILENAME,
    BROKEN_SUBFOLDERS_FILENAME,
    ALL_COLLECTED_STRINGS_FILENAME,
    PRODUCT_CATEGORY_MAP_FILENAME,
}


CategoryRow = Dict[str, str]
CompiledCategoryRow = Dict[str, object]


def is_number(value: str) -> bool:
    """Return True if value can reasonably be interpreted as a number."""
    cleaned = value.strip()
    if not cleaned:
        return False

    # Support common thousands separators: 1,234 -> 1234
    cleaned = cleaned.replace(",", "")

    try:
        float(cleaned)
        return True
    except ValueError:
        return False


def is_string_like(value: str) -> bool:
    """A valid name/string is non-empty and not numeric."""
    stripped = value.strip()
    return bool(stripped) and not is_number(stripped)


def relative_display_path(path: Path) -> str:
    """Display folders as InflationItems/Datas/x instead of absolute paths when possible."""
    try:
        return str(path.relative_to(Path.cwd())).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def read_first_column_values(csv_path: Path, skip_header: bool = False) -> Tuple[List[str], bool]:
    """
    Return first-column values from a CSV and whether the CSV structure was valid.

    valid_structure is False if a row is empty / missing column index 0 or if the file
    cannot be decoded/read as CSV.
    """
    values: List[str] = []
    valid_structure = True

    # Try UTF-8 first, then UTF-8 with BOM, then latin-1 as a permissive fallback.
    encodings = ("utf-8", "utf-8-sig", "latin-1")
    last_error: Exception | None = None

    for encoding in encodings:
        try:
            with csv_path.open("r", newline="", encoding=encoding) as f:
                reader = csv.reader(f)
                for row_index, row in enumerate(reader):
                    if skip_header and row_index == 0:
                        continue

                    if not row:
                        valid_structure = False
                        continue

                    values.append(row[0])
            return values, valid_structure
        except UnicodeDecodeError as exc:
            last_error = exc
            continue
        except csv.Error as exc:
            last_error = exc
            break
        except OSError as exc:
            last_error = exc
            break

    print(f"Could not read CSV: {csv_path} ({last_error})")
    return values, False


def iter_folders_with_csvs(root: Path) -> Iterable[Tuple[Path, List[Path]]]:
    """
    Recursively yield each folder under root that directly contains source CSV files.

    CSV files in child folders are handled when that child folder is yielded.
    Generated output files are ignored.
    """
    folders = [root, *[p for p in root.rglob("*") if p.is_dir()]]

    for folder in sorted(folders):
        csv_files = sorted(
            p
            for p in folder.iterdir()
            if p.is_file()
            and p.suffix.lower() == ".csv"
            and p.name not in GENERATED_FILENAMES
        )
        if csv_files:
            yield folder, csv_files


def process_folder(folder: Path, csv_files: List[Path], skip_header: bool) -> Tuple[bool, Set[str]]:
    """
    Process all source CSV files directly inside one folder.

    Returns:
        (folder_is_ok, unique_names)
    """
    all_checked_values_are_strings = True
    unique_names: Set[str] = set()

    for csv_file in csv_files:
        first_column_values, valid_structure = read_first_column_values(csv_file, skip_header=skip_header)

        if not valid_structure or not first_column_values:
            all_checked_values_are_strings = False

        for value in first_column_values:
            stripped = value.strip()
            if is_string_like(stripped):
                unique_names.add(stripped)
            else:
                all_checked_values_are_strings = False

    display_path = relative_display_path(folder)
    if all_checked_values_are_strings:
        print(f"{display_path} index=0 reached string")
    else:
        print(f"{display_path} broken")

    return all_checked_values_are_strings, unique_names


def write_collected_strings_json(folder: Path, unique_names: Set[str]) -> None:
    """Write collected unique strings into a JSON file inside the given folder."""
    output_path = folder / COLLECTED_STRINGS_FILENAME

    with output_path.open("w", encoding="utf-8") as f:
        json.dump(sorted(unique_names), f, indent=2, ensure_ascii=False)
        f.write("\n")


def write_broken_subfolders_csv(root: Path, broken_folders: List[Path]) -> None:
    """Write all broken folder paths into one CSV in the root folder."""
    output_path = root / BROKEN_SUBFOLDERS_FILENAME

    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["broken_subfolder"])
        for folder in broken_folders:
            writer.writerow([relative_display_path(folder)])


def collect_per_folder_jsons(root: Path) -> Set[str]:
    """Read every collected_first_column_strings.json under root and return one unique set."""
    all_strings: Set[str] = set()

    for json_path in sorted(root.rglob(COLLECTED_STRINGS_FILENAME)):
        try:
            with json_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError) as exc:
            print(f"Could not read JSON: {relative_display_path(json_path)} ({exc})")
            continue

        if not isinstance(data, list):
            print(f"Skipping JSON because it is not a list: {relative_display_path(json_path)}")
            continue

        for value in data:
            if isinstance(value, str):
                stripped = value.strip()
                if stripped:
                    all_strings.add(stripped)

    return all_strings


def write_big_collected_json(root: Path, all_strings: Set[str]) -> Tuple[Path, List[str], int]:
    """
    Save one big JSON containing all collected strings, excluding strings > 75 chars.

    Returns:
        (output_path, filtered_strings, deleted_count)
    """
    filtered_strings = sorted(s for s in all_strings if len(s) <= MAX_PRODUCT_NAME_LENGTH)
    deleted_count = len(all_strings) - len(filtered_strings)
    output_path = root / ALL_COLLECTED_STRINGS_FILENAME

    with output_path.open("w", encoding="utf-8") as f:
        json.dump(filtered_strings, f, indent=2, ensure_ascii=False)
        f.write("\n")

    return output_path, filtered_strings, deleted_count


def normalize_for_match(value: str) -> str:
    """
    Normalize text for matching while handling Turkish dotted/dotless I.

    This keeps Turkish letters meaningful, but makes matching case-insensitive.
    """
    value = value.strip()

    # Python's default lower/casefold is not Turkish-locale-aware for I/İ.
    value = value.replace("İ", "i").replace("I", "ı")
    value = value.casefold()

    # Collapse all whitespace to single spaces.
    value = re.sub(r"\s+", " ", value)
    return value


def compile_category_products(category_products: List[CategoryRow]) -> List[CompiledCategoryRow]:
    """
    Pre-compile category/product match patterns.

    This is much faster than compiling a regex for every collected string and
    every category/product pair. Longer product names must already be sorted
    first by load_leaf_category_products().
    """
    compiled_products: List[CompiledCategoryRow] = []

    for category_product in category_products:
        normalized_product = normalize_for_match(category_product["turkish_name"])
        if not normalized_product:
            continue

        # Word-boundary-ish check so short names such as "Su" are not matched
        # inside larger words such as "Susam".
        pattern = re.compile(rf"(?<![\w]){re.escape(normalized_product)}(?![\w])", re.UNICODE)
        compiled_products.append(
            {
                "code": category_product["code"],
                "turkish_name": category_product["turkish_name"],
                "english_name": category_product["english_name"],
                "pattern": pattern,
            }
        )

    return compiled_products


def resolve_category_csv(cli_category_csv: Optional[Path]) -> Path:
    """Resolve the category CSV path, defaulting to the script folder."""
    if cli_category_csv is not None:
        return cli_category_csv

    script_dir = Path(__file__).resolve().parent
    default_path = script_dir / DEFAULT_CATEGORY_CSV_FILENAME
    if default_path.exists():
        return default_path

    # Helpful fallback for this workspace if the uploaded file is still in uploads/.
    uploads_fallback = script_dir / "uploads" / DEFAULT_CATEGORY_CSV_FILENAME
    if uploads_fallback.exists():
        return uploads_fallback

    return default_path


def load_leaf_category_products(category_csv_path: Path) -> List[CategoryRow]:
    """
    Load category CSV rows and keep only leaf rows.

    A row is considered a leaf if no other row's code starts with this row's code.
    These leaf rows are the most product-like entries in the category hierarchy.
    """
    rows: List[CategoryRow] = []

    with category_csv_path.open("r", newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        required_columns = {"code", "turkish_name", "english_name"}
        missing_columns = required_columns - set(reader.fieldnames or [])
        if missing_columns:
            raise ValueError(
                f"Category CSV is missing required columns: {', '.join(sorted(missing_columns))}"
            )

        for row in reader:
            code = (row.get("code") or "").strip()
            turkish_name = (row.get("turkish_name") or "").strip()
            english_name = (row.get("english_name") or "").strip()

            if not code or not turkish_name:
                continue

            rows.append(
                {
                    "code": code,
                    "turkish_name": turkish_name,
                    "english_name": english_name,
                }
            )

    codes = [row["code"] for row in rows]
    leaf_rows: List[CategoryRow] = []

    for row in rows:
        code = row["code"]
        is_leaf = not any(other_code != code and other_code.startswith(code) for other_code in codes)
        if is_leaf:
            leaf_rows.append(row)

    # Check longer category/product names first, so e.g. "Fıstık ezmesi" wins
    # before the shorter "Fıstık" if both are present.
    leaf_rows.sort(
        key=lambda row: len(normalize_for_match(row["turkish_name"])),
        reverse=True,
    )
    return leaf_rows


def write_product_category_map_csv(
    root: Path,
    collected_strings: List[str],
    category_products: List[CategoryRow],
) -> Tuple[Path, int, int]:
    """
    Match collected strings to category products and write product-category-map.csv.

    Only matched strings are written.

    Returns:
        (output_path, matched_count, unmatched_count)
    """
    output_path = root / PRODUCT_CATEGORY_MAP_FILENAME
    matched_count = 0
    unmatched_count = 0
    total_strings = len(collected_strings)

    print(
        f"Starting product/category matching for {total_strings} strings "
        f"against {len(category_products)} category products..."
    )

    compiled_category_products = compile_category_products(category_products)
    print(f"Prepared {len(compiled_category_products)} category match patterns")

    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "collected_string",
                "matched_category_code",
                "matched_category_turkish_name",
                "matched_category_english_name",
            ]
        )

        for index, collected_string in enumerate(collected_strings, start=1):
            if index == 1 or index % 1000 == 0 or index == total_strings:
                print(f"Matching progress: {index}/{total_strings}")

            normalized_collected_string = normalize_for_match(collected_string)
            matched_row: Optional[CompiledCategoryRow] = None

            for category_product in compiled_category_products:
                pattern = category_product["pattern"]
                if not isinstance(pattern, re.Pattern):
                    continue

                if pattern.search(normalized_collected_string):
                    matched_row = category_product
                    break

            if matched_row is None:
                unmatched_count += 1
                continue

            matched_count += 1
            writer.writerow(
                [
                    collected_string,
                    matched_row["code"],
                    matched_row["turkish_name"],
                    matched_row["english_name"],
                ]
            )

    return output_path, matched_count, unmatched_count


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check first column of CSV files under InflationItems/Datas and save collected names."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=DEFAULT_ROOT,
        help="Root folder to scan. Default: InflationItems/Datas",
    )
    parser.add_argument(
        "--skip-header",
        action="store_true",
        help="Skip the first row of every CSV file.",
    )
    parser.add_argument(
        "--category-csv",
        type=Path,
        default=None,
        help=(
            "Category CSV used for product matching. Default: "
            "tuik_cpi_categories_comma.csv in the same folder as this script."
        ),
    )
    args = parser.parse_args()

    root = args.root
    if not root.exists() or not root.is_dir():
        print(f"Root folder does not exist or is not a directory: {root}")
        return 1

    category_csv_path = resolve_category_csv(args.category_csv)

    collected_by_folder: Dict[Path, Set[str]] = {}
    broken_folders: List[Path] = []
    found_any_csv = False

    # First traverse and collect everything without writing per-folder output files.
    # This prevents generated files from affecting the current run.
    for folder, csv_files in iter_folders_with_csvs(root):
        found_any_csv = True
        folder_is_ok, unique_names = process_folder(folder, csv_files, skip_header=args.skip_header)
        collected_by_folder[folder] = unique_names

        if not folder_is_ok:
            broken_folders.append(folder)

    if not found_any_csv:
        print(f"No source CSV files found under {root}")

    # After traversal, save the broken subfolder list.
    write_broken_subfolders_csv(root, broken_folders)
    print(f"Saved broken subfolders to {relative_display_path(root / BROKEN_SUBFOLDERS_FILENAME)}")

    # Save each folder's collected strings into that same folder as JSON.
    for folder, unique_names in collected_by_folder.items():
        write_collected_strings_json(folder, unique_names)
        print(f"Saved collected strings to {relative_display_path(folder / COLLECTED_STRINGS_FILENAME)}")

    # Collect all per-folder JSON files into one big JSON.
    all_collected_strings = collect_per_folder_jsons(root)
    big_json_path, filtered_collected_strings, deleted_count = write_big_collected_json(
        root,
        all_collected_strings,
    )
    print(f"Deleted {deleted_count} strings longer than {MAX_PRODUCT_NAME_LENGTH} characters")
    print(f"Saved all collected strings to {relative_display_path(big_json_path)}")

    # Match the collected product strings against the category CSV and save the map.
    if not category_csv_path.exists() or not category_csv_path.is_file():
        print(f"Category CSV does not exist: {category_csv_path}")
        print("Skipping product-category-map.csv creation")
        return 1

    try:
        category_products = load_leaf_category_products(category_csv_path)
    except (OSError, csv.Error, ValueError) as exc:
        print(f"Could not load category CSV: {category_csv_path} ({exc})")
        return 1

    print(f"Loaded {len(category_products)} leaf category products from {relative_display_path(category_csv_path)}")

    map_path, matched_count, unmatched_count = write_product_category_map_csv(
        root,
        filtered_collected_strings,
        category_products,
    )
    print(f"Saved product/category map to {relative_display_path(map_path)}")
    print(f"Matched {matched_count} strings; {unmatched_count} strings were not matched")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
