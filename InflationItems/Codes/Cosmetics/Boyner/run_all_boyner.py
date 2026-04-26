import os
import sys
import subprocess
import pandas as pd
import time
from datetime import datetime

# ── CONFIGURATION ────────────────────────────────────────────────────────────
SCRIPTS_TO_RUN = [
    "boyner_scraper1.py",
    "boyner_scraper2.py",
    "boyner_scraper3.py",
    "boyner_scraper4.py"
]

PART_IDENTIFIERS = ["part1", "part2", "part3", "part4"]


# ─────────────────────────────────────────────────────────────────────────────

def run_parallel_scrapers():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    processes = []

    print("\n🚀 STARTING PARALLEL EXECUTION...")
    print("=" * 50)

    # 1. Launch scripts with a staggered delay to prevent driver collision
    for index, script_name in enumerate(SCRIPTS_TO_RUN):
        script_path = os.path.join(current_dir, script_name)

        if not os.path.exists(script_path):
            print(f"  ❌ ERROR: Could not find {script_name} in {current_dir}")
            continue

        print(f"  ▶️ Launching {script_name}...")
        process = subprocess.Popen([sys.executable, script_path])
        processes.append(process)

        # STAGGERED LAUNCH: Wait 7 seconds before launching the next script.
        # This prevents the 'FileExistsError' browser patching crash.
        if index < len(SCRIPTS_TO_RUN) - 1:
            print("     ⏳ Pausing 7 seconds to let the browser driver initialize...")
            time.sleep(7)

    print("\n✅ All 4 scrapers are now safely running in the background.")
    print("   Please wait for them to finish. This may take a few minutes...\n")

    # 2. Wait for all scripts to finish
    for process in processes:
        process.wait()

    print("\n✅ All scrapers have successfully finished their tasks!")


def merge_csv_files():
    print("\n🧩 INITIATING DATA MERGE...")
    print("=" * 50)

    current_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.abspath(os.path.join(current_dir, "..", "..", ".."))
    data_dir = os.path.join(root_dir, "Datas", "Cosmetics", "Boyner")

    date_str = datetime.now().strftime("%Y-%m-%d")
    all_dataframes = []

    # 1. Gather all the part files
    for part in PART_IDENTIFIERS:
        part_filename = f"boyner_{part}_{date_str}.csv"
        part_filepath = os.path.join(data_dir, part_filename)

        if os.path.exists(part_filepath):
            print(f"  📄 Found {part_filename}...")
            df = pd.read_csv(part_filepath)
            all_dataframes.append(df)

            # Clean up temporary file
            os.remove(part_filepath)
            print(f"     🗑️ Deleted temporary file {part_filename}")
        else:
            print(f"  ⚠️ Warning: Could not find {part_filename}.")

    # 2. Merge and Save
    if all_dataframes:
        print("\n  ⚙️ Merging all data together...")

        master_df = pd.concat(all_dataframes, ignore_index=True)

        initial_count = len(master_df)
        master_df.drop_duplicates(subset=["Product Name", "Category"], inplace=True)
        duplicates_removed = initial_count - len(master_df)

        if duplicates_removed > 0:
            print(f"  ✂️ Removed {duplicates_removed} overlapping duplicate products.")

        final_filename = f"boyner_{date_str}.csv"
        final_filepath = os.path.join(data_dir, final_filename)

        master_df.to_csv(final_filepath, index=False, encoding="utf-8-sig")

        print(f"\n🏆 SUCCESS! Master file created.")
        print(f"📊 Total Unique Products: {len(master_df)}")
        print(f"📁 Location: {final_filepath}")

    else:
        print("\n❌ MERGE FAILED: No partial CSV files were found to merge.")


if __name__ == "__main__":
    run_parallel_scrapers()
    merge_csv_files()