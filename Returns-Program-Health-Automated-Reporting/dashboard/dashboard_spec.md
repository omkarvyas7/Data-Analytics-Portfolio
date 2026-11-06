# Dashboard Spec: Returns Program Health (Tableau / QuickSight)

I drew the preview in `screenshots/dashboard.png` with matplotlib from the files in this folder, using the layout below. Anyone rebuilding it in Tableau Public/Desktop or QuickSight should land on the same numbers.

## Data sources

| File | Grain | Use |
|---|---|---|
| `tableau_extract.csv` | `row_type='returns'`: week x marketplace x category x channel (additive return measures). `row_type='shipments'`: week x marketplace x category, `channel='All channels'`, units_shipped only | All KPI tiles and trends; every KPI is SUM(numerator)/SUM(denominator), so it is correct at any filter level |
| `kpi_weekly_long.csv` | week x KPI (program total) with target, T4W rolling average, last-year value | KPI trend sheet with target reference line |
| `program_health.csv` | initiative | Program health RAG table |
| `milestones.csv` | milestone | Milestone timeline (Gantt) |

No joins needed. `tableau_extract.csv` is the main source; the other three are separate sources, related on `week_start` only where a sheet needs it.

## Calculated fields (Tableau syntax; QuickSight equivalents in brackets)

```
Return Rate          = SUM([return_units]) / SUM([units_shipped])
                       // only valid with Channel = All; return rate has no meaning by return channel
Refund Cycle Days    = SUM([refund_cycle_hours]) / 24 / SUM([cycle_units])
Transit Days         = SUM([transit_hours]) / 24 / SUM([cycle_units])
Processing Days      = SUM([processing_hours]) / 24 / SUM([cycle_units])
Contacts per Return  = SUM([customer_contacts]) / SUM([return_units])
Disposition Units    = SUM([resold_units]) + SUM([liquidated_units]) + SUM([recycled_units]) + SUM([waste_units])
Resale %             = SUM([resold_units]) / [Disposition Units]
Liquidation %        = SUM([liquidated_units]) / [Disposition Units]
Recovery Rate        = SUM([recovered_usd]) / SUM([refund_usd])
Cost per Return      = SUM([processing_cost_usd]) / SUM([return_units])
WoW Change           = ZN([KPI]) - LOOKUP(ZN([KPI]), -1)                      [periodOverPeriodDifference]
YoY Change %         = ([KPI] - LOOKUP([KPI], -52)) / ABS(LOOKUP([KPI], -52))  [periodOverPeriodPercentDifference, period = 52 weeks]
T4W Avg              = WINDOW_AVG([KPI], -3, 0)                               [windowAvg(..., 3, 0)]
RAG (lower better)   = IF [KPI] <= [Target] THEN "Green"
                       ELSEIF [KPI] <= [Target] * (1 + [Amber Band]) THEN "Amber" ELSE "Red" END
                       // higher-better KPIs flip it (>= target, >= target * (1 - band))
```

`[Target]` and `[Amber Band]` are parameters, with defaults from `data/raw/kpi_targets.csv`, so leaders can run what-ifs on targets.

## Sheets and layout (1600 x 1050)

1. **KPI tiles (top row, 8 tiles).** Current-week value, target, WoW change, and a border colored by RAG. Click a tile to filter the trend sheet to that KPI.
2. **Trend lines (middle row, 4 charts).** Refund cycle days, contacts per return, recovery rate, cost per return: weekly value, T4W average (dotted), last year (grey), target reference line (dashed), 52 weeks.
3. **Program health RAG table (bottom left).** Initiative, team, milestones done/total, at risk, blocked, max slip, open High risks, RAG (colored cell).
4. **Milestone timeline (bottom right).** Gantt bars: planned window outline, actual/forecast bar colored by status, reference line at the as-of date.
5. **Drill-through sheet (tooltip / second dashboard).** Refund cycle by marketplace x channel, split into transit vs processing, matching `sql/05`.

## Filters

Week (single value, defaults to the latest complete week), Marketplace, Category, Channel (return-rate tile shows "n/a by channel" when Channel is filtered), Initiative (program sheets).

## Refresh cadence

| Tool | Setup |
|---|---|
| Pipeline | `src/run_wbr.py` runs Monday 06:00 (Task Scheduler / cron, see `docs/schedule_refresh.md`) and rewrites the CSVs in this folder |
| Tableau Server / Cloud | Publish the extract as a data source; schedule an **extract refresh** for Monday 07:00 (after the pipeline). Tableau Bridge is needed if the files live on a private file share. Subscribe WBR attendees to a Monday 08:00 email snapshot |
| QuickSight | Put the CSVs in S3 (or load into Redshift via the same SQL), create a SPICE dataset, and set a **scheduled refresh** (weekly, Monday 07:00). Use an email report on the dashboard for the 08:00 pre-read. Row-level security on `team` if partner teams should see only their gaps |
| Tableau Public | Re-upload the extract manually; Public does not support scheduled refresh for file sources |

## Access

Aggregated data only, no customer identifiers. Viewer: program and partner teams. Editor: Data Analyst and BI Engineer. Target parameters are changed only by KPI owners.
