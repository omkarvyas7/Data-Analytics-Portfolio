"""Rebuild everything from scratch: data -> database -> SQL outputs -> stats/charts -> Excel ->
dashboard -> documents/README -> executed notebook.

Usage: python src/run_all.py
"""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

SRC = Path(__file__).resolve().parent
STEPS = ["generate_data.py", "build_db.py", "run_sql.py", "analyze.py", "make_excel.py",
         "make_dashboard.py", "make_docs.py", "build_notebook.py"]


def main() -> None:
    t0 = time.time()
    for step in STEPS:
        print(f"\n=== {step} ===", flush=True)
        t = time.time()
        subprocess.run([sys.executable, str(SRC / step)], check=True, cwd=SRC.parent)
        print(f"--- {step} done in {time.time() - t:.1f}s", flush=True)
    print(f"\nAll steps completed in {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
