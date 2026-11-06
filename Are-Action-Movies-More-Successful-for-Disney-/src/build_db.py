"""Load the raw files and the cleaned film table into a local SQLite database.

Tables
  disney_gross   579 Disney releases 1937-2016 (data/raw/disney_movies_total_gross.csv)
  imdb_movies    7,668 films with budget, score, star (data/raw/movies.csv)
  actors         500 actors with a popularity rating (data/raw/Actors_Raw.txt)
  merged_raw     156-row Disney x IMDb merge as delivered (data/raw/final_df.csv)
  films          148-row cleaned analysis table (src/common.py::clean_final_df)
"""
from __future__ import annotations

import sqlite3

import pandas as pd

from common import DB_PATH, PROCESSED, RAW, clean_final_df, load_actors


def main() -> None:
    PROCESSED.mkdir(parents=True, exist_ok=True)
    if DB_PATH.exists():
        DB_PATH.unlink()
    merged = pd.read_csv(RAW / "final_df.csv")
    merged = merged.drop(columns=[c for c in merged.columns if c.startswith("Unnamed")])
    tables = {
        "disney_gross": pd.read_csv(RAW / "disney_movies_total_gross.csv"),
        "imdb_movies": pd.read_csv(RAW / "movies.csv"),
        "actors": load_actors()[["name", "rating", "alternative_name", "objectID"]],
        "merged_raw": merged,
        "films": clean_final_df(),
    }
    with sqlite3.connect(DB_PATH) as con:
        for name, df in tables.items():
            df.to_sql(name, con, index=False)
            print(f"{name:<13} {len(df):>6,} rows")


if __name__ == "__main__":
    main()
