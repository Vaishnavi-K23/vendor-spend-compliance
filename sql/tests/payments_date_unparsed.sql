-- severity: error
-- why: check_date must be either mm/dd/yyyy or a bare year; anything else is a new format to handle.
select count(*) filter (where payment_year is null) as failing_rows,
       count(*) as total_rows
from stg.payments;
