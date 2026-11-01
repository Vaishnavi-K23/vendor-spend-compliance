-- severity: error
-- why: every payment must have a numeric amount or spend totals are understated.
select count(*) filter (where amount is null) as failing_rows,
       count(*) as total_rows
from stg.payments;
