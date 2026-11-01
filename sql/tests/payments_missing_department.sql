-- severity: info
-- why: department is needed for maverick-spend breakdowns; contract-linked rows can inherit it from stg.contracts.
select count(*) filter (where department_name is null) as failing_rows,
       count(*) as total_rows
from stg.payments;
