"""Post-build checks: workbooks, docs, notebook, PDF, extract reconciliation and number traceability.

Exits non-zero if any check fails. Called at the end of run_all.py.
"""
import sqlite3
import sys
from datetime import date, timedelta

import nbformat
import pandas as pd
import pypdfium2 as pdfium
from docx import Document
from openpyxl import load_workbook

from config import DB_PATH, DEFAULT_WEEK, DOCS, EXCEL_DIR, NOTEBOOKS, PROCESSED, REPORTS_DIR, ROOT, DASH_DIR, fmt_kpi

WEEK = DEFAULT_WEEK
results = []


def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))


def formulas(ws):
    return [c.value for row in ws.iter_rows() for c in row if isinstance(c.value, str) and c.value.startswith("=")]


def main():
    # ---- WBR workbook
    wb = load_workbook(EXCEL_DIR / f"Returns_WBR_{WEEK}.xlsx")
    need = ["WBR Summary", "Trends", "Targets & Inputs", "Weekly KPI Data", "Top Movers", "Refund Cycle Drivers",
            "Program Health", "Risks", "Gap List"]
    check("WBR sheets present", all(s in wb.sheetnames for s in need), ", ".join(wb.sheetnames))
    fs = formulas(wb["WBR Summary"])
    check("WBR summary formula-driven (INDEX/MATCH, AVERAGEIFS, RAG IF)",
          sum("INDEX(" in f for f in fs) >= 24 and sum("AVERAGEIFS" in f for f in fs) == 8 and sum('"Amber",' in f for f in fs) >= 8,
          f"{len(fs)} formulas")
    n_charts = sum(len(wb[s]._charts) for s in wb.sheetnames)
    check("WBR native charts", n_charts >= 10, f"{n_charts} charts")
    check("WBR conditional formatting", len(wb["WBR Summary"].conditional_formatting) >= 2 and len(wb["Program Health"].conditional_formatting) >= 1)
    # Emulate the Excel RAG formula from workbook values and compare to SQL RAG (column Q)
    vals = list(wb["Weekly KPI Data"].values)
    wd = pd.DataFrame(vals[1:], columns=list(vals[0])).set_index("week_start")
    tgt = pd.DataFrame(list(wb["Targets & Inputs"].iter_rows(min_row=4, max_row=11, max_col=6, values_only=True)),
                       columns=["kpi", "name", "unit", "direction", "target", "band"]).set_index("kpi")
    ws = wb["WBR Summary"]
    mism = []
    for row in ws.iter_rows(min_row=1, max_row=40, values_only=True):
        if row[0] in tgt.index and row[16] in ("Green", "Amber", "Red"):
            t = tgt.loc[row[0]]
            v = float(wd.loc[pd.Timestamp(WEEK), row[0]])
            if t.direction == "lower":
                rag = "Green" if v <= t.target else ("Amber" if v <= t.target * (1 + t.band) else "Red")
            else:
                rag = "Green" if v >= t.target else ("Amber" if v >= t.target * (1 - t.band) else "Red")
            if rag != row[16]:
                mism.append(row[0])
    check("Excel RAG logic == SQL RAG", not mism, f"mismatches: {mism}")

    # ---- Tracker workbook
    tb = load_workbook(EXCEL_DIR / "Program_Tracker.xlsx")
    tf = formulas(tb["Milestones"]) + formulas(tb["Status Summary"])
    check("Tracker XLOOKUP owner lookup", sum("XLOOKUP" in f for f in tf) >= 28 * 3)
    check("Tracker COUNTIFS/AVERAGEIFS/MAXIFS summary",
          any("COUNTIFS" in f for f in tf) and any("AVERAGEIFS" in f for f in tf) and any("MAXIFS" in f for f in tf))
    check("Tracker Gantt conditional formatting", len(tb["Milestones"].conditional_formatting) >= 4)
    check("Tracker native chart", len(tb["Status Summary"]._charts) == 1)
    check("Tracker defined name AsOf", "AsOf" in tb.defined_names)

    # ---- Docs
    for name in ["BRD_Returns_Program_Health_Dashboard", "Program_Plan_RACI_Risks"]:
        d = Document(DOCS / f"{name}.docx")
        check(f"docx opens: {name}", len(d.paragraphs) > 20 and len(d.tables) >= 4, f"{len(d.paragraphs)} paras, {len(d.tables)} tables")
    for name in ["Stakeholder_Communication_Plan", "meeting_notes_stakeholder_alignment", "schedule_refresh"]:
        check(f"md exists: {name}", (DOCS / f"{name}.md").stat().st_size > 1000)

    # ---- Notebook executed, no errors
    nb = nbformat.read(NOTEBOOKS / "analysis.ipynb", as_version=4)
    cc = [c for c in nb.cells if c.cell_type == "code"]
    errs = [o for c in cc for o in c.get("outputs", []) if o.get("output_type") == "error"]
    check("notebook executed without errors", all(c.get("execution_count") for c in cc) and not errs, f"{len(cc)} code cells")

    # ---- PDF page count
    pdf = pdfium.PdfDocument(str(REPORTS_DIR / f"WBR_{WEEK}.pdf"))
    check("PDF is 2-3 pages", 2 <= len(pdf) <= 3, f"{len(pdf)} pages")
    pdf.close()

    # ---- Extract reconciles to the SQL KPI layer
    ext = pd.read_csv(DASH_DIR / "tableau_extract.csv")
    e = ext[ext.week_start == WEEK]
    con = sqlite3.connect(DB_PATH)
    v = pd.read_sql("SELECT * FROM v_weekly_kpi WHERE week_start = ?", con, params=[WEEK]).iloc[0]
    rr = e.return_units.sum() / e.units_shipped.sum()
    cyc = e.refund_cycle_hours.sum() / 24 / e.cycle_units.sum()
    rec = e.recovered_usd.sum() / e.refund_usd.sum()
    check("extract reconciles: return rate", abs(rr - v.return_rate) < 1e-9)
    check("extract reconciles: refund cycle", abs(cyc - v.refund_cycle_days) < 1e-4)
    check("extract reconciles: recovery rate", abs(rec - v.recovery_rate) < 1e-6)

    # ---- Driver decomposition sums to program change
    drv = pd.read_csv(PROCESSED / f"wbr_{WEEK}" / "05_refund_cycle_driver_channel.csv")
    d0 = date.fromisoformat(WEEK)
    base_weeks = [(d0 - timedelta(days=n)).isoformat() for n in (56, 49, 42, 35)]
    q = "SELECT SUM(refund_cycle_hours)/24.0/SUM(cycle_units) FROM weekly_fact WHERE week_start IN ({})"
    base = con.execute(q.format(",".join("?" * 4)), base_weeks).fetchone()[0]
    cur = con.execute(q.format("?"), [WEEK]).fetchone()[0]
    check("rate + mix effects == program change", abs(drv.total_effect_days.sum() - (cur - base)) < 1e-9,
          f"{drv.total_effect_days.sum():.4f} vs {cur - base:.4f}")
    dup = con.execute("SELECT COUNT(*) FROM (SELECT date, marketplace, category, channel, COUNT(*) n FROM returns_daily GROUP BY 1,2,3,4 HAVING n > 1)").fetchone()[0]
    check("no duplicate keys after cleaning", dup == 0)
    con.close()

    # ---- README numbers trace to outputs
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    rag = pd.read_csv(PROCESSED / f"wbr_{WEEK}" / "02_kpi_vs_target_rag.csv").set_index("kpi")
    toks = [fmt_kpi(rag.loc[k_, "actual"], rag.loc[k_, "unit"]) for k_ in ["refund_cycle_days", "contacts_per_return", "recovery_rate", "waste_units"]]
    check("README quotes current KPI values", all(t in readme for t in toks), ", ".join(toks))
    check("README has repo map and preview", "What's in the repo" in readme and "screenshots/dashboard.png" in readme)
    size_mb = sum(p.stat().st_size for p in ROOT.rglob("*") if p.is_file() and p.suffix != ".db") / 1e6
    check("repo size < 50 MB (excl. db)", size_mb < 50, f"{size_mb:.1f} MB")

    w = max(len(n) for n, _, _ in results)
    for n, ok, d in results:
        print(f"{'PASS' if ok else 'FAIL'}  {n:<{w}}  {d}")
    failed = [n for n, ok, _ in results if not ok]
    print(f"verify_outputs: {len(results) - len(failed)}/{len(results)} checks passed")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
