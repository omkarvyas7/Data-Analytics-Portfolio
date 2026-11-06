-- 08_pilot_pre_post.sql
-- Pilot site (RC-CENTRAL, SOP v3.0 + checklist + photo step from 2026-03-01) vs the other three sites, by phase (Improve).
-- Question: did the pilot site improve more than the comparison sites over the same weeks?
-- Returns audited units, defects, defect rate, leakage per unit, waste per 10k, mean cycle hours and complaint rate.
WITH a AS (
    SELECT CASE WHEN is_pilot_site = 1 THEN 'Pilot site (RC-CENTRAL)' ELSE 'Comparison sites' END AS site_group,
           phase, COUNT(*) AS audited_units, SUM(is_defect) AS defects,
           SUM(CASE WHEN defect_direction LIKE 'Upgrade%' THEN 1 ELSE 0 END) AS upgrade_defects
    FROM v_audited
    GROUP BY 1, 2
),
u AS (
    SELECT CASE WHEN is_pilot_site = 1 THEN 'Pilot site (RC-CENTRAL)' ELSE 'Comparison sites' END AS site_group,
           phase, COUNT(*) AS units,
           AVG(recovery_leakage_usd) AS leakage_per_unit,
           10000.0 * AVG(waste_flag) AS waste_per_10k,
           AVG(dock_to_disposition_hrs) AS mean_cycle_hrs,
           AVG(customer_complaint_flag) AS complaint_rate
    FROM v_units
    GROUP BY 1, 2
)
SELECT a.site_group, a.phase, u.units, a.audited_units, a.defects, a.upgrade_defects,
       ROUND(1.0 * a.defects / a.audited_units, 4) AS defect_rate,
       ROUND(u.leakage_per_unit, 3)                AS leakage_usd_per_unit,
       ROUND(u.waste_per_10k, 1)                   AS waste_per_10k_units,
       ROUND(u.mean_cycle_hrs, 2)                  AS mean_cycle_hrs,
       ROUND(u.complaint_rate, 4)                  AS complaint_rate
FROM a JOIN u ON u.site_group = a.site_group AND u.phase = a.phase
ORDER BY a.site_group DESC, CASE a.phase WHEN 'Baseline' THEN 1 WHEN 'Pilot' THEN 2 ELSE 3 END;
