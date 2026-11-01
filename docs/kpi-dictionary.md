# KPI dictionary

Snapshot (as-of) date: **2026-10-31**. Built by `python -m src.model.build_model` (`sql/07`–`09`). All values below are at that snapshot, with the **rules as revised after the Phase 4 review** (see the last section). Every number in the README, dashboard and report must trace to a row in `dw.kpi_summary` or a mart listed here.

**Periods.** `2025` (full year) and `2026 YTD` (to 2026-10-29, the last payment date). These are the only years in which both direct-voucher (DV) and contract payments are itemized. `Snapshot` KPIs are measured on the as-of date.

**Purchasing.** A payment whose payee type has `is_procurement_like = true` (`data/reference/payee_types.csv`): every contract payment, plus DVs to `goods_services` and `outside_counsel` payees. Excluded: pensions, debt service, payroll pass-throughs, settlements, transfers to governments, utilities, refunds and rebates, and insurance premiums and claims funding.

## Marts

| Table | Grain | Use |
| --- | --- | --- |
| `dw.kpi_summary` | KPI × period | headline cards, README |
| `dw.mart_payment_exceptions` | purchasing payment (DV 2022+, contract 2025+) | exception flags, drill-through |
| `dw.mart_contract_spend` | contract paid since 2022 | spend vs award, expiry, growth |
| `dw.mart_procurement_method` | procurement method (standard procurement only) | sole-source share, growth by method |
| `dw.mart_vendor_spend` | period × scope × vendor | vendor rankings |
| `dw.mart_concentration` | period × scope | top-10 share, HHI |

## Spend

| KPI | Formula | 2025 | 2026 YTD |
| --- | --- | --- | --- |
| `total_payments` | Σ itemized payments, all payees | $10,662.9M | $8,809.5M |
| `purchasing_spend` | Σ purchasing payments | $5,965.0M | $5,316.2M |
| `dv_share_raw` | DV $ ÷ all $ | 46.4% | 42.3% |

## Off-contract spend

| KPI | Formula | 2025 | 2026 YTD |
| --- | --- | --- | --- |
| `off_contract_spend` | Σ purchasing DV $ | $247.0M | $231.4M |
| `off_contract_share` | purchasing DV $ ÷ purchasing $ | **4.1%** | **4.4%** |
| `off_contract_spend_vendor_had_active_contract` | purchasing DV $ where the payee's vendor held a contract in force on the payment date | $40.8M | $43.4M |

The raw DV share (46%) overstates off-contract purchasing more than tenfold. Most DV dollars are pensions, debt service, transfers and insurance premiums (`docs/data-model.md`). The "had an active contract" subset is the most actionable: the vendor was already under contract but was paid outside it (2025 leaders: USALCO, Pan-Oceanic Engineering, Ernst & Young, McDonagh Demolition, each about $2–3M).

**Caveat from Phase 4:** outside counsel are 26.7% of off-contract purchasing dollars since 2022 ($290M), and 13 of the 20 largest off-contract payees (69% of their dollars), led by Sotos, Taft and Borkan & Scahill. They have no contract in the published DPS data, but are most likely retained by the Law Department under engagement letters. Treat them as "not under a published contract", not as maverick spend, until confirmed.

## Exceptions (`dw.mart_payment_exceptions`)

Each payment gets **at most one** `exception_type`, in this order, so dollars are never double counted:

1. **`possible_duplicate`**: the later of two positive payments to the same payee for the same amount, on **different vouchers**, within **7 days**. Excluded:
   - payee/amount pairs that occur 4+ times (recurring rates and installments)
   - payments under **$1,000**
   - grant reimbursement vouchers (`CVIP…`), since agencies bill equal program amounts
   - high-volume billers (**30+ payments a month**)
   - pairs with a reversal (same payee, negative amount) within 30 days

   Exception $ = payment amount.
2. **`off_contract`**: purchasing DV. Exception $ = payment amount.
3. **`paid_after_end_date`**: a contract payment past the grace period (**90 days; 180 for delegate-agency grants**) on a contract with **sustained** billing after the term, meaning payments in 2+ distinct months past the grace period. Contracts with no end date are excluded. Exception $ = payment amount.
4. **`over_award`**: contract whose award is a ceiling, whose revision history is complete, and which ends up **materially** over: paid > award × 1.05 and more than $1 over. Exception $ = only the part of each payment that crosses the award line, using a running paid-to-date (annual totals through 2024 as the opening balance, then itemized payments in date order).

| KPI | 2025 | 2026 YTD |
| --- | --- | --- |
| `possible_duplicate_payments` / `_spend` | 160 / $19.5M | 135 / $8.3M |
| `paid_after_end_date_contracts` / `_spend` | 62 / $30.4M | 52 / $25.9M |
| `over_award_contracts` / `_spend` | 111 / $88.1M | 92 / $125.1M |
| `total_exception_spend` (all four types) | $384.9M | $390.5M |

**Reported separately, not exceptions:**

| KPI | Meaning | 2025 | 2026 YTD |
| --- | --- | --- | --- |
| `over_award_incomplete_history_spend` | past-award $ on ceiling contracts with **missing revision numbers**, so the published award is likely understated | $170.9M | $113.1M |
| `over_estimate_spend` | past-award $ on contracts whose award is an estimate (master agreements, comptroller agreements, "requirements" contracts) | $41.8M | $22.9M |

**Other known limits:**
- Payments citing a contract number missing from the contracts table ($95.9M since 2022) can't be measured against an award or term.
- 6,754 lines repeat exactly within the same voucher. They stay in totals and are not flagged.
- **Duplicates can't be confirmed from public data**, because there are no invoice numbers. The flag is a screening list for accounts payable, not a count of confirmed duplicates.

## Contracts (`dw.mart_contract_spend`)

| Field / KPI | Formula |
| --- | --- |
| `paid_to_date` | Σ annual totals (all years) + Σ itemized payments |
| `pct_of_award` | paid_to_date ÷ cumulative_award (cumulative award = Σ revision amount changes) |
| `award_growth_ratio` | cumulative_award ÷ original_award |
| `days_to_expiry`, `expiry_bucket` | current_end_date − as-of date |
| `paid_trailing_12m` | itemized payments in the 12 months to the as-of date |
| `is_expiring_with_spend` | 0 ≤ days_to_expiry ≤ 90 and paid_trailing_12m > 0 |

| KPI (Snapshot) | Value | Note |
| --- | --- | --- |
| `contracts_expiring_90d_with_spend` | **83** | standard procurement only |
| `trailing_12m_spend_expiring_90d` | **$268.7M** | spend on those 83 contracts in the last 12 months (6-month run-rate exposure ≈ $126M: `notebooks/analysis.ipynb`) |
| `annual_cycle_agreements_expiring_90d` | 974 | grants and comptroller agreements, mostly ending Dec 31 and renewed as new agreements: routine |
| `contracts_paid_no_end_date` | 100 | paid in the last 12 months with no end date; excluded from expiry and paid-after-end rules |

## Procurement method (`dw.mart_procurement_method`, standard procurement)

| Method | Contracts | Paid, last 12 months | Share | Median award growth |
| --- | --- | --- | --- | --- |
| Bid | 936 | $1,765.8M | 46.2% | 1.00× |
| RFP | 199 | $820.6M | 21.5% | **1.41×** |
| RFQ | 122 | $746.3M | 19.5% | 1.00× |
| Master agreement | 288 | $129.6M | 3.4% | 1.00× |
| Sole source | 66 | $87.3M | **2.3%** | 1.00× |

`sole_source_share_standard_procurement` = 2.3%; `median_award_growth_standard_procurement` = 1.00×. In the statistics notebook, RFP contracts grow more often than bid contracts (55% vs 35%, p ≈ 1e-6), and sole source shows no difference from competitive procurement.

## Concentration (`dw.mart_concentration`)

- **HHI** = Σ (vendor % share)², from 0 to 10,000; above 2,500 is conventionally "highly concentrated".
- **Top-10 share** = share of the 10 largest vendors.

| Scope | 2025 | 2026 YTD |
| --- | --- | --- |
| All purchasing: `top10_vendor_share` | 30.2% | 32.4% |
| All purchasing: `vendor_hhi` | 186 | 197 |

Department scopes use contract payments only, since DVs have no department. Department HHI is only meaningful at ≥ $50M spend.

## Rule changes from the Phase 4 review

First-pass review of 245 sampled rows (`validation/`). Precision is measured on the same reviewed rows before and after the change:

| Rule | Before | After | Change and evidence |
| --- | --- | --- | --- |
| Possible duplicate | 7% (2 of 29 decided) | 50% (1 of 2), 6 of 40 still flagged | False positives were condo rebates (`PV27`), payroll deductions (`PVPR`), grant installments (`CVIP`) and high-volume billers (Herc Rentals, AT&T, jet fuel). Added the $1,000 floor and the `CVIP` and volume exclusions; payee reclassification removed rebates and payroll deductions. |
| Paid after end date | 14% | 75% (3 of 4), 13 of 40 still flagged | Most flags were grant closeouts 91–190 days after term, single late invoices, and retainage paid years later. Readable PDFs confirmed the data's end dates in every case. Added the 180-day grant grace and the sustained-billing test. Lost one true issue (ABM, whose continued service was paid mostly by DV, so it's still caught by off-contract). |
| Over award | 77% | 100% (23 of 23) | False positives were 4 rounding cases (the portal truncates award cents: $76,704.4 vs PDF $76,704.41) and 3 grants 1–4% over. Added the 5% / $1 materiality gate. |
| Off-contract | 83% by count; top payees 86% by count but **52% by $** | 88%; top payees 100% | Insurance broker payments are premium pass-throughs: USI is 87% $1M+ payments, 76% in Dec–Feb, same amounts each year. `insurance_risk` is no longer purchasing (−$289M of DV since 2022). Also added refunds (`PVRF` majority) and condo rebates → `refund_rebate`, payroll vouchers (`PVPR` majority) → payroll pass-through, and people paid repeatedly → `individual_recurring` (unclassified). |
| Missed duplicates / missed after end | 0% miss rate (0 of 28; 0 of 30) | no change | The recurring-pair exclusion and the 90-day grace did not hide issues in the sample. |
