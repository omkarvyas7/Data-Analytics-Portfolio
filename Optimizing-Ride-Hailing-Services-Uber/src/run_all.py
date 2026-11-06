"""Rebuild everything: python src/run_all.py

simulate, SQLite, SQL outputs, ILP check, Excel, dashboard extract and PNGs, docs, then the
notebook (skipped without cvxpy, saved outputs kept).
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import build_db  # noqa: E402
import make_dashboard  # noqa: E402
import make_docs  # noqa: E402
import make_excel  # noqa: E402
import run_notebook  # noqa: E402
import run_sql  # noqa: E402
import simulate  # noqa: E402
import validate_ilp  # noqa: E402

STEPS = [
    ("simulate", simulate.main),
    ("build_db", build_db.main),
    ("run_sql", lambda: run_sql.run_all(verbose=False)),
    ("validate_ilp", validate_ilp.main),
    ("make_excel", make_excel.main),
    ("make_dashboard", make_dashboard.main),
    ("make_docs", make_docs.main),
    ("run_notebook", run_notebook.main),
]


def main():
    t0 = time.time()
    for name, fn in STEPS:
        t = time.time()
        print(f"--> {name}")
        fn()
        print(f"    done in {time.time() - t:.1f}s")
    print(f"all steps finished in {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
