-- 01_data_quality_checks.sql
-- Checks the source tables before anything else: gaps, duplicates and bad joins.
-- Returns three result sets:
--   1. null/blank counts in the Disney gross file
--   2. title-match errors (Disney release year and IMDb year more than a year apart)
--   3. duplicate titles and non-positive money fields in the merged file
-- Written for SQLite with plain CASE/aggregates, so it runs on Redshift/Postgres too.

SELECT 'disney_gross'                                               AS table_name,
       COUNT(*)                                                     AS row_count,
       SUM(CASE WHEN genre IS NULL OR genre = '' THEN 1 ELSE 0 END) AS missing_genre,
       SUM(CASE WHEN mpaa_rating IS NULL THEN 1 ELSE 0 END)         AS missing_mpaa,
       SUM(CASE WHEN total_gross <= 0 THEN 1 ELSE 0 END)            AS zero_gross,
       COUNT(*) - COUNT(DISTINCT movie_title || release_date)       AS duplicate_rows
FROM disney_gross;

SELECT name,
       CAST(substr(release_date, 7, 4) AS INTEGER)           AS disney_release_year,
       year                                                  AS imdb_year,
       budget,
       total_gross,
       'title matched to a different film (remake/same name)' AS issue
FROM merged_raw
WHERE ABS(CAST(substr(release_date, 7, 4) AS INTEGER) - year) > 1
ORDER BY name;

SELECT 'merged_raw'                                                    AS table_name,
       COUNT(*)                                                        AS row_count,
       COUNT(*) - COUNT(DISTINCT name)                                 AS duplicate_titles,
       SUM(CASE WHEN budget IS NULL OR budget <= 0 THEN 1 ELSE 0 END)  AS bad_budget,
       SUM(CASE WHEN star_rating IS NULL THEN 1 ELSE 0 END)            AS missing_star_power,
       (SELECT COUNT(*) FROM films)                                    AS rows_after_cleaning
FROM merged_raw;
