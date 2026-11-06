-- 07_marvel_vs_non_marvel.sql
-- Is "Action works" really "Marvel works"? Splits the sample into Marvel, non-Marvel Action
-- and everything else, with films, avg gross/budget ($M), pooled ROI and share of total revenue.

WITH seg AS (
    SELECT CASE WHEN is_marvel = 1 THEN '1 Marvel (any genre label)'
                WHEN is_action = 1 THEN '2 Action, non-Marvel'
                ELSE '3 All other genres' END AS segment,
           inflation_adjusted_gross,
           inflation_budget,
           imdb_score
    FROM films
)
SELECT segment,
       COUNT(*)                                                            AS films,
       ROUND(AVG(inflation_adjusted_gross) / 1e6, 1)                       AS avg_adj_gross_musd,
       ROUND(AVG(inflation_budget) / 1e6, 1)                               AS avg_adj_budget_musd,
       ROUND(SUM(inflation_adjusted_gross) / SUM(inflation_budget), 2)     AS pooled_roi,
       ROUND(AVG(imdb_score), 2)                                           AS avg_imdb_score,
       ROUND(100.0 * SUM(inflation_adjusted_gross) / SUM(SUM(inflation_adjusted_gross)) OVER (), 1) AS pct_of_revenue
FROM seg
GROUP BY segment
ORDER BY segment;
