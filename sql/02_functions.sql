-- Name normalization used to match vendor and payee names across tables.
-- Payments carry only a vendor name (no vendor ID), so this is the join key for
-- direct-voucher payees, and it groups spelling variants of the same vendor ID.

create schema if not exists dw;

create or replace function dw.norm_name(t text) returns text
language sql immutable as $$
    select nullif(trim(
        regexp_replace(
        regexp_replace(
        regexp_replace(
        regexp_replace(
        regexp_replace(
        regexp_replace(upper(coalesce(t, '')),
            '\|CLEANED-UP|\yD ?/ ?B ?/ ?A\y.*$', '', 'g'),       -- admin tag; trailing d/b/a trade name
            '[^A-Z0-9& ]', ' ', 'g'),                              -- punctuation -> space
            '\s*&\s*', ' & ', 'g'),                                -- "AT&T" = "AT & T"
            '\y(THE|INC|INCORPORATED|LLC|L L C|LLP|PLLC|LTD|LIMITED|CORP|CORPORATION|CO|COMPANY|P C|PC|N A|NA)\y', ' ', 'g'),
            '\s+0\d$', ''),                                         -- trailing record suffix like " 01"
            '\s+', ' ', 'g')), '')
$$;
