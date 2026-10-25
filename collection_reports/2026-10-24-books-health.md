# Books and Health collection — 2026-10-24

Collected from the cloud terminal using Python 3.12. No SSH server was needed.

| File | Records | Meaning |
| --- | ---: | --- |
| `InflationItems/Datas/BooksStationery/Nezih/nezih_2026-10-24.csv` | 12,159 | Live Nezih listings: 8,928 Kitap and 3,231 Kırtasiye products. TRY selling prices. |
| `InflationItems/Datas/Health/Medicine_Glasses_Lenses/sgk_2026-10-24.csv` | 7 | Unambiguously parsed numeric optical reimbursement amounts from Optik Gazete's institution table. TRY tariffs, not retail prices. Includes a source-labelled 2025 institution entry. |
| `InflationItems/Datas/Health/Medicine_Glasses_Lenses/titck_reference_2026-10-24.csv` | 2,469 | TİTCK reference-source prices in EUR, published 2026-02-18; collected today, not current retail medicine prices. |

Nezih was collected using:

```bash
/workspace/.venvs/inflation/bin/python InflationItems/Codes/BooksStationery/Nezih/nezih_scraper.py --workers 2
```

All 90 Kitap pages and 33 Kırtasiye pages completed. Checked nonempty names,
unique product IDs and strictly positive numeric prices. The 200-row smoke output
was kept outside the repository, separately from the full collection.

The combined Health scraper ran, but its medicine output failed provenance
validation: it fell through to old spreadsheets, assigned the collection date to
unknown publication dates, and did not preserve the price currency. That output
was excluded from this commit. The Health scraper still needs a follow-up fix
for publication dates, sheet header detection, source selection, and currency;
its successful exit alone does not validate medicine data.

Instead, downloaded the official spreadsheet linked by the TİTCK source page's
row labelled `REFERANS BAZLI İLAÇ FİYAT LİSTESİ 18/02/2026`. Read the actual header
at Excel row 5 (`pandas.read_excel(..., header=4)`): `ILAC ADI`, `FIRMA ADI`, and
`GERCEK KAYNAK FIYAT (GKF) (€)`. Selected nonempty drug names and positive numeric
prices, removed exact duplicate records, and retained the company name,
publication date, collection date, EUR currency, reference-price classification,
and original source URL in the CSV. Do not mix these reference prices with TRY
retail prices in an inflation index.

Optical amounts were checked against the source table. Only fields parsed
unambiguously by the existing collector are included, not every institution.
Currency, collection date, reimbursement classification, and source URL are
explicit. Future runs of the current scraper do not automatically add these
extra provenance columns; preserve this collection when refreshing data.

Other Health collections failed without producing new CSVs:

- Dentgroup's old fee-list URL redirected to its homepage; no fee table.
- Ortopedi İstanbul's old price URL redirected to its homepage; no fee table.
- ADÜ's configured patient-guide page had no expected price table.
- Özel Fizyoterapist redirected to a redesigned listing; expected price cards
  were absent across the configured 35-page fallback range.

No prices were inferred or fabricated for these sources. A dedicated retailer
contact-lens scraper is absent. The six offline regression checks passed; this
is separate from the live source failures above.
