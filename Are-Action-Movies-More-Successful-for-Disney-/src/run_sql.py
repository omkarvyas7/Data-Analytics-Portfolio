"""Run each numbered query in sql/ against data/processed/disney.db.

A file can hold several ';'-separated statements. Each result goes to
data/processed/sql_outputs/<file stem>[_<n>].csv and a preview is printed.
"""
from __future__ import annotations

import sqlite3

import pandas as pd

from common import DB_PATH, SQL_DIR, SQL_OUT


def split_statements(sql: str) -> list[str]:
    body = "\n".join(line for line in sql.splitlines() if not line.strip().startswith("--"))
    return [s.strip() for s in body.split(";") if s.strip()]


def main() -> None:
    SQL_OUT.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as con:
        for path in sorted(SQL_DIR.glob("[0-9][0-9]_*.sql")):
            stmts = split_statements(path.read_text(encoding="utf-8"))
            for i, stmt in enumerate(stmts, 1):
                df = pd.read_sql_query(stmt, con)
                suffix = f"_{i}" if len(stmts) > 1 else ""
                df.to_csv(SQL_OUT / f"{path.stem}{suffix}.csv", index=False)
                print(f"\n== {path.name}{suffix}: {len(df)} rows")
                print(df.head(8).to_string(index=False))


if __name__ == "__main__":
    main()
