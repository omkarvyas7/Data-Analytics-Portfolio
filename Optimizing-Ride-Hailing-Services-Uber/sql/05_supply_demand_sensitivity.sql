-- 05_supply_demand_sensitivity.sql
-- How the batching gain changes with drivers per rider.
-- Question: does batching help most when drivers are scarce, and where is the gain too small
-- to matter?
-- One row per supply segment: greedy vs batched ETA (no radius), % reduction, match rate, rank.

WITH seg AS (
    SELECT
        r.*,
        CASE
            WHEN 1.0 * drivers / riders < 0.8 THEN '1. Under-supplied (<0.8)'
            WHEN 1.0 * drivers / riders < 1.0 THEN '2. Tight (0.8-1.0)'
            WHEN 1.0 * drivers / riders < 1.2 THEN '3. Balanced (1.0-1.2)'
            ELSE                                   '4. Over-supplied (>=1.2)'
        END AS supply_segment
    FROM simulation_results r
    WHERE protocol IN ('greedy_first_dispatch', 'batched_min_eta')
),
agg AS (
    SELECT
        supply_segment,
        COUNT(DISTINCT window_id)                                                       AS windows,
        SUM(CASE WHEN protocol = 'greedy_first_dispatch' THEN total_enroute_min END)
          / SUM(CASE WHEN protocol = 'greedy_first_dispatch' THEN matched END)          AS greedy_eta,
        SUM(CASE WHEN protocol = 'batched_min_eta' THEN total_enroute_min END)
          / SUM(CASE WHEN protocol = 'batched_min_eta' THEN matched END)                AS batched_eta,
        1.0 * SUM(CASE WHEN protocol = 'batched_min_eta' THEN matched END)
          / SUM(CASE WHEN protocol = 'batched_min_eta' THEN riders END)                 AS match_rate,
        1.0 * SUM(CASE WHEN protocol = 'batched_min_eta' THEN matched END)
          / SUM(CASE WHEN protocol = 'batched_min_eta' THEN drivers END)                AS driver_util
    FROM seg
    GROUP BY supply_segment
)
SELECT
    supply_segment,
    windows,
    ROUND(greedy_eta, 3)                                         AS greedy_avg_eta_min,
    ROUND(batched_eta, 3)                                        AS batched_avg_eta_min,
    ROUND(greedy_eta - batched_eta, 3)                           AS eta_saved_min_per_rider,
    ROUND(100.0 * (1 - batched_eta / greedy_eta), 2)             AS eta_reduction_pct,
    ROUND(100.0 * match_rate, 2)                                 AS match_rate_pct,
    ROUND(100.0 * driver_util, 2)                                AS driver_utilization_pct,
    RANK() OVER (ORDER BY (1 - batched_eta / greedy_eta) DESC)   AS rank_by_eta_reduction
FROM agg
ORDER BY supply_segment;
