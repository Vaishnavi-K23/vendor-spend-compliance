-- severity: error
-- why: every payment must resolve to a vendor in dw.dim_vendor.
select count(*) filter (where v.vendor_key is null) as failing_rows, count(*) as total_rows
from dw.fact_payment f left join dw.dim_vendor v using (vendor_key);
