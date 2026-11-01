-- severity: warn
-- why: a contract-year published both as an annual total and as itemized lines would be double counted in paid-to-date.
with a as (select distinct contract_number, payment_year from stg.payments where not is_itemized),
     i as (select distinct contract_number, payment_year from stg.payments where is_itemized and contract_number is not null)
select (select count(*) from a join i using (contract_number, payment_year)) as failing_rows,
       (select count(*) from a) as total_rows;
