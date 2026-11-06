-- 08_action_within_budget_band.sql
-- The budget confounder, head on: at similar budgets, does Action still out-gross other genres?
-- Budget tercile (NTILE(3) on adjusted budget) by segment, with films, avg budget and gross ($M)
-- and the Action vs non-Action gross gap in each band.

WITH banded AS (
    SELECT *,
           NTILE(3) OVER (ORDER BY inflation_budget) AS budget_band
    FROM films
),
agg AS (
    SELECT budget_band,
           CASE WHEN is_action = 1 THEN 'Action' ELSE 'Non-Action' END AS segment,
           COUNT(*)                       AS films,
           AVG(inflation_budget)          AS avg_budget,
           AVG(inflation_adjusted_gross)  AS avg_gross
    FROM banded
    GROUP BY budget_band, segment
)
SELECT a.budget_band,
       a.segment,
       a.films,
       ROUND(a.avg_budget / 1e6, 1) AS avg_adj_budget_musd,
       ROUND(a.avg_gross / 1e6, 1)  AS avg_adj_gross_musd,
       ROUND((a.avg_gross - n.avg_gross) / 1e6, 1) AS gap_vs_non_action_musd
FROM agg a
JOIN agg n
  ON n.budget_band = a.budget_band AND n.segment = 'Non-Action'
ORDER BY a.budget_band, a.segment;
