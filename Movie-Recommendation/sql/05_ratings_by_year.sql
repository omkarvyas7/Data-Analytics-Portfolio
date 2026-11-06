-- Ratings per year: is there enough steady volume to retrain on a schedule?
-- One row per year: ratings, active users, average rating.
SELECT CAST(strftime('%Y', datetime(timestamp, 'unixepoch')) AS INTEGER) AS rating_year,
       COUNT(*)                AS ratings,
       COUNT(DISTINCT userId)  AS active_users,
       ROUND(AVG(rating), 3)   AS avg_rating
FROM ratings
GROUP BY rating_year
ORDER BY rating_year;
