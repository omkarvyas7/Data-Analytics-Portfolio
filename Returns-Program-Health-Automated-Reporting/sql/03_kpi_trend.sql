/* 03_kpi_trend.sql
Weekly trend per KPI for the charts, so a one-off week can be told apart from a trend.

Param: :week_start (the trend ends here and starts at the first full week)
Returns week_start x kpi with value, t4w_rolling_avg (window function), target and yoy_value.
*/
WITH k AS (
    SELECT week_start, kpi, value
    FROM v_weekly_kpi_long
    WHERE week_start <= :week_start
)
SELECT
    k.week_start,
    k.kpi,
    k.value,
    AVG(k.value) OVER (PARTITION BY k.kpi ORDER BY k.week_start
                       ROWS BETWEEN 3 PRECEDING AND CURRENT ROW)   AS t4w_rolling_avg,
    t.target,
    ly.value                                                       AS yoy_value
FROM k
JOIN kpi_targets t ON t.kpi = k.kpi
LEFT JOIN k ly     ON ly.kpi = k.kpi AND ly.week_start = date(k.week_start, '-364 days')
ORDER BY k.kpi, k.week_start;
