-- Top-rated movies, but only ones with 50+ ratings so the average actually means something.
WITH per_movie AS (
    SELECT m.title,
           COUNT(*)              AS n_ratings,
           ROUND(AVG(r.rating), 3) AS avg_rating
    FROM ratings r
    JOIN movies m ON m.movieId = r.movieId
    GROUP BY m.title
    HAVING COUNT(*) >= 50
)
SELECT RANK() OVER (ORDER BY avg_rating DESC, n_ratings DESC) AS rank_no,
       title, n_ratings, avg_rating
FROM per_movie
ORDER BY rank_no
LIMIT 15;
