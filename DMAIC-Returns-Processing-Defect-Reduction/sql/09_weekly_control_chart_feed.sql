-- 09_weekly_control_chart_feed.sql
-- Weekly network feed for the p-chart, the Excel KPI tracker and the dashboard (Control).
-- One row per Monday-start week: units, audits, defects, p, cycle time, recovery rate, waste and complaints.
-- Partial first and last weeks get partial_week_flag = 1 so the charts can drop them.
WITH u AS (
    SELECT week_start,
           MIN(phase)                                AS phase_min,
           MAX(phase)                                AS phase_max,
           COUNT(*)                                  AS units,
           COUNT(DISTINCT op_date)                   AS days_in_week,
           ROUND(AVG(dock_to_disposition_hrs), 2)    AS mean_cycle_hrs,
           ROUND(AVG(sla_breach_flag), 4)            AS sla_breach_rate,
           ROUND(SUM(recovery_achieved_usd), 2)      AS achieved_usd,
           ROUND(SUM(potential_recovery_usd), 2)     AS potential_usd,
           SUM(waste_flag)                           AS waste_units,
           SUM(customer_complaint_flag)              AS complaints
    FROM v_units
    GROUP BY week_start
),
a AS (
    SELECT week_start, COUNT(*) AS audited_units, SUM(is_defect) AS defects
    FROM v_audited
    GROUP BY week_start
)
SELECT u.week_start,
       CASE WHEN u.week_start < '2026-03-01' THEN 'Baseline'
            WHEN u.week_start < '2026-05-01' THEN 'Pilot' ELSE 'Control' END AS phase,
       u.days_in_week, CASE WHEN u.days_in_week < 7 THEN 1 ELSE 0 END AS partial_week_flag,
       u.units, a.audited_units, a.defects,
       ROUND(1.0 * a.defects / a.audited_units, 4)                    AS defect_rate,
       u.mean_cycle_hrs, u.sla_breach_rate,
       u.achieved_usd, u.potential_usd,
       ROUND(u.achieved_usd / u.potential_usd, 4)                     AS recovery_rate,
       u.waste_units, u.complaints
FROM u JOIN a ON a.week_start = u.week_start
ORDER BY u.week_start;
