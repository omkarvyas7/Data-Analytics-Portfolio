/* 00_create_views.sql
Reporting layer for the WBR. Puts every returns KPI on one weekly grain.

Builds two tables and two views:
  weekly_fact        week x marketplace x category x channel, additive measures
  weekly_ship        week x marketplace x category, units shipped
  v_weekly_kpi       one row per week, all KPIs at program level
  v_weekly_kpi_long  week x kpi x value, joins to kpi_targets

Weeks run Monday to Sunday and week_start is the Monday. Ratios are always summed
numerator over summed denominator, never an average of rates.
SQLite: date(x,'weekday 0','-6 days') is DATE_TRUNC('week', x) in Redshift/Postgres.
*/

DROP TABLE IF EXISTS weekly_fact;
CREATE TABLE weekly_fact AS
SELECT
    date(date, 'weekday 0', '-6 days')      AS week_start,
    marketplace,
    category,
    channel,
    SUM(return_units)                        AS return_units,
    SUM(refund_usd)                          AS refund_usd,
    SUM(transit_hours)                       AS transit_hours,
    SUM(processing_hours)                    AS processing_hours,
    SUM(refund_cycle_hours)                  AS refund_cycle_hours,
    SUM(cycle_units)                         AS cycle_units,
    SUM(customer_contacts)                   AS customer_contacts,
    SUM(resold_units)                        AS resold_units,
    SUM(liquidated_units)                    AS liquidated_units,
    SUM(recycled_units)                      AS recycled_units,
    SUM(waste_units)                         AS waste_units,
    SUM(recovered_usd)                       AS recovered_usd,
    SUM(processing_cost_usd)                 AS processing_cost_usd
FROM returns_daily
GROUP BY 1, 2, 3, 4;

CREATE INDEX ix_wf_week ON weekly_fact(week_start);

DROP TABLE IF EXISTS weekly_ship;
CREATE TABLE weekly_ship AS
SELECT
    date(date, 'weekday 0', '-6 days') AS week_start,
    marketplace,
    category,
    SUM(units_shipped)                 AS units_shipped
FROM shipments_daily
GROUP BY 1, 2, 3;

DROP VIEW IF EXISTS v_weekly_kpi;
CREATE VIEW v_weekly_kpi AS
WITH r AS (
    SELECT week_start,
           SUM(return_units) AS return_units,
           SUM(refund_usd) AS refund_usd,
           SUM(refund_cycle_hours) AS refund_cycle_hours,
           SUM(cycle_units) AS cycle_units,
           SUM(customer_contacts) AS customer_contacts,
           SUM(resold_units) AS resold_units,
           SUM(liquidated_units) AS liquidated_units,
           SUM(recycled_units) AS recycled_units,
           SUM(waste_units) AS waste_units,
           SUM(recovered_usd) AS recovered_usd,
           SUM(processing_cost_usd) AS processing_cost_usd
    FROM weekly_fact
    GROUP BY week_start
),
s AS (
    SELECT week_start, SUM(units_shipped) AS units_shipped
    FROM weekly_ship
    GROUP BY week_start
)
SELECT
    r.week_start,
    s.units_shipped,
    r.return_units,
    r.refund_usd,
    r.recovered_usd,
    1.0 * r.return_units / s.units_shipped                                         AS return_rate,
    r.refund_cycle_hours / 24.0 / NULLIF(r.cycle_units, 0)                         AS refund_cycle_days,
    1.0 * r.customer_contacts / NULLIF(r.return_units, 0)                          AS contacts_per_return,
    1.0 * r.resold_units / NULLIF(r.resold_units + r.liquidated_units + r.recycled_units + r.waste_units, 0)     AS resale_pct,
    1.0 * r.liquidated_units / NULLIF(r.resold_units + r.liquidated_units + r.recycled_units + r.waste_units, 0) AS liquidation_pct,
    1.0 * r.recycled_units / NULLIF(r.resold_units + r.liquidated_units + r.recycled_units + r.waste_units, 0)   AS recycled_pct,
    r.recovered_usd / NULLIF(r.refund_usd, 0)                                      AS recovery_rate,
    r.waste_units                                                                  AS waste_units,
    r.processing_cost_usd / NULLIF(r.return_units, 0)                              AS cost_per_return
FROM r
JOIN s ON s.week_start = r.week_start;

DROP VIEW IF EXISTS v_weekly_kpi_long;
CREATE VIEW v_weekly_kpi_long AS
SELECT week_start, 'return_rate' AS kpi, return_rate AS value FROM v_weekly_kpi
UNION ALL SELECT week_start, 'refund_cycle_days', refund_cycle_days FROM v_weekly_kpi
UNION ALL SELECT week_start, 'contacts_per_return', contacts_per_return FROM v_weekly_kpi
UNION ALL SELECT week_start, 'resale_pct', resale_pct FROM v_weekly_kpi
UNION ALL SELECT week_start, 'liquidation_pct', liquidation_pct FROM v_weekly_kpi
UNION ALL SELECT week_start, 'recovery_rate', recovery_rate FROM v_weekly_kpi
UNION ALL SELECT week_start, 'waste_units', waste_units FROM v_weekly_kpi
UNION ALL SELECT week_start, 'cost_per_return', cost_per_return FROM v_weekly_kpi;
