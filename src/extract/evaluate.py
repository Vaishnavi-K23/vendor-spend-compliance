"""Score the LLM extraction and build the review gate.

Summary fields are scored automatically against the portal row for the SAME
contract and revision as the PDF (file name <contract>_<revision>.pdf):

| field           | expected value                              | match rule                         |
| contract_number | portal contract number                      | exact                              |
| revision_number | the file's revision; null on an original    | exact                              |
| contractor_name | portal vendor_name                          | names agree after normalising      |
| department      | portal department                           | names agree after normalising      |
| start_date      | portal start_date                           | exact                              |
| end_date        | portal end_date                             | exact                              |
| award_amount    | portal award, originals (revision 0) only   | within $1 (portal truncates cents) |

modification_reason has no portal equivalent and isn't scored.
Body fields are scored against hand labels in validation/llm_body_labels.csv when present.

Gate: a field reaches the dashboard only if its confidence is "high" and, for
scored summary fields, it agrees with the portal. Everything else goes to
llm.manual_review_queue with the reason.

Results go to schema llm (extraction, summary_eval, manual_review_queue) and
validation/llm_results_<split>_<version>.md.

Usage: python -m src.extract.evaluate [--model qwen2.5:7b] [--version v1] [--split dev|test|all]
"""
import argparse
import json
import re
from difflib import SequenceMatcher

import pandas as pd

from src.config import ROOT
from src.db import connect
from src.extract.run_extraction import OUT_DIR

DEV_SET = ROOT / "data" / "reference" / "llm_dev_set.csv"
BODY_LABELS = ROOT / "validation" / "llm_body_labels.csv"
RESULTS = ROOT / "validation" / "llm_results.md"

SUFFIXES = r"\b(INC|INCORPORATED|LLC|L L C|LTD|CORP|CORPORATION|CO|COMPANY|THE|LP|LLP|PC|PLLC|NFP)\b"
DEPT_NOISE = r"\b(CHICAGO|CITY|OF|DEPARTMENT|DEPT|THE|AND|OFFICE|COMMISSION|PROGRAM|PROJECT)\b"
# Abbreviations the City uses on its own forms.
DEPT_ALIASES = {"DCASE": "CULTURAL AFFAIRS SPECIAL EVENTS", "2FM": "FLEET FACILITY MANAGEMENT",
                "CDOT": "TRANSPORTATION", "DOIT": "INNOVATION TECHNOLOGY", "DPS": "PROCUREMENT SERVICES",
                "CDA": "AVIATION", "DFSS": "FAMILY SUPPORT SERVICES", "CDPH": "PUBLIC HEALTH",
                "OEMC": "EMERGENCY MANAGEMENT COMMUNICATIONS", "DWM": "WATER MANAGEMENT",
                "DSS": "STREETS SANITATION", "CPD": "POLICE", "CFD": "FIRE", "DPD": "PLANNING DEVELOPMENT",
                "DOH": "HOUSING", "BACP": "BUSINESS AFFAIRS CONSUMER PROTECTION", "DOB": "BUILDINGS",
                "AIS": "ASSETS INFORMATION SERVICES"}
WORD_ALIASES = {"MFG": "MANUFACTURING", "BROS": "BROTHERS", "INTL": "INTERNATIONAL", "SVCS": "SERVICES"}
# Departments the City merged or renamed. A PDF carries the name in use when it was signed, the
# portal the current one, so names from the same lineage count as a match (flagged in the report).
DEPT_LINEAGE = [
    ["GENERAL SERVICES", "FLEET FACILITY MANAGEMENT", "ASSETS INFORMATION SERVICES"],
    ["BUSINESS INFORMATION SERVICES", "INNOVATION TECHNOLOGY", "ASSETS INFORMATION SERVICES"],
]
TEXT_DIR = ROOT / "data" / "raw" / "pdf_text"
SUMMARY_FORM = re.compile(r"Contract\s*\(P\.?\s*O\.?\)\s*Number|Summary\s+(?:Sheet|Report)", re.I)


def name_tokens(s) -> list[str]:
    s = str(s).upper().replace("&", " AND ")
    s = re.sub(r"['’.\-]", "", s)          # F.H. -> FH, R-4 -> R4, O'HARE -> OHARE
    s = re.sub(r"[^A-Z0-9 ]", " ", s)
    s = " ".join(DEPT_ALIASES.get(t, WORD_ALIASES.get(t, t)) for t in s.split())
    s = re.sub(SUFFIXES, " ", s)
    return [t[:-1] if len(t) > 4 and t.endswith("S") else t for t in s.split()]  # SERVICES = SERVICE


def norm_name(s) -> set:
    return set(name_tokens(s))


def names_agree(a, b, noise: str | None = None) -> bool:
    ta, tb = norm_name(a), norm_name(b)
    if noise:
        ta = {t for t in ta if not re.fullmatch(noise, t)}
        tb = {t for t in tb if not re.fullmatch(noise, t)}
    if not ta or not tb:
        return False
    if len(ta & tb) / min(len(ta), len(tb)) >= 0.75:
        return True
    if noise:
        return False
    # Company names: same letters with spacing or a typo ("MC HUGH", portal's "VIKEN DECTECTION").
    ca, cb = sorted(("".join(name_tokens(a)), "".join(name_tokens(b))), key=len)
    return (len(ca) >= 8 and ca in cb) or SequenceMatcher(None, ca, cb).ratio() >= 0.9


def same_lineage(a, b) -> bool:
    return any(any(names_agree(a, x, DEPT_NOISE) for x in g) and any(names_agree(b, y, DEPT_NOISE) for y in g)
               for g in DEPT_LINEAGE)


def load_extractions(model: str, version: str) -> pd.DataFrame:
    path = OUT_DIR / f"{model.replace(':', '_')}__{version}.jsonl"
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        contract, revision = r["file"][:-4].rsplit("_", 1)
        for part in ("summary", "body"):
            for field, f in r[part].items():
                rows.append({
                    "file": r["file"], "contract_number": contract, "revision_number": revision,
                    "kind": r["kind"], "part": part, "field": field,
                    "value": None if f.get("value") is None else str(f["value"]),
                    "quote": f.get("quote"), "page": f.get("page"), "confidence": f["confidence"],
                    "model": r["model"], "prompt_version": r["prompt_version"],
                    "seconds": r["stats"]["summary"]["seconds"] + r["stats"]["body"]["seconds"],
                })
    return pd.DataFrame(rows)


def score_summary(ex: pd.DataFrame, portal: pd.DataFrame) -> pd.DataFrame:
    portal = portal.rename(columns={"start_date": "start_date_portal", "end_date": "end_date_portal"})
    s = ex[ex.part.eq("summary") & ex.field.ne("modification_reason")].merge(
        portal, on=["contract_number", "revision_number"], how="left")
    out = []
    for r in s.itertuples():
        v = None if pd.isna(r.value) else str(r.value)
        note = ""
        if r.field == "contract_number":
            expected, ok = r.contract_number, v is not None and v.strip() == r.contract_number
        elif r.field == "revision_number":
            expected = None if r.revision_number == "0" else r.revision_number
            ok = (v is None and expected is None) or (v is not None and v.strip().lstrip("0") == str(expected or "").lstrip("0") and expected is not None)
        elif r.field == "contractor_name":
            # a revision can list several vendors (joint ventures): any of them counts
            names = r.vendor_name if isinstance(r.vendor_name, list) else []
            expected = " | ".join(names) or None
            ok = v is not None and any(names_agree(v, n) for n in names)
        elif r.field == "department":
            expected = None if pd.isna(r.department) else r.department
            ok = v is not None and expected is not None and names_agree(v, expected, DEPT_NOISE)
            if not ok and v is not None and expected is not None and same_lineage(v, expected):
                ok, note = True, "renamed department"
        elif r.field in ("start_date", "end_date"):
            exp = getattr(r, f"{r.field}_portal")
            expected = None if pd.isna(exp) else str(exp)[:10]
            ok = v is not None and expected is not None and v[:10] == expected
        elif r.field == "award_amount":
            if r.revision_number != "0" or pd.isna(r.award_amount) or float(r.award_amount) <= 0:
                continue  # modification forms carry no amount; nothing to score against
            expected = float(r.award_amount)
            try:
                ok = v is not None and abs(float(v) - expected) <= 1
            except ValueError:
                ok = False
        if expected is None and r.field != "revision_number":
            continue  # portal has no value
        outcome = "correct" if ok else ("missing" if v is None else "wrong")
        out.append({"file": r.file, "field": r.field, "kind": r.kind, "contract_type": r.contract_type,
                    "value": v, "expected": None if expected is None else str(expected),
                    "confidence": r.confidence, "outcome": outcome, "note": note})
    return pd.DataFrame(out)


def score_body(ex: pd.DataFrame) -> pd.DataFrame:
    if not BODY_LABELS.exists():
        return pd.DataFrame()
    labels = pd.read_csv(BODY_LABELS, dtype=str)
    labels = labels[labels.label_status.eq("labeled")]
    b = ex[ex.part.eq("body")].merge(labels[["file", "field", "true_value"]], on=["file", "field"])

    def outcome(v, t) -> str:
        v = None if pd.isna(v) else v
        if pd.isna(t) or t == "":  # the document doesn't state this term
            return "correct_absent" if v is None else "false_positive"
        if v is None:
            return "missing"
        try:  # "a|b": the document offers both (e.g. "a single 36-month or up to three 12-month extensions")
            return "correct" if any(abs(float(v) - float(x)) < 0.5 for x in t.split("|")) else "wrong"
        except ValueError:
            return "wrong"

    b["outcome"] = [outcome(v, t) for v, t in zip(b.value, b.true_value)]
    return b


def summarise_body(b: pd.DataFrame) -> pd.DataFrame:
    """Recall on documents that state the term; false positives on documents that don't."""
    g = b.groupby("field").outcome.value_counts().unstack(fill_value=0)
    for c in ("correct", "wrong", "missing", "false_positive", "correct_absent"):
        g[c] = g.get(c, 0)
    g["stated"] = g[["correct", "wrong", "missing"]].sum(axis=1)
    g["recall"] = g.correct / g.stated.where(lambda x: x > 0)
    g["precision"] = g.correct / (g.correct + g.wrong + g.false_positive).where(lambda x: x > 0)
    g["not_stated"] = g.false_positive + g.correct_absent
    return g[["stated", "correct", "wrong", "missing", "recall", "precision", "not_stated", "false_positive"]]


def summarise(scored: pd.DataFrame) -> pd.DataFrame:
    g = scored.groupby("field").outcome.value_counts().unstack(fill_value=0)
    for c in ("correct", "wrong", "missing"):
        g[c] = g.get(c, 0)
    g["n"] = g[["correct", "wrong", "missing"]].sum(axis=1)
    g["accuracy"] = g.correct / g.n
    g["precision"] = g.correct / (g.correct + g.wrong).where(lambda x: x > 0)
    g["coverage"] = (g.correct + g.wrong) / g.n
    return g[["n", "correct", "wrong", "missing", "accuracy", "precision", "coverage"]]


def pct(x) -> str:
    return "–" if pd.isna(x) else f"{x:.0%}"


def table(df: pd.DataFrame) -> str:
    cols = list(df.columns)
    lines = ["| " + " | ".join([df.index.name or ""] + cols) + " |", "|" + "---|" * (len(cols) + 1)]
    for idx, row in df.iterrows():
        vals = [pct(v) if c in ("accuracy", "precision", "coverage", "share", "recall") else str(v) for c, v in row.items()]
        lines.append("| " + " | ".join([str(idx)] + vals) + " |")
    return "\n".join(lines)


def main(model: str, version: str, split: str) -> None:
    ex = load_extractions(model, version)
    dev = set(pd.read_csv(DEV_SET).file)
    ex["split"] = ex.file.map(lambda f: "dev" if f in dev else "test")
    if split != "all":
        ex = ex[ex.split.eq(split)]

    with connect() as conn:
        portal = pd.read_sql(
            "select contract_number, revision_number, contract_type, vendor_name, department, "
            "start_date, end_date, award_amount from stg.contracts", conn)
    # A revision can list several vendors (joint ventures): keep all their names.
    names = portal.groupby(["contract_number", "revision_number"]).vendor_name.agg(lambda x: sorted(set(x.dropna())))
    portal = portal.drop_duplicates(["contract_number", "revision_number"]).drop(columns="vendor_name") \
        .merge(names.reset_index(), on=["contract_number", "revision_number"])

    # Documents whose first page isn't the City's summary form have nothing to score summary fields against.
    no_form = {f for f in ex.file.unique()
               if not SUMMARY_FORM.search(json.loads((TEXT_DIR / f"{f[:-4]}.json").read_text(encoding="utf-8"))
                                          ["page_text"][0]["text"][:3000])}

    summary = score_summary(ex[~ex.file.isin(no_form)], portal)
    body = score_body(ex)
    docs = ex.file.nunique()

    # Gate: high confidence and (for scored summary fields) agrees with the portal.
    ex = ex.merge(summary[["file", "field", "outcome"]], on=["file", "field"], how="left")
    reason = pd.Series("", index=ex.index)
    reason[ex.confidence.eq("low")] = "quote not found in document"
    reason[ex.confidence.eq("medium")] = "value not confirmed by its quote"
    reason[ex.outcome.eq("wrong")] = "disagrees with portal"
    ex["review_reason"] = reason.where(ex.confidence.ne("not_found"), "")
    ex["passes_gate"] = ex.confidence.eq("high") & ex.outcome.fillna("unscored").ne("wrong")
    queue = ex[ex.review_reason.ne("")]

    lines = [f"# LLM extraction results: {model}, prompt {version}, {split} split", "",
             f"{docs} documents ({ex.drop_duplicates('file').kind.value_counts().to_dict()}), "
             f"median {ex.drop_duplicates('file').seconds.median():.0f}s per document on the CPU.", "",
             "## Summary fields vs the portal (same contract and revision)", "",
             "accuracy = correct / scored; precision = correct / values extracted; coverage = values extracted / scored.",
             f"{len(no_form)} documents have no summary form on page 1 and aren't scored here: {sorted(no_form)}.", "",
             table(summarise(summary)), "",
             "### By document kind", ""]
    for kind, g in summary.groupby("kind"):
        lines += [f"**{kind}** ({g.file.nunique()} documents): accuracy {pct((g.outcome == 'correct').mean())}", ""]
    lines += ["### Does the evidence grade predict errors?", "",
              "Accuracy of scored summary fields by confidence grade. If the gate works, `high` is far more accurate.", ""]
    cal = summary.groupby("confidence").outcome.agg(n="size", accuracy=lambda o: (o == "correct").mean())
    lines += [table(cal), ""]
    renamed = summary.note.eq("renamed department").sum()
    if renamed:
        lines += [f"{renamed} department values count as correct because the PDF names an earlier form of the "
                  "portal's department (City reorganisations: General Services -> Fleet & Facility Management -> "
                  "Assets, Information & Services; Business & Information Services -> Innovation & Technology).", ""]
    if not body.empty:
        lines += ["## Contract-body fields vs hand labels", "",
                  f"{body.file.nunique()} test documents labeled by hand from their full text "
                  "(`validation/llm_body_labels.csv`). stated = documents that state the term; "
                  "recall = correct / stated; precision = correct / values extracted; "
                  "false_positive = a value extracted where the document states none.", "",
                  table(summarise_body(body)), ""]
    else:
        lines += ["## Contract-body fields", "", "Not scored yet: hand labels go in `validation/llm_body_labels.csv`.", ""]
    found = ex[ex.part.eq("body") & ex.confidence.ne("not_found")]
    lines += ["### Body fields found", "",
              table(found.groupby("field").confidence.value_counts().unstack(fill_value=0)), "",
              "## Review gate", "",
              f"{int(ex.passes_gate.sum())} of {int(ex.confidence.ne('not_found').sum())} extracted values pass the gate; "
              f"{len(queue)} go to `llm.manual_review_queue`:", "",
              table(queue.review_reason.value_counts().rename("count").to_frame()), "",
              "## Errors (summary fields)", "",
              "| file | field | extracted | portal | confidence |", "|---|---|---|---|---|"]
    for r in summary[summary.outcome.ne("correct")].itertuples():
        lines.append(f"| {r.file} | {r.field} | {r.value} | {r.expected} | {r.confidence} |")
    out = RESULTS.with_name(f"llm_results_{split}_{version}.md")
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(out.read_text(encoding="utf-8")[:3000])

    with connect() as conn:
        conn.execute("create schema if not exists llm")
        for name, df in (("extraction", ex), ("summary_eval", summary), ("manual_review_queue", queue)):
            conn.execute(f"drop table if exists llm.{name}")
            cols = ", ".join(f'"{c}" text' for c in df.columns)
            conn.execute(f"create table llm.{name} ({cols})")
            with conn.cursor().copy(f"copy llm.{name} from stdin") as cp:
                for row in df.astype(object).where(df.notna(), None).itertuples(index=False):
                    cp.write_row([None if v is None else str(v) for v in row])
        conn.commit()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="qwen2.5:7b")
    ap.add_argument("--version", default="v1")
    ap.add_argument("--split", default="all", choices=["dev", "test", "all"])
    a = ap.parse_args()
    main(a.model, a.version, a.split)
