"""Draw random samples of flagged (and unflagged) payments and write the review workbook.

Phase 4: the exception rules have no planted answers, so their precision is
measured by hand. Each sheet holds one sample with the evidence a reviewer needs;
the reviewer fills in verdict / reason / notes, then runs
`python -m src.validation.score_review`.

Samples are deterministic (md5 of id + seed), so rerunning gives the same rows.
The workbook is never overwritten once it exists, so reviews can't be lost.

Usage: python -m src.validation.build_review [--force]
"""
import argparse

import pandas as pd
from openpyxl import load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation

from src.config import ROOT
from src.db import connect

VALIDATION_DIR = ROOT / "validation"
WORKBOOK = VALIDATION_DIR / "review_workbook.xlsx"
SEED = "phase4"

VERDICTS = ["true_issue", "false_positive", "unclear"]
REVIEW_COLUMNS = ["verdict", "reason", "notes"]

# Each sample: sheet name, what a reviewer decides, and the query.
# Contract rules sample one payment per contract, so one big contract can't fill a sheet.
SAMPLES = {
    "duplicates": (
        "Is the flagged payment a second payment for the same thing? "
        "Compare with the earlier payment (same payee and amount within 7 days, different voucher).",
        f"""
        with flagged as (
            select e.*, md5(e.payment_id::text || '{SEED}') as r
            from dw.mart_payment_exceptions e where e.exception_type = 'possible_duplicate'
        )
        select f.payment_id, f.payment_date, f.amount, f.voucher_number, f.payee_name, f.payee_type,
               f.contract_number, c.description as contract_description,
               prev.payment_date as earlier_date, prev.voucher_number as earlier_voucher,
               (select count(*) from dw.fact_payment o where o.payee_key = f.payee_key
                  and o.payment_date between f.payment_date - 30 and f.payment_date + 30) as payee_payments_pm30d
        from flagged f
        left join dw.dim_contract c using (contract_number)
        left join lateral (
            select p.payment_date, p.voucher_number from dw.fact_payment p
            where p.payee_key = f.payee_key and p.amount = f.amount and p.payment_id <> f.payment_id
              and p.payment_date between f.payment_date - 7 and f.payment_date
            order by p.payment_date desc limit 1) prev on true
        order by f.r limit 40""",
    ),
    "paid_after_end": (
        "Was the contract genuinely over when this was paid, or was it extended / is this a late invoice "
        "for work done in term? Check the latest revision PDF for a time extension.",
        f"""
        with one_per_contract as (
            select distinct on (contract_number) e.*, md5(e.contract_number || '{SEED}') as r
            from dw.mart_payment_exceptions e where e.exception_type = 'paid_after_end_date'
            order by contract_number, md5(e.payment_id::text || '{SEED}')
        )
        select o.payment_id, o.payment_date, o.amount, o.payee_name, o.contract_number,
               c.description as contract_description, c.contract_type, c.current_end_date,
               o.days_after_end, c.revision_count, c.last_approval_date,
               s.paid_after_end_payments as contract_payments_after_end,
               s.paid_after_end_amount as contract_amount_after_end,
               (select r.pdf_url from dw.fact_contract_revision r where r.contract_number = o.contract_number
                  and r.pdf_url is not null order by r.revision_order desc limit 1) as latest_revision_pdf
        from one_per_contract o
        join dw.dim_contract c using (contract_number)
        join dw.mart_contract_spend s using (contract_number)
        order by o.r limit 40""",
    ),
    "over_award": (
        "Was the contract really paid beyond its total award, or is an amendment missing from the data / "
        "is the award an estimate? Check the latest revision PDF for the current contract value.",
        f"""
        select s.contract_number, s.vendor_name, s.description as contract_description, s.contract_type,
               s.procurement_channel, s.procurement_type, s.original_award, s.cumulative_award,
               s.paid_to_date, s.pct_of_award, s.over_award_amount_2025_plus, s.revision_count,
               s.start_date, s.current_end_date,
               (select r.pdf_url from dw.fact_contract_revision r where r.contract_number = s.contract_number
                  and r.pdf_url is not null order by r.revision_order desc limit 1) as latest_revision_pdf
        from dw.mart_contract_spend s
        where s.over_award_amount_2025_plus > 0
        order by md5(s.contract_number || '{SEED}') limit 30""",
    ),
    "off_contract": (
        "Is this a purchase of goods/services made without a contract? If the payee type is wrong "
        "(e.g. a refund, settlement or pass-through), mark false_positive with reason wrong_payee_type.",
        f"""
        select e.payment_id, e.payment_date, e.amount, e.payee_name, e.payee_type,
               v.classification_source, v.classification_confidence, v.has_contract_record,
               e.off_contract_vendor_has_active_contract,
               (select string_agg(c.contract_number || ' (' || left(coalesce(c.description, ''), 50) || ')', '; ')
                  from dw.dim_contract c where c.vendor_key = e.vendor_key
                  and e.payment_date between c.start_date and c.current_end_date) as active_contracts
        from dw.mart_payment_exceptions e
        join dw.dim_vendor v using (vendor_key)
        where e.exception_type = 'off_contract'
        order by md5(e.payment_id::text || '{SEED}') limit 50""",
    ),
    # The random sample above is count-weighted (mostly small payments); this sheet is
    # dollar-weighted: every one of the largest off-contract payees, reviewed once each.
    "off_contract_top_payees": (
        "Is this payee's off-contract spend purchasing without a contract? For insurance brokers: "
        "are the payments premiums passed through to insurers (not maverick spend) or broker services?",
        """
        select v.vendor_name as payee, e.payee_type, v.classification_source, v.classification_confidence,
               count(*) as payments, sum(e.amount) as off_contract_amount_2022_plus,
               sum(e.amount) filter (where e.payment_year >= 2025) as off_contract_amount_2025_plus,
               min(e.payment_date) as first_payment, max(e.payment_date) as last_payment,
               bool_or(e.off_contract_vendor_has_active_contract) as ever_had_active_contract,
               (select string_agg(distinct c.contract_number, ', ') from dw.dim_contract c
                  where c.vendor_key = e.vendor_key) as vendor_contracts
        from dw.mart_payment_exceptions e
        join dw.dim_vendor v using (vendor_key)
        where e.exception_type = 'off_contract'
        group by v.vendor_name, e.payee_type, v.classification_source, v.classification_confidence, e.vendor_key
        order by sum(e.amount) desc limit 25""",
    ),
    "missed_duplicates": (
        "UNFLAGGED: same payee and amount within 7 days on different vouchers, but excluded because the "
        "pair recurs 4+ times. Is it really a recurring charge, or a duplicate the exclusion hid?",
        f"""
        with pairs as (
            select e.*, lag(e.payment_date) over w as prev_date, lag(e.voucher_number) over w as prev_voucher,
                   count(*) over (partition by e.payee_key, e.amount) as times_amount_paid
            from dw.mart_payment_exceptions e where e.amount > 0
            window w as (partition by e.payee_key, e.amount order by e.payment_date, e.payment_id)
        )
        select payment_id, payment_date, amount, voucher_number, payee_name, contract_number,
               prev_date as earlier_date, prev_voucher as earlier_voucher, times_amount_paid
        from pairs
        where prev_date >= payment_date - 7 and prev_voucher <> voucher_number
          and times_amount_paid >= 4 and not is_possible_duplicate
        order by md5(payment_id::text || '{SEED}') limit 30""",
    ),
    "missed_after_end": (
        "UNFLAGGED: paid 1-90 days after the end date (inside the grace period). Is this a normal late "
        "invoice for work done in term, or should it have been flagged?",
        f"""
        select e.payment_id, e.payment_date, e.amount, e.payee_name, e.contract_number,
               c.description as contract_description, c.current_end_date, e.days_after_end,
               (select r.pdf_url from dw.fact_contract_revision r where r.contract_number = e.contract_number
                  and r.pdf_url is not null order by r.revision_order desc limit 1) as latest_revision_pdf
        from dw.mart_payment_exceptions e
        join dw.dim_contract c using (contract_number)
        where e.days_after_end between 1 and 90
        order by md5(e.payment_id::text || '{SEED}') limit 30""",
    ),
}

REASONS = {
    "duplicates": "duplicate_paid | separate_invoice_same_amount | installment_or_split | correction_or_reissue | other",
    "paid_after_end": "work_after_term | extension_not_in_data | late_invoice_for_term_work | retainage_or_closeout | wrong_end_date | other",
    "over_award": "overspend | amendment_missing_from_data | award_is_estimate | multi_year_or_renewal | other",
    "off_contract": "purchase_without_contract | wrong_payee_type | covered_by_other_agreement | pass_through | other",
    "off_contract_top_payees": "purchase_without_contract | premium_pass_through | wrong_payee_type | covered_by_other_agreement | other",
    "missed_duplicates": "recurring_charge_ok | hidden_duplicate | other",
    "missed_after_end": "late_invoice_ok | should_flag | extension_not_in_data | other",
}


def read_samples(conn) -> dict[str, pd.DataFrame]:
    out = {}
    for sheet, (_, sql) in SAMPLES.items():
        cur = conn.execute(sql)
        df = pd.DataFrame(cur.fetchall(), columns=[c.name for c in cur.description])
        for col in REVIEW_COLUMNS:
            df[col] = ""
        out[sheet] = df
        print(f"{sheet}: {len(df)} rows")
    return out


def write_workbook(samples: dict[str, pd.DataFrame]) -> None:
    VALIDATION_DIR.mkdir(exist_ok=True)
    instructions = pd.DataFrame(
        [(s, SAMPLES[s][0], REASONS[s]) for s in SAMPLES],
        columns=["sheet", "question", "reason codes"])
    with pd.ExcelWriter(WORKBOOK, engine="openpyxl") as xw:
        instructions.to_excel(xw, sheet_name="README", index=False)
        for sheet, df in samples.items():
            df.to_excel(xw, sheet_name=sheet, index=False)

    wb = load_workbook(WORKBOOK)
    review_fill = PatternFill("solid", fgColor="FFF4CC")
    for ws in wb.worksheets:
        for cell in ws[1]:
            cell.font = Font(bold=True)
        ws.freeze_panes = "B2"
        for col in ws.columns:
            width = max(len(str(c.value or "")) for c in col[:60])
            ws.column_dimensions[col[0].column_letter].width = min(max(width + 2, 10), 60)
        if ws.title == "README":
            for row in ws.iter_rows(min_row=2):
                for cell in row:
                    cell.alignment = Alignment(wrap_text=True, vertical="top")
            continue
        headers = [c.value for c in ws[1]]
        verdict_col = ws.cell(row=1, column=headers.index("verdict") + 1).column_letter
        dv = DataValidation(type="list", formula1='"' + ",".join(VERDICTS) + '"', allow_blank=True)
        ws.add_data_validation(dv)
        dv.add(f"{verdict_col}2:{verdict_col}{ws.max_row}")
        for name in REVIEW_COLUMNS:
            idx = headers.index(name) + 1
            for row in range(1, ws.max_row + 1):
                ws.cell(row=row, column=idx).fill = review_fill
    wb.save(WORKBOOK)
    print(f"wrote {WORKBOOK}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="overwrite an existing workbook (loses reviews)")
    args = ap.parse_args()
    if WORKBOOK.exists() and not args.force:
        raise SystemExit(f"{WORKBOOK} exists; refusing to overwrite reviews (use --force)")
    with connect() as conn:
        write_workbook(read_samples(conn))
