-- Typed staging layer over raw.*. No business logic here, only parsing and
-- normalization; every rule below is listed in docs/data-profile.md.

create schema if not exists stg;

-- One row per contract revision per vendor record (revision 0 = original award).
-- The portal republishes a handful of revisions twice; keep the copy with a PDF link.
drop table if exists stg.contracts cascade;
create table stg.contracts as
select distinct on (trim(purchase_order_contract_number), trim(revision_number), nullif(trim(vendor_id), ''))
    _row_id                                             as raw_row_id,
    trim(purchase_order_contract_number)                as contract_number,
    -- ~9% of revisions are codes like 'T10456', so keep the text; revision_seq orders numeric ones.
    trim(revision_number)                               as revision_number,
    case when revision_number ~ '^\d+$' then revision_number::int end
                                                        as revision_seq,
    nullif(trim(specification_number), '')              as specification_number,
    nullif(trim(contract_type), '')                     as contract_type,
    nullif(trim(procurement_type), '')                  as procurement_type,
    nullif(trim(department), '')                        as department,
    nullif(trim(vendor_id), '')                         as vendor_id,
    upper(regexp_replace(trim(vendor_name), '\s+', ' ', 'g'))
                                                        as vendor_name,
    nullif(trim(purchase_order_description), '')        as description,
    nullif(start_date, '')::timestamp::date             as start_date,
    nullif(end_date, '')::timestamp::date               as end_date,
    nullif(approval_date, '')::timestamp::date          as approval_date,
    case when award_amount ~ '^-?\d+(\.\d+)?$' then award_amount::numeric(18, 2) end
                                                        as award_amount,
    -- Two link formats: current links carry the document GUID; legacy (sid=EDGE) links
    -- carry a short ID that the viewer resolves to a GUID at download time.
    nullif(trim(contract_pdf), '')                      as pdf_url,
    case when contract_pdf ~ 'id=\{[0-9A-Fa-f-]+\}' then 'current'
         when contract_pdf ~ 'sid=EDGE'             then 'legacy'
         when nullif(trim(contract_pdf), '') is not null then 'other' end
                                                        as pdf_link_format,
    substring(contract_pdf from 'id=(\{[0-9A-Fa-f-]+\})') as pdf_doc_id
from raw.contracts
order by trim(purchase_order_contract_number), trim(revision_number), nullif(trim(vendor_id), ''),
         (contract_pdf is null), _row_id;

create index on stg.contracts (contract_number, revision_number);

-- One row per published payment line.
-- check_date is mm/dd/yyyy for itemized payments (2022+) and a bare year for
-- older payments, which the portal publishes as one annual total per contract.
-- contract_number 'DV' = direct voucher, i.e. paid without a contract.
drop table if exists stg.payments cascade;
create table stg.payments as
select
    _row_id                                             as payment_id,
    nullif(trim(voucher_number), '')                    as voucher_number,
    case when amount ~ '^-?\d+(\.\d+)?$' then amount::numeric(18, 2) end
                                                        as amount,
    check_date                                          as check_date_raw,
    case when check_date ~ '^\d{2}/\d{2}/\d{4}$'
         then to_date(check_date, 'MM/DD/YYYY') end     as check_date,
    case when check_date ~ '^\d{4}$' then check_date::int
         when check_date ~ '^\d{2}/\d{2}/\d{4}$'
         then right(check_date, 4)::int end             as payment_year,
    check_date ~ '^\d{2}/\d{2}/\d{4}$'                  as is_itemized,
    trim(contract_number) = 'DV'                        as is_direct_voucher,
    nullif(nullif(trim(contract_number), 'DV'), '')     as contract_number,
    nullif(trim(department_name), '')                   as department_name,
    upper(regexp_replace(trim(vendor_name), '\s+', ' ', 'g'))
                                                        as vendor_name
from raw.payments;

create index on stg.payments (contract_number);
create index on stg.payments (check_date);
