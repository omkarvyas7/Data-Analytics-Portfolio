-- 04_defect_rate_by_segment.sql
-- Baseline defect rate split by category, site, shift, tenure band, correct disposition, photo step and month (Analyze).
-- Question: where do defects pile up, and which segments run well above the network rate?
-- index_vs_network = segment rate / network rate, so 1.00 is average.
WITH b AS (
    SELECT * FROM v_audited WHERE phase = 'Baseline'
),
seg AS (
    SELECT 'Category' AS dimension, category AS segment, COUNT(*) AS audited_units, SUM(is_defect) AS defects FROM b GROUP BY category
    UNION ALL
    SELECT 'Site', site_id, COUNT(*), SUM(is_defect) FROM b GROUP BY site_id
    UNION ALL
    SELECT 'Shift', shift, COUNT(*), SUM(is_defect) FROM b GROUP BY shift
    UNION ALL
    SELECT 'Tenure band', tenure_band, COUNT(*), SUM(is_defect) FROM b GROUP BY tenure_band
    UNION ALL
    SELECT 'Correct disposition', audited_disposition, COUNT(*), SUM(is_defect) FROM b GROUP BY audited_disposition
    UNION ALL
    SELECT 'Photo step done', CASE photo_step_done WHEN 1 THEN 'Yes' ELSE 'No' END, COUNT(*), SUM(is_defect) FROM b GROUP BY photo_step_done
    UNION ALL
    SELECT 'Month', month, COUNT(*), SUM(is_defect) FROM b GROUP BY month
),
net AS (
    SELECT 1.0 * SUM(is_defect) / COUNT(*) AS network_rate FROM b
)
SELECT s.dimension, s.segment, s.audited_units, s.defects,
       ROUND(1.0 * s.defects / s.audited_units, 4)                    AS defect_rate,
       ROUND((1.0 * s.defects / s.audited_units) / n.network_rate, 2) AS index_vs_network
FROM seg s CROSS JOIN net n
ORDER BY s.dimension, defect_rate DESC;
