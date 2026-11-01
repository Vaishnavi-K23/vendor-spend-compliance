"""Land the raw CSVs in Postgres as text, then build typed staging tables.

raw.*  = exactly what the portal published, every column as text, plus _row_id
stg.*  = typed, cleaned, one documented rule per transformation (sql/01_staging.sql)

Usage: python -m src.load.load_raw
"""
import csv

from src.config import DATASETS, RAW_DIR, SQL_DIR
from src.db import connect, run_sql_file


def load_csv(conn, table: str) -> None:
    path = RAW_DIR / f"{table}.csv"
    with open(path, encoding="utf-8", newline="") as f:
        header = next(csv.reader([f.readline()]))
        cols = ", ".join(f'"{c}"' for c in header)
        ddl = ", ".join(f'"{c}" text' for c in header)
        conn.execute(f"drop table if exists raw.{table} cascade")
        conn.execute(f"create table raw.{table} (_row_id bigserial primary key, {ddl})")
        f.seek(0)
        with conn.cursor().copy(
            f"copy raw.{table} ({cols}) from stdin with (format csv, header true)"
        ) as copy:
            while chunk := f.read(1 << 20):
                copy.write(chunk)
    n = conn.execute(f"select count(*) from raw.{table}").fetchone()[0]
    conn.commit()
    print(f"raw.{table}: {n:,} rows")


if __name__ == "__main__":
    with connect() as conn:
        conn.execute("create schema if not exists raw")
        for table in DATASETS:
            load_csv(conn, table)
        run_sql_file(conn, SQL_DIR / "01_staging.sql")
