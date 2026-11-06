"""Run every sql/*.sql file against the SQLite database and save each result to data/processed/."""
import sqlite3

import pandas as pd

from common import DATA_PROCESSED, DB_PATH, SQL_DIR


def run_all(verbose: bool = True) -> dict[str, pd.DataFrame]:
    out = {}
    with sqlite3.connect(DB_PATH) as con:
        for path in sorted(SQL_DIR.glob("*.sql")):
            df = pd.read_sql_query(path.read_text(encoding="utf-8"), con)
            df.to_csv(DATA_PROCESSED / f"sql_{path.stem}.csv", index=False)
            out[path.stem] = df
            if verbose:
                print(f"\n== {path.name}: {len(df)} rows")
                print(df.head(12).to_string(index=False))
    return out


if __name__ == "__main__":
    pd.set_option("display.width", 220)
    run_all()
