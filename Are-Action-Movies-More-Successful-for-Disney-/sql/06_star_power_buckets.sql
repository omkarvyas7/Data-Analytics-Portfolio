-- 06_star_power_buckets.sql
-- Does a bigger-name lead show up at the box office?
-- Star-power quartile (NTILE(4) on the lead actor's popularity rating) by Action flag:
-- films, average gross and budget ($M), pooled ROI.

WITH bucketed AS (
    SELECT *,
           NTILE(4) OVER (ORDER BY star_power) AS star_quartile
    FROM films
)
SELECT star_quartile,
       MIN(star_power)                                                 AS min_star_power,
       MAX(star_power)                                                 AS max_star_power,
       CASE WHEN is_action = 1 THEN 'Action' ELSE 'Non-Action' END     AS segment,
       COUNT(*)                                                        AS films,
       ROUND(AVG(inflation_adjusted_gross) / 1e6, 1)                   AS avg_adj_gross_musd,
       ROUND(AVG(inflation_budget) / 1e6, 1)                           AS avg_adj_budget_musd,
       ROUND(SUM(inflation_adjusted_gross) / SUM(inflation_budget), 2) AS pooled_roi
FROM bucketed
GROUP BY star_quartile, segment
ORDER BY star_quartile, segment;
