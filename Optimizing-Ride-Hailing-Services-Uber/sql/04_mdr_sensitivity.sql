-- 04_mdr_sensitivity.sql
-- How match rate, ETA and contribution respond to the max dispatch radius (MDR).
-- Question: where should the MDR sit? How much match rate does each extra mile buy, and what
-- does it cost in ETA?
-- One row per MDR x protocol (the radius protocols plus no-radius batching as a reference),
-- with the change versus the next-smaller radius via LAG.

WITH by_mdr AS (
    SELECT
        mdr_miles,
        protocol,
        COUNT(*)                                        AS windows,
        1.0 * SUM(matched) / SUM(riders)                AS match_rate,
        SUM(total_enroute_min) / SUM(matched)           AS avg_eta_min,
        AVG(p90_eta_min)                                AS avg_p90_eta_min,
        AVG(profit_usd)                                 AS contribution_per_window
    FROM simulation_results
    WHERE protocol IN ('greedy_first_dispatch_mdr', 'batched_min_eta_mdr',
                       'batched_max_profit_mdr', 'batched_min_eta')
    GROUP BY mdr_miles, protocol
)
SELECT
    mdr_miles,
    protocol,
    windows,
    ROUND(100.0 * match_rate, 2)                                                AS match_rate_pct,
    ROUND(avg_eta_min, 3)                                                       AS avg_eta_min,
    ROUND(avg_p90_eta_min, 3)                                                   AS avg_p90_eta_min,
    ROUND(contribution_per_window, 2)                                           AS contribution_per_window,
    ROUND(100.0 * (match_rate - LAG(match_rate) OVER w), 2)                     AS match_rate_pp_vs_prev_mdr,
    ROUND(avg_eta_min - LAG(avg_eta_min) OVER w, 3)                             AS eta_min_vs_prev_mdr,
    RANK() OVER (PARTITION BY mdr_miles ORDER BY avg_eta_min)                   AS eta_rank_within_mdr
FROM by_mdr
WINDOW w AS (PARTITION BY protocol ORDER BY mdr_miles)
ORDER BY mdr_miles, protocol;
