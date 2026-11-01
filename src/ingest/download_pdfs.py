"""Download a stratified sample of contract PDFs and record a manifest.

Only contracts with itemized (2022+) payments are sampled, so every PDF can be
tied back to spend. Files already on disk are skipped.

Usage: python -m src.ingest.download_pdfs --n 200
"""
import argparse
import io
import re
import time
import warnings

import pandas as pd
import requests
from pypdf import PdfReader

from src.config import MANIFEST_DIR, PDF_DIR, PDF_URL, RAW_DIR, USER_AGENT

warnings.filterwarnings("ignore")  # pypdf is noisy about malformed scans

MANIFEST = MANIFEST_DIR / "pdf_manifest.csv"
TEXT_CHARS_PER_PAGE = 200  # below this on the first pages, treat as a scan needing OCR
GUID_RE = r"id=(\{[0-9A-Fa-f-]+\})"


def resolve_doc_id(session: requests.Session, link: str) -> str | None:
    """Legacy links: open the viewer page and read the GUID from its iframe."""
    resp = session.get(link, timeout=90)  # redirects through a session-cookie hop
    m = re.search(GUID_RE, resp.text)
    return m.group(1) if m else None


def sample_pool(n: int, seed: int) -> pd.DataFrame:
    c = pd.read_csv(RAW_DIR / "contracts.csv", dtype=str, low_memory=False)
    p = pd.read_csv(RAW_DIR / "payments.csv", dtype=str, low_memory=False,
                    usecols=["check_date", "contract_number"])
    itemized = p.check_date.str.contains("/", na=False) & p.contract_number.ne("DV")
    paid = set(p.loc[itemized, "contract_number"])

    c["doc_id"] = c.contract_pdf.str.extract(GUID_RE)[0]
    c["link_format"] = c.doc_id.notna().map({True: "current", False: "legacy"})
    c = c[c.purchase_order_contract_number.isin(paid) & c.contract_pdf.notna()].copy()
    c["award"] = pd.to_numeric(c.award_amount, errors="coerce")
    c["size_band"] = pd.qcut(c.award.rank(method="first"), 4, labels=["s", "m", "l", "xl"])

    # Spread the sample evenly across size bands, then across contract types within each.
    per_band = max(1, n // 4)
    parts = []
    for _, g in c.groupby("size_band", observed=True):
        g = g.sample(frac=1, random_state=seed)
        g["type_rank"] = g.groupby("contract_type").cumcount()
        parts.append(g.sort_values("type_rank").head(per_band))
    return pd.concat(parts).head(n)


def inspect_pdf(content: bytes) -> dict:
    reader = PdfReader(io.BytesIO(content))
    pages = len(reader.pages)
    first = [reader.pages[i] for i in range(min(pages, 5))]
    chars = sum(len((pg.extract_text() or "").strip()) for pg in first) / max(len(first), 1)
    return {"pages": pages, "chars_per_page": int(chars),
            "kind": "text" if chars > TEXT_CHARS_PER_PAGE else "scan"}


def main(n: int, seed: int, delay: float) -> None:
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
    done = pd.read_csv(MANIFEST, dtype=str) if MANIFEST.exists() else pd.DataFrame()

    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    rows = []
    for _, r in sample_pool(n, seed).iterrows():
        path = PDF_DIR / f"{r.purchase_order_contract_number}_{r.revision_number}.pdf"
        rec = {"contract_number": r.purchase_order_contract_number,
               "revision_number": r.revision_number, "doc_id": r.doc_id,
               "link_format": r.link_format,
               "contract_type": r.contract_type, "award_amount": r.award_amount,
               "file": path.name}
        if path.exists():
            continue
        try:
            if pd.isna(rec["doc_id"]):
                rec["doc_id"] = resolve_doc_id(session, r.contract_pdf)
                if rec["doc_id"] is None:
                    rec.update(http_status="unresolved")
                    rows.append(rec)
                    continue
            resp = session.get(PDF_URL.format(doc_id=rec["doc_id"]), timeout=180)
            is_pdf = resp.ok and resp.content[:4] == b"%PDF"
            rec.update(http_status=resp.status_code, bytes=len(resp.content), is_pdf=is_pdf)
            if is_pdf:
                path.write_bytes(resp.content)
                rec.update(inspect_pdf(resp.content))
        except Exception as e:  # keep going; failures are part of the manifest
            rec.update(http_status="error", error=str(e)[:200])
        rows.append(rec)
        print(rec["file"], rec.get("http_status"), rec.get("kind", ""))
        time.sleep(delay)

    pd.concat([done, pd.DataFrame(rows)], ignore_index=True).to_csv(MANIFEST, index=False)
    print(f"{len(rows)} new rows -> {MANIFEST}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--delay", type=float, default=1.0, help="seconds between requests")
    args = ap.parse_args()
    main(args.n, args.seed, args.delay)
