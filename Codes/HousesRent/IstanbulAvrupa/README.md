# Istanbul Avrupa Rent Scraper

A Python tool to scrape residential rental listings for **Istanbul's European side** from [sahibinden.com](https://www.sahibinden.com).

## Project Structure

```
Codes/HousesRent/IstanbulAvrupa/
├── scripts/
│   ├── main.py       # CLI entry point & orchestrator
│   ├── scraper.py    # Core scraping logic (driver, parsing, CSV saving)
│   └── config.py     # All settings, paths, price brackets
├── checkpoints/
│   └── checkpoint_<DATE>.json   # Resume state (auto-generated)
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

# Quick smoke-test — only scrape the first price bracket
python main.py --limit-brackets 1

# Verbose debug output
python main.py -v
```

## How It Works

### Price Brackets

sahibinden.com caps results at ~1 000 listings per query. Istanbul Avrupa has
far more than that, so the scraper splits the search into **price range brackets**
(configured in `config.py`):

| Bracket (TL)       |
| ------------------ |
| 0 – 14 999         |
| 15 000 – 19 999    |
| 20 000 – 24 999    |
| 25 000 – 29 999    |
| 30 000 – 34 999    |
| 35 000 – 39 999    |
| 40 000 – 49 999    |
| 50 000 – 74 999    |
| 75 000 – 9 999 999 |

Each bracket is paginated fully before moving to the next.

### Resume Support

After each bracket the scraper writes a checkpoint file:

```
Codes/HousesRent/IstanbulAvrupa/checkpoints/checkpoint_<DATE>.json
```

Pass `--resume` to pick up from where a previous interrupted run left off. A
new run (without `--resume`) always starts fresh.

### CAPTCHA Handling

If sahibinden blocks a request, the scraper:

1. Detects the missing listings and prints a warning.
2. Pauses and prompts you to solve the CAPTCHA in the Chrome window.
3. Resumes automatically once you press **ENTER** in the terminal.

## Configuration

Edit `scripts/config.py` to change:

| Setting                   | Default       | Description                     |
| ------------------------- | ------------- | ------------------------------- |
| `PRICE_BRACKETS`          | 9 ranges      | Price ranges to query           |
| `PAGE_LOAD_DELAY`         | `2.5` s       | Wait after each page loads      |
| `PAGE_TURN_DELAY_MIN/MAX` | `2.0 – 4.0` s | Random delay between page turns |
| `BETWEEN_BRACKET_DELAY`   | `2.0 – 4.0` s | Random delay between brackets   |
| `PAGE_SIZE`               | `50`          | Listings per page               |

> **Note**: This tool is for academic / research purposes only. Always respect `robots.txt` and the site's Terms of Service.
