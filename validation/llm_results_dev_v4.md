# LLM extraction results: qwen2.5:7b, prompt v4, dev split

24 documents ({'text': 14, 'scan': 10}), median 46s per document on the CPU.

## Summary fields vs the portal (same contract and revision)

accuracy = correct / scored; precision = correct / values extracted; coverage = values extracted / scored.
1 documents have no summary form on page 1 and aren't scored here: ['340903_0.pdf'].

| field | n | correct | wrong | missing | accuracy | precision | coverage |
|---|---|---|---|---|---|---|---|
| award_amount | 13.0 | 12.0 | 0.0 | 1.0 | 92% | 100% | 92% |
| contract_number | 23.0 | 22.0 | 1.0 | 0.0 | 96% | 96% | 100% |
| contractor_name | 23.0 | 22.0 | 1.0 | 0.0 | 96% | 96% | 100% |
| department | 23.0 | 22.0 | 1.0 | 0.0 | 96% | 96% | 100% |
| end_date | 20.0 | 16.0 | 4.0 | 0.0 | 80% | 80% | 100% |
| revision_number | 23.0 | 22.0 | 0.0 | 1.0 | 96% | 100% | 96% |
| start_date | 20.0 | 18.0 | 1.0 | 1.0 | 90% | 95% | 95% |

### By document kind

**scan** (9 documents): accuracy 89%

**text** (14 documents): accuracy 94%

### Does the evidence grade predict errors?

Accuracy of scored summary fields by confidence grade. If the gate works, `high` is far more accurate.

| confidence | n | accuracy |
|---|---|---|
| high | 121.0 | 98% |
| low | 3.0 | 100% |
| medium | 5.0 | 0% |
| not_found | 16.0 | 81% |

1 department values count as correct because the PDF names an earlier form of the portal's department (City reorganisations: General Services -> Fleet & Facility Management -> Assets, Information & Services; Business & Information Services -> Innovation & Technology).

## Contract-body fields

Not scored yet: hand labels go in `validation/llm_body_labels.csv`.

### Body fields found

| field | high | medium |
|---|---|---|
| not_to_exceed_amount | 14 | 0 |
| payment_terms_days | 1 | 1 |
| renewal_options_count | 3 | 1 |
| renewal_term_months | 3 | 0 |

## Review gate

150 of 166 extracted values pass the gate; 16 go to `llm.manual_review_queue`:

| review_reason | count |
|---|---|
| disagrees with portal | 8 |
| value not confirmed by its quote | 4 |
| quote not found in document | 4 |

## Errors (summary fields)

| file | field | extracted | portal | confidence |
|---|---|---|---|---|
| 211667_1.pdf | revision_number | nan | 1 | not_found |
| 148654_1.pdf | contractor_name | GRANITE CONSTRUCTION CO. | KENNY CONSTRUCTION COMPANY | high |
| 19393_3.pdf | end_date | 2016-03-19 | 2016-12-31 | medium |
| 100106_0.pdf | start_date | 2019-12-05 | 2019-05-20 | medium |
| 100106_0.pdf | end_date | 2019-11-05 | 2024-05-19 | medium |
| 318277_0.pdf | department | DEPARTMENT OF HOUSING | DEPARTMENT OF PLANNING AND DEVELOPMENT | high |
| 318277_0.pdf | start_date | nan | 2025-05-22 | not_found |
| 318277_0.pdf | end_date | 2025-05-22 | 2064-06-01 | high |
| 225755_0.pdf | contract_number | strconv5755 | 225755 | medium |
| 307284_0.pdf | award_amount | nan | 15650617.0 | not_found |
| 175192_0.pdf | end_date | 2025-01-01 | 2025-05-02 | medium |
