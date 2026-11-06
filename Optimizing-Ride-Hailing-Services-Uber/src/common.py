"""Shared paths and constants for the dispatch simulation project."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_RAW = ROOT / "data" / "raw"
DATA_PROCESSED = ROOT / "data" / "processed"
SQL_DIR = ROOT / "sql"
EXCEL_DIR = ROOT / "excel"
DASHBOARD_DIR = ROOT / "dashboard"
SCREENSHOTS_DIR = ROOT / "screenshots"
DOCS_DIR = ROOT / "docs"
NOTEBOOK = ROOT / "notebooks" / "Uber_dispatch_optimization.ipynb"
DB_PATH = DATA_PROCESSED / "dispatch_sim.db"

# Protocol labels used everywhere (CSV, SQL, Excel, dashboard)
GREEDY = "greedy_first_dispatch"
GREEDY_MDR = "greedy_first_dispatch_mdr"
BATCH = "batched_min_eta"
BATCH_MDR = "batched_min_eta_mdr"
BATCH_PROFIT_MDR = "batched_max_profit_mdr"
PROTOCOLS = [GREEDY, GREEDY_MDR, BATCH, BATCH_MDR, BATCH_PROFIT_MDR]

for d in (DATA_RAW, DATA_PROCESSED, EXCEL_DIR, DASHBOARD_DIR, SCREENSHOTS_DIR, DOCS_DIR):
    d.mkdir(parents=True, exist_ok=True)
