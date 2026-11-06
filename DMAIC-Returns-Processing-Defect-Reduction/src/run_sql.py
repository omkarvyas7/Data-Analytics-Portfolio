"""Run every numbered query in sql/ against the SQLite database and save results to data/processed/."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SQL_DIR = ROOT / "sql"
PROC = ROOT / "data" / "processed"
DB = ROOT / "data" / "returns_dmaic.db"


def run_query(con: sqlite3.Connection, path: Path) -> pd.DataFrame:
    return pd.read_sql_query(path.read_text(encoding="utf-8"), con)


def main() -> None:
    PROC.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB)
    for path in sorted(SQL_DIR.glob("[0-9][0-9]_*.sql")):
        df = run_query(con, path)
        out = PROC / f"{path.stem}.csv"
        df.to_csv(out, index=False)
        print(f"{path.name:45s} -> {out.name} ({len(df)} rows)")
    con.close()


if __name__ == "__main__":
    main()
