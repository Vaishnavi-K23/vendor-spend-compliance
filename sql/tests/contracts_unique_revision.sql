-- severity: error
-- why: contract_number + revision_number + vendor_id is the grain of stg.contracts; duplicates double-count award growth.
select count(*) - count(distinct (contract_number, revision_number, vendor_id)) as failing_rows,
       count(*) as total_rows
from stg.contracts;
