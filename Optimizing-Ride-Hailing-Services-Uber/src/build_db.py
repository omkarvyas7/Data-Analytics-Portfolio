"""Load simulation CSVs into a local SQLite database (data/processed/dispatch_sim.db)."""
import sqlite3

import pandas as pd

from common import DATA_PROCESSED, DATA_RAW, DB_PATH

TABLES = {
    "dispatch_windows": DATA_RAW / "dispatch_windows.csv",
    "simulation_results": DATA_PROCESSED / "simulation_results.csv",
    "simulation_matches": DATA_PROCESSED / "simulation_matches.csv",
}
INDEXES = [
    "CREATE INDEX IF NOT EXISTS ix_res_proto ON simulation_results(protocol)",
    "CREATE INDEX IF NOT EXISTS ix_res_window ON simulation_results(window_id)",
    "CREATE INDEX IF NOT EXISTS ix_match_proto ON simulation_matches(protocol, window_id)",
]


def main():
    if DB_PATH.exists():
        DB_PATH.unlink()
    with sqlite3.connect(DB_PATH) as con:
        for name, path in TABLES.items():
            df = pd.read_csv(path)
            df.to_sql(name, con, index=False)
            print(f"{name}: {len(df):,} rows")
        for stmt in INDEXES:
            con.execute(stmt)


if __name__ == "__main__":
    main()
