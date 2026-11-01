# Data profile — City of Chicago contracts & payments

Snapshot (as-of) date: **2026-10-31**. Row counts and file hashes are in `data/manifests/download_manifest.json`.

## Sources

| Table | Portal ID | Rows | Grain |
| --- | --- | --- | --- |
| Contracts | `rsxa-ify5` | 186,011 raw → 186,004 staged | one row per contract revision per vendor record (89,133 contract numbers), approved 1993–2026 |
| Payments | `s4vu-giwb` | 477,811 | itemized payment lines, or one annual total per contract (see below); $119.6B total |
| Contract PDFs | `contract_pdf` column on Contracts | 68,971 links → 68,938 documents | one document per revision |

## Payments: what is itemized, and when

| Years | Contract payments | Direct vouchers (DV) |
| --- | --- | --- |
| 2002–2021 | annual totals per contract | not published |
| 2022–2024 | **annual totals per contract** (plus ~60 stray itemized rows a year) | itemized |
| 2025–2026 | itemized | itemized |

Consequences:

- **Day-level contract analysis (paid after end date, duplicate payments, trailing-12-month spend) covers 2025-01-01 → 2026-10-29 only.** Earlier contract spend is usable at year level.
- **Paid-to-date = annual totals through 2024 + itemized from 2025.** The two forms overlap on only 6 contract-years (check `payments_annual_itemized_overlap`), so they can be added.
- Annual rows are close to unique on contract × year × vendor × department (116,421 keys for 116,574 rows); treat them as additive.

## Direct vouchers are mostly not procurement

`contract_number = 'DV'` means paid without a contract. In 2022–2026 DVs are **$21.2B vs $10.8B** in contract payments (≈66% of dollars). But the largest DV payees are:

| Payee type | Examples (2022+ DV $) |
| --- | --- |
| Pension funds | Municipal Employee Pension Fund ($4.1B), Policemen's A & B Fund ($1.8B), Firemen's Annuity ($0.9B) |
| Other governments | Cook County Treasurer ($1.9B), State of Illinois Treasurer ($0.6B), CTA ($0.3B), Public Building Commission |
| Banks / bond trustees | Amalgamated Bank, Zions Bank, Bank of New York Trust, U.S. Bank (debt service, ~$4.8B combined) |
| Payroll pass-through | Nationwide Retirement (deferred comp), police/fire credit unions |
| Legal settlements | Loevy & Loevy ($0.37B) |

**The raw DV share is not a maverick-spend number.** Phase 2 classifies DV payees (pension, government, debt service, payroll, legal/judgments, refunds to individuals, internal), and the off-contract KPI uses only the remainder.

- **DVs carry no department (0% of rows).** The off-contract view leads with payee and payee type.
- Department on contract payments: 0% in 2022–2024, ~46% in 2025–2026; the rest is inherited from the contract.

## Contracts

- **Revision numbers are text.** 17,605 rows (9%) use codes like `T10456`, `D701291`. `revision_number` stays text; `revision_seq` is the integer for numeric revisions only.
- **7 revisions were published twice**, identical except that only one copy has a PDF. Staging keeps one copy per contract × revision × vendor ID, preferring the one with a PDF.
- **34 revisions appear under two vendor records** — renamed or re-registered vendors (e.g. `SKYTECH ENTERPRISES, LIMITED|CLEANED-UP` vs `SKYTECH ENTERPRISES, LIMITED`, two vendor IDs). Resolved in `dim_vendor`.
- **27,005 revisions have a negative award** (de-obligations) and **27,495 have $0** (typically time extensions/admin changes). Cumulative award = sum of all revisions; a $0 revision is not a $0 cap.
- 115 revisions end before they start.
- 1.1% of payment rows citing a contract number find no matching contract.

## Contract PDFs

| Link format | Documents | Years | On contracts with 2022+ payments |
| --- | --- | --- | --- |
| Current (`id={GUID}`) | 40,009 | 1996–2026 | 10,856 |
| Legacy (`sid=EDGE&id=…`) | 28,929 | 1993–2017 | 67 |
| **Total** | **68,938** | | **10,923 docs / 5,028 contracts** |

- The link opens a JavaScript viewer. The file is served at the URL in `src/config.py` (`PDF_URL`); legacy links first need the viewer page to reveal the GUID (`resolve_doc_id` in `src/ingest/download_pdfs.py`). Both paths tested.
- Current sample (`data/manifests/pdf_manifest.csv`): **24 PDFs, 15 text, 9 scanned (38%)**, median 28.5 pages, max 305. Plan for OCR on roughly a third of documents.
- Page 1 is a standard **Contract Summary Sheet** or **Modification Summary Report** (contractor, department, term, amount, revision).

## Staging rules (`sql/01_staging.sql`)

| Column | Rule |
| --- | --- |
| vendor_name | upper-cased, trimmed, internal whitespace collapsed |
| revision_number / revision_seq | text kept as published; integer only when all digits |
| award_amount, amount | cast to numeric only if it looks numeric, else null (a DQ check catches any raw value that failed) |
| check_date / payment_year | date parsed only when `mm/dd/yyyy`; year taken from either format |
| is_itemized | true when check_date is a full date |
| contract_number (payments) | `'DV'` → null, with `is_direct_voucher = true` |
| pdf_url / pdf_link_format / pdf_doc_id | original link kept; format `current` or `legacy`; GUID filled for current links |
| duplicates | one row per contract × revision × vendor ID, PDF copy preferred |

## Data-quality checks (`sql/tests/`)

Run with `python -m src.dq.run_checks`. `error` checks must pass; `warn` and `info` are explained above.

Latest run (snapshot 2026-10-31):

```
status  check                               failing      total     pct
PASS    contracts_award_unparsed                  0    186,004    0.0%
WARN    contracts_end_before_start              115    186,004    0.1%
PASS    contracts_pdf_link_format                 0     68,971    0.0%
WARN    contracts_revision_multi_vendor          34    186,004    0.0%
PASS    contracts_unique_revision                 0    186,004    0.0%
INFO    contracts_zero_award                 27,495    186,004   14.8%
PASS    payments_amount_unparsed                  0    477,811    0.0%
WARN    payments_annual_itemized_overlap          6    109,373    0.0%
PASS    payments_date_unparsed                    0    477,811    0.0%
INFO    payments_missing_department         289,742    477,811   60.6%
WARN    payments_orphan_contract              2,781    244,118    1.1%
```
