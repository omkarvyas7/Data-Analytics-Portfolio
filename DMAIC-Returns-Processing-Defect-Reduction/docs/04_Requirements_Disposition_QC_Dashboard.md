# Business Requirements Document: Disposition Quality Control Dashboard

Version 1.0 | Owner: Project Lead (Data Analyst, Returns Quality) | Status: Approved for build | Data is synthetic.

## 1. Background

The DMAIC project on returns disposition quality reduced the audited defect rate from 6.8% to 3.0%. Sustaining that gain needs a weekly view that site leaders, QA and the ReCommerce program can act on without asking an analyst for a query. Today, defect data sits in audit spreadsheets, cycle-time data in the warehouse system and recovery value in Finance reports. Nobody sees them together, and nothing tells a site manager that a week is out of control.

## 2. Problem statement

Leaders cannot see disposition quality, recovery value and waste on one page, by site and shift, with statistical control limits. Special-cause weeks (for example the January backlog) are found weeks late, after the recovery value is gone.

## 3. Goals and non-goals

Goals:

1. One dashboard with weekly defect rate (p-chart with UCL/LCL), Pareto of defect causes, site and shift comparison, recovery $ achieved vs potential, waste units and cycle time.
2. Automated daily refresh from the returns data mart, no manual steps.
3. Clear out-of-control and off-target flags that map to the reaction plan in the Control Plan.

Non-goals:

- Associate-level performance ranking (the dashboard shows tenure bands, not named people).
- Real-time (sub-hour) monitoring.
- Replacing the QA audit tool.

## 4. Stakeholders (RACI)

| Stakeholder | Role in this dashboard | RACI |
|---|---|---|
| Returns QA Manager | Process owner; reviews weekly; triggers reaction plan | A |
| Project Lead (Data Analyst) | Requirements, data model, metric definitions, build | R |
| Business Intelligence Engineer | Data mart tables, scheduled refresh | R |
| Returns Operations Managers (4 sites) | Primary users; act on site/shift flags | C |
| ReCommerce Program Manager | Uses recovery and waste views | C |
| Software Development Engineer | Adds checklist and photo fields to the grading tool feed | C |
| Finance partner | Validates recovery $ definitions | C |
| Site shift leads | Read-only users | I |

## 5. Functional requirements

| ID | Requirement | Acceptance criteria |
|---|---|---|
| FR-1 | Show the weekly network defect rate as a p-chart with centre line, UCL and LCL computed per week from that week's audit count. | For a test week with n = 250 and p-bar = 3.0%, UCL shows 6.24% and LCL 0.00% (3-sigma, LCL floored at 0). |
| FR-2 | Allow the centre line and limits to be staged by phase (baseline vs control) and recalculated by an admin. | Admin can set a limit-recalculation date; chart shows two limit sets with a break. |
| FR-3 | Flag any week above UCL, or 7 consecutive weeks above the centre line, in red with the rule that fired. | Synthetic test data with one point above UCL is flagged with "Rule 1"; a run of 7 is flagged "Rule 2". |
| FR-4 | Show a Pareto of defect causes (count and cumulative %) for a user-selected date range. | Bars sorted descending; cumulative line ends at 100%; totals equal the defect count in the KPI tile. |
| FR-5 | Compare defect rate by site, shift, category and tenure band, with an index vs network average. | Selecting one site filters every panel; index = segment rate / network rate, shown to 2 decimals. |
| FR-6 | Show recovery value achieved vs potential and leakage $ by month and site. | Leakage = potential - achieved; monthly totals reconcile to the Finance recovery report within 0.5%. |
| FR-7 | Show waste units (resellable units sent to recycle or destroy) per 10k units, by site and month. | Waste count matches `sql/07_waste_units.sql` for the same filters. |
| FR-8 | Show dock-to-disposition cycle time (mean, p50, p90, p95) and % over the 48-hour SLA, with an I-MR chart of the daily mean. | Percentiles match `sql/05_cycle_time_percentiles.sql`; I-MR limits use 2.66 x MR-bar. |
| FR-9 | Show a pilot / before-after panel comparing any site's selected period with a reference period, with a two-proportion z-test p-value. | For RC-CENTRAL baseline vs pilot the panel shows p = 4.5e-11, matching `data/processed/hypothesis_tests.csv`. |
| FR-10 | Provide filters: date range, site, shift, category, phase, tenure band. | Every panel respects every filter; filter state persists in a shared URL. |
| FR-11 | Refresh daily by 06:00 local time; show the data-as-of timestamp. | Refresh log shows success for 20 of 20 business days in UAT. |
| FR-12 | Email a weekly PDF snapshot to site managers every Monday 08:00 with any red flags listed first. | Subscription delivers to the distribution list in UAT. |

## 6. Metric definitions

| Metric | Formula | Grain | Source | Owner |
|---|---|---|---|---|
| Disposition defect rate | audited units where assigned <> audited disposition / audited units | Week x site x shift | audits + units (`v_audited`) | Returns QA Manager |
| DPMO | defects / audited units x 1,000,000 (1 opportunity per unit) | Week, phase | `v_audited` | Returns QA Manager |
| Sigma level | short-term sigma from DPMO with 1.5-sigma shift (`sigma_lookup`) | Phase | `sigma_lookup` | Project Lead |
| First-pass yield | audited units correct and not re-graded / audited units | Week | `v_audited` | Returns QA Manager |
| Recovery rate | sum(recovery achieved $) / sum(potential recovery $) | Month x site | `v_units` | Finance partner |
| Recovery leakage $ | potential $ - achieved $ | Unit, summed | `v_units` | Finance partner |
| Waste units | units assigned RECYCLE/DESTROY whose correct disposition is resellable | Unit, summed | `v_units` (waste_flag) | ReCommerce Program Manager |
| Dock-to-disposition hours | sum of dock wait, triage, queue, grading and routing hours | Unit | `cycle_stages` | Returns Operations Manager |
| SLA breach rate | units with dock-to-disposition > 48 h / units | Week x site | `v_units` | Returns Operations Manager |
| Photo step compliance | units with photo captured / units graded | Week x site | `units.photo_step_done` | Returns Operations Manager |

## 7. Data requirements

- Unit grain table with site, shift, associate (anonymized ID), category, SOP version, photo flag, price, assigned disposition, potential and achieved recovery $, waste and complaint flags (see `data/raw/returns_units.csv`).
- Stage-time table at unit grain (`data/raw/unit_cycle_stages.csv`).
- Audit table with audited disposition and defect cause code (`data/raw/audits.csv`).
- Associate dimension with hire date for tenure bands (`data/raw/associates.csv`).
- Daily extract for the BI tool: `dashboard/tableau_extract.csv` (day x site x shift x category).
- New field requested: checklist completion flag from the grading tool (owner: Software Development Engineer).

## 8. Assumptions

- QA audits are a random sample within site and day, and the audit decision is the reference for correct disposition.
- Associate IDs are anonymized. The dashboard never shows names.
- Potential recovery value is supplied by the ReCommerce pricing model.

## 9. Risks

| Risk | Impact | Mitigation |
|---|---|---|
| Low weekly audit count at small sites widens limits | Real shifts missed | Show network chart by default; site charts use 4-week rolling window |
| Auditor disagreement | False defects | Quarterly attribute agreement analysis, target kappa >= 0.8 |
| Dashboard used to rank individuals | Morale, gaming | Tenure band and shift only; no associate-level view |

## 10. Open questions

1. Should the Control Plan target tighten to 3.0% once 12 weeks of stable data exist?
2. Does Finance want leakage valued at resale price or at net recovery after channel fees?
3. Can the photo images be sampled into the audit tool to speed up remote audits?

## 11. Timeline and milestones

| Milestone | Date |
|---|---|
| Requirements sign-off | 8 May 2026 |
| Data mart tables and extract | 22 May 2026 |
| Dashboard build complete | 5 Jun 2026 |
| UAT with 4 site managers | 8 to 19 Jun 2026 |
| Go-live and weekly email | 22 Jun 2026 |
