"""Matplotlib charts shared by the WBR PDF, the dashboard preview and the README."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import textwrap

from config import RAG_COLORS, KPI_ORDER

STATUS_COLORS = {"Complete": "#90A4AE", "On Track": "#43A047", "At Risk": "#F9A825",
                 "Blocked": "#C62828", "Not Started": "#CFD8DC"}
LABELS = {
    "return_rate": "Return rate", "refund_cycle_days": "Refund cycle (days)",
    "contacts_per_return": "Contacts per return", "resale_pct": "Resold share",
    "liquidation_pct": "Liquidated share", "recovery_rate": "Recovery rate",
    "waste_units": "Waste units", "cost_per_return": "Cost per return ($)",
}
PCT_KPIS = {"return_rate", "resale_pct", "liquidation_pct", "recovery_rate"}


def _style(ax):
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", alpha=0.25)
    ax.tick_params(labelsize=7)


def plot_kpi_trend(ax, trend, kpi, rag, weeks=26, show_ly=True):
    d = trend[trend["kpi"] == kpi].copy()
    d["week_start"] = pd.to_datetime(d["week_start"])
    d = d.sort_values("week_start").tail(weeks)
    scale = 100 if kpi in PCT_KPIS else 1
    color = RAG_COLORS.get(rag, "#455A64")
    ax.plot(d["week_start"], d["value"] * scale, color="#1565C0", lw=1.6, label="Weekly")
    ax.plot(d["week_start"], d["t4w_rolling_avg"] * scale, color="#1565C0", lw=1, ls=":", label="T4W avg")
    if show_ly:
        ax.plot(d["week_start"], d["yoy_value"] * scale, color="#9E9E9E", lw=1, alpha=0.8, label="Last year")
    ax.axhline(d["target"].iloc[-1] * scale, color="#424242", ls="--", lw=1, label="Target")
    ax.scatter(d["week_start"].iloc[-1], d["value"].iloc[-1] * scale, color=color, s=36, zorder=5)
    ax.set_title(f"{LABELS[kpi]}{' (%)' if scale == 100 else ''}  [{rag}]", fontsize=8.5, color=color, loc="left")
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b"))
    _style(ax)


def kpi_small_multiples(trend, rag_df, path, weeks=26):
    rag = dict(zip(rag_df["kpi"], rag_df["rag"]))
    fig, axes = plt.subplots(2, 4, figsize=(12, 5.2))
    for ax, kpi in zip(axes.ravel(), KPI_ORDER):
        plot_kpi_trend(ax, trend, kpi, rag[kpi], weeks)
    axes[0, 0].legend(fontsize=6.5, frameon=False, loc="best")
    fig.suptitle(f"WBR KPI trends, last {weeks} weeks (weekly, trailing-4-week average, last year, target)", fontsize=10, x=0.01, ha="left")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def cycle_driver_chart(driver, path, top=8):
    d = driver.copy()
    d["segment"] = d["marketplace"] + " " + d["channel"]
    d = d.reindex(d["total_effect_days"].abs().sort_values(ascending=False).index).head(top)
    d = d.iloc[::-1]
    fig, ax = plt.subplots(figsize=(7.5, 3.0))
    ax.barh(d["segment"], d["rate_effect_days"], color="#C62828", label="Rate effect (segment got slower/faster)")
    ax.barh(d["segment"], d["mix_effect_days"], left=d["rate_effect_days"].where(d["rate_effect_days"] * d["mix_effect_days"] > 0, 0),
            color="#90A4AE", label="Mix effect (volume shift)")
    for y, (v, dc, tc) in enumerate(zip(d["total_effect_days"], d["days_change"], d["transit_change"])):
        ax.text(max(v, 0) + 0.005, y, f"{v:+.3f} d  (segment {dc:+.2f} d, transit {tc:+.2f} d)", va="center", fontsize=7)
    ax.axvline(0, color="#424242", lw=0.8)
    ax.set_xlabel("Contribution to program refund-cycle change vs baseline (days)", fontsize=8)
    ax.set_title("Refund cycle time driver: marketplace x channel (current week vs 4-week pre-incident baseline)", fontsize=9, loc="left")
    ax.set_xlim(min(d["total_effect_days"].min(), 0) - 0.02, d["total_effect_days"].max() * 1.9 + 0.02)
    ax.legend(fontsize=7, frameon=False, loc="lower right")
    _style(ax)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def top_movers_heatmap(movers, path):
    kpis = ["refund_cycle_days", "contacts_per_return", "cost_per_return", "recovery_rate", "return_rate"]
    lower_better = {"refund_cycle_days", "contacts_per_return", "cost_per_return", "return_rate"}
    m = movers.pivot(index="category", columns="kpi", values="yoy_pct")[kpis]
    fav = m.copy()
    for k in kpis:
        fav[k] = -m[k] if k in lower_better else m[k]
    fig, ax = plt.subplots(figsize=(7.5, 3.0))
    lim = np.nanmax(np.abs(fav.values))
    ax.imshow(fav.values, cmap="RdYlGn", vmin=-lim, vmax=lim, aspect="auto")
    ax.set_xticks(range(len(kpis)), [LABELS[k] for k in kpis], fontsize=7.5)
    ax.set_yticks(range(len(m.index)), m.index, fontsize=8)
    for i in range(m.shape[0]):
        for j in range(m.shape[1]):
            ax.text(j, i, f"{m.values[i, j] * 100:+.1f}%", ha="center", va="center", fontsize=7.5)
    ax.set_title("Top movers by category: YoY % change (green = favourable, red = unfavourable)", fontsize=9, loc="left")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def plot_milestone_timeline(ax, ms, as_of):
    d = ms.copy()
    for c in ["planned_start", "planned_end", "actual_start", "actual_end", "forecast_end"]:
        d[c] = pd.to_datetime(d[c])
    d = d.sort_values(["initiative_id", "planned_start"], ascending=[False, False]).reset_index(drop=True)
    for y, r in d.iterrows():
        ax.barh(y, (r["planned_end"] - r["planned_start"]).days, left=r["planned_start"], height=0.75,
                color="none", edgecolor="#9E9E9E", lw=0.7)
        start = r["actual_start"] if pd.notna(r["actual_start"]) else r["planned_start"]
        end = r["actual_end"] if pd.notna(r["actual_end"]) else (r["forecast_end"] if pd.notna(r["forecast_end"]) else r["planned_end"])
        ax.barh(y, (end - start).days, left=start, height=0.45, color=STATUS_COLORS[r["status"]])
    ax.axvline(pd.Timestamp(as_of), color="#C62828", lw=1, ls="--")
    ax.text(pd.Timestamp(as_of), len(d) - 0.3, " as of", color="#C62828", fontsize=6.5, va="bottom")
    # shorten on a word boundary so names don't get cut mid-word
    names = [textwrap.shorten(b, 30, placeholder="...") for b in d["milestone"]]
    ax.set_yticks(range(len(d)), [f"{a} {b}" for a, b in zip(d["milestone_id"], names)], fontsize=5.8)
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %y"))
    ax.tick_params(axis="x", labelsize=7)
    handles = [plt.Rectangle((0, 0), 1, 1, color=c) for c in STATUS_COLORS.values()]
    ax.legend(handles, STATUS_COLORS.keys(), fontsize=6, ncol=5, frameon=False, loc="upper left", bbox_to_anchor=(0, -0.06))
    ax.spines[["top", "right"]].set_visible(False)


def milestone_timeline(ms, as_of, path):
    fig, ax = plt.subplots(figsize=(9, 6.5))
    plot_milestone_timeline(ax, ms, as_of)
    ax.set_title("Program milestone timeline (outline = plan, bar = actual/forecast, colour = status)", fontsize=9, loc="left")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
