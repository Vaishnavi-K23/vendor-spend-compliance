# LLM prompt log

Model: Qwen 2.5 7B (Ollama, local CPU), temperature 0, seed 42, JSON-schema output.
Prompts and schemas live in `src/extract/prompts.py`; every change bumps `PROMPT_VERSION`.

**Method.** Prompts are tuned only on the 24-document development set
(`data/reference/llm_dev_set.csv`, the first PDFs downloaded). The headline accuracy is measured
once, on the remaining test documents, with the final prompt. Tuning on the documents you
report on would overstate accuracy.

## v1: first version

Observed on the first two development documents, before any scoring:

| Problem | Example | Type |
| --- | --- | --- |
| Revision number filled with the Specification Number | 100106_0: "547589A" | prompt |
| OCR-damaged date read as a different date | "5120/2019" (5/20/2019) → 2019-12-05 | model + OCR |
| Percentage read as a dollar cap | "NOT TO EXCEED 12%" → $12,000 | prompt |
| Contractor missing on grant forms | the label there is "Delegate Agency" | prompt |
| Evidence check passed a wrong date | year + day matched by chance | **grader bug, fixed**: now needs the full date in a form documents use |

**v1 on the development set** (21 of 24 documents; 3 timed out, 2 more looped):

| Field | Accuracy | Notes |
| --- | --- | --- |
| contract_number | 100% | |
| start_date | 94% | |
| contractor_name | 90% | grant form labels it "Delegate Agency" |
| department | 90% | 2 are real PDF/portal differences (department renamed) |
| award_amount | 83% | |
| end_date | 82% | OCR-damaged dates ("19/31/2016") |
| revision_number | **35%** | model returns the Specification Number |

Evidence grade: `high` 85% accurate (n = 119), `medium` 0% (n = 3). The grade separates good from bad values; `high` is pulled down almost entirely by the revision-number problem.

Runtime: median 71 s per document. Two documents looped, repeating table rows inside a quote
(about 7,800 output tokens instead of about 300), and three hit the 30-minute timeout. Several runs
also stalled while the laptop slept.

**Grader fixes made while reading v1's errors** (scoring, not the model):
- A revision can list several vendors (joint ventures); any of them now counts as a match.
- Department abbreviations the City uses on its own forms (DCASE, 2FM, CDOT…) are expanded;
  apostrophes are dropped ("O'HARE" = "OHARE").
- Documents with no summary form on page 1 (e.g. an ordinance) aren't scored on summary fields.
  Returning nothing there is the right answer.

## v2

| Change | Why |
| --- | --- |
| Revision number: only the value labeled "Modification Revision Number", never Specification/Requisition/Vendor Number; null on a Contract Summary Sheet | v1 revision accuracy 35% |
| Contractor: "on grant forms, the Delegate Agency" | v1 missed it on grant forms |
| Modification reason: the short code only | v1 copied long descriptions |
| Not-to-exceed: dollars only, not percentages or per-item caps | v1 read "NOT TO EXCEED 12%" as $12,000 |
| Schema: quotes ≤ 300 characters, string values ≤ 120; output capped at 1,500 tokens; 15-minute timeout | stops the looping seen in v1 |
| Runner keeps Windows awake during a run | v1 stalled during sleep |

**v2 on the development set** (24 of 24 documents, median 57 s, no loops or timeouts):

| Field | v1 | v2 |
| --- | --- | --- |
| revision_number | 35% | 61% |
| contractor_name | 90% | 96% |
| award_amount | 83% | 92% |
| start_date | 94% | 95% |
| end_date | 82% | 85% |
| department | 90% | 91% |
| contract_number | 100% | **57%** |

Contract number regressed: values like `strconv7871`, `{7}` and blanks. Cause: the `maxLength`
limits. Ollama compiles the schema into a grammar that constrains each token, and the length
limits distorted it. The prompt fixes worked; the schema fix broke simple fields.
Evidence grade: `high` 94% accurate (n = 97), `medium` 0% (n = 7).

## v3

| Change | Why |
| --- | --- |
| Remove `maxLength` from the schema | v2 contract-number regression |
| Keep the 1,500-token output cap; if the JSON comes back cut off, retry once with repeat_penalty 1.3 | still guards against v1's looping |

**v3 result: identical to v2, field for field.** So `maxLength` was not the cause; the v2 diagnosis
was wrong. Ablation on the 6 documents that failed, summary call only:

| Prompt | contract_number | revision_number |
| --- | --- | --- |
| v3 as is | 0/6 | 1/6 |
| without "if the page is not a summary form, return null" | 4/6 | 1/6 |
| without the long revision-number rule | 5/6 | 3/6 |

Both added rules made the model abstain on fields it got right in v1. The revision rule made
revision numbers *worse*. Lesson: with a 7B model, more "never do X" instructions made it more
cautious across the board, not more precise.

## v4

| Change | Why |
| --- | --- |
| Remove both rules (keep the contractor and modification-reason lines, which helped) | ablation above |
| **Label check in code**: a revision number counts only if its quote contains "Revision"; otherwise it's set to null and the rejected value is kept | moves the fix from prompt wording to a deterministic rule |

**v4 on the development set** (24 of 24, median 46 s per document):

| Field | v1 | v2 | v3 | v4 |
| --- | --- | --- | --- | --- |
| contract_number | 100% | 57% | 57% | 96% |
| revision_number | 35% | 61% | 61% | **96%** |
| contractor_name | 90% | 96% | 96% | 96% |
| award_amount | 83% | 92% | 92% | 92% |
| department | 90% | 91% | 91% | 91% |
| start_date | 94% | 95% | 95% | 90% |
| end_date | 82% | 85% | 85% | 80% |

Evidence grade: `high` 97% accurate (n = 121); `medium` 0% (n = 5). Remaining errors: OCR-damaged
dates (all graded `medium`, so gated), PDF/portal disagreements (renamed department, joint-venture
vendor, a lease with a 2064 end date), and one `strconv` artifact (graded `medium`).

**v4 is frozen** and run once on the test set. Test-set results: `validation/llm_results.md`.

## v4 on the test set (final prompt, run once)

196 documents (112 text, 84 scan), median 51 s per document; 19 have no summary form on page 1.
Reports: `validation/llm_results_test_v4.md` (model output as run) and
`validation/llm_results_test_v4.1.md` (same output, code fixes below).

### Summary fields

| Field | Dev v4 | Test v4, original grader | Test v4, fixed grader | **Test v4.1** |
| --- | --- | --- | --- | --- |
| contract_number | 96% | 91% | 91% | **99%** |
| award_amount | 92% | 95% | 95% | **95%** |
| contractor_name | 96% | 91% | 97% | **97%** |
| department | 91% | 89% | 97% | **97%** |
| revision_number | 96% | 82% | 82% | **92%** |
| end_date | 80% | 87% | 87% | **87%** |
| start_date | 90% | 85% | 85% | **85%** |

Evidence grade (v4.1, test): `high` 97% accurate (n = 917), `medium` 53% (n = 36), `low` 64% (n = 11).

**Grader fixes** (scoring was wrong, the model wasn't):
- Company names: punctuation and abbreviations ("F.H. PASCHEN, S.N. NIELSEN" = "FH PASCHEN SN NIELSEN",
  "Mfg." = "Manufacturing", "R-4" = "R4") and spacing or typos in the portal ("MC HUGH", "VIKEN DECTECTION").
  Still counted wrong: renamed companies (Harris vs L3Harris) and different joint-venture partners.
- Departments: the City reorganised departments (General Services → Fleet & Facility Management →
  Assets, Information & Services; Business & Information Services → Innovation & Technology). A PDF
  carries the name in use when it was signed. 10 test values match this way; the report counts them.
- Two rows scored as wrong where the portal has no department: now skipped.

**v4.1: code fixes, no new model run** (`src/extract/regrade.py` re-applies them to the v4 output):
- Clean-up of decoding artifacts: `{7}` → 7, `strconv232286` / `log266688` → the number, `277 50` → 27750,
  an empty string → null.
- Stacked form layout. Some summary forms print all labels in one column and all values below in the
  same order. The model read the later pairs but skipped Contract Number and Revision Number on 8
  documents. A rule pairs them by position. It runs only when the model returned nothing and the
  value has the right shape, and those values are marked `source: layout_rule`.

**Caveat.** These fixes were chosen after reading the test errors, so v4.1's test numbers are
optimistic. The v4 column is the clean held-out result. Dev scores didn't change under v4.1 (no
regression), but the honest check is a fresh sample of documents.

Remaining errors are mostly OCR-damaged dates (graded `medium`, so held for review) and real
disagreements between the PDF and the portal.

### Contract-body fields vs hand labels

60 test documents sampled at random (seed 2026); 59 labeled, 1 excluded because its text layer is
unreadable. Labels come from the full text of each document, read without the model's answers.
Rules:
- not_to_exceed_amount: the contract's overall dollar ceiling as of the document ("not to exceed",
  maximum compensation, contract limit amount, adjusted contract value; on an original, the page-1 amount).
- renewal_options_count / renewal_term_months: options the contract grants. An amendment that uses
  one up isn't an option. The standard "extend once for up to 181 days while a new contract is procured"
  holdover counts only when the contract has no other extension clause.
- payment_terms_days: days the City has to pay an invoice.
- `a|b` only where the document itself offers both readings ("a single 36-month extension or up to
  three of 12 months"). Used on 10 of 236 labels.

**Correction during labeling.** My first pass missed the contract-specific extension clause on 3
documents. The labeling view had cut it off, and only the holdover clause showed. The model quoted
the real clause. I then re-read every extension clause in all 14 original contracts in the sample,
not just those 3, and fixed the labels. The model's output pointed to the gap, but every corrected
label is checked against the source text.

| field | stated | correct | missing | wrong | recall | precision | false positives (not stated) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| renewal_options_count | 10 | 8 | 1 | 1 | 80% | 89% | 0 of 49 |
| renewal_term_months | 10 | 7 | 1 | 2 | 70% | 78% | 0 of 49 |
| not_to_exceed_amount | 52 | 12 | 37 | 3 | **23%** | 80% | 0 of 7 |
| payment_terms_days | 12 | 3 | 8 | 1 | **25%** | 60% | 1 of 47 |

**Finding: the bottleneck is passage selection, not the model.** 41 of the 47 missed values never
reached the model. The keyword selector doesn't match "Contract Limit Amount", "Adjusted Contract
Value", page 1's "Dollar Amount of Contract", or "within sixty (60) *calendar* days after receipt of
invoices". When the model does see the term, it's usually right and rarely invents one (1 false
positive in 152 "not stated" cases). Next step (v5): widen the selector and rerun the body call, then
score it on a fresh labeled sample, since these 59 documents have now been studied.
