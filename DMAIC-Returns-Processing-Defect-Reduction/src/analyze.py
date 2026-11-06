"""Stats and charts for the DMAIC project.

Produces (data/processed/): p_chart_data.csv, imr_chart_data.csv, hypothesis_tests.csv,
logit_odds_ratios.csv, capability.csv, impact_summary.csv, metrics.json
Charts (screenshots/): pareto_defect_causes.png, p_chart_weekly_defect_rate.png,
imr_chart_cycle_time.png, value_stream_cycle_time.png, pilot_before_after.png,
defect_drivers_odds_ratios.png, cycle_time_capability.png; docs/fishbone_ishikawa.png
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from scipy import stats
from statsmodels.stats.proportion import proportion_confint, proportions_ztest

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
DB = ROOT / "data" / "returns_dmaic.db"
SHOTS = ROOT / "screenshots"
DOCS = ROOT / "docs"

USL_HRS = 48.0          # dock-to-disposition SLA
TARGET_DEFECT = 0.035   # project goal (charter)
NAVY, TEAL, ORANGE, RED, GREY, GREEN = "#1f3b57", "#2a9d8f", "#f4a261", "#d62828", "#8d99ae", "#2d6a4f"
PHASE_COL = {"Baseline": GREY, "Pilot": ORANGE, "Control": TEAL}

plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "axes.spines.top": False,
                     "axes.spines.right": False, "axes.titleweight": "bold", "figure.dpi": 110})


def load() -> tuple[pd.DataFrame, pd.DataFrame]:
    con = sqlite3.connect(DB)
    aud = pd.read_sql_query("SELECT * FROM v_audited", con, parse_dates=["op_date", "week_start"])
    units = pd.read_sql_query(
        "SELECT unit_id, op_date, site_id, phase, is_pilot_site, dock_to_disposition_hrs, waste_flag, "
        "potential_recovery_usd, recovery_achieved_usd, recovery_leakage_usd, customer_complaint_flag "
        "FROM v_units", con, parse_dates=["op_date"])
    con.close()
    return aud, units


def pareto_chart(m: dict) -> None:
    p = pd.read_csv(PROC / "03_defect_pareto_by_cause.csv")
    fig, ax = plt.subplots(figsize=(10, 5.2))
    bars = ax.bar(p.defect_cause, p.defects, color=[NAVY if c <= 0.80 else GREY for c in p.cumulative_share.shift(fill_value=0)])
    ax.set_ylabel("Defects in baseline audit sample")
    ax.set_title("Pareto of disposition defects by root cause (baseline, Jul 2025 to Feb 2026)")
    ax.tick_params(axis="x", rotation=25)
    for lab in ax.get_xticklabels():
        lab.set_ha("right")
    for b, v in zip(bars, p.defects):
        ax.text(b.get_x() + b.get_width() / 2, v + 2, str(v), ha="center", fontsize=9)
    ax2 = ax.twinx()
    ax2.plot(p.defect_cause, p.cumulative_share * 100, color=ORANGE, marker="o", lw=2)
    ax2.axhline(80, color=RED, ls="--", lw=1)
    ax2.text(len(p) - 0.6, 81.5, "80%", color=RED, fontsize=9)
    ax2.set_ylim(0, 105)
    ax2.set_ylabel("Cumulative %")
    ax2.spines["top"].set_visible(False)
    fig.tight_layout()
    fig.savefig(SHOTS / "pareto_defect_causes.png")
    plt.close(fig)
    top = p[p.cumulative_share.shift(fill_value=0) < 0.80]  # causes that make up the first 80%
    m["pareto_vital_few"] = top.defect_cause.tolist()
    m["pareto_vital_few_share"] = float(top.defects.sum() / p.defects.sum())
    m["pareto_top_cause"] = p.defect_cause.iloc[0]
    m["pareto_top_cause_share"] = float(p.share.iloc[0])
    m["pareto_top3_share"] = float(p.cumulative_share.iloc[2])
    m["pareto_top3"] = p.defect_cause.iloc[:3].tolist()


def p_chart(m: dict) -> pd.DataFrame:
    w = pd.read_csv(PROC / "09_weekly_control_chart_feed.csv", parse_dates=["week_start"])
    w = w[w.partial_week_flag == 0].copy()
    base = w[w.phase == "Baseline"]
    ctrl = w[w.phase == "Control"]
    pbar_b = base.defects.sum() / base.audited_units.sum()
    pbar_c = ctrl.defects.sum() / ctrl.audited_units.sum()
    w["center"] = np.where(w.phase == "Control", pbar_c, pbar_b)
    se = np.sqrt(w.center * (1 - w.center) / w.audited_units)
    w["ucl"] = w.center + 3 * se
    w["lcl"] = (w.center - 3 * se).clip(lower=0)
    w["signal"] = np.where(w.defect_rate > w.ucl, "Above UCL", np.where(w.defect_rate < w.lcl, "Below LCL", ""))
    w.to_csv(PROC / "p_chart_data.csv", index=False)

    fig, ax = plt.subplots(figsize=(11, 5))
    for ph, g in w.groupby("phase", sort=False):
        ax.step(g.week_start, g.ucl * 100, where="mid", color=RED, lw=1, ls="--")
        ax.step(g.week_start, g.lcl * 100, where="mid", color=RED, lw=1, ls="--")
        ax.plot(g.week_start, g.center * 100, color=PHASE_COL[ph], lw=1.5)
    ax.plot(w.week_start, w.defect_rate * 100, color=NAVY, marker="o", ms=4, lw=1.2, label="Weekly defect rate (p)")
    out = w[w.signal != ""]
    ax.scatter(out.week_start, out.defect_rate * 100, s=70, facecolors="none", edgecolors=RED, lw=1.8,
               label="Out-of-control signal", zorder=5)
    ax.axhline(TARGET_DEFECT * 100, color=GREEN, lw=1, ls=":", label=f"Target {TARGET_DEFECT:.1%}")
    ax.axvspan(pd.Timestamp("2026-03-02"), pd.Timestamp("2026-04-27"), color=ORANGE, alpha=0.12, label="Pilot at RC-CENTRAL")
    ax.axvspan(pd.Timestamp("2026-04-27"), w.week_start.max() + pd.Timedelta(days=3), color=TEAL, alpha=0.10, label="Control (network rollout)")
    ax.set_ylabel("Defect rate (%)")
    ax.set_title(f"p-chart: weekly disposition defect rate (baseline p-bar {pbar_b:.2%}, control p-bar {pbar_c:.2%})")
    ax.legend(loc="upper right", fontsize=8, ncol=2, frameon=False)
    ax.text(w.week_start.iloc[0], -0.6, "dashed red = UCL / LCL (3-sigma, varies with weekly audit n)", fontsize=8, color=RED)
    fig.tight_layout()
    fig.savefig(SHOTS / "p_chart_weekly_defect_rate.png")
    plt.close(fig)
    m["pchart_baseline_pbar"] = float(pbar_b)
    m["pchart_control_pbar"] = float(pbar_c)
    m["pchart_baseline_weeks"] = int(len(base))
    m["pchart_baseline_signals_above"] = int((base.defect_rate > w.loc[base.index, "ucl"]).sum())
    m["pchart_baseline_signal_weeks"] = [d.strftime("%Y-%m-%d") for d in w.loc[(w.phase == "Baseline") & (w.signal == "Above UCL"), "week_start"]]
    m["pchart_control_signals"] = int((w.loc[w.phase == "Control", "signal"] != "").sum())
    m["pchart_control_weeks"] = int(len(ctrl))
    m["pchart_control_avg_n"] = float(ctrl.audited_units.mean())
    return w


def imr_chart(units: pd.DataFrame, m: dict) -> None:
    """I-MR chart of daily mean cycle time. Reference limits come from Jul-Sep 2025 (volume under
    capacity) and run through Apr 2026; the Control period (May-Jun 2026) gets its own limits."""
    d = (units.dropna(subset=["dock_to_disposition_hrs"]).groupby(["op_date", "phase"], as_index=False)
         .dock_to_disposition_hrs.mean().rename(columns={"dock_to_disposition_hrs": "mean_cycle_hrs"}))
    d = d.sort_values("op_date").reset_index(drop=True)
    d["mr"] = d.mean_cycle_hrs.diff().abs()
    ref_mask = d.op_date < pd.Timestamp("2025-10-01")
    ctl_mask = d.phase == "Control"
    d["limit_set"] = np.where(ctl_mask, "Control (May-Jun 2026)", "Reference (Jul-Sep 2025)")
    lim = {}
    for name, mask in [("Reference (Jul-Sep 2025)", ref_mask), ("Control (May-Jun 2026)", ctl_mask)]:
        x = d.loc[mask, "mean_cycle_hrs"].mean()
        mr = d.loc[mask, "mr"].iloc[1:].mean() if mask.iloc[0] else d.loc[mask, "mr"].mean()
        lim[name] = (x, x + 2.66 * mr, max(x - 2.66 * mr, 0), mr)
    d["i_center"] = d.limit_set.map(lambda k: lim[k][0])
    d["i_ucl"] = d.limit_set.map(lambda k: lim[k][1])
    d["i_lcl"] = d.limit_set.map(lambda k: lim[k][2])
    d["mr_center"] = d.limit_set.map(lambda k: lim[k][3])
    d["mr_ucl"] = 3.267 * d.mr_center
    d["i_signal"] = np.where(d.mean_cycle_hrs > d.i_ucl, "Above UCL", np.where(d.mean_cycle_hrs < d.i_lcl, "Below LCL", ""))
    d.to_csv(PROC / "imr_chart_data.csv", index=False)

    fig, (a1, a2) = plt.subplots(2, 1, figsize=(11, 6.5), sharex=True, gridspec_kw={"height_ratios": [2, 1]})
    a1.plot(d.op_date, d.mean_cycle_hrs, color=NAVY, lw=1)
    sig = d[d.i_signal == "Above UCL"]
    a1.scatter(sig.op_date, sig.mean_cycle_hrs, color=RED, s=9, zorder=5, label=f"Above UCL ({len(sig)} days)")
    for name, g in d.groupby("limit_set", sort=False):
        a1.plot(g.op_date, g.i_center, color=GREEN, lw=1.2)
        a1.plot(g.op_date, g.i_ucl, color=RED, ls="--", lw=1)
        a1.plot(g.op_date, g.i_lcl, color=RED, ls="--", lw=1)
        a2.plot(g.op_date, g.mr_center, color=GREEN, lw=1)
        a2.plot(g.op_date, g.mr_ucl, color=RED, ls="--", lw=1)
    xr, ur, lr, _ = lim["Reference (Jul-Sep 2025)"]
    xc, uc, lc, _ = lim["Control (May-Jun 2026)"]
    a1.text(pd.Timestamp("2025-07-03"), ur + 0.6, f"Reference limits: X-bar {xr:.1f} h, UCL {ur:.1f} h, LCL {lr:.1f} h", fontsize=8, color=RED)
    a1.text(pd.Timestamp("2026-04-20"), uc + 2.2, f"Control limits:\nX-bar {xc:.1f} h, UCL {uc:.1f} h", fontsize=8, color=TEAL)
    a1.axvspan(pd.Timestamp("2026-05-01"), d.op_date.max(), color=TEAL, alpha=0.08)
    a1.set_ylabel("Daily mean hours")
    a1.set_title("I-MR chart: daily mean dock-to-disposition hours (post-Q4 backlog is special-cause variation)")
    a1.legend(loc="upper right", fontsize=8, frameon=False)
    a2.plot(d.op_date, d.mr, color=GREY, lw=1)
    a2.set_ylabel("Moving range (h)")
    fig.tight_layout()
    fig.savefig(SHOTS / "imr_chart_cycle_time.png")
    plt.close(fig)
    ref_period = d[~ctl_mask & ~ref_mask]
    m["imr_ref_xbar_hrs"], m["imr_ref_ucl_hrs"], m["imr_ref_lcl_hrs"] = float(xr), float(ur), float(lr)
    m["imr_ctl_xbar_hrs"], m["imr_ctl_ucl_hrs"], m["imr_ctl_lcl_hrs"] = float(xc), float(uc), float(lc)
    m["imr_days_above_ref_ucl_oct_apr"] = int((ref_period.i_signal == "Above UCL").sum())
    m["imr_days_oct_apr"] = int(len(ref_period))
    m["imr_ctl_days_out"] = int((d[ctl_mask].i_signal != "").sum())
    m["imr_peak_daily_mean_hrs"] = float(d.mean_cycle_hrs.max())
    m["imr_peak_day"] = d.loc[d.mean_cycle_hrs.idxmax(), "op_date"].strftime("%Y-%m-%d")

def value_stream_chart(m: dict) -> None:
    v = pd.read_csv(PROC / "10_value_stream_stage_times.csv")
    order = ["Other baseline / pilot months", "Peak backlog (Dec-Jan)", "Control (May-Jun 2026)"]
    stages = v.sort_values("step_order").stage.unique()
    colors = {"Dock wait": "#adb5bd", "Triage / receive scan": TEAL, "Queue to grading": RED,
              "Grading": GREEN, "Routing to disposition": ORANGE}
    fig, ax = plt.subplots(figsize=(11, 4.2))
    for i, per in enumerate(order):
        left = 0
        g = v[v.period == per].set_index("stage")
        for s in stages:
            h = g.loc[s, "mean_hrs"]
            ax.barh(i, h, left=left, color=colors[s], edgecolor="white", label=s if i == 0 else None)
            if h > 1.0:
                ax.text(left + h / 2, i, f"{h:.1f}h", ha="center", va="center", fontsize=8, color="white")
            left += h
        va = g[g.value_added == 1].mean_hrs.sum()
        ax.text(left + 0.3, i, f"total {left:.1f}h | value-added {va:.1f}h ({va / left:.0%})", va="center", fontsize=8)
    ax.set_yticks(range(len(order)), order)
    ax.set_xlabel("Mean hours per unit (dock to disposition)")
    ax.set_title("Value stream: most of the cycle time is waiting, and grading itself takes under an hour")
    ax.legend(ncol=5, fontsize=8, loc="upper center", bbox_to_anchor=(0.5, -0.18), frameon=False)
    ax.set_xlim(0, v.groupby("period").mean_hrs.sum().max() * 1.45)
    fig.tight_layout()
    fig.savefig(SHOTS / "value_stream_cycle_time.png")
    plt.close(fig)
    for per, key in [(order[0], "vs_normal"), (order[1], "vs_peak"), (order[2], "vs_control")]:
        g = v[v.period == per]
        tot = g.mean_hrs.sum()
        m[f"{key}_total_hrs"] = float(tot)
        m[f"{key}_va_share"] = float(g[g.value_added == 1].mean_hrs.sum() / tot)
        m[f"{key}_queue_hrs"] = float(g[g.stage == "Queue to grading"].mean_hrs.iloc[0])


def hypothesis_tests(aud: pd.DataFrame, m: dict) -> None:
    rows = []

    def ztest(name, a_mask, b_mask, alt="smaller"):
        d1, n1 = aud.loc[a_mask, "is_defect"].sum(), a_mask.sum()
        d0, n0 = aud.loc[b_mask, "is_defect"].sum(), b_mask.sum()
        z, p = proportions_ztest([d1, d0], [n1, n0], alternative=alt)
        lo1, hi1 = proportion_confint(d1, n1, method="wilson")
        diff = d1 / n1 - d0 / n0
        se = np.sqrt((d1 / n1) * (1 - d1 / n1) / n1 + (d0 / n0) * (1 - d0 / n0) / n0)
        rows.append({"test": name, "group_after": f"{d1}/{n1}", "rate_after": d1 / n1,
                     "group_before": f"{d0}/{n0}", "rate_before": d0 / n0, "diff_pts": diff,
                     "diff_ci95_low": diff - 1.96 * se, "diff_ci95_high": diff + 1.96 * se,
                     "relative_change": diff / (d0 / n0), "z": z, "p_value": p,
                     "after_rate_ci95": f"{lo1:.4f}-{hi1:.4f}"})
        return rows[-1]

    pilot = aud.is_pilot_site == 1
    r1 = ztest("Pilot site: Pilot vs Baseline (two-proportion z, H1: rate fell)",
               pilot & (aud.phase == "Pilot"), pilot & (aud.phase == "Baseline"))
    r2 = ztest("Comparison sites: Pilot window vs Baseline (two-proportion z)",
               ~pilot & (aud.phase == "Pilot"), ~pilot & (aud.phase == "Baseline"))
    r3 = ztest("Network: Control vs Baseline (two-proportion z)",
               aud.phase == "Control", aud.phase == "Baseline")
    r4 = ztest("Comparison sites: Control (after rollout) vs Pilot window (two-proportion z)",
               ~pilot & (aud.phase == "Control"), ~pilot & (aud.phase == "Pilot"))

    # difference-in-differences: logit with a pilot_site x post interaction, baseline and pilot windows only
    dd = aud[aud.phase.isin(["Baseline", "Pilot"])].copy()
    dd["post"] = (dd.phase == "Pilot").astype(int)
    fit = smf.logit("is_defect ~ is_pilot_site * post", data=dd).fit(disp=False)
    inter = "is_pilot_site:post"
    rows.append({"test": "Difference-in-differences (logit interaction pilot_site x post)",
                 "group_after": "", "rate_after": np.nan, "group_before": "", "rate_before": np.nan,
                 "diff_pts": (r1["diff_pts"] - r2["diff_pts"]), "diff_ci95_low": np.nan, "diff_ci95_high": np.nan,
                 "relative_change": np.nan, "z": fit.tvalues[inter], "p_value": fit.pvalues[inter],
                 "after_rate_ci95": f"odds ratio {np.exp(fit.params[inter]):.2f}"})
    # chi-square: night vs day/swing, baseline only
    b = aud[aud.phase == "Baseline"]
    ct = pd.crosstab(b["shift"] == "Night", b.is_defect)
    chi2, pchi, _, _ = stats.chi2_contingency(ct)
    rows.append({"test": "Chi-square: Night vs Day/Swing defect rate (baseline)", "group_after": "",
                 "rate_after": b[b["shift"] == "Night"].is_defect.mean(), "group_before": "",
                 "rate_before": b[b["shift"] != "Night"].is_defect.mean(), "diff_pts": np.nan,
                 "diff_ci95_low": np.nan, "diff_ci95_high": np.nan, "relative_change": np.nan,
                 "z": chi2, "p_value": pchi, "after_rate_ci95": "statistic column holds chi2"})
    pd.DataFrame(rows).to_csv(PROC / "hypothesis_tests.csv", index=False)

    m.update({
        "pilot_site_baseline_rate": r1["rate_before"], "pilot_site_pilot_rate": r1["rate_after"],
        "pilot_site_n_before": int((pilot & (aud.phase == "Baseline")).sum()),
        "pilot_site_n_after": int((pilot & (aud.phase == "Pilot")).sum()),
        "pilot_z": float(r1["z"]), "pilot_p": float(r1["p_value"]), "pilot_rel_change": float(r1["relative_change"]),
        "pilot_diff_ci_low": float(r1["diff_ci95_low"]), "pilot_diff_ci_high": float(r1["diff_ci95_high"]),
        "comparison_baseline_rate": r2["rate_before"], "comparison_pilot_rate": r2["rate_after"],
        "comparison_p": float(r2["p_value"]),
        "did_pts": float(r1["diff_pts"] - r2["diff_pts"]), "did_p": float(fit.pvalues[inter]),
        "did_odds_ratio": float(np.exp(fit.params[inter])),
        "network_baseline_rate": r3["rate_before"], "network_control_rate": r3["rate_after"],
        "network_z": float(r3["z"]), "network_p": float(r3["p_value"]),
        "network_rel_change": float(r3["relative_change"]),
        "comparison_control_rate": r4["rate_after"], "comparison_rollout_p": float(r4["p_value"]),
        "night_rate": float(b[b["shift"] == "Night"].is_defect.mean()),
        "nonnight_rate": float(b[b["shift"] != "Night"].is_defect.mean()), "night_chi_p": float(pchi),
    })


def drivers_logit(aud: pd.DataFrame, m: dict) -> None:
    b = aud[aud.phase == "Baseline"].copy()
    b["tenure_lt30"] = (b.tenure_days < 30).astype(int)
    b["tenure_30_89"] = ((b.tenure_days >= 30) & (b.tenure_days < 90)).astype(int)
    b["electronics"] = (b.category == "Electronics").astype(int)
    b["true_open_box"] = (b.audited_disposition == "OPEN_BOX").astype(int)
    b["night_shift"] = (b["shift"] == "Night").astype(int)
    b["swing_shift"] = (b["shift"] == "Swing").astype(int)
    b["no_photo_step"] = (b.photo_step_done == 0).astype(int)
    b["peak_backlog_dec_jan"] = b.month.isin(["2025-12", "2026-01"]).astype(int)
    terms = ["tenure_lt30", "tenure_30_89", "electronics", "true_open_box", "night_shift", "swing_shift",
             "no_photo_step", "peak_backlog_dec_jan"]
    fit = smf.logit("is_defect ~ " + " + ".join(terms), data=b).fit(disp=False)
    ci = fit.conf_int()
    labels = {"tenure_lt30": "Associate tenure < 30 days", "tenure_30_89": "Associate tenure 30-89 days",
              "electronics": "Electronics category", "true_open_box": "Item is truly open-box",
              "night_shift": "Night shift (vs Day)", "swing_shift": "Swing shift (vs Day)",
              "no_photo_step": "No photo-grading step", "peak_backlog_dec_jan": "Peak backlog month (Dec-Jan)"}
    o = pd.DataFrame({"driver": [labels[t] for t in terms], "term": terms,
                      "odds_ratio": np.exp(fit.params[terms]).values,
                      "ci95_low": np.exp(ci.loc[terms, 0]).values, "ci95_high": np.exp(ci.loc[terms, 1]).values,
                      "p_value": fit.pvalues[terms].values,
                      "share_of_baseline_audits": [b[t].mean() for t in terms]})
    o = o.sort_values("odds_ratio", ascending=False)
    o.to_csv(PROC / "logit_odds_ratios.csv", index=False)

    fig, ax = plt.subplots(figsize=(9, 4.6))
    y = np.arange(len(o))[::-1]
    ax.errorbar(o.odds_ratio, y, xerr=[o.odds_ratio - o.ci95_low, o.ci95_high - o.odds_ratio],
                fmt="o", color=NAVY, ecolor=GREY, capsize=3)
    ax.axvline(1, color=RED, ls="--", lw=1)
    ax.set_yticks(y, o.driver)
    for yi, (orv, pv) in zip(y, zip(o.odds_ratio, o.p_value)):
        ax.text(o.ci95_high.max() * 1.03, yi, f"OR {orv:.2f}  p={pv:.3g}", va="center", fontsize=8)
    ax.set_xlim(0, o.ci95_high.max() * 1.45)
    ax.set_xlabel("Odds ratio of a misgrade with 95% CI (logistic regression on baseline audits)")
    ax.set_title("Root-cause check: drivers that raise the odds of a disposition defect")
    fig.tight_layout()
    fig.savefig(SHOTS / "defect_drivers_odds_ratios.png")
    plt.close(fig)
    m["logit_n"] = int(fit.nobs)
    m["odds_ratios"] = {r.term: {"or": float(r.odds_ratio), "p": float(r.p_value), "lo": float(r.ci95_low),
                                 "hi": float(r.ci95_high)} for r in o.itertuples()}
    tl = b.groupby("tenure_lt30").is_defect.mean()
    m["tenure_lt30_rate"], m["tenure_ge30_rate"] = float(tl[1]), float(tl[0])
    m["tenure_lt30_share"] = float(b.tenure_lt30.mean())
    el = b.groupby("electronics").is_defect.mean()
    m["electronics_rate"], m["non_electronics_rate"] = float(el[1]), float(el[0])
    ob = b.groupby("true_open_box").is_defect.mean()
    m["open_box_rate"] = float(ob[1])
    ph = b.groupby("no_photo_step").is_defect.mean()
    m["no_photo_rate"], m["photo_rate"] = float(ph[1]), float(ph[0])
    pk = b.groupby("peak_backlog_dec_jan").is_defect.mean()
    m["peak_rate"], m["nonpeak_rate"] = float(pk[1]), float(pk[0])
    nh = b[b.month.isin(["2025-11", "2025-12"])]
    m["tenure_lt30_share_nov_dec"] = float(nh.tenure_lt30.mean())


def capability(units: pd.DataFrame, m: dict) -> None:
    rows = []
    for ph in ["Baseline", "Pilot", "Control"]:
        x = units.loc[(units.phase == ph), "dock_to_disposition_hrs"].dropna()
        lx = np.log(x)
        ppk = (np.log(USL_HRS) - lx.mean()) / (3 * lx.std())
        pct_over = (x > USL_HRS).mean()
        rows.append({"phase": ph, "units": len(x), "mean_hrs": x.mean(), "p50_hrs": x.median(),
                     "p95_hrs": x.quantile(0.95), "usl_hrs": USL_HRS, "pct_over_usl": pct_over,
                     "ppm_over_usl": pct_over * 1e6, "ppk_lognormal": ppk})
    c = pd.DataFrame(rows)
    c.to_csv(PROC / "capability.csv", index=False)
    b = units.loc[units.phase == "Baseline", "dock_to_disposition_hrs"].dropna()
    k = units.loc[units.phase == "Control", "dock_to_disposition_hrs"].dropna()
    fig, ax = plt.subplots(figsize=(10, 4.4))
    bins = np.linspace(0, 80, 81)
    ax.hist(b.clip(upper=80), bins=bins, color=GREY, alpha=0.7, density=True, label="Baseline")
    ax.hist(k.clip(upper=80), bins=bins, color=TEAL, alpha=0.6, density=True, label="Control")
    ax.axvline(USL_HRS, color=RED, ls="--")
    cb, cc = c.set_index("phase").loc["Baseline"], c.set_index("phase").loc["Control"]
    ax.text(USL_HRS + 1, ax.get_ylim()[1] * 0.85,
            f"USL {USL_HRS:.0f} h SLA\nBaseline: {cb.pct_over_usl:.2%} over, Ppk {cb.ppk_lognormal:.2f}\n"
            f"Control: {cc.pct_over_usl:.2%} over, Ppk {cc.ppk_lognormal:.2f}", fontsize=8.5, color=RED)
    ax.set_xlabel("Dock-to-disposition hours (values above 80 h shown in last bin)")
    ax.set_ylabel("Density")
    ax.set_title("Process capability vs 48-hour disposition SLA (Ppk on log-transformed hours)")
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(SHOTS / "cycle_time_capability.png")
    plt.close(fig)
    for ph in ["Baseline", "Control"]:
        r = c.set_index("phase").loc[ph]
        m[f"cap_{ph.lower()}_ppk"] = float(r.ppk_lognormal)
        m[f"cap_{ph.lower()}_pct_over"] = float(r.pct_over_usl)
        m[f"cap_{ph.lower()}_p50"] = float(r.p50_hrs)
        m[f"cap_{ph.lower()}_p95"] = float(r.p95_hrs)
        m[f"cap_{ph.lower()}_mean"] = float(r.mean_hrs)


def pilot_chart(m: dict) -> None:
    p = pd.read_csv(PROC / "08_pilot_pre_post.csv")
    fig, axes = plt.subplots(1, 3, figsize=(12, 4))
    groups = ["Pilot site (RC-CENTRAL)", "Comparison sites"]
    phases = ["Baseline", "Pilot", "Control"]
    for ax, col, title, scale, fmt in [
        (axes[0], "defect_rate", "Defect rate", 100, "{:.1f}%"),
        (axes[1], "leakage_usd_per_unit", "Recovery leakage $ per unit", 1, "${:.2f}"),
        (axes[2], "waste_per_10k_units", "Waste units per 10k", 1, "{:.0f}")]:
        x = np.arange(len(groups))
        for i, ph in enumerate(phases):
            vals = [p[(p.site_group == g) & (p.phase == ph)][col].iloc[0] * scale for g in groups]
            bars = ax.bar(x + (i - 1) * 0.27, vals, 0.27, color=PHASE_COL[ph], label=ph)
            for bb, v in zip(bars, vals):
                ax.text(bb.get_x() + bb.get_width() / 2, v, fmt.format(v), ha="center", va="bottom", fontsize=7.5)
        ax.set_xticks(x, ["Pilot site\n(RC-CENTRAL)", "Comparison\nsites"])
        ax.set_title(title)
    axes[0].legend(frameon=False, fontsize=8)
    fig.suptitle(f"Pilot before/after: RC-CENTRAL defect rate fell {abs(m['pilot_rel_change']):.0%} "
                 f"(two-proportion z = {m['pilot_z']:.2f}, p = {m['pilot_p']:.1e}); comparison sites flat until rollout",
                 fontweight="bold", fontsize=10.5)
    fig.tight_layout()
    fig.savefig(SHOTS / "pilot_before_after.png")
    plt.close(fig)


def fishbone(rate: float) -> None:
    fig, ax = plt.subplots(figsize=(16, 7))
    ax.set_xlim(0, 15.8)
    ax.set_ylim(0, 7)
    ax.axis("off")
    ax.annotate("", xy=(12.6, 3.5), xytext=(0.4, 3.5), arrowprops=dict(arrowstyle="-|>", lw=3, color=NAVY))
    ax.add_patch(plt.Rectangle((12.65, 2.7), 3.0, 1.6, color=RED, alpha=0.9))
    ax.text(14.15, 3.5, f"Wrong disposition\n(misgrade / mis-route)\n{rate:.1%} of audited units", ha="center",
            va="center", color="white", fontsize=10, fontweight="bold")
    bones = {
        ("People", 2.6, "top"): ["Tenure < 30 days (Q4 seasonal hires)", "Grading training is shadow-only",
                                  "Night shift fatigue, thin lead coverage"],
        ("Method", 6.6, "top"): ["SOP v2.x: open-box criteria in free text", "Electronics functional test optional",
                                  "No grading checklist / standard work"],
        ("Machine / Tools", 10.6, "top"): ["No photo-grading step at RC-CENTRAL", "Station scanner / UI defaults",
                                          "Manual disposition code entry"],
        ("Measurement", 2.6, "bottom"): ["QA audit sample only ~10%", "Defect cause codes inconsistent",
                                         "No weekly defect feedback to associates"],
        ("Materials", 6.6, "bottom"): ["Missing accessories / manuals", "Damaged or reused packaging",
                                       "Electronics with hidden faults"],
        ("Environment", 10.6, "bottom"): ["Post-Q4 backlog (Jan peak)", "Queue pressure to clear dock",
                                         "Lighting at night grading stations"],
    }
    for (name, x, pos), causes in bones.items():
        y0, y1 = (6.4, 3.5) if pos == "top" else (0.6, 3.5)
        ax.plot([x, x + 1.6], [y0, y1], color=NAVY, lw=2)
        ax.text(x, y0 + (0.25 if pos == "top" else -0.3), name, ha="center", fontsize=11, fontweight="bold",
                color=NAVY, bbox=dict(boxstyle="round", fc="#e9f1f7", ec=NAVY))
        for i, c in enumerate(causes):
            t = (i + 1) / (len(causes) + 1)
            xc, yc = x + 1.6 * t, y0 + (y1 - y0) * t
            ax.plot([xc - 0.4, xc], [yc, yc], color=GREY, lw=1)
            ax.text(xc - 0.45, yc, c, ha="right", va="center", fontsize=8.2)
    ax.text(0.2, 0.05, "Causes validated with data in Analyze: tenure < 30 days, SOP v2.x open-box / electronics criteria, "
            "night shift, missing photo step, post-Q4 backlog.", fontsize=8.5, style="italic", color="#333")
    ax.set_title("Fishbone (Ishikawa): causes of disposition defects at returns processing centers", fontsize=13,
                 fontweight="bold", color=NAVY)
    fig.tight_layout()
    fig.savefig(DOCS / "fishbone_ishikawa.png", dpi=130)
    plt.close(fig)


def impact(aud: pd.DataFrame, units: pd.DataFrame, m: dict) -> None:
    b = aud[aud.phase == "Baseline"]
    leak_def = b.loc[b.is_defect == 1, "recovery_leakage_usd"].mean()
    leak_ok = b.loc[b.is_defect == 0, "recovery_leakage_usd"].mean()
    per_defect = leak_def - leak_ok
    annual_units = len(units) * 365 / units.op_date.nunique()
    dp = m["network_baseline_rate"] - m["network_control_rate"]
    defects_avoided = annual_units * dp
    dollars = defects_avoided * per_defect
    ub = units[units.phase == "Baseline"]
    uc = units[units.phase == "Control"]
    waste_b, waste_c = ub.waste_flag.mean(), uc.waste_flag.mean()
    comp_b, comp_c = ub.customer_complaint_flag.mean(), uc.customer_complaint_flag.mean()
    rec_b = ub.recovery_achieved_usd.sum() / ub.potential_recovery_usd.sum()
    rec_c = uc.recovery_achieved_usd.sum() / uc.potential_recovery_usd.sum()
    leak_unit_b, leak_unit_c = ub.recovery_leakage_usd.mean(), uc.recovery_leakage_usd.mean()
    target_dollars = annual_units * (m["network_baseline_rate"] - TARGET_DEFECT) * per_defect
    rows = [
        ("Annualized units processed", annual_units),
        ("Baseline defect rate", m["network_baseline_rate"]),
        ("Control defect rate", m["network_control_rate"]),
        ("Target defect rate (charter)", TARGET_DEFECT),
        ("Incremental leakage per defect (USD)", per_defect),
        ("Defects avoided per year (at control rate)", defects_avoided),
        ("Recovery value protected per year at control rate (USD)", dollars),
        ("Recovery value protected per year at target rate (USD)", target_dollars),
        ("Baseline recovery rate (achieved / potential)", rec_b),
        ("Control recovery rate (achieved / potential)", rec_c),
        ("Baseline leakage per unit (USD)", leak_unit_b),
        ("Control leakage per unit (USD)", leak_unit_c),
        ("Baseline waste units per 10k", waste_b * 1e4),
        ("Control waste units per 10k", waste_c * 1e4),
        ("Waste units avoided per year", annual_units * (waste_b - waste_c)),
        ("Baseline customer complaint rate", comp_b),
        ("Control customer complaint rate", comp_c),
        ("Customer complaints avoided per year", annual_units * (comp_b - comp_c)),
        ("Baseline total leakage, Jul 2025-Feb 2026 (USD)", ub.recovery_leakage_usd.sum()),
        ("Baseline waste units, Jul 2025-Feb 2026", ub.waste_flag.sum()),
    ]
    pd.DataFrame(rows, columns=["metric", "value"]).to_csv(PROC / "impact_summary.csv", index=False)
    m.update({"annual_units": annual_units, "leak_per_defect": per_defect, "defects_avoided": defects_avoided,
              "annual_dollars": dollars, "target_dollars": target_dollars, "recovery_rate_baseline": rec_b,
              "recovery_rate_control": rec_c, "leak_unit_baseline": leak_unit_b, "leak_unit_control": leak_unit_c,
              "waste10k_baseline": waste_b * 1e4, "waste10k_control": waste_c * 1e4,
              "waste_avoided": annual_units * (waste_b - waste_c), "complaint_baseline": comp_b,
              "complaint_control": comp_c, "complaints_avoided": annual_units * (comp_b - comp_c),
              "baseline_leakage_total": float(ub.recovery_leakage_usd.sum()),
              "baseline_waste_units": int(ub.waste_flag.sum()), "target_defect_rate": TARGET_DEFECT,
              "usl_hrs": USL_HRS})


def main() -> None:
    SHOTS.mkdir(exist_ok=True)
    DOCS.mkdir(exist_ok=True)
    aud, units = load()
    m: dict = {}
    base = pd.read_csv(PROC / "02_baseline_defect_rate_dpmo_sigma.csv")
    for ph in ["Baseline", "Pilot", "Control"]:
        r = base[(base.phase == ph) & (base.site_id == "NETWORK")].iloc[0]
        m[f"{ph.lower()}_dpmo"] = float(r.dpmo)
        m[f"{ph.lower()}_sigma"] = float(r.sigma_level)
        m[f"{ph.lower()}_fpy"] = float(r.first_pass_yield)
        m[f"{ph.lower()}_audited"] = int(r.audited_units)
        m[f"{ph.lower()}_defects"] = int(r.defects)
    sb = base[(base.phase == "Baseline") & (base.site_id != "NETWORK")].set_index("site_id")
    m["site_baseline_rates"] = sb.defect_rate.to_dict()
    dq = pd.read_csv(PROC / "01_data_quality_profile.csv").set_index("check_name").value
    m["units_total"] = int(dq["Units processed (clean)"])
    m["units_audited"] = int(dq["Units audited (QA sample)"])
    m["associates"] = int(dq["Distinct associates"])

    pareto_chart(m)
    hypothesis_tests(aud, m)
    p_chart(m)
    imr_chart(units, m)
    value_stream_chart(m)
    drivers_logit(aud, m)
    capability(units, m)
    pilot_chart(m)
    fishbone(m["network_baseline_rate"])
    impact(aud, units, m)
    m = {k: (float(v) if isinstance(v, (np.floating, np.integer)) else v) for k, v in m.items()}
    (PROC / "metrics.json").write_text(json.dumps(m, indent=2, default=float), encoding="utf-8")
    print(json.dumps({k: m[k] for k in ["network_baseline_rate", "network_control_rate", "pilot_site_baseline_rate",
                                        "pilot_site_pilot_rate", "pilot_p", "did_p", "annual_dollars",
                                        "pareto_vital_few"]}, indent=1, default=float))


if __name__ == "__main__":
    main()
