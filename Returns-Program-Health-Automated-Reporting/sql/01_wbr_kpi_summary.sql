/* 01_wbr_kpi_summary.sql
Headline KPI table for the WBR week: how each KPI moved WoW, YoY and against its
trailing-4-week average.

Param: :week_start (Monday, 'YYYY-MM-DD')
One row per KPI with current, prior week, WoW abs/pct, same week last year, YoY abs/pct,
T4W average and target. "Last year" is 364 days back so weekdays line up. T4W is the
plain mean of the current and 3 prior weekly values. The 1.0 * forces real division
(waste_units is an integer count).
*/
WITH k AS (
    SELECT week_start, kpi, value FROM v_weekly_kpi_long
),
cur AS (SELECT kpi, value FROM k WHERE week_start = :week_start),
pw  AS (SELECT kpi, value FROM k WHERE week_start = date(:week_start, '-7 days')),
py  AS (SELECT kpi, value FROM k WHERE week_start = date(:week_start, '-364 days')),
t4  AS (
    SELECT kpi, AVG(value) AS t4w_avg
    FROM k
    WHERE week_start BETWEEN date(:week_start, '-21 days') AND :week_start
    GROUP BY kpi
)
SELECT
    t.sort_order,
    t.kpi,
    t.display_name,
    t.unit,
    t.direction,
    cur.value                                   AS current_week,
    pw.value                                    AS prior_week,
    cur.value - pw.value                        AS wow_abs,
    1.0 * (cur.value - pw.value) / NULLIF(pw.value, 0) AS wow_pct,
    py.value                                    AS last_year,
    cur.value - py.value                        AS yoy_abs,
    1.0 * (cur.value - py.value) / NULLIF(py.value, 0) AS yoy_pct,
    t4.t4w_avg,
    t.target
FROM kpi_targets t
JOIN cur      ON cur.kpi = t.kpi
LEFT JOIN pw  ON pw.kpi  = t.kpi
LEFT JOIN py  ON py.kpi  = t.kpi
LEFT JOIN t4  ON t4.kpi  = t.kpi
ORDER BY t.sort_order;
