-- 02_batching_improvement_vs_greedy.sql
-- How much batched dispatch beats greedy first-dispatch on the same riders and drivers,
-- with and without a max dispatch radius (MDR).
-- Question: if we switch to batching, how far do ETA, en-route time, match rate and contribution
-- move, and in what share of windows does batching win?
-- One row per comparison (baseline -> candidate): both values, % change, and the share of
-- windows where the candidate is at least as good.
-- The "paired" CTE puts baseline and candidate side by side, one row per window per comparison.

WITH paired AS (
    SELECT
        c.label,
        b.window_id,
        b.total_enroute_min  AS b_enroute,  k.total_enroute_min  AS k_enroute,
        b.matched            AS b_matched,  k.matched            AS k_matched,
        b.riders,
        b.p90_eta_min        AS b_p90,      k.p90_eta_min        AS k_p90,
        b.profit_usd         AS b_profit,   k.profit_usd         AS k_profit
    FROM (
        SELECT '1. No radius: greedy -> batched min-ETA'            AS label,
               'greedy_first_dispatch' AS base, 'batched_min_eta' AS cand
        UNION ALL
        SELECT '2. With MDR: greedy -> batched min-ETA',
               'greedy_first_dispatch_mdr', 'batched_min_eta_mdr'
        UNION ALL
        SELECT '3. With MDR: greedy -> batched max-profit',
               'greedy_first_dispatch_mdr', 'batched_max_profit_mdr'
    ) c
    JOIN simulation_results b ON b.protocol = c.base
    JOIN simulation_results k ON k.protocol = c.cand AND k.window_id = b.window_id
)
SELECT
    label,
    COUNT(*)                                                          AS windows,
    ROUND(SUM(b_enroute) / SUM(b_matched), 3)                         AS baseline_avg_eta_min,
    ROUND(SUM(k_enroute) / SUM(k_matched), 3)                         AS candidate_avg_eta_min,
    ROUND(100.0 * ((SUM(k_enroute) / SUM(k_matched)) /
                   (SUM(b_enroute) / SUM(b_matched)) - 1), 2)        AS avg_eta_pct_change,
    ROUND(100.0 * (AVG(k_p90) / AVG(b_p90) - 1), 2)                   AS p90_eta_pct_change,
    ROUND(100.0 * SUM(b_matched) / SUM(riders), 2)                    AS baseline_match_rate_pct,
    ROUND(100.0 * SUM(k_matched) / SUM(riders), 2)                    AS candidate_match_rate_pct,
    ROUND(100.0 * (SUM(k_profit) / SUM(b_profit) - 1), 2)             AS contribution_pct_change,
    ROUND(AVG(k_profit - b_profit), 2)                                AS contribution_delta_usd_per_window,
    ROUND(100.0 * AVG(CASE WHEN k_matched >= b_matched
                            AND k_enroute / NULLIF(k_matched, 0)
                                <= b_enroute / NULLIF(b_matched, 0) + 1e-9
                           THEN 1.0 ELSE 0.0 END), 1)                 AS pct_windows_candidate_not_worse
FROM paired
GROUP BY label
ORDER BY label;
