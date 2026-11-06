-- 03_eta_distribution_buckets.sql
-- Rider-level ETA by protocol, split into service-level bands.
-- Question: what share of matched riders wait under 5 minutes, and how big is the 12+ minute
-- tail under each protocol?
-- One row per protocol x band: rider count, share of matched riders, cumulative share.

WITH bucketed AS (
    SELECT
        protocol,
        CASE
            WHEN eta_min < 3  THEN '1. <3 min'
            WHEN eta_min < 5  THEN '2. 3-5 min'
            WHEN eta_min < 8  THEN '3. 5-8 min'
            WHEN eta_min < 12 THEN '4. 8-12 min'
            ELSE                   '5. 12+ min'
        END AS eta_bucket
    FROM simulation_matches
),
counts AS (
    SELECT protocol, eta_bucket, COUNT(*) AS riders
    FROM bucketed
    GROUP BY protocol, eta_bucket
)
SELECT
    protocol,
    eta_bucket,
    riders,
    ROUND(100.0 * riders / SUM(riders) OVER (PARTITION BY protocol), 2)          AS pct_of_matched,
    ROUND(100.0 * SUM(riders) OVER (PARTITION BY protocol ORDER BY eta_bucket
                                    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
                / SUM(riders) OVER (PARTITION BY protocol), 2)                   AS cumulative_pct
FROM counts
ORDER BY protocol, eta_bucket;
