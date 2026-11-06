-- 03_top_titles.sql
-- Are the biggest grossers also the best investments?
-- Top 15 films by adjusted domestic gross, with budget, ROI multiple and IMDb score.

SELECT title,
       release_year,
       disney_genre,
       company,
       ROUND(inflation_adjusted_gross / 1e6, 1) AS adj_gross_musd,
       ROUND(inflation_budget / 1e6, 1)         AS adj_budget_musd,
       ROUND(roi_multiple, 2)                   AS roi_multiple,
       imdb_score,
       is_marvel
FROM films
ORDER BY inflation_adjusted_gross DESC
LIMIT 15;
