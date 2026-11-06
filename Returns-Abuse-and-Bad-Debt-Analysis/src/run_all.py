"""Rebuild everything from scratch: data, db, SQL, stats, Excel, dashboard, docs, notebook.

Usage: python src/run_all.py [--keep-db]
"""
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import build_db  # noqa: E402
import config as C  # noqa: E402
import generate_data  # noqa: E402
import make_dashboard  # noqa: E402
import make_docs  # noqa: E402
import make_excel  # noqa: E402
import make_notebook  # noqa: E402
import metrics  # noqa: E402
import run_sql  # noqa: E402
import stats_analysis  # noqa: E402


def clean():
    """Remove generated outputs so the run starts from a fresh state."""
    if C.DB_PATH.exists():
        C.DB_PATH.unlink()
    for d in [C.PROCESSED, C.RAW, C.SHOTS]:
        if d.exists():
            shutil.rmtree(d)
        d.mkdir(parents=True)
    for f in [C.EXCEL_DIR / "Returns_Risk_Model.xlsx", C.DASH_DIR / "tableau_extract.csv", C.NOTEBOOK]:
        if f.exists():
            f.unlink()
    for f in C.DOCS_DIR.glob("*"):
        f.unlink()


STEPS = [
    ("clean outputs", clean),
    ("generate synthetic data", generate_data.main),
    ("build SQLite db", build_db.main),
    ("run SQL 01-12", run_sql.main),
    ("statistics", stats_analysis.main),
    ("metrics", metrics.build),
    ("Excel workbook", make_excel.build),
    ("dashboard + charts", make_dashboard.main),
    ("documents + README", make_docs.main),
    ("execute notebook", make_notebook.main),
]


def main():
    t0 = time.time()
    for name, fn in STEPS:
        t = time.time()
        print(f"\n=== {name} ===")
        fn()
        print(f"--- {name}: {time.time() - t:.1f}s")
    if "--keep-db" not in sys.argv:
        C.DB_PATH.unlink()  # ~90 MB and easy to rebuild, pass --keep-db to keep it
        print("removed data/returns.db (rerun with --keep-db to keep it)")
    print(f"\nAll steps finished in {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
