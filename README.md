# Vendor Spend & Contract Compliance Analytics — City of Chicago

> Work in progress. Findings below are placeholders until the marts are built.

## Business question

Chicago's published payments run to roughly $10B a year in 2022–2026 — but much of that is pensions, debt service and transfers to other governments, not purchasing. Procurement and finance need to know:

1. **How much purchasing happens outside a contract?** (direct vouchers, after separating out non-procurement payees)
2. **Which contracts are paid beyond their award amount or after their end date?**
3. **Which high-spend contracts expire in the next 30/60/90 days** while payments are still flowing?
4. **How concentrated is spend** in a small number of vendors, by department and category?

Audience: procurement leads and department finance managers deciding which contracts to review, rebid or extend.

## Data

Real public data from the [City of Chicago Data Portal](https://data.cityofchicago.org): Contracts (`rsxa-ify5`), Payments (`s4vu-giwb`), and contract PDFs linked from the contracts table. See [docs/data-profile.md](docs/data-profile.md) for coverage, caveats and data-quality rules.

Key caveats: itemized payments start in 2022; there are no invoice lines or rate cards, so compliance is measured payment-to-contract. A payment after a recorded end date is a **flag for review**, not proof of wrongdoing — extensions may exist that the dataset does not show.

## Approach

```
Portal CSVs ──► raw (text) ──► stg (typed) ──► marts (KPIs) ──► Power BI
Contract PDFs ──► LLM extraction ──► evaluation vs structured fields + hand labels ──► review queue
```

## Findings

_To be written from the marts._

## Repo

| Path | What |
| --- | --- |
| `src/ingest/` | download tables and a stratified PDF sample |
| `src/load/` | land raw CSVs in Postgres, build staging |
| `src/dq/` | run data-quality checks in `sql/tests/` |
| `sql/` | staging, marts, tests |
| `extract/` | LLM extraction and evaluation |
| `powerbi/` | report file and page specs |
| `reports/` | weekly exception pack |
| `excel/` | reconciliation workbook |
| `docs/` | data profile, KPI dictionary |

## Run it

```bash
docker compose up -d                      # Postgres 16 on localhost:5433
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env

python -m src.ingest.download_tables      # ~100 MB of CSVs into data/raw/
python -m src.ingest.download_pdfs --n 200
python -m src.load.load_raw               # raw.* and stg.*
python -m src.dq.run_checks
```

## With production data

With an ERP (SAP, Oracle, Coupa) I would join invoice lines and goods receipts to add price variance against rate cards and a true PO–receipt–invoice 3-way match.
