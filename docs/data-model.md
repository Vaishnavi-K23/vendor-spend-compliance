# Data model (schema `dw`)

Built by `python -m src.model.build_model` from `stg.*` and the reference files in `data/reference/`. Snapshot: 2026-10-31.

```
                    dim_calendar
                         │
dim_vendor ──── fact_payment ──── dim_department
    │                │
    │           dim_contract ──── dim_contract_type
    │                │
    └──── fact_contract_revision
                     
fact_payment_annual (contract × year, through 2024) ── dim_contract
```

## Tables

| Table | Grain | Rows | Notes |
| --- | --- | --- | --- |
| `dim_vendor` | one normalized vendor / payee name | 77,652 | 13,425 hold contracts. 734 of them merge 1,513 vendor IDs. Carries the payee type. |
| `dim_contract` | contract number | 89,133 | original award, cumulative award, growth ratio, current end date, revision and extension counts, procurement flags |
| `dim_contract_type` | contract type | 54 | category and **procurement channel** |
| `dim_department` | department | 70 | includes `UNKNOWN` |
| `dim_calendar` | day, 2002–2027 | 9,496 | Chicago fiscal year = calendar year |
| `fact_contract_revision` | contract × revision | 185,970 | amount change, running cumulative award, revision type |
| `fact_payment` | itemized payment line | 361,237 | DVs 2022+, contract payments 2025+ |
| `fact_payment_annual` | contract × year | 109,373 | contract payments through 2024 (annual totals only) |

## Key rules

**Vendor key.** `dw.norm_name()` upper-cases the name, drops punctuation, the `|CLEANED-UP` tag, trailing d/b/a names and legal suffixes (INC, LLC, CO…), and normalizes `&` spacing. A contract's vendor comes from its latest approved revision's vendor ID. A payment's vendor is the contract's vendor, or for DVs, the payee name. Vendor IDs whose names normalize to the same key are merged (734 merges, e.g. AECOM Technical Services: 4 IDs).

**Award amounts are changes.** Revision 0 is the original award; later revisions add or subtract; $0 revisions usually extend the term. `cumulative_award` = sum of all revisions. Revisions published under two vendor records (34) are collapsed so they count once.

**Revision type.** original → increase / decrease (amount ≠ 0) → time_extension (amount 0, end date moves later) → admin.

**Procurement channel.**

| Channel | Contract types | Contracts paid 2025+ | Paid 2025+ |
| --- | --- | --- | --- |
| Standard procurement | construction, consulting, commodities, A/E, IT… | 1,211 | $6.57B |
| Comptroller agreement | `COMPTROLLER-OTHER`: employee benefits, utilities, intergovernmental, airport consortia | 1,598 | $3.09B |
| Delegate agency (grant) | `DELEGATE AGENCY` | 2,279 | $1.13B |

Procurement method (bid, RFP, sole source…) is recorded almost only for standard procurement, so sole-source and competition metrics are computed within that channel.

**`award_is_ceiling` = false** for master agreements, comptroller agreements and "requirements" contracts, whose award is an estimate. Over-award flags are reported separately for these (13,342 contracts).

**Current end date** = end date on the most recently approved revision that states one. 170 contracts paid in 2025+ ($1.0B, 9% of contract spend) have no end date; they are excluded from the paid-after-end-date rule and are extraction candidates in Phase 6.

**Department.** Payment department if present, else the contract's, else `UNKNOWN` (`department_source` records which). DVs are always `UNKNOWN`.

## DV payee classification

Every payee gets a `payee_type` (definitions in `data/reference/payee_types.csv`):

1. **Analyst overrides** (`data/reference/payee_type_overrides.csv`): the top 200 DV payees by dollars (96% of DV $), each with a confidence level and basis. Law firms are split by billing pattern: City counsel bill hundreds of times (`outside_counsel`, purchasing); plaintiff firms receive a few large payments (`legal_settlement`). **Review the `low` confidence rows.**
2. **Keyword rules** for the long tail, in order: internal → pension → payroll pass-through (credit unions, unions) → legal settlement → government → law firm (side unknown) → bank → utility → registered City vendor → business suffix → person-like name with ≤5 payments (`individual`) → any other payee paid more than 5 times (`goods_services`) → `unclassified`.

Result for DVs 2022–2026 ($21.2B):

| Payee group | $ | Share |
| --- | --- | --- |
| Obligations (pension, debt service, payroll pass-through, settlements) | $15.6B | 73.9% |
| Transfers (other governments, internal) | $3.6B | 17.1% |
| **Purchasing** (goods & services, outside counsel, insurance) | **$1.4B** | **6.7%** |
| Other (individual refunds/claims, real estate, concessions, civic) | $0.3B | 1.2% |
| Unclassified | $0.1B | 0.6% |
| Utilities | $0.1B | 0.5% |

**Off-contract purchasing share** (purchasing-type DV $ ÷ all purchasing $):

| Year | Purchasing DVs | Contract payments | Off-contract share |
| --- | --- | --- | --- |
| 2025 | $318M | $5,718M | 5.3% |
| 2026 (to Oct 29) | $303M | $5,085M | 5.6% |

The raw DV share of 2022+ payments is ~66%; the true off-contract purchasing share is ~5%.

Known error sources, measured in Phase 4: small businesses without a legal suffix and paid ≤5 times land in `individual`; law partnerships named "X & Y" without an override land in `unclassified`.

## Checks

`python -m src.dq.run_checks` includes model checks (`dw_*`): payment rows and dollars reconcile to staging to the cent, every payment and contract resolves to a vendor, every payment has a payee type, cumulative award equals the sum of revisions, and every override matches a payee.
