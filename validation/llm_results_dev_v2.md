# LLM extraction results: qwen2.5:7b, prompt v2, dev split

24 documents ({'text': 14, 'scan': 10}), median 57s per document on the CPU.

## Summary fields vs the portal (same contract and revision)

accuracy = correct / scored; precision = correct / values extracted; coverage = values extracted / scored.
1 documents have no summary form on page 1 and aren't scored here: ['340903_0.pdf'].

| field | n | correct | wrong | missing | accuracy | precision | coverage |
|---|---|---|---|---|---|---|---|
| award_amount | 13.0 | 12.0 | 0.0 | 1.0 | 92% | 100% | 92% |
| contract_number | 23.0 | 13.0 | 4.0 | 6.0 | 57% | 76% | 74% |
| contractor_name | 23.0 | 22.0 | 1.0 | 0.0 | 96% | 96% | 100% |
| department | 23.0 | 21.0 | 2.0 | 0.0 | 91% | 91% | 100% |
| end_date | 20.0 | 17.0 | 3.0 | 0.0 | 85% | 85% | 100% |
| revision_number | 23.0 | 14.0 | 2.0 | 7.0 | 61% | 88% | 70% |
| start_date | 20.0 | 19.0 | 1.0 | 0.0 | 95% | 95% | 100% |

### By document kind

**scan** (9 documents): accuracy 78%

**text** (14 documents): accuracy 83%

### Does the evidence grade predict errors?

Accuracy of scored summary fields by confidence grade. If the gate works, `high` is far more accurate.

| confidence | n | accuracy |
|---|---|---|
| high | 97.0 | 94% |
| low | 14.0 | 100% |
| medium | 7.0 | 0% |
| not_found | 27.0 | 48% |

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

125 of 155 extracted values pass the gate; 30 go to `llm.manual_review_queue`:

| review_reason | count |
|---|---|
| quote not found in document | 14 |
| disagrees with portal | 13 |
| value not confirmed by its quote | 3 |

## Errors (summary fields)

| file | field | extracted | portal | confidence |
|---|---|---|---|---|
| 37743_7.pdf | revision_number | {7} | 7 | high |
| 211667_1.pdf | revision_number | nan | 1 | not_found |
| 224791_1.pdf | revision_number | {1} | 1 | high |
| 148654_1.pdf | contract_number | nan | 148654 | not_found |
| 148654_1.pdf | revision_number | nan | 1 | not_found |
| 148654_1.pdf | contractor_name | GRANITE CONSTRUCTION CO. | KENNY CONSTRUCTION COMPANY | high |
| 19393_3.pdf | department | DEPT OF INNOVATION & TECHNOLOGY | DEPT OF BUSINESS & INFORMATION SERVICES | high |
| 19393_3.pdf | end_date | 2016-03-19 | 2016-12-31 | medium |
| 162388_2.pdf | contract_number | nan | 162388 | not_found |
| 162388_2.pdf | revision_number | nan | 2 | not_found |
| 334001_0.pdf | contract_number |  | 334001 | high |
| 79644_7.pdf | contract_number | nan | 79644 | not_found |
| 79644_7.pdf | revision_number | nan | 7 | not_found |
| 267871_0.pdf | contract_number | strconv7871 | 267871 | medium |
| 32790_0.pdf | contract_number | s32790 | 32790 | medium |
| 64819_1.pdf | revision_number | nan | 1 | not_found |
| 66009_6.pdf | contract_number | nan | 66009 | not_found |
| 66009_6.pdf | revision_number | nan | 6 | not_found |
| 56322_15.pdf | contract_number | nan | 56322 | not_found |
| 56322_15.pdf | revision_number | nan | 15 | not_found |
| 100106_0.pdf | start_date | 2019-12-05 | 2019-05-20 | medium |
| 100106_0.pdf | end_date | 2019-11-05 | 2024-05-19 | medium |
| 318277_0.pdf | department | DEPARTMENT OF HOUSING | DEPARTMENT OF PLANNING AND DEVELOPMENT | high |
| 225755_0.pdf | contract_number | strconv5755 | 225755 | medium |
| 307284_0.pdf | contract_number | nan | 307284 | not_found |
| 307284_0.pdf | award_amount | nan | 15650617.0 | not_found |
| 175192_0.pdf | end_date | 2025-01-01 | 2025-05-02 | medium |
