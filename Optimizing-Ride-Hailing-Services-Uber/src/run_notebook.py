"""Re-run notebooks/Uber_dispatch_optimization.ipynb in place. Skipped without cvxpy."""
import asyncio
import importlib.util
import sys

import nbformat
from nbclient import NotebookClient

from common import NOTEBOOK


def main():
    if importlib.util.find_spec("cvxpy") is None:
        print("cvxpy not installed, keeping the notebook's saved outputs (not re-executed)")
        return
    if sys.platform.startswith("win"):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    nb = nbformat.read(NOTEBOOK, as_version=4)
    NotebookClient(nb, kernel_name="python3", timeout=600,
                   resources={"metadata": {"path": str(NOTEBOOK.parent)}}).execute()
    nbformat.write(nb, NOTEBOOK)
    print(f"executed {NOTEBOOK.name}")


if __name__ == "__main__":
    main()
