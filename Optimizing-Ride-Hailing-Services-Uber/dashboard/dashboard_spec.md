# Dispatch Performance Dashboard: build spec (Tableau Public / QuickSight)

`screenshots/dashboard.png` is a matplotlib render of this layout from `src/make_dashboard.py`,
not a screenshot of a published Tableau workbook. To rebuild it in Tableau Public or QuickSight,
use the extracts below. The reasoning behind each view is in
`docs/Requirements_Dispatch_Performance_Dashboard.md`.

## Data sources

| File | Grain | Rows | Use |
|---|---|---|---|
| `tableau_extract.csv` | window x protocol | 5,000 | All KPI tiles and charts except the ETA distribution |
| `tableau_eta_distribution.csv` | protocol x ETA band | 25 | ETA distribution chart (pre-aggregated from rider-level matches) |

Key fields in `tableau_extract.csv`: `window_id`, `protocol`, `protocol_label`, `dispatch_method`
(Greedy / Batched), `radius_policy` (No radius / MDR enforced), `objective` (Min ETA / Max contribution),
`mdr_miles`, `supply_ratio_design`, `supply_ratio_actual`, `supply_segment`, `riders`, `drivers`,
`matched`, `unmatched_riders`, `total_enroute_min`, `p90_eta_min`, `max_eta_min`, `avg_enroute_miles`,
`profit_usd`.

## Calculated fields (Tableau syntax)

```
[Avg ETA (min)]          = SUM([total_enroute_min]) / SUM([matched])
[Match rate]             = SUM([matched]) / SUM([riders])
[Drivers matched %]      = SUM([matched]) / SUM([drivers])
[Avg p90 ETA (min)]      = AVG([p90_eta_min])
[Contribution / window]  = SUM([profit_usd]) / COUNTD([window_id])
[Unmatched riders]       = SUM([unmatched_riders])
[ETA vs baseline %]      = [Avg ETA (min)] /
                           { FIXED : SUM(IF [protocol]="greedy_first_dispatch" THEN [total_enroute_min] END)
                                   / SUM(IF [protocol]="greedy_first_dispatch" THEN [matched] END) } - 1
```

Keep the ratios rider-weighted (SUM / SUM). An AVG of per-window averages won't match `sql/01`.

## Sheets

| # | Sheet | Mark | Rows / Columns | Matches |
|---|---|---|---|---|
| 1 | KPI tiles | Text | Avg ETA, p90 ETA, Match rate, Contribution / window, 12+ min share | sql/01, sql/02, sql/03 |
| 2 | ETA by protocol | Bar (side-by-side) | protocol_label x [Avg ETA], [Avg p90 ETA] | sql/01 |
| 3 | ETA distribution | Stacked bar (100%) | protocol_label x pct_of_matched, color = eta_bucket | sql/03 |
| 4 | Match rate vs MDR | Line | mdr_miles x [Match rate], color = protocol_label (MDR protocols + batched_min_eta) | sql/04 |
| 5 | Batching gain by supply | Bar | supply_segment x [Avg ETA], color = dispatch_method, radius_policy = No radius | sql/05 |
| 6 | Gap list | Table | gap rules from sql/06 (export of `data/processed/sql_06_gap_list_batching_underperforms.csv`) | sql/06, sql/07 |

## Filters (apply to all sheets using `tableau_extract.csv`)

Protocol, Radius policy, MDR miles, Supply segment, Dispatch method. Production version adds Date and Zone.

## Layout

Title bar, filter row, five KPI tiles across the top, then a 2 x 2 grid: ETA by protocol (top left),
ETA distribution (top right), match rate vs MDR (bottom left), batching gain by supply (bottom right).
Gap list on a second dashboard tab.

## Refresh cadence

The simulation extract is rebuilt whenever you run `python src/run_all.py`. In production it would
refresh daily (incremental) by 07:00 local time from dispatch event logs (FR8 in the requirements doc).

## Colours

Grey for the greedy baselines, blue for batched min-ETA, orange for batched max-contribution. Green
means better than baseline and red means worse.
