-- severity: warn
-- why: a term that ends before it starts breaks days-to-expiry and "paid after end date" logic.
select count(*) filter (where end_date < start_date) as failing_rows,
       count(*) as total_rows
from stg.contracts;
