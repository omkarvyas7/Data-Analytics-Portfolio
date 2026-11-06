/* 04_top_movers_category.sql
Which categories moved most week over week on the KPIs leaders watch, and was it good or bad?

Param: :week_start
Returns category x kpi with current, prior week, last year, WoW and YoY deltas, a
favourable flag, and rank_in_kpi (1 = biggest absolute WoW % move).
*/
WITH cat_week AS (
    SELECT
        f.week_start,
        f.category,
        SUM(f.return_units)                                     AS return_units,
        SUM(f.refund_cycle_hours) / 24.0 / NULLIF(SUM(f.cycle_units), 0) AS refund_cycle_days,
        1.0 * SUM(f.customer_contacts) / NULLIF(SUM(f.return_units), 0) AS contacts_per_return,
        SUM(f.recovered_usd) / NULLIF(SUM(f.refund_usd), 0)     AS recovery_rate,
        SUM(f.processing_cost_usd) / NULLIF(SUM(f.return_units), 0) AS cost_per_return
    FROM weekly_fact f
    WHERE f.week_start IN (:week_start, date(:week_start, '-7 days'), date(:week_start, '-364 days'))
    GROUP BY f.week_start, f.category
),
ship AS (
    SELECT week_start, category, SUM(units_shipped) AS units_shipped
    FROM weekly_ship
    WHERE week_start IN (:week_start, date(:week_start, '-7 days'), date(:week_start, '-364 days'))
    GROUP BY week_start, category
),
long AS (
    SELECT c.week_start, c.category, 'return_rate' AS kpi, 'lower' AS direction,
           1.0 * c.return_units / s.units_shipped AS value
    FROM cat_week c JOIN ship s ON s.week_start = c.week_start AND s.category = c.category
    UNION ALL SELECT week_start, category, 'refund_cycle_days', 'lower', refund_cycle_days FROM cat_week
    UNION ALL SELECT week_start, category, 'contacts_per_return', 'lower', contacts_per_return FROM cat_week
    UNION ALL SELECT week_start, category, 'recovery_rate', 'higher', recovery_rate FROM cat_week
    UNION ALL SELECT week_start, category, 'cost_per_return', 'lower', cost_per_return FROM cat_week
),
pivoted AS (
    SELECT
        category, kpi, direction,
        MAX(CASE WHEN week_start = :week_start THEN value END)                     AS current_week,
        MAX(CASE WHEN week_start = date(:week_start, '-7 days') THEN value END)    AS prior_week,
        MAX(CASE WHEN week_start = date(:week_start, '-364 days') THEN value END)  AS last_year
    FROM long
    GROUP BY category, kpi, direction
)
SELECT
    category,
    kpi,
    current_week,
    prior_week,
    last_year,
    current_week - prior_week                         AS wow_abs,
    (current_week - prior_week) / NULLIF(prior_week, 0) AS wow_pct,
    current_week - last_year                          AS yoy_abs,
    (current_week - last_year) / NULLIF(last_year, 0) AS yoy_pct,
    CASE WHEN (direction = 'lower'  AND current_week <= prior_week)
           OR (direction = 'higher' AND current_week >= prior_week) THEN 'Favourable'
         ELSE 'Unfavourable' END                      AS wow_direction,
    RANK() OVER (PARTITION BY kpi
                 ORDER BY ABS((current_week - prior_week) / NULLIF(prior_week, 0)) DESC) AS rank_in_kpi
FROM pivoted
ORDER BY kpi, rank_in_kpi;
