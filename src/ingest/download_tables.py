"""Download the Chicago contracts and payments tables as CSV.

Writes data/manifests/download_manifest.json with the snapshot (as-of) date,
row counts and file hashes, so every KPI can be traced to one snapshot.

Usage:
    python -m src.ingest.download_tables
    python -m src.ingest.download_tables --manifest-only   # re-describe files already on disk
"""
import argparse
import csv
import hashlib
import json
from datetime import datetime

import requests

from src.config import DATASETS, MANIFEST_DIR, RAW_DIR, SOCRATA_BASE, USER_AGENT

MANIFEST = MANIFEST_DIR / "download_manifest.json"


def download(name: str, dataset_id: str) -> None:
    url = f"{SOCRATA_BASE}/{dataset_id}.csv"
    out = RAW_DIR / f"{name}.csv"
    # Socrata caps rows per request; one large limit covers both tables today.
    params = {"$limit": 2_000_000, "$order": ":id"}
    with requests.get(url, params=params, stream=True, timeout=600,
                      headers={"User-Agent": USER_AGENT}) as resp:
        resp.raise_for_status()
        with open(out, "wb") as f:
            for chunk in resp.iter_content(1 << 20):
                f.write(chunk)
    print(f"{name}: {out.stat().st_size / 1e6:.1f} MB -> {out}")


def describe(name: str, dataset_id: str) -> dict:
    path = RAW_DIR / f"{name}.csv"
    sha = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1 << 20):
            sha.update(chunk)
    with open(path, encoding="utf-8", newline="") as f:
        rows = sum(1 for _ in csv.reader(f)) - 1
    # Local time with offset, so the as-of date matches the calendar day it was pulled.
    downloaded = datetime.fromtimestamp(path.stat().st_mtime).astimezone()
    return {"dataset_id": dataset_id, "file": path.name, "rows": rows,
            "sha256": sha.hexdigest(), "downloaded_at": downloaded.isoformat(timespec="seconds")}


def write_manifest() -> None:
    tables = {name: describe(name, ds) for name, ds in DATASETS.items()}
    # As-of date = the day the oldest file was pulled; KPIs are computed against it.
    as_of = min(t["downloaded_at"] for t in tables.values())[:10]
    MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps({"as_of_date": as_of, "source": SOCRATA_BASE,
                                    "tables": tables}, indent=2))
    print(f"as_of_date {as_of} -> {MANIFEST}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest-only", action="store_true")
    args = ap.parse_args()
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    if not args.manifest_only:
        for name, dataset_id in DATASETS.items():
            download(name, dataset_id)
    write_manifest()
