"""Shared paths and constants for the Returns Program Health WBR pipeline."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
DB_PATH = ROOT / "data" / "returns_wbr.db"
SQL_DIR = ROOT / "sql"
EXCEL_DIR = ROOT / "excel"
REPORTS_DIR = ROOT / "reports"
CHART_DIR = REPORTS_DIR / "charts"
DASH_DIR = ROOT / "dashboard"
SHOTS = ROOT / "screenshots"
DOCS = ROOT / "docs"
NOTEBOOKS = ROOT / "notebooks"

SEED = 20261105
DATA_START = "2025-05-05"   # Monday
DATA_END = "2026-11-01"     # Sunday  (78 full weeks, ~18 months)
DEFAULT_WEEK = "2026-10-26"  # Monday of the example WBR week (Oct 26 to Nov 1, 2026)

# Ordered list of WBR KPIs (must match data/raw/kpi_targets.csv)
KPI_ORDER = [
    "return_rate", "refund_cycle_days", "contacts_per_return", "resale_pct",
    "liquidation_pct", "recovery_rate", "waste_units", "cost_per_return",
]

RAG_COLORS = {"Green": "#2E7D32", "Amber": "#F9A825", "Red": "#C62828",
              "Complete": "#607D8B"}
RAG_FILLS = {"Green": "C8E6C9", "Amber": "FFE082", "Red": "EF9A9A", "Complete": "CFD8DC"}


def fmt_kpi(value, unit):
    """Format a KPI value for narrative / tables."""
    if value is None:
        return "n/a"
    try:
        if value != value:  # NaN
            return "n/a"
    except TypeError:
        return "n/a"
    if unit == "pct":
        return f"{value * 100:.1f}%"
    if unit == "usd":
        return f"${value:,.2f}"
    if unit == "days":
        return f"{value:.2f} days"
    if unit == "units":
        return f"{value:,.0f}"
    return f"{value:.3f}"


def fmt_delta(value, unit):
    """Format an absolute change (pct KPIs shown in percentage points)."""
    if value is None or value != value:
        return "n/a"
    sign = "+" if value >= 0 else "-"
    v = abs(value)
    if unit == "pct":
        return f"{sign}{v * 100:.1f} pts"
    if unit == "usd":
        return f"{sign}${v:,.2f}"
    if unit == "days":
        return f"{sign}{v:.2f} days"
    if unit == "units":
        return f"{sign}{v:,.0f}"
    return f"{sign}{v:.3f}"
