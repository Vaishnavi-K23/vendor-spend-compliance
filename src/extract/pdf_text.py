"""Extract per-page text from the sampled contract PDFs, with OCR for scanned pages.

A page keeps its embedded text when it has at least MIN_CHARS characters;
otherwise it is rendered and read with Tesseract. Scanned documents are OCR'd
up to MAX_OCR_PAGES pages (coverage is recorded, so missed clauses beyond the
cap show up in the evaluation instead of being silently lost).

Output: data/raw/pdf_text/<file stem>.json, one per PDF, with each page's text
and the method that produced it ("text" or "ocr"). Existing files are skipped.

Usage: python -m src.extract.pdf_text [--workers 6]
"""
import argparse
import json
import os
import shutil
import time
import warnings
from concurrent.futures import ThreadPoolExecutor

import pandas as pd
import pypdfium2 as pdfium
import pytesseract
from pypdf import PdfReader

from src.config import MANIFEST_DIR, PDF_DIR, RAW_DIR

warnings.filterwarnings("ignore")  # pypdf is noisy about malformed scans

TEXT_DIR = RAW_DIR / "pdf_text"
MIN_CHARS = 200        # below this, the page is treated as an image
MAX_OCR_PAGES = 80     # OCR budget per document
OCR_DPI = 200

TESSERACT = os.getenv("TESSERACT_CMD") or shutil.which("tesseract") \
    or r"C:\Program Files\Tesseract-OCR\tesseract.exe"
pytesseract.pytesseract.tesseract_cmd = TESSERACT
os.environ.setdefault("OMP_THREAD_LIMIT", "1")  # one core per Tesseract process; parallelism comes from the pool


def ocr(image) -> str:
    return pytesseract.image_to_string(image, config="--psm 3")


def extract(path, pool: ThreadPoolExecutor) -> dict:
    reader = PdfReader(path)
    texts = []
    for page in reader.pages:
        try:
            texts.append((page.extract_text() or "").strip())
        except Exception:  # a broken page shouldn't lose the document
            texts.append("")

    need_ocr = [i for i, t in enumerate(texts) if len(t) < MIN_CHARS][:MAX_OCR_PAGES]
    methods = ["text" if len(t) >= MIN_CHARS else "none" for t in texts]
    if need_ocr:
        pdf = pdfium.PdfDocument(path)
        # pdfium isn't thread-safe: render here, OCR in the pool.
        futures = {i: pool.submit(ocr, pdf[i].render(scale=OCR_DPI / 72).to_pil()) for i in need_ocr}
        for i, fut in futures.items():
            texts[i] = fut.result().strip()
            methods[i] = "ocr"
        pdf.close()

    n_ocr = methods.count("ocr")
    kind = "scan" if n_ocr > len(texts) / 2 else "text"
    return {
        "file": path.name,
        "pages": len(texts),
        "kind": kind,
        "pages_text": methods.count("text"),
        "pages_ocr": n_ocr,
        "pages_unread": methods.count("none"),  # image pages beyond the OCR budget
        "page_text": [{"page": i + 1, "method": m, "text": t} for i, (t, m) in enumerate(zip(texts, methods))],
    }


def main(workers: int) -> None:
    TEXT_DIR.mkdir(parents=True, exist_ok=True)
    manifest = pd.read_csv(MANIFEST_DIR / "pdf_manifest.csv", dtype=str)
    files = manifest.loc[manifest.is_pdf.eq("True"), "file"].tolist()
    with ThreadPoolExecutor(workers) as pool:
        for name in files:
            out = TEXT_DIR / f"{name[:-4]}.json"
            if out.exists():
                continue
            start = time.time()
            doc = extract(PDF_DIR / name, pool)
            doc["seconds"] = round(time.time() - start, 1)
            out.write_text(json.dumps(doc), encoding="utf-8")
            print(f"{name}: {doc['pages']} pages, {doc['pages_ocr']} OCR, "
                  f"{doc['pages_unread']} unread, {doc['seconds']}s", flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=6)
    main(ap.parse_args().workers)
