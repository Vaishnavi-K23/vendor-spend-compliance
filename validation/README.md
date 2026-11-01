# Phase 4: hand validation

The exception rules have no answer key, so their precision is measured by reviewing random samples by hand. The miss rate is estimated from samples the rules did **not** flag.

## Files

- `review_workbook.xlsx`: one sheet per sample, with evidence pre-filled. The yellow columns are yours.
- `results.md`: precision and miss rates with 95% intervals, written by the scorer.

## How to review

1. Open `review_workbook.xlsx`. The `README` sheet states the question for each sample and its reason codes.
2. For each row, use the evidence columns: both payments for duplicates, contract dates and the latest revision PDF for contract rules, and payee classification for off-contract payments. For PDF links, the URL in `src/config.py` (`PDF_URL`) fetches the file directly. Fill in:
   - **verdict**: `true_issue`, `false_positive` or `unclear` (dropdown)
   - **reason**: one code from the README sheet
   - **notes**: what you saw, in a phrase. These notes become the interview story.
3. Score it: `python -m src.validation.score_review`.
4. If a rule's precision is low, change the rule (`sql/07_mart_payments.sql`), rebuild (`python -m src.model.build_model`), and record what changed and why in `docs/kpi-dictionary.md`. Don't redraw the samples. Re-score the same rows so the before/after comparison is fair.

## Samples

| Sheet | Rows | Drawn from |
| --- | --- | --- |
| duplicates | 40 | random flagged possible duplicates |
| paid_after_end | 40 | one random flagged payment per contract |
| over_award | 30 | random contracts with over-award dollars |
| off_contract | 50 | random off-contract payments (count-weighted) |
| off_contract_top_payees | 25 | the 25 largest off-contract payees ($591M, dollar-weighted) |
| missed_duplicates | 30 | **unflagged**: same-amount pairs excluded as recurring charges |
| missed_after_end | 30 | **unflagged**: payments 1–90 days after end date (grace window) |

Samples are deterministic (md5 of the ID with a fixed seed), so `build_review --force` redraws the same rows. It also erases verdicts, so it refuses to run without `--force`.

## Time budget

About 3–4 hours in total: 1–2 minutes a row for duplicates and off-contract, and 5 minutes a row where a PDF needs opening (paid after end, over award). For interview purposes, 20 rows per sheet with notes is enough to report precision with an honest interval.
