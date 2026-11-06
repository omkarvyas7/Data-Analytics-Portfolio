-- 02_baseline_defect_rate_dpmo_sigma.sql
-- Defect rate, DPMO, first-pass yield and sigma level by phase and site, plus a NETWORK row per phase (Measure).
-- Defect: assigned disposition <> the QA auditor's disposition. One opportunity per unit.
-- DPMO = defects / audited units * 1,000,000. Sigma comes from sigma_lookup (1.5-sigma shift).
-- First-pass yield: audited units that were right and not sent back for re-grade, over audited units.
WITH agg AS (
    SELECT phase, site_id,
           COUNT(*)                                                     AS audited_units,
           SUM(is_defect)                                               AS defects,
           SUM(CASE WHEN is_defect = 0 AND regrade_flag = 0 THEN 1 ELSE 0 END) AS first_pass_good
    FROM v_audited
    GROUP BY phase, site_id
    UNION ALL
    SELECT phase, 'NETWORK',
           COUNT(*), SUM(is_defect),
           SUM(CASE WHEN is_defect = 0 AND regrade_flag = 0 THEN 1 ELSE 0 END)
    FROM v_audited
    GROUP BY phase
),
metrics AS (
    SELECT phase, site_id, audited_units, defects,
           ROUND(1.0 * defects / audited_units, 4)               AS defect_rate,
           ROUND(1000000.0 * defects / audited_units, 0)         AS dpmo,
           ROUND(1.0 * first_pass_good / audited_units, 4)       AS first_pass_yield
    FROM agg
)
SELECT m.*,
       (SELECT MAX(sl.sigma_level) FROM sigma_lookup sl WHERE sl.dpmo >= m.dpmo) AS sigma_level
FROM metrics m
ORDER BY CASE m.phase WHEN 'Baseline' THEN 1 WHEN 'Pilot' THEN 2 ELSE 3 END,
         CASE WHEN m.site_id = 'NETWORK' THEN 0 ELSE 1 END, m.site_id;
