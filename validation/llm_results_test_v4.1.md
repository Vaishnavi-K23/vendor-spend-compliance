# LLM extraction results: qwen2.5:7b, prompt v4.1, test split

196 documents ({'text': 112, 'scan': 84}), median 51s per document on the CPU.

## Summary fields vs the portal (same contract and revision)

accuracy = correct / scored; precision = correct / values extracted; coverage = values extracted / scored.
19 documents have no summary form on page 1 and aren't scored here: ['100106_5.pdf', '102620_4.pdf', '108929_2.pdf', '131840_3.pdf', '158837_9.pdf', '166316_5.pdf', '228978_1.pdf', '232051_0.pdf', '24326_0.pdf', '28080_8.pdf', '297081_0.pdf', '301207_0.pdf', '316300_0.pdf', '318306_1.pdf', '320970_0.pdf', '32204_0.pdf', '326747_0.pdf', '32916_0.pdf', '361224_0.pdf'].

| field | n | correct | wrong | missing | accuracy | precision | coverage |
|---|---|---|---|---|---|---|---|
| award_amount | 55.0 | 52.0 | 3.0 | 0.0 | 95% | 95% | 100% |
| contract_number | 177.0 | 175.0 | 1.0 | 1.0 | 99% | 99% | 99% |
| contractor_name | 177.0 | 172.0 | 5.0 | 0.0 | 97% | 97% | 100% |
| department | 175.0 | 169.0 | 6.0 | 0.0 | 97% | 97% | 100% |
| end_date | 142.0 | 123.0 | 13.0 | 6.0 | 87% | 90% | 96% |
| revision_number | 177.0 | 162.0 | 2.0 | 13.0 | 92% | 99% | 93% |
| start_date | 141.0 | 120.0 | 14.0 | 7.0 | 85% | 90% | 95% |

### By document kind

**scan** (74 documents): accuracy 91%

**text** (103 documents): accuracy 95%

### Does the evidence grade predict errors?

Accuracy of scored summary fields by confidence grade. If the gate works, `high` is far more accurate.

| confidence | n | accuracy |
|---|---|---|
| high | 917.0 | 97% |
| low | 11.0 | 64% |
| medium | 36.0 | 53% |
| not_found | 80.0 | 66% |

10 department values count as correct because the PDF names an earlier form of the portal's department (City reorganisations: General Services -> Fleet & Facility Management -> Assets, Information & Services; Business & Information Services -> Innovation & Technology).

## Contract-body fields vs hand labels

59 test documents labeled by hand from their full text (`validation/llm_body_labels.csv`). stated = documents that state the term; recall = correct / stated; precision = correct / values extracted; false_positive = a value extracted where the document states none.

| field | stated | correct | wrong | missing | recall | precision | not_stated | false_positive |
|---|---|---|---|---|---|---|---|---|
| not_to_exceed_amount | 52.0 | 12.0 | 3.0 | 37.0 | 23% | 80% | 7.0 | 0.0 |
| payment_terms_days | 12.0 | 3.0 | 1.0 | 8.0 | 25% | 60% | 47.0 | 1.0 |
| renewal_options_count | 10.0 | 8.0 | 1.0 | 1.0 | 80% | 89% | 49.0 | 0.0 |
| renewal_term_months | 10.0 | 7.0 | 2.0 | 1.0 | 70% | 78% | 49.0 | 0.0 |

### Body fields found

| field | high | low | medium |
|---|---|---|---|
| not_to_exceed_amount | 48 | 0 | 8 |
| payment_terms_days | 13 | 0 | 4 |
| renewal_options_count | 16 | 0 | 13 |
| renewal_term_months | 10 | 2 | 14 |

## Review gate

1146 of 1295 extracted values pass the gate; 149 go to `llm.manual_review_queue`:

| review_reason | count |
|---|---|
| value not confirmed by its quote | 87 |
| disagrees with portal | 44 |
| quote not found in document | 18 |

## Errors (summary fields)

| file | field | extracted | portal | confidence |
|---|---|---|---|---|
| 108189_1.pdf | revision_number | nan | 1 | not_found |
| 108189_1.pdf | start_date | 2019-02-23 | 2019-12-23 | high |
| 113838_6.pdf | revision_number | nan | 6 | not_found |
| 134949_2.pdf | contractor_name | COSTARREALTY INFORMATION, INC | COSTAR|CLEANED-UP | high |
| 148654_2.pdf | contractor_name | GRANITE CONSTRUCTION CO. | KENNY CONSTRUCTION COMPANY | high |
| 174503_4.pdf | revision_number | nan | 4 | not_found |
| 176307_2.pdf | revision_number | nan | 2 | not_found |
| 176307_2.pdf | contractor_name | Rogers Park Community Council dba Northside Community Resources | NORTHSIDE COMMUNITY DEVELOPMENT CORPORATION|CLEANED-UP | high |
| 177765_2.pdf | revision_number | nan | 2 | not_found |
| 184524_0.pdf | department | DEPT OF ASSETS INFORMATION AND SERVICES | DEPARTMENT OF ENVIRONMENT | high |
| 186153_1.pdf | revision_number | nan | 1 | not_found |
| 186153_1.pdf | department | Sanitation | CHICAGO POLICE DEPARTMENT | high |
| 20339_10.pdf | start_date | 2010-12-21 | 2010-02-05 | medium |
| 20339_10.pdf | end_date | 2021-11-30 | 2021-08-01 | medium |
| 210686_1.pdf | revision_number | nan | 1 | not_found |
| 21191_1.pdf | contractor_name | HARRIS CORPORATION | L3HARRIS TECHNOLOGIES, INC. | high |
| 21191_1.pdf | start_date | nan | 2011-06-23 | not_found |
| 21191_1.pdf | end_date | nan | 2018-06-22 | not_found |
| 214209_0.pdf | department | OPSA | CHICAGO FIRE DEPARTMENT | high |
| 230644_2.pdf | revision_number | nan | 2 | not_found |
| 230644_2.pdf | department | City Department | DEPARTMENT OF FAMILY AND SUPPORT SERVICES | low |
| 230644_2.pdf | start_date | 2023-01-01 | 2023-05-01 | high |
| 256040_0.pdf | end_date | nan | 2025-04-24 | not_found |
| 26603_7.pdf | start_date | nan | 2012-08-20 | not_found |
| 26603_7.pdf | end_date | 2019-12-16 | 2019-08-16 | medium |
| 26644_4.pdf | start_date | nan | 2012-10-31 | not_found |
| 26775_1.pdf | start_date | nan | 2012-09-27 | not_found |
| 26775_1.pdf | end_date | nan | 2017-09-26 | not_found |
| 27075_3.pdf | start_date | 2012-11-06 | 2012-06-01 | medium |
| 273020_0.pdf | start_date | nan | 2024-08-01 | not_found |
| 273020_0.pdf | end_date | nan | 2024-12-31 | not_found |
| 273020_0.pdf | award_amount | 119792 | 1677083.0 | high |
| 27750_2.pdf | revision_number | nan | 2 | not_found |
| 28300_10.pdf | start_date | 2013-11-01 | 2013-08-01 | medium |
| 28300_10.pdf | end_date | 2022-11-26 | 2022-01-26 | medium |
| 29118_3.pdf | start_date | 2013-01-12 | 2013-12-20 | medium |
| 298749_0.pdf | award_amount | 38350 | 53340.0 | high |
| 32528_7.pdf | department | CPD | CHICAGO FIRE DEPARTMENT | high |
| 32528_7.pdf | end_date | 2022-06-30 | 2023-12-29 | high |
| 335940_0.pdf | contract_number | C335940 | 335940 | high |
| 33795_4.pdf | start_date | 2016-12-31 | 2016-03-09 | medium |
| 33795_4.pdf | end_date | 2022-06-30 | 2022-03-06 | medium |
| 340030_0.pdf | revision_number | 12 | nan | high |
| 342803_0.pdf | revision_number | 2026 | nan | high |
| 342803_0.pdf | award_amount | 36845641 | 13610.0 | high |
| 37504_4.pdf | start_date | 2021-12-01 | 2017-02-08 | low |
| 37504_4.pdf | end_date | 2022-02-28 | 2027-02-07 | low |
| 41709_1.pdf | revision_number | nan | 1 | not_found |
| 41709_1.pdf | end_date | 2022-07-14 | 2021-07-14 | high |
| 46733_5.pdf | start_date | 2016-10-08 | 2016-08-01 | medium |
| 46733_5.pdf | end_date | 2022-06-29 | 2023-06-29 | medium |
| 54002_0.pdf | start_date | 2018-01-01 | 2018-02-01 | medium |
| 54742_8.pdf | contract_number | nan | 54742 | not_found |
| 54742_8.pdf | revision_number | nan | 8 | not_found |
| 54742_8.pdf | department | Public Safety Administration | OFFICE OF EMERGENCY MANAGEMENT AND COMMUNICATIONS | high |
| 54742_8.pdf | start_date | nan | 2017-05-01 | not_found |
| 54742_8.pdf | end_date | nan | 2023-04-30 | not_found |
| 56283_2.pdf | start_date | 2017-08-17 | 2017-08-07 | medium |
| 56283_2.pdf | end_date | 2029-08-16 | 2029-08-06 | medium |
| 63833_2.pdf | start_date | 2017-09-10 | 2017-10-10 | high |
| 64824_3.pdf | end_date | 2025-12-31 | 2024-12-31 | high |
| 75072_2.pdf | revision_number | nan | 2 | not_found |
| 75072_2.pdf | start_date | 2018-11-01 | 2018-07-10 | medium |
| 75072_2.pdf | end_date | 2020-12-19 | 2020-07-09 | medium |
| 84664_31.pdf | contractor_name | GRANITE CONSTRUCTION CO. | KENNY CONSTRUCTION COMPANY | high |
| 86020_1.pdf | revision_number | nan | 1 | not_found |
| 89344_1.pdf | end_date | 2023-12-25 | 2024-12-22 | high |
| 91955_2.pdf | start_date | nan | 2019-02-01 | not_found |
| 91955_2.pdf | end_date | nan | 2024-12-31 | not_found |
| T26138_12.pdf | start_date | 2001-08-13 | 2001-08-31 | medium |
| T26138_12.pdf | end_date | 2019-08-13 | 2019-08-31 | low |
