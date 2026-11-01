-- severity: error
-- why: itemized + annual fact dollars must equal staging dollars to the cent (failing_rows = 1 if not).
select case when (select sum(amount) from stg.payments)
               = (select sum(amount) from dw.fact_payment) + (select sum(amount) from dw.fact_payment_annual)
            then 0 else 1 end as failing_rows,
       1 as total_rows;
