"""Write the Tableau extract (dashboard/tableau_extract.csv, one row per return)
and render the dashboard preview plus supporting charts into screenshots/.
"""
import sqlite3

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from config import DB_PATH, DASH_DIR, PROCESSED, SHOTS
import metrics

NAVY, ORANGE, GREY, RED, GREEN, BLUE = "#232F3E", "#FF9900", "#8C8C8C", "#C0392B", "#2E8B57", "#3B6FB6"
TIER_COLORS = {"High": RED, "Medium": ORANGE, "Low": GREEN}
plt.rcParams.update({"font.family": "DejaVu Sans", "axes.spines.top": False, "axes.spines.right": False,
                     "axes.titleweight": "bold", "axes.titlesize": 11})


def extract():
    con = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("""
        SELECT rf.return_id, rf.order_id, rf.customer_id, rf.region, rf.is_member, rf.payment_type,
               rf.order_date, rf.order_month, rf.category, rf.item_price,
               rf.return_request_date, rf.request_month, rf.period, rf.reason_code, rf.return_method,
               rf.is_inr, rf.refund_issued, rf.refund_amount, rf.refund_issued_date, rf.instant_refund_flag,
               rf.return_received_date, rf.condition_grade, rf.days_request_to_refund,
               rf.bad_debt_flag, rf.fraud_return_flag, rf.condition_mismatch_flag,
               rf.recovery_value, rf.loss_amt, rf.prior_returns_90d,
               co.risk_score, co.risk_tier, co.address_inr_cluster,
               CASE WHEN co.perf_active = 1 AND co.perf_loss_event = 0 THEN 1 ELSE 0 END AS good_customer_perf
        FROM return_facts rf JOIN customer_outcomes co USING (customer_id)
        ORDER BY rf.return_id""", con)
    con.close()
    DASH_DIR.mkdir(exist_ok=True)
    df.to_csv(DASH_DIR / "tableau_extract.csv", index=False)
    return df


def kpi(ax, label, value, sub, color=NAVY):
    ax.axis("off")
    ax.add_patch(plt.Rectangle((0, 0), 1, 1, transform=ax.transAxes, color="#F4F6F8", zorder=0))
    ax.text(0.5, 0.70, value, ha="center", va="center", fontsize=20, fontweight="bold", color=color,
            transform=ax.transAxes)
    ax.text(0.5, 0.38, label, ha="center", va="center", fontsize=10, color=NAVY, transform=ax.transAxes)
    ax.text(0.5, 0.15, sub, ha="center", va="center", fontsize=8, color=GREY, transform=ax.transAxes)


def short(name):
    return name.split(" ", 1)[1] if name[:1] == "S" and name[1:2].isdigit() else name


def draw_monthly(ax):
    rr = pd.read_csv(PROCESSED / "03_return_rate_by_category_month.csv")
    mon = rr.groupby("order_month")[["orders", "returns"]].sum()
    mon["rate"] = mon["returns"] / mon["orders"]
    x = np.arange(len(mon))
    ax2 = ax.twinx()
    ax2.bar(x, mon["orders"] / 1000, color="#D9DEE4", width=0.8, label="Orders (k)")
    ax2.set_ylabel("Orders (k)", color=GREY)
    ax2.spines["top"].set_visible(False)
    ax.set_zorder(ax2.get_zorder() + 1)
    ax.patch.set_visible(False)
    ax.plot(x, mon["rate"] * 100, color=NAVY, marker="o", ms=3, lw=2, label="Return rate %")
    ax.set_xticks(x[::3])
    ax.set_xticklabels(mon.index[::3], rotation=45, fontsize=8)
    ax.set_ylabel("Return rate %")
    ax.set_title("Return rate by order month (bars = orders)")
    return mon


def draw_bad_debt(ax):
    bd = pd.read_csv(PROCESSED / "06_bad_debt.csv")
    bd = bd[bd["refund_month"] != "TOTAL"]
    piv = bd.pivot(index="refund_month", columns="refund_type", values="bad_debt_dollars").fillna(0)
    piv = piv[piv.index <= "2025-12"]
    x = np.arange(len(piv))
    ax.bar(x, piv["instant"] / 1000, color=RED, label="Instant refund")
    ax.bar(x, piv["standard"] / 1000, bottom=piv["instant"] / 1000, color=GREY, label="Standard (carrier-lost)")
    ax.set_xticks(x[::3])
    ax.set_xticklabels(piv.index[::3], rotation=45, fontsize=8)
    ax.set_ylabel("$k")
    ax.set_title("Bad debt $ by refund month")
    ax.legend(fontsize=8, frameon=False)


def draw_tiers(ax):
    tv = pd.read_csv(PROCESSED / "09_tier_outcomes_validation.csv").set_index("risk_tier").loc[["High", "Medium", "Low"]]
    y = np.arange(3)
    ax.barh(y + 0.2, tv["pct_of_active_customers"], height=0.38, color=[TIER_COLORS[t] for t in tv.index],
            alpha=0.45, label="% of customers")
    ax.barh(y - 0.2, tv["pct_of_loss_dollars"], height=0.38, color=[TIER_COLORS[t] for t in tv.index],
            label="% of loss $")
    for i, t in enumerate(tv.index):
        ax.text(tv.loc[t, "pct_of_active_customers"] + 1, i + 0.2, f"{tv.loc[t, 'pct_of_active_customers']:.1f}% of customers",
                va="center", fontsize=8)
        ax.text(tv.loc[t, "pct_of_loss_dollars"] + 1, i - 0.2, f"{tv.loc[t, 'pct_of_loss_dollars']:.1f}% of loss $",
                va="center", fontsize=8, fontweight="bold")
    ax.set_yticks(y)
    ax.set_yticklabels(tv.index)
    ax.invert_yaxis()
    ax.set_xlim(0, 125)
    ax.set_xlabel("%")
    ax.set_title("Risk tier mix vs share of loss $ (Jul-Dec 2025)")


def draw_patterns(ax):
    pat = pd.read_csv(PROCESSED / "12_abuse_patterns.csv").sort_values("est_loss_dollars")
    ax.barh(pat["pattern"].str.replace(r" \(.*\)", "", regex=True), pat["est_loss_dollars"] / 1000, color=NAVY)
    for i, (v, c) in enumerate(zip(pat["est_loss_dollars"], pat["customers"])):
        ax.text(v / 1000 + 2, i, f"${v / 1000:,.0f}k | {c:,} cust.", va="center", fontsize=8)
    ax.set_xlabel("Estimated loss $k (24 months)")
    ax.set_xlim(0, pat["est_loss_dollars"].max() / 1000 * 1.6)
    ax.tick_params(axis="y", labelsize=8)
    ax.set_title("Top abuse and loss patterns")


def draw_policy(ax):
    pol = pd.read_csv(PROCESSED / "11_policy_simulation.csv")
    pol = pol[pol["scenario_id"] > 0].iloc[::-1]
    colors = [GREEN if p <= 2 else (ORANGE if p <= 5 else RED) for p in pol["pct_good_customers_affected"]]
    labels = [f"S{i} " + short(s)[:58] for i, s in zip(pol["scenario_id"], pol["scenario"])]
    ax.barh(labels, pol["dollars_saved"] / 1000, color=colors)
    for i, (v, g) in enumerate(zip(pol["dollars_saved"], pol["pct_good_customers_affected"])):
        ax.text(v / 1000 + 0.5, i, f"${v / 1000:,.1f}k | {g:.2f}% good cust.", va="center", fontsize=8)
    ax.set_xlim(0, pol["dollars_saved"].max() / 1000 * 1.6)
    ax.set_xlabel("$k saved in Jul-Dec 2025 replay")
    ax.tick_params(axis="y", labelsize=8)
    ax.set_title("Policy savings vs good-customer impact (green <= 2%)")


def dashboard(m):
    fig = plt.figure(figsize=(18, 11), dpi=110)
    fig.patch.set_facecolor("white")
    top = fig.add_gridspec(1, 5, left=0.03, right=0.98, top=0.92, bottom=0.80, wspace=0.12)
    mid = fig.add_gridspec(1, 3, left=0.05, right=0.97, top=0.71, bottom=0.46, wspace=0.38,
                           width_ratios=[1.25, 1, 1.1])
    bot = fig.add_gridspec(1, 2, left=0.15, right=0.97, top=0.36, bottom=0.07, wspace=0.75,
                           width_ratios=[1, 1.25])
    fig.suptitle("Returns Risk & Bad Debt Dashboard  |  synthetic e-commerce returns, Jan 2024 to Dec 2025",
                 fontsize=16, fontweight="bold", color=NAVY, x=0.03, ha="left", y=0.975)
    kpis = [
        ("Return rate", f"{m['return_rate'] * 100:.1f}%", f"{m['returns']:,} returns / {m['orders']:,} orders"),
        ("Bad debt $", f"${m['bad_debt_dollars'] / 1000:,.1f}k", f"{m['bad_debt_pct']:.2f}% of refund $ ({m['bad_debt_instant_share'] * 100:.0f}% instant)"),
        ("High-tier share of loss $", f"{m['high_loss_share']:.1f}%", f"from {m['high_active_share']:.1f}% of active customers"),
        ("High vs Low loss-event rate", f"{m['stats']['lift_high_vs_low']:.1f}x", f"{m['high_loss_event_rate']:.1f}% vs {m['low_loss_event_rate']:.1f}% (p < 0.001)"),
        ("Recommended package saves", f"${m['s7_saved'] / 1000:,.1f}k", f"{m['s7_pct_loss']:.1f}% of 6-mo loss; {m['s7_pct_good']:.2f}% good cust. hit"),
    ]
    for i, (lab, val, sub) in enumerate(kpis):
        kpi(fig.add_subplot(top[0, i]), lab, val, sub, color=RED if i == 1 else NAVY)
    draw_monthly(fig.add_subplot(mid[0, 0]))
    draw_bad_debt(fig.add_subplot(mid[0, 1]))
    draw_tiers(fig.add_subplot(mid[0, 2]))
    draw_patterns(fig.add_subplot(bot[0, 0]))
    draw_policy(fig.add_subplot(bot[0, 1]))
    fig.text(0.03, 0.01, "Data is synthetic (src/generate_data.py). Tiers are scored on Jan 2024-Jun 2025 and tested on "
             "Jul-Dec 2025. Filters in the Tableau build: region, category, member flag, tier, refund type.",
             fontsize=8, color=GREY)
    fig.savefig(SHOTS / "dashboard.png", bbox_inches="tight")
    plt.close(fig)


def single(name, fn, size=(9, 5)):
    fig, ax = plt.subplots(figsize=size, dpi=110)
    fn(ax)
    fig.tight_layout()
    fig.savefig(SHOTS / name)
    plt.close(fig)


def category_chart(ax):
    rr = pd.read_csv(PROCESSED / "03_return_rate_by_category_month.csv")
    cat = rr.groupby("category")[["orders", "returns", "loss_dollars"]].sum()
    cat["rate"] = cat["returns"] / cat["orders"] * 100
    cat = cat.sort_values("rate")
    ax.barh(cat.index, cat["rate"], color=NAVY)
    for i, (r, l) in enumerate(zip(cat["rate"], cat["loss_dollars"])):
        ax.text(r + 0.4, i, f"{r:.1f}%  (loss ${l / 1000:,.0f}k)", va="center", fontsize=9)
    ax.set_xlim(0, cat["rate"].max() * 1.35)
    ax.set_xlabel("Return rate % (24 months)")
    ax.set_title("Return rate and loss $ by category")


def odds_chart(ax):
    o = pd.read_csv(PROCESSED / "stats_logit_odds_ratios.csv")
    o = o[o["term"] != "Intercept"].sort_values("odds_ratio")
    y = np.arange(len(o))
    ax.errorbar(o["odds_ratio"], y, xerr=[o["odds_ratio"] - o["or_ci_low"], o["or_ci_high"] - o["odds_ratio"]],
                fmt="o", color=NAVY, ecolor=GREY, capsize=3)
    ax.axvline(1, color=RED, ls="--", lw=1)
    ax.set_xscale("log")
    ax.set_yticks(y)
    ax.set_yticklabels(o["description"])
    for i, v in enumerate(o["odds_ratio"]):
        ax.text(v * 1.08, i + 0.18, f"{v:.1f}x", fontsize=8)
    ax.set_xlabel("Odds ratio of a loss event in Jul-Dec 2025 (log scale, 95% CI)")
    ax.set_title("Logistic regression: which score drivers predict future loss")


def cycle_chart(ax):
    ct = pd.read_csv(PROCESSED / "05_refund_cycle_time.csv")
    ct = ct[ct["request_quarter"] <= "2025-Q4"]
    for t, c in [("instant", RED), ("standard", NAVY)]:
        d = ct[ct["refund_type"] == t]
        ax.plot(d["request_quarter"], d["avg_days_request_to_refund"], marker="o", color=c, label=f"{t}: days to refund")
    d = ct[ct["refund_type"] == "instant"]
    ax.plot(d["request_quarter"], d["avg_days_refund_to_receipt"], marker="s", ls="--", color=ORANGE,
            label="instant: days refund is out before item arrives")
    ax.set_ylabel("Days")
    ax.tick_params(axis="x", rotation=45)
    ax.legend(fontsize=8, frameon=False)
    ax.set_title("Refund cycle time: instant vs standard")


def cohort_chart(ax):
    c = pd.read_csv(PROCESSED / "10_cohort_view.csv")
    c = c[c["period"] == "performance"]
    ax.bar(c["signup_cohort"].str[3:], c["loss_dollars_per_1k_orders"], color=NAVY)
    for i, v in enumerate(c["loss_dollars_per_1k_orders"]):
        ax.text(i, v + 40, f"${v:,.0f}", ha="center", fontsize=8)
    ax.set_ylabel("Loss $ per 1,000 orders")
    ax.set_xlabel("Account signup cohort")
    ax.set_title("Newer accounts carry higher loss per order (Jul-Dec 2025)")


def main():
    SHOTS.mkdir(exist_ok=True)
    extract()
    m = metrics.load()
    dashboard(m)
    single("return_rate_by_category.png", category_chart)
    single("bad_debt_by_month.png", draw_bad_debt)
    single("risk_tier_mix_vs_loss.png", draw_tiers)
    single("policy_savings_vs_impact.png", draw_policy, size=(11, 5))
    single("logit_odds_ratios.png", odds_chart)
    single("refund_cycle_time.png", cycle_chart)
    single("cohort_loss_per_order.png", cohort_chart)
    print("dashboard extract + screenshots written")


if __name__ == "__main__":
    main()
