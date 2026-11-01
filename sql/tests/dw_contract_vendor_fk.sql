-- severity: error
-- why: every contract must resolve to a vendor in dw.dim_vendor.
select count(*) filter (where v.vendor_key is null) as failing_rows, count(*) as total_rows
from dw.dim_contract c left join dw.dim_vendor v using (vendor_key);
