# Istanbul Avrupa Rent Scraper

A Python tool to scrape residential rental listings for **Istanbul's European side** from [sahibinden.com](https://www.sahibinden.com).

## Features

- 🗂️ Discovers **all price brackets** automatically using adaptive splitting
- 📄 **Pagination** handled seamlessly — fetches every page per bracket
- ♻️ **Resume support** — restart an interrupted run without re-scraping completed brackets
- ⏱️ Configurable **rate limiting** with per-request jitter to avoid detection
- 🛡️ Interactive **CAPTCHA handling** — alerts user and waits for manual solving
- 💾 Output as **CSV**, named with today's date

## Project Structure

```
Codes/HousesRent/IstanbulAvrupa/
├── scripts/
│   ├── main.py       # CLI entry point & run orchestration
│   ├── scraper.py    # Scraping logic (bracket splitting, page parsing, CSV output)
│   └── config.py     # All settings, paths, seed ranges
├── checkpoints/
│   └── checkpoint_<DATE>.json   # Resume state (auto-generated)
├── SeleniumProfile/  # Persistent browser profile (saves login state, cookies)
├── requirements.txt
└── README.md

Datas/HousesRent/IstanbulAvrupa/           ← output lives here
└── IstanbulAvrupa_<DATE>.csv
```

## Scraping Pipeline

```
main.py
  │
  ├─ 1. Load / initialise checkpoint
  │
  ├─ 2. Adaptive bracket discovery       ← scraper.scrape_and_resolve()
  │       Recursively splits large price ranges if listings > 1,000.
  │       Produces "safe" leaf brackets.
  │
  ├─ 3. Page scraping                    ← scraper.scrape_leaf_bracket()
  │       Paginates through safe brackets and normalizes records.
  │       Results saved to CSV incrementally.
  │
  └─ 4. Caching & Checkpointing
          Records completed brackets to allow quick resume.
          Caches resolved bounds for faster restart.
```

## Output Fields

| Field      | Type   | Description                   |
| ---------- | ------ | ----------------------------- |
| `District` | string | District / neighbourhood      |
| `Rooms`    | string | Room count (raw from listing) |
| `Price`    | string | Monthly rent (raw from site)  |

## Setup

```bash
# 1. Go to the project root
cd InflationResearchStudy

# 2. Create a virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate

# 3. Install dependencies
pip install -r Codes/HousesRent/IstanbulAvrupa/requirements.txt
```

> Chrome must be installed. The `undetected-chromedriver` version is pinned in `scraper.py` (`version_main=145`).

## Usage

Run all commands from inside the `scripts/` directory:

```bash
cd Codes/HousesRent/IstanbulAvrupa/scripts

# Full scrape (starts fresh, clears today's CSV if it exists)
python main.py

# Resume an interrupted run (skips already-completed brackets)
python main.py --resume

# Quick smoke-test — scrape only the first 3 brackets
python main.py --limit-brackets 3

# Increase per-page wait time (default: 2.5 s)
python main.py --delay 4.0

# Verbose debug output
python main.py -v
```

### CLI Reference

| Argument             | Default         | Description                                                    |
| -------------------- | --------------- | -------------------------------------------------------------- |
| `--delay SECONDS`    | `2.5`           | Per-page wait time in seconds. Actual waits are ±50% jittered. |
| `--limit-brackets N` | `0` (unlimited) | Stop after scraping N leaf brackets. Useful for testing.       |
| `--resume`           | —               | Skip brackets already completed in today’s checkpoint.         |
| `-v` / `--verbose`   | —               | Enable DEBUG-level logging.                                    |

## How It Works

### Adaptive Bracket Splitting

sahibinden.com caps results at **1,000 listings** per query (20 pages of 50).
To capture all data across high-density areas like Istanbul, the scraper uses adaptive bracket splitting:

1. It starts with wide **Seed Ranges** (e.g., 0 – 20,000 TL).
2. For each range, it loads page 1 and reads the total listing count.
3. If the count exceeds 1,000, it splits the range in half and recurses.
4. Once a range is safe (≤ 1,000 listings), it scrapes all pages immediately using the already-loaded page 1 — no URL is ever fetched twice.

### Resume Support

Progress is tracked in a checkpoint file:

```
Codes/HousesRent/IstanbulAvrupa/checkpoints/checkpoint_<DATE>.json
```

The checkpoint stores both the list of **completed brackets** and the full **resolved bracket list** from the current day. When `--resume` is used and the bracket list is present, the scraper skips all listing-count checks and jumps straight to scraping the remaining brackets.

### CAPTCHA Handling

If a CAPTCHA or login wall is detected:

1. The scraper pauses and alerts you in the terminal.
2. Solve the challenge manually in the Chrome window.
3. Press **ENTER** in the terminal once the listings are visible.

The scraper re-checks after each ENTER press and will prompt again if the page has not fully loaded yet.

## Configuration

Edit `scripts/config.py` to customise behaviour:

| Setting                  | Default       | Description                                                 |
| ------------------------ | ------------- | ----------------------------------------------------------- |
| `SEED_RANGES`            | 5 wide ranges | Starting price ranges for bracket splitting                 |
| `MAX_LISTINGS_PER_QUERY` | `1000`        | Listing count threshold that triggers a split               |
| `MIN_BRACKET_WIDTH`      | `50` TL       | Prevents infinite splits when many listings share one price |
| `PAGE_LOAD_DELAY`        | `2.5` s       | Base wait after each page loads (also `--delay`)            |
| `BETWEEN_BRACKET_DELAY`  | `1.0 – 2.0` s | Random delay between bracket splits                         |

## Developer Notes

The scraper logic is compartmentalized:

- **`config.py`** — single source of truth for all constants and file paths. No logic.
- **`scraper.py`** — core logic utilizing BeautifulSoup and undetected_chromedriver for HTML interaction, parsing, and caching.
- **`main.py`** — CLI orchestrator combining bracket retrieval, terminal logging, and state checkpointing.

---

> **Disclaimer**: This tool is for educational / research purposes. Always respect `robots.txt` and the site's Terms of Service. Do not overload the server.
