"""Shared paths and the one cleaning routine every script uses.

Cleaning lives here so the SQL tables, workbook, dashboard extract and notebook all see the same 148 films.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
SQL_DIR = ROOT / "sql"
SQL_OUT = PROCESSED / "sql_outputs"
EXCEL_DIR = ROOT / "excel"
DASH_DIR = ROOT / "dashboard"
SHOTS = ROOT / "screenshots"
DOCS = ROOT / "docs"
DB_PATH = PROCESSED / "disney.db"
RESULTS_JSON = PROCESSED / "model_results.json"

MARVEL_COMPANIES = {"Marvel Studios", "Marvel Entertainment"}


def load_actors() -> pd.DataFrame:
    """Actors_Raw.txt is a comma-separated stream of JSON objects (no outer list)."""
    text = (RAW / "Actors_Raw.txt").read_text(encoding="utf-8").strip().rstrip(",")
    return pd.DataFrame(json.loads("[" + text + "]"))


def clean_final_df(return_log: bool = False):
    """Clean the merged Disney x IMDb file (data/raw/final_df.csv). Row counts go in the log.

    Steps:
      1. drop the two leftover pandas index columns
      2. drop title-match errors, where the Disney and IMDb years are more than a year apart
         (e.g. the 1991 'Beauty and the Beast' matched to the 2017 remake's budget)
      3. drop exact duplicate (title, release year) pairs
      4. add the derived analysis fields
    """
    log = []
    df = pd.read_csv(RAW / "final_df.csv")
    log.append(("Raw merged file (final_df.csv)", len(df), int(df.isna().sum().sum())))

    df = df.drop(columns=[c for c in df.columns if c.startswith("Unnamed")])

    df["release_dt"] = pd.to_datetime(df["release_date"], format="%d/%m/%Y")
    df["release_year"] = df["release_dt"].dt.year
    mismatch = (df["release_year"] - df["year"]).abs() > 1
    dropped_titles = df.loc[mismatch, ["name", "release_year", "year"]].copy()
    df = df.loc[~mismatch].copy()
    log.append(("After dropping title-match errors (|release year - IMDb year| > 1)", len(df), int(df.isna().sum().sum())))

    df = df.drop_duplicates(subset=["name", "release_year"])
    log.append(("After dropping duplicate title/year pairs", len(df), int(df.isna().sum().sum())))

    df = df[(df["budget"] > 0) & (df["total_gross"] > 0)].copy()
    log.append(("After dropping non-positive budget or gross", len(df), int(df.isna().sum().sum())))

    df = df.rename(columns={"name": "title", "genre_x": "disney_genre", "genre_y": "imdb_genre",
                            "score": "imdb_score", "star_rating": "star_power"})
    df["decade"] = (df["release_year"] // 10 * 10).astype(int)
    df["inflation_factor"] = df["inflation_adjusted_gross"] / df["total_gross"]
    df["inflation_budget"] = df["budget"] * df["inflation_factor"]
    df["roi_multiple"] = df["total_gross"] / df["budget"]  # same ratio in nominal or adjusted $
    df["log_gross"] = np.log(df["inflation_adjusted_gross"])
    df["log_budget"] = np.log(df["inflation_budget"])
    df["is_action"] = (df["disney_genre"] == "Action").astype(int)
    df["is_action_imdb"] = (df["imdb_genre"] == "Action").astype(int)
    df["is_marvel"] = df["company"].isin(MARVEL_COMPANIES).astype(int)
    df["star_bucket"] = pd.qcut(df["star_power"], 4,
                                labels=["Q1 lowest", "Q2", "Q3", "Q4 highest"]).astype(str)
    keep = ["title", "release_date", "release_year", "decade", "disney_genre", "imdb_genre",
            "mpaa_rating", "company", "director", "star", "star_power", "star_bucket", "imdb_score",
            "votes", "runtime", "budget", "total_gross", "inflation_adjusted_gross", "inflation_factor",
            "inflation_budget", "roi_multiple", "log_gross", "log_budget", "is_action",
            "is_action_imdb", "is_marvel"]
    df = df[keep].sort_values("inflation_adjusted_gross", ascending=False).reset_index(drop=True)
    if return_log:
        return df, pd.DataFrame(log, columns=["step", "rows", "null_cells"]), dropped_titles
    return df
