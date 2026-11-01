-- severity: info
-- why: DV dollars whose payee type is unknown (failing_rows/total_rows are $ thousands) are excluded from both sides of the off-contract KPI.
select coalesce(round(sum(amount) filter (where payee_type in ('unclassified', 'legal_unclassified')) / 1000), 0)::bigint as failing_rows,
       round(sum(amount) / 1000)::bigint as total_rows
from dw.fact_payment where is_direct_voucher;
