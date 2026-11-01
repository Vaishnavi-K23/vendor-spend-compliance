-- severity: error
-- why: every PDF link must be a known format (current GUID or legacy EDGE) or the downloader cannot fetch it.
select count(*) filter (where pdf_link_format = 'other') as failing_rows,
       count(*) filter (where pdf_url is not null) as total_rows
from stg.contracts;
