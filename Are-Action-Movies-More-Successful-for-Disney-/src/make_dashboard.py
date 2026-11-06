"""Write the dashboard extract, the PNG charts and a matplotlib preview of the dashboard.

Outputs
  dashboard/tableau_extract.csv            one row per film, with the model prediction
  screenshots/chart_gross_by_genre.png
  screenshots/chart_budget_vs_gross.png
  screenshots/chart_action_effect.png
  screenshots/chart_roi_by_genre.png
  screenshots/dashboard.png                matplotlib render of the dashboard layout in dashboard_spec.md
"""
from __future__ import annotations

import json

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from common import DASH_DIR, PROCESSED, RESULTS_JSON, SHOTS, SQL_OUT

NAVY, GOLD, GREY, RED = "#1f3b73", "#e0a526", "#9aa5b1", "#c0392b"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "axes.spines.top": False,
                     "axes.spines.right": False})


def load():
    df = pd.read_csv(PROCESSED / "disney_clean.csv")
    res = json.loads(RESULTS_JSON.read_text())
    coefs = pd.read_csv(PROCESSED / "model_coefficients.csv")
    roi = pd.read_csv(SQL_OUT / "04_roi_by_genre.csv")
    return df, res, coefs, roi


def build_extract(df, res):
    c = res["m2_coef"]
    out = df.copy()
    out["predicted_adj_gross"] = np.exp(c["Intercept"] + c["is_action"] * out.is_action
                                        + c["log_budget"] * out.log_budget + c["star_power"] * out.star_power
                                        + c["imdb_score"] * out.imdb_score) * res["smearing_factor"]
    out["gross_vs_expected"] = out.inflation_adjusted_gross - out.predicted_adj_gross
    out["budget_band"] = pd.qcut(out.inflation_budget, 3, labels=["Low", "Mid", "High"]).astype(str)
    out["segment"] = np.where(out.is_marvel == 1, "Marvel",
                              np.where(out.is_action == 1, "Action (non-Marvel)", "Other genres"))
    cols = ["title", "release_year", "decade", "disney_genre", "imdb_genre", "segment", "mpaa_rating",
            "company", "star", "star_power", "star_bucket", "imdb_score", "budget_band", "budget",
            "inflation_budget", "total_gross", "inflation_adjusted_gross", "roi_multiple",
            "predicted_adj_gross", "gross_vs_expected", "is_action", "is_marvel"]
    DASH_DIR.mkdir(exist_ok=True)
    out[cols].round(2).to_csv(DASH_DIR / "tableau_extract.csv", index=False)
    return out


def ax_gross_by_genre(ax, df):
    g = (df.groupby("disney_genre").agg(n=("title", "count"), mean=("inflation_adjusted_gross", "mean"),
                                         median=("inflation_adjusted_gross", "median"))
           .query("n >= 3").sort_values("mean"))
    y = np.arange(len(g))
    colors = [GOLD if i == "Action" else NAVY for i in g.index]
    ax.barh(y, g["mean"] / 1e6, color=colors, alpha=.9, label="Average")
    ax.scatter(g["median"] / 1e6, y, color="white", edgecolor="black", zorder=3, s=30, label="Median")
    ax.set_yticks(y, [f"{i} (n={n})" for i, n in zip(g.index, g.n)])
    ax.set_xlabel("Inflation-adjusted domestic gross ($M)")
    ax.set_title("Average gross by genre (raw, no controls)", loc="left", fontweight="bold")
    ax.legend(frameon=False, loc="lower right")


def ax_budget_scatter(ax, df, res):
    for flag, col, lab in [(0, GREY, "Other genres"), (1, GOLD, "Action")]:
        s = df[df.is_action == flag]
        ax.scatter(s.inflation_budget / 1e6, s.inflation_adjusted_gross / 1e6, c=col, s=28,
                   edgecolor="black" if flag else "none", linewidth=.4, label=lab, alpha=.9)
    m = df[df.is_marvel == 1]
    ax.scatter(m.inflation_budget / 1e6, m.inflation_adjusted_gross / 1e6, facecolor="none", edgecolor=RED,
               s=90, linewidth=1.2, label="Marvel")
    xs = np.linspace(np.log(df.inflation_budget.min()), np.log(df.inflation_budget.max()), 50)
    b = np.polyfit(df.log_budget, df.log_gross, 1)
    ax.plot(np.exp(xs) / 1e6, np.exp(np.polyval(b, xs)) / 1e6, color=NAVY, lw=1.5, label="Log-log trend")
    ax.set_xscale("log"); ax.set_yscale("log")
    ax.set_xlabel("Inflation-adjusted budget ($M, log)"); ax.set_ylabel("Adj. gross ($M, log)")
    ax.set_title(f"Budget drives gross: +1% budget = +{res['m2_budget_elasticity']:.2f}% gross",
                 loc="left", fontweight="bold")
    ax.legend(frameon=False, fontsize=8)


def ax_action_effect(ax, coefs):
    rows = [("M1 Action only", "is_action", "No controls"),
            ("M2 Main (controls)", "is_action", "With controls"),
            ("M3 Main excl. Marvel", "is_action", "Controls, no Marvel"),
            ("M4 Main, IMDb Action label", "is_action_imdb", "Controls, IMDb label")]
    data = []
    for model, term, lab in rows:
        r = coefs[(coefs.model == model) & (coefs.term == term)].iloc[0]
        data.append((lab, np.exp(r.coef) - 1, np.exp(r.ci_low) - 1, np.exp(r.ci_high) - 1, r.p_value))
    y = np.arange(len(data))[::-1]
    for yi, (lab, est, lo, hi, p) in zip(y, data):
        col = RED if p < .05 else NAVY
        ax.plot([lo * 100, hi * 100], [yi, yi], color=col, lw=2.5)
        ax.scatter(est * 100, yi, color=col, s=60, zorder=3)
        ax.text(hi * 100 + 4, yi, f"{est:+.1%}  (p={p:.2f})", va="center", fontsize=9)
    ax.axvline(0, color="black", lw=.8)
    ax.set_yticks(y, [d[0] for d in data])
    ax.set_xlabel("Action premium on gross, % (log-gross model, 95% CI, HC3)")
    # the log model compares typical (geometric) gross, so its no-controls figure is not the
    # +71% gap in simple averages quoted in the README
    ax.text(0, -0.2, "Log-model estimates. The simple-average gap with no controls is +71% (see README).",
            transform=ax.transAxes, fontsize=8, color="#555555")
    ax.set_xlim(-60, max(d[3] for d in data) * 100 + 60)
    ax.set_title("The Action premium goes away once budget is controlled", loc="left", fontweight="bold")


def ax_roi(ax, roi):
    r = roi.sort_values("pooled_roi")
    colors = [GOLD if g == "Action" else NAVY for g in r.disney_genre]
    ax.barh(r.disney_genre, r.pooled_roi, color=colors)
    ax.axvline(1, color=RED, lw=1, ls="--")
    for i, v in enumerate(r.pooled_roi):
        ax.text(v + .03, i, f"{v:.2f}x", va="center", fontsize=9)
    ax.set_xlabel("Pooled ROI = total domestic gross / total budget")
    ax.set_title("Return per budget dollar by genre", loc="left", fontweight="bold")


def save_single(fn, name, *args, size=(8, 5)):
    fig, ax = plt.subplots(figsize=size)
    fn(ax, *args)
    fig.tight_layout()
    fig.savefig(SHOTS / name, dpi=150)
    plt.close(fig)


def dashboard(df, res, coefs, roi):
    fig = plt.figure(figsize=(16, 10), facecolor="#f5f6f8")
    fig.suptitle("Disney genre performance: are Action films more successful?", x=.02, ha="left",
                 fontsize=18, fontweight="bold", color=NAVY)
    fig.text(.02, .925, f"Sample: {res['clean_rows']} Disney releases {res['year_min']}-{res['year_max']} with budget data  |  "
             "Gross = domestic, inflation-adjusted  |  Filters: Decade, Genre, Segment, Budget band",
             fontsize=10, color="#444")
    kpis = [("Films analysed", f"{res['clean_rows']}"),
            ("Avg gross, Action", f"${res['mean_gross_action']/1e6:,.0f}M"),
            ("Avg gross, other", f"${res['mean_gross_non_action']/1e6:,.0f}M"),
            ("Action premium after controls", f"{res['m2_action_pct']:+.1%} (p={res['m2_p']['is_action']:.2f})"),
            ("Budget elasticity", f"{res['m2_budget_elasticity']:.2f}"),
            ("Model R-squared", f"{res['m2_r2']:.2f}")]
    for i, (lab, val) in enumerate(kpis):
        ax = fig.add_axes([.02 + i * .163, .78, .15, .11])
        ax.set_xticks([]); ax.set_yticks([])
        for s in ax.spines.values():
            s.set_visible(False)
        ax.set_facecolor("white")
        ax.text(.06, .66, lab, fontsize=10, color="#555", transform=ax.transAxes)
        ax.text(.06, .2, val, fontsize=16 if len(val) < 12 else 12.5, fontweight="bold", color=NAVY,
                transform=ax.transAxes)
    gs = fig.add_gridspec(2, 2, left=.14, right=.98, top=.72, bottom=.07, hspace=.45, wspace=.38)
    ax_gross_by_genre(fig.add_subplot(gs[0, 0]), df)
    ax_budget_scatter(fig.add_subplot(gs[0, 1]), df, res)
    ax_action_effect(fig.add_subplot(gs[1, 0]), coefs)
    ax_roi(fig.add_subplot(gs[1, 1]), roi)
    fig.text(.98, .01, "Rendered with matplotlib from dashboard/tableau_extract.csv; layout per dashboard/dashboard_spec.md",
             ha="right", fontsize=8, color="#777")
    fig.savefig(SHOTS / "dashboard.png", dpi=110, facecolor=fig.get_facecolor())
    plt.close(fig)


def main() -> None:
    SHOTS.mkdir(exist_ok=True)
    df, res, coefs, roi = load()
    build_extract(df, res)
    save_single(ax_gross_by_genre, "chart_gross_by_genre.png", df)
    save_single(ax_budget_scatter, "chart_budget_vs_gross.png", df, res)
    save_single(ax_action_effect, "chart_action_effect.png", coefs, size=(9, 4.5))
    save_single(ax_roi, "chart_roi_by_genre.png", roi)
    dashboard(df, res, coefs, roi)
    print("extract + 5 PNGs written")


if __name__ == "__main__":
    main()
