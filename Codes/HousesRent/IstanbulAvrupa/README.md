# Istanbul Avrupa Rent Scraper

A Python tool to scrape residential rental listings for **Istanbul's European side** from [sahibinden.com](https://www.sahibinden.com).

## Project Structure

```
Codes/HousesRent/IstanbulAvrupa/
├── scripts/
│   ├── main.py       # CLI entry point & orchestrator
│   ├── scraper.py    # Core scraping logic (adaptive splitting, parsing, CSV saving)
│   └── config.py     # All settings, paths, seed ranges
├── checkpoints/
│   └── checkpoint_<DATE>.json   # Resume state (auto-generated)
├── SeleniumProfile/  # Persistent browser profile (saves login state, cookies)
├── requirements.txt
└── README.md

Datas/HousesRent/IstanbulAvrupa/           ← output lives here
└── IstanbulAvrupa_<DATE>.csv
```

## Output Format

| Column     | Example             | Description                   |
| ---------- | ------------------- | ----------------------------- |
| `District` | `Bakırköy / Ataköy` | District / neighbourhood      |
| `Rooms`    | `2+1`               | Room count (raw from listing) |
| `Price`    | `35.000 TL`         | Monthly rent (raw from site)  |

## Setup

```bash
# From the project root
pip install -r Codes/HousesRent/IstanbulAvrupa/requirements.txt
```

> Chrome must be installed. The undetected-chromedriver version is auto-detected from your Chrome installation.

## Usage

Run all commands from inside the `scripts/` directory:

```bash
cd Codes/HousesRent/IstanbulAvrupa/scripts
```

```bash
# Full scrape (starts fresh, deletes today's CSV if it exists)
python main.py

# Resume an interrupted run (skips already-completed brackets)
python main.py --resume

# Quick smoke-test — only scrape the first seed range
python main.py --limit-brackets 1

# Verbose debug output
python main.py -v
```

## How It Works

### Smart Adaptive Brackets

sahibinden.com caps results at **1,000 listings** per query (20 pages of 50). To capture all data in high-density areas like Istanbul, the scraper uses an **Adaptive Splitting** strategy:

1. It starts with wide **Seed Ranges** (e.g., 0 – 20,000 TL).
2. For each range, it "peeks" at the total results count on the first page.
3. If the count exceeds 1,000:
   - It immediately splits the range in half (e.g., [0-10k] and [10k-20k]).
   - It recursively applies this logic until every bracket is "safe" (<= 1,000 listings).
4. This ensures 100% data coverage while minimizing redundant requests.

### Resume Support

The scraper tracks progress using checkpoint files:

```
Codes/HousesRent/IstanbulAvrupa/checkpoints/checkpoint_<DATE>.json
```

Use the `--resume` flag to continue from where you left off.

### CAPTCHA Handling

If a CAPTCHA or Login wall is detected:

1. The scraper pauses and alerts you in the terminal.
2. Solve the challenge manually in the open Chrome window.
3. Press **ENTER** in the terminal to resume scraping.

## Configuration

Edit `scripts/config.py` to customize the behavior:

| Setting                  | Default       | Description                                  |
| ------------------------ | ------------- | -------------------------------------------- |
| `SEED_RANGES`            | 5 wide ranges | Starting points for adaptive splitting       |
| `MAX_LISTINGS_PER_QUERY` | `1000`        | Threshold to trigger a range split           |
| `MIN_BRACKET_WIDTH`      | `50` TL       | Prevents infinite splits on identical prices |
| `PAGE_LOAD_DELAY`        | `2.5` s       | Wait after each page loads                   |
| `PAGE_TURN_DELAY`        | `2.0 – 4.0` s | Random delay between page turns              |
| `BETWEEN_BRACKET_DELAY`  | `1.0 – 2.0` s | Random delay between completed brackets      |

> **Note**: This tool is for academic / research purposes only. Always respect `robots.txt` and the site's Terms of Service.
