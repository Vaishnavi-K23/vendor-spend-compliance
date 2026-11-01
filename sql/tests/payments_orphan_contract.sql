-- severity: warn
-- why: payments citing a contract number missing from the contracts table cannot be checked against award or term.
select count(*) filter (where c.contract_number is null) as failing_rows,
       count(*) as total_rows
from stg.payments p
left join (select distinct contract_number from stg.contracts) c using (contract_number)
where p.contract_number is not null;
