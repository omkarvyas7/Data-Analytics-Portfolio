# Requirements: Dispatch Performance Dashboard

Version 1.0 | Status: Draft for review | Data: simulated (1,000 windows), see README

## 1. Background

Operations is considering a move from greedy first-dispatch to batched dispatch with a maximum dispatch radius (MDR). The simulation in this repository shows a 23.7% cut in average rider ETA, and a 3.98 pp gain in match rate when a radius is enforced. To run a pilot, operations needs a single view that compares protocols on the same KPI definitions and shows regressions early.

## 2. Problem statement

Without a shared dashboard, dispatch KPIs end up in ad hoc queries with different definitions (average ETA per window in one place, per rider in another). Without a gap classification, a pilot can also be stopped on a false alarm. In the simulation 506 windows look worse on some KPI, but 0 are true ETA regressions.

## 3. Goals and non-goals

Goals
- G1. One dashboard comparing dispatch protocols on rider ETA, match rate, share of drivers matched and contribution.
- G2. Sensitivity views by max dispatch radius and driver supply ratio.
- G3. A classified gap list so reviewers can separate expected trade-offs from true regressions.
- G4. Daily automated refresh with no manual steps.

Non-goals
- Changing the dispatch algorithm itself (owned by Dispatch engineering).
- Real-time (sub-minute) monitoring or alerting on individual trips.
- Driver pay or pricing analysis.

## 4. Stakeholders (RACI)

| Role | Responsibility | RACI |
|---|---|---|
| Rider Operations Manager | Pilot owner, go/no-go decision | A |
| Business / Data Analyst | Metric definitions, SQL, dashboard build | R |
| Marketplace Program Manager | Timeline, cross-team alignment | R |
| Software Development Engineer, Dispatch | Event logging, data pipeline | C |
| Finance partner | Contribution definition and sign-off | C |
| Regional operations leads | Daily dashboard users | I |

## 5. Functional requirements

| ID | Requirement | Acceptance criteria |
|---|---|---|
| FR1 | Show KPI tiles: avg ETA, p90 ETA, match rate, unmatched riders, share of drivers matched, contribution per window | Tile values equal sql/01 output for the same filters, to 2 decimals |
| FR2 | Filter by protocol, radius policy, MDR, supply segment and date | Every chart responds to every filter; default view is the last 7 days |
| FR3 | Protocol comparison chart for avg and p90 ETA | Bars match sql/01; baseline protocol is visually distinct |
| FR4 | ETA distribution in bands <3, 3-5, 5-8, 8-12, 12+ minutes | Band shares per protocol sum to 100% and match sql/03 |
| FR5 | Match rate vs MDR line chart | One line per protocol; values match sql/04 |
| FR6 | Batching gain by supply segment | Segments and % reduction match sql/05 |
| FR7 | Gap list with gap type for each flagged window or zone-day | Counts by gap type match sql/06 and sql/07 |
| FR8 | Daily refresh by 07:00 local time | Refresh log shows success for 5 consecutive days in UAT |
| FR9 | Data dictionary tab with each metric's formula and owner | Every tile and chart metric appears in the dictionary |

## 6. Metric definitions

| Metric | Formula | Grain | Source | Owner |
|---|---|---|---|---|
| Avg ETA (min) | SUM(total_enroute_min) / SUM(matched) | protocol x filter | simulation_results | Analyst |
| p90 ETA (min) | AVG of window-level 90th percentile ETA | protocol x filter | simulation_results | Analyst |
| Match rate | SUM(matched) / SUM(riders) | protocol x filter | simulation_results | Rider Ops |
| Unmatched riders | SUM(riders - matched) | protocol x filter | simulation_results | Rider Ops |
| Share of drivers matched (driver_utilization) | SUM(matched) / SUM(drivers) | protocol x filter | simulation_results | Rider Ops |
| Contribution per window ($) | AVG(profit_usd) | protocol x filter | simulation_results | Finance |
| 12+ min share | riders with ETA >= 12 / matched riders | protocol | simulation_matches | Analyst |
| Gap type | CASE rules in sql/06 | window | simulation_results | Analyst |

## 7. Data requirements

- Window-level table: window_id, zone, timestamp, protocol, riders, drivers, matched, MDR, ETA aggregates, contribution. In this repository: dashboard/tableau_extract.csv (5,000 rows).
- Rider-level match table for ETA distribution: dashboard/tableau_eta_distribution.csv (pre-aggregated) or simulation_matches.
- Production equivalent: dispatch event logs with request, assignment and pickup timestamps; latency up to 24 hours is acceptable.

## 8. Assumptions

- Protocol labels are logged on every dispatch decision during the pilot.
- ETA is measured as assignment-to-pickup time, not the quoted ETA.
- Contribution uses the Finance-approved fare and cost model.

## 9. Risks

- Definition drift between teams. Mitigation: FR9 data dictionary and Finance sign-off.
- Small zones produce noisy daily KPIs. Mitigation: show window counts and use 7-day rolling views.
- Higher average ETA after launch may reflect more riders served. Mitigation: FR7 gap classification.

## 10. Open questions

- What p90 ETA target counts as success for go/no-go?
- Is the 3-mile radius uniform, or set by zone density?
- Which BI tool hosts the production version (Tableau or QuickSight)?

## 11. Timeline and milestones

| Milestone | Target |
|---|---|
| Requirements sign-off | Week 1 |
| Metric definitions approved by Finance | Week 2 |
| Dashboard v1 on simulated extract | Week 3 |
| UAT with operations leads | Week 4 |
| Pilot launch with daily refresh | Week 5 |
| Go/no-go review | Week 7 |
