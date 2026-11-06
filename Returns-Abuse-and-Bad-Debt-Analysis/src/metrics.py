"""Collect headline metrics from the SQL and stats outputs into one JSON file.

Every number quoted in the README, dashboard and docs is read from
data/processed/metrics.json, which this script builds from the query outputs.
"""
import json
import sqlite3

import pandas as pd

import config as C
from config import PROCESSED, DB_PATH


def read(name):
    return pd.read_csv(PROCESSED / f"{name}.csv")


def build():
    m = {}
    rr = read("03_return_rate_by_category_month")
    m["orders"] = int(rr["orders"].sum())
    m["returns"] = int(rr["returns"].sum())
    m["inr_claims"] = int(rr["inr_claims"].sum())
    m["return_rate"] = m["returns"] / m["orders"]
    cat = rr.groupby("category")[["orders", "returns"]].sum()
    cat["rate"] = cat["returns"] / cat["orders"]
    cat = cat.sort_values("rate", ascending=False)
    m["top_category"] = cat.index[0]
    m["top_category_rate"] = float(cat["rate"].iloc[0])
    m["low_category"] = cat.index[-1]
    m["low_category_rate"] = float(cat["rate"].iloc[-1])
    mon = rr.groupby("order_month")[["orders", "returns"]].sum()
    mon["rate"] = mon["returns"] / mon["orders"]
    m["peak_return_month"] = mon["rate"].idxmax()
    m["peak_return_month_rate"] = float(mon["rate"].max())
    q4 = mon.index.str[5:7].isin(["11", "12"])
    m["nov_dec_return_rate"] = float(mon.loc[q4, "returns"].sum() / mon.loc[q4, "orders"].sum())
    m["other_month_return_rate"] = float(mon.loc[~q4, "returns"].sum() / mon.loc[~q4, "orders"].sum())
    m["peak_order_month"] = mon["orders"].idxmax()
    m["peak_order_month_orders"] = int(mon["orders"].max())

    dq = read("01_data_quality_checks")
    m["dirty_rows_flagged"] = int(dq["rows_flagged"].sum())
    m["dq_checks"] = int(len(dq))

    bd = read("06_bad_debt")
    tot = bd[bd["refund_month"] == "TOTAL"].set_index("refund_type")
    m["refund_dollars_judged"] = float(tot.loc["all", "refund_dollars"])
    m["bad_debt_dollars"] = float(tot.loc["all", "bad_debt_dollars"])
    m["bad_debt_refunds"] = int(tot.loc["all", "bad_debt_refunds"])
    m["bad_debt_pct"] = float(tot.loc["all", "bad_debt_pct_of_refund_dollars"])
    m["bad_debt_instant_dollars"] = float(tot.loc["instant", "bad_debt_dollars"])
    m["bad_debt_instant_share"] = m["bad_debt_instant_dollars"] / m["bad_debt_dollars"]
    m["bad_debt_pct_instant"] = float(tot.loc["instant", "bad_debt_pct_of_refund_dollars"])
    m["bad_debt_pct_standard"] = float(tot.loc["standard", "bad_debt_pct_of_refund_dollars"])

    ct = read("05_refund_cycle_time")
    g = ct.groupby("refund_type").apply(
        lambda d: (d["avg_days_request_to_refund"] * d["refunds"]).sum() / d["refunds"].sum(),
        include_groups=False)
    m["avg_days_instant"] = float(g["instant"])
    m["avg_days_standard"] = float(g["standard"])
    inst = ct[ct["refund_type"] == "instant"]
    m["instant_exposure_days"] = float((inst["avg_days_refund_to_receipt"] * inst["refunds"]).sum() / inst["refunds"].sum())

    reasons = read("04_return_reason_condition_mix").set_index("reason_code")
    m["nln_share"] = float(reasons.loc["no_longer_needed", "pct_of_returns"])
    m["nln_mismatch_rate"] = float(reasons.loc["no_longer_needed", "mismatch_rate_pct"])
    m["defective_mismatch_rate"] = float(reasons.loc["defective", "mismatch_rate_pct"])

    tiers = read("08_risk_score_tiers").set_index("risk_tier")
    m["high_tier_customers"] = int(tiers.loc["High", "customers"])
    m["high_tier_pct"] = float(tiers.loc["High", "pct_of_customers"])
    m["medium_tier_pct"] = float(tiers.loc["Medium", "pct_of_customers"])
    m["low_tier_pct"] = float(tiers.loc["Low", "pct_of_customers"])

    tv = read("09_tier_outcomes_validation").set_index("risk_tier")
    m["perf_loss_dollars"] = float(tv["loss_dollars"].sum())
    m["high_loss_share"] = float(tv.loc["High", "pct_of_loss_dollars"])
    m["high_active_share"] = float(tv.loc["High", "pct_of_active_customers"])
    m["high_loss_event_rate"] = float(tv.loc["High", "loss_event_rate_pct"])
    m["medium_loss_event_rate"] = float(tv.loc["Medium", "loss_event_rate_pct"])
    m["low_loss_event_rate"] = float(tv.loc["Low", "loss_event_rate_pct"])
    m["high_loss_per_customer"] = float(tv.loc["High", "loss_dollars_per_active_customer"])
    m["low_loss_per_customer"] = float(tv.loc["Low", "loss_dollars_per_active_customer"])
    m["good_customers_total"] = int(tv["good_customers"].sum())

    pol = read("11_policy_simulation").set_index("scenario_id")
    m["policy"] = pol.reset_index().to_dict(orient="records")
    for sid in range(1, 8):
        m[f"s{sid}_saved"] = float(pol.loc[sid, "dollars_saved"])
        m[f"s{sid}_pct_loss"] = float(pol.loc[sid, "pct_of_baseline_loss"])
        m[f"s{sid}_good_affected"] = int(pol.loc[sid, "good_customers_affected"])
        m[f"s{sid}_pct_good"] = float(pol.loc[sid, "pct_good_customers_affected"])

    pat = read("12_abuse_patterns")
    m["patterns"] = pat.to_dict(orient="records")

    coh = read("10_cohort_view")
    perf = coh[coh["period"] == "performance"].set_index("signup_cohort")
    m["cohort_old_loss_per_1k"] = float(perf.loc["1. before 2022", "loss_dollars_per_1k_orders"])
    m["cohort_old_return_rate"] = float(perf.loc["1. before 2022", "return_rate_pct"])
    new = perf.loc[["4. 2024 H1", "5. 2024 H2", "6. 2025 H1", "7. 2025 H2"]]
    m["cohort_new_return_rate"] = float((new["return_rate_pct"] * new["orders"]).sum() / new["orders"].sum())
    m["cohort_new_loss_per_1k"] = float((new["loss_dollars_per_1k_orders"] * new["orders"]).sum() / new["orders"].sum())

    m["stats"] = json.loads((PROCESSED / "stats_summary.json").read_text())
    ors = read("stats_logit_odds_ratios").set_index("term")
    m["or_address_cluster"] = float(ors.loc["flag_address_cluster", "odds_ratio"])
    m["or_mismatch"] = float(ors.loc["flag_mismatch", "odds_ratio"])
    m["or_roll90"] = float(ors.loc["flag_roll90", "odds_ratio"])
    m["or_never_received"] = float(ors.loc["flag_never_received", "odds_ratio"])

    con = sqlite3.connect(DB_PATH)
    m["customers"] = int(con.execute("SELECT COUNT(*) FROM customers").fetchone()[0])
    m["refund_dollars_total"] = float(con.execute("SELECT SUM(refund_amount) FROM return_facts").fetchone()[0])
    m["instant_refund_share"] = float(con.execute(
        "SELECT 1.0*SUM(instant_refund_flag)/SUM(refund_issued) FROM return_facts WHERE is_inr=0").fetchone()[0])
    con.close()
    m["params"] = {k: getattr(C, k) for k in [
        "SCORING_CUTOFF", "EXTRACT_DATE", "BAD_DEBT_DAYS", "HIGH_VALUE_THRESHOLD", "RESTOCK_FEE_RATE",
        "REPEAT_RETURNS_90D", "INR_DENY_RATE", "TIER_HIGH_CUTOFF", "TIER_MED_CUTOFF"]}
    (PROCESSED / "metrics.json").write_text(json.dumps(m, indent=2, default=str))
    return m


def load():
    return json.loads((PROCESSED / "metrics.json").read_text())


if __name__ == "__main__":
    out = build()
    print({k: v for k, v in out.items() if not isinstance(v, (list, dict))})
