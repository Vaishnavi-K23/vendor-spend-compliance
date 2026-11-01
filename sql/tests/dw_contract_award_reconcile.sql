-- severity: error
-- why: dim_contract cumulative award must equal the sum of its revisions.
select count(*) filter (where c.cumulative_award <> r.total) as failing_rows, count(*) as total_rows
from dw.dim_contract c
join (select contract_number, sum(coalesce(amount_change, 0)) total from dw.fact_contract_revision group by 1) r
using (contract_number);
