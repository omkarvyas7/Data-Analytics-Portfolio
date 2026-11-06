-- 06_recovery_value_leakage.sql
-- Recovery $ achieved vs potential by phase, site and category (Measure and Control).
-- Question: how much recovery value do misgrades leave on the table, and where?
-- Potential is the value of the correct disposition from the pricing model.
-- leakage = potential - achieved, recovery rate = achieved / potential.
SELECT phase, site_id, category,
       COUNT(*)                                                         AS units,
       ROUND(SUM(potential_recovery_usd), 2)                            AS potential_usd,
       ROUND(SUM(recovery_achieved_usd), 2)                             AS achieved_usd,
       ROUND(SUM(recovery_leakage_usd), 2)                              AS leakage_usd,
       ROUND(SUM(recovery_achieved_usd) / NULLIF(SUM(potential_recovery_usd), 0), 4) AS recovery_rate,
       ROUND(1000.0 * SUM(recovery_leakage_usd) / COUNT(*), 2)          AS leakage_usd_per_1k_units
FROM v_units
GROUP BY phase, site_id, category
ORDER BY CASE phase WHEN 'Baseline' THEN 1 WHEN 'Pilot' THEN 2 ELSE 3 END, leakage_usd DESC;
