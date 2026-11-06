"""Write the Tableau/QuickSight extract and render the dashboard preview + README screenshots.

Outputs
  dashboard/tableau_extract.csv          tidy weekly extract (sql/11_tableau_extract.sql)
  dashboard/kpi_weekly_long.csv          week x KPI with target and RAG (for KPI tiles / trend sheet)
  dashboard/program_health.csv           initiative RAG table for the BI program-health sheet
  screenshots/dashboard.png              matplotlib preview of the dashboard layout in dashboard_spec.md
  screenshots/*.png                      key charts copied from the WBR run
  screenshots/wbr_pdf_page1.png          rasterised page 1 of reports/WBR_<week>.pdf (pypdfium2)
"""
import shutil
import sqlite3
from datetime import date, timedelta

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import pypdfium2 as pdfium

import charts
from config import (CHART_DIR, DASH_DIR, DB_PATH, DEFAULT_WEEK, PROCESSED, RAG_COLORS, REPORTS_DIR, SHOTS,
                    SQL_DIR, fmt_kpi, fmt_delta)
from run_sql import run_file


def kpi_tiles(fig, gs_row, rag, summary):
    s = summary.set_index("kpi")
    for j, (_, r) in enumerate(rag.iterrows()):
        ax = fig.add_subplot(gs_row[j])
        ax.set_xticks([])
        ax.set_yticks([])
        col = RAG_COLORS[r["rag"]]
        for sp in ax.spines.values():
            sp.set_edgecolor(col)
            sp.set_linewidth(2.5)
        ax.text(0.5, 0.80, charts.LABELS[r["kpi"]], ha="center", fontsize=8, color="#37474F", transform=ax.transAxes)
        ax.text(0.5, 0.48, fmt_kpi(r["actual"], r["unit"]).replace(" days", "d"), ha="center", fontsize=14,
                weight="bold", color="#212121", transform=ax.transAxes)
        ax.text(0.5, 0.24, f"target {fmt_kpi(r['target'], r['unit']).replace(' days', 'd')}", ha="center", fontsize=7,
                color="#616161", transform=ax.transAxes)
        ax.text(0.5, 0.07, f"WoW {fmt_delta(s.loc[r['kpi'], 'wow_abs'], r['unit']).replace(' days', 'd')}  |  {r['rag']}",
                ha="center", fontsize=7, color=col, transform=ax.transAxes)


def dashboard_png(res, week, path):
    fig = plt.figure(figsize=(16, 10.5))
    gs = fig.add_gridspec(3, 8, height_ratios=[0.75, 2.1, 2.7], hspace=0.45, wspace=0.35,
                          left=0.04, right=0.985, top=0.9, bottom=0.05)
    wk_end = (date.fromisoformat(week) + timedelta(days=6)).isoformat()
    fig.text(0.04, 0.955, "Returns Program Health Dashboard", fontsize=18, weight="bold", color="#232F3E")
    fig.text(0.04, 0.927, f"Week {week} to {wk_end}  |  Filters: Marketplace = All, Category = All, Channel = All  |  "
             "Preview rendered with matplotlib from dashboard/*.csv following dashboard/dashboard_spec.md (synthetic data)",
             fontsize=9, color="#616161")
    kpi_tiles(fig, [gs[0, j] for j in range(8)], res["kpi_rag"], res["kpi_summary"])
    rag = dict(zip(res["kpi_rag"]["kpi"], res["kpi_rag"]["rag"]))
    for j, kpi in enumerate(["refund_cycle_days", "contacts_per_return", "recovery_rate", "cost_per_return"]):
        ax = fig.add_subplot(gs[1, 2 * j:2 * j + 2])
        charts.plot_kpi_trend(ax, res["kpi_trend"], kpi, rag[kpi], weeks=52)
        if j == 0:
            ax.legend(fontsize=7, frameon=False)
    # program health RAG table
    ax = fig.add_subplot(gs[2, 0:4])
    ax.axis("off")
    ph = res["program_health"]
    cols = ["Initiative", "Team", "Done", "Risk", "Blkd", "Slip", "High", "RAG"]
    cell = [[r.initiative, r.team, f"{r.milestones_complete}/{r.milestones_total}", r.milestones_at_risk,
             r.blocked_by_dependency, f"{r.max_slip_days} d", r.open_high_risks, r.program_rag] for r in ph.itertuples()]
    t = ax.table(cellText=cell, colLabels=cols, bbox=[0, 0.18, 1.0, 0.8], cellLoc="center",
                 colWidths=[0.36, 0.25, 0.06, 0.06, 0.06, 0.07, 0.06, 0.08])
    t.auto_set_font_size(False)
    t.set_fontsize(7.5)
    for (i, j), c in t.get_celld().items():
        c.set_edgecolor("#BDBDBD")
        if i == 0:
            c.set_facecolor("#232F3E")
            c.set_text_props(color="white", weight="bold")
        elif j == 7:
            c.set_facecolor(RAG_COLORS[cell[i - 1][7]])
            c.set_text_props(color="white", weight="bold")
        if i > 0 and j in (0, 1):
            c.set_text_props(ha="left")
            c._loc = "left"
    ax.set_title("Program health (RAG)", fontsize=10, loc="left")
    gaps = res["gap_list"]
    ax.text(0.0, 0.02, f"Gap list: {int((gaps['priority'] == 'P1').sum())} P1 and {int((gaps['priority'] == 'P2').sum())} P2 asks "
            f"routed to {gaps['team'].nunique()} teams.\nRisk = milestones at risk, Blkd = blocked by dependency, Slip = max schedule slip, High = open High risks.", fontsize=8.5, transform=ax.transAxes, color="#37474F")
    ax2 = fig.add_subplot(gs[2, 5:8])
    charts.plot_milestone_timeline(ax2, res["milestones"], wk_end)
    ax2.set_title("Milestone timeline", fontsize=10, loc="left")
    fig.savefig(path, dpi=110)
    plt.close(fig)


def main(week=DEFAULT_WEEK):
    from run_sql import run_wbr_queries
    DASH_DIR.mkdir(parents=True, exist_ok=True)
    SHOTS.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    ext = run_file(con, "11_tableau_extract.sql")
    ext.to_csv(DASH_DIR / "tableau_extract.csv", index=False)
    con.close()
    res = run_wbr_queries(week)
    trend = res["kpi_trend"].copy()
    tg = pd.read_csv(PROCESSED / f"wbr_{week}" / "02_kpi_vs_target_rag.csv")[["kpi", "display_name", "unit", "direction", "owner_team"]]
    trend.merge(tg, on="kpi").to_csv(DASH_DIR / "kpi_weekly_long.csv", index=False)
    res["program_health"].to_csv(DASH_DIR / "program_health.csv", index=False)
    res["milestones"].to_csv(DASH_DIR / "milestones.csv", index=False)

    dashboard_png(res, week, SHOTS / "dashboard.png")
    for src, dst in [(f"kpi_trends_{week}.png", "kpi_trends.png"), (f"refund_cycle_driver_{week}.png", "refund_cycle_driver.png"),
                     (f"top_movers_{week}.png", "top_movers_category.png"), (f"milestone_timeline_{week}.png", "milestone_timeline.png")]:
        shutil.copyfile(CHART_DIR / src, SHOTS / dst)
    pdf = pdfium.PdfDocument(str(REPORTS_DIR / f"WBR_{week}.pdf"))
    pdf[0].render(scale=1.6).to_pil().save(SHOTS / "wbr_pdf_page1.png")
    n_pages = len(pdf)
    pdf.close()
    print(f"make_dashboard: extract {len(ext):,} rows; dashboard.png + {5} screenshots; PDF has {n_pages} pages")


if __name__ == "__main__":
    main()
