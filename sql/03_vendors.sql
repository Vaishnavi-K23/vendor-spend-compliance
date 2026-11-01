-- Vendors and payees.
--
-- Contracts carry a vendor_id; payments carry only a payee name. Both resolve to
-- vendor_key = dw.norm_name(name), so spelling variants collapse and a DV payee
-- can be matched to a vendor that also holds contracts.

-- One row per vendor_id, named by its most recently approved revision.
drop table if exists dw.vendor_id_map cascade;
create table dw.vendor_id_map as
select distinct on (vendor_id)
    vendor_id,
    vendor_name,
    dw.norm_name(vendor_name) as vendor_key
from stg.contracts
order by vendor_id, approval_date desc nulls last, raw_row_id desc;

create unique index on dw.vendor_id_map (vendor_id);

-- Every payee name seen in payments, with a raw spelling kept for the suffix rule.
drop table if exists dw.payee_names cascade;
create table dw.payee_names as
select
    coalesce(dw.norm_name(vendor_name), '(BLANK)') as vendor_key,
    max(vendor_name)                                as sample_name,
    count(*)                                        as n_payments,
    sum(amount)                                     as total_amount,
    -- Voucher prefixes mark the payment stream (Phase 4 review): PVPR = payroll
    -- remittances, PVRF = refunds.
    avg((voucher_number like 'PVPR%')::int)         as share_payroll_vouchers,
    avg((voucher_number like 'PVRF%')::int)         as share_refund_vouchers
from stg.payments
group by 1;

-- DV payee classification: analyst overrides first (data/reference/payee_type_overrides.csv),
-- then keyword rules in a fixed order. classification_source records which one fired.
drop table if exists dw.dim_vendor cascade;
create table dw.dim_vendor as
with contract_vendors as (
    select vendor_key,
           min(vendor_name)                 as vendor_name,
           count(*)                         as n_vendor_ids,
           string_agg(vendor_id, ', ' order by vendor_id) as vendor_ids
    from dw.vendor_id_map
    group by vendor_key
),
keys as (
    select vendor_key from contract_vendors
    union
    select vendor_key from dw.payee_names
),
classified as (
    select
        k.vendor_key,
        coalesce(cv.vendor_name, p.sample_name, k.vendor_key) as vendor_name,
        cv.vendor_key is not null                  as has_contract_record,
        coalesce(cv.n_vendor_ids, 0)               as n_vendor_ids,
        cv.vendor_ids,
        coalesce(p.n_payments, 0)                  as n_payments,
        coalesce(p.total_amount, 0)                as total_paid,
        o.payee_type                               as override_type,
        o.confidence                               as override_confidence,
        case
            when k.vendor_key ~ '^(CITY OF CHICAGO|DEPARTMENT OF|DEPT OF|CITY TREASURER|OFFICE OF)'
                then 'internal'
            when k.vendor_key ~ '\y(PENSION|ANNUITY|RETIREMENT)\y'
                then 'pension'
            when k.vendor_key ~ '\y(CREDIT UNION|FCU|LOCAL [0-9]+|AFSCME|TEAMSTERS|FRATERNAL ORDER|UNION|BROTHERHOOD|MACHINISTS)\y'
                then 'payroll_passthrough'
            when p.share_payroll_vouchers >= 0.5
                then 'payroll_passthrough'     -- e.g. employee charitable deductions
            when p.share_refund_vouchers >= 0.5
                or k.vendor_key ~ '\y(CONDO|CONDOS|CONDOMINIUM|CONDOMINIUMS|ASSN|HOMEOWNERS|TOWNHOMES)\y'
                then 'refund_rebate'           -- refunds; condo refuse rebates
            when k.vendor_key ~ '\y(SETTLEMENT|QUALIFIED ASSIGNMENT|STRUCTURED|QSF|ESTATE OF)\y'
                then 'legal_settlement'
            when k.vendor_key ~ '\y(COUNTY|STATE OF|ILLINOIS DEPARTMENT|UNITED STATES|U S DEPARTMENT|TREASURER|CLERK|DISTRICT|AUTHORITY|COMMISSION|BOARD OF|VILLAGE OF|CITY OF)\y'
                then 'government'
            when k.vendor_key ~ '\y(LAW|LAWYERS|ATTORNEY|ATTORNEYS|LEGAL)\y'
                then 'legal_unclassified'
            when k.vendor_key ~ '\y(BANK|TRUST)\y'
                then 'debt_financial'
            when k.vendor_key ~ '\y(EDISON|PEOPLES GAS|COMED|NICOR)\y'
                then 'utility'
            when cv.vendor_key is not null
                then 'goods_services'          -- a registered City contract vendor
            when p.sample_name ~* '\y(INC|LLC|L\.L\.C|CORP|CORPORATION|CO|COMPANY|LTD|LLP|LP|SERVICES|GROUP|ENTERPRISES|INTERNATIONAL|INDUSTRIES|SOLUTIONS|SYSTEMS|CONSTRUCTION|ENGINEERING|SUPPLY|ASSOCIATES|PARTNERS|FOUNDATION|CENTER|CHURCH|UNIVERSITY|HOSPITAL)\y'
                then 'goods_services'
            when k.vendor_key = '(BLANK)'
                then 'unclassified'
            -- No business suffix. Reads like a person (2-4 words, no "&") and paid a few
            -- times: a refund or claim. Paid repeatedly: a vendor without a suffix.
            when k.vendor_key !~ '&'
                 and array_length(regexp_split_to_array(k.vendor_key, ' '), 1) between 2 and 4
                 and p.n_payments <= 5
                then 'individual'
            -- A person paid repeatedly ("LAST, FIRST" or "FIRST M. LAST") could be an
            -- independent contractor or a stipend/assistance recipient; the data can't tell.
            when p.sample_name ~ '^[A-Z''-]+, [A-Z]' or p.sample_name ~ '^[A-Z]+ [A-Z]\.? [A-Z''-]+$'
                then 'individual_recurring'
            when p.n_payments > 5
                then 'goods_services'
            else 'unclassified'
        end as rule_type
    from keys k
    left join contract_vendors cv using (vendor_key)
    left join dw.payee_names p using (vendor_key)
    -- Override keys go through the same normalization, so a rule change can't orphan them.
    left join ref.payee_type_overrides o on dw.norm_name(o.payee_key) = k.vendor_key
)
select
    c.vendor_key,
    c.vendor_name,
    c.has_contract_record,
    c.n_vendor_ids,
    c.vendor_ids,
    c.n_payments,
    c.total_paid,
    coalesce(c.override_type, c.rule_type)                   as payee_type,
    t.payee_group,
    t.is_procurement_like,
    case when c.override_type is not null then 'override' else 'rule' end as classification_source,
    c.override_confidence                                    as classification_confidence
from classified c
left join ref.payee_types t on t.payee_type = coalesce(c.override_type, c.rule_type);

create unique index on dw.dim_vendor (vendor_key);
