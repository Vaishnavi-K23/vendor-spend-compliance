-- severity: info
-- why: $0 revisions are usually time extensions or admin changes; they must not count as a $0 cap.
select count(*) filter (where award_amount = 0) as failing_rows,
       count(*) as total_rows
from stg.contracts;
