-- Sanity checks before doing anything else: counts, nulls, bad ratings, dupes, orphan movie IDs.
SELECT
    (SELECT COUNT(*) FROM ratings)                                         AS rating_rows,
    (SELECT COUNT(*) FROM movies)                                          AS movie_rows,
    (SELECT COUNT(DISTINCT userId) FROM ratings)                           AS users,
    (SELECT COUNT(DISTINCT movieId) FROM ratings)                          AS rated_movies,
    (SELECT COUNT(*) FROM ratings WHERE rating IS NULL)                    AS null_ratings,
    (SELECT COUNT(*) FROM ratings WHERE rating < 0.5 OR rating > 5)        AS out_of_range_ratings,
    (SELECT COUNT(*) FROM (SELECT userId, movieId FROM ratings
                           GROUP BY userId, movieId HAVING COUNT(*) > 1))  AS duplicate_user_movie_pairs,
    (SELECT COUNT(*) FROM ratings r LEFT JOIN movies m ON r.movieId = m.movieId
      WHERE m.movieId IS NULL)                                             AS ratings_without_movie;
