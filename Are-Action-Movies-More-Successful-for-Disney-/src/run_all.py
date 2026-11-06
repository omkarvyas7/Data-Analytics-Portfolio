"""Rebuild every output from data/raw in one command: python src/run_all.py"""
from __future__ import annotations

import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import analysis  # noqa: E402
import build_db  # noqa: E402
import make_dashboard  # noqa: E402
import make_docs  # noqa: E402
import make_excel  # noqa: E402
import make_notebook  # noqa: E402
import run_sql  # noqa: E402
from common import PROCESSED  # noqa: E402

STEPS = [("clean + statistics", analysis.main), ("SQLite database", build_db.main), ("SQL queries", run_sql.main),
         ("dashboard extract + charts", make_dashboard.main), ("Excel workbook", make_excel.main),
         ("execute notebook", make_notebook.main), ("memo + README", make_docs.main)]


def main() -> None:
    if PROCESSED.exists():
        shutil.rmtree(PROCESSED)  # everything in data/processed gets rebuilt below
    for name, fn in STEPS:
        t = time.time()
        print(f"\n### {name}")
        fn()
        print(f"    done in {time.time() - t:.1f}s")
    print("\nAll outputs rebuilt.")


if __name__ == "__main__":
    main()
