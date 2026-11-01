# KPI dictionary

Snapshot (as-of) date: **2026-10-31**. Built by `python -m src.model.build_model` (`sql/07`–`09`). All values below are at that snapshot; every number in the README, dashboard and report must trace to a row in `dw.kpi_summary` or a mart listed here.

**Periods.** `2025` (full year) and `2026 YTD` (to 2026-10-29, the last payment date). These are the only years in which both direct-voucher (DV) and contract payments are itemized. `Snapshot` KPIs are measured on the as-of date.

**Purchasing.** A payment whose payee type has `is_procurement_like = true` (`data/reference/payee_types.csv`): every contract payment, plus DVs to `goods_services`, `outside_counsel` and `insurance_risk` payees. Pensions, debt service, payroll pass-throughs, settlements, transfers to governments and utilities are excluded.

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
| `purchasing_spend` | Σ purchasing payments | $6,036.3M | $5,388.2M |
| `dv_share_raw` | DV $ ÷ all $ | 46.4% | 42.3% |

## Off-contract spend

| KPI | Formula | 2025 | 2026 YTD |
| --- | --- | --- | --- |
| `off_contract_spend` | Σ purchasing DV $ | $318.4M | $303.4M |
| `off_contract_share` | purchasing DV $ ÷ purchasing $ | **5.3%** | **5.6%** |
| `off_contract_spend_vendor_had_active_contract` | purchasing DV $ where the payee's vendor held a contract in force on the payment date (`start_date ≤ payment_date ≤ current_end_date`) | $80.3M | $88.9M |

The raw DV share (46%) overstates off-contract purchasing ninefold; most DV dollars are pensions, debt service and transfers (`docs/data-model.md`). The "had an active contract" subset is the most actionable: the vendor was already under contract but was paid outside it. In 2025 it is led by insurance brokers (USI $31.1M, Alliant $8.3M), which may be premium pass-throughs rather than maverick spend; check in Phase 4.

## Exceptions (`dw.mart_payment_exceptions`)

Each payment gets **at most one** `exception_type`, in this order, so dollars are never double counted:

1. **`possible_duplicate`**: the later of two positive payments to the same payee for the same amount, on **different vouchers**, within **7 days**; and
   - the payee/amount pair occurs fewer than 4 times (4+ = a recurring rate or installment: rentals, fuel, fixed monthly fees), and
   - no reversal (same payee, negative of the amount) within 30 days (void-and-reissue).
   - Exception $ = payment amount.
2. **`off_contract`**: purchasing DV. Exception $ = payment amount.
3. **`paid_after_end_date`**: contract payment more than **90 days** after the contract's current end date (grace for invoice lag). Contracts with no end date are excluded. Exception $ = payment amount.
4. **`over_award`**: contract whose award is a ceiling (`award_is_ceiling`) **and** whose revision history is complete (`revision_gap_count = 0`). Exception $ = only the part of the payment that crosses the award line, using a running paid-to-date (annual totals through 2024 as the opening balance, then itemized payments in date order).

| KPI | 2025 | 2026 YTD |
| --- | --- | --- |
| `possible_duplicate_payments` / `_spend` | 1,007 / $24.8M | 800 / $13.1M |
| `paid_after_end_date_contracts` / `_spend` | 135 / $38.1M | 106 / $30.7M |
| `over_award_contracts` / `_spend` | 127 / $88.1M | 116 / $125.8M |
| `total_exception_spend` (all four types) | $468.8M | $472.6M |

**Reported separately, not exceptions:**

| KPI | Meaning | 2025 | 2026 YTD |
| --- | --- | --- | --- |
| `over_award_incomplete_history_spend` | past-award $ on ceiling contracts with **missing revision numbers** (e.g. revisions 1, 2, 6 absent), so the published award is likely understated | $171.1M | $113.4M |
| `over_estimate_spend` | past-award $ on contracts whose award is an estimate (master agreements, comptroller agreements, "requirements" contracts) | $42.0M | $22.9M |

Why the split: 35% of over-award contracts have revision gaps, against 16% of other paid contracts, and they carried $284M of the original over-award total.

**Other known limits:**
- Payments citing a contract number missing from the contracts table ($95.9M since 2022) can't be measured against an award or term.
- 6,754 lines repeat exactly within the same voucher (same payee, amount and date). It's unclear whether these are publishing duplicates or identical invoice lines, so they stay in totals and are not flagged.

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
| `trailing_12m_spend_expiring_90d` | **$268.7M** | spend on those 83 contracts in the last 12 months |
| `annual_cycle_agreements_expiring_90d` | 974 | grants and comptroller agreements, mostly ending Dec 31 and renewed as new agreements: routine |
| `contracts_paid_no_end_date` | 100 | paid in the last 12 months with no end date; excluded from expiry and paid-after-end rules |

## Procurement method (`dw.mart_procurement_method`, standard procurement)

Procurement method is recorded almost only for standard procurement, so these KPIs exclude grants and comptroller agreements.

| Method | Contracts | Paid, last 12 months | Share | Median award growth |
| --- | --- | --- | --- | --- |
| Bid | 936 | $1,765.8M | 46.2% | 1.00× |
| RFP | 199 | $820.6M | 21.5% | **1.41×** |
| RFQ | 122 | $746.3M | 19.5% | 1.00× |
| Master agreement | 288 | $129.6M | 3.4% | 1.00× |
| Sole source | 66 | $87.3M | **2.3%** | 1.00× |

`sole_source_share_standard_procurement` = 2.3%; `median_award_growth_standard_procurement` = 1.00× (most contracts never change value). RFP contracts grow a median 41% after award, a candidate for the Phase 3b statistics notebook.

## Concentration (`dw.mart_concentration`)

- **HHI** = Σ (vendor % share)², from 0 to 10,000; above 2,500 is conventionally "highly concentrated".
- **Top-10 share** = share of the 10 largest vendors.

| Scope | 2025 | 2026 YTD |
| --- | --- | --- |
| All purchasing: `top10_vendor_share` | 29.9% | 31.9% |
| All purchasing: `vendor_hhi` | 182 | 193 |

Department scopes use contract payments only, since DVs have no department. Department HHI is only meaningful for departments with real spend: filter to ≥ $50M. Among those, the most concentrated in 2025 were Business & Information Services (HHI 5,397), Finance (5,389, which includes employee benefits contracts), Assets Information & Services (3,709), Technology & Innovation (3,458) and Streets & Sanitation (2,541).
