from pathlib import Path

import psycopg

from src.config import DATABASE_URL


def connect() -> psycopg.Connection:
    return psycopg.connect(DATABASE_URL)


def run_sql_file(conn: psycopg.Connection, path: Path) -> None:
    conn.execute(path.read_text(encoding="utf-8"))
    conn.commit()
    print(f"ran {path.name}")
