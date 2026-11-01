"""Run every check in sql/tests and print a results table.

Each check returns one row (failing_rows, total_rows) and declares a severity
in its header. Exits non-zero if any `error` check fails.

Usage: python -m src.dq.run_checks
"""
import re
import sys

from src.config import SQL_DIR
from src.db import connect


def header(sql: str, key: str) -> str:
    m = re.search(rf"--\s*{key}:\s*(.+)", sql)
    return m.group(1).strip() if m else ""


def main() -> int:
    failed_errors = 0
    rows = []
    with connect() as conn:
        for path in sorted((SQL_DIR / "tests").glob("*.sql")):
            sql = path.read_text(encoding="utf-8")
            failing, total = conn.execute(sql).fetchone()
            severity = header(sql, "severity") or "error"
            status = "PASS" if failing == 0 else severity.upper()
            if failing and severity == "error":
                failed_errors += 1
            rows.append((status, path.stem, failing, total))

    print(f"{'status':<6}  {'check':<32} {'failing':>10} {'total':>10} {'pct':>7}")
    for status, name, failing, total in rows:
        pct = failing / total * 100 if total else 0
        print(f"{status:<6}  {name:<32} {failing:>10,} {total:>10,} {pct:>6.1f}%")
    return 1 if failed_errors else 0


if __name__ == "__main__":
    sys.exit(main())
