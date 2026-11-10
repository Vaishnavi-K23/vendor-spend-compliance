"""Re-apply value clean-up and evidence grading to an existing run, without calling the model again.

The model's answers are unchanged; only the code that cleans and grades them is newer.
Writes data/extract/<model>__<new version>.jsonl.

Usage: python -m src.extract.regrade --source v4 --target v4.1
"""
import argparse
import json

from src.extract.pdf_text import TEXT_DIR
from src.extract.prompts import select_passages
from src.extract.run_extraction import OUT_DIR, PAGE1_MAX_CHARS, fill_from_layout, grade


def main(model: str, source: str, target: str) -> None:
    stem = model.replace(":", "_")
    lines = (OUT_DIR / f"{stem}__{source}.jsonl").read_text(encoding="utf-8").splitlines()
    out = []
    for line in lines:
        rec = json.loads(line)
        doc = json.loads((TEXT_DIR / f"{rec['file'][:-4]}.json").read_text(encoding="utf-8"))
        page1 = doc["page_text"][0]["text"][:PAGE1_MAX_CHARS] if doc["page_text"] else ""
        rec["summary"] = grade(fill_from_layout(rec["summary"], page1), page1)
        rec["body"] = grade(rec["body"], select_passages(doc["page_text"]))
        rec["postprocess"] = target
        out.append(json.dumps(rec))
    path = OUT_DIR / f"{stem}__{target}.jsonl"
    path.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"{len(out)} documents regraded -> {path}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="qwen2.5:7b")
    ap.add_argument("--source", required=True)
    ap.add_argument("--target", required=True)
    a = ap.parse_args()
    main(a.model, a.source, a.target)
