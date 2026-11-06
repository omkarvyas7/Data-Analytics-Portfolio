/* 02_kpi_vs_target_rag.sql
Which KPIs missed target this week, by how much, and has the miss lasted?

Param: :week_start
RAG for lower-is-better KPIs:
  Green  actual <= target
  Amber  target < actual <= target * (1 + amber_band)
  Red    actual >  target * (1 + amber_band)
Higher-is-better KPIs flip it. amber_band is set per KPI in kpi_targets (default 5%).
Returns one row per KPI with variance_abs, variance_pct (+ = unfavourable), rag and
weeks_missed_last_4.
*/
WITH k AS (
    SELECT l.week_start, l.kpi, l.value, t.target, t.direction, t.amber_band
    FROM v_weekly_kpi_long l
    JOIN kpi_targets t ON t.kpi = l.kpi
),
scored AS (
    SELECT
        week_start, kpi, value, target, direction, amber_band,
        CASE WHEN direction = 'lower' THEN (value - target) / target
             ELSE (target - value) / target END                     AS unfavourable_pct,
        CASE
            WHEN direction = 'lower' AND value <= target                       THEN 'Green'
            WHEN direction = 'lower' AND value <= target * (1 + amber_band)    THEN 'Amber'
            WHEN direction = 'lower'                                           THEN 'Red'
            WHEN direction = 'higher' AND value >= target                      THEN 'Green'
            WHEN direction = 'higher' AND value >= target * (1 - amber_band)   THEN 'Amber'
            ELSE 'Red'
        END                                                          AS rag
    FROM k
),
persistence AS (
    SELECT kpi, SUM(CASE WHEN rag <> 'Green' THEN 1 ELSE 0 END) AS weeks_missed_last_4
    FROM scored
    WHERE week_start BETWEEN date(:week_start, '-21 days') AND :week_start
    GROUP BY kpi
)
SELECT
    t.sort_order,
    s.kpi,
    t.display_name,
    t.unit,
    s.direction,
    s.value                       AS actual,
    s.target,
    s.value - s.target            AS variance_abs,
    s.unfavourable_pct            AS variance_pct,
    s.rag,
    p.weeks_missed_last_4,
    t.owner_team,
    t.initiative_id
FROM scored s
JOIN kpi_targets t  ON t.kpi = s.kpi
JOIN persistence p  ON p.kpi = s.kpi
WHERE s.week_start = :week_start
ORDER BY t.sort_order;
