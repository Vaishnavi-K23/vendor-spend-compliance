-- Payment facts.
--
-- fact_payment        = itemized payment lines (DVs 2022+, contract payments 2025+)
-- fact_payment_annual = annual totals per contract (contract payments through 2024)
-- They never cover the same contract-year except for 6 cases (DQ check
-- payments_annual_itemized_overlap), so paid-to-date = annual + itemized.

drop table if exists dw.fact_payment cascade;
create table dw.fact_payment as
select
    p.payment_id,
    p.check_date                                         as payment_date,
    p.payment_year,
    p.amount,
    p.voucher_number,
    p.is_direct_voucher,
    p.contract_number,
    c.contract_number is not null                        as has_contract_record,
    -- Contract payments take the contract's vendor; DVs and orphans match by name.
    coalesce(c.vendor_key, dw.norm_name(p.vendor_name), '(BLANK)') as vendor_key,
    coalesce(dw.norm_name(p.vendor_name), '(BLANK)')     as payee_key,
    p.vendor_name                                        as payee_name,
    case when p.is_direct_voucher then v.payee_type else 'contract' end as payee_type,
    coalesce(p.department_name, c.department, 'UNKNOWN') as department,
    case when p.department_name is not null then 'payment'
         when c.department is not null and c.department <> 'UNKNOWN' then 'contract'
         else 'unknown' end                              as department_source
from stg.payments p
left join dw.dim_contract c using (contract_number)
left join dw.dim_vendor v on v.vendor_key = coalesce(dw.norm_name(p.vendor_name), '(BLANK)')
where p.is_itemized;

create unique index on dw.fact_payment (payment_id);
create index on dw.fact_payment (contract_number);
create index on dw.fact_payment (vendor_key);
create index on dw.fact_payment (payment_date);

drop table if exists dw.fact_payment_annual cascade;
create table dw.fact_payment_annual as
select
    p.contract_number,
    p.payment_year,
    coalesce(c.vendor_key, dw.norm_name(max(p.vendor_name)), '(BLANK)') as vendor_key,
    coalesce(c.department, 'UNKNOWN')                    as department,
    c.contract_number is not null                        as has_contract_record,
    sum(p.amount)                                        as amount,
    count(*)                                             as source_rows
from stg.payments p
left join dw.dim_contract c using (contract_number)
where not p.is_itemized
group by p.contract_number, p.payment_year, c.vendor_key, c.department, c.contract_number;

create unique index on dw.fact_payment_annual (contract_number, payment_year);
