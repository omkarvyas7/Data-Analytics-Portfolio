-- 05_rank_within_genre.sql
-- Is a genre's average carried by one or two hits?
-- Top 3 films per genre with RANK(), share of genre revenue and a running cumulative share.

WITH ranked AS (
    SELECT disney_genre,
           title,
           release_year,
           inflation_adjusted_gross,
           RANK() OVER (PARTITION BY disney_genre ORDER BY inflation_adjusted_gross DESC) AS genre_rank,
           SUM(inflation_adjusted_gross) OVER (PARTITION BY disney_genre)                 AS genre_total,
           SUM(inflation_adjusted_gross) OVER (PARTITION BY disney_genre
                                               ORDER BY inflation_adjusted_gross DESC
                                               ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS running_total,
           COUNT(*) OVER (PARTITION BY disney_genre)                                      AS genre_films
    FROM films
)
SELECT disney_genre,
       genre_rank,
       title,
       release_year,
       genre_films,
       ROUND(inflation_adjusted_gross / 1e6, 1)              AS adj_gross_musd,
       ROUND(100.0 * inflation_adjusted_gross / genre_total, 1) AS pct_of_genre,
       ROUND(100.0 * running_total / genre_total, 1)         AS cumulative_pct
FROM ranked
WHERE genre_rank <= 3 AND genre_films >= 3
ORDER BY disney_genre, genre_rank;
