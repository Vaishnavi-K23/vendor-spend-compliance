-- Payment-level exception flags (docs/kpi-dictionary.md).
--
-- Scope: purchasing payments only (payee types with is_procurement_like = true).
-- DV payments from 2022; contract payments from 2025, the first year they are itemized.
--
-- A payment can trip several flags; exception_type assigns it to exactly one, in
-- this order, so dollars are never double counted:
--     possible_duplicate > off_contract > paid_after_end_date > over_award

drop table if exists dw.mart_payment_exceptions cascade;
create table dw.mart_payment_exceptions as
with params as (
    select as_of_date from ref.run_params
),
p as (
    select f.*,
           c.start_date       as contract_start_date,
           c.current_end_date,
           c.cumulative_award,
           c.award_is_ceiling,
           c.has_complete_revision_history,
           -- Grants close out slowly: final reimbursements routinely arrive 3-6 months
           -- after the period ends (Phase 4), so they get a longer grace period.
           case when ct.procurement_channel = 'Delegate agency (grant)' then 180 else 90 end
                              as grace_days
    from dw.fact_payment f
    join ref.payee_types t using (payee_type)
    left join dw.dim_contract c using (contract_number)
    left join dw.dim_contract_type ct on ct.contract_type = c.contract_type
    where t.is_procurement_like
      and (f.is_direct_voucher or f.payment_date >= date '2025-01-01')
),
-- Paid after end date only counts when billing is sustained: payments in 2+ distinct
-- months past the grace period. A single late or closeout batch is normal (Phase 4).
sustained_after_end as (
    select contract_number
    from p
    where payment_date > current_end_date + grace_days
    group by contract_number
    having count(distinct date_trunc('month', payment_date)) >= 2
),
-- High-volume billers (30+ payments a month) issue many same-amount invoices
-- (rentals, fuel, telecom accounts), which swamp the duplicate rule.
payee_volume as (
    select payee_key,
           count(*)::numeric / count(distinct date_trunc('month', payment_date)) as payments_per_month
    from dw.fact_payment
    group by payee_key
),
-- Contract total, for the over-award materiality gate.
contract_total as (
    select contract_number, sum(amount) as total_paid
    from (select contract_number, amount from dw.fact_payment where contract_number is not null
          union all
          select contract_number, amount from dw.fact_payment_annual) x
    group by contract_number
),
-- Running paid-to-date per contract: annual totals (through 2024) are the opening
-- balance, then itemized payments accumulate in date order.
opening as (
    select contract_number, sum(amount) as paid_before_itemized
    from dw.fact_payment_annual
    group by contract_number
),
running as (
    select p.payment_id,
           coalesce(o.paid_before_itemized, 0)
             + sum(p.amount) over (partition by p.contract_number
                                   order by p.payment_date, p.payment_id) as paid_to_date_running
    from p
    join opening o using (contract_number)
    where p.contract_number is not null
    union all
    select p.payment_id,
           sum(p.amount) over (partition by p.contract_number
                               order by p.payment_date, p.payment_id)
    from p
    where p.contract_number is not null
      and not exists (select 1 from opening o where o.contract_number = p.contract_number)
),
-- Possible duplicate: the later of two positive payments to the same payee for the
-- same amount, on different vouchers, within 7 days. Excluded (Phase 4 review):
--   payee/amount pairs seen 4+ times (recurring rates, installments)
--   amounts under $1,000 (noise, immaterial)
--   grant reimbursement vouchers (CVIP): agencies bill equal program amounts
--   high-volume billers (30+ payments a month)
dup_candidates as (
    select payment_id, payee_key, amount, payment_date
    from (
        select p.payment_id, p.payee_key, p.amount, p.payment_date, p.voucher_number,
               lag(p.payment_date)   over w as prev_date,
               lag(p.voucher_number) over w as prev_voucher,
               count(*) over (partition by p.payee_key, p.amount) as times_amount_paid
        from p
        join payee_volume v using (payee_key)
        where p.amount >= 1000
          and p.voucher_number not like 'CVIP%'
          and v.payments_per_month < 30
        window w as (partition by p.payee_key, p.amount order by p.payment_date, p.payment_id)
    ) x
    where prev_date >= payment_date - 7
      and prev_voucher <> voucher_number
      and times_amount_paid < 4
),
-- ...unless a matching reversal (same payee, negative of the amount) follows within
-- 30 days, which is a void-and-reissue rather than a duplicate.
dups as (
    select d.payment_id
    from dup_candidates d
    where not exists (
        select 1 from dw.fact_payment r
        where r.payee_key = d.payee_key
          and r.amount = -d.amount
          and r.payment_date between d.payment_date - 7 and d.payment_date + 30
    )
),
flagged as (
    select
        p.payment_id,
        p.payment_date,
        p.payment_year,
        p.amount,
        p.voucher_number,
        p.contract_number,
        p.vendor_key,
        p.payee_key,
        p.payee_name,
        p.payee_type,
        p.department,
        p.is_direct_voucher,
        p.is_direct_voucher                                           as is_off_contract,
        -- DV paid to a vendor that held a contract in force on that date
        p.is_direct_voucher and exists (
            select 1 from dw.dim_contract c
            where c.vendor_key = p.vendor_key
              and p.payment_date between c.start_date and c.current_end_date
        )                                                             as off_contract_vendor_has_active_contract,
        d.payment_id is not null                                      as is_possible_duplicate,
        p.current_end_date,
        case when p.payment_date > p.current_end_date
             then p.payment_date - p.current_end_date end             as days_after_end,
        -- Past the grace period (90 days; 180 for grants) on a contract with sustained
        -- billing after the term
        coalesce(p.payment_date > p.current_end_date + p.grace_days, false)
            and s.contract_number is not null                         as is_paid_after_end,
        r.paid_to_date_running,
        p.cumulative_award,
        p.award_is_ceiling,
        p.has_complete_revision_history,
        -- Only the part of a payment that crosses the award line counts, and only on
        -- contracts that end up materially over: > 5% and > $1 past the award. The
        -- portal truncates award cents, and 1-4% overages are closeout adjustments.
        case when p.amount > 0 and p.cumulative_award > 0
                  and ct.total_paid > p.cumulative_award * 1.05
                  and ct.total_paid - p.cumulative_award > 1
             then greatest(0, least(p.amount, r.paid_to_date_running - p.cumulative_award))
             else 0 end                                               as amount_past_award
    from p
    left join running r using (payment_id)
    left join dups d using (payment_id)
    left join sustained_after_end s using (contract_number)
    left join contract_total ct using (contract_number)
)
-- Past-award dollars are only an exception when the award is a ceiling AND the
-- revision history is complete; with missing revisions the award is likely
-- understated, so those dollars are a data-quality measure instead.
select
    f.*,
    case when f.award_is_ceiling and f.has_complete_revision_history
         then f.amount_past_award else 0 end                              as over_award_amount,
    case when f.award_is_ceiling and not f.has_complete_revision_history
         then f.amount_past_award else 0 end                              as over_award_incomplete_history_amount,
    case when not f.award_is_ceiling then f.amount_past_award else 0 end  as over_estimate_amount,
    case when f.is_possible_duplicate then 'possible_duplicate'
         when f.is_off_contract       then 'off_contract'
         when f.is_paid_after_end     then 'paid_after_end_date'
         when f.award_is_ceiling and f.has_complete_revision_history and f.amount_past_award > 0
                                      then 'over_award'
    end                                                                   as exception_type,
    case when f.is_possible_duplicate or f.is_off_contract or f.is_paid_after_end then f.amount
         when f.award_is_ceiling and f.has_complete_revision_history then f.amount_past_award
         else 0 end                                                       as exception_amount
from flagged f;

create unique index on dw.mart_payment_exceptions (payment_id);
create index on dw.mart_payment_exceptions (contract_number);
create index on dw.mart_payment_exceptions (exception_type);
