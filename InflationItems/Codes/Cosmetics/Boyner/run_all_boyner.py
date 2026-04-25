import os
import sys
import subprocess
import pandas as pd
from datetime import datetime

# ── CONFIGURATION ────────────────────────────────────────────────────────────
# The names of your 4 scraper scripts
SCRIPTS_TO_RUN = [
    "boyner_scraper1.py",
    "boyner_scraper2.py",
    "boyner_scraper3.py",
    "boyner_scraper4.py"
]

# The unique identifiers you put inside each script (part1, part2, etc.)
PART_IDENTIFIERS = ["part1", "part2", "part3", "part4"]


# ─────────────────────────────────────────────────────────────────────────────

def run_parallel_scrapers():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    processes = []

    print("\n🚀 STARTING PARALLEL EXECUTION...")
    print("=" * 50)

    # 1. Launch all 4 scripts simultaneously
    for script_name in SCRIPTS_TO_RUN:
        script_path = os.path.join(current_dir, script_name)

        if not os.path.exists(script_path):
            print(f"  ❌ ERROR: Could not find {script_name} in {current_dir}")
            continue

        print(f"  ▶️ Launching {script_name}...")

        # sys.executable ensures it uses your .venv python, not the global one
        process = subprocess.Popen([sys.executable, script_path])
        processes.append(process)

    print("\n⏳ All 4 scrapers are now running in the background.")
    print("   Please wait for them to finish. This may take a few minutes...")

    # 2. Wait for all scripts to finish before moving to the merge step
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

            # Clean up: Delete the part file after reading it to keep the folder tidy
            os.remove(part_filepath)
            print(f"     🗑️ Deleted temporary file {part_filename}")
        else:
            print(f"  ⚠️ Warning: Could not find {part_filename}. Did that script crash?")

    # 2. Merge and Save
    if all_dataframes:
        print("\n  ⚙️ Merging all data together...")

        # Combine all dataframes into one
        master_df = pd.concat(all_dataframes, ignore_index=True)

        # Drop any accidental duplicates just in case brands overlapped
        initial_count = len(master_df)
        master_df.drop_duplicates(subset=["Product Name", "Category"], inplace=True)
        duplicates_removed = initial_count - len(master_df)
        if duplicates_removed > 0:
            print(f"  ✂️ Removed {duplicates_removed} overlapping duplicate products.")

        # Save the final Master CSV
        final_filename = f"boyner_{date_str}.csv"
        final_filepath = os.path.join(data_dir, final_filename)

        master_df.to_csv(final_filepath, index=False, encoding="utf-8-sig")

        print(f"\n🏆 SUCCESS! Master file created.")
        print(f"📊 Total Unique Products: {len(master_df)}")
        print(f"📁 Location: {final_filepath}")

    else:
        print("\n❌ MERGE FAILED: No partial CSV files were found to merge.")


if __name__ == "__main__":
    # Execute the two steps in order
    run_parallel_scrapers()
    merge_csv_files()