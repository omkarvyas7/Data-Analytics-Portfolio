"""Rebuilds everything: loads the CSVs into SQLite, runs sql/*.sql, fits the kNN
recommender (same 50-rating cutoff as the notebook), draws the charts and writes
data/processed/key_metrics.json.

Usage: python src/run_all.py
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "processed"
SQL_DIR = ROOT / "sql"
SHOTS = ROOT / "screenshots"
POPULARITY_THRESHOLD = 50  # same threshold as the original notebook
EXAMPLE_TITLES = ["Toy Story (1995)", "Matrix, The (1999)", "Godfather, The (1972)"]


def load_db() -> tuple[sqlite3.Connection, pd.DataFrame, pd.DataFrame]:
    movies = pd.read_csv(RAW / "movies.csv")
    ratings = pd.read_csv(RAW / "ratings.csv")
    con = sqlite3.connect(":memory:")
    movies.to_sql("movies", con, index=False)
    ratings.to_sql("ratings", con, index=False)
    return con, movies, ratings


def run_sql(con: sqlite3.Connection) -> dict[str, pd.DataFrame]:
    results = {}
    for path in sorted(SQL_DIR.glob("*.sql")):
        df = pd.read_sql_query(path.read_text(encoding="utf-8"), con)
        df.to_csv(OUT / f"sql_{path.stem}.csv", index=False)
        results[path.stem] = df
    return results


def knn_recommend(movies: pd.DataFrame, ratings: pd.DataFrame, k: int = 5) -> pd.DataFrame:
    """Item-based kNN: cosine similarity between movie rating vectors (users as features)."""
    merged = ratings.merge(movies[["movieId", "title"]], on="movieId")
    counts = merged.groupby("title")["rating"].transform("count")
    popular = merged[counts >= POPULARITY_THRESHOLD]
    matrix = popular.pivot_table(index="title", columns="userId", values="rating").fillna(0)
    vecs = matrix.to_numpy()
    norms = np.linalg.norm(vecs, axis=1, keepdims=True)
    unit = vecs / np.where(norms == 0, 1, norms)
    rows = []
    for title in EXAMPLE_TITLES:
        if title not in matrix.index:
            continue
        i = matrix.index.get_loc(title)
        sims = unit @ unit[i]
        sims[i] = -1  # exclude the movie itself
        for rank, j in enumerate(np.argsort(sims)[::-1][:k], start=1):
            rows.append({"seed_movie": title, "rank": rank,
                         "recommended_movie": matrix.index[j],
                         "cosine_similarity": round(float(sims[j]), 3)})
    recs = pd.DataFrame(rows)
    recs.to_csv(OUT / "knn_recommendations.csv", index=False)
    return recs, matrix.shape


def charts(res: dict[str, pd.DataFrame]) -> None:
    plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False})
    b = res["02_rating_count_buckets"]
    seg = res["04_user_activity_segments"]
    top = res["03_top_movies_min_50"].head(10)
    yr = res["05_ratings_by_year"]

    def bucket_chart(ax):
        x = np.arange(len(b))
        ax.bar(x - 0.2, b["pct_of_movies"], 0.4, label="% of movies", color="#4C72B0")
        ax.bar(x + 0.2, b["pct_of_ratings"], 0.4, label="% of ratings", color="#DD8452")
        ax.set_xticks(x, [s.split(": ")[1] for s in b["rating_count_bucket"]])
        ax.set_xlabel("Ratings per movie")
        ax.set_ylabel("%")
        ax.set_title("Long tail: most movies have few ratings")
        ax.legend(frameon=False)

    def top_chart(ax):
        t = top.iloc[::-1]
        ax.barh([s[:38] for s in t["title"]], t["avg_rating"], color="#55A868")
        ax.set_xlim(3.5, 5)
        ax.set_xlabel("Average rating (movies with 50+ ratings)")
        ax.set_title("Top 10 trustworthy titles")

    def seg_chart(ax):
        ax.bar([s.split(": ")[1] for s in seg["user_segment"]], seg["pct_of_ratings"], color="#8172B3")
        ax.set_ylabel("% of all ratings")
        ax.set_title("Who supplies the feedback")
        ax.tick_params(axis="x", rotation=15)

    def year_chart(ax):
        ax.plot(yr["rating_year"], yr["ratings"], marker="o", color="#C44E52")
        ax.set_ylabel("Ratings per year")
        ax.set_title("Feedback volume over time")

    for name, fn, size in [("chart_long_tail", bucket_chart, (7, 4)),
                           ("chart_top_movies", top_chart, (7, 4.5)),
                           ("chart_user_segments", seg_chart, (7, 4)),
                           ("chart_ratings_by_year", year_chart, (7, 4))]:
        fig, ax = plt.subplots(figsize=size)
        fn(ax)
        fig.tight_layout()
        fig.savefig(SHOTS / f"{name}.png", dpi=150)
        plt.close(fig)

    fig, axes = plt.subplots(2, 2, figsize=(14, 9))
    for fn, ax in zip([bucket_chart, top_chart, seg_chart, year_chart], axes.flat):
        fn(ax)
    fig.suptitle("Movie Ratings & Recommender Readiness Dashboard (MovieLens sample)",
                 fontsize=14, fontweight="bold")
    fig.tight_layout()
    fig.savefig(SHOTS / "dashboard.png", dpi=130)
    plt.close(fig)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    SHOTS.mkdir(parents=True, exist_ok=True)
    con, movies, ratings = load_db()
    res = run_sql(con)
    recs, shape = knn_recommend(movies, ratings)
    charts(res)

    dq = res["01_data_quality"].iloc[0].to_dict()
    b = res["02_rating_count_buckets"].set_index("rating_count_bucket")
    under_10 = b.loc[["01: 1", "02: 2-9"], "pct_of_movies"].sum()
    seg = res["04_user_activity_segments"].set_index("user_segment")
    metrics = {
        "rating_rows": int(dq["rating_rows"]), "users": int(dq["users"]),
        "rated_movies": int(dq["rated_movies"]),
        "null_ratings": int(dq["null_ratings"]),
        "duplicate_pairs": int(dq["duplicate_user_movie_pairs"]),
        "pct_movies_under_10_ratings": round(float(under_10), 1),
        "pct_ratings_from_movies_100plus": float(b.loc["05: 100+", "pct_of_ratings"]),
        "pct_ratings_from_power_users": float(seg.loc["4: Power (500+)", "pct_of_ratings"]),
        "power_users": int(seg.loc["4: Power (500+)", "users"]),
        "knn_matrix_movies": int(shape[0]), "knn_matrix_users": int(shape[1]),
    }
    (OUT / "key_metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(json.dumps(metrics, indent=2))
    print(recs.to_string(index=False))


if __name__ == "__main__":
    main()
