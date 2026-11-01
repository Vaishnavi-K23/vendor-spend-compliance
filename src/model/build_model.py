"""Build the dimensional model (schema dw) from staging.

Loads the reference CSVs in data/reference into schema ref, then runs the
model SQL files in order. Requires stg.* (python -m src.load.load_raw).

Usage: python -m src.model.build_model
"""
import time

from src.config import ROOT, SQL_DIR
from src.db import connect, run_sql_file

REFERENCE_DIR = ROOT / "data" / "reference"

REFERENCE_TABLES = {
    "payee_types": """
        payee_type text primary key,
        payee_group text not null,
        is_procurement_like boolean,
        description text""",
    "payee_type_overrides": """
        payee_key text primary key,
        payee_type text not null,
        confidence text not null,
        basis text""",
}

MODEL_FILES = [
    "02_functions.sql",
    "03_vendors.sql",
    "04_contracts.sql",
    "05_payments.sql",
    "06_conformed.sql",
]


def load_reference(conn) -> None:
    conn.execute("create schema if not exists ref")
    for table, ddl in REFERENCE_TABLES.items():
        conn.execute(f"drop table if exists ref.{table} cascade")
        conn.execute(f"create table ref.{table} ({ddl})")
        with open(REFERENCE_DIR / f"{table}.csv", encoding="utf-8") as f, \
                conn.cursor().copy(f"copy ref.{table} from stdin with (format csv, header true)") as copy:
            copy.write(f.read())
        n = conn.execute(f"select count(*) from ref.{table}").fetchone()[0]
        print(f"ref.{table}: {n} rows")
    # Every override must use a defined type, or it silently drops out of the payee groups.
    bad = conn.execute("""select payee_key, payee_type from ref.payee_type_overrides
                          where payee_type not in (select payee_type from ref.payee_types)""").fetchall()
    if bad:
        raise ValueError(f"overrides with unknown payee_type: {bad}")
    conn.commit()


if __name__ == "__main__":
    with connect() as conn:
        load_reference(conn)
        for name in MODEL_FILES:
            start = time.time()
            run_sql_file(conn, SQL_DIR / name)
            print(f"  {time.time() - start:.1f}s")
