-- Contract-level marts (docs/kpi-dictionary.md).

-- One row per contract paid since 2022 (annual totals 2022-2024 or itemized).
-- Paid-to-date uses the full payment history back to 2002.
drop table if exists dw.mart_contract_spend cascade;
create table dw.mart_contract_spend as
with params as (
    select as_of_date from ref.run_params
),
annual as (
    select contract_number,
           sum(amount)                                    as paid_annual,
           sum(amount) filter (where payment_year >= 2022) as paid_annual_2022_plus
    from dw.fact_payment_annual
    group by contract_number
),
itemized as (
    select contract_number,
           sum(amount)                                    as paid_itemized,
           sum(amount) filter (where payment_date > (select as_of_date from params) - interval '12 months'
                                 and payment_date <= (select as_of_date from params))
                                                          as paid_trailing_12m,
           max(payment_date)                              as last_payment_date
    from dw.fact_payment
    where contract_number is not null
    group by contract_number
),
flags as (
    select contract_number,
           sum(amount) filter (where is_paid_after_end)   as paid_after_end_amount,
           count(*)    filter (where is_paid_after_end)   as paid_after_end_payments,
           sum(over_award_amount)                         as over_award_amount,
           sum(over_award_incomplete_history_amount)      as over_award_incomplete_amount,
           sum(over_estimate_amount)                      as over_estimate_amount,
           count(*)    filter (where is_possible_duplicate) as possible_duplicate_payments
    from dw.mart_payment_exceptions
    where contract_number is not null
    group by contract_number
),
base as (
    select
        c.contract_number,
        c.contract_type,
        t.category,
        t.procurement_channel,
        c.procurement_type,
        c.is_sole_source,
        c.is_emergency,
        c.vendor_key,
        v.vendor_name,
        c.department,
        c.description,
        c.award_is_ceiling,
        c.revision_gap_count,
        c.has_complete_revision_history,
        c.original_award,
        c.cumulative_award,
        c.award_growth_ratio,
        c.revision_count,
        c.amount_change_count,
        c.extension_count,
        c.start_date,
        c.current_end_date,
        c.pdf_count,
        coalesce(a.paid_annual, 0) + coalesce(i.paid_itemized, 0)           as paid_to_date,
        coalesce(a.paid_annual_2022_plus, 0) + coalesce(i.paid_itemized, 0) as paid_2022_plus,
        coalesce(i.paid_trailing_12m, 0)                                    as paid_trailing_12m,
        i.last_payment_date,
        coalesce(f.paid_after_end_amount, 0)                                as paid_after_end_amount,
        coalesce(f.paid_after_end_payments, 0)                              as paid_after_end_payments,
        coalesce(f.over_award_amount, 0)                                    as over_award_amount_2025_plus,
        coalesce(f.over_award_incomplete_amount, 0)                         as over_award_incomplete_amount_2025_plus,
        coalesce(f.over_estimate_amount, 0)                                 as over_estimate_amount_2025_plus,
        coalesce(f.possible_duplicate_payments, 0)                          as possible_duplicate_payments,
        c.current_end_date - (select as_of_date from params)                as days_to_expiry
    from dw.dim_contract c
    join dw.dim_contract_type t using (contract_type)
    left join dw.dim_vendor v using (vendor_key)
    left join annual a using (contract_number)
    left join itemized i using (contract_number)
    left join flags f using (contract_number)
    where coalesce(a.paid_annual_2022_plus, 0) <> 0 or i.paid_itemized is not null
)
select
    b.*,
    case when b.cumulative_award > 0 then b.paid_to_date / b.cumulative_award end as pct_of_award,
    greatest(b.paid_to_date - b.cumulative_award, 0)                             as paid_beyond_award,
    case when b.current_end_date is null then 'No end date'
         when b.days_to_expiry < 0    then 'Expired'
         when b.days_to_expiry <= 30  then '0-30 days'
         when b.days_to_expiry <= 60  then '31-60 days'
         when b.days_to_expiry <= 90  then '61-90 days'
         when b.days_to_expiry <= 180 then '91-180 days'
         else '180+ days' end                                                    as expiry_bucket,
    -- Ending within 90 days of the snapshot while money is still going out
    coalesce(b.days_to_expiry between 0 and 90 and b.paid_trailing_12m > 0, false) as is_expiring_with_spend
from base b;

create unique index on dw.mart_contract_spend (contract_number);

-- Procurement method mix, standard procurement only (method is rarely recorded elsewhere).
drop table if exists dw.mart_procurement_method cascade;
create table dw.mart_procurement_method as
select
    coalesce(procurement_type, '(NOT RECORDED)')          as procurement_type,
    count(*)                                              as contracts,
    sum(paid_trailing_12m)                                as paid_trailing_12m,
    sum(paid_2022_plus)                                   as paid_2022_plus,
    round(100 * sum(paid_trailing_12m) / sum(sum(paid_trailing_12m)) over (), 2) as pct_trailing_12m,
    percentile_cont(0.5) within group (order by award_growth_ratio)            as median_award_growth,
    avg(case when award_growth_ratio > 1.5 then 1.0 else 0 end)                as share_grown_over_50pct
from dw.mart_contract_spend
where procurement_channel = 'Standard procurement'
group by 1;
