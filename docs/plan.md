# Vendor Spend & Contract Compliance Analytics: City of Chicago

## 1. Goal

A portfolio case study for U.S. Data Analyst roles. SQL, KPIs and Power BI carry the project. An LLM extraction layer with a proper evaluation is the extra for AI-named postings.

**Budget: $0.** Every tool in this plan is free (see section 6).

Business questions (for procurement leads and department finance managers):

1. How much is paid outside any contract (direct vouchers), and to which vendors?
2. Which contracts have been paid beyond their award amount, or well after their end date?
3. Which high-spend contracts expire in the next 30/60/90 days while payments are still going out?
4. How fast do contracts grow after award (modifications, extensions)?
5. How concentrated is spend in a few vendors, by department?

Scope: direct vouchers are itemized 2022–2026; **contract payments are itemized only from 2025** (2022–2024 are annual totals per contract). Day-level contract analysis covers 2025-01-01 onward; annual totals are used for year-level trends and cumulative paid-to-date.

**As-of date:** all KPIs and README findings are computed against a fixed snapshot date, stored in the download manifest. The weekly automation job (Phase 7) runs on fresh data, but the case-study numbers do not move.

## 2. Data (confirmed by profiling)

| Source | What it gives |
|---|---|
| Contracts (rsxa-ify5) | 186k contract revisions: vendor, department, type, procurement method, dates, award amount, PDF link |
| Payments (s4vu-giwb) | 478k payments ($119.6B). DVs itemized 2022+, contract payments itemized 2025+. 99% join to a contract. "DV" means no contract — and most DV dollars are pensions, debt service and transfers, not purchasing. |
| Contract PDFs | 68,938 linked documents (1993–2026). 10,923 belong to the 5,028 contracts with 2022+ payments. Page 1 is a standard summary form, followed by the legal contract. About a third are scans (9 of 24 sampled). |
| CUAD (optional) | About 500 commercial contracts already labeled by lawyers, as a second extraction test set |

PDF links come in two formats:
- **Current** (`id={GUID}`): 40,009 documents, downloaded directly.
- **Legacy** (`sid=EDGE&id=...`): 28,929 documents, mostly pre-2018. The viewer page must be opened first to resolve the real document ID. Only 67 matter for the 2022+ pool.

Not available: invoice lines, rate cards, goods receipts. So the project can't do price variance or a true 3-way match. The README says this upfront.

## 3. Phases

### Phase 1: Ingest, staging, data quality — done ✅

Full results in `docs/data-profile.md`.

Done:
- Download scripts for the two tables and a stratified PDF sample, with a manifest.
- Postgres in Docker. A `raw` schema stores everything as text; a `stg` schema holds typed, cleaned tables.
- 9 data-quality checks, all error-level checks passing. Findings:
  - Revision numbers are sometimes codes like T10456 (staging bug, fixed).
  - 7 revisions published twice; deduplicated, keeping the copy with the PDF.
  - 34 revisions appear under two vendor records, such as "SKYTECH…|CLEANED-UP".
  - 27k revisions are reductions (negative amounts); 27k are $0 revisions.
  - 1.1% of payments cite a contract number that doesn't exist in the contracts table.
  - 61% of payments have no department.

Finished in the last pass:
- PDF link staging: `pdf_url` and `pdf_link_format` (current / legacy) kept in `stg.contracts`; the downloader resolves legacy links through the viewer page (tested). New error check: every link is a known format.
- DV department coverage: **0%**. The off-contract view leads with payee and payee type.
- Annual totals grain: contract × year × vendor × department (additive). They run through **2024**, and contract payments are itemized only from 2025. Annual and itemized overlap on just 6 contract-years (new warn check), so paid-to-date can add them.
- PDF sample verified: 24 files, all in the manifest; 15 text, 9 scans.
- Snapshot recorded: `data/manifests/download_manifest.json`, as-of **2026-10-31**, with row counts and file hashes.
- Check results pasted into `docs/data-profile.md`; first git commit.

**Findings that change later phases:**
- **DV ≠ maverick spend.** 2022+ DVs are $21.2B vs $10.8B on contracts, but the top payees are pension funds, Cook County / State treasurers, bond trustees, payroll pass-throughs and legal settlements. Phase 2 adds payee classification; Phase 3's off-contract KPI uses only the procurement-type remainder. "Raw DV share vs. true off-contract share" becomes a README finding.
- **Day-level contract rules run on 2025-01-01 → as-of only** (paid after end date, duplicates, trailing-12-month spend).

### Phase 2: Dimensional model — done ✅

Built in schema `dw` (`sql/02_functions.sql` … `sql/06_conformed.sql`, run by `python -m src.model.build_model`). Full documentation in `docs/data-model.md`. All model checks pass; payments reconcile to staging to the cent.

What changed from the design below:
- Payee type lives on `dim_vendor` (from `data/reference/payee_type_overrides.csv` + keyword rules), with group definitions in `data/reference/payee_types.csv`. No separate dim table.
- Added `fact_payment_annual` (contract × year, through 2024) and `procurement_channel` on `dim_contract_type` (standard procurement / comptroller agreement / delegate agency grant). Sole-source and competition metrics run within standard procurement only, because procurement method is rarely recorded outside it.
- `award_is_ceiling` sits on `dim_contract` (it depends on procurement type and description, not only contract type).

**Findings:**
- **True off-contract purchasing share ≈ 5%** (5.3% in 2025, 5.6% in 2026 YTD), against a raw DV share of 46% (2025). DVs are 74% obligations (pension, debt service, payroll pass-through, settlements), 17% transfers to other governments, 6.7% purchasing.
- Award amounts on revisions are **changes**, not new totals; cumulative award = sum of revisions.
- 734 vendors are registered under more than one vendor ID (1,513 IDs total).
- 170 contracts paid in 2025+ ($1.0B, 9% of contract spend) have no end date in the data — extraction candidates for Phase 6.
- **To review:** the `low`-confidence rows in `payee_type_overrides.csv`, mostly law firms classified as plaintiff vs. City counsel by billing pattern.

Original design:

| Table | Grain | Notes |
|---|---|---|
| dim_vendor | one cleaned vendor | Merges name variants and re-registered vendor IDs. The merge rules are documented; this is a finding in itself. |
| dim_payee_type | payee type | Rule-based classification of DV payees: pension, government, debt service / trustee, payroll pass-through, legal / judgment, refund to individual, internal, **procurement**. Rules are keyword + manual overrides for the top payees by $, with % of DV dollars classified reported. |
| dim_department | department | Payments with no department get one through their contract; DVs stay "Unknown" |
| dim_contract_type / procurement method | type | Includes sole-source and emergency flags, and an **award_is_ceiling** flag (false for requirements / blanket / master agreements, where the award is an estimate) |
| dim_calendar | day | Fiscal year = calendar year for Chicago |
| dim_contract | contract | Original award, cumulative award (sum of all revisions including reductions), latest end date, revision count, extension count |
| fact_contract_revision | revision | Amount change, date change, type (modification / time extension) |
| fact_payment | payment line | Itemized 2022+; annual totals kept separately for paid-to-date |

### Phase 3: SQL marts and KPIs

#### Status: done ✅

Built as plain SQL (`sql/07_mart_payments.sql`, `08_mart_contracts.sql`, `09_mart_kpis.sql`), run by `python -m src.model.build_model`. dbt was deferred: it would add a second tool for one layer, and the SQL can move into dbt models later without changing any logic. Formulas, values and caveats are in `docs/kpi-dictionary.md`. Mart checks pass; contract-level spend reconciles to payments, apart from $95.9M paid against contract numbers missing from the contracts table, which is documented.

Headline values (2025):
- off-contract purchasing **5.3%** ($318M), of which $80M went to vendors that held a contract in force
- exceptions **$469M**: possible duplicates $25M, paid after end date $38M, over award $88M, off-contract $318M
- **83** standard-procurement contracts expire within 90 days with **$269M** of spend in the last 12 months
- sole source 2.3% of standard procurement; top-10 vendors 30% of purchasing

Changes from the design, found while checking the first results:
- **Raw DV share is 46% (2025), not ~66%.** The earlier figure compared against itemized contract payments only.
- **Possible duplicates** now exclude payee/amount pairs seen 4+ times (recurring rates, rentals, fixed fees) and void-and-reissue reversals. This cut flags from 4,962 to 1,007 in 2025. Same-voucher identical lines (6,754) are reported but not flagged.
- **Over award** counts only when the revision history is complete. Contracts with missing revision numbers ($171M in 2025) are reported as `over_award_incomplete_history`, a data-quality measure: their published award is likely understated.
- **Expiry risk** is headlined for standard procurement only. 974 grants and comptroller agreements expiring within 90 days are annual Dec 31 cycles.
- Department HHI is only meaningful at ≥ $50M spend.

For Phase 4 to check first: insurance brokers in off-contract spend (premium pass-throughs?), grants paid beyond award (missing funding amendments?), and the precision of the 1,007 duplicate flags.

Original design:

| KPI | Definition |
|---|---|
| Off-contract spend share | **Procurement-type** DV dollars ÷ (procurement-type DV + contract dollars), by payee. Raw DV share shown alongside to explain the gap. Department is unknown for all DVs. |
| Off-contract vendors who have contracts | Vendors paid by DV who also held an active contract on the payment date |
| Spend vs award | Cumulative paid ÷ cumulative award; flag above 100%. Reported separately for contracts where `award_is_ceiling` is false. |
| Over-award dollars | Only the dollars paid **past** the award line count as exceptions, not every payment on the contract |
| Paid after end date | Payments dated more than **90 days** after the contract's latest end date (grace period for invoice lag; tuned in Phase 4) |
| Expiry risk | Contracts ending within 30/60/90 days of the as-of date, ranked by trailing-12-month spend |
| Contract growth | Cumulative award ÷ original award; number of modifications and extensions |
| Concentration | Top-10 vendor share, plus HHI by department |
| Possible duplicate payments | Same vendor and amount within 7 days, different voucher. Vendors with a regular monthly pattern (rent, leases, fixed fees) are reviewed separately. |
| Sole-source / emergency share | Dollars by procurement method |

To avoid double-counting dollars: when one payment trips several flags, it's assigned to a single exception type by a fixed order: possible duplicate > off-contract > paid after end date > over award.

Build the marts as dbt Core models on the same Postgres (free), with dbt tests (`unique`, `not_null`, `relationships`) mirroring the Phase 1 checks. Optional: if time is short, plain SQL views are fine and dbt is added later.

SQL to be able to walk through live:
- running paid-to-date against award (window functions)
- year-over-year vendor spend
- matching each payment to the contract revision in force on its date
- duplicate detection with `lag()`
- expiry buckets
- the vendor deduplication logic

### Phase 3b: Statistics notebook (Python) — done ✅

`notebooks/analysis.ipynb`, executed with outputs and 3 charts. Results:
1. **Off-contract timing** (the department question was replaced, because DVs have no department). No December spike. January–February is higher by dollars (7.6% vs 5.0%) but *lower* by payment count (odds ratio 0.80). The rise is annual **insurance renewals**: 49% of off-contract insurance dollars fall in Jan–Feb, against 19% expected. Excluding insurance: 4.9% vs 4.3%. Contracts lapsing at Dec 31 explain little (OR 1.23).
2. **Contract growth by method.** RFP contracts grow more often than bid contracts (55% vs 35%; median 1.16× vs 1.00×; Mann-Whitney p ≈ 1e-6, rank-biserial r = 0.24). Sole source vs competitive: no difference (p = 0.38).
3. **Expiry exposure.** 83 standard-procurement contracts ending within 90 days run **$126M per 6 months**. The top 10 hold 68% of it, and 41 have rising spend.

Original design:

One notebook (`notebooks/analysis.ipynb`, pandas + scipy/statsmodels):
- Does off-contract share differ significantly across departments/vendor groups? (chi-square test, with effect size, not just the p-value)
- Is contract growth (cumulative ÷ original award) different for sole-source vs competitively bid contracts? (Mann-Whitney U, since growth is skewed)
- Simple spend forecast for the top expiring contracts (trailing trend), to size the "what happens if this lapses" risk

Results are stated in plain language in the README, with caveats (observational data, not causal).

### Phase 4: Validate the exception rules (no planted answers, so check by hand) — set up, review in progress

Built: `validation/review_workbook.xlsx` (7 sheets, 245 rows with evidence pre-filled), `python -m src.validation.score_review` (precision and miss rate with 95% Wilson intervals → `validation/results.md`), and the how-to in `validation/README.md`. Samples are deterministic.

**Your part:** fill in verdict / reason / notes. The verdicts must be your own judgment, because this is the interview story. Priority order: `off_contract_top_payees` (insurance brokers), `duplicates`, `over_award` (grants paid beyond award), `paid_after_end`. Then rescore, adjust rules where precision is low, and record the changes.

- For each rule, hand-review a random 30–50 flagged payments and record precision ("41 of 50 were real issues; the 9 false positives were…").
- Review a sample of unflagged payments too, to estimate what the rules miss.
- Expected false-positive sources to check first: invoice lag (end-date rule), estimate-style awards (over-award rule), recurring and split payments (duplicate rule).
- Write up what changed in the rules as a result. This is the "skepticism of numbers" story for interviews.

### Phase 5: Power BI (3 pages)

- **Executive:** off-contract spend in dollars and as a share; dollars over award or paid after end date; an expiry calendar; top exception vendors.
- **Analyst:** exception list with drill-through to individual payments and the contract's revision history, including the PDF link.
- **Vendor & concentration:** top-10 share, HHI, department and category mix.

The README carries screenshots and a 2-minute walkthrough video (OBS). The `.pbix` goes in `powerbi/` (keep it under GitHub's 100 MB file limit). "Publish to web" needs a paid or work account, so it's not used.

**Tableau Public (1 page, free):** rebuild only the Executive page in Tableau Public from an exported CSV of the marts. This gives recruiters a live clickable link and puts Tableau on the resume. One page only; not a second full dashboard.

### Phase 6: LLM extraction and evaluation (local model, $0)

Why it belongs in the analysis:
- Renewal options, extension rights and not-to-exceed language exist only in the PDFs. Extracting them makes the expiry-risk view better.
- When the PDF and the portal disagree on amount or dates, that disagreement is a finding of its own.

**Model:** Qwen 2.5 7B through Ollama, running locally on the processor (Ryzen AI 7 350, 24 GB RAM), with JSON-schema structured output. Fallback if too slow: Qwen 2.5 3B. Optional speed-up: LM Studio using the built-in Radeon graphics (same local API style, no code change). Documents never leave the machine.

Sample: about 200 PDFs from the 5,028 contracts that have both payments and PDFs, stratified by type and size. Decide and document which document per contract is sampled (original vs revision), and score summary fields against the **matching** portal revision.

Input reduction (needed for a small local model):
- Summary fields: page 1 only.
- Body fields: keyword search the text ("renewal", "extension", "option to extend", "not to exceed", "payment terms") and send only matching passages.

Scans: OCR first (ocrmypdf / Tesseract) and record the OCR's effect on accuracy separately.

Fields and scoring:
- **Contract-body fields** (renewal options, extension terms, not-to-exceed, payment terms): hand-labeled on 50–75 documents. These are the headline result.
- **Summary-form fields** (contractor, department, term dates, amount, revision): scored automatically against the portal across all 200. A sanity check, since page 1 is a standard form.

Stored per field: extracted value, model and prompt_version, confidence, source page and quoted text, QA flag.

Evaluation:
- accuracy, precision and recall per field
- errors broken down by text vs scan and by contract type
- a log of prompt versions showing which changes moved accuracy
- optional: 7B vs 3B comparison (accuracy vs runtime)

Gate: low-confidence or mismatched fields go to `manual_review_queue` and never reach the dashboard. Report how many were held back and why.

Optional: run the same prompts on CUAD to show the results hold beyond Chicago's documents.

Runtime: a few hours on the processor for 200 documents; run overnight.

### Phase 7: Automation and Excel

- Weekly exception report: a GitHub Actions job (free on a public repo) that downloads fresh data, rebuilds the marts and commits an HTML report covering off-contract dollars, contracts expiring within 60 days, and new exceptions. Raw data and PDFs are never committed.
- Excel reconciliation workbook: pivot of exceptions by department and type, plus a tab reconciling payment totals back to the portal. Built in Excel for the web (free) or LibreOffice Calc if desktop Excel isn't available.

### Phase 8: Case-study README

- business question, data caveats, method, as-of date
- links: Tableau Public page, video, glossary (`docs/glossary.md`)
- statistics results in plain language
- 3 findings with real dollars, worded as flags for review rather than accusations
- validation results for both the rules and the LLM
- screenshots and video
- "with ERP data I'd add invoice-line price variance and a 3-way match"

## 4. Timeline (about 5 weeks)

| Week | Work |
|---|---|
| 1 | Finish Phase 1, build Phase 2 |
| 2 | Phase 3 marts (dbt) and KPI dictionary; Phase 3b stats notebook; Phase 4 hand validation |
| 3 | Phase 5 Power BI + Tableau Public page. At this point it's a complete portfolio piece. |
| 4 | Phase 6 extraction, OCR, evaluation |
| 5 | Phase 7 automation and Excel; Phase 8 README and video |

If time slips, cut in this order: CUAD run, 7B-vs-3B comparison, dbt (use plain SQL views), Excel workbook. Never cut Phase 4.

## 5. Out of scope

- web app, login, chatbot
- vector database, LangChain, agents
- fraud claims
- a full second dashboard in Tableau (only the 1-page Tableau Public version)
- every one of the 69k PDFs (a well-evaluated sample is enough)
- paid APIs or services of any kind

## 6. Tools (all free)

| Need | Tool |
|---|---|
| Database | PostgreSQL in Docker Desktop (free for personal use) |
| Code | Python (pandas, scipy/statsmodels), SQL, dbt Core, Git |
| Dashboard | Power BI Desktop; Tableau Public (1 page) |
| OCR | ocrmypdf + Tesseract |
| LLM | Ollama + Qwen 2.5 7B (local); LM Studio optional |
| Automation | GitHub Actions (public repo) |
| Spreadsheet | Excel for the web or LibreOffice Calc |
| Video | OBS Studio |

## 7. Decisions

- **LLM provider:** local Qwen 2.5 7B via Ollama, $0. ✅
- **Power BI Desktop:** installed. ✅
- **GitHub:** public repo under Vaishnavi-K23, commits under your name only. ✅
