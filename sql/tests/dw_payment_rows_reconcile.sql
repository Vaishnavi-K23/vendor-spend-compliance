-- severity: error
-- why: every itemized staging payment must land in dw.fact_payment exactly once.
select abs((select count(*) from stg.payments where is_itemized) - (select count(*) from dw.fact_payment)) as failing_rows,
       (select count(*) from stg.payments where is_itemized) as total_rows;
