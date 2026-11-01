import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

RAW_DIR = ROOT / "data" / "raw"
PDF_DIR = RAW_DIR / "pdfs"
MANIFEST_DIR = ROOT / "data" / "manifests"
SQL_DIR = ROOT / "sql"

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://vendor:vendor@localhost:5433/vendor")

SOCRATA_BASE = "https://data.cityofchicago.org/resource"
DATASETS = {
    "contracts": "rsxa-ify5",
    "payments": "s4vu-giwb",
}

# The contract_pdf link opens a JavaScript viewer; this is the URL its iframe loads.
# Legacy (sid=EDGE) links don't carry the GUID; the viewer page reveals it.
PDF_URL = (
    "https://ecm.chicago.gov/eSMARTContracts/service/DPSWebDocumentViewer"
    "?id={doc_id}&osName=eContentContracts&el=0&image=image"
)
USER_AGENT = "vendor-spend-compliance portfolio project"
