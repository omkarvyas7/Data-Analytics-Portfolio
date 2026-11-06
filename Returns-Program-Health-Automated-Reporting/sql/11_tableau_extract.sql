/* 11_tableau_extract.sql
One tidy file for Tableau / QuickSight that can rebuild every WBR KPI at any grain.

No params (full history). Two row types:
  'returns'    week x marketplace x category x channel, additive return measures
  'shipments'  week x marketplace x category, channel = 'All channels', units_shipped only
Every measure is additive, so each KPI is SUM(numerator) / SUM(denominator) in the BI tool
(calculated fields are in dashboard/dashboard_spec.md). Written to dashboard/tableau_extract.csv.
*/
SELECT
    'returns'               AS row_type,
    f.week_start,
    f.marketplace,
    f.category,
    f.channel,
    NULL                    AS units_shipped,
    f.return_units,
    ROUND(f.refund_usd, 2)  AS refund_usd,
    ROUND(f.refund_cycle_hours, 1) AS refund_cycle_hours,
    ROUND(f.transit_hours, 1)      AS transit_hours,
    ROUND(f.processing_hours, 1)   AS processing_hours,
    f.cycle_units,
    f.customer_contacts,
    f.resold_units,
    f.liquidated_units,
    f.recycled_units,
    f.waste_units,
    ROUND(f.recovered_usd, 2)       AS recovered_usd,
    ROUND(f.processing_cost_usd, 2) AS processing_cost_usd
FROM weekly_fact f
UNION ALL
SELECT
    'shipments', s.week_start, s.marketplace, s.category, 'All channels', s.units_shipped,
    NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL
FROM weekly_ship s
ORDER BY 2, 1, 3, 4, 5;
