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
  - InflationItems/Datas/x/collected_first_column_strings.csv
      Created inside each processed folder and contains that folder's distinct
      first-column strings.

Generated output CSVs are ignored during scanning so re-running the script does
not cause the output files to be read as input.

"String-like" means: non-empty and not parseable as a number.
This avoids treating values such as 123, 45.6, or 1,234 as names.

Usage:
    python check_inflation_items.py
    python check_inflation_items.py --root InflationItems/Datas
    python check_inflation_items.py --skip-header
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Dict, Iterable, List, Set, Tuple


DEFAULT_ROOT = Path("InflationItems") / "Datas"
COLLECTED_STRINGS_FILENAME = "collected_first_column_strings.csv"
BROKEN_SUBFOLDERS_FILENAME = "broken_subfolders.csv"
GENERATED_FILENAMES = {COLLECTED_STRINGS_FILENAME, BROKEN_SUBFOLDERS_FILENAME}


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
    Generated output CSVs are ignored.
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


def write_collected_strings_csv(folder: Path, unique_names: Set[str]) -> None:
    """Write collected unique strings into a CSV inside the given folder."""
    output_path = folder / COLLECTED_STRINGS_FILENAME

    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["name"])
        for name in sorted(unique_names):
            writer.writerow([name])


def write_broken_subfolders_csv(root: Path, broken_folders: List[Path]) -> None:
    """Write all broken folder paths into one CSV in the root folder."""
    output_path = root / BROKEN_SUBFOLDERS_FILENAME

    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["broken_subfolder"])
        for folder in broken_folders:
            writer.writerow([relative_display_path(folder)])


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
    args = parser.parse_args()

    root = args.root
    if not root.exists() or not root.is_dir():
        print(f"Root folder does not exist or is not a directory: {root}")
        return 1

    collected_by_folder: Dict[Path, Set[str]] = {}
    broken_folders: List[Path] = []
    found_any_csv = False

    # First traverse and collect everything without writing per-folder output CSVs.
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

    # Then save each folder's collected strings into that same folder.
    for folder, unique_names in collected_by_folder.items():
        write_collected_strings_csv(folder, unique_names)
        print(f"Saved collected strings to {relative_display_path(folder / COLLECTED_STRINGS_FILENAME)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
