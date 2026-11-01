-- severity: error
-- why: every in-scope purchasing payment (DV 2022+, contract 2025+) must appear in the exceptions mart exactly once.
select abs((select count(*) from dw.fact_payment f join ref.payee_types t using (payee_type)
            where t.is_procurement_like and (f.is_direct_voucher or f.payment_date >= date '2025-01-01'))
           - (select count(*) from dw.mart_payment_exceptions)) as failing_rows,
       (select count(*) from dw.mart_payment_exceptions) as total_rows;
