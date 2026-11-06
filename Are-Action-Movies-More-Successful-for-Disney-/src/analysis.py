"""Welch t-tests and OLS models (HC3 standard errors) on the cleaned film table.

Writes:
  data/processed/disney_clean.csv      cleaned film-level table (148 rows)
  data/processed/cleaning_log.csv      row counts per cleaning step
  data/processed/genre_summary.csv     genre-level KPIs
  data/processed/model_coefficients.csv
  data/processed/model_results.json    every headline number used in README/docs
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from scipy import stats

from common import PROCESSED, RAW, RESULTS_JSON, clean_final_df

MAIN = "log_gross ~ is_action + log_budget + star_power + imdb_score"


def fit(formula: str, data: pd.DataFrame):
    return smf.ols(formula, data).fit(cov_type="HC3")


def coef_rows(name: str, m) -> list[dict]:
    ci = m.conf_int()
    return [{"model": name, "term": t, "coef": m.params[t], "se_hc3": m.bse[t], "p_value": m.pvalues[t],
             "ci_low": ci.loc[t, 0], "ci_high": ci.loc[t, 1], "n": int(m.nobs), "r2": m.rsquared}
            for t in m.params.index]


def main() -> dict:
    PROCESSED.mkdir(parents=True, exist_ok=True)
    df, log, dropped = clean_final_df(return_log=True)
    df.to_csv(PROCESSED / "disney_clean.csv", index=False)
    log.to_csv(PROCESSED / "cleaning_log.csv", index=False)
    dropped.to_csv(PROCESSED / "dropped_title_mismatches.csv", index=False)
    raw_disney = pd.read_csv(RAW / "disney_movies_total_gross.csv")

    # Genre summary (Disney's own genre label)
    g = (df.groupby("disney_genre")
           .agg(films=("title", "count"),
                avg_adj_gross=("inflation_adjusted_gross", "mean"),
                median_adj_gross=("inflation_adjusted_gross", "median"),
                avg_adj_budget=("inflation_budget", "mean"),
                median_roi=("roi_multiple", "median"),
                avg_imdb_score=("imdb_score", "mean"))
           .sort_values("avg_adj_gross", ascending=False).reset_index())
    g.to_csv(PROCESSED / "genre_summary.csv", index=False)

    act = df.loc[df.is_action == 1]
    non = df.loc[df.is_action == 0]
    welch = stats.ttest_ind(act.inflation_adjusted_gross, non.inflation_adjusted_gross, equal_var=False)
    welch_log = stats.ttest_ind(act.log_gross, non.log_gross, equal_var=False)
    mw = stats.mannwhitneyu(act.inflation_adjusted_gross, non.inflation_adjusted_gross, alternative="two-sided")
    welch_roi = stats.ttest_ind(act.roi_multiple, non.roi_multiple, equal_var=False)

    models = {
        "M1 Action only": fit("log_gross ~ is_action", df),
        "M2 Main (controls)": fit(MAIN, df),
        "M3 Main excl. Marvel": fit(MAIN, df[df.is_marvel == 0]),
        "M4 Main, IMDb Action label": fit(MAIN.replace("is_action", "is_action_imdb"), df),
        "M5 Main + interactions": fit(MAIN + " + is_action:star_power + is_action:imdb_score", df),
    }
    coefs = pd.DataFrame([r for k, m in models.items() for r in coef_rows(k, m)])
    coefs.to_csv(PROCESSED / "model_coefficients.csv", index=False)

    m2 = models["M2 Main (controls)"]
    smear = float(np.mean(np.exp(m2.resid)))  # Duan smearing factor, used when converting log predictions back to dollars

    def pct(b):
        return float(np.exp(b) - 1)

    res = {
        "raw_disney_titles": int(len(raw_disney)),
        "raw_merged_rows": int(log.rows.iloc[0]),
        "clean_rows": int(len(df)),
        "rows_dropped_mismatch": int(log.rows.iloc[0] - log.rows.iloc[1]),
        "null_cells_raw": int(log.null_cells.iloc[0]),
        "year_min": int(df.release_year.min()), "year_max": int(df.release_year.max()),
        "n_action": int(len(act)), "n_non_action": int(len(non)),
        "n_marvel": int(df.is_marvel.sum()),
        "mean_gross_action": float(act.inflation_adjusted_gross.mean()),
        "mean_gross_non_action": float(non.inflation_adjusted_gross.mean()),
        "median_gross_action": float(act.inflation_adjusted_gross.median()),
        "median_gross_non_action": float(non.inflation_adjusted_gross.median()),
        "mean_budget_action": float(act.inflation_budget.mean()),
        "mean_budget_non_action": float(non.inflation_budget.mean()),
        "median_roi_action": float(act.roi_multiple.median()),
        "median_roi_non_action": float(non.roi_multiple.median()),
        "mean_roi_action": float(act.roi_multiple.mean()),
        "mean_roi_non_action": float(non.roi_multiple.mean()),
        "welch_t": float(welch.statistic), "welch_p": float(welch.pvalue),
        "welch_log_t": float(welch_log.statistic), "welch_log_p": float(welch_log.pvalue),
        "mannwhitney_p": float(mw.pvalue),
        "welch_roi_p": float(welch_roi.pvalue),
        "m1_action_coef": float(models["M1 Action only"].params["is_action"]),
        "m1_action_p": float(models["M1 Action only"].pvalues["is_action"]),
        "m1_action_pct": pct(models["M1 Action only"].params["is_action"]),
        "m2_r2": float(m2.rsquared), "m2_adj_r2": float(m2.rsquared_adj), "m2_n": int(m2.nobs),
        "m2_coef": {k: float(v) for k, v in m2.params.items()},
        "m2_p": {k: float(v) for k, v in m2.pvalues.items()},
        "m2_action_pct": pct(m2.params["is_action"]),
        "m2_action_ci_pct": [pct(m2.conf_int().loc["is_action", 0]), pct(m2.conf_int().loc["is_action", 1])],
        "m2_budget_elasticity": float(m2.params["log_budget"]),
        "m2_score_pct_per_point": pct(m2.params["imdb_score"]),
        "m2_star_pct_per_100": pct(100 * m2.params["star_power"]),
        "m3_action_pct": pct(models["M3 Main excl. Marvel"].params["is_action"]),
        "m3_action_p": float(models["M3 Main excl. Marvel"].pvalues["is_action"]),
        "m3_n": int(models["M3 Main excl. Marvel"].nobs),
        "m4_action_pct": pct(models["M4 Main, IMDb Action label"].params["is_action_imdb"]),
        "m4_action_p": float(models["M4 Main, IMDb Action label"].pvalues["is_action_imdb"]),
        "m5_interaction_p": {k: float(models["M5 Main + interactions"].pvalues[k])
                             for k in ["is_action:star_power", "is_action:imdb_score"]},
        "smearing_factor": smear,
        "corr_action_logbudget": float(df[["is_action", "log_budget"]].corr().iloc[0, 1]),
        "top_genre_by_avg_gross": str(g.disney_genre.iloc[0]),
        "top_genre_avg_gross": float(g.avg_adj_gross.iloc[0]),
        "median_roi_all": float(df.roi_multiple.median()),
        "score_q": {"p25": float(df.imdb_score.quantile(.25)), "p75": float(df.imdb_score.quantile(.75))},
    }
    res["action_significant_controls"] = bool(res["m2_p"]["is_action"] < 0.05)
    res["action_significant_ttest"] = bool(res["welch_p"] < 0.05)
    RESULTS_JSON.write_text(json.dumps(res, indent=2))
    return res


if __name__ == "__main__":
    r = main()
    print(json.dumps({k: r[k] for k in ["clean_rows", "n_action", "welch_p", "m2_r2", "m2_action_pct",
                                         "action_significant_controls"]}, indent=2))
    print("M2 p-values:", r["m2_p"])
