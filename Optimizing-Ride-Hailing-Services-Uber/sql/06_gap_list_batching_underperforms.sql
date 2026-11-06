-- 06_gap_list_batching_underperforms.sql
-- Gap list: windows where batching with a radius (min-ETA) looks worse than greedy
-- first-dispatch on some rider or money KPI.
-- Question: which windows would a dashboard flag after rollout, and are they real regressions
-- or just a side effect of serving more riders?
-- One row per flagged window with gap type, KPI deltas, supply ratio and MDR, worst first.

WITH g AS (
    SELECT window_id, riders, drivers, mdr_miles, matched AS g_matched,
           total_enroute_min / NULLIF(matched, 0) AS g_eta, p90_eta_min AS g_p90, profit_usd AS g_profit
    FROM simulation_results WHERE protocol = 'greedy_first_dispatch_mdr'
),
b AS (
    SELECT window_id, matched AS b_matched,
           total_enroute_min / NULLIF(matched, 0) AS b_eta, p90_eta_min AS b_p90, profit_usd AS b_profit
    FROM simulation_results WHERE protocol = 'batched_min_eta_mdr'
),
cmp AS (
    SELECT g.*, b.b_matched, b.b_eta, b.b_p90, b.b_profit,
           b.b_eta - g.g_eta       AS eta_delta_min,
           b.b_p90 - g.g_p90       AS p90_delta_min,
           b.b_profit - g.g_profit AS profit_delta_usd,
           b.b_matched - g.g_matched AS extra_riders_served
    FROM g JOIN b USING (window_id)
)
SELECT
    window_id,
    CASE
        WHEN eta_delta_min > 0 AND extra_riders_served > 0
            THEN 'Higher avg ETA - serves more riders (expected trade-off)'
        WHEN eta_delta_min > 0
            THEN 'Higher avg ETA - same riders served (true regression)'
        WHEN p90_delta_min > 0
            THEN 'Longer p90 tail - avg ETA better'
        ELSE     'Lower contribution - ETA better'
    END                                    AS gap_type,
    riders, drivers,
    ROUND(1.0 * drivers / riders, 2)       AS supply_ratio,
    mdr_miles,
    extra_riders_served,
    ROUND(eta_delta_min, 3)                AS avg_eta_delta_min,
    ROUND(p90_delta_min, 3)                AS p90_delta_min,
    ROUND(profit_delta_usd, 2)             AS contribution_delta_usd
FROM cmp
WHERE eta_delta_min > 1e-9 OR p90_delta_min > 1e-9 OR profit_delta_usd < -1e-9
ORDER BY eta_delta_min DESC, p90_delta_min DESC;
