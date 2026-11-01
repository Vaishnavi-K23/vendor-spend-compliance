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

### Phase 2: Dimensional model

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

Each KPI gets a formula in `docs/kpi-dictionary.md`:

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

### Phase 3b: Statistics notebook (Python)

One notebook (`notebooks/analysis.ipynb`, pandas + scipy/statsmodels):
- Does off-contract share differ significantly across departments/vendor groups? (chi-square test, with effect size, not just the p-value)
- Is contract growth (cumulative ÷ original award) different for sole-source vs competitively bid contracts? (Mann-Whitney U, since growth is skewed)
- Simple spend forecast for the top expiring contracts (trailing trend), to size the "what happens if this lapses" risk

Results are stated in plain language in the README, with caveats (observational data, not causal).

### Phase 4: Validate the exception rules (no planted answers, so check by hand)

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
- **Power BI Desktop:** confirm it's installed (Windows 11 Home is fine).
- **GitHub:** repo goes public after the Phase 1 commit.
