"""Run the local LLM over the sampled PDFs and store every extracted field with its evidence.

Two calls per document:
- summary: page 1 (the City's summary form) -> SUMMARY_FIELDS
- body: keyword-selected passages from all pages -> BODY_FIELDS

Each field keeps its value, the model's quote and page, and an evidence-based
confidence that doesn't trust the model's own opinion:
- high:   the quote is found in the source text and contains the value
- medium: the quote is found, but the value can't be confirmed inside it
          (e.g. a date the model reformatted, a number written in words)
- low:    a value without a quote, or a quote that isn't in the source (possible invention)
Fields the model left empty are "not_found".

Output: data/extract/<model>__<prompt_version>.jsonl, one line per document.
Documents already in that file are skipped, so the run can be stopped and resumed.

Usage: python -m src.extract.run_extraction [--model qwen2.5:7b] [--limit N] [--files a.pdf b.pdf]
"""
import argparse
import ctypes
import json
import sys
import re
import time
from difflib import SequenceMatcher

import requests

from src.config import ROOT
from src.extract.pdf_text import TEXT_DIR
from src.extract.prompts import (BODY_PROMPT, BODY_SCHEMA, PROMPT_VERSION, SUMMARY_PROMPT,
                                 SUMMARY_SCHEMA, select_passages)

OLLAMA = "http://localhost:11434/api/chat"
OUT_DIR = ROOT / "data" / "extract"
PAGE1_MAX_CHARS = 6000


def ask(model: str, prompt: str, schema: dict) -> tuple[dict, dict]:
    """One call; if the model loops until the token cap (cut-off JSON), retry once with a repeat penalty."""
    seconds, retried = 0.0, False
    for options in ({}, {"repeat_penalty": 1.3}):
        resp = requests.post(OLLAMA, timeout=900, json={
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "format": schema,
            "stream": False,
            "options": {"temperature": 0, "seed": 42, "num_ctx": 8192, "num_predict": 1500, **options},
        })
        resp.raise_for_status()
        body = resp.json()
        seconds += body.get("total_duration", 0) / 1e9
        stats = {"prompt_tokens": body.get("prompt_eval_count"), "output_tokens": body.get("eval_count"),
                 "seconds": round(seconds, 1), "retried": retried}
        try:
            return json.loads(body["message"]["content"]), stats
        except json.JSONDecodeError:
            retried = True
    raise ValueError("model output was not valid JSON after a retry")


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9$.,/]+", " ", s.lower()).strip()


def quote_in_source(quote: str, source: str) -> bool:
    """Exact match after normalising, else 90% of the quote found in runs of 4+ characters (OCR noise)."""
    q, s = norm(quote), norm(source)
    if not q:
        return False
    if q in s:
        return True
    blocks = SequenceMatcher(None, q, s, autojunk=False).get_matching_blocks()
    return sum(b.size for b in blocks if b.size >= 4) / len(q) >= 0.9


def value_in_quote(value, quote: str) -> bool:
    if isinstance(value, (int, float)):
        digits = re.sub(r"\D", "", quote)
        whole = str(int(value)) if float(value).is_integer() else f"{value:.2f}".replace(".", "")
        return whole in digits
    if isinstance(value, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        # The model reformats dates, so look for the same date in the ways documents write it.
        y, m, d = (int(x) for x in value.split("-"))
        months = ["january", "february", "march", "april", "may", "june", "july", "august",
                  "september", "october", "november", "december"]
        forms = [f"{m}/{d}/{y}", f"{m:02d}/{d:02d}/{y}", f"{m}/{d}/{y % 100:02d}", f"{m:02d}/{d:02d}/{y % 100:02d}",
                 f"{m}-{d}-{y}", f"{m:02d}-{d:02d}-{y}", f"{y}-{m:02d}-{d:02d}",
                 f"{months[m - 1]} {d}, {y}", f"{months[m - 1]} {d} {y}", f"{d} {months[m - 1]} {y}",
                 f"{d}-{months[m - 1][:3]}-{y}"]
        q = re.sub(r"\s+", " ", quote.lower())
        return any(f in q for f in forms)
    return norm(str(value)) in norm(quote)


# A value only counts if its quote carries the field's label. Catches the model reading the
# neighbouring number (v1: "Specification Number: 547589A" returned as the revision number).
# Prompt rules didn't fix this (v2/v3 made it worse), so it's enforced here.
LABEL_REQUIRED = {"revision_number": re.compile(r"revision|rev\b", re.I)}

# Clean-up of artifacts from grammar-constrained decoding (added in v4.1, after the v4 test run):
# "strconv232286", "log266688", "{7}", "277 50", "" -> the ID itself, or null.
ARTIFACT_PREFIX = re.compile(r"^(?:strconv|log)", re.I)


def clean(name: str, value):
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None
        if name == "contract_number":
            v = re.sub(r"(?<=\d)\s+(?=\d)", "", ARTIFACT_PREFIX.sub("", value))
            m = re.search(r"\b[A-Z]?\d{3,}\b", v, re.I)
            return m.group().upper() if m else None
        if name == "revision_number":
            m = re.search(r"\d+", value)
            return str(int(m.group())) if m else None
    return value


STACKED_LABELS = {"contract_number": r"Contract\s*\(P\.?\s*O\.?\)\s*Number",
                  "revision_number": r"Modification\s+Revision\s+Number"}
STACKED_PATTERN = {"contract_number": r"[A-Z]?\d{3,}", "revision_number": r"\d{1,3}"}


def stacked_form_values(page1: str) -> dict:
    """Some summary forms print every label in one column, then every value in the same order:

        Contract (PO) Number:          <- run of label-only lines
        Modification Revision Number:
        Specification Number:
        108299                         <- values, same order
        3
        650026

    The model reads the later pairs but often skips the first ones (v4 test set). Pair them by
    position; only used when the model returned nothing, and only if the value has the right shape.
    """
    lines = [l.strip() for l in page1.splitlines() if l.strip()]
    for i, line in enumerate(lines):
        if not re.fullmatch(r"[A-Za-z()./ ]+:", line):
            continue
        j = i
        while j < len(lines) and re.fullmatch(r"[A-Za-z()./ ]+:", lines[j]):
            j += 1
        labels, values = lines[i:j], lines[j:j + (j - i)]
        if len(labels) < 3 or len(values) < len(labels):
            continue
        found = {}
        for name, label in STACKED_LABELS.items():
            for k, lab in enumerate(labels):
                if re.fullmatch(label + r"\s*:", lab, re.I) and re.fullmatch(STACKED_PATTERN[name], values[k]):
                    found[name] = {"value": values[k], "quote": f"{lab} {values[k]}", "source": "layout_rule"}
        return found
    return {}


def fill_from_layout(summary: dict, page1: str) -> dict:
    for name, f in stacked_form_values(page1).items():
        if clean(name, summary.get(name, {}).get("rejected_value", summary.get(name, {}).get("value"))) is None:
            summary[name] = f
    return summary


def grade(fields: dict, source: str) -> dict:
    out = {}
    for name, f in fields.items():
        if f.get("source") == "layout_rule":  # label and value both read off the page by position
            out[name] = {**f, "confidence": "high"}
            continue
        raw = f.get("rejected_value", f.get("value"))  # regrading starts from the model's own value
        f = {k: v for k, v in f.items() if k not in ("rejected_value", "rejected_reason", "confidence")}
        f["value"] = clean(name, raw)
        if f["value"] != raw:
            f["raw_value"] = raw
        value, quote = f["value"], f.get("quote") or ""
        if value is not None and name in LABEL_REQUIRED and not LABEL_REQUIRED[name].search(quote):
            f = {**f, "value": None, "rejected_value": value, "rejected_reason": "quote lacks the field label"}
            value = None
        if value is None:
            conf = "not_found"
        elif not quote or not quote_in_source(quote, source):
            conf = "low"
        elif value_in_quote(value, quote):
            conf = "high"
        else:
            conf = "medium"
        out[name] = {**f, "confidence": conf}
    return out


def run_doc(model: str, doc: dict) -> dict:
    page1 = doc["page_text"][0]["text"][:PAGE1_MAX_CHARS] if doc["page_text"] else ""
    summary, s_stats = ask(model, SUMMARY_PROMPT.format(text=page1), SUMMARY_SCHEMA)

    passages = select_passages(doc["page_text"])
    if passages:
        body, b_stats = ask(model, BODY_PROMPT.format(text=passages), BODY_SCHEMA)
    else:
        body = {k: {"value": None, "quote": None, "page": None} for k in BODY_SCHEMA["properties"]}
        b_stats = {"prompt_tokens": 0, "output_tokens": 0, "seconds": 0}

    return {
        "file": doc["file"], "kind": doc["kind"], "pages": doc["pages"],
        "pages_ocr": doc["pages_ocr"], "pages_unread": doc["pages_unread"],
        "model": model, "prompt_version": PROMPT_VERSION,
        "passage_chars": len(passages),
        "summary": grade(fill_from_layout(summary, page1), page1), "body": grade(body, passages),
        "stats": {"summary": s_stats, "body": b_stats},
    }


def main(model: str, limit: int | None, files: list[str] | None) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"{model.replace(':', '_')}__{PROMPT_VERSION}.jsonl"
    done = set()
    if out.exists():
        done = {json.loads(line)["file"] for line in out.read_text(encoding="utf-8").splitlines()}

    paths = sorted(TEXT_DIR.glob("*.json"))
    if files:
        paths = [TEXT_DIR / f"{f.removesuffix('.pdf')}.json" for f in files]
    todo = [p for p in paths if f"{p.stem}.pdf" not in done][:limit]
    print(f"{len(done)} done, {len(todo)} to run -> {out}", flush=True)
    if sys.platform == "win32":
        # Keep Windows from sleeping mid-run (v1 lost hours to sleep). Released when the process exits.
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x00000001)  # ES_CONTINUOUS | ES_SYSTEM_REQUIRED

    for i, path in enumerate(todo, 1):
        doc = json.loads(path.read_text(encoding="utf-8"))
        start = time.time()
        try:
            rec = run_doc(model, doc)
        except Exception as e:  # log and move on; the file can be rerun later
            print(f"[{i}/{len(todo)}] {doc['file']}: ERROR {str(e)[:200]}", flush=True)
            continue
        with out.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")
        found = sum(v["confidence"] != "not_found" for v in rec["body"].values())
        print(f"[{i}/{len(todo)}] {doc['file']}: {time.time() - start:.0f}s, "
              f"{found}/4 body fields found", flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="qwen2.5:7b")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--files", nargs="*")
    a = ap.parse_args()
    main(a.model, a.limit, a.files)
