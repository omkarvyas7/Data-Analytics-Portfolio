-- Long tail check: how many movies have too few ratings to trust?
-- Used this to pick the popularity cutoff for the recommender.
WITH per_movie AS (
    SELECT movieId, COUNT(*) AS n_ratings
    FROM ratings
    GROUP BY movieId
),
bucketed AS (
    SELECT CASE
             WHEN n_ratings = 1 THEN '01: 1'
             WHEN n_ratings < 10 THEN '02: 2-9'
             WHEN n_ratings < 50 THEN '03: 10-49'
             WHEN n_ratings < 100 THEN '04: 50-99'
             ELSE '05: 100+'
           END AS rating_count_bucket,
           n_ratings
    FROM per_movie
)
SELECT rating_count_bucket,
       COUNT(*)                                                     AS movies,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1)           AS pct_of_movies,
       SUM(n_ratings)                                               AS ratings,
       ROUND(100.0 * SUM(n_ratings) / SUM(SUM(n_ratings)) OVER (), 1) AS pct_of_ratings
FROM bucketed
GROUP BY rating_count_bucket
ORDER BY rating_count_bucket;
