-- Shared dimensions: calendar and department.

drop table if exists dw.dim_calendar cascade;
create table dw.dim_calendar as
select
    d::date                              as date,
    extract(year from d)::int            as year,
    extract(quarter from d)::int         as quarter,
    extract(month from d)::int           as month,
    to_char(d, 'Mon')                    as month_name,
    date_trunc('month', d)::date         as month_start,
    extract(isodow from d)::int          as day_of_week,
    extract(isodow from d) in (6, 7)     as is_weekend
from generate_series('2002-01-01'::date, '2027-12-31'::date, interval '1 day') d;  -- Chicago FY = calendar year

create unique index on dw.dim_calendar (date);

-- Payment and contract department names already match exactly (checked in Phase 1).
drop table if exists dw.dim_department cascade;
create table dw.dim_department as
select department, department = 'UNKNOWN' as is_unknown
from (select department from dw.dim_contract
      union select department from dw.fact_payment
      union select department from dw.fact_payment_annual
      union select 'UNKNOWN') d;

create unique index on dw.dim_department (department);
