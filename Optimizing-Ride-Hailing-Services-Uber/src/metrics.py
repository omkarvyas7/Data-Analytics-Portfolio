"""Pull the headline numbers from the SQL outputs into one dict and key_metrics.json.

The docs read their numbers from here, so they stay in sync with the outputs.
"""
import json

import pandas as pd

from common import DATA_PROCESSED


def load() -> dict:
    rd = lambda n: pd.read_csv(DATA_PROCESSED / f"sql_{n}.csv")   # noqa: E731
    kpi = rd("01_kpi_by_protocol").set_index("protocol")
    imp = rd("02_batching_improvement_vs_greedy")
    dist = rd("03_eta_distribution_buckets")
    mdr = rd("04_mdr_sensitivity")
    sup = rd("05_supply_demand_sensitivity")
    gaps = rd("06_gap_list_batching_underperforms")
    tail = dist[dist.eta_bucket == "5. 12+ min"].set_index("protocol").pct_of_matched
    under5 = dist[dist.eta_bucket == "2. 3-5 min"].set_index("protocol").cumulative_pct
    m3 = mdr[mdr.mdr_miles == 3.0].set_index("protocol")
    m15 = mdr[mdr.mdr_miles == 1.5].set_index("protocol")
    no_rad, w_mdr, w_profit = imp.iloc[0], imp.iloc[1], imp.iloc[2]
    gt = gaps.gap_type.value_counts()
    m = {
        "windows": int(kpi.windows.iloc[0]),
        "riders": int(kpi.riders_requested.iloc[0]),
        "greedy_eta": kpi.loc["greedy_first_dispatch", "avg_eta_min"],
        "batched_eta": kpi.loc["batched_min_eta", "avg_eta_min"],
        "eta_pct": no_rad.avg_eta_pct_change,
        "greedy_p90": kpi.loc["greedy_first_dispatch", "avg_window_p90_eta_min"],
        "batched_p90": kpi.loc["batched_min_eta", "avg_window_p90_eta_min"],
        "p90_pct": no_rad.p90_eta_pct_change,
        "greedy_enroute": kpi.loc["greedy_first_dispatch", "avg_enroute_min_per_window"],
        "batched_enroute": kpi.loc["batched_min_eta", "avg_enroute_min_per_window"],
        "tail_greedy": tail["greedy_first_dispatch"], "tail_batched": tail["batched_min_eta"],
        "tail_batched_mdr": tail["batched_min_eta_mdr"],
        "under5_greedy": under5["greedy_first_dispatch"], "under5_batched": under5["batched_min_eta"],
        "match_nr": no_rad.baseline_match_rate_pct,
        "mdr_match_greedy": w_mdr.baseline_match_rate_pct, "mdr_match_batched": w_mdr.candidate_match_rate_pct,
        "mdr_match_pp": round(w_mdr.candidate_match_rate_pct - w_mdr.baseline_match_rate_pct, 2),
        "mdr_eta_greedy": w_mdr.baseline_avg_eta_min, "mdr_eta_batched": w_mdr.candidate_avg_eta_min,
        "mdr_eta_pct": w_mdr.avg_eta_pct_change,
        "mdr_contrib_pct": w_mdr.contribution_pct_change, "mdr_contrib_delta": w_mdr.contribution_delta_usd_per_window,
        "mdr_not_worse_pct": w_mdr.pct_windows_candidate_not_worse,
        "contrib_greedy_mdr_total": kpi.loc["greedy_first_dispatch_mdr", "total_contribution_usd"],
        "contrib_batched_mdr_total": kpi.loc["batched_min_eta_mdr", "total_contribution_usd"],
        "contrib_greedy_mdr_avg": kpi.loc["greedy_first_dispatch_mdr", "avg_contribution_usd_per_window"],
        "contrib_batched_mdr_avg": kpi.loc["batched_min_eta_mdr", "avg_contribution_usd_per_window"],
        "contrib_profit_mdr_avg": kpi.loc["batched_max_profit_mdr", "avg_contribution_usd_per_window"],
        "profit_contrib_pct": w_profit.contribution_pct_change, "profit_contrib_delta": w_profit.contribution_delta_usd_per_window,
        "profit_eta": w_profit.candidate_avg_eta_min, "profit_eta_pct": w_profit.avg_eta_pct_change,
        "util_nr": kpi.loc["batched_min_eta", "driver_utilization"] * 100,
        "util_greedy_mdr": kpi.loc["greedy_first_dispatch_mdr", "driver_utilization"] * 100,
        "util_batched_mdr": kpi.loc["batched_min_eta_mdr", "driver_utilization"] * 100,
        "m3_match_batched": m3.loc["batched_min_eta_mdr", "match_rate_pct"],
        "m3_match_greedy": m3.loc["greedy_first_dispatch_mdr", "match_rate_pct"],
        "m3_match_norad": m3.loc["batched_min_eta", "match_rate_pct"],
        "m3_eta_batched": m3.loc["batched_min_eta_mdr", "avg_eta_min"],
        "m3_eta_norad": m3.loc["batched_min_eta", "avg_eta_min"],
        "m15_match_batched": m15.loc["batched_min_eta_mdr", "match_rate_pct"],
        "m15_match_norad": m15.loc["batched_min_eta", "match_rate_pct"],
        "sup_under_pct": sup.iloc[0].eta_reduction_pct, "sup_under_saved": sup.iloc[0].eta_saved_min_per_rider,
        "sup_over_pct": sup.iloc[-1].eta_reduction_pct, "sup_over_saved": sup.iloc[-1].eta_saved_min_per_rider,
        "sup_under_windows": int(sup.iloc[0].windows), "sup_over_windows": int(sup.iloc[-1].windows),
        "gap_windows": int(len(gaps)),
        "gap_more_riders": int(gt.get("Higher avg ETA - serves more riders (expected trade-off)", 0)),
        "gap_true_regression": int(gt.get("Higher avg ETA - same riders served (true regression)", 0)),
        "gap_p90_only": int(gt.get("Longer p90 tail - avg ETA better", 0)),
        "gap_contrib_only": int(gt.get("Lower contribution - ETA better", 0)),
    }
    m = {k: (round(float(v), 2) if not isinstance(v, int) else v) for k, v in m.items()}
    m["contrib_uplift_total"] = round(m["contrib_batched_mdr_total"] - m["contrib_greedy_mdr_total"], 0)
    (DATA_PROCESSED / "key_metrics.json").write_text(json.dumps(m, indent=2))
    return m


if __name__ == "__main__":
    for k, v in load().items():
        print(f"{k}: {v}")
