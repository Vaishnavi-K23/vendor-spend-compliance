-- Contracts: revision history and one row per contract.
--
-- A revision's award_amount is the CHANGE to the contract value (revision 0 is the
-- original award; later revisions add or subtract; $0 revisions usually extend the
-- term). Cumulative award is therefore a running sum of revisions.

-- One row per contract x revision. The 34 revisions published under two vendor
-- records are collapsed here, keeping the most recently approved record, so award
-- amounts are not counted twice.
drop table if exists dw.fact_contract_revision cascade;
create table dw.fact_contract_revision as
with r as (
    select distinct on (contract_number, revision_number) *
    from stg.contracts
    order by contract_number, revision_number, approval_date desc nulls last, raw_row_id desc
),
ordered as (
    select r.*,
           row_number() over w            as revision_order,
           lag(end_date) over w           as prev_end_date
    from r
    window w as (partition by contract_number
                 order by revision_seq nulls last, approval_date, revision_number)
)
select
    o.contract_number,
    o.revision_number,
    o.revision_seq,
    o.revision_order,
    o.approval_date,
    o.start_date,
    o.end_date,
    o.prev_end_date,
    o.award_amount                                         as amount_change,
    sum(coalesce(o.award_amount, 0)) over (partition by o.contract_number order by o.revision_order)
                                                           as cumulative_award,
    case when o.revision_number = '0'   then 'original'
         when o.award_amount > 0        then 'increase'
         when o.award_amount < 0        then 'decrease'
         when o.end_date > o.prev_end_date then 'time_extension'
         else 'admin' end                                  as revision_type,
    coalesce(o.end_date > o.prev_end_date, false)          as extends_term,
    o.contract_type,
    o.procurement_type,
    o.department,
    o.vendor_id,
    m.vendor_key,
    o.pdf_url,
    o.pdf_link_format,
    o.pdf_doc_id
from ordered o
left join dw.vendor_id_map m using (vendor_id);

create unique index on dw.fact_contract_revision (contract_number, revision_number);

-- Contract types: revision rows typed 'Modification' / 'Time Extension' describe the
-- change, not the contract, so they are excluded when picking a contract's base type.
drop table if exists dw.dim_contract_type cascade;
create table dw.dim_contract_type as
select
    contract_type,
    case
        when contract_type ~ 'CONSTRUCTION|JOC|DEMOLITION|ROOFING'   then 'Construction'
        when contract_type ~ 'ARCH/ENGINEERING'                      then 'Architecture & engineering'
        when contract_type ~ 'PRO SERV'                              then 'Professional services'
        when contract_type ~ 'WORK SERV'                             then 'Work services & maintenance'
        when contract_type ~ 'COMMODITIES'                           then 'Commodities'
        when contract_type ~ 'SOFTWARE|TELECOM'                      then 'IT & telecom'
        when contract_type ~ 'VEHICLES|EQUIPMENT'                    then 'Vehicles & equipment'
        when contract_type ~ 'DELEGATE AGENCY'                       then 'Grants (delegate agency)'
        when contract_type = 'COMPTROLLER-OTHER'                     then 'Comptroller agreements'
        when contract_type = 'PROPERTY LEASE'                        then 'Property lease'
        else 'Other'
    end as category,
    -- Only standard procurement goes through DPS bidding, so sole-source and
    -- competition metrics are computed within this channel only.
    case
        when contract_type ~ 'DELEGATE AGENCY'                       then 'Delegate agency (grant)'
        when contract_type = 'COMPTROLLER-OTHER'                     then 'Comptroller agreement'
        when contract_type = 'PROPERTY LEASE'                        then 'Property lease'
        else 'Standard procurement'
    end as procurement_channel
from (select distinct contract_type from stg.contracts
      where contract_type is not null
        and contract_type not in ('Modification', 'Time Extension')
      union select '(UNKNOWN)') t;

create unique index on dw.dim_contract_type (contract_type);

drop table if exists dw.dim_contract cascade;
create table dw.dim_contract as
with base as (       -- base type and description from the earliest typed revision
    select distinct on (contract_number)
           contract_number, contract_type, specification_number, description
    from stg.contracts
    where contract_type is not null and contract_type not in ('Modification', 'Time Extension')
    order by contract_number, revision_seq nulls last, approval_date
),
latest as (          -- current vendor and department from the latest approved revision
    select distinct on (contract_number)
           contract_number, vendor_key, department
    from dw.fact_contract_revision
    order by contract_number, approval_date desc nulls last, revision_order desc
),
current_term as (    -- end date as set by the most recent revision that states one
    select distinct on (contract_number) contract_number, end_date
    from dw.fact_contract_revision
    where end_date is not null
    order by contract_number, approval_date desc nulls last, revision_order desc
),
agg as (
    select
        contract_number,
        sum(amount_change) filter (where revision_type = 'original')   as original_award,
        sum(coalesce(amount_change, 0))                                as cumulative_award,
        count(*)                                                       as revision_count,
        count(*) filter (where revision_type in ('increase', 'decrease')) as amount_change_count,
        count(*) filter (where extends_term)                           as extension_count,
        bool_or(revision_type = 'original')                            as has_original,
        min(start_date)                                                as start_date,
        min(approval_date)                                             as first_approval_date,
        max(approval_date)                                             as last_approval_date,
        (array_agg(procurement_type order by revision_order)
            filter (where procurement_type is not null))[1]            as procurement_type,
        bool_or(procurement_type = 'SOLE SOURCE')                      as is_sole_source,
        bool_or(procurement_type = 'EMERGENCY')                        as is_emergency,
        count(distinct pdf_url)                                        as pdf_count
    from dw.fact_contract_revision
    group by contract_number
)
select
    a.contract_number,
    coalesce(b.contract_type, '(UNKNOWN)')                as contract_type,
    b.specification_number,
    b.description,
    l.vendor_key,
    coalesce(l.department, 'UNKNOWN')                    as department,
    a.procurement_type,
    a.is_sole_source,
    a.is_emergency,
    -- Award amounts on master/requirements agreements and comptroller agreements are
    -- estimates, not ceilings; over-award flags are reported separately for them.
    not coalesce(a.procurement_type = 'MASTER AGREEMENT'
                 or b.contract_type = 'COMPTROLLER-OTHER'
                 or b.description ~* 'REQUIREMENT', false) as award_is_ceiling,
    a.has_original,
    a.original_award,
    a.cumulative_award,
    case when a.original_award > 0 then a.cumulative_award / a.original_award end
                                                         as award_growth_ratio,
    a.revision_count,
    a.amount_change_count,
    a.extension_count,
    a.start_date,
    t.end_date                                           as current_end_date,
    a.first_approval_date,
    a.last_approval_date,
    a.pdf_count
from agg a
left join base b         using (contract_number)
left join latest l       using (contract_number)
left join current_term t using (contract_number);

create unique index on dw.dim_contract (contract_number);
