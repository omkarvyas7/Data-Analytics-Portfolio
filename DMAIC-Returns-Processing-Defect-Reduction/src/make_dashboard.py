"""Build the Tableau/QuickSight extract and a matplotlib preview of the dashboard.

Outputs: dashboard/tableau_extract.csv (day x site x shift x category grain),
dashboard/tableau_defects_extract.csv (one row per audited defect, for the Pareto), screenshots/dashboard.png
The PNG follows the layout in dashboard/dashboard_spec.md.
"""
from __future__ import annotations

import json
import textwrap
import sqlite3
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
DB = ROOT / "data" / "returns_dmaic.db"
DASH = ROOT / "dashboard"
SHOTS = ROOT / "screenshots"
NAVY, TEAL, ORANGE, RED, GREY, GREEN = "#1f3b57", "#2a9d8f", "#f4a261", "#d62828", "#8d99ae", "#2d6a4f"

EXTRACT_SQL = """
WITH a AS (
    SELECT op_date, site_id, shift, category, COUNT(*) AS audited_units, SUM(is_defect) AS defects,
           SUM(CASE WHEN defect_direction LIKE 'Upgrade%' THEN 1 ELSE 0 END) AS upgrade_defects
    FROM v_audited GROUP BY op_date, site_id, shift, category
)
SELECT u.op_date, u.week_start, u.month, u.phase, u.site_id, u.is_pilot_site, u.shift, u.category,
       COUNT(*)                                  AS units,
       COALESCE(a.audited_units, 0)              AS audited_units,
       COALESCE(a.defects, 0)                    AS defects,
       COALESCE(a.upgrade_defects, 0)            AS upgrade_defects,
       SUM(CASE WHEN u.tenure_days < 30 THEN 1 ELSE 0 END) AS units_by_new_associates,
       ROUND(SUM(u.potential_recovery_usd), 2)   AS potential_recovery_usd,
       ROUND(SUM(u.recovery_achieved_usd), 2)    AS recovery_achieved_usd,
       ROUND(SUM(u.recovery_leakage_usd), 2)     AS recovery_leakage_usd,
       SUM(u.waste_flag)                         AS waste_units,
       SUM(u.customer_complaint_flag)            AS complaints,
       SUM(u.regrade_flag)                       AS regrades,
       ROUND(SUM(u.dock_to_disposition_hrs), 2)  AS cycle_hrs_sum,
       COUNT(u.dock_to_disposition_hrs)          AS cycle_units,
       SUM(u.sla_breach_flag)                    AS sla_breaches
FROM v_units u
LEFT JOIN a ON a.op_date = u.op_date AND a.site_id = u.site_id AND a.shift = u.shift AND a.category = u.category
GROUP BY u.op_date, u.week_start, u.month, u.phase, u.site_id, u.is_pilot_site, u.shift, u.category
ORDER BY u.op_date, u.site_id, u.shift, u.category
"""


def kpi(ax, title, value, sub, color=NAVY):
    ax.axis("off")
    ax.add_patch(plt.Rectangle((0, 0), 1, 1, transform=ax.transAxes, color="#f1f5f9", zorder=0))
    ax.text(0.5, 0.78, title, ha="center", fontsize=9, color="#475569", transform=ax.transAxes)
    ax.text(0.5, 0.42, value, ha="center", fontsize=17, fontweight="bold", color=color, transform=ax.transAxes)
    ax.text(0.5, 0.13, sub, ha="center", fontsize=8, color="#475569", transform=ax.transAxes)


def main() -> None:
    DASH.mkdir(exist_ok=True)
    SHOTS.mkdir(exist_ok=True)
    con = sqlite3.connect(DB)
    ext = pd.read_sql_query(EXTRACT_SQL, con)
    defects = pd.read_sql_query(
        "SELECT audit_id, op_date, week_start, month, phase, site_id, shift, category, tenure_band, sop_version, "
        "assigned_disposition, audited_disposition, defect_direction, defect_cause, "
        "ROUND(recovery_leakage_usd, 2) AS recovery_leakage_usd, waste_flag "
        "FROM v_audited WHERE is_defect = 1 ORDER BY op_date", con)
    con.close()
    defects.to_csv(DASH / "tableau_defects_extract.csv", index=False)
    print(f"tableau_defects_extract.csv rows={len(defects):,}")
    ext.to_csv(DASH / "tableau_extract.csv", index=False)
    print(f"tableau_extract.csv rows={len(ext):,}")

    m = json.loads((PROC / "metrics.json").read_text())
    pc = pd.read_csv(PROC / "p_chart_data.csv", parse_dates=["week_start"])
    pc["signal"] = pc["signal"].fillna("")
    par = pd.read_csv(PROC / "03_defect_pareto_by_cause.csv")
    base = pd.read_csv(PROC / "02_baseline_defect_rate_dpmo_sigma.csv")
    pilot = pd.read_csv(PROC / "08_pilot_pre_post.csv")
    ext["month"] = pd.to_datetime(ext["month"])
    mon = ext.groupby("month")[["recovery_achieved_usd", "recovery_leakage_usd", "waste_units", "units"]].sum()

    plt.rcParams.update({"font.family": "DejaVu Sans", "axes.spines.top": False, "axes.spines.right": False})
    fig = plt.figure(figsize=(17, 10.5))
    gs = fig.add_gridspec(2, 6, height_ratios=[1.25, 1.2], hspace=0.45, wspace=0.6, top=0.74, bottom=0.07)
    tiles = [fig.add_axes([0.035 + i * 0.158, 0.85, 0.145, 0.095]) for i in range(6)]
    fig.suptitle("Disposition Quality Control Dashboard: returns processing network (synthetic data, Jul 2025 to Jun 2026)",
                 fontsize=14, fontweight="bold", color=NAVY, y=0.99)

    kpi(tiles[0], "Defect rate (audited)", f"{m['network_control_rate']:.1%}",
        f"Control | baseline {m['network_baseline_rate']:.1%}", TEAL)
    kpi(tiles[1], "DPMO / sigma", f"{m['control_dpmo']:,.0f}",
        f"sigma {m['control_sigma']:.2f} | baseline {m['baseline_sigma']:.2f}")
    kpi(tiles[2], "First-pass yield", f"{m['control_fpy']:.1%}", f"baseline {m['baseline_fpy']:.1%}")
    kpi(tiles[3], "Recovery rate ($ achieved/potential)", f"{m['recovery_rate_control']:.1%}",
        f"baseline {m['recovery_rate_baseline']:.1%}")
    kpi(tiles[4], "Waste units per 10k", f"{m['waste10k_control']:.1f}",
        f"baseline {m['waste10k_baseline']:.1f}")
    kpi(tiles[5], "Recovery $ protected / yr", f"${m['annual_dollars'] / 1000:,.0f}k",
        f"{m['defects_avoided']:,.0f} defects avoided", GREEN)

    ax = fig.add_subplot(gs[0, :4])
    for ph, g in pc.groupby("phase", sort=False):
        ax.step(g.week_start, g.ucl * 100, where="mid", color=RED, lw=0.9, ls="--")
        ax.step(g.week_start, g.lcl * 100, where="mid", color=RED, lw=0.9, ls="--")
        ax.plot(g.week_start, g.center * 100, color=GREEN, lw=1.2)
    ax.plot(pc.week_start, pc.defect_rate * 100, color=NAVY, marker="o", ms=3.5, lw=1.2)
    o = pc[pc.signal != ""]
    ax.scatter(o.week_start, o.defect_rate * 100, s=60, facecolors="none", edgecolors=RED, lw=1.6)
    ax.axhline(m["target_defect_rate"] * 100, color=TEAL, ls=":", lw=1.2)
    ax.axvspan(pd.Timestamp("2026-03-02"), pd.Timestamp("2026-04-27"), color=ORANGE, alpha=0.13)
    ax.axvspan(pd.Timestamp("2026-04-27"), pc.week_start.max(), color=TEAL, alpha=0.10)
    ax.text(pd.Timestamp("2026-03-05"), 11.7, "Pilot\n(RC-CENTRAL)", fontsize=8, color="#9a5b1f")
    ax.text(pd.Timestamp("2026-05-01"), 11.7, "Control\n(rollout)", fontsize=8, color=GREEN)
    ax.set_title("Weekly defect rate p-chart with 3-sigma limits (dotted = 3.5% target)", fontsize=10.5, fontweight="bold")
    ax.set_ylabel("Defect rate %")

    ax = fig.add_subplot(gs[0, 4:])
    labels = [textwrap.fill(c, 16, break_long_words=False) for c in par.defect_cause][::-1]
    ax.barh(labels, par.defects[::-1], color=NAVY)
    ax2 = ax.twiny()
    ax2.plot(par.cumulative_share[::-1] * 100, labels, color=ORANGE, marker="o")
    ax2.set_xlim(0, 105)
    ax2.set_xlabel("Cumulative %", fontsize=8)
    ax.set_title("Pareto: baseline defects by root cause", fontsize=10.5, fontweight="bold", pad=28)
    ax.tick_params(axis="y", labelsize=8)
    ax.set_xlabel("Defects")

    ax = fig.add_subplot(gs[1, :2])
    s = base[base.site_id != "NETWORK"].pivot(index="site_id", columns="phase", values="defect_rate")[["Baseline", "Pilot", "Control"]]
    x = range(len(s))
    for i, (ph, col) in enumerate(zip(s.columns, [GREY, ORANGE, TEAL])):
        bars = ax.bar([k + (i - 1) * 0.27 for k in x], s[ph] * 100, 0.27, color=col, label=ph)
        for b, v in zip(bars, s[ph] * 100):
            ax.text(b.get_x() + b.get_width() / 2, v + 0.1, f"{v:.1f}", ha="center", fontsize=7)
    ax.set_xticks(list(x), s.index, fontsize=8)
    ax.axhline(m["target_defect_rate"] * 100, color=TEAL, ls=":", lw=1.2)
    ax.set_title("Site comparison: defect rate % by phase", fontsize=10.5, fontweight="bold")
    ax.legend(fontsize=8, frameon=False)

    ax = fig.add_subplot(gs[1, 2:4])
    ax.bar(mon.index, mon.recovery_achieved_usd / 1000, width=20, color=TEAL, label="Achieved")
    ax.bar(mon.index, mon.recovery_leakage_usd / 1000, width=20, bottom=mon.recovery_achieved_usd / 1000, color=RED,
           label="Leakage (potential - achieved)")
    for d, lv, av in zip(mon.index, mon.recovery_leakage_usd, mon.recovery_achieved_usd):
        ax.text(d, (av + lv) / 1000 + 8, f"${lv / 1000:.0f}k", ha="center", fontsize=7, color=RED)
    ax.set_title("Recovery value by month ($k): achieved vs leakage", fontsize=10.5, fontweight="bold")
    ax.legend(fontsize=8, frameon=False, loc="upper left")
    ax.tick_params(axis="x", labelsize=7, rotation=45)

    ax = fig.add_subplot(gs[1, 4:])
    groups = ["Pilot site (RC-CENTRAL)", "Comparison sites"]
    for i, (ph, col) in enumerate(zip(["Baseline", "Pilot", "Control"], [GREY, ORANGE, TEAL])):
        v = [pilot[(pilot.site_group == g) & (pilot.phase == ph)].defect_rate.iloc[0] * 100 for g in groups]
        bars = ax.bar([k + (i - 1) * 0.27 for k in range(2)], v, 0.27, color=col, label=ph)
        for b, val in zip(bars, v):
            ax.text(b.get_x() + b.get_width() / 2, val + 0.1, f"{val:.1f}%", ha="center", fontsize=7.5)
    ax.set_xticks([0, 1], ["Pilot site\nRC-CENTRAL", "Comparison\nsites"], fontsize=8)
    ax.set_title(f"Pilot before/after (z-test p = {m['pilot_p']:.1e})", fontsize=10.5, fontweight="bold")
    ax.legend(fontsize=8, frameon=False)

    fig.text(0.01, 0.005, "Filters in the Tableau build: date range, site, shift, category, phase. Source: dashboard/tableau_extract.csv. "
             "Synthetic data generated by src/generate_data.py.", fontsize=8, color="#64748b")
    fig.savefig(SHOTS / "dashboard.png", dpi=105, bbox_inches="tight")
    plt.close(fig)
    print("saved screenshots/dashboard.png")


if __name__ == "__main__":
    main()
