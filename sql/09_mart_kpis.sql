-- Vendor concentration and the headline KPI table (docs/kpi-dictionary.md).
-- Periods: 2025 (full year) and 2026 YTD (to the snapshot date), the years in which
-- both DV and contract payments are itemized.

-- Purchasing spend per vendor. Scope 'All purchasing' = contract payments + purchasing
-- DVs; department scopes use contract payments only, since DVs carry no department.
drop table if exists dw.mart_vendor_spend cascade;
create table dw.mart_vendor_spend as
with p as (
    select case f.payment_year when 2025 then '2025' when 2026 then '2026 YTD' end as period,
           f.vendor_key, f.department, f.is_direct_voucher, f.amount
    from dw.fact_payment f
    join ref.payee_types t using (payee_type)
    where t.is_procurement_like and f.payment_year in (2025, 2026)
),
scoped as (
    select period, 'All purchasing' as scope, vendor_key, sum(amount) as amount
    from p group by 1, 2, 3
    union all
    select period, department, vendor_key, sum(amount)
    from p where not is_direct_voucher and department <> 'UNKNOWN'
    group by 1, 2, 3
)
select
    s.period,
    s.scope,
    s.vendor_key,
    v.vendor_name,
    s.amount,
    s.amount / nullif(sum(s.amount) over (partition by s.period, s.scope), 0) as share,
    rank() over (partition by s.period, s.scope order by s.amount desc)       as vendor_rank
from scoped s
left join dw.dim_vendor v using (vendor_key)
where s.amount > 0;

-- Top-10 share and HHI (sum of squared % shares: 0-10,000; above 2,500 is
-- conventionally "highly concentrated").
drop table if exists dw.mart_concentration cascade;
create table dw.mart_concentration as
select
    period,
    scope,
    count(*)                                                 as vendors,
    sum(amount)                                              as amount,
    sum(share) filter (where vendor_rank <= 10)              as top10_share,
    round(sum(power(share * 100, 2)))                        as hhi
from dw.mart_vendor_spend
group by period, scope;

-- Headline KPIs, one row per KPI x period.
drop table if exists dw.kpi_summary cascade;
create table dw.kpi_summary as
with params as (select as_of_date from ref.run_params),
pay as (
    select case f.payment_year when 2025 then '2025' when 2026 then '2026 YTD' end as period,
           f.*, t.is_procurement_like
    from dw.fact_payment f join ref.payee_types t using (payee_type)
    where f.payment_year in (2025, 2026)
),
exc as (
    select case payment_year when 2025 then '2025' when 2026 then '2026 YTD' end as period, *
    from dw.mart_payment_exceptions
    where payment_year in (2025, 2026)
),
k as (
    select period, 'total_payments' as kpi, sum(amount) as value, 'usd' as unit from pay group by 1
    union all
    select period, 'dv_share_raw', sum(amount) filter (where is_direct_voucher) / sum(amount), 'ratio' from pay group by 1
    union all
    select period, 'purchasing_spend', sum(amount) filter (where is_procurement_like), 'usd' from pay group by 1
    union all
    select period, 'off_contract_spend', sum(amount) filter (where is_procurement_like and is_direct_voucher), 'usd' from pay group by 1
    union all
    select period, 'off_contract_share',
           sum(amount) filter (where is_procurement_like and is_direct_voucher)
             / sum(amount) filter (where is_procurement_like), 'ratio' from pay group by 1
    union all
    select period, 'off_contract_spend_vendor_had_active_contract',
           sum(amount) filter (where off_contract_vendor_has_active_contract), 'usd' from exc group by 1
    union all
    select period, 'possible_duplicate_payments', count(*) filter (where exception_type = 'possible_duplicate'), 'count' from exc group by 1
    union all
    select period, 'possible_duplicate_spend', sum(exception_amount) filter (where exception_type = 'possible_duplicate'), 'usd' from exc group by 1
    union all
    select period, 'paid_after_end_date_spend', sum(exception_amount) filter (where exception_type = 'paid_after_end_date'), 'usd' from exc group by 1
    union all
    select period, 'paid_after_end_date_contracts', count(distinct contract_number) filter (where exception_type = 'paid_after_end_date'), 'count' from exc group by 1
    union all
    select period, 'over_award_spend', sum(exception_amount) filter (where exception_type = 'over_award'), 'usd' from exc group by 1
    union all
    select period, 'over_award_contracts', count(distinct contract_number) filter (where exception_type = 'over_award'), 'count' from exc group by 1
    union all
    select period, 'over_award_incomplete_history_spend', sum(over_award_incomplete_history_amount), 'usd' from exc group by 1
    union all
    select period, 'over_estimate_spend', sum(over_estimate_amount), 'usd' from exc group by 1
    union all
    select period, 'total_exception_spend', sum(exception_amount) filter (where exception_type is not null), 'usd' from exc group by 1
    union all
    select period, 'top10_vendor_share', top10_share, 'ratio' from dw.mart_concentration where scope = 'All purchasing'
    union all
    select period, 'vendor_hhi', hhi, 'index' from dw.mart_concentration where scope = 'All purchasing'
    union all
    -- Snapshot KPIs (as of the snapshot date, not per year).
    -- Expiry risk is headlined for standard procurement only: grants and comptroller
    -- agreements mostly run on calendar-year cycles ending Dec 31 and are renewed as
    -- new agreements, so their expiries are routine and counted separately.
    select 'Snapshot', 'contracts_expiring_90d_with_spend', count(*), 'count'
    from dw.mart_contract_spend
    where is_expiring_with_spend and procurement_channel = 'Standard procurement'
    union all
    select 'Snapshot', 'trailing_12m_spend_expiring_90d', sum(paid_trailing_12m), 'usd'
    from dw.mart_contract_spend
    where is_expiring_with_spend and procurement_channel = 'Standard procurement'
    union all
    select 'Snapshot', 'annual_cycle_agreements_expiring_90d', count(*), 'count'
    from dw.mart_contract_spend
    where is_expiring_with_spend and procurement_channel <> 'Standard procurement'
    union all
    select 'Snapshot', 'contracts_paid_no_end_date', count(*), 'count'
    from dw.mart_contract_spend where current_end_date is null and paid_trailing_12m > 0
    union all
    select 'Snapshot', 'sole_source_share_standard_procurement',
           sum(paid_trailing_12m) filter (where is_sole_source) / sum(paid_trailing_12m), 'ratio'
    from dw.mart_contract_spend where procurement_channel = 'Standard procurement'
    union all
    select 'Snapshot', 'median_award_growth_standard_procurement',
           percentile_cont(0.5) within group (order by award_growth_ratio), 'ratio'
    from dw.mart_contract_spend where procurement_channel = 'Standard procurement' and paid_trailing_12m > 0
)
select k.kpi, k.period, k.value, k.unit, p.as_of_date
from k cross join params p
order by k.kpi, k.period;
