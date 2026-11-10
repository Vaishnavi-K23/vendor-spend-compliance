# LLM extraction results: qwen2.5:7b, prompt v1, dev split

21 documents ({'text': 11, 'scan': 10}), median 71s per document on the CPU.

## Summary fields vs the portal (same contract and revision)

accuracy = correct / scored; precision = correct / values extracted; coverage = values extracted / scored.
1 documents have no summary form on page 1 and aren't scored here: ['340903_0.pdf'].

| field | n | correct | wrong | missing | accuracy | precision | coverage |
|---|---|---|---|---|---|---|---|
| award_amount | 12.0 | 10.0 | 1.0 | 1.0 | 83% | 91% | 92% |
| contract_number | 20.0 | 20.0 | 0.0 | 0.0 | 100% | 100% | 100% |
| contractor_name | 20.0 | 18.0 | 1.0 | 1.0 | 90% | 95% | 95% |
| department | 20.0 | 18.0 | 2.0 | 0.0 | 90% | 90% | 100% |
| end_date | 17.0 | 14.0 | 3.0 | 0.0 | 82% | 82% | 100% |
| revision_number | 20.0 | 7.0 | 13.0 | 0.0 | 35% | 35% | 100% |
| start_date | 17.0 | 16.0 | 1.0 | 0.0 | 94% | 94% | 100% |

### By document kind

**scan** (9 documents): accuracy 84%

**text** (11 documents): accuracy 80%

### Does the evidence grade predict errors?

Accuracy of scored summary fields by confidence grade. If the gate works, `high` is far more accurate.

| confidence | n | accuracy |
|---|---|---|
| high | 119.0 | 85% |
| low | 1.0 | 100% |
| medium | 3.0 | 0% |
| not_found | 3.0 | 33% |

## Contract-body fields

Not scored yet: hand labels go in `validation/llm_body_labels.csv`.

### Body fields found

| field | high | low | medium |
|---|---|---|---|
| not_to_exceed_amount | 11 | 1 | 1 |
| payment_terms_days | 1 | 0 | 1 |
| renewal_options_count | 2 | 0 | 0 |
| renewal_term_months | 2 | 0 | 0 |

## Review gate

128 of 155 extracted values pass the gate; 27 go to `llm.manual_review_queue`:

| review_reason | count |
|---|---|
| disagrees with portal | 21 |
| quote not found in document | 4 |
| value not confirmed by its quote | 2 |

## Errors (summary fields)

| file | field | extracted | portal | confidence |
|---|---|---|---|---|
| 211667_1.pdf | revision_number | 1248935 | 1 | high |
| 211667_1.pdf | contractor_name | nan | CAROLE ROBERTSON CENTER FOR LEARNING | not_found |
| 148654_1.pdf | contractor_name | GRANITE CONSTRUCTION CO. | KENNY CONSTRUCTION COMPANY | high |
| 19393_3.pdf | department | DEPT OF INNOVATION & TECHNOLOGY | DEPT OF BUSINESS & INFORMATION SERVICES | high |
| 19393_3.pdf | end_date | 2016-03-19 | 2016-12-31 | medium |
| 294957_0.pdf | revision_number | 450998 | nan | high |
| 216193_0.pdf | revision_number | 1200928 | nan | high |
| 334001_0.pdf | revision_number | 1330863 | nan | high |
| 267871_0.pdf | revision_number | 1290468 | nan | high |
| 333083_0.pdf | revision_number | Rev 09/25 | nan | high |
| 333083_0.pdf | award_amount | 102000 | 306000.0 | high |
| 32790_0.pdf | revision_number | 133154 | nan | high |
| 64819_1.pdf | revision_number | 186944 | 1 | high |
| 100106_0.pdf | revision_number | 547589A | nan | high |
| 100106_0.pdf | start_date | 2019-12-05 | 2019-05-20 | medium |
| 100106_0.pdf | end_date | 2019-11-05 | 2024-05-19 | medium |
| 318277_0.pdf | revision_number | 1329745 | nan | high |
| 318277_0.pdf | department | DEPARTMENT OF HOUSING | DEPARTMENT OF PLANNING AND DEVELOPMENT | high |
| 215577_0.pdf | revision_number | 1244618 | nan | high |
| 225755_0.pdf | revision_number | 1209922 | nan | high |
| 307284_0.pdf | award_amount | nan | 15650617.0 | not_found |
| 175192_0.pdf | revision_number | 1186765 | nan | high |
| 175192_0.pdf | end_date | 2025-05-01 | 2025-05-02 | high |
