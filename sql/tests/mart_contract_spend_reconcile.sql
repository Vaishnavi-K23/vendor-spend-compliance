-- severity: error
-- why: contract-level paid since 2022 must add up to all contract payments since 2022, minus payments citing a contract number missing from the contracts table ($95.9M at the 2026-10-31 snapshot), which can't be measured against an award. failing_rows = $ difference, rounded.
select abs(round((select sum(paid_2022_plus) from dw.mart_contract_spend)
           - (select coalesce(sum(amount), 0) from dw.fact_payment_annual where payment_year >= 2022 and has_contract_record)
           - (select sum(amount) from dw.fact_payment where contract_number is not null and has_contract_record)))::bigint as failing_rows,
       1 as total_rows;
