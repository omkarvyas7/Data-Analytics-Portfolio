"""Shared paths and analysis parameters for the returns abuse project."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
DB_PATH = ROOT / "data" / "returns.db"
SQL_DIR = ROOT / "sql"
EXCEL_DIR = ROOT / "excel"
DASH_DIR = ROOT / "dashboard"
DOCS_DIR = ROOT / "docs"
SHOTS = ROOT / "screenshots"
NOTEBOOK = ROOT / "notebooks" / "analysis.ipynb"

SEED = 20260105
N_CUSTOMERS = 20_000

# Time frame
ORDER_START = "2024-01-01"
ORDER_END = "2025-12-31"
SCORING_CUTOFF = "2025-07-01"  # features use activity before this date; outcomes after it
EXTRACT_DATE = "2026-03-15"    # data snapshot date
BAD_DEBT_DAYS = 30             # refund counted as bad debt if item not received N days after refund

# Policy simulation defaults (also the Excel what-if defaults)
HIGH_VALUE_THRESHOLD = 200     # $ threshold for receipt-before-refund rule
RESTOCK_FEE_RATE = 0.15        # restocking fee on 'no_longer_needed' for repeat returners
REPEAT_RETURNS_90D = 3         # prior returns in 90 days that make a customer a repeat returner
INR_DENY_RATE = 0.70           # share of cluster-address INR claims expected to be denied after investigation
TIER_HIGH_CUTOFF = 4           # risk points >= this -> High
TIER_MED_CUTOFF = 2            # risk points >= this -> Medium
