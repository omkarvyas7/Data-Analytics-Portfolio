-- How concentrated is the feedback? Bucket users by how many ratings they give.
-- One row per segment: users, ratings, share of all ratings, avg rating given.
WITH per_user AS (
    SELECT userId, COUNT(*) AS n_ratings, AVG(rating) AS avg_rating
    FROM ratings
    GROUP BY userId
)
SELECT CASE
         WHEN n_ratings < 50 THEN '1: Light (<50)'
         WHEN n_ratings < 200 THEN '2: Medium (50-199)'
         WHEN n_ratings < 500 THEN '3: Heavy (200-499)'
         ELSE '4: Power (500+)'
       END                                                         AS user_segment,
       COUNT(*)                                                    AS users,
       SUM(n_ratings)                                              AS ratings,
       ROUND(100.0 * SUM(n_ratings) / SUM(SUM(n_ratings)) OVER (), 1) AS pct_of_ratings,
       ROUND(AVG(avg_rating), 2)                                   AS avg_rating_given
FROM per_user
GROUP BY user_segment
ORDER BY user_segment;
