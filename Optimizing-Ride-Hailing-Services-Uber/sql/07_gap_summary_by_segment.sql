-- 07_gap_summary_by_segment.sql
-- Rolls the 06 gap list up by gap type and supply segment.
-- Question: do the bad windows cluster somewhere we can guard against (tight radius,
-- under-supply), or are they noise?
-- One row per gap type x supply segment: window count, share of the segment, average deltas.

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
    SELECT g.window_id, g.mdr_miles,
           CASE WHEN 1.0 * g.drivers / g.riders < 1.0 THEN 'Under/tight supply (<1.0)'
                ELSE 'Balanced/over supply (>=1.0)' END                   AS supply_segment,
           b.b_eta - g.g_eta AS eta_delta, b.b_p90 - g.g_p90 AS p90_delta,
           b.b_profit - g.g_profit AS profit_delta, b.b_matched - g.g_matched AS extra
    FROM g JOIN b USING (window_id)
),
flagged AS (
    SELECT cmp.*,
           CASE
               WHEN eta_delta > 1e-9 AND extra > 0 THEN 'Higher avg ETA - serves more riders'
               WHEN eta_delta > 1e-9               THEN 'Higher avg ETA - same riders served'
               WHEN p90_delta > 1e-9               THEN 'Longer p90 tail only'
               WHEN profit_delta < -1e-9           THEN 'Lower contribution only'
               ELSE                                     'No gap'
           END AS gap_type
    FROM cmp
)
SELECT
    gap_type,
    supply_segment,
    COUNT(*)                                                                    AS windows,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (PARTITION BY supply_segment), 1) AS pct_of_segment_windows,
    ROUND(AVG(mdr_miles), 2)                                                    AS avg_mdr_miles,
    ROUND(AVG(extra), 2)                                                        AS avg_extra_riders_served,
    ROUND(AVG(eta_delta), 3)                                                    AS avg_eta_delta_min,
    ROUND(AVG(profit_delta), 2)                                                 AS avg_contribution_delta_usd
FROM flagged
GROUP BY gap_type, supply_segment
ORDER BY supply_segment, windows DESC;
