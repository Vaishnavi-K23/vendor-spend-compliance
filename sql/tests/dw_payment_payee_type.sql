-- severity: error
-- why: every payment needs a payee type, or it falls out of the off-contract KPI.
select count(*) filter (where payee_type is null) as failing_rows, count(*) as total_rows
from dw.fact_payment;
