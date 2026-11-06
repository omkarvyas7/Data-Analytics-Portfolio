-- 07_waste_units.sql
-- Waste: resellable units sent to recycle or destroy, by month and site (zero-waste goal).
-- Returns units processed, waste units, waste per 10k units and the recovery value lost on them.
SELECT month, site_id,
       COUNT(*)                                                           AS units,
       SUM(waste_flag)                                                    AS waste_units,
       ROUND(10000.0 * SUM(waste_flag) / COUNT(*), 1)                     AS waste_per_10k_units,
       ROUND(SUM(CASE WHEN waste_flag = 1 THEN recovery_leakage_usd ELSE 0 END), 2) AS waste_value_lost_usd
FROM v_units
GROUP BY month, site_id
ORDER BY month, site_id;
