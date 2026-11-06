-- 01_kpi_by_protocol.sql
-- KPI scorecard per dispatch protocol over all simulated windows.
-- Question: which protocol gives the shortest waits, keeps the most drivers busy and earns the
-- most contribution per window?
-- One row per protocol. avg_eta_min is rider-weighted (total minutes / matched riders).
-- Written for SQLite, ANSI-style, so it should run as-is on Postgres or Redshift.

SELECT
    protocol,
    COUNT(*)                                              AS windows,
    SUM(riders)                                           AS riders_requested,
    SUM(matched)                                          AS riders_matched,
    ROUND(1.0 * SUM(matched) / SUM(riders), 4)            AS match_rate,
    SUM(unmatched_riders)                                 AS riders_unmatched,
    ROUND(SUM(total_enroute_min) / SUM(matched), 3)       AS avg_eta_min,
    ROUND(AVG(p90_eta_min), 3)                            AS avg_window_p90_eta_min,
    ROUND(AVG(total_enroute_min), 2)                      AS avg_enroute_min_per_window,
    ROUND(1.0 * SUM(matched) / SUM(drivers), 4)           AS driver_utilization,
    ROUND(AVG(profit_usd), 2)                             AS avg_contribution_usd_per_window,
    ROUND(SUM(profit_usd), 0)                             AS total_contribution_usd
FROM simulation_results
GROUP BY protocol
ORDER BY avg_eta_min;
