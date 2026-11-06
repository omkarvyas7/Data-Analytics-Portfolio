"""Automated weekly business review (WBR) pipeline.

Usage:
    python src/run_wbr.py --week 2026-10-26

Steps:
  1. Build the SQLite database from data/raw if it does not exist (or --rebuild).
  2. Run sql/01-10 for the week and save every result to data/processed/wbr_<week>/.
  3. Write the headline narrative from the numbers (src/narrative.py) -> narrative.json.
  4. Render charts (reports/charts/).
  5. Build excel/Returns_WBR_<week>.xlsx (formula-driven, conditional-formatting RAG, native charts).
  6. Build reports/WBR_<week>.pdf (3 pages).
Exit code is non-zero if any step fails, so a scheduler can alert on failure.
"""
import argparse
import json
import sqlite3
import sys
import time

import pandas as pd

import build_db
import charts
from config import CHART_DIR, DB_PATH, DEFAULT_WEEK, EXCEL_DIR, PROCESSED, REPORTS_DIR
from narrative import build_narrative
from run_sql import run_wbr_queries
from wbr_excel import build_wbr_workbook
from wbr_pdf import build_wbr_pdf


def run(week, rebuild=False):
    t0 = time.time()
    if rebuild or not DB_PATH.exists():
        build_db.main()
    out_dir = PROCESSED / f"wbr_{week}"
    res = run_wbr_queries(week, out_dir)
    con = sqlite3.connect(DB_PATH)
    weekly = pd.read_sql_query("SELECT * FROM v_weekly_kpi WHERE week_start <= ? ORDER BY week_start", con, params=[week])
    targets = pd.read_sql_query("SELECT * FROM kpi_targets ORDER BY sort_order", con)
    con.close()

    narrative = build_narrative(res, week)
    (out_dir / "narrative.json").write_text(json.dumps(narrative, indent=2), encoding="utf-8")

    CHART_DIR.mkdir(parents=True, exist_ok=True)
    ch = {"trends": CHART_DIR / f"kpi_trends_{week}.png",
          "driver": CHART_DIR / f"refund_cycle_driver_{week}.png",
          "movers": CHART_DIR / f"top_movers_{week}.png",
          "timeline": CHART_DIR / f"milestone_timeline_{week}.png"}
    charts.kpi_small_multiples(res["kpi_trend"], res["kpi_rag"], ch["trends"])
    charts.cycle_driver_chart(res["cycle_driver"], ch["driver"])
    charts.top_movers_heatmap(res["top_movers"], ch["movers"])
    charts.milestone_timeline(res["milestones"], narrative["week_end"], ch["timeline"])

    xlsx = build_wbr_workbook(res, weekly, targets, narrative, week, EXCEL_DIR / f"Returns_WBR_{week}.xlsx")
    pdf = build_wbr_pdf(res, narrative, ch, week, REPORTS_DIR / f"WBR_{week}.pdf")
    print(f"run_wbr: week {week} -> {xlsx.name}, {pdf.name} ({time.time() - t0:.1f}s)")
    for line in narrative["headline"]:
        print("  -", line)
    return res, narrative


def main():
    ap = argparse.ArgumentParser(description="Generate the Returns Program WBR for one week.")
    ap.add_argument("--week", default=DEFAULT_WEEK, help="Monday of the WBR week, YYYY-MM-DD")
    ap.add_argument("--rebuild", action="store_true", help="rebuild the SQLite database first")
    a = ap.parse_args()
    try:
        run(a.week, a.rebuild)
    except Exception as exc:  # surfaced to the scheduler as a non-zero exit
        print(f"run_wbr FAILED for week {a.week}: {exc}", file=sys.stderr)
        raise


if __name__ == "__main__":
    main()
