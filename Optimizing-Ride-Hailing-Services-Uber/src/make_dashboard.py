"""Write the Tableau/QuickSight extract and matplotlib renders of the dashboard and charts.

The PNGs follow the layout in dashboard/dashboard_spec.md. They are not Tableau screenshots.
"""
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from common import DASHBOARD_DIR, DATA_PROCESSED, SCREENSHOTS_DIR  # noqa: E402

LABEL = {
    "greedy_first_dispatch": "Greedy first-dispatch",
    "greedy_first_dispatch_mdr": "Greedy first-dispatch + MDR",
    "batched_min_eta": "Batched min-ETA",
    "batched_min_eta_mdr": "Batched min-ETA + MDR",
    "batched_max_profit_mdr": "Batched max-profit + MDR",
}
COLOR = {
    "greedy_first_dispatch": "#9E9E9E", "greedy_first_dispatch_mdr": "#616161",
    "batched_min_eta": "#5B9BD5", "batched_min_eta_mdr": "#1F3A5F", "batched_max_profit_mdr": "#ED7D31",
}
ORDER = list(LABEL)


def supply_segment(ratio: float) -> str:
    if ratio < 0.8:
        return "1. Under-supplied (<0.8)"
    if ratio < 1.0:
        return "2. Tight (0.8-1.0)"
    if ratio < 1.2:
        return "3. Balanced (1.0-1.2)"
    return "4. Over-supplied (>=1.2)"


def build_extract() -> pd.DataFrame:
    res = pd.read_csv(DATA_PROCESSED / "simulation_results.csv")
    ext = res.copy()
    ext.insert(2, "protocol_label", ext["protocol"].map(LABEL))
    ext.insert(3, "dispatch_method", ext["protocol"].str.startswith("batched").map({True: "Batched", False: "Greedy"}))
    ext.insert(4, "radius_policy", ext["protocol"].str.endswith("_mdr").map({True: "MDR enforced", False: "No radius"}))
    ext.insert(5, "objective", ext["protocol"].map(lambda p: "Max contribution" if "profit" in p else "Min ETA"))
    ext["supply_ratio_actual"] = (ext["drivers"] / ext["riders"]).round(4)
    ext["supply_segment"] = ext["supply_ratio_actual"].map(supply_segment)
    ext.to_csv(DASHBOARD_DIR / "tableau_extract.csv", index=False)
    buckets = pd.read_csv(DATA_PROCESSED / "sql_03_eta_distribution_buckets.csv")
    buckets.insert(1, "protocol_label", buckets["protocol"].map(LABEL))
    buckets.to_csv(DASHBOARD_DIR / "tableau_eta_distribution.csv", index=False)
    return ext


def chart_eta(ax, kpi):
    k = kpi.set_index("protocol").loc[ORDER]
    x = range(len(k))
    ax.bar([i - 0.2 for i in x], k["avg_eta_min"], 0.4, color=[COLOR[p] for p in k.index], label="Avg ETA")
    ax.bar([i + 0.2 for i in x], k["avg_window_p90_eta_min"], 0.4, color=[COLOR[p] for p in k.index],
           alpha=0.45, hatch="//", label="Avg window p90 ETA")
    for i, (a, b) in enumerate(zip(k["avg_eta_min"], k["avg_window_p90_eta_min"])):
        ax.text(i - 0.2, a + 0.15, f"{a:.2f}", ha="center", fontsize=8)
        ax.text(i + 0.2, b + 0.15, f"{b:.2f}", ha="center", fontsize=8)
    ax.set_xticks(list(x))
    ax.set_xticklabels([LABEL[p].replace(" + ", "\n+ ") for p in k.index], fontsize=8)
    ax.set_ylabel("minutes")
    ax.set_title("Rider ETA by dispatch protocol (avg and p90)")
    ax.legend(fontsize=8, frameon=False)


def chart_dist(ax, dist):
    piv = dist.pivot(index="protocol", columns="eta_bucket", values="pct_of_matched").loc[ORDER]
    left = [0] * len(piv)
    shades = ["#1A9850", "#91CF60", "#FEE08B", "#FC8D59", "#D73027"]
    for col, c in zip(piv.columns, shades):
        ax.barh([LABEL[p] for p in piv.index], piv[col], left=left, color=c, label=col[3:])
        left = [a + b for a, b in zip(left, piv[col])]
    for i, v in enumerate(piv[piv.columns[-1]]):
        ax.text(101, i, f"12+ min: {v:.1f}%", va="center", fontsize=8)
    ax.set_xlim(0, 125)
    ax.invert_yaxis()
    ax.set_xlabel("% of matched riders")
    ax.set_title("ETA distribution (service-level bands)")
    ax.legend(ncol=5, fontsize=7, frameon=False, loc="lower center", bbox_to_anchor=(0.45, -0.32))


def chart_mdr(ax, mdr):
    for p in ["greedy_first_dispatch_mdr", "batched_min_eta_mdr", "batched_min_eta"]:
        d = mdr[mdr["protocol"] == p]
        ax.plot(d["mdr_miles"], d["match_rate_pct"], marker="o", color=COLOR[p], label=LABEL[p])
    ax.set_xlabel("max dispatch radius (miles)")
    ax.set_ylabel("match rate (%)")
    ax.set_xticks(sorted(mdr["mdr_miles"].unique()))
    ax.set_title("Match rate vs max dispatch radius")
    ax.legend(fontsize=8, frameon=False)
    ax.grid(alpha=0.3)


def chart_supply(ax, sup):
    x = range(len(sup))
    ax.bar([i - 0.2 for i in x], sup["greedy_avg_eta_min"], 0.4, color=COLOR["greedy_first_dispatch"], label="Greedy")
    ax.bar([i + 0.2 for i in x], sup["batched_avg_eta_min"], 0.4, color=COLOR["batched_min_eta"], label="Batched")
    for i, r in sup.reset_index(drop=True).iterrows():
        ax.text(i, max(r.greedy_avg_eta_min, r.batched_avg_eta_min) + 0.25, f"-{r.eta_reduction_pct:.1f}%",
                ha="center", fontsize=9, fontweight="bold")
    ax.set_xticks(list(x))
    ax.set_xticklabels([s[3:].replace(" (", "\n(") for s in sup["supply_segment"]], fontsize=8)
    ax.set_ylabel("avg ETA (min)")
    ax.set_ylim(0, sup["greedy_avg_eta_min"].max() * 1.2)
    ax.set_title("Batching ETA reduction by driver supply (no radius)")
    ax.legend(fontsize=8, frameon=False)


def save(fig, name):
    fig.savefig(SCREENSHOTS_DIR / name, dpi=130, bbox_inches="tight")
    plt.close(fig)


def main():
    ext = build_extract()
    kpi = pd.read_csv(DATA_PROCESSED / "sql_01_kpi_by_protocol.csv")
    imp = pd.read_csv(DATA_PROCESSED / "sql_02_batching_improvement_vs_greedy.csv")
    dist = pd.read_csv(DATA_PROCESSED / "sql_03_eta_distribution_buckets.csv")
    mdr = pd.read_csv(DATA_PROCESSED / "sql_04_mdr_sensitivity.csv")
    sup = pd.read_csv(DATA_PROCESSED / "sql_05_supply_demand_sensitivity.csv")

    for fn, name, size in [(chart_eta, "chart_eta_by_protocol.png", (9, 4.5)),
                           (chart_dist, "chart_eta_distribution.png", (9, 4.5)),
                           (chart_mdr, "chart_mdr_sensitivity.png", (7, 4.5)),
                           (chart_supply, "chart_supply_sensitivity.png", (8, 4.5))]:
        fig, ax = plt.subplots(figsize=size)
        fn(ax, {chart_eta: kpi, chart_dist: dist, chart_mdr: mdr, chart_supply: sup}[fn])
        save(fig, name)

    # ---- dashboard preview ----
    k = kpi.set_index("protocol")
    i1 = imp.iloc[0]
    i2 = imp.iloc[1]
    tail = dist[dist["eta_bucket"] == "5. 12+ min"].set_index("protocol")["pct_of_matched"]
    tail_b, tail_g = tail["batched_min_eta"], tail["greedy_first_dispatch"]
    fig = plt.figure(figsize=(16, 10))
    fig.suptitle("Dispatch Performance Dashboard  |  1,000 simulated batching windows (seed 42)",
                 fontsize=16, fontweight="bold", x=0.02, ha="left", color="#1F3A5F")
    fig.text(0.02, 0.935, "Filters: Protocol  |  Radius policy  |  MDR miles  |  Supply segment        "
                          "Source: dashboard/tableau_extract.csv (simulated data, not company data)",
             fontsize=9, color="#555555")
    tiles = [
        ("Avg rider ETA (batched, no radius)", f"{k.loc['batched_min_eta','avg_eta_min']:.2f} min",
         f"vs {k.loc['greedy_first_dispatch','avg_eta_min']:.2f} greedy ({i1.avg_eta_pct_change:+.1f}%)"),
        ("Avg p90 ETA (batched, no radius)", f"{k.loc['batched_min_eta','avg_window_p90_eta_min']:.2f} min",
         f"vs {k.loc['greedy_first_dispatch','avg_window_p90_eta_min']:.2f} greedy ({i1.p90_eta_pct_change:+.1f}%)"),
        ("Match rate (batched, MDR)", f"{i2.candidate_match_rate_pct:.1f}%",
         f"vs {i2.baseline_match_rate_pct:.1f}% greedy (+{i2.candidate_match_rate_pct - i2.baseline_match_rate_pct:.1f} pp)"),
        ("Contribution / window (batched, MDR)", f"${k.loc['batched_min_eta_mdr','avg_contribution_usd_per_window']:.2f}",
         f"vs ${k.loc['greedy_first_dispatch_mdr','avg_contribution_usd_per_window']:.2f} greedy ({i2.contribution_pct_change:+.1f}%)"),
        ("Riders waiting 12+ min (batched)", f"{tail_b:.1f}%", f"vs {tail_g:.1f}% greedy (no radius)"),
    ]
    for i, (t, v, s) in enumerate(tiles):
        ax = fig.add_axes([0.02 + i * 0.196, 0.80, 0.18, 0.11])
        ax.set_xticks([]), ax.set_yticks([])
        ax.set_facecolor("#F3F6FA")
        for sp in ax.spines.values():
            sp.set_color("#1F3A5F")
        ax.text(0.05, 0.75, t, fontsize=10, color="#555555", transform=ax.transAxes)
        ax.text(0.05, 0.35, v, fontsize=20, fontweight="bold", color="#1F3A5F", transform=ax.transAxes)
        ax.text(0.05, 0.10, s, fontsize=8.5, color="#2E7D32", transform=ax.transAxes)
    chart_eta(fig.add_axes([0.05, 0.43, 0.42, 0.30]), kpi)
    chart_dist(fig.add_axes([0.62, 0.45, 0.30, 0.28]), dist)
    chart_mdr(fig.add_axes([0.05, 0.06, 0.40, 0.28]), mdr)
    chart_supply(fig.add_axes([0.55, 0.06, 0.42, 0.28]), sup)
    save(fig, "dashboard.png")
    print(f"extract rows: {len(ext)}; screenshots written to {SCREENSHOTS_DIR}")


if __name__ == "__main__":
    main()

