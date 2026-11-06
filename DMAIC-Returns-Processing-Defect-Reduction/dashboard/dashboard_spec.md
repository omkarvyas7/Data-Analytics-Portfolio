# Dashboard Spec: Disposition Quality Control Dashboard

Written for Tableau Public or Desktop. The same fields and calcs carry over to Amazon QuickSight. Data comes from `dashboard/tableau_extract.csv` (daily aggregate) and `dashboard/tableau_defects_extract.csv` (one row per audited defect, with its cause code). The Tableau workbook isn't in the repo. `screenshots/dashboard.png` is a matplotlib mock-up of this layout. Requirements are in `docs/04_Requirements_Disposition_QC_Dashboard.md`. Data is synthetic.

## Data source

`tableau_extract.csv`, one row per operating day x site x shift x category.

| Field | Type | Description |
|---|---|---|
| op_date | Date | Operating day (night shift after midnight belongs to the previous day) |
| week_start | Date | Monday of the operating week |
| month | String (YYYY-MM) | Calendar month |
| phase | String | Baseline (to 2026-02-28), Pilot (2026-03-01 to 04-30), Control (from 2026-05-01) |
| site_id | String | RC-WEST, RC-CENTRAL, RC-EAST, RC-SOUTH |
| is_pilot_site | Integer 0/1 | 1 for RC-CENTRAL |
| shift | String | Day, Swing, Night |
| category | String | Product category |
| units | Integer | Units dispositioned |
| audited_units | Integer | Units in the QA audit sample |
| defects | Integer | Audited units with the wrong disposition |
| upgrade_defects | Integer | Defects graded too high (customer-facing) |
| units_by_new_associates | Integer | Units graded by associates with tenure < 30 days |
| potential_recovery_usd | Number | Value of the correct disposition |
| recovery_achieved_usd | Number | Value achieved |
| recovery_leakage_usd | Number | potential - achieved |
| waste_units | Integer | Resellable units sent to recycle / destroy |
| complaints | Integer | Customer complaints (condition not as described) |
| regrades | Integer | Units sent back to grading |
| cycle_hrs_sum, cycle_units | Number, Integer | Sum of dock-to-disposition hours and units with valid times (for weighted means) |
| sla_breaches | Integer | Units over the 48-hour SLA |

## Calculated fields

| Name | Formula (Tableau) |
|---|---|
| Defect Rate | `SUM([defects]) / SUM([audited_units])` |
| DPMO | `[Defect Rate] * 1000000` |
| p-bar (window) | `WINDOW_SUM(SUM([defects])) / WINDOW_SUM(SUM([audited_units]))` (compute using week_start, partitioned by Limit Set) |
| Limit Set | `IF [phase] = "Control" THEN "Control" ELSE "Baseline" END` |
| UCL | `[p-bar (window)] + 3 * SQRT([p-bar (window)] * (1 - [p-bar (window)]) / SUM([audited_units]))` |
| LCL | `MAX(0, [p-bar (window)] - 3 * SQRT([p-bar (window)] * (1 - [p-bar (window)]) / SUM([audited_units])))` |
| Out of Control | `IF [Defect Rate] > [UCL] OR [Defect Rate] < [LCL] THEN "Signal" ELSE "In control" END` |
| Recovery Rate | `SUM([recovery_achieved_usd]) / SUM([potential_recovery_usd])` |
| Waste per 10k | `SUM([waste_units]) / SUM([units]) * 10000` |
| Mean Cycle Hrs | `SUM([cycle_hrs_sum]) / SUM([cycle_units])` |
| SLA Breach Rate | `SUM([sla_breaches]) / SUM([cycle_units])` |
| Index vs Network | `[Defect Rate] / {FIXED : SUM([defects]) / SUM([audited_units])}` |
| Defect RAG | `IF [Defect Rate] <= [Target Defect Rate] THEN "Green" ELSEIF [Defect Rate] <= [Target Defect Rate] * 1.25 THEN "Amber" ELSE "Red" END` |

Parameter: `Target Defect Rate` (float, default 0.035).

## Sheets

| # | Sheet | Chart | Rows / columns | Notes |
|---|---|---|---|---|
| 1 | KPI tiles | Text tiles | Defect Rate, DPMO, Recovery Rate, Waste per 10k, Mean Cycle Hrs | Show the selected period and the baseline for comparison |
| 2 | Defect p-chart | Line + reference lines | week_start (continuous) x Defect Rate, UCL, LCL | Colour points by Out of Control; reference line = Target Defect Rate; phase bands |
| 3 | Pareto | Bar + line (dual axis) | Defect cause x count, running % | Source: `tableau_defects_extract.csv`; running % via `RUNNING_SUM(COUNT([audit_id])) / TOTAL(COUNT([audit_id]))`; blend on op_date + site_id |
| 4 | Site comparison | Grouped bar | site_id x Defect Rate, colour = phase | Sort by baseline rate |
| 5 | Shift / tenure heatmap | Highlight table | shift x category, colour = Index vs Network | Tooltip shows audited units |
| 6 | Recovery $ | Stacked bar | month x achieved and leakage | Label leakage $ |
| 7 | Pilot before / after | Grouped bar | is_pilot_site x phase x Defect Rate | Caption shows the z-test p-value from `data/processed/hypothesis_tests.csv` |
| 8 | Cycle time | Line | op_date x Mean Cycle Hrs | Reference line at 48 h SLA, I-MR limits from `data/processed/imr_chart_data.csv` |

## Dashboard layout

KPI tiles across the top. The p-chart takes two-thirds of the middle row, with the Pareto next to it. The bottom row has site comparison, recovery $ and pilot before/after. Filters sit on the right: date range, site, shift, category, phase. Clicking a site bar filters every sheet, and clicking a Pareto bar filters the p-chart to that cause.

## Refresh cadence

- Extract refresh daily at 05:00 local from the returns data mart (in this repo: `python src/run_all.py`).
- Weekly PDF subscription to site managers every Monday at 08:00.
- Only the process owner recalculates control limits, and only after a documented process change such as a new SOP version.
