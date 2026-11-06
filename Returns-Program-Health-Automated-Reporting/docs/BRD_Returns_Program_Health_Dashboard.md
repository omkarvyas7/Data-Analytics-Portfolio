# Business Requirements Document: Returns Program Health Dashboard and Automated WBR

| Field | Value |
|---|---|
| Document owner | Data Analyst, Returns & ReCommerce Analytics |
| Status | Approved for build (v1.0) |
| Business sponsor | Director, Returns Experience & ReCommerce |
| Last updated | 2026-11-01 |
| Related artifacts | `sql/`, `src/run_wbr.py`, `excel/Program_Tracker.xlsx`, `dashboard/dashboard_spec.md` |

## 1. Background

The Returns and ReCommerce program runs five cross-functional initiatives: grade-and-resell open-box electronics, returnless refunds for low-value items, drop-off point expansion, return reason capture redesign, and liquidation partner onboarding. Each initiative is owned by a different team and moves a different customer or cost KPI. Today the weekly business review (WBR) is assembled by hand from four spreadsheets, takes about a day of analyst time, and reports outcome KPIs separately from program status. Leaders cannot see in one place whether a KPI miss is linked to a late or blocked initiative.

## 2. Problem statement

Leaders need a single, automated weekly view that answers three questions: (1) are the returns outcome KPIs on target, (2) are the initiatives that should move them on schedule, and (3) which team owes what action before next week. For the week of 2026-10-26, the manual process would not have connected the refund-cycle miss (3.77 days vs 3.30 days) to the blocked drop-off Wave 2 milestone and an unmitigated carrier risk.

## 3. Goals and non-goals

**Goals**
- G1. Publish the WBR (Excel workbook + PDF pre-read) automatically every Monday by 08:00 local, with zero manual data steps.
- G2. Show every KPI vs target with WoW, YoY, trailing-4-week average and a documented RAG rule.
- G3. Roll up program health (schedule variance, milestones at risk, blocked dependencies, open High risks) per initiative.
- G4. Produce a gap list that routes each miss to an owning team with a specific ask and due date.
- G5. Provide a Tableau/QuickSight-ready extract so the same numbers drive the interactive dashboard.

**Non-goals**
- Real-time (intra-day) monitoring; the grain is weekly.
- Customer-level or order-level drill-down (privacy and scale; aggregates only).
- Changing initiative scope or targets; the dashboard reports against targets set by the business owners.
- Forecasting KPIs (a later phase).

## 4. Stakeholders (RACI)

| Stakeholder role | Interest | R | A | C | I |
|---|---|---|---|---|---|
| Director, Returns Experience & ReCommerce (sponsor) | Decisions and escalations at the WBR | | X | | |
| ReCommerce Program Manager | Program health, milestone data quality | X | | | |
| Data Analyst, Returns Analytics (document owner) | Requirements, SQL, pipeline, dashboard | X | | | |
| Returns Operations Manager | Processing and grading KPIs | | | X | X |
| Reverse Logistics Program Manager | Cycle time, drop-off network | | | X | X |
| Returns Experience Product Manager | Contacts per return, reason capture | | | X | X |
| Disposition Program Manager | Recovery rate, waste, liquidation | | | X | X |
| Returns Policy Manager / Risk & Abuse Prevention Manager | Returnless refunds, abuse, bad debt | | | X | X |
| Finance partner | $ recovery and cost definitions | | | X | X |
| Software Development Manager / Data Engineer | Source feeds, scheduling, access | | | X | X |
| Business Intelligence Engineer | Tableau/QuickSight build and refresh | X | | | |

## 5. User stories

1. As the program sponsor, I want a one-page headline written from the numbers so that I can see the week's top issues in two minutes before the WBR.
2. As a KPI owner, I want each KPI shown against its target with a RAG status and WoW/YoY deltas so that I know whether I need to present a recovery plan.
3. As the program manager, I want milestones with schedule variance and dependency blockers so that I can escalate cross-team blockers before they slip the launch.
4. As a partner team lead, I want a gap list filtered to my team with a due date so that I know exactly what I owe before next week.
5. As an analyst, I want a driver breakdown (marketplace x channel, rate vs mix, transit vs processing) so that I can explain a KPI miss without ad-hoc queries.
6. As a BI engineer, I want one tidy extract with additive measures so that I can rebuild every KPI in Tableau/QuickSight without custom SQL.

## 6. Functional requirements

| ID | Requirement | Acceptance criteria | Delivered by |
|---|---|---|---|
| FR-1 | The pipeline runs for any week with one command: `python src/run_wbr.py --week YYYY-MM-DD`. | Given a Monday within the data range, the command exits 0 and writes the xlsx, PDF and query CSVs; a non-Monday or out-of-range week exits non-zero with a clear message. | `src/run_wbr.py`, `src/run_sql.py` |
| FR-2 | KPI summary shows current, prior week, WoW (abs and %), same week last year, YoY, trailing-4-week average and target for all 8 KPIs. | Values match `sql/01_wbr_kpi_summary.sql` output to 4 decimals; YoY compares 52 weeks back (-364 days). | `sql/01`, WBR Summary tab |
| FR-3 | Each KPI gets a RAG status from a documented rule (Green at/better than target; Amber within the KPI's tolerance band; Red outside). | Excel RAG formula (column P) equals SQL RAG (column Q) for every KPI; status counts agree. | `sql/02`, WBR Summary tab |
| FR-4 | Persistence of a miss is shown (weeks missed in the last 4). | Column present in the scorecard; equals count of non-Green weeks in the trailing 4. | `sql/02` |
| FR-5 | Top movers by category for cycle time, contacts, cost, recovery and return rate, ranked by absolute WoW % change, with YoY. | Ranks 1..5 per KPI; favourable/unfavourable flag respects KPI direction. | `sql/04`, Top Movers tab |
| FR-6 | When refund cycle time is off target, the WBR includes a marketplace x channel driver decomposition into rate and mix effects, split into transit and processing. | Sum of segment effects equals the program change vs baseline (to 3 decimals). | `sql/05`, Refund Cycle Drivers tab |
| FR-7 | Program health per initiative: milestones complete/total, at risk, blocked by dependency, max and average schedule variance, open High risks, initiative RAG. | Rules in `sql/06` header; recomputed in `excel/Program_Tracker.xlsx` with COUNTIFS/MAXIFS and give the same counts. | `sql/06`, `sql/07`, tracker |
| FR-8 | Risk register shows open risks with severity = likelihood x impact and flags High risks with no mitigation or past target close. | Flag = 1 exactly for those rows; rows highlighted in Excel and PDF. | `sql/08` |
| FR-9 | Cross-team dependency blockers list the blocked milestone, the predecessor and its owning team. | Every milestone whose predecessor is not Complete and whose planned start has passed appears once. | `sql/09` |
| FR-10 | Gap list routes each KPI miss, blocker, slipping milestone and unmitigated High risk to a team with priority (P1/P2), ask and due date. | Each gap has team, owner role, ask and due date = next WBR as-of date. | `sql/10`, Gap List tab |
| FR-11 | The PDF pre-read is 2-3 pages: headline narrative, KPI scorecard, program health, trend and driver charts, asks/escalations. | Page count between 2 and 3; every narrative number traceable to a query CSV. | `src/wbr_pdf.py`, `src/narrative.py` |
| FR-12 | Excel workbook is formula-driven: changing the report week or a target on the Inputs tab recalculates the summary. | Summary cells contain INDEX/MATCH and AVERAGEIFS formulas, not pasted values; RAG uses conditional formatting. | `src/wbr_excel.py` |
| FR-13 | A tidy BI extract with additive measures is produced every run. | `dashboard/tableau_extract.csv` rebuilds program KPIs to within rounding of `v_weekly_kpi`. | `sql/11`, `src/make_dashboard.py` |

## 7. Non-functional requirements

| ID | Requirement | Acceptance criteria |
|---|---|---|
| NFR-1 Refresh SLA | Source data lands by Sunday 23:59; WBR artifacts published by Monday 08:00 local. | Scheduled task at 06:00; run time under 5 minutes (current run is a few seconds). |
| NFR-2 Reliability | A failed run alerts the owner and never publishes partial output silently. | Non-zero exit code on failure; scheduler sends failure notice; previous week's file stays in place. |
| NFR-3 Data quality | Duplicates, key casing, sign errors and missing scans are handled by rule and logged. | `data/processed/data_quality_log.csv` written each run; zero duplicate keys at daily grain after cleaning. |
| NFR-4 Reproducibility | Any past week can be regenerated from raw data. | `run_wbr.py --week <past Monday>` reproduces that week's numbers. |
| NFR-5 Access | Aggregated, non-customer data only. Dashboard viewers: program team and partner teams; edit rights on targets restricted to KPI owners. | No customer identifiers in any extract; target changes go through the KPI owner. |
| NFR-6 Portability | SQL is ANSI-style (CTEs, window functions, CASE) and ports to Redshift/Postgres with date-function swaps only. | Dialect notes in each SQL header and the README. |
| NFR-7 Readability | A non-technical leader can read the headline without the tables. | Headline sentences use plain units (days, %, $) and name the owning team. |

## 8. Metric dictionary

| Metric | Formula | Grain | Source | Better | Target | Owner team |
|---|---|---|---|---|---|---|
| Return rate (`return_rate`) | SUM(return_units) / SUM(units_shipped) | week (Mon-Sun) x marketplace x category x channel | returns_daily, shipments_daily | lower | 9.5% (amber band 5%) | Returns Policy |
| Refund cycle time (`refund_cycle_days`) | SUM(transit_hours + processing_hours) / 24 / SUM(cycle_units); rows with missing scans excluded from numerator and denominator | week (Mon-Sun) x marketplace x category x channel | returns_daily | lower | 3.30 days (amber band 5%) | Reverse Logistics Ops |
| Customer contacts per return (`contacts_per_return`) | SUM(customer_contacts) / SUM(return_units) | week (Mon-Sun) x marketplace x category x channel | returns_daily | lower | 0.180 (amber band 5%) | Returns Experience Tech |
| Resold share of dispositions (`resale_pct`) | SUM(resold_units) / SUM(resold + liquidated + recycled + waste units) | week (Mon-Sun) x marketplace x category x channel | returns_daily | higher | 50.0% (amber band 3%) | ReCommerce |
| Liquidated share of dispositions (`liquidation_pct`) | SUM(liquidated_units) / SUM(disposition units) | week (Mon-Sun) x marketplace x category x channel | returns_daily | lower | 36.0% (amber band 5%) | Liquidation & Disposition |
| Recovery rate ($ recovered / $ refunded) (`recovery_rate`) | SUM(recovered_usd) / SUM(refund_usd) | week (Mon-Sun) x marketplace x category x channel | returns_daily | higher | 36.0% (amber band 3%) | Liquidation & Disposition |
| Waste (landfill) units (`waste_units`) | SUM(waste_units) (landfill) | week (Mon-Sun) x marketplace x category x channel | returns_daily | lower | 11,000 (amber band 5%) | Liquidation & Disposition |
| Cost per return (`cost_per_return`) | SUM(processing_cost_usd) / SUM(return_units) | week (Mon-Sun) x marketplace x category x channel | returns_daily | lower | $6.80 (amber band 5%) | Reverse Logistics Ops |
| Schedule variance (days) | actual_end - planned_end; else forecast_end - planned_end; else as_of - planned_end if overdue | milestone | milestones | lower | 0 (Amber > 7, Red > 21) | milestone owner |
| Blocked by dependency | predecessor not Complete AND milestone not Complete AND planned_start <= as_of | milestone | milestones | lower | 0 | predecessor owner |
| Risk severity | likelihood (1-5) x impact (1-5); High >= 15 | risk | risks | lower | no unmitigated High risks | risk owner |

## 9. Data sources and requirements

| Source | Grain | Key fields | Refresh | Owner |
|---|---|---|---|---|
| `returns_daily` | day x marketplace x category x return channel | return_units, refund_usd, transit_hours, processing_hours, customer_contacts, disposition units, recovered_usd, processing_cost_usd | daily, by 23:59 | Data Engineer |
| `shipments_daily` | day x marketplace x category | units_shipped | daily | Data Engineer |
| `kpi_targets` | KPI | target, direction, amber_band, owner_team, initiative_id | on change (owner sign-off) | KPI owners |
| `initiatives`, `milestones` | initiative / milestone | planned, actual and forecast dates, status, % complete, depends_on | weekly, by Friday 17:00 | Program managers |
| `risks`, `issues` | risk / issue | likelihood, impact, mitigation, owner, dates | weekly | Initiative owners |

Data cleaning rules applied this run: 45 duplicate rows removed, 60 marketplace codes normalised, 45 channel labels mapped, 15 negative-unit rows excluded, 40 rows with missing scans excluded from the cycle-time calculation only. 43,665 clean daily rows loaded.

## 10. Assumptions

- Weeks run Monday to Sunday; YoY compares the same week 52 weeks earlier.
- Trailing-4-week average is the mean of the four weekly values (a ratio-of-sums version is available in the extract).
- Milestone status and forecasts are updated by owners before the Friday cut-off; the pipeline does not infer status.
- Customer contact handling cost is a planning assumption ($4.50 per contact) until finance provides a rate.

## 11. Risks

| Risk | Impact | Mitigation |
|---|---|---|
| Milestone data entered late or inconsistently | Program RAG is stale | Friday cut-off, late-update flag, program manager owns tracker hygiene |
| Target changes without sign-off | RAG loses credibility | Targets table owned by KPI owners; change log in the tracker |
| Upstream feed delay on Sunday | WBR misses the 08:00 SLA | Retry at 07:00; alert the Data Engineer on failure |
| Metric definition drift between Excel, PDF and BI | Conflicting numbers in the room | One SQL layer feeds all three outputs; Excel shows Excel vs SQL RAG side by side |

## 12. Open questions

1. Should the amber tolerance band be uniform (5%) or set per KPI by the owner? (Current build: per KPI, 3-5%.)
2. Does finance want recovery rate on refund value or on original sale price?
3. Which partner teams need row-level security in the BI tool versus a shared view?

## 13. Timeline and milestones

| Milestone | Target date | Exit criteria |
|---|---|---|
| Requirements sign-off | 2026-09-25 | This BRD approved by sponsor and KPI owners |
| SQL layer and data-quality rules | 2026-10-09 | `sql/00-11` reviewed; DQ log in place |
| Excel + PDF WBR automated | 2026-10-23 | FR-1 to FR-12 pass for 3 back-tested weeks |
| BI dashboard live (Tableau/QuickSight) | 2026-11-06 | FR-13; extract refresh scheduled |
| First automated WBR | 2026-11-02 | Run for week 2026-10-26; artifacts in `excel/` and `reports/` |
| Retire manual WBR | 2026-11-30 | Four consecutive on-time automated WBRs |

## Appendix: example output (week of 2026-10-26)

| KPI | Actual | Target | Variance (unfav +) | YoY | RAG |
|---|---|---|---|---|---|
| Return rate | 9.5% | 9.5% | +0.2% | +0.9% | Amber |
| Refund cycle time | 3.77 days | 3.30 days | +14.2% | +8.1% | Red |
| Customer contacts per return | 0.192 | 0.180 | +6.8% | +5.1% | Red |
| Resold share of dispositions | 49.6% | 50.0% | +0.9% | +4.4% | Amber |
| Liquidated share of dispositions | 35.5% | 36.0% | -1.3% | +2.1% | Green |
| Recovery rate ($ recovered / $ refunded) | 38.6% | 36.0% | -7.1% | +11.8% | Green |
| Waste (landfill) units | 10,829 | 11,000 | -1.6% | -29.2% | Green |
| Cost per return | $7.05 | $6.80 | +3.7% | -3.1% | Amber |
