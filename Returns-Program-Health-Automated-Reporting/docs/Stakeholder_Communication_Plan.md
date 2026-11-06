# Stakeholder Communication Plan and Escalation Path

Program: Returns Experience and ReCommerce initiatives. Owner: ReCommerce Program Manager, with the Data Analyst for WBR content.

## 1. Principles

- One source of numbers: the WBR pipeline (`src/run_wbr.py`). Nobody presents a number that is not in the WBR or traceable to `sql/`.
- Lead with the decision needed, then the data. Write for a reader who has two minutes.
- Bad news travels fast: a Red KPI or a blocked dependency is communicated the day it is known, not held for the WBR.

## 2. Audiences and cadence

| Audience | What they need | Channel | Cadence | Owner |
|---|---|---|---|---|
| Director, Returns Experience & ReCommerce | Headline, Red items, decisions needed | PDF pre-read + WBR meeting | Weekly (Mon 08:00 pre-read, Tue review) | ReCommerce PgM |
| Initiative owners (5 teams) | Their KPIs, milestones, gaps due | Excel WBR (Gap List filtered by team) | Weekly | Data Analyst |
| Partner teams (Risk & Abuse, Transportation, Vendor Mgmt, Finance) | Asks routed to them, due dates | Email digest of their gap-list rows | Weekly, Monday | ReCommerce PgM |
| Engineering (SDM, Data Engineer) | Blockers on the critical path, data issues | Sprint sync + ticket | Weekly + ad hoc | Returns Experience Product Manager |
| Operations site leaders | Processing, grading and disposition KPIs | Dashboard (Tableau/QuickSight) | Daily view, weekly summary | Returns Operations Manager |
| Finance partner | Recovery $ and cost per return | Monthly business review | Monthly | Data Analyst |

## 3. Message templates

**KPI miss (owner to WBR):** "[KPI] was [actual] vs [target] ([variance]). Driver: [segment/cause]. Action: [countermeasure], owner [role], date-to-green [date]."

**Blocker (program manager to dependency owner):** "[Milestone] is blocked by [predecessor] ([team], forecast [date]). Impact: [downstream milestone / KPI]. Ask: firm date or interim workaround by [date]."

**Example from week of 2026-10-26:** "Refund cycle time was 3.77 days vs 3.30 days (+14.2%). Driver: US Mail-in transit up 2.22 days after carrier linehaul consolidation. Ask: Transportation Manager to assign a mitigation owner for R05 and bring a carrier SLA plan to the next WBR."

## 4. Escalation path

| Level | Trigger | Who | Response time | Forum |
|---|---|---|---|---|
| L0 Team | Amber KPI or milestone slip <= 7 days | Initiative owner resolves within the team | Next WBR | Team stand-up |
| L1 Program | Red KPI 1 week, slip > 7 days, or any cross-team dependency at risk | ReCommerce Program Manager with both team leads | 2 business days | Dependency sync (30 min) |
| L2 Sponsor | Red KPI 2+ consecutive weeks, blocked dependency, slip > 21 days, or High risk without mitigation | Director, Returns Experience & ReCommerce | At the WBR, or within 1 business day if urgent | WBR escalations section |
| L3 Leadership | Customer-impacting incident, policy or abuse exposure, or a launch date at risk | Sponsor escalates to the VP-level business owner | Same day | Written 1-page escalation |

Current escalations (week of 2026-10-26): 6 P1 gaps across 4 teams, including 2 High risks without mitigation (R04, R05) and M402, 63 days late, blocking 3 milestones.

## 5. Feedback loop

- After each WBR, the program manager sends decisions and action items within 24 hours (see `docs/meeting_notes_stakeholder_alignment.md` for the format).
- Quarterly survey of WBR readers: is the pre-read useful, what is missing, what can be cut.
