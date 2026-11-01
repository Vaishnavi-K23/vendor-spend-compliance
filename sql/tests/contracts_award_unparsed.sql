-- severity: error
-- why: award_amount that is present in raw but did not parse means the cast rule is wrong.
select count(*) filter (where s.award_amount is null and nullif(r.award_amount, '') is not null) as failing_rows,
       count(*) as total_rows
from stg.contracts s join raw.contracts r on r._row_id = s.raw_row_id;
