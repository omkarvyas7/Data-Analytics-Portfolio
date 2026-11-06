"""Rebuild everything from a fresh state: data -> db -> WBR -> workbooks -> dashboard -> notebook -> docs.

Usage: python src/run_all.py [--week YYYY-MM-DD]
"""
import argparse
import shutil
import time

import build_db
import generate_data
import make_dashboard
import make_docs
import make_notebook
import make_tracker_excel
import run_wbr
import verify_outputs
from config import CHART_DIR, DB_PATH, DEFAULT_WEEK, PROCESSED


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--week", default=DEFAULT_WEEK)
    a = ap.parse_args()
    t0 = time.time()
    # fresh state: remove regenerable outputs
    if DB_PATH.exists():
        DB_PATH.unlink()
    for p in [PROCESSED, CHART_DIR]:
        if p.exists():
            shutil.rmtree(p)
    generate_data.main()
    build_db.main()
    run_wbr.run(a.week)
    make_tracker_excel.main()
    make_dashboard.main(a.week)
    make_notebook.main()
    make_docs.main()
    verify_outputs.main()
    print(f"run_all: complete in {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
