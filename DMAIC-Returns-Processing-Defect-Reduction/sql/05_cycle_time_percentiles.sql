-- 05_cycle_time_percentiles.sql
-- Dock-to-disposition hours by site and month: mean, p50, p90, p95 and share over the 48 h SLA (Measure).
-- SQLite has no PERCENTILE_CONT, so this takes nearest-rank percentiles from ROW_NUMBER and COUNT.
-- On Redshift/Postgres, PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY ...) does the same job.
WITH r AS (
    SELECT site_id, month, dock_to_disposition_hrs AS hrs, sla_breach_flag,
           ROW_NUMBER() OVER (PARTITION BY site_id, month ORDER BY dock_to_disposition_hrs) AS rn,
           COUNT(*)     OVER (PARTITION BY site_id, month)                                AS cnt
    FROM v_units
    WHERE dock_to_disposition_hrs IS NOT NULL
)
SELECT site_id, month,
       COUNT(*)                                        AS units,
       ROUND(AVG(hrs), 2)                              AS mean_hrs,
       MIN(CASE WHEN rn >= 0.50 * cnt THEN hrs END)    AS p50_hrs,
       MIN(CASE WHEN rn >= 0.90 * cnt THEN hrs END)    AS p90_hrs,
       MIN(CASE WHEN rn >= 0.95 * cnt THEN hrs END)    AS p95_hrs,
       ROUND(AVG(sla_breach_flag), 4)                  AS sla_breach_rate
FROM r
GROUP BY site_id, month
ORDER BY site_id, month;
