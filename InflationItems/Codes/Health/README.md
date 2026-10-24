# Health data collection

Run these commands from the repository root with Python 3.12 and `requests`,
`beautifulsoup4`, `pandas`, `lxml`, `openpyxl`, and `xlrd` installed:

```bash
python 'InflationItems/Codes/Health/Dentist&Doctor&Physical_Therapy/dentgroup_scraper.py'
python 'InflationItems/Codes/Health/Dentist&Doctor&Physical_Therapy/adu_hospital_scraper.py'
python 'InflationItems/Codes/Health/Dentist&Doctor&Physical_Therapy/ozelfizyoterapist_scraper.py'
python 'InflationItems/Codes/Health/Diagnostic&Surgical Services/ortopedi_istanbul_scraper.py'
python InflationItems/Codes/Health/Medicine_Glasses_Lenses/health_scraper.py
```

Code filenames use the provider name. CSV filenames use
`provider_YYYY-MM-DD.csv`; category directories remain for project navigation.
Output paths are resolved from the script location, including when run from the
repository root. The existing physical therapy CSVs were renamed to
`ozelfizyoterapist_YYYY-MM-DD.csv` without changing their contents.

The medicine/optical collector uses public tariff sources rather than retailer
brands. It writes separate `titck_YYYY-MM-DD.csv` and `sgk_YYYY-MM-DD.csv` files in
`InflationItems/Datas/Health/Medicine_Glasses_Lenses/`, preserving source and date
columns. The filename records the collection date. It no longer assigns current
prices to artificial historical months. Existing mixed `health_prices_YYYY-MM.csv`
files are legacy data and must not be treated as verified historical snapshots.
Their source separation cannot safely be reconstructed from their two columns.
TİTCK source dates still depend on the date inferred from the published link;
verify them against the original publication before historical analysis.
SGK reimbursement tariffs are not retail glasses or contact-lens selling prices.
There is no dedicated retailer contact-lens scraper in this checkout.

Books/stationery collection is provided by Nezih:

```bash
python InflationItems/Codes/BooksStationery/Nezih/nezih_scraper.py --page-limit 1 --output /tmp/nezih_smoke.csv
```

Omit `--page-limit` and `--output` for the full daily collection. Nezih already
uses `nezih_YYYY-MM-DD.csv` filenames. A failed or empty collection must not be
reported as successful data collection; inspect logs and validate nonempty CSVs.
Health's combined collector saves an available source even if the other fails,
but exits unsuccessfully when either source is missing.

Offline regression checks (requires pytest):

```bash
python -m pytest tests/check_books_health.py -q
```

These checks cover parsing into provider-named files from an unrelated working
directory, failed requests, source separation, retained dates, and empty Books
collections. They do not establish live website availability or current markup
compatibility. Live collection requires network access to each source hostname.
