import argparse
import subprocess
import os
import sys
import time
import re
from datetime import datetime, timedelta
import glob

# --- Palette ---
CYAN    = "\033[96m"
GREEN   = "\033[92m"
YELLOW  = "\033[93m"
RED     = "\033[91m"
WHITE   = "\033[97m"
MAGENTA = "\033[95m"
BOLD    = "\033[1m"
RESET   = "\033[0m"
CLEAR   = "\033[H\033[J" # Clear screen

# Table Configuration
TABLE_WIDTH = 140

# Hardcoded totals for progress tracking
HAPELOGLU_CATS = [
    "Meyve, Sebze", "Et, Tavuk, Balık", "Süt, Kahvaltılık", "İçecek", "Temel Gıda",
    "Fırın, Pastane", "Atıştırmalık", "Deterjan, Temizlik", "Kağıt, Islak Mendil",
    "Kişisel Bakım, Kozmetik", "Bebek", "Ev, Yaşam", "Evcil Hayvan"
]
ERZURUM_CITIES = ["Erzurum", "Erzincan", "Bayburt"]

def get_last_lines_fast(log_path, num_bytes=8192):
    if not os.path.exists(log_path): return []
    try:
        with open(log_path, "rb") as f:
            f.seek(0, 2)
            size = f.tell()
            f.seek(max(0, size - num_bytes))
            data = f.read().decode("utf-8", errors="ignore")
            return [l.strip() for l in data.splitlines() if l.strip()]
    except: return []

def parse_advanced_progress(name, lines):
    # 1. EEB (Global) — Prioritize items-based progress to avoid categorical jumps
    if name == "EEB":
        items = count_items_from_log(lines)
        # Based on successful runs, we estimate ~2210 items total
        return items, 2210, 0.0

    # 2. Safe progress patterns (Universal)
    for line in reversed(lines):
        line_clean = strip_ansi(line)
        # Bracket form: [120/334]
        match = re.search(r"\[(\d+)/(\d+)\]", line_clean)
        if match: return int(match.group(1)), int(match.group(2)), 0.0
        # tqdm form
        match = re.search(r"\|\s*(\d+)/(\d+)\s*\[", line_clean)
        if match: return int(match.group(1)), int(match.group(2)), 0.0

    # 3. Sub-page granularity
    sub_page_pct = 0.0
    for line in reversed(lines):
        line_clean = strip_ansi(line)
        page_match = re.search(r"Page (\d+):", line_clean)
        if page_match:
            sub_page_pct = min(0.95, int(page_match.group(1)) / 20.0)
            break

    # 4. Scraper-specific parsing
    if name == "Hapeloglu":
        for line in reversed(lines):
            for i, cat in enumerate(HAPELOGLU_CATS):
                if cat.lower() in line.lower(): return i + 1, len(HAPELOGLU_CATS), sub_page_pct
                    
    return None

def parse_tqdm_eta(lines):
    """Extract tqdm's own remaining-time estimate (more accurate than ours)."""
    for line in reversed(lines):
        # tqdm format: [01:29<02:28, ...] — we want the 02:28 part
        match = re.search(r"\[\d+[:\d]*<(\d+):(\d+)", strip_ansi(line))
        if match:
            mins, secs = int(match.group(1)), int(match.group(2))
            return mins * 60 + secs
    return None

def count_items_from_log(lines):
    """Extract the total items/products count from scraper logs."""
    for line in reversed(lines):
        clean = strip_ansi(line)
        # Universal: "[ITEMS] 2362 total items collected" or "[DONE] 2362 items saved"
        m = re.search(r"\[ITEMS\]\s*(\d+)", clean)
        if m: return int(m.group(1))
        m = re.search(r"\[DONE\]\s*(\d+)", clean)
        if m: return int(m.group(1))
        m = re.search(r"Snapshot updated:\s*(\d+)\s+unique\b", clean)
        if m: return int(m.group(1))
        m = re.search(r"Final unique .* count:\s*(\d+)", clean)
        if m: return int(m.group(1))
        # EEB specific: "(total so far: 301)"
        m = re.search(r"total so far:\s*(\d+)", clean)
        if m: return int(m.group(1))
        # Fallback: Bershka tqdm "total unique so far: N" or general "X items saved"
        m = re.search(r"(?:unique so far|items saved):\s*(\d+)", clean)
        if m: return int(m.group(1))
    return 0

def get_historical_stats(name, codes_dir):
    """Scan the last 7 days of CSVs to calculate the average item count baseline."""
    project_root = os.path.dirname(codes_dir)
    datas_root = os.path.join(project_root, "Datas")
    
    patterns = {
        "Nalburadam": os.path.join(datas_root, "ConstructionSuppliesMarkets", "Nalburadam", "nalburadam_*.csv"),
        "Bershka":    os.path.join(datas_root, "ClothingStores", "Bershka", "ProductData", "bershka_*.csv"),
        "Hapeloglu":  os.path.join(datas_root, "Markets", "Hapeloglu", "hapeloglu_*.csv"),
        "EEB":        os.path.join(datas_root, "HousesRent", "ErzurumErzincanBayburt", "*", "*_*.csv"),
        "Karaca":     os.path.join(datas_root, "HomeGoods", "Karaca", "karaca_*.csv"),
        "GoldenRose": os.path.join(datas_root, "Cosmetics", "GoldenRose", "goldenrose_*.csv"),
    }
    
    if name not in patterns: return 0
    files = glob.glob(patterns[name])
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    # date_str -> total_items
    daily_totals = {}
    for f in files:
        match = re.search(r"(\d{4}-\d{2}-\d{2})", os.path.basename(f))
        if not match: continue
        f_date = match.group(1)
        if f_date == today_str: continue 
        
        try:
            dt = datetime.strptime(f_date, "%Y-%m-%d")
            if (datetime.now() - dt).days > 7: continue
        except: continue
        
        # Count lines minus header
        try:
            with open(f, 'r', encoding='utf-8', errors='ignore') as fh:
                count = sum(1 for _ in fh) - 1
                daily_totals[f_date] = daily_totals.get(f_date, 0) + max(0, count)
        except: continue
        
    if not daily_totals: return 0
    return sum(daily_totals.values()) / len(daily_totals)

def strip_ansi(text):
    return re.sub(r'\033\[[0-9;]*m', '', text)

def clean_for_display(text):
    """Strip ANSI codes and wide/emoji characters that break alignment."""
    clean = strip_ansi(text)
    # Remove any non-ASCII characters (emojis, special symbols)
    return clean.encode('ascii', 'ignore').decode('ascii')


def format_row(content_left, content_right="", width=TABLE_WIDTH):
    raw_left = strip_ansi(content_left)
    raw_right = strip_ansi(content_right)
    max_left = width - 6 - len(raw_right)
    if len(raw_left) > max_left:
        content_left = content_left[:max_left-3] + "..."
        raw_left = strip_ansi(content_left)
    space_needed = width - 4 - len(raw_left) - len(raw_right)
    padding = " " * max(0, space_needed)
    return f"{WHITE}║ {RESET}{content_left}{padding}{content_right}{WHITE} ║{RESET}"


def _build_parser():
    parser = argparse.ArgumentParser(
        description="Run Batu Koray Masak's full scrape orchestration."
    )
    parser.add_argument(
        "--only",
        type=str,
        default="",
        help="Comma-separated scraper names to run: Nalburadam,Bershka,Hapeloglu,EEB,Karaca,GoldenRose",
    )
    parser.add_argument(
        "--skip",
        type=str,
        default="",
        help="Comma-separated scraper names to skip: Nalburadam,Bershka,Hapeloglu,EEB,Karaca,GoldenRose",
    )
    parser.add_argument(
        "--skip-inflation",
        action="store_true",
        help="Skip the automatic inflation calculation after scraping.",
    )
    return parser


def _parse_name_list(raw_value):
    return {
        part.strip().lower()
        for part in raw_value.split(",")
        if part.strip()
    }


def main():
    args = _build_parser().parse_args()

    # Pathing: script_dir is batukoraymasak, so we go up two levels to reach Codes/
    script_dir = os.path.dirname(os.path.abspath(__file__))
    codes_dir = os.path.dirname(os.path.dirname(script_dir))
    logs_dir = os.path.join(script_dir, "batus_logs")
    os.makedirs(logs_dir, exist_ok=True)
    
    my_scrapers = [
        ("Nalburadam", os.path.join(codes_dir, "ConstructionSuppliesMarkets", "Nalburadam")),
        ("Bershka",    os.path.join(codes_dir, "ClothingStores", "Bershka")),
        ("Hapeloglu",  os.path.join(codes_dir, "Markets", "Hapeloglu")),
        ("EEB",        os.path.join(codes_dir, "HousesRent", "ErzurumErzincanBayburt")),
        ("Karaca",     os.path.join(codes_dir, "HomeGoods", "Karaca")),
        ("GoldenRose", os.path.join(codes_dir, "Cosmetics", "GoldenRose")),
    ]

    allowed_names = {name.lower() for name, _ in my_scrapers}
    only_names = _parse_name_list(args.only)
    skip_names = _parse_name_list(args.skip)

    unknown_names = sorted((only_names | skip_names) - allowed_names)
    if unknown_names:
        print(f"{RED}Unknown scraper name(s): {', '.join(unknown_names)}{RESET}")
        sys.exit(1)

    if only_names:
        my_scrapers = [item for item in my_scrapers if item[0].lower() in only_names]

    if skip_names:
        my_scrapers = [item for item in my_scrapers if item[0].lower() not in skip_names]

    if not my_scrapers:
        print(f"{RED}No scrapers selected after applying --only/--skip.{RESET}")
        sys.exit(1)
    
    processes = []
    log_file_objects = []
    start_time = datetime.now()
    
    BANNER = [
        f"   {MAGENTA}Batu Koray Masak{RESET}",
        "",
    ]


    sys.stdout.write("\033[?25l")
    
    try:
        while not processes or any(d["status"] == "RUNNING" for d in processes):
            if not processes:
                for name, path in my_scrapers:
                    log_path = os.path.join(logs_dir, f"{name}.log")
                    f = open(log_path, "w", encoding="utf-8")
                    log_file_objects.append(f)
                    cmd = ["uv", "run", "python", "-m", "scripts.run_scraper"]
                    p = subprocess.Popen(cmd, cwd=path, stdout=f, stderr=subprocess.STDOUT)
                    processes.append({"name": name, "proc": p, "log": log_path, "status": "RUNNING", "done": 1, "total": 100, "finish_time": None})

            elapsed = datetime.now() - start_time
            sys.stdout.write("\033[H")
            

            for line in BANNER:
                print(f"   {WHITE}{BOLD}{line}{RESET}")

            print(f"\n{YELLOW}Starting {len(my_scrapers)} scrapers...{RESET}\n")

            print(f"{WHITE}╔{'═' * (TABLE_WIDTH - 2)}╗{RESET}")
            print(format_row(f"{BOLD}ACTIVE ENGINE STATUS{RESET}", f"Elapsed: {YELLOW}{str(elapsed).split('.')[0]}{RESET}"))
            print(f"{WHITE}╠{'═' * (TABLE_WIDTH - 2)}╣{RESET}")
            
            total_progress_sum = 0
            max_remaining_seconds = 0
            
            for d in processes:
                if d["status"] == "RUNNING":
                    if d["proc"].poll() is not None:
                        d["status"] = "COMPLETE" if d["proc"].returncode == 0 else "ERROR"
                        d["finish_time"] = datetime.now()
                
                recent_lines = get_last_lines_fast(d["log"])
                # For display: skip tag lines, show actual work log
                last_line = "Initializing..."
                for rl in reversed(recent_lines):
                    cl = strip_ansi(rl)
                    if not any(tag in cl for tag in ["[ITEMS]", "[PROGRESS]", "[DONE]"]):
                        last_line = rl
                        break
                prog_data = parse_advanced_progress(d["name"], recent_lines)
                
                if prog_data:
                    done, total, sub = prog_data
                    d["done"], d["total"] = done, total
                    if d["name"] == "EEB":
                        # Direct items-to-total percentage
                        pct = (done / total * 100) if total > 0 else 0
                    else:
                        # Category + Sub-page percentage
                        pct = ((done - 1 + max(sub, 0.1)) / total * 100) if total > 0 else 0
                else:
                    pct = (d["done"] / d["total"] * 100) if d["total"] > 0 else 1.0

                # A finished scraper is always 100%
                if d["status"] == "COMPLETE":
                    pct = 100.0

                # Per-scraper ETA: prefer tqdm's own estimate, fall back to our math
                scraper_eta = ""
                if d["status"] == "RUNNING":
                    tqdm_remaining = parse_tqdm_eta(recent_lines)
                    if tqdm_remaining is not None:
                        scraper_eta = str(timedelta(seconds=tqdm_remaining))
                    elif pct > 0.5:
                        est = (elapsed.total_seconds() / pct) * 100 - elapsed.total_seconds()
                        scraper_eta = str(timedelta(seconds=int(max(0, est))))
                    else:
                        scraper_eta = "..."
                elif d["status"] == "COMPLETE":
                    dur = (d["finish_time"] - start_time)
                    scraper_eta = f"Done in {str(dur).split('.')[0]}"
                else:
                    scraper_eta = "FAILED"

                # Items count (live)
                items = count_items_from_log(recent_lines)
                items_str = f"{items:,}" if items > 0 else "-"
                
                total_progress_sum += pct
                
                # Bottleneck ETA: best available per-scraper remaining time
                if d["status"] == "RUNNING":
                    tqdm_remaining = parse_tqdm_eta(recent_lines)
                    if tqdm_remaining is not None and tqdm_remaining > max_remaining_seconds:
                        max_remaining_seconds = tqdm_remaining
                    elif pct > 0.5:
                        bot_est = (elapsed.total_seconds() / pct) * 100 - elapsed.total_seconds()
                        if bot_est > max_remaining_seconds:
                            max_remaining_seconds = bot_est

                status_color = GREEN if d["status"] == "RUNNING" else (RED if d["status"] == "ERROR" else MAGENTA)
                log_limit = TABLE_WIDTH - 55
                display_log = clean_for_display(last_line)[:log_limit].ljust(log_limit)
                print(format_row(f"{status_color}{d['name']:12}{RESET} | {pct:5.1f}% | {CYAN}{items_str:>7}{RESET} | {display_log}", f"{scraper_eta}"))

            avg_pct = min(100.0, total_progress_sum / len(my_scrapers))
            eta_str = str(timedelta(seconds=int(max_remaining_seconds))) if max_remaining_seconds > 0 else "Calculating..."

            print(f"{WHITE}╠{'═' * (TABLE_WIDTH - 2)}╣{RESET}")
            print(format_row(f"{BOLD}OVERALL PROGRESS:{RESET} {GREEN}{avg_pct:5.1f}%{RESET}", f"Bottleneck ETA: \033[95m{eta_str}{RESET}"))
            print(f"{WHITE}╚{'═' * (TABLE_WIDTH - 2)}╝{RESET}")
            time.sleep(1)

    except KeyboardInterrupt:
        sys.stdout.write("\033[?25h")
        print(f"\n{RED}Stopping all processes...{RESET}")
        for d in processes: d["proc"].terminate()

    sys.stdout.write("\033[?25h")
    for f in log_file_objects: f.close()
    sys.stdout.write(f"\033[{len(my_scrapers) + 14}E")
    
    final_time = datetime.now() - start_time
    CARD_WIDTH = 80
    print(f"\n{GREEN}{BOLD}ALL ENGINES FINISHED!{RESET}")
    print(f"{WHITE}╔{'═' * (CARD_WIDTH - 2)}╗{RESET}")
    print(format_row(f"{BOLD}FINAL RECON REPORT{RESET}", f"{datetime.now().strftime('%Y-%m-%d %H:%M')}", width=CARD_WIDTH))
    print(f"{WHITE}╠{'═' * (CARD_WIDTH - 2)}╣{RESET}")
    print(format_row(f"Total Duration: {YELLOW}{str(final_time).split('.')[0]}{RESET}", "", width=CARD_WIDTH))
    print(f"{WHITE}╠{'═' * (CARD_WIDTH - 2)}╣{RESET}")
    print(format_row(f"{'Scraper':12} {'Status':8} {'Items':>8}  {'7d Avg':>8}  {'Var':>5}  {'Dur'}", "", width=CARD_WIDTH))
    print(f"{WHITE}╠{'═' * (CARD_WIDTH - 2)}╣{RESET}")
    total_items = 0
    for d in processes:
        all_lines = get_last_lines_fast(d["log"], num_bytes=16384)
        items = count_items_from_log(all_lines)
        total_items += items
        
        # Historical Comparison
        hist_avg = get_historical_stats(d["name"], codes_dir)
        var_str = "-"
        if hist_avg > 0:
            var = (items / hist_avg - 1) * 100
            var_color = GREEN if var > -5 else (YELLOW if var > -15 else RED)
            var_str = f"{var_color}{var:+4.1f}%{RESET}"
        
        hist_str = f"{int(hist_avg):,}" if hist_avg > 0 else "-"
        dur = str((d['finish_time'] - start_time) if d.get('finish_time') else final_time).split('.')[0]
        res_str = f"{GREEN}OK{RESET}" if d["status"] == "COMPLETE" else f"{RED}FAIL{RESET}"
        print(format_row(f"{d['name']:12} {res_str:>17} {CYAN}{items:>8,}{RESET}  {WHITE}{hist_str:>8}{RESET}  {var_str:>14}  {YELLOW}{dur:>5}{RESET}", "", width=CARD_WIDTH))
    print(f"{WHITE}╠{'═' * (CARD_WIDTH - 2)}╣{RESET}")
    print(format_row(f"{BOLD}TOTAL ITEMS COLLECTED: {CYAN}{total_items:,}{RESET}", "", width=CARD_WIDTH))
    print(f"{WHITE}╚{'═' * (CARD_WIDTH - 2)}╝{RESET}\n")

    # Run inflation calculations automatically after scraping
    if args.skip_inflation:
        print(f"{YELLOW}{BOLD}Skipping inflation calculations (--skip-inflation).{RESET}\n")
    else:
        print(f"{YELLOW}{BOLD}Running inflation calculations...{RESET}\n")
        calc_script = os.path.join(
            os.path.dirname(codes_dir),  # InflationItems/
            os.pardir, "Inflations", "Codes", "Full_Calculate", "batukoray", "calc_inflation.py"
        )
        calc_script = os.path.normpath(calc_script)
        subprocess.run([sys.executable, calc_script])

if __name__ == "__main__":
    main()
