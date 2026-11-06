"""Run the numbered WBR SQL files against SQLite and save results to data/processed/.

Usage:  python src/run_sql.py --week 2026-10-26
"""
import argparse
import sqlite3
from datetime import date, timedelta

import pandas as pd

from config import DB_PATH, SQL_DIR, PROCESSED, DEFAULT_WEEK

WBR_QUERIES = {
    "kpi_summary": "01_wbr_kpi_summary.sql",
    "kpi_rag": "02_kpi_vs_target_rag.sql",
    "kpi_trend": "03_kpi_trend.sql",
    "top_movers": "04_top_movers_category.sql",
    "cycle_driver": "05_refund_cycle_driver_channel.sql",
    "program_health": "06_program_health_initiative.sql",
    "milestones": "07_milestone_status.sql",
    "risks": "08_open_high_risks.sql",
    "blocked": "09_blocked_dependencies.sql",
    "gap_list": "10_gap_list_partner_teams.sql",
}


def week_params(week):
    d = date.fromisoformat(week)
    if d.weekday() != 0:
        raise ValueError(f"--week must be a Monday (got {week}, a {d.strftime('%A')})")
    return {"week_start": d.isoformat(), "week_end": (d + timedelta(days=6)).isoformat()}


def run_file(con, filename, params=None):
    sql = (SQL_DIR / filename).read_text(encoding="utf-8")
    used = {k: v for k, v in (params or {}).items() if f":{k}" in sql}
    return pd.read_sql_query(sql, con, params=used)


def run_wbr_queries(week, save_dir=None):
    """Execute every WBR query for `week`; optionally save each result as CSV."""
    params = week_params(week)
    con = sqlite3.connect(DB_PATH)
    try:
        out = {key: run_file(con, fn, params) for key, fn in WBR_QUERIES.items()}
    finally:
        con.close()
    if out["kpi_summary"].empty:
        raise ValueError(f"No KPI data for week {week}; check the data range.")
    if save_dir is not None:
        save_dir.mkdir(parents=True, exist_ok=True)
        for key, df in out.items():
            stem = WBR_QUERIES[key].replace(".sql", "")
            df.to_csv(save_dir / f"{stem}.csv", index=False)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--week", default=DEFAULT_WEEK)
    a = ap.parse_args()
    res = run_wbr_queries(a.week, PROCESSED / f"wbr_{a.week}")
    for k, v in res.items():
        print(f"{k:15s} {len(v):5d} rows")


if __name__ == "__main__":
    main()
