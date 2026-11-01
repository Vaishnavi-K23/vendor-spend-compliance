-- severity: error
-- why: an override that matches no payee means its key drifted from dw.norm_name and the classification silently fell back to rules.
select count(*) filter (where v.vendor_key is null) as failing_rows, count(*) as total_rows
from ref.payee_type_overrides o left join dw.dim_vendor v on v.vendor_key = dw.norm_name(o.payee_key);
