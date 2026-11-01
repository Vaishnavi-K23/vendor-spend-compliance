-- severity: warn
-- why: the same contract revision published under two vendor records (renamed or re-registered vendor); dedupe before summing awards.
select coalesce(sum(n - 1), 0) as failing_rows,
       (select count(*) from stg.contracts) as total_rows
from (select count(*) as n from stg.contracts
      group by contract_number, revision_number having count(distinct vendor_id) > 1) d;
