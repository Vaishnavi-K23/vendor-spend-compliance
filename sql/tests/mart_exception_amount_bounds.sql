-- severity: error
-- why: an exception can never claim more than the payment itself, and a payment without an exception type must carry $0.
select count(*) filter (where (amount > 0 and exception_amount > amount)
                           or (exception_type is null and exception_amount <> 0)) as failing_rows,
       count(*) as total_rows
from dw.mart_payment_exceptions;
