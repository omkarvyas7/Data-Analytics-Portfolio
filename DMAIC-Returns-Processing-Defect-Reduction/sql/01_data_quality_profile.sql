-- 01_data_quality_profile.sql
-- Quick profile of the cleaned tables before baselining anything (Measure).
-- Question: is the data complete enough to trust a defect-rate baseline?
-- Returns one row per check with a count and its share of units.
-- Written for SQLite. On Redshift/Postgres, swap the julianday() date math.
WITH unit_stats AS (
    SELECT COUNT(*)                                           AS total_units,
           SUM(price_imputed_flag)                            AS imputed_price,
           SUM(CASE WHEN dock_to_disposition_hrs IS NULL THEN 1 ELSE 0 END) AS null_cycle_time,
           COUNT(DISTINCT associate_id)                       AS associates,
           MIN(op_date)                                       AS first_day,
           MAX(op_date)                                       AS last_day
    FROM v_units
),
audit_stats AS (
    SELECT COUNT(*) AS audited_units FROM v_audited
)
SELECT 'Units processed (clean)'               AS check_name, total_units AS value, 1.0 AS share_of_units FROM unit_stats
UNION ALL
SELECT 'Units audited (QA sample)', a.audited_units, ROUND(1.0 * a.audited_units / u.total_units, 4) FROM unit_stats u, audit_stats a
UNION ALL
SELECT 'Units with imputed price', imputed_price, ROUND(1.0 * imputed_price / total_units, 4) FROM unit_stats
UNION ALL
SELECT 'Units with NULL cycle time (bad stage data)', null_cycle_time, ROUND(1.0 * null_cycle_time / total_units, 4) FROM unit_stats
UNION ALL
SELECT 'Distinct associates', associates, NULL FROM unit_stats
UNION ALL
SELECT 'Days covered', CAST(julianday(last_day) - julianday(first_day) + 1 AS INTEGER), NULL FROM unit_stats;
