-- 02_revenue_by_genre_decade.sql
-- Which genres carried Disney's box office in each decade? Uses the full release list
-- (579 titles, 1937-2016), so genres without budget data are included.
-- One row per decade and genre: titles, total and average adjusted gross ($M), share of the decade.

WITH base AS (
    SELECT (CAST(substr(release_date, 1, 4) AS INTEGER) / 10) * 10 AS decade,
           COALESCE(NULLIF(genre, ''), 'Unknown')                  AS genre,
           inflation_adjusted_gross
    FROM disney_gross
),
agg AS (
    SELECT decade, genre,
           COUNT(*)                       AS titles,
           SUM(inflation_adjusted_gross)  AS adj_gross
    FROM base
    GROUP BY decade, genre
)
SELECT decade,
       genre,
       titles,
       ROUND(adj_gross / 1e6, 1)                                               AS adj_gross_musd,
       ROUND(adj_gross / titles / 1e6, 1)                                      AS avg_adj_gross_musd,
       ROUND(100.0 * adj_gross / SUM(adj_gross) OVER (PARTITION BY decade), 1) AS pct_of_decade
FROM agg
ORDER BY decade, adj_gross DESC;
