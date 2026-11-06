# Dashboard spec: Disney genre performance

One page for the green-light committee. It answers "Is Action a safer bet?" and lets people filter by
genre, budget band and franchise. It's meant to be rebuilt in Tableau Public (or QuickSight) from
`dashboard/tableau_extract.csv`. The image in `screenshots/dashboard.png` is a matplotlib render of
this layout, not a Tableau screenshot.

## Data source
| Item | Value |
|---|---|
| File | `dashboard/tableau_extract.csv` (one row per film, 148 rows) |
| Produced by | `src/make_dashboard.py` (called from `src/run_all.py`) |
| Grain | film |
| Money fields | domestic gross and production budget, inflation-adjusted with Disney's own factor |
| Refresh | on demand when the source CSVs change. In production this would be weekly, after box-office data loads |

Main columns: `title`, `release_year`, `decade`, `disney_genre`, `imdb_genre`, `segment`
(Marvel / Action (non-Marvel) / Other genres), `budget_band` (Low/Mid/High terciles), `star_bucket`,
`imdb_score`, `inflation_budget`, `inflation_adjusted_gross`, `roi_multiple`, `predicted_adj_gross`
(model M2), `gross_vs_expected`.

## KPIs (top banner)
| KPI | Definition |
|---|---|
| Films analysed | `COUNTD([title])` |
| Avg gross, Action | `AVG(IF [is_action]=1 THEN [inflation_adjusted_gross] END)` |
| Avg gross, other | `AVG(IF [is_action]=0 THEN [inflation_adjusted_gross] END)` |
| Action premium after controls | parameter from `data/processed/model_results.json` (`m2_action_pct`, `m2_p.is_action`) |
| Budget elasticity | parameter (`m2_budget_elasticity`) |
| Model R-squared | parameter (`m2_r2`) |

## Calculated fields
- `Pooled ROI` = `SUM([inflation_adjusted_gross]) / SUM([inflation_budget])`
- `Hit flag` = `IF [roi_multiple] >= 1 THEN "Recouped budget" ELSE "Below budget" END`
- `Over/under model` = `IF [gross_vs_expected] > 0 THEN "Beat expectation" ELSE "Below expectation" END`
- `Gross $M` = `[inflation_adjusted_gross] / 1e6`

## Sheets
1. Average gross by genre: horizontal bars of average gross with the median as a dot. Action is highlighted.
2. Budget vs gross: log-log scatter coloured by `segment`, with a trend line. Tooltip shows title, ROI and IMDb score.
3. Action premium by model: dot-and-interval chart, values from `data/processed/model_coefficients.csv`.
4. Return per budget dollar: `Pooled ROI` by genre with a reference line at 1.0.
5. Drill-down: film table sorted by `gross_vs_expected`, for post-mortems.

## Filters (all sheets)
Decade, Disney genre, Segment, Budget band, Star bucket, MPAA rating.

## Notes
- The raw averages sit next to the controlled estimate on purpose, so it's clear why they disagree
  (Action films get bigger budgets).
- Gross is domestic box office only. Budgets exclude marketing.
