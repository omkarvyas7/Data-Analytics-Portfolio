-- 04_roi_by_genre.sql
-- Which genres turn budget into box office most efficiently? Looks at return per dollar
-- alongside total gross.
-- Per Disney genre: films, avg gross and budget ($M, adjusted), pooled ROI (sum gross / sum budget),
-- average ROI and the % of films that out-grossed their budget.
-- ROI here is domestic gross / production budget. Marketing, international and home video are left out.

SELECT disney_genre,
       COUNT(*)                                                       AS films,
       ROUND(AVG(inflation_adjusted_gross) / 1e6, 1)                  AS avg_adj_gross_musd,
       ROUND(AVG(inflation_budget) / 1e6, 1)                          AS avg_adj_budget_musd,
       ROUND(SUM(inflation_adjusted_gross) / SUM(inflation_budget), 2) AS pooled_roi,
       ROUND(AVG(roi_multiple), 2)                                    AS avg_roi,
       ROUND(100.0 * AVG(CASE WHEN roi_multiple >= 1 THEN 1 ELSE 0 END), 1) AS pct_films_roi_ge_1
FROM films
GROUP BY disney_genre
HAVING COUNT(*) >= 3
ORDER BY pooled_roi DESC;
