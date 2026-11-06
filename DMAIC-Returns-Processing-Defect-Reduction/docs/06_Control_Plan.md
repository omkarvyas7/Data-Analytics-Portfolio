# Control Plan: Returns Disposition Quality

Process owner: Returns QA Manager | Effective 1 May 2026 | Review: monthly for 6 months, then quarterly. Data is synthetic.

Control limits below come from the Control period (May to June 2026) unless stated. p-chart limits move with the weekly audit count n, so the values shown use the average Control-period n of 251 audits per week.

| # | Metric (CTQ) | Target / spec | Control limits | Frequency and method | Owner | Reaction plan |
|---|---|---|---|---|---|---|
| 1 | Network disposition defect rate (audited) | <= 3.5% | p-chart: CL 3.09%, UCL 6.36%, LCL 0.00% at n = 251 | Weekly, p-chart on dashboard | Returns QA Manager | Point above UCL or 7 weeks above CL: raise audit rate to 25% at the affected site for 1 week, Pareto the new defects, root cause in 48 h, correct SOP or retrain |
| 2 | Site defect rate | <= 4.0% per site, 4-week rolling | p-chart per site (4-week window) | Weekly | Returns Operations Manager (site) | Site above UCL: shift-lead huddle, side-by-side grading calibration with QA |
| 3 | Defect rate, associates with tenure < 30 days | <= 6.0% | Monthly attribute chart | Monthly | Learning & Development | Above target: extend buddy period to 4 weeks; restrict new hires from Electronics grading until certified |
| 4 | Photo step compliance | >= 95% (Control actual 96.1%) | Lower limit 93% | Daily, grading-tool report | Returns Operations Manager | Below 93% on any shift: station check (camera, UI), shift-lead follow-up same day |
| 5 | Checklist completion (new grading-tool field) | >= 98% | Lower limit 95% | Daily | Software Development Engineer (feed), site ops (behaviour) | Field missing: fix feed within 2 business days; low completion: coach at start-of-shift |
| 6 | Mean dock-to-disposition hours (daily) | <= 12 h | I-MR: X-bar 10.3 h, UCL 10.8 h, LCL 9.7 h | Daily, I-MR chart | Returns Operations Manager | Above UCL 2 days in a row: open overflow grading stations, pull flex labor; at backlog index > 1.1, add a second QA audit pass for Electronics |
| 7 | % units over 48 h SLA | < 1.0% (Control actual 0.00%) | Upper limit 1.0% | Weekly | Returns Operations Manager | Above 1%: daily backlog review with Workforce Planning |
| 8 | Recovery rate (achieved / potential $) | >= 97.0% (Control actual 97.4%) | Lower limit 96.5% | Monthly | Finance partner | Below 96.5%: leakage Pareto by category and site; joint review with ReCommerce |
| 9 | Waste units per 10k processed | <= 22.0 (50% of baseline) | Upper limit 25 per 10k | Weekly | ReCommerce Program Manager | Above limit: 100% second check on units routed to recycle/destroy for 2 weeks |
| 10 | Customer complaint rate (condition not as described) | <= 0.72% | Upper limit 0.90% | Monthly | ReCommerce Program Manager | Above limit: sample complaints, check upgrade misgrades by category |

## Standard work and documents controlled

- Grading SOP v3.0 with the open-box / electronics visual grading matrix (owner: Returns QA Manager, with the version number and effective date tracked in `sop_versions`).
- 8-point grading checklist embedded in the grading tool.
- Mandatory photo capture before a disposition can be submitted.
- New-hire onboarding: 2-week buddy period and Electronics certification.

## Hand-off

The Project Lead hands the dashboard, SQL (`sql/`), weekly feed (`sql/09_weekly_control_chart_feed.sql`) and this plan to the Returns QA Manager on 30 June 2026. The project closes when 8 weeks of Control data stay in statistical control; the Control period had 0 out-of-control signals in 8 full weeks.
