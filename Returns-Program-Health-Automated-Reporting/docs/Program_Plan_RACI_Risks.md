# Program Plan: Returns Experience and ReCommerce Initiatives (FY26 H2)

Status as of 2026-11-01. Source of truth: `excel/Program_Tracker.xlsx`; roll-up logic in `sql/06_program_health_initiative.sql`.

## 1. Objectives

Each initiative is tied to one KPI it is supposed to move:

| Initiative | Primary KPI | Current (week of 2026-10-26) | Target |
|---|---|---|---|
| INI-1 Grade-and-resell open-box electronics | Resold share of dispositions | 49.6% | 50.0% |
| INI-2 Returnless refunds for low-value items | Cost per return | $7.05 | $6.80 |
| INI-3 Drop-off point expansion | Refund cycle time | 3.77 days | 3.30 days |
| INI-4 Return reason capture redesign | Customer contacts per return | 0.192 | 0.180 |
| INI-5 Liquidation partner onboarding | Recovery rate | 38.6% | 36.0% |

## 2. Current health

| Initiative | Team | Done | At risk | Blocked | Max slip (d) | Open High risks | RAG |
|---|---|---|---|---|---|---|---|
| Drop-off point expansion | Reverse Logistics Ops | 3/6 | 2 | 1 | 56 | 2 | Red |
| Return reason capture redesign | Returns Experience Tech | 1/5 | 3 | 2 | 63 | 1 | Red |
| Grade-and-resell open-box electronics | ReCommerce | 3/6 | 1 | 0 | 21 | 1 | Amber |
| Returnless refunds for low-value items | Returns Policy | 4/6 | 0 | 0 | 14 | 1 | Amber |
| Liquidation partner onboarding | Liquidation & Disposition | 3/5 | 0 | 0 | 14 | 0 | Green |

2 initiatives are Red (Drop-off point expansion, Return reason capture redesign). 6 milestones are at risk and 3 are blocked by a dependency. The critical path runs through M402 (QR label and reason-code API), 63 days late with a forecast of 2026-11-13; it blocks drop-off Wave 2 (M304) and two reason-capture milestones.

## 3. Governance and cadence

- Weekly WBR (Tuesday, 45 min): sponsor, initiative owners, finance partner. Pre-read is `reports/WBR_<week>.pdf`, published Monday 08:00.
- Tracker cut-off: owners update status, % complete and forecast dates by Friday 17:00.
- Monthly business review: re-baseline requests, target changes, resourcing.
- Change control: a milestone date moves only with the owner's forecast and a reason in the issue log; targets change only with KPI-owner sign-off.

## 4. RACI

| Activity | Sponsor (Director) | ReCommerce PgM | Data Analyst | Returns Ops Mgr | Reverse Logistics PgM | PM Returns Experience | Disposition PgM | SDM / Data Eng | Finance partner |
|---|---|---|---|---|---|---|---|---|---|
| Set KPI targets | A | C | C | R | R | R | R | I | C |
| Maintain milestone tracker | I | A | C | R | R | R | R | R | I |
| Build and run WBR pipeline | I | C | A/R | I | I | I | I | C | I |
| Explain KPI misses (root cause) | I | C | R | R | R | R | R | C | C |
| Escalate cross-team blockers | A | R | C | C | C | C | C | C | I |
| Approve re-baselines | A | R | I | C | C | C | C | C | C |
| Source data feeds and scheduling | I | I | C | I | I | I | I | A/R | I |
| Validate $ recovery and cost | I | I | C | I | I | I | C | I | A/R |

R = responsible, A = accountable, C = consulted, I = informed.

## 5. Milestones

| ID | Initiative | Milestone | Owner role | Planned end | Forecast / actual | Status | Slip (d) | RAG |
|---|---|---|---|---|---|---|---|---|
| M101 | INI-1 | Grading SOP and condition codes defined | ReCommerce Program Manager | 2026-03-13 | 2026-03-20 | Complete | 7 | Complete |
| M102 | INI-1 | Grading station pilot at 2 sites | Returns Operations Manager | 2026-05-08 | 2026-05-22 | Complete | 14 | Complete |
| M103 | INI-1 | Open-box listing integration | Software Development Manager | 2026-07-31 | 2026-08-21 | Complete | 21 | Complete |
| M104 | INI-1 | Scale grading to 6 sites | Returns Operations Manager | 2026-10-30 | 2026-11-20 | At Risk | 21 | Amber |
| M105 | INI-1 | Price optimization for graded tiers | ReCommerce Analyst | 2026-12-11 | 2026-12-18 | On Track | 7 | Green |
| M106 | INI-1 | Program review and handoff to operations | ReCommerce Program Manager | 2027-01-15 | - | Not Started | 0 | Green |
| M201 | INI-2 | Policy thresholds and abuse guardrails | Returns Policy Manager | 2026-04-10 | 2026-04-10 | Complete | 0 | Complete |
| M202 | INI-2 | Abuse-prevention rules with Risk partner | Risk & Abuse Prevention Manager | 2026-05-29 | 2026-06-12 | Complete | 14 | Complete |
| M203 | INI-2 | Launch returnless in Beauty/Toys (US) | Returns Policy Manager | 2026-06-30 | 2026-07-03 | Complete | 3 | Complete |
| M204 | INI-2 | Extend to Apparel and UK/DE | Returns Policy Manager | 2026-10-16 | 2026-10-30 | Complete | 14 | Complete |
| M205 | INI-2 | Bad-debt and abuse monitoring dashboard | Business Intelligence Engineer | 2026-11-13 | 2026-11-13 | On Track | 0 | Green |
| M206 | INI-2 | Expand to CA | Returns Policy Manager | 2026-12-18 | - | Not Started | 0 | Green |
| M301 | INI-3 | Site selection model and partner shortlist | Reverse Logistics Program Manager | 2026-02-27 | 2026-02-27 | Complete | 0 | Complete |
| M302 | INI-3 | Retail drop-off partner contracts signed | Vendor Manager | 2026-04-24 | 2026-05-15 | Complete | 21 | Complete |
| M303 | INI-3 | Wave 1 go-live (400 points, US) | Reverse Logistics Program Manager | 2026-06-26 | 2026-07-10 | Complete | 14 | Complete |
| M304 | INI-3 | Wave 2 go-live (900 points, US/CA) | Reverse Logistics Program Manager | 2026-10-02 | 2026-11-27 | Blocked | 56 | Red |
| M305 | INI-3 | Carrier consolidation SLA review | Transportation Manager | 2026-11-06 | 2026-11-20 | At Risk | 14 | Amber |
| M306 | INI-3 | Wave 3 plan and business case | Reverse Logistics Program Manager | 2026-12-18 | - | Not Started | 0 | Green |
| M401 | INI-4 | Customer research and reason taxonomy | UX Researcher | 2026-05-15 | 2026-05-22 | Complete | 7 | Complete |
| M402 | INI-4 | QR label and reason-code API | Software Development Manager | 2026-09-11 | 2026-11-13 | At Risk | 63 | Red |
| M403 | INI-4 | Return-flow UX redesign A/B test | Returns Experience Product Manager | 2026-10-23 | 2026-12-04 | Blocked | 42 | Red |
| M404 | INI-4 | Reason-code data feed to Operations | Data Engineer | 2026-12-04 | 2026-12-18 | Not Started | 14 | Red |
| M405 | INI-4 | Launch to all marketplaces | Returns Experience Product Manager | 2027-01-29 | - | Not Started | 0 | Green |
| M501 | INI-5 | RFP and partner scoring | Disposition Program Manager | 2026-04-17 | 2026-04-17 | Complete | 0 | Complete |
| M502 | INI-5 | Partner 1 onboarding (US electronics/home) | Disposition Program Manager | 2026-06-26 | 2026-06-26 | Complete | 0 | Complete |
| M503 | INI-5 | Partner 2 onboarding (EU) | Disposition Program Manager | 2026-09-25 | 2026-10-09 | Complete | 14 | Complete |
| M504 | INI-5 | Auction price floors and recovery tracking | Finance Partner | 2026-11-20 | 2026-11-20 | On Track | 0 | Green |
| M505 | INI-5 | Partner 3 onboarding (apparel bulk lots) | Disposition Program Manager | 2026-12-18 | 2026-12-18 | On Track | 0 | Green |

Slip = actual or forecast end minus planned end (or days overdue when no forecast). RAG rules: Red if Blocked, blocked by dependency, or slip > 21 days; Amber if At Risk, slip > 7 days, or the planned start has passed without a start.

## 6. Risk register

| ID | Initiative | Risk | L | I | Severity | Status | Owner role | Mitigation | Close by |
|---|---|---|---|---|---|---|---|---|---|
| R01 | INI-1 | Grading labor not staffed at 4 of 6 scale sites before peak | 4 | 4 | 16 | Open | Returns Operations Manager | Cross-train inbound associates; stagger site launches | 2026-11-13 |
| R02 | INI-1 | Open-box price erosion if graded supply outpaces demand | 3 | 3 | 9 | Mitigating | ReCommerce Analyst | Tiered price floors; weekly sell-through review | 2026-12-11 |
| R03 | INI-2 | Returnless refunds increase abuse / bad debt in new categories | 3 | 5 | 15 | Mitigating | Risk & Abuse Prevention Manager | Per-customer frequency caps; abuse dashboard (M205) | 2026-11-13 |
| R04 | INI-3 | QR label API slip blocks Wave 2 drop-off go-live | 5 | 4 | 20 | Open | Software Development Manager | (none recorded) | 2026-10-30 |
| R05 | INI-3 | Carrier linehaul consolidation lengthens US mail-in transit | 5 | 4 | 20 | Open | Transportation Manager | (none recorded) | 2026-11-06 |
| R06 | INI-3 | Retail partner capacity limits during holiday peak | 3 | 3 | 9 | Open | Vendor Manager | Peak capacity clauses; overflow to carrier pickup | 2026-12-18 |
| R07 | INI-4 | Engineering capacity shared with peak code freeze | 4 | 4 | 16 | Open | Software Development Manager | Request 2 additional SDEs; descope phase-2 fields | 2026-11-06 |
| R08 | INI-4 | Reason taxonomy change breaks downstream reports | 2 | 3 | 6 | Mitigating | Data Engineer | Mapping table and parallel run for 4 weeks | 2026-12-04 |
| R09 | INI-5 | EU partner recovery below business case | 2 | 4 | 8 | Closed | Disposition Program Manager | Auction floor pricing pilot | 2026-10-09 |
| R10 | INI-5 | Liquidation lot quality disputes delay payment | 3 | 2 | 6 | Open | Finance Partner | Standard lot manifest and photo audit | 2026-12-18 |

Severity = likelihood x impact (1-5 each). High >= 15. 2 High risks (R04, R05) have no mitigation recorded or are past their close date and are escalated on the WBR.

## 7. Dependencies

| Dependent milestone | Depends on | Owning team of predecessor | Type |
|---|---|---|---|
| M304 Wave 2 go-live | M402 QR label and reason-code API | Returns Experience Tech | Cross-team |
| M403 UX redesign A/B test | M402 | Returns Experience Tech | Same team |
| M404 Reason-code data feed | M402 | Returns Experience Tech | Same team |
| M106 Handoff to operations | M104 Scale grading to 6 sites | ReCommerce | Same team |
| M306 Wave 3 plan | M304 | Reverse Logistics Ops | Same team |

## 8. Lean / DMAIC application

- Define: each initiative maps to one primary KPI and target (section 1).
- Measure: weekly KPI layer (`sql/00-03`) with control-chart monitoring for cycle time.
- Analyze: driver decomposition (`sql/05`, `notebooks/analysis.ipynb`) separates rate vs mix and transit vs processing.
- Improve: gap list (`sql/10`) assigns countermeasures with owners and dates.
- Control: the WBR itself; RAG persistence (weeks missed of last 4) shows whether a fix held.
- Waste removed from the reporting process: manual copy-paste of four spreadsheets (about one analyst-day per week) replaced by one scheduled command.
