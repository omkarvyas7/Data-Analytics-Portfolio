"""Statistical validation of the rule-based risk tiers.

1. Chi-square test of independence: risk tier x loss event (performance window).
2. Two-proportion z-tests: High vs Low and Medium vs Low loss-event rates.
3. Logistic regression (statsmodels): loss event ~ the score's rule flags,
   reported as odds ratios with 95% confidence intervals.
4. Ranking power of the points score (AUC via Mann-Whitney U).

Outputs in data/processed/: stats_tier_tests.csv, stats_logit_odds_ratios.csv,
stats_summary.json
"""
import json
import sqlite3

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from scipy import stats
from statsmodels.stats.proportion import proportions_ztest

from config import DB_PATH, PROCESSED

FLAGS = {
    "flag_roll90": "90-day return rate >= 50%",
    "flag_dollar_share": "Return $ share >= 50%",
    "flag_mismatch": "1+ condition mismatch",
    "flag_inr": "1+ INR claim",
    "flag_never_received": "1+ never-received refund",
    "flag_address_cluster": "Address in INR cluster",
    "flag_new_account": "Account < 180 days old",
}


def load():
    con = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query(
        """SELECT o.*, r.pts_roll90, r.pts_dollar_share, r.pts_mismatch, r.pts_inr,
                  r.pts_never_received, r.pts_address_cluster, r.pts_new_account
           FROM customer_outcomes o JOIN customer_risk r USING (customer_id)
           WHERE o.perf_active = 1""", con)
    con.close()
    for f, col in zip(FLAGS, ["pts_roll90", "pts_dollar_share", "pts_mismatch", "pts_inr",
                              "pts_never_received", "pts_address_cluster", "pts_new_account"]):
        df[f] = (df[col] > 0).astype(int)
    return df


def tier_tests(df):
    ct = pd.crosstab(df["risk_tier"], df["perf_loss_event"])
    chi2, p, dof, _ = stats.chi2_contingency(ct)
    rows = [{"test": "Chi-square: tier x loss event", "statistic": chi2, "dof": dof, "p_value": p,
             "group_a": "All tiers", "rate_a": np.nan, "group_b": "", "rate_b": np.nan}]
    g = df.groupby("risk_tier")["perf_loss_event"].agg(["sum", "count"])
    for a in ["High", "Medium"]:
        z, pz = proportions_ztest([g.loc[a, "sum"], g.loc["Low", "sum"]],
                                  [g.loc[a, "count"], g.loc["Low", "count"]])
        rows.append({"test": f"Two-proportion z-test: {a} vs Low", "statistic": z, "dof": np.nan,
                     "p_value": pz, "group_a": a, "rate_a": g.loc[a, "sum"] / g.loc[a, "count"],
                     "group_b": "Low", "rate_b": g.loc["Low", "sum"] / g.loc["Low", "count"]})
    return pd.DataFrame(rows), chi2, p


def logit(df):
    formula = "perf_loss_event ~ " + " + ".join(FLAGS) + " + is_member"
    model = smf.logit(formula, data=df).fit(disp=False)
    ci = model.conf_int()
    out = pd.DataFrame({
        "term": model.params.index,
        "description": [FLAGS.get(t, "Member account" if t == "is_member" else "Intercept")
                        for t in model.params.index],
        "coef": model.params.values,
        "odds_ratio": np.exp(model.params.values),
        "or_ci_low": np.exp(ci[0].values),
        "or_ci_high": np.exp(ci[1].values),
        "p_value": model.pvalues.values,
    })
    return model, out


def auc(score, y):
    pos, neg = score[y == 1], score[y == 0]
    u = stats.mannwhitneyu(pos, neg, alternative="two-sided").statistic
    return u / (len(pos) * len(neg))


def main():
    df = load()
    tests, chi2, p = tier_tests(df)
    tests.to_csv(PROCESSED / "stats_tier_tests.csv", index=False)
    model, ors = logit(df)
    ors.to_csv(PROCESSED / "stats_logit_odds_ratios.csv", index=False)
    score_model = smf.logit("perf_loss_event ~ risk_score", data=df).fit(disp=False)
    rates = df.groupby("risk_tier")["perf_loss_event"].mean()
    summary = {
        "n_active_customers": int(len(df)),
        "base_loss_event_rate": float(df["perf_loss_event"].mean()),
        "loss_event_rate_by_tier": {k: float(v) for k, v in rates.items()},
        "lift_high_vs_low": float(rates["High"] / rates["Low"]),
        "chi2": float(chi2), "chi2_p_value": float(p),
        "z_high_vs_low": float(tests.loc[1, "statistic"]), "p_high_vs_low": float(tests.loc[1, "p_value"]),
        "z_med_vs_low": float(tests.loc[2, "statistic"]), "p_med_vs_low": float(tests.loc[2, "p_value"]),
        "logit_pseudo_r2": float(model.prsquared),
        "logit_llr_p_value": float(model.llr_pvalue),
        "score_odds_ratio_per_point": float(np.exp(score_model.params["risk_score"])),
        "score_auc": float(auc(df["risk_score"].values, df["perf_loss_event"].values)),
    }
    (PROCESSED / "stats_summary.json").write_text(json.dumps(summary, indent=2))
    print(tests.round(4).to_string(index=False))
    print(ors.round(3).to_string(index=False))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
